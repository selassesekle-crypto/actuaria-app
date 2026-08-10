# -*- coding: utf-8 -*-
"""C5a — le constat technique porté par les registres art. 30.

⚠️ CE QUE CES TESTS VERROUILLENT VRAIMENT. Pas la forme du dictionnaire : la
VÉRITÉ de ce qu'il affirme. Le constat dit « la forme des valeurs sort, jamais
les valeurs » ; deux tests relisent les deux sites de correspondance pour
vérifier que le caviardage y est toujours branché. Débrancher C2 demain ferait
donc échouer C5 — c'est le seul montage qui empêche un registre de devenir
faux en silence.
"""
import ast
import os
import unittest

from core import frontiere_llm, traitement_ia

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Les deux sites qui reçoivent un fichier client — relevés en C1, caviardés
#: en C2. ⚠️ Le chemin du second n'est PAS celui que j'avais en tête : il vit
#: dans `direction_non_vie/services/`, pas sous `a7_provisionnement/`.
SITES_FICHIER_CLIENT = (
    'core/mapping_llm.py',
    'direction_non_vie/services/nv_triangle_mapping_llm.py',
)


def _source(chemin_relatif):
    with open(os.path.join(_RACINE, *chemin_relatif.split('/')),
              encoding='utf-8') as f:
        return f.read()


class T5A_ConstatAssistanceIA(unittest.TestCase):
    """Le constat rend ce que le dépôt fait, mesuré à sa source."""

    def test_compte_les_sites_depuis_la_frontiere(self):
        """Le nombre de sites vient de la frontière, pas d'une recopie."""
        constat = traitement_ia.constat_assistance_ia()
        self.assertEqual(constat['nb_sites_appelants'],
                         len(frontiere_llm.chemins_appelants()))
        self.assertGreater(constat['nb_sites_appelants'], 0)

    def test_nomme_le_fournisseur_et_les_modeles(self):
        """Ce que les deux registres n'avaient jamais nommé."""
        constat = traitement_ia.constat_assistance_ia()
        self.assertEqual(constat['fournisseur'], frontiere_llm.FOURNISSEUR)
        self.assertEqual(constat['modeles_appeles'],
                         list(frontiere_llm.MODELES_CONNUS))

    def test_porte_la_frontiere_du_droit(self):
        """⚠️ Sans cette phrase, le bloc se lirait comme une qualification."""
        constat = traitement_ia.constat_assistance_ia()
        self.assertIn('DPO', constat['qualification_juridique'])
        self.assertIn('non une qualification',
                      constat['qualification_juridique'])

    def test_aucun_booleen_ne_tranche_le_caractere_personnel(self):
        """⚠️ J'en avais écrit un. Un booléen aplatit la seule nuance qui
        compte : trois canaux clos par construction, un quatrième qui dépend
        de ce que l'utilisateur saisit."""
        constat = traitement_ia.constat_assistance_ia()
        for cle, valeur in constat.items():
            self.assertNotIsInstance(
                valeur, bool,
                f"« {cle} » tranche par un booléen ce que seules les "
                f"catégories et les réserves peuvent dire exactement")

    def test_les_deux_reserves_sont_nommees(self):
        """Les taire rendrait le reste suspect."""
        reserves = ' '.join(traitement_ia.constat_assistance_ia()['reserves'])
        self.assertIn('En-tête décalé', reserves)
        self.assertIn('conversationnel', reserves)


class T5A_VeriteDuConstat(unittest.TestCase):
    """⚠️ LE VERROU QUI COMPTE : le constat est-il encore VRAI ?"""

    def test_les_deux_sites_fichier_client_caviardent_toujours(self):
        """Le constat affirme « la forme, jamais les valeurs ». Si un site
        cessait d'appeler `apercu_caviarde`, l'affirmation deviendrait fausse
        sans que rien ne le signale. Ce test est ce signal."""
        for chemin in SITES_FICHIER_CLIENT:
            src = _source(chemin)
            self.assertIn('apercu_caviarde', src,
                          f'{chemin} n\'importe plus le caviardage : le '
                          f'constat C5 affirme une propriété qu\'il a perdue')

    def test_aucun_site_fichier_client_n_envoie_de_lignes_brutes(self):
        """`df.to_csv()` / `to_string()` / `to_markdown()` rendraient les
        valeurs elles-mêmes. Relevé par AST, sur les appels d'attribut."""
        interdits = {'to_csv', 'to_string', 'to_markdown'}
        for chemin in SITES_FICHIER_CLIENT:
            arbre = ast.parse(_source(chemin))
            trouves = sorted({
                n.func.attr for n in ast.walk(arbre)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr in interdits})
            self.assertEqual(trouves, [], f'{chemin} rend des valeurs brutes')


if __name__ == '__main__':
    unittest.main()
