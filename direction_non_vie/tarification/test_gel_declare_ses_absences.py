r"""
==============================================================================
  LA REFERENCE DE GEL DIT CE QU'ELLE NE COUVRE PAS
==============================================================================

⚠️⚠️ `D4` -- REPORT DU ROUND 4, CONFIRME LE 14/09/2026. `figer()` ecrivait
les 32 surfaces sans distinguer, alors que QUINZE d'entre elles valent
`ABSENT` : leur producteur rend ZERO octet, et leur sha256 est celui de
la chaine `<livrable absent>` -- **le MEME pour toutes**,
`sha256:cc62197f13e6...`. La sentinelle publiait ensuite

    << 32 surfaces signees, contenu inchange >>

*une phrase quinze fois trop genereuse sur sa propre couverture.* Un
<< 0 ecart >> ne disait RIEN de ces quinze.

⚠️ SON JUMEAU DISTINGUAIT DEPUIS TOUJOURS. `deposer()` calcule
`reelles = [nom for nom, contenu in ... if contenu != G.ABSENT]` et
l'annonce : << surfaces reelles : 17 >>. *Deux fonctions du meme fichier
ne disaient pas la meme chose de la meme mesure* -- et c'est l'asymetrie
entre voisins qui a livre ce constat, comme d'habitude.

⚠️⚠️ ON NE RETIRE RIEN DE LA REFERENCE. Une surface absente qui
DEVIENDRAIT reelle est un ecart qu'il faut voir, et l'inverse aussi. On
NOMME, pour que le compte cesse de mentir. Mesure du figeage du
14/09 : **22 insertions, 0 suppression** -- aucune empreinte ne bouge.

⚠️ ET LA CAUSE N'EST PAS TOUJOURS WEASYPRINT, ce qui est le vrai
inconfort. Au 15/09/2026 les absentes sont DIX-SEPT : NEUF PDF
(weasyprint non installe, cause connue), UNE a cause DECLAREE
(`a5 Word` -- A5 ne produit pas de Word, et son gabarit le dit), et SEPT
sans cause, les memes qu'au 14/09 :

    a1 Word, a2 Word, a3 Word, a6 Rapport equipe Excel,
    a6 Rapport equipe HTML, a6 Rapport equipe Word, rapport_modeles Excel

Leur producteur rend zero octet et rien ne dit pourquoi. `DA-5` MESURE
ce partage et le publie ; il ne le ferme pas.

⚠️ CE SCEAU EST RAPIDE, ET C'EST DELIBERE. `GEL-15b` produit la chaine
entiere -- 260 secondes. Un garde-fou qu'on ne peut pas PLANTER quatre
fois sans y passer vingt minutes finit par n'etre jamais plante. Ici on
lit la reference et le SOURCE ; `GEL-15b` reste la sentinelle vivante.
==============================================================================
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import pathlib
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from direction_non_vie.tarification.services import gel_livrables as G

_REFERENCE = (_RACINE / 'direction_non_vie' / 'tarification'
              / 'reference_gel.json')
_LANCEUR = _RACINE / 'scripts' / 'gel_avant_apres.py'

#: ⚠️⚠️ LES ABSENCES DONT LA CAUSE EST CONNUE **ET ECRITE** — hors PDF, dont
#: la cause (weasyprint non installe) se lit deja au suffixe.
#: *Une absence expliquee et une absence inexpliquee ne se comptent pas
#: ensemble : la seconde est une dette, la premiere un fait declare.*
_CAUSES_DECLAREES: dict[str, str] = {
    'a5 Word':
        "A5 ne produit PAS de document Word, et sa sortie le DIT : son "
        "gabarit porte `word_bytes = b''`. La surface est entree dans "
        "l'assiette du gel le 15/09/2026, avec `a5 PDF`, precisement parce "
        "qu'une surface TUE est une surface que l'instrument de "
        "non-regression ne regarde pas. Mesure : 34 surfaces, 17 reelles "
        "inchangees.",
}

#: ⚠️ ET CELLES QUI RESTENT SANS CAUSE : un ensemble FIGE, pas un plafond.
#: Elles valaient sept au 14/09/2026 et ce sont les memes.
_SANS_CAUSE_CONNUE = frozenset({
    'a1 Word', 'a2 Word', 'a3 Word', 'a6 Rapport equipe Excel',
    'a6 Rapport equipe HTML', 'a6 Rapport equipe Word',
    'rapport_modeles Excel',
})


def _reference() -> dict:
    return json.loads(_REFERENCE.read_text(encoding='utf-8'))


def _empreinte_de_l_absence() -> str:
    """⚠️ CALCULEE, JAMAIS RECOPIEE : un sha256 en dur dans un controle
    devient faux le jour ou le marqueur change, et le controle devient un
    garde-fou sur une constante morte."""
    canon = json.dumps(G.ABSENT, sort_keys=True, ensure_ascii=False,
                       default=str)
    return 'sha256:' + hashlib.sha256(canon.encode('utf-8')).hexdigest()


class TestGelDeclareSesAbsences(unittest.TestCase):

    # ── DA-1 ─────────────────────────────────────────────────────────────
    def test_DA1_la_reference_NOMME_les_surfaces_qu_elle_ne_couvre_pas(self):
        """⚠️ LA LISTE DECLAREE SE CONFRONTE A LA MESURE, jamais a
        elle-meme : une declaration qu'on ne verifie pas est une prose."""
        ref = _reference()
        surfaces = ref.get('surfaces') or {}
        self.assertTrue(surfaces, 'aucune surface figee')
        absente = _empreinte_de_l_absence()
        mesurees = sorted(n for n, h in surfaces.items() if h == absente)
        bloc = ref.get('_surfaces_absentes')
        self.assertIsNotNone(
            bloc,
            f"la reference ne declare pas ses surfaces ABSENTES. "
            f"{len(mesurees)} surface(s) sur {len(surfaces)} portent "
            f"pourtant l'empreinte de {G.ABSENT!r}, et un << 0 ecart >> ne "
            f"dit rien d'elles.")
        self.assertEqual(
            sorted(bloc.get('noms') or []), mesurees,
            f"la declaration ne correspond pas a la mesure. "
            f"declarees={sorted(bloc.get('noms') or [])} "
            f"mesurees={mesurees}")
        print(f"    DA-1 SCEAU : {len(mesurees)} absente(s) declaree(s) sur "
              f"{len(surfaces)} surfaces, liste conforme a la mesure")

    # ── DA-2 ─────────────────────────────────────────────────────────────
    def test_DA2_les_deux_comptes_declares_sont_COHERENTS(self):
        """Un compte qui ne se referme pas est un compte qu'on n'a pas
        fait."""
        ref = _reference()
        bloc = ref.get('_surfaces_absentes') or {}
        surfaces = ref.get('surfaces') or {}
        self.assertEqual(
            bloc.get('nb_absentes'), len(bloc.get('noms') or []),
            "le compte d'absentes ne correspond pas a la liste qui le porte")
        self.assertEqual(
            (bloc.get('nb_absentes') or 0) + (bloc.get('nb_reelles') or 0),
            len(surfaces),
            f"reelles + absentes ne fait pas le total : "
            f"{bloc.get('nb_reelles')} + {bloc.get('nb_absentes')} != "
            f"{len(surfaces)}")
        print(f"    DA-2 SCEAU : {bloc.get('nb_reelles')} reelles + "
              f"{bloc.get('nb_absentes')} absentes = {len(surfaces)}")

    # ── DA-3 ─────────────────────────────────────────────────────────────
    def test_DA3_figer_et_deposer_emploient_le_MEME_predicat(self):
        """⚠️⚠️ L'ASYMETRIE ENTRE JUMEAUX EST CE QUI A LIVRE CE CONSTAT.
        `deposer()` distinguait les surfaces reelles depuis toujours,
        `figer()` non. Le releve est par AST et porte sur le PREDICAT : un
        futur lot qui en changerait un seul des deux le rouvrirait."""
        #: ⚠️⚠️ ON CHERCHE LA COMPARAISON, PAS LE NOM. Une premiere version
        #: testait `'G.ABSENT' in ast.unparse(fonction)` : le plant qui
        #: remplacait le predicat par `if False` restait VERT, parce que
        #: `G.ABSENT` survivait dans la f-string de DOCTRINE du meme bloc.
        #: *Une interpolation n'est pas un predicat.* Troisieme forme de ce
        #: piege dans la meme session -- on descend donc au noeud `Compare`.
        arbre = ast.parse(_LANCEUR.read_bytes().decode('utf-8'))
        vus = {}
        for n in arbre.body:
            if not isinstance(n, ast.FunctionDef) or n.name not in (
                    'figer', 'deposer'):
                continue
            trouve = False
            for c in ast.walk(n):
                if not isinstance(c, ast.Compare):
                    continue
                cotes = [c.left, *c.comparators]
                for x in cotes:
                    nom = (x.attr if isinstance(x, ast.Attribute)
                           else x.id if isinstance(x, ast.Name) else '')
                    if nom == 'ABSENT':
                        trouve = True
            vus[n.name] = trouve
        self.assertEqual(
            sorted(vus), ['deposer', 'figer'],
            f"l'assiette de ce controle a change : {sorted(vus)}")
        manquants = [k for k, v in vus.items() if not v]
        self.assertEqual(
            manquants, [],
            f"{manquants} ne distingue(nt) plus les surfaces ABSENTES des "
            f"surfaces reelles. Deux fonctions du meme fichier diraient a "
            f"nouveau deux choses de la meme mesure.")
        print(f"    DA-3 SCEAU : {sorted(vus)} distinguent tous deux "
              f"l'absence par une COMPARAISON, pas par une mention")

    # ── DA-4 ─────────────────────────────────────────────────────────────
    def test_DA4_le_bloc_DIT_ce_que_la_reference_ne_couvre_pas(self):
        """⚠️ UNE LISTE SANS SA PHRASE EST UN CHIFFRE SANS SON SENS. Le
        lecteur de cette reference doit comprendre, SANS lire le code, que
        ces surfaces ne sont pas couvertes."""
        bloc = _reference().get('_surfaces_absentes') or {}
        doctrine = str(bloc.get('doctrine') or '')
        for attendu in ('ZERO octet', 'ne couvre', G.ABSENT):
            self.assertIn(
                attendu, doctrine,
                f"la doctrine du bloc ne dit pas {attendu!r} : "
                f"{doctrine[:90]!r}")
        print(f"    DA-4 SCEAU : la doctrine du bloc fait "
              f"{len(doctrine)} caracteres et nomme l'absence")

    # ── DA-5 ─────────────────────────────────────────────────────────────
    def test_DA5_LE_PARTAGE_des_causes_est_MESURE_constat_ouvert(self):
        """⚠️ CE CONTROLE NE FERME RIEN : il MESURE et PUBLIE. Huit des
        quinze absentes sont des PDF -- weasyprint n'est pas installe, la
        cause est connue. SEPT ne le sont pas, et rien ne dit pourquoi
        leur producteur rend zero octet. *Le jour ou ce partage change, ce
        controle le dira.*"""
        bloc = _reference().get('_surfaces_absentes') or {}
        noms = sorted(bloc.get('noms') or [])
        self.assertTrue(noms, 'aucune absente declaree : rien a mesurer')
        pdf = [n for n in noms if n.endswith('PDF')]
        autres = [n for n in noms if not n.endswith('PDF')
                  and n not in _CAUSES_DECLAREES]
        #: ⚠️⚠️ ON NOMME, ON NE COMPTE PLUS. Le controle disait
        #: `len(autres) <= 7` : un plafond laisse passer un ECHANGE -- une
        #: absente qui disparait pendant qu'une autre arrive, et le compte
        #: ne bouge pas. Depuis le 15/09 la liste est EGALE a un ensemble
        #: fige, ce qui est strictement plus fort.
        self.assertEqual(
            sorted(autres), sorted(_SANS_CAUSE_CONNUE),
            f"la liste des surfaces absentes SANS cause connue a change.\n"
            f"  apparues  : {sorted(set(autres) - _SANS_CAUSE_CONNUE)}\n"
            f"  disparues : {sorted(_SANS_CAUSE_CONNUE - set(autres))}\n"
            f"Chacune est un livrable signe que la chaine ne produit pas : "
            f"si une cause est desormais connue, elle se DECLARE dans "
            f"`_CAUSES_DECLAREES`, avec sa mesure.")
        print(f"    DA-5 RELEVE (non ferme) : {len(pdf)} PDF (weasyprint "
              f"absent) + {len(_CAUSES_DECLAREES)} a cause DECLAREE + "
              f"{len(autres)} SANS cause connue -> {autres}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
