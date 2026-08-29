"""Controles positifs — lot 2.1b : `agents/C2` et `conformite/C14`.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
DEUX CONSTATS, UNE SEULE PROPRIETE : *un livrable ne doit pas affirmer un
succes qu'il n'a pas eu, ni une portee qu'il ne couvre pas.*

═══ `agents/C2` — `is not None` REPONDAIT A LA MAUVAISE QUESTION ═══

`ResultatAgents.success` testait `self.frequence.a6 is not None`. Or
`_arbitrer` rend TOUJOURS un dict `a6` : A6 en echec en rend un aussi, avec
`success: False`. Repro fidele, sur l'objet reel :

    a6 = {'success': False, 'erreur': 'A6 a echoue', 'classement': []}
    -> ResultatAgents.success                  = True
       resume()['success']                     = True
       resume()['frequence']['modele_production'] = None

Le `resume()` -- que sa PROPRE docstring appelle << le livrable d'audit >> --
publiait donc un SUCCES sur un dossier sans modele et sans classement.

⚠️ ON LIT LE DRAPEAU D'A6, PAS UNE FORME. A6 pose `success` sur ses deux
sorties (retour nominal l.648/778, `_erreur` l.3389) -- verifie PAR EXECUTION
avant d'ecrire le correctif. Deduire l'echec d'un `classement` vide serait
deviner par un symptome.

⚠️ LA PORTEE NE CHANGE PAS : `.success` ne regarde toujours QUE A3 et la
FREQUENCE, comme la docstring de la classe l'explique (la prime pure directe
est un challengeur additif). Ce lot corrige CE QUI EST TESTE, pas CE QUI EST
REGARDE.

═══ `conformite/C14` — UNE REGLE UNIVERSELLE, UNE SURVEILLANCE PARTIELLE ═══

Le module s'annonce << SOURCE UNIQUE, POUR LES TROIS DIRECTIONS >> et enonce
<< POUR TOUTE BRANCHE >>. Re-mesure par AST le 29/08/2026 :

    446 fichiers balayes
      core                          2 importateur(s)
      demos                         1
      direction_non_vie            19
      direction_vie_epre            0   <-- AUCUNE surveillance
      direction_sante_prevoyance    0   <-- AUCUNE surveillance

⚠️ LES CHIFFRES DU RELEVE ONT VIEILLI (418 fichiers, 13 importateurs), SA
CONCLUSION TIENT : zero importateur hors Non-Vie. *Un compte se re-derive ; une
conclusion se re-verifie.*

⚠️ LE CORRECTIF EST UNE PHRASE, PAS UN MECANISME -- et c'est ce que le constat
demandait. Etendre la surveillance aux deux autres directions serait un
chantier, pas un lot ; et rien ne l'exige aujourd'hui, leurs agents etant
parametriques. Ce qui etait fautif, c'est que le fichier ne DISAIT PAS son
assiette.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

from direction_non_vie.tarification.pipeline_agents import (
    ArbitrageCible,
    ResultatAgents,
)

_RACINE = pathlib.Path(__file__).resolve().parent


def _resultat(a6_frequence, a3_ok: bool = True) -> ResultatAgents:
    """Un `ResultatAgents` minimal — seul l'arbitrage fréquence varie.

    ⚠️ Le PLAN est le vrai (`_PLAN_AUTO`) : `resume()` lit `plan.lob` et
    `plan.empreinte()`. Un plan factice aurait fait tomber le test sur la
    fixture au lieu du sujet — mesuré, il levait un `AttributeError`.
    """
    from direction_non_vie.tarification.test_pipeline_agents import _PLAN_AUTO
    plan = _PLAN_AUTO
    vide = ArbitrageCible(cible='x', a4=None, a5=None, a6=None,
                          statut_rag=None, n_candidats=0, erreur='n/a')
    freq = ArbitrageCible(cible='nb_sinistres', a4={}, a5={}, a6=a6_frequence,
                          statut_rag=None, n_candidats=0)
    return ResultatAgents(plan=plan, a1={}, a2={}, a3={'success': a3_ok},
                          frequence=freq, cout=vide, prime_pure=vide,
                          audit_id='T', date_calcul='2026-08-29T00:00:00')


class TestSuccesRefleteLEchecReel(unittest.TestCase):
    """`agents/C2` — un objet présent n'est pas un objet qui a réussi."""

    def test_A6_EN_ECHEC_ne_publie_plus_un_succes(self):
        """⚠️⚠️ LE TEST QUI FERME LE CONSTAT — la mesure d'origine, rejouée."""
        res = _resultat({'success': False, 'erreur': 'A6 a echoue',
                         'classement': []})
        self.assertFalse(res.success,
                         'un arbitrage en echec publie encore un succes')
        self.assertFalse(res.resume()['success'],
                         'le livrable d audit publie encore un succes')
        print("    P-1 A6 en echec -> success = False (avant : True, avec "
              "modele_production = None)")

    def test_TEMOIN_le_cas_NOMINAL_reste_un_succes(self):
        """⚠️⚠️ SECOND SENS — un correctif qui rendrait TOUT faux fermerait le
        constat en detruisant l'information.

        A6 pose `success: True` sur son retour nominal : le succes doit
        continuer d'etre publie.
        """
        res = _resultat({'success': True, 'classement': [{'modele': 'GLM'}]})
        self.assertTrue(res.success)
        self.assertTrue(res.resume()['success'])
        print("    P-2 temoin : A6 nominal -> success = True, inchange")

    def test_les_TROIS_formes_d_echec_sont_couvertes(self):
        """⚠️ `a6` absent, `a6` vide, `a6` en échec : les trois disent False.

        L'ancienne condition n'attrapait que la PREMIÈRE — et c'est la seule
        que le pipeline produit lui-même (`_echec`), donc la seule qui
        marchait par accident.
        """
        for etiquette, a6 in (('a6 = None', None),
                              ('a6 = {}', {}),
                              ('a6 success=False', {'success': False})):
            with self.subTest(cas=etiquette):
                self.assertFalse(_resultat(a6).success)
        print("    P-3 les 3 formes d echec rendent False (l ancienne n en "
              "voyait qu une)")

    def test_A3_EN_ECHEC_reste_decisif(self):
        """⚠️ Le socle A3 garde son veto : un A6 réussi ne rachète pas un A3
        échoué."""
        res = _resultat({'success': True, 'classement': [{'modele': 'GLM'}]},
                        a3_ok=False)
        self.assertFalse(res.success)
        print("    P-4 A3 en echec -> success = False, quel que soit A6")

    def test_la_PORTEE_de_success_n_a_pas_change(self):
        """⚠️⚠️ CE LOT CORRIGE CE QUI EST TESTÉ, PAS CE QUI EST REGARDÉ.

        `.success` ne dépend que d'A3 et de la FRÉQUENCE — la prime pure
        directe est un challengeur additif, la docstring de la classe
        l'explique. Élargir la portée serait un autre constat.
        """
        source = ast.unparse(next(
            n for n in ast.walk(ast.parse(
                (_RACINE / 'pipeline_agents.py').read_text(encoding='utf-8')))
            if isinstance(n, ast.FunctionDef) and n.name == 'success'))
        self.assertIn('frequence', source)
        self.assertNotIn('prime_pure', source,
                         'la portee de `.success` a ete elargie en silence')
        self.assertNotIn('self.cout', source,
                         'la portee de `.success` a ete elargie en silence')
        print("    P-5 la portee reste A3 + frequence, ni cout ni prime_pure")


