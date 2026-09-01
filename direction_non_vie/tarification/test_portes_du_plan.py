"""Controles positifs — TROIS PORTES : `pipeline/C4`+`C5`, `pipeline/C1` (residu),
`pipeline/C8`.

CE QUE CES TROIS CONSTATS ONT EN COMMUN, ET CE QUI LES SEPARE
──────────────────────────────────────────────────────────────

**Deux d'entre eux sont la meme forme** : *le plan declare une chose et pas
l'autre, et l'aval devine.* C'est exactement `unite_exposition`, qui declarait
le ROLE de l'exposition et jamais son UNITE.

| constat | ce que le plan declarait | ce qu'il ne declarait pas |
|---|---|---|
| `C4`+`C5` | rien sur les chargements | **la taxe**, donc le prix paye |
| `C1` residu | le TYPE d'un facteur | **son DOMAINE de validite** |

**Le troisieme est d'une autre nature**, et la mesure l'a recadre : ce n'est pas
un defaut de DETECTION, c'est une INDIFFERENCE au signal detecte.

═══ `C4` + `C5` — UNE SEULE QUESTION, PAS DEUX ═══

`C4` disait que les chargements << declarables dans le plan (etape 6) >> ne
l'etaient pas ; `C5` en est la CONSEQUENCE sur l'entree la plus chere :
`CHARGEMENTS_DEFAUT` portait `taxes: 0.33` -- le taux AUTO -- pour **les 20
LoB**, alors que son propre commentaire enumerait << auto 33 %, MRH 30 %,
RC 9 % >>. *Les corriger separement aurait repare deux fois le meme defaut.*

```
  MRH : 33 % au lieu de 30 %  ->  prime TTC x 1,0231   (+2,31 %)
  RC  : 33 % au lieu de  9 %  ->  prime TTC x 1,2202  (+22,02 %)
```

⚠️ **LATENT, ET IL FAUT LE DIRE** : `prime_ttc` n'a qu'UNE occurrence dans le
depot -- sa propre construction. Aucun service ne la lit ; seuls des tests
l'assertent `> 0`. *C'est la surface publique de `tarifer()`, pas un rapport
signe.*

═══ `C1` RESIDU — LISIBLE N'EST PAS PLAUSIBLE ═══

`C1` est ferme pour l'ILLISIBILITE : `tarifer()` refuse `bonus_malus =
'beaucoup'`. Il restait ouvert pour la PLAUSIBILITE -- `-999` est un flottant
parfaitement lisible, et rendait toujours un prix (-19,4 % sur le contrat de
reference). `modalites` borne les categoriels ; **le continu n'avait rien**.

═══ ⚠️⚠️ `C8` — LA RACINE N'EST PAS CELLE QUE LE CONSTAT DECRIT ═══

Le constat annonce une asymetrie de `fillna`. **Mesure du 31/08** :

```
  couche qualite -> valeur_illisible_exposition        5 lignes  (regle 3)
                    valeur_illisible_cible_frequence   4 lignes  (regle 3)
  NaN SURVIVANTS dans le dataframe PROPRE : exposition=5  nb_sinistres=4
  puis : ValueError << deviance function returned a nan ... should be reported >>
```

**La couche qualite fait son travail : elle SIGNALE et ne decide rien** (regle
3, la doctrine tranchee par `qualite/C8`). *Le defaut n'est pas la DETECTION,
c'est l'INDIFFERENCE au signal detecte.* L'actuaire recevait une invitation a
signaler un bug a `statsmodels` la ou son fichier portait 5 expositions
illisibles.

⚠️ **CE QUI A ETE REJETE, ET POURQUOI** : reclasser en regle 1 (un euro
bougerait, et << illisible >> est AMBIGU, pas IMPOSSIBLE) · un `fillna` en aval
(imputer en silence sur une donnee illisible -- le motif d'`a2/C5`).

═══ AUCUN EURO, PAR CONSTRUCTION ═══

⚠️⚠️ **AUCUN TAUX, AUCUNE BORNE N'EST INVENTE ICI.** Les vrais taux par LoB
demandent une source (le CGI) ; les vraies bornes sont des choix actuariels.
**0 / 20 plans declarent l'un ou l'autre** : le repli d'aujourd'hui s'applique
partout, a l'identique -- et il est desormais DIT. `PTE-9` le tient.

⚠️ `EMPREINTE_SCHEMA` bumpe `2` -> `3` : une TAXE decide de la prime payee, une
BORNE refuse un contrat. Les deux changent ce qui est tarife, donc les deux
sont opposables.
"""

