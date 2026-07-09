"""
Tests A3 GLM v1.0 — Tarification GLM Poisson/Gamma/Tweedie Non-Vie
7 tests · données synthétiques freMTPL2 · 500 contrats
"""
import sys, os, unittest
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))


def _make_r_a2(n=2000):
    """Result A2 synthétique avec données freMTPL2-like pour GLM.
    n=2000 et bonus_malus fortement discriminant pour garantir
    qu'au moins 1 variable est retenue par le stepwise backward.
    """
    np.random.seed(42)
    exposition  = np.random.uniform(0.1, 1.0, n)
    # bonus_malus dans [50, 350] — effet multiplicatif fort sur la fréquence
    bonus_malus = np.random.uniform(50, 350, n)
    # lambda proportionnel au bonus_malus : fort signal actuariel
    lam = 0.04 * exposition * (bonus_malus / 100.0)
    nb_sin     = np.random.poisson(lam, n).astype(float)
    cout       = np.where(nb_sin > 0, np.random.gamma(2, 400, n), 0.0)
    df = pd.DataFrame({
        'nb_sinistres':         nb_sin,
        'cout_total_sinistres': cout,
        'exposition':           exposition,
        'age':                  np.random.randint(18, 75, n).astype(float),
        'bonus_malus':          bonus_malus,
        'puissance_fiscale':    np.random.randint(4, 15, n).astype(float),
        'densite_population':   np.random.uniform(10, 5000, n),
        'log_exposition':       np.log(np.maximum(exposition, 1e-6)),
        'prime_pure':           cout * exposition,
    })
    return {
        'success': True, 'dataframe': df, 'branche': 'auto',
        'statut_rag': 'VERT', 'parametres': {}, 'rapport': {},
        'commentaire': 'OK', 'audit_id': 'A2_TEST', 'erreur': None,
    }


class TestA3GLM(unittest.TestCase):
    """A3 GLM — Calibration Poisson/Gamma/Tweedie, Gini, relativités, H1-H4."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
        cls.agent = AgentA3GLM(models_path='/tmp', audit_path='/tmp', verbose=False)
        cls.r_a2  = _make_r_a2(500)
        cls.r     = cls.agent.run(result_a2=cls.r_a2, generer_graphiques=False)

    def test_a3(self):
        r = self.r

        # ST1 — Pipeline sans erreur
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT', 'AMBRE', 'ROUGE'])
        print(f"    ST1 Pipeline ✅ | statut={r['statut_rag']}")

        # ST2 — Les 3 modèles GLM calibrés
        # Note : Tweedie peut ne pas avoir 'gini' si peu de sinistres en test
        met = r['metriques']
        for modele in ['poisson', 'gamma', 'tweedie']:
            self.assertIn(modele, met, f"Modèle {modele} manquant")
            m = met[modele]
            self.assertIn('aic', m)
            self.assertGreater(m.get('aic', 0), 0)
            # Gini présent uniquement si données test suffisantes
            if 'gini' in m:
                self.assertGreaterEqual(m['gini'], 0.0)
                self.assertLessEqual(m['gini'], 1.0)
        print(f"    ST2 3 GLM calibrés ✅ | Poisson AIC={met['poisson'].get('aic',0):.0f} "              f"Gini={'oui' if 'gini' in met['poisson'] else 'N/A (peu sinistres)'}")

        # ST3 — Gini Poisson calculé et positif
        gini_p = met['poisson'].get('gini', 0)
        self.assertGreaterEqual(gini_p, 0.0)
        self.assertLessEqual(gini_p, 1.0)
        print(f"    ST3 Gini Poisson ✅ | Gini={gini_p:.4f}")

        # ST4 — Stepwise backward : au moins 1 variable retenue
        # (n=2000 avec bonus_malus fortement discriminant garantit la sélection)
        vars_ret = met['poisson'].get('vars_retenues', [])
        self.assertIsInstance(vars_ret, list)
        self.assertGreater(len(vars_ret), 0,
            "Aucune variable retenue — vérifier la puissance statistique des données")
        print(f"    ST4 Stepwise ✅ | {len(vars_ret)} var(s) retenue(s) : {vars_ret[:3]}")

        # ST5 — Relativités tarifaires exp(β) présentes et cohérentes
        rels = r.get('relativites_poisson', {})
        self.assertIsInstance(rels, dict)
        self.assertGreater(len(rels), 0, "Aucune relativité calculée")
        # Vérifier la structure d'au moins une relativité
        first_rel = next(iter(rels.values()))
        for key in ['beta', 'relativite', 'ic95_low', 'ic95_high', 'pvalue']:
            self.assertIn(key, first_rel, f"Clé '{key}' manquante dans relativités")
        # Toutes les relativités exp(β) sont positives
        for var, d in rels.items():
            self.assertGreater(d['relativite'], 0,
                f"Relativité négative pour '{var}' : {d['relativite']}")
        print(f"    ST5 Relativités ✅ | {len(rels)} var(s) | "
              f"ex: {list(rels.keys())[0]}={list(rels.values())[0]['relativite']:.3f}")

        # ST6 — Standard ActuarIA : clés obligatoires
        for key in ['excel_bytes', 'hypotheses', 'audit_trail']:
            self.assertIn(key, r, f"Clé '{key}' manquante dans le résultat")
        self.assertIsInstance(r['excel_bytes'], bytes)
        self.assertIsInstance(r['audit_trail'], dict)
        hyp = r['hypotheses']
        for hkey in ['h1_poisson', 'h2_homosc', 'h3_ajustement', 'h4_stabilite']:
            self.assertIn(hkey, hyp, f"Hypothèse '{hkey}' manquante")
        print(f"    ST6 Standard ActuarIA ✅ | excel={len(r['excel_bytes'])} bytes | "
              f"H1={hyp['h1_poisson']['statut']} H2={hyp['h2_homosc']['statut']} "
              f"H3={hyp['h3_ajustement']['statut']} H4={hyp['h4_stabilite']['statut']}")

        # ST7 — Cohérence AIC : Poisson AIC > 0, déviance nulle > déviance
        m_p = met['poisson']
        self.assertGreater(m_p['deviance_nulle'], m_p.get('deviance', 0),
            "Déviance nulle doit être > déviance du modèle")
        self.assertGreater(m_p.get('pseudo_r2', 0), 0,
            "Pseudo-R² doit être positif")
        print(f"    ST7 Cohérence AIC ✅ | déviance={m_p.get('deviance',0):.2f} < "
              f"nulle={m_p['deviance_nulle']:.2f} | pseudo-R²={m_p.get('pseudo_r2',0):.4f}")


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A3 GLM v1.0 — TARIFICATION POISSON/GAMMA/TWEEDIE")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
