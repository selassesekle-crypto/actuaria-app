# -*- coding: utf-8 -*-
"""Tests U1c-1 — §28 : ce qui arrive quand un contrat entre.

⚠️ GATE : `py -m unittest discover -s normes -t .` — voir test_contrat.py.
"""
import unittest
from datetime import date

from normes.ifrs17.socle.entree import (
    CREE, EFFETS, REJOINT, Entree, analyser, resume_entrees,
    trace_reconnaissance_tardive)
from normes.ifrs17.socle.groupe import (
    CONVENTION_CALENDAIRE, CleGroupe, convention_exercice)
from normes.ifrs17.socle.registre import ajouter, ouvrir


def _ligne(ident='P-001', emission='2026-03-15', **kw):
    base = {'identifiant_contrat': ident, 'portefeuille': 'rc_auto',
            'date_emission': emission, 'debut_couverture': emission,
            'fin_couverture': '2027-03-14'}
    base.update(kw)
    return base


class T1_LesDeuxSeulsEffets(unittest.TestCase):
    """T1 — un contrat rejoint, ou crée. Il n'y a pas de troisième cas."""

    def test_cree_quand_aucun_groupe_ne_porte_la_cle(self):
        e = analyser(set(), _ligne(), CONVENTION_CALENDAIRE,
                     date(2026, 6, 30))
        self.assertEqual(e.effet, CREE)
        self.assertEqual(e.cle, CleGroupe('rc_auto', 'AUTRES', '2026'))
        print(f"    OK T1 : aucune cle existante -> {e.effet} "
              f"({e.cle.texte})")

    def test_rejoint_quand_la_cle_existe(self):
        cle = CleGroupe('rc_auto', 'AUTRES', '2026')
        e = analyser({cle}, _ligne(), CONVENTION_CALENDAIRE,
                     date(2026, 6, 30))
        self.assertEqual(e.effet, REJOINT)
        print(f"    OK T1b : cle deja presente -> {e.effet}")

    def test_il_n_y_a_que_deux_effets(self):
        """⚠️ NI REFUS, NI RECLASSEMENT, NI DOUBLON DE CLE."""
        self.assertEqual(set(EFFETS), {REJOINT, CREE})
        self.assertEqual(len(EFFETS), 2)
        print(f"    OK T1c : {len(EFFETS)} effets possibles, pas un de plus")


class T2_LaFenetreFermeeNExistePas(unittest.TestCase):
    """T2 — la correction de ma propre conception, verrouillée.

    J'avais écrit qu'un contrat de cohorte 2024 déclaré en 2027 créerait un
    NOUVEAU groupe de cohorte 2024, la fenêtre étant close. §28 dit l'inverse
    — « l'entité PEUT AJOUTER de nouveaux contrats au groupe APRÈS LA DATE DE
    CLÔTURE » — et aucun des 303 paragraphes de la norme ne ferme un groupe.
    """

    def test_un_contrat_ancien_rejoint_le_groupe_de_sa_cohorte(self):
        cle_2024 = CleGroupe('rc_auto', 'AUTRES', '2024')
        e = analyser({cle_2024}, _ligne(emission='2024-05-10'),
                     CONVENTION_CALENDAIRE, date(2027, 6, 30))
        self.assertEqual(e.effet, REJOINT)
        self.assertEqual(e.cle, cle_2024)
        print("    OK T2 : contrat de cohorte 2024 declare en 2027 -> "
              "REJOINT le groupe 2024, il n'en cree pas un second")

    def test_la_cle_reste_unique(self):
        """Deux groupes de meme cle briseraient l'identite du groupe (§24)."""
        r = ajouter(ouvrir('CLI', 'ENT'),
                    [_ligne('P-001', '2024-05-10')], '2024-12-31')
        r = ajouter(r, [_ligne('P-002', '2024-11-20')], '2027-06-30')
        cles = [g.cle for g in r.groupes]
        self.assertEqual(len(cles), len(set(cles)))
        self.assertEqual(len(r.groupes), 1)
        self.assertEqual(r.groupes[0].nb_lignes, 2)
        print(f"    OK T2b : {len(r.groupes)} groupe, "
              f"{r.groupes[0].nb_lignes} lignes — aucune cle dupliquee")

    def test_un_contrat_ancien_n_est_jamais_refuse(self):
        r = ajouter(ouvrir('CLI', 'ENT'),
                    [_ligne('P-001', '2021-02-01')], '2027-06-30')
        self.assertEqual(len(r.groupes), 1)
        self.assertEqual(r.groupes[0].cle.cohorte, '2021')
        print("    OK T2c : un contrat de 2021 declare en 2027 entre, "
              "il n'est pas refuse")


