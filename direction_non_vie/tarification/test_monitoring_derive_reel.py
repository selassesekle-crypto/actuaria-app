"""Controles positifs — constat `a4/C2` : le monitoring n'est plus simule.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
`a4/C2` disait : « le monitoring de derive est integralement simule ». Le PSI
sortait de `np.random.beta(2,5)` contre `beta(2.2,4.8)` sous graine 42 — donc
IDENTIQUE sur deux portefeuilles differents — et l'« historique Gini 12 mois »
etait une degradation inventee. Re-mesure du 26/08/2026 : **c'est ferme**.

⚠️⚠️ MAIS LA FERMETURE S'ETAIT PERIMEE EN SILENCE AILLEURS. La liste
`FIGURES_ECARTEES` retirait encore `monitoring_gini` du rapport SIGNE au motif
que ses donnees etaient « FABRIQUEES », en citant un code disparu. Une figure
mesuree restait donc accusee. **Le dernier test de ce fichier est le garde-fou
qui manquait** : il fait tomber la gate si le motif d'exclusion accuse encore.

⚠️ Le garde-fou qui existait ne voyait pas ce cas : il fait tomber la gate sur
une figure NOUVELLE ni au plan ni ecartee — jamais sur un MOTIF perime. Son
assiette couvrait les ajouts, pas le vieillissement. *Un garde-fou qui exclut
la seule chose qui compte n'en est pas un.*

⚠️ Ces tests sont des `unittest.TestCase` : la gate execute `unittest`, qui ne
collecte pas les fonctions `test_*` de niveau module.
"""

from __future__ import annotations

import ast
import inspect
import unittest

import numpy as np
import pandas as pd

from direction_non_vie.tarification.a4_ml.agent import AgentA4ML


def _a4() -> AgentA4ML:
    return AgentA4ML(models_path='/tmp', audit_path='/tmp', verbose=False)


