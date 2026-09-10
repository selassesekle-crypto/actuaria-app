# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — LA GEOMETRIE DU TRIANGLE SE LIT DANS LA DONNEE, PAS DANS SA FORME
=============================================================================

 Toute la couche N3 repose sur une convention jamais ecrite : **l'indice de
 ligne et l'indice de colonne avancent au MEME PAS**, si bien que `i + j`
 est le temps calendaire et que `i + j < n` est la zone observee. Cette
 convention est vraie de la plupart des triangles. Quand elle est fausse, le
 module ne s'en apercoit pas -- il calcule quand meme, et il se tait.

 MESURE. Sur 8 annees de survenance annuelles developpees en 32 trimestres,
 le module lit **36 cellules sur 144** et publie **1 364 690 EUR** la ou la
 reserve vraie est **3 316 654 EUR** : **-58,9 %**. Preuve que les 108
 autres ne sont lues par personne : les multiplier par DIX ne deplace le
 Best Estimate d'aucun centime.

 CE QUE CE MODULE FAIT. Il lit **le pas** entre les longueurs de lignes
 observees et en tire la geometrie :

   pas = 1     le triangle usuel. Rien ne change, jamais.
   pas = K > 1 le developpement est plus fin que la survenance (annuel x
               trimestriel : K = 4). On AGREGE l'axe de developpement pour
               revenir au pas de la survenance, et toute la couche N3
               tourne inchangee.
   pas = 0     toutes les lignes vont jusqu'au bout : plus aucune cellule
               n'est inconnue. Il n'y a pas de futur a projeter.
   illisible   les longueurs ne decroissent pas regulierement : ce n'est
               pas un triangle. On le dit.

 ⚠️⚠️ POURQUOI AGREGER PLUTOT QUE LIRE LE MASQUE. Rendre les estimateurs
 pilotes par le masque des cellules observees est plus seduisant : cela
 garderait la finesse trimestrielle. **C'est mesure, et c'est dangereux.**
 Deux sites suffisent a rendre le Best Estimate exact (-0,00 % sur l'oracle,
 et aucun euro deplace sur RAA ni GenIns) -- mais `mack.py` et
 `bootstrap_odp.py` portent LEUR PROPRE frontiere. Sur le meme triangle
 bruite, on obtient alors un BE de 3 292 747 EUR assorti d'un **CV de
 3 961 256 %**, d'un **P90 de 30 261 EUR -- CENT FOIS SOUS la moyenne** --
 et d'un ecart-type bootstrap NUL. Un montant juste avec une incertitude
 absurde est PIRE que l'etat anterieur, ou tout etait faux ensemble.
 ⚠️ Et c'est MAL POSE : 31 facteurs ne tiennent pas dans 8 lignes
 d'origine. La finesse achetee ne serait pas soutenue par la donnee.
 Apres agregation, le meme triangle bruite rend un CV de **3,43 %** et un
 P90 AU-DESSUS du BE.

 ⚠️ L'AGREGATION EST EXACTE, PAS APPROCHEE : le triangle agrege depuis les
 trimestres et le triangle annuel construit directement different de
 **0,000000 EUR**, cellule par cellule. Sur un triangle CUMULE on
 SELECTIONNE la colonne `K*k + K-1` -- on ne somme pas, le cumul est deja
 fait.

 ⚠️ CE QUE L'AGREGATION COUTE, ET QUI DOIT ETRE ECRIT. Le profil
 d'ecoulement passe au pas de la survenance : si A10 actualise sur un
 echeancier plus fin, cette finesse est perdue. Et quand l'arrete tombe EN
 MILIEU de sous-periode, la derniere sous-periode incomplete de chaque
 ligne est ecartee -- mesure : **6,3 %** des paiements observes si l'arrete
 tombe au premier trimestre, **11,6 %** au deuxieme, **16,3 %** au
 troisieme, **0 %** en fin d'annee. C'est borne, et c'est declare.

 LE REMPLISSAGE, TROUVE EN INSTRUISANT LE RESTE.

 ⚠️⚠️ Un triangle 6x6 pose dans une matrice 6x10 dont les quatre dernieres
 colonnes sont VIDES n'est pas le meme dossier. Les colonnes vides
 fabriquent quatre facteurs de developpement egaux a 1,0000 ; l'estimateur
 de queue lit les DERNIERS facteurs, les trouve stabilises, et conclut
 « tail non applicable ». Mesure sur les MEMES 21 cellules :

     6x6            facteurs 1,85 1,39 1,24 1,16 1,12   tail 1,2624  ROUGE
     6x10 complete  les memes + 1,0000 x4               tail 1,0     VERT
     Best Estimate  1 582 982 EUR  ->  972 735 EUR      soit -38,6 %

 Une reserve plus basse ASSORTIE D'UN VOYANT PLUS VERT, pour des colonnes
 qui ne contiennent rien. Tout extrait qui reserve la largeur maximale de
 developpement produit ce cas. Les colonnes de queue entierement vides sont
 donc RETIREES avant tout calcul, et le retrait est dit.
