# -*- coding: utf-8 -*-
"""Tests O1-O3 — l'état daté : ce qu'il assemble, et ses TROIS refus.

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️ LE TEST QUI PORTE CE LOT EST `test_LES_ARTICULATIONS_CESSENT_D_ETRE_
FACULTATIVES` : les deux contrôles existaient, étaient testés, et PERSONNE
NE LES APPELAIT.
"""
import ast
import pathlib
import unittest

from normes.ifrs17.etats.assemblage import (
    ARTICULATION_80_100,
    ARTICULATION_99B,
    CE_QUI_MANQUE_ENCORE,
    ETABLIE,
    INDISPENSABLES,
    MOTIF_ABSENCE_SANS_MOTIF,
    MOTIF_ETAT_CONTREDIT,
    MOTIF_PIECE_INCONNUE,
    MOTIF_PIECE_INDISPENSABLE_ABSENTE,
    MOTIF_PIECE_NI_FOURNIE_NI_DECLAREE,
    NON_ETABLIE,
    PIECES,
    EtatDate,
    assembler,
)
from normes.ifrs17.mesure.bilan import SoldeGroupe, etat_situation_financiere
from normes.ifrs17.mesure.declaration import ContexteEvaluation
from normes.ifrs17.mesure.lrc_paa import RefusMesure
from normes.ifrs17.socle.cloture import NATURE_EMIS, NATURE_REASSURANCE_DETENUE

PTF = ('DO', 'MRH')
CONTEXTE = ContexteEvaluation(arrete='2026-12-31', portefeuilles=PTF)
SOLDES = (SoldeGroupe('DO', 'DO|AUTRES|2026', 1000.0),
          SoldeGroupe('MRH', 'MRH|AUTRES|2026', -300.0))
BILAN = etat_situation_financiere(list(SOLDES), CONTEXTE)

#: Un résultat qui s'articule au déroulé : chaque ligne vaut son opposé.
DEROULE = {'revenue_du_deroule': -800.0, 'charges_du_deroule': 500.0,
           'charges_financieres_du_deroule': 60.0}


class _Resultat:
    """⚠️ Un double minimal : `verifier_articulation` ne lit que trois
    champs, et les fabriquer ici évite de faire dépendre ce test de la
    construction complète du §80."""
    insurance_revenue = 800.0
    insurance_service_expenses = -500.0
    charges_financieres = -60.0


def _pieces(**kw):
    base = {'PERIMETRE_PUBLIE': 'PÉRIMÈTRE IFRS 17 — …',
            'BILAN_78': BILAN, 'RESULTAT_80': _Resultat()}
    base.update(kw)
    return base


def _absences(**kw):
    base = {'RAPPROCHEMENTS_100': 'premier exercice, aucune ouverture signée',
            'NOTES_97_119_120': 'les cinq declarations ne sont pas signees',
            'REGISTRE_DES_GROUPES': 'premier exercice, aucun registre',
            'DEVELOPPEMENT_130': 'aucune donnee de sinistres remise',
            'FINANCEMENT_56': 'aucun groupe a composante financement'}
    base.update(kw)
    return base


def _assembler(pieces=None, absences=None, **kw):
    return assembler(arrete='2026-12-31', entite='MutuelleTest',
                     pieces=_pieces() if pieces is None else pieces,
                     absences=_absences() if absences is None else absences,
                     **kw)


class O1_LEtatEstUnOBJET(unittest.TestCase):
    """⚠️ UN ÉTAT DATÉ DOIT SE RELIRE, SE COMPARER ET SE REGROUPER. Un
    document ne se compare pas — et §96 laisse la maille à l'entité."""

    def test_l_etat_rend_une_structure_pas_un_texte(self):
        e = _assembler()
        self.assertIsInstance(e, EtatDate)
        self.assertEqual(e.arrete, '2026-12-31')
        self.assertEqual(len(e.pieces), len(PIECES))
        self.assertEqual(len(e.articulations), 2)
        print(f"    OK O1 : {len(e.pieces)} pieces, 2 articulations, un OBJET")

    def test_le_vocabulaire_des_pieces_est_CLOS_et_porte_ses_paragraphes(self):
        """⚠️ Un CAC lit la référence, pas l'identifiant Python."""
        self.assertEqual(len(PIECES), 8)
        for nom, ref in PIECES.items():
            self.assertTrue(ref.strip(), nom)
        self.assertEqual(PIECES['BILAN_78'], '§78-79')

    def test_une_piece_HORS_VOCABULAIRE_est_refusee(self):
        with self.assertRaises(RefusMesure) as e:
            _assembler(pieces=_pieces(ETAT_FLUX_TRESORERIE='…'))
        self.assertEqual(e.exception.motif, MOTIF_PIECE_INCONNUE)
        self.assertIn('est une décision', str(e.exception))

    def test_la_piece_se_retrouve_par_son_nom(self):
        e = _assembler()
        self.assertTrue(e.piece('BILAN_78').presente)
        self.assertFalse(e.piece('DEVELOPPEMENT_130').presente)
        self.assertIn('aucune donnee', e.piece('DEVELOPPEMENT_130').motif)
        with self.assertRaises(KeyError):
            e.piece('INEXISTANTE')


