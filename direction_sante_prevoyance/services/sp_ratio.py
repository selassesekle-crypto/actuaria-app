"""
sp_ratio.py — le ratio sinistres sur primes, tel que la place le définit.

LA DÉFINITION, ET SA SOURCE
    « Ce ratio, appelé P/C pour prestations sur cotisations ou S/P pour
      sinistres sur primes, rapporte simplement la charge de sinistres au
      montant des cotisations. Si ce ratio est supérieur à 100 %, le régime
      est déficitaire car les cotisations ne suffisent pas à couvrir la somme
      des prestations et des provisions. »
    — V. PAVARD, « Ajustement du provisionnement du risque arrêt de travail
      pour optimiser le pilotage des régimes collectifs », mémoire ENSAE
      Paris / Institut des Actuaires, 13/03/2023, p. 30.

Deux points que cette définition fixe, et que le code ne respectait pas :
  · le NUMÉRATEUR est une charge de sinistres — prestations versées **plus**
    provisions constituées, rattachées à l'exercice ;
  · le DÉNOMINATEUR est un montant de cotisations, pas un taux.

LES DEUX DÉFAUTS FERMÉS

D07 — P3 construisait son loss ratio ainsi :
        taux_cot = result_p1["taux_cotisation_pct"] / 100   # % du SALAIRE
        lr_att   = taux_cot * 0.80
    Un taux de cotisation multiplié par 0,80 ne produit pas un rapport de
    sinistres à primes : cela produit 80 % d'un taux, une grandeur d'une autre
    dimension. Mesuré : au taux nominal de 1,51 %, l'agent publiait un
    **Loss Ratio de 1,21 %**. Résolution inverse : il faudrait un taux de
    cotisation de **125 % du salaire** pour atteindre 100 %. Ce n'était pas un
    cas limite, c'était le régime permanent.

D17 — S1 calculait :
        lr_attendu = prime_pure / max(prime_comm, 1)
    Or `prime_comm = prime_pure × (1 + chargement)` quelques lignes plus haut :
    le rapport élimine la prime pure et ne laisse que le chargement. Mesuré :
    `lr_attendu` vaut `1/(1+chargement)` à **1e−16 près**, sur 256
    configurations croisant l'âge, la taille, la garantie et la sinistralité.
    Un indicateur de pilotage qui ne dépend d'aucune sinistralité ne pilote rien.

D06 / H5 — le garde-fou ne bornait QUE PAR LE HAUT. Un LR de 1,21 % passait
    donc sans difficulté. C'est la borne BASSE qui est le vrai correctif : un
    S/P de 1,2 % est aussi invraisemblable qu'un S/P de 120 %.
"""

__all__ = [
    "LR_CTIP_ITT_MARCHE", "LR_PLANCHER_VRAISEMBLABLE", "LR_CIBLE_MAX",
    "apriori_volume_mature", "charge_sinistres", "loss_ratio",
    "statut_loss_ratio",
]

# Reference de marche employee FAUTE DE SINISTRES OBSERVES, jamais a la place.
# Elle est nommee dans la sortie pour qu un lecteur puisse la contester.
LR_CTIP_ITT_MARCHE = 0.68

# Bornes de VRAISEMBLANCE, et non de rentabilite. Un S/P hors de cet
# intervalle signale une erreur d assiette avant de signaler un resultat.
LR_PLANCHER_VRAISEMBLABLE = 0.30
LR_CIBLE_MAX = 0.90


def charge_sinistres(prestations_versees, provisions_constituees=0.0):
    """Charge de sinistres = prestations versées + provisions constituées.

    C'est le numérateur du S/P au sens de la définition de place. Omettre les
    provisions revient à ne compter que la part déjà réglée et à sous-estimer
    la sinistralité d'un exercice, particulièrement en arrêt de travail où la
    part provisionnée est prépondérante.
    """
    return max(0.0, float(prestations_versees or 0.0)) \
        + max(0.0, float(provisions_constituees or 0.0))


