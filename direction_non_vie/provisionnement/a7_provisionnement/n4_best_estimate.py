# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n4_best_estimate.py  —  Best Estimate S2 + SCR provisions
# =============================================================================
#
#  Références réglementaires
#  -------------------------
#  Directive Solvabilité II (2009/138/CE), Art. 77 :
#    Best Estimate = espérance de la valeur actuelle des flux futurs.
#    ⚠️ A7 calcule ici la RÉSERVE BRUTE (non actualisée). L'actualisation à la
#    courbe RFR EIOPA — la « valeur actuelle » au sens de l'Art. 77 — est opérée
#    en aval par A10 (Solvabilité 2) et A11 (IFRS 17, à son propre taux).
#
#    ⚠️ BRUTE AU SECOND SENS AUSSI : brute de RÉASSURANCE. Cela a une
#    conséquence sur le SCR, et elle est chiffrable. L'Art. 116(6) du
#    Règlement délégué définit la mesure de volume du risque de réserve
#    comme la meilleure estimation des provisions pour sinistres à payer
#    « après déduction des montants recouvrables au titre des contrats de
#    réassurance et des véhicules de titrisation ». Le SCR publié ici
#    s'applique donc à une assiette PLUS LARGE que celle du texte : c'est un
#    MAJORANT, d'autant plus élevé que la cession est importante. La
#    réassurance n'est pas dans le périmètre d'A7 — A10 opère en aval.
#
#  Règlement Délégué (UE) 2015/35, Art. 115 à 117 :
#    SCR provisions Non-Vie = formule standard par segment
#    (l'Art. 105 DU RÈGLEMENT porte sur le risque de spread des captives —
#     la confusion venait de l'Art. 105 de la DIRECTIVE 2009/138/CE)
#
#  EIOPA Guidelines on valuation of technical provisions (2014) :
#    TP.5.26 — distribution log-normale pour IBNR
#    Statut : CV < 10% VERT | 10-20% AMBRE | > 20% ROUGE
#
#  Formules implémentées
#  ---------------------
#
#  Best Estimate — réserve brute (Art. 77 ; actualisation S2 en aval, A10)
#  ────────────────────────
#  Combinaison des méthodes actuarielles admises, ANNÉE PAR ANNÉE :
#
#      BE = Σ_i Σ_{m ∈ M_inc(i)} w[m,i] × R[m,i]     avec Σ_m w[m,i] = 1
#
#  où  M_inc(i) = méthodes admises pour l'année i — cf. `selectionner_et_agreger`
#      w[m,i]   = 1 / |M_inc(i)|   (POIDS ÉGAUX, choix assumé : ni le guide de
#                 l'Institut des Actuaires ni Mack ne disent comment pondérer
#                 plusieurs méthodes entre elles)
#      R[m,i]   = IBNR de l'année i estimé par la méthode m
#
#  Percentiles log-normale (QIS5 TP.5.26)
#  ────────────────────────────────────────
#  σ = σ_Mack (incertitude de réserve totale Mack 1993)
#
#      σ_LN = √(ln(1 + (σ/BE)²))
#      μ_LN = ln(BE) - σ²_LN / 2
#      P_α  = exp(μ_LN + z_α × σ_LN)
#
#  SCR provisions formule standard (Art. 115 Rgt délégué 2015/35)
#  ───────────────────────────────────────────────
#  Pour une seule LoB :
#
#      SCR_prov(LoB) = 3 × σ(LoB) × BE(LoB)
#
#  Pour plusieurs LoB, agrégation avec matrice de corrélation EIOPA :
#
#      SCR_NL = √(Σ_{i,j} ρ_{ij} × SCR_i × SCR_j)
#
#  où σ(LoB) est l'écart type du risque de RÉSERVE du segment (annexe II pour
#  le non-vie, annexe XIV pour la santé non-SLT) et ρ_{ij} la corrélation
#  entre LoB i et j (Annexe IV, Rgt 2015/35).
#
#  Le σ est celui de la réserve et non celui des primes parce que l'Art. 117(2)
#  se réduit exactement à σ_réserve quand la mesure de volume des primes est
#  nulle — c'est le cas d'un agent qui provisionne des sinistres survenus.
#  Démonstration et source dans l'en-tête de `config/lob_config.py`.
#
# =============================================================================

import logging
from datetime import datetime
# `Any` manquait alors que `Dict[str, Any]` est annoté deux fois (l. 316 et
# 368). Sur Python 3.14 les annotations ne sont plus évaluées à la définition
# (PEP 649) et rien ne plantait ; sur Python <= 3.13 le module levait
# `NameError` DÈS L'IMPORT. Trouvé par ruff (F821), invisible à l'exécution.
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .config.lob_config import get_lob_config, get_sigma_eiopa, reference_s2
from .methodes_be       import _CLES_N3, _LIBELLE_METHODE
from .n2_hypotheses_bootstrap import lignes_hypotheses_bootstrap
from .config.rfr_eiopa  import (get_taux_rfr, DATE_COURBE,
                                get_courbe_embarquee, diagnostic_peremption)

logger = logging.getLogger('actuaria.a7')


def garde_fou_be_negatif(be_final: float) -> Optional[Dict]:
    """Garde-fou TOTAL : si le Best Estimate final est <= 0 (reprise nette), les
    agrégats S2 deviennent mathématiquement absurdes — SCR = 3σ×BE devient négatif,
    le ratio SCR/max(BE,1e-9) explose, la log-normale des percentiles n'est pas
    définie. Retourne alors un descriptif ROUGE + marqueurs 'non calculable' (None) ;
    retourne None si BE > 0 (l'appelant calcule normalement).

    Le BE négatif n'est JAMAIS écrasé en silence (aucun plancher caché) : il est
    signalé pour revue actuarielle. Le point estimate BE lui-même reste tel quel."""
    if be_final > 0:
        return None
    return {
        'be_negatif':               True,
        'statut':                   'ROUGE',
        'message': ("BE brut négatif — reprise nette, SCR/RM non calculables sur "
                    "BE négatif, revue actuaire impérative."),
        'scr_provisions':           None,
        'ratio_scr_be':             None,
        'reserve_p75':              None,
        'reserve_p90':              None,
        'reserve_p99_5':            None,
        'risk_margin':              None,
        'ratio_rm_be':              None,
        'provisions_techniques_s2': None,
    }


# Message UNIQUE affiché par les livrables N5 quand les agrégats S2 ne sont pas
# calculables (BE négatif). Source unique — ne pas dupliquer dans N5.
MSG_S2_NON_CALCULABLE = (
    "Agrégats S2 NON CALCULABLES — Best Estimate négatif (reprise nette) : SCR, "
    "Risk Margin, provisions techniques et percentiles ne sont pas définis sur un "
    "BE négatif. Revue actuaire impérative avant toute inscription au bilan."
)


def s2_non_calculable(n4: Dict) -> bool:
    """True si les agrégats S2 (SCR / Risk Margin / PT / percentiles) sont non
    calculables parce que le Best Estimate est négatif (cf. garde_fou_be_negatif).

    Les générateurs N5 (commentaire, rapport, Excel, graphiques) doivent alors
    afficher MSG_S2_NON_CALCULABLE AU LIEU des chiffres : aucune valeur None ne
    doit atteindre un formatage ou un calcul. Source UNIQUE partagée par les 4."""
    return bool(n4.get('be_negatif'))


# =============================================================================
#  SÉLECTION PAR ANNÉE DE SURVENANCE  (lot B — remplace le gate par score)
# =============================================================================

#: ⚠️ `_CLES_N3` EST IMPORTÉ DE `methodes_be` DEPUIS LE LOT C3a — il était
#: recopié six fois dans la couche N5, et chacune des copies produisait un
#: « 0 € » sur une méthode non calculable. Le référentiel y explique pourquoi
#: les trois méthodes du BE partagent le même motif de développement.
#: `PORTEURS_DE_CIBLE`, juste dessous, RESTE ici : c'est de la gouvernance,
#: écrite tout entière en termes de « dans / hors `_CLES_N3` ».

#: REGISTRE DES PORTEURS — LE VRAI LIVRABLE DU LOT « MACK ».
#:
#: ⚠️ QUATRE FOIS DE SUITE, ON EST TOMBÉ SUR LE MÊME MOTIF : une hypothèse
#: déclare une cible qui n'est pas une méthode du Best Estimate, et personne ne
#: sait quoi en faire. BOOT-H3/H4, MCL-H5, puis CLM-H3. À chaque fois on l'a
#: redécouvert par hasard. Ce registre existe pour qu'il n'y ait pas de
#: cinquième fois — et le test qui l'applique compte plus que le registre.
#:
#: LA RÈGLE, EN TROIS CAS :
#:   · cible DANS `_CLES_N3`  → le circuit du Best Estimate (exclusion, ou
#:     « à justifier » qui plafonne le VERT) ;
#:   · cible HORS `_CLES_N3`  → un PORTEUR DÉCLARÉ obligatoire, qui retire ou
#:     étiquette la sortie concernée ;
#:   · pas de porteur         → l'hypothèse DOIT déclarer `critique_pour=()`
#:     et s'assumer descriptive.
#:
#: Le troisième cas n'est pas un trou : il LÉGITIME le descriptif. CLM-H1,
#: BFCC-H3, BOOT-H1/H2 et MCL-H1..H4 déclarent une cible vide et l'assument.
#: Ce que le registre interdit, c'est le quatrième cas — gatante sur le papier,
#: inerte en fait. C'est exactement ce qu'était le drapeau de MCL-H5.
PORTEURS_DE_CIBLE = {
    # ── Cibles DANS `_CLES_N3` : le circuit du Best Estimate ────────────────
    'chain_ladder':         "circuit du BE — `_HYPOTHESES_BLOQUANTES` et "
                            "`_hypotheses_a_justifier`, plus le filet par année",
    'bornhuetter_ferguson': "circuit du BE — exclusion par BFCC-H4",
    'cape_cod':             "circuit du BE — exclusion par BFCC-H5 et BFCC-H6",

    # ── Cibles HORS `_CLES_N3` : chacune a son porteur nommé ────────────────
    'mack':                 "le circuit du BE VIA `chain_ladder` — le point "
                            "estimate de Mack VAUT Chain Ladder (commit "
                            "6e2e66e) : ce qui traite l'un traite l'autre. "
                            "Seule son INCERTITUDE a besoin d'un porteur "
                            "propre, et c'est `percentiles_mack`",
    'percentiles_mack':     "`n2_hypotheses_clm.percentiles_mack_publiables` — "
                            "retire la colonne comparative et fait basculer la "
                            "mesure principale, dans `BestEstimateS2.calculer`",
    'percentiles_bootstrap':"`n2_hypotheses_bootstrap.percentiles_publiables` — "
                            "met `reserve_p*_boot` à None",
    'reserve_munich':       "la garde `n3.munich_cl.valider_prerequis`, EN "
                            "AMONT — elle rend Munich indisponible avant même "
                            "que l'hypothèse ne soit évaluée",
}


