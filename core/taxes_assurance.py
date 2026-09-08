"""
=============================================================================
  ActuarIA — REGISTRE DES TAUX DE TAXE SUR LES CONVENTIONS D'ASSURANCE
=============================================================================

UN SEUL ENDROIT POUR LE TAUX QUI TRANSFORME UNE PRIME HT EN PRIME PAYÉE.

⚠️⚠️ POURQUOI CE MODULE EXISTE. `CHARGEMENTS_DEFAUT` portait `taxes: 0.33`
pour **les vingt LoB**, sans source. L'enquête du 08/09/2026 a retrouvé son
origine — commit `a17f058`, 14/07/2026 — et elle est nue : trois chiffres
dans un plan d'exécution (« auto 33 %, MRH 30 %, RC 9 % »), aucun article,
aucune décomposition. Le dépôt le déclarait lui-même non sourcé, six fois.

  Mesuré : le repli 0,33 sur-taxe la prime TTC de **+22,02 %** sur les
  branches au taux résiduel de 9 %, et de **+17,28 %** sur la protection
  juridique. Latent aujourd'hui — `prime_ttc` n'atteint aucun livrable signé
  — et **armé** : il devient réel le jour où ce prix est publié.

⚠️⚠️ LA PROVENANCE VIT DANS LA DONNÉE, JAMAIS DANS UN COMMENTAIRE. C'est la
doctrine de `parametres_fs.py`, apprise à ses dépens : *« TOUTES les valeurs
fausses étaient commentées Annexe II »*. Un commentaire ne se vérifie pas ;
un champ, si. Et la porte :func:`_taux` REFUSE une source hors vocabulaire —
parce que `parametres_fs` a d'abord écrit cette contrainte en commentaire, et
qu'elle ne contraignait rien.

⚠️⚠️ LE PLAN NE PORTE PAS LE TAUX, IL PORTE LA QUALIFICATION. Un taux écrit
dans vingt YAML, ce sont vingt endroits à corriger à la prochaine loi de
finances. Le plan déclare `regime_fiscal` — *« ce contrat relève du régime
auto véhicule léger »*, une décision de PRODUIT — et ce registre porte le
nombre — *« ce régime, c'est 33 % sur la RC, CGI art. 1001-5° quater »*, un
fait LÉGAL. **Un seul endroit à modifier quand la loi change.**

⚠️ UN RÉGIME MIXTE NE REÇOIT PAS DE NOMBRE. Plusieurs branches mélangent des
garanties taxées différemment — l'habitation (incendie 30 %, reste 9 %),
l'automobile elle-même (RC 33 %, autres garanties 18 %). Un taux moyen
pondéré supposerait une part de prime que personne n'a mesurée. Le registre
rend donc un :class:`RegimeMixte` : un REFUS motivé, qui nomme ses
composantes. *Jamais un chiffre qui masque une décision non prise.*

RÉFÉRENCES
  Article 1001 du Code général des impôts, texte consolidé en vigueur au
  12/08/2026, modifié en dernier lieu par le décret n° 2026-562 du
  29 juin 2026 (JORF n° 0151 du 30/06/2026), applicable depuis le
  1er juillet 2026.
  Doctrine administrative : BOI-TCAS-ASSUR-30-10-10 (incendie),
  BOI-TCAS-ASSUR-30-10-30 (véhicules terrestres à moteur).

⚠️ CE REGISTRE N'EST PAS UNE VALIDATION FISCALE. Il porte des taux sourcés,
relus le 08/09/2026, et il DIT lesquels sont lus dans le texte et lesquels
sont déduits par élimination. Une validation par un fiscaliste reste requise
avant mise en production — et `verifie_le` est là pour que cette relecture ne
soit pas indéfiniment supposée acquise.
=============================================================================
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from typing import NamedTuple

__all__ = [
    'MIXTE_NON_TRANCHE',
    'REGIMES',
    'REGIMES_ADMIS',
    'SOURCES_ADMISES',
    'SOURCE_APPROXIMATION',
    'SOURCE_CGI',
    'SOURCE_DEDUCTION',
    'RegimeFiscalRoute',
    'RegimeMixte',
    'TauxTaxe',
    'diagnostic_peremption',
    'regime_du_plan',
    'route_depuis_dict',
    'synthese_regime_fiscal',
    'taux_applicable',
    'valider_declaration',
]

# =============================================================================
#  LE VOCABULAIRE CONTRÔLÉ DES SOURCES
# =============================================================================

#: ⚠️⚠️ TROIS NATURES, ET LE DOCUMENT DE RÉFÉRENCE LES DISTINGUE LUI-MÊME.
#: Les confondre parerait une déduction d'une référence d'article — le défaut
#: exact que `parametres_fs.py` raconte avoir payé.
SOURCE_CGI = 'CGI_ART_1001'                     # LU dans le texte
SOURCE_DEDUCTION = 'DEDUCTION_PAR_ELIMINATION'  # la branche n'est nommée
#                                                 nulle part : le résiduel
#                                                 s'applique par élimination.
#                                                 À FAIRE CONFIRMER.
SOURCE_APPROXIMATION = 'APPROXIMATION'          # un taux assumé, méthode dite

SOURCES_ADMISES = (SOURCE_CGI, SOURCE_DEDUCTION, SOURCE_APPROXIMATION)

#: Le régime qui n'est PAS un taux : ce contrat mélange des garanties taxées
#: différemment, et aucun nombre ne peut le représenter fidèlement.
MIXTE_NON_TRANCHE = 'MIXTE_NON_TRANCHE'

#: ⚠️ L'ANCIENNETÉ SE COMPTE EN LOIS DE FINANCES, PAS EN JOURS. Un taux fiscal
#: n'est pas une courbe qui dérive : c'est une marche d'escalier. « Douze mois
#: d'ancienneté » ne veut donc pas dire « douze mois d'erreur » — cela veut
#: dire qu'une loi de finances a pu passer sans qu'un humain relise. Le
#: diagnostic ci-dessous rappelle une OBLIGATION DE RELECTURE ; il n'estime
#: aucune erreur.
MOIS_AVANT_AMBRE = 12
MOIS_AVANT_ROUGE = 24


class TauxTaxe(NamedTuple):
    """Un taux de taxe, avec de quoi le justifier ET de quoi le dater.

    ⚠️ DEUX DATES, DEUX QUESTIONS DIFFÉRENTES. `en_vigueur_depuis` dit depuis
    quand la LOI dit cela ; `verifie_le` dit quand un HUMAIN l'a relue. La
    courbe RFR n'en porte qu'une parce qu'elle est publiée, pas relue. Un taux
    fiscal, si — et sans la seconde, la confiance devient indéfinie.

    ⚠️ `methode` N'EST REMPLIE QUE POUR UNE APPROXIMATION, et elle est alors
    OBLIGATOIRE : elle dit ce qui est approximé et **dans quel sens** l'erreur
    joue. Une approximation sans sa méthode est un chiffre nu qui a l'air
    sourcé.
    """
    taux: float                 # décimal — 0.18, jamais 18
    source: str                 # l'un de SOURCES_ADMISES
    reference: str              # 'CGI art. 1001-5° quater'
    en_vigueur_depuis: str      # 'AAAA-MM-JJ' — la date du TEXTE
    verifie_le: str             # 'AAAA-MM-JJ' — la date de la RELECTURE
    libelle: str
    methode: str = ''           # obligatoire si source == APPROXIMATION


class RegimeMixte(NamedTuple):
    """Un régime qui ne peut PAS recevoir un taux unique — et pourquoi.

    ⚠️⚠️ CE N'EST PAS UN TAUX MANQUANT, C'EST UN REFUS MOTIVÉ. *Jamais un
    chiffre qui masque une décision non prise.*

    Deux causes distinctes, et le `motif` dit laquelle :
      · le contrat MÉLANGE des garanties taxées différemment (habitation :
        incendie 30 %, reste 9 %) — un taux unique supposerait une part de
        prime par composante que personne n'a mesurée ;
      · la QUALIFICATION elle-même n'est pas tranchée (bris de machine :
        9 % ou 12 % selon le rattachement, et c'est disputé devant les
        tribunaux) — les composantes sont alors des ALTERNATIVES, pas des
        parts qui s'additionnent.

    `composantes` les nomme avec le taux et l'article de chacune — pour que
    l'actuaire sache exactement ce qu'il faudrait déclarer, ou trancher, pour
    sortir de ce régime.
    """
    composantes: tuple[tuple[str, float, str], ...]   # (libellé, taux, réf.)
    motif: str
    verifie_le: str


Regime = TauxTaxe | RegimeMixte


@dataclasses.dataclass(frozen=True)
class RegimeFiscalRoute:
    """Le régime fiscal d'un plan dont la QUALIFICATION dépend d'un facteur.

    ⚠️⚠️ POURQUOI CETTE FORME EXISTE — ARBITRAGE DU 08/09/2026 SUR LES FLOTTES.
    `flotte_automobile` déclare `type_flotte` à quatre modalités (VL, VUL, PL,
    Mixte) parce que leurs profils de PÉRIL sont distincts. Or la fiscalité
    suit ce même axe sans coïncider avec lui : VL et VUL relèvent de la RC à
    33 %, PL de la RC à 15 %, et « Mixte » est une police qui porte les deux.

      *Un régime posé au niveau du plan, et un seul, aurait eu deux issues
      également fausses : appliquer un taux moyen pondéré — un chiffre qui
      masque une décision non prise — ou refuser tout prix, y compris à un
      parc 100 % poids lourds, qui est pourtant homogène et parfaitement
      tarifable.*

    La route est donc DÉCLARÉE AU PLAN — un seul objet, dans le YAML signé —
    et RÉSOLUE PAR CONTRAT. `Mixte` y route vers `MIXTE_NON_TRANCHE` : un refus
    qui se dit, plutôt qu'un prix moyenné sur deux risques incomparables.

    ⚠️ `regimes` EST UN TUPLE DE PAIRES TRIÉ, PAS UN DICT. Le plan entre dans
    une empreinte SHA-256 opposable : une structure ordonnée déterministe est
    ce qui garantit que deux chargements du même YAML signent pareil.
    """
    selon: str                                  # nom d'un facteur DÉCLARÉ
    regimes: tuple[tuple[str, str], ...]        # (modalité, nom de régime)

    def pour(self, modalite) -> str | None:
        """Le nom de régime d'une modalité, ou ``None`` si elle est inconnue."""
        for m, r in self.regimes:
            if m == modalite:
                return r
        return None


