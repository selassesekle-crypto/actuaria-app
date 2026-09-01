"""⚠️⚠️ « PAS VÉRIFIÉ » N'EST PAS « VÉRIFIÉ, RIEN À SIGNALER ».

Décision de Selasse, 01/09/2026. `synthese_qualite_donnees` rendait `None` dans
DEUX états que rien ne distinguait :

    * `rapport is None`        -> la couche N'A PAS TOURNÉ ;
    * `rapport` sans anomalie  -> elle a tourné et n'a RIEN trouvé.

Mesuré le 01/09 sur 10 000 contrats dont **600 à fréquence négative (6 %)** :
le chemin agent ne les exclut pas, et la section « qualité des données » des
livrables rendait exactement ce que rend un portefeuille sain.

> *Le silence par défaut n'était pas une absence d'information : c'était une
> AFFIRMATION, et elle était fausse.*

⚠️ CE QUE LA TRACE A MONTRÉ AVANT LE CODE — quatre surfaces de production, et
elles traitaient l'ambiguïté de **trois façons différentes** :

    services/tarif_excel.py         ligne ABSENTE de l'Excel A6
    services/rapport_equipe_tarif   ligne ABSENTE de l'Excel équipe
    rapport_modeles_tarif (Word/HTML)  bloc ABSENT du rapport SIGNÉ
    rapport_modeles_tarif (prompt)  « ... (ou couche non exécutée sur ce
                                    chemin) » -- LES DEUX ÉTATS FONDUS DANS
                                    UNE SEULE PHRASE, dans le prompt du LLM

⚠️⚠️ ET LE BADGE DEVAIT SUIVRE. Les deux Excel dérivent leur pastille du TEXTE
(`"EXCLUE" in ...`). Aucun de ces mots n'apparaît dans la phrase « non
exécuté » : sans `QNE-4`, le correctif publiait **« rien n'a été vérifié » sous
une pastille VERTE** -- pire que le silence qu'il corrige. *Le correctif et son
badge sont la même correction.*

⚠️ AUCUN EURO, ET C'EST `QNE-8` QUI LE TIENT. La fonction ne fait que rendre un
texte ; elle n'exclut, ne corrige et ne conserve aucune ligne.
"""
import ast
import inspect
import pathlib
import unittest

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire
from core.qualite_donnees import (
    MARQUEUR_QUALITE_NON_EXECUTEE,
    PHRASE_QUALITE_NON_EXECUTEE,
    controler_qualite,
    synthese_qualite_donnees,
)
from direction_non_vie.tarification.services import rapport_modeles_tarif as RM

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_PLAN = PlanTarifaire.depuis_yaml(str(_RACINE / 'plans' / 'auto.yaml'))


def _portefeuille_sain(n=2_000, seed=9):
    """n lignes DISTINCTES et cohérentes : la couche n'a rien à y redire.

    ⚠️ La base est vérifiée muette par `QNE-1` avant tout usage. Trois jeux
    d'essai successifs ont répondu à la place du système pendant la mesure
    (lignes identiques -> doublons ; coût aléatoire sur zéro sinistre ->
    incohérence). *Un témoin non prouvé muet ne prouve rien.*
    """
    e, f, c = _PLAN.exposition, _PLAN.cible_frequence, _PLAN.cible_cout
    rng = np.random.default_rng(seed)
    nb = rng.integers(0, 3, n).astype(float)
    cout = np.where(nb > 0, rng.uniform(500, 5000, n).round(2), 0.0)
    return pd.DataFrame({e: np.ones(n), f: nb, c: cout,
                         'prime_acquise': (200 + np.arange(n) * 0.01).round(2)})


