"""
sp_ani.py — le panier de soins minimal, avec l'UNITÉ de chaque seuil.

LE DÉFAUT FERMÉ (D19, D34, D05)
`ANI_PANIER_MIN` portait quatre nombres nus — 30, 100, 75, 100 — comparés à une
charge EN EUROS, et commentés en POURCENTAGE DE BASE DE REMBOURSEMENT :

    ANI_PANIER_MIN = {
        "medecine":        30.0,   # >= 100% BR consultations
        "dentaire":        75.0,   # >= 125% BR soins dentaires
    }
    conforme = charge_mutuelle[poste] >= ANI_PANIER_MIN[poste]

Les deux lectures sont incompatibles : soit les seuils sont des euros et le
commentaire est faux, soit l'inverse et la comparaison est fausse. Mesure sur
24 configurations (6 profils d'âge × 4 niveaux de garantie) : la charge
mutuelle du poste médecine ressort à **7,52 €** face à un seuil de 30.
**0 configuration conforme sur 24**, et le RAG ROUGE pour tout contrat
collectif testé. L'erreur ACCUSE À TORT, dans 100 % des cas.

⚠️ ET DEUX AGENTS DU MÊME MODULE RÉPONDAIENT L'INVERSE (D34). S1 appliquait ces
seuils en euros ; SP-REG3 appliquait ses propres règles en supposant par défaut
un contrat collectif. Même portefeuille, même exécution, deux verdicts
réglementaires opposés, tous deux publiés, et aucun agent pour les rapprocher.

LA RÈGLE, ET SA SOURCE
Le panier minimal est **hétérogène par nature** : certaines lignes sont des
taux, d'autres des forfaits en euros. C'est précisément ce que quatre nombres
nus ne pouvaient pas exprimer.

  · intégralité du **ticket modérateur** sur les consultations, actes et
    prestations remboursables par l'assurance maladie            → un TAUX
  · totalité du **forfait journalier hospitalier**               → EUROS/jour
  · frais dentaires (prothèses, orthodontie) : **125 % du tarif
    conventionnel**                                              → un TAUX
  · frais d'optique, forfait par période de 2 ans : minimum
    **100 €** (correction simple), **150 €** voire **200 €**
    (correction complexe)                                        → EUROS

Source réglementaire : art. L911-7 et D911-1 du code de la Sécurité sociale
(décret n° 2014-1025 du 8 septembre 2014), pris en application de l'ANI du
11 janvier 2013. Le contenu du panier a été vérifié le 12/09/2026 contre un
mémoire d'actuaire du Centre d'Études Actuarielles (J.-P. MOINEAU, admission
à l'Institut des Actuaires, 27/04/2016), conservé HORS DU DÉPÔT.

⛔ CE QUE CE MODULE REFUSE DE FAIRE, ET C'EST DÉLIBÉRÉ.
Le **forfait journalier hospitalier** est un montant PAR JOUR d'hospitalisation.
Le modèle de tarification ne porte ni durée de séjour ni nombre de journées :
la ligne n'est donc pas mesurable ici, et elle rend `NON_MESURABLE` — pas
« conforme », pas « non conforme ». Inventer une durée pour pouvoir conclure
serait fabriquer de l'actuariat, et c'est exactement ce que le défaut d'origine
faisait dans l'autre sens.

Un poste NON MESURABLE ne rend pas le contrat non conforme : il rend le verdict
global INCOMPLET, et le document le dit.
"""

__all__ = [
    "CONFORME", "NON_CONFORME", "NON_MESURABLE", "HORS_CHAMP",
    "OPTIQUE_FORFAIT_SIMPLE_EUR", "PANIER", "SEUIL_PATRONAL_SANTE",
    "part_patronale_conforme", "verifier_panier",
]

CONFORME = "CONFORME"
NON_CONFORME = "NON CONFORME"
NON_MESURABLE = "NON MESURABLE"
HORS_CHAMP = "HORS CHAMP"

#: Forfait optique minimal, correction simple, par equipement (periode de 2 ans).
OPTIQUE_FORFAIT_SIMPLE_EUR = 100.0

