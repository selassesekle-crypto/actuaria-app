# ruff: noqa
"""RELEVE core/conformite_reglementaire.py -- LES MECANISMES ANNONCES.

Chaque garde-fou annonce quelque chose. On plante la violation et on regarde.
"""
import logging
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')
if __name__ == '__main__':
    logging.disable(logging.CRITICAL)   # les WARNING sont mesures separement (M11)

import numpy as np
import pandas as pd

import core.conformite_reglementaire as C

RACINE = r'C:\Users\selse\actuaria-app'


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


# ══════════════════════════════════════════════════════════════════════════════
titre("M1 -- LE FILTRE GENRE (CJUE C-236/09) : casse, langue, one-hot, proxys")
# ══════════════════════════════════════════════════════════════════════════════
CAS_GENRE = [
    'sexe', 'Sexe', 'SEXE', 'sexe_enc', 'sexe_M', 'sexe_F',
    'genre', 'genre_H', 'gender', 'gender_enc', 'sex',
    'civilite', 'civilite_Mme', 'titre', 'titre_enc', 'titre_civil',
    'prenom', 'madame', 'monsieur', 'is_male', 'is_female',
]
restants = C.filtrer_genre(list(CAS_GENRE), contexte='mesure M1')
print(f"  {len(CAS_GENRE)} noms genres/proxys presentes -> {len(restants)} survivant(s)")
if restants:
    print(f"  [CONSTAT] PASSENT LE FILTRE : {restants}")
else:
    print("  [BON    ] aucun ne passe.")

# et le contraire : un facteur legitime est-il detruit par un stem de genre ?
LEGITIMES = sorted(C.FACTEURS_TARIFAIRES_AUTORISES)
faux_pos = [f for f in LEGITIMES if C._est_variable_genre(f)]
print(f"  facteurs declares LEGITIMES detruits par le filtre genre : "
      f"{faux_pos if faux_pos else 'aucun'}  ({len(LEGITIMES)} testes)")


# ══════════════════════════════════════════════════════════════════════════════
titre("M2 -- LE FILTRE ANTI-FUITE PAR LE NOM")
# ══════════════════════════════════════════════════════════════════════════════
CAS_FUITE = [
    'prime_pure', 'log_prime_pure', 'prime_pure_obs', 'prime_commerciale',
    'cout_total_sinistres', 'MONTANT_SINISTRES', 'nb_sinistres',
    'total_sinistres_sante', 'cout_hospitalisation', 'lambda_freq',
    'charge_annuelle_eur', 'part_hospit',
]
restants = C.filtrer_famille_cible(list(CAS_FUITE), contexte='mesure M2')
print(f"  {len(CAS_FUITE)} grandeurs de sinistralite OBSERVEE -> "
      f"{len(restants)} survivant(s)")
print(f"  {'[CONSTAT] PASSENT : ' + str(restants) if restants else '[BON    ] aucune ne passe.'}")

# les 11 noms que le module dit lui-meme NON captures par la liste noire (l.328)
NON_CAPTURES_ANNONCES = [
    'loss_ratio', 'taux_S_sur_P', 'ratio_sp', 'frequence_observee',
    'severite_observee', 'charge_totale', 'montant_regle', 'indemnite_versee',
    'provision_dossier', 'burning_cost', 'sinistralite_n',
]
passent = C.filtrer_famille_cible(list(NON_CAPTURES_ANNONCES))
print(f"  les 11 fuites que le module annonce NON captures par le nom : "
      f"{len(passent)} passent encore")
print(f"    -> {sorted(passent)}")
print("    (le module l'ecrit lui-meme l.328 ; c'est la raison d'etre de la")
print("     liste blanche et du controle par l'effet)")


# ══════════════════════════════════════════════════════════════════════════════
titre("M3 -- L'ANTERIORITE : les 6 variables que B5 detruisait survivent-elles ?")
# ══════════════════════════════════════════════════════════════════════════════
B5 = ['cout_total_sinistres_anterieurs', 'charge_sinistres_n1',
      'nb_sinistres_passes', 'historique_sinistres_3ans',
      'montant_sinistres_anterieurs', 'sinistres_anterieurs_5ans']
DECLAREES = ['antecedents_sinistres_n1', 'nb_sinistres_anterieurs',
             'antecedents_sinistres_3ans']
