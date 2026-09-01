"""Controles positifs — etape 4 du chantier des roles de donnees : le vocabulaire.

CE QUE CE FICHIER PROUVE, ET POURQUOI IL Y A DEUX SYSTEMES
──────────────────────────────────────────────────────────

Le depot porte DEUX vocabulaires paralleles, et ils ne se lisent pas :

    SYNONYMES_COLONNES  (A1)          -> les noms canoniques et leurs synonymes
    _roles_attendus     (mapping LLM) -> derive du PLAN, n'importe PAS le premier

⚠️⚠️ AJOUTER LE NOM CANONIQUE A UN SEUL DES DEUX EST INOPERANT. Mesure du
30/08/2026 : declarer `echeance` au plan faisait passer les roles de 16 a 17,
et le seul ajout etait `id_contrat` -- `date_echeance` rendait `None`.

⚠️⚠️ ET C'ETAIT PIRE QUE MUET. `_prompt_utilisateur` etiquette
`roles.get(c, 'facteur')` : tout role non nomme devient un FACTEUR TARIFAIRE
aux yeux du modele, c'est-a-dire une grandeur A MODELISER. Or le plan interdit
exactement cela a ces colonnes -- « purement des roles de donnees ; elles
n'entrent JAMAIS dans `colonnes_produites()` ». *Declarer l'echeance sans la
nommer dans `_roles_attendus` aurait appris au modele le contraire de ce que
le plan dit.*

═══ LA VALEUR EST UN DISCRIMINANT OPAQUE ═══

Jamais parsee, jamais comparee, jamais soustraite. Une annee (`2024`), une date
(`2024-03-01`) ou un libelle de periode conviennent egalement : on ne fait qu'y
distinguer des groupes. *Cela evite d'introduire un contrat de date la ou une
simple cle de partition suffit.*

═══ RGPD ═══

L'ajout d'un champ de DATE ne cree aucun risque propre : le caviardage reduit
la colonne a sa FORME (`date AAAA-MM-JJ, 3 valeurs distinctes`). Verifie par
sentinelle ci-dessous, sans cle API.
"""

from __future__ import annotations

import dataclasses
import os
import unittest
from unittest import mock

import pandas as pd

from core import mapping_llm
from direction_non_vie.tarification.a1_ingestion.agent import SYNONYMES_COLONNES
from direction_non_vie.tarification.test_pipeline_agents import _PLAN_AUTO

_PLAN_ROLES = dataclasses.replace(_PLAN_AUTO, identifiant_contrat='id_contrat',
                                  echeance='date_echeance')

# ⚠️⚠️ `_PLAN_AUTO` EST LE PLAN LIVRE, et depuis l'etape 5 il declare son
# echeance. « Un plan sans echeance » doit donc etre construit EXPLICITEMENT :
# s'appuyer sur une absence implicite fait dependre le test d'un fichier livre.
_PLAN_SANS_ROLE = dataclasses.replace(_PLAN_AUTO, identifiant_contrat=None,
                                      echeance=None)


def _sans_cle():
    env = {k: v for k, v in os.environ.items()
           if k not in ('ANTHROPIC_API_KEY', 'CLAUDE_API_KEY')}
    return mock.patch.dict(os.environ, env, clear=True)


def _fichier_client(sentinelles):
    ident, date, nom = sentinelles
    return pd.DataFrame({'num_police': [ident] * 4, 'date_ech': [date] * 4,
                         'nom_assure': [nom] * 4, 'expo': [1.0] * 4,
                         'claimnb': [0] * 4, 'claimamount': [0.0] * 4})


class TestLeVocabulaireD_A1(unittest.TestCase):
    """Systeme 1 — `SYNONYMES_COLONNES`."""

    def test_date_echeance_est_une_entree_canonique(self):
        self.assertIn('date_echeance', SYNONYMES_COLONNES)
        self.assertGreaterEqual(len(SYNONYMES_COLONNES['date_echeance']), 12)
        print(f"    V-1 `date_echeance` canonique, "
              f"{len(SYNONYMES_COLONNES['date_echeance'])} synonymes")

    def test_aucun_synonyme_n_est_revendique_par_DEUX_entrees(self):
        """⚠️⚠️ UN SYNONYME PARTAGE EST UNE AMBIGUITE DE MAPPING, pas un detail.

        Ce controle porte sur TOUTE la table, pas seulement sur l'ajout : il
        tombera aussi le jour ou une autre entree revendiquera un nom deja pris.
        ⚠️ Il ne juge PAS les doublons INTRA-liste : deux fois le meme nom sous
        la MEME cle ne cree aucune ambiguite de mapping. C'etait `a1/C5`, FERME
        le 01/09/2026 et epingle par `A1-4` de `test_a1_six_constats.py` -- qui
        garde les DEUX formes. *Nommer la borne d'un filet reste ce qui empeche
        de le croire plus large qu'il n'est.*
        """
        vu, partages = {}, {}
        for cle, syns in SYNONYMES_COLONNES.items():
            for s in set(syns):
                if s in vu and vu[s] != cle:
                    partages.setdefault(s, {vu[s]}).add(cle)
                vu[s] = cle
        self.assertEqual(partages, {},
                         f'synonyme(s) revendique(s) par deux entrees '
                         f'canoniques : {partages}')
        print(f"    V-2 {len(vu)} synonymes, aucun revendique par deux entrees")

    def test_l_echeance_n_est_PAS_l_annee_de_survenance(self):
        """⚠️⚠️ LES CONFONDRE SERAIT GRAVE. L'une est la periode de couverture
        du CONTRAT, l'autre l'annee ou le SINISTRE est survenu. Dedoublonner sur
        la seconde trancherait sur la mauvaise grandeur."""
        ech = set(SYNONYMES_COLONNES['date_echeance'])
        surv = set(SYNONYMES_COLONNES['annee_survenance'])
        self.assertEqual(ech & surv, set(),
                         'un synonyme est partage entre echeance et survenance')
        print(f"    V-3 echeance ∩ survenance = ∅ ({len(ech)} vs {len(surv)})")


