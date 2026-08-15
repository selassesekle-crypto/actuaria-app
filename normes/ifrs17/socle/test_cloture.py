# -*- coding: utf-8 -*-
"""Tests M1 — le magasin de clôtures, et ce qu'il refuse.

⚠️ GATE : `py -m unittest discover -s normes -t .` — voir test_contrat.py.

⚠️ CE QUI SE VÉRIFIE ICI VIENT D'UNE LECTURE, PAS D'UNE INTUITION. Les quatre
axes, le vocabulaire des postes et la case ouverte du §105 d) ont été relevés
dans le règlement (UE) 2023/1803 avant d'être codés — et le relevé a corrigé
le dessin deux fois.
"""
import ast
import shutil
import unittest
from pathlib import Path

from normes.ifrs17.mesure.declaration import (
    QUALITE_ENTITE,
    QUALITE_TIERS,
    ContexteEvaluation,
)
from normes.ifrs17.socle.cloture import (
    AXE_DECLARE,
    AXE_ELEMENT_DE_PERTE,
    AXE_LIC_AJUSTEMENT_RISQUE,
    AXE_LIC_FLUX_FUTURS,
    AXE_LRC_HORS_PERTE,
    AXES,
    FORMAT_CLOTURES,
    LIMITE_DE_LA_CHAINE,
    MOTIF_ARRETE_INVALIDE,
    MOTIF_ARTICULATION_ROMPUE,
    MOTIF_AXE_NON_DECLARE,
    MOTIF_CHAINE_ROMPUE,
    MOTIF_DOSSIER_ABSENT,
    MOTIF_FORMAT_INCONNU,
    MOTIF_LIBELLE_MANQUANT,
    MOTIF_NATURE_DIVERGENTE,
    MOTIF_NATURE_NON_DECLAREE,
    MOTIF_OUVERTURE_NON_SIGNEE,
    MOTIF_POSTE_INCONNU,
    MOTIF_VERSION_SANS_MOTIF,
    NATURE_EMIS,
    NATURE_REASSURANCE_DETENUE,
    NATURES,
    POSTE_AUTRE,
    POSTES,
    PRESENCE_CONDITIONNELLE,
    SIGNATURE_INOPPOSABLE,
    SIGNATURE_OPPOSABLE,
    CleCloture,
    Mouvement,
    RefusCloture,
    Soldes,
    apposer,
    chainer,
    constituer,
    deposer,
    dossier_courant,
    ecrire,
    ouvrir,
    relire,
    resume,
    servir_comme_ouverture,
    signature_de,
    versions,
)

ZERO = Soldes(0.0, 0.0, 0.0, 0.0)


def _dossier(**kw):
    """Un dossier qui s'articule : 1 000 de primes encaissées sur le LRC."""
    base = {
        'nature': NATURE_EMIS, 'cle_groupe': 'DO|AUTRES|2026',
        'arrete': '2026-12-31',
        'ouverture': ZERO,
        'mouvements': [Mouvement('PRIMES', AXE_LRC_HORS_PERTE, 1000.0)],
        'cloture': Soldes(1000.0, 0.0, 0.0, 0.0),
    }
    base.update(kw)
    return constituer(**base)


class T1_QuatreSoldesEtNonSix(unittest.TestCase):
    """⚠️⚠️ LA VENTILATION PAA EST DANS LE POSTE c) SEUL.

    Le §100 aplati laisse croire qu'elle porte sur les trois éléments. La
    mise en page brute la place à l'intérieur de c) — le passif au titre des
    sinistres survenus. Six axes auraient suggéré que le LRC en PAA se
    ventile entre flux et ajustement pour risque : il ne le fait pas.
    """

    def test_il_y_a_QUATRE_axes(self):
        self.assertEqual(len(AXES), 4)
        self.assertEqual(len(set(AXES)), 4)
        print(f"    OK M1 : {len(AXES)} axes -- 100 a), 100 b), "
              "100 c) i), 100 c) ii)")

    def test_la_ventilation_ne_porte_QUE_sur_le_LIC(self):
        """⚠️ Deux axes pour c), UN SEUL pour a) et pour b)."""
        self.assertIn(AXE_LIC_FLUX_FUTURS, AXES)
        self.assertIn(AXE_LIC_AJUSTEMENT_RISQUE, AXES)
        for absent in ('LRC_FLUX_FUTURS', 'LRC_AJUSTEMENT_RISQUE',
                       'ELEMENT_DE_PERTE_FLUX_FUTURS'):
            self.assertNotIn(absent, AXES)

    def test_les_quatre_soldes_se_lisent_par_axe(self):
        s = Soldes(1.0, 2.0, 3.0, 4.0)
        self.assertEqual(s.par_axe(), {
            AXE_LRC_HORS_PERTE: 1.0, AXE_ELEMENT_DE_PERTE: 2.0,
            AXE_LIC_FLUX_FUTURS: 3.0, AXE_LIC_AJUSTEMENT_RISQUE: 4.0})


