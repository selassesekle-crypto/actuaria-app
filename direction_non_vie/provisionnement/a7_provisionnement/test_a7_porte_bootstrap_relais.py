# -*- coding: utf-8 -*-
"""LA PORTE DU BOOTSTRAP : ON EPROUVE LE RELAIS, PAS LE DECLENCHEUR.

⚠️⚠️ POURQUOI CE FICHIER EXISTE. Trois sentinelles du depot gardaient cette
porte, et elles se sont ETEINTES — pas rougies, SAUTEES. Mesure du
12/09/2026, apres application des correctifs :

    test_a7_porte_et_marqueur::test_le_retrait_est_NOMME_…          saute
    test_a7_porte_et_marqueur::test_porte_fermee_le_p90_bootstrap_… saute
    test_a7_canal_qualite::test_porte_fermee_le_word_ne_publie_pas… saute
    motif : « ce triangle ne ferme pas la porte »   (0 saut avant)

LA CAUSE EST DECLAREE PAR L'AUDITEUR LUI-MEME. Le correctif D-J applique
Holm-Bonferroni a BOOT-H3 : la porte devient MOINS sensible, et c'est le sens
de l'arbitrage. Sur la fixture historique `_tri_bruite(0.75, graine=9)`,
BOOT-H3 passe de `NON VALIDEE` a `A JUSTIFIER` — d'un cran. Le test ne
trouvait donc plus de porte fermee a garder.

⛔⛔ CE QU'IL NE FALLAIT PAS FAIRE : chercher un triangle plus bruite. Mesure
sur huit couples (bruit 0,75 a 3,00) : plus de bruit ne rend pas
`NON VALIDEE` mais `NON TESTABLE` — le test ne peut plus tourner. Et une
violation de STRUCTURE (ecart-type croissant avec la colonne) rend bien
`NON VALIDEE` sur l'arbre d'origine, mais Holm l'absorbe sur l'arbre corrige.
Faire dependre une sentinelle de la puissance d'un test statistique, c'est
cabler un verdict instable.

CE FICHIER EPROUVE DONC LA PROPRIETE ELLE-MEME : quand la gouvernance dit
« ces percentiles ne sont pas publiables », AUCUN livrable ne les publie. Le
declencheur est POSE, pas espere — on force `percentiles_publiables` et on
relance la chaine aval. La sentinelle ne peut plus s'eteindre.
"""
import copy
import logging
import unittest
import warnings

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement)
from direction_non_vie.provisionnement.a7_provisionnement.n4_best_estimate import (
    BestEstimateS2)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    RAA)

#: ⚠️ ON NE COUPE PAS LES JOURNAUX A L'IMPORT — `core/test_journaux_
#: importables.py::F5_LeDepotEntier` l'interdit pour tout le depot.
_SOURDINE = None


def setUpModule():
    global _SOURDINE
    _SOURDINE = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    warnings.filterwarnings('ignore')


def tearDownModule():
    logging.disable(_SOURDINE)


