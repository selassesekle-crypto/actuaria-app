r"""
==============================================================================
  UNE MESURE ABSENTE SE DIT, ELLE NE FAIT PAS TOMBER L'AGENT
==============================================================================

⚠️⚠️ TROISIEME APPARITION DE CETTE FAMILLE DANS CE CHANTIER, ET LA PLUS
CHERE. `.get(cle, defaut)` **ne protege de RIEN quand la cle EXISTE et
vaut `None`** : le defaut ne couvre que l'ABSENCE.

  . `WORD-1` -- six sites derriere `if 'cle' in d`, meme angle mort ;
  . la note `PredictionImpossible` le denonce en toutes lettres ;
  . et le 13/09, `f"{m_poi.get('frequence_pred',0):.4f}"` a fait lever
    `TypeError: unsupported format string passed to NoneType.__format__`.
    A3 a rendu **`success: False`** : le portefeuille n'avait AUCUN TARIF.

⚠️⚠️ LE DEPOT PORTE DEJA SA PRIMITIVE, ET C'EST CE QUI REND LE DEFAUT
INSTRUCTIF. `core.conformite_reglementaire.mesure_texte` l'ecrit : << toute
grandeur qu'un modele peut ne pas avoir produite passe par ici avant
d'atteindre un livrable signe >>. Elle etait employee 18 fois dans A5,
6 dans A6, et le Gini y passait -- *mais pas sa voisine de la meme ligne.*
Le garde etait pose a certaines portes et pas a leurs jumelles.

L'ASSIETTE DE CE CONTROLE EST DERIVEE, JAMAIS ECRITE A LA MAIN : on releve
par AST les cles qu'un agent peut poser a `None`, puis les sites qui les
FORMATENT avec un format numerique. *Une assiette ecrite a la main
atteste ce qu'on a pense a y mettre.*

⚠️ ET L'ERREUR DU RELEVE VA VERS LE SUR-COMPTAGE : le criterion
<< nullable >> retient toute valeur dont l'expression mentionne `None`.
Il peut donc accuser une cle qui ne l'est pas ; il ne peut pas en manquer
une qui l'est par ce chemin. *Un zero rendu par un releve qui sur-compte
vaut une preuve.*
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

_ZONE = _RACINE / 'direction_non_vie' / 'tarification'
#: ⚠️ les formats qui LEVENT sur `None`. `{x}` et `{x:>10}` ne levent pas :
#: les inclure ferait accuser des sites sains.
_SPECS_NUMERIQUES = ('f', 'g', 'e', 'd', '%', ',')


def _fichiers_de_production():
    for p in sorted(_ZONE.rglob('*.py')):
        s = str(p)
        if (p.name.startswith('test_') or '__pycache__' in s
                or 'audit_2026_08' in s):
            continue
        yield p


def _arbre(p):
    try:
        return ast.parse(p.read_bytes().decode('utf-8'))
    except (SyntaxError, UnicodeDecodeError):
        return None


def _cles_nullables():
    """Les cles de dictionnaire dont la valeur PEUT valoir `None`."""
    vues = set()
    for p in _fichiers_de_production():
        a = _arbre(p)
        if a is None:
            continue
        for n in ast.walk(a):
            if not isinstance(n, ast.Dict):
                continue
            for k, v in zip(n.keys, n.values):
                if (isinstance(k, ast.Constant) and isinstance(k.value, str)
                        and 'None' in ast.unparse(v)):
                    vues.add(k.value)
    return vues


def _formats_numeriques(a):
    """(ligne, cle, source) des formats numeriques sur un acces dict."""
    out = []
    for n in ast.walk(a):
        if not isinstance(n, ast.FormattedValue) or n.format_spec is None:
            continue
        if not any(c in ast.unparse(n.format_spec)
                   for c in _SPECS_NUMERIQUES):
            continue
        v, cle = n.value, None
        if isinstance(v, ast.Call) and getattr(v.func, 'attr', '') == 'get':
            if v.args and isinstance(v.args[0], ast.Constant):
                cle = v.args[0].value
        elif isinstance(v, ast.Subscript) and isinstance(v.slice,
                                                         ast.Constant):
            cle = v.slice.value
        if isinstance(cle, str):
            out.append((n.lineno, cle, ast.unparse(v)[:60]))
    return out


def _metriques(mesure: bool):
    """Les metriques d'un moteur, avec ou SANS prediction evaluee.

    ⚠️ `mesure=False` est l'etat EXACT que le commit `1670414` publie quand
    un modele refuse de predire : les observations restent, les predictions
    et les scores passent a `None`. *C'est un etat legitime, pas une
    donnee abimee.*
    """
    return {'metriques': {
        'nb_vars_retenues': 3 if mesure else 0,
        'aic': 1234.5 if mesure else 'N/A',
        'gini': 0.3956 if mesure else None,
        'frequence_obs': 0.2367,
        'frequence_pred': 0.2401 if mesure else None,
        'cout_moyen_obs': 1200.0,
        'cout_moyen_pred': 1187.0 if mesure else None,
        'prime_pure_moy_obs': 280.0,
        'prime_pure_moy_pred': 284.0 if mesure else None,
        'rmse_test': 0.55 if mesure else None,
        'vars_retenues': ['x1'] if mesure else [],
        'prediction_impossible': None if mesure else 'ValueError: shapes',
    }}


def _rediger(m, statut='AMBRE'):
    """Le redacteur reel, appele avec sa vraie signature."""
    import numpy as np
    import pandas as pd

    from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
    r = np.random.default_rng(3)
    d = pd.DataFrame({'nb_sinistres': r.poisson(0.2, 30).astype(float),
                      'exposition': np.full(30, 0.8),
                      'cout_total_sinistres': np.zeros(30)})
    return AgentA3GLM(verbose=False)._commenter_actuaire_senior(
        {}, 'auto', statut, m, m, m, d, d.copy())


class TestUneMesureAbsenteNeFaitPasTomberLAgent(unittest.TestCase):

    def test_ME1_SCEAU_aucune_cle_NULLABLE_n_est_formatee_nue(self):
        """⚠️⚠️ LE SCEAU. Toute grandeur qu'un agent peut ne pas avoir
        produite, et qu'un autre FORMATE en numerique, est un `TypeError` en
        attente. *Le defaut du 13/09 a coute un tarif entier.*"""
        nullables = _cles_nullables()
        self.assertGreater(
            len(nullables), 10,
            f"seulement {len(nullables)} cle(s) nullables relevees : "
            f"l'assiette s'est vidée, ce controle n'atteste plus rien")
        fautifs = []
        for p in _fichiers_de_production():
            a = _arbre(p)
            if a is None:
                continue
            rel = str(p.relative_to(_RACINE)).replace('\\', '/')
            for lg, cle, src in _formats_numeriques(a):
                if cle in nullables:
                    fautifs.append(f'{rel}:{lg} `{cle}` -> {src}')
        self.assertEqual(
            fautifs, [],
            "ces sites formatent en numerique une cle qu'un agent peut "
            "poser a `None` -- `.get(cle, defaut)` ne protege pas d'un "
            "`None`, il ne couvre que l'ABSENCE :\n  "
            + "\n  ".join(fautifs))
        print(f"    ME-1 SCEAU : 0 format nu sur {len(nullables)} cles "
              f"nullables relevees")

    def test_ME2_SCEAU_la_PRIMITIVE_du_depot_dit_l_absence(self):
        """⚠️⚠️ LE COMPORTEMENT, PAS LA PRESENCE D'UN APPEL. Un futur site
        ecrit autrement mais correct doit rester vert ; ce qui doit etre
        tenu, c'est que l'absence se DISE au lieu de lever."""
        from core.conformite_reglementaire import (
            NON_MESURE,
            gini_texte,
            mesure_texte,
        )
        for valeur in (None, float('nan'), float('inf')):
            with self.subTest(valeur=repr(valeur)):
                self.assertEqual(mesure_texte(valeur, 4), NON_MESURE)
                self.assertEqual(gini_texte(valeur), NON_MESURE)
        #: ⚠️ ET LE SECOND SENS : une vraie mesure passe telle quelle.
        self.assertEqual(mesure_texte(0.2367, 4), '0.2367')
        self.assertEqual(mesure_texte(0.0, 2), '0.00',
                         "zero est une MESURE, pas une absence")
        self.assertNotEqual(mesure_texte(0.0, 2), NON_MESURE)
        print(f"    ME-2 SCEAU : None/nan/inf -> {NON_MESURE!r}, "
              f"0.0 -> '0.00' (une mesure, pas une absence)")

    def test_ME3_SCEAU_A3_rend_un_TARIF_meme_sans_frequence_mesuree(self):
        """⚠️⚠️ LE VRAI COMPORTEMENT, ET C'EST LE COEUR DU LOT. Le
        `TypeError` ne faisait pas qu'abimer un texte : il remontait jusqu'au
        `except` de `run`, et A3 rendait `success: False`. *Un tarif entier
        disparaissait parce qu'une ligne de commentaire ne savait pas dire
        « non mesure ».*

        On appelle donc le redacteur avec des metriques dont la prediction
        est ABSENTE -- l'etat exact que le commit B publie quand un modele
        refuse -- et on exige un texte, pas une exception."""
        try:
            texte = _rediger(_metriques(mesure=False))
        except TypeError as e:
            self.fail(
                f"une mesure absente fait encore lever le redacteur -- "
                f"{e}. C'est le defaut du 13/09, et il coutait le tarif.")
        self.assertIsInstance(texte, str)
        self.assertIn(
            'non mesur', texte.lower(),
            "le texte ne DIT pas l'absence : il l'a peut-etre remplacee "
            "par un zero, ce qui fabrique une mesure que personne n'a faite")
        print(f"    ME-3 SCEAU : redacteur appele sans aucune prediction -> "
              f"texte de {len(texte)} caracteres, l'absence est dite")

    def test_ME4_CONTRE_EPREUVE_une_mesure_PRESENTE_est_publiee_telle_quelle(
            self):
        """⚠️ Le second sens, et il est indispensable : un correctif qui
        dirait « non mesure » partout aurait supprime le defaut en
        supprimant la mesure."""
        texte = _rediger(_metriques(mesure=True), statut='VERT')
        for attendu, quoi in (('0.2401', 'la frequence predite'),
                              ('0.3956', 'le Gini'),
                              ('284', 'la prime pure predite')):
            self.assertIn(
                attendu, texte,
                f"{quoi} ({attendu}) n'apparait plus : le correctif a "
                f"remplace une mesure par son absence")
        print("    ME-4 contre-epreuve : frequence, Gini et prime mesures "
              "sont publies tels quels")


if __name__ == '__main__':
    unittest.main(verbosity=2)
