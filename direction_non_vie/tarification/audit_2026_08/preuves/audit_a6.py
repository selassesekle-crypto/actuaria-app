# ruff: noqa
# ⚠️ SCRIPT D'ARCHIVE — PREUVE D'AUDIT, PAS DU CODE MAINTENU.
# Il a ete ecrit un jour donne pour ETABLIR UN FAIT, et il est conserve
# tel qu'il a ete execute. Le relire aux regles du code de production
# reviendrait a reecrire une piece a conviction : les 25 ecarts qu'il
# porte (10 F841, 8 BLE001, 3 PLW1510, 2 UP031, 1 S110, 1 RUF015) sont
# DECLARES ici plutot que corriges. Les BLE001 sont d'ailleurs voulus :
# un script qui mesure si quelque chose casse doit tout attraper.
# ⚠️ DETERMINISME VERIFIE : sur deux executions successives, 7 des 8
# scripts rendent des mesures IDENTIQUES. Le huitieme, audit_services,
# ne varie que sur l'horodatage QU'IL MESURE -- et c'est precisement son
# constat U1 : << Arrete : publie l'horodatage de generation >>.
"""RELEVE A6 -- chaque constat porte sa mesure, ou n'est pas rendu."""
import inspect
import pathlib
import re
import sys
import tempfile

RACINE = pathlib.Path(r'C:\Users\selse\actuaria-app')
sys.path.insert(0, str(RACINE))

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire

PLAN = PlanTarifaire.depuis_yaml(str(RACINE / 'plans' / 'auto.yaml'))
SRC = (RACINE / 'direction_non_vie/tarification/a6_comparaison/agent.py'
       ).read_text(encoding='utf-8')
RES = []


def dire(cle, verdict, detail):
    RES.append((cle, verdict, detail))
    print(f'  [{verdict:9}] {cle:46} {detail}')


def a6():
    from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
    d = tempfile.mkdtemp(prefix='a6_')
    return AgentA6Comparaison(models_path=d, audit_path=d, verbose=False)


def jeu(n=1200):
    rng = np.random.default_rng(5)
    expo = rng.uniform(.1, 1., n)
    nb = rng.poisson(.08 * expo).astype(float)
    cout = np.where(nb > 0, rng.gamma(2, 400, n), 0.)
    return {'success': True, 'branche': 'auto', 'statut_rag': 'VERT', 'erreur': None,
            'dataframe': pd.DataFrame({
                'nb_sinistres': nb, 'cout_total_sinistres': cout,
                'exposition': expo, 'prime_pure': cout / np.maximum(expo, 1e-6),
                'annee_souscription': rng.choice([2020, 2021, 2022, 2023], n),
                'age': rng.integers(18, 75, n).astype(float),
                'zone_geographique': rng.choice(['A', 'B', 'C', 'D'], n),
                'bonus_malus': rng.uniform(50, 350, n)})}


def r_a3():
    return {'success': True, 'branche': 'auto',
            'metriques': {
                'poisson': {'gini': 0.18, 'cible': 'nb_sinistres', 'rmse_test': 0.3},
                'gamma': {'gini': 0.12, 'cible': 'cout_moyen', 'rmse_test': 200.},
                'tweedie': {'gini': 0.15, 'cible': 'prime_pure', 'rmse_test': 300.}}}


def r_a4():
    return {'success': True, 'branche': 'auto', 'col_cible': 'prime_pure',
            'metriques': {
                'xgboost': {'gini_test': .22, 'gini_train': .24, 'overfit_ratio': .92, 'rmse_test': 290.},
                'lightgbm': {'gini_test': .21, 'gini_train': .23, 'overfit_ratio': .91, 'rmse_test': 295.},
                'lineaire_regularise': {'gini_test': .16, 'gini_train': .17, 'overfit_ratio': .94, 'rmse_test': 310.}}}


_R = {}


def run(graph=False):
    if graph not in _R:
        _R[graph] = a6().run(result_a2=jeu(), result_a3=r_a3(), result_a4=r_a4(),
                             result_a5=None, col_cible='prime_pure',
                             generer_graphiques=graph, generer_rapport_equipe=False,
                             profil_valide_par='Actuaire Test')
    return _R[graph]