#: ⚠️ `_LIBELLE_METHODE` EST IMPORTÉ DE `methodes_be` DEPUIS LE LOT C3a. Son
#: commentaire d'origine annonçait la dette : « Source unique pour ce module ;
#: la couche N5 aura la sienne au lot C ». Elle n'en a pas eu une autre, elle
#: partage désormais celle-ci.

#: Conséquences EFFECTIVEMENT appliquées, telles que la trace les nomme. Ce
#: sont des constantes et non des chaînes écrites sur place : la trace doit
#: pouvoir être filtrée par conséquence, pas seulement lue.
_CONSEQ_FILET        = 'FILET — année portée par une seule méthode'
_CONSEQ_SIGNALEMENT  = 'signalement — toutes les méthodes conservées'
_CONSEQ_CADENCE      = 'retrait ciblé — Bornhuetter-Ferguson et Cape Cod'

#: Méthode du filet de sécurité : celle qui ne suppose aucun a priori exogène.
_METHODE_FILET = 'chain_ladder'


#: Hypothèses BFCC dont un verdict NON VALIDÉE écarte GLOBALEMENT une méthode.
#: BFCC-H2 n'y figure PAS : elle se juge année par année (cf.
#: `couverture_cadence`), une seule année à recours ne disqualifiant pas les
#: autres. BFCC-H1 et BFCC-H3 non plus : la première est reprise de CLM-H1, que
#: le guide traite en signalement et non en rejet ; la seconde est descriptive.
#: BFCC-H6 rejoint BFCC-H5 sur Cape Cod (lot F1) : la première teste une DÉRIVE
#: du loss ratio, la seconde son NIVEAU. Deux conditions distinctes, deux
#: remèdes distincts — un recalage « as-if » d'un côté, la vérification de
#: l'exposition de l'autre. Le contrôle de niveau n'existait qu'en alerte, et
#: la valeur hors plage était écrêtée puis utilisée : Cape Cod entrait au Best
#: Estimate avec une réserve bâtie sur une borne.
_HYPOTHESES_BLOQUANTES = {
    'bornhuetter_ferguson': ('BFCC-H4',),
    'cape_cod':             ('BFCC-H5', 'BFCC-H6'),
}


def _hypotheses_a_justifier(n2: Dict, methodes_incluses: Dict) -> List[str]:
    """Hypothèses en À JUSTIFIER qui portent sur une méthode RETENUE.

    ⚠️ DEUX FAMILLES DEPUIS LE LOT A1, ET C'EST TOUT CE QUI PEUT L'ÊTRE. Ce
    circuit ne lisait que BFCC : les verdicts de Chain Ladder et Mack n'avaient
    donc AUCUN effet sur le statut, quel qu'il soit. CLM le rejoint.

    Les deux autres familles NE PEUVENT PAS rejoindre ce circuit, et ce n'est
    pas un oubli : le filtre exige qu'une cible de `critique_pour` figure dans
    `methodes_incluses`, qui ne contient que les trois clés de `_CLES_N3`.
    · BOOT-H3/H4 visent `percentiles_bootstrap` — elles ont DÉJÀ leur
      conséquence propre, `percentiles_publiables`, appliquée l. 562.
    · MCL-H5 vise `reserve_munich` — informative, la circularité étant bloquée
      en amont par `valider_prerequis`.
    · CLM-H3 vise `mack` seul, qui n'est pas dans `_CLES_N3` : elle est donc
      DESCRIPTIVE ici, exactement comme BOOT-H3/H4 le seraient. Sa traduction
      par année, `couverture_volatilite`, est désormais PUBLIÉE (l. ~420) au
      lieu d'être calculée et jetée — mais elle ne gate rien, et lui donner un
      effet demanderait de décider ce qu'un percentile Mack non opposable doit
      produire. Ce n'est pas ce lot.

    Le filtre par méthode est essentiel : une hypothèse à justifier sur une
    méthode déjà écartée du Best Estimate n'a plus de conséquence sur lui, et
    plafonner son statut pour cela reviendrait à sanctionner deux fois.

    ⚠️ UNE HYPOTHÈSE À `critique_pour` VIDE NE PLAFONNE RIEN. C'est le sens même
    du champ : elle est DESCRIPTIVE, aucune méthode n'est invalidée si elle tombe.
    C'est le cas de BFCC-H3, qui republie le test calendaire du GLM Poisson APC
    sans lui donner d'effet décisionnel dans ce lot.
    """
    hyps = dict(n2.get('bfcc', {}).get('hypotheses', {}))
    hyps.update(n2.get('clm', {}).get('hypotheses', {}))
    return sorted(
        code for code, h in hyps.items()
        if h.get('statut') == 'À JUSTIFIER'
        and any(m in methodes_incluses for m in (h.get('critique_pour') or []))
    )


#: Formulé en CONSÉQUENCE et en action possible, pas en reproche : l'a priori
#: dérivé est l'une des cinq voies du guide (§2.b.i p14), pas une faute.
MSG_NIVEAU_ANCRE_CL = (
    "🟡 Le NIVEAU du Best Estimate remonte entièrement à Chain Ladder : aucune "
    "méthode retenue n'apporte d'estimation du niveau extérieure au triangle. "
    "Bornhuetter-Ferguson, dont l'a priori est ici dérivé des ultimes matures, "
    "corrige la répartition entre années sans en corriger le niveau. Fournir un "
    "loss ratio a priori (tarification, plan à moyen terme, benchmark de marché, "
    "jugement d'expert — guide IA 2023 §2.b.i p14) ou une charge ultime a priori "
    "donnerait au Best Estimate un second avis indépendant."
)


def _niveau_ancre_sur_chain_ladder(n3: Dict, methodes_incluses: Dict) -> bool:
    """Le NIVEAU du Best Estimate remonte-t-il entièrement à Chain Ladder ?

    Vrai quand aucune méthode retenue n'apporte d'estimation du niveau qui soit
    extérieure au triangle :
      · Chain Ladder, par définition, n'en apporte pas ;
      · Bornhuetter-Ferguson n'en apporte que si son a priori est EXOGÈNE —
        loss ratio fourni (`manuel`) ou charge ultime fournie (`ultime_apriori`).
        Dérivé des ultimes matures (`matures`), il est une lecture de Chain
        Ladder de plus.
      · Cape Cod, elle, estime son loss ratio sur le rapport entre sinistres
        observés et EXPOSITION FOURNIE : sa présence suffit à sortir de l'ancrage.

    Ce n'est pas un jugement sur la qualité de BF — l'a priori dérivé est l'une
    des cinq voies du guide (§2.b.i p14) — mais sur ce que la moyenne des
    méthodes couvre réellement.
    """
    if not methodes_incluses:
        return False
    if 'cape_cod' in methodes_incluses:
        return False
    if 'bornhuetter_ferguson' in methodes_incluses:
        source = str(n3.get('bf', {}).get('source_lr', ''))
        if source in ('manuel', 'ultime_apriori'):
            return False
    return True


def _admissibilite_globale(
    n2:             Dict,
    n3:             Dict,
    methodes_dispo: Dict[str, float],
) -> Tuple[Dict[str, float], Dict[str, Tuple[float, str]]]:
    """Quelles méthodes sont admissibles AVANT même de regarder les années.

    · Chain Ladder est toujours admissible : elle ne repose sur aucun a priori
      exogène, et c'est elle qui porte le filet de sécurité.
    · Bornhuetter-Ferguson et Cape Cod sont jugées sur les hypothèses QUI LEUR
      SONT PROPRES — BFCC-H4 pour la provenance et la plausibilité du loss ratio
      a priori, BFCC-H5 pour sa stabilité dans le temps. Un statut NON VALIDÉE
      écarte la méthode ; À JUSTIFIER la conserve et plafonne le statut du BE.
    · Une méthode qui s'est déclarée NON CALCULÉE (`disponible = False`) est
      écartée d'emblée. C'est le cas de Bornhuetter-Ferguson et de Cape Cod
      quand aucune mesure d'exposition n'est fournie : elles refusent de
      produire un chiffre plutôt que d'en inventer un. Le test porte sur ce
      drapeau et NON sur une réserve nulle — une réserve nulle peut être un
      résultat parfaitement légitime.
    · Une réserve non finie reste un échec de calcul, pas un jugement.

    ⚠️ PLUS AUCUN SCORE. `scores_confiance` a disparu avec l'ancienne H3 qui
    l'alimentait seule. Ce qu'il apportait — un nombre sur 100 comparé à un
    seuil — était une apparence de calibration : il ne dépendait que du
    coefficient de variation du loss ratio, ignorait le contrôle de plage
    pourtant calculé à côté, et laissait passer un loss ratio de 364,7 % avec
    81/100. Un statut motivé dit la même chose sans prétendre la mesurer.

    POURQUOI BFCC-H5 BLOQUE CAPE COD ET PAS BORNHUETTER-FERGUSON. Cape Cod met
    en commun UN loss ratio unique sur toutes les années d'origine (Bühlmann &
    Straub 1983) : une dérive le rend trop bas pour les années récentes, celles
    qui portent l'essentiel de la réserve. L'a priori de BF est par année — la
    dérive s'y corrige par un recalage « as-if », elle ne l'invalide pas.
    """
    statuts  = n2.get('bfcc', {}).get('statuts', {})
    admises: Dict[str, float] = {}
    exclues: Dict[str, Tuple[float, str]] = {}
    for m, r in methodes_dispo.items():
        bloquantes = [h for h in _HYPOTHESES_BLOQUANTES.get(m, ())
                      if statuts.get(h) == 'NON VALIDÉE']
        if not n3.get(_CLES_N3[m], {}).get('disponible', True):
            exclues[m] = (r, 'non calculée')
        elif not np.isfinite(r) or r == 0:
            exclues[m] = (r, 'réserve nulle ou non finie')
        elif bloquantes:
            exclues[m] = (r, ' et '.join(bloquantes) + ' NON VALIDÉE')
        else:
            admises[m] = float(r)
    return admises, exclues


