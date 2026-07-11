"""
ActuarIA — Tests d'INVARIANTS · Direction Non-Vie · Équipe Tarification
═══════════════════════════════════════════════════════════════════════════════

CE QUE CES TESTS SONT, ET POURQUOI ILS COMPTENT PLUS QUE LES AUTRES

Onze cycles d'audit ont posé la même question : « quel scénario casse le code ? »
Chaque cycle a trouvé de vrais bugs — et chaque cycle en a laissé passer, parce
qu'un scénario adverse ne trouve que ce qu'on a pensé à imaginer. Les deux
bloquants de l'audit V11 (B4, B5) étaient présents depuis des cycles : ils ont
échappé à tout le monde simplement parce que personne n'avait exercé un
portefeuille RC Pro.

La question qui manquait est différente, et elle ne demande aucune imagination :

        « Quelles affirmations le code fait-il sur lui-même,
          et sont-elles vraies ? »

Un test d'INVARIANT ne construit aucun portefeuille, ne simule aucun client, ne
devine aucun nom de colonne malveillant. Il vérifie la COHÉRENCE INTERNE entre
deux parties du système qui se sont mises à diverger sans que personne ne s'en
aperçoive. Quinze lignes auraient suffi à attraper B5 — la destruction
silencieuse d'antecedents_sinistres_3ans, le facteur central de la RC Pro
(−17,4 % de pouvoir discriminant du GLM) — dès sa première seconde d'existence.

Ces tests sont la seule classe de garde-fou qui protège contre les défauts que
PERSONNE N'A ENCORE IMAGINÉS. Ils doivent être maintenus en priorité sur tout le
reste : chaque fois qu'un agent déclare une configuration, un invariant doit
vérifier que le reste du système l'honore.

Origine : recommandation du certificateur indépendant, audit V11.
"""
import sys, os, unittest
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from core.conformite_reglementaire import (
    filtrer_features, filtrer_genre, filtrer_famille_cible,
    est_facteur_autorise, avertissement_walk_forward,
)
from direction_non_vie.tarification.a1_ingestion.agent import (
    MOTS_CLES_DETECTION, BRANCHES_SUPPORTEES,
)
from direction_non_vie.tarification.a2_preprocessing.agent import (
    VARS_CATEGORIELLES, INTERACTIONS,
)
from direction_non_vie.tarification.a3_glm.agent import VARS_GLM


class TestInvariant_ConfigsSurviventAuFiltre(unittest.TestCase):
    """
    INVARIANT N°1 — Le code ne doit pas détruire ce qu'il déclare lui-même.

    Toute variable qu'un agent DÉCLARE comme facteur tarifaire (VARS_GLM,
    VARS_CATEGORIELLES, INTERACTIONS) doit survivre à filtrer_features().
    Sinon, l'agent construit un modèle amputé — en silence.

    C'est cet invariant qui a révélé le BLOQUANT B5 de l'audit V11 :
    'antecedents_sinistres_3ans' (VARS_GLM['rcpro']) et 'double_vitrage'
    (VARS_GLM['mrh']) étaient DÉTRUITS par la liste blanche.
    """

    def test_vars_glm_survivent_toutes(self):
        for sous_branche, variables in VARS_GLM.items():
            with self.subTest(sous_branche=sous_branche):
                conservees = set(filtrer_features(list(variables)))
                detruites = set(variables) - conservees
                self.assertEqual(detruites, set(),
                    f"VARS_GLM['{sous_branche}'] déclare {sorted(detruites)}, "
                    f"que filtrer_features() DÉTRUIT. Le GLM sera amputé de ces "
                    f"facteurs, en silence. Soit la variable est légitime et doit "
                    f"être déclarée dans FACTEURS_TARIFAIRES_AUTORISES, soit elle "
                    f"est prohibée et ne doit pas figurer dans VARS_GLM.")
        print(f"    INV-1a VARS_GLM : {sum(len(v) for v in VARS_GLM.values())} "
              f"variables déclarées, toutes conservées ✅")

    def test_encodages_declares_survivent(self):
        """Les colonnes produites par l'encodage déclaré d'A2 (label → *_enc,
        one-hot → base_modalite) doivent survivre au filtre."""
        for sous_branche, cfg in VARS_CATEGORIELLES.items():
            with self.subTest(sous_branche=sous_branche):
                derivees = ([f"{c}_enc" for c in cfg.get('label', [])]
                            + [f"{c}_modalite" for c in cfg.get('one_hot', [])])
                detruites = set(derivees) - set(filtrer_features(derivees))
                self.assertEqual(detruites, set(),
                    f"VARS_CATEGORIELLES['{sous_branche}'] produira {sorted(detruites)}, "
                    f"que filtrer_features() DÉTRUIT.")
        print("    INV-1b Encodages déclarés par A2 : tous conservés ✅")

    def test_interactions_declarees_survivent(self):
        """A2 génère 'inter_{a}_{b}' et '{a}_x_{b}' à partir d'INTERACTIONS."""
        for sous_branche, paires in INTERACTIONS.items():
            with self.subTest(sous_branche=sous_branche):
                noms = ([f"inter_{a}_{b}" for a, b in paires]
                        + [f"{a}_x_{b}" for a, b in paires])
                detruites = set(noms) - set(filtrer_features(noms))
                self.assertEqual(detruites, set(),
                    f"INTERACTIONS['{sous_branche}'] produira {sorted(detruites)}, "
                    f"que filtrer_features() DÉTRUIT.")
        print("    INV-1c Interactions déclarées par A2 : toutes conservées ✅")


