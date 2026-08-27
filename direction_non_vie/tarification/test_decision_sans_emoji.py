"""Controles positifs — 2a + 2b : une decision ne lit jamais un emoji.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
SITE 9 — LA VRAIE FAILLE. Le verrou du statut RAG decidait ainsi :

    elif '🔴' in _stab:
        _wf_resultat_ok = False

`stabilite_wf` est un LIBELLE D'AFFICHAGE (« 🔴 Instable »), fait pour etre lu
par un humain. **Une decision reglementaire qui bloque le VERT dependait donc
de la presence d'un symbole dans une chaine de texte.** Qu'on ecrive
« Instable ❌ » et le garde-fou cesse de bloquer, EN SILENCE -- exactement le
defaut `a6/C6`, ou trois branches etaient mortes derriere une gate verte.

⚠️ LE CORRECTIF N'EST PAS DE CHERCHER UN AUTRE SYMBOLE : c'est de lire le
CHAMP -- `ae_cv_wf` -- et de NOMMER le seuil, pour que le libelle et la
decision lisent le meme nombre et ne puissent plus diverger.

⚠️ ET UNE ABSENCE DE MESURE N'EST PAS UNE INSTABILITE : `ae_cv_wf` peut valoir
None. On ne degrade alors PAS. *Meme regle que partout dans cet audit.*

SITE 1 — la branche ROUGE de la recommandation de monitoring portait un rond
colore, alors que les deux autres branches du meme bloc utilisaient deja le
jeu commun. Elle lit desormais la source.

2a — les 14 lignes de la table `{'VERT': '🟢', ...}` lisent la source unique.
⚠️ Le repli `'⚪'` des deux fonctions de service est PRESERVE : `glyphe_rag`
rend une chaine vide pour un statut inconnu, la ou ces fonctions rendaient un
cercle blanc. *Un correctif qui change un comportement non demande est un
defaut, meme petit.*

⚠️ CE QUI N'EST PAS TOUCHE, ET C'EST UNE DECISION DE FOND, PAS UNE PRUDENCE :
  · les legendes de FAMILLE (« 🔵 Deep Learning · 🟡 ML · ⬜ GLM ») -- les ronds
    y encodent un TYPE, pas un statut ; y mettre ✅⚠️❌ ecrirait un faux ;
  · les verdicts A/E et de stabilite a trois bandes -- ce ne sont pas des RAG,
    et leur imposer le glyphe du RAG effacerait la distinction ;
  · les 30 fixtures de TEST -- ce sont des valeurs ATTENDUES. Les modifier
    changerait ce que les invariants prouvent.
"""

from __future__ import annotations

import inspect
import re
import unicodedata
import unittest

from core.charts_tarif import GLYPHE_RAG
from direction_non_vie.tarification.a6_comparaison.agent import (
    SEUIL_CV_INSTABLE,
    SPLIT_WALK_FORWARD,
    AgentA6Comparaison,
)

_AGENTS = ('a3_glm', 'a4_ml', 'a5_deep_learning', 'a6_comparaison')
_RONDS = ('🟢', '🟡', '🔴')


def _source(module: str) -> str:
    mod = __import__(module, fromlist=['x'])
    return unicodedata.normalize('NFC', inspect.getsource(mod))


def _modele() -> dict:
    return {'modele': 'GLM_POISSON', 'famille': 'GLM', 'cible': 'nb_sinistres',
            'gini_test': 0.31, 'gini_train': 0.33, 'score_global': 0.72,
            'rmse_test': 1.0, 'overfit_ratio': 1.02, 'nb_vars': 5,
            'interpretabilite': 1.0}


def _backtest(cv, libelle: str) -> dict:
    return {'disponible': True, 'split': SPLIT_WALK_FORWARD, 'n_fenetres': 3,
            'ae_ratio': 1.0, 'ae_moyen_wf': 1.0, 'gini_wf_moyen': 0.25,
            'n_fenetres_rouge': 0, 'ae_cv_wf': cv, 'stabilite_wf': libelle,
            'modele': 'GLM_POISSON', 'methode': SPLIT_WALK_FORWARD}


