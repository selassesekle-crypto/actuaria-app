"""
==============================================================================
  D1 + D7 -- L'ASSIETTE DU BLOC PRIX, ET CE QU'IL IMPUTE EN SILENCE
==============================================================================

⚠️⚠️ DEUX DEFAUTS D'UNE MEME CAUSE : L'ASYMETRIE ENTRE VOISINS. Un garde pose
a une porte et pas a sa jumelle.

D1 -- A2 APPLIQUE DEUX FOIS SUR LE CHEMIN DU PRIX PUBLIE
  A6 remettait `result_a2['dataframe']` au rapport ; or le prix se calcule en
  RE-APPLIQUANT A2 (`predire_portefeuille` -> `_design` -> `a2.transform`).
  Le tarif, lui, est ajuste sur UNE seule application. *Le lot precedent avait
  ferme la CONSTRUCTION du tarif et laisse sa PUBLICATION ouverte.*
  Mesure du 10/09/2026, 3 000 lignes : total publie 1 103 945,59 EUR au lieu
  de 1 099 487,51 -- ecart +4 458,08 EUR (+0,4055 %), 53 contrats deplaces,
  jusqu'a 55,98 % sur un contrat. Mecanisme isole, sans aucun GLM : cinq
  colonnes changent au second passage, dont `risque_historique` sur 82 lignes.

D7 -- LE TOTAL IMPUTE LA OU LE DETAIL REFUSE
  `anomalies_du_contrat` n'a qu'UN appelant : `tarifer()`, qui produit le
  DETAIL. Le TOTAL passe par `predire_portefeuille`, qui ne refuse rien.
  Mesure du 10/09/2026, 40 valeurs absentes sur 3 000 lignes : la couche
  qualite ne voit RIEN (0 exclusion, 0 correction, 0 signalement), `tarifer`
  refuse les 40, et le total en compte 14 099,19 EUR -- 1,28 % du montant
  publie, mediane 303,53 EUR, max 767,40 EUR.
  *Le meme bloc signe pouvait afficher un refus a la ligne 3 et compter ce
  contrat dans son total.*

⚠️⚠️ ON REFUSE, ON NE SUBSTITUE PAS (D1) ; ON NE REFUSE PAS, ON DECLARE (D7).
Les deux gestes different parce que les deux causes different : une entree
deja transformee est une ERREUR D'APPELANT ; une valeur imputee est un FAIT
du fichier client, que refuser deplacerait le comportement de tout dossier
reel.

⚠️ ET LE REFUS NE CASSE PAS LE DOCUMENT. `{'refus_assiette': ...}` est un dict
VRAI sans cle `total` : lire `publie['total']` juste apres `if publie:` ferait
perdre le RAPPORT ENTIER sur un `KeyError`. Les deux formats traitent le refus
AVANT de lire le total.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
==============================================================================
"""
from __future__ import annotations

import ast
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
from core.prix_compares import assiette_du_tarif
from direction_non_vie.tarification import test_plan_invariants as T
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
)
from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
from direction_non_vie.tarification.services.rapport_modeles_tarif import (
    TITRE_TARIF,
    _bloc_tarif_html,
    tarif_publie,
)

_PLANS = os.path.join(_RACINE, 'plans')
_TMP = os.environ.get('TEMP', '/tmp')


#: ⚠️⚠️ FIXTURE DE MODULE, PAS D'HERITAGE ENTRE CLASSES. Une classe qui lit
#: les attributs poses par le `setUpClass` d'une AUTRE classe depend de
#: l'ordre de decouverte -- et `unittest` ne le garantit pas. *Mesure : la
#: seconde classe levait selon l'ordre.* Une fixture memorisee, construite a
#: la demande, ne depend de rien.
_FIXTURE = {}


def _fixture():
    if _FIXTURE:
        return _FIXTURE
    plan = PlanTarifaire.depuis_yaml(os.path.join(_PLANS, 'auto.yaml'))
    base = {'audit_path': _TMP, 'verbose': False}
    df = T.portefeuille_auto(1500, 11).reset_index(drop=True)
    # ⚠️ 25 valeurs absentes sur un FACTEUR : la couche qualite ne les traite
    # pas (mesure), A2 les impute, et `tarifer` les refuse.
    df.loc[0:24, 'bonus_malus'] = np.nan
    r1 = AgentA1Ingestion(**base).run(
        branche='non_vie', sous_branche='auto', dataframe=df, plan=plan)
    a2 = AgentA2Preprocessing(models_path=_TMP, **base).run(
        result_a1=r1, plan=plan)['dataframe']
    tarif = pipeline_complet(r1['dataframe'], plan)
    _FIXTURE.update(plan=plan, a2=a2, tarif=tarif,
                    assiette=assiette_du_tarif(tarif))
    return _FIXTURE


