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

#: ⚠️⚠️ UNE LIMITE TROUVÉE PAR LE BALAYAGE EN PROSE, ET ELLE N'EST PAS
#: FERMÉE — elle est NOMMÉE. Le refus sur deux taux verrouillés de même arrêté
#: était justifié par « §22 impose des cohortes ANNUELLES, donc deux cohortes
#: ont deux arrêtés ». ⚠️ CETTE JUSTIFICATION EST DU MÊME AXE FAUX que celle
#: que ce lot corrige : l'arrêté d'un taux verrouillé ne vient pas de la
#: cohorte (§22, l'émission) mais de la comptabilisation initiale (§25).
#:
#: ⚠️ ET DEUX GROUPES PEUVENT SE COMPTABILISER LE MÊME JOUR — deux
#: portefeuilles dont la couverture s'ouvre au 1er janvier, ou deux cohortes
#: dont l'une porte une couverture rétroactive. Le refus peut donc être un
#: FAUX REJET. Il est maintenu parce que le cas ordinaire reste le doublon, et
#: parce que le corriger relève du COMPORTEMENT, pas de la propreté de ce lot.
LIMITE_DU_DOUBLON = (
    "⚠️ CE REFUS SUPPOSE QUE DEUX GROUPES SE COMPTABILISENT À DES DATES "
    "DISTINCTES, ET CE N'EST PAS TOUJOURS VRAI. B72 d) fige le taux à la "
    "COMPTABILISATION INITIALE (§25), que deux groupes peuvent partager — "
    "deux portefeuilles dont la couverture s'ouvre le même jour, ou une "
    "cohorte à couverture rétroactive. C'est donc un faux rejet POSSIBLE, "
    "nommé plutôt que tu : sa justification d'origine invoquait les cohortes "
    "annuelles du §22, qui est le MÊME axe faux que ce module vient de "
    "défaire ailleurs.")


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
    porte celui de la COMPTABILISATION INITIALE de son groupe (B72 d) + §25),
    nécessairement antérieur ou égal à l'évaluation. Les confondre refuserait
    des déclarations correctes — le mode de défaillance qu'une comparaison
    uniforme produit toujours.

    ⚠️⚠️ CETTE DOCSTRING DISAIT « PORTE CELUI DE LA COHORTE », ET C'ÉTAIT
    FAUX. Un taux verrouillé n'est pas daté par la cohorte : §22 constitue le
    groupe sur l'ÉMISSION, §25 le comptabilise ailleurs. La correction est
    venue d'un balayage EN PROSE — un relevé par symbole ne l'aurait pas vue,
    parce que rien de ce qui est faux ici n'est un nom.
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
            f"deux taux verrouillés portent le même arrêté "
            f"{sorted(doublons)}. Le cas ordinaire est un doublon, ou un "
            f"groupe oublié dont le taux manque. " + LIMITE_DU_DOUBLON)

    return (f"{len(perimetres)} déclarations, {len(courants)} d'usage COURANT "
            f"à l'arrêté évalué {contexte.arrete} et {len(verrouilles)} "
            f"VERROUILLÉ(S) sur {sorted(verrouilles.values())}. ⚠️ LA "
            f"COHÉRENCE SE JUGE PAR USAGE : des arrêtés différents ne sont "
            f"incohérents que s'ils servent le MÊME usage. §22 bornant "
            f"l'étendue d'un groupe à un an d'émissions, un portefeuille de "
            f"trois cohortes appelle trois taux verrouillés — quatre arrêtés "
            f"distincts, et l'ensemble se tient. ⚠️ CE CONTRÔLE NE VÉRIFIE "
            f"PAS que chaque taux verrouillé porte la date de comptabilisation "
            f"initiale de SON groupe : il ne connaît pas les groupes évalués. "
            + LIMITE_DU_DOUBLON)


