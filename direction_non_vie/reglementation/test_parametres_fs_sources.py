# -*- coding: utf-8 -*-
"""
=============================================================================
  LE VOCABULAIRE DE PROVENANCE EST-IL APPLIQUE ? (parametres_fs)
=============================================================================

CE FICHIER EST CELUI QUE `parametres_fs.py` AFFIRMAIT DEJA POSSEDER.

Son commentaire disait, du vocabulaire du champ `source` : << Un test
verrouille qu'aucune autre valeur ne s'y glisse : c'est ce qui empeche de
parer une approximation d'une reference d'article inventee. >>

Mesure du 03/09/2026, avant ce fichier :
  - aucun test du depot n'importait `parametres_fs` ni ne citait
    `PARAMETRES_FS`, `SOURCE_DELEGUE` ou `SOURCE_APPROXIMATION` ;
  - `SOURCES_ADMISES` n'apparaissait qu'a sa propre DEFINITION, ligne 53 :
    aucune comparaison, nulle part ;
  - et la preuve par execution :
        ParametreFS(0.42, 'ANNEXE_II_INVENTEE', 'art. 999', '...')
    se construisait SANS LA MOINDRE ERREUR.

  *Une contrainte ecrite dans un commentaire n'est pas une contrainte ;
  c'est une intention.*

Et c'est le risque exact que ce module existe pour empecher : son en-tete
raconte les lots B10-a et B10-b, ou TOUTES les valeurs fausses etaient
commentees << Annexe II >>, certaines citant un segment qui n'existe pas.

-----------------------------------------------------------------------------
QUELLE EST L'ASSIETTE ?
-----------------------------------------------------------------------------
La porte `_parametre()` ne garde QUE ce qui passe par elle. Un seizieme
parametre ecrit `ParametreFS(...)` directement dans le litteral la
contournerait, et un controle qui se contenterait de relire les sources de
la table finirait VERT : ses auteurs y ont ecrit de bonnes sources. C'est
pourquoi FS-3 mesure PAR AST que chaque entree passe par la porte -- le
CHEMIN, pas l'etat final.

-----------------------------------------------------------------------------
⚠️⚠️ POURQUOI CE FICHIER EST EN `unittest.TestCase` ET NON EN PYTEST
-----------------------------------------------------------------------------
Sa premiere version etait ecrite en fonctions nues avec `pytest.raises` et
`monkeypatch`. Les six controles passaient sous pytest, le sceau les tenait
tous les six -- et `scripts/gate.py` lance `python -m unittest discover`, qui
ne decouvre QUE les methodes de `TestCase`.

  Mesure : `unittest discover` sur ce fichier rendait << Ran 0 tests >>.

La gate rendait donc << OK - 127 tests >> pendant que pytest en comptait 154
sur la meme zone, et AUCUNE des six sentinelles n'etait executee par
l'instrument qui sert de preuve.

  *Un filet hors de l'assiette du garde-fou qui l'invoque est du decor,
  quelle que soit sa qualite.*
=============================================================================
"""

import ast
import pathlib
import unittest

from direction_non_vie.reglementation import parametres_fs as pfs

_SOURCE = pathlib.Path(pfs.__file__)


def _table_du_litteral() -> ast.Dict:
    """Le litteral `PARAMETRES_FS` tel qu'il est ECRIT, lu par AST."""
    arbre = ast.parse(_SOURCE.read_text(encoding='utf-8'))
    for noeud in arbre.body:
        cibles = ([noeud.target] if isinstance(noeud, ast.AnnAssign)
                  else getattr(noeud, 'targets', []))
        if any(getattr(c, 'id', '') == 'PARAMETRES_FS' for c in cibles):
            if not isinstance(noeud.value, ast.Dict):
                raise AssertionError(
                    "PARAMETRES_FS n'est plus un dictionnaire litteral : ce "
                    "controle lit la SOURCE, il faut le reecrire avec elle.")
            return noeud.value
    raise AssertionError("PARAMETRES_FS introuvable dans la source.")


