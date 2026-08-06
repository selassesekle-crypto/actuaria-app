# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 : L'OBJET CONTRAT ET CE QUE CHAQUE CHAMP DÉBLOQUE
=============================================================================

LE VOCABULAIRE, ET RIEN D'AUTRE. Ce module ne lit aucun fichier et ne calcule
aucun montant. Il répond à une seule question : étant donné les colonnes qu'un
client a su fournir, QUELLES EXIGENCES D'IFRS 17 deviennent atteignables, et
lesquelles restent hors de portée — chacune nommée par son paragraphe.

⚠️ POURQUOI CE MODULE EXISTE. Le dépôt connaissait des SINISTRES (chaîne de
provisionnement, agrégés par année de survenance) et des POLICES TARIFÉES
(chaîne de tarification), mais aucun CONTRAT au sens d'IFRS 17. Or §22 impose
de ne pas grouper des contrats « émis à plus d'un an d'intervalle » : la
cohorte est une année de SOUSCRIPTION, quand le triangle est bâti sur l'année
de SURVENANCE. Un sinistre de 2026 peut relever d'un contrat émis en 2024 —
aucune agrégation du triangle ne reconstitue la cohorte. L'information n'est
pas perdue en aval : elle n'entre nulle part.

⚠️ CE QUE CHAQUE CHAMP DÉBLOQUE EST UNE DONNÉE, PAS UN COMMENTAIRE. C'est la
leçon de `parametres_fs.py` : un commentaire ne se vérifie pas, un champ si.
Le lecteur d'inventaire (D2) construit son diagnostic à partir d'ici, donc ce
que le client lit à l'écran et ce que le code applique ne peuvent pas diverger.

⚠️ TROIS EXIGENCES DE GÉNÉRALITÉ, TENUES ICI ET PAS AILLEURS. On ne code que
le non-vie, mais l'objet ne lui est pas taillé :
  1. la couverture n'est JAMAIS supposée inférieure à un an — `fin_couverture`
     est une date libre, un contrat pluriannuel entre et échoue proprement au
     test §53 b) au lieu d'être mesuré à tort ;
  2. une couverture à durée INDÉTERMINÉE (vie entière) se représente par
     `COUVERTURE_INDETERMINEE`, valeur DISTINCTE d'une absence de donnée —
     « pas de fin prévue » et « on ne sait pas » ne se confondent pas ;
  3. ce qu'on ne traite pas se NOMME : `participation_directe` (§45, B101 à
     B118) et `composante_investissement` (§85) permettent au contrôle de
     périmètre de refuser explicitement plutôt que de mesurer en silence.

⚠️ UNE LIGNE = UN CONTRAT **OU** UN ENSEMBLE PRÉ-AGRÉGÉ. §17 admet d'évaluer
« un ensemble de contrats » plutôt que chaque contrat. Plutôt que deux objets,
un seul portant `nb_contrats` : 1 pour un inventaire ligne à ligne, N pour un
ensemble. La granularité se lit dans la donnée.

RÉFÉRENCES
  IFRS 17 « Contrats d'assurance », annexe au règlement (UE) 2023/1803,
  JO L 237 du 26.9.2023. Chaque paragraphe cité ci-dessous a été relu dans ce
  texte.
