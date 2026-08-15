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
    FORME_DATE_25,
    FORME_MOYENNE_B73,
    FORMES_DU_TAUX_VERROUILLE,
    LIMITE_ANTERIEUR_OU_EGAL,
    LIMITE_DES_DEUX_FORMES,
    LIMITE_INTERVALLE_PAR_FORME,
    MARQUEURS_DE_NON_SIGNATURE,
    MOTIF_ARRETE_HORS_CONTEXTE,
    MOTIF_COHORTE_NON_DECLAREE,
    MOTIF_CONTEXTE_INVALIDE,
    MOTIF_DECLARANT_NON_HABILITE,
    MOTIF_FORME_DU_TAUX_NON_DECLAREE,
    MOTIF_HORS_INTERVALLE_EMISSION,
    MOTIF_PERIMETRE_DISCORDANT,
    MOTIF_PONDERATION_NON_DECLAREE,
    MOTIF_STATUT_NON_SIGNE,
    MOTIF_TAUX_HORS_COHORTE,
    MOTIF_USAGE_NON_DECLARE,
    QUALITE_ENTITE,
    QUALITE_TIERS,
    QUALITES,
    RAISONNEMENT_COHORTE_ANNUELLE,
    RESERVE_MOYENNE_DE_TAUX,
    USAGE_COURANT,
    USAGE_VERROUILLE,
    ContexteEvaluation,
    PerimetreDeclare,
    exiger_arrete_dans_le_contexte,
    exiger_declaration_opposable,
    exiger_ensemble_coherent,
    exiger_taux_de_la_cohorte,
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
    le passé par B72 d). Les comparer pareil refuserait un taux correct — et
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
        self.assertIn('B72 d)', str(e.exception))

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


class T7_LaCoherenceSeJugePARUSAGE(unittest.TestCase):
    """⚠️⚠️ CE CONTRÔLE REFUSAIT UNE DÉCLARATION CORRECTE.

    Il exigeait UN SEUL arrêté pour tout l'ensemble. Or §22 impose des
    cohortes ANNUELLES : un portefeuille de trois cohortes appelle TROIS taux
    verrouillés (B72 d) plus un taux courant (B72 a). Quatre arrêtés, et le
    tout cohérent. **Une exigence FAUSSE bloque** — c'est le défaut le plus
    visible, et le plus vite payé.
    """

    QUATRE = {'courant': PerimetreDeclare('2026-12-31', PTF),
              'verr_2024': PerimetreDeclare('2024-12-31', PTF),
              'verr_2025': PerimetreDeclare('2025-12-31', PTF),
              'verr_2026': PerimetreDeclare('2026-12-31', PTF)}
    USAGES = {'courant': USAGE_COURANT, 'verr_2024': USAGE_VERROUILLE,
              'verr_2025': USAGE_VERROUILLE, 'verr_2026': USAGE_VERROUILLE}

    def _ensemble(self, per=None, us=None):
        return exiger_ensemble_coherent(
            perimetres=per or self.QUATRE, contexte=CONTEXTE,
            erreur=RefusMesure, usages=self.USAGES if us is None else us)

    def test_quatre_jeux_a_quatre_arretes_sont_COHERENTS(self):
        m = self._ensemble()
        self.assertIn("1 d'usage COURANT", m)
        self.assertIn('3 VERROUILLÉ', m)

    def test_le_motif_dit_pourquoi_des_arretes_differents_se_tiennent(self):
        m = self._ensemble()
        self.assertIn('SE JUGE PAR USAGE', m)
        self.assertIn('cohortes annuelles', m)

    def test_un_COURANT_perime_reste_refuse(self):
        """⚠️ L'assouplissement ne doit pas ouvrir l'autre porte."""
        with self.assertRaises(RefusMesure) as e:
            self._ensemble({**self.QUATRE,
                            'courant': PerimetreDeclare('2025-12-31', PTF)})
        self.assertIn('B72 a)', str(e.exception))

    def test_un_VERROUILLE_dans_le_FUTUR_est_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            self._ensemble({**self.QUATRE,
                            'verr_2024': PerimetreDeclare('2027-12-31', PTF)})
        self.assertIn('POSTÉRIEUR', str(e.exception))

    def test_deux_verrouilles_au_MEME_arrete_signalent_une_cohorte_oubliee(self):
        """⚠️ §22 impose des cohortes annuelles : un doublon d'arrêté est
        soit un doublon, soit une cohorte manquante."""
        with self.assertRaises(RefusMesure) as e:
            self._ensemble({**self.QUATRE,
                            'verr_2025': PerimetreDeclare('2024-12-31', PTF)})
        self.assertIn('cohorte oubliée', str(e.exception))

    def test_un_usage_non_declare_est_refuse(self):
        us = {k: v for k, v in self.USAGES.items() if k != 'verr_2026'}
        with self.assertRaises(RefusMesure) as e:
            self._ensemble(us=us)
        self.assertEqual(e.exception.motif, MOTIF_USAGE_NON_DECLARE)

    def test_SANS_usages_l_ancienne_regle_tient(self):
        """⚠️ Ce n'est pas un défaut à None : c'est le cas où toutes les
        déclarations servent le même usage, et il reste le plus fréquent."""
        with self.assertRaises(RefusMesure) as e:
            self._ensemble(us={})
        self.assertEqual(e.exception.motif, MOTIF_PERIMETRE_DISCORDANT)

    def test_le_motif_dit_CE_QU_IL_NE_VERIFIE_PAS(self):
        """⚠️ Il ne sait pas si chaque taux porte l'arrêté de SA cohorte."""
        self.assertIn('NE VÉRIFIE PAS', self._ensemble())
        self.assertIn('ne connaît pas les cohortes', self._ensemble())


