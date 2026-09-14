r"""TR-1..TR-7 — A6 RELAIE LE PRIX QU'IL BÂTIT.

A6 bâtissait un tarif, le mettait dans son PROPRE document, et ne le
donnait à personne : ses 53 clés de sortie n'en portaient aucune liée au
prix. Un appelant qui régénère un document — c'est ce que fait
`scripts/rapport_tarif_local.py` — ne pouvait pas le reconstituer, et
publiait un second document SANS PRIX. Mesure du 14/09/2026, même
portefeuille :

    document d'A6        prime pure PRÉSENTE, 409,22 EUR
    document régénéré    prime pure ABSENTE, `0,00 EUR` seul

*Le calcul atteignait une surface et une seule.* C'est le patron que
`PUBLICATION-1` prescrit, et qu'`anti_selection_a3` / `reserve_gini_a3`
appliquent déjà : **A6 relaie**.

⚠️⚠️ CE SCEAU MESURE PAR EXÉCUTION, ET CE N'EST PAS UN CONFORT. Le
relais s'écrit `_tmp_a6.update(_relais_prix)` et `**_relais_prix` : ni
l'un ni l'autre n'est une clé littérale. Un relevé par `ast.Dict` — la
méthode d'`EP-1`, à côté — rend **53 clés comme avant** et n'attesterait
RIEN. Je l'ai mesuré avant d'écrire ce fichier. *Un instrument qui ne
voit pas le geste ne peut pas l'attester.*

⚠️ `TR-6` PORTE LE SECOND SENS, ET C'EST LUI QUI COÛTE LE PLUS CHER À
TENIR : les documents signés ne doivent PAS bouger. Le relais pose des
clés que les trois surfaces ne lisent pas — relevé AST du 14/09 :
l'Excel A6 (30 clés lues), le rapport modèles (20) et le rapport
d'équipe (25) n'en lisent aucune. Le générateur, lui, reçoit ces valeurs
en PARAMÈTRES depuis toujours.
"""
import ast
import logging
import os
import pathlib
import sys
import tempfile
import unittest
import warnings

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../')))

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison

_RACINE = pathlib.Path(__file__).resolve().parent.parent.parent
_A6 = pathlib.Path(__file__).parent / 'a6_comparaison' / 'agent.py'

#: les cinq clés, par FAMILLE — chacune a son contrôle
_PRIX = ('tarif', 'portefeuille_tarife')
_COMPARAISON = ('comparaison_prix',)
_CONDITIONS = ('conditions_mesure',)
_DECISION = ('decision_actuaire',)
_TOUTES = _PRIX + _COMPARAISON + _CONDITIONS + _DECISION