class T_La_Porte_Fermee_Retire_Les_Percentiles(unittest.TestCase):
    """Un dossier ordinaire, et la gouvernance posee dans les deux positions."""

    #: ⚠️ LE NOM DE CET ATTRIBUT COMPTE. Je l avais appele `cls.run` : il
    #: ECRASE `TestCase.run`, la methode qu unittest appelle pour executer
    #: le test — `TypeError: dict object is not callable`, et AUCUN test ne
    #: tournait. Un attribut de fixture ne doit jamais porter le nom d une
    #: methode du cadre.
    @classmethod
    def setUpClass(cls):
        cls.dossier = AgentA7Provisionnement(verbose=False).run(
            source=np.asarray(RAA, dtype=float), mode_declare='cumule',
            arrete='31/12/2026', ref_client='PBR', generer_graphiques=False,
            generer_word=False, generer_html=False, n_sim_bootstrap=300,
            seed=42)

    def _n4_avec_porte(self, publiables):
        """N4 rejoue avec `percentiles_publiables` POSE a la valeur voulue.

        ⚠️ ON NE TOUCHE QU'A CE DRAPEAU. Le reste de `n2` et tout `n3` sont
        ceux du run reel : si le retrait deplacait autre chose que les
        percentiles Bootstrap, la comparaison le montrerait.
        """
        n2 = copy.deepcopy(self.dossier['n2'])
        n2.setdefault('bootstrap_hyp', {})['percentiles_publiables'] = \
            publiables
        # ⚠️ LE TRIANGLE N EST PAS DANS `n1` — le dict rendu par `run` est la
        # version RAPPORT (alertes, infos, taille…), pas les donnees. On
        # repart donc de l entree, APRES avoir verifie que la porte de
        # geometrie ne l a pas transformee : sur un 10x10 ordinaire elle
        # traverse, et la taille publiee le dit.
        C = np.asarray(RAA, dtype=float)
        self.assertEqual(
            self.dossier['n1']['taille'],
            '%d×%d' % C.shape,   # le module ecrit le signe MULTIPLIE
            'la porte de geometrie a transforme RAA : ce test ne rejouerait '
            'pas N4 sur le meme triangle que le run')
        return BestEstimateS2().calculer(n2, self.dossier['n3'], C)

    def test_PBR_1_la_porte_ouverte_publie_les_trois_percentiles(self):
        """LA PREMISSE. Sans elle, le test suivant passerait sur un dossier
        ou il n'y a simplement rien a retirer."""
        n4 = self._n4_avec_porte(True)
        presents = [c for c in ('reserve_p75_boot', 'reserve_p90_boot',
                                'reserve_p99_5_boot')
                    if n4.get(c) is not None]
        self.assertEqual(
            len(presents), 3,
            'porte OUVERTE et seulement %d percentile(s) Bootstrap publie(s) '
            ': ce dossier ne peut rien prouver sur le retrait' % len(presents))
        print('    OK PBR-1 : porte ouverte, les 3 percentiles sont publies')

    def test_PBR_2_la_porte_fermee_les_retire_TOUS_LES_TROIS(self):
        """⚠️ LES TROIS, PAS LE SEUL P90. La sentinelle historique ne balayait
        que le P90 : c'est ce qui a rendu le P99,5 invisible pendant que le
        commentaire le publiait."""
        n4 = self._n4_avec_porte(False)
        for cle in ('reserve_p75_boot', 'reserve_p90_boot',
                    'reserve_p99_5_boot'):
            with self.subTest(percentile=cle):
                self.assertIsNone(
                    n4.get(cle),
                    'porte FERMEE et %s vaut %s' % (cle, n4.get(cle)))
        print('    OK PBR-2 : porte fermee, les 3 percentiles sont retires')

    def test_PBR_3_le_retrait_ne_deplace_ni_BE_ni_SCR_ni_marge(self):
        """LA CONTRE-EPREUVE. Le retrait est une decision de PUBLICATION : il
        ne doit toucher aucun chiffre de bilan."""
        ouvert = self._n4_avec_porte(True)
        ferme = self._n4_avec_porte(False)
        for cle in ('best_estimate', 'risk_margin', 'scr_prov',
                    'provision_technique_s2'):
            if ouvert.get(cle) is None:
                continue
            with self.subTest(grandeur=cle):
                self.assertEqual(
                    ouvert.get(cle), ferme.get(cle),
                    '%s change avec la porte : %s -> %s'
                    % (cle, ouvert.get(cle), ferme.get(cle)))
        print('    OK PBR-3 : BE, marge de risque et SCR sont inchanges')

    def test_PBR_4_le_document_dit_le_retrait_au_lieu_de_le_taire(self):
        """Un retrait muet se lirait comme « le Bootstrap n'a pas tourne »."""
        from direction_non_vie.provisionnement.a7_provisionnement import (
            n5_commentaire)
        n4 = self._n4_avec_porte(False)
        texte = n5_commentaire.generer_commentaire(
            self.dossier['n1'], self.dossier['n2'], self.dossier['n3'], n4,
            ref_client='PBR')
        self.assertNotIn(
            'Le P99.5 Bootstrap', texte,
            'le commentaire publie le P99,5 alors que la porte est fermee')
        self.assertTrue(
            'retir' in texte.lower() or 'gouvernance' in texte.lower()
            or 'non publi' in texte.lower(),
            'le retrait n est nomme nulle part dans le commentaire')
        print('    OK PBR-4 : le commentaire ne publie plus, et il le dit')


if __name__ == '__main__':
    unittest.main(verbosity=2)