def route_depuis_dict(d: Mapping) -> RegimeFiscalRoute:
    """Construit une route depuis le bloc YAML, en TRIANT les modalités.

    ⚠️ Le tri est ici et nulle part ailleurs : c'est le seul point d'entrée
    depuis un fichier, et c'est lui qui rend l'empreinte reproductible.
    """
    if not isinstance(d, Mapping):
        raise TypeError(
            f"`regime_fiscal` doit être soit un nom de régime, soit un bloc "
            f"`selon:`/`regimes:`, reçu {type(d).__name__}.")
    inconnues = sorted(set(d) - {'selon', 'regimes'})
    if inconnues:
        raise ValueError(
            f"`regime_fiscal` : clé(s) inconnue(s) {inconnues}. Un bloc de "
            f"routage ne porte que `selon` (le facteur) et `regimes` (les "
            f"modalités).")
    if not d.get('selon') or not isinstance(d.get('regimes'), Mapping):
        raise ValueError(
            "`regime_fiscal` : un bloc de routage exige `selon` (le nom d'un "
            "facteur déclaré) ET `regimes` (une modalité -> un régime).")
    return RegimeFiscalRoute(
        selon=str(d['selon']),
        regimes=tuple(sorted((str(k), str(v))
                             for k, v in d['regimes'].items())))


