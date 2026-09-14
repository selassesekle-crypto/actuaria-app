"""UNE MESURE ABSENTE NE FAIT PAS DISPARAÎTRE LA FIGURE — CONSTAT `RADAR-1`.

Le bloc G3 d'A6 dessine le « Profil multicritères » du modèle retenu.
Cinq axes, cinq composantes déjà normalisées dans [0,1]. Deux d'entre
elles — la stabilité et le RMSE — peuvent être **NON MESURÉES**, et le
module le dit lui-même à leur naissance :

    a6:1788   s_stab = None      # NON MESURÉE → le critère sortira du score
    a6:1802   s_rmse = None      # NON MESURÉE → le critère sortira du score

et à leur publication :

    a6:1833   modele['score_stabilite'] = (None if s_stab is None else …)
    a6:1836   modele['score_rmse']      = (None if s_rmse is None else …)

⚠️⚠️ CE CONSTAT N'EST PAS UNE VALEUR FAUSSE : C'EST UNE FIGURE SIGNÉE QUI
DISPARAÎT. Le site lisait ces cinq composantes puis les bornait d'un seul
geste — `[min(max(v, 0), 1) for v in vals_radar]`. Or `max(None, 0)` lève
`TypeError`, le `try` du bloc avale l'exception, et l'affectation
`graphiques["radar_modele_retenu"] = fig3`, qui vit APRÈS la ligne
fautive, n'a jamais lieu. *Le seul témoin est une ligne de journal :*

    WARNING | G3 radar : '>' not supported between 'int' and 'NoneType'

MESURÉ PAR EXÉCUTION SUR LE CHEMIN RÉEL, le 14/09/2026, même catalogue à
trois modèles :

    nominal                      4 figures, radar PRÉSENT
    sans `overfit_ratio`         3 figures, radar ABSENT

⚠️ ET LE COMMENTAIRE DU SITE POSAIT DÉJÀ L'INTENTION, MOT POUR MOT :
« Une stabilité NON MESURÉE ne se dessine pas à 0 : ce serait le pire
score possible, aussi inventé que le 1.0 d'avant. `None` laisse Plotly
interrompre le tracé sur cet axe. » *La ligne suivante l'écrasait.* Deux
gestes voisins, l'un annulant l'autre, et la contradiction n'était
visible qu'à l'exécution.

⚠️⚠️ L'AFFIRMATION SUR PLOTLY A ÉTÉ VÉRIFIÉE, PAS CRUE. Si Plotly levait
à son tour sur `None`, laisser passer le `None` n'aurait rien réparé : le
plantage aurait seulement glissé de trois lignes et la figure aurait
disparu pareil. Mesure : `Scatterpolar(r=[0.83, None, …])` se construit,
se rend en HTML et sérialise `null`. *Une phrase de portée se mesure
comme un chiffre.*

⛔⛔ ET LE SECOND AXE PORTAIT LA MÊME MALADIE, MASQUÉE PAR UN FAUX FILET.
`score_rmse` était lu `retenu.get('score_rmse', 0)`. Ce défaut ne protège
de RIEN : il ne s'applique qu'à une clé ABSENTE, et la clé est toujours
POSÉE — à `None`. Mesure : `{'k': None}.get('k', 0)` rend `None`.
L'auditeur ne nommait qu'un axe ; il y en avait deux.

CE QUE CETTE SENTINELLE EXIGE :

  AX-1  le témoin — la fixture produit bien `score_stabilite is None`,
        sinon les exigences suivantes mesureraient un chemin non emprunté ;
  AX-2  **la figure EXISTE** quand une composante n'est pas mesurée ;
  AX-3  l'axe non mesuré porte `None` — ni 0, ni 1, ni une invention ;
  AX-4  le second axe (`score_rmse`) obéit à la même règle ;
  AX-5  le bornage à [0,1] fonctionne TOUJOURS sur les valeurs mesurées —
        la réparation n'affaiblit rien ;
  AX-6  le cas nominal ne bouge pas : mêmes figures, mêmes cinq valeurs ;
  AX-7  **LE CONTRÔLE QUI DÉRIVE** — aucun lecteur de production d'une clé
        nullable ne la lit avec un défaut numérique, et l'ensemble des clés
        se DÉRIVE du producteur au lieu de s'énumérer ici. *Un ensemble
        fermé de noms exacts est un relevé par symbole déguisé en AST.*
"""
import ast
import os
import pathlib
import subprocess
import unittest

from direction_non_vie.tarification.a6_comparaison.agent import (
    AgentA6Comparaison,
)

#: ⚠️ FIXTURES PARTAGÉES, PAS RECOPIÉES. `test_absence_declaree` porte le
#: catalogue et le scoreur depuis le 05/09 ; en écrire une seconde version
#: les ferait diverger au premier ajout. Même patron que
#: `test_conditions_mesure` important `source_aplatie`.
from direction_non_vie.tarification.test_absence_declaree import (
    _catalogue,
    _scorer,
)

