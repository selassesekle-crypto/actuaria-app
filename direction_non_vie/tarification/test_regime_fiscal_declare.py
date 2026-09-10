"""
==============================================================================
  LOT 2 -- LE TAUX QUI TRANSFORME LA PRIME HT EN PRIME PAYEE PORTE SA SOURCE
==============================================================================

⚠️⚠️ CE QUE CE LOT FERME. `CHARGEMENTS_DEFAUT['taxes'] = 0.33` s'appliquait
aux **vingt LoB**, sans source. L'enquete du 08/09/2026 a retrouve l'origine
du chiffre -- commit `a17f058`, 14/07/2026 -- et elle est nue : trois nombres
dans un plan d'execution, aucun article de loi, aucune decomposition. Le
depot le declarait lui-meme non source, a six endroits.

  Mesure : sur une branche au taux residuel de 9 %, le repli sur-taxe la
  prime TTC de **+22,02 %** ; sur la protection juridique, de **+17,28 %**.
  Le defaut est LATENT -- `prime_ttc` n'atteint aucun livrable signe -- et
  **arme** : il devient reel le jour ou ce prix est publie.

CE QUI EST POSE
  · `core/taxes_assurance.py` : un registre a vocabulaire controle. Chaque
    regime porte son taux, son article, sa date d'entree en vigueur ET sa
    date de RELECTURE. La porte `_taux()` REFUSE une source hors vocabulaire
    et une approximation sans methode.
  · `PlanTarifaire.regime_fiscal` : le plan declare la QUALIFICATION, jamais
    le nombre. Un seul endroit a corriger a la prochaine loi de finances.
  · Le routage PAR CONTRAT : sur `flotte_automobile`, la qualification suit
    `type_flotte`. VL et VUL relevent de la RC a 33 %, PL de la RC a 15 %,
    et **`Mixte` ne recoit AUCUNE prime TTC**.

⚠️⚠️ LE POINT DUR, ET C'EST UN ARBITRAGE DE FOND. La modalite `Mixte` RESTE
dans le plan : une police qui mele vehicules legers et poids lourds est un
vrai objet, et le facteur qui la distingue est juste. Mais elle ne recoit
jamais de prix TTC calcule. *Un taux moyen ponderee supposerait une part de
prime que personne n'a mesuree -- et publierait, sous forme de nombre, une
decision que personne n'a prise.*

⚠️ CE QUI N'EST PAS FAIT, ET POURQUOI. Huit plans sur vingt ne sont PAS
etiquetes. Six sont des branches MIXTES dont le document de reference dit
explicitement qu'elles exigent un arbitrage sur la methode de repartition ;
deux ne sont couvertes par aucune source (voir `TX-15`). Ils gardent le
comportement d'aujourd'hui -- **aucun euro ne bouge** -- et le repli est DIT.
==============================================================================
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import os
import sys
import unittest
from datetime import date
from typing import ClassVar

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from core.plan_tarifaire import (
    EMPREINTE_SCHEMA,
    Chargements,
    PlanTarifaire,
)
from core.taxes_assurance import (
    MIXTE_NON_TRANCHE,
    REGIMES,
    REGIMES_ADMIS,
    SOURCE_APPROXIMATION,
    SOURCE_CGI,
    RegimeFiscalRoute,
    RegimeMixte,
    TauxTaxe,
    _taux,
    diagnostic_peremption,
    regime_du_plan,
    route_depuis_dict,
    synthese_regime_fiscal,
    taux_applicable,
)
from direction_non_vie.tarification import test_plan_invariants as T
from direction_non_vie.tarification.pipeline_tarifaire import (
    TarifNonVie,
    phrase_chargements_non_declares,
    pipeline_complet,
)

_PLANS = os.path.join(_RACINE, 'plans')

def _plan(nom: str) -> PlanTarifaire:
    return PlanTarifaire.depuis_yaml(os.path.join(_PLANS, f'{nom}.yaml'))


#: ⚠️⚠️ LE CAS NORMAL DEPUIS L'ARBITRAGE DU 08/09/2026 : un client declare SES
#: trois chargements commerciaux, et la taxe vient du registre via
#: `regime_fiscal`. `taxes` est ABSENT -- son absence dit precisement << le taux
#: vient du regime >>. Ces controles observent un TAUX DE TAXE sur un prix : il
#: leur faut donc une prime commerciale, donc des chargements declares.
_CHARGEMENTS = Chargements(frais=0.15, commission=0.10, marge=0.03,
                           declare_par='Controle du lot', declare_le='2026-09-08')

#: ⚠️ LES TROIS CHARGEMENTS COMMERCIAUX SEULS, SANS `taxes` -- la forme que
#: `pipeline_complet` attend a l'appel. Son absence de `taxes` dit precisement
#: << le taux ne vient PAS de l'appel >>, et laisse parler les deux autres
#: sources. Un dict a part, parce que quatre controles le passent a l'identique
#: et qu'un chiffre recopie quatre fois finit par diverger en un endroit.
_COMMERCIAUX = {'frais': 0.15, 'commission': 0.10, 'marge': 0.03}


def _plan_tarifable(nom: str) -> PlanTarifaire:
    """Le plan du depot, plus des chargements declares -- rien d autre."""
    return dataclasses.replace(_plan(nom), chargements=_CHARGEMENTS)


# ═════════════════════════════════════════════════════════════════════════════
#  LE REGISTRE REFUSE
# ═════════════════════════════════════════════════════════════════════════════
class TestLeRegistreRefuse(unittest.TestCase):
    """⚠️⚠️ LA LECON DE `parametres_fs.py`, APPLIQUEE AVANT DE LA PAYER.

    Ce module raconte que TOUTES ses valeurs fausses etaient commentees
    << Annexe II >> : la contrainte etait ecrite en commentaire, donc elle ne
    contraignait rien. Ici la porte LEVE.
    """

    def test_TX1_une_source_hors_vocabulaire_est_REFUSEE(self):
        with self.assertRaises(ValueError) as ctx:
            _taux(0.09, 'BOFIP', 'BOI-TCAS-ASSUR-30-10-10',
                  '2026-07-01', '2026-09-08', "un taux invente")
        msg = str(ctx.exception)
        self.assertIn('BOFIP', msg)
        self.assertIn('CGI_ART_1001', msg,
                      "le motif doit NOMMER le vocabulaire admis : une erreur "
                      "se corrige si on voit le bon mot")
        print("    TX-1 source hors vocabulaire REFUSEE, motif nommant "
              "le vocabulaire")

    def test_TX2_une_approximation_SANS_methode_est_REFUSEE(self):
        """⚠️ Sans sa methode, une approximation a l'air d'une lecture."""
        with self.assertRaises(ValueError) as ctx:
            _taux(0.33, SOURCE_APPROXIMATION, 'CGI art. 1001-5 quater',
                  '2026-07-01', '2026-09-08', "auto sans methode")
        self.assertIn('methode', str(ctx.exception).lower())
        # ⚠️ ET LE MIROIR : avec sa methode, elle passe. Un controle qui ne
        # verifie que le refus laisserait passer une porte qui refuse TOUT.
        ok = _taux(0.33, SOURCE_APPROXIMATION, 'CGI art. 1001-5 quater',
                   '2026-07-01', '2026-09-08', "auto",
                   methode="le taux RC applique au contrat entier ; majore")
        self.assertEqual(ok.taux, 0.33)
        print("    TX-2 approximation sans methode REFUSEE ; avec methode, "
              "admise")

    def test_TX2b_un_taux_en_POURCENTAGE_est_refuse(self):
        """⚠️ `18` au lieu de `0.18` multiplierait la prime par dix-neuf."""
        with self.assertRaises(ValueError) as ctx:
            _taux(18, SOURCE_CGI, 'CGI art. 1001-5 bis',
                  '2026-07-01', '2026-09-08', "auto autres garanties")
        # ⚠️ L'assertion cherche << POURCENTAGE >>, pas << DECIMAL >> : le motif
        # ecrit << DÉCIMAL >> avec son accent, et une comparaison sur la forme
        # non accentuee echouait. *Le piege des regex qui cherchent une graphie
        # que le code n'emploie pas -- deja paye six fois dans ce chantier.*
        self.assertIn('POURCENTAGE', str(ctx.exception).upper())
        print("    TX-2b taux en pourcentage REFUSE")

    def test_TX2c_toutes_les_APPROXIMATIONS_du_registre_disent_leur_SENS(self):
        """⚠️⚠️ UNE APPROXIMATION QUI NE DIT PAS SI ELLE MAJORE OU MINORE EST
        INUTILISABLE. `auto_vehicule_leger` majore (les autres garanties sont
        a 18 %, sous 33 %) ; `auto_poids_lourd` MINORE (elles sont au-dessus
        de 15 %). *Le sens s'inverse avec le taux : le lire dans le registre
        est la seule facon de ne pas le supposer.*
        """
        approx = {n: r for n, r in REGIMES.items()
                  if isinstance(r, TauxTaxe) and r.source == SOURCE_APPROXIMATION}
        self.assertGreaterEqual(len(approx), 2)
        for nom, r in approx.items():
            with self.subTest(regime=nom):
                bas = r.methode.lower()
                self.assertTrue('majore' in bas or 'minore' in bas,
                                f"l'approximation '{nom}' ne dit pas dans quel "
                                f"SENS elle se trompe")
        print(f"    TX-2c les {len(approx)} approximations disent leur sens "
              f"(majore / minore)")


# ═════════════════════════════════════════════════════════════════════════════
#  LE PLAN REFUSE
# ═════════════════════════════════════════════════════════════════════════════
class TestLePlanRefuse(unittest.TestCase):

    def test_TX3_un_regime_INCONNU_est_refuse_au_plan(self):
        with self.assertRaises(ValueError) as ctx:
            dataclasses.replace(T.AUTO, regime_fiscal='taux_maison')
        msg = str(ctx.exception)
        self.assertIn('taux_maison', msg)
        self.assertIn('residuel_par_elimination', msg,
                      "le motif doit lister les regimes admis")
        print("    TX-3 regime inconnu REFUSE au plan")

    def test_TX4_le_routage_est_verifie_DANS_LES_DEUX_SENS(self):
        """⚠️⚠️ LA LECON DU VERROU A SENS UNIQUE, FERMEE LE MEME JOUR.

        La frontiere LLM demandait << chaque site DECLARE existe-t-il ? >>
        sans jamais demander << chaque site REEL est-il DECLARE ? >>. Les deux
        moities d'une meme question : ici, une modalite du facteur SANS regime
        laisse un contrat sans qualification, et un regime pour une modalite
        INEXISTANTE est une regle qui ne se declenchera jamais.
        """
        base = _plan('flotte_automobile')

        # SENS 1 -- une modalite reelle n'est pas qualifiee
        partielle = RegimeFiscalRoute(
            selon='type_flotte',
            regimes=(('VL', 'auto_vehicule_leger'),
                     ('VUL', 'auto_vehicule_leger'),
                     ('PL', 'auto_poids_lourd')))     # `Mixte` manque
        with self.assertRaises(ValueError) as ctx:
            dataclasses.replace(base, regime_fiscal=partielle)
        self.assertIn('Mixte', str(ctx.exception))

        # SENS 2 -- une modalite qualifiee n'existe pas
        fantome = RegimeFiscalRoute(
            selon='type_flotte',
            regimes=(('Mixte', MIXTE_NON_TRANCHE),
                     ('PL', 'auto_poids_lourd'),
                     ('Remorque', 'residuel_par_elimination'),
                     ('VL', 'auto_vehicule_leger'),
                     ('VUL', 'auto_vehicule_leger')))
        with self.assertRaises(ValueError) as ctx2:
            dataclasses.replace(base, regime_fiscal=fantome)
        self.assertIn('Remorque', str(ctx2.exception))
        print("    TX-4 routage : modalite NON qualifiee ET modalite FANTOME, "
              "les deux refusees")

    def test_TX4b_une_route_sur_un_facteur_INEXISTANT_est_refusee(self):
        """⚠️ Une route qui ne se declencherait jamais a l'apparence d'un
        garde-fou sans en etre un."""
        with self.assertRaises(ValueError) as ctx:
            dataclasses.replace(
                _plan('flotte_automobile'),
                regime_fiscal=RegimeFiscalRoute(
                    selon='type_de_flotte',            # faute de frappe
                    regimes=(('VL', 'auto_vehicule_leger'),)))
        self.assertIn('type_de_flotte', str(ctx.exception))
        print("    TX-4b route sur un facteur inexistant REFUSEE")

    def test_TX9_UN_TAUX_de_taxe_ET_un_regime_sont_REFUSES_ENSEMBLE(self):
        """⚠️⚠️ LE CONFLIT REEL, ET IL EST PLUS ETROIT QU'IL N'Y PARAISSAIT.

        Ce controle a d'abord refuse TOUTE cohabitation de `chargements` et
        `regime_fiscal`. C'etait trop large, et cela interdisait le cas
        NORMAL : un client qui declare SA commission et dont la taxe vient du
        registre. Le defaut venait de ce que `taxes` avait alors un defaut
        implicite (0,33) -- le bloc portait toujours un taux, meme muet.

        `taxes` est desormais optionnel, et son absence dit << le taux vient du
        regime >>. Le conflit se resserre donc sur ce qu'il est vraiment : un
        NOMBRE dans `taxes` ET un `regime_fiscal`. *Quand deux declarations se
        contredisent, on refuse, on ne choisit pas -- mais encore faut-il
        qu'elles se contredisent.*
        """
        with self.assertRaises(ValueError) as ctx:
            dataclasses.replace(
                T.AUTO, regime_fiscal='residuel_par_elimination',
                chargements=dataclasses.replace(_CHARGEMENTS, taxes=0.20))
        msg = str(ctx.exception)
        self.assertIn('regime_fiscal', msg)
        self.assertIn('0.2', msg,
                      "le motif doit MONTRER le taux qui entre en conflit")
        print("    TX-9 un TAUX de taxe + un regime : REFUSES ensemble")

    def test_TX9b_LE_MIROIR_commission_propre_ET_taxe_du_registre_ADMIS(self):
        """⚠️⚠️ SANS CE SENS, TX-9 SERAIT SATISFAIT PAR UN GARDE QUI REFUSE TOUT.

        C'est exactement ce qui s'etait produit : la premiere version refusait
        toute cohabitation, et aucun controle ne mesurait qu'elle interdisait
        au passage le cas le plus courant. *Un garde-fou ne se verifie que dans
        ses DEUX sens.*
        """
        plan = dataclasses.replace(
            T.AUTO, regime_fiscal='residuel_par_elimination',
            chargements=_CHARGEMENTS)          # `taxes` ABSENT
        self.assertIsNone(plan.chargements.taxes)
        self.assertEqual(plan.regime_fiscal, 'residuel_par_elimination')
        self.assertEqual(plan.chargements.commission, 0.10)
        print("    TX-9b commission propre + taxe du registre : ADMIS")

    def test_TX9c_une_declaration_A_MOITIE_est_REFUSEE(self):
        """⚠️ Le niveau general est la RACINE dont les exceptions heritent : il
        n'a lui-meme rien a heriter. Declarer `frais` seul serait une
        declaration a moitie faite -- le depot a deja arbitre ce cas pour
        `Comportement`."""
        with self.assertRaises(ValueError) as ctx:
            dataclasses.replace(
                T.AUTO, chargements=Chargements(
                    frais=0.20, declare_par='X', declare_le='2026-09-08'))
        msg = str(ctx.exception)
        self.assertIn('INCOMPL', msg.upper())
        self.assertIn('commission', msg)
        self.assertIn('marge', msg)
        print("    TX-9c declaration incomplete REFUSEE, et elle NOMME "
              "ce qui manque")

    def test_TX9d_declare_par_et_declare_le_sont_OBLIGATOIRES(self):
        """⚠️⚠️ UN CHARGEMENT DECIDE DU PRIX PAYE : un regulateur demande QUI
        l'a fixe. Et c'est un ROLE, jamais un nom -- ce fichier est versionne
        dans un depot public."""
        for manquant in ('declare_par', 'declare_le'):
            with self.subTest(champ=manquant):
                champs = {'frais': 0.15, 'commission': 0.10, 'marge': 0.03,
                          'declare_par': 'Direction Technique',
                          'declare_le': '2026-09-08'}
                champs[manquant] = ''
                with self.assertRaises(ValueError) as ctx:
                    dataclasses.replace(T.AUTO,
                                        chargements=Chargements(**champs))
                self.assertIn(manquant, str(ctx.exception))
        print("    TX-9d `declare_par` et `declare_le` obligatoires")


# ═════════════════════════════════════════════════════════════════════════════
#  L'EMPREINTE
# ═════════════════════════════════════════════════════════════════════════════
class TestLEmpreinte(unittest.TestCase):

    def test_TX7_le_regime_fiscal_est_DANS_l_empreinte(self):
        """⚠️ Il decide du montant facture a l'assure : plus opposable qu'un
        chargement, qui y est depuis `s3`."""
        nu = T.AUTO.empreinte()
        etiquete = dataclasses.replace(
            T.AUTO, regime_fiscal='residuel_par_elimination').empreinte()
        autre = dataclasses.replace(
            T.AUTO, regime_fiscal='auto_vehicule_leger').empreinte()
        self.assertNotEqual(nu, etiquete,
                            "deux plans qui ne different que par leur regime "
                            "fiscal signent pareil : l'audit trail les declare "
                            "identiques alors qu'ils ne facturent pas pareil")
        self.assertNotEqual(etiquete, autre)
        # ⚠️ Le prefixe est DERIVE, jamais un litteral : c'est ce qui fait que
        # le prochain bump ne laisse pas ce controle vert par inadvertance.
        for emp in (nu, etiquete, autre):
            self.assertTrue(emp.startswith(f's{EMPREINTE_SCHEMA}:'), emp)
        print(f"    TX-7 regime fiscal dans l'empreinte : {nu} vs {etiquete} "
              f"vs {autre}")

    def test_TX7b_une_route_signe_de_maniere_REPRODUCTIBLE(self):
        """⚠️ Un dictionnaire n'a pas d'ordre garanti d'une lecture a l'autre.
        `route_depuis_dict` TRIE, et c'est la seule raison pour laquelle deux
        chargements du meme YAML signent pareil."""
        a = route_depuis_dict({'selon': 'type_flotte', 'regimes': {
            'Mixte': MIXTE_NON_TRANCHE, 'VL': 'auto_vehicule_leger',
            'PL': 'auto_poids_lourd', 'VUL': 'auto_vehicule_leger'}})
        b = route_depuis_dict({'selon': 'type_flotte', 'regimes': {
            'VL': 'auto_vehicule_leger', 'VUL': 'auto_vehicule_leger',
            'PL': 'auto_poids_lourd', 'Mixte': MIXTE_NON_TRANCHE}})
        self.assertEqual(a.regimes, b.regimes)
        base = _plan('flotte_automobile')
        self.assertEqual(dataclasses.replace(base, regime_fiscal=a).empreinte(),
                         dataclasses.replace(base, regime_fiscal=b).empreinte())
        print("    TX-7b deux ordres d'ecriture du meme routage signent "
              "IDENTIQUE")


# ═════════════════════════════════════════════════════════════════════════════
#  LE TAUX EST REELLEMENT APPLIQUE -- ET LE MIXTE EST REELLEMENT REFUSE
# ═════════════════════════════════════════════════════════════════════════════
class TestLeTauxApplique(unittest.TestCase):
    """⚠️ Un champ declare que le calcul n'utiliserait pas serait un champ qui
    PROMET -- le defaut que ce chantier poursuit depuis le debut."""

    @classmethod
    def setUpClass(cls):
        cls.flotte = pipeline_complet(
            T.portefeuille_flotte(n=1500),
            _plan_tarifable('flotte_automobile'))
        cls.contrat = {'taille_flotte': 20, 'valeur_moyenne_vehicule': 18000,
                       'age_moyen_flotte': 6, 'puissance_moyenne': 120,
                       'secteur_activite': 'Transport',
                       'zone_circulation': 'Periurbaine', 'telematique': 1,
                       'sinistres_2ans_anterieurs': 0}

    def _tarifer(self, modalite):
        return self.flotte.tarifer({**self.contrat, 'type_flotte': modalite})

    def test_TX5_LE_SCEAU_un_contrat_Mixte_ne_recoit_AUCUNE_prime_TTC(self):
        """⚠️⚠️ LE CONTROLE CENTRAL DE CE LOT, ET IL EXIGE LES TROIS MOITIES.

        Un plant qui ferait router `Mixte` vers un taux CALCULE -- une moyenne
        ponderee des 33 % et des 15 %, par exemple -- doit faire rougir ceci.
        Verifier seulement << TTC est None >> ne suffirait pas : il faut aussi
        que le REFUS SOIT DIT, et que la prime HT reste publiee. *Un refus muet
        se lit comme une panne ; un refus qui emporte le prix HT punirait
        l'assure au lieu de l'informer.*
        """
        r = self._tarifer('Mixte')
        self.assertEqual(r['success'], True,
                         "le contrat reste TARIFABLE : c'est sa QUALIFICATION "
                         "FISCALE qui n'est pas tranchee, pas son risque")
        self.assertIsNone(r['prime_ttc'],
                          "un contrat Mixte a recu une prime TTC : un taux a "
                          "ete CALCULE la ou une decision devait etre prise")
        self.assertGreater(r['prime_commerciale_ht'], 0,
                           "la prime HT doit rester publiee : le refus porte "
                           "sur la TAXE, pas sur le tarif")
        phrase = r['regime_fiscal']
        self.assertIsNotNone(phrase, "le refus est MUET")
        self.assertIn('NON TRANCHE', phrase.upper())
        print(f"    TX-5 SCEAU : Mixte -> HT={r['prime_commerciale_ht']} EUR, "
              f"TTC=None, refus DIT")

    def test_TX6_les_trois_regimes_de_la_route_sont_REELLEMENT_appliques(self):
        """⚠️ VL et VUL a 33 %, PL a 15 % -- lus sur le PRIX, pas sur le plan."""
        attendus = {'VL': 0.33, 'VUL': 0.33, 'PL': 0.15}
        for modalite, taux in attendus.items():
            with self.subTest(type_flotte=modalite):
                r = self._tarifer(modalite)
                rapport = r['prime_ttc'] / r['prime_commerciale_ht']
                self.assertAlmostEqual(rapport, 1 + taux, places=3,
                    msg=f"{modalite} : rapport TTC/HT = {rapport:.4f}, "
                        f"attendu {1 + taux:.2f}")
        print("    TX-6 VL et VUL taxes a 33 %, PL a 15 % -- mesure sur le prix")

    def test_TX6b_la_phrase_publiee_porte_l_article_de_loi(self):
        """⚠️ Un taux publie sans son article ne se conteste pas devant un
        controleur : c'est la meme exigence que le seuil declare, qui doit
        nommer sa source."""
        r = self._tarifer('PL')
        phrase = r['regime_fiscal']
        self.assertIn('1001', phrase)
        self.assertIn('15 %', phrase)
        self.assertIn('2026-09-08', phrase,
                      "la date de RELECTURE doit voyager avec le taux")
        self.assertIn('MINORE', phrase.upper(),
                      "le sens de l'approximation doit etre publie : sur un "
                      "parc poids lourd, elle SOUS-taxe")
        print("    TX-6b phrase publiee : article, taux, date, sens de "
              "l'approximation")

    def test_TX14_une_modalite_INCONNUE_refuse_au_lieu_de_se_replier(self):
        """⚠️⚠️ LA DIRECTION SURE. `anomalies_du_contrat` refuse deja une
        modalite hors enumeration ; si elle arrivait malgre tout -- contrat sans
        la colonne, appel direct -- le registre ne doit pas retomber sur un taux
        quelconque. *Ne pas savoir sous quelle qualification on taxe n'autorise
        pas a taxer quand meme.*
        """
        plan = _plan('flotte_automobile')
        regime = regime_du_plan(plan, {'taille_flotte': 20})   # pas de type_flotte
        self.assertIsInstance(regime, RegimeMixte)
        self.assertIn('None', regime.motif)
        print("    TX-14 modalite absente -> REFUS, jamais un repli silencieux")


# ═════════════════════════════════════════════════════════════════════════════
#  L'ASYMETRIE -- ce qui bouge, et ce qui NE BOUGE PAS
# ═════════════════════════════════════════════════════════════════════════════
class TestLAsymetrie(unittest.TestCase):
    """⚠️⚠️ LE CONTROLE LE MOINS CHER ET LE PLUS PARLANT : deux voisins traites
    differemment. Un plan ETIQUETE doit voir son prix bouger ; un plan NON
    etiquete doit garder EXACTEMENT celui d'hier. Si les deux bougeaient, le
    lot aurait deplace des euros que personne n'a arbitres ; si aucun ne
    bougeait, il n'aurait rien fait.
    """

    @classmethod
    def setUpClass(cls):
        cls.rcg = pipeline_complet(T.portefeuille_rcg(n=1500),
                                   _plan_tarifable('rc_generale'))
        cls.mrh = pipeline_complet(
            T.portefeuille_mrh(n=1500),
            dataclasses.replace(T.MRH, chargements=_CHARGEMENTS))

    def test_TX13_un_plan_ETIQUETE_bouge_un_plan_NU_ne_bouge_pas(self):
        r_etiquete = self.rcg.tarifer({
            'chiffre_affaires_eur': 600000, 'effectif': 20,
            'secteur_activite': 'BTP', 'anciennete_entreprise_ans': 10,
            'sous_traitance': 1, 'couverture_produits': 'Export',
            'sinistres_3ans_anterieurs': 0})
        self.assertEqual(r_etiquete['success'], True, r_etiquete.get('erreur'))
        rapport_e = (r_etiquete['prime_ttc']
                     / r_etiquete['prime_commerciale_ht'])
        self.assertAlmostEqual(rapport_e, 1.09, places=3,
            msg="rc_generale est etiquetee au taux residuel : sa taxe doit "
                "valoir 9 %, pas le repli de 33 %")

        # ⚠️⚠️ L'AUTRE MOITIE DE L'ASYMETRIE A CHANGE DE FORME AVEC LE REPLI.
        # Elle disait : << un plan non etiquete garde EXACTEMENT le prix
        # d'hier (x1,33) >>. Ce prix d'hier venait du repli, et le repli
        # n'existe plus. Ce qu'on peut affirmer maintenant est plus fort : un
        # plan sans regime obtient sa prime commerciale HT -- ses chargements
        # sont declares -- mais AUCUNE prime TTC, parce qu'aucun taux de taxe
        # n'existe pour lui. *Le refus se voit, il ne se devine pas.*
        r_nu = self.mrh.tarifer({
            'surface_m2': 75, 'etage': 2, 'alarme': 1, 'double_vitrage': 1,
            'garantie_vol': 1, 'zone_geographique': 'Urbaine',
            'statut_occupation': 'Locataire', 'type_logement': 'Appartement',
            'valeur_mobilier': 30000, 'annee_construction': 1990})
        self.assertGreater(r_nu['prime_commerciale_ht'], 0,
                           "les chargements sont declares : la prime HT doit "
                           "exister")
        self.assertIsNone(r_nu['prime_ttc'],
                          "un plan sans regime fiscal a recu une prime TTC : "
                          "un taux de taxe est apparu sans etre declare")
        # ⚠️ ET LE REFUS EST DIT. `regime_fiscal` ne vaut plus `None` ici : il
        # porte le MOTIF. Un `None` se lit << rien a signaler >> ; ce n'est pas
        # le cas — il y a quelque chose a signaler, et c'est meme la raison
        # pour laquelle aucun prix TTC ne sort.
        self.assertIsNotNone(r_nu['regime_fiscal'], "le refus est MUET")
        self.assertIn('AUCUN TAUX DE TAXE', r_nu['regime_fiscal'])
        print(f"    TX-13 ASYMETRIE : rc_generale x{rapport_e:.4f} (9 %, "
              f"sourcee) · mrh HT={r_nu['prime_commerciale_ht']} mais "
              f"TTC=None (aucun taux declare)")

    def test_TX10_l_appelant_EXPLICITE_l_emporte_sur_le_regime_du_plan(self):
        """⚠️ Des chargements passes a l'appel sont une decision sur CE calcul :
        les ecraser par le registre reviendrait a ignorer un parametre qu'on
        accepte. C'est l'ordre deja arbitre pour `_chargements_effectifs`.

        ⚠️⚠️ L'ORACLE A ETE RESSERRE LE 10/09/2026, ET DANS LE SENS STRICT. Il
        exigeait `regime_fiscal is None` -- le SILENCE -- pour empecher
        d'attester un taux qui n'avait pas servi. Mais se taire ne protege de
        rien : mesure du 10/09, un TTC partait signe avec `regime_fiscal:
        None`, donc un taux sans article, sans date d'entree en vigueur et sans
        date de relecture, et RIEN dans le document ne le disait. Le motif du
        test etait juste, son oracle le confondait avec l'absence. Il verifie
        desormais ce que le motif voulait vraiment : la phrase n'atteste PAS le
        regime du plan, et elle NOMME le taux qui a servi ainsi que sa
        provenance. *Un silence ne se relit pas ; une phrase, si.*"""
        force = pipeline_complet(
            T.portefeuille_rcg(n=1200), _plan_tarifable('rc_generale'),
            chargements={'frais': 0.15, 'commission': 0.10, 'marge': 0.03,
                         'taxes': 0.20})
        r = force.tarifer({
            'chiffre_affaires_eur': 600000, 'effectif': 20,
            'secteur_activite': 'BTP', 'anciennete_entreprise_ans': 10,
            'sous_traitance': 1, 'couverture_produits': 'Export',
            'sinistres_3ans_anterieurs': 0})
        rapport = r['prime_ttc'] / r['prime_commerciale_ht']
        self.assertAlmostEqual(rapport, 1.20, places=3,
            msg="le regime du plan a ecrase des chargements EXPLICITES")
        phrase = r['regime_fiscal']
        self.assertIsNotNone(
            phrase, "un TTC publie sans un mot sur l'origine de son taux est "
                    "un taux sans provenance dans un document signe")
        # ⚠️ CE QUE LE MOTIF D'ORIGINE PROTEGEAIT : ne pas attester le regime
        # du PLAN, qui n'a pas servi. `rc_generale` porte un regime au
        # registre ; ni son article ni son taux ne doivent apparaitre.
        regime_du_plan_ = REGIMES[_plan('rc_generale').regime_fiscal]
        self.assertNotIn(regime_du_plan_.reference, phrase,
                         "l'article du CGI du regime du plan atteste un taux "
                         "qui n'a PAS ete applique")
        self.assertNotIn(f"{100 * regime_du_plan_.taux:.4g} %", phrase,
                         "le taux du registre n'a pas servi : le publier "
                         "attesterait le mauvais nombre")
        # ⚠️ ET CE QUE LE SILENCE NE DISAIT PAS : le taux qui a REELLEMENT
        # servi, d'ou il vient, et ce qu'il n'est pas.
        self.assertIn('20 %', phrase, "le taux applique doit etre nomme")
        self.assertIn("FOURNI A L'APPEL", phrase.upper(),
                      "la provenance du taux applique doit etre publiee")
        for manque in ('article', 'vigueur', 'relecture'):
            self.assertIn(manque, phrase.lower(),
                          f"la phrase doit dire ce qui MANQUE a ce taux "
                          f"('{manque}') : une provenance pauvre se publie, "
                          f"elle ne se maquille pas en provenance sourcee")
        print(f"    TX-10 appelant explicite x{rapport:.4f} : il l'emporte, "
              f"et sa provenance est PUBLIEE")


# ═════════════════════════════════════════════════════════════════════════════
#  LA PEREMPTION ET LES PHRASES
# ═════════════════════════════════════════════════════════════════════════════
class TestPeremptionEtPhrases(unittest.TestCase):

    def test_TX11_VERT_AMBRE_ROUGE_et_sans_date_ROUGE(self):
        """⚠️⚠️ CE DIAGNOSTIC NE MESURE PAS UNE ERREUR. Un taux fiscal ne derive
        pas : il change ou il ne change pas. L'anciennete dit qu'une loi de
        finances a pu passer sans qu'un humain relise -- rien d'autre."""
        r = REGIMES['residuel_par_elimination']
        cas = ((date(2026, 12, 1), 'VERT'),
               (date(2027, 10, 1), 'AMBRE'),
               (date(2028, 10, 1), 'ROUGE'))
        for jour, attendu in cas:
            with self.subTest(jour=jour):
                self.assertEqual(
                    diagnostic_peremption(r, jour)['statut'], attendu)
        sans_date = REGIMES['habitation']._replace(verifie_le='')
        self.assertEqual(diagnostic_peremption(sans_date)['statut'], 'ROUGE',
                         "un taux dont personne n'a date la verification ne "
                         "peut pas porter une prime opposable")
        print("    TX-11 VERT / AMBRE / ROUGE, et sans date -> ROUGE")

    def test_TX12_la_phrase_de_repli_NE_MENT_PLUS(self):
        """⚠️⚠️ ELLE AFFIRMAIT << auto 33 %, MRH 30 %, RC 9 % >>. Deux des trois
        etaient faux : l'auto n'a pas de taux unique (33 % sur la RC, 18 % sur
        ses autres garanties) et la MRH non plus (30 % sur la seule composante
        incendie). *Un texte qui accompagne un comportement se relit quand ce
        comportement change.*"""
        nu = phrase_chargements_non_declares(T.MRH)
        self.assertIsNotNone(nu)
        self.assertIn('CHARGEMENTS NON DECLARES', nu)
        self.assertNotIn('MRH 30', nu)
        # ⚠️⚠️ ELLE N ANNONCE PLUS UN REPLI : IL N Y EN A PLUS. Depuis
        # l'arbitrage du 08/09/2026, un plan sans chargements n'obtient pas un
        # prix approximatif -- il n'obtient PAS DE PRIME COMMERCIALE, et la
        # prime PURE sort quand meme. La phrase doit dire les deux.
        self.assertIn('aucune prime commerciale', nu.lower())
        self.assertIn('pure', nu.lower(),
                      "le refus doit dire ce qui RESTE publie, sinon il se lit "
                      "comme une panne")
        self.assertNotIn('repli', nu.lower(),
                         "le mot `repli` survit a la disparition du repli")
        print("    TX-12 phrase de refus : plus d'affirmation fausse, et elle "
              "dit ce qui reste publie")

    def test_TX12b_un_plan_qui_declare_son_REGIME_a_une_phrase_DIFFERENTE(self):
        """⚠️⚠️ DEUX SILENCES DIFFERENTS. Un plan qui declare son regime a une
        taxe SOURCEE, mais ses frais, sa commission et sa marge restent le
        repli. Se taire effacerait la moitie supposee ; dire << non declares >>
        effacerait la moitie sourcee."""
        # ⚠️⚠️ IL N Y A PLUS DE TROISIEME ETAT << PARTIELLEMENT >>, et c'est
        # l'arbitrage : les chargements ne sont plus a moitie declares par un
        # repli. Restent DEUX etats, et le second est le silence.
        nu = phrase_chargements_non_declares(_plan('rc_generale'))
        self.assertIsNotNone(nu, "un plan sans chargements doit le DIRE")
        self.assertIn('CHARGEMENTS NON DECLARES', nu)
        self.assertIsNone(
            phrase_chargements_non_declares(
                dataclasses.replace(T.MRH, chargements=_CHARGEMENTS)),
            "un avertissement permanent est un avertissement qu'on cesse de "
            "lire")
        print("    TX-12b deux etats : NON declares -> DIT ; declares -> "
              "silence")

    def test_TX12c_la_synthese_d_un_MIXTE_nomme_ses_composantes(self):
        """⚠️ Un refus qui ne dit pas ce qu'il faudrait declarer pour en sortir
        est un mur, pas un diagnostic."""
        phrase = synthese_regime_fiscal(
            dataclasses.replace(T.MRH, regime_fiscal='habitation'))
        self.assertIn('NON TRANCHE', phrase.upper())
        self.assertIn('incendie', phrase)
        self.assertIn('30 %', phrase)
        self.assertIn('9 %', phrase)
        print("    TX-12c un mixte publie ses composantes et leurs taux")


# ═════════════════════════════════════════════════════════════════════════════
#  UN REGIME *ROUTE* N'EST PAS UN REGIME *MIXTE* -- defaut D2 du 09/09/2026
# ═════════════════════════════════════════════════════════════════════════════
class TestUneRoutN_estPasUnMixte(unittest.TestCase):
    """⚠️⚠️ LE MEME BLOC SIGNE ECRIVAIT << aucune prime TTC n'est publiee >> ET
    PUBLIAIT NEUF PRIMES TTC. Mesure du 10/09/2026 sur `flotte_automobile` :
    la phrase du bloc appelle `synthese_regime_fiscal(plan)` SANS contrat, la
    table de detail resout, elle, contrat par contrat -- neuf TTC sur dix
    lignes, 131 644,24 EUR sous une phrase affirmant qu'aucun ne l'etait. *Un
    commissaire aux comptes doit alors conclure que l'un des deux ment.*
    """

    REFUS = "aucune prime TTC n'est publiee"
    ROUTE = 'REGIME FISCAL ROUTE, NON RESOLU A CE NIVEAU'

    def test_TX18_une_route_SANS_contrat_ne_refuse_plus_le_TTC(self):
        """⚠️ Le fait a publier n'est pas << pas de prix >> mais << pas A CE
        NIVEAU >>."""
        phrase = synthese_regime_fiscal(_plan('flotte_automobile'))
        self.assertIsNotNone(phrase)
        self.assertNotIn(self.REFUS, phrase,
                         "le bloc affirme qu'aucun TTC n'est publie alors que "
                         "sa propre table de detail en publie")
        self.assertTrue(phrase.startswith(self.ROUTE), phrase[:120])
        self.assertIn('CONTRAT PAR CONTRAT', phrase.upper(),
                      "la phrase doit dire OU le regime se resout, sinon elle "
                      "se lit comme une panne")
        print("    TX-18 route sans contrat : plus de refus, et le niveau de "
              "resolution est DIT")

    def test_TX18b_la_phrase_annonce_les_TTC_que_le_detail_publie(self):
        """⚠️⚠️ ELLE NE SE CONTENTE PAS DE NE PLUS MENTIR -- elle ANNONCE. Un
        lecteur qui voit des TTC sous une phrase muette sur eux doit deviner
        d'ou ils sortent ; le silence entre deux sections se lit comme un
        lien."""
        phrase = synthese_regime_fiscal(_plan('flotte_automobile'))
        self.assertIn('TTC', phrase, "les primes TTC du detail ne sont pas "
                                     "annoncees par la phrase du bloc")
        self.assertIn('detail', phrase.lower())
        # ⚠️ ET LES BRANCHES RESTENT NOMMEES : un refus -- ou un renvoi -- qui
        # ne dit pas ce qu'il faudrait declarer est un mur, pas un diagnostic.
        for modalite in ('VL', 'VUL', 'PL', 'Mixte'):
            self.assertIn(modalite, phrase,
                          f"la branche '{modalite}' n'est pas nommee")
        print("    TX-18b la phrase ANNONCE les TTC du detail et nomme ses "
              "quatre branches")

    def test_TX18c_LE_SCEAU_le_garde_a_ete_SEPARE_et_non_ELARGI(self):
        """⚠️⚠️ LE CONTROLE CENTRAL DE CE CORRECTIF, ET IL PORTE SUR LES SIX
        SITES. Le risque n'est pas que la route cesse de refuser : c'est que le
        refus s'ouvre AILLEURS. Un plant qui mettrait `routage_non_resolu=True`
        sur un autre site -- ou qui ferait de `synthese_regime_fiscal` une
        phrase unique -- doit faire rougir ceci. *La question a tout garde-fou
        est << sur quelle assiette ? >>, et la reponse ici est UN site sur
        six.*
        """
        cas = [(f'registre {nom}',
                dataclasses.replace(_plan('flotte_automobile'),
                                    regime_fiscal=nom), None)
               for nom, r in sorted(REGIMES.items())
               if isinstance(r, RegimeMixte)]
        cas.append(('declare MIXTE_NON_TRANCHE',
                    dataclasses.replace(_plan('flotte_automobile'),
                                        regime_fiscal=MIXTE_NON_TRANCHE),
                    None))
        cas.append(('route modalite HORS enumeration',
                    _plan('flotte_automobile'),
                    {'type_flotte': 'Tracteur agricole'}))
        self.assertGreaterEqual(
            len(cas), 6, "l'assiette du sceau s'est retrecie : des regimes "
                         "mixtes ont disparu du registre sans que ce controle "
                         "le voie")
        for nom, plan, contrat in cas:
            with self.subTest(site=nom):
                r = regime_du_plan(plan, contrat)
                self.assertIsInstance(r, RegimeMixte)
                self.assertFalse(
                    r.routage_non_resolu,
                    f"'{nom}' est un VRAI refus : lever le drapeau ici "
                    f"publierait un renvoi la ou aucune prime TTC ne doit "
                    f"sortir")
                phrase = synthese_regime_fiscal(plan, contrat)
                self.assertIn(self.REFUS, phrase,
                              f"'{nom}' a perdu son refus")
                self.assertNotIn(self.ROUTE, phrase)
        # ⚠️ ET L'ASYMETRIE, le revelateur le moins cher : le SEUL site qui
        # doit changer change bien.
        seul = regime_du_plan(_plan('flotte_automobile'), None)
        self.assertTrue(seul.routage_non_resolu,
                        "le site VISE n'a pas change : le correctif ne mord "
                        "sur rien")
        print(f"    TX-18c SCEAU : {len(cas)} vrais refus intacts, 1 seul "
              f"site route -- garde SEPARE, pas elargi")

    def test_TX18d_un_MIXTE_construit_a_la_main_refuse_TOUJOURS(self):
        """⚠️ CONTRE-EPREUVE SUR LE DEFAUT PAR DEFAUT. Le champ vaut `False`
        sans qu'on le dise : un `RegimeMixte` ecrit ailleurs, demain, refusera
        sans avoir a connaitre ce correctif."""
        mixte = RegimeMixte(
            composantes=(("une garantie", 0.09, 'CGI art. 1001-6°'),),
            motif="Motif de controle.", verifie_le='2026-09-10')
        self.assertFalse(mixte.routage_non_resolu,
                         "le drapeau doit etre BAISSE par defaut : un refus "
                         "qui s'ouvre tout seul est pire que pas de refus")
        plan = dataclasses.replace(T.MRH, regime_fiscal='habitation')
        self.assertIn(self.REFUS, synthese_regime_fiscal(plan))
        print("    TX-18d drapeau BAISSE par defaut, refus intact")

    def test_TX18e_le_4e_champ_ne_casse_AUCUN_consommateur(self):
        """⚠️⚠️ UN CHAMP, PAS UN TYPE NOUVEAU. Les consommateurs testent
        `isinstance(regime, TauxTaxe)` ; releve AST du 10/09/2026 sur tout le
        depot : zero construction positionnelle, zero depaquetage, zero test de
        longueur. Ce controle tient la propriete cote comportement."""
        r = regime_du_plan(_plan('flotte_automobile'))
        self.assertIsInstance(r, RegimeMixte)
        self.assertNotIsInstance(r, TauxTaxe)
        self.assertIsNone(taux_applicable(_plan('flotte_automobile')),
                          "une route sans contrat n'a toujours PAS de taux "
                          "unique : le renvoi ne cree pas un nombre")
        self.assertEqual(len(r.composantes), 4)
        self.assertTrue(r.motif)
        print("    TX-18e retro-compatible : isinstance, taux_applicable et "
              "les champs d'origine intacts")


# ═════════════════════════════════════════════════════════════════════════════
#  AUCUN TAUX MUET -- defaut D3 du 09/09/2026
# ═════════════════════════════════════════════════════════════════════════════
class TestAucunTauxMuet(unittest.TestCase):
    """⚠️⚠️ TROIS SOURCES DE TAUX, DEUX SANS AUCUNE PROVENANCE PUBLIEE. Le
    commentaire du site affirmait << le taux ne peut venir que de deux
    endroits >> ; le releve AST du 10/09/2026 en compte TROIS qui rendent un
    taux, et DEUX rendaient `phrase=None`. Un TTC partait signe avec
    `regime_fiscal: None` : un taux sans article, sans date d'entree en vigueur
    et sans date de relecture, et rien dans le document ne le disait.
    """

    @classmethod
    def setUpClass(cls):
        cls.pf = T.portefeuille_rcg(n=1200)
        cls.contrat = {
            'chiffre_affaires_eur': 600000, 'effectif': 20,
            'secteur_activite': 'BTP', 'anciennete_entreprise_ans': 10,
            'sous_traitance': 1, 'couverture_produits': 'Export',
            'sinistres_3ans_anterieurs': 0}
        cls.muet = dataclasses.replace(_plan_tarifable('rc_generale'),
                                       regime_fiscal=None)

    def _tarifer(self, plan, chargements):
        return pipeline_complet(self.pf, plan,
                                chargements=chargements).tarifer(
                                    dict(self.contrat))

    def test_TX19_LE_SCEAU_aucune_branche_ne_rend_un_taux_SANS_provenance(self):
        """⚠️⚠️ LE CONTROLE CENTRAL DE CE CORRECTIF, ET IL EST *COMPORTEMENTAL*.

        Lire le TEXTE du code dirait seulement qu'une phrase y est ecrite ; ce
        controle EXECUTE les quatre branches et lit ce qui SORT. Un plant qui
        remettrait `None` sur l'une des deux branches rendues bavardes doit
        faire rougir ceci.
        """
        matrice = (
            ('appelant explicite', self.muet,
             {'frais': 0.15, 'commission': 0.10, 'marge': 0.03,
              'taxes': 0.25}, 0.25),
            ('plan.chargements.taxes',
             dataclasses.replace(
                 self.muet,
                 chargements=dataclasses.replace(_CHARGEMENTS, taxes=0.20)),
             None, 0.20),
            ('registre regime_fiscal', _plan_tarifable('rc_generale'),
             None, None),
        )
        for nom, plan, ch, attendu in matrice:
            with self.subTest(source=nom):
                r = self._tarifer(plan, ch or _COMMERCIAUX)
                self.assertIsNotNone(
                    r['prime_ttc'],
                    f"'{nom}' devait produire un TTC : le controle porterait "
                    f"alors sur une branche qui n'est pas empruntee")
                self.assertIsNotNone(
                    r['regime_fiscal'],
                    f"'{nom}' publie un TTC SANS un mot sur l'origine de son "
                    f"taux -- un taux sans provenance dans un document signe")
                self.assertIn('Taxe appliquee', r['regime_fiscal'])
                if attendu is not None:
                    applique = r['prime_ttc'] / r['prime_commerciale_ht'] - 1
                    self.assertAlmostEqual(
                        applique, attendu, places=3,
                        msg=f"'{nom}' : le taux APPLIQUE a bouge")
                    self.assertIn(f"{100 * attendu:.4g} %", r['regime_fiscal'],
                                  "la phrase doit nommer le taux REELLEMENT "
                                  "applique, pas un autre")
        print("    TX-19 SCEAU : 3/3 sources publient leur origine, et le "
              "taux publie est celui qui a servi")

    def test_TX19b_les_sources_HORS_registre_disent_ce_qu_elles_NE_sont_PAS(self):
        """⚠️⚠️ UNE PROVENANCE PAUVRE SE PUBLIE, ELLE NE SE MAQUILLE PAS. Une
        phrase qui dirait seulement << taxe 20 % >> se lirait comme un taux
        source. Ces deux-la doivent nommer les trois choses qui leur manquent
        -- article, entree en vigueur, relecture -- sinon elles empruntent
        l'autorite du registre sans en porter les obligations."""
        cas = (
            ('appelant', self.muet,
             {'frais': 0.15, 'commission': 0.10, 'marge': 0.03,
              'taxes': 0.25}),
            ('plan', dataclasses.replace(
                self.muet,
                chargements=dataclasses.replace(_CHARGEMENTS, taxes=0.20)),
             None),
        )
        for nom, plan, ch in cas:
            with self.subTest(source=nom):
                phrase = self._tarifer(
                    plan, ch or _COMMERCIAUX)['regime_fiscal']
                for manque in ('article', 'vigueur', 'relecture'):
                    self.assertIn(manque, phrase.lower(),
                                  f"'{nom}' ne dit pas qu'il lui manque "
                                  f"'{manque}'")
                self.assertNotIn('CGI art.', phrase,
                                 f"'{nom}' s'attribue un article du CGI qu'il "
                                 f"n'a pas")
        print("    TX-19b les deux sources hors registre nomment les trois "
              "choses qui leur manquent")

    def test_TX19c_le_taux_du_PLAN_dit_QUI_l_a_declare_et_QUAND(self):
        """⚠️ Un chargement decide du prix paye : un regulateur demande QUI l'a
        fixe. Le bloc `chargements` porte deja `declare_par` et `declare_le`,
        obligatoires au plan -- la phrase les publie."""
        plan = dataclasses.replace(
            self.muet,
            chargements=dataclasses.replace(_CHARGEMENTS, taxes=0.20))
        phrase = self._tarifer(plan, _COMMERCIAUX)['regime_fiscal']
        self.assertIn(_CHARGEMENTS.declare_par, phrase)
        self.assertIn(_CHARGEMENTS.declare_le, phrase)
        self.assertIn(plan.lob, phrase, "la phrase doit nommer le PLAN dont "
                                        "le bloc chargements porte ce taux")
        print("    TX-19c le taux declare au plan dit QUI et QUAND")

    def test_TX19d_CONTRE_EPREUVE_le_cas_sans_aucun_taux_refuse_TOUJOURS(self):
        """⚠️⚠️ LE CORRECTIF REND DES BRANCHES BAVARDES : il ne doit pas rendre
        une branche PAYANTE. Sans regime au plan et sans taxe a l'appel, aucun
        taux n'existe -- et il n'en apparait pas un."""
        r = self._tarifer(self.muet, _COMMERCIAUX)
        self.assertIsNone(r['prime_ttc'],
                          "un taux est apparu la ou aucune source n'en "
                          "declare : le correctif a INVENTE un taux fiscal")
        self.assertGreater(r['prime_commerciale_ht'], 0,
                           "la prime HT reste publiee : le refus porte sur la "
                           "TAXE")
        self.assertIn('AUCUN TAUX DE TAXE', r['regime_fiscal'])
        print("    TX-19d contre-epreuve : pas de source -> pas de TTC, et le "
              "motif est DIT")

    def test_TX19e_AUCUN_return_ne_rend_un_taux_sans_phrase(self):
        """⚠️⚠️ LA PROPRIETE, PAS SES TROIS EXEMPLES. Les controles ci-dessus
        executent les branches CONNUES ; celui-ci releve par AST *toutes* les
        sorties de la methode. Une sixieme branche ajoutee demain, muette,
        rougirait ici sans que personne ait pense a l'ajouter a la matrice."""
        src = inspect.getsource(TarifNonVie._taxe_du_contrat)
        arbre = ast.parse('if 1:\n' + src)
        sorties = [n for n in ast.walk(arbre) if isinstance(n, ast.Return)]
        self.assertGreaterEqual(len(sorties), 5,
                                "l'assiette du releve s'est retrecie")
        muets = [n.lineno - 1 for n in sorties
                 if (getattr(n.value, 'elts', None)
                     and len(n.value.elts) == 3
                     and isinstance(n.value.elts[2], ast.Constant)
                     and n.value.elts[2].value is None)]
        self.assertEqual(
            muets, [], f"{len(muets)} sortie(s) de `_taxe_du_contrat` rendent "
                       f"encore `phrase=None` (lignes relatives {muets}) : un "
                       f"TTC peut repartir sans provenance")
        print(f"    TX-19e {len(sorties)} sorties relevees par AST, 0 muette")


