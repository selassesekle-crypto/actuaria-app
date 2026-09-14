r"""
==============================================================================
  LE TOTAL COMMERCIAL APPLIQUE LE TAUX DE CHAQUE CONTRAT
==============================================================================

⚠️⚠️ `D2` -- REPORT DU ROUND 4, CONFIRME LE 14/09/2026. `tarif_publie`
appelait `chargements_du_contrat(plan)` avec le PLAN SEUL, alors que sa
signature est `(plan, contrat, table)`. Sans `contrat`, l'exception PAR
CRITERE ne peut pas s'appliquer : un triplet UNIQUE etait multiplie a
toute la serie.

*Pendant que le DETAIL, trente lignes plus haut, tarife contrat par
contrat.* Le meme bloc signe pouvait donc afficher un prix derogatoire a
la ligne 3 et l'ignorer dans son total.

Mesure du 14/09, plan `auto` + exception << commission 25 % sur Tiers >>,
2 000 contrats dont 824 derogatoires :

    publie (taux general partout)   857 017,78 EUR
    vrai   (taux par contrat)       917 525,53 EUR
    ecart                           -60 507,75 EUR   (-6,59 %)

Apres correctif : 917 525,53 EUR, ecart -0,00 EUR.

⚠️⚠️ LE CONSTAT EST LATENT AUJOURD'HUI, et on le DIT plutot que de
l'enfler : **0 des 20 plans livres ne declare de chargements**, donc
`ch` vaut `None` et aucune prime commerciale ne sort. `CH-6` mesure
cette assiette et la publie. Le defaut se produira le jour ou un client
declarera ses chargements -- c'est exactement ce que le bump
`s9 -> s10` de l'empreinte opposable a prepare.

⚠️ VECTORISE, PAS BOUCLE. Une exception par CRITERE ne depend que de la
modalite d'un axe : au plus `1 + len(cas)` triplets DISTINCTS, quel que
soit le nombre de contrats. Le depot a deja paye la boucle `iloc` --
3,13 s sur 3 000 lignes, 12,55 s sur 12 000, pour le meme resultat.

⚠️⚠️ CE QUI NE PEUT PAS S'APPLIQUER EST DIT. `TableExceptionsContrat` est
une DECLARATION : la table vit HORS DEPOT, parce qu'un identifiant de
contrat dans un YAML versionne publiquement serait une donnee
personnelle publiee. `tarif_publie` ne la recoit pas. *On declare, on ne
certifie pas* -- et la reserve atteint les DEUX formats, `CH-3`.
==============================================================================
"""
from __future__ import annotations

import ast
import dataclasses
import io
import logging
import os
import pathlib
import re
import sys
import unittest
import warnings
import zipfile

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

import numpy as np

from core.chargements_declares import (
    CasException,
    ExceptionsChargements,
    TableExceptionsContrat,
    chargements_du_contrat,
)
from core.plan_tarifaire import Chargements, PlanTarifaire
from direction_non_vie.tarification import test_plan_invariants as T
from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
from direction_non_vie.tarification.services import rapport_modeles_tarif as RM

_SOURCE = (_RACINE / 'direction_non_vie' / 'tarification' / 'services'
           / 'rapport_modeles_tarif.py')
_PLANS = _RACINE / 'plans'
_GENERAL = {'frais': 0.15, 'commission': 0.10, 'marge': 0.03,
            'declare_par': 'Direction Technique', 'declare_le': '2026-09-08'}
_AXE = 'garantie'
_DEROGE = 'Tiers'
_SHA_BIDON = 'b' * 64

_FIXTURE: dict = {}


def _fixture() -> dict:
    """⚠️ MEMORISEE : `pipeline_complet` sur 1 200 contrats coute cher, et
    une fixture par classe dependrait de l'ordre de decouverte."""
    if _FIXTURE:
        return _FIXTURE
    plan = PlanTarifaire.depuis_yaml(str(_PLANS / 'auto.yaml'))
    df = T.portefeuille_auto(1200, 11).reset_index(drop=True)
    _FIXTURE.update(plan=plan, df=df, tarif=pipeline_complet(df, plan))
    return _FIXTURE


