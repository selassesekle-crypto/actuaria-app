# -*- coding: utf-8 -*-
"""Tests C3 — aucun contexte de narration ne transporte l'identité du client.

⚠️ CE QUI IDENTIFIE N'EST PAS LE CHIFFRE, C'EST LE NOM. « BE = 18 680 856 € »
ne désigne personne ; le même chiffre accompagné du nom de l'organisme désigne
un assureur et son résultat non publié. Le nom reste PARTOUT dans le livrable
(titre, page de garde, tables, pied de page) — il ne sort plus vers l'API.

⚠️ GATE : `py -m unittest discover -s core -t .` — voir test_frontiere_llm.py.
"""
import ast
import os
import re
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IGNORES = ('.venv', 'venv', 'site-packages', '__pycache__', '.git')

# Le vocabulaire qui IDENTIFIE. Relevé sur le code, pas deviné : `ref_client`
# vaut littéralement `client_nom` (ep5_reporting/agent.py), `entite` alimentait
# le `<title>` du rapport autant que le contexte API.
IDENTIFIANTS = re.compile(
    r'entite|entité|ref_client|client_nom|nom_client|societe|société'
    r'|raison_sociale|siren|siret|denomination|dénomination'
    r'|numero_police|num_police|matricule', re.I)

# ⚠️ CE QUI N'IDENTIFIE PAS, ET QUI RESTE — tranché champ par champ :
#   · `arrete` / `date_arrete` : une DATE seule ne désigne personne, et
#     plusieurs prompts en ont besoin (calendrier ACPR, évolution N vs N-1) ;
#   · `lob_label` / `branche`  : une branche (RC_AUTO, MRH) est une catégorie
#     universelle, pas une identité ;
#   · `contrat` ('individuel'|'collectif') et `garantie_niveau`
#     ('eco'|'confort'|'premium'|'luxe') : des types de produit.
CONSERVES = ('arrete', 'date_arrete', 'lob_label', 'branche', 'contrat',
             'garantie_niveau')

# Le relevé : 9 constructeurs de contexte, dont 5 portaient un nom.
NB_CONSTRUCTEURS = 9
NB_QUI_PORTAIENT_UN_NOM = 5


def _fichiers_python():
    for base, dossiers, fichiers in os.walk(RACINE):
        dossiers[:] = [d for d in dossiers if d not in IGNORES]
        for nom in fichiers:
            if nom.endswith('.py'):
                chemin = os.path.join(base, nom)
                yield os.path.relpath(chemin, RACINE).replace('\\', '/'), chemin


def _constructeurs_de_contexte():
    """Toutes les fonctions `_construire_contexte*` du dépôt, avec leur AST.

    ⚠️ RELEVÉ, PAS LISTE : on part du code. Un dixième constructeur ajouté
    demain est trouvé ici, et le compte ci-dessous le signale.
    """
    trouves = []
    for rel, chemin in _fichiers_python():
        with open(chemin, encoding='utf-8') as f:
            source = f.read()
        if '_construire_contexte' not in source:
            continue
        try:
            arbre = ast.parse(source)
        except SyntaxError:                      # pragma: no cover
            continue
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.FunctionDef)
                    and noeud.name.startswith('_construire_contexte')):
                trouves.append((rel, noeud))
    return trouves


def _noms_interpoles(fonction):
    """Les identifiants Python effectivement interpolés dans les f-strings."""
    noms = set()
    for noeud in ast.walk(fonction):
        if isinstance(noeud, ast.JoinedStr):
            for morceau in noeud.values:
                if isinstance(morceau, ast.FormattedValue):
                    for sous in ast.walk(morceau):
                        if isinstance(sous, ast.Name):
                            noms.add(sous.id)
                        elif isinstance(sous, ast.Constant) and isinstance(
                                sous.value, str):
                            noms.add(sous.value)
    return noms


class T1_AucuneIdentiteNeSort(unittest.TestCase):
    """T1 — le verrou. Sans lui, `entite` revient au premier en-tête ajouté."""

    def test_aucun_constructeur_ne_prend_un_identifiant_en_parametre(self):
        fautifs = []
        for rel, fonction in _constructeurs_de_contexte():
            for arg in fonction.args.args:
                if IDENTIFIANTS.search(arg.arg):
                    fautifs.append(f'{rel}::{fonction.name}({arg.arg})')
        self.assertEqual(fautifs, [], 'identité en paramètre : %s'
                         % ', '.join(fautifs))
        print('    OK T1 : aucun constructeur de contexte ne reçoit '
              'd\'identifiant')

    def test_aucun_identifiant_n_est_interpole_dans_un_contexte(self):
        """⚠️ LE PARAMÈTRE PEUT DISPARAÎTRE ET LA VALEUR RESTER — par un
        `.get('entite')` ou une variable locale. On regarde ce qui est
        RÉELLEMENT interpolé, pas seulement la signature."""
        fautifs = []
        for rel, fonction in _constructeurs_de_contexte():
            for nom in _noms_interpoles(fonction):
                if IDENTIFIANTS.search(nom):
                    fautifs.append(f'{rel}::{fonction.name} → {nom}')
        self.assertEqual(fautifs, [], 'identité interpolée : %s'
                         % ', '.join(fautifs))
        print('    OK T1b : aucune identité interpolée dans un contexte')

    def test_le_releve_compte_neuf_constructeurs(self):
        """Un dixième constructeur fait tomber ce test : c'est voulu — il doit
        être instruit, pas ajouté en silence."""
        trouves = _constructeurs_de_contexte()
        self.assertEqual(len(trouves), NB_CONSTRUCTEURS,
                         'constructeurs trouvés : %s'
                         % ', '.join(f'{r}::{f.name}' for r, f in trouves))
        print(f'    OK T1c : {NB_CONSTRUCTEURS} constructeurs de contexte, '
              f'{NB_QUI_PORTAIENT_UN_NOM} portaient un nom avant C3')


