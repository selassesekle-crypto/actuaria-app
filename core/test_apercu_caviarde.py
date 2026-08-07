# -*- coding: utf-8 -*-
"""Tests C2 — l'aperçu caviardé, et la preuve qu'aucune valeur ne sort.

⚠️ GATE : `py -m unittest discover -s core -t .` — voir test_frontiere_llm.py.
"""
import os
import re
import unittest

import pandas as pd

from core.apercu_caviarde import (
    BANDE_MILLESIME, ETIQUETTE_MILLESIME, ETIQUETTE_PETIT_RANG, FORME_COMPACTE,
    FORME_DATE_FR, FORME_DATE_ISO, FORME_DECIMAL, FORME_ENTIER, FORME_TEXTE,
    FORME_VIDE, LIGNES_PROFILEES, apercu, forme, profil_colonne)

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Les deux seuls sites qui envoyaient de vraies lignes de contrat.
SITES_MAPPING = ('core/mapping_llm.py',
                 'direction_non_vie/services/nv_triangle_mapping_llm.py')

# ⚠️ SENTINELLES : des valeurs assez distinctives pour qu'aucune collision
# fortuite avec un mot du gabarit ne soit possible.
INVENTAIRE = pd.DataFrame({
    'NUMERO_POLICE': ['P-88213-XQ', 'P-88214-XQ', 'P-88215-XQ'],
    'BRANCHE': ['RC_AUTO_SENTINELLE', 'MRH_SENTINELLE', 'RC_AUTO_SENTINELLE'],
    'DATE_SOUSCRIPTION': ['2026-03-15', '2026-07-01', '2026-11-30'],
    'ECHEANCE': ['31/12/2026', '30/06/2027', '30/11/2027'],
    'PRIME_ANNUELLE': [1240.50, 8317.25, 4471.75],
    'CAPITAL': [3140000, 8250000, 6170000],
})


class T1_AucuneValeurNeSort(unittest.TestCase):
    """T1 — le verrou. C'est la seule chose que ce lot puisse GARANTIR."""

    def test_aucune_valeur_du_fichier_ne_figure_dans_l_apercu(self):
        """⚠️ LE TEST QUI PORTE LE LOT. Chaque valeur du tableau est cherchée
        telle quelle dans l'aperçu : aucune ne doit s'y trouver."""
        texte = apercu(INVENTAIRE)
        fuites = []
        for colonne in INVENTAIRE.columns:
            for valeur in INVENTAIRE[colonne]:
                if str(valeur) in texte:
                    fuites.append(f'{colonne} = {valeur}')
        self.assertEqual(fuites, [], 'valeurs sorties : %s' % ', '.join(fuites))
        print(f'    OK T1 : aucune des {INVENTAIRE.size} valeurs ne figure '
              f'dans l\'aperçu')

    def test_les_noms_de_colonnes_sortent_INTACTS(self):
        """⚠️ C'EST LA MESURE D'IA-0 QUI L'EXIGE : le signal discriminant est
        dans les NOMS. Les caviarder viderait le caviardage de son intérêt."""
        texte = apercu(INVENTAIRE)
        for colonne in INVENTAIRE.columns:
            self.assertIn(colonne, texte, colonne)
        print(f'    OK T1b : les {len(INVENTAIRE.columns)} noms de colonnes '
              f'sortent intacts')

    def test_aucune_ligne_reelle_n_atteint_plus_un_prompt(self):
        """Le pendant du verrou C1, côté charge utile : plus aucun
        `to_csv` ni `head(` dans les deux sites de mapping."""
        fautifs = []
        for rel in SITES_MAPPING:
            with open(os.path.join(RACINE, rel.replace('/', os.sep)),
                      encoding='utf-8') as f:
                source = f.read()
            for motif in (r'\.to_csv\s*\(', r'\.head\s*\('):
                if re.search(motif, source):
                    fautifs.append(f'{rel} → {motif}')
        self.assertEqual(fautifs, [], '; '.join(fautifs))
        print('    OK T1c : plus aucun to_csv ni head() dans les 2 sites')


class T2_LesFormes(unittest.TestCase):
    """T2 — le vocabulaire des formes, exercé valeur par valeur."""

    def test_chaque_forme_est_reconnue(self):
        cas = [('2026-03-15', FORME_DATE_ISO), ('15/03/2026', FORME_DATE_FR),
               ('20260315', FORME_COMPACTE), ('45731', FORME_ENTIER),
               ('-12', FORME_ENTIER), ('1240.50', FORME_DECIMAL),
               ('1240,50', FORME_DECIMAL), ('RC_AUTO', FORME_TEXTE),
               ('', FORME_VIDE), (None, FORME_VIDE), ('  ', FORME_VIDE)]
        for valeur, attendu in cas:
            self.assertEqual(forme(valeur), attendu, repr(valeur))
        print(f'    OK T2 : {len(cas)} formes reconnues')

    def test_une_date_compacte_ne_se_confond_pas_avec_un_entier(self):
        """⚠️ L'ORDRE DES TESTS COMPTE : « 20260315 » est huit chiffres AVANT
        d'être un entier. L'inverse masquerait une colonne de dates."""
        self.assertEqual(forme('20260315'), FORME_COMPACTE)
        self.assertEqual(forme('2026031'), FORME_ENTIER)     # 7 chiffres
        print('    OK T2b : 8 chiffres prime sur entier, 7 chiffres non')


