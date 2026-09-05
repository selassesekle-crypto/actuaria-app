# -*- coding: utf-8 -*-
"""A1 DEVINAIT L'IDENTITE DU CONTRAT, ET NE LE DISAIT A PERSONNE (A1.5).

A1 calcule `source_identifiant` (`plan` / `devinee` / `aucune`),
`note_identite` et `granularite` depuis le 24/08. Mesure du 05/09/2026 :
**seuls des tests les lisaient**. Le classeur A1 signe publiait
<< Nb doublons >> et << Taux doublons >> sans jamais dire SUR QUELLE CLE le
compte portait -- alors que le titre du bloc annonce, lui,
<< lisibilite, completude, IDENTITE >>.

  *Un calcul qui n'atteint aucun livrable n'existe pas ; et un titre qui
  annonce plus que son bloc ne porte est une dette.*

⚠️⚠️ ET LE MOTIF DU REPLI A CHANGE, CE QUI CHANGE LE CONSTAT. Le code disait
<< aucun des vingt plans ne declare d'identifiant >> : re-mesure le
05/09/2026, **les vingt declarent `identifiant_contrat` ET `echeance`**. Le
repli ne vient donc plus d'un plan incomplet -- il vient de ce qu'**aucun
appelant de production ne passe le plan a `A1.run`** (releve par AST :
`pipeline_agents.py:346`, les demos, les scripts). *L'information existe, elle
n'atteint pas l'agent qui en a besoin.*

⚠️⚠️ LE CABLAGE N'EST PAS FAIT, ET C'EST DELIBERE. Passer le plan ferait
dedoublonner sur (identifiant, echeance) au lieu du seul identifiant : mesure
portee par l'arbre de decision -- sur un historique de renouvellement de 200
contrats sur 3 exercices, **400 faux doublons (66,7 %) et statut ROUGE sans le
plan, contre 0 et VERT avec**. Cela change les lignes retenues, donc le
modele, donc le prix. **C'est une decision, pas un correctif.** Ce lot rend le
fait VISIBLE ; il ne le tranche pas.

⚠️ ET LE STATUT N'EST PAS PLAFONNE, POUR UNE RAISON MESUREE. Aucun appelant de
production ne passant le plan, plafonner mettrait TOUS les fichiers en AMBRE :
*un avertissement permanent est un avertissement qu'on cesse de lire* -- le
meme principe qui gouverne `phrase_unite_non_declaree`. Le badge de la LIGNE
d'identite, lui, suit la source.

Ce que cette sentinelle exige :
  ID-1  la note d'identite atteint le classeur A1 SIGNE ;
  ID-2  son badge suit la SOURCE : declaree -> VERT, devinee -> AMBRE ;
  ID-3  la granularite du dedoublonnage est publiee ;
  ID-4  second sens : plan transmis -> plus aucune mention de << devinee >> ;
  ID-5  la note DIT quoi faire, et ne se contredit pas avec le referentiel.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""
import io
import logging
import os
import sys
import unittest
import warnings

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

import numpy as np


def _run_a1(**kwargs):
    from direction_non_vie.tarification import test_pipeline_agents as T
    from direction_non_vie.tarification.a1_ingestion.agent import (
        AgentA1Ingestion,
    )
    np.random.seed(7)
    return AgentA1Ingestion(audit_path='/tmp', verbose=False).run(
        branche='non_vie', sous_branche='auto',
        dataframe=T._portefeuille_auto(900), **kwargs)


def _texte_classeur(result_a1):
    from openpyxl import load_workbook
    octets = result_a1.get('excel_bytes') or b''
    if not octets:
        return ''
    classeur = load_workbook(io.BytesIO(octets), data_only=True)
    return '\n'.join(str(c.value) for f in classeur.worksheets
                     for ligne in f.iter_rows() for c in ligne
                     if c.value is not None)


class TestLIdentiteAtteintLeClasseur(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)
        from direction_non_vie.tarification import test_pipeline_agents as T
        cls.sans = _run_a1()                      # le cas de PRODUCTION
        cls.avec = _run_a1(plan=T._PLAN_AUTO)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_ID1_la_note_d_identite_atteint_le_classeur_SIGNE(self):
        """⚠️⚠️ *Un calcul qui n'atteint aucun livrable n'existe pas.*"""
        qualite = self.sans.get('qualite') or {}
        self.assertEqual(qualite.get('source_identifiant'), 'devinee',
                         "sans plan, A1 devrait DEVINER l'identite : ce test "
                         'ne mesure plus le bon chemin')
        texte = _texte_classeur(self.sans)
        self.assertTrue(texte, 'aucun classeur A1')
        self.assertIn('Identité du contrat', texte,
                      "le classeur publie un compte de doublons sans dire sur "
                      'quelle CLE il porte')
        self.assertIn('DEVINÉE', texte)

    def test_ID2_le_badge_suit_la_SOURCE_pas_le_compte(self):
        """⚠️ Une identite DECLAREE n'est pas un fait a verifier ; une
        identite DEVINEE en est un. Le badge doit distinguer les deux."""
        from openpyxl import load_workbook
        for resultat, attendu in ((self.sans, 'devinee'), (self.avec, 'plan')):
            with self.subTest(source=attendu):
                qualite = resultat.get('qualite') or {}
                self.assertEqual(qualite.get('source_identifiant'), attendu)
                classeur = load_workbook(
                    io.BytesIO(resultat['excel_bytes']), data_only=True)
                trouve = None
                for feuille in classeur.worksheets:
                    for ligne in feuille.iter_rows():
                        for cellule in ligne:
                            if str(cellule.value or '').startswith(
                                    'Identité du contrat'):
                                trouve = feuille.cell(row=cellule.row,
                                                      column=3).value
                self.assertIsNotNone(
                    trouve, "la ligne d'identite n'est pas dans le classeur")
                # ⚠️⚠️ L'ATTENDU EST LE MOT PUBLIE, PAS LE CODE INTERNE.
                # `_kpi` rend « ✓ Conforme » / « △ À surveiller » -- c'est ce
                # que l'actuaire LIT. Et il se DERIVE de sa source unique
                # (`_MOT_RAG`, `GLYPHE_RAG_EXCEL`) : le recopier ici en
                # creerait une seconde, qui divergerait le jour ou la charte
                # change. *Mon premier attendu etait `VERT` -- le classeur ne
                # l'ecrit nulle part.*
                from direction_non_vie.tarification.services.excel_helpers import (
                    MOT_RAG,
                )
                code = 'VERT' if attendu == 'plan' else 'AMBRE'
                self.assertIn(
                    MOT_RAG[code], str(trouve),
                    f"identite {attendu} : le badge publie est {trouve!r}, "
                    f"attendu un badge {code}")

    def test_ID3_la_granularite_du_dedoublonnage_est_publiee(self):
        for resultat in (self.sans, self.avec):
            with self.subTest():
                self.assertIn('Granularité déclarée',
                              _texte_classeur(resultat))
                self.assertTrue((resultat.get('qualite') or {})
                                .get('granularite'))

    def test_ID4_SECOND_SENS_plan_transmis_plus_aucune_mention_devinee(self):
        """⚠️ Sans ce sens, on aurait pu ecrire << DEVINEE >> en dur."""
        texte = _texte_classeur(self.avec)
        self.assertNotIn('DEVINÉE', texte,
                         "le plan est transmis et le classeur dit encore que "
                         "l'identite est devinee")
        self.assertIn('DÉCLARÉE au plan', texte)

    def test_ID5_la_note_dit_QUOI_FAIRE_et_ne_ment_pas_sur_le_referentiel(self):
        """⚠️⚠️ LE TEXTE SE RELIT QUAND LE FAIT CHANGE. La note disait
        << Non declaree au plan >> ; re-mesure le 05/09/2026, **les vingt
        plans declarent `identifiant_contrat` ET `echeance`**. Le repli ne
        vient donc pas d'un plan incomplet mais d'un plan NON TRANSMIS --
        affirmer le contraire enverrait l'actuaire corriger un fichier qui
        n'a rien."""
        note = (self.sans.get('qualite') or {}).get('note_identite') or ''
        self.assertIn('DEVINÉE', note)
        self.assertIn("n'a pas été transmis", note,
                      'la note attribue le repli au plan alors que le plan '
                      'porte deja l information')
        self.assertIn('échéance', note.lower() + note)