class TestInvariant_DetectionCoherenteAvecConfigs(unittest.TestCase):
    """
    INVARIANT N°2 — Une sous-branche configurée doit être détectable.

    Si A2 et A3 déclarent une configuration pour une sous-branche, alors le
    vocabulaire de détection d'A1 doit pouvoir la reconnaître — sinon cette
    configuration est du CODE MORT, et les portefeuilles concernés sont traités
    avec une configuration générique, en silence.

    C'est cet invariant qui a révélé le BLOQUANT B4 de l'audit V11 :
    MOTS_CLES_DETECTION['rcpro'] n'avait AUCUNE intersection avec les 8 colonnes
    que A2/A3 déclarent pour la RC Pro. Un portefeuille RC Pro réel était
    étiqueté 'non' — une sous-branche qui n'existe nulle part.
    """

    def test_chaque_sous_branche_est_detectable_par_ses_propres_colonnes(self):
        for sous_branche in VARS_GLM:
            with self.subTest(sous_branche=sous_branche):
                self.assertIn(sous_branche, MOTS_CLES_DETECTION,
                    f"A3 configure '{sous_branche}' mais A1 ne sait pas la détecter.")
                mots = MOTS_CLES_DETECTION[sous_branche]
                cfg = VARS_CATEGORIELLES.get(sous_branche, {})
                colonnes = (set(VARS_GLM[sous_branche])
                            | set(cfg.get('one_hot', []))
                            | set(cfg.get('label', [])))
                declencheuses = [c for c in colonnes
                                 if any(m in c.lower() for m in mots)]
                self.assertTrue(declencheuses,
                    f"AUCUNE des {len(colonnes)} colonnes déclarées pour "
                    f"'{sous_branche}' ne déclenche sa propre détection "
                    f"(mots-clés : {mots}). Un portefeuille '{sous_branche}' réel "
                    f"ne sera JAMAIS reconnu : toute cette configuration est du "
                    f"code mort.")
        print(f"    INV-2a Les {len(VARS_GLM)} sous-branches configurées sont "
              f"détectables par leurs propres colonnes ✅")

    def test_pas_de_config_orpheline(self):
        """Symétrique : A1 ne doit pas savoir détecter une sous-branche que
        personne ne configure (résidu de périmètre)."""
        for sous_branche in MOTS_CLES_DETECTION:
            with self.subTest(sous_branche=sous_branche):
                self.assertIn(sous_branche, VARS_GLM,
                    f"A1 détecte '{sous_branche}' mais A3 ne la configure pas — "
                    f"résidu de périmètre (Vie/Santé/Prévoyance ?).")
        print("    INV-2b Aucune sous-branche détectable sans configuration ✅")

    def test_perimetre_non_vie_strict(self):
        """Aucun résidu Vie / Santé / Prévoyance dans les configurations."""
        interdits = ('vie', 'sante', 'prevoyance', 'epargne', 'retraite')
        for nom, cfg in [('MOTS_CLES_DETECTION', MOTS_CLES_DETECTION),
                         ('VARS_GLM', VARS_GLM),
                         ('VARS_CATEGORIELLES', VARS_CATEGORIELLES),
                         ('INTERACTIONS', INTERACTIONS)]:
            for sous_branche in cfg:
                self.assertFalse(
                    any(i in sous_branche.lower() for i in interdits),
                    f"{nom} contient '{sous_branche}' — hors périmètre Non-Vie. "
                    f"Les directions Vie/EP-RE et Santé-Prévoyance sont autonomes.")
        self.assertEqual(tuple(BRANCHES_SUPPORTEES), ('non_vie',))
        print("    INV-2c Périmètre strictement Non-Vie (auto · MRH · RC Pro) ✅")