#: ⚠️⚠️ LA FORME D'UNE ÉTIQUETTE DE COHORTE, ET ELLE ÉTAIT TROP ÉTROITE.
#: `^\d{4}$` n'acceptait que l'année civile. Or le socle produit l'étiquette
#: sous une convention DÉCLARÉE : `cohorte(convention_exercice(4), …)` rend
#: « 2024-25 » pour un exercice avril-mars, que ce module refusait à tort —
#: mesuré sur le producteur d'étiquettes lui-même. La forme accepte donc les
#: deux, et REFUSE toujours ce qui n'est pas une étiquette : « 2024-12-31 »
#: (un arrêté glissé à la place d'une cohorte) et « 24 » (une année tronquée).
#:
#: ⚠️ ET LA CORRESPONDANCE AVEC LE SOCLE EST VÉRIFIÉE BRUYAMMENT, DANS LE
#: SOCLE — `test_groupe.py`. Ce module ne peut pas importer `socle.groupe`
#: sans rompre la frontière du paquet ; c'est donc au producteur de
#: l'étiquette de crier si sa forme s'écarte de ce que la mesure accepte.
FORME_COHORTE = re.compile(r'^\d{4}(-\d{2})?$')

MOTIF_COHORTE_NON_DECLAREE = 'cohorte_du_groupe_non_declaree'
MOTIF_GROUPE_NON_DECLARE = 'groupe_evalue_non_declare'
MOTIF_TAUX_POSTERIEUR_A_L_EVALUATION = 'taux_verrouille_posterieur'
MOTIF_TAUX_HORS_COMPTABILISATION_25 = 'taux_hors_comptabilisation_initiale'

#: ⚠️⚠️ DEUX AXES, ET LES CONFONDRE REFUSAIT DU CORRECT. C'est le troisième
#: état de ce raisonnement, et les deux premiers étaient faux :
#:
#:   1. « §22 impose des cohortes annuelles, donc la cohorte est l'unité » —
#:      FAUX D'APPUI. §22 dit seulement qu'on « ne doit pas classer dans un
#:      même groupe des contrats ÉMIS à plus d'un an d'intervalle » : il
#:      plafonne l'ÉTENDUE d'un groupe et ne dit rien de la date d'un taux.
#:   2. « l'appui est B73, donc l'arrêté du taux tombe dans l'année de la
#:      cohorte » — APPUI JUSTE, CONCLUSION FAUSSE. B73 autorise la moyenne
#:      pondérée sur l'intervalle d'ÉMISSION ; il ne dit pas que la
#:      comptabilisation initiale tombe dans l'année d'émission.
#:
#: ⚠️⚠️ CE QUI EST VRAI : LA COHORTE SUIT L'ÉMISSION, LE TAUX SUIT LA
#: COMPTABILISATION INITIALE, ET AUCUNE DES DEUX NE BORNE L'AUTRE.
#:
#:   · §22  — la cohorte, par l'ÉMISSION ;
#:   · B72 d) — le taux verrouillé, « DÉTERMINÉ LORS DE LA COMPTABILISATION
#:     INITIALE » ; §25 la définit comme la PREMIÈRE du début de couverture,
#:     de la première prime exigible, ou du moment où le groupe devient
#:     déficitaire. Aucune des trois n'est bornée par l'année d'émission.
#:
#: ⚠️ LES DEUX SENS SONT MESURÉS SUR LE BANC LOCAL, pas supposés : une
#: production de décembre 2024 (cohorte 2024) se comptabilise le 08/01/2025 ;
#: une couverture rétroactive émise en 2026 (cohorte 2026) se comptabilise le
#: 27/12/2025. L'ancien contrôle refusait les deux.
#:
#: ⚠️⚠️ UNE VARIANTE DU MOTIF DE CE DÉPÔT, ET ELLE EST NEUVE. Le premier
#: raisonnement ANNONÇAIT qu'il était un raisonnement — « c'est un
#: raisonnement, pas une lecture littérale » — et s'appuyait pourtant sur le
#: mauvais article. LE SIGNALER NE LE RENDAIT PAS JUSTE. Une étiquette
#: d'honnêteté n'est pas une vérification : elle dit qu'on sait ce qu'on fait,
#: pas qu'on a raison de le faire. ⚠️ ET LE SECOND ÉTAT MONTRE LA SUITE : un
#: appui CORRIGÉ ne corrige pas à lui seul la conclusion qu'il portait.
RAISONNEMENT_DES_DEUX_AXES = (
    "⚠️ LA COHORTE ET L'ARRÊTÉ DU TAUX SONT DEUX AXES, ET LES CONFONDRE "
    "REFUSAIT DU CORRECT. La cohorte suit l'ÉMISSION — §22 : « ne pas classer "
    "dans un même groupe des contrats ÉMIS à plus d'un an d'intervalle ». Le "
    "taux verrouillé suit la COMPTABILISATION INITIALE — B72 d) : des taux "
    "« déterminés lors de la comptabilisation initiale », que §25 fixe à la "
    "PREMIÈRE du début de couverture, de la première prime exigible, ou du "
    "moment où le groupe devient déficitaire. ⚠️ AUCUNE DES DEUX NE BORNE "
    "L'AUTRE, DANS AUCUN SENS : une production de décembre relève de la "
    "cohorte de l'année et se comptabilise en janvier suivant ; une "
    "couverture rétroactive relève de la cohorte de son émission et se "
    "comptabilise l'année d'avant. ⚠️ CE CONTRÔLE A EXIGÉ L'ANNÉE DE LA "
    "COHORTE, ET LE PRIX EST MESURÉ : 2 groupes sur 18 du banc local refusés "
    "à tort, et 116 contrats sur 2 005 dont l'année du §25 diffère de l'année "
    "d'émission — 25 par la branche §25 a), 91 par la branche §25 b).")

