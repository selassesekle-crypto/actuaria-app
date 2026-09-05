"""Controles positifs — lot 4.5 : l'avertissement DL, et la vraie courbe.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
DEUX SUJETS, UNE SEULE PROPRIETE : *ce qui decide doit etre VISIBLE sur la
surface signee, et ce qui est MONTRE doit avoir ete mesure.*

═══ A — UN GARDE-FOU REGLEMENTAIRE QUI DEPENDAIT D'UN APPEL RESEAU ═══

⚠️⚠️ CE QUI A ETE MESURE LE 29/08/2026, PAR EXECUTION DU PIPELINE REEL.
Les modeles d'A5 concourent DEJA au choix du modele de production -- ce n'est
pas une hypothese, c'est un run :

    frequence   9 candidats {GLM 1, Deep Learning 2, ML 6}  DL_CANN rang 2
    cout        8 candidats {Deep Learning 1, GLM 1, ML 6}  DL_TABNET RANG 1
                -> modele_production = DL_TABNET

Sur ce dossier, le rapport signe publiait :

    << Chapitre 6 -- Modele de production retenu : DL_TABNET, Deep Learning >>
    << RECOMMANDATION : -> Deployer DL_TABNET comme modele de tarification. >>

et l'alerte `dl_validation_humaine_requise` s'etait BIEN declenchee dans
`alertes_modele`. Pourtant le HTML contenait **ZERO** occurrence de
<< validation actuarielle humaine >>, << ACTION REQUISE >>, << alerte >>.

⚠️⚠️ LA CAUSE, VERIFIEE AU SITE : `synthese_modele_dl` n'avait qu'UN SEUL point
de sortie dans ce rapport -- `_construire_contexte_tarif`, **qui construit le
prompt envoye au LLM**. Sans cle, sans reseau, ou sur une narration tronquee,
l'avertissement disparaissait. *Un garde-fou reglementaire ne peut pas dependre
d'un appel reseau.*

⚠️ ET LE CONSTAT EST PLUS LARGE QUE CE LOT NE LE FERME : les **six** syntheses
du rapport (`mapping`, `exclusions`, `alertes_experience`, `modele_dl`,
`qualite_donnees`, `colonnes_plan_manquantes`) vivent TOUTES dans ce seul
prompt. Ce lot ne cable que celle que Selasse a autorisee. Les cinq autres sont
NOMMEES, non traitees.

⚠️ Le texte n'est pas reecrit ici : il vient de `synthese_modele_dl`, la source
unique que le rapport d'equipe et l'Excel utilisent deja.

═══ B — UNE COURBE D'ENTRAINEMENT QUI N'AVAIT JAMAIS ETE MESUREE ═══

`a5/C4`. La figure tracait une exponentielle analytique bruitee :

    courbe = loss_init*exp(-3e/50) + loss_final*(1-exp(-3e/50))   analytique
    bruit  = np.random.normal()                       NON SEME
    50 epoques codees en dur                          le run reel en fait 3

⚠️⚠️ ET LE REMEDE N'EST PAS DE SEMER LE BRUIT -- ce serait rendre une courbe
FABRIQUEE reproductible, donc credible. Les vraies pertes existaient deja :
`_calibrer_cann` / `_calibrer_tabnet` empilent `{'epoch','train','val'}`.

⚠️ ET LE CORRECTIF ETAIT DEJA ARRIVE A COTE UNE FOIS : `_valider_hypotheses_dl`
avait cesse de simuler ses losses (<< H1 NE SIMULE PLUS SES LOSSES >>, l.2028)
-- la FIGURE, elle, continuait. *Corrige dans la validation, pas dans ce qui
est montre.*

Mesure apres correctif, deux runs identiques : courbe tracee = historique reel
au flottant pres, 3 epoques, et **identique entre les deux runs**.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

from core.conformite_reglementaire import synthese_modele_dl
from direction_non_vie.tarification.services import rapport_modeles_tarif as R

_RACINE = pathlib.Path(__file__).resolve().parent

#: L'historique REEL mesure sur un run a 3 epoques (CANN, portefeuille auto).
_HISTORIQUE = [
    {'epoch': 1, 'train': 1727.661, 'val': 1717.849},
    {'epoch': 2, 'train': 1623.403, 'val': 1588.604},
    {'epoch': 3, 'train': 1466.265, 'val': 1441.543},
]


def _a6(modele: str, famille: str, valide_par=None) -> dict:
    """Un resultat A6 minimal — seulement ce que le bloc lit."""
    return {
        'modele_production': {'modele': modele, 'famille': famille},
        'valide_par_actuaire_dl': valide_par,
        'audit_trail': {'timestamp': '2026-08-29T13:44:00', 'raisons_plafond': ()},
        'statut_rag': 'AMBRE',
    }


class TestAvertissementDLSurLaSurfaceSignee(unittest.TestCase):
    """A — l'avertissement ne depend plus du LLM."""

    def test_il_apparait_SANS_AUCUNE_NARRATION(self):
        """⚠️⚠️ LE TEST QUI FERME LE CONSTAT.

        `narration_calculee=('', 'absente')` reproduit exactement l'etat mesure : pas de cle, pas de
        reseau. Avant ce lot, le HTML ne portait alors AUCUN avertissement.
        """
        html = R.export_html(result_a3={}, result_a4={},
                             result_a6=_a6('DL_TABNET', 'Deep Learning'),
                             narration_calculee=('', 'absente'))
        texte = html if isinstance(html, str) else html.decode('utf-8', 'replace')
        self.assertIn('validation actuarielle humaine requise', texte)
        self.assertIn('ACTION REQUISE', texte)
        self.assertIn(R.TITRE_DL_PRODUCTION, texte)
        print("    A-1 avertissement present SANS narration LLM")

    def test_TEMOIN_il_se_TAIT_quand_le_modele_n_est_pas_DL(self):
        """⚠️⚠️ SECOND SENS, ET IL COMPTE AUTANT QUE LE PREMIER.

        Un avertissement affiche toujours cesse d'etre un signal — c'est la
        lecon de `charts/C3`. Sur un modele GLM, le bloc doit etre ABSENT.
        """
        html = R.export_html(result_a3={}, result_a4={},
                             result_a6=_a6('GLM_POISSON', 'GLM'), narration_calculee=('', 'absente'))
        texte = html if isinstance(html, str) else html.decode('utf-8', 'replace')
        self.assertNotIn('ACTION REQUISE', texte)
        self.assertNotIn(R.TITRE_DL_PRODUCTION, texte)
        self.assertEqual(R.avertissement_dl(_a6('GLM_POISSON', 'GLM')), '')
        print("    A-2 temoin : silence complet sur un modele GLM")

    def test_une_fois_VALIDE_la_trace_reste_VISIBLE(self):
        """⚠️ L'alerte se tait quand la validation est faite — la TRACE, non.

        `synthese_modele_dl` documente les deux etats : non valide -> ACTION
        REQUISE ; valide -> trace factuelle (qui, quand). *Une validation
        invisible ne vaut pas mieux qu'une validation absente pour l'actuaire
        qui relit le dossier plus tard.*
        """
        html = R.export_html(
            result_a3={}, result_a4={},
            result_a6=_a6('DL_TABNET', 'Deep Learning', valide_par='M. Dupont'),
            narration_calculee=('', 'absente'))
        texte = html if isinstance(html, str) else html.decode('utf-8', 'replace')
        self.assertNotIn('ACTION REQUISE', texte)
        self.assertIn('M. Dupont', texte)
        self.assertIn('29/08/2026', texte)
        print("    A-3 valide : l'action requise disparait, la trace reste")

    def test_le_texte_vient_de_la_SOURCE_UNIQUE(self):
        """⚠️ Aucune reformulation locale.

        Le rapport d'equipe et l'Excel publient deja ce texte. Une seconde
        redaction aurait diverge — comme les 30 definitions de couleurs avant
        `STATUT_RAG`.
        """
        a6 = _a6('DL_TABNET', 'Deep Learning')
        attendu = synthese_modele_dl(a6['modele_production'], None,
                                     a6['audit_trail']['timestamp'])
        self.assertEqual(R.avertissement_dl(a6), attendu)
        print("    A-4 texte identique a `synthese_modele_dl`, caractere pour "
              "caractere")

    def test_les_DEUX_formats_le_portent(self):
        """⚠️⚠️ LE WORD PART AU CAC COMME LE HTML.

        Corriger un seul des deux aurait laisse la moitie du livrable signe
        recommander un deploiement sans son garde-fou.
        """
        blob = R.export_word(result_a3={}, result_a4={},
                             result_a6=_a6('DL_TABNET', 'Deep Learning'),
                             narration_calculee=('', 'absente'))
        self.assertTrue(blob, 'aucun .docx produit')
        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            xml = z.read('word/document.xml').decode('utf-8', 'replace')
        for attendu in ('ACTION REQUISE', 'DL_TABNET', R.TITRE_DL_PRODUCTION):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, xml)
        print("    A-5 le .docx porte le meme avertissement que le HTML")

    def test_les_QUATRE_AUTRES_syntheses_restent_dans_le_prompt_SEUL(self):
        """⚠️⚠️ L'ASSIETTE REELLE DU DEFAUT, RELEVEE PAR AST ET NON TRAITEE.

        ⚠️⚠️ MIS A JOUR LE 30/08/2026 — ET CE TEST A FAIT EXACTEMENT CE QU'IL
        ANNONCAIT. `synthese_qualite_donnees` a ete cablee hors du prompt par
        le lot des roles de donnees (constat `services/C12`), et ce
        filet est tombe le jour meme, en nommant la synthese ajoutee.
        *Un defaut connu et non traite se declare ; celui-ci s'est aussi
        souvenu du jour ou on le traiterait.*

        ⚠️⚠️ MIS A JOUR LE 05/09/2026 — ET IL EST RETOMBE LE JOUR MEME, POUR
        LA SECONDE FOIS. `synthese_elasticite` a ete cablee hors du prompt par
        le lot des faits publies. La mesure qui l'a motivee :
        **7 occurrences de l'elasticite dans le classeur A6, 7 dans le rapport
        d'equipe, 0 dans le Word et le HTML d'A6** -- alors qu'elle y etait
        bien calculee, dans `_construire_contexte_tarif`, c'est-a-dire dans le
        PROMPT. Et la narration rendue (1 269 caracteres) n'en portait aucune
        trace. *Un calcul qui n'atteint que le prompt n'atteint pas un
        livrable.*

        TROIS sont desormais cablees. SIX ne le sont pas : leur seul point de
        sortie reste `_construire_contexte_tarif`. Ce test FIGE ce fait pour
        qu'il ne se perde pas : il tombera le jour ou l'une d'elles sera
        cablee, et il faudra alors mettre a jour le compte.

        *Un defaut connu et non traite se declare ; il ne se laisse pas
        oublier entre deux lots.*
        """
        src = (_RACINE / 'services' / 'rapport_modeles_tarif.py').read_text(
            encoding='utf-8')
        arbre = ast.parse(src)
        fonctions = [(n.name, n.lineno, n.end_lineno) for n in ast.walk(arbre)
                     if isinstance(n, ast.FunctionDef)]

        def enclos(ligne):
            cands = [f for f in fonctions if f[1] <= ligne <= f[2]]
            return min(cands, key=lambda f: f[2] - f[1])[0] if cands else '?'

        dehors = set()
        for n in ast.walk(arbre):
            if isinstance(n, ast.Call):
                nom = getattr(n.func, 'id', None) or getattr(n.func, 'attr', None)
                if (nom and nom.startswith('synthese_')
                        and enclos(n.lineno) != '_construire_contexte_tarif'):
                    dehors.add(nom)
        self.assertEqual(
            dehors, {'synthese_elasticite', 'synthese_modele_dl',
                     'synthese_qualite_donnees'},
            f"L'assiette a change : synthese(s) hors du prompt = {sorted(dehors)}. "
            f"Si une autre a ete cablee, mettre a jour le releve et ce test.")
        print("    A-6 3 syntheses cablees ; les 6 autres restent dans le "
              "prompt SEUL, et c'est declare")


