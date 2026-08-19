# =============================================================================
#  Tests — lot « avant Bootstrap » : livrables, courbe des taux, affichages
#
#  CE FICHIER MESURE DES TAILLES ET DES CONTENUS, JAMAIS L'ABSENCE D'EXCEPTION.
#  C'est tout son propos. Trois fois de suite, un livrable A7 a été cassé sans
#  qu'aucun test ne bronche, parce que le code rattrapait son propre échec et
#  rendait un repli :
#    · `generer_graphiques` masqué par un paramètre → 0 graphique (lot T20) ;
#    · `export_excel` → 0 octet sur un None (lot 1 de l'harmonisation) ;
#    · `export_html` → 88 octets sur un NameError, LA GATE ENTIÈRE AU VERT
#      (lot BFCC — 596 tests verts avec le rapport HTML cassé).
#  Un test qui se contente d'appeler la fonction sans lever ne voit rien de tout
#  cela. Il faut regarder ce qui SORT.
# =============================================================================

import inspect
import unittest
from datetime import date, timedelta

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    _TAILLE_MIN_LIVRABLE,
    AgentA7Provisionnement,
    _dependance_absente,
    _produire_livrable,
    etiquette_methode_grands,
)
from direction_non_vie.provisionnement.a7_provisionnement.config.lob_config import (
    LOB_CONFIG,
    get_lob_config,
)
from direction_non_vie.provisionnement.a7_provisionnement.config.rfr_eiopa import (
    DATE_COURBE,
    MOIS_ALERTE_PEREMPTION,
    MOIS_ROUGE_PEREMPTION,
    age_courbe_mois,
    diagnostic_peremption,
    get_courbe_embarquee,
)
from direction_non_vie.provisionnement.a7_provisionnement.n4_best_estimate import (
    CLE_BOOT,
    CLE_COMPOSE,
    CLE_MACK,
    LIBELLE_APPROCHE,
    libelle_percentiles,
    marque_retenue,
)
from direction_non_vie.provisionnement.a7_provisionnement.n5_excel import (
    export_excel,
)
from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
    ARRETE_ABSENT,
    MARQUEUR_ECHEC_RAPPORT,
    _build_blocks,
    _construire_contexte,
    _md_to_html,
    _nettoyer_narration,
    etat_calendaire,
    export_html,
    export_word,
)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_graphiques import (
    kaleido_declare,
    rendeur_substitue,
)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS,
)


def _exposition(triangle, loss_ratio=0.70):
    C = np.array(triangle, dtype=float)
    return C.max(axis=1) * 1.6 / loss_ratio


# =============================================================================
#  1. LES LIVRABLES DÉCLARENT LEUR ÉCHEC — ILS NE LE TAISENT PLUS
# =============================================================================

class T1_Livrables_Declarent(unittest.TestCase):
    """Un livrable dégradé est DÉCLARÉ dans le résultat, jamais deviné."""

    @classmethod
    def setUpClass(cls):
        # ⚠️ CE VERROU PORTE SUR LA DÉCLARATION DES LIVRABLES, pas sur les
        # pixels. Il faisait rasteriser 14 figures — 103 s mesurées — pour
        # inspecter un classeur Excel.
        with kaleido_declare(True), rendeur_substitue():
            cls.r = AgentA7Provisionnement(verbose=False).run(
                source=np.array(GENINS, dtype=float), mode_declare='cumule',
                primes=_exposition(GENINS), n_sim_bootstrap=300, seed=42,
                generer_graphiques=True, generer_word=True)

    def test_le_resultat_porte_un_bilan_des_livrables(self):
        self.assertTrue(self.r.get('success'), self.r.get('erreur'))
        self.assertIn('livrables_erreurs', self.r,
                      "le résultat doit porter le bilan des livrables")
        self.assertIsInstance(self.r['livrables_erreurs'], dict)
        print(f"    OK LIV-1 bilan présent : {self.r['livrables_erreurs'] or 'aucune erreur'}")

    def test_excel_est_un_vrai_classeur_pas_un_repli(self):
        """Le seul export dont la dépendance est toujours là : il doit sortir."""
        octets = self.r.get('excel_bytes', b'')
        self.assertGreater(len(octets), _TAILLE_MIN_LIVRABLE,
                           f"export_excel a rendu {len(octets)} octets — repli ?")
        # Un .xlsx est un ZIP : les deux premiers octets valent 'PK'.
        self.assertEqual(octets[:2], b'PK',
                         "ce ne sont pas les octets d'un classeur Excel")
        self.assertNotIn('excel', self.r['livrables_erreurs'])
        print(f"    OK LIV-2 Excel : {len(octets):,} octets, en-tête ZIP conforme")

    def test_un_livrable_vide_est_toujours_explique(self):
        """Aucun octet manquant sans motif — c'était exactement le trou."""
        for cle, nom in (('excel_bytes', 'excel'), ('word_bytes', 'word'),
                         ('html', 'html')):
            octets = self.r.get(cle, b'')
            if len(octets) >= _TAILLE_MIN_LIVRABLE:
                continue
            self.assertIn(nom, self.r['livrables_erreurs'],
                          f"{nom} rend {len(octets)} octets SANS motif déclaré")
            motif = self.r['livrables_erreurs'][nom]
            self.assertTrue(
                motif.startswith(('dependance_absente:', 'echec:', 'vide:')),
                f"motif non classé pour {nom} : {motif!r}")
            print(f"    OK LIV-3 {nom} vide, et le motif le dit : {motif}")

    def test_une_dependance_absente_nest_pas_un_echec_de_code(self):
        """La distinction qui manquait : bibliothèque absente ≠ bug."""
        for nom in ('word', 'pdf'):
            motif = self.r['livrables_erreurs'].get(nom)
            if motif is None:
                continue
            if _dependance_absente(nom):
                self.assertTrue(motif.startswith('dependance_absente:'),
                                f"{nom} : dépendance absente mais motif {motif!r}")
            else:
                self.assertFalse(
                    motif.startswith('dependance_absente:'),
                    f"{nom} : dépendance présente, le motif ne peut pas "
                    f"l'incriminer — {motif!r}")
        print("    OK LIV-4 dépendance absente et échec de code sont distingués")

    def test_un_echec_reel_est_classe_comme_tel(self):
        """Chemin d'échec exercé pour de vrai, pas seulement décrit."""
        def fabrique_qui_casse(**kw):
            raise TypeError('boum')
        octets, err = _produire_livrable('excel', fabrique_qui_casse)
        self.assertEqual(octets, b'')
        self.assertTrue(err.startswith('echec: TypeError'), err)

        octets, err = _produire_livrable('excel', lambda **kw: b'PK\x03\x04')
        self.assertTrue(err.startswith('vide:'),
                        f"4 octets doivent être classés 'vide:' — {err!r}")

        octets, err = _produire_livrable(
            'excel', lambda **kw: b'PK' + b'\x00' * _TAILLE_MIN_LIVRABLE)
        self.assertIsNone(err, "un livrable de taille normale n'a pas de motif")
        print("    OK LIV-5 les trois classements exercés : echec / vide / OK")


# =============================================================================
#  1bis. LE RAPPORT HTML — ET LE PDF QU'IL ALIMENTE
# =============================================================================

class T2_Rapport_HTML_Et_PDF(unittest.TestCase):
    """`export_html` rattrape ses échecs et rend une page d'erreur VALIDE."""

    def test_le_rapport_reel_ne_porte_pas_le_marqueur_dechec(self):
        r = AgentA7Provisionnement(verbose=False).run(
            source=np.array(GENINS, dtype=float), mode_declare='cumule',
            primes=_exposition(GENINS), n_sim_bootstrap=300, seed=42,
            generer_graphiques=False)
        html = export_html(r['n1'], r['n2'], r['n3'], r['n4'], {},
                           ref_client='test')
        self.assertFalse(html.startswith(MARQUEUR_ECHEC_RAPPORT),
                         "export_html est retombé sur son repli d'échec")
        self.assertGreater(len(html), 20_000, f"{len(html)} octets — repli ?")
        print(f"    OK LIV-6 rapport HTML : {len(html):,} octets, sans marqueur")

    def test_le_repli_porte_un_marqueur_detectable(self):
        """Sans marqueur, la page d'erreur est un HTML que rien ne distingue."""
        # n3 dépourvu des clés attendues → _build_blocks lève → repli.
        html = export_html({}, {}, {}, {}, {}, ref_client='casse')
        if html.startswith(MARQUEUR_ECHEC_RAPPORT):
            print(f"    OK LIV-7 repli marqué et détectable ({len(html)} octets)")
        else:
            # Le rapport a tenu sur des dicts vides : c'est légitime, mais alors
            # il doit être un VRAI rapport, pas un entre-deux silencieux.
            self.assertGreater(len(html), 20_000,
                               f"ni marqué comme repli, ni un rapport complet "
                               f"({len(html)} octets)")
            print(f"    OK LIV-7 aucun repli déclenché ({len(html):,} octets)")

    def test_un_repli_de_rapport_reste_trop_petit_pour_passer(self):
        """⚠️ CE TEST VISAIT `export_pdf`, RETIRE AU LOT C1 (decision B).

        Sa preoccupation survit et elle est intacte : `export_pdf` GONFLAIT le
        repli d'echec en un PDF volumineux et parfaitement valide, ce qui
        defaisait le controle de taille de `_produire_livrable`. Le PDF n'etant
        plus genere, le repli reste une chaine courte -- et la garde le
        rattrape. C'est ce que ce test verifie desormais : la protection tient
        PAR CONSTRUCTION, non par un controle supplementaire.
        """
        import direction_non_vie.provisionnement.a7_provisionnement.agent as ag
        repli = MARQUEUR_ECHEC_RAPPORT + '<html><body><h1>Erreur</h1></body></html>'
        self.assertLess(
            len(repli), ag._TAILLE_MIN_LIVRABLE,
            "le repli d'echec doit rester sous le seuil qui le disqualifie")
        octets, erreur = ag._produire_livrable('html', lambda **k: repli)
        self.assertTrue(erreur, "un repli doit etre declare comme anomalie")
        self.assertIn('vide', erreur)
        print(f"    OK LIV-8 le repli d'echec ({len(repli)} car.) reste sous "
              f"le seuil ({ag._TAILLE_MIN_LIVRABLE}) et est declare : {erreur}")


