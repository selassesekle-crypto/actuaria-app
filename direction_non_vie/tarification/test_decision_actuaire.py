"""
==============================================================================
  CHANTIER A -- CE N'EST JAMAIS L'ACCORD QU'IL FAUT ENREGISTRER
==============================================================================

⚠️⚠️ CE QUE CE CHANTIER FERME. Le depot produit un verdict (`statut_rag` :
VERT, AMBRE, ROUGE), publie des reserves d'arbitrage, et fait signer un
actuaire nomme. **Il n'enregistrait nulle part ce que cet actuaire a DECIDE de
ce verdict.**

  Mesure du 08/09/2026 : `fiche_decision` est une AIDE -- << questions a poser
  avant signature >> --, et la seule decision humaine tracee est
  `profil_valide_par`, qui valide un profil de ponderation, pas un tarif.

  *Un journal ou l'actuaire suit toujours la recommandation ne prouve rien.
  Ce qu'un controleur cherche, c'est la fois ou il ne l'a pas suivie.*

LA REGLE
  Un DESACCORD sans motif est REFUSE. Un ACCORD n'en demande aucun -- exiger
  un motif partout ferait ecrire << RAS >> mille fois, et le jour ou il compte
  personne ne le lirait.

⚠️⚠️ ET L'ABSENCE DE DECISION N'EST PAS UN ACCORD. Sans decision enregistree,
le document ecrit << aucune decision d'actuaire enregistree >> -- jamais
<< l'actuaire a suivi >>. C'est le defaut `... else "VERT"` que ce chantier a
deja trouve cinq fois : un statut par defaut qui certifie ce qu'il n'a pas
regarde.

⚠️ SEULE SECTION DU RAPPORT QUI NE SE TAIT JAMAIS. Toutes les autres se
taisent quand elles n'ont rien a dire, pour ne pas devenir un avertissement
permanent qu'on cesse de lire. Celle-ci fait l'inverse : un document
SILENCIEUX sur la decision se lit comme un accord.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys
import unittest

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from core.charts_tarif import STATUT_RAG
from core.decision_actuaire import (
    ACCORD,
    DECISIONS_ADMISES,
    PASSE_OUTRE,
    REFUS,
    STATUTS_ADMIS,
    TITRE_DECISION,
    DecisionActuaire,
    decision_depuis_dict,
    divergence,
    synthese_decision,
)
from direction_non_vie.tarification.services.rapport_modeles_tarif import (
    _bloc_decision_html,
)

#: ⚠️⚠️ UN ROLE, JAMAIS UNE PERSONNE -- ET C'EST UNE REGLE DU DEPOT, PAS UN
#: gout de redaction. `decide_par` PEUT porter un nom : il vit dans le contexte
#: de run, qui n'est jamais versionne. Cette fixture-ci, elle, EST versionnee
#: dans un depot PUBLIC : un nom y serait une donnee personnelle publiee.
#:   *Ma premiere version portait un nom reel. Le scan d'avant-poussee l'a
#:   trouve -- c'est exactement ce pour quoi ce scan existe.*
_QUI, _QUAND = 'actuaire signataire (role)', '2026-09-08'


def _d(verdict, decision, motif=''):
    return DecisionActuaire(verdict, decision, _QUI, _QUAND, motif)


# ═════════════════════════════════════════════════════════════════════════════
#  LE DESACCORD EXIGE UN MOTIF, L'ACCORD N'EN DEMANDE AUCUN
# ═════════════════════════════════════════════════════════════════════════════
class TestLeDesaccordExigeUnMotif(unittest.TestCase):

    def test_DA1_LE_SCEAU_un_desaccord_SANS_motif_est_REFUSE(self):
        """⚠️⚠️ LE CONTROLE CENTRAL. Passer outre un verdict defavorable est une
        decision LEGITIME -- c'est l'actuaire qui signe, pas le systeme. Mais
        elle engage, et une decision qui engage sans dire pourquoi n'est pas
        opposable devant un controleur."""
        for verdict, decision in (('AMBRE', PASSE_OUTRE),
                                  ('ROUGE', PASSE_OUTRE),
                                  ('VERT', REFUS)):
            with self.subTest(verdict=verdict, decision=decision):
                with self.assertRaises(ValueError) as ctx:
                    _d(verdict, decision)
                msg = str(ctx.exception)
                self.assertIn('motif', msg.lower())
                self.assertIn(decision, msg)
        print("    DA-1 SCEAU : les trois formes de desaccord exigent un motif")

    def test_DA2_LE_MIROIR_un_ACCORD_ne_demande_AUCUN_motif(self):
        """⚠️⚠️ SANS CE SENS, UN GARDE QUI EXIGERAIT UN MOTIF PARTOUT PASSERAIT
        DA-1. *Exiger un motif partout ferait ecrire << RAS >> mille fois, et
        le jour ou il compte vraiment personne ne le lirait.*"""
        for verdict in STATUTS_ADMIS:
            with self.subTest(verdict=verdict):
                d = _d(verdict, ACCORD)
                self.assertFalse(divergence(d))
                self.assertEqual(d.motif, '')
        print(f"    DA-2 accord admis sans motif sur les {len(STATUTS_ADMIS)} "
              f"verdicts")

    def test_DA3_un_desaccord_AVEC_motif_est_admis(self):
        """⚠️ Le systeme n'a pas le dernier mot : il enregistre, il ne bloque
        pas. *L'actuaire decide, le systeme assiste, jamais l'inverse.*"""
        d = _d('ROUGE', PASSE_OUTRE, 'segment jeune conducteur retarife a la '
                                     'main sur le tarif de reassurance')
        self.assertTrue(divergence(d))
        self.assertIn('reassurance', synthese_decision(d))
        print("    DA-3 desaccord motive : ADMIS, et le motif est publie")

    def test_DA4_qui_et_quand_sont_OBLIGATOIRES(self):
        """⚠️ Une decision que personne ne signe et qu'aucune date ne situe
        n'est pas opposable -- meme sur un accord."""
        for champ, valeurs in (('decide_par', ('', '   ')),
                               ('decide_le', ('', '  '))):
            for mauvais in valeurs:
                with self.subTest(champ=champ, valeur=repr(mauvais)):
                    kw = {'verdict_systeme': 'VERT', 'decision': ACCORD,
                          'decide_par': _QUI, 'decide_le': _QUAND}
                    kw[champ] = mauvais
                    with self.assertRaises(ValueError) as ctx:
                        DecisionActuaire(**kw)
                    self.assertIn(champ, str(ctx.exception))
        print("    DA-4 signataire et date obligatoires, meme sur un accord")


