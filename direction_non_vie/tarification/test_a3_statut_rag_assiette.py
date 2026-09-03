# -*- coding: utf-8 -*-
"""
=============================================================================
  L'ASSIETTE DU STATUT RAG D'A3 -- ce qu'il lit, et ce qu'il NE lit PAS
=============================================================================

CE FICHIER EXISTE PARCE QU'UNE QUESTION EST RESTEE EN SUSPENS HUIT JOURS.

`_calculer_statut_rag` portait, depuis le constat `a3/C10`, cette phrase :

  << faire entrer le Tweedie dans le statut importerait son Gini, dont le
  constat `a3/C6` etablit qu'il vaut 0 partout. [...] le jour ou `a3/C6`
  sera ferme, la question de l'inclure se reposera. >>

`a3/C6` a ete ferme le **26/08/2026** (`b0ae396`). La condition etait donc
remplie, et **rien ne l'a rappele** : ni un test, ni une gate, ni le compte
de l'archive -- qui affiche `a3` 19/19 ferme. *Une suite documentee n'est
pas une suite tenue.*

-----------------------------------------------------------------------------
CE QUE CE FILET FAIT, ET CE QU'IL NE FAIT PAS
-----------------------------------------------------------------------------
Il ne tranche PAS. Deux points relevent de l'actuaire, pas du module :
un Gini Tweedie NON MESURABLE doit-il rendre le statut AMBRE, ROUGE, ou
rester sans effet ? Un Tweedie ANTI-SELECTIF (Gini < 0) doit-il degrader un
statut que le Poisson rend VERT ?

Il rend la decision IMPOSSIBLE A PRENDRE EN SILENCE : l'assiette de lecture
est verrouillee par AST.

  *Un garde-fou ne remplace pas un arbitrage ; il l'oblige a etre explicite.*

-----------------------------------------------------------------------------
⛔⛔ ET CE FICHIER A DEJA MONTRE SON PROPRE TROU -- LE 03/09/2026, MEME JOUR
-----------------------------------------------------------------------------
`AC6-1` promettait : << le jour ou quelqu'un fait entrer le Tweedie, il
tombe >>. Selasse a arbitre le soir meme qu'un Tweedie ANTI-SELECTIF force
ROUGE. Le Tweedie est donc entre dans le statut d'A3 -- et **`AC6-1` est
reste VERT**.

Raison : le correctif applique `statut_anti_selection(...)` dans `run()`,
APRES `_calculer_statut_rag`, comme le fait deja
`plafonner_statut_si_ampute`. L'assiette d'`AC6-1` est la FONCTION ; le
statut, lui, se construit par un PIPELINE de trois transformations.

  *Un controle garde ce qu'on a pense a lui donner. << Ce que lit la
  fonction >> et << ce qui determine le statut >> ne sont pas la meme
  assiette, et la seconde est celle qui compte.*

`AC6-6` verrouille desormais le pipeline complet : toute fonction ajoutee
ou retiree de la chaine qui produit `statut_rag` le fait tomber.
=============================================================================
"""

import ast
import inspect
import textwrap
import unittest

from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM

_FONCTION = '_calculer_statut_rag'

#: Ce que le statut lit, MESURE le 03/09/2026 et arbitre par `a3/C10` :
#: le Gini du POISSON seul, et la convergence des DEUX modeles.
_LECTURES_ADMISES = {'poisson', 'gamma', 'gini', 'nb_vars_retenues'}

#: ⚠️ Ce qui n'y entre PAS sans decision. `tweedie` est la question en
#: suspens ; `gini` du gamma en est le residu (assigne puis jamais relu
#: jusqu'au 03/09).
_HORS_ASSIETTE = {'tweedie'}


def _arbre_fonction() -> ast.FunctionDef:
    """L'AST de la fonction TELLE QU'ELLE S'EXECUTE.

    ⚠️ On part de `inspect.getsource` sur l'objet importe, pas d'un chemin
    de fichier devine : c'est le corps reellement charge qui est mesure.
    """
    source = inspect.getsource(getattr(AgentA3GLM, _FONCTION))
    return ast.parse(textwrap.dedent(source)).body[0]


