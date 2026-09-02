"""Controles positifs — `qualite/C8`, RANG 1 : une charge NETTE peut etre negative.

CE QUE CE FICHIER PROUVE, ET POURQUOI C'EST UN RANG 1
─────────────────────────────────────────────────────

La regle 1 classait `cout_total_sinistres < 0` comme **IMPOSSIBLE
MATHEMATIQUEMENT** et EXCLUAIT la ligne. ⚠️⚠️ **La doctrine confondait deux
grandeurs** : un COUT (un prix) est >= 0, mais une CHARGE NETTE -- paiements
moins recours -- est de signe quelconque. Subrogation, sauvetage, recuperation
sur tiers la rendent negative, et c'est NORMAL.

═══ MESURE SUR LA SEULE DONNEE REELLE VERSIONNEE ═══

`data/PG_2017_CLAIMS_YEAR0.csv`, 14 243 sinistres :

```
  AU SINISTRE : 1 263 montants negatifs / 14 243  =  8,9 %
  AU CONTRAT  : 1 116 / 12 654  =  8,82 %   <- au-dessus du seuil d escalade
  charge nette des cas negatifs : -563 749 EUR

  charge NETTE (tous)  : 11 724 608 EUR  ->  prime moyenne   926,55 EUR
  charge si on EXCLUT  : 12 288 358 EUR  ->  prime moyenne 1 065,03 EUR
  -> EXCLURE SUR-TARIFE DE 14,9 %, et perd 1 116 contrats
```

═══ ET AUCUN INDICE NE PERMET DE TRANCHER ═══

Arbitre par Selasse : erreurs de saisie ET vrais recours coexistent, le second
cas est rare, ni l'un ni l'autre n'est la regle. Les deux discriminants mesures
sur les 1 116 cas :

```
                                        n     part   ratio median
  AVEC paiement positif au contrat      80    7,2%       0,33
  SANS aucun paiement positif        1 036   92,8%       0,52

  parmi les 80 couverts : 44 DEPASSENT le paiement du contrat
  distributions du ratio  couverts     0,02 -> 1,05
                          non couverts 0,00 -> 1,87
```

**Les deux distributions se chevauchent entierement, et les deux groupes se
disqualifient mutuellement.** Aucun seuil ne les separe.

═══ LES TROIS GESTES, INDISSOCIABLES ═══

  A. `cout < 0` passe en REGLE 3 : signale, CONSERVE, ne decide rien.
  B. une ANNEXE DE REVUE : un cas par ligne, pour que l'actuaire VOIE.
  C. une QUESTION NEUTRE a trois issues, avec EMPREINTE des positions.

⚠️⚠️ LA QUESTION EST NEUTRE, ET C'EST LE POINT DE CONCEPTION LE PLUS IMPORTANT.
La formulation d'abord envisagee -- « ces cas SEMBLENT ETRE DES RECOURS
LEGITIMES, confirmez-vous ? » -- ferait affirmer au systeme une conclusion que
la donnee ne porte pas. *Le motif exact de cet audit.*

⚠️ RGPD : deux surfaces. La SYNTHESE (rapport signe, circule) ne cite ni valeur
ni index -- deux sentinelles le verifient et ce lot ne les affaiblit pas.
L'ANNEXE ne quitte pas le poste de l'actuaire et porte la POSITION dans SON
fichier, jamais un identifiant client.
"""

from __future__ import annotations

import dataclasses
import logging
import unittest
import warnings

import pandas as pd

from core.qualite_donnees import (
    EMPREINTE_REVUE_SCHEMA,
    annexe_revue_charges_negatives,
    controler_qualite,
    empreinte_positions,
    question_charges_negatives,
    synthese_qualite_donnees,
)
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)

_PLAN = dataclasses.replace(_PLAN_AUTO, identifiant_contrat=None)


