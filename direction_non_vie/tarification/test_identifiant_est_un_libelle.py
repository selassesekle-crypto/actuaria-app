"""Controles positifs — `qualite/C7` : l'identifiant de contrat est un LIBELLE.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────

═══ LE DEFAUT, MESURE LE 30/08/2026 ═══

`controler_qualite` faisait passer `identifiant_contrat` par
`detecter_illisible`, aux cotes de trois GRANDEURS (`exposition`,
`cible_frequence`, `cible_cout`). Ce detecteur compte comme illisible « ce que
`to_numeric` a detruit ». Or un numero de police est un **libelle** --
`P2024-00123`, `AUTO/45/8891` -- il n'est jamais cense etre un nombre.

Mesure, sur **400 contrats sans le moindre doublon** :

```
  identifiant « C0001 » (alphanumerique)  -> 100 % d'illisibles -> BLOQUE
  identifiant « 1..400 » (numerique)      -> 0 anomalie         -> passe
```

**Un fichier client normal etait refuse.** Et le motif designait la donnee du
client, jamais le detecteur.

═══ CE QUE LE CORRECTIF FAIT, ET CE QU'IL NE FAIT PAS ═══

⚠️⚠️ IL NE SUPPRIME PAS LA DETECTION, IL LA REMPLACE PAR LA BONNE. Un
identifiant **absent** reste une vraie ambiguite : la ligne ne peut etre
rattachee a aucun contrat, donc le dedoublonnage ne peut pas en juger. Retirer
le role de la boucle sans lui donner `detecter_absent` aurait ferme le constat
en detruisant une detection legitime -- le motif meme de cet audit.

⚠️⚠️ ET J'AI RETIRE UN CONTROLE QUE J'AVAIS ECRIT, PARCE QU'IL NE POUVAIT PAS
TOMBER. J'avais compose `detecter_illisible` a partir de `detecter_absent` et
ecrit un test de cette composition. La violation plantee ne l'a PAS fait
tomber : mesure sur 25 formes, `_num().isna()` seul est EQUIVALENT -- tout
absent est deja detruit par `to_numeric`. Le terme ajoute ne servait a rien, et
le test ne prouvait rien. *Un controle qui ne peut pas echouer est du decor.*
Les deux ont ete retires ; `detecter_illisible` est rendu INTACT.

⚠️ RGPD -- verifie par sentinelle : le message ne cite NI valeur NI index.
Un role, un nom de colonne, un compte. Rien d'autre ne sort.
"""

from __future__ import annotations

import dataclasses
import logging
import unittest
import warnings

import numpy as np
import pandas as pd

from core.qualite_donnees import (
    controler_qualite,
    detecter_absent,
    detecter_illisible,
)
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)

_PLAN_ID = dataclasses.replace(_PLAN_AUTO, identifiant_contrat='id_contrat')


def _controler(df, plan=_PLAN_ID):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return controler_qualite(df, plan,
                                     horodatage='2026-08-30T00:00:00')
        finally:
            logging.disable(precedent)


def _sur_identifiant(rapport):
    return [a for a in (rapport.signalements or []) + (rapport.exclusions or [])
            if a.role == 'identifiant_contrat']


class TestUnIdentifiantAlphanumeriqueEstNormal(unittest.TestCase):
    """`qualite/C7` — le defaut, dans sa forme pure."""

    def test_LE_TEST_QUI_FERME_un_identifiant_alphanumerique_ne_bloque_plus(self):
        """⚠️⚠️ LE CONSTAT MESURE : 400 contrats, aucun doublon, et le fichier
        etait REFUSE parce que l'identifiant n'etait pas un nombre."""
        r = _controler(_portefeuille_auto(400, seed=3).assign(
            id_contrat=[f'P2024-{i:05d}' for i in range(400)]))
        self.assertFalse(
            r.bloque,
            f"un portefeuille sain a identifiant alphanumerique est BLOQUE : "
            f"{r.anomalies_au_dela_seuil}")
        self.assertEqual(
            _sur_identifiant(r), [],
            'un identifiant non numerique est signale alors qu il est normal')
        print("    ID-1 400 identifiants « P2024-xxxxx » : 0 anomalie, ne "
              "bloque pas (avant : 100 % d'illisibles, BLOQUE)")

    def test_les_formes_reelles_de_numero_de_police_passent(self):
        """⚠️ Le constat ne portait pas sur une forme exotique : ce sont les
        formes ORDINAIRES d'un numero de contrat qui bloquaient."""
        for libelle in ('P2024-00123', 'AUTO/45/8891', 'C0001', '2024_AB_77'):
            with self.subTest(forme=libelle):
                r = _controler(_portefeuille_auto(200, seed=3).assign(
                    id_contrat=[f'{libelle}-{i}' for i in range(200)]))
                self.assertEqual(_sur_identifiant(r), [], f'{libelle} signale')
        print("    ID-2 quatre formes reelles de numero de police : aucune "
              "signalee")