class TestLAssietteDuBlocPrix(unittest.TestCase):
    """⚠️⚠️ D1 -- le prix publie se calcule sur les lignes du tarif."""

    @classmethod
    def setUpClass(cls):
        f = _fixture()
        cls.plan, cls.a2 = f['plan'], f['a2']
        cls.tarif, cls.assiette = f['tarif'], f['assiette']

    def test_BP1_LE_SCEAU_une_entree_DEJA_transformee_est_REFUSEE(self):
        """⚠️⚠️ LE DEFAUT MESURE. La sortie d'A2 porte les colonnes qu'A2 CREE :
        la re-transformer applique A2 deux fois sur le chemin du prix."""
        temoins = [c for c in self.plan.colonnes_derivees()
                   if c in self.a2.columns]
        self.assertTrue(temoins, "l'entree de ce controle ne porte aucun "
                                 "temoin : il s'exercerait sur une assiette "
                                 "ou la violation ne peut pas survenir")
        publie = tarif_publie(self.tarif, self.a2)
        self.assertTrue(publie.get('refus_assiette'),
                        "une sortie d'A2 est acceptee : A2 tourne deux fois")
        self.assertNotIn('total', publie,
                         "un refus ne porte pas de total")
        self.assertTrue(any(c in publie['refus_assiette'] for c in temoins),
                        "le refus ne nomme aucune colonne temoin")
        print(f"    BP-1 SCEAU : {len(temoins)} temoin(s) -> REFUS nomme")

    def test_BP2_LE_MIROIR_l_assiette_du_tarif_PUBLIE_un_prix(self):
        """⚠️ Sans ce sens, un garde qui refuserait TOUT satisferait BP-1 et le
        document n'aurait plus jamais de prix."""
        publie = tarif_publie(self.tarif, self.assiette)
        self.assertNotIn('refus_assiette', publie)
        self.assertGreater(publie['total']['somme_prime_pure'], 0.0)
        self.assertEqual(publie['total']['n_contrats'], len(self.assiette))
        print(f"    BP-2 miroir : total publie "
              f"{publie['total']['somme_prime_pure']:,.2f} EUR"
              .replace(',', ' '))

    def test_BP3_LE_SCEAU_le_refus_NE_CASSE_PAS_le_document(self):
        """⚠️⚠️ LE PIEGE QUE L'AUDITEUR A LUI-MEME RENCONTRE. Un dict VRAI sans
        cle `total` fait lever `publie['total']` juste apres `if publie:` --
        et le RAPPORT ENTIER est perdu. *Un refus qui casse le document est
        pire que le defaut qu'il refuse.*"""
        publie = tarif_publie(self.tarif, self.a2)
        html = _bloc_tarif_html(publie)          # ne doit PAS lever
        self.assertIn(TITRE_TARIF, html)
        self.assertIn('AUCUN PRIX PUBLIE', html)
        self.assertGreater(len(html), 100)
        print(f"    BP-3 SCEAU : le refus est publie ({len(html)} car.), "
              f"aucun KeyError")

    def test_BP4_A6_remet_l_ASSIETTE_DU_TARIF_releve_par_AST(self):
        """⚠️⚠️ LE CORRECTIF DOIT ATTEINDRE LA SURFACE. Le garde du service ne
        sert a rien si A6 continue de remettre la sortie d'A2 : le document
        perdrait simplement son prix."""
        a6 = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
              / 'a6_comparaison' / 'agent.py').read_text(encoding='utf-8')
        arbre = ast.parse(a6)
        assignations = {
            cible.id: ast.unparse(n.value)
            for n in ast.walk(arbre) if isinstance(n, ast.Assign)
            for cible in n.targets if isinstance(cible, ast.Name)}
        vus = []
        for n in ast.walk(arbre):
            if not (isinstance(n, ast.Call)
                    and getattr(n.func, 'id', None)
                    == 'generer_rapport_tarification'):
                continue
            for mot in n.keywords:
                if mot.arg != 'portefeuille':
                    continue
                source = ast.unparse(mot.value)
                for nom, valeur in assignations.items():
                    if nom in source:
                        source += ' || ' + valeur
                vus.append(source)
        self.assertTrue(vus, "A6 ne transmet plus de portefeuille")
        for source in vus:
            self.assertIn('assiette_du_tarif', source,
                          "A6 remet un portefeuille sans le rapporter a "
                          "l'assiette du tarif : A2 tournerait deux fois")
        print("    BP-4 A6 remet l'assiette du tarif")


