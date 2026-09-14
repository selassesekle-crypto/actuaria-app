"""
=============================================================================
  ActuarIA — PLUSIEURS PRIX, UN SEUL CRITÈRE QUI ÉLIMINE
=============================================================================

⚠️⚠️ CE QUE CE MODULE EXISTE POUR EMPÊCHER. Comparer des prix, c'est comparer
des **calibrations** avant de comparer des risques. Mesuré le 08/09/2026 sur
les candidats du dépôt : le rapport prédit/observé va de **0,5508 à 1,2438**,
un facteur **2,26**. Publier ces prix côte à côte sans rien d'autre
présenterait un écart de calage comme un choix de tarif.

LE COEFFICIENT D'ÉQUILIBRE A DEUX MÉTIERS, ET IL NE FAUT PAS LES CONFONDRE
  · celui de PRODUCTION est calculé sur le portefeuille complet, pour que la
    prime totale reproduise la charge totale — c'est `INV-8`, un invariant du
    dépôt. **Il ne bouge pas d'un centime.**
  · celui de MESURE, `k_train`, est gelé sur le train déclaré et appliqué au
    holdout. Il ne touche **jamais** un prix publié.

  *Les geler tous les deux aurait fait qu'un tarif livré ne s'équilibre plus
  sur les données qui l'ont ajusté : un euro aurait bougé pour un besoin de
  mesure, pas pour une décision de tarif.*

E2 — LE SEUL CRITÈRE QUI ÉLIMINE
  Σ prime prédite (× `k_train`) / Σ charge observée, **sur le holdout**. Un
  modèle dont le calage ne transfère pas échoue ici, et il est ÉCARTÉ avec son
  motif publié. Mesure du 08/09/2026, six candidats réajustés sur une découpe
  déclarée : cinq entre 0,9377 et 1,0086, et `xgboost_tweedie` à **0,8257** —
  celui-là même dont le `k_train` vaut **1,4280** quand les autres sont à
  1,000. *Les deux nombres disent la même chose par deux angles.*

⚠️⚠️ LA BANDE NE S'INVENTE PAS. Sans bande déclarée, E2 est **mesuré et
publié**, mais il n'élimine personne — et le document le dit. C'est le patron
de `refus_anti_selection` : une règle qui bloque se déclare, elle ne se devine
pas. *Et un seuil qui bascule avec la taille de l'échantillon mesure du bruit
— la gate l'a déjà démontré une fois sur ce dépôt.*

⚠️⚠️ ET C'EST DÉSORMAIS TRANCHÉ SUR E2 LUI-MÊME, PAS PAR ANALOGIE — ARBITRAGE
DU 10/09/2026, MESURÉ CONTRADICTOIREMENT. Deux formes de bande ont été
proposées, mesurées à 4 tailles × 5 découpes × 6 candidats, et **les deux sont
réfutées** :

    n        bande FIXE [0,90 ; 1,10]     bande CALCULÉE 1 ± z/√sinistres
    1 000        80,0 % de refus              [0,642 ; 1,358]   40,0 %
    2 000        73,3 %                       [0,770 ; 1,230]   46,7 %
    4 000        53,3 %                       [0,834 ; 1,166]   20,0 %
    8 000        33,3 %                       [0,875 ; 1,125]   20,0 %
    amplitude    46,7 points                                    26,7 points

La bande calculée corrige la LARGEUR, pas le CENTRE : elle reproduit **57 %**
du défaut de la bande fixe. *Un verdict qui dépend encore à moitié de la taille
de l'échantillon reste un verdict sur du bruit.*

⚠️⚠️ ET L'ARGUMENT QUI LES ENTERRE VRAIMENT — elle cesse d'éliminer le mauvais
modèle quand le portefeuille grossit. `xgboost_tweedie` est mal calibré à
TOUTES les tailles (son `k_train` vaut 1,29 à 1,55 partout : il sous-prédit de
23 à 36 % sur ses propres données). La bande le rejette **5 fois sur 5** à
n = 1 000 et le **retient 4 fois sur 5** à n = 8 000. *Elle devient indulgente
exactement quand la réponse commence à compter.*

⚠️ LE « BIAIS DE CENTRE » N'EST PAS UNE PROPRIÉTÉ D'E2 — c'est une COMPOSITION.
La médiane à 0,699 (n = 1 000) est un artefact d'agrégation entre candidats de
qualité inégale : `lineaire_regularise` ne dérive quasiment pas (0,9674 →
1,0158), c'est `xgboost_tweedie` (0,3857 → 0,9578) qui tire la médiane. *Une
médiane entre candidats de qualité inégale n'est la propriété de personne.*

⚠️ CE QUE LA MESURE SUGGÈRE POUR PLUS TARD, ET QUI N'EST PAS CÂBLÉ ICI :
`k_train` est **~40 × plus stable** qu'E2 entre découpes (étendues 0,0005 à
0,0308 contre 0,2031 à 0,2278) et sépare proprement les candidats aux quatre
tailles. ⚠️⚠️ **MAIS LES DEUX NE MESURENT PAS LA MÊME FAUTE** : `k_train`
détecte un défaut de **spécification** (le modèle ne se cale pas sur ses
propres données), E2 un défaut de **transfert** (il se cale sur le train et pas
ailleurs). *`k_train` n'est donc PAS un substitut d'E2* — au mieux un meilleur
candidat pour un critère qui élimine, le jour où l'on en déclarera un. Rien
n'est câblé sur cette base : la mesure ci-dessus porte sur un portefeuille où
la seule faute réelle est de spécification, et une règle ne se pose pas sur un
seul portefeuille.

⚠️ CE QUI EST COMPARÉ : la FRÉQUENCE de chaque candidat, multipliée par un
modèle de coût PARTAGÉ. Mesuré : il n'existe qu'un seul modèle de sévérité
dans toute la chaîne. Comparer autre chose supposerait des modèles de coût qui
n'existent pas — et le document doit dire ce qu'il compare.
=============================================================================
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

__all__ = [
    'CAUSE_CRITERE', 'CAUSE_SANS_PRIX', 'NATURES',
    'AdaptateurTauxFrequence', 'Candidat', 'NatureIncomparable',
    'ResultatCandidat', 'assiette_du_tarif', 'niveau_holdout',
    'refuser_assiette_discordante', 'refuser_natures_melangees',
    'synthese_comparaison',
]

#: ⚠️⚠️ TROIS NATURES, ET ELLES NE SE COMPARENT PAS ENTRE ELLES. Un modèle de
#: fréquence rend un taux annuel par unité d'exposition ; un modèle de prime
#: pure rend un montant ; un modèle de coût rend une sévérité. Les additionner
#: dans un même tableau referait l'erreur des deux bases de Gini
#: incompatibles, déjà trouvée et fermée ailleurs dans ce chantier.
#:
#: ⚠️ MESURÉ LE 08/09/2026 : les sept candidats classés par A6 sont TOUS de
#: nature `frequence` — y compris `xgboost_tweedie`, dont l'objectif est
#: `reg:tweedie` mais qui est **ajusté sur `nb_sinistres`**. *Le nom trompe,
#: la construction non.* Le seul vrai modèle de prime pure du dépôt est le
#: `tweedie` d'A3, et il n'entre pas dans le classement.
#:
#: Ce garde ne bloque donc rien aujourd'hui — et c'est exactement sa valeur :
#: il tient AVANT que la faute arrive. Le jour où quelqu'un change une cible
#: (`a4:697` bascule de `poisson` à `tweedie` selon la cible), le catalogue
#: mélangerait deux natures sans un mot.
NATURES = ('frequence', 'prime_pure', 'cout_moyen')


class NatureIncomparable(Exception):
    """Deux candidats de natures différentes dans la même comparaison."""


@dataclasses.dataclass(frozen=True)
class Candidat:
    """Un modèle candidat, avec la nature DÉCLARÉE de ce qu'il prédit."""
    nom: str
    nature: str
    source: str = ''          # 'A3', 'A4', 'A5' — d'où vient la famille

    def __post_init__(self):
        if self.nature not in NATURES:
            raise ValueError(
                f"candidat '{self.nom}' : nature '{self.nature}' inconnue — "
                f"attendu l'une de {', '.join(NATURES)}. La nature n'est pas "
                f"une étiquette : elle dit ce que `predict` rend, et deux "
                f"natures ne se comparent pas.")
        if not str(self.nom or '').strip():
            raise ValueError("candidat : `nom` est obligatoire.")


