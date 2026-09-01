"""Controles positifs -- `conformite` : les six derniers constats de la zone.

═══ ⛔⛔ `C4` -- L'EXEMPTION PAR LE PLAN ETAIT MUETTE ═══

Deux chemins soustraient une colonne au garde-fou le plus fort du module.
Celui par le NOM (`exposition`, la cible) est structurel. Celui par le PLAN --
`plan.facteurs_anteriorite()` -- faisait un `continue` NU. Mesure du 01/09 sur
un portefeuille auto reel portant `antecedents_sinistres_n1` :

    0 mention en log  ·  0 dans `exclusions`  ·  0 dans `alertes`

> *L'asymetrie entre deux chemins qui font le meme geste est ce qui localise
> le defaut : ici l'un parle, l'autre se tait.*

⚠️ CE N'EST PAS UNE EXCLUSION : ces colonnes sont **conservees**. Les ranger
dans `exclusions` dirait le contraire de ce qui s'est passe. Le canal est donc
neuf -- `MatriceX.exemptees_effet` -- sur le patron exact de `ecartees_amont`
(`conformite/C15`), et il va jusqu'aux TROIS surfaces signees.

═══ ⛔⛔ `C11` -- UN FILTRE PLACE APRES CELUI QUI LUI OTE SON OBJET ═══

`filtrer_genre` journalise << toute suppression effective -- tracabilite
requise pour l'audit ACPR >>. Mais sur le chemin `plan` il recevait une liste
dont l'intersection avec les colonnes declarees avait DEJA retire `sexe` :
mesure du 01/09 sur un portefeuille qui PORTE la colonne, **0 log citant
C-236/09**. La trace reglementaire de l'exclusion du genre n'existait pas.

⚠️ L'ENSEMBLE RETENU EST LE MEME. Filtrer puis intersecter et intersecter puis
filtrer donnent le meme resultat -- `CF-5` le prouve dans les deux sens. Seule
la TRACE change ; **aucun euro ne bouge**.

═══ ⛔ `C8` ET `C9` -- LE MEME AJOUT, DEUX TEXTES RESTES EN ARRIERE ═══

L'ajout du Gini normalise a change ce que rend `detecter_fuites_par_effet` (un
DICT de deux mesures) et le critere applique (`max` des deux). Deux textes
sont restes sur l'ancien etat :

| constat | ce qu'il disait | ce qui est |
|---|---|---|
| `C8` | `corrélation de {'spearman': 0.4563, ...}` | un dict Python dans un rapport signe |
| `C8` | `avec la cible ['nb_sinistres']` | une liste Python, meme ligne |
| `C9` | << Retourne {colonne: correlation} >> | `{colonne: {spearman, gini_normalise}}` |
| `C9` | << la correlation de Spearman depasse `seuil` >> | `max(spearman, gini_normalise)` |

═══ LES DEUX AUTRES ═══

`C12` -- l'instruction etait FAUSSE sur le chemin declaratif : le motif portait
<< (liste blanche) >> et la synthese en tirait << declarez-la
(FACTEURS_TARIFAIRES_AUTORISES) >>. Or la verite est `plan.colonnes_produites()`
: editer la constante ne change RIEN. *Une instruction que l'actuaire ne peut
pas suivre est pire que le silence.*

`C13` -- `valeur_mobilier` etait rangee sous << Indicateurs DERIVES generes par
A2 >>. A2 la LIT et ne l'ecrit jamais : c'est une colonne SOURCE.

═══ ⛔⛔ ET UNE TROUVAILLE QUI EST DE MOI ═══

`CF-9` derive l'inclusion au lieu de la supposer, et il a trouve que
`plan_ecarte` -- MON correctif de `conformite/C15`, commit `9a69162` --
n'avait PAS de libelle dans `_LABELS_SYNTHESES`. Or `_syntheses_html` et
l'Excel equipe iterent CE TUPLE, pas le dictionnaire.

> *La synthese etait calculee et rendue NULLE PART, en silence, dans les
> formats qui partent au CAC. Le correctif atterrissait a cote de la surface
> signee -- le motif que cet audit poursuit, commis par l'audit lui-meme.*
"""

from __future__ import annotations

