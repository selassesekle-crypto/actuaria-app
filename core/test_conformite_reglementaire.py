"""CONTRÔLES POSITIFS DU LOT 1.3 — `core/conformite_reglementaire.py`.

⚠️⚠️ CE LOT EST LE SYMÉTRIQUE DU 1.2, ET C'EST CE QUI LE REND DÉLICAT.
En 1.2, le risque était de **laisser passer du faux**. Ici, le risque est de
**détruire du légitime** — et le dépôt a déjà payé ce prix : le BLOQUANT B5,
**−17,4 % de Gini** pour UN seul facteur détruit.

**LE SECOND SENS DE CHAQUE CONTRÔLE EST DONC L'OBJET MÊME DU LOT**, pas une
précaution ajoutée après coup. Chaque classe ci-dessous porte les deux :
ce qui doit être RÉCUPÉRÉ, et ce qui doit RESTER bloqué. Un correctif qui
récupérerait `secteur_activite_imprimerie` en laissant repasser
`garantie_montant_regle` (BLOQUANT B6, Gini 0,0709 → 0,9222) serait pire que
le défaut qu'il corrige.
"""
import os
import sys
import unittest
from typing import ClassVar

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import core.conformite_reglementaire as C


class POS_Conf_C5_LesMotsMetriquesSeTestentEnMOTS(unittest.TestCase):
    """⚠️ `conformite/C5` — le test était une recherche de SOUS-CHAÎNE.

        secteur_activite_imprimerie  ->  'imprimerie' contient 'prime'
        secteur_activite_couture     ->  'couture'    contient 'cout'
        secteur_activite_primeur     ->  'primeur'    contient 'prime'

    Trois secteurs d'activité légitimes détruits parce qu'un mot métrique se
    cachait DANS un autre mot.
    """

    RECUPEREES: ClassVar[tuple] = (
        'secteur_activite_imprimerie', 'secteur_activite_couture',
        'secteur_activite_primeur')
    #: ⚠️ LE SECOND SENS — ce qui doit RESTER détruit, et pourquoi.
    DOIVENT_RESTER_BLOQUEES: ClassVar[dict] = {
        'garantie_montant_regle': 'BLOQUANT B6 — Gini 0,0709 -> 0,9222',
        'garantie_perte_charge': 'charge est un mot entier',
        'garantie_perte_ratio': 'ratio est un mot entier',
        'garantie_montant_perte': 'montant est un mot entier',
    }

    def test_les_faux_positifs_de_sous_chaine_sont_recuperes(self):
        for nom in self.RECUPEREES:
            with self.subTest(colonne=nom):
                self.assertTrue(
                    C.est_facteur_autorise(nom),
                    f"{nom} est detruite : un mot metrique cache DANS un autre "
                    f"mot ne doit pas la condamner")
        print(f"    POS-1.3a {len(self.RECUPEREES)} modalites recuperees "
              f"(sous-chaine -> mot entier) ✅")

    def test_LE_SECOND_SENS_les_vrais_montants_restent_bloques(self):
        """⚠️⚠️ C'EST L'OBJET DU LOT, PAS UNE PRÉCAUTION. Un correctif qui
        récupérerait les faux positifs en rouvrant B6 serait pire que le
        défaut : B6 a fait passer un Gini de 0,0709 à 0,9222 — le modèle
        « expliquait » la sinistralité par le montant réglé."""
        for nom, pourquoi in self.DOIVENT_RESTER_BLOQUEES.items():
            with self.subTest(colonne=nom):
                self.assertFalse(
                    C.est_facteur_autorise(nom),
                    f"{nom} repasse la liste blanche — {pourquoi}")
        print(f"    POS-1.3a LE SECOND SENS : "
              f"{len(self.DOIVENT_RESTER_BLOQUEES)} montants restent bloques ✅")

    def test_le_releve_se_fait_bien_sur_des_MOTS(self):
        """La mesure directe, sans passer par la liste blanche."""
        self.assertEqual(C.mots_metriques_du_suffixe('imprimerie'), [])
        self.assertEqual(C.mots_metriques_du_suffixe('couture'), [])
        self.assertEqual(C.mots_metriques_du_suffixe('montant_regle'),
                         ['montant', 'regle'])
        print("    POS-1.3a le releve porte sur des MOTS, pas des lettres ✅")

    def test_les_temoins_deja_bons_ne_bougent_pas(self):
        """⚠️ LE SECOND SENS, encore : un correctif ne doit pas déplacer ce qui
        allait bien."""
        for nom in ('garantie_incendie', 'carburant_diesel', 'age'):
            with self.subTest(colonne=nom):
                self.assertTrue(C.est_facteur_autorise(nom))
        print("    POS-1.3a les temoins deja bons sont inchanges ✅")