=============================================================================
"""
from typing import Dict, List, Optional, Tuple

import numpy as np

__all__ = [
    'GeometrieRefusee',
    'analyser_geometrie',
    'appliquer_geometrie',
    'longueurs_observees',
    'pas_de_developpement',
]

#: Ce qu'une cellule vaut quand elle n'est pas observee. C'est la convention
#: du module, ecrite dans `chain_ladder.calculer_facteurs` : « Zeros utilises
#: pour les cellules inconnues ». On la NOMME au lieu de la recopier.
INCONNU = 0.0


class GeometrieRefusee(ValueError):
    """La geometrie du triangle ne permet aucun calcul honnete."""


def longueurs_observees(C: np.ndarray) -> List[int]:
    """Index de la DERNIERE cellule connue de chaque ligne, plus un.

    ⚠️ PAS LEUR NOMBRE. Compter les cellules non nulles parait equivalent et
    ne l'est pas : un TROU interieur -- une annee sans aucun paiement au
    milieu du developpement -- fait perdre une unite a la ligne et rend le
    pas illisible. Mesure : RAA avec une seule cellule interieure annulee
    passe de « pas = 1 » a « pas illisible » si l'on compte, et reste a
    « pas = 1 » si l'on prend le dernier index.
    """
    A = np.asarray(C, dtype=float)
    out = []
    for i in range(A.shape[0]):
        connues = np.where(np.isfinite(A[i]) & (A[i] != INCONNU))[0]
        out.append(int(connues[-1]) + 1 if connues.size else 0)
    return out


def pas_de_developpement(C: np.ndarray) -> Optional[int]:
    """Le pas constant entre les longueurs de lignes, ou None s'il n'y en a
    pas.

    Sur un triangle usuel il vaut 1 -- la regle GENERALISE donc l'existant
    au lieu de le contourner, et c'est ce qui garantit qu'aucun dossier
    d'aujourd'hui ne bouge.
    """
    L = longueurs_observees(C)
    if len(L) < 2:
        return None
    ecarts = {L[i] - L[i + 1] for i in range(len(L) - 1)}
    return ecarts.pop() if len(ecarts) == 1 else None


def _retirer_colonnes_vides(C: np.ndarray) -> Tuple[np.ndarray, int]:
    """Retire les colonnes de QUEUE entierement inconnues."""
    A = np.asarray(C, dtype=float)
    pleines = np.where(np.any(np.isfinite(A) & (A != INCONNU), axis=0))[0]
    if not pleines.size:
        return A, 0
    fin = int(pleines[-1]) + 1
    return A[:, :fin], A.shape[1] - fin


def _agreger(C: np.ndarray, K: int) -> Tuple[np.ndarray, float]:
    """Ramene l'axe de developpement au pas de la survenance.

    Sur un triangle CUMULE, le cumul de la periode k EST le cumul de la
    sous-periode `K*k + K-1` : on SELECTIONNE, on ne somme pas. Rend aussi
    la part des paiements observes que la selection ECARTE -- la derniere
    sous-periode incomplete de chaque ligne.
    """
    A = np.asarray(C, dtype=float)
    n, m = A.shape
    L = longueurs_observees(A)
    n_col = (m + K - 1) // K
    B = np.zeros((n, n_col))
    retenu = 0.0
    for i in range(n):
        for k in range(n_col):
            q = K * k + (K - 1)
            if q < L[i]:
                B[i, k] = A[i, q]
                retenu = max(retenu, 0.0)
    # part ecartee : ce qui suit la derniere sous-periode COMPLETE de la ligne
    total = ecarte = 0.0
    for i in range(n):
        if not L[i]:
            continue
        dernier_complet = (L[i] // K) * K
        total += float(A[i, L[i] - 1])
        if dernier_complet >= 1:
            ecarte += float(A[i, L[i] - 1]) - float(A[i, dernier_complet - 1])
        else:
            ecarte += float(A[i, L[i] - 1])
    # on ne garde que les colonnes qui portent quelque chose
    B, _ = _retirer_colonnes_vides(B)
    return B, (100.0 * ecarte / total if total else 0.0)


def appliquer_geometrie(C_autre: np.ndarray, geo: Dict) -> np.ndarray:
    """Applique à un SECOND triangle la géométrie retenue pour le premier.

    ⚠️⚠️ POURQUOI PAS UNE SECONDE `analyser_geometrie`. Deux analyses
    indépendantes peuvent conclure différemment : mesuré, un payé 6×10 aux
    quatre colonnes de queue vides devenait 6×6, l'engagé restait 6×10, et
    `munich_cl.valider_prerequis` désactivait la méthode sur
    « Dimensions incompatibles : payé (6, 6) ≠ engagé (6, 10) » — un motif que
    l'utilisateur ne peut pas corriger, puisqu'il avait bien fourni deux
    matrices de MÊME forme. Le nettoyage du module fabriquait l'incompatibilité
    qu'il reprochait ensuite aux données.

    La règle est donc : l'engagé subit LA MÊME transformation, jamais la
    sienne. Les deux triangles restent comparables par construction — ce que
    Munich CL exige, puisqu'il rapproche cellule à cellule.
    """
    A = np.asarray(C_autre, dtype=float)
    if geo.get('transforme'):
        A, _ = _agreger(A, int(geo['pas']))
    largeur = int(geo['triangle'].shape[1])
    if A.shape[1] > largeur:
        A = A[:, :largeur]
    return A


def analyser_geometrie(C: np.ndarray) -> Dict:
    """Rend `{'triangle', 'pas', 'infos', 'transforme'}`, ou leve
    `GeometrieRefusee`.

    ⚠️ L'ASYMETRIE EST VOULUE. Un triangle dont le developpement ne depasse
    pas la survenance (`m <= n`) n'est PAS examine : c'est la forme normale,
    y compris tronquee, et la toucher ferait courir un risque a des dossiers
    qui n'ont rien demande. Seule la forme que le module traite aujourd'hui
    en silence -- plus large que haute -- passe par l'analyse.
    """
    A = np.asarray(C, dtype=float)
    infos: List[str] = []

    A, retirees = _retirer_colonnes_vides(A)
    if retirees:
        infos.append(
            f"🔵 Géométrie : {retirees} colonne(s) de développement "
            f"entièrement vide(s) retirée(s) avant calcul. Laissées en place, "
            f"elles fabriquent autant de facteurs égaux à 1,0000 : "
            f"l'estimateur de queue les lit comme des coefficients stabilisés "
            f"et retire la queue. Mesuré sur un cas à quatre colonnes vides : "
            f"tail 1,2624 → 1,0, statut ROUGE → VERT, Best Estimate −38,6 %.")

    n, m = A.shape

    # ⚠️⚠️ « AUCUN FUTUR » N'EST PAS UNE QUESTION DE FORME, ET CE REFUS NE
    # VIVAIT QUE DANS LA BRANCHE `m > n`. Un carré 6×6 ou un tronqué 8×4 dont
    # TOUTES les cellules sont connues traversait en silence et recevait
    # « pas = 1 ». Mesuré sur un 6×6 entièrement observé — donc d'IBNR NUL par
    # construction : le module publiait 870 € de réserve, 7,3 % de la charge à
    # date, entièrement extrapolés. Le MÊME jeu de nombres posé en 4×8 était
    # refusé, avec le message ci-dessous. Des quatre géométries que ce module
    # nomme, c'est la seule dont l'assiette dépendait de la forme.
    #
    # ⚠️ LE PRÉDICAT EST LU DANS LA DONNÉE, ET IL EST STRICTEMENT PLUS ÉTROIT
    # QUE `pas == 0` : il exige que CHAQUE ligne aille jusqu'à la dernière
    # colonne. Un triangle usuel a `L = [m, m−1, …]` — il n'entre jamais ici.
    # Aucun dossier au pas usuel ne peut donc être refusé par cette porte.
    _L = longueurs_observees(A)
    if n >= 2 and m >= 1 and all(l == m for l in _L):
        raise GeometrieRefusee(
            f"Triangle {n}×{m} entièrement observé : aucune cellule n'est "
            f"inconnue, il n'y a donc aucun futur à projeter. Un portefeuille "
            f"dont toutes les survenances sont développées jusqu'au bout ne "
            f"relève pas d'une méthode de provisionnement — sa charge est "
            f"connue. Le module publierait sinon une réserve entièrement "
            f"extrapolée.")

    if m <= n:
        return {'triangle': A, 'pas': 1, 'infos': infos, 'transforme': False}

    pas = pas_de_developpement(A)

    if pas is None:
        raise GeometrieRefusee(
            f"Géométrie du triangle non interprétable : {n} années de "
            f"survenance pour {m} périodes de développement, et les longueurs "
            f"de lignes observées ({longueurs_observees(A)}) ne décroissent "
            f"pas d'un pas constant. Le module ne peut pas situer la frontière "
            f"entre observé et futur ; il la supposerait à i+j<n et écarterait "
            f"des paiements réels sans le dire.")

    if pas == 0:
        raise GeometrieRefusee(
            f"Triangle {n}×{m} entièrement observé : aucune cellule n'est "
            f"inconnue, il n'y a donc aucun futur à projeter. Un portefeuille "
            f"dont toutes les survenances sont développées jusqu'au bout ne "
            f"relève pas d'une méthode de provisionnement — sa charge est "
            f"connue. Le module publierait sinon une réserve entièrement "
            f"extrapolée.")

    if pas < 0:
        raise GeometrieRefusee(
            f"Les lignes du triangle {n}×{m} s'allongent avec l'ancienneté "
            f"(pas = {pas}) : les survenances les plus récentes seraient "
            f"observées plus longtemps que les anciennes, ce qui est "
            f"impossible à une date d'arrêté unique.")

    if pas == 1:
        raise GeometrieRefusee(
            f"Triangle {n}×{m} : {m} périodes de développement pour seulement "
            f"{n} années de survenance, au pas de 1. C'est un portefeuille en "
            f"run-off — les survenances se sont arrêtées et le développement a "
            f"continué. Les méthodes du module situent la frontière à i+j<n et "
            f"écarteraient "
            f"{sum(max(0, l - (n - i)) for i, l in enumerate(longueurs_observees(A)))} "
            f"cellules observées sans le dire.")

    B, part_ecartee = _agreger(A, pas)
    infos.append(
        f"🔵 Géométrie : {pas} périodes de développement par année de "
        f"survenance, lues dans les longueurs de lignes "
        f"({longueurs_observees(A)}). L'axe de développement est agrégé au pas "
        f"de la survenance — {A.shape[0]}×{A.shape[1]} → {B.shape[0]}×{B.shape[1]} "
        f"— sinon la frontière i+j<n écarterait la majeure partie des "
        f"paiements observés en silence.")
    infos.append(
        "⚠️ Le profil d'écoulement est désormais au pas de la survenance : la "
        "finesse infra-annuelle est perdue pour l'actualisation en aval.")
    if part_ecartee > 0.01:
        infos.append(
            f"⚠️ L'arrêté tombe en milieu de sous-période : {part_ecartee:.2f} % "
            f"des paiements observés tombent dans une sous-période incomplète "
            f"et ne sont pas retenus par l'agrégation.")
    return {'triangle': B, 'pas': pas, 'infos': infos, 'transforme': True}
