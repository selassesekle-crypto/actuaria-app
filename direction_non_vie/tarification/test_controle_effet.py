"""CONTRÔLES POSITIFS DU LOT ② — `conformite/C1` + `conformite/C7`.

  `C1` — `controle_effet_execute` valait `True` alors que le contrôle n'avait
         examiné AUCUNE colonne. Il était calculé AVANT l'appel, sur la seule
         présence des arguments : `not (df is None or not cibles)`.
         `detecter_fuites_par_effet` renonçait en silence dans deux cas —
         cible absente du DataFrame, cible de variance nulle.
         **La propriété attestait la FOURNITURE DES ARGUMENTS, pas
         l'EXÉCUTION DU CONTRÔLE.**
  `C7` — cette même propriété portait « ⚠ À REMONTER DANS LES RAPPORTS »
         depuis l'audit V14. Mesuré : **aucun agent, aucun service, aucun
         livrable ne la lisait.**

⚠️⚠️ LE COUPLAGE EST L'OBJET DU LOT, ET IL EST ORIENTÉ.
Publier `C7` sans corriger `C1` aurait mis dans le livrable une attestation
**fausse** : « garde-fou n°4 exécuté » sur une matrice où il n'avait examiné
aucune colonne. `C1` est donc corrigé D'ABORD, dans le même changement.
`POS_Effet_LeCouplageEstVerrouille` lit le CLASSEUR PRODUIT — elle échoue si
l'on revient sur `C1`, comme si l'on débranchait `C7`.

⚠️ Tout se conclut PAR EXÉCUTION : on produit le classeur et on lit ses cellules.
"""
import io
import os
import sys
import unittest
from typing import ClassVar

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import numpy as np
import openpyxl
import pandas as pd

import core.conformite_reglementaire as C
from direction_non_vie.tarification.services.tarif_excel import export_excel_a6

_FEATURES = ['age', 'bonus_malus']


def _donnees(n=300, cible='variable'):
    """⚠️⚠️ LE TÉMOIN `vide` A MANQUÉ TROIS FOIS DANS LA MÊME JOURNÉE.

    Mes fixtures ne portaient que « cible ABSENTE de la table » et « cible
    CONSTANTE » — jamais **cible PRÉSENTE mais entièrement vide**. C'est ce
    trou précis qui a laissé passer `NaN == 0.0` (toujours faux), donc un
    contrôle par l'effet qui s'attestait exécuté sur une cible inexistante,
    **et le classeur du CAC écrivait « exécuté sur toutes les cibles »**.

    Les cinq états sont désormais dans la fixture, et chacun a son test.
    """
    rng = np.random.default_rng(1)
    df = pd.DataFrame({'age': rng.uniform(20, 70, n),
                       'bonus_malus': rng.uniform(50, 200, n)})
    if cible == 'variable':
        df['nb'] = rng.poisson(0.3, n).astype(float)
    elif cible == 'constante':
        df['nb'] = np.zeros(n)
    elif cible == 'vide':                     # présente, et entièrement NaN
        df['nb'] = np.nan
    elif cible == 'moitie_vide':              # couverture partielle
        df['nb'] = [np.nan if i % 2 else float(i % 7) for i in range(n)]
    # cible == 'absente' : la colonne n'est pas créée du tout
    return df


def _matrice(df, col_cible='nb', contexte='ctrl'):
    return C.construire_matrice_x(_FEATURES, contexte=contexte, df=df,
                                  col_cible=col_cible)


def _rapport(mx) -> dict:
    return {'execute': mx.controle_effet_execute,
            'motifs': mx.motifs_controle_effet}


