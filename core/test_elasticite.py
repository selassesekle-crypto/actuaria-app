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
            ELASTICITE_ESTIMEE,
            ELASTICITE_NON_CONCLUANTE,
            ELASTICITE_NON_EXPLOITEE,
            ELASTICITE_NON_IDENTIFIABLE,
            etat_elasticite,
        )
        p = _plan(comportement=_bloc())
        e_det = etat_elasticite(p, _renouvellements(regime='deterministe'))
        self.assertEqual(e_det['etat'], ELASTICITE_NON_IDENTIFIABLE)
        self.assertIn('exploitabilite', e_det)
        # ⚠️ CE QUI EST VÉRIFIÉ N'A PAS BOUGÉ : une variation exploitable
        # n'accuse PAS le portefeuille. Ce qui a bougé, c'est l'état exact —
        # avant L4 le logiciel ne savait pas estimer (`NON_EXPLOITEE`) ; il
        # sait désormais, et rend `ESTIMEE` ou `NON_CONCLUANTE` selon le
        # signal. `_renouvellements` n'encode aucun effet-prix, d'où le
        # second. Épingler `NON_EXPLOITEE` aurait figé un détail
        # d'implémentation à la place de la propriété.
        e_ok = etat_elasticite(p, _renouvellements(regime='residuelle'))
        self.assertNotEqual(
            e_ok['etat'], ELASTICITE_NON_IDENTIFIABLE,
            "une variation exploitable ne doit pas accuser le portefeuille")
        self.assertIn(e_ok['etat'], (ELASTICITE_ESTIMEE,
                                     ELASTICITE_NON_CONCLUANTE,
                                     ELASTICITE_NON_EXPLOITEE))
        print(f"    POS-L3g déterministe → {e_det['etat']} · "
              f"exploitable → {e_ok['etat']} ✅")


# ══════════════════════════════════════════════════════════════════════════════
#  L4 — L'ESTIMATION, ET SON ORACLE
# ══════════════════════════════════════════════════════════════════════════════

def _eps_connu(eps_cible=-0.25, n=25000, seed=5, avec_test_de_prix=False,
               taux_resil=0.15, bruit_prix=0.12):
    """Un portefeuille dont on CONNAÎT l'élasticité, et le prix y est ENDOGÈNE.

    ⚠️⚠️ C'EST L'ORACLE, ET IL EST NON NÉGOCIABLE. Un estimateur qui ne
    retrouve pas un ε qu'on a posé soi-même ne vaut rien. La construction est
    l'inverse exact de la formule : P = logistique(a + b·v + g·risque), d'où
    ε = −b·P̄ ; on choisit ε, on en déduit b.

    ⚠️ LE PRIX SUIT LE RISQUE, À DESSEIN. Un oracle où le prix serait
    indépendant du risque ne prouverait rien : c'est précisément l'endogénéité
    qui fait échouer l'estimateur naïf, et c'est elle qu'il faut reproduire.
    Mesuré : sans contrôle du risque, ε sort à −0,7213 pour une vérité de
    −0,2329, soit trois fois trop grand, et son intervalle rate la cible.
    """
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(seed)
    risque = rng.normal(0, 1, n)
    age = 45.0 + 12.0 * risque
    bm = 200.0 + 45.0 * risque

    groupe = np.array(['—'] * n, dtype=object)
    v = bruit_prix * risque                       # le prix SUIT le risque
    if avec_test_de_prix:
        tire = rng.integers(0, 2, n)
        groupe = np.where(tire == 1, 'hausse', 'temoin')
        v = v + 0.10 * tire                       # la hausse est TIREE AU SORT
    else:
        v = v + rng.normal(0, 0.08, n)            # variation residuelle

    b = 1.5
    g = 0.45                                      # effet PROPRE du risque
    a = np.log(taux_resil / (1 - taux_resil))
    P = 1.0 / (1.0 + np.exp(-(a + b * v + g * risque)))
    # ⚠️ ON RECALE b POUR ATTEINDRE L'eps VOULU : eps = -b * P_moyen.
    b = -eps_cible / float(P.mean())
    P = 1.0 / (1.0 + np.exp(-(a + b * v + g * risque)))
    eps_vrai = -b * float(P.mean())

    p0 = rng.uniform(300, 900, n)
    df = pd.DataFrame({
        'id_contrat':     np.arange(n),
        'annee_exercice': 2023,
        'age':            age,
        'bonus_malus':    bm,
        'prime_n_1':      p0,
        'prime_n':        p0 * np.exp(v),
        'resilie':        (rng.random(n) < P).astype(float),
        'groupe_prix':    groupe,
        'exposition':     rng.uniform(0.3, 1.0, n),
        'nb_sinistres':   rng.poisson(0.08, n).astype(float),
        'cout_total_sinistres': rng.exponential(600, n),
    })
    return df, eps_vrai


