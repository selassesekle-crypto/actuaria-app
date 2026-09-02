"""⚠️⚠️ 49 IMPORTS PAYAIENT UNE SURFACE QUE PERSONNE N'UTILISE.

Constat `socle/C6`, ouvert le 03/09/2026 en auditant les 1 170 lignes que la
carte declarait << jamais auditees >>.

`core/__init__.py` re-exportait vingt symboles par des `from .x import y`
executes A L'IMPORT DU PAQUET. Or importer n'importe quel sous-module
(`from core import arrete`) execute ce fichier. Mesure du 03/09 :

```
  from core import arrete   AVANT : 6 modules, 4 429 lignes
                            APRES : 1 module,    233 lignes
```

⚠️⚠️ ET LA SURFACE AINSI PAYEE A **ZERO CONSOMMATEUR**. Releve par AST sur
tout le depot : **49 imports `from core import X`, et les 49 importent un
SOUS-MODULE** (`arrete`, `frontiere_llm`, `traitement_ia`, `format_fr`...).
Aucun n'importe un symbole d'`__all__`.

> *Une porte que personne ne franchit et que tout le monde paye.*

⚠️ LE RE-EXPORT N'EST PAS SUPPRIME, IL EST RENDU PARESSEUX (PEP 562). Le
depot est PUBLIC : `from core import PlanTarifaire` peut vivre dans un carnet
qu'on ne voit pas. *Retirer une API publique parce qu'aucun appelant INTERNE
ne l'utilise, c'est mesurer sur la mauvaise assiette.*

⚠️ SECOND DEFAUT, DANS LE FICHIER QUI SERT A DECLARER LA SURFACE :
`construire_lx` et `insee_qx_prospectif` etaient importes SANS figurer dans
`__all__`. Prouve par execution : joignables par `from core import X`,
invisibles a `from core import *`.
"""
from __future__ import annotations

import ast
import importlib
import pathlib
import subprocess
import sys
import unittest

import core

_RACINE = pathlib.Path(__file__).resolve().parents[1]

#: Les quatre sous-modules que l'ancien `__init__` chargeait AVIDEMENT.
_AVIDES = ('core.base_agent', 'core.conformite_reglementaire',
           'core.plan_tarifaire', 'core.tables_mortalite')