def _classeur(controle_effet: dict) -> str:
    modele = {'modele': 'GBM', 'famille': 'GBM', 'gini_test': 0.21,
              'overfit_ratio': 1.07, 'score_global': 0.83, 'rmse_test': 12.3}
    res = {'success': True, 'branche': 'auto', 'statut_rag': 'VERT',
           'classement': [dict(modele, rang=1)], 'modele_production': modele,
           'backtest': {'disponible': True}, 'fiche_decision': {},
           'audit_trail': {}, 'validation_selection': {},
           'controle_effet': controle_effet}
    wb = openpyxl.load_workbook(io.BytesIO(export_excel_a6(res, audit_id='CTRL')))
    return "\n".join(str(c.value) for ws in wb.worksheets
                     for row in ws.iter_rows() for c in row
                     if c.value is not None)


class POS_Effet_C1_LaProprieteAtteste_L_EXECUTION(unittest.TestCase):
    """⚠️ `conformite/C1` — elle attestait la fourniture des arguments."""

    def test_les_trois_cas_muets_ne_sont_plus_attestes(self):
        cas = {
            'cible ABSENTE du df': (_donnees(cible='absente'), 'nb'),
            'cible CONSTANTE': (_donnees(cible='constante'), 'nb'),
            'df absent': (None, 'nb'),
        }
        for libelle, (df, cible) in cas.items():
            with self.subTest(cas=libelle):
                mx = _matrice(df, cible, libelle)
                self.assertFalse(
                    mx.controle_effet_execute,
                    f"[{libelle}] la matrice atteste un controle qui n'a "
                    f"examine AUCUNE colonne")
                self.assertTrue(
                    mx.motifs_controle_effet,
                    f"[{libelle}] aucun motif : l'actuaire saurait QUE, "
                    f"jamais POURQUOI")
        print(f"    POS-C1 les {len(cas)} cas muets ne sont plus attestes ✅")

    def test_LE_SECOND_SENS_un_controle_qui_TOURNE_est_bien_atteste(self):
        """⚠️⚠️ SANS LUI, UNE PROPRIÉTÉ FIGÉE À `False` PASSERAIT LES TROIS
        TESTS CI-DESSUS. Le garde-fou doit encore pouvoir dire qu'il a tourné."""
        mx = _matrice(_donnees(), 'nb')
        self.assertTrue(mx.controle_effet_execute,
                        "un controle qui a tourne se declare non execute")
        self.assertEqual(mx.motifs_controle_effet, {},
                         "un controle complet ne doit porter aucun motif")
        print("    POS-C1 LE SECOND SENS : un controle qui tourne est atteste ✅")

    def test_le_motif_NOMME_la_cause(self):
        """Un booléen dit QUE ; l'actuaire a besoin de POURQUOI."""
        for cible, mot in (('absente', 'ABSENTE'), ('constante', 'CONSTANTE')):
            with self.subTest(cas=cible):
                mx = _matrice(_donnees(cible=cible), 'nb')
                motifs = " ".join(mx.motifs_controle_effet.values())
                self.assertIn(mot, motifs)
        print("    POS-C1 le motif nomme la cause ✅")

    def test_le_WARNING_ne_se_contredit_PAS_lui_meme(self):
        """⚠️ Mon premier correctif annonçait « appelée SANS df et/ou SANS
        col_cible » alors que les DEUX étaient fournis — l'en-tête contredisait
        le motif qu'il portait. Le défaut de ce module, dans son correctif."""
        import logging as _lg
        journal = []

        class _Espion(_lg.Handler):
            def emit(self, record):
                journal.append(record.getMessage())

        log = _lg.getLogger('ctrl_effet_espion')
        log.setLevel(_lg.WARNING)
        log.addHandler(_Espion())
        try:
            _matrice(_donnees(cible='absente'), 'nb')
            C.construire_matrice_x(_FEATURES, contexte='espion',
                                   df=_donnees(cible='absente'),
                                   col_cible='nb', logger_agent=log)
        finally:
            log.handlers.clear()
        msg = " ".join(journal)
        self.assertIn("aucune cible exploitable", msg,
                      "le WARNING n'annonce pas la vraie cause")
        self.assertNotIn("SANS df et/ou SANS col_cible", msg,
                         "le WARNING affirme une cause FAUSSE : df et "
                         "col_cible ont bien ete fournis")
        print("    POS-C1 le WARNING annonce la vraie cause ✅")

    def test_une_cible_sur_deux_est_un_controle_PARTIEL_declare(self):
        """⚠️ L'agrégation ne doit pas arrondir au meilleur : A3 passe DEUX
        cibles, et l'une peut manquer."""
        mx = C.construire_matrice_x(_FEATURES, contexte='partiel',
                                    df=_donnees(), col_cible=['nb', 'absente'])
        self.assertTrue(mx.controle_effet_execute, "une cible valide suffit")
        self.assertIn('absente', mx.motifs_controle_effet,
                      "la cible non examinee n'est pas signalee")
        avert = C.avertissement_controle_effet(_rapport(mx))
        self.assertIsNotNone(avert)
        self.assertIn('PARTIEL', avert)
        print("    POS-C1 couverture partielle : declaree, pas arrondie ✅")


