r"""
==============================================================================
  UN OPTIMUM DE MARGE NE SE CALCULE PAS SUR DES TAUX QUE PERSONNE N'A
  DECLARES
==============================================================================

⚠️⚠️ `ELA-2` -- ET L'AUDITEUR N'AVAIT ECRIT AUCUN CORRECTIF. Il le dit
lui-meme : *<< le remede est raisonne -- `sensibilite_tarifaire`
publierait le refus au lieu de se replier -- mais il n'a ete ni ecrit ni
verifie >>*. Ce lot est donc de la CONCEPTION.

LE DEFAUT. `core/elasticite.sensibilite_tarifaire` retombait sur
`CHARGEMENTS_DEFAUT` (frais 15 %, commission 10 %, marge 3 %) quand ni
l'appel ni le plan ne declaraient de chargements, et publiait une
`marge_technique` -- puis un OPTIMUM -- calcules dessus. Or
`core/chargements_declares.py` ecrit en en-tete la regle arbitree le
08/09/2026 : *<< la prime commerciale n'existe QUE si le client a declare
ses trois chargements. Sans declaration, elle n'est pas calculee et LE
REFUS EST PUBLIE -- jamais un repli muet. >>*

*La prime pure refusait de deviner ces nombres ; la marge les devinait
encore.* Le lot `EL-D1` du 12/09 avait ferme la moitie du probleme en
PUBLIANT l'origine ; il restait le repli lui-meme.

⚠️ LE CONSTAT EST LATENT, ET LA MESURE LE DIT : **0 plan sur 20** declare
un bloc `comportement`, **0 sur 20** declare ses `chargements`. Aucun
chiffre publie aujourd'hui ne bouge -- `EL-5` le mesure plutot que de le
croire. Ce qui se ferme est la CONTRADICTION, avant qu'un client ne
declare ses taux : sur un plan declarant frais 5 % / commission 25 %, la
marge au tarif actuel passe de 637 489,65 a 473 455,32 EUR, soit
**-164 034,33 EUR (-25,73 %)**.

⚠️ POURQUOI UN REFUS TOTAL, ET PAS UNE MARGE TUE. Cette fonction existe
pour trouver l'OPTIMUM DE MARGE : sans taux declares il n'y a pas
d'optimum, seulement une devinette. Le refus REEMPLOIE l'idiome deja
present dans la fonction (`vide` + `motif`, employe deux fois), et
`synthese_elasticite` sait deja le publier -- << SENSIBILITE TARIFAIRE :
non disponible. >>. *On ne cree pas de mecanisme quand celui qui convient
est deja la.*
==============================================================================
"""
from __future__ import annotations

import ast
import logging
import os
import pathlib
import sys
import unittest

import numpy as np
import pandas as pd

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from core import elasticite as EL
from core.plan_tarifaire import Chargements, Comportement, PlanTarifaire

_SOURCE = (_RACINE / 'core' / 'elasticite.py').read_bytes().decode('utf-8')


def _plans_du_depot():
    fichiers = sorted((_RACINE / 'plans').glob('*.yaml'))
    if not fichiers:
        raise AssertionError(
            f"aucun plan sous {_RACINE / 'plans'} : l'assiette du controle "
            f"est VIDE, il attesterait sans rien surveiller")
    return fichiers


def _auto() -> PlanTarifaire:
    return PlanTarifaire.depuis_yaml(
        str(next(f for f in _plans_du_depot() if f.stem == 'auto')))


def _portefeuille(plan, n=400):
    """⚠️ Il porte les colonnes du PLAN REEL : sans elles la regression est
    degeneree, et on mesurerait le harnais plutot que la garde."""
    rng = np.random.default_rng(13)
    prime = rng.uniform(200, 900, n)
    df = pd.DataFrame({
        'prime_proposee': prime,
        'prime_precedente': prime * 0.95,
        'souscrit': (rng.random(n) < 0.5).astype(int),
        'exposition': np.ones(n),
        'cout_total_sinistres': rng.gamma(2, 120, n),
        'nb_sinistres': rng.poisson(0.1, n),
        'groupe_test': np.where(np.arange(n) % 2 == 0, 'A', 'B'),
    })
    for c in plan.colonnes_produites():
        if c not in df.columns:
            df[c] = rng.normal(0, 1, n)
    return df


