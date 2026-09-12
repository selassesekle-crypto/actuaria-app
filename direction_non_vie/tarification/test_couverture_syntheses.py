# -*- coding: utf-8 -*-
"""
=============================================================================
  COUVERTURE COMPLETE : chaque synthese atteint chaque livrable signe
=============================================================================

DEUX RENDUS A LA MAIN PRENAIENT DU RETARD, ET RIEN NE LE DISAIT.

  L'EXCEL D'EQUIPE ne parcourt pas `_LABELS_SYNTHESES` : il code UN BLOC PAR
  CLE. Mesure du 03/09/2026 : **13 cles sur 16**. Manquaient `plan_ecarte`
  (`conformite/C15`), `exempt_effet` (`conformite/C4`) et `plafond`
  (`services/C7`) -- ce dernier le plus genant, son constat existant
  precisement pour qu'une cause de statut atteigne TOUS les livrables.

  LE RAPPORT MODELES ne portait aucune des trois reserves d'A6. Elles
  n'atteignaient donc qu'**une surface sur six**, l'Excel A6.

  *Un rendu par enumeration et un rendu a la main ne se maintiennent pas au
  meme rythme : c'est le second qui prend du retard, et il faut un filet
  SOUS lui, pas a sa place.*

-----------------------------------------------------------------------------
POURQUOI L'EXCEL N'A PAS ETE REECRIT EN BOUCLE
-----------------------------------------------------------------------------
Chaque synthese y a SA place (le walk-forward dans la section BACKTESTING,
la validation DL dans GOUVERNANCE), SON libelle -- avec des prefixes
<< ⚠ >> / << ℹ >> que `_LABELS_SYNTHESES` ne porte pas -- et SA regle de
badge (<< AMBRE si ACTION REQUISE >>, etc.). Une boucle unique aurait
detruit les trois, sur un livrable signe.

Le geste retenu : **lire une cle vaut l'enregistrer**, et ce qu'aucun bloc
n'a pris est rendu en fin de section. Un bloc supprime emporte son
enregistrement, donc sa cle retombe dans le filet -- le mecanisme se repare
tout seul.

-----------------------------------------------------------------------------
LES SIX SURFACES SIGNEES
-----------------------------------------------------------------------------
    equipe.html · equipe.word · equipe.excel
    modeles.html · modeles.word · a6.excel

⚠️ Elles s'enumerent ICI, une fois pour toutes. J'ai deja conclu << aucune
surface >> sur un releve fait a DEUX services sur trois : *un releve partiel
conclut faux, et toujours vers l'alarme.*
=============================================================================
"""

import io
import unittest
import zipfile

from core.conformite_reglementaire import synthese_sensibilite_profils
from direction_non_vie.tarification.services import (
    rapport_equipe_tarif as RE,
)
from direction_non_vie.tarification.services import (
    rapport_modeles_tarif as RM,
)
from direction_non_vie.tarification.services import (
    tarif_excel as TX,
)


def _docx(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return z.read('word/document.xml').decode('utf-8')


def _xlsx(blob: bytes) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(blob))
    return '\n'.join(str(c.value) for ws in wb.worksheets
                     for row in ws.iter_rows() for c in row
                     if c.value is not None)


def _r6(**extra):
    base = {'success': True, 'statut_rag': 'AMBRE', 'branche': 'auto',
            'modele_production': {'modele': 'GLM'}, 'backtest': {},
            'audit_trail': {}, 'classement': [], 'metriques': {}}
    base.update(extra)
    return base


