"""⚠️⚠️ LA COUCHE REGARDE, ET ELLE N'APPLIQUE RIEN — 1-B-OBSERVATION.

Étape ④ du chantier 1-B, décidée par Selasse le 02/09/2026 : *le système
observe et publie honnêtement, sans encore rien bloquer ni exclure.*

> *Une décision qui déplace un prix se prend sur des fréquences réelles, pas
> sur une intuition.* Le chemin agent ne saura jamais s'il faut brancher la
> couche tant qu'il ne mesure pas ce qu'elle ferait.

⚠️⚠️ L'ASSIETTE EST TOUT LE SUJET, ET LA MESURE L'A TRANCHÉE. Sur un fichier à
30 expositions nulles + 60 fréquences négatives :

```
  observee AVANT A2 : exposition_non_positive 30 + frequence_negative 60
  observee APRES A2 :                              frequence_negative 60
```

A2 exclut **déjà** les expositions non positives. Observer avant lui aurait
fait publier « 30 lignes, et RIEN n'a été appliqué » sur des lignes que le
tarif ne porte plus — *un chiffre juste sur la mauvaise assiette dit une chose
fausse.* L'observation mesure **ce qui atteint le tarif** et que la couche
complète aurait écarté. `OB-4` le tient.

⚠️⚠️ ET LE DÉFAUT DE `qualite/C9` A REPARU UN CRAN PLUS HAUT. Ma première
version rendait `PHRASE_QUALITE_NON_EXECUTEE` dès que l'observation ne trouvait
rien — c'est-à-dire **sur un portefeuille sain**. « Observé, rien trouvé »
redisait « pas observé ». *C'est l'EXISTENCE de l'observation qui prouve que la
couche a tourné, jamais son contenu.* `OB-7` tient cette distinction.

⚠️ TROIS ÉTATS, ET LE TROISIÈME EST LE PLUS TRAÎTRE : **partiellement
exécuté**. A2 exclut les expositions non positives et le publiait seul — un
actuaire y lisait que la couche entière avait tourné. Les deux textes se
publient désormais côte à côte (`OB-6`), et ils ne disent pas la même chose :
l'un ce qui a ÉTÉ FAIT, l'autre ce qui AURAIT été fait.

⚠️ AUCUN EURO (`OB-8`) : `observer_qualite` rend un `dataframe_propre` à `None`
pour qu'aucun appelant ne puisse s'y tromper, et l'orchestrateur ne relit
jamais l'observation — vérifié par AST.
"""
import ast
import contextlib
import inspect
import io
import pathlib
import unittest

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire
from core.qualite_donnees import (
    MARQUEUR_QUALITE_NON_EXECUTEE,
    MARQUEUR_QUALITE_OBSERVEE,
    PHRASE_QUALITE_NON_EXECUTEE,
    controler_qualite,
    observer_qualite,
    synthese_qualite_donnees,
)
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
)

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_PLAN = PlanTarifaire.depuis_yaml(str(_RACINE / 'plans' / 'auto.yaml'))
_E, _F, _C = _PLAN.exposition, _PLAN.cible_frequence, _PLAN.cible_cout
_SERVICES = _RACINE / 'direction_non_vie' / 'tarification' / 'services'


def _cadre(n=1_000, seed=9, expo_nulles=0, freq_neg=0):
    rng = np.random.default_rng(seed)
    nb = rng.integers(0, 3, n).astype(float)
    cout = np.where(nb > 0, rng.uniform(500, 5000, n).round(2), 0.0)
    df = pd.DataFrame({
        _E: np.ones(n), _F: nb, _C: cout,
        'prime_acquise': (200 + np.arange(n) * 0.01).round(2)})
    if expo_nulles:
        df.loc[:expo_nulles - 1, _E] = 0.0
    if freq_neg:
        df.loc[100:100 + freq_neg - 1, _F] = -1.0
        df.loc[100:100 + freq_neg - 1, _C] = 0.0
    return df


