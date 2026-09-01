"""Controles positifs -- `plan` : les cinq derniers constats de la zone.

═══ ⛔⛔ `C6` -- DEUX FORMES DE DICT, ET LE MELANGE ECHOUAIT VERS LE SILENCE ═══

Dans le MEME fichier, deux dictionnaires disent << plan ampute >> :

    verifier_completude_plan          rend  {plan, n_attendues, n_presentes,
                                             colonnes_manquantes, ampute}
    synthese_colonnes_plan_manquantes lit   {plan, colonnes_non_produites,
                                             facteurs_absents}

**Aucune cle en commun hors `plan`.** Mesure du 01/09 : passer le PREMIER a la
seconde rend `None`, c'est-a-dire << rien a signaler >> -- sur un plan
massivement ampute.

> *Un << rien a signaler >> silencieux sur un modele ampute est exactement ce
> que ce libelle existe pour empecher.*

Les deux formes ont chacune leurs producteurs et leurs lecteurs ; les fondre
casserait `alerte_modele_ampute` et `plafonner_statut_si_ampute`. Ce qui est
corrige est le SILENCE : une forme non reconnue LEVE, et le message nomme les
deux structures.

═══ ⛔⛔ `C8` -- L'EMPREINTE ETAIT AVEUGLE A LA JUSTIFICATION ═══

Deux plans identiques dont le `commentaire` d'un facteur -- **la justification
ecrite par l'actuaire** -- differe portaient la MEME empreinte, et l'audit
trail les declarait IDENTIQUES. Le champ entre dans le payload : `s3` -> `s4`.

⚠️ C'est le SEUL champ hache qui ne change pas un prix. Il y est parce que
l'empreinte scelle **le document SIGNE**, pas seulement le calcul. Arbitrage
deja rendu : << VERSIONNER, ne pas omettre >>.

⚠️ CE QUE LE BUMP COUTE, ET C'EST VOULU : toute empreinte archivee sous `s3`
cesse de correspondre -- etat PREVU par `comparer_empreinte`. `PL-5` refait la
mesure qu'un bump exige : **aucune empreinte `sN:` anterieure persistee**.

═══ LES TROIS AUTRES ═══

| constat | ce qui etait annonce | ce qui est |
|---|---|---|
| `C4` | `config_encodage()` << ce que A2 consomme >> | 0 appelant ; A2 lit `f.encodage` |
| `C10` | quatre listes remplacees | trois supprimees, **la quatrieme existe** |
| `C11` | `colonnes_obligatoires()` publique | 0 appelant hors du module |

⚠️ `C10` EST LE PLUS TRAITRE DES TROIS. L'en-tete rangeait sous une seule
fleche trois etats differents : SUPPRIMEE, SUPPRIMEE, SUPPRIMEE... et
`FACTEURS_TARIFAIRES_AUTORISES`, qui vit toujours comme repli de
`construire_matrice_x`. *La liste la plus dangereuse est celle qu'on croit
supprimee.* `PL-6` DERIVE l'etat des quatre au lieu de le relire.
"""

from __future__ import annotations

import ast
import glob
import os
import pathlib
import unittest

import core.plan_tarifaire as _pmod
from core.plan_tarifaire import (
    EMPREINTE_SCHEMA,
    PlanTarifaire,
    synthese_colonnes_plan_manquantes,
    verifier_completude_plan,
)

_SOURCE = pathlib.Path(_pmod.__file__).read_text(encoding='utf-8')
_RACINE = pathlib.Path(_pmod.__file__).parents[1]
_EN_TETE = _SOURCE.split('"""')[1]

_PLAN_MINIMAL = {
    'lob': 'ctrl', 'version': '1.0', 'auteur': 'controle',
    'exposition': 'expo', 'cible_frequence': 'nb_sin', 'cible_cout': 'cout',
    'facteurs': [{'nom': 'age', 'type': 'continu'}],
}


def _fichiers_python():
    """Tout le depot, hors archive d'audit et environnements."""
    for chemin in glob.glob(str(_RACINE / '**' / '*.py'), recursive=True):
        if 'audit_2026_08' in chemin or '.venv' in chemin:
            continue
        yield chemin


