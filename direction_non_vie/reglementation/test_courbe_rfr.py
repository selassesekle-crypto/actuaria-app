# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — RÉFÉRENTIEL DE COURBE RFR  ·  FILET
=============================================================================

⚠️ LE CLASSEUR D'ESSAI EST CONSTRUIT ICI, PAS CHARGÉ. Le vrai fichier EIOPA
vit sur le poste de l'actuaire, pas dans le dépôt : un filet qui en dépendrait
serait vert chez l'un et absent chez l'autre. La forme reproduite est celle du
fichier du 31/07/2026, relevée cellule par cellule — pays en tête de colonne,
code de courbe dessous, paramètres étiquetés en colonne 1, taux ensuite.

Le lecteur est par ailleurs exercé sur le VRAI classeur dans la preuve du lot ;
ce qui est verrouillé ici, c'est le COMPORTEMENT, y compris les refus.

⚠️ POURQUOI CE FICHIER N'EST PAS DANS `core/` À CÔTÉ DE SON MODULE. Parce
qu'aucune gate ne l'y exécuterait : `core/` ne contient AUCUN fichier de test,
et la gate scanne `direction_non_vie`. Vérifié plutôt que supposé — la
découverte y trouve 56 modules, et `core.test_courbe_rfr` n'en faisait pas
partie. Un filet que personne ne lance n'existe pas, et c'est la leçon du lot
F2, où la gate perdait A7 EN ENTIER en annonçant « OK ».

