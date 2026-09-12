"""
==============================================================================
  CHANTIER B+C -- PLUSIEURS PRIX, UN SEUL CRITERE QUI ELIMINE
==============================================================================

⚠️⚠️ LE PIEGE QUE TROIS ANALYSES INDEPENDANTES ONT IDENTIFIE LE MEME JOUR.
Comparer des prix, c'est comparer des CALIBRATIONS avant de comparer des
risques : le rapport predit/observe des candidats du depot va de 0,5508 a
1,2438, un facteur 2,26. Et le coefficient qui rend les prix comparables
masque simultanement tout defaut structurel, puisqu'il ramene chaque candidat
de force au bon total.

  La parade : le coefficient est GELE sur le train et le niveau est mesure sur
  le HOLDOUT. Le recalculer sur le holdout ferait sortir 1 pour n'importe quel
  candidat, par construction -- *un critere qui vaut toujours 1 ne mesure
  rien.*

⚠️⚠️ ET LE COEFFICIENT A DEUX METIERS. Celui de PRODUCTION s'ajuste sur le
portefeuille complet pour que la prime totale reproduise la charge (`INV-8`) :
il ne bouge pas d'un centime. Celui de MESURE, `k_train`, ne touche jamais un
prix publie. Les geler tous les deux aurait fait qu'un tarif livre ne
s'equilibre plus sur les donnees qui l'ont ajuste.

CE QUI EST PUBLIE
  La liste BRUTE des prix des survivants -- pas de classement, pas de note,
  pas de recommandation -- plus UNE colonne : `k_train`. C'est le seul nombre
  que le mecanisme fabrique puis EFFACE du prix affiche.

⚠️ LES CANDIDATS SONT REAJUSTES sur la decoupe DECLAREE au plan, pas repris
d'A4 qui ajuste sur la sienne (`random_state=42`, non declaree). Asseoir une
elimination publiee sur une decoupe non declaree rouvrirait `C-36`.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
==============================================================================
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import os
import pathlib
import sys
import unittest

import numpy as np

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from core.plan_tarifaire import PlanTarifaire
from core.prix_compares import (
    CAUSE_CRITERE,
    CAUSE_SANS_PRIX,
    NATURES,
    AdaptateurTauxFrequence,
    Candidat,
    NatureIncomparable,
    assiette_du_tarif,
    niveau_holdout,
    refuser_assiette_discordante,
    refuser_natures_melangees,
    synthese_comparaison,
)
from core.validation_tarif import DecoupeValidation
from direction_non_vie.tarification import test_plan_invariants as T
from direction_non_vie.tarification.comparaison_prix import (
    CANDIDATS_ML,
    comparer_les_prix,
)
from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
from direction_non_vie.tarification.services.rapport_modeles_tarif import (
    TITRE_COMPARAISON,
    _bloc_comparaison_html,
)

_PLANS = os.path.join(_RACINE, 'plans')


class TestLeCoefficientEstGele(unittest.TestCase):
    """⚠️⚠️ LE CŒUR DU PIEGE, ET SA PARADE."""

    def test_PC1_LE_SCEAU_k_est_GELE_sur_le_train(self):
        """⚠️⚠️ SI `k` ETAIT RECALCULE SUR LE HOLDOUT, LE NIVEAU VAUDRAIT 1
        POUR TOUT LE MONDE. Ce controle plante un candidat volontairement
        mal cale et exige que le niveau le REVELE."""
        rng = np.random.default_rng(7)
        n = 800
        expo = np.ones(n)
        y_tr, y_te = rng.poisson(0.2, n).astype(float), rng.poisson(0.2, n).astype(float)
        # un candidat bien cale sur le train, DERIVANT sur le holdout
        p_tr = np.full(n, y_tr.mean())
        p_te = np.full(n, y_tr.mean() * 1.60)
        k, niveau = niveau_holdout(p_tr, y_tr, expo, p_te, y_te, expo)
        self.assertAlmostEqual(k, 1.0, places=2,
                               msg="le calage du train n'est pas neutre")
        self.assertGreater(
            niveau, 1.35,
            "le niveau ne revele pas la derive : le coefficient a ete "
            "recalcule sur le holdout, et il masque le defaut")
        print(f"    PC-1 SCEAU : k_train={k:.4f} gele, niveau holdout "
              f"{niveau:.4f} -- la derive est VISIBLE")

    def test_PC2_LE_MIROIR_un_candidat_bien_cale_passe(self):
        """⚠️ Sans ce sens, un critere qui refuserait TOUT satisferait PC-1."""
        rng = np.random.default_rng(3)
        n = 1500
        expo = np.ones(n)
        y_tr, y_te = rng.poisson(0.25, n).astype(float), rng.poisson(0.25, n).astype(float)
        p = np.full(n, y_tr.mean())
        _, niveau = niveau_holdout(p, y_tr, expo, p, y_te, expo)
        self.assertAlmostEqual(niveau, 1.0, delta=0.12)
        print(f"    PC-2 candidat bien cale : niveau {niveau:.4f}")

    def test_PC3_le_niveau_NON_MESURABLE_ne_se_devine_pas(self):
        """⚠️ Aucun sinistre sur le holdout : le ratio n'existe pas. On rend
        `nan`, jamais 1 -- une absence de mesure n'est pas une mesure
        reussie."""
        n = 100
        _, niveau = niveau_holdout(np.full(n, 0.2), np.full(n, 0.2),
                                   np.ones(n), np.full(n, 0.2),
                                   np.zeros(n), np.ones(n))
        self.assertTrue(np.isnan(niveau))
        print("    PC-3 niveau non mesurable -> nan, jamais 1")


class TestLaComparabilite(unittest.TestCase):

    def test_PC4_LES_DEUX_SENS_des_natures_MELANGEES_sont_refusees(self):
        """⚠️⚠️ C'EST L'ERREUR DES DEUX BASES DE GINI INCOMPATIBLES, deja
        trouvee et fermee dans ce depot. Un taux et un montant dans le meme
        tableau se lisent comme une seule grandeur."""
        with self.assertRaises(NatureIncomparable) as ctx:
            refuser_natures_melangees((Candidat('a', 'frequence'),
                                       Candidat('b', 'prime_pure')))
        self.assertIn('MÉLANGÉES', str(ctx.exception).upper()
                      .replace('MELANGEES', 'MÉLANGÉES'))
        # ⚠️ ET LE MIROIR : une comparaison homogene passe, sinon le garde
        # refuserait tout sans rien proteger.
        self.assertEqual(
            refuser_natures_melangees((Candidat('a', 'frequence'),
                                       Candidat('b', 'frequence'))),
            'frequence')
        print("    PC-4 natures melangees REFUSEES, natures homogenes ADMISES")

    def test_PC5_les_candidats_du_depot_sont_TOUS_de_nature_declaree(self):
        """⚠️ `xgboost_tweedie` porte un nom trompeur : son objectif est
        `reg:tweedie` mais il est ajuste sur `nb_sinistres`. Il est declare
        pour ce qu'il EST -- une frequence."""
        self.assertEqual({c.nature for c in CANDIDATS_ML}, {'frequence'})
        self.assertIn('xgboost_tweedie', {c.nom for c in CANDIDATS_ML})
        for c in CANDIDATS_ML:
            self.assertIn(c.nature, NATURES)
        print(f"    PC-5 les {len(CANDIDATS_ML)} candidats declarent leur "
              f"nature, tweedie compris")

    def test_PC6_l_adaptateur_REFUSE_une_autre_nature(self):
        """⚠️⚠️ Envelopper un modele de prime pure ferait lire un montant comme
        un taux, puis le remultiplier par l'exposition ET par le cout moyen :
        un prix faux d'un facteur inconnu, sans un mot."""
        with self.assertRaises(NatureIncomparable) as ctx:
            AdaptateurTauxFrequence(object(), ('a',),
                                    Candidat('x', 'prime_pure'))
        self.assertIn('prime_pure', str(ctx.exception))
        print("    PC-6 l'adaptateur refuse une nature qui n'est pas un taux")