for nom, lot in (('les 6 de B5', B5), ('les 3 declarees', DECLAREES)):
    survivants = C.filtrer_famille_cible(list(lot))
    etat = 'BON    ' if len(survivants) == len(lot) else 'CONSTAT'
    print(f"  [{etat}] {nom:18s} : {len(survivants)}/{len(lot)} survivent "
          f"au filtre anti-fuite")
    if len(survivants) != len(lot):
        print(f"            detruites : {sorted(set(lot) - set(survivants))}")

# et la liste blanche, elle ? (B5 etait une destruction PAR LA LISTE BLANCHE)
for nom, lot in (('les 6 de B5', B5), ('les 3 declarees', DECLAREES)):
    ok = [c for c in lot if C.est_facteur_autorise(c)]
    etat = 'BON    ' if len(ok) == len(lot) else 'CONSTAT'
    print(f"  [{etat}] {nom:18s} : {len(ok)}/{len(lot)} passent la LISTE BLANCHE")
    if len(ok) != len(lot):
        print(f"            ecartees  : {sorted(set(lot) - set(ok))}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M4 -- B6 : 'garantie_montant_regle' passe-t-il encore la liste blanche ?")
# ══════════════════════════════════════════════════════════════════════════════
for c in ('garantie_montant_regle', 'carburant_diesel', 'type_logement_maison',
          'statut_occupation_locataire', 'inter_age_bonus_malus',
          'inter_bonus_malus_antecedents_sinistres_n1', 'age_carre',
          'log_exposition', 'zone_geographique_enc'):
    print(f"    est_facteur_autorise({c!r:46s}) = {C.est_facteur_autorise(c)}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M5 -- MatriceX : instanciable ? modifiable ?")
# ══════════════════════════════════════════════════════════════════════════════
try:
    C.MatriceX(['age'], {}, 'forge directe')
    print("  [CONSTAT] MatriceX() instanciable SANS jeton")
except TypeError as e:
    print(f"  [BON    ] instanciation directe refusee : {str(e)[:56]}...")

try:
    C.MatriceX(['age'], {}, 'forge', _jeton=getattr(C.MatriceX, '_JETON', None))
    print("  [CONSTAT] MatriceX._JETON est encore expose sur la CLASSE")
except (TypeError, AttributeError) as e:
    print(f"  [BON    ] MatriceX._JETON n'existe plus sur la classe "
          f"({type(e).__name__})")

mx = C.construire_matrice_x(['age', 'bonus_malus', 'sexe'], contexte='M5')
print(f"  {mx!r}")
for geste, fn in (
        ("mx.features = (...)", lambda: setattr(mx, 'features', ('sexe',))),
        ("mx._features = (...)", lambda: setattr(mx, '_features', ('sexe',))),
        ("del mx._features", lambda: delattr(mx, '_features')),
        ("mx.features.append", lambda: mx.features.append('sexe')),
):
    try:
        fn()
        print(f"  [CONSTAT] {geste:24s} ACCEPTE")
    except (AttributeError, TypeError) as e:
        print(f"  [BON    ] {geste:24s} -> {type(e).__name__}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M6 -- LE CONTROLE PAR L'EFFET attrape-t-il un nom JAMAIS IMAGINE ?")
# ══════════════════════════════════════════════════════════════════════════════
rng = np.random.default_rng(7)
n = 4000
expo = rng.uniform(0.2, 1.0, n)
bm = rng.uniform(50, 350, n)
age = rng.uniform(18, 80, n)
nb = rng.poisson(0.10 * expo * (bm / 200.0), n).astype(float)
df = pd.DataFrame({
    'exposition': expo, 'bonus_malus': bm, 'age': age, 'nb_sinistres': nb,
    # la fuite, sous un nom qu'aucune liste ne contient
    'zorglub_machin': nb + rng.normal(0, 1e-6, n),
    'garantie_montant_regle': nb * 812.0 + rng.normal(0, 1e-3, n),
})
fuites = C.detecter_fuites_par_effet(df, list(df.columns), 'nb_sinistres')
print(f"  taux de sinistres = {nb.mean():.3f} /contrat  ({(nb == 0).mean():.0%} de zeros)")
for c in df.columns:
    if c == 'nb_sinistres':
        continue
    v = fuites.get(c)
    if v:
        print(f"  [ECARTEE] {c:24s} spearman={v['spearman']:.4f}  "
              f"gini_norm={v['gini_normalise']:.4f}")
    else:
        print(f"  [gardee ] {c:24s}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M7 -- LA CALIBRATION ANNONCEE : fuites ~1,00 / legitimes 0,03-0,10 ?")
