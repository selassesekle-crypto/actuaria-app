"""LE MAPPING D'A1 PUBLIE SA CAUSE -- constat `A1-1`, le dernier des seize.

`a1._appliquer_mapping_client` renommait SANS RIEN VALIDER : 80 lignes, zero
controle -- ni cible inconnue du plan, ni collision, ni plan vise. Une faute
de frappe dans `config/{client}_mapping.json` renomme vers une colonne que le
plan n'attend pas ; A2 la declare manquante et le modele sort << ampute >>.

  ***L'effet est publie, la cause ne l'est pas*** -- l'actuaire ne peut pas
  distinguer << le client n'a pas fourni la colonne >> de << mon mapping l'a
  mal nommee >>.

⚠️⚠️ ET C'ETAIENT DEUX MOITIES D'UNE MEME CHAINE QUI NE SE TOUCHAIENT PAS. Le
socle SAIT valider (4 refus) et SAIT rediger (`synthese_mapping`, 3 phrases,
3 surfaces) -- mais son point d'entree `preparer_fichier_client` a ZERO
appelant de production. A1 TOURNE et jetait son diagnostic. Les trois
surfaces recevaient donc TOUJOURS `None`.

⚠️ LA FORME VIENT D'UN ECHANGE AVEC L'AUDITEUR INDEPENDANT :
  · `diagnostiquer_mapping` rend les faits SANS lever -- un booleen
    `lever=False` aurait masque TROIS dispositions differentes (une collision
    ne peut pas s'appliquer, une cible inconnue le peut, un mauvais plan ne
    produit rien) ;
  · format ADDITIF : le JSON plat existant continue de marcher, et le rapport
    declare que le controle de plan n'a PAS ete exerce -- plutot que de
    synthetiser le champ, ce qui rendrait le garde INOPERANT tout en le
    faisant figurer comme un controle effectue ;
  · severite CROISEE : une correspondance morte est informative, SAUF si la
    colonne du plan qu'elle visait est non couverte -- c'est alors la seule
    phrase qui nomme la cause de l'amputation, et le cas reel le plus
    frequent (un export client renomme en amont).

  MC-1  le diagnostic vient du SOCLE, jamais recopie dans A1 ;
  MC-2  une cible mal orthographiee est NOMMEE ;
  MC-3  une cle source morte qui cause une amputation est NOMMEE comme telle ;
  MC-4  second sens : une morte SANS consequence reste informative ;
  MC-5  le format plat marche, et le controle de plan se declare NON exerce ;
  MC-6  un mapping echoue ne se confond plus avec un mapping absent ;
  MC-7  `diagnostiquer_mapping` ne leve JAMAIS, `appliquer_mapping` si ;
  MC-8  la cle voyage jusqu'a la RACINE du resultat d'A1, la ou A6 lit.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""

from __future__ import annotations

import ast
import os
import pathlib
import sys
import tempfile
import unittest

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

import pandas as pd

from core.mapping_client import (
    MappingClient,
    MappingIncoherent,
    appliquer_mapping,
    diagnostiquer_mapping,
    synthese_mapping,
)
from core.plan_tarifaire import PlanTarifaire

_A1 = pathlib.Path(_ICI) / 'a1_ingestion' / 'agent.py'


def _plan():
    return PlanTarifaire.depuis_yaml(
        os.path.join(_RACINE, 'plans', 'auto.yaml'))


def _df(colonnes):
    return pd.DataFrame({c: [1, 2] for c in colonnes})


class TestMappingPublieSaCause(unittest.TestCase):

    def test_MC1_le_diagnostic_vient_du_SOCLE_jamais_recopie(self):
        """⚠️⚠️ LA FORME QUE L'AUDITEUR PROPOSAIT D'ABORD RECOPIAIT LES TROIS
        CONTROLES DANS A1. Sa prose disait << faire valider par le socle >> et
        son code les reimplementait a la main : deux jeux de regles qui
        divergent, le defaut que ce chantier ferme partout. On epingle donc
        l'APPEL, par AST."""
        arbre = ast.parse(_A1.read_text(encoding='utf-8'))
        appelle = any(
            isinstance(n, ast.Call)
            and getattr(n.func, 'attr', getattr(n.func, 'id', None))
            == 'diagnostiquer_mapping'
            for n in ast.walk(arbre))
        self.assertTrue(
            appelle,
            'A1 ne fait plus appel au diagnostic du socle : les regles y sont '
            'peut-etre recopiees, et elles divergeront')
        # ⚠️ ET IL NE LES RECOPIE PAS : aucune des trois regles au site.
        texte = _A1.read_text(encoding='utf-8')
        for interdit in ('colonnes_attendues()', 'cibles_inconnues ='):
            with self.subTest(interdit=interdit):
                self.assertNotIn(
                    interdit, texte,
                    f'A1 reimplemente une regle du socle ({interdit})')
        print('    MC-1 A1 appelle le socle et ne le recopie pas')

    def test_MC2_une_cible_mal_orthographiee_est_NOMMEE(self):
        plan = _plan()
        att = sorted(plan.colonnes_attendues())
        df = _df(['SRC_A', 'SRC_B'])
        m = MappingClient.depuis_plat(
            {'SRC_A': att[0], 'SRC_B': att[1] + '_FAUTE'}, 'demo')
        r = diagnostiquer_mapping(df, m, plan)
        self.assertIn(att[1] + '_FAUTE', r.cibles_inconnues_du_plan)
        self.assertIn('INCONNUE', synthese_mapping(r) or '')
        print('    MC-2 la faute de frappe sur la cible est nommee')

    def test_MC3_une_morte_qui_cause_une_amputation_est_NOMMEE(self):
        """⚠️⚠️ LA SEVERITE CROISEE, ET C'EST LE CAS REEL LE PLUS FREQUENT :
        un export client renomme en amont. La cle source ne correspond plus,
        l'entree est ecartee EN SILENCE (`a1:691-694`), et le modele sort
        ampute sans que rien ne dise pourquoi."""
        plan = _plan()
        att = sorted(plan.colonnes_attendues())
        df = _df(['SRC_A'])
        m = MappingClient.depuis_plat(
            {'SRC_A': att[0], 'ANCIEN_NOM': att[1]}, 'demo')
        r = diagnostiquer_mapping(df, m, plan)
        self.assertIn('ANCIEN_NOM', r.correspondances_mortes)
        self.assertIn(att[1], r.colonnes_plan_non_couvertes)
        self.assertIn('ANCIEN_NOM', r.mortes_qui_causent_une_amputation())
        phrase = synthese_mapping(r) or ''
        self.assertIn("CAUSE DE L'AMPUTATION", phrase, phrase)
        self.assertIn('ANCIEN_NOM', phrase)
        print('    MC-3 la cause de l amputation est nommee')

    def test_MC4_second_sens_une_morte_SANS_consequence_reste_informative(self):
        """⚠️ Sans ce sens, une regle qui crierait sur TOUTE morte passerait
        MC-3 -- et la phrase qui nomme la cause deviendrait du bruit."""
        plan = _plan()
        att = sorted(plan.colonnes_attendues())
        # la cible de la morte est DEJA presente sous son propre nom
        df = _df(['SRC_A', att[1]])
        m = MappingClient.depuis_plat(
            {'SRC_A': att[0], 'ANCIEN_NOM': att[1]}, 'demo')
        r = diagnostiquer_mapping(df, m, plan)
        self.assertIn('ANCIEN_NOM', r.correspondances_mortes)
        self.assertNotIn(att[1], r.colonnes_plan_non_couvertes)
        self.assertEqual(r.mortes_qui_causent_une_amputation(), ())
        self.assertNotIn("CAUSE DE L'AMPUTATION", synthese_mapping(r) or '')
        print('    MC-4 une morte sans consequence ne crie pas')

    def test_MC5_le_format_plat_marche_et_le_controle_se_declare(self):
        """⚠️⚠️ LE GARDE QUI NE PEUT PAS TIRER SE DECLARE, IL NE SE SIMULE PAS.
        La tentation etait de mettre `plan.lob` dans le champ manquant : le
        garde << le mapping cible un autre plan >> comparerait alors
        `plan.lob` a lui-meme -- il ne pourrait plus JAMAIS se declencher, tout
        en figurant au rapport comme un controle EFFECTUE. *Un garde muet est
        pire que pas de garde.*"""
        plan = _plan()
        att = sorted(plan.colonnes_attendues())
        m = MappingClient.depuis_plat({'SRC_A': att[0]}, 'demo')
        self.assertEqual(m.plan, '', 'le plan a ete synthetise')
        r = diagnostiquer_mapping(_df(['SRC_A']), m, plan)
        self.assertIsNone(r.plan_declare)
        self.assertFalse(r.plan_incoherent)
        self.assertFalse(r.synthese()['controle_plan_effectue'])
        self.assertIn("n'a PAS ete exerce", synthese_mapping(r) or '')
        # ⚠️ ET LA FORME ENVELOPPEE GAGNE LE CONTROLE : c'est ce qui rend le
        # format ADDITIF, et non un simple contournement.
        m2 = MappingClient.depuis_dict(
            {'client': 'demo', 'plan': 'mrh', 'correspondances': {'SRC_A': att[0]}})
        r2 = diagnostiquer_mapping(_df(['SRC_A']), m2, plan)
        self.assertTrue(r2.synthese()['controle_plan_effectue'])
        self.assertTrue(r2.plan_incoherent)
        print('    MC-5 format plat : controle declare NON exerce ; enveloppe : exerce')

    def test_MC6_un_mapping_ECHOUE_ne_se_confond_plus_avec_un_ABSENT(self):
        """⚠️ L'`except` d'A1 partait dans un `logger.warning` et laissait
        `applique` a False -- exactement l'etat d'un client SANS fichier.
        *Deux causes opposees, un seul symptome.*"""
        from direction_non_vie.tarification.a1_ingestion.agent import (
            AgentA1Ingestion,
        )
        a1 = AgentA1Ingestion.__new__(AgentA1Ingestion)
        with tempfile.TemporaryDirectory() as tmp:
            chemin = pathlib.Path(tmp)
            (chemin / 'demo_mapping.json').write_text('{ ceci n est pas du json',
                                                      encoding='utf-8')
            a1.config_path_dir = chemin
            _, info = a1._appliquer_mapping_client(
                _df(['SRC_A']), 'demo', plan=_plan())
        self.assertFalse(info['applique'])
        self.assertIsNotNone(
            info['echec_chargement'],
            'un mapping ILLISIBLE reste indiscernable d un mapping ABSENT')
        print(f"    MC-6 echec declare : {info['echec_chargement'][:44]}")

    def test_MC7_diagnostiquer_ne_leve_jamais_appliquer_si(self):
        """⚠️ C'est toute la difference entre les deux, et c'est ce qui permet
        a A1 de SIGNALER sans changer le comportement d'ingestion."""
        plan = _plan()
        att = sorted(plan.colonnes_attendues())
        df = _df(['SRC_A', 'SRC_B'])
        m = MappingClient.depuis_plat(
            {'SRC_A': att[0] + '_FAUTE', 'SRC_B': att[0] + '_FAUTE'}, 'demo')
        # diagnostiquer : rend les faits
        r = diagnostiquer_mapping(df, m, plan)
        self.assertTrue(r.cibles_inconnues_du_plan)
        self.assertTrue(r.collisions)
        # appliquer : leve
        with self.assertRaises(MappingIncoherent):
            appliquer_mapping(df, m, plan)
        print('    MC-7 le diagnostic rend, l application leve')

    def test_MC8_la_cle_voyage_jusqu_a_la_RACINE_du_resultat_d_A1(self):
        """⚠️⚠️ TROISIEME FOIS DANS CE CHANTIER. Poser la cle sur un
        dictionnaire qui voyage ne suffit pas : A6 lit la RACINE de
        `result_a1`, comme pour `qualite` ou `statut_rag`. Mesure par
        execution : la cause n'atteignait rien. *Seule la mesure de la SORTIE
        le dit -- le cablage avait l'air juste.*

        ⚠️⚠️ ET LA PREMIERE VERSION DE CE CONTROLE ETAIT TROP ETROITE : elle
        n'epinglait que les `return` litteraux portant `statut_rag`, c'est-a-
        dire LE SEUL CHEMIN DE SUCCES. Les trois chemins d'echec passent par
        `sortie_completee(GABARIT_SORTIE, ...)` et rendaient donc une cle de
        MOINS -- ce que `CS-1` a vu et pas moi. *Le filet avait le defaut du
        chantier : il regardait la ou j'avais corrige.* On epingle desormais
        LE GABARIT, qui est ce qui garantit les quatre chemins.
        """
        from direction_non_vie.tarification.a1_ingestion.agent import (
            GABARIT_SORTIE,
        )
        self.assertIn(
            'rapport_mapping', GABARIT_SORTIE,
            'la cle n est pas au gabarit : les chemins d ECHEC d A1 ne la '
            'porteront pas, et A6 lira un litteral quand A1 aura echoue')
        source = _A1.read_text(encoding='utf-8')
        arbre = ast.parse(source)
        racines = [n for n in ast.walk(arbre)
                   if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict)
                   and 'statut_rag' in {k.value for k in n.value.keys
                                        if isinstance(k, ast.Constant)}]
        self.assertTrue(racines, 'le dict rendu par A1 a change de forme')
        for n in racines:
            cles = {k.value for k in n.value.keys if isinstance(k, ast.Constant)}
            self.assertIn(
                'rapport_mapping', cles,
                f'le dict rendu a a1:{n.lineno} ne porte pas '
                f'`rapport_mapping` a la racine : A6 ne le verra pas')
        # ⚠️ ET A6 LE LIT BIEN DEPUIS LA RACINE.
        a6 = (pathlib.Path(_ICI) / 'a6_comparaison' / 'agent.py'
              ).read_text(encoding='utf-8')
        self.assertIn("(result_a1 or {}).get('rapport_mapping')", a6,
                      'A6 ne relaie plus le rapport de mapping d A1')
        print(f'    MC-8 la cle est a la racine des {len(racines)} sorties d A1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
