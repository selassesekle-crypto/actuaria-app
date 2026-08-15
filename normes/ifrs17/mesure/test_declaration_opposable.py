# -*- coding: utf-8 -*-
"""Tests — l'opposabilité d'une déclaration : signée, et PAR QUI.

⚠️ LE CALIBRAGE VIT ICI, comme celui de `PLACEHOLDERS` et celui du néant
motivé. Un contrôle sur du texte qui n'exhibe pas ses deux taux d'erreur se
fait croire sur parole.
"""

import unittest

from normes.ifrs17.mesure.declaration import (
    MARQUEURS_DE_NON_SIGNATURE,
    MOTIF_DECLARANT_NON_HABILITE,
    MOTIF_STATUT_NON_SIGNE,
    QUALITE_ENTITE,
    QUALITE_TIERS,
    QUALITES,
    exiger_declaration_opposable,
)
from normes.ifrs17.mesure.lrc_paa import RefusMesure


def _opposable(**kw):
    base = {'statut': 'signee le 12/06/2026', 'declarant': 'directrice technique',
            'qualite': QUALITE_ENTITE, 'erreur': RefusMesure}
    base.update(kw)
    return exiger_declaration_opposable(**base)


class T1_CalibrageDuStatut(unittest.TestCase):
    """⚠️ ZÉRO FAUX ACCEPTÉ EST LA CONTRAINTE ; le faux rejet est le prix."""

    A_REFUSER = (
        'DEMONSTRATION_A_REMPLACER', 'A_REMPLACER', 'PROVISOIRE', 'BROUILLON',
        'DRAFT', 'TEST', 'EXEMPLE', 'PROJET', 'DEMO', 'a valider',
        'NON SIGNEE', 'non signe', 'specimen', 'MAQUETTE',
        'jeu de demonstration', 'version provisoire', 'brouillon du 12/06',
        'DEMONSTRATION', 'simulation',
    )
    #: ⚠️ LES CAS ADVERSES QUI ONT DISQUALIFIÉ LA VARIANTE FINE. Une règle à
    #: deux listes les laissait TOUS passer ; ils sont gardés ici pour que le
    #: jour où quelqu'un voudra « améliorer » le contrôle, il les rencontre.
    ADVERSES = (
        'signee, mais provisoire', 'validee a titre de demonstration',
        'approuvee sous reserve, statut provisoire', 'signee - jeu de test',
        'definitive pour la demo', 'valide en environnement de test',
        'arretee, version brouillon',
    )
    A_ACCEPTER = (
        'SIGNEE', 'signee le 12/06/2026 par le directeur technique',
        'validee par le comite ALM du 30/06/2026', 'APPROUVEE', 'DEFINITIVE',
        'signee et opposable', 'arretee par le conseil du 15/07', 'VALIDEE',
        'signature electronique du 01/08/2026', 'definitive, version 3',
    )

    def test_zero_faux_accepte_sur_les_statuts_non_signes(self):
        for s in self.A_REFUSER:
            with self.assertRaises(RefusMesure, msg=s) as e:
                _opposable(statut=s)
            self.assertEqual(e.exception.motif, MOTIF_STATUT_NON_SIGNE)

    def test_zero_faux_accepte_sur_les_cas_ADVERSES(self):
        """⚠️ Ceux-là ont fait tomber la variante à deux listes, 8 sur 8."""
        for s in self.ADVERSES:
            with self.assertRaises(RefusMesure, msg=s) as e:
                _opposable(statut=s)
            self.assertEqual(e.exception.motif, MOTIF_STATUT_NON_SIGNE)

    def test_zero_faux_rejet_sur_les_statuts_signes(self):
        for s in self.A_ACCEPTER:
            _opposable(statut=s)

    def test_le_faux_rejet_connu_est_assume_et_le_refus_l_explique(self):
        """⚠️ LE PRIX DE LA SOUS-CHAÎNE, NOMMÉ PLUTÔT QUE TU.

        « signée après remplacement de la version provisoire » est refusé à
        tort. Le refus dit pourquoi et invite à reformuler — un faux refus se
        voit, un faux accepté ne laisse aucune trace.
        """
        with self.assertRaises(RefusMesure) as e:
            _opposable(statut='signee apres remplacement de la version '
                              'provisoire')
        self.assertIn('version ANTÉRIEURE', str(e.exception))
        self.assertIn('reformulez', str(e.exception))

    def test_un_statut_vide_ou_fictif_est_refuse(self):
        for s in ('', 'A_RENSEIGNER', 'TBD'):
            with self.assertRaises(RefusMesure, msg=s) as e:
                _opposable(statut=s)
            self.assertEqual(e.exception.motif, MOTIF_STATUT_NON_SIGNE)


class T2_LaQualiteEstUnSecondChamp(unittest.TestCase):
    """⚠️⚠️ LE STATUT DIT SI C'EST SIGNÉ, JAMAIS PAR QUI."""

    def test_un_statut_irreprochable_ne_sauve_pas_un_TIERS(self):
        """Le cas exact du jeu reçu, et celui qu'aucun marqueur n'attrape."""
        with self.assertRaises(RefusMesure) as e:
            _opposable(statut='signee le 12/06/2026',
                       declarant='producteur des donnees', qualite=QUALITE_TIERS)
        self.assertEqual(e.exception.motif, MOTIF_DECLARANT_NON_HABILITE)
        self.assertIn("L'ENTITÉ", str(e.exception))

    def test_le_refus_dit_que_le_statut_ne_porte_pas_la_qualite(self):
        with self.assertRaises(RefusMesure) as e:
            _opposable(qualite='')
        self.assertIn('LE STATUT NE LA PORTE PAS', str(e.exception))
        self.assertIn('jamais PAR QUI', str(e.exception))

    def test_une_qualite_inconnue_est_refusee(self):
        with self.assertRaises(RefusMesure) as e:
            _opposable(qualite='PEUT_ETRE')
        self.assertEqual(e.exception.motif, MOTIF_DECLARANT_NON_HABILITE)

    def test_une_qualite_sans_declarant_nomme_est_refusee(self):
        for d in ('', 'A_RENSEIGNER'):
            with self.assertRaises(RefusMesure, msg=d) as e:
                _opposable(declarant=d)
            self.assertEqual(e.exception.motif, MOTIF_DECLARANT_NON_HABILITE)

    def test_il_n_y_a_que_deux_qualites(self):
        self.assertEqual(QUALITES, (QUALITE_ENTITE, QUALITE_TIERS))


class T3_CeQueLeControleNEtablitPas(unittest.TestCase):
    """⚠️ UN CONTRÔLE QUI NE DIT PAS SA PORTÉE SE FAIT SURÉVALUER."""

    def test_le_motif_dit_qu_il_ne_verifie_pas_la_signature_elle_meme(self):
        m = _opposable()
        self.assertIn("un statut qui ment", m)
        self.assertIn('ne vaut donc pas vérification', m)

    def test_le_motif_porte_le_statut_ET_le_declarant(self):
        """Un lecteur doit pouvoir juger sur pièce, pas sur un booléen."""
        m = _opposable(statut='validee le 30/06', declarant='comite ALM')
        self.assertIn('validee le 30/06', m)
        self.assertIn('comite ALM', m)

    def test_les_marqueurs_sont_une_liste_fermee(self):
        self.assertIn('demonstration', MARQUEURS_DE_NON_SIGNATURE)
        self.assertIn('a remplacer', MARQUEURS_DE_NON_SIGNATURE)
        self.assertIsInstance(MARQUEURS_DE_NON_SIGNATURE, tuple)


if __name__ == '__main__':
    unittest.main()