def _a1_a2(df):
    """Le socle du chemin agent, sans les modèles : A1 puis A2."""
    with contextlib.redirect_stdout(io.StringIO()):
        r1 = AgentA1Ingestion().run(sous_branche='auto', dataframe=df.copy(),
                                    plan=_PLAN)
        r2 = AgentA2Preprocessing().run(r1, plan=_PLAN)
    return r1, r2


def _codes(rapport):
    return {a.code: a.nb_lignes for a in
            ((rapport.exclusions or []) + (rapport.corrections or [])
             + (rapport.signalements or []))}


class TestObservationQualite(unittest.TestCase):

    def test_OB_1_l_observation_n_applique_RIEN(self):
        """⚠️⚠️ LE CŒUR DE L'ÉTAPE : elle voit tout, elle ne touche à rien."""
        df = _cadre(freq_neg=60)
        avant = df.copy()
        obs = observer_qualite(df, _PLAN)

        self.assertTrue(df.equals(avant),
                        "l'observation a MUTÉ le dataframe qu'on lui a donné")
        self.assertFalse(obs.bloque, "l'observation bloque")
        self.assertIsNone(
            obs.dataframe_propre,
            "l'observation rend un dataframe_propre : un appelant croirait "
            "tenir une donnée nettoyée")
        self.assertIsNone(
            obs.validee_par,
            "l'observation porte un validateur : aucun être humain n'a validé "
            "quoi que ce soit ici")
        self.assertIn('frequence_negative', _codes(obs))
        print(f"    OK OB-1 dataframe intact, bloque=False, "
              f"dataframe_propre=None, validee_par=None, "
              f"{len(_codes(obs))} anomalie(s) VUE(S)")

    def test_OB_2_elle_DELEGUE_les_regles_au_lieu_de_les_recopier(self):
        """⚠️ Une seconde implémentation des règles aurait divergé de la
        première — le défaut que cet audit a fermé cinq fois.

        Assiette : les APPELS du corps, par AST, docstring exclue.
        """
        src = inspect.getsource(observer_qualite).lstrip()
        corps = ast.parse(src).body[0].body[1:]
        appels = {n.func.attr if isinstance(n.func, ast.Attribute)
                  else getattr(n.func, 'id', '')
                  for x in corps for n in ast.walk(x)
                  if isinstance(n, ast.Call)}
        self.assertIn('controler_qualite', appels,
                      "l'observation ne délègue plus : elle réimplémente")
        interdits = {'detecter_negatifs', 'detecter_sup', 'detecter_illisible',
                     'detecter_non_entier'}
        self.assertEqual(
            interdits & appels, set(),
            f'elle recopie des détecteurs : {interdits & appels}')
        print("    OK OB-2 elle delegue a controler_qualite, 0 detecteur "
              "recopie")

    def test_OB_3_le_jeton_n_est_pas_un_nom_et_ne_ressort_JAMAIS(self):
        """⚠️⚠️ `controler_qualite` refuse un rapport complet sans signature dès
        que l'escalade se déclenche. L'observation en fournit une TECHNIQUE.

        *Un jeton qui ressemblerait à un nom finirait par être lu comme une
        validation.* Il ne doit apparaître nulle part dans ce qui se publie.
        """
        obs = observer_qualite(_cadre(freq_neg=60), _PLAN)
        self.assertTrue(obs.escalade_declenchee,
                        'le témoin ne déclenche plus : la mesure ne prouve rien')
        publie = (synthese_qualite_donnees(None, obs) or '')
        for grain in ('observation', '__'):
            self.assertNotIn(
                grain, publie.lower(),
                f"le jeton technique fuit dans le texte publié : {grain!r}")
        self.assertIsNone(obs.validee_par)
        print("    OK OB-3 jeton technique, absent du rapport et du texte")

    def test_OB_4_l_assiette_est_CE_QUI_ATTEINT_LE_TARIF(self):
        """⚠️⚠️ LA MESURE QUI A TRANCHÉ LA CONCEPTION.

        A2 exclut déjà les expositions non positives. Observer AVANT lui ferait
        publier « et RIEN n'a été appliqué » sur des lignes que le tarif ne
        porte plus. *Un chiffre juste sur la mauvaise assiette dit une chose
        fausse.*
        """
        df = _cadre(expo_nulles=30, freq_neg=60)
        r1, r2 = _a1_a2(df)
        avant = _codes(observer_qualite(r1['dataframe'], _PLAN))
        apres = _codes(observer_qualite(r2['dataframe'], _PLAN))

        self.assertIn('exposition_non_positive', avant,
                      'le témoin ne porte pas le cas à mesurer')
        self.assertNotIn(
            'exposition_non_positive', apres,
            "A2 n'exclut plus les expositions non positives : l'assiette "
            "d'après A2 ne mesure plus ce qui atteint le tarif")
        self.assertEqual(apres.get('frequence_negative'), 60)

        # ⚠️⚠️ CE CONTRÔLE A ÉTÉ DU DÉCOR, ET LE SCEAU L'A DÉMASQUÉ. Sa
        # première version lisait l'APPEL — `observer_qualite(_df_obs, ...)` —
        # puis y remplaçait `_df_obs` par `r2` avant de chercher `r2` : elle
        # était donc VRAIE quoi qu'il arrive, y compris sur `r1`. *Un contrôle
        # qui regarde le nom de la variable au lieu de sa SOURCE ne mesure
        # rien.* L'assiette est l'AFFECTATION.
        src = pathlib.Path(
            _RACINE / 'direction_non_vie' / 'tarification'
            / 'pipeline_agents.py').read_text(encoding='utf-8')
        arbre = ast.parse(src)
        appel = [n for n in ast.walk(arbre) if isinstance(n, ast.Call)
                 and getattr(n.func, 'id', '') == 'observer_qualite']
        self.assertEqual(len(appel), 1, 'un seul site d observation attendu')
        argument = ast.unparse(appel[0].args[0])
        source = [ast.unparse(n.value) for n in ast.walk(arbre)
                  if isinstance(n, ast.Assign)
                  and any(getattr(t, 'id', '') == argument
                          for t in n.targets)]
        self.assertEqual(
            len(source), 1,
            f'{argument} est affecte {len(source)} fois : assiette ambigue')
        self.assertIn(
            'r2', source[0],
            f"l'observation porte sur `{source[0]}` : ce n'est pas la sortie "
            f"d'A2, donc pas ce qui atteint le tarif")
        self.assertNotIn(
            'r1', source[0],
            "l'observation porte sur la sortie d'A1 : elle compterait des "
            "lignes qu'A2 a deja exclues")
        print(f"    OK OB-4 avant A2 : {sorted(avant)} | apres A2 : "
              f"{sorted(apres)} -- l'assiette est ce qui atteint le tarif")

    def test_OB_5_le_texte_publie_CE_QU_IL_FAUT_POUR_DECIDER(self):
        """⚠️⚠️ C'est ce texte qui alimentera l'arbitrage de l'étape ⑤.

        *La liste des alertes qui doivent bloquer se décide sur des fréquences
        réelles.* Le texte doit donc porter, par anomalie : le code, la règle,
        le nombre de lignes, la proportion — et **si elle aurait escaladé**.
        """
        obs = observer_qualite(_cadre(freq_neg=60), _PLAN)
        txt = synthese_qualite_donnees(None, obs)
        self.assertIsNotNone(txt)
        self.assertIn(MARQUEUR_QUALITE_OBSERVEE, txt)
        self.assertIn('RIEN', txt)
        self.assertIn('frequence_negative', txt)
        self.assertIn('regle 1', txt)
        self.assertIn('60 ligne(s)', txt)
        self.assertRegex(txt, r'\d+[.,]\d+%')
        self.assertIn('AURAIT BLOQUE', txt,
                      "le texte ne dit pas que le seuil aurait ete franchi")
        self.assertIn('AU-DESSUS du seuil', txt)

        calme = observer_qualite(_cadre(freq_neg=5), _PLAN)
        txt2 = synthese_qualite_donnees(None, calme) or ''
        self.assertIn("n'aurait pas bloque", txt2,
                      'le second regime (sous le seuil) ne se dit pas')
        self.assertNotIn('AU-DESSUS du seuil', txt2)
        print("    OK OB-5 code, regle, lignes, proportion et VERDICT "
              "d'escalade -- dans les deux regimes")

    def test_OB_6_le_TROISIEME_ETAT_les_deux_textes_se_publient(self):
        """⚠️⚠️ PARTIELLEMENT EXÉCUTÉ — l'état que l'audit n'avait pas nommé.

        A2 exclut les expositions non positives et publiait cela **seul** : un
        actuaire y lisait que la couche entière avait tourné. Les deux se
        publient désormais, et ils ne disent pas la même chose.
        """
        df = _cadre(expo_nulles=30, freq_neg=60)
        r2 = _a1_a2(df)[1]
        obs = observer_qualite(r2['dataframe'], _PLAN)
        txt = synthese_qualite_donnees(r2.get('rapport_qualite'), obs)

        self.assertIsNotNone(r2.get('rapport_qualite'),
                             "A2 ne publie plus son rapport partiel")
        self.assertIn('EXCLUE(S)', txt, 'ce qui a ETE FAIT a disparu')
        self.assertIn(MARQUEUR_QUALITE_OBSERVEE, txt,
                      "ce qui AURAIT ete fait a disparu")
        self.assertLess(
            txt.index('EXCLUE(S)'), txt.index(MARQUEUR_QUALITE_OBSERVEE),
            'le fait accompli doit preceder l hypothetique')
        print("    OK OB-6 les 2 textes coexistent : ce qui a ete fait, puis "
              "ce qui aurait pu l etre")

    def test_OB_7_observe_sans_rien_trouver_SE_TAIT_et_ne_ment_pas(self):
        """⚠️⚠️ LE DÉFAUT DE `qualite/C9` A REPARU UN CRAN PLUS HAUT.

        Ma première version rendait `PHRASE_QUALITE_NON_EXECUTEE` dès que
        l'observation ne trouvait rien — c'est-à-dire sur un portefeuille sain.
        *« Observé, rien trouvé » redisait « pas observé ».*

        C'est l'EXISTENCE de l'observation qui prouve que la couche a tourné,
        jamais son contenu.
        """
        sain = observer_qualite(_cadre(), _PLAN)
        self.assertEqual(_codes(sain), {},
                         'le témoin sain porte des anomalies')
        txt = synthese_qualite_donnees(None, sain)
        self.assertIsNone(
            txt,
            f"une couche qui a observé et n'a rien vu doit se TAIRE ; "
            f"elle publie : {txt!r}")
        self.assertNotEqual(txt, PHRASE_QUALITE_NON_EXECUTEE)
        print("    OK OB-7 observe + rien trouve = silence, jamais "
              "<< non execute >>")

    def test_OB_8_aucun_euro_l_observation_n_est_JAMAIS_relue(self):
        """⚠️⚠️ « AUCUN EURO » SE PROUVE PAR LA STRUCTURE.

        Si l'orchestrateur relisait l'observation — son `dataframe_propre`,
        ses index — il déplacerait des lignes. Il ne doit que la TRANSPORTER.
        """
        src = pathlib.Path(
            _RACINE / 'direction_non_vie' / 'tarification'
            / 'pipeline_agents.py').read_text(encoding='utf-8')
        usages = [ast.unparse(n) for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.Name) and n.id == '_obs'
                  and isinstance(n.ctx, ast.Load)]
        self.assertEqual(
            len(usages), 1,
            f'`_obs` est relu {len(usages)} fois : il doit seulement transiter')
        attrs = [ast.unparse(n) for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Attribute)
                 and getattr(n.value, 'id', '') == '_obs']
        self.assertEqual(attrs, [],
                         f'l orchestrateur lit dans l observation : {attrs}')
        self.assertIsNone(observer_qualite(_cadre(freq_neg=60), _PLAN)
                          .dataframe_propre)
        print("    OK OB-8 `_obs` transite (1 lecture, 0 attribut lu), "
              "dataframe_propre=None")

    def test_OB_9_second_sens_sans_observation_la_phrase_NON_EXECUTE_reste(
            self):
        """⚠️ Un correctif qui aurait fait disparaître `qualite/C9` en même
        temps aurait échangé un mensonge contre un silence."""
        self.assertEqual(synthese_qualite_donnees(None),
                         PHRASE_QUALITE_NON_EXECUTEE)
        self.assertEqual(synthese_qualite_donnees(None, None),
                         PHRASE_QUALITE_NON_EXECUTEE)
        propre = controler_qualite(_cadre(), _PLAN)
        self.assertIsNone(synthese_qualite_donnees(propre),
                          'un rapport propre sans observation doit se taire')
        print("    OK OB-9 second sens : sans observation, "
              "<< non execute >> subsiste")

    def test_OB_10_aucun_badge_VERT_sur_une_couche_non_appliquee(self):
        """⚠️⚠️ LA MÊME LEÇON QU'À `QNE-4`, SUR LE NOUVEAU MARQUEUR.

        Les deux Excel dérivent leur pastille du TEXTE. Publier « rien n'a été
        appliqué » sous une pastille VERTE serait pire que le silence.
        """
        obs = observer_qualite(_cadre(freq_neg=60), _PLAN)
        txt = synthese_qualite_donnees(None, obs)
        self.assertNotIn('EXCLUE(S)', txt,
                         'le texte declenche le badge par accident')
        for nom, ancre in (('tarif_excel.py', '_synth_q'),
                           ('rapport_equipe_tarif.py', '_synth_q6')):
            src = (_SERVICES / nom).read_text(encoding='utf-8')
            expr = next((ast.unparse(n) for n in ast.walk(ast.parse(src))
                         if isinstance(n, ast.IfExp) and 'AMBRE' in
                         ast.unparse(n) and ancre in ast.unparse(n)), None)
            self.assertIsNotNone(expr, f'{nom} : badge introuvable')
            self.assertIn('MARQUEUR_QUALITE_OBSERVEE', expr,
                          f'{nom} : le badge ignore la couche observee')
            ctx = {ancre: txt,
                   'MARQUEUR_QUALITE_OBSERVEE': MARQUEUR_QUALITE_OBSERVEE,
                   'MARQUEUR_QUALITE_NON_EXECUTEE':
                       MARQUEUR_QUALITE_NON_EXECUTEE}
            self.assertEqual(eval(expr, {}, ctx), 'AMBRE',
                             f'{nom} : couche non appliquee badgee VERTE')
        print("    OK OB-10 les 2 Excel badgent AMBRE la couche observee")

    def test_OB_11_l_observation_atteint_le_resultat_du_chemin_agent(self):
        """⚠️ Un calcul qui n'atteint aucun livrable n'existe pas — la leçon de
        `services/C7` et `socle/C1`. A6 la TRANSITE, comme `rapport_qualite`."""
        src = pathlib.Path(
            _RACINE / 'direction_non_vie' / 'tarification' / 'a6_comparaison'
            / 'agent.py').read_text(encoding='utf-8')
        arbre = ast.parse(src)
        params = [n for n in ast.walk(arbre)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and n.name == 'run'
                  and any(a.arg == 'observation_qualite' for a in n.args.args
                          + n.args.kwonlyargs)]
        self.assertTrue(params, "A6.run n'accepte pas l'observation")
        # ⚠️ On compte les CLÉS de dictionnaire, pas les mentions : le nom du
        # paramètre n'est pas une constante chaîne. *Ma première version
        # attendait 3 et mesurait 2 — le contrôle était faux, pas le code.*
        cles = [n for n in ast.walk(arbre)
                if isinstance(n, ast.Dict)
                for c in n.keys
                if isinstance(c, ast.Constant)
                and c.value == 'observation_qualite']
        self.assertEqual(
            len(cles), 2,
            f"A6 relaie l'observation dans {len(cles)} dict(s) de sortie au "
            f"lieu des DEUX -- une moitie des appelants ne la verrait pas")
        print(f"    OK OB-11 A6 accepte l'observation et la transite dans ses "
              f"{len(cles)} dicts de sortie")


if __name__ == '__main__':
    unittest.main(verbosity=2)