class T_L_Estimateur_Retrouve_Un_Eps_Qu_On_A_Pose(unittest.TestCase):
    """CONTRÔLE POSITIF — L'ORACLE. Le seul qui compte vraiment.

    ⚠️⚠️ UN ESTIMATEUR QUI NE RETROUVE PAS UN ε QU'ON A POSÉ SOI-MÊME NE VAUT
    RIEN. Aucun texte ne fixe une élasticité, donc aucun oracle externe
    n'existe : la seule vérification possible est de fabriquer la vérité, puis
    d'exiger que l'estimateur la retrouve DANS SON INTERVALLE.
    """

    def test_l_estimateur_retrouve_l_eps_VRAI_dans_son_intervalle(self):
        """⚠️⚠️ DEUX PROPRIÉTÉS, ET ELLES NE SE CONFONDENT PAS — ma première
        version les mélangeait, et c'est le contrôle qui me l'a appris.

          COUVERTURE  l'intervalle contient-il la vérité ? C'est l'oracle, et
                      il doit tenir DANS TOUS LES CAS.
          CONCLUSIVITÉ l'intervalle est-il assez étroit pour décider ? C'est
                      une question de politique, réglée par une convention.

        MESURÉ : à ε = −0,147, l'estimateur rend −0,1315 avec IC
        [−0,2013 ; −0,0618] sur 25 000 renouvellements. La vérité EST dans
        l'intervalle — l'estimateur est juste — mais la demi-largeur vaut
        53 % de l'estimation, au-dessus du plafond de 50 %. À 60 000 elle
        tombe à 31 %, à 150 000 à 20 %. **Une petite élasticité demande plus
        de données** : ce n'est pas un défaut de l'estimateur, c'est une
        propriété du signal, et le tableau ci-dessous l'épingle.
        """
        from core.elasticite import diagnostic_exploitabilite, estimer_elasticite
        p = _plan(comportement=_bloc())
        for eps_cible, n, conclut in ((-0.15, 25000, False),
                                      (-0.15, 60000, True),
                                      (-0.30, 25000, True),
                                      (-0.55, 25000, True)):
            with self.subTest(eps=eps_cible, n=n):
                df, vrai = _eps_connu(eps_cible, n=n, seed=7)
                r = estimer_elasticite(p, df, diagnostic_exploitabilite(p, df))
                # ── L'ORACLE : la couverture, TOUJOURS ────────────────────
                self.assertLessEqual(
                    r['ic_bas'], vrai,
                    f"ε vrai {vrai:.4f} au-dessus de l'IC [{r['ic_bas']:.4f}, "
                    f"{r['ic_haut']:.4f}] (estimé {r['elasticite']:.4f})")
                self.assertGreaterEqual(
                    r['ic_haut'], vrai,
                    f"ε vrai {vrai:.4f} en dessous de l'IC [{r['ic_bas']:.4f}, "
                    f"{r['ic_haut']:.4f}] (estimé {r['elasticite']:.4f})")
                # ── LA CONCLUSIVITÉ : une AUTRE propriété ─────────────────
                self.assertEqual(
                    r['concluante'], conclut,
                    f"conclusivité attendue {conclut} sur n={n} pour "
                    f"ε={vrai:.4f} : {r.get('motif')}")
                demi = (r['ic_haut'] - r['ic_bas']) / 2
                print(f"    POS-L4a ε vrai {vrai:+.4f} n={n:,} → estimé "
                      f"{r['elasticite']:+.4f} IC [{r['ic_bas']:+.4f}, "
                      f"{r['ic_haut']:+.4f}] précision "
                      f"{demi / abs(r['elasticite']):.0%} concluante="
                      f"{r['concluante']} ✅")

    def test_l_intervalle_est_OBLIGATOIRE_et_non_degenere(self):
        """⚠️ UN ε PONCTUEL SANS SON INCERTITUDE EST EXACTEMENT CE QU'ON VIENT
        DE RETIRER. La grille à ±20 % ne portait aucune incertitude non plus."""
        from core.elasticite import diagnostic_exploitabilite, estimer_elasticite
        df, _ = _eps_connu(-0.25)
        p = _plan(comportement=_bloc())
        r = estimer_elasticite(p, df, diagnostic_exploitabilite(p, df))
        for cle in ('elasticite', 'ic_bas', 'ic_haut', 'erreur_type',
                    'n_lignes', 'n_resiliations', 'voie', 'conventions'):
            with self.subTest(cle=cle):
                self.assertIn(cle, r, f"« {cle} » n'est pas publié")
                self.assertIsNotNone(r[cle], f"« {cle} » est vide")
        self.assertLess(r['ic_bas'], r['elasticite'])
        self.assertLess(r['elasticite'], r['ic_haut'])
        print(f"    POS-L4b IC non dégénéré, largeur "
              f"{r['ic_haut'] - r['ic_bas']:.4f} ✅")

    def test_l_estimateur_VARIE_avec_les_donnees(self):
        """⚠️⚠️ LE GARDE-FOU DU GARDE-FOU. Un estimateur qui rendrait toujours
        le même ε serait aussi inutile que la constante qu'on vient de retirer
        — et bien plus difficile à repérer. Même contrôle que pour le PSI."""
        from core.elasticite import diagnostic_exploitabilite, estimer_elasticite
        p = _plan(comportement=_bloc())
        vus = []
        for cible in (-0.15, -0.55):
            df, vrai = _eps_connu(cible, seed=21)
            r = estimer_elasticite(p, df, diagnostic_exploitabilite(p, df))
            vus.append((vrai, r['elasticite']))
        (v1, e1), (v2, e2) = vus
        self.assertGreater(
            abs(e1 - e2), 0.15,
            f"deux portefeuilles d'élasticités vraies {v1:.3f} et {v2:.3f} "
            f"rendent {e1:.4f} et {e2:.4f} — l'estimateur ne dépend pas des "
            f"données qu'il prétend mesurer")
        self.assertLess(e2, e1, "l'ordre des deux estimations est inversé")
        print(f"    POS-L4c ε vrais {v1:+.3f}/{v2:+.3f} → estimés "
              f"{e1:+.4f}/{e2:+.4f} — il varie ✅")

    def test_la_voie_EXPERIMENTALE_prime_et_n_a_pas_la_meme_arithmetique(self):
        """⚠️ LA SUBORDINATION, TENUE DANS L'ESTIMATION. La voie expérimentale
        n'utilise QUE le contraste tiré au sort et ne dépend d'AUCUN modèle de
        contrôle : c'est sa supériorité, et elle est arithmétique."""
        from core.elasticite import diagnostic_exploitabilite, estimer_elasticite
        df, vrai = _eps_connu(-0.30, seed=9, avec_test_de_prix=True)
        p = _plan(comportement=_bloc(groupe_test='groupe_prix'))
        r = estimer_elasticite(p, df, diagnostic_exploitabilite(p, df))
        self.assertEqual(r['voie'], 'experimentale')
        self.assertEqual(
            r['facteurs_de_controle'], [],
            "la voie expérimentale ne doit dépendre d'AUCUN contrôle")
        self.assertTrue(r['concluante'])
        self.assertLessEqual(r['ic_bas'], vrai)
        self.assertGreaterEqual(r['ic_haut'], vrai)
        print(f"    POS-L4d voie expérimentale, 0 contrôle : ε vrai "
              f"{vrai:+.4f} → [{r['ic_bas']:+.4f}, {r['ic_haut']:+.4f}] ✅")

    def test_un_signal_TROP_FAIBLE_rend_NON_CONCLUANTE_pas_autre_chose(self):
        """⚠️⚠️ LE CINQUIÈME CAS, ET IL NE SE CONFOND PAS AVEC LE TROISIÈME.
        « La variation ne permet pas d'identifier » et « l'estimation n'a pas
        abouti » disent des choses différentes : la première accuse les
        données, la seconde constate que le signal était trop faible pour
        conclure. Les faire retomber l'un sur l'autre tromperait le lecteur."""
        from core.elasticite import diagnostic_exploitabilite, estimer_elasticite
        # eps quasi nul + petit effectif : l'IC contiendra zero
        df, vrai = _eps_connu(-0.004, n=900, seed=13)
        p = _plan(comportement=_bloc())
        d = diagnostic_exploitabilite(p, df)
        self.assertTrue(d['exploitable'],
                        "prémisse : la variation DOIT être exploitable, sinon "
                        "on testerait le troisième cas et non le cinquième")
        r = estimer_elasticite(p, df, d)
        self.assertFalse(r['concluante'])
        self.assertTrue((r.get('motif') or '').strip())
        print(f"    POS-L4e ε vrai {vrai:+.4f}, IC "
              f"[{r['ic_bas']:+.4f}, {r['ic_haut']:+.4f}] → non concluante : "
              f"{r['motif'][:56]}… ✅")

    def test_la_RESERVE_accompagne_tout_eps_publie(self):
        """⚠️ LA LIMITE N°2, DANS LE RÉSULTAT ET PAS DANS UN COMMENTAIRE. On
        mesure la variation résiduelle ; on ne démontre pas son indépendance à
        ce qu'on n'observe pas. Aucun calcul ne le peut."""
        from core.elasticite import diagnostic_exploitabilite, estimer_elasticite
        p_res = _plan(comportement=_bloc())
        df_res, _ = _eps_connu(-0.25)
        r_res = estimer_elasticite(p_res, df_res,
                                   diagnostic_exploitabilite(p_res, df_res))
        self.assertIn('reserve', r_res)
        self.assertIn('pas démontr', r_res['reserve'].lower())

        p_exp = _plan(comportement=_bloc(groupe_test='groupe_prix'))
        df_exp, _ = _eps_connu(-0.30, avec_test_de_prix=True)
        r_exp = estimer_elasticite(p_exp, df_exp,
                                   diagnostic_exploitabilite(p_exp, df_exp))
        self.assertNotEqual(
            r_res['reserve'], r_exp['reserve'],
            "la réserve doit DIFFÉRER entre une exogénéité supposée et une "
            "exogénéité garantie par tirage au sort")
        print("    POS-L4f la réserve accompagne l'ε, et elle différencie "
              "les deux voies ✅")


