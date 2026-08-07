# -*- coding: utf-8 -*-
"""Tests U1b — la persistance du registre, et ses trois invariants.

⚠️ GATE : `py -m unittest discover -s normes -t .` — voir test_contrat.py.
⚠️ C'est le module qui introduit les ENTRÉES-SORTIES, donc celui où les
défauts vivent. Les invariants y sont testés sur leur mécanique, pas sur
leur énoncé.
"""
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from normes.ifrs17.socle import registre as R
from normes.ifrs17.socle.confirmation import Confirmation
from normes.ifrs17.socle.groupe import (
    CLASSE_16A, CleGroupe, convention_exercice)
from normes.ifrs17.socle.registre import (
    API_PUBLIQUE, FORMAT_REGISTRE, MOTIF_CLE_DIVERGENTE,
    MOTIF_FORMAT_INCONNU, MOTIF_RECLASSIFICATION,
    TRACE_APPARTENANCE_NON_TRACABLE, GroupeEnregistre, Membre, Registre,
    RefusRegistre, ajouter, ecrire, groupe, ouvrir, relire, resume)

ARRETE_2026 = '2026-06-30'
ARRETE_2027 = '2027-06-30'


def _ligne(ident='P-001', **kw):
    base = {'identifiant_contrat': ident, 'portefeuille': 'rc_auto',
            'date_emission': '2026-03-15', 'debut_couverture': '2026-04-01',
            'fin_couverture': '2027-03-31'}
    base.update(kw)
    return base


def _conf(arrete):
    """Une confirmation signee — le scellement exige un signataire (U1d)."""
    return Confirmation('Actuaire Test', arrete, ())


C26 = _conf(ARRETE_2026)
C27 = _conf(ARRETE_2027)


def _fichier():
    return Path(tempfile.mkdtemp()) / 'registre.json'


