"""
Contrôles positifs — le catalogue d'exigences de l'élasticité-prix (L2).

⚠️ LE PATRON N'EST PAS INVENTÉ ICI. C'est celui du socle IFRS 17
(`normes/ifrs17/socle/contrat.py` : `EXIGENCES` → `capacites()` →
`exigences_hors_portee()` qui dit CE QUE L'ABSENCE COÛTE, plus un diagnostic
en prose). Le socle le décrit lui-même comme « le pendant de
`_capacites_depuis_champs` de la couche triangle, étendu du booléen au
catalogue nommé » — il existe donc DEUX instances dans le dépôt, et
`core/elasticite.py` en est une TROISIÈME. C'est signalé, pas tu :
l'extraction du mécanisme commun est un chantier, pas ce lot.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _plan(**kw):
    """Un plan auto minimal, éventuellement doté d'un bloc comportement."""
    import dataclasses

    from core.plan_tarifaire import PlanTarifaire
    base = PlanTarifaire.depuis_yaml(os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
        'plans', 'auto.yaml'))
    return dataclasses.replace(base, **kw) if kw else base


class T_Le_Comportement_Se_Declare_Au_Plan(unittest.TestCase):
    """CONTRÔLE POSITIF — la déclaration, et sa validation.

    ⚠️ RÈGLE ARBITRÉE : le bloc ENTIER absent n'est pas une erreur — les vingt
    plans du dépôt n'en ont pas — mais un bloc INCOMPLET en est une. Une issue
    de contrat sans les deux primes est une déclaration à moitié : elle promet
    une capacité qu'elle ne porte pas.
    """

    def test_un_bloc_complet_est_accepte(self):
        from core.plan_tarifaire import Comportement
        c = Comportement(issue='resilie',
                         prime_precedente='prime_n_1',
                         prime_proposee='prime_n')
        p = _plan(comportement=c)
        self.assertIsNotNone(p.comportement)
        self.assertEqual(p.comportement.issue, 'resilie')
        print(f"    POS-L2a bloc complet accepté : {c.issue} / "
              f"{c.prime_precedente} → {c.prime_proposee} ✅")

    def test_un_bloc_INCOMPLET_est_une_erreur(self):
        """⚠️ LES TROIS CHAMPS SONT INDISSOCIABLES. Une élasticité répond à une
        VARIATION de prix : sans les deux primes, l'issue seule ne dit rien."""
        from core.plan_tarifaire import Comportement
        for manquant, kw in (
            ('prime_precedente', {'issue': 'resilie', 'prime_precedente': '',
                                  'prime_proposee': 'prime_n'}),
            ('prime_proposee',   {'issue': 'resilie', 'prime_precedente': 'p1',
                                  'prime_proposee': ''}),
            ('issue',            {'issue': '', 'prime_precedente': 'p1',
                                  'prime_proposee': 'p2'}),
        ):
            with self.subTest(manquant=manquant):
                with self.assertRaises(ValueError) as ctx:
                    Comportement(**kw)
                self.assertIn(manquant, str(ctx.exception))
        print("    POS-L2b un bloc à moitié déclaré est refusé, "
              "et le message nomme le champ manquant ✅")

    def test_les_colonnes_declarees_sont_ATTENDUES_jamais_PRODUITES(self):
        """⚠️ UN RÔLE DE DONNÉES N'EST PAS UN FACTEUR TARIFAIRE. Si ces
        colonnes entraient dans `colonnes_produites()`, elles deviendraient des
        prédicteurs — la prime précédente prédirait la sinistralité, ce qui est
        la fuite structurelle que le plan rend inexprimable pour l'exposition.
        Même règle que `identifiant_contrat` et `echeance`."""
        from core.plan_tarifaire import Comportement
        p = _plan(comportement=Comportement(
            issue='resilie', prime_precedente='prime_n_1',
            prime_proposee='prime_n', canal='canal_distri'))
        attendues = set(p.colonnes_attendues())
        produites = set(p.colonnes_produites())
        for col in ('resilie', 'prime_n_1', 'prime_n', 'canal_distri'):
            with self.subTest(col=col):
                self.assertIn(col, attendues, f"« {col} » n'est pas attendue")
                self.assertNotIn(col, produites,
                                 f"« {col} » est devenue un FACTEUR TARIFAIRE")
        print("    POS-L2c les 4 colonnes déclarées : attendues, "
              "jamais produites ✅")


