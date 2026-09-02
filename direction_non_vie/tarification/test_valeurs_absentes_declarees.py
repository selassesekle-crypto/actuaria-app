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

⚠️ PORTÉE DE CE LOT : les trois grandeurs. Les FACTEURS tarifaires restent
imputés comme avant — Selasse les a explicitement laissés hors de ce lot, et
`VA-9` tient cette limite pour qu'elle ne dérive pas en silence.
"""
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
    annexe_revue_valeurs_absentes,
    empreinte_positions,
    exiger_valeurs_absentes_declarees,
    synthese_qualite_donnees,
)
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
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

    def test_VA_9_la_PORTEE_est_tenue_les_facteurs_restent_hors_lot(self):
        """⚠️ Selasse a limité ce lot aux trois grandeurs. *Une portée qui
        déborde en silence est une décision prise sans arbitrage.*"""
        self.assertEqual(ROLES_GRANDEURS,
                         ('exposition', 'cible_frequence', 'cible_cout'))
        df = _cadre()
        facteur = next(f.nom for f in _PLAN.facteurs
                       if f.nom not in (_E, _F, _C))
        df[facteur] = 1.0
        df.loc[_TROUS, facteur] = np.nan
        self.assertEqual(
            exiger_valeurs_absentes_declarees(df, _PLAN), {},
            "un FACTEUR declenche le refus : la portee du lot a deborde")
        print(f"    OK VA-9 portee tenue : un trou sur le facteur "
              f"'{facteur}' ne declenche rien")

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
