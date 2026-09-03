# -*- coding: utf-8 -*-
"""
=============================================================================
  ANTI-SELECTION ET RESERVE DE GINI -- deux situations, deux traitements
=============================================================================

ARBITRAGE DE SELASSE, 03/09/2026, sur la suite laissee en suspens par
`a3/C6` :

  Gini MESURE et NEGATIF  -> le modele discrimine A L'ENVERS. Ce n'est pas
      une question de performance mais de VALIDITE : il fait payer MOINS les
      mauvais risques. **Le statut d'A3 passe ROUGE**, que le modele soit
      retenu en production ou non, avec la RAISON publiee.

  Gini NON MESURABLE (`None`) -> on ne sait pas. **Cela ne colore RIEN.**
      Une RESERVE est publiee, nommant ce qui n'a pas pu etre mesure.

  *Une absence de mesure se declare ; elle ne se convertit pas en verdict.*

-----------------------------------------------------------------------------
LE TROU QUE CE LOT FERME, ET IL EST MESURE
-----------------------------------------------------------------------------
A6 force deja ROUGE sur un Gini negatif -- mais SEULEMENT pour le modele de
PRODUCTION (`a6_comparaison/agent.py`, la regle anti-selection ne lit que le
modele retenu). Et le statut d'A3 ne lisait que le Gini du POISSON, qui ne
concourt meme pas : sur la cible par defaut `prime_pure`, A6 ecarte le
Poisson (frequence) et le Gamma (cout moyen) par filtre de cible, et seul le
TWEEDIE reste candidat.

  Un GLM anti-selectif battu par un modele ML etait donc journalise par
  `_calculer_gini`, et publie dans AUCUN statut.

-----------------------------------------------------------------------------
CE QUI RESTE OUVERT, ET C'EST DIT
-----------------------------------------------------------------------------
`_calculer_gini` fabrique encore `0.0` dans trois branches non mesurables
(tableau vide, somme de sinistres nulle -- branche commentee << Gini
incalculable >> --, et son propre `except`). La racine n'est PAS traitee ici :
A6 arbitre le modele de production sur le Gini, et changer ces zeros
deplacerait le modele retenu, donc le tarif. Selasse a demande le chiffre
avant tout code dessus.
=============================================================================
"""

import io
import unittest
import zipfile

from core.conformite_reglementaire import (
    GINI_ABSENT,
    GINI_NON_MESURE,
    etats_gini,
    modeles_anti_selectifs,
    statut_anti_selection,
    synthese_anti_selection,
    synthese_gini_non_mesure,
)
from direction_non_vie.tarification.services import rapport_equipe_tarif as RE

_SAIN = {'poisson': {'gini': 0.22}, 'gamma': {'gini': 0.11},
         'tweedie': {'gini': 0.15}}
_ANTI = {'poisson': {'gini': 0.22}, 'gamma': {'gini': 0.11},
         'tweedie': {'gini': -0.078}}
_NON_MESURE = {'poisson': {'gini': 0.22}, 'gamma': {'gini': 0.11},
               'tweedie': {'gini': None}}
_LES_DEUX = {'poisson': {'gini': -0.30}, 'gamma': {'gini': 0.11},
             'tweedie': {'gini': None}}


def _texte_docx(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return z.read('word/document.xml').decode('utf-8')


def _texte_xlsx(blob: bytes) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(blob))
    return '\n'.join(str(c.value) for ws in wb.worksheets
                     for row in ws.iter_rows() for c in row
                     if c.value is not None)


def _r6(synth: dict) -> dict:
    """Un result_a6 minimal, avec les syntheses DEJA calculees (voie b)."""
    return {'success': True, 'statut_rag': 'AMBRE', 'branche': 'auto',
            'modele_production': {'modele': 'GLM'}, 'backtest': {},
            'audit_trail': {}, 'classement': [], 'metriques': {}, **synth}


