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
from typing import NamedTuple

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
MOTIF_PERIMETRE_DISCORDANT = 'perimetre_de_validite_discordant'
MOTIF_CONTEXTE_INVALIDE = 'contexte_d_evaluation_invalide'

#: ⚠️ LA FORME ATTENDUE D'UN ARRÊTÉ, ET ELLE EST STRICTE À DESSEIN. Comparer
#: « 2026-12-31 » à « 31/12/2026 » exigerait de PARSER, donc de deviner un
#: format. Ce module refuse de deviner : il impose l'ISO et le dit.
FORME_ARRETE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

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


class ContexteEvaluation(NamedTuple):
    """CE QU'ON DEMANDE D'ÉVALUER — pas ce qui existe.

    ⚠️⚠️ IL NE PORTE AUCUN `Groupe`, ET C'EST DÉLIBÉRÉ. La frontière du
    paquet tient : `mesure` ne sait toujours pas quels groupes existent, il
    sait seulement à quel ARRÊTÉ et sur quels PORTEFEUILLES on lui demande de
    travailler. C'est le minimum qui rende une comparaison possible.

    ⚠️ ET SANS LUI, LE CONTRÔLE DE PÉRIMÈTRE N'EST PAS OMIS, IL EST
    IMPOSSIBLE : on ne peut pas confronter une déclaration à un périmètre
    évalué que personne ne tient.
    """
    arrete:        str    # 'AAAA-MM-JJ', celui qu'on évalue
    portefeuilles: tuple  # ceux qu'on évalue réellement


class PerimetreDeclare(NamedTuple):
    """POUR QUOI une déclaration est signée — la troisième question.

    ⚠️ ELLE N'EST RÉDUCTIBLE NI AU STATUT NI À LA QUALITÉ. Une courbe de
    l'arrêté précédent est SIGNÉE, par la BONNE ENTITÉ, et FAUSSE : §36 b)
    impose une courbe à la date d'évaluation. C'est le seul des trois défauts
    qui ne laisse AUCUNE trace — les montants restent plausibles.
    """
    arrete:        str    # 'AAAA-MM-JJ', celui que la déclaration couvre
    portefeuilles: tuple  # ceux qu'elle couvre


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


def _exiger_arrete_iso(valeur, quoi: str, erreur, motif):
    """⚠️ L'ISO EST IMPOSÉE PLUTÔT QUE DEVINÉE. Comparer « 2026-12-31 » à
    « 31/12/2026 » exigerait de parser, donc de supposer un format ; et un
    format supposé de travers ferait passer deux arrêtés différents pour le
    même. Ce module refuse, et dit ce qu'il attend."""
    if not FORME_ARRETE.match(str(valeur or '')):
        raise erreur(
            motif,
            f"{quoi} vaut {valeur!r} : la forme AAAA-MM-JJ est attendue. Les "
            f"arrêtés se COMPARENT ici, et comparer deux formats différents "
            f"exigerait d'en deviner un — ce qui ferait passer deux dates "
            f"distinctes pour la même.")