class TestInvariant_ConformiteNonContournable(unittest.TestCase):
    """
    INVARIANT N°3 — Les garde-fous de conformité sont cohérents entre eux.

    Les trois filtres doivent se comporter de la même façon face aux mêmes
    variations de forme (casse, encodage). Une asymétrie est une faille : elle
    signifie qu'une variable prohibée passe par un filtre et pas par l'autre.
    (Audit V10 : filtrer_famille_cible était sensible à la casse là où
    filtrer_genre ne l'était pas → 'MONTANT_SINISTRES' passait.)
    """

    def test_filtres_insensibles_a_la_casse(self):
        for nom in ['sexe', 'genre', 'civilite', 'titre']:
            for variante in (nom, nom.upper(), nom.capitalize()):
                self.assertEqual(filtrer_genre([variante]), [],
                    f"filtrer_genre laisse passer '{variante}' (casse).")
        for nom in ['montant_sinistres', 'cout_total_sinistres', 'prime_pure']:
            for variante in (nom, nom.upper(), nom.capitalize()):
                self.assertEqual(filtrer_famille_cible([variante]), [],
                    f"filtrer_famille_cible laisse passer '{variante}' (casse).")
        print("    INV-3a Les deux filtres sont insensibles à la casse ✅")

    def test_filtrer_features_est_bien_la_composition_des_trois(self):
        """filtrer_features doit être au moins aussi strict que chacun de ses
        composants pris séparément — sinon un chemin l'affaiblit."""
        echantillon = ['age', 'bonus_malus', 'sexe', 'titre_enc', 'prime_pure',
                       'montant_sinistres', 'loss_ratio', 'colonne_inconnue_xyz']
        via_composition = set(filtrer_famille_cible(filtrer_genre(echantillon)))
        via_entree_unique = set(filtrer_features(echantillon))
        self.assertTrue(via_entree_unique <= via_composition,
            "filtrer_features est MOINS strict que la composition de ses filtres.")
        for prohibee in ['sexe', 'titre_enc', 'prime_pure', 'montant_sinistres',
                         'loss_ratio', 'colonne_inconnue_xyz']:
            self.assertNotIn(prohibee, via_entree_unique)
        print("    INV-3b filtrer_features ⊆ composition des filtres ✅")


class TestInvariant_LivrablesCoherentsAvecLeGate(unittest.TestCase):
    """
    INVARIANT N°4 — Aucun livrable ne peut contredire la certification.

    Le BLOQUANT B3 (audit V10) : l'Excel estampillait « ✓ Conforme » en VERT
    pendant que le gate RAG plafonnait à AMBRE. Puis, au V11 : le correctif
    n'avait été appliqué qu'à Excel — Word, HTML et le rapport d'équipe
    continuaient d'afficher la chaîne brute. Sixième occurrence du motif
    « corrigé à un endroit, non propagé ailleurs ».

    Remède : une SOURCE UNIQUE (avertissement_walk_forward) que TOUS les
    livrables appellent. Cet invariant vérifie qu'aucun ne l'a oubliée.
    """

    def test_tous_les_livrables_appellent_la_source_unique(self):
        import inspect
        from direction_non_vie.tarification.services import (
            tarif_excel, rapport_equipe_tarif, rapport_modeles_tarif,
        )
        for module in (tarif_excel, rapport_equipe_tarif, rapport_modeles_tarif):
            with self.subTest(module=module.__name__):
                src = inspect.getsource(module)
                self.assertIn('avertissement_walk_forward', src,
                    f"{module.__name__} n'appelle pas la source unique de vérité "
                    f"sur la portée de la validation temporelle : ce livrable peut "
                    f"contredire le gate de certification.")
        print("    INV-4a Excel · Word/HTML · rapport d'équipe : tous câblés sur "
              "la source unique ✅")

    def test_la_source_unique_avertit_dans_tous_les_cas_degrades(self):
        cas = [
            ("backtest indisponible", {'disponible': False}),
            ("recalibration sur proxy",
             {'disponible': True, 'modele_recalibre_fidele': False,
              'modele_recalibre': 'GLM → proxy GBM'}),
            ("aucune métrique produite",
             {'disponible': True, 'modele_recalibre_fidele': True,
              'gini_wf_moyen': None}),
            ("biais de tarification (A/E hors bande)",
             {'disponible': True, 'modele_recalibre_fidele': True,
              'gini_wf_moyen': 0.2, 'ae_ratio': 0.45}),
            ("instabilité temporelle",
             {'disponible': True, 'modele_recalibre_fidele': True,
              'gini_wf_moyen': 0.2, 'ae_ratio': 1.0,
              'stabilite_wf': '🔴 Instable'}),
        ]
        for label, bt in cas:
            with self.subTest(cas=label):
                self.assertIsNotNone(avertissement_walk_forward(bt),
                    f"Cas dégradé '{label}' : aucun avertissement produit.")
        # Contrôle négatif : un walk-forward sain ne doit PAS déclencher d'alerte.
        sain = {'disponible': True, 'modele_recalibre_fidele': True,
                'gini_wf_moyen': 0.28, 'ae_ratio': 1.01,
                'stabilite_wf': '🟢 Stable'}
        self.assertIsNone(avertissement_walk_forward(sain),
            "Un walk-forward sain ne doit produire aucun avertissement.")
        print("    INV-4b 5 cas dégradés avertis · walk-forward sain silencieux ✅")