#: ⚠️⚠️ DEUX CAUSES DE MISE À L'ÉCART, ET ELLES NE SONT PAS DE MÊME NATURE.
#: `critere_E2` est un CRITÈRE : le candidat sait produire un prix, et ce prix
#: échoue à la bande déclarée. `sans_prix` est une IMPOSSIBILITÉ : le candidat
#: ne produit pas de prix du tout — une fréquence négative ou non finie ne
#: fait pas un prix cher, elle ne fait pas un prix.
#:
#: *E2 reste le SEUL critère éliminatoire. Refuser de publier un nombre qui
#: n'en est pas un n'est pas un second critère : c'est le refus de publier.*
#:
#: ⚠️ ET CE N'EST PAS THÉORIQUE. Mesuré le 08/09/2026 : `gbm`, `lightgbm` et
#: `catboost` rendent des fréquences NÉGATIVES sur ce portefeuille (77, 129 et
#: 15 contrats sur 2 500). Leur objectif est une régression non bornée sur une
#: cible à beaucoup de zéros. A4 le sait — il écrête à zéro en **cinq
#: endroits** (`a4:1225, 1249, 1279, 1454, 1455`) pour calculer ses métriques.
#: *Son Gini décrit donc un modèle écrêté, pendant que le modèle brut ne sait
#: pas tarifer.*
CAUSE_CRITERE = 'critere_E2'
CAUSE_SANS_PRIX = 'sans_prix'


