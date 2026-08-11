"""Tests — l'outil de mesure de propreté garde ses trois désamorçages.

⚠️ GATE : `py -m unittest discover -s core -t .` — voir test_imports_app.py,
qui explique pourquoi les tests de ce qui vit hors des directions atterrissent
ici : `scripts/` ne porte aucun test et aucune gate ne l'y découvrirait.

POURQUOI CES TESTS EXISTENT. `scripts/proprete.py` ne calcule rien qui entre
dans un rapport : c'est un INSTRUMENT. Un instrument faux est pire qu'aucun,
parce qu'on le croit. Trois pièges d'outillage ont faussé cette mesure au
moins une fois chacun, et l'outil les désamorce — mais rien n'empêcherait
quelqu'un de « simplifier » l'un des trois et de rendre la mesure muette :

  · écrire la référence dans un fichier temporaire hors du dépôt — ruff n'y
    résout pas la même configuration, et les comptes n'ont plus de sens ;
  · nommer le témoin autrement — vulture cesse alors de taire les méthodes
    `test_*`, et affiche 97 signalements là où il en tient 23 ;
  · appeler `ruff --fix` — il corrige des défauts ANTÉRIEURS au lot, deux
    fois douze hunks hors périmètre dans la même journée.
"""
import ast
import os
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTIL = os.path.join(RACINE, 'scripts', 'proprete.py')


def _source():
    with open(OUTIL, encoding='utf-8') as f:
        return f.read()


class T1_LesTroisDesamorcages(unittest.TestCase):

    def test_la_reference_ruff_passe_par_le_MEME_chemin(self):
        """⚠️ PIÈGE 1. Une référence hors du dépôt ne résout pas la même
        configuration ruff : la comparaison devient un chiffre contre un
        autre chiffre, sans rapport entre eux."""
        src = _source()
        self.assertIn('--stdin-filename', src)
        self.assertNotIn('tempfile', src,
                         'la référence repasse par un fichier temporaire')
        print("    OK 1 : la reference ruff passe par --stdin-filename")

    def test_le_temoin_vulture_garde_le_prefixe_du_nom(self):
        """⚠️ PIÈGE 2. Vulture tait les méthodes `test_*` selon le NOM DU
        FICHIER. Un témoin mal nommé affichait 97 au lieu de 23."""
        src = _source()
        self.assertIn('_zz_temoin', src)
        self.assertIn('base, _ = os.path.splitext(nom)', src,
                      'le témoin ne dérive plus son nom du fichier mesuré')
        print("    OK 2 : le temoin vulture garde le prefixe du fichier")

    def test_l_outil_n_appelle_JAMAIS_ruff_fix(self):
        """⚠️ PIÈGE 3. `--fix` corrige des défauts antérieurs au lot. Un
        outil de MESURE qui corrige ne mesure plus ce qu'il rapporte.

        ⚠️ ET L'ANCRE EST L'ARBRE, PAS LE TEXTE : la docstring de l'outil
        NOMME `ruff --fix` pour expliquer pourquoi il ne l'appelle pas. Un
        `assertNotIn` sur le source entier échouait sur cette explication —
        le même défaut d'ancre qu'un commentaire pris pour du code.
        """
        arbre = ast.parse(_source())
        # ⚠️ ON EXCLUT PAR NŒUD, PAS PAR VALEUR : `ast.get_docstring` NORMALISE
        # le texte (dédente, rogne), donc comparer les chaînes ne reconnaît
        # aucune docstring. Deuxième défaut d'ancre du même test.
        docstrings = set()
        for n in ast.walk(arbre):
            corps = getattr(n, 'body', None)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)) and corps:
                premier = corps[0]
                if (isinstance(premier, ast.Expr)
                        and isinstance(premier.value, ast.Constant)
                        and isinstance(premier.value.value, str)):
                    docstrings.add(id(premier.value))
        litteraux = [n.value for n in ast.walk(arbre)
                     if isinstance(n, ast.Constant)
                     and isinstance(n.value, str)
                     and id(n) not in docstrings]
        fautifs = [x for x in litteraux if '--fix' in x]
        self.assertEqual(fautifs, [],
                         f'`--fix` apparaît dans du code : {fautifs}')
        print(f"    OK 3 : l'outil mesure, il ne corrige pas "
              f"({len(litteraux)} litteraux relus)")


class T2_LaRegleArbitree(unittest.TestCase):
    """⚠️ LE ZÉRO N'EST STRICT QUE SUR LES CODES DE CORRECTION. `RUF012` et
    `UP009` sont des préférences de style : la règle « +0 » sur eux avait fait
    sortir une fixture de sa classe pour la mettre là où elle est moins bien.
    Une règle de propreté qui arbitre la conception a cessé de servir.
    """

    def _constantes(self):
        arbre = ast.parse(_source())
        valeurs = {}
        for n in arbre.body:
            if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
                try:
                    valeurs[n.targets[0].id] = ast.literal_eval(n.value)
                except ValueError:
                    pass
        return valeurs

    def test_les_deux_familles_sont_DISTINCTES_et_declarees(self):
        v = self._constantes()
        stricts = set(v.get('CODES_STRICTS', ()))
        toleres = set(v.get('CODES_TOLERES', ()))
        self.assertTrue(stricts and toleres)
        self.assertEqual(stricts & toleres, set(),
                         'un code ne peut pas être strict ET toléré')
        for attendu in ('RUF012', 'UP009'):
            self.assertIn(attendu, toleres)
        for attendu in ('F', 'E', 'W', 'DTZ'):
            self.assertIn(attendu, stricts)
        print(f"    OK regle : {len(stricts)} familles strictes, "
              f"{len(toleres)} tolerees, aucune des deux")

    def test_le_motif_vulture_vise_les_classes_de_test(self):
        """⚠️ ET PAS UNE LISTE BLANCHE : elle deviendrait une liste à tenir."""
        motif = self._constantes().get('MOTIF_VULTURE', '')
        self.assertTrue(motif)
        for prefixe in ('T[0-9]*_*', 'V[0-9]_*'):
            self.assertIn(prefixe, motif)
        print("    OK motif : les classes de test sont exclues par MOTIF")


