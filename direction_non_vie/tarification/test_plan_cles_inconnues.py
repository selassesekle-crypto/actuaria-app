"""Controles positifs — `plan/C5`, RANG 1 : la porte du plan n'avale plus rien.

CE QUE CE FICHIER PROUVE, ET POURQUOI C'EST UN RANG 1
─────────────────────────────────────────────────────

Le plan est le document que l'actuaire SIGNE, et il est opposable. Sa porte
d'entree, `depuis_dict`, lisait les cles qu'elle connaissait et **ignorait
toutes les autres sans un mot**.

⚠️⚠️ L'EURO BOUGE, ET IL A ETE MESURE. Declarer `famille_severity: lognormal`
(l'anglais) au lieu de `famille_severite` etait accepte en silence et rendait
une **gamma** :

```
  prime totale        : +1,00 %
  sur 1 500 contrats  : +42 124 EUR
  sur un seul contrat : jusqu'a +525,35 EUR
```

*L'actuaire signait une log-normale et obtenait autre chose.*

═══ L'ASYMETRIE ENTRE VOISINS, ET ELLE PENCHE DU BON COTE ═══

Mesure du 30/08/2026, dans le MEME fichier :

```
  PlanTarifaire.depuis_dict  -> cle inconnue ACCEPTEE en silence
  Facteur (via depuis_dict)  -> cle inconnue ACCEPTEE en silence
  Comportement(**d)          -> cle inconnue LEVE DEJA (TypeError)
```

⚠️ **Deux des trois sous-objets se taisaient, le troisieme refusait.** Le
correctif n'invente donc aucun comportement : il ALIGNE les deux autres sur
celui qui avait deja raison, et fait passer les trois par la meme porte pour
qu'ils rendent le meme motif.

═══ CE QUE LE CORRECTIF FAIT ═══

⚠️ LES CLES CONNUES SONT DERIVEES DE LA DATACLASSE, JAMAIS RECOPIEES. Une liste
en dur divergerait au premier champ ajoute -- et c'est exactement ce qui va
arriver : `unite_exposition` est le prochain, et le garde-fou doit le couvrir
sans qu'on y pense.

⚠️ LE MOTIF DIT QUOI FAIRE : il nomme la cle fautive, l'endroit, et propose la
plus proche des cles connues. *Une faute d'orthographe se corrige si on voit le
bon mot, pas si on lit « cle invalide ».*

⚠️ AUCUN PLAN LIVRE N'EST CASSE, et c'est mesure AVANT le correctif : **0/20**
portaient une cle inconnue. Cette etape ne peut donc pas degrader l'existant.
"""

from __future__ import annotations

import copy
import dataclasses
import glob
import unittest

import yaml

from core.plan_tarifaire import Comportement, Facteur, PlanTarifaire

_PLANS = sorted(glob.glob('plans/*.yaml'))


def _base() -> dict:
    """Le plan `auto` livre, comme dictionnaire — la vraie porte d'entree."""
    with open('plans/auto.yaml', encoding='utf-8') as fh:
        return yaml.safe_load(fh)


class TestLaPorteRefuseCeQuEllePasseSousSilence(unittest.TestCase):
    """`plan/C5` — LE CONTROLE QUI FERME, sur les quatre cas du releve."""

    def test_LE_TEST_QUI_FERME_les_quatre_cas_du_constat_LEVENT(self):
        """⚠️⚠️ Les quatre formes relevees, une par une. `famille_severity` est
        celle qui deplacait 42 124 EUR."""
        for libelle, cle, valeur in (
                ('anglais sur la famille', 'famille_severity', 'lognormal'),
                ('pluriel sur l echeance', 'echeances', 'date_echeance'),
                ('anglais sur l identifiant', 'identifiant_contract', 'id'),
                ('cle totalement inventee', 'zorglub', 1)):
            with self.subTest(cas=libelle):
                d = _base()
                d[cle] = valeur
                with self.assertRaises(ValueError) as leve:
                    PlanTarifaire.depuis_dict(d)
                self.assertIn(cle, str(leve.exception),
                              'le motif ne nomme pas la cle fautive')
        print("    PC5-1 les 4 cas du constat levent, et le motif nomme la cle")

    def test_le_motif_PROPOSE_la_cle_la_plus_proche(self):
        """⚠️ Une faute d'orthographe se corrige si on voit le bon mot. Sans
        cette suggestion, l'actuaire lit « cle invalide » et cherche."""
        for faute, attendue in (('famille_severity', 'famille_severite'),
                                ('echeances', 'echeance'),
                                ('identifiant_contract', 'identifiant_contrat')):
            with self.subTest(faute=faute):
                d = _base()
                d[faute] = 'x'
                with self.assertRaises(ValueError) as leve:
                    PlanTarifaire.depuis_dict(d)
                self.assertIn(f"vouliez-vous '{attendue}' ?", str(leve.exception))
        print("    PC5-2 le motif propose la cle la plus proche, 3 fois sur 3")

    def test_le_motif_dit_POURQUOI_c_est_grave(self):
        """⚠️ Le plan est signe : le motif doit dire ce qui se joue, pas
        seulement ce qui est refuse."""
        d = _base()
        d['zorglub'] = 1
        with self.assertRaises(ValueError) as leve:
            PlanTarifaire.depuis_dict(d)
        motif = str(leve.exception)
        self.assertIn('document que vous signez', motif)
        self.assertIn('autre tarif', motif)
        self.assertIn('Cles acceptees ici', motif,
                      "le motif ne liste pas les cles valides")
        print("    PC5-3 le motif dit l'enjeu ET liste les cles acceptees")


