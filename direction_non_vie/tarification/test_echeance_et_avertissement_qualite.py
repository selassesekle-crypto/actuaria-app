"""Controles positifs — etapes 2 et 3 du chantier `plan/C7`.

CE QUE CE FICHIER PROUVE, ET POURQUOI LES DEUX ETAPES SONT UN SEUL LOT
──────────────────────────────────────────────────────────────────────

═══ ETAPE 2 — UN DOUBLON N'EST PAS UNE ECHEANCE ═══

`detecter_doublons_id` dedoublonnait sur l'identifiant SEUL, en **regle 1**,
c'est-a-dire **exclusion sans discussion**. Mesure : un historique de
renouvellement sur 3 ans porte **66,7 % de « doublons »** pour un seuil a 5 %.
A1 faisait DEJA le calcul par paire `(identifiant, echeance)` ; le chemin
declaratif, non. *« Corrige OU ? » vaut aussi entre deux chemins qui font le
meme metier.*

Le correctif a deux faces, et la seconde est la plus importante :

    echeance declaree ET presente -> cle = (identifiant, echeance), REGLE 1
    echeance absente              -> REGLE 3 : signale, lignes CONSERVEES

⚠️⚠️ POURQUOI LA REGLE CHANGE. Sans echeance, on ne peut PAS distinguer un
doublon d'un historique : la constatation devient **ambigue**, pas impossible.
*Exclure sans pouvoir trancher, c'est trancher a la place de l'actuaire.*

═══ ETAPE 3 — L'AVERTISSEMENT ET SON CHEMIN, DANS LE MEME GESTE ═══

⚠️⚠️ CONSTAT `services/C12`. `synthese_qualite_donnees` avait TROIS points de
sortie de production, et celui du rapport de modeles signe etait
`_construire_contexte_tarif` — **le prompt envoye au LLM**. Le rapport
d'equipe et l'Excel la publiaient sans IA ; **le document qui part au CAC et a
l'ACPR, non.** C'est `services/C10` mot pour mot, sur une autre fonction.

*Creer l'avertissement de l'etape 2 sans lui donner ce chemin aurait construit
un garde-fou qui s'evapore des que la cle manque.* Les deux etapes ne peuvent
donc pas etre separees, et les tests ci-dessous s'executent **sans cle API**.
"""

from __future__ import annotations

import dataclasses
import io
import logging
import os
import unittest
import warnings
import zipfile
from unittest import mock

import pandas as pd

from core.qualite_donnees import controler_qualite, synthese_qualite_donnees
from direction_non_vie.tarification.services import rapport_modeles_tarif as R
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)

_PLAN_ID = dataclasses.replace(_PLAN_AUTO, identifiant_contrat='id_contrat')
_PLAN_PAIRE = dataclasses.replace(_PLAN_ID, echeance='date_echeance')


def _historique(n_contrats: int = 300, n_exercices: int = 3):
    """Un HISTORIQUE de renouvellement : le meme contrat sur plusieurs exercices.

    ⚠️ Ce n'est pas un fichier fautif — c'est la forme normale d'un portefeuille
    suivi dans le temps, et c'est exactement la donnee qu'exige une elasticite.
    """
    base = _portefeuille_auto(n_contrats, seed=3)
    return pd.concat(
        [base.assign(id_contrat=[f'P2024-{i:05d}' for i in range(n_contrats)],
                     date_echeance=2023 + k) for k in range(n_exercices)],
        ignore_index=True)


def _controler(df, plan):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return controler_qualite(df, plan,
                                     horodatage='2026-08-30T00:00:00')
        finally:
            logging.disable(precedent)


def _sans_cle():
    """Environnement SANS cle API — c'est la condition de toute l'etape 3."""
    env = {k: v for k, v in os.environ.items()
           if k not in ('ANTHROPIC_API_KEY', 'CLAUDE_API_KEY')}
    return mock.patch.dict(os.environ, env, clear=True)