def _reel() -> pd.DataFrame:
    """Le portefeuille AGREGE depuis la seule donnee reelle versionnee.

    ⚠️ C'est l'assiette que la couche qualite recoit : UNE LIGNE PAR CONTRAT.
    Le detail des sinistres n'y est pas -- et c'est precisement ce qui l'empeche
    de trancher.
    """
    d = pd.read_csv('data/PG_2017_CLAIMS_YEAR0.csv')
    g = d.groupby(['id_client', 'id_vehicle', 'id_year']).agg(
        cout_total_sinistres=('claim_amount', 'sum'),
        nb_sinistres=('claim_nb', 'sum')).reset_index()
    g['exposition'] = 1.0
    for c in _PLAN.colonnes_attendues():
        if c not in g.columns:
            g[c] = 0.5
    return g


def _controler(df, validee_par=None):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return controler_qualite(df, _PLAN,
                                     qualite_validee_par=validee_par,
                                     horodatage='2026-08-31T00:00:00')
        finally:
            logging.disable(precedent)


class TestA_LaChargeNetteNEstPlusExclue(unittest.TestCase):
    """GESTE A — `qualite/C8` : regle 1 -> regle 3."""

    def test_LE_TEST_QUI_FERME_aucune_ligne_n_est_exclue_pour_charge_negative(self):
        """⚠️⚠️ Sur la VRAIE donnee : 1 116 contrats etaient exclus, et la prime
        moyenne montait de 14,9 %."""
        g = _reel()
        r = _controler(g)
        self.assertEqual(len(r.exclusions), 0,
                         f"des lignes sont encore exclues : "
                         f"{[(a.code, a.nb_lignes) for a in r.exclusions]}")
        self.assertEqual(r.lignes_retenues, len(g),
                         'des contrats sont perdus')
        codes = [a.code for a in r.signalements]
        self.assertIn('cout_net_negatif', codes)
        print(f"    C8-1 {len(g):,} contrats reels : 0 exclusion, "
              f"{r.lignes_retenues:,} retenus")

    def test_le_motif_nomme_LES_DEUX_lectures_possibles(self):
        """⚠️ Le systeme ne tranche pas : il doit donc dire les deux."""
        a = next(x for x in _controler(_reel()).signalements
                 if x.code == 'cout_net_negatif')
        self.assertIn('RECOURS', a.description)
        self.assertIn('ERREUR DE SAISIE', a.description)
        self.assertIn('CONSERVEES', a.description)
        print("    C8-2 le motif nomme recours ET erreur, et dit que les "
              "lignes sont conservees")

    def test_SECOND_SENS_les_vraies_impossibilites_restent_EXCLUES(self):
        """⚠️⚠️ SANS CE SENS, LE LOT AURAIT DESARME LA REGLE 1. Une frequence
        negative et une exposition nulle restent impossibles."""
        df = _portefeuille_auto(600, seed=3)
        df.loc[df.index[:20], 'nb_sinistres'] = -1.0
        df.loc[df.index[20:40], 'exposition'] = 0.0
        r = _controler(df)
        codes = {a.code for a in r.exclusions}
        self.assertIn('frequence_negative', codes)
        self.assertIn('exposition_non_positive', codes)
        print(f"    C8-3 second sens : {sorted(codes)} restent en regle 1")


class TestB_LAnnexeDeRevue(unittest.TestCase):
    """GESTE B — l'actuaire doit VOIR chaque cas."""

    def test_un_cas_par_ligne_avec_ses_indices(self):
        g = _reel()
        ann = annexe_revue_charges_negatives(_controler(g), g)
        self.assertEqual(len(ann), 1116,
                         f'{len(ann)} cas listes pour 1 116 attendus')
        for x in ann[:50]:
            self.assertLess(x['charge_nette'], 0)
            self.assertGreater(x['ratio_cout_moyen_positif'], 0)
        print(f"    C8-4 annexe : {len(ann):,} cas, chacun avec sa position, "
              f"sa charge nette et son ratio")

    def test_l_annexe_ne_publie_AUCUN_identifiant_client(self):
        """⚠️⚠️ RGPD. La POSITION est une coordonnee dans le fichier de
        l'actuaire ; l'identifiant client n'y a pas sa place."""
        g = _reel()
        ann = annexe_revue_charges_negatives(_controler(g), g)
        interdits = {'id_client', 'id_vehicle', 'identifiant_contrat'}
        for x in ann[:100]:
            self.assertEqual(set(x) & interdits, set())
        self.assertEqual(sorted(ann[0]),
                         ['charge_nette', 'position', 'ratio_cout_moyen_positif'])
        print("    C8-5 RGPD : position, charge nette, ratio — aucun "
              "identifiant client")

    def test_SECOND_SENS_un_portefeuille_SAIN_ne_produit_AUCUNE_annexe(self):
        """⚠️ Une annexe toujours produite cesse d'etre un signal."""
        df = _portefeuille_auto(600, seed=3)
        self.assertEqual(annexe_revue_charges_negatives(_controler(df), df), [])
        print("    C8-6 second sens : portefeuille sain -> annexe vide")