C'est aussi la convention déjà établie du dépôt : un module de `core/` est
testé depuis la direction qui le consomme — `core/mapping_client.py` par
`tarification/test_mapping_client.py`, `core/derivations.py` par
`tarification/test_derivations.py`. Le référentiel de taux vit ici parce que
`reglementation/` héberge déjà `segments_s2.py`, l'autre table partagée.
"""

import io
import unittest

from core import courbe_rfr as R

try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:                                        # pragma: no cover
    PANDAS_OK = False

#: Quelques maturités suffisent : ce qui est testé est la LECTURE, pas
#: l'interpolation sur cent cinquante points.
_MATS = (1, 2, 5, 10, 20, 30)
_TAUX = (0.02826, 0.02931, 0.02987, 0.03159, 0.03354, 0.03371)


def _classeur(code='EUR_31_07_2026_SWP_LLP_20_EXT_40_UFR_3.30',
              ufr=3.3, llp=20, convergence=40, va_sans=None, va_avec=13,
              lignes_avant=0, pays='Euro'):
    """Un classeur à la forme du fichier EIOPA officiel.

    `lignes_avant` insère des lignes vides en tête : c'est ce qui distingue
    un lecteur qui compte les rangs d'un lecteur qui lit les contenus.
    """
    def onglet(va):
        lignes = [[None, None, None]] * lignes_avant
        lignes += [
            [None, None,             None],
            [None, 'Main menu',      pays],
            [None, None,             code],
            [None, 'Coupon_freq',    1],
            [None, 'LLP',            llp],
            [None, 'Convergence',    convergence],
            [None, 'UFR',            ufr],
            [None, 'alpha',          0.066628],
            [None, 'CRA',            10],
            [None, 'VA',             va],
        ]
        lignes += [[None, m, t] for m, t in zip(_MATS, _TAUX)]
        return pd.DataFrame(lignes)

    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon) as ecrivain:
        onglet(va_sans).to_excel(ecrivain, sheet_name='RFR_spot_no_VA',
                                 header=False, index=False)
        onglet(va_avec).to_excel(ecrivain, sheet_name='RFR_spot_with_VA',
                                 header=False, index=False)
    return tampon.getvalue()


class TRFR_Base(unittest.TestCase):
    def setUp(self):
        if not PANDAS_OK:
            self.skipTest("pandas absent — pas de classeur à lire")


# =============================================================================
#  RFR-1 — LE LECTEUR AUTO-VÉRIFIANT
# =============================================================================

class TRFR1_Lecteur(TRFR_Base):

    def test_le_classeur_officiel_est_lu_avec_sa_date(self):
        """La date d'arrêté vient du FICHIER, elle n'est pas saisie — c'est
        ce qui rend la courbe opposable."""
        c = R.lire_classeur_eiopa(_classeur())
        self.assertEqual(c.date_arrete, '2026-07-31')
        self.assertEqual(c.devise, 'EUR')
        self.assertFalse(c.avec_va)
        self.assertEqual(len(c.maturites), len(_MATS))
        self.assertAlmostEqual(R.actualiser(c, 10), 0.03159, places=6)
        self.assertEqual((c.ufr, c.cra_bps, c.llp, c.convergence),
                         (3.3, 10.0, 20.0, 40.0))
        print("    OK RFR-1a le classeur est lu, la date d'arrêté 2026-07-31 "
              "vient du fichier")

    def test_les_deux_declarations_doivent_concorder(self):
        """⚠️ LE VERROU CENTRAL. Le classeur écrit la MÊME chose deux fois —
        le code `..._LLP_20_EXT_40_UFR_3.30` et les lignes de paramètres. Un
        lecteur qui n'en lit qu'une continue de produire une courbe quand
        EIOPA réorganise son fichier, sans produire la bonne."""
        for champ, valeur, mot in (('ufr', 4.2, 'UFR'),
                                   ('llp', 50, 'LLP'),
                                   ('convergence', 60, 'convergence')):
            with self.assertRaises(R.CourbeIllisible) as leve:
                R.lire_classeur_eiopa(_classeur(**{champ: valeur}))
            self.assertIn('se contredit', str(leve.exception))
            self.assertIn(mot, str(leve.exception))
        print("    OK RFR-1b une divergence sur UFR, LLP ou convergence est "
              "refusée — le lecteur ne choisit pas entre les deux")

    def test_une_ligne_inseree_ne_decale_pas_la_lecture(self):
        """Pays, code et paramètres sont cherchés par leur CONTENU et leur
        LIBELLÉ. Un lecteur qui compterait les rangs lirait de travers."""
        for avant in (0, 1, 3):
            c = R.lire_classeur_eiopa(_classeur(lignes_avant=avant))
            self.assertEqual(c.date_arrete, '2026-07-31',
                             f"{avant} ligne(s) insérée(s) décalent la lecture")
            self.assertAlmostEqual(R.actualiser(c, 10), 0.03159, places=6)
        print("    OK RFR-1c 0, 1 puis 3 lignes insérées en tête : la lecture "
              "est identique")

    def test_un_classeur_qui_n_est_pas_celui_attendu_est_refuse(self):
        """Refuser en disant quoi, plutôt que rendre une courbe devinée."""
        with self.assertRaises(R.CourbeIllisible) as sans_pays:
            R.lire_classeur_eiopa(_classeur(pays='Atlantide'))
        self.assertIn('Euro', str(sans_pays.exception))
        with self.assertRaises(R.CourbeIllisible) as sans_code:
            R.lire_classeur_eiopa(_classeur(code='courbe maison v3'))
        self.assertIn("date d'arrêté", str(sans_code.exception))
        with self.assertRaises(R.CourbeIllisible):
            R.lire_classeur_eiopa(b'ceci n est pas un classeur')
        print("    OK RFR-1d pays absent, code non reconnu, fichier illisible "
              "— trois refus motivés, aucune courbe devinée")

    def test_le_lecteur_leve_au_lieu_de_se_rabattre(self):
        """⚠️ UNE BIBLIOTHÈQUE QUI SUBSTITUE EN SILENCE EST PIRE QU'UNE QUI
        REFUSE. Le repli sur l'embarquée est une décision d'AGENT, prise par
        l'appelant, qui sait ce qu'il publie."""
        with self.assertRaises(R.CourbeIllisible):
            R.lire_classeur_eiopa(b'')
        print("    OK RFR-1e le lecteur lève ; le repli appartient à "
              "l'appelant, pas au référentiel")


# =============================================================================
#  RFR-2 — LE VA EST LU, JAMAIS DÉCLARÉ
# =============================================================================

class TRFR2_VolatilityAdjustment(TRFR_Base):

    def test_avec_va_est_lu_dans_le_fichier(self):
        """La courbe sait d'elle-même ce qu'elle est : la ligne VA est vide
        sur l'onglet sans VA, renseignée sur l'autre."""
        sans = R.lire_classeur_eiopa(_classeur())
        avec = R.lire_classeur_eiopa_avec_va(_classeur(), agrement_acpr=True)
        self.assertFalse(sans.avec_va)
        self.assertIsNone(sans.va_bps)
        self.assertTrue(avec.avec_va)
        self.assertEqual(avec.va_bps, 13.0)
        print("    OK RFR-2a `avec_va` vient de la ligne VA du fichier, pas "
              "d'un argument")

    def test_un_onglet_qui_dement_son_nom_est_refuse(self):
        """Si la ligne VA contredit l'onglet demandé, le fichier n'est pas
        celui qu'on croit."""
        with self.assertRaises(R.CourbeIllisible):
            R.lire_classeur_eiopa(_classeur(va_sans=13))
        with self.assertRaises(R.CourbeIllisible):
            R.lire_classeur_eiopa_avec_va(_classeur(va_avec=None), True)
        print("    OK RFR-2b un onglet dont la ligne VA dément son nom est "
              "refusé")

    def test_l_agrement_n_a_pas_de_valeur_par_defaut(self):
        """⚠️ L'ART. 77 QUINQUIES DEVIENT UN FAIT DE CODE. Le VA suppose
        l'agrément de l'autorité de contrôle ; un défaut à `False` le ferait
        oublier, un défaut à `True` le supposerait acquis. Il n'y en a pas."""
        with self.assertRaises(TypeError):
            R.lire_classeur_eiopa_avec_va(_classeur())     # sans l'argument
        with self.assertRaises(ValueError):
            R.lire_classeur_eiopa_avec_va(_classeur(), agrement_acpr=False)
        avec = R.lire_classeur_eiopa_avec_va(_classeur(), agrement_acpr=True)
        with self.assertRaises(TypeError):
            R.actualiser_avec_va(avec, 10)                  # idem à l'usage
        print("    OK RFR-2c l'agrément est exigé à la lecture ET à chaque "
              "actualisation — jamais par défaut")

    def test_actualiser_refuse_une_courbe_avec_va(self):
        """Le point de la typologie (A)/(B) : l'actualisation de base ne peut
        pas prendre la variante par mégarde."""
        avec = R.lire_classeur_eiopa_avec_va(_classeur(), agrement_acpr=True)
        with self.assertRaises(ValueError) as leve:
            R.actualiser(avec, 10)
        self.assertIn('77 quinquies', str(leve.exception))
        sans = R.lire_classeur_eiopa(_classeur())
        with self.assertRaises(ValueError):
            R.actualiser_avec_va(sans, 10, agrement_acpr=True)
        print("    OK RFR-2d `actualiser` refuse une courbe avec VA, et "
              "l'inverse aussi")