class T1_InvariantAucunMontant(unittest.TestCase):
    """T1 — le registre répond à « quels groupes », pas à « combien »."""

    def test_aucun_champ_monetaire(self):
        for structure in (GroupeEnregistre, Membre, Registre):
            for champ in structure._fields:
                for interdit in ('prime', 'montant', 'euro', 'valeur', 'be',
                                 'lrc', 'lic', 'solde', 'total'):
                    self.assertNotIn(interdit, champ,
                                     f"{structure.__name__}.{champ}")
        self.assertEqual(set(GroupeEnregistre._fields), {
            'cle', 'date_compta_25', 'origine_date_25', 'eligibilite_paa',
            'motif_eligibilite', 'arrete_creation', 'nb_lignes', 'membres',
            'traces'})
        print(f"    OK T1 : {len(GroupeEnregistre._fields)} champs de groupe, "
              "aucun monetaire — frontiere avec le magasin de clotures tenue")

    def test_le_fichier_ecrit_ne_contient_aucun_montant(self):
        """Le verrou porte sur le LIVRABLE, pas seulement sur la structure.

        ⚠️ IL PORTE SUR LES CLEFS ET LES VALEURS, PAS SUR LA PROSE. Le motif
        du §25 explique que les critères b) et c) sont hors de portée « faute
        de donnée sur l'échéance des primes » : le mot y est légitime. Ce qui
        ne doit pas s'y trouver, c'est un montant.
        """
        r = ajouter(ouvrir('CLI', 'ENT'),
                    [_ligne(prime=1234.56, frais_acquisition=99.9)],
                    ARRETE_2026, C26)
        brut = json.loads(ecrire(r, _fichier()).read_text(encoding='utf-8'))

        def clefs(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    yield k
                    yield from clefs(v)
            elif isinstance(o, list):
                for v in o:
                    yield from clefs(v)

        for k in clefs(brut):
            for interdit in ('prime', 'montant', 'euro', 'frais', 'valeur',
                             'solde', 'total'):
                self.assertNotIn(interdit, k, f"clef monétaire : {k}")
        for valeur in ('1234', '99.9'):
            self.assertNotIn(valeur, json.dumps(brut))
        print("    OK T1b : ni prime ni frais d'acquisition n'atteignent "
              "le fichier — verifie sur les CLEFS et les VALEURS")


class T2_InvariantAucuneModification(unittest.TestCase):
    """T2 — c'est l'ABSENCE de la fonction qui rend le geste impossible."""

    def test_la_surface_publique_est_close(self):
        publiques = {n for n, o in vars(R).items()
                     if inspect.isfunction(o) and not n.startswith('_')
                     and o.__module__ == R.__name__}
        self.assertEqual(publiques, set(API_PUBLIQUE))
        print(f"    OK T2 : {len(publiques)} fonctions publiques, "
              f"liste close : {', '.join(sorted(publiques))}")

    def test_aucun_verbe_de_modification_ni_de_suppression(self):
        for verbe in ('modifier', 'supprimer', 'retirer', 'changer',
                      'reclasser', 'corriger', 'update', 'delete', 'remove',
                      'set_', 'ecraser', 'vider', 'purger'):
            for nom in API_PUBLIQUE:
                self.assertNotIn(verbe, nom)
        print("    OK T2b : aucun verbe de modification dans l'API")

    def test_les_structures_sont_immuables(self):
        r = ajouter(ouvrir('CLI', 'ENT'), [_ligne()], ARRETE_2026, C26)
        with self.assertRaises(AttributeError):
            r.groupes = ()
        with self.assertRaises(AttributeError):
            r.groupes[0].eligibilite_paa = 'ELIGIBLE'
        print("    OK T2c : Registre et GroupeEnregistre sont immuables")

    def test_ajouter_rend_un_nouveau_registre_sans_toucher_l_ancien(self):
        r0 = ouvrir('CLI', 'ENT')
        r1 = ajouter(r0, [_ligne()], ARRETE_2026, C26)
        self.assertEqual(len(r0.groupes), 0)
        self.assertEqual(len(r1.groupes), 1)
        self.assertIsNot(r0, r1)
        print("    OK T2d : ajouter() n'altere pas le registre recu")


class T3_InvariantAucuneReclassification(unittest.TestCase):
    """T3 — §24 : « ne doit pas revoir la composition par la suite »."""

    def test_un_contrat_qui_change_de_groupe_est_refuse(self):
        """⚠️ LE CAS REEL : un inventaire corrige ou la classe §16 a bouge."""
        r = ajouter(ouvrir('CLI', 'ENT'), [_ligne('P-001')], ARRETE_2026, C26)
        with self.assertRaises(RefusRegistre) as ctx:
            ajouter(r, [_ligne('P-001', classe_profitabilite=CLASSE_16A)],
                    ARRETE_2027, C27)
        self.assertEqual(ctx.exception.motif, MOTIF_RECLASSIFICATION)
        msg = str(ctx.exception)
        self.assertIn('P-001', msg)
        self.assertIn('rc_auto|AUTRES|2026', msg)
        self.assertIn('rc_auto|DEFICITAIRE|2026', msg)
        self.assertIn('§24', msg)
        print("    OK T3 : reclassification refusee, avec le contrat "
              "et LES DEUX groupes nommes")

    def test_un_changement_de_cohorte_est_aussi_une_reclassification(self):
        r = ajouter(ouvrir('CLI', 'ENT'), [_ligne('P-001')], ARRETE_2026, C26)
        with self.assertRaises(RefusRegistre) as ctx:
            ajouter(r, [_ligne('P-001', date_emission='2025-03-15')],
                    ARRETE_2027, C27)
        self.assertEqual(ctx.exception.motif, MOTIF_RECLASSIFICATION)
        print("    OK T3b : changer la cohorte d'un contrat enregistre "
              "est refuse")

    def test_la_resoumission_dans_le_meme_groupe_est_absorbee(self):
        """Pas un doublon, pas un refus : une resoumission tracee."""
        r = ajouter(ouvrir('CLI', 'ENT'), [_ligne('P-001')], ARRETE_2026, C26)
        r2 = ajouter(r, [_ligne('P-001'), _ligne('P-002')], ARRETE_2027, C27)
        g = r2.groupes[0]
        self.assertEqual(len(g.membres), 2)
        self.assertEqual(g.nb_lignes, 2)
        self.assertTrue(any('resoumission absorbée' in t for t in g.traces))
        print(f"    OK T3c : 1 + 2 lignes -> {len(g.membres)} membres, "
              "resoumission absorbee et tracee")

    def test_sans_identifiant_l_appartenance_n_est_pas_tracable_et_le_dit(self):
        """⚠️ LE FICHIER MINIMAL DE 4 COLONNES N'A PAS D'IDENTIFIANT."""
        ligne = {'portefeuille': 'rc_auto', 'date_emission': '2026-03-15',
                 'fin_couverture': '2027-03-14'}
        r = ajouter(ouvrir('CLI', 'ENT'), [ligne], ARRETE_2026, C26)
        g = r.groupes[0]
        self.assertEqual(g.membres, ())
        self.assertEqual(g.nb_lignes, 1)
        self.assertIn(TRACE_APPARTENANCE_NON_TRACABLE, g.traces)
        print("    OK T3d : sans identifiant, le groupe existe mais "
              "l'appartenance est declaree non tracable")


class T4_LesScellesNeSEcrasentPas(unittest.TestCase):
    """T4 — §53 s'apprécie à la création ; la divergence se dit."""

    def test_le_verdict_53_scelle_l_emporte_et_l_ecart_est_trace(self):
        r = ajouter(ouvrir('CLI', 'ENT'), [_ligne('P-001')], ARRETE_2026, C26)
        self.assertEqual(r.groupes[0].eligibilite_paa, 'ELIGIBLE')
        # un contrat de 3 ans rejoint le meme groupe : la derivation dirait
        # NON_ELIGIBLE, mais le verdict a ete scelle a la creation
        r2 = ajouter(r, [_ligne('P-002', fin_couverture='2029-03-31')],
                     ARRETE_2027, C27)
        g = r2.groupes[0]
        self.assertEqual(g.eligibilite_paa, 'ELIGIBLE')
        self.assertEqual(g.arrete_creation, ARRETE_2026, C26)
        self.assertTrue(any('SCELLÉ' in t and '§53' in t for t in g.traces))
        print("    OK T4 : verdict §53 conserve, divergence TRACEE "
              "-- ni ecrase, ni tu")

    def test_la_date_25_et_l_arrete_de_creation_ne_bougent_pas(self):
        r = ajouter(ouvrir('CLI', 'ENT'), [_ligne('P-001')], ARRETE_2026, C26)
        d25 = r.groupes[0].date_compta_25
        r2 = ajouter(r, [_ligne('P-002', debut_couverture='2026-01-01')],
                     ARRETE_2027, C27)
        self.assertEqual(r2.groupes[0].date_compta_25, d25)
        self.assertEqual(r2.groupes[0].arrete_creation, ARRETE_2026, C26)
        print(f"    OK T4b : §25 reste {d25}, arrete de creation reste "
              f"{ARRETE_2026}")


class T5_EcrireEtRelire(unittest.TestCase):
    """T5 — le livrable, et sa relecture."""

    def test_aller_retour_fidele(self):
        r = ajouter(ouvrir('CLI', 'ENT', convention_exercice(4)),
                    [_ligne('P-001'), _ligne('P-002', portefeuille='mrh')],
                    ARRETE_2026, C26)
        p = ecrire(r, _fichier())
        relu = relire(p)
        self.assertEqual(relu, r)
        print(f"    OK T5 : aller-retour fidele sur {len(r.groupes)} groupes, "
              f"convention {relu.convention.libelle} conservee")

    def test_l_ecriture_est_deterministe(self):
        """Un livrable auditable ne change pas de forme sans changer de fond."""
        r = ajouter(ouvrir('CLI', 'ENT'),
                    [_ligne('P-00%d' % i) for i in range(5)], ARRETE_2026, C26)
        a, b = _fichier(), _fichier()
        self.assertEqual(ecrire(r, a).read_bytes(), ecrire(r, b).read_bytes())
        print("    OK T5b : deux ecritures du meme registre -> memes octets")

    def test_un_format_inconnu_est_refuse(self):
        p = _fichier()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"format": "autre/9", "client": "X"}', encoding='utf-8')
        with self.assertRaises(RefusRegistre) as ctx:
            relire(p)
        self.assertEqual(ctx.exception.motif, MOTIF_FORMAT_INCONNU)
        self.assertIn(FORMAT_REGISTRE, str(ctx.exception))
        print("    OK T5c : un format inconnu est refuse, pas devine")

    def test_l_arrete_d_entree_est_conserve_par_membre(self):
        """⚠️ SANS LUI, IMPOSSIBLE DE REJOUER UNE CLOTURE PASSEE (B73)."""
        r = ajouter(ouvrir('CLI', 'ENT'), [_ligne('P-001')], ARRETE_2026, C26)
        r = ajouter(r, [_ligne('P-002')], ARRETE_2027, C27)
        entrees = {m.cle_contrat: m.arrete_entree
                   for m in relire(ecrire(r, _fichier())).groupes[0].membres}
        self.assertEqual(entrees, {'P-001': ARRETE_2026, 'P-002': ARRETE_2027})
        print(f"    OK T5d : arretes d'entree conserves {entrees}")