def _avec(plan, chargements=None):
    import dataclasses
    return dataclasses.replace(
        plan,
        comportement=Comportement(
            issue='souscrit', prime_precedente='prime_precedente',
            prime_proposee='prime_proposee', canal=None,
            groupe_test='groupe_test'),
        chargements=chargements)


def _charges(frais=0.05, commission=0.25, marge=0.03):
    return Chargements(frais=frais, commission=commission, marge=marge,
                       taxes=None, declare_par='Client Test',
                       declare_le='2026-09-13')


def _sensibilite(plan, df):
    """L'appel, mene JUSQU'A la garde.

    ⚠️⚠️ DEUX AMENAGEMENTS, ET ILS SE DISENT. Sur des donnees synthetiques
    la machine a etats s'arrete AVANT la garde qu'on veut mesurer, et le
    logit ne converge pas. On declare donc l'etat ESTIMEE -- `etat` est un
    PARAMETRE documente de la fonction, pas un interne -- et on remplace
    `_ajuster_logit` le temps de l'appel, avant de le REMETTRE.
    *On ne mesure pas un correctif en s'arretant avant lui ; et on nomme ce
    qu'on a amenage plutot que de laisser croire a un run nominal.*"""
    etat = EL.etat_elasticite(plan, df)
    etat = {**etat, 'etat': EL.ELASTICITE_ESTIMEE,
            'estimation': {**(etat.get('estimation') or {}),
                           'elasticite': -1.2, 'ic_bas': -1.8,
                           'ic_haut': -0.6, 'p_valeur': 0.001}}
    vrai = EL._ajuster_logit
    EL._ajuster_logit = lambda y, _X: (-0.004, 0.001, 0.5, True,
                                       np.full(len(y), 0.5), None)
    try:
        return EL.sensibilite_tarifaire(plan, df, etat)
    finally:
        EL._ajuster_logit = vrai