#: ⚠️⚠️ ET L'EXACTITUDE FERME UN TROU QUI ÉTAIT NOMMÉ. L'ancien contrôle
#: acceptait TOUTE date de l'année de la cohorte : le 1er janvier, le
#: 1er juillet et le 31 décembre indifféremment. Il était donc PLUS LÂCHE que
#: les deux formes légitimes, et sa docstring le disait sans le corriger.
#: C'est exactement ce qui a laissé passer la première déclaration du
#: producteur — un taux au 31/12/2024 annoncé pour une cohorte 2024 dont la
#: comptabilisation initiale tombe le 11/01/2024.
#:
#: ⚠️ LA COMPARAISON EXACTE PAR FORME LE FERME DANS LES DEUX SENS : elle
#: cesse de refuser du correct (les deux groupes ci-dessus) et cesse
#: d'accepter le taux de FIN d'année déguisé en date de comptabilisation.
CE_QUE_L_EXACTITUDE_FERME = (
    "⚠️ CE CONTRÔLE COMPARE DÉSORMAIS PAR FORME, ET EXACTEMENT. L'ancien "
    "acceptait toute date de l'année de la cohorte — plus lâche que les DEUX "
    "formes légitimes, et sa propre docstring le disait sans le corriger. "
    "C'est ce qui a laissé passer un taux au 31 décembre annoncé pour un "
    "groupe dont la comptabilisation initiale tombe le 11 janvier. "
    "L'exactitude ferme le trou dans les deux sens : elle cesse de refuser du "
    "correct, et cesse d'accepter le taux de FIN d'année déguisé en date de "
    "comptabilisation initiale.")


#: ⚠️⚠️ LES DEUX FORMES QUE B73 REND LÉGITIMES, ET ELLES SE DÉCLARENT. B73
#: dit « PEUT » : l'entité détermine le taux à la date de comptabilisation
#: initiale (§25), OU par moyenne pondérée sur l'intervalle d'émission. Les
#: deux sont recevables et ne donnent pas la même date — deviner laquelle est
#: employée reviendrait à supposer une méthode.
FORME_DATE_25 = 'DATE_COMPTABILISATION_25'
FORME_MOYENNE_B73 = 'MOYENNE_PONDEREE_B73'
FORMES_DU_TAUX_VERROUILLE = (FORME_DATE_25, FORME_MOYENNE_B73)