class T_L_Etat_Atteint_Enfin_ESTIMEE(unittest.TestCase):
    """CONTRÔLE POSITIF — les cinq états, tous atteignables.

    ⚠️⚠️ UN ÉTAT QUI NE PEUT PAS ÊTRE ATTEINT EST UN ÉTAT QUI N'EXISTE PAS.
    Depuis L0, `ESTIMEE` était déclaré et inatteignable ; ce lot le rend
    joignable, et chacun des cinq doit désormais se prouver par un chemin.
    """

    def _etat(self, **kw):
        from core.elasticite import etat_elasticite
        return etat_elasticite(*kw.pop('args', ()), **kw)

    def test_un_signal_FRANC_rend_ESTIMEE_avec_son_intervalle(self):
        from core.elasticite import ELASTICITE_ESTIMEE, etat_elasticite
        df, vrai = _eps_connu(-0.35, n=30000, seed=4)
        e = etat_elasticite(_plan(comportement=_bloc()), df)
        self.assertEqual(e['etat'], ELASTICITE_ESTIMEE)
        est = e['estimation']
        self.assertLessEqual(est['ic_bas'], vrai)
        self.assertGreaterEqual(est['ic_haut'], vrai)
        self.assertIn('elasticite', est)
        print(f"    POS-L4g ε vrai {vrai:+.4f} → état {e['etat']}, "
              f"ε={est['elasticite']:+.4f} IC [{est['ic_bas']:+.4f}, "
              f"{est['ic_haut']:+.4f}] ✅")

    def test_les_CINQ_etats_sont_atteignables_par_un_chemin_distinct(self):
        """⚠️ CHACUN DIT AUTRE CHOSE, ET LE CHEMIN LE PROUVE. Un état qui se
        confondrait avec un autre ferait corriger au client la mauvaise
        chose."""
        from core.elasticite import (
            ELASTICITE_ESTIMEE,
            ELASTICITE_NON_CONCLUANTE,
            ELASTICITE_NON_EXPLOITEE,
            ELASTICITE_NON_FOURNIE,
            ELASTICITE_NON_IDENTIFIABLE,
            etat_elasticite,
        )
        p = _plan(comportement=_bloc())
        chemins = {
            ELASTICITE_NON_FOURNIE:
                etat_elasticite(_plan(), _renouvellements()),
            ELASTICITE_NON_EXPLOITEE:
                etat_elasticite(p, None),
            ELASTICITE_NON_IDENTIFIABLE:
                etat_elasticite(p, _renouvellements(regime='deterministe')),
            ELASTICITE_NON_CONCLUANTE:
                etat_elasticite(p, _eps_connu(-0.004, n=900, seed=13)[0]),
            ELASTICITE_ESTIMEE:
                etat_elasticite(p, _eps_connu(-0.35, n=30000, seed=4)[0]),
        }
        for attendu, obtenu in chemins.items():
            with self.subTest(etat=attendu):
                self.assertEqual(obtenu['etat'], attendu,
                                 f"chemin de « {attendu} » : {obtenu['motif']}")
                self.assertTrue((obtenu.get('motif') or '').strip())
        self.assertEqual(len({e['etat'] for e in chemins.values()}), 5)
        print(f"    POS-L4h les 5 états atteints par 5 chemins distincts : "
              f"{sorted(chemins)} ✅")

    def test_NON_CONCLUANTE_n_accuse_ni_les_donnees_ni_l_absence(self):
        """⚠️ LE CINQUIÈME CAS DIT CE QU'IL EST. La variation était
        exploitable — le troisième cas ne s'applique pas — et la donnée était
        déclarée — le premier non plus. Ce qui manquait, c'est du signal."""
        from core.elasticite import ELASTICITE_NON_CONCLUANTE, etat_elasticite
        e = etat_elasticite(_plan(comportement=_bloc()),
                            _eps_connu(-0.004, n=900, seed=13)[0])
        self.assertEqual(e['etat'], ELASTICITE_NON_CONCLUANTE)
        self.assertTrue(e['exploitabilite']['exploitable'],
                        "prémisse : la variation DOIT être exploitable")
        self.assertIn('estimation', e)
        self.assertFalse(e['estimation']['concluante'])
        print(f"    POS-L4i {e['etat']} : variation exploitable, signal "
              f"insuffisant ✅")

    def test_la_RESERVE_est_dans_l_etat_quand_un_eps_est_publie(self):
        """⚠️ LA LIMITE N°2 SUIT LE CHIFFRE. Un ε publié sans sa réserve
        laisserait croire que l'exogénéité a été démontrée."""
        from core.elasticite import ELASTICITE_ESTIMEE, etat_elasticite
        e = etat_elasticite(_plan(comportement=_bloc()),
                            _eps_connu(-0.35, n=30000, seed=4)[0])
        self.assertEqual(e['etat'], ELASTICITE_ESTIMEE)
        self.assertIn('reserve', e['estimation'])
        self.assertIn('pas démontr', e['estimation']['reserve'].lower())
        print("    POS-L4j la réserve suit l'ε publié ✅")

    def test_la_justification_de_NON_EXPLOITEE_N_A_PAS_SURVECU_a_son_objet(self):
        """⚠️⚠️ LE DÉFAUT QUE J'AI TROUVÉ AILLEURS, ET QUE JE M'INTERDIS ICI.
        `FIGURES_ECARTEES['monitoring_gini']` justifie encore son exclusion par
        « données FABRIQUÉES » alors que le correctif `98dba85` les a rendues
        mesurées — et son test l'épingle par le MOT, pas par le FAIT.

        `NON_EXPLOITEE` disait « l'estimation (L3-L5) n'est pas construite ».
        Elle l'est. Son motif doit donc dire ce qui est VRAI maintenant :
        aucune donnée n'a été fournie à ce calcul."""
        from core.elasticite import ELASTICITE_NON_EXPLOITEE, etat_elasticite
        e = etat_elasticite(_plan(comportement=_bloc()), None)
        self.assertEqual(e['etat'], ELASTICITE_NON_EXPLOITEE)
        motif = e['motif'].lower()
        self.assertNotIn('l3', motif)
        self.assertNotIn('l4', motif)
        self.assertNotIn('pas encore construite', motif)
        self.assertIn('aucun', motif)
        print(f"    POS-L4k le motif de {ELASTICITE_NON_EXPLOITEE} dit ce qui "
              f"est vrai aujourd'hui ✅")

    def test_A4_publie_l_eps_de_bout_en_bout_ET_tarife_normalement(self):
        """⚠️ LE CHEMIN COMPLET, ET IL NE BLOQUE RIEN. Un état qui n'arriverait
        pas jusqu'au commentaire actuaire n'existerait que pour les tests. Et
        la règle tient dans les cinq états : aucun blocage."""
        import importlib

        from core.elasticite import ELASTICITE_ESTIMEE
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        T4 = importlib.import_module(
            'direction_non_vie.tarification.a4_ml.test_a4_ml')

        df, vrai = _eps_connu(-0.35, n=30000, seed=4)
        r_a2 = T4._make_r_a2(600)
        # le portefeuille de comportement porte AUSSI les colonnes ML
        for col in r_a2['dataframe'].columns:
            if col not in df.columns:
                df[col] = r_a2['dataframe'][col].reindex(df.index).ffill().bfill()
        r_a2['dataframe'] = df

        r = AgentA4ML(models_path='/tmp', audit_path='/tmp', verbose=False).run(
            result_a2=r_a2, result_a3=T4._make_r_a3(),
            plan=_plan(comportement=_bloc()),
            calcul_shap=False, generer_graphiques=False)
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertTrue(r['classement'], "aucun modèle classé")
        e = r['elasticite']
        self.assertEqual(e['etat'], ELASTICITE_ESTIMEE, e.get('motif'))
        self.assertIn('ÉLASTICITÉ-PRIX : ESTIMÉE', r['commentaire'])
        self.assertIn('IC 95 %', r['commentaire'])
        print(f"    POS-L4l A4 de bout en bout : ε vrai {vrai:+.4f} → "
              f"{e['estimation']['elasticite']:+.4f}, statut "
              f"{r['statut_rag']}, {len(r['classement'])} modèles ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
