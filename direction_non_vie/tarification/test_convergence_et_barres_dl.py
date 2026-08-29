"""Controles positifs — lot 4.6 : le verdict vise le bon modele, la barre
absente n'est plus un zero.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
DEUX SUJETS, UNE SEULE PROPRIETE : *un chiffre publie doit designer l'objet
qu'il pretend mesurer, et une absence ne se publie jamais comme une valeur.*

═══ ① LE VERDICT PORTAIT SUR LE MAUVAIS OBJET ═══

⚠️⚠️ TROUVE PARCE QU'UN CORRECTIF DE LA VEILLE A REND VISIBLE UN DEFAUT
CACHE. Le lot 4.5 a fait tracer a `convergence_loss` les VRAIES pertes au lieu
d'une exponentielle simulee. Mesure ensuite, sur deux runs reels :

    portefeuille 2500 : classement A5 tete = CANN               -> 3 points
    portefeuille 3000 : classement A5 tete = 'GLM Poisson (A3)' -> 0 point
                        (cann=3 et tabnet=3 historiques EXISTAIENT pourtant)

Cause au site : `_cle_h1 = classement[0]['modele'].lower()`. Le classement
INTERNE d'A5 contient aussi le GLM d'A3 et le meilleur ML d'A4. Quand l'un
d'eux gagne, `historiques.get('glm poisson (a3)')` ne trouve rien, et H1
publie << convergence NON mesuree >>, statut ROUGE -- **un verdict sur la
convergence du DEEP LEARNING rendu faux par la victoire d'un GLM.**

⚠️ AVANT LE LOT 4.5, CE CAS FABRIQUAIT UNE COURBE PLATE A ZERO etiquetee
<< Convergence >>. Le correctif a transforme un mensonge silencieux en trou
visible -- c'est ce trou qui a livre le defaut.

⚠️ ON FILTRE PAR LA DONNEE PRESENTE, PAS PAR UNE ETIQUETTE. Le classement
porte bien `type == 'Deep Learning'`, mais s'y fier ferait dependre un verdict
d'un libelle. Seuls les modeles DL ont un historique : **avoir une entree dans
`historiques` EST le critere**, et il ne peut pas mentir. Le parcours suit
l'ORDRE du classement, donc le premier trouve est le MEILLEUR des DL.

═══ ② `a5/C5` — LE SYMPTOME SE REPRODUISAIT ENCORE, PAR UNE AUTRE CAUSE ═══

Le releve mesurait `barres [GLM, CANN, TabNet] = [0.14, 0, 0]` pour des Gini
reels `[0.4781, 0.0950]` : la figure lisait la mauvaise cle. Elle lit la bonne
depuis. ⚠️⚠️ MAIS, mesure le 29/08/2026 AVANT ce lot :

    les deux modeles ENTRAINES        barres = [0.14, 0.4781, 0.095]
    CANN ABSENT (calibration echouee) barres = [0.14, 0.0,    0.095]
    LES DEUX ABSENTS                  barres = [0.14, 0.0,    0.0]

`self.metriques['cann']` n'existe QUE si la calibration a reussi ; le
`.get(..., 0)` transformait une absence en performance nulle. **La derniere
ligne reproduit EXACTEMENT les nombres du releve.** Epingler `a5/C5` sans
fermer cette cause aurait certifie un constat qui se reproduit encore --
*le filet aurait eu une assiette trop etroite.*

*Un zero qui signifie << jamais entraine >> est indiscernable d'un zero
mesure* : meme lecon qu'`a3/C6` (le Gini du Tweedie) et que le plancher d'A5.
"""

from __future__ import annotations

import unittest

from direction_non_vie.tarification.a5_deep_learning.agent import (
    AgentA5DeepLearning,
)

#: Deux historiques distincts, pour que le test voie LEQUEL est lu.
_HISTORIQUES = {
    'cann':   [{'epoch': 1, 'train': 1.0, 'val': 1.1},
               {'epoch': 2, 'train': 0.4, 'val': 0.5}],      # ratio 0,40 -> VERT
    'tabnet': [{'epoch': 1, 'train': 2.0, 'val': 2.1}],      # ratio 1,00 -> ROUGE
}

_VAL_DL = {
    'h1_convergence': {'loss_init': 1.0, 'loss_final': 0.5, 'ratio_conv': 0.5,
                       'statut': 'VERT', 'message': 'm', 'conseil': 'c',
                       'courbe': [], 'titre_graphique': 't'},
    'h2_surapprentissage': {'ratio_of': 1.0, 'statut': 'VERT', 'message': 'm',
                            'conseil': 'c', 'titre_graphique': 't'},
    'h3_apport_dl': {'gini_glm': 0.14, 'statut': 'ROUGE', 'message': 'm',
                     'conseil': 'c', 'titre_graphique': 't'},
    'statut_global': 'ROUGE', 'conclusion': 'c',
}


