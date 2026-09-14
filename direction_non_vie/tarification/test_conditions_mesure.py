"""
==============================================================================
  LOT D-3a + D-4 -- SUR QUELLE DECOUPE LE CLASSEMENT A-T-IL ETE ETABLI ?
==============================================================================

⚠️⚠️ LE PREMIER DU CLASSEMENT DEVIENT LE MODELE DE PRODUCTION, et le document
signe ne disait pas sur quelles lignes son score avait ete mesure.

MESURE DU 08/09/2026 -- POURQUOI CA COMPTE
  Les memes six candidats, notes sur deux decoupes 80/20 des MEMES donnees :
  recouvrement des holdouts 19,2 % a 22,5 %, Gini jusqu'a x3,8 (`catboost`
  0,1725 contre 0,0459), et 3 a 5 modeles sur 6 CHANGENT DE RANG. *Le
  vainqueur a tenu sur les deux tirages ; l'ordre en dessous, non.*

DEUX REGIMES DE DECOUPE COEXISTENT, ET UN SEUL EST DECLARE
  ALPHA -- A3/A4/A5, donc le classement : temporelle si colonne, sinon
    aleatoire graine 42. AUCUN PLAN NE LA DECLARE.
  BETA  -- `pipeline_complet.validation` et la comparaison de prix : la
    `decoupe_validation` du plan. Mesure : 0 des 20 plans en declare une.

⚠️⚠️ CE LOT NE CHANGE PAS ALPHA, IL LE DIT. Le rendre refusable ferait cesser
la selection de modele sur 20/20 plans -- c'est `D-3b`, et il attend une
mesure de son effet sur le PRIX. *On publie d'abord ce qui est.*

⚠️ D-4 SE PUBLIE TOUT SEUL. A5 reserve une part de validation pour son arret
anticipe : mesure par execution, il apprend sur 1 360 lignes quand A3 et A4
en ont 1 600 -- 68 % contre 80 %, pour un holdout IDENTIQUE (400/400 lignes
communes). Comme chaque agent declare son `n_train` REEL, l'asymetrie
apparait sans qu'aucun chiffre soit ecrit en dur.

⚠️⚠️ CHAQUE AGENT DECLARE LA SIENNE, LA OU LA DECOUPE A LIEU. A4 avertit
lui-meme, au-dessus de son propre diagnostic, que les redériver ailleurs
<< reviendrait a recopier le mecanisme qu'on surveille >>.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys
import unittest

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from core.conditions_mesure import (
    REGLE_ALEATOIRE,
    REGLE_TEMPORELLE,
    ConditionsDeMesure,
    phrase_conditions_de_mesure,
)
from direction_non_vie.tarification.services.rapport_modeles_tarif import (
    TITRE_CONDITIONS,
    _bloc_conditions_html,
)

#: ⚠️ LE MECANISME VIT CHEZ `BP-4`, QUI L'A PAYE LE PREMIER. Deux
#: controles ont besoin de suivre une variable jusqu'a sa definition ;
#: en ecrire deux versions les ferait diverger au premier ajout. Meme
#: patron que `test_derivations` important ses fixtures de
#: `test_plan_invariants`.
from direction_non_vie.tarification.test_bloc_prix_assiette import (
    source_aplatie,
)

_AGENTS = {
    'A3': 'direction_non_vie/tarification/a3_glm/agent.py',
    'A4': 'direction_non_vie/tarification/a4_ml/agent.py',
    'A5': 'direction_non_vie/tarification/a5_deep_learning/agent.py',
}


def _alpha():
    """Les trois conditions telles que le depot les produit reellement.

    ⚠️ Les chiffres viennent de la MESURE PAR EXECUTION du 08/09/2026 sur
    2 000 lignes : A3 et A4 apprennent sur 1 600, A5 sur 1 360 avec 240 lignes
    de validation, et les trois mesurent sur LE MEME holdout de 400.
    """
    return [ConditionsDeMesure('A3', REGLE_ALEATOIRE, 1600, 400),
            ConditionsDeMesure('A4', REGLE_ALEATOIRE, 1600, 400),
            ConditionsDeMesure('A5', REGLE_ALEATOIRE, 1360, 400,
                               n_validation=240)]


class TestLaDeclarationDesConditions(unittest.TestCase):

    def test_CM1_une_decoupe_TEMPORELLE_sans_colonne_est_refusee(self):
        """⚠️⚠️ LES DEUX SENS. Une decoupe qui se dit temporelle sans nommer sa
        colonne n'est pas verifiable ; une decoupe aleatoire qui en nomme une
        se contredit. *Un champ libre aurait laisse passer les deux.*"""
        with self.assertRaises(ValueError) as ctx:
            ConditionsDeMesure('A3', REGLE_TEMPORELLE, 100, 20)
        self.assertIn('colonne', str(ctx.exception).lower())
        with self.assertRaises(ValueError):
            ConditionsDeMesure('A3', REGLE_ALEATOIRE, 100, 20, colonne='annee')
        # et le miroir : les deux formes correctes passent
        self.assertEqual(
            ConditionsDeMesure('A3', REGLE_TEMPORELLE, 100, 20,
                               colonne='annee').colonne, 'annee')
        self.assertIsNone(
            ConditionsDeMesure('A3', REGLE_ALEATOIRE, 100, 20).colonne)
        print("    CM-1 temporelle sans colonne REFUSEE, aleatoire avec "
              "colonne REFUSEE, les deux formes justes ADMISES")

    def test_CM2_une_part_vide_n_est_pas_une_decoupe(self):
        """⚠️ Un holdout de zero ligne se lirait comme une mesure."""
        for train, test in ((0, 20), (100, 0), (-1, 20)):
            with self.assertRaises(ValueError):
                ConditionsDeMesure('A4', REGLE_ALEATOIRE, train, test)
        with self.assertRaises(ValueError):
            ConditionsDeMesure('A5', REGLE_ALEATOIRE, 100, 20,
                               n_validation=-1)
        print("    CM-2 une part vide est refusee")

    def test_CM2b_LA_PART_DE_VALIDATION_entre_dans_le_denominateur(self):
        """⚠️⚠️ MON PROPRE CODE ETAIT FAUX ICI, ET C'EST CE CONTROLE QUI L'A
        TROUVE. La premiere version divisait par `train + test` seulement : A5
        sortait a 77,3 % au lieu de 68 %, soit un ecart affiche de 2,7 points
        la ou il en vaut 12. *La part de validation n'est ni du train ni du
        holdout ; l'omettre du denominateur retrecit precisement l'asymetrie
        que ce module existe pour publier.*"""
        a5 = ConditionsDeMesure('A5', REGLE_ALEATOIRE, 1360, 400,
                                n_validation=240)
        self.assertEqual(a5.n_total, 2000)
        self.assertAlmostEqual(a5.part_apprentissage, 0.68, places=4)
        sans = ConditionsDeMesure('A4', REGLE_ALEATOIRE, 1600, 400)
        self.assertEqual(sans.n_total, 2000)
        self.assertAlmostEqual(sans.part_apprentissage, 0.80, places=4)
        print("    CM-2b la part de validation compte : A5 68,00 %, "
              "A4 80,00 %")

    def test_CM3_LE_SCEAU_les_TROIS_agents_declarent_leurs_conditions(self):
        """⚠️⚠️ LE CORRECTIF DOIT ATTEINDRE LES TROIS SOURCES. Un agent qui ne
        declare pas laisse un score au classement sans dire d'ou il vient --
        et le bloc publierait une liste incomplete sans le signaler. Releve
        PAR AST : construction ET remontee au resultat."""
        for agent, relatif in _AGENTS.items():
            source = (pathlib.Path(_RACINE) / relatif).read_text(
                encoding='utf-8')
            arbre = ast.parse(source)
            construit = any(
                isinstance(n, ast.Call)
                and getattr(n.func, 'id', None) == 'ConditionsDeMesure'
                for n in ast.walk(arbre))
            self.assertTrue(construit,
                            f"{agent} ne construit aucune ConditionsDeMesure")
            remonte = any(
                isinstance(n, ast.Constant) and n.value == 'conditions_mesure'
                for n in ast.walk(arbre))
            self.assertTrue(remonte,
                            f"{agent} ne remonte pas ses conditions au "
                            f"resultat : elles resteraient au journal")
        print(f"    CM-3 SCEAU : les {len(_AGENTS)} agents declarent ET "
              f"remontent leurs conditions")

    def test_CM4_A6_RASSEMBLE_les_trois_et_les_transmet_releve_par_AST(self):
        """⚠️⚠️ A6 RASSEMBLE, IL NE FABRIQUE PAS -- meme doctrine que pour le
        tarif, la relecture actuarielle et le rapport qualite. Redériver la
        decoupe ici recopierait le mecanisme surveille."""
        a6 = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
              / 'a6_comparaison' / 'agent.py').read_text(encoding='utf-8')
        arbre = ast.parse(a6)
        # ⚠️⚠️ L'ASSIETTE EST L'ARGUMENT, PAS L'APPEL ENTIER. Ce controle a
        # d'abord cherche les trois agents dans la source de TOUT l'appel :
        # or le meme appel porte deja `result_a5=result_a5`, si bien qu'un
        # plant retirant A5 de la COLLECTE restait VERT (sceau du 09/09,
        # plant X4). *Un controle dont l'assiette deborde de ce qu'il surveille
        # atteste sans surveiller.*
        valeurs = [k.value for n in ast.walk(arbre)
                   if isinstance(n, ast.Call)
                   for k in n.keywords if k.arg == 'conditions_mesure']
        self.assertTrue(valeurs, "A6 ne transmet pas les conditions")
        # ⚠️⚠️ LES VARIABLES LOCALES SONT SUBSTITUÉES, ET C'EST UNE
        # RÉPARATION. Ce contrôle lisait `ast.unparse(v)` tel quel : le
        # jour ou A6 a extrait la collecte dans `_conditions_pub` — pour
        # la passer au document ET la relayer a ses appelants, une
        # definition au lieu de deux — la source est devenue
        # `_conditions_pub` et les trois agents ont disparu du relevé.
        # *Le controle est tombe sur un refactor qui ne changeait RIEN au
        # comportement.* Il exige toujours la meme chose ; il sait
        # desormais la suivre a travers une variable.
        #   ⚠️ L'ASSIETTE NE S'ELARGIT PAS POUR AUTANT : on ne substitue
        # que ce que l'argument REFERENCE, jamais l'appel entier — la
        # lecon du plant X4 rappelee juste au-dessus.
        source = ' '.join(source_aplatie(v, arbre) for v in valeurs)
        for agent in ('result_a3', 'result_a4', 'result_a5'):
            self.assertIn(agent, source,
                          f"A6 oublie {agent} dans la COLLECTE : le bloc "
                          f"publierait une liste incomplete sans le dire")
        # ⚠️ PAR AST, PAS AU TEXTE : un relevé au texte manquerait
        # `module.ConditionsDeMesure(...)` et sur-compterait une mention en
        # commentaire. C'est la 8e forme de `releve-symbole-vs-prose`.
        fabrique = [
            n for n in ast.walk(arbre) if isinstance(n, ast.Call)
            and 'ConditionsDeMesure' in (getattr(n.func, 'id', ''),
                                         getattr(n.func, 'attr', ''))]
        self.assertEqual(fabrique, [],
                         "A6 FABRIQUE des conditions au lieu de les "
                         "rassembler : il recopierait le mecanisme surveille")
        print("    CM-4 A6 rassemble les TROIS et les transmet, sans fabriquer")


class TestCeQueLaPhrasePublie(unittest.TestCase):

    def test_CM5_LE_SCEAU_la_phrase_dit_que_la_decoupe_N_EST_PAS_declaree(self):
        """⚠️⚠️ C'EST LE FAIT QUI MANQUAIT AU DOCUMENT. Le classement decide du
        modele de production sur une decoupe qu'aucun plan ne declare."""
        phrase = phrase_conditions_de_mesure(_alpha())
        self.assertIn('DECLAREE DANS AUCUN PLAN', phrase.upper())
        self.assertIn('decoupe_validation', phrase)
        print("    CM-5 SCEAU : la phrase dit que la decoupe n'est declaree "
              "dans aucun plan")

    def test_CM6_LE_MIROIR_une_decoupe_DECLAREE_ne_declenche_pas_l_alerte(self):
        """⚠️ Sans ce sens, une phrase qui alerterait TOUJOURS satisferait
        CM-5 -- et l'alerte ne vaudrait plus rien le jour ou `D-3b` fera
        suivre la decoupe du plan."""
        declarees = [ConditionsDeMesure(c.agent, c.regle, c.n_train, c.n_test,
                                        colonne=c.colonne,
                                        declaree_au_plan=True)
                     for c in _alpha()]
        phrase = phrase_conditions_de_mesure(declarees)
        self.assertNotIn('AUCUN PLAN', phrase.upper())
        print("    CM-6 miroir : declaree au plan -> plus d'alerte")

    def test_CM7_D4_LE_SCEAU_l_asymetrie_d_apprentissage_est_DITE(self):
        """⚠️⚠️ A5 APPREND SUR 68 %, A3 ET A4 SUR 80 %, et A6 range leurs Gini
        cote a cote. Mesure par execution : 1 360 lignes contre 1 600, pour un
        holdout IDENTIQUE (400/400 communes). *Aucun chiffre en dur ici : la
        phrase le derive des `n_train` declares.*"""
        phrase = phrase_conditions_de_mesure(_alpha())
        self.assertIn("ASSIETTES D'APPRENTISSAGE DIFFERENT", phrase.upper())
        self.assertIn('68.0 %', phrase)
        self.assertIn('80.0 %', phrase)
        print("    CM-7 SCEAU D-4 : 68,0 % contre 80,0 %, l'asymetrie est dite")

    def test_CM8_LE_MIROIR_des_assiettes_EGALES_ne_declenchent_rien(self):
        """⚠️ Sans ce sens, une alerte permanente satisferait CM-7."""
        egales = [ConditionsDeMesure(a, REGLE_ALEATOIRE, 1600, 400)
                  for a in ('A3', 'A4', 'A5')]
        self.assertNotIn("ASSIETTES D'APPRENTISSAGE DIFFERENT",
                         phrase_conditions_de_mesure(egales).upper())
        print("    CM-8 miroir : assiettes egales -> aucune alerte")

    def test_CM9_SANS_condition_remontee_la_phrase_NE_SE_TAIT_PAS(self):
        """⚠️⚠️ UN SILENCE SE LIRAIT << RIEN A SIGNALER >>. C'est la doctrine
        de la decision d'actuaire et du refus de comparaison, appliquee ici."""
        for vide in (None, [], [None, None]):
            phrase = phrase_conditions_de_mesure(vide)
            self.assertIn('aucune', phrase.lower())
            self.assertIn('CONDITIONS DE MESURE', phrase)
        print("    CM-9 sans condition : la phrase le DIT")

    def test_CM10_la_regle_et_la_colonne_sont_NOMMEES(self):
        """⚠️ << Temporelle >> sans la colonne ne se verifie pas."""
        phrase = phrase_conditions_de_mesure(
            [ConditionsDeMesure('A3', REGLE_TEMPORELLE, 1600, 400,
                                colonne='annee_souscription')])
        self.assertIn('annee_souscription', phrase)
        self.assertIn('TEMPORELLE', phrase.upper())
        self.assertIn('1600', phrase)
        print("    CM-10 la regle, la colonne et les tailles sont nommees")