class TestLeVocabulaireDuMappingLLM(unittest.TestCase):
    """Systeme 2 — `_roles_attendus`, derive du plan."""

    def test_LE_TEST_QUI_FERME_l_echeance_a_son_VRAI_role(self):
        """⚠️⚠️ Elle etait presentee comme « facteur » — une grandeur a
        modeliser, l'inverse de ce que le plan declare."""
        role = mapping_llm._roles_attendus(_PLAN_ROLES).get('date_echeance')
        self.assertIsNotNone(role, "l'echeance n'a AUCUN role : elle tombera "
                                   "sur le defaut « facteur »")
        self.assertIn('echeance', role)
        self.assertIn('ne pas modeliser', role,
                      'le role ne dit pas que la colonne ne se modelise pas')
        print(f"    V-4 role = « {role} »")

    def test_AUCUNE_colonne_attendue_ne_tombe_sur_le_defaut(self):
        """⚠️⚠️ LE CONTROLE LE PLUS LARGE DU LOT, ET LE PLUS UTILE.

        `_prompt_utilisateur` fait `roles.get(c, 'facteur')`. Plutot que
        d'epingler la seule echeance, on epingle la PROPRIETE : aucune colonne
        attendue ne doit tomber sur ce defaut. Mesure — avant ce lot,
        `date_echeance` etait la SEULE ; le defaut est desormais vide.
        *Ce test tombera le jour ou un nouveau role sera ajoute au plan sans
        etre nomme ici, c'est-a-dire avant qu'il ne soit mal presente.*
        """
        roles = mapping_llm._roles_attendus(_PLAN_ROLES)
        sans = [c for c in _PLAN_ROLES.colonnes_attendues() if c not in roles]
        self.assertEqual(
            sans, [],
            f"{len(sans)} colonne(s) seront presentees au modele comme "
            f"« facteur » faute de role nomme : {sans}")
        print(f"    V-5 {len(list(_PLAN_ROLES.colonnes_attendues()))} colonnes "
              f"attendues, 0 sur le defaut « facteur »")

    def test_le_PROMPT_reel_porte_le_role(self):
        """⚠️ La table peut le nommer sans que le prompt le montre. On lit le
        prompt, pas la table."""
        with _sans_cle():
            p = mapping_llm._prompt_utilisateur(
                _fichier_client(('X', '2024-03-01', 'Y')), _PLAN_ROLES, 5)
        self.assertIn('date_echeance : echeance de contrat', p)
        self.assertNotIn(' : facteur', p,
                         'une colonne est encore presentee comme « facteur »')
        print("    V-6 le prompt reel porte le role, et plus aucun « facteur »")

    def test_SECOND_SENS_un_plan_SANS_echeance_n_en_invente_pas(self):
        """⚠️⚠️ Les 20 plans du depot n'en declarent aucune (etape 5). Le
        vocabulaire ne doit rien ajouter tant que le plan se tait."""
        roles = mapping_llm._roles_attendus(_PLAN_SANS_ROLE)
        self.assertFalse(any('echeance' in str(v) for v in roles.values()),
                         "un role d'echeance apparait alors que le plan n'en "
                         'declare aucune')
        with _sans_cle():
            p = mapping_llm._prompt_utilisateur(
                _fichier_client(('X', '2024-03-01', 'Y')), _PLAN_SANS_ROLE, 5)
        self.assertNotIn('date_echeance', p)
        print("    V-7 second sens : plan sans echeance -> aucun role inedit, "
              "rien dans le prompt")


class TestRGPD(unittest.TestCase):
    """⚠️⚠️ NON NEGOCIABLE — un champ de DATE ne doit rien laisser sortir."""

    def test_le_prompt_ne_laisse_sortir_AUCUNE_valeur(self):
        sentinelles = ('POLICE-SECRETE-1', '2024-03-01', 'DUPONT Jean')
        with _sans_cle():
            p = mapping_llm._prompt_utilisateur(
                _fichier_client(sentinelles), _PLAN_ROLES, 5)
        for s in sentinelles:
            with self.subTest(sentinelle=s):
                self.assertNotIn(s, p, 'une valeur du fichier client sort')
        self.assertIn('date_ech', p, 'le NOM de la colonne doit sortir, lui')
        self.assertIn('date AAAA-MM-JJ', p,
                      'la FORME de la date doit sortir, pas la date')
        print("    V-8 RGPD : identifiant, date et nom absents du prompt ; "
              "seuls le NOM de colonne et la FORME sortent")


if __name__ == '__main__':
    unittest.main()