from __future__ import annotations

import dataclasses
import glob
import logging
import unittest
import warnings

import numpy as np

from core.plan_tarifaire import (
    EMPREINTE_SCHEMA,
    Chargements,
    Facteur,
    PlanTarifaire,
)
from direction_non_vie.tarification.pipeline_tarifaire import (
    CHARGEMENTS_DEFAUT,
    DonneeIllisibleBloquante,
    phrase_chargements_non_declares,
    phrase_domaines_non_declares,
    pipeline_complet,
)
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)

_CONTRAT = {
    'age': 40, 'bonus_malus': 0.9, 'anciennete_permis': 20,
    'puissance_fiscale': 6, 'age_vehicule': 5, 'valeur_venale': 12000,
    'garantie': 'TousRisques', 'carburant': 'Diesel', 'csp': 'Cadre',
    'usage': 'Prive', 'antecedents_sinistres_n1': 0,
    'kilometrage_annuel': 12000, 'milieu_geographique': 'Urbain',
}


def _sans_bruit(fn, *a, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return fn(*a, **kw)
        finally:
            logging.disable(precedent)


def _tarif(plan=_PLAN_AUTO, n=800, seed=3, df=None):
    portefeuille = _portefeuille_auto(n, seed=seed) if df is None else df
    return _sans_bruit(pipeline_complet, portefeuille, plan,
                       qualite_validee_par='Selasse Sekle')


def _avec_bornes(nom, bornes, plan=_PLAN_AUTO):
    facteurs = tuple(dataclasses.replace(f, bornes=bornes) if f.nom == nom
                     else f for f in plan.facteurs)
    return dataclasses.replace(plan, facteurs=facteurs)


class TestPorte1Chargements(unittest.TestCase):
    """`pipeline/C4` + `C5` — LE PLAN DECLARE CE QU'IL SUPPOSAIT."""

    def test_LE_TEST_QUI_FERME_les_chargements_sont_DECLARABLES_et_OPPOSABLES(self):
        """⚠️⚠️ Une taxe decide de la prime PAYEE : elle doit etre dans
        l'empreinte, sinon deux plans qui facturent differemment rendraient
        `IDENTIQUE`."""
        self.assertIn('chargements',
                      {f.name for f in dataclasses.fields(PlanTarifaire)})
        base = _PLAN_AUTO.empreinte()
        auto = dataclasses.replace(
            _PLAN_AUTO, chargements=Chargements(taxes=0.33)).empreinte()
        rc = dataclasses.replace(
            _PLAN_AUTO, chargements=Chargements(taxes=0.09)).empreinte()
        self.assertNotEqual(auto, rc, "la taxe ne bouge pas l'empreinte : "
                                      "elle n'est donc pas opposable")
        self.assertNotEqual(base, auto)
        # ⚠️⚠️ DERIVE, JAMAIS ECRIT EN DUR. Ces deux lignes epinglaient `'s3:'`
        # et `EMPREINTE_SCHEMA == 3` en LITTERAL. Le bump `s3` -> `s4` du
        # constat `plan/C8` les a fait rougir -- alors que RIEN de ce que ce
        # test prouve n'avait bouge. C'est la TROISIEME occurrence du meme
        # defaut (`'s1:'` dans `test_horodatage_livrable`, puis ici) :
        # *un numero de schema epingle ailleurs que dans le golden fait de
        # chaque bump une edition a deux sites, sans la discipline du sceau.*
        # Le SEUL endroit qui doit connaitre le numero est le golden de
        # `test_plan_invariants`, ou constante et empreinte bougent ensemble.
        prefixe = f's{EMPREINTE_SCHEMA}:'
        self.assertTrue(all(e.startswith(prefixe) for e in (base, auto, rc)))
        # Ce qui est VRAI ET DURABLE : les chargements sont entres au schema 3,
        # donc le schema ne peut pas etre anterieur. Un bump futur ne rend pas
        # cette phrase fausse.
        self.assertGreaterEqual(EMPREINTE_SCHEMA, 3)
        print(f"    PTE-1 taxe dans l'empreinte : auto={auto} rc={rc}")

    def test_un_chargement_ABSURDE_est_refuse_a_la_declaration(self):
        """⚠️ SECOND SENS. Une commission a 100 % divise par zero dans
        `tarifer()` : la borne est le domaine de definition du calcul."""
        # ⚠️ DEUX EXCEPTIONS, ET LA DISTINCTION EST VOULUE : un TYPE invalide
        # leve `TypeError`, une VALEUR hors domaine leve `ValueError`.
        # *L'appelant qui rattrape ne traite pas les deux pareil.*
        for mauvais, attendu in (({'commission': 1.0}, ValueError),
                                 ({'taxes': -0.1}, ValueError),
                                 ({'frais': 'beaucoup'}, TypeError)):
            with self.subTest(**mauvais), self.assertRaises(attendu):
                Chargements(**mauvais)
        print("    PTE-2 commission >= 1, taux negatif, non-nombre : refuses")

    def test_le_repli_est_DIT_et_se_TAIT_quand_le_plan_declare(self):
        """⚠️⚠️ LES DEUX SENS. Un avertissement permanent est un avertissement
        qu'on cesse de lire."""
        muet = phrase_chargements_non_declares(_PLAN_AUTO)
        self.assertIn('CHARGEMENTS NON DECLARES', muet)
        self.assertIn('33%', muet.replace(' %', '%'))
        declare = phrase_chargements_non_declares(
            dataclasses.replace(_PLAN_AUTO, chargements=Chargements(taxes=0.09)))
        self.assertIsNone(declare, "la phrase parle alors que le plan declare")
        print("    PTE-3 repli non declare -> DIT ; plan declarant -> silence")

    def test_le_plan_declarant_est_REELLEMENT_applique(self):
        """⚠️ Un champ declare que le calcul n'utiliserait pas serait un champ
        qui PROMET — le defaut que cet audit poursuit."""
        t_auto = _tarif()
        t_rc = _tarif(dataclasses.replace(
            _PLAN_AUTO, chargements=Chargements(taxes=0.09)))
        ttc_auto = t_auto.tarifer(_CONTRAT)['prime_ttc']
        ttc_rc = t_rc.tarifer(_CONTRAT)['prime_ttc']
        self.assertAlmostEqual(ttc_auto / ttc_rc, 1.33 / 1.09, places=4)
        print(f"    PTE-4 taxe declaree APPLIQUEE : {ttc_auto} vs {ttc_rc} "
              f"(rapport {ttc_auto / ttc_rc:.4f} = 1.33/1.09)")


class TestPorte2Bornes(unittest.TestCase):
    """`pipeline/C1` residu — LISIBLE N'EST PAS PLAUSIBLE."""

    def test_LE_TEST_QUI_FERME_une_valeur_HORS_DOMAINE_est_refusee(self):
        """⚠️ Le motif nomme LA BORNE SIGNEE : l'actuaire doit pouvoir
        verifier le refus contre son plan."""
        t = _tarif(_avec_bornes('bonus_malus', (0.5, 3.5)))
        r = t.tarifer({**_CONTRAT, 'bonus_malus': -999})
        self.assertFalse(r['success'])
        motif = ' '.join(r.get('anomalies') or [r.get('erreur', '')])
        self.assertIn('HORS DU DOMAINE', motif)
        self.assertIn('[0.5, 3.5]', motif)
        self.assertIn('EXTRAPOLATION', motif)
        print(f"    PTE-5 -999 refuse, borne signee nommee : {motif[:66]}...")

    def test_second_sens_SANS_borne_le_comportement_est_CELUI_D_HIER(self):
        """⚠️⚠️ SANS CE SENS, la porte pourrait tout refuser et passer.
        **0 / 20 plans declarent des bornes : c'est la preuve d'aucun euro.**"""
        t = _tarif()
        r = t.tarifer({**_CONTRAT, 'bonus_malus': -999})
        self.assertTrue(r['success'], "un plan SANS borne refuse desormais : "
                                      "un euro a bouge sur l'existant")
        declarants = [f for f in sorted(glob.glob('plans/*.yaml'))
                      if any(fa.bornes for fa in
                             PlanTarifaire.depuis_yaml(f).facteurs)]
        self.assertEqual(declarants, [])
        print(f"    PTE-6 sans borne : prime rendue comme hier ; "
              f"0 / {len(glob.glob('plans/*.yaml'))} plans declarent")

    def test_l_absence_de_domaine_est_DITE_et_se_TAIT_quand_tout_est_borne(self):
        """⚠️⚠️ SANS CETTE PHRASE LA FERMETURE SERAIT A MOITIE. La porte
        existe, **0/20 plans la remplissent** : `-999` est donc toujours
        tarife, et rien ne le dirait. *Le meme piege qu'`unite_exposition`
        aurait eu si l'hypothese annuelle etait restee muette.*"""
        muet = phrase_domaines_non_declares(_PLAN_AUTO)
        self.assertIn('DOMAINES NON DECLARES', muet)
        self.assertIn('bonus_malus', muet)
        self.assertIn('EXTRAPOLATION', muet)
        tous = dataclasses.replace(
            _PLAN_AUTO,
            facteurs=tuple(dataclasses.replace(f, bornes=(0.0, 1e9))
                           if f.type == 'continu' else f
                           for f in _PLAN_AUTO.facteurs))
        self.assertIsNone(phrase_domaines_non_declares(tous),
                          'la phrase parle alors que tout est borne')
        r = _tarif().tarifer(_CONTRAT)
        self.assertIn('DOMAINES NON DECLARES', r['domaines_non_declares'])
        print("    PTE-12 absence de domaine DITE, et silence quand tout est "
              "borne")

    def test_une_borne_ABSURDE_est_refusee_a_la_declaration(self):
        """⚠️ *Un garde-fou mal declare est pire qu'aucun garde-fou.*"""
        for mauvaise, attendu in (((1, 2, 3), ValueError), ((5, 5), ValueError),
                                  (('a', 2), TypeError)):
            with self.subTest(b=mauvaise), self.assertRaises(attendu):
                Facteur(nom='x', type='continu', bornes=mauvaise)
        with self.assertRaises(ValueError):
            Facteur(nom='z', type='categoriel', encodage='label',
                    modalites=('a', 'b'), bornes=(0, 1))
        print("    PTE-7 triplet, min>=max, non-nombre, categoriel : refuses")


class TestPorte3IllisiblesSurUnRoleDuGLM(unittest.TestCase):
    """`pipeline/C8` — LE SIGNAL EXISTAIT, PERSONNE NE L'ECOUTAIT."""

    def test_LE_TEST_QUI_FERME_le_calcul_REFUSE_et_dit_pourquoi(self):
        """⚠️⚠️ Avant : `ValueError: deviance function returned a nan ...
        should be reported`. *Un message qui accuse la bibliotheque et non le
        fichier.*"""
        df = _portefeuille_auto(600, seed=3)
        df.loc[df.index[:5], 'exposition'] = np.nan
        df.loc[df.index[10:14], 'nb_sinistres'] = np.nan
        with self.assertRaises(DonneeIllisibleBloquante) as leve:
            _tarif(df=df)
        msg = str(leve.exception)
        self.assertIn('exposition', msg)
        self.assertIn('cible_frequence', msg)
        self.assertIn('5 ligne(s)', msg)
        self.assertIn('SIGNALEES', msg)
        self.assertIsNotNone(leve.exception.rapport)
        print(f"    PTE-8 refus NOMME : {msg[:70]}...")

    def test_second_sens_un_portefeuille_SAIN_tarife(self):
        """⚠️ Un refus qui tomberait toujours ne protegerait de rien."""
        t = _tarif()
        self.assertGreater(t.coefficient_equilibre, 0)
        print(f"    PTE-9 portefeuille sain : tarif produit, "
              f"k={t.coefficient_equilibre:.5f}")

    def test_second_sens_un_role_NON_consomme_ne_bloque_PAS(self):
        """⚠️⚠️ L'ASSIETTE. Refuser sur un role que le GLM ne lit pas serait un
        garde-fou plus large que sa raison — la 8e forme du piege d'assiette.

        ⚠️⚠️ LE CAS EST CONSTRUIT, PAS EMPRUNTE, ET LA MESURE L'EXIGE. Le
        detecteur `valeur_illisible_*` ne tourne AUJOURD'HUI que sur les trois
        roles que le GLM consomme (`exposition`, `cible_frequence`,
        `cible_cout`) : un identifiant illisible produit
        `valeur_absente_identifiant_contrat`, un autre code. **Le filtre de
        role ne peut donc rien filtrer aujourd'hui** — ma premiere version de
        ce controle s'appuyait sur un cas que la couche ne produit jamais, et
        le sceau l'a montre : le plant qui RETIRE le filtre ne la faisait pas
        tomber. *Un controle qui ne peut pas echouer est du decor.*

        Le filtre reste, et c'est motive : le jour ou la couche qualite
        detectera un illisible sur un role que le modele ne lit pas, refuser
        dessus serait faux. On forge donc le signalement pour l'exercer.
        """
        from core.qualite_donnees import Anomalie, RapportQualite
        from direction_non_vie.tarification.pipeline_tarifaire import (
            _refuser_illisibles_sur_roles_du_glm,
        )
        hors_assiette = Anomalie(
            code='valeur_illisible_identifiant_contrat', regle=3,
            role='identifiant_contrat', colonne='id_contrat', nb_lignes=5,
            proportion=0.05, index=(0, 1, 2, 3, 4),
            description='forge pour exercer le filtre de role')
        rapport = RapportQualite(
            lignes_initiales=100, lignes_retenues=100, exclusions=[],
            corrections=[], signalements=[hors_assiette],
            escalade_declenchee=False, anomalies_au_dela_seuil=[], seuil=0.05,
            validee_par=None, horodatage='t', bloque=False,
            dataframe_propre=None)
        roles = {'expo': 'exposition', 'freq': 'cible_frequence',
                 'cout': 'cible_cout'}
        _refuser_illisibles_sur_roles_du_glm(rapport, roles, 'auto')
        # ⚠️ Et le SENS INVERSE, sur le meme rapport : un role CONSOMME leve.
        rapport.signalements = [dataclasses.replace(hors_assiette,
                                                    role='exposition')]
        with self.assertRaises(DonneeIllisibleBloquante):
            _refuser_illisibles_sur_roles_du_glm(rapport, roles, 'auto')
        print("    PTE-10 role NON consomme : aucun refus ; role consomme : "
              "refus — le filtre de role porte bien sur l'assiette")


class TestAucunEuroSurLExistant(unittest.TestCase):

    def test_les_20_plans_ne_declarent_NI_chargements_NI_bornes(self):
        """⚠️⚠️ C'EST LA PREUVE D'AUCUN EURO. Le jour ou un plan declarera sa
        vraie taxe, l'euro bougera -- jusqu'a -22 % sur la RC -- et ce sera un
        ARBITRAGE, pas un effet de bord."""
        fichiers = sorted(glob.glob('plans/*.yaml'))
        plans = {f: PlanTarifaire.depuis_yaml(f) for f in fichiers}
        avec_ch = [f for f, p in plans.items() if p.chargements is not None]
        avec_bo = [f for f, p in plans.items()
                   if any(fa.bornes for fa in p.facteurs)]
        self.assertEqual(avec_ch, [])
        self.assertEqual(avec_bo, [])
        self.assertEqual(CHARGEMENTS_DEFAUT['taxes'], 0.33)
        print(f"    PTE-11 0 / {len(fichiers)} plans declarent chargements ou "
              f"bornes : repli inchange, aucun euro")


if __name__ == '__main__':
    unittest.main()