#: Financement patronal minimal — art. L911-7 CSS. ⚠️ FRAIS DE SANTE SEULEMENT.
SEUIL_PATRONAL_SANTE = 0.50

#: Chaque ligne porte son UNITE et sa BASE. C'est tout le correctif.
#: `base` dit COMMENT le seuil se calcule a partir des donnees du poste :
#:   "ticket_moderateur" -> cout_acte - remb_ss
#:   "pct_tarif"         -> facteur x cout_acte - remb_ss
#:   "forfait_eur"       -> un montant, tel quel
#:   "non_mesurable"     -> le modele ne porte pas la grandeur necessaire
PANIER = {
    "medecine": {
        "base": "ticket_moderateur", "facteur": 1.0, "unite": "EUR",
        "regle": "integralite du ticket moderateur",
        "reference": "art. D911-1 CSS 1o",
    },
    "pharmacie": {
        "base": "ticket_moderateur", "facteur": 1.0, "unite": "EUR",
        "regle": "integralite du ticket moderateur",
        "reference": "art. D911-1 CSS 1o",
    },
    "hospitalisation": {
        "base": "non_mesurable", "facteur": None, "unite": "EUR/jour",
        "regle": "totalite du forfait journalier hospitalier",
        "reference": "art. D911-1 CSS 2o",
        "motif_non_mesurable": (
            "le forfait journalier se compte PAR JOUR d hospitalisation ; le "
            "modele de tarification ne porte ni duree de sejour ni nombre de "
            "journees"),
    },
    "dentaire": {
        "base": "pct_tarif", "facteur": 1.25, "unite": "EUR",
        "regle": "125 % du tarif conventionnel (protheses, orthodontie)",
        "reference": "art. D911-1 CSS 3o",
    },
    "optique": {
        "base": "forfait_eur", "facteur": OPTIQUE_FORFAIT_SIMPLE_EUR,
        "unite": "EUR",
        "regle": "forfait minimal 100 EUR (correction simple), par periode "
                 "de 2 ans",
        "reference": "art. D911-1 CSS 4o",
    },
}