class TestInvariant_MatriceXNonContournable(unittest.TestCase):
    """
    INVARIANT N°5 — Le contournement de la conformité doit être IMPOSSIBLE,
    pas seulement interdit.

    Six cycles ont produit six variantes du même défaut : le filtre est correct,
    et il est contourné ailleurs. Le pire (BLOQUANT B1, audit V10) : A3 appelait
    le filtre, puis réinjectait des colonnes brutes vingt lignes plus bas — le
    GLM tarifait la civilité (37,9 % d'écart H/F).

    MatriceX rend ce code littéralement inécrivable : la liste de features
    conforme est un TUPLE IMMUABLE, instanciable uniquement par le module de
    conformité.
    """

    def test_matricex_ne_peut_pas_etre_instanciee_directement(self):
        from core.conformite_reglementaire import MatriceX
        with self.assertRaises(TypeError):
            MatriceX(['sexe'], {}, 'contournement')
        print("    INV-5a MatriceX non instanciable hors du module de conformité ✅")

    def test_matricex_est_immuable(self):
        from core.conformite_reglementaire import construire_matrice_x
        mx = construire_matrice_x(['age', 'bonus_malus', 'titre_enc'],
                                  contexte='test')
        # Reproduction exacte du geste qui a produit le BLOQUANT B1 :
        with self.assertRaises(AttributeError):
            mx.features.extend(['titre_enc'])
        with self.assertRaises(AttributeError):
            mx._features = ('sexe',)
        self.assertNotIn('titre_enc', list(mx))
        print("    INV-5b MatriceX immuable — la réinjection post-filtre (B1) "
              "lève AttributeError ✅")

    def test_matricex_trace_ses_exclusions_avec_un_motif(self):
        """Une exclusion silencieuse est un défaut en soi : c'est ce silence qui
        a rendu le BLOQUANT B5 si coûteux (antecedents_sinistres_3ans détruit,
        −17,4 % de Gini, sans que rien ne l'indique nulle part)."""
        from core.conformite_reglementaire import construire_matrice_x
        mx = construire_matrice_x(
            ['age', 'sexe', 'montant_sinistres', 'colonne_inconnue_xyz'],
            contexte='test')
        excl = mx.exclusions
        self.assertIn('sexe', excl)
        self.assertIn('C-236/09', excl['sexe'])
        self.assertIn('montant_sinistres', excl)
        self.assertIn('fuite', excl['montant_sinistres'].lower())
        self.assertIn('colonne_inconnue_xyz', excl)
        self.assertIn('liste blanche', excl['colonne_inconnue_xyz'])
        print("    INV-5c Chaque exclusion porte son motif réglementaire ✅")

    def test_tous_les_agents_passent_par_construire_matrice_x(self):
        """Aucun agent ne doit construire une matrice X autrement."""
        import inspect
        from direction_non_vie.tarification.a3_glm import agent as a3
        from direction_non_vie.tarification.a4_ml import agent as a4
        from direction_non_vie.tarification.a5_deep_learning import agent as a5
        from direction_non_vie.tarification.a6_comparaison import agent as a6
        for mod in (a3, a4, a5, a6):
            with self.subTest(agent=mod.__name__):
                src = inspect.getsource(mod)
                self.assertIn('construire_matrice_x', src,
                    f"{mod.__name__} ne passe pas par construire_matrice_x() : "
                    f"sa matrice X n'est pas certifiée conforme.")
        print("    INV-5d A3 · A4 · A5 · A6 : tous passent par "
              "construire_matrice_x() ✅")


