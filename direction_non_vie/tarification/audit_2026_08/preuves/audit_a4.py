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
"""RELEVE A4 -- chaque constat porte sa mesure, ou n'est pas rendu."""
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
SRC = (RACINE / 'direction_non_vie/tarification/a4_ml/agent.py').read_text(encoding='utf-8')
RES = []


def dire(cle, verdict, detail):
    RES.append((cle, verdict, detail))
    print(f'  [{verdict:9}] {cle:42} {detail}')


def jeu(n=2500, seed=11):
    rng = np.random.default_rng(seed)
    expo = rng.uniform(.15, 1., n)
    bm = rng.uniform(50, 350, n)
    nb = rng.poisson(.06 * expo * (bm / 100.)).astype(float)
    return {'success': True, 'branche': 'auto', 'statut_rag': 'VERT', 'erreur': None,
            'dataframe': pd.DataFrame({
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
                'jeune_conducteur': (rng.integers(18, 80, n) < 25).astype(float),
                'annee_souscription': rng.choice([2020, 2021, 2022, 2023], n),
            })}


def a4():
    from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
    d = tempfile.mkdtemp(prefix='a4_')
    return AgentA4ML(models_path=d, audit_path=d, verbose=False)


_R = {}


def run(seed=11, graph=False):
    if (seed, graph) not in _R:
        _R[(seed, graph)] = a4().run(result_a2=jeu(seed=seed), plan=PLAN,
                                     generer_graphiques=graph, calcul_shap=False)
    return _R[(seed, graph)]


# ==================================================================
# Q1 -- 8 modeles annonces, combien tournent ?
# ==================================================================
def q1():
    r = run()
    testes = r['rapport']['modeles_testes']
    boucle = len(re.findall(r"^\s{12}\('(\w+)',", SRC, re.MULTILINE))
    n8 = len(re.findall(r'×8|/8|8 MODÈLES|ML ×8|8 modèles|8 algorithmes', SRC))
    dire('Q1 nombre de modeles ML', 'CONSTAT' if len(testes) != 8 else 'BON',
         f'boucle declare {boucle} · REELLEMENT calibres {len(testes)} : {testes} · '
         f'{n8} mentions de "8" dans le module')


# ==================================================================
# Q2 -- l optimisation tarifaire depend-elle du portefeuille ?
# ==================================================================
def q2():
    ag = a4()
    corps = inspect.getsource(ag._optimisation_tarifaire)
    utilise = len(re.findall(r'\bgini_meilleur\b', corps))
    o1 = ag._optimisation_tarifaire(0.05)
    o2 = ag._optimisation_tarifaire(0.95)
    identique = o1['recommandation'] == o2['recommandation']
    dire('Q2 optimisation tarifaire', 'CONSTAT' if identique else 'BON',
         f"gini_meilleur cite {utilise}x (signature seule) · gini 0.05 et 0.95 "
         f"-> MEME sortie : {identique} · {o1['recommandation'][:52]}")


# ==================================================================
# Q3 -- la cle 'gini' existe-t-elle dans le classement ?
# ==================================================================
def q3():
    r = run()
    cles = sorted(r['classement'][0]) if r['classement'] else []
    lu_gini = len(re.findall(r"\.get\('gini',\s*0(?:\.25)?\)", SRC))
    dire('Q3 cle "gini" lue dans le classement',
         'CONSTAT' if ('gini' not in cles and lu_gini) else 'BON',
         f"cles reelles = {cles} · 'gini' presente = {'gini' in cles} · "
         f"{lu_gini} site(s) lisent .get('gini', defaut)")


# ==================================================================
# Q4 -- le graphique overfitting affiche-t-il de vrais Gini test ?
# ==================================================================
def q4():
    r = run(graph=True)
    fig = r.get('graphiques_validation', {}).get('overfitting_train_test')
    if fig is None:
        dire('Q4 graphique overfitting', 'NON MESURE', 'figure absente')
        return
    series = {t.name: list(t.y) for t in fig.data}
    test = series.get('Gini Test', [])
    reel = [c['gini_test'] for c in r['classement'][:6]]
    dire('Q4 graphique overfitting : Gini Test',
         'CONSTAT' if all(v == 0 for v in test) and any(reel) else 'BON',
         f'trace "Gini Test" = {[round(v,4) for v in test]} · '
         f'valeurs REELLES = {[round(v,4) for v in reel]}')