MOTIF_FORME_DU_TAUX_NON_DECLAREE = 'forme_du_taux_verrouille_non_declaree'
MOTIF_HORS_INTERVALLE_EMISSION = 'taux_b73_hors_intervalle_d_emission'
MOTIF_PONDERATION_NON_DECLAREE = 'ponderation_b73_non_declaree'

#: ⚠️⚠️ L'INTERVALLE D'ÉMISSION VAUT POUR B73, ET PAS POUR LE §25 — la
#: distinction est le tout de ce contrôle.
#:
#:   · Pour B73, il est EXACT PAR CONSTRUCTION : une moyenne pondérée de
#:     valeurs de [a ; b] avec des poids positifs est dans [a ; b]. Ce n'est
#:     pas une heuristique, c'est une propriété — le refus est donc sûr.
#:   · Pour le §25, il serait FAUX. §25 retient la PREMIÈRE de trois dates :
#:     début de couverture, première prime exigible, ou moment où le groupe
#:     devient déficitaire. Un début de couverture peut PRÉCÉDER l'émission
#:     (couverture rétroactive) ; un déclenchement de déficit peut la SUIVRE.
#:     Aucune des trois n'est bornée par l'intervalle d'émission, et l'imposer
#:     refuserait une date §25 légitime.
LIMITE_INTERVALLE_PAR_FORME = (
    "⚠️ L'INTERVALLE D'ÉMISSION N'EST OPPOSÉ QU'À LA FORME B73. Pour elle il "
    "est EXACT par construction — une moyenne pondérée de valeurs de [a ; b] "
    "est dans [a ; b]. Pour la date du §25 il serait FAUX : §25 retient la "
    "PREMIÈRE de trois dates — début de couverture, première prime exigible, "
    "moment où le groupe devient déficitaire — dont aucune n'est bornée par "
    "l'intervalle d'émission. L'y contraindre refuserait du correct.")

#: ⚠️⚠️ CE QU'UNE DATE NE PEUT PAS PORTER, ET IL FAUT LE LIRE. B73 autorise
#: des « taux d'actualisation MOYENS PONDÉRÉS », pas une date moyenne.
#: Déclarer une DATE suppose que le taux au barycentre des émissions égale la
#: moyenne pondérée des taux sur l'intervalle — ce qui n'est exact que si le
#: taux évolue LINÉAIREMENT sur la période. Sur une courbe convexe ou un
#: mouvement brutal en cours d'exercice, l'écart est réel.
#:
#: ⚠️ ET CE MODULE NE PEUT RIEN Y FAIRE : il ne voit pas les taux, seulement
#: leur date. Un champ d'arrêté unique ne peut pas porter une moyenne de
#: taux ; il porte au mieux son approximation par une date. La limite est
#: nommée plutôt que comblée par un contrôle que les paramètres ne permettent
#: pas — un contrôle qui ne dit pas sa portée se fait surévaluer.
RESERVE_MOYENNE_DE_TAUX = (
    "⚠️ B73 AUTORISE UNE MOYENNE DE TAUX, PAS UNE DATE MOYENNE. Déclarer une "
    "date suppose que le taux au barycentre des émissions égale la moyenne "
    "pondérée des taux sur l'intervalle — exact si le taux évolue "
    "linéairement, APPROCHÉ sinon, et l'écart est réel sur une courbe convexe "
    "ou un mouvement brutal en cours d'exercice. Un champ d'arrêté unique ne "
    "peut pas porter une moyenne de taux ; ce module ne voit que la date, et "
    "ne vérifie donc PAS l'approximation elle-même.")