def _taux(taux: float, source: str, reference: str, en_vigueur_depuis: str,
          verifie_le: str, libelle: str, methode: str = '') -> TauxTaxe:
    """Seule porte d'entrée de :data:`REGIMES`, et elle REFUSE.

    ⚠️ ELLE EXISTE PARCE QU'UN `NamedTuple` ACCEPTE N'IMPORTE QUOI. Une source
    inventée — « BOFIP », « art. 999 » — s'installerait dans la table sans que
    rien ne bronche, et un livrable la citerait à un contrôleur. C'est mot pour
    mot l'histoire de `parametres_fs._parametre`.

    ⚠️ ET ELLE EXIGE LA MÉTHODE D'UNE APPROXIMATION. Substituer un silence à
    une méthode laisserait une approximation passer pour une lecture — la
    confusion que le vocabulaire contrôlé existe pour empêcher.
    """
    if source not in SOURCES_ADMISES:
        raise ValueError(
            f"Source de taux non admise : '{source}' (régime '{libelle}', "
            f"référence '{reference}'). Le vocabulaire contrôlé est "
            f"{', '.join(SOURCES_ADMISES)}. Un taux qui n'est pas LU dans "
            f"l'article 1001 se marque '{SOURCE_DEDUCTION}' ou "
            f"'{SOURCE_APPROXIMATION}' — il ne se pare pas d'une référence.")
    if source == SOURCE_APPROXIMATION and not methode.strip():
        raise ValueError(
            f"Régime '{libelle}' : source '{SOURCE_APPROXIMATION}' SANS "
            f"méthode. Une approximation doit dire ce qu'elle approxime et "
            f"dans quel sens — sinon c'est un chiffre nu qui a l'air sourcé.")
    if not isinstance(taux, (int, float)) or isinstance(taux, bool):
        raise TypeError(
            f"Régime '{libelle}' : taux {taux!r} n'est pas un nombre.")
    if not (0.0 <= float(taux) < 1.0):
        raise ValueError(
            f"Régime '{libelle}' : taux {taux!r} hors [0 ; 1[. Le taux se "
            f"déclare en DÉCIMAL (0.18), jamais en pourcentage (18).")
    return TauxTaxe(float(taux), source, reference, en_vigueur_depuis,
                    verifie_le, libelle, methode)


