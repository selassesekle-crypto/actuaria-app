"""CONTRÔLES POSITIFS DU LOT ③ — les valeurs LIMITES et les valeurs ABSENTES.

Quatre constats, un même sujet : *ce qui tombe exactement sur la borne, ou qui
n'est pas là du tout.*

  `qualite/C1` — une valeur MANQUANTE ou ILLISIBLE n'était vue par AUCUNE des
                 quatre règles : tout passe par `to_numeric(errors='coerce')`
                 et **toute comparaison est fausse sur un NaN**. Une colonne
                 d'exposition entièrement vide traversait avec zéro anomalie.
  `qualite/C2` — l'escalade comptait PAR TYPE, jamais l'union : quatre types à
                 **4,9 %** chacun = **19,6 % du portefeuille exclu**, escalade
                 `False`.
  `a1/C3`      — `prime_pure > 0` déclaré dans la docstring, `< 0` testé dans
                 le code : une prime pure NULLE passait sans un mot.
  `a1/C4`      — `between(0, 1)` est inclusif : `exposition = 0` donnait
                 `expo_ok_pct = 100,0` **pendant que** le contrôle 4d la
                 signalait aberrante. Deux verdicts contradictoires dans la
                 même fonction.

⚠️⚠️ CHAQUE CONTRÔLE PORTE SES DEUX SENS. Ici le risque est symétrique : un
détecteur de valeurs manquantes trop large bloquerait des portefeuilles sains,
et une escalade sur l'union rendrait la couche hystérique. Les témoins sains
sont donc testés autant que les cas fautifs.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import numpy as np
import pandas as pd

from core.plan_tarifaire import Facteur, PlanTarifaire
from core.qualite_donnees import controler_qualite, detecter_illisible

_PLAN = PlanTarifaire(
    lob='ctrl', exposition='expo', cible_frequence='nb', cible_cout='cout',
    facteurs=(Facteur('age', 'continu'),), identifiant_contrat='id')


def _sain(n=1000):
    """⚠️ Un portefeuille RÉELLEMENT sain : `cout = 0` quand `nb = 0`, sinon
    l'incohérence « coût sans sinistre » domine tout et masque la mesure.
    Ma première version du banc portait ce défaut."""
    rng = np.random.default_rng(0)
    nb = rng.poisson(0.2, n).astype(float)
    cout = np.where(nb > 0, rng.gamma(2, 300, n), 0.0)
    return pd.DataFrame({'id': np.arange(n), 'age': rng.uniform(20, 70, n),
                         'expo': np.ones(n), 'nb': nb, 'cout': cout})


class POS_Qualite_C1_UneValeurAbsenteEstVUE(unittest.TestCase):
    """⚠️ `qualite/C1` — le trou était invisible à la couche qualité."""

    def _codes_illisibles(self, df):
        r = controler_qualite(df, _PLAN, horodatage='t')
        tous = r.exclusions + r.corrections + r.signalements
        return [a.code for a in tous if 'illisible' in a.code]

    def test_les_quatre_formes_d_absence_sont_signalees(self):
        n = 1000
        cas = {
            "50 % d'expositions NaN":
                _sain(n).assign(expo=[np.nan if i % 2 else 1.0 for i in range(n)]),
            "100 % d'expositions NaN": _sain(n).assign(expo=np.nan),
            "50 % de frequences NaN":
                _sain(n).assign(nb=[np.nan if i % 2 else 0.0 for i in range(n)]),
            "50 % d'expositions en TEXTE":
                _sain(n).assign(expo=['douze mois' if i % 2 else 1.0
                                      for i in range(n)]),
        }
        for libelle, df in cas.items():
            with self.subTest(cas=libelle):
                codes = self._codes_illisibles(df)
                self.assertTrue(
                    codes,
                    f"[{libelle}] la couche qualite ne voit RIEN — elle declare "
                    f"bonnes des donnees absentes")
        print(f"    POS-C1q les {len(cas)} formes d'absence sont signalees ✅")

    def test_LE_SECOND_SENS_un_portefeuille_COMPLET_ne_declenche_RIEN(self):
        """⚠️⚠️ Un détecteur d'absence trop large signalerait tout le monde et
        rendrait le signal inutile."""
        self.assertEqual(self._codes_illisibles(_sain()), [],
                         "un portefeuille complet est signale comme illisible")
        print("    POS-C1q LE SECOND SENS : un portefeuille complet, rien ✅")

    def test_l_absence_est_SIGNALEE_jamais_exclue(self):
        """⚠️ Doctrine du module : ambigu → signaler et LAISSER. Une valeur
        manquante peut être un vrai zéro, une erreur de saisie ou une grandeur
        inconnue — rien dans la donnée ne le dit. Exclure trancherait à la
        place de l'actuaire, et déplacerait des lignes."""
        df = _sain(1000).assign(nb=[np.nan if i % 2 else 0.0 for i in range(1000)])
        r = controler_qualite(df, _PLAN, horodatage='t',
                              qualite_validee_par='ctrl')
        illisibles = [a for a in r.exclusions + r.corrections + r.signalements
                      if 'illisible' in a.code]
        self.assertTrue(illisibles)
        for a in illisibles:
            self.assertEqual(a.regle, 3,
                             f"{a.code} est en regle {a.regle} : une absence "
                             f"EXCLUT ou CORRIGE, au lieu de signaler")
        print("    POS-C1q l'absence est SIGNALEE (regle 3), jamais exclue ✅")

    def test_le_detecteur_voit_le_TEXTE_que_to_numeric_a_detruit(self):
        """La mesure directe : c'est `to_numeric(coerce)` qui créait le trou."""
        df = pd.DataFrame({'x': [1.0, np.nan, 'douze mois', '', 3.0]})
        vu = detecter_illisible(df, 'x')
        self.assertEqual(list(np.asarray(vu, dtype=bool)),
                         [False, True, True, True, False])
        print("    POS-C1q le detecteur voit NaN, texte et chaine vide ✅")


