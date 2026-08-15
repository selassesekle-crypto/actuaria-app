# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 : « NON VIDE » N'EST PAS « RENSEIGNÉ »
=============================================================================

⚠️⚠️ POURQUOI CE MODULE EXISTE, ET IL A ÉTÉ MESURÉ, PAS SUPPOSÉ. Les cinq
portes de signature du chantier vérifiaient qu'un champ n'était pas VIDE. Un
producteur de données a livré une déclaration d'ajustement pour risque dont
le signataire s'appelait littéralement `A_RENSEIGNER` et l'arrêté
`A_RENSEIGNER`, avec un statut `A_REMPLACER` et l'avertissement « taux
INVENTÉS ». **Elle a été ACCEPTÉE intégralement.**

    AjustementRisque(montant=1253.29, niveau_confiance='0.75',
                     methode='quantile', arrete='A_RENSEIGNER',
                     actuaire_resp='A_RENSEIGNER')

⚠️ ET AJOUTER UN CONTRÔLE DE « STATUT » N'AURAIT PAS SUFFI. Le signataire
fictif serait passé quand même. Le défaut de fond n'est pas un champ
manquant : c'est que `not valeur.strip()` attrape `''` et les espaces, et
laisse passer `A_RENSEIGNER`, `TBD`, `N/A`, `XXX`, `TODO`.

⚠️ CE QUI REND CE DÉFAUT GRAVE : ces portes sont le mécanisme sur lequel
repose CHAQUE décision d'entité de ce chantier — §54, §59 a), B66 d),
§36 b), §37, le déclenchement du §57, la base de la prime. Une porte
perméable les rend toutes perméables.

⚠️ LE PIÈGE INVERSE A ÉTÉ MESURÉ AVANT DE POSER LE CONTRÔLE. Un refus trop
large bloquerait des valeurs légitimes. Le détecteur a été confronté à 21
valeurs réellement employées dans le chantier — noms d'actuaires, arrêtés,
méthodes, sources, niveaux de confiance, portefeuilles, devises — et à 21
formes de remplissage fictif : ZÉRO rejet à tort, ZÉRO échappement.