# =============================================================================
#  RFR-3 — SANS DATE D'ARRÊTÉ, JAMAIS UN CHIFFRE DÉFINITIF
# =============================================================================

class TRFR3_Peremption(TRFR_Base):

    def test_une_courbe_sans_date_est_rouge(self):
        """⚠️ LA RÈGLE QUE CE LOT POSE, ET ELLE CORRIGE UN SILENCE MESURÉ.

        Une courbe fournie sans date recevait « NON TESTABLE », qui n'est ni
        `'ROUGE'` (donc aucun plafonnement) ni dans `('AMBRE','ROUGE')` (donc
        aucune alerte) : elle traversait DEUX circuits de gouvernance sans en
        déclencher un seul. Le repli explicite était mieux gouverné que la
        saisie de l'actuaire.
        """
        tampon = io.BytesIO()
        pd.DataFrame({'maturite': [1, 10],
                      'taux_pct': [2.826, 3.159]}).to_excel(tampon, index=False)
        for lib, courbe in (('taux plat', R.taux_plat(3.0)),
                            ('extrait 2 colonnes',
                             R.lire_deux_colonnes(tampon.getvalue()))):
            self.assertIsNone(courbe.date_arrete, lib)
            diag = R.diagnostic_peremption(courbe)
            self.assertEqual(diag['statut'], 'ROUGE', lib)
            self.assertIn("SANS DATE D'ARRÊTÉ", diag['message'])
        print("    OK RFR-3a les deux portes secondaires sont ROUGE : sans "
              "arrêté, aucun chiffre définitif")

    def test_une_courbe_datee_vieillit_par_paliers(self):
        c = R.lire_classeur_eiopa(_classeur())
        for valorisation, attendu in (('2026-08-31', 'VERT'),
                                      ('2026-12-31', 'AMBRE'),
                                      ('2027-09-30', 'ROUGE')):
            self.assertEqual(
                R.diagnostic_peremption(c, valorisation)['statut'], attendu,
                valorisation)
        print("    OK RFR-3b VERT sous 3 mois, AMBRE au-delà, ROUGE au-delà "
              "d'un an")

    def test_un_arrete_passe_est_juge_a_sa_date(self):
        """Un arrêté du 31/12/2026 recalculé en 2028 ne doit pas déclarer sa
        courbe périmée à tort."""
        c = R.lire_classeur_eiopa(_classeur())
        self.assertEqual(
            R.diagnostic_peremption(c, '2026-08-15')['statut'], 'VERT')
        print("    OK RFR-3c la date de valorisation est respectée")

    def test_l_embarquee_porte_sa_date_et_sa_provenance(self):
        emb = R.courbe_embarquee()
        self.assertEqual(emb.date_arrete, R.DATE_EMBARQUEE)
        self.assertEqual(len(emb.maturites), 150)
        self.assertAlmostEqual(R.actualiser(emb, 10), 0.03159, places=6)
        self.assertIn('RFR_spot_no_VA', emb.provenance)
        self.assertFalse(emb.avec_va)
        print(f"    OK RFR-3d embarquée du {emb.date_arrete}, 150 maturités, "
              f"10 ans = {100 * R.actualiser(emb, 10):.3f} %")


