"""Controles positifs — lot 4.8 : trois figures supprimees, une question publiee.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
UNE SEULE PROPRIETE : *on ne supprime pas une question en supprimant une
figure fausse — on publie la question correctement.*

═══ LES TROIS SUPPRESSIONS ═══

`a3/C5` (`lorenz_glm`), `a4/C5` (`lorenz`), `a6/C3` (`scores_profils`) sont
supprimees du code, entrees d'ecart comprises. Ce n'etaient pas des doublons
inoffensifs, c'etaient des doublons FAUX :

  · la Lorenz etait RECONSTRUITE du seul scalaire Gini,
    `t ** (1/(1+gini*2))` -- deux portefeuilles differents de meme Gini
    donnaient la meme courbe au pixel pres. La figure PUBLIEE, elle, recoit
    des points mesures (`np.cumsum(y_sort)/np.sum(y_sort)`) ;
  · `scores_profils` affichait 0,56 la ou le score reel du meme modele
    valait 0,9001, parce qu'elle inventait une seconde formule.

⚠️⚠️ LA SUPPRESSION S'EST FAITE PAR SITE, JAMAIS PAR NOM. `a6:1824` definit
aussi une cle `'lorenz'` -- mais c'est le dictionnaire des points REELS qui
alimente `chart_lorenz_gini`, la figure publiee. Un test plante cet homonyme.

═══ CE QUI EST PUBLIE A LA PLACE ═══

⚠️⚠️ SUPPRIMER `scores_profils` AURAIT FAIT DISPARAITRE UNE QUESTION AVEC UN
DEFAUT. Elle etait la seule a demander : << le classement changerait-il sous
un autre profil de ponderation ? >>. Mesure sur quatre portefeuilles, en
recalculant avec `_calculer_scores_multicriteres`, LA FORMULE QUI DECIDE :

    seed  3 cout  vainqueurs=2  ['DL_TABNET', 'GLM_GAMMA']
    seed 11 cout  vainqueurs=2  ['GLM_GAMMA', 'ML_LINEAIRE_REGULARISE']
    seed 21 cout  vainqueurs=1  ['DL_TABNET']
    seed 42 cout  vainqueurs=2  ['DL_TABNET', 'ML_XGBOOST']
    -> 3 bascules de vainqueur sur 8 cas ; marges #1-#2 a 0,008 · 0,016 · 0,021

⚠️ ET LA TRACE EXISTANTE NE REPONDAIT PAS A CETTE QUESTION.
`gouvernance_validee` se reduit a `bool(str(profil_valide_par or '').strip())`
-- elle verifie qu'un NOM NON VIDE est present. Elle dit QUI a assume le
choix, jamais CE QUE le choix a change. *Le profil est un levier sur le prix.*

⚠️ C'EST UN TABLEAU, PAS UNE FIGURE, ET C'EST DELIBERE. Quatre profils, quatre
lignes : un graphique a quatre points serait un << tableau deguise >> -- le
motif meme par lequel cet audit a ecarte les quatre scorecards.

⚠️⚠️ ET LA COPIE PROFONDE N'EST PAS UNE PRECAUTION.
`_calculer_scores_multicriteres` ECRIT `score_global` dans les dictionnaires
recus. Sans copie, quatre appels ecraseraient le classement publie avec les
scores du dernier profil -- UN PRIX DEPLACE. Un test l'epingle.
"""

from __future__ import annotations

import ast
import copy
import io
import pathlib
import unittest
import zipfile

from direction_non_vie.tarification.a6_comparaison.agent import (
    PROFILS_PONDERATION,
    AgentA6Comparaison,
    gouvernance_validee,
)
from direction_non_vie.tarification.services import rapport_modeles_tarif as R

_RACINE = pathlib.Path(__file__).resolve().parent

#: Un classement minimal, aux composantes assez contrastees pour que le
#: profil PUISSE faire basculer le vainqueur.
_CLASSEMENT = [
    {'modele': 'DL_TABNET', 'gini_test': 0.30, 'rmse_test': 900.0,
     'overfit_ratio': 1.40, 'interpretabilite': 0.30, 'famille': 'Deep Learning'},
    {'modele': 'GLM_GAMMA', 'gini_test': 0.20, 'rmse_test': 800.0,
     'overfit_ratio': 1.00, 'interpretabilite': 0.95, 'famille': 'GLM'},
    {'modele': 'ML_XGBOOST', 'gini_test': 0.24, 'rmse_test': 850.0,
     'overfit_ratio': 1.20, 'interpretabilite': 0.55, 'famille': 'ML'},
]


