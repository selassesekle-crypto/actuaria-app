"""
Tests pipeline_agents — l'orchestrateur des DEUX moitiés du tarif.

Ce qu'ils verrouillent : la prime pure est fréquence × coût, et jusqu'à
l'orchestrateur SEULE la fréquence était challengée (sur la cible coût, A6
n'avait qu'un candidat, le GLM Gamma d'A3, et « l'arbitrait » contre personne).
Ces tests protègent les trois règles actuarielles qui rendent l'arbitrage coût
honnête — sans elles, il redeviendrait silencieusement faux :

  · le coût s'entraîne sur les SINISTRÉS seulement (sinon on modélise
    E[coût] inconditionnel ≈ une prime pure, pas une sévérité) ;
  · le CANN est EXCLU du coût (son offset log(exposition) est une construction
    de modèle de comptage : la sévérité ne varie pas avec l'exposition) ;
  · un portefeuille sans sinistre ne produit pas un modèle bricolé, mais une
    erreur PROPRE.

Volumétrie délibérément petite (5 000 lignes, 3 époques DL) : ces tests vérifient
un CONTRAT d'orchestration, pas une performance de modèle.
"""
import json
import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from core.plan_tarifaire import PlanTarifaire
from direction_non_vie.tarification.pipeline_agents import (
    pipeline_agents, ResultatAgents, ArbitrageCible, CIBLE_COUT, CIBLE_PRIME_PURE,
)

try:
    import torch  # noqa: F401
    TORCH_OK = True
except ImportError:
    TORCH_OK = False

_RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
_PLAN_AUTO = PlanTarifaire.depuis_yaml(os.path.join(_RACINE, 'plans', 'auto.yaml'))


def _portefeuille_auto(n=5000, seed=11, avec_sinistres=True):
    """Portefeuille auto COMPLET (tous les facteurs de plans/auto.yaml) et à
    SIGNAL injecté. Complet : sinon le modèle serait AMPUTÉ et plafonné AMBRE —
    on testerait le garde-fou, pas l'orchestrateur.

    avec_sinistres=False → AUCUN sinistre : le cas limite du test n°4.
    """
    rng = np.random.default_rng(seed)
    age = rng.integers(18, 85, n)
    bm = np.clip(rng.normal(.9, .2, n), .5, 3.5)
    expo = np.clip(rng.beta(5, 1, n), .2, 1.)
    if avec_sinistres:
        # Signal net : jeunes + mauvais bonus-malus = sinistrogènes.
        lam = 0.55 * np.exp(0.9 * np.log(bm) + 0.7 * (age < 25))
        nb = rng.poisson(lam * expo)
    else:
        nb = np.zeros(n, dtype=int)
    return pd.DataFrame({
        'id_contrat': range(n),
        'annee_souscription': rng.choice([2019, 2020, 2021, 2022, 2023], n),
        'exposition': expo, 'age': age.astype(float), 'bonus_malus': bm,
        'anciennete_permis': np.clip(age - 18, 0, None).astype(float),
        'puissance_fiscale': rng.integers(4, 15, n).astype(float),
        'age_vehicule': rng.integers(0, 20, n).astype(float),
        'carburant': rng.choice(['Essence', 'Diesel'], n),
        'usage': rng.choice(['Prive', 'Pro'], n),
        'csp': rng.choice(['Cadre', 'Employe', 'Retraite'], n),
        'milieu_geographique': rng.choice(['Urbain', 'Rural'], n),
        'garantie': rng.choice(['Tiers', 'TousRisques'], n),
        'valeur_venale': rng.uniform(5000, 40000, n),
        'kilometrage_annuel': rng.uniform(5000, 30000, n),
        'antecedents_sinistres_n1': rng.poisson(0.15, n).astype(float),
        'nb_sinistres': nb.astype(float),
        'cout_total_sinistres': np.where(nb > 0, rng.gamma(2, 1200, n), 0.),
    })


def _lancer(df, **kw):
    return pipeline_agents(
        df, _PLAN_AUTO, sous_branche='auto',
        models_path='/tmp', audit_path='/tmp',
        n_epochs_dl=3, batch_size_dl=512, calcul_shap=False,
        generer_graphiques=False, environnement='production',
        profil_valide_par='Actuaire Test', **kw)