class TestInvariant_GateLitToutesLesFenetres(unittest.TestCase):
    """
    INVARIANT N°6 — Le gate doit exploiter TOUT ce que le backtest calcule.

    'ae_ratio' ne porte que sur la DERNIÈRE fenêtre walk-forward (a6:938-939).
    A6 calcule aussi 'ae_moyen_wf' et 'n_fenetres_rouge' — mais le gate ne les
    lisait pas : un modèle avec 3 fenêtres ROUGE sur 4 restait VERT au seul
    motif que la dernière année était bonne (angle mort signalé à l'audit V11).
    """

    def setUp(self):
        from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
        self.agent = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp',
                                        verbose=False)
        self.modele = {'score_global': 0.82, 'gini_test': 0.31}

    def _statut(self, bt):
        return self.agent._calculer_statut_rag(
            self.modele, [self.modele], profil_valide_par='X',
            environnement='production', backtest=bt)

    def test_fenetres_rouges_anterieures_bloquent_le_vert(self):
        bt = {'disponible': True, 'modele_recalibre_fidele': True,
              'gini_wf_moyen': 0.25, 'ae_ratio': 1.02,   # dernière fenêtre : bonne
              'ae_moyen_wf': 0.78, 'n_fenetres_rouge': 3,
              'stabilite_wf': '🟡 Moyen'}
        self.assertNotEqual(self._statut(bt), 'VERT',
            "3 fenêtres ROUGE sur 4 : le modèle a échoué la validation temporelle "
            "sur trois exercices. La dernière année ne rachète pas les autres.")
        print("    INV-6a 3 fenêtres ROUGE → VERT refusé ✅")

    def test_ae_moyen_hors_bande_bloque_le_vert(self):
        bt = {'disponible': True, 'modele_recalibre_fidele': True,
              'gini_wf_moyen': 0.25, 'ae_ratio': 1.05,
              'ae_moyen_wf': 0.85, 'n_fenetres_rouge': 0,
              'stabilite_wf': '🟡 Moyen'}
        self.assertNotEqual(self._statut(bt), 'VERT',
            "A/E moyen 0,85 sur l'ensemble des fenêtres = biais persistant.")
        print("    INV-6b A/E moyen hors bande → VERT refusé ✅")

    def test_walk_forward_sain_reste_vert(self):
        """Contrôle négatif : le garde-fou ne doit pas plafonner en permanence."""
        bt = {'disponible': True, 'modele_recalibre_fidele': True,
              'gini_wf_moyen': 0.28, 'ae_ratio': 1.01,
              'ae_moyen_wf': 1.01, 'n_fenetres_rouge': 0,
              'stabilite_wf': '🟢 Stable'}
        self.assertEqual(self._statut(bt), 'VERT')
        print("    INV-6c Walk-forward sain → VERT accessible ✅")

    def test_gate_et_rapports_disent_la_meme_chose(self):
        """Le gate et la source unique d'avertissement ne doivent JAMAIS
        diverger : un livrable qui contredit la certification, c'est le
        BLOQUANT B3 (audit V10)."""
        cas = [
            {'disponible': True, 'modele_recalibre_fidele': True,
             'gini_wf_moyen': 0.28, 'ae_ratio': 1.01, 'ae_moyen_wf': 1.01,
             'n_fenetres_rouge': 0, 'stabilite_wf': '🟢 Stable'},
            {'disponible': True, 'modele_recalibre_fidele': True,
             'gini_wf_moyen': 0.25, 'ae_ratio': 1.02, 'ae_moyen_wf': 0.78,
             'n_fenetres_rouge': 3, 'stabilite_wf': '🟡 Moyen'},
            {'disponible': True, 'modele_recalibre_fidele': False,
             'gini_wf_moyen': 0.25, 'ae_ratio': 1.00, 'ae_moyen_wf': 1.00,
             'n_fenetres_rouge': 0, 'stabilite_wf': '🟢 Stable'},
            {'disponible': False},
        ]
        for i, bt in enumerate(cas):
            with self.subTest(cas=i):
                gate_vert = self._statut(bt) == 'VERT'
                rapport_silencieux = avertissement_walk_forward(bt) is None
                self.assertEqual(gate_vert, rapport_silencieux,
                    f"Cas {i} : le gate dit {'VERT' if gate_vert else 'pas VERT'} "
                    f"mais le rapport "
                    f"{'ne dit rien' if rapport_silencieux else 'avertit'} — "
                    f"le livrable contredit la certification.")
        print("    INV-6d Gate et rapports strictement alignés (4 cas) ✅")


class TestInvariant_ExclusionsRemonteesDansLesLivrables(unittest.TestCase):
    """
    INVARIANT N°7 — Une exclusion ne doit JAMAIS être silencieuse.

    Constat I5 du certificateur (audit V11) : les colonnes écartées de la matrice
    X n'apparaissaient dans AUCUN livrable — seulement dans un WARNING de log,
    que personne ne lit. C'est ce silence qui a rendu le BLOQUANT B5 si coûteux :
    'antecedents_sinistres_3ans', LE facteur tarifaire de la RC Pro, était
    détruit (−17,4 % de Gini) sans que rien ne l'indique à l'actuaire.

    Une exclusion de genre ou de sinistralité est obligatoire — mais une colonne
    écartée parce qu'elle n'est pas DÉCLARÉE peut être un facteur parfaitement
    légitime : l'actuaire doit le savoir pour le déclarer.
    """

    def test_les_trois_livrables_appellent_la_source_unique(self):
        import inspect
        from direction_non_vie.tarification.services import (
            tarif_excel, rapport_equipe_tarif, rapport_modeles_tarif,
        )
        for module in (tarif_excel, rapport_equipe_tarif, rapport_modeles_tarif):
            with self.subTest(module=module.__name__):
                self.assertIn('synthese_exclusions', inspect.getsource(module),
                    f"{module.__name__} ne remonte pas les exclusions de "
                    f"conformité : un facteur tarifaire peut être détruit en "
                    f"silence (BLOQUANT B5).")
        print("    INV-7a Excel · Word/HTML · rapport d'équipe : exclusions "
              "remontées ✅")

    def test_la_synthese_distingue_action_requise_et_exclusion_obligatoire(self):
        from core.conformite_reglementaire import (
            synthese_exclusions, construire_matrice_x,
        )
        # Une colonne non déclarée = peut-être un facteur légitime → ACTION.
        mx = construire_matrice_x(['age', 'mon_facteur_metier_rare'],
                                  contexte='test')
        txt = synthese_exclusions(mx.exclusions)
        self.assertIsNotNone(txt)
        self.assertIn('ACTION REQUISE', txt)
        self.assertIn('mon_facteur_metier_rare', txt)

        # Genre et sinistralité = exclusions obligatoires → PAS d'action.
        mx2 = construire_matrice_x(['age', 'sexe', 'montant_sinistres'],
                                   contexte='test')
        txt2 = synthese_exclusions(mx2.exclusions)
        self.assertNotIn('ACTION REQUISE', txt2)
        self.assertIn('C-236/09', txt2)

        # Rien à signaler → silence.
        self.assertIsNone(synthese_exclusions({}))
        print("    INV-7b La synthèse distingue action requise / exclusion "
              "obligatoire ✅")

    def test_le_scenario_B5_serait_desormais_visible(self):
        """Reproduction du BLOQUANT B5 : si un facteur déclaré venait à être
        détruit, l'actuaire DOIT le voir dans le rapport."""
        from core.conformite_reglementaire import (
            synthese_exclusions, construire_matrice_x,
        )
        mx = construire_matrice_x(
            ['nb_salaries', 'un_facteur_non_declare_critique'], contexte='RC Pro')
        txt = synthese_exclusions(mx.exclusions)
        self.assertIsNotNone(txt,
            "Un facteur écarté doit produire un message visible dans le rapport.")
        self.assertIn('un_facteur_non_declare_critique', txt)
        self.assertIn('amputé', txt)
        print("    INV-7c Un facteur détruit est désormais VISIBLE dans le "
              "rapport (B5 ne peut plus être silencieux) ✅")