class T1_La_Porte_Applique_Le_Vocabulaire(unittest.TestCase):
    """La contrainte que le module decrivait sans la tenir."""

    def test_fs_1_une_source_inventee_est_refusee(self):
        """FS-1 : la porte LEVE sur une source hors vocabulaire.

        Le message doit nommer la source fautive ET ce qui est admis : un
        mainteneur qui ajoute un parametre doit savoir quoi ecrire, pas
        seulement que son entree est refusee.
        """
        with self.assertRaises(ValueError) as capture:
            pfs._parametre(0.42, 'ANNEXE_II_INVENTEE', 'art. 999',
                           "un choc invente")
        message = str(capture.exception)
        self.assertIn('ANNEXE_II_INVENTEE', message,
                      f"Le refus ne nomme pas la source fautive : {message}")
        for admise in pfs.SOURCES_ADMISES:
            self.assertIn(admise, message,
                          f"Le refus ne dit pas ce qui EST admis : {message}")

    def test_fs_2_la_porte_relaie_sans_alterer(self):
        """FS-2 : la porte accepte les sources admises, et relaie TEL QUEL.

        ⚠️ CE CONTROLE A D'ABORD ETE DU DECOR, ET LE SCEAU L'A MONTRE DEUX
        FOIS. Il visait << la porte n'est pas un mur >> : propriete deja
        garantie par le simple fait que le module s'importe, puisque la table
        se construit au chargement et exerce les trois sources -- une porte
        qui refuserait tout ne ferait pas tomber ce test, elle empecherait
        de collecter quoi que ce soit.

        ⚠️ ET SON TEMOIN VALAIT 0,5, QUE `round(x, 2)` LAISSE INTACT : un
        arrondi silencieux glissait dans la porte sans que rien ne bronche.
        Le temoin est desormais 0,0418 -- le coefficient MCR reel, que le
        moindre arrondi ecrase a 0,04.
        """
        temoin = 0.0418
        for source in pfs.SOURCES_ADMISES:
            with self.subTest(source=source):
                p = pfs._parametre(temoin, source, 'art. 1', "temoin")
                self.assertEqual(p.source, source,
                                 "la porte a altere la source")
                self.assertEqual(p.reference, 'art. 1',
                                 "la porte a altere la reference")
                self.assertEqual(
                    p.valeur, temoin,
                    f"la porte a altere la valeur qu'elle relaie : "
                    f"{p.valeur!r} au lieu de {temoin!r}")

    def test_fs_3_chaque_entree_de_la_table_passe_par_la_porte(self):
        """FS-3 : L'ASSIETTE. Aucune entree ne contourne la porte.

        ⚠️ Le controle qui MANQUERAIT ici est celui qui relit `p.source`
        pour chaque parametre : la table serait verte avec ou sans porte,
        puisque ses auteurs y ont ecrit de bonnes sources. Ce qu'il faut
        verrouiller, c'est que la PROCHAINE entree ne puisse pas etre ecrite
        hors du chemin.
        """
        litteral = _table_du_litteral()
        hors_porte = []
        for cle, valeur in zip(litteral.keys, litteral.values):
            nom_cle = getattr(cle, 'value', ast.unparse(cle))
            appele = (ast.unparse(valeur.func)
                      if isinstance(valeur, ast.Call) else ast.unparse(valeur))
            if appele != '_parametre':
                hors_porte.append(f'{nom_cle} -> {appele}')
        self.assertFalse(
            hors_porte,
            "Ces entrees de PARAMETRES_FS contournent la porte `_parametre`, "
            "donc leur champ `source` n'est verifie par rien :\n  "
            + "\n  ".join(hors_porte))
        self.assertEqual(
            len(litteral.keys), len(pfs.PARAMETRES_FS),
            "Le litteral lu par AST et la table importee n'ont pas le meme "
            "nombre d'entrees : le controle ne lit pas ce qui s'execute.")

    def test_fs_5_la_porte_ne_corrige_pas_en_silence(self):
        """FS-5 : elle LEVE, elle ne substitue pas.

        Remplacer une source inconnue par `APPROXIMATION` deciderait a la
        place de celui qui ecrit la valeur -- exactement le geste que tout
        cet audit proscrit : personne d'autre que l'actuaire ne dit s'il a
        LU l'article.
        """
        with self.assertRaises(ValueError):
            pfs._parametre(0.42, 'ANNEXE_II', 'art. 999', "temoin")
        self.assertFalse(
            [c for c, p in pfs.PARAMETRES_FS.items()
             if p.source == 'ANNEXE_II'],
            "une source refusee s'est tout de meme installee dans la table")