class TestLesTroisSousObjetsParlentDUneSeuleVOIX(unittest.TestCase):
    """⚠️⚠️ L'asymetrie entre voisins etait DANS le meme fichier."""

    def test_un_FACTEUR_a_cle_inconnue_leve_aussi(self):
        """⚠️⚠️ SANS CE SENS, LE CORRECTIF AURAIT LAISSE LE JUMEAU UN NIVEAU
        PLUS BAS. Corriger le seul niveau racine, c'est « corrige OU ? »."""
        d = _base()
        d['facteurs'][0]['encodages'] = 'one_hot'      # pluriel
        with self.assertRaises(ValueError) as leve:
            PlanTarifaire.depuis_dict(d)
        motif = str(leve.exception)
        self.assertIn('facteur', motif.lower(),
                      "le motif ne dit pas QUEL facteur est fautif")
        self.assertIn("vouliez-vous 'encodage' ?", motif)
        print(f"    PC5-4 un facteur fautif est nomme : « {motif[:56]}... »")

    def test_le_bloc_COMPORTEMENT_passe_par_la_meme_porte(self):
        """⚠️ Il levait deja, mais avec un `TypeError` nu. Meme porte, meme
        motif : *un garde-fou qui parle deux langues se lit deux fois.*"""
        d = _base()
        d['comportement'] = {'issue': 'i', 'prime_precedente': 'a',
                             'prime_proposee': 'b', 'zorglub': 1}
        with self.assertRaises(ValueError) as leve:
            PlanTarifaire.depuis_dict(d)
        self.assertIn('comportement', str(leve.exception))
        self.assertIn('zorglub', str(leve.exception))
        print("    PC5-5 le bloc `comportement` rend le meme motif que le reste")

    def test_les_cles_connues_sont_DERIVEES_des_dataclasses(self):
        """⚠️⚠️ LE CONTROLE QUI PROTEGE LE CHANTIER SUIVANT. Une liste en dur
        divergerait au premier champ ajoute, et `unite_exposition` arrive.
        On verifie qu'AUCUN nom de champ n'est recopie dans le garde-fou."""
        import inspect

        from core.plan_tarifaire import _refuser_cles_inconnues
        source = inspect.getsource(_refuser_cles_inconnues)
        for classe in (PlanTarifaire, Facteur, Comportement):
            for champ in dataclasses.fields(classe):
                with self.subTest(champ=champ.name):
                    self.assertNotIn(f"'{champ.name}'", source,
                                     f"le nom de champ '{champ.name}' est "
                                     f"RECOPIE dans le garde-fou : il "
                                     f"divergera au prochain champ ajoute")
        self.assertIn('dataclasses.fields', source,
                      'les cles connues ne sont pas derivees de la structure')
        print("    PC5-6 0 nom de champ recopie — les cles derivent de "
              "`dataclasses.fields`")


class TestAucunPlanLivreNEstCasse(unittest.TestCase):
    """⚠️⚠️ SECOND SENS — un garde-fou qui casse la livraison est pire que rien."""

    def test_les_20_plans_livres_chargent_TOUJOURS(self):
        self.assertEqual(len(_PLANS), 20,
                         f'premisse : 20 plans attendus, {len(_PLANS)} trouves')
        for f in _PLANS:
            with self.subTest(plan=f):
                PlanTarifaire.depuis_yaml(f)
        print(f"    PC5-7 second sens : {len(_PLANS)}/20 plans livres chargent")

    def test_un_plan_MINIMAL_et_valide_passe(self):
        """⚠️ Le garde-fou ne doit pas exiger les champs OPTIONNELS : il refuse
        ce qu'il ne connait pas, il n'impose pas ce qu'il connait."""
        d = copy.deepcopy(_base())
        for optionnel in ('identifiant_contrat', 'echeance', 'comportement',
                          'auteur', 'version'):
            d.pop(optionnel, None)
        p = PlanTarifaire.depuis_dict(d)
        self.assertEqual(p.lob, _base()['lob'])
        print("    PC5-8 second sens : un plan sans aucun champ optionnel passe")


if __name__ == '__main__':
    unittest.main()
