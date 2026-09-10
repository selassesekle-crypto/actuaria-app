# -*- coding: utf-8 -*-
"""
==============================================================================
  UN CLASSEMENT MUET SUR SA PROPRE STABILITE SE LIT COMME UN CLASSEMENT STABLE
==============================================================================

⚠️⚠️ ARBITRAGE ② DU 10/09/2026. Le document ne publie pas seulement un
vainqueur : il publie le CLASSEMENT ENTIER, scores a quatre decimales. Or cet
ordre depend de la decoupe train/test, non declaree au plan (`C-36`, 0/20).

  Mesure du 10/09, cinq tirages des MEMES donnees :
    · CINQ modeles sur SEPT changent de rang ; deux tiennent le leur ;
    · le PRIX ne bouge pas -- etendue 0,00 EUR.
  Releve independant de l'auditeur sur un catalogue de neuf : 8/9 bougent.
  *Meme nature, meme conclusion : l'essentiel de l'ordre est du bruit.*

⚠️⚠️ ET LE RISQUE N'EST PAS SYMETRIQUE. Attendre ne coute rien tant que le
vainqueur tient ; le jour ou deux candidats se croisent -- la marge relevee
vaut 0,0357 -- le document recommandera un modele different d'un tirage a
l'autre, et ce sera INVISIBLE.

⚠️ CE QUE CE LOT NE FAIT PAS, ET POURQUOI C'EST MESURE. Il ne REEXECUTE pas la
chaine : A6 recoit des metriques deja calculees et ne peut pas refaire les
decoupes. Chronometre : **62,1 s par chaine A1->A6**, donc x5 le temps de
production pour cinq tirages. Ce cout est une decision, pas une redaction. La
mesure se DECLARE donc -- meme patron que `bande` et `decoupe_validation` --
et, tant qu'elle manque, le document le DIT.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import re
import sys
import unittest

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from core.stabilite_du_rang import (
    intervalles_de_rang,
    phrase_stabilite_rang,
)
from direction_non_vie.tarification.services import (
    rapport_modeles_tarif as RM,
)

_A6 = {'success': True, 'branche': 'auto', 'statut_rag': 'VERT',
       'classement': [{'nom': 'GLM_POISSON', 'score_global': 0.91},
                      {'nom': 'ML_XGBOOST', 'score_global': 0.74}]}


class TestLaPhraseDeStabilite(unittest.TestCase):

    def test_SR1_LE_SCEAU_sans_mesure_le_document_DIT_qu_elle_manque(self):
        """⚠️⚠️ LE CONTROLE CENTRAL. Un plant qui rendrait la phrase vide -- ou
        qui la ferait taire quand la mesure manque -- doit faire rougir ceci.
        *Le silence entre un classement et son lecteur se lit comme une
        garantie.*"""
        phrase = phrase_stabilite_rang(None)
        self.assertIn('NON MESUREE', phrase.upper())
        self.assertTrue(phrase.strip())
        # ⚠️ ELLE DIT LES TROIS CHOSES QUI COMPTENT : le fait, son ampleur,
        # et ce qui NE bouge pas.
        self.assertIn('decoupe', phrase.lower())
        self.assertIn('rang', phrase.lower())
        self.assertIn('prix', phrase.lower(),
                      "la phrase doit dire que le PRIX ne bouge pas, sinon "
                      "un lecteur croit son tarif instable")
        print("    SR-1 SCEAU : sans mesure, l'absence est DITE")

    def test_SR2_avec_une_mesure_la_phrase_la_PUBLIE(self):
        """⚠️ Le miroir de SR-1 : une phrase qui dirait TOUJOURS << non
        mesuree >> satisferait SR-1 sans jamais rien publier."""
        phrase = phrase_stabilite_rang(
            {'GLM_POISSON': (1, 1), 'ML_XGBOOST': (3, 7)}, tirages=5)
        self.assertIn('MESUREE', phrase.upper())
        self.assertNotIn('NON MESUREE', phrase.upper())
        self.assertIn('5 tirages', phrase)
        self.assertIn('GLM_POISSON rang 1', phrase)
        self.assertIn('ML_XGBOOST rang 3 a 7', phrase)
        print("    SR-2 avec mesure : les intervalles sont publies")

    def test_SR3_LES_DEUX_FORMATS_publient_la_phrase(self):
        """⚠️⚠️ L'ASYMETRIE ENTRE HTML ET WORD EST LE DEFAUT QUE CE DEPOT A
        PAYE QUATRE FOIS -- mapping, elasticite, qualite des donnees, reserves
        d'A6. Releve PAR AST : les deux exportateurs appellent la meme source
        unique."""
        chemin = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
                  / 'services' / 'rapport_modeles_tarif.py')
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        appelants = set()
        for fonction in ast.walk(arbre):
            if not isinstance(fonction, ast.FunctionDef):
                continue
            for n in ast.walk(fonction):
                if (isinstance(n, ast.Call)
                        and getattr(n.func, 'id', None)
                        == '_stabilite_du_rang'):
                    appelants.add(fonction.name)
        self.assertIn('export_html', appelants)
        self.assertIn('export_word', appelants)
        print(f"    SR-3 les deux exportateurs publient ({sorted(appelants)})")

    def test_SR4_LE_SCEAU_la_phrase_atteint_le_document_REELLEMENT_produit(
            self):
        """⚠️⚠️ PAR EXECUTION, PAS PAR AST. Un appel present dans le code peut
        etre dans une branche que le document n'emprunte pas -- le defaut
        `correctif-a-cote-de-la-surface`, paye six fois ici."""
        html = RM.export_html(result_a6=_A6)
        self.assertIn('STABILITE DU RANG NON MESUREE', html)
        word = RM.export_word(result_a6=_A6)
        self.assertGreater(len(word), 1000)

        avec = {**_A6, 'stabilite_rang': {
            'tirages': 5,
            'intervalles': {'GLM_POISSON': (1, 1), 'ML_XGBOOST': (3, 7)}}}
        html2 = RM.export_html(result_a6=avec)
        self.assertIn('STABILITE DU RANG MESUREE', html2)
        self.assertNotIn('STABILITE DU RANG NON MESUREE', html2)
        print("    SR-4 SCEAU : les DEUX etats atteignent le document rendu")

    def test_SR5_un_modele_ABSENT_d_un_tirage_n_est_pas_au_dernier_rang(self):
        """⚠️⚠️ SUPPOSER LE DERNIER RANG INVENTERAIT UNE DONNEE. Un modele qui
        n'apparait pas dans un tirage n'y a pas de rang -- il n'y est pas.
        Seuls les tirages ou il figure comptent."""
        intervalles = intervalles_de_rang([
            ['A', 'B', 'C'],
            ['A', 'C'],          # B absent de ce tirage
            ['B', 'A', 'C'],
        ])
        self.assertEqual(intervalles['A'], (1, 2))
        self.assertEqual(
            intervalles['B'], (1, 2),
            "B est classe 2 puis 1 : le tirage ou il est ABSENT ne doit pas "
            "lui donner un rang 3 invente")
        self.assertEqual(intervalles['C'], (2, 3))
        # ⚠️ ET UN MODELE ABSENT PARTOUT N'EST PAS DANS LE RESULTAT.
        self.assertNotIn('D', intervalles)
        print("    SR-5 un modele absent d'un tirage n'herite pas d'un rang")

    def test_SR6_CONTRE_EPREUVE_la_phrase_ne_pretend_PAS_la_stabilite(self):
        """⚠️ Une phrase qui publierait les intervalles SANS dire que l'ecart
        de rang n'est pas un ecart de qualite laisserait le lecteur exactement
        ou il etait."""
        phrase = phrase_stabilite_rang(
            {'A': (3, 7), 'B': (1, 5)}, tirages=5)
        self.assertIn('0 modele(s) sur 2 tiennent leur rang', phrase)
        self.assertIn('ne doit PAS se lire comme un ecart de qualite', phrase)
        # ⚠️ ET LE CAS TOTALEMENT STABLE reste dit, sans fausse alarme.
        stable = phrase_stabilite_rang({'A': (1, 1), 'B': (2, 2)}, tirages=5)
        self.assertIn('2 modele(s) sur 2 tiennent leur rang', stable)
        print("    SR-6 contre-epreuve : instable ET stable, tous deux dits")

    def test_SR7_la_phrase_est_REPRODUCTIBLE_mot_pour_mot(self):
        """⚠️ Deux dossiers du meme classement doivent produire la MEME phrase.
        Un ordre de dictionnaire qui fuit rendrait le temoin de gel instable
        et ferait rougir la nocturne sans qu'un euro ait bouge."""
        gauche = phrase_stabilite_rang(
            {'B': (2, 2), 'A': (1, 1), 'C': (3, 9)}, tirages=4)
        droite = phrase_stabilite_rang(
            {'C': (3, 9), 'A': (1, 1), 'B': (2, 2)}, tirages=4)
        self.assertEqual(gauche, droite)
        self.assertLess(gauche.index('A rang 1'), gauche.index('B rang 2'),
                        "l'ordre publie n'est pas celui des rangs")
        print("    SR-7 phrase reproductible, triee par rang")

    def test_SR8_le_cout_qui_JUSTIFIE_la_declaration_est_ECRIT(self):
        """⚠️⚠️ *UNE DECISION DE NE PAS FAIRE SE GARDE, SINON ELLE SE REPREND.*
        Ce lot ne reexecute pas la chaine parce que cela coute x5 -- 62,1 s par
        tirage, mesure. Sans ce chiffre au dossier, un lecteur prend la
        declaration pour de la paresse et cable la reexecution."""
        source = (pathlib.Path(_RACINE) / 'core'
                  / 'stabilite_du_rang.py').read_text(encoding='utf-8')
        self.assertIn('62,1 s', source,
                      "le cout mesure a disparu du module : la decision de "
                      "declarer plutot que de mesurer n'est plus motivee")
        self.assertTrue(
            re.search(r'REEXECUTER|reexecuter', source, re.IGNORECASE),
            "le module ne dit pas ce qu'il faudrait faire pour obtenir la "
            "mesure")
        print("    SR-8 le cout mesure (62,1 s/tirage) motive la declaration")


if __name__ == '__main__':
    unittest.main(verbosity=2)