class T2_LeVocabulaireVientDe103Et105(unittest.TestCase):
    """⚠️⚠️ JAMAIS DE §104 : il vise les rapprochements du §101, et §101
    porte sur les contrats « QUI NE SONT PAS évalués selon la méthode
    d'affectation des primes ». Il aurait apporté la marge sur services
    contractuels, qui n'existe pas en PAA."""

    def test_douze_postes_onze_clos_et_un_residu(self):
        self.assertEqual(len(POSTES), 12)
        self.assertIn(POSTE_AUTRE, POSTES)
        print(f"    OK M1b : {len(POSTES)} postes -- 11 clos + le residu "
              "105 d)")

    def test_chaque_poste_porte_sa_reference_et_aucune_n_est_du_104(self):
        """⚠️ Un CAC lit la référence, pas l'identifiant Python."""
        for poste, ref in POSTES.items():
            self.assertTrue(ref.startswith(('§103', '§105')),
                            f"{poste} → {ref}")
            self.assertNotIn('§104', ref)
        self.assertEqual(POSTES[POSTE_AUTRE], '§105 d)')

    def test_les_six_postes_du_103_et_les_six_du_105(self):
        cent_trois = [p for p, r in POSTES.items() if r.startswith('§103')]
        cent_cinq = [p for p, r in POSTES.items() if r.startswith('§105')]
        self.assertEqual((len(cent_trois), len(cent_cinq)), (6, 6))

    def test_un_poste_inconnu_est_refuse_et_le_refus_dit_la_source(self):
        with self.assertRaises(RefusCloture) as e:
            _dossier(mouvements=[Mouvement('MARGE_SERVICES_CONTRACTUELS',
                                           AXE_LRC_HORS_PERTE, 1000.0)])
        self.assertEqual(e.exception.motif, MOTIF_POSTE_INCONNU)
        self.assertIn('§104', str(e.exception))
        self.assertIn('NON évalués en PAA', str(e.exception))

    def test_la_presence_de_chaque_poste_est_CONDITIONNELLE(self):
        """⚠️ « le cas échéant » figure dans §103 ET §105. Exiger les onze
        refuserait un groupe sans réassurance."""
        d = _dossier()
        self.assertEqual(len(d.mouvements), 1)
        self.assertIn('le cas échéant', PRESENCE_CONDITIONNELLE)
        self.assertIn('refuserait un dossier correct',
                      PRESENCE_CONDITIONNELLE)


class T3_LaCaseOuverteDu105d(unittest.TestCase):
    """⚠️⚠️ LA NORME OUVRE ELLE-MÊME LA DERNIÈRE CASE — « tout autre poste
    pouvant être nécessaire à la compréhension ». Une liste ENTIÈREMENT close
    aurait refusé du correct. C'est le critère d'arrêt retourné contre le
    dessin qui allait être posé."""

    def test_le_residu_passe_AVEC_son_libelle(self):
        d = _dossier(
            mouvements=[Mouvement('PRIMES', AXE_LRC_HORS_PERTE, 999.99),
                        Mouvement(POSTE_AUTRE, AXE_LRC_HORS_PERTE, 0.01,
                                  'arrondi de presentation au centime')])
        self.assertEqual(len(d.mouvements), 2)

    def test_le_residu_SANS_libelle_est_refuse(self):
        """⚠️ Un résidu sans libellé rendrait les onze autres inutiles :
        tout y tomberait."""
        with self.assertRaises(RefusCloture) as e:
            _dossier(mouvements=[Mouvement(POSTE_AUTRE, AXE_LRC_HORS_PERTE,
                                           1000.0)])
        self.assertEqual(e.exception.motif, MOTIF_LIBELLE_MANQUANT)
        self.assertIn("n'affirme rien", str(e.exception))

    def test_les_ONZE_autres_ne_demandent_PAS_de_libelle(self):
        """Leur référence les nomme déjà."""
        for poste in POSTES:
            if poste == POSTE_AUTRE:
                continue
            _dossier(mouvements=[Mouvement(poste, AXE_LRC_HORS_PERTE,
                                           1000.0)])


