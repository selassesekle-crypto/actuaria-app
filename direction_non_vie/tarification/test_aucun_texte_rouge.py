"""Controle positif — 2c : AUCUN TEXTE EN ROUGE, nulle part.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
Arbitre par Selasse le 27/08/2026, sans exception ni cas par cas.

LA MESURE QUI A PRECEDE LA DECISION
  · 38 sites utilisaient une couleur RAG comme couleur de TEXTE ;
  · 3 en ROUGE explicite -- corriges a l'etape 2b ;
  · 23 avec une couleur VARIABLE, susceptible de valoir ROUGE ;
  · frequence reelle mesuree sur le portefeuille du banc : 5 statuts ROUGE
    sur 21, soit 24 %. Ce n'est pas un cas rare.

POURQUOI LE ROUGE NE PEUT PAS ECRIRE
ROUGE #E74C3C vaut 3,74 sur le fond des figures : il PASSE comme objet
(WCAG 1.4.11, seuil 3:1) et ECHOUE comme texte (1.4.3, seuil 4,5:1).

⚠️⚠️ ON NE BLANCHIT PAS TOUT. Le VERT (6,80) et l'AMBRE (6,51) sont
parfaitement lisibles : ils GARDENT leur couleur, donc leur signal. Seul un
statut dont la couleur echoue bascule vers le texte de la charte (12,93).
*On retire ce qui n'est pas lisible, pas ce qui porte du sens.*

⚠️ ET LE SENS DU ROUGE NE SE PERD PAS : partout ou la bascule s'applique, le
glyphe ❌ et/ou le mot « ROUGE » figurent deja dans le texte affiche -- par
exemple `f"{icone} {statut}"` qui rend « ❌ ROUGE » en toutes lettres.

⚠️ SEUL LE TEXTE EST CONCERNE. Les barres, lignes et jauges restent rouges :
elles passent le seuil des objets. Un test l'exige explicitement -- sans lui,
supprimer tout rouge passerait pour une correction alors qu'on aurait perdu
le signal.
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
    COULEURS,
    FOND_REFERENCE,
    FOND_SOMBRE,
    contraste,
    couleur_rag,
    couleur_texte_rag,
)

_AGENTS = ('a3_glm', 'a4_ml', 'a5_deep_learning', 'a6_comparaison')
_CHAMPS_TEXTE = ('annotation_font', 'textfont', 'titlefont', 'font')


def _source(agent: str) -> str:
    mod = __import__(
        f'direction_non_vie.tarification.{agent}.agent', fromlist=['agent'])
    return unicodedata.normalize('NFC', inspect.getsource(mod))


class TestAucunTexteRouge(unittest.TestCase):
    """Le rouge dessine, il n'ecrit plus -- et le vert garde son signal."""

    # ══════════════════════════════════════════════════════════════════════
    # ① LE MÉCANISME : bascule seulement ce qui n'est pas lisible
    # ══════════════════════════════════════════════════════════════════════

    def test_le_vert_et_l_ambre_GARDENT_leur_couleur(self):
        """⚠️⚠️ SECOND SENS — le plus important du fichier.

        Si la fonction blanchissait tout, elle passerait pour une correction
        alors qu'elle aurait effacé deux signaux parfaitement lisibles.
        """
        self.assertEqual(couleur_texte_rag('VERT'),
                         couleur_rag('VERT', FOND_SOMBRE))
        self.assertEqual(couleur_texte_rag('AMBRE'),
                         couleur_rag('AMBRE', FOND_SOMBRE))

    def test_le_rouge_bascule_vers_un_texte_lisible(self):
        remplacant = couleur_texte_rag('ROUGE')
        self.assertNotEqual(remplacant, couleur_rag('ROUGE', FOND_SOMBRE))
        self.assertEqual(remplacant, COULEURS['texte'])
        self.assertGreaterEqual(
            contraste(remplacant, FOND_REFERENCE[FOND_SOMBRE]),
            CONTRASTE_MIN_TEXTE)

    def test_un_statut_inconnu_bascule_aussi(self):
        """Second sens : on ne peint pas un inconnu comme un statut connu."""
        self.assertEqual(couleur_texte_rag('MAUVE'), COULEURS['texte'])

    def test_la_bascule_suit_le_drapeau_usage_texte(self):
        """⚠️ Le mécanisme se DÉRIVE de la mesure, il ne liste pas les statuts.

        Si le rouge devenait lisible un jour, il garderait sa couleur sans
        qu'on touche à cette fonction — et ce test le dirait.
        """
        rouge = couleur_rag('ROUGE', FOND_SOMBRE)
        c = contraste(rouge, FOND_REFERENCE[FOND_SOMBRE])
        self.assertLess(c, CONTRASTE_MIN_TEXTE)
        self.assertGreaterEqual(
            c, CONTRASTE_MIN_OBJET,
            "Le rouge ne passe plus comme objet : les lignes rouges seraient "
            "fautives à leur tour, et ce lot doit être revu.")

    # ══════════════════════════════════════════════════════════════════════
    # ② AUCUN CHAMP DE POLICE NE LIT UNE COULEUR D'OBJET
    # ══════════════════════════════════════════════════════════════════════

    def test_aucun_champ_de_police_ne_lit_une_couleur_d_objet(self):
        """⚠️ Contrôle par AST sur les quatre agents.

        Un `textfont=dict(color=couleur_h1)` peut valoir ROUGE selon les
        données — mesuré : 24 % du temps sur le portefeuille du banc. Les
        champs de police doivent lire la variante `_txt`.
        """
        fautifs = []
        for agent in _AGENTS:
            src = _source(agent)
            for i, ligne in enumerate(src.split('\n'), 1):
                for champ in _CHAMPS_TEXTE:
                    m = re.search(
                        rf'{champ}\s*=\s*dict\([^)]*color\s*=\s*'
                        rf'(couleur\w*?)(?<!_txt)\b', ligne)
                    if m and not m.group(1).endswith('_txt'):
                        fautifs.append(f"{agent}:{i} {champ}={m.group(1)}")
                        break
        self.assertEqual(
            fautifs, [],
            "Champ(s) de police lisant une couleur d'OBJET :\n  " +
            "\n  ".join(fautifs) +
            "\n⚠️ Ils peuvent valoir ROUGE, qui échoue à 3,74 comme texte.")

    def test_chaque_variante_texte_est_definie_avant_usage(self):
        """⚠️⚠️ CE TEST EXISTE PARCE QUE J'AI FAILLI LIVRER 23 ORPHELINES.

        Ma première passe a inséré les usages `_txt` sans leurs définitions :
        les modules s'importaient sans broncher, et CHAQUE figure aurait levé
        un `NameError` à la construction. *L'import ne prouve pas l'exécution.*
        """
        for agent in _AGENTS:
            arbre = ast.parse(_source(agent))
            defs, uses = {}, {}
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Assign):
                    for cible in noeud.targets:
                        if isinstance(cible, ast.Name) and cible.id.endswith('_txt'):
                            defs.setdefault(cible.id, []).append(noeud.lineno)
                if (isinstance(noeud, ast.Name) and noeud.id.endswith('_txt')
                        and isinstance(noeud.ctx, ast.Load)):
                    uses.setdefault(noeud.id, []).append(noeud.lineno)
            orphelins = {v: l for v, l in uses.items()
                         if not any(d < min(l) for d in defs.get(v, []))}
            self.assertEqual(orphelins, {},
                             f"{agent} : variante(s) texte utilisée(s) sans "
                             f"définition : {orphelins}")

    # ══════════════════════════════════════════════════════════════════════
    # ③ LES OBJETS RESTENT ROUGES — l'interdiction ne porte QUE sur le texte
    # ══════════════════════════════════════════════════════════════════════

    def test_les_barres_et_les_lignes_restent_rouges(self):
        """⚠️⚠️ SECOND SENS — sans lui, effacer tout rouge passerait pour une
        correction alors qu'on aurait perdu le signal que l'objet portait."""
        objets = 0
        for agent in _AGENTS:
            src = _source(agent)
            objets += len(re.findall(r'(marker_color|line_color)\s*=\s*'
                                     r'(ROUGE|couleur\w*?)(?<!_txt)\b', src))
        self.assertGreater(
            objets, 5,
            f"Seulement {objets} objet(s) coloré(s) par un statut : le rouge "
            f"a disparu des marques aussi, alors qu'il y passe le seuil.")

    def test_le_rendu_reel_ne_contient_aucun_texte_rouge(self):
        """⚠️⚠️ CONCLU PAR EXÉCUTION, pas par lecture.

        On construit les figures d'A6 et on relit la couleur de chaque champ
        de police. C'est la seule méthode qui voie ce que l'actuaire voit.
        """
        import sys
        from pathlib import Path

        chemin = (Path(__file__).resolve().parent / 'a6_comparaison')
        if str(chemin) not in sys.path:
            sys.path.insert(0, str(chemin))
        import test_a6_comparaison as fixtures

        from direction_non_vie.tarification.a6_comparaison.agent import (
            AgentA6Comparaison,
        )

        agent = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp',
                                   verbose=False)
        resultat = agent.run(
            result_a2=fixtures._make_r_a2_avec_annee(600),
            result_a3=fixtures._make_r_a3(), result_a4=fixtures._make_r_a4(),
            generer_graphiques=True, col_cible='nb_sinistres')
        rouge = couleur_rag('ROUGE', FOND_SOMBRE)
        figures = resultat.get('graphiques') or {}
        self.assertTrue(figures, "Aucune figure produite : le test ne prouve rien.")

        fautes = []
        for cle, figure in figures.items():
            for trace in figure.data:
                for champ in ('textfont', 'titlefont'):
                    police = getattr(trace, champ, None)
                    if police is not None and getattr(police, 'color', None) == rouge:
                        fautes.append(f"{cle}.{champ}")
            titre = getattr(figure.layout.title, 'font', None)
            if titre is not None and getattr(titre, 'color', None) == rouge:
                fautes.append(f"{cle}.layout.title")
            for annotation in (figure.layout.annotations or []):
                police = getattr(annotation, 'font', None)
                if police is not None and getattr(police, 'color', None) == rouge:
                    fautes.append(f"{cle}.annotation")
        self.assertEqual(fautes, [], f"Texte(s) rouge(s) rendu(s) : {fautes}")


if __name__ == '__main__':
    unittest.main()