# ═════════════════════════════════════════════════════════════════════════════
#  L'ABSENCE DE DECISION N'EST PAS UN ACCORD
# ═════════════════════════════════════════════════════════════════════════════
class TestLAbsenceNEstPasUnAccord(unittest.TestCase):

    def test_DA5_LE_SCEAU_aucune_decision_ne_se_lit_PAS_comme_un_accord(self):
        """⚠️⚠️ LE DEFAUT `... else "VERT"`, SOUS SA FORME LA PLUS CHERE. Un
        document muet sur la decision de l'actuaire se lit comme un accord. Ce
        module distingue les deux, et le texte publie le dit explicitement."""
        phrase = synthese_decision(None, 'ROUGE')
        self.assertIn('AUCUNE DECISION', phrase.upper())
        self.assertIn('ROUGE', phrase, "le verdict doit rester visible")
        self.assertIn('ne dit pas que', phrase.lower(),
                      "le texte doit NIER l'interpretation << accord >>, pas "
                      "seulement s'abstenir")
        self.assertNotIn('SUIT', phrase.upper())
        self.assertFalse(divergence(None))
        print("    DA-5 SCEAU : l'absence est DITE, et elle nie l'accord")

    def test_DA6_les_TROIS_etats_produisent_TROIS_textes_distincts(self):
        """⚠️ Deux etats qui rendraient le meme texte seraient indiscernables
        pour le lecteur du document signe."""
        textes = {
            'aucune': synthese_decision(None, 'AMBRE'),
            'accord': synthese_decision(_d('AMBRE', ACCORD)),
            'desaccord': synthese_decision(
                _d('AMBRE', PASSE_OUTRE, 'motif declare')),
        }
        self.assertEqual(len(set(textes.values())), 3, textes)
        self.assertIn('SUIT', textes['accord'].upper())
        self.assertIn('DESACCORD', textes['desaccord'].upper())
        print("    DA-6 trois etats, trois textes")

    def test_DA7_le_bloc_ne_se_tait_JAMAIS(self):
        """⚠️⚠️ SEULE SECTION DU RAPPORT DANS CE CAS, ET C'EST DELIBERE. Les
        autres se taisent pour ne pas devenir un avertissement permanent ;
        celle-ci s'affiche meme sans decision, parce que le silence se lirait
        comme un accord."""
        for etat, phrase in (
                ('aucune', synthese_decision(None, 'ROUGE')),
                ('accord', synthese_decision(_d('VERT', ACCORD))),
                ('desaccord', synthese_decision(
                    _d('ROUGE', PASSE_OUTRE, 'motif')))):
            with self.subTest(etat=etat):
                html = _bloc_decision_html(phrase, etat == 'desaccord')
                self.assertTrue(html, "le bloc s'est tu")
                self.assertIn(TITRE_DECISION, html)
        print("    DA-7 le bloc s'affiche dans les TROIS etats")

    def test_DA8_le_DESACCORD_est_marque_dans_le_TITRE_du_bloc(self):
        """⚠️ Une couleur n'est pas une information : un document imprime en
        noir et blanc, ou lu par un outil, doit porter l'ecart.

        ⚠️⚠️ CE CONTROLE ATTESTAIT SANS SURVEILLER, et le sceau l'a trouve. Il
        cherchait << DESACCORD >> n'importe ou dans le bloc — et le mot y est
        DEJA, dans la phrase que `synthese_decision` redige. Le plant qui
        retirait le marqueur du TITRE le laissait donc VERT : il verifiait le
        travail d'une autre fonction en croyant verifier celui-ci.
          *La question a poser a tout garde-fou : sur quelle assiette ?* Ici,
        l'assiette est la LIGNE DE TITRE, seule chose que ce bloc ajoute.
        """
        def _titre(html):
            deb = html.find('raisons-titre">')
            return html[deb:html.find('</div>', deb)] if deb >= 0 else ''

        avec = _bloc_decision_html(
            synthese_decision(_d('ROUGE', PASSE_OUTRE, 'm')), True)
        sans = _bloc_decision_html(
            synthese_decision(_d('VERT', ACCORD)), False)
        self.assertIn('DESACCORD', _titre(avec),
                      "le titre du bloc ne porte pas la marque du desaccord")
        self.assertNotIn('DESACCORD', _titre(sans))
        # ⚠️ Et le second sens : un accord ne doit pas porter la marque, ni
        # dans le titre ni dans le corps.
        self.assertNotIn('DESACCORD', sans)
        print("    DA-8 le desaccord est marque dans le TITRE du bloc, "
              "assiette nommee")