class TestInvariant_AntiSelectionVisibleEtDisqualifiante(unittest.TestCase):
    """
    INVARIANT N°8 — Un modèle ANTI-SÉLECTIF ne doit jamais passer inaperçu.

    Trouvé par auto-audit (11/07/2026). A3, A4 et A5 écrêtaient le Gini à
    [0, 1] : un Gini réel de −0,50 était rapporté « 0,0000 ». Or les deux
    situations n'ont rien à voir —
      · Gini = 0    → modèle inutile (aucune discrimination) ;
      · Gini = −0,50 → modèle RUINEUX : il attribue les primes les plus faibles
        aux risques les plus élevés, organisant activement l'anti-sélection.
    Et A6 (walk-forward), lui, n'écrêtait pas : la règle différait selon
    l'endroit — encore une fois.

    Le Gini est désormais rapporté à sa valeur vraie, borné à [−1, 1], et un
    Gini négatif est DISQUALIFIANT (ROUGE), quel que soit le score composite —
    lequel est relatif au meilleur modèle du profil, et vaut donc ≈ 1,0 même si
    TOUS les modèles sont anti-sélectifs.
    """

    def setUp(self):
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
        self.a3 = AgentA3GLM(models_path='/tmp', audit_path='/tmp', verbose=False)
        self.a4 = AgentA4ML(models_path='/tmp', audit_path='/tmp', verbose=False)
        self.a6 = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp',
                                     verbose=False)
        self.y = np.array([0., 0., 1., 1., 2., 3.])
        self.pred_antiselectif = np.array([9., 8., 7., 3., 2., 1.])
        self.pred_discriminant = np.array([1., 2., 3., 7., 8., 9.])

    def test_le_gini_negatif_n_est_plus_masque(self):
        for nom, agent in [('A3', self.a3), ('A4', self.a4)]:
            with self.subTest(agent=nom):
                g = agent._calculer_gini(self.y, self.pred_antiselectif)
                self.assertLess(g, 0,
                    f"{nom} rapporte {g} pour un modèle anti-sélectif : "
                    f"l'écrêtage masque le défaut le plus dangereux qui soit.")
                self.assertGreaterEqual(g, -1.0)
        print("    INV-8a Gini négatif rapporté à sa valeur vraie (plus d'écrêtage) ✅")

    def test_le_gini_positif_reste_correct(self):
        """Contrôle négatif : la correction ne doit pas dégrader le cas normal."""
        for nom, agent in [('A3', self.a3), ('A4', self.a4)]:
            with self.subTest(agent=nom):
                g = agent._calculer_gini(self.y, self.pred_discriminant)
                self.assertGreater(g, 0)
                self.assertLessEqual(g, 1.0)
        print("    INV-8b Gini positif inchangé ✅")

    def test_anti_selection_est_disqualifiante(self):
        bt = {'disponible': True, 'modele_recalibre_fidele': True,
              'gini_wf_moyen': 0.2, 'ae_ratio': 1.0, 'ae_moyen_wf': 1.0,
              'n_fenetres_rouge': 0, 'stabilite_wf': '🟢 Stable'}
        # Score composite EXCELLENT mais modèle anti-sélectif → ROUGE.
        m = {'score_global': 0.99, 'gini_test': -0.30}
        statut = self.a6._calculer_statut_rag(
            m, [m], profil_valide_par='X', environnement='production', backtest=bt)
        self.assertEqual(statut, 'ROUGE',
            "Un modèle anti-sélectif est ROUGE, quel que soit son score composite "
            "(qui est RELATIF au meilleur modèle du profil, et vaut donc ≈1,0 "
            "même si tous les modèles discriminent à l'envers).")
        # Contrôle négatif : un bon modèle reste VERT.
        m_bon = {'score_global': 0.99, 'gini_test': 0.30}
        self.assertEqual(self.a6._calculer_statut_rag(
            m_bon, [m_bon], profil_valide_par='X', environnement='production',
            backtest=bt), 'VERT')
        print("    INV-8c Anti-sélection → ROUGE · bon modèle → VERT ✅")