def _portefeuille(centre: float, n: int = 600, graine: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(graine)
    return pd.DataFrame({
        'age':   rng.normal(centre, 8.0, n),
        'bonus': rng.normal(centre / 2.0, 4.0, n),
    })


def _valeur(sortie) -> float:
    """`_psi_reel` peut rendre un couple (psi, details) — on lit le PSI."""
    return float(sortie[0] if isinstance(sortie, tuple) else sortie)


class TestMonitoringDeriveReel(unittest.TestCase):
    """Le PSI mesure, la figure porte sa marque, et le motif ne perime plus."""

    # ══════════════════════════════════════════════════════════════════════
    # ① LE PSI REPOND AUX DONNEES — c'etait exactement le defaut
    # ══════════════════════════════════════════════════════════════════════

    def test_le_psi_differe_sur_deux_portefeuilles_differents(self):
        """⚠️ Le constat mesurait « PSI identique sur 2 portefeuilles = True ».

        La violation est plantee dans les deux sens : deux portefeuilles
        PROCHES doivent donner un PSI faible, deux ELOIGNES un PSI eleve. Si
        la grandeur redevenait une constante du module, les deux seraient
        egales et l'assertion tomberait.
        """
        a4 = _a4()
        psi_proches = _valeur(a4._psi_reel(
            _portefeuille(40.0), _portefeuille(41.0), 10, 20))
        psi_eloignes = _valeur(a4._psi_reel(
            _portefeuille(40.0), _portefeuille(65.0), 10, 20))

        self.assertNotAlmostEqual(
            psi_proches, psi_eloignes, places=3,
            msg="Le PSI est identique sur deux portefeuilles differents : "
                "c'est le defaut d'origine de `a4/C2`, revenu.")
        self.assertLess(
            psi_proches, psi_eloignes,
            f"Deux portefeuilles eloignes doivent deriver PLUS que deux "
            f"portefeuilles proches (obtenu {psi_proches:.4f} contre "
            f"{psi_eloignes:.4f}).")

    def test_aucun_tirage_aleatoire_ne_subsiste_dans_le_module_a4(self):
        """⚠️ Controle par AST, jamais par `grep` : un `np.random.*` reintroduit
        dans A4 ferait retomber le monitoring dans la simulation.

        Ce test EPINGLE la fermeture. Sans lui, la correction pouvait etre
        defaite sans que rien ne tombe — c'est precisement ce qui est arrive
        au MOTIF d'exclusion, qui a survecu six semaines a la correction.
        """
        from direction_non_vie.tarification.a4_ml import agent as mod_a4

        arbre = ast.parse(inspect.getsource(mod_a4))
        tirages = [
            f"ligne {n.lineno} : {ast.unparse(n)[:70]}"
            for n in ast.walk(arbre)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and 'random' in ast.unparse(n.func)
        ]
        self.assertEqual(
            tirages, [],
            f"Des tirages aleatoires sont revenus dans A4 : {tirages}. Le "
            f"monitoring publie serait de nouveau une constante du module.")

    # ══════════════════════════════════════════════════════════════════════
    # ② LA FIGURE PORTE SA MARQUE — le relevé disait « aucune marque »
    # ══════════════════════════════════════════════════════════════════════

    def test_la_figure_declare_qu_elle_ne_mesure_pas_la_derive_en_production(self):
        """Le titre publie disait « ... en production ». Rien n'entrait de la
        production. La figure doit dire elle-meme ce qu'elle compare."""
        from direction_non_vie.tarification.a4_ml import agent as mod_a4

        src = inspect.getsource(mod_a4)
        self.assertIn(
            "ne mesure PAS la dérive en production", src,
            "La figure `monitoring_gini` ne porte plus sa marque : elle "
            "redeviendrait lisible comme un monitoring de production.")

    def test_un_psi_non_mesure_ne_s_affiche_pas_comme_un_nombre(self):
        """Meme regle qu'au Gini du Tweedie : non mesure vaut `None`, et se
        DIT — un nombre a la place serait indiscernable d'une mesure."""
        from direction_non_vie.tarification.a4_ml import agent as mod_a4

        src = inspect.getsource(mod_a4)
        self.assertIn("PSI non mesuré", src)

    # ══════════════════════════════════════════════════════════════════════
    # ③ LE GARDE-FOU QUI MANQUAIT — un motif perime fait tomber la gate
    # ══════════════════════════════════════════════════════════════════════

    def test_aucun_motif_d_exclusion_n_accuse_une_figure_de_donnees_fabriquees(self):
        """⚠️⚠️ CE TEST EST LA VRAIE TROUVAILLE DU LOT.

        `FIGURES_ECARTEES` retirait `monitoring_gini` du rapport signe au
        motif de « donnees FABRIQUEES », six semaines apres la correction qui
        les avait rendues reelles. **Une accusation perimee est un defaut** :
        elle discredite une figure mesuree, et elle apprend au lecteur a se
        mefier des avertissements.

        Le garde-fou existant ne pouvait pas le voir — il fait tomber la gate
        sur une figure NOUVELLE ni au plan ni ecartee, jamais sur un motif qui
        vieillit. Son assiette couvrait les ajouts, pas le vieillissement.

        ⚠️ Ce controle ne decide RIEN de la publication : une figure peut
        rester ecartee. Il exige seulement que le motif enonce l'etat REEL.
        """
        from direction_non_vie.tarification.services.rapport_modeles_tarif import (
            FIGURES_ECARTEES,
        )

        accusations = ('fabriqu', 'simul', 'invent')
        fautifs = {
            cle: motif for cle, motif in FIGURES_ECARTEES.items()
            if any(mot in motif.lower() for mot in accusations)
            and 'ne sont plus' not in motif.lower()
        }
        self.assertEqual(
            fautifs, {},
            f"Motif(s) d'exclusion accusant des donnees fabriquees : "
            f"{fautifs}. Si l'accusation est VRAIE, elle doit citer la mesure "
            f"qui l'etablit AUJOURD'HUI ; si elle est perimee, elle salit une "
            f"figure mesuree.")

    def test_le_motif_de_monitoring_gini_dit_l_etat_mesure(self):
        """Second sens du controle precedent : le motif doit dire ce qui est
        vrai, pas seulement eviter le mot interdit."""
        from direction_non_vie.tarification.services.rapport_modeles_tarif import (
            FIGURES_ECARTEES,
        )

        motif = FIGURES_ECARTEES['monitoring_gini']
        self.assertIn('ne sont plus', motif)
        self.assertIn('arbitrage', motif.lower(), (
            "Le motif doit dire que la figure attend une DECISION, sinon son "
            "exclusion redevient un jugement implicite."))


if __name__ == '__main__':
    unittest.main()