class TestA6ProduitVraimentSesDocuments(unittest.TestCase):
    """⚠️⚠️ LE CONTROLE QUI MANQUAIT, ET IL A COUTE DEUX DOCUMENTS SIGNES.

    `BP-4` releve PAR AST que A6 remet l'assiette du tarif. Il etait VERT
    pendant que A6 perdait son HTML et son Word : ma ligne ecrivait
    `_assiette_pub or (...)`, et `or` sur un DataFrame leve
    « The truth value of a DataFrame is ambiguous ».

    ⚠️⚠️ *UN RELEVE AST PROUVE QUE LE CABLAGE EXISTE, PAS QU'IL S'EXECUTE.*
    Il faut les deux : l'AST tient l'intention, l'execution tient le fait.
    """

    def test_BP10_LE_SCEAU_A6_produit_SES_DEUX_documents(self):
        """⚠️ On traverse A6 pour de vrai, avec un plan et un `result_a1` --
        le seul chemin ou l'assiette de publication est calculee."""
        from direction_non_vie.tarification.a2_preprocessing.agent import (
            AgentA2Preprocessing as _A2,
        )
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
        from direction_non_vie.tarification.a6_comparaison.agent import (
            AgentA6Comparaison,
        )
        plan = _fixture()['plan']
        base = {'audit_path': _TMP, 'verbose': False}
        df = T.portefeuille_auto(400, 5)
        r1 = AgentA1Ingestion(**base).run(
            branche='non_vie', sous_branche='auto', dataframe=df, plan=plan)
        r2 = _A2(models_path=_TMP, **base).run(result_a1=r1, plan=plan)
        r3 = AgentA3GLM(models_path=_TMP, audit_path=_TMP,
                        verbose=False).run(
            result_a2=r2, plan=plan, col_frequence=plan.cible_frequence,
            col_cout=plan.cible_cout, generer_graphiques=False)
        r6 = AgentA6Comparaison(models_path=_TMP, audit_path=_TMP,
                                verbose=False).run(
            result_a1=r1, result_a2=r2, result_a3=r3, col_cible='nb_sinistres',
            plan=plan, environnement='production', profil_valide_par='Test',
            generer_graphiques=False, generer_rapport_equipe=False)
        self.assertTrue(r6.get('success'), r6.get('erreur'))
        for cle in ('html_bytes', 'word_bytes'):
            self.assertTrue(
                r6.get(cle),
                f"A6 n'a PAS produit `{cle}` : le document signe est perdu")
        print(f"    BP-10 SCEAU : A6 produit ses deux documents "
              f"({len(r6['html_bytes']):,} + {len(r6['word_bytes']):,} octets)"
              .replace(',', ' '))