# ═════════════════════════════════════════════════════════════════════════════
#  LE VOCABULAIRE, ET LA VOIE JUSQU'AU DOCUMENT
# ═════════════════════════════════════════════════════════════════════════════
class TestVocabulaireEtBranchement(unittest.TestCase):

    def test_DA9_les_statuts_sont_DERIVES_de_la_source_unique(self):
        """⚠️⚠️ LE DEPOT A DEJA PAYE SEPT VALEURS DISTINCTES de VERT/AMBRE/ROUGE
        dans sept fichiers, sans source. Une huitieme liste divergerait au
        premier statut ajoute.

        ⚠️ Et la derivation elle-meme se verifie : `STATUT_RAG` est indexe par
        FOND, pas par statut. Une premiere ecriture prenait ses cles
        EXTERIEURES et rendait `('clair', 'sombre')` -- une liste de statuts
        qui n'en contenait aucun. *Deriver d'une table ne dispense pas de
        regarder sa forme.*
        """
        self.assertEqual(set(STATUTS_ADMIS), {'VERT', 'AMBRE', 'ROUGE'})
        for fond, table in STATUT_RAG.items():
            with self.subTest(fond=fond):
                self.assertEqual(set(table), set(STATUTS_ADMIS),
                                 "une palette declare d'autres statuts : "
                                 "l'intersection les a masques")
        with self.assertRaises(ValueError) as ctx:
            _d('ORANGE', ACCORD)
        self.assertIn('ORANGE', str(ctx.exception))
        print(f"    DA-9 statuts derives : {STATUTS_ADMIS}, et un statut hors "
              f"table est refuse")

    def test_DA10_une_decision_INCONNUE_est_refusee(self):
        with self.assertRaises(ValueError) as ctx:
            _d('VERT', 'IGNORE')
        msg = str(ctx.exception)
        self.assertIn('IGNORE', msg)
        for admise in DECISIONS_ADMISES:
            self.assertIn(admise, msg, "le motif doit LISTER les admises")
        print(f"    DA-10 decision hors vocabulaire refusee, motif listant "
              f"{DECISIONS_ADMISES}")

    def test_DA11_une_cle_SURNUMERAIRE_est_refusee(self):
        """⚠️ Une cle mal orthographiee ne produit pas une approximation : elle
        produit une decision AUTRE, sans un mot. Meme doctrine que
        `_refuser_cles_inconnues` sur le plan."""
        with self.assertRaises(ValueError) as ctx:
            decision_depuis_dict({
                'verdict_systeme': 'VERT', 'decision': ACCORD,
                'decide_par': _QUI, 'decide_le': _QUAND, 'motif_': 'faute'})
        self.assertIn('motif_', str(ctx.exception))
        self.assertIsNone(decision_depuis_dict(None))
        print("    DA-11 cle surnumeraire refusee ; `None` reste `None`")

    def test_DA12_LE_BRANCHEMENT_la_decision_atteint_les_DEUX_formats(self):
        """⚠️⚠️ LA QUATRIEME ASYMETRIE QUE CE DEPOT A PAYEE. Le mapping,
        l'elasticite, la qualite des donnees et les reserves d'A6 ont chacun
        atteint UN format et pas l'autre. Releve PAR AST : les deux
        exportateurs appellent `synthese_decision`, et A6 la fait passer."""
        chemin = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
                  / 'services' / 'rapport_modeles_tarif.py')
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        appelants = set()
        for fonction in ast.walk(arbre):
            if not isinstance(fonction, ast.FunctionDef):
                continue
            for n in ast.walk(fonction):
                if (isinstance(n, ast.Call)
                        and getattr(n.func, 'id', None) == 'synthese_decision'):
                    appelants.add(fonction.name)
        self.assertIn('export_html', appelants)
        self.assertIn('export_word', appelants)

        a6 = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
              / 'a6_comparaison' / 'agent.py')
        passe = any(
            isinstance(n, ast.Call)
            and getattr(n.func, 'id', None) == 'generer_rapport_tarification'
            and 'decision_actuaire' in {k.arg for k in n.keywords}
            for n in ast.walk(ast.parse(a6.read_text(encoding='utf-8'))))
        self.assertTrue(
            passe,
            "A6 ne fait plus passer `decision_actuaire` : la decision ne peut "
            "plus atteindre le document signe.")
        print(f"    DA-12 les deux exportateurs publient, et A6 fait passer "
              f"({sorted(appelants)})")


if __name__ == '__main__':
    unittest.main(verbosity=2)
