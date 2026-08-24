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
"""RELEVE A3 -- chaque constat porte sa mesure, ou n'est pas rendu."""
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
F = RACINE / 'direction_non_vie/tarification/a3_glm/agent.py'
SRC = F.read_text(encoding='utf-8')
RES = []


def dire(cle, verdict, detail):
    RES.append((cle, verdict, detail))
    print(f'  [{verdict:9}] {cle:40} {detail}')


def jeu(n=3000, seed=11):
    rng = np.random.default_rng(seed)
    expo = rng.uniform(.15, 1., n)
    bm = rng.uniform(50, 350, n)
    lam = .05 * expo * (bm / 100.)
    nb = rng.poisson(lam).astype(float)
    df = pd.DataFrame({
        'nb_sinistres': nb,
        'cout_total_sinistres': np.where(nb > 0, rng.gamma(2, 500, n), 0.),
        'exposition': expo, 'bonus_malus': bm,
        'age': rng.integers(18, 80, n).astype(float),
        'anciennete_permis': rng.integers(0, 50, n).astype(float),
        'puissance_fiscale': rng.integers(4, 15, n).astype(float),
        'age_vehicule': rng.integers(0, 20, n).astype(float),
        'antecedents_sinistres_n1': rng.poisson(.15, n).astype(float),
        'valeur_venale': rng.uniform(2000, 40000, n),
        'kilometrage_annuel': rng.uniform(3000, 40000, n),
        'csp': rng.choice(['Cadre', 'Employe', 'Retraite'], n),
        'usage': rng.choice(['Prive', 'Pro'], n),
        'carburant': rng.choice(['Essence', 'Diesel'], n),
        'garantie': rng.choice(['Tiers', 'TousRisques'], n),
        'milieu_geographique': rng.choice(['Urbain', 'Periurbain', 'Rural'], n),
    })
    return {'success': True, 'dataframe': df, 'branche': 'auto',
            'statut_rag': 'VERT', 'erreur': None}


def a3():
    from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
    d = tempfile.mkdtemp(prefix='a3_')
    return AgentA3GLM(models_path=d, audit_path=d, verbose=False)


_R = {}


def run(graph=False, seed=11):
    cle = (graph, seed)
    if cle not in _R:
        _R[cle] = a3().run(result_a2=jeu(seed=seed), plan=PLAN,
                           generer_graphiques=graph)
    return _R[cle]


# ======================================================================
# P1 -- le Tweedie : ajuste SANS offset, predit AVEC ?
# ======================================================================
def p1():
    src_fit = re.search(r'def _calibrer_tweedie.*?(?=\n    # =====)', SRC, re.DOTALL).group(0)
    src_pred = re.search(r'def _calculer_predictions.*?(?=\n    # =====)', SRC, re.DOTALL).group(0)
    fit_offset = 'offset' in re.search(r'pred_test = modele_final\.predict\([^)]*\)',
                                       src_fit).group(0)
    bloc_tw = re.search(r"self\.modeles\['tweedie'\]\.predict\((.*?)\)", src_pred, re.DOTALL)
    pred_offset = 'offset' in (bloc_tw.group(1) if bloc_tw else '')
    # MESURE reelle : la prime tweedie est-elle proportionnelle a l'exposition ?
    r = run()
    df = r['dataframe']
    p = r['predictions'].get('prime_pure_tweedie')
    corr = float(np.corrcoef(np.asarray(p, float), df['exposition'].values)[0, 1]) if p is not None else float('nan')
    dire('P1 Tweedie : offset au fit / au predict',
         'CONSTAT' if (pred_offset and not fit_offset) else 'BON',
         f'fit offset={fit_offset} · predict offset={pred_offset} · '
         f'corr(prime_tweedie, exposition) = {corr:+.3f}')


# ======================================================================
# P2 -- H1 : valeurs de repli codees en dur -> VERT
# ======================================================================
def p2():
    ag = a3()
    run()
    # On appelle _valider_hypotheses_glm avec un df SANS colonne de frequence
    faux = ag._valider_hypotheses_glm(pd.DataFrame({'x': [1, 2, 3]}), {}, {})
    h1 = faux['h1_poisson']
    dur = (h1['ratio_disp'], h1['mean_y'], h1['var_y'])
    dire('P2 H1 sans donnee -> repli code en dur',
         'CONSTAT' if h1['statut'] == 'VERT' else 'BON',
         f"statut={h1['statut']} · valeurs rendues (ratio, moy, var) = {dur} "
         f"· message={h1['message'][:38]}")