# =============================================================================
#  2. COURBE DES TAUX — LA PÉREMPTION EST MESURÉE, PAS SUPPOSÉE
# =============================================================================

class T3_Peremption_Courbe(unittest.TestCase):
    """La courbe embarquée ne peut plus se déclarer sans reproche."""

    def test_les_trois_statuts_sont_atteignables(self):
        courbe = date.fromisoformat(DATE_COURBE)
        cas = [
            (courbe + timedelta(days=15),  'VERT'),
            (courbe + timedelta(days=int(MOIS_ALERTE_PEREMPTION * 31)), 'AMBRE'),
            (courbe + timedelta(days=int(MOIS_ROUGE_PEREMPTION * 31)),  'ROUGE'),
        ]
        for quand, attendu in cas:
            d = diagnostic_peremption(quand)
            self.assertEqual(d['statut'], attendu,
                             f"{quand} → {d['statut']} ({d['age_mois']} mois)")
        print("    OK LIV-9 péremption : VERT / AMBRE / ROUGE tous atteignables")

    def test_un_arrete_passe_est_juge_a_sa_date(self):
        """Un arrêté contemporain de la courbe ne doit pas la déclarer périmée."""
        d = diagnostic_peremption(DATE_COURBE)
        self.assertEqual(d['statut'], 'VERT')
        self.assertLess(d['age_mois'], 1.0)
        print(f"    OK LIV-10 arrêté du {DATE_COURBE} : VERT (0 mois)")

    def test_la_courbe_embarquee_signale_son_age_aujourdhui(self):
        """Le cœur du point : plus de 'erreur': None inconditionnel.

        ⚠️ CE TEST N'ASSERTAIT PLUS RIEN APRÈS LA BASCULE DU LOT R2, ET IL
        PASSAIT QUAND MÊME. Son unique assertion vivait sous
        `if mois >= MOIS_ALERTE_PEREMPTION` ; la courbe embarquée étant
        passée du 31/03/2025 au 31/07/2026, la branche n'était plus prise et
        le test devenait creux — vert, silencieux, et sans valeur. Il vérifie
        désormais LES DEUX SENS, donc il ne peut plus se vider tout seul.
        """
        c = get_courbe_embarquee()
        self.assertIn('peremption', c)
        mois = age_courbe_mois()
        if mois >= MOIS_ALERTE_PEREMPTION:
            self.assertIsNotNone(
                c['erreur'],
                "la courbe est périmée et ne le déclare pas — c'était le bug")
        else:
            self.assertIsNone(
                c['erreur'],
                "la courbe est fraîche et se déclare pourtant en défaut — "
                "un reproche sans motif use le signal")
        print(f"    OK LIV-11 courbe du {DATE_COURBE} : {mois:.0f} mois, "
              f"statut {c['peremption']['statut']}, erreur "
              f"{'absente' if c['erreur'] is None else 'présente'}")

    def test_la_peremption_atteint_le_resultat_et_les_alertes(self):
        r = AgentA7Provisionnement(verbose=False).run(
            source=np.array(GENINS, dtype=float), mode_declare='cumule',
            n_sim_bootstrap=300, seed=42, generer_graphiques=False)
        diag = (r['n4'].get('peremption_courbe')
                or (r['n4'].get('risk_margin_data') or {}).get('peremption_courbe'))
        self.assertIsNotNone(diag, "le diagnostic doit remonter jusqu'à N4")
        alertes = ' '.join(str(a) for a in r['n4'].get('alertes', []))
        # ⚠️ MÊME DÉFAUT QUE LIV-11, ET MÊME CORRECTIF. L'assertion vivait
        # sous `if diag['statut'] in ('AMBRE','ROUGE')` ; la courbe embarquée
        # étant devenue fraîche au lot R2, la branche n'était plus prise et le
        # test passait sans rien vérifier. Les deux sens sont désormais
        # exigés : une courbe en défaut doit alerter, une courbe à jour ne
        # doit PAS — une alerte sans motif use le signal aussi sûrement qu'une
        # alerte manquante.
        if diag['statut'] in ('AMBRE', 'ROUGE'):
            self.assertIn('courbe', alertes.lower(),
                          "la péremption doit apparaître dans les alertes N4")
        else:
            self.assertNotIn('périmée', alertes.lower(),
                             "la courbe est à jour et N4 alerte quand même")
        print(f"    OK LIV-12 N4 porte le diagnostic : {diag['statut']} "
              f"({diag['age_mois']} mois)")


# =============================================================================
#  3 & 4. LES DEUX AFFICHAGES FAUX DE L'APPLICATION
# =============================================================================

class T4_Affichages_Application(unittest.TestCase):

    def test_munich_expose_bien_ses_deux_reserves(self):
        """`be_munich` n'existe pas — l'app affichait « 0 € ✅ ».

        MUNICH EST RÉELLEMENT EXERCÉE ICI. Il y faut DEUX conditions, et rater
        l'une des deux rend le test creux : un triangle d'engagés, et une LoB où
        `munich_cl_disponible` est vrai — sur 'generique' la méthode est
        désactivée, et le premier jet de ce test ne prouvait donc rien.
        """
        from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
            _MCL_ENG_SAIN,
            _MCL_PAYE,
        )
        r = AgentA7Provisionnement(verbose=False).run(
            source=np.array(_MCL_PAYE, dtype=float), mode_declare='cumule',
            triangle_engage=np.array(_MCL_ENG_SAIN, dtype=float),
            lob='rc_auto_corporels',
            n_sim_bootstrap=300, seed=42, generer_graphiques=False)
        m = r['n3']['munich_cl']
        self.assertTrue(m.get('disponible'),
                        "le scénario doit RÉELLEMENT exercer Munich")
        self.assertNotIn('be_munich', m,
                         "si cette clé apparaît un jour, l'app doit la lire")
        for cle in ('be_munich_paye', 'be_munich_engage'):
            self.assertIn(cle, m, f"clé {cle} attendue par l'application")
            self.assertNotEqual(m[cle], 0.0,
                                f"{cle} nul : le scénario n'exerce rien")
        print(f"    OK LIV-13 Munich exercée : payé={m['be_munich_paye']:,.2f} "
              f"engagé={m['be_munich_engage']:,.2f} (l'app affichait 0 €)")

    def test_letiquette_grands_sinistres_suit_le_resultat(self):
        """Elle annonçait « BF auto » là où seul Chain Ladder était retenu."""
        f = etiquette_methode_grands
        code, lbl = f(['chain_ladder'])
        self.assertEqual(code, 'cl_separe')
        self.assertIn('Chain Ladder', lbl)
        self.assertNotIn('Bornhuetter', lbl)

        code, lbl = f(['bornhuetter_ferguson', 'chain_ladder'])
        self.assertEqual(code, 'bf_auto')
        self.assertIn('Bornhuetter-Ferguson', lbl)

        code, lbl = f([])
        self.assertEqual(code, 'manuel')
        print("    OK LIV-14 étiquette grands sinistres déduite du résultat")

    def test_un_triangle_sans_exposition_ne_produit_pas_de_bf(self):
        """La prémisse du correctif, vérifiée et non supposée."""
        r = AgentA7Provisionnement(verbose=False).run(
            source=np.array(GENINS, dtype=float), mode_declare='cumule',
            n_sim_bootstrap=300, seed=42, generer_graphiques=False)
        inc = r['n4']['methodes_incluses']
        self.assertNotIn('bornhuetter_ferguson', inc)
        code, _ = etiquette_methode_grands(inc)
        self.assertEqual(code, 'cl_separe',
                         "sans exposition, l'étiquette ne peut pas dire BF")
        print(f"    OK LIV-15 sans exposition : incluses={inc} → cl_separe")

    def test_plus_aucune_citation_du_guide_inexistante(self):
        """« §3.2 » ne correspond à aucune section du guide (numérotée en lettres)."""
        # `actuaria_app` n'est PAS importable dans la gate (streamlit absent) :
        # on lit son source comme un fichier. C'est le seul moyen de couvrir ce
        # fichier, et c'est aussi pourquoi il faut y laisser le moins de logique
        # possible.
        import io as _io
        from pathlib import Path
        racine = Path(__file__).resolve().parents[3]
        # ⚠️ CE BALAYAGE PORTAIT SUR DEUX FICHIERS, ET LE SECOND N'EXISTE
        # PLUS : `nv_triangle_builder.py` a été supprimé avec l'ancien chemin
        # de préparation des données. ⚠️ Il était ouvert PAR SON CHEMIN, pas
        # importé — sa disparition ne se serait donc pas vue à l'import mais
        # par un `FileNotFoundError` à l'exécution, et aucun relevé par AST
        # ne l'aurait signalée. C'est un relevé par CHAÎNE qui l'a trouvé.
        for chemin in (racine / 'actuaria_app.py',):
            src = _io.open(chemin, encoding='utf-8').read()
            self.assertNotIn(
                'Guide IA 2023 §3.', src,
                f"{chemin.name} cite une section inexistante du guide — les "
                f"sinistres graves sont traités en §4.c p36-37")
        print("    OK LIV-16 citations du guide corrigées (§4.c p36-37)")


# =============================================================================
#  5. LES DEUX LoB PRESQUE HOMONYMES
# =============================================================================