class T6_SurfaceEtRefus(unittest.TestCase):
    """T6 — la clé du registre, et la lecture d'un groupe."""

    def test_client_ou_entite_vide_refuse(self):
        for c, e in (('', 'ENT'), ('CLI', ''), ('  ', 'ENT')):
            with self.assertRaises(RefusRegistre) as ctx:
                ouvrir(c, e)
            self.assertEqual(ctx.exception.motif, MOTIF_CLE_DIVERGENTE)
        print("    OK T6 : la cle (client, entite) ne peut pas etre vide")

    def test_lire_un_groupe_absent_leve(self):
        r = ajouter(ouvrir('CLI', 'ENT'), [_ligne()], ARRETE_2026, C26)
        self.assertEqual(groupe(r, r.groupes[0].cle), r.groupes[0])
        with self.assertRaises(KeyError):
            groupe(r, CleGroupe('inconnu', 'AUTRES', '2026'))
        print("    OK T6b : un groupe absent leve, il ne rend pas un defaut")

    def test_la_convention_du_registre_gouverne(self):
        """Personne ne verse sous une convention differente de celle
        qui a scelle les groupes existants."""
        r = ajouter(ouvrir('CLI', 'ENT', convention_exercice(4)),
                    [_ligne('P-001', date_emission='2026-02-15')],
                    ARRETE_2026, C26)
        self.assertEqual(r.groupes[0].cle.cohorte, '2025-26')
        print(f"    OK T6c : cohorte {r.groupes[0].cle.cohorte} — "
              "la convention du registre gouverne")

    def test_le_resume_dit_ce_qui_est_suivi_nominativement(self):
        r = ajouter(ouvrir('CLI', 'ENT'),
                    [_ligne('P-001'),
                     {'portefeuille': 'mrh', 'date_emission': '2026-01-05',
                      'fin_couverture': '2027-01-04'}], ARRETE_2026, C26)
        txt = resume(r)
        self.assertIn('2 groupe(s), 2 ligne(s), 1 contrat(s) suivi(s)', txt)
        print("    OK T6d : le resume distingue les lignes des contrats suivis")


if __name__ == '__main__':
    unittest.main(verbosity=2)