class T1_LExcelDEquipeRendTOUTES_les_cles(unittest.TestCase):

    def test_cs_1_TOUTES_les_cles_atteignent_les_TROIS_formats_d_equipe(self):
        """CS-1 : plus AUCUNE clé absente d'un format.

        ⚠️ LE NOM NE PORTE PLUS DE COMPTE — 12/09/2026. Il annonçait « les
        seize clés » quand la table en portait DIX-NEUF : un nom qui compte
        se périme à chaque ajout, en silence, et personne ne relit un nom de
        méthode. L'assiette, elle, est DÉRIVÉE de `_LABELS_SYNTHESES` depuis
        le début — c'est le nom qui mentait, pas le contrôle.

        ⚠️ Aucune liste de trous n'est declaree ici, et c'est le point : le
        filet de fin de section les couvre TOUTES. Une exemption serait le
        retour du defaut.
        """
        for cle, _ in RE._LABELS_SYNTHESES:
            temoin = f'ZZ{cle.upper().replace("_", "")}ZZ'
            res, synth = {'a6': _r6()}, {cle: temoin}
            sorties = {
                'html': RE.export_html_equipe(res, syntheses=synth),
                'word': _docx(RE.export_word_equipe(res, syntheses=synth)),
                'excel': _xlsx(RE.export_excel_equipe(res, syntheses=synth)),
            }
            for nom, texte in sorties.items():
                with self.subTest(cle=cle, format=nom):
                    self.assertIn(
                        temoin, texte,
                        f"« {cle} » n'atteint pas {nom}. Si c'est une cle "
                        f"nouvelle, le filet de fin de section aurait du la "
                        f"prendre : verifier qu'elle a bien un LIBELLE dans "
                        f"`_LABELS_SYNTHESES`.")

    def test_cs_2_une_cle_INCONNUE_des_blocs_est_rendue_par_le_FILET(self):
        """CS-2 : le mecanisme lui-meme, pas seulement son resultat.

        ⚠️ Sans ce controle, quelqu'un pourrait recabler les trois cles a la
        main et supprimer le filet : `CS-1` resterait vert, et la PROCHAINE
        cle retomberait dans le trou. *Ce qui doit tenir, c'est le
        mecanisme, pas l'etat qu'il produit aujourd'hui.*
        """
        libelles = dict(RE._LABELS_SYNTHESES)
        # une cle qui n'a AUCUN bloc dedie dans l'Excel
        cle = 'exempt_effet'
        self.assertIn(cle, libelles)
        temoin = 'ZZFILETZZ'
        texte = _xlsx(RE.export_excel_equipe(
            {'a6': _r6()}, syntheses={cle: temoin}))
        self.assertIn(temoin, texte)
        self.assertIn(
            'AUTRES SYNTHÈSES RÉGLEMENTAIRES', texte,
            "la cle est rendue mais PAS par le filet : verifier qu'un bloc "
            "a la main ne l'a pas reprise, auquel cas le filet n'est plus "
            "eprouve par ce controle")

    def test_cs_3_rien_n_est_rendu_quand_il_n_y_a_rien_a_dire(self):
        """CS-3 : le second sens. Un filet qui affiche toujours est du bruit.

        ⚠️ MA PREMIERE FIXTURE ETAIT FAUSSE, et l'echec l'a montre : sur un
        `result_a6` minimal, le statut est AMBRE et `synthese_raisons_plafond`
        a donc bien quelque chose a dire -- le filet le rendait a bon droit.
        *Un << rien a dire >> se construit, il ne se suppose pas.* Il faut un
        statut VERT, ou cette synthese rend `None`.
        """
        texte = _xlsx(RE.export_excel_equipe(
            {'a6': _r6(statut_rag='VERT')}))
        self.assertNotIn('AUTRES SYNTHÈSES RÉGLEMENTAIRES', texte)


class T2_LeRapportModelesPorteLesReserves(unittest.TestCase):

    def test_cs_4_les_trois_reserves_atteignent_html_ET_word(self):
        """CS-4 : les deux formats, jamais un seul.

        ⚠️ Corriger un seul des deux laisserait la moitie du livrable signe
        muette -- c'est exactement ce qui s'etait produit pour
        l'avertissement DL (`avertissement_dl`).
        """
        for cle, _ in RM.RESERVES_A6:
            temoin = f'ZZ{cle.upper().replace("_", "")}ZZ'
            r6 = _r6(**{cle: temoin})
            with self.subTest(cle=cle, format='html'):
                self.assertIn(temoin, RM.export_html({}, {}, r6))
            with self.subTest(cle=cle, format='word'):
                self.assertIn(temoin, _docx(RM.export_word({}, {}, r6)))

    def test_cs_5_l_ordre_est_STABLE_et_rien_si_rien(self):
        """CS-5 : deux executions rendent le meme document.

        ⚠️ L'ordre vient de `RESERVES_A6`, pas du dictionnaire.

        ⚠️⚠️ LA FIXTURE SE DERIVE DE `RESERVES_A6`, ELLE NE LA RECOPIE PLUS.
        Elle posait TROIS reserves en dur ; l'ajout d'une quatrieme
        (`reserve_surapprentissage`, 07/09/2026) l'a fait rougir a la gate
        alors que la propriete testee -- l'ORDRE vient de la liste -- n'avait
        pas bouge. *Un controle qui recopie la liste qu'il verifie casse a
        chaque ajout et n'apprend rien ; derive, il reste juste.* C'est ce que
        `CS-4` faisait deja, deux methodes plus haut.
        """
        r6 = _r6(**{cle: f'VAL_{i}'
                    for i, (cle, _) in enumerate(RM.RESERVES_A6)})
        rendues = [lib for lib, _ in RM.reserves_arbitrage(r6)]
        self.assertEqual(rendues, [lib for _, lib in RM.RESERVES_A6])
        self.assertEqual(RM.reserves_arbitrage(_r6()), ())
        self.assertEqual(RM.reserves_arbitrage(None), ())
        self.assertEqual(RM.reserves_arbitrage(_r6(reserve_arbitrage='   ')),
                         ())