if __name__ == '__main__':
    unittest.main(verbosity=2)


def _outil():
    """Le module de l'outil, charge depuis son chemin (il vit hors paquet)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('proprete_outil', OUTIL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class T3_LEtatAbsolu(unittest.TestCase):
    """L'outil doit VOIR ce qui ne change pas — c'etait son angle mort.

    ⚠️ IL AFFICHAIT `31 -> 31` SANS DIRE QUE 24 ETAIENT DES CODES DE
    CORRECTION. Un defaut committe devenait invisible a l'instrument cense
    l'attraper : meme famille que la gate rendant « Ran 0 tests » et sortant
    en 0, et que le registre ou « 0 non etabli » ne se comptait pas.
    """

    def test_l_absolu_et_le_delta_partagent_UNE_SEULE_regle(self):
        """⚠️ Deux classifications donneraient deux chiffres pour le meme
        fichier selon qui mesure — l'erreur exacte commise en annoncant
        3 791 defauts la ou l'outil en compte 7 618."""
        o = _outil()
        src = _source()
        self.assertIn('def _famille(', src)
        # Le delta comme l'absolu passent par `_famille`, jamais par une
        # comparaison recopiee.
        corps_classer = src.split('def _classer(')[1].split('\ndef ')[0]
        corps_absolu = src.split('def absolu(')[1].split('\ndef ')[0]
        for nom, corps in (('_classer', corps_classer), ('absolu', corps_absolu)):
            self.assertIn('_famille(', corps,
                          f'{nom} doit classer par `_famille`, pas autrement')
        self.assertEqual(o._famille('UP009'), 'tolere')
        self.assertEqual(o._famille('F401'), 'correction')
        self.assertEqual(o._famille('I001'), 'jamais_examine')

    def test_un_code_INCONNU_compte_comme_un_defaut_MAIS_SE_DISTINGUE(self):
        """⚠️ Arbitre le 11/08 : defensif. Un code que le projet n'a pas
        examine compte comme un defaut — MAIS PAS SOUS LE MEME NOM.

        ⚠️ `F401` est un defaut ARBITRE ; `I001` n'a JAMAIS ETE EXAMINE. Les
        confondre laisserait croire que 7 618 defauts ont ete juges, quand la
        moitie n'a jamais ete regardee. Avant ce lot, les deux branches de
        `_classer` etaient IDENTIQUES : `CODES_STRICTS` ne gouvernait RIEN."""
        o = _outil()
        self.assertEqual(o._famille('XYZ999'), 'jamais_examine')
        self.assertNotEqual(o._famille('I001'), o._famille('F401'))
        # Les deux comptent, aucun n'est tolere.
        for code in ('I001', 'F401', 'XYZ999'):
            self.assertNotEqual(o._famille(code), 'tolere')

    def test_l_absolu_decompose_ce_que_le_total_taisait(self):
        o = _outil()
        arbitres, jamais_vus, declares = o.absolu(
            {'F401': 24, 'I001': 8, 'UP009': 7})
        self.assertEqual((arbitres, jamais_vus, declares), (24, 8, 7))

    def test_l_absolu_N_EST_PAS_un_verdict(self):
        """⚠️ LE POINT QUI REND LA REGLE TENABLE. Faire echouer un lot sur la
        dette pre-existante bloquerait toute retouche dans un gros fichier.
        Le verdict reste sur le DELTA ; la dette se ferme par DECISION."""
        src = _source()
        # `faute` — la variable qui commande la sortie — ne doit jamais etre
        # armee par l'absolu.
        corps = src.split('def mesurer(')[1]
        for ligne in corps.split('\n'):
            if 'faute = True' in ligne:
                self.assertNotIn('dette', ligne)
                self.assertNotIn('absolu', ligne)
        self.assertIn('DECISION', src)

    def test_le_total_du_lot_est_TOUJOURS_affiche_meme_a_zero(self):
        """⚠️ L'absence d'une ligne ne doit jamais pouvoir se lire comme
        « je n'ai pas regarde » — meme lecon que NON_ETABLI dans le registre
        IFRS 17."""
        src = _source()
        corps = src.split('def mesurer(')[1]
        i = corps.index('DETTE PRE-EXISTANTE DU LOT')
        avant = corps[:i].split('\n')[-3:]
        self.assertNotIn('if ', '\n'.join(avant),
                         "le total du lot ne doit etre sous AUCUNE condition")