def loss_ratio(prestations_versees, cotisations,
               provisions_constituees=0.0, lr_reference=None):
    """Rend `(loss_ratio, source)`.

    La source voyage AVEC la valeur : un lecteur doit savoir si le chiffre
    vient de sinistres observés ou d'une référence de marché.

    Parameters
    ----------
    prestations_versees : float
        Prestations réglées sur l'exercice.
    cotisations : float
        Cotisations acquises. Le DÉNOMINATEUR — jamais un taux.
    provisions_constituees : float
        Provisions rattachées à l'exercice. Voir `charge_sinistres`.
    lr_reference : float, optionnel
        Valeur à retenir si aucune sinistralité n'est observable.
    """
    cot = float(cotisations or 0.0)
    charge = charge_sinistres(prestations_versees, provisions_constituees)

    if cot > 0 and charge > 0:
        return charge / cot, "sinistres observes (prestations + provisions)"

    reference = LR_CTIP_ITT_MARCHE if lr_reference is None else float(lr_reference)
    return reference, (
        "reference de marche CTIP %.0f%% — AUCUN sinistre observe"
        % (reference * 100))


def statut_loss_ratio(lr):
    """Statut d'un S/P, borné DES DEUX CÔTÉS.

    ⚠️ La borne basse est le correctif. L'ancien garde-fou ne testait que
    `lr <= 0,90` : un loss ratio de 1,21 % — mesuré en production — passait
    donc pour validé. Un S/P trop bas ne signale pas un régime florissant,
    il signale une erreur d'assiette.
    """
    try:
        v = float(lr)
    except (TypeError, ValueError):
        return "NON MESURÉE", "loss ratio non numérique"

    if v < LR_PLANCHER_VRAISEMBLABLE:
        return "NON VALIDÉE", (
            "S/P = %.1f%% < %.0f%% — invraisemblable, vérifier l'assiette "
            "(charge de sinistres et cotisations)"
            % (v * 100, LR_PLANCHER_VRAISEMBLABLE * 100))
    if v <= LR_CIBLE_MAX:
        return "VALIDÉE", "S/P = %.1f%% dans [%.0f%%, %.0f%%]" % (
            v * 100, LR_PLANCHER_VRAISEMBLABLE * 100, LR_CIBLE_MAX * 100)
    if v <= 1.00:
        return "À JUSTIFIER", "S/P = %.1f%% dans ]%.0f%%, 100%%]" % (
            v * 100, LR_CIBLE_MAX * 100)
    return "NON VALIDÉE", (
        "S/P = %.1f%% > 100%% — regime deficitaire" % (v * 100))


# =============================================================================
#  A PRIORI DU BORNHUETTER-FERGUSON
# =============================================================================

def apriori_volume_mature(dernier_diag, pct_developpe, n, loss_ratio_apriori,
                          nb_annees_matures=3):
    """A priori BF construit sur le VOLUME OBSERVE, et non sur l ultime projete.

    LE DEFAUT FERME (D09)
    En l absence de primes exogenes, l a priori valait `ult_cl * lr` --
    l ultime projete par Chain Ladder de l annee meme qu on cherche a estimer.
    Le BF degenerait alors en `lr x CL`, identiquement. Mesure :
    **BF / CL = 0,680000 exactement**, soit le loss ratio a priori, et
    **Mack - CL = 0,000000**. Trois methodes publiees, une seule valeur -- et
    un « CV inter-methodes » de 16,89 % calcule sur trois copies de la meme
    chose, presente comme une mesure d incertitude de modele.

    Un contre-test l avait confirme : en fournissant de vraies primes acquises,
    le rapport tombait a 0,9922 -- une valeur qui VARIE avec les donnees, comme
    doit le faire une methode independante. Le chemin correct existait deja ;
    il n etait simplement jamais emprunte.

    Returns
    -------
    (numpy.ndarray, str) : le vecteur d a priori, et sa provenance.
    """
    import numpy as np

    k = max(1, min(int(nb_annees_matures), int(n)))
    observes = [
        float(dernier_diag[i]) / float(pct_developpe[i])
        for i in range(k)
        if float(pct_developpe[i]) > 0
    ]
    if not observes:
        return (np.array([float(dernier_diag[i]) for i in range(n)]),
                "diagonale observee (degrade — aucune annee mature)")

    socle = sum(observes) / len(observes)
    return (np.full(n, socle),
            "volume moyen des %d annee(s) mature(s) — independant de l ultime "
            "projete" % len(observes))
