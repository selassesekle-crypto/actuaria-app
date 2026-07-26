# =============================================================================
#  Tests — nv_triangle_mapping_llm.py (Bloc II, module 3)
#
#  AUCUN test ne nécessite le paquet `anthropic` ni de clé API : tous patchent
#  _appeler_claude, la frontière unique avec le service. C'est indispensable ici,
#  l'environnement n'ayant NI le paquet NI la clé.
#
#  CE QU'ON TESTE : qu'une réponse BIEN FORMÉE est correctement exploitée, et
#  qu'une réponse MAL FORMÉE dégrade proprement.
#  CE QU'ON NE TESTE PAS : si la proposition de Claude est actuariellement BONNE
#  — ce n'est pas testable unitairement, c'est précisément le rôle de la
#  validation par l'actuaire.
# =============================================================================

import ast
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import direction_non_vie.services.nv_triangle_mapping_llm as llm
from direction_non_vie.services.nv_triangle_mapping_llm import (
    ROLES, RapportRolesLLM, MappingTriangleLLMIndisponible,
    proposer_roles_onglets, proposer_mapping_colonnes,
)
from direction_non_vie.services.nv_triangle_mapping import (
    CHAMPS_SINISTRES, CHAMPS_PRIMES, TriangleSchema, MappingTriangleIncoherent,
    appliquer_mapping_triangle,
)

# ── Jeux d'essai ─────────────────────────────────────────────────────────────
DF_SINISTRES = pd.DataFrame({
    'ANNEE_SURV': [2020, 2020, 2021],
    'DEV':        [0, 1, 0],
    'REGLEMENTS': [100.0, 150.0, 120.0],
    'CHARGE_TOT': [180.0, 175.0, 200.0],
})
DF_PRIMES = pd.DataFrame({'AY': [2020, 2021], 'PREM': [5000.0, 5200.0]})
ONGLETS = {'Feuil1': DF_SINISTRES, 'Feuil2': DF_PRIMES}


def _mock(payload) -> str:
    """Réponse simulée du modèle (texte brut, comme l'API)."""
    return json.dumps(payload)


class T1_Roles_Nominal(unittest.TestCase):
    """Rôles — réponse bien formée."""

    def test_roles_valides_parses(self):
        rep = _mock({
            'Feuil1': {'role': 'sinistres', 'confiance': 'haute',
                       'justification': '3 colonnes de montants et un axe de dev'},
            'Feuil2': {'role': 'primes', 'confiance': 'moyenne',
                       'justification': '1 ligne par annee, une seule mesure'},
        })
        with patch.object(llm, '_appeler_claude', return_value=rep):
            rap = proposer_roles_onglets(ONGLETS)
        self.assertIsInstance(rap, RapportRolesLLM)
        self.assertEqual(rap.roles['Feuil1'].role, 'sinistres')
        self.assertEqual(rap.roles['Feuil2'].confiance, 'moyenne')
        self.assertEqual(rap.onglets_ignores, ())
        self.assertEqual(rap.entrees_ecartees, ())
        print("    OK T1a rôles : 2 onglets classés, aucune entrée écartée")

    def test_synthese_json_serialisable(self):
        rep = _mock({'Feuil1': {'role': 'inconnu', 'confiance': 'basse',
                                'justification': 'feuille de notes'}})
        with patch.object(llm, '_appeler_claude', return_value=rep):
            rap = proposer_roles_onglets(ONGLETS)
        s = rap.synthese()
        json.dumps(s)                                    # doit être sérialisable
        self.assertIn('roles', s)
        self.assertIn('Feuil2', s['onglets_ignores'])    # non classé → ignoré
        print("    OK T1b synthese() sérialisable, onglet non classé listé")