#: ⚠️⚠️ CE QUE CE MODULE NE PEUT PAS VÉRIFIER, ET IL FAUT LE LIRE AVANT DE S'Y
#: FIER. Aucune des deux formes n'est RECALCULABLE ici : la date du §25 se
#: DÉCLARE avec le groupe, elle ne se dérive pas — il faudrait le début de
#: couverture, l'échéance de la première prime et le moment du déficit, que ce
#: module ne reçoit pas. La moyenne de B73 exigerait les dates d'émission de
#: chaque contrat, qu'il ne reçoit pas davantage.
#:
#: ⚠️ CE QU'IL ÉTABLIT EST DONC UNE COHÉRENCE ENTRE DÉCLARATIONS, PAS UNE
#: VALEUR : que la forme est déclarée, et que l'arrêté du taux s'accorde avec
#: le fait déclaré que cette forme désigne. C'est réel — c'est exactement ce
#: qui attrape « forme §25 déclarée, taux de fin d'année fourni » — et ce
#: n'est pas une vérification de la courbe elle-même.
LIMITE_DES_DEUX_FORMES = (
    "⚠️ CE CONTRÔLE NE RECALCULE NI L'UNE NI L'AUTRE DES DEUX FORMES. La date "
    "du §25 se DÉCLARE avec le groupe — la dériver exigerait le début de "
    "couverture, l'échéance de la première prime et le moment du déficit ; la "
    "moyenne pondérée de B73 exigerait les dates d'émission de chaque "
    "contrat. Ce module ne reçoit ni les uns ni les autres. Il établit une "
    "COHÉRENCE ENTRE DÉCLARATIONS — la forme déclarée et le fait qu'elle "
    "désigne — et non la valeur du taux, qui reste sous la responsabilité de "
    "l'entité.")


class GroupeEvalue(NamedTuple):
    """L'IDENTITÉ DÉCLARÉE DU GROUPE — TROIS FAITS, TROIS ARTICLES.

    ⚠️⚠️ CE REGROUPEMENT EST NÉ D'UN DÉFAUT, ET LE DÉFAUT VENAIT DE LA
    SÉPARATION. La cohorte et l'arrêté du taux verrouillé voyageaient comme
    deux paramètres indépendants d'une signature qui en portait six. Rien ne
    disait qu'ils relevaient de DEUX AXES, et le contrôle a comparé l'un à
    l'autre : il exigeait que l'arrêté du taux tombe dans l'ANNÉE de la
    cohorte. ⚠️ IL REFUSAIT ALORS DES TAUX CORRECTS.

      · `cohorte`             — §22, l'ÉMISSION. C'est l'étiquette produite
        par le socle sous la convention déclarée, « 2024 » ou « 2024-25 ».
      · `date_25`             — §25, la COMPTABILISATION INITIALE. C'est elle
        que B72 d) vise, et elle NE SE DÉRIVE PAS de la cohorte.
      · `intervalle_emission` — B73, les bornes d'émission du groupe.

    ⚠️ LE REGROUPEMENT NE CORRIGE PAS LE DÉFAUT — la comparaison par forme le
    fait. Il empêche le SUIVANT : trois faits liés qui voyagent ensemble ne
    peuvent plus être comparés au hasard de l'ordre des paramètres.
    """
    cohorte:             str          # §22  — l'étiquette du socle
    date_25:             str          # §25  — 'AAAA-MM-JJ'
    intervalle_emission: tuple = ()   # B73  — (première, dernière) émission


def _exiger_groupe_declare(groupe, erreur):
    """Le groupe évalué est-il déclaré, et ses trois faits bien formés ?

    ⚠️ LA `date_25` EST VÉRIFIÉE MÊME SOUS LA FORME B73, QUI NE LA COMPARE
    PAS. Elle fait partie de l'identité du groupe, pas de la déclaration de
    taux : une `date_25` malformée signale un appelant qui s'est trompé
    d'objet, et le signaler tard vaudrait moins que le signaler ici.
    """
    if groupe is None:
        raise erreur(
            MOTIF_GROUPE_NON_DECLARE,
            "le groupe évalué n'est pas déclaré. Un taux verrouillé se "
            "rattache à UN groupe — sans lui, toute comparaison serait une "
            "supposition. " + RAISONNEMENT_DES_DEUX_AXES)
    if not FORME_COHORTE.match(str(groupe.cohorte or '')):
        raise erreur(
            MOTIF_COHORTE_NON_DECLAREE,
            f"la cohorte du groupe évalué n'est pas déclarée (reçu "
            f"{groupe.cohorte!r}, attendu l'étiquette produite par le socle — "
            f"« AAAA » en année civile, « AAAA-AA » sous exercice décalé). "
            f"⚠️ ELLE N'EST PLUS CE QUI BORNE LE TAUX : elle identifie le "
            f"groupe. " + RAISONNEMENT_DES_DEUX_AXES)
    _exiger_arrete_iso(groupe.date_25,
                       "la date de comptabilisation initiale (§25) du groupe",
                       erreur, MOTIF_TAUX_HORS_COMPTABILISATION_25)