class TestC_LaQuestionNeutre(unittest.TestCase):
    """GESTE C — la question ne suggere RIEN."""

    def test_LE_TEST_QUI_FERME_la_question_dit_ce_qu_elle_NE_SAIT_PAS(self):
        g = _reel()
        q = question_charges_negatives(_controler(g), g)
        self.assertIn('NE PEUT PAS TRANCHER', q)
        self.assertIn('detail des sinistres', q)
        self.assertIn('RECOURS', q)
        self.assertIn('ERREUR DE SAISIE', q)
        print(f"    C8-7 la question dit son incapacite : "
              f"« ...{q[q.find('NE PEUT PAS'):q.find('NE PEUT PAS')+52]}... »")

    def test_elle_n_est_JAMAIS_orientee(self):
        """⚠️⚠️ LE POINT DE CONCEPTION LE PLUS IMPORTANT. La formulation
        d'abord envisagee suggerait la reponse. La mesure l'interdit."""
        q = question_charges_negatives(_controler(_reel()), _reel())
        for oriente in ('semblent etre', 'semblent être', 'probablement',
                        'confirmez-vous', 'il s agit de'):
            with self.subTest(mot=oriente):
                self.assertNotIn(oriente.lower(), q.lower())
        print("    C8-8 aucune formulation orientee dans la question")

    def test_les_TROIS_issues_sont_proposees(self):
        q = question_charges_negatives(_controler(_reel()), _reel())
        # La troisieme issue disait << LISTE des positions >> ; le mot a ete
        # retire le 02/09 parce que la question CIRCULE desormais et que la
        # sentinelle RGPD voisine interdit ce mot dans la synthese. *Les trois
        # issues proposees sont INCHANGEES.*
        for issue in ('CONSERVER tout', 'EXCLURE tout', 'LISTE des cas'):
            with self.subTest(issue=issue):
                self.assertIn(issue, q)
        print("    C8-9 trois issues proposees, aucune n'est suggeree")

    def test_elle_ne_cite_AUCUN_chiffre_qu_elle_ne_sache_produire(self):
        """⚠️⚠️ MA PREMIERE VERSION ANNONCAIT « 80 couverts / 1 036 non
        couverts ». **Cette couche ne peut pas les calculer** : elle recoit une
        ligne par CONTRAT, jamais le detail des sinistres. *Annoncer un chiffre
        qu'on ne sait pas produire est le defaut que ce lot corrige.*"""
        q = question_charges_negatives(_controler(_reel()), _reel())
        for interdit in ('couvert', 'paiement positif', '1 036', '80 '):
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, q)
        print("    C8-10 aucun chiffre non calculable a cette couche")


