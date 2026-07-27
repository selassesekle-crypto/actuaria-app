# =============================================================================
#  ActuarIA — Bloc II, module 5 : SÉPARATION ATTRITIONNEL / GRANDS SINISTRES
#  nv_triangle_separation.py
# =============================================================================
#
#  RESPONSABILITÉ — répartir les lignes d'une table de sinistres en DEUX groupes
#  selon un seuil (LLT, Large Loss Threshold) fourni par l'actuaire, pour que les
#  méthodes N3 tournent sur un triangle attritionnel statistiquement plus propre.
#
#  ⚠️ ORDRE DE FLUX ≠ ORDRE DE NUMÉROTAGE. Le numéro 5 est une étiquette d'ordre
#  de CONSTRUCTION. Dans le FLUX DE DONNÉES, ce module s'exécute AVANT le module 4
#  (construction) :
#
#      cas LONG    : 1 lire → 2/3 mapper → 5 SÉPARER → 4 construire (×2)
#      cas MATRICE : 1 lire → 4 construire     · module 5 ne peut qu'AVERTIR
#
#  C'est arithmétiquement inévitable : une cellule de triangle est une SOMME, et
#  on ne dé-somme pas — l'identité des sinistres y est perdue. La variante
#  « C_attrit = C_total − C_grands » n'y échappe pas : construire C_grands exige
#  déjà de savoir quels sinistres sont grands, donc les données individuelles.
#  La façade (module 7) doit appeler dans l'ordre du FLUX, pas des numéros.
#
#  CE MODULE NE FAIT PAS :
#    · construire des triangles   → module 4, SEUL agrégateur, appelé deux fois
#    · calculer une réserve       → JAMAIS. Il IDENTIFIE et ISOLE, il ne chiffre
#      pas. La réserve des grands sinistres est un jugement d'expert dossier par
#      dossier, fourni par l'actuaire via `reserve_grands_sinistres` (agent.py,
#      injection scalaire à N4). Ce module lui fournit LA LISTE des dossiers à
#      évaluer — il ne remplit jamais ce champ à sa place.
#
#  SUR QUELLE MESURE PORTE LE SEUIL — question actuarielle, pas technique :
#  classer sur le seul PAYÉ À DATE sous-classe les sinistres JEUNES (un dossier
#  provisionné 5 M€ mais payé 100 k€ serait jugé attritionnel, alors que c'est
#  précisément celui qu'il fallait isoler). D'où la hiérarchie, avec alerte en
#  dégradant : montant_charge > montant_paye + evaluation_courante > montant_paye.
#
#  Agnostique de l'interface : aucun import Streamlit ni agent. Testable seul.
# =============================================================================

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger('actuaria.nv.separation')

__all__ = [
    'BASES_CLASSEMENT', 'SeparationLLT', 'SeparationImpossible',
    'separer_par_seuil', 'avertir_si_agregat',
]

# Bases de classement, de la meilleure à la plus dégradée.
BASES_CLASSEMENT: Tuple[str, ...] = ('charge', 'paye_plus_provision', 'paye')

# Nombre de dossiers en deçà duquel le triangle des grands sinistres est qualifié
# de support de DIAGNOSTIC. Ce seuil ne CONDITIONNE RIEN : les deux triangles sont
# TOUJOURS construits (sinon on perdrait la preuve de cohérence attritionnel +
# grands = total, et le diagnostic, précisément quand ils servent le plus). Il ne
# règle que le libellé d'un avertissement.
#  ⚠️ À NE PAS CONFONDRE avec les seuils 20/50 de _recommander_methode_grands
#  (builder) : ceux-là choisissent une MÉTHODE de provisionnement, décision qui
#  n'appartient pas à ce module.
SEUIL_VOLUME_DIAGNOSTIC: int = 20

_MSG_AGREGAT = (
    "Séparation impossible sur un triangle DÉJÀ AGRÉGÉ : une cellule est une "
    "somme, l'identité des sinistres y est perdue et aucun seuil ne peut être "
    "appliqué. Fournissez le fichier de sinistres individuels (une ligne par "
    "sinistre/période), ou renoncez à la séparation.")