# ═════════════════════════════════════════════════════════════════════════════
#  L'ASSIETTE DE CE LOT -- ce qu'il couvre, et ce qu'il ne couvre PAS
# ═════════════════════════════════════════════════════════════════════════════
class TestLAssietteDuLot(unittest.TestCase):

    #: ⚠️⚠️ LES HUIT PLANS QUE CE LOT N'ETIQUETTE PAS, ET LE MOTIF DE CHACUN.
    #: Cette liste n'interdit rien : elle **oblige a passer par ici** pour
    #: etiqueter l'un d'eux, donc a lire pourquoi il ne l'etait pas. *Un lot
    #: qui ne nomme pas ce qu'il laisse dehors laisse croire qu'il a tout pris.*
    NON_ETIQUETES: ClassVar[dict[str, str]] = {
        'mrh': "MIXTE (incendie 30 % / reste 9 %) -- la methode de repartition "
               "attend l'arbitrage de Selasse",
        'multirisque_professionnelle': "MIXTE (incendie pro 12 % / reste 9 %)",
        'multirisque_immeuble': "MIXTE (incendie pro 12 % / reste 9 %)",
        'perte_exploitation': "MIXTE (pertes consecutives a incendie 12 % / "
                              "reste 9 %)",
        'bris_machine': "QUALIFICATION NON TRANCHEE (9 % ou 12 % selon le "
                        "rattachement -- disputee devant les tribunaux)",
        'risques_agricoles': "MIXTE, dont une contribution HORS TSCA (11 %, "
                             "code rural)",
        'assistance': "AUCUNE SOURCE : le document de reference ne nomme pas "
                      "cette branche, et l'assistance vendue AVEC un contrat "
                      "auto releve de 18 % -- vendue seule, c'est autre chose",
        'marchandises_transportees':
            "AUCUNE SOURCE, et un risque d'EXONERATION : le transport "
            "maritime, fluvial et aerien de marchandises est exonere de TSCA. "
            "Appliquer 9 % a une branche peut-etre exoneree serait inventer",
    }

    def test_TX15_les_huit_plans_non_etiquetes_le_sont_DELIBEREMENT(self):
        """⚠️⚠️ CE CONTROLE SCELLE UNE FRONTIERE D'ARBITRAGE, PAS UN CHIFFRE.

        Les etiqueter au taux residuel << parce que c'est le plus courant >>
        aurait ete exactement le geste que ce lot combat : un nombre a la place
        d'une decision. Les laisser nus ne deplace AUCUN euro -- ils gardent le
        repli d'aujourd'hui, et il est DIT.
        """
        etiquetes_par_erreur = {}
        for nom in sorted(self.NON_ETIQUETES):
            decl = getattr(_plan(nom), 'regime_fiscal', None)
            if decl:
                etiquetes_par_erreur[nom] = decl
        self.assertEqual(
            etiquetes_par_erreur, {},
            f"des plans listes comme NON etiquetes le sont : "
            f"{etiquetes_par_erreur}. Si c'est delibere, retirez-les de "
            f"`NON_ETIQUETES` en disant sur quelle source vous vous appuyez.")
        print(f"    TX-15 les {len(self.NON_ETIQUETES)} plans hors perimetre "
              f"restent nus, chacun avec son motif")

    def test_TX16_tout_plan_ETIQUETE_declare_un_regime_du_REGISTRE(self):
        """⚠️ Le miroir de TX-15 : ce que le lot couvre, il le couvre pour de
        bon. Un regime absent du registre n'a ni taux, ni source, ni date."""
        vus = {}
        for fichier in sorted(os.listdir(_PLANS)):
            if not fichier.endswith('.yaml'):
                continue
            nom = fichier[:-5]
            plan = _plan(nom)
            decl = getattr(plan, 'regime_fiscal', None)
            if not decl:
                continue
            noms = ([decl] if isinstance(decl, str)
                    else [r for _, r in decl.regimes])
            for n in noms:
                self.assertIn(n, REGIMES_ADMIS, f"plan '{nom}'")
            vus[nom] = noms
        self.assertEqual(len(vus), 12,
                         f"12 plans etiquetes attendus, {len(vus)} vus : "
                         f"{sorted(vus)}")
        print(f"    TX-16 les {len(vus)} plans etiquetes pointent tous vers le "
              f"registre")

    def test_TX17_aucun_taux_fiscal_EN_DUR_hors_du_registre(self):
        """⚠️⚠️ LE POINT DE TOUT LE LOT : **un seul endroit a modifier quand la
        loi change**. Un taux recopie dans un YAML ou dans le pipeline serait
        vingt endroits a corriger a la prochaine loi de finances -- et vingt
        occasions d'en oublier un.

        ⚠️ L'assiette est nommee : les vingt plans. Le repli `0.33` de
        `CHARGEMENTS_DEFAUT` reste, lui, dans `core/plan_tarifaire.py` : c'est
        le comportement d'hier pour les plans qui ne declarent rien, et il est
        DIT a chaque tarification.
        """
        coupables = []
        for fichier in sorted(os.listdir(_PLANS)):
            if not fichier.endswith('.yaml'):
                continue
            with open(os.path.join(_PLANS, fichier), encoding='utf-8') as fh:
                for i, ligne in enumerate(fh, 1):
                    nue = ligne.split('#')[0]
                    if 'taxes' in nue and ':' in nue:
                        coupables.append(f"{fichier}:{i} {ligne.strip()}")
        self.assertEqual(coupables, [],
            f"un taux de taxe est ecrit en dur dans un plan : {coupables}. "
            f"Le plan declare la QUALIFICATION (`regime_fiscal`), le registre "
            f"porte le NOMBRE.")
        print("    TX-17 aucun taux fiscal en dur dans les 20 plans")


if __name__ == '__main__':
    unittest.main(verbosity=2)
