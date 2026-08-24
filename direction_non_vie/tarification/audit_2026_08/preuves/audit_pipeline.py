# ruff: noqa
"""AUDIT DE pipeline_tarifaire.py -- LE CHEMIN QUI CALCULE LE PRIX.

Posture : ce code a ete construit avec soin. On part de l'hypothese qu'il est
BON et on prouve le contraire. Rien ne se signale sans mesure reproductible,
et ce qui est classe BON est mesure autant que ce qui est signale.
"""
import io
import os
import re
import sys
import warnings

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))
sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire
import direction_non_vie.tarification.pipeline_tarifaire as P

RACINE = r'C:\Users\selse\actuaria-app'
SRC = io.open(os.path.join(RACINE, 'direction_non_vie/tarification/pipeline_tarifaire.py'),
              encoding='utf-8').read()
PLAN = PlanTarifaire.depuis_yaml(os.path.join(RACINE, 'plans', 'auto.yaml'))

RES = []


def dire(nom, verdict, detail):
    RES.append((verdict, nom))
    print(f"  [{verdict:9s}] {nom:44s} {detail}")


def portefeuille(n=3000, seed=1):
    """Le portefeuille est construit DEPUIS LE PLAN : une fixture ecrite a la
    main se perimerait au premier facteur ajoute, et c est exactement ce qui
    vient de m arriver."""
    rng = np.random.default_rng(seed)
    expo = rng.uniform(0.2, 1.0, n)
    bm = rng.uniform(50, 350, n)
    nb = rng.poisson(0.10 * expo * (bm / 200.0), n).astype(float)
    df = pd.DataFrame({
        'id_contrat': np.arange(n), 'exposition': expo,
        'nb_sinistres': nb,
        'cout_total_sinistres': np.where(nb > 0, rng.gamma(2, 400, n), 0.0),
        'bonus_malus': bm,
    })
    for f in PLAN.facteurs:
        if f.nom in df.columns:
            continue
        if f.type == 'continu':
            df[f.nom] = rng.uniform(1, 100, n)
        elif f.type == 'binaire':
            df[f.nom] = rng.integers(0, 2, n).astype(float)
        else:
            df[f.nom] = rng.choice([str(m) for m in f.modalites], n)
    for col in PLAN.colonnes_attendues():
        if col not in df.columns:
            df[col] = rng.uniform(1, 100, n)
    return df


print("=" * 78)
print("  AUDIT pipeline_tarifaire.py -- 343 lignes")
print("=" * 78)

DF = portefeuille()
TARIF = P.pipeline_complet(DF, PLAN)

# ── M1 : tarifer() reproduit-il predire_portefeuille() ? (INV-7 annonce) ─────
pred = TARIF.predire_portefeuille(DF)
ecarts = []
for i in range(6):
    lig = DF.iloc[i].to_dict()
    expo_i = float(lig.pop('exposition'))
    r = TARIF.tarifer(lig, exposition=expo_i)
    if r['success']:
        ecarts.append(abs(r['prime_pure'] - float(pred['prime_pure'].iloc[i])))
m1 = max(ecarts) if ecarts else None
dire('M1 tarifer == predire_portefeuille', 'BON' if (m1 is not None and m1 < 1e-2) else 'CONSTAT',
     f"ecart max sur 6 contrats = {m1:.6f}")
dire('M1b la precision annoncee (1e-6) est-elle verifiable ?',
     'CONSTAT' if m1 > 1e-6 else 'BON',
     f"tarifer() ARRONDIT prime_pure a 2 decimales (round(.., 2)) : la "
     f"coincidence a 1e-6 annoncee l.123 n'est PAS observable sur la sortie "
     f"publiee -- l'ecart mesure {m1:.6f} est de l'arrondi, pas une divergence")

# ── M2 : le taux de frequence est-il PAR UNITE d'exposition ? ────────────────
f = pred['frequence_annuelle'].to_numpy()
e = pred['exposition'].to_numpy()
obs = DF['nb_sinistres'].to_numpy()
r_sans = obs.sum() / f.sum()
r_avec = obs.sum() / (f * e).sum()
dire('M2 frequence par unite d exposition', 'BON' if abs(r_avec - 1) < abs(r_sans - 1) else 'CONSTAT',
     f"Sigma obs / Sigma freq = {r_sans:.4f} | / Sigma (freq x expo) = {r_avec:.4f}")

# ── M3 : le coefficient d equilibre ramene-t-il a +/- 1 % ? ──────────────────
somme = float(TARIF.predire_portefeuille(DF)['prime_pure'].sum())
charge = float(DF['cout_total_sinistres'].sum())
dire('M3 equilibre technique a +/- 1 %', 'BON' if abs(somme / charge - 1) < 0.01 else 'CONSTAT',
     f"Sigma prime / Sigma charge = {somme/charge:.4f}  (k = {TARIF.coefficient_equilibre:.4f})")