class T3_LeRetardEstDerive(unittest.TestCase):
    """T3 — dérivé de deux faits enregistrés, jamais stocké (leçon de D3)."""

    def test_le_retard_se_calcule_des_periodes(self):
        e = analyser(set(), _ligne(emission='2024-05-10'),
                     CONVENTION_CALENDAIRE, date(2027, 6, 30))
        self.assertEqual(e.periode_25, '2024')
        self.assertEqual(e.periode_entree, '2027')
        self.assertEqual(e.retard_periodes, 3)
        print(f"    OK T3 : §25 en {e.periode_25}, entree en "
              f"{e.periode_entree} -> retard {e.retard_periodes}")

    def test_aucun_champ_de_fenetre_n_est_stocke(self):
        """⚠️ UN ETAT STOCKE PEUT CONTREDIRE LA DONNEE QUI LE DETERMINE."""
        for champ in Entree._fields:
            for interdit in ('ouvert', 'ferme', 'statut', 'fenetre'):
                self.assertNotIn(interdit, champ)
        self.assertEqual(set(Entree._fields), {
            'cle', 'effet', 'periode_25', 'periode_entree',
            'retard_periodes'})
        print("    OK T3b : aucun champ d'etat de fenetre — "
              "le retard se derive des periodes")

    def test_une_entree_dans_les_temps_n_a_aucun_retard(self):
        e = analyser(set(), _ligne(emission='2026-03-15'),
                     CONVENTION_CALENDAIRE, date(2026, 12, 31))
        self.assertEqual(e.retard_periodes, 0)
        self.assertIsNone(trace_reconnaissance_tardive(e))
        print("    OK T3c : entree dans sa periode -> aucun retard, "
              "aucune trace")

    def test_la_convention_du_registre_gouverne_le_retard(self):
        """Fevrier 2026 : cohorte 2026 en calendaire, 2025-26 en avril-mars —
        donc un retard different vu d'un meme arrete."""
        ligne = _ligne(emission='2026-02-15')
        cal = analyser(set(), ligne, CONVENTION_CALENDAIRE, date(2026, 6, 30))
        exo = analyser(set(), ligne, convention_exercice(4),
                       date(2026, 6, 30))
        self.assertEqual(cal.retard_periodes, 0)
        self.assertEqual(exo.retard_periodes, 1)
        print(f"    OK T3d : meme contrat, retard {cal.retard_periodes} en "
              f"calendaire et {exo.retard_periodes} en avril-mars")


class T4_LaTraceNommeSansBloquer(unittest.TestCase):
    """T4 — §28 autorise l'ajout ; l'écart de date relève d'IAS 8."""

    def test_la_trace_nomme_le_retard_et_renvoie_a_IAS_8(self):
        e = analyser(set(), _ligne(emission='2024-05-10'),
                     CONVENTION_CALENDAIRE, date(2027, 6, 30))
        t = trace_reconnaissance_tardive(e)
        self.assertIn('reconnaissance tardive', t)
        self.assertIn('3 période(s)', t)
        self.assertIn('§28', t)
        self.assertIn('IAS 8', t)
        self.assertIn('Le contrat est enregistré', t)
        print("    OK T4 : la trace nomme le retard, cite §28 et IAS 8, "
              "et dit que le contrat EST enregistre")

    def test_le_registre_porte_la_trace_sur_le_groupe(self):
        r = ajouter(ouvrir('CLI', 'ENT'),
                    [_ligne('P-001', '2024-05-10')], '2027-06-30')
        self.assertTrue(any('reconnaissance tardive' in t
                            for t in r.groupes[0].traces))
        print("    OK T4b : la trace remonte jusqu'au groupe enregistre")

    def test_le_resume_compte_les_entrees(self):
        cle = CleGroupe('rc_auto', 'AUTRES', '2026')
        entrees = [
            analyser({cle}, _ligne('A'), CONVENTION_CALENDAIRE,
                     date(2026, 6, 30)),
            analyser(set(), _ligne('B', '2024-01-05'), CONVENTION_CALENDAIRE,
                     date(2026, 6, 30)),
        ]
        txt = resume_entrees(entrees)
        self.assertIn('1 rejoignent un groupe existant', txt)
        self.assertIn('1 groupe(s) créé(s)', txt)
        self.assertIn('reconnaissance tardive', txt)
        print("    OK T4c : le resume distingue rejoint, cree et tardif")


if __name__ == '__main__':
    unittest.main(verbosity=2)
