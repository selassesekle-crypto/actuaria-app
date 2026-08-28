"""Controle positif — `agents/C4` : `resume()` ne genere plus d'horodatage.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
LE CONSTAT. `ResultatAgents.resume()` faisait, l.157 :

    "date_calcul": datetime.now().isoformat()

Mesure d'origine, DEUX appels sur LE MEME OBJET :

    champs qui different : ['date_calcul']
      ('2026-08-24T16:14:00.384865', '2026-08-24T16:14:00.384929')

*Deux executions identiques produisaient deux livrables d'audit differents.*

⚠️ ET LES DEUX MODULES FRERES L'ECRIVENT NOIR SUR BLANC :
  `core/qualite_donnees`          << ne genere aucun horodatage -- reutilise
                                     celui fourni par l'appelant >>
  `core/conformite_reglementaire` << aucune date n'est generee ici : on
                                     reutilise >>
La convention de la maison etait deja ecrite ; seul ce module s'en ecartait.

⚠️⚠️ CE QUI N'EST PAS LE DEFAUT, ET C'EST UNE DISTINCTION DE FOND. Le run
capture bien un instant (`t0`, l.221) pour fabriquer `audit_id` : c'est
LEGITIME, il est pris UNE FOIS et transporte. Le defaut n'etait pas de lire
l'horloge -- c'etait de la relire A CHAQUE RENDU. Un livrable doit pouvoir se
re-rendre a l'identique ; un RUN, lui, a le droit d'avoir une date.

⚠️ ET LA DATE N'EST PAS DERIVEE DE `audit_id`, bien qu'il l'encode.
`audit_id` est une ETIQUETTE, faite pour etre lue. Lire une donnee dans une
etiquette est exactement le defaut que cet audit poursuit (cf. la decision
reglementaire qui lisait un emoji, `236dcf2`).
"""

from __future__ import annotations

import ast
import inspect
import re
import textwrap
import unicodedata
import unittest

from core.plan_tarifaire import Facteur, PlanTarifaire
from direction_non_vie.tarification import pipeline_agents as PA

#: Un plan MINIMAL, comme la preuve `audit_orchestrateur` -- on ne teste pas le
#: plan ici, on teste l'horodatage.
_PLAN = PlanTarifaire(lob='horodatage', exposition='expo',
                      cible_frequence='nb', cible_cout='cout',
                      facteurs=(Facteur('age', 'continu'),))


def _resultat(date: str = '2026-08-28T12:00:00+02:00') -> PA.ResultatAgents:
    """Un `ResultatAgents` minimal, sans lancer le pipeline."""
    vide = PA.ArbitrageCible(cible='x', a4=None, a5=None, a6=None,
                             statut_rag=None, n_candidats=0, erreur=None)
    return PA.ResultatAgents(
        plan=_PLAN, a1={}, a2={},
        a3={'success': True}, frequence=vide, cout=vide, prime_pure=vide,
        audit_id='AGENTS_20260828_120000', date_calcul=date)


class TestHorodatageAgents(unittest.TestCase):
    """Le livrable d'audit se re-rend a l'identique."""

    def test_deux_resume_sur_le_meme_objet_sont_identiques(self):
        """⚠️⚠️ LE TEST QUI FERME LE CONSTAT.

        C'est la mesure d'origine, rejouee : elle rendait deux dates.
        """
        r = _resultat()
        a, b = r.resume(), r.resume()
        differents = [c for c in a if a[c] != b[c]]
        self.assertEqual(
            differents, [],
            f"deux rendus du MEME objet different sur {differents} : le "
            f"livrable d'audit ne se re-rend pas a l'identique")
        self.assertEqual(a['date_calcul'], '2026-08-28T12:00:00+02:00')
        print("    OK C4-1 deux resume() du meme objet : identiques, "
              "date reutilisee")

    def test_resume_ne_lit_aucune_horloge(self):
        """⚠️ Controle par AST — la propriete, pas la valeur.

        Un test de valeur passerait si quelqu'un remettait un `now()` derriere
        un cache. On interdit l'APPEL a l'horloge dans le corps de `resume()`.
        """
        src = textwrap.dedent(
            unicodedata.normalize('NFC',
                                  inspect.getsource(PA.ResultatAgents.resume)))
        horloges = {'now', 'utcnow', 'today', 'time', 'time_ns', 'monotonic'}
        fautifs = [
            f'l.{n.lineno} {getattr(n.func, "attr", getattr(n.func, "id", "?"))}'
            for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.Call)
            and getattr(n.func, 'attr', getattr(n.func, 'id', '')) in horloges]
        self.assertEqual(
            fautifs, [],
            f"`resume()` lit une horloge : {fautifs}. Elle doit REUTILISER "
            f"l'instant du run, comme les deux modules freres.")
        print("    OK C4-2 `resume()` n'appelle aucune horloge (AST)")

    def test_le_champ_est_REQUIS(self):
        """⚠️⚠️ SECOND SENS — un defaut laisserait publier un vide.

        `''` ou `None` par defaut, et un site de construction pourrait omettre
        la date en silence. *« Present mais VIDE » a deja morde trois fois dans
        cet audit.*
        """
        vide = PA.ArbitrageCible(cible='x', a4=None, a5=None, a6=None,
                                 statut_rag=None, n_candidats=0, erreur=None)
        with self.assertRaises(TypeError):
            PA.ResultatAgents(                       # type: ignore[call-arg]
                plan=_PLAN, a1={}, a2={},
                a3={'success': True}, frequence=vide, cout=vide,
                prime_pure=vide, audit_id='X')
        print("    OK C4-3 omettre `date_calcul` LEVE : aucun vide publiable")

    def test_le_run_capture_un_seul_instant_pour_les_deux(self):
        """⚠️ `audit_id` et `date_calcul` doivent decrire LE MEME instant.

        Deux horloges lues separement donneraient deux verites sur un seul run.
        On lit la SOURCE : un seul `datetime.now()`, et les deux en derivent.
        """
        src = unicodedata.normalize('NFC', inspect.getsource(PA))
        corps = src.split('def pipeline_agents(', 1)[1]
        self.assertEqual(
            len(re.findall(r'datetime\.now\(', corps)), 1,
            "le run lit l'horloge plus d'une fois : `audit_id` et "
            "`date_calcul` pourraient decrire deux instants")
        self.assertIn('t0.strftime', corps)
        self.assertIn('t0.isoformat()', corps)
        print("    OK C4-4 un seul appel a l'horloge dans le run, les deux "
              "grandeurs en derivent")

    def test_la_date_reste_une_VRAIE_date_du_run(self):
        """⚠️⚠️ SECOND SENS — corriger ne doit pas figer la date.

        Un correctif qui remplacerait l'horodatage par une constante fermerait
        le constat en detruisant l'information. La date doit rester celle du
        RUN : deux objets construits a des instants differents la portent
        differente.
        """
        a = _resultat('2026-08-28T12:00:00+02:00').resume()
        b = _resultat('2026-08-28T13:30:00+02:00').resume()
        self.assertNotEqual(
            a['date_calcul'], b['date_calcul'],
            "la date ne varie plus d'un run a l'autre : elle a ete figee")
        self.assertIn('date_calcul', a)
        print("    OK C4-5 deux runs distincts portent deux dates : "
              "l'information n'est pas detruite")


if __name__ == '__main__':
    unittest.main()