def _agent():
    return AgentA6Comparaison(models_path='/tmp', audit_path='/tmp',
                              verbose=False)


class TestLesTroisFiguresOntDisparu(unittest.TestCase):
    """Supprimees du code ET du catalogue, dans le meme geste."""

    def test_le_code_qui_les_produisait_N_EXISTE_PLUS(self):
        """⚠️⚠️ LE TEST QUI FERME LES TROIS CONSTATS — relevé par AST.

        On ne cherche pas une chaîne dans un commentaire : on lit les
        affectations réelles `graphiques[...] = ...` de chaque agent.
        """
        disparues = {'lorenz_glm': 'a3_glm', 'lorenz': 'a4_ml',
                     'scores_profils': 'a6_comparaison'}
        for cle, agent in disparues.items():
            chemin = _RACINE / agent / 'agent.py'
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            produites = set()
            for n in ast.walk(arbre):
                if (isinstance(n, ast.Subscript)
                        and isinstance(n.ctx, ast.Store)
                        and isinstance(n.value, ast.Name)
                        and n.value.id.startswith('graphiques')
                        and isinstance(n.slice, ast.Constant)):
                    produites.add(str(n.slice.value))
            with self.subTest(figure=cle):
                self.assertNotIn(cle, produites,
                                 f'{agent} produit encore « {cle} »')
        print("    S-1 les 3 figures ne sont plus produites (AST, "
              "affectations reelles)")

    def test_la_formule_ANALYTIQUE_a_disparu_du_depot(self):
        """⚠️ Supprimer la figure sans la formule laisserait le vrai défaut.

        `t ** (1/(1+gini*2))` reconstruisait une courbe du seul scalaire Gini.
        Balayage de TOUT le dépôt, pas des seuls agents.

        ⚠️ ASSIETTE DÉCLARÉE : le CODE DE PRODUCTION seulement. Les fichiers
        `test_*.py` sont exclus — **celui-ci cite la formule** pour la
        documenter, et sans cette borne la sonde se trouvait elle-même
        (4 faux positifs à la première exécution). *Une sonde qui lève sur sa
        propre documentation accuse le code à tort.* La contrepartie est
        déclarée : une réintroduction dans un TEST échapperait à ce contrôle.
        """
        racine = _RACINE.parent.parent
        sites = []
        for p in racine.rglob('*.py'):
            if ('.venv' in str(p) or 'audit_2026_08' in str(p)
                    or p.name.startswith('test_')):
                continue
            for i, l in enumerate(p.read_text(encoding='utf-8',
                                              errors='replace').split('\n'), 1):
                if (('1 + gini * 2' in l or '1+gini*2' in l.replace(' ', ''))
                        and not l.strip().startswith('#')):
                    sites.append(f'{p.name}:{i}')
        self.assertEqual(sites, [],
                         f'la formule analytique subsiste : {sites}')
        print("    S-2 la formule `t ** (1/(1+gini*2))` a disparu du depot")

    def test_les_entrees_d_ecart_sont_parties_AVEC_les_figures(self):
        """⚠️ Une entrée qui survit à sa figure est une justification sans
        objet — et le contrôle du catalogue la signale."""
        au_plan = {c for _, cles in R.PLAN_FIGURES for c in cles}
        for cle in ('lorenz', 'lorenz_glm', 'scores_profils'):
            with self.subTest(figure=cle):
                self.assertNotIn(cle, R.FIGURES_ECARTEES)
                self.assertNotIn(cle, au_plan)
                self.assertNotIn(cle, R.SOURCES_FIGURES)
        print(f"    S-3 0 entree residuelle · FIGURES_ECARTEES : "
              f"{len(R.FIGURES_ECARTEES)}")

    def test_L_HOMONYME_lorenz_d_A6_EST_INTACT(self):
        """⚠️⚠️ LA PRÉCAUTION QUI A DÉCIDÉ LA MÉTHODE DE SUPPRESSION.

        `a6` définit aussi une clé `'lorenz'` — mais c'est le dictionnaire des
        points RÉELS (`np.cumsum(y_sort)/np.sum(y_sort)`) qui alimente
        `chart_lorenz_gini`, LA FIGURE PUBLIÉE. Supprimer par le nom aurait
        détruit la bonne courbe. *On supprime par SITE, jamais par nom.*
        """
        src = (_RACINE / 'a6_comparaison' / 'agent.py').read_text(
            encoding='utf-8')
        self.assertIn("'lorenz': {", src,
                      "le dictionnaire des points MESURES a ete detruit")
        self.assertIn('np.cumsum(y_sort)', src,
                      'le cumul reel a disparu')
        self.assertIn('chart_lorenz_gini', src,
                      'la figure publiee ne recoit plus ses points')
        print("    S-4 l'homonyme `courbes['lorenz']` et son cumul reel sont "
              "intacts")