# =============================================================================
#  RFR-4 — LA TYPOLOGIE, VERROUILLÉE COMME TELLE
# =============================================================================

class TRFR4_Typologie(TRFR_Base):

    #: (C) — ce qui n'est PAS un taux d'actualisation réglementaire.
    _EXCLUS = ('oat', 'bce', 'inflation', 'ifrs', 'illiq', 'macro',
               'directeur', 'spread')

    def test_le_referentiel_n_expose_que_le_taux_d_actualisation(self):
        """⚠️ LE VERROU CONTRE LE FOURRE-TOUT. Un référentiel où chacun pioche
        reproduirait le problème qu'il résout. L'OAT n'entre dans aucun
        calcul, le taux directeur BCE n'a aucun usage nulle part, l'inflation
        est une hypothèse de projection, et le taux IFRS 17 est un DÉRIVÉ qui
        se calcule chez A11 à partir d'ici."""
        publics = [n for n in dir(R) if not n.startswith('_')]
        for nom in publics:
            for exclu in self._EXCLUS:
                self.assertNotIn(
                    exclu, nom.lower(),
                    f"`{nom}` fait entrer « {exclu} » dans le référentiel — "
                    f"c'est le fourre-tout que ce module refuse d'être")
        print(f"    OK RFR-4a aucun des {len(publics)} noms publics ne porte "
              f"un taux de la famille (C)")

    def test_aucun_accesseur_generique(self):
        """⚠️ UN PARAMÈTRE CHAÎNE EST LE FOURRE-TOUT. C'est ce mécanisme qui
        avait fait choisir un écart type par sous-chaîne du nom de branche au
        lot B10-c : `'rc' in 'rc_auto'` était vrai, et le choix était faux sur
        treize noms sur dix-sept."""
        import inspect
        suspects = ('nature', 'type', 'kind', 'quel', 'lequel', 'variante')
        for nom, objet in vars(R).items():
            if nom.startswith('_') or not inspect.isfunction(objet):
                continue
            for parametre in inspect.signature(objet).parameters:
                self.assertNotIn(
                    parametre.lower(), suspects,
                    f"`{nom}({parametre}=...)` est un accesseur générique : "
                    f"une fonction par question, pas un paramètre qui choisit")
        print("    OK RFR-4b aucune fonction ne prend un paramètre qui "
              "choisit le taux à rendre")

    def test_une_fonction_par_question(self):
        """Les quatre questions du référentiel ont chacune leur porte."""
        for nom in ('courbe_embarquee', 'lire_classeur_eiopa',
                    'lire_classeur_eiopa_avec_va', 'lire_deux_colonnes',
                    'taux_plat', 'actualiser', 'actualiser_avec_va',
                    'facteur_actualisation', 'diagnostic_peremption',
                    'resume_confirmation'):
            self.assertTrue(callable(getattr(R, nom, None)), nom)
        print("    OK RFR-4c les dix fonctions du référentiel sont en place")