# ══════════════════════════════════════════════════════════════════════════════
print("  Le module ecrit l.1074-1075 : « fuites : 1,00 / 0,99 / 1,00 ;")
print("  legitimes : 0,03 / 0,04 / 0,05 / 0,10 ». Mesure sur la meme structure :")
y = df['nb_sinistres'].astype(float)


def _gini_norm(x):
    yy = y.to_numpy(float)
    tr = getattr(np, 'trapezoid', None) or np.trapz

    def g(xa):
        o = np.argsort(-xa)
        yo = yy[o]
        t = yo.sum()
        if t <= 0:
            return 0.0
        return float(2.0 * tr(np.cumsum(yo) / t, np.arange(1, len(yo) + 1) / len(yo)) - 1.0)
    gp = g(yy)
    return abs(g(np.asarray(x, float)) / gp) if gp > 1e-9 else 0.0


for nom, x in (('FUITE zorglub_machin', df['zorglub_machin']),
               ('FUITE garantie_montant_regle', df['garantie_montant_regle']),
               ('legitime bonus_malus', df['bonus_malus']),
               ('legitime age', df['age']),
               ('legitime exposition', df['exposition'])):
    rho = abs(float(y.rank().corr(pd.Series(np.asarray(x, float)).rank())))
    print(f"    {nom:32s} spearman={rho:.4f}   gini_normalise={_gini_norm(x):.4f}")
print(f"  -> le seuil unique est {C.SEUIL_CORRELATION_FUITE} sur max(spearman, gini_norm)")


# ══════════════════════════════════════════════════════════════════════════════
titre("M8 -- LE PLAN AUTORISE-T-IL A DISPENSER ? (INV-3 / INV-4)")
# ══════════════════════════════════════════════════════════════════════════════
from core.plan_tarifaire import PlanTarifaire
PLAN = PlanTarifaire.depuis_yaml(os.path.join(RACINE, 'plans', 'auto.yaml'))


class PlanMenteur:
    """Un plan SIGNE qui declare le genre et la prime pure comme facteurs."""

    def colonnes_produites(self):
        return tuple(PLAN.colonnes_produites()) + ('sexe', 'prime_pure',
                                                   'civilite_Mme')

    def facteurs_anteriorite(self):
        return PLAN.facteurs_anteriorite()


cols = ['age', 'bonus_malus', 'sexe', 'prime_pure', 'civilite_Mme']
mx = C.construire_matrice_x(cols, contexte='M8', plan=PlanMenteur())
print(f"  le plan DECLARE sexe, civilite_Mme et prime_pure comme legitimes.")
print(f"  matrice X obtenue : {list(mx)}")
for c in ('sexe', 'civilite_Mme', 'prime_pure'):
    dans = c in list(mx)
    print(f"    {'[CONSTAT] ' if dans else '[BON    ] '}{c:14s} "
          f"{'DANS' if dans else 'hors'} la matrice X   "
          f"motif={mx.exclusions.get(c, '-')[:52]!r}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M9 -- LE GARDE-FOU N.4 SE DECLARE-T-IL NON EXECUTE ?")
# ══════════════════════════════════════════════════════════════════════════════
for lib, kw in (
        ("sans df ni cible", {}),
        ("avec df, sans cible", {'df': df}),
        ("sans df, avec cible", {'col_cible': 'nb_sinistres'}),
        ("df + cible", {'df': df, 'col_cible': 'nb_sinistres'}),
):
    m = C.construire_matrice_x(['age', 'bonus_malus'], contexte='M9', **kw)
    print(f"    {lib:22s} -> controle_effet_execute = {m.controle_effet_execute}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M10 -- LA JOURNALISATION EST-ELLE REELLE ? (traçabilite ACPR)")
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    logging.disable(logging.NOTSET)
import io as _io
flux = _io.StringIO()
h = logging.StreamHandler(flux)
h.setLevel(logging.WARNING)
lg = logging.getLogger('mesure.m10')
lg.addHandler(h)
lg.setLevel(logging.WARNING)
C.construire_matrice_x(['age', 'sexe', 'prime_pure', 'colonne_inconnue_xyz'],
                       contexte='M10', logger_agent=lg)
sortie = flux.getvalue()
for marque in ('C-236/09', 'data leakage', 'LISTE BLANCHE', "ANTI-FUITE PAR L'EFFET"):
    print(f"    {'[BON    ]' if marque in sortie else '[CONSTAT]'} "
          f"le log porte {marque!r} : {marque in sortie}")
if __name__ == '__main__':
    logging.disable(logging.CRITICAL)
print()
print(f"  {len(sortie.splitlines())} ligne(s) de WARNING emises.")