class TestLeBlocPublie(unittest.TestCase):

    def test_CM11_le_bloc_HTML_porte_la_phrase_et_le_detail(self):
        html = _bloc_conditions_html(_alpha())
        self.assertIn(TITRE_CONDITIONS, html)
        self.assertIn('AUCUN PLAN', html.upper())
        for agent in ('A3', 'A4', 'A5'):
            self.assertIn(f'<td>{agent}</td>', html)
        self.assertIn('1360', html)
        self.assertIn('68.0 %', html)
        print("    CM-11 le bloc HTML porte la phrase et le detail par agent")

    def test_CM12_LES_DEUX_FORMATS_publient_les_conditions_par_AST(self):
        """⚠️⚠️ LA CINQUIEME ASYMETRIE QUE CE DEPOT AURAIT PAYEE. Le mapping,
        l'elasticite, la qualite des donnees, les reserves d'A6 et la
        comparaison de prix avaient chacun atteint UN SEUL format."""
        chemin = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
                  / 'services' / 'rapport_modeles_tarif.py')
        texte = chemin.read_text(encoding='utf-8')
        arbre = ast.parse(texte)
        html = mots = False
        for fonction in ast.walk(arbre):
            if not isinstance(fonction, ast.FunctionDef):
                continue
            src = ast.get_source_segment(texte, fonction) or ''
            if fonction.name == 'export_html':
                html = '_bloc_conditions_html' in src
            if fonction.name == 'export_word':
                mots = 'TITRE_CONDITIONS' in src
        self.assertTrue(html, "le HTML ne publie pas les conditions")
        self.assertTrue(mots, "le Word ne publie pas les conditions")
        print("    CM-12 les deux formats publient les conditions")

    def test_CM13_le_socle_ne_remonte_PAS_vers_une_direction(self):
        socle = (pathlib.Path(_RACINE) / 'core'
                 / 'conditions_mesure.py').read_text(encoding='utf-8')
        remontees = [
            n.module for n in ast.walk(ast.parse(socle))
            if isinstance(n, ast.ImportFrom) and n.module
            and n.module.startswith('direction_')]
        self.assertEqual(remontees, [], f"le socle importe : {remontees}")
        print("    CM-13 le socle n'importe aucune direction")


if __name__ == '__main__':
    unittest.main(verbosity=2)
