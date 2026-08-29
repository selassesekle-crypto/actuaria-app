"""Controles positifs — lot 4.7 : les deux figures DL entrent au rapport signe.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
UNE SEULE PROPRIETE : *une figure qui entre au rapport signe doit y arriver
REELLEMENT, dans les deux formats, et ne pas y arriver quand elle n'existe pas.*

═══ CE QUE SELASSE A ARBITRE ═══

`convergence_loss` (H1 DL) et `comparaison_dl_glm` (H3 DL) quittent
`FIGURES_ECARTEES` pour le PLAN, chapitre 4. Elles n'y entrent qu'apres la
fermeture de leurs trois constats : `a5/C4` (courbe simulee), `a5/C5` (barres
a zero pour un modele absent), `a5/C10` (verdict sur le mauvais modele).

⚠️⚠️ CE N'ETAIT PAS DU CABLAGE, MAIS UN CHANGEMENT D'INTERFACE. Le
constructeur du rapport ne recevait AUCUN `result_a5` : sa signature ne le
prevoyait pas. Il a fallu le faire descendre par `generer_rapport_tarification`
-> `export_html` / `export_word` / `export_pdf` -> `figures_disponibles`.

⚠️⚠️ ET IL EST EN MOT-CLE SEUL, EN FIN DE SIGNATURE. Releve par AST AVANT
d'ecrire la premiere ligne : `export_html` est appelee avec NEUF arguments
POSITIONNELS en production et dans une trentaine de tests, `figures_disponibles`
avec trois. Inserer `result_a5` entre `a4` et `a6` -- l'ordre de lecture --
aurait fait glisser `result_a6` dans `result_a5` : deux dictionnaires, aucune
erreur de type, et un rapport signe construit sur les mauvaises donnees.
*Un accident de typage qui decide de ce qui est publie est plus dangereux
qu'une decision explicite.* Le `*` rend cet accident IMPOSSIBLE.

⚠️ ET LE CABLAGE AVAIT UN TROU, QUE `proprete` A ATTRAPE : `export_pdf`
utilisait `result_a5` sans l'avoir en parametre (`F821`). Le PDF aurait leve
un `NameError` a la premiere generation. Un test ci-dessous ferme ce trou.

⚠️ LES SIX AUTRES FIGURES D'A5 RESTENT ECARTEES, et leur motif a ete PRECISE :
il ne dit plus << A5 n'entre pas dans la chaine du rapport >> -- ambigu, et
faux si on le lisait << A5 ne participe pas >> -- mais qu'elles sont destinees
a qui CONSTRUIT le modele. Leur place est le document technique de validation
(arbitrage M4), chantier ouvert sur les 25 figures ecartees.
"""

from __future__ import annotations

import io
import unittest
import zipfile

from direction_non_vie.tarification.services import rapport_modeles_tarif as R


class _FigureFactice:
    """Un objet de figure minimal — seul son identite compte ici."""

    def __init__(self, cle):
        self.cle = cle

    def to_html(self, **_):
        return f'<div data-figure="{self.cle}"></div>'


def _charges(avec_a5: bool = True):
    """Les quatre resultats d'agent, portant les figures du catalogue."""
    res = {'a3': {}, 'a4': {}, 'a5': {}, 'a6': {}}
    for cle, (agent, dico) in R.SOURCES_FIGURES.items():
        if agent == 'a5' and not avec_a5:
            continue
        res[agent].setdefault(dico, {})[cle] = _FigureFactice(cle)
    return res['a3'], res['a4'], res['a6'], res['a5']


_DEUX = ('convergence_loss', 'comparaison_dl_glm')


