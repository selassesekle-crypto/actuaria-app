# -*- coding: utf-8 -*-
"""Tests — l'opposabilité d'une déclaration : signée, et PAR QUI.

⚠️ LE CALIBRAGE VIT ICI, comme celui de `PLACEHOLDERS` et celui du néant
motivé. Un contrôle sur du texte qui n'exhibe pas ses deux taux d'erreur se
fait croire sur parole.
"""

import unittest

from normes.ifrs17.mesure.declaration import (
    CE_QUE_L_EXACTITUDE_FERME,
    COMPARAISON_ANTERIEUR_OU_EGAL,
    COMPARAISON_EGAL,
    DEMONSTRATION_INCOHERENCE_D_ENSEMBLE,
    FORME_ARRETE,
    FORME_DATE_25,
    FORME_MOYENNE_B73,
    FORMES_DU_TAUX_VERROUILLE,
    LIMITE_ANTERIEUR_OU_EGAL,
    LIMITE_DES_DEUX_FORMES,
    LIMITE_DU_DOUBLON,
    LIMITE_INTERVALLE_PAR_FORME,
    MARQUEURS_DE_NON_SIGNATURE,
    MOTIF_ARRETE_HORS_CONTEXTE,
    MOTIF_COHORTE_NON_DECLAREE,
    MOTIF_CONTEXTE_INVALIDE,
    MOTIF_DECLARANT_NON_HABILITE,
    MOTIF_FORME_DU_TAUX_NON_DECLAREE,
    MOTIF_GROUPE_NON_DECLARE,
    MOTIF_HORS_INTERVALLE_EMISSION,
    MOTIF_PERIMETRE_DISCORDANT,
    MOTIF_PONDERATION_NON_DECLAREE,
    MOTIF_STATUT_NON_SIGNE,
    MOTIF_TAUX_HORS_COMPTABILISATION_25,
    MOTIF_TAUX_POSTERIEUR_A_L_EVALUATION,
    MOTIF_USAGE_NON_DECLARE,
    QUALITE_ENTITE,
    QUALITE_TIERS,
    QUALITES,
    RAISONNEMENT_DES_DEUX_AXES,
    RESERVE_MOYENNE_DE_TAUX,
    USAGE_COURANT,
    USAGE_VERROUILLE,
    ContexteEvaluation,
    GroupeEvalue,
    PerimetreDeclare,
    exiger_arrete_dans_le_contexte,
    exiger_declaration_opposable,
    exiger_ensemble_coherent,
    exiger_taux_verrouille_du_groupe,
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

    Il exigeait UN SEUL arrêté pour tout l'ensemble. Or §22 borne l'étendue
    d'un groupe à un an d'ÉMISSIONS : un portefeuille de trois cohortes
    appelle TROIS taux verrouillés (B72 d) plus un taux courant (B72 a).
    Quatre arrêtés, et le tout cohérent. **Une exigence FAUSSE bloque** —
    c'est le défaut le plus visible, et le plus vite payé.
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

    def test_deux_verrouilles_au_MEME_arrete_sont_refuses(self):
        """⚠️ Le cas ordinaire est un doublon, ou un groupe dont le taux
        manque. Le refus TIENT — mais sa portée est nommée : voir le test
        suivant."""
        with self.assertRaises(RefusMesure) as e:
            self._ensemble({**self.QUATRE,
                            'verr_2025': PerimetreDeclare('2024-12-31', PTF)})
        self.assertIn('un doublon', str(e.exception))

    def test_le_refus_du_doublon_NOMME_son_faux_rejet_possible(self):
        """⚠️⚠️ TROUVÉ PAR LE BALAYAGE EN PROSE, PAS PAR LES SYMBOLES. Sa
        justification d'origine — « §22 impose des cohortes annuelles » —
        était du MÊME axe faux que le défaut principal de ce lot. Deux
        groupes PEUVENT se comptabiliser le même jour. Le refus est maintenu
        (le corriger relève du comportement) et sa limite est écrite."""
        with self.assertRaises(RefusMesure) as e:
            self._ensemble({**self.QUATRE,
                            'verr_2025': PerimetreDeclare('2024-12-31', PTF)})
        self.assertIn(LIMITE_DU_DOUBLON, str(e.exception))
        self.assertIn('faux rejet POSSIBLE', str(e.exception))
        self.assertIn('MÊME axe faux', str(e.exception))

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
        """⚠️ Il ne sait pas si chaque taux porte la date de comptabilisation
        initiale de SON groupe — il ne connaît pas les groupes évalués."""
        self.assertIn('NE VÉRIFIE PAS', self._ensemble())
        self.assertIn('ne connaît pas les groupes', self._ensemble())
        self.assertIn(LIMITE_DU_DOUBLON, self._ensemble())


class T8_LaCohorteEtLeTauxSontDEUX_AXES(unittest.TestCase):
    """⚠️⚠️ CE CONTRÔLE EXIGEAIT L'ANNÉE DE LA COHORTE, ET IL REFUSAIT DU
    CORRECT. La cohorte suit l'ÉMISSION (§22), le taux verrouillé suit la
    COMPTABILISATION INITIALE (B72 d) + §25), et aucune des deux ne borne
    l'autre — dans aucun des deux sens.

    ⚠️ LES CAS DE CETTE CLASSE SONT MESURÉS SUR LE BANC LOCAL, PAS INVENTÉS :
    2 groupes sur 18 étaient refusés à tort, et 116 contrats sur 2 005 ont une
    date §25 dans une autre année que leur émission.
    """

    #: L'intervalle réel de la cohorte DO 2024 du banc local.
    INTERVALLE = ('2024-01-11', '2024-12-25')
    PONDERATION = 'par la prime, la composante §56 s accretant sur elle'
    #: DO 2024 : émissions du 11/01 au 25/12, comptabilisation le 11/01.
    DO_2024 = GroupeEvalue(cohorte='2024', date_25='2024-01-11',
                           intervalle_emission=INTERVALLE)

    def _taux(self, arrete, groupe=None, forme=FORME_DATE_25, **kw):
        base = {'arrete_verrouillage': arrete, 'groupe': groupe or self.DO_2024,
                'contexte': CONTEXTE, 'erreur': RefusMesure, 'forme': forme}
        if forme == FORME_MOYENNE_B73:
            base.setdefault('ponderation_declaree', self.PONDERATION)
        base.update(kw)
        return exiger_taux_verrouille_du_groupe(**base)

    # -- LES DEUX SENS QUI ÉTAIENT REFUSÉS À TORT --------------------------

    def test_une_COUVERTURE_RETROACTIVE_passe_desormais(self):
        """⚠️⚠️ LE CAS RÉEL N° 1, MESURÉ : GAV cohorte 2026, comptabilisé le
        27/12/2025. L'ancien contrôle exigeait un arrêté en 2026 et refusait
        ce groupe — un des 2 sur 18 du banc local."""
        g = GroupeEvalue(cohorte='2026', date_25='2025-12-27')
        m = self._taux('2025-12-27', g)
        self.assertIn('cohorte 2026', m)
        self.assertIn('2025-12-27', m)

    def test_une_PRODUCTION_DE_DECEMBRE_passe_desormais(self):
        """⚠️⚠️ LE CAS RÉEL N° 2, MESURÉ : DO, 3 contrats émis du 01/12 au
        25/12/2024 — cohorte 2024 — comptabilisés le 08/01/2025. C'est le
        sens le plus courant : 91 des 116 écarts viennent de §25 b)."""
        g = GroupeEvalue(cohorte='2024', date_25='2025-01-08')
        m = self._taux('2025-01-08', g)
        self.assertIn('cohorte 2024', m)
        self.assertIn('2025-01-08', m)

    def test_le_motif_dit_LES_DEUX_AXES_et_le_prix_mesure(self):
        m = self._taux('2024-01-11')
        self.assertIn(RAISONNEMENT_DES_DEUX_AXES, m)
        self.assertIn('DEUX AXES', m)
        self.assertIn('2 groupes sur 18', m)
        self.assertIn('116 contrats sur 2 005', m)

    # -- CE QUE L'EXACTITUDE FERME, ET QUI PASSAIT AVANT -------------------

    def test_la_forme_25_EXIGE_LA_DATE_du_25_pas_l_annee(self):
        """⚠️⚠️ LE TROU QUI ÉTAIT NOMMÉ SANS ÊTRE FERMÉ. L'ancien contrôle
        acceptait TOUTE date de l'année : c'est ce qui a laissé passer la
        première déclaration du producteur — taux au 31/12/2024 pour un
        groupe comptabilisé le 11/01/2024."""
        with self.assertRaises(RefusMesure) as e:
            self._taux('2024-12-31')
        self.assertEqual(e.exception.motif,
                         MOTIF_TAUX_HORS_COMPTABILISATION_25)
        self.assertIn('2024-01-11', str(e.exception))
        self.assertIn('APPROXIMATION', str(e.exception))

    def test_le_refus_du_25_DIT_QU_IL_N_EST_PAS_UN_CONTROLE_DE_COHORTE(self):
        """⚠️ Sans quoi le lecteur referait la confusion qu'on vient de
        défaire — et « corrigerait » en alignant sur la cohorte."""
        with self.assertRaises(RefusMesure) as e:
            self._taux('2024-12-31')
        self.assertIn("PAS un contrôle de cohorte", str(e.exception))

    def test_le_motif_dit_CE_QUE_L_EXACTITUDE_FERME(self):
        m = self._taux('2024-01-11')
        self.assertIn(CE_QUE_L_EXACTITUDE_FERME, m)
        self.assertIn('dans les deux sens', m)

    def test_le_cas_de_2020_reste_refuse_PAR_LA_BONNE_RAISON(self):
        """⚠️ Il l'était pour une raison fausse — « autre cohorte ». Il l'est
        maintenant parce que ce n'est pas la date de comptabilisation."""
        with self.assertRaises(RefusMesure) as e:
            self._taux('2020-01-01')
        self.assertEqual(e.exception.motif,
                         MOTIF_TAUX_HORS_COMPTABILISATION_25)

    # -- CE QUI SURVIT INCHANGÉ -------------------------------------------

    def test_un_taux_POSTERIEUR_a_l_evaluation_reste_refuse(self):
        g = GroupeEvalue(cohorte='2027', date_25='2027-06-30')
        with self.assertRaises(RefusMesure) as e:
            self._taux('2027-06-30', g)
        self.assertEqual(e.exception.motif,
                         MOTIF_TAUX_POSTERIEUR_A_L_EVALUATION)
        self.assertIn('POSTÉRIEUR', str(e.exception))

    def test_sans_GROUPE_declare_le_module_refuse(self):
        """⚠️ Un taux verrouillé se rattache à UN groupe ; sans lui, toute
        comparaison serait une supposition. L'appel contourne l'aide de la
        classe, qui substitue le groupe par défaut."""
        with self.assertRaises(RefusMesure) as e:
            exiger_taux_verrouille_du_groupe(
                arrete_verrouillage='2024-01-11', groupe=None,
                contexte=CONTEXTE, erreur=RefusMesure, forme=FORME_DATE_25)
        self.assertEqual(e.exception.motif, MOTIF_GROUPE_NON_DECLARE)
        self.assertIn('DEUX AXES', str(e.exception))

    def test_une_cohorte_malformee_est_refusee(self):
        for c in ('', '24', '2024-12-31', 'A_RENSEIGNER'):
            g = GroupeEvalue(cohorte=c, date_25='2024-01-11')
            with self.assertRaises(RefusMesure, msg=c) as e:
                self._taux('2024-01-11', g)
            self.assertEqual(e.exception.motif, MOTIF_COHORTE_NON_DECLAREE)

    def test_une_date_25_malformee_est_refusee(self):
        for d in ('', '11/01/2024', 'A_RENSEIGNER'):
            g = GroupeEvalue(cohorte='2024', date_25=d)
            with self.assertRaises(RefusMesure, msg=d) as e:
                self._taux('2024-01-11', g)
            self.assertEqual(e.exception.motif,
                             MOTIF_TAUX_HORS_COMPTABILISATION_25)

    def test_la_FORME_du_taux_se_declare_et_ne_se_devine_pas(self):
        """⚠️ B73 dit « PEUT » : deux formes légitimes, dates différentes."""
        with self.assertRaises(RefusMesure) as e:
            self._taux('2024-01-11', forme='')
        self.assertEqual(e.exception.motif, MOTIF_FORME_DU_TAUX_NON_DECLAREE)
        self.assertIn('supposer une méthode', str(e.exception))

    def test_les_deux_formes_sont_acceptees_ET_IL_N_Y_EN_A_QUE_DEUX(self):
        """⚠️ L'ARITÉ SE VÉRIFIE À PART. B73 dit « PEUT » et n'ouvre qu'UNE
        alternative à B72 d) : une troisième forme ajoutée sans son appui au
        texte passerait ici sans que rien ne le dise."""
        self.assertEqual(FORMES_DU_TAUX_VERROUILLE,
                         (FORME_DATE_25, FORME_MOYENNE_B73))
        self.assertIn(FORME_DATE_25, self._taux('2024-01-11'))
        self.assertIn(FORME_MOYENNE_B73,
                      self._taux('2024-07-20', forme=FORME_MOYENNE_B73))

    # -- U2 : L'INTERVALLE RESTE OPPOSÉ À B73, ET À ELLE SEULE -------------

    def test_l_intervalle_refuse_EXACTEMENT_pour_B73(self):
        """⚠️ CE REFUS N'EST PAS PRUDENTIEL : une moyenne pondérée de
        valeurs de [a ; b] est NÉCESSAIREMENT dans [a ; b]."""
        with self.assertRaises(RefusMesure) as e:
            self._taux('2024-01-05', forme=FORME_MOYENNE_B73)
        self.assertEqual(e.exception.motif, MOTIF_HORS_INTERVALLE_EMISSION)
        self.assertIn('EXACT, PAS PRUDENTIEL', str(e.exception))

    def test_la_date_ponderee_REELLE_de_DO_2024_passe(self):
        """Sa déclaration : 2024-07-20, dans [11/01 ; 25/12]."""
        self._taux('2024-07-20', forme=FORME_MOYENNE_B73)

    def test_l_intervalle_n_est_PAS_oppose_a_la_forme_25(self):
        """⚠️⚠️ U2 : l'intervalle borne B73 et RIEN D'AUTRE. §25 retient la
        PREMIÈRE de trois dates, dont aucune n'est bornée par l'émission —
        l'y contraindre refuserait du correct, et c'est exactement ce que les
        deux cas mesurés ci-dessus démontrent."""
        g = GroupeEvalue(cohorte='2024', date_25='2025-01-08',
                         intervalle_emission=('2024-12-01', '2024-12-25'))
        m = self._taux('2025-01-08', g)
        self.assertIn(LIMITE_INTERVALLE_PAR_FORME, m)
        self.assertIn('refuserait du correct', m)
        self.assertIn('PREMIÈRE de trois dates', m)

    def test_B73_sans_intervalle_est_refuse_et_le_refus_dit_pourquoi(self):
        """⚠️ Qui a calculé une moyenne AVAIT les dates."""
        g = GroupeEvalue(cohorte='2024', date_25='2024-01-11')
        with self.assertRaises(RefusMesure) as e:
            self._taux('2024-07-20', g, forme=FORME_MOYENNE_B73)
        self.assertEqual(e.exception.motif, MOTIF_HORS_INTERVALLE_EMISSION)
        self.assertIn('AVAIT NÉCESSAIREMENT ces dates', str(e.exception))

    def test_B73_sans_PONDERATION_est_refuse(self):
        """⚠️ Prime, nombre, flux : trois pondérations, trois dates."""
        with self.assertRaises(RefusMesure) as e:
            self._taux('2024-07-20', forme=FORME_MOYENNE_B73,
                       ponderation_declaree='')
        self.assertEqual(e.exception.motif, MOTIF_PONDERATION_NON_DECLAREE)
        self.assertIn('3 à 9', str(e.exception))

    def test_la_RESERVE_moyenne_de_TAUX_descend_sur_B73_seulement(self):
        """⚠️ T3 : une limite non dite se fait surévaluer."""
        b73 = self._taux('2024-07-20', forme=FORME_MOYENNE_B73)
        self.assertIn(RESERVE_MOYENNE_DE_TAUX, b73)
        self.assertIn('MOYENNE DE TAUX, PAS UNE DATE MOYENNE', b73)
        self.assertNotIn(RESERVE_MOYENNE_DE_TAUX, self._taux('2024-01-11'))

    def test_une_MOYENNE_au_31_decembre_est_SIGNALEE_pas_refusee(self):
        """⚠️ Elle n'est possible que si tous les contrats ont été émis ce
        jour-là. Refuser bloquerait un cas légitime ; taire laisserait passer
        le taux de FIN d'année déguisé en moyenne."""
        g = GroupeEvalue(cohorte='2024', date_25='2024-01-11',
                         intervalle_emission=('2024-01-11', '2024-12-31'))
        m = self._taux('2024-12-31', g, forme=FORME_MOYENNE_B73)
        self.assertIn('SIGNALEMENT, NON REFUS', m)
        self.assertIn('émis ce jour-là', m)

    def test_la_meme_date_en_forme_25_n_est_PAS_signalee(self):
        """La date du §25 peut légitimement tomber le 31 décembre."""
        g = GroupeEvalue(cohorte='2024', date_25='2024-12-31')
        self.assertNotIn('SIGNALEMENT', self._taux('2024-12-31', g))

    def test_la_LIMITE_des_deux_formes_est_nommee(self):
        """⚠️ NI L'UNE NI L'AUTRE N'EST RECALCULABLE ICI, et le dire vaut
        mieux que bâtir un contrôle que les paramètres ne permettent pas."""
        m = self._taux('2024-01-11')
        self.assertIn(LIMITE_DES_DEUX_FORMES, m)
        self.assertIn('NE RECALCULE NI', m)
        self.assertIn("responsabilité de l'entité", m)

    def test_le_22_n_est_PLUS_invoque_comme_BORNE_du_taux(self):
        """⚠️⚠️ VERROU DANS L'AUTRE SENS, ET IL A DÉJÀ SERVI DEUX FOIS. Le
        §22 est revenu deux fois comme fondement — d'abord comme appui de
        l'année, puis comme borne. Il ne doit revenir que comme ce qu'il est :
        la règle d'ÉMISSION qui constitue la cohorte."""
        m = self._taux('2024-01-11')
        self.assertNotIn('§22 la rend suffisante', m)
        self.assertNotIn("granularité qu'elle ne demande pas", m)
        self.assertNotIn("CE CONTRÔLE RETIENT L'ANNÉE", m)
        self.assertIn("§22, l'émission", m)


class T8b_LEtiquetteDeCohorteSuitLaCONVENTION(unittest.TestCase):
    """⚠️⚠️ `^\\d{4}$` REFUSAIT UNE ÉTIQUETTE CORRECTE. Le socle produit
    « 2024-25 » sous exercice décalé — `convention_exercice(4)` — et ce module
    la rejetait. Même famille que le défaut principal du lot : un contrôle qui
    suppose une forme au lieu de suivre son producteur.

    ⚠️ La correspondance elle-même est verrouillée DANS LE SOCLE, qui produit
    l'étiquette ; ici on ne vérifie que ce que la mesure accepte.
    """

    def test_l_annee_civile_et_l_exercice_decale_passent(self):
        for c in ('2024', '2024-25'):
            g = GroupeEvalue(cohorte=c, date_25='2024-04-02')
            m = exiger_taux_verrouille_du_groupe(
                arrete_verrouillage='2024-04-02', groupe=g,
                contexte=CONTEXTE, erreur=RefusMesure, forme=FORME_DATE_25)
            self.assertIn(f'cohorte {c}', m)

    def test_ce_qui_n_est_PAS_une_etiquette_reste_refuse(self):
        """⚠️ Élargir n'est pas ouvrir : un arrêté glissé à la place d'une
        cohorte, ou une année tronquée, restent des erreurs d'appelant."""
        for c in ('2024-12-31', '24', '2024-2025'):
            g = GroupeEvalue(cohorte=c, date_25='2024-04-02')
            with self.assertRaises(RefusMesure, msg=c) as e:
                exiger_taux_verrouille_du_groupe(
                    arrete_verrouillage='2024-04-02', groupe=g,
                    contexte=CONTEXTE, erreur=RefusMesure,
                    forme=FORME_DATE_25)
            self.assertEqual(e.exception.motif, MOTIF_COHORTE_NON_DECLAREE)


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
