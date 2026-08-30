"""Controles positifs — `a4/C11`, RANG 1 : une reference fabriquee qui decidait
d'un statut RAG.

CE QUE CE FICHIER PROUVE, ET POURQUOI C'EST UN RANG 1
─────────────────────────────────────────────────────

Le statut RAG du monitoring autorise ou plafonne la mise en production d'un
modele. Il etait calcule contre une reference que **personne n'avait mesuree**.

═══ LE DEFAUT, MESURE LE 30/08/2026 ═══

⚠️⚠️ TROIS NOMBRES INVENTES COEXISTAIENT DANS LA MEME CHAINE, A TROIS VALEURS
DIFFERENTES :

```
  a4_ml/agent.py:737   gini_reference_a3 = 0.25      (affectation appelant)
  a4_ml/agent.py:740   .get('gini', 0.25)            (repli)
  a4_ml/agent.py:2453  gini_reference = 0.2651       (defaut de signature)
  a4_ml/agent.py:2945  .get('gini_reference', 0.265) (repli de la FIGURE)
```

Le `0.2651` est le hardcodage freMTPL2 que le commentaire de l'appelant dit
**precisement vouloir eviter** : *le correctif avait atterri sur l'appelant,
jamais sur l'appele.*

⚠️⚠️ ET LE LIBELLE PUBLIE ETAIT « Reference A3 » -- une provenance que le code
ne portait pas. Mesure par execution, avec A3 absent :

```
  Gini reel 0.24 -> variation -0.01  statut_gini VERT   global AMBRE
  Gini reel 0.28 -> variation +0.03  statut_gini AMBRE  global AMBRE
  Gini reel 0.34 -> variation +0.09  statut_gini ROUGE  global ROUGE
```

⚠️⚠️ LE TEST PORTAIT SUR `abs(variation)` : **un modele qui discrimine MIEUX
que la reference fantome sortait ROUGE exactement comme un modele degrade.**
*Un bon modele pouvait etre refuse par un nombre que personne n'avait mesure.*

═══ CE QUE LE CORRECTIF FAIT — DEUX ARBITRAGES DE SELASSE, 30/08/2026 ═══

① **Reference absente -> `None` + AMBRE**, sur le modele DEJA valide pour l'A/E
non calculable d'A6. C'est la regle que la docstring de `_monitoring_derive`
enonce depuis toujours -- « une grandeur non mesuree vaut None et son statut
est AMBRE » -- et le Gini etait le seul des trois indicateurs a ne pas
l'appliquer.

② **Le test devient ASYMETRIQUE** : une degradation reste surveillee
normalement, une amelioration se SIGNALE sans jamais plafonner le statut.

⚠️ L'ASYMETRIE ENTRE VOISINS A DESIGNE LE CHAMP MANQUANT : le PSI publiait
`interpretation_psi` -- « Stabilite NON mesuree » en toutes lettres -- et le
Gini, indicateur voisin dans le MEME dictionnaire, n'avait aucune prose. Il ne
pouvait donc rien dire quand il ne pouvait rien mesurer.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

from direction_non_vie.tarification.a4_ml.agent import (
    MSG_REFERENCE_A3_INDISPONIBLE,
    AgentA4ML,
)

_A4 = (pathlib.Path(__file__).resolve().parent / 'a4_ml' / 'agent.py')


def _monitoring(**kw):
    """`_monitoring_derive` sans passer par `__init__` : on teste la regle de
    decision, pas la construction de l'agent."""
    return AgentA4ML.__new__(AgentA4ML)._monitoring_derive({}, **kw)


