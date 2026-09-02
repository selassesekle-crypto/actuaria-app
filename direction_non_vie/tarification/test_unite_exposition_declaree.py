"""Controles positifs — chantier `unite_exposition`, ETAPE 2 : le plan DECLARE
l'unite, et la borne de plausibilite en DERIVE.

CE QUE CE FICHIER PROUVE, ET CE QUE L'ETAPE FERME
──────────────────────────────────────────────────

⚠️⚠️ LE DEFAUT, CONSTAT `qualite/C3`. Le plan declarait le ROLE de l'exposition
-- quelle colonne -- et JAMAIS son unite. Les deux chemins plafonnaient donc a
1,0 sur une hypothese ANNUELLE que rien n'avait verifiee. Mesure du 30/08 sur
un portefeuille exprime en mois :

```
  exposition totale : 10 083 -> 1 000   (-90,1 %)
  et l'exposition est le DENOMINATEUR de la frequence et de la prime pure :
  la prime est donc MULTIPLIEE PAR 10,08.
```

*L'actuaire validait une ligne de rapport et obtenait un tarif multiplie par
dix.* Le plan se disait opposable sur une grandeur dont il ne disait pas
l'unite.

═══ LES QUATRE PIECES, ET POURQUOI AUCUNE NE PEUT MANQUER ═══

| # | piece | sans elle |
|---|---|---|
| A | `unite_exposition` au plan, ensemble ferme, inconnue LEVE | un champ qui promet |
| B | la borne DERIVE de l'unite, aux deux chemins | l'unite serait decorative |
| C | non declaree -> hypothese annuelle **DITE** | le defaut d'origine, intact |
| D | donnee qui CONTREDIT l'unite -> SIGNALEE | declarer `mois` desactiverait le controle |

⚠️⚠️ **D EST LA PIECE QU'ON OUBLIE.** Declarer `mois` porte la borne a 12 :
plus rien ne peut etre attrape, et une declaration FAUSSE passe pour une
declaration juste. *Un instrument qui ne peut plus rien signaler cesse d'etre
un instrument.* Le signal se derive ENTIEREMENT de l'ensemble ferme -- l'unite
apparente est la plus grossiere dont la borne contient le maximum observe --
**il n'y a aucun seuil invente a justifier.**

⚠️ D SIGNALE, NE CORRIGE JAMAIS (regle 3). Un portefeuille d'assistance dont
tous les contrats durent moins d'un mois ressemble legitimement a des annees :
c'est a l'actuaire de trancher. Il escalade cependant comme toute anomalie
touchant >= 5 % des lignes -- une unite fausse mesestime TOUT le portefeuille --
et l'echappatoire nominative reste la voie normale.

═══ CE QUE CE LOT DEPLACE, ET CE QU'IL NE DEPLACE PAS ═══

⚠️⚠️ AUCUN EURO SUR L'EXISTANT, ET C'EST MESURE. A l'etape 2 : **0 des 20 plans
ne declarait d'unite**, donc la borne valait partout `PLAFOND_EXPOSITION`.
**L'ETAPE 5 a fait declarer `annee` aux 20**, et la preuve est devenue plus
forte : ils declarent tous une unite **dont la borne EST le plafond annuel**.
`UX-4` compare la borne OBTENUE, jamais la seule chaine declaree -- *c'est la
borne qui decide d'un prix.* Le comportement n'a pas change ; il a cesse d'etre
suppose.

⚠️ ET SIX CONTROLES SONT TOMBES LE JOUR DE L'ETAPE 5, tous pour la meme raison :
ils testaient la branche << unite non declaree >> en EMPRUNTANT le plan `auto`
du depot. *Un cas qui doit exister independamment du depot se CONSTRUIT
(`_SANS_UNITE`), il ne s'emprunte pas a un fichier qui peut changer sous lui.*
La branche existe toujours -- un plan client peut ne rien declarer.

⚠️⚠️ MAIS IL DEPLACE UN TEXTE PUBLIE, DELIBEREMENT. Le message de la regle 2
porte desormais la phrase C. *C'est le but du constat `qualite/C3` : rendre
l'hypothese visible avant la signature.* Le libelle de correction
(« plafond a 1.0 ») est en revanche inchange, verifie.

⚠️⚠️ ET IL BUMPE `EMPREINTE_SCHEMA` 1 -> 2. `unite_exposition` entre dans le
payload : elle decide d'un prix, donc elle est opposable. *L'alternative --
n'inclure le champ que s'il est declare -- aurait rendu la COMPOSITION du
payload dependante du CONTENU, detruisant la distinction meme que
`EMPREINTE_SCHEMA` existe pour porter.* Mesure faite avant : aucune empreinte
`s1:` persistee dans `models/` ni `data/`.
"""