class T3_LaBandeSepareCeQueLeTypeConfond(unittest.TestCase):
    """T3 — mesuré sur le vocabulaire A7 : trois champs entiers."""

    def test_millesime_et_petit_rang_se_distinguent(self):
        """⚠️ SANS LA BANDE, `annee_survenance` ET `annee_developpement`
        SERAIENT LE MÊME PROFIL : « entier ». Ce sont deux champs distincts du
        vocabulaire A7, et les confondre renommerait des colonnes."""
        survenance = pd.Series([2015, 2016, 2017, 2018, 2019])
        developpement = pd.Series([0, 1, 2, 3, 4])
        montants = pd.Series([45000, 120000, 78000, 250000, 33000])
        self.assertIn(ETIQUETTE_MILLESIME, profil_colonne(survenance))
        self.assertIn(ETIQUETTE_PETIT_RANG, profil_colonne(developpement))
        self.assertNotIn(ETIQUETTE_MILLESIME, profil_colonne(montants))
        self.assertNotIn(ETIQUETTE_PETIT_RANG, profil_colonne(montants))
        print('    OK T3 : millésime, petit rang et montant se séparent')

    def test_la_bande_est_une_categorie_pas_un_minimum(self):
        """Deux portefeuilles de millésimes différents rendent LE MÊME profil :
        l'étiquette ne divulgue ni le min ni le max."""
        a = profil_colonne(pd.Series([2015, 2016, 2017]))
        b = profil_colonne(pd.Series([1998, 1999, 2000]))
        self.assertEqual(a, b)
        for interdit in ('2015', '2017', '1998', '2000'):
            self.assertNotIn(interdit, a)
        self.assertEqual(BANDE_MILLESIME, (1900, 2100))
        print(f'    OK T3b : deux millésimes distincts → même profil '
              f'« {a} »')

    def test_la_cardinalite_et_les_manquants_sont_annonces(self):
        s = pd.Series(['RC_AUTO', 'MRH', 'RC_AUTO', None])
        p = profil_colonne(s)
        self.assertIn('2 valeurs distinctes', p)
        self.assertIn('valeurs manquantes', p)
        print(f'    OK T3c : « {p} »')


class T4_LeParametreQuiNeCommandePlusRien(unittest.TestCase):
    """T4 — la propriété qui dit le lot en une phrase."""

    def test_n_lignes_exemple_n_influence_plus_ce_qui_sort(self):
        """⚠️ CE PARAMÈTRE COMMANDAIT LE NOMBRE DE VRAIES LIGNES ENVOYÉES.
        Il n'en part aucune : il ne commande donc plus rien, et c'est
        exactement ce que le lot change."""
        from direction_non_vie.services import nv_triangle_mapping_llm as llm
        rendus = {llm._apercu(INVENTAIRE, n) for n in (1, 5, 50, 5000)}
        self.assertEqual(len(rendus), 1)
        print('    OK T4 : n_lignes_exemple ∈ {1, 5, 50, 5000} → aperçu '
              'identique')

    def test_le_profil_est_borne_et_ne_depend_pas_de_la_taille(self):
        petit = pd.DataFrame({'X': list(range(2100, 2100 + 5))})
        grand = pd.DataFrame({'X': list(range(2100, 2100 + 5)) * 900})
        self.assertGreater(len(grand), LIGNES_PROFILEES)
        self.assertEqual(profil_colonne(petit['X']),
                         profil_colonne(grand['X']))
        print(f'    OK T4b : profil borné à {LIGNES_PROFILEES} lignes lues '
              f'localement, identique sur 5 et 4500 lignes')


class T5_LApercuResteExploitable(unittest.TestCase):
    """T5 — ce que je peux montrer, et ce que je ne peux pas."""

    def test_l_apercu_porte_dimensions_types_et_profils(self):
        texte = apercu(INVENTAIRE)
        for attendu in ('dimensions :', '3 lignes x 6 colonnes',
                        'type pandas', 'CAVIARDÉ', 'valeurs distinctes'):
            self.assertIn(attendu, texte)
        self.assertEqual(len(texte.splitlines()),
                         2 + len(INVENTAIRE.columns) + 1)
        print(f'    OK T5 : {len(texte.splitlines())} lignes d\'aperçu pour '
              f'{len(INVENTAIRE.columns)} colonnes')

    def test_une_colonne_exotique_degrade_sans_faire_tomber(self):
        """Une colonne d'objets non comparables ne doit pas casser l'aperçu :
        elle se déclare indisponible, comme le lecteur d'inventaire le fait."""
        df = pd.DataFrame({'OK': [1, 2], 'EXOTIQUE': [{'a': 1}, {'b': 2}]})
        texte = apercu(df)
        self.assertIn('OK', texte)
        self.assertIn('EXOTIQUE', texte)
        print('    OK T5b : une colonne exotique dégrade l\'aperçu, ne le '
              'fait pas tomber')


if __name__ == '__main__':
    unittest.main(verbosity=2)