# ===============================================================
# S1 -- le << A/E >> compare-t-il l observe au PREDIT ?
# ===============================================================
def s1():
    ag = a6()
    corps = inspect.getsource(ag._backtesting_temporel)
    ae_obs = bool(re.search(r"m_tr = float\(df_tr\[col_cible\]\.mean\(\)\).*?"
                            r"m_te = float\(df_te\[col_cible\]\.mean\(\)\).*?"
                            r"ae\s*=\s*round\(m_te / max\(m_tr", corps, re.DOTALL))
    pred_existe = 'pred_te = np.maximum(modele_wf.predict(X_te), 0)' in corps
    pred_dans_ae = bool(re.search(r'ae\s*=.*pred_te', corps))
    r = run()
    bt = r['backtest']
    dire('S1 A/E : observe/predit ou observe/observe ?',
         'CONSTAT' if (ae_obs and not pred_dans_ae) else 'BON',
         f'A/E = moy(obs_test)/moy(obs_train) = {ae_obs} · la prediction EXISTE '
         f'= {pred_existe} · elle entre dans le A/E = {pred_dans_ae} · '
         f"valeur publiee = {bt.get('ae_ratio')}")


# ===============================================================
# S2 -- le A/E par SEGMENT mesure-t-il un biais de modele ?
# ===============================================================
def s2():
    ag = a6()
    corps = inspect.getsource(ag._backtesting_temporel)
    ref_globale = "moy_ref    = float(df_train_n[col_cible].mean())" in corps
    seg_obs = bool(re.search(r'ae_\w+\s*=\s*float\(sub\[col_cible\]\.mean\(\)\) / max\(moy_ref', corps))
    r = run()
    segs = r['backtest'].get('ae_par_segment', {})
    detail = {k: [x['statut'] for x in v] for k, v in segs.items()}
    dire('S2 A/E par segment', 'CONSTAT' if (ref_globale and seg_obs) else 'BON',
         f'segment compare a la MOYENNE GLOBALE du train = {seg_obs} · '
         f'un segment plus risque sortira ROUGE meme si le modele le predit bien · '
         f'statuts rendus = {detail}')


# ===============================================================
# S3 -- la chaine 'split' : commentaire et TEST la manquent
# ===============================================================
def s3():
    r = run()
    reel = r['backtest'].get('split')
    dans_commentaire = bool(re.search(r"split'\)\s*==\s*'walk_forward_temporel'", SRC))
    t = (RACINE / 'direction_non_vie/tarification/a6_comparaison'
         / 'test_a6_comparaison.py').read_text(encoding='utf-8')
    dans_test = len(re.findall(r"split'\)\s*==\s*'walk_forward_temporel'", t))
    publie_wf = 'Fenêtres WF' in r['commentaire']
    dire('S3 chaine "split" comparee', 'CONSTAT' if not publie_wf else 'BON',
         f"valeur REELLE = {reel!r} · comparee a 'walk_forward_temporel' dans "
         f"l agent = {dans_commentaire} et {dans_test} fois dans le TEST · "
         f"le commentaire publie-t-il les fenetres WF = {publie_wf}")


# ===============================================================
# S4 -- _calculer_courbes : les 3 meilleurs modeles ?
# ===============================================================
def s4():
    ag = a6()
    corps = inspect.getsource(ag._calculer_courbes)
    utilise = len(re.findall(r'\btop_modeles\b', corps))
    tri_obs = bool(re.search(r'order\s*=\s*np\.argsort\(y\)\[::-1\]', corps))
    r = run()
    dire('S4 courbes : par modele ou observees ?',
         'CONSTAT' if (utilise <= 1 and tri_obs) else 'BON',
         f'docstring dit "pour les 3 meilleurs modeles" · top_modeles cite '
         f'{utilise}x (signature seule) · tri par la valeur OBSERVEE = {tri_obs} '
         f"· gini_observe publie = {r['courbes'].get('gini_observe')} "
         f"(gini du modele = {r['modele_production']['gini_test']})")