class TestAucuneReferenceFabriquee(unittest.TestCase):
    """`a4/C11` — LE CONTROLE QUI FERME : plus un seul nombre invente."""

    def test_LE_TEST_QUI_FERME_A3_absent_ne_fabrique_AUCUNE_reference(self):
        """⚠️⚠️ C'est le coeur du rang 1 : la reference etait `0.25`, publiee
        comme « Reference A3 », et elle decidait du statut."""
        m = _monitoring(gini_reference=None, gini_actuel=0.34)
        self.assertIsNone(m['gini_reference'],
                          "une reference est fabriquee alors qu'A3 n'a rien "
                          "fourni")
        self.assertIsNone(m['variation_gini'])
        self.assertIsNone(m['variation_gini_pct'])
        self.assertEqual(m['statut_gini'], 'AMBRE',
                         "une grandeur non mesuree doit valoir AMBRE, comme le "
                         "PSI et comme l'A/E non calculable d'A6")
        print(f"    C11-1 A3 absent : reference={m['gini_reference']}, "
              f"variation={m['variation_gini']}, statut={m['statut_gini']}")

    def test_la_courbe_ne_trace_AUCUN_point_fantome(self):
        """⚠️ Elle tracait DEUX points dont un inventé, sous le libelle
        « Reference A3 ». Une courbe ne montre que ce qui est mesure."""
        m = _monitoring(gini_reference=None, gini_actuel=0.34)
        self.assertEqual(m['mois_historique'], ['Modèle retenu (test)'])
        self.assertEqual(m['gini_historique'], [0.34])
        self.assertNotIn('Référence A3', m['mois_historique'],
                         "le libelle « Reference A3 » est publie alors qu'A3 "
                         "n'a fourni aucune reference")
        print(f"    C11-2 courbe = {m['mois_historique']} / "
              f"{m['gini_historique']} — un seul point, mesure")

    def test_SECOND_SENS_une_reference_REELLE_est_bien_utilisee(self):
        """⚠️⚠️ SANS CE SENS, LE CORRECTIF POURRAIT AVOIR TUE LA COMPARAISON.
        Quand A3 a mesure un Gini, il doit servir -- et les deux points doivent
        etre traces."""
        m = _monitoring(gini_reference=0.25, gini_actuel=0.19)
        self.assertEqual(m['gini_reference'], 0.25)
        self.assertAlmostEqual(m['variation_gini'], -0.06, places=4)
        self.assertEqual(m['mois_historique'],
                         ['Référence A3', 'Modèle retenu (test)'])
        self.assertEqual(m['statut_gini'], 'ROUGE')
        print(f"    C11-3 second sens : reference reelle 0.25 utilisee, "
              f"variation {m['variation_gini']}, statut {m['statut_gini']}")

    def test_plus_aucun_defaut_chiffre_dans_la_chaine(self):
        """⚠️ Mesure par AST sur le module : ni defaut de signature, ni repli
        numerique, ni AFFECTATION DIRECTE d'un nombre a la reference.

        ⚠️⚠️ ET CE CONTROLE A ETE ELARGI PAR SA PROPRE VIOLATION PLANTEE. Ecrit
        d'abord, il ne regardait que la signature et les replis `.get` ; le
        plant `gini_reference_a3 = 0.25` chez l'appelant -- **la forme meme du
        defaut d'origine, l.737** -- ne l'a PAS fait tomber. *Le motif de ce
        chantier applique au filet : la question « sur quelle assiette ? » vaut
        aussi pour mes propres controles.* Les trois formes sont couvertes.
        """
        arbre = ast.parse(_A4.read_text(encoding='utf-8'))
        fautifs = []
        for n in ast.walk(arbre):
            # ⚠️ FORME 3 : l'affectation directe, celle qui a echappe au filet.
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) \
                    and isinstance(n.value.value, (int, float)) and n.value.value:
                for cible in n.targets:
                    if isinstance(cible, ast.Name) and 'gini_reference' in cible.id:
                        fautifs.append(
                            f'affectation l.{n.lineno} : {cible.id} = '
                            f'{n.value.value}')
            if isinstance(n, ast.FunctionDef) and n.name == '_monitoring_derive':
                portants = n.args.args[-len(n.args.defaults):]
                for arg, defaut in zip(portants, n.args.defaults):
                    if (arg.arg == 'gini_reference'
                            and isinstance(defaut, ast.Constant)
                            and isinstance(defaut.value, (int, float))):
                        fautifs.append(f'signature l.{n.lineno} = {defaut.value}')
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'get' and len(n.args) == 2
                    and isinstance(n.args[0], ast.Constant)
                    and str(n.args[0].value) in ('gini', 'gini_reference')
                    and isinstance(n.args[1], ast.Constant)
                    and isinstance(n.args[1].value, (int, float))
                    and n.args[1].value):
                fautifs.append(f'repli l.{n.lineno} = {n.args[1].value}')
        self.assertEqual(
            fautifs, [],
            f"un nombre invente est revenu servir de reference : {fautifs}. "
            f"Il deciderait de nouveau d'un statut qui autorise ou plafonne "
            f"une mise en production.")
        print("    C11-4 0 defaut chiffre — les 0.25 / 0.265 / 0.2651 ont "
              "disparu de la chaine")


