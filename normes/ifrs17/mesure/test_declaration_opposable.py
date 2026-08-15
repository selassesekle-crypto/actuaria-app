# -*- coding: utf-8 -*-
"""Tests — l'opposabilité d'une déclaration : signée, et PAR QUI.

⚠️ LE CALIBRAGE VIT ICI, comme celui de `PLACEHOLDERS` et celui du néant
motivé. Un contrôle sur du texte qui n'exhibe pas ses deux taux d'erreur se
fait croire sur parole.
"""

import unittest

from normes.ifrs17.mesure.declaration import (
    COMPARAISON_ANTERIEUR_OU_EGAL,
    COMPARAISON_EGAL,
    DEMONSTRATION_INCOHERENCE_D_ENSEMBLE,
    FORME_ARRETE,
    LIMITE_ANTERIEUR_OU_EGAL,
    MARQUEURS_DE_NON_SIGNATURE,
    MOTIF_ARRETE_HORS_CONTEXTE,
    MOTIF_CONTEXTE_INVALIDE,
    MOTIF_DECLARANT_NON_HABILITE,
    MOTIF_PERIMETRE_DISCORDANT,
    MOTIF_STATUT_NON_SIGNE,
    QUALITE_ENTITE,
    QUALITE_TIERS,
    QUALITES,
    ContexteEvaluation,
    PerimetreDeclare,
    exiger_arrete_dans_le_contexte,
    exiger_declaration_opposable,
    exiger_ensemble_coherent,
)
from normes.ifrs17.mesure.lrc_paa import RefusMesure

PTF = ('AUTO_TR', 'MRH', 'GAV', 'RC_AUTO', 'RC_PRO', 'DO')
CONTEXTE = ContexteEvaluation(arrete='2026-12-31', portefeuilles=PTF)
PERIMETRE = PerimetreDeclare(arrete='2026-12-31', portefeuilles=PTF)


def _opposable(**kw):
    base = {'statut': 'signee le 12/06/2026', 'declarant': 'directrice technique',
            'qualite': QUALITE_ENTITE, 'erreur': RefusMesure,
            'perimetre': PERIMETRE, 'contexte': CONTEXTE}
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


class T4_LeTroisiemeControle_POUR_QUOI(unittest.TestCase):
    """⚠️⚠️ LE CAS LE PLUS DANGEREUX : signée, par la bonne entité, et FAUSSE.

    Une courbe de l'arrêté précédent franchit les deux premiers contrôles.
    C'est le seul des trois défauts qui NE LAISSE AUCUNE TRACE — les montants
    qui en descendent restent plausibles.
    """

    def test_une_courbe_PERIMEE_est_refusee(self):
        with self.assertRaises(RefusMesure) as e:
            _opposable(perimetre=PerimetreDeclare(arrete='2025-12-31',
                                                  portefeuilles=PTF))
        self.assertEqual(e.exception.motif, MOTIF_PERIMETRE_DISCORDANT)
        self.assertIn('PÉRIMÉE', str(e.exception))
        self.assertIn('aucune trace', str(e.exception))

    def test_une_couverture_PARTIELLE_est_refusee_et_nomme_les_manquants(self):
        """⚠️ Cinq portefeuilles sur six : silencieux jusqu'ici."""
        with self.assertRaises(RefusMesure) as e:
            _opposable(perimetre=PerimetreDeclare(arrete='2026-12-31',
                                                  portefeuilles=PTF[:5]))
        self.assertEqual(e.exception.motif, MOTIF_PERIMETRE_DISCORDANT)
        self.assertIn("'DO'", str(e.exception))
        self.assertIn('SILENCIEUSE', str(e.exception))

    def test_couvrir_DAVANTAGE_que_l_evalue_passe(self):
        """La déclaration doit couvrir AU MOINS l'évalué, pas exactement."""
        _opposable(perimetre=PerimetreDeclare(
            arrete='2026-12-31', portefeuilles=PTF + ('SANTE', 'PREVOYANCE')))

    def test_sans_contexte_le_controle_est_IMPOSSIBLE_et_le_dit(self):
        for absent in ({'perimetre': None}, {'contexte': None}):
            with self.assertRaises(RefusMesure, msg=str(absent)) as e:
                _opposable(**absent)
            self.assertEqual(e.exception.motif, MOTIF_CONTEXTE_INVALIDE)
            self.assertIn("IL EST IMPOSSIBLE", str(e.exception))

    def test_un_arrete_hors_ISO_est_refuse_plutot_que_devine(self):
        """⚠️ Parser « 31/12/2026 » ferait passer deux dates pour une."""
        with self.assertRaises(RefusMesure) as e:
            _opposable(perimetre=PerimetreDeclare(arrete='31/12/2026',
                                                  portefeuilles=PTF))
        self.assertIn('AAAA-MM-JJ', str(e.exception))

    def test_la_forme_de_l_arrete_est_STRICTE_et_le_reste(self):
        """⚠️ Un verrou sur la décision « refuser plutôt que deviner ».

        Assouplir cette expression pour accepter « 31/12/2026 » rouvrirait
        le parsing, donc la possibilité que deux dates distinctes soient
        prises pour la même.
        """
        self.assertTrue(FORME_ARRETE.match('2026-12-31'))
        for mauvais in ('31/12/2026', '2026-12-31 ', '26-12-31', '2026-12',
                        '2026/12/31', 'le 31 decembre 2026'):
            self.assertIsNone(FORME_ARRETE.match(mauvais), msg=mauvais)

    def test_un_contexte_sans_portefeuille_est_refuse(self):
        """Sinon la couverture serait suffisante trivialement."""
        with self.assertRaises(RefusMesure) as e:
            _opposable(contexte=ContexteEvaluation(arrete='2026-12-31',
                                                   portefeuilles=()))
        self.assertEqual(e.exception.motif, MOTIF_CONTEXTE_INVALIDE)

    def test_le_contexte_ne_porte_AUCUN_groupe(self):
        """⚠️ LA FRONTIÈRE TIENT : `mesure` ne sait pas quels groupes
        existent, seulement ce qu'on lui demande d'évaluer."""
        self.assertEqual(ContexteEvaluation._fields,
                         ('arrete', 'portefeuilles'))


