"""Controles positifs -- `socle` : quatre des cinq derniers constats.

═══ ⛔ `C2` -- UN MOTEUR DE 430 LIGNES SANS APPELANT DE PRODUCTION ═══

Releve par AST le 01/09/2026 : `preparer_fichier_client`, la porte d'entree du
moteur de mapping, a **0 appelant de production**. Ce n'est PAS du code mort :
la couche est concue pour etre appelee par CELUI QUI APPELLE le pipeline,
avant lui, et sa jonction est `pipeline_agents(rapport_mapping=...)` -- dont le
rapport voyage jusqu'aux trois livrables via `synthese_mapping`. **Aucun code
de ce depot ne joue ce role.**

⚠️⚠️ ET IL EXISTE UN SECOND MOTEUR, DANS A1. `_appliquer_mapping_client` fait
le meme metier avec un autre format (`{client_id}_mapping.json`), et A1
n'importe PAS `core.mapping_client`. *Deux moteurs pour un seul geste, et rien
ne le disait.* Les unifier deplacerait un comportement : c'est NOMME, pas
tranche.

═══ ⛔ `C4` -- UNE PROMESSE QUE LE FICHIER AVAIT RETIREE ═══

`proposer_mapping` promettait << Temperature 0 pour la reproductibilite (meme
convention que le reste du projet) >>. Mesure :

    _TEMPERATURE_DEFAUT (l.51) = None      defaut du parametre = None

La temperature a ete retiree le 07/08/2026 parce que **le modele la REFUSE**
(400, << deprecated for this model >>). *Quand un comportement change, le texte
qui l'accompagne se relit.*

═══ LES DEUX AUTRES ═══

| constat | ce qui etait annonce | ce qui est |
|---|---|---|
| `C3` | deux symboles dans `__all__` | 0 consommateur externe, et aucun motif ecrit |
| `C5` | `n_lignes_exemple: int = 5` | `del` des la premiere ligne, docstring muette |

⚠️ `C3` NE SE FERME PAS EN RETIRANT LES SYMBOLES. `DERIVATIONS` est LA TABLE
que `sources_brutes` interroge ; `CibleSeverite` est LE TYPE DE RETOUR de
`construire_cible_severite`, que ses trois appelants utilisent sans jamais
l'ecrire. *Un symbole exporte sans consommateur n'est pas un defaut ; ne pas
dire lequel des deux il est, si.*

⚠️ `C5` A UN HOMONYME VIVANT. Le meme parametre, dans
`nv_triangle_mapping_llm`, est REELLEMENT lu (deux fonctions, aucun `del`).
Deux parametres du meme nom, un mort et un vif -- raison de plus pour dire
lequel est lequel.

⚠️ `socle/C1` n'etait PAS dans ce lot -- il attendait son arbitrage. Selasse a
tranche le 01/09/2026 : le seuil porte sur CHAQUE SINISTRE. Il est ferme par
`test_socle_c1_assiette_ecretement`, qui porte les controles `SC-1` a `SC-9`.
"""

from __future__ import annotations

import ast
import glob
import os
import pathlib
import unittest

import core.derivations as _dmod
import core.mapping_client as _mcmod
import core.mapping_llm as _mlmod
import core.severite as _smod

_RACINE = pathlib.Path(_mcmod.__file__).parents[1]


def _fichiers_python(exclure_tests=True):
    for chemin in glob.glob(str(_RACINE / '**' / '*.py'), recursive=True):
        if 'audit_2026_08' in chemin or '.venv' in chemin:
            continue
        if exclure_tests and os.path.basename(chemin).startswith('test_'):
            continue
        yield chemin


