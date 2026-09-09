# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — CE QUE N1 CONSTATE ATTEINT ENFIN LE DOCUMENT
=============================================================================

 N1 diagnostique la qualite de la donnee, et personne ne lisait.

 Les controles dont le statut est ROUGE partent dans `rapport['infos']`, et
 non dans `rapport['alertes']` qui seul colore le statut. C'est une decision
 tranchee et argumentee en tete de `nv_triangle`, et elle n'est PAS en cause.
 Ce qui l'etait est la phrase qui l'accompagne : « il est integralement
 expose ». Mesure : le mot `infos` n'apparaissait pas UNE SEULE FOIS dans les
 cinq modules N5, et `prep.diagnostics` n'avait aucun lecteur hors de son
 module. Le diagnostic etait expose dans un dictionnaire de retour ; il
 n'etait expose a personne.

 ⚠️ ET LE SYSTEM_PROMPT DE LA NARRATION exige une section « §1 — CONTEXTE ET
 QUALITE DES DONNEES » en interdisant les « phrases generiques sans
 donnees », pendant que rien ne lui transmettait de charge sur la qualite.

 ⚠️⚠️ LE CAS QUI COMPTE. Sur un triangle 6x10 entierement observe, le seul
 signal du masquage etait la ligne « 4 colonnes vides — structure du triangle
 a verifier », rangee dans `infos`. C'est le controle qui aurait revele le
 defaut, et il n'atteignait aucun document. Il l'atteint desormais.

 ⚠️ UN SEUL HELPER POUR DEUX RENDUS. Composer la meme section deux fois,
 c'est se donner deux occasions de diverger — ce depot l'a deja paye sur
 l'arrete et sur les seuils.

 ⚠️ ET LA PORTE DE GOUVERNANCE VAUT AUSSI POUR LE WORD. Le tableau
 « Diagnostic » du format SIGNE lisait `n3['bootstrap']['p90']` en direct,
 exactement comme le bloc du commentaire. Fermer un rendu sur deux aurait
 laisse la contradiction vivante la ou elle compte le plus.