# ── M4 : le plan declare-t-il les chargements, comme le commentaire l annonce ?
declarables = hasattr(PLAN, 'chargements')
dire('M4 chargements "declarables dans le plan"', 'CONSTAT' if not declarables else 'BON',
     f"PlanTarifaire porte un champ `chargements` : {declarables} -- "
     f"le commentaire l.35 dit « Declarables dans le plan (etape 6) »")

# ── M5 : le commentaire enumere 3 taux de taxe, le code en applique 1 ────────
taux_cites = re.findall(r'(\d+)\s*%', SRC[SRC.find('Taxes :'):SRC.find('Taxes :') + 80])
applique = P.CHARGEMENTS_DEFAUT['taxes']
dire('M5 "auto 33 %, MRH 30 %, RC 9 %"', 'CONSTAT' if len(taux_cites) > 1 else 'BON',
     f"taux cites au commentaire = {taux_cites} | applique en dur = {applique} "
     f"pour TOUTE LoB")

# ── M6 : gini_lorenz, "UNE SEULE definition" ? ───────────────────────────────
autres = []
for chemin, sym in (('direction_non_vie/tarification/a6_comparaison/agent.py', '_gini_lorenz'),
                    ('direction_non_vie/tarification/a3_glm/agent.py', '_calculer_gini'),
                    ('direction_non_vie/tarification/a4_ml/agent.py', '_calculer_gini'),
                    ('direction_non_vie/tarification/a5_deep_learning/agent.py', '_calculer_gini')):
    s = io.open(os.path.join(RACINE, chemin), encoding='utf-8').read()
    if re.search(rf'def {sym}\b', s):
        autres.append(f"{os.path.basename(os.path.dirname(chemin))}::{sym}")
dire('M6 "UNE SEULE definition" du Gini', 'CONSTAT' if autres else 'BON',
     f"autres definitions trouvees : {autres}")

# ── M7 : le seuil INV-6 (< 0,40) est-il APPLIQUE quelque part ? ──────────────
applique_ou = []
for f_ in ('direction_non_vie/tarification/test_plan_invariants.py',
           'direction_non_vie/tarification/pipeline_tarifaire.py'):
    s = io.open(os.path.join(RACINE, f_), encoding='utf-8').read()
    if re.search(r'ecart_relatif.{0,40}0[.,]4|0[.,]4.{0,40}ecart_relatif', s):
        applique_ou.append(os.path.basename(f_))
dire('M7 le seuil INV-6 annonce est applique', 'BON' if applique_ou else 'CONSTAT',
     f"seuil 0,40 applique dans : {applique_ou or 'NULLE PART'}")

# ── M8 : une exposition ILLISIBLE -- que devient-elle ? ──────────────────────
d2 = DF.copy()
d2['exposition'] = d2['exposition'].astype(object)
d2.loc[d2.index[:5], 'exposition'] = 'illisible'
try:
    t2 = P.pipeline_complet(d2, PLAN)
    p2 = t2.predire_portefeuille(d2)
    nan_prime = int(p2['prime_pure'].isna().sum())
    dire('M8 exposition illisible', 'CONSTAT' if nan_prime else 'BON',
         f"5 valeurs non numeriques -> {nan_prime} primes NaN, "
         f"aucune erreur levee, k = {t2.coefficient_equilibre}")
except Exception as ex:
    dire('M8 exposition illisible', 'BON',
         f"arret loud : {type(ex).__name__} : {str(ex)[:60]}")

# ── M9 : le cout NaN est protege (fillna) -- l exposition et la frequence ? ──
prot = {
    'cout_total': 'fillna' in SRC[SRC.find('cout_total ='):SRC.find('cout_total =') + 120],
    'exposition': 'fillna' in SRC[SRC.find('expo = pd.to_numeric'):SRC.find('expo = pd.to_numeric') + 120],
    'frequence': 'fillna' in SRC[SRC.find('y_freq = pd.to_numeric'):SRC.find('y_freq = pd.to_numeric') + 120],
}
dire('M9 asymetrie de protection NaN', 'CONSTAT' if not all(prot.values()) else 'BON',
     f"fillna present : {prot}")

# ── M10 : deux horodatages, deux fuseaux ? ──────────────────────────────────
utc = 'datetime.now(timezone.utc)' in SRC
local = re.search(r'horodatage=datetime\.now\(\)', SRC) is not None
dire('M10 deux horodatages, deux fuseaux', 'CONSTAT' if (utc and local) else 'BON',
     f"tarifer() en UTC = {utc} | controler_qualite en LOCAL = {local}")