class POS_Conf_C2_C5_LeMotifNommeUneActionQuiEXISTE(unittest.TestCase):
    """⚠️⚠️ LA LEÇON DU BLOQUANT B7 : *une instruction erronée est pire qu'un
    silence.*

    `garantie_perte_exploitation` recevait « *non déclarée comme facteur
    tarifaire légitime — déclarez-la dans `FACTEURS_TARIFAIRES_AUTORISES`* ».
    Or `garantie` **y est déjà déclaré** : suivre l'instruction ne change rien.
    L'actuaire ne pouvait pas s'en sortir.

    Et le contrôle par l'EFFET publiait « exclusion obligatoire, **aucune
    action** » alors qu'une action existe : en RC Pro, l'effectif corrèle
    fortement avec le nombre de sinistres **parce que la relation est réelle et
    connue à la souscription** — la déclarer exemptée au plan la récupère.
    """

    def test_le_motif_metrique_dit_que_la_liste_blanche_ne_sert_a_RIEN(self):
        motif = C.motif_mot_metrique('garantie_perte_exploitation')
        self.assertIsNotNone(motif, "aucun motif specifique n'est produit")
        self.assertIn('ne changera', motif,
                      "le motif n'avertit pas que redeclarer est inutile")
        self.assertIn('PLAN', motif, "le motif ne nomme pas l'action qui MARCHE")
        print("    POS-1.3b le motif nomme l'action qui marche (le PLAN) ✅")

    def test_LE_SECOND_SENS_une_colonne_hors_liste_garde_le_motif_generique(self):
        """⚠️ Le motif précis ne doit pas se substituer au motif générique pour
        une colonne qui, elle, n'a rien à voir avec un mot métrique — sinon on
        remplacerait une instruction erronée par une autre."""
        self.assertIsNone(C.motif_mot_metrique('charge_sinistres_n1'))
        self.assertIsNone(C.motif_mot_metrique('une_colonne_inventee'))
        print("    POS-1.3b LE SECOND SENS : motif generique preserve ailleurs ✅")

    def test_l_exclusion_PAR_L_EFFET_ne_dit_plus_aucune_action(self):
        s = C.synthese_exclusions(
            {'effectif': "FUITE DÉTECTÉE PAR L'EFFET — corrélation de 0.93"})
        self.assertIsNotNone(s)
        self.assertIn('ACTION REQUISE', s)
        self.assertNotIn('aucune action', s,
                         "le controle par l'EFFET dit encore « aucune action » "
                         "— c'est le texte que B7 a juge pire que le silence")
        print("    POS-1.3b l'exclusion par l'EFFET porte une action ✅")

    def test_LE_SECOND_SENS_le_genre_dit_TOUJOURS_aucune_action(self):
        """⚠️⚠️ ET C'EST ESSENTIEL. L'exclusion du genre (CJUE C-236/09) est
        obligatoire et n'admet AUCUNE action de l'actuaire. Donner une action
        ici serait suggérer qu'on peut la contourner."""
        s = C.synthese_exclusions(
            {'sexe': 'genre ou proxy de genre — CJUE C-236/09 (Test-Achats)'})
        self.assertIn('aucune action', s,
                      "le filtre GENRE ne doit JAMAIS suggerer une action")
        self.assertNotIn('ACTION REQUISE', s)
        print("    POS-1.3b LE SECOND SENS : le genre reste sans action ✅")

    def test_chaque_colonne_n_apparait_que_dans_UN_motif(self):
        """⚠️ Le tri se faisait par sous-chaîne indépendante — et ma première
        version de ce correctif classait `garantie_perte_exploitation` dans
        DEUX lignes, son motif contenant les mots « liste blanche ». *Le défaut
        corrigé, reproduit dans le correctif.*"""
        exc = {
            'garantie_perte_exploitation':
                C.motif_mot_metrique('garantie_perte_exploitation'),
            'effectif': "FUITE DÉTECTÉE PAR L'EFFET — corrélation de 0.93",
            'sexe': 'genre ou proxy de genre — CJUE C-236/09 (Test-Achats)',
            'cout_obs': 'dérivée de la sinistralité observée — fuite de données',
            'truc': 'non déclarée comme facteur tarifaire légitime (liste blanche)',
        }
        s = C.synthese_exclusions(exc)
        for col in exc:
            # une colonne est LISTÉE une fois : on compte les occurrences
            # precedees de ': ' ou ', ' (la forme d'une enumeration)
            listee = sum(1 for ligne in s.split('\n')
                         if f": {col}" in ligne or f", {col}" in ligne
                         or f"{col}." in ligne or f"{col}," in ligne)
            with self.subTest(colonne=col):
                self.assertEqual(listee, 1,
                                 f"{col} est listee dans {listee} motifs")
        print("    POS-1.3b chaque colonne dans UN seul motif ✅")