class SeparationImpossible(ValueError):
    """La séparation ne peut pas être faite PROPREMENT : données déjà agrégées,
    seuil invalide, ou aucune mesure exploitable. Jamais un résultat faux en
    silence, jamais une séparation partielle non signalée."""


# =============================================================================
#  RÉSULTAT
# =============================================================================
@dataclass(frozen=True)
class SeparationLLT:
    """Deux tables LONGUES + la liste des dossiers à évaluer.

    Volontairement AUCUN champ de réserve : ce module identifie et isole, il ne
    chiffre pas (verrou de périmètre, testé explicitement).
    """
    attritionnel: pd.DataFrame            # → module 4
    grands:       pd.DataFrame            # → module 4 (indicatif) ; PAS une réserve
    sinistres_grands: pd.DataFrame        # id · cout_retenu · annee : LE livrable actuaire
    seuil_llt:    float
    n_grands:            int
    n_attritionnels:     int
    montant_grands:       float
    montant_attritionnel: float
    base_classement_utilisee: str         # 'charge' | 'paye_plus_provision' | 'paye'
    classement_par_sinistre:  bool        # False = par ligne (dégradé, alerté)
    avertissement_volume: str = ''        # qualifie l'USAGE du triangle grands
    rapport: Dict[str, Any] = field(default_factory=dict)

    def synthese(self) -> Dict[str, Any]:
        """Vue json-sérialisable (types natifs) — livrables / audit."""
        return {
            'seuil_llt':            float(self.seuil_llt),
            'n_grands':             int(self.n_grands),
            'n_attritionnels':      int(self.n_attritionnels),
            'montant_grands':       float(self.montant_grands),
            'montant_attritionnel': float(self.montant_attritionnel),
            'base_classement_utilisee': self.base_classement_utilisee,
            'classement_par_sinistre':  bool(self.classement_par_sinistre),
            'avertissement_volume':     self.avertissement_volume,
            'sinistres_grands': self.sinistres_grands.to_dict(orient='records'),
            'alertes': list(self.rapport.get('alertes', [])),
            'infos':   list(self.rapport.get('infos', [])),
        }


# =============================================================================
#  GARDE-FOU
# =============================================================================
def avertir_si_agregat(source) -> Optional[str]:
    """Message d'avertissement si `source` est un triangle déjà agrégé, sinon None.

    Exposé SÉPARÉMENT de separer_par_seuil pour que la façade puisse
    avertir-et-poursuivre (construire ce qui est possible, signaler le reste)
    plutôt que faire tomber tout le run — même politique que les primes
    manquantes au module 4.
    """
    if isinstance(source, pd.DataFrame) and 'annee_survenance' in source.columns:
        return None                      # table longue : séparation possible
    return _MSG_AGREGAT


# =============================================================================
#  CLASSEMENT
# =============================================================================
def _choisir_base(df: pd.DataFrame, demandee: str,
                  rapport: Dict) -> Tuple[pd.Series, str]:
    """Coût retenu par LIGNE + nom de la base utilisée.

    Hiérarchie (meilleure → dégradée), avec alerte quand on dégrade :
      · 'charge'              : montant_charge — coût à terminaison, le bon critère
      · 'paye_plus_provision' : montant_paye + evaluation_courante — équivalent
      · 'paye'               : montant_paye seul — SOUS-CLASSE les sinistres jeunes
    """
    def num(col: str) -> pd.Series:
        return pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    a_charge = 'montant_charge' in df.columns
    a_paye   = 'montant_paye' in df.columns
    a_prov   = 'evaluation_courante' in df.columns

    if demandee != 'auto' and demandee not in BASES_CLASSEMENT:
        raise SeparationImpossible(
            f"base_classement '{demandee}' inconnue (attendu 'auto' ou "
            f"{list(BASES_CLASSEMENT)}).")

    if demandee in ('auto', 'charge') and a_charge:
        return num('montant_charge'), 'charge'
    if demandee in ('auto', 'paye_plus_provision') and a_paye and a_prov:
        rapport['infos'].append(
            "Classement LLT sur payé + provision (équivalent à la charge).")
        return num('montant_paye') + num('evaluation_courante'), 'paye_plus_provision'
    if demandee in ('auto', 'paye') and a_paye:
        rapport['alertes'].append(
            "⚠️ Classement LLT sur le PAYÉ À DATE seul (ni montant_charge ni "
            "evaluation_courante) : les sinistres JEUNES seront SOUS-CLASSÉS — un "
            "dossier lourdement provisionné mais peu payé sera jugé attritionnel. "
            "Fournir la charge ou la provision pour un classement fiable.")
        return num('montant_paye'), 'paye'

    raise SeparationImpossible(
        f"base de classement '{demandee}' indisponible : aucune mesure exploitable "
        f"(montant_charge / montant_paye / evaluation_courante) dans le tableau.")