class TestInvariant_ControleParLEffet(unittest.TestCase):
    """
    INVARIANT N°9 — Une fuite doit être détectée par son EFFET, pas par son nom.

    Sept cycles ont durci des listes de noms ; sept fois, le cycle suivant a
    trouvé le nom qui passait au travers. Le dernier en date (BLOQUANT B6,
    audit V12) : 'garantie_montant_regle' — le montant réglé au titre de la
    garantie, colonne parfaitement standard d'une extraction jointe aux
    sinistres — traversait les TROIS filtres nominaux via le préfixe
    'garantie_' (car 'garantie' est un facteur légitime). Gini 0,0709 → 0,9222
    (+1201 %). Et le walk-forward, contaminé par la même fuite, la CONFIRMAIT
    au lieu de la détecter.

    Le contrôle par l'effet ne dépend d'aucun nom : il attrape les fuites que
    personne n'a encore imaginées. C'est le seul garde-fou qui ne repose pas sur
    l'imagination de celui qui l'écrit.
    """

    def test_une_fuite_est_detectee_quel_que_soit_son_nom(self):
        from core.conformite_reglementaire import construire_matrice_x
        rng = np.random.default_rng(99)
        n = 3000
        cout = np.where(rng.poisson(.2, n) > 0, rng.gamma(2, 1200, n), 0.)
        df = pd.DataFrame({
            'age': rng.integers(18, 80, n).astype(float),
            'bonus_malus': rng.uniform(.5, 3.5, n),
            'nb_sinistres': (cout > 0).astype(float),
            # ⚠ Trois fuites aux noms INSOUPÇONNABLES, qui passent tous les
            # filtres NOMINAUX (préfixe d'un facteur autorisé) :
            'garantie_montant_regle': cout,
            'usage_loss_ratio': cout / 1000.,
            'age_burning_cost': cout * 2,
        })
        candidates = ['age', 'bonus_malus', 'garantie_montant_regle',
                      'usage_loss_ratio', 'age_burning_cost']
        mx = construire_matrice_x(candidates, contexte='test',
                                  df=df, col_cible='nb_sinistres')
        for fuite in ['garantie_montant_regle', 'usage_loss_ratio',
                      'age_burning_cost']:
            self.assertNotIn(fuite, list(mx),
                f"'{fuite}' fuit dans la matrice X : le contrôle par l'effet "
                f"n'a pas fonctionné.")
            self.assertIn(fuite, mx.exclusions)
            self.assertIn("EFFET", mx.exclusions[fuite])
        # Contrôle négatif indispensable : aucun facteur légitime écarté.
        self.assertIn('age', list(mx))
        self.assertIn('bonus_malus', list(mx))
        print("    INV-9a 3 fuites à noms insoupçonnables détectées par l'effet ✅")

    def test_aucun_faux_positif_sur_les_facteurs_legitimes(self):
        """Le garde-fou ne doit pas écarter de vrais facteurs tarifaires.
        Aucun ne corrèle à 0,80+ avec la sinistralité : le bonus-malus, meilleur
        prédicteur de l'auto, plafonne autour de 0,30."""
        from core.conformite_reglementaire import detecter_fuites_par_effet
        rng = np.random.default_rng(3)
        n = 4000
        expo = np.clip(rng.beta(5, 1, n), .05, 1.)
        bm = np.clip(rng.normal(.9, .2, n), .5, 3.5)
        age = rng.integers(18, 85, n)
        nb = rng.poisson(expo * .10 * np.exp(.4*np.log(bm) + .5*(age < 25)))
        df = pd.DataFrame({
            'nb_sinistres': nb.astype(float), 'exposition': expo,
            'age': age.astype(float), 'bonus_malus': bm,
            'puissance_fiscale': rng.integers(4, 15, n).astype(float),
            'antecedents_sinistres_n1': rng.poisson(.15, n).astype(float),
        })
        feats = ['age', 'bonus_malus', 'puissance_fiscale',
                 'antecedents_sinistres_n1']
        fuites = detecter_fuites_par_effet(df, feats, 'nb_sinistres')
        self.assertEqual(fuites, {},
            f"Faux positif : facteur(s) légitime(s) écarté(s) — {fuites}")
        print("    INV-9b Aucun faux positif sur les facteurs légitimes ✅")

    def test_tous_les_agents_fournissent_les_donnees_au_controle(self):
        """Sans df ET col_cible, le contrôle par l'effet est INERTE : seuls les
        contrôles par le nom protègent — et l'audit V12 a démontré qu'ils sont
        structurellement insuffisants.

        Analyse par AST (et non par regex) : on inspecte les VRAIS appels de
        fonction, pas les mentions du nom dans les commentaires. Un test fragile
        ne prouve rien — la première version de ce test capturait les
        occurrences en commentaire et échouait à tort."""
        import ast, inspect
        from direction_non_vie.tarification.a3_glm import agent as a3
        from direction_non_vie.tarification.a4_ml import agent as a4
        from direction_non_vie.tarification.a5_deep_learning import agent as a5
        from direction_non_vie.tarification.a6_comparaison import agent as a6

        for mod in (a3, a4, a5, a6):
            with self.subTest(agent=mod.__name__):
                arbre = ast.parse(inspect.getsource(mod))
                appels = [
                    n for n in ast.walk(arbre)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == 'construire_matrice_x'
                ]
                self.assertTrue(appels,
                    f"{mod.__name__} : aucun appel à construire_matrice_x().")
                for appel in appels:
                    kw = {k.arg for k in appel.keywords}
                    self.assertIn('df', kw,
                        f"{mod.__name__} (ligne {appel.lineno}) appelle "
                        f"construire_matrice_x SANS df : le contrôle par l'effet "
                        f"est inerte.")
                    self.assertIn('col_cible', kw,
                        f"{mod.__name__} (ligne {appel.lineno}) appelle "
                        f"construire_matrice_x SANS col_cible : le contrôle par "
                        f"l'effet est inerte.")
        print("    INV-9c Les 4 agents alimentent le contrôle par l'effet "
              "(df + col_cible) — vérifié par AST ✅")

    def test_gini_implausible_plafonne_a_ambre(self):
        """Pendant du contrôle par l'effet, au niveau du RÉSULTAT : même une
        fuite qui aurait traversé tous les filtres se trahit par une performance
        impossible. Les deux fuites bloquantes affichaient 0,91 (V8) et 0,92
        (V12) ; la littérature situe les GLM de fréquence auto entre 0,15 et
        0,35."""
        from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
        a6 = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp',
                                verbose=False)
        bt = {'disponible': True, 'modele_recalibre_fidele': True,
              'gini_wf_moyen': 0.30, 'ae_ratio': 1.0, 'ae_moyen_wf': 1.0,
              'n_fenetres_rouge': 0, 'stabilite_wf': '🟢 Stable'}
        m_fuite = {'score_global': 0.99, 'gini_test': 0.92}   # signature de fuite
        self.assertNotEqual(
            a6._calculer_statut_rag(m_fuite, [m_fuite], profil_valide_par='X',
                                    environnement='production', backtest=bt),
            'VERT',
            "Un Gini de 0,92 en fréquence Non-Vie est actuariellement "
            "impossible : c'est une fuite, pas un exploit.")
        m_ok = {'score_global': 0.99, 'gini_test': 0.32}      # bon modèle réel
        self.assertEqual(
            a6._calculer_statut_rag(m_ok, [m_ok], profil_valide_par='X',
                                    environnement='production', backtest=bt),
            'VERT', "Un Gini de 0,32 est excellent et plausible — VERT accessible.")
        print("    INV-9d Gini implausible (0,92) → AMBRE · Gini réaliste (0,32) "
              "→ VERT ✅")