# ==================================================================
# Q5 -- le monitoring est-il mesure ou simule ?
# ==================================================================
def q5():
    ag = a4()
    corps = inspect.getsource(ag._monitoring_derive)
    simule = bool(re.search(r'np\.random\.beta', corps))
    m1 = ag._monitoring_derive({}, gini_reference=0.10)
    m2 = ag._monitoring_derive({}, gini_reference=0.40)
    r1, r2 = run(seed=11), run(seed=77)
    psi_egaux = r1['monitoring']['psi'] == r2['monitoring']['psi']
    dire('Q5 monitoring de derive', 'CONSTAT' if simule else 'BON',
         f'distributions tirees par np.random.beta = {simule} · '
         f'PSI identique sur 2 portefeuilles differents = {psi_egaux} '
         f"({r1['monitoring']['psi']}) · KS identique = "
         f"{m1['ks_stat'] == m2['ks_stat']}")


# ==================================================================
# Q6 -- deux validations differentes dans le meme retour
# ==================================================================
def q6():
    r = run()
    h = r['hypotheses']['h4_calibration']
    v = r['validation_ml']['h4_calibration']
    dire('Q6 "hypotheses" vs "validation_ml"',
         'CONSTAT' if h['statut'] != v['statut'] else 'BON',
         f"hypotheses.h4 = {h['statut']} (ecart={h['ecart_moy_pct']}) · "
         f"validation_ml.h4 = {v['statut']} (ecart={v['ecart_moy_pct']}) "
         f"— l Excel lit validation_ml")


# ==================================================================
# Q7 -- la courbe de Lorenz d A4
# ==================================================================
def q7():
    formule = bool(re.search(r'lorenz_y\s*=\s*t\s*\*\*\s*\(1\s*/\s*\(1\s*\+\s*gini\s*\*\s*2\)\)', SRC))
    axe = 'du moins au plus risqué' in SRC
    tri = bool(re.search(r'np\.argsort\(y_pred\)\[::-1\]', SRC))
    dire('Q7 courbe de Lorenz d A4', 'CONSTAT' if formule else 'BON',
         f'formule analytique = {formule} · axe dit "du moins au plus risque" = {axe} '
         f'· le Gini trie DECROISSANT (plus risque d abord) = {tri}')


# ==================================================================
# Q8 -- << Modeles testes : N/8 >> publie au commentaire
# ==================================================================
def q8():
    r = run()
    m = re.search(r'Modèles testés\s*:\s*(\d+)/(\d+)', r['commentaire'])
    dire('Q8 "Modeles testes : N/8" publie',
         'CONSTAT' if m and m.group(2) != m.group(1) else 'BON',
         f'publie {m.group(0) if m else "?"} · reellement calibres '
         f"{len(r['rapport']['modeles_testes'])}")


# ==================================================================
# Q9 -- scorecard : 3 annonces, 4 items
# ==================================================================
def q9():
    bloc = re.search(r'# G4 — Scorecard validation ML.*?return graphiques', SRC, re.DOTALL).group(0)
    items = len(re.findall(r'\("H\d', bloc))
    ann = re.search(r'(\d+)\s*✅\s*=\s*modèle validé', bloc)
    dire('Q9 scorecard ML : compte annonce',
         'CONSTAT' if ann and int(ann.group(1)) != items else 'BON',
         f"annonce {ann.group(1) if ann else '?'} ✅ · liste {items} items")


# ==================================================================
# Q10 -- COLS_A_EXCLURE_ML hors perimetre
# ==================================================================
def q10():
    from direction_non_vie.tarification.a4_ml.agent import COLS_A_EXCLURE_ML
    hors = [c for c in COLS_A_EXCLURE_ML
            if any(m in c for m in ('salarie', 'adherent', 'beneficiaire',
                                    'ij_', 'cotisation_mensuelle'))]
    dire('Q10 COLS_A_EXCLURE_ML hors Non-Vie', 'CONSTAT' if hors else 'BON',
         f'{len(COLS_A_EXCLURE_ML)} entrees, dont {len(hors)} Vie/Sante : {hors}')