=============================================================================
"""

import io
import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement)
from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
    lignes_qualite_donnees)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    RAA)

TITRE = 'ualit'          # « Qualite » / « Qualité », les deux graphies


def _tri_rectangulaire():
    """6 annees x 10 periodes, ENTIEREMENT observe : le cas dont le seul
    signal etait une ligne rangee dans `infos`."""
    cad = np.array([0.20, 0.18, 0.14, 0.11, 0.09, 0.08, 0.07, 0.05, 0.05, 0.03])
    M = np.zeros((6, 10))
    for i in range(6):
        M[i, :] = 250000.0 * (1 + 0.05 * i) * cad
    return M


def _run(src, **kw):
    d = dict(source=np.asarray(src, dtype=float), mode_declare='cumule',
             generer_graphiques=False, generer_word=False,
             n_sim_bootstrap=30, seed=42)
    d.update(kw)
    return AgentA7Provisionnement(verbose=False).run(**d)


# =============================================================================
#  T1 — LE CANAL EXISTE, DANS LES DEUX RENDUS
# =============================================================================

class T1_Le_Canal_Atteint_Les_Deux_Formats(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = _run(RAA, generer_word=True)

    def test_le_html_porte_la_section_qualite_des_donnees(self):
        html = self.r.get('html') or ''
        self.assertIn(TITRE, html)
        self.assertIn('préparation (N1)'.replace('é', 'é'), html.replace(
            'preparation', 'préparation'))
        print('    OK L9-1 le HTML porte la section qualite des donnees')

    def test_le_word_porte_la_meme_section(self):
        from docx import Document
        w = Document(io.BytesIO(self.r['word_bytes']))
        txt = '\n'.join(p.text for p in w.paragraphs)
        self.assertIn(TITRE, txt,
                      'le canal atteint un format sur deux : le Word, qui est '
                      'le document SIGNE, ne porte pas la section.')
        print('    OK L9-2 le Word porte la meme section')

    def test_les_deux_rendus_viennent_du_MEME_helper(self):
        """⚠️ SOURCE UNIQUE. Deux compositions, deux occasions de diverger."""
        lignes = lignes_qualite_donnees(self.r['n1'])
        self.assertTrue(lignes, 'le helper ne rend rien')
        html = self.r.get('html') or ''
        from docx import Document
        w = Document(io.BytesIO(self.r['word_bytes']))
        txt = '\n'.join(p.text for p in w.paragraphs)
        # La premiere ligne (taille, mode, statut) doit se retrouver telle
        # quelle dans les deux formats.
        socle = lignes[0]
        for nom, doc in (('HTML', html), ('Word', txt)):
            self.assertIn(
                socle[:40], doc,
                '%s : la ligne de socle du helper ne s y retrouve pas — les '
                'deux rendus ne partagent plus leur source.' % nom)
        print('    OK L9-3 la meme ligne de socle dans les deux : %r'
              % socle[:60])


# =============================================================================
#  T2 — LE CONTROLE ROUGE ATTEINT LE DOCUMENT
# =============================================================================

class T2_Un_Controle_Rouge_Est_Publie(unittest.TestCase):

    def test_le_diagnostic_rouge_du_triangle_rectangulaire_est_publie(self):
        r = _run(_tri_rectangulaire(), mode_declare='incremental')
        infos_rouges = [str(i) for i in (r['n1'].get('infos') or [])
                        if 'ROUGE' in str(i) or '\U0001F534' in str(i)]
        self.assertTrue(
            infos_rouges,
            'ce triangle ne produit plus de controle ROUGE : le plant est mort')
        html = r.get('html') or ''
        self.assertIn(
            'ROUGE', html,
            'le controle ROUGE de N1 n atteint toujours aucun document — '
            'c est pourtant lui qui aurait revele le masquage.')
        self.assertIn('colonnes vides', html)
        print('    OK L9-4 le controle ROUGE (%d) est publie : %s'
              % (len(infos_rouges), infos_rouges[0][:80]))

    def test_un_triangle_propre_le_dit_au_lieu_de_se_taire(self):
        """⚠️ LA CONTRE-EPREUVE. Une section vide ne vaut pas une section qui
        DECLARE l absence : un CAC ne distingue pas « rien a signaler » de
        « rien n a ete regarde »."""
        # ⚠️ « PROPRE » A CHANGE DE SENS AU LOT 12. En branchant
        # `methodes_demandees`, la preparation annonce desormais que
        # Bornhuetter-Ferguson et Cape Cod ne pourront pas s'executer
        # faute d'exposition : RAA SANS primes porte deux alertes, et
        # elles sont justes. Le triangle propre est donc celui qui porte
        # AUSSI son exposition. C'est la gate qui l'a signale, sur
        # l'instantane gele, et l'assertion reste entiere.
        _expo = np.full(len(RAA),
                        float(np.nanmean(np.asarray(RAA, float)[:, 0]))
                        * 8.0)
        lignes = lignes_qualite_donnees(_run(RAA, primes=_expo)['n1'])
        self.assertTrue(
            any('Aucune alerte' in l for l in lignes),
            'sur un triangle propre, la section doit DECLARER l absence : %s'
            % lignes)
        print('    OK L9-5 triangle propre : l absence est declaree')

    def test_le_helper_ne_rend_jamais_une_liste_vide(self):
        for cas in ({}, None, {'statut': 'VERT'}):
            self.assertTrue(
                lignes_qualite_donnees(cas),
                'le helper rend une liste vide sur %r : la section serait un '
                'titre sans contenu' % (cas,))
        print('    OK L9-6 le helper ne rend jamais une section vide')


# =============================================================================
#  T3 — LA PORTE DE GOUVERNANCE VAUT AUSSI POUR LE WORD
# =============================================================================

class T3_La_Porte_Vaut_Pour_Le_Word(unittest.TestCase):

    @staticmethod
    def _tri_porte_fermee():
        rng = np.random.default_rng(9)
        n = 9
        inc = np.array([0.85 ** j for j in range(n)])
        C = np.zeros((n, n))
        for i in range(n):
            acc = 0.0
            for j in range(n):
                if i + j < n:
                    acc += 100000.0 * (1 + 0.04 * i) * inc[j] * \
                        max(0.05, 1.0 + rng.normal(0, 0.75))
                    C[i, j] = acc
        return C

    def test_porte_fermee_le_word_ne_publie_pas_le_percentile(self):
        from docx import Document
        r = _run(self._tri_porte_fermee(), generer_word=True,
                 n_sim_bootstrap=200)
        if r['n4'].get('reserve_p90_boot') is not None:
            self.skipTest('ce triangle ne ferme pas la porte')
        p90 = (r['n3'].get('bootstrap') or {}).get('p90')
        self.assertIsInstance(p90, float, 'le Bootstrap n a pas tourne')
        w = Document(io.BytesIO(r['word_bytes']))
        cellules = [c.text for t in w.tables for row in t.rows for c in row.cells]
        # ⚠️⚠️ LES SEPARATEURS S'ECRIVENT EN ECHAPPEMENT, JAMAIS EN LITTERAL.
        # `_f` separe les milliers par une espace FINE INSECABLE (U+202F) et
        # suffixe par U+202F + euro. Ecrits en caracteres bruts, ces espaces
        # ont ete aplatis en espaces ordinaires a l'ecriture du fichier : le
        # tuple portait TROIS fois le meme separateur, et l'assertion ne
        # pouvait plus matcher. Le test passait pour la mauvaise raison — la
        # violation plantee l'a revele, c'est son role.
        formes = [('%s' % format(round(p90), ',')).replace(',', c)
                  for c in (' ', ' ', ' ', ',')]
        for f in formes:
            self.assertFalse(
                any(f in c for c in cellules),
                'le WORD — le document SIGNE — publie %s alors que la '
                'gouvernance a ferme la publication des percentiles.' % f)
        print('    OK L9-7 porte fermee : le Word ne publie pas le P90 (%s)'
              % round(p90))


if __name__ == '__main__':
    unittest.main(verbosity=2)
