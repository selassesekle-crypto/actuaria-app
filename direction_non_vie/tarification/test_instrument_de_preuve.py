"""
==============================================================================
  P2 -- LES DEUX ANGLES MORTS DE L'INSTRUMENT DE PREUVE
==============================================================================

⚠️⚠️ CES DEUX DEFAUTS NE SE COMPTENT PAS COMME DEUX DE PLUS : ils mettent en
doute les mesures faites avec l'instrument. Tant qu'ils tiennent, « aucun euro
n'a bouge » porte moins loin qu'il ne le dit.

D8 -- LA GATE CHANGEAIT DE VERDICT SELON L'ENCODAGE DE LA CONSOLE
  Mesure du 10/09/2026, chaine reelle, memes donnees :
      console utf-8   ->  A3 success = True    statut = VERT
      console cp1252  ->  A3 success = False   statut = ROUGE
      'charmap' codec can't encode characters in position 1-65
  L'affichage vit DANS le `try` metier de `run()` (releve AST : A3, A4, A5) :
  un incident de RENDU devenait un echec de CALCUL. En cascade, A6 echouait sur
  « Aucun resultat disponible » et le rapport HTML signe n'etait pas produit.
  `TestAssietteDeLaChaine` -- qui porte `GEL-12`/`GEL-13` -- rendait
  `Ran 0 · FAILED` sans executer une seule assertion.

D5 -- LE GEL NE VOYAIT PAS LES FIGURES
  Tromperie refaite le 10/09/2026 sur un livrable REEL : figure remplacee,
  7 983 octets d'ecart, texte identique -> **0 ecart**, et `non_lues` restait
  **AUCUNE**. *Le pire des trois defauts possibles selon la doctrine du module
  lui-meme : il ne voit pas, ET il ne dit pas qu'il ne voit pas.*
  Mesure prealable, avant tout correctif : **31 figures dans 3 livrables
  signes**, deux executions completes, **empreintes identiques** -- hacher ne
  produit aucun faux rouge.

⚠️ `contenu_xlsx` avait le meme angle mort par un AUTRE chemin : openpyxl rend
des CELLULES, et les images d'un classeur vivent dans `xl/media/`.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
==============================================================================
"""
from __future__ import annotations

import ast
import hashlib
import io
import os
import pathlib
import sys
import unittest
import zipfile

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from core.sortie_console import afficher_sans_echouer, console_tolerante
from direction_non_vie.tarification.services import gel_livrables as G

_AGENTS = ('a1_ingestion', 'a2_preprocessing', 'a3_glm', 'a4_ml',
           'a5_deep_learning', 'a6_comparaison')


