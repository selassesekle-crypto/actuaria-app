# -*- coding: utf-8 -*-
"""Tests U1d — la porte de confirmation avant tout scellement.

⚠️ GATE : `py -m unittest discover -s normes -t .` — voir test_contrat.py.
"""
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from normes.ifrs17.socle.confirmation import (
    MOTIF_ARRETE_DISCORDANT,
    MOTIF_SANS_SIGNATAIRE,
    Confirmation,
    RefusConfirmation,
    a_confirmer,
    confirmer,
    resume_confirmation,
    verifier,
)
from normes.ifrs17.socle.groupe import deriver
from normes.ifrs17.socle.lecture_inventaire import lire
from normes.ifrs17.socle.registre import ajouter, ecrire, ouvrir, relire

ARRETE = '2026-06-30'

#: Colonnes telles qu'un assureur les sort — les champs scellés y sont
#: reconnus par SYNONYME, donc à attester.
INFERE = {'POLICE': ['P-001', 'P-002'],
          'BRANCHE': ['RC_AUTO', 'MRH'],
          'DT_SOUSCRIPTION': ['2026-03-15', '2026-04-02'],
          'DT_ECHEANCE': ['2027-03-14', '2027-04-01']}

#: Les mêmes données, colonnes nommées canoniquement — rien à attester.
CANONIQUE = {'identifiant_contrat': ['P-001', 'P-002'],
             'portefeuille': ['RC_AUTO', 'MRH'],
             'date_emission': ['2026-03-15', '2026-04-02'],
             'fin_couverture': ['2027-03-14', '2027-04-01']}


def _lu(dico):
    p = Path(tempfile.mkdtemp()) / 'inv.csv'
    pd.DataFrame(dico).to_csv(p, index=False, sep=';', encoding='utf-8')
    return lire(p)


class T1_CeQuiDoitEtreAtteste(unittest.TestCase):
    """T1 — la porte ne se déclenche que sur ce qui a été inféré."""

    def test_un_synonyme_sur_un_champ_scelle_doit_etre_atteste(self):
        _, r = _lu(INFERE)
        champs = {c.champ for c in a_confirmer(r)}
        self.assertEqual(champs, {'portefeuille', 'date_emission'})
        print(f"    OK T1 : {len(champs)} champs scelles inferes, a attester")

    def test_un_nom_canonique_n_a_rien_a_attester(self):
        """⚠️ Le lecteur n'a rien devine : il n'y a rien a signer DESSUS."""
        _, r = _lu(CANONIQUE)
        self.assertEqual(a_confirmer(r), ())
        print("    OK T1b : colonnes canoniques -> aucune correspondance "
              "a attester")

    def test_la_regle_vit_a_un_seul_endroit(self):
        """⚠️ DEUX DEFINITIONS DE << CE QUI DOIT ETRE CONFIRME >> DIVERGERAIENT.

        La verification porte sur l'ACCORD des deux voies, sur des entrees
        de natures differentes -- pas sur l'identite des objets rendus, la
        propriete reconstruisant son tuple a chaque appel.
        """
        for dico in (INFERE, CANONIQUE):
            _, r = _lu(dico)
            self.assertEqual(a_confirmer(r), r.a_confirmer)
        import inspect

        from normes.ifrs17.socle import confirmation as C
        corps = [l.strip() for l in
                 inspect.getsource(C.a_confirmer).split('\n')
                 if l.strip() and not l.strip().startswith(('"', '#', 'def',
                                                            '⚠', 'Cette',
                                                            'definitions',
                                                            "c'est le"))]
        self.assertIn('return rapport.a_confirmer', corps)
        print("    OK T1c : a_confirmer() delegue au rapport, "
              "il n'en tient pas une seconde copie")


class T2_LaSignature(unittest.TestCase):
    """T2 — sceller engage quelqu'un, nommément."""

    def test_confirmer_capture_ce_que_le_lecteur_a_compris(self):
        _, r = _lu(INFERE)
        c = confirmer(r, 'Selasse Sekle', ARRETE)
        self.assertEqual(c.actuaire_resp, 'Selasse Sekle')
        self.assertEqual(c.arrete, ARRETE)
        self.assertEqual(dict(c.correspondances),
                         {'BRANCHE': 'portefeuille',
                          'DT_SOUSCRIPTION': 'date_emission'})
        print(f"    OK T2 : {len(c.correspondances)} correspondances "
              f"attestees par {c.actuaire_resp}")

    def test_sans_signataire_confirmer_refuse(self):
        _, r = _lu(INFERE)
        for vide in ('', '   ', None):
            with self.assertRaises(RefusConfirmation) as ctx:
                confirmer(r, vide, ARRETE)
            self.assertEqual(ctx.exception.motif, MOTIF_SANS_SIGNATAIRE)
        print("    OK T2b : pas de confirmation sans signataire nomme")

    def test_le_resume_dit_ce_qui_a_ete_atteste(self):
        _, r = _lu(INFERE)
        txt = resume_confirmation(confirmer(r, 'Selasse Sekle', ARRETE))
        self.assertIn('CONFIRMÉ par Selasse Sekle', txt)
        self.assertIn('DT_SOUSCRIPTION lu comme « date_emission »', txt)
        self.assertIn('NI la survenance', txt)
        print("    OK T2c : le resume nomme le signataire et rappelle "
              "ce que le champ signifie")