class TestInvariant_JetonMatriceXPrive(unittest.TestCase):
    """
    INVARIANT N°10 — Le jeton de MatriceX ne doit pas être exposé sur la classe.

    Constat I6 (audit V12) : _JETON était un ATTRIBUT DE CLASSE public, et la
    docstring affirmait « seul ce module y a accès ». C'était FAUX :
        MatriceX([...], _jeton=MatriceX._JETON)
    fonctionnait parfaitement. Une garantie qu'on affirme sans l'avoir vérifiée
    est pire qu'une absence de garantie : elle endort la vigilance.
    """

    def test_le_jeton_n_est_pas_exposé_sur_la_classe(self):
        from core.conformite_reglementaire import MatriceX
        self.assertFalse(hasattr(MatriceX, '_JETON'),
            "MatriceX._JETON est public : MatriceX([...], _jeton=MatriceX._JETON) "
            "permet de forger une matrice non conforme.")
        with self.assertRaises(TypeError):
            MatriceX(['sexe'], {}, 'contournement',
                     _jeton=getattr(MatriceX, '_JETON', None))
        print("    INV-10 Jeton non exposé sur la classe ✅")


if __name__ == '__main__':
    print("=" * 70)
    print("  TESTS D'INVARIANTS — le code se contredit-il lui-même ?")
    print("=" * 70)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} invariant(s)")