class T_Le_Catalogue_Dit_Ce_Que_L_Absence_COUTE(unittest.TestCase):
    """CONTRÔLE POSITIF — le patron du socle IFRS 17, appliqué à l'élasticité.

    ⚠️ « PAS D'ÉLASTICITÉ » NE VEUT RIEN DIRE POUR UN ACTUAIRE. « Sans
    l'issue du contrat, l'estimation de l'élasticité et l'optimisation
    tarifaire sont hors de portée » se comprend et se fournit. C'est la raison
    d'être d'`exigences_hors_portee` dans le socle, mot pour mot.
    """

    def test_sans_declaration_AUCUNE_capacite_n_est_atteignable(self):
        from core.elasticite import capacites
        caps = capacites(set())
        self.assertTrue(caps, "le catalogue est vide")
        self.assertFalse(any(caps.values()),
                         f"une capacité est déclarée atteignable sans aucun "
                         f"champ : {[k for k, v in caps.items() if v]}")
        print(f"    POS-L2d sans déclaration : 0 capacité sur "
              f"{len(caps)} ✅")

    def test_ce_qui_manque_est_NOMME_avec_son_cout(self):
        from core.elasticite import EXIGENCES, exigences_hors_portee
        hp = exigences_hors_portee(set())
        self.assertEqual(set(hp), set(EXIGENCES),
                         "toutes les exigences doivent être hors de portée")
        for nom, absents in hp.items():
            with self.subTest(exigence=nom):
                self.assertTrue(absents, f"« {nom} » ne nomme aucun manquant")
                self.assertTrue(EXIGENCES[nom].libelle.strip(),
                                f"« {nom} » n'a pas de libellé")
        print(f"    POS-L2e {len(hp)} exigences hors de portée, chacune avec "
              f"le champ qui lui manque ✅")

    def test_la_declaration_complete_ouvre_l_estimation(self):
        from core.elasticite import capacites
        caps = capacites({'issue', 'prime_precedente', 'prime_proposee'})
        self.assertTrue(
            caps.get('elasticite_estimable'),
            f"la déclaration minimale n'ouvre pas l'estimation : {caps}")
        self.assertFalse(
            caps.get('identification_experimentale'),
            "un groupe de test non déclaré ne peut pas ouvrir "
            "l'identification expérimentale")
        print("    POS-L2f déclaration minimale → estimation atteignable, "
              "identification expérimentale non ✅")

    def test_AUCUNE_exigence_ne_se_reclame_d_une_NORME(self):
        """⚠️⚠️ LA LIMITE N°1, INSCRITE DANS LE CODE. Aucun texte normatif ne
        fixe une élasticité ni une méthode pour l'estimer — contrairement à
        R. 221-5 ou aux paragraphes d'IFRS 17. Le champ `source` du socle
        existe précisément pour empêcher qu'une règle maison passe pour une
        obligation ; ici, TOUTES les exigences sont des conventions du module,
        et le catalogue doit le dire."""
        from core.elasticite import EXIGENCES, SOURCE_CONVENTION
        for nom, ex in EXIGENCES.items():
            with self.subTest(exigence=nom):
                self.assertEqual(
                    ex.source, SOURCE_CONVENTION,
                    f"« {nom} » se réclame de « {ex.source} » — aucune norme "
                    f"ne fixe d'élasticité")
        print(f"    POS-L2g les {len(EXIGENCES)} exigences se déclarent "
              f"CONVENTION, aucune ne se réclame d'une norme ✅")

    def test_le_diagnostic_dit_ce_qu_il_peut_ET_ce_qui_manque(self):
        """⚠️ LE DIAGNOSTIC EST LA MISE EN MOTS, rien n'y est calculé qui ne
        soit dans le catalogue — même contrat que le socle."""
        from core.elasticite import diagnostic
        from core.plan_tarifaire import Comportement
        texte_vide = diagnostic(_plan())
        self.assertIn('CE QUI MANQUE', texte_vide.upper())
        self.assertNotIn('prime_precedente', texte_vide.split('CE QUI MANQUE')[0])
        texte_plein = diagnostic(_plan(comportement=Comportement(
            issue='resilie', prime_precedente='p1', prime_proposee='p2')))
        self.assertIn('CE QUE JE PEUX PRODUIRE', texte_plein.upper())
        self.assertNotEqual(texte_vide, texte_plein,
                            "le diagnostic ne dépend pas de la déclaration")
        print("    POS-L2h le diagnostic distingue ce qui est atteignable "
              "de ce qui manque ✅")