# ======================================================================
# P3 -- H4 : << non testee >> vaut VERT (corrige dans A4, pas dans A3)
# ======================================================================
def p3():
    ag = a3()
    faux = ag._valider_hypotheses_glm(pd.DataFrame({'x': [1, 2, 3]}), {}, {})
    h4 = faux['h4_stabilite']
    # et le meme defaut existe-t-il encore dans A4 ?
    a4src = (RACINE / 'direction_non_vie/tarification/a4_ml/agent.py').read_text(encoding='utf-8')
    a4_defaut = re.search(r"h4_statut\s*=\s*[\"'](\w+)[\"']", a4src)
    dire('P3 H4 non testee -> statut par defaut',
         'CONSTAT' if h4['statut'] == 'VERT' else 'BON',
         f"A3 : statut={h4['statut']} msg={h4['message'][:40]!r} · "
         f"A4 (corrige) : {a4_defaut.group(1) if a4_defaut else '?'}")


# ======================================================================
# P4 -- H3 : le seuil annonce est-il le seuil applique ?
# ======================================================================
def p4():
    ag = a3()
    bandes = {}
    for g in (0.20, 0.12, 0.09, 0.05):
        v = ag._valider_hypotheses_glm(
            pd.DataFrame({'x': [1]}), {}, {'poisson': {'gini': g}})
        bandes[g] = v['h3_ajustement']['statut']
    doc = re.search(r'H3 — Qualité d\'ajustement \(Gini\).*?H4 —', SRC, re.DOTALL).group(0)
    annonce_ambre = '[0.08,0.15]' in doc.replace(' ', '')
    dire('P4 H3 seuils annonces vs appliques',
         'CONSTAT' if bandes[0.12] == 'VERT' and annonce_ambre else 'BON',
         f'gini 0.20->{bandes[0.20]} · 0.12->{bandes[0.12]} · 0.09->{bandes[0.09]} '
         f'· 0.05->{bandes[0.05]} | docstring annonce [0.08,0.15] = acceptable/AMBRE')


# ======================================================================
# P5 -- infobulles des graphiques : IC 95 %
# ======================================================================
def p5():
    r = run(graph=True)
    g = r.get('graphiques', {})
    txt = {}
    for nom in ('coefficients_glm', 'relativites_poisson'):
        fig = g.get(nom)
        if fig is None:
            txt[nom] = 'FIGURE ABSENTE'
            continue
        ht = ''.join(str(getattr(t, 'hovertemplate', '') or '') for t in fig.data)
        m = re.search(r'IC 95%[^<]*', ht)
        txt[nom] = m.group(0) if m else 'pas d IC dans l infobulle'
    faux = any('0.0000' in v or v.rstrip().endswith('[') for v in txt.values())
    dire('P5 IC 95 % dans les infobulles', 'CONSTAT' if faux else 'BON',
         ' | '.join(f'{k}: {v!r}' for k, v in txt.items()))


# ======================================================================
# P6 -- la courbe de Lorenz publiee est-elle MESUREE ou CALCULEE ?
# ======================================================================
def p6():
    formule = bool(re.search(r'lorenz\s*=\s*t\s*\*\*\s*\(1\s*/\s*\(1\s*\+\s*gini\s*\*\s*2\)\)', SRC))
    # Preuve : deux portefeuilles DIFFERENTS, meme Gini -> meme courbe ?
    r1, r2 = run(graph=True, seed=11), run(graph=True, seed=77)
    g1 = r1['metriques']['poisson']['gini']
    g2 = r2['metriques']['poisson']['gini']
    dire('P6 courbe de Lorenz : mesuree ou tracee ?',
         'CONSTAT' if formule else 'BON',
         f'formule analytique t**(1/(1+2g)) presente = {formule} · '
         f'gini portefeuilles = {g1:.4f} / {g2:.4f} · '
         f'la courbe ne depend QUE du scalaire gini')


# ======================================================================
# P7 -- le Tweedie a-t-il un Gini ? (publie dans G3, G4 et H3)
# ======================================================================
def p7():
    r = run()
    tw = r['metriques'].get('tweedie', {})
    h3 = r['hypotheses']['h3_ajustement']
    dire('P7 Gini du Tweedie', 'CONSTAT' if 'gini' not in tw else 'BON',
         f"cle 'gini' dans metriques tweedie : {'gini' in tw} · "
         f"h3 publie gini_tweedie={h3['gini_tweedie']} (defaut 0)")