def _appels(nom, hors=()):
    """Tous les appels a `nom`, hors des fichiers dont le nom est dans `hors`."""
    sites = []
    for chemin in _fichiers_python():
        if os.path.basename(chemin) in hors:
            continue
        try:
            arbre = ast.parse(pathlib.Path(chemin).read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for n in ast.walk(arbre):
            if isinstance(n, ast.Call):
                x = getattr(n.func, 'attr', None) or getattr(n.func, 'id', None)
                if x == nom:
                    sites.append(f'{os.path.basename(chemin)}:{n.lineno}')
    return sites


def _mentions(nom, hors=()):
    """Toute mention du SYMBOLE (Name ou Attribute), hors fichiers exclus."""
    sites = []
    for chemin in _fichiers_python():
        if os.path.basename(chemin) in hors:
            continue
        try:
            arbre = ast.parse(pathlib.Path(chemin).read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for n in ast.walk(arbre):
            if ((isinstance(n, ast.Name) and n.id == nom)
                    or (isinstance(n, ast.Attribute) and n.attr == nom)
                    or (isinstance(n, ast.alias) and n.name == nom)):
                sites.append(f'{os.path.basename(chemin)}:{getattr(n, "lineno", 0)}')
    return sites


class TestSocleQuatreConstats(unittest.TestCase):
    """Quatre constats de la zone `socle` -- `C1` reste ouvert, et c'est dit."""

    # ── `socle/C2` — la porte sans appelant, et le second moteur ────────────

    def test_SO_1_LE_TEST_QUI_FERME_la_porte_sans_appelant_le_DIT(self):
        """`socle/C2` : les DEUX sens -- la phrase se mesure comme un chiffre."""
        sites = _appels('preparer_fichier_client',
                        hors=('mapping_client.py',))
        doc = _mcmod.preparer_fichier_client.__doc__ or ''
        if sites:
            self.assertNotIn(
                "AUCUN APPELANT DE PRODUCTION", doc,
                f"la docstring dit << aucun appelant de production >> alors "
                f"qu'il y en a : {sites}. *Une phrase de portee se mesure "
                f"comme un chiffre.*")
        else:
            self.assertIn(
                "AUCUN APPELANT DE PRODUCTION", doc,
                "la porte d'entree du moteur de mapping n'a aucun appelant "
                "de production et la docstring ne le dit pas")
            self.assertIn(
                'pipeline_agents', doc,
                "la docstring ne nomme pas la jonction prevue : le lecteur "
                "ne peut pas savoir OU cette couche devrait etre appelee")

    def test_SO_2_le_SECOND_moteur_de_mapping_est_nomme(self):
        """`socle/C2` : A1 fait le meme metier, avec un autre format."""
        src_a1 = (_RACINE / 'direction_non_vie' / 'tarification'
                  / 'a1_ingestion' / 'agent.py').read_text(encoding='utf-8')
        importe = any(
            isinstance(n, (ast.Import, ast.ImportFrom))
            and 'mapping_client' in (getattr(n, 'module', '') or '')
            for n in ast.walk(ast.parse(src_a1)))
        doc = _mcmod.preparer_fichier_client.__doc__ or ''
        if importe:
            self.assertNotIn(
                "n'importe PAS ce", doc,
                "A1 importe desormais `core.mapping_client` : la phrase qui "
                "annonce deux moteurs separes est devenue fausse")
        else:
            self.assertIn(
                '_appliquer_mapping_client', doc,
                "le second moteur de mapping, dans A1, n'est nomme nulle "
                "part : deux mecanismes pour un seul geste, en silence")
            self.assertIn('def _appliquer_mapping_client', src_a1)

    # ── `socle/C3` — exportes, sans consommateur, et desormais DITS ────────

    def test_SO_3_LE_TEST_QUI_FERME_les_deux_exports_portent_leur_motif(self):
        """`socle/C3` : dans les deux sens, pour chacun des deux symboles."""
        cas = [
            ('DERIVATIONS', _dmod, 'derivations.py'),
            ('CibleSeverite', _smod, 'severite.py'),
        ]
        for nom, module, fichier in cas:
            source = pathlib.Path(module.__file__).read_text(encoding='utf-8')
            self.assertIn(
                nom, getattr(module, '__all__', ()),
                f"'{nom}' a quitte le `__all__` de {fichier} : le retirer "
                f"casserait un lecteur en silence")
            externes = _mentions(nom, hors=(fichier,))
            entete = source.split('__all__')[0]
            if externes:
                self.assertNotIn(
                    'SANS CONSOMMATEUR', entete.upper(),
                    f"{fichier} dit '{nom}' sans consommateur externe, il y "
                    f"en a : {externes}")
            else:
                self.assertIn(
                    'socle/C3', entete,
                    f"{fichier} exporte '{nom}' sans aucun consommateur "
                    f"externe et n'en donne pas la raison")

    # ── `socle/C4` — une promesse retiree du code ──────────────────────────

    def test_SO_4_LE_TEST_QUI_FERME_plus_aucune_temperature_promise(self):
        """`socle/C4` : le TEXTE et le FAIT, tous les deux."""
        self.assertIsNone(
            _mlmod._TEMPERATURE_DEFAUT,
            'le defaut de temperature est revenu : le modele la REFUSE (400)')
        doc = _mlmod.proposer_mapping.__doc__ or ''
        annonce = doc.split('⚠️')[0]
        self.assertNotIn(
            'Température 0', annonce,
            f"la docstring promet encore une temperature que le fichier a "
            f"retiree : {annonce}")
        # Le correctif CITE la promesse retiree : la citation est legitime,
        # l'annonce ne l'est pas. Meme distinction que `conformite/C9`.
        self.assertIn('REFUSE', doc)

    # ── `socle/C5` — un parametre public sans effet ────────────────────────

    def test_SO_5_LE_TEST_QUI_FERME_le_parametre_sans_effet_est_DIT(self):
        """`socle/C5` : le FAIT est deja epingle ailleurs, le TEXTE ne l'etait pas.

        ⚠️ La preuve par execution appartient a `test_apercu_caviarde` (T4 :
        `n_lignes_exemple` dans {1, 5, 50, 5000} -> apercu identique). Elle
        n'est PAS redite ici. Ce controle porte sur ce que la docstring
        PUBLIQUE dit -- c'est-a-dire sur ce que lit l'appelant.
        """
        doc = _mlmod.proposer_mapping.__doc__ or ''
        self.assertIn('n_lignes_exemple', doc,
                      "le parametre public n'est pas mentionne du tout")
        self.assertIn(
            'SANS EFFET', doc.upper(),
            "la docstring ne dit pas que `n_lignes_exemple` est sans effet : "
            "un appelant peut croire qu'il regle la taille de l'apercu")
        # Le FAIT, verifie ici sans dupliquer T4 : la fonction qui le recoit
        # le supprime des sa premiere instruction.
        source = pathlib.Path(_mlmod.__file__).read_text(encoding='utf-8')
        supprime = any(
            isinstance(n, ast.Delete)
            and any(getattr(c, 'id', None) == 'n_lignes_exemple'
                    for c in n.targets)
            for n in ast.walk(ast.parse(source)))
        self.assertTrue(
            supprime,
            "`n_lignes_exemple` n'est plus supprime : s'il sert desormais, "
            "c'est la docstring qui doit changer, pas ce controle")

    def test_SO_6_l_HOMONYME_vivant_est_nomme(self):
        """`socle/C5` : deux parametres du meme nom, un mort et un vif."""
        src = (_RACINE / 'direction_non_vie' / 'services'
               / 'nv_triangle_mapping_llm.py').read_text(encoding='utf-8')
        arbre = ast.parse(src)
        vivants = []
        for n in ast.walk(arbre):
            if (isinstance(n, ast.FunctionDef)
                    and 'n_lignes_exemple' in [a.arg for a in n.args.args]):
                lu = any(isinstance(x, ast.Name)
                         and x.id == 'n_lignes_exemple'
                         and isinstance(x.ctx, ast.Load)
                         for x in ast.walk(n))
                if lu:
                    vivants.append(n.name)
        doc = _mlmod.proposer_mapping.__doc__ or ''
        if vivants:
            self.assertIn(
                'nv_triangle_mapping_llm', doc,
                f"l'homonyme VIVANT ({vivants}) n'est nomme nulle part : "
                f"*un releve par symbole ne voit pas l'homonyme*")
        else:
            self.assertNotIn(
                'est VIVANT', doc,
                "la docstring annonce un homonyme vivant qui ne l'est plus")


if __name__ == '__main__':
    unittest.main(verbosity=2)
