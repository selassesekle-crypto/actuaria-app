"""
==============================================================================
  LOT 1 -- LA PRIME PURE EST UN FAIT, LA PRIME COMMERCIALE EST UNE DECISION
==============================================================================

⚠️⚠️ CE QUE CE LOT FERME. Le depot appliquait `frais 15 % · commission 10 % ·
marge 3 %` a **vingt LoB sur vingt**, sans que personne les ait declarees.
L'enquete les fait remonter au commit `a17f058` du 14/07/2026 -- *le meme
commit, le meme jour et la meme absence de source que le `taxes: 0.33`* que le
registre fiscal a remplace. Mesure du 08/09/2026 : **20/20 plans ne declarent
AUCUNE des trois valeurs**, ni partiellement, ni completement.

  Ces trois nombres ne sont pas des faits actuariels : ils dependent du client
  et de son reseau de distribution. Un repli les devinait vingt fois.

LA REGLE ARBITREE
  · la **prime pure** se calcule TOUJOURS, sans condition ;
  · la **prime commerciale** n'existe QUE si le client a declare ses trois
    chargements -- sinon elle n'est pas calculee, et le refus est PUBLIE.

DEUX NIVEAUX, DEUX VOIES POUR UNE EXCEPTION
  Un taux general obligatoire et complet, puis des exceptions qui ne
  declarent que ce qui differe -- par CRITERE sur un axe categoriel du plan,
  ou par CONTRAT via une table qui vit HORS du depot et dont seul le SHA-256
  est declare. ⚠️ Les vingt plans sont versionnes publiquement : un
  identifiant de contrat y serait une donnee personnelle publiee.

ET DEUX DETTES FERMEES AU PASSAGE
  · `C-36` -- la decoupe du holdout etait positionnelle et MUETTE. Mesure :
    Gini de frequence x1,71, Gini de severite x8,9 selon le seul ordre des
    lignes. Elle se declare desormais, et sans declaration aucune validation
    n'est publiee.
  · le normaliseur du temoin de gel prenait `8:20` dans `s8:20fefd1a...` pour
    une heure : **le prefixe de schema lui etait invisible**.

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

from core.chargements_declares import (
    EXCEPTION_CONTRAT,
    EXCEPTION_CRITERE,
    GENERAL,
    NON_DECLARE,
    CasException,
    ExceptionsChargements,
    TableExceptionsContrat,
    chargements_du_contrat,
    empreinte_table,
)
from core.plan_tarifaire import CHARGEMENTS_DEFAUT, Chargements, PlanTarifaire
from core.validation_tarif import DecoupeValidation, indices_validation
from direction_non_vie.tarification import test_plan_invariants as T
from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
from direction_non_vie.tarification.services.gel_livrables import neutraliser

_PLANS = os.path.join(_RACINE, 'plans')
_SHA_BIDON = 'a' * 64


def _plan(nom: str) -> PlanTarifaire:
    return PlanTarifaire.depuis_yaml(os.path.join(_PLANS, f'{nom}.yaml'))


def _general(**kw) -> Chargements:
    """Le niveau general, complet et date -- la racine dont on herite."""
    champs = {'frais': 0.15, 'commission': 0.10, 'marge': 0.03,
              'declare_par': 'Direction Technique', 'declare_le': '2026-09-08'}
    champs.update(kw)
    return Chargements(**champs)


_CONTRAT_FLOTTE = {
    'taille_flotte': 20, 'valeur_moyenne_vehicule': 18000,
    'age_moyen_flotte': 6, 'puissance_moyenne': 120,
    'secteur_activite': 'Transport', 'zone_circulation': 'Periurbaine',
    'telematique': 1, 'sinistres_2ans_anterieurs': 0, 'type_flotte': 'VL',
}


# ═════════════════════════════════════════════════════════════════════════════
#  LA PRIME PURE EST UN FAIT
# ═════════════════════════════════════════════════════════════════════════════
class TestLaPrimePureEstInconditionnelle(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.plan = _plan('flotte_automobile')
        cls.df = T.portefeuille_flotte(n=1500)
        cls.nu = pipeline_complet(cls.df, cls.plan)
        cls.declare = pipeline_complet(
            cls.df, dataclasses.replace(cls.plan, chargements=_general()))

    def test_CD1_sans_AUCUNE_declaration_la_prime_pure_sort_quand_meme(self):
        """⚠️⚠️ C'EST LA MOITIE POSITIVE DE L'ARBITRAGE, et sans elle le lot
        n'aurait fait que retirer. Frequence x cout moyen, plus la charge
        grave, porte par l'exposition : rien la-dedans ne depend d'une
        decision commerciale."""
        r = self.nu.tarifer(_CONTRAT_FLOTTE)
        self.assertEqual(r['success'], True, r.get('erreur'))
        self.assertGreater(r['prime_pure'], 0)
        self.assertIsNone(r['prime_commerciale_ht'])
        self.assertIsNone(r['prime_ttc'])
        self.assertEqual(r['chargements_origine'], NON_DECLARE)
        print(f"    CD-1 sans declaration : prime_pure="
              f"{r['prime_pure']} EUR, commerciale refusee")

    def test_CD2_le_refus_est_DIT_et_il_dit_ce_qui_RESTE(self):
        """⚠️ Un refus muet se lit comme une panne. Celui-ci nomme ce qui
        manque, POURQUOI le systeme ne le devine pas, et ce qui reste
        publie."""
        phrase = self.nu.tarifer(_CONTRAT_FLOTTE)['chargements']
        self.assertIn('CHARGEMENTS NON DECLARES', phrase)
        for attendu in ('commercial', 'client', 'pure', 'declarez'):
            self.assertIn(attendu, phrase.lower(), attendu)
        print("    CD-2 le refus nomme le manque, la cause et ce qui reste")

    def test_CD3_LE_MIROIR_declares_la_prime_commerciale_existe(self):
        """⚠️⚠️ SANS CE SENS, UN GARDE QUI REFUSERAIT TOUJOURS PASSERAIT CD-1
        ET CD-2. *Un garde-fou ne se verifie que dans ses deux sens.*"""
        r = self.declare.tarifer(_CONTRAT_FLOTTE)
        self.assertGreater(r['prime_commerciale_ht'], 0)
        attendu = (r['prime_pure'] * 1.15 * 1.03) / 0.90
        self.assertAlmostEqual(r['prime_commerciale_ht'], attendu, places=1)
        self.assertEqual(r['chargements_origine'], GENERAL)
        self.assertIn('Direction Technique', r['chargements'])
        self.assertIn('2026-09-08', r['chargements'])
        print(f"    CD-3 declares : HT={r['prime_commerciale_ht']} EUR, "
              f"formule verifiee, auteur et date publies")

    def test_CD4_les_20_plans_rendent_TOUS_une_prime_pure(self):
        """⚠️ L'assiette est nommee : les vingt plans du depot, et aucun ne
        declare de chargements aujourd'hui (mesure du 08/09/2026)."""
        noms = sorted(f.stem for f in pathlib.Path(_PLANS).glob('*.yaml'))
        self.assertEqual(len(noms), 20)
        declarants = [n for n in noms if _plan(n).chargements is not None]
        self.assertEqual(
            declarants, [],
            f"des plans declarent des chargements : {declarants}. Si c'est "
            f"voulu, ce controle doit dire d'ou viennent les valeurs.")
        print(f"    CD-4 {len(noms)}/20 plans sans chargements declares, "
              f"tous tarifables en prime pure")


