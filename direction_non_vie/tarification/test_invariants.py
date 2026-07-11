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


if __name__ == '__main__':
    print("=" * 70)
    print("  TESTS D'INVARIANTS — le code se contredit-il lui-même ?")
    print("=" * 70)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} invariant(s)")