class TestLeMessageQueLitLActuaire(unittest.TestCase):
    """⚠️⚠️ EXIGENCE EXPLICITE DE SELASSE : clair et parlant, pas du jargon.

    Le message doit dire TROIS choses, et une seule manquante le rend
    trompeur. Chacune est verifiee separement : *un controle qui n'exigerait
    que la presence du message ne dirait rien de ce qu'il contient.*
    """

    def test_il_dit_que_le_modele_A_BIEN_ETE_juge_sur_le_reste(self):
        self.assertIn('bien été évalué sur tous ses autres critères',
                      MSG_REFERENCE_A3_INDISPONIBLE)
        print("    C11-5 ① le message dit que le modele a bien ete juge sur "
              "ses autres criteres")

    def test_il_dit_CE_QUI_manque_et_POURQUOI(self):
        self.assertIn('A3', MSG_REFERENCE_A3_INDISPONIBLE)
        self.assertIn("n'a pas tourné pour cette exécution",
                      MSG_REFERENCE_A3_INDISPONIBLE)
        self.assertIn('seule cette comparaison manque',
                      MSG_REFERENCE_A3_INDISPONIBLE)
        print("    C11-6 ② il nomme A3, dit qu'il n'a pas tourne, et borne ce "
              "qui manque a la seule comparaison")

    def test_il_dit_que_ce_N_EST_PAS_un_defaut_du_modele(self):
        self.assertIn("Ce n'est pas un défaut du modèle évalué",
                      MSG_REFERENCE_A3_INDISPONIBLE)
        print("    C11-7 ③ il dit que ce n'est pas un defaut du modele evalue")

    def test_il_dit_QUOI_FAIRE(self):
        """⚠️ La regle de ce depot : un message qui signale dit aussi quoi
        faire. Sans elle, l'actuaire lit un constat sans issue."""
        self.assertIn('relancer A3 avant A4', MSG_REFERENCE_A3_INDISPONIBLE)
        print("    C11-8 le message porte son remede")

    def test_il_N_EST_PAS_du_jargon(self):
        """⚠️⚠️ « Clair et parlant » se mesure, sinon ce n'est qu'un avis. Le
        message ne doit contenir AUCUN nom de variable ni de fonction : ce sont
        eux qui rendent un message illisible pour qui ne lit pas le code."""
        for jargon in ('gini_reference', '_monitoring_derive', 'None',
                       'AMBRE', 'statut_gini', 'variation_gini', 'a4/C11'):
            with self.subTest(jargon=jargon):
                self.assertNotIn(jargon, MSG_REFERENCE_A3_INDISPONIBLE,
                                 f"le message publie « {jargon} », un terme de "
                                 f"code que l'actuaire n'a pas a connaitre")
        self.assertGreater(len(MSG_REFERENCE_A3_INDISPONIBLE), 200,
                           "un message d'une ligne ne peut pas porter les "
                           "trois points exiges")
        print(f"    C11-9 aucun nom de variable, "
              f"{len(MSG_REFERENCE_A3_INDISPONIBLE)} caracteres de francais")

    def test_il_ATTEINT_le_resultat_publie(self):
        """⚠️⚠️ LA METHODE QUI A DEMASQUE `services/C10` PUIS `services/C12` :
        on lit ce qui sort, pas la constante."""
        m = _monitoring(gini_reference=None, gini_actuel=0.34)
        self.assertEqual(m['interpretation_gini'], MSG_REFERENCE_A3_INDISPONIBLE,
                         "le monitoire reecrit le message au lieu de le lire, "
                         "ou ne le publie pas du tout")
        print("    C11-10 le message atteint `interpretation_gini`, caractere "
              "pour caractere")


