"""
=============================================================================
 A7 Ibrahim — la signature actuarielle : le document signe la portait pas
=============================================================================

 ⚠️ MESURÉ SUR LE CODE : `export_word` DÉCLARAIT `actuaire_nom`,
 `actuaire_numero_ia` et `audit_id` dans sa signature et n'en lisait AUCUN —
 0 occurrence du mot « actuaire » sur ses 375 lignes. L'HTML, lui, imprimait
 la signature ET l'identifiant d'audit. Des deux formats, celui qui VOYAGE et
 qu'on SIGNE était le seul à ne rien porter.

 ⚠️ ET UN SECOND DÉFAUT, PLUS LARGE : `run()` ne connaissait pas l'actuaire
 du tout — 0 occurrence de `actuaire_nom` dans l'agent. Un rapport produit
 par la CHAÎNE ne pouvait donc porter de signature dans AUCUN des deux
 formats ; seul un appel direct depuis l'application en posait une, et
 seulement en HTML.

 ⚠️ DEUX ÉTATS, PAS TROIS. Le rapport de tarification en porte trois, le
 troisième dérivant du paramètre `environnement` d'A6. A7 n'a aucune notion
 d'environnement : le transposer serait un état qu'aucune donnée ne peut
 produire.

 Gate : `py -m unittest discover -s direction_non_vie -t .`
"""
import io
import unittest
import zipfile

from .n5_rapport import export_html, export_word, trace_relecture

N2 = {'lob_label': 'auto', 'methode_recommandee': 'Chain Ladder'}
N4 = {'statut': 'VERT', 'methode_facteurs': 'volume'}
AUDIT = 'A7_20260809_TEST'


def _texte_docx(octets):
    """Le XML du corps du .docx — un Word ne se lit pas comme du texte."""
    with zipfile.ZipFile(io.BytesIO(octets)) as z:
        return z.read('word/document.xml').decode('utf-8', 'replace')


def _les_deux_formats(nom, ia):
    html = export_html({}, N2, {}, N4, ref_client='CLIENT',
                       arrete='31/12/2025', audit_id=AUDIT,
                       actuaire_nom=nom, actuaire_numero_ia=ia)
    word = _texte_docx(export_word({}, N2, {}, N4, ref_client='CLIENT',
                                   arrete='31/12/2025', audit_id=AUDIT,
                                   actuaire_nom=nom, actuaire_numero_ia=ia))
    return (('HTML', html), ('WORD', word))


class S1_LesDeuxEtats(unittest.TestCase):
    """Ce que `trace_relecture` répond, et ce qu'elle refuse de fabriquer."""

    def test_un_nom_donne_l_etat_valide(self):
        t = trace_relecture('Selasse Sekle', '12345')
        self.assertFalse(t.alerte)
        self.assertIn('Relu et validé par Selasse Sekle', t.texte)
        self.assertIn('12345', t.texte)
        print('    OK S1 : un nom et un numéro donnent l\'état validé')

    def test_le_numero_est_FACULTATIF_le_nom_non(self):
        self.assertFalse(trace_relecture('Selasse Sekle').alerte)
        self.assertTrue(trace_relecture('', '12345').alerte)
        print('    OK S1-b : le nom décide, le numéro complète')

    def test_l_absence_est_ACTIVE_et_alerte(self):
        """⚠️ LE POINT DU LOT. A7 ne distinguait que « signé » et « rien » :
        sans nom, le pied ne disait RIEN, et le lecteur ne pouvait pas
        séparer « relu par personne » de « le champ n'a pas été transmis »."""
        for vide in ('', '   ', None):
            with self.subTest(valeur=vide):
                t = trace_relecture(vide)
                self.assertTrue(t.alerte)
                self.assertIn('non enregistrée', t.texte)
        print('    OK S1-c : l\'absence se DIT, elle ne se devine pas')

    def test_l_alerte_SE_VOIT_dans_les_deux_formats(self):
        """⚠️ DÉFAUT DE MA PROPRE PREMIÈRE VERSION : le Word colorait la
        mention en ambre, l'HTML la rendait au gris du pied. L'état négatif
        aurait été ACTIF dans un format et discret dans l'autre — la
        divergence que ce lot ferme."""
        html_alerte = export_html({}, N2, {}, N4, ref_client='C',
                                  arrete='31/12/2025', audit_id=AUDIT)
        html_signe = export_html({}, N2, {}, N4, ref_client='C',
                                 arrete='31/12/2025', audit_id=AUDIT,
                                 actuaire_nom='Selasse Sekle')
        # ⚠️ L'ANCRE EST LE DIV DU PIED, PAS LA CLASSE : « pied-meta » apparaît
        # d'abord dans la feuille de style, et le test passait à côté.
        bloc_a = html_alerte[html_alerte.index('<div class="pied-meta">'):][:500]
        bloc_s = html_signe[html_signe.index('<div class="pied-meta">'):][:500]
        self.assertIn('#E67E22', bloc_a, 'l\'HTML ne marque pas l\'alerte')
        self.assertNotIn('#E67E22', bloc_s, 'l\'HTML alerte alors qu\'il est '
                                            'signé')
        print('    OK S1-e : l\'HTML marque l\'alerte, comme le Word')

    def test_aucune_date_n_est_fabriquee(self):
        """⚠️ Une date posée au rendu dirait quand le document a été PRODUIT,
        pas quand il a été RELU — et le dépôt n'enregistre pas la seconde."""
        t = trace_relecture('Selasse Sekle', '12345')
        self.assertNotIn('/20', t.texte)
        self.assertNotIn(', le ', t.texte)
        print('    OK S1-d : aucune date inventée dans la mention')