def _avec(**kw) -> PlanTarifaire:
    f = _fixture()
    return dataclasses.replace(f['plan'],
                               chargements=Chargements(**_GENERAL, **kw))


_EXCEPTION = ExceptionsChargements(
    selon=_AXE,
    cas=((_DEROGE, CasException(commission=0.25,
                                motif='accord de distribution',
                                declare_par='Direction Commerciale',
                                declare_le='2026-09-08')),))


def _somme_contrat_par_contrat(plan, tarif, df) -> float:
    """La VERITE, calculee autrement : chaque contrat avec SES taux.

    ⚠️ Cette reference n'emploie AUCUN code du correctif -- ni son helper,
    ni sa formule. *Une contre-mesure qui passe par le chemin qu'elle
    verifie ne verifie rien.*"""
    pure = np.asarray(tarif.predire_portefeuille(df)['prime_pure'],
                      dtype=float)
    total = 0.0
    for rang, contrat in enumerate(df.to_dict('records')):
        v = chargements_du_contrat(plan, contrat)[0]
        total += float(pure[rang]) * (1 + v['frais']) * (1 + v['marge']) \
            / (1 - v['commission'])
    return round(total, 2)


def _texte_word(octets) -> str:
    with zipfile.ZipFile(io.BytesIO(octets)) as z:
        xml = z.read('word/document.xml').decode('utf-8', 'replace')
    return ' | '.join(re.compile(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>',
                                 re.DOTALL).findall(xml))