def exiger_declaration_opposable(*, statut, declarant, qualite, erreur,
                                 perimetre=None, contexte=None,
                                 objet: str = 'cette déclaration') -> str:
    """TROIS contrôles distincts, parce que ce sont trois faits distincts.

    ⚠️⚠️ EST-CE SIGNÉ, PAR QUI, ET POUR QUOI. Le troisième a été trouvé après
    les deux autres, et il porte le cas le plus dangereux : une courbe de
    l'arrêté précédent est SIGNÉE, par la BONNE ENTITÉ, et FAUSSE. §36 b)
    impose une courbe à la date d'évaluation. C'est le seul des trois défauts
    qui NE LAISSE AUCUNE TRACE — les montants restent plausibles.

    ⚠️ ET LE PÉRIMÈTRE N'EST PAS PLUS RÉDUCTIBLE AU STATUT QUE LA QUALITÉ NE
    L'ÉTAIT. Fondre l'un dans l'autre reproduirait la faille qu'on vient de
    fermer : trois questions, trois champs.

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

    if perimetre is None or contexte is None:
        raise erreur(
            MOTIF_CONTEXTE_INVALIDE,
            f"{objet} est présentée sans son périmètre de validité ou sans le "
            f"contexte évalué (reçus {perimetre!r} et {contexte!r}). ⚠️ SANS "
            f"EUX LE CONTRÔLE N'EST PAS OMIS, IL EST IMPOSSIBLE : on ne peut "
            f"pas confronter une déclaration à un périmètre que personne ne "
            f"tient. C'est ce qui a laissé passer une courbe périmée.")

    _exiger_arrete_iso(perimetre.arrete, f"l'arrêté déclaré de {objet}",
                       erreur, MOTIF_PERIMETRE_DISCORDANT)
    _exiger_arrete_iso(contexte.arrete, "l'arrêté évalué", erreur,
                       MOTIF_CONTEXTE_INVALIDE)
    if not contexte.portefeuilles:
        raise erreur(
            MOTIF_CONTEXTE_INVALIDE,
            "le contexte n'évalue aucun portefeuille. Une couverture jugée "
            "suffisante sur un ensemble vide le serait trivialement.")

    if perimetre.arrete != contexte.arrete:
        raise erreur(
            MOTIF_PERIMETRE_DISCORDANT,
            f"{objet} couvre l'arrêté {perimetre.arrete} et l'évaluation "
            f"porte sur {contexte.arrete}. ⚠️ ELLE EST SIGNÉE, PAR LA BONNE "
            f"ENTITÉ, ET PÉRIMÉE : §36 b) impose des taux à la date "
            f"d'évaluation. C'est le défaut qui ne laisse aucune trace — les "
            f"montants qui en descendent restent plausibles.")

    manquants = sorted(set(contexte.portefeuilles)
                       - set(perimetre.portefeuilles))
    if manquants:
        raise erreur(
            MOTIF_PERIMETRE_DISCORDANT,
            f"{objet} ne couvre pas {len(manquants)} des "
            f"{len(set(contexte.portefeuilles))} portefeuilles évalués : "
            f"{manquants}. ⚠️ UNE COUVERTURE PARTIELLE EST SILENCIEUSE — le "
            f"calcul aboutit sur les portefeuilles couverts et laisse les "
            f"autres sans déclaration, sans que rien ne le signale. La "
            f"déclaration doit couvrir AU MOINS ce qui est évalué ; couvrir "
            f"davantage est sans conséquence.")

    return (f"{objet} : statut « {statut} », déclarée par « {declarant} » de "
            f"qualité {QUALITE_ENTITE}, pour l'arrêté {perimetre.arrete} et "
            f"{len(set(perimetre.portefeuilles))} portefeuille(s) couvrant "
            f"les {len(set(contexte.portefeuilles))} évalué(s). ⚠️ CE QUE CE "
            f"CONTRÔLE ÉTABLIT ET CE QU'IL N'ÉTABLIT PAS : il constate une "
            f"signature DÉCLARÉE, par un déclarant DÉCLARÉ de la bonne "
            f"qualité, pour un périmètre DÉCLARÉ qui couvre l'évalué. Il ne "
            f"peut pas attraper un statut qui ment, et ne vaut donc pas "
            f"vérification de la signature elle-même.")


#: ⚠️⚠️ LA QUATRIÈME QUESTION, ET ELLE N'EST PAS DANS LES TROIS AUTRES.
#: Est-ce signé · par qui · pour quoi — les trois portent sur UNE déclaration.
#: Celle-ci porte sur L'ENSEMBLE : trois déclarations irréprochables prises
#: séparément peuvent alimenter un même calcul avec TROIS ARRÊTÉS DIFFÉRENTS.
#: Aucun contrôle par déclaration ne peut le voir — le défaut est ENTRE elles.
#:
#: ⚠️ ET CE DÉPÔT AVAIT DÉJÀ ÉCRIT LA RÈGLE, POUR AUTRE CHOSE. « Deux états
#: produits séparément peuvent chacun boucler sur eux-mêmes et se contredire
#: entre eux » figure à quatre endroits — pour le §80, pour le §63, pour la
#: réconciliation. Elle n'avait jamais été retournée contre les DÉCLARATIONS
#: elles-mêmes. La règle existait, elle portait sur autre chose.
DEMONSTRATION_INCOHERENCE_D_ENSEMBLE = (
    "la courbe signée le 05/01/2027 pour l'arrêté 2026-12-31, la convention "
    "signée le 20/01/2026 pour l'arrêté 2025-12-31, et la prime "
    "d'illiquidité signée le 18/01/2025 pour l'arrêté 2024-12-31 : chacune "
    "est signée, par l'entité, et valide pour SON arrêté — et les trois "
    "alimentent un seul calcul.")


#: ⚠️⚠️ LE TAUX A UN USAGE, ET L'USAGE COMMANDE L'ARRÊTÉ ATTENDU. B72 énumère
#: les taux PAR USAGE : a) les flux d'exécution prennent des taux COURANTS ;
#: b), c) et d) prennent des taux DÉTERMINÉS À LA COMPTABILISATION INITIALE du
#: groupe. Deux déclarations d'arrêtés différents ne sont donc pas
#: nécessairement incohérentes — elles le sont si elles servent le MÊME usage.
#:
#: ⚠️ ET CE CONTRÔLE REFUSAIT UNE DÉCLARATION CORRECTE. Il exigeait UN SEUL
#: arrêté pour tout l'ensemble. Or §22 impose des COHORTES ANNUELLES : un
#: portefeuille de trois cohortes a besoin de TROIS taux verrouillés, plus un
#: taux courant. Quatre jeux, quatre arrêtés, et le tout parfaitement
#: cohérent. ⚠️ Une exigence FAUSSE bloque ; c'est le défaut le plus visible,
#: et le plus vite payé.
USAGE_COURANT = 'COURANT'
USAGE_VERROUILLE = 'VERROUILLE'
USAGES_DU_TAUX = (USAGE_COURANT, USAGE_VERROUILLE)

MOTIF_USAGE_NON_DECLARE = 'usage_du_taux_non_declare'


def exiger_ensemble_coherent(*, perimetres: dict, contexte, erreur,
                             usages: dict | None = None) -> str:
    """LA QUATRIÈME QUESTION : ensemble, sont-elles cohérentes ?

    ⚠️ ELLE EST IRRÉDUCTIBLE AUX TROIS AUTRES, qui portent chacune sur UNE
    déclaration. Ici le défaut vit ENTRE elles : voir
    `DEMONSTRATION_INCOHERENCE_D_ENSEMBLE`, qui n'est pas une illustration
    mais le cas mesuré — les trois déclarations y passent les trois premiers
    contrôles et le jeu reste faux.

    ⚠️ ET ELLE NE SE SUBSTITUE PAS À EUX : un ensemble cohérent de trois
    déclarations toutes périmées du même arrêté serait cohérent et faux. Les
    quatre contrôles se cumulent, aucun n'absorbe l'autre.
    """
    if not perimetres:
        raise erreur(
            MOTIF_PERIMETRE_DISCORDANT,
            "aucune déclaration fournie à la vérification d'ensemble. Une "
            "cohérence constatée sur un ensemble vide le serait "
            "trivialement, et ce serait la même faute qu'une gate rendant "
            "« Ran 0 tests » en sortant 0.")

    #: ⚠️ SANS `usages`, ON RETOMBE SUR L'ANCIENNE RÈGLE — un seul arrêté
    #: pour tout. Ce n'est pas un défaut à None : c'est le cas où toutes les
    #: déclarations servent le même usage, et il reste le plus fréquent.
    if usages:
        inconnus = sorted(n for n in perimetres if n not in usages)
        if inconnus:
            raise erreur(
                MOTIF_USAGE_NON_DECLARE,
                f"{len(inconnus)} déclaration(s) sans usage déclaré : "
                f"{inconnus}. Dès qu'un ensemble mêle des usages, CHACUN doit "
                f"dire le sien — sinon l'arrêté attendu n'est pas déterminé.")
        mauvais = sorted(n for n, u in usages.items()
                         if u not in USAGES_DU_TAUX)
        if mauvais:
            raise erreur(
                MOTIF_USAGE_NON_DECLARE,
                f"usage inconnu pour {mauvais} (attendu l'une de "
                f"{USAGES_DU_TAUX}). B72 range les taux par usage : les flux "
                f"d'exécution prennent des taux COURANTS (B72 a), "
                f"l'ajustement du §56 des taux VERROUILLÉS à la "
                f"comptabilisation initiale (B72 d).")
        return _coherence_par_usage(perimetres, usages, contexte, erreur)

    arretes = {nom: p.arrete for nom, p in perimetres.items()}
    distincts = sorted(set(arretes.values()))
    if len(distincts) > 1:
        detail = ' · '.join(f'{nom} → {a}' for nom, a in sorted(arretes.items()))
        raise erreur(
            MOTIF_PERIMETRE_DISCORDANT,
            f"les {len(perimetres)} déclarations qui alimentent ce calcul "
            f"portent {len(distincts)} arrêtés différents : {detail}. ⚠️ "
            f"CHACUNE PEUT ÊTRE IRRÉPROCHABLE PRISE SÉPARÉMENT — signée, par "
            f"l'entité, valide pour SON arrêté — et l'ensemble reste faux. "
            f"Le défaut est ENTRE elles, et aucun contrôle par déclaration ne "
            f"le voit.")

    if distincts[0] != contexte.arrete:
        raise erreur(
            MOTIF_PERIMETRE_DISCORDANT,
            f"les {len(perimetres)} déclarations s'accordent sur l'arrêté "
            f"{distincts[0]}, mais l'évaluation porte sur {contexte.arrete}. "
            f"⚠️ UN ENSEMBLE COHÉRENT ET PÉRIMÉ RESTE PÉRIMÉ : la cohérence "
            f"d'ensemble ne remplace pas le contrôle de périmètre, elle "
            f"s'y ajoute.")

    return (f"{len(perimetres)} déclarations — {', '.join(sorted(perimetres))} "
            f"— s'accordent sur l'arrêté {contexte.arrete}, celui qui est "
            f"évalué. ⚠️ CE CONTRÔLE EST LE SEUL À REGARDER L'ENSEMBLE : les "
            f"trois autres portent chacun sur une déclaration, et un jeu de "
            f"déclarations toutes valides séparément peut rester faux.")


#: ⚠️⚠️ DEUX CATÉGORIES DE COMPARAISON, ET UN BALAYAGE UNIFORME SERAIT FAUX.
#: Tous les arrêtés déclarés ne se comparent pas de la même façon à l'arrêté
#: évalué, et les traiter pareil refuserait des déclarations CORRECTES :
#:
#:   · ÉGAL — une valeur qui vaut pour UNE date d'évaluation : une courbe
#:     (« une courbe vaut pour une date, pas pour toutes »), un ajustement
#:     pour risque, un ultime de projection, une répartition de coûts.
#:
#:   · ANTÉRIEUR OU ÉGAL — une valeur FIGÉE ou ÉVÉNEMENTIELLE, dont la date
#:     est dans le passé PAR CONSTRUCTION : un taux verrouillé, que B72 d)
#:     fige à la comptabilisation initiale du groupe ; une appréciation du
#:     §57, portée « à n'importe quel moment au cours de la période de
#:     couverture ».
#:
#: ⚠️ ET LA CATÉGORIE SE DÉCLARE PAR SITE, JAMAIS NE SE DÉDUIT DU NOM DU
#: CHAMP. Deux champs appelés `arrete` désignent ici deux choses opposées.
COMPARAISON_EGAL = 'EGAL'
COMPARAISON_ANTERIEUR_OU_EGAL = 'ANTERIEUR_OU_EGAL'
COMPARAISONS = (COMPARAISON_EGAL, COMPARAISON_ANTERIEUR_OU_EGAL)

MOTIF_ARRETE_HORS_CONTEXTE = 'arrete_declare_hors_contexte'

#: ⚠️ CE QUE `ANTÉRIEUR OU ÉGAL` NE VÉRIFIE PAS, ET IL FAUT LE LIRE.
LIMITE_ANTERIEUR_OU_EGAL = (
    "⚠️ CE CONTRÔLE NE VÉRIFIE QU'UNE BORNE, LA HAUTE. Il refuse une date "
    "postérieure à l'arrêté évalué ; il ne peut pas refuser une date trop "
    "ANCIENNE, faute de connaître le début de la période concernée. Pour le "
    "§57, qui vise « à n'importe quel moment AU COURS DE la période de "
    "couverture », une appréciation antérieure au début de couverture serait "
    "aussi invalide qu'une appréciation postérieure à l'arrêté — et elle "
    "passerait ici. La fenêtre complète exigerait le début de couverture, que "
    "ce module ne reçoit pas : la limite est NOMMÉE plutôt que comblée par "
    "un contrôle que les paramètres ne permettent pas.")


def exiger_arrete_dans_le_contexte(*, arrete, comparaison, contexte, erreur,
                                   objet: str = 'cette déclaration') -> str:
    """Confronte un arrêté DÉCLARÉ à l'arrêté ÉVALUÉ, selon sa catégorie.

    ⚠️ SIX MODULES EXIGEAIENT L'ARRÊTÉ NON VIDE ET AUCUN NE LE COMPARAIT. Le
    refus d'`attribution` écrivait pourtant « une répartition vaut pour
    l'exercice où elle a été arrêtée, pas pour tous » : la prose énonçait la
    règle, le code ne vérifiait que le non-vide. C'est la forme exacte du
    §70A, dont la docstring citait « ÉVALUE » quand le code testait
    « éligible ».
    """
    if comparaison not in COMPARAISONS:
        raise erreur(
            MOTIF_ARRETE_HORS_CONTEXTE,
            f"la catégorie de comparaison de {objet} n'est pas déclarée "
            f"(reçu {comparaison!r}, attendu l'une de {COMPARAISONS}). ⚠️ "
            f"ELLE NE SE DÉDUIT PAS DU NOM DU CHAMP : deux champs appelés "
            f"`arrete` désignent ici deux choses opposées — une courbe vaut "
            f"pour la date évaluée, un taux verrouillé est figé dans le "
            f"passé par B72 d).")
    _exiger_arrete_iso(arrete, f"l'arrêté déclaré de {objet}", erreur,
                       MOTIF_ARRETE_HORS_CONTEXTE)
    _exiger_arrete_iso(contexte.arrete, "l'arrêté évalué", erreur,
                       MOTIF_CONTEXTE_INVALIDE)

    if comparaison == COMPARAISON_EGAL:
        if arrete != contexte.arrete:
            raise erreur(
                MOTIF_ARRETE_HORS_CONTEXTE,
                f"{objet} porte l'arrêté {arrete} et l'évaluation porte sur "
                f"{contexte.arrete}. Cette valeur vaut pour UNE date, pas "
                f"pour toutes — l'employer hors de sa date la rend fausse "
                f"sans rien changer à sa vraisemblance.")
        return (f"{objet} : arrêté {arrete}, égal à l'arrêté évalué.")

    if arrete > contexte.arrete:
        raise erreur(
            MOTIF_ARRETE_HORS_CONTEXTE,
            f"{objet} porte l'arrêté {arrete}, POSTÉRIEUR à l'arrêté évalué "
            f"{contexte.arrete}. Une valeur figée ou un fait constaté ne "
            f"peuvent pas venir d'après la date qu'on évalue.")
    return (f"{objet} : arrêté {arrete}, antérieur ou égal à l'arrêté évalué "
            f"{contexte.arrete}. " + LIMITE_ANTERIEUR_OU_EGAL)


def _coherence_par_usage(perimetres, usages, contexte, erreur) -> str:
    """La cohérence se juge PAR USAGE, pas sur l'ensemble indistinct.

    ⚠️ LES DEUX USAGES N'ATTENDENT PAS LE MÊME ARRÊTÉ, et c'est tout le
    point : un taux COURANT doit porter l'arrêté évalué ; un taux VERROUILLÉ
    porte celui de la cohorte, nécessairement antérieur ou égal. Les
    confondre refuserait des déclarations correctes — le mode de défaillance
    qu'une comparaison uniforme produit toujours.
    """
    courants = {n: p.arrete for n, p in perimetres.items()
                if usages[n] == USAGE_COURANT}
    hors = sorted(n for n, a in courants.items() if a != contexte.arrete)
    if hors:
        raise erreur(
            MOTIF_PERIMETRE_DISCORDANT,
            f"{len(hors)} déclaration(s) d'usage COURANT ne portent pas "
            f"l'arrêté évalué {contexte.arrete} : "
            f"{[(n, courants[n]) for n in hors]}. B72 a) impose des taux "
            f"COURANTS pour les flux d'exécution.")

    verrouilles = {n: p.arrete for n, p in perimetres.items()
                   if usages[n] == USAGE_VERROUILLE}
    futurs = sorted(n for n, a in verrouilles.items() if a > contexte.arrete)
    if futurs:
        raise erreur(
            MOTIF_PERIMETRE_DISCORDANT,
            f"{len(futurs)} taux VERROUILLÉ(S) portent un arrêté POSTÉRIEUR "
            f"à l'évaluation : {[(n, verrouilles[n]) for n in futurs]}. Un "
            f"taux figé à la comptabilisation initiale ne peut pas venir "
            f"d'après la date qu'on évalue.")

    doublons = [a for a in set(verrouilles.values())
                if list(verrouilles.values()).count(a) > 1]
    if doublons:
        raise erreur(
            MOTIF_PERIMETRE_DISCORDANT,
            f"deux taux verrouillés portent le même arrêté {sorted(doublons)} "
            f"alors qu'ils devraient couvrir des cohortes distinctes. §22 "
            f"impose des cohortes ANNUELLES : un arrêté en double signale "
            f"soit un doublon, soit une cohorte oubliée.")

    return (f"{len(perimetres)} déclarations, {len(courants)} d'usage COURANT "
            f"à l'arrêté évalué {contexte.arrete} et {len(verrouilles)} "
            f"VERROUILLÉ(S) sur {sorted(verrouilles.values())}. ⚠️ LA "
            f"COHÉRENCE SE JUGE PAR USAGE : des arrêtés différents ne sont "
            f"incohérents que s'ils servent le MÊME usage. §22 imposant des "
            f"cohortes annuelles, un portefeuille de trois cohortes appelle "
            f"trois taux verrouillés — quatre arrêtés distincts, et l'ensemble "
            f"se tient. ⚠️ CE CONTRÔLE NE VÉRIFIE PAS que chaque taux "
            f"verrouillé porte l'arrêté de SA cohorte : il ne connaît pas les "
            f"cohortes évaluées.")


#: ⚠️ LA FORME D'UNE COHORTE — §22 les impose ANNUELLES, donc une année.
FORME_COHORTE = re.compile(r'^\d{4}$')

MOTIF_COHORTE_NON_DECLAREE = 'cohorte_du_groupe_non_declaree'
MOTIF_TAUX_HORS_COHORTE = 'taux_verrouille_hors_cohorte'

#: ⚠️⚠️ POURQUOI L'ANNÉE, ET L'APPUI A ÉTÉ CORRIGÉ — LE PREMIER ÉTAIT FAUX.
#: Ce module a d'abord justifié l'année par le §22 : « §22 impose des cohortes
#: annuelles, donc la cohorte est l'unité ». ⚠️ §22 NE DIT PAS ÇA. Il dit
#: seulement qu'on « ne doit pas classer dans un même groupe des contrats émis
#: à plus d'un an d'intervalle » — il plafonne l'ÉTENDUE d'un groupe, et ne
#: dit rien de la date à laquelle un taux se détermine. Celle-ci relève du
#: §25 : la PREMIÈRE du début de couverture, de la première prime exigible, ou
#: du moment où le groupe devient déficitaire.
#:
#: ⚠️⚠️ L'APPUI RÉEL EST B73, ET IL EST DIRECT : « Pour déterminer, à la date
#: de la comptabilisation initiale d'un groupe de contrats, les taux
#: d'actualisation décrits AUX PARAGRAPHES B72 b) À B72 e), l'entité PEUT
#: utiliser des taux d'actualisation MOYENS PONDÉRÉS POUR L'INTERVALLE DE
#: TEMPS AU COURS DUQUEL SONT ÉMIS LES CONTRATS DU GROUPE, et qui, selon le
#: paragraphe 22, ne peut excéder un an. » Il couvre B72 d), donc le §56 : la
#: norme ANTICIPE qu'un groupe s'étale sur un an, et l'autorise explicitement.
#:
#: ⚠️ ET B73 DIT « PEUT » — C'EST UNE FACULTÉ, PAS UNE RÈGLE. Deux formes sont
#: donc légitimes, et elles ne donnent pas la même date :
#:
#:   · la DATE DU §25 — celle de la comptabilisation initiale du groupe ;
#:   · la MOYENNE PONDÉRÉE DE B73 — sur l'intervalle d'émission.
#:
#: ⚠️⚠️ ET CE CONTRÔLE N'EXIGE NI L'UNE NI L'AUTRE : il accepte toute date de
#: l'année de la cohorte. Il est donc PLUS LÂCHE QUE LES DEUX FORMES
#: LÉGITIMES — mesuré : il accepte le 1er janvier, le 1er juillet et le
#: 31 décembre indifféremment. Le 31 décembre est le taux de FIN d'année, pas
#: une moyenne ; sur des émissions quasi uniformes, une moyenne pondérée
#: tombe vers le milieu de l'année. La différence n'est pas cosmétique sur un
#: exercice à taux mobiles.
#:
#: ⚠️⚠️ UNE VARIANTE DU MOTIF DE CE DÉPÔT, ET ELLE EST NEUVE. Le premier
#: raisonnement ANNONÇAIT qu'il était un raisonnement — « c'est un
#: raisonnement, pas une lecture littérale » — et s'appuyait pourtant sur le
#: mauvais article. LE SIGNALER NE LE RENDAIT PAS JUSTE. Une étiquette
#: d'honnêteté n'est pas une vérification : elle dit qu'on sait ce qu'on fait,
#: pas qu'on a raison de le faire.
RAISONNEMENT_COHORTE_ANNUELLE = (
    "⚠️ CE CONTRÔLE RETIENT L'ANNÉE, ET SON APPUI EST B73 — non le §22, qui "
    "avait d'abord été invoqué À TORT. §22 plafonne l'ÉTENDUE d'un groupe "
    "(pas de contrats émis à plus d'un an d'intervalle) et ne dit rien de la "
    "date d'un taux ; celle-ci relève du §25. B73, lui, autorise directement "
    "« des taux d'actualisation MOYENS PONDÉRÉS pour l'intervalle de temps au "
    "cours duquel sont émis les contrats du groupe » — pour les taux de B72 "
    "b) à e), donc pour le §56. La norme anticipe qu'un groupe s'étale sur "
    "un an. ⚠️ MAIS B73 DIT « PEUT » : deux formes sont légitimes — la date "
    "du §25, ou la moyenne pondérée de B73 — et elles ne donnent pas la même "
    "date. ⚠️ CE QUE CE CONTRÔLE LAISSE PASSER, ET C'EST PLUS LARGE QU'UN "
    "ARBITRAGE : il n'exige NI l'une NI l'autre, il accepte toute date de "
    "l'année. Le 31 décembre est le taux de FIN d'année ; sur des émissions "
    "quasi uniformes, une moyenne pondérée tombe vers le milieu. Sur un "
    "exercice à taux mobiles, l'écart n'est pas cosmétique.")


#: ⚠️⚠️ LES DEUX FORMES QUE B73 REND LÉGITIMES, ET ELLES SE DÉCLARENT. B73
#: dit « PEUT » : l'entité détermine le taux à la date de comptabilisation
#: initiale (§25), OU par moyenne pondérée sur l'intervalle d'émission. Les
#: deux sont recevables et ne donnent pas la même date — deviner laquelle est
#: employée reviendrait à supposer une méthode.
FORME_DATE_25 = 'DATE_COMPTABILISATION_25'
FORME_MOYENNE_B73 = 'MOYENNE_PONDEREE_B73'
FORMES_DU_TAUX_VERROUILLE = (FORME_DATE_25, FORME_MOYENNE_B73)

MOTIF_FORME_DU_TAUX_NON_DECLAREE = 'forme_du_taux_verrouille_non_declaree'

#: ⚠️⚠️ CE QUE CE MODULE NE PEUT PAS VÉRIFIER, ET IL FAUT LE LIRE AVANT DE S'Y
#: FIER. Aucune des deux formes n'est RECALCULABLE ici : la date du §25 exige
#: le début de couverture du groupe, la moyenne de B73 exige les dates
#: d'émission de ses contrats — `roll_forward` ne reçoit ni l'un ni l'autre.
#: Ce contrôle vérifie donc trois choses seulement : que la forme est
#: DÉCLARÉE, que la date tombe dans l'année de la cohorte, et qu'elle n'est
#: pas postérieure à l'évaluation. ⚠️ LA LIMITE EST NOMMÉE PLUTÔT QUE COMBLÉE
#: PAR UN CONTRÔLE QUE LES PARAMÈTRES NE PERMETTENT PAS — c'est la règle qui a
#: déjà servi pour la fenêtre du §57.
LIMITE_DES_DEUX_FORMES = (
    "⚠️ CE CONTRÔLE NE RECALCULE NI L'UNE NI L'AUTRE DES DEUX FORMES. La date "
    "du §25 exigerait le début de couverture du groupe, la moyenne pondérée "
    "de B73 exigerait les dates d'émission de ses contrats : ce module ne "
    "reçoit ni l'un ni l'autre. Il vérifie que la forme est DÉCLARÉE, que la "
    "date tombe dans l'année de la cohorte, et qu'elle n'est pas postérieure "
    "à l'évaluation. La valeur elle-même reste sous la responsabilité de "
    "l'entité.")


def exiger_taux_de_la_cohorte(*, arrete_verrouillage, cohorte, contexte,
                              erreur, forme: str = '',
                              objet: str = 'le taux verrouillé') -> str:
    """B72 d) — le taux figé appartient-il à la cohorte du groupe évalué ?

    ⚠️ `ANTERIEUR_OU_EGAL` NE SUFFISAIT PAS, ET C'ÉTAIT MESURÉ : il acceptait
    un taux de 2020 pour une cohorte 2024. Il ne vérifiait qu'une borne, la
    haute — la limite était nommée, et c'est ici qu'elle mordait.
    """
    if forme not in FORMES_DU_TAUX_VERROUILLE:
        raise erreur(
            MOTIF_FORME_DU_TAUX_NON_DECLAREE,
            f"la forme du taux verrouillé n'est pas déclarée (reçu "
            f"{forme!r}, attendu l'une de {FORMES_DU_TAUX_VERROUILLE}). B73 "
            f"dit « PEUT » : l'entité détermine le taux à la date de "
            f"comptabilisation initiale du groupe (§25) OU par moyenne "
            f"pondérée sur l'intervalle d'émission. Les deux sont légitimes "
            f"et ne donnent pas la même date — la deviner reviendrait à "
            f"supposer une méthode.")
    if not FORME_COHORTE.match(str(cohorte or '')):
        raise erreur(
            MOTIF_COHORTE_NON_DECLAREE,
            f"la cohorte du groupe évalué n'est pas déclarée (reçu "
            f"{cohorte!r}, attendu une année AAAA). §22 impose des cohortes "
            f"ANNUELLES ; sans elle, un taux verrouillé ne se rattache à "
            f"aucun groupe et toute comparaison serait une supposition.")
    _exiger_arrete_iso(arrete_verrouillage, f"l'arrêté de {objet}", erreur,
                       MOTIF_TAUX_HORS_COHORTE)
    _exiger_arrete_iso(contexte.arrete, "l'arrêté évalué", erreur,
                       MOTIF_CONTEXTE_INVALIDE)

    if arrete_verrouillage > contexte.arrete:
        raise erreur(
            MOTIF_TAUX_HORS_COHORTE,
            f"{objet} porte l'arrêté {arrete_verrouillage}, POSTÉRIEUR à "
            f"l'arrêté évalué {contexte.arrete}. Un taux figé à la "
            f"comptabilisation initiale ne peut pas venir d'après la date "
            f"qu'on évalue.")
    if arrete_verrouillage[:4] != cohorte:
        raise erreur(
            MOTIF_TAUX_HORS_COHORTE,
            f"{objet} porte l'arrêté {arrete_verrouillage} et le groupe "
            f"évalué relève de la cohorte {cohorte}. B72 d) fige le taux À LA "
            f"COMPTABILISATION INITIALE du groupe : un taux d'une AUTRE "
            f"cohorte est signé, antérieur, et faux. ⚠️ C'est le cas qu'une "
            f"simple borne « antérieur ou égal » laissait passer — elle "
            f"acceptait un taux de 2020 pour une cohorte 2024. "
            + RAISONNEMENT_COHORTE_ANNUELLE)

    #: ⚠️ UNE MOYENNE PONDÉRÉE QUI TOMBE LE 31 DÉCEMBRE EST SIGNALÉE, PAS
    #: REFUSÉE. Elle n'est possible que si tous les contrats du groupe ont
    #: été émis ce jour-là — cas réel mais rare. Refuser bloquerait un cas
    #: légitime ; taire laisserait passer le taux de FIN d'année déguisé en
    #: moyenne, qui est l'approximation la plus courante.
    signal = ''
    if forme == FORME_MOYENNE_B73 and arrete_verrouillage[5:] == '12-31':
        signal = (
            " ⚠️ SIGNALEMENT, NON REFUS : une MOYENNE PONDÉRÉE annoncée qui "
            "tombe le 31 décembre n'est possible que si tous les contrats du "
            "groupe ont été émis ce jour-là. Sur des émissions étalées, une "
            "moyenne tombe vers le milieu de l'intervalle — le 31 décembre "
            "est le taux de FIN d'année, qui est une autre chose. Ce module "
            "ne peut pas trancher, faute des dates d'émission ; il signale.")

    return (f"{objet} : arrêté {arrete_verrouillage}, cohorte {cohorte} du "
            f"groupe évalué, forme déclarée « {forme} »."
            + signal + ' ' + RAISONNEMENT_COHORTE_ANNUELLE
            + ' ' + LIMITE_DES_DEUX_FORMES)