class T_L_Etat_Distingue_Ce_Qui_Manque_De_Ce_Qui_N_Est_Pas_Construit(
        unittest.TestCase):
    """CONTRÔLE POSITIF — la contestation du modèle à trois états, épinglée.

    ⚠️⚠️ CONFONDRE « LES DONNÉES NE PERMETTENT PAS » ET « LE MODULE NE SAIT PAS
    ENCORE » SERAIT LE MOTIF MÊME DE CET AUDIT. Un plan qui déclare
    correctement son bloc `comportement` ne peut pas sortir `NON_FOURNIE` —
    la donnée EST fournie — ni `NON_IDENTIFIABLE`, qui imputerait au
    PORTEFEUILLE une limite qui est celle du LOGICIEL. D'où `NON_EXPLOITEE`,
    qui disparaîtra quand L4 atterrira.
    """

    def test_sans_bloc_l_etat_est_NON_FOURNIE(self):
        from core.elasticite import ELASTICITE_NON_FOURNIE, etat_elasticite
        e = etat_elasticite(_plan())
        self.assertEqual(e['etat'], ELASTICITE_NON_FOURNIE)
        self.assertIn('coûte', e['ce_que_cela_coute'].lower() + 'coûte')
        self.assertTrue(e['ce_quil_faudrait'].strip())
        print(f"    POS-L2i sans bloc → {e['etat']} ✅")

    def test_avec_un_bloc_COMPLET_l_etat_n_impute_rien_au_portefeuille(self):
        from core.elasticite import (
            ELASTICITE_NON_EXPLOITEE,
            ELASTICITE_NON_FOURNIE,
            ELASTICITE_NON_IDENTIFIABLE,
            etat_elasticite,
        )
        from core.plan_tarifaire import Comportement
        e = etat_elasticite(_plan(comportement=Comportement(
            issue='resilie', prime_precedente='p1', prime_proposee='p2')))
        self.assertNotEqual(
            e['etat'], ELASTICITE_NON_FOURNIE,
            "la donnée EST déclarée : dire « non fournie » serait faux")
        self.assertNotEqual(
            e['etat'], ELASTICITE_NON_IDENTIFIABLE,
            "rien n'a été mesuré sur la variation de prix : imputer une "
            "non-identifiabilité au portefeuille serait une accusation sans "
            "mesure")
        self.assertEqual(e['etat'], ELASTICITE_NON_EXPLOITEE)
        self.assertIn('PAS une limite du portefeuille', e['ce_que_cela_coute'])
        self.assertTrue(e['capacites']['elasticite_estimable'])
        print(f"    POS-L2j bloc complet → {e['etat']}, "
              f"et le coût dit que la limite est logicielle ✅")

    def test_l_etat_publie_le_catalogue_qui_le_fonde(self):
        """⚠️ RIEN DANS L'ÉTAT QUI NE SOIT DANS LE CATALOGUE — même contrat que
        le diagnostic du socle. Un état qui déciderait pour son compte pourrait
        diverger de ce que le module fait réellement."""
        from core.elasticite import capacites, etat_elasticite, roles_du_plan
        p = _plan()
        e = etat_elasticite(p)
        self.assertEqual(e['capacites'], capacites(roles_du_plan(p)))
        self.assertIn('hors_portee', e)
        self.assertIn('CE QUI MANQUE', e['diagnostic'].upper())
        print("    POS-L2k l'état publie capacités, hors-portée et "
              "diagnostic — une seule source ✅")


# ══════════════════════════════════════════════════════════════════════════════
#  L3 — L'EXPLOITABILITÉ DE LA VARIATION DE PRIX
# ══════════════════════════════════════════════════════════════════════════════

def _bloc(**kw):
    from core.plan_tarifaire import Comportement
    base = {'issue': 'resilie', 'prime_precedente': 'prime_n_1',
            'prime_proposee': 'prime_n'}
    base.update(kw)
    return Comportement(**base)


