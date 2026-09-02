"""⚠️⚠️ LES DEUX MOITIES DU BADGE NE NORMALISAIENT PAS PAREIL.

Constat `services/C14`, ouvert le 03/09/2026 en auditant `excel_helpers.py` --
l'un des trois modules que la carte declarait << jamais audites >>.

La pastille des deux Excel a deux moities : le FOND (`_statut_fill`) et le
MOT (`_MOT_RAG`). La premiere faisait `.upper()`, la seconde non.

```
  statut='vert'  ->  FOND VERT  +  TEXTE 'vert'   (au lieu de ✓ Conforme)
```

> *La couleur disait << conforme >> et le mot ne le disait pas -- sur la
> pastille que l'actuaire lit en diagonale.*

C'est la famille de `services/C9`, ou le mot le plus fort etait le moins
alarmant. Ici ce n'est pas le mot qui est faux : c'est qu'il DISPARAIT au
profit d'une chaine brute, sous une couleur qui, elle, affirme.

⚠️⚠️ LE DEFAUT EST LATENT, ET LE DIRE FAIT PARTIE DU CONSTAT. Releve sur tout
le depot : les valeurs litterales ecrites en `statut_rag` sont toutes en
MAJUSCULES, et aucun des 45 chemins dynamiques mesures ne produit de
minuscule. *Une asymetrie qui ne tire pas aujourd'hui reste une asymetrie :
elle attend un appelant.*
"""
from __future__ import annotations

import ast
import pathlib
import unittest

from direction_non_vie.tarification.services.excel_helpers import (
    AMBRE,
    GRIS,
    ROUGE,
    VERT_H,
    _normaliser_statut,
    _statut_fill,
)

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_HELPERS = (_RACINE / 'direction_non_vie' / 'tarification' / 'services'
            / 'excel_helpers.py')

#: Le mot publie par `_kpi`, relu ici depuis SA SOURCE pour que ce controle ne
#: recopie pas la table qu'il surveille.
_FONDS = {VERT_H: 'VERT', AMBRE: 'AMBRE', ROUGE: 'ROUGE', GRIS: None}


def _mots_rag() -> dict:
    """La table `_MOT_RAG` telle qu'elle est ECRITE dans `_kpi`, par AST.

    ⚠️ *Une citation n'est pas une affirmation* : on lit la table du CODE, on
    ne la recopie pas dans le test. Recopiee, elle passerait meme le jour ou
    la vraie table change.
    """
    arbre = ast.parse(_HELPERS.read_text(encoding='utf-8'))
    for n in ast.walk(arbre):
        if (isinstance(n, ast.Assign) and n.targets
                and getattr(n.targets[0], 'id', '') == '_MOT_RAG'):
            return ast.literal_eval(n.value)
    raise AssertionError('`_MOT_RAG` introuvable : le controle ne surveille '
                         'plus rien')