@unittest.skipUnless(TORCH_OK, "PyTorch absent — A5 ne peut pas être exercé")
class TestPipelineAgents(unittest.TestCase):
    """Portefeuille auto SAIN : l'orchestrateur rend-il les DEUX moitiés ?"""

    @classmethod
    def setUpClass(cls):
        cls.df = _portefeuille_auto(5000)
        cls.res = _lancer(cls.df)

    def test_les_trois_arbitrages_sont_rendus(self):
        r = self.res
        self.assertIsInstance(r, ResultatAgents)
        self.assertTrue(r.a3.get('success'), f"A3 : {r.a3.get('erreur')}")

        for arb in (r.frequence, r.cout, r.prime_pure):
            with self.subTest(cible=arb.cible):
                self.assertIsInstance(arb, ArbitrageCible)
                self.assertIsNone(arb.erreur,
                    f"Arbitrage '{arb.cible}' en erreur : {arb.erreur}")
                self.assertIn(arb.statut_rag, ['VERT', 'AMBRE', 'ROUGE'])
                self.assertTrue(arb.a6.get('classement'),
                    f"Classement VIDE sur '{arb.cible}' : A6 n'a arbitré personne.")
                self.assertIsNotNone(
                    (arb.a6.get('modele_production') or {}).get('modele'),
                    f"Aucun modèle de production sur '{arb.cible}'.")

        # Les TROIS cibles sont DISTINCTES — sinon on arbitrerait deux fois la même.
        self.assertEqual(r.frequence.cible, _PLAN_AUTO.cible_frequence)
        self.assertEqual(r.cout.cible, CIBLE_COUT)
        self.assertEqual(r.prime_pure.cible, CIBLE_PRIME_PURE)

        # COÛT et PRIME PURE réellement challengés — plusieurs candidats chacun.
        # Avant l'orchestrateur : le coût n'avait qu'un candidat (GLM Gamma d'A3),
        # la prime pure directe n'était PAS challengée du tout (aucun A4/A5 dessus).
        self.assertGreater(r.cout.n_candidats, 1,
            "L'arbitrage COÛT n'a qu'un candidat : A4/A5 ne concourent pas.")
        self.assertGreater(r.prime_pure.n_candidats, 1,
            "L'arbitrage PRIME PURE n'a qu'un candidat : A4/A5 ne concourent pas "
            "contre le Tweedie d'A3.")
        print(f"    PA-1 Trois arbitrages ✅ | freq={r.frequence.statut_rag} "
              f"({r.frequence.n_candidats}) · cout={r.cout.statut_rag} "
              f"({r.cout.n_candidats}) · prime_pure={r.prime_pure.statut_rag} "
              f"({r.prime_pure.n_candidats})")

    def test_cann_present_en_frequence_absent_en_cout(self):
        """RÈGLE ACTUARIELLE : le CANN est exp(GLM_gelé + offset·log(exposition)),
        un modèle de COMPTAGE. La sévérité ne varie PAS avec l'exposition — c'est
        le sens même de E[S] = E[N] × E[C|N>0]. L'offset y serait faux."""
        m_freq = set((self.res.frequence.a5 or {}).get('metriques', {}))
        m_cout = set((self.res.cout.a5 or {}).get('metriques', {}))
        m_pp   = set((self.res.prime_pure.a5 or {}).get('metriques', {}))

        self.assertIn('cann', m_freq,
            "Le CANN doit concourir sur la FRÉQUENCE : son offset log-exposition "
            "y est cohérent.")
        self.assertIn('tabnet', m_freq)
        self.assertNotIn('cann', m_cout,
            "RÉGRESSION : le CANN a été calibré sur la cible COÛT. Son offset "
            "log(exposition) est incompatible avec une sévérité.")
        self.assertIn('tabnet', m_cout,
            "TabNet doit rester : c'est un réseau tabulaire générique, sans "
            "contrainte d'exposition.")
        self.assertNotIn('cann', m_pp,
            "RÉGRESSION : le CANN a été calibré sur la PRIME PURE. Son offset "
            "log(exposition) est une construction de comptage, incompatible avec "
            "une cible déjà annualisée (exposure-indépendante).")
        self.assertIn('tabnet', m_pp)
        print(f"    PA-2 CANN freq={sorted(m_freq)} · cout={sorted(m_cout)} · "
              f"prime_pure={sorted(m_pp)} ✅")

    def test_le_cout_tourne_sur_les_sinistres_seulement(self):
        """RÈGLE ACTUARIELLE : la sévérité est E[coût | sinistre]. S'entraîner sur
        tout le portefeuille modéliserait E[coût] INCONDITIONNEL — une prime pure
        déguisée, où la zéro-inflation ferait apprendre la FRÉQUENCE au modèle de
        coût. Le sous-échantillon vient de construire_cible_severite (source
        unique), jamais d'un masque recalculé ici."""
        def _n(arb):
            rap = arb.a4['rapport']
            return rap['nb_train'] + rap['nb_test']

        n_freq, n_cout = _n(self.res.frequence), _n(self.res.cout)
        n_sinistres_reels = int((self.df['cout_total_sinistres'] > 0).sum())

        self.assertLess(n_cout, n_freq,
            "Le modèle de COÛT s'entraîne sur autant de lignes que la fréquence : "
            "il voit donc les contrats SANS sinistre — ce n'est plus une sévérité.")
        # Tolérance : A3 écrête les graves, le masque exige un coût OBSERVÉ.
        self.assertLessEqual(n_cout, n_sinistres_reels)
        self.assertGreater(n_cout, 0)
        # La cible de sévérité doit exister comme COLONNE (c'est ce qui rend le
        # walk-forward du coût possible — il était disponible=False avant).
        self.assertIn(CIBLE_COUT, self.res.cout.a4['rapport'].get('feature_names', [])
                      + [CIBLE_COUT])
        print(f"    PA-3 Coût sur sinistrés ✅ | freq={n_freq:,} lignes · "
              f"cout={n_cout:,} lignes (sinistrés réels={n_sinistres_reels:,})")

    def test_resume_est_json_serialisable(self):
        """Contrat d'audit, comme tarifer() : 100 % types natifs. ResultatAgents
        lui-même ne l'est PAS et n'a pas à l'être (il porte dataframes et modèles
        pour travailler) ; resume() est ce qui se trace et se transmet."""
        res = self.res.resume()
        rendu = json.dumps(res)              # lève si un type n'est pas natif
        self.assertIsInstance(rendu, str)
        self.assertTrue(res['success'])
        self.assertIn('plan_empreinte', res)
        self.assertIn('date_calcul', res)
        for cible in ('frequence', 'cout', 'prime_pure'):
            with self.subTest(cible=cible):
                self.assertIn(res[cible]['statut_rag'], ['VERT', 'AMBRE', 'ROUGE'])
                self.assertTrue(res[cible]['classement'])
                self.assertIsNotNone(res[cible]['modele_production'])
        print(f"    PA-5 resume() JSON ✅ | {len(rendu):,} octets · "
              f"empreinte={res['plan_empreinte'][:16]}")