class T4_LArticulationEstUneIDENTITE(unittest.TestCase):
    """⚠️⚠️ UN MAGASIN QUI NE PEUT PAS SE CONTREDIRE NE PEUT RIEN DÉTECTER.

    Porter les mouvements seuls et CALCULER la clôture la rendrait toujours
    exacte — c'est le défaut qui a laissé 550,66 € de résidu dans un
    roll-forward composé à la main, sans que rien ne le signale.
    """

    def test_un_mouvement_perdu_est_refuse(self):
        with self.assertRaises(RefusCloture) as e:
            _dossier(cloture=Soldes(1500.0, 0.0, 0.0, 0.0))
        self.assertEqual(e.exception.motif, MOTIF_ARTICULATION_ROMPUE)
        self.assertIn('IDENTITÉ', str(e.exception))
        self.assertIn('+500.00', str(e.exception))

    def test_LE_CAS_QU_UN_CONTROLE_GLOBAL_LAISSERAIT_PASSER(self):
        """⚠️⚠️ LE TEST QUI JUSTIFIE L'AXE. Deux erreurs de sens contraire
        sur DEUX axes : le total est juste, chaque axe est faux. Un contrôle
        global n'y verrait rien — c'est la forme exacte du défaut que ce
        dépôt combat depuis « un bilan dont le total est juste et dont les
        deux lignes sont fausses »."""
        with self.assertRaises(RefusCloture) as e:
            _dossier(
                mouvements=[
                    Mouvement('PRIMES', AXE_LRC_HORS_PERTE, 1000.0),
                    Mouvement('SERVICES_FUTURS', AXE_ELEMENT_DE_PERTE, 300.0)],
                cloture=Soldes(700.0, 600.0, 0.0, 0.0))
        self.assertEqual(e.exception.motif, MOTIF_ARTICULATION_ROMPUE)
        self.assertIn('2 axe(s) sur 4', str(e.exception))
        somme_ouv, somme_clo = 0.0 + 1000.0 + 300.0, 700.0 + 600.0
        self.assertAlmostEqual(somme_ouv, somme_clo, 6,
                               "le TOTAL boucle : c'est tout le piege")
        print("    OK M1c : total juste, 2 axes faux -> REFUSE. Un controle "
              "global aurait laisse passer")

    def test_l_articulation_est_INDIFFERENTE_AU_SIGNE(self):
        """⚠️ §98 prévient que la réassurance détenue donne des charges là où
        l'émis donne des produits. Ce module n'impose AUCUNE convention : ce
        dépôt en a déjà payé deux contradictoires."""
        _dossier(nature=NATURE_REASSURANCE_DETENUE,
                 mouvements=[Mouvement('PRIMES', AXE_LRC_HORS_PERTE, -1000.0)],
                 cloture=Soldes(-1000.0, 0.0, 0.0, 0.0))

    def test_le_refus_indique_la_place_PREVUE_PAR_LA_NORME_pour_un_arrondi(self):
        """⚠️ Une tolérance ne distinguerait pas l'arrondi de l'oubli ; une
        déclaration au §105 d), si."""
        with self.assertRaises(RefusCloture) as e:
            _dossier(cloture=Soldes(1000.01, 0.0, 0.0, 0.0))
        self.assertIn(POSTE_AUTRE, str(e.exception))
        self.assertIn('§105 d)', str(e.exception))
        self.assertIn("l'arrondi de l'oubli", str(e.exception))

    def test_l_axe_est_DECLARE_et_ne_se_deduit_pas(self):
        """⚠️ §103 et §105 n'ont AUCUNE table poste → axe. La déduire serait
        présenter une invention comme une lecture."""
        with self.assertRaises(RefusCloture) as e:
            _dossier(mouvements=[Mouvement('PRIMES', 'LRC', 1000.0)])
        self.assertEqual(e.exception.motif, MOTIF_AXE_NON_DECLARE)
        self.assertIn(AXE_DECLARE, str(e.exception))
        self.assertIn('invention', str(e.exception))


class T5_LaNatureVientDu98(unittest.TestCase):
    """⚠️⚠️ §98 EXIGE DES RAPPROCHEMENTS SÉPARÉS pour les contrats émis et la
    réassurance détenue. `CleGroupe` ne porte pas la nature — et on ne la lui
    ajoute pas : elle est scellée à la naissance (§24), un test refuse la
    reclassification, et un champ de plus changerait l'identité de toutes les
    clés déjà écrites."""

    def test_la_cle_a_TROIS_composantes(self):
        c = CleCloture(NATURE_EMIS, 'DO|AUTRES|2026', '2026-12-31')
        self.assertEqual(len(c), 3)
        self.assertEqual(c.texte, 'EMIS|DO|AUTRES|2026|2026-12-31')

    def test_sans_nature_declaree_le_dossier_est_refuse(self):
        for n in ('', 'emis', 'CEDE', None):
            with self.assertRaises(RefusCloture, msg=str(n)) as e:
                _dossier(nature=n)
            self.assertEqual(e.exception.motif, MOTIF_NATURE_NON_DECLAREE)
        self.assertIn('§98', str(e.exception))

    def test_un_groupe_ne_peut_PAS_apparaitre_sous_DEUX_natures(self):
        """⚠️ LE GARDE-FOU DE LA CLÉ À TROIS COMPOSANTES. Sans lui, la même
        clé traverserait les deux rapprochements du §98 et les rendrait
        incomparables d'un arrêté à l'autre."""
        m = deposer(ouvrir('MutuelleTest'), _dossier())
        with self.assertRaises(RefusCloture) as e:
            deposer(m, _dossier(nature=NATURE_REASSURANCE_DETENUE))
        self.assertEqual(e.exception.motif, MOTIF_NATURE_DIVERGENTE)
        self.assertIn('ÉMIS OU DÉTENU, JAMAIS LES DEUX', str(e.exception))
        print("    OK M1d : un groupe sous deux natures -> REFUSE (par. 98)")

    def test_les_deux_natures_coexistent_sur_des_groupes_DISTINCTS(self):
        m = deposer(ouvrir('MutuelleTest'), _dossier())
        m = deposer(m, _dossier(nature=NATURE_REASSURANCE_DETENUE,
                                cle_groupe='TRAITE_QP|AUTRES|2026'))
        self.assertEqual(len(m.dossiers), 2)
        self.assertEqual({d.cle.nature for d in m.dossiers}, set(NATURES))