class T2_Roles_Tolerance(unittest.TestCase):
    """Rôles — validation TOLÉRANTE : on écarte l'entrée douteuse, pas le reste."""

    def test_role_hors_enumeration_ecarte_le_reste_conserve(self):
        rep = _mock({
            'Feuil1': {'role': 'sinistres', 'confiance': 'haute', 'justification': 'ok'},
            'Feuil2': {'role': 'triangle_magique', 'confiance': 'haute',
                       'justification': 'invente'},
        })
        with patch.object(llm, '_appeler_claude', return_value=rep):
            rap = proposer_roles_onglets(ONGLETS)
        self.assertIn('Feuil1', rap.roles)               # la bonne est CONSERVÉE
        self.assertNotIn('Feuil2', rap.roles)            # la douteuse est écartée
        self.assertTrue(any('hors enumeration' in e for e in rap.entrees_ecartees))
        self.assertIn('Feuil2', rap.onglets_ignores)
        print("    OK T2a rôle hors énumération : écarté + tracé, le reste conservé")

    def test_onglet_hallucine_ecarte(self):
        rep = _mock({
            'Feuil1': {'role': 'sinistres', 'confiance': 'haute', 'justification': 'ok'},
            'FeuilFantome': {'role': 'primes', 'confiance': 'haute', 'justification': 'x'},
        })
        with patch.object(llm, '_appeler_claude', return_value=rep):
            rap = proposer_roles_onglets(ONGLETS)
        self.assertNotIn('FeuilFantome', rap.roles)
        self.assertTrue(any('onglet inconnu' in e for e in rap.entrees_ecartees))
        print("    OK T2b onglet halluciné : écarté + tracé")

    def test_proposition_mal_formee_et_confiance_invalide(self):
        rep = _mock({
            'Feuil1': 'sinistres',                        # pas un objet → écarté
            'Feuil2': {'role': 'primes', 'confiance': 'certaine'},  # confiance inconnue
        })
        with patch.object(llm, '_appeler_claude', return_value=rep):
            rap = proposer_roles_onglets(ONGLETS)
        self.assertNotIn('Feuil1', rap.roles)
        self.assertEqual(rap.roles['Feuil2'].confiance, 'basse')   # repli prudent
        self.assertEqual(rap.roles['Feuil2'].justification, '')    # absente → vide
        print("    OK T2c entrée mal formée écartée ; confiance inconnue → 'basse'")

    def test_aucun_role_exploitable_leve(self):
        rep = _mock({'Feuil1': {'role': 'zzz'}, 'Feuil2': {'role': 'yyy'}})
        with patch.object(llm, '_appeler_claude', return_value=rep):
            with self.assertRaises(MappingTriangleLLMIndisponible):
                proposer_roles_onglets(ONGLETS)
        print("    OK T2d aucun rôle exploitable → Indisponible")


class T3_Mapping_Strict(unittest.TestCase):
    """Mapping — validation STRICTE : aucun passe-droit pour le LLM."""

    def test_mapping_valide_donne_un_schema_utilisable(self):
        rep = _mock({'ANNEE_SURV': 'annee_survenance', 'DEV': 'annee_developpement',
                     'REGLEMENTS': 'montant_paye', 'CHARGE_TOT': 'montant_charge'})
        with patch.object(llm, '_appeler_claude', return_value=rep):
            schema = proposer_mapping_colonnes(DF_SINISTRES)
        self.assertIsInstance(schema, TriangleSchema)
        self.assertEqual(schema.kind, 'sinistres')
        # le schéma est directement consommable par le module 2
        _, rap = appliquer_mapping_triangle(DF_SINISTRES, schema)
        self.assertTrue(rap.peut_construire_paiements)
        self.assertTrue(rap.peut_construire_charges)
        print("    OK T3a mapping valide : TriangleSchema consommable par le module 2")

    def test_cible_inventee_leve_incoherent(self):
        """Le mur du module 2 s'applique au LLM comme à un YAML humain."""
        rep = _mock({'ANNEE_SURV': 'annee_survenance', 'REGLEMENTS': 'montant_magique'})
        with patch.object(llm, '_appeler_claude', return_value=rep):
            with self.assertRaises(MappingTriangleIncoherent):
                proposer_mapping_colonnes(DF_SINISTRES)
        print("    OK T3b cible inventée → MappingTriangleIncoherent (pas de passe-droit)")

    def test_collision_de_cible_leve(self):
        rep = _mock({'ANNEE_SURV': 'annee_survenance',
                     'REGLEMENTS': 'montant_paye', 'CHARGE_TOT': 'montant_paye'})
        with patch.object(llm, '_appeler_claude', return_value=rep):
            with self.assertRaises(MappingTriangleIncoherent):
                proposer_mapping_colonnes(DF_SINISTRES)
        print("    OK T3c deux colonnes → même cible : lève")

    def test_kind_primes_utilise_le_bon_vocabulaire(self):
        rep = _mock({'AY': 'annee_survenance', 'PREM': 'prime'})
        with patch.object(llm, '_appeler_claude', return_value=rep):
            schema = proposer_mapping_colonnes(DF_PRIMES, kind='primes')
        self.assertEqual(schema.kind, 'primes')
        _, rap = appliquer_mapping_triangle(DF_PRIMES, schema)
        self.assertEqual(set(rap.champs_couverts), {'annee_survenance', 'prime'})
        print("    OK T3d kind='primes' : vocabulaire primes appliqué")

    def test_proposition_vide_leve_indisponible(self):
        with patch.object(llm, '_appeler_claude', return_value=_mock({})):
            with self.assertRaises(MappingTriangleLLMIndisponible):
                proposer_mapping_colonnes(DF_SINISTRES)
        print("    OK T3e aucune correspondance proposée → Indisponible")