class POS_Effet_C7_LAvertissementATTEINTLeLivrable(unittest.TestCase):
    """⚠️ `conformite/C7` — la propriété n'atteignait aucun livrable."""

    def test_le_classeur_porte_l_avertissement_quand_le_controle_n_a_pas_tourne(self):
        txt = _classeur(_rapport(_matrice(None, 'nb')))
        self.assertIn("NON EXÉCUTÉ", txt,
                      "le classeur ne dit pas que le garde-fou n'a pas tourne")
        self.assertIn("aucun DataFrame", txt,
                      "le classeur ne publie pas le MOTIF")
        print("    POS-C7 le classeur porte l'avertissement ET son motif ✅")

    def test_LE_SECOND_SENS_rien_n_est_publie_quand_tout_va_bien(self):
        """⚠️ Un avertissement affiché en permanence ne serait plus un
        avertissement : l'actuaire cesserait de le lire."""
        txt = _classeur(_rapport(_matrice(_donnees(), 'nb')))
        self.assertNotIn("NON EXÉCUTÉ", txt)
        self.assertIn("exécuté sur toutes les cibles", txt,
                      "l'etat SAIN n'est pas publie non plus — l'actuaire ne "
                      "peut pas distinguer « tout va bien » de « rien n'a ete "
                      "verifie »")
        print("    POS-C7 LE SECOND SENS : etat sain publie, pas d'alarme ✅")


class POS_Effet_LeCouplageEstVerrouille(unittest.TestCase):
    """⚠️⚠️ `C7` NE PEUT PAS ÊTRE PUBLIÉ SI `C1` N'EST PAS VRAI.

    Ce test lit le CLASSEUR PRODUIT, pas la propriété : il échoue si l'on
    revient sur `C1` (la propriété redeviendrait `True` à tort et le classeur
    attesterait un contrôle jamais exécuté), comme si l'on débranchait `C7`.
    """

    def test_le_classeur_n_atteste_JAMAIS_un_controle_qui_n_a_rien_examine(self):
        for libelle, df, cible in (
            ('df absent', None, 'nb'),
            ('cible absente', _donnees(cible='absente'), 'nb'),
            ('cible constante', _donnees(cible='constante'), 'nb'),
        ):
            with self.subTest(cas=libelle):
                txt = _classeur(_rapport(_matrice(df, cible, libelle)))
                self.assertNotIn(
                    "exécuté sur toutes les cibles", txt,
                    f"[{libelle}] LE CLASSEUR ATTESTE un controle anti-fuite "
                    f"qui n'a examine AUCUNE colonne — c'est le constat C1 "
                    f"publie, donc pire qu'avant")
        print("    POS-couplage le classeur n'atteste jamais a tort ✅")

    def test_la_source_unique_est_la_MEME_pour_les_deux_sorties_muettes(self):
        """⚠️ `detecter_fuites_par_effet` et `construire_matrice_x` doivent
        consulter LA MÊME fonction. Deux tests séparés se désynchroniseraient —
        c'est la maladie que ce module existe pour supprimer."""
        for cible in ('absente', 'constante'):
            with self.subTest(cas=cible):
                df = _donnees(cible=cible)
                self.assertIsNotNone(
                    C.motif_controle_effet_impossible(df, 'nb'),
                    "la source unique ne voit pas ce cas")
                self.assertEqual(
                    C.detecter_fuites_par_effet(df, _FEATURES, 'nb'), {},
                    "la detection ne renonce pas sur ce cas")
                self.assertFalse(_matrice(df, 'nb').controle_effet_execute,
                                 "la matrice atteste malgre le renoncement")
        print("    POS-couplage une seule source pour les deux sorties ✅")