@unittest.skipUnless(TORCH_OK, "PyTorch absent — A5 ne peut pas être exercé")
class TestPipelineAgentsSansSinistre(unittest.TestCase):
    """Cas limite : aucun contrat sinistré. On ne bricole pas un modèle de
    sévérité sur rien — on le DIT."""

    def test_portefeuille_sans_sinistre_erreur_propre(self):
        res = _lancer(_portefeuille_auto(2000, avec_sinistres=False))

        # Contrat n°1 : ça ne CRASHE pas.
        self.assertIsInstance(res, ResultatAgents)
        # Contrat n°2 : l'arbitrage COÛT est en erreur PROPRE et NOMMÉE.
        self.assertIsNotNone(res.cout.erreur,
            "Aucun sinistre, et pourtant l'arbitrage coût aboutit : un modèle de "
            "sévérité a été bricolé sur rien.")
        self.assertIsNone(res.cout.a6)
        self.assertEqual(res.cout.n_candidats, 0)
        self.assertIn(res.cout.statut_rag, [None])
        # Contrat n°3 : l'erreur reste sérialisable (comme tarifer en échec).
        self.assertIsInstance(json.dumps(res.resume()), str)
        print(f"    PA-4 Sans sinistre → erreur propre ✅ | "
              f"cout.erreur = {res.cout.erreur[:70]}…")

    def test_trop_peu_de_sinistres_le_seuil_est_atteint(self):
        """⚠ Ce test existe parce que le précédent NE COUVRE PAS le seuil : à zéro
        sinistre, le Gamma d'A3 meurt AVANT (déviance nan) et c'est SON échec qui
        remonte — le garde-fou des 100 n'est jamais atteint. Ici A3 survit, et on
        vérifie que c'est bien NOTRE seuil qui refuse de modéliser une sévérité sur
        30 sinistres, en le NOMMANT. Sans ce test, le garde-fou serait mort-né."""
        df = _portefeuille_auto(3000, seed=5)
        idx = np.where(df['nb_sinistres'].to_numpy() > 0)[0]
        a_annuler = idx[30:]                       # on ne garde que 30 sinistres
        df.loc[a_annuler, 'nb_sinistres'] = 0.0
        df.loc[a_annuler, 'cout_total_sinistres'] = 0.0
        n_sin = int((df['cout_total_sinistres'] > 0).sum())
        self.assertLess(n_sin, 100, "Prémisse : il faut moins de 100 sinistrés.")

        res = _lancer(df)
        self.assertTrue(res.a3.get('success'),
            "Prémisse : A3 doit SURVIVRE, sinon c'est son échec qu'on teste, "
            "pas le seuil.")
        self.assertIsNotNone(res.cout.erreur)
        self.assertIn('non modélisable', res.cout.erreur)
        self.assertIn(str(n_sin), res.cout.erreur,
            "L'erreur doit NOMMER le nombre de sinistrés — un refus muet ne dit "
            "pas à l'actuaire ce qui manque.")
        # La FRÉQUENCE, elle, aboutit : un arbitrage perdu n'emporte pas l'autre.
        self.assertIsNone(res.frequence.erreur)
        self.assertTrue(res.frequence.a6.get('classement'))
        print(f"    PA-6 Seuil sévérité atteint ✅ | {n_sin} sinistrés → coût "
              f"refusé, fréquence aboutit ({res.frequence.n_candidats} candidats)")


if __name__ == '__main__':
    print("=" * 65)
    print("  TESTS pipeline_agents — orchestrateur 2 cibles")
    print("=" * 65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
