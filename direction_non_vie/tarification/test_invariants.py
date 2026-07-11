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


if __name__ == '__main__':
    print("=" * 70)
    print("  TESTS D'INVARIANTS — le code se contredit-il lui-même ?")
    print("=" * 70)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} invariant(s)")
