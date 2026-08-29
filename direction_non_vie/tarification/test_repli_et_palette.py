"""Controles positifs — lot 4.4 : le repli d'A3, et `charts/C4`.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
DEUX SUJETS, UNE SEULE PROPRIETE : *un instrument ne doit pas affirmer plus,
ni autre chose, que ce que le code porte.*

═══ LE REPLI D'A3 — UN AVEU QUI DESIGNAIT LE MAUVAIS COUPABLE ═══

Les trois calibrations (Poisson, Gamma, Tweedie) se replient sur un
<< intercept seul >> quand aucun modele n'a converge. CE REPLI ETAIT HORS DE
LEUR `try` : quand il echouait a son tour, une exception BRUTE de statsmodels
remontait jusqu'a l'actuaire.

⚠️⚠️ LE DECLENCHEUR N'EST PAS UNE DONNEE CORROMPUE. Mesure, sur la vraie
`_calibrer_poisson` :

    portefeuille normal                 -> REPOND
    aucune variable predictive fournie  -> REPOND       (le repli SAIN)
    PORTEFEUILLE SANS AUCUN SINISTRE    -> *** LEVE ***
    portefeuille VIDE (0 contrat)       -> *** LEVE ***
    un NaN dans la cible                -> *** LEVE ***

Un segment neuf, une branche a faible frequence : cas actuariels ordinaires.

⚠️⚠️ ET LE MESSAGE PUBLIE ETAIT CELUI-CI, mesure de bout en bout :

    << A3 a echoue : The first guess on the deviance function returned a nan.
       This could be a boundary problem and SHOULD BE REPORTED. >>

Un message INTERNE de statsmodels, qui invite l'actuaire a signaler un bogue
pour un portefeuille qui n'a simplement pas de sinistre.

⚠️⚠️ ET ON NE FABRIQUE PAS DE MODELE POUR AUTANT. A zero sinistre le maximum
de vraisemblance de l'intercept vaut log(0) : aucune valeur finie n'existe.
Publier << frequence = 0 >> donnerait une PRIME PURE NULLE, alors que la regle
de trois donne une borne haute de 3/n. Le contrat de `test_pipeline_agents`
est le bon -- on ne bricole pas un modele sur rien. Ce lot change le CONTENU
de l'aveu, pas sa nature.

⚠️ ET LE CONSTAT ETAIT PLUS LARGE QUE SON LIBELLE : releve par AST, les TROIS
calibrations portaient le meme repli nu (l.937 Poisson, l.1201 Gamma, l.1408
Tweedie). Corriger le seul Poisson aurait laisse deux jumeaux identiques.

═══ `charts/C4` — ET LE DEFAUT N'ETAIT PAS L'ESTHETIQUE ═══

Le constat disait << les quatre agents portent leur propre charte >>. Re-mesure
au code du 29/08, cette premisse est PERIMEE : les quatre partagent UNE seule
palette (3 fonds NAVY + 4 accents identiques). Et migrer vers la charte ne
changerait presque rien a l'oeil -- l'or des agents `#C9A84C` est a 1,09 de
contraste de l'or de la charte `#D4AF37`.

⚠️⚠️ LE VRAI DEFAUT EST SEMANTIQUE. Les listes decoratives contenaient
`couleur_rag('VERT'/'AMBRE'/'ROUGE')` -- LES COULEURS DE STATUT -- consommees
en cycle POSITIONNEL : `COULEURS_MODELES[idx % len(...)]`. Le modele numero 5
etait peint en ROUGE RAG parce qu'il etait cinquieme.

⚠️ ET DEUX DE MES PROPRES ACCUSATIONS ONT ETE RETIREES PAR LA MESURE :
  · j'ai accuse `#0F2E52 #1B3A5C #243F6A` d'etre sous le seuil WCAG. VERIFIE
    AU SITE : ce sont `NAVY / NAVY_L / NAVY_LL`, les FONDS. Le seuil 1.4.11 ne
    les concerne pas ;
  · j'ai accuse six paires d'etre << trop proches >> (contraste < 1,5).
    Mesure en deuteranopie : 0 paire sur 15 fusionne. Le contraste mesure la
    LUMINANCE, pas la couleur -- il sur-accusait.
Ce qui reste apres retrait est ce qui est vrai.
"""