def _agent() -> AgentA5DeepLearning:
    return AgentA5DeepLearning(models_path='/tmp', audit_path='/tmp',
                               verbose=False)


def _h1(classement, historiques=None):
    return _agent()._valider_hypotheses_dl(
        classement, {}, historiques=_HISTORIQUES if historiques is None
        else historiques)['h1_convergence']


class TestLeVerdictViseLeModeleDL(unittest.TestCase):
    """① H1 mesure la convergence DU DEEP LEARNING, quel que soit le vainqueur."""

    def test_un_GLM_EN_TETE_ne_vide_plus_la_courbe(self):
        """⚠️⚠️ LE TEST QUI FERME LE DEFAUT — le cas mesure sur run reel.

        `classement[0]` etait le GLM ; la courbe tombait a 0 point et le statut
        a ROUGE << non mesuree >>, alors que l'historique du CANN existait.
        """
        h1 = _h1([{'modele': 'GLM Poisson (A3)'}, {'modele': 'CANN'}])
        self.assertEqual(len(h1['courbe']), 2,
                         'la courbe se vide encore quand un GLM gagne')
        self.assertEqual(h1['statut'], 'VERT')
        self.assertNotIn('NON mesurée', h1['message'])
        print("    D-1 GLM en tete : courbe = 2 points, statut VERT "
              "(avant : 0 point, ROUGE)")

    def test_c_est_le_MEILLEUR_DL_qui_est_lu_pas_n_importe_lequel(self):
        """⚠️ Le parcours suit l'ORDRE du classement.

        Deux DL avec des historiques OPPOSES : celui qui decide doit etre le
        mieux classe. Sinon le verdict serait juste par accident.
        """
        cann_devant = _h1([{'modele': 'GLM Poisson (A3)'},
                           {'modele': 'CANN'}, {'modele': 'TABNET'}])
        tabnet_devant = _h1([{'modele': 'GLM Poisson (A3)'},
                             {'modele': 'TABNET'}, {'modele': 'CANN'}])
        self.assertEqual(cann_devant['statut'], 'VERT')
        self.assertEqual(tabnet_devant['statut'], 'ROUGE')
        self.assertNotEqual(cann_devant['courbe'], tabnet_devant['courbe'])
        print("    D-2 l'ordre du classement decide : CANN devant -> VERT, "
              "TABNET devant -> ROUGE")

    def test_le_MESSAGE_nomme_le_modele_dont_on_lit_les_pertes(self):
        """⚠️⚠️ LE LIBELLE DOIT DESIGNER L'OBJET MESURE, PAS SON VOISIN.

        `modele_nm` valait `classement[0]` : le conseil aurait dit << GLM
        Poisson (A3) a bien converge >> en lisant l'historique du CANN.
        """
        h1 = _h1([{'modele': 'GLM Poisson (A3)'}, {'modele': 'CANN'}])
        texte = f"{h1['message']} {h1['conseil']}"
        self.assertIn('CANN', texte)
        self.assertNotIn('GLM Poisson', texte)
        print(f"    D-3 le conseil nomme CANN, pas le GLM : "
              f"« {h1['conseil'][:52]}… »")

    def test_SECOND_SENS_aucun_DL_au_classement_reste_NON_MESUREE(self):
        """⚠️⚠️ LE CORRECTIF NE DOIT PAS FABRIQUER UN VERDICT.

        S'il n'y a aucun modele DL, il n'y a rien a mesurer — et cela reste
        ROUGE << non mesuree >>, jamais un VERT commode. C'est exactement ce
        que `test_epinglage_fermes_vivants` epingle deja ; on le REVERIFIE ici
        parce que ce lot touche la recherche qu'il exerce.
        """
        h1 = _h1([{'modele': 'GLM Poisson (A3)'}, {'modele': 'ML Best (xgb)'}])
        self.assertEqual(len(h1['courbe']), 0)
        self.assertEqual(h1['statut'], 'ROUGE')
        self.assertIn('NON mesurée', h1['message'])
        print("    D-4 second sens : aucun DL -> ROUGE non mesuree, pas de "
              "verdict fabrique")

    def test_un_historique_VIDE_donne_NON_MESUREE_et_la_garde_est_DOUBLE(self):
        """⚠️⚠️ CE TEST DIT MAINTENANT LA VERITE SUR CE QUI LE PROTEGE.

        Il affirmait que la protection venait du `historiques.get(_cle)` —
        une cle presente mais vide n'etant pas << trouvee >>. **VIOLATION
        PLANTEE, ET LE FILET N'EST PAS TOMBE** : en remplacant le `.get()` par
        un `in historiques`, le comportement ne bouge pas, parce que le
        `if classement and histo_h1:` en aval retient deja le cas.

        *J'attribuais la protection au mauvais mecanisme.* La propriete reste
        vraie et vaut d'etre figee — un historique vide ne peut pas produire un
        verdict — mais elle est portee par DEUX gardes, et ce test ne
        discrimine pas laquelle. **Il ne faut donc pas s'en servir pour
        conclure quoi que ce soit sur le `.get()`.**
        """
        h1 = _h1([{'modele': 'CANN'}], historiques={'cann': []})
        self.assertEqual(len(h1['courbe']), 0)
        self.assertEqual(h1['statut'], 'ROUGE')
        self.assertIn('NON mesurée', h1['message'])
        print("    D-5 historique VIDE -> non mesuree (garde DOUBLE : ce test "
              "ne dit pas laquelle agit)")


