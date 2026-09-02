"""⚠️⚠️ UNE QUESTION, UN VERDICT — A1 NE JUGE PLUS CE QUI N'EST PAS À LUI.

Étape ⑤-③ du chantier 1-B, arbitrée par Selasse le 02/09/2026 : *rendre à
chacun sa propre question, ni réparer ni supprimer.*

```
  DONNEE REELLE, 12 654 contrats -- AVANT
    A1     : ROUGE, score 98,50
    couche : ne bloque pas
    cause du ROUGE : cout_total_sinistres_negatifs 1 116 (8,82 %)
                     incoh_sin_sans_cout             436 (3,45 %)
    -> NI L'UN NI L'AUTRE n'est dans CODES_DISQUALIFIANTS
```

A1 mettait un vrai portefeuille au ROUGE sur exactement les types que
l'arbitrage avait délibérément écartés — et la contradiction jouait **dans les
deux sens** : sur le fichier témoin A1 disait AMBRE pendant que la couche
BLOQUAIT.

> *La contradiction ne venait pas de deux mécanismes qui coexistent, mais d'un
> mécanisme qui répondait à la question de l'autre.*

⚠️ CE N'EST NI UNE RÉPARATION NI UNE SUPPRESSION. A1 garde ce dont il est la
SEULE source — complétude de **toutes** les colonnes, doublons de forme,
granularité, provenance de l'identité, coercition. La couche qualité devient
la seule autorité sur « ces lignes sont-elles tarifables ».

⚠️⚠️ ET IL N'Y RÉPONDAIT PAS SEULEMENT EN DOUBLE : IL Y RÉPONDAIT FAUX.

```
  donnees EN MOIS, plan declarant `mois` (borne de la couche = 12)
    A1     : expo_ok_pct = 0,00 %   score 82,35   <- borne (0,1] CODEE EN DUR
    couche : AUCUNE anomalie
```

C'est le défaut que `qualite/C3` a fermé dans la couche — une hypothèse
annuelle muette — et il survivait dans A1. La borne vient désormais de la
**même source unique**, `borne_exposition`.

⚠️ LE FAIT SURVIT, SEUL LE VERDICT PART. `aberrants` et `alertes_aberrants`
restent publiés ; `expo_ok_pct` reste publié. *Retirer un verdict n'efface pas
le fait — c'est même tout l'objet.*
"""
import contextlib
import dataclasses
import inspect
import io
import logging
import pathlib
import unittest

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire
from core.qualite_donnees import CODES_DISQUALIFIANTS, controler_qualite
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_PLAN = PlanTarifaire.depuis_yaml(str(_RACINE / 'plans' / 'auto.yaml'))
_E, _F, _C = _PLAN.exposition, _PLAN.cible_frequence, _PLAN.cible_cout
_ID = _PLAN.identifiant_contrat
_SERVICES = _RACINE / 'direction_non_vie' / 'tarification' / 'services'


def _cadre(n=1_000, seed=9, expo=None):
    rng = np.random.default_rng(seed)
    nb = rng.integers(0, 3, n).astype(float)
    return pd.DataFrame({
        _E: np.ones(n) if expo is None else expo, _F: nb,
        _C: np.where(nb > 0, rng.uniform(500, 5000, n).round(2), 0.0),
        'prime_acquise': (200 + np.arange(n) * 0.01).round(2)})


def _a1(df, plan=_PLAN):
    with contextlib.redirect_stdout(io.StringIO()):
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return AgentA1Ingestion().run(sous_branche='auto',
                                          dataframe=df.copy(), plan=plan)
        finally:
            logging.disable(precedent)


def _reel():
    d = pd.read_csv(_RACINE / 'data' / 'PG_2017_CLAIMS_YEAR0.csv')
    g = d.groupby(['id_client', 'id_vehicle']).agg(
        **{_F: ('claim_nb', 'sum'), _C: ('claim_amount', 'sum')}).reset_index()
    g[_ID] = g['id_client'].astype(str) + '-' + g['id_vehicle'].astype(str)
    g[_E] = 1.0
    return g[[_ID, _E, _F, _C]]


