r"""
==============================================================================
  LE COUT MOYEN PREDIT SEGMENTE, OU IL NE TARIFE PAS
==============================================================================

⚠️⚠️ CE QUE CE CONTROLE EXISTE POUR EMPECHER, ET IL EST ARRIVE. Le cout
moyen predit etait **une valeur unique pour tout le portefeuille**, sur
TOUS les portefeuilles, depuis toujours sur ce chemin. La cause d'hier
etait un `.values` sur un `ndarray` -- `core.severite.ModeleCout.predict`
est annote `-> np.ndarray` et fait lui-meme le `np.asarray` --, mais **ce
controle ne surveille pas cette cause** : il surveille le RESULTAT.

  Une cause future -- une nouvelle classe de modele, une autre forme de
  retour, un repli mal place, un raccourci de performance -- reproduirait
  le meme silence. *Ce qui doit etre tenu, c'est que le cout VARIE d'un
  contrat a l'autre ; pas qu'une ligne precise soit absente.*

⚠️⚠️ ET C'EST EXACTEMENT LE TROU QUE LA SUITE AVAIT. Toute la suite passait
avec un cout constant, parce qu'AUCUN controle ne l'exigeait segmente. Le
defaut n'a pas ete trouve par un test : il a ete trouve parce qu'un
correctif a cesse de l'avaler. *Un comportement que personne n'exige n'est
pas garanti, meme quand tout est vert.*

MESURE DU 13/09/2026, quatre portefeuilles independants -- graines,
tailles et sinistralites differentes, cout dependant du profil :

    cout moyen predit   AVANT   1 valeur distincte, les quatre fois
                        APRES   1 907 / 4 998 / 2 500 / 5 861
    prime pure          AVANT   414 valeurs distinctes
                        APRES   2 218

L'agregat, lui, ne bougeait que de -0,65 % : *il masquait entierement la
divergence individuelle.*

⚠️ LE PORTEFEUILLE DE CE FICHIER EST CONSTRUIT POUR QUE LA SEGMENTATION
SOIT POSSIBLE : le cout d'un sinistre y depend du profil (bonus-malus,
age). Sur un portefeuille ou le cout ne dependrait de rien, un modele
plat serait la BONNE reponse -- et ce controle mesurerait autre chose que
ce qu'il annonce.
==============================================================================
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

_CACHE: dict = {}


def _portefeuille_heterogene(graine=20260913, n=3000, taux=0.45):
    """Un portefeuille SYNTHETIQUE ou le cout DEPEND du profil.

    ⚠️ Sans cette dependance, un cout plat serait statistiquement correct
    et le controle n'aurait rien a exiger.
    """
    import numpy as np
    import pandas as pd
    r = np.random.default_rng(graine)
    d = pd.DataFrame({
        'id_contrat': np.arange(1, n + 1), 'date_echeance': '2023-01-01',
        'exposition': np.clip(r.beta(1.3, 1.5, n), 0.02, 1.0),
        'age': r.integers(18, 85, n),
        'bonus_malus': np.clip(r.normal(0.75, 0.20, n), 0.50, 3.50),
        'anciennete_permis': r.integers(0, 50, n),
        'puissance_fiscale': r.integers(3, 20, n),
        'age_vehicule': r.integers(0, 25, n),
        'valeur_venale': np.exp(r.normal(9.3, 0.6, n)),
        'garantie': r.choice(['Tiers', 'TousRisques'], n),
        'carburant': r.choice(['Essence', 'Diesel', 'Electrique'], n),
        'csp': r.choice(['Cadre', 'Employe', 'Retraite'], n),
        'usage': r.choice(['Prive', 'Pro'], n),
        'antecedents_sinistres_n1': r.poisson(0.25, n),
        'kilometrage_annuel': r.integers(2000, 40000, n),
        'milieu_geographique': r.choice(
            ['Urbain', 'Periurbain', 'Rural'], n)})
    lam = taux * np.exp(0.30 * (d['bonus_malus'] - 0.75)
                        - 0.006 * (d['age'] - 45))
    d['nb_sinistres'] = r.poisson(lam * d['exposition'])
    #: le COUT d'un sinistre depend du profil -- c'est ce qui rend la
    #: segmentation possible, donc exigible
    base = 600.0 * np.exp(0.45 * (d['bonus_malus'] - 0.75)
                          + 0.010 * (45 - d['age']))
    d['cout_total_sinistres'] = np.where(
        d['nb_sinistres'] > 0,
        r.gamma(4.0, base / 4.0) * d['nb_sinistres'], 0.0)
    return d


def _resultat_a3():
    """La chaine A1 -> A2 -> A3, une seule fois pour tout le fichier."""
    if 'r3' in _CACHE:
        return _CACHE['r3']
    import logging
    import tempfile
    import warnings

    from core.plan_tarifaire import PlanTarifaire
    from core.qualite_donnees import preambule_qualite
    from direction_non_vie.tarification.a1_ingestion.agent import (
        AgentA1Ingestion,
    )
    from direction_non_vie.tarification.a2_preprocessing.agent import (
        AgentA2Preprocessing,
    )
    from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM

    warnings.filterwarnings('ignore')
    niveau = logging.getLogger().level
    logging.disable(logging.CRITICAL)
    try:
        tmp = tempfile.mkdtemp(prefix='seg_')
        plan = PlanTarifaire.depuis_yaml(str(_RACINE / 'plans' / 'auto.yaml'))
        r1 = AgentA1Ingestion(base_path=tmp + '/d', audit_path=tmp + '/a',
                              verbose=False).run(
            branche='non_vie', sous_branche='auto',
            dataframe=_portefeuille_heterogene(), plan=plan)
        rq = preambule_qualite(r1.get('dataframe'), plan,
                               horodatage='2026-09-13T00:00:00')
        r2 = AgentA2Preprocessing(verbose=False).run(
            result_a1={**r1, 'dataframe': rq.dataframe_propre}, plan=plan)
        r3 = AgentA3GLM(verbose=False).run(
            result_a2=r2, plan=plan, col_frequence=plan.cible_frequence,
            col_cout=plan.cible_cout, generer_graphiques=False)
    finally:
        logging.disable(niveau)
    _CACHE['r3'] = r3
    return r3


class TestLeCoutMoyenSegmente(unittest.TestCase):

    def _cout(self):
        import numpy as np
        r3 = _resultat_a3()
        pred = (r3.get('predictions') or {})
        cm = np.asarray(pred.get('cout_moyen', []), dtype=float)
        self.assertTrue(
            cm.size,
            f"A3 ne publie AUCUN cout moyen predit (success="
            f"{r3.get('success')}, erreur={str(r3.get('erreur'))[:70]}). "
            f"Sans lui, la moitie du tarif n'existe pas -- et ce controle "
            f"ne peut rien attester.")
        return cm, r3

    def test_SEG1_SCEAU_le_cout_predit_VARIE_d_un_contrat_a_l_autre(self):
        """⚠️⚠️ LE SCEAU. Un cout identique pour tout un portefeuille n'est
        pas une tarification : c'est une moyenne presentee comme un prix.

        Le critere ne cite AUCUNE ligne de code : il porte sur les valeurs
        publiees. Une cause future quelconque qui rendrait le cout plat le
        fait rougir."""
        import numpy as np
        cm, _ = self._cout()
        distinctes = len(np.unique(cm))
        self.assertGreater(
            distinctes, 1,
            f"le cout moyen predit vaut UNE SEULE valeur ({cm[0]:.2f}) pour "
            f"les {cm.size} contrats : le tarif ne segmente pas sur le "
            f"cout, il applique une moyenne.")
        #: ⚠️ ET PAS SEULEMENT << plus d'une valeur >>. Un cout a deux ou
        #: trois paliers serait plat en pratique ; on exige une vraie
        #: dispersion individuelle.
        self.assertGreater(
            distinctes, cm.size // 2,
            f"seulement {distinctes} couts distincts pour {cm.size} "
            f"contrats : la prediction est degeneree, pas segmentee.")
        etendue = float(np.max(cm) / max(float(np.min(cm)), 1e-9))
        self.assertGreater(
            etendue, 1.10,
            f"le cout predit s'etale de x{etendue:.3f} seulement entre le "
            f"contrat le moins cher et le plus cher : la variation est du "
            f"bruit, pas une segmentation.")
        print(f"    SEG-1 SCEAU : {distinctes} couts distincts sur "
              f"{cm.size} contrats, etendue x{etendue:.2f}")

    def test_SEG2_SCEAU_le_cout_predit_n_est_pas_la_MOYENNE_OBSERVEE(self):
        """⚠️⚠️ LA VALEUR EXACTE QUE LE REPLI POSAIT. A3 publie
        `cout_moyen_obs` dans ses metriques : c'est ce nombre-la que
        l'ancien `except` posait pour tous. Un repli futur qui le reposerait
        -- meme sous une autre forme, meme a un autre endroit -- rendrait
        un cout egal a cette metrique pour chaque contrat.

        *Ce controle vise la VALEUR fabriquee, pas le code qui la
        fabriquait.*"""
        import numpy as np
        cm, r3 = self._cout()
        obs = ((r3.get('metriques') or {}).get('gamma') or {}).get(
            'cout_moyen_obs')
        if obs is None:
            self.skipTest("`cout_moyen_obs` non publie : rien a comparer")
        colles = int(np.sum(np.isclose(cm, float(obs), rtol=1e-6)))
        self.assertLess(
            colles, cm.size // 2,
            f"{colles} contrats sur {cm.size} portent EXACTEMENT la moyenne "
            f"observee ({obs}) : c'est la valeur que l'ancien repli posait, "
            f"et elle est revenue.")
        print(f"    SEG-2 SCEAU : {colles}/{cm.size} contrats collent a la "
              f"moyenne observee {obs}")

    def test_SEG3_SCEAU_la_PRIME_PURE_herite_de_cette_variation(self):
        """⚠️⚠️ LA OU L'EURO SE VOIT. `prime pure = frequence x cout`. Quand
        le cout est plat, la prime ne varie plus que par la frequence -- et
        l'agregat, lui, ne bouge presque pas : *mesure du 13/09, -0,65 %
        sur le total quand la prime passait de 414 a 2 218 prix
        distincts.* Un controle sur l'agregat n'aurait rien vu."""
        import numpy as np
        r3 = _resultat_a3()
        pred = (r3.get('predictions') or {})
        pp = np.asarray(pred.get('prime_pure', []), dtype=float)
        self.assertTrue(pp.size, "aucune prime pure publiee")
        distinctes = len(np.unique(pp))
        self.assertGreater(
            distinctes, pp.size // 2,
            f"{distinctes} primes pures distinctes pour {pp.size} contrats : "
            f"un des deux facteurs du prix ne segmente pas.")
        print(f"    SEG-3 SCEAU : {distinctes} primes distinctes sur "
              f"{pp.size} contrats")

    def test_SEG4_LE_CRITERE_attrape_bien_un_cout_PLAT(self):
        """⚠️⚠️ LA CONTRE-EPREUVE DU MECANISME. Un critere qui ne saurait
        pas reconnaitre un cout plat rendrait les trois sceaux ci-dessus
        verts sur un portefeuille entierement aplati. *Un controle qui ne
        sait pas dire non ne dit rien.*"""
        import numpy as np
        plat = np.full(3000, 1694.62)
        self.assertEqual(len(np.unique(plat)), 1)
        self.assertFalse(
            len(np.unique(plat)) > plat.size // 2,
            "le critere de dispersion accepte un vecteur constant")
        etendue = float(np.max(plat) / max(float(np.min(plat)), 1e-9))
        self.assertFalse(
            etendue > 1.10,
            "le critere d'etendue accepte un vecteur constant")
        #: ⚠️ ET LE SECOND SENS : un vecteur REELLEMENT segmente passe.
        varie = np.linspace(800.0, 2400.0, 3000)
        self.assertTrue(len(np.unique(varie)) > varie.size // 2)
        self.assertTrue(
            float(np.max(varie) / np.min(varie)) > 1.10,
            "le critere refuse un vecteur pourtant bien segmente : il "
            "accuse au lieu de surveiller")
        print("    SEG-4 le critere dit NON a un cout plat et OUI a un "
              "cout segmente")


if __name__ == '__main__':
    unittest.main(verbosity=2)