def _trace_gouvernance(
    n2:        Dict,
    detail:    List[Dict[str, Any]],
    be:        float,
) -> List[Dict[str, Any]]:
    """Une entrée par (année, hypothèse en défaut) — TOUT est sourcé.

    ⚠️ AUCUN CALCUL NEUF, UNE JOINTURE. Chaque champ est repris d'un endroit
    qui l'a déjà produit et publié : le détail PAR COLONNE de CLM-H2
    (`ordonnee`, `p_ordonnee`), les colonnes traversées par chaque année
    (`couvertures`), et la contribution de l'année au Best Estimate calculée
    par `selectionner_et_agreger`. Rien n'est saisi, rien n'est rédigé à la
    main : c'est ce qui permet à la trace d'être opposable.

    ⚠️ POURQUOI LES DEUX DERNIERS CHAMPS CHANGENT TOUT. Sans
    `contribution_eur` et `part_du_be`, la trace dit « l'année 9 est sous
    filet » — une curiosité. Avec, elle dit « 26,3 % de votre provision repose
    sur une hypothèse démentie ». Mesuré sur GenIns : les années en défaut
    portent 15 324 384 EUR, soit 87,2 % du Best Estimate, et RIEN dans les
    livrables ne le disait avant ce lot.

    Deux mécanismes par année produisent une entrée, et ce sont les deux seuls
    qui aient aujourd'hui une conséquence par année :
      · CLM-H2 via `couverture_motif` — le motif de développement ;
      · BFCC-H2 via `couverture_cadence` — la cadence, qui retire BF et
        Cape Cod sur l'année concernée.
    """
    clm  = n2.get('clm', {})
    h2   = (clm.get('hypotheses', {}) or {}).get('CLM-H2', {}) or {}
    par_colonne = {d.get('colonne'): d for d in (h2.get('detail') or ())}
    couverture  = {a['annee']: a
                   for a in (clm.get('couvertures', {}) or {}).get('annees', [])}
    cadence     = (n2.get('bfcc', {}) or {}).get('couverture_cadence', {}) or {}

    trace: List[Dict[str, Any]] = []
    for d in detail:
        i    = d['annee']
        part = (d['contribution'] / be) if be else 0.0

        # ── CLM-H2 : le motif de développement, colonne par colonne ─────────
        if d['motif'] in ('À JUSTIFIER', 'NON VALIDÉE'):
            traversees = (couverture.get(i, {}) or {}).get('colonnes_traversees', [])
            # La colonne EN CAUSE est la pire de celles que l'année doit
            # encore traverser — c'est elle qui a fixé la couverture.
            pires = [par_colonne[j] for j in traversees
                     if par_colonne.get(j, {}).get('statut') == d['motif']]
            col = pires[0] if pires else {}
            trace.append({
                'annee':             i,
                'hypothese':         'CLM-H2',
                'statut':            d['motif'],
                'portee':            (f"colonne {col.get('colonne')}"
                                      if col else 'colonnes traversées'),
                'statistique':       (
                    f"ordonnée à l'origine = {col['ordonnee']:,.0f} €"
                    .replace(',', ' ') if col.get('ordonnee') is not None
                    else 'non publiée'),
                'valeur':            col.get('p_ordonnee'),
                'seuil':             ('p < 0,01' if d['motif'] == 'NON VALIDÉE'
                                      else 'p < 0,05'),
                'consequence':       (_CONSEQ_FILET if d['sous_filet']
                                      else _CONSEQ_SIGNALEMENT),
                'methodes_retenues': list(d['methodes']),
                'contribution_eur':  round(float(d['contribution']), 2),
                'part_du_be':        round(part, 4),
            })

        # ── BFCC-H2 : la cadence, qui retire BF et Cape Cod ─────────────────
        if d['cadence_ko']:
            trace.append({
                'annee':             i,
                'hypothese':         'BFCC-H2',
                'statut':            str(cadence.get(i, 'NON VALIDÉE')),
                'portee':            f"année {i}",
                'statistique':       'cadence brute hors de [0 ; 1]',
                'valeur':            None,
                'seuil':             'appartenance à [0 ; 1], non écrêtée',
                'consequence':       _CONSEQ_CADENCE,
                'methodes_retenues': list(d['methodes']),
                'contribution_eur':  round(float(d['contribution']), 2),
                'part_du_be':        round(part, 4),
            })
    return trace


def _methodes_de_lannee(
    i:          int,
    admises:    Dict[str, float],
    ibnr:       Dict[str, np.ndarray],
    sous_filet: bool,
    cadence_ko: bool,
) -> List[str]:
    """Méthodes retenues pour l'année `i`, après les deux retraits par année.

    · FILET (motif non validé) → Chain Ladder seule : les hypothèses qui fondent
      un coefficient de passage sont démenties sur le parcours de cette année.
    · CADENCE non admissible → Bornhuetter-Ferguson et Cape Cod partent, Chain
      Ladder reste. Retrait CIBLÉ et non filet : ce n'est pas le motif de
      développement qui est en cause, c'est la forme de ces deux méthodes, qui
      multiplient `1 − α` par un a priori et ne peuvent donc rendre qu'un zéro
      là où le cumulé redescend.

    Les deux se composent : sous filet, Chain Ladder survit dans les deux cas.
    """
    # ⚠️ RÈGLE ÉCRITE GÉNÉRIQUEMENT, MAIS SA PORTÉE RÉELLE EST DITE (lot A2).
    # Le filet désigne UNE méthode, lue dans `_METHODE_FILET` et non écrite en
    # dur ici — la structure survivra donc à un changement de filet.
    #
    # MAIS AUJOURD'HUI CETTE MÉTHODE NE PEUT ÊTRE QUE CHAIN LADDER, et le taire
    # serait pire que de ne pas généraliser. `_admissibilite_globale` l'énonce :
    # « Chain Ladder est toujours admissible […] c'est elle qui porte le filet ».
    # Les deux seules causes d'année mono-méthode y mènent mécaniquement : le
    # filet pose `[_METHODE_FILET]`, et la cadence retire les deux clés de
    # `_HYPOTHESES_BLOQUANTES` — Bornhuetter-Ferguson et Cape Cod. Mesuré sur
    # les cinq scénarios de référence : les onze années mono-méthode sont TOUTES
    # Chain Ladder, et c'est structurel, pas conjoncturel.
    #
    # Du code générique d'apparence qui masque un cas particulier est un piège :
    # c'était exactement le drapeau `reserve_publiable` de MCL-H5.
    candidates = [_METHODE_FILET] if sous_filet else list(admises)
    if cadence_ko:
        candidates = [m for m in candidates if m not in _HYPOTHESES_BLOQUANTES]
    return [m for m in candidates if m in ibnr and np.isfinite(ibnr[m][i])]


def selectionner_et_agreger(
    n2:             Dict,
    n3:             Dict,
    methodes_dispo: Dict[str, float],
) -> Dict[str, Any]:
    """Best Estimate agrégé ANNÉE PAR ANNÉE selon les couvertures.

        BE = Σ_i Σ_m w[m,i] · R[m,i]      avec Σ_m w[m,i] = 1 pour chaque i

    RÈGLE PAR ANNÉE
    ---------------
    · `couverture_motif[i]` NON VALIDÉE → FILET : Chain Ladder seule pour cette
      année, et le statut passe au ROUGE. Les hypothèses qui fondent un
      coefficient de passage sont démenties sur le parcours de cette année : on
      ne prétend pas la couvrir par une moyenne de trois méthodes qui reposent
      toutes sur ce même coefficient.
    · `couverture_cadence[i]` NON VALIDÉE → Bornhuetter-Ferguson et Cape Cod
      SEULES sont retirées de cette année, Chain Ladder la porte. La cadence y
      dépasse 1 : le cumulé redescend, et les deux méthodes qui multiplient
      `1 − α` par un a priori ne peuvent structurellement y rendre qu'un zéro
      là où Chain Ladder rend la reprise. CE N'EST PAS LE FILET — le motif de
      développement n'est pas en cause, la seule forme de BF et Cape Cod l'est.
      Le statut ne passe donc pas au ROUGE de ce seul fait.
    · Chain Ladder elle-même incalculable pour l'année → aucune projection n'a
      de sens : l'année sort de l'agrégation et un ROUGE DUR est levé, appelant
      une évaluation dossier par dossier.
    · Sinon → toutes les méthodes globalement admises, À POIDS ÉGAL.

    POURQUOI DES POIDS ÉGAUX — décision assumée, pas une formule calibrée. La
    pondération précédente (`score/Σscores`, plus un plancher de 50 % à la
    méthode dite recommandée) n'avait aucun fondement théorique : ni le guide de
    l'Institut des Actuaires ni Mack ne disent comment pondérer plusieurs
    méthodes entre elles. Des poids égaux disent honnêtement « aucune base pour
    préférer l'une » ; une formule donnait l'apparence d'une calibration.

    IDENTITÉ VÉRIFIABLE : si aucune année n'est sous filet et que les mêmes
    méthodes sont admises partout, `Σ_i Σ_m w·R[m,i] = Σ_m w·R[m]` — le résultat
    se réduit exactement à une moyenne pondérée des totaux.
    """
    admises, exclues = _admissibilite_globale(n2, n3, methodes_dispo)

    ibnr = {}
    for m in list(admises):
        valeurs = n3.get(_CLES_N3[m], {}).get('ibnr_par_annee')
        if valeurs is None:
            exclues[m] = (methodes_dispo[m], "aucun IBNR par année publié")
            del admises[m]
        else:
            ibnr[m] = np.asarray(valeurs, dtype=float)

    annee_base = int(n3.get('chain_ladder', {}).get('annee_base_reserve', 1))
    couverture = {a['annee']: a for a in
                  n2.get('clm', {}).get('couvertures', {}).get('annees', [])}
    cadence = n2.get('bfcc', {}).get('couverture_cadence', {})

    be = 0.0
    detail: List[Dict[str, Any]] = []
    contribution: Dict[str, float] = {m: 0.0 for m in admises}
    n_annees = max((len(v) for v in ibnr.values()), default=0)

    for i in range(annee_base, n_annees):
        motif = couverture.get(i, {}).get('couverture_motif', 'NON TESTABLE')
        # `couverture_volatilite` est le pendant de `couverture_motif` pour la
        # DISPERSION (CLM-H3 par colonne, durci par CLM-H4). Elle était calculée
        # par `couvertures_par_annee` et lue par PERSONNE. Elle est désormais
        # publiée. Elle ne gate rien : elle porte sur Mack, qui n'entre pas dans
        # le Best Estimate — voir `_hypotheses_a_justifier`.
        volatilite = couverture.get(i, {}).get('couverture_volatilite',
                                               'NON TESTABLE')
        sous_filet = motif == 'NON VALIDÉE'
        cadence_ko = cadence.get(i) == 'NON VALIDÉE'
        retenues = _methodes_de_lannee(i, admises, ibnr, sous_filet, cadence_ko)

        if not retenues:
            detail.append({'annee': i, 'motif': motif, 'methodes': [],
                           'volatilite': volatilite,
                           'sous_filet': sous_filet, 'cadence_ko': cadence_ko,
                           'rouge_dur': True, 'contribution': 0.0})
            continue

        poids_i = 1.0 / len(retenues)          # POIDS ÉGAL — choix assumé
        contrib_annee = 0.0
        for m in retenues:
            part = poids_i * float(ibnr[m][i])
            contribution[m] = contribution.get(m, 0.0) + part
            contrib_annee += part
        be += contrib_annee
        detail.append({'annee': i, 'motif': motif, 'methodes': retenues,
                       'volatilite': volatilite,
                       'sous_filet': sous_filet, 'cadence_ko': cadence_ko,
                       'rouge_dur': False,
                       'poids_unitaire': round(poids_i, 6),
                       'contribution': round(contrib_annee, 2)})

    utilisees = sorted({m for d in detail for m in d['methodes']})
    for m in list(admises):
        if m not in utilisees:
            exclues[m] = (methodes_dispo[m],
                          "retirée de toutes les années par la couverture")

    # `poids` = part EFFECTIVE de chaque méthode dans le BE final. Les poids
    # varient d'une année à l'autre ; publier un poids nominal unique serait
    # trompeur. Cette part-là, elle, décrit ce qui s'est réellement passé.
    poids = ({m: round(contribution[m] / be, 4) for m in utilisees}
             if abs(be) > 1e-9 else {m: round(1.0 / max(len(utilisees), 1), 4)
                                     for m in utilisees})

    return {
        'best_estimate':     float(be),
        'methodes_incluses': {m: float(methodes_dispo[m]) for m in utilisees},
        'methodes_exclues':  exclues,
        'poids':             poids,
        'annees':            detail,
        'annees_sous_filet': [d['annee'] for d in detail if d['sous_filet']],
        'annees_cadence_ko': [d['annee'] for d in detail if d['cadence_ko']],
        'annees_rouge_dur':  [d['annee'] for d in detail if d['rouge_dur']],
        # Dispersion : publiée, jamais gatante. Une année y figure dès que
        # CLM-H3/H4 doutent de la structure de variance SUR SON PARCOURS —
        # l'écart-type de Mack et les percentiles qui en dérivent sont alors à
        # lire avec prudence, la réserve centrale ne l'étant pas.
        'annees_volatilite_douteuse': [
            d['annee'] for d in detail
            if d['volatilite'] in ('À JUSTIFIER', 'NON VALIDÉE')],
        # LA TRACE (lot A2) — une entrée par (année, hypothèse en défaut).
        'trace_gouvernance': _trace_gouvernance(n2, detail, float(be)),
    }


