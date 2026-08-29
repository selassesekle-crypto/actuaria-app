"""Controles positifs — `a2/C7`, `a2/C8` et `a2/C17` : l'imputation d'A2.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────

═══ `a2/C7` + `a2/C8` — UN SEUL DEFAUT VU DES DEUX COTES ═══

`STRATEGIES_IMPUTATION` declare quatre strategies. Mesure du 29/08 (AST, tout
le depot) : **une seule occurrence, sa propre definition**. Personne ne la
lisait, et `_imputer` en reecrivait TROIS entrees en dur. La quatrieme,
`binaire -> mode`, n'existait donc **nulle part**.

Consequence mesuree sur une vraie fixture d'imputation (40 NaN) : une colonne
0/1 declaree `binaire` au plan recevait la **moyenne 0,8152** et sortait en
`[0.0, 0.8152, 1.0]` -- **40 lignes portant une valeur qui n'est pas une
modalite**. `_appliquer_facteur` ne l'arretait pas : il verifiait les modalites
pour l'encodage `label` et **rien** pour `binaire`.

⚠️⚠️ LE CONTROLE QUI COMPTE N'EST PAS « le binaire recoit le mode » -- c'est
**« la table est REELLEMENT lue »**. On change une entree de la table, et le
comportement doit suivre. *Aucun `grep` ne peut prouver ca ; une execution si.*

═══ `a2/C17` — UNE PROMESSE QUI NE TENAIT PAS ═══

La docstring de `_imputer` garantissait que les parametres calcules en 'train'
etaient reutilises en 'predict', « ce qui evite la fuite de donnees ». Mesure :
une colonne saine au train ne laissait aucun parametre, et le repli
`.get(col, df[col].mean())` **recalculait sur les donnees de predict** -- la
fuite exacte que la phrase disait eviter.

Le mecanisme etait mort (aucun appelant en 'predict', `charger_parametres` sans
appelant). Arbitrage : le **retirer avec sa promesse**, pas le reparer. Ces
tests epinglent l'absence -- sinon rien n'empeche la phrase de revenir.
"""

from __future__ import annotations

import dataclasses
import inspect
import logging
import unittest
import warnings
from unittest import mock

import numpy as np

from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing import agent as mod_a2
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
)
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)


#: Un binaire de SOURCE, ajoute au plan signe.
#: ⚠️ Les binaires du plan auto (`jeune_conducteur`...) sont DERIVES a l'etape 5,
#: apres l'imputation qui est l'etape 1 : ils ne portent jamais de NaN et ne
#: peuvent donc pas reproduire le constat. Le plan MRH du depot, lui, declare
#: `alarme`, `double_vitrage` et `garantie_vol` -- des colonnes de source.
def _plan_avec_binaire_source(nom: str = 'alarme'):
    modele = next(f for f in _PLAN_AUTO.facteurs if f.type == 'binaire')
    return dataclasses.replace(
        _PLAN_AUTO,
        facteurs=tuple(_PLAN_AUTO.facteurs)
        + (dataclasses.replace(modele, nom=nom),))


def _portefeuille_troue(n: int = 500, valeurs=None, graine: int = 11):
    """Un portefeuille avec des NaN dans QUATRE natures de colonnes.

    ⚠️ Sans NaN, `_imputer` sort avant d'imputer quoi que ce soit : mesurer sur
    des donnees propres ne prouve rien du tout. C'est ce qui avait fait conclure
    a tort que `a2/C8` et `a2/C9` n'etaient pas reproduits.
    """
    rng = np.random.default_rng(graine)
    df = _portefeuille_auto(n, seed=3)
    df['alarme'] = ((rng.random(n) < 0.79).astype(float) if valeurs is None
                    else valeurs)
    for col in ('alarme', 'age', 'valeur_venale', 'csp'):
        df.loc[df.index[rng.choice(n, 40, replace=False)], col] = np.nan
    return df