# ═════════════════════════════════════════════════════════════════════════════
#  LES EXCEPTIONS PAR CRITERE
# ═════════════════════════════════════════════════════════════════════════════
class TestExceptionsParCritere(unittest.TestCase):

    def _avec(self, cas) -> PlanTarifaire:
        return dataclasses.replace(
            _plan('flotte_automobile'),
            chargements=_general(exceptions=ExceptionsChargements(
                selon='type_flotte', cas=cas)))

    def test_CD5_LES_DEUX_SENS_l_exception_frappe_la_bonne_modalite(self):
        """⚠️⚠️ LE SCEAU DE CETTE VOIE, ET IL EXIGE LES DEUX MOITIES. Une
        exception qui s'appliquerait PARTOUT et une exception qui ne
        s'appliquerait NULLE PART echouent toutes deux a faire ce qu'on lui
        demande -- et un controle qui n'en verifie qu'une laisse passer
        l'autre."""
        plan = self._avec(
            (('PL', CasException(commission=0.05, motif='accord PL',
                                 declare_par='Souscription',
                                 declare_le='2026-04-02')),))
        # SENS 1 -- elle s'applique la ou elle est declaree
        v, origine, detail = chargements_du_contrat(
            plan, {**_CONTRAT_FLOTTE, 'type_flotte': 'PL'})
        self.assertEqual(origine, EXCEPTION_CRITERE)
        self.assertEqual(v['commission'], 0.05)
        self.assertEqual(detail['modalite'], 'PL')
        # SENS 2 -- et NULLE PART ailleurs
        for autre in ('VL', 'VUL', 'Mixte'):
            with self.subTest(type_flotte=autre):
                v2, o2, _ = chargements_du_contrat(
                    plan, {**_CONTRAT_FLOTTE, 'type_flotte': autre})
                self.assertEqual(o2, GENERAL)
                self.assertEqual(v2['commission'], 0.10)
        print("    CD-5 l'exception frappe PL, et PL seulement")

    def test_CD6_elle_HERITE_de_ce_qu_elle_ne_redeclare_pas(self):
        """⚠️ Sans ambiguite ICI, contrairement au cas fiscal : le niveau
        general est OBLIGATOIRE et COMPLET. Il y a toujours une valeur
        DECLAREE a heriter, jamais une valeur devinee."""
        plan = self._avec(
            (('PL', CasException(commission=0.05, motif='m',
                                 declare_par='S', declare_le='2026-04-02')),))
        v, _, detail = chargements_du_contrat(
            plan, {**_CONTRAT_FLOTTE, 'type_flotte': 'PL'})
        self.assertEqual(v['frais'], 0.15)
        self.assertEqual(v['marge'], 0.03)
        self.assertEqual(detail['champs'], ('commission',))
        print("    CD-6 heritage : seul `commission` est redeclare")

    def test_CD7_une_exception_QUI_NE_CHANGE_RIEN_est_refusee(self):
        """⚠️ Elle ferait croire a une derogation qui n'existe pas."""
        with self.assertRaises(ValueError) as ctx:
            self._avec((('PL', CasException(motif='m', declare_par='S',
                                            declare_le='2026-04-02')),))
        self.assertIn('AUCUN', str(ctx.exception).upper())
        print("    CD-7 exception sans redeclaration REFUSEE")

    def test_CD8_une_modalite_FANTOME_est_refusee(self):
        """⚠️⚠️ Une regle ecrite pour une modalite inexistante ne se declenche
        jamais : elle a l'apparence d'un garde-fou sans en etre un. C'est la
        lecon du verrou a sens unique de la frontiere LLM."""
        with self.assertRaises(ValueError) as ctx:
            self._avec((('Remorque', CasException(commission=0.05, motif='m',
                                                  declare_par='S',
                                                  declare_le='2026-04-02')),))
        self.assertIn('Remorque', str(ctx.exception))
        print("    CD-8 modalite fantome REFUSEE")

    def test_CD9_un_axe_INEXISTANT_est_refuse(self):
        with self.assertRaises(ValueError) as ctx:
            dataclasses.replace(
                _plan('flotte_automobile'),
                chargements=_general(exceptions=ExceptionsChargements(
                    selon='type_de_flotte',
                    cas=(('PL', CasException(commission=0.05, motif='m',
                                             declare_par='S',
                                             declare_le='2026-04-02')),))))
        self.assertIn('type_de_flotte', str(ctx.exception))
        print("    CD-9 axe inexistant REFUSE")

    def test_CD10_DEUX_exceptions_sur_la_MEME_modalite_sont_refusees(self):
        """⚠️ Laquelle s'applique deviendrait une affaire d'ordre dans le code,
        invisible depuis le document signe. *Quand deux declarations se
        contredisent, on refuse, on ne choisit pas.*"""
        c = CasException(commission=0.05, motif='m', declare_par='S',
                         declare_le='2026-04-02')
        with self.assertRaises(ValueError) as ctx:
            self._avec((('PL', c), ('PL', c._replace(commission=0.07))))
        self.assertIn('PL', str(ctx.exception))
        print("    CD-10 deux exceptions sur la meme modalite : REFUSEES")

    def test_CD11_motif_auteur_et_date_sont_OBLIGATOIRES(self):
        """⚠️ Une derogation au taux general sans motif ni auteur ni date n'est
        pas opposable."""
        for manquant in ('motif', 'declare_par', 'declare_le'):
            with self.subTest(champ=manquant):
                champs = {'commission': 0.05, 'motif': 'm',
                          'declare_par': 'S', 'declare_le': '2026-04-02'}
                champs[manquant] = ''
                with self.assertRaises(ValueError) as ctx:
                    self._avec((('PL', CasException(**champs)),))
                self.assertIn(manquant, str(ctx.exception))
        print("    CD-11 motif, auteur et date obligatoires sur une exception")


