# ruff: noqa
"""RELEVE core/conformite_reglementaire.py -- LES TROUS.

Ce que M3 et M10 ont ouvert, plus le soupcon central : B7 (l'anteriorite est le
critere, pas la correlation) a-t-il ete ferme pour les variables de TAILLE ?
"""
import io
import logging
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')
if __name__ == '__main__':
    logging.disable(logging.CRITICAL)

import numpy as np
import pandas as pd

import core.conformite_reglementaire as C


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


# ══════════════════════════════════════════════════════════════════════════════
titre("H1 -- LE GARDE-FOU N.4 SE DECLARE-T-IL EXECUTE QUAND IL NE FAIT RIEN ?")
# ══════════════════════════════════════════════════════════════════════════════
rng = np.random.default_rng(3)
n = 3000
expo = rng.uniform(0.2, 1.0, n)
nb = rng.poisson(0.12 * expo, n).astype(float)
df = pd.DataFrame({
    'exposition': expo, 'age': rng.uniform(18, 80, n),
    'bonus_malus': rng.uniform(50, 350, n), 'nb_sinistres': nb,
    'zorglub': nb + rng.normal(0, 1e-6, n),      # la fuite
    'cible_constante': np.ones(n),
})
COLS = ['age', 'bonus_malus', 'zorglub']
# 'zorglub' est DECLARE par l'actuaire comme facteur de son portefeuille : il
# passe donc la liste blanche. Le garde-fou n.4 est alors le SEUL a pouvoir
# l'ecarter -- c'est tout l'objet de la mesure.
SUPP = ['zorglub']

print("  Le module ecrit l.870 : « Un controle dont on ne verifie pas")
print("  l'execution n'est pas un controle. »  Trois appels :")
print()
# ⚠️ CETTE MESURE VIT SOUS LA GARDE `__main__`, et pas dans une fonction
# appelee au niveau module : elle bascule le journal global (NOTSET puis
# CRITICAL) pour capturer les WARNING, et la cacher dans un helper aurait
# satisfait le detecteur F5 SANS corriger le defaut -- le module aurait
# continue d'eteindre le journal a l'import. Un controle battu par la forme
# est exactement ce que cet audit poursuit.
if __name__ == '__main__':
    for lib, cible in (("cible presente dans df ", 'nb_sinistres'),
                       ("cible ABSENTE de df    ", 'cible_qui_nexiste_pas'),
                       ("cible CONSTANTE        ", 'cible_constante')):
        flux = io.StringIO()
        logging.disable(logging.NOTSET)
        lg = logging.getLogger(f'h1.{cible}')
        lg.handlers[:] = []
        h = logging.StreamHandler(flux)
        lg.addHandler(h)
        lg.setLevel(logging.WARNING)
        mx = C.construire_matrice_x(COLS, contexte='H1', df=df, col_cible=cible,
                                    logger_agent=lg, facteurs_supplementaires=SUPP)
        logging.disable(logging.CRITICAL)
        fuite_vue = 'zorglub' not in list(mx)
        avert = ("ANTI-FUITE PAR L'EFFET" in flux.getvalue()
                 and 'NON' in flux.getvalue())
        print(f"  {lib} controle_effet_execute = "
              f"{str(mx.controle_effet_execute):5s}  "
              f"fuite ecartee = {str(fuite_vue):5s}  avertissement = {avert}")

print()
print("  -> LE MEME OBJET dit « controle execute » dans les trois cas.")
print("     Dans deux d'entre eux le controle n'a examine AUCUNE colonne, et")
print("     'zorglub' (la cible plus un bruit de 1e-6) entre dans la matrice X.")


# ══════════════════════════════════════════════════════════════════════════════
titre("H2 -- B7 : L'ANTERIORITE EST LE CRITERE... POUR LES NOMS QUI LE DISENT")
# ══════════════════════════════════════════════════════════════════════════════
print("  Un portefeuille RC Pro reel : la frequence est proportionnelle a")
print("  l'EFFECTIF de l'entreprise. 'effectif' et 'nb_salaries' sont declares")
print("  facteurs legitimes (liste blanche l.381). Ils n'ont aucun marqueur de")
print("  passe. Que leur arrive-t-il ?")
print()
rng2 = np.random.default_rng(11)
m = 4000
effectif = rng2.integers(1, 400, m).astype(float)
ca = effectif * rng2.uniform(45_000, 90_000, m)
anc = rng2.uniform(1, 40, m)
# frequence RC Pro : proportionnelle a l'effectif (comme l'exposition l'est en auto)
sin = rng2.poisson(0.020 * effectif, m).astype(float)
dfp = pd.DataFrame({
    'effectif': effectif, 'nb_salaries': effectif,
    'ca_annuel_eur': ca, 'anciennete_entreprise_ans': anc,
    'antecedents_sinistres_3ans': rng2.poisson(3 * 0.020 * effectif, m).astype(float),
    'nb_sinistres': sin,
})
print(f"  frequence moyenne = {sin.mean():.2f} sinistre(s)/an/contrat  "
      f"({(sin == 0).mean():.0%} de zeros)")