class POS_Qualite_C2_L_EscaladeVoitL_UNION(unittest.TestCase):
    """⚠️ `qualite/C2` — quatre types à 4,9 %, 19,6 % du portefeuille exclu,
    et rien n'était escaladé."""

    def _quatre_types(self):
        d = _sain(1000)
        d.loc[d.index[0:49], 'nb'] = -1.0
        d.loc[d.index[49:98], 'cout'] = -1.0
        d.loc[d.index[98:147], 'expo'] = 0.0
        d.loc[d.index[147:196], 'id'] = 0
        return d

    def test_quatre_types_sous_le_seuil_escaladent_par_leur_UNION(self):
        r = controler_qualite(self._quatre_types(), _PLAN, horodatage='t')
        self.assertTrue(
            r.escalade_declenchee,
            "196 lignes sur 1000 (19,6 %) sont exclues et rien n'escalade")
        self.assertTrue(r.bloque, "l'escalade ne bloque pas la tarification")
        motifs = " ".join(r.anomalies_au_dela_seuil)
        self.assertIn('union', motifs,
                      f"le motif ne nomme pas la vraie raison : {motifs}")
        # ⚠️⚠️ LE CHIFFRE SE DÉRIVE, IL NE SE RETAPE PLUS. Il valait `19.6%`
        # en dur ; l'arbitrage du 02/09 a restreint l'union aux quatre types
        # DISQUALIFIANTS, et deux des quatre plantés ici n'en sont pas — la
        # part tombe mécaniquement. *Ce que ce contrôle prouve est inchangé :
        # aucun type seul n'atteint le seuil, et leur union escalade quand
        # même. Le nombre en dur ne prouvait que lui-même.*
        from core.qualite_donnees import CODES_DISQUALIFIANTS
        _touchees = set()
        for a in ((r.exclusions or []) + (r.corrections or [])
                  + (r.signalements or [])):
            self.assertLess(a.proportion, 0.05,
                            f"{a.code} atteint le seuil SEUL : ce test ne "
                            f"mesure plus l'union")
            if a.code in CODES_DISQUALIFIANTS:
                _touchees.update(a.index)
        _part = len(_touchees) / 1000
        self.assertIn(f'{_part:.1%}', motifs,
                      f"le motif ne chiffre pas l'union ({_part:.1%})")
        print(f"    POS-C2q quatre types a 4,9 %, union des DISQUALIFIANTS "
              f"{_part:.1%} -> escalade ✅")

    def test_LE_SENS_CONSERVE_un_seul_type_au_dessus_du_seuil_escalade_encore(self):
        """⚠️ Le nouveau critère AJOUTE, il ne remplace pas. Un type unique à
        6 % doit continuer d'escalader **sous son propre nom**, sinon le motif
        publié désignerait la mauvaise cause."""
        d = _sain(1000)
        d.loc[d.index[0:60], 'nb'] = -1.0
        r = controler_qualite(d, _PLAN, horodatage='t')
        self.assertTrue(r.escalade_declenchee)
        self.assertIn('frequence_negative', r.anomalies_au_dela_seuil,
                      "le motif ne nomme plus le type fautif")
        self.assertNotIn('union', " ".join(r.anomalies_au_dela_seuil),
                         "l'union masque le motif par type")
        print("    POS-C2q un type seul a 6 % escalade sous son propre nom ✅")

    def test_LE_SECOND_SENS_un_portefeuille_SAIN_n_escalade_PAS(self):
        """⚠️⚠️ Sans lui, une escalade câblée à `True` passerait les deux tests
        ci-dessus et bloquerait toute tarification."""
        r = controler_qualite(_sain(), _PLAN, horodatage='t')
        self.assertFalse(r.escalade_declenchee,
                         f"un portefeuille sain escalade : "
                         f"{r.anomalies_au_dela_seuil}")
        self.assertFalse(r.bloque)
        print("    POS-C2q LE SECOND SENS : un portefeuille sain n'escalade pas ✅")

    def test_LE_SECOND_SENS_un_type_isole_sous_le_seuil_n_escalade_PAS(self):
        d = _sain(1000)
        d.loc[d.index[0:20], 'nb'] = -1.0
        r = controler_qualite(d, _PLAN, horodatage='t')
        self.assertFalse(r.escalade_declenchee,
                         "2 % d'anomalies declenchent l'escalade")
        print("    POS-C2q LE SECOND SENS : 2 % n'escalade pas ✅")