class TestLeReferentielPorteBienLInformation(unittest.TestCase):
    """⚠️ Ce test FIGE la mesure sur laquelle repose la note ci-dessus. Le
    jour ou un plan cesse de declarer son identifiant, la note redevient
    fausse -- et c'est ici qu'on l'apprend."""

    def test_ID6_les_vingt_plans_declarent_identifiant_ET_echeance(self):
        import pathlib

        import yaml
        racine = pathlib.Path(_RACINE)
        lus = sans_id = sans_ech = 0
        manquants = []
        illisibles = []
        for fichier in sorted(racine.rglob('*.y*ml')):
            chemin = fichier.as_posix()
            if '.venv' in chemin or 'plan' not in chemin.lower():
                continue
            try:
                contenu = yaml.safe_load(fichier.read_text(encoding='utf-8'))
            except Exception as erreur:                      # noqa: BLE001
                # ⚠️⚠️ UN PLAN ILLISIBLE NE S'IGNORE PAS. Ma premiere version
                # faisait `except: continue` : un YAML casse aurait fait
                # BAISSER le compte de plans, donc rendu ce controle plus
                # facile a satisfaire. *Un test qui avale l'erreur qu'il
                # devrait voir se rend lui-meme complaisant.*
                illisibles.append(f'{chemin} ({type(erreur).__name__})')
                continue
            if not isinstance(contenu, dict) or 'cible_frequence' not in contenu:
                continue
            lus += 1
            if not contenu.get('identifiant_contrat'):
                sans_id += 1
                manquants.append(f"{contenu.get('lob', fichier.stem)}:id")
            if not contenu.get('echeance'):
                sans_ech += 1
                manquants.append(f"{contenu.get('lob', fichier.stem)}:echeance")
        self.assertEqual(illisibles, [],
                         'des fichiers de plan sont illisibles : le compte '
                         'de plans ci-dessous est donc incomplet')
        self.assertGreaterEqual(lus, 20, 'le referentiel de plans a retreci')
        self.assertEqual(
            manquants, [],
            f"{sans_id} plan(s) sans `identifiant_contrat` et {sans_ech} sans "
            f"`echeance` : la note d'identite d'A1 affirme que les vingt les "
            f"declarent. Corrigez le plan, ou corrigez la note.")


if __name__ == '__main__':
    unittest.main(verbosity=2)