# ═════════════════════════════════════════════════════════════════════════════
#  LES EXCEPTIONS PAR CONTRAT -- ET LE RGPD
# ═════════════════════════════════════════════════════════════════════════════
class TestExceptionsParContrat(unittest.TestCase):

    def _plan_table(self) -> PlanTarifaire:
        return dataclasses.replace(
            _plan('flotte_automobile'),
            chargements=_general(
                exceptions_par_contrat=TableExceptionsContrat(
                    source='table client, hors depot',
                    empreinte_sha256=_SHA_BIDON, nb_contrats=2,
                    declare_par='Direction Technique',
                    declare_le='2026-09-08')))

    def test_CD12_RGPD_le_plan_ne_porte_AUCUN_identifiant(self):
        """⚠️⚠️ LA CONTRAINTE DURE, ET ELLE EST MESUREE, PAS SUPPOSEE. Les
        vingt plans sont versionnes dans un depot PUBLIC : un identifiant de
        contrat ecrit dans l'un d'eux serait une donnee personnelle publiee.
        La declaration ne porte donc que la provenance, le compte et le
        SHA-256 -- jamais une liste."""
        champs = {f.name for f in dataclasses.fields(TableExceptionsContrat)}
        self.assertEqual(
            champs, {'source', 'empreinte_sha256', 'nb_contrats',
                     'declare_par', 'declare_le'},
            "un champ a ete ajoute a la declaration de table : verifiez qu'il "
            "ne peut pas porter d'identifiant de contrat")
        # ⚠️ Et le SECOND SENS : le refus d'une cle surnumeraire.
        from core.chargements_declares import table_depuis_dict
        with self.assertRaises(ValueError) as ctx:
            table_depuis_dict({
                'source': 's', 'empreinte_sha256': _SHA_BIDON,
                'nb_contrats': 1, 'declare_par': 'D', 'declare_le': 'd',
                'identifiants': ['POL-001']})
        self.assertIn('identifiants', str(ctx.exception))
        print("    CD-12 RGPD : la declaration ne porte aucun identifiant, "
              "et refuse d'en accueillir un")

    def test_CD13_LES_DEUX_SENS_la_table_frappe_le_bon_contrat(self):
        plan = self._plan_table()
        table = {'POL-1': {'commission': 0.04, 'motif': 'grand compte'}}
        v, origine, detail = chargements_du_contrat(
            plan, {**_CONTRAT_FLOTTE, 'id_contrat': 'POL-1'}, table)
        self.assertEqual(origine, EXCEPTION_CONTRAT)
        self.assertEqual(v['commission'], 0.04)
        self.assertEqual(v['frais'], 0.15)
        self.assertIn('grand compte', detail['motif'])
        # SENS 2 -- un autre contrat n'est PAS touche
        v2, o2, _ = chargements_du_contrat(
            plan, {**_CONTRAT_FLOTTE, 'id_contrat': 'POL-2'}, table)
        self.assertEqual(o2, GENERAL)
        self.assertEqual(v2['commission'], 0.10)
        print("    CD-13 la table frappe POL-1, et POL-1 seulement")

    def test_CD14_le_PLUS_SPECIFIQUE_l_emporte(self):
        """⚠️ Un client qui nomme un contrat precis a voulu ce contrat precis,
        pas la moyenne de son segment."""
        plan = dataclasses.replace(
            _plan('flotte_automobile'),
            chargements=_general(
                exceptions=ExceptionsChargements(
                    selon='type_flotte',
                    cas=(('VL', CasException(commission=0.06, motif='m',
                                             declare_par='S',
                                             declare_le='2026-04-02')),)),
                exceptions_par_contrat=TableExceptionsContrat(
                    source='s', empreinte_sha256=_SHA_BIDON, nb_contrats=1,
                    declare_par='D', declare_le='2026-09-08')))
        v, origine, _ = chargements_du_contrat(
            plan, {**_CONTRAT_FLOTTE, 'type_flotte': 'VL',
                   'id_contrat': 'POL-1'},
            {'POL-1': {'commission': 0.04}})
        self.assertEqual(origine, EXCEPTION_CONTRAT)
        self.assertEqual(v['commission'], 0.04)
        print("    CD-14 table > critere > general")

    def test_CD15_l_empreinte_de_la_table_SUIT_son_contenu(self):
        """⚠️⚠️ SANS CELA, LA DECLARATION SIGNERAIT UNE TABLE ET LE CALCUL EN
        APPLIQUERAIT UNE AUTRE. L'empreinte porte le contenu, normalise et
        TRIE : deux lectures du meme fichier rendent le meme hash, quel que
        soit l'ordre des lignes."""
        a = [{'identifiant_contrat': 'POL-1', 'commission': 0.04},
             {'identifiant_contrat': 'POL-2', 'commission': 0.06}]
        self.assertEqual(empreinte_table(a), empreinte_table(list(reversed(a))))
        b = [{'identifiant_contrat': 'POL-1', 'commission': 0.05},
             {'identifiant_contrat': 'POL-2', 'commission': 0.06}]
        self.assertNotEqual(empreinte_table(a), empreinte_table(b),
                            "le contenu a change et l'empreinte n'a pas bouge")
        print("    CD-15 empreinte stable a l'ordre, sensible au contenu")

    def test_CD16_une_empreinte_MAL_FORMEE_est_refusee(self):
        for mauvaise in ('', 'abc', 'z' * 64, 'a' * 63):
            with self.subTest(sha=mauvaise[:8]),                     self.assertRaises(ValueError):
                dataclasses.replace(
                    _plan('flotte_automobile'),
                    chargements=_general(
                        exceptions_par_contrat=TableExceptionsContrat(
                            source='s', empreinte_sha256=mauvaise,
                            nb_contrats=1, declare_par='D',
                            declare_le='d')))
        print("    CD-16 empreinte mal formee REFUSEE")