class T5_LoB_Distinguables(unittest.TestCase):
    """Elles partagent la LoB S2 et le σ, mais pas le régime de queue.

    Le renommage a été ÉCARTÉ après mesure du périmètre : `dommage_corporel_
    individuel` est une clé d'A10 (table σ et table de correspondance), figure
    dans le snapshot T7 du filet historique, et les deux noms sont des termes
    professionnels corrects. Renommer aurait désynchronisé A7 et A10 sans
    traiter le vrai risque — un choix fait sans voir la conséquence. Ce que ces
    tests verrouillent, c'est que la conséquence soit VISIBLE.
    """

    PAIRE = ('accidents_corporels', 'dommage_corporel_individuel')

    def test_elles_diffèrent_bien_sur_le_regime_de_queue(self):
        a, b = (get_lob_config(k) for k in self.PAIRE)
        self.assertNotEqual(a['risque_long'], b['risque_long'])
        # `lob_eiopa` (texte libre) a fusionné avec `sigma_eiopa` dans un champ
        # unique `segment_s2` au lot B10-a : les deux se contredisaient sur
        # trois LoB sur quinze. L'intention du test est inchangée, elle est
        # seulement exprimée sur le segment officiel plutôt que sur un libellé.
        self.assertEqual(a['segment_s2'], b['segment_s2'],
                         "même segment Solvabilité II — la différence est la queue")
        self.assertEqual(a['sigma_eiopa'], b['sigma_eiopa'])
        print(f"    OK LIV-17 même LoB S2 et même σ, risque_long "
              f"{a['risque_long']} contre {b['risque_long']}")

    def test_leurs_libelles_disent_lequel_est_long(self):
        for cle in self.PAIRE:
            cfg = get_lob_config(cle)
            libelle = cfg['label'].upper()
            attendu = 'LONGUE' if cfg['risque_long'] else 'COURTE'
            self.assertIn(attendu, libelle,
                          f"{cle} : le libellé doit dire son régime de queue")
        self.assertNotEqual(get_lob_config(self.PAIRE[0])['label'],
                            get_lob_config(self.PAIRE[1])['label'])
        print("    OK LIV-18 les libellés portent COURTE / LONGUE")

    def test_la_distinction_remonte_jusqua_lactuaire(self):
        """Une configuration que personne ne lit ne protège de rien."""
        for cle in self.PAIRE:
            r = AgentA7Provisionnement(verbose=False).run(
                source=np.array(GENINS, dtype=float), mode_declare='cumule',
                lob=cle, n_sim_bootstrap=300, seed=42, generer_graphiques=False)
            infos = ' '.join(str(i) for i in r['n2'].get('infos', []))
            self.assertIn('LoB retenue', infos,
                          f"{cle} : la distinction n'atteint pas les infos N2")
            self.assertIn('risque_long', infos)
        print("    OK LIV-19 la distinction apparaît dans les infos N2")

    def test_toute_lob_portant_distinction_la_voit_remonter(self):
        """Invariant général, pas un cas particulier codé en dur."""
        avec = [k for k, v in LOB_CONFIG.items() if v.get('distinction')]
        self.assertGreaterEqual(len(avec), 2)
        for cle in avec:
            self.assertIn(cle, LOB_CONFIG)
            self.assertTrue(LOB_CONFIG[cle]['distinction'].strip())
        print(f"    OK LIV-20 {len(avec)} LoB portent une distinction explicite")


# =============================================================================
#  LOT B (releve B2) — UN ARRETE NON COMMUNIQUE NE DEVIENT PAS LA DATE DU JOUR
# =============================================================================
#
#  ⚠️ LE FILET COUVRE LES TROIS LIVRABLES, PAS LE MODULE, ET C'EST LA LECON DU
#  LOT. A4a avait ferme ce defaut dans `n5_commentaire` et cru le lot complet ;
#  la correction n'avait atteint ni le HTML ni le Word, qui ecrivaient encore
#  `arr = arrete or dt` -- la date du jour sous une etiquette << Arrete >>.
#  Un filet borne au module l'aurait laisse revenir par un autre export.
#
#  ⚠️ ET LA TRACE PAR CONSOMMATEUR A CORRIGE MON PROPRE RELEVE. J'avais compte
#  l'Excel comme troisieme site du meme faux. Il ne l'est PAS : son `date_str`
#  est etiquete << Date rapport >> (la date de generation, pour laquelle
#  aujourd'hui est JUSTE quand l'arrete manque), pas << Arrete >>. Le variable
#  matchait le grep ; le consommateur dit autre chose. L'Excel porte un autre
#  defaut, plus doux -- il confond arrete et date de generation dans un seul
#  champ quand l'arrete EST fourni -- nomme a l'ardoise, hors de ce lot.
#  Le filet le VERIFIE quand meme : il s'assure que l'Excel ne presente jamais
#  la date du jour SOUS une etiquette d'arrete.
# =============================================================================

def _today_fr():
    # ⚠️ `datetime.now()` NAIF, ET C'EST DELIBERE (noqa DTZ005). Ce helper doit
    # reproduire A L'IDENTIQUE la date que la production calcule dans
    # `n5_rapport` (`datetime.now().strftime('%d/%m/%Y')`, sans fuseau) : la
    # comparaison << la date du jour n'apparait pas comme arrete >> n'a de sens
    # que si les deux chaines sont produites de la meme facon. Un tz les ferait
    # diverger aux frontieres de journee.
    # ⚠️ `noqa` MAL CIBLE AU LOT B, ET LE CONSTAT VAUT D'ETRE ECRIT : la
    # directive portait `DTZ005` seul, que `ruff` nu n'active pas -- il la
    # declarait donc INUTILE (RUF100) pendant que `scripts/proprete.py`, lui,
    # active DTZ005 et l'exigeait. Deux outils, deux configurations, une seule
    # ligne : il faut les deux codes pour satisfaire les deux.
    from datetime import datetime
    return datetime.now().strftime('%d/%m/%Y')  # noqa: DTZ005, RUF100


class T_Arrete_Les_Trois_Livrables_Ne_Fabriquent_Pas_La_Date(unittest.TestCase):
    """⚠️ TROIS LIVRABLES, UN INVARIANT : la date du jour ne se fait jamais
    passer pour l'arrete quand aucun arrete n'est communique."""

    @classmethod
    def setUpClass(cls):
        # ⚠️ UN RUN REEL, RE-EXPORTE AVEC L'ARRETE CHOISI. Bricoler un `n4`
        # partiel ferait lever l'Excel (`n4['reserve_p75']`, acces direct) sur
        # une cause etrangere au lot. On part des vrais objets et on ne fait
        # varier QUE l'arrete.
        with kaleido_declare(True), rendeur_substitue():
            r = AgentA7Provisionnement(verbose=False).run(
                source=np.array(GENINS, dtype=float), mode_declare='cumule',
                primes=_exposition(GENINS), n_sim_bootstrap=200, seed=42,
                generer_graphiques=False)
        cls.n1, cls.n2 = r['n1'], r['n2']
        cls.n3, cls.n4 = r['n3'], r['n4']
        cls.C = np.array(GENINS, dtype=float)

    def _formes_fabriquees(self):
        t = _today_fr()
        return (f'Arrêté au {t}', f'Arrêté {t}', f'Arrêté : {t}')

    def test_html_nomme_l_absence_au_lieu_de_la_combler(self):
        html = export_html(self.n1, self.n2, self.n3, self.n4,
                           arrete='', ref_client='ACME')
        self.assertIn(ARRETE_ABSENT, html)
        for forme in self._formes_fabriquees():
            self.assertNotIn(forme, html, f'HTML fabrique : {forme!r}')
        print('    OK LIV-B1 le HTML dit « non communiqué », pas la date du jour')

    def test_html_garde_la_vraie_date_quand_elle_existe(self):
        html = export_html(self.n1, self.n2, self.n3, self.n4,
                           arrete='30/06/2026', ref_client='ACME')
        # ⚠️ NE PAS SUR-CORRIGER : un arrete fourni doit s'afficher, avec « au ».
        self.assertIn('Arrêté au 30/06/2026', html)
        print('    OK LIV-B2 le HTML garde l arrete fourni, avec « au »')

    def test_word_nomme_l_absence(self):
        import io

        from docx import Document
        w = export_word(self.n1, self.n2, self.n3, self.n4,
                        arrete='', ref_client='ACME')
        cells = [c.text for t in Document(io.BytesIO(w)).tables
                 for r in t.rows for c in r.cells]
        self.assertIn('Arrêté', cells)                    # l'etiquette existe
        self.assertIn(ARRETE_ABSENT, cells)               # la valeur nomme l'absence
        self.assertNotIn(_today_fr(), cells, 'le Word porte la date du jour')
        print('    OK LIV-B3 le Word dit « non communiqué » dans sa table')

    def test_excel_n_etiquette_jamais_la_date_du_jour_en_arrete(self):
        # ⚠️ L'EXCEL N'EST PAS LE MEME FAUX (cf. l'en-tete). On verrouille qu'il
        # ne le DEVIENNE pas : la date du jour peut figurer, mais jamais sous
        # une etiquette d'arrete.
        import io

        from openpyxl import load_workbook
        xl = export_excel(self.C, self.n1, self.n2, self.n3, self.n4,
                          ref_client='ACME', arrete='')
        wb = load_workbook(io.BytesIO(xl))
        textes = [str(c.value) for ws in wb.worksheets
                  for row in ws.iter_rows() for c in row if c.value is not None]
        self.assertTrue(any('Date rapport' in t for t in textes),
                        "l'etiquette « Date rapport » a disparu")
        for forme in self._formes_fabriquees():
            self.assertFalse(any(forme in t for t in textes),
                             f'Excel etiquette la date du jour en arrete : {forme!r}')
        print('    OK LIV-B4 l Excel etiquette la date du jour « Date rapport »')


# =============================================================================
#  F-cal (releve B2) — UN TEST CALENDAIRE NON FAIT N'EST PAS UN << AUCUN EFFET >>
# =============================================================================
#
#  ⚠️ LE FAUX DE F3, TRANSPOSE AU CALENDAIRE. Le Word (document SIGNE) et le
#  prompt LLM deduisaient << Aucun effet calendaire significatif >> / << non
#  significatif >> du SEUL compteur d'effets, sans regarder si le GLM Poisson
#  age-cohorte avait pu s'ajuster. Sur un triangle ou il ne s'ajuste pas, ils
#  affirmaient une absence d'EFFET la ou il n'y avait qu'absence de TEST. Le
#  HTML distinguait deja les deux (FIX 2) -- encore une correction qui n'avait
#  pas atteint tous ses sites.
#
#  ⚠️ LE FILET PORTE SUR LES TROIS CONSOMMATEURS, PAS SUR LE MODULE, et le
#  remede est une SOURCE UNIQUE (`etat_calendaire`) plutot qu'une troisieme
#  copie de la logique -- c'est la duplication qui a cause la divergence.