=============================================================================
"""

from typing import Dict, FrozenSet, NamedTuple, Tuple

# =============================================================================
#  LES TROIS NIVEAUX
# =============================================================================

#: Sans lui, le client n'obtient rien d'utile.
NIVEAU_SOCLE = 'SOCLE'
#: Chacun débloque une exigence NOMMÉE, et son absence a un coût chiffrable.
NIVEAU_DEBLOQUE = 'DEBLOQUE'
#: Améliore la mesure sans conditionner aucune exigence.
NIVEAU_AMELIORE = 'AMELIORE'

NIVEAUX = (NIVEAU_SOCLE, NIVEAU_DEBLOQUE, NIVEAU_AMELIORE)

#: Couverture sans terme prévu (vie entière). ⚠️ DISTINCT d'une absence de
#: donnée : `fin_couverture` manquante veut dire « inconnue », cette valeur
#: veut dire « connue, et sans terme ». Les deux ne débloquent pas la même
#: chose — une durée indéterminée EXCÈDE un an, donc §53 b) est tranché
#: (négativement) ; une absence laisse la question ouverte.
COUVERTURE_INDETERMINEE = 'INDETERMINEE'


# =============================================================================
#  LES EXIGENCES, CHACUNE AVEC SON PARAGRAPHE
# =============================================================================

class Exigence(NamedTuple):
    """Une exigence d'IFRS 17 que la plateforme peut ou non atteindre.

    `requiert` est une conjonction de disjonctions : chaque élément est un
    groupe de champs dont AU MOINS UN doit être présent, et TOUS les groupes
    doivent être satisfaits. C'est la forme la plus simple qui exprime
    « il faut une prime ET une borne de couverture, quelle qu'elle soit ».
    """
    reference: str                       # le paragraphe, tel qu'il se cite
    libelle:   str
    requiert:  Tuple[FrozenSet[str], ...]


def _et(*groupes: Tuple[str, ...]) -> Tuple[FrozenSet[str], ...]:
    """Conjonction de groupes ; dans un groupe, un champ suffit."""
    return tuple(frozenset(g) for g in groupes)


EXIGENCES: Dict[str, Exigence] = {
    'portefeuilles': Exigence(
        '§14', "Identifier les portefeuilles de contrats",
        _et(('portefeuille',))),

    'cohortes_annuelles': Exigence(
        '§22, §25', "Ne pas grouper des contrats émis à plus d'un an "
                    "d'intervalle, et dater la comptabilisation initiale",
        _et(('date_emission',))),

    'granularite_declaree': Exigence(
        '§17', "Savoir si l'évaluation porte sur un contrat ou un ensemble",
        _et(('nb_contrats',))),

    'eligibilite_paa_verifiee': Exigence(
        '§53 b)', "Vérifier — et non déclarer — que la période de couverture "
                  "de chacun des contrats n'excède pas un an",
        _et(('fin_couverture',), ('debut_couverture', 'date_emission'))),

    'lrc': Exigence(
        '§55 a) i)', "Évaluer le passif au titre de la couverture restante",
        _et(('prime',))),

    'revenu': Exigence(
        'B126', "Affecter les encaissements de primes attendus à la période, "
                "en fonction de l'écoulement du temps",
        _et(('prime',), ('fin_couverture',),
            ('debut_couverture', 'date_emission'))),

    'frais_acquisition_dans_lrc': Exigence(
        '§55 a) ii)', "Déduire du LRC les flux liés aux frais d'acquisition "
                      "dès la comptabilisation initiale",
        _et(('frais_acquisition',))),

    'amortissement_frais_acquisition': Exigence(
        'B125', "Affecter les frais d'acquisition aux périodes et "
                "comptabiliser le même montant en charges",
        _et(('frais_acquisition',), ('fin_couverture',),
            ('debut_couverture', 'date_emission'))),

    'option_charges_acquisition': Exigence(
        '§59 a)', "Ouvrir l'option de comptabiliser les frais d'acquisition "
                  "en charges — subordonnée à une couverture d'au plus un an",
        _et(('frais_acquisition',), ('fin_couverture',),
            ('debut_couverture', 'date_emission'))),

    'classement_16a_calcule': Exigence(
        '§47, §16 a), §18', "Établir sur des chiffres qu'un groupe est "
                            "déficitaire à l'origine, plutôt que de s'en "
                            "remettre à la présomption de §18",
        _et(('sinistres_attendus',), ('prime',))),

    'classement_16_declare': Exigence(
        '§16', "Recevoir du client le classement en groupes de profitabilité",
        _et(('classe_profitabilite',))),

    'multi_entites': Exigence(
        '§78', "Produire un jeu d'états par entité juridique",
        _et(('entite',))),

    'controle_devise': Exigence(
        '§30', "Vérifier qu'une entité ne change pas de monnaie d'un arrêté "
               "à l'autre — aucune conversion n'est pratiquée",
        _et(('devise',))),

    'signalement_participation_directe': Exigence(
        '§45, B101-B118', "Reconnaître les contrats avec éléments de "
                          "participation directe pour les refuser "
                          "explicitement — hors périmètre",
        _et(('participation_directe',))),

    'signalement_composante_investissement': Exigence(
        '§85', "Reconnaître une composante d'investissement à exclure des "
               "produits des activités d'assurance",
        _et(('composante_investissement',))),
}


# =============================================================================
#  LES CHAMPS
# =============================================================================

class ChampContrat(NamedTuple):
    """Un champ de l'inventaire de contrats.

    `scelle` marque les champs qui fixent l'unité de compte à la naissance du
    groupe. §16, §22 et §53 s'apprécient tous « à la date de la création du
    groupe » : une erreur sur ces champs n'est pas rattrapable à l'arrêté
    suivant, elle est dans le registre. Le lecteur ne les accepte donc jamais
    sur la seule foi d'un synonyme (voir D2).
    """
    niveau:  str
    libelle: str
    scelle:  bool = False


CHAMPS: Dict[str, ChampContrat] = {
    # ── Socle — sans eux, rien d'utile ───────────────────────────────────────
    'portefeuille': ChampContrat(
        NIVEAU_SOCLE,
        "Regroupement de contrats à risques similaires, gérés ensemble",
        scelle=True),
    'date_emission': ChampContrat(
        NIVEAU_SOCLE,
        "Date d'émission du contrat — NI la survenance, NI la comptabilisation",
        scelle=True),
    'prime': ChampContrat(
        NIVEAU_SOCLE,
        "Prime attendue sur toute la période de couverture"),
    'nb_contrats': ChampContrat(
        NIVEAU_SOCLE,
        "1 pour un contrat, N pour un ensemble pré-agrégé (§17)"),

    # ── Débloquent une exigence nommée ───────────────────────────────────────
    'debut_couverture': ChampContrat(
        NIVEAU_DEBLOQUE, "Date de début de la période de couverture"),
    'fin_couverture': ChampContrat(
        NIVEAU_DEBLOQUE,
        "Date de fin de couverture, ou COUVERTURE_INDETERMINEE"),
    'frais_acquisition': ChampContrat(
        NIVEAU_DEBLOQUE,
        "Flux de trésorerie liés aux frais d'acquisition du contrat"),
    'sinistres_attendus': ChampContrat(
        NIVEAU_DEBLOQUE,
        "Charge de sinistres attendue à la souscription"),
    'classe_profitabilite': ChampContrat(
        NIVEAU_DEBLOQUE,
        "Classement §16 fourni par le client quand il n'est pas calculable",
        scelle=True),
    'entite': ChampContrat(
        NIVEAU_DEBLOQUE, "Entité juridique qui publie les états"),
    'devise': ChampContrat(
        NIVEAU_DEBLOQUE, "Monnaie du contrat — jamais convertie"),
    'participation_directe': ChampContrat(
        NIVEAU_DEBLOQUE,
        "Le contrat comporte des éléments de participation directe"),
    'composante_investissement': ChampContrat(
        NIVEAU_DEBLOQUE,
        "Le contrat comporte une composante d'investissement"),

    # ── Améliorent sans rien débloquer ───────────────────────────────────────
    'identifiant_contrat': ChampContrat(
        NIVEAU_AMELIORE, "Référence du contrat — traçabilité, doublons"),
    'prime_encaissee': ChampContrat(
        NIVEAU_AMELIORE,
        "Prime réellement reçue, distincte de la prime attendue"),
    'date_resiliation': ChampContrat(
        NIVEAU_AMELIORE, "Fin anticipée — affine la couverture restante"),
    'groupe_declare': ChampContrat(
        NIVEAU_AMELIORE, "Regroupement imposé par le client (§17)"),
    'traite_lie': ChampContrat(
        NIVEAU_AMELIORE,
        "Traité de réassurance couvrant ce contrat — prépare §60-70A"),
}


# =============================================================================
#  FONCTIONS PUBLIQUES — UNE PAR QUESTION
# =============================================================================

def champs_du_niveau(niveau: str) -> Tuple[str, ...]:
    """Les champs d'un niveau donné, triés. Lève sur un niveau inconnu."""
    if niveau not in NIVEAUX:
        raise KeyError(
            f"Niveau inconnu : « {niveau} ». Les niveaux sont "
            f"{', '.join(NIVEAUX)}.")
    return tuple(sorted(c for c, d in CHAMPS.items() if d.niveau == niveau))