# ═════════════════════════════════════════════════════════════════════════════
#  C-36 -- LA DECOUPE DE VALIDATION
# ═════════════════════════════════════════════════════════════════════════════
class TestDecoupeValidation(unittest.TestCase):

    def test_CD17_sans_decoupe_declaree_AUCUNE_validation(self):
        """⚠️⚠️ MESURE QUI FONDE CE CORRECTIF : MEMES donnees, seul l'ordre des
        lignes changeant, le Gini de frequence variait d'un facteur 1,71 et
        celui de severite d'un facteur 8,9. Un tel nombre ne peut pas
        accompagner un prix publie sans que l'hypothese soit declaree."""
        self.assertIsNone(indices_validation(T.portefeuille_auto(200, 1), None))
        plan = _plan('flotte_automobile')
        self.assertIsNone(plan.decoupe_validation)
        tarif = pipeline_complet(T.portefeuille_flotte(n=1200), plan)
        self.assertIsNone(tarif.validation)
        r = tarif.tarifer(_CONTRAT_FLOTTE)
        self.assertIsNone(r['validation'])
        self.assertIn('NON DECLAREE', r['validation_hypothese'])
        print("    CD-17 decoupe non declaree -> aucune validation, et DIT")

    def test_CD18_LE_MIROIR_declaree_la_validation_existe(self):
        """⚠️ Sans ce sens, un garde qui supprimerait TOUTE validation
        passerait CD-17."""
        plan = dataclasses.replace(
            _plan('flotte_automobile'),
            decoupe_validation=DecoupeValidation(methode='positionnelle'))
        tarif = pipeline_complet(T.portefeuille_flotte(n=1500), plan)
        self.assertIsNotNone(tarif.validation,
                             "decoupe declaree et pourtant aucune validation")
        r = tarif.tarifer(_CONTRAT_FLOTTE)
        self.assertIsNone(r['validation_hypothese'],
                          "un avertissement permanent cesse d'etre lu")
        print("    CD-18 decoupe declaree -> validation mesuree, phrase muette")

    def test_CD19_une_methode_INCOMPLETE_est_refusee(self):
        """⚠️ `aleatoire` sans graine publierait deux Gini differents pour le
        meme plan ; `chronologique` sans colonne trierait sur une date
        devinee. Et un parametre qui ne sert pas est un parametre qui PROMET."""
        for kw, mot in (
                ({'methode': 'aleatoire'}, 'graine'),
                ({'methode': 'chronologique'}, 'colonne'),
                ({'methode': 'positionnelle', 'graine': 7}, 'graine'),
                ({'methode': 'positionnelle', 'colonne': 'd'}, 'colonne'),
                ({'methode': 'au_hasard'}, 'inconnue')):
            with self.subTest(**kw):
                with self.assertRaises(ValueError) as ctx:
                    DecoupeValidation(**kw)
                self.assertIn(mot, str(ctx.exception))
        print("    CD-19 methode incomplete ou inconnue : REFUSEE")

    def test_CD20_une_decoupe_CHRONOLOGIQUE_ne_depend_plus_de_l_ordre(self):
        """⚠️⚠️ LE POINT DE C-36. Deux fichiers portant les MEMES lignes dans
        deux ordres differents doivent rendre la MEME decoupe des lors que la
        methode declare sur quoi trier."""
        df = T.portefeuille_auto(300, 3)
        df = df.assign(date_effet=range(len(df)))
        melange = df.sample(frac=1.0, random_state=0).reset_index(drop=True)
        d = DecoupeValidation(methode='chronologique', colonne='date_effet')
        tr_a, te_a = indices_validation(df, d)
        tr_b, te_b = indices_validation(melange, d)
        self.assertEqual(sorted(df['date_effet'].to_numpy()[tr_a]),
                         sorted(melange['date_effet'].to_numpy()[tr_b]))
        self.assertEqual(sorted(df['date_effet'].to_numpy()[te_a]),
                         sorted(melange['date_effet'].to_numpy()[te_b]))
        print("    CD-20 decoupe chronologique : identique aux deux ordres")

    def test_CD21_une_colonne_DECLAREE_et_ABSENTE_leve(self):
        """⚠️ Une declaration que le fichier ne tient pas ne se remplace pas en
        silence -- meme doctrine que `cout_par_sinistre`."""
        with self.assertRaises(ValueError) as ctx:
            indices_validation(
                T.portefeuille_auto(200, 1),
                DecoupeValidation(methode='chronologique',
                                  colonne='date_absente'))
        self.assertIn('date_absente', str(ctx.exception))
        print("    CD-21 colonne declaree et absente : LEVE")


