# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 : LIRE L'INVENTAIRE DE CONTRATS, ET DIRE CE QU'ON A LU
=============================================================================

LE LECTEUR AFFICHE CE QU'IL A COMPRIS, PUIS CE QUI MANQUE ET CE QUE L'ABSENCE
COÛTE — EN TERMES DE LA NORME. C'est le patron du lecteur EIOPA du chantier
RFR : un fichier client ne se devine pas en silence, il se lit, se montre et
se fait confirmer.

⚠️ IL NE REFUSE QUE SUR QUATRE MOTIFS, ET C'EST DÉLIBÉRÉ. Une plateforme qui
exige quinze fichiers avant de produire un chiffre n'a aucune chance face aux
acteurs établis. La règle vient de la couche triangle, qui l'applique déjà :
lever si le tableau ne permet RIEN, sinon décrire ce qui est faisable. Ici,
« rien » se réduit à deux champs — sans année d'émission il n'y a aucune
cohorte (§22), sans portefeuille aucun regroupement (§14).

⚠️ LE REFUS SUR `date_emission` DÉFINIT LE PRODUIT. L'exemption de cohorte
annuelle de l'article 2 du règlement (UE) 2023/1803 ne vise que la
participation directe et l'ajustement égalisateur — elle est FERMÉE au
non-vie. Produire des groupes sans cohortes livrerait la non-conformité même
que ce socle corrige, sous une étiquette conforme.

⚠️ CE MODULE N'IMPORTE RIEN DE `direction_non_vie`. Les conventions de
lecture viennent de `nv_triangle_io` — séparateur détecté, onglet explicite —
mais elles sont RECOPIÉES et non importées : `normes/` est transversal aux
directions, l'y attacher recréerait le couplage que l'architecture défait.

⚠️ IL NE RÉINVENTE PAS LES CAPACITÉS. Ce qu'un champ débloque vit dans
`contrat.py` et nulle part ailleurs : ce que le client lit à l'écran et ce
que le code appliquera ne peuvent donc pas diverger.