#: Les quatre etats du test calendaire et un `bz` (glm_apc) qui les produit.
#: Au niveau du module, comme N4_GARDE : un dict mutable en attribut de classe
#: demanderait un ClassVar, et il n'appartient pas plus a une classe qu'a une
#: autre.
ETATS_CALENDAIRE = {
    'indisponible': {'glm_disponible': False},
    'aucun':        {'glm_disponible': True, 'n_effets_significatifs': 0,
                     'cal_significatif': False},
    'diffus':       {'glm_disponible': True, 'n_effets_significatifs': 0,
                     'cal_significatif': True},
    'present':      {'glm_disponible': True, 'n_effets_significatifs': 2},
}


class T_Calendaire_Non_Teste_N_Est_Pas_Aucun_Effet(unittest.TestCase):
    """⚠️ TROIS RENDUS (HTML, Word, prompt LLM), UNE SOURCE : un test absent
    ne se rend jamais comme une absence d'effet."""

    @classmethod
    def setUpClass(cls):
        with kaleido_declare(True), rendeur_substitue():
            cls.r = AgentA7Provisionnement(verbose=False).run(
                source=np.array(GENINS, dtype=float), mode_declare='cumule',
                primes=_exposition(GENINS), n_sim_bootstrap=200, seed=42,
                generer_graphiques=False)

    def _word_paras(self, bz):
        import io

        from docx import Document
        n3 = dict(self.r['n3']); n3['glm_apc'] = bz
        w = export_word(self.r['n1'], self.r['n2'], n3, self.r['n4'],
                        arrete='30/06/2026', ref_client='ACME')
        return ' '.join(p.text for p in Document(io.BytesIO(w)).paragraphs)

    def _html(self, bz):
        n3 = dict(self.r['n3']); n3['glm_apc'] = bz
        return export_html(self.r['n1'], self.r['n2'], n3, self.r['n4'],
                           arrete='30/06/2026', ref_client='ACME')

    def test_l_etat_a_quatre_valeurs_exactes(self):
        for attendu, bz in ETATS_CALENDAIRE.items():
            self.assertEqual(etat_calendaire(bz), attendu, f'etat {attendu}')
        print('    OK CAL-1 les quatre etats de etat_calendaire sont exacts')

    def test_word_ne_dit_pas_aucun_effet_quand_le_test_est_absent(self):
        joined = self._word_paras(ETATS_CALENDAIRE['indisponible'])
        self.assertNotIn('Aucun effet calendaire significatif', joined)
        self.assertIn('indisponible', joined.lower())
        print('    OK CAL-2 le Word dit indisponible, jamais aucun effet')

    def test_word_dit_bien_aucun_effet_quand_le_test_a_conclu(self):
        # ⚠️ NE PAS SUR-CORRIGER : un vrai << aucun effet >> reste vert.
        joined = self._word_paras(ETATS_CALENDAIRE['aucun'])
        self.assertIn('Aucun effet calendaire significatif', joined)
        print('    OK CAL-3 le Word dit aucun effet quand le test a conclu')

    def test_le_prompt_llm_ne_conclut_pas_sur_un_test_absent(self):
        ctx = _construire_contexte({}, {'glm_apc': ETATS_CALENDAIRE['indisponible']},
                                   {}, 'RC', '30/06')
        ligne = next(x for x in ctx.splitlines() if 'test calendaire' in x)
        self.assertIn('INDISPONIBLE', ligne)
        self.assertNotIn('non significatif', ligne)
        print('    OK CAL-4 le prompt LLM ne conclut pas sur un test absent')

    def test_html_distingue_toujours_indisponible_de_aucun(self):
        # ⚠️ NON-REGRESSION : le HTML distinguait deja, il doit rendre pareil.
        self.assertIn('Test calendaire indisponible',
                      self._html(ETATS_CALENDAIRE['indisponible']))
        self.assertIn('Aucun effet significatif',
                      self._html(ETATS_CALENDAIRE['aucun']))
        print('    OK CAL-5 le HTML distingue toujours indisponible et aucun')


# =============================================================================
#  AVIS-COULEUR (releve B2) — LA COULEUR SUIT LE STATUT, PAS UN MOT
# =============================================================================
#
#  ⚠️⚠️ LA COULEUR ETAIT TOUJOURS VERTE, PAS << verte sauf si >>. Les deux
#  renderers coloraient l'avis en rouge SI le mot << DEFAVORABLE >> figurait
#  dans `avis_actuariel` -- un mot que ce champ NE PRODUIT JAMAIS. Ses trois
#  valeurs (n4_best_estimate l. 1315-1322) commencent TOUTES par
#  << FAVORABLE >>. Le test etait donc toujours faux : l'avis d'un dossier
#  ROUGE (<< FAVORABLE SOUS RESERVE -- revisions requises avant bilan S2 >>)
#  s'affichait EN VERT dans le HTML ET dans le Word signe.
#
#  Le controle lisait le vocabulaire d'un AUTRE champ : c'est `jugement`
#  (l. 1919) qui ecrit << AVIS DEFAVORABLE >>.
#
#  ⚠️ LE REMEDE TRANSPOSE `_RAG_CELLULE` : match exact sur un vocabulaire FINI
#  (VERT / AMBRE / ROUGE), jamais une recherche de mot dans du texte libre.
#  Un statut inconnu tombe sur l'orange, jamais sur le vert.
#
#  ⚠️ ET CE LOT A REVELE UN BUG DU LOT C : la boucle des cartes d'hypotheses
#  ECRASAIT le parametre `statut` de `_build_blocks`. Invisible tant que rien
#  ne lisait `statut` en aval ; avis-couleur l'a fait pour la premiere fois.
#  Le verrou ci-dessous est STRUCTUREL -- aucun parametre reaffecte -- parce
#  qu'un test sur la seule couleur n'aurait pas empeche le prochain ecrasement.

#: Les couleurs attendues, par statut RAG. Cote Word ce sont les RGB de
#: `n5_rapport` (VR / AR / RgR), cote HTML les variables CSS.
_AVIS_ATTENDU = {
    'VERT':  ('var(--vert)',   '1E8449'),
    'AMBRE': ('var(--orange)', 'E67E22'),
    'ROUGE': ('var(--rouge)',  'C0392B'),
}


class T_Avis_Couleur_Suit_Le_Statut(unittest.TestCase):
    """⚠️ DEUX LIVRABLES, UN INVARIANT : la couleur de l'avis vient du statut
    RAG, jamais d'un mot cherche dans le texte."""

    @classmethod
    def setUpClass(cls):
        with kaleido_declare(True), rendeur_substitue():
            cls.r = AgentA7Provisionnement(verbose=False).run(
                source=np.array(GENINS, dtype=float), mode_declare='cumule',
                primes=_exposition(GENINS), n_sim_bootstrap=200, seed=42,
                generer_graphiques=False)

    def _n4(self, statut):
        n4 = dict(self.r['n4']); n4['statut'] = statut
        return n4

    def test_le_champ_avis_est_produit(self):
        # ⚠️ CE TEST CONSTATAIT << l'avis ne dit JAMAIS DEFAVORABLE >> -- la
        # mesure qui fondait le lot avis-couleur. Le lot du double vocabulaire
        # a rendu ce constat FAUX A DESSEIN : un dossier ROUGE dit desormais
        # << DEFAVORABLE >>. Le test a donc fait son office et cede la place ;
        # ce qui reste verifiable ici, c'est qu'un avis EXISTE. La coherence
        # avec `jugement` est verrouillee par la classe dediee plus bas.
        avis = str(self.r['n4'].get('avis_actuariel', ''))
        self.assertTrue(avis, "n4 ne produit aucun avis actuariel")
        print(f'    OK AVIS-1 un avis est produit : {avis[:44]}…')

    def test_html_colore_l_avis_selon_le_statut(self):
        import re
        # ⚠️ INDEX PLUTOT QUE DEBALLAGE : `for statut, (css, _rgb)` laissait une
        # locale assignee et jamais relue -- l'angle mort de ruff, que le
        # controle de proprete du depot attrape.
        for statut, attendu in _AVIS_ATTENDU.items():
            css = attendu[0]
            b = _build_blocks(self.r['n2'], self.r['n3'], self._n4(statut),
                              '', 'aucune', 'RC', 'X', '30/06', '18/08',
                              'A7-1', 'chain_ladder', statut, {})
            trouve = re.search(r'background:(var\(--[a-z]+\))', b['avis'])
            self.assertIsNotNone(trouve, f'{statut} : encadre d avis absent')
            self.assertEqual(trouve.group(1), css, f'statut {statut}')
        print('    OK AVIS-2 le HTML colore l avis selon VERT/AMBRE/ROUGE')

    def test_word_colore_l_avis_selon_le_statut(self):
        import io

        from docx import Document
        avis = str(self.r['n4'].get('avis_actuariel', '')).strip()[:20]
        for statut, attendu in _AVIS_ATTENDU.items():
            rgb = attendu[1]
            w = export_word(self.r['n1'], self.r['n2'], self.r['n3'],
                            self._n4(statut), arrete='30/06/2026',
                            ref_client='ACME')
            cols = [str(run.font.color.rgb)
                    for p in Document(io.BytesIO(w)).paragraphs
                    for run in p.runs if run.text.strip()[:20] == avis]
            self.assertTrue(cols, f'{statut} : avis introuvable dans le Word')
            self.assertEqual(cols[0], rgb, f'statut {statut}')
        print('    OK AVIS-3 le Word colore l avis selon VERT/AMBRE/ROUGE')

    def test_un_dossier_rouge_n_est_jamais_vert(self):
        # ⚠️ LE FAUX EXACT, ENONCE EN TOUTES LETTRES pour qu'une recherche
        # plein texte le retrouve s'il revenait.
        b = _build_blocks(self.r['n2'], self.r['n3'], self._n4('ROUGE'),
                          '', 'aucune', 'RC', 'X', '30/06', '18/08',
                          'A7-1', 'chain_ladder', 'ROUGE', {})
        self.assertNotIn('background:var(--vert)', b['avis'])
        print('    OK AVIS-4 un dossier ROUGE n affiche jamais un avis vert')

    def test_aucun_parametre_de_build_blocks_n_est_ecrase(self):
        # ⚠️ VERROU STRUCTUREL, PAS COSMETIQUE. Le lot C avait ecrase `statut`
        # dans la boucle des cartes d'hypotheses : tout code lisant `statut`
        # en aval recevait le verdict de la DERNIERE hypothese. Un test sur la
        # seule couleur n'aurait pas empeche le prochain ecrasement.
        import ast
        import inspect

        from direction_non_vie.provisionnement.a7_provisionnement import (
            n5_rapport as _n5r_mod,
        )
        fn = ast.parse(inspect.getsource(_n5r_mod._build_blocks)).body[0]
        params = {a.arg for a in fn.args.args}
        ecrases = sorted({
            t.id for n in ast.walk(fn) if isinstance(n, ast.Assign)
            for t in n.targets if isinstance(t, ast.Name) and t.id in params
        })
        self.assertEqual(ecrases, [],
                         f'parametres de _build_blocks reaffectes : {ecrases}')
        print('    OK AVIS-5 aucun parametre de _build_blocks n est ecrase')