# ═════════════════════════════════════════════════════════════════════════════
#  LE TEMOIN DE GEL, ET L'ASSIETTE DU LOT
# ═════════════════════════════════════════════════════════════════════════════
class TestGelEtAssiette(unittest.TestCase):

    def test_CD22_LES_DEUX_SENS_une_empreinte_n_est_plus_prise_pour_une_heure(
            self):
        """⚠️⚠️ MESURE DU 08/09/2026 : `s8:20fefd1aa55cf229` devenait
        `s<heure>fefd1aa55cf229` -- `8:20` etait pris pour une heure, et **le
        temoin de gel ne voyait plus le numero de schema**. Un bump dont le
        digest n'aurait pas change serait reste invisible. *Le garde a tenu au
        bump `s8` -> `s9` par chance, pas par construction.*"""
        for emp in ('s8:20fefd1aa55cf229', 's9:7ce0606a6b19e717',
                    's10:150492a0597035ce'):
            with self.subTest(empreinte=emp):
                self.assertEqual(neutraliser(emp), emp,
                                 "le prefixe de schema est masque")
        # ⚠️ ET LE SECOND SENS : une VRAIE heure reste neutralisee, sinon on
        # aurait repare le gel en cassant ce qu'il servait a faire.
        self.assertIn('<heure>', neutraliser('Imprime a 01:46'))
        self.assertIn('<horodatage>', neutraliser('le 05/09/2026 01:46'))
        print("    CD-22 empreintes preservees, heures toujours neutralisees")

    def test_CD23_AUCUN_chemin_de_prix_ne_lit_le_repli(self):
        """⚠️⚠️ LE CONTROLE QUI TIENT L'ARBITRAGE. `CHARGEMENTS_DEFAUT` existe
        encore -- des preuves d'audit figees le citent, et `core/elasticite.py`
        s'en sert comme CONVENTION de structure pour sa marge technique. Ce qui
        ne doit plus exister, c'est un chemin qui s'en sert pour fabriquer un
        PRIX. Releve PAR AST sur le module qui tarife."""
        chemin = pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification' \
            / 'pipeline_tarifaire.py'
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        lectures = [n.lineno for n in ast.walk(arbre)
                    if isinstance(n, ast.Name)
                    and n.id == 'CHARGEMENTS_DEFAUT'
                    and isinstance(n.ctx, ast.Load)]
        self.assertEqual(
            lectures, [],
            f"`CHARGEMENTS_DEFAUT` est LU dans le module de tarification aux "
            f"lignes {lectures} : le repli que ce lot supprime est revenu par "
            f"une autre porte.")
        # ⚠️ Et il reste ce qu'il est devenu : une convention, pas un tarif.
        self.assertEqual(sorted(CHARGEMENTS_DEFAUT),
                         ['commission', 'frais', 'marge', 'taxes'])
        print("    CD-23 aucun chemin de prix ne lit le repli (releve AST)")

    def test_CD24_le_bloc_chargements_est_DANS_l_empreinte(self):
        """⚠️ Deux plans dont l'auteur, la date ou une exception different ne
        portent pas la meme responsabilite -- c'est l'argument du
        `commentaire`, hache depuis `s4`."""
        base = dataclasses.replace(_plan('flotte_automobile'),
                                   chargements=_general())
        autre_auteur = dataclasses.replace(
            base, chargements=_general(declare_par='Souscription'))
        avec_exc = dataclasses.replace(
            base, chargements=_general(exceptions=ExceptionsChargements(
                selon='type_flotte',
                cas=(('PL', CasException(commission=0.05, motif='m',
                                         declare_par='S',
                                         declare_le='2026-04-02')),))))
        empreintes = {base.empreinte(), autre_auteur.empreinte(),
                      avec_exc.empreinte()}
        self.assertEqual(len(empreintes), 3,
                         "deux plans qui facturent ou engagent differemment "
                         "signent pareil")
        print("    CD-24 trois declarations, trois empreintes distinctes")


if __name__ == '__main__':
    unittest.main(verbosity=2)