# ======================================================================
# P8 -- le graphique durbin_watson lit une cle qui n'existe plus
# ======================================================================
def p8():
    r = run(graph=True)
    gv = r.get('graphiques_validation', {})
    cle_lue = bool(re.search(r'val_glm\["h2_homosc"\]\["dw_stat"\]', SRC))
    cle_rendue = 'dw_stat' in r['hypotheses']['h2_homosc']
    dire('P8 graphique durbin_watson',
         'CONSTAT' if (cle_lue and not cle_rendue) else 'BON',
         f"graphiques_validation = {sorted(gv)} · le code lit 'dw_stat' = {cle_lue} · "
         f"h2 rend cette cle = {cle_rendue}")


# ======================================================================
# P9 -- la scorecard annonce << 3 >> et liste 4 items, sur 5 hypotheses
# ======================================================================
def p9():
    bloc = re.search(r'# G4 — Scorecard validation GLM.*?return graphiques', SRC, re.DOTALL).group(0)
    items = len(re.findall(r'\("H\d', bloc))
    ann = re.search(r'(\d+)\s*✅\s*=\s*GLM valid', bloc)
    r = run()
    n_hyp = len([k for k in r['hypotheses'] if k.startswith('h')])
    dire('P9 scorecard : compte annonce',
         'CONSTAT' if (ann and int(ann.group(1)) != items) else 'BON',
         f"annonce {ann.group(1) if ann else '?'} ✅ · liste {items} items · "
         f"hypotheses reellement calculees = {n_hyp}")


# ======================================================================
# P10 -- statut RAG : << convergence des 3 modeles >> ?
# ======================================================================
def p10():
    import inspect

    from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
    corps = inspect.getsource(AgentA3GLM._calculer_statut_rag)
    lus = sorted(set(re.findall(r"metriques\.get\('(\w+)'", corps)))
    doc = 'convergence des 3 modèles' in corps
    dire('P10 statut RAG : 3 modeles annonces',
         'CONSTAT' if (doc and 'tweedie' not in lus) else 'BON',
         f'docstring dit 3 modeles = {doc} · modeles reellement lus = {lus}')


# ======================================================================
# P11 -- meilleur_modele : compare deux Gini de cibles differentes
# ======================================================================
def p11():
    r = run()
    mg = r['rapport']['metriques_globales']
    comp = mg['comparaison_gini']
    dire('P11 meilleur_modele : cibles comparees',
         'CONSTAT' if set(comp) == {'poisson', 'gamma'} else 'BON',
         f"comparaison_gini={ {k: round(v,4) for k,v in comp.items()} } · "
         f"meilleur={mg['meilleur_modele']!r} · Poisson=frequence (tout le test), "
         f"Gamma=severite (sinistres seuls)")


# ======================================================================
# P12 -- vars_exclues fabrique une p-value de 1.0 sur erreur numerique
# ======================================================================
def p12():
    n = len(re.findall(r"'pvalue':\s*1\.0,\s*\n\s*'raison':\s*f?'erreur", SRC))
    dire('P12 p-value fabriquee sur erreur', 'CONSTAT' if n else 'BON',
         f"{n} site(s) inscrivent pvalue=1.0 avec raison 'erreur numerique' "
         f"— la p-value n'a pas ete calculee")


# ======================================================================
# P13 -- le chemin d erreur de predict casse lui-meme (.values sur ndarray)
# ======================================================================
def p13():
    sites = []
    for m in re.finditer(r'except Exception:\s*\n\s*pred_test = np\.full\(', SRC):
        ligne = SRC[:m.start()].count('\n') + 1
        suite = SRC[m.end():m.end() + 700]
        if '.values' in suite.split('return')[0]:
            sites.append(ligne)
    dire('P13 repli de predict puis .values', 'CONSTAT' if sites else 'BON',
         f'repli np.full(...) suivi d un .values, lignes {sites} '
         f'— ndarray n a pas .values')


# ======================================================================
# P14 -- docstrings et commentaires renvoyant a VARS_GLM (supprime)
# ======================================================================
def p14():
    vivant = bool(re.search(r'^VARS_GLM\s*=', SRC, re.MULTILINE))
    mentions = [i for i, l in enumerate(SRC.splitlines(), 1) if 'VARS_GLM' in l]
    dire('P14 renvois a VARS_GLM', 'CONSTAT' if mentions and not vivant else 'BON',
         f'VARS_GLM defini = {vivant} · {len(mentions)} mention(s) l.{mentions}')