class T4_Garde_Fou_Indisponibilite(unittest.TestCase):
    """Le service indisponible ne doit JAMAIS produire un crash opaque."""

    def test_service_qui_leve_devient_indisponible(self):
        def _boom(*a, **k):
            raise MappingTriangleLLMIndisponible("paquet 'anthropic' indisponible")
        for fn, args in ((proposer_roles_onglets, (ONGLETS,)),
                         (proposer_mapping_colonnes, (DF_SINISTRES,))):
            with patch.object(llm, '_appeler_claude', side_effect=_boom):
                with self.assertRaises(MappingTriangleLLMIndisponible):
                    fn(*args)
        print("    OK T4a service indisponible → MappingTriangleLLMIndisponible (2 fonctions)")

    def test_reponse_illisible_et_non_objet(self):
        for reponse in ("désolé, je ne peux pas", "", "[1, 2, 3]"):
            with patch.object(llm, '_appeler_claude', return_value=reponse):
                with self.assertRaises(MappingTriangleLLMIndisponible):
                    proposer_mapping_colonnes(DF_SINISTRES)
        print("    OK T4b réponse illisible / vide / non-objet → Indisponible")

    def test_json_avec_preambule_est_tolere(self):
        """Un préambule bavard ne doit pas faire échouer une réponse exploitable."""
        rep = ('Voici ma proposition :\n```json\n'
               '{"ANNEE_SURV": "annee_survenance", "REGLEMENTS": "montant_paye"}\n```')
        with patch.object(llm, '_appeler_claude', return_value=rep):
            schema = proposer_mapping_colonnes(DF_SINISTRES)
        self.assertEqual(schema.correspondances['REGLEMENTS'], 'montant_paye')
        print("    OK T4c JSON entouré de texte : extrait correctement")

    def test_entrees_vides_levent(self):
        with self.assertRaises(MappingTriangleLLMIndisponible):
            proposer_roles_onglets({})
        with self.assertRaises(MappingTriangleLLMIndisponible):
            proposer_mapping_colonnes(pd.DataFrame())
        print("    OK T4d entrée vide (aucun onglet / aucune colonne) → Indisponible")