class TestUneMargeSansTauxDeclares(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_EL1_SCEAU_sans_taux_declares_le_refus_est_PUBLIE(self):
        """⚠️⚠️ LE SCEAU. Sans declaration, aucun optimum : le refus est
        publie, et il NOMME ce qu'il faut faire."""
        plan = _avec(_auto())
        s = _sensibilite(plan, _portefeuille(plan))
        self.assertFalse(
            s.get('disponible'),
            'une sensibilite est publiee sur trois taux que personne n a '
            'declares')
        self.assertIsNone(s.get('optimum'),
                          'un optimum est publie sur des taux devines')
        motif = s.get('motif') or ''
        for attendu in ('chargements', 'déclare', 'relancez'):
            self.assertIn(
                attendu, motif,
                f"le refus ne dit pas {attendu!r} : il nomme le manque sans "
                f"dire quoi faire. Motif : {motif[:140]}")
        print(f"    EL-1 SCEAU : refus publie, {len(motif)} caracteres, "
              f"action nommee")

    def test_EL2_CONTRE_EPREUVE_des_taux_DECLARES_calculent_encore(self):
        """⚠️⚠️ LE SECOND SENS, ET IL EST INDISPENSABLE. Un refus qui
        refuserait TOUJOURS aurait simplement supprime la fonction."""
        plan = _avec(_auto(), _charges())
        s = _sensibilite(plan, _portefeuille(plan))
        self.assertTrue(
            s.get('disponible'),
            f"la sensibilite est refusee alors que le plan DECLARE ses "
            f"chargements : {(s.get('motif') or '')[:140]}")
        self.assertIn('DECLARES AU PLAN', s['conventions']['origine'],
                      "l'origine ne nomme pas le plan comme source")
        print(f"    EL-2 contre-epreuve : taux declares -> sensibilite "
              f"disponible, origine "
              f"{s['conventions']['origine'][:34]!r}")

    def test_EL3_le_drapeau_est_POSE_HORS_DE_TOUTE_GARDE(self):
        """⚠️⚠️ LE DEFAUT `A6-1` DE CE DEPOT, QUI NE SE REPRODUIT PAS ICI.
        Une variable affectee seulement dans une branche et lue en dehors
        leve `NameError` sur les autres chemins. Le drapeau doit etre
        initialise AVANT la garde, et cela se releve PAR AST."""
        arbre = ast.parse(_SOURCE)
        f = next(n for n in ast.walk(arbre)
                 if isinstance(n, ast.FunctionDef)
                 and n.name == 'sensibilite_tarifaire')
        poses = [n.lineno for n in ast.walk(f)
                 if isinstance(n, ast.Name) and n.id == '_ch_devines'
                 and isinstance(n.ctx, ast.Store)]
        lus = [n.lineno for n in ast.walk(f)
               if isinstance(n, ast.Name) and n.id == '_ch_devines'
               and isinstance(n.ctx, ast.Load)]
        sous_garde = {x.lineno for n in ast.walk(f) if isinstance(n, ast.If)
                      for x in ast.walk(n)
                      if isinstance(x, ast.Name) and x.id == '_ch_devines'
                      and isinstance(x.ctx, ast.Store)}
        self.assertTrue(poses and lus, 'le drapeau a disparu de la fonction')
        self.assertNotIn(
            min(poses), sous_garde,
            f"la PREMIERE affectation du drapeau (l.{min(poses)}) est SOUS "
            f"GARDE : un chemin qui ne la traverse pas leverait NameError")
        self.assertLess(min(poses), min(lus),
                        'le drapeau est lu avant d etre pose')
        print(f"    EL-3 : drapeau pose l.{min(poses)} hors garde, lu "
              f"l.{min(lus)}")

    def test_EL4_le_refus_precede_TOUTE_lecture_des_taux(self):
        """⚠️⚠️ L'ORDRE EST LE CORRECTIF. Si la garde passait APRES la ligne
        qui lit `ch['commission']`, une marge devinee serait calculee avant
        d'etre jetee -- et un jour republiee par un chemin voisin."""
        arbre = ast.parse(_SOURCE)
        f = next(n for n in ast.walk(arbre)
                 if isinstance(n, ast.FunctionDef)
                 and n.name == 'sensibilite_tarifaire')
        garde = [n.lineno for n in ast.walk(f)
                 if isinstance(n, ast.If) and ast.unparse(n.test)
                 == '_ch_devines']
        lectures = [n.lineno for n in ast.walk(f)
                    if isinstance(n, ast.Subscript)
                    and ast.unparse(n).startswith("ch['")]
        self.assertTrue(garde, 'la garde `if _ch_devines:` a disparu')
        self.assertTrue(lectures, "plus aucune lecture de `ch[...]` : "
                                  "l assiette de ce controle est vide")
        self.assertLess(
            max(garde), min(lectures),
            f"la garde (l.{max(garde)}) passe APRES la premiere lecture des "
            f"taux (l.{min(lectures)}) : une marge devinee est calculee")
        print(f"    EL-4 : garde l.{max(garde)} avant la lecture des taux "
              f"l.{min(lectures)}")

    def test_EL5_CONTRE_EPREUVE_les_20_plans_ne_bougent_PAS(self):
        """⚠️⚠️ CE QUE CE LOT NE DOIT SURTOUT PAS DEPLACER, ET C'EST MESURE.
        Aucun des 20 plans livres ne declare de bloc `comportement` : ils
        s'arretent bien avant la garde, et ce qu'ils publient est
        rigoureusement inchange. *Une phrase de portee se mesure comme un
        chiffre* -- ce compteur rougira au premier plan qui declarera un
        comportement sans declarer ses chargements."""
        plan = _auto()
        df = _portefeuille(plan)
        etats, dispos = set(), set()
        for y in _plans_du_depot():
            p = PlanTarifaire.depuis_yaml(str(y))
            self.assertIsNone(
                getattr(p, 'comportement', None),
                f"le plan `{y.stem}` declare desormais un bloc "
                f"`comportement` : si ses `chargements` ne le sont pas, le "
                f"refus `ELA-2` va s'appliquer a un plan reel -- relire le "
                f"lot avant de livrer.")
            etat = EL.etat_elasticite(p, df)
            etats.add(etat.get('etat'))
            dispos.add(EL.sensibilite_tarifaire(p, df, etat).get('disponible'))
        self.assertEqual(etats, {EL.ELASTICITE_NON_FOURNIE},
                         f'les etats ont change : {etats}')
        self.assertEqual(dispos, {False}, f'`disponible` a change : {dispos}')
        print(f"    EL-5 contre-epreuve : {len(_plans_du_depot())} plans, "
              f"etat {etats}, disponible {dispos} -- inchange")


if __name__ == '__main__':
    unittest.main(verbosity=2)
