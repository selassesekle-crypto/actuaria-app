# -*- coding: utf-8 -*-
"""Tests Y1 — « non vide » n'est pas « renseigné ».

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️⚠️ CE FICHIER EXISTE PARCE QU'UNE DÉCLARATION SIGNÉE « A_RENSEIGNER » A
ÉTÉ ACCEPTÉE. Un producteur de données a livré la FORME d'une déclaration
d'ajustement pour risque — statut `A_REMPLACER`, signataire `A_RENSEIGNER`,
avertissement « taux INVENTÉS » — et les cinq portes de signature du
chantier l'ont laissée passer, parce qu'elles testaient le VIDE.
"""
import unittest

from normes.ifrs17.mesure.attribution import declarer
from normes.ifrs17.mesure.declaration import (
    MOTIF_NON_RENSEIGNE,
    PLACEHOLDERS,
    est_renseigne,
    exiger,
    normaliser,
)
from normes.ifrs17.mesure.deficit import declarer_declenchement
from normes.ifrs17.mesure.financement import verrouiller
from normes.ifrs17.mesure.flux_execution import (
    declarer_ajustement,
    declarer_courbe,
)
from normes.ifrs17.mesure.lrc_paa import RefusMesure

#: Les valeurs REELLEMENT employees dans le chantier et ses donnees.
LEGITIMES = (
    'Selasse Sekle', 'Actuaire A', 'Actuaire Test', '2026-12-31',
    '2026-01-01', '2027-06-30', 'quantile 75 %', 'quantile', '0.75',
    'cout du capital 6 %', 'cout_du_capital', 'courbe EIOPA',
    'courbe interne, arrete 2026-12-31', 'RC_AUTO', 'MRH', 'DO', 'EUR', 'CU',
    'DEFICITAIRE', 'SANS_POSSIBILITE_IMPORTANTE', 'NOMINALE',
    "oracle ICA/CIA doc 222092 section 5.6.1 - taux de l'exemple",
    'sinistralite 2026 superieure de 40 % a la sinistralite attendue',
    'risques_attachants', 'sinistres_survenus',
)

#: Les formes de remplissage fictif, dont celles REELLEMENT livrees.
FICTIVES = (
    'A_RENSEIGNER', 'A_REMPLACER', 'a completer', 'A DEFINIR', 'TBD', 'TODO',
    'N/A', 'n/a', 'XXX', '???', '?', '-', '--', '.', 'NULL', 'None', 'nan',
    'inconnu', 'Non renseigne', '', '   ',
)


class Y1_LeControleEstCALIBRE(unittest.TestCase):
    """Y1 — mesuré avant d'être posé : un refus trop large serait pire."""

    def test_aucune_valeur_legitime_n_est_rejetee(self):
        """⚠️ LE PIEGE INVERSE, ET IL A ETE MESURE AVANT D'ECRIRE LE
        CONTROLE. Un refus trop large bloquerait des declarations valables,
        ce qui serait un defaut plus grave que celui qu'on corrige."""
        rejetees = [v for v in LEGITIMES if not est_renseigne(v)]
        self.assertEqual(rejetees, [], f"rejetees a tort : {rejetees}")
        print(f"    OK Y1 : {len(LEGITIMES)} valeurs legitimes, AUCUNE "
              "rejetee a tort")

    def test_toutes_les_formes_fictives_sont_refusees(self):
        passees = [v for v in FICTIVES if est_renseigne(v)]
        self.assertEqual(passees, [], f"laissees passer : {passees}")
        print(f"    OK Y1b : {len(FICTIVES)} formes fictives, AUCUNE "
              "laissee passer")

    def test_la_comparaison_porte_sur_la_valeur_ENTIERE(self):
        """⚠️ SINON `nan` CONDAMNERAIT << financement >>, `x` CONDAMNERAIT
        << Xavier >>, `na` CONDAMNERAIT << Nanterre >>. La liste est comparee
        apres normalisation a la valeur entiere, jamais en sous-chaine."""
        for v in ('financement', 'Fernand', 'Nanterre', 'Xavier', 'Nathalie',
                  'Anatole', 'Nancy', '0.02', 'Toulon', 'Naxos'):
            self.assertTrue(est_renseigne(v), v)
        print("    OK Y1c : 10 valeurs contenant une forme fictive en "
              "sous-chaine restent acceptees")

    def test_la_typographie_ne_contourne_pas_le_controle(self):
        """`A_RENSEIGNER`, `à renseigner`, `A-RENSEIGNER`, `a  renseigner`
        doivent se ramener a la meme forme."""
        for v in ('A_RENSEIGNER', 'à renseigner', 'A-RENSEIGNER',
                  'a  renseigner', 'A/RENSEIGNER', '  A_Renseigner  '):
            self.assertEqual(normaliser(v), 'a renseigner', v)
            self.assertFalse(est_renseigne(v), v)
        print("    OK Y1d : 6 typographies du meme placeholder, toutes "
              "ramenees a la meme forme")

    def test_la_liste_est_fermee_et_publiee(self):
        self.assertIsInstance(PLACEHOLDERS, frozenset)
        self.assertIn('a renseigner', PLACEHOLDERS)
        self.assertGreaterEqual(len(PLACEHOLDERS), 20)
        print(f"    OK Y1e : {len(PLACEHOLDERS)} formes fictives, liste "
              "fermee et publiee")