# =============================================================================
#  RFR-5 — LE GARDE-FOU D'UNITÉ SUR LES PORTES SECONDAIRES
# =============================================================================

class TRFR5_Unite(TRFR_Base):

    def test_le_garde_fou_d_unite_tient_sur_les_deux_portes(self):
        """EIOPA publie en décimal, ces portes attendent des pourcents : une
        série décimale y produirait une courbe cent fois trop basse."""
        with self.assertRaises(R.CourbeIllisible):
            R.taux_plat(0.03)
        tampon = io.BytesIO()
        pd.DataFrame({'maturite': [1, 10],
                      'taux_pct': [0.02826, 0.03159]}).to_excel(tampon,
                                                                index=False)
        with self.assertRaises(R.CourbeIllisible):
            R.lire_deux_colonnes(tampon.getvalue())
        self.assertAlmostEqual(R.actualiser(R.taux_plat(3.0), 10), 0.03,
                               places=6)
        print("    OK RFR-5a taux plat et extrait refusent une série en "
              "décimal ; 3,0 passe et vaut bien 3 %")

    def test_un_taux_nul_assume_reste_permis(self):
        self.assertEqual(R.actualiser(R.taux_plat(0.0), 10), 0.0)
        print("    OK RFR-5b un taux nul assumé n'est pas une erreur d'unité")

    def test_le_seuil_reste_calibre(self):
        """Le cas serré : une courbe légitime en taux négatifs tronquée aux
        maturités courtes a un maximum en MODULE de 0,60."""
        self.assertGreater(R.TAUX_MIN_PLAUSIBLE_PCT, 0.0337 * 2)
        self.assertLess(R.TAUX_MIN_PLAUSIBLE_PCT, 0.60 / 2)
        tampon = io.BytesIO()
        pd.DataFrame({'maturite': [1, 5, 10],
                      'taux_pct': [-0.60, -0.55, -0.25]}).to_excel(tampon,
                                                                   index=False)
        c = R.lire_deux_colonnes(tampon.getvalue())
        self.assertAlmostEqual(R.actualiser(c, 10), -0.0025, places=6)
        print(f"    OK RFR-5c seuil {R.TAUX_MIN_PLAUSIBLE_PCT} : une courbe "
              f"entièrement négative passe, c'est le module qui la sauve")


# =============================================================================
#  RFR-6 — L'AFFICHAGE DE CONFIRMATION
# =============================================================================

class TRFR6_Confirmation(TRFR_Base):

    def test_le_resume_porte_la_ligne_de_concordance(self):
        """⚠️ C'EST LA DERNIÈRE LIGNE QUI COMPTE. Sans elle, l'affichage
        demanderait à l'actuaire de contrôler ce qu'il n'a aucun moyen de
        contrôler : il verrait « 150 maturités, 10 ans 3,159 % » sans pouvoir
        savoir si c'est la bonne colonne pays."""
        texte = R.resume_confirmation(R.lire_classeur_eiopa(_classeur()))
        self.assertIn('2026-07-31', texte)
        self.assertIn('3.159', texte)
        self.assertIn('✓', texte)
        self.assertIn('concordants', texte)
        self.assertIn('LLP 20', texte)
        print("    OK RFR-6a le résumé porte la date, les témoins et la "
              "preuve de concordance")

    def test_une_courbe_sans_concordance_le_dit(self):
        """Le résumé ne doit pas ressembler à une confirmation quand il n'y a
        rien eu à confirmer."""
        texte = R.resume_confirmation(R.taux_plat(3.0))
        self.assertNotIn('✓', texte)
        self.assertIn('NON ÉTABLI', texte)
        self.assertIn('ROUGE', texte)
        print("    OK RFR-6b un taux plat affiche « arrêté NON ÉTABLI » et "
              "ROUGE, sans coche de concordance")



# =============================================================================
#  RFR-7 — L'ANACHRONISME : UNE COURBE POSTÉRIEURE À L'ARRÊTÉ
# =============================================================================

