r"""ML-1..ML-6 — LA VALIDATION « ML » PORTE SUR UN MODÈLE ML, ET UNE
ABSENCE DE MESURE NE CERTIFIE PAS.

Constats `A4-2` et `A4-3` du 2e audit de tarification, reproduits au
site le 14/09/2026 et fermés par ce lot. Ils partagent une cause : *un
statut réglementaire lisait autre chose que ce que son titre annonce.*

`A4-2` — `overfit_alerte` vaut ``None`` quand la stabilité n'a pas pu
être mesurée, et ``not None`` est vrai. Mesuré, même portefeuille, même
référence A3 :

    ==========================  ======
    overfit_ratio = 1.40        AMBRE     mesuré, mauvais
    overfit_ratio = 1.02        VERT      mesuré, bon
    overfit_ratio = None        VERT      NON ÉVALUABLE
    ==========================  ======

*Ne pas mesurer était strictement plus favorable que mesurer mauvais, et
exactement aussi favorable que mesurer bon.*

`A4-3` — `_valider_modele_ml` lisait `classement[0]`, et
`_classer_modeles` ajoute la référence GLM d'A3 à ce même tableau avant
de trier par Gini décroissant. Dès que le GLM discrimine mieux que tous
les ML — le cas qu'A4 nomme « aucun ML n'améliore le GLM » — le bloc
« Validation complète des hypothèses ML » certifiait le GLM sous ce
titre. Mesuré, GLM 0,31 contre gbm 0,12 : H1 rendait le ratio **1,0968**
(la stabilité du GLM) et son conseil disait « Le modèle GLM Poisson
(référence A3) généralise bien ».

⚠️⚠️ CE SCEAU MESURE UN COMPORTEMENT. Il appelle les deux méthodes avec
des classements fabriqués — l'entrée de ces méthodes EST un classement —
et lit ce qu'elles RENDENT. Aucun texte de source n'est cherché, sauf en
`ML-6`, qui est explicitement un contrôle d'assiette et le dit.

⚠️ `ML-2` ET `ML-5` PORTENT LE SECOND SENS, et sans eux ce lot serait
ininstruit : un correctif qui rendrait AMBRE *partout*, ou qui viderait
le classement, fermerait les deux constats en cassant tout le reste.
"""
import ast
import os
import pathlib
import sys
import unittest

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../')))

from direction_non_vie.tarification.a4_ml.agent import AgentA4ML

_A4 = pathlib.Path(AgentA4ML.__module__.replace('.', os.sep))
_SOURCE = (pathlib.Path(__file__).parent / 'a4_ml' / 'agent.py')

#: ce qu'A3 rend, dans la forme que `glm_de_reference` sait lire.
#: ⚠️ SANS `_cible_run`, `_reference_glm` rend `(None, None)` et la garde
#: `if gini_glm is None: return 'AMBRE'` sort AVANT la ligne mesurée :
#: les trois cas rendraient AMBRE et ce sceau n'attesterait rien. Un
#: témoin le vérifie dans `ML-1`.
_CIBLE = 'nb_sinistres'
_RESULT_A3 = {
    'success': True,
    'metriques': {'poisson': {'gini': 0.10, 'gini_train': 0.11,
                              'overfit_ratio': 1.10, 'rmse_test': 0.30,
                              'cible': _CIBLE}},
}
_MONITORING = {'psi': None, 'psi_details': {}, 'gini_actuel': None,
               'gini_reference': 0.10, 'statut': 'AMBRE'}


def _agent():
    a = AgentA4ML.__new__(AgentA4ML)
    a.modeles = {}
    a.metriques = {}
    a._cible_run = _CIBLE
    return a


def _ligne(nom, gini, ratio, alerte, famille='ML'):
    return {'modele': nom, 'famille': famille, 'gini_test': gini,
            'gini_train': None if ratio is None else gini * ratio,
            'overfit_ratio': ratio, 'overfit_ic': None,
            'rmse_test': 0.20, 'mae_test': 0.10,
            'overfit_alerte': alerte, 'recommandation': 'mesure'}


