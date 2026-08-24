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
"""RELEVE A5 -- chaque constat porte sa mesure, ou n'est pas rendu."""
import inspect
import pathlib
import re
import sys
import tempfile

RACINE = pathlib.Path(r'C:\Users\selse\actuaria-app')
sys.path.insert(0, str(RACINE))

import numpy as np
import pandas as pd
import torch

from core.plan_tarifaire import PlanTarifaire

PLAN = PlanTarifaire.depuis_yaml(str(RACINE / 'plans' / 'auto.yaml'))
SRC = (RACINE / 'direction_non_vie/tarification/a5_deep_learning/agent.py'
       ).read_text(encoding='utf-8')
RES = []


def dire(cle, verdict, detail):
    RES.append((cle, verdict, detail))
    print(f'  [{verdict:9}] {cle:44} {detail}')


def jeu(n=1500, seed=42):
    rng = np.random.default_rng(seed)
    expo = rng.uniform(.1, 1., n)
    age = rng.integers(18, 75, n).astype(float)
    bm = rng.uniform(50, 350, n)
    lam = .18 * np.exp(.6 * (age < 25) + .004 * (bm - 100))
    nb = rng.poisson(lam * expo).astype(float)
    return {'success': True, 'branche': 'auto', 'statut_rag': 'VERT', 'erreur': None,
            'dataframe': pd.DataFrame({
                'nb_sinistres': nb,
                'cout_total_sinistres': np.where(nb > 0, rng.gamma(2, 400, n), 0.),
                'exposition': expo, 'age': age, 'bonus_malus': bm,
                'puissance_fiscale': rng.integers(4, 15, n).astype(float),
                'anciennete_permis': rng.integers(0, 50, n).astype(float),
                'age_vehicule': rng.integers(0, 20, n).astype(float),
                'antecedents_sinistres_n1': rng.poisson(.15, n).astype(float),
            })}


def r_a3(df):
    import statsmodels.api as sm
    feats = ['age', 'bonus_malus', 'puissance_fiscale']
    m = sm.GLM(df['nb_sinistres'], sm.add_constant(df[feats]),
               family=sm.families.Tweedie(var_power=1.5, link=sm.families.links.Log()),
               offset=np.log(np.maximum(df['exposition'].to_numpy(), 1e-6))).fit(maxiter=60)
    return {'success': True, 'branche': 'auto',
            'metriques': {'poisson': {'gini': 0.14, 'rmse_test': 0.3}},
            'modeles': {'tweedie': m}}


def a5():
    from direction_non_vie.tarification.a5_deep_learning.agent import (
        AgentA5DeepLearning,
    )
    d = tempfile.mkdtemp(prefix='a5_')
    return AgentA5DeepLearning(models_path=d, audit_path=d, verbose=False)


_R = {}


def run(graph=False, seed_torch=1):
    if (graph, seed_torch) not in _R:
        j = jeu()
        np.random.seed(seed_torch)
        torch.manual_seed(seed_torch)
        _R[(graph, seed_torch)] = a5().run(
            result_a2=j, result_a3=r_a3(j['dataframe']), plan=PLAN,
            col_cible='nb_sinistres', n_epochs=12, batch_size=256,
            generer_graphiques=graph)
    return _R[(graph, seed_torch)]


# =================================================================
# R1 -- l early stopping se regle-t-il sur le jeu de TEST ?
# =================================================================
def r1():
    for nom in ('_calibrer_cann', '_calibrer_tabnet'):
        corps = re.search(rf'def {nom}\(.*?(?=\n    # ={{10,}})', SRC, re.DOTALL).group(0)
        val_sur_test = bool(re.search(r'pred_val = modele\(X_test_t', corps))
        best_state = 'best_state' in corps and 'val_loss < best_val_loss' in corps
        jeu_valid = bool(re.search(r'X_val|y_val\b', corps))
        dire(f'R1 {nom} : early stopping',
             'CONSTAT' if (val_sur_test and best_state and not jeu_valid) else 'BON',
             f'val_loss calculee sur X_test = {val_sur_test} · best_state '
             f'selectionne dessus = {best_state} · jeu de validation distinct = {jeu_valid}')