class TestUnDoublonNEstPasUneEcheance(unittest.TestCase):
    """Etape 2 — la cle du contrat est une PAIRE quand le plan la declare."""

    def test_LE_TEST_QUI_FERME_un_historique_avec_echeance_ne_bloque_plus(self):
        """⚠️⚠️ 66,7 % de « doublons » sur un fichier parfaitement normal."""
        r = _controler(_historique(), _PLAN_PAIRE)
        self.assertFalse(r.bloque,
                         f'historique de renouvellement BLOQUE : '
                         f'{r.anomalies_au_dela_seuil}')
        self.assertEqual([a.code for a in r.exclusions], [],
                         'des lignes d historique sont EXCLUES')
        print(f"    E2-1 historique {r.lignes_initiales} lignes (300 contrats x "
              f"3 exercices) : 0 exclusion, ne bloque pas")

    def test_SECOND_SENS_meme_contrat_MEME_echeance_reste_EXCLU(self):
        """⚠️⚠️ SANS CE SENS, LA PAIRE OUVRIRAIT UN TROU. Un vrai doublon —
        meme contrat, MEME exercice — reste impossible, donc regle 1."""
        h = _historique()
        r = _controler(pd.concat([h, h.iloc[:50]], ignore_index=True),
                       _PLAN_PAIRE)
        vrais = [a for a in r.exclusions if a.code == 'doublon_identifiant']
        self.assertTrue(vrais, 'un VRAI doublon n est plus exclu : la paire a '
                               'ouvert un trou')
        self.assertEqual(vrais[0].nb_lignes, 50)
        self.assertEqual(vrais[0].regle, 1)
        print(f"    E2-2 second sens : 50 vrais doublons (meme echeance) "
              f"exclus en regle {vrais[0].regle}")

    def test_SANS_echeance_la_regle_devient_3_et_les_lignes_RESTENT(self):
        """⚠️⚠️ LE CŒUR DE L'ETAPE. Sans echeance la constatation est AMBIGUE :
        on ne peut pas distinguer un doublon d'un historique."""
        h = _historique()
        r = _controler(h, _PLAN_ID)
        sig = [a for a in r.signalements
               if a.code == 'doublon_identifiant_sans_echeance']
        self.assertTrue(sig, 'les lignes de meme identifiant ne sont pas '
                             'signalees du tout')
        self.assertEqual(sig[0].regle, 3)
        self.assertEqual([a.code for a in r.exclusions], [],
                         'des lignes sont EXCLUES alors que rien ne permet de '
                         'trancher entre doublon et historique')
        self.assertEqual(r.lignes_retenues, r.lignes_initiales)
        print(f"    E2-3 sans echeance : {sig[0].nb_lignes} lignes signalees en "
              f"regle 3, {r.lignes_retenues}/{r.lignes_initiales} conservees, "
              f"0 exclusion")

    def test_le_message_dit_QUOI_FAIRE_pas_seulement_quoi(self):
        """⚠️ « Dire clairement ce qui n'a pas pu etre verifie » — et comment y
        remedier. Le motif nomme `echeance` ; sans lui l'actuaire lit un refus
        sans issue."""
        texte = synthese_qualite_donnees(_controler(_historique(), _PLAN_ID))
        self.assertIn('echeance', texte)
        self.assertIn('CONSERVEES', texte)
        self.assertIn('doublon_identifiant_sans_echeance', texte)
        print("    E2-4 le message porte le code, l'etat des lignes ET le "
              "remede (« declarer `echeance` »)")


