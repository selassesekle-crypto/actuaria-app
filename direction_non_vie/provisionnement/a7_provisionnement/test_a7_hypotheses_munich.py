# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 Ibrahim — filet des hypothèses de Munich CL (MCL-H1..H5)
=============================================================================

 DEUX NIVEAUX, comme les filets Bootstrap et Clark.

 NIVEAU 1 — VÉRITÉ CONNUE, BLOQUANT. Le guide de l'Institut ne traite pas
 Munich Chain Ladder (sommaire vérifié : §3 stochastique = Mack 3.b et
 Bootstrap 3.c seulement) : aucun oracle publié n'existe. Les paramètres sont
 fixés ici, et le code doit les retrouver.

 NIVEAU 2 — STRUCTUREL. Reprises sur les deux triangles, gouvernance,
 périmètre, et les trois formats de livrable.
=============================================================================
"""

import ast
import io
import os
import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses_munich import (
    CODES, MCL_H2_PAIRES_MIN, MESSAGE_H4, RESERVE_MUNICH,
    lignes_hypotheses_munich, mcl_h4_homogeneite_lambda,
    verifier_hypotheses_munich)
from direction_non_vie.provisionnement.a7_provisionnement.n3.munich_cl import (
    MCL_CV_ALERTE, MCL_CV_BLOQUANT, _statistiques_colonne, munich_cl,
    valider_prerequis)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    _MCL_ENG_SAIN, _MCL_LAM_E, _MCL_LAM_P, _MCL_PAYE)

# =============================================================================
#  LA VÉRITÉ — fixée ici, jamais montrée au code
# =============================================================================

N   = 9
VOL = np.array([1000., 1100., 1250., 1300., 1400., 1500., 1600., 1750., 1800.])
F_I = np.array([1.45, 1.20, 1.10, 1.055, 1.030, 1.018, 1.010, 1.004])
F_P = np.array([1.95, 1.42, 1.22, 1.115, 1.060, 1.032, 1.016, 1.006])


def _carres(lam_j, bruit=0.030, graine=0):
    """Carrés engendrés par la récursion de Quarg & Mack, λ_j IMPOSÉ."""
    rng = np.random.default_rng(graine)
    P = np.zeros((N, N))
    I = np.zeros((N, N))
    q0 = np.linspace(0.35, 0.70, N)
    rng.shuffle(q0)
    I[:, 0] = VOL * (1.0 + bruit * rng.normal(size=N))
    P[:, 0] = I[:, 0] * q0
    for j in range(N - 1):
        qi     = I[:, j] / np.maximum(P[:, j], 1e-9)
        qi_moy = I[:, j].sum() / max(P[:, j].sum(), 1e-9)
        ecart  = (qi - qi_moy) / max(np.std(qi), 1e-9)
        lam = lam_j[j] if hasattr(lam_j, '__len__') else lam_j
        I[:, j + 1] = I[:, j] * (F_I[j] * (1.0 + bruit * rng.normal(size=N)))
        P[:, j + 1] = P[:, j] * np.maximum(
            (F_P[j] + lam * 0.10 * ecart) * (1.0 + bruit * rng.normal(size=N)),
            1.001)
    return (np.maximum.accumulate(P, axis=1),
            np.maximum.accumulate(I, axis=1))


def _tri(P, I):
    Pt, It = P.copy(), I.copy()
    for i in range(N):
        for j in range(N):
            if i + j >= N:
                Pt[i, j] = It[i, j] = 0.0
    return Pt, It


def _engage(Pt, mode, par, graine):
    """Engagé LÉGITIME (provision dossier propre) ou CIRCULAIRE (dérivé)."""
    rng = np.random.default_rng(graine)
    if mode == 'circulaire':
        return np.where(Pt > 0,
                        Pt * 1.35 * (1 + par * rng.normal(size=Pt.shape)), 0.0)
    prov = np.where(Pt > 0, Pt * 0.35 * (1 + par * rng.normal(size=Pt.shape)), 0.0)
    return Pt + np.maximum(prov, 0.0)


def _taux_alerte(mode, par, n=60, base=41_000):
    """Fraction des tirages où `valider_prerequis` signale quelque chose."""
    n_alerte = n_ok = 0
    for g in range(n):
        P, I = _carres(np.full(N - 1, 0.6), graine=base + g)
        Pt, _ = _tri(P, I)
        E = _engage(Pt, mode, par, base + g)
        ok, msg = valider_prerequis(Pt, E)
        n_ok += 1
        if (not ok) or ('CV' in msg):
            n_alerte += 1
    return n_alerte / max(n_ok, 1)


# =============================================================================
#  NIVEAU 1 — VÉRITÉ CONNUE (BLOQUANT)
# =============================================================================

class TestMunichHypothesesVeriteConnue(unittest.TestCase):

    def test_mh1_circularite_stricte_bloquee(self):
        """Un engagé dérivé du payé doit être rejeté, pas seulement signalé."""
        for bruit in (0.0, 0.005):
            with self.subTest(bruit=bruit):
                n_bloq = 0
                for g in range(30):
                    P, I = _carres(np.full(N - 1, 0.6), graine=43_000 + g)
                    Pt, _ = _tri(P, I)
                    E = _engage(Pt, 'circulaire', bruit, 43_000 + g)
                    ok, _ = valider_prerequis(Pt, E)
                    n_bloq += (not ok)
                self.assertGreaterEqual(n_bloq / 30, 0.95,
                                        f"circularité à {bruit:.1%} non bloquée")

    def test_mh2_portefeuille_legitime_non_alarme(self):
        """Une provision dossier réellement dispersée ne doit pas alarmer."""
        taux = _taux_alerte('legitime', 0.25, base=44_000)
        self.assertLessEqual(taux, 0.05,
                             f"{taux:.1%} de fausses alarmes à dispersion 25 %")

    def test_mh3_seuil_alerte_corrige(self):
        """⚠️ ORACLE HISTORIQUE : le seuil d'alerte valait 0,05 et se
        déclenchait sur 100 % des portefeuilles légitimes à 10 % de dispersion.
        Une alerte qui sonne toujours n'informe de rien.

        Ramené à 0,025 (croisement des deux populations). Le recouvrement
        subsiste et il est assumé : circulaire-bruité q95 = 0,0233, légitime-10 %
        q05 = 0,0223 — aucun seuil ne les sépare proprement dans cette bande.
        """
        self.assertEqual(MCL_CV_BLOQUANT, 0.02)
        self.assertLess(MCL_CV_ALERTE, 0.05,
                        "le seuil d'alerte 0,05 était mesuré faux")
        taux = _taux_alerte('legitime', 0.10, base=45_000)
        self.assertLessEqual(taux, 0.50,
                             f"{taux:.1%} de fausses alarmes à dispersion 10 % "
                             f"(était 100 % au seuil 0,05)")

    def test_mh4_calibration_du_test_de_linearite(self):
        """MCL-H2 sous vérité LINÉAIRE : le test ne doit pas crier au loup.

        Mesuré à la conception : 1,7 % de rejets pour un nominal de 5 %. Le
        test est CONSERVATEUR — c'est une faiblesse assumée, pas un défaut.
        """
        rejets = tot = 0
        for g in range(40):
            P, I = _carres(np.full(N - 1, 0.6), graine=46_000 + g)
            Pt, It = _tri(P, I)
            h = verifier_hypotheses_munich(Pt, It, munich_cl(Pt, It, annee_base=1))
            st = h['statuts']['MCL-H2']
            if st == 'NON TESTABLE':
                continue
            tot += 1
            rejets += (st == 'NON VALIDÉE')
        self.assertGreaterEqual(tot, 20, 'campagne trop maigre')
        self.assertLessEqual(rejets / tot, 0.10,
                             f"{rejets}/{tot} rejets sous vérité linéaire")

    def test_mh5_faiblesse_de_h4_verrouillee(self):
        """⚠️ VERROU ANTI-SUR-PROMESSE. Un test d'homogénéité de λ est
        constructible et parfaitement calibré, mais sa puissance vaut 13 à 17 %
        contre un λ variant de 0 à 1,2 : sous λ CONSTANT, l'étendue médiane des
        λ_j vaut déjà 1,469. Le bruit d'estimation par colonne dépasse le
        signal — le pooling ne peut pas se tester par les λ par colonne.

        Ce test FIGE cette faiblesse : un jour où quelqu'un prétendrait
        détecter l'hétérogénéité de λ à cette taille, il faudrait le prouver
        contre cette mesure.
        """
        def lam_j(C_P, C_E):
            out = []
            for j in range(C_P.shape[1] - 1):
                s = _statistiques_colonne(C_P, C_E, j)
                if s is None:
                    continue
                pr = []
                for i in s['idx']:
                    p, p1, e = C_P[i, j], C_P[i, j + 1], C_E[i, j]
                    w = float(np.sqrt(p))
                    pr.append(((p1 / p - s['f_P']) / s['sig_P'] * w,
                               (e / p - s['q_inv']) / s['rho_Qi'] * w))
                a = np.asarray(pr, float)
                if len(a) < 2 or np.sum(a[:, 1] ** 2) <= 0:
                    continue
                out.append(float(np.sum(a[:, 0] * a[:, 1]) / np.sum(a[:, 1] ** 2)))
            return np.array(out)

        etendues = []
        for g in range(40):
            P, I = _carres(np.full(N - 1, 0.6), graine=47_000 + g)   # λ CONSTANT
            l = lam_j(*_tri(P, I))
            if len(l) >= 2:
                etendues.append(l.max() - l.min())
        self.assertGreaterEqual(len(etendues), 20)
        med = float(np.median(etendues))
        self.assertGreater(med, 0.30,
                           f"étendue médiane {med:.3f} sous λ CONSTANT — si elle "
                           f"devenait faible, le test d'homogénéité redeviendrait "
                           f"envisageable et cette décision serait à revoir")

    def test_mh6_consequence_du_pooling_verrouillee(self):
        """La conséquence, elle, est RÉELLE : pooler un λ qui varie coûte.

        Mesuré à la conception : biais moyen 1,15 % (λ constant) contre 20,05 %
        (λ en créneau). C'est ce qui interdit de traiter MCL-H4 par le silence.
        """
        def biais(lam):
            errs = []
            for g in range(35):
                P, I = _carres(lam, graine=48_000 + g)
                Pt, It = _tri(P, I)
                paye  = np.array([Pt[i, N - 1 - i] for i in range(N)])
                vraie = float((P[:, -1] - paye)[1:].sum())
                if vraie <= 0:
                    continue
                r = munich_cl(Pt, It, annee_base=1)
                if r.get('disponible'):
                    errs.append(r['be_munich_paye'] / vraie - 1.0)
            return float(np.mean(errs)) if len(errs) >= 8 else None

        b_cst = biais(np.full(N - 1, 0.6))
        b_var = biais(np.array([0.0] * 4 + [1.2] * 4))
        self.assertIsNotNone(b_cst)
        self.assertIsNotNone(b_var)
        self.assertGreater(abs(b_var), abs(b_cst),
                           "pooler un λ variable doit coûter plus qu'un λ constant")
        self.assertGreater(abs(b_var), 0.10,
                           f"biais {abs(b_var):.1%} — la mention MCL-H4 annonce "
                           f"« de l'ordre de 20 % », elle doit rester fondée")


# =============================================================================
#  NIVEAU 2 — STRUCTUREL
# =============================================================================

class TestMunichHypothesesStructurel(unittest.TestCase):

    def _bloc(self, P, E):
        A, B = np.asarray(P, float), np.asarray(E, float)
        return verifier_hypotheses_munich(A, B, munich_cl(A, B, annee_base=1))

    def test_mh7_h1_et_h3_portent_sur_les_deux_triangles(self):
        """MCL-H1 et MCL-H3 rejouent CLM sur le payé ET l'engagé, pire retenu."""
        h = self._bloc(_MCL_LAM_P, _MCL_LAM_E)
        for code in ('MCL-H1', 'MCL-H3'):
            with self.subTest(code=code):
                detail = h['hypotheses'][code]['detail']
                self.assertEqual(len(detail), 2, "les DEUX triangles")
                self.assertEqual({d['triangle'] for d in detail},
                                 {'payé', 'engagé'})
                # agrégation par le pire
                from direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses_clm import (
                    _pire_statut)
                self.assertEqual(h['statuts'][code],
                                 _pire_statut([d['statut'] for d in detail]))

    def test_mh8_seule_h5_est_critique(self):
        """Une seule hypothèse gate, et c'est mesuré — pas de symétrie."""
        h = self._bloc(_MCL_LAM_P, _MCL_LAM_E)
        for code in CODES:
            cp = h['hypotheses'][code]['critique_pour']
            if code == 'MCL-H5':
                self.assertEqual(cp, [RESERVE_MUNICH])
            else:
                self.assertEqual(cp, [], f"{code} ne doit rien gater")

    def test_mh9_h5_gouverne_la_reserve_publiable(self):
        h = self._bloc(_MCL_LAM_P, _MCL_LAM_E)
        self.assertTrue(h['reserve_publiable'])
        # engagé circulaire → H5 NON VALIDÉE → réserve non publiable
        Pt = np.asarray(_MCL_LAM_P, float)
        E  = np.where(Pt > 0, Pt * 1.35, 0.0)
        hc = verifier_hypotheses_munich(Pt, E, munich_cl(Pt, E, annee_base=1))
        self.assertEqual(hc['statuts']['MCL-H5'], 'NON VALIDÉE')
        self.assertFalse(hc['reserve_publiable'])

    def test_mh10_h4_est_une_mention_jamais_un_verdict(self):
        """MCL-H4 ne peut être ni VALIDÉE ni NON VALIDÉE, et son texte est figé."""
        r = mcl_h4_homogeneite_lambda()
        self.assertEqual(r.statut, 'NON TESTABLE')
        self.assertEqual(r.message, MESSAGE_H4)
        self.assertEqual(r.critique_pour, ())
        self.assertTrue(r.extras.get('mention_permanente'))
        for P, E in ((_MCL_PAYE, _MCL_ENG_SAIN), (_MCL_LAM_P, _MCL_LAM_E)):
            h = self._bloc(P, E)
            self.assertEqual(h['statuts']['MCL-H4'], 'NON TESTABLE')
            self.assertIn('20 %', h['hypotheses']['MCL-H4']['message'])

    def test_mh11_4x4_majoritairement_non_testable(self):
        """Sur un 4×4 le bloc est surtout muet — VOULU, pas une régression.

        MCL-H2 exige 6 paires (un 4×4 en fournit 5), MCL-H3 n'est pas testable
        à cette taille. NON TESTABLE est un verdict honnête.
        """
        h = self._bloc(_MCL_PAYE, _MCL_ENG_SAIN)
        self.assertEqual(h['statuts']['MCL-H2'], 'NON TESTABLE')
        self.assertIn(str(MCL_H2_PAIRES_MIN), h['hypotheses']['MCL-H2']['message'])
        self.assertEqual(h['statuts']['MCL-H4'], 'NON TESTABLE')
        n_muet = sum(1 for c in CODES if h['statuts'][c] == 'NON TESTABLE')
        self.assertGreaterEqual(n_muet, 3, 'comportement attendu sur 4×4')

    def test_mh12_perimetre_aucune_reference_au_be(self):
        """Verrou AST : le module ne peut pas toucher au Best Estimate."""
        from direction_non_vie.provisionnement.a7_provisionnement import (
            n2_hypotheses_munich as mod)
        src = io.open(mod.__file__, encoding='utf-8').read()
        arbre = ast.parse(src)
        noms = {n.id for n in ast.walk(arbre)
                if isinstance(n, ast.Name)} | \
               {n.attr for n in ast.walk(arbre) if isinstance(n, ast.Attribute)} | \
               {c.value for c in ast.walk(arbre)
                if isinstance(c, ast.Constant) and isinstance(c.value, str)}
        for interdit in ('methodes_incluses', 'best_estimate', 'poids',
                         'seuil_score', '_CLES_N3'):
            self.assertNotIn(interdit, noms,
                             f"{interdit} n'a rien à faire dans ce module")

    def test_mh13_formateur_ne_fabrique_jamais_de_defaut(self):
        """Bloc absent → cinq NON TESTABLE, jamais un vert par défaut."""
        lignes = lignes_hypotheses_munich({})
        self.assertEqual(len(lignes), len(CODES))
        for l in lignes:
            self.assertEqual(l['statut'], 'NON TESTABLE')
            self.assertFalse(l['ok'])

    def test_mh14_les_trois_formats_portent_le_bloc(self):
        """HTML, Word ET Excel — vérifiés sur de vrais fichiers générés.

        ⚠️ La mention MCL-H4 était TRONQUÉE : Word coupait les messages à 80
        caractères (14/14 lignes rognées, médiane 170) et Excel à 200 (5/14).
        Le chiffre de 20 % — la seule information du bloc — disparaissait.
        """
        import zipfile
        from direction_non_vie.provisionnement.a7_provisionnement.agent import (
            AgentA7Provisionnement)
        from direction_non_vie.provisionnement.a7_provisionnement.n5_excel import (
            export_excel)
        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
            export_html, export_word)

        C = np.asarray(_MCL_PAYE, float)
        r = AgentA7Provisionnement(verbose=False).run(
            source=C, triangle_engage=np.asarray(_MCL_ENG_SAIN, float),
            lob='rc_generale', mode_declare='cumule', generer_graphiques=False,
            generer_word=False, generer_pdf_flag=False,
            n_sim_bootstrap=200, seed=42)
        n1, n2, n3, n4 = r.get('n1', {}), r['n2'], r['n3'], r['n4']
        self.assertIn('munich_hyp', n2, "l'agent doit publier le bloc")

        html = export_html(n1=n1, n2=n2, n3=n3, n4=n4)
        self.assertIn('MCL-H', html)
        self.assertIn('puissance mesurée', html)

        docx = export_word(n1, n2, n3, n4)
        self.assertGreater(len(docx), 1024, 'python-docx absent ?')
        with zipfile.ZipFile(io.BytesIO(docx)) as z:
            txt = b''.join(z.read(k) for k in z.namelist() if k.endswith('.xml'))
        self.assertIn(b'MCL-H', txt)
        self.assertIn('20 %'.encode(), txt)

        import openpyxl
        xls = export_excel(C, n1, n2, n3, n4)
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              '_mcl_hyp_test.xlsx')
        try:
            io.open(chemin, 'wb').write(xls)
            ws = openpyxl.load_workbook(chemin)['6. Hypothèses']
            cells = [v for row in ws.iter_rows(values_only=True)
                     for v in row if isinstance(v, str)]
            self.assertTrue(any('MCL-H4' in c for c in cells))
            # message COMPLET, pas tronqué
            self.assertTrue(any(c == MESSAGE_H4 for c in cells),
                            "la mention MCL-H4 doit être entière")
        finally:
            if os.path.exists(chemin):
                os.remove(chemin)


if __name__ == '__main__':
    unittest.main(verbosity=2)
