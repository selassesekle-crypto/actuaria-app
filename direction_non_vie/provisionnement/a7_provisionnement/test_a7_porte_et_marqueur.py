# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — CE QUI SORT PASSE PAR LA PORTE, ET UNE PAGE D'ERREUR SE DECLARE
=============================================================================

 Quatre constats, une meme forme : un mecanisme de securite EXISTE, il est
 correct, et quelque chose passe A COTE de lui.

 · La gouvernance des hypotheses ferme la publication des percentiles quand
   BOOT-H3 est NON VALIDEE : elle pose `percentiles_publiables = False` et
   `reserve_p90_boot` ressort a None. Le garde-fou mord. Mais le bloc
   « Diagnostic — decomposition de l'incertitude » du commentaire lisait
   `n3['bootstrap']['p90']` EN DIRECT. Le meme document ecrivait donc deux
   fois « les percentiles Bootstrap (P75/P90/P99.5) ne sont pas publies »
   PUIS les publiait quelques milliers de caracteres plus loin. Mesure :
   P90 = 3 129 736 EUR imprime porte fermee. Le P75, lui, etait bien absent
   — ce qui rendait la contradiction plus difficile a voir, pas moins reelle.

 · `MARQUEUR_ECHEC_RAPPORT` existe pour distinguer une page d'erreur d'un
   rapport, « ce que ni la taille ni la validite du HTML ne permettent ».
   Zero lecteur de production : seuls les tests le lisaient. Le seul filet
   etait un seuil de 512 octets, que le repli franchit des que le message
   d'exception depasse 439 caracteres.

 · Le controle `references_hors_liste` a ete construit APRES qu'une citation
   fausse eut ete payee a vingt endroits. Son assiette etait la NARRATION du
   modele ; le pied de page DETERMINISTE citait « Art. 77 et 105 », que ce
   meme controle refuse.

 · BOOT-H3 levait `ValueError: lam value too large` quand la sur-dispersion
   tend vers zero. L'exception etait rattrapee et les quatre hypotheses du
   Bootstrap sortaient NON TESTABLE — une degradation honnete, mais obtenue
   par une PANNE.

 ⚠️ CHAQUE CLASSE PORTE SA CONTRE-EPREUVE : une porte OUVERTE doit laisser
 passer, un VRAI rapport ne doit pas etre pris pour un repli, et un triangle
 bruite doit encore rendre un verdict.
=============================================================================
"""

import unittest

import numpy as np

import direction_non_vie.provisionnement.a7_provisionnement.agent as AG
from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement)
from direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses_bootstrap import (
    nulle_parametrique)
from direction_non_vie.provisionnement.a7_provisionnement.n3.chain_ladder import (
    calculer_facteurs)
from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
    MARQUEUR_ECHEC_RAPPORT, references_hors_liste)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    RAA)


def _formes(v):
    """Les trois espaces qu'un montant peut porter dans un document."""
    return [('%s' % format(round(v), ',')).replace(',', c)
            for c in (' ', ' ', ' ', ',')]


def _tri_bruite(sigma, graine=9, n=9):
    rng = np.random.default_rng(graine)
    inc = np.array([0.85 ** j for j in range(n)])
    C = np.zeros((n, n))
    for i in range(n):
        acc = 0.0
        for j in range(n):
            if i + j < n:
                acc += 100000.0 * (1 + 0.04 * i) * inc[j] * \
                    max(0.05, 1.0 + rng.normal(0, sigma))
                C[i, j] = acc
    return C


def _run(C, **kw):
    d = dict(source=np.asarray(C, dtype=float), mode_declare='cumule',
             generer_graphiques=False, generer_word=False,
             n_sim_bootstrap=300, seed=42)
    d.update(kw)
    return AgentA7Provisionnement(verbose=False).run(**d)


# =============================================================================
#  T1 — PORTE FERMEE : LE DOCUMENT NE PUBLIE PAS CE QU'IL DECLARE RETIRE
# =============================================================================

