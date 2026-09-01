"""Controles positifs -- `a4` : les quatre derniers constats de la zone.

═══ ⛔⛔ `C3` -- LE QUATRIEME ETAT : CORRIGE, EPINGLE... ET NOMME NULLE PART ═══

Le graphique d'overfitting affichait un Gini test NUL pour tous les modeles :

    trace << Gini Test >> = [0, 0, 0, 0, 0, 0]
    valeurs REELLES       = [0.3405, 0.2946, 0.2886, 0.2536, 0.2349, 0.1156]

Cause : `m.get('gini', 0)` alors que la cle du classement est `gini_test`. Les
couleurs, calculees sur ce zero, sortaient TOUTES en rouge -- sous une legende
qui dit << un grand ecart = surapprentissage >>.

⚠️⚠️ MESURE DU 01/09 : LE CODE ETAIT DEJA CORRIGE, ET DEJA EPINGLE par
`test_le_graphique_d_overfitting_porte_les_Gini_REELS`. Mais la cle `a4/C3`
n'etait ECRITE NULLE PART -- donc invisible pour `ARCH-1`, donc comptee
OUVERTE.

> *Un correctif sans le nom de son constat est un correctif que l'archive ne
> peut pas voir.* C'est la seconde occurrence du quatrieme etat, apres `a5/C3`.

═══ ⛔⛔ `C7` -- << ML x8 >>, ET LE COMPTE SE TROMPAIT DANS LES DEUX SENS ═══

Dix mentions de << 8 >> dans le module. La boucle de calibration en tient SIX.
Et l'en-tete ne se contentait pas d'un mauvais chiffre :

| annonce dans l'en-tete | dans la boucle ? |
|---|---|
| RandomForest | NON |
| GAM | NON -- **le nom n'existe nulle part dans le depot** |
| RegQuantile | NON |
| *(absent de l'en-tete)* | `xgboost_tweedie`, CALIBRE |

> *Une liste qui se trompe dans les deux sens ne se corrige pas au chiffre :
> elle se REECRIT depuis la source.*

⚠️ `FAMILLES_MODELES_ML` en declare DIX, et c'est JUSTE : c'est une table de
FAMILLES, pas une liste de candidats -- elle nomme aussi ce qui pourrait
arriver d'ailleurs. *Les deux comptes sont vrais ; les confondre produisait
<< 8 >>.*

═══ LES DEUX AUTRES ═══

`C12` -- cinq entrees Vie/Sante dans `COLS_A_EXCLURE_ML`. **Jumeau exact
d'`a3/C16`**, meme liste heritee, MEME ARBITRAGE : elles RESTENT. Cette liste
EXCLUT ; en oter une AJOUTERAIT une variable au modele si un fichier client
portait cette colonne. *Le geste << propre >> est ici le geste RISQUE.*

`C13` -- l'en-tete de test annoncait << 7 tests >> pour **18** methodes. Le
constat lui-meme disait 11 : il avait peri entre sa redaction et aujourd'hui,
ce qui est exactement l'argument pour ne plus annoncer de compte.
"""

from __future__ import annotations

import ast
import glob
import pathlib
import unittest

import yaml

from direction_non_vie.tarification.a4_ml import agent as _a4mod
from direction_non_vie.tarification.a4_ml.agent import (
    COLS_A_EXCLURE_ML,
    FAMILLES_MODELES_ML,
)

_SOURCE = pathlib.Path(_a4mod.__file__).read_text(encoding='utf-8')
_DOSSIER = pathlib.Path(_a4mod.__file__).parent
_SOURCE_TEST = (_DOSSIER / 'test_a4_ml.py').read_text(encoding='utf-8')
_PLANS = str(pathlib.Path(_a4mod.__file__).parents[3] / 'plans' / '*.yaml')
_VIE_SANTE = ('id_salarie', 'id_beneficiaire', 'id_adherent',
              'cotisation_mensuelle_eur', 'charge_ij_annuelle_eur')


def _modeles_de_la_boucle():
    """Les noms de la boucle de calibration, PAR AST -- jamais recopies."""
    for n in ast.walk(ast.parse(_SOURCE)):
        if not (isinstance(n, ast.Assign) and n.targets
                and getattr(n.targets[0], 'id', '') == 'modeles_a_calibrer'):
            continue
        return [e.elts[0].value for e in n.value.elts
                if isinstance(e, ast.Tuple) and isinstance(e.elts[0],
                                                           ast.Constant)]
    return []