class POS_Conf_C3_LeCheminDeclaratifNeDetruitRIEN(unittest.TestCase):
    """⚠️⚠️ LA MESURE QUI RECADRE LES CONSTATS C3 ET C5.

    Les destructions décrites par C3 et C5 n'ont lieu que sur le chemin
    RÉTROCOMPAT (`plan=None`). Sur le chemin déclaratif — **celui des six
    appelants de production** — la liste blanche est `plan.colonnes_produites()`
    et `est_facteur_autorise` n'est **jamais appelée**.

    ⚠️ Ce test est le garde-fou de cette affirmation : si un jour le chemin
    déclaratif se met à détruire ces colonnes, il échoue.
    """

    COLONNES = ('age', 'garantie_perte_exploitation',
                'secteur_activite_imprimerie', 'charge_sinistres_n1')

    def test_une_colonne_declaree_au_plan_survit_meme_avec_un_mot_metrique(self):
        import numpy as np
        import pandas as pd

        from core.plan_tarifaire import Facteur, PlanTarifaire

        plan = PlanTarifaire(
            lob='rcpro_ctrl', exposition='expo', cible_frequence='nb',
            cible_cout='cout',
            facteurs=(
                Facteur('age', 'continu'),
                Facteur('garantie', 'categoriel', encodage='one_hot',
                        modalites=('incendie', 'perte exploitation'),
                        reference='incendie'),
                Facteur('secteur_activite', 'categoriel', encodage='one_hot',
                        modalites=('batiment', 'imprimerie'),
                        reference='batiment'),
                Facteur('charge_sinistres_n1', 'continu', anteriorite=True),
            ))
        declarees = list(plan.colonnes_produites())
        for c in self.COLONNES:
            self.assertIn(c, declarees, f"le plan de controle ne produit pas {c}")

        rng = np.random.default_rng(0)
        n = 400
        df = pd.DataFrame({c: rng.normal(size=n) for c in declarees})
        df['nb'] = rng.poisson(0.2, n).astype(float)

        mx = C.construire_matrice_x(declarees, contexte='POS-1.3c', df=df,
                                    col_cible='nb', plan=plan)
        retenues = list(mx)
        for c in self.COLONNES:
            with self.subTest(colonne=c):
                self.assertIn(c, retenues,
                              f"{c}, DECLAREE au plan signe, est detruite sur "
                              f"le chemin declaratif — ce n'etait pas le cas")
        self.assertEqual(dict(mx.exclusions), {},
                         f"le chemin declaratif exclut : {dict(mx.exclusions)}")
        print(f"    POS-1.3c chemin declaratif : {len(retenues)} colonnes, "
              f"0 exclusion ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