class T6_LeMagasinEstAPPEND_ONLY(unittest.TestCase):
    """⚠️ UNE CLÔTURE EST RECTIFIÉE AVANT SIGNATURE, et elle ne s'écrase
    JAMAIS : un CAC demandera si le chiffre a changé après le premier
    passage. Un magasin qui écrase ne peut pas répondre."""

    def test_une_rectification_s_AJOUTE_et_les_deux_survivent(self):
        cle = CleCloture(NATURE_EMIS, 'DO|AUTRES|2026', '2026-12-31')
        m = deposer(ouvrir('MutuelleTest'), _dossier())
        m = deposer(m, _dossier(
            mouvements=[Mouvement('PRIMES', AXE_LRC_HORS_PERTE, 1200.0)],
            cloture=Soldes(1200.0, 0.0, 0.0, 0.0),
            version=2, motif='prime tardive integree le 15/01'))
        self.assertEqual(len(versions(m, cle)), 2)
        self.assertEqual(dossier_courant(m, cle).cloture.lrc_hors_perte,
                         1200.0)
        self.assertEqual(versions(m, cle)[0].cloture.lrc_hors_perte, 1000.0)
        print("    OK M1e : 2 versions deposees, la premiere SURVIT")

    def test_une_rectification_SANS_motif_est_refusee(self):
        with self.assertRaises(RefusCloture) as e:
            _dossier(version=2)
        self.assertEqual(e.exception.motif, MOTIF_VERSION_SANS_MOTIF)
        self.assertIn('indistinguable', str(e.exception))

    def test_deposer_n_altere_pas_le_magasin_recu(self):
        m = ouvrir('MutuelleTest')
        deposer(m, _dossier())
        self.assertEqual(len(m.dossiers), 0)

    def test_un_dossier_ABSENT_n_est_pas_un_dossier_a_ZERO(self):
        """⚠️ Rendre des soldes nuls ferait passer une absence pour une
        mesure — la faute que ce dépôt combat depuis « Ran 0 tests »."""
        with self.assertRaises(RefusCloture) as e:
            dossier_courant(ouvrir('MutuelleTest'),
                            CleCloture(NATURE_EMIS, 'X|AUTRES|2026',
                                       '2026-12-31'))
        self.assertEqual(e.exception.motif, MOTIF_DOSSIER_ABSENT)
        self.assertIn('pas un dossier à ZÉRO', str(e.exception))


class T7_LeResumeDitCeQuIlNEtablitPas(unittest.TestCase):
    """⚠️ UN CONTRÔLE QUI NE DIT PAS SA PORTÉE SE FAIT SURÉVALUER."""

    def test_le_resume_separe_les_deux_natures_du_98(self):
        m = deposer(ouvrir('MutuelleTest'), _dossier())
        m = deposer(m, _dossier(nature=NATURE_REASSURANCE_DETENUE,
                                cle_groupe='TRAITE_QP|AUTRES|2026'))
        t = resume(m)
        self.assertIn('1 émis', t)
        self.assertIn('1 en réassurance détenue', t)
        self.assertIn('§98', t)

    def test_le_resume_dit_CE_QU_IL_N_ETABLIT_PAS_sans_nommer_de_lot(self):
        """⚠️⚠️ CE TEST ÉPINGLAIT UNE PHRASE QUI NOMMAIT UN LOT À VENIR —
        « aucune clôture n'est SIGNÉE […] c'est le lot M2 ». Il était juste le
        jour où il a été écrit, et il GARANTISSAIT que la prose devienne
        fausse : le lot suivant devait la démentir.

        ⚠️ ÉPINGLER UN NOM DE LOT DANS UN TEXTE PUBLIÉ, C'EST DATER CE TEXTE.
        Ce que le résumé doit dire est ce qu'il N'ÉTABLIT PAS — une limite qui
        reste vraie tant que le contrôle n'existe pas, et qui se retire avec
        lui. Le reste se CALCULE sur l'état du magasin.
        """
        t = resume(deposer(ouvrir('MutuelleTest'), _dossier()))
        self.assertIn("CE QUE CE MAGASIN N'ÉTABLIT PAS", t)
        self.assertIn('AUDITÉE', t)
        for date in ('M1', 'M2', 'M3', 'M4'):
            self.assertNotIn(f'lot {date}', t)
        self.assertIn("ne peuvent PAS servir d'ouverture", t)