class TestA1QualiteDuFichier(unittest.TestCase):

    def test_QF_1_les_aberrants_ne_font_plus_le_statut_d_A1(self):
        """⚠️⚠️ LE CŒUR DE L'ARBITRAGE, SUR LA VRAIE DONNÉE."""
        r = _a1(_reel())
        self.assertEqual(
            r['statut_rag'], 'VERT',
            "A1 juge encore une question qui n'est pas la sienne")
        self.assertAlmostEqual(float(r['score_qual']), 100.0, places=2)
        self.assertTrue(r['qualite']['aberrants'],
                        'le temoin ne porte plus d aberrants : la mesure ne '
                        'prouverait rien')
        print(f"    OK QF-1 donnee reelle : A1 {r['statut_rag']} "
              f"{float(r['score_qual']):.2f} malgre "
              f"{len(r['qualite']['aberrants'])} type(s) d'aberrants")

    def test_QF_2_A1_les_DETECTE_et_les_PUBLIE_toujours(self):
        """⚠️ Retirer un VERDICT n'efface pas le FAIT — c'est tout l'objet."""
        q = _a1(_reel())['qualite']
        self.assertIn('cout_total_sinistres_negatifs', q['aberrants'])
        self.assertEqual(q['aberrants']['cout_total_sinistres_negatifs'], 1116)
        self.assertTrue(q['alertes_aberrants'])
        self.assertGreaterEqual(q['nb_types_aberrants'], 2)
        print(f"    OK QF-2 les faits survivent : {q['aberrants']}")

    def test_QF_3_ceux_que_A1_signalait_sont_HORS_de_la_liste(self):
        """⚠️⚠️ LA MESURE QUI A TRANCHÉ : A1 mettait au ROUGE exactement les
        types que l'arbitrage a écartés. *Deux verdicts sur la même question.*
        """
        # ⚠️⚠️ LA CORRESPONDANCE EST EXPLICITE, ET LE SCEAU L'A EXIGÉ. Ma
        # première version cherchait le nom de COLONNE d'A1 comme sous-chaîne
        # des codes de la couche : `cout_total_sinistres` n'apparaît nulle part
        # dans `cout_net_negatif`, donc l'assertion passait quoi qu'il arrive.
        # *Deux vocabulaires ne se rapprochent pas par ressemblance de
        # chaînes ; il faut dire QUI correspond à QUI.*
        equivalences = {
            'cout_total_sinistres_negatifs': 'cout_net_negatif',
            'incoh_sin_sans_cout': 'incoherence_sin_sans_cout',
            'nb_sinistres_negatifs': 'frequence_negative',
            'exposition_nulle_ou_negative': 'exposition_non_positive',
        }
        q = _a1(_reel())['qualite']
        vus = sorted(q['aberrants'])
        inconnus = [c for c in vus if c not in equivalences]
        self.assertEqual(
            inconnus, [],
            f"A1 signale des types sans equivalent connu : {inconnus} — la "
            f"correspondance doit etre tenue a jour, sinon ce controle cesse "
            f"de mesurer")
        for cle in vus:
            self.assertNotIn(
                equivalences[cle], CODES_DISQUALIFIANTS,
                f"{cle} correspond a {equivalences[cle]}, qui EST "
                f"disqualifiant : le temoin ne mesure plus la contradiction "
                f"d'origine")
        print(f"    OK QF-3 {vus} -> {[equivalences[c] for c in vus]} : "
              f"aucun n'est dans la liste disqualifiante")

    def test_QF_4_la_borne_d_exposition_vient_du_PLAN(self):
        """⚠️⚠️ IL N'Y RÉPONDAIT PAS SEULEMENT EN DOUBLE, IL Y RÉPONDAIT FAUX.

        Données en mois, plan déclarant `mois` : la borne codée en dur `(0,1]`
        déclarait **0,00 %** d'expositions conformes, là où la couche ne voit
        aucune anomalie.
        """
        rng = np.random.default_rng(5)
        df = _cadre(expo=rng.uniform(1, 11, 1_000).round(2))
        plan_mois = dataclasses.replace(_PLAN, unite_exposition='mois')

        q = _a1(df, plan_mois)['qualite']
        self.assertAlmostEqual(q['expo_ok_pct'], 100.0, places=2,
                               msg='la borne reste codee en dur')
        rapport = controler_qualite(df.copy(), plan_mois)
        self.assertFalse(rapport.bloque)

        # Second sens : sous un plan ANNUEL, la meme donnee est hors borne.
        q2 = _a1(df, _PLAN)['qualite']
        self.assertLess(q2['expo_ok_pct'], 1.0,
                        "la borne ne suit plus l'unite declaree dans l'autre "
                        "sens : elle ne mesure plus rien")
        print(f"    OK QF-4 meme donnee : {q['expo_ok_pct']:.2f} % sous un "
              f"plan `mois`, {q2['expo_ok_pct']:.2f} % sous un plan `annee`")

    def test_QF_5_ni_les_aberrants_ni_l_exposition_n_entrent_dans_le_SCORE(
            self):
        """⚠️ Un score est un verdict. Le retirer du statut sans le retirer du
        score aurait laissé la contradiction sous une autre forme.

        Assiette : le CORPS de la fonction, par lecture du source.
        """
        src = inspect.getsource(AgentA1Ingestion._valider_qualite)
        formule = src[src.index('score = min('):src.index('score = min(') + 320]
        for interdit in ('penalite_aberrants', 'expo_ok'):
            self.assertNotIn(
                interdit, formule,
                f"'{interdit}' pese encore sur le score d'A1")
        df = _cadre()
        df.loc[:299, _F] = -1.0        # 30 % d'aberrants
        df.loc[:299, _C] = 0.0
        r = _a1(df)
        self.assertAlmostEqual(float(r['score_qual']), 100.0, places=2)
        self.assertEqual(r['statut_rag'], 'VERT')
        print("    OK QF-5 30 % d'aberrants : score 100,00 et VERT -- le "
              "fichier est bien forme, c'est tout ce qu'A1 dit")

    def test_QF_6_second_sens_A1_juge_TOUJOURS_ce_qui_est_a_lui(self):
        """⚠️⚠️ SANS CE SENS, LE LOT AURAIT DÉSARMÉ A1.

        Complétude et doublons restent son verdict : il est la seule source
        sur **toutes** les colonnes, là où la couche ne voit que les trois
        grandeurs.
        """
        creux = _cadre()
        creux['facteur_client'] = np.nan          # colonne entierement vide
        r = _a1(creux)
        self.assertLess(r['qualite']['taux_completude'], 95.0)
        self.assertIn(r['statut_rag'], ('AMBRE', 'ROUGE'),
                      "une colonne entierement vide ne fait plus reagir A1")

        double = pd.concat([_cadre(n=900), _cadre(n=900).head(100)],
                           ignore_index=True)
        r2 = _a1(double)
        self.assertGreater(r2['qualite']['taux_doublons'], 1.0)
        self.assertIn(r2['statut_rag'], ('AMBRE', 'ROUGE'),
                      'les doublons de forme ne font plus reagir A1')
        print(f"    OK QF-6 second sens : completude "
              f"{r['qualite']['taux_completude']:.1f} % -> "
              f"{r['statut_rag']} | doublons "
              f"{r2['qualite']['taux_doublons']:.1f} % -> {r2['statut_rag']}")

    def test_QF_7_plus_aucune_CONTRADICTION_entre_les_deux_verdicts(self):
        """⚠️⚠️ ELLE JOUAIT DANS LES DEUX SENS : A1 criait quand la couche se
        taisait, et se taisait quand la couche criait.

        Désormais les deux répondent à des questions différentes — et le
        fichier témoin le montre : A1 dit « bien formé », la couche dit « pas
        tarifable ». *Deux réponses cohérentes, pas deux verdicts opposés.*
        """
        temoin = _cadre(seed=31)
        temoin.loc[0:29, _F] = -1.0
        temoin.loc[0:29, _C] = 0.0
        temoin.loc[200:229, _E] = 0.0

        r = _a1(temoin)
        rapport = controler_qualite(temoin.copy(), _PLAN)
        self.assertEqual(r['statut_rag'], 'VERT',
                         "A1 juge encore la tarifabilite")
        self.assertTrue(rapport.bloque,
                        'le temoin ne bloque plus : la mesure ne prouve rien')
        self.assertAlmostEqual(r['qualite']['taux_completude'], 100.0,
                               places=2)

        reel = _reel()
        r2 = _a1(reel)
        self.assertEqual(r2['statut_rag'], 'VERT')
        self.assertFalse(controler_qualite(reel.copy(), _PLAN).bloque)
        print("    OK QF-7 temoin : A1 VERT + couche BLOQUE | reel : A1 VERT "
              "+ couche passe -- deux questions, deux reponses")

    def test_QF_8_les_libelles_distinguent_les_deux_verdicts(self):
        """⚠️ Sans ce mot, deux verdicts cohérents se lisent encore comme une
        contradiction. *Le texte qui accompagne un comportement se relit quand
        il change.*"""
        src = (_SERVICES / 'tarif_excel.py').read_text(encoding='utf-8')
        for attendu in ('QUALITÉ DU FICHIER (lisibilité, complétude, identité)',
                        'Score qualité du fichier',
                        'Statut RAG — qualité du fichier',
                        'Exposition dans la borne déclarée au plan'):
            self.assertIn(attendu, src, f'libelle manquant : {attendu!r}')
        for perime in ('▶ QUALITÉ DES DONNÉES"', 'Exposition conforme [0,1]'):
            self.assertNotIn(perime, src,
                             f'libelle perime encore present : {perime!r}')
        print("    OK QF-8 les 4 libelles distinguent le FICHIER (A1) des "
              "DONNEES (couche)")

    def test_QF_9_le_seuil_mort_ne_traine_pas(self):
        """⚠️ Un seuil qui ne gouverne plus rien mais reste écrit laisse croire
        qu'un contrôle existe. *La forme de `socle/C2`, en plus discret.*"""
        src = (_RACINE / 'direction_non_vie' / 'tarification' / 'a1_ingestion'
               / 'agent.py').read_text(encoding='utf-8')
        self.assertNotIn("'aberrants_taux_rouge':", src,
                         'le seuil mort est encore declare')
        self.assertNotIn("SEUILS_QUALITE['aberrants_taux_rouge']", src)
        self.assertIn('aberrants_taux_rouge', src,
                      "son RETRAIT n'est plus explique : un lecteur croira a "
                      "un oubli")
        print("    OK QF-9 seuil retire, et son retrait est explique sur "
              "place")


if __name__ == '__main__':
    unittest.main(verbosity=2)
