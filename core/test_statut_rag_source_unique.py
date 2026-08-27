"""Controle positif — la charte RAG a UNE source, et ses contrastes sont MESURES.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
Releve PAR AST avant d'ecrire, le 27/08/2026 : **30 definitions locales** de
VERT/AMBRE/ROUGE dans 7 fichiers, **7 valeurs distinctes**, et AUCUNE source.
Rien ne pouvait verifier ni le contraste, ni la coherence, ni meme quelle
palette s'applique a quel fond.

⚠️ LA PALETTE N'A PAS CHANGE, ET C'EST UNE DECISION MOTIVEE. Remesuree sur les
vraies valeurs de production, elle tient. Le defaut n'etait pas leur valeur --
c'est qu'elles n'etaient tenues par rien.

⚠️⚠️ LE DEFAUT REEL, MESURE : VERT et AMBRE ont un contraste mutuel de 1,04 --
LA MEME LUMINANCE. Seule la teinte les separe. En niveaux de gris, le statut
VERT devient indiscernable de l'AMBRE. C'est la demonstration mesuree qu'un
second canal est necessaire.

⚠️ ET CE CONTROLE A DEJA ATTRAPE UNE FAUTE, AVANT TOUT COMMIT : j'avais ecrit
dans la source une couleur INVENTEE (`#B9770E`, declaree a 4,51, mesuree a
3,68). Le recalcul l'a vue. *Une couleur fabriquee est une valeur fabriquee,
meme quand elle a l'air raisonnable.*

⚠️ CE CONTROLE VERIFIE LA COHERENCE, PAS LA CONFORMITE. `ORANGE #E67E22` des
rapports est a 2,85 -- sous le seuil 3:1. Il est DECLARE non conforme
(`usage_texte=False`, `usage_objet=False`) plutot qu'ajuste : on ne change pas
une couleur de production sans arbitrage, on dit qu'elle ne passe pas.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

from core.charts_tarif import (
    CONTRASTE_MIN_OBJET,
    CONTRASTE_MIN_TEXTE,
    FOND_CLAIR,
    FOND_REFERENCE,
    FOND_SOMBRE,
    GLYPHE_RAG,
    GLYPHE_RAG_EXCEL,
    GLYPHES_SANS_SECOND_CANAL,
    MOTIF_RAG,
    STATUT_RAG,
    SYMBOLE_RAG,
    contraste,
    couleur_rag,
    glyphe_rag,
)

_RACINE = pathlib.Path(__file__).resolve().parents[1]
_PERIMETRE = _RACINE / 'direction_non_vie' / 'tarification'
_ROLES = ('VERT', 'AMBRE', 'ROUGE', 'ORANGE')


class TestStatutRagSourceUnique(unittest.TestCase):
    """Une source, des contrastes recalcules, et aucune definition locale."""

    # ══════════════════════════════════════════════════════════════════════
    # ① LE CONTRASTE DECLARE EST RECALCULE — jamais recopie
    # ══════════════════════════════════════════════════════════════════════

    def test_chaque_contraste_declare_est_exact(self):
        """⚠️ C'est ce test qui a attrapé ma couleur inventée."""
        ecarts = []
        for fond, table in STATUT_RAG.items():
            reference = FOND_REFERENCE[fond]
            for statut, entree in table.items():
                reel = contraste(entree['couleur'], reference)
                if abs(reel - entree['contraste']) >= 0.02:
                    ecarts.append(
                        f"{fond}/{statut} {entree['couleur']} : déclaré "
                        f"{entree['contraste']}, mesuré {reel}")
        self.assertEqual(
            ecarts, [],
            "Contraste(s) déclaré(s) faux :\n  " + "\n  ".join(ecarts) +
            "\n⚠️ Un contraste recopié n'est pas un contraste mesuré.")

    def test_usage_texte_et_usage_objet_suivent_la_MESURE(self):
        """⚠️ Les drapeaux se dérivent du seuil, ils ne s'écrivent pas au juger.

        C'est ce qui rend la non-conformité d'`ORANGE` VISIBLE au lieu de
        silencieuse : elle est déclarée, et la déclaration est vérifiée.
        """
        incoherents = []
        for fond, table in STATUT_RAG.items():
            reference = FOND_REFERENCE[fond]
            for statut, entree in table.items():
                reel = contraste(entree['couleur'], reference)
                if entree['usage_texte'] != (reel >= CONTRASTE_MIN_TEXTE):
                    incoherents.append(f"{fond}/{statut} usage_texte")
                if entree['usage_objet'] != (reel >= CONTRASTE_MIN_OBJET):
                    incoherents.append(f"{fond}/{statut} usage_objet")
        self.assertEqual(incoherents, [], f"Drapeau(x) incohérent(s) : {incoherents}")

    def test_la_non_conformite_connue_reste_DECLAREE(self):
        """⚠️⚠️ `ORANGE #E67E22` est à 2,85 — sous le seuil 3:1.

        Ce test le FIGE. S'il devenait conforme, il tomberait et il faudrait
        le dire ; s'il disparaissait en silence, il tomberait aussi. *Une
        non-conformité connue vaut mieux qu'une non-conformité oubliée.*
        """
        ambre = STATUT_RAG[FOND_CLAIR]['AMBRE']
        self.assertEqual(ambre['couleur'], '#E67E22')
        self.assertFalse(ambre['usage_objet'])
        self.assertFalse(ambre['usage_texte'])
        self.assertLess(contraste(ambre['couleur'], FOND_REFERENCE[FOND_CLAIR]),
                        CONTRASTE_MIN_OBJET)

    def test_le_defaut_qui_justifie_le_second_canal_est_mesure(self):
        """⚠️⚠️ VERT et AMBRE ont la MÊME luminance sur le fond des figures.

        Si un jour ils se séparaient, ce test tomberait — et le second canal
        deviendrait discutable. Tant qu'il passe, il est nécessaire.
        """
        v = couleur_rag('VERT', FOND_SOMBRE)
        a = couleur_rag('AMBRE', FOND_SOMBRE)
        self.assertLess(
            contraste(v, a), 1.15,
            f"VERT et AMBRE se distinguent désormais par la luminance "
            f"({contraste(v, a)}) : la justification du second canal a changé.")

    # ══════════════════════════════════════════════════════════════════════
    # ② PLUS AUCUNE DÉFINITION LOCALE — c'était 30
    # ══════════════════════════════════════════════════════════════════════

    def test_aucune_couleur_RAG_n_est_redefinie_localement(self):
        """⚠️ Contrôle par AST sur tout le périmètre tarification.

        30 définitions locales et 7 valeurs distinctes existaient. Une seule
        qui revient, et plus rien ne peut vérifier le contraste.
        """
        locales = []
        for chemin in sorted(_PERIMETRE.rglob('*.py')):
            if chemin.name.startswith('test_') or 'audit_2026_08' in str(chemin):
                continue
            try:
                arbre = ast.parse(chemin.read_text(encoding='utf-8',
                                                   errors='replace'))
            except (SyntaxError, OSError):
                continue
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.Assign):
                    continue
                for cible in noeud.targets:
                    if (isinstance(cible, ast.Name)
                            and cible.id.split('_')[0] in _ROLES
                            and isinstance(noeud.value, ast.Constant)):
                        locales.append(
                            f"{chemin.name}:{noeud.lineno} {cible.id} = "
                            f"{noeud.value.value!r}")
        self.assertEqual(
            locales, [],
            "Définition(s) locale(s) de couleur RAG :\n  " +
            "\n  ".join(locales) +
            "\n⚠️ Elles doivent venir de `core.charts_tarif.couleur_rag`.")

    def test_un_statut_inconnu_ne_se_peint_pas_comme_un_autre(self):
        """⚠️ `None`, jamais une couleur de repli : un repli serait
        indiscernable d'une valeur mesurée."""
        self.assertIsNone(couleur_rag('MAUVE', FOND_SOMBRE))
        self.assertIsNone(couleur_rag('VERT', 'fond_inexistant'))

    def test_la_forme_sans_diese_sert_l_Excel(self):
        self.assertEqual(couleur_rag('AMBRE', FOND_SOMBRE, avec_diese=False),
                         'F39C12')

    # ══════════════════════════════════════════════════════════════════════
    # ③ LE SECOND CANAL — trois mécanismes, un par type de marque
    # ══════════════════════════════════════════════════════════════════════

    def test_les_trois_canaux_couvrent_les_trois_statuts(self):
        for table, nom in ((MOTIF_RAG, 'motif'), (SYMBOLE_RAG, 'symbole'),
                           (GLYPHE_RAG, 'glyphe'), (GLYPHE_RAG_EXCEL, 'excel')):
            self.assertEqual(set(table), {'VERT', 'AMBRE', 'ROUGE'}, nom)
            self.assertEqual(len(set(table.values())), 3,
                             f"Le canal « {nom} » ne distingue pas les trois "
                             f"statuts : {table}")

    def test_le_glyphe_texte_est_la_convention_DEJA_majoritaire(self):
        """⚠️ 585 occurrences dans 50 fichiers. On adopte, on ne migre pas."""
        self.assertEqual(GLYPHE_RAG, {'VERT': '✅', 'AMBRE': '⚠️', 'ROUGE': '❌'})
        self.assertEqual(glyphe_rag('AMBRE'), '⚠️')
        self.assertEqual(glyphe_rag('AMBRE', cible='excel'), '△')

    def test_les_ronds_colores_sont_nommes_comme_NON_second_canal(self):
        """⚠️⚠️ `🟢🟡🔴` : LARGE GREEN/YELLOW/RED CIRCLE — trois cercles
        identiques. C'est la couleur seule. 230 occurrences, 39 fichiers :
        chantier NOMMÉ, non ouvert. Ce test empêche qu'on les prenne un jour
        pour un second canal."""
        self.assertEqual(GLYPHES_SANS_SECOND_CANAL, ('🟢', '🟡', '🔴'))
        for rond in GLYPHES_SANS_SECOND_CANAL:
            self.assertNotIn(rond, GLYPHE_RAG.values())
            self.assertNotIn(rond, GLYPHE_RAG_EXCEL.values())


if __name__ == '__main__':
    unittest.main()
