# ActuarIA — core
# Modules transversaux communs à tous les agents
#
# ══════════════════════════════════════════════════════════════════════════
# ⚠️⚠️ CONSTAT `socle/C6` — CE FICHIER FAISAIT PAYER À 49 IMPORTS UNE SURFACE
# QUE PERSONNE N'UTILISE.
#
# Il ré-exportait vingt symboles par des `from .x import y` exécutés À
# L'IMPORT DU PAQUET. Or importer n'importe quel sous-module (`from core
# import arrete`) exécute ce fichier. Mesuré le 03/09/2026 :
#
#     from core import arrete   ->  6 modules charges, 4 429 lignes
#     `core.arrete` lui-meme    ->                       233 lignes
#
# ⚠️⚠️ ET LA SURFACE AINSI PAYÉE A **ZÉRO CONSOMMATEUR**. Relevé par AST sur
# tout le dépôt : **49 imports `from core import X`, et les 49 importent un
# SOUS-MODULE** (`arrete`, `frontiere_llm`, `traitement_ia`, `format_fr`…).
# Aucun n'importe un symbole d'`__all__` ; chaque appelant passe par le
# sous-module direct (`from core.plan_tarifaire import PlanTarifaire`).
#
#   *Une porte que personne ne franchit et que tout le monde paye.*
#
# ⚠️ LE RÉ-EXPORT N'EST PAS SUPPRIMÉ, IL EST RENDU PARESSEUX (PEP 562). Le
# dépôt est PUBLIC : `from core import PlanTarifaire` peut vivre dans un
# carnet que je ne vois pas. *Retirer une API publique parce qu'aucun
# appelant INTERNE ne l'utilise, c'est mesurer sur la mauvaise assiette.*
# Le contrat est donc conservé à l'identique, et le coût disparaît.
#
# ⚠️ ET `__all__` DIVERGEAIT DE CE QUI ÉTAIT RÉELLEMENT RÉ-EXPORTÉ :
# `construire_lx` et `insee_qx_prospectif` étaient importés sans y figurer.
# Prouvé par exécution : joignables par `from core import X`, invisibles à
# `from core import *`. *Une surface déclarée qui ment sur la surface
# réelle, dans le fichier qui SERT à déclarer la surface.*
#
# ⚠️ `audit_trail` RETIRÉ (C5d) : 333 lignes qu'aucun appelant n'instanciait,
# portant 76 déclarations juridiques (19 agents × traitement / base légale /
# données / durée) que rien ne produisait. Les registres art. 30 vivants sont
# ceux d'A13 et de SP audit. Réparer cette couche lui aurait donné une
# apparence de justesse qui aurait invité à la brancher.
# ══════════════════════════════════════════════════════════════════════════

#: ⚠️⚠️ LA TABLE EST LA SOURCE UNIQUE DU RÉ-EXPORT. `__all__` la reprend en
#: LITTÉRAL — un `__all__` calculé (`sorted(_REEXPORTS)`) est invisible à
#: l'outillage statique, et `PLE0605` a raison de le refuser. La divergence
#: entre les deux, elle, est interdite par une SENTINELLE (`SC6-1`) : c'est
#: le patron du golden d'`EMPREINTE_SCHEMA`, déjà en service.
#: *Ce qui doit rester lisible se déclare ; ce qui doit rester vrai se teste.*
_REEXPORTS = {
    'BaseAgent': 'base_agent',
    # Plan tarifaire — LA SOURCE UNIQUE du contrat A2→A3→conformité
    'PlanTarifaire': 'plan_tarifaire',
    'Facteur': 'plan_tarifaire',
    # Conformité réglementaire — SOURCE UNIQUE pour les trois directions
    'filtrer_genre': 'conformite_reglementaire',
    'filtrer_famille_cible': 'conformite_reglementaire',
    'COLS_GENRE_INTERDITES': 'conformite_reglementaire',
    'COLS_GENRE_STEMS': 'conformite_reglementaire',
    'COLS_FAMILLE_CIBLE': 'conformite_reglementaire',
    'COLS_FAMILLE_CIBLE_STEMS': 'conformite_reglementaire',
    'COLS_FAMILLE_CIBLE_EXCEPTIONS': 'conformite_reglementaire',
    # Tables de mortalité réglementaires
    'QX_TH0002': 'tables_mortalite',
    'QX_TF0002': 'tables_mortalite',
    'QX_INSEE_H': 'tables_mortalite',
    'QX_INSEE_F': 'tables_mortalite',
    'get_qx': 'tables_mortalite',
    'construire_lx': 'tables_mortalite',
    'calculer_annuite_viagere': 'tables_mortalite',
    'calculer_annuite_viagere_prospective': 'tables_mortalite',
    'insee_qx_prospectif': 'tables_mortalite',
    'REFERENCE_REGLEMENTAIRE': 'tables_mortalite',
}

__all__ = [
    'BaseAgent',
    'COLS_FAMILLE_CIBLE',
    'COLS_FAMILLE_CIBLE_EXCEPTIONS',
    'COLS_FAMILLE_CIBLE_STEMS',
    'COLS_GENRE_INTERDITES',
    'COLS_GENRE_STEMS',
    'Facteur',
    'PlanTarifaire',
    'QX_INSEE_F',
    'QX_INSEE_H',
    'QX_TF0002',
    'QX_TH0002',
    'REFERENCE_REGLEMENTAIRE',
    'calculer_annuite_viagere',
    'calculer_annuite_viagere_prospective',
    'construire_lx',
    'filtrer_famille_cible',
    'filtrer_genre',
    'get_qx',
    'insee_qx_prospectif',
]


def __getattr__(nom):
    """Ré-export PARESSEUX — le sous-module n'est chargé qu'à l'usage réel.

    ⚠️ PEP 562. Le contrat public est inchangé (`from core import
    PlanTarifaire` fonctionne), mais un appelant qui ne veut que
    `core.arrete` ne paye plus les 4 196 lignes qu'il n'utilise pas.
    """
    module = _REEXPORTS.get(nom)
    if module is None:
        raise AttributeError(f"module 'core' has no attribute {nom!r}")
    import importlib
    return getattr(importlib.import_module(f'.{module}', __name__), nom)


def __dir__():
    """⚠️ Sans elle, la complétion et `dir(core)` cesseraient de voir les
    ré-exports : *un mécanisme paresseux ne doit pas devenir invisible.*"""
    return sorted(set(__all__) | set(globals()))