from __future__ import annotations

import dataclasses
import logging
import unittest
import warnings

from core.plan_tarifaire import (
    _UNITES_EXPOSITION,
    EMPREINTE_SCHEMA,
    PlanTarifaire,
    UniteExposition,
)
from core.qualite_donnees import (
    BORNES_EXPOSITION,
    PLAFOND_EXPOSITION,
    borne_exposition,
    controler_qualite,
    unite_apparente,
)
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
)
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)

_PLAN = PlanTarifaire.depuis_yaml('plans/auto.yaml')

#: ⚠️⚠️ CONSTRUIT, JAMAIS LU AU DEPOT — et l'etape 5 explique pourquoi. Ces
#: controles testaient la branche << unite non declaree >> en prenant le plan
#: `auto` du depot, qui n'en declarait pas. L'etape 5 a fait declarer `annee`
#: aux 20 plans : six controles sont tombes d'un coup. **La branche existe
#: toujours** -- un plan client peut ne rien declarer -- mais son cas doit etre
#: CONSTRUIT, pas emprunte a un fichier qui peut changer sous lui.
_SANS_UNITE = dataclasses.replace(_PLAN_AUTO, unite_exposition=None)


def _sans_bruit(fn, *a, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return fn(*a, **kw)
        finally:
            logging.disable(precedent)


def _en_mois(n=400, seed=3):
    df = _portefeuille_auto(n, seed=seed)
    df['exposition'] = df['exposition'] * 12
    return df


def _a2(df, plan):
    """A1 puis A2, comme le chemin agent les enchaine reellement."""
    def _run():
        r1 = AgentA1Ingestion(audit_path='/tmp', verbose=False).run(
            dataframe=df, branche='non_vie', sous_branche='auto')
        return AgentA2Preprocessing(audit_path='/tmp', verbose=False).run(
            r1, plan=plan)
    return _sans_bruit(_run)


def _anos(rapport):
    return [*rapport.exclusions, *rapport.corrections, *rapport.signalements]


def _code(rapport, code):
    return next((a for a in _anos(rapport) if a.code == code), None)


# ═══════════════════════════════════════════════════════════════════════════════
#  A — LA DECLARATION
# ═══════════════════════════════════════════════════════════════════════════════
class TestLePlanDeclareLUnite(unittest.TestCase):

    def test_LE_TEST_QUI_FERME_le_plan_porte_l_unite_et_elle_est_opposable(self):
        """⚠️⚠️ Le champ existe, il est dans l'EMPREINTE, et l'empreinte bouge
        avec lui. *Un champ qui decide d'un prix hors de l'empreinte rendrait
        `IDENTIQUE` pour deux plans qui tarifent differemment.*"""
        self.assertIn('unite_exposition',
                      {f.name for f in dataclasses.fields(PlanTarifaire)})
        a = dataclasses.replace(_PLAN, unite_exposition='annee').empreinte()
        b = dataclasses.replace(_PLAN, unite_exposition='mois').empreinte()
        c = dataclasses.replace(_PLAN, unite_exposition=None).empreinte()
        self.assertNotEqual(a, b, "l'unite ne bouge pas l'empreinte : elle "
                                  "n'est donc pas opposable")
        self.assertNotEqual(a, c)
        # ⚠️⚠️ DERIVE, PLUS ECRIT EN DUR. J'avais fige `s2:` ici dans le lot
        # meme ou je denoncais un litteral `s1:` ailleurs et le derivais.
        # Le bump `2` -> `3` des trois portes l'a fait rougir. *Ce que je
        # corrige chez le voisin, je dois le corriger chez moi.*
        prefixe = f's{EMPREINTE_SCHEMA}:'
        self.assertTrue(all(x.startswith(prefixe) for x in (a, b, c)))
        print(f"    UX-1 l'unite est DANS l'empreinte : annee={a} mois={b}")

    def test_une_unite_inconnue_LEVE_avec_l_attendu_nomme(self):
        """⚠️ SECOND SENS. Un defaut silencieux sur un champ qui decide d'un
        prix est ce que `a6/C9` a ferme -- on ne le rouvre pas."""
        with self.assertRaises(ValueError) as leve:
            dataclasses.replace(_PLAN, unite_exposition='semaine')
        msg = str(leve.exception)
        self.assertIn('unite_exposition', msg)
        for admise in sorted(_UNITES_EXPOSITION):
            self.assertIn(repr(admise), msg,
                          "le message doit NOMMER les valeurs admises")
        print(f"    UX-2 valeur inconnue -> ValueError nommant "
              f"{sorted(_UNITES_EXPOSITION)}")

    def test_l_absence_reste_un_ETAT_legitime(self):
        """⚠️ « Non declaree » et « declaree a tort » sont DEUX etats. Le
        premier conserve le comportement d'aujourd'hui, et il reste ATTEIGNABLE
        meme apres l'etape 5 : un plan client peut ne rien declarer."""
        self.assertIsNone(_SANS_UNITE.unite_exposition)
        self.assertEqual(borne_exposition(_SANS_UNITE), PLAFOND_EXPOSITION)
        print("    UX-3 unite absente : borne = plafond annuel, inchangee")

    def test_LE_TEST_QUI_FERME_L_ETAPE_5_les_20_plans_declarent_annee(self):
        """⚠️⚠️ CE CONTROLE A CHANGE DE SENS AVEC L'ETAPE 5, ET IL PROUVE LA
        MEME CHOSE : *aucun euro*. Il verifiait que **0 / 20** plans declaraient
        une unite -- la borne valait donc partout le plafond annuel. Les 20 la
        declarent desormais, et la preuve devient plus forte : ils declarent
        tous `annee`, **dont la borne EST le plafond annuel**. Le comportement
        n'a pas change, il a cesse d'etre suppose.

        ⚠️ On compare la borne OBTENUE, jamais la seule chaine declaree : c'est
        la borne qui decide d'un prix.
        """
        import glob
        fichiers = sorted(glob.glob('plans/*.yaml'))
        plans = {f: PlanTarifaire.depuis_yaml(f) for f in fichiers}
        muets = [f for f, p in plans.items() if p.unite_exposition is None]
        self.assertEqual(muets, [],
                         f"{len(muets)} plan(s) ne declarent toujours pas leur "
                         f"unite -> {muets}")
        bornes = {borne_exposition(p) for p in plans.values()}
        self.assertEqual(
            bornes, {PLAFOND_EXPOSITION},
            f"les plans du depot n'ont plus tous la borne annuelle : {bornes}. "
            f"L'etape 5 devait etre sans euro PAR CONSTRUCTION.")
        print(f"    UX-4 {len(fichiers)} / {len(fichiers)} plans declarent "
              f"leur unite, borne obtenue = {bornes} (inchangee)")


# ═══════════════════════════════════════════════════════════════════════════════
#  B — LA BORNE EN DERIVE, AUX DEUX CHEMINS
# ═══════════════════════════════════════════════════════════════════════════════
class TestLaBorneDeriveDeLUnite(unittest.TestCase):

    def test_toute_unite_admise_a_SA_borne(self):
        """⚠️⚠️ Une correspondance ne se DERIVE pas d'un `Literal` : on
        controle donc l'EGALITE des deux ensembles. *Ajouter une unite sans sa
        borne doit faire rougir la gate, pas lever en production.*"""
        self.assertEqual(set(BORNES_EXPOSITION), set(_UNITES_EXPOSITION))
        self.assertEqual(BORNES_EXPOSITION['annee'], PLAFOND_EXPOSITION)
        print(f"    UX-5 bornes et unites admises coincident : "
              f"{ {k: v for k, v in sorted(BORNES_EXPOSITION.items())} }")

    def test_LES_DEUX_CHEMINS_derivent_la_MEME_borne(self):
        """⚠️⚠️ LE JUMEAU. Meme fichier en mois, meme plan `unite='mois'` :
        aucun des deux chemins ne doit plafonner. *Avant l'etape 1d, la borne
        vivait a deux endroits et un seul aurait suivi.*"""
        plan = dataclasses.replace(_PLAN_AUTO, unite_exposition='mois')
        rq = _sans_bruit(controler_qualite, _en_mois(), plan, horodatage='t')
        self.assertIsNone(_code(rq, 'exposition_sup_1'),
                          'le chemin declaratif plafonne encore a 1.0')
        r2 = _a2(_en_mois(), plan)
        self.assertGreater(float(r2['dataframe']['exposition'].max()), 1.0,
                           'le chemin agent plafonne encore a 1.0')
        print(f"    UX-6 unite='mois' : declaratif max="
              f"{rq.dataframe_propre['exposition'].max():.4f} · agent max="
              f"{float(r2['dataframe']['exposition'].max()):.4f}")

    def test_second_sens_sans_unite_les_deux_plafonnent_COMME_HIER(self):
        """⚠️ Sans ce sens, `UX-6` passerait aussi si la borne etait devenue
        infinie et que plus rien n'etait jamais corrige."""
        rq = _sans_bruit(controler_qualite, _en_mois(), _PLAN_AUTO,
                         horodatage='t', qualite_validee_par='X')
        a = _code(rq, 'exposition_sup_1')
        self.assertIsNotNone(a, 'plus rien ne plafonne sans unite declaree')
        self.assertEqual(a.correction, 'plafond a 1.0')
        self.assertAlmostEqual(
            float(rq.dataframe_propre['exposition'].max()), 1.0, places=9)
        r2 = _a2(_en_mois(), _PLAN_AUTO)
        self.assertAlmostEqual(
            float(r2['dataframe']['exposition'].max()), 1.0, places=9)
        print(f"    UX-7 sans unite : les DEUX plafonnent a 1.0, "
              f"correction={a.correction!r} inchangee")


# ═══════════════════════════════════════════════════════════════════════════════
#  C — L'HYPOTHESE ANNUELLE EST DITE
# ═══════════════════════════════════════════════════════════════════════════════
class TestLHypotheseEstPUBLIEE(unittest.TestCase):

    def test_unite_absente_le_message_le_DIT_et_dit_la_consequence(self):
        rq = _sans_bruit(controler_qualite, _en_mois(), _SANS_UNITE,
                         horodatage='t', qualite_validee_par='X')
        d = _code(rq, 'exposition_sup_1').description
        self.assertIn('UNITE NON DECLAREE', d)
        self.assertIn('ANNUELLE', d)
        self.assertIn('unite_exposition', d)
        self.assertIn('denominateur', d)
        print("    UX-8 hypothese annuelle DITE, avec sa consequence sur la "
              "prime")

    def test_unite_declaree_la_phrase_DISPARAIT(self):
        """⚠️⚠️ SECOND SENS, et il compte : *un avertissement permanent est un
        avertissement qu'on cesse de lire.*"""
        plan = dataclasses.replace(_PLAN_AUTO, unite_exposition='annee')
        rq = _sans_bruit(controler_qualite, _en_mois(), plan,
                         horodatage='t', qualite_validee_par='X')
        d = _code(rq, 'exposition_sup_1').description
        self.assertNotIn('UNITE NON DECLAREE', d)
        self.assertIn('contrat annuel', d)
        print("    UX-9 unite declaree : la phrase d'hypothese disparait")

    def test_LES_DEUX_CHEMINS_publient_la_MEME_phrase(self):
        """⚠️ Apres avoir cesse de diverger dans le NOMBRE (1d), les jumeaux
        ne doivent pas diverger dans le TEXTE."""
        rq = _sans_bruit(controler_qualite, _en_mois(), _SANS_UNITE,
                         horodatage='t', qualite_validee_par='X')
        r2 = _a2(_en_mois(), _SANS_UNITE)
        a_qual = _code(rq, 'exposition_sup_1')
        a_agent = _code(r2['rapport_qualite'], 'exposition_sup_1')
        self.assertIsNotNone(a_agent)
        self.assertEqual(a_qual.correction, a_agent.correction)
        for morceau in ('UNITE NON DECLAREE', 'ANNUELLE', 'denominateur'):
            self.assertIn(morceau, a_agent.description,
                          'le chemin agent ne publie pas la phrase partagee')
        print(f"    UX-10 jumeaux d'accord sur le texte : "
              f"correction={a_agent.correction!r}")


# ═══════════════════════════════════════════════════════════════════════════════
#  D — LA CONTRADICTION EST SIGNALEE
# ═══════════════════════════════════════════════════════════════════════════════
class TestLaDonneeQuiContreditLUnite(unittest.TestCase):

    def test_l_unite_apparente_se_derive_de_l_ensemble_ferme(self):
        """⚠️⚠️ AUCUN SEUIL INVENTE : la plus grossiere borne qui contient le
        maximum observe."""
        self.assertEqual(unite_apparente(0.9), 'annee')
        self.assertEqual(unite_apparente(1.0), 'annee')
        self.assertEqual(unite_apparente(11.5), 'mois')
        self.assertEqual(unite_apparente(200.0), 'jour')
        self.assertIsNone(unite_apparente(900.0))
        print("    UX-11 unite apparente : 0.9->annee · 11.5->mois · "
              "200->jour · 900->None")

    def test_LE_CONTROLE_QUI_EMPECHE_LE_DECOR_une_unite_fausse_est_SIGNALEE(self):
        """⚠️⚠️ SANS LUI, DECLARER `mois` DESACTIVERAIT LE CONTROLE. Donnee
        annuelle, plan declarant `mois` : la borne monte a 12, plus rien n'est
        corrige -- et c'est precisement le moment ou il faut parler."""
        plan = dataclasses.replace(_PLAN_AUTO, unite_exposition='mois')
        rq = _sans_bruit(controler_qualite, _portefeuille_auto(400, seed=3),
                         plan, horodatage='t')
        a = _code(rq, 'unite_exposition_contredite')
        self.assertIsNotNone(a, "une donnee annuelle sous un plan 'mois' ne "
                                "declenche AUCUN signal : le mecanisme est "
                                "decoratif")
        self.assertEqual(a.regle, 3, 'la contradiction se SIGNALE, jamais ne '
                                     'se corrige')
        # ⚠️ Le message a été réécrit pour l'actuaire le 02/09 (arbitré par
        # Selasse) : les unités sont désormais entre guillemets français. *Ce
        # que ce contrôle prouve est inchangé — la description nomme l'unité
        # DÉCLARÉE et celle à laquelle la donnée RESSEMBLE.*
        self.assertIn('« mois »', a.description)
        self.assertIn('« annee »', a.description)
        self.assertTrue(rq.bloque, "une unite fausse mesestime TOUT le "
                                   "portefeuille : elle doit escalader")
        print(f"    UX-12 contradiction SIGNALEE (regle {a.regle}) et "
              f"bloquante, echappatoire nominative intacte")

    def test_second_sens_une_unite_JUSTE_ne_declenche_RIEN(self):
        """⚠️ Un signal qui tirerait aussi sur une declaration juste serait du
        bruit, et l'actuaire cesserait de le lire."""
        plan = dataclasses.replace(_PLAN_AUTO, unite_exposition='mois')
        rq = _sans_bruit(controler_qualite, _en_mois(), plan, horodatage='t')
        self.assertIsNone(_code(rq, 'unite_exposition_contredite'))
        print("    UX-13 donnee en mois + plan 'mois' : aucun signal")

    def test_la_contradiction_n_a_RIEN_corrige(self):
        """⚠️ Regle 3 : elle compte, elle affiche, elle ne touche pas."""
        plan = dataclasses.replace(_PLAN_AUTO, unite_exposition='mois')
        df = _portefeuille_auto(400, seed=3)
        avant = float(df['exposition'].sum())
        rq = _sans_bruit(controler_qualite, df.copy(), plan, horodatage='t',
                         qualite_validee_par='Selasse Sekle')
        self.assertAlmostEqual(float(rq.dataframe_propre['exposition'].sum()),
                               avant, places=6)
        print(f"    UX-14 contradiction signalee, exposition INTACTE "
              f"({avant:.2f})")


class TestLEmpreinteEstVersionnee(unittest.TestCase):

    def test_le_schema_a_bumpe_et_le_type_est_ferme(self):
        """⚠️ Le golden de `test_plan_invariants` est le sceau ; celui-ci
        verifie que le bump a bien eu lieu ET que le type reste ferme."""
        from typing import get_args
        # ⚠️ Le SCEAU du numero vit dans `test_plan_invariants` (golden) :
        # le figer ICI aussi creerait un second endroit a bumper.
        self.assertGreaterEqual(EMPREINTE_SCHEMA, 2)
        self.assertEqual(set(get_args(UniteExposition)),
                         {'annee', 'mois', 'jour'})
        self.assertEqual(
            PlanTarifaire.comparer_empreinte('s1:aaaabbbbccccdddd',
                                             _PLAN.empreinte()),
            'SCHEMA_DIFFERENT',
            "une empreinte s1: doit etre declaree NON COMPARABLE, jamais "
            "rendue comme un simple contenu different")
        print(f"    UX-15 schema {EMPREINTE_SCHEMA}, une empreinte s1: rend "
              f"SCHEMA_DIFFERENT (action prescrite : re-tarifer)")


if __name__ == '__main__':
    unittest.main()