class T5_LaQuatriemeQuestion_ENSEMBLE(unittest.TestCase):
    """⚠️⚠️ TROIS DÉCLARATIONS VALIDES SÉPARÉMENT, UN JEU FAUX.

    Les trois premiers contrôles portent chacun sur UNE déclaration. Celui-ci
    porte sur l'ENSEMBLE — et le défaut vit entre elles.
    """

    def _jeu(self, a_courbe, a_conv, a_prime):
        return {'courbe': PerimetreDeclare(a_courbe, PTF),
                'convention': PerimetreDeclare(a_conv, PTF),
                'prime_illiquidite': PerimetreDeclare(a_prime, PTF)}

    def test_trois_arretes_differents_sont_refuses(self):
        with self.assertRaises(RefusMesure) as e:
            exiger_ensemble_coherent(
                perimetres=self._jeu('2026-12-31', '2025-12-31', '2024-12-31'),
                contexte=CONTEXTE, erreur=RefusMesure)
        self.assertEqual(e.exception.motif, MOTIF_PERIMETRE_DISCORDANT)
        self.assertIn('3 arrêtés différents', str(e.exception))
        self.assertIn('Le défaut est ENTRE elles', str(e.exception))

    def test_chacune_du_jeu_faux_passe_les_TROIS_premiers_controles(self):
        """⚠️ LA DÉMONSTRATION, ET C'EST ELLE QUI REND LA QUESTION CITABLE.

        Si l'une échouait aux contrôles individuels, le quatrième serait
        superflu. Aucune n'échoue.
        """
        for nom, arrete in (('courbe', '2026-12-31'),
                            ('convention', '2025-12-31'),
                            ('prime', '2024-12-31')):
            exiger_declaration_opposable(
                statut='signee', declarant='directrice technique',
                qualite=QUALITE_ENTITE, erreur=RefusMesure,
                perimetre=PerimetreDeclare(arrete, PTF),
                contexte=ContexteEvaluation(arrete, PTF), objet=nom)

    def test_un_ensemble_coherent_MAIS_PERIME_reste_refuse(self):
        """⚠️ La cohérence ne remplace pas le périmètre, elle s'y ajoute."""
        with self.assertRaises(RefusMesure) as e:
            exiger_ensemble_coherent(
                perimetres=self._jeu('2025-12-31', '2025-12-31', '2025-12-31'),
                contexte=CONTEXTE, erreur=RefusMesure)
        self.assertIn('PÉRIMÉ RESTE PÉRIMÉ', str(e.exception))

    def test_un_ensemble_coherent_et_a_jour_passe(self):
        m = exiger_ensemble_coherent(
            perimetres=self._jeu('2026-12-31', '2026-12-31', '2026-12-31'),
            contexte=CONTEXTE, erreur=RefusMesure)
        self.assertIn('2026-12-31', m)
        self.assertIn("le seul à regarder l'ensemble", m.lower())

    def test_un_ensemble_vide_est_refuse(self):
        """Sinon la cohérence serait constatée trivialement."""
        with self.assertRaises(RefusMesure) as e:
            exiger_ensemble_coherent(perimetres={}, contexte=CONTEXTE,
                                     erreur=RefusMesure)
        self.assertIn('Ran 0 tests', str(e.exception))

    def test_la_demonstration_est_PORTEE_par_le_module(self):
        """⚠️ Citable plutôt que théorique."""
        self.assertIn('2026-12-31', DEMONSTRATION_INCOHERENCE_D_ENSEMBLE)
        self.assertIn('2024-12-31', DEMONSTRATION_INCOHERENCE_D_ENSEMBLE)
        self.assertIn('un seul calcul', DEMONSTRATION_INCOHERENCE_D_ENSEMBLE)


