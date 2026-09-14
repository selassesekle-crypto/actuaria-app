r"""
==============================================================================
  LE PDF NE PEUT PAS AFFIRMER UNE ABSENCE SUR UNE PRESENCE
==============================================================================

⚠️⚠️ `RMT-D1` -- `export_pdf` N'ACCEPTAIT AUCUN DES CINQ BLOCS que
`export_html` accepte : ni `tarif`, ni `portefeuille`, ni
`decision_actuaire`, ni `comparaison_prix`, ni `conditions_mesure`. Elle
ne les transmettait donc pas, et le PDF publiait

    << AUCUNE DECISION D'ACTUAIRE ENREGISTREE (verdict du systeme : AMBRE) >>

sur une decision `PASSE_OUTRE` MOTIVEE, remise aux deux autres formats.
*Le bloc de decision est le seul que ce module declare ne devoir jamais
se taire, et le PDF en affirmait l'absence.*

Mesure du 14/09/2026, l'HTML tel que `export_pdf` le demandait, contre
l'HTML complet, memes donnees :

    complet   19 242 car. | << aucune decision >> x0 | PASSE_OUTRE x1
              | motif x1 | signataire x1
    demande   19 008 car. | << aucune decision >> x1 | PASSE_OUTRE x0
              | motif x0 | signataire x0

⚠️⚠️ CE QUI EST VIVANT, ET CE QUI NE L'EST PAS -- et je le dis plutot
que de l'enfler. Sur l'orchestrateur, `html_str` est construit AVEC les
cinq blocs des que `'pdf' in formats` (l.3914), et le PDF en est le
rendu : le repli qui appelle `export_pdf` n'est atteint que si
`export_html` a deja rendu `''`. Le defaut est donc LATENT par cette
porte. Il est VIVANT par l'autre : `services/__init__.py` reexporte
`export_pdf` publiquement, et un appelant direct perdait les cinq blocs.

⚠️ ET LE REPLI PERDAIT AUSSI LE SIGNATAIRE. `actuaire_nom` et
`actuaire_numero_ia` sont en 8e et 9e position ; l'appel du repli
s'arretait a la 7e. Un PDF produit par ce chemin sortait NON SIGNE.

⚠️⚠️ WEASYPRINT EST ABSENT DE CET ENVIRONNEMENT, et `export_pdf`
l'importe en PREMIERE instruction : sans doublure, elle rend `b''` sans
jamais atteindre `export_html`, et ce sceau ne mesurerait RIEN. On
injecte donc un rendu de PDF factice qui CAPTURE la chaine HTML -- le
code du depot, lui, n'est pas touche. *Une sonde qui ne peut pas
atteindre le site qu'elle surveille est un controle qui atteste.*

⚠️ LAISSE OUVERT ET NOMME : `export_pdf_equipe` porte la MEME classe de
defaut -- 4 parametres contre 5 a `export_html_equipe`, `syntheses`
manquant. Ce n'est pas le constat de l'auditeur et il n'est pas traite
ici ; `PD-5` le MESURE et publie son etat sans le fermer.
==============================================================================
"""
from __future__ import annotations

import ast
import logging
import os
import pathlib
import re
import sys
import types
import unittest
import warnings

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from direction_non_vie.tarification.services import rapport_modeles_tarif as RM

_SOURCE = (_RACINE / 'direction_non_vie' / 'tarification' / 'services'
           / 'rapport_modeles_tarif.py')
_JUMEAU = (_RACINE / 'direction_non_vie' / 'tarification' / 'services'
           / 'rapport_equipe_tarif.py')

_R3 = {'success': True, 'statut_rag': 'VERT', 'metriques': {}}
_R6 = {'success': True, 'statut_rag': 'VERT',
       'modele_production': {'nom': 'xgboost'}}
_MOTIF = ("le classement recommande un modele que l'actuaire ecarte : "
          "sur-apprentissage mesure a 2,757.")
_DECISION = {'verdict_systeme': 'AMBRE', 'decision': 'PASSE_OUTRE',
             'decide_par': 'Direction Technique', 'decide_le': '2026-09-14',
             'motif': _MOTIF}