def _nombre(source, cle):
    try:
        return float(source.get(cle, 0) or 0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def _seuil_du_poste(regle, infos):
    """Rend `(seuil, mesurable, explication)` — le seuil DANS L'UNITE de la charge.

    C'est la fonction qui ferme D19 : le seuil n'est plus un nombre nu, il se
    CALCULE à partir de la base déclarée et des données du poste.
    """
    base = regle["base"]
    if base == "non_mesurable":
        return None, False, regle.get("motif_non_mesurable", "")

    cout = _nombre(infos, "cout_acte") or _nombre(infos, "cout_moyen")
    remb = _nombre(infos, "remb_ss")

    if base == "forfait_eur":
        return float(regle["facteur"]), True, (
            "forfait de %.0f EUR par equipement" % regle["facteur"])

    if cout <= 0:
        return None, False, (
            "le cout de l acte est absent : le seuil ne peut pas etre calcule")

    seuil = regle["facteur"] * cout - remb
    seuil = max(seuil, 0.0)
    if base == "ticket_moderateur":
        explication = ("ticket moderateur = %.2f - %.2f = %.2f EUR"
                       % (cout, remb, seuil))
    else:
        explication = ("%.0f %% du tarif moins le remboursement SS = "
                       "%.2f x %.2f - %.2f = %.2f EUR"
                       % (regle["facteur"] * 100, regle["facteur"], cout,
                          remb, seuil))
    return seuil, True, explication


def verifier_panier(postes, contrat="collectif"):
    """Vérifie le panier minimal, poste par poste, dans la bonne unité.

    Rend un dictionnaire portant `statut`, `complet`, `detail` et `note`.

    `statut` vaut `HORS_CHAMP` pour un contrat individuel — l'obligation est
    attachée au contrat collectif obligatoire (art. L911-7 CSS). Ce n'est PAS
    « conforme » : un contrat hors champ n'a rien satisfait, il n'est pas
    soumis. La nuance atteint le document.
    """
    postes = postes or {}
    if contrat != "collectif":
        return {
            "statut": HORS_CHAMP,
            "conforme": None,
            "complet": True,
            "contrat": contrat,
            "detail": {},
            "note": ("Contrat %s : le panier minimal de l art. D911-1 CSS "
                     "s applique au contrat COLLECTIF OBLIGATOIRE (art. L911-7 "
                     "CSS). Aucun verdict de conformite n est emis." % contrat),
        }

    detail = {}
    manques, non_mesures = [], []
    for poste, regle in PANIER.items():
        if poste not in postes or not isinstance(postes[poste], dict):
            detail[poste] = {
                "statut": NON_MESURABLE, "seuil": None, "charge": None,
                "regle": regle["regle"], "reference": regle["reference"],
                "explication": "poste absent du portefeuille tarife",
            }
            non_mesures.append(poste)
            continue

        infos = postes[poste]
        charge = _nombre(infos, "charge_mutuelle")
        seuil, mesurable, explication = _seuil_du_poste(regle, infos)

        if not mesurable:
            statut = NON_MESURABLE
            non_mesures.append(poste)
        elif charge >= seuil:
            statut = CONFORME
        else:
            statut = NON_CONFORME
            manques.append(poste)

        detail[poste] = {
            "statut": statut,
            "seuil": None if seuil is None else round(seuil, 2),
            "charge": round(charge, 2),
            "unite": regle["unite"],
            "regle": regle["regle"],
            "reference": regle["reference"],
            "explication": explication,
        }

    complet = not non_mesures
    if manques:
        statut = NON_CONFORME
        note = ("Panier minimal non atteint sur : %s (art. D911-1 CSS)"
                % ", ".join(sorted(manques)))
    elif complet:
        statut = CONFORME
        note = "Panier minimal atteint sur tous les postes mesurables"
    else:
        statut = CONFORME
        note = ("Panier minimal atteint sur les postes MESURABLES ; %s "
                "reste(nt) non mesurable(s) : le verdict est INCOMPLET"
                % ", ".join(sorted(non_mesures)))

    return {
        "statut": statut,
        "conforme": statut == CONFORME,
        "complet": complet,
        "contrat": contrat,
        "non_mesurables": sorted(non_mesures),
        "detail": detail,
        "note": note,
    }


def part_patronale_conforme(part_patronale, nature="frais_de_sante"):
    """Le financement patronal, CALCULÉ, et seulement là où le texte s'applique.

    LE DÉFAUT FERMÉ (D05)
    P1 publiait `part_patronale = prime_comm * 0.60` et, à côté, la chaîne
    CONSTANTE « Part patronale 60 % → Conforme ANI 2013 ✅ ». Le taux était un
    littéral, la mention n'était jamais calculée ni conditionnée : quelle que
    soit la répartition réelle du contrat client, le document publiait
    « 60 % — conforme ». Mesuré en faisant varier la prime, la garantie et la
    population : la chaîne ne bougeait jamais.

    ⚠️ ET L'AFFIRMATION DÉPASSAIT LE TEXTE. L'art. L911-7 CSS impose un
    financement patronal d'au moins 50 % **en frais de santé**. L'étendre à la
    prévoyance est une extension que le texte ne fait pas — sur un sujet où un
    contrôleur vérifiera la source. Pour la prévoyance, cette fonction rend
    donc `HORS_CHAMP`, et non « conforme ».

    Rend `(statut, mention)`.
    """
    try:
        part = float(part_patronale)
    except (TypeError, ValueError):
        return NON_MESURABLE, (
            "part patronale illisible : aucun verdict de conformite")

    if nature != "frais_de_sante":
        return HORS_CHAMP, (
            "Financement patronal %.0f %%. L obligation de 50 %% de l art. "
            "L911-7 CSS porte sur les FRAIS DE SANTE ; l etendre a la "
            "prevoyance serait une extension que le texte ne fait pas. "
            "Aucun verdict de conformite n est emis." % (part * 100))

    if part >= SEUIL_PATRONAL_SANTE:
        return CONFORME, (
            "Financement patronal %.0f %% >= 50 %% — art. L911-7 CSS"
            % (part * 100))
    return NON_CONFORME, (
        "Financement patronal %.0f %% < 50 %% — art. L911-7 CSS non respecte"
        % (part * 100))