@dataclasses.dataclass(frozen=True)
class ResultatCandidat:
    """Ce qu'un candidat rend, et ce que la mesure en dit."""
    candidat: Candidat
    k_train: float
    niveau_holdout: float
    ecarte: bool
    motif: str = ''
    somme_prime_pure: float | None = None
    cause: str = ''


def refuser_natures_melangees(candidats) -> str:
    """Refuse une comparaison qui mélangerait deux natures. Rend la nature.

    ⚠️⚠️ LES DEUX SENS, comme pour le routage fiscal : une comparaison à
    natures mélangées est refusée, ET une comparaison homogène passe. Un garde
    qui refuserait tout satisferait le premier sens sans rien protéger.
    """
    natures = {c.nature for c in candidats}
    if not natures:
        raise NatureIncomparable(
            "comparaison de prix : aucun candidat. Il n'y a rien à comparer, "
            "et le document doit le dire plutôt que d'afficher un tableau "
            "vide.")
    if len(natures) > 1:
        detail = ', '.join(f"{c.nom}={c.nature}" for c in candidats)
        raise NatureIncomparable(
            f"comparaison de prix : natures MÉLANGÉES ({detail}). Un modèle "
            f"de fréquence rend un taux, un modèle de prime pure rend un "
            f"montant : les mettre dans le même tableau ferait lire deux "
            f"grandeurs comme une seule. C'est l'erreur des deux bases de "
            f"Gini incompatibles, déjà trouvée et fermée dans ce dépôt.")
    return next(iter(natures))


def assiette_du_tarif(tarif):
    """Les lignes sur lesquelles ce tarif a RÉELLEMENT été ajusté, ou `None`.

    ⚠️ Lu par `getattr`, jamais par un import : le socle ne connaît pas
    `TarifNonVie`, qui vit dans une direction. `None` signifie « ce tarif n'a
    pas été ajusté par `pipeline_complet` », donc **on ne sait pas** sur quelles
    lignes il l'a été — ce n'est pas « il a été ajusté sur tout ».
    """
    rapport = getattr(tarif, 'rapport_qualite', None)
    if rapport is None:
        return None
    return getattr(rapport, 'dataframe_propre', None)


def _colonnes_discordantes(gauche, droite) -> list:
    """Les colonnes dont les VALEURS diffèrent, index supposé déjà égal."""
    ecarts = []
    for colonne in droite.columns:
        a, b = gauche[colonne], droite[colonne]
        if (pd.api.types.is_numeric_dtype(a)
                and pd.api.types.is_numeric_dtype(b)):
            if not np.allclose(a.to_numpy(dtype=float),
                               b.to_numpy(dtype=float), equal_nan=True):
                ecarts.append(colonne)
        elif not a.astype(str).equals(b.astype(str)):
            ecarts.append(colonne)
    return ecarts