# =============================================================================
#  N2/N3/N4 (releve narration) — LE NETTOYAGE N'EFFACE PLUS DU VRAI
# =============================================================================
#
#  ⚠️ CE DEFAUT N'AFFIRMAIT RIEN DE FAUX -- IL SUPPRIMAIT DU VRAI, en silence,
#  dans le commentaire actuariel remis au CAC. Trois pertes, toutes mesurees
#  AVANT correction :
#    N2 : une ligne de tableau markdown etait effacee AVEC ses chiffres.
#         Mesure : narration 81 -> 25 caracteres, << 7 746 000 EUR >> disparu.
#    N3 : six motifs de faux-titre s'appliquaient a TOUT le texte. Mesure :
#         << Ce rapport sera transmis a l'ACPR avec une reserve de 12 M EUR >>,
#         ecrite en §5, etait supprimee -- le chiffre avec.
#    N4 : le preambule etait TRONQUE en bloc, ouverture legitime comprise.
#
#  ⚠️ LE FILET PORTE SUR `_md_to_html`, PAS SEULEMENT SUR `_nettoyer_narration`.
#  La trace par consommateur l'impose : les deux services Sante-Prevoyance
#  (`sp_rapport_prevoyance`, `sp_rapport_sante`) importent ces fonctions mais
#  n'appellent QUE `_md_to_html` -- ils consomment donc la correction
#  INDIRECTEMENT. Un filet borne a la fonction interne ne prouverait rien pour
#  eux. TROIS livrables, d'ou la gate Vie+SP.

_NL = chr(10)


class T_Nettoyage_Narration_N_Efface_Plus_Du_Vrai(unittest.TestCase):
    """⚠️ CE QUI DOIT PARTIR PART, CE QUI DOIT RESTER RESTE."""

    TABLEAU = ('§1 — CONTEXTE' + _NL * 2 + '| Methode | Reserve |' + _NL
               + '|---|---|' + _NL + '| CL | 7 746 000 EUR |' + _NL * 2 + '§2')
    CORPS = ('§1 — CONTEXTE' + _NL * 2
             + "Ce rapport sera transmis a l ACPR avec une reserve de 12 M EUR."
             + _NL * 2 + '§2')
    OUVERTURE = ('Analyse du portefeuille auto, primes acquises 45 M EUR.'
                 + _NL * 2 + '§1 — CONTEXTE' + _NL + 'suite')
    FAUX_TITRE = ('# RAPPORT ACTUARIEL' + _NL + 'Document destine au Conseil'
                  + _NL + 'Arrete au 30/06/2026' + _NL * 2 + '§1 — CONTEXTE'
                  + _NL + 'corps')

    # ── N2 ───────────────────────────────────────────────────────────────────
    def test_n2_le_chiffre_d_un_tableau_survit(self):
        r = _nettoyer_narration(self.TABLEAU)
        self.assertIn('7 746 000', r, 'le Best Estimate est efface')
        self.assertNotIn('|', r, 'les pipes markdown restent')
        self.assertIn('CL · 7 746 000 EUR', r)
        print('    OK NAR-1 le contenu du tableau est converti, pas efface')

    def test_n2_la_separatrice_seule_disparait(self):
        # ⚠️ ELLE NE PORTE AUCUN CONTENU : la garder afficherait des tirets nus.
        self.assertNotIn('---', _nettoyer_narration(self.TABLEAU))
        print('    OK NAR-2 la separatrice |---|---| part, elle seule')

    # ── N3 ───────────────────────────────────────────────────────────────────
    def test_n3_une_phrase_du_corps_n_est_pas_filtree(self):
        self.assertIn('12 M EUR', _nettoyer_narration(self.CORPS),
                      'un motif de faux-titre mange une phrase du corps')
        print('    OK NAR-3 le corps du rapport n est plus filtre')

    # ── N4 ───────────────────────────────────────────────────────────────────
    def test_n4_une_ouverture_legitime_survit(self):
        self.assertIn('45 M EUR', _nettoyer_narration(self.OUVERTURE),
                      'le preambule est encore tronque en bloc')
        print('    OK NAR-4 une ouverture legitime avant le §1 survit')

    # ── NON-REGRESSION : ce que la fonction doit TOUJOURS retirer ────────────
    def test_le_faux_titre_part_toujours(self):
        r = _nettoyer_narration(self.FAUX_TITRE)
        self.assertNotIn('RAPPORT ACTUARIEL', r)
        self.assertNotIn('Document destine', r)
        self.assertIn('§1', r); self.assertIn('corps', r)
        print('    OK NAR-5 le faux-titre part, le corps reste')

    def test_un_texte_vide_reste_vide(self):
        self.assertEqual(_nettoyer_narration(''), '')
        print('    OK NAR-6 un texte vide reste vide')

    # ── LE CHEMIN DES TROIS LIVRABLES ───────────────────────────────────────
    def test_md_to_html_le_point_d_entree_reel_conserve_tout(self):
        # ⚠️ C'EST CE CHEMIN QUE LES DEUX SERVICES SP CONSOMMENT.
        html = _md_to_html(self.TABLEAU + _NL * 2
                           + "Ce rapport transmis a l ACPR avec 12 M EUR.")
        self.assertIn('7 746 000', html)
        self.assertIn('12 M EUR', html)
        self.assertNotIn('|', html)
        print('    OK NAR-7 _md_to_html conserve tout (chemin A7 + 2 SP)')


# =============================================================================
#  N1 — L'AVIS ET LE JUGEMENT NE SE CONTREDISENT JAMAIS
# =============================================================================
#
#  ⚠️⚠️ LA RAISON PREMIERE DE CE LOT N'EST PAS L'HARMONISATION : c'est que le
#  module IMPOSAIT AU MODELE UNE REGLE QU'IL VIOLAIT LUI-MEME. Le
#  `SYSTEM_PROMPT` d'A7 porte en regle 9 :
#
#      << INTERDIT : [...] FAVORABLE si H1 rejetee ET BT ROUGE. >>
#
#  et la premiere branche de l'avis (`n4_best_estimate`) est le MOT POUR MOT de
#  cet interdit -- elle ecrivait << FAVORABLE SOUS RESERVE >>.
#
#  ⚠️ ET LE DOCUMENT SE CONTREDISAIT A UNE PAGE D'ECART. Sur un ROUGE :
#      section 7 (narration en repli) : << AVIS DEFAVORABLE -- Ne pas inscrire
#                                         au bilan S2 sans validation formelle >>
#      section 8 (conclusion)         : << FAVORABLE SOUS RESERVE >>
#  Le mot rassurant etait dans la section de CONCLUSION.
#
#  ⚠️⚠️ CE VERROU PORTE SUR LA PROPRIETE, PAS SUR LES LIBELLES. Un test qui
#  comparerait trois chaines passerait le jour ou l'un des deux producteurs
#  changerait de vocabulaire sans l'autre -- exactement la divergence qu'on
#  ferme. Ce qui est verrouille : les deux verdicts ne se contredisent jamais.

#: Les trois etats RAG et le mot que l'avis doit porter. Vocabulaire du depot
#: (Sante-Prevoyance le produit deja dans ce meme champ).
_AVIS_PAR_STATUT = {
    'VERT':  'FAVORABLE',
    'AMBRE': 'AVEC RÉSERVES',
    'ROUGE': 'DÉFAVORABLE',
}


