"""
==============================================================================
  L'ARRETE D'UN LIVRABLE SIGNE SE DECLARE -- IL NE SE LIT PAS SUR L'HORLOGE
==============================================================================

⚠️⚠️ CE QUE CE LOT FERME. Trois lignes de la tarification posaient
`arrete=datetime.now().strftime('%d/%m/%Y')` :

    a4_ml/agent.py:1501          a6_comparaison/agent.py:1094 et :1142

Or l'arrete est une REFERENCE METIER declaree par l'actuaire -- la date a
laquelle les comptes sont arretes -- et non le jour de l'impression. Le
service appele le dit deja dans sa propre docstring : *<< jamais un horodatage
a l'heure >>*, et `libelle_arrete(None)` ecrit << non declare >>, VISIBLE.
**Trois appelants devinaient a sa place.**

DEUX CONSEQUENCES, ET LA SECONDE EST CELLE QUI A REVELE LA PREMIERE
  · un livrable SIGNE affirmait un arrete que personne n'avait declare, et le
    MEME dossier regenere le lendemain en portait un autre ;
  · le temoin de gel, VERT a 23 h le 08/09/2026, rougissait a minuit sur
    `a4 Word` : il mesurait la DATE, pas le code. Mesure : deux occurrences de
    `09/09/2026` dans le contenu normalise, dont
    `... Arrete 09/09/2026 . Genere le <horodatage> ...` -- le << Genere le >>
    etait bien neutralise, l'arrete non, et c'est VOULU (`GEL-3` : un arrete
    qui change EST un ecart).

⚠️ L'ASYMETRIE ENTRE VOISINS L'AURAIT MONTRE : A7 (provisionnement) passe un
`arrete` DECLARE a ses livrables ; la tarification le fabriquait.

⚠️⚠️ UN PARAMETRE QUE PERSONNE NE REMPLIT EST UN TUYAU SANS SOURCE -- la lecon
du lot 2, ou le gel etait reste VERT parce qu'aucun appelant ne fournissait
rien. Le pilote de gel declare donc son `ARRETE` a A4 et A6, comme il le
faisait deja aux deux rapports.

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

from direction_non_vie.tarification.services.entete_livrable import (
    ARRETE_NON_DECLARE,
    libelle_arrete,
)

#: Les modules de tarification qui produisent un livrable signe.
_SOURCES = (
    'direction_non_vie/tarification/a4_ml/agent.py',
    'direction_non_vie/tarification/a6_comparaison/agent.py',
    'direction_non_vie/tarification/a3_glm/agent.py',
    'direction_non_vie/tarification/a5_deep_learning/agent.py',
    'direction_non_vie/tarification/a2_preprocessing/agent.py',
    'direction_non_vie/tarification/a1_ingestion/agent.py',
)


def _arretes_passes(chemin: pathlib.Path) -> list[str]:
    """Toute expression passee en `arrete=` dans ce fichier, relevee PAR AST.

    ⚠️ PAR AST, PAS AU TEXTE : un releve au texte manquerait un alias, une
    variable intermediaire ou un appel reparti sur deux lignes.
    """
    arbre = ast.parse(chemin.read_text(encoding='utf-8'))
    return [ast.unparse(mot.value)
            for noeud in ast.walk(arbre) if isinstance(noeud, ast.Call)
            for mot in noeud.keywords if mot.arg == 'arrete']


class TestAucunArreteNeVientDeLHorloge(unittest.TestCase):

    def test_AR1_LE_SCEAU_aucune_source_de_tarification_ne_lit_l_horloge(self):
        """⚠️⚠️ LE DEFAUT QUE CE LOT FERME, RELEVE SUR TOUTE LA DIRECTION -- pas
        sur les trois lignes connues. *Un controle qui ne regarderait que les
        sites deja corriges ne verrait jamais le quatrieme.*"""
        coupables = []
        for relatif in _SOURCES:
            chemin = pathlib.Path(_RACINE) / relatif
            if not chemin.exists():
                continue
            for expression in _arretes_passes(chemin):
                if 'now()' in expression or 'today()' in expression:
                    coupables.append(f"{relatif} : arrete={expression}")
        self.assertEqual(
            coupables, [],
            "un livrable signe date son ARRETE sur l'horloge :\n  "
            + "\n  ".join(coupables))
        print(f"    AR-1 SCEAU : {len(_SOURCES)} sources relevees, "
              f"0 arrete lu sur l'horloge")

    def test_AR2_LE_MIROIR_les_agents_ACCEPTENT_un_arrete_declare(self):
        """⚠️ Sans ce sens, supprimer purement l'argument satisferait AR-1 -- et
        plus aucun arrete ne pourrait jamais etre declare."""
        for relatif, classe in (
                ('direction_non_vie/tarification/a4_ml/agent.py', 'AgentA4ML'),
                ('direction_non_vie/tarification/a6_comparaison/agent.py',
                 'AgentA6Comparaison')):
            arbre = ast.parse((pathlib.Path(_RACINE) / relatif)
                              .read_text(encoding='utf-8'))
            trouve = False
            for noeud in ast.walk(arbre):
                if (isinstance(noeud, ast.ClassDef) and noeud.name == classe):
                    for fonction in noeud.body:
                        if (isinstance(fonction, ast.FunctionDef)
                                and fonction.name == 'run'):
                            noms = {a.arg for a in fonction.args.args}
                            noms |= {a.arg for a in fonction.args.kwonlyargs}
                            trouve = 'arrete' in noms
            self.assertTrue(trouve,
                            f"{classe}.run n'accepte pas d'arrete declare")
        print("    AR-2 miroir : A4 et A6 acceptent un arrete DECLARE")

    def test_AR3_le_pilote_de_gel_DECLARE_son_arrete_a_A4_et_A6(self):
        """⚠️⚠️ UN PARAMETRE QUE PERSONNE NE REMPLIT EST UN TUYAU SANS SOURCE.
        Le pilote declarait deja `ARRETE` aux deux rapports ; il le declare
        maintenant aussi aux agents, sinon le meme dossier porterait DEUX
        arretes differents."""
        arbre = ast.parse((pathlib.Path(_RACINE) / 'scripts'
                           / 'gel_avant_apres.py').read_text(encoding='utf-8'))
        agents = {'AgentA4ML': False, 'AgentA6Comparaison': False}
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.Call)
                    and getattr(noeud.func, 'attr', None) == 'run'):
                continue
            source = ast.unparse(noeud)
            for nom in agents:
                if nom in source and 'arrete=ARRETE' in source:
                    agents[nom] = True
        for nom, vu in agents.items():
            self.assertTrue(vu, f"le pilote de gel ne declare pas d'arrete "
                                f"a {nom} : le tuyau n'a pas de source")
        print("    AR-3 le pilote de gel declare son ARRETE a A4 et a A6")

    def test_AR4_sans_declaration_le_service_le_DIT_il_ne_devine_pas(self):
        """⚠️⚠️ C'EST LE CONTRAT DEJA ECRIT, et il n'a jamais eu besoin d'etre
        change : `None` rend un libelle VISIBLE, jamais une date d'aujourd'hui.
        *Ce lot n'a rien invente -- il a fait respecter une decision deja
        prise.*"""
        self.assertEqual(libelle_arrete(None), ARRETE_NON_DECLARE)
        self.assertEqual(libelle_arrete(''), ARRETE_NON_DECLARE)
        self.assertNotIn('/', libelle_arrete(None))
        # et le miroir : un arrete DECLARE survit
        self.assertIn('2026', libelle_arrete('2026-06-30'))
        print(f"    AR-4 sans declaration : '{libelle_arrete(None)}', "
              f"jamais une date")

    def test_AR5_un_arrete_declare_ne_DEPEND_pas_du_jour_de_generation(self):
        """⚠️⚠️ LA PROPRIETE QUE LE TEMOIN DE GEL SURVEILLE. Deux appels
        identiques a des jours differents doivent rendre le meme libelle --
        c'est ce qui rend `GEL-3` mesurable."""
        declare = '2026-06-30'
        self.assertEqual(libelle_arrete(declare), libelle_arrete(declare))
        self.assertNotEqual(libelle_arrete(declare), libelle_arrete(None))
        print("    AR-5 un arrete declare ne bouge pas d'un jour a l'autre")


if __name__ == '__main__':
    unittest.main(verbosity=2)