class T1_LesDeuxSituationsNeSeConfondentPas(unittest.TestCase):

    def test_as_1_un_gini_negatif_force_ROUGE_depuis_tout_statut(self):
        """AS-1 : ce n'est pas un plafond, c'est un plancher inverse.

        `plafonner_statut_si_ampute` ramene VERT a AMBRE ; ici on force ROUGE
        depuis n'importe ou. Un modele anti-selectif n'est pas << moins
        bon >>, il organise l'anti-selection.
        """
        for depart in ('VERT', 'AMBRE', 'ROUGE'):
            with self.subTest(depart=depart):
                self.assertEqual(
                    statut_anti_selection(depart, _ANTI), 'ROUGE')
        self.assertEqual(statut_anti_selection('VERT', _SAIN), 'VERT')

    def test_as_2_un_gini_non_mesurable_ne_colore_RIEN(self):
        """AS-2 : L'AUTRE MOITIE DE L'ARBITRAGE, et la plus facile a trahir.

        Degrader sur un `None` confondrait << pas pu mesurer >> avec
        << mesure et mauvais >> -- la confusion meme que `a3/C6` a supprimee
        en remplacant le zero fabrique par `None`.
        """
        for depart in ('VERT', 'AMBRE', 'ROUGE'):
            with self.subTest(depart=depart):
                self.assertEqual(
                    statut_anti_selection(depart, _NON_MESURE), depart,
                    "un Gini non mesurable a deplace le statut")
        self.assertEqual(modeles_anti_selectifs(_NON_MESURE), [])

    def test_as_3_trois_etats_distincts_valeur_absent_non_mesure(self):
        """AS-3 : un modele ABSENT n'est ni une reserve ni une anti-selection.

        Les confondre est la racine du defaut ferme par `a3/C6` : un modele
        jamais ajuste et un modele dont le Gini n'a pas pu etre calcule ne se
        disent pas pareil, et aucun des deux ne vaut zero.
        """
        etats = etats_gini({'poisson': {'gini': 0.2}, 'gamma': {'gini': None}})
        self.assertEqual(etats['poisson'], 0.2)
        self.assertEqual(etats['gamma'], GINI_NON_MESURE)
        self.assertEqual(etats['tweedie'], GINI_ABSENT)
        # un modele ABSENT ne declenche NI reserve NI anti-selection
        sans_tweedie = {'poisson': {'gini': 0.2}, 'gamma': {'gini': 0.1}}
        self.assertIsNone(synthese_gini_non_mesure(sans_tweedie))
        self.assertIsNone(synthese_anti_selection(sans_tweedie))

    def test_as_4_les_deux_se_composent_sans_se_confondre(self):
        """AS-4 : un portefeuille peut porter les DEUX a la fois."""
        self.assertEqual(statut_anti_selection('VERT', _LES_DEUX), 'ROUGE')
        raison = synthese_anti_selection(_LES_DEUX)
        reserve = synthese_gini_non_mesure(_LES_DEUX)
        self.assertIn('poisson', raison, "la raison ne nomme pas le fautif")
        self.assertNotIn('tweedie', raison,
                         "le modele NON MESURE est accuse d'anti-selection")
        self.assertIn('tweedie', reserve)
        self.assertNotIn('poisson', reserve.split('NON MESURÉ pour :')[1]
                         .split('.')[0])


class T2_CeQuiEstPublie(unittest.TestCase):

    def test_as_5_la_raison_NOMME_le_modele_et_sa_valeur(self):
        """AS-5 : un ROUGE sans sa cause fait chercher au mauvais endroit.

        C'est le defaut que `services/C7` a ferme pour le plafond AMBRE.
        """
        raison = synthese_anti_selection(_ANTI)
        self.assertIsNotNone(raison)
        self.assertIn('tweedie', raison)
        self.assertIn('0,0780', raison, f"la valeur n'est pas citee : {raison}")
        self.assertIn('ROUGE', raison)
        self.assertIsNone(synthese_anti_selection(_SAIN),
                          "une raison est publiee alors que rien ne cloche")

    def test_as_6_la_reserve_NE_JUGE_PAS(self):
        """AS-6 : elle declare, elle ne conclut pas.

        ⚠️ Le controle porte sur ce qu'elle NE dit PAS : aucun mot de verdict.
        Une reserve qui glisserait vers le jugement redonnerait au `None` le
        role du zero fabrique.
        """
        reserve = synthese_gini_non_mesure(_NON_MESURE)
        self.assertIsNotNone(reserve)
        self.assertIn('tweedie', reserve)
        for verdict in ('AMBRE', 'ROUGE', 'insuffisant', 'mauvais',
                        'degrade', 'dégradé'):
            self.assertNotIn(
                verdict, reserve,
                f"la reserve porte un jugement (« {verdict} ») : elle doit "
                f"DECLARER l'absence, pas la convertir en verdict")
        self.assertIn('ÉCARTE', reserve,
                      "la reserve ne dit pas ce que l'absence COUTE (A6 "
                      "ecarte le modele non note de l'arbitrage)")
        self.assertIsNone(synthese_gini_non_mesure(_SAIN))