class TRFR7_Anachronisme(TRFR_Base):
    """⚠️ QUATRIÈME CAUSE DE ROUGE, ET CE N'EST PAS DE LA PÉREMPTION.

    Une courbe postérieure à l'arrêté n'est pas « trop vieille » : elle
    n'existait pas quand la clôture a été arrêtée. Le silence était total —
    un âge NÉGATIF passe sous tous les seuils, donc sortait VERT, avec ce
    message publié : « Courbe EIOPA du 2026-07-31 (-24 mois) — à jour pour
    l'arrêté retenu ». Un âge négatif s'affichait ET se certifiait à jour.

    ⚠️ ET CE N'EST PAS UN QUATRIÈME ÉTAT : rendre un second verdict aurait
    laissé deux valeurs à consulter, et un consommateur n'en aurait lu
    qu'une. Un statut, des causes nommées.
    """

    def test_une_courbe_posterieure_a_l_arrete_est_ROUGE(self):
        c = R.lire_classeur_eiopa(_classeur())      # arrêté 2026-07-31
        for valorisation in ('2026-07-30', '2026-01-31', '2024-07-31'):
            with self.subTest(arrete=valorisation):
                diag = R.diagnostic_peremption(c, valorisation)
                self.assertEqual(diag['statut'], 'ROUGE', valorisation)
                self.assertIn("POSTÉRIEURE À L'ARRÊTÉ", diag['message'])
                self.assertLessEqual(diag['age_mois'], 0)
        print("    OK RFR-7a une courbe qui n'existait pas à l'arrêté est "
              "ROUGE")

    def test_un_ecart_de_MOINS_D_UN_MOIS_se_dit_en_jours(self):
        """⚠️ DÉFAUT DE MA PROPRE PREMIÈRE VERSION, trouvé par ce test : à un
        jour d'écart, −0,03 mois s'arrondit à zéro et le message annonçait
        « 0 mois APRÈS l'arrêté » — un chiffre qui nie sa propre phrase."""
        diag = R.diagnostic_peremption(R.lire_classeur_eiopa(_classeur()),
                                       '2026-07-30')
        self.assertEqual(diag['statut'], 'ROUGE')
        self.assertIn('jour(s)', diag['message'])
        self.assertNotIn('0 mois APRÈS', diag['message'])
        print("    OK RFR-7e un écart de moins d'un mois se dit en jours")

    def test_le_message_ne_certifie_plus_un_age_negatif(self):
        """⚠️ LE DÉFAUT LITTÉRAL : « (-24 mois) — à jour pour l'arrêté
        retenu »."""
        diag = R.diagnostic_peremption(R.lire_classeur_eiopa(_classeur()),
                                       '2024-07-31')
        self.assertNotIn('à jour', diag['message'])
        self.assertIn('information future', diag['message'])
        print("    OK RFR-7b un âge négatif ne se certifie plus « à jour »")

    def test_le_jour_meme_reste_VERT(self):
        """La borne : l'arrêté ET la courbe au même jour n'est pas un
        anachronisme."""
        c = R.lire_classeur_eiopa(_classeur())
        self.assertEqual(R.diagnostic_peremption(c, '2026-07-31')['statut'],
                         'VERT')
        print("    OK RFR-7c le jour même n'est pas un anachronisme")

    def test_les_trois_autres_causes_de_ROUGE_sont_intactes(self):
        """⚠️ UNE CAUSE AJOUTÉE NE DOIT PAS EN MASQUER UNE AUTRE."""
        c = R.lire_classeur_eiopa(_classeur())
        self.assertEqual(R.diagnostic_peremption(c, '2027-09-30')['statut'],
                         'ROUGE')                       # périmée
        self.assertIn('PÉRIMÉE',
                      R.diagnostic_peremption(c, '2027-09-30')['message'])
        self.assertEqual(R.diagnostic_peremption(R.taux_plat(3.0))['statut'],
                         'ROUGE')                       # sans date
        self.assertEqual(R.diagnostic_peremption(c, '2026-12-31')['statut'],
                         'AMBRE')                       # l'AMBRE survit
        print("    OK RFR-7d péremption, absence de date et AMBRE intacts")


