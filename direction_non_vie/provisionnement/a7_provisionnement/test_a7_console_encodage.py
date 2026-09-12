# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — LE VERDICT DE LA SUITE NE DEPEND PAS DE LA CONSOLE QUI LA LANCE
=============================================================================

 MESURE D'OUVERTURE, 11/09/2026 — memes 882 tests, meme code, meme machine :

     PYTHONUTF8=1  (ce que `scripts/gate.py` impose)  code 0, « OK »
     console cp1252 (le defaut Windows)               code 1, « FAILED
                                                       (errors=87) »

 Les 87 sont des `UnicodeEncodeError` levees dans des `print` de TESTS. Aucun
 cadre dans un fichier de production : aucun euro ne bouge. Mais une suite qui
 rend deux verdicts opposes selon la console ne prouve pas la meme chose selon
 la console -- et le lanceur, qui force l'encodage favorable, ne peut
 STRUCTURELLEMENT pas voir l'autre.

 CE QUE CE FICHIER FAIT, ET CE QU'IL NE FAIT PAS. Il ne corrige pas les 51
 fichiers : il fait tomber UNE fois, tot, avec le motif et la commande, la ou
 le defaut produisait 87 erreurs opaques. La correction de fond vit dans
 `scripts/gate.py`, qui pose desormais un gestionnaire d'erreur NON STRICT.

 ⚠️⚠️ AUCUNE LISTE DE CARACTERES N'EST ECRITE ICI. Le repertoire est RELEVE
 dans les fichiers du depot a chaque execution : une liste figee serait une
 assiette qui se perime au premier caractere ajoute -- le defaut que ce depot
 a deja paye plusieurs fois.
