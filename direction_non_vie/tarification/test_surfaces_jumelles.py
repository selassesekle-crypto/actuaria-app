"""LES SURFACES JUMELLES -- cause (b) de l'audit du 06/09/2026.

Un correctif atterrit sur UNE surface et pas sur sa jumelle, et les deux
documents du meme dossier cessent de dire la meme chose. Quatre constats de
l'audit relevent de cette cause, et le depot en porte l'histoire dans ses
propres commentaires : << le correctif V10 B3 n'avait ete applique qu'a
l'export Excel d'A6 >>, << constat C6 : elles manquaient au Word >>.

  SJ-1  toute GRANDEUR publiee au chapitre 5 du rapport d'equipe est rendue
        par les TROIS formats -- et l'inventaire est DERIVE du classeur, pas
        ecrit ici ;
  SJ-2  et elle y est rendue DANS LE MEME FORMAT : un 0.17832145678901234 a
        cote d'un 0.1783 est l'ecart qu'un commissaire releve ;
  SJ-3  une grandeur ABSENTE se declare pareil dans les trois.

⚠️⚠️ POURQUOI L'INVENTAIRE EST DERIVE. Une liste de grandeurs ecrite ici
serait exactement la dette qu'on ferme : elle divergerait le jour ou le
chapitre 5 en gagne une, et le controle certifierait une couverture qu'il
n'aurait plus. On lit donc les LIGNES REELLEMENT PRODUITES par le classeur --
la surface la plus complete des trois -- et on exige que le HTML et le Word
les portent. *Le classeur devient la reference, et il ne peut pas mentir sur
ce qu'il contient : c'est lui qu'on ouvre.*

⚠️ CE QUE CE FICHIER NE COUVRE PAS, ET C'EST DECLARE : le chapitre 5 seul, du
seul rapport d'equipe. Les cinq autres surfaces (rapport modeles HTML/Word,
Excel A1..A6) ont leurs propres chapitres ; les ouvrir ici ferait un controle
qui promet plus qu'il ne porte.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""

from __future__ import annotations

import io
import re
import unittest
import warnings

from direction_non_vie.tarification.services import (
    rapport_equipe_tarif as RE,
)

#: Des valeurs TEMOINS, choisies pour etre introuvables par hasard dans un
#: document : chacune doit se retrouver telle quelle dans les trois formats.
GINI_TEST = 0.31415926535
GINI_WF = 0.17832145678901234
AE = 0.4242424242
SCORE = 0.8123


def _resultats(ae=AE, gini_wf=GINI_WF):
    return {
        'a1': {'success': True, 'statut_rag': 'VERT',
               'qualite': {'score_global': 92.5, 'nb_lignes': 3000,
                           'nb_colonnes': 12, 'taux_completude': 99.1,
                           'nb_doublons': 0, 'taux_doublons': 0.0,
                           'nb_types_aberrants': 0, 'expo_ok_pct': 100.0}},
        'a6': {'success': True, 'statut_rag': 'VERT',
               'modele_production': {'modele': 'GLM_POISSON',
                                     'score_global': SCORE,
                                     'gini_test': GINI_TEST,
                                     'overfit_ratio': 1.08},
               'classement': [{'modele': 'GLM_POISSON', 'gini_test': GINI_TEST,
                               'score_global': SCORE, 'overfit_ratio': 1.08}],
               'backtest': {'disponible': True, 'gini_wf_moyen': gini_wf,
                            'ae_ratio': ae, 'modele_recalibre': 'GLM_POISSON',
                            'modele_recalibre_fidele': True},
               'audit_trail': {'profil_ponderation': 'equilibre',
                               'profil_valide_par': 'Test',
                               'environnement': 'production',
                               'gouvernance_ok': True}},
    }


def _rendus(resultats):
    sortie = RE.generer_rapport_equipe_tarification(
        resultats, branche='non_vie', arrete='2026-06-30', audit_id='SJ',
        formats=['html', 'word', 'excel'])
    return sortie


def _texte_html(octets):
    texte = re.sub(r'<[^>]+>', ' ', octets.decode('utf-8', 'replace'))
    return re.sub(r'\s+', ' ', texte)


def _texte_word(octets):
    from docx import Document
    doc = Document(io.BytesIO(octets))
    morceaux = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for ligne in table.rows:
            morceaux += [c.text for c in ligne.cells]
    return re.sub(r'\s+', ' ', '\n'.join(morceaux))


def _feuille_decision(octets):
    """Les couples (libelle, valeur) du chapitre 5 du classeur."""
    from openpyxl import load_workbook
    classeur = load_workbook(io.BytesIO(octets), data_only=True)
    nom = next((n for n in classeur.sheetnames if 'Décision' in n
                or 'Decision' in n), None)
    if nom is None:
        return []
    couples = []
    for ligne in classeur[nom].iter_rows():
        valeurs = [c.value for c in ligne if c.value not in (None, '')]
        if len(valeurs) >= 2 and isinstance(valeurs[0], str):
            couples.append((valeurs[0].strip(), valeurs[1]))
    return couples


class TestSurfacesJumelles(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        cls.sortie = _rendus(_resultats())
        cls.html = _texte_html(cls.sortie['html_bytes'])
        cls.word = _texte_word(cls.sortie['word_bytes'])
        cls.couples = _feuille_decision(cls.sortie['excel_bytes'])

    def test_SJ1_toute_grandeur_du_chapitre_5_est_rendue_par_les_TROIS(self):
        """⚠️⚠️ INVENTAIRE DERIVE. On prend les lignes NUMERIQUES reellement
        produites par le classeur -- ce sont les grandeurs -- et on exige que
        le HTML et le Word les portent. Une liste ecrite ici aurait diverge au
        premier ajout.
        """
        grandeurs = [(libelle, valeur) for libelle, valeur in self.couples
                     if isinstance(valeur, (int, float))
                     and not isinstance(valeur, bool)]
        self.assertGreaterEqual(
            len(grandeurs), 3,
            f'le chapitre 5 du classeur ne porte que {len(grandeurs)} '
            f'grandeur(s) numerique(s) : le controle mesurerait presque rien. '
            f'Couples lus : {self.couples[:12]}')

        # ⚠️⚠️ PAS UNE SOUS-CHAINE. Mesure du sceau : `'0.4242' in texte` etait
        # satisfait par la phrase d'avertissement qui contient
        # `0.4242424242` -- le controle restait VERT alors que la grandeur
        # avait disparu de sa ligne. *Le releve au texte SUR-COMPTE, et c'est
        # ma propre sentinelle qui en portait le defaut.* On exige donc que le
        # nombre ne soit pas suivi d'un autre chiffre.
        manquantes = []
        for libelle, valeur in grandeurs:
            motif = re.compile(rf'(?<![\d.]){re.escape(f"{valeur}")}(?![\d])')
            for nom, texte in (('HTML', self.html), ('WORD', self.word)):
                if not motif.search(texte):
                    manquantes.append((libelle, valeur, nom))
        self.assertEqual(
            manquantes, [],
            'des grandeurs du chapitre 5 manquent a une surface jumelle -- '
            f'(libelle, valeur, format absent) : {manquantes}')
        print(f'    SJ-1 {len(grandeurs)} grandeurs derivees du classeur, '
              f'rendues par les 3 formats')

    def test_SJ2_le_Gini_WF_est_rendu_DANS_LE_MEME_FORMAT_partout(self):
        """⚠️⚠️ `EX-1` : le Gini WF etait interpole BRUT dans le HTML et le
        Word -- 0.17832145678901234 a cote de 0.1783 dans le classeur du meme
        dossier. Cosmetique, et c'est le genre d'ecart qu'un commissaire
        releve."""
        for nom, texte in (('HTML', self.html), ('WORD', self.word)):
            with self.subTest(surface=nom):
                self.assertNotIn(
                    str(GINI_WF), texte,
                    f'{nom} rend le Gini WF BRUT : il ne passe pas par la '
                    f'source unique de mise en forme')
                self.assertIn('0.1783', texte,
                              f'{nom} ne rend plus le Gini WF du tout')
        print('    SJ-2 Gini WF : 4 decimales dans les trois formats')

    def test_SJ3_une_grandeur_ABSENTE_se_declare_pareil_dans_les_trois(self):
        """⚠️ Controle NEGATIF de la meme propriete : si les trois divergeaient
        sur l'ABSENCE, SJ-1 resterait vert -- il ne compare que des valeurs
        presentes."""
        sortie = _rendus(_resultats(ae=None, gini_wf=None))
        textes = {'HTML': _texte_html(sortie['html_bytes']),
                  'WORD': _texte_word(sortie['word_bytes'])}
        couples = _feuille_decision(sortie['excel_bytes'])
        excel = ' '.join(f'{lib} {val}' for lib, val in couples)
        for nom, texte in list(textes.items()) + [('EXCEL', excel)]:
            with self.subTest(surface=nom):
                self.assertIn(
                    'non calcule', texte,
                    f"{nom} ne declare pas l'A/E absent comme les autres")
        print('    SJ-3 absence : declaree a l identique dans les trois')


if __name__ == '__main__':
    unittest.main(verbosity=2)