⚠️ LA CONFIRMATION DES CHAMPS SCELLÉS N'EST PAS ICI (lot D2b). §16, §22 et
§53 s'apprécient « à la date de la création du groupe » : une erreur sur
`portefeuille`, `date_emission` ou `classe_profitabilite` n'est pas
rattrapable à l'arrêté suivant. Le diagnostic les SIGNALE dès maintenant ;
la porte de confirmation se posera avec le registre, seul moment où elle a
un sens.
=============================================================================
"""

import csv
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

import pandas as pd

from normes.ifrs17.socle.contrat import (
    CHAMPS, EXIGENCES, capacites, champs_bloquants, champs_scelles,
    exigences_hors_portee, reference)

# =============================================================================
#  LE VOCABULAIRE D'ENTRÉE
# =============================================================================

#: Synonymes reconnus sans réserve : la cible ne fait pas de doute.
SYNONYMES: Dict[str, Tuple[str, ...]] = {
    'portefeuille': ('lob', 'branche', 'produit', 'ligne_produit',
                     'portfolio', 'product', 'line_of_business', 'segment'),
    'date_emission': ('date_souscription', 'date_emission', 'dt_souscription',
                      'annee_souscription', 'exercice_souscription',
                      'issue_date', 'underwriting_year', 'inception_date'),
    'debut_couverture': ('date_effet', 'dt_effet', 'date_debut',
                         'debut_garantie', 'effective_date', 'start_date'),
    'fin_couverture': ('date_echeance', 'dt_echeance', 'date_fin',
                       'fin_garantie', 'expiry_date', 'end_date'),
    'date_emission_min': ('date_emission_min', 'emission_min',
                          'date_souscription_min', 'dt_souscription_min',
                          'premiere_emission', 'first_issue_date'),
    'date_emission_max': ('date_emission_max', 'emission_max',
                          'date_souscription_max', 'dt_souscription_max',
                          'derniere_emission', 'last_issue_date'),
    'prime': ('prime_ht', 'prime_annuelle', 'prime_totale', 'prime_emise',
              'cotisation', 'premium', 'written_premium'),
    'frais_acquisition': ('frais_acquisition', 'commission', 'commissions',
                          'frais_courtage', 'acquisition_cost', 'dac'),
    'sinistres_attendus': ('sinistres_attendus', 'charge_attendue',
                           'cout_attendu', 'sp_attendu', 'expected_claims'),
    'classe_profitabilite': ('classe_profitabilite', 'groupe_profitabilite',
                             'onerosite', 'profitability_bucket'),
    'nb_contrats': ('nb_contrats', 'nombre_contrats', 'effectif', 'count',
                    'nb_polices'),
    'entite': ('entite', 'entite_juridique', 'societe', 'entity',
               'legal_entity'),
    'devise': ('devise', 'monnaie', 'currency', 'ccy'),
    'identifiant_contrat': ('identifiant_contrat', 'police', 'num_police',
                            'numero_police', 'id_contrat', 'policy_id',
                            'contract_id'),
    'prime_encaissee': ('prime_encaissee', 'prime_recue', 'cash_premium'),
    'date_resiliation': ('date_resiliation', 'dt_resiliation',
                         'cancellation_date'),
    'groupe_declare': ('groupe_declare', 'groupe_ifrs17', 'group_id'),
    'traite_lie': ('traite_lie', 'traite', 'traite_reassurance', 'treaty'),
    'participation_directe': ('participation_directe', 'vfa',
                              'direct_participation'),
    'composante_investissement': ('composante_investissement',
                                  'investment_component'),
}

#: ⚠️ RECONNUS, MAIS SOUS RÉSERVE — le diagnostic les nomme un par un.
#: `prime_acquise` est la part ACQUISE de la prime, pas la prime attendue sur
#: toute la couverture que §55 a) i) demande : les confondre sous-évalue le
#: LRC des contrats souscrits en cours d'exercice. On l'accepte plutôt que de
#: refuser un client qui n'a que cette colonne, mais on le DIT.
AMBIGUS: Dict[str, str] = {
    'prime_acquise':   'prime',
    'primes_acquises': 'prime',
    'earned_premium':  'prime',
}

#: Indices qu'on nous a remis un fichier de SINISTRES. C'est l'erreur la plus
#: probable, et un refus qui la nomme vaut mieux qu'un refus qui la subit.
INDICES_FICHIER_SINISTRES = frozenset({
    'annee_survenance', 'accident_year', 'annee_developpement', 'dev',
    'montant_paye', 'paid', 'montant_charge', 'incurred', 'sinistre_id',
    'claim_id', 'annee_sinistre',
})

_INDEX_SYNONYMES: Dict[str, str] = {
    syn: champ for champ, syns in SYNONYMES.items() for syn in syns}

#: Comment une colonne a été rattachée — la nuance importe au client.
PAR_NOM_CANONIQUE = 'nom canonique'
PAR_SYNONYME = 'synonyme'
PAR_DECLARATION = 'déclaration'
PAR_SYNONYME_AMBIGU = 'synonyme sous réserve'


# =============================================================================
#  LE REFUS
# =============================================================================

class RefusLecture(Exception):
    """L'inventaire ne permet RIEN — les quatre seuls cas.

    `motif` est un code stable ; le message, lui, est écrit pour un humain
    qui doit corriger son fichier.
    """

    def __init__(self, motif: str, message: str):
        self.motif = motif
        super().__init__(message)


MOTIF_SANS_DATE_EMISSION = 'SANS_DATE_EMISSION'
MOTIF_SANS_PORTEFEUILLE = 'SANS_PORTEFEUILLE'
MOTIF_AUCUNE_LIGNE = 'AUCUNE_LIGNE'
MOTIF_COLONNES_CONCURRENTES = 'COLONNES_CONCURRENTES'


# =============================================================================
#  CE QUE LA LECTURE REND
# =============================================================================

class Correspondance(NamedTuple):
    """Une colonne du client, rattachée à un champ canonique — et comment."""
    colonne: str
    champ:   str
    par:     str


class RapportInventaire(NamedTuple):
    """Tout ce que le lecteur a compris. Le diagnostic n'en est que la mise
    en mots : rien n'y est calculé qui ne soit ici."""
    conteneur:        str
    detail_conteneur: str          # séparateur détecté, ou onglet lu
    nb_lignes:        int
    nb_colonnes:      int
    correspondances:  Tuple[Correspondance, ...]
    colonnes_ignorees: Tuple[str, ...]
    granularite:      str
    capacites:        Dict[str, bool]
    hors_portee:      Dict[str, Tuple[str, ...]]

    @property
    def champs_lus(self) -> Tuple[str, ...]:
        return tuple(sorted({c.champ for c in self.correspondances}))

    @property
    def sous_reserve(self) -> Tuple[Correspondance, ...]:
        return tuple(c for c in self.correspondances
                     if c.par == PAR_SYNONYME_AMBIGU)

    @property
    def a_confirmer(self) -> Tuple[Correspondance, ...]:
        """Les champs scellés — voir la note D2b en tête de module."""
        scelles = set(champs_scelles())
        return tuple(c for c in self.correspondances if c.champ in scelles)