class TestPlanCinqConstats(unittest.TestCase):
    """Cinq constats de la zone `plan`."""

    # ── `plan/C4` — une methode qui affirmait etre consommee ─────────────────

    def test_PL_1_config_encodage_n_existe_plus_et_A2_lit_le_facteur(self):
        """`plan/C4` : 0 appelant, et une docstring qui affirmait le contraire."""
        self.assertFalse(
            hasattr(PlanTarifaire, 'config_encodage'),
            "`config_encodage` est de retour : elle avait 0 appelant en "
            "production ET en test, et affirmait << ce que A2 consomme >>.")
        # Le FAIT derriere le retrait : A2 lit l'encodage SUR LE FACTEUR.
        src_a2 = (_RACINE / 'direction_non_vie' / 'tarification'
                  / 'a2_preprocessing' / 'agent.py').read_text(encoding='utf-8')
        sites = [n.lineno for n in ast.walk(ast.parse(src_a2))
                 if isinstance(n, ast.Attribute) and n.attr == 'encodage']
        self.assertGreaterEqual(
            len(sites), 3,
            f"A2 ne lit plus l'encodage sur les facteurs du plan ({sites}) : "
            f"la raison du retrait de `config_encodage` ne tient plus")

    # ── `plan/C6` — le melange des deux formes ──────────────────────────────

    def test_PL_2_LE_TEST_QUI_FERME_la_forme_etrangere_LEVE(self):
        """`plan/C6` : elle rendait `None` sur un plan massivement ampute."""
        plan = PlanTarifaire.depuis_dict(dict(_PLAN_MINIMAL))
        # Un fichier qui ne porte AUCUNE colonne declaree : le cas le plus
        # ampute qui soit -- c'est bien la que le silence etait le pire.
        rapport = verifier_completude_plan(plan, ['sans_rapport'])
        self.assertTrue(rapport['ampute'],
                        'la premisse est fausse : ce plan n est pas ampute')
        with self.assertRaises(TypeError) as ctx:
            synthese_colonnes_plan_manquantes(rapport)
        msg = str(ctx.exception)
        for attendu in ('verifier_completude_plan', 'colonnes_manquantes',
                        'colonnes_non_produites'):
            self.assertIn(
                attendu, msg,
                f"le message ne nomme pas '{attendu}' : celui qui tombe "
                f"dessus doit savoir QUELLE forme il tenait et laquelle "
                f"est attendue. Message : {msg}")

    def test_PL_3_et_la_BONNE_forme_marche_toujours(self):
        """`plan/C6`, second sens : ne pas casser ce qui fonctionnait.

        ⚠️ Une levee trop large transformerait un libelle utile en panne.
        """
        self.assertIsNone(synthese_colonnes_plan_manquantes(None))
        self.assertIsNone(synthese_colonnes_plan_manquantes({}))
        # Forme attendue, plan honore : rien a signaler, sans lever.
        self.assertIsNone(synthese_colonnes_plan_manquantes(
            {'plan': 'auto', 'colonnes_non_produites': []}))
        txt = synthese_colonnes_plan_manquantes(
            {'plan': 'auto', 'colonnes_non_produites': ['age_carre'],
             'facteurs_absents': ['age']})
        self.assertIn('MODELE AMPUTE', txt or '')
        self.assertIn('age_carre', txt or '')

    # ── `plan/C8` — l'empreinte scelle le document signe ────────────────────

    def test_PL_4_LE_TEST_QUI_FERME_le_commentaire_change_l_empreinte(self):
        """`plan/C8` : deux justifications differentes, deux empreintes."""
        sans = dict(_PLAN_MINIMAL)
        avec = dict(_PLAN_MINIMAL)
        avec['facteurs'] = [{'nom': 'age', 'type': 'continu',
                             'commentaire': 'retenu apres etude de 2026'}]
        autre = dict(_PLAN_MINIMAL)
        autre['facteurs'] = [{'nom': 'age', 'type': 'continu',
                              'commentaire': 'retenu par habitude'}]
        e_sans = PlanTarifaire.depuis_dict(sans).empreinte()
        e_avec = PlanTarifaire.depuis_dict(avec).empreinte()
        e_autre = PlanTarifaire.depuis_dict(autre).empreinte()
        self.assertNotEqual(
            e_sans, e_avec,
            'ajouter une justification ne change pas l empreinte')
        self.assertNotEqual(
            e_avec, e_autre,
            "deux justifications DIFFERENTES portent la MEME empreinte : "
            "l'audit trail declarerait les deux plans IDENTIQUES")
        for emp in (e_sans, e_avec, e_autre):
            self.assertTrue(emp.startswith(f's{EMPREINTE_SCHEMA}:'), emp)

    def test_PL_5_aucune_empreinte_d_un_schema_ANTERIEUR_persistee(self):
        """`plan/C8` : la mesure que tout bump exige, refaite ici.

        ⚠️ Un bump rend `SCHEMA_DIFFERENT` toute empreinte archivee sous
        l'ancien numero. C'est PREVU par `comparer_empreinte` -- mais il faut
        savoir combien d'artefacts sont concernes AVANT de bumper, pas apres.
        """
        anciens = [f's{n}:' for n in range(1, EMPREINTE_SCHEMA)]
        trouves = []
        for dossier in ('models', 'data'):
            racine = _RACINE / dossier
            if not racine.exists():
                continue
            for chemin in racine.rglob('*.json'):
                try:
                    texte = chemin.read_text(encoding='utf-8', errors='ignore')
                except OSError:
                    continue
                for prefixe in anciens:
                    if prefixe in texte:
                        trouves.append(f'{chemin.name} porte {prefixe}')
        self.assertEqual(
            trouves, [],
            f"des empreintes d'un schema anterieur sont persistees : "
            f"{trouves[:5]}. Elles deviendront SCHEMA_DIFFERENT -- il faut "
            f"le dire, et prescrire la re-tarification.")

    def test_PL_8_aucun_test_hors_du_GOLDEN_n_epingle_le_numero_en_dur(self):
        """⚠️⚠️ TROISIEME OCCURRENCE DU MEME DEFAUT, ET C'EST LE BUMP QUI L'A
        REVELEE.

        `test_horodatage_livrable` epinglait `'s1:'` en litteral ;
        `test_portes_du_plan` epinglait `'s3:'` ET `EMPREINTE_SCHEMA == 3`.
        Le bump `s3` -> `s4` du constat `plan/C8` a fait rougir la gate sur un
        test dont RIEN de ce qu'il prouve n'avait bouge.

        > *Un numero de schema epingle ailleurs que dans le golden fait de
        > chaque bump une edition a deux sites, sans la discipline du sceau.*

        Le SEUL endroit qui doit connaitre le numero est le golden de
        `test_plan_invariants` : la, constante et empreinte bougent ENSEMBLE,
        et c'est precisement ce qui rend le sceau opposable.

        ⚠️⚠️ ET MA PREMIERE VERSION DE CE CONTROLE ETAIT AU TEXTE, ELLE
        SUR-COMPTAIT. Le motif `EMPREINTE_SCHEMA\\s*(==|,)\\s*\\d` attrapait
        `assertGreaterEqual(EMPREINTE_SCHEMA, 3)` -- c'est-a-dire la forme
        DURABLE que je venais d'introduire -- et un litteral `'s1:'` servant
        de FIXTURE a `comparer_empreinte`, qui est parfaitement legitime.
        *Un releve au texte ne distingue pas une assertion d'une fixture.*
        Releve par AST, sur les deux formes qui, elles, perissent :
          - `assertEqual(EMPREINTE_SCHEMA, <litteral>)` ;
          - `.startswith('sN:')` sur une empreinte COURANTE.
        """
        import re
        golden = 'test_plan_invariants.py'
        prefixe_litteral = re.compile(r'^s\d+:$')
        fautifs = []
        for chemin in _fichiers_python():
            base = os.path.basename(chemin)
            if not base.startswith('test_') or base == golden:
                continue
            try:
                arbre = ast.parse(pathlib.Path(chemin).read_text(
                    encoding='utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for n in ast.walk(arbre):
                if not isinstance(n, ast.Call):
                    continue
                nom = getattr(n.func, 'attr', None)
                if (nom == 'assertEqual' and n.args
                        and isinstance(n.args[0], ast.Name)
                        and n.args[0].id == 'EMPREINTE_SCHEMA'):
                    fautifs.append(f'{base}:{n.lineno} assertEqual')
                if (nom == 'startswith' and n.args
                        and isinstance(n.args[0], ast.Constant)
                        and isinstance(n.args[0].value, str)
                        and prefixe_litteral.match(n.args[0].value)):
                    fautifs.append(f'{base}:{n.lineno} startswith')
        self.assertEqual(
            fautifs, [],
            f"numero de schema epingle en dur hors du golden : {fautifs}. "
            f"Deriver de `EMPREINTE_SCHEMA` -- sinon le prochain bump fera "
            f"rougir un test dont le sujet n'a pas bouge.")

    # ── `plan/C10` — trois etats sous une seule fleche ──────────────────────

    def test_PL_6_LE_TEST_QUI_FERME_l_en_tete_dit_l_etat_REEL(self):
        """`plan/C10` : DERIVE l'existence des quatre listes, ne la relit pas."""
        listes = ('MOTS_CLES_DETECTION', 'VARS_CATEGORIELLES', 'VARS_GLM',
                  'FACTEURS_TARIFAIRES_AUTORISES')
        existe = {nom: [] for nom in listes}
        for chemin in _fichiers_python():
            if os.path.basename(chemin).startswith('test_'):
                continue
            try:
                arbre = ast.parse(pathlib.Path(chemin).read_text(
                    encoding='utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for n in ast.walk(arbre):
                cibles = (n.targets if isinstance(n, ast.Assign)
                          else [n.target] if isinstance(n, ast.AnnAssign)
                          else [])
                for c in cibles:
                    if isinstance(c, ast.Name) and c.id in existe:
                        existe[c.id].append(f'{chemin}:{n.lineno}')
        for nom, sites in existe.items():
            ligne = next((l for l in _EN_TETE.split('\n') if nom in l), None)
            self.assertIsNotNone(
                ligne, f"l'en-tete ne mentionne plus '{nom}' : le lecteur ne "
                       f"peut plus savoir ce qu'elle est devenue")
            if sites:
                self.assertNotIn(
                    'SUPPRIM', ligne,
                    f"l'en-tete dit '{nom}' supprimee, elle est DEFINIE en "
                    f"{sites}")
            else:
                self.assertIn(
                    'SUPPRIM', ligne,
                    f"l'en-tete ne dit pas '{nom}' supprimee alors qu'elle "
                    f"n'est definie nulle part")

    # ── `plan/C11` — interne, pas une interface ─────────────────────────────

    def test_PL_7_colonnes_obligatoires_n_a_aucun_appelant_externe(self):
        """`plan/C11` : ce n'est pas du code mort, ce n'est pas une porte."""
        externes = []
        for chemin in _fichiers_python():
            if pathlib.Path(chemin) == pathlib.Path(_pmod.__file__):
                continue
            if os.path.basename(chemin).startswith('test_'):
                continue
            try:
                arbre = ast.parse(pathlib.Path(chemin).read_text(
                    encoding='utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for n in ast.walk(arbre):
                if isinstance(n, ast.Call):
                    nom = (getattr(n.func, 'attr', None)
                           or getattr(n.func, 'id', None))
                    if nom == 'colonnes_obligatoires':
                        externes.append(f'{chemin}:{n.lineno}')
        doc = PlanTarifaire.colonnes_obligatoires.__doc__ or ''
        if externes:
            self.assertNotIn(
                'PAS UNE INTERFACE', doc.upper(),
                f"la docstring dit << usage interne >> mais elle a des "
                f"appelants externes : {externes}. *Une phrase de portee se "
                f"mesure comme un chiffre.*")
        else:
            self.assertIn(
                'PAS UNE INTERFACE', doc.upper(),
                'la docstring ne dit pas que cette methode est interne')


if __name__ == '__main__':
    unittest.main(verbosity=2)