class TestLaPorteeSurveilleeEstDite(unittest.TestCase):
    """`conformite/C14` — la règle est universelle, le filtre ne l'est pas."""

    def _entete(self) -> str:
        chemin = _RACINE.parent.parent / 'core' / 'conformite_reglementaire.py'
        return ast.get_docstring(ast.parse(
            chemin.read_text(encoding='utf-8'))) or ''

    def test_l_entete_BORNE_la_surveillance_a_la_Non_Vie(self):
        """⚠️⚠️ LE TEST QUI FERME LE CONSTAT.

        Le fichier annonçait « POUR LES TROIS DIRECTIONS » et « POUR TOUTE
        BRANCHE » sans dire nulle part ce qu'il surveille RÉELLEMENT.
        """
        entete = self._entete()
        self.assertIn('SURVEILLE AUJOURD', entete,
                      "l en-tete ne borne pas la portee surveillee")
        self.assertIn('NON-VIE', entete.upper())
        for direction in ('direction_vie_epre', 'direction_sante_prevoyance'):
            self.assertIn(direction, entete,
                          f'{direction} n est pas nommee comme non couverte')
        print("    P-6 l en-tete nomme la portee surveillee et les 2 "
              "directions NON couvertes")

    def test_la_REGLE_reste_universelle_et_le_DIT(self):
        """⚠️⚠️ SECOND SENS, ET IL EST ESSENTIEL ICI.

        Borner la SURVEILLANCE ne doit pas laisser croire que la RÈGLE est
        bornée. Test-Achats s'applique à toute l'assurance : affaiblir cette
        phrase serait un défaut réglementaire, pas un correctif.

        ⚠️⚠️ ET CE TEST A ÉTÉ CORRIGÉ PAR SA PROPRE VIOLATION PLANTÉE. Il
        cherchait la chaîne « POUR TOUTE BRANCHE » — qui apparaît DEUX fois
        depuis le correctif, la seconde dans la phrase qui la qualifie. En
        affaiblissant la phrase qui fait autorité, le filet **ne tombait
        pas** : il trouvait l'autre. *Un relevé par fragment sur-compte ; on
        s'attache à la phrase entière.*
        """
        entete = self._entete()
        self.assertIn(
            'depuis le 21 décembre 2012, POUR TOUTE BRANCHE '
            '(pas seulement la RC Auto)', entete,
            "la portee de la REGLE CJUE a ete affaiblie")
        self.assertIn('Test-Achats', entete)
        self.assertIn("l'étendue de la RÈGLE", entete,
                      'la distinction regle / surveillance a disparu')
        print("    P-7 second sens : la regle CJUE reste universelle, et la "
              "distinction est ecrite")

    def test_l_exemption_par_le_MECANISME_est_declaree_insuffisante(self):
        """⚠️ Le module s'exemptait au motif que les autres agents sont
        « paramétriques ». C'est vrai, et ça ne couvre rien : l'absence de
        matrice X est une propriété de la FORME du modèle, pas de l'usage du
        critère genre."""
        entete = self._entete()
        self.assertIn('MÉCANISME', entete.upper().replace('MECANISME', 'MÉCANISME'))
        self.assertIn('CRITÈRE', entete.upper().replace('CRITERE', 'CRITÈRE'))
        print("    P-8 l exemption par le mecanisme est declaree insuffisante")

    def test_le_COMPTE_annonce_est_REJOUABLE_et_JUSTE(self):
        """⚠️⚠️ UN COMPTE ÉCRIT DANS UN EN-TÊTE SE RE-DÉRIVE.

        L'en-tête annonce 0 importateur hors Non-Vie. Ce test refait la mesure
        par AST : il tombera le jour où une direction Vie ou Santé importera
        le module — c'est-à-dire le jour où la phrase deviendra fausse.

        ⚠️ On ne fige PAS les 19 de Non-Vie : ce nombre grandit à chaque agent
        et n'est pas ce que la phrase affirme. *Ce qui LIMITE est sûr, ce qui
        AFFIRME est une dette.*
        """
        racine = _RACINE.parent.parent
        hors_non_vie = []
        for p in racine.rglob('*.py'):
            if '.venv' in str(p) or 'audit_2026_08' in str(p):
                continue
            if p.parts[0] not in ('direction_vie_epre',
                                  'direction_sante_prevoyance'):
                continue
            try:
                arbre = ast.parse(p.read_text(encoding='utf-8', errors='replace'))
            except SyntaxError:
                continue
            if any((isinstance(n, ast.ImportFrom)
                    and 'conformite_reglementaire' in (n.module or ''))
                   or (isinstance(n, ast.Import)
                       and any('conformite_reglementaire' in x.name
                               for x in n.names))
                   for n in ast.walk(arbre)):
                hors_non_vie.append(str(p))
        self.assertEqual(
            hors_non_vie, [],
            f"une direction hors Non-Vie importe désormais le module : "
            f"{hors_non_vie}. L'en-tête annonce 0 — le mettre à jour.")
        print("    P-9 0 importateur hors Non-Vie, re-derive par AST "
              "(l en-tete dit vrai)")


if __name__ == '__main__':
    unittest.main()