# ── M11 : grille() -- "relativites exportables" ne porte que la frequence ────
g = TARIF.grille('bonus_malus')
dire('M11 grille() ne porte que la frequence', 'CONSTAT' if 'relativite_cout' not in g.columns else 'BON',
     f"colonnes = {list(g.columns)} -- la prime depend AUSSI du cout moyen")

# ── M12 : tarifer() capture-t-il TOUTE exception ? ───────────────────────────
r_bug = TARIF.tarifer({'age': 'pas un nombre', 'bonus_malus': 200})
dire('M12 tarifer capture tout', 'CONSTAT' if not r_bug['success'] else 'BON',
     f"contrat aberrant -> success={r_bug['success']}, "
     f"erreur='{str(r_bug.get('erreur'))[:50]}' (jamais levee)")

# ── M13 : le filtre GENRE est-il applique par le chemin declaratif ? ─────────
d3 = DF.copy()
d3['sexe'] = np.random.default_rng(0).choice([0, 1], len(d3))
t3 = P.pipeline_complet(d3, PLAN)
dire('M13 filtre genre (CJUE C-236/09)', 'BON' if 'sexe' not in t3.features else 'CONSTAT',
     f"'sexe' dans les features ajustees : {'sexe' in t3.features}")

# ── M14 : la couche qualite BLOQUE-t-elle vraiment ? ────────────────────────
d4 = DF.copy()
d4.loc[d4.index[:400], 'exposition'] = -1.0        # 13 % de lignes impossibles
try:
    P.pipeline_complet(d4, PLAN)
    dire('M14 blocage qualite a 5 %', 'CONSTAT', "13 % d expositions negatives -> AUCUN blocage")
except P.QualiteBloquante:
    dire('M14 blocage qualite a 5 %', 'BON', "13 % d expositions negatives -> QualiteBloquante levee")

# ── M15 : combien de fenetres le walk-forward produit-il reellement ? ────────
st = P.evaluer_stabilite_temporelle(DF.iloc[:1200], PLAN, n_fenetres=4)
dire('M15 n_fenetres demandees vs produites', 'BON' if len(st['ginis_fenetres']) == 4 else 'CONSTAT',
     f"demandees=4, produites={len(st['ginis_fenetres'])}, "
     f"ecart_relatif={st['ecart_relatif']:.4f}")

# ── M16 : aucun cout observe -- le GLM degenere rend-il quelque chose ? ──────
d5 = DF.copy()
d5['cout_total_sinistres'] = 0.0
d5['nb_sinistres'] = 0.0
try:
    t5 = P.pipeline_complet(d5, PLAN, equilibrer=False)
    p5 = t5.predire_portefeuille(d5)
    dire('M16 portefeuille sans aucun sinistre', 'BON',
         f"cout moyen predit = {float(p5['cout_moyen'].iloc[0]):.4f}, "
         f"prime_pure = {float(p5['prime_pure'].iloc[0]):.4f}")
except Exception as ex:
    dire('M16 portefeuille sans aucun sinistre', 'CONSTAT',
         f"{type(ex).__name__} : {str(ex)[:70]}")

# ── M17 : la formule de prime commerciale -- ou s applique la marge ? ────────
ct = DF.iloc[0].to_dict()
expo0 = float(ct.pop('exposition'))
rt = TARIF.tarifer(ct, exposition=expo0)
ch = P.CHARGEMENTS_DEFAUT
attendu = rt['prime_pure'] * (1 + ch['frais']) * (1 + ch['marge']) / (1 - ch['commission'])
dire('M17 formule de prime commerciale', 'BON' if abs(rt['prime_commerciale_ht'] - attendu) < 0.02 else 'CONSTAT',
     f"pc={rt['prime_commerciale_ht']} vs formule={attendu:.2f} "
     f"(marge appliquee sur la prime pure CHARGEE des frais)")

# ── M18 : le tarif est-il reproductible d un ajustement a l autre ? ──────────
t6 = P.pipeline_complet(DF, PLAN)
p6 = t6.predire_portefeuille(DF)['prime_pure'].to_numpy()
p0 = pred['prime_pure'].to_numpy()
dire('M18 reproductibilite de l ajustement', 'BON' if np.allclose(p0, p6) else 'CONSTAT',
     f"ecart max entre deux ajustements identiques = {float(np.max(np.abs(p0 - p6))):.2e}")

print()
print(f"  CONSTAT : {sum(1 for v, _ in RES if v == 'CONSTAT')}")
print(f"  BON     : {sum(1 for v, _ in RES if v == 'BON')}")