_RACINE = pathlib.Path(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_A6 = _RACINE / 'direction_non_vie' / 'tarification' / 'a6_comparaison' / 'agent.py'
_CLE_RADAR = 'radar_modele_retenu'
#: L'ordre des cinq axes, tel que le site les empile.
_AXES = ('score_gini', 'score_stabilite', 'score_interpretabilite',
         'score_rmse', 'score_global')


def _agent():
    return AgentA6Comparaison.__new__(AgentA6Comparaison)


def _figures(classement):
    """Le chemin RÉEL : validation puis fabrique des quatre graphiques."""
    agent = _agent()
    val_sel = agent._valider_selection(
        classement, classement[0]['modele'], {})
    return agent._graphiques_validation_selection(val_sel, classement)


def _rayons(figures):
    """Les valeurs portées par les axes du radar, telles que Plotly les a."""
    trace = figures[_CLE_RADAR].data[0]
    return list(trace.r)


class TestRadarSurvitAUneMesureAbsente(unittest.TestCase):

    # ── AX-1 — le témoin ────────────────────────────────────────────────
    def test_AX1_la_fixture_produit_bien_une_stabilite_non_mesuree(self):
        """Sans cette vérification, AX-2 et AX-3 mesureraient un chemin que
        le cas fautif n'emprunte pas — le 14e piège du dépôt."""
        classement = _scorer(_catalogue(m0={'overfit_ratio': None}))
        self.assertIsNone(
            classement[0]['score_stabilite'],
            "le témoin est mort : la fixture ne produit plus de stabilité "
            "NON MESURÉE, donc les exigences qui suivent ne prouvent rien")
        #: ⚠️ et le modèle retenu doit bien être celui-là, sinon le radar
        #: dessinerait un AUTRE modèle, mesuré, lui.
        self.assertEqual(classement[0]['modele'],
                         _catalogue()[0]['modele'])

    # ── AX-2 — la figure EXISTE ─────────────────────────────────────────
    def test_AX2_la_figure_existe_quand_une_composante_manque(self):
        """Le cœur du constat : ce n'est pas un axe faux, c'est une figure
        signée qui manque au document, sans autre trace qu'un log."""
        figures = _figures(_scorer(_catalogue(m0={'overfit_ratio': None})))
        #: ⚠️ ON COMPARE LES NOMS, PAS LES FIGURES. Un `assertIn` sur le
        #: dictionnaire déverse tout l'objet Plotly dans le message : le
        #: sceau devient illisible à l'instant précis où il sert.
        self.assertIn(
            _CLE_RADAR, sorted(figures),
            "le radar a DISPARU parce qu'une composante n'était pas "
            "mesurée : le bloc G3 a levé, son `except` a écrit un WARNING, "
            "et la clé n'a jamais été posée")

    # ── AX-3 — l'axe non mesuré porte None ──────────────────────────────
    def test_AX3_l_axe_non_mesure_porte_None_et_pas_un_nombre(self):
        """Dessiner 0 serait le PIRE score possible ; dessiner 1 le
        meilleur. Les deux sont des inventions."""
        figures = _figures(_scorer(_catalogue(m0={'overfit_ratio': None})))
        rayons = _rayons(figures)
        i = _AXES.index('score_stabilite')
        self.assertIsNone(
            rayons[i],
            f"l'axe stabilité porte {rayons[i]!r} au lieu de None : une "
            f"mesure absente a été convertie en note")

    # ── AX-4 — le second axe ────────────────────────────────────────────
    def test_AX4_le_second_axe_obeit_a_la_meme_regle(self):
        """`score_rmse` naît `None` exactement comme `score_stabilite`, et
        son lecteur portait un défaut numérique qui ne protégeait de rien :
        `{'k': None}.get('k', 0)` rend `None`."""
        self.assertIsNone({'k': None}.get('k', 0),
                          "prémisse fausse : un défaut de `.get` "
                          "s'appliquerait à une clé présente à None")
        classement = _scorer(_catalogue(m0={'rmse_test': None}))
        self.assertIsNone(classement[0]['score_rmse'],
                          "le témoin du second axe est mort")
        figures = _figures(classement)
        self.assertIn(_CLE_RADAR, sorted(figures),
                      "le radar disparaît sur un RMSE non mesuré")
        rayons = _rayons(figures)
        self.assertIsNone(rayons[_AXES.index('score_rmse')],
                          "l'axe RMSE a reçu un nombre inventé")

    # ── AX-5 — le bornage n'est PAS affaibli ────────────────────────────
    def test_AX5_le_bornage_a_0_1_fonctionne_toujours(self):
        """La contre-épreuve de la réparation elle-même : laisser passer
        `None` ne doit pas laisser passer n'importe quoi."""
        classement = _scorer(_catalogue(m0={'overfit_ratio': None}))
        classement[0]['score_gini'] = 1.4
        classement[0]['score_global'] = -0.2
        rayons = _rayons(_figures(classement))
        self.assertEqual(rayons[_AXES.index('score_gini')], 1,
                         "une valeur > 1 n'est plus ramenée à 1")
        self.assertEqual(rayons[_AXES.index('score_global')], 0,
                         "une valeur < 0 n'est plus ramenée à 0")

    # ── AX-6 — aucun cas déjà correct ne bouge ──────────────────────────
    def test_AX6_le_cas_nominal_est_inchange(self):
        """Toutes les composantes mesurées : mêmes figures, et les cinq
        rayons valent exactement les cinq scores."""
        classement = _scorer(_catalogue())
        figures = _figures(classement)
        self.assertEqual(
            sorted(figures),
            ['gini_comparaison', _CLE_RADAR, 'scorecard_selection',
             'scores_multicriteres'],
            "le jeu de figures du cas nominal a changé")
        rayons = _rayons(figures)
        attendus = [classement[0][a] for a in _AXES]
        for axe, attendu, rayon in zip(_AXES, attendus, rayons):
            self.assertIsNotNone(attendu, f"témoin : {axe} devrait être mesuré")
            self.assertAlmostEqual(
                rayon, min(max(attendu, 0), 1), places=6,
                msg=f"l'axe {axe} ne porte plus son score")

    # ── AX-7 — le contrôle qui DÉRIVE ───────────────────────────────────
    def test_AX7_aucun_lecteur_de_production_ne_met_un_defaut_numerique(self):
        """L'assiette se DÉRIVE du producteur : toute clé publiée sous la
        forme `(None if x is None else …)` est nullable, et aucun lecteur de
        production ne doit la lire avec un défaut numérique — ce défaut ne
        s'applique qu'à l'absence et masque le cas réel."""
        arbre = ast.parse(_A6.read_text(encoding='utf-8'))
        nullables = set()
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Assign):
                continue
            if not isinstance(noeud.value, ast.IfExp):
                continue
            if 'None' not in ast.unparse(noeud.value.body):
                continue
            for cible in noeud.targets:
                if (isinstance(cible, ast.Subscript)
                        and isinstance(cible.slice, ast.Constant)
                        and isinstance(cible.slice.value, str)):
                    nullables.add(cible.slice.value)
        self.assertTrue(
            nullables,
            "l'assiette est VIDE : le relevé ne trouve plus aucune clé "
            "nullable, donc il n'atteste plus rien")

        #: ⚠️ `check=False` EST DELIBERE : hors d'un dépôt git, `ls-files`
        #: sort en erreur et rendrait une liste vide. C'est l'assertion
        #: d'assiette non vide ci-dessus qui doit le dire, pas une
        #: exception opaque levée ici.
        fichiers = subprocess.run(
            ['git', 'ls-files', '*.py'], cwd=str(_RACINE), check=False,
            capture_output=True, text=True, encoding='utf-8',
            errors='replace').stdout.split()
        self.assertTrue(fichiers,
                        "l'assiette des fichiers de production est VIDE : "
                        "`git ls-files` n'a rien rendu, ce contrôle "
                        "n'atteste rien")
        fautifs = []
        for rel in fichiers:
            if '/test_' in '/' + rel or rel.startswith('test_'):
                continue
            chemin = _RACINE / rel
            try:
                source = chemin.read_text(encoding='utf-8', errors='replace')
                sous_arbre = ast.parse(source)
            except (OSError, SyntaxError):
                continue
            for noeud in ast.walk(sous_arbre):
                if not (isinstance(noeud, ast.Call)
                        and isinstance(noeud.func, ast.Attribute)
                        and noeud.func.attr == 'get'
                        and len(noeud.args) == 2
                        and isinstance(noeud.args[0], ast.Constant)
                        and noeud.args[0].value in nullables):
                    continue
                defaut = noeud.args[1]
                if (isinstance(defaut, ast.Constant)
                        and isinstance(defaut.value, (int, float))
                        and not isinstance(defaut.value, bool)):
                    fautifs.append(f"{rel}:{noeud.lineno}  "
                                   f"{ast.unparse(noeud)[:60]}")
        self.assertFalse(
            fautifs,
            "une clé qui peut valoir None est lue avec un défaut numérique. "
            "Ce défaut ne s'applique qu'à l'ABSENCE : sur une clé présente "
            "à None il ne protège de rien, et il fait croire l'inverse.\n  "
            + "\n  ".join(fautifs))


if __name__ == '__main__':
    unittest.main(verbosity=2)