# =================================================================
# R2 -- les courbes d apprentissage lisent-elles les bonnes cles ?
# =================================================================
def r2():
    r = run(graph=True)
    hist = r['historique_cann']
    cles_reelles = sorted(hist[0]) if hist else []
    cles_lues = sorted(set(re.findall(r"h\.get\('(\w+)', 0\)", SRC)))
    fig = r['graphiques'].get('apprentissage_cann')
    traces = {t.name: list(t.y) for t in fig.data} if fig is not None else {}
    tout_nul = all(all(v == 0 for v in y) for y in traces.values()) if traces else None
    dire('R2 courbes d apprentissage (CANN)',
         'CONSTAT' if tout_nul else 'BON',
         f'cles de l historique = {cles_reelles} · cles LUES = {cles_lues} · '
         f'traces = { {k: len(v) for k, v in traces.items()} } toutes a zero = {tout_nul}')


# =================================================================
# R3 -- H1 convergence : mesuree ou simulee ?
# =================================================================
def r3():
    ag = a5()
    corps = inspect.getsource(ag._valider_hypotheses_dl)
    simule = 'Simuler les losses' in corps
    dur = bool(re.search(r'loss_init\s*=\s*0\.50', corps))
    r = run()
    h1 = r['validation_dl']['h1_convergence']
    dire('R3 H1 convergence', 'CONSTAT' if (simule and dur) else 'BON',
         f'commentaire dit "Simuler les losses" = {simule} · loss_init=0.50 code '
         f"en dur = {dur} · rendu : statut={h1['statut']} loss_final={h1['loss_final']} "
         f"ratio={h1['ratio_conv']}")


# =================================================================
# R4 -- les trois hypotheses DL lisent-elles une cle qui existe ?
# =================================================================
def r4():
    r = run()
    met = r['metriques']['cann']
    cle_ok = 'gini' in met
    v = r['validation_dl']
    statuts = {k: v[k]['statut'] for k in ('h1_convergence', 'h2_surapprentissage', 'h3_apport_dl')}
    reel = {k: r['metriques'][k]['gini_test'] for k in r['metriques']}
    dire('R4 cle "gini" dans les metriques DL',
         'CONSTAT' if not cle_ok else 'BON',
         f"cles = {sorted(met)[:5]}… · 'gini' presente = {cle_ok} · "
         f'statuts publies = {statuts} · Gini REELS = ' +
         str({k: round(x, 4) for k, x in reel.items()}))


# =================================================================
# R5 -- le graphique de convergence est-il fabrique ?
# =================================================================
def r5():
    corps = re.search(r'# G1 — Courbe de convergence.*?graphiques\["convergence_loss"\]',
                      SRC, re.DOTALL).group(0)
    expo = bool(re.search(r'np\.exp\(-3 \* e / n_ep\)', corps))
    bruit = bool(re.search(r'np\.random\.normal\(\)', corps))
    n_dur = bool(re.search(r'n_ep\s*=\s*50', corps))
    r1_ = run(graph=True)
    fig = r1_['graphiques_validation'].get('convergence_loss')
    n_pts = len(fig.data[0].y) if fig is not None else None
    dire('R5 graphique de convergence', 'CONSTAT' if expo else 'BON',
         f'courbe = exponentielle analytique {expo} · bruit np.random.normal() '
         f'NON SEME = {bruit} · 50 epoques codees en dur = {n_dur} · '
         f'points traces = {n_pts} (epoques REELLES = '
         f"{r1_['metriques']['cann']['n_epochs_reels']})")


# =================================================================
# R6 -- G2 : les barres CANN/TabNet valent-elles zero ?
# =================================================================
def r6():
    r = run(graph=True)
    fig = r['graphiques_validation'].get('comparaison_dl_glm')
    if fig is None:
        dire('R6 barres DL vs GLM', 'NON MESURE', 'figure absente')
        return
    y = list(fig.data[0].y)
    reel = [r['metriques'][k]['gini_test'] for k in ('cann', 'tabnet')]
    dire('R6 barres DL vs GLM', 'CONSTAT' if y[1] == 0 and y[2] == 0 else 'BON',
         f'barres [GLM, CANN, TabNet] = {[round(v,4) for v in y]} · '
         f'Gini REELS CANN/TabNet = {[round(v,4) for v in reel]}')


# =================================================================
# R7 -- A5 fixe-t-il un seed ? (reproductibilite S2)
# =================================================================
def r7():
    seeds = re.findall(r'torch\.manual_seed|np\.random\.seed\(', SRC)
    j = jeu()
    ra3 = r_a3(j['dataframe'])
    g = []
    for _ in range(2):
        g.append(a5().run(result_a2=jeu(), result_a3=ra3, plan=PLAN,
                          col_cible='nb_sinistres', n_epochs=6, batch_size=256,
                          generer_graphiques=False)['metriques']['tabnet']['gini_test'])
    dire('R7 reproductibilite (aucun seed fixe)',
         'CONSTAT' if g[0] != g[1] else 'BON',
         f'{len(seeds)} appel(s) a un seed dans le module · deux runs identiques '
         f'-> Gini TabNet {g[0]} puis {g[1]}')


