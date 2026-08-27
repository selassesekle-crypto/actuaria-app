"""Controles positifs — arbitrage 2, etapes 2a et 2b.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
2a — LE GLYPHE N'ETAIT PAS UN AJOUT, C'ETAIT UNE CORRECTION.
Releve par AST : **18 expressions a TROIS glyphes** (correctes) et **7 a
DEUX**. Trois des binaires alimentaient des figures du PLAN DU RAPPORT SIGNE :

    f"{'✅' if statut_g == 'VERT' else '⚠️'} Scores multicriteres..."

Un statut ROUGE affichait donc le glyphe de l'AMBRE, sur `scores_multicriteres`
et `radar_modele_retenu`. *Le second canal existait, et il mentait.*

2b — LA LIGNE RESTE ROUGE, LE TEXTE NON.
ROUGE #E74C3C vaut 3,74 sur le fond des figures : il PASSE comme objet (WCAG
1.4.11, seuil 3:1) et ECHOUE comme texte (1.4.3, seuil 4,5:1). Trois sites
l'utilisaient comme couleur d'annotation.

⚠️⚠️ LES DEUX AUTRES VOIES SONT ECARTEES PAR LA MESURE, PAS PAR GOUT :
  · #C0392B (le rouge des rapports) tombe a 2,63 sur ce fond -- PIRE que
    l'actuel. La voie « reprendre le rouge des rapports » est morte ;
  · inventer un rouge plus clair (#FF6B5A passait a 5,10) serait FABRIQUER une
    couleur -- exactement la faute que le controle de contraste m'avait
    reprochee le matin meme.
La ligne rouge porte deja le sens ; l'etiquette n'a qu'a etre lisible. Le
texte passe au blanc de la charte : 12,93 contre 3,74.

⚠️ L'ASSIETTE REELLE DE CETTE ETAPE EST DE 4 SITES, PAS 13 FIGURES. Sur 19
traductions statut -> couleur, **15 alimentent des figures HORS du plan** --
surtout les scorecards, deja nommees comme question separee. Ma mesure de la
veille (« les 13 figures encodent toutes un statut ») venait d'une fenetre de
90 lignes qui attrapait le code voisin : elle est corrigee.
"""

from __future__ import annotations

import ast
import inspect
import re
import unicodedata
import unittest

from core.charts_tarif import (
    CONTRASTE_MIN_OBJET,
    CONTRASTE_MIN_TEXTE,
    FOND_REFERENCE,
    FOND_SOMBRE,
    contraste,
    couleur_rag,
    glyphe_rag,
)

_AGENTS = ('a3_glm', 'a4_ml', 'a5_deep_learning', 'a6_comparaison')


def _source(agent: str) -> str:
    mod = __import__(
        f'direction_non_vie.tarification.{agent}.agent', fromlist=['agent'])
    return unicodedata.normalize('NFC', inspect.getsource(mod))


