"""⚠️⚠️ LE SYSTÈME N'INVENTE JAMAIS UNE VALEUR À LA PLACE DE L'ACTUAIRE.

Étape ⑤-② du chantier 1-B, arbitrée par Selasse le 02/09/2026.

```
  30 expositions ABSENTES sur 1 000, AVANT l'arbitrage :
    exposition totale AVANT : 970,0
    exposition totale APRES : 1 000,0     <- 30 ANNEES inventees
    ce que le rapport signe en disait : RIEN
```

Les valeurs absentes étaient remplacées par la moyenne, **en silence**, et
entraient au dénominateur du tarif. *Une valeur absente est AMBIGUË : ni le
code ni la donnée ne savent si c'est un vrai zéro, une erreur de saisie ou une
grandeur inconnue. Choisir à la place de l'actuaire, c'est trancher une
question actuarielle par défaut.*

Le plan déclare désormais `valeurs_absentes`. **Non déclaré, le run s'arrête et
nomme les lignes** — patron déjà validé quatre fois (`unite_exposition`,
`Chargements`, `identifiant_contrat`, `echeance`).

⚠️ DEUX SURFACES, DEUX AUDIENCES — la doctrine de l'annexe jumelle
(`annexe_revue_charges_negatives`), généralisée aux trois grandeurs. La
SYNTHÈSE circule et ne porte qu'un COMPTE ; l'ANNEXE ne quitte pas le poste de
l'actuaire et porte **la position dans SON fichier**.

⚠️⚠️ ET LA POSITION EST POSITIONNELLE, JAMAIS L'ÉTIQUETTE. `VA-6` le plante :
même sur un dataframe indexé par des numéros de police, l'annexe rend des
rangs. *Aucun identifiant client ne peut fuir par ce canal.*

⚠️⚠️ PORTÉE ÉTENDUE AUX FACTEURS LE 02/09/2026, PAR ARBITRAGE DE SELASSE. Ce
texte disait : « les FACTEURS tarifaires restent imputés comme avant — Selasse
les a explicitement laissés hors de ce lot ». Il a ensuite ouvert les facteurs,
avec un régime **délibérément différent** :

```
  les 3 GRANDEURS   trou non declare -> le run S'ARRETE
  les ~160 FACTEURS trou non declare -> la ligne est EXCLUE, le run continue
```

*Arrêter sur trois colonnes protège le tarif ; arrêter sur cent soixante
rendrait tout fichier client imparfait intarifable.* `VA-9` ne tient donc plus
une limite, il tient une **distinction** — et `VA-11` à `VA-16` la peuplent.

⚠️⚠️ ET « ABSENT » NE VEUT PAS DIRE LA MÊME CHOSE SELON LE TYPE DÉCLARÉ.
`detecter_illisible` signifie *non convertible en nombre* : appliqué à un
facteur catégoriel il marque **100 % de la colonne**. Mesuré sur mon propre
correctif, il nommait **six facteurs au lieu d'un**, dont cinq intacts. `VA-12`
le plante. *Le type vient du PLAN, jamais du dtype.*

⚠️ La modalité inventée `'INCONNU'` a été **supprimée** dans le même lot
(`VA-16`) : *inventer une valeur catégorielle est le même geste qu'inventer une
valeur numérique — il est simplement plus difficile à voir, parce qu'il porte
un nom.*
"""
import ast
import contextlib
import dataclasses
import io
import logging
import pathlib
import unittest

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire
from core.qualite_donnees import (
    ROLES_GRANDEURS,
    ValeurAbsenteNonDeclaree,
    annexe_revue_facteurs_absents,
    annexe_revue_valeurs_absentes,
    empreinte_positions,
    exiger_valeurs_absentes_declarees,
    facteurs_valeurs_absentes,
    masque_lignes_facteurs_absents,
    synthese_qualite_donnees,
)
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
)
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_PLAN = PlanTarifaire.depuis_yaml(str(_RACINE / 'plans' / 'auto.yaml'))
_E, _F, _C = _PLAN.exposition, _PLAN.cible_frequence, _PLAN.cible_cout
_TROUS = [7, 42, 999]


