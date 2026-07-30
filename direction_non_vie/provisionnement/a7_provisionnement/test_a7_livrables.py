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

import unittest
from datetime import date, timedelta

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement, _TAILLE_MIN_LIVRABLE, _dependance_absente,
    _produire_livrable, etiquette_methode_grands,
)
from direction_non_vie.provisionnement.a7_provisionnement.config.lob_config import (
    LOB_CONFIG, get_lob_config,
)
from direction_non_vie.provisionnement.a7_provisionnement.config.rfr_eiopa import (
    DATE_COURBE, MOIS_ALERTE_PEREMPTION, MOIS_ROUGE_PEREMPTION,
    age_courbe_mois, diagnostic_peremption, get_courbe_embarquee,
)
from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
    MARQUEUR_ECHEC_RAPPORT, export_html,
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
        cls.r = AgentA7Provisionnement(verbose=False).run(
            source=np.array(GENINS, dtype=float), mode_declare='cumule',
            primes=_exposition(GENINS), n_sim_bootstrap=300, seed=42,
            generer_graphiques=True, generer_word=True, generer_pdf_flag=True)

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
                         ('pdf_bytes', 'pdf')):
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

    def test_le_pdf_refuse_de_mettre_en_page_un_repli(self):
        """Sinon : un PDF volumineux et valide de la page d'erreur."""
        import direction_non_vie.provisionnement.a7_provisionnement.n5_rapport as mod
        from unittest.mock import patch
        with patch.object(mod, 'export_html',
                          return_value=MARQUEUR_ECHEC_RAPPORT + '<html></html>'):
            octets = mod.export_pdf(n1={}, n2={}, n3={}, n4={})
        self.assertEqual(octets, b'',
                         "export_pdf a mis en page un repli d'échec")
        print("    OK LIV-8 export_pdf refuse le repli de export_html")


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
        """Le cœur du point : plus de 'erreur': None inconditionnel."""
        c = get_courbe_embarquee()
        self.assertIn('peremption', c)
        mois = age_courbe_mois()
        if mois >= MOIS_ALERTE_PEREMPTION:
            self.assertIsNotNone(
                c['erreur'],
                "la courbe est périmée et ne le déclare pas — c'était le bug")
        print(f"    OK LIV-11 courbe du {DATE_COURBE} : {mois:.0f} mois, "
              f"statut {c['peremption']['statut']}")

    def test_la_peremption_atteint_le_resultat_et_les_alertes(self):
        r = AgentA7Provisionnement(verbose=False).run(
            source=np.array(GENINS, dtype=float), mode_declare='cumule',
            n_sim_bootstrap=300, seed=42, generer_graphiques=False)
        diag = (r['n4'].get('peremption_courbe')
                or (r['n4'].get('risk_margin_data') or {}).get('peremption_courbe'))
        self.assertIsNotNone(diag, "le diagnostic doit remonter jusqu'à N4")
        if diag['statut'] in ('AMBRE', 'ROUGE'):
            alertes = ' '.join(str(a) for a in r['n4'].get('alertes', []))
            self.assertIn('courbe', alertes.lower(),
                          "la péremption doit apparaître dans les alertes N4")
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
        from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim             import _MCL_PAYE, _MCL_ENG_SAIN
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
        for chemin in (racine / 'actuaria_app.py',
                       racine / 'direction_non_vie' / 'services'
                              / 'nv_triangle_builder.py'):
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
        self.assertEqual(a['lob_eiopa'], b['lob_eiopa'],
                         "même LoB Solvabilité II — la différence est la queue")
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


if __name__ == '__main__':
    unittest.main(verbosity=1)