def refuser_assiette_discordante(tarif, portefeuille) -> str:
    """L'assiette de la comparaison EST celle du tarif, ou il n'y a pas de prix.

    ⚠️⚠️ CE QUE CE GARDE EXISTE POUR EMPÊCHER, ET C'EST MESURÉ. `pipeline_complet`
    ajuste sur `rapport_qualite.dataframe_propre` — **après** que la couche
    qualité a exclu les lignes impossibles (règle 1) et corrigé les implausibles
    établies (règle 2). Le premier appelant de production, lui, remettait ici le
    portefeuille d'AVANT cette couche.

      Mesuré le 08/09/2026, 2 000 lignes portant 3 % de défauts réalistes : la
      couche exclut **25 lignes** (`frequence_negative` 10,
      `exposition_non_positive` 15) et **corrige 35 expositions**
      (`exposition_sup_1`). Sur l'assiette brute, **6 candidats sur 6 sont sans
      prix publiable, 0 survivant** ; sur l'assiette du tarif, **1 survivant à
      622 391,70 EUR**, 2 écartés par le critère, 3 sans prix. *Le verdict
      publié bascule entièrement.*

    ⚠️⚠️ ET LES LONGUEURS NE SUFFISENT PAS. Une correction de règle 2 garde la
    ligne et change sa VALEUR : même longueur, même index, exposition différente.
    Un garde qui ne compterait que des lignes la laisserait passer — et le prix
    serait mesuré sur une exposition que le tarif n'a jamais vue.

    ⚠️ ON REFUSE, ON NE SUBSTITUE PAS. Remplacer en silence l'assiette par la
    bonne cacherait l'erreur de l'appelant. *Un appelant qui se trompe d'assiette
    doit l'apprendre.* Rend le motif publiable, ou `''` si tout concorde.
    """
    assiette = assiette_du_tarif(tarif)
    if assiette is None:
        return (
            "AUCUNE COMPARAISON DE PRIX : ce tarif ne porte aucun rapport de "
            "qualite, donc rien ne dit sur quelles lignes il a ete ajuste. "
            "Comparer des prix sur des lignes que le tarif n'a pas vues "
            "publierait des prix qui ne sont pas les siens. Un tarif ajuste "
            "par `pipeline_complet` porte ce rapport.")
    if list(portefeuille.columns) != list(assiette.columns):
        manque = [c for c in assiette.columns if c not in portefeuille.columns]
        surplus = [c for c in portefeuille.columns
                   if c not in assiette.columns]
        return (
            f"AUCUNE COMPARAISON DE PRIX : le portefeuille remis n'a pas les "
            f"memes colonnes que l'assiette d'ajustement du tarif -- "
            f"manquante(s) {manque[:5]}, en trop {surplus[:5]}.")
    if len(portefeuille) != len(assiette):
        return (
            f"AUCUNE COMPARAISON DE PRIX : le portefeuille remis porte "
            f"{len(portefeuille)} ligne(s), le tarif a ete ajuste sur "
            f"{len(assiette)}. La couche qualite a exclu des lignes que la "
            f"comparaison tarifierait quand meme : les prix compares ne "
            f"seraient pas ceux de ce tarif.")
    if not portefeuille.index.equals(assiette.index):
        return (
            "AUCUNE COMPARAISON DE PRIX : le portefeuille remis a le meme "
            "NOMBRE de lignes que l'assiette d'ajustement du tarif, mais pas "
            "les memes. Un decompte egal ne fait pas une assiette egale.")
    ecarts = _colonnes_discordantes(portefeuille, assiette)
    if ecarts:
        premiere = ecarts[0]
        n_lignes = int((pd.to_numeric(portefeuille[premiere], errors='coerce')
                        != pd.to_numeric(assiette[premiere], errors='coerce')
                        ).sum()) if pd.api.types.is_numeric_dtype(
                            assiette[premiere]) else -1
        return (
            f"AUCUNE COMPARAISON DE PRIX : les lignes sont les memes, mais "
            f"{len(ecarts)} colonne(s) portent d'autres VALEURS que celles sur "
            f"lesquelles le tarif a ete ajuste : {ecarts[:5]}"
            + (f" ({n_lignes} ligne(s) sur '{premiere}')" if n_lignes >= 0
               else '')
            + ". La couche qualite corrige des valeurs sans retirer la ligne "
              "(regle 2) : un decompte de lignes ne voit pas cette "
              "correction.")
    return ''