def _cles_lues(noeud: ast.AST) -> set[str]:
    """Toute cle de chaine atteinte dans le corps, HORS docstring.

    ⚠️ L'ASSIETTE EST LE CODE, JAMAIS LA PROSE. La docstring de la fonction
    cite `tweedie` une dizaine de fois pour expliquer pourquoi il en est
    absent : un releve au texte conclurait l'inverse de la verite.

    ⚠️⚠️ ET ELLE COMPTE DEUX FORMES D'ACCES, PARCE QUE LE SCEAU A MONTRE
    QU'UNE SEULE NE SUFFIT PAS. Ma premiere version ne regardait que les
    appels `.get('cle', ...)`. La violation plantee
    `metriques['tweedie']['gini']` la traversait sans la faire broncher :
    le controle presente comme << celui qui tient >> laissait passer
    l'acces le plus direct qui soit.

      *Un releve par UNE forme syntaxique n'est pas un releve : la
      violation entre par celle qu'on n'a pas prevue.*
    """
    cles = set()
    for n in ast.walk(noeud):
        if (isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'get'
                and n.args
                and isinstance(n.args[0], ast.Constant)
                and isinstance(n.args[0].value, str)):
            cles.add(n.args[0].value)
        elif (isinstance(n, ast.Subscript)
                and isinstance(n.slice, ast.Constant)
                and isinstance(n.slice.value, str)):
            cles.add(n.slice.value)
        elif (isinstance(n, ast.Compare)
                and any(isinstance(o, (ast.In, ast.NotIn)) for o in n.ops)
                and isinstance(n.left, ast.Constant)
                and isinstance(n.left.value, str)):
            # `if 'tweedie' in metriques` : un test d'appartenance est deja
            # une lecture de la cle, et c'est par la qu'on garde un acces
            # par indice de lever.
            cles.add(n.left.value)
    return cles


class T1_Assiette(unittest.TestCase):

    def test_ac6_1_le_statut_ne_lit_que_ce_qui_est_arbitre(self):
        """AC6-1 : L'ASSIETTE. Le Tweedie ne peut pas y entrer en silence.

        ⚠️ Ce controle est ce qui manquait : la question etait posee dans
        une docstring, et une docstring ne se declenche jamais.
        """
        lues = _cles_lues(_arbre_fonction())
        intruses = lues - _LECTURES_ADMISES
        self.assertFalse(
            intruses,
            f"{_FONCTION} lit des cles hors de son assiette arbitree : "
            f"{sorted(intruses)}.\nSi c'est voulu, l'arbitrage doit etre "
            f"ECRIT (docstring de la fonction) et cette liste mise a jour "
            f"dans le meme geste.")
        for interdite in _HORS_ASSIETTE:
            self.assertNotIn(
                interdite, lues,
                f"« {interdite} » est entre dans le statut RAG sans que la "
                f"question laissee en suspens le 26/08/2026 soit tranchee : "
                f"un Gini non mesurable vaut None, et un Tweedie "
                f"anti-selectif peut etre negatif.")

    def test_ac6_2_aucune_locale_calculee_puis_jetee(self):
        """AC6-2 : rien n'est calcule sans servir a la decision.

        ⚠️ `gini_gamma` etait assigne ligne 2005 et jamais relu -- il
        laissait croire que le Gamma pesait sur le statut. Retire le
        03/09/2026. *Un calcul qui n'atteint aucune decision n'existe pas,
        mais il TROMPE le lecteur.*
        """
        fonc = _arbre_fonction()
        assignes, lus = {}, set()
        for n in ast.walk(fonc):
            if isinstance(n, ast.Name):
                if isinstance(n.ctx, ast.Store):
                    assignes.setdefault(n.id, n.lineno)
                else:
                    lus.add(n.id)
        mortes = sorted(n for n in assignes if n not in lus and n != '_')
        self.assertFalse(
            mortes,
            f"{_FONCTION} calcule ces valeurs sans jamais les relire : "
            f"{mortes}")


class T1bis_LePipelineDuStatut(unittest.TestCase):
    """⚠️⚠️ L'ASSIETTE QUI COMPTE VRAIMENT : ce qui DETERMINE le statut.

    `AC6-1` garde ce que LIT `_calculer_statut_rag`. Mais le statut publie
    par A3 n'est pas ce que rend cette fonction : c'est le resultat d'une
    CHAINE de transformations appliquees dans `run()`. Une quatrieme
    fonction glissee dans cette chaine changerait le statut sans qu'`AC6-1`
    bronche -- et c'est arrive, le jour meme ou ce fichier a ete ecrit.
    """

    #: La chaine ARBITREE, dans l'ordre. Chaque entree a sa raison :
    #:   `_calculer_statut_rag`      -- le calcul de base (Gini Poisson)
    #:   `plafonner_statut_si_ampute` -- plafond AMBRE si le plan est ampute
    #:   `statut_anti_selection`      -- ROUGE si un Gini mesure est negatif
    #:                                   (arbitrage Selasse du 03/09/2026)
    _CHAINE_ARBITREE = (
        '_calculer_statut_rag',
        'plafonner_statut_si_ampute',
        'statut_anti_selection',
    )

    def test_ac6_6_la_chaine_qui_produit_le_statut_est_verrouillee(self):
        """AC6-6 : rien ne s'ajoute a la chaine du statut en silence."""
        source = inspect.getsource(AgentA3GLM)
        arbre = ast.parse(textwrap.dedent(source)).body[0]
        appliquees = []
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Assign):
                continue
            if not any(getattr(c, 'id', '') == 'statut_rag'
                       for c in noeud.targets):
                continue
            if isinstance(noeud.value, ast.Call):
                fonc = noeud.value.func
                appliquees.append(getattr(fonc, 'attr', None)
                                  or getattr(fonc, 'id', ast.unparse(fonc)))
        self.assertEqual(
            tuple(appliquees), self._CHAINE_ARBITREE,
            f"la chaine qui produit `statut_rag` a change.\n"
            f"  mesuree : {tuple(appliquees)}\n"
            f"  arbitree: {self._CHAINE_ARBITREE}\n"
            f"Toute transformation du statut est une DECISION : elle "
            f"s'ecrit ici, avec sa raison, dans le meme geste que le code.")