def champs_scelles() -> Tuple[str, ...]:
    """Les champs qui fixent l'unité de compte et ne se corrigent plus.

    §16, §22 et §53 s'apprécient « à la date de la création du groupe ». Le
    lecteur doit les faire CONFIRMER avant de sceller un registre.
    """
    return tuple(sorted(c for c, d in CHAMPS.items() if d.scelle))


def champs_bloquants() -> Tuple[str, ...]:
    """Les champs dont l'absence fait REFUSER la lecture.

    ⚠️ C'EST LE REFUS QUI DÉFINIT LE PRODUIT. Sans `date_emission` il n'y a
    aucune cohorte (§22), et l'exemption de l'article 2 du règlement (UE)
    2023/1803 est fermée au non-vie — elle ne vise que les contrats à
    participation directe et l'ajustement égalisateur, c'est-à-dire la vie.
    Produire des groupes sans cohortes livrerait la non-conformité même que
    ce socle corrige, sous une étiquette conforme. Sans `portefeuille`, il n'y
    a pas de portefeuille au sens de §14, seulement un tas.

    Tout le reste ne refuse pas : le diagnostic chiffre ce qui est faisable.
    """
    return ('date_emission', 'portefeuille')


def capacites(champs_presents) -> Dict[str, bool]:
    """Exigence par exigence : atteignable ou non, à partir des champs fournis.

    Le pendant de `_capacites_depuis_champs` de la couche triangle, étendu du
    booléen au catalogue nommé. Les champs inconnus sont ignorés en silence :
    un client a le droit d'avoir des colonnes qui ne nous concernent pas.
    """
    presents = {c for c in champs_presents if c in CHAMPS}
    return {nom: all(bool(groupe & presents) for groupe in ex.requiert)
            for nom, ex in EXIGENCES.items()}


def exigences_hors_portee(champs_presents) -> Dict[str, Tuple[str, ...]]:
    """Ce qui reste inatteignable, et LE CHAMP QUI MANQUE pour chacune.

    Existe pour que le diagnostic dise le COÛT d'une absence plutôt que de la
    taire : « pas de frais d'acquisition » ne veut rien dire pour un client,
    « §55 a) ii) et B125 hors de portée » se comprend et se corrige.
    """
    presents = {c for c in champs_presents if c in CHAMPS}
    manquantes = {}
    for nom, ex in EXIGENCES.items():
        absents = tuple(sorted(
            c for groupe in ex.requiert if not (groupe & presents)
            for c in groupe))
        if absents:
            manquantes[nom] = absents
    return manquantes


def reference(exigence: str) -> str:
    """Ce qu'il faut CITER dans un livrable pour une exigence donnée."""
    if exigence not in EXIGENCES:
        raise KeyError(
            f"Exigence inconnue : « {exigence} ». Les {len(EXIGENCES)} "
            f"exigences sont {', '.join(sorted(EXIGENCES))}.")
    ex = EXIGENCES[exigence]
    return f"IFRS 17 {ex.reference} — {ex.libelle}"