=============================================================================
"""
import os
import pathlib
import re
import sys
import unittest

_ICI = pathlib.Path(__file__).resolve().parent
_RACINE = _ICI.parents[2]

#: Les repertoires balayes. Le perimetre est celui des tests qui IMPRIMENT.
_ZONES = ('direction_non_vie/provisionnement',
          'direction_non_vie/services')


def _repertoire_hors(codec):
    """Les caracteres employes au voisinage d'un `print`, que `codec` ne sait
    pas representer -- releves DANS LES FICHIERS, jamais ecrits en dur."""
    vus = {}
    for zone in _ZONES:
        base = _RACINE / zone
        if not base.is_dir():
            continue
        for f in base.rglob('*.py'):
            try:
                txt = f.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError):
                continue
            for m in re.finditer(r'print\s*\(', txt):
                for ch in txt[m.start():m.start() + 400]:
                    if ch in vus:
                        continue
                    try:
                        ch.encode(codec)
                    except UnicodeEncodeError:
                        vus[ch] = f.name
    return vus


class T_La_Console_Ne_Decide_Pas_Du_Verdict(unittest.TestCase):

    def test_le_flux_de_sortie_sait_porter_ce_que_la_suite_imprime(self):
        """⚠️⚠️ LE TEST QUI REMPLACE 87 ERREURS OPAQUES PAR UN MOTIF.

        Il ne regarde pas un nom d'encodage : il ESSAIE d'encoder, avec le
        codec ET le gestionnaire d'erreur reels du flux de sortie."""
        flux = sys.stdout
        codec = (getattr(flux, 'encoding', None) or 'utf-8')
        gestion = (getattr(flux, 'errors', None) or 'strict')
        muets = _repertoire_hors(codec)
        if not muets:
            print('    OK ENC-1 la console (%s) porte tout le repertoire'
                  % codec)
            return
        self.assertNotEqual(
            gestion, 'strict',
            "La console est en %s STRICT et la suite imprime %d caractere(s) "
            "qu'elle ne sait pas representer (ex. %s). Chacun leve un "
            "UnicodeEncodeError DANS LE TEST qui l'imprime : mesure du "
            "11/09/2026, 87 erreurs pour 882 tests, alors que le meme code "
            "rend OK sous UTF-8. Relancer ainsi :\n"
            "    set PYTHONIOENCODING=utf-8:backslashreplace\n"
            "ou passer par `py scripts/gate.py <cible>`, qui le pose."
            % (codec, len(muets),
               ' '.join(sorted(muets)[:8])))
        print('    OK ENC-1 %d caractere(s) hors %s, mais le gestionnaire est '
              '« %s » : rien ne peut lever' % (len(muets), codec, gestion))

    def test_le_lanceur_impose_un_gestionnaire_non_strict(self):
        """⚠️ ON LIT LE LANCEUR, PARCE QUE C'EST LUI QUI DECIDE. Un
        `PYTHONUTF8=1` seul choisit l'encodage sans garantir que l'echec
        d'encodage n'existe plus."""
        gate = (_RACINE / 'scripts' / 'gate.py')
        if not gate.exists():
            self.skipTest('scripts/gate.py absent de cet arbre')
        src = gate.read_text(encoding='utf-8')
        self.assertIn('PYTHONIOENCODING', src,
                      "le lanceur ne fixe pas l'encodage de sortie du fils")
        self.assertIn('backslashreplace', src,
                      'le lanceur laisse un gestionnaire STRICT : un print '
                      'peut encore faire tomber un test')
        print('    OK ENC-2 le lanceur impose un gestionnaire non strict')

    def test_le_verdict_publie_ses_conditions_d_encodage(self):
        """⚠️⚠️ UN VERT QUI NE DIT PAS SOUS QUEL ENCODAGE IL A ETE OBTENU N'EST
        PAS RELISABLE — c'est tout le constat D-C.

        ⚠️ ET ON LE MESURE EN LANCANT LE LANCEUR, PAS EN LISANT SON TEXTE. Ma
        premiere version cherchait un motif dans le source : elle est tombee
        des que la ligne de verdict a ete coupee en deux — un controle qui lit
        la PROSE du code et non son comportement, exactement ce que ce depot
        reproche ailleurs a `T5_Une_Panne_N_Est_Pas_Verte`. On lance donc la
        gate sur une cible VIDE : elle doit rendre un code non nul, et sa ligne
        de verdict doit porter l'encodage."""
        import subprocess
        import tempfile
        gate = (_RACINE / 'scripts' / 'gate.py')
        if not gate.exists():
            self.skipTest('scripts/gate.py absent de cet arbre')
        # ⚠️ LA CIBLE EST RELATIVE A LA RACINE, ET LA SORTIE EST DONNEE. Une
        # cible ABSOLUE fait construire au lanceur un nom de fichier invalide
        # sous Windows (`gate_C:\...`) — mesure du 11/09/2026. Ce n'est pas ce
        # que ce test mesure, et l'usage documente passe `--sortie`.
        with tempfile.TemporaryDirectory(dir=str(_RACINE)) as vide:
            rel = pathlib.Path(vide).name
            (pathlib.Path(vide) / '__init__.py').write_text('',
                                                            encoding='utf-8')
            env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
                   'PYTHONIOENCODING': 'utf-8'}
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as t:
                journal = t.name
            r = subprocess.run(
                [sys.executable, '-B', str(gate), rel, '--delai', '120',
                 '--sortie', journal],
                capture_output=True, text=True, encoding='utf-8',
                errors='replace', cwd=str(_RACINE), env=env, timeout=300)
            os.unlink(journal)
        sortie = (r.stdout or '') + (r.stderr or '')
        self.assertIn(
            'sortie utf-8', sortie,
            'la ligne de verdict ne publie pas les conditions d encodage :\n'
            + sortie)
        self.assertIn(
            'backslashreplace', sortie,
            'le gestionnaire publie est STRICT : un print peut encore faire '
            'tomber un test')
        # ⚠️ CONTRE-EPREUVE : une cible VIDE ne doit pas passer pour un succes.
        self.assertNotEqual(r.returncode, 0,
                            'une cible VIDE rend 0 : le lanceur ment')
        print('    OK ENC-3 le verdict publie ses conditions (mesure reelle)')

    def test_le_releve_porte_sur_les_fichiers_et_non_sur_une_liste(self):
        """⚠️⚠️ LA CONTRE-EPREUVE DE L'INSTRUMENT LUI-MEME. Si le releve
        rendait toujours vide, les deux tests precedents passeraient sans rien
        mesurer. On verifie qu'il TROUVE quelque chose sous un codec etroit,
        et RIEN sous un codec total."""
        etroit = _repertoire_hors('ascii')
        self.assertGreater(
            len(etroit), 5,
            'le releve ne trouve rien meme en ASCII : il ne mesure plus les '
            'fichiers (%d)' % len(etroit))
        self.assertEqual(
            _repertoire_hors('utf-8'), {},
            'un caractere echappe a UTF-8 : le releve est casse')
        print('    OK ENC-4 le releve mesure les fichiers (%d hors ASCII)'
              % len(etroit))


if __name__ == '__main__':
    unittest.main(verbosity=1)