class TestSecondCanalFigures(unittest.TestCase):
    """Le glyphe dit les TROIS statuts, et le rouge n'ecrit plus."""

    # ══════════════════════════════════════════════════════════════════════
    # 2a — LE GLYPHE A TROIS ÉTATS
    # ══════════════════════════════════════════════════════════════════════

    def test_le_glyphe_distingue_les_trois_statuts(self):
        self.assertEqual(glyphe_rag('VERT'), '✅')
        self.assertEqual(glyphe_rag('AMBRE'), '⚠️')
        self.assertEqual(
            glyphe_rag('ROUGE'), '❌',
            "Un statut ROUGE ne doit plus emprunter le glyphe de l'AMBRE.")

    def test_aucune_figure_du_plan_ne_porte_un_glyphe_BINAIRE(self):
        """⚠️⚠️ LE TEST QUI FERME 2a.

        Une expression `'✅' if X == 'VERT' else '⚠️'` n'a que DEUX issues :
        le ROUGE y devient AMBRE. On l'interdit dans A6, où les trois sites
        alimentaient des figures du rapport signé.
        """
        src = _source('a6_comparaison')
        binaires = re.findall(
            r"f?\"\{'✅' if \w+ ?== ?'VERT' else '⚠️'\}", src)
        self.assertEqual(
            binaires, [],
            f"Glyphe(s) binaire(s) revenu(s) dans A6 : {binaires}. Un statut "
            f"ROUGE afficherait le glyphe de l'AMBRE sur une figure du plan.")

    def test_les_titres_de_A6_passent_par_la_source_unique(self):
        """Second sens : ce n'est pas seulement « plus de binaire », c'est
        « la source unique ». Un troisième glyphe recopié à la main
        divergerait le jour où la table change."""
        src = _source('a6_comparaison')
        self.assertGreaterEqual(
            len(re.findall(r'glyphe_rag\(', src)), 3,
            "A6 ne lit plus le glyphe à la source unique.")

    # ══════════════════════════════════════════════════════════════════════
    # 2b — LE ROUGE N'ÉCRIT PLUS
    # ══════════════════════════════════════════════════════════════════════

    def test_le_rouge_passe_comme_objet_et_echoue_comme_texte(self):
        """⚠️ Le fait qui motive 2b, remesuré à chaque exécution."""
        rouge = couleur_rag('ROUGE', FOND_SOMBRE)
        c = contraste(rouge, FOND_REFERENCE[FOND_SOMBRE])
        self.assertGreaterEqual(c, CONTRASTE_MIN_OBJET,
                                "Le rouge ne passerait plus comme objet non "
                                "textuel : la ligne rouge deviendrait fautive.")
        self.assertLess(c, CONTRASTE_MIN_TEXTE,
                        f"Le rouge atteint {c} : il passerait désormais comme "
                        f"texte, et l'interdiction n'aurait plus d'objet.")

    def test_les_deux_voies_ecartees_le_sont_PAR_LA_MESURE(self):
        """⚠️⚠️ Second sens du choix de conception, figé.

        Si `#C0392B` devenait acceptable sur ce fond, la décision de 2b
        mériterait d'être rouverte — ce test tomberait et le dirait.
        """
        c = contraste('#C0392B', FOND_REFERENCE[FOND_SOMBRE])
        self.assertLess(
            c, CONTRASTE_MIN_OBJET,
            f"`#C0392B` vaut {c} sur le fond sombre : il ne justifie plus "
            f"d'avoir été écarté.")

    def test_plus_aucune_annotation_n_ecrit_en_ROUGE(self):
        """⚠️ Contrôle par AST sur les quatre agents.

        `annotation_font=dict(color=ROUGE)` écrit un texte à 3,74. La LIGNE
        peut rester rouge — c'est un objet, elle passe à 3:1.
        """
        fautifs = []
        for agent in _AGENTS:
            src = _source(agent)
            for i, ligne in enumerate(src.split('\n'), 1):
                if re.search(r'(annotation_font|textfont|titlefont)\s*=\s*'
                             r'dict\([^)]*color\s*=\s*ROUGE\b', ligne):
                    fautifs.append(f"{agent}:{i}")
        self.assertEqual(
            fautifs, [],
            f"Annotation(s) écrite(s) en ROUGE : {fautifs}. Le rouge vaut "
            f"3,74 — il passe comme ligne, pas comme texte.")

    def test_la_ligne_rouge_est_CONSERVEE(self):
        """⚠️ SECOND SENS — on n'a pas retiré le rouge, on l'a retiré du TEXTE.

        Sans cette assertion, supprimer toute trace de rouge passerait pour
        une correction : on aurait perdu le signal que la ligne portait.
        """
        src = _source('a3_glm')
        self.assertIn('line_color=ROUGE', src,
                      "Les lignes de seuil ne sont plus rouges : le signal "
                      "porté par la couleur a disparu au lieu d'être déplacé.")

    def test_le_remplacant_du_texte_est_largement_lisible(self):
        from core.charts_tarif import COULEURS
        c = contraste(COULEURS['texte'], FOND_REFERENCE[FOND_SOMBRE])
        self.assertGreaterEqual(c, CONTRASTE_MIN_TEXTE)
        self.assertGreater(c, 10.0, f"Contraste du texte tombé à {c}.")

    # ══════════════════════════════════════════════════════════════════════
    # L'ASSIETTE — mesurée, et beaucoup plus petite qu'annoncé
    # ══════════════════════════════════════════════════════════════════════

    def test_l_assiette_mesuree_des_couleurs_de_statut(self):
        """⚠️⚠️ CE TEST A FAIT TOMBER LA GATE — ET IL AVAIT RAISON.

        Il figeait l'assiette à 19 traductions statut→couleur, mesurée le
        27/08. L'étape 2c en a retiré **12** : leurs seuls usages étaient du
        TEXTE, et ce texte lit désormais la variante `_txt`. Une couleur
        d'objet qui ne sert jamais d'objet n'a pas lieu d'être.

        ⚠️⚠️ ET C'EST UN CONSTAT EN SOI : **12 des 19 variables de couleur ne
        coloraient AUCUN objet**. Elles existaient uniquement pour écrire —
        en rouge un quart du temps, mesuré. *Le rouge de ce module servait
        surtout à écrire, pas à dessiner.*

        Le seuil est REBASÉ sur la mesure, avec sa raison — il n'est pas
        affaibli : il tombera encore si l'assiette rebouge.
        """
        objets = variantes = 0
        for agent in _AGENTS:
            arbre = ast.parse(_source(agent))
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.Assign):
                    continue
                cible = ast.unparse(noeud.targets[0])
                valeur = ast.unparse(noeud.value)
                if cible.endswith('_txt') and 'couleur_texte_rag' in valeur:
                    variantes += 1
                elif (isinstance(noeud.value, ast.IfExp)
                        and cible.startswith('couleur')
                        and 'VERT' in valeur and 'ROUGE' in valeur):
                    objets += 1
        self.assertEqual(
            objets, 7,
            f"{objets} couleurs de statut servant encore un OBJET (7 mesurées "
            f"après l'étape 2c, 19 avant). L'assiette a bougé : la re-mesurer "
            f"avant d'étendre l'étape 2.")
        self.assertEqual(
            variantes, 20,
            f"{variantes} variantes TEXTE (20 mesurées). Une variante perdue, "
            f"et un texte redevient susceptible de s'afficher en rouge.")


if __name__ == '__main__':
    unittest.main()