class T8_LaSignatureEstCONSTATEE_PasEXIGEE(unittest.TestCase):
    """⚠️⚠️ M2 — ET SON DESSIN VIENT DU RENDU, QUI EST POURTANT LOIN.

    LE RENDU NE DEMANDE RIEN, IL RESTITUE : il assemble ce qui existe, porte
    les signatures comme information tracée, et DIT ce qui manque plutôt que
    de bloquer. C'est ce principe qui décide où le refus se place.
    """

    PTF = ('DO', 'MRH')
    CONTEXTE = ContexteEvaluation(arrete='2026-12-31', portefeuilles=PTF)

    def _magasin(self):
        return deposer(ouvrir('MutuelleTest'), _dossier())

    def _signer(self, m, **kw):
        base = {'arrete': '2026-12-31', 'statut': 'signee le 15/02/2027',
                'declarant': 'directrice technique', 'qualite': QUALITE_ENTITE,
                'portefeuilles': self.PTF, 'contexte': self.CONTEXTE}
        base.update(kw)
        return apposer(m, **base)

    def test_une_signature_de_l_entite_est_OPPOSABLE(self):
        m = self._signer(self._magasin())
        s = signature_de(m, '2026-12-31')
        self.assertEqual(s.verdict, SIGNATURE_OPPOSABLE)
        self.assertIn('directrice technique', s.motif)
        print("    OK M2 : signature de l'entite -> OPPOSABLE")

    def test_une_signature_de_TIERS_est_ENREGISTREE_pas_rejetee(self):
        """⚠️⚠️ « PERSONNE N'A SIGNÉ » ET « LE PRODUCTEUR A SIGNÉ, ET IL N'EST
        PAS L'ENTITÉ » NE SONT PAS LA MÊME INFORMATION. Le chantier du taux
        l'a établi : cinq déclarations parfaitement signées par un tiers ne
        valaient rien au sens du §36. Les rejeter ferait perdre la seconde."""
        m = self._signer(self._magasin(), qualite=QUALITE_TIERS,
                         declarant='producteur de donnees')
        s = signature_de(m, '2026-12-31')
        self.assertEqual(s.verdict, SIGNATURE_INOPPOSABLE)
        self.assertIn('producteur de donnees', s.motif)
        self.assertIn('§36', s.motif)
        print("    OK M2b : signature d'un TIERS -> enregistree INOPPOSABLE, "
              "avec son motif")

    def test_un_statut_de_DEMONSTRATION_est_enregistre_INOPPOSABLE(self):
        m = self._signer(self._magasin(), statut='DEMONSTRATION_NON_SIGNEE')
        self.assertEqual(signature_de(m, '2026-12-31').verdict,
                         SIGNATURE_INOPPOSABLE)

    def test_un_ARRETE_MALFORME_reste_un_REFUS_et_non_un_verdict(self):
        """⚠️ LA DISTINCTION COMPTE : une signature dont on ignore QUEL arrêté
        elle couvre n'est pas inopposable, elle est invalide — et
        `signature_de` ne la retrouverait jamais."""
        with self.assertRaises(RefusCloture) as e:
            self._signer(self._magasin(), arrete='31/12/2026')
        self.assertEqual(e.exception.motif, MOTIF_ARRETE_INVALIDE)

    def test_sans_signature_la_lecture_rend_None_et_NE_LEVE_PAS(self):
        self.assertIsNone(signature_de(self._magasin(), '2026-12-31'))

    def test_une_signature_refaite_s_AJOUTE_et_la_derniere_vaut(self):
        m = self._signer(self._magasin(), qualite=QUALITE_TIERS)
        m = self._signer(m)
        self.assertEqual(len(m.signatures), 2)
        self.assertEqual(signature_de(m, '2026-12-31').verdict,
                         SIGNATURE_OPPOSABLE)
        self.assertEqual(m.signatures[0].verdict, SIGNATURE_INOPPOSABLE)