class O2_LesTroisRefus(unittest.TestCase):
    """⚠️⚠️ LA LIGNE DE PARTAGE : une pièce peut manquer si son absence est
    un FAIT DÉCLARABLE ; elle ne le peut pas si son absence rend les autres
    fausses."""

    def test_REFUS_1_une_piece_ni_fournie_ni_declaree_est_un_OUBLI(self):
        """⚠️ On ne peut pas oublier une pièce, on peut seulement la déclarer
        absente. Passée sous silence, elle est indiscernable d'un oubli."""
        manque = {k: v for k, v in _absences().items()
                  if k != 'DEVELOPPEMENT_130'}
        with self.assertRaises(RefusMesure) as e:
            _assembler(absences=manque)
        self.assertEqual(e.exception.motif,
                         MOTIF_PIECE_NI_FOURNIE_NI_DECLAREE)
        self.assertIn('DEVELOPPEMENT_130', str(e.exception))
        self.assertIn("INDISCERNABLE D'UN OUBLI", str(e.exception))
        print("    OK O2 : une piece passee sous silence -> REFUSE")

    def test_REFUS_2_une_piece_INDISPENSABLE_absente(self):
        for nom in INDISPENSABLES:
            p = {k: v for k, v in _pieces().items() if k != nom}
            a = {**_absences(), nom: 'un motif quelconque'}
            with self.assertRaises(RefusMesure, msg=nom) as e:
                _assembler(pieces=p, absences=a)
            self.assertEqual(e.exception.motif,
                             MOTIF_PIECE_INDISPENSABLE_ABSENTE)
        self.assertEqual(len(INDISPENSABLES), 3)
        print(f"    OK O2b : les {len(INDISPENSABLES)} indispensables "
              "refusent leur propre absence, MEME motivee")

    def test_le_refus_2_ECRIT_le_critere_qui_le_fonde(self):
        """⚠️ Un refus qui ne dit pas sa règle se fait contester sur son
        arbitraire."""
        p = {k: v for k, v in _pieces().items() if k != 'BILAN_78'}
        with self.assertRaises(RefusMesure) as e:
            _assembler(pieces=p, absences={**_absences(), 'BILAN_78': 'x'})
        m = str(e.exception)
        self.assertIn('FAIT DÉCLARABLE', m)
        self.assertIn('REND LES AUTRES FAUSSES', m)
        self.assertIn('IMPOSSIBLE', m)

    def test_une_absence_SANS_MOTIF_est_refusee(self):
        with self.assertRaises(RefusMesure) as e:
            _assembler(absences={**_absences(), 'DEVELOPPEMENT_130': '  '})
        self.assertEqual(e.exception.motif, MOTIF_ABSENCE_SANS_MOTIF)

    def test_une_piece_a_la_fois_fournie_ET_declaree_absente_est_refusee(self):
        with self.assertRaises(RefusMesure) as e:
            _assembler(pieces=_pieces(DEVELOPPEMENT_130='un tableau'),
                       absences=_absences())
        self.assertEqual(e.exception.motif, MOTIF_ABSENCE_SANS_MOTIF)
        self.assertIn('ne peuvent pas être vraies toutes les deux',
                      str(e.exception))


