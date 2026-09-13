r"""
==============================================================================
  UN FILTRE PLACE APRES CELUI QUI LUI OTE SON OBJET NE TRACE PLUS RIEN
==============================================================================

⚠️⚠️ `CFR-1` -- LA TRACE ACPR DE L'ANTI-FUITE ETAIT IMPOSSIBLE A
DECLENCHER. `filtrer_genre` et `filtrer_famille_cible` journalisent
chacun ce qu'ils retirent : c'est la trace opposable devant l'ACPR
(arret CJUE C-236/09 pour l'un, prevention du data leakage pour
l'autre). Mais la LISTE BLANCHE -- l'intersection avec les colonnes
declarees au plan, ou `selectionner_features_autorisees` sur le chemin
retrocompatible -- passait AVANT eux et leur otait leur objet.

Mesure du 13/09/2026, sur une liste portant `sexe`, `prime_pure` et
`cout_total_sinistres` avec un plan qui n'en declare aucun :

    chemin                    C-236/09   fuite   liste blanche
    PLAN, ordre ancien            1        0           0
    PLAN, ordre corrige           1        1           0
    RETRO, ordre ancien           0        0           1
    RETRO, ordre corrige          1        1           1

*Un controle qui ne peut pas se declencher est du decor.*

⚠️⚠️ ET AUCUN EURO NE BOUGE, C'EST LE COEUR DE L'AFFAIRE. Les trois
fonctions sont de purs filtres a PREDICAT -- elles ne RETIENNENT que,
n'AJOUTENT jamais (verifie par AST : aucun `append`, `extend`, `insert`,
aucune concatenation de liste). Des filtres a predicat COMMUTENT : sur
2 000 listes tirees, l'ensemble retenu est identique dans les deux
ordres, **ordre des elements compris**. Seule la TRACE change.

⚠️ EFFET DE BORD DECLARE : le journal de la liste blanche ne cite plus
`sexe` ni les grandeurs derivees parmi ses << colonnes non declarees >>.
Chaque exclusion est desormais imputee a SA cause reglementaire, une
seule fois, au lieu d'etre mise au compte du fail-safe.

⚠️ 0 PLAN SUR 20 ne declare une colonne que l'un des deux filtres
retirerait : l'intersection retirait donc la colonne fautive AVANT le
filtre a TOUS les coups. Le defaut etait systematique, pas occasionnel.
==============================================================================
"""
from __future__ import annotations

import ast
import logging
import os
import pathlib
import random
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from core import conformite_reglementaire as CR
from core.plan_tarifaire import PlanTarifaire

_SOURCE = (_RACINE / 'core' / 'conformite_reglementaire.py').read_bytes(
    ).decode('utf-8')

#: ⚠️ DERIVE DE `__file__` -- constat `CWD-1` : un chemin relatif au
#: repertoire courant rend une assiette VIDE depuis ailleurs.
def _plan_auto():
    fichiers = sorted((_RACINE / 'plans').glob('*.yaml'))
    if not fichiers:
        raise AssertionError(
            f"aucun plan sous {_RACINE / 'plans'} : l'assiette du controle "
            f"est VIDE, il attesterait sans rien surveiller")
    auto = next(f for f in fichiers if f.stem == 'auto')
    return PlanTarifaire.depuis_yaml(str(auto))


class _Journal(logging.Handler):
    """⚠️ ON CAPTURE LES LOGS. Le defaut EST une absence de log, et une
    absence ne se lit pas a l'oeil dans une sortie de test."""

    def __init__(self):
        super().__init__()
        self.lignes = []

    def emit(self, record):
        self.lignes.append(record.getMessage())


def _journal(nom):
    j = _Journal()
    lg = logging.getLogger(f'trace_reglementaire.{nom}')
    #: ⚠️ ON VIDE PUIS ON AJOUTE : un `logging.getLogger` du meme nom rend
    #: le MEME objet, et deux appels accumuleraient leurs poignees -- le
    #: second controle compterait alors les lignes du premier.
    lg.handlers.clear()
    lg.addHandler(j)
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    return j, lg


def _compter(lignes):
    return {
        'C-236/09': sum(1 for x in lignes if 'C-236/09' in x),
        'fuite': sum(1 for x in lignes if 'data leakage' in x),
        'blanche': sum(1 for x in lignes if 'LISTE BLANCHE' in x),
    }


#: Une liste de candidates qui porte les DEUX familles prohibees, plus une
#: colonne simplement inconnue pour que la liste blanche ait aussi a dire.
_CANDIDATES = ['age', 'bonus_malus', 'sexe', 'exposition', 'prime_pure',
               'cout_total_sinistres', 'colonne_inconnue']