class ML1_UneStabiliteNonMesureeNeCertifiePas(unittest.TestCase):
    """ML-1 — `A4-2` : non évaluable ne vaut pas « pas de sur-apprentissage »."""

    def test_ML1_SCEAU_overfit_alerte_None_ne_rend_jamais_VERT(self):
        agent = _agent()
        #: ⚠️ TÉMOIN D'ABORD : si la référence GLM ne se résout pas, la
        #: garde amont sort et les trois cas rendent AMBRE — le sceau
        #: attesterait sans rien mesurer.
        self.assertIsNotNone(
            (agent._reference_glm(_RESULT_A3)[1] or {}).get('gini'),
            "le Gini de la référence A3 ne se résout pas : la garde amont "
            "sort avant la ligne mesurée, et ce contrôle n'atteste rien")
        statut = agent._calculer_statut_rag(
            [_ligne('gbm', 0.31, None, None)], _RESULT_A3, shap_absent=False)
        self.assertNotEqual(
            statut, 'VERT',
            "une stabilité NON ÉVALUABLE rend un statut réglementaire VERT : "
            "ne pas mesurer devient exactement aussi favorable que mesurer "
            "bon, et strictement plus favorable que mesurer mauvais")
        print(f"    ML-1 SCEAU : stabilité non mesurée -> {statut}")


class ML2_LesCasMesuresNeBougentPas(unittest.TestCase):
    """ML-2 — le SECOND SENS : plafonner n'est pas dégrader."""

    def test_ML2_le_cas_mesure_BON_reste_VERT_et_le_MAUVAIS_AMBRE(self):
        agent = _agent()
        for ratio, alerte, attendu in ((1.02, False, 'VERT'),
                                       (1.40, True, 'AMBRE')):
            with self.subTest(ratio=ratio):
                statut = agent._calculer_statut_rag(
                    [_ligne('gbm', 0.31, ratio, alerte)], _RESULT_A3,
                    shap_absent=False)
                self.assertEqual(
                    statut, attendu,
                    f"overfit_ratio={ratio} (MESURÉ) rend {statut} au lieu de "
                    f"{attendu} : le correctif a DÉGRADÉ un cas mesuré au "
                    f"lieu de PLAFONNER un cas non mesuré")
        print("    ML-2 second sens : mesuré-bon VERT, mesuré-mauvais AMBRE")


class ML3_LesHypothesesMLPortentSurUnML(unittest.TestCase):
    """ML-3 — `A4-3` : jamais sur la ligne de référence du GLM."""

    def test_ML3_SCEAU_H1_et_H3_ne_portent_jamais_sur_une_ligne_GLM(self):
        #: le GLM discrimine MIEUX que tous les ML — le cas exact qu'A4
        #: nomme « aucun ML n'améliore le GLM »
        classement = [
            _ligne('GLM Poisson (référence A3)', 0.31, 1.0968, False, 'GLM'),
            _ligne('gbm', 0.12, 1.05, False),
            _ligne('rf', 0.09, 1.11, False),
        ]
        val = _agent()._valider_modele_ml(classement, _MONITORING,
                                          n_train=2400, n_test=600)
        evalue = val.get('modele_evalue')
        self.assertIsNotNone(
            evalue, "`modele_evalue` est absent : un lecteur ne peut pas "
                    "savoir sur quel modèle portent H1, H3 et H4 — c'est "
                    "ce qui rendait le défaut indétectable")
        self.assertNotIn(
            'GLM', str(evalue).upper(),
            f"les « hypothèses ML » portent sur {evalue!r} : le bloc "
            f"certifie le GLM sous le titre « Validation complète des "
            f"hypothèses ML », et A6 lit ce dictionnaire")
        self.assertAlmostEqual(
            val['h3_gini']['gini'], 0.12, places=6,
            msg="H3 publie le Gini du GLM, pas celui du meilleur ML")
        self.assertNotIn('GLM', str(val['h1_overfitting']['conseil']).upper())
        print(f"    ML-3 SCEAU : hypothèses ML sur {evalue!r}, "
              f"H3 gini={val['h3_gini']['gini']}")

    def test_ML3b_le_fait_metier_GLM_EN_TETE_est_PUBLIE(self):
        """⚠️ L'information ne se perd pas : que le GLM batte tous les ML
        est une conclusion d'actuaire, pas un détail de tri."""
        classement = [
            _ligne('GLM Poisson (référence A3)', 0.31, 1.0968, False, 'GLM'),
            _ligne('gbm', 0.12, 1.05, False),
        ]
        val = _agent()._valider_modele_ml(classement, _MONITORING)
        self.assertTrue(
            val.get('glm_en_tete'),
            "le GLM domine le classement et rien ne le dit dans le "
            "dictionnaire que lit A6")
        self.assertIn('GLM', val['conclusion'].upper())
        print("    ML-3b `glm_en_tete` publié, et la conclusion le dit")


