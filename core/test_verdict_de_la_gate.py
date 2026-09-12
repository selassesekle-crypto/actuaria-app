# -*- coding: utf-8 -*-
"""LE VERDICT DE LA GATE NE SE LIT PAS N'IMPORTE OU DANS LE FICHIER.

⚠️⚠️ CE SCEAU MANQUAIT, ET C'EST MESURE. Le correctif qui ancre `_verdict`
sur le bloc de synthese d'`unittest` est arrive SANS garde-fou : remettre la
version d'origine -- celle qui rendait `OK` sur une campagne `FAILED` --
laissait la suite entierement VERTE. Plant du 12/09/2026, sur l'arbre
corrige : `_verdict` d'origine remis en entier, `test_a7_console_encodage`
rend « Ran 4 tests / OK ». Rien ne mordait.

CE QUE LE DEFAUT ETAIT. `stdout` est BLOC-bufferise quand la sortie est
redirigee vers un fichier ; `stderr` ne l'est pas. Les `print('OK ...')` des
tests -- le motif d'impression normal de ce depot -- sont donc vides A LA
SORTIE DU PROCESSUS, c'est-a-dire APRES la ligne `FAILED` du lanceur.
L'ancienne lecture gardait la DERNIERE ligne commencant par `OK`, ou qu'elle
tombe : une ligne de test l'emportait sur le verdict.

MESURE QUI L'A ETABLI, sur un run REEL de ce depot, sans rien fabriquer :
deux modules A7 (`test_a7_ibrahim`, `test_a7_colonnes_et_dormants`) lances
en console cp1252 rendent `FAILED (errors=13)` et un code de sortie 1 ;
12 lignes `OK ...` tombent APRES le verdict ; l'ancienne lecture annoncait
« OK -- 86 tests -- code 0 ».

⚠️ CE QUE CE SCEAU VERIFIE, ET CE QU'IL NE VERIFIE PAS. Il porte sur la
PROPRIETE : ce qui suit la synthese ne peut pas changer le verdict. Il
n'atteste ni la mise en forme de la sortie, ni le code de retour du
processus -- ce dernier est un contre-signal verifie ailleurs dans le
lanceur.
"""
import importlib.util
import pathlib
import tempfile
import unittest

_RACINE = pathlib.Path(__file__).resolve().parents[1]
_GATE = _RACINE / 'scripts' / 'gate.py'