class TestLaComparaisonBout_en_bout(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.nu = PlanTarifaire.depuis_yaml(os.path.join(_PLANS, 'auto.yaml'))
        cls.plan = dataclasses.replace(
            cls.nu, decoupe_validation=DecoupeValidation('positionnelle'))
        cls.df = T.portefeuille_auto(2000, 11)
        cls.tarif = pipeline_complet(cls.df, cls.plan)
        # ⚠️⚠️ CAPTURE AVANT LA PREMIERE COMPARAISON, ET C'EST TOUT L'INTERET.
        # Lire l'invariant APRES coup le mesurerait sur un tarif deja abime :
        # un sceau du 08/09/2026 a plante une mutation du coefficient de
        # production et le controle est reste VERT, parce qu'il comparait
        # l'apres a l'apres.
        cls.k_production = cls.tarif.coefficient_equilibre
        cls.frequence_production = cls.tarif.glm_frequence
        cls.sans_bande = comparer_les_prix(cls.tarif, cls.df, cls.plan)
        cls.avec_bande = comparer_les_prix(cls.tarif, cls.df, cls.plan,
                                           bande=(0.85, 1.15))

    def test_PC7_SANS_DECOUPE_DECLAREE_aucune_comparaison(self):
        """⚠️⚠️ Publier des prix sans le filtre reviendrait a publier des prix
        NON FILTRES. Et le refus se dit -- il ne se tait pas."""
        tarif_nu = pipeline_complet(self.df, self.nu)
        c = comparer_les_prix(tarif_nu, self.df, self.nu)
        self.assertEqual(c.resultats, ())
        self.assertIn('AUCUNE COMPARAISON', c.motif_absence)
        self.assertIn('decoupe', c.motif_absence.lower())
        print("    PC-7 sans decoupe declaree : aucune comparaison, et DIT")

    def test_PC8_LE_SCEAU_k_train_est_PUBLIE_a_cote_de_chaque_prix(self):
        """⚠️⚠️ LE SEUL NOMBRE QUE LE MECANISME FABRIQUE PUIS EFFACE. Le prix
        affiche est le prix APRES correction : un candidat corrige par 1,43 et
        un autre par 1,00 produisent des prix qui se ressemblent. Ne pas le
        montrer, c'est publier un prix corrige sans dire de combien."""
        html = _bloc_comparaison_html(self.sans_bande)
        self.assertIn(TITRE_COMPARAISON, html)
        self.assertIn('calage', html.lower())
        for r in self.sans_bande.survivants:
            self.assertIn(f'{r.k_train:.4f}', html,
                          f"le calage de {r.candidat.nom} n'est pas publie")
            self.assertIn(f'{r.somme_prime_pure:,.2f}'.replace(',', ' '), html)
        print(f"    PC-8 SCEAU : les {len(self.sans_bande.survivants)} prix "
              f"publies portent chacun leur coefficient de calage")

    def test_PC9_SANS_BANDE_le_critere_MESURE_mais_n_elimine_pas(self):
        """⚠️⚠️ UNE REGLE QUI BLOQUE SE DECLARE, ELLE NE SE DEVINE PAS. C'est
        le patron de `refus_anti_selection`, et un seuil qui bascule avec la
        taille de l'echantillon mesure du bruit -- la gate l'a deja demontre
        une fois sur ce depot."""
        par_critere = [r for r in self.sans_bande.ecartes
                       if r.cause == CAUSE_CRITERE]
        self.assertEqual(par_critere, [],
                         "un candidat a ete ecarte par le critere alors "
                         "qu'aucune bande n'est declaree")
        for r in self.sans_bande.resultats:
            if r.cause != CAUSE_SANS_PRIX:
                self.assertTrue(np.isfinite(r.niveau_holdout),
                                "le niveau n'est pas mesure")
        self.assertIn('AUCUNE BANDE', self.sans_bande.synthese.upper())
        print("    PC-9 sans bande : mesure et publie, mais n'elimine pas")

    def test_PC10_LE_MIROIR_avec_bande_le_critere_ELIMINE(self):
        """⚠️ Sans ce sens, un critere qui n'eliminerait JAMAIS passerait
        PC-9."""
        par_critere = [r for r in self.avec_bande.ecartes
                       if r.cause == CAUSE_CRITERE]
        self.assertTrue(par_critere,
                        "la bande declaree n'ecarte personne : le critere ne "
                        "mord pas")
        for r in par_critere:
            self.assertIn('bande', r.motif.lower())
            self.assertIsNone(r.somme_prime_pure,
                              "un candidat ecarte publie quand meme un prix")
        print(f"    PC-10 bande declaree : {len(par_critere)} ecarte(s) par le "
              f"critere, sans prix publie")

    def test_PC11_DEUX_CAUSES_distinctes_et_elles_ne_se_confondent_pas(self):
        """⚠️⚠️ `critere_E2` est un CRITERE -- le candidat sait tarifer et
        tarife mal. `sans_prix` est une IMPOSSIBILITE -- il ne tarife pas.
        Mesure du 08/09/2026 : `gbm`, `lightgbm` et `catboost` rendent des
        frequences NEGATIVES, et A4 les ecrete a zero en cinq endroits pour
        ses metriques. *Son Gini decrit un modele ecrete pendant que le modele
        brut ne sait pas tarifer.*"""
        sans_prix = [r for r in self.sans_bande.ecartes
                     if r.cause == CAUSE_SANS_PRIX]
        self.assertTrue(sans_prix,
                        "aucun candidat sans prix : le garde ne mord pas sur "
                        "ce portefeuille, et ce controle ne prouve plus rien")
        for r in sans_prix:
            self.assertRegex(r.motif.upper(), 'NEGATIVE|NON FINIE|AJUSTABLE')
            self.assertIsNone(r.somme_prime_pure)
        self.assertIn('sans prix publiable', self.sans_bande.synthese)
        print(f"    PC-11 {len(sans_prix)} candidat(s) sans prix publiable, "
              f"cause distincte du critere")

    def test_PC12_le_tarif_de_PRODUCTION_ne_bouge_pas(self):
        """⚠️⚠️ `INV-8` EST INTACT. La comparaison remplace le seul modele de
        FREQUENCE ; l'ecretement, le modele de cout et le coefficient
        d'equilibre restent ceux du tarif signe. *Un euro qui bougerait pour
        un besoin de mesure serait le defaut que ce module existe pour
        eviter.*

        ⚠️⚠️ SUR QUELLE ASSIETTE ? Ce controle a DEJA menti une fois. Il lisait
        le coefficient APRES les comparaisons de `setUpClass`, puis rappelait
        avec une bande resserree qui ne laissait AUCUN survivant : le chemin
        de tarification n'etait pas emprunte, la mutation plantee ne
        s'executait pas, et l'apres etait compare a l'apres. *Un controle qui
        s'exerce la ou la violation ne peut pas se produire atteste sans
        surveiller.* Il porte donc maintenant sur la valeur capturee AVANT la
        premiere comparaison, et il exige que des prix aient reellement ete
        calcules.
        """
        # ① l'invariant tient depuis AVANT la premiere comparaison
        self.assertEqual(self.tarif.coefficient_equilibre, self.k_production,
                         "le coefficient d'equilibre de PRODUCTION a bouge "
                         "pendant une comparaison de prix : INV-8 est rompu")
        # ② et il tient sur un appel ou des prix sont VRAIMENT calcules
        c = comparer_les_prix(self.tarif, self.df, self.plan)
        self.assertTrue(c.survivants,
                        "aucun prix calcule : ce controle s'exercerait sur "
                        "une assiette ou la violation ne peut pas survenir")
        self.assertEqual(self.tarif.coefficient_equilibre, self.k_production)
        # ③ le modele de frequence SIGNE n'a pas ete remplace par un
        #    adaptateur de mesure -- c'est la seule piece que la comparaison
        #    substitue, et elle doit la substituer sur une COPIE.
        self.assertIs(self.tarif.glm_frequence, self.frequence_production)
        self.assertNotIsInstance(self.tarif.glm_frequence,
                                 AdaptateurTauxFrequence)
        self.assertIsNotNone(self.tarif.glm_cout)
        print(f"    PC-12 k de production inchange : {self.k_production:.6f} "
              f"({len(c.survivants)} prix calcules entre-temps)")


class TestLAssietteDeLaComparaison(unittest.TestCase):
    """⚠️⚠️ `D-2` — LA COMPARAISON PORTE SUR LES LIGNES AJUSTEES, OU SUR RIEN.

    ⚠️⚠️ CES CONTROLES TIENNENT UNE PROPRIETE, JAMAIS UN MONTANT -- et c'est
    delibere. Le chantier `D-1` va changer la source dont le tarif est
    construit : tout euro fige ici serait faux des le lot suivant. *Ce qui doit
    rester vrai n'est pas le prix, c'est que l'assiette de la comparaison EST
    celle du tarif.*
    """

    @classmethod
    def setUpClass(cls):
        nu = PlanTarifaire.depuis_yaml(os.path.join(_PLANS, 'auto.yaml'))
        cls.plan = dataclasses.replace(
            nu, decoupe_validation=DecoupeValidation('positionnelle'))
        # ⚠️ 60 defauts sur 2 000 = 3 %, SOUS le seuil d'escalade de 5 % : la
        # couche qualite agit au lieu de bloquer, ce qui est le cas a tenir.
        df = T.portefeuille_auto(2000, 11).reset_index(drop=True)
        df.loc[0:14, cls.plan.exposition] = 0.0          # regle 1 : exclue
        df.loc[15:24, cls.plan.cible_frequence] = -1.0   # regle 1 : exclue
        df.loc[25:59, cls.plan.exposition] = 1.8         # regle 2 : corrigee
        cls.df_defauts = df
        cls.tarif = pipeline_complet(df, cls.plan)
        cls.propre = cls.tarif.rapport_qualite.dataframe_propre

    def test_PC16_LE_SCEAU_l_assiette_de_la_comparaison_EST_celle_du_tarif(self):
        """⚠️⚠️ MESURE DU 08/09/2026 : sur ce portefeuille, la couche qualite
        exclut des lignes et en corrige d'autres. Comparer sur le portefeuille
        d'AVANT ferait tarifer des lignes que le tarif n'a jamais vues."""
        self.assertLess(len(self.propre), len(self.df_defauts),
                        "la couche qualite n'exclut rien ici : ce controle "
                        "s'exercerait sur une assiette ou la violation ne "
                        "peut pas survenir")
        c = comparer_les_prix(self.tarif, self.df_defauts, self.plan)
        self.assertEqual(c.resultats, (),
                         "des prix ont ete calcules sur une assiette qui "
                         "n'est pas celle du tarif")
        self.assertIn('AUCUNE COMPARAISON', c.motif_absence)
        self.assertIn(str(len(self.df_defauts)), c.motif_absence)
        self.assertIn(str(len(self.propre)), c.motif_absence)
        print(f"    PC-16 SCEAU : {len(self.df_defauts)} lignes remises contre "
              f"{len(self.propre)} ajustees -> REFUS nomme")

    def test_PC17_LE_MIROIR_sur_la_BONNE_assiette_la_comparaison_a_lieu(self):
        """⚠️ Sans ce sens, un garde qui refuserait TOUT satisferait PC-16."""
        c = comparer_les_prix(self.tarif, self.propre, self.plan)
        self.assertEqual(c.motif_absence, '',
                         f"la bonne assiette est refusee : {c.motif_absence}")
        self.assertTrue(c.resultats, "aucun candidat mesure")
        print(f"    PC-17 miroir : assiette du tarif -> "
              f"{len(c.resultats)} candidat(s) mesure(s)")

    def test_PC18_une_CORRECTION_de_valeur_est_vue_a_lignes_EGALES(self):
        """⚠️⚠️ LE CAS QU'UN COMPTE DE LIGNES NE VOIT PAS. La regle 2 corrige
        une valeur et GARDE la ligne : meme longueur, meme index, exposition
        differente. Mesure : 35 expositions corrigees sur ce portefeuille."""
        faux = self.propre.copy()
        faux.iloc[0, faux.columns.get_loc(self.plan.exposition)] = 0.123456
        self.assertEqual(len(faux), len(self.propre))
        self.assertTrue(faux.index.equals(self.propre.index))
        motif = refuser_assiette_discordante(self.tarif, faux)
        self.assertTrue(motif, "une VALEUR modifiee passe le garde : il ne "
                               "compare que des lignes")
        self.assertIn(self.plan.exposition, motif)
        print("    PC-18 valeur corrigee a lignes egales : VUE et nommee")

    def test_PC19_un_tarif_SANS_rapport_qualite_est_refuse_et_c_est_DIT(self):
        """⚠️ `None` se lit « on ne sait pas sur quoi il a ete ajuste », jamais
        « il a ete ajuste sur tout »."""
        orphelin = dataclasses.replace(self.tarif, rapport_qualite=None)
        self.assertIsNone(assiette_du_tarif(orphelin))
        c = comparer_les_prix(orphelin, self.propre, self.plan)
        self.assertEqual(c.resultats, ())
        self.assertIn('rapport', c.motif_absence.lower())
        print("    PC-19 tarif sans rapport qualite : REFUS nomme")

    def test_PC20_A6_remet_l_ASSIETTE_DU_TARIF_releve_par_AST(self):
        """⚠️⚠️ LE CORRECTIF DOIT ATTEINDRE LA SURFACE. Le defaut vivait au
        SITE D'APPEL : le garde du socle ne sert a rien si A6 continue de
        remettre `result_a2['dataframe']` sans condition."""
        a6 = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
              / 'a6_comparaison' / 'agent.py').read_text(encoding='utf-8')
        arbre = ast.parse(a6)
        appels = [n for n in ast.walk(arbre)
                  if isinstance(n, ast.Call)
                  and getattr(n.func, 'id', None) == '_comparer']
        self.assertTrue(appels, "A6 n'appelle plus la comparaison")
        for appel in appels:
            source = ' '.join(ast.unparse(a) for a in appel.args)
            self.assertIn('_assiette_tarif', source,
                          "A6 remet un portefeuille sans le rapporter a "
                          "l'assiette du tarif")
        print("    PC-20 A6 remet l'assiette du tarif")

    def test_PC21_le_refus_d_assiette_ATTEINT_le_document(self):
        """⚠️ Un refus qui ne sort pas du calcul ne protege personne."""
        c = comparer_les_prix(self.tarif, self.df_defauts, self.plan)
        html = _bloc_comparaison_html(c)
        self.assertIn(TITRE_COMPARAISON, html)
        self.assertIn('AUCUNE COMPARAISON', html)
        print("    PC-21 le refus d'assiette est publie dans le document")