# =============================================================================
#  LECTURE
# =============================================================================

def _normaliser(nom: Any) -> str:
    """Nom de colonne → forme comparable."""
    return str(nom).strip().lower().replace(' ', '_').replace('-', '_')


def _reconnaitre(nom: Any) -> Tuple[Optional[str], str]:
    """(champ canonique | None, comment). Canonique > synonyme > ambigu."""
    n = _normaliser(nom)
    if n in CHAMPS:
        return n, PAR_NOM_CANONIQUE
    if n in _INDEX_SYNONYMES:
        return _INDEX_SYNONYMES[n], PAR_SYNONYME
    if n in AMBIGUS:
        return AMBIGUS[n], PAR_SYNONYME_AMBIGU
    return None, ''


def _detecter_separateur(chemin: Path) -> str:
    """Le séparateur d'un CSV, pour pouvoir l'AFFICHER.

    `pd.read_csv(sep=None, engine='python')` le devine mais ne le dit pas.
    On le renifle donc nous-mêmes : le client doit pouvoir vérifier que le
    fichier a été découpé comme il l'entendait.
    """
    with open(chemin, 'r', encoding='utf-8-sig', errors='replace') as f:
        echantillon = f.read(8192)
    try:
        return csv.Sniffer().sniff(echantillon, delimiters=',;\t|').delimiter
    except csv.Error:
        return ','


def _lire_tableau(chemin: Path,
                  onglet: Optional[str]) -> Tuple[pd.DataFrame, str, str]:
    """(tableau, conteneur, détail). Un tableau plat, rien d'autre."""
    suffixe = chemin.suffix.lower()
    if suffixe in ('.xlsx', '.xlsm', '.xls'):
        # ⚠️ `sheet_name=None` rendrait un DICT de toutes les feuilles, pas un
        # tableau. On nomme donc la feuille explicitement — et on la DIT, pour
        # qu'un classeur multi-onglets ne se lise pas de travers en silence.
        classeur = pd.ExcelFile(chemin)
        nom = onglet if onglet is not None else classeur.sheet_names[0]
        return classeur.parse(nom), 'Excel', f"onglet « {nom} »"
    if suffixe in ('.csv', '.txt'):
        sep = _detecter_separateur(chemin)
        brut = pd.read_csv(chemin, sep=sep, encoding='utf-8-sig')
        lisible = {'\t': 'tabulation'}.get(sep, f"« {sep} »")
        return brut, 'CSV', f"séparateur {lisible}"
    raise RefusLecture(
        MOTIF_AUCUNE_LIGNE,
        f"Format non pris en charge : « {suffixe} ». L'inventaire de "
        f"contrats se dépose en CSV (.csv, .txt) ou en Excel (.xlsx).")