def _sans_bruit(fn, *a, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return fn(*a, **kw)
        finally:
            logging.disable(precedent)


class _Chaine:
    """La chaîne A1→A6, jouée UNE fois pour tous les contrôles."""

    _cache = None

    @classmethod
    def resultat(cls):
        if cls._cache is not None:
            return cls._cache
        from demos.pipeline_3lob_a1_a6_demo import portefeuille_auto
        tmp = tempfile.mkdtemp(prefix='actuaria_tr_')
        plan = PlanTarifaire.depuis_yaml(
            str(_RACINE / 'plans' / 'auto.yaml'))
        df = portefeuille_auto(700, np.random.default_rng(2026))
        k = {'models_path': tmp, 'audit_path': tmp, 'verbose': False}

        def _jouer():
            r1 = AgentA1Ingestion(audit_path=tmp, verbose=False).run(
                branche='non_vie', sous_branche='auto', dataframe=df)
            r2 = AgentA2Preprocessing(audit_path=tmp, verbose=False).run(
                result_a1=r1, plan=plan)
            r3 = AgentA3GLM(**k).run(result_a2=r2, plan=plan,
                                     generer_graphiques=False)
            r4 = AgentA4ML(**k).run(result_a2=r2, result_a3=r3, plan=plan,
                                    calcul_shap=False,
                                    generer_graphiques=False)
            return AgentA6Comparaison(**k).run(
                result_a1=r1, result_a2=r2, result_a3=r3, result_a4=r4,
                result_a5=None, col_cible='nb_sinistres', plan=plan,
                generer_graphiques=False, generer_rapport_equipe=False,
                environnement='production',
                # ⚠️⚠️ `'Sceau TR'` A FAIT ROUGIR `RD-7`, ET LE GARDE AVAIT
                # RAISON : deux mots capitalisés dont aucun n'est un mot de
                # rôle, c'est la FORME exacte d'un « Prénom Nom ». Le
                # détecteur ne connaît aucun nom d'avance — il ne peut que
                # lire la forme, et cette forme-là était la mauvaise.
                # ⚠️ `'Sceau TR9'` serait passé, par la clause qui exempte
                # les jetons portant un chiffre. *Utiliser cette clause pour
                # faire taire le garde serait le contourner, pas le
                # satisfaire* — et affaiblir un garde-fou RGPD pour faire
                # passer son propre travail est ce qui est interdit ici en
                # premier. La valeur dit donc ce qu'elle est.
                profil_valide_par=(
                    'SCEAU AUTOMATISE TR - aucun actuaire responsable'))

        cls._cache = _sans_bruit(_jouer)
        return cls._cache


class TR1_LePrixEstRelaye(unittest.TestCase):
    """TR-1 — famille PRIX : le tarif et son assiette."""

    def test_TR1_SCEAU_le_tarif_et_son_assiette_sortent_d_A6(self):
        r6 = _Chaine.resultat()
        for cle in _PRIX:
            with self.subTest(cle=cle):
                self.assertIn(
                    cle, r6,
                    f"A6 a bati un tarif et ne relaie pas '{cle}' : un "
                    f"appelant qui regenere un document publiera un second "
                    f"document SANS PRIX, et rien ne le lui dira")
        self.assertIsNotNone(
            r6['tarif'],
            "`tarif` est relaye mais vaut None sur un dossier ou A6 a bien "
            "bati un tarif : le relais existe et ne porte rien")
        assiette = r6['portefeuille_tarife']
        self.assertIsInstance(
            assiette, pd.DataFrame,
            f"`portefeuille_tarife` n'est pas un DataFrame mais "
            f"{type(assiette).__name__} : le document ne pourra pas "
            f"l'utiliser")
        print(f"    TR-1 SCEAU : tarif={type(r6['tarif']).__name__}, "
              f"assiette {len(assiette):,} lignes")


class TR2_LaComparaisonEstRelayee(unittest.TestCase):
    """TR-2 — famille COMPARAISON."""

    def test_TR2_la_comparaison_de_prix_sort_d_A6(self):
        r6 = _Chaine.resultat()
        self.assertIn(
            'comparaison_prix', r6,
            "la comparaison de prix (critere E2) reste enfermee dans A6")
        print(f"    TR-2 comparaison_prix relayee : "
              f"{type(r6['comparaison_prix']).__name__}")


class TR3_LesConditionsSontRelayees(unittest.TestCase):
    """TR-3 — famille CONDITIONS DE MESURE."""

    def test_TR3_les_conditions_de_mesure_sortent_d_A6(self):
        r6 = _Chaine.resultat()
        self.assertIn('conditions_mesure', r6)
        valeur = r6['conditions_mesure']
        self.assertIsInstance(
            valeur, list,
            f"`conditions_mesure` AGREGE les declarations d'A3, A4 et A5 : "
            f"une liste est attendue, pas {type(valeur).__name__}")
        self.assertEqual(
            len(valeur), 3,
            f"l'agregat porte {len(valeur)} entree(s) au lieu de TROIS : un "
            f"agent a disparu de la collecte sans que rien ne le dise")
        print(f"    TR-3 conditions_mesure relayees : {len(valeur)} agent(s)")


class TR4_LaDecisionEstRelayee(unittest.TestCase):
    """TR-4 — famille DECISION D'ACTUAIRE."""

    def test_TR4_la_decision_d_actuaire_sort_d_A6(self):
        r6 = _Chaine.resultat()
        self.assertIn(
            'decision_actuaire', r6,
            "la decision d'actuaire transite par A6 et n'en ressort pas : "
            "un document regenere ne saurait pas qu'elle existe")
        print(f"    TR-4 decision_actuaire relayee "
              f"(valeur : {r6['decision_actuaire']!r})")


class TR5_UneSeuleEcritureDuRELAIS(unittest.TestCase):
    """TR-5 — l'ASSIETTE : une définition, deux poses."""

    def test_TR5_le_relais_est_ECRIT_une_fois_et_POSE_deux_fois(self):
        """⚠️⚠️ DEUX ECRITURES DIVERGERAIENT AU PREMIER AJOUT. C'est
        exactement ce qu'`EP-1` epingle a cote pour `elasticite` : une
        cle relayee dans UN seul des deux dicts, et la moitie des
        appelants ne voit rien."""
        arbre = ast.parse(_A6.read_text(encoding='utf-8'))
        ecritures = [n.lineno for n in ast.walk(arbre)
                     if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name)
                             and t.id == '_relais_prix' for t in n.targets)]
        self.assertEqual(
            len(ecritures), 1,
            f"`_relais_prix` est ecrit {len(ecritures)} fois (lignes "
            f"{ecritures}) : deux listes de cles divergeraient")
        poses = []
        for n in ast.walk(arbre):
            #: `_tmp_a6.update(_relais_prix)`
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'update'
                    and any(isinstance(a, ast.Name)
                            and a.id == '_relais_prix' for a in n.args)):
                poses.append(('update', n.lineno))
            #: `**_relais_prix` dans un dict litteral
            if isinstance(n, ast.Dict):
                for k, v in zip(n.keys, n.values):
                    if (k is None and isinstance(v, ast.Name)
                            and v.id == '_relais_prix'):
                        poses.append(('deballage', n.lineno))
        self.assertEqual(
            len(poses), 2,
            f"`_relais_prix` est pose {len(poses)} fois au lieu de DEUX "
            f"({poses}) : `_tmp_a6` alimente les livrables signes, le dict "
            f"final alimente les appelants — il en faut aux DEUX")
        print(f"    TR-5 assiette : 1 ecriture, 2 poses {poses}")