class AdaptateurTauxFrequence:
    """Fait parler à un candidat le contrat que `TarifNonVie` attend.

    ⚠️⚠️ POURQUOI IL EXISTE, MESURÉ. `TarifNonVie._taux_frequence` appelle
    `predict(Xc, offset=...)` — une signature que **seul statsmodels** porte.
    Essayé le 08/09/2026 avec un candidat A4 : `TypeError:
    _ModeleFrequenceExposition.predict() got an unexpected keyword argument
    'offset'`. C'est le seul blocage technique du branchement, et il est
    étroit.

    ⚠️ L'OFFSET EST IGNORÉ, ET C'EST CORRECT : le candidat rend DÉJÀ un taux
    annuel par unité d'exposition — `λ(X) = E[N | X, expo=1]` — exactement la
    grandeur que `_taux_frequence` obtient d'un GLM en annulant son offset.
    *Ce n'est pas une approximation, c'est la même quantité par deux chemins.*

    ⚠️ ET IL REFUSE UNE AUTRE NATURE. Envelopper un modèle de prime pure ici
    ferait lire un montant comme un taux, puis le remultiplier par
    l'exposition et par le coût moyen : un prix faux d'un facteur inconnu,
    sans un mot.
    """

    def __init__(self, modele, features, candidat: Candidat):
        if candidat.nature != 'frequence':
            raise NatureIncomparable(
                f"candidat '{candidat.nom}' de nature '{candidat.nature}' : "
                f"cet adaptateur ne sait rendre qu'un TAUX de fréquence. "
                f"L'envelopper ferait lire un {candidat.nature} comme un "
                f"taux, puis le remultiplier par l'exposition et par le coût "
                f"moyen.")
        self.modele = modele
        self.features = tuple(features)
        self.candidat = candidat

    def predict(self, Xc, offset=None, **_):
        X = (Xc[list(self.features)]
             if hasattr(Xc, 'columns') else Xc)
        return np.asarray(self.modele.predict(X), dtype=float)


def niveau_holdout(pred_train, y_train, expo_train,
                   pred_holdout, y_holdout, expo_holdout) -> tuple:
    """E2 — le calage du train tient-il sur le holdout ?

    Rend ``(k_train, niveau)`` :
      · ``k_train`` Σ sinistres observés / Σ prédits, **sur le train** ;
      · ``niveau``  Σ (prédit × `k_train`) / Σ observés, **sur le holdout**.

    ⚠️⚠️ `k_train` EST GELÉ, JAMAIS RECALCULÉ SUR LE HOLDOUT. Le recalculer
    ferait sortir `niveau = 1` pour **n'importe quel** candidat, par
    construction : c'est le piège que trois analyses indépendantes ont
    identifié le même jour. *Un critère qui vaut toujours 1 ne mesure rien.*

    ⚠️ Ce `k_train` n'est PAS le coefficient d'équilibre de production. Celui-
    là reste calculé sur le portefeuille complet (`INV-8`) et ne bouge pas.
    Confondre les deux ferait qu'un tarif livré ne s'équilibre plus sur les
    données qui l'ont ajusté.
    """
    def _somme(pred, expo):
        return float((np.asarray(pred, dtype=float)
                      * np.asarray(expo, dtype=float)).sum())

    somme_tr = _somme(pred_train, expo_train)
    obs_tr = float(np.asarray(y_train, dtype=float).sum())
    if somme_tr <= 0 or obs_tr <= 0:
        return float('nan'), float('nan')
    k = obs_tr / somme_tr
    obs_te = float(np.asarray(y_holdout, dtype=float).sum())
    if obs_te <= 0:
        return k, float('nan')
    return k, _somme(pred_holdout, expo_holdout) * k / obs_te