class ML5_UnClassementSansGLMNeBougePas(unittest.TestCase):
    """ML-5 — le SECOND SENS d'`A4-3` : le filtre ne touche que le GLM."""

    def test_ML5_sans_ligne_GLM_le_resultat_est_identique(self):
        sans = [_ligne('gbm', 0.12, 1.05, False),
                _ligne('rf', 0.09, 1.11, False)]
        avec = [_ligne('GLM Poisson (référence A3)', 0.31, 1.0968,
                       False, 'GLM')] + sans
        r_sans = _agent()._valider_modele_ml(sans, _MONITORING)
        r_avec = _agent()._valider_modele_ml(avec, _MONITORING)
        for cle in ('h1_overfitting', 'h3_gini'):
            self.assertEqual(
                r_sans[cle], r_avec[cle],
                f"{cle} diffère selon que la ligne de RÉFÉRENCE du GLM est "
                f"présente ou non : le filtre ne fait pas son office, ou il "
                f"en fait trop")
        self.assertFalse(r_sans['glm_en_tete'])
        self.assertEqual(r_sans['modele_evalue'], 'gbm')
        print("    ML-5 second sens : dossier sans GLM, résultat identique")


class ML6_UneSeuleRegleDeFiltre(unittest.TestCase):
    """ML-6 — l'ASSIETTE : deux règles divergeraient."""

    def test_ML6_les_deux_sites_ecartent_le_GLM_DE_LA_MEME_MANIERE(self):
        """⚠️ CONTRÔLE D'ASSIETTE, ET IL LIT LA SOURCE — c'est assumé.
        La question n'est pas ce que le code REND (les autres contrôles
        le mesurent) mais s'il existe UNE règle ou DEUX : deux
        compréhensions de « écarter le GLM » divergeraient au premier
        renommage, et le dépôt ne s'en apercevrait pas."""
        arbre = ast.parse(_SOURCE.read_text(encoding='utf-8'))
        regles = {}
        for n in ast.walk(arbre):
            if not isinstance(n, ast.FunctionDef):
                continue
            if n.name not in ('_calculer_statut_rag', '_valider_modele_ml'):
                continue
            for x in ast.walk(n):
                if (isinstance(x, ast.Compare)
                        and any(isinstance(o, ast.NotIn) for o in x.ops)
                        and isinstance(x.left, ast.Constant)
                        and x.left.value == 'GLM'):
                    regles[n.name] = ast.unparse(x.left)
        self.assertEqual(
            sorted(regles), ['_calculer_statut_rag', '_valider_modele_ml'],
            f"un des deux sites n'écarte plus le GLM par la même règle : "
            f"{regles}. `_calculer_statut_rag` portait déjà le bon geste ; "
            f"la règle d'`A4-3` en est REPRISE, pas inventée")
        print(f"    ML-6 assiette : {len(regles)} site(s), une seule règle "
              f"`'GLM' not in ...`")


if __name__ == '__main__':
    # ⚠️ LE BLOC EN FIN DE FICHIER, DERRIÈRE TOUTES LES DÉFINITIONS —
    # constat `COLLECTE-1`, sceau `GD-1..GD-4`.
    unittest.main(verbosity=2)
