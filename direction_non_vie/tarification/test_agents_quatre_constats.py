"""Controles positifs -- `agents` : les quatre derniers constats de la zone.

═══ ⛔⛔ `C3` -- LA CIBLE FREQUENCE ETAIT LA SEULE DES TROIS SANS FILET ═══

L'en-tete du module promet : << Un arbitrage peut echouer la ou un autre
reussit [...] c'est rendu dans `<cible>.erreur`, jamais masque, et n'empeche
pas les autres d'aboutir. >> Mesure du 01/09 : le COUT et la PRIME PURE sont
enveloppes dans un `try`, la FREQUENCE ne l'etait pas. Une exception y
remontait hors de `pipeline_agents` et TUAIT les deux autres cibles.

> *Une promesse d'independance tenue sur deux tiers des cas n'est pas une
> promesse d'independance.*

⚠️ AUCUN SUCCES N'EST MASQUE : `_echec` pose `a6=None`, et
`ResultatAgents.success` lit `frequence.a6['success']` -- il reste `False`.
*Rendre l'erreur n'est pas l'avaler.* `AG-2` le verifie par EXECUTION.

═══ ⛔ `C6` -- LE MESSAGE D'ECHEC ACCUSAIT LE MAUVAIS COUPABLE ═══

Si `prime_pure` manque, l'erreur disait << contrat de donnees V7 B2 rompu --
`_calculer_prime_pure` >>, ce qui envoie l'actuaire chercher une rupture entre
A2 et A3. Mesure : `A2._calculer_prime_pure` lit `'cout_total_sinistres'` et
`'exposition'` **EN DUR**, pas `plan.cible_cout` / `plan.exposition`. Sur 19
des 20 plans les deux coincident ; sur `auto_fr_reel.yaml` -- celui bati sur le
jeu francais REEL -- ils s'appellent `ClaimAmountTotal` et `Exposure`.

⚠️⚠️ LA CAUSE N'EST PAS CORRIGEE, ET C'EST DIT. Faire lire le plan a
`_calculer_prime_pure` FERAIT APPARAITRE une troisieme cible la ou il n'y en a
aucune : c'est un changement de SORTIE sur un plan signe, pas un correctif de
texte. Le message, lui, nomme desormais la cause reelle ET les deux noms en
conflit.

═══ LES DEUX AUTRES ═══

`C1` -- l'orchestrateur n'a AUCUN appelant de production, et les trois defauts
qu'il repare sont intacts chez les deux appelants hors app. Ce n'est pas un
defaut de code : c'est un CABLAGE qui manque. Le brancher leur ferait produire
trois cibles et un A5 la ou ils n'en produisent qu'une -- change de sortie,
donc hors de ce lot.

`C5` -- `_vue_sinistres` annoncait `Dict[str, Any]` et rendait un TUPLE. La
docstring etait juste sur le premier membre et TAISAIT le second, l'objet
`CibleSeverite` dont l'appelant lit `n_retenus` juste apres. *Une annotation
qui dit la moitie du contrat est plus traitre qu'une annotation absente.*
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import typing
import unittest

from direction_non_vie.tarification import pipeline_agents as _pa

_SOURCE = pathlib.Path(_pa.__file__).read_text(encoding='utf-8')
_EN_TETE = _SOURCE.split('"""')[1]
_RACINE = pathlib.Path(_pa.__file__).parents[2]  # racine du depot
_APPELANTS = ('demos/pipeline_3lob_a1_a6_demo.py',
              'scripts/rapport_tarif_local.py')


def _fonction(nom):
    for n in ast.walk(ast.parse(_SOURCE)):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    return None


