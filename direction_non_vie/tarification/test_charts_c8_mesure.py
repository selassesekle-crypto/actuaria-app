# -*- coding: utf-8 -*-
"""
=============================================================================
  LA DESCRIPTION DE `charts/C8` EST-ELLE AU NIVEAU DE LA MESURE ?
=============================================================================

⚠️⚠️ CE FICHIER NE FERME PAS LE CONSTAT -- IL EPINGLE SA DESCRIPTION.

`charts/C8` reste OUVERT : son correctif vit dans `actuaria_app.py`, et
Selasse a arbitre qu'on ne touche pas a l'app Streamlit. Une exemption
declaree dans `test_archive_fermeture_reportee.py` dit exactement cela --
sans elle, `ARCH-1` accuserait ce fichier d'epingler un constat sans bloc
de fermeture, et il aurait raison de le faire.

-----------------------------------------------------------------------------
POURQUOI CE FILET EXISTE
-----------------------------------------------------------------------------
Le constat annoncait UN site et concluait << meme valeur aujourd'hui ; deux
endroits a changer demain >>. Re-mesure le 03/09/2026 :

  - il y a DEUX sites litteraux, pas un ;
  - `CONFIG_PLOTLY` porte DEUX cles, `displayModeBar` ET `responsive` ;
  - les deux sites n'en passent qu'UNE : `responsive: True` est deja perdu,
    et le mot n'apparait nulle part dans l'app.

*Le constat decrivait un risque futur ; la mesure montrait un ecart present.*

  **Une phrase qui affirme MOINS que ce que le code porte est aussi
  trompeuse qu'une qui en affirme plus.**

C'est pourquoi ce filet DERIVE les deux nombres des fichiers eux-memes et
verifie que le releve les porte -- plutot que de les recopier, ce qui
perimerait avec lui.
=============================================================================
"""

import ast
import pathlib
import re
import unittest

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_APP = _RACINE / 'actuaria_app.py'
_CHARTS = _RACINE / 'core' / 'charts_tarif.py'
_RELEVE = (pathlib.Path(__file__).resolve().parent
           / 'audit_2026_08' / 'releve_charts_tarif.md')


def _config_plotly() -> dict:
    """La constante, lue par AST dans le module qui la definit."""
    arbre = ast.parse(_CHARTS.read_text(encoding='utf-8'))
    for n in arbre.body:
        cibles = ([n.target] if isinstance(n, ast.AnnAssign)
                  else getattr(n, 'targets', []))
        if any(getattr(c, 'id', '') == 'CONFIG_PLOTLY' for c in cibles):
            return ast.literal_eval(n.value)
    raise AssertionError(
        "CONFIG_PLOTLY introuvable dans core/charts_tarif.py : ce controle "
        "ne mesure plus ce qu'il croit mesurer.")


def _sites_litteraux() -> list[int]:
    """Les lignes de l'app qui ecrivent `displayModeBar` a la main."""
    return [i for i, l in enumerate(
        _APP.read_text(encoding='utf-8').splitlines(), 1)
        if 'displayModeBar' in l]


class T1_LaMesureQuiFondeLeConstat(unittest.TestCase):
    """Le constat est-il TOUJOURS vrai ? (s'il ne l'est plus, il se ferme)"""

    def test_c8_1_l_app_n_importe_toujours_pas_la_constante(self):
        """C8-1 : le constat decrit encore la realite.

        ⚠️ Si l'app se met a importer `CONFIG_PLOTLY`, ce test tombe -- et
        c'est le signal que le constat doit etre FERME, pas que le filet est
        casse. *Un filet qui ne sait pas dire << c'est corrige >> oblige a
        garder ouvert ce qui ne l'est plus.*
        """
        texte = _APP.read_text(encoding='utf-8')
        self.assertNotIn(
            'CONFIG_PLOTLY', texte,
            "actuaria_app.py importe desormais CONFIG_PLOTLY : `charts/C8` "
            "est corrige et doit etre ferme dans son releve.")

    def test_c8_2_la_cle_responsive_est_bien_PERDUE(self):
        """C8-2 : la divergence est PRESENTE, pas future.

        C'est le fait que le constat taisait.
        """
        cfg = _config_plotly()
        self.assertIn('responsive', cfg,
                      "CONFIG_PLOTLY ne porte plus `responsive` : le constat "
                      "doit etre re-mesure.")
        self.assertNotIn(
            'responsive', _APP.read_text(encoding='utf-8'),
            "l'app mentionne `responsive` : la perte decrite par le constat "
            "n'est plus exacte.")


class T2_LeReleveDitCeQueLaMesureDit(unittest.TestCase):
    """⚠️ L'ASSIETTE : le DOCUMENT, confronte aux FICHIERS."""

    def setUp(self):
        self.texte = _RELEVE.read_text(encoding='utf-8')

    def test_c8_3_le_releve_publie_le_BON_NOMBRE_de_sites(self):
        """C8-3 : le compte publie est le compte mesure.

        ⚠️ Le releve en annoncait UN quand il y en a DEUX. Le nombre est
        derive ici, jamais recopie : un filet qui recopie ce qu'il surveille
        perime avec lui.
        """
        n = len(_sites_litteraux())
        self.assertGreaterEqual(
            n, 1, "plus aucun site litteral : le constat est corrige et doit "
                  "etre ferme.")
        self.assertIn(
            f'le COMPTE, {n},', self.texte,
            f"le releve ne publie pas le compte mesure ({n} sites litteraux "
            f"de `displayModeBar` dans actuaria_app.py).")

    def test_c8_4_le_releve_NOMME_la_cle_perdue(self):
        """C8-4 : la cle absente est nommee, pas resumee.

        ⚠️ Dire << la valeur diverge >> n'aide personne ; dire LAQUELLE
        permet de verifier.
        """
        cfg = _config_plotly()
        app = _APP.read_text(encoding='utf-8')
        perdues = sorted(k for k in cfg if k not in app)
        self.assertTrue(
            perdues, "aucune cle n'est perdue : le constat doit etre ferme.")
        for cle in perdues:
            self.assertIn(
                cle, self.texte,
                f"le releve ne nomme pas la cle perdue « {cle} ».")

    def test_c8_5_le_constat_reste_OUVERT_dans_le_releve(self):
        """C8-5 : corriger la DESCRIPTION ne ferme pas le constat.

        ⚠️⚠️ LE PIEGE QUE CE CONTROLE GARDE. Les blocs ajoutes au releve
        commencent par `>`, comme les blocs de fermeture. S'il s'y glissait
        un `✅`, `_cles_fermees` les lirait comme une FERMETURE et le seul
        constat ouvert de tout l'audit disparaitrait du compte -- sans que
        rien ne soit corrige dans l'app.
        """
        bloc = self.texte.split('**C8 —')[1].split('\n### ')[0]
        fermetures = [l for l in bloc.split('\n')
                      if l.strip().startswith('>') and '✅' in l]
        self.assertFalse(
            fermetures,
            f"un bloc de fermeture s'est glisse dans C8, qui reste OUVERT : "
            f"{fermetures}")
        self.assertTrue(
            re.search(r'reste\s+OUVERT', bloc, re.IGNORECASE),
            "le releve ne dit plus que C8 reste ouvert.")


if __name__ == '__main__':
    unittest.main(verbosity=2)