class T3_LesSixSurfaces(unittest.TestCase):
    """⚠️ L'ASSIETTE COMPLETE, enumeree une fois pour toutes."""

    def test_cs_6_les_reserves_atteignent_les_SIX_surfaces(self):
        """CS-6 : de 1/6 a 6/6, mesure de bout en bout."""
        for cle, _ in RM.RESERVES_A6:
            temoin = f'ZZ{cle.upper().replace("_", "")}ZZ'
            r6 = _r6(**{cle: temoin})
            res = {'a6': r6}
            surfaces = {
                'equipe.html': RE.export_html_equipe(res),
                'equipe.word': _docx(RE.export_word_equipe(res)),
                'equipe.excel': _xlsx(RE.export_excel_equipe(res)),
                'modeles.html': RM.export_html({}, {}, r6),
                'modeles.word': _docx(RM.export_word({}, {}, r6)),
                'a6.excel': _xlsx(TX.export_excel_a6(r6)),
            }
            manquantes = [nom for nom, txt in surfaces.items()
                          if temoin not in txt]
            with self.subTest(cle=cle):
                self.assertFalse(
                    manquantes,
                    f"« {cle} » n'atteint pas {manquantes} sur les six "
                    f"surfaces signees")

    def test_cs_7_le_GARDE_FOU_N4_atteint_les_SIX_surfaces(self):
        """CS-7 : le controle anti-fuite par l'effet, de 1/6 a 6/6.

        ⚠️⚠️ POURQUOI UNE DENT A PART. `CS-6` itere `RESERVES_A6`, et le
        garde-fou n°4 n'est PAS une reserve : `result_a6['controle_effet']`
        est un DICT (`{'execute': bool, 'motifs': {cible: pourquoi}}`) que
        seule `avertissement_controle_effet` sait rendre. Le glisser dans
        le catalogue aurait publie le dict brut.

        ⚠️⚠️ ET CE QUI ETAIT EN JEU. Sa source unique porte, ecrit dans sa
        docstring, *« a afficher dans TOUT livrable »* -- et elle raconte
        que la propriete `controle_effet_execute` etait restee **une trace
        interne que rien n'atteignait** jusqu'au 25/08/2026. Mesure du
        12/09/2026 : elle atteignait l'Excel A6, et RIEN d'autre.

          *Le garde-fou n°4 est le SEUL qui ne depende d'aucun nom de
          colonne. Dire qu'il n'a pas tourne appartient au document que
          l'actuaire signe.*

        ⚠️ LES DEUX SENS. Non execute -> le texte atteint les six ; execute
        sans motif -> RIEN n'est publie, car un bloc toujours affiche ne
        signale plus rien.
        """
        temoin = 'ZZCIBLEEFFETZZ'
        r6 = _r6(controle_effet={'execute': False,
                                 'motifs': {temoin: 'non examinee'}})
        res = {'a6': r6}
        surfaces = {
            'equipe.html': RE.export_html_equipe(res),
            'equipe.word': _docx(RE.export_word_equipe(res)),
            'equipe.excel': _xlsx(RE.export_excel_equipe(res)),
            'modeles.html': RM.export_html({}, {}, r6),
            'modeles.word': _docx(RM.export_word({}, {}, r6)),
            'a6.excel': _xlsx(TX.export_excel_a6(r6)),
        }
        manquantes = [nom for nom, txt in surfaces.items()
                      if temoin not in txt]
        self.assertFalse(
            manquantes,
            f"le garde-fou n°4 n'atteint pas {manquantes} : un actuaire y "
            f"signe un tarif sans savoir que le SEUL controle independant "
            f"des noms de colonnes n'a examine aucune colonne")

        #: ⚠️ SECOND SENS : execute et complet -> le bloc DISPARAIT.
        r6b = _r6(controle_effet={'execute': True, 'motifs': {}})
        for nom, txt in (('modeles.html', RM.export_html({}, {}, r6b)),
                         ('modeles.word',
                          _docx(RM.export_word({}, {}, r6b)))):
            with self.subTest(surface=nom):
                self.assertNotIn(
                    'NON EXÉCUTÉ', txt,
                    f"{nom} annonce le garde-fou n°4 comme non execute "
                    f"alors qu'il a couvert toutes les cibles : un bloc qui "
                    f"parle toujours ne signale plus rien")
        print(f"    CS-7 le garde-fou n4 atteint {len(surfaces)}/6 surfaces, "
              f"et se tait quand il n'a rien a dire")

    def test_cs_8_la_SENSIBILITE_AU_PROFIL_atteint_les_SIX_surfaces(self):
        """CS-8 : le profil de ponderation est un LEVIER SUR LE PRIX.

        ⚠️⚠️ CE QUI ETAIT EN JEU, ET IL EST CHIFFRE. Le profil est choisi par
        un humain ; `gouvernance_validee` ne verifie qu'un NOM NON VIDE --
        elle dit QUI a assume le choix, jamais CE QUE le choix a change.
        Mesure du 29/08/2026, sur quatre portefeuilles, avec la formule qui
        DECIDE : **le modele retenu bascule dans 3 cas sur 4 sur la cible
        cout**, marges #1-#2 a 0,008 / 0,016 / 0,021 selon le profil.

        Mesure du 12/09/2026 : la table n'atteignait que le rapport modeles
        -- 2 surfaces sur 6. Ni le rapport qui CIRCULE, ni le classeur
        SIGNE n'en portaient rien.

        ⚠️ LES DEUX SENS, ET LE SECOND EST UNE INFORMATION. Quand tous les
        profils designent le meme modele, le texte l'AFFIRME : *taire la
        stabilite laisserait croire qu'elle n'a pas ete regardee.*
        """
        temoin = 'ZZPROFILSENSZZ'
        table = [{'profil': temoin, 'modele': 'glm_poisson',
                  'score': 0.81, 'marge': 0.008, 'actif': True},
                 {'profil': 'discrimination', 'modele': 'xgboost',
                  'score': 0.79, 'marge': 0.021, 'actif': False}]
        r6 = _r6(sensibilite_profils=table)
        res = {'a6': r6}
        surfaces = {
            'equipe.html': RE.export_html_equipe(res),
            'equipe.word': _docx(RE.export_word_equipe(res)),
            'equipe.excel': _xlsx(RE.export_excel_equipe(res)),
            'modeles.html': RM.export_html({}, {}, r6),
            'modeles.word': _docx(RM.export_word({}, {}, r6)),
            'a6.excel': _xlsx(TX.export_excel_a6(r6)),
        }
        manquantes = [nom for nom, txt in surfaces.items()
                      if temoin not in txt]
        self.assertFalse(
            manquantes,
            f"la sensibilite au profil n'atteint pas {manquantes} : un "
            f"lecteur y voit un modele retenu sans savoir qu'un autre "
            f"profil en aurait retenu un autre")

        #: ⚠️ SECOND SENS : profils UNANIMES -> la stabilite est AFFIRMEE,
        #: pas passee sous silence.
        stable = [{'profil': 'equilibre', 'modele': 'glm', 'actif': True},
                  {'profil': 'discrimination', 'modele': 'glm'}]
        texte = synthese_sensibilite_profils(stable) or ''
        self.assertIn(
            'NE dépend PAS', texte,
            "des profils unanimes ne produisent aucune phrase : le lecteur "
            "ne peut pas distinguer « stable » de « pas regarde »")
        #: ⚠️ TROISIEME SENS : pas de table -> RIEN. On ne suppose pas.
        self.assertIsNone(
            synthese_sensibilite_profils(None),
            "une table absente produit un texte : le rapport affirmerait "
            "une sensibilite qu'A6 n'a jamais calculee")
        print(f"    CS-8 la sensibilite au profil atteint {len(surfaces)}/6 "
              f"surfaces, et dit la stabilite au lieu de la taire")


if __name__ == '__main__':
    unittest.main(verbosity=2)
