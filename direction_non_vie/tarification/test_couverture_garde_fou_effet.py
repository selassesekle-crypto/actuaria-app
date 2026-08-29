"""Controles positifs — `conformite/C10` : ce que le garde-fou ne lit pas.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
UNE SEULE PROPRIETE : *un controle qui saute ce qu'il ne sait pas lire, EN
SILENCE, rend << aucune fuite trouvee >> indiscernable de << pas regarde >>.*

═══ LE DEFAUT, REPRODUIT AVANT CORRECTIF ═══

`x = df[c].astype(float)` dans un `try/except (TypeError, ValueError): continue`.
Une colonne non numerique disparaissait sans un mot :

    ecartees : ['flag_sinistre']
    flag_sinistre   (NUMERIQUE) vue ? True    <- Spearman 0,988, attrapee
    libelle_gravite (TEXTE)     vue ? False   <- LA MEME INFORMATION, invisible

⚠️ C'est mot pour mot la doctrine que le `except` GLOBAL de cette meme fonction
ecrit deja -- << ECHEC VISIBLE, JAMAIS SILENCIEUX >> : le saut interne la
contredisait.

═══ L'AMPLEUR REELLE, MESUREE ET NON GONFLEE ═══

⚠️⚠️ SELASSE A DEMANDE DE VERIFIER SI A2 ENCODE AVANT QUE LE DETECTEUR NE
TOURNE, ET DE NE RIEN GONFLER. Mesure par instrumentation du detecteur sur des
runs reels :

    chemin AGENT       20 appels · 22 features · 0 colonne texte
    chemin DECLARATIF   2 appels · 23 features · 0 colonne texte

**AUCUN chemin de production n'expose le trou aujourd'hui** : `feature_names`
vient de `plan.colonnes_produites()`, et A2 encode les facteurs declares. Le
defaut est donc REEL DANS LA FONCTION et LATENT SUR LES CHEMINS -- meme etat
que la fuite Optuna d'A4.

⚠️ CE QUI N'EST DONC PAS FAIT, ET POURQUOI : l'information NE REMONTE PAS
jusqu'au livrable. Le canal existe (`controle_effet` -> `MatriceX` -> agents ->
A6 -> `avertissement_controle_effet`), mais l'y brancher toucherait cinq sites
pour publier << 0 colonne sautee >> sur chaque rapport, d'un fait jamais
observe. *La lecon de `conformite/C7` -- un WARNING seul n'atteint pas
l'actuaire -- vaut pour un fait QUI SE PRODUIT ; ici il ne se produit pas.*
Le jour ou il se produira, le journal le NOMMERA, et ce sera le signal
d'ouvrir le cablage. **C'est une borne declaree, pas un oubli.**

⚠️ ET `motifs` N'A PAS ETE REUTILISE : il compte des CIBLES non examinees
(<< N/M cible(s) >>). Y glisser des colonnes aurait fait mentir son propre
compte -- exactement le defaut d'assiette que cet audit poursuit.
"""

from __future__ import annotations

import ast
import io
import logging
import pathlib
import unittest

import numpy as np
import pandas as pd

from core.conformite_reglementaire import detecter_fuites_par_effet

_RACINE = pathlib.Path(__file__).resolve().parent.parent.parent


def _donnees(n: int = 1500):
    """Une fuite parfaite, en DEUX formes : numerique et texte."""
    rng = np.random.default_rng(3)
    y = rng.poisson(0.4, n).astype(float)
    return pd.DataFrame({
        'age': rng.integers(18, 80, n).astype(float),
        'nb_sinistres': y,
        # la cible binarisee EN TEXTE — le scenario exact du constat
        'libelle_gravite': np.where(y > 0, 'sinistre', 'aucun'),
        # la MEME information, en numerique
        'flag_sinistre': (y > 0).astype(float),
    })


def _executer(features, df=None):
    """Lance le detecteur et rend (fuites, journal)."""
    df = _donnees() if df is None else df
    flux = io.StringIO()
    poste = logging.StreamHandler(flux)
    poste.setLevel(logging.WARNING)
    journal = logging.getLogger('test.c10')
    journal.handlers = [poste]
    journal.setLevel(logging.WARNING)
    journal.propagate = False
    fuites = detecter_fuites_par_effet(df, features, 'nb_sinistres',
                                       logger_agent=journal)
    return fuites, flux.getvalue()