def _corps(fonction):
    """L'AST du CORPS d'une fonction, docstring exclue.

    ⚠️⚠️ *Une citation n'est pas une affirmation.* Ces fichiers expliquent leur
    correctif en prose, et une prose qui NOMME le défaut ferait passer un
    contrôle qui lit le source entier. L'assiette est le code exécuté.
    """
    arbre = ast.parse(inspect.getsource(fonction).lstrip())
    corps = arbre.body[0].body
    if (corps and isinstance(corps[0], ast.Expr)
            and isinstance(corps[0].value, ast.Constant)
            and isinstance(corps[0].value.value, str)):
        corps = corps[1:]
    return corps


def _appel_badge(fichier, texte_ancre):
    """L'expression de badge RÉELLE d'un des deux Excel, par AST."""
    src = pathlib.Path(fichier).read_text(encoding='utf-8')
    for n in ast.walk(ast.parse(src)):
        if (isinstance(n, ast.IfExp)
                and 'AMBRE' in ast.unparse(n)
                and texte_ancre in ast.unparse(n)):
            return ast.unparse(n)
    return None


_SERVICES = _RACINE / 'direction_non_vie' / 'tarification' / 'services'


class TestQualiteNonExecutee(unittest.TestCase):

    def test_QNE_1_les_deux_etats_ne_rendent_jamais_la_meme_valeur(self):
        """⚠️⚠️ LE CONSTAT LUI-MÊME : « pas vérifié » != « rien à signaler »."""
        sain = _portefeuille_sain()
        rapport = controler_qualite(sain.copy(), _PLAN)
        n_anom = (len(rapport.exclusions) + len(rapport.corrections)
                  + len(rapport.signalements))
        self.assertEqual(
            n_anom, 0,
            "témoin non muet : la mesure ne prouverait rien "
            f"({n_anom} anomalie(s))")

        non_execute = synthese_qualite_donnees(None)
        execute_propre = synthese_qualite_donnees(rapport)

        self.assertIsNone(
            execute_propre,
            "une couche qui a tourné sans rien trouver doit se TAIRE : un "
            "avertissement affiché toujours cesse d'être un signal.")
        self.assertIsNotNone(
            non_execute,
            "une couche qui n'a PAS tourné doit le DIRE. C'est le constat.")
        self.assertNotEqual(
            non_execute, execute_propre,
            "les deux états rendent encore la même valeur : le défaut est "
            "intact.")
        print(f"    OK QNE-1 non execute = {len(non_execute)} car., "
              f"execute-propre = None ({n_anom} anomalie sur le temoin)")

    def test_QNE_2_la_phrase_NIE_explicitement_rien_a_signaler(self):
        """⚠️ Dire « non exécuté » ne suffit pas : il faut nier l'autre lecture.

        *Un actuaire qui lit « aucun traitement » comprend « donnée propre ».*
        La phrase doit fermer cette lecture, et dire que le nombre de lignes
        fautives est INCONNU — pas nul.
        """
        p = PHRASE_QUALITE_NON_EXECUTEE
        self.assertIn(MARQUEUR_QUALITE_NON_EXECUTEE, p)
        self.assertIn('rien a signaler', p.lower(),
                      "la phrase doit NOMMER la lecture qu'elle refuse")
        self.assertRegex(p, r"(?i)ce n'est pas\s+«?\s*rien a signaler",
                         "elle doit la NIER, pas seulement la citer")
        self.assertIn('INCONNU', p,
                      "le nombre de lignes fautives est inconnu, pas nul")
        self.assertIn('qualite/C4', p,
                      "la phrase doit dire POURQUOI la couche n'a pas tourne")
        print("    OK QNE-2 la phrase nie « rien a signaler » et dit INCONNU")

    def test_QNE_3_le_rapport_SIGNE_distingue_les_deux_cas(self):
        """⚠️⚠️ LE CONTRÔLE DEMANDÉ PAR SELASSE — sur le document qui part au CAC.

        Le Word et le HTML passent tous deux par `avertissement_qualite` puis
        par `_bloc_qualite_html` / le paragraphe Word : un texte vide fait
        DISPARAÎTRE le bloc. C'est donc la présence même du bloc qui portait
        le mensonge — mesuré, le rapport signé du chemin agent n'avait AUCUNE
        section qualité, exactement comme celui d'un portefeuille sain.
        """
        rapport = controler_qualite(_portefeuille_sain().copy(), _PLAN)

        agent = RM.avertissement_qualite({})
        declaratif_sain = RM.avertissement_qualite(
            {'rapport_qualite': rapport})

        self.assertTrue(
            agent, "chemin agent : le rapport signé se tait encore")
        self.assertEqual(
            declaratif_sain, '',
            "portefeuille sain : le rapport signé ne doit RIEN dire")

        bloc_agent = RM._bloc_qualite_html(agent)
        bloc_sain = RM._bloc_qualite_html(declaratif_sain)
        self.assertIn(MARQUEUR_QUALITE_NON_EXECUTEE, bloc_agent,
                      "le bloc HTML signé ne nomme pas l'absence de contrôle")
        self.assertIn(RM.TITRE_QUALITE_DONNEES, bloc_agent)
        self.assertEqual(bloc_sain, '',
                         "un portefeuille sain ne doit produire aucun bloc")
        self.assertNotEqual(bloc_agent, bloc_sain)
        print(f"    OK QNE-3 rapport signe : bloc de {len(bloc_agent)} car. "
              f"quand non execute, ABSENT quand execute-propre")

    def test_QNE_4_aucun_badge_VERT_sur_une_couche_non_executee(self):
        """⚠️⚠️ SANS CECI, LE CORRECTIF PUBLIAIT « NON VÉRIFIÉ » EN VERT.

        Les deux Excel dérivent leur pastille du TEXTE. La phrase « non
        exécuté » ne contient ni EXCLUE, ni SIGNALEE, ni BLOQUE : elle serait
        sortie VERTE. *Le correctif atterrissait à côté de la surface signée —
        le motif que cet audit poursuit.*

        L'assiette est l'expression RÉELLE des deux fichiers, prise par AST.
        """
        p = PHRASE_QUALITE_NON_EXECUTEE
        self.assertFalse(
            any(m in p for m in ('EXCLUE', 'SIGNALEE', 'BLOQUE')),
            "la phrase déclenche le badge par accident : le contrôle ne "
            "prouverait plus rien le jour où elle changera de mots.")

        cibles = (('tarif_excel.py', '_synth_q'),
                  ('rapport_equipe_tarif.py', '_synth_q6'))
        for nom, ancre in cibles:
            expr = _appel_badge(str(_SERVICES / nom), ancre)
            self.assertIsNotNone(expr, f'{nom} : badge introuvable')
            self.assertIn(
                'MARQUEUR_QUALITE_NON_EXECUTEE', expr,
                f"{nom} : le badge ne connaît pas la couche non exécutée — "
                f"elle sortirait en VERT.")
            # Le badge, EXÉCUTÉ sur la phrase réelle.
            contexte = {'_synth_q': p, '_synth_q6': p,
                        'MARQUEUR_QUALITE_NON_EXECUTEE':
                            MARQUEUR_QUALITE_NON_EXECUTEE}
            self.assertEqual(
                eval(expr, {}, contexte), 'AMBRE',
                f'{nom} : « non vérifié » sort sous une pastille VERTE')
        print("    OK QNE-4 les 2 Excel badgent AMBRE la couche non executee")

    def test_QNE_5_le_marqueur_a_une_source_unique(self):
        """⚠️ Recopier `'NON EXECUTE'` rouvrirait la divergence.

        Le lot « 30 définitions locales -> 0 » a fermé ce motif ; un littéral
        de plus le rouvre en silence le jour où la phrase change.
        """
        fautifs = []
        for f in sorted(_SERVICES.glob('*.py')):
            for n in ast.walk(ast.parse(f.read_text(encoding='utf-8'))):
                if (isinstance(n, ast.Constant)
                        and isinstance(n.value, str)
                        and MARQUEUR_QUALITE_NON_EXECUTEE in n.value):
                    fautifs.append(f'{f.name}:{n.lineno}')
        self.assertEqual(
            fautifs, [],
            f"littéral recopié au lieu d'importer la constante : {fautifs}")
        print(f"    OK QNE-5 marqueur importe, 0 litteral recopie dans "
              f"{len(list(_SERVICES.glob('*.py')))} services")

    def test_QNE_6_aucun_repli_ne_fond_les_deux_etats(self):
        """⚠️⚠️ LE MENSONGE ÉTAIT UNE PARENTHÈSE, ET IL ÉTAIT ÉCRIT.

        Le prompt du LLM portait « Aucun traitement de qualité de données à
        signaler **(ou couche non exécutée sur ce chemin)** ». Une phrase qui
        offre deux lectures n'en affirme aucune — et l'actuaire qui signe ne
        peut pas savoir laquelle il signe.

        ⚠️ ASSIETTE : les littéraux du CODE, pas la prose qui les explique.
        Ce fichier CITE la phrase fautive juste au-dessus ; un contrôle au
        texte du source passerait sur son propre correctif.
        """
        motifs = ('ou couche non exécutée', 'ou couche non executee')
        fautifs = []
        for f in sorted(_SERVICES.glob('*.py')):
            for n in ast.walk(ast.parse(f.read_text(encoding='utf-8'))):
                if (isinstance(n, ast.Constant)
                        and isinstance(n.value, str)
                        and any(m in n.value.lower() for m in motifs)):
                    fautifs.append(f'{f.name}:{n.lineno}')
        self.assertEqual(
            fautifs, [],
            f"un repli fond encore les deux états : {fautifs}")
        print("    OK QNE-6 aucun repli n offre les deux lectures a la fois")

    def test_QNE_7_le_second_sens_un_portefeuille_sain_ne_publie_RIEN(self):
        """⚠️ LE SECOND SENS — sans lui, un contrôle qui crie toujours passe.

        Un correctif qui ferait parler la couche dans les DEUX cas serait
        aussi faux que le silence : il rendrait le signal inutile.
        """
        rapport = controler_qualite(_portefeuille_sain(seed=21).copy(), _PLAN)
        self.assertIsNone(synthese_qualite_donnees(rapport))
        self.assertEqual(
            RM.avertissement_qualite({'rapport_qualite': rapport}), '')
        self.assertEqual(
            RM._bloc_qualite_html(
                RM.avertissement_qualite({'rapport_qualite': rapport})), '')
        print("    OK QNE-7 second sens : portefeuille sain, aucune surface "
              "ne publie")

    def test_QNE_8_aucun_euro_la_synthese_ne_touche_aucune_ligne(self):
        """⚠️⚠️ « AUCUN EURO » SE PROUVE, IL NE SE DÉCLARE PAS.

        La fonction rend un TEXTE. Elle ne doit appeler ni la couche de
        contrôle, ni rien qui produise un dataframe : sinon un rendu de
        rapport déplacerait des lignes.
        """
        interdits = {'controler_qualite', 'preambule_qualite', 'drop',
                     'to_numeric', 'where', 'clip'}
        appels = set()
        for n in ast.walk(ast.Module(body=_corps(synthese_qualite_donnees),
                                     type_ignores=[])):
            if isinstance(n, ast.Call):
                appels.add(n.func.attr if isinstance(n.func, ast.Attribute)
                           else getattr(n.func, 'id', ''))
        self.assertEqual(
            interdits & appels, set(),
            f"la synthèse touche aux données : {interdits & appels}")

        sain = _portefeuille_sain(seed=33)
        rapport = controler_qualite(sain.copy(), _PLAN)
        avant = len(rapport.dataframe_propre)
        synthese_qualite_donnees(rapport)
        synthese_qualite_donnees(None)
        self.assertEqual(len(rapport.dataframe_propre), avant,
                         "le rendu du texte a modifié le dataframe propre")
        print(f"    OK QNE-8 aucun euro : {avant} lignes avant et apres, "
              f"0 appel interdit")


if __name__ == '__main__':
    unittest.main(verbosity=2)