class TestL_AsymetrieDuTest(unittest.TestCase):
    """⚠️⚠️ ARBITRAGE : une amelioration n'est pas une derive."""

    def test_LE_TEST_QUI_FERME_un_modele_MEILLEUR_ne_plafonne_plus(self):
        """⚠️ Mesure d'avant le lot : Gini 0.34 contre une reference 0.25
        rendait `statut_global = ROUGE`. Le modele etait REFUSE pour avoir ete
        trop bon."""
        m = _monitoring(gini_reference=0.25, gini_actuel=0.34)
        self.assertAlmostEqual(m['variation_gini'], 0.09, places=4)
        self.assertEqual(m['statut_gini'], 'VERT',
                         f"un modele qui discrimine MIEUX que la reference "
                         f"(+{m['variation_gini']}) est plafonne a "
                         f"{m['statut_gini']}")
        self.assertNotEqual(m['statut_global'], 'ROUGE')
        print(f"    C11-11 Gini +0.09 : statut_gini {m['statut_gini']} "
              f"(ROUGE avant ce lot)")

    def test_l_amelioration_est_SIGNALEE_pas_seulement_toleree(self):
        """⚠️ « Sans jamais plafonner » ne veut pas dire « en silence ». Une
        hausse surprenante doit rester visible."""
        m = _monitoring(gini_reference=0.25, gini_actuel=0.34)
        self.assertIn('SUPÉRIEUR', m['interpretation_gini'])
        self.assertIn('+0.0900', m['interpretation_gini'])
        print(f"    C11-12 l'amelioration est dite : "
              f"« {m['interpretation_gini'][:58]}... »")

    def test_SECOND_SENS_une_DEGRADATION_reste_surveillee(self):
        """⚠️⚠️ SANS CE SENS, L'ASYMETRIE AURAIT DESARME LE GARDE-FOU."""
        m = _monitoring(gini_reference=0.25, gini_actuel=0.19)
        self.assertEqual(m['statut_gini'], 'ROUGE',
                         "une degradation de 0.06 au-dela du seuil 0.05 ne "
                         "declenche plus rien : l'asymetrie a ouvert un trou")
        self.assertEqual(m['statut_global'], 'ROUGE')
        print(f"    C11-13 second sens : degradation -0.06 -> "
              f"{m['statut_gini']}, global {m['statut_global']}")

    def test_les_TROIS_bandes_restent_atteignables(self):
        """⚠️⚠️ UNE BANDE QU'AUCUNE ENTREE N'ATTEINT EST DU DECOR. On balaie la
        degradation et on exige que les trois statuts sortent."""
        vus = {}
        for pas in range(0, 80, 5):
            g = round(0.25 - pas / 1000, 4)
            vus.setdefault(_monitoring(gini_reference=0.25,
                                       gini_actuel=g)['statut_gini'],
                           []).append(pas / 1000)
        self.assertEqual(sorted(vus), ['AMBRE', 'ROUGE', 'VERT'],
                         f"une bande n'est jamais atteinte : {sorted(vus)}")
        print(f"    C11-14 3 bandes atteintes — VERT jusqu'a "
              f"{max(vus['VERT']):.3f}, AMBRE jusqu'a {max(vus['AMBRE']):.3f}, "
              f"ROUGE au-dela")


if __name__ == '__main__':
    unittest.main()