class T1_La_Porte_De_Gouvernance(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ferme = _run(_tri_bruite(0.75))
        cls.ouvert = _run(RAA)

    def test_porte_fermee_le_p90_bootstrap_ne_figure_dans_aucun_livrable(self):
        n4 = self.ferme['n4']
        p90_n3 = (self.ferme['n3'].get('bootstrap') or {}).get('p90')
        if n4.get('reserve_p90_boot') is not None:
            self.skipTest('ce triangle ne ferme pas la porte')
        self.assertIsInstance(
            p90_n3, float, 'le Bootstrap n a pas tourne : rien a retirer')
        # ⚠️⚠️ LES TROIS PERCENTILES, ET NON LE SEUL P90. Cette sentinelle
        # ne balayait que `p90`. Mesure du 11/09/2026 : le §4 du commentaire
        # (`_s4_methodes`) lisait `n3['bootstrap']['p99_5']` EN DIRECT et
        # publiait « Le P99.5 Bootstrap s'etablit a 1 265 € » sur le dossier
        # de reference `Recours`, PORTE FERMEE, pendant que le meme document
        # ecrivait « percentiles retires par la gouvernance ». Le P90, lui,
        # etait bien retire — c'est exactement ce qui rendait la
        # contradiction invisible a ce controle.
        _b = self.ferme['n3'].get('bootstrap') or {}
        cibles = [('P75', _b.get('p75')), ('P90', p90_n3),
                  ('P99,5', _b.get('p99_5'))]
        for nom, txt in (('HTML', self.ferme.get('html') or ''),
                         ('commentaire', self.ferme.get('commentaire') or '')):
            for lbl, val in cibles:
                if val is None:
                    continue
                for f in _formes(val):
                    self.assertNotIn(
                        f, txt,
                        '%s : la gouvernance a ferme la publication des '
                        'percentiles et le document publie le %s (%s) quand '
                        'meme.' % (nom, lbl, f))
        print('    OK L8-1 porte fermee : le P90 de n3 (%s) ne figure ni au '
              'HTML ni au commentaire' % round(p90_n3))

    def test_le_retrait_est_NOMME_et_non_confondu_avec_une_panne(self):
        if self.ferme['n4'].get('reserve_p90_boot') is not None:
            self.skipTest('ce triangle ne ferme pas la porte')
        com = self.ferme.get('commentaire') or ''
        self.assertIn(
            'gouvernance', com,
            'le retrait DECIDE par une hypothese est presente comme une '
            'indisponibilite : deux absences differentes, deux phrases.')
        print('    OK L8-2 le retrait est nomme, pas confondu avec une panne')

    def test_porte_OUVERTE_les_percentiles_sont_bien_publies(self):
        """⚠️ LA CONTRE-EPREUVE. Fermer toujours n'est pas gouverner."""
        n4 = self.ouvert['n4']
        if n4.get('reserve_p90_boot') is None:
            self.skipTest('ce triangle ferme aussi la porte')
        com = self.ouvert.get('commentaire') or ''
        self.assertTrue(
            any(f in com for f in _formes(n4['reserve_p90_boot'])),
            'porte OUVERTE et le percentile ne sort pas : le bloc ne publie '
            'plus rien du tout.')
        print('    OK L8-3 porte ouverte : le P90 gouverne est publie')


# =============================================================================
#  T2 — UNE PAGE D'ERREUR SE DECLARE
# =============================================================================

class T2_Le_Marqueur_A_Un_Lecteur(unittest.TestCase):

    def test_un_repli_plus_gros_que_le_seuil_est_quand_meme_attrape(self):
        def repli(**kw):
            return (MARQUEUR_ECHEC_RAPPORT + '<html><body><h1>Erreur : '
                    + 'X' * 600 + '</h1></body></html>').encode('utf-8')
        octets, err = AG._produire_livrable('html', repli)
        self.assertGreater(
            len(octets), AG._TAILLE_MIN_LIVRABLE,
            'le repli ne depasse plus le seuil : le plant est mort, il serait '
            'attrape par le controle de TAILLE et non par le marqueur.')
        self.assertTrue(
            err, 'un repli de %d octets passe pour un livrable' % len(octets))
        print('    OK L8-4 repli de %d octets (seuil %d) : %r'
              % (len(octets), AG._TAILLE_MIN_LIVRABLE, err))

    def test_un_vrai_rapport_n_est_pas_pris_pour_un_repli(self):
        """⚠️ LA CONTRE-EPREUVE."""
        def vrai(**kw):
            return ('<html><body>' + 'contenu reel ' * 80
                    + '</body></html>').encode('utf-8')
        octets, err = AG._produire_livrable('html', vrai)
        self.assertIsNone(
            err, 'un vrai rapport est declare en echec : %r' % err)
        print('    OK L8-5 vrai rapport de %d octets : aucune erreur'
              % len(octets))


# =============================================================================
#  T3 — LE CONTROLE DES REFERENCES A L'ASSIETTE DU DOCUMENT
# =============================================================================

class T3_L_Assiette_Est_Le_Document(unittest.TestCase):

    def test_aucun_article_hors_liste_dans_le_document_entier(self):
        html = _run(RAA, n_sim_bootstrap=30).get('html') or ''
        self.assertTrue(html, 'pas de HTML produit')
        hors = references_hors_liste(html)
        self.assertEqual(
            hors, [],
            "le DOCUMENT cite %s, que le controle des references refuse. Son "
            "assiette etait la narration du modele ; le texte deterministe en "
            "sortait." % hors)
        print('    OK L8-6 document entier (%d car.) : aucun article hors '
              'liste' % len(html))

    def test_le_controle_attrape_encore_un_article_interdit(self):
        """⚠️ LA CONTRE-EPREUVE : un controle qui ne trouve plus rien parce
        qu'il ne cherche plus rien ne protege rien."""
        self.assertEqual(
            references_hors_liste("conformement a l'Art. 105 de la Directive"),
            ['105'],
            'le controle ne voit plus un article interdit')
        print('    OK L8-7 le controle attrape encore un article hors liste')


# =============================================================================
#  T4 — UNE SUR-DISPERSION NULLE N'EST PAS UNE PANNE
# =============================================================================

class T4_Phi_Quasi_Nul(unittest.TestCase):

    @staticmethod
    def _sans_bruit(n=8):
        cad = np.cumsum([0.85 ** j for j in range(n)])
        C = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i + j < n:
                    C[i, j] = 100000.0 * (1 + 0.03 * i) * cad[j]
        return C

    def test_un_triangle_sans_dispersion_se_retire_au_lieu_de_planter(self):
        C = self._sans_bruit()
        f, _ = calculer_facteurs(C, 'standard')
        self.assertIsNone(
            nulle_parametrique(C, f),
            'un triangle sans dispersion doit se retirer : il n y a AUCUNE '
            'heterogeneite a tester.')
        r = _run(C, generer_html=False, n_sim_bootstrap=30)
        self.assertIsNone(
            (r['n2'].get('bootstrap') or {}).get('erreur'),
            'le run porte encore une erreur de Bootstrap : %r'
            % (r['n2'].get('bootstrap') or {}).get('erreur'))
        print('    OK L8-8 triangle sans dispersion : retrait propre, aucune '
              'exception')

    def test_une_dispersion_nulle_ne_publie_pas_un_percentile(self):
        """⚠️⚠️ CE FICHIER CONSTRUIT DEJA LE TRIANGLE QUI DECLENCHE LE DEFAUT,
        ET NE REGARDAIT QUE L'ABSENCE D'EXCEPTION.

        Mesure du 11/09/2026 sur `_sans_bruit()`, la fixture ci-dessus :
        sigma_Mack = 0, sigma Bootstrap = 0, sigma compose = 0, et le module
        publiait BE = P75 = P90 = P99,5 = 2 400 931 EUR, avec un Bootstrap
        `disponible=True, statut=VERT` et un statut global AMBRE. Le document
        affirmait donc que la reserve ne peut pas etre depassee — la
        pathologie que la docstring de `_resultat_degrade` nomme.
        """
        r = _run(self._sans_bruit(), generer_html=False, n_sim_bootstrap=60)
        n4 = r['n4']
        self.assertAlmostEqual(
            float(n4.get('sigma_mack') or 0), 0.0, places=6,
            msg='ce triangle n a plus une dispersion nulle : le controle ne '
                'prouve plus rien')
        self.assertFalse(
            (r['n3'].get('bootstrap') or {}).get('disponible'),
            'un Bootstrap a dispersion nulle se declare disponible')
        self.assertEqual(
            n4.get('statut'), 'ROUGE',
            'une dispersion nulle sur les trois approches ne peut pas '
            'coexister avec un statut favorable')
        self.assertTrue(
            n4.get('percentiles_non_mesurables'),
            'le module ne DECLARE pas que les percentiles sont non mesurables')
        self.assertIn('NON MESURABLES', str(n4.get('source_percentiles')))
        print('    OK L8-10 dispersion nulle : Bootstrap retire, statut '
              'ROUGE, percentiles declares non mesurables')

    def test_un_triangle_BRUITE_rend_encore_un_verdict(self):
        """⚠️ LA CONTRE-EPREUVE : se retirer toujours ne teste plus rien."""
        C = _tri_bruite(0.05, graine=3, n=8)
        f, _ = calculer_facteurs(C, 'standard')
        self.assertIsNotNone(
            nulle_parametrique(C, f),
            'un triangle bruite doit encore produire une nulle parametrique')
        print('    OK L8-9 triangle bruite : la nulle parametrique est '
              'toujours calculee')


if __name__ == '__main__':
    unittest.main(verbosity=2)