class T5_Anti_Derive(unittest.TestCase):
    """Le prompt est CONSTRUIT depuis le module 2, jamais recopié — sans quoi un
    prompt figé ferait proposer des cibles périmées."""

    def test_prompt_contient_exactement_le_vocabulaire_du_module_2(self):
        for kind, attendus in (('sinistres', CHAMPS_SINISTRES),
                               ('primes', CHAMPS_PRIMES)):
            prompt = llm._prompt_utilisateur_mapping(DF_SINISTRES, kind, 3)
            for champ in attendus:
                self.assertIn(champ, prompt, f"{kind} : {champ} absent du prompt")
            # et AUCUN champ de l'autre vocabulaire ne fuite
            for champ in (CHAMPS_SINISTRES | CHAMPS_PRIMES) - attendus:
                self.assertNotIn(f"- {champ} :", prompt,
                                 f"{kind} : {champ} ne devrait pas figurer")
        print("    OK T5a prompt mapping : vocabulaire exact du module 2, sans fuite")

    def test_champ_ajoute_au_module_2_apparait_sans_toucher_au_prompt(self):
        """Preuve de la construction DYNAMIQUE : on ajoute un champ au vocabulaire
        du module 2 et il apparaît dans le prompt sans qu'une ligne du module 3
        ne change. Un prompt recopié à la main échouerait ici."""
        etendu = frozenset(CHAMPS_SINISTRES | {'montant_recours'})
        with patch.object(llm, 'CHAMPS_SINISTRES', etendu):
            prompt = llm._prompt_utilisateur_mapping(DF_SINISTRES, 'sinistres', 3)
        self.assertIn('montant_recours', prompt)
        print("    OK T5b champ ajouté au module 2 → présent dans le prompt (dynamique)")

    def test_prompt_roles_contient_les_5_roles(self):
        systeme = llm._prompt_systeme_roles()
        for role in ROLES:
            self.assertIn(role, systeme)
        self.assertIn('CONTENU', systeme.upper())      # contenu > nom
        print("    OK T5c prompt rôles : les 5 rôles + primauté du contenu")

    def test_nom_onglet_signal_secondaire(self):
        """Le nom d'onglet est envoyé, mais le prompt interdit de justifier par
        le seul nom (décision de conception validée)."""
        systeme = llm._prompt_systeme_roles()
        self.assertIn('SECONDAIRE', systeme.upper())
        self.assertIn('JAMAIS par le seul nom', systeme)
        utilisateur = llm._prompt_utilisateur_roles(ONGLETS, 3)
        self.assertIn('Feuil1', utilisateur)           # le nom EST transmis
        print("    OK T5d nom d'onglet transmis mais explicitement secondaire")


class T6_Perimetre(unittest.TestCase):
    """Verrous de périmètre : isolement et frontière API unique."""

    def test_aucun_import_anthropic_au_niveau_module(self):
        """`anthropic` ne doit être importé QU'À l'appel — sinon le module
        deviendrait inimportable sans le paquet (absent de cet environnement)."""
        src = Path(llm.__file__).read_text(encoding='utf-8')
        for noeud in ast.parse(src).body:            # niveau MODULE uniquement
            if isinstance(noeud, (ast.Import, ast.ImportFrom)):
                noms = [a.name for a in noeud.names]
                mod = getattr(noeud, 'module', '') or ''
                self.assertNotIn('anthropic', noms + [mod])
        print("    OK T6a aucun import 'anthropic' au niveau module")

    def test_module_agnostique_de_l_interface(self):
        src = Path(llm.__file__).read_text(encoding='utf-8')
        for noeud in ast.walk(ast.parse(src)):
            if isinstance(noeud, (ast.Import, ast.ImportFrom)):
                cible = (getattr(noeud, 'module', '') or '') + ' ' + \
                        ' '.join(a.name for a in noeud.names)
                self.assertNotIn('streamlit', cible)
                self.assertNotIn('core.mapping', cible)   # indépendant du tarif
        print("    OK T6b aucun import streamlit ni core.mapping_* (indépendant du tarif)")

    def test_api_publique_stable(self):
        for nom in ('proposer_roles_onglets', 'proposer_mapping_colonnes',
                    'MappingTriangleLLMIndisponible', 'RapportRolesLLM', 'ROLES'):
            self.assertIn(nom, llm.__all__)
        self.assertEqual(set(ROLES), {'triangle_paiements', 'triangle_charges',
                                      'sinistres', 'primes', 'inconnu'})
        print("    OK T6c API publique et les 5 rôles stables")


if __name__ == '__main__':
    unittest.main()
