# -*- coding: utf-8 -*-
"""Tests M1 — le magasin de clôtures, et ce qu'il refuse.

⚠️ GATE : `py -m unittest discover -s normes -t .` — voir test_contrat.py.

⚠️ CE QUI SE VÉRIFIE ICI VIENT D'UNE LECTURE, PAS D'UNE INTUITION. Les quatre
axes, le vocabulaire des postes et la case ouverte du §105 d) ont été relevés
dans le règlement (UE) 2023/1803 avant d'être codés — et le relevé a corrigé
le dessin deux fois.
"""
import ast
import unittest
from pathlib import Path

from normes.ifrs17.socle.cloture import (
    AXE_DECLARE,
    AXE_ELEMENT_DE_PERTE,
    AXE_LIC_AJUSTEMENT_RISQUE,
    AXE_LIC_FLUX_FUTURS,
    AXE_LRC_HORS_PERTE,
    AXES,
    MOTIF_ARTICULATION_ROMPUE,
    MOTIF_AXE_NON_DECLARE,
    MOTIF_DOSSIER_ABSENT,
    MOTIF_LIBELLE_MANQUANT,
    MOTIF_NATURE_DIVERGENTE,
    MOTIF_NATURE_NON_DECLAREE,
    MOTIF_POSTE_INCONNU,
    MOTIF_VERSION_SANS_MOTIF,
    NATURE_EMIS,
    NATURE_REASSURANCE_DETENUE,
    NATURES,
    POSTE_AUTRE,
    POSTES,
    PRESENCE_CONDITIONNELLE,
    CleCloture,
    Mouvement,
    RefusCloture,
    Soldes,
    constituer,
    deposer,
    dossier_courant,
    ouvrir,
    resume,
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

    def test_le_resume_dit_que_RIEN_N_EST_SIGNE_et_nomme_M2(self):
        """⚠️ M1 ne signe pas, et rien n'empêche encore de servir une clôture
        non signée comme ouverture. Le taire ferait croire l'inverse."""
        t = resume(deposer(ouvrir('MutuelleTest'), _dossier()))
        self.assertIn("aucune clôture n'est SIGNÉE", t)
        self.assertIn('M2', t)


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