import ast
import logging
import pathlib
import unittest

import numpy as np
import pandas as pd

import core.conformite_reglementaire as _cmod
from core.conformite_reglementaire import (
    MOTIF_EXEMPTEE_ANTERIORITE,
    construire_matrice_x,
    detecter_fuites_par_effet,
    est_facteur_autorise,
    filtrer_genre,
    synthese_exclusions,
    synthese_exemptions_effet,
)
from core.plan_tarifaire import PlanTarifaire
from direction_non_vie.tarification.services import (
    rapport_equipe_tarif as _eq,
)

_SOURCE = pathlib.Path(_cmod.__file__).read_text(encoding='utf-8')
_RACINE = pathlib.Path(_eq.__file__).parents[1]
_SERVICES = ('rapport_equipe_tarif.py', 'rapport_modeles_tarif.py',
             'tarif_excel.py')
_AGENTS = ('a3_glm', 'a4_ml', 'a5_deep_learning', 'a6_comparaison')


class Collecteur(logging.Handler):
    """Un logger qui garde ses messages -- le seul moyen de mesurer une TRACE."""

    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _portefeuille(n=400, graine=7):
    """Portefeuille auto porteur des DEUX declencheurs : `sexe` (C11) et
    `antecedents_sinistres_n1`, declaree `anteriorite=True` au plan (C4)."""
    rng = np.random.default_rng(graine)
    theta = rng.gamma(2.0, 0.6, n)
    df = pd.DataFrame({
        'age': rng.integers(18, 80, n).astype(float),
        'bonus_malus': rng.uniform(0.5, 1.5, n),
        'sexe': rng.choice(['M', 'F'], n),
        'exposition': np.ones(n),
        'antecedents_sinistres_n1': rng.poisson(theta * 3, n).astype(float),
    })
    df['nb_sinistres'] = rng.poisson(theta, n).astype(float)
    return df


def _plan_auto():
    return PlanTarifaire.depuis_yaml(
        str(_RACINE.parents[1] / 'plans' / 'auto.yaml'))


def _source_service(nom):
    return (_RACINE / 'services' / nom).read_text(encoding='utf-8')