class TestLesDeuxFiguresDLSontPubliees(unittest.TestCase):
    """Elles quittent l'ecart pour le plan, et elles y arrivent vraiment."""

    def test_elles_ne_sont_PLUS_ecartees_et_sont_AU_PLAN(self):
        """⚠️⚠️ LE TEST QUI FERME LE LOT — les deux mouvements ENSEMBLE.

        Retirer de `FIGURES_ECARTEES` sans ajouter au plan les rendrait
        << ni publiees ni ecartees >> ; l'inverse les mettrait aux deux
        endroits. La garde du catalogue attrape les deux cas, on le verifie
        ici sur les cles nommees.
        """
        au_plan = {c for _, cles in R.PLAN_FIGURES for c in cles}
        for cle in _DEUX:
            with self.subTest(figure=cle):
                self.assertNotIn(cle, R.FIGURES_ECARTEES)
                self.assertIn(cle, au_plan)
                self.assertIn(cle, R.TITRES_FIGURES)
                self.assertEqual(R.SOURCES_FIGURES[cle],
                                 ('a5', 'graphiques_validation'))
        print("    P-1 les 2 figures DL : hors ecart, au plan, avec titre "
              "et source ('a5', 'graphiques_validation')")

    def test_elles_sont_au_CHAPITRE_4_avec_les_autres_hypotheses(self):
        """⚠️ Le chapitre 4 s'appelle « Validation des hypotheses
        actuarielles » et porte deja H1 GLM, H2 GLM et H1 ML. A5 nomme les
        siennes H1 et H3 : les mettre au chapitre 3 (le classement) aurait
        separe une hypothese de ses soeurs pour la coller a des rangs."""
        ch4 = dict(R.PLAN_FIGURES)[4]
        for cle in _DEUX:
            self.assertIn(cle, ch4)
        for cle in _DEUX:
            self.assertRegex(R.TITRES_FIGURES[cle], r'^H\d DL — ',
                             'le titre quitte la nomenclature « H<n> DL »')
        print(f"    P-2 chapitre 4 : {len(ch4)} figures, dont H1 DL et H3 DL")

    def test_elles_ARRIVENT_dans_les_DEUX_formats(self):
        """⚠️⚠️ LE CATALOGUE PEUT LES NOMMER SANS QU'ELLES ARRIVENT.

        Si `result_a5` ne descend pas jusqu'a `figures_disponibles`, le
        rapport en publie deux de moins — EN SILENCE. On lit donc les deux
        livrables, pas la table.
        """
        a3, a4, a6, a5 = _charges()
        html = R.export_html(a3, a4, a6, 'DEMO', '31/12/2025', 'PUB',
                             result_a5=a5,
                             narration_calculee=('Texte.', 'temoin'))
        blob = R.export_word(a3, a4, a6, 'DEMO', '31/12/2025', 'PUB',
                             result_a5=a5,
                             narration_calculee=('Texte.', 'temoin'))
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            xml = z.read('word/document.xml').decode('utf-8', 'replace')
        for cle in _DEUX:
            titre = R.TITRES_FIGURES[cle]
            with self.subTest(figure=cle):
                self.assertIn(titre[:36], html, 'absente du HTML')
                self.assertIn(titre[:36], xml, 'absente du Word')
        print("    P-3 les 2 figures sont dans le HTML ET dans le .docx")

    def test_le_PDF_ne_leve_plus_sur_un_nom_indefini(self):
        """⚠️⚠️ LE TROU DU CABLAGE, ATTRAPE PAR `proprete` AVANT LA GATE.

        `export_pdf` passait `result_a5=result_a5` sans avoir le parametre :
        `F821`, nom indefini. Le PDF aurait leve un `NameError` a la premiere
        generation. On verifie la SIGNATURE, parce que `weasyprint` est
        absent de ce poste et que l'appel se replierait avant d'atteindre le
        defaut. *Un test qui ne peut pas executer le chemin verifie le
        contrat, il ne se tait pas.*
        """
        import inspect
        sig = inspect.signature(R.export_pdf)
        self.assertIn('result_a5', sig.parameters)
        self.assertEqual(sig.parameters['result_a5'].kind,
                         inspect.Parameter.KEYWORD_ONLY)
        source = inspect.getsource(R.export_pdf)
        self.assertIn('result_a5=result_a5', source,
                      'le PDF ne transmet pas les figures DL a son HTML')
        print("    P-4 `export_pdf` a bien `result_a5`, en mot-cle seul")

    def test_result_a5_est_MOT_CLE_SEUL_sur_toute_la_chaine(self):
        """⚠️⚠️ LA DECISION DE CONCEPTION, EPINGLEE.

        Si quelqu'un le rendait positionnel — ou pire, l'inserait entre `a4`
        et `a6` — les appels a neuf positionnels feraient glisser `result_a6`
        dans `result_a5` sans aucune erreur. Ce test rend le glissement
        impossible a introduire en silence.
        """
        import inspect
        for fn in (R.figures_disponibles, R.export_html, R.export_word,
                   R.export_pdf, R.generer_rapport_tarification):
            with self.subTest(fonction=fn.__name__):
                sig = inspect.signature(fn)
                self.assertIn('result_a5', sig.parameters)
                self.assertEqual(
                    sig.parameters['result_a5'].kind,
                    inspect.Parameter.KEYWORD_ONLY,
                    f'{fn.__name__} : `result_a5` n\'est plus en mot-cle seul')
                positions = list(sig.parameters)
                self.assertLess(positions.index('result_a6'),
                                positions.index('result_a5'),
                                f'{fn.__name__} : `result_a5` est passe AVANT '
                                f'`result_a6` — les appels positionnels '
                                f'glissent')
        print("    P-5 les 5 fonctions de la chaine : `result_a5` en mot-cle "
              "seul, et APRES `result_a6`")

    def test_SECOND_SENS_sans_A5_le_rapport_ne_les_INVENTE_pas(self):
        """⚠️⚠️ SECOND SENS, ET IL EST LE PLUS IMPORTANT ICI.

        A5 n'est pas sur tous les chemins : `scripts/rapport_tarif_local.py`
        passe `result_a5=None`, et PyTorch peut etre absent. Le rapport doit
        alors publier DEUX FIGURES DE MOINS, sans trou de numerotation et
        sans rien fabriquer.
        """
        a3, a4, a6, _ = _charges(avec_a5=False)
        dispo = R.figures_disponibles(a3, a4, a6)
        for cle in _DEUX:
            self.assertNotIn(cle, dispo)
        plan = R.numeroter(dispo)
        numeros = sorted(f.numero for fs in plan.values() for f in fs)
        self.assertEqual(numeros, list(range(1, len(numeros) + 1)),
                         'trou de numerotation quand A5 est absent')
        self.assertEqual(len(numeros), len(R.SOURCES_FIGURES) - 2)
        print(f"    P-6 sans A5 : {len(numeros)} figures, numerotees 1.."
              f"{len(numeros)} sans trou")

    def test_leur_absence_est_DECLAREE_conditionnelle(self):
        """⚠️ Sans cette declaration, le controle d'absence de
        `figures_disponibles` crierait au defaut a chaque execution sans DL.

        *Une absence ATTENDUE se declare ; toute autre est un defaut* — c'est
        la regle que `FIGURES_CONDITIONNELLES` porte deja pour SHAP.
        """
        for cle in _DEUX:
            with self.subTest(figure=cle):
                self.assertIn(cle, R.FIGURES_CONDITIONNELLES)
                self.assertIn('A5', R.FIGURES_CONDITIONNELLES[cle])
        print("    P-7 les 2 absences sont declarees conditionnelles, comme "
              "SHAP")

    def test_les_SIX_autres_figures_d_A5_restent_ecartees(self):
        """⚠️⚠️ ON N'OUVRE PAS LA PORTE A TOUT A5.

        Selasse a arbitre DEUX figures, pas huit. Les six autres restent
        ecartees ; leur motif ne dit plus << A5 n'entre pas dans la chaine >>
        -- ambigu et faux si on le lit << A5 ne participe pas >>, alors que
        ses modeles concourent et qu'un DL a gagne une cible.
        """
        autres = ('apprentissage_cann', 'apprentissage_tabnet',
                  'importance_tabnet', 'jauge_surapprentissage',
                  'comparaison_gini', 'scorecard_validation_dl')
        for cle in autres:
            with self.subTest(figure=cle):
                self.assertIn(cle, R.FIGURES_ECARTEES)
                self.assertNotIn("n'entre pas dans la chaîne",
                                 R.FIGURES_ECARTEES[cle],
                                 'le motif ambigu est revenu')
        self.assertEqual(
            len([c for c in R.SOURCES_FIGURES if c in _DEUX]), 2)
        print(f"    P-8 {len(autres)} figures d'A5 restent ecartees, avec un "
              f"motif qui ne dit plus « A5 n'entre pas dans la chaine »")


    def test_A6_PASSE_bien_result_a5_au_constructeur_du_rapport(self):
        """⚠️⚠️ LE TROU QUE LA VIOLATION PLANTEE A REVELE — ET IL ETAIT REEL.

        En retirant `result_a5=result_a5` du site d'appel d'A6, **aucun test
        du depot ne tombait**. Tout le cablage pouvait etre juste — catalogue,
        plan, signatures, les deux formats — et les figures n'arrivaient
        jamais, parce que le SEUL appel de production ne les passait pas.
        *C'est le motif de `correctif-a-cote-de-la-surface` applique au
        filet lui-meme : je verifiais le mecanisme, pas le site.*

        Releve par AST : on ne cherche pas une chaine, on lit l'appel.
        """
        import ast as _ast
        import pathlib as _pathlib
        chemin = (_pathlib.Path(__file__).resolve().parent
                  / 'a6_comparaison' / 'agent.py')
        arbre = _ast.parse(chemin.read_text(encoding='utf-8'))
        appels = [
            n for n in _ast.walk(arbre)
            if isinstance(n, _ast.Call)
            and (getattr(n.func, 'id', None)
                 or getattr(n.func, 'attr', None)) == 'generer_rapport_tarification'
        ]
        self.assertTrue(appels, 'A6 n\'appelle plus le constructeur du rapport')
        for appel in appels:
            mots = [k.arg for k in appel.keywords]
            self.assertIn(
                'result_a5', mots,
                f"A6 (l.{appel.lineno}) n'envoie pas `result_a5` : les figures "
                f"DL du plan n'arriveront JAMAIS, en silence.")
            self.assertEqual(appel.args, [],
                             'A6 passe des arguments positionnels : un '
                             'glissement deviendrait possible')
        print(f"    P-9 A6 passe `result_a5` a ses {len(appels)} appel(s), "
              f"en mots-cles (releve AST)")


class TestLaGardeResteCoherente(unittest.TestCase):
    """La garde du catalogue, dans les DEUX sens, apres le mouvement."""

    def test_aucune_figure_au_plan_n_est_ecartee_et_reciproquement(self):
        """⚠️ Les deux sens ENSEMBLE, sur l'etat d'aujourd'hui."""
        au_plan = {c for _, cles in R.PLAN_FIGURES for c in cles}
        self.assertEqual(au_plan & set(R.FIGURES_ECARTEES), set(),
                         'une figure est a la fois publiee et ecartee')
        self.assertEqual(au_plan - set(R.SOURCES_FIGURES), set(),
                         'une figure du plan n\'a pas de source')
        self.assertEqual(set(R.SOURCES_FIGURES) - au_plan, set(),
                         'une figure a une source mais n\'est pas au plan')
        self.assertEqual(set(R.TITRES_FIGURES), au_plan,
                         'titres et plan divergent')
        print(f"    G-1 {len(au_plan)} au plan · "
              f"{len(R.FIGURES_ECARTEES)} ecartees · intersection vide, "
              f"titres et sources complets")


if __name__ == '__main__':
    unittest.main()