from __future__ import annotations

import ast
import colorsys
import itertools
import logging
import pathlib
import unittest
import warnings
from typing import ClassVar

import numpy as np
import pandas as pd

from core.charts_tarif import FOND_SOMBRE, contraste, couleur_rag
from direction_non_vie.tarification.a3_glm.agent import (
    AgentA3GLM,
    CalibrationImpossible,
)

#: Le fond de TRACE des quatre agents (`plot_bgcolor = NAVY_L`), mesure au site.
FOND_TRACE = '#1B3A5C'

#: Le seuil WCAG 2.2 §1.4.11 pour un contenu non textuel.
SEUIL_WCAG_OBJET = 3.0

_RACINE = pathlib.Path(__file__).resolve().parent


def _agent() -> AgentA3GLM:
    return AgentA3GLM(models_path='/tmp', audit_path='/tmp', verbose=False)


def _portefeuille(n: int = 300, *, sinistres: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    d = pd.DataFrame({'x1': rng.normal(0, 1, n), 'x2': rng.normal(0, 1, n)})
    d['expo'] = 1.0
    d['nb'] = rng.poisson(0.3, n).astype(float) if sinistres else 0.0
    return d


class TestRepliRepondAuLieuDePlanter(unittest.TestCase):
    """Le repli << intercept seul >> ne laisse plus fuir statsmodels."""

    def setUp(self):
        self._log = logging.getLogger('actuaria.a3').level
        logging.getLogger('actuaria.a3').setLevel(logging.CRITICAL)
        self._w = warnings.catch_warnings()
        self._w.__enter__()
        warnings.simplefilter('ignore')

    def tearDown(self):
        self._w.__exit__(None, None, None)
        logging.getLogger('actuaria.a3').setLevel(self._log)

    def test_le_message_de_statsmodels_NE_REMONTE_PLUS(self):
        """⚠️⚠️ LE TEST QUI FERME LE CONSTAT — la phrase exacte, epinglee.

        « should be reported » invitait l'actuaire a signaler un bogue chez
        statsmodels pour un portefeuille sans sinistre.
        """
        with self.assertRaises(CalibrationImpossible) as ctx:
            _agent()._calibrer_poisson(
                _portefeuille(sinistres=False), _portefeuille(sinistres=False),
                ['x1', 'x2'], 'nb', 'expo')
        msg = str(ctx.exception)
        self.assertNotIn('should be reported', msg)
        self.assertNotIn('boundary', msg)
        print(f"    R-1 le message de statsmodels ne remonte plus | "
              f"{msg[:66]}…")

    def test_le_motif_NOMME_ce_qui_a_ete_OBSERVE(self):
        """⚠️ Un refus muet ne dit pas a l'actuaire ce qui manque.

        Meme discipline que `a3/C14` : on nomme les FAITS mesures, et on dit
        explicitement que la cause n'est pas etablie plutot que d'en designer
        une au hasard.
        """
        with self.assertRaises(CalibrationImpossible) as ctx:
            _agent()._calibrer_poisson(
                _portefeuille(sinistres=False), _portefeuille(sinistres=False),
                ['x1', 'x2'], 'nb', 'expo')
        msg = str(ctx.exception)
        for attendu in ('GLM Poisson', 'intercept seul', '300 observation(s)',
                        '0 strictement positive', 'log(0)',
                        "cause n'est pas etablie"):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, msg)
        print("    R-2 le motif nomme le modele, les faits, et la limite "
              "mathematique")

    def test_le_motif_DISCRIMINE_les_trois_causes(self):
        """⚠️⚠️ UN VERDICT QUI AGREGE NE PROUVE RIEN SUR UN CAS.

        Trois situations tres differentes -- pas de sinistre, donnee non
        finie, portefeuille vide -- doivent produire trois motifs DISTINCTS.
        Sinon le message ne vaut pas mieux que celui qu'il remplace.
        """
        vide = _portefeuille(4).iloc[:0].copy()
        avec_nan = _portefeuille()
        avec_nan.loc[3, 'nb'] = np.nan

        motifs = {}
        for nom, d in (('sans sinistre', _portefeuille(sinistres=False)),
                       ('valeur non finie', avec_nan),
                       ('portefeuille vide', vide)):
            with self.assertRaises(CalibrationImpossible) as ctx:
                _agent()._calibrer_poisson(d, d.copy(), ['x1', 'x2'],
                                           'nb', 'expo')
            motifs[nom] = str(ctx.exception)

        self.assertEqual(len(set(motifs.values())), 3,
                         'deux situations distinctes publient le meme motif')
        self.assertIn('non finie', motifs['valeur non finie'])
        self.assertIn('aucune observation', motifs['portefeuille vide'])
        self.assertNotIn('log(0)', motifs['valeur non finie'],
                         'la limite log(0) est annoncee hors de son cas')
        print("    R-3 trois situations, trois motifs distincts")

    def test_TEMOIN_le_repli_SAIN_repond_toujours(self):
        """⚠️⚠️ SECOND SENS — le correctif ne doit pas transformer en echec
        un repli qui MARCHAIT.

        Sans variable predictive mais avec des donnees saines, l'intercept
        seul est le bon modele : il s'ajuste, et A3 continue.
        """
        d = _portefeuille()
        res = _agent()._calibrer_poisson(d, d.copy(), [], 'nb', 'expo')
        self.assertEqual(res['metriques']['nb_vars_retenues'], 0)
        self.assertGreater(res['metriques']['frequence_pred'], 0.0)
        self.assertIsNotNone(res['modele'])
        print(f"    R-4 temoin : repli sain toujours ajuste | "
              f"frequence_pred = {res['metriques']['frequence_pred']}")

    def test_LES_TROIS_calibrations_sont_protegees(self):
        """⚠️⚠️ L'ASSIETTE DU CONSTAT, RELEVEE PAR AST.

        Le constat nommait le Poisson ; les TROIS portaient le meme repli nu.
        Ce controle plante la violation : il tombe si un `sm.GLM(...).fit()`
        reapparait hors de tout `try`.
        """
        src = (_RACINE / 'a3_glm' / 'agent.py').read_text(encoding='utf-8')
        arbre = ast.parse(src)

        nus: list[tuple[int, str]] = []

        class Visiteur(ast.NodeVisitor):
            def __init__(self):
                self.pile: list[int] = []
                self.fn = '?'

            def visit_FunctionDef(self, n):
                prec, self.fn = self.fn, n.name
                self.generic_visit(n)
                self.fn = prec

            def visit_Try(self, n):
                self.pile.append(n.lineno)
                self.generic_visit(n)
                self.pile.pop()

            def visit_Call(self, n):
                f = n.func
                if isinstance(f, ast.Attribute) and f.attr == 'fit':
                    base = f.value
                    if (isinstance(base, ast.Call)
                            and isinstance(base.func, ast.Attribute)
                            and base.func.attr == 'GLM'
                            and not self.pile):
                        nus.append((n.lineno, self.fn))
                self.generic_visit(n)

        Visiteur().visit(arbre)
        self.assertEqual(
            nus, [],
            f'{len(nus)} ajustement(s) GLM hors de tout try : {nus} — '
            f'le repli redevient une fuite de statsmodels')
        print("    R-5 les 3 calibrations protegees, 0 GLM.fit hors try (AST)")