class T9_LeRefusEstAuSEUL_POINT_QUI_ENGAGE(unittest.TestCase):
    """⚠️⚠️ LE REFUS NE VIT QU'À UN ENDROIT : servir une clôture comme
    OUVERTURE. Partout ailleurs, la signature est une donnée qu'on lit."""

    PTF = ('DO', 'MRH')
    CONTEXTE = ContexteEvaluation(arrete='2026-12-31', portefeuilles=PTF)
    CLE = CleCloture(NATURE_EMIS, 'DO|AUTRES|2026', '2026-12-31')

    def _magasin(self, signee=None):
        m = deposer(ouvrir('MutuelleTest'), _dossier())
        if signee is not None:
            m = apposer(m, arrete='2026-12-31', statut='signee le 15/02',
                        declarant='directrice technique', qualite=signee,
                        portefeuilles=self.PTF, contexte=self.CONTEXTE)
        return m

    def test_une_cloture_SIGNEE_sert_d_ouverture(self):
        soldes = servir_comme_ouverture(self._magasin(QUALITE_ENTITE),
                                        self.CLE)
        self.assertEqual(soldes.lrc_hors_perte, 1000.0)
        print("    OK M2c : cloture signee -> sert d'ouverture")

    def test_une_cloture_NON_signee_est_REFUSEE_comme_ouverture(self):
        with self.assertRaises(RefusCloture) as e:
            servir_comme_ouverture(self._magasin(), self.CLE)
        self.assertEqual(e.exception.motif, MOTIF_OUVERTURE_NON_SIGNEE)
        self.assertIn('aucune signature', str(e.exception))
        self.assertIn('ENTRER DANS LA CHAÎNE', str(e.exception))
        print("    OK M2d : cloture non signee -> REFUSEE comme ouverture")

    def test_une_signature_INOPPOSABLE_ne_sert_pas_davantage(self):
        """⚠️ Signée par un tiers reste non opposable — et le refus REPREND
        le motif, il ne dit pas seulement « non signée »."""
        with self.assertRaises(RefusCloture) as e:
            servir_comme_ouverture(self._magasin(QUALITE_TIERS), self.CLE)
        self.assertEqual(e.exception.motif, MOTIF_OUVERTURE_NON_SIGNEE)
        self.assertIn('INOPPOSABLE', str(e.exception))
        self.assertIn('§36', str(e.exception))

    def test_LE_RENDU_LIT_TOUT_SANS_JAMAIS_ETRE_REFUSE(self):
        """⚠️⚠️ LE TEST QUI PORTE LE DESSIN D'ENSEMBLE. Un rendu qui assemble
        un état doit pouvoir tout lire — dossier, versions, signature — et
        écrire « non signée » de lui-même. S'il pouvait être refusé, il
        devrait REDEMANDER une signature pour afficher quoi que ce soit,
        l'inverse de ce qu'il doit faire.
        """
        for m in (self._magasin(), self._magasin(QUALITE_TIERS),
                  self._magasin(QUALITE_ENTITE)):
            self.assertIsNotNone(dossier_courant(m, self.CLE))
            self.assertTrue(versions(m, self.CLE))
            signature_de(m, '2026-12-31')     # ⚠️ ne lève jamais
            self.assertIn('MAGASIN DE CLÔTURES', resume(m))
        print("    OK M2e : 3 etats de signature, le rendu lit TOUT et n'est "
              "JAMAIS refuse")

    def test_le_resume_SE_CALCULE_et_ne_recite_pas_un_lot(self):
        """⚠️⚠️ SA VERSION PRÉCÉDENTE ANNONÇAIT « aucune clôture n'est SIGNÉE
        […] c'est le lot M2 » — juste le jour où elle a été écrite, fausse en
        silence dès la première signature. C'est le motif que le périmètre
        publié venait de payer : une étiquette en retard sur ce qu'elle
        décrit."""
        t = resume(self._magasin(QUALITE_ENTITE))
        self.assertIn("arrêtés SIGNÉS et opposables : ['2026-12-31']", t)
        self.assertNotIn('lot M2', t)
        self.assertNotIn("aucune clôture n'est SIGNÉE", t)
        sans = resume(self._magasin())
        self.assertIn('ne peuvent PAS servir', sans)
        tiers = resume(self._magasin(QUALITE_TIERS))
        self.assertIn('signature INOPPOSABLE', tiers)
        self.assertIn("Ce n'est pas « non signé »", tiers)

    def test_le_resume_NOMME_ses_limites_ET_ELLES_SE_RETIRENT_AVEC_LEUR_LOT(
            self):
        """⚠️ Il constate une signature apposée ICI, jamais un audit mené
        ailleurs. Une première année vient d'un autre système.

        ⚠️⚠️ CE TEST A PERDU UNE ASSERTION, ET C'EST LA RÈGLE QUI FONCTIONNE.
        Il exigeait aussi que le résumé nomme l'absence de contrôle de
        CONTINUITÉ — vrai tant que `chainer` n'existait pas, faux dès qu'il a
        été bâti. ⚠️ C'est la différence exacte avec le test que M2 a dû
        démonter : celui-là épinglait un ÉTAT TRANSITOIRE et un nom de lot,
        qui devaient être démentis ; celui-ci épingle une LIMITE, et une
        limite se retire AVEC le contrôle qui la comble. La première dérive,
        la seconde suit.
        """
        t = resume(self._magasin(QUALITE_ENTITE))
        self.assertIn('AUDITÉE', t)
        self.assertIn('arrêté MANQUE', t)
        self.assertNotIn('CONTINUITÉ', t)