def _motifs(cv, libelle: str) -> str:
    """Le MOTIF, pas le statut. ⚠️ Le statut seul ne discrimine pas : un autre
    plafond (walk-forward proxy) le ramène à AMBRE dans les deux cas. C'est le
    motif qui dit QUELLE condition a tiré."""
    import logging
    from io import StringIO

    tampon = StringIO()
    poignee = logging.StreamHandler(tampon)
    poignee.setLevel(logging.WARNING)
    journal = logging.getLogger('actuaria.a6')
    etat, niveau = journal.disabled, journal.level
    journal.disabled = False
    journal.setLevel(logging.WARNING)
    journal.addHandler(poignee)
    try:
        AgentA6Comparaison(models_path='/tmp', audit_path='/tmp',
                           verbose=False)._calculer_statut_rag(
            _modele(), [_modele()], profil_valide_par='X',
            environnement='production', backtest=_backtest(cv, libelle),
            cible_est_frequence=True)
    finally:
        journal.removeHandler(poignee)
        journal.disabled, journal.level = etat, niveau
    return tampon.getvalue()


class TestDecisionSansEmoji(unittest.TestCase):
    """La decision lit un champ ; l'emoji n'est plus qu'un affichage."""

    # ══════════════════════════════════════════════════════════════════════
    # SITE 9 — la décision suit le CHAMP, plus le symbole
    # ══════════════════════════════════════════════════════════════════════

    def test_un_CV_degrade_bloque_MEME_SANS_emoji_dans_le_libelle(self):
        """⚠️⚠️ LE TEST QUI FERME LA FAILLE.

        Avant, un libellé « Instable » sans son rond ne déclenchait RIEN : le
        garde-fou cherchait le symbole. Il lit désormais `ae_cv_wf`.
        """
        motifs = _motifs(0.40, 'Instable')
        self.assertIn('stabilité inter-fenêtres dégradée', motifs)
        self.assertIn('0.4000', motifs)
        self.assertIn(str(SEUIL_CV_INSTABLE), motifs)

    def test_un_emoji_SEUL_ne_declenche_PLUS_rien(self):
        """⚠️ SECOND SENS — un libellé rouge avec un CV sain ne doit rien
        déclencher. Sinon la décision suivrait encore le symbole."""
        motifs = _motifs(0.02, '🔴 Instable')
        self.assertNotIn('stabilité inter-fenêtres dégradée', motifs)

    def test_un_CV_non_mesure_ne_degrade_PAS(self):
        """⚠️ Une absence de mesure n'est pas une instabilité — même règle que
        partout dans cet audit. `None` ne doit pas se lire comme « mauvais »."""
        motifs = _motifs(None, '🔴 Instable')
        self.assertNotIn('stabilité inter-fenêtres dégradée', motifs)

    def test_aucune_decision_ne_lit_un_rond_colore(self):
        """⚠️ Contrôle par AST : plus aucun `'🔴' in …` dans les quatre agents.

        Chercher un symbole dans une chaîne d'affichage est une dépendance
        invisible : le jour où le libellé change, la décision se tait.
        """
        fautifs = []
        for agent in _AGENTS:
            src = _source(f'direction_non_vie.tarification.{agent}.agent')
            for i, ligne in enumerate(src.split('\n'), 1):
                if re.match(r'\s*#', ligne):
                    continue
                for rond in _RONDS:
                    if re.search(rf"[\'\"]{rond}[\'\"]\s+in\s+", ligne):
                        fautifs.append(f"{agent}:{i}")
        self.assertEqual(
            fautifs, [],
            f"Décision(s) lisant un rond dans une chaîne : {fautifs}. Le "
            f"libellé est fait pour être lu, pas interrogé par un verrou.")

    def test_le_seuil_est_NOMME_et_partage(self):
        """⚠️ Le libellé et la décision doivent lire LE MÊME nombre.

        Un `0.10` recopié des deux côtés diverge au premier ajustement.
        """
        src = _source('direction_non_vie.tarification.a6_comparaison.agent')
        self.assertGreaterEqual(
            len(re.findall(r'SEUIL_CV_INSTABLE', src)), 3,
            "Le seuil n'est plus partagé entre le libellé et la décision.")
        self.assertEqual(SEUIL_CV_INSTABLE, 0.10)

    # ══════════════════════════════════════════════════════════════════════
    # 2a + SITE 1 — la table et la branche ROUGE lisent la source
    # ══════════════════════════════════════════════════════════════════════

    def test_la_table_des_ronds_a_disparu(self):
        """Les 14 lignes `{'VERT': '🟢', …}` lisent la source unique."""
        import pathlib

        racine = pathlib.Path(__file__).resolve().parent
        restants = []
        for chemin in sorted(racine.rglob('*.py')):
            if chemin.name.startswith('test_') or 'audit_2026_08' in str(chemin):
                continue
            texte = unicodedata.normalize(
                'NFC', chemin.read_text(encoding='utf-8', errors='replace'))
            for i, ligne in enumerate(texte.split('\n'), 1):
                if re.search(r"\{'VERT': '🟢'", ligne):
                    restants.append(f"{chemin.name}:{i}")
        self.assertEqual(restants, [], f"Table(s) de ronds restante(s) : {restants}")

    def test_le_repli_du_statut_inconnu_est_PRESERVE(self):
        """⚠️⚠️ SECOND SENS — `glyphe_rag` rend '' pour un inconnu, les deux
        fonctions de service rendaient '⚪'. Un correctif qui change un
        comportement non demandé est un défaut, même petit."""
        from direction_non_vie.tarification.services import (
            rapport_equipe_tarif,
            rapport_modeles_tarif,
        )

        for mod in (rapport_modeles_tarif, rapport_equipe_tarif):
            fonction = next(
                (v for k, v in vars(mod).items()
                 if callable(v) and 'emoji' in k.lower()), None)
            self.assertIsNotNone(fonction, f"{mod.__name__} : fonction absente")
            self.assertEqual(fonction('VERT'), GLYPHE_RAG['VERT'])
            self.assertEqual(fonction('ROUGE'), GLYPHE_RAG['ROUGE'])
            self.assertEqual(
                fonction('INCONNU'), '⚪',
                "Le repli d'un statut inconnu n'est plus le cercle blanc.")

    def test_la_recommandation_de_monitoring_lit_la_source(self):
        """Site 1 — les deux autres branches du bloc utilisaient déjà le jeu
        commun ; seule celle du ROUGE portait un rond."""
        src = _source('direction_non_vie.tarification.a4_ml.agent')
        self.assertNotIn('"🔴 Ré-entraînement URGENT', src)
        self.assertIn("glyphe_rag('ROUGE')", src)

    # ══════════════════════════════════════════════════════════════════════
    # CE QUI N'EST PAS TOUCHÉ — décision de fond, figée
    # ══════════════════════════════════════════════════════════════════════

    def test_les_legendes_de_FAMILLE_gardent_leurs_ronds(self):
        """⚠️⚠️ Les ronds y encodent un TYPE de modèle, pas un statut. Y mettre
        le glyphe du RAG écrirait un faux. Ce test l'interdit."""
        src5 = _source('direction_non_vie.tarification.a5_deep_learning.agent')
        src6 = _source('direction_non_vie.tarification.a6_comparaison.agent')
        self.assertIn('🔵 Deep Learning', src5)
        self.assertIn('🟡 ML · 🔵 DL', src6)

    def test_les_verdicts_a_trois_bandes_gardent_leurs_ronds(self):
        """⚠️ A/E et stabilité ne sont PAS des RAG : leur imposer ✅⚠️❌
        effacerait la distinction entre un verdict de mesure et un statut
        réglementaire. Décision de fond, pas une prudence."""
        src = _source('direction_non_vie.tarification.a6_comparaison.agent')
        for attendu in ('🟢 Non biaisé', '🔴 Déviation majeure',
                        '🟢 Stable', '🔴 Instable'):
            self.assertIn(attendu, src)


if __name__ == '__main__':
    unittest.main()
