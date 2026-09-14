r"""
==============================================================================
  UNE LACUNE SE DIT -- DEUX COMPTES QUI LAISSAIENT PASSER UN CAS
==============================================================================

DEUX REPORTS DU ROUND 4, MEME FAMILLE : un predicat qui ne distingue que
DEUX etats la ou il en existe TROIS, et le troisieme disparait en
silence.

⚠️⚠️ `D5` -- UNE DECLARATION A MOITIE FAITE ETEIGNAIT L'ALARME AU LIEU
DE LA LEVER. `phrase_conditions_de_mesure` testait
`if not any(c.declaree_au_plan for c in lignes)` : il suffisait qu'UN
SEUL agent declare sa decoupe pour que la phrase disparaisse -- POUR
TOUS LES AUTRES. *Le classement met cote a cote des scores dont certains
reposent sur une hypothese signee et d'autres non, et c'est son premier
qui devient le modele de production.*

    0 / 3 declarees   avant  alarme LEVEE (785 car.)   apres  TOTALE
    1 / 3 declarees   avant  ETEINTE (396 car.)        apres  PARTIELLE (707)
    2 / 3 declarees   avant  ETEINTE (396 car.)        apres  PARTIELLE (703)
    3 / 3 declarees   avant  ETEINTE (396 car.)        apres  aucune (396)

⚠️ LA DOCTRINE ETAIT DEJA APPLIQUEE A COTE : le bloc juste au-dessus sait
dire une divergence PARTIELLE des assiettes d'apprentissage, en nommant
chaque agent. On lui a emprunte sa forme.

⚠️⚠️ `D6` -- UN ECARTE SANS CAUSE N'ENTRAIT DANS AUCUN COMPTE.
`synthese_comparaison` ne comptait que `CAUSE_CRITERE` et
`CAUSE_SANS_PRIX` ; or `ResultatCandidat.cause` vaut `''` PAR DEFAUT.

    3 ecartes, causes nommees  ->  2 + 1     = 3 comptes  (juste)
    2 ecartes, une cause vide  ->  1 + 0     = 1 compte   (1 PERDU)
    2 ecartes, toutes vides    ->  0 + 0     = 0 compte   (2 PERDUS)

*Le titre annoncait bien << COMPARAISON DE 2 CANDIDAT(S) >> et sa
ventilation en comptait zero : le total et son detail ne portaient pas
sur la meme assiette.*

⚠️ ON NE RANGE PAS L'ECARTE SANS CAUSE DANS UN SEAU EXISTANT. Ce n'est
ni un echec de critere ni une absence de prix : c'est une LACUNE DE
DECLARATION. Le module interdit deja d'additionner les deux premieres
especes ; en inventer une troisieme sous un nom emprunte serait la meme
faute.

⚠️ LES DEUX PHRASES ATTEIGNENT LES DEUX SURFACES SIGNEES sans travail
supplementaire : `phrase_conditions_de_mesure` est publiee en HTML
(l.1456) et en Word (l.3534) ; `synthese_comparaison` passe par le bloc
de comparaison des prix.
==============================================================================
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from core.conditions_mesure import (
    ConditionsDeMesure,
    phrase_conditions_de_mesure,
)
from core.prix_compares import (
    CAUSE_CRITERE,
    CAUSE_SANS_PRIX,
    Candidat,
    ResultatCandidat,
    synthese_comparaison,
)

_TOTALE = "N'EST DECLAREE DANS AUCUN PLAN"
_PARTIELLE = 'DECLARATION PARTIELLE DE LA DECOUPE'
_SANS_CAUSE = 'SANS CAUSE DECLAREE'


def _cond(agent: str, declaree: bool) -> ConditionsDeMesure:
    return ConditionsDeMesure(agent=agent, regle='aleatoire_graine_42',
                              n_train=800, n_test=200,
                              declaree_au_plan=declaree)


def _lignes(n_declarees: int) -> list:
    noms = ('A3', 'A4', 'A5')
    return [_cond(nom, i < n_declarees) for i, nom in enumerate(noms)]


def _ecarte(nom: str, cause: str) -> ResultatCandidat:
    return ResultatCandidat(candidat=Candidat(nom=nom, nature='prime_pure'),
                            k_train=1.0, niveau_holdout=0.5, ecarte=True,
                            motif='motif', cause=cause)


class TestLacuneSeDitJamaisSeDevine(unittest.TestCase):

    # ── LC-1 ─────────────────────────────────────────────────────────────
    def test_LC1_une_declaration_PARTIELLE_leve_sa_propre_alarme(self):
        """⚠️ TROIS ETATS, TROIS PHRASES. Le predicat d'origine n'en
        distinguait que deux, et le troisieme -- le plus frequent en
        pratique -- tombait du bon cote par accident."""
        vus = {}
        for n in (0, 1, 2, 3):
            t = phrase_conditions_de_mesure(_lignes(n))
            vus[n] = ('TOTALE' if _TOTALE in t
                      else 'PARTIELLE' if _PARTIELLE in t else 'aucune')
        self.assertEqual(
            vus, {0: 'TOTALE', 1: 'PARTIELLE', 2: 'PARTIELLE', 3: 'aucune'},
            f"les quatre etats ne rendent pas les bonnes alarmes : {vus}")
        print(f"    LC-1 SCEAU : {vus}")

    # ── LC-2 ─────────────────────────────────────────────────────────────
    def test_LC2_l_alarme_partielle_NOMME_les_agents_non_declares(self):
        """⚠️ UN COMPTE SANS SES NOMS N'EST PAS ACTIONNABLE : l'actuaire
        doit savoir POUR QUI declarer."""
        #: ⚠️⚠️ L'ASSIETTE EST L'ALARME, PAS LA PHRASE ENTIERE. Ma premiere
        #: version cherchait `A3`, `A4`, `A5` dans TOUT le texte : ils y
        #: figurent deja par le detail des decoupes, agent par agent. Un
        #: plant qui retirait les noms DE L'ALARME restait donc VERT.
        #: *Assiette trop large : le controle attestait la presence des
        #: noms sans surveiller la phrase qui doit les porter.*
        t = phrase_conditions_de_mesure(_lignes(1))
        debut = t.find(_PARTIELLE)
        self.assertGreaterEqual(
            debut, 0, "l'alarme partielle a disparu de la phrase")
        #: l'alarme va de son entete jusqu'a la fin de sa propre phrase
        alarme = t[debut:]
        fin = alarme.find('relancez')
        alarme = alarme[:fin] if fin > 0 else alarme
        for attendu in ('A3', 'A4', 'A5', 'decoupe_validation'):
            self.assertIn(
                attendu, alarme,
                f"l'ALARME PARTIELLE ne nomme pas {attendu!r} : "
                f"{alarme[:170]!r}")
        print(f"    LC-2 SCEAU : l'alarme partielle ({len(alarme)} car. sur "
              f"{len(t)}) nomme les 3 agents et la cle a declarer")

    # ── LC-3 ─────────────────────────────────────────────────────────────
    def test_LC3_SANS_lacune_les_phrases_ne_bougent_pas(self):
        """La contre-epreuve, pour les DEUX constats : le cas deja correct
        ne gagne aucune phrase."""
        t5 = phrase_conditions_de_mesure(_lignes(3))
        self.assertNotIn(_PARTIELLE, t5,
                         "une alarme partielle sort alors que TOUT est "
                         "declare")
        self.assertNotIn(_TOTALE, t5, "l'alarme totale sort a tort")
        t6 = synthese_comparaison([_ecarte('a', CAUSE_CRITERE),
                                   _ecarte('b', CAUSE_SANS_PRIX)])
        self.assertNotIn(
            _SANS_CAUSE, t6,
            "la mention « sans cause » sort alors que les deux causes sont "
            "declarees")
        print(f"    LC-3 SCEAU : 3/3 declarees -> {len(t5)} car. sans "
              f"alarme ; 2 causes nommees -> {len(t6)} car. sans mention")

    # ── LC-4 ─────────────────────────────────────────────────────────────
    def test_LC4_la_ventilation_RECONCILIE_avec_le_total_annonce(self):
        """⚠️⚠️ LE POINT DE FOND : le titre annonce N candidats, et la somme
        des seaux doit faire N. Un ecarte qui n'entre nulle part rend le
        document irreconciliable avec lui-meme."""
        import re
        cas = {
            'causes nommees': [_ecarte('a', CAUSE_CRITERE),
                               _ecarte('b', CAUSE_SANS_PRIX),
                               _ecarte('c', CAUSE_CRITERE)],
            'une cause vide': [_ecarte('a', CAUSE_CRITERE), _ecarte('b', '')],
            'toutes vides': [_ecarte('a', ''), _ecarte('b', '')],
        }
        vus = {}
        for etiq, lot in cas.items():
            t = synthese_comparaison(lot)
            m = re.search(r'COMPARAISON DE (\d+) CANDIDAT', t)
            self.assertTrue(m, f"le titre a change : {t[:80]!r}")
            total = int(m.group(1))
            seaux = sum(int(x) for x in re.findall(
                r'(\d+) (?:retenu|ecarte\(s\) par le critere|sans prix '
                r'publiable|ecarte\(s\) SANS CAUSE)', t))
            vus[etiq] = (total, seaux)
        ecarts = {k: v for k, v in vus.items() if v[0] != v[1]}
        self.assertEqual(
            ecarts, {},
            f"la ventilation ne reconcilie pas avec le total : {ecarts} "
            f"(total annonce, somme des seaux). Des candidats ecartes "
            f"n'entrent dans aucun compte.")
        print(f"    LC-4 SCEAU : {vus} -- total = somme des seaux partout")

    # ── LC-5 ─────────────────────────────────────────────────────────────
    def test_LC5_l_ecarte_sans_cause_est_NOMME_et_non_range_ailleurs(self):
        """⚠️ NI DANS UN SEAU EXISTANT, NI EN SILENCE. Le ranger avec les
        echecs de critere ferait lire une espece d'echec pour une autre --
        ce que ce module interdit deja pour les deux premieres."""
        t = synthese_comparaison([_ecarte('alpha', CAUSE_CRITERE),
                                  _ecarte('beta', '')])
        self.assertIn(_SANS_CAUSE, t, "la lacune n'est pas dite")
        self.assertIn('beta', t, "le candidat sans cause n'est pas nomme")
        self.assertIn(
            '1 ecarte(s) par le critere', t,
            "le candidat sans cause a ete range parmi les echecs de "
            "critere : une espece d'echec est lue pour une autre")
        print(f"    LC-5 SCEAU : la lacune est dite et NOMMEE "
              f"({len(t)} car.)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