def synthese_comparaison(resultats, bande=None, nature=None) -> str:
    """La phrase publiable — source UNIQUE de cette rédaction.

    ⚠️⚠️ ELLE DIT CE QU'ELLE COMPARE, et c'est la moitié du travail. Ce sont
    des fréquences multipliées par un modèle de coût PARTAGÉ, mesurées sur un
    holdout déclaré, par des candidats RÉAJUSTÉS sur ce train — pas les
    modèles d'A4, qui sont ajustés sur une découpe qui leur est propre.
    """
    survivants = [r for r in resultats if not r.ecarte]
    ecartes = [r for r in resultats if r.ecarte]
    # ⚠️⚠️ LES DEUX CAUSES SE COMPTENT SEPAREMENT DANS LE DOCUMENT. Un
    # candidat ecarte par E2 sait tarifer et tarife mal ; un candidat sans
    # prix ne tarife pas. Les additionner ferait lire six echecs de meme
    # nature la ou il y en a deux especes.
    par_critere = [r for r in ecartes if r.cause == CAUSE_CRITERE]
    sans_prix = [r for r in ecartes if r.cause == CAUSE_SANS_PRIX]
    # ⚠️⚠️ UN ECARTE SANS CAUSE N'ENTRAIT DANS AUCUN COMPTE — constat `D6`,
    # report du round 4, confirme le 14/09/2026. La tete ne comptait que
    # `CAUSE_CRITERE` et `CAUSE_SANS_PRIX` ; or `ResultatCandidat.cause`
    # vaut `''` PAR DEFAUT, et un ecarte construit sans cause explicite
    # disparaissait de la ventilation.
    #   Mesure du 14/09 :
    #       3 ecartes, causes nommees  -> 2 + 1 = 3 comptes   (juste)
    #       2 ecartes, une cause vide  -> 1 + 0 = 1 compte    (1 perdu)
    #       2 ecartes, toutes vides    -> 0 + 0 = 0 compte    (2 perdus)
    # *Le titre annoncait bien << COMPARAISON DE 2 CANDIDAT(S) >> et sa
    # ventilation en comptait zero : le total et son detail ne portaient
    # pas sur la meme assiette.*
    # ⚠️ ON NE LES RANGE PAS DANS UN SEAU EXISTANT : un ecarte sans cause
    # n'est ni un echec de critere ni une absence de prix, c'est une
    # LACUNE DE DECLARATION. La confondre avec l'une des deux ferait lire
    # une espece d'echec pour une autre -- ce que le commentaire ci-dessus
    # interdit deja pour les deux premieres.
    sans_cause = [r for r in ecartes
                  if r.cause not in (CAUSE_CRITERE, CAUSE_SANS_PRIX)]
    tete = (
        f"COMPARAISON DE {len(resultats)} CANDIDAT(S) de nature "
        f"{nature or '?'} : {len(survivants)} retenu(s), "
        f"{len(par_critere)} ecarte(s) par le critere de niveau, "
        f"{len(sans_prix)} sans prix publiable"
        + (f", {len(sans_cause)} ecarte(s) SANS CAUSE DECLAREE"
           if sans_cause else "")
        # ⚠️ LE `f` TOMBE AVEC LES SUBSTITUTIONS : ces fragments etaient
        # dans la MEME f-string que le titre ; les separer leur a fait
        # perdre leur raison d'etre des `f`, et `proprete` l'a vu (F541).
        + ". Ce qui est compare : la FREQUENCE de "
        "chaque candidat, multipliee par un modele de cout PARTAGE -- il "
        "n'existe qu'un seul modele de severite dans la chaine. Les "
        "candidats sont REAJUSTES sur la decoupe declaree au plan, et non "
        "repris d'A4, qui ajuste sur une decoupe qui lui est propre.")
    if bande is None:
        tete += (
            " /!\\ AUCUNE BANDE DE NIVEAU DECLAREE : le critere E2 est MESURE "
            "et publie, mais il n'ecarte personne. Une regle qui bloque se "
            "declare au plan, elle ne se devine pas.")
    else:
        tete += (f" Bande de niveau declaree : [{bande[0]:.4g} ; "
                 f"{bande[1]:.4g}] sur le holdout, coefficient gele sur le "
                 f"train.")
    if sans_cause:
        # ⚠️ LA LACUNE SE DIT, ELLE NE SE DEVINE PAS. Sans cette phrase, le
        # lecteur du document ne peut pas savoir POURQUOI le compte des
        # deux causes ne fait pas le compte des ecartes.
        tete += (
            f" /!\\ {len(sans_cause)} CANDIDAT(S) ECARTE(S) SANS CAUSE "
            f"DECLAREE ({', '.join(r.candidat.nom for r in sans_cause)}) : "
            f"leur exclusion n'est ni un echec du critere de niveau, ni une "
            f"absence de prix publiable. Le champ `cause` vaut sa valeur par "
            f"defaut. Sans elle, le total des candidats et la ventilation "
            f"ci-dessus ne portent pas sur la meme assiette.")
    for r in ecartes:
        niveau = ('non mesurable' if r.niveau_holdout != r.niveau_holdout
                  else f"{r.niveau_holdout:.4f}")
        tete += (f" ECARTE -- {r.candidat.nom} (niveau {niveau}) : {r.motif}.")
    return tete
