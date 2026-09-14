r"""
==============================================================================
  L'HISTORIQUE DE L'EMPREINTE OPPOSABLE NE SAUTE AUCUNE GENERATION
==============================================================================

⚠️⚠️ `PT-D1` -- LE BLOC DE COMMENTAIRES DOCUMENTAIT CHAQUE BUMP DEPUIS
`s1`, ET IL EN MANQUAIT UN. Releve du 14/09/2026 sur les couples ecrits :

    1->2   2->3   3->4   4->5   [TROU]   6->7   7->8   8->9   9->10

Mesure par `git log -S` : le commit `4cb2abc` (02/09/2026) porte
`EMPREINTE_SCHEMA` de 5 a 6 et fait entrer `valeurs_absentes` dans le
payload -- verifie present dans `empreinte()` aujourd'hui -- SANS note de
bump et sans la mesure << aucune empreinte s5: persistee >>.

*Un contestataire d'une empreinte `s5:` ou `s6:` ne pouvait pas savoir
ce qui avait change entre les deux, donc ne pouvait pas juger si l'ecart
qu'il observe vient du plan ou de la structure.* C'est le seul defaut de
la liste du 1er audit qui porte sur l'OPPOSABILITE plutot que sur un
chiffre.

⚠️⚠️ MA PREMIERE MESURE N'AVAIT RIEN TROUVE, et la cause est instructive :
ma regex cherchait `s?(\d+)\s*(->|a|vers)\s*s?(\d+)` alors que le bloc
ecrit les couples avec des BACKTICKS -- `` `4` -> `5` ``. *Un seul
caractere cachait le site entier.* C'est la lecture du bloc, a l'oeil,
qui a tranche.

⚠️ UNE SUITE DOCUMENTEE N'EST PAS UNE SUITE TENUE -- le depot a deja paye
cette lecon le 03/09/2026. Celle-ci est tenue PAR CONSTRUCTION : la
verification vit AU NIVEAU DU MODULE, donc un bump sans note (ou une note
sans bump) fait echouer l'IMPORT, pas un test qu'on pourrait oublier de
lancer.

⚠️ ET LA MESURE MANQUANTE DE `s5` EST DITE, PAS FABRIQUEE. Les huit
autres notes portent << aucune empreinte sN: persistee, mesure AVANT le
bump >>. Pour `s5`, cette mesure n'a pas eu lieu et ne peut plus l'etre :
le bump est passe. *Le dire vaut mieux que l'affirmer.* `HS-3` verifie
que la note l'avoue.
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

from core.plan_tarifaire import (
    EMPREINTE_SCHEMA,
    HISTORIQUE_SCHEMA,
    PlanTarifaire,
)

_SOURCE = _RACINE / 'core' / 'plan_tarifaire.py'
_PLANS = _RACINE / 'plans'
#: La generation dont la mesure de persistance N'A PAS eu lieu.
_GENERATION_SANS_MESURE = 6


class TestHistoriqueDeLEmpreinte(unittest.TestCase):

    # ── HS-1 ─────────────────────────────────────────────────────────────
    def test_HS1_chaque_generation_porte_sa_note_et_reciproquement(self):
        """⚠️ LES DEUX SENS. Une generation sans note laisse un
        contestataire sans explication ; une note sans generation decrit un
        bump qui n'a pas eu lieu."""
        attendues = set(range(2, EMPREINTE_SCHEMA + 1))
        sans_note = sorted(attendues - set(HISTORIQUE_SCHEMA))
        sans_bump = sorted(set(HISTORIQUE_SCHEMA) - attendues)
        self.assertEqual(
            (sans_note, sans_bump), ([], []),
            f"l'historique ne couvre pas EMPREINTE_SCHEMA={EMPREINTE_SCHEMA} :"
            f" sans note {sans_note}, sans bump {sans_bump}")
        print(f"    HS-1 SCEAU : {len(HISTORIQUE_SCHEMA)} note(s) pour les "
              f"generations 2..{EMPREINTE_SCHEMA}, 0 trou, 0 surplus")

    # ── HS-2 ─────────────────────────────────────────────────────────────
    def test_HS2_la_verification_vit_AU_NIVEAU_DU_MODULE(self):
        """⚠️⚠️ C'EST TOUT L'INTERET : un lot qui bumpe sans ecrire sa note
        ne passe pas la PORTE. Une verification rangee dans une fonction, ou
        dans ce seul test, serait une suite DOCUMENTEE de plus -- et le
        depot a deja perdu huit jours sur cette confusion."""
        arbre = ast.parse(_SOURCE.read_bytes().decode('utf-8'))
        au_module = [
            n.lineno for n in arbre.body
            if isinstance(n, ast.If)
            and any(isinstance(x, ast.Raise) for x in ast.walk(n))
            and 'HISTORIQUE_SCHEMA' in ast.unparse(n)]
        self.assertTrue(
            au_module,
            "aucune verification de `HISTORIQUE_SCHEMA` ne leve AU NIVEAU DU "
            "MODULE : l'historique redevient un commentaire, et un bump sans "
            "note passera la porte sans rien dire.")
        print(f"    HS-2 SCEAU : verification a l'import, l.{au_module}")

    # ── HS-3 ─────────────────────────────────────────────────────────────
    def test_HS3_la_note_manquante_AVOUE_sa_mesure_non_faite(self):
        """⚠️⚠️ ON NE FABRIQUE PAS RETROACTIVEMENT UNE VERIFICATION QUI N'A
        PAS EU LIEU. Les huit autres notes portent << mesure AVANT le
        bump >> ; celle-ci ne le peut pas, et elle le DIT."""
        note = HISTORIQUE_SCHEMA[_GENERATION_SANS_MESURE]
        for attendu in ('4cb2abc', "N'A PAS", 'valeurs_absentes'):
            self.assertIn(
                attendu, note,
                f"la note de la generation {_GENERATION_SANS_MESURE} ne dit "
                f"pas {attendu!r} : {note[:90]!r}")
        #: et les autres notes, elles, portent bien leur mesure
        sans_mesure = [n for n, t in HISTORIQUE_SCHEMA.items()
                       if n != _GENERATION_SANS_MESURE
                       and 'persist' not in t]
        self.assertLessEqual(
            len(sans_mesure), 3,
            f"trop de notes ne disent rien de la persistance des empreintes "
            f"anterieures : {sans_mesure}")
        print(f"    HS-3 SCEAU : la note {_GENERATION_SANS_MESURE} nomme son "
              f"commit et AVOUE sa mesure non faite ; {len(sans_mesure)} "
              f"autre(s) sans mention de persistance")

    # ── HS-4 ─────────────────────────────────────────────────────────────
    def test_HS4_les_20_plans_conservent_leur_empreinte(self):
        """La contre-epreuve : ce lot ne touche AUCUN prix, AUCUNE
        structure. Les empreintes signees ne deviennent pas
        `SCHEMA_DIFFERENT`.

        ⚠️⚠️ LE NUMERO NE S'EPINGLE PAS ICI, ET C'EST UN SCEAU DU DEPOT QUI
        ME L'A APPRIS. Ma premiere version ecrivait
        `assertEqual(EMPREINTE_SCHEMA, 10)` ; `PL-8` a mordu, et il a
        raison : *un numero de schema epingle ailleurs que dans le golden
        fait de chaque bump une edition a DEUX sites, sans la discipline du
        sceau.* Le seul endroit qui doit connaitre le numero est le golden
        de `test_plan_invariants`, ou constante et empreinte bougent
        ENSEMBLE. On garde donc la forme DURABLE que `PL-8` nomme
        lui-meme -- le numero ne recule jamais -- et le prefixe se DERIVE
        de la constante au lieu d'etre recopie."""
        self.assertGreaterEqual(
            EMPREINTE_SCHEMA, 10,
            "EMPREINTE_SCHEMA a RECULE : une empreinte signee sous un "
            "schema plus recent deviendrait incomparable")
        prefixes, lus = set(), 0
        for chemin in sorted(_PLANS.glob('*.yaml')):
            plan = PlanTarifaire.depuis_yaml(str(chemin))
            prefixes.add(plan.empreinte().split(':')[0])
            lus += 1
        self.assertGreaterEqual(
            lus, 20, f"seuls {lus} plans lus : l'assiette a change")
        self.assertEqual(
            prefixes, {f's{EMPREINTE_SCHEMA}'},
            f"les plans ne portent pas tous le prefixe attendu : {prefixes}")
        print(f"    HS-4 SCEAU : {lus} plans, prefixe unique "
              f"{sorted(prefixes)} DERIVE de EMPREINTE_SCHEMA="
              f"{EMPREINTE_SCHEMA} (jamais epingle en dur -- `PL-8`)")

    # ── HS-5 ─────────────────────────────────────────────────────────────
    def test_HS5_chaque_note_NOMME_ce_qui_entre_dans_le_payload(self):
        """⚠️ UNE TABLE DECORATIVE NE VAUT PAS MIEUX QU'UN COMMENTAIRE. Une
        note doit nommer le CHAMP, sinon elle n'explique pas l'ecart qu'un
        contestataire observe."""
        muettes = [n for n, t in HISTORIQUE_SCHEMA.items()
                   if '`' not in t or len(t) < 40]
        self.assertEqual(
            muettes, [],
            f"{muettes} ne nomme(nt) aucun champ entre backticks, ou tient "
            f"en moins de 40 caracteres : la note n'explique rien.")
        print(f"    HS-5 SCEAU : {len(HISTORIQUE_SCHEMA)} notes, toutes "
              f"nomment un champ (mediane "
              f"{sorted(len(t) for t in HISTORIQUE_SCHEMA.values())[4]} car.)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