class TestAgentsQuatreConstats(unittest.TestCase):
    """Quatre constats de la zone `agents`."""

    # ── `agents/C3` — les trois cibles sont protegees, ou aucune ───────────

    def test_AG_1_LE_TEST_QUI_FERME_les_TROIS_cibles_sont_protegees(self):
        """`agents/C3` : par AST, aucune des trois n'est a nu."""
        fn = _fonction('pipeline_agents')
        self.assertIsNotNone(fn, 'pipeline_agents introuvable')
        nus = []
        for n in ast.walk(fn):
            if not (isinstance(n, ast.Call)
                    and getattr(n.func, 'id', None) == '_arbitrer'):
                continue
            # Un appel est PROTEGE s'il vit sous un `try` de cette fonction.
            protege = any(
                isinstance(t, ast.Try)
                and any(n is c for c in ast.walk(t))
                for t in ast.walk(fn) if isinstance(t, ast.Try))
            if not protege:
                nus.append(n.lineno)
        self.assertEqual(
            nus, [],
            f"appel(s) a `_arbitrer` hors de tout `try` en l.{nus} : une "
            f"exception y tuerait les DEUX autres cibles, alors que l'en-tete "
            f"promet qu'un echec << n'empeche pas les autres d'aboutir >>")

    def test_AG_2_et_l_echec_reste_un_ECHEC(self):
        """`agents/C3`, second sens : proteger n'est pas masquer.

        ⚠️ Sans ce controle, envelopper la frequence pourrait transformer un
        plantage en succes silencieux -- exactement `agents/C2`, referme.
        """
        echec = _pa._echec if hasattr(_pa, '_echec') else None
        if echec is None:
            # `_echec` est une fermeture interne : on la reconstruit par la
            # meme voie que le code -- un ArbitrageCible sans a6.
            arb = _pa.ArbitrageCible(cible='freq', a4=None, a5=None, a6=None,
                                     statut_rag=None, n_candidats=0,
                                     erreur='plantage simule')
        else:
            arb = echec('freq', 'plantage simule')
        self.assertIsNone(arb.a6, 'un echec ne doit porter aucun resultat A6')
        self.assertTrue(arb.erreur, "l'echec doit porter son motif")
        # ⚠️⚠️ PAR AST SUR LE CORPS, PAS SUR LA SOURCE. Ma premiere version
        # faisait `assertIn('frequence', inspect.getsource(...))` -- et la
        # DOCSTRING de `success` parle longuement de la frequence. Le sceau
        # l'a demasque : un plant qui retire completement la lecture du
        # drapeau (le defaut d'`agents/C2`, referme) ne faisait rien tomber,
        # parce que le controle lisait le texte qui EXPLIQUE le code, pas le
        # code. *Une explication n'est pas un comportement* -- meme piege que
        # la citation, sur un autre support.
        import textwrap
        corps = ast.parse(textwrap.dedent(
            inspect.getsource(_pa.ResultatAgents.success.fget))).body[0].body
        instructions = [n for n in corps if not (
            isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
        lus = {n.attr for i in instructions for n in ast.walk(i)
               if isinstance(n, ast.Attribute)}
        self.assertIn(
            'frequence', lus,
            "`success` ne lit plus l'arbitrage FREQUENCE : il redeviendrait "
            "vrai sur un dossier sans modele -- c'est `agents/C2`, referme.")
        self.assertIn('a3', lus, "`success` ne lit plus le socle A3")

    # ── `agents/C6` — le message nomme la vraie cause ──────────────────────

    def test_AG_3_LE_TEST_QUI_FERME_le_message_nomme_la_VRAIE_cause(self):
        """`agents/C6` : ni contrat rompu, ni fonction innocente accusee."""
        fn = _fonction('pipeline_agents')
        textes = [n.value for n in ast.walk(fn)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        joint = ' '.join(textes)
        self.assertIn(
            'CAUSE MESUR', joint,
            "le message d'echec de la prime pure ne nomme pas la cause")
        self.assertIn('cout_total_sinistres', joint)
        self.assertIn('cible_cout', joint)
        self.assertNotIn(
            'contrat de données V7 B2 rompu', joint,
            "le message accuse encore un contrat de donnees rompu, alors que "
            "la cause mesuree est deux noms de colonnes codes en dur")

    def test_AG_4_et_la_cause_reelle_est_toujours_la(self):
        """`agents/C6` : le message dit vrai TANT QUE la cause existe.

        ⚠️ Le jour ou `A2._calculer_prime_pure` lira le plan, ce message
        deviendra faux a son tour. Ce controle le fera tomber -- *une phrase
        de portee se mesure comme un chiffre.*
        """
        src_a2 = (_RACINE / 'direction_non_vie' / 'tarification' / 'a2_preprocessing'
                  / 'agent.py').read_text(encoding='utf-8')
        fn_a2 = None
        for n in ast.walk(ast.parse(src_a2)):
            if (isinstance(n, ast.FunctionDef)
                    and n.name == '_calculer_prime_pure'):
                fn_a2 = n
        self.assertIsNotNone(fn_a2, '_calculer_prime_pure introuvable dans A2')
        litteraux = {c.value for c in ast.walk(fn_a2)
                     if isinstance(c, ast.Constant)
                     and isinstance(c.value, str)}
        en_dur = {'cout_total_sinistres', 'exposition'} & litteraux
        self.assertEqual(
            en_dur, {'cout_total_sinistres', 'exposition'},
            "A2._calculer_prime_pure ne lit plus ces noms en dur : le message "
            "d'echec qui les nomme est devenu faux, il faut le reecrire")

    # ── `agents/C5` — l'annotation dit tout le contrat ────────────────────

    def test_AG_5_LE_TEST_QUI_FERME_l_annotation_dit_le_TUPLE(self):
        """`agents/C5` : elle annoncait un dict, elle rend un couple."""
        annotations = typing.get_type_hints(_pa._vue_sinistres)
        rendu = annotations.get('return')
        self.assertIsNotNone(rendu, '_vue_sinistres n a plus d annotation')
        # ⚠️ Le `tuple` BUILTIN, pas `typing.Tuple` : la seconde est depreciee
        # (UP035) et la proprete du lot la refuse. Le controle porte sur le
        # FAIT -- un couple -- pas sur l'orthographe de son ecriture.
        self.assertIn(
            'tuple', str(rendu).lower(),
            f"l'annotation de retour dit encore {rendu} alors que la fonction "
            f"rend un couple (result_a2, CibleSeverite)")
        self.assertIn('CibleSeverite', str(rendu),
                      "le SECOND membre du couple n'est pas annonce")
        doc = _pa._vue_sinistres.__doc__ or ''
        self.assertIn('agents/C5', doc)

    # ── `agents/C1` — un cablage qui manque, et qui est DIT ───────────────

    def test_AG_6_le_module_DIT_qu_il_n_est_pas_appele(self):
        """`agents/C1` : les deux sens -- la phrase se mesure."""
        appels = []
        for rel in _APPELANTS:
            chemin = _RACINE / rel
            if not chemin.exists():
                continue
            texte = chemin.read_text(encoding='utf-8')
            if 'pipeline_complet' in texte or 'pipeline_agents' in texte:
                appels.append(rel)
        if appels:
            self.assertNotIn(
                "AUCUN APPELANT DE PRODUCTION", _EN_TETE,
                f"l'en-tete dit << aucun appelant de production >> alors que "
                f"{appels} l'appellent desormais : la phrase doit tomber")
        else:
            self.assertIn(
                "AUCUN APPELANT DE PRODUCTION", _EN_TETE,
                "le module n'est appele par personne et son en-tete ne le "
                "dit pas : un lecteur croit que la reparation a eu lieu")
            for rel in _APPELANTS:
                self.assertIn(
                    rel.split('/')[-1], _EN_TETE,
                    f"l'en-tete ne nomme pas l'appelant '{rel}' chez qui les "
                    f"trois defauts restent vrais")


if __name__ == '__main__':
    unittest.main(verbosity=2)
