"""
=============================================================================
  ActuarIA — L'ORCHESTRATION DE LA COMPARAISON DE PRIX
=============================================================================

⚠️⚠️ POURQUOI ELLE VIT ICI ET PAS DANS LE SOCLE. Elle a besoin de la FABRIQUE
de candidats d'A4 — une direction. Le socle porte le vocabulaire, le garde de
comparabilité et la mesure E2 ; il ne remonte jamais vers une direction. C'est
le seul import de production qui l'avait fait une fois, mesuré par AST le
05/09/2026, et il a coûté 4,41 s et quatorze modules.

⚠️⚠️ LES CANDIDATS SONT RÉAJUSTÉS ICI, ET C'EST LE POINT LE PLUS IMPORTANT DU
MODULE. A4 ajuste ses six modèles sur SA propre découpe —
`train_test_split(test_size=0.20, random_state=42, shuffle=True)`, mesuré à
`a4:1782` — qui n'est **pas** celle que le plan déclare. Mesurer E2 sur le
holdout du plan avec les modèles d'A4 porterait donc sur des lignes que les
candidats ont déjà vues : l'élimination flatterait tout le monde.

  Asseoir une élimination PUBLIÉE sur une découpe non déclarée rouvrirait
  exactement `C-36`, que le lot 1 vient de fermer. Il n'y a qu'une réponse
  honnête : réajuster sur la découpe DÉCLARÉE. Coût mesuré : **5,4 s** pour
  les six candidats sur 4 000 lignes.

  *Conséquence à dire, et le document la dit : les prix comparés viennent de
  candidats réajustés sur la découpe du plan, pas des modèles d'A4. Le
  classement d'A6 reste ce qu'il est ; la comparaison de prix est son propre
  exercice, sur sa propre base déclarée.*

⚠️ SANS DÉCOUPE DÉCLARÉE, AUCUNE COMPARAISON. E2 ne peut pas se mesurer, donc
aucun prix n'est publié — et le document dit pourquoi. Publier des prix sans
le filtre reviendrait à publier des prix non filtrés.
=============================================================================
"""

from __future__ import annotations

import dataclasses
import logging

import numpy as np

from core.prix_compares import (
    CAUSE_CRITERE,
    CAUSE_SANS_PRIX,
    AdaptateurTauxFrequence,
    Candidat,
    ResultatCandidat,
    niveau_holdout,
    refuser_assiette_discordante,
    refuser_natures_melangees,
    synthese_comparaison,
)
from core.validation_tarif import indices_validation
from direction_non_vie.tarification.a4_ml.agent import (
    creer_modele_ml_pour_nom,
)

logger = logging.getLogger('actuaria.tarif.comparaison')

__all__ = ['CANDIDATS_ML', 'ComparaisonPrix', 'comparer_les_prix']

#: ⚠️⚠️ LES SIX FAMILLES D'A4, ET LEUR NATURE DÉCLARÉE. Toutes de nature
#: `frequence` : la fabrique les enveloppe dans `_ModeleFrequenceExposition`
#: sur une cible de comptage, et leur `predict` rend le TAUX λ(X).
#:
#: ⚠️ `xgboost_tweedie` PORTE UN NOM TROMPEUR et il est déclaré pour ce qu'il
#: EST : son objectif est `reg:tweedie`, mais il est ajusté sur `nb_sinistres`
#: — c'est une fréquence à perte Tweedie, pas une prime pure. *Le seul vrai
#: modèle de prime pure du dépôt est le `tweedie` d'A3, et il n'est pas ici.*
CANDIDATS_ML = (
    Candidat('gbm', 'frequence', 'A4'),
    Candidat('xgboost', 'frequence', 'A4'),
    Candidat('xgboost_tweedie', 'frequence', 'A4'),
    Candidat('lightgbm', 'frequence', 'A4'),
    Candidat('catboost', 'frequence', 'A4'),
    Candidat('lineaire_regularise', 'frequence', 'A4'),
)


@dataclasses.dataclass(frozen=True)
class ComparaisonPrix:
    """Le résultat de la comparaison — ce qui va au document signé."""
    resultats: tuple
    nature: str
    bande: tuple | None
    synthese: str
    motif_absence: str = ''

    @property
    def survivants(self) -> tuple:
        return tuple(r for r in self.resultats if not r.ecarte)

    @property
    def ecartes(self) -> tuple:
        return tuple(r for r in self.resultats if r.ecarte)


def _refuser_prix_absurde(nom: str, pred) -> str:
    """Un prix non fini ou négatif est un refus, pas une valeur basse.

    ⚠️⚠️ MESURÉ, PAS SUPPOSÉ. Une sonde du 08/09/2026 a obtenu `inf` d'un
    candidat pénalisé sur une matrice de design assemblée à la main. Un modèle
    qui explose hors du domaine appris ne produit pas un prix cher : il ne
    produit pas de prix. *Le laisser passer publierait un nombre qui n'en est
    pas un.*
    """
    p = np.asarray(pred, dtype=float)
    if not np.all(np.isfinite(p)):
        return (f"le candidat rend {int((~np.isfinite(p)).sum())} "
                f"prediction(s) NON FINIE(S)")
    if np.any(p < 0):
        return (f"le candidat rend {int((p < 0).sum())} prediction(s) "
                f"NEGATIVE(S) : une frequence ne peut pas etre negative")
    return ''