def _cadre(n=1_000, seed=77, trous=None, col=None):
    rng = np.random.default_rng(seed)
    nb = rng.integers(0, 3, n).astype(float)
    df = pd.DataFrame({
        _E: np.ones(n), _F: nb,
        _C: np.where(nb > 0, rng.uniform(500, 5000, n).round(2), 0.0),
        'prime_acquise': (200 + np.arange(n) * 0.01).round(2)})
    if trous:
        df.loc[trous, col or _E] = np.nan
    return df


def _socle(df, plan):
    """A1 puis A2, muets. Rend le resultat d'A2."""
    with contextlib.redirect_stdout(io.StringIO()):
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            r1 = AgentA1Ingestion().run(sous_branche='auto',
                                        dataframe=df.copy(), plan=plan)
            return AgentA2Preprocessing().run(r1, plan=plan)
        finally:
            logging.disable(precedent)


class TestValeursAbsentesDeclarees(unittest.TestCase):

    def test_VA_1_non_declare_le_run_S_ARRETE_et_nomme_les_lignes(self):
        """⚠️⚠️ LE CŒUR DE L'ARBITRAGE : ne rien inventer, et le dire."""
        with self.assertRaises(ValeurAbsenteNonDeclaree) as ctx:
            exiger_valeurs_absentes_declarees(
                _cadre(trous=_TROUS), _PLAN)
        e = ctx.exception
        self.assertEqual(e.manquants, {'exposition': 3})
        self.assertEqual(e.total, 1_000)
        self.assertTrue(e.empreinte.startswith('r'))
        msg = str(e)
        self.assertIn("AUCUNE VALEUR N'A ETE INVENTEE", msg)
        self.assertIn('durée de couverture', msg,
                      "le message nomme une colonne technique au lieu de la "
                      "grandeur")
        self.assertIn('valeurs_absentes', msg, 'le message ne dit pas QUOI '
                                               'declarer')
        for issue in ('exclure', 'imputer_mediane', 'imputer_moyenne'):
            self.assertIn(issue, msg, f"l'issue '{issue}' n'est pas proposee")
        print(f"    OK VA-1 non declare : le run s'arrete, {e.manquants}, "
              f"empreinte {e.empreinte}")

    def test_VA_2_declare_exclure_les_lignes_SORTENT(self):
        """⚠️ Un euro bouge — et c'est l'actuaire qui l'a décidé, au plan."""
        plan = dataclasses.replace(_PLAN, valeurs_absentes='exclure')
        r2 = _socle(_cadre(trous=_TROUS), plan)
        self.assertTrue(r2.get('success'), r2.get('erreur'))
        df = r2['dataframe']
        self.assertEqual(len(df), 1_000 - len(_TROUS))
        self.assertEqual(int(df[_E].isna().sum()), 0)
        self.assertAlmostEqual(float(df[_E].sum()), 997.0, places=2)
        print(f"    OK VA-2 'exclure' : 1 000 -> {len(df)} lignes, "
              f"exposition totale {df[_E].sum():.2f}")

    def test_VA_3_la_STRATEGIE_vient_du_plan_jamais_du_nom_de_colonne(self):
        """⚠️⚠️ DÉRIVER LA STRATÉGIE D'UN NOM DE COLONNE, C'EST ENCORE CHOISIR.

        A2 classait la colonne par une table de mots-clés et en déduisait
        médiane ou moyenne. *L'actuaire a déclaré ; on obéit à sa déclaration,
        pas à une heuristique sur un nom.*
        """
        # ⚠️⚠️ LE TÉMOIN DOIT SÉPARER LES DEUX STRATÉGIES, SINON LE CONTRÔLE EST
        # DU DÉCOR. Ma première version utilisait une exposition constante à
        # 1,0 : médiane et moyenne y valaient toutes deux 1,0000, et le test
        # passait même si la déclaration était ignorée. *Un contrôle qui ne
        # peut pas distinguer les deux cas qu'il oppose ne prouve rien.* On
        # rend donc la distribution asymétrique.
        base = _cadre(trous=_TROUS)
        base.loc[100:199, _E] = 0.2
        attendu = {'imputer_mediane': float(base[_E].median()),
                   'imputer_moyenne': float(base[_E].mean())}
        self.assertNotAlmostEqual(
            attendu['imputer_mediane'], attendu['imputer_moyenne'], places=3,
            msg='mediane et moyenne coincident : le temoin ne separe rien')
        for choix, valeur in attendu.items():
            plan = dataclasses.replace(_PLAN, valeurs_absentes=choix)
            r2 = _socle(base, plan)
            self.assertTrue(r2.get('success'), r2.get('erreur'))
            df = r2['dataframe']
            self.assertEqual(len(df), 1_000, 'des lignes ont ete retirees')
            self.assertEqual(int(df[_E].isna().sum()), 0)
            for pos in _TROUS:
                self.assertAlmostEqual(float(df[_E].iloc[pos]), valeur,
                                       places=6,
                                       msg=f'{choix} : valeur non conforme')
        print(f"    OK VA-3 la valeur suit la declaration : "
              f"mediane {attendu['imputer_mediane']:.4f} / "
              f"moyenne {attendu['imputer_moyenne']:.4f}")

    def test_VA_4_le_rapport_SIGNE_dit_qu_aucune_valeur_n_a_ete_devinee(self):
        """⚠️⚠️ UNE INSTRUCTION SUIVIE EN SILENCE NE SE DISTINGUE PAS D'UNE
        INVENTION. Le rapport doit dire le compte, le geste, et QUI l'a
        décidé."""
        for choix, verbe in (('exclure', 'retirees'),
                             ('imputer_mediane', 'completees')):
            plan = dataclasses.replace(_PLAN, valeurs_absentes=choix)
            r2 = _socle(_cadre(trous=_TROUS), plan)
            texte = synthese_qualite_donnees(r2.get('rapport_qualite'))
            self.assertIsNotNone(texte, f'{choix} : le rapport se tait')
            self.assertIn("AUCUNE valeur n'a ete devinee", texte, choix)
            self.assertIn('SUR VOTRE INSTRUCTION', texte, choix)
            self.assertIn(f"valeurs_absentes='{choix}'", texte, choix)
            self.assertIn(verbe, texte, choix)
            self.assertIn('durée de couverture', texte, choix)
        print("    OK VA-4 le rapport signe nomme le geste, la grandeur et la "
              "declaration qui l'a decide")

    def test_VA_5_l_annexe_liste_les_positions_EXACTES(self):
        """⚠️ Une annexe qui ne désigne pas les bonnes lignes ne sert à rien —
        *un compte juste sur les mauvaises lignes reste faux.*"""
        ann = annexe_revue_valeurs_absentes(_cadre(trous=_TROUS), _PLAN)
        self.assertEqual([x['position'] for x in ann], _TROUS)
        for x in ann:
            self.assertEqual(x['grandeur'], 'exposition')
            self.assertEqual(x['colonne'], _E)
            self.assertEqual(sorted(x), ['colonne', 'grandeur', 'position'])
        # Les trois grandeurs, pas seulement l'exposition.
        multi = _cadre(trous=[3], col=_F)
        multi.loc[[8], _C] = np.nan
        roles = {x['grandeur'] for x in
                 annexe_revue_valeurs_absentes(multi, _PLAN)}
        self.assertEqual(roles, {'cible_frequence', 'cible_cout'})
        print(f"    OK VA-5 annexe : positions {_TROUS}, et les TROIS "
              f"grandeurs couvertes")

    def test_VA_6_RGPD_aucun_identifiant_client_ne_fuit_dans_l_annexe(self):
        """⚠️⚠️ LE PLANT RGPD EXIGÉ PAR SELASSE.

        On indexe le dataframe par des NUMÉROS DE POLICE et on ajoute une
        colonne d'identifiants. L'annexe doit rendre des RANGS, et ne porter
        aucune de ces valeurs.
        """
        df = _cadre(trous=_TROUS)
        df.index = [f'POLICE-{i:05d}' for i in range(len(df))]
        df['id_contrat'] = [f'CLIENT-{i:05d}' for i in range(len(df))]
        ann = annexe_revue_valeurs_absentes(df, _PLAN)
        self.assertEqual([x['position'] for x in ann], _TROUS,
                         "l'annexe ne rend plus des rangs")
        brut = str(ann)
        for grain in ('POLICE-', 'CLIENT-', 'id_contrat'):
            self.assertNotIn(grain, brut,
                             f'identifiant client dans l annexe : {grain!r}')
        for x in ann:
            self.assertIsInstance(x['position'], int)
        print("    OK VA-6 RGPD : dataframe indexe par des numeros de police, "
              "l'annexe rend des RANGS et aucun identifiant")

    def test_VA_7_la_synthese_CIRCULEE_ne_porte_aucune_position(self):
        """⚠️ Le rapport signé circule ; les positions restent sur le poste de
        l'actuaire. *Deux surfaces, deux audiences.*"""
        plan = dataclasses.replace(_PLAN, valeurs_absentes='exclure')
        r2 = _socle(_cadre(trous=_TROUS), plan)
        texte = synthese_qualite_donnees(r2.get('rapport_qualite')) or ''
        self.assertNotIn('999', texte, 'une POSITION fuit dans la synthese')
        self.assertNotIn('position', texte.lower(),
                         'la synthese parle de positions : elle doit rester '
                         'circulable')
        self.assertIn('3 ligne(s)', texte, 'le COMPTE a disparu')
        print("    OK VA-7 la synthese porte le compte, jamais une position")

    def test_VA_8_second_sens_un_fichier_SANS_trou_ne_declenche_RIEN(self):
        """⚠️⚠️ SANS CE SENS, LE REFUS ARRÊTERAIT TOUT LE MONDE.

        Les 20 plans actuels ne déclarent rien : si le refus se déclenchait
        sans valeur absente, **aucun tarif ne sortirait plus**.
        """
        self.assertIsNone(getattr(_PLAN, 'valeurs_absentes', None),
                          'le plan de reference declare : le temoin ne mesure '
                          'plus le cas courant')
        self.assertEqual(exiger_valeurs_absentes_declarees(_cadre(), _PLAN),
                         {})
        r2 = _socle(_cadre(), _PLAN)
        self.assertTrue(r2.get('success'), r2.get('erreur'))
        self.assertEqual(len(r2['dataframe']), 1_000)
        print("    OK VA-8 second sens : sans valeur absente, les 20 plans "
              "actuels tournent inchanges")

    def test_VA_9_DEUX_PORTES_un_ARRET_et_une_EXCLUSION_jamais_fondues(self):
        """⚠️⚠️ CE CONTROLE A CHANGE DE SENS LE 02/09/2026, ET C'EST UN
        ARBITRAGE DE SELASSE QUI L'A FAIT.

        Il s'appelait « la PORTEE est tenue, les facteurs restent hors lot » et
        prouvait que Selasse avait limite le lot aux trois grandeurs. Il a
        ensuite ouvert les FACTEURS, avec un regime DIFFERENT : un trou non
        declare y EXCLUT la ligne au lieu d'ARRETER le run.

        > *Arreter sur trois colonnes protege le tarif ; arreter sur cent
        > soixante rendrait tout fichier client imparfait intarifable.*

        Ce que le controle prouve reste EXACTEMENT le meme fait mecanique --
        la porte des grandeurs ignore les facteurs -- mais il dit desormais
        pourquoi : **deux portes, deux gestes, et les fondre effacerait la
        difference entre un arret que l'actuaire doit lever et une exclusion
        qu'il doit verifier.**
        """
        self.assertEqual(ROLES_GRANDEURS,
                         ('exposition', 'cible_frequence', 'cible_cout'))
        df = _cadre()
        facteur = next(f.nom for f in _PLAN.facteurs
                       if f.nom not in (_E, _F, _C))
        df[facteur] = 1.0
        df.loc[_TROUS, facteur] = np.nan
        self.assertEqual(
            exiger_valeurs_absentes_declarees(df, _PLAN), {},
            "un FACTEUR fait ARRETER le run : les deux portes sont fondues")
        # ⚠️ SECOND SENS : et la porte des FACTEURS, elle, le voit.
        self.assertEqual(
            facteurs_valeurs_absentes(df, _PLAN), {facteur: len(_TROUS)},
            "la porte des facteurs ne voit pas le trou : elle est du decor")
        print(f"    OK VA-9 deux portes : '{facteur}' ignore par l'ARRET, "
              f"vu par l'EXCLUSION ({len(_TROUS)} lignes)")

    def test_VA_11_un_facteur_troue_EXCLUT_la_ligne_sans_arreter_le_run(self):
        """⚠️⚠️ LE CŒUR DE L'ARBITRAGE : la ligne sort, le run continue.

        *Le systeme n'invente toujours rien ; il refuse de tarifer une ligne
        dont un facteur manque, plutot que de deviner ce facteur.*
        """
        base = _portefeuille_auto(600, seed=4)
        troue = base.copy()
        troue.loc[10:39, 'age'] = np.nan
        sain = _socle(base.copy(), _PLAN_AUTO)
        avec = _socle(troue, _PLAN_AUTO)
        self.assertEqual(len(sain['dataframe']), 600,
                         'le temoin sain perd deja des lignes')
        self.assertEqual(
            len(avec['dataframe']), 570,
            "les 30 lignes a facteur absent n'ont pas ete exclues")
        self.assertTrue(avec.get('success'),
                        'le run s est ARRETE : ce devait etre une exclusion')
        print(f"    OK VA-11 600 -> {len(avec['dataframe'])} lignes, le run "
              f"aboutit ; temoin sain intact a {len(sain['dataframe'])}")

    def test_VA_12_ABSENT_ne_veut_pas_dire_la_meme_chose_selon_le_TYPE(self):
        """⛔⛔ LE DEFAUT QUE LA MESURE A TROUVE DANS MON PROPRE CORRECTIF.

        `detecter_illisible` signifie *non convertible en nombre*. Applique a
        un facteur CATEGORIEL il marque **100 % de la colonne** : sur un
        temoin dont UNE colonne etait trouee, il nommait **six facteurs, dont
        cinq intacts**.

        > *Le rapport signe aurait dit « valeur absente sur `carburant`,
        > 1 000 lignes » d'une colonne pleine de « Essence » et « Diesel ».*

        Le type vient du PLAN, jamais du dtype.
        """
        df = _portefeuille_auto(200, seed=8)
        self.assertEqual(facteurs_valeurs_absentes(df, _PLAN_AUTO), {},
                         'le temoin sain nomme deja des facteurs : la '
                         'detection confond MODALITE et ABSENCE')
        cat = next(f.nom for f in _PLAN_AUTO.facteurs
                   if f.type == 'categoriel' and f.nom in df.columns)
        con = next(f.nom for f in _PLAN_AUTO.facteurs
                   if f.type == 'continu' and f.nom in df.columns)
        d2 = df.copy()
        d2.loc[0:4, cat] = None
        d2.loc[0:2, con] = np.nan
        comptes = facteurs_valeurs_absentes(d2, _PLAN_AUTO)
        self.assertEqual(comptes,
                         {con: 3, cat: 5} if con < cat else {cat: 5, con: 3})
        # ⚠️⚠️ LE COMPTE ET LES POSITIONS VIENNENT DU MEME MASQUE, ET LE SCEAU
        # A DU ME L'APPRENDRE. Le plant qui faisait diverger l'annexe ne
        # tombait sur AUCUN controle : `VA-14` ne trouait qu'un facteur
        # CONTINU, ou les deux detecteurs coincident. *Un temoin qui ne peut
        # pas distinguer les deux cas qu'il oppose ne prouve rien* -- c'est
        # la lecon de `VA-3`, reapprise sur un autre couple.
        annexe = annexe_revue_facteurs_absents(d2, _PLAN_AUTO)
        self.assertEqual(
            len(annexe), sum(comptes.values()),
            f"l'annexe rend {len(annexe)} position(s) pour "
            f"{sum(comptes.values())} absence(s) comptee(s) : le compte et "
            f"les positions ne viennent pas du meme masque, et un document "
            f"signe porterait les deux")
        self.assertEqual(
            sorted(x['facteur'] for x in annexe),
            sorted([cat] * 5 + [con] * 3),
            "l'annexe nomme des facteurs que le compte ignore")
        print(f"    OK VA-12 categoriel '{cat}' 5 absences (pas 200), "
              f"continu '{con}' 3, annexe {len(annexe)} positions du MEME "
              f"masque")

    def test_VA_13_le_rapport_SIGNE_nomme_le_facteur_le_compte_et_la_raison(
            self):
        """⚠️ *Un actuaire doit lire CE QU'IL VALIDE* : quel facteur, combien
        de lignes, ce qui leur est arrive, et pourquoi."""
        troue = _portefeuille_auto(500, seed=6)
        troue.loc[0:19, 'age'] = np.nan
        r2 = _socle(troue, _PLAN_AUTO)
        texte = synthese_qualite_donnees(r2.get('rapport_qualite')) or ''
        for attendu in ('age', '20 ligne(s)', 'EXCLUE(S)',
                        "n'invente pas", 'devinee'):
            self.assertIn(attendu, texte,
                          f"le rapport signe ne dit pas << {attendu} >>")
        print(f"    OK VA-13 le rapport nomme le facteur, le compte, le geste "
              f"et la raison ({len(texte)} car.)")

    def test_VA_14_RGPD_l_annexe_rend_des_RANGS_jamais_un_identifiant(self):
        """⚠️⚠️ MEME EXIGENCE QUE `VA-6`, SUR LE CANAL NEUF. Un index de
        dataframe peut porter un numero de police : la position est un RANG."""
        df = _portefeuille_auto(120, seed=2)
        df.index = [f'POLICE-{90000 + i}' for i in range(len(df))]
        df.loc[df.index[3], 'age'] = np.nan
        annexe = annexe_revue_facteurs_absents(df, _PLAN_AUTO)
        self.assertEqual(annexe, [{'position': 3, 'facteur': 'age'}])
        brut = repr(annexe)
        self.assertNotIn('POLICE', brut,
                         "un identifiant client fuit par l'annexe")
        print(f"    OK VA-14 RGPD : index 'POLICE-90003' -> rang 3, "
              f"0 identifiant dans {len(annexe)} entree(s)")

    def test_VA_15_tout_exclure_est_un_ARRET_jamais_un_portefeuille_vide(self):
        """⚠️⚠️ *Rendre zero ligne n'est pas une exclusion, c'est une panne.*

        Un agent aval prendrait un dataframe vide pour un portefeuille sans
        risque. Le systeme le DIT au lieu de le rendre.
        """
        df = _portefeuille_auto(80, seed=3)
        df['age'] = np.nan
        r2 = _socle(df, _PLAN_AUTO)
        # ⚠️⚠️ CE CONTROLE A ETE REECRIT APRES SA PREMIERE EXECUTION : il
        # attendait une levee, or `A2.run` CONVERTIT ses exceptions en
        # `success=False` -- son contrat etabli, le meme que sur une modalite
        # inconnue. *Un controle qui teste le mauvais canal echoue sur un code
        # juste, et j'aurais pu conclure au defaut inverse.*
        self.assertFalse(
            r2.get('success'),
            'A2 rend un succes sur un portefeuille entierement vide')
        msg = str(r2.get('erreur') or '')
        self.assertIn('age', msg)
        self.assertIn('viderait le portefeuille', msg)
        # ⚠️ Le dataframe rendu EST vide : c'est pourquoi l'echec doit etre
        # DECLARE. *Un appelant qui lirait `dataframe` sans lire `success`
        # tarifierait sur zero ligne.*
        self.assertEqual(len(r2.get('dataframe')), 0)
        print(f"    OK VA-15 facteur entierement vide -> success=False et la "
              f"cause est nommee ({len(msg)} car.)")

    def test_VA_17_le_COMPTE_publie_et_le_GESTE_viennent_du_MEME_masque(self):
        """⛔⛔ LE DEFAUT QUE J'AI LIVRE, ET QUE SELASSE M'A FAIT CHERCHER.

        A la question << est-ce que tout va bien avec certitude ? >>, la
        verification a trouve ceci : A2 excluait par `dropna`, qui ne voit que
        les vrais `NaN`, alors que le compte publie et l'annexe venaient de
        `_masque_absence_facteur`, qui voit AUSSI une chaine inconvertible sur
        un facteur `continu`.

        ```
          facteur `age` : 5 vrais vides + 4 chaines
            compte publie  : 9 lignes
            annexe publiee : 9 positions
            action reelle  : 5 lignes retirees
        ```

        > *Le rapport signe aurait annonce neuf exclusions dont quatre
        > n'avaient pas eu lieu -- et ces quatre lignes portaient un TEXTE dans
        > une colonne numerique du tarif.*

        ⚠️⚠️ SUR LE CHEMIN COMPLET, LA DIVERGENCE N'ETAIT PAS ATTEIGNABLE : A1
        coerce les types avant A2. **Mais rien ne gardait cette dependance.**
        Ce controle assemble donc A2 SANS A1 -- le cas que `agents/C1`
        documente deja -- parce que c'est la seule assiette ou l'invariant est
        reellement teste. *On ne compte pas sur un agent amont pour tenir un
        invariant qu'on peut rendre impossible ici.*
        """
        df = _portefeuille_auto(200, seed=5)
        df['age'] = df['age'].astype(object)
        df.loc[df.index[0:5], 'age'] = np.nan
        df.loc[df.index[10:14], 'age'] = 'non renseigne'
        compte = facteurs_valeurs_absentes(df, _PLAN_AUTO)
        self.assertEqual(compte, {'age': 9},
                         'le temoin ne separe plus les deux detecteurs')
        # ⚠️ La premisse EST le controle : `dropna` doit voir MOINS que le
        # compte, sinon le cas ne prouve rien.
        self.assertEqual(
            len(df.dropna(subset=['age'])), 195,
            "`dropna` voit autant que le compte : le temoin ne peut pas "
            'distinguer les deux sources')
        masque = masque_lignes_facteurs_absents(df, _PLAN_AUTO)
        self.assertEqual(int(np.asarray(masque, dtype=bool).sum()), 9)

        with contextlib.redirect_stdout(io.StringIO()):
            precedent = logging.root.manager.disable
            logging.disable(logging.CRITICAL)
            try:
                r2 = AgentA2Preprocessing().run(
                    {'dataframe': df.copy(), 'success': True}, plan=_PLAN_AUTO)
            finally:
                logging.disable(precedent)
        self.assertTrue(r2.get('success'), r2.get('erreur'))
        self.assertEqual(
            len(r2['dataframe']), 200 - 9,
            f"A2 a retire {200 - len(r2['dataframe'])} ligne(s) pour un compte "
            f"publie de 9 : le chiffre et le geste ne viennent pas de la meme "
            f"source, et le rapport signe annoncerait des exclusions qui n'ont "
            f"pas eu lieu")
        print(f"    OK VA-17 compte 9 = geste 9 (dropna n'en aurait vu que "
              f"{200 - len(df.dropna(subset=['age']))}), sans A1")

    def test_VA_16_la_modalite_inventee_INCONNU_a_disparu_du_CODE(self):
        """⚠️⚠️ ARBITRE PAR SELASSE : le systeme n'invente plus de modalite.

        Assiette : le CODE d'A2 par AST, docstrings et commentaires exclus --
        *une citation n'est pas une affirmation*, et ce fichier EXPLIQUE le
        retrait en nommant ce qui a ete retire.
        """
        src = (_RACINE / 'direction_non_vie' / 'tarification'
               / 'a2_preprocessing' / 'agent.py').read_text(encoding='utf-8')
        litteraux = [n.lineno for n in ast.walk(ast.parse(src))
                     if isinstance(n, ast.Constant) and n.value == 'INCONNU']
        self.assertEqual(
            litteraux, [],
            f"la modalite inventee 'INCONNU' subsiste dans le code "
            f"(ligne(s) {litteraux}) : le systeme fabrique encore une "
            f"modalite qu'aucun contrat ne porte")
        print("    OK VA-16 'INCONNU' absent du code d'A2 (0 litteral)")

    def test_VA_10_l_empreinte_change_si_le_fichier_change(self):
        """⚠️⚠️ CE QUI REND LA RÉPONSE OPPOSABLE. Si le fichier bouge et qu'on
        rejoue, la décision de l'actuaire **ne doit plus valoir** — et le
        système doit le DÉTECTER, pas le supposer."""
        e1 = empreinte_positions(_TROUS)
        e2 = empreinte_positions(_TROUS + [12])
        self.assertNotEqual(e1, e2)
        self.assertEqual(e1, empreinte_positions(list(reversed(_TROUS))),
                         "l'empreinte depend de l'ORDRE : elle mesurerait un "
                         "tri, pas un contenu")
        print(f"    OK VA-10 empreinte {e1} != {e2}, et stable par "
              f"permutation")


if __name__ == '__main__':
    unittest.main(verbosity=2)