class POS_Effet_L_AgregationD_A6_NeMasqueRien(unittest.TestCase):
    """⚠️⚠️ CETTE CLASSE N'EXISTAIT PAS, ET C'EST SELASSE QUI L'A DEMANDÉE.

    J'affirmais dans mon rapport « A6 agrège par le pire » — **sans aucun test
    nommé pour l'appuyer**, contrairement au reste du lot. *Une affirmation sans
    mesure est exactement ce que cet audit poursuit ; je l'avais écrite.*

    Et la mesure a trouvé un défaut que je n'avais pas vu : l'agrégat était clé
    par CIBLE seule, si bien que **deux agents en échec sur la même cible
    s'écrasaient l'un l'autre — un motif sur deux disparaissait.**
    """

    SAIN: ClassVar[dict] = {'execute': True, 'motifs': {}}

    def test_UN_agent_en_echec_suffit_a_declarer_la_protection_incomplete(self):
        """Le cas demandé : A3 en échec, A4 et A5 sains."""
        r = C.agreger_controle_effet({
            'A3': {'execute': False, 'motifs': {'nb': 'cible nb ABSENTE'}},
            'A4': self.SAIN, 'A5': self.SAIN})
        self.assertFalse(r['execute'],
                         "A3 en echec et l'agregat declare la protection "
                         "complete — l'agregat MASQUE")
        self.assertTrue(r['motifs'], "le motif d'A3 est perdu")
        self.assertIn('A3', " ".join(r['motifs']),
                      "le motif ne nomme pas l'agent concerne")
        avert = C.avertissement_controle_effet(r)
        self.assertIn("NON EXÉCUTÉ", avert or "")
        print("    POS-agregat un seul agent en echec -> protection incomplete ✅")

    def test_DEUX_agents_en_echec_sur_la_MEME_cible_gardent_LEURS_DEUX_motifs(self):
        """⚠️ LE DÉFAUT QUE LA QUESTION A TROUVÉ. Clés par cible seule, le
        second `update()` écrasait le premier."""
        r = C.agreger_controle_effet({
            'A3': {'execute': False, 'motifs': {'nb': 'cible nb ABSENTE'}},
            'A4': self.SAIN,
            'A5': {'execute': False, 'motifs': {'nb': 'cible nb CONSTANTE'}}})
        self.assertEqual(
            len(r['motifs']), 2,
            f"un motif a ete ECRASE : {r['motifs']} — l'actuaire perd une des "
            f"deux causes")
        joint = " ".join(r['motifs'])
        for agent in ('A3', 'A5'):
            self.assertIn(agent, joint, f"le motif d'{agent} a disparu")
        print("    POS-agregat deux echecs sur la meme cible : 2 motifs gardes ✅")

    def test_LE_SECOND_SENS_trois_agents_sains_n_alertent_PAS(self):
        """⚠️ Sans lui, un agrégat figé à `False` passerait les deux tests
        ci-dessus en n'ayant rien mesuré."""
        r = C.agreger_controle_effet({'A3': self.SAIN, 'A4': self.SAIN,
                                      'A5': self.SAIN})
        self.assertTrue(r['execute'])
        self.assertEqual(r['motifs'], {})
        self.assertIsNone(C.avertissement_controle_effet(r))
        print("    POS-agregat LE SECOND SENS : trois agents sains, rien ✅")

    def test_aucune_source_renseignee_n_atteste_RIEN(self):
        """Le silence ne vaut jamais accord pour un garde-fou."""
        for sources in ({}, {'A3': None, 'A4': None, 'A5': None}):
            with self.subTest(sources=sources):
                r = C.agreger_controle_effet(sources)
                self.assertFalse(r['execute'],
                                 "aucune information et l'agregat atteste")
        print("    POS-agregat aucune source -> rien n'est atteste ✅")