class TestLeBranchement(unittest.TestCase):

    def test_PC13_LES_DEUX_FORMATS_publient_la_comparaison(self):
        """⚠️⚠️ LA QUATRIEME ASYMETRIE QUE CE DEPOT A PAYEE. Releve PAR AST."""
        chemin = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
                  / 'services' / 'rapport_modeles_tarif.py')
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        html = mots = False
        for fonction in ast.walk(arbre):
            if not isinstance(fonction, ast.FunctionDef):
                continue
            noms = {getattr(n.func, 'id', None) for n in ast.walk(fonction)
                    if isinstance(n, ast.Call)}
            if fonction.name == 'export_html' and '_bloc_comparaison_html' in noms:
                html = True
            if fonction.name == 'export_word':
                src = ast.get_source_segment(
                    chemin.read_text(encoding='utf-8'), fonction) or ''
                mots = 'TITRE_COMPARAISON' in src
        self.assertTrue(html, "le HTML ne publie pas la comparaison")
        self.assertTrue(mots, "le Word ne publie pas la comparaison")
        print("    PC-13 les deux formats publient la comparaison")

    def test_PC14_A6_PRODUIT_et_transmet_la_comparaison(self):
        """⚠️⚠️ SANS CETTE LIGNE, TOUT LE RESTE EST INERTE -- la lecon du lot 2,
        ou un tuyau sans source avait laisse le temoin de gel VERT."""
        a6 = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
              / 'a6_comparaison' / 'agent.py').read_text(encoding='utf-8')
        arbre = ast.parse(a6)
        produit = any(
            isinstance(n, ast.Call)
            and getattr(n.func, 'id', None) == '_comparer'
            for n in ast.walk(arbre))
        transmet = any(
            isinstance(n, ast.Call)
            and getattr(n.func, 'id', None) == 'generer_rapport_tarification'
            and 'comparaison_prix' in {k.arg for k in n.keywords}
            for n in ast.walk(arbre))
        self.assertTrue(produit, "A6 ne produit plus la comparaison")
        self.assertTrue(transmet, "A6 ne la transmet plus au rapport")
        print("    PC-14 A6 produit ET transmet la comparaison")

    def test_PC15_le_socle_ne_remonte_PAS_vers_une_direction(self):
        """⚠️⚠️ LE SEUL IMPORT DE PRODUCTION QUI L'AVAIT FAIT a coute 4,41 s et
        quatorze modules, mesure par AST le 05/09/2026. Le socle porte le
        vocabulaire et la mesure ; l'orchestration vit dans la direction."""
        socle = (pathlib.Path(_RACINE) / 'core'
                 / 'prix_compares.py').read_text(encoding='utf-8')
        arbre = ast.parse(socle)
        remontees = [
            n.module for n in ast.walk(arbre)
            if isinstance(n, ast.ImportFrom) and n.module
            and n.module.startswith('direction_')]
        self.assertEqual(remontees, [],
                         f"le socle importe une direction : {remontees}")
        print("    PC-15 le socle n'importe aucune direction")