#: ⚠️ LA DATE DE RELECTURE, UNE SEULE FOIS. Toutes les entrées ci-dessous ont
#: été relues le même jour, sur le même document de référence ; répéter la date
#: à chaque ligne inviterait à la faire diverger.
_RELU = '2026-09-08'
_EN_VIGUEUR = '2026-07-01'      # décret n° 2026-562 du 29/06/2026


REGIMES: dict[str, Regime] = {

    # ── Le taux résiduel, appliqué PAR ÉLIMINATION ───────────────────────
    # ⚠️⚠️ LE TAUX EST LU, SON APPLICABILITÉ EST DÉDUITE — et ce n'est pas la
    # même chose. L'article 1001-6° fixe bien 9 % ; mais il ne NOMME aucune des
    # branches qui le portent ici, lesquelles n'y tombent que parce qu'aucun
    # autre alinéa ne les réclame. Le document de référence le dit de lui-même :
    # « c'est une déduction par élimination, pas une lecture directe. À faire
    # confirmer. » Marquer ce régime `CGI_ART_1001` aurait paré la déduction
    # d'une autorité qu'elle n'a pas.
    'residuel_par_elimination': _taux(
        0.09, SOURCE_DEDUCTION, 'CGI art. 1001-6° (par élimination)',
        _EN_VIGUEUR, _RELU,
        "Taux résiduel — branche non nommée à l'article 1001"),

    # ── Le seul taux LU pour une branche NOMMÉE ──────────────────────────
    'protection_juridique': _taux(
        0.134, SOURCE_CGI, 'CGI art. 1001-5° ter', _EN_VIGUEUR, _RELU,
        "Protection juridique — défense pénale et recours de droit commun"),

    # ── L'automobile : une APPROXIMATION, et elle se dit ─────────────────
    # ⚠️⚠️ L'AUTO N'EST PAS UN TAUX SIMPLE. Sa RC obligatoire est à 33 %
    # (art. 1001-5° quater), toutes ses autres garanties à 18 %
    # (art. 1001-5° bis) — BOI-TCAS-ASSUR-30-10-30 l'établit noir sur blanc.
    # Le 0,33 historique du dépôt n'est donc très probablement PAS inventé :
    # c'est le taux légal de la composante DOMINANTE, appliqué au contrat
    # entier. On le garde, et on cesse de le présenter comme un chiffre nu.
    'auto_vehicule_leger': _taux(
        0.33, SOURCE_APPROXIMATION, 'CGI art. 1001-5° quater (RC) et 5° bis',
        _EN_VIGUEUR, _RELU,
        "Automobile véhicule léger — taux RC appliqué au contrat entier",
        methode=(
            "Le taux de la RC obligatoire (33 %) est applique a TOUTE la "
            "prime, alors que les autres garanties du contrat relevent de "
            "18 %. Sur-taxation MESUREE le 08/09/2026 sur le portefeuille de "
            "reference (39,98 % Tiers, 60,02 % TousRisques) : +0,00 % si la "
            "part RC d'un TousRisques vaut 100 %, +3,50 % a 50 %, +5,73 % a "
            "20 %. L'approximation MAJORE : elle ne sous-taxe jamais. Sortir "
            "de l'approximation exige de declarer au plan la part de prime "
            "imputable a la RC, qui est un fait de PORTEFEUILLE et non une "
            "donnee legale.")),

    'auto_poids_lourd': _taux(
        0.15, SOURCE_APPROXIMATION, 'CGI art. 1001-5° quater (RC) et 5° bis',
        _EN_VIGUEUR, _RELU,
        "Automobile poids lourd (> 3,5 t) et utilitaire agricole — taux RC "
        "appliqué au contrat entier",
        methode=(
            "Meme approximation que 'auto_vehicule_leger', avec le taux RC des "
            "poids lourds (15 %). ⚠ ELLE MINORE ICI, la ou l'autre majore : "
            "les autres garanties du contrat sont a 18 %, donc AU-DESSUS de "
            "15 %. Le sens de l'erreur s'inverse avec le taux, et il doit etre "
            "lu avant toute mise en production. Mesure du 08/09/2026 : "
            "appliquer 33 % a un parc poids lourd le sur-taxerait de +13,58 % "
            "a +15,65 % selon la part RC.")),

    # ── Les régimes MIXTES : aucun nombre ────────────────────────────────
    'habitation': RegimeMixte(
        composantes=(
            ("incendie", 0.30, 'CGI art. 1001-1°'),
            ("autres garanties (vol, dégâts des eaux, RC…)", 0.09,
             'CGI art. 1001-6°'),
        ),
        motif=(
            "Une multirisque habitation mélange une composante incendie taxée "
            "à 30 % et des garanties au taux résiduel de 9 %. Un taux unique "
            "supposerait la part de prime imputable à l'incendie — un fait de "
            "portefeuille que le plan ne déclare pas."),
        verifie_le=_RELU),

    'incendie_professionnel': RegimeMixte(
        composantes=(
            ("incendie — biens à usage professionnel permanent et exclusif",
             0.12, 'CGI art. 1001-2°, décret 2026-562'),
            ("autres garanties", 0.09, 'CGI art. 1001-6°'),
        ),
        motif=(
            "Composante incendie professionnelle à 12 % depuis le "
            "1er juillet 2026 — elle valait 7 % avant le décret n° 2026-562 — "
            "et reste des garanties au taux résiduel de 9 %. La part incendie "
            "n'est pas déclarée au plan. Régime commun à la multirisque "
            "professionnelle, à la multirisque immeuble et à la perte "
            "d'exploitation, dont les pertes consécutives à un incendie "
            "suivent le même taux de 12 %."),
        verifie_le=_RELU),

    'bris_machine_qualification': RegimeMixte(
        composantes=(
            ("qualification « dommage matériel générique »", 0.09,
             'CGI art. 1001-6°'),
            ("qualification « rattaché à la garantie incendie du site »",
             0.12, 'CGI art. 1001-2°, décret 2026-562'),
        ),
        motif=(
            "⚠ CE N'EST PAS UN MÉLANGE DE PARTS, C'EST UNE QUALIFICATION NON "
            "TRANCHÉE : les deux composantes ci-dessus sont des ALTERNATIVES "
            "qui ne s'additionnent pas. Selon que le contrat couvre un dommage "
            "matériel générique ou qu'il se rattache à la garantie incendie du "
            "site, le taux applicable change du tout au tout. Une jurisprudence "
            "récente montre que ce rattachement se dispute effectivement devant "
            "les tribunaux. Trancher relève de la rédaction du produit, pas du "
            "code."),
        verifie_le=_RELU),

    'risques_agricoles': RegimeMixte(
        composantes=(
            ("incendie agricole", 0.07, 'CGI art. 1001-2°'),
            ("autres garanties", 0.09, 'CGI art. 1001-6°'),
            (("contribution au fonds national de gestion des risques en "
              "agriculture — HORS TSCA"), 0.11, 'code rural, hors CGI'),
        ),
        motif=(
            "Trois composantes, dont une qui n'est PAS une taxe sur les "
            "conventions d'assurance mais une contribution distincte, prévue "
            "par le code rural. Les additionner dans un champ « taxes » "
            "mélangerait deux natures, et le total ne serait opposable ni au "
            "titre de l'une ni au titre de l'autre."),
        verifie_le=_RELU),
}

