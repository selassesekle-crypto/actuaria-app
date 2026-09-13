r"""
==============================================================================
  UN MOTEUR QUI NE RETIENT AUCUNE VARIABLE PUBLIE QUAND MEME SON PRIX
==============================================================================

⚠️⚠️ CE QUE CE CONTROLE EXISTE POUR EMPECHER, ET IL EST ARRIVE SUR LE JEU
DE REFERENCE DES DOCUMENTS SIGNES. `_calculer_predictions` portait TROIS
gardes -- `if vars_poisson:`, `if vars_gamma:`, `if vars_tweedie:` --
**sans aucun `else`**. Quand la selection descendante n'avait rien retenu,
le bloc entier etait saute : pas de cle dans le resultat, pas d'erreur,
pas de `prediction_impossible`. **Du silence, sous `success: True`.**

ET LA CASCADE EST ECRITE DANS LE MODULE : `prime_pure` n'est calculee que
si `frequence_annuelle` ET `cout_moyen` sont presentes. *Une moitie
manquante emporte le prix entier.*

MESURE DU 13/09/2026, huit portefeuilles :

    signal fort (5 cas)   poisson ok   gamma ok   prime pure OUI
    signal NUL  (3 cas)   poisson MUET            prime pure NON
    `success: True` les HUIT fois

ET SUR LE JEU DU GEL -- celui des livrables signes -- c'est le GAMMA qui
retient zero : `cout_moyen` et `prime_pure` manquaient aux documents.
Garde levee : le Gamma rend 1 200 valeurs, et la prime pure revient a
1 165 valeurs distinctes.

⚠️⚠️ LE MODELE EXISTAIT POURTANT, ET IL SAIT PREDIRE. Le socle l'ajuste a
la SEULE CONSTANTE et le declare legitime -- << c'est un tarif qui ne
segmente pas, et il se dit >>. *L'agent jetait le modele que le socle
venait d'ajuster.*

⚠️ CE QUE CELA PUBLIE EST UN TARIF PLAT SUR CETTE MOITIE, ET C'EST VOULU.
La distinction avec le defaut de L5 est entiere : la, le cout etait plat
parce qu'une LIGNE ETAIT MORTE ; ici il est plat parce que le modele n'a
RIEN RETENU, et `puissance_selection` porte la phrase. *Un tarif a zero
facteur se voit ; un tarif absent ne se voit pas.*
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
#: les trois couples (moteur, cle publiee) -- la table est DERIVEE plus bas
_COUPLES = (('poisson', 'frequence_annuelle'),
            ('gamma', 'cout_moyen'),
            ('tweedie', 'prime_pure_tweedie'))


def _portefeuille(graine, n, taux, signal):
    """⚠️ `signal=0.0` : le profil n'explique RIEN. La selection descendante
    epuise alors ses variables -- c'est la situation reelle d'un petit
    portefeuille ou d'une population homogene, pas un cas de laboratoire."""
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
    lam = taux * np.exp(signal * 0.30 * (d['bonus_malus'] - 0.75))
    d['nb_sinistres'] = r.poisson(lam * d['exposition'])
    base = 600.0 * np.exp(signal * 0.45 * (d['bonus_malus'] - 0.75))
    d['cout_total_sinistres'] = np.where(
        d['nb_sinistres'] > 0,
        r.gamma(4.0, base / 4.0) * d['nb_sinistres'], 0.0)
    return d