class TestLaSensibiliteEstPubliee(unittest.TestCase):
    """La question de `a6/C3` survit a sa figure, correctement calculee."""

    def test_la_table_couvre_LES_QUATRE_profils(self):
        """⚠️ Un sous-ensemble laisserait croire que les autres n'existent pas."""
        table = _agent()._sensibilite_profils(_CLASSEMENT, 'equilibre')
        self.assertEqual([l['profil'] for l in table],
                         list(PROFILS_PONDERATION))
        self.assertEqual(sum(1 for l in table if l['actif']), 1,
                         'le profil actif doit etre marque une fois')
        print(f"    S-5 {len(table)} profils, le profil actif marque une fois")

    def test_elle_utilise_LA_FORMULE_QUI_DECIDE(self):
        """⚠️⚠️ CE QUI MANQUAIT A `scores_profils` : elle en inventait une
        autre (Gini brut, `1/overfit`, `1 - rmse/400`) et publiait 0,56 la ou
        le score reel valait 0,9001.

        On recalcule ici avec `_calculer_scores_multicriteres` et on exige
        l'egalite EXACTE, pas la ressemblance.
        """
        ag = _agent()
        table = ag._sensibilite_profils(_CLASSEMENT, 'equilibre')
        for ligne in table:
            attendu = ag._calculer_scores_multicriteres(
                copy.deepcopy(_CLASSEMENT), PROFILS_PONDERATION[ligne['profil']])
            attendu = sorted(attendu, key=lambda m: m['score_global'],
                             reverse=True)
            with self.subTest(profil=ligne['profil']):
                self.assertEqual(ligne['modele'], attendu[0]['modele'])
                self.assertAlmostEqual(ligne['score'],
                                       round(attendu[0]['score_global'], 4), 4)
                self.assertAlmostEqual(
                    ligne['marge'],
                    round(attendu[0]['score_global']
                          - attendu[1]['score_global'], 4), 4)
        print("    S-6 les 4 lignes egalent la formule qui decide, au "
              "quatrieme chiffre")

    def test_LE_CLASSEMENT_REEL_N_EST_PAS_MUTE(self):
        """⚠️⚠️ LE PIÈGE QUI AURAIT DÉPLACÉ UN PRIX.

        `_calculer_scores_multicriteres` ÉCRIT `score_global` dans les
        dictionnaires reçus. Sans copie profonde, quatre appels auraient
        écrasé le classement publié avec les scores du DERNIER profil — et le
        rapport aurait affiché un score qui n'est pas celui du profil retenu.
        """
        avant = copy.deepcopy(_CLASSEMENT)
        _agent()._sensibilite_profils(_CLASSEMENT, 'equilibre')
        self.assertEqual(_CLASSEMENT, avant,
                         'le classement a ete MUTE : un prix se deplace')
        print("    S-7 le classement recu est inchange apres les 4 recalculs")

    def test_la_MARGE_est_publiee_avec_le_vainqueur(self):
        """⚠️ « Même vainqueur » à 0,008 d'écart et à 0,381 ne se lisent pas
        pareil. La marge est la moitié de l'information."""
        table = _agent()._sensibilite_profils(_CLASSEMENT, 'equilibre')
        for ligne in table:
            self.assertIn('marge', ligne)
            self.assertGreaterEqual(ligne['marge'], 0.0,
                                    'la marge du 1er sur le 2e est negative')
        self.assertGreater(len({l['modele'] for l in table}), 0)
        print(f"    S-8 marges publiees : "
              f"{[round(l['marge'], 3) for l in table]}")

    def test_SECOND_SENS_un_classement_trop_court_ne_publie_RIEN(self):
        """⚠️⚠️ Avec un seul modèle, « la marge sur le 2e » n'existe pas.

        La table se tait plutôt que d'inventer une marge de 0 — *un zéro qui
        signifie « pas de second » est indiscernable d'un ex aequo.*
        """
        self.assertEqual(_agent()._sensibilite_profils(_CLASSEMENT[:1], 'x'), [])
        self.assertEqual(_agent()._sensibilite_profils([], 'x'), [])
        print("    S-9 second sens : moins de 2 modeles -> table vide, aucune "
              "marge inventee")

    def test_elle_ARRIVE_dans_les_DEUX_formats(self):
        """⚠️ Le .docx part au CAC comme le HTML."""
        a6 = {'classement': copy.deepcopy(_CLASSEMENT),
              'modele_production': _CLASSEMENT[0],
              'sensibilite_profils': _agent()._sensibilite_profils(
                  _CLASSEMENT, 'equilibre'),
              'audit_trail': {'timestamp': '2026-08-29T13:44:00'},
              'statut_rag': 'AMBRE'}
        html = R.export_html(result_a3={}, result_a4={}, result_a6=a6,
                             narration_calculee=('', 'absente'))
        blob = R.export_word(result_a3={}, result_a4={}, result_a6=a6,
                             narration_calculee=('', 'absente'))
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            xml = z.read('word/document.xml').decode('utf-8', 'replace')
        for nom, doc in (('HTML', html), ('WORD', xml)):
            with self.subTest(format=nom):
                self.assertIn(R.TITRE_SENSIBILITE, doc)
                for profil in PROFILS_PONDERATION:
                    self.assertIn(profil, doc, f'{profil} absent du {nom}')
        print("    S-10 le tableau est dans le HTML ET dans le .docx")

    def test_SECOND_SENS_sans_donnee_le_rapport_ne_l_INVENTE_pas(self):
        """⚠️ A6 peut ne pas la produire (classement trop court). Le rapport
        doit alors se taire, pas afficher un tableau vide."""
        html = R.export_html(result_a3={}, result_a4={},
                             result_a6={'classement': [], 'statut_rag': 'AMBRE'},
                             narration_calculee=('', 'absente'))
        self.assertNotIn(R.TITRE_SENSIBILITE, html)
        self.assertEqual(R.sensibilite_profils({}), ())
        print("    S-11 second sens : aucune donnee -> aucun tableau")


class TestLaTraceNeRemplacePasLaMesure(unittest.TestCase):
    """Le constat qui a motive la publication, epingle."""

    def test_gouvernance_validee_ne_verifie_QU_UN_NOM(self):
        """⚠️⚠️ LA PREUVE QUE LA TRACE NE COUVRE PAS LE BESOIN.

        Selasse a demandé si `profil_valide_par` suffisait à répondre à
        « le classement changerait-il ? ». Mesuré : la fonction ne regarde
        QUE la présence d'un nom non vide. Elle dit QUI a assumé, jamais CE
        QUE le choix a changé. *Ce test existe pour que l'équivalence ne soit
        pas re-proposée sans mesure.*
        """
        self.assertTrue(gouvernance_validee('Marie Dupont'))
        self.assertFalse(gouvernance_validee(''))
        self.assertFalse(gouvernance_validee(None))
        # ⚠️ Le point : elle rend VRAI quel que soit le profil, donc elle ne
        # peut porter aucune information sur l'effet du profil.
        self.assertTrue(gouvernance_validee('X'))
        print("    S-12 `gouvernance_validee` ne teste qu'un nom non vide : "
              "elle ne peut pas repondre a la question de sensibilite")


if __name__ == '__main__':
    unittest.main()