class T3_LaPorteEstAuScellement(unittest.TestCase):
    """T3 — lire et dériver restent libres ; sceller exige une signature."""

    def test_lire_et_deriver_ne_demandent_aucune_signature(self):
        """⚠️ L'EXIGENCE DE FACILITE : le client depose et voit, sans signer."""
        df, _ = _lu(INFERE)
        groupes = deriver(df.to_dict('records'))
        self.assertEqual(len(groupes), 2)
        print(f"    OK T3 : {len(groupes)} groupes derives sans aucune "
              "signature")

    def test_sceller_sans_confirmation_est_refuse(self):
        df, _ = _lu(INFERE)
        with self.assertRaises(RefusConfirmation) as ctx:
            ajouter(ouvrir('CLI', 'ENT'), df.to_dict('records'), ARRETE)
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_SIGNATAIRE)
        msg = str(ctx.exception)
        self.assertIn('date_emission', msg)
        self.assertIn('Lecture et dérivation restent possibles', msg)
        print("    OK T3b : sceller sans confirmation est refuse, "
              "et le message dit ce qui reste possible")

    def test_une_confirmation_d_un_autre_arrete_est_refusee(self):
        df, r = _lu(INFERE)
        c = confirmer(r, 'Selasse Sekle', '2025-12-31')
        with self.assertRaises(RefusConfirmation) as ctx:
            ajouter(ouvrir('CLI', 'ENT'), df.to_dict('records'), ARRETE, c)
        self.assertEqual(ctx.exception.motif, MOTIF_ARRETE_DISCORDANT)
        print("    OK T3c : une attestation vaut pour SON scellement, "
              "pas pour un autre")

    def test_verifier_refuse_une_confirmation_sans_nom(self):
        with self.assertRaises(RefusConfirmation) as ctx:
            verifier(Confirmation('  ', ARRETE, ()), ARRETE)
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_SIGNATAIRE)
        print("    OK T3d : une confirmation fabriquee a la main sans nom "
              "est refusee au scellement")


class T4_AppendOnlyEtPersistance(unittest.TestCase):
    """T4 — une confirmation ne se corrige pas ; elle s'ajoute."""

    def test_chaque_versement_ajoute_sa_confirmation(self):
        df, r = _lu(INFERE)
        lignes = df.to_dict('records')
        reg = ajouter(ouvrir('CLI', 'ENT'), lignes, ARRETE,
                      confirmer(r, 'Actuaire A', ARRETE))
        self.assertEqual(len(reg.confirmations), 1)
        reg2 = ajouter(reg, lignes, '2027-06-30',
                       confirmer(r, 'Actuaire B', '2027-06-30'))
        self.assertEqual(len(reg2.confirmations), 2)
        self.assertEqual([c.actuaire_resp for c in reg2.confirmations],
                         ['Actuaire A', 'Actuaire B'])
        self.assertEqual(len(reg.confirmations), 1)     # l'ancien intact
        print("    OK T4 : 2 versements -> 2 confirmations, "
              "la premiere inchangee")

    def test_une_confirmation_est_immuable(self):
        _, r = _lu(INFERE)
        c = confirmer(r, 'Selasse Sekle', ARRETE)
        with self.assertRaises(AttributeError):
            c.actuaire_resp = 'Quelqu un d autre'
        print("    OK T4b : une confirmation ne se corrige pas")

    def test_les_confirmations_survivent_a_l_ecriture(self):
        df, r = _lu(INFERE)
        reg = ajouter(ouvrir('CLI', 'ENT'), df.to_dict('records'), ARRETE,
                      confirmer(r, 'Selasse Sekle', ARRETE))
        p = Path(tempfile.mkdtemp()) / 'reg.json'
        relu = relire(ecrire(reg, p))
        self.assertEqual(relu, reg)
        self.assertEqual(relu.confirmations[0].actuaire_resp,
                         'Selasse Sekle')
        self.assertEqual(dict(relu.confirmations[0].correspondances),
                         {'BRANCHE': 'portefeuille',
                          'DT_SOUSCRIPTION': 'date_emission'})
        print("    OK T4c : signataire et correspondances survivent "
              "a l'aller-retour")

    def test_un_registre_canonique_confirme_sans_correspondance(self):
        """Rien n'a ete infere, mais quelqu'un scelle quand meme."""
        df, r = _lu(CANONIQUE)
        reg = ajouter(ouvrir('CLI', 'ENT'), df.to_dict('records'), ARRETE,
                      confirmer(r, 'Selasse Sekle', ARRETE))
        self.assertEqual(reg.confirmations[0].correspondances, ())
        self.assertIn('aucune correspondance inférée',
                      resume_confirmation(reg.confirmations[0]))
        print("    OK T4d : colonnes canoniques -> confirmation sans "
              "correspondance, mais signee")


if __name__ == '__main__':
    unittest.main(verbosity=2)