class O3_LesArticulationsCessentDEtreFacultatives(unittest.TestCase):
    """⚠️⚠️ LE VRAI SUJET DE CE LOT. §99 b) et §80 ↔ §100 existaient, étaient
    testées, et PERSONNE NE LES APPELAIT. Un contrôle que personne n'exécute
    est un contrôle qui ne contrôle rien."""

    def test_LES_ARTICULATIONS_CESSENT_D_ETRE_FACULTATIVES(self):
        e = _assembler(soldes_du_rapprochement=SOLDES,
                       nature_du_rapprochement=NATURE_EMIS,
                       nature_emise=NATURE_EMIS,
                       deroule_du_passif=DEROULE)
        self.assertEqual({a.verdict for a in e.articulations}, {ETABLIE})
        self.assertIn('boucle sur', e.articulations[0].motif)
        print("    OK O3 : les DEUX articulations tournent DANS "
              "l'assemblage, plus au bon vouloir de l'appelant")

    def test_REFUS_3_une_articulation_qui_ECHOUE_refuse_l_ETAT_ENTIER(self):
        """⚠️ Ce n'est pas une absence, c'est une CONTRADICTION : deux pièces
        se démentent, et aucune note ne rendrait leur publication honnête."""
        faux = (SoldeGroupe('DO', 'DO|AUTRES|2026', 1500.0),
                SoldeGroupe('MRH', 'MRH|AUTRES|2026', -300.0))
        with self.assertRaises(RefusMesure) as e:
            _assembler(soldes_du_rapprochement=faux,
                       nature_du_rapprochement=NATURE_EMIS,
                       nature_emise=NATURE_EMIS, deroule_du_passif=DEROULE)
        self.assertEqual(e.exception.motif, MOTIF_ETAT_CONTREDIT)
        self.assertIn('PAS UNE ABSENCE', str(e.exception))
        self.assertIn('aucune note', str(e.exception))
        # ⚠️ LE REFUS DOIT DIRE LAQUELLE DES DEUX A ÉCHOUÉ. Deux
        # articulations tournent ; un refus qui ne les distingue pas
        # obligerait à deviner laquelle relancer.
        self.assertIn(ARTICULATION_99B, str(e.exception))
        self.assertNotIn(ARTICULATION_80_100, str(e.exception))
        print("    OK O3b : une articulation qui ECHOUE refuse l'etat "
              "ENTIER -- pas une note en bas de page")

    def test_le_80_100_refuse_AUSSI_l_etat_entier(self):
        with self.assertRaises(RefusMesure) as e:
            _assembler(deroule_du_passif={**DEROULE,
                                          'charges_du_deroule': 999.0})
        self.assertEqual(e.exception.motif, MOTIF_ETAT_CONTREDIT)
        self.assertIn(ARTICULATION_80_100, str(e.exception))

    def test_NON_ETABLIE_n_est_PAS_concordante_et_le_motif_le_dit(self):
        """⚠️⚠️ LA CONFUSION LA PLUS COÛTEUSE POSSIBLE : un contrôle qui n'a
        pas tourné n'a rien constaté. Le lire comme un accord serait pire que
        de ne pas l'avoir."""
        e = _assembler()
        self.assertEqual({a.verdict for a in e.articulations}, {NON_ETABLIE})
        self.assertIn("n'a donc RIEN établi", e.articulations[0].motif)
        self.assertIn('« NON ÉTABLIE » N\'EST PAS « CONCORDANTE »', e.motif)

    def test_le_CEDE_ne_boucle_pas_et_c_est_une_CONTRADICTION_declaree(self):
        """⚠️ §98 exige un rapprochement séparé pour le cédé, et §78 c)/d)
        n'existent pas. Le contrôle REFUSE — il ne rend pas un accord."""
        with self.assertRaises(RefusMesure) as e:
            _assembler(soldes_du_rapprochement=SOLDES,
                       nature_du_rapprochement=NATURE_REASSURANCE_DETENUE,
                       nature_emise=NATURE_EMIS)
        self.assertEqual(e.exception.motif, MOTIF_ETAT_CONTREDIT)
        self.assertIn('§78 c) et d)', str(e.exception))

    def test_le_motif_NOMME_ce_qui_manque_encore(self):
        """⚠️ §82 et §78 c)/d) vont ENSEMBLE : les traiter séparément
        laisserait le cédé séparé d'un côté et fondu de l'autre. Et l'état
        des flux de trésorerie est nommé comme EXTÉRIEUR, pas ignoré."""
        m = _assembler().motif
        self.assertIn(CE_QUI_MANQUE_ENCORE, m)
        for attendu in ('AUCUN TABLEAU', '§99 a)', '§78 c) et d)', '§82',
                        'FLUX DE TRÉSORERIE', "état d'entité"):
            self.assertIn(attendu, m, attendu)


class Z_RIEN_N_IMPORTE_etats(unittest.TestCase):
    """⚠️⚠️ LE VERROU DE LA TROISIÈME ZONE. `etats/` peut TOUT importer ;
    RIEN ne peut l'importer. Sans lui, le cycle `socle ↔ mesure` se
    reformerait par le bas — et il existe déjà, mesuré : 2 arcs de
    production dans un sens, 1 dans l'autre."""

    def test_aucun_module_hors_de_etats_n_importe_etats(self):
        racine = pathlib.Path(__file__).resolve().parents[3]
        fautifs = []
        for f in racine.rglob('*.py'):
            if 'ifrs17' + '/etats' in f.as_posix() or '__pycache__' in f.parts:
                continue
            for n in ast.walk(ast.parse(f.read_text(encoding='utf-8'))):
                cible = ((n.module or '') if isinstance(n, ast.ImportFrom)
                         else ' '.join(a.name for a in n.names)
                         if isinstance(n, ast.Import) else '')
                if 'ifrs17.etats' in cible:
                    fautifs.append(f'{f.name} → {cible}')
        self.assertEqual(
            fautifs, [],
            f"{len(fautifs)} module(s) importent `etats/` : {fautifs}. Ce "
            f"paquet ASSEMBLE — il est le seul à tenir un Groupe, un "
            f"Magasin, un Bilan et le PERIMETRE ensemble. L'importer "
            f"ferait remonter cette exception dans un paquet qui l'interdit.")
        print("    OK Oz : aucun module du depot n'importe etats/")

    def test_etats_importe_bien_LES_DEUX_paquets(self):
        """⚠️ Sa raison d'être est de les voir tous les deux. S'il n'en
        voyait qu'un, il n'aurait pas lieu d'exister à part."""
        from normes.ifrs17.etats import assemblage
        arbre = ast.parse(pathlib.Path(assemblage.__file__).read_text(
            encoding='utf-8'))
        modules = {(n.module or '') for n in ast.walk(arbre)
                   if isinstance(n, ast.ImportFrom)}
        self.assertTrue(any('mesure' in m for m in modules), modules)


if __name__ == '__main__':
    unittest.main(verbosity=2)