class TestA4QuatreConstats(unittest.TestCase):
    """Quatre constats de la zone `a4`."""

    # ── `a4/C3` — le quatrieme etat ─────────────────────────────────────────

    def test_A4_1_LE_TEST_QUI_FERME_la_figure_lit_gini_test(self):
        """`a4/C3` : la cle du classement, pas une cle qui n'a jamais existe.

        ⚠️ Le FAIT (la trace n'est pas a zero) appartient a
        `test_le_graphique_d_overfitting_porte_les_Gini_REELS`, qui tourne sur
        un run reel. Ce controle-ci porte sur la SOURCE -- deuxieme assiette --
        et sur le NOM du constat, qui manquait.
        """
        # ⚠️⚠️ ASSIETTE : LES DEUX TRACES DE LA FIGURE, PAS TOUT `get('gini')`.
        # Ma premiere version interdisait la cle `gini` PARTOUT et relevait
        # cinq sites -- dont trois `result_a3['metriques'].get('poisson',
        # {}).get('gini', 0)`, ou `gini` EST la bonne cle : c'est celle d'A3.
        # *Deux dictionnaires qui partagent un nom de cle ne partagent pas sa
        # signification* -- le piege de l'homonyme, troisieme fois de la
        # session. Le controle porte donc sur les deux listes qui alimentent
        # la figure, reperees par leur nom d'assignation.
        cles = {}
        for n in ast.walk(ast.parse(_SOURCE)):
            if (isinstance(n, ast.Assign) and n.targets
                    and getattr(n.targets[0], 'id', '') in ('ginis_t',
                                                            'ginis_tr')):
                for c in ast.walk(n.value):
                    if (isinstance(c, ast.Call)
                            and getattr(c.func, 'attr', None) == 'get'
                            and c.args and isinstance(c.args[0], ast.Constant)):
                        cles[n.targets[0].id] = c.args[0].value
        self.assertEqual(
            cles, {'ginis_t': 'gini_test', 'ginis_tr': 'gini_train'},
            f"les traces de la figure d'overfitting ne lisent pas les cles du "
            f"classement : {cles}. `_classer_modeles` pose `gini_test` et "
            f"`gini_train` ; `gini` n'a jamais existe dans ce dictionnaire.")
        self.assertIn(
            'a4/C3', _SOURCE_TEST,
            "le test qui epingle ce constat ne le NOMME pas : l'archive ne "
            "peut pas le voir, et il compte OUVERT alors qu'il est ferme")

    # ── `a4/C7` — l'en-tete se derive de la boucle ─────────────────────────

    def test_A4_2_LE_TEST_QUI_FERME_l_en_tete_liste_LA_BOUCLE(self):
        """`a4/C7` : les deux sens -- ni oubli, ni nom en trop."""
        boucle = _modeles_de_la_boucle()
        self.assertTrue(boucle, 'la boucle de calibration est introuvable')
        # ⚠️⚠️ L'ASSIETTE EST LA SECTION << MODELES CALIBRES >>, PAS TOUT
        # L'EN-TETE. Le sceau l'a demasque : retirer `xgboost_tweedie` de la
        # LISTE ne faisait rien tomber, parce que le paragraphe qui EXPLIQUE
        # le constat le cite (<< REELLEMENT calibre, xgboost_tweedie... >>).
        # *Une citation n'est pas une affirmation* -- et c'est ici la forme la
        # plus vicieuse : elle ne declenche pas le controle a tort, elle le
        # fait PASSER a tort. Un controle qui lit son propre commentaire
        # d'explication ne peut plus echouer.
        entete = _SOURCE.split('"""')[1]
        marqueur = 'MODELES CALIBRES'
        self.assertIn(marqueur, entete,
                      "la section qui liste les modeles a disparu")
        bloc = []
        for ligne in entete.split('\n')[entete.split('\n').index(
                next(l for l in entete.split('\n') if marqueur in l)) + 1:]:
            nu = ligne.strip('║ ')
            if nu.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.',
                              '9.')):
                bloc.append(nu)
            elif bloc and not nu:
                break
        self.assertTrue(bloc, 'la liste numerotee des modeles est vide')
        annonces = [l.split('--')[0].split('.', 1)[1].strip() for l in bloc]
        self.assertEqual(
            annonces, list(boucle),
            f"la liste de l'en-tete ne correspond PAS a la boucle de "
            f"calibration.\n  en-tete : {annonces}\n  boucle  : {list(boucle)}")
        # `GAM` n'existe nulle part : la mesure, pas le souvenir.
        self.assertNotIn('gam', {n.lower() for n in FAMILLES_MODELES_ML})

    def test_A4_3_aucun_compte_de_modeles_n_est_annonce_ailleurs(self):
        """`a4/C7` : dix mentions de << 8 >>, aucune derivee."""
        import re
        motif = re.compile(r'(×|x)\s*8\b|\b8\s+MOD|\b8\s+mod')
        # ⚠️ UNE CITATION N'EST PAS UNE AFFIRMATION -- cinquieme fois de la
        # session. Le correctif de `C7` CITE le compte qu'il retire
        # (<< CET EN-TETE ANNONCAIT << 8 MODELES >> >>), et ma premiere
        # version de ce controle tombait dessus. L'assiette est ce qui
        # ANNONCE, pas ce qui rapporte.
        citation = re.compile(r'CONSTAT|ANNONCAIT|produisait')
        fautifs = []
        for chemin in glob.glob(str(_DOSSIER / '*.py')):
            for i, ligne in enumerate(
                    pathlib.Path(chemin).read_text(
                        encoding='utf-8').split('\n'), 1):
                if motif.search(ligne) and not citation.search(ligne):
                    fautifs.append(f'{pathlib.Path(chemin).name}:{i}')
        self.assertEqual(
            fautifs, [],
            f"un compte de modeles est encore annonce en dur : {fautifs}. "
            f"La seule source est la boucle de `_calibrer_tous_modeles`.")

    # ── `a4/C12` — les entrees Vie/Sante RESTENT, et sont dites ────────────

    def test_A4_4_LE_TEST_QUI_FERME_le_temoin_des_entrees_Vie_Sante(self):
        """`a4/C12` : elles restent, et AUCUN plan ne les nomme.

        ⚠️ Jumeau exact d'`a3/C16` : meme liste heritee, meme arbitrage. En
        oter une AJOUTERAIT une variable au modele si un fichier client
        portait cette colonne. Le temoin RE-MESURE au lieu de recopier.
        """
        for nom in _VIE_SANTE:
            self.assertIn(
                nom, COLS_A_EXCLURE_ML,
                f"'{nom}' a ete retiree de la liste d'EXCLUSION : si un "
                f"fichier client porte cette colonne, elle entre desormais "
                f"dans la matrice X du ML")
        plans = glob.glob(_PLANS)
        self.assertGreater(len(plans), 10, 'les plans sont introuvables')
        nommees = {}
        for chemin in plans:
            texte = pathlib.Path(chemin).read_text(encoding='utf-8')
            donnees = yaml.safe_load(texte) or {}
            noms = {f.get('nom') for f in (donnees.get('facteurs') or [])
                    if isinstance(f, dict)}
            croisement = noms & set(_VIE_SANTE)
            if croisement:
                nommees[pathlib.Path(chemin).name] = sorted(croisement)
        self.assertEqual(
            nommees, {},
            f"un plan declare une colonne de la liste d'exclusion Vie/Sante : "
            f"{nommees}. L'arbitrage << on n'en retire aucune >> reposait sur "
            f"le fait qu'aucun plan ne les nomme.")
        self.assertIn('a4/C12', _SOURCE,
                      "l'arbitrage n'est pas ecrit a cote de la liste")

    # ── `a4/C13` — plus aucun compte de tests ──────────────────────────────

    def test_A4_5_aucun_en_tete_de_la_zone_n_annonce_un_compte_de_tests(self):
        """`a4/C13` : << 7 tests >> pour 18 methodes -- et le constat disait 11."""
        import re
        motif = re.compile(r'\b\d+\s+tests?\b', re.IGNORECASE)
        for chemin in glob.glob(str(_DOSSIER / '*.py')):
            tete = pathlib.Path(chemin).read_text(
                encoding='utf-8').split('"""')[1:2]
            if not tete:
                continue
            trouve = motif.search(tete[0])
            self.assertIsNone(
                trouve,
                f'{pathlib.Path(chemin).name} annonce '
                f'<< {trouve.group(0) if trouve else ""} >> dans son en-tete')


if __name__ == '__main__':
    unittest.main(verbosity=2)