# ═════════════════════════════════════════════════════════════════════════════
#  AUCUNE BANDE DE NIVEAU N'EST CÂBLÉE -- arbitrage ① du 10/09/2026
# ═════════════════════════════════════════════════════════════════════════════
class TestAucuneBandeCablee(unittest.TestCase):
    """⚠️⚠️ UNE DÉCISION DE NE PAS FAIRE SE GARDE, SINON ELLE SE REPREND.

    Deux formes de bande ont été proposées et mesurées contradictoirement à
    4 tailles x 5 découpes x 6 candidats. **Les deux sont réfutées** :

      · la bande FIXE `[0,90 ; 1,10]` : le taux de refus va de 80,0 % (n=1 000)
        à 33,3 % (n=8 000) -- **46,7 points** d'amplitude par la seule taille ;
      · la bande CALCULÉE `1 ± z/√sinistres` : **26,7 points**, soit **57 %**
        du même défaut. Elle corrige la LARGEUR, pas le CENTRE.

    ⚠️⚠️ Et elle cesse d'éliminer le mauvais modèle quand le portefeuille
    grossit : `xgboost_tweedie`, mal calibré à toutes les tailles, est rejeté
    5/5 à n = 1 000 et **retenu 4/5 à n = 8 000**.

    *Ce contrôle ne teste pas un calcul : il tient une ABSENCE.* Sans lui, un
    lecteur qui trouve `bande=None` partout le prend pour un oubli et le
    << répare >>.
    """

    def test_PC22_AUCUN_des_20_plans_ne_declare_de_bande_de_niveau(self):
        """⚠️ MIROIR DE `VT10b`. Le champ peut exister ; ce qui compte est que
        personne ne le déclare, sinon ce lot changerait le comportement d'un
        plan réel sans que quiconque l'ait décidé."""
        import glob
        declarants = []
        for chemin in sorted(glob.glob(os.path.join(_RACINE, 'plans',
                                                    '*.yaml'))):
            plan = PlanTarifaire.depuis_yaml(chemin)
            for champ in ('bande_niveau', 'bande_de_niveau', 'bande'):
                if getattr(plan, champ, None):
                    declarants.append(f"{os.path.basename(chemin)}:{champ}")
        self.assertEqual(
            declarants, [],
            f"des plans declarent une bande de niveau : {declarants} -- or "
            f"les deux formes mesurees eliminent sur la TAILLE du "
            f"portefeuille avant d'eliminer sur la qualite du calage")
        print("    PC-22 aucun des 20 plans ne declare de bande de niveau")

    def test_PC23_LE_SCEAU_sans_bande_E2_n_ecarte_PERSONNE(self):
        """⚠️⚠️ LE SCEAU DE L'ARBITRAGE : AUCUNE BANDE N'EST POSEE PAR DEFAUT.
        Un plant qui poserait une bande par defaut -- un litteral, une valeur
        calculee, n'importe quoi -- doit faire rougir ceci. *E2 reste MESURE et
        PUBLIE ; il n'ELIMINE pas.*

        ⚠️⚠️ CE CONTROLE EST UN RELEVE DE SIGNATURE, PAS UN COMPORTEMENT --
        et sa version du 10/09/2026 se disait << comportemental >> alors
        qu'elle ne parcourait **AUCUNE PAIRE**. Elle appariait
        `zip(noms[len(noms) - len(n.defaults):], defauts)` avec `noms` couvrant
        posonly + args + **kwonly** mais la tranche prise sur `len(n.defaults)`
        SEUL, qui ne compte que les positionnels. Or `bande` est KEYWORD-ONLY :
        `n.defaults` est vide, la tranche vaut `[]`, le `zip` est vide, et
        `litteraux` valait `[]` QUOI QU'ON ECRIVE dans la signature.
        Mesure du 11/09/2026 : un plant `*, bande=(0.9, 1.1)` restait **VERT**,
        `*, bande_niveau=[0.85, 1.15]` restait **VERT** ; seule la forme
        POSITIONNELLE -- que le code n'emploie pas -- rougissait.
        Le COMPORTEMENT, lui, est tenu par `PC-9` (sans bande, aucun candidat
        n'est ecarte par le critere) et par `PC-10` (son miroir)."""
        source = inspect.getsource(comparer_les_prix)
        arbre = ast.parse(source)
        litteraux = []
        for n in ast.walk(arbre):
            if not isinstance(n, ast.arguments):
                continue
            # ⚠️⚠️ LES DEUX FAMILLES DE DEFAUTS S'APPARIENT SEPAREMENT.
            # `n.defaults` ne concerne QUE les positionnels ; `n.kw_defaults`
            # est aligné sur `n.kwonlyargs`, trou compris (`None` = pas de
            # défaut). Les mélanger dans un seul `zip` décale l'appariement.
            positionnels = list(n.posonlyargs) + list(n.args)
            paires = list(zip(positionnels[len(positionnels) - len(n.defaults):],
                              n.defaults))
            paires += [(a, d) for a, d in zip(n.kwonlyargs, n.kw_defaults)
                       if d is not None]
            for arg, defaut in paires:
                if 'bande' in arg.arg and not (
                        isinstance(defaut, ast.Constant)
                        and defaut.value is None):
                    litteraux.append(f"{arg.arg}={ast.unparse(defaut)}")
        self.assertEqual(
            litteraux, [],
            f"une bande est posee PAR DEFAUT : {litteraux}. Une regle qui "
            f"bloque se declare, elle ne se devine pas")
        print("    PC-23 SCEAU : aucune bande par defaut dans "
              "`comparer_les_prix`")

    def test_PC24_le_document_DIT_qu_aucune_bande_n_est_declaree(self):
        """⚠️ Un critere qui n'elimine pas et qui se TAIT se lit comme un
        critere qui a laisse tout passer. La phrase doit dire les deux : E2 est
        mesure, ET il n'ecarte personne."""
        phrase = synthese_comparaison([], bande=None)
        self.assertIn('AUCUNE BANDE', phrase.upper())
        self.assertIn('MESURE', phrase.upper())
        for mot in ('ecarte', 'declare'):
            self.assertIn(mot, phrase.lower(),
                          f"la phrase ne dit pas '{mot}' : le lecteur ne sait "
                          f"ni ce qui a ete fait, ni comment l'activer")
        # ⚠️ ET LE MIROIR : avec une bande DECLAREE, la phrase la publie -- un
        # controle qui ne verifie que l'absence laisserait la branche declaree
        # se taire.
        declaree = synthese_comparaison([], bande=(0.9, 1.1))
        self.assertNotIn('AUCUNE BANDE', declaree.upper())
        self.assertIn('0.9', declaree)
        print("    PC-24 le document dit l'absence de bande, et publie celle "
              "qui est declaree")


if __name__ == '__main__':
    unittest.main(verbosity=2)