class T2_Ce_Qui_Est_Publie(unittest.TestCase):
    """Ce que la table fait DIRE a un livrable reglementaire."""

    def setUp(self):
        self._table = pfs.PARAMETRES_FS
        self._admises = pfs.SOURCES_ADMISES

    def tearDown(self):
        pfs.PARAMETRES_FS = self._table
        pfs.SOURCES_ADMISES = self._admises

    def test_fs_4_la_phrase_de_provenance_est_derivee(self):
        """FS-4 : la proportion publiee SUIT la table.

        La docstring annoncait << HUIT SUR QUINZE >> en toutes lettres.
        Exact au moment ou c'etait ecrit -- et faux en silence des le
        parametre suivant, dans un texte destine a un livrable.
        """
        reelle = pfs.phrase_provenance()
        self.assertIn('15', reelle, f"compte total absent : {reelle}")
        self.assertIn('8', reelle, f"compte hors texte absent : {reelle}")

        pfs.PARAMETRES_FS = {c: p for c, p in self._table.items()
                             if p.source == pfs.SOURCE_DELEGUE}
        sans_hors_texte = pfs.phrase_provenance()
        self.assertNotIn(
            '8', sans_hors_texte,
            f"La phrase affirme encore 8 alors que la table n'en porte plus "
            f"aucun : elle est ECRITE, pas derivee -- {sans_hors_texte}")
        self.assertIn(str(len(pfs.PARAMETRES_FS)), sans_hors_texte)

    def test_fs_6_aucune_source_admise_n_est_publiee_par_defaut(self):
        """FS-6 : elargir le vocabulaire ne suffit pas a faire CITER.

        ⚠️ TROUVE EN REDIGEANT CE FICHIER. `libelle_reference` finissait par
        `return f"Approximation -- ..."` : pas un repli neutre, une
        AFFIRMATION. Toute source ajoutee a SOURCES_ADMISES sans revenir
        dans la fonction aurait ete publiee, dans un livrable reglementaire,
        comme une approximation -- sans que personne l'ait decide.

        C'est la meme forme que le defaut principal du module : un
        instrument qui AFFIRME plus que ce que le code porte.
        """
        for cle in pfs.PARAMETRES_FS:
            with self.subTest(parametre=cle):
                self.assertTrue(pfs.libelle_reference(cle),
                                f"citation vide pour {cle}")

        faux = 'SOURCE_AJOUTEE_SANS_FORMULATION'
        pfs.SOURCES_ADMISES = self._admises + (faux,)
        pfs.PARAMETRES_FS = dict(
            self._table,
            temoin=pfs._parametre(0.1, faux, 'art. 1', "temoin"))
        with self.assertRaises(ValueError) as capture:
            pfs.libelle_reference('temoin')
        self.assertIn(
            faux, str(capture.exception),
            "Le refus ne nomme pas la source qu'il ne sait pas citer.")


class T3_La_Gate_Voit_Ce_Fichier(unittest.TestCase):
    """⚠️ LE CONTROLE QUI MANQUAIT A TOUT LE DEPOT.

    `scripts/gate.py` lance `unittest discover`. Un fichier de test ecrit en
    fonctions nues lui est INVISIBLE : il passe sous pytest, la gate le
    ignore, et la gate rend VERT sans l'avoir lance.
    """

    def test_fs_7_ce_fichier_est_decouvrable_par_unittest(self):
        """FS-7 : ce filet est dans l'assiette de la gate qui l'invoque.

        Mesure du 03/09/2026 sur le depot entier : 3 013 tests decouvrables
        par unittest, et 163 qui ne le sont pas, dont 21 dans cette zone
        meme (`a9_coherence`, `a13_audit`, `a14_mortalite`, moities nues).
        """
        arbre = ast.parse(
            pathlib.Path(__file__).read_text(encoding='utf-8'))
        nues = [n.name for n in arbre.body
                if isinstance(n, ast.FunctionDef)
                and n.name.startswith('test')]
        self.assertFalse(
            nues,
            "Ces tests sont ecrits en fonctions nues au niveau module : "
            "`unittest discover`, donc `scripts/gate.py`, ne les verra "
            f"JAMAIS -- {nues}")

        classes = [n for n in arbre.body
                   if isinstance(n, ast.ClassDef)
                   and any('TestCase' in ast.unparse(b) for b in n.bases)]
        methodes = sum(1 for c in classes for m in c.body
                       if isinstance(m, ast.FunctionDef)
                       and m.name.startswith('test'))
        self.assertGreaterEqual(
            methodes, 7,
            f"Ce fichier ne porte que {methodes} methodes de test visibles.")


if __name__ == '__main__':
    unittest.main()