class POS_Effet_LeCouplageTientDANS_LES_DEUX_SENS(unittest.TestCase):
    """⚠️⚠️ MESURÉ SUR DEMANDE DE SELASSE — je n'avais montré qu'un sens.

    Le couplage doit tenir que l'on annule `C1` (la propriété redevient `True`
    à tort) OU que l'on débranche `C7` (l'avertissement n'est plus publié).
    Ce test PLANTE la seconde violation et vérifie qu'elle est attrapée.
    """

    def test_C7_debranche_SEUL_est_attrape(self):
        """⚠️ Violation plantée : la source unique du texte est neutralisée,
        `C1` reste intact. Le classeur bascule alors sur « exécuté sur toutes
        les cibles » — il ATTESTE un contrôle qui n'a rien examiné."""
        import direction_non_vie.tarification.services.tarif_excel as TE
        original = TE.avertissement_controle_effet
        TE.avertissement_controle_effet = lambda rapport: None
        try:
            txt = _classeur(_rapport(_matrice(None, 'nb')))
        finally:
            TE.avertissement_controle_effet = original
        self.assertIn(
            "exécuté sur toutes les cibles", txt,
            "la violation n'a pas ete plantee : le classeur ne bascule pas")
        # C'est très exactement ce que le contrôle du couplage interdit.
        self.assertNotIn("NON EXÉCUTÉ", txt)
        print("    POS-couplage C7 debranche SEUL : la violation est visible ✅")

    def test_et_le_controle_du_couplage_ECHOUE_sur_cette_violation(self):
        """⚠️ Le sens qui compte : ce n'est pas assez que la violation soit
        visible, il faut qu'un contrôle la REFUSE."""
        import direction_non_vie.tarification.services.tarif_excel as TE
        original = TE.avertissement_controle_effet
        TE.avertissement_controle_effet = lambda rapport: None
        try:
            with self.assertRaises(AssertionError):
                POS_Effet_LeCouplageEstVerrouille(
                    'test_le_classeur_n_atteste_JAMAIS_un_controle_qui_n_a_rien_examine'
                ).test_le_classeur_n_atteste_JAMAIS_un_controle_qui_n_a_rien_examine()
        finally:
            TE.avertissement_controle_effet = original
        print("    POS-couplage le controle REFUSE C7 debranche ✅")