class TestBarreAbsenteNEstPasUnZero(unittest.TestCase):
    """② `a5/C5` — un modele non calibre est retire, pas mis a zero."""

    def _figure(self, metriques):
        return _agent()._graphiques_validation_dl(
            _VAL_DL, [], metriques).get('comparaison_dl_glm')

    def _barres(self, metriques):
        fig = self._figure(metriques)
        self.assertIsNotNone(fig, 'figure non produite')
        return (list(fig.data[0].x),
                [round(float(v), 4) for v in fig.data[0].y],
                ' '.join(str(a.text) for a in (fig.layout.annotations or ())))

    def test_les_deux_modeles_ENTRAINES_publient_leur_VRAI_gini(self):
        """⚠️ La cause d'origine du constat : la mauvaise cle. Deja corrigee,
        jamais epinglee — l'archive la classe « corrige, NON epingle »."""
        x, y, _ = self._barres({'cann': {'gini_test': 0.4781},
                                'tabnet': {'gini_test': 0.0950}})
        self.assertEqual(len(x), 3)
        self.assertEqual(y, [0.14, 0.4781, 0.095])
        print(f"    E-1 barres = {y} (le releve mesurait [0.14, 0, 0])")

    def test_un_modele_ABSENT_est_RETIRE_et_DECLARE(self):
        """⚠️⚠️ LA SECONDE CAUSE, CELLE QUE CE LOT FERME.

        `.get('gini_test', 0)` publiait une absence comme une performance
        nulle. Le modele sort de la figure, et son absence est ECRITE.
        """
        x, y, notes = self._barres({'tabnet': {'gini_test': 0.0950}})
        self.assertEqual(x, ['GLM Poisson (ref)', 'TabNet'])
        self.assertEqual(y, [0.14, 0.095])
        self.assertNotIn(0.0, y, 'une barre fantome a zero subsiste')
        self.assertIn('CANN', notes)
        self.assertIn('non calibré', notes)
        print(f"    E-2 CANN absent : {len(x)} barres au lieu de 3, retire ET "
              f"declare sous l'axe (avant : barre a 0,0)")

    def test_LE_CAS_EXACT_DU_RELEVE_ne_se_reproduit_PLUS(self):
        """⚠️⚠️ LES NOMBRES DU RELEVE, REJOUES.

        Avant ce lot, deux modeles absents rendaient `[0.14, 0.0, 0.0]` —
        **exactement** ce que le releve avait mesure. Le constat se
        reproduisait donc encore, par une autre cause.
        """
        x, y, notes = self._barres({})
        self.assertEqual(y, [0.14],
                         'le symptome [0.14, 0.0, 0.0] se reproduit encore')
        self.assertEqual(len(x), 1)
        self.assertIn('AUCUNE DONNÉE', notes)
        self.assertIn('Deep Learning', notes)
        print("    E-3 aucun DL calibre : une seule barre, et la figure "
              "declare qu'elle ne montre rien du DL")

    def test_la_PALETTE_suit_le_nombre_de_barres(self):
        """⚠️ Une couleur de trop laisserait une barre retiree decaler les
        autres — le modele restant prendrait la couleur de l'absent."""
        fig_plein = self._figure({'cann': {'gini_test': 0.4781},
                                  'tabnet': {'gini_test': 0.0950}})
        fig_creux = self._figure({'tabnet': {'gini_test': 0.0950}})
        c_plein = list(fig_plein.data[0].marker.color)
        c_creux = list(fig_creux.data[0].marker.color)
        self.assertEqual(len(c_plein), 3)
        self.assertEqual(len(c_creux), 2)
        self.assertEqual(c_creux, c_plein[:2],
                         'les couleurs se decalent quand une barre disparait')
        print(f"    E-4 palette = {len(c_creux)} couleurs pour "
              f"{len(c_creux)} barres, aucun decalage")


if __name__ == '__main__':
    unittest.main()