fuites, alertes = C.detecter_fuites_par_effet(
    dfp, [c for c in dfp.columns if c != 'nb_sinistres'], 'nb_sinistres',
    retourner_alertes=True)


def _signal(col):
    """Le signal REELLEMENT calcule par le module, pour toute colonne."""
    yv = dfp['nb_sinistres'].astype(float)
    tr = getattr(np, 'trapezoid', None) or np.trapz
    ya = yv.to_numpy(float)

    def g(xa):
        o = np.argsort(-xa)
        yo = ya[o]
        t = yo.sum()
        if t <= 0:
            return 0.0
        return float(2.0 * tr(np.cumsum(yo) / t,
                              np.arange(1, len(yo) + 1) / len(yo)) - 1.0)
    gp = g(ya)
    gn = abs(g(dfp[col].to_numpy(float)) / gp) if gp > 1e-9 else 0.0
    rho = abs(float(yv.rank().corr(dfp[col].rank())))
    return rho, gn


for c in dfp.columns:
    if c == 'nb_sinistres':
        continue
    rho, gn = _signal(c)
    if c in fuites:
        etat = "[ECARTEE ]"
        note = "<-- « la cible deguisee », exclusion OBLIGATOIRE"
    elif c in alertes:
        etat = "[ALERTEE ]"
        note = "(conservee, marqueur de passe)"
    else:
        etat = "[gardee  ]"
        note = ""
    print(f"  {etat} {c:28s} spearman={rho:.3f} gini_norm={gn:.3f}  {note}")

mxp = C.construire_matrice_x(
    [c for c in dfp.columns if c != 'nb_sinistres'], contexte='H2',
    df=dfp, col_cible='nb_sinistres')
print()
print(f"  matrice X livree : {list(mxp)}")
for c, motif in sorted(mxp.exclusions.items()):
    print(f"    exclue {c!r} -> {motif[:66]}...")
txt = C.synthese_exclusions(mxp.exclusions)
if txt:
    print()
    print("  Ce que le RAPPORT dira a l'actuaire :")
    for L in txt.split('\n'):
        print(f"      {L[:96]}")


# ══════════════════════════════════════════════════════════════════════════════
titre("H3 -- L'EXEMPTION PAR LE PLAN EST-ELLE SIGNALEE ?")
# ══════════════════════════════════════════════════════════════════════════════
print("  Deux facons d'exempter du controle par l'effet :")
print("    (a) un NOM porteur d'un marqueur de passe -> alerte 'A VERIFIER'")
print("    (b) plan.facteurs_anteriorite()            -> ?")
print()
dfx = pd.DataFrame({
    'age': rng2.uniform(18, 80, m), 'nb_sinistres': sin,
    'sinistres_anterieurs_3ans': sin + rng2.normal(0, 1e-6, m),   # (a) marqueur
    'score_experience': sin + rng2.normal(0, 1e-6, m),            # (b) plan
})


class PlanAvecAnteriorite:
    def colonnes_produites(self):
        return ('age', 'sinistres_anterieurs_3ans', 'score_experience')

    def facteurs_anteriorite(self):
        return ('score_experience',)


mxa = C.construire_matrice_x(
    ['age', 'sinistres_anterieurs_3ans', 'score_experience'], contexte='H3',
    df=dfx, col_cible='nb_sinistres', plan=PlanAvecAnteriorite())
print(f"  matrice X : {list(mxa)}")
print(f"  alertes   : {mxa.alertes}")
print(f"  exclusions: {list(mxa.exclusions)}")
print()
print(f"  synthese_alertes_experience -> ", end='')
sa = C.synthese_alertes_experience(mxa.alertes)
print((sa.split('.')[0] + '.') if sa else 'None')
print()
print("  Les deux colonnes sont la MEME grandeur (la cible + 1e-6). L'une est")
print("  signalee a l'actuaire, l'autre ne l'est nulle part.")