def _docx(texte: str, figures: dict) -> bytes:
    """Un .docx minimal : un texte, et des figures nommees."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('word/document.xml',
                   '<?xml version="1.0"?><w:document xmlns:w="x"><w:body>'
                   f'<w:p><w:r><w:t>{texte}</w:t></w:r></w:p>'
                   '</w:body></w:document>')
        for nom, octets in figures.items():
            z.writestr(f'word/media/{nom}', octets)
    return tampon.getvalue()


class TestLeRenduConsoleNeCasseRien(unittest.TestCase):
    """⚠️⚠️ D8 -- un incident de RENDU ne peut plus devenir un echec de CALCUL."""

    def test_IP1_LE_SCEAU_un_rendu_impossible_ne_LEVE_pas(self):
        """⚠️⚠️ LE DEFAUT MESURE : sous cp1252, `€ → ═ β` levaient et A3
        rendait `success: False`, statut ROUGE.

        ⚠️ CE CONTROLE TRAVERSE LE VRAI CHEMIN, et il a fallu le corriger pour
        cela : `console_tolerante` reconfigure `sys.stdout`, pas un flux
        quelconque. Un premier jet passait un flux a part -- il mesurait alors
        le SECOND filet (le `except`), jamais le premier (`errors='replace'`),
        et concluait a l'echec sur un mecanisme qui marche. *Un controle qui
        n'emprunte pas le chemin de production ne mesure pas la production.*
        """
        message = 'Prime pure : 1 025 € — β = 0,29 ═══'
        flux = io.TextIOWrapper(io.BytesIO(), encoding='cp1252',
                                errors='strict', newline='')
        # sans filet : ca leve
        with self.assertRaises(UnicodeEncodeError):
            print(message, file=flux)
        # avec filet, SUR LE VRAI FLUX : ca passe, et le calcul continue
        vrai = sys.stdout
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding='cp1252',
                                      errors='strict', newline='')
        try:
            alle_au_bout = afficher_sans_echouer(lambda: print(message))
            sys.stdout.flush()
            rendu = sys.stdout.buffer.getvalue().decode('cp1252')
        finally:
            sys.stdout = vrai
        self.assertTrue(alle_au_bout,
                        "le rendu a ete rattrape alors qu'il aurait du passer "
                        "en `errors=replace`")
        self.assertIn('1 025', rendu,
                      "le rapport a ete perdu au lieu d'etre degrade")
        self.assertIn('?', rendu,
                      "aucun caractere n'a ete remplace : le flux n'a pas ete "
                      "rendu tolerant")
        print(f"    IP-1 SCEAU : rendu cp1252 degrade, pas perdu "
              f"-- {rendu.strip()[:46]}")

    def test_IP2_LE_MIROIR_le_texte_survit_en_utf8(self):
        """⚠️ Sans ce sens, un filet qui avalerait TOUT satisferait IP-1 -- et
        le rapport console ne dirait plus rien."""
        flux = io.TextIOWrapper(io.BytesIO(), encoding='utf-8',
                                errors='strict', newline='')
        message = 'Prime pure : 1 025 € — β = 0,29 ═══'
        self.assertTrue(afficher_sans_echouer(lambda: print(message,
                                                            file=flux)))
        flux.flush()
        rendu = flux.buffer.getvalue().decode('utf-8')
        for signe in ('€', '—', 'β', '═'):
            self.assertIn(signe, rendu, f"'{signe}' perdu en utf-8")
        print("    IP-2 miroir : en utf-8, aucun caractere perdu")

    def test_IP3_le_flux_est_RESTAURE_apres_le_contexte(self):
        """⚠️⚠️ UN CONTEXTE QUI NE RESTAURE PAS laisse le processus dans un
        etat que personne n'a demande -- le prochain appelant heriterait d'un
        flux silencieusement permissif."""
        flux = io.TextIOWrapper(io.BytesIO(), encoding='cp1252',
                                errors='strict', newline='')
        avant = flux.errors
        with console_tolerante(flux):
            self.assertEqual(flux.errors, 'replace')
        self.assertEqual(flux.errors, avant,
                         "le flux n'a pas ete restaure")
        print(f"    IP-3 flux restaure : '{avant}' -> 'replace' -> "
              f"'{flux.errors}'")

    def test_IP4_SEULE_UnicodeEncodeError_est_rattrapee(self):
        """⚠️⚠️ ELARGIR CE FILET A `Exception` FERAIT DISPARAITRE UNE VRAIE
        PANNE DU RENDU dans le meme silence -- la faute que ce module existe
        pour defaire, a l'envers."""
        def casse():
            raise ValueError('vraie panne du rendu')

        with self.assertRaises(ValueError):
            afficher_sans_echouer(casse)
        print("    IP-4 une vraie panne de rendu remonte toujours")

    def test_IP5_LE_SCEAU_les_SIX_agents_posent_le_filet_par_AST(self):
        """⚠️⚠️ LE CORRECTIF DOIT ATTEINDRE LES SIX. Un agent laisse sans filet
        garde la cascade : A6 echoue en aval et le rapport signe est perdu."""
        manquants = []
        for nom in _AGENTS:
            chemin = (pathlib.Path(_RACINE) / 'direction_non_vie'
                      / 'tarification' / nom / 'agent.py')
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            protege = any(
                isinstance(n, ast.Call)
                and getattr(n.func, 'id', None) == 'afficher_sans_echouer'
                for n in ast.walk(arbre))
            if not protege:
                manquants.append(nom)
        self.assertEqual(manquants, [],
                         f"agents sans filet console : {manquants}")
        print(f"    IP-5 SCEAU : les {len(_AGENTS)} agents posent le filet")

    def test_IP6_aucun_appel_console_NU_ne_subsiste_dans_run(self):
        """⚠️ Le filet doit envelopper l'APPEL, pas cohabiter avec lui."""
        nus = []
        for nom in _AGENTS:
            chemin = (pathlib.Path(_RACINE) / 'direction_non_vie'
                      / 'tarification' / nom / 'agent.py')
            texte = chemin.read_text(encoding='utf-8')
            arbre = ast.parse(texte)
            proteges = set()
            for n in ast.walk(arbre):
                if (isinstance(n, ast.Call)
                        and getattr(n.func, 'id', None)
                        == 'afficher_sans_echouer'):
                    for x in ast.walk(n):
                        if (isinstance(x, ast.Call) and
                                getattr(x.func, 'attr', None)
                                == '_afficher_rapport_console'):
                            proteges.add((x.lineno, x.col_offset))
            for n in ast.walk(arbre):
                if (isinstance(n, ast.Call)
                        and getattr(n.func, 'attr', None)
                        == '_afficher_rapport_console'
                        and (n.lineno, n.col_offset) not in proteges):
                    nus.append(f"{nom}:{n.lineno}")
        self.assertEqual(nus, [], f"appels console NON proteges : {nus}")
        print("    IP-6 aucun appel console nu ne subsiste")


