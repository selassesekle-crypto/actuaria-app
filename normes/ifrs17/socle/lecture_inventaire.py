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
import unicodedata
from pathlib import Path
from typing import Any, NamedTuple

import pandas as pd

from normes.ifrs17.socle.contrat import (
    CHAMPS,
    EXIGENCES,
    capacites,
    champs_bloquants,
    champs_scelles,
    exigences_hors_portee,
    reference,
)

# =============================================================================
#  LE VOCABULAIRE D'ENTRÉE
# =============================================================================

#: Synonymes reconnus sans réserve : la cible ne fait pas de doute.
SYNONYMES: dict[str, tuple[str, ...]] = {
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
AMBIGUS: dict[str, str] = {
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

_INDEX_SYNONYMES: dict[str, str] = {
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
MOTIF_FORMAT = 'FORMAT'

#: ⚠️ Une ligne de total n'est pas un contrat. Un export Excel en porte
#: presque toujours une en pied de tableau. On l'écarte — ce n'est pas
#: inventer une valeur, c'est reconnaître une ligne qui n'en est pas une —
#: mais JAMAIS en silence : le diagnostic la nomme.
MOTS_DE_TOTAL = ('total', 'totaux', 'sous-total', 'sous total', 'somme',
                 'cumul', 'ensemble', 'general', 'général')

#: Combien de premières lignes on inspecte pour trouver l'en-tête réel.
LIGNES_SONDEES_POUR_ENTETE = 8

#: Séparateurs essayés, par ordre de préférence — « ; » d'abord, l'usage
#: français, qui tranche les égalités.
SEPARATEURS = (';', ',', '	', '|')


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
    correspondances:  tuple[Correspondance, ...]
    colonnes_ignorees: tuple[str, ...]
    granularite:      str
    capacites:        dict[str, bool]
    hors_portee:      dict[str, tuple[str, ...]]
    #: Lignes reconnues comme des totaux et écartées — jamais en silence.
    lignes_ecartees:  tuple[str, ...] = ()

    @property
    def champs_lus(self) -> tuple[str, ...]:
        return tuple(sorted({c.champ for c in self.correspondances}))

    @property
    def sous_reserve(self) -> tuple[Correspondance, ...]:
        return tuple(c for c in self.correspondances
                     if c.par == PAR_SYNONYME_AMBIGU)

    @property
    def a_confirmer(self) -> tuple[Correspondance, ...]:
        """Les correspondances qui exigent une signature avant scellement.

        ⚠️ LES CHAMPS SCELLÉS RECONNUS PAR LEUR NOM CANONIQUE EN SONT EXCLUS.
        Une colonne nommée `date_emission` n'a rien fait deviner : il n'y a
        rien à attester. C'est la seule définition de ce qui doit être
        confirmé — `confirmation.a_confirmer` s'y rapporte plutôt que d'en
        tenir une seconde, qui dériverait un jour.
        """
        scelles = set(champs_scelles())
        return tuple(c for c in self.correspondances
                     if c.champ in scelles and c.par != PAR_NOM_CANONIQUE)


# =============================================================================
#  LECTURE
# =============================================================================

def sans_accents(texte: str) -> str:
    """Forme comparable d'un texte accentué — idiome standard, pas une table.

    ⚠️ NÉCESSAIRE, ET TROUVÉ PAR UN TEST. `DATE_ÉCHÉANCE` — une colonne
    parfaitement ordinaire dans un export français — ne se reconnaissait pas,
    parce que le synonyme est `date_echeance`. Une colonne accentuée était
    donc ignorée en silence.
    """
    return unicodedata.normalize('NFKD', str(texte)) \
        .encode('ascii', 'ignore').decode('ascii')


def _normaliser(nom: Any) -> str:
    """Nom de colonne → forme comparable."""
    return sans_accents(nom).strip().lower() \
        .replace(' ', '_').replace('-', '_')


def _reconnaitre(nom: Any) -> tuple[str | None, str]:
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
                  onglet: str | None) -> tuple[pd.DataFrame, str, str]:
    """(tableau, conteneur, détail). Un tableau plat, rien d'autre."""
    suffixe = chemin.suffix.lower()
    if suffixe in ('.xlsx', '.xlsm'):
        # ⚠️ `sheet_name=None` rendrait un DICT de toutes les feuilles, pas un
        # tableau. On nomme donc la feuille explicitement — et on la DIT, pour
        # qu'un classeur multi-onglets ne se lise pas de travers en silence.
        classeur = pd.ExcelFile(chemin)
        nom = onglet if onglet is not None else classeur.sheet_names[0]
        return classeur.parse(nom), 'Excel', f"onglet « {nom} »"
    if suffixe == '.xls':
        # ⚠️ ANNONCER UN FORMAT QU'ON NE SAIT PAS LIRE EST PIRE QUE DE LE
        # REFUSER. `.xls` (Excel 97-2003) exige le moteur `xlrd`, absent de
        # cet environnement : la lecture échouait sur un « format cannot be
        # determined » qui ne disait rien au client.
        raise RefusLecture(
            MOTIF_FORMAT,
            "Format « .xls » (Excel 97-2003) non lisible ici : il exige le "
            "moteur `xlrd`, absent de cet environnement. Réenregistrez le "
            "fichier en « .xlsx » depuis Excel, ou exportez-le en CSV.")
    if suffixe in ('.csv', '.txt'):
        brut, encodage, sep, saut = _lire_csv(chemin)
        lisible = {'\t': 'tabulation'}.get(sep, f"« {sep} »")
        detail = f"séparateur {lisible}, encodage {encodage}"
        if saut:
            detail += (f", en-tête à la ligne {saut + 1} — les {saut} "
                       f"première(s) ligne(s) sont un titre, pas des données")
        return brut, 'CSV', detail
    raise RefusLecture(
        MOTIF_FORMAT,
        f"Format non pris en charge : « {suffixe} ». L'inventaire de "
        f"contrats se dépose en CSV (.csv, .txt) ou en Excel (.xlsx, .xlsm).")


def _lire_csv(chemin: Path) -> tuple[pd.DataFrame, str, str, int]:
    """Lit un CSV en essayant les encodages, dans l'ordre — et DIT lequel.

    ⚠️ CECI CORRIGE UN DÉFAUT, PAS UNE LACUNE. Le lecteur imposait `utf-8` :
    un CSV en `cp1252` — l'encodage par défaut des systèmes d'assurance
    français — produisait une TRACE DE PILE, pas un diagnostic. C'était le
    seul endroit du socle où la promesse « jamais de refus global, toujours
    un diagnostic » était rompue.

    ⚠️ ESSAI ORDONNÉ, PAS DÉTECTION STATISTIQUE. `charset_normalizer` est
    présent, mais mesuré sur un en-tête court il lit du `cp1252` comme du
    `big5` : deviner l'encodage est moins fiable que l'essayer. L'ordre
    compte — `utf-8` d'abord, car un fichier UTF-8 se décoderait sans erreur
    en `cp1252`, en produisant des accents faux.

    ⚠️ ET `latin-1` NE PEUT PAS ÉCHOUER : tout octet y est valide. C'est un
    dernier recours, et il se DIT comme tel.
    """
    for encodage in ('utf-8-sig', 'utf-8', 'cp1252'):
        try:
            sep, saut = _reperer_structure(chemin, encodage)
            return (pd.read_csv(chemin, sep=sep, encoding=encodage,
                                skiprows=saut), encodage, sep, saut)
        except UnicodeDecodeError:
            continue
    dernier = ('latin-1 (dernier recours — aucun octet n\'y est invalide, '
               'vérifiez les accents)')
    sep, saut = _reperer_structure(chemin, 'latin-1')
    return (pd.read_csv(chemin, sep=sep, encoding='latin-1', skiprows=saut),
            dernier, sep, saut)


def _reperer_structure(chemin: Path, encodage: str) -> tuple[str, int]:
    """(séparateur, lignes à sauter) — résolus ENSEMBLE, et c'est le point.

    ⚠️ LES DEUX QUESTIONS N'EN FONT QU'UNE. Mesuré : sur un fichier dont les
    en-têtes sont précédés d'un titre, le renifleur de `csv` rend « , » là où
    le fichier est en « ; » — le titre, sans séparateur, l'égare. Et sans le
    bon séparateur, aucune ligne ne se découpe en champs reconnaissables.
    Chercher l'un sans l'autre échoue donc dans les deux sens.

    On essaie chaque séparateur sur chaque ligne de tête, et on retient le
    couple qui reconnaît le PLUS de champs. À égalité, l'ordre de préférence
    tranche — « ; » d'abord, l'usage français.

    ⚠️ ET CE REPÉRAGE PRÉCÈDE L'ANALYSE. pandas fixe le nombre de colonnes sur
    la PREMIÈRE ligne : un titre isolé réduit le tableau à une colonne et
    écrase l'en-tête véritable, irrécupérablement. On lit donc le texte brut
    avant de le confier à pandas.
    """
    with open(chemin, 'r', encoding=encodage, newline='') as f:
        lignes = [f.readline() for _ in range(LIGNES_SONDEES_POUR_ENTETE)]
    meilleur = (0, 0, ';')            # (reconnus, -rang, separateur)
    for sep in SEPARATEURS:
        for i, ligne in enumerate(lignes):
            if not ligne.strip():
                continue
            n = _reconnues(ligne.rstrip('\r\n').split(sep))
            if n > meilleur[0]:
                meilleur = (n, i, sep)
    if meilleur[0] == 0:
        # Aucun champ reconnu nulle part : on s'en remet au renifleur, et le
        # diagnostic dira que rien n'a été reconnu.
        return _detecter_separateur(chemin), 0
    return meilleur[2], meilleur[1]


def lire(chemin, *, onglet: str | None = None,
         correspondances: dict[str, str] | None = None
         ) -> tuple[pd.DataFrame, RapportInventaire]:
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
    brut, decale = _recadrer_sur_l_entete(brut)
    if decale:
        detail += (f", en-tête à la ligne {decale + 1} — les {decale} "
                   f"première(s) ligne(s) sont un titre, pas des données")

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

    liens: list[Correspondance] = []
    ignorees: list[str] = []
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

    par_champ = {c.champ: c.colonne for c in liens}
    brut, totaux = _ecarter_les_totaux(
        brut, par_champ.get('portefeuille', ''),
        par_champ.get('date_emission'))

    _refuser_si_bloquant_absent(liens, brut, chemin)

    canonique = brut.rename(
        columns={c.colonne: c.champ for c in liens})[
            [c.champ for c in liens]]
    presents = {c.champ for c in liens}

    return canonique, RapportInventaire(
        lignes_ecartees=totaux,
        conteneur=conteneur,
        detail_conteneur=detail,
        nb_lignes=len(brut),
        nb_colonnes=len(brut.columns),
        correspondances=tuple(liens),
        colonnes_ignorees=tuple(ignorees),
        granularite=('ensemble pré-agrégé (§17)' if 'nb_contrats' in presents
                     else 'contrat par contrat'),
        capacites=capacites(presents),
        hors_portee=exigences_hors_portee(presents),
    )


def _reconnues(noms) -> int:
    """Combien de ces noms sont des champs connus."""
    return sum(1 for n in noms if _reconnaitre(n)[0] is not None)


def _recadrer_sur_l_entete(brut: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """(tableau recadré, nombre de lignes écartées au-dessus de l'en-tête).

    ⚠️ UN EXPORT EXCEL PORTE SOUVENT UN TITRE AU-DESSUS DE SES EN-TÊTES.
    pandas prend alors le titre pour l'en-tête, et le lecteur refusait pour
    « aucune date d'émission » — un message vrai mais trompeur, qui envoyait
    le client chercher une colonne qu'il avait pourtant fournie.

    ⚠️ CETTE VOIE SERT LES CLASSEURS EXCEL. Pour un CSV, le repérage se fait
    AVANT l'analyse (`_ligne_d_entete`) : pandas y fixe le nombre de colonnes
    sur la première ligne, et un titre isolé écrase l'en-tête réel de façon
    irrécupérable. Deux mécanismes, parce que les deux conteneurs cassent
    différemment.

    On ne recadre que si une ligne suivante reconnaît STRICTEMENT PLUS de
    champs que l'en-tête courant : sans ce gain mesuré, on ne touche à rien.
    """
    depart = _reconnues(brut.columns)
    meilleur, gain = 0, depart
    for i in range(min(LIGNES_SONDEES_POUR_ENTETE, len(brut))):
        n = _reconnues(brut.iloc[i].tolist())
        if n > gain:
            meilleur, gain = i + 1, n
    if not meilleur:
        return brut, 0
    entete = [str(x) for x in brut.iloc[meilleur - 1].tolist()]
    recadre = brut.iloc[meilleur:].reset_index(drop=True)
    recadre.columns = entete
    return recadre, meilleur


def _ecarter_les_totaux(df: pd.DataFrame, cible_portefeuille: str,
                        cible_emission: str | None
                        ) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Retire les lignes de total, et rend leur libellé pour le diagnostic.

    ⚠️ DEUX SIGNAUX EXIGÉS, PAS UN. Le libellé doit évoquer un total ET la
    date d'émission doit manquer : un contrat réel porte une date. Exiger les
    deux rend quasi impossible d'écarter un vrai contrat dont le portefeuille
    s'appellerait « TOTAL ».
    """
    if cible_portefeuille not in df.columns:
        return df, ()
    libelles = df[cible_portefeuille].astype(str).str.strip().str.lower()
    suspect = libelles.apply(lambda v: any(m in v for m in MOTS_DE_TOTAL))
    if cible_emission in df.columns:
        vide = df[cible_emission].isna() | (
            df[cible_emission].astype(str).str.strip() == '')
        suspect = suspect & vide
    if not suspect.any():
        return df, ()
    ecartes = tuple(sorted({str(v) for v in
                            df.loc[suspect, cible_portefeuille]}))
    return df.loc[~suspect].reset_index(drop=True), ecartes


def _refuser_si_concurrentes(liens: list[Correspondance]) -> None:
    """Deux colonnes pour un même champ : le client tranche, pas nous."""
    par_champ: dict[str, list[str]] = {}
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


def _refuser_si_bloquant_absent(liens: list[Correspondance],
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

def _ordre_paragraphe(exigence: str) -> tuple[int, int, str]:
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
    lignes: list[str] = []
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

    if rapport.lignes_ecartees:
        a("")
        a(f"LIGNES ÉCARTÉES ({len(rapport.lignes_ecartees)}) — reconnues "
          f"comme des totaux, pas des contrats")
        a(f"  {', '.join(rapport.lignes_ecartees)}")
        a("  (libellé évoquant un total ET date d'émission absente)")

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
        par_champ: dict[str, list[str]] = {}
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