def lire(chemin, *, onglet: Optional[str] = None,
         correspondances: Optional[Dict[str, str]] = None
         ) -> Tuple[pd.DataFrame, RapportInventaire]:
    """Lit un inventaire de contrats et rend (tableau canonique, rapport).

    `correspondances` — déclaration explicite {colonne client: champ} — prend
    le pas sur les synonymes, colonne par colonne. Même montage que la couche
    triangle : les synonymes couvrent le cas courant, la déclaration tranche
    ce qu'ils ne sauraient deviner.

    Lève `RefusLecture` sur les quatre seuls motifs. Tout le reste se dit
    dans le rapport.
    """
    chemin = Path(chemin)
    brut, conteneur, detail = _lire_tableau(chemin, onglet)

    if brut.empty or not len(brut.columns):
        raise RefusLecture(
            MOTIF_AUCUNE_LIGNE,
            f"Aucune ligne exploitable dans {chemin.name} — le fichier a été "
            f"lu ({conteneur}, {detail}) mais ne contient aucune donnée.")

    declarees = {_normaliser(k): v for k, v in (correspondances or {}).items()}
    inconnues = {v for v in declarees.values() if v not in CHAMPS}
    if inconnues:
        raise RefusLecture(
            MOTIF_COLONNES_CONCURRENTES,
            f"Déclaration invalide : {', '.join(sorted(inconnues))} ne "
            f"sont pas des champs de l'inventaire. Champs valides : "
            f"{', '.join(sorted(CHAMPS))}.")

    liens: List[Correspondance] = []
    ignorees: List[str] = []
    for col in brut.columns:
        n = _normaliser(col)
        if n in declarees:
            liens.append(Correspondance(str(col), declarees[n],
                                        PAR_DECLARATION))
            continue
        champ, par = _reconnaitre(col)
        if champ is None:
            ignorees.append(str(col))
        else:
            liens.append(Correspondance(str(col), champ, par))

    _refuser_si_concurrentes(liens)
    _refuser_si_bloquant_absent(liens, brut, chemin)

    canonique = brut.rename(
        columns={c.colonne: c.champ for c in liens})[
            [c.champ for c in liens]]
    presents = {c.champ for c in liens}

    return canonique, RapportInventaire(
        conteneur=conteneur,
        detail_conteneur=detail,
        nb_lignes=int(len(brut)),
        nb_colonnes=int(len(brut.columns)),
        correspondances=tuple(liens),
        colonnes_ignorees=tuple(ignorees),
        granularite=('ensemble pré-agrégé (§17)' if 'nb_contrats' in presents
                     else 'contrat par contrat'),
        capacites=capacites(presents),
        hors_portee=exigences_hors_portee(presents),
    )


def _refuser_si_concurrentes(liens: List[Correspondance]) -> None:
    """Deux colonnes pour un même champ : le client tranche, pas nous."""
    par_champ: Dict[str, List[str]] = {}
    for lien in liens:
        par_champ.setdefault(lien.champ, []).append(lien.colonne)
    doubles = {ch: cols for ch, cols in par_champ.items() if len(cols) > 1}
    if doubles:
        detail = ' ; '.join(
            f"« {ch} » revendiqué par {', '.join(cols)}"
            for ch, cols in sorted(doubles.items()))
        raise RefusLecture(
            MOTIF_COLONNES_CONCURRENTES,
            f"Deux colonnes revendiquent le même champ — {detail}. Deviner "
            f"reviendrait à choisir à votre place sur une donnée que vous "
            f"verrez scellée : déclarez la correspondance voulue.")


def _refuser_si_bloquant_absent(liens: List[Correspondance],
                                brut: pd.DataFrame, chemin: Path) -> None:
    """Les deux champs sans lesquels rien n'est calculable."""
    presents = {lien.champ for lien in liens}
    colonnes = {_normaliser(c) for c in brut.columns}
    ressemble_sinistres = bool(colonnes & INDICES_FICHIER_SINISTRES)
    indice = (
        f"\n⚠️ Ce fichier porte {', '.join(sorted(colonnes & INDICES_FICHIER_SINISTRES))} : "
        f"il ressemble à un inventaire de SINISTRES. L'inventaire attendu ici "
        f"est celui des CONTRATS — les sinistres arrivent par la chaîne de "
        f"provisionnement, ne les fournissez pas deux fois."
        if ressemble_sinistres else '')

    for champ in champs_bloquants():
        if champ in presents:
            continue
        if champ == 'date_emission':
            raise RefusLecture(
                MOTIF_SANS_DATE_EMISSION,
                f"Aucune date d'émission dans {chemin.name}. Sans elle, "
                f"aucune cohorte annuelle : IFRS 17 §22 interdit de grouper "
                f"des contrats émis à plus d'un an d'intervalle, et "
                f"l'exemption de l'article 2 du règlement (UE) 2023/1803 est "
                f"fermée à l'assurance non-vie. ⚠️ C'est la date à laquelle "
                f"le contrat a été SOUSCRIT — ni la survenance du sinistre, "
                f"ni la date comptable." + indice)
        raise RefusLecture(
            MOTIF_SANS_PORTEFEUILLE,
            f"Aucun axe de portefeuille dans {chemin.name}. IFRS 17 §14 "
            f"demande de regrouper les contrats à risques similaires, gérés "
            f"ensemble : la branche ou la ligne de produits convient." + indice)