# =============================================================================
#  RFR-8 — LA DEVISE : ON NE COMPARE PAS CE QU'ON NE SAIT PAS LIRE
# =============================================================================

class TRFR8_Devise(TRFR_Base):
    """⚠️ `actualiser` NE LISAIT JAMAIS `courbe.devise`. Un engagement en
    dollars aurait été actualisé sur la courbe euro EN SILENCE, contre B79 —
    exigence que le socle IFRS 17 de ce dépôt déclare déjà sous
    `courbe_dans_la_monnaie`.

    ⚠️ GARDE LATENTE, comme l'était le refus du VA quand il a été posé :
    aucun appelant du dépôt ne déclare de devise, le passif Non-Vie n'en
    porte pas.
    """

    def test_sans_declaration_le_comportement_est_INCHANGE(self):
        """⚠️ LA CONDITION DE L'INNOCUITÉ : `None` ne déclenche rien."""
        c = R.courbe_embarquee()
        for m in (0.5, 1, 5, 10, 20, 30, 50):
            with self.subTest(maturite=m):
                self.assertEqual(R.actualiser(c, m), R.actualiser(c, m, None))
        print("    OK RFR-8a sans devise déclarée, rien ne change")

    def test_une_devise_concordante_passe(self):
        c = R.courbe_embarquee()
        self.assertEqual(R.actualiser(c, 10.0, 'EUR'), R.actualiser(c, 10.0))
        self.assertEqual(R.actualiser(c, 10.0, 'eur'), R.actualiser(c, 10.0))
        print("    OK RFR-8b la devise de la courbe passe, casse comprise")

    def test_une_devise_DISCORDANTE_est_refusee(self):
        c = R.courbe_embarquee()
        with self.assertRaises(ValueError) as e:
            R.actualiser(c, 10.0, 'USD')
        self.assertIn('B79', str(e.exception))
        print("    OK RFR-8c un engagement USD sur courbe EUR est refusé")

    def test_une_courbe_SANS_devise_ISO_est_refusee_et_NON_devinee(self):
        """⚠️ LE POINT DE FOND : le décodeur d'onglet EIOPA accepte deux ou
        trois lettres, et les onglets réels portent `FR_...` et `UK_...` —
        des PAYS. Traduire FR en EUR serait deviner, la ligne que
        `CourbeIllisible` trace déjà pour la lecture du classeur."""
        for faux in ('FR', 'UK', '?'):
            with self.subTest(devise=faux):
                c = R.courbe_embarquee()._replace(devise=faux)
                with self.assertRaises(ValueError) as e:
                    R.actualiser(c, 10.0, 'EUR')
                self.assertIn('deviner', str(e.exception))
                # ... et sans déclaration, cette même courbe passe
                self.assertIsInstance(R.actualiser(c, 10.0), float)
        print("    OK RFR-8d une devise non ISO se refuse au lieu de se "
              "traduire")

    def test_une_devise_d_engagement_non_ISO_est_refusee(self):
        c = R.courbe_embarquee()
        for mauvaise in ('EU', 'EUROS', 'euro'):
            with self.subTest(devise=mauvaise):
                with self.assertRaises(ValueError) as e:
                    R.actualiser(c, 10.0, mauvaise)
                self.assertIn('ISO 4217', str(e.exception))
        print("    OK RFR-8e la devise demandée doit être un code ISO 4217")

    def test_actualiser_avec_va_porte_la_MEME_garde(self):
        """⚠️ DEUX PORTES D'ACTUALISATION, UNE SEULE RÈGLE : une garde posée
        sur une seule des deux aurait laissé l'autre ouverte."""
        c = R.courbe_embarquee()._replace(avec_va=True, va_bps=13)
        with self.assertRaises(ValueError) as e:
            R.actualiser_avec_va(c, 10.0, True, 'USD')
        self.assertIn('B79', str(e.exception))
        self.assertIsInstance(R.actualiser_avec_va(c, 10.0, True, 'EUR'),
                              float)
        self.assertIsInstance(R.actualiser_avec_va(c, 10.0, True), float)
        print("    OK RFR-8f les deux portes d'actualisation sont gardées")


if __name__ == '__main__':
    unittest.main(verbosity=2)