def comparer_les_prix(tarif, portefeuille, plan, *, bande=None,
                      candidats=CANDIDATS_ML) -> ComparaisonPrix:
    """Compare les prix des candidats, filtrés par E2.

    ⚠️ `tarif` est le `TarifNonVie` de PRODUCTION : il fournit la matrice de
    design, les colonnes retenues, l'écrêtement, le modèle de coût PARTAGÉ et
    le coefficient d'équilibre. **Rien de tout cela ne bouge** — seul le
    modèle de fréquence est remplacé, candidat par candidat.
    """
    nature = refuser_natures_melangees(candidats)
    # ⚠️⚠️ L'ASSIETTE D'ABORD, AVANT MEME LA DECOUPE. Mesurer une decoupe sur
    # des lignes que le tarif n'a pas vues n'aurait aucun sens : les indices
    # porteraient sur un autre portefeuille que celui qui a produit les
    # modeles. *Le premier appelant de production remettait ici le
    # portefeuille d'AVANT la couche qualite ; le verdict publie basculait
    # entierement -- 0 survivant contre 1 a 622 391,70 EUR, mesure le
    # 08/09/2026.*
    discordance = refuser_assiette_discordante(tarif, portefeuille)
    if discordance:
        return ComparaisonPrix(
            resultats=(), nature=nature, bande=bande, synthese='',
            motif_absence=discordance)
    decoupe = getattr(plan, 'decoupe_validation', None)
    paire = indices_validation(portefeuille, decoupe)
    if paire is None:
        return ComparaisonPrix(
            resultats=(), nature=nature, bande=bande, synthese='',
            motif_absence=(
                "AUCUNE COMPARAISON DE PRIX : le plan ne declare pas de "
                "decoupe de validation, donc le critere de niveau ne peut pas "
                "etre mesure. Publier des prix sans ce filtre reviendrait a "
                "publier des prix non filtres. Declarez `decoupe_validation` "
                "au plan."))
    tr, te = paire

    Xc = tarif._design(portefeuille)
    colonnes = list(tarif.features)
    y = portefeuille[plan.cible_frequence].to_numpy(dtype=float)
    expo = portefeuille[plan.exposition].to_numpy(dtype=float)
    X = Xc[colonnes]

    resultats = []
    for candidat in candidats:
        try:
            modele = creer_modele_ml_pour_nom(candidat.nom,
                                              plan.cible_frequence)
            modele.fit(X.iloc[tr], y[tr], sample_weight=expo[tr])
            p_tr = np.asarray(modele.predict(X.iloc[tr]), dtype=float)
            p_te = np.asarray(modele.predict(X.iloc[te]), dtype=float)
        except Exception as erreur:                            # noqa: BLE001
            logger.warning("Candidat %s non ajuste : %s", candidat.nom, erreur)
            resultats.append(ResultatCandidat(
                candidat=candidat, k_train=float('nan'),
                niveau_holdout=float('nan'), ecarte=True,
                motif=f"non ajustable ({type(erreur).__name__})",
                cause=CAUSE_SANS_PRIX))
            continue

        absurde = _refuser_prix_absurde(candidat.nom,
                                        np.concatenate([p_tr, p_te]))
        if absurde:
            resultats.append(ResultatCandidat(
                candidat=candidat, k_train=float('nan'),
                niveau_holdout=float('nan'), ecarte=True, motif=absurde,
                cause=CAUSE_SANS_PRIX))
            continue

        k, niveau = niveau_holdout(p_tr, y[tr], expo[tr],
                                   p_te, y[te], expo[te])
        # ⚠️ SANS BANDE DECLAREE, ON MESURE ET ON PUBLIE -- on n'ecarte pas.
        # Une regle qui bloque se declare au plan, elle ne se devine pas.
        ecarte, motif, cause = False, '', ''
        if bande is not None and np.isfinite(niveau):
            if not (bande[0] <= niveau <= bande[1]):
                ecarte, cause = True, CAUSE_CRITERE
                motif = (f"niveau hors bande declaree "
                         f"[{bande[0]:.4g} ; {bande[1]:.4g}] : le calage du "
                         f"train ne tient pas sur le holdout")
        elif not np.isfinite(niveau):
            ecarte, cause = True, CAUSE_SANS_PRIX
            motif = 'niveau non mesurable sur ce portefeuille'

        somme = None
        if not ecarte:
            # ⚠️ LE PRIX, PAR LE MEME CHEMIN QUE LA PRODUCTION. Seul le modele
            # de frequence change : l'ecretement, le modele de cout et le
            # coefficient d'equilibre restent ceux du tarif signe.
            faux = dataclasses.replace(
                tarif,
                glm_frequence=AdaptateurTauxFrequence(modele, colonnes,
                                                      candidat))
            somme = float(
                faux.predire_portefeuille(portefeuille)['prime_pure'].sum())
        resultats.append(ResultatCandidat(
            candidat=candidat, k_train=k, niveau_holdout=niveau,
            ecarte=ecarte, motif=motif, cause=cause,
            somme_prime_pure=(None if somme is None else round(somme, 2))))

    resultats = tuple(resultats)
    return ComparaisonPrix(
        resultats=resultats, nature=nature, bande=bande,
        synthese=synthese_comparaison(resultats, bande, nature))
