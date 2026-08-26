# -*- coding: utf-8 -*-
"""CONTRÔLES POSITIFS — l'archive vérifiable du livrable de tarification.

Sur le modèle A7 : écriture avec empreinte + `verifier_archive` + portée
déclarée (intégrité, jamais signature). Deux garanties DISTINCTES :
  · reproductibilité du CONTENU  → l'empreinte du PLAN (`s1:`, chantier S3) ;
  · intégrité du DOCUMENT         → le sha256 de CE mécanisme.

⚠️ LE SCEAU (condition ④) : sans `verifier_archive`, l'empreinte est
décorative. On l'ÉPINGLE par une ALTÉRATION PLANTÉE — on archive, on flippe un
octet sur disque, et la vérification DOIT rougir.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from direction_non_vie.tarification.services.archive_livrable import (
    archiver_livrable, verifier_archive, charger_manifeste,
    PORTEE_ARCHIVE_TARIF, _TAILLE_MIN_LIVRABLE)


def _out(html=b'', word=b'', pdf=b'', excel=b''):
    return {'html_bytes': html, 'word_bytes': word,
            'pdf_bytes': pdf, 'excel_bytes': excel}


#: Des octets « livrables » (>= seuil) et un repli (< seuil).
_GROS = b'<html>' + b'x' * 2000
_GROS2 = b'PK\x03\x04' + b'y' * 2000
_REPLI = b'vide'


class TestArchiverEtManifeste(unittest.TestCase):

    def test_ecrit_les_fichiers_et_leurs_empreintes(self):
        d = tempfile.mkdtemp()
        archive, err = archiver_livrable(d, 'RUN1', _out(html=_GROS, word=_GROS2))
        self.assertIsNone(err)
        self.assertTrue((Path(d) / 'RUN1' / 'rapport.html').exists())
        self.assertTrue((Path(d) / 'RUN1' / 'rapport.docx').exists())
        self.assertIn('rapport.html', archive['fichiers'])
        self.assertEqual(len(archive['fichiers']['rapport.html']['sha256']), 64)

    def test_manifeste_persiste_SEPARE_du_dossier(self):
        # ⚠️ voie B : le sha256 vit dans {id}.archive.json, PAS dans {id}/.
        d = tempfile.mkdtemp()
        archive, _ = archiver_livrable(d, 'RUN2', _out(html=_GROS))
        manifeste = Path(d) / 'RUN2.archive.json'
        self.assertTrue(manifeste.exists())
        self.assertFalse((Path(d) / 'RUN2' / 'RUN2.archive.json').exists())
        # rechargé depuis le disque, il reste utilisable et intact
        recharge = charger_manifeste(d, 'RUN2')
        self.assertEqual(recharge['dossier'], archive['dossier'])
        self.assertEqual(verifier_archive(recharge)['intact'], True)

    def test_repli_sous_le_seuil_non_archive(self):
        d = tempfile.mkdtemp()
        self.assertLess(len(_REPLI), _TAILLE_MIN_LIVRABLE)
        archive, _ = archiver_livrable(d, 'RUN3', _out(html=_GROS, word=_REPLI))
        self.assertIn('rapport.html', archive['fichiers'])
        self.assertNotIn('rapport.docx', archive['fichiers'])   # repli écarté


class TestVerifierArchive(unittest.TestCase):

    def test_intact_sur_dossier_sain(self):
        d = tempfile.mkdtemp()
        archive, _ = archiver_livrable(d, 'OK', _out(html=_GROS, excel=_GROS2))
        v = verifier_archive(archive)
        self.assertEqual(v['verifiable'], True)
        self.assertEqual(v['intact'], True)
        self.assertEqual(v['ecarts'], [])

    def test_SCEAU_alteration_plantee_est_detectee(self):
        # ⚠️⚠️ LE SCEAU (④). On archive, la vérif est verte ; on ALTÈRE un
        # octet sur disque SANS toucher le manifeste ; la vérif DOIT rougir et
        # NOMMER le fichier. C'est ce qui rend l'empreinte non décorative.
        d = tempfile.mkdtemp()
        archive, _ = archiver_livrable(d, 'ALT', _out(html=_GROS, word=_GROS2))
        self.assertEqual(verifier_archive(archive)['intact'], True)   # sain d'abord
        cible = Path(archive['dossier']) / 'rapport.html'
        octets = cible.read_bytes()
        cible.write_bytes(octets[:-1] + bytes([octets[-1] ^ 0x01]))    # 1 bit flippé
        v = verifier_archive(archive)
        self.assertEqual(v['intact'], False)
        self.assertTrue(any('rapport.html' in e and 'altere' in e for e in v['ecarts']),
                        f"l'écart ne nomme pas le fichier altéré : {v['ecarts']}")

    def test_fichier_absent_est_detecte(self):
        d = tempfile.mkdtemp()
        archive, _ = archiver_livrable(d, 'DEL', _out(html=_GROS, word=_GROS2))
        (Path(archive['dossier']) / 'rapport.docx').unlink()   # on supprime un fichier
        v = verifier_archive(archive)
        self.assertEqual(v['intact'], False)
        self.assertTrue(any('rapport.docx' in e and 'absent' in e for e in v['ecarts']))

    def test_sans_dossier_non_verifiable(self):
        v = verifier_archive({})
        self.assertEqual(v['verifiable'], False)
        self.assertIsNone(v['intact'])


class TestPorteeArchive(unittest.TestCase):

    def test_porte_les_trois_negations(self):
        # La portée doit dire ce qu'elle NE prouve PAS : juste, signé, opposable.
        p = PORTEE_ARCHIVE_TARIF.lower()
        self.assertIn('juste', p)          # pas la justesse du tarif (c'est le PLAN)
        self.assertIn('sign', p)           # pas la signature
        self.assertIn('opposable', p)      # pas l'opposabilité
        self.assertIn('declarative', p)    # la relecture reste déclarative

    def test_la_portee_est_rendue_par_la_verification(self):
        # Publiée aux trois endroits : constante, manifeste, retour de vérif.
        d = tempfile.mkdtemp()
        archive, _ = archiver_livrable(d, 'P', _out(html=_GROS))
        self.assertEqual(archive['porte'], PORTEE_ARCHIVE_TARIF)
        self.assertEqual(verifier_archive(archive)['porte'], PORTEE_ARCHIVE_TARIF)


class TestArchiveViaA6(unittest.TestCase):
    """Le POINT D'ATTACHE : A6 avec `archiver=True` écrit l'archive du livrable
    signé (le rapport consolidé équipe), manifeste séparé, vérifiable."""

    def test_a6_archiver_produit_une_archive_verifiable(self):
        from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
        # fixtures RÉUTILISÉES (pas de duplication) — mêmes que test_a6_comparaison
        from direction_non_vie.tarification.a6_comparaison.test_a6_comparaison import (
            _make_r_a2_avec_annee, _make_r_a3, _make_r_a4)
        d = tempfile.mkdtemp()
        agent = AgentA6Comparaison(models_path=tempfile.mkdtemp(),
                                   audit_path=d, verbose=False)
        r = agent.run(
            result_a2=_make_r_a2_avec_annee(800), result_a3=_make_r_a3(),
            result_a4=_make_r_a4(), result_a5=None,
            col_cible='prime_pure', col_expo='exposition',
            generer_graphiques=False, aide_decision=True,
            archiver=True)                       # ← le drapeau, activé ici seulement
        self.assertTrue(r['success'], r.get('erreur'))
        self.assertIsNone(r['archive_erreur'])
        self.assertTrue(r['archive'].get('fichiers'), "aucun fichier archivé")
        self.assertEqual(verifier_archive(r['archive'])['intact'], True)
        # manifeste persisté, SÉPARÉ du dossier (voie B)
        self.assertTrue((Path(d) / f"{r['audit_id']}.archive.json").exists())

    def test_a6_dormant_par_defaut(self):
        # ⚠️ Dormant, comme l'arrête de C1 : sans `archiver=True`, rien n'est
        # archivé. On vérifie le défaut du paramètre (sans relancer A6).
        import inspect
        from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
        self.assertIs(
            inspect.signature(AgentA6Comparaison.run).parameters['archiver'].default,
            False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