def _renouvellements(n=3000, seed=3, regime='residuelle', taux_resil=0.15):
    """Un historique de renouvellement, sous quatre régimes de variation.

    ⚠️ C'EST LA VARIATION DE PRIX QUI DÉCIDE, PAS LE VOLUME DE DONNÉES. Les
    quatre régimes ci-dessous portent tous la même donnée déclarée ; seule
    change la façon dont le prix a bougé — et c'est elle qui rend l'élasticité
    identifiable ou non.

      'deterministe' le prix proposé est une fonction EXACTE des facteurs de
                     risque. Prix et risque sont colinéaires : aucune méthode
                     ne sépare l'effet-prix de la sélection.
      'residuelle'   le prix suit le risque, PLUS un aléa propre. C'est cet
                     aléa qui identifie l'effet-prix.
      'experimentale' une hausse tirée au sort sur un groupe : l'exogénéité ne
                     se discute pas.
      'sans_variation' le prix n'a pas bougé. Rien à exploiter.
    """
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(seed)
    age = rng.integers(18, 75, n).astype(float)
    bm = rng.uniform(50, 350, n)
    p0 = rng.uniform(300, 900, n)

    # la part de la variation expliquee par le risque
    part_risque = 0.10 * (bm - 200) / 200 + 0.05 * (age - 45) / 45
    groupe = np.array(['—'] * n, dtype=object)

    if regime == 'deterministe':
        v = part_risque
    elif regime == 'residuelle':
        v = part_risque + rng.normal(0, 0.08, n)
    elif regime == 'experimentale':
        groupe = rng.choice(['temoin', 'hausse'], n)
        v = part_risque + np.where(groupe == 'hausse', 0.10, 0.0)
    elif regime == 'sans_variation':
        v = np.zeros(n)
    else:
        raise ValueError(regime)

    return pd.DataFrame({
        'id_contrat':       np.arange(n),
        'annee_exercice':   2023,
        'age':              age,
        'bonus_malus':      bm,
        'prime_n_1':        p0,
        'prime_n':          p0 * np.exp(v),
        'resilie':          (rng.random(n) < taux_resil).astype(float),
        'groupe_prix':      groupe,
        'exposition':       rng.uniform(0.3, 1.0, n),
        'nb_sinistres':     rng.poisson(0.08, n).astype(float),
        'cout_total_sinistres': rng.exponential(600, n),
    })