class TestUneAbsenceResteDetectee(unittest.TestCase):
    """⚠️⚠️ LE SECOND SENS LE PLUS IMPORTANT DU LOT.

    Retirer le role de la boucle sans le remplacer aurait supprime une
    detection legitime. Une ligne sans identifiant ne peut etre rattachee a
    aucun contrat.
    """

    def test_un_identifiant_ABSENT_est_signale_en_REGLE_3(self):
        ids = [f'P2024-{i:05d}' for i in range(400)]
        for i in range(20):
            ids[i] = None
        for i in range(20, 30):
            ids[i] = '   '          # blanc : absent, pas illisible
        r = _controler(_portefeuille_auto(400, seed=3).assign(id_contrat=ids))
        vus = _sur_identifiant(r)
        self.assertTrue(vus, "30 identifiants absents ne sont vus par PERSONNE")
        a = vus[0]
        self.assertEqual(a.code, 'valeur_absente_identifiant_contrat')
        self.assertEqual(a.nb_lignes, 30,
                         f'{a.nb_lignes} lignes vues pour 30 absences')
        self.assertEqual(
            a.regle, 3,
            'une absence d identifiant EXCLUT ou CORRIGE au lieu de signaler : '
            'elle est AMBIGUE, aucune regle ne peut trancher a la place de '
            "l'actuaire")
        print(f"    ID-3 20 None + 10 blancs -> {a.nb_lignes} signales en "
              f"regle {a.regle}, aucune exclusion")

    def test_absent_et_illisible_ne_disent_PAS_la_meme_chose(self):
        """⚠️ La distinction, mesuree sur le meme vecteur : « douze mois » est
        ILLISIBLE pour une grandeur, il n'est pas ABSENT."""
        t = pd.DataFrame({'x': [1.0, np.nan, 'douze mois', '', 3.0]})
        self.assertEqual(
            list(np.asarray(detecter_illisible(t, 'x'), dtype=bool)),
            [False, True, True, True, False])
        self.assertEqual(
            list(np.asarray(detecter_absent(t, 'x'), dtype=bool)),
            [False, True, False, True, False],
            "« douze mois » est compte comme ABSENT : le detecteur des libelles "
            "teste la numerisabilite, ce qu'il ne doit pas faire")
        print("    ID-4 « douze mois » : illisible=OUI, absent=NON — les deux "
              "detecteurs sont distincts")


class TestLesGrandeursGardentLeurDetection(unittest.TestCase):
    """⚠️⚠️ SECOND SENS — resserrer une assiette ne doit pas la raboter."""

    def test_une_exposition_ILLISIBLE_est_toujours_signalee(self):
        d = _portefeuille_auto(400, seed=3)
        d['exposition'] = d['exposition'].astype(object)
        d.loc[d.index[:25], 'exposition'] = 'douze mois'
        r = _controler(d.assign(id_contrat=[f'P{i:05d}' for i in range(400)]))
        vus = [a.code for a in r.signalements if 'illisible' in a.code]
        self.assertIn('valeur_illisible_exposition', vus,
                      "l'exposition illisible n'est plus vue : l'assiette des "
                      'GRANDEURS a ete rabotee avec celle du libelle')
        print(f"    ID-6 second sens : exposition « douze mois » toujours "
              f"signalee ({vus})")


class TestLeMessageNeSortAucuneDonnee(unittest.TestCase):
    """⚠️⚠️ RGPD — non negociable. Un compte, jamais une valeur."""

    def test_le_message_ne_cite_NI_valeur_NI_index(self):
        sentinelle = 'P2024-SECRET'
        ids = [f'{sentinelle}-{i:04d}' for i in range(400)]
        ids[0] = None
        r = _controler(_portefeuille_auto(400, seed=3).assign(id_contrat=ids))
        for a in _sur_identifiant(r):
            with self.subTest(code=a.code):
                self.assertNotIn(sentinelle, a.description,
                                 'le message publie une VALEUR client')
                self.assertIn(a.colonne, a.description,
                              'le message ne nomme pas la colonne fautive')
                self.assertNotIn(str(list(a.index)[:1]), a.description,
                                 'le message publie des index de lignes')
        print("    ID-7 RGPD : aucune valeur client, aucun index — un role, "
              "une colonne, un compte")


if __name__ == '__main__':
    unittest.main()