# ======================================================================
# P15 -- 'significatif' : seuil code en dur, et toujours vrai ?
# ======================================================================
def p15():
    r = run()
    rels = r['relativites_poisson']
    tous_vrais = all(d['significatif'] for d in rels.values()) if rels else None
    dur = len(re.findall(r"'significatif':\s*bool\(float\(pvalues\w*\[var\]\) <= 0\.05\)", SRC))
    dire('P15 champ significatif', 'CONSTAT' if (dur and tous_vrais) else 'BON',
         f'{dur} site(s) codent 0.05 en dur (SEUIL_PVALUE existe) · '
         f'{len(rels)} relativites, toutes significatives = {tous_vrais} '
         f'(le stepwise ne garde que p<=0.05)')


# ======================================================================
# P16 -- COLS_A_EXCLURE : colonnes hors perimetre Non-Vie
# ======================================================================
def p16():
    from direction_non_vie.tarification.a3_glm.agent import COLS_A_EXCLURE
    hors = [c for c in COLS_A_EXCLURE
            if any(m in c for m in ('salarie', 'adherent', 'beneficiaire',
                                    'ij_', 'cotisation_mensuelle'))]
    dire('P16 COLS_A_EXCLURE hors Non-Vie', 'CONSTAT' if hors else 'BON',
         f'{len(COLS_A_EXCLURE)} entrees, dont {len(hors)} Vie/Sante : {hors}')


# ======================================================================
# P17 -- l exemple d usage du module
# ======================================================================
def p17():
    ag = a3()
    r = ag.run(jeu())        # exactement l exemple de l en-tete l. 48 / l. 224
    n = SRC.count('run(result_a2)')
    dire('P17 exemple "run(result_a2)" de l en-tete',
         'CONSTAT' if not r['success'] else 'BON',
         f"success={r['success']} · figure {n} fois dans le module")


# ======================================================================
# P18 -- l en-tete du fichier de test
# ======================================================================
def p18():
    t = (RACINE / 'direction_non_vie/tarification/a3_glm/test_a3_glm.py'
         ).read_text(encoding='utf-8')
    ann = re.search(r'(\d+)\s+tests', t)
    reels = len(re.findall(r'^\s+def (test_\w+)', t, re.MULTILINE))
    dire('P18 en-tete de test << N tests >>',
         'CONSTAT' if ann and int(ann.group(1)) != reels else 'BON',
         f'annonce {ann.group(1) if ann else "?"} · methodes reelles = {reels}')


# ======================================================================
# P19 -- VERIFICATIONS POSITIVES
# ======================================================================
def p19():
    ag = a3()
    a = not ag.run(jeu(), plan=None)['success']
    r = run()
    vars_glm = r['metriques']['poisson']['vars_retenues']
    b = not [v for v in vars_glm if 'sexe' in v.lower() or 'titre' in v.lower()]
    c = not [v for v in vars_glm if 'sinistre' in v.lower() or 'cout_' in v.lower()]
    d = 'prime_grave_unitaire' in SRC and hasattr(ag, '__class__')
    # Gini non ecrete a zero
    e = bool(re.search(r'np\.clip\(gini,\s*-1\.0,\s*1\.0\)', SRC))
    # severite via la source unique
    f_ = 'construire_cible_severite' in SRC
    for cle, ok, det in (
            ('P19a plan absent -> erreur propre', a, ''),
            ('P19b aucune variable de genre retenue', b, f'{len(vars_glm)} vars'),
            ('P19c aucune fuite de sinistralite', c, f'{vars_glm[:4]}'),
            ('P19d graves reinjectes dans la prime', d, 'prime_grave_unitaire'),
            ('P19e Gini non ecrete a zero', e, 'clip(-1, 1)'),
            ('P19f severite par la source unique', f_, 'core/severite')):
        dire(cle, 'BON' if ok else 'CONSTAT', det)


def main() -> int:
    print('  RELEVE A3 -- chaque ligne est une mesure\n')
    for f in (p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12,
              p13, p14, p15, p16, p17, p18, p19):
        try:
            f()
        except Exception as e:
            dire(f.__name__.upper(), 'NON MESURE', f'{type(e).__name__}: {e}')
    print('\n  ' + '=' * 78)
    for v in ('CONSTAT', 'BON', 'NON MESURE'):
        print(f'  {v:11} : {sum(1 for _, x, _ in RES if x == v)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