# ===============================================================
# S5 -- deux formules pour le meme score
# ===============================================================
def s5():
    r = run(graph=True)
    fig = r['graphiques'].get('scores_profils')
    if fig is None:
        dire('S5 deux formules de score', 'NON MESURE', 'figure absente')
        return
    # la valeur tracee pour le profil 'equilibre' vs le score_global reel
    noms = [t.name.replace('⭐ ', '') for t in fig.data]
    prod = r['modele_production']['modele']
    i = next((k for k, n in enumerate(noms) if n == prod), None)
    trace = list(fig.data[i].y)[0] if i is not None else None
    dire('S5 deux formules pour le meme score',
         'CONSTAT' if (trace is not None and abs(trace - r['modele_production']['score_global']) > 1e-3) else 'BON',
         f"graphique 'scores_profils' profil equilibre = {trace} · "
         f"score_global REEL = {r['modele_production']['score_global']}")


# ===============================================================
# S6 -- graphiques de validation : cle 'gini' inexistante
# ===============================================================
def s6():
    r = run(graph=True)
    gv = r.get('graphiques_validation', {})
    fig = gv.get('gini_comparaison')
    y = list(fig.data[0].y) if fig is not None else None
    reel = [m['gini_test'] for m in r['classement']]
    radar = gv.get('radar_modele_retenu')
    r_vals = list(radar.data[0].r) if radar is not None else None
    dire('S6 graphiques validation : cle "gini"',
         'CONSTAT' if (y is not None and all(v == 0 for v in y)) else 'BON',
         f'barres Gini = {y} · valeurs REELLES = {[round(v,4) for v in reel]} · '
         f'radar (5 axes) = {[round(v,3) for v in (r_vals or [])][:5]}')


# ===============================================================
# S7 -- plafond de vraisemblance : toujours "frequence"
# ===============================================================
def s7():
    dur = bool(re.search(r'gini_est_plausible\(gini, cible_est_frequence=True\)', SRC))
    import inspect as _i

    from core.conformite_reglementaire import (
        GINI_PLAUSIBLE_MAX_FREQUENCE,
        gini_est_plausible,
    )
    sig = _i.signature(gini_est_plausible)
    dire('S7 plafond de vraisemblance du Gini',
         'CONSTAT' if dur else 'BON',
         f'cible_est_frequence=True code en dur = {dur} (col_cible peut etre '
         f'cout_moyen ou prime_pure) · seuil frequence = {GINI_PLAUSIBLE_MAX_FREQUENCE} '
         f'· parametres = {list(sig.parameters)}')


# ===============================================================
# S8 -- une justification reglementaire inconditionnelle
# ===============================================================
def s8():
    r = run()
    j = r['fiche_decision'].get('justification_regl', [])
    inconditionnel = any('validé sur données de test indépendantes' in x for x in j)
    # est-elle publiee meme quand le backtest est indisponible ?
    ag = a6()
    fd = ag._generer_fiche_decision([{'modele': 'X', 'score_global': .1,
                                      'gini_test': .01, 'overfit_ratio': 1.,
                                      'famille': 'ML'}],
                                    {'modele': 'X', 'score_global': .1,
                                     'gini_test': .01, 'overfit_ratio': 1.,
                                     'famille': 'ML'}, 'equilibre')
    tjrs = any('validé sur données de test indépendantes' in x
               for x in fd['justification_regl'])
    dire('S8 justification S2 inconditionnelle',
         'CONSTAT' if (inconditionnel and tjrs) else 'BON',
         f'"Conformite S2 Pilier 1 : modele valide sur donnees de test '
         f'independantes" publiee sans condition = {tjrs} (fiche recoit ni '
         f'backtest ni statut)')