_ABSENCE = re.compile(r'(?i)aucune.{0,3}d.cision')


class _Capture:
    """La doublure de weasyprint : elle retient l'HTML au lieu d'imprimer."""

    dernier = None

    def __init__(self, string=''):
        _Capture.dernier = string

    def write_pdf(self, cible):
        cible.write(b'%PDF-1.4 doublure de test')


def _parametres(chemin, nom):
    for n in ast.parse(chemin.read_bytes().decode('utf-8')).body:
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return ([x.arg for x in n.args.posonlyargs]
                    + [x.arg for x in n.args.args]
                    + [x.arg for x in n.args.kwonlyargs])
    raise AssertionError(f"`{nom}` introuvable dans {chemin.name}")


def _pdf_avec(**kw) -> str:
    """Lance le VRAI `export_pdf` derriere la doublure, rend l'HTML capte."""
    faux = types.ModuleType('weasyprint')
    faux.HTML = _Capture
    ancien = sys.modules.get('weasyprint')
    sys.modules['weasyprint'] = faux
    _Capture.dernier = None
    try:
        octets = RM.export_pdf(
            _R3, None, _R6, '', '2026-09-14', 'RMTD1', None,
            'Direction Technique', 'IA-0001', result_a5=None, **kw)
    finally:
        if ancien is None:
            sys.modules.pop('weasyprint', None)
        else:
            sys.modules['weasyprint'] = ancien
    assert octets, "la doublure n'a pas produit d'octets : sonde cassee"
    return _Capture.dernier or ''