def _cout_par_sinistre(df: pd.DataFrame, cout_ligne: pd.Series,
                       rapport: Dict) -> Tuple[pd.Series, bool]:
    """Coût de référence du seuil, PAR SINISTRE si possible.

    Le seuil porte sur le coût TOTAL d'un dossier : sans identifiant, un sinistre
    réglé en plusieurs versements serait jugé ligne à ligne et passerait sous le
    seuil (un sinistre de 5 M€ payé en 10 fois 500 k€ n'atteint jamais 1 M€).
    Retourne (coût aligné sur les lignes, classement_par_sinistre).
    """
    if 'sinistre_id' not in df.columns:
        rapport['alertes'].append(
            "⚠️ Colonne 'sinistre_id' absente — classement LLT ligne à ligne, "
            "DÉGRADÉ : un sinistre réglé en plusieurs versements ne sera pas "
            "reconnu comme grand même si son coût total dépasse le seuil.")
        return cout_ligne, False

    par_sinistre = cout_ligne.groupby(df['sinistre_id']).transform('sum')
    rapport['infos'].append(
        f"Classement LLT par sinistre : {df['sinistre_id'].nunique()} dossier(s) "
        f"distinct(s) regroupé(s).")
    return par_sinistre, True


def _liste_grands(df: pd.DataFrame, cout_reference: pd.Series, est_grand: pd.Series,
                  par_sinistre: bool) -> pd.DataFrame:
    """Liste des dossiers dépassant le seuil — LE livrable pour l'actuaire.

    C'est à partir de cette liste que l'actuaire produit son jugement dossier par
    dossier, qui alimentera `reserve_grands_sinistres`. Ce module ne la chiffre
    jamais lui-même.
    """
    if not est_grand.any():
        return pd.DataFrame(columns=['sinistre_id', 'cout_retenu', 'annee_survenance'])

    extrait = pd.DataFrame({
        'sinistre_id': (df['sinistre_id'] if 'sinistre_id' in df.columns
                        else pd.Series(df.index, index=df.index)),
        'cout_retenu': cout_reference,
        'annee_survenance': pd.to_numeric(df['annee_survenance'], errors='coerce'),
    })[est_grand]

    if par_sinistre:
        # une ligne par dossier : le coût est déjà le total du sinistre
        extrait = (extrait.groupby('sinistre_id', as_index=False)
                   .agg(cout_retenu=('cout_retenu', 'first'),
                        annee_survenance=('annee_survenance', 'min')))
    return extrait.sort_values('cout_retenu', ascending=False).reset_index(drop=True)