class TestLeGelVoitLesFigures(unittest.TestCase):
    """⚠️⚠️ D5 -- l'instrument qui atteste tous les lots regarde enfin les
    figures."""

    def test_IP7_LE_SCEAU_une_figure_changee_est_VUE(self):
        """⚠️⚠️ LA TROMPERIE, REFAITE. Texte identique, figure differente :
        l'instrument rendait 0 ecart."""
        a = _docx('Prime pure totale : 1 025 222,39 EUR',
                  {'image1.png': b'\x89PNG-FIGURE-A' + b'\x00' * 40})
        b = _docx('Prime pure totale : 1 025 222,39 EUR',
                  {'image1.png': b'\x89PNG-FIGURE-B' + b'\x00' * 40})
        self.assertNotEqual(a, b)
        ecarts = G.comparer(G.empreinte({'Word': a}), G.empreinte({'Word': b}))
        self.assertTrue(ecarts,
                        "figure changee a texte identique : 0 ecart -- "
                        "l'instrument est aveugle")
        self.assertIn('figure', ' '.join(str(e) for e in ecarts).lower())
        print(f"    IP-7 SCEAU : figure changee -> {len(ecarts)} ecart(s)")

    def test_IP8_LE_MIROIR_deux_rendus_identiques_ne_rougissent_PAS(self):
        """⚠️⚠️ HACHER UNE FIGURE NON DETERMINISTE FERAIT UN ROUGE PAR RUN, et
        le correctif serait pire que le defaut. Mesure du 10/09/2026 : 31
        figures, deux executions completes, empreintes identiques."""
        figures = {'image1.png': b'\x89PNG-STABLE' + b'\x00' * 30,
                   'image2.png': b'\x89PNG-AUTRE' + b'\x00' * 30}
        a = _docx('Meme texte', figures)
        b = _docx('Meme texte', figures)
        self.assertEqual(
            G.comparer(G.empreinte({'Word': a}), G.empreinte({'Word': b})), [])
        print("    IP-8 miroir : figures identiques -> aucun faux rouge")

    def test_IP9_le_CONTENU_est_hache_jamais_les_octets_bruts(self):
        """⚠️ UN ECART DOIT RENDRE UNE LIGNE, PAS QUARANTE KILO-OCTETS -- et le
        nom de la partie voyage avec elle, comme la coordonnee Excel voyage
        avec sa valeur."""
        octets = b'\x89PNG' + b'\x00' * 5000
        doc = _docx('T', {'image1.png': octets})
        contenu = G.contenu_docx(doc)
        self.assertIn('<figures>', contenu)
        empreinte = contenu['<figures>']['word/media/image1.png']
        self.assertEqual(empreinte, hashlib.sha256(octets).hexdigest())
        self.assertNotIn(b'\x89PNG'.decode('latin-1'), str(contenu))
        print("    IP-9 le contenu est hache, les octets ne voyagent pas")

    def test_IP10_contenu_xlsx_voit_AUSSI_les_figures(self):
        """⚠️⚠️ LE MEME ANGLE MORT PAR UN AUTRE CHEMIN. `openpyxl` rend des
        CELLULES ; les images d'un classeur vivent dans `xl/media/` et ne
        traversent jamais cette lecture.

        ⚠️⚠️ CE CONTROLE EXECUTE, IL NE LIT PLUS LE TEXTE DU CODE. Premier
        jet : un releve AST cherchant `_empreintes_media` dans la source de
        `contenu_xlsx`. Le sceau a plante `if media:` -> `if False:` : l'APPEL
        restait ecrit, le releve restait VERT, et le lecteur etait redevenu
        aveugle. *Une MENTION n'est pas un COMPORTEMENT* -- 13e forme.
        """
        from openpyxl import Workbook
        classeur = Workbook()
        classeur.active['A1'] = 'Prime pure totale'
        tampon = io.BytesIO()
        classeur.save(tampon)
        base = tampon.getvalue()

        def avec_figure(octets_figure):
            sortie = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(base)) as z_in, \
                    zipfile.ZipFile(sortie, 'w', zipfile.ZIP_DEFLATED) as z_o:
                for info in z_in.infolist():
                    z_o.writestr(info, z_in.read(info.filename))
                z_o.writestr('xl/media/image1.png', octets_figure)
            return sortie.getvalue()

        a = avec_figure(b'\x89PNG-FIGURE-A' + b'\x00' * 40)
        b = avec_figure(b'\x89PNG-FIGURE-B' + b'\x00' * 40)
        # ⚠️ LE SENS QUI COMPTE : une figure changee, memes cellules -> ecart
        ecarts = G.comparer(G.empreinte({'Excel': a}),
                            G.empreinte({'Excel': b}))
        self.assertTrue(ecarts,
                        "figure changee a cellules identiques : 0 ecart -- "
                        "`contenu_xlsx` est aveugle aux figures")
        # ⚠️ ET LE MIROIR : deux classeurs identiques ne rougissent pas
        self.assertEqual(
            G.comparer(G.empreinte({'Excel': a}), G.empreinte({'Excel': a})),
            [])
        print(f"    IP-10 SCEAU : figure Excel changee -> {len(ecarts)} "
              f"ecart(s), figures identiques -> 0")


if __name__ == '__main__':
    unittest.main(verbosity=2)