class T10_LaPersistance(unittest.TestCase):
    """M3 — écrire, relire, et refuser un format qu'on ne connaît pas."""

    PTF = ('DO', 'MRH')
    CONTEXTE = ContexteEvaluation(arrete='2026-12-31', portefeuilles=PTF)

    def _fichier(self):
        import tempfile
        d = tempfile.mkdtemp(prefix='cloture_')
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return Path(d) / 'clotures.json'

    def _magasin(self):
        m = deposer(ouvrir('MutuelleTest'), _dossier())
        m = deposer(m, _dossier(
            mouvements=[Mouvement('PRIMES', AXE_LRC_HORS_PERTE, 1234.567891)],
            cloture=Soldes(1234.567891, 0.0, 0.0, 0.0),
            version=2, motif='prime tardive'))
        m = apposer(m, arrete='2026-12-31', statut='signee le 15/02',
                    declarant='directrice technique', qualite=QUALITE_ENTITE,
                    portefeuilles=self.PTF, contexte=self.CONTEXTE)
        return m

    def test_l_aller_retour_est_fidele(self):
        m = self._magasin()
        relu = relire(ecrire(m, self._fichier()))
        self.assertEqual(relu, m)
        print(f"    OK M3 : aller-retour fidele sur {len(m.dossiers)} "
              f"dossiers et {len(m.signatures)} signature(s)")

    def test_les_montants_traversent_SANS_PERDRE_DE_PRECISION(self):
        """⚠️ Un solde arrondi par la sérialisation romprait l'articulation
        au retour, et le magasin l'aurait accepté à l'aller."""
        relu = relire(ecrire(self._magasin(), self._fichier()))
        self.assertEqual(relu.dossiers[1].cloture.lrc_hors_perte,
                         1234.567891)
        self.assertEqual(relu.dossiers[1].mouvements[0].montant, 1234.567891)

    def test_deux_ecritures_du_meme_magasin_rendent_les_MEMES_OCTETS(self):
        m = self._magasin()
        a, b = self._fichier(), self._fichier()
        self.assertEqual(ecrire(m, a).read_bytes(), ecrire(m, b).read_bytes())
        print("    OK M3b : deux ecritures -> memes octets")

    def test_L_ORDRE_DE_DEPOT_SURVIT_et_n_est_PAS_trie(self):
        """⚠️⚠️ LA SEULE DIFFÉRENCE AVEC `registre`, ET LA RECOPIER AURAIT
        CASSÉ CE MODULE EN SILENCE. Le registre TRIE ses groupes ;
        `dossier_courant` rend le DERNIER DÉPOSÉ. Trier ferait remonter une
        rectification avant la clôture qu'elle corrige, et la version 1
        redeviendrait courante."""
        cle = CleCloture(NATURE_EMIS, 'DO|AUTRES|2026', '2026-12-31')
        relu = relire(ecrire(self._magasin(), self._fichier()))
        self.assertEqual([d.version for d in versions(relu, cle)], [1, 2])
        self.assertEqual(dossier_courant(relu, cle).version, 2)
        print("    OK M3c : l'ordre de depot survit -- la v2 reste courante")

    def test_le_VERDICT_de_signature_est_relu_TEL_QUEL(self):
        """⚠️ Il dit ce que le contrôle établissait CE JOUR-LÀ. Le recalculer
        ferait changer l'histoire quand le vocabulaire du contrôle évolue."""
        m = apposer(deposer(ouvrir('X'), _dossier()), arrete='2026-12-31',
                    statut='signee', declarant='producteur',
                    qualite=QUALITE_TIERS, portefeuilles=self.PTF,
                    contexte=self.CONTEXTE)
        relu = relire(ecrire(m, self._fichier()))
        s = signature_de(relu, '2026-12-31')
        self.assertEqual(s.verdict, SIGNATURE_INOPPOSABLE)
        self.assertIn('§36', s.motif)

    def test_un_format_inconnu_est_refuse_pas_devine(self):
        p = self._fichier()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"format": "autre/9", "entite": "X"}',
                     encoding='utf-8')
        with self.assertRaises(RefusCloture) as e:
            relire(p)
        self.assertEqual(e.exception.motif, MOTIF_FORMAT_INCONNU)
        self.assertIn(FORMAT_CLOTURES, str(e.exception))
        print("    OK M3d : un format inconnu est refuse, pas devine")

    def test_un_magasin_relu_REFUSE_TOUJOURS_ce_qu_il_refusait(self):
        """⚠️ La persistance ne doit pas être une porte dérobée : une clôture
        non signée relue ne devient pas servable."""
        cle = CleCloture(NATURE_EMIS, 'DO|AUTRES|2026', '2026-12-31')
        m = relire(ecrire(deposer(ouvrir('X'), _dossier()), self._fichier()))
        with self.assertRaises(RefusCloture) as e:
            servir_comme_ouverture(m, cle)
        self.assertEqual(e.exception.motif, MOTIF_OUVERTURE_NON_SIGNEE)