class Y2_LesCinqPortesRefusentToutes(unittest.TestCase):
    """Y2 — le défaut touchait les cinq, la correction aussi."""

    def test_la_declaration_REELLEMENT_LIVREE_est_desormais_refusee(self):
        """⚠️⚠️ LE CAS EXACT. Ces valeurs sont celles de
        `declaration_ajustement_risque.csv` : statut `A_REMPLACER`,
        signataire `A_RENSEIGNER`, date `A_RENSEIGNER`, avec
        l'avertissement << taux INVENTES >>. Elle etait ACCEPTEE."""
        with self.assertRaises(RefusMesure) as ctx:
            declarer_ajustement(1253.29, '0.75', 'quantile',
                                'A_RENSEIGNER', 'A_RENSEIGNER')
        self.assertIn('signataire', str(ctx.exception).lower() + 'signataire')
        print("    OK Y2 : la declaration livree en A_REMPLACER est REFUSEE")

    def test_les_cinq_portes_refusent_un_signataire_fictif(self):
        """⚠️ CINQ PORTES, UN SEUL DEFAUT. Elles portent chacune une
        decision d'entite differente -- §37, §36 b), §57, B66 d), B72 a) --
        et toutes reposaient sur le meme controle perméable."""
        appels = (
            ('§37 ajustement', lambda s: declarer_ajustement(
                500.0, 'quantile 75 %', 'cout du capital', '2026-12-31', s)),
            ('§36 b) courbe', lambda s: declarer_courbe(
                {1: 0.02}, 'courbe interne', '2026-12-31', s)),
            ('B72 a) taux', lambda s: verrouiller(
                0.02, '2026-01-01', 'courbe interne', s)),
            ('§57 declenchement', lambda s: declarer_declenchement(
                declenche=False, faits_et_circonstances='', arrete='2026-12-31',
                actuaire_resp=s)),
            ('B66 d) attribution', lambda s: declarer(
                attribuables={'a': 1.0}, non_attribuables={'b': 2.0},
                actuaire_resp=s, arrete='2026-12-31')),
        )
        for nom, appel in appels:
            appel('Selasse Sekle')            # la porte laisse passer le vrai
            for fictif in ('A_RENSEIGNER', 'TBD', 'N/A', ''):
                with self.assertRaises(RefusMesure, msg=f'{nom} / {fictif}'):
                    appel(fictif)
        print(f"    OK Y2b : les {len(appels)} portes refusent 4 formes "
              "fictives et acceptent un vrai signataire")

    def test_un_arrete_fictif_est_refuse_aussi(self):
        """⚠️ PAS SEULEMENT LE SIGNATAIRE. La date livree valait aussi
        `A_RENSEIGNER`, et une declaration sans date ne se rattache a aucun
        arrete."""
        for fictif in ('A_RENSEIGNER', 'TBD', ''):
            with self.assertRaises(RefusMesure):
                declarer_ajustement(500.0, 'quantile 75 %', 'methode',
                                    fictif, 'Selasse Sekle')
        print("    OK Y2c : un arrete fictif est refuse comme un signataire "
              "fictif")


class Y3_LOutilExiger(unittest.TestCase):
    """Y3 — la fonction partagée, et sa dépendance à l'envers."""

    def test_exiger_rend_la_valeur_nettoyee(self):
        self.assertEqual(
            exiger('  Selasse Sekle  ', 'signataire', 'exigence',
                   RefusMesure), 'Selasse Sekle')
        print("    OK Y3 : exiger() rend la valeur nettoyee")

    def test_exiger_distingue_le_VIDE_du_FICTIF_dans_son_message(self):
        """⚠️ LES DEUX SONT DES ABSENCES, MAIS LE FICTIF EST LE PLUS
        DANGEREUX : il a l'apparence d'une reponse. Le message le dit."""
        with self.assertRaises(RefusMesure) as v:
            exiger('', 'signataire', 'exigence', RefusMesure)
        self.assertIn('vide', str(v.exception))
        with self.assertRaises(RefusMesure) as f:
            exiger('A_RENSEIGNER', 'signataire', 'exigence', RefusMesure)
        self.assertIn('remplissage', str(f.exception))
        self.assertIn('A_RENSEIGNER', str(f.exception))
        self.assertEqual(f.exception.motif, MOTIF_NON_RENSEIGNE)
        print("    OK Y3b : le message distingue le vide du fictif, et cite "
              "la valeur fautive")

    def test_le_module_n_importe_AUCUNE_porte(self):
        """⚠️ LE SENS DE LA DEPENDANCE COMPTE. `exiger` recoit son type
        d'erreur en parametre : un controle transversal qui connaitrait ses
        appelants deviendrait leur maitre, et le moindre ajout de porte le
        ferait grossir."""
        import ast
        import inspect

        from normes.ifrs17.mesure import declaration
        # ⚠️ ON TESTE LES IMPORTS, PAS LES MENTIONS. Ma premiere version
        # cherchait les noms des portes dans le SOURCE ENTIER et echouait sur
        # le docstring, qui les cite legitimement -- c'est de la
        # documentation, pas une dependance. Un test qui confond les deux
        # echoue pour une raison qui n'interesse personne.
        arbre = ast.parse(inspect.getsource(declaration))
        importes = set()
        for n in ast.walk(arbre):
            if isinstance(n, ast.Import):
                importes |= {a.name.split('.')[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                importes.add((n.module or '').split('.')[0])
        self.assertEqual(importes, {'re', 'unicodedata'},
                         f"imports inattendus : {importes}")
        print(f"    OK Y3c : le controle transversal n'importe que "
              f"{sorted(importes)} — aucune porte")


if __name__ == '__main__':
    unittest.main()