class T2_CeQuiResteEtPourquoi(unittest.TestCase):
    """T2 — retirer aveuglément aurait coûté ce qui ne coûtait rien."""

    def test_la_date_d_arrete_reste_dans_les_neuf_contextes(self):
        """⚠️ UNE DATE SEULE N'IDENTIFIE PERSONNE, et plusieurs prompts en ont
        besoin : calendrier de soumission ACPR, évolution N vs N-1."""
        sans_date = []
        for rel, fonction in _constructeurs_de_contexte():
            noms = _noms_interpoles(fonction)
            if not any(c in noms for c in ('arrete', 'date_arrete')):
                sans_date.append(f'{rel}::{fonction.name}')
        self.assertEqual(sans_date, [], 'contexte sans date : %s'
                         % ', '.join(sans_date))
        print('    OK T2 : la date d\'arrêté reste dans les 9 contextes')

    def test_la_branche_reste_la_ou_elle_etait(self):
        """Une branche (RC_AUTO, MRH) est une catégorie universelle."""
        avec_branche = [
            rel for rel, f in _constructeurs_de_contexte()
            if {'lob_label', 'branche'} & _noms_interpoles(f)]
        self.assertEqual(len(avec_branche), 2, avec_branche)
        print('    OK T2b : les 2 contextes Non-Vie gardent leur branche')

    def test_le_vocabulaire_conserve_n_est_pas_un_identifiant(self):
        """Verrou croisé : aucun champ de la liste des conservés ne doit
        tomber sous le motif des identifiants — sinon la règle se contredit."""
        for champ in CONSERVES:
            self.assertIsNone(IDENTIFIANTS.search(champ), champ)
        print('    OK T2c : les %d champs conservés sont hors du motif '
              'd\'identité' % len(CONSERVES))


class T3_LeLivrableNEstPasTouche(unittest.TestCase):
    """T3 — le nom sort de l'API, PAS du rapport."""

    def test_le_nom_reste_dans_les_cinq_livrables(self):
        """⚠️ C'EST LA MESURE QUI JUSTIFIE LE LOT : le nom apparaît de 6 à 23
        fois par fichier — titre, page de garde, tables, pied de page. Seul
        l'appel API cesse de le porter."""
        attendus = {
            'direction_vie_epre/services/rapport_vie.py': 'ref_client',
            'direction_vie_epre/services/rapport_rvie2.py': 'ref_client',
            'direction_vie_epre/services/rapport_epre.py': 'ref_client',
            'direction_sante_prevoyance/sante/rapport_sante/agent.py': 'entite',
            'direction_sante_prevoyance/prevoyance/rapport_prevoyance/agent.py':
                'entite',
        }
        for rel, champ in attendus.items():
            with open(os.path.join(RACINE, rel.replace('/', os.sep)),
                      encoding='utf-8') as f:
                source = f.read()
            self.assertGreaterEqual(
                source.count(champ), 4,
                f'{rel} : « {champ} » a disparu du livrable, pas seulement '
                f'du contexte API')
        print('    OK T3 : le nom reste dans les 5 livrables (titre, garde, '
              'tables, pied de page)')

    def test_la_consigne_anti_invention_accompagne_chaque_retrait(self):
        """⚠️ SANS ELLE, LE MODÈLE POURRAIT INVENTER UN NOM — dans un rapport
        destiné à l'ACPR, ce serait pire que l'absence."""
        manquants = []
        for rel in ('direction_vie_epre/services/rapport_vie.py',
                    'direction_vie_epre/services/rapport_rvie2.py',
                    'direction_vie_epre/services/rapport_epre.py',
                    'direction_sante_prevoyance/sante/rapport_sante/agent.py',
                    'direction_sante_prevoyance/prevoyance/'
                    'rapport_prevoyance/agent.py'):
            with open(os.path.join(RACINE, rel.replace('/', os.sep)),
                      encoding='utf-8') as f:
                source = f.read()
            if 'ne jamais la nommer ni l\'inventer' not in source:
                manquants.append(rel)
        self.assertEqual(manquants, [], '; '.join(manquants))
        print('    OK T3b : les 5 contextes portent la consigne '
              'anti-invention')


if __name__ == '__main__':
    unittest.main(verbosity=2)