class T6_DeuxCategoriesDeComparaison(unittest.TestCase):
    """⚠️⚠️ UN BALAYAGE UNIFORME SERAIT FAUX SUR DEUX MODULES SUR SIX.

    Une courbe vaut pour LA date évaluée ; un taux verrouillé est figé dans
    le passé par B72 a). Les comparer pareil refuserait un taux correct — et
    un contrôle faux est pire que pas de contrôle.
    """

    def _cmp(self, arrete, comparaison):
        return exiger_arrete_dans_le_contexte(
            arrete=arrete, comparaison=comparaison, contexte=CONTEXTE,
            erreur=RefusMesure, objet='la valeur')

    def test_EGAL_refuse_un_arrete_anterieur(self):
        with self.assertRaises(RefusMesure) as e:
            self._cmp('2025-12-31', COMPARAISON_EGAL)
        self.assertEqual(e.exception.motif, MOTIF_ARRETE_HORS_CONTEXTE)
        self.assertIn('vaut pour UNE date', str(e.exception))

    def test_EGAL_accepte_l_arrete_evalue(self):
        self.assertIn('égal', self._cmp('2026-12-31', COMPARAISON_EGAL))

    def test_ANTERIEUR_accepte_ce_que_EGAL_refuse(self):
        """⚠️ LA PREUVE QUE LES DEUX BRANCHES DIFFÈRENT, sur le MÊME arrêté."""
        with self.assertRaises(RefusMesure):
            self._cmp('2025-12-31', COMPARAISON_EGAL)
        self._cmp('2025-12-31', COMPARAISON_ANTERIEUR_OU_EGAL)

    def test_ANTERIEUR_refuse_un_arrete_POSTERIEUR(self):
        with self.assertRaises(RefusMesure) as e:
            self._cmp('2027-12-31', COMPARAISON_ANTERIEUR_OU_EGAL)
        self.assertIn('POSTÉRIEUR', str(e.exception))

    def test_la_categorie_se_DECLARE_et_ne_se_deduit_pas(self):
        with self.assertRaises(RefusMesure) as e:
            self._cmp('2026-12-31', '')
        self.assertEqual(e.exception.motif, MOTIF_ARRETE_HORS_CONTEXTE)
        self.assertIn('NE SE DÉDUIT PAS DU NOM DU CHAMP', str(e.exception))
        self.assertIn('B72 a)', str(e.exception))

    def test_la_limite_de_ANTERIEUR_descend_avec_le_resultat(self):
        """⚠️ IL NE VÉRIFIE QU'UNE BORNE, ET LE DIT.

        La fenêtre complète du §57 exigerait le début de couverture, que le
        module ne reçoit pas. La limite est NOMMÉE plutôt que comblée par un
        contrôle que les paramètres ne permettent pas.
        """
        m = self._cmp('2025-12-31', COMPARAISON_ANTERIEUR_OU_EGAL)
        self.assertIn(LIMITE_ANTERIEUR_OU_EGAL, m)
        self.assertIn('AU COURS DE', m)
        self.assertIn('ANCIENNE', m)
        self.assertIn('la limite est NOMMÉE', m)

    def test_EGAL_ne_porte_PAS_la_limite_qui_ne_le_concerne_pas(self):
        """Une réserve hors sujet finit par ne plus être lue."""
        self.assertNotIn(LIMITE_ANTERIEUR_OU_EGAL,
                         self._cmp('2026-12-31', COMPARAISON_EGAL))


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
        self.assertIn('2026-12-31', m)

    def test_les_marqueurs_sont_une_liste_fermee(self):
        self.assertIn('demonstration', MARQUEURS_DE_NON_SIGNATURE)
        self.assertIn('a remplacer', MARQUEURS_DE_NON_SIGNATURE)
        self.assertIsInstance(MARQUEURS_DE_NON_SIGNATURE, tuple)


if __name__ == '__main__':
    unittest.main()