#: ⚠️ Les noms qu'un plan peut DÉCLARER. `MIXTE_NON_TRANCHE` en fait partie :
#: c'est une déclaration honnête, pas un défaut de déclaration.
REGIMES_ADMIS = tuple(sorted(REGIMES)) + (MIXTE_NON_TRANCHE,)


#: Le régime rendu quand un plan — ou une modalité — déclare `MIXTE_NON_TRANCHE`.
_REFUS_DECLARE = RegimeMixte(
    composantes=(),
    motif=("Le plan déclare explicitement que le régime fiscal de ce contrat "
           "n'est PAS tranché : les garanties qu'il réunit ne relèvent pas du "
           "même taux. Aucune prime TTC n'est publiée."),
    verifie_le=_RELU)


# =============================================================================
#  VALIDER CE QU'UN PLAN DÉCLARE — appelée par `PlanTarifaire.__post_init__`
# =============================================================================

def valider_declaration(declaration, facteurs: Sequence, lob: str) -> None:
    """Refuse une déclaration de régime fiscal qui ne peut pas être tenue.

    ⚠️⚠️ ELLE VIT ICI, PAS DANS `PlanTarifaire`. Le vocabulaire des régimes est
    la connaissance de ce module ; une seconde liste dans le plan divergerait
    au premier régime ajouté — c'est le défaut que `ASSIETTES_SEUIL_GRAVE`
    documente déjà avoir évité en dérivant ses valeurs plutôt qu'en les
    recopiant.

    ⚠️⚠️ ET ELLE VÉRIFIE LES DEUX SENS DU ROUTAGE. Une modalité du facteur sans
    régime laisserait un contrat sans qualification ; un régime pour une
    modalité qui n'existe pas est une règle qui **ne se déclenchera jamais**,
    donc un garde-fou qui n'en est pas. *La leçon du verrou à sens unique de la
    frontière LLM, fermé le 08/09/2026 : demander « chaque déclaré existe-t-il
    ? » sans demander « chaque réel est-il déclaré ? » laisse passer exactement
    la moitié des fautes.*
    """
    if declaration is None:
        return
    if isinstance(declaration, str):
        if declaration not in REGIMES_ADMIS:
            raise ValueError(
                f"Plan '{lob}' : regime_fiscal='{declaration}' inconnu — "
                f"attendu l'un de {', '.join(REGIMES_ADMIS)}. Un régime absent "
                f"du registre n'a ni taux, ni source, ni date de relecture : il "
                f"ne peut pas porter une prime opposable.")
        return
    if not isinstance(declaration, RegimeFiscalRoute):
        raise TypeError(
            f"Plan '{lob}' : regime_fiscal doit être un nom de régime ou un "
            f"bloc de routage, reçu {type(declaration).__name__}.")

    par_nom = {getattr(f, 'nom', None): f for f in facteurs}
    facteur = par_nom.get(declaration.selon)
    if facteur is None:
        raise ValueError(
            f"Plan '{lob}' : regime_fiscal route SELON '{declaration.selon}', "
            f"qui n'est pas un facteur déclaré du plan (facteurs : "
            f"{', '.join(sorted(n for n in par_nom if n)) or 'aucun'}). Une "
            f"route sur un facteur inexistant ne se déclencherait jamais.")
    modalites = tuple(getattr(facteur, 'modalites', None) or ())
    if not modalites:
        raise ValueError(
            f"Plan '{lob}' : regime_fiscal route selon le facteur "
            f"'{declaration.selon}', qui ne déclare aucune modalité. Le "
            f"routage fiscal suit un axe CATÉGORIEL énuméré ; sur un facteur "
            f"continu, il n'y a rien à router.")

    declarees = tuple(m for m, _ in declaration.regimes)
    manquantes = sorted(set(modalites) - set(declarees))
    if manquantes:
        raise ValueError(
            f"Plan '{lob}' : regime_fiscal ne qualifie pas les modalités "
            f"{manquantes} du facteur '{declaration.selon}'. Un contrat "
            f"portant l'une d'elles n'aurait aucun régime — et l'absence de "
            f"décision se lirait comme un prix. Qualifiez-les, ou déclarez-les "
            f"'{MIXTE_NON_TRANCHE}'.")
    fantomes = sorted(set(declarees) - set(modalites))
    if fantomes:
        raise ValueError(
            f"Plan '{lob}' : regime_fiscal qualifie {fantomes}, qui ne sont PAS "
            f"des modalités de '{declaration.selon}' ({', '.join(modalites)}). "
            f"Une règle écrite pour une modalité inexistante ne se déclenche "
            f"jamais : elle a l'apparence d'un garde-fou sans en être un.")
    for modalite, nom in declaration.regimes:
        if nom not in REGIMES_ADMIS:
            raise ValueError(
                f"Plan '{lob}' : regime_fiscal['{modalite}']='{nom}' inconnu — "
                f"attendu l'un de {', '.join(REGIMES_ADMIS)}.")