class TestChargementsParContratAuTotal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._journal = logging.getLogger()
        cls._niveau = cls._journal.level
        cls._journal.setLevel(logging.CRITICAL)
        warnings.filterwarnings('ignore')
        f = _fixture()
        cls.df, cls.tarif = f['df'], f['tarif']

    @classmethod
    def tearDownClass(cls):
        cls._journal.setLevel(cls._niveau)

    # ── CH-1 ─────────────────────────────────────────────────────────────
    def test_CH1_LE_TOTAL_est_la_somme_des_contrats_pas_un_taux_moyen(self):
        """⚠️⚠️ L'EURO. Le total publie doit egaler, au centime, la somme
        obtenue contrat par contrat."""
        plan = _avec(exceptions=_EXCEPTION)
        publie = RM.tarif_publie(pipeline_complet(self.df, plan), self.df)
        somme = publie['total']['somme_prime_commerciale_ht']
        vrai = _somme_contrat_par_contrat(
            plan, pipeline_complet(self.df, plan), self.df)
        n_derog = int((self.df[_AXE] == _DEROGE).sum())
        self.assertGreater(
            n_derog, 0,
            "aucun contrat ne porte la modalite derogatoire : ce controle "
            "s'exercerait sur une assiette ou la violation ne peut pas "
            "survenir")
        self.assertAlmostEqual(
            somme, vrai, places=2,
            msg=f"le total publie n'est PAS la somme des contrats : "
                f"publie {somme:,.2f} EUR contre {vrai:,.2f} EUR, ecart "
                f"{somme - vrai:,.2f} EUR sur {n_derog} contrat(s) "
                f"derogatoires.")
        print(f"    CH-1 SCEAU : {somme:,.2f} EUR = somme contrat par "
              f"contrat, {n_derog}/{len(self.df)} derogatoires")

    # ── CH-2 ─────────────────────────────────────────────────────────────
    def test_CH2_SANS_exception_le_total_ne_bouge_pas(self):
        """La contre-epreuve : le cas DEJA CORRECT doit rendre exactement ce
        qu'il rendait -- le taux general applique a toute la serie."""
        plan = _avec()
        tarif = pipeline_complet(self.df, plan)
        publie = RM.tarif_publie(tarif, self.df)
        pure = publie['total']['somme_prime_pure']
        attendu = round(pure * (1 + _GENERAL['frais'])
                        * (1 + _GENERAL['marge'])
                        / (1 - _GENERAL['commission']), 2)
        self.assertAlmostEqual(
            publie['total']['somme_prime_commerciale_ht'], attendu, places=2,
            msg="sans exception declaree, le total n'est plus le taux "
                "general applique a la prime pure")
        self.assertEqual(
            publie['total']['n_contrats_chargement_derogatoire'], 0,
            "des contrats sont comptes derogatoires alors qu'aucune "
            "exception n'est declaree")
        self.assertIsNone(
            publie['total']['phrase_chargements'],
            "une reserve est publiee alors qu'il n'y a rien a reserver")
        print(f"    CH-2 SCEAU : sans exception -> "
              f"{publie['total']['somme_prime_commerciale_ht']:,.2f} EUR, "
              f"0 derogatoire, 0 reserve")

    # ── CH-3 ─────────────────────────────────────────────────────────────
    def test_CH3_la_reserve_atteint_les_DEUX_formats(self):
        """⚠️⚠️ UN FAIT PUBLIE A UN ENDROIT ET TU A L'AUTRE est exactement ce
        que ce chantier ferme depuis le debut. La table par contrat ne peut
        pas s'appliquer ici ; la reserve doit atteindre l'HTML ET le Word."""
        plan = _avec(exceptions_par_contrat=TableExceptionsContrat(
            source='accords commerciaux 2026', empreinte_sha256=_SHA_BIDON,
            nb_contrats=42, declare_par='Direction Commerciale',
            declare_le='2026-09-08'))
        tarif = pipeline_complet(self.df, plan)
        publie = RM.tarif_publie(tarif, self.df)
        reserve = publie['total']['phrase_chargements']
        self.assertTrue(
            reserve,
            "le plan declare une table d'exceptions PAR CONTRAT que ce "
            "service ne recoit pas, et aucune reserve n'est publiee")
        self.assertIn('42', reserve, "la reserve ne dit pas sa portee")
        a = {'result_a3': {'success': True, 'statut_rag': 'VERT',
                           'metriques': {}},
             'result_a6': {'success': True, 'statut_rag': 'VERT',
                           'modele_production': {'nom': 'x'}},
             'tarif': tarif, 'portefeuille': self.df, 'audit_id': 'D2'}
        h = RM.export_html(**a)
        if isinstance(h, bytes):
            h = h.decode('utf-8', 'replace')
        w = _texte_word(RM.export_word(**a))
        temoin = 'CHARGEMENTS PAR CONTRAT NON APPLIQUES'
        absents = [n for n, t in (('HTML', h), ('Word', w))
                   if temoin not in t]
        self.assertEqual(
            absents, [],
            f"{absents} ne publie(nt) pas la reserve. Le total y affirme "
            f"un montant que la table declaree aurait modifie.")
        print(f"    CH-3 SCEAU : reserve publiee au HTML ({len(h)} car.) "
              f"ET au Word ({len(w)} car.)")

    # ── CH-4 ─────────────────────────────────────────────────────────────
    def test_CH4_un_axe_ABSENT_du_portefeuille_se_DIT(self):
        """⚠️ ON NE DEVINE PAS. Appliquer le general en silence ferait passer
        une derogation SIGNEE pour une absence de derogation.

        ⚠️⚠️ IL A FALLU DEUX ESSAIS POUR ATTEINDRE CE CAS, et c'est une
        bonne nouvelle sur le depot. `valider_chargements` refuse deja, A LA
        CONSTRUCTION DU PLAN, une exception `selon` un facteur INCONNU
        (1er essai), puis une exception sur un facteur CONTINU sans
        modalites (2e essai). L'axe est donc toujours un facteur CATEGORIEL
        DECLARE. *Le cas reel n'est pas un plan mal ecrit : c'est un
        FICHIER CLIENT auquel la colonne declaree manque.*

        ⚠️ ET LA GARDE SE MESURE SUR LE HELPER, PAS SUR `tarif_publie` :
        un portefeuille ampute casse la fabrique du DETAIL bien avant
        d'atteindre les chargements (`KeyError: 'garantie'`, mesure du
        14/09). *La branche n'est donc pas atteignable par cette porte
        aujourd'hui -- on le DIT, et on scelle la garde la ou elle vit.*
        """
        plan = _avec(exceptions=_EXCEPTION)
        ampute = self.df.drop(columns=[_AXE])
        self.assertNotIn(
            _AXE, ampute.columns,
            "l'assiette de ce controle n'est pas celle qu'il annonce")
        coefficients, n_derog, reserve = \
            RM._coefficients_du_portefeuille(plan, ampute)
        reserve = reserve or ''
        self.assertIn(
            'EXCEPTIONS DE CHARGEMENT NON APPLIQUEES', reserve,
            f"l'axe declare manque au portefeuille et le total l'applique "
            f"en silence : {reserve[:80]!r}")
        self.assertEqual(
            n_derog, 0,
            "des contrats sont comptes derogatoires sur un axe absent")
        self.assertIsInstance(
            coefficients, float,
            "un axe absent doit rendre le coefficient GENERAL, un scalaire")
        print(f"    CH-4 SCEAU : axe absent -> reserve publiee "
              f"({len(reserve)} car.), 0 derogatoire, coefficient general "
              f"{coefficients:.4f}")

    # ── CH-5 ─────────────────────────────────────────────────────────────
    def test_CH5_les_DEUX_canaux_de_phrase_lisent_la_MEME_cle(self):
        """⚠️⚠️ LE RELEVE EST PAR AST ET IL PORTE SUR LES DEUX FORMATS. Une
        cle ajoutee a un seul canal est l'asymetrie que ce chantier a
        fermee quatre fois."""
        arbre = ast.parse(_SOURCE.read_bytes().decode('utf-8'))
        lus = []
        for n in ast.walk(arbre):
            if (isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'get' and n.args
                    and isinstance(n.args[0], ast.Constant)
                    and n.args[0].value == 'phrase_chargements'):
                lus.append(n.lineno)
        self.assertGreaterEqual(
            len(lus), 2,
            f"`phrase_chargements` n'est lue qu'a {len(lus)} endroit(s) "
            f"({lus}) : un format publie la reserve et l'autre se tait.")
        print(f"    CH-5 SCEAU : `phrase_chargements` lue a "
              f"{len(lus)} site(s) -> {lus}")

    # ── CH-6 ─────────────────────────────────────────────────────────────
    def test_CH6_L_ASSIETTE_du_constat_est_MESUREE_et_publiee(self):
        """⚠️ CE CONTROLE NE FERME RIEN : il MESURE. Le defaut est LATENT
        tant qu'aucun plan livre ne declare de chargements. Le jour ou l'un
        d'eux en declarera, ce compte le dira."""
        avec, illisibles = [], []
        for chemin in sorted(_PLANS.glob('*.yaml')):
            #: ⚠️ UN PLAN ILLISIBLE NE DISPARAIT PAS DE LA MESURE : il en
            #: ressort NOMME. Un `continue` muet ferait passer un plan
            #: casse pour un plan sans chargements.
            try:
                p = PlanTarifaire.depuis_yaml(str(chemin))
            except Exception as erreur:                       # noqa: BLE001
                illisibles.append((chemin.stem, type(erreur).__name__))
            else:
                if chargements_du_contrat(p)[0] is not None:
                    avec.append(chemin.stem)
        self.assertEqual(
            illisibles, [],
            f"des plans livres sont ILLISIBLES : {illisibles}. Ce releve "
            f"ne porte alors pas sur l'assiette qu'il annonce.")
        print(f"    CH-6 RELEVE : {len(avec)} plan(s) livre(s) declarent des "
              f"chargements -> constat "
              f"{'VIVANT ' + str(avec) if avec else 'LATENT'}")
        self.assertIsInstance(avec, list)


if __name__ == '__main__':
    unittest.main(verbosity=2)