class TestC_bis_LEmpreinte(unittest.TestCase):
    """⚠️⚠️ Sans elle, on sait QU'IL a repondu, pas SUR QUOI."""

    def test_l_empreinte_change_quand_les_CAS_changent(self):
        a = empreinte_positions([1, 2, 3])
        self.assertEqual(a, empreinte_positions([3, 2, 1]),
                         "l'ordre change l'empreinte : elle n'est pas stable")
        self.assertNotEqual(a, empreinte_positions([1, 2, 4]),
                            "un cas different rend la MEME empreinte : la "
                            "reponse resterait valable sur d'autres donnees")
        print(f"    C8-11 empreinte stable a l'ordre, sensible au contenu : "
              f"{a}")

    def test_elle_porte_sa_VERSION_DE_SCHEMA(self):
        """⚠️ Leçon reprise de `PlanTarifaire.empreinte()` : un comparateur lit
        le schema SANS recalculer, et une empreinte sans prefixe se reconnait
        comme HERITEE plutot que fausse."""
        e = empreinte_positions([1, 2, 3])
        self.assertTrue(e.startswith(f'r{EMPREINTE_REVUE_SCHEMA}:'), e)
        print(f"    C8-12 prefixe de schema present : « {e.split(':')[0]} »")

    def test_la_question_PORTE_l_empreinte(self):
        g = _reel()
        r = _controler(g)
        q = question_charges_negatives(r, g)
        a = next(x for x in r.signalements if x.code == 'cout_net_negatif')
        self.assertIn(empreinte_positions(a.index), q,
                      "la question ne porte pas l'empreinte de ses cas : la "
                      "reponse ne serait attachee a aucun contenu")
        print("    C8-13 la question porte l'empreinte de ses propres cas")


class TestLaQuestionATTEINT_LE_BLOCAGE(unittest.TestCase):
    """GESTE C, cablage — la question doit ATTEINDRE celui qui decide.

    ⚠️⚠️ `vulture` a signale `question_charges_negatives` comme fonction MORTE :
    elle n'avait AUCUN appelant de production. *C'est la forme de `socle/C2` --
    de la plomberie posee que rien n'alimente -- dans le lot meme qui ferme ce
    motif.* Le blocage est le moment ou l'actuaire decide : la question y est.
    """

    def test_la_levee_QualiteBloquante_PORTE_la_question(self):
        from core.qualite_donnees import QualiteBloquante
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        # ⚠️⚠️ LE VÉHICULE DU BLOCAGE A CHANGÉ LE 02/09, ET C'EST L'ARBITRAGE
        # DE SELASSE. Une charge NETTE négative n'escalade plus : mesurée à
        # 8,82 % sur cette même donnée réelle, elle est légitime et bloquait un
        # vrai portefeuille. On co-plante donc une anomalie DISQUALIFIANTE pour
        # obtenir un blocage. *Ce que ce contrôle prouve est inchangé : quand
        # un blocage survient, sa levée PORTE la question.* Et `LD-11` tient
        # désormais l'autre moitié — la question atteint l'actuaire même SANS
        # blocage, puisque son ancien porteur ne se déclenche plus seul.
        g = _reel().copy()
        g.loc[g.index[:len(g) // 5], 'nb_sinistres'] = -1.0
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            precedent = logging.root.manager.disable
            logging.disable(logging.CRITICAL)
            try:
                with self.assertRaises(QualiteBloquante) as leve:
                    pipeline_complet(g, _PLAN)
            finally:
                logging.disable(precedent)
        motif = str(leve.exception)
        self.assertIn('NE PEUT PAS TRANCHER', motif,
                      "la levee ne porte pas la question : l'actuaire bloque "
                      "sans savoir ce qu'on lui demande de juger")
        self.assertIn('Empreinte des cas', motif)
        self.assertIn('CONSERVER tout', motif)
        print("    C8-15 la levee du chemin declaratif porte la question, ses "
              "trois issues et son empreinte")


class TestLaSyntheseSigneeRESTE_SANS_INDEX(unittest.TestCase):
    """⚠️⚠️ SECOND SENS RGPD — ce lot ne doit pas affaiblir la regle posee."""

    def test_la_synthese_ne_publie_ni_index_ni_valeur_de_ligne(self):
        g = _reel()
        texte = synthese_qualite_donnees(_controler(g)) or ''
        self.assertNotIn('[0,', texte, 'des index de lignes sortent')
        self.assertNotIn('position', texte.lower(),
                         'la synthese publie des positions : elle doit rester '
                         'circulable')
        self.assertIn('cout_net_negatif', texte)
        print("    C8-14 second sens : la synthese signee reste sans index ni "
              "position")


if __name__ == '__main__':
    unittest.main()
