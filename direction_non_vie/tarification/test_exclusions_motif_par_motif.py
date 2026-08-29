"""Controles positifs — lot 1.3b : `conformite/C2` et `conformite/C6`.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
UNE SEULE PROPRIETE : *le seul motif d'exclusion que l'actuaire peut
legitimement contester ne doit pas etre publie comme indiscutable.*

═══ CE QUE J'AI TROUVE EN ALLANT AU SITE ═══

La feuille de route les disait FERMES ; l'archive ne portait aucun bloc de
fermeture. Deux issues etaient possibles -- code jamais corrige, ou code
corrige jamais epingle. Mesure au site le 29/08/2026 :

  ⚠️ LES DEUX SONT DANS LE SECOND CAS : LE CODE EST CORRIGE, RIEN NE L'EPINGLE.

`C2` -- le texte publie dit desormais << ⚠ ACTION REQUISE >>, que l'exclusion
est << MESUREE >> et << ne distingue pas une fuite d'une variable de VOLUME
legitime >>, que l'effectif joue en RC Pro le role de l'exposition en auto, et
il renvoie au PLAN (`anteriorite=True`). Il disait << Exclusion obligatoire,
aucune action >> -- le texte que le BLOQUANT B7 a juge PIRE QUE LE SILENCE.

`C6` -- le tri est devenu EXCLUSIF et ordonne : chaque colonne appartient a UN
seul motif, le premier qui la reconnait. La colonne ecartee PAR L'EFFET a sa
propre ligne, elle n'est plus fondue dans << derivee de la sinistralite,
aucune action >>.

⚠️⚠️ MAIS UN TEXTE ETAIT RESTE FAUX, ET C'ETAIT LA PREUVE CITEE PAR LE CONSTAT.
La docstring de `synthese_exclusions` annoncait << Trois motifs >> alors que le
code en trie CINQ depuis le lot 1.3. *Quand un comportement change, le texte
qui l'accompagne se relit.* Corrige dans ce lot.

⚠️ ET MA PREMIERE SONDE A ACCUSE LE CODE A TORT : j'avais ecrit le motif
`'FUITE DETECTEE PAR L EFFET'` (sans apostrophe) la ou le module teste
`"PAR L'EFFET"`. La colonne retombait dans << aucune action >> et le defaut
semblait vivant. *Une sonde qui invente un motif mesure sa propre invention.*
Les fixtures ci-dessous reprennent les motifs TELS QUE le module les ecrit.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

from core.conformite_reglementaire import synthese_exclusions

_RACINE = pathlib.Path(__file__).resolve().parent.parent.parent

#: Les motifs AUTHENTIQUES, repris du site qui les produit
#: (`construire_matrice_x`, l.1160-1175). ⚠️ Ne pas les paraphraser : le tri se
#: fait par sous-chaine, un motif reecrit ne mesurerait plus le meme code.
_M_GENRE = 'proxy de genre — CJUE C-236/09 (Test-Achats)'
_M_FUITE = ("dérivée de la sinistralité observée — fuite de données, inconnue "
            "au moment de tarifer un contrat neuf")
_M_EFFET = ("FUITE DÉTECTÉE PAR L'EFFET — corrélation de 0.93 avec la cible "
            "nb_sinistres. Aucun facteur tarifaire légitime n'atteint ce "
            "niveau : cette variable EST la cible déguisée, et l'exclusion "
            "est mesurée")
_M_MONNAIE = ("modalité écartée : son nom contient un mot de GRANDEUR "
              "MONÉTAIRE")
_M_BLANCHE = 'non déclarée en liste blanche des facteurs tarifaires'


def _lignes(exclusions) -> list[str]:
    return [x for x in (synthese_exclusions(exclusions) or '').split('\n')
            if x.strip()]


class TestLeMotifContestableEstPublieCommeTel(unittest.TestCase):
    """`conformite/C2` — « aucune action » n'est plus dit d'une mesure."""

    def test_la_colonne_PAR_L_EFFET_appelle_une_ACTION(self):
        """⚠️⚠️ LE TEST QUI FERME `C2`.

        Le motif publié disait « Exclusion obligatoire, aucune action » — le
        texte que B7 a jugé PIRE QUE LE SILENCE, puisqu'une action existe et
        qu'il la niait.
        """
        lignes = _lignes({'effectif': _M_EFFET})
        self.assertEqual(len(lignes), 1)
        self.assertIn('ACTION REQUISE', lignes[0])
        self.assertNotIn('aucune action', lignes[0])
        print("    Q-1 la colonne ecartee PAR L'EFFET appelle une ACTION "
              "(avant : « aucune action »)")

    def test_le_texte_NOMME_ce_que_l_actuaire_doit_verifier(self):
        """⚠️ « Action requise » sans dire laquelle ne vaut guère mieux.

        Le texte doit dire que l'exclusion est MESURÉE, qu'elle ne distingue
        pas une fuite d'un VOLUME légitime, et où déclarer l'exemption.
        """
        ligne = _lignes({'effectif': _M_EFFET})[0]
        for attendu in ('MESURÉE', 'VOLUME', 'anteriorite=True', 'plan'):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, ligne)
        print("    Q-2 le texte nomme la mesure, le cas VOLUME, et le PLAN "
              "comme lieu de l'exemption")

    def test_TEMOIN_les_exclusions_OBLIGATOIRES_gardent_aucune_action(self):
        """⚠️⚠️ SECOND SENS, ET IL EST LE CŒUR DU CONSTAT.

        Le genre et la dérivée de sinistralité SONT indiscutables : leur dire
        « action requise » diluerait le signal que `C2` cherche à rendre
        lisible. *Un correctif qui alerterait sur tout fermerait le constat en
        détruisant l'information.*
        """
        for etiquette, motif in (('genre', _M_GENRE), ('fuite par le nom', _M_FUITE)):
            with self.subTest(motif=etiquette):
                ligne = _lignes({'x': motif})[0]
                self.assertIn('aucune action', ligne)
                self.assertNotIn('ACTION REQUISE', ligne)
        print("    Q-3 temoin : genre et fuite-par-le-nom gardent « aucune "
              "action » — elles sont indiscutables")


class TestChaqueColonneAUnSeulMotif(unittest.TestCase):
    """`conformite/C6` — le tri est exclusif, plus par sous-chaîne partagée."""

    def test_l_EFFET_n_est_plus_fondu_dans_la_derivee_de_sinistralite(self):
        """⚠️⚠️ LE TEST QUI FERME `C6` — la mesure d'origine, rejouée.

        `'fuite' in m.lower()` capturait AUSSI BIEN « dérivée de la
        sinistralité — **fuite** de données » que « **FUITE** DÉTECTÉE PAR
        L'EFFET ». Les deux recevaient le même texte ; une seule le méritait.
        """
        texte = synthese_exclusions({'cout_n1': _M_FUITE,
                                     'zorglub': _M_EFFET}) or ''
        obligatoire = [x for x in texte.split('\n') if 'aucune action' in x]
        self.assertTrue(obligatoire, 'la ligne obligatoire a disparu')
        for x in obligatoire:
            self.assertNotIn('zorglub', x,
                             "la colonne PAR L'EFFET est encore publiee comme "
                             'indiscutable')
        self.assertTrue(any('zorglub' in x and 'ACTION REQUISE' in x
                            for x in texte.split('\n')))
        print("    Q-4 la colonne PAR L'EFFET a sa propre ligne, hors de "
              "« aucune action »")

    def test_les_CINQ_motifs_donnent_CINQ_lignes_distinctes(self):
        """⚠️ Le tri doit séparer les cinq, pas seulement les deux du constat."""
        lignes = _lignes({'sexe_m': _M_GENRE, 'cout_n1': _M_FUITE,
                          'zorglub': _M_EFFET, 'garantie_montant': _M_MONNAIE,
                          'kilometrage': _M_BLANCHE})
        self.assertEqual(len(lignes), 5,
                         f'{len(lignes)} ligne(s) au lieu de 5 : le tri fond '
                         f'des motifs distincts')
        print(f"    Q-5 5 motifs -> {len(lignes)} lignes distinctes")

    def test_AUCUNE_colonne_n_apparait_DEUX_FOIS(self):
        """⚠️⚠️ LE DÉFAUT QUE LE CORRECTIF LUI-MÊME AVAIT REPRODUIT.

        Le commentaire du site le raconte : une première version classait par
        sous-chaîne indépendante, et `garantie_perte_exploitation` ressortait
        dans DEUX lignes — son motif contient « ne changera RIEN — il y est
        déjà » ET les mots « liste blanche ». Le tri est désormais EXCLUSIF.
        """
        colonnes = {'sexe_m': _M_GENRE, 'cout_n1': _M_FUITE,
                    'zorglub': _M_EFFET, 'garantie_montant': _M_MONNAIE,
                    'kilometrage': _M_BLANCHE}
        texte = synthese_exclusions(colonnes) or ''
        for col in colonnes:
            with self.subTest(colonne=col):
                self.assertEqual(
                    texte.count(col), 1,
                    f'« {col} » apparait {texte.count(col)} fois : le tri '
                    f'n est plus exclusif')
        print("    Q-6 chaque colonne apparait exactement UNE fois")

    def test_la_DOCSTRING_ne_dit_plus_TROIS_MOTIFS(self):
        """⚠️⚠️ C'ÉTAIT LA PREUVE CITÉE PAR LE CONSTAT, ET ELLE ÉTAIT RESTÉE
        FAUSSE.

        Le lot 1.3 a rendu le tri exclusif à cinq motifs ; la docstring
        annonçait toujours « Trois motifs ». *Quand un comportement change, le
        texte qui l'accompagne se relit.* Ce test fige la correspondance.

        ⚠️⚠️ ET IL A ÉTÉ CORRIGÉ PAR SON PROPRE ÉCHEC — LA DEUXIÈME FOIS DE LA
        JOURNÉE. Il cherchait l'absence du fragment « Trois motifs » ; or la
        correction le CITE pour raconter ce qui a changé. Le filet ne pouvait
        pas discriminer. Il s'attache désormais à la **phrase qui fait
        autorité** — celle qui introduit la liste — et non à un fragment que
        l'historique reprend. *Un filet qui cherche un fragment que le
        correctif cite lui-même ne mesure rien.*
        """
        chemin = _RACINE / 'core' / 'conformite_reglementaire.py'
        fn = next(n for n in ast.walk(ast.parse(
            chemin.read_text(encoding='utf-8')))
            if isinstance(n, ast.FunctionDef)
            and n.name == 'synthese_exclusions')
        doc = ast.get_docstring(fn) or ''
        self.assertNotIn(
            'Trois motifs, trois niveaux de gravité', doc,
            "la phrase qui ANNONCE la liste dit encore trois motifs")
        self.assertIn('Cinq motifs, trois niveaux de gravité', doc,
                      "la phrase qui annonce la liste ne dit pas cinq motifs")
        self.assertIn('CINQ MOTIFS', doc.upper())
        self.assertIn("PAR L'EFFET", doc,
                      "la docstring ne nomme pas le motif contestable")
        print("    Q-7 la docstring annonce CINQ motifs et nomme le "
              "contestable")

    def test_SECOND_SENS_aucune_exclusion_ne_publie_RIEN(self):
        """⚠️ Une synthèse posée sur tous les dossiers cesserait d'être un
        signal."""
        self.assertIsNone(synthese_exclusions({}))
        self.assertIsNone(synthese_exclusions(None))
        print("    Q-8 second sens : aucune exclusion -> aucun texte")


if __name__ == '__main__':
    unittest.main()