def _chaine(cle, graine, n, taux, signal):
    """A1 -> A2 -> A3, mise en cache : deux chaines par fichier suffisent."""
    if cle in _CACHE:
        return _CACHE[cle]
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
        tmp = tempfile.mkdtemp(prefix='zv_')
        plan = PlanTarifaire.depuis_yaml(str(_RACINE / 'plans' / 'auto.yaml'))
        d = _portefeuille(graine, n, taux, signal)
        r1 = AgentA1Ingestion(base_path=tmp + '/d', audit_path=tmp + '/a',
                              verbose=False).run(
            branche='non_vie', sous_branche='auto', dataframe=d, plan=plan)
        rq = preambule_qualite(r1.get('dataframe'), plan,
                               horodatage='2026-09-13T00:00:00')
        r2 = AgentA2Preprocessing(verbose=False).run(
            result_a1={**r1, 'dataframe': rq.dataframe_propre}, plan=plan)
        r3 = AgentA3GLM(verbose=False).run(
            result_a2=r2, plan=plan, col_frequence=plan.cible_frequence,
            col_cout=plan.cible_cout, generer_graphiques=False)
    finally:
        logging.disable(niveau)
    _CACHE[cle] = r3
    return r3


def _sans_signal():
    return _chaine('nul', 7, 1200, 0.14, 0.0)


def _avec_signal():
    return _chaine('fort', 20260913, 3000, 0.45, 1.0)


