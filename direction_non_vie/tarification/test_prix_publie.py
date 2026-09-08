"""
==============================================================================
  LOT 2 -- LE PRIX ATTEINT ENFIN UN DOCUMENT SIGNE
==============================================================================

⚠️⚠️ CE QUE CE LOT FERME. Un objet qui sait calculer un prix existait dans le
depot et fonctionnait : `TarifNonVie`, produit par `pipeline_complet`. Il
n'avait simplement jamais ete appele en production, ni connecte a aucun
livrable signe. *Le meme motif que le mapping client et que
`cout_par_sinistre` : un mecanisme juste, jamais branche.*

  Mesure du 08/09/2026, par AST et par relevé :
    - appelants de production de `pipeline_complet` : l'app Streamlit
      (interdite, et elle alimente un ECRAN), une demo, deux constructions
      internes au module. ZERO chemin de production reel.
    - occurrences de `prime_pure`, `prime_commerciale_ht`, `prime_ttc` ou
      `chargements` dans les TROIS services de livrable : ZERO.

CE QUI EST POSE
  A6 -- qui produit deja le rapport signe -- FAIT PASSER le tarif jusqu'a
  `generer_rapport_tarification`. Il ne le fabrique pas : c'est la doctrine
  qu'il applique deja a la relecture actuarielle et au rapport qualite.

⚠️⚠️ LES DEUX NIVEAUX ENSEMBLE, ET C'EST UN ARBITRAGE DE FOND. Le DETAIL par
contrat sert a verifier que chaque cas a du sens ; le TOTAL agrege sert a
juger l'impact d'ensemble. Publier l'un sans l'autre priverait l'actuaire
signataire d'une de ses deux lectures. Et les deux se RECONCILIENT : le bloc
dit sur quelle assiette porte chacun -- sans quoi un lecteur additionnerait le
detail en croyant retrouver le total.

⚠️⚠️ RGPD, CONTRAINTE DURE. Le detail porte les FACTEURS TARIFAIRES et un rang
dans le document, JAMAIS l'identifiant du contrat. Ce rapport sort du
perimetre de traitement ; un identifiant y serait une donnee personnelle
diffusee.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
==============================================================================
"""
from __future__ import annotations

import ast
import dataclasses
import os
import pathlib
import sys
import unittest

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from core.plan_tarifaire import Chargements, PlanTarifaire
from core.validation_tarif import DecoupeValidation
from direction_non_vie.tarification import test_plan_invariants as T
from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
from direction_non_vie.tarification.services.rapport_modeles_tarif import (
    LIGNES_DETAIL_TARIF,
    TITRE_TARIF,
    _bloc_tarif_html,
    tarif_publie,
)

_PLANS = os.path.join(_RACINE, 'plans')
_CH = Chargements(frais=0.15, commission=0.10, marge=0.03,
                  declare_par='Direction Technique', declare_le='2026-09-08')