⚠️ ET LA COMPARAISON PORTE SUR LA VALEUR ENTIÈRE, JAMAIS SUR UNE
SOUS-CHAÎNE. Sinon `nan` condamnerait « financement », `x` condamnerait
« Xavier », `na` condamnerait « Nanterre ». Vérifié sur ces trois cas et
cinq autres.
=============================================================================
"""

import re
import unicodedata

#: Les formes de remplissage fictif refusées. ⚠️ LISTE FERMÉE ET COMPARÉE À
#: LA VALEUR ENTIÈRE APRÈS NORMALISATION — jamais en sous-chaîne.
PLACEHOLDERS = frozenset({
    'a renseigner', 'a remplacer', 'a completer', 'a definir', 'a determiner',
    'tbd', 'todo', 'na', 'n a', 'nc', 'xxx', 'yyy', 'zzz', '?',
    'null', 'none', 'nan', 'vide', 'inconnu', 'non renseigne', 'non defini',
    'to be defined', 'to be determined', 'placeholder', 'fixme', 'x', '0',
})

MOTIF_NON_RENSEIGNE = 'champ_non_renseigne'
MOTIF_STATUT_NON_SIGNE = 'declaration_non_signee'
MOTIF_DECLARANT_NON_HABILITE = 'declarant_non_habilite'

#: ⚠️⚠️ LES MARQUEURS D'UNE NON-SIGNATURE DÉCLARÉE — ET ILS SE CHERCHENT EN
#: SOUS-CHAÎNE, contrairement à `PLACEHOLDERS`. La différence tient au champ :
#: un STATUT est une étiquette courte et catégorielle, un CONTENU est de la
#: prose. Chercher « à remplacer » dans une prose refuserait « note de méthode
#: à remplacer par la version signée », qui est une déclaration légitime ;
#: dans un statut, le même mot désigne le statut lui-même.
#:
#: ⚠️ CALIBRAGE MESURÉ, ET UNE VARIANTE PLUS FINE A ÉTÉ REJETÉE. Une règle à
#: deux listes — un marqueur refuse SAUF si un mot de signature l'accompagne —
#: donnait 0 faux rejet sur les 32 valeurs ordinaires, et s'est effondrée à
#: 8 FAUX ACCEPTÉS SUR 8 dès qu'on l'a attaquée : « signée, mais provisoire »,
#: « validée à titre de démonstration », « signée - jeu de test » passaient
#: toutes. Elle ne paraissait propre que sur les exemples qui l'avaient
#: construite. La sous-chaîne, plus bête, refuse sur la seule présence du
#: marqueur et tient sous l'attaque.
#:
#: ⚠️ SON PRIX EST NOMMÉ : un statut mentionnant une version antérieure
#: remplacée — « signée après remplacement de la version provisoire » — est
#: refusé à tort. Le refus le dit et invite à reformuler. Un faux refus se
#: voit et se corrige ; un faux accepté laisse passer une déclaration non
#: signée sans laisser de trace.
MARQUEURS_DE_NON_SIGNATURE = (
    'demonstration', 'demo', 'a remplacer', 'provisoire', 'brouillon',
    'draft', 'test', 'exemple', 'projet', 'a valider', 'non signe',
    'non signee', 'specimen', 'maquette', 'simulation',
)

#: ⚠️⚠️ LA QUALITÉ DU DÉCLARANT EST UN SECOND CHAMP, ET C'EST LA TROUVAILLE
#: DE CE CONTRÔLE. Le statut dit SI une déclaration est signée ; il ne dit
#: JAMAIS PAR QUI. « Signée par le producteur, non par l'entité » franchit
#: tous les marqueurs — et c'est le cas exact du jeu de démonstration reçu,
#: dont chaque ligne porte « le producteur n'est PAS l'entité au sens du
#: §36 ». Or §36 remet la décision à L'ENTITÉ : une déclaration signée par un
#: tiers est signée, et sans valeur ici.
#:
#: ⚠️ ELLE SE DÉCLARE, ELLE NE SE DEVINE PAS — même leçon que l'élection du
#: modèle au §70A : lire la qualité dans une prose serait deviner.
QUALITE_ENTITE = 'ENTITE'
QUALITE_TIERS = 'TIERS'
QUALITES = (QUALITE_ENTITE, QUALITE_TIERS)


def normaliser(valeur) -> str:
    """La valeur, sans accents, sans casse, séparateurs unifiés.

    ⚠️ `A_RENSEIGNER`, `à renseigner`, `A-RENSEIGNER` et `a  renseigner`
    doivent se ramener à la même forme, sinon le contrôle se contourne par
    la typographie.
    """
    s = unicodedata.normalize('NFKD', str(valeur or ''))
    s = s.encode('ascii', 'ignore').decode()
    s = re.sub(r'[_\-/\\.?]+', ' ', s.lower()).strip()
    return re.sub(r'\s+', ' ', s)


def est_renseigne(valeur) -> bool:
    """Vrai si la valeur dit quelque chose. ⚠️ VIDE ET FICTIF SONT ÉGAUX ICI.

    Une chaîne vide et `A_RENSEIGNER` désignent la même chose — l'absence —
    et le second est le plus dangereux des deux, parce qu'il a l'apparence
    d'une réponse.
    """
    n = normaliser(valeur)
    return bool(n) and n not in PLACEHOLDERS


def exiger(valeur, champ: str, exigence: str, erreur):
    """Rend la valeur nettoyée, ou lève `erreur` en disant ce qui manque.

    ⚠️ `erreur` EST PASSÉE EN PARAMÈTRE pour que ce module n'importe rien :
    chaque porte lève SON type de refus, et celui-ci ne connaît aucune
    d'elles. Le sens de la dépendance compte — un contrôle transversal qui
    connaîtrait ses appelants deviendrait leur maître.
    """
    if est_renseigne(valeur):
        return str(valeur).strip()
    vu = normaliser(valeur)
    raison = ('vide' if not vu
              else f"« {str(valeur).strip()} » — une forme de remplissage "
                   f"fictif, pas une réponse")
    raise erreur(
        MOTIF_NON_RENSEIGNE,
        f"« {champ} » n'est pas renseigné : {raison}. {exigence} "
        f"⚠️ « NON VIDE » N'EST PAS « RENSEIGNÉ » : un champ portant "
        f"`A_RENSEIGNER` ou `TBD` a l'apparence d'une réponse et n'en est "
        f"pas une. Cette porte a déjà laissé passer une déclaration signée "
        f"« A_RENSEIGNER ».")


def exiger_declaration_opposable(*, statut, declarant, qualite, erreur,
                                 objet: str = 'cette déclaration') -> str:
    """DEUX contrôles distincts, parce que ce sont deux faits distincts.

    ⚠️ LE STATUT DIT SI C'EST SIGNÉ, LA QUALITÉ DIT PAR QUI. Aucun des deux
    ne se déduit de l'autre : un jeu de démonstration porte un statut qui le
    dit, mais une déclaration parfaitement signée par un prestataire porte un
    statut irréprochable et reste sans valeur au sens du §36, qui remet la
    décision à L'ENTITÉ.

    ⚠️ CE QUE CE CONTRÔLE NE PEUT PAS FAIRE, et il faut le lire avant de s'y
    fier : il attrape une non-signature DÉCLARÉE et une qualité DÉCLARÉE. Il
    ne peut pas attraper un statut qui ment. Un contrôle qui ne dit pas sa
    portée se fait surévaluer.

    Rend le motif à faire descendre avec tout résultat qui en dépend.
    """
    if not est_renseigne(statut):
        raise erreur(
            MOTIF_STATUT_NON_SIGNE,
            f"{objet} ne porte aucun statut (reçu {statut!r}). Une "
            f"déclaration sans statut n'est pas une déclaration signée : "
            f"elle est une déclaration dont on ignore si elle l'est.")

    n = normaliser(statut)
    marqueurs = sorted(m for m in MARQUEURS_DE_NON_SIGNATURE if m in n)
    if marqueurs:
        raise erreur(
            MOTIF_STATUT_NON_SIGNE,
            f"le statut de {objet} est « {statut} » : il porte "
            f"{len(marqueurs)} marqueur(s) de non-signature "
            f"({', '.join(marqueurs)}). Une déclaration provisoire, de "
            f"démonstration ou à remplacer ne peut pas fonder un montant "
            f"publié. ⚠️ Si votre statut mentionne une version ANTÉRIEURE "
            f"remplacée, reformulez-le sans le marqueur : ce contrôle refuse "
            f"sur la présence du mot, faute de pouvoir lire une intention.")

    if qualite not in QUALITES:
        raise erreur(
            MOTIF_DECLARANT_NON_HABILITE,
            f"la qualité du déclarant de {objet} n'est pas déclarée (reçu "
            f"{qualite!r}, attendu l'une de {QUALITES}). ⚠️ LE STATUT NE LA "
            f"PORTE PAS : il dit si la déclaration est signée, jamais PAR "
            f"QUI. La deviner dans une prose serait deviner.")
    if not est_renseigne(declarant):
        raise erreur(
            MOTIF_DECLARANT_NON_HABILITE,
            f"la qualité « {qualite} » est déclarée pour {objet}, mais le "
            f"déclarant n'est pas nommé (reçu {declarant!r}). Une qualité "
            f"sans nom n'est pas opposable.")
    if qualite == QUALITE_TIERS:
        raise erreur(
            MOTIF_DECLARANT_NON_HABILITE,
            f"{objet} est déclarée par « {declarant} », de qualité "
            f"{QUALITE_TIERS}. §36 remet la décision à L'ENTITÉ : une "
            f"déclaration d'un tiers — producteur de données, prestataire, "
            f"conseil — peut être parfaitement signée et rester sans valeur "
            f"ici. ⚠️ Son statut ne le dirait pas : c'est pourquoi la qualité "
            f"est un champ à part.")

    return (f"{objet} : statut « {statut} », déclarée par « {declarant} » de "
            f"qualité {QUALITE_ENTITE}. ⚠️ CE QUE CE CONTRÔLE ÉTABLIT ET CE "
            f"QU'IL N'ÉTABLIT PAS : il constate une signature DÉCLARÉE par un "
            f"déclarant DÉCLARÉ de la bonne qualité. Il ne peut pas attraper "
            f"un statut qui ment, et ne vaut donc pas vérification de la "
            f"signature elle-même.")
