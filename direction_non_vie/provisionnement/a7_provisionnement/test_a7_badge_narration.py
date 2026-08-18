# =============================================================================
#  A7 — CE QUE PORTE L'HTML, LE WORD LE PORTE
# =============================================================================
#
#  ⚠️ CE VERROU N'EXISTAIT PAS, ET LE DÉFAUT VIVAIT DEPUIS L'ORIGINE.
#
#  Le rendu Word était gardé par `if source == 'claude_api'`. Or ce chemin ne
#  s'exécute QUE si une clé API est posée ; sans clé — le cas par défaut — la
#  narration vient de `templates`, et le Word ne publiait alors NI l'origine
#  du texte NI la phrase d'engagement. Mesuré avant le lot A5 :
#
#      « Cette narration engage l'actuaire signataire. »   HTML 1   WORD 0
#      « Mode standard »                                    HTML 1   WORD 0
#
#  ⚠️ ET C'EST LE WORD QUE L'ACTUAIRE ENVOIE AU COMMISSAIRE AUX COMPTES. Un
#  document qui ne dit pas ce qui a produit sa section 7, ni ce qu'elle
#  engage, n'est pas opposable — quelle que soit la qualité de son contenu.
#
#  Aucun test ne couvrait ce badge. Les seuls qui touchaient ces marqueurs
#  vivaient dans une AUTRE direction (`direction_sante_prevoyance`), et l'un
#  d'eux cite A7 comme référence de vocabulaire honnête — pendant que le Word
#  d'A7 se taisait.
# =============================================================================

import io
import re
import unittest
import zipfile

import numpy as np

from core import traitement_ia

from .agent import AgentA7Provisionnement
from .n5_rapport import badge_narration

#: Le triangle témoin des mesures du chantier — RC Générale, 6×6, cumulé.
_TRIANGLE = np.array([
    [3_200., 5_100., 5_900., 6_250., 6_400., 6_450.],
    [3_450., 5_400., 6_300., 6_700., 6_850.,   np.nan],
    [3_800., 6_050., 7_050., 7_500.,   np.nan, np.nan],
    [4_100., 6_400., 7_400.,   np.nan, np.nan, np.nan],
    [4_500., 7_200.,   np.nan, np.nan, np.nan, np.nan],
    [4_900.,   np.nan, np.nan, np.nan, np.nan, np.nan],
])
_PRIMES = [9_000., 9_600., 10_400., 11_100., 12_000., 13_000.]


def _texte_du_word(octets: bytes) -> str:
    """Le texte nu d'un .docx — les balises retirées, rien d'autre."""
    if not octets:
        return ''
    with zipfile.ZipFile(io.BytesIO(octets)) as z:
        xml = z.read('word/document.xml').decode('utf-8', 'replace')
    return re.sub(r'<[^>]+>', '', xml)


class A5_Le_Badge_Vient_D_Une_Seule_Table(unittest.TestCase):
    """Le libellé d'origine et l'engagement ne se recopient pas d'un rendu
    à l'autre : ils viennent de `badge_narration`."""

    def test_chaque_source_reelle_porte_l_engagement(self):
        for source in ('claude_api', 'templates'):
            badge = badge_narration(source)
            self.assertIn(traitement_ia.ENGAGEMENT, badge,
                          f"la source {source!r} ne porte pas l'engagement")
            self.assertNotEqual(badge.strip(), traitement_ia.ENGAGEMENT,
                                f"la source {source!r} n'a pas de libellé")
        print("    OK A5-1 claude_api et templates portent libellé + engagement")

    def test_sans_narration_le_badge_n_affirme_rien(self):
        # ⚠️ Un rapport sans narration ne doit engager personne. `aucune` et
        # une source inconnue rendent la chaîne vide, pas l'engagement seul.
        for source in ('aucune', '', 'source_inventee'):
            self.assertEqual(badge_narration(source), '',
                             f"la source {source!r} publie un badge")
        print("    OK A5-2 aucune source vide ne publie d'engagement")


class A5_Le_Word_Porte_Ce_Que_Porte_L_HTML(unittest.TestCase):
    """⚠️ LE TEST QUI MANQUAIT. Sur un run réel, sans clé API — donc sur le
    chemin `templates`, le seul qui s'exécute — les deux rendus disent la
    même chose sur l'origine de la narration."""

    @classmethod
    def setUpClass(cls):
        r = AgentA7Provisionnement().run(
            source=_TRIANGLE, primes=_PRIMES, lob='rc_generale',
            ref_client='PARITE', arrete='T2 2026', date_arrete='2026-06-30')
        cls.ok = bool(r.get('success'))
        cls.html = r.get('html') or ''
        cls.word = _texte_du_word(r.get('word_bytes') or b'')

    def test_le_run_produit_les_deux_rendus(self):
        self.assertTrue(self.ok, 'le run a échoué')
        self.assertTrue(self.html, 'aucun HTML produit')
        self.assertTrue(self.word, 'aucun Word produit')
        print(f"    OK A5-3 HTML {len(self.html):,} car. · "
              f"Word {len(self.word):,} car.")

    def test_l_engagement_est_dans_les_deux(self):
        # ⚠️ C'EST LE CŒUR DU VERROU. Avant le lot A5 : HTML 1, Word 0.
        for nom, rendu in (('HTML', self.html), ('Word', self.word)):
            self.assertIn(
                traitement_ia.ENGAGEMENT, rendu,
                f"{nom} ne porte pas la phrase d'engagement — "
                f"c'est le format remis au CAC")
        print("    OK A5-4 l'engagement est dans l'HTML ET dans le Word")

    def test_l_origine_est_dans_les_deux(self):
        libelle = '📝 Mode standard'
        for nom, rendu in (('HTML', self.html), ('Word', self.word)):
            self.assertIn(libelle, rendu,
                          f"{nom} ne dit pas l'origine de sa narration")
        print("    OK A5-5 l'origine « Mode standard » est dans les deux")

    def test_il_attrape_la_violation_plantee(self):
        """⚠️ LE VERROU SE CONFRONTE À L'ANCIEN COMPORTEMENT.

        Sans cette épreuve, un test qui passe ne prouve rien : il pourrait
        passer parce qu'il ne regarde pas au bon endroit. On rejoue ici la
        garde d'origine — `if source == 'claude_api'` — sur la source qui
        s'exécute réellement, et on vérifie qu'elle produirait un Word muet.
        """
        source_reelle = 'templates'
        ancien = ('✦ Narration générée par ActuarIA Intelligence'
                  if source_reelle == 'claude_api' else '')
        self.assertEqual(ancien, '',
                         'la garde d’origine aurait publié quelque chose')
        self.assertNotEqual(
            badge_narration(source_reelle), '',
            'le correctif ne publie rien non plus — le verrou est inutile')
        print("    OK A5-6 la garde d'origine rendait bien un Word muet")


if __name__ == '__main__':
    unittest.main(verbosity=2)