# =============================================================================
#  LIRE LE RÉGIME D'UN PLAN, POUR UN CONTRAT
# =============================================================================

def regime_du_plan(plan, contrat: Mapping | None = None) -> Regime | None:
    """Le régime fiscal applicable, ou ``None`` si le plan n'en déclare pas.

    ⚠️ ELLE NE DEVINE RIEN. Un plan sans `regime_fiscal` rend ``None`` et
    l'appelant retombe sur son repli — le comportement d'aujourd'hui, inchangé.
    Deviner le régime depuis le nom de la LoB serait exactement le défaut
    « rôle métier résolu par un nom en dur » que ce module combat.

    ⚠️⚠️ ET UNE MODALITÉ INCONNUE REFUSE, elle ne se replie pas. Le plan
    garantit que toutes les modalités DÉCLARÉES sont qualifiées ; un contrat
    peut malgré tout porter une valeur hors énumération. Lui appliquer le
    premier taux venu signerait un prix sous une qualification que personne n'a
    prise — on rend un refus qui NOMME la valeur reçue.
    """
    declaration = getattr(plan, 'regime_fiscal', None) if plan is not None \
        else None
    if not declaration:
        return None

    if isinstance(declaration, RegimeFiscalRoute):
        if contrat is None:
            return RegimeMixte(
                composantes=tuple(
                    (f"{declaration.selon} = {m}", _taux_ou_nan(n),
                     _reference_ou_nom(n))
                    for m, n in declaration.regimes),
                motif=(f"Le régime fiscal de ce plan dépend du facteur "
                       f"'{declaration.selon}' : il se résout CONTRAT PAR "
                       f"CONTRAT, et aucun contrat n'a été fourni."),
                verifie_le=_RELU)
        modalite = contrat.get(declaration.selon)
        nom = declaration.pour(modalite)
        if nom is None:
            return RegimeMixte(
                composantes=(),
                motif=(f"Le contrat porte {declaration.selon}={modalite!r}, "
                       f"qui n'est pas une modalité qualifiée du plan "
                       f"({', '.join(m for m, _ in declaration.regimes)}). "
                       f"Aucune prime TTC n'est publiée sous une qualification "
                       f"fiscale que personne n'a prise."),
                verifie_le=_RELU)
        declaration = nom

    if declaration == MIXTE_NON_TRANCHE:
        return _REFUS_DECLARE
    return REGIMES.get(declaration)