class TestConformiteSixConstats(unittest.TestCase):
    """Six constats de la zone `conformite`, plus le cablage jusqu'au signe."""

    def setUp(self):
        self.journal = Collecteur()
        self.log = logging.getLogger(f'test_conf_{id(self)}')
        self.log.setLevel(logging.DEBUG)
        self.log.addHandler(self.journal)
        self.log.propagate = False
        self.plan = _plan_auto()
        self.df = _portefeuille()
        self.candidates = [c for c in self.df.columns if c != 'nb_sinistres']

    def _matrice(self, **kw):
        params = {'contexte': 'controle', 'logger_agent': self.log,
                  'df': self.df, 'col_cible': 'nb_sinistres',
                  'plan': self.plan}
        params.update(kw)
        return construire_matrice_x(list(self.candidates), **params)

    # ── `conformite/C4` — l'exemption se dit ─────────────────────────────────

    def test_CF_1_LE_TEST_QUI_FERME_l_exemption_par_le_plan_est_publiee(self):
        """`conformite/C4` : par EXECUTION, elle n'etait NULLE PART."""
        self.assertIn(
            'antecedents_sinistres_n1', self.plan.facteurs_anteriorite(),
            "la premisse du controle est fausse : le plan auto ne declare "
            "plus cette colonne en anteriorite")
        mx = self._matrice()
        self.assertIn(
            'antecedents_sinistres_n1', mx.exemptees_effet,
            f"la colonne exemptee du controle par l'effet n'est publiee nulle "
            f"part : exemptees={mx.exemptees_effet}")
        self.assertEqual(
            mx.exemptees_effet['antecedents_sinistres_n1'],
            MOTIF_EXEMPTEE_ANTERIORITE,
            "le motif publie n'est pas celui de la source unique")

    def test_CF_2_l_exemptee_est_CONSERVEE_pas_exclue(self):
        """`conformite/C4` : la ranger dans `exclusions` dirait l'inverse."""
        mx = self._matrice()
        self.assertIn('antecedents_sinistres_n1', mx.features,
                      'la colonne exemptee a ete ecartee de la matrice')
        self.assertNotIn(
            'antecedents_sinistres_n1', mx.exclusions,
            "une colonne CONSERVEE est publiee comme EXCLUE : le rapport "
            "dirait le contraire de ce qui s'est passe")

    def test_CF_3_la_synthese_nomme_la_colonne_et_l_action(self):
        """`conformite/C4` : le texte demande de VERIFIER, pas de retablir."""
        self.assertIsNone(synthese_exemptions_effet({}),
                          'une synthese vide doit rendre None, pas du bruit')
        txt = synthese_exemptions_effet(self._matrice().exemptees_effet)
        self.assertIsNotNone(txt)
        self.assertIn('antecedents_sinistres_n1', txt)
        for attendu in ('CONSERV', 'anteriorite=True', 'PASS'):
            self.assertIn(attendu, txt,
                          f"la synthese ne porte pas '{attendu}' : {txt}")
        # Elle accepte aussi une simple liste de noms : `a6` agrege en SET.
        self.assertIn('zorglub', synthese_exemptions_effet(['zorglub']) or '')

    # ── `conformite/C11` — la trace ACPR retrouve son objet ──────────────────

    def test_CF_4_LE_TEST_QUI_FERME_la_trace_ACPR_se_declenche(self):
        """`conformite/C11` : par EXECUTION -- 0 log avant, au moins 1 apres."""
        mx = self._matrice()
        self.assertIn('sexe', self.candidates, 'premisse fausse')
        self.assertNotIn('sexe', mx.features)
        cjue = [m for m in self.journal.messages if 'C-236/09' in m]
        self.assertTrue(
            cjue,
            "aucun log ne cite C-236/09 alors que le portefeuille PORTE une "
            "colonne de genre : la tracabilite ACPR de cette exclusion "
            "n'existe pas. Un controle qui ne peut pas se declencher est du "
            f"decor. Journal : {self.journal.messages}")

    def test_CF_5_et_l_ensemble_retenu_est_INCHANGE(self):
        """`conformite/C11` : filtrer puis intersecter == l'inverse.

        ⚠️ C'est la preuve qu'AUCUN EURO ne bouge : le correctif ne deplace
        que la TRACE. Verifie dans les deux sens, sur les colonnes reelles.
        """
        declarees = set(self.plan.colonnes_produites())
        ancien = [c for c in filtrer_genre(
            [c for c in self.candidates if c in declarees])]
        nouveau = [c for c in filtrer_genre(list(self.candidates))
                   if c in declarees]
        self.assertEqual(
            ancien, nouveau,
            "l'ordre des deux filtres change le jeu retenu -- le correctif "
            "de C11 ne serait alors PAS neutre")
        self.assertEqual(sorted(self._matrice().features), sorted(nouveau))

    # ── `conformite/C8` et `C9` — le texte suit la grandeur ──────────────────

    def test_CF_6_LE_TEST_QUI_FERME_le_motif_ne_porte_plus_de_dict(self):
        """`conformite/C8` : ni dict ni liste Python dans un rapport signe."""
        df = self.df.copy()
        df['zorglub'] = df['nb_sinistres'] * 3.0 + 1.0
        mx = construire_matrice_x(
            ['age', 'zorglub'], contexte='controle', logger_agent=self.log,
            df=df, col_cible=['nb_sinistres'],
            facteurs_supplementaires=['zorglub'])
        motif = mx.exclusions.get('zorglub', '')
        self.assertIn("PAR L'EFFET", motif,
                      f'la fuite plantee n a pas ete detectee : {mx.exclusions}')
        for signe in ('{', '}', '[', ']'):
            self.assertNotIn(
                signe, motif,
                f"le motif lu par l'actuaire porte un '{signe}' -- une "
                f"structure Python n'est pas une phrase : {motif}")
        self.assertIn('Spearman', motif)
        self.assertIn('Gini', motif,
                      "le motif ne nomme qu'une des DEUX mesures alors que "
                      "le critere est leur maximum")

    def test_CF_7_la_docstring_decrit_le_critere_REEL(self):
        """`conformite/C9` : elle annoncait un critere qui n'est plus le sien."""
        doc = None
        for n in ast.walk(ast.parse(_SOURCE)):
            if (isinstance(n, ast.FunctionDef)
                    and n.name == 'detecter_fuites_par_effet'):
                doc = ast.get_docstring(n) or ''
        self.assertIsNotNone(doc, 'detecter_fuites_par_effet introuvable')
        self.assertIn('gini_normalise', doc,
                      'la docstring ne nomme pas la seconde mesure')
        self.assertIn('max(spearman, gini_normalise)', doc,
                      'la docstring ne dit pas que le critere est le MAXIMUM')
        # ⚠️⚠️ L'ASSIETTE EST CE QUE LA DOCSTRING ANNONCE, PAS CE QU'ELLE CITE.
        # Ma premiere version interdisait la chaine dans TOUT le texte -- et
        # elle tombait sur le correctif lui-meme, qui CITE le defaut qu'il
        # repare (<< Il annoncait "Retourne {colonne: correlation}" >>).
        # *Une citation n'est pas une affirmation* -- quatrieme occurrence de
        # la session. Le controle porte donc sur l'ANNONCE : le texte qui
        # precede le premier bloc d'avertissement.
        annonce = doc.split('⚠️')[0]
        self.assertNotIn(
            'Retourne {colonne: corr', annonce,
            "la docstring annonce encore une simple correlation la ou la "
            f"valeur rendue est un dict de deux mesures : {annonce}")
        self.assertNotIn(
            'la corrélation de\nSpearman avec la cible dépasse', annonce,
            'la docstring annonce encore Spearman SEUL comme critere')
        # Et le CODE dit bien ce que la docstring annonce : derive, pas suppose.
        rendu = detecter_fuites_par_effet(
            self.df.assign(zorglub=self.df['nb_sinistres'] * 3.0 + 1.0),
            ['age', 'zorglub'], 'nb_sinistres')
        self.assertEqual(sorted(rendu['zorglub']),
                         ['gini_normalise', 'spearman'])

    # ── `conformite/C12` — l'instruction nomme la bonne source ───────────────

    def test_CF_8_LE_TEST_QUI_FERME_l_instruction_nomme_le_PLAN(self):
        """`conformite/C12` : editer la constante ne change rien sur ce chemin."""
        df = self.df.copy()
        df['zorglub_non_declare'] = np.linspace(0, 1, len(df))
        mx = construire_matrice_x(
            [c for c in df.columns if c != 'nb_sinistres'],
            contexte='controle', logger_agent=self.log, df=df,
            col_cible='nb_sinistres', plan=self.plan)
        motif = mx.exclusions.get('zorglub_non_declare', '')
        self.assertIn('PLAN DE TARIFICATION SIGNÉ', motif)
        self.assertNotIn(
            'liste blanche', motif,
            "le motif du chemin declaratif renvoie encore a la liste "
            f"blanche, dont l'edition n'a aucun effet ici : {motif}")
        txt = synthese_exclusions(mx.exclusions) or ''
        self.assertIn('DANS LE PLAN', txt)
        self.assertIn('NE CHANGERA RIEN', txt,
                      "la synthese ne previent pas que FACTEURS_TARIFAIRES_"
                      "AUTORISES est sans effet sur ce chemin")
        # ⚠️ SECOND SENS : le chemin SANS plan garde son instruction propre.
        # Corriger l'un en cassant l'autre serait la meme faute, deplacee.
        hors_plan = construire_matrice_x(
            ['age', 'zorglub_inconnu'], contexte='controle',
            logger_agent=self.log)
        self.assertIn('liste blanche',
                      hors_plan.exclusions.get('zorglub_inconnu', ''))

    # ── `conformite/C13` — une source rangee parmi les derivees ──────────────

    def test_CF_10_valeur_mobilier_est_rangee_comme_SOURCE(self):
        """`conformite/C13` : A2 la LIT, elle ne l'ECRIT jamais."""
        lignes = _SOURCE.splitlines()
        l_vm = [i for i, x in enumerate(lignes) if "'valeur_mobilier'" in x]
        l_hdr = [i for i, x in enumerate(lignes)
                 if x.lstrip().startswith('#')
                 and 'Indicateurs D' in x and 'A2' in x]
        self.assertTrue(l_vm and l_hdr, 'ancres introuvables')
        # ⚠️ TOUTES les occurrences, pas la premiere. Ma version initiale
        # comparait `min(l_vm)` : une SECONDE declaration ajoutee dans le bloc
        # des derivees passait inapercue, et le sceau l'a montre en plantant
        # une violation qui ne faisait rien tomber. *Un controle qui regarde
        # le premier venu ne surveille pas l'ensemble.*
        self.assertLess(
            max(l_vm), max(l_hdr),
            f"`valeur_mobilier` est declaree dans le bloc des DERIVEES d'A2 "
            f"(lignes {[n + 1 for n in l_vm]}, en-tete des derivees ligne "
            f"{max(l_hdr) + 1}), alors qu'A2 ne la produit pas")
        self.assertTrue(est_facteur_autorise('valeur_mobilier'),
                        'le deplacement a rendu la colonne non autorisee')
        # Le FAIT, pas seulement le rangement : A2 ne l'ecrit nulle part.
        src_a2 = (_RACINE / 'a2_preprocessing' / 'agent.py').read_text(
            encoding='utf-8')
        ecrites = set()
        for n in ast.walk(ast.parse(src_a2)):
            if isinstance(n, ast.Assign):
                for cible in n.targets:
                    if (isinstance(cible, ast.Subscript)
                            and isinstance(cible.slice, ast.Constant)):
                        ecrites.add(cible.slice.value)
        self.assertNotIn(
            'valeur_mobilier', ecrites,
            "A2 ECRIT `valeur_mobilier` : le constat C13 serait faux et ce "
            "controle avec lui")

    # ── Le cablage jusqu'aux surfaces SIGNEES ────────────────────────────────

    def test_CF_9_toute_synthese_produite_porte_son_LIBELLE(self):
        """⚠️⚠️ LE CONTROLE GENERAL -- il a trouve MON propre oubli.

        `_syntheses_html` et l'Excel equipe iterent `_LABELS_SYNTHESES`, pas le
        dictionnaire. Une cle produite sans libelle est rendue NULLE PART, en
        silence. `plan_ecarte` -- constat `conformite/C15`, commit `9a69162` --
        etait dans ce cas.
        """
        src = _source_service('rapport_equipe_tarif.py')
        produites, libelles = set(), set()
        for n in ast.walk(ast.parse(src)):
            if (isinstance(n, ast.FunctionDef)
                    and n.name == 'syntheses_reglementaires'):
                for d in ast.walk(n):
                    if isinstance(d, ast.Dict):
                        produites |= {k.value for k in d.keys
                                      if isinstance(k, ast.Constant)}
            if (isinstance(n, ast.Assign)
                    and getattr(n.targets[0], 'id', '') == '_LABELS_SYNTHESES'):
                libelles = {e.elts[0].value for e in n.value.elts}
        self.assertTrue(produites and libelles, 'ancres introuvables')
        self.assertEqual(
            sorted(produites - libelles), [],
            f"cle(s) calculee(s) mais SANS libelle, donc jamais rendues en "
            f"HTML/Word/Excel equipe : {sorted(produites - libelles)}")
        self.assertEqual(
            sorted(libelles - produites), [],
            f"libelle(s) sans clé produite -- une ligne morte dans le rendu : "
            f"{sorted(libelles - produites)}")

    def test_CF_11_le_canal_va_jusqu_aux_trois_surfaces_signees(self):
        """`conformite/C4` : corrige OU ? Sur les memes surfaces que `C15`."""
        for nom in _SERVICES:
            src = _source_service(nom)
            self.assertIn(
                'synthese_exemptions_effet', src,
                f"{nom} ne publie pas les exemptions du controle par l'effet, "
                f"alors qu'il publie deja `synthese_colonnes_plan_ecartees`")
            self.assertIn('colonnes_exemptees_effet', src,
                          f'{nom} ne lit pas la cle dans le resultat')
        for zone in _AGENTS:
            src = (_RACINE / zone / 'agent.py').read_text(encoding='utf-8')
            self.assertIn(
                'colonnes_exemptees_effet', src,
                f"{zone} ne fait pas voyager les exemptions vers `a6`")


if __name__ == '__main__':
    unittest.main(verbosity=2)