class TR6_LesDocumentsSignesNeBOUGENTpas(unittest.TestCase):
    """TR-6 — le SECOND SENS, et le plus cher à tenir."""

    def test_TR6_aucune_surface_signee_ne_lit_les_cles_relayees(self):
        """⚠️⚠️ SI UNE SURFACE LES LISAIT, LE DOCUMENT CHANGERAIT. Le
        relais rend des valeurs DISPONIBLES ; il ne doit rien ajouter au
        rendu. Le generateur, lui, recoit ces valeurs en PARAMETRES
        depuis toujours — c'est par la qu'elles atteignent le document,
        et ce chemin-la n'est pas touche."""
        services = pathlib.Path(__file__).parent / 'services'
        bases = {'result_a6', 'r6', 'resultat', 'res', 'a6'}
        fautifs = []

        def _base_ok(n):
            b = n.values[0] if isinstance(n, ast.BoolOp) and n.values else n
            return isinstance(b, ast.Name) and b.id in bases

        for p in sorted(services.glob('*.py')):
            arbre = ast.parse(p.read_text(encoding='utf-8'))
            for n in ast.walk(arbre):
                cle = None
                if (isinstance(n, ast.Subscript)
                        and isinstance(n.slice, ast.Constant)
                        and _base_ok(n.value)):
                    cle = n.slice.value
                elif (isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute)
                      and n.func.attr == 'get' and n.args
                      and isinstance(n.args[0], ast.Constant)
                      and _base_ok(n.func.value)):
                    cle = n.args[0].value
                if cle in _TOUTES:
                    fautifs.append(f"{p.name}:{n.lineno} -> {cle!r}")
        self.assertEqual(
            fautifs, [],
            f"{len(fautifs)} site(s) d'une surface signee lisent une cle "
            f"relayee SUR LE DICT D'A6 : le document change, et la "
            f"contre-epreuve << inchange octet pour octet >> tombe.\n  "
            + "\n  ".join(fautifs))
        print("    TR-6 second sens : 0 surface signee ne lit ces cles")


class TR7_LeRelaisNeRECALCULEpas(unittest.TestCase):
    """TR-7 — un relais transmet, il ne refait pas."""

    def test_TR7_les_cles_relayees_ne_sont_pas_des_appels(self):
        """⚠️ `portefeuille_tarife` et `conditions_mesure` etaient des
        EXPRESSIONS calculees au site d'appel du generateur. Les relayer
        en les reecrivant aurait fait DEUX calculs du meme fait. Elles
        sont desormais des variables, lues par l'appel ET par le relais.
        *Un relais qui recalcule n'est pas un relais, c'est une seconde
        source.*"""
        arbre = ast.parse(_A6.read_text(encoding='utf-8'))
        relais = None
        for n in ast.walk(arbre):
            if (isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name)
                            and t.id == '_relais_prix' for t in n.targets)):
                relais = n.value
        self.assertIsInstance(
            relais, ast.Dict, '`_relais_prix` n est pas un dict litteral')
        appels = []
        for k, v in zip(relais.keys, relais.values):
            nom = k.value if isinstance(k, ast.Constant) else '?'
            if any(isinstance(x, ast.Call) for x in ast.walk(v)):
                appels.append(f"{nom} = {ast.unparse(v)[:48]}")
        self.assertEqual(
            appels, [],
            f"{len(appels)} cle(s) du relais RECALCULENT au lieu de "
            f"transmettre : {appels}")
        noms = sorted(k.value for k in relais.keys
                      if isinstance(k, ast.Constant))
        self.assertEqual(
            noms, sorted(_TOUTES),
            f"le relais porte {noms} au lieu des cinq cles attendues")
        print(f"    TR-7 {len(noms)} cle(s) relayees, 0 recalcul")


if __name__ == '__main__':
    # ⚠️ LE BLOC EN FIN DE FICHIER — constat `COLLECTE-1`, sceau `GD-1..GD-4`.
    unittest.main(verbosity=2)