def _taux_ou_nan(nom: str) -> float:
    """Le taux d'un régime simple ; `nan` pour un régime qui n'en a pas."""
    r = REGIMES.get(nom)
    return r.taux if isinstance(r, TauxTaxe) else float('nan')


def _reference_ou_nom(nom: str) -> str:
    """La référence légale d'un régime simple ; son nom sinon."""
    r = REGIMES.get(nom)
    return r.reference if isinstance(r, TauxTaxe) else nom


def taux_applicable(plan, contrat: Mapping | None = None) -> float | None:
    """Le taux applicable, ou ``None`` quand il n'y en a pas UN.

    ⚠️⚠️ ``None`` A DEUX CAUSES, ET L'APPELANT DOIT LES DISTINGUER : le plan ne
    déclare rien (il retombe sur son repli, et le dit), ou le régime est MIXTE
    (aucun prix TTC ne doit être publié). :func:`regime_du_plan` les sépare —
    ``None`` contre :class:`RegimeMixte` ; celle-ci ne sert qu'au cas simple,
    où les deux se confondraient sans dommage.
    """
    regime = regime_du_plan(plan, contrat)
    return regime.taux if isinstance(regime, TauxTaxe) else None


# =============================================================================
#  LA PÉREMPTION — un rappel de relecture, pas une estimation d'erreur
# =============================================================================

def _age_mois(verifie_le: str,
              aujourdhui: date | None = None) -> float | None:
    if not verifie_le:
        return None
    try:
        a, m, j = (int(x) for x in str(verifie_le).split('-'))
        depuis = date(a, m, j)
    except (ValueError, TypeError):
        return None
    # ⚠️ DTZ011 : `date.today()` depend du fuseau de la machine. Le
    # diagnostic se compte en MOIS -- un jour d'ecart ne le change pas --
    # mais une date sans fuseau n'est pas reproductible d'une machine a
    # l'autre, et ce statut peut voyager dans un livrable.
    ref = aujourdhui or datetime.now(timezone.utc).date()
    return ((ref.year - depuis.year) * 12 + (ref.month - depuis.month)
            + (ref.day - depuis.day) / 30.0)


