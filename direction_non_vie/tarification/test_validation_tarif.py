# -*- coding: utf-8 -*-
"""L'OBJET QUI VEND NE SAVAIT RIEN DE LA QUALITE DE SON MODELE (lot 14).

`TarifNonVie` portait le plan, deux GLM, un ecretement et des chargements --
**aucun Gini, aucun statut, aucune puissance**. Le pouvoir discriminant vivait
chez A3, dans un rapport que le tarif ne lit pas. *Un objet qui produit un prix
sans savoir ce que vaut son modele ne peut pas le dire a celui qui le signe.*

⚠️⚠️ ET IL NE BLOQUE RIEN TOUT SEUL. LA PREMIERE VERSION LE FAISAIT, ET LA
GATE L'A REFUTEE -- c'est la trouvaille la plus importante du lot.

La regle << refuser quand l'intervalle de confiance du Gini de holdout est
entierement sous zero >> a ete cablee, puis mesuree SUR LE CHEMIN OU ELLE
S'APPLIQUE (`pipeline_complet`), 18 plans x 3 tailles :

    1 500 lignes : 2 refus sur 18   (`auto` -0,0900 / 48 sinistres,
                                     `bris_machine` -0,1274 / 47)
    3 000 lignes : 1 refus sur 18   (`rc_produit` -0,1249 / 80)
    4 000 lignes : 0 refus sur 18

***`auto` est REFUSE a 1 500 et ACCEPTE a 3 000 et 4 000 -- meme generateur,
meme graine, meme plan.*** Un verdict qui change avec la TAILLE de
l'echantillon sur les memes donnees mesure du bruit, pas un fait.

Et la cause se mesure, en sinistres d'apprentissage par parametre du GLM de
severite :

    `auto`         :  6,5 -> 13,5 -> 19,8  pour  -0,0900 -> +0,0247 -> +0,0418
    `bris_machine` : 12,9 -> 27,1 -> 37,6  pour  -0,1274 -> -0,0134 -> +0,0313
    `rc_produit`   : 11,3 -> 21,9 -> 27,0  pour  -0,0231 -> -0,1249 -> -0,0577

Les deux premiers sont MONOTONES : sur-apprentissage reel a faible n/p. Le
troisieme est NON MONOTONE : celui-la a tire sur du bruit -- un IC a 95 %
tombe entierement sous zero environ 2,5 % du temps quand le vrai effet est nul,
et on en mesure dix-huit par execution.

**Arbitre par Selasse le 05/09/2026 : on PUBLIE toujours -- Gini, intervalle,
effectif du holdout ET rapport n/p -- et on ne bloque JAMAIS tout seul. Un
blocage dur se declare au PLAN (`refus_anti_selection`, defaut `False`).**

Ce que cette sentinelle exige :
  VT-1   un Gini NEGATIF dont l'IC contient zero -> mention AMBRE, aucun refus ;
  VT-2   ⚠️ un IC ENTIEREMENT sous zero -> mention ROUGE, et TOUJOURS AUCUN
         refus tant que le plan ne l'a pas demande ;
  VT-3   un Gini positif ne dit rien et ne bloque rien ;
  VT-4   `TarifNonVie` PORTE sa validation, et `tarifer()` la publie ;
  VT-5   chaque Gini est publie avec son EFFECTIF et sa PUISSANCE (n/p) ;
  VT-6   trop peu d'observations -> l'IC est DECLARE absent, jamais fabrique ;
  VT-7   une validation NON MESUREE vaut `None`, jamais << aucun defaut >> ;
  VT-8   ⚠️ AUCUN EURO NE BOUGE sur les 18 plans actuels ;
  VT-9   ⚠️ la mention ROUGE est DIAGNOSTICABLE : elle ne conclut pas
         << anti-selection etablie >>, elle porte le n/p et dit ce qu'elle ne
         tranche pas ;
  VT-10  ⚠️⚠️ le blocage dur vient du PLAN et de lui seul -- meme donnee, deux
         plans, deux comportements ;
  VT-11  une puissance NON TRANSMISE se declare, elle ne se remplace pas ;
  VT-12  ⚠️ le Gini de la direction DELEGUE a celui du socle -- il n'y en a
         plus deux, et le socle rend `None` la ou la direction rend `0.0`.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""
import logging
import os
import sys
import unittest
import warnings

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

import numpy as np

from core.validation_tarif import (
    AMBRE,
    MINIMUM_POUR_INTERVALLE,
    ROUGE,
    Discrimination,
    gini_lorenz,
    mesurer_discrimination,
    publication,
    valider,
)


def _d(gini, n, bas=None, haut=None, n_app=None, n_par=None):
    return Discrimination(gini=gini, n_observations=n, ic_bas=bas,
                          ic_haut=haut, n_apprentissage=n_app,
                          n_parametres=n_par)


class TestLaRegleDeCeQuiSePUBLIE(unittest.TestCase):
    """⚠️ Ces tests ne lancent aucun pipeline : ils verifient LA REGLE, sur
    des intervalles construits a la main. C'est elle qui decide de ce qui est
    ecrit dans un livrable signe."""

    def test_VT1_un_gini_negatif_dont_l_IC_CONTIENT_zero_ne_bloque_PAS(self):
        """⚠️⚠️ LE CAS MESURE SUR 10 PLANS SUR 18 a 3 000 lignes. `-0,0028`
        avec un IC de [-0,0736 ; +0,0685] n'etablit rien : le portefeuille ne
        permet pas de distinguer ce Gini de zero. *Le signe d'un point n'est
        pas un fait.*"""
        for gini, bas, haut, n in ((-0.0028, -0.0736, 0.0685, 123),
                                   (-0.0096, -0.0922, 0.0736, 104),
                                   (-0.0264, -0.1032, 0.0538, 68)):
            with self.subTest(gini=gini):
                d = _d(gini, n, bas, haut, n_app=300, n_par=15)
                self.assertFalse(d.ic_entierement_negatif)
                v = valider(severite=d)
                self.assertFalse(
                    v.refuse,
                    f'un Gini de {gini} dont l IC contient zero BLOQUE le '
                    f'tarif : ce serait refuser sur du bruit')
                self.assertEqual(v.niveau_max, AMBRE)
                self.assertIn('NON DISTINGUABLE DE ZERO', v.mentions[0].texte)

    def test_VT2_un_IC_ENTIEREMENT_sous_zero_MENTIONNE_mais_ne_bloque_PAS(self):
        """⚠️⚠️ LE CAS QUI A FAIT ROUGIR LA GATE, ET LA DECISION QUI EN SORT.
        `auto` a 1 500 lignes : -0,0900 sur 48 observations, IC entierement
        sous zero. **Le meme plan a 3 000 lignes rend +0,0247.** On le DIT, on
        ne l'utilise pas pour supprimer un tarif."""
        d = _d(-0.0900, 48, -0.1782, -0.0018, n_app=157, n_par=24)
        self.assertTrue(d.ic_entierement_negatif)
        v = valider(severite=d)
        self.assertFalse(
            v.refuse,
            "un IC entierement sous zero BLOQUE encore : c'est exactement la "
            "regle que la mesure du 05/09/2026 a refutee")
        self.assertEqual(v.niveau_max, ROUGE,
                         "le cas le plus lourd ne ressort pas en ROUGE")
        self.assertEqual(v.mentions[0].grandeur, 'severite')

    def test_VT2b_la_BORNE_de_la_mention_ROUGE_est_le_HAUT_de_l_intervalle(self):
        """⚠️ Le cas limite, et il decide : un IC qui touche zero par le haut
        n'est pas entierement sous zero. *Une borne qui atteint zero n'exclut
        pas zero.*"""
        self.assertFalse(_d(-0.05, 200, -0.10, 0.0).ic_entierement_negatif)
        self.assertTrue(_d(-0.05, 200, -0.10, -1e-9).ic_entierement_negatif)

    def test_VT3_un_gini_POSITIF_ne_dit_rien_et_ne_bloque_rien(self):
        d = _d(0.1489, 500, 0.0677, 0.2260, n_app=400, n_par=20)
        v = valider(frequence=d)
        self.assertFalse(v.refuse)
        self.assertFalse(v.mentions, 'un pouvoir discriminant ETABLI declenche '
                                     'une mention : ce serait du bruit')
        self.assertIsNone(v.niveau_max)
        self.assertTrue(d.distinguable_de_zero)

    def test_VT6_trop_peu_d_observations_l_IC_est_DECLARE_absent(self):
        """⚠️ *Des bornes fabriquees sur douze sinistres seraient plus
        trompeuses que pas de bornes du tout.*"""
        rng = np.random.default_rng(3)
        n = MINIMUM_POUR_INTERVALLE - 1
        d = mesurer_discrimination(rng.gamma(2, 500, n), rng.normal(size=n))
        self.assertIsNone(d.ic_bas)
        self.assertIsNone(d.ic_haut)
        self.assertFalse(d.ic_entierement_negatif,
                         'un IC NON MESURE declenche une mention ROUGE')
        self.assertFalse(d.distinguable_de_zero)
        # ⚠️ Et un Gini sans IC ne declenche NI refus NI mention : on ne dit
        # rien de ce qu'on n'a pas mesure.
        v = valider(severite=d)
        self.assertFalse(v.refuse)
        self.assertFalse(v.mentions)

    def test_VT5_chaque_gini_est_publie_avec_son_EFFECTIF_et_sa_PUISSANCE(self):
        v = valider(frequence=_d(0.15, 500, 0.06, 0.22, n_app=420, n_par=21),
                    severite=_d(-0.03, 176, -0.09, 0.02, n_app=157, n_par=24))
        pub = publication(v)
        for nom in ('frequence', 'severite'):
            with self.subTest(bloc=nom):
                bloc = pub[nom]
                for cle in ('n_observations', 'ic_bas', 'confiance',
                            'n_apprentissage', 'n_parametres',
                            'sinistres_par_parametre'):
                    self.assertIn(cle, bloc, f'{cle} absente de {nom}')
        self.assertEqual(pub['frequence']['n_observations'], 500)
        self.assertEqual(pub['frequence']['sinistres_par_parametre'], 20.0)
        # 157 / 24 = 6,541666... — publie arrondi, pas tronque en entier.
        self.assertEqual(pub['severite']['sinistres_par_parametre'], 6.54)
        self.assertFalse(pub['refuse'])
        self.assertEqual(pub['niveau_max'], AMBRE)

    def test_VT7_une_validation_NON_MESUREE_ne_vaut_pas_conforme(self):
        """⚠️⚠️ `None` se lit « non mesuree », jamais « aucun defaut ».
        C'est la meme regle que partout dans ce chantier."""
        v = valider()
        self.assertFalse(v.refuse)
        pub = publication(v)
        self.assertIsNone(pub['frequence'])
        self.assertIsNone(pub['severite'])
        self.assertIsNone(pub['niveau_max'])

    def test_VT9_la_mention_ROUGE_est_DIAGNOSTICABLE(self):
        """⚠️⚠️ LE POINT DE L'ARBITRAGE. L'ancienne phrase concluait
        << ANTI-SELECTION ETABLIE >> -- un verdict que la donnee ne porte pas,
        puisque le meme plan bascule selon la taille. La nouvelle dit ce qui
        est MESURE, avec la PUISSANCE a cote, et dit ce qu'elle ne tranche
        pas."""
        v = valider(severite=_d(-0.0900, 48, -0.1782, -0.0018,
                                n_app=157, n_par=24))
        texte = v.mentions[0].texte
        self.assertNotIn(
            'ANTI-SELECTION ETABLIE', texte,
            "la mention conclut encore a une anti-selection ETABLIE : c'est le "
            "verdict que la mesure du 05/09/2026 a refute")
        self.assertIn('NE DISCRIMINE PAS SUR HOLDOUT', texte)
        for attendu in ('157 sinistres', '24 parametres',
                        '6.5 sinistres par parametre', 'SUR-APPRENTISSAGE',
                        'NE LES DISTINGUE', "l'actuaire signataire tranche"):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, texte)
        self.assertIn('Aucun tarif n\'est bloque', texte)

    def test_VT10_le_blocage_dur_vient_du_PLAN_et_de_lui_seul(self):
        """⚠️⚠️ MEME DONNEE, DEUX PLANS, DEUX COMPORTEMENTS. C'est le point
        (4) de l'arbitrage : *un seuil qui bloque un tarif ne s'invente pas
        dans le code qui l'applique.*"""
        d = _d(-0.0900, 48, -0.1782, -0.0018, n_app=157, n_par=24)
        sans = valider(severite=d)
        avec = valider(severite=d, refus_anti_selection=True)
        self.assertFalse(sans.refuse, 'le defaut bloque : il ne doit pas')
        self.assertTrue(avec.refuse,
                        "un plan qui DECLARE `refus_anti_selection` ne bloque "
                        "pas : le champ ne sert a rien")
        self.assertIn('BLOCAGE DEMANDE PAR LE PLAN', avec.refus[0])
        # ⚠️ Ce qui bloque doit AUSSI etre lisible par qui n'a pas vu la levee.
        self.assertEqual(avec.niveau_max, ROUGE)
        self.assertEqual(len(avec.mentions), len(sans.mentions))

    def test_VT11_une_puissance_NON_TRANSMISE_se_DECLARE(self):
        """⚠️ Meme regle que partout : une absence se dit. Un n/p manquant ne
        devient pas un chiffre rassurant."""
        v = valider(severite=_d(-0.09, 48, -0.1782, -0.0018))
        texte = v.mentions[0].texte
        self.assertIn("N'A PAS ETE TRANSMIS", texte)
        self.assertIsNone(
            publication(v)['severite']['sinistres_par_parametre'],
            'une puissance non mesuree est publiee comme un nombre')
        self.assertIsNone(_d(-0.09, 48, n_app=157, n_par=0)
                          .sinistres_par_parametre,
                          'zero parametre produit une division, pas une '
                          'absence declaree')

    def test_VT12_le_gini_du_socle_rend_None_et_la_direction_DELEGUE(self):
        """⚠️⚠️ LE NEUVIEME GINI, TROUVE PAR `pipeline/C3`. Il n'y en a plus
        deux : la direction appelle le socle. Ce test verifie les DEUX faces --
        l'identite des valeurs, et la difference ASSUMEE des contrats
        d'absence."""
        from direction_non_vie.tarification.pipeline_tarifaire import (
            gini_lorenz as gini_direction,
        )
        rng = np.random.default_rng(5)
        for n in (200, 2000):
            y = rng.poisson(0.25, n).astype(float)
            # ⚠️ Des EX AEQUO : c'est la ou les tris du depot divergent.
            p = rng.integers(0, 8, n).astype(float) / 8.0
            with self.subTest(n=n):
                self.assertEqual(gini_lorenz(y, p), gini_direction(y, p),
                                 'le socle et la direction ne rendent plus le '
                                 'meme Gini : la delegation est rompue')
        # ⚠️ Le socle DECLARE l'absence ; la direction publie un `float` et
        # convertit A LA FRONTIERE, ce qui est ecrit dans sa docstring.
        vide = np.array([])
        self.assertIsNone(gini_lorenz(vide, vide))
        self.assertIsNone(gini_lorenz(np.zeros(50), rng.random(50)),
                          'une cible de somme nulle rend un ZERO au lieu de '
                          "declarer qu'il n'y a rien a mesurer")
        self.assertEqual(gini_direction(vide, vide), 0.0)