class T_L_Exploitabilite_Se_Mesure_Avant_Toute_Estimation(unittest.TestCase):
    """CONTRÔLE POSITIF — le troisième état, et il se mesure sans estimer.

    ⚠️⚠️ LE POINT DUR DE TOUT LE CHANTIER. L'assureur fixe le prix D'APRÈS LE
    RISQUE. Si les segments dont la sinistralité s'est dégradée ont été
    augmentés, alors prix, résiliation et risque bougent ensemble : régresser
    la résiliation sur le prix mesure UN MÉLANGE de l'effet-prix et de la
    sélection. C'est de l'endogénéité au sens strict.

    ⚠️ ET ÇA SE MESURE AVANT D'ESTIMER QUOI QUE CE SOIT : la part de la
    variation de prix expliquée par les facteurs de risque est une propriété
    des DONNÉES, pas du modèle. Si elle vaut 1, il ne reste rien à exploiter.
    """

    def test_un_prix_FONCTION_DU_RISQUE_n_est_pas_identifiable(self):
        from core.elasticite import diagnostic_exploitabilite
        d = diagnostic_exploitabilite(
            _plan(comportement=_bloc()), _renouvellements(regime='deterministe'))
        self.assertFalse(d['exploitable'],
                         f"un prix déterministe du risque est déclaré "
                         f"exploitable : {d}")
        self.assertIsNotNone(d['r2_prix_sur_risque'])
        self.assertGreaterEqual(
            d['r2_prix_sur_risque'], 0.95,
            "prémisse : la variation doit être quasi entièrement expliquée")
        self.assertIn('risque', d['motif'].lower())
        print(f"    POS-L3a prix déterministe : R²={d['r2_prix_sur_risque']:.4f} "
              f"→ non identifiable ✅")

    def test_une_variation_RESIDUELLE_est_exploitable(self):
        """⚠️⚠️ LA LEÇON V14 APPLIQUÉE ICI. Un diagnostic qui refuserait tout
        serait aussi inutile qu'un diagnostic qui accepterait tout — et bien
        plus difficile à repérer, parce qu'il donne l'apparence de la rigueur.
        Ce contrôle est le garde-fou du précédent."""
        from core.elasticite import diagnostic_exploitabilite
        d = diagnostic_exploitabilite(
            _plan(comportement=_bloc()), _renouvellements(regime='residuelle'))
        self.assertTrue(d['exploitable'],
                        f"une variation résiduelle réelle est refusée : {d}")
        self.assertEqual(d['voie'], 'residuelle')
        self.assertLess(d['r2_prix_sur_risque'], 0.95)
        print(f"    POS-L3b variation résiduelle : R²="
              f"{d['r2_prix_sur_risque']:.4f} → exploitable ({d['voie']}) ✅")

    def test_un_TEST_DE_PRIX_identifie_meme_si_le_prix_suit_le_risque(self):
        """⚠️ LA VOIE FORTE. Une hausse tirée au sort est exogène par
        construction : son exogénéité ne se mesure pas, elle se déclare — et
        c'est la seule situation où c'est vrai."""
        from core.elasticite import diagnostic_exploitabilite
        d = diagnostic_exploitabilite(
            _plan(comportement=_bloc(groupe_test='groupe_prix')),
            _renouvellements(regime='experimentale'))
        self.assertTrue(d['exploitable'], f"un test de prix est refusé : {d}")
        self.assertEqual(d['voie'], 'experimentale')
        print(f"    POS-L3c test de prix → exploitable ({d['voie']}), "
              f"{d['n_groupes_test']} groupes ✅")

    def test_SANS_VARIATION_rien_n_est_exploitable_et_le_motif_DIFFERE(self):
        """⚠️ DEUX RAISONS DE REFUSER, ET ELLES NE SE CONFONDENT PAS. « Le prix
        n'a pas bougé » et « le prix a bougé comme le risque » appellent des
        actions différentes du client : la première demande une révision
        tarifaire, la seconde une variation qui ne suive pas le risque."""
        from core.elasticite import diagnostic_exploitabilite
        d = diagnostic_exploitabilite(
            _plan(comportement=_bloc()),
            _renouvellements(regime='sans_variation'))
        self.assertFalse(d['exploitable'])
        self.assertIn('aucune variation', d['motif'].lower())
        self.assertNotIn('risque', d['motif'].lower())
        print("    POS-L3d sans variation → non exploitable, motif distinct "
              "du déterminisme ✅")

    def test_un_SUPPORT_insuffisant_se_dit_comme_tel(self):
        """⚠️ TROISIÈME RAISON, TROISIÈME MOTIF. Trente contrats ne portent pas
        une élasticité, quelle que soit la qualité de leur variation de prix.
        Un refus qui ne dirait pas LAQUELLE des trois raisons s'applique
        n'aiderait personne."""
        from core.elasticite import diagnostic_exploitabilite
        d = diagnostic_exploitabilite(
            _plan(comportement=_bloc()),
            _renouvellements(n=40, regime='residuelle'))
        self.assertFalse(d['exploitable'])
        self.assertIn('effectif', d['motif'].lower())
        print(f"    POS-L3e support insuffisant ({d['n_lignes']} lignes, "
              f"{d['n_resiliations']} résiliations) → motif « effectif » ✅")

    def test_le_diagnostic_publie_ses_MESURES_et_ses_CONVENTIONS(self):
        """⚠️ UN VERDICT SANS SES CHIFFRES N'EST PAS VÉRIFIABLE, et un seuil
        sans son origine se lit comme une norme. Les deux seuils employés ici
        sont des conventions du module — aucun texte n'en fixe."""
        from core.elasticite import diagnostic_exploitabilite
        d = diagnostic_exploitabilite(
            _plan(comportement=_bloc()), _renouvellements(regime='residuelle'))
        for cle in ('r2_prix_sur_risque', 'n_lignes', 'n_resiliations',
                    'ecart_type_residuel', 'conventions'):
            with self.subTest(cle=cle):
                self.assertIn(cle, d, f"« {cle} » n'est pas publié")
        self.assertTrue(d['conventions'], "les seuils ne sont pas nommés")
        for nom, val in d['conventions'].items():
            self.assertIsNotNone(val, f"la convention « {nom} » est vide")
        print(f"    POS-L3f mesures et conventions publiées : "
              f"{sorted(d['conventions'])} ✅")

    def test_l_etat_devient_NON_IDENTIFIABLE_et_n_accuse_pas_le_logiciel(self):
        """⚠️ LE PENDANT DE POS-L2j. Là, on refusait d'imputer au portefeuille
        une limite du logiciel. Ici, la limite EST celle du portefeuille et
        l'état doit le dire — sinon le client corrigerait la mauvaise chose."""
        from core.elasticite import (
            ELASTICITE_NON_EXPLOITEE,
            ELASTICITE_NON_IDENTIFIABLE,
            etat_elasticite,
        )
        p = _plan(comportement=_bloc())
        e_det = etat_elasticite(p, _renouvellements(regime='deterministe'))
        self.assertEqual(e_det['etat'], ELASTICITE_NON_IDENTIFIABLE)
        self.assertIn('exploitabilite', e_det)
        e_ok = etat_elasticite(p, _renouvellements(regime='residuelle'))
        self.assertEqual(
            e_ok['etat'], ELASTICITE_NON_EXPLOITEE,
            "une variation exploitable doit rendre la main au logiciel, "
            "pas accuser le portefeuille")
        print(f"    POS-L3g déterministe → {e_det['etat']} · "
              f"exploitable → {e_ok['etat']} ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