def _charger_le_lanceur():
    """Le VRAI module du lanceur, charge par chemin.

    ⚠️ ON N'EN RECOPIE PAS UNE VERSION : recopier reviendrait a mesurer la
    transcription, et ce sceau existe justement parce qu'une lecture peut
    diverger de ce qu'elle croit lire.

    ⚠️ ON GARDE LE MODULE, PAS LA FONCTION. Une fonction rangee en attribut
    de classe se lie `self` au premier appel : `self.verdict(chemin)` passait
    DEUX arguments a `_verdict`, et les dix cas rendaient `TypeError`. Le
    sceau echouait alors sur l'arbre CORRIGE -- c'est ce qui l'a revele.
    """
    spec = importlib.util.spec_from_file_location('_gate_reel', _GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: Chaque cas : (libelle, contenu du fichier de sortie, le verdict EXIGE).
#: `PAS_OK` signifie « n'importe quoi sauf un succes » : l'exigence porte sur
#: le fait de ne PAS rendre vert, pas sur le libelle exact de l'echec.
PAS_OK = object()

CAS = (
    ('vert nu',
     'Ran 12 tests in 1.0s\n\nOK\n', 'OK'),
    ('vert avec sauts',
     'Ran 12 tests in 1.0s\n\nOK (skipped=3)\n', 'OK'),
    ('rouge nu',
     'Ran 12 tests in 1.0s\n\nFAILED (failures=1)\n', 'FAILED'),
    ('rouge suivi du print OK d un test',
     'Ran 12 tests in 1.0s\n\nFAILED (failures=1)\n'
     'OK GEO-1 : quatre formes normales traversent intactes\n', 'FAILED'),
    ('rouge suivi de DOUZE prints, comme le run reel',
     'Ran 86 tests in 120.0s\n\nFAILED (errors=13)\n'
     + ''.join('OK COL-%d : une ligne de test\n' % k for k in range(1, 13)),
     'FAILED'),
    ('processus tue : un print OK, aucune synthese',
     'OK COL-1 : 32 tableaux, aucune colonne morte\n', PAS_OK),
    ('cible vide ou mal orthographiee',
     'Ran 0 tests in 0.0s\n\nNO TESTS RAN\n', PAS_OK),
    ('fichier de sortie vide',
     '', PAS_OK),
    ('deux zones, la seconde rouge',
     'Ran 5 tests in 0.5s\n\nOK\n=== zone 2 ===\n'
     'Ran 7 tests in 0.7s\n\nFAILED (errors=1)\n', 'FAILED'),
    ('un atexit ecrit OK apres la fin',
     'Ran 30 tests in 3.0s\n\nFAILED (errors=2)\n'
     'OK tout est bien qui finit bien\n', 'FAILED'),
)


class T_Le_Verdict_S_Ancre_Sur_La_Synthese(unittest.TestCase):
    """Dix formes de sortie, dont trois qui trompaient la version d'origine."""

    @classmethod
    def setUpClass(cls):
        cls.gate = _charger_le_lanceur()
        cls.dossier = tempfile.mkdtemp(prefix='verdict_gate_')

    def _lire(self, contenu):
        chemin = pathlib.Path(self.dossier) / 'sortie.log'
        chemin.write_text(contenu, encoding='utf-8')
        return self.gate._verdict(chemin)

    def test_GATE_1_le_lanceur_existe(self):
        """Sans lui, tous les autres controles seraient vides de sens."""
        self.assertTrue(
            _GATE.exists(),
            'scripts/gate.py est introuvable : ce sceau ne prouverait rien')
        print('    OK GATE-1 : le lanceur est la (%s)' % _GATE.name)

    def test_GATE_2_les_dix_formes_rendent_le_verdict_exige(self):
        """⚠️ L'EXIGENCE EST NOMMEE PAR CAS, pas globale : un controle qui
        agrege dirait seulement « quelque chose ne va pas »."""
        rendus = []
        for libelle, contenu, exige in CAS:
            with self.subTest(cas=libelle):
                etat, _n = self._lire(contenu)
                if exige is PAS_OK:
                    self.assertNotEqual(
                        etat, 'OK',
                        'cas « %s » : la gate rend OK' % libelle)
                else:
                    self.assertEqual(
                        etat, exige,
                        'cas « %s » : attendu %s, rendu %s'
                        % (libelle, exige, etat))
                rendus.append((libelle, etat))
        print('    OK GATE-2 : %d formes de sortie, %d verdicts conformes'
              % (len(CAS), len(rendus)))

    def test_GATE_3_ce_qui_suit_la_synthese_ne_change_rien(self):
        """LA PROPRIETE, ISOLEE. Le meme run rouge, avec 0, 1, puis 40 lignes
        de print apres le verdict : le verdict ne bouge pas."""
        base = 'Ran 42 tests in 9.0s\n\nFAILED (failures=2)\n'
        reference, n_ref = self._lire(base)
        self.assertEqual(reference, 'FAILED')
        for k in (1, 5, 40):
            queue = ''.join('OK SIG-%d : une ligne bavarde\n' % i
                            for i in range(k))
            etat, n = self._lire(base + queue)
            self.assertEqual(
                etat, reference,
                '%d ligne(s) apres la synthese ont change le verdict '
                '(%s -> %s)' % (k, reference, etat))
            self.assertEqual(n, n_ref, 'le compte de tests a bouge')
        print('    OK GATE-3 : 0, 1, 5 et 40 lignes apres la synthese - '
              'verdict inchange (%s, %d tests)' % (reference, n_ref))

    def test_GATE_4_le_compte_vient_de_la_ligne_Ran_retenue(self):
        """⚠️ UN FAUX « Ran » IMPRIME PAR UN TEST NE DOIT PAS FOURNIR LE
        COMPTE. Il n'est suivi d'aucun jeton de synthese."""
        etat, n = self._lire(
            'Ran 9999 tests in 0.1s\nun test bavard\n'
            'Ran 12 tests in 1.0s\n\nFAILED (failures=2)\n')
        self.assertEqual(etat, 'FAILED')
        self.assertEqual(
            n, 12,
            'le compte a ete pris sur une ligne « Ran » imprimee par un test')
        print('    OK GATE-4 : le faux « Ran 9999 » est ignore, compte = 12')


if __name__ == '__main__':
    unittest.main(verbosity=2)