# =================================================================
# R8 -- COLS_A_EXCLURE hors perimetre + en-tete de test
# =================================================================
def r8():
    from direction_non_vie.tarification.a5_deep_learning.agent import COLS_A_EXCLURE
    hors = [c for c in COLS_A_EXCLURE if any(m in c for m in
            ('salarie', 'adherent', 'beneficiaire', 'ij_', 'cotisation_mensuelle'))]
    dire('R8a COLS_A_EXCLURE hors Non-Vie', 'CONSTAT' if hors else 'BON',
         f'{len(COLS_A_EXCLURE)} entrees, dont {len(hors)} Vie/Sante : {hors}')
    t = (RACINE / 'direction_non_vie/tarification/a5_deep_learning'
         / 'test_a5_deep_learning.py').read_text(encoding='utf-8')
    ann = re.search(r'(\d+)\s+tests', t)
    reels = len(re.findall(r'^\s+def (test_\w+)', t, re.MULTILINE))
    dire('R8b en-tete de test << N tests >>',
         'CONSTAT' if ann and int(ann.group(1)) != reels else 'BON',
         f'annonce {ann.group(1) if ann else "?"} · methodes reelles = {reels}')


# =================================================================
# R9 -- VERIFICATIONS POSITIVES
# =================================================================
def r9():
    ag = a5()
    j = jeu()
    a = not ag.run(result_a2=j, plan=None, col_cible='nb_sinistres')['success']
    b = not ag.run(result_a2=j, plan=PLAN, col_cible=None)['success']
    r = run()
    m = r['metriques']['cann']
    c = m.get('glm_gele') is True
    d = m.get('glm_verification_error') is not None and m['glm_verification_error'] < 1e-3
    # mode degrade -> alerte surfacee
    np.random.seed(1); torch.manual_seed(1)
    rd = a5().run(result_a2=jeu(), result_a3={'success': True, 'metriques': {}, 'modeles': {}},
                  plan=PLAN, col_cible='nb_sinistres', n_epochs=3, batch_size=256,
                  generer_graphiques=False)
    e = any(x.get('code') == 'cann_glm_non_ancre' for x in rd.get('alertes_modele', []))
    f_ = bool(re.search(r'scaler\.fit_transform\(X_raw_train\)', SRC)) and \
        bool(re.search(r'scaler\.transform\(X_raw_test\)', SRC))
    g_ = bool(re.search(r'np\.clip\(2 \* auc - 1, -1\.0, 1\.0\)', SRC))
    bloc = re.search(r'# G4 — Scorecard validation DL.*?return graphiques', SRC, re.DOTALL).group(0)
    items = len(re.findall(r'\("H\d', bloc))
    ann = re.search(r'(\d+)\s*✅\s*=\s*Deep Learning valid', bloc)
    h_ = ann and int(ann.group(1)) == items
    for cle, ok, det in (
            ('R9a plan absent -> erreur propre', a, ''),
            ('R9b col_cible absente -> erreur propre', b, 'defaut prime_pure supprime'),
            ('R9c CANN ancre : glm_gele=True', c, f"{m.get('n_vars_glm_matchees')}/{m.get('n_vars_glm_total')} vars"),
            ('R9d verification epoque0 == GLM', d, f"ecart={m.get('glm_verification_error')}"),
            ('R9e mode degrade -> alerte surfacee', e, 'cann_glm_non_ancre'),
            ('R9f scaler ajuste sur TRAIN seul', f_, 'pas de fuite au scaler'),
            ('R9g Gini non ecrete a zero', g_, 'clip(-1, 1)'),
            ('R9h scorecard : compte exact', h_, f'annonce {ann.group(1) if ann else "?"}, {items} items')):
        dire(cle, 'BON' if ok else 'CONSTAT', det)


def main() -> int:
    print('  RELEVE A5 -- chaque ligne est une mesure\n')
    for f in (r1, r2, r3, r4, r5, r6, r7, r8, r9):
        try:
            f()
        except Exception as e:
            dire(f.__name__.upper(), 'NON MESURE', f'{type(e).__name__}: {e}')
    print('\n  ' + '=' * 80)
    for v in ('CONSTAT', 'BON', 'NON MESURE'):
        print(f'  {v:11} : {sum(1 for _, x, _ in RES if x == v)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