class TestCeQuiNEstPasLuEstNomme(unittest.TestCase):
    """`conformite/C10` — la couverture incomplète se déclare."""

    def test_la_colonne_TEXTE_est_NOMMEE_dans_le_journal(self):
        """⚠️⚠️ LE TEST QUI FERME LE CONSTAT.

        Avant : elle disparaissait dans un `continue`, sans un mot. Le
        `continue` reste — une colonne illisible ne PEUT pas être corrélée, et
        lever désactiverait le garde-fou entier pour une seule colonne. Ce qui
        change, c'est qu'elle est **nommée**.
        """
        _, journal = _executer(['age', 'libelle_gravite', 'flag_sinistre'])
        self.assertIn('COUVERTURE INCOMPLÈTE', journal)
        self.assertIn('libelle_gravite', journal)
        self.assertIn('NON NUMÉRIQUE', journal)
        print("    R-1 la colonne texte est NOMMEE (avant : disparue en "
              "silence)")

    def test_le_message_dit_POURQUOI_c_est_grave(self):
        """⚠️ « Colonne sautée » sans dire ce que ça coûte n'alerte personne.

        Le texte doit nommer le risque — une fuite en texte y est invisible —
        et rappeler que seuls les contrôles par le NOM protègent alors, ceux
        que l'audit V12 a démontrés insuffisants.
        """
        _, journal = _executer(['age', 'libelle_gravite'])
        for attendu in ('INVISIBLE', 'par le NOM', 'garde-fou n°4'):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, journal)
        print("    R-2 le message nomme le risque, pas seulement le fait")

    def test_LA_MEME_information_en_numerique_est_TOUJOURS_attrapee(self):
        """⚠️⚠️ SECOND SENS — le correctif ne doit rien affaiblir.

        `flag_sinistre` est la même fuite, en numérique : elle DOIT rester
        écartée, à Spearman 0,988. *Un correctif qui protégerait moins qu'avant
        fermerait le constat en créant un défaut.*
        """
        fuites, _ = _executer(['age', 'libelle_gravite', 'flag_sinistre'])
        self.assertIn('flag_sinistre', fuites)
        self.assertNotIn('age', fuites)
        print(f"    R-3 second sens : la fuite NUMERIQUE reste attrapee "
              f"({sorted(fuites)})")

    def test_TEMOIN_aucune_colonne_texte_NE_DIT_RIEN(self):
        """⚠️⚠️ SECOND SENS, ET IL COMPTE AUTANT.

        Un avertissement posé sur tous les dossiers cesserait d'être un
        signal — et ce serait le cas de TOUS les runs de production, où 0
        colonne texte atteint le détecteur.
        """
        _, journal = _executer(['age', 'flag_sinistre'])
        self.assertNotIn('COUVERTURE INCOMPLÈTE', journal)
        print("    R-4 temoin : que du numerique -> aucun avertissement")

    def test_le_COMPTE_annonce_est_le_nombre_REEL_de_colonnes_sautees(self):
        """⚠️ Un compte annoncé se vérifie contre ce qu'il compte."""
        df = _donnees()
        df['libelle_zone'] = np.where(df['age'] > 45, 'nord', 'sud')
        _, journal = _executer(['age', 'libelle_gravite', 'libelle_zone'], df)
        self.assertIn('2 colonne(s)', journal)
        for c in ('libelle_gravite', 'libelle_zone'):
            self.assertIn(c, journal)
        print("    R-5 2 colonnes sautees -> « 2 colonne(s) », les deux "
              "nommees")

    def test_le_saut_reste_un_CONTINUE_pas_une_LEVEE(self):
        """⚠️⚠️ CE QUE LE CORRECTIF NE FAIT PAS, ET POURQUOI.

        Lever sur une colonne illisible désactiverait le garde-fou pour TOUTES
        les autres — le défaut V6 que le `except` global de cette fonction
        raconte. Le contrôle doit continuer d'examiner ce qu'il PEUT lire.
        """
        fuites, journal = _executer(['libelle_gravite', 'flag_sinistre'])
        self.assertIn('flag_sinistre', fuites,
                      'le garde-fou a cesse d examiner apres la colonne texte')
        self.assertIn('COUVERTURE INCOMPLÈTE', journal)
        print("    R-6 le controle CONTINUE apres une colonne illisible, et "
              "le dit")

    def test_motifs_N_A_PAS_ete_detourne_de_son_assiette(self):
        """⚠️⚠️ `motifs` COMPTE DES CIBLES, PAS DES COLONNES.

        `avertissement_controle_effet` publie « N/M cible(s) non examinée(s) »
        à partir de `len(motifs)`. Y glisser des colonnes aurait fait mentir ce
        compte. Ce test fige la séparation : le fait neuf a son propre canal
        (le journal), il n'emprunte pas celui d'un autre.
        """
        source = (_RACINE / 'core' / 'conformite_reglementaire.py').read_text(
            encoding='utf-8')
        fn = next(n for n in ast.walk(ast.parse(source))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == 'detecter_fuites_par_effet')
        noms = {x.id for x in ast.walk(fn) if isinstance(x, ast.Name)}
        self.assertIn('non_examinees', noms)
        self.assertNotIn('motifs_effet', noms,
                         "le detecteur ecrit dans `motifs_effet`, dont le "
                         "compte porte sur les CIBLES")
        print("    R-7 `motifs` garde son assiette : le fait neuf a son "
              "propre nom")


if __name__ == '__main__':
    unittest.main()