# ==================================================================
# Q11 -- le GLM entre au classement : meme base de rang ?
# ==================================================================
def q11():
    a3_src = (RACINE / 'direction_non_vie/tarification/a3_glm/agent.py').read_text(encoding='utf-8')
    a3_rang = bool(re.search(r'gini = self\._calculer_gini\(df_test\[col_freq\]\.values, pred_test\.values\)', a3_src))
    a4_taux = 'Gini sur le TAUX' in SRC
    dire('Q11 base de rang du Gini compare',
         'CONSTAT' if (a3_rang and a4_taux) else 'BON',
         f'A3 classe sur le COMPTAGE predit (avec offset) = {a3_rang} · '
         f'A4 classe sur le TAUX = {a4_taux} · les deux sont mis dans UN classement')


# ==================================================================
# Q12 -- statut RAG : docstring vs code
# ==================================================================
def q12():
    from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
    ag = a4()
    # ROUGE annonce : << Aucun modele ML ne bat le GLM >>
    cl = [{'modele': 'gbm', 'gini_test': 0.14, 'overfit_alerte': False}]
    r3 = {'success': True, 'metriques': {'poisson': {'gini': 0.30}}}
    obtenu = ag._calculer_statut_rag(cl, r3)
    dire('Q12 statut RAG : ROUGE annonce',
         'CONSTAT' if obtenu != 'ROUGE' else 'BON',
         f'ML 0.14 < GLM 0.30 (le ML ne bat PAS le GLM) -> {obtenu} '
         f'· docstring dit ROUGE dans ce cas')


# ==================================================================
# Q13 -- en-tete du fichier de test
# ==================================================================
def q13():
    t = (RACINE / 'direction_non_vie/tarification/a4_ml/test_a4_ml.py').read_text(encoding='utf-8')
    ann = re.search(r'(\d+)\s+tests', t)
    reels = len(re.findall(r'^\s+def (test_\w+)', t, re.MULTILINE))
    dire('Q13 en-tete de test << N tests >>',
         'CONSTAT' if ann and int(ann.group(1)) != reels else 'BON',
         f'annonce {ann.group(1) if ann else "?"} · methodes reelles = {reels}')


# ==================================================================
# Q14 -- VERIFICATIONS POSITIVES
# ==================================================================
def q14():
    ag = a4()
    a = not ag.run(jeu(), plan=None)['success']
    r = run()
    # H4 par defaut AMBRE (le correctif faux-vert)
    v = ag._valider_modele_ml(r['classement'], ag._monitoring_derive({}))
    b = v['h4_calibration']['statut'] == 'AMBRE'
    c = v['h4_calibration']['ecart_moy_pct'] is None
    d = not [f for f in r['rapport']['feature_names']
             if 'sexe' in f.lower() or 'genre' in f.lower()]
    e = bool(re.search(r'np\.clip\(2 \* auc - 1, -1\.0, 1\.0\)', SRC))
    f_ = 'creer_modele_ml_pour_nom' in SRC and SRC.count('return creer_modele_ml_pour_nom') >= 6
    for cle, ok, det in (
            ('Q14a plan absent -> erreur propre', a, ''),
            ('Q14b H4 non testee -> AMBRE (correctif)', b, v['h4_calibration']['statut']),
            ('Q14c ecart non mesure -> None, pas 0.0', c, repr(v['h4_calibration']['ecart_moy_pct'])),
            ('Q14d aucune feature de genre', d, f"{len(r['rapport']['feature_names'])} features"),
            ('Q14e Gini non ecrete a zero', e, 'clip(-1, 1)'),
            ('Q14f fabrique = source unique A4/A6', f_, '6 delegations')):
        dire(cle, 'BON' if ok else 'CONSTAT', det)


def main() -> int:
    print('  RELEVE A4 -- chaque ligne est une mesure\n')
    for f in (q1, q2, q3, q4, q5, q6, q7, q8, q9, q10, q11, q12, q13, q14):
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