# =============================================================================
#  API PUBLIQUE
# =============================================================================
def separer_par_seuil(
    df,
    seuil_llt: float,
    *,
    base_classement: str = 'auto',
) -> SeparationLLT:
    """Sépare une table LONGUE de sinistres en attritionnel / grands sinistres.

    Rend DEUX TABLES LONGUES (pas des triangles) : le module 4 reste le seul
    agrégateur et sera appelé une fois par groupe. Aucune logique de construction
    n'est dupliquée ici.

    `seuil_llt` est FOURNI par l'actuaire — jamais calculé par le système : c'est
    un jugement d'expert. Le classement porte sur le coût TOTAL d'un sinistre
    (regroupé par `sinistre_id` si disponible), évalué selon la hiérarchie
    charge > payé+provision > payé (cf. _choisir_base).

    LÈVE SeparationImpossible si la source est un triangle déjà agrégé, si le
    seuil est invalide, ou si aucune mesure n'est exploitable. Pour avertir sans
    lever (façade), utiliser avertir_si_agregat().
    """
    message = avertir_si_agregat(df)
    if message is not None:
        raise SeparationImpossible(message)
    if not np.isfinite(seuil_llt) or seuil_llt <= 0:
        raise SeparationImpossible(
            f"seuil LLT invalide ({seuil_llt}) : attendu un montant strictement "
            f"positif, fourni par l'actuaire.")

    rapport: Dict[str, Any] = {'alertes': [], 'infos': []}
    cout_ligne, base = _choisir_base(df, base_classement, rapport)
    cout_reference, par_sinistre = _cout_par_sinistre(df, cout_ligne, rapport)

    est_grand = cout_reference >= float(seuil_llt)      # convention : seuil INCLUS
    attritionnel = df[~est_grand].copy()
    grands       = df[est_grand].copy()

    rapport['infos'].append(
        f"Séparation LLT = {seuil_llt:,.0f} (base '{base}') : "
        f"{len(grands)} ligne(s) grands sinistres, {len(attritionnel)} attritionnelles.")
    if len(grands) == 0:
        rapport['alertes'].append(
            f"⚠️ Aucun sinistre n'atteint le seuil de {seuil_llt:,.0f} — séparation "
            f"sans effet. Vérifier que le seuil correspond à l'ordre de grandeur "
            f"du portefeuille.")
    elif len(attritionnel) == 0:
        rapport['alertes'].append(
            f"⚠️ TOUS les sinistres dépassent le seuil de {seuil_llt:,.0f} — le "
            f"triangle attritionnel serait vide. Seuil probablement trop bas.")

    # Avertissement de VOLUME : qualifie l'usage du triangle des grands sinistres
    # sans jamais empêcher sa construction (cf. SEUIL_VOLUME_DIAGNOSTIC).
    liste = _liste_grands(df, cout_reference, est_grand, par_sinistre)
    n_dossiers = len(liste)
    if n_dossiers == 0:
        avertissement = ("Aucun dossier au-dessus du seuil : le triangle des grands "
                         "sinistres est vide (zéros) — il ne sert qu'à vérifier que "
                         "l'attritionnel reprend bien la totalité du portefeuille.")
    elif n_dossiers < SEUIL_VOLUME_DIAGNOSTIC:
        avertissement = (
            f"{n_dossiers} dossier(s) au-dessus du seuil : le triangle des grands "
            f"sinistres est un support de DIAGNOSTIC (cadence observée, part déjà "
            f"payée), PAS une base statistique fiable — trop peu de dossiers, et des "
            f"développements par nature hétérogènes. La provision de ces dossiers "
            f"relève du jugement d'expert, dossier par dossier.")
    else:
        avertissement = (
            f"{n_dossiers} dossiers au-dessus du seuil. Un volume suffisant ne garantit "
            f"pas à lui seul l'homogénéité : vérifier la densité en fin de "
            f"développement avant tout traitement statistique de ce triangle.")
    rapport['infos'].append(avertissement)

    return SeparationLLT(
        attritionnel=attritionnel, grands=grands,
        sinistres_grands=liste, avertissement_volume=avertissement,
        seuil_llt=float(seuil_llt),
        n_grands=int(len(grands)), n_attritionnels=int(len(attritionnel)),
        montant_grands=float(cout_ligne[est_grand].sum()),
        montant_attritionnel=float(cout_ligne[~est_grand].sum()),
        base_classement_utilisee=base, classement_par_sinistre=par_sinistre,
        rapport=rapport)