class TestPaquetCore(unittest.TestCase):

    def test_SC6_1_le_all_NE_PEUT_PAS_diverger_de_la_table(self):
        """⚠️⚠️ LE PATRON DU GOLDEN D'`EMPREINTE_SCHEMA`.

        `__all__` est un LITTERAL -- un `__all__` calcule est invisible a
        l'outillage statique, et `PLE0605` a raison de le refuser. La
        divergence, elle, est interdite ici.

        *Ce qui doit rester lisible se declare ; ce qui doit rester vrai se
        teste.* C'est tres exactement le defaut que ce fichier portait :
        `construire_lx` et `insee_qx_prospectif` etaient re-exportes sans
        etre declares.
        """
        self.assertEqual(
            list(core.__all__), sorted(core._REEXPORTS),
            "`__all__` et la table de re-export ont diverge : un symbole est "
            "joignable par `from core import X` mais invisible a "
            "`from core import *`, ou l'inverse")
        for s in ('construire_lx', 'insee_qx_prospectif'):
            self.assertIn(s, core.__all__,
                          f"'{s}' etait le defaut d'origine : re-exporte, "
                          f"jamais declare")
        print(f"    SC6-1 {len(core.__all__)} symboles declares == la table, "
              f"aucune divergence possible")

    def test_SC6_2_LE_CONSTAT_importer_un_sous_module_ne_charge_QUE_lui(self):
        """⚠️⚠️ LA MESURE QUI A OUVERT LE CONSTAT, DEVENUE CONTROLE.

        Assiette : un interpreteur NEUF -- dans celui-ci, les modules sont
        deja charges par les autres tests, et la mesure ne prouverait rien.
        *Un temoin contamine par ses voisins ne mesure que ses voisins.*
        """
        code = (
            'import sys; from core import arrete; '
            "print(','.join(sorted(m for m in sys.modules "
            "if m.startswith('core.'))))"
        )
        # ⚠️ `check=False` EXPLICITE : on veut LIRE le code de retour et son
        # `stderr` dans l'assertion, pas lever une exception qui masquerait
        # le message. *Un echec qu'on veut expliquer ne se lance pas tout
        # seul.*
        r = subprocess.run([sys.executable, '-B', '-c', code], check=False,
                           capture_output=True, text=True, cwd=str(_RACINE),
                           encoding='utf-8', errors='replace')
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        charges = [m for m in r.stdout.strip().split(',') if m]
        self.assertEqual(
            charges, ['core.arrete'],
            f"importer `core.arrete` charge {charges} : le paquet re-importe "
            f"avidement une surface que personne n'utilise")
        for avide in _AVIDES:
            self.assertNotIn(avide, charges)
        print(f"    SC6-2 `from core import arrete` -> {charges} "
              f"(avant : 6 modules, 4 429 lignes)")

    def test_SC6_3_le_contrat_PUBLIC_est_intact_dans_les_deux_formes(self):
        """⚠️⚠️ *Un correctif qui retire un mecanisme emporte tout ce que ce
        mecanisme portait.* Le depot est PUBLIC : les deux formes d'acces
        doivent survivre au passage en paresseux.
        """
        for nom in core.__all__:
            self.assertTrue(hasattr(core, nom),
                            f"`from core import {nom}` a cesse de fonctionner")
        espace: dict = {}
        exec('from core import *', espace)          # noqa: S102 - le contrat
        manquants = [s for s in core.__all__ if s not in espace]
        self.assertEqual(manquants, [],
                         f'`from core import *` n exporte plus {manquants}')
        print(f"    SC6-3 les {len(core.__all__)} symboles joignables par les "
              f"DEUX formes")

    def test_SC6_4_un_attribut_INCONNU_leve_au_lieu_de_se_taire(self):
        """⚠️ Un `__getattr__` trop permissif rendrait `None` sur une faute de
        frappe. *Une porte paresseuse ne doit pas devenir une porte muette.*"""
        with self.assertRaises(AttributeError) as capt:
            core.symbole_qui_nexiste_pas          # noqa: B018 - c'est le test
        self.assertIn('symbole_qui_nexiste_pas', str(capt.exception))
        # ⚠️ SECOND SENS : un symbole de la table, lui, se resout vraiment.
        self.assertTrue(callable(core.get_qx))
        print("    SC6-4 attribut inconnu -> AttributeError nomme ; "
              "attribut de la table -> resolu")

    def test_SC6_5_la_table_pointe_vers_des_sous_modules_QUI_EXISTENT(self):
        """⚠️⚠️ SANS CECI, UNE ENTREE FAUSSE NE SE VERRAIT QU'A L'USAGE.

        Le ré-export etant PARESSEUX, une cible erronee ne leve plus a
        l'import du paquet : elle attend qu'un appelant la demande. *Un
        mecanisme paresseux deplace l'erreur dans le temps ; le controle doit
        la ramener a la gate.*
        """
        for nom, module in sorted(core._REEXPORTS.items()):
            with self.subTest(symbole=nom):
                m = importlib.import_module(f'core.{module}')
                self.assertTrue(
                    hasattr(m, nom),
                    f"`core.{module}` ne porte pas '{nom}' : la table de "
                    f"re-export designe une cible qui n'existe pas")
        print(f"    SC6-5 les {len(core._REEXPORTS)} cibles de la table "
              f"existent toutes, verifiees une par une")

    def test_SC6_6_aucun_appelant_INTERNE_ne_dependait_de_la_surface(self):
        """⚠️⚠️ LA MESURE QUI A JUSTIFIE DE NE PAS SUPPRIMER.

        49 imports `from core import X`, et les 49 importent un SOUS-MODULE.
        Ce controle fige le fait : le jour ou un appelant interne se mettra a
        importer un symbole d'`__all__`, il tombera -- et ce sera le signal
        que la surface a trouve un usage, donc qu'elle doit etre gardee pour
        une autre raison que la prudence.
        """
        symboles = set(core.__all__)
        interne = []
        for p in sorted(_RACINE.rglob('*.py')):
            if '__pycache__' in p.parts or p.name == '__init__.py':
                continue
            try:
                arbre = ast.parse(p.read_text(encoding='utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for n in ast.walk(arbre):
                if (isinstance(n, ast.ImportFrom) and n.module == 'core'
                        and n.level == 0):
                    for al in n.names:
                        if al.name in symboles:
                            interne.append(
                                f'{p.relative_to(_RACINE).as_posix()}:'
                                f'{n.lineno} -> {al.name}')
        self.assertEqual(
            interne, [],
            f"un appelant interne importe desormais un symbole d'`__all__` "
            f"depuis le paquet : {interne}. Ce n'est pas une faute -- c'est "
            f"un CHANGEMENT DE FAIT, et la mesure qui justifiait le maintien "
            f"de cette surface doit etre relue")
        print("    SC6-6 0 appelant interne ne passe par la surface du "
              "paquet (49 imports, tous des sous-modules)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