class TestLeTarifPorteSaValidation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)
        from direction_non_vie.tarification import test_pipeline_agents as T
        from direction_non_vie.tarification.pipeline_tarifaire import (
            pipeline_complet,
        )
        np.random.seed(7)
        cls.plan = T._PLAN_AUTO
        cls.df = T._portefeuille_auto(2500)
        cls.tarif = pipeline_complet(cls.df, cls.plan)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_VT4_TarifNonVie_PORTE_sa_validation(self):
        self.assertIsNotNone(
            self.tarif.validation,
            "l'objet qui vend ne mesure toujours rien de lui-meme")
        self.assertIsNotNone(self.tarif.validation.frequence)
        self.assertIsNotNone(self.tarif.validation.severite)

    def test_VT4b_tarifer_PUBLIE_la_validation_ET_sa_puissance(self):
        """⚠️ *Un calcul qui n'atteint aucun livrable n'existe pas.*"""
        contrat = self.df.iloc[0].to_dict()
        r = self.tarif.tarifer(contrat)
        self.assertTrue(r['success'])
        pub = r.get('validation')
        self.assertIsNotNone(pub, "`tarifer()` ne publie pas la validation")
        for nom in ('frequence', 'severite'):
            self.assertIsNotNone(pub[nom], f'{nom} absente de la publication')
            self.assertIn('n_observations', pub[nom])
            self.assertIsNotNone(
                pub[nom]['sinistres_par_parametre'],
                f'{nom} : la PUISSANCE n atteint pas le livrable -- un Gini '
                f'negatif y serait indiagnosticable')
        self.assertIn('mentions', pub)
        self.assertIn('niveau_max', pub)

    def test_VT4c_le_holdout_est_DISTINCT_du_portefeuille_complet(self):
        """⚠️⚠️ La validation doit porter sur des lignes que le modele n'a pas
        vues. Si `n_observations` valait la taille du portefeuille, le Gini
        serait mesure sur les donnees d'apprentissage -- il n'aurait aucune
        valeur de holdout."""
        n_freq = self.tarif.validation.frequence.n_observations
        self.assertLess(
            n_freq, len(self.df),
            'la validation porte sur TOUT le portefeuille : ce n est pas un '
            'holdout')
        self.assertGreater(n_freq, 0)

    def test_VT8_AUCUN_EURO_NE_BOUGE(self):
        """⚠️⚠️ LA CONDITION (4), DEVENUE CONTROLE. Les GLM de PRODUCTION
        restent ajustes sur 100 % : le bloc de validation s'ajoute a cote."""
        primes = np.asarray(
            self.tarif.predire_portefeuille(self.df)['prime_pure'],
            dtype=float)
        self.assertAlmostEqual(
            float(primes.sum()), 1993741.098588, places=2,
            msg='LE TARIF A BOUGE — le bloc de validation devait etre '
                'strictement additif')

    def test_VT1b_le_cas_REEL_du_referentiel_ne_bloque_PAS(self):
        """⚠️ Sur `auto` a 2 500 lignes, la severite mesure un Gini negatif
        dont l'IC contient zero. Il se MENTIONNE, en AMBRE."""
        v = self.tarif.validation
        self.assertFalse(v.refuse, f'le tarif est REFUSE : {v.refus}')
        sev = v.severite
        if sev.gini is not None and sev.gini < 0 and sev.ic_bas is not None:
            self.assertTrue(
                v.mentions,
                'un Gini de severite negatif ne declenche aucune mention')

    def test_VT13_le_plan_qui_DECLARE_le_blocage_bloque_VRAIMENT(self):
        """⚠️⚠️ LE POINT (4) DE BOUT EN BOUT, SUR LE CAS QUE LA GATE A TROUVE.

        `portefeuille_auto(1500)` est EXACTEMENT le jeu qui a fait rougir la
        gate le 05/09/2026 : Gini de severite de holdout -0,0900 sur 48
        observations, IC [-0,1782 ; -0,0018], entierement sous zero.

        *Que `valider()` sache bloquer ne prouve pas que le drapeau du plan
        TRAVERSE le pipeline.* Ce test le fait traverser -- MEME donnee, deux
        plans, deux comportements -- et c'est la seule facon de savoir que le
        point (4) n'est pas une declaration.
        """
        import dataclasses

        from direction_non_vie.tarification import test_plan_invariants as T
        from direction_non_vie.tarification.pipeline_tarifaire import (
            CalculImpossibleBloquant,
            pipeline_complet,
        )
        np.random.seed(7)
        df = T.portefeuille_auto(1500, 1)

        # ① Sans declaration : le tarif SORT, et il porte sa mention ROUGE.
        tarif = pipeline_complet(df, T.AUTO)
        self.assertIsNotNone(tarif.validation)
        sev = tarif.validation.severite
        self.assertIsNotNone(sev, 'la severite du cas mesure n est pas validee')
        self.assertTrue(
            sev.ic_entierement_negatif,
            f"le cas de reference a change : IC [{sev.ic_bas} ; {sev.ic_haut}] "
            f"n'est plus entierement sous zero, ce test ne prouve plus rien")
        self.assertFalse(tarif.validation.refuse,
                         'le defaut bloque encore un tarif')
        from core.validation_tarif import ROUGE as _R
        self.assertEqual(tarif.validation.niveau_max, _R)

        # ② Avec declaration : le MEME jeu ne produit AUCUN tarif.
        plan_bloquant = dataclasses.replace(T.AUTO, refus_anti_selection=True)
        with self.assertRaises(
                CalculImpossibleBloquant,
                msg="`refus_anti_selection` declare au plan ne bloque rien : "
                    "le drapeau ne traverse pas `pipeline_complet`") as leve:
            pipeline_complet(df, plan_bloquant)
        self.assertIn('BLOCAGE DEMANDE PAR LE PLAN', str(leve.exception))

    def test_VT13b_le_drapeau_est_DANS_l_empreinte_du_plan(self):
        """⚠️⚠️ IL DECIDE QU'AUCUN TARIF N'EXISTE : il est opposable, donc
        hache. *Deux plans qui ne different que par lui declareraient la meme
        empreinte a l'audit trail ACPR* -- et le CAC lirait deux runs
        identiques la ou l'un refuse de produire."""
        import dataclasses

        from direction_non_vie.tarification import test_plan_invariants as T
        sans = T.AUTO.empreinte()
        avec = dataclasses.replace(T.AUTO,
                                   refus_anti_selection=True).empreinte()
        self.assertNotEqual(
            sans, avec,
            'deux plans dont un seul BLOQUE la tarification portent la MEME '
            'empreinte : l audit trail les declarerait identiques')

    def test_VT10b_AUCUN_des_20_plans_ne_declare_le_blocage(self):
        """⚠️⚠️ LA PORTEE DU POINT (4), MESUREE ET NON AFFIRMEE. Le champ
        existe ; s'il etait deja declare quelque part, ce lot changerait le
        comportement d'un plan reel sans l'avoir dit."""
        import glob

        from core.plan_tarifaire import PlanTarifaire
        declarants = []
        for chemin in sorted(glob.glob(os.path.join(_RACINE, 'plans',
                                                    '*.yaml'))):
            p = PlanTarifaire.depuis_yaml(chemin)
            if getattr(p, 'refus_anti_selection', False):
                declarants.append(os.path.basename(chemin))
        self.assertEqual(
            declarants, [],
            f'des plans declarent deja le blocage dur : {declarants} -- ce '
            f'lot changerait leur comportement sans que personne l ait decide')


if __name__ == '__main__':
    unittest.main(verbosity=2)
