# -*- coding: utf-8 -*-
"""
=============================================================================
  LES TROIS RESERVES D'A6 ATTEIGNENT LE RAPPORT QUI CIRCULE
=============================================================================

A6 produit trois reserves sur son propre arbitrage :

  `reserve_arbitrage`     -- un seul candidat : << retenu >> sans avoir ete
                             compare a quoi que ce soit
  `reserve_vraisemblance` -- la vraisemblance du Gini n'est pas calibree sur
                             cette cible
  `reserve_bases_gini`    -- deux colonnes du meme tableau ne sont pas sur le
                             meme pied (constat `a4/C10`)

Mesure du 03/09/2026, par EXECUTION, sur les SIX surfaces signees : elles
n'atteignaient QUE l'Excel A6. **1 sur 6.** Ni les trois formats du rapport
d'equipe, ni les deux du rapport modeles -- or c'est le rapport d'EQUIPE qui
circule au CAC.

  *Une reserve sur l'arbitrage qui n'atteint pas le document qui circule ne
  reserve rien : elle informe un fichier que personne n'ouvre.*

⚠️ ET J'AVAIS ANNONCE << AUCUNE SURFACE >>. Le releve avait ete fait sur DEUX
services sur trois -- `tarif_excel` n'avait pas ete regarde. *Un releve
partiel conclut faux, et dans le sens le plus alarmant.* La correction de ce
chiffre fait partie de ce lot autant que le correctif.

-----------------------------------------------------------------------------
CE QUE CE LOT FAIT, ET CE QU'IL NE FAIT PAS
-----------------------------------------------------------------------------
Il porte les trois reserves de **1/6 a 4/6** : les trois formats du rapport
d'equipe s'ajoutent a l'Excel A6. Le rendu reste fait UNE fois -- par A6,
qui produit deja des CHAINES : on relaie, on ne recompose pas.

⚠️⚠️ MISE A JOUR DU 03/09/2026 (soir) : la couverture est passee a **6/6**.
Le rapport MODELES porte desormais les trois reserves, en html ET en word
(`reserves_arbitrage`, source unique lue par les deux formats). Et l'Excel
d'equipe a recu un FILET qui rend toute cle qu'aucun bloc a la main n'a
prise -- ce qui a ferme du meme coup `plan_ecarte`, `exempt_effet` et
`plafond`.

⚠️ `RA-5` ET `RA-6` ONT TIRE TOUT SEULS POUR L'EXIGER : ecrits pour tomber
dans les DEUX sens, ils ont echoue des que les trous ont ete combles, et
ont force leurs propres phrases a suivre le code. *Un controle qui accepte
la bonne nouvelle en silence devient la description d'un passe.*
=============================================================================
"""

import io
import unittest
import zipfile

from direction_non_vie.tarification.services import rapport_equipe_tarif as RE

_CLES = ('reserve_arbitrage', 'reserve_vraisemblance', 'reserve_bases_gini')


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


def _trois_formats(r6) -> dict:
    res = {'a6': r6}
    return {'html': RE.export_html_equipe(res),
            'word': _docx(RE.export_word_equipe(res)),
            'excel': _xlsx(RE.export_excel_equipe(res))}


class T1_LesTroisReservesCirculent(unittest.TestCase):

    def test_ra_1_chaque_reserve_atteint_les_TROIS_formats_d_equipe(self):
        """RA-1 : mesure par EXECUTION, sur les sorties reelles."""
        for cle in _CLES:
            temoin = f'ZZ{cle.upper().replace("_", "")}ZZ'
            sorties = _trois_formats(_r6(**{cle: temoin}))
            for nom, texte in sorties.items():
                with self.subTest(cle=cle, format=nom):
                    self.assertIn(
                        temoin, texte,
                        f"« {cle} » n'atteint pas le format {nom} du rapport "
                        f"d'equipe -- celui qui circule")

    def test_ra_2_les_trois_cles_ont_un_LIBELLE(self):
        """RA-2 : le piege `CF-9`, cinquieme rencontre.

        Le html et le word iterent `_LABELS_SYNTHESES` : une cle SANS
        libelle est rendue NULLE PART, en silence.
        """
        libelles = dict(RE._LABELS_SYNTHESES)
        for cle_synthese in ('reserve_arbitrage', 'reserve_vraisemblance',
                             'reserve_bases'):
            with self.subTest(cle=cle_synthese):
                self.assertIn(cle_synthese, libelles)
                self.assertTrue(libelles[cle_synthese].strip())

    def test_ra_3_rien_n_est_publie_quand_il_n_y_a_rien_a_dire(self):
        """RA-3 : le second sens. Une reserve toujours affichee ne reserve rien.

        ⚠️ Sans ce controle, publier les trois libelles en dur passerait
        RA-1 et RA-2.
        """
        synth = RE.syntheses_reglementaires({'a6': _r6()})
        for cle_synthese in ('reserve_arbitrage', 'reserve_vraisemblance',
                             'reserve_bases'):
            with self.subTest(cle=cle_synthese):
                self.assertNotIn(
                    cle_synthese, synth,
                    "une reserve est publiee alors qu'A6 n'en produit pas")
        sorties = _trois_formats(_r6())
        for nom, texte in sorties.items():
            with self.subTest(format=nom):
                self.assertNotIn("l'arbitrage n'avait qu'un candidat", texte)

    def test_ra_4_le_rendu_est_RELAYE_et_non_recompose(self):
        """RA-4 : source unique -- deux rendus, deux verites possibles.

        A6 produit deja des CHAINES. Le service ne doit que les relayer :
        si la synthese recomposait le texte, le meme fait pourrait se lire
        differemment dans l'Excel A6 et dans le rapport d'equipe.
        """
        phrase = ("⚠ ARBITRAGE À UN SEUL CANDIDAT — texte produit par A6, "
                  "mot pour mot.")
        synth = RE.syntheses_reglementaires(
            {'a6': _r6(reserve_arbitrage=phrase)})
        self.assertEqual(
            synth.get('reserve_arbitrage'), phrase,
            "la synthese a MODIFIE le texte d'A6 : le rendu n'est plus "
            "fait a un seul endroit")