class S2_LesDeuxFormatsPortentLaMemeChose(unittest.TestCase):
    """⚠️ LE WORD ÉTAIT LE SEUL DES DEUX À NE RIEN PORTER."""

    def test_signe_les_deux_formats_nomment_l_actuaire(self):
        for nom_fmt, texte in _les_deux_formats('Selasse Sekle', '12345'):
            self.assertIn('Selasse Sekle', texte, nom_fmt)
            self.assertIn('12345', texte, nom_fmt)
            self.assertNotIn('non enregistr', texte, nom_fmt)
        print('    OK S2 : signé, les DEUX formats nomment l\'actuaire')

    def test_non_signe_les_deux_formats_DISENT_l_absence(self):
        for nom_fmt, texte in _les_deux_formats('', ''):
            self.assertIn('non enregistr', texte, nom_fmt)
            self.assertNotIn('Selasse Sekle', texte, nom_fmt)
        print('    OK S2-b : non signé, les DEUX formats disent l\'absence')

    def test_l_AUDIT_ID_est_dans_les_deux_formats(self):
        """⚠️ `audit_id` ÉTAIT LE TROISIÈME PARAMÈTRE MORT d'`export_word`, et
        le plus grave : l'identifiant de traçabilité manquait au document qui
        voyage, alors que l'HTML l'imprimait."""
        for nom_fmt, texte in _les_deux_formats('Selasse Sekle', '12345'):
            self.assertIn(AUDIT, texte, nom_fmt)
        print('    OK S2-c : l\'Audit ID est dans les deux formats')


class S3_LaChaineTransmetLActuaire(unittest.TestCase):
    """⚠️ SANS CE BRANCHEMENT, LES DEUX ÉTATS SERAIENT UN TAMPON PERMANENT :
    100 % des rapports de la chaîne porteraient « non enregistrée », et un
    signal qui se déclenche toujours a cessé d'être un signal."""

    def test_run_accepte_l_actuaire_et_le_transmet_aux_DEUX_exports(self):
        import inspect

        from .agent import AgentA7Provisionnement
        parametres = inspect.signature(AgentA7Provisionnement.run).parameters
        for p in ('actuaire_nom', 'actuaire_numero_ia'):
            self.assertIn(p, parametres, f'run() ignore {p}')
        src = inspect.getsource(AgentA7Provisionnement.run)
        self.assertGreaterEqual(
            src.count('actuaire_nom=actuaire_nom'), 2,
            'l\'actuaire n\'atteint pas les DEUX exports')
        print('    OK S3 : run() accepte l\'actuaire et le passe aux deux '
              'exports')

    def test_les_parametres_declares_sont_LUS(self):
        """⚠️ LE MOTIF QUE CE CHANTIER A FERMÉ CINQ FOIS : un paramètre
        déclaré et jamais lu. On relit le corps d'`export_word`."""
        import ast
        import inspect

        from . import n5_rapport
        src = inspect.getsource(n5_rapport)
        fonction = next(
            n for n in ast.parse(src).body
            if isinstance(n, ast.FunctionDef) and n.name == 'export_word')
        lus = {n.id for n in ast.walk(fonction)
               if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        for p in ('actuaire_nom', 'actuaire_numero_ia', 'audit_id'):
            self.assertIn(p, lus, f'{p} est encore déclaré et jamais lu')
        print('    OK S3-b : les trois paramètres morts d\'export_word sont '
              'lus')


if __name__ == '__main__':
    unittest.main(verbosity=2)