class TestLePrixEstPublie(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.plan_nu = PlanTarifaire.depuis_yaml(
            os.path.join(_PLANS, 'flotte_automobile.yaml'))
        cls.plan = dataclasses.replace(cls.plan_nu, chargements=_CH)
        # ⚠️⚠️ UN IDENTIFIANT DE CONTRAT EST INJECTE, ET C'EST INDISPENSABLE.
        # La fixture synthetique n'en portait pas : `PX-4` aurait alors
        # verifie qu'une colonne ABSENTE ne fuite pas, ce qui ne prouve rien.
        # Un vrai fichier client en porte un -- les 20 plans le declarent --,
        # donc le controle doit s'exercer dans cette situation-la.
        # ⚠️ Valeurs SYNTHETIQUES : aucune donnee reelle n'entre dans un test.
        cls.df = T.portefeuille_flotte(n=800)
        cls.df = cls.df.assign(
            id_contrat=[f'POL-SYNTH-{i:05d}' for i in range(len(cls.df))])
        cls.publie = tarif_publie(pipeline_complet(cls.df, cls.plan), cls.df)
        cls.publie_nu = tarif_publie(
            pipeline_complet(cls.df, cls.plan_nu), cls.df)
        cls.html = _bloc_tarif_html(cls.publie)

    # ── les deux niveaux ─────────────────────────────────────────────────
    def test_PX1_LE_SCEAU_les_DEUX_niveaux_coexistent(self):
        """⚠️⚠️ LE CONTROLE CENTRAL DE CE LOT. Un plant qui ferait disparaitre
        le detail au profit du seul total -- ou l'inverse -- doit faire rougir
        ceci. *Un actuaire a besoin des deux : le detail pour verifier que
        chaque cas a du sens, le total pour juger l'impact d'ensemble.*"""
        self.assertTrue(self.publie['detail'], "le DETAIL a disparu")
        self.assertTrue(self.publie['total'], "le TOTAL a disparu")
        self.assertIn('Total du portefeuille', self.html)
        self.assertIn('Detail des', self.html)
        self.assertEqual(len(self.publie['detail']), LIGNES_DETAIL_TARIF)
        print(f"    PX-1 SCEAU : total ({self.publie['total']['n_contrats']} "
              f"contrats) ET detail ({len(self.publie['detail'])} lignes)")

    def test_PX2_les_deux_niveaux_se_RECONCILIENT(self):
        """⚠️⚠️ SANS RECONCILIATION, DEUX CHIFFRES SOUS LE MEME TITRE SONT DEUX
        VERITES POSSIBLES. Le detail montre les premiers contrats, le total
        porte sur TOUS : le document doit le dire, et la formule doit tenir
        ligne a ligne."""
        t = self.publie['total']
        self.assertGreater(t['n_contrats'], t['n_lignes_detail'],
                           "le controle ne prouve rien si les deux assiettes "
                           "coincident")
        # la phrase qui dit les deux assiettes
        self.assertIn(str(t['n_lignes_detail']), self.html)
        self.assertIn(str(t['n_contrats']), self.html)
        self.assertIn('porte sur TOUS les', self.html)
        # et la formule, ligne a ligne
        for ligne in self.publie['detail']:
            attendu = (ligne['prime_pure'] * 1.15 * 1.03) / 0.90
            self.assertAlmostEqual(ligne['prime_commerciale_ht'], attendu,
                                   places=1, msg=f"rang {ligne['rang']}")
        print("    PX-2 assiettes dites, et la formule tient ligne a ligne")

    def test_PX2b_LE_DETAIL_ET_LE_TOTAL_TARIFENT_LE_MEME_CONTRAT(self):
        """⚠️⚠️ CE CONTROLE MANQUAIT, ET C'EST UN GARDE-FOU EXISTANT QUI L'A
        REVELE. `PX-2` verifiait le rapport HT / pure DANS une ligne -- une
        coherence interne, qui reste vraie meme si la ligne entiere est
        fausse. Le total, lui, passe par `predire_portefeuille`.

        Mesure : le detail construisait le contrat a partir des seuls
        FACTEURS, donc `tarifer()` retombait sur une exposition d'un an --
        et sur-tarifait tout contrat plus court, pendant que le total lisait
        la colonne. *Deux niveaux qui ne tarifent pas le meme contrat ne se
        reconcilient pas, quoi qu'en dise la phrase qui les accompagne.*

        C'est `DC-7` qui l'a trouve, pas ce fichier : il exige que TOUT
        appelant de `tarifer()` fournisse la duree ou publie l'hypothese.
        Le controle qui manquait est donc celui-ci -- la reconciliation
        entre les deux CHEMINS, pas seulement au sein d'une ligne.
        """
        pred = self.publie_nu and pipeline_complet(
            self.df, self.plan).predire_portefeuille(self.df)
        for ligne in self.publie['detail']:
            rang = ligne['rang'] - 1
            attendu = float(pred['prime_pure'].iloc[rang])
            self.assertAlmostEqual(
                ligne['prime_pure'], attendu, places=2,
                msg=f"rang {ligne['rang']} : le detail rend "
                    f"{ligne['prime_pure']} la ou le chemin portefeuille rend "
                    f"{attendu:.2f}. Les deux niveaux ne tarifent pas le meme "
                    f"contrat.")
            self.assertAlmostEqual(
                ligne['exposition'],
                float(self.df[self.plan.exposition].iloc[rang]), places=6,
                msg="la duree du contrat n'a pas voyage jusqu'au detail")
        print(f"    PX-2b les {len(self.publie['detail'])} lignes du detail "
              f"tarifent EXACTEMENT ce que le chemin portefeuille tarife")

    def test_PX3_le_total_porte_sur_TOUT_le_portefeuille(self):
        """⚠️ Un total calcule sur les seules lignes montrees serait faux d'un
        facteur 80 sur ce jeu -- et personne ne le verrait."""
        t = self.publie['total']
        self.assertEqual(t['n_contrats'], len(self.df))
        moyenne = t['somme_prime_pure'] / t['n_contrats']
        self.assertAlmostEqual(moyenne, t['prime_pure_moyenne'], places=1)
        somme_detail = sum(l['prime_pure'] for l in self.publie['detail'])
        self.assertGreater(t['somme_prime_pure'], somme_detail * 5,
                           "le total semble calcule sur le seul detail")
        print(f"    PX-3 total sur {t['n_contrats']} contrats, detail sur "
              f"{t['n_lignes_detail']} -- assiettes distinctes")

    # ── RGPD ─────────────────────────────────────────────────────────────
    def test_PX4_RGPD_aucun_identifiant_de_contrat_ne_fuite(self):
        """⚠️⚠️ CONTRAINTE DURE, ET VERIFIEE SUR LE RENDU, PAS SUR L'INTENTION.
        Le plan DECLARE `identifiant_contrat` (20/20 le font) et la colonne
        existe dans le portefeuille : rien n'empeche techniquement qu'elle
        entre dans la table. Ce qui l'empeche, c'est que le detail ne montre
        que les FACTEURS -- et ce controle le mesure sur le HTML rendu."""
        idc = self.plan.identifiant_contrat
        self.assertTrue(idc, "le plan ne declare pas d'identifiant : ce "
                             "controle ne prouve plus rien")
        self.assertIn(idc, self.df.columns)
        self.assertNotIn(idc, self.html,
                         "le nom de la colonne identifiante est dans le "
                         "document")
        for valeur in self.df[idc].astype(str).head(50):
            self.assertNotIn(valeur, self.html,
                             f"l'identifiant {valeur!r} a fuite dans le "
                             f"document signe")
        for ligne in self.publie['detail']:
            self.assertNotIn(idc, ligne['facteurs'])
        print(f"    PX-4 RGPD : ni la colonne '{idc}' ni aucune de ses "
              f"valeurs dans le rendu")

    def test_PX4b_le_detail_ne_montre_QUE_des_facteurs_declares(self):
        """⚠️ Le second sens : il ne suffit pas d'exclure l'identifiant, il
        faut que ce qui reste soit exactement ce que le plan declare comme
        facteur -- `echeance` et les cibles n'ont rien a faire la non plus."""
        declares = {f.nom for f in self.plan.facteurs}
        for ligne in self.publie['detail']:
            self.assertTrue(set(ligne['facteurs']) <= declares,
                            f"colonnes hors plan : "
                            f"{set(ligne['facteurs']) - declares}")
        self.assertTrue(self.publie['detail'][0]['facteurs'],
                        "le detail ne montre AUCUN facteur : il ne permet "
                        "plus de verifier qu'un cas a du sens")
        print("    PX-4b le detail ne porte que des facteurs declares")

    # ── ce qui accompagne le prix ────────────────────────────────────────
    def test_PX5_les_HYPOTHESES_voyagent_avec_le_prix(self):
        """⚠️⚠️ UN PRIX SANS SES HYPOTHESES N'EST PAS CONTESTABLE. Qui a
        declare les chargements et quand, de quel regime fiscal vient la taxe,
        et si la validation a pu etre mesuree."""
        self.assertIn('Direction Technique', self.html)
        self.assertIn('2026-09-08', self.html)
        self.assertIn('NON DECLAREE', self.html,
                      "la decoupe de validation n'est pas declaree sur ce "
                      "plan : le document doit le dire")
        self.assertIn(self.publie['plan_empreinte'], self.html)
        self.assertTrue(self.publie['plan_empreinte'].startswith('s'))
        print(f"    PX-5 auteur, date, empreinte "
              f"{self.publie['plan_empreinte']} publies")

    def test_PX5b_la_decoupe_DECLAREE_fait_taire_la_phrase(self):
        """⚠️ Les deux sens : un avertissement permanent cesse d'etre lu."""
        plan = dataclasses.replace(
            self.plan, decoupe_validation=DecoupeValidation('positionnelle'))
        pub = tarif_publie(pipeline_complet(self.df, plan), self.df)
        self.assertIsNone(pub['validation_hypothese'])
        self.assertNotIn('NON DECLAREE', _bloc_tarif_html(pub))
        print("    PX-5b decoupe declaree -> la phrase se tait")

    def test_PX6_un_plan_SANS_chargements_publie_la_prime_PURE(self):
        """⚠️⚠️ LA MOITIE POSITIVE DE L'ARBITRAGE DU LOT 1, VUE DEPUIS LE
        DOCUMENT. Le prix vendable manque, et le document le DIT -- mais la
        prime pure, elle, y figure. *Un document muet se lirait comme une
        panne.*"""
        t = self.publie_nu['total']
        self.assertGreater(t['somme_prime_pure'], 0)
        self.assertIsNone(t['somme_prime_commerciale_ht'])
        self.assertEqual(t['n_sans_prime_commerciale'], len(self.df))
        html = _bloc_tarif_html(self.publie_nu)
        self.assertIn('sans prime', html)
        self.assertIn('CHARGEMENTS NON DECLARES', html)
        for ligne in self.publie_nu['detail']:
            self.assertGreater(ligne['prime_pure'], 0)
            self.assertIsNone(ligne['prime_commerciale_ht'])
        print(f"    PX-6 sans chargements : pure "
              f"{t['somme_prime_pure']} EUR publiee, commerciale dite absente")

    def test_PX7_SANS_TARIF_le_rapport_est_celui_d_hier(self):
        """⚠️ Un bloc vide dirait qu'il n'y a pas de prix la ou il n'y a pas eu
        de calcul. Ce n'est pas la meme chose, et le rapport ne doit RIEN
        gagner quand aucun tarif ne lui est fourni."""
        self.assertEqual(tarif_publie(None, self.df), {})
        self.assertEqual(tarif_publie(None, None), {})
        self.assertEqual(_bloc_tarif_html({}), '')
        print("    PX-7 aucun tarif -> aucun bloc, pas meme vide")

    # ── les deux formats ─────────────────────────────────────────────────
    def test_PX8_LES_DEUX_FORMATS_publient_le_prix(self):
        """⚠️⚠️ LA QUATRIEME FOIS QUE CE DEPOT PAIE CETTE ASYMETRIE. Le
        mapping client, l'elasticite, la qualite des donnees et les reserves
        d'A6 ont chacun atteint UN format et pas l'autre. *Corriger un seul
        format laisse la moitie du livrable signe sans le fait.*

        Releve PAR AST : les deux exportateurs appellent `tarif_publie`."""
        chemin = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
                  / 'services' / 'rapport_modeles_tarif.py')
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        appelants = set()
        for fonction in ast.walk(arbre):
            if not isinstance(fonction, ast.FunctionDef):
                continue
            for n in ast.walk(fonction):
                if (isinstance(n, ast.Call)
                        and getattr(n.func, 'id', None) == 'tarif_publie'):
                    appelants.add(fonction.name)
        self.assertIn('export_html', appelants)
        self.assertIn('export_word', appelants)
        print(f"    PX-8 les deux exportateurs publient le prix : "
              f"{sorted(appelants)}")

    def test_PX9_A6_FAIT_PASSER_le_tarif_jusqu_au_rapport(self):
        """⚠️⚠️ LE BRANCHEMENT LUI-MEME, RELEVE PAR AST. Sans cette ligne, tout
        le reste est inerte : le service saurait publier un prix qu'aucun
        chemin ne lui donnerait -- exactement l'etat d'avant ce lot."""
        chemin = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
                  / 'a6_comparaison' / 'agent.py')
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        passe = False
        for n in ast.walk(arbre):
            if (isinstance(n, ast.Call)
                    and getattr(n.func, 'id', None)
                    == 'generer_rapport_tarification'):
                mots = {k.arg for k in n.keywords}
                if {'tarif', 'portefeuille'} <= mots:
                    passe = True
        self.assertTrue(
            passe,
            "A6 n'appelle plus `generer_rapport_tarification` avec `tarif` et "
            "`portefeuille` : le prix ne peut plus atteindre le document.")
        print("    PX-9 A6 fait passer le tarif ET son portefeuille")

    def test_PX10_le_TITRE_est_publie_et_nomme_les_deux_niveaux(self):
        """⚠️ Un bloc sans titre se lit comme la suite du precedent."""
        self.assertIn(TITRE_TARIF, self.html)
        self.assertIn('pure', TITRE_TARIF.lower())
        self.assertIn('commerciale', TITRE_TARIF.lower())
        print(f"    PX-10 titre publie : {TITRE_TARIF!r}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
