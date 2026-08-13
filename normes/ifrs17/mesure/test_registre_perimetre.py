# -*- coding: utf-8 -*-
"""Tests V1 — aucun module de mesure ne peut naître hors du périmètre.

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️⚠️ CE FICHIER EXISTE PARCE QUE LE PÉRIMÈTRE A VIEILLI DEUX FOIS EN UNE
JOURNÉE, et les deux fois de ma main. Un lot de construction était poussé,
et la raison du périmètre continuait de dire « reste à bâtir » alors que le
module existait. Sous-affirmer trompe autant que sur-affirmer : le lecteur
croit devoir refaire un travail déjà fait, ou juge la plateforme plus loin
de son objectif qu'elle ne l'est.

⚠️ CE QUE CE VERROU FAIT, ET CE QU'IL NE FAIT PAS. Il force l'auteur d'un
module neuf à l'inscrire au registre, donc à ouvrir la raison du périmètre
qui le concerne. Il ne peut PAS forcer cette raison à dire vrai. C'est un
rappel mécanique, pas une preuve — et le dire ici évite qu'on le prenne
pour davantage.
"""
import pathlib
import unittest

from normes.ifrs17.mesure import PARAGRAPHE_DES_MODULES
from normes.ifrs17.socle.perimetre import PERIMETRE

#: Les fichiers du paquet qui ne sont pas des modules de mesure.
HORS_MESURE = ('__init__',)


def _modules_sur_le_disque():
    """Ce que le paquet contient VRAIMENT, lu sur le disque.

    ⚠️ SUR LE DISQUE, PAS PAR IMPORT. Un module qui échouerait à s'importer
    disparaîtrait d'un relevé par import — et un module cassé est justement
    celui qu'on veut voir.
    """
    dossier = pathlib.Path(__file__).parent
    return {p.stem for p in dossier.glob('*.py')
            if not p.stem.startswith('test_') and p.stem not in HORS_MESURE}


class V1_LeRegistreEstComplet(unittest.TestCase):
    """V1 — un module non inscrit fait échouer la gate, bruyamment."""

    def test_tout_module_de_mesure_est_inscrit_au_registre(self):
        """⚠️ LE VERROU. Ajouter un module sans l'inscrire echoue ici, et le
        message nomme le module manquant."""
        sur_disque = _modules_sur_le_disque()
        inscrits = set(PARAGRAPHE_DES_MODULES)
        oublies = sorted(sur_disque - inscrits)
        self.assertFalse(
            oublies,
            f"module(s) de mesure non inscrit(s) au registre : {oublies}. "
            f"Inscrivez-le dans `PARAGRAPHE_DES_MODULES` ET relisez la "
            f"raison du perimetre correspondante -- c'est tout l'objet de "
            f"ce verrou : le perimetre a vieilli deux fois faute de cette "
            f"relecture.")
        print(f"    OK V1 : {len(sur_disque)} modules de mesure, tous "
              f"inscrits")

    def test_le_registre_ne_cite_aucun_module_disparu(self):
        """⚠️ L'AUTRE SENS. Un module supprime et laisse au registre ferait
        croire le perimetre plus fourni qu'il ne l'est -- la sur-affirmation
        cette fois."""
        fantomes = sorted(set(PARAGRAPHE_DES_MODULES)
                          - _modules_sur_le_disque())
        self.assertFalse(
            fantomes,
            f"le registre cite {fantomes}, qui n'existe(nt) plus sur le "
            f"disque")
        print("    OK V1b : aucun module fantome au registre")

    def test_chaque_paragraphe_cite_existe_au_perimetre(self):
        """⚠️ SANS CECI, LE REGISTRE POURRAIT POINTER VERS LE VIDE. Inscrire
        un module contre un paragraphe absent du perimetre donnerait
        l'illusion d'un rattachement."""
        connus = {e.reference for e in PERIMETRE}
        for module, paragraphe in sorted(PARAGRAPHE_DES_MODULES.items()):
            self.assertIn(paragraphe, connus,
                          f"{module} pointe vers « {paragraphe} », absent "
                          f"du perimetre publie")
        vises = sorted(set(PARAGRAPHE_DES_MODULES.values()))
        print(f"    OK V1c : les {len(PARAGRAPHE_DES_MODULES)} modules "
              f"pointent vers {len(vises)} elements du perimetre, tous "
              f"existants")

    def test_le_verrou_dit_lui_meme_ce_qu_il_ne_prouve_pas(self):
        """⚠️ UN INSTRUMENT QUI NE DIT PAS SA PORTEE SE FAIT SUREVALUER.
        Ce verrou force a REGARDER la raison du perimetre ; il ne peut pas
        forcer a y ecrire la verite."""
        from normes.ifrs17 import mesure
        doc = mesure.__doc__
        self.assertIn('BRUYAMMENT', doc)
        self.assertIn('CE QU\'IL NE PROUVE PAS', doc)
        # ⚠️ FRAGMENTS COURTS, ET C'EST UNE LECON PAYEE DEUX FOIS DE SUITE.
        # Les retours a la ligne du docstring coupent « rappel / mecanique »
        # puis « se / fait surevaluer » : une assertion qui les traverserait
        # echouerait sur la MISE EN PAGE et non sur le fond -- un test faux
        # pour une raison qui n'interesse personne.
        self.assertIn('pas une preuve', doc)
        self.assertIn('surévaluer', doc)
        print("    OK V1d : le registre publie sa propre portee -- rappel "
              "mecanique, pas preuve")


if __name__ == '__main__':
    unittest.main()