class TestCeQueLeTotalImpute(unittest.TestCase):
    """⚠️⚠️ D7 -- le total dit combien de contrats il compte sans les tarifer."""

    @classmethod
    def setUpClass(cls):
        f = _fixture()
        cls.plan, cls.tarif, cls.assiette = (f['plan'], f['tarif'],
                                             f['assiette'])
        cls.publie = tarif_publie(cls.tarif, cls.assiette)

    def test_BP5_LE_SCEAU_le_total_DECLARE_les_contrats_imputes(self):
        """⚠️⚠️ LE MEME BLOC AFFICHAIT UN REFUS A LA LIGNE 3 ET COMPTAIT CE
        CONTRAT DANS SON TOTAL."""
        total = self.publie['total']
        self.assertEqual(total['n_contrats_imputes'], 25,
                         "les contrats imputes ne sont pas comptes")
        self.assertTrue(total['phrase_imputes'])
        self.assertIn('ABSENT ou ILLISIBLE', total['phrase_imputes'])
        self.assertIn('REFUSE', total['phrase_imputes'].upper())
        print(f"    BP-5 SCEAU : {total['n_contrats_imputes']} contrat(s) "
              f"imputes, declares")

    def test_BP6_LE_MIROIR_un_portefeuille_SAIN_ne_dit_rien(self):
        """⚠️⚠️ LA PHRASE SE TAIT QUAND IL N'Y A RIEN A DIRE. Une phrase
        permanente ne signalerait plus rien le jour ou elle compterait."""
        sain = T.portefeuille_auto(600, 3)
        tarif = pipeline_complet(sain, self.plan)
        publie = tarif_publie(tarif, assiette_du_tarif(tarif))
        self.assertEqual(publie['total']['n_contrats_imputes'], 0)
        self.assertIsNone(publie['total']['phrase_imputes'])
        self.assertEqual(publie['total']['rangs_imputes'], [])
        print("    BP-6 miroir : portefeuille sain -> aucune phrase")

    def test_BP7_RGPD_le_RANG_jamais_l_identifiant(self):
        """⚠️⚠️ CE RAPPORT SORT DU PERIMETRE DE TRAITEMENT. Un identifiant de
        contrat y serait une donnee personnelle diffusee."""
        total = self.publie['total']
        self.assertTrue(all(isinstance(r, int) for r in total['rangs_imputes']))
        self.assertLessEqual(len(total['rangs_imputes']), 20,
                             "la liste des rangs n'est pas bornee")
        interdits = [getattr(self.plan, 'identifiant_contrat', None),
                     getattr(self.plan, 'echeance', None)]
        for nom in [x for x in interdits if x]:
            self.assertNotIn(str(nom), total['phrase_imputes'] or '')
        print(f"    BP-7 RGPD : {len(total['rangs_imputes'])} rang(s), "
              f"0 identifiant")

    def test_BP8_le_compte_reutilise_le_PREDICAT_de_tarifer(self):
        """⚠️⚠️ JAMAIS UNE SECONDE DEFINITION -- deux codes qui disent la meme
        regle finissent par diverger. Releve PAR AST : le service appelle
        `anomalies_du_contrat`, il ne reimplemente pas le test."""
        chemin = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
                  / 'services' / 'rapport_modeles_tarif.py')
        texte = chemin.read_text(encoding='utf-8')
        arbre = ast.parse(texte)
        appels = [n for n in ast.walk(arbre) if isinstance(n, ast.Call)
                  and getattr(n.func, 'attr', None) == 'anomalies_du_contrat']
        self.assertTrue(appels,
                        "le service ne consulte plus le predicat de "
                        "`tarifer()` : il en a fabrique un second")
        # ⚠️ et le compte porte sur TOUT le portefeuille, pas sur les 10
        # lignes du detail -- sinon il attesterait sur une assiette etroite.
        self.assertEqual(self.publie['total']['n_contrats'],
                         len(self.assiette))
        print(f"    BP-8 le predicat de `tarifer` est reutilise "
              f"({len(appels)} appel(s))")

    def test_BP9_LES_DEUX_FORMATS_publient_la_phrase_par_AST(self):
        """⚠️⚠️ LA SEPTIEME ASYMETRIE QUE CE DEPOT AURAIT PAYEE."""
        chemin = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
                  / 'services' / 'rapport_modeles_tarif.py')
        texte = chemin.read_text(encoding='utf-8')
        arbre = ast.parse(texte)
        html = mots = False
        for f in ast.walk(arbre):
            if not isinstance(f, ast.FunctionDef):
                continue
            src = ast.get_source_segment(texte, f) or ''
            if f.name == '_bloc_tarif_html':
                html = 'phrase_imputes' in src
            if f.name == 'export_word':
                mots = 'phrase_imputes' in src
        self.assertTrue(html, "le HTML ne publie pas la phrase")
        self.assertTrue(mots, "le Word ne publie pas la phrase")
        # et le refus d'assiette aussi, dans les deux
        self.assertIn('refus_assiette', texte)
        print("    BP-9 les deux formats publient la phrase et le refus")


if __name__ == '__main__':
    unittest.main(verbosity=2)