def _executer(df, plan):
    """A1 -> A2, le chemin de production."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            r1 = AgentA1Ingestion(audit_path='/tmp', verbose=False).run(
                branche='non_vie', sous_branche='auto', dataframe=df)
            a2 = AgentA2Preprocessing(
                models_path='/tmp', audit_path='/tmp', verbose=False)
            return a2, a2.run(result_a1=r1, plan=plan)
        finally:
            logging.disable(precedent)


def _imputees(resultat) -> dict:
    return ((resultat.get('rapport') or {})
            .get('transformations', {}).get('imputation', {})
            .get('colonnes_imputees', {}))


class TestLaTableEstLue(unittest.TestCase):
    """`a2/C7` — la declaration pilote le comportement, ou elle ne sert a rien."""

    def test_LA_TABLE_EST_REELLEMENT_LUE_on_change_une_entree(self):
        """⚠️⚠️ LE TEST QUI FERME `a2/C7`, ET AUCUN `grep` NE PEUT LE REMPLACER.

        On remplace `numerique_symetrique: 'mean'` par `'median'` dans la table
        declaree. Si `_imputer` la LIT, `age` bascule de « moyenne » a
        « mediane » et la valeur appliquee change. Si elle est recopiee en dur,
        rien ne bouge -- et c'etait le cas mesure le 29/08.
        """
        plan = _plan_avec_binaire_source()
        df = _portefeuille_troue()

        _, avant = _executer(df.copy(), plan)
        self.assertEqual(_imputees(avant)['age']['methode'], 'moyenne',
                         'premisse : la table declare `mean` pour un symetrique')

        table = dict(mod_a2.STRATEGIES_IMPUTATION)
        table['numerique_symetrique'] = 'median'
        with mock.patch.object(mod_a2, 'STRATEGIES_IMPUTATION', table):
            _, apres = _executer(df.copy(), plan)

        self.assertEqual(
            _imputees(apres)['age']['methode'], 'mediane',
            "la table a ete changee et le comportement n'a pas suivi : elle "
            "n'est donc pas lue, elle est recopiee en dur (`a2/C7`)")
        self.assertNotEqual(_imputees(avant)['age']['valeur'],
                            _imputees(apres)['age']['valeur'],
                            'meme methode annoncee, meme valeur : rien de reel '
                            "n'a change")
        print(f"    IMP-1 table modifiee -> `age` passe de "
              f"{_imputees(avant)['age']['methode']} "
              f"({_imputees(avant)['age']['valeur']:.3f}) a "
              f"{_imputees(apres)['age']['methode']} "
              f"({_imputees(apres)['age']['valeur']:.3f})")

    def test_les_QUATRE_categories_de_la_table_sont_atteintes(self):
        """⚠️ Une table dont trois entrees sur quatre sont mortes serait le
        meme defaut, en plus discret. On verifie que chaque categorie declaree
        est effectivement exercee par le chemin de production."""
        _, r = _executer(_portefeuille_troue(), _plan_avec_binaire_source())
        imp = _imputees(r)
        attendu = {
            'alarme':        'mode',      # binaire        (plan)
            'csp':           'mode',      # categorielle   (dtype)
            'valeur_venale': 'mediane',   # asymetrique    (nom)
            'age':           'moyenne',   # symetrique     (defaut)
        }
        for col, methode in attendu.items():
            with self.subTest(colonne=col):
                self.assertIn(col, imp, f'{col} devrait etre imputee')
                self.assertEqual(imp[col]['methode'], methode)
        self.assertEqual(
            set(mod_a2.STRATEGIES_IMPUTATION), {
                'numerique_asymetrique', 'numerique_symetrique',
                'categorielle', 'binaire'},
            'la table a change de forme : ce controle ne couvre plus ses '
            'entrees une par une')
        print("    IMP-2 les 4 categories declarees sont exercees : "
              + ', '.join(f'{c}={m}' for c, m in attendu.items()))


class TestLeBinaireResteBinaire(unittest.TestCase):
    """`a2/C8` — une colonne 0/1 imputee reste une colonne 0/1."""

    def test_un_binaire_du_plan_recoit_le_MODE_et_reste_binaire(self):
        """⚠️⚠️ LE TEST QUI FERME `a2/C8`.

        Le relevé mesurait la moyenne 0,8152 et une sortie `[0.0, 0.8152, 1.0]`.
        On epingle la PROPRIETE -- « les valeurs restent des modalites » -- pas
        le nombre 1.0, qui depend du portefeuille.
        """
        _, r = _executer(_portefeuille_troue(), _plan_avec_binaire_source())
        self.assertTrue(r.get('success'), r.get('message'))
        imp = _imputees(r)
        self.assertEqual(imp['alarme']['methode'], 'mode')
        self.assertGreater(imp['alarme']['nb_na'], 0,
                           'premisse : la colonne doit vraiment avoir des NaN')
        valeurs = set(r['dataframe']['alarme'].dropna().unique())
        self.assertTrue(
            valeurs <= {0.0, 1.0},
            f"la colonne binaire sort avec {sorted(valeurs)} : une valeur qui "
            f"n'est pas une modalite a ete introduite par l'imputation")
        print(f"    IMP-3 {imp['alarme']['nb_na']} NaN imputes par le mode "
              f"({imp['alarme']['valeur']}) — sortie "
              f"{[float(v) for v in sorted(valeurs)]}")

    def test_le_mode_est_range_sous_modes_pas_sous_medianes(self):
        """⚠️ Le mode d'un binaire est un MODE. Le ranger sous `medianes`
        aurait ajoute une occurrence a `a2/C9` au lieu d'en retirer."""
        a2, _ = _executer(_portefeuille_troue(), _plan_avec_binaire_source())
        self.assertIn('alarme', a2.parametres['modes'])
        self.assertNotIn('alarme', a2.parametres['medianes'])
        print("    IMP-4 le mode du binaire est trace sous `modes`")