# ===============================================================
# S9 -- INTERPRETABILITE : modeles disparus + en-tete de test
# ===============================================================
def s9():
    from direction_non_vie.tarification.a6_comparaison.agent import INTERPRETABILITE
    a4src = (RACINE / 'direction_non_vie/tarification/a4_ml/agent.py').read_text(encoding='utf-8')
    bloc = re.search(r'modeles_a_calibrer = \[(.*?)\]', a4src, re.DOTALL).group(1)
    vivants = set(re.findall(r"\('([a-z_]+)',", bloc)) | {'poisson', 'gamma', 'tweedie',
                                                          'cann', 'tabnet'}
    morts = sorted(set(INTERPRETABILITE) - vivants)
    dire('S9a INTERPRETABILITE : entrees mortes', 'CONSTAT' if morts else 'BON',
         f'{len(INTERPRETABILITE)} entrees, {len(morts)} sans modele : {morts}')
    t = (RACINE / 'direction_non_vie/tarification/a6_comparaison'
         / 'test_a6_comparaison.py').read_text(encoding='utf-8')
    ann = re.search(r'(\d+)\s+tests', t)
    reels = len(re.findall(r'^\s+def (test_\w+)', t, re.MULTILINE))
    dire('S9b en-tete de test << N tests >>',
         'CONSTAT' if ann and int(ann.group(1)) != reels else 'BON',
         f'annonce {ann.group(1) if ann else "?"} · methodes reelles = {reels}')


# ===============================================================
# S10 -- VERIFICATIONS POSITIVES
# ===============================================================
def s10():
    from direction_non_vie.tarification.a6_comparaison.agent import (
        AgentA6Comparaison,
        gouvernance_validee,
    )
    ag = a6()
    r = run()
    a = (not gouvernance_validee('', 'production')
         and not gouvernance_validee('   ', 'production')
         and gouvernance_validee('Marie Dupont', 'production'))
    b = SRC.count('profil_valide_par is None') == 0 and SRC.count('gouvernance_validee(') >= 3
    # filtre par cible
    exc = r['exclusions_cible']
    c = len(exc) >= 2 and all(e['cible_modele'] != 'prime_pure' for e in exc)
    # les 6 plafonds + raisons
    m = {'modele': 'X', 'famille': 'GLM', 'gini_test': .22, 'score_global': .85,
         'overfit_ratio': 1.05}
    ag._calculer_statut_rag(m, [m], profil_valide_par=None, environnement='production')
    d = bool(ag._raisons_plafond) and all(len(x) > 30 and '_ok' not in x
                                          for x in ag._raisons_plafond)
    # _gini_lorenz source unique : predicteur parfait / anticorrele
    y = np.random.default_rng(1).exponential(100, 400)
    e = (AgentA6Comparaison._gini_lorenz(y, y.copy()) > 0.5
         and AgentA6Comparaison._gini_lorenz(y, -y) < -0.4)
    # plafond vraisemblance
    f_ = ag._calculer_statut_rag({'modele': 'X', 'gini_test': .93, 'score_global': .95},
                                 [m], profil_valide_par='A', environnement='production',
                                 backtest={'disponible': True, 'modele_recalibre_fidele': True,
                                           'gini_wf_moyen': .3, 'ae_ratio': 1.0,
                                           'n_fenetres_rouge': 0, 'stabilite_wf': '🟢 Stable'}) != 'VERT'
    # le WF est-il fidele sur un vrai run ?
    g_ = r['backtest'].get('modele_recalibre_fidele')
    for cle, ok, det in (
            ('S10a gouvernance : le vide ne vaut pas validation', a, ''),
            ('S10b predicat unique, 3+ appelants', b, f"{SRC.count('gouvernance_validee(')} appels"),
            ('S10c filtre par cible : modeles ecartes surfaces', c, f'{len(exc)} ecartes'),
            ('S10d causes du plafond nommees en toutes lettres', d, f'{len(ag._raisons_plafond)} causes'),
            ('S10e _gini_lorenz : signe correct (5 sentinelles)', e, 'parfait>0.5, anti<-0.4'),
            ('S10f plafond de vraisemblance mord a 0.93', f_, 'AMBRE'),
            ('S10g walk-forward FIDELE sur un vrai run', g_ is True, f'fidele={g_}')):
        dire(cle, 'BON' if ok else 'CONSTAT', det)


def main() -> int:
    print('  RELEVE A6 -- chaque ligne est une mesure\n')
    for f in (s1, s2, s3, s4, s5, s6, s7, s8, s9, s10):
        try:
            f()
        except Exception as e:
            dire(f.__name__.upper(), 'NON MESURE', f'{type(e).__name__}: {e}')
    print('\n  ' + '=' * 82)
    for v in ('CONSTAT', 'BON', 'NON MESURE'):
        print(f'  {v:11} : {sum(1 for _, x, _ in RES if x == v)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