class TestPdfPorteLaDecision(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._journal = logging.getLogger()
        cls._niveau = cls._journal.level
        cls._journal.setLevel(logging.CRITICAL)
        warnings.filterwarnings('ignore')

    @classmethod
    def tearDownClass(cls):
        cls._journal.setLevel(cls._niveau)

    # ── PD-1 ─────────────────────────────────────────────────────────────
    def test_PD1_export_pdf_accepte_TOUT_ce_que_export_html_accepte(self):
        """⚠️ LE RELEVE PORTE SUR LA FORME : une difference de signature,
        pas une liste de cinq noms. Un sixieme bloc ajoute demain a
        `export_html` et oublie ici ferait exactement le meme degat."""
        html = _parametres(_SOURCE, 'export_html')
        pdf = _parametres(_SOURCE, 'export_pdf')
        manquants = [x for x in html if x not in pdf]
        self.assertEqual(
            manquants, [],
            f"`export_pdf` n'accepte pas {manquants}, que `export_html` "
            f"accepte : ces blocs ne peuvent pas atteindre le PDF. Le bloc "
            f"de decision est le seul que ce module declare ne devoir jamais "
            f"se taire.")
        print(f"    PD-1 SCEAU : export_html {len(html)} params, export_pdf "
              f"{len(pdf)}, 0 manquant")

    # ── PD-2 ─────────────────────────────────────────────────────────────
    def test_PD2_le_PDF_porte_la_decision_son_motif_et_le_signataire(self):
        """⚠️⚠️ LA MESURE EST SUR L'HTML QUI ATTEINT WEASYPRINT, pas sur la
        signature : c'est la seule qui prouve que le bloc VOYAGE."""
        html = _pdf_avec(decision_actuaire=_DECISION)
        self.assertTrue(html, "la doublure n'a capte aucun HTML")
        absences = _ABSENCE.findall(html)
        self.assertEqual(
            absences, [],
            f"le PDF affirme encore une absence de decision ({absences}) "
            f"alors qu'une decision PASSE_OUTRE motivee lui est remise.")
        for attendu, quoi in ((_DECISION['decision'], 'la decision'),
                              (_MOTIF[:44], 'le motif'),
                              ('IA-0001', 'le numero du signataire')):
            self.assertIn(
                attendu, html,
                f"{quoi} n'atteint pas le PDF ({len(html)} car. captes).")
        print(f"    PD-2 SCEAU : {len(html)} car. captes, 0 << aucune "
              f"decision >>, decision + motif + signataire presents")

    # ── PD-3 ─────────────────────────────────────────────────────────────
    def test_PD3_SANS_decision_le_PDF_est_ce_qu_il_etait(self):
        """La contre-epreuve : le cas deja correct ne bouge pas. ⚠️ Et le
        document DIT l'absence quand elle est REELLE -- on ne remplace pas
        une affirmation fausse par un silence."""
        html = _pdf_avec()
        self.assertEqual(
            len(_ABSENCE.findall(html)), 1,
            f"sans decision remise, le PDF ne dit plus l'absence : "
            f"{_ABSENCE.findall(html)}. Un bloc qui ne se tait jamais doit "
            f"aussi parler quand il n'y a rien.")
        self.assertNotIn(
            _DECISION['decision'], html,
            "une decision apparait alors qu'aucune n'a ete remise")
        print(f"    PD-3 SCEAU : sans decision -> l'absence est DITE une "
              f"fois, 0 decision inventee ({len(html)} car.)")

    # ── PD-4 ─────────────────────────────────────────────────────────────
    def test_PD4_le_REPLI_de_l_orchestrateur_a_le_meme_contrat(self):
        """⚠️⚠️ UN REPLI QUI N'A PAS LE CONTRAT DE SA PORTE PRINCIPALE EST
        UN SECOND DOCUMENT. Le releve est par AST sur les DEUX appels de
        l'orchestrateur -- celui qui construit `html_str` et celui du repli
        -- et compare ce qu'ils transmettent."""
        arbre = ast.parse(_SOURCE.read_bytes().decode('utf-8'))
        orch = next(n for n in arbre.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'generer_rapport_tarification')
        appels = {}
        for n in ast.walk(orch):
            if isinstance(n, ast.Call):
                cible = ast.unparse(n.func)
                if cible in ('export_html', 'export_pdf'):
                    appels[cible] = (
                        len(n.args),
                        sorted(k.arg for k in n.keywords if k.arg))
        self.assertEqual(
            sorted(appels), ['export_html', 'export_pdf'],
            f"l'assiette de ce controle a change : {sorted(appels)}")
        n_h, mots_h = appels['export_html']
        n_p, mots_p = appels['export_pdf']
        manquants = [x for x in mots_h if x not in mots_p]
        self.assertEqual(
            manquants, [],
            f"le repli PDF de l'orchestrateur ne transmet pas {manquants}, "
            f"que la porte principale transmet.")
        self.assertGreaterEqual(
            n_p, n_h,
            f"le repli PDF passe {n_p} arguments positionnels contre {n_h} "
            f"a la porte principale : `actuaire_nom` et `actuaire_numero_ia` "
            f"sont en 8e et 9e position, un PDF produit par ce chemin "
            f"sortirait NON SIGNE.")
        print(f"    PD-4 SCEAU : porte {n_h}+{len(mots_h)} / repli "
              f"{n_p}+{len(mots_p)}, 0 manquant")

    # ── PD-5 ─────────────────────────────────────────────────────────────
    def test_PD5_LE_JUMEAU_equipe_porte_la_meme_classe_et_on_le_DIT(self):
        """⚠️ CE CONTROLE NE FERME RIEN : il MESURE et PUBLIE un constat
        laisse ouvert. `export_pdf_equipe` n'accepte pas `syntheses`, que
        `export_html_equipe` accepte. Le jour ou quelqu'un le corrige, ce
        controle le dira -- et le jour ou l'ecart s'AGGRAVE, il mord."""
        html = _parametres(_JUMEAU, 'export_html_equipe')
        pdf = _parametres(_JUMEAU, 'export_pdf_equipe')
        manquants = [x for x in html if x not in pdf]
        self.assertLessEqual(
            len(manquants), 1,
            f"l'ecart du jumeau s'est AGGRAVE : {manquants}. Il valait un "
            f"seul parametre (`syntheses`) au 14/09/2026.")
        print(f"    PD-5 RELEVE (non ferme) : export_pdf_equipe manque "
              f"{manquants or 'rien'} -- constat NOMME, hors perimetre de "
              f"`RMT-D1`")


if __name__ == '__main__':
    unittest.main(verbosity=2)