class T11_LaContinuiteDeLaChaine(unittest.TestCase):
    """M4 — la clôture d'un arrêté ouvre le SUIVANT, nommément.

    ⚠️ LES DEUX CONTRÔLES SE CUMULENT ET AUCUN N'ABSORBE L'AUTRE : une
    clôture signée peut être chaînée à l'envers, une clôture bien chaînée
    peut n'être signée par personne.
    """

    PTF = ('DO', 'MRH')
    CONTEXTE = ContexteEvaluation(arrete='2026-12-31', portefeuilles=PTF)
    CLE = CleCloture(NATURE_EMIS, 'DO|AUTRES|2026', '2026-12-31')

    def _magasin(self, signee=True):
        m = deposer(ouvrir('MutuelleTest'), _dossier())
        if signee:
            m = apposer(m, arrete='2026-12-31', statut='signee le 15/02',
                        declarant='directrice technique',
                        qualite=QUALITE_ENTITE, portefeuilles=self.PTF,
                        contexte=self.CONTEXTE)
        return m

    def test_un_arrete_POSTERIEUR_est_chaine(self):
        soldes = chainer(self._magasin(), self.CLE, '2027-12-31')
        self.assertEqual(soldes.lrc_hors_perte, 1000.0)
        print("    OK M4 : 2026-12-31 -> 2027-12-31, chaine")

    def test_une_periodicite_non_annuelle_passe(self):
        """⚠️ IFRS 17 N'IMPOSE AUCUNE PÉRIODICITÉ — §98 vise « la période »,
        que l'entité définit. Exiger douze mois refuserait un semestriel."""
        self.assertIsNotNone(chainer(self._magasin(), self.CLE, '2027-06-30'))

    def test_un_arrete_ANTERIEUR_est_refuse(self):
        with self.assertRaises(RefusCloture) as e:
            chainer(self._magasin(), self.CLE, '2025-12-31')
        self.assertEqual(e.exception.motif, MOTIF_CHAINE_ROMPUE)
        self.assertIn('ANTÉRIEUR', str(e.exception))
        self.assertIn('inverserait le temps', str(e.exception))

    def test_LE_MEME_arrete_est_refuse(self):
        """⚠️ L'exercice boucler sur lui-même : le solde de clôture
        deviendrait sa propre origine, et l'articulation n'aurait plus de
        sens."""
        with self.assertRaises(RefusCloture) as e:
            chainer(self._magasin(), self.CLE, '2026-12-31')
        self.assertEqual(e.exception.motif, MOTIF_CHAINE_ROMPUE)
        self.assertIn('le même arrêté', str(e.exception))
        self.assertIn('sa propre origine', str(e.exception))
        print("    OK M4b : chainage sur le meme arrete -> REFUSE")

    def test_les_DEUX_controles_se_cumulent(self):
        """⚠️ AUCUN N'ABSORBE L'AUTRE, et c'est mesuré dans les deux sens."""
        # bien chaîné, mais non signé
        with self.assertRaises(RefusCloture) as e:
            chainer(self._magasin(signee=False), self.CLE, '2027-12-31')
        self.assertEqual(e.exception.motif, MOTIF_OUVERTURE_NON_SIGNEE)
        # signé, mais chaîné à l'envers
        with self.assertRaises(RefusCloture) as e:
            chainer(self._magasin(), self.CLE, '2025-12-31')
        self.assertEqual(e.exception.motif, MOTIF_CHAINE_ROMPUE)
        print("    OK M4c : signature et continuite se cumulent -- deux "
              "motifs distincts")

    def test_un_arrete_de_destination_malforme_est_refuse(self):
        with self.assertRaises(RefusCloture) as e:
            chainer(self._magasin(), self.CLE, '31/12/2027')
        self.assertEqual(e.exception.motif, MOTIF_ARRETE_INVALIDE)

    def test_la_LIMITE_de_la_chaine_est_NOMMEE_dans_le_refus(self):
        """⚠️ IL NE DÉTECTE PAS UN ARRÊTÉ MANQUANT : 2025 → 2027 sans 2026
        passe. Le magasin ne connaît que ce qu'on lui a remis."""
        with self.assertRaises(RefusCloture) as e:
            chainer(self._magasin(), self.CLE, '2026-12-31')
        self.assertIn(LIMITE_DE_LA_CHAINE, str(e.exception))
        self.assertIn('arrêté MANQUANT', str(e.exception))
        # ⚠️ et le trou passe REELLEMENT : la limite n'est pas rhetorique
        trou = deposer(ouvrir('X'), _dossier(arrete='2025-12-31'))
        trou = apposer(trou, arrete='2025-12-31', statut='signee',
                       declarant='DT', qualite=QUALITE_ENTITE,
                       portefeuilles=self.PTF,
                       contexte=ContexteEvaluation('2025-12-31', self.PTF))
        self.assertIsNotNone(chainer(
            trou, CleCloture(NATURE_EMIS, 'DO|AUTRES|2026', '2025-12-31'),
            '2027-12-31'))
        print("    OK M4d : le trou 2025 -> 2027 PASSE, et la limite le dit")


class Z_LaMesureN_IMPORTE_PAS_LeMagasin(unittest.TestCase):
    """⚠️⚠️ MÊME DOCTRINE QUE `mesure` ⊥ `socle`, ET POUR LA MÊME RAISON. La
    mesure reçoit des valeurs DÉCLARÉES ; elle ne va pas chercher un solde
    historique. C'est l'orchestrateur qui câblera les deux — et il n'existe
    pas encore.

    ⚠️ LE CONTRÔLE SE LIT SUR L'AST, PAS SUR LE TEXTE. Ce dépôt a payé trois
    fois qu'un relevé textuel ne distingue pas un identifiant d'une phrase
    française qui le mentionne.
    """

    def test_aucun_module_de_mesure_n_importe_cloture(self):
        mesure = Path(__file__).resolve().parents[1] / 'mesure'
        fautifs = []
        for f in mesure.rglob('*.py'):
            arbre = ast.parse(f.read_text(encoding='utf-8'))
            for n in ast.walk(arbre):
                cible = ''
                if isinstance(n, ast.ImportFrom):
                    cible = n.module or ''
                elif isinstance(n, ast.Import):
                    cible = ' '.join(a.name for a in n.names)
                if 'cloture' in cible:
                    fautifs.append(f'{f.name} → {cible}')
        self.assertEqual(
            fautifs, [],
            f"{len(fautifs)} module(s) de mesure/ importent le magasin : "
            f"{fautifs}. La mesure reçoit des valeurs DÉCLARÉES ; c'est "
            f"l'orchestrateur qui câble le magasin.")
        n = sum(1 for _ in mesure.rglob('*.py'))
        print(f"    OK M1z : {n} modules de mesure/ balayes sur l'AST, "
              "AUCUN n'importe le magasin")


if __name__ == '__main__':
    unittest.main(verbosity=2)