# ══════════════════════════════════════════════════════════════════════════════
titre("H4 -- LES MOTS METRIQUES DETRUISENT-ILS DES MODALITES LEGITIMES ?")
# ══════════════════════════════════════════════════════════════════════════════
print("  Un one-hot produit 'facteur_modalite'. La regle l.486 rejette tout")
print("  suffixe contenant un MOT METRIQUE. Sur des modalites reelles :")
print()
CAS = [
    ('garantie_perte_exploitation', 'LA garantie centrale de la RC Pro'),
    ('type_garantie_perte_exploitation', 'idem, via type_garantie'),
    ('garantie_perte_financiere', 'garantie RC Pro courante'),
    ('secteur_activite_imprimerie', "'imprimerie' contient 'prime'"),
    ('secteur_activite_couture', "'couture' contient 'cout'"),
    ('secteur_activite_primeur', "'primeur' contient 'prime'"),
    ('garantie_incendie', 'temoin -- doit passer'),
    ('carburant_diesel', 'temoin -- doit passer'),
    ('garantie_montant_regle', 'B6 -- doit etre rejete'),
]
for nom, quoi in CAS:
    ok = C.est_facteur_autorise(nom)
    marque = '[bon    ]' if ok else '[CONSTAT]'
    if nom == 'garantie_montant_regle':
        marque = '[bon    ]' if not ok else '[CONSTAT]'
    print(f"  {marque} {nom:36s} autorise={str(ok):5s}  {quoi}")


# ══════════════════════════════════════════════════════════════════════════════
titre("H5 -- LE MOTIF LU PAR L'ACTUAIRE EST-IL LISIBLE ?")
# ══════════════════════════════════════════════════════════════════════════════
mxf = C.construire_matrice_x(['age', 'bonus_malus', 'zorglub'], contexte='H5',
                             df=df, col_cible='nb_sinistres')
for c, motif in mxf.exclusions.items():
    print(f"  {c!r} :")
    for L in [motif[i:i + 88] for i in range(0, len(motif), 88)]:
        print(f"      {L}")


# ══════════════════════════════════════════════════════════════════════════════
titre("H6 -- LE MOTIF DES 6 VARIABLES DE B5")
# ══════════════════════════════════════════════════════════════════════════════
B5 = ['charge_sinistres_n1', 'nb_sinistres_passes', 'historique_sinistres_3ans',
      'montant_sinistres_anterieurs', 'sinistres_anterieurs_5ans',
      'cout_total_sinistres_anterieurs']
mxb = C.construire_matrice_x(['age'] + B5, contexte='H6')
print(f"  matrice X : {list(mxb)}")
for c in B5:
    print(f"    {c:34s} -> {mxb.exclusions.get(c, '(conservee)')[:60]}")
print()
print("  Ce que le RAPPORT dira :")
t = C.synthese_exclusions(mxb.exclusions)
for L in (t or '').split('\n'):
    for k in range(0, len(L), 92):
        print(f"      {L[k:k + 92]}")


# ══════════════════════════════════════════════════════════════════════════════
titre("H7 -- UN MARQUEUR DE PASSE SUFFIT-IL A TRAVERSER LES QUATRE GARDE-FOUS ?")
# ══════════════════════════════════════════════════════════════════════════════
dfm = df.copy()
dfm['prime_pure_n1'] = dfm['nb_sinistres'] * 1000.0    # la cible, deguisee
etapes = [
    ('1 liste blanche', C.est_facteur_autorise('prime_pure_n1')),
    ('2 genre        ', not C._est_variable_genre('prime_pure_n1')),
    ('3 anti-fuite nom', not C._est_derivee_sinistralite('prime_pure_n1')),
]


class PlanLarge:
    def colonnes_produites(self):
        return ('age', 'bonus_malus', 'prime_pure_n1')

    def facteurs_anteriorite(self):
        return ()


mx7 = C.construire_matrice_x(['age', 'bonus_malus', 'prime_pure_n1'],
                             contexte='H7', df=dfm, col_cible='nb_sinistres',
                             plan=PlanLarge())
etapes.append(("4 effet        ", 'prime_pure_n1' in list(mx7)))
for lib, passe in etapes:
    print(f"    garde-fou {lib} : {'TRAVERSE' if passe else 'bloque'}")
print(f"  matrice X finale : {list(mx7)}")
print(f"  alertes          : {list(mx7.alertes)}")


# ══════════════════════════════════════════════════════════════════════════════
titre("H8 -- LE CONTROLE PAR L'EFFET VOIT-IL LES COLONNES NON NUMERIQUES ?")
# ══════════════════════════════════════════════════════════════════════════════
dfs = df.copy()
dfs['libelle_gravite'] = np.where(dfs['nb_sinistres'] > 0, 'SINISTRE', 'RAS')
f2 = C.detecter_fuites_par_effet(dfs, ['age', 'libelle_gravite', 'zorglub'],
                                 'nb_sinistres')
print(f"  colonnes examinees : age (num), zorglub (num, fuite), "
      f"libelle_gravite (texte, fuite parfaite)")
print(f"  ecartees : {sorted(f2)}")
print(f"  -> 'libelle_gravite' est la cible binarisee, en texte. "
      f"{'VUE' if 'libelle_gravite' in f2 else 'INVISIBLE'} au garde-fou n.4.")