class T_Avis_Et_Jugement_Ne_Se_Contredisent_Pas(unittest.TestCase):
    """⚠️ UN DOSSIER QU'ON NE PEUT INSCRIRE A AUCUN BILAN N'EST PAS FAVORABLE,
    meme sous reserve."""

    @classmethod
    def setUpClass(cls):
        with kaleido_declare(True), rendeur_substitue():
            cls.r = AgentA7Provisionnement(verbose=False).run(
                source=np.array(GENINS, dtype=float), mode_declare='cumule',
                primes=_exposition(GENINS), n_sim_bootstrap=200, seed=42,
                generer_graphiques=False)

    def test_un_rouge_ne_dit_plus_favorable(self):
        # ⚠️ LE CAS QUE LA REGLE 9 DU PROMPT NOMME. On force le statut ROUGE et
        # on relit l'avis produit pour CE cas, sans toucher au calcul.
        from direction_non_vie.provisionnement.a7_provisionnement import (
            n4_best_estimate as _n4m,
        )
        src = inspect.getsource(_n4m)
        i = src.find("if statut == 'ROUGE' or (not h1_ok")
        self.assertGreater(i, 0, 'la branche ROUGE de l avis est introuvable')
        branche = src[i:i + 260]
        self.assertIn('DÉFAVORABLE', branche)
        self.assertNotIn('FAVORABLE SOUS RÉSERVE', branche)
        print('    OK N1-1 la branche ROUGE dit DEFAVORABLE')

    def test_les_trois_etats_portent_le_vocabulaire_du_depot(self):
        from direction_non_vie.provisionnement.a7_provisionnement import (
            n4_best_estimate as _n4m,
        )
        src = inspect.getsource(_n4m)
        for statut, mot in _AVIS_PAR_STATUT.items():
            self.assertIn(mot, src, f'{statut} : « {mot} » absent du module')
        print('    OK N1-2 FAVORABLE / AVEC RESERVES / DEFAVORABLE presents')

    def test_le_prompt_interdit_ce_que_le_code_n_ecrit_plus(self):
        # ⚠️ LE VERROU QUI COMPTE : la regle du prompt et le code doivent rester
        # d'accord. Si l'un des deux bouge, ce test le dit.
        from direction_non_vie.provisionnement.a7_provisionnement import (
            n5_rapport as _n5m,
        )
        self.assertIn('FAVORABLE si H1 rejetée ET BT ROUGE',
                      _n5m.SYSTEM_PROMPT,
                      "la regle 9 du prompt a change : revoir l'avis de n4")
        from direction_non_vie.provisionnement.a7_provisionnement import (
            n4_best_estimate as _n4m,
        )
        src = inspect.getsource(_n4m)
        i = src.find("if statut == 'ROUGE' or (not h1_ok")
        self.assertNotIn('FAVORABLE', src[i:i + 260].replace('DÉFAVORABLE', ''),
                         'le code ecrit encore FAVORABLE dans le cas interdit')
        print('    OK N1-3 le code respecte la regle 9 du SYSTEM_PROMPT')

    def test_avis_et_jugement_ne_se_contredisent_jamais(self):
        # ⚠️ LA PROPRIETE, PAS LES MOTS. Les deux champs sont produits par le
        # MEME statut : quand l'un dit << ne pas inscrire >>, l'autre ne peut
        # pas dire << favorable >>. On lit les deux sur le run reel.
        avis = str(self.r['n4'].get('avis_actuariel', ''))
        jug = str(self.r['n4'].get('jugement', ''))
        self.assertTrue(avis and jug, 'avis ou jugement absent du run')
        contredit = ('DÉFAVORABLE' in jug.upper()
                     and avis.upper().startswith('FAVORABLE'))
        self.assertFalse(contredit,
                         f'jugement dit DEFAVORABLE, avis dit : {avis[:60]}')
        print('    OK N1-4 avis et jugement ne se contredisent pas')


# =============================================================================
#  LE JUGEMENT DIT DE QUELLE GRANDEUR IL PARLE, ET NE DIRIGE PLUS VERS LE
#  MAUVAIS NOMBRE
# =============================================================================
#
#  ⚠️ CES TROIS DEFAUTS ONT ETE TROUVES PAR LA MESURE DU VERROU C2, AVANT MEME
#  QUE LE VERROU EXISTE : en comparant les nombres publies a la charge utile,
#  trois provisions sont ressorties orphelines. Aucun releve ne les avait vues.
#
#  P1/P2 -- `_documenter_jugement` publiait les percentiles de MACK SEUL sous
#  l'etiquette generique << Provision P75 / P90 / P99.5 >>, la MEME que le
#  rapport emploie pour les percentiles COMPOSES de N4. Deux grandeurs justes
#  chacune, sous un nom identique, dans le meme document. Ecart mesure :
#      P75   Mack 20 226 075   compose 17 660 196   -12,7 %
#      P90   Mack 21 892 882   compose 21 832 044    -0,3 %
#      P99.5 Mack 25 918 951   compose 34 310 605   +32,4 %  (8,4 M EUR)
#  ⚠️ AUCUNE VALEUR N'A CHANGE : le defaut etait l'ETIQUETTE. La vue Mack
#  native est diagnostique et le HTML la publie sciemment.
#
#  P3 -- LE PLUS GRAVE, ET SUR LE CHEMIN LE MOINS RELU. La section
#  << DECISION ET RECOMMANDATIONS >>, branche VERT SEULE, disait :
#      << Utiliser 21 892 882 EUR pour le calcul du SCR provisions. >>
#  Or `scr_prov = 3.0 * sigma_eiopa * be` -- AUCUN percentile n'y entre. Le
#  SCR reel vaut 4 894 197 EUR : un actuaire qui aurait suivi l'instruction
#  aurait obtenu un SCR 4,5x trop eleve. Et l'instruction n'avait pas d'objet,
#  le SCR etant deja calcule par ce meme module.

class T_Jugement_Nomme_Ses_Grandeurs(unittest.TestCase):
    """⚠️ DEUX GRANDEURS JUSTES SOUS UN MEME NOM RESTENT UN DEFAUT."""

    @classmethod
    def setUpClass(cls):
        with kaleido_declare(True), rendeur_substitue():
            cls.r = AgentA7Provisionnement(verbose=False).run(
                source=np.array(GENINS, dtype=float), mode_declare='cumule',
                primes=_exposition(GENINS), n_sim_bootstrap=200, seed=42,
                generer_graphiques=False)

    def _jugement(self, statut):
        """Le jugement pour un statut donne -- la branche VERT n'est atteignable
        que par cette voie, et c'est justement celle qu'on relit le moins."""
        from direction_non_vie.provisionnement.a7_provisionnement.n4_best_estimate import (
            BestEstimateS2,
        )
        n4 = self.r['n4']
        return BestEstimateS2()._documenter_jugement(
            {}, {}, n4.get('poids', {}), n4['best_estimate'], 2.0,
            self.r['n2'], self.r['n3'], statut, n4['scr'], {'label': 'RC'})

    # ── P1 / P2 ──────────────────────────────────────────────────────────────
    #
    # ⚠️⚠️ CES TROIS TESTS ONT ETE REECRITS PAR LE LOT PERCENTILES, ET LA RAISON
    # DOIT ETRE LUE AVANT DE LES CROIRE. Ils verrouillaient la decision du lot
    # `fcfb3d3` : le jugement publie MACK NATIF, et on le NOMME sans rien
    # deplacer. Cette decision a ete explicitement renversee -- Mack natif est
    # centre sur la reserve de Mack, pas sur le BE publie, donc ses percentiles
    # ne decrivent aucune distribution du Best Estimate que le meme bloc
    # annonce. Le jugement republie desormais `reserve_p*`, la meme grandeur
    # que les quatre livrables.
    #
    # ⚠️ ILS VERROUILLENT DESORMAIS UNE PROPRIETE, PLUS UN LIBELLE : non pas
    # << le jugement dit "Mack natif" >>, mais << le jugement dit ce que
    # `cle_percentiles` designe, et publie les nombres que le rapport publie >>.
    # Un libelle peut etre rearbitre ; la coherence entre deux documents, non.
    def test_les_percentiles_nomment_leur_source(self):
        n4 = self.r['n4']
        attendu = libelle_percentiles(n4)
        j = n4['jugement']
        for cle in ('P75', 'P90', 'P99.5'):
            ligne = next((x for x in j.splitlines()
                          if f'Provision {cle}' in x), None)
            self.assertIsNotNone(ligne, f'{cle} absent du jugement')
            self.assertIn(attendu, ligne,
                          f'{cle} ne dit pas de quelle grandeur il parle')
        # Et ce nom n'est pas une constante de test : il vient de l'arbitrage.
        self.assertIn(n4.get('cle_percentiles'),
                      (CLE_MACK, CLE_BOOT, CLE_COMPOSE))
        print(f'    OK JUG-1 les trois percentiles disent « {attendu} »')

    def test_le_jugement_nomme_sa_source_en_toutes_lettres(self):
        # ⚠️ NOMMER L'APPROCHE NE SUFFIT PAS : le lecteur doit savoir POURQUOI
        # c'est celle-la. La phrase de `source_percentiles` porte la raison --
        # et, quand Mack est retenu, la reserve sur l'hypothese d'independance
        # du compose. Elle doit arriver INTACTE dans le jugement.
        n4 = self.r['n4']
        source = n4.get('source_percentiles') or ''
        self.assertTrue(source.strip(), 'aucune source publiee')
        self.assertIn(source, n4['jugement'],
                      'le jugement ne porte pas la raison de son arbitrage')
        print('    OK JUG-2 le jugement porte la raison de son arbitrage')

    def test_le_jugement_publie_les_memes_nombres_que_le_rapport(self):
        # ⚠️ LE VERROU DU LOT, ET IL REMPLACE L'ANCIEN. On ne verifie plus que
        # << rien n'a bouge >> -- quelque chose a bouge, deliberement. On
        # verifie que le jugement et le rapport ne peuvent plus DIVERGER.
        n4 = self.r['n4']
        for cle, attendu in (('P75',   n4['reserve_p75']),
                             ('P90',   n4['reserve_p90']),
                             ('P99.5', n4['reserve_p99_5'])):
            ligne = next(x for x in n4['jugement'].splitlines()
                         if f'Provision {cle}' in x)
            self.assertIn(f'{attendu:,.0f}', ligne,
                          f'{cle} : le jugement ne publie pas le chiffre du rapport')
        # Et la contre-epreuve : Mack NATIF, l'ancienne source, a bien disparu
        # du bloc -- sinon les deux grandeurs cohabiteraient encore.
        mk = self.r['n3']['mack']
        bloc = [x for x in n4['jugement'].splitlines() if 'Provision P' in x]
        self.assertNotIn(f"{mk.get('reserve_p99_5') or 0:,.0f}", ' '.join(bloc),
                         'le P99.5 de Mack natif est encore publie')
        print('    OK JUG-3 jugement et rapport publient les memes nombres')

    # ── P3 ───────────────────────────────────────────────────────────────────
    def test_le_vert_ne_dirige_plus_vers_un_percentile_pour_le_scr(self):
        j = self._jugement('VERT')
        self.assertNotIn('pour le calcul du SCR provisions', j,
                         "l'instruction fausse est encore la")
        print('    OK JUG-4 l instruction « utiliser X pour le SCR » a disparu')

    def test_le_vert_publie_le_scr_reellement_calcule(self):
        j = self._jugement('VERT')
        scr = self.r['n4']['scr'].get('scr_provisions') or 0
        self.assertIn(f'{scr:,.0f}', j, 'le SCR publie n est pas celui de n4')
        self.assertIn('Art. 115', j)
        # ⚠️ ET SURTOUT : le P90 ne doit PLUS figurer comme cible du SCR.
        p90 = self.r['n3']['mack'].get('reserve_p90') or 0
        ligne = next(x for x in j.splitlines() if 'SCR provisions' in x)
        self.assertNotIn(f'{p90:,.0f}', ligne,
                         'la ligne SCR porte encore le P90')
        print('    OK JUG-5 le VERT publie le SCR reel, pas un percentile')