class TestCourbeConvergenceMesuree(unittest.TestCase):
    """B — `a5/C4` : la figure trace ce qui s'est passe."""

    def _figure(self, courbe):
        from direction_non_vie.tarification.a5_deep_learning.agent import (
            AgentA5DeepLearning,
        )
        val_dl = {
            'h1_convergence': {
                'loss_init': 1727.661, 'loss_final': 1466.265,
                'ratio_conv': 0.8487, 'statut': 'ROUGE',
                'message': 'm', 'conseil': 'c', 'courbe': courbe,
                'titre_graphique': 'Convergence',
            },
            'h2_surapprentissage': {'ratio_of': 1.0, 'statut': 'VERT',
                                    'message': 'm', 'conseil': 'c',
                                    'titre_graphique': 't'},
            'h3_apport_dl': {'gini_glm': 0.1, 'statut': 'VERT',
                             'message': 'm', 'conseil': 'c',
                             'titre_graphique': 't'},
            'statut_global': 'AMBRE', 'conclusion': 'c',
        }
        agent = AgentA5DeepLearning(models_path='/tmp', audit_path='/tmp',
                                    verbose=False)
        figs = agent._graphiques_validation_dl(val_dl, [], {})
        return figs.get('convergence_loss')

    def test_la_courbe_TRACEE_est_l_historique_REEL(self):
        """⚠️⚠️ LE TEST QUI FERME `a5/C4` — egalite exacte, pas ressemblance."""
        fig = self._figure(_HISTORIQUE)
        self.assertIsNotNone(fig, 'figure non produite')
        traces = [t for t in fig.data if getattr(t, 'y', None) is not None]
        self.assertEqual(len(traces), 2, 'train et val attendues')
        self.assertEqual([int(v) for v in traces[0].x],
                         [p['epoch'] for p in _HISTORIQUE])
        self.assertEqual([round(float(v), 3) for v in traces[0].y],
                         [p['train'] for p in _HISTORIQUE])
        self.assertEqual([round(float(v), 3) for v in traces[1].y],
                         [p['val'] for p in _HISTORIQUE])
        print(f"    B-1 courbe tracee = historique reel, "
              f"{len(_HISTORIQUE)} epoques (le releve en simulait 50)")

    def test_DEUX_APPELS_donnent_la_MEME_figure(self):
        """⚠️⚠️ LE BRUIT NON SEME, EPINGLE PAR SON EFFET.

        `np.random.normal()` sans graine faisait differer la figure a CHAQUE
        run. On ne teste pas l'absence d'un symbole : on teste que le resultat
        ne bouge pas. *Un test sur l'effet survit a un changement de methode.*
        """
        a = self._figure(_HISTORIQUE)
        b = self._figure(_HISTORIQUE)
        for i in (0, 1):
            self.assertEqual(
                [float(v) for v in a.data[i].y], [float(v) for v in b.data[i].y],
                'la figure differe entre deux appels identiques')
        print("    B-2 deux appels identiques -> figure identique")

    def test_AUCUN_tirage_aleatoire_dans_les_figures_d_A5(self):
        """⚠️ LE FILET, PAR AST. Il tombe si un `np.random.*` revient.

        ⚠️ Il ne remplace PAS le test par l'effet ci-dessus : un tirage seme
        passerait ce controle-ci et serait pourtant une courbe FABRIQUEE.
        Les deux ensemble disent << ni fabrique, ni aleatoire >>.
        """
        src = (_RACINE / 'a5_deep_learning' / 'agent.py').read_text(
            encoding='utf-8')
        arbre = ast.parse(src)
        cible = next(
            (n for n in ast.walk(arbre)
             if isinstance(n, ast.FunctionDef)
             and n.name == '_graphiques_validation_dl'), None)
        self.assertIsNotNone(cible, '_graphiques_validation_dl introuvable')
        tirages = [
            n.lineno for n in ast.walk(cible)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Attribute)
            and n.func.value.attr == 'random']
        self.assertEqual(
            tirages, [],
            f'tirage(s) aleatoire(s) dans les figures A5 : lignes {tirages}')
        print("    B-3 0 `np.random.*` dans `_graphiques_validation_dl` (AST)")

    def test_l_ABSENCE_d_historique_se_DECLARE_au_lieu_de_se_fabriquer(self):
        """⚠️⚠️ SECOND SENS — le cas ou l'ancien code inventait le plus.

        Sans historique, la figure ne se rabat sur AUCUNE formule : elle dit
        qu'elle ne montre rien. Lecon de `charts/C3`.
        """
        fig = self._figure([])
        self.assertIsNotNone(fig)
        textes = ' '.join(str(a.text) for a in (fig.layout.annotations or ()))
        self.assertIn('AUCUNE DONNÉE', textes)
        self.assertIn("historique d'entraînement", textes)
        for t in fig.data:
            self.assertEqual(len(getattr(t, 'y', ()) or ()), 0,
                             'des points sont traces sans historique')
        print("    B-4 sans historique : la figure le DECLARE, 0 point trace")

    def test_le_nombre_d_epoques_ANNONCE_est_celui_qui_est_TRACE(self):
        """⚠️ Le `50` code en dur ne correspondait a aucun run.

        La figure annonce desormais son propre compte — et on verifie que le
        nombre ECRIT est bien le nombre TRACE, pas un second littéral.
        """
        fig = self._figure(_HISTORIQUE)
        textes = ' '.join(str(a.text) for a in (fig.layout.annotations or ()))
        n_trace = len(fig.data[0].y)
        self.assertIn(f'{n_trace} époque(s) réellement effectuée(s)', textes)
        self.assertNotIn('50 époque', textes)
        print(f"    B-5 la figure annonce {n_trace} epoques, et en trace "
              f"{n_trace}")


if __name__ == '__main__':
    unittest.main()