class POS_Effet_UneCibleVIDE_NeSAttestePas(unittest.TestCase):
    """⚠️⚠️ LE TROU QUE SELASSE A TROUVÉ, ET QUI M'A ÉCHAPPÉ TROIS FOIS.

    Le garde testait `float(serie.std()) == 0.0`. Sur une colonne entièrement
    vide, `std()` vaut **NaN**, et **`NaN == 0.0` est FAUX** : aucun motif,
    `controle_effet_execute = True`, et le classeur qui part au CAC écrivait
    « exécuté sur toutes les cibles » **sur une cible qui n'existe pas**.

    ⚠️ C'est `qualite/C1` — l'aveuglement au NaN — reproduit dans la correction
    de `conformite/C1`, qui portait précisément sur un contrôle qui s'atteste
    sans avoir rien examiné. *On ne teste jamais une borne sur des données qui
    peuvent manquer : on teste ce qui RESTE.*
    """

    def test_une_cible_PRESENTE_mais_VIDE_n_est_pas_attestee(self):
        mx = _matrice(_donnees(cible='vide'), 'nb')
        self.assertFalse(
            mx.controle_effet_execute,
            "une cible entierement vide et le controle se declare execute")
        motif = " ".join(mx.motifs_controle_effet.values())
        self.assertIn("ENTIÈREMENT", motif,
                      "le motif ne nomme pas la vraie cause")
        print("    POS-vide une cible presente et VIDE n'est pas attestee ✅")

    def test_le_CLASSEUR_ne_l_atteste_pas_non_plus(self):
        """⚠️ Le sens qui compte : le défaut atteignait le LIVRABLE."""
        txt = _classeur(_rapport(_matrice(_donnees(cible='vide'), 'nb')))
        self.assertIn("NON EXÉCUTÉ", txt)
        self.assertNotIn("exécuté sur toutes les cibles", txt,
                         "LE CLASSEUR ATTESTE un controle sur une cible vide")
        print("    POS-vide le classeur ne l'atteste pas non plus ✅")

    def test_une_couverture_PARTIELLE_est_DECLAREE_pas_arrondie(self):
        """⚠️⚠️ NI AU PIRE, NI AU MIEUX. Une cible à moitié vide laissait le
        contrôle tourner sur la moitié des lignes **sans le dire**. L'arrondir
        au pire ferait croire que rien n'a été vérifié ; au mieux, que tout
        l'a été. *Une couverture partielle est un fait à publier.*"""
        mx = _matrice(_donnees(cible='moitie_vide'), 'nb')
        self.assertTrue(mx.controle_effet_execute,
                        "le controle a bien tourne : il ne doit pas etre "
                        "declare non execute")
        motif = " ".join(mx.motifs_controle_effet.values())
        self.assertIn("INCOMPLÈTE", motif, "la reserve n'est pas publiee")
        txt = _classeur(_rapport(mx))
        self.assertIn("PARTIEL", txt, "le classeur n'annonce pas le partiel")
        self.assertNotIn("exécuté sur toutes les cibles", txt)
        print("    POS-vide couverture partielle : DECLAREE, pas arrondie ✅")

    def test_LE_SECOND_SENS_une_cible_PLEINE_reste_attestee_sans_reserve(self):
        """⚠️ Sans lui, une réserve émise sur tout portefeuille rendrait
        l'avertissement permanent — donc illisible."""
        mx = _matrice(_donnees(), 'nb')
        self.assertTrue(mx.controle_effet_execute)
        self.assertEqual(mx.motifs_controle_effet, {},
                         "une cible pleine porte une reserve")
        self.assertIn("exécuté sur toutes les cibles",
                      _classeur(_rapport(mx)))
        print("    POS-vide LE SECOND SENS : une cible pleine, aucune reserve ✅")

    def test_les_CINQ_etats_de_la_fixture_sont_distincts(self):
        """⚠️ Le témoin manquant est la cause de ce défaut : on épingle donc
        la fixture elle-même, pour qu'aucun état ne disparaisse en silence."""
        attendus = {
            'variable':    (True,  ''),
            'moitie_vide': (True,  'INCOMPLÈTE'),
            'vide':        (False, 'ENTIÈREMENT'),
            'constante':   (False, 'CONSTANTE'),
            'absente':     (False, 'ABSENTE'),
        }
        for etat, (execute, mot) in attendus.items():
            with self.subTest(etat=etat):
                mx = _matrice(_donnees(cible=etat), 'nb')
                self.assertEqual(mx.controle_effet_execute, execute)
                if mot:
                    self.assertIn(mot,
                                  " ".join(mx.motifs_controle_effet.values()))
        print(f"    POS-vide les {len(attendus)} etats de cible sont distincts ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