# =============================================================================
#  LOT PERCENTILES — LA REFERENCE SUIT L'ARBITRAGE, ET LES 4 FORMATS SUIVENT
# =============================================================================
#
#  ⚠️ LE COMPOSE NE MESURAIT PAS L'INCERTITUDE, IL MESURAIT LE DESACCORD ENTRE
#  METHODES. sigma_modele est l'ecart-type des reserves des methodes retenues :
#  79 % de la variance sur GenIns (methodes divergentes), 18 % sur RAA (elles
#  convergent). Et son hypothese d'independance est FAUSSE -- les methodes
#  partagent `pct_dev`, BF recoit `ultimates_cl`. Sous covariance positive la
#  somme quadratique SOUS-ESTIME : le compose n'est pas prudent, il est
#  INDETERMINE.
#
#  ⚠️⚠️ CE FILET VERROUILLE DES PROPRIETES, JAMAIS DES LIBELLES. Un libelle
#  peut etre rearbitre demain -- ce lot en rearbitre trois. Ce qui ne doit
#  jamais changer : quelle grandeur `reserve_p*` porte, que le sigma publie la
#  REGENERE, que la bascule reste conditionnelle a CLM-H3, et que les quatre
#  livrables nomment tous la meme approche.


class T_Percentiles_La_Reference_Suit_L_Arbitrage(unittest.TestCase):
    """⚠️ LA BASCULE EST CONDITIONNELLE, ET C'EST LE POINT LE PLUS IMPORTANT."""

    @classmethod
    def setUpClass(cls):
        cls.C = np.array(GENINS, dtype=float)
        with kaleido_declare(True), rendeur_substitue():
            cls.r = AgentA7Provisionnement(verbose=False).run(
                source=cls.C, mode_declare='cumule',
                primes=_exposition(GENINS), n_sim_bootstrap=200, seed=42,
                generer_graphiques=False)
        cls.n4 = cls.r['n4']

    def _calculer(self, mack_ok, boot_ok):
        """N4 recalcule avec les DEUX portes d'hypothese forcees.

        C'est la seule facon d'atteindre les branches de repli : sur les
        triangles de reference, CLM-H3 passe toujours."""
        from direction_non_vie.provisionnement.a7_provisionnement.n4_best_estimate import (
            BestEstimateS2,
        )
        n2 = self.r['n2']
        n2b = {
            **n2,
            'clm': {**n2.get('clm', {}),
                    'percentiles_mack_publiables': mack_ok},
            'bootstrap_hyp': {**n2.get('bootstrap_hyp', {}),
                              'percentiles_publiables': boot_ok},
        }
        return BestEstimateS2().calculer(n2b, self.r['n3'], self.C)

    @staticmethod
    def _log_normale(be, sig, z):
        """QIS5 TP.5.26, REECRITE ICI. Le filet ne doit pas emprunter la
        fonction qu'il verifie -- sinon une erreur commune passerait deux
        fois inapercue."""
        cv = sig / be
        s2 = float(np.log(1.0 + cv ** 2))
        return float(np.exp(np.log(be) - s2 / 2.0 + z * np.sqrt(s2)))

    # ── PCT-1 ────────────────────────────────────────────────────────────────
    def test_la_reference_est_mack_recentre_quand_clm_h3_valide(self):
        n4 = self.n4
        self.assertTrue(self.r['n2'].get('clm', {})
                        .get('percentiles_mack_publiables', True),
                        'ce triangle ne valide pas CLM-H3 : test sans objet')
        self.assertEqual(n4['cle_percentiles'], CLE_MACK)
        for p in ('p75', 'p90', 'p99_5'):
            self.assertEqual(n4[f'reserve_{p}'], n4[f'reserve_{p}_mack'],
                             f'{p} publie n est pas le Mack recentre')
        print('    OK PCT-1 la reference publiee est Mack recentre')

    # ── PCT-2 ────────────────────────────────────────────────────────────────
    def test_le_sigma_publie_regenere_les_percentiles_publies(self):
        # ⚠️ LA PROPRIETE QUI REND LE CHIFFRE OPPOSABLE : un tiers doit
        # pouvoir refaire le calcul avec les seuls nombres publies.
        n4 = self.n4
        be, sig = n4['best_estimate'], n4['sigma_percentiles']
        for p, z in (('p75', 0.6745), ('p90', 1.2816), ('p99_5', 2.5758)):
            self.assertAlmostEqual(
                self._log_normale(be, sig, z), n4[f'reserve_{p}'], delta=1.0,
                msg=f'{p} n est pas regenerable depuis (BE, sigma_percentiles)')
        print('    OK PCT-2 (BE, sigma_percentiles) regenerent les 3 publies')

    # ── PCT-3 ────────────────────────────────────────────────────────────────
    def test_le_compose_reste_publie_et_differe_de_la_reference(self):
        # Une colonne comparative qui vaut la reference ne compare rien.
        n4 = self.n4
        for p in ('p75', 'p90', 'p99_5'):
            self.assertIsNotNone(n4.get(f'reserve_{p}_compose'),
                                 f'{p} compose retire du livrable')
        self.assertNotEqual(n4['reserve_p99_5'], n4['reserve_p99_5_compose'],
                            'le compose vaut la reference : rien n a bascule')
        # Et le sens mesure : retirer sigma_modele RETRECIT la queue.
        self.assertLess(n4['reserve_p99_5'], n4['reserve_p99_5_compose'])
        print('    OK PCT-3 le compose reste publie, et il differe')

    # ── PCT-4 : LA BASCULE EST CONDITIONNELLE ────────────────────────────────
    def test_clm_h3_rejetee_retire_mack_de_la_reference(self):
        # ⚠️⚠️ LE TEST LE PLUS IMPORTANT DU LOT. Si CLM-H3 est NON VALIDEE,
        # sigma_Mack ne mesure plus l'erreur de prediction : en faire la
        # reference publierait sigma_Mack exactement la ou ce module a etabli
        # qu'il ne vaut rien. La bascule DOIT rendre la main.
        r = self._calculer(mack_ok=False, boot_ok=True)
        self.assertNotEqual(r['cle_percentiles'], CLE_MACK,
                            'Mack reste la reference alors que CLM-H3 le rejette')
        self.assertEqual(r['cle_percentiles'], CLE_BOOT)
        for p in ('p75', 'p90', 'p99_5'):
            self.assertEqual(r[f'reserve_{p}'], r[f'reserve_{p}_boot'],
                             f'{p} ne suit pas le relais Bootstrap')
        print('    OK PCT-4 CLM-H3 rejetee : la reference passe au Bootstrap')

    def test_sans_relais_bootstrap_le_repli_est_le_compose_signale(self):
        r = self._calculer(mack_ok=False, boot_ok=False)
        self.assertEqual(r['cle_percentiles'], CLE_COMPOSE)
        for p in ('p75', 'p90', 'p99_5'):
            self.assertEqual(r[f'reserve_{p}'], r[f'reserve_{p}_compose'])
        # Et le repli se DIT : une case juste mais contestee doit le declarer.
        self.assertIn('CONTESTÉE', r['source_percentiles'])
        print('    OK PCT-5 sans relais : compose, et le livrable le signale')

    # ── PCT-6 : l'hypothese d'independance est declaree NON VERIFIEE ─────────
    def test_l_hypothese_d_independance_du_compose_est_declaree(self):
        # ⚠️ LA RESERVE DE FOND VIT DANS LE LIVRABLE, PAS SEULEMENT EN
        # COMMENTAIRE : le compose suppose sigma_Mack et sigma_modele
        # independants, et rien ne le verifie.
        src = self.n4['source_percentiles']
        self.assertIn("indépendance", src)
        self.assertIn("PAS vérifiée", src)
        print('    OK PCT-6 l hypothese d independance est declaree non verifiee')

    # ── PCT-7 : une seule approche marquee « retenue », la bonne ─────────────
    def test_une_seule_approche_est_marquee_retenue(self):
        n4 = self.n4
        marques = [c for c in (CLE_MACK, CLE_BOOT, CLE_COMPOSE)
                   if marque_retenue(n4, c, 'X') != 'X']
        self.assertEqual(marques, [n4['cle_percentiles']],
                         'la marque « retenue » ne suit pas l arbitrage')
        # Mack natif ne peut JAMAIS l'etre : il est centre ailleurs.
        self.assertEqual(marque_retenue(n4, '', 'Mack natif'), 'Mack natif')
        print('    OK PCT-7 une seule approche marquee, celle qui est publiee')

    # ── PCT-8 : les quatre livrables nomment la MEME approche ────────────────
    def test_les_quatre_livrables_nomment_la_meme_approche(self):
        # ⚠️ LE DEFAUT QUE LE LOT FERME : chaque format ecrivait « composé » en
        # dur. Le nom vient desormais d'une source unique -- on verifie qu'il
        # ARRIVE dans les trois formats textuels, et qu'aucun ne contredit.
        n4, n3, n2, n1 = (self.r['n4'], self.r['n3'],
                          self.r['n2'], self.r['n1'])
        appr = libelle_percentiles(n4)
        self.assertEqual(appr, LIBELLE_APPROCHE[CLE_MACK])
        html = export_html(n1, n2, n3, n4, {})
        self.assertIn(appr, html, 'le HTML ne nomme pas l approche publiee')
        # ⚠️ CONTRE-EPREUVE : plus aucune etiquette « (composé) » collee a un
        # percentile publie. On cherche la FORME EXACTE qui etait en dur.
        for forme in ('P99,5 (composé)', 'P90 (composé)', 'P75 (composé)'):
            self.assertNotIn(forme, html,
                             f'etiquette figee encore presente : {forme}')
        comm = n4.get('jugement') or ''
        self.assertIn(appr, comm)
        print(f'    OK PCT-8 les livrables nomment tous « {appr} »')

    # ── PCT-9 : le chemin LLT ne ressuscite pas le compose ───────────────────
    def test_le_recentrage_llt_repart_du_sigma_de_la_bascule(self):
        # ⚠️ LE SECOND PRODUCTEUR. `agent.py` recalcule `reserve_p*` apres le
        # LLT ; il lisait `sigma_total_compose` EN DUR. Le dossier divergeait
        # donc selon qu'un grand sinistre etait detecte ou non. On verifie sur
        # le CODE que la cle de la bascule est bien celle qui est lue -- un
        # test de valeur ne le verrait pas tant qu'aucun LLT ne se declenche.
        import direction_non_vie.provisionnement.a7_provisionnement.agent as ag
        src = inspect.getsource(ag)
        # On isole L'EXPRESSION elle-meme, pas une fenetre de caracteres : un
        # commentaire un peu plus long deplacerait une fenetre, jamais ceci.
        i = src.index('_sig_pct = float(')
        expr = src[i:src.index('0.0)', i) + 4]
        self.assertIn("n4.get('sigma_percentiles')", expr,
                      'le recentrage LLT ne lit pas le sigma de la bascule')
        self.assertLess(expr.index("sigma_percentiles"),
                        expr.index("sigma_total_compose"),
                        'le compose est lu AVANT le sigma de la bascule')
        print('    OK PCT-9 le recentrage LLT repart du sigma de la bascule')

    # ── PCT-10 : rien d'autre n'a bouge ──────────────────────────────────────
    def test_ni_le_be_ni_le_scr_ni_la_rm_ne_dependent_des_percentiles(self):
        # ⚠️ MESURE, PAS RAISONNEMENT : on rejoue les trois arbitrages et on
        # verifie que les agregats du bilan sont RIGOUREUSEMENT identiques.
        ref = self.n4
        for mack_ok, boot_ok in ((False, True), (False, False)):
            r = self._calculer(mack_ok, boot_ok)
            for cle in ('best_estimate', 'risk_margin',
                        'provisions_techniques_s2', 'cv_inter_methodes'):
                self.assertEqual(r[cle], ref[cle],
                                 f'{cle} depend de l arbitrage des percentiles')
            self.assertEqual(r['scr']['scr_provisions'],
                             ref['scr']['scr_provisions'])
        print('    OK PCT-10 BE / SCR / RM / PT invariants aux 3 arbitrages')