class POS_A1_C3_C4_LesBornesDisentCeQueLaDocstringDeclare(unittest.TestCase):
    """⚠️ `a1/C3` et `a1/C4` — le code contredisait sa propre docstring."""

    @staticmethod
    def _diagnostic(df):
        from direction_non_vie.tarification.a1_ingestion.agent import (
            AgentA1Ingestion,
        )
        agent = AgentA1Ingestion(audit_path='/tmp', verbose=False)
        return agent._valider_qualite(df)

    def test_C4_une_exposition_NULLE_n_est_plus_comptee_saine(self):
        """⚠️ `between(0, 1)` incluait 0 : le score disait 100 % sain pendant
        que l'alerte 4d signalait la même colonne comme aberrante."""
        n = 100
        df = pd.DataFrame({'exposition': np.r_[np.zeros(20), np.ones(n - 20)],
                           'nb_sinistres': np.zeros(n),
                           'cout_total_sinistres': np.zeros(n)})
        d = self._diagnostic(df)
        self.assertLess(d['expo_ok_pct'], 100.0,
                        "expo_ok_pct = 100 % alors que 20 % des expositions "
                        "sont nulles — le score contredit l'alerte 4d")
        self.assertIn('exposition_nulle_ou_negative', d['aberrants'],
                      "l'alerte 4d ne signale plus l'exposition nulle")
        self.assertAlmostEqual(d['expo_ok_pct'], 80.0, places=1)
        print("    POS-C4a exposition nulle : score et alerte CONCORDENT ✅")

    def test_LE_SECOND_SENS_une_exposition_VALIDE_reste_a_100(self):
        """⚠️ La borne haute (1 inclus) ne doit PAS bouger : une exposition de
        1,0 est une année pleine, parfaitement licite."""
        n = 100
        df = pd.DataFrame({'exposition': np.r_[np.ones(50), np.full(50, 0.5)],
                           'nb_sinistres': np.zeros(n),
                           'cout_total_sinistres': np.zeros(n)})
        d = self._diagnostic(df)
        self.assertAlmostEqual(d['expo_ok_pct'], 100.0, places=1,
                               msg="une exposition de 1,0 est jugee hors bornes")
        self.assertNotIn('exposition_nulle_ou_negative', d['aberrants'])
        print("    POS-C4a LE SECOND SENS : expo = 1,0 reste saine ✅")

    def test_C3_une_prime_pure_NULLE_est_signalee(self):
        n = 100
        df = pd.DataFrame({'prime_pure': np.zeros(n),
                           'nb_sinistres': np.zeros(n),
                           'cout_total_sinistres': np.zeros(n)})
        d = self._diagnostic(df)
        self.assertIn('prime_pure_non_positive', d['aberrants'],
                      "prime_pure = 0 traverse le controle, alors que la "
                      "docstring declare « prime_pure > 0 »")
        self.assertEqual(d['aberrants']['prime_pure_non_positive'], n)
        print("    POS-C3a prime_pure nulle : signalee ✅")

    def test_LE_SECOND_SENS_un_cout_de_sinistres_NUL_reste_normal(self):
        """⚠️⚠️ LE PIÈGE DE CE CORRECTIF : `cout_total_sinistres = 0` est le cas
        NORMAL d'un contrat sans sinistre. Appliquer « > 0 » à cette colonne
        signalerait la majorité d'un portefeuille sain."""
        n = 100
        df = pd.DataFrame({'cout_total_sinistres': np.zeros(n),
                           'prime_pure': np.full(n, 250.0),
                           'nb_sinistres': np.zeros(n)})
        d = self._diagnostic(df)
        self.assertNotIn('cout_total_sinistres_negatifs', d['aberrants'])
        self.assertNotIn('prime_pure_non_positive', d['aberrants'])
        print("    POS-C3a LE SECOND SENS : cout de sinistres nul = normal ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