class T3_LaChaineAtteintLesLivrables(unittest.TestCase):
    """⚠️⚠️ << PUBLIEE >> SE VERIFIE PAR EXECUTION, JAMAIS PAR LECTURE.

    A3 rend -> A6 relaie -> `syntheses_reglementaires` -> html/word/excel.
    C'est le chemin qui manquait a `socle/C9`.
    """

    def test_sy_1_les_deux_syntheses_atteignent_les_TROIS_formats(self):
        """SY-1 : le maillon final, mesure sur les sorties reelles."""
        cas = (('anti_selection', synthese_anti_selection(_ANTI),
                "ANTI-SÉLECTION"),
               ('reserve_gini', synthese_gini_non_mesure(_NON_MESURE),
                "Gini NON MESURÉ"))
        for cle, valeur, ancre in cas:
            self.assertIsNotNone(valeur, f'{cle} : rien a publier')
            res = {'a6': _r6({})}
            synth = {cle: valeur}
            sorties = (
                ('html', RE.export_html_equipe(res, syntheses=synth)),
                ('word', _texte_docx(
                    RE.export_word_equipe(res, syntheses=synth))),
                ('excel', _texte_xlsx(
                    RE.export_excel_equipe(res, syntheses=synth))),
            )
            for nom, txt in sorties:
                with self.subTest(cle=cle, format=nom):
                    self.assertIn(
                        ancre, txt,
                        f"« {cle} » n'atteint pas le format {nom}")

    def test_sy_2_les_deux_cles_ont_un_LIBELLE(self):
        """SY-2 : le piege `CF-9`.

        Le html et le word iterent `_LABELS_SYNTHESES` : une cle SANS libelle
        est rendue NULLE PART, en silence, dans les formats qui partent au
        CAC.
        """
        libelles = dict(RE._LABELS_SYNTHESES)
        for cle in ('anti_selection', 'reserve_gini'):
            with self.subTest(cle=cle):
                self.assertIn(cle, libelles)
                self.assertTrue(libelles[cle].strip())

    def test_sy_3_la_couverture_EXCEL_est_epinglee_et_ses_trous_NOMMES(self):
        """SY-3 : L'ASSIETTE. L'Excel ne parcourt PAS `_LABELS_SYNTHESES`.

        ⚠️⚠️ Il code UN BLOC A LA MAIN par cle, quand le html et le word
        iterent le tuple. Une cle nouvelle atteint donc automatiquement deux
        formats sur trois, et le troisieme reste muet EN SILENCE.

        ⛔ TROIS TROUS ETAIENT NOMMES ICI (`plan_ecarte`, `exempt_effet`,
        `plafond`). **COMBLES le 03/09/2026 (soir)** : l'Excel d'equipe porte
        un FILET qui rend toute cle qu'aucun bloc a la main n'a prise.

        ⚠️⚠️ ET CE CONTROLE A TIRE POUR L'EXIGER -- APRES `RA-5`, QUI PORTAIT
        LA MEME LISTE. Deux controles epinglaient les memes trous ; j'ai mis
        a jour le premier et oublie celui-ci. La gate est passee ROUGE sur
        << ces trous connus sont COMBLES >>.

          *Une liste dupliquee dans deux controles ne se met a jour qu'a
          moitie : c'est le second qui reste faux, et il tire.*

        La liste est desormais VIDE ici comme dans `RA-5`. `CS-1` et `CS-2`
        (test_couverture_syntheses) tiennent la couverture et le MECANISME.
        """
        connus_manquants: set = set()
        res = {'a6': _r6({})}
        manquants = set()
        for cle, _ in RE._LABELS_SYNTHESES:
            temoin = f'ZZ{cle.upper().replace("_", "")}ZZ'
            txt = _texte_xlsx(
                RE.export_excel_equipe(res, syntheses={cle: temoin}))
            if temoin not in txt:
                manquants.add(cle)
        nouveaux = manquants - connus_manquants
        self.assertFalse(
            nouveaux,
            f"ces cles de synthese n'atteignent PAS l'Excel equipe et ce lot "
            f"n'en avait pas connaissance : {sorted(nouveaux)}. L'Excel code "
            f"un bloc par cle -- ajouter une cle exige d'y ajouter son bloc.")
        disparus = connus_manquants - manquants
        self.assertFalse(
            disparus,
            f"ces trous connus sont COMBLES : {sorted(disparus)}. C'est une "
            f"bonne nouvelle, mais la liste doit etre mise a jour dans le "
            f"meme geste, sinon elle ment sur l'etat du depot.")


if __name__ == '__main__':
    unittest.main(verbosity=2)