class T2_Comportement(unittest.TestCase):
    """Ce que la fonction REND, sur des entrees construites."""

    def setUp(self):
        self.agent = AgentA3GLM.__new__(AgentA3GLM)

    @staticmethod
    def _met(gini_p, vars_p=3, vars_g=3, **extra):
        m = {'poisson': {'gini': gini_p, 'nb_vars_retenues': vars_p},
             'gamma': {'gini': 0.30, 'nb_vars_retenues': vars_g}}
        m.update(extra)
        return m

    def test_ac6_3_les_trois_statuts_sont_atteignables_et_derives(self):
        """AC6-3 : VERT / AMBRE / ROUGE suivent bien les entrees."""
        cas = [
            (self._met(0.20), 'VERT'),
            (self._met(0.10), 'AMBRE'),
            (self._met(0.20, vars_g=0), 'AMBRE'),
            (self._met(0.02), 'ROUGE'),
            (self._met(0.20, vars_p=0, vars_g=0), 'ROUGE'),
        ]
        for metriques, attendu in cas:
            with self.subTest(attendu=attendu, gini=metriques['poisson']['gini']):
                self.assertEqual(
                    self.agent._calculer_statut_rag(metriques), attendu)

    def test_ac6_4_un_gini_tweedie_None_ne_change_RIEN_aujourd_hui(self):
        """AC6-4 : le statut est INSENSIBLE au Tweedie, y compris `None`.

        ⚠️ C'est la mesure qui justifie de ne pas trancher a la legere :
        depuis `a3/C6`, `metriques['tweedie']['gini']` vaut `float | None`.
        Une comparaison naive `< 0.05` sur `None` LEVE -- verifie ici -- donc
        inclure le Tweedie exige d'abord de decider ce que vaut un Gini non
        mesurable pour un statut. Tant que ce n'est pas decide, le statut
        doit rester exactement le meme avec ou sans Tweedie.
        """
        gini_non_mesurable = None
        with self.assertRaises(TypeError):
            self.assertLess(gini_non_mesurable, 0.05)

        for tweedie in ({'gini': None}, {'gini': -0.078}, {'gini': 0.90}, {}):
            with self.subTest(tweedie=tweedie):
                sans = self.agent._calculer_statut_rag(self._met(0.20))
                avec = self.agent._calculer_statut_rag(
                    self._met(0.20, tweedie=tweedie))
                self.assertEqual(
                    sans, avec,
                    f"le Tweedie {tweedie} a deplace le statut alors que la "
                    f"question de l'inclure n'est pas tranchee")


class T3_LaSuiteEstConsignee(unittest.TestCase):

    def test_ac6_5_la_docstring_ne_presente_plus_le_blocage_comme_actuel(self):
        """AC6-5 : la raison consignee cite la fermeture qui l'a rendue caduque.

        ⚠️ CE CONTROLE LIT DE LA PROSE, et c'est le plus faible du fichier --
        il est ecrit ici pour ce qu'il vaut, pas plus. Ce qui TIENT
        reellement, c'est `AC6-1` : l'assiette mesuree sur le code.
        Celui-ci empeche seulement qu'on retire la consignation en gardant
        le comportement, ce qui rendrait la question invisible a nouveau.
        """
        doc = inspect.getdoc(getattr(AgentA3GLM, _FONCTION)) or ''
        self.assertIn(
            'b0ae396', doc,
            "la docstring ne cite pas le commit qui a ferme `a3/C6` : rien "
            "n'y dit que la condition posee est remplie")
        self.assertIn(
            'None', doc,
            "la docstring ne dit pas que le Gini est devenu `float | None` "
            "-- c'est ce qui empeche l'inclusion mecanique")


if __name__ == '__main__':
    unittest.main(verbosity=2)