def exiger_taux_verrouille_du_groupe(*, arrete_verrouillage, groupe, contexte,
                                     erreur, forme: str = '',
                                     ponderation_declaree: str = '',
                                     objet: str = 'le taux verrouillé') -> str:
    """B72 d) — le taux figé s'accorde-t-il à la forme DÉCLARÉE du groupe ?

    ⚠️⚠️ SON NOM A CHANGÉ PARCE QUE L'ANCIEN ÉTAIT FAUX. Il s'appelait
    `exiger_taux_de_la_cohorte`, et un taux verrouillé N'APPARTIENT PAS à une
    cohorte : B72 d) le fige à la COMPTABILISATION INITIALE, que §25 place où
    elle tombe. Le nom disait l'axe que le code comparait, et c'était le
    mauvais — un instrument qui affirme autre chose que ce qu'il porte, encore.

    ⚠️ LA COMPARAISON EST PAR FORME, ET CHACUNE EST EXACTE :
      · §25 — l'arrêté du taux ÉGALE la date de comptabilisation initiale
        déclarée. C'est ce que la forme signifie ;
      · B73 — l'arrêté tombe dans l'intervalle d'ÉMISSION. Une moyenne
        pondérée de valeurs de [a ; b] à poids positifs y est nécessairement.

    ⚠️ ET LA COHORTE NE BORNE PLUS RIEN : elle identifie le groupe et descend
    dans le motif, pour qu'un lecteur sache lequel a été contrôlé.
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
    _exiger_groupe_declare(groupe, erreur)
    _exiger_arrete_iso(arrete_verrouillage, f"l'arrêté de {objet}", erreur,
                       MOTIF_TAUX_POSTERIEUR_A_L_EVALUATION)
    _exiger_arrete_iso(contexte.arrete, "l'arrêté évalué", erreur,
                       MOTIF_CONTEXTE_INVALIDE)

    if arrete_verrouillage > contexte.arrete:
        raise erreur(
            MOTIF_TAUX_POSTERIEUR_A_L_EVALUATION,
            f"{objet} porte l'arrêté {arrete_verrouillage}, POSTÉRIEUR à "
            f"l'arrêté évalué {contexte.arrete}. Un taux figé à la "
            f"comptabilisation initiale ne peut pas venir d'après la date "
            f"qu'on évalue.")

    if forme == FORME_DATE_25 and arrete_verrouillage != groupe.date_25:
        raise erreur(
            MOTIF_TAUX_HORS_COMPTABILISATION_25,
            f"{objet} porte l'arrêté {arrete_verrouillage} et la forme "
            f"déclarée est {FORME_DATE_25} : le groupe se comptabilise le "
            f"{groupe.date_25} (§25). ⚠️ CETTE FORME SIGNIFIE EXACTEMENT CETTE "
            f"DATE — B72 d) fige le taux « lors de la comptabilisation "
            f"initiale ». Un arrêté qui s'en écarte relève soit de l'autre "
            f"forme ({FORME_MOYENNE_B73}), soit d'une APPROXIMATION, et ce "
            f"module refuse de deviner laquelle. ⚠️ Ce n'est PAS un contrôle "
            f"de cohorte : le groupe relève de la cohorte "
            f"{groupe.cohorte} (§22, l'émission), et sa comptabilisation "
            f"initiale peut tomber une autre année. "
            + RAISONNEMENT_DES_DEUX_AXES)

    #: ⚠️ UNE MOYENNE PONDÉRÉE QUI TOMBE LE 31 DÉCEMBRE EST SIGNALÉE, PAS
    #: REFUSÉE. Elle n'est possible que si tous les contrats du groupe ont
    #: été émis ce jour-là — cas réel mais rare. Refuser bloquerait un cas
    #: légitime ; taire laisserait passer le taux de FIN d'année déguisé en
    #: moyenne, qui est l'approximation la plus courante.
    if forme == FORME_MOYENNE_B73:
        intervalle_emission = groupe.intervalle_emission
        if not intervalle_emission or len(intervalle_emission) != 2:
            raise erreur(
                MOTIF_HORS_INTERVALLE_EMISSION,
                f"la forme {FORME_MOYENNE_B73} est déclarée pour {objet}, "
                f"mais l'intervalle d'émission du groupe n'est pas fourni "
                f"(reçu {intervalle_emission!r}). ⚠️ CE N'EST PAS UNE "
                f"EXIGENCE DE PLUS : qui a calculé une moyenne pondérée sur "
                f"l'intervalle d'émission AVAIT NÉCESSAIREMENT ces dates. On "
                f"demande ce qui a déjà servi.")
        debut, fin = intervalle_emission
        _exiger_arrete_iso(debut, "le début de l'intervalle d'émission",
                           erreur, MOTIF_HORS_INTERVALLE_EMISSION)
        _exiger_arrete_iso(fin, "la fin de l'intervalle d'émission", erreur,
                           MOTIF_HORS_INTERVALLE_EMISSION)
        if not debut <= arrete_verrouillage <= fin:
            raise erreur(
                MOTIF_HORS_INTERVALLE_EMISSION,
                f"{objet} porte l'arrêté {arrete_verrouillage}, hors de "
                f"l'intervalle d'émission [{debut} ; {fin}]. ⚠️ CE REFUS EST "
                f"EXACT, PAS PRUDENTIEL : une moyenne pondérée de valeurs de "
                f"[{debut} ; {fin}] avec des poids positifs est "
                f"NÉCESSAIREMENT dans cet intervalle. Une date hors bornes "
                f"n'est donc pas une moyenne pondérée, quoi qu'elle déclare.")
        if not est_renseigne(ponderation_declaree):
            raise erreur(
                MOTIF_PONDERATION_NON_DECLAREE,
                f"la forme {FORME_MOYENNE_B73} est déclarée pour {objet} sans "
                f"sa PONDÉRATION. ⚠️ ELLE EST ELLE-MÊME UNE DÉCISION : par la "
                f"prime, par le nombre de contrats, par les flux d'exécution "
                f"— trois pondérations défendables qui donnent trois dates. "
                f"Mesuré sur un portefeuille de démonstration : de 3 à 9 "
                f"jours d'écart, et davantage dès que la production se "
                f"concentre en fin d'exercice.")

    signal = ''
    if forme == FORME_MOYENNE_B73 and arrete_verrouillage[5:] == '12-31':
        signal = (
            " ⚠️ SIGNALEMENT, NON REFUS : une MOYENNE PONDÉRÉE annoncée qui "
            "tombe le 31 décembre n'est possible que si tous les contrats du "
            "groupe ont été émis ce jour-là. Sur des émissions étalées, une "
            "moyenne tombe vers le milieu de l'intervalle — le 31 décembre "
            "est le taux de FIN d'année, qui est une autre chose. Ce module "
            "ne peut pas trancher, faute des dates d'émission ; il signale.")

    return (f"{objet} : arrêté {arrete_verrouillage}, forme déclarée "
            f"« {forme} ». Groupe évalué — cohorte {groupe.cohorte} (§22, "
            f"l'émission), comptabilisation initiale {groupe.date_25} (§25)."
            + signal + ' ' + RAISONNEMENT_DES_DEUX_AXES
            + ' ' + CE_QUE_L_EXACTITUDE_FERME
            + ' ' + LIMITE_DES_DEUX_FORMES
            + ' ' + LIMITE_INTERVALLE_PAR_FORME
            + (' ' + RESERVE_MOYENNE_DE_TAUX
               if forme == FORME_MOYENNE_B73 else ''))
