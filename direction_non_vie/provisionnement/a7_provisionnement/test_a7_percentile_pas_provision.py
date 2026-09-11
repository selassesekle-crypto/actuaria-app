# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — UN PERCENTILE MESURE, IL NE S'INSCRIT PAS (Art. 77)
=============================================================================

 CE QUE CE FICHIER TIENT.

 Sous Solvabilité II, les provisions techniques valent BE + marge de risque,
 et le Best Estimate est une ESPÉRANCE (Art. 77 de la Directive 2009/138/CE —
 c'est bien la Directive, `config/rfr_eiopa.py` a déjà établi que l'article 77
 du Règlement délégué porte, lui, sur les fonds propres de niveau 3). Y
 substituer un P75, un P90 ou un P99,5 ajoute une prudence discrétionnaire que
 le texte ne prévoit pas.

 ⚠️⚠️ LE DÉFAUT ÉTAIT UNE FAMILLE, PAS UNE PHRASE. Dix-neuf sites, dans TROIS
 modules — `n5_commentaire`, `n5_excel` et `n4_best_estimate` — en trois
 formes : la recommandation qui substitue (« {P90} au lieu du BE », publié sur
 TOUT dossier AMBRE ou ROUGE, c'est-à-dire la quasi-totalité puisqu'un dossier
 mono-méthode ne peut pas sortir VERT), l'étiquette qui renomme (« Provision
 stress test P90 » sous un en-tête annonçant « percentiles retenus »), et le
 verdict qui se contredit.

 ⚠️ ET LE DÉPÔT AVAIT DÉJÀ PAYÉ CETTE FAMILLE UNE FOIS : le commentaire de la
 branche VERT de `_s8_recommandations` documente une instruction identique
 retirée au commit `fcfb3d3` — « elle vivait ici, mot pour mot ». Corrigée à
 un endroit, elle survivait à dix-huit autres. C'est pourquoi ce test balaie
 le DOCUMENT PRODUIT et le SOURCE des trois modules, jamais un site nommé.

 ⚠️ LA VIOLATION EST PLANTÉE DANS LE TEST. `T4` rejoue les formulations
 d'avant et exige que le détecteur les attrape : un détecteur qu'on n'a pas
 vu mordre ne prouve rien.
=============================================================================
"""

import io
import re
import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    RAA)

#: Les tournures qui demandent d'INSCRIRE un percentile, ou qui le renomment
#: du mot réservé à ce qui s'inscrit. Motifs volontairement larges : c'est
#: l'intention qui est interdite, pas une phrase précise.
MOTIFS_INTERDITS = (
    r"au lieu du BE",
    r"provision\s+(?:de\s+risque\s+)?complémentaire",
    r"provision\s+conservatrice",
    r"provision\s+prudentielle",
    r"provision\s+stress\s+test",
    r"provision\s+extrême",
    r"plancher\s+conservateur",
    r"buffer\s+de\s+prudence",
    # ⚠️⚠️ LE MOTIF VISAIT LES TOURNURES QUALIFIEES, PAS LA PROPRIETE.
    # « Provision prudentielle P75 », « Provision stress test P90 » etaient
    # attrapees ; la forme NUE « Provision P90 » — celle qui a survecu a
    # dix-neuf renommages — passait. Sept tests rendaient VERT en imprimant
    # « n5_excel.py : net » sur un fichier qui portait la faute.
    r"provisions?\s+de\s+pr[ée]caution",
    r"provision\s+p\s*\d",
)

#: Les modules qui composent du texte signé.
#: ⚠️⚠️ L'ASSIETTE OUBLIAIT `n5_rapport.py` — celui qui en compose DEUX (le
#: HTML et le Word) et qui porte le PLAN IMPOSE au modele de langage :
#: « §4 — INCERTITUDE STOCHASTIQUE ET PROVISIONS DE PRECAUTION ». Le sceau
#: se declarait « les trois modules qui composent du texte signé » et le
#: quatrieme en composait deux. Un controle hors de l'assiette du defaut
#: est du decor, quelle que soit sa qualite.
MODULES = ('n5_commentaire.py', 'n5_excel.py', 'n4_best_estimate.py',
           'n5_rapport.py')


def _sans_commentaires(src: str) -> str:
    """Retire les lignes de commentaire : elles CITENT le défaut pour le
    documenter, et une citation n'est pas une instruction publiée."""
    return '\n'.join(l for l in src.split('\n')
                     if not l.lstrip().startswith('#'))


def _hits(texte: str) -> list:
    trouves = []
    for m in MOTIFS_INTERDITS:
        if re.search(m, texte, re.IGNORECASE):
            trouves.append(m)
    return trouves