class TestPaletteSansCouleurDeStatut(unittest.TestCase):
    """`charts/C4` — une couleur de statut ne decore pas."""

    #: Les deux cycles, releves au site.
    CYCLES: ClassVar[dict[str, tuple[str, str]]] = {
        'a4_ml': ('a4_ml/agent.py', 'COULEURS_MODELES'),
        'a6_comparaison': ('a6_comparaison/agent.py', 'COULEURS'),
    }

    def _cycle(self, chemin: str, nom: str) -> list[str]:
        """Les couleurs du cycle, RESOLUES — variables locales comprises.

        ⚠️ Un relevé par symbole verrait `[OR, BLEU, "#C89BD4", ...]` et
        conclurait a deux couleurs. *On resout vers la valeur reelle.*
        """
        src = (_RACINE / chemin).read_text(encoding='utf-8')
        arbre = ast.parse(src)
        constantes: dict[str, str] = {}
        cycle: list[str] | None = None
        for n in ast.walk(arbre):
            if not isinstance(n, ast.Assign) or len(n.targets) != 1:
                continue
            cible = n.targets[0]
            if not isinstance(cible, ast.Name):
                continue
            if isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                if n.value.value.startswith('#'):
                    constantes[cible.id] = n.value.value
            elif cible.id == nom and isinstance(n.value, ast.List):
                cycle = []
                for e in n.value.elts:
                    if isinstance(e, ast.Constant):
                        cycle.append(str(e.value))
                    elif isinstance(e, ast.Name):
                        cycle.append(constantes.get(e.id, f'<{e.id}>'))
                    else:
                        cycle.append('<expr>')
        self.assertIsNotNone(cycle, f'{nom} introuvable dans {chemin}')
        for c in cycle:
            self.assertTrue(c.startswith('#'),
                            f'{nom} contient une valeur non resolue : {c}')
        return cycle

    def test_AUCUNE_couleur_de_statut_dans_un_cycle_decoratif(self):
        """⚠️⚠️ LE TEST QUI FERME LE CONSTAT.

        `COULEURS[idx % len(COULEURS)]` est un cycle POSITIONNEL : la couleur
        y designe un rang, pas une qualite. Une couleur de statut y devient un
        faux signal.
        """
        rag = {couleur_rag(s, FOND_SOMBRE).upper()
               for s in ('VERT', 'AMBRE', 'ROUGE')}
        for agent, (chemin, nom) in self.CYCLES.items():
            with self.subTest(agent=agent):
                fautives = [c for c in self._cycle(chemin, nom)
                            if c.upper() in rag]
                self.assertEqual(
                    fautives, [],
                    f'{agent} peint un rang avec une couleur de STATUT : '
                    f'{fautives}')
        print(f"    C4-1 aucun des 2 cycles ne contient un couleur_rag "
              f"(RAG = {sorted(rag)})")

    def test_TOUT_le_cycle_passe_le_seuil_WCAG_1_4_11(self):
        """⚠️ Sur le fond de trace REEL `#1B3A5C`, mesure au site -- pas sur
        le fond de page. `#9B59B6` y valait 2,49, sous le seuil de 3:1.
        """
        for agent, (chemin, nom) in self.CYCLES.items():
            with self.subTest(agent=agent):
                mesures = {c: contraste(c, FOND_TRACE)
                           for c in self._cycle(chemin, nom)}
                sous = {c: round(v, 2) for c, v in mesures.items()
                        if v < SEUIL_WCAG_OBJET}
                self.assertEqual(
                    sous, {},
                    f'{agent} : couleur(s) sous {SEUIL_WCAG_OBJET}:1 sur '
                    f'{FOND_TRACE} — {sous}')
                print(f"    C4-2 {agent:16s} min {min(mesures.values()):.2f} "
                      f"sur {len(mesures)} couleurs (seuil {SEUIL_WCAG_OBJET})")

    def test_le_cycle_reste_LISIBLE_en_deuteranopie(self):
        """⚠️⚠️ LA LECON DE `charts/C9` ET `charts/C10`, APPLIQUEE ICI.

        La couleur seule ne suffit que si les couleurs se distinguent. On
        simule la deuteranopie (Vienot/Brettel) et on exige que la paire la
        plus proche reste au-dessus du seuil pratique de 40 en distance L1.

        ⚠️ ET C'EST CE CRITERE QUI A REFUTE MES DEUX PREMIERS CYCLES :
        mauve/cyan a 20, puis mauve/ardoise a 17. *Une palette se mesure.*
        """
        def deuteranope(h: str) -> tuple[float, float, float]:
            r, g, b = (int(h.lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4))
            lin = (lambda c: c / 12.92 if c <= 0.04045
                   else ((c + 0.055) / 1.055) ** 2.4)
            r, g, b = lin(r), lin(g), lin(b)
            grand_l = 17.8824 * r + 43.5161 * g + 4.11935 * b
            petit_s = 0.0299566 * r + 0.184309 * g + 1.46709 * b
            m2 = 0.494207 * grand_l + 1.24827 * petit_s
            canaux = (0.080944 * grand_l - 0.130504 * m2 + 0.116721 * petit_s,
                      -0.010248 * grand_l + 0.054019 * m2 - 0.113614 * petit_s,
                      -0.000365 * grand_l - 0.004122 * m2 + 0.693513 * petit_s)
            delin = (lambda c: 12.92 * c if c <= 0.0031308
                     else 1.055 * (max(c, 0) ** (1 / 2.4)) - 0.055)
            return tuple(min(255, max(0, round(delin(x) * 255))) for x in canaux)

        for agent, (chemin, nom) in self.CYCLES.items():
            with self.subTest(agent=agent):
                cycle = self._cycle(chemin, nom)
                pires = sorted(
                    (sum(abs(x - y) for x, y in
                         zip(deuteranope(a), deuteranope(b))), a, b)
                    for a, b in itertools.combinations(cycle, 2))
                self.assertGreaterEqual(
                    pires[0][0], 40,
                    f'{agent} : {pires[0][1]} et {pires[0][2]} fusionnent en '
                    f'deuteranopie (L1 = {pires[0][0]})')
                print(f"    C4-3 {agent:16s} paire la plus proche L1 = "
                      f"{pires[0][0]} (seuil 40)")

    def test_aucune_TEINTE_de_statut_hors_l_or_maison(self):
        """⚠️ Une couleur peut n'etre AUCUN `couleur_rag` et rester dans la
        famille rouge/ambre ou verte -- et donc se lire comme un statut.

        ⚠️⚠️ L'OR `#C9A84C` (teinte 44 deg) EST DANS LA FAMILLE AMBRE, et il
        RESTE. C'est l'accent maison du rapport, il n'a jamais designe un
        statut, et il porte une information en A6 (le modele de PRODUCTION).
        *On declare l'exception, on ne la cache pas dans un seuil.*
        """
        def teinte(h: str) -> float:
            r, g, b = (int(h.lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4))
            return colorsys.rgb_to_hsv(r, g, b)[0] * 360

        for agent, (chemin, nom) in self.CYCLES.items():
            with self.subTest(agent=agent):
                suspectes = [
                    c for c in self._cycle(chemin, nom)
                    if c.upper() != '#C9A84C'
                    and (teinte(c) < 50 or teinte(c) > 345
                         or 90 <= teinte(c) <= 175)]
                self.assertEqual(
                    suspectes, [],
                    f'{agent} : teinte(s) dans une famille de statut — '
                    f'{[(c, round(teinte(c), 1)) for c in suspectes]}')
        print("    C4-4 aucune teinte de statut hors l'or maison (44 deg, "
              "declare)")

    def test_les_deux_agents_partagent_le_MEME_cycle(self):
        """⚠️ Le constat reprochait << quatre chartes >>. Le correctif ne doit
        pas en creer deux de plus : A6 est A4 plus le blanc.
        """
        a4 = self._cycle(*self.CYCLES['a4_ml'])
        a6 = self._cycle(*self.CYCLES['a6_comparaison'])
        self.assertEqual(a4, a6[:len(a4)],
                         'les deux cycles ont diverge')
        print(f"    C4-5 un seul cycle : a4 = {len(a4)} couleurs, "
              f"a6 = les memes + {len(a6) - len(a4)}")


if __name__ == '__main__':
    unittest.main()