class BestEstimateS2:
    """
    Calcule le Best Estimate — réserve BRUTE, avant actualisation (la valeur
    actuelle S2 au sens de l'Art. 77 est produite en aval par A10) — avec :
      · Sélection des méthodes admises, année par année (couvertures CLM + BFCC)
      · Poids égaux entre méthodes admises — choix assumé, pas une calibration
      · Percentiles log-normale (QIS5 TP.5.26)
      · SCR provisions formule standard (Art. 115 S2)
      · Sensibilités aux hypothèses clés
      · Jugement actuariel documenté (style rapport ORSA)
    """

    def calculer(
        self,
        n2:           Dict,
        n3:           Dict,
        C:            np.ndarray,
        lob:          str   = 'generique',
        provisions_dossier: Optional[float] = None,
        **kwargs,
    ) -> Dict:
        """
        Calcule le Best Estimate (réserve brute, avant actualisation) et le SCR.

        Parameters
        ----------
        n2 : dict
            Résultats N2 — hypothèses H1/H2/H4, couvertures CLM et BFCC.
        n3 : dict
            Résultats des méthodes actuarielles N3 — réserves par méthode.
        C : np.ndarray
            Triangle cumulé (pour calculs complémentaires).
        lob : str
            Ligne d'activité — pilote σ(LoB) EIOPA pour le SCR.
        provisions_dossier : float, optionnel
            Σ(charges à date − payé à date), à fournir UNIQUEMENT quand les
            méthodes N3 ont tourné sur un triangle de CHARGES : leurs réserves
            sont alors l'IBNR pur, et il manque au BE les provisions dossier.
            None (défaut) = base paiements, aucune correction — cf. § 3bis.

        Returns
        -------
        dict conforme standard ActuarIA. `best_estimate` est le BE S2 complet ;
        `be_ibnr_pur` et `provisions_dossier` en donnent la décomposition (en
        base paiements, `be_ibnr_pur == best_estimate` et les provisions sont 0).
        """
        cfg = get_lob_config(lob)

        # ── Réserves par méthode ──────────────────────────────────────────────
        cl_res   = n3['chain_ladder']['reserve_totale']
        bf_res   = n3['bf']['reserve_totale']
        cc_res   = n3['cape_cod']['reserve_totale']
        sigma    = n3['mack']['sigma_total']
        boot     = n3.get('bootstrap', {})

        # Mack RETIRÉ du point estimate du BE : son point = celui du Chain Ladder
        # (Mack = CL + σ ; réserve identique par construction, mack consomme les
        # facteurs du CL). L'inclure comme méthode pondérée double-compterait le CL.
        # Mack reste utilisé pour la VOLATILITÉ (sigma, n3['mack']['sigma_total']).
        methodes_dispo = {
            'chain_ladder':         cl_res,
            'bornhuetter_ferguson': bf_res,
            'cape_cod':             cc_res,
        }

        # ── 1-3. Sélection PAR ANNÉE et Best Estimate ─────────────────────────
        selection = selectionner_et_agreger(n2, n3, methodes_dispo)
        methodes_incluses = selection['methodes_incluses']
        methodes_exclues  = selection['methodes_exclues']
        poids             = selection['poids']
        be                = selection['best_estimate']

        # ── 3bis. BASE CHARGES : réintégration des provisions dossier ──────────
        #
        # ⚠️ CORRECTION RÉGLEMENTAIRE. Les méthodes N3 calculent toutes
        # `IBNR = ultime − dernière diagonale DU TRIANGLE QU'ON LEUR A PASSÉ`.
        # Sur un triangle de CHARGES, cette diagonale est la charge à date, donc
        # chaque R_m — et donc `be` — vaut l'IBNR PUR : il MANQUE les provisions
        # dossier, déjà comprises dans les charges mais pas encore payées. Or le
        # Best Estimate S2 (Art. 77) est l'ensemble des flux FUTURS, soit
        # `ultime − PAYÉ à date`.
        #
        #     ultime − payé  =  (ultime − charges)  +  (charges − payé)
        #     réserve totale =      IBNR pur        + provisions dossier
        #
        # Exemple : ultime 300, charge 270, payé 50
        #     sans correction : 300 − 270 =  30   ← IBNR pur, BE sous-estimé
        #     avec correction :  30 + 220 = 250   ← correct (220 = 270 − 50)
        #
        # La correction est ADDITIVE et UNIFORME : un seul point suffit, aucune
        # des 9 méthodes N3 n'est touchée. Elle est placée AVANT tout ce qui
        # dérive de `be` (σ composé, percentiles, SCR, RM, PT), qui devient donc
        # correct automatiquement.
        #
        # `provisions_dossier=None` (défaut) = base paiements : AUCUN changement.
        be_ibnr_pur = be
        if provisions_dossier:
            be += float(provisions_dossier)

        # ── 4. CV inter-méthodes ──────────────────────────────────────────────
        reserves_val = list(methodes_incluses.values())
        cv_inter = (
            float(np.std(reserves_val) / max(np.mean(reserves_val), 1e-9) * 100)
            if len(reserves_val) > 1 else 0.0
        )

        # ── 5. Percentiles — Incertitude composée (Option B) ──────────────────
        #
        # Approche : σ_total² = σ_Mack² + σ_modèle²
        #
        # σ_Mack   = incertitude stochastique (England & Verrall 2002 via Mack)
        # σ_modèle = incertitude de modèle = std(réserves des méthodes incluses)
        #            mesure la dispersion entre méthodes — EIOPA TP.5.22
        #
        # Cette approche est plus rigoureuse que d'utiliser les percentiles
        # Bootstrap bruts (centrés sur BE_Bootstrap ≠ BE pondéré) et garantit
        # P90 > BE pondéré même quand les méthodes divergent fortement.
        #
        # Références :
        #   · EIOPA (2014) Guidelines TP.5.22 — risque de modèle
        #   · Mack (1993) — σ stochastique
        #   · England & Verrall (2002) — Bootstrap ODP comme alternative
        #
        _boot = n3.get('bootstrap', {})
        # `disponible` d'abord : un Bootstrap NON CALCULÉ publie un point
        # estimate (la réserve Chain Ladder de référence, légitime) mais AUCUN
        # percentile. Lire les siens donnerait des None aux variantes `_boot`.
        #
        # `percentiles_publiables` ensuite — SEULE CONSÉQUENCE GATANTE de
        # BOOT-H1..H4. Le Bootstrap ODP ne figure pas dans `_CLES_N3` : il ne
        # pèse pas dans le Best Estimate, il en mesure la dispersion. Rejeter ses
        # hypothèses ne peut donc retirer qu'un LIVRABLE — les percentiles
        # `reserve_p*_boot` — jamais une méthode. Le BE, le SCR et la Risk Margin
        # sont rigoureusement inchangés, et c'est vérifié par test.
        # Absent (module non exécuté) → True : ne pas avoir jugé n'est pas juger
        # défavorablement.
        _boot_hyp_ok = bool(n2.get('bootstrap_hyp', {})
                              .get('percentiles_publiables', True))
        _boot_ok = _boot_hyp_ok and bool(_boot.get('disponible', True)) and bool(
            (_boot.get('be_bootstrap') or 0) > 0
            and _boot.get('p90') is not None)

        # PORTEUR DE LA CIBLE `percentiles_mack` — CLM-H3. Même convention que
        # le Bootstrap : absent → True, ne pas avoir jugé n'est pas juger
        # défavorablement.
        _mack_hyp_ok = bool(n2.get('clm', {})
                              .get('percentiles_mack_publiables', True))

        # σ_modèle : std des réserves des méthodes incluses (pondérées par poids)
        # Si une seule méthode → σ_modèle = 0 (pas de dispersion inter-méthodes)
        reserves_val = list(methodes_incluses.values())
        sigma_modele = (
            float(np.std(reserves_val, ddof=0))
            if len(reserves_val) > 1 else 0.0
        )

        # σ_total composé — centré sur le BE pondéré
        sigma_total_compose = float(np.sqrt(sigma ** 2 + sigma_modele ** 2))

        # Percentiles log-normale centrés sur le BE pondéré (QIS5 TP.5.26)
        # avec σ_total composé
        if sigma_total_compose > 0 and be > 0:
            cv_ln  = sigma_total_compose / be
            s2_ln  = np.log(1.0 + cv_ln ** 2)
            s_ln   = np.sqrt(s2_ln)
            m_ln   = np.log(be) - s2_ln / 2.0

            p75  = float(np.exp(m_ln + 0.6745 * s_ln))
            p90  = float(np.exp(m_ln + 1.2816 * s_ln))
            p995 = float(np.exp(m_ln + 2.5758 * s_ln))
        else:
            p75 = p90 = p995 = be

        # ⚠️ LES DEUX ÉTAGES DE LA CONSÉQUENCE, ET ILS NE SONT PAS SYMÉTRIQUES.
        # Si CLM-H3 est NON VALIDÉE, σ_Mack ne mesure plus l'erreur de
        # prédiction. Mais σ_Mack alimente DEUX choses de statut très différent :
        #   · les percentiles Mack `reserve_p*_mack`, colonne COMPARATIVE — on
        #     les retire, exactement comme les percentiles Bootstrap ;
        #   · `sigma_total_compose`, d'où sortent les percentiles PRINCIPAUX du
        #     rapport — les retirer laisserait le livrable SANS AUCUNE mesure
        #     d'incertitude. On ne fait JAMAIS ça en silence.
        # D'où la bascule : si le Bootstrap est publiable, il prend le relais et
        # `source_percentiles` le DIT ; sinon on publie quand même, en nommant
        # la composante contestée. Le principe est celui du lot F1 — une case
        # vide honnête vaut mieux qu'un nombre faux, mais un nombre étiqueté
        # vaut mieux qu'une case vide quand une alternative existe.
        p90_source = 'Incertitude composée (σ_Mack + σ_modèle)'
        if not _mack_hyp_ok:
            if _boot_ok:
                p75  = float(_boot.get('p75')  or p75)
                p90  = float(_boot.get('p90')  or p90)
                p995 = float(_boot.get('p99_5') or p995)
                p90_source = (
                    "Bootstrap ODP — σ_Mack ÉCARTÉ : CLM-H3 (structure de "
                    "variance) non validée, l'écart-type de Mack ne mesure "
                    "plus l'erreur de prédiction")
            else:
                p90_source = (
                    "⚠️ Incertitude composée dont la composante σ_Mack est "
                    "CONTESTÉE — CLM-H3 (structure de variance) non validée, "
                    "et le Bootstrap n'offre pas de relais publiable. "
                    "Percentiles à interpréter avec prudence ; la réserve "
                    "centrale, elle, n'est pas concernée.")

        # Percentiles Mack seul — centrés sur BE pondéré (pour affichage comparatif)
        if sigma > 0 and be > 0:
            cv_ln_m  = sigma / be
            s2_ln_m  = np.log(1.0 + cv_ln_m ** 2)
            s_ln_m   = np.sqrt(s2_ln_m)
            m_ln_m   = np.log(be) - s2_ln_m / 2.0
            p75_mack  = float(np.exp(m_ln_m + 0.6745 * s_ln_m))
            p90_mack  = float(np.exp(m_ln_m + 1.2816 * s_ln_m))
            p995_mack = float(np.exp(m_ln_m + 2.5758 * s_ln_m))
        else:
            p75_mack = p90_mack = p995_mack = be

        # Stocker les deux séries pour affichage comparatif dans le rapport
        p75_mack_val  = p75_mack
        p90_mack_val  = p90_mack
        p995_mack_val = p995_mack

        # Exposer σ_modèle et σ_total composé dans le dict retour
        sigma_modele_val       = round(sigma_modele, 2)
        sigma_total_compose_val = round(sigma_total_compose, 2)

        # ── 6. SCR provisions formule standard (Art. 115 S2) ──────────────────
        scr = self._calculer_scr(be, lob, cfg)

        # ── 7. Risk Margin S2 (Art. 77 §5) ───────────────────────────────────
        _f_cum  = n3.get('chain_ladder', {}).get('facteurs_cumules', [])
        _courbe = kwargs.get('courbe_rfr', None)
        if _courbe is None:
            _courbe = get_courbe_embarquee()
        _courbe['_lob'] = lob
        risk_margin_data = self._calculer_risk_margin(be, scr, _f_cum, _courbe)

        # ── 8. Sensibilités ───────────────────────────────────────────────────
        sensibilites = self._calculer_sensibilites(
            methodes_incluses, poids, boot, be, _boot_ok
        )

        # ── 8. Statut ─────────────────────────────────────────────────────────
        if cv_inter < 5.0:
            statut = 'VERT'
        elif cv_inter < 15.0:
            statut = 'AMBRE'
        else:
            statut = 'ROUGE'

        # Le filet de sécurité force le ROUGE — il ne peut JAMAIS passer
        # inaperçu. C'est ce qui remplace l'ancien garde-fou, qui repliait
        # silencieusement sur Chain Ladder + BF avec un score forcé à 50.
        if selection['annees_rouge_dur']:
            statut = 'ROUGE'
        elif selection['annees_sous_filet']:
            statut = 'ROUGE'

        # UN BEST ESTIMATE MONO-MÉTHODE NE PEUT PAS SORTIR EN VERT.
        # Avec une seule méthode, `cv_inter` vaut 0 par construction — l'absence
        # de dispersion viendrait alors mécaniquement valider le résultat, alors
        # qu'elle traduit exactement l'inverse : aucune méthode indépendante ne
        # vient le corroborer. C'est le cas dès qu'aucune mesure d'exposition
        # n'est fournie, Bornhuetter-Ferguson et Cape Cod refusant alors de
        # produire un chiffre.
        if len(methodes_incluses) < 2 and statut == 'VERT':
            statut = 'AMBRE'

        # UN BEST ESTIMATE DONT LE NIVEAU REMONTE ENTIÈREMENT À CHAIN LADDER
        # NE PEUT PAS SORTIR EN VERT NON PLUS. Même principe, une marche plus
        # loin : plusieurs méthodes peuvent figurer au résultat sans qu'aucune
        # n'apporte d'avis INDÉPENDANT sur le niveau. C'est le cas quand le loss
        # ratio a priori de Bornhuetter-Ferguson est dérivé des ultimes Chain
        # Ladder (`source_lr = 'matures'`) et que Cape Cod est absente : BF
        # corrige alors l'ALLOCATION entre années — il y substitue l'exposition,
        # ce qui est un apport réel — mais hérite intégralement du NIVEAU.
        # Mesuré sur GenIns : ultimes Chain Ladder matures +10 % déplacent la
        # réserve BF de +10,0 %. Moyenner les deux ne couvre alors aucun risque
        # de niveau, et le `cv_inter` faible qui en résulte le dirait à tort.
        niveau_ancre_cl = _niveau_ancre_sur_chain_ladder(n3, methodes_incluses)
        if statut == 'VERT' and niveau_ancre_cl:
            statut = 'AMBRE'

        # UNE HYPOTHÈSE « À JUSTIFIER » NE PEUT PAS COEXISTER AVEC UN VERT.
        # Le statut à trois états n'aurait aucun sens si son état intermédiaire
        # n'avait aucune conséquence : À JUSTIFIER conserve la méthode — c'est là
        # sa différence avec NON VALIDÉE — mais demande une justification, et un
        # Best Estimate présenté comme VERT dispenserait de la donner.
        a_justifier = _hypotheses_a_justifier(n2, methodes_incluses)
        if statut == 'VERT' and a_justifier:
            statut = 'AMBRE'

        # ⚠️ ET LA COUVERTURE « À JUSTIFIER » PAR ANNÉE ? ELLE NE PEUT RIEN
        # PLAFONNER, ET C'EST DÉMONTRÉ — ne pas rouvrir le sujet (lot A2).
        #
        # Le lot A2 devait ajouter ici un plafonnement du VERT par
        # `couverture_motif == 'À JUSTIFIER'`. Il n'a pas été écrit parce qu'il
        # ne peut JAMAIS être la règle décisive :
        #
        #   · `couvertures_par_annee` pose `k_i = min(n-i-1, m-1)` puis
        #     `traversees = range(k_i, m-1)`. Pour l'année la PLUS RÉCENTE,
        #     `k_i = 0` : elle traverse TOUTES les colonnes testées, et sa
        #     couverture est donc le pire de toutes.
        #   · `_agreger_par_colonne` — le verdict GLOBAL de CLM-H2 — applique
        #     exactement la même règle : `if n_non … elif n_just …`.
        #   · Donc `couverture_motif[année la plus récente]` EST le statut
        #     global de CLM-H2, toujours.
        #
        # D'où deux cas, et deux seulement :
        #   · une colonne À JUSTIFIER (aucune non validée) → global
        #     À JUSTIFIER → `_hypotheses_a_justifier` plafonne DÉJÀ, juste
        #     au-dessus, puisque CLM-H2 vise `chain_ladder`, toujours retenue ;
        #   · une colonne NON VALIDÉE → l'année la plus récente passe sous
        #     filet → le ROUGE est DÉJÀ forcé plus haut.
        #
        # Balayage de 48 triangles (bruit x terme additif x graine) : aucun cas
        # où la couverture annuelle serait seule à parler. Ajouter ce
        # plafonnement reviendrait à écrire une règle morte — c'était exactement
        # le drapeau `reserve_publiable` de MCL-H5, retiré au lot précédent.
        #
        # Ce que le lot A2 a livré à la place se trouve dans
        # `_trace_gouvernance` : ces années ne changent pas le statut, mais
        # elles ne sont plus muettes. Sur GenIns, les quatre années « à
        # justifier » portent 60,9 % du Best Estimate.

        # ── 9. Jugement actuariel (alertes, recommandations, avis) ───────────
        alertes_jugement = []
        recommandations  = []

        # PÉREMPTION DE LA COURBE DES TAUX — remontée en alerte, pas seulement
        # journalisée. Elle actualise la Risk Margin, qui entre au bilan.
        _per = risk_margin_data.get('peremption_courbe') or {}
        if _per.get('statut') in ('AMBRE', 'ROUGE'):
            alertes_jugement.append(_per['message'])

        if niveau_ancre_cl:
            alertes_jugement.append(MSG_NIVEAU_ANCRE_CL)

        if a_justifier:
            alertes_jugement.append(
                f"🟡 Hypothèses à justifier avant validation : "
                f"{', '.join(a_justifier)} — les méthodes concernées restent "
                f"retenues, mais le Best Estimate ne peut pas sortir en VERT "
                f"sans que l'écart soit expliqué dans la note méthodologique.")

        # ⚠️ LE PARADOXE DU FILET, NOMMÉ. Jusqu'à ce lot, `annees_sous_filet`
        # forçait le ROUGE et ne produisait AUCUNE alerte — l'actuaire lisait un
        # statut sans jamais en apprendre la cause. Le modèle est celui de
        # `annees_cadence_ko` juste en dessous, qui dit déjà ce genre de chose.
        # Tout est GÉNÉRÉ depuis la trace : aucun chiffre n'est écrit ici.
        _filet = [t for t in selection['trace_gouvernance']
                  if t['consequence'] == _CONSEQ_FILET]
        if _filet:
            _part = sum(t['part_du_be'] for t in _filet)
            _eur  = sum(t['contribution_eur'] for t in _filet)
            _t0   = _filet[0]
            _meth = sorted({_LIBELLE_METHODE.get(m, m)
                            for t in _filet for m in t['methodes_retenues']})
            # ⚠️ LE SÉPARATEUR DE MILLIERS NE TOUCHE QUE LE NOMBRE. Appliqué à
            # la phrase, il mange les virgules de ponctuation — « p < 0,01 »
            # devient « p < 0 01 ». Ce défaut s'est produit SIX fois dans ce
            # dépôt ; il est cantonné ici à la seule valeur formatée.
            _eur_txt  = f"{_eur:,.0f}".replace(',', ' ')
            _part_txt = f"{_part * 100:.1f}".replace('.', ',')
            alertes_jugement.append(
                f"⚠️ Années {[t['annee'] for t in _filet]} : FILET DE SÉCURITÉ "
                f"déclenché. L'hypothèse {_t0['hypothese']} est "
                f"{_t0['statut'].lower()} sur la {_t0['portee']} "
                f"({_t0['statistique']}, {_t0['seuil']}) que ces années doivent "
                f"encore traverser. Elles sont portées par "
                f"{' et '.join(_meth)} seule, soit "
                f"{_eur_txt} € — {_part_txt} % du Best Estimate."
                f" C'EST PRÉCISÉMENT L'HYPOTHÈSE DE CETTE MÉTHODE QUI EST EN "
                f"CAUSE, ET ELLE EST POURTANT RETENUE. Ce n'est pas une "
                f"contradiction : Bornhuetter-Ferguson et Cape Cod sont "
                f"construites sur (1 − α) × a priori et ne peuvent rien "
                f"représenter de fiable sur un motif de développement démenti, "
                f"tandis que Chain Ladder projette le cumulé tel qu'il est "
                f"observé. C'est le moins mauvais choix, pas un choix "
                f"satisfaisant — le coefficient de passage retenu sur ces "
                f"années demande une justification dans la note "
                f"méthodologique.")

        if selection['annees_cadence_ko']:
            alertes_jugement.append(
                f"⚠️ Années {selection['annees_cadence_ko']} : cumulé "
                f"décroissant (recours, subrogation ou reprise de provision). "
                f"Bornhuetter-Ferguson et Cape Cod ne peuvent structurellement "
                f"pas y représenter une reprise — ils y rendraient zéro. CES "
                f"ANNÉES SONT PORTÉES PAR CHAIN LADDER SEULE, qui projette le "
                f"cumulé tel qu'il est. Hypothèse (H2) du guide IA 2023, "
                f"§2.c.ii p18-19.")

        # Reprendre les alertes de N2
        for a in n2.get('alertes', []):
            alertes_jugement.append(str(a))

        # Recommandations depuis la méthode recommandée
        methode_rec = n2.get('methode_recommandee', 'chain_ladder')
        raison_rec  = n2.get('raison_recommandation', '')
        if raison_rec:
            # Tronquer proprement à la dernière phrase complète
            _raison_short = raison_rec[:300]
            if len(raison_rec) > 300 and '.' in _raison_short:
                _raison_short = _raison_short[:_raison_short.rfind('.')+1]
            recommandations.append(
                f"Méthode principale : "
                f"{methode_rec.replace('_',' ').title()} — {_raison_short}")

        # Recommandation back-testing si dispo
        bt_statut_val = n3.get('backtesting', {}).get('statut', '')
        if bt_statut_val == 'ROUGE':
            recommandations.append(
                "Back-testing ROUGE — réviser les hypothèses de provisionnement N-1/N-2 "
                "avant inscription au bilan S2."
            )

        # Recommandation effets calendaire si dispo
        bz_statut_val = n3.get('glm_apc', {}).get('statut', '')
        if bz_statut_val == 'AMBRE':   # le GLM APC n'emet que VERT/AMBRE (pas de ROUGE)
            recommandations.append(
                "Effets calendaire détectés — documenter la cause "
                "(inflation, changement législatif) "
                "dans la note méthodologique S2."
            )

        # H1 rejetée → déjà dans "Point de vigilance" section 08, on ne la
        # duplique pas ici. (Les deux lectures de `h1_independance` qui vivaient
        # à cet endroit étaient mortes : `h1_corr` n'était jamais utilisée et
        # `h1_ok` était réassignée à l'identique plus bas, là où elle sert.)

        # Hypothèses du Bootstrap ODP — BOOT-H1..H4.
        #
        # ⚠️ CE QUI A REMPLACÉ L'ANCIENNE RECOMMANDATION H4, ET POURQUOI.
        # Elle lisait `n2['h4_homosc_bootstrap']['cv_var']`, le coefficient de
        # variation des variances des FACTEURS de développement, et annonçait
        # « Bootstrap ODP non fiable » dès qu'il dépassait 1,0 — ce qui était le
        # cas sur les TROIS triangles de référence (2,12 · 2,40 · 1,31). Une
        # alerte qui se déclenche partout n'informe nulle part, et celle-ci
        # portait en plus sur une grandeur sans rapport avec la sur-dispersion
        # des résidus. Ici, le verdict vient du φ du Bootstrap lui-même, et il a
        # une conséquence : les percentiles ne sont pas publiés.
        for ligne in lignes_hypotheses_bootstrap(n2):
            if ligne['statut'] == 'NON VALIDÉE' and ligne['critique']:
                recommandations.append(
                    f"{ligne['libelle']} — NON VALIDÉE. Les percentiles "
                    f"Bootstrap (P75/P90/P99.5) ne sont pas publiés. Le Best "
                    f"Estimate est INCHANGÉ : le Bootstrap ne pèse pas dans sa "
                    f"pondération, il en mesure la dispersion. Retenir "
                    f"l'incertitude de Mack (σ) pour le SCR provisions."
                )

        # Recommandation Clark — deux causes DISTINCTES, deux messages distincts.
        # L'incompatibilité de structure n'est pas un ajustement raté : c'est
        # une impossibilité de forme, que la queue soit raisonnable ou non.
        clark = n3.get('clark', {})
        _ck_struct = clark.get('structure_monotone') or {}
        if _ck_struct.get('testable') and not _ck_struct.get('compatible', True):
            _cols = _ck_struct.get('facteurs_reprise') or []
            recommandations.append(
                "Clark LDF inapplicable sur ce triangle — "
                f"{len(_cols)} facteur(s) de développement sous 1 "
                f"(minimum {_ck_struct.get('facteur_min')}). Les courbes de Clark "
                "sont monotones croissantes et ne peuvent pas représenter un "
                "recours : la réserve n'est pas publiée. Chain Ladder, qui "
                "accepte les facteurs sous 1, reste applicable."
            )
        elif clark.get('aberrant'):
            recommandations.append(
                "Clark LDF produit un résultat aberrant — méthode exclue de la pondération. "
                "Vérifier la structure du triangle et la longueur de la "
                "queue de développement."
            )

        # Recommandation Risk Margin
        recommandations.append(
            "Risk Margin S2 calculé par la méthode proportionnelle au BE "
            "(méthode 2 EIOPA, CoC 6%). "
            "Documenter la courbe EIOPA RFR utilisée dans la note méthodologique. "
            "Vérifier la cohérence avec le Risk Margin du dernier arrêté."
        )

        # Recommandation tail factor si appliqué
        tail_info = n3.get('chain_ladder', {}).get('tail_factor', {})
        if isinstance(tail_info, dict) and tail_info.get('tail_factor', 1.0) > 1.0:
            tail_val = tail_info.get('tail_factor', 1.0)
            recommandations.append(
                f"Tail factor = {tail_val:.4f} appliqué "
                f"(Guide IA 2023 — régression log-linéaire). "
                "Justifier le seuil de stabilisation retenu dans la note méthodologique S2."
            )

        def _safe_year(s):
            try: return int(s.strip()[-4:])
            except: return 0

        # Recommandation rupture sinistralité (back-testing rouge récent)
        bt_tableau = n3.get('backtesting', {}).get('tableau', [])
        annees_rouge_recentes = [
            r.get('annee_label', r.get('annee', '')) for r in bt_tableau
            if isinstance(r, dict) and r.get('mature', True)
            and abs(float(r.get('ecart_pct_n1', 0) or 0)) >= 15.0
            and _safe_year(str(r.get('annee_label', r.get('annee', '0')))) >= 2020
        ]
        if annees_rouge_recentes:
            recommandations.append(
                f"Rupture de sinistralité détectée sur les années récentes "
                f"({', '.join(str(a) for a in annees_rouge_recentes[:3])}) — "
                "écart back-testing > 15% sur N-1. Analyser la cause (inflation judiciaire, "
                "changement de portefeuille) et envisager un chargement prudentiel "
                "sur les années 2020+ avant inscription au bilan S2."
            )

        # Avis actuariel global
        h1_ok = n2.get('h1_independance', {}).get('ok', True)
        if statut == 'ROUGE' or (not h1_ok and bt_statut_val == 'ROUGE'):
            avis_actuariel = 'FAVORABLE SOUS RÉSERVE — révisions requises avant bilan S2'
        elif statut == 'AMBRE' or not h1_ok:
            avis_actuariel = 'FAVORABLE SOUS RÉSERVE — points de vigilance à documenter'
        else:
            avis_actuariel = ("FAVORABLE — Best Estimate (réserve brute) "
                              "robuste ; actualisation S2 opérée en aval (A10)")

        # ── 9. Jugement actuariel documenté ───────────────────────────────────
        jugement = self._documenter_jugement(
            methodes_incluses, methodes_exclues, poids,
            be, cv_inter, n2, n3, statut, scr, cfg
        )

        msg = (
            f"BE brut = {be:,.0f}€ · P90 = {p90:,.0f}€ · "
            f"CV = {cv_inter:.1f}% · σ = {sigma:,.0f}€ · "
            f"SCR_prov = {scr['scr_provisions']:,.0f}€"
        )
        logger.info(msg)

        resultat = {
            # Best Estimate
            'best_estimate':         round(be,     0),

            # Décomposition en base CHARGES — exposée pour qu'aucun lecteur ne
            # confonde les réserves PAR MÉTHODE (qui restent l'IBNR pur sur un
            # triangle de charges) avec le BE total. En base paiements,
            # provisions_dossier vaut 0 et be_ibnr_pur == best_estimate.
            # ATTENTION : la somme des deux reconstitue le BE ATTRITIONNEL, celui
            # que N4 calcule. Si l'appelant réintègre ensuite des grands sinistres
            # (LLT), il écrase `best_estimate` et conserve le pivot dans
            # `be_attritional` — c'est à lui que la décomposition se compare.
            'be_ibnr_pur':           round(be_ibnr_pur, 0),
            'provisions_dossier':    round(float(provisions_dossier or 0.0), 0),

            # Percentiles log-normale (QIS5 TP.5.26)
            'reserve_p75':           round(p75,    0),
            'reserve_p90':           round(p90,    0),
            'reserve_p99_5':         round(p995,   0),
            # Colonne COMPARATIVE — retirée si CLM-H3 est non validée, exactement
            # comme les percentiles Bootstrap le sont par BOOT-H3/H4. `None` et
            # non zéro : un zéro se lirait « dispersion nulle », soit l'inverse.
            'reserve_p75_mack':      (round(p75_mack_val,  0)
                                      if _mack_hyp_ok else None),
            'reserve_p90_mack':      (round(p90_mack_val,  0)
                                      if _mack_hyp_ok else None),
            'reserve_p99_5_mack':    (round(p995_mack_val, 0)
                                      if _mack_hyp_ok else None),
            'reserve_p75_boot':      (round(float(_boot.get('p75', p75_mack_val)), 0)
                                      if _boot_ok else None),
            'reserve_p90_boot':      (round(float(_boot.get('p90', p90_mack_val)), 0)
                                      if _boot_ok else None),
            'reserve_p99_5_boot':    (round(float(_boot.get('p99_5', p995_mack_val)), 0)
                                      if _boot_ok else None),
            'source_percentiles':    p90_source,

            # Incertitude composée (Option B — σ_Mack² + σ_modèle²)
            'sigma_mack':            round(sigma,  0),
            'sigma_modele':          sigma_modele_val,
            'sigma_total_compose':   sigma_total_compose_val,
            'cv_inter_methodes':     round(cv_inter, 2),

            # Méthodes — `poids` est la part EFFECTIVE de chaque méthode dans le
            # BE, et non un poids nominal : les pondérations varient d'une année
            # à l'autre, publier un chiffre unique serait trompeur.
            'methodes_incluses':     list(methodes_incluses.keys()),
            'methodes_exclues':      list(methodes_exclues.keys()),

            # ⚠️ LE MOTIF ÉTAIT CALCULÉ PUIS JETÉ (lot C3a). `_admissibilite_
            # globale` distingue « non calculée », « réserve nulle ou non
            # finie » et « <HYPOTHÈSE> NON VALIDÉE » — et seule la LISTE des
            # noms sortait. Le commentaire, faute de mieux, écrivait donc
            # « [exclu — score insuffisant] » : un motif qui n'existe plus
            # depuis que `scores_confiance` a disparu, et qui n'a jamais
            # correspondu à aucun des trois cas réels. Jointure pure, aucun
            # calcul neuf.
            'methodes_exclues_motifs': {m: motif for m, (_, motif)
                                        in methodes_exclues.items()},
            'poids':                 poids,

            # Sélection par année de survenance (lot B)
            'selection_par_annee':   selection['annees'],
            'annees_sous_filet':     selection['annees_sous_filet'],
            # LA TRACE STRUCTURÉE (lot A2). `annees_sous_filet` publiait un
            # NUMÉRO D'ANNÉE sans son motif : l'actuaire lisait « [9] » et un
            # statut ROUGE, sans jamais savoir quelle hypothèse avait échoué,
            # sur quelle colonne, ni ce que ça pesait. La trace répond aux
            # trois questions, et elle est filtrable.
            'trace_gouvernance':     selection['trace_gouvernance'],
            # Dispersion douteuse — publiée, jamais gatante (lot A1).
            'annees_volatilite_douteuse':
                selection['annees_volatilite_douteuse'],
            # Années dont la cadence a retiré BF et Cape Cod — SANS elle,
            # l'actuaire voyait le Best Estimate changer sans savoir où.
            'annees_cadence_ko':     selection['annees_cadence_ko'],
            'annees_rouge_dur':      selection['annees_rouge_dur'],
            'hypotheses_a_justifier': a_justifier,

            # SCR formule standard
            'scr':                   scr,

            # Risk Margin S2 (Art. 77 §5)
            'risk_margin':              risk_margin_data.get('risk_margin', 0),
            'provisions_techniques_s2': risk_margin_data.get(
                'provisions_techniques_s2', round(be, 0)),
            'ratio_rm_be':              risk_margin_data.get('ratio_rm_be', 0),
            'date_courbe_rfr':          risk_margin_data.get('date_courbe_rfr', '—'),
            # Diagnostic de péremption REMONTÉ jusqu'ici : la date seule ne dit
            # pas si la courbe est encore valable, et c'est elle qui actualise
            # la Risk Margin inscrite au bilan.
            'peremption_courbe':        risk_margin_data.get('peremption_courbe'),
            'tableau_run_off':          risk_margin_data.get('tableau_run_off', []),
            'message_rm':               risk_margin_data.get('message', ''),


            # Sensibilités
            'sensibilites':          sensibilites,

            # Jugement
            'jugement':              jugement,

            # Statut
            'statut':                statut,
            'message':               msg,

            # Jugement actuariel — alimenté depuis les alertes N2/N4
            'alertes':               alertes_jugement,
            'recommandations':       recommandations,
            'avis_actuariel':        avis_actuariel,

            # Alias pour compatibilité rapport
            'scr_prov':              scr['scr_provisions'],
            'methode_facteurs':      methode_rec,
        }

        # ── 10. Garde-fou TOTAL — BE pondéré <= 0 (reprise nette) ──────────────
        # Chemin PRIMAIRE (sans grands sinistres) : si le BE est négatif, les
        # agrégats S2 (SCR = 3σ×BE, ratio, RM, PT, percentiles log-normaux) sont
        # non calculables → marqueurs None + statut ROUGE, jamais de plancher
        # silencieux. Le bloc LLT d'agent.py applique le même garde-fou sur le BE
        # final post-grands-sinistres. Dormant tant que les méthodes planchent.
        _garde = garde_fou_be_negatif(be)
        if _garde is not None:
            resultat['scr']['scr_provisions']    = None
            resultat['scr']['ratio_scr_be']      = None
            resultat['scr']['message']           = _garde['message']
            resultat['scr_prov']                 = None
            resultat['reserve_p75']              = None
            resultat['reserve_p90']              = None
            resultat['reserve_p99_5']            = None
            resultat['risk_margin']              = None
            resultat['provisions_techniques_s2'] = None
            resultat['ratio_rm_be']              = None
            resultat['statut']                   = 'ROUGE'
            resultat['be_negatif']               = True
            resultat['alertes']    = [_garde['message']] + list(resultat.get('alertes', []))
            resultat['message']                  = _garde['message']

        return resultat

    # =========================================================================
    #  SCR PROVISIONS FORMULE STANDARD (Art. 115 S2)
    # =========================================================================

    def _calculer_scr(
        self,
        be:  float,
        lob: str,
        cfg: Dict,
    ) -> Dict:
        """
        SCR provisions formule standard pour une LoB unique.

        Art. 115 du Règlement Délégué (UE) 2015/35 :

            SCR_prov(LoB) = 3 × σ(LoB) × BE(LoB)

        σ(LoB) = écart type du risque de RÉSERVE du segment (art. 117 ; valeurs
        à l'annexe II pour le non-vie, à l'annexe XIV pour la santé non-SLT).
        Le facteur 3 correspond au quantile 99,5 % d'une loi normale.

        ⚠️ CE N'EST PAS L'ARTICLE 105. L'art. 105 du Règlement délégué porte
        sur le calcul simplifié du risque de spread des entreprises captives.
        C'est l'art. 105 de la DIRECTIVE 2009/138/CE qui décrit les modules du
        SCR ; la formule est à l'art. 115 du Règlement.

        ⚠️ LE BE EST BRUT. L'art. 116(6) définit la mesure de volume du risque
        de réserve nette des montants recouvrables au titre de la réassurance,
        alors que le BE d'A7 est brut : le SCR publié est un MAJORANT sur cet
        axe. La cession relève d'A10, en aval.

        Pour plusieurs LoB : agrégation avec matrice corrélation EIOPA.
        Ici, calcul mono-LoB — l'agrégation multi-LoB est prévue
        au niveau du tableau de bord consolidé.

        Returns
        -------
        dict avec scr_provisions, sigma_eiopa, reference_s2, lob, methode.
        """
        sigma_eiopa  = get_sigma_eiopa(lob)
        scr_prov     = 3.0 * sigma_eiopa * be

        # Ratio SCR/BE : signal de niveau de risque
        ratio = scr_prov / max(be, 1e-9)

        return {
            'scr_provisions':   round(scr_prov,    0),
            'sigma_eiopa':      sigma_eiopa,
            'ratio_scr_be':     round(ratio,        4),
            'lob':              lob,
            'lob_label':        cfg.get('label', lob),
            # La traçabilité voyage AVEC le résultat : les livrables citaient
            # « Annexe II » en dur, ce qui devient faux dès qu'une LoB relève
            # de la santé non-SLT (annexe XIV).
            'reference_s2':     reference_s2(lob),
            'methode':          'Formule standard Art. 115 (Rgt délégué (UE) 2015/35)',
            'message': (
                # .1% et non .0% : deux segments ont un σ à trois chiffres
                # significatifs (protection juridique 5,5 %, crédit 17,2 %) que
                # l'arrondi à l'entier faisait disparaître.
                f"SCR_prov = 3 × {sigma_eiopa:.1%} × {be:,.0f}€ "
                f"= {scr_prov:,.0f}€ "
                f"(ratio SCR/BE = {ratio:.1%})"
            ),
        }

    # =========================================================================
    #  RISK MARGIN S2 (Art. 77 §5 — Directive Solvabilité 2)
    # =========================================================================

    def _calculer_risk_margin(
        self,
        be:     float,
        scr:    Dict,
        f_cum:  list,
        courbe: dict = None,
    ) -> Dict:
        """
        Risk Margin S2 — Méthode proportionnelle au BE (méthode 2 EIOPA).

        RM = CoC × Σ_{t=0}^{T} [ SCR_NL(t) / (1+r_t)^(t+1) ]

        SCR_NL(t) = SCR_NL(0) × BE(t) / BE(0)   [méthode 2]
        BE(t)     = BE(0) / CDF(t)               [run-off CL]
        CoC       = 6%                            [EIOPA fixé]
        r_t       = courbe EIOPA RFR EUR embarquée (Q1 2025)
        """
        COC  = 0.06
        be_0 = max(float(be), 1.0)
        scr_0 = float(scr.get('scr_provisions', 0))

        if be_0 <= 0 or scr_0 <= 0 or not f_cum:
            return {
                'risk_margin':              0.0,
                'provisions_techniques_s2': round(be_0, 0),
                'ratio_rm_be':              0.0,
                'coc':                      COC,
                'date_courbe_rfr':          DATE_COURBE,
                'peremption_courbe':        diagnostic_peremption(),
                'tableau_run_off':          [],
                'message': 'Risk Margin non calculable — données insuffisantes.',
            }

        rm_sum = 0.0
        tableau = []

        # PROFIL DE RUN-OFF RETENU — et il est un CHOIX, pas une donnée.
        # `f_cum` est dans l'ordre [CDF_dernière_col, …, CDF_1ère_col]. On pose
        # la part encore à développer à la colonne j, pct_résiduel[j] = 1/f_cum[j],
        # puis :
        #
        #     BE(t) = BE(0) × Σ_{j≥t} pct_résiduel[j] / Σ_j pct_résiduel[j]
        #
        # et le SCR projeté proportionnellement au BE (méthode 2 de l'orientation
        # EIOPA sur la Risk Margin).
        #
        # ⚠️ CE CHOIX PÈSE LOURD, ET LE CHIFFRE EST MESURÉ, PAS ESTIMÉ (lot F2).
        # Sur GenIns, BE = 17 571 609 € : le profil ci-dessus rend une Risk
        # Margin de 2 107 541 € (11,99 % du BE) ; un amortissement LINÉAIRE sur
        # la même durée, tout aussi admissible au titre de la méthode 2, rend
        # 1 582 906 € (9,01 % du BE) — soit **−24,9 %**. Le profil n'est donc
        # pas un détail de mise en œuvre : il déplace le quart d'un poste de
        # bilan, et c'est à ce titre qu'il est écrit ici plutôt que déduit du
        # code par le lecteur.
        #
        # Deux esquisses de profils ABANDONNÉES occupaient cette place, dont une
        # inachevée finissant sur un commentaire vide. Elles décrivaient des
        # méthodes qui ne sont pas celle appliquée : les garder revenait à
        # documenter le code par ce qu'il ne fait pas.
        pct_res  = [1.0 / max(float(f), 1.0) for f in f_cum]
        total_pr = max(sum(pct_res), 1e-10)
        m_rm     = len(pct_res)
        be_par_t = []
        for _t in range(m_rm + 15):
            if _t == 0:
                be_par_t.append(be_0)
            elif _t < m_rm:
                be_par_t.append(be_0 * sum(pct_res[_t:]) / total_pr)
            else:
                be_par_t.append(0.0)

        for t, be_t in enumerate(be_par_t):
            if be_t < be_0 * 0.001:
                break

            # SCR projeté (méthode 2 — proportionnel au BE)
            scr_t    = scr_0 * (be_t / be_0)
            r_t      = get_taux_rfr(t + 1)
            fact_act = 1.0 / (1.0 + r_t) ** (t + 1)
            contrib  = COC * scr_t * fact_act
            rm_sum  += contrib

            tableau.append({
                'annee':      t,
                'be_t':       round(be_t,    0),
                'scr_t':      round(scr_t,   0),
                'taux_rfr':   round(r_t * 100, 4),
                'fact_act':   round(fact_act,  6),
                'contrib_rm': round(contrib,   0),
            })

        risk_margin = round(rm_sum, 0)
        pt_s2       = round(be_0 + risk_margin, 0)
        ratio_rm_be  = round(risk_margin / be_0 * 100, 2)
        _diag_courbe = diagnostic_peremption()

        return {
            'risk_margin':              risk_margin,
            'provisions_techniques_s2': pt_s2,
            'ratio_rm_be':              ratio_rm_be,
            'coc':                      COC,
            'date_courbe_rfr':          DATE_COURBE,
            # La péremption de la courbe voyage AVEC la Risk Margin qu'elle
            # actualise : sans ça, l'âge de la courbe n'atteignait aucun livrable.
            'peremption_courbe':        _diag_courbe,
            'tableau_run_off':          tableau,
            'message': (
                f"Risk Margin = {risk_margin:,.0f}€ ({ratio_rm_be:.1f}% du BE). "
                f"Provisions Techniques S2 = {pt_s2:,.0f}€. "
                f"CoC=6%, courbe EIOPA RFR EUR du {DATE_COURBE}. "
                f"Méthode proportionnelle au BE (méthode 2 EIOPA, Art. 77 §5)."
                + ('' if _diag_courbe['statut'] == 'VERT'
                   else ' ' + _diag_courbe['message'])
            ),
        }

    # =========================================================================
    #  SENSIBILITÉS
    # =========================================================================

    def _calculer_sensibilites(
        self,
        methodes_incluses: Dict,
        poids:             Dict,
        boot:              Dict,
        be:                float,
        boot_ok:           bool = True,
    ) -> Dict:
        """
        Analyse de sensibilité du BE aux hypothèses clés.

        Tests :
        · Exclusion de chaque méthode tour à tour
        · Fourchette Bootstrap (IC 95%)

        ⚠️ REPONDÉRATION SUR LES POIDS EFFECTIFS, PLUS SUR LES SCORES. Cette
        fonction renormalisait `score / Σ scores` — une pondération que le Best
        Estimate lui-même avait cessé d'appliquer au lot B, qui lui a substitué
        des poids égaux par année. La sensibilité décrivait donc un BE qui
        n'existait plus, et le paramètre `poids` — la part EFFECTIVE de chaque
        méthode dans le résultat publié — était reçu puis ignoré. Il sert
        désormais : on retire une méthode et l'on renormalise ce qui reste.
        """
        sensibilites: Dict[str, float] = {}

        # Sensibilité à l'exclusion de chaque méthode
        for m_exclu in methodes_incluses:
            autres = {k: v for k, v in methodes_incluses.items() if k != m_exclu}
            if autres:
                poids_autres = {k: float(poids.get(k, 1.0 / len(autres)))
                                for k in autres}
                total = sum(poids_autres.values())
                if total <= 0:                     # poids tous nuls : équipartition
                    poids_autres = {k: 1.0 / len(autres) for k in autres}
                    total = 1.0
                be_sans = sum(poids_autres[k] / total * float(autres[k])
                              for k in autres)
                sensibilites[f'sans_{m_exclu}'] = round(be_sans, 0)

        # Fourchette Bootstrap — MÊME PORTE QUE LES PERCENTILES PUBLIÉS.
        # `boot_ok` porte à la fois la disponibilité du Bootstrap et le verdict
        # de BOOT-H1..H4 : retirer `reserve_p90_boot` du livrable tout en le
        # republiant ici sous un autre nom n'aurait aucun sens. Le défaut d'un
        # `.get(clé, défaut)` mérite d'être noté : ces clés EXISTENT et valent
        # `None` quand le Bootstrap est dégradé, si bien que le défaut ne se
        # déclenchait jamais et que `round(None, 0)` levait un TypeError.
        if boot_ok and (boot.get('be_bootstrap') or 0) > 0:
            sensibilites['boot_ic_inf'] = round(float(
                boot.get('ic_95_inf') if boot.get('ic_95_inf') is not None
                else be * 0.85), 0)
            sensibilites['boot_ic_sup'] = round(float(
                boot.get('ic_95_sup') if boot.get('ic_95_sup') is not None
                else be * 1.15), 0)
            sensibilites['boot_p90'] = round(float(
                boot.get('p90') if boot.get('p90') is not None
                else be * 1.10), 0)
            sensibilites['boot_p99_5'] = round(float(
                boot.get('p99_5') if boot.get('p99_5') is not None
                else be * 1.30), 0)

        return sensibilites

    # =========================================================================
    #  JUGEMENT ACTUARIEL DOCUMENTÉ
    # =========================================================================

    def _documenter_jugement(
        self,
        incluses:  Dict,
        exclues:   Dict,
        poids:     Dict,
        be:        float,
        cv:        float,
        n2:        Dict,
        n3:        Dict,
        statut:    str,
        scr:       Dict,
        cfg:       Dict,
    ) -> str:
        """
        Génère le texte de jugement actuariel documenté.

        Format conforme à un rapport actuaire désigné ACPR :
        sections numérotées, décision explicite, recommandations.
        """
        methode_rec = n2.get('methode_recommandee', 'mack')
        raison_rec  = n2.get('raison_recommandation', '')
        raison_cl   = n2.get('raison_cl', '')
        h1          = n2.get('h1_independance', {})
        h2          = n2.get('h2_stabilite', {})
        bfcc        = n2.get('bfcc', {}).get('hypotheses', {})
        lob_label   = cfg.get('label', 'Non précisée')
        date_str    = datetime.now().strftime('%d/%m/%Y')
        sigma       = n3['mack']['sigma_total']
        p90         = n3['mack']['reserve_p90']
        p995        = n3['mack']['reserve_p99_5']

        lignes = [
            f"JUGEMENT ACTUARIEL — {date_str}",
            f"Branche : {lob_label}",
            "─" * 60,
            "",
            "1. MÉTHODES RETENUES ET EXCLUES",
            "─" * 40,
        ]

        for m, r in incluses.items():
            lignes.append(
                f"  ✅ {m.replace('_', ' ').title():30s} "
                f"réserve={float(r):>14,.0f}€  poids={poids.get(m, 0):.0%}"
            )
        for m, (r, motif) in exclues.items():
            lignes.append(
                f"  ❌ {m.replace('_', ' ').title():30s} exclue — {motif}"
            )

        lignes += [
            "",
            "2. VALIDATION DES HYPOTHÈSES ACTUARIELLES",
            "─" * 40,
            f"  H1 Indépendance   : "
            f"{'✅ VALIDÉE' if h1.get('ok') else '⚠️ REJETÉE':15s} "
            f"corr_moy={h1.get('corr_moy', 0):.2f}  "
            f"score={h1.get('score', 0)}/100",
            f"  H2 Stabilité      : "
            f"{'✅ VALIDÉE' if h2.get('ok') else '⚠️ REJETÉE':15s} "
            f"CV={h2.get('cv_moy', 0):.1%}  "
            f"dérive={h2.get('derive_moy', 0):.1%}  "
            f"score={h2.get('score', 0)}/100",
            "",
            "   Bornhuetter-Ferguson et Cape Cod — hypothèses propres :",
        ] + [
            f"  {code} {bfcc[code].get('libelle', ''):42.42s} "
            f"{bfcc[code].get('statut', 'NON TESTABLE')}"
            for code in ('BFCC-H1', 'BFCC-H2', 'BFCC-H3', 'BFCC-H4', 'BFCC-H5')
            if code in bfcc
        ] + [
            "",
            "   Bootstrap ODP — hypothèses propres :",
        ] + [
            f"  {l['code']} {l['libelle'].split('— ', 1)[-1]:42.42s} {l['statut']}"
            + ("   ⚠️ percentiles retirés"
               if l['statut'] == 'NON VALIDÉE' and l['critique'] else "")
            for l in lignes_hypotheses_bootstrap(n2)
        ] + [
            "",
            f"  Méthode CL retenue    : {n2.get('methode_cl_retenue', '—')}",
            f"  Justification CL      : {raison_cl}",
            f"  Méthode recommandée   : {methode_rec}",
            f"  Justification         : {raison_rec}",
            "",
            "3. BEST ESTIMATE — RÉSERVE BRUTE (Art. 77 ; actualisation S2 par A10)",
            "─" * 40,
            f"  BE retenu         : {be:>16,.0f} €",
            f"  Provision P75     : {n3['mack'].get('reserve_p75', 0):>16,.0f} €",
            f"  Provision P90     : {p90:>16,.0f} €",
            f"  Provision P99.5   : {p995:>16,.0f} €",
            f"  σ Mack total      : {sigma:>16,.0f} €",
            f"  CV inter-méthodes : {cv:>15.1f} %"
            f"  {'(acceptable)' if cv < 5 else '(à surveiller)' if cv < 15 else '(élevé)'}",
            "",
            "4. SCR PROVISIONS (Art. 115 S2)",
            "─" * 40,
            f"  {scr['message']}",
            f"  Ratio SCR/BE      : {scr['ratio_scr_be']:.1%}",
        ]

        # Alertes LoB spécifiques
        alertes_lob = cfg.get('alertes_specifiques', [])
        if alertes_lob:
            lignes += ["", "5. POINTS DE VIGILANCE — BRANCHE", "─" * 40]
            for a in alertes_lob[:4]:
                lignes.append(f"  ⚠️  {a}")
        else:
            lignes += ["", "5. POINTS DE VIGILANCE", "─" * 40]

        # Alertes N2
        for alerte in n2.get('alertes', [])[:3]:
            clean = str(alerte).strip()
            if clean:
                lignes.append(f"  {clean}")

        lignes += [
            "",
            "6. DÉCISION ET RECOMMANDATIONS",
            "─" * 40,
        ]

        if statut == 'VERT':
            lignes += [
                f"  AVIS FAVORABLE — Les méthodes convergent (CV={cv:.1f}%).",
                f"  BE de {be:,.0f}€ retenu pour inscription au bilan S2.",
                f"  Utiliser {p90:,.0f}€ pour le calcul du SCR provisions.",
                f"  Archiver ce rapport et l'audit trail associé.",
            ]
        elif statut == 'AMBRE':
            lignes += [
                f"  AVIS AVEC RÉSERVES — Divergence modérée (CV={cv:.1f}%).",
                f"  BE de {be:,.0f}€ utilisable sous réserve de validation",
                f"  par l'actuaire désigné avant signature du bilan.",
                f"  Constituer une provision de risque complémentaire.",
            ]
        else:
            lignes += [
                f"  AVIS DÉFAVORABLE — Divergence importante (CV={cv:.1f}%).",
                f"  BE à valider impérativement par l'actuaire désigné.",
                f"  Ne pas inscrire au bilan S2 sans validation formelle.",
                f"  Révision approfondie des hypothèses recommandée.",
            ]

        return "\n".join(lignes)