class _Socle(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        src = np.asarray(RAA, dtype=float)
        cls.r = AgentA7Provisionnement(verbose=False).run(
            source=src, mode_declare='cumule', generer_graphiques=False,
            generer_word=False, n_sim_bootstrap=30, seed=42)
        cls.commentaire = cls.r.get('commentaire') or ''
        cls.html = cls.r.get('html') or ''


# =============================================================================
#  T1 — LE DOCUMENT PRODUIT N'INSTRUIT JAMAIS D'INSCRIRE UN PERCENTILE
# =============================================================================

class T1_Le_Document_Ne_Substitue_Pas(_Socle):

    def test_le_commentaire_signe_ne_demande_pas_d_inscrire_un_percentile(self):
        h = _hits(self.commentaire)
        self.assertEqual(
            h, [],
            "le commentaire SIGNÉ porte %r — un percentile mesure la "
            "dispersion, il ne s'inscrit pas au bilan (Art. 77)." % h)
        print("    OK PA2-1 commentaire signé : aucune instruction "
              "d'inscrire un percentile")

    def test_le_rapport_html_ne_demande_pas_d_inscrire_un_percentile(self):
        h = _hits(self.html)
        self.assertEqual(
            h, [],
            "le rapport HTML porte %r (Art. 77)." % h)
        print("    OK PA2-2 rapport HTML : idem, sur %d caractères"
              % len(self.html))


# =============================================================================
#  T2 — LE SOURCE DES TROIS MODULES NE PORTE PLUS LA FAMILLE
# =============================================================================

class T2_Les_Trois_Modules_Sont_Nets(unittest.TestCase):
    """⚠️ L'ASSIETTE EST LE SOURCE, PAS UN RUN. Un run ne traverse qu'une
    branche de statut ; le défaut vivait dans les branches AMBRE et ROUGE, que
    le triangle de référence ne prend pas toujours."""

    def test_aucun_des_trois_modules_n_instruit_d_inscrire_un_percentile(self):
        import direction_non_vie.provisionnement.a7_provisionnement as pkg
        base = pkg.__path__[0]
        for nom in MODULES:
            src = io.open(base + '/' + nom, encoding='utf-8').read()
            h = _hits(_sans_commentaires(src))
            self.assertEqual(
                h, [],
                "%s porte %r hors commentaire — la famille est revenue."
                % (nom, h))
            print("    OK PA2-3 %s : net" % nom)


# =============================================================================
#  T3 — LE VERDICT NE SE CONTREDIT PAS
# =============================================================================

class T3_Un_Seul_Verdict(_Socle):

    def test_l_avis_du_commentaire_est_celui_que_n4_publie(self):
        avis_n4 = (self.r.get('rapport_actuaire') or {}).get('avis') or ''
        self.assertIn(
            'AVIS ACTUARIEL : ' + avis_n4.split('—')[0].strip(),
            self.commentaire,
            "le §8 du commentaire et `rapport_actuaire.avis` publient deux "
            "verdicts différents dans le MÊME document.")
        self.assertNotIn(
            'FAVORABLE AVEC RÉSERVES', self.commentaire,
            "« FAVORABLE » commence le mot que N4 a retiré du cas AMBRE : un "
            "lecteur qui parcourt la fin y lit un feu vert.")
        print("    OK PA2-4 un seul verdict : %r" % avis_n4)

    def test_un_cv_nul_sur_une_seule_methode_ne_se_lit_pas_convergence(self):
        n_meth = len(self.r['n4'].get('methodes_incluses') or ())
        if n_meth >= 2:
            self.skipTest('ce triangle retient %d méthodes' % n_meth)
        self.assertNotIn(
            'divergence modérée est observée entre méthodes',
            self.commentaire,
            "une SEULE méthode est retenue : le CV inter-méthodes vaut zéro "
            "PAR CONSTRUCTION et ne mesure aucune convergence.")
        self.assertIn('SEULE méthode', self.commentaire)
        print("    OK PA2-5 mono-méthode : le CV nul est déclaré pour ce "
              "qu'il est")


# =============================================================================
#  T4 — LA VIOLATION PLANTÉE : le détecteur mord-il vraiment ?
# =============================================================================

class T4_Le_Detecteur_Mord(unittest.TestCase):
    """⚠️ SANS CETTE CLASSE, T1 à T3 passeraient avec un détecteur qui ne
    détecte rien. On rejoue les formulations D'AVANT et on exige qu'il les
    attrape, une par une."""

    AVANT = (
        "3. Envisager une provision de risque complémentaire "
        "(86 365 € au lieu du BE) si la direction financière privilégie "
        "la prudence.",
        "5. Considérer une provision conservatrice de 161 991 € en attendant "
        "la résolution.",
        "  • Provision prudentielle P75  : 61 049 €",
        "  • Provision stress test P90   : 86 365 €",
        "  • Provision extrême P99.5     : 161 991 €",
        "Le P90 de 86 365 € est recommandé comme plancher conservateur.",
        "Le P90 = 86 365 € est à utiliser pour le calibrage du buffer de "
        "prudence.",
    )

    def test_chaque_formulation_d_avant_est_bien_attrapee(self):
        for txt in self.AVANT:
            h = _hits(txt)
            self.assertTrue(
                h, "le détecteur laisse passer %r — il ne protège rien."
                   % txt[:60])
        print("    OK PA2-6 les %d formulations d'avant sont toutes "
              "attrapées" % len(self.AVANT))

    def test_une_formulation_conforme_n_est_PAS_attrapee(self):
        """⚠️ L'AUTRE MOITIÉ : un détecteur qui attrape tout ne discrimine pas
        davantage qu'un détecteur qui n'attrape rien."""
        conformes = (
            "3. Documenter la dispersion dans le dossier actuariel : "
            "86 365 € au P90, soit 65.7% au-dessus du Best Estimate.",
            "  • Percentile de stress P90    : 86 365 €",
            "Le P90 mesure l'ampleur de cette divergence ; il ne constitue "
            "pas un montant à inscrire (Art. 77).",
        )
        for txt in conformes:
            self.assertEqual(
                _hits(txt), [],
                "le détecteur attrape une formulation CONFORME : %r" % txt[:60])
        print("    OK PA2-7 les formulations conformes passent : le "
              "détecteur discrimine")


if __name__ == '__main__':
    unittest.main(verbosity=2)