class TestLaTraceReglementaireSeDeclenche(unittest.TestCase):

    def test_TR1_SCEAU_le_chemin_du_PLAN_trace_les_DEUX_exclusions(self):
        """⚠️⚠️ LE SCEAU, PAR EXECUTION, SUR LA VRAIE PORTE. On appelle
        `construire_matrice_x` avec un plan signe qui ne declare ni genre ni
        grandeur derivee -- exactement le cas de production -- et les DEUX
        traces reglementaires doivent apparaitre."""
        j, lg = _journal('tr1')
        CR.construire_matrice_x(
            list(_CANDIDATES), contexte='sceau CFR-1', logger_agent=lg,
            plan=_plan_auto())
        c = _compter(j.lignes)
        self.assertGreaterEqual(
            c['C-236/09'], 1,
            "aucune trace citant l'arret CJUE C-236/09 : la liste blanche a "
            "retire `sexe` avant que `filtrer_genre` ne le voie")
        self.assertGreaterEqual(
            c['fuite'], 1,
            "aucune trace citant la fuite de donnees : la liste blanche a "
            "retire les grandeurs derivees avant que `filtrer_famille_cible` "
            "ne les voie -- c'est le constat `CFR-1`")
        print(f"    TR-1 SCEAU chemin PLAN : C-236/09 {c['C-236/09']}, "
              f"fuite {c['fuite']}")

    def test_TR2_SCEAU_le_chemin_RETROCOMPATIBLE_trace_aussi(self):
        """⚠️⚠️ L'ASYMETRIE ENTRE VOISINS EST LE REVELATEUR LE MOINS CHER.
        `filtrer_features` est le point d'entree des appelants non migres :
        il portait le MEME defaut, sur ses DEUX filtres au lieu d'un."""
        j, lg = _journal('tr2')
        CR.filtrer_features(list(_CANDIDATES), contexte='sceau CFR-1',
                            logger_agent=lg)
        c = _compter(j.lignes)
        self.assertGreaterEqual(c['C-236/09'], 1,
                                'chemin retrocompatible : 0 trace C-236/09')
        self.assertGreaterEqual(c['fuite'], 1,
                                'chemin retrocompatible : 0 trace de fuite')
        #: ⚠️ ET LA LISTE BLANCHE PARLE TOUJOURS : la deplacer ne devait pas
        #: la faire taire, seulement lui retirer ce qui ne la regarde pas.
        self.assertGreaterEqual(
            c['blanche'], 1,
            'la liste blanche ne journalise plus rien : le fail-safe est muet')
        print(f"    TR-2 SCEAU chemin RETRO : C-236/09 {c['C-236/09']}, "
              f"fuite {c['fuite']}, liste blanche {c['blanche']}")

    def test_TR3_SCEAU_l_ordre_des_filtres_releve_PAR_AST(self):
        """⚠️⚠️ LE RELEVE PORTE SUR LE GESTE, PAS SUR SA FORME. Sur le
        chemin du plan, << celui qui ote son objet >> n'est pas un appel mais
        une COMPREHENSION (`[c for c in conformes if c in declarees]`) : un
        releve limite aux appels ne la verrait pas, et le sceau serait vert
        sur la violation qu'il pretend interdire."""
        arbre = ast.parse(_SOURCE)
        REGLEMENTAIRES = ('filtrer_genre', 'filtrer_famille_cible')
        for nom, oteur in (('filtrer_features',
                            'selectionner_features_autorisees'),
                           ('construire_matrice_x', 'INTERSECTION')):
            f = next(n for n in ast.walk(arbre)
                     if isinstance(n, ast.FunctionDef) and n.name == nom)
            seq = []
            for n in ast.walk(f):
                if (isinstance(n, ast.Call)
                        and getattr(n.func, 'id', None)
                        in REGLEMENTAIRES + (oteur,)):
                    seq.append((n.lineno, n.func.id))
                elif (isinstance(n, ast.ListComp)
                      and 'declarees' in ast.unparse(n)):
                    seq.append((n.lineno, 'INTERSECTION'))
            ordre = [x for _, x in sorted(seq)]
            for r in REGLEMENTAIRES:
                self.assertIn(r, ordre, f'{nom} : {r} a disparu du chemin')
                self.assertLess(
                    ordre.index(r), ordre.index(oteur),
                    f"`{nom}` : `{r}` passe APRES `{oteur}`, qui lui a deja "
                    f"retire son objet -- il ne peut plus rien journaliser. "
                    f"Ordre releve : {ordre}")
            print(f"    TR-3 SCEAU {nom:22} ordre {ordre}")

    def test_TR4_CONTRE_EPREUVE_les_trois_filtres_COMMUTENT(self):
        """⚠️⚠️ CE QUE CE LOT NE DOIT SURTOUT PAS DEPLACER. Si les filtres ne
        commutaient pas, deplacer la liste blanche changerait l'ensemble
        retenu -- donc la matrice X, donc le prix. *La preuve qu'aucun euro
        ne bouge tient a cette propriete, et elle se MESURE.*"""
        vocab = sorted(set(list(CR.FACTEURS_TARIFAIRES_AUTORISES)[:14]) | {
            'sexe', 'genre', 'civilite', 'is_male', 'prime_pure',
            'cout_total_sinistres', 'nb_sinistres', 'loss_ratio',
            'colonne_inconnue_1', 'Exposure'})
        declarees = set(list(CR.FACTEURS_TARIFAIRES_AUTORISES)[:9]) | {
            'sexe', 'prime_pure'}
        muet = logging.getLogger('trace_reglementaire.muet')
        muet.handlers.clear()
        muet.addHandler(logging.NullHandler())
        muet.propagate = False
        rng = random.Random(20260913)
        ecarts = []
        for _ in range(500):
            xs = rng.sample(vocab, rng.randint(0, len(vocab)))
            ancien = CR.filtrer_genre(list(xs), logger_agent=muet)
            ancien = [c for c in ancien if c in declarees]
            ancien = CR.filtrer_famille_cible(ancien, logger_agent=muet)
            nouveau = CR.filtrer_genre(list(xs), logger_agent=muet)
            nouveau = CR.filtrer_famille_cible(nouveau, logger_agent=muet)
            nouveau = [c for c in nouveau if c in declarees]
            if ancien != nouveau:
                ecarts.append((xs, ancien, nouveau))
        self.assertEqual(
            ecarts, [],
            f"{len(ecarts)} liste(s) sur 500 rendent un ensemble DIFFERENT "
            f"selon l'ordre : les filtres ne commutent pas, et deplacer la "
            f"liste blanche DEPLACE alors la matrice X. Premier : "
            f"{ecarts[0] if ecarts else ''}")
        print('    TR-4 contre-epreuve : 500 listes, 0 ecart entre les deux '
              'ordres (ordre des elements compris)')

    def test_TR5_CONTRE_EPREUVE_un_portefeuille_PROPRE_ne_trace_RIEN(self):
        """⚠️ LE SECOND SENS. Un controle qui tracerait tout le temps ne
        surveillerait rien : sur une liste sans genre et sans grandeur
        derivee, les deux filtres reglementaires doivent rester MUETS."""
        j, lg = _journal('tr5')
        propre = ['age', 'bonus_malus', 'exposition', 'anciennete_permis']
        retenu = CR.filtrer_features(propre, logger_agent=lg)
        c = _compter(j.lignes)
        self.assertEqual(c['C-236/09'], 0, f'trace de genre a tort : {j.lignes}')
        self.assertEqual(c['fuite'], 0, f'trace de fuite a tort : {j.lignes}')
        self.assertEqual(sorted(retenu), sorted(propre),
                         'une colonne legitime a ete retiree')
        print(f"    TR-5 contre-epreuve : portefeuille propre -> 0 trace, "
              f"{len(retenu)} colonne(s) conservee(s)")

    def test_TR6_le_TEXTE_qui_decrit_l_ordre_a_ete_RELU(self):
        """⚠️⚠️ LE TEXTE QUI ACCOMPAGNE UN COMPORTEMENT SE RELIT QUAND IL
        CHANGE. Trois phrases du depot enoncaient l'ancien ordre, dont deux
        dans le module de conformite lui-meme. *Y laisser une description
        fausse de l'ordre reglementaire, ce serait publier une contre-verite
        a l'endroit exact ou un controleur la lirait.*

        ⚠️ Ce controle-ci lit la PROSE, et il le sait : il ne remplace pas
        `TR-1` a `TR-3`, qui lisent le COMPORTEMENT. Il les complete."""
        perimes = [
            "À utiliser en PREMIER, avant filtrer_genre",
            ("1. LISTE BLANCHE  — seuls les facteurs tarifaires déclarés "
             "passent ;"),
            ("1. LISTE BLANCHE           — seuls les facteurs déclarés "
             "passent ;"),
            "① LISTE BLANCHE + ② GENRE",
        ]
        restants = [p for p in perimes if p in _SOURCE]
        self.assertEqual(
            restants, [],
            f"{len(restants)} phrase(s) decrivent encore l'ANCIEN ordre dans "
            f"`core/conformite_reglementaire.py` : {restants}")
        print(f"    TR-6 texte : 0 / {len(perimes)} phrase(s) perimee(s) "
              f"restante(s)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