def diagnostic_peremption(regime: Regime | None,
                          aujourdhui: date | None = None) -> dict:
    """VERT / AMBRE / ROUGE — et un régime SANS date de relecture est ROUGE.

    ⚠️⚠️ CE DIAGNOSTIC NE MESURE PAS UNE ERREUR. Une courbe de taux dérive
    continûment ; un taux fiscal est une MARCHE D'ESCALIER — soit la loi a
    changé, soit rien n'a bougé. « Douze mois d'ancienneté » ne veut donc pas
    dire « douze mois d'erreur ». Ce que ce statut dit, c'est qu'**une loi de
    finances a pu passer sans qu'un humain relise**. L'horloge est la loi de
    finances, pas le calendrier — c'est ce qui rend le seuil défendable plutôt
    qu'arbitraire.

    ⚠️ SEUL LE ROUGE PLAFONNE, comme pour la courbe RFR. Un AMBRE qui
    plafonnerait interdirait le VERT dès le treizième mois, et un avertissement
    permanent cesse d'être lu.
    """
    if regime is None:
        return {'statut': 'VERT', 'age_mois': None, 'message': None}
    mois = _age_mois(getattr(regime, 'verifie_le', ''), aujourdhui)
    if mois is None:
        return {
            'statut': 'ROUGE', 'age_mois': None,
            'message': ("⚠ TAUX DE TAXE SANS DATE DE RELECTURE. Un taux dont "
                        "personne n'a daté la vérification ne peut pas porter "
                        "une prime opposable.")}
    if mois >= MOIS_AVANT_ROUGE:
        return {
            'statut': 'ROUGE', 'age_mois': round(mois, 1),
            'message': (f"⚠ TAUX DE TAXE NON RELU DEPUIS {mois:.0f} MOIS — au "
                        f"moins deux lois de finances ont pu le modifier. "
                        f"Relecture requise avant publication d'une prime "
                        f"TTC.")}
    if mois >= MOIS_AVANT_AMBRE:
        return {
            'statut': 'AMBRE', 'age_mois': round(mois, 1),
            'message': (f"⚠ Taux de taxe non relu depuis {mois:.0f} mois : une "
                        f"loi de finances a pu passer. Ceci n'affirme AUCUNE "
                        f"erreur — un taux fiscal ne dérive pas, il change ou "
                        f"non. C'est un rappel de relecture.")}
    return {'statut': 'VERT', 'age_mois': round(mois, 1), 'message': None}


# =============================================================================
#  LA PHRASE PUBLIABLE — source unique des surfaces signées
# =============================================================================

def synthese_regime_fiscal(plan, contrat: Mapping | None = None,
                           aujourdhui: date | None = None) -> str | None:
    """Le régime appliqué, sa source, sa date — ou ``None`` si rien n'est déclaré.

    ⚠️ SOURCE UNIQUE, comme `synthese_mapping` et `phrase_seuil_suppose` : une
    seule rédaction pour toutes les surfaces. Deux rédactions du même fait
    finissent par en dire deux choses différentes.
    """
    regime = regime_du_plan(plan, contrat)
    if regime is None:
        return None
    if isinstance(regime, RegimeMixte):
        # ⚠️ `nan` marque une composante qui n'a elle-meme PAS de taux --
        # une route dont une branche est un refus. `math.isnan` le dit ;
        # `t == t` le disait aussi, mais seulement a qui connait l'astuce.
        parts = ' ; '.join(
            (f"{lib} -> {ref}" if math.isnan(t)
             else f"{lib} {100 * t:.4g} % ({ref})")
            for lib, t, ref in regime.composantes)
        return ("REGIME FISCAL NON TRANCHE -- aucune prime TTC n'est publiee. "
                + regime.motif
                + (f" Composantes : {parts}." if parts else ""))
    diag = diagnostic_peremption(regime, aujourdhui)
    phrase = (f"Taxe appliquee : {100 * regime.taux:.4g} % "
              f"({regime.libelle}) -- {regime.reference}, en vigueur depuis le "
              f"{regime.en_vigueur_depuis}, relu le {regime.verifie_le}.")
    if regime.source == SOURCE_APPROXIMATION:
        phrase += f" ⚠ APPROXIMATION : {regime.methode}"
    elif regime.source == SOURCE_DEDUCTION:
        phrase += (" ⚠ Taux DEDUIT par elimination : l'article 1001 ne nomme "
                   "pas cette branche. A faire confirmer par un fiscaliste.")
    if diag['message']:
        phrase += f" {diag['message']}"
    return phrase