class TestLaVerificationDeModalite(unittest.TestCase):
    """La contrepartie de `_verifier_modalites_connues`, cote `binaire`."""

    def test_une_valeur_HORS_MODALITE_fait_LEVER(self):
        """⚠️⚠️ LE SCEAU DU LOT — l'asymetrie corrigee.

        Un `label` a modalite inconnue levait ; un `binaire` ne passait par
        aucun controle. Desormais les deux levent.
        """
        df = _portefeuille_troue(
            valeurs=np.random.default_rng(4).integers(0, 3, 500).astype(float))

        # ① AU MECANISME : `_appliquer_plan` leve.
        a2 = AgentA2Preprocessing(
            models_path='/tmp', audit_path='/tmp', verbose=False)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with self.assertRaises(ValueError) as cm:
                a2._appliquer_plan(df.copy(), _plan_avec_binaire_source())
        message = str(cm.exception)
        self.assertIn('alarme', message)
        self.assertIn('HORS MODALITE', message)
        self.assertNotIn('np.float64', message,
                         "le message est lu par un actuaire, pas par un "
                         "interpreteur")

        # ② AU CHEMIN DE PRODUCTION : `run` n'explose pas, il ECHOUE PROPREMENT.
        # ⚠️ C'est le contrat d'agent, et c'est ce que l'actuaire voit. Epingler
        # seulement la levee aurait laisse passer une A2 qui plante le pipeline
        # au lieu de rendre un statut.
        _, r = _executer(df, _plan_avec_binaire_source())
        self.assertFalse(r.get('success'))
        self.assertEqual(r.get('statut_rag'), 'ROUGE')
        self.assertIn('HORS MODALITE', str(r.get('commentaire')),
                      "le motif n'atteint pas le commentaire : l'actuaire lit "
                      "un echec sans sa cause")
        print(f"    IMP-5 hors modalite -> leve au plan ET ROUGE au run : "
              f"{message[:76]}...")

    def test_SECOND_SENS_un_binaire_legitime_passe(self):
        """⚠️⚠️ SANS CE SENS, LE CONTROLE POURRAIT REFUSER TOUT LE MONDE.

        Un garde-fou qui bloque aussi les cas valides n'est pas un garde-fou :
        c'est une panne.
        """
        _, r = _executer(_portefeuille_troue(), _plan_avec_binaire_source())
        self.assertTrue(r.get('success'), r.get('message'))
        print("    IMP-6 second sens : un binaire 0/1 legitime passe (VERT)")

    def test_les_deux_verifications_sont_SYMETRIQUES(self):
        """⚠️ « Coherence entre les deux, pas juste un correctif de surface. »
        Les deux controles doivent lever le meme type d'erreur et nommer le
        facteur fautif -- sinon l'un est un garde-fou et l'autre un decor."""
        for nom in ('_verifier_modalites_connues', '_verifier_modalites_binaires'):
            with self.subTest(controle=nom):
                src = inspect.getsource(getattr(AgentA2Preprocessing, nom))
                self.assertIn('raise ValueError', src,
                              f'{nom} ne leve pas : il n arrete rien')
                self.assertIn("f.nom", src,
                              f'{nom} ne nomme pas le facteur fautif')
        print("    IMP-7 les deux verifications de modalite levent et nomment "
              "leur facteur")


class TestLeMecanismePredictAEteRetire(unittest.TestCase):
    """`a2/C17` — l'absence s'epingle, sinon la phrase revient."""

    def test_la_signature_de_run_n_a_plus_de_mode(self):
        parametres = inspect.signature(AgentA2Preprocessing.run).parameters
        self.assertNotIn(
            'mode', parametres,
            "le parametre `mode` est revenu : avec lui revient la branche "
            "'predict' qui recalculait sur les donnees de prediction")
        print(f"    IMP-8 `run` sans `mode` — parametres : "
              f"{[p for p in parametres if p != 'self']}")

    def test_charger_parametres_n_existe_plus(self):
        self.assertFalse(
            hasattr(AgentA2Preprocessing, 'charger_parametres'),
            'le chargeur de parametres est revenu sans appelant')
        print("    IMP-9 `charger_parametres` absent")

    def test_la_promesse_de_NON_FUITE_n_est_plus_AFFIRMEE(self):
        """⚠️⚠️ ON EPINGLE LA PHRASE QUI AFFIRME, PAS LE MOT.

        Le fichier PARLE encore de la fuite -- il explique pourquoi le
        mecanisme a ete retire, et c'est voulu. Ce qui ne doit plus exister,
        c'est l'AFFIRMATION que le code l'evite. *Un filet qui chercherait le
        mot « fuite » tomberait sur le commentaire qui raconte le retrait :
        il ne discriminerait pas.*
        """
        source = inspect.getsource(mod_a2)
        for affirmation in ("Cela évite la fuite",
                            "Cela evite la fuite",
                            "utilise les paramètres sauvegardés"):
            with self.subTest(phrase=affirmation):
                self.assertNotIn(
                    affirmation, source,
                    f"la promesse « {affirmation} » est revenue alors que la "
                    f"mesure du 29/08 l'a refutee")
        self.assertIn('a2/C17', source,
                      "le retrait doit rester racontable : sans sa raison "
                      "ecrite, quelqu'un remettra le mecanisme")
        print("    IMP-10 aucune promesse de non-fuite affirmee ; la raison du "
              "retrait est ecrite")


if __name__ == '__main__':
    unittest.main()