class TestUnMoteurSansVariablePublieQuandMeme(unittest.TestCase):

    def test_ZV1_SCEAU_un_moteur_a_ZERO_variable_publie_sa_prediction(self):
        """⚠️⚠️ LE SCEAU. Un moteur qui ne retient rien a quand meme ete
        AJUSTE : le socle pose le modele a la seule constante et le declare
        legitime. Le jeter revient a supprimer la moitie d'un tarif signe
        sans le dire."""
        import numpy as np
        r3 = _sans_signal()
        pred = r3.get('predictions') or {}
        met = r3.get('metriques') or {}
        n = len(np.asarray(pred.get('frequence_brute', []), dtype=float))
        zero = []
        for moteur, cle in _COUPLES:
            m = met.get(moteur) or {}
            if m.get('nb_vars_retenues') != 0:
                continue
            zero.append(moteur)
            v = np.asarray(pred.get(cle, []), dtype=float)
            self.assertTrue(
                v.size,
                f"`{moteur}` retient ZERO variable et ne publie AUCUN "
                f"`{cle}` : la moitie du tarif disparait en silence, sous "
                f"success={r3.get('success')}.")
            self.assertEqual(
                v.size, n,
                f"`{moteur}` publie {v.size} valeurs pour {n} contrats")
        self.assertTrue(
            zero,
            "aucun moteur ne retient zero variable sur ce portefeuille : "
            "ce controle ne mesure plus ce qu'il annonce -- refaire le jeu")
        print(f"    ZV-1 SCEAU : {zero} a zero variable, prediction publiee "
              f"sur {n} contrats")

    def test_ZV2_SCEAU_la_PRIME_PURE_survit_a_un_moteur_sans_variable(self):
        """⚠️⚠️ LA CASCADE, ET C'EST ELLE QUI COUTE. `prime_pure` n'est
        calculee que si `frequence_annuelle` ET `cout_moyen` sont presentes :
        une seule moitie manquante emporte le PRIX ENTIER. Mesure du 13/09 :
        trois portefeuilles sur huit n'avaient plus de prime pure."""
        import numpy as np
        r3 = _sans_signal()
        pred = r3.get('predictions') or {}
        pp = np.asarray(pred.get('prime_pure', []), dtype=float)
        self.assertTrue(
            pp.size,
            f"aucune PRIME PURE publiee (cles : {sorted(pred)}) alors que "
            f"success={r3.get('success')} : le tarif n'existe pas, et rien "
            f"ne le dit.")
        self.assertTrue(np.all(np.isfinite(pp)) and np.all(pp >= 0),
                        'la prime pure publiee n est pas finie et positive')
        print(f"    ZV-2 SCEAU : prime pure publiee sur {pp.size} contrats, "
              f"{len(np.unique(pp))} valeurs distinctes")

    def test_ZV3_SCEAU_la_PLATITUDE_est_DECLAREE_et_non_subie(self):
        """⚠️⚠️ CE QUI SEPARE CE LOT DE CELUI DE L5. En L5, le cout etait
        plat parce qu'une LIGNE ETAIT MORTE -- un defaut. Ici il peut etre
        plat parce que le modele n'a RIEN RETENU -- une mesure. *Publier un
        tarif plat sans le dire echangerait un silence contre un autre.*

        On exige donc que `puissance_selection` porte la phrase pour tout
        moteur a zero variable."""
        r3 = _sans_signal()
        met = r3.get('metriques') or {}
        muets = [mo for mo, _ in _COUPLES
                 if (met.get(mo) or {}).get('nb_vars_retenues') == 0]
        self.assertTrue(muets, 'aucun moteur a zero : rien a verifier')
        for moteur in muets:
            phrase = (met.get(moteur) or {}).get('puissance_selection')
            self.assertTrue(
                phrase,
                f"`{moteur}` ne retient AUCUNE variable et ne publie aucune "
                f"phrase de puissance : le tarif est plat et rien ne le dit.")
            self.assertIn(
                'SEGMENTANT', str(phrase).upper(),
                f"la phrase de `{moteur}` ne nomme pas le defaut de "
                f"segmentation : {str(phrase)[:70]}")
        print(f"    ZV-3 SCEAU : la platitude de {muets} est DECLAREE")

    def test_ZV4_CONTRE_EPREUVE_un_moteur_qui_RETIENT_ne_change_pas(self):
        """⚠️ Le second sens. Sur un portefeuille ou les trois moteurs
        retiennent des variables, rien de ce lot ne doit se voir -- et la
        segmentation doit rester entiere."""
        import numpy as np
        r3 = _avec_signal()
        pred = r3.get('predictions') or {}
        met = r3.get('metriques') or {}
        for moteur, cle in _COUPLES:
            m = met.get(moteur) or {}
            self.assertGreater(
                m.get('nb_vars_retenues') or 0, 0,
                f"`{moteur}` ne retient rien sur le portefeuille a SIGNAL "
                f"FORT : la contre-epreuve ne mesure pas ce qu'elle annonce")
            v = np.asarray(pred.get(cle, []), dtype=float)
            self.assertTrue(v.size, f"`{cle}` absente sur le cas sain")
        pp = np.asarray(pred.get('prime_pure', []), dtype=float)
        self.assertGreater(
            len(np.unique(pp)), pp.size // 2,
            f"la prime pure ne segmente plus : {len(np.unique(pp))} valeurs "
            f"distinctes pour {pp.size} contrats")
        print(f"    ZV-4 contre-epreuve : les 3 moteurs retiennent, prime "
              f"pure a {len(np.unique(pp))} valeurs distinctes")

    def test_ZV5_SCEAU_aucune_garde_ne_SAUTE_une_prediction(self):
        """⚠️⚠️ LA CAUSE, RELEVEE PAR AST. Le defaut n'etait pas une valeur
        fausse : c'etait un `if` sans `else` qui sautait un bloc entier.
        *Un controle qui ne verifierait que le comportement d'aujourd'hui
        laisserait un quatrieme moteur renaitre avec la meme garde demain.*"""
        import ast
        chemin = (_RACINE / 'direction_non_vie' / 'tarification' / 'a3_glm'
                  / 'agent.py')
        a = ast.parse(chemin.read_bytes().decode('utf-8'))
        fn = next(n for n in ast.walk(a) if isinstance(n, ast.FunctionDef)
                  and n.name == '_calculer_predictions')
        fautifs = []
        for n in ast.walk(fn):
            if not isinstance(n, ast.If) or n.orelse:
                continue
            test = ast.unparse(n.test)
            #: une garde sur une liste de variables, sans `else`
            if test.startswith('vars_') or test.endswith('vars_retenues'):
                fautifs.append(f'l.{n.lineno} : if {test}')
        self.assertEqual(
            fautifs, [],
            "une garde sur une liste de variables, SANS `else`, est revenue "
            "dans `_calculer_predictions` : elle sautera la prediction en "
            "silence.\n  " + "\n  ".join(fautifs))
        print('    ZV-5 SCEAU : 0 garde sans `else` sur une liste de '
              'variables')


if __name__ == '__main__':
    unittest.main(verbosity=2)