class T8_LeTauxVERROUILLE_APPARTIENT_A_SA_COHORTE(unittest.TestCase):
    """⚠️⚠️ « ANTÉRIEUR OU ÉGAL » ACCEPTAIT UN TAUX DE 2020 POUR UNE COHORTE
    2024. Il ne vérifiait qu'une borne, la haute — la limite était nommée, et
    c'est ici qu'elle mordait."""

    #: L'intervalle réel de la cohorte DO 2024 du banc local.
    INTERVALLE = ('2024-01-11', '2024-12-25')
    PONDERATION = 'par la prime, la composante §56 s accretant sur elle'

    def _cohorte(self, arrete, cohorte, forme=FORME_DATE_25, **kw):
        base = {'arrete_verrouillage': arrete, 'cohorte': cohorte,
                'contexte': CONTEXTE, 'erreur': RefusMesure, 'forme': forme}
        if forme == FORME_MOYENNE_B73:
            base.setdefault('intervalle_emission', self.INTERVALLE)
            base.setdefault('ponderation_declaree', self.PONDERATION)
        base.update(kw)
        return exiger_taux_de_la_cohorte(**base)

    def test_le_taux_de_SA_cohorte_passe(self):
        m = self._cohorte('2024-12-31', '2024')
        self.assertIn('cohorte 2024', m)

    def test_le_cas_QUE_LA_BORNE_LACHE_LAISSAIT_PASSER(self):
        """⚠️ 2020 pour une cohorte 2024 : antérieur, donc admis avant."""
        with self.assertRaises(RefusMesure) as e:
            self._cohorte('2020-01-01', '2024')
        self.assertEqual(e.exception.motif, MOTIF_TAUX_HORS_COHORTE)
        self.assertIn('une AUTRE cohorte', str(e.exception))
        self.assertIn('2020', str(e.exception))

    def test_un_taux_POSTERIEUR_a_l_evaluation_reste_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            self._cohorte('2027-06-30', '2027')
        self.assertIn('POSTÉRIEUR', str(e.exception))

    def test_sans_cohorte_declaree_le_module_refuse(self):
        """⚠️ Sans elle, toute comparaison serait une supposition."""
        for c in ('', '24', '2024-12-31', 'A_RENSEIGNER'):
            with self.assertRaises(RefusMesure, msg=c) as e:
                self._cohorte('2024-12-31', c)
            self.assertEqual(e.exception.motif, MOTIF_COHORTE_NON_DECLAREE)

    def test_le_jour_DANS_l_annee_de_la_cohorte_est_indifferent(self):
        """⚠️ L'ARBITRAGE : l'ANNÉE, pas la date exacte."""
        for jour in ('2024-01-01', '2024-06-30', '2024-12-31'):
            self._cohorte(jour, '2024')

    def test_l_appui_est_B73_ET_LE_PREMIER_ETAIT_FAUX(self):
        """⚠️⚠️ LE §22 AVAIT ÉTÉ INVOQUÉ À TORT.

        §22 plafonne l'ÉTENDUE d'un groupe — pas de contrats émis à plus d'un
        an d'intervalle — et ne dit RIEN de la date d'un taux ; celle-ci
        relève du §25. B73 est l'appui direct : il autorise « des taux
        MOYENS PONDÉRÉS pour l'intervalle de temps au cours duquel sont émis
        les contrats du groupe », pour les taux de B72 b) à e).
        """
        m = self._cohorte('2024-12-31', '2024')
        self.assertIn(RAISONNEMENT_COHORTE_ANNUELLE, m)
        self.assertIn('B73', m)
        self.assertIn('MOYENS PONDÉRÉS', m)
        self.assertIn('À TORT', m)

    def test_la_FORME_du_taux_se_declare_et_ne_se_devine_pas(self):
        """⚠️ B73 dit « PEUT » : deux formes légitimes, dates différentes."""
        with self.assertRaises(RefusMesure) as e:
            self._cohorte('2024-12-31', '2024', forme='')
        self.assertEqual(e.exception.motif, MOTIF_FORME_DU_TAUX_NON_DECLAREE)
        self.assertIn('supposer une méthode', str(e.exception))

    def test_les_deux_formes_sont_acceptees(self):
        for f in FORMES_DU_TAUX_VERROUILLE:
            self.assertIn(f, self._cohorte('2024-06-30', '2024', forme=f))

    def test_l_intervalle_refuse_EXACTEMENT_pour_B73(self):
        """⚠️ CE REFUS N'EST PAS PRUDENTIEL : une moyenne pondérée de
        valeurs de [a ; b] est NÉCESSAIREMENT dans [a ; b]."""
        with self.assertRaises(RefusMesure) as e:
            self._cohorte('2024-01-05', '2024', forme=FORME_MOYENNE_B73)
        self.assertEqual(e.exception.motif, MOTIF_HORS_INTERVALLE_EMISSION)
        self.assertIn('EXACT, PAS PRUDENTIEL', str(e.exception))

    def test_la_date_ponderee_REELLE_de_DO_2024_passe(self):
        """Sa déclaration : 2024-07-20, dans [11/01 ; 25/12]."""
        self._cohorte('2024-07-20', '2024', forme=FORME_MOYENNE_B73)

    def test_l_intervalle_n_est_PAS_oppose_a_la_forme_25(self):
        """⚠️ §25 retient la PREMIÈRE de trois dates, dont aucune n'est
        bornée par l'émission — l'y contraindre refuserait du correct."""
        m = self._cohorte('2024-01-05', '2024', forme=FORME_DATE_25)
        self.assertIn(LIMITE_INTERVALLE_PAR_FORME, m)
        self.assertIn('refuserait du correct', m)
        self.assertIn('PREMIÈRE de trois dates', m)

    def test_B73_sans_intervalle_est_refuse_et_le_refus_dit_pourquoi(self):
        """⚠️ Qui a calculé une moyenne AVAIT les dates."""
        with self.assertRaises(RefusMesure) as e:
            self._cohorte('2024-07-20', '2024', forme=FORME_MOYENNE_B73,
                          intervalle_emission=None)
        self.assertEqual(e.exception.motif, MOTIF_HORS_INTERVALLE_EMISSION)
        self.assertIn('AVAIT NÉCESSAIREMENT ces dates', str(e.exception))

    def test_B73_sans_PONDERATION_est_refuse(self):
        """⚠️ Prime, nombre, flux : trois pondérations, trois dates."""
        with self.assertRaises(RefusMesure) as e:
            self._cohorte('2024-07-20', '2024', forme=FORME_MOYENNE_B73,
                          ponderation_declaree='')
        self.assertEqual(e.exception.motif, MOTIF_PONDERATION_NON_DECLAREE)
        self.assertIn('3 à 9', str(e.exception))

    def test_la_RESERVE_moyenne_de_TAUX_descend_sur_B73_seulement(self):
        """⚠️ T3 : une limite non dite se fait surévaluer."""
        b73 = self._cohorte('2024-07-20', '2024', forme=FORME_MOYENNE_B73)
        self.assertIn(RESERVE_MOYENNE_DE_TAUX, b73)
        self.assertIn('MOYENNE DE TAUX, PAS UNE DATE MOYENNE', b73)
        self.assertNotIn(RESERVE_MOYENNE_DE_TAUX,
                         self._cohorte('2024-01-11', '2024'))

    def test_une_MOYENNE_au_31_decembre_est_SIGNALEE_pas_refusee(self):
        """⚠️ Elle n'est possible que si tous les contrats ont été émis ce
        jour-là. Refuser bloquerait un cas légitime ; taire laisserait passer
        le taux de FIN d'année déguisé en moyenne."""
        m = self._cohorte('2024-12-31', '2024', forme=FORME_MOYENNE_B73,
                          intervalle_emission=('2024-01-11', '2024-12-31'))
        self.assertIn('SIGNALEMENT, NON REFUS', m)
        self.assertIn('émis ce jour-là', m)

    def test_la_meme_date_en_forme_25_n_est_PAS_signalee(self):
        """La date du §25 peut légitimement tomber le 31 décembre."""
        m = self._cohorte('2024-12-31', '2024', forme=FORME_DATE_25)
        self.assertNotIn('SIGNALEMENT', m)

    def test_la_LIMITE_des_deux_formes_est_nommee(self):
        """⚠️ NI L'UNE NI L'AUTRE N'EST RECALCULABLE ICI, et le dire vaut
        mieux que bâtir un contrôle que les paramètres ne permettent pas."""
        m = self._cohorte('2024-06-30', '2024')
        self.assertIn(LIMITE_DES_DEUX_FORMES, m)
        self.assertIn('NE RECALCULE NI', m)
        self.assertIn("responsabilité de l'entité", m)

    def test_le_motif_dit_que_B73_est_une_FACULTE(self):
        """⚠️ « PEUT » : deux formes légitimes, et elles ne donnent pas la
        même date — celle du §25, ou la moyenne pondérée de B73."""
        m = self._cohorte('2024-12-31', '2024')
        self.assertIn('« PEUT »', m)
        self.assertIn('§25', m)

    def test_le_motif_dit_que_le_controle_N_EXIGE_NI_L_UNE_NI_L_AUTRE(self):
        """⚠️ PLUS LARGE QU'UN ARBITRAGE : il accepte toute date de l'année.

        Le 31 décembre est le taux de FIN d'année ; une moyenne pondérée sur
        des émissions quasi uniformes tombe vers le milieu.
        """
        m = self._cohorte('2024-12-31', '2024')
        self.assertIn("NI l'une NI l'autre", m)
        self.assertIn("FIN d'année", m)
        self.assertIn('pas cosmétique', m)

    def test_le_22_n_est_PLUS_invoque_comme_appui(self):
        """⚠️ VERROU DANS L'AUTRE SENS : le §22 ne doit revenir que comme
        ce qu'il est — un plafond d'étendue, jamais un fondement de date."""
        m = self._cohorte('2024-12-31', '2024')
        self.assertNotIn('§22 la rend suffisante', m)
        self.assertNotIn("granularité qu'elle ne demande pas", m)
        self.assertIn("plafonne l'ÉTENDUE", m)


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