class T2_LaCouvertureEstEpingleeEtSesTrousNommes(unittest.TestCase):

    def test_ra_5_la_couverture_EXCEL_des_syntheses_ne_regresse_pas(self):
        """RA-5 : L'ASSIETTE. L'Excel code un bloc PAR CLE, a la main.

        ⛔ TROIS TROUS ETAIENT NOMMES ICI -- `plan_ecarte`
        (`conformite/C15`), `exempt_effet` (`conformite/C4`) et `plafond`
        (`services/C7`). **Ils sont COMBLES depuis le 03/09/2026** : l'Excel
        d'equipe porte desormais un FILET qui rend toute cle qu'aucun bloc a
        la main n'a prise.

        ⚠️⚠️ ET CE CONTROLE A TIRE TOUT SEUL POUR L'EXIGER. Ecrit pour
        tomber DANS LES DEUX SENS, il a echoue sur << ces trous connus sont
        COMBLES >> des que le filet a ete pose. *Un controle qui n'accepte
        pas la bonne nouvelle en silence force la liste a suivre le code.*

        La liste est donc VIDE : plus aucune exemption. `CS-1` et `CS-2`
        (test_couverture_syntheses) tiennent desormais la couverture et le
        MECANISME ; celui-ci garde la non-regression.
        """
        connus_manquants: set = set()
        manquants = set()
        for cle, _ in RE._LABELS_SYNTHESES:
            temoin = f'ZZ{cle.upper().replace("_", "")}ZZ'
            texte = _xlsx(RE.export_excel_equipe(
                {'a6': _r6()}, syntheses={cle: temoin}))
            if temoin not in texte:
                manquants.add(cle)
        self.assertFalse(
            manquants - connus_manquants,
            f"nouvelles cles absentes de l'Excel equipe : "
            f"{sorted(manquants - connus_manquants)}. L'Excel code un bloc "
            f"par cle : en ajouter une exige d'y ajouter son bloc.")
        self.assertFalse(
            connus_manquants - manquants,
            f"ces trous connus sont COMBLES : "
            f"{sorted(connus_manquants - manquants)}. Bonne nouvelle, mais "
            f"la liste se met a jour DANS LE MEME GESTE.")

    def test_ra_6_le_rapport_MODELES_les_porte_AUSSI(self):
        """RA-6 : la couverture est passee de 4/6 a 6/6 le 03/09/2026.

        ⚠️⚠️ CE CONTROLE DISAIT L'INVERSE, ET C'EST POUR CELA QU'IL EXISTE.
        Il epinglait << le rapport MODELES reste hors couverture >>, pour
        que l'elargissement soit un GESTE CONSCIENT et non un effet de
        bord. Il a tire des que les blocs ont ete poses, et a exige que sa
        propre phrase soit reecrite.

          *Un controle qui epingle une limite doit tomber quand la limite
          est levee : sinon il devient la description d'un passe que plus
          rien ne verifie.*

        ⚠️ PAS DE `try/except: continue` ICI. Ma premiere version en avait
        un : sur une exception, le controle passait au suivant EN SILENCE,
        et un export casse l'aurait rendu vert sans rien verifier. *Un garde
        pose << au cas ou >> transforme une panne en succes.*
        """
        from direction_non_vie.tarification.services import (
            rapport_modeles_tarif as RM,
        )
        for cle in _CLES:
            temoin = f'ZZ{cle.upper().replace("_", "")}ZZ'
            r6 = _r6(**{cle: temoin})
            with self.subTest(cle=cle):
                self.assertIn(
                    temoin, RM.export_html({}, {}, r6),
                    f"« {cle} » n'atteint plus le rapport modeles (html)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