# =============================================================================
#  LE DIAGNOSTIC — CE QUE LE CLIENT VOIT
# =============================================================================

def _ordre_paragraphe(exigence: str) -> Tuple[int, int, str]:
    """Classe les exigences dans l'ordre de la norme, pas de l'alphabet.

    Un actuaire lit §14, §16, §22… puis l'annexe B. Sortir §22 avant §14
    parce que « c » précède « p » ferait lire un livrable dans un ordre qui
    n'est celui de rien.
    """
    ref = EXIGENCES[exigence].reference
    annexe = 1 if ref.lstrip('§').startswith('B') else 0
    # ⚠️ `str.isdigit()` accepte les chiffres UNICODE : '④'.isdigit() vaut
    # True, mais int('④') lève. La référence de la règle ActuarIA porte
    # précisément « décision produit ④ ». On restreint donc à l'ASCII, et ce
    # qui n'a pas de numéro passe en fin de liste.
    chiffres = ''.join(ch for ch in ref.split(',')[0] if ch in '0123456789')
    return (annexe, int(chiffres) if chiffres else 9_999, ref)


def diagnostic(rapport: RapportInventaire) -> str:
    """Ce que j'ai compris, ce qui manque, et ce que l'absence coûte.

    ⚠️ JAMAIS DE REFUS GLOBAL, JAMAIS DE VALEUR INVENTÉE POUR COMBLER. Le
    coût d'une absence se dit en paragraphes de la norme : « pas de frais
    d'acquisition » ne veut rien dire pour un client, « §55 a) ii) et B125
    hors de portée » se comprend et se corrige.
    """
    lignes: List[str] = []
    a = lignes.append
    nb = f"{rapport.nb_lignes:,}".replace(',', ' ')

    a(f"INVENTAIRE LU — {rapport.conteneur}, {rapport.detail_conteneur}, "
      f"{nb} lignes, {rapport.nb_colonnes} colonnes.")
    a(f"Granularité : {rapport.granularite}.")
    a("")

    a(f"COLONNES RECONNUES ({len(rapport.correspondances)})")
    for c in rapport.correspondances:
        a(f"  {c.colonne} -> {c.champ}   [{c.par}]")

    if rapport.sous_reserve:
        a("")
        a("SOUS RÉSERVE — à vérifier avant de vous en servir")
        for c in rapport.sous_reserve:
            a(f"  {c.colonne} lu comme « {c.champ} » : "
              f"{CHAMPS[c.champ].libelle}")

    if rapport.a_confirmer:
        a("")
        a("À CONFIRMER AVANT SCELLEMENT — ces champs fixent l'unité de compte")
        a("et ne se corrigent plus après (§16, §22 et §53 s'apprécient à la")
        a("date de création du groupe) :")
        for c in rapport.a_confirmer:
            a(f"  {c.colonne} lu comme « {c.champ} » — "
              f"{CHAMPS[c.champ].libelle}")

    if rapport.colonnes_ignorees:
        a("")
        a(f"COLONNES NON RECONNUES ({len(rapport.colonnes_ignorees)}) — "
          f"ignorées")
        a(f"  {', '.join(rapport.colonnes_ignorees)}")
        a("  Si l'une porte un champ attendu, déclarez la correspondance.")

    possibles = sorted((n for n, ok in rapport.capacites.items() if ok),
                       key=_ordre_paragraphe)
    a("")
    a(f"CE QUE JE PEUX PRODUIRE ({len(possibles)} sur {len(EXIGENCES)})")
    for n in possibles:
        a(f"  OK  {reference(n)}")

    if rapport.hors_portee:
        a("")
        a(f"CE QUI MANQUE, ET CE QUE CELA COÛTE ({len(rapport.hors_portee)})")
        par_champ: Dict[str, List[str]] = {}
        for nom, absents in rapport.hors_portee.items():
            par_champ.setdefault(' ou '.join(absents), []).append(nom)
        for champ, noms in sorted(par_champ.items()):
            a(f"  Sans « {champ} » :")
            for n in sorted(noms, key=_ordre_paragraphe):
                a(f"      hors de portée — {reference(n)}")

    a("")
    a("NON DEMANDÉ ICI : les sinistres. Le passif au titre des sinistres")
    a("survenus (§59 b) vient de la chaîne de provisionnement, pas de ce")
    a("fichier.")
    return '\n'.join(lignes)
