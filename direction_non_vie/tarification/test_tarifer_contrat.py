"""CONTRÔLE POSITIF — `pipeline/C1` : `tarifer()` refuse ce qu'il ne sait pas lire.

`tarifer()` acceptait n'importe quoi et rendait un prix sans un mot. Mesuré sur
un contrat de référence :

    bonus_malus = 'beaucoup'   ->  +128 %   success=True
    bonus_malus = ''           ->  +128 %   success=True
    bonus_malus = None         ->  +128 %   success=True

⚠️⚠️ **LES TROIS RENDAIENT LA MÊME PRIME** : toutes coercées vers le même repli
— l'imputation d'A2. *Le souscripteur recevait la prime du contrat MOYEN en
croyant tarifer le sien, et le contrat de sortie disait `success: True`.*

⚠️ CE QUI EST FERMÉ ET CE QUI NE L'EST PAS. Ce lot ferme l'ILLISIBILITÉ — une
valeur que le plan ne permet pas de lire. Il ne ferme **pas** la PLAUSIBILITÉ :
`bonus_malus = -999` et `1e12` restent tarifés, parce qu'ils sont *lisibles* et
qu'**aucune borne n'est déclarée dans le plan**. En inventer une ici serait
poser un chiffre actuariel que personne n'a signé.

⚠️ La modalité catégorielle inconnue est déjà couverte par `INV-7c`
(`test_plan_invariants.py`) — **ce fichier ne la duplique pas.**
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire
from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet

_RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))


def _portefeuille(plan, n=1500, graine=0):
    """Dérivé du PLAN — chaque facteur reçoit ce que son type déclare.
    ⚠️ Un portefeuille improvisé se fait refuser par A2 (piège V9), et à
    juste titre : `garantie` est un one-hot à modalités figées."""
    rng = np.random.default_rng(graine)
    d = {}
    for f in plan.facteurs:
        if f.type == 'categoriel' and f.modalites:
            d[f.nom] = rng.choice(list(f.modalites), n)
        elif f.type == 'binaire':
            d[f.nom] = rng.integers(0, 2, n).astype(float)
        else:
            d[f.nom] = rng.uniform(18, 70, n)
    for c in plan.colonnes_attendues():
        d.setdefault(c, rng.uniform(1, 10, n))
    d[plan.exposition] = np.ones(n)
    d[plan.cible_frequence] = rng.poisson(0.2, n).astype(float)
    d[plan.cible_cout] = np.where(d[plan.cible_frequence] > 0,
                                  rng.gamma(2, 300, n), 0.0)
    return pd.DataFrame(d)


class POS_Tarifer_C1_UnFacteurIllisibleNeProduitPlusDePrix(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.plan = PlanTarifaire.depuis_yaml(
            os.path.join(_RACINE, 'plans', 'auto.yaml'))
        cls.tarif = pipeline_complet(_portefeuille(cls.plan), cls.plan)
        cls.base = {
            f.nom: (f.modalites[0] if (f.type == 'categoriel' and f.modalites)
                    else 40.0)
            for f in cls.plan.facteurs}

    def test_les_trois_valeurs_illisibles_sont_REFUSEES(self):
        """⚠️ Les trois rendaient la MÊME prime, +128 % : le contrat moyen."""
        for libelle, valeur in (("texte", 'beaucoup'), ("chaine vide", ''),
                                ("None", None)):
            with self.subTest(cas=libelle):
                r = self.tarif.tarifer(dict(self.base, bonus_malus=valeur))
                self.assertFalse(
                    r['success'],
                    f"[{libelle}] un facteur illisible produit encore un prix")
                self.assertIsNone(r.get('prime_pure'),
                                  "une prime est rendue malgre le refus")
                self.assertIn('bonus_malus', r['erreur'],
                              "l'erreur ne nomme pas le facteur fautif")
        print("    POS-C1p les 3 valeurs illisibles sont REFUSEES ✅")

    def test_le_motif_dit_POURQUOI_le_prix_serait_faux(self):
        """⚠️ Un refus sans motif renvoie l'actuaire à la devinette. Le message
        doit dire que la prime rendue serait celle du contrat MOYEN."""
        r = self.tarif.tarifer(dict(self.base, bonus_malus=None))
        self.assertIn('MOYEN', r['erreur'],
                      "le motif ne dit pas que la prime serait celle du "
                      "contrat moyen")
        self.assertTrue(r.get('anomalies_contrat'),
                        "les anomalies ne sont pas rendues separement")

    def test_le_contrat_de_sortie_reste_STABLE_meme_en_refus(self):
        """⚠️ La docstring de `tarifer` promet que `success`, `plan_empreinte`
        et `date_calcul` sont TOUJOURS presents — succes comme erreur."""
        import json
        r = self.tarif.tarifer(dict(self.base, bonus_malus='beaucoup'))
        for cle in ('success', 'plan_empreinte', 'date_calcul', 'erreur'):
            self.assertIn(cle, r, f"'{cle}' manque au contrat de sortie")
        self.assertIsInstance(json.dumps(r), str,
                              "la reponse n'est plus serialisable en JSON")
        print("    POS-C1p le contrat de sortie reste stable en refus ✅")

    def test_LE_SECOND_SENS_un_contrat_VALIDE_tarife_a_l_identique(self):
        """⚠️⚠️ C'EST LE SENS QUI COMPTE. Une validation trop large refuserait
        des contrats legitimes — et `tarifer()` est l'API qui vend."""
        ref = self.tarif.tarifer(dict(self.base))
        self.assertTrue(ref['success'], f"le contrat de reference est refuse : "
                                        f"{ref.get('erreur')}")
        self.assertGreater(ref['prime_pure'], 0)
        # deux appels successifs : meme prime, au centime
        self.assertEqual(self.tarif.tarifer(dict(self.base))['prime_pure'],
                         ref['prime_pure'])
        print(f"    POS-C1p LE SECOND SENS : contrat valide tarife "
              f"({ref['prime_pure']}) ✅")

    def test_LE_SECOND_SENS_un_nombre_ECRIT_EN_TEXTE_reste_accepte(self):
        """⚠️ `'50'` est lisible : le refuser casserait tout appelant JSON, où
        les nombres arrivent souvent en chaînes."""
        a = self.tarif.tarifer(dict(self.base, bonus_malus=50))
        b = self.tarif.tarifer(dict(self.base, bonus_malus='50'))
        self.assertTrue(a['success'] and b['success'])
        self.assertEqual(a['prime_pure'], b['prime_pure'],
                         "'50' et 50 ne donnent pas la meme prime")
        print("    POS-C1p LE SECOND SENS : un nombre en texte reste accepte ✅")

    def test_ce_qui_reste_OUVERT_est_la_PLAUSIBILITE_pas_la_lisibilite(self):
        """⚠️⚠️ CE TEST ÉPINGLE UNE LIMITE, PAS UN SUCCÈS.

        `-999` et `1e12` sont *lisibles* : ils passent, et **c'est voulu**.
        Aucune borne de plausibilité n'est déclarée dans le plan, et en
        inventer une ici serait poser un chiffre actuariel que personne n'a
        signé. Si ce test se met à échouer, c'est qu'une borne a été ajoutée —
        **alors il faut qu'elle vienne du PLAN**, et ce test doit être révisé
        en conséquence, jamais supprimé en silence.
        """
        for valeur in (-999, 1e12):
            with self.subTest(valeur=valeur):
                r = self.tarif.tarifer(dict(self.base, bonus_malus=valeur))
                self.assertTrue(
                    r['success'],
                    f"{valeur} est desormais refuse : une borne de "
                    f"plausibilite a ete ajoutee. Vient-elle du PLAN SIGNE ?")
        print("    POS-C1p limite epinglee : la plausibilite reste OUVERTE ⚠️")


if __name__ == '__main__':
    unittest.main(verbosity=2)