class TestL_AvertissementAtteintLeRapportSANS_IA(unittest.TestCase):
    """Etape 3 — `services/C12`. La preuve se fait SANS CLE API."""

    def _resultat_a6(self, plan=_PLAN_ID):
        return {'rapport_qualite': _controler(_historique(), plan)}

    def test_LE_TEST_QUI_FERME_le_HTML_signe_le_porte_sans_cle(self):
        """⚠️⚠️ LA METHODE EXACTE QUI A DEMASQUE `services/C10` : on lit le
        livrable, pas la table des fonctions."""
        with _sans_cle():
            html = R.export_html({}, {}, self._resultat_a6(), 'DEMO',
                                 '31/12/2025', 'PUB')
        self.assertIn(R.TITRE_QUALITE_DONNEES, html,
                      "le bloc qualite est ABSENT du HTML signe : sans cle, "
                      "l'avertissement s'evapore comme dans `services/C10`")
        self.assertIn('doublon_identifiant_sans_echeance', html)
        self.assertIn('echeance', html)
        print("    E3-1 HTML signe SANS CLE : titre, code et remede presents")

    def test_le_WORD_signe_le_porte_aussi(self):
        """⚠️⚠️ LE WORD PART AU CAC COMME LE HTML. Corriger un seul des deux
        laisserait la moitie du livrable muette — la lecon est deja ecrite dans
        ce module pour l'avertissement DL."""
        with _sans_cle():
            blob = R.export_word({}, {}, self._resultat_a6(), 'DEMO',
                                 '31/12/2025', 'PUB')
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            xml = z.read('word/document.xml').decode('utf-8', 'replace')
        self.assertIn(R.TITRE_QUALITE_DONNEES, xml, 'absent du .docx signe')
        self.assertIn('doublon_identifiant_sans_echeance', xml)
        print("    E3-2 .docx signe SANS CLE : titre et code presents")

    def test_SECOND_SENS_rien_a_signaler_AUCUN_bloc(self):
        """⚠️⚠️ Un avertissement affiche TOUJOURS cesse d'etre un signal."""
        sain = _portefeuille_auto(300, seed=3).assign(
            id_contrat=[f'P{i:05d}' for i in range(300)])
        r6 = {'rapport_qualite': _controler(sain, _PLAN_ID)}
        self.assertEqual(R.avertissement_qualite(r6), '')
        self.assertEqual(R._bloc_qualite_html(R.avertissement_qualite(r6)), '')
        with _sans_cle():
            html = R.export_html({}, {}, r6, 'DEMO', '31/12/2025', 'PUB')
        self.assertNotIn(R.TITRE_QUALITE_DONNEES, html,
                         'un bloc qualite apparait alors qu il n y a rien a '
                         'dire')
        print("    E3-3 second sens : portefeuille sain -> aucun bloc, ni "
              "texte ni HTML")

    def test_le_texte_vient_de_la_SOURCE_UNIQUE_il_n_est_pas_reecrit(self):
        """⚠️ Une reformulation locale aurait diverge de l'Excel et du rapport
        d'equipe — les 30 definitions de couleurs avant `STATUT_RAG`."""
        rq = _controler(_historique(), _PLAN_ID)
        self.assertEqual(R.avertissement_qualite({'rapport_qualite': rq}),
                         synthese_qualite_donnees(rq),
                         'le service reecrit le texte au lieu de le lire')
        print("    E3-4 le texte est celui de `synthese_qualite_donnees`, "
              "caractere pour caractere")

    def test_RGPD_le_bloc_ne_publie_AUCUNE_valeur_client(self):
        """⚠️⚠️ NON NEGOCIABLE. Un role, une colonne, un compte."""
        sentinelle = 'P2024-00042'
        rq = _controler(_historique(), _PLAN_ID)
        with _sans_cle():
            html = R.export_html({}, {}, {'rapport_qualite': rq}, 'DEMO',
                                 '31/12/2025', 'PUB')
        bloc = R._bloc_qualite_html(
            R.avertissement_qualite({'rapport_qualite': rq}))
        self.assertNotIn(sentinelle, bloc, 'le bloc publie un identifiant client')
        self.assertNotIn(sentinelle, html, 'le HTML publie un identifiant client')
        print("    E3-5 RGPD : aucun identifiant client dans le bloc ni dans "
              "le HTML signe")


if __name__ == '__main__':
    unittest.main()