class TestBadgeDeuxMoities(unittest.TestCase):

    def test_BD_1_LE_CONSTAT_les_deux_moities_s_accordent_sur_la_CASSE(self):
        """⚠️⚠️ LA MESURE QUI A OUVERT LE CONSTAT, DEVENUE CONTROLE.

        ⛔⛔ CE CONTROLE A ETE REFAIT : SA PREMIERE VERSION ETAIT DU DECOR.
        Elle calculait `mots.get(_normaliser_statut(forme))` **elle-meme** --
        elle testait donc sa PROPRE reimplementation, pas `_kpi`. Le plant qui
        remettait le defaut d'origine (`_MOT_RAG.get(statut)` sur le statut
        BRUT) ne la faisait pas tomber.

        > *Un controle qui refait le calcul qu'il surveille ne surveille que
        > lui-meme.*

        Il ecrit desormais dans une VRAIE feuille et relit la cellule que
        l'actuaire verra.
        """
        from openpyxl import Workbook

        from direction_non_vie.tarification.services.excel_helpers import _kpi
        desaccords = []
        for forme in ('VERT', 'vert', 'Vert', ' VERT ', 'AMBRE', 'ambre',
                      'ROUGE', 'rouge'):
            ws = Workbook().active
            _kpi(ws, 1, 'libelle', 'valeur', statut=forme)
            cellule = ws.cell(row=1, column=3)
            fond = _FONDS.get(_statut_fill(forme), '?')
            # ⚠️ Le MOT lu dans la cellule REELLE, jamais recalcule ici.
            reconnu = any(m in str(cellule.value or '')
                          for m in _mots_rag().values())
            if (fond is None) != (not reconnu):
                desaccords.append(
                    f'{forme!r} : fond={fond} cellule={cellule.value!r}')
        self.assertEqual(
            desaccords, [],
            f"le fond et le mot de la pastille se contredisent : "
            f"{desaccords}. Une couleur qui affirme sous un mot qui se tait "
            f"est le defaut de `services/C9`, un cran plus bas")
        print("    BD-1 8 formes de casse, ecrites dans une VRAIE feuille : "
              "fond et cellule toujours d'accord")

    def test_BD_2_second_sens_un_statut_INCONNU_reste_gris_ET_muet(self):
        """⚠️ Sans ce sens, une normalisation trop large ferait passer
        n'importe quoi pour VERT. *Un garde-fou qui accepte tout n'en est
        plus un.*
        """
        mots = _mots_rag()
        for inconnu in ('VERTT', 'V E R T', 'ok', None, '', 'CONFORME'):
            self.assertEqual(
                _statut_fill(inconnu), GRIS,
                f'{inconnu!r} recoit une couleur RAG : la normalisation est '
                f'trop permissive')
            self.assertIsNone(mots.get(_normaliser_statut(inconnu)))
        print("    BD-2 second sens : 6 formes inconnues -> GRIS et aucun mot")

    def test_BD_3_la_normalisation_est_UNE_seule_pour_les_deux(self):
        """⚠️⚠️ *Deux moities d'un meme badge ne peuvent pas normaliser
        differemment.* Assiette : le CODE de `_kpi` et de `_statut_fill`, par
        AST -- pas la prose qui explique le correctif.
        """
        arbre = ast.parse(_HELPERS.read_text(encoding='utf-8'))
        for cible in ('_statut_fill', '_kpi'):
            fn = next((n for n in ast.walk(arbre)
                       if isinstance(n, ast.FunctionDef) and n.name == cible),
                      None)
            self.assertIsNotNone(fn, f'{cible} a disparu')
            corps = ast.unparse(ast.Module(body=fn.body, type_ignores=[]))
            self.assertIn(
                '_normaliser_statut', corps,
                f"`{cible}` ne passe plus par la normalisation commune : les "
                f"deux moities du badge peuvent de nouveau diverger")
            self.assertNotIn(
                '.upper()', corps,
                f"`{cible}` normalise DE SON COTE (`.upper()`) au lieu "
                f"d'appeler la source unique")
            # ⚠️⚠️ ET LA VALEUR NORMALISEE DOIT ETRE CELLE QU'ON UTILISE.
            # *Une MENTION n'est pas un APPEL* : `_norme = _normaliser_statut(
            # statut)` peut rester en place pendant que la ligne suivante
            # interroge la table avec le statut BRUT -- c'est exactement le
            # plant qui ne tombait pas.
            brut = [ast.unparse(n) for n in ast.walk(fn)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'get'
                    and getattr(n.func.value, 'id', '') in ('_MOT_RAG',)
                    and n.args and getattr(n.args[0], 'id', '') == 'statut']
            self.assertEqual(
                brut, [],
                f"`{cible}` interroge la table avec le statut BRUT : "
                f"{brut}. La normalisation est calculee et jetee")
        print("    BD-3 `_statut_fill` et `_kpi` passent par la MEME "
              "normalisation, 0 `.upper()` local")

    def test_BD_4_le_repli_garde_le_statut_BRUT_et_c_est_delibere(self):
        """⚠️ *Un repli qui reformule efface la trace de l'anomalie qu'il
        signale.* Un statut inconnu doit rester LISIBLE tel qu'il a ete recu,
        pour que l'actuaire voie ce que le systeme n'a pas su interpreter.
        """
        arbre = ast.parse(_HELPERS.read_text(encoding='utf-8'))
        fn = next(n for n in ast.walk(arbre)
                  if isinstance(n, ast.FunctionDef) and n.name == '_kpi')
        corps = ast.unparse(ast.Module(body=fn.body, type_ignores=[]))
        self.assertIn(
            "else statut", corps,
            "le repli ne rend plus le statut BRUT : un statut inconnu serait "
            "reformule, et l'actuaire ne verrait plus ce qui n'a pas ete "
            "compris")
        print("    BD-4 statut inconnu -> la chaine RECUE est publiee, jamais "
              "reformulee")


if __name__ == '__main__':
    unittest.main(verbosity=2)