# =============================================================================
#  VERROU C2 — AUCUN NOMBRE PUBLIE QUI NE SOIT DANS LA CHARGE UTILE
# =============================================================================
#
#  ⚠️⚠️ CE VERROU PROUVE LA PROVENANCE, JAMAIS LA JUSTESSE -- et c'est ecrit
#  dans le module, pas seulement ici. Un modele qui INVERSERAIT deux valeurs
#  justes passerait : les deux sont dans la charge utile.
#
#  ⚠️ IL A TROUVE TROIS DEFAUTS AVANT D'EXISTER. Sa mesure preparatoire a fait
#  ressortir les trois provisions du jugement (`fcfb3d3`) -- un ecart de
#  8,4 M EUR sur le P99.5 -- que SIX releves successifs n'avaient pas vus.
#
#  ⚠️ ET LE DETECTEUR EST TESTE POUR LUI-MEME, AVANT D'ETRE CRU. Une premiere
#  version ne reconnaissait pas la virgule comme separateur de milliers : elle
#  scindait << 8,057,830 >> en trois nombres, tous orphelins, et annoncait 42 %
#  de faux positifs. La narration n'inventait rien -- le detecteur fabriquait
#  des orphelins. Un verrou ne vaut pas mieux que son instrument.

#: Formes mesurees dans la narration et la charge utile reelles. Au niveau du
#: module : un attribut de classe mutable demanderait un `ClassVar`, et ces
#: formes n'appartiennent pas plus a une classe qu'a une autre.
_FORMES_MESUREES = {
    '8,057,830':   '8057830',      # virgule -- celle qui m'avait trompe
    '1.234.567':   '1234567',      # point separateur de milliers
    '4 894 197':   '4894197',      # espace fine insecable
    '11.0':        '11',           # decimale nulle == entier
    '17,3':        '17.3',         # decimale a la francaise
    '0.5':         '0.5',
    '7':           '7',
}


class T_Detecteur_De_Nombres(unittest.TestCase):
    """⚠️ LE DETECTEUR AVANT LE VERROU. S'il se trompe, tout le reste ment."""

    def test_les_formes_mesurees_sont_reconnues(self):
        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
            _cle_nombre,
            nombres_publies,
        )
        for brut, attendu in _FORMES_MESUREES.items():
            trouves = nombres_publies(brut)
            self.assertEqual(trouves, [brut], f'{brut!r} mal decoupe')
            self.assertEqual(_cle_nombre(brut), attendu, f'{brut!r} mal normalise')
        print(f'    OK C2-1 les {len(_FORMES_MESUREES)} formes mesurees '
              f'sont reconnues')

    def test_une_decimale_non_nulle_ne_s_apparie_pas_a_l_entier(self):
        # ⚠️ SANS CETTE EPREUVE, LA NORMALISATION POURRAIT TOUT APLATIR et le
        # verrou laisserait passer n'importe quel arrondi.
        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
            _cle_nombre,
        )
        self.assertEqual(_cle_nombre('11.0'), _cle_nombre('11'))
        self.assertNotEqual(_cle_nombre('11.3'), _cle_nombre('11'))
        self.assertNotEqual(_cle_nombre('17'), _cle_nombre('17,3'))
        print('    OK C2-2 un arrondi ne s apparie pas a sa valeur pleine')

    def test_la_zone_franche_ne_couvre_que_des_references(self):
        # ⚠️ LA REGLE DE SELASSE : aucun seuil numerique n'y entre.
        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
            nombres_publies,
        )
        for ref in ('§5 — CONTEXTE', 'Mack 1993', 'Mack (1993)', 'BFCC-H4',
                    'H2', 'Art. 115', 'QIS5 TP.5.26', '2015/35'):
            self.assertEqual(nombres_publies(ref), [],
                             f'{ref!r} devrait etre en zone franche')
        # ⚠️ ET CE QUI N'EST PAS UNE REFERENCE DOIT RESTER CONTROLE.
        for grandeur in ('5 annees', '3 observations', 'CV de 11.0 %'):
            self.assertTrue(nombres_publies(grandeur),
                            f'{grandeur!r} ne doit PAS etre exempte')
        print('    OK C2-3 zone franche = references seules, aucun seuil')


class T_Verrou_Charge_Utile(unittest.TestCase):
    """⚠️ UN NOMBRE PUBLIE QUI N'EST PAS DANS LA CHARGE EST SOIT INVENTE, SOIT
    PERIME."""

    @classmethod
    def setUpClass(cls):
        with kaleido_declare(True), rendeur_substitue():
            cls.r = AgentA7Provisionnement(verbose=False).run(
                source=np.array(GENINS, dtype=float), mode_declare='cumule',
                primes=_exposition(GENINS), n_sim_bootstrap=200, seed=42,
                generer_graphiques=False)

    def test_un_nombre_invente_est_detecte(self):
        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
            orphelins_narration,
        )
        charge = 'BEST ESTIMATE : 14 830 899 € | CV=2.0 %'
        propre = 'Le Best Estimate ressort a 14 830 899 € (CV 2.0 %).'
        self.assertEqual(orphelins_narration(propre, charge), [])
        invente = 'Le Best Estimate ressort a 99 999 999 € (CV 2.0 %).'
        self.assertEqual(orphelins_narration(invente, charge), ['99 999 999'])
        print('    OK C2-4 un nombre absent de la charge est signale')

    def test_le_taux_reste_praticable_sur_la_narration_reelle(self):
        # ⚠️ MESURE SUR LE DETERMINISTE, PAS SUR LE LLM -- aucune cle API
        # disponible, aucune narration Claude archivee. Ordre de grandeur.
        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
            _construire_contexte,
            nombres_publies,
            orphelins_narration,
        )
        n2, n3, n4 = self.r['n2'], self.r['n3'], self.r['n4']
        texte = n4.get('jugement', '')
        charge = _construire_contexte(n2, n3, n4, 'RC', '30/06/2026')
        pub = nombres_publies(texte)
        orph = orphelins_narration(texte, charge)
        taux = 100 * len(orph) / max(len(pub), 1)
        self.assertGreater(len(pub), 20, 'narration trop pauvre pour mesurer')
        # ⚠️ SEUIL LARGE ET ASSUME : il verrouille que le detecteur ne se
        # DEREGLE pas (retour a 42 %), pas que la narration soit parfaite.
        self.assertLess(taux, 30,
                        f'taux d orphelins {taux:.0f} % -- detecteur deregle ?')
        print(f'    OK C2-5 taux mesure {taux:.0f} % '
              f'({len(orph)}/{len(pub)}) sur le deterministe')

    def test_le_verrou_ne_juge_pas_la_justesse(self):
        # ⚠️ LA RESERVE DE FOND, EPROUVEE PLUTOT QUE SEULEMENT ECRITE. Deux
        # valeurs justes ECHANGEES passent le verrou : c'est sa limite, et
        # elle doit etre demontree, pas promise.
        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
            orphelins_narration,
        )
        charge = 'BE : 14 830 899 € | SCR : 4 894 197 €'
        inverse = 'Le BE vaut 4 894 197 € et le SCR 14 830 899 €.'
        self.assertEqual(orphelins_narration(inverse, charge), [],
                         'le verrou pretendrait juger la justesse')
        print('    OK C2-6 le verrou prouve la provenance, PAS la justesse')


if __name__ == '__main__':
    unittest.main(verbosity=1)
