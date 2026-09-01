"""Controles positifs -- le DERNIER lot : `qualite`, `a6`, `services`.

═══ ⛔⛔ `qualite/C6` -- AUCUNE PART DU PORTEFEUILLE N'ETAIT PUBLIEE ═══

`resume()` -- le dict qui part dans l'`audit_trail` et les rapports -- portait
`lignes_initiales`, `lignes_retenues`, et une `proportion` **par anomalie**.
Jamais la part du portefeuille touchee. Il fallait la soustraire a la main.

⚠️⚠️ ET LA CALCULER PAR SOMME DONNE UN CHIFFRE FAUX. Mesure du 01/09 sur un cas
construit ou deux anomalies frappent des lignes qui se recouvrent :

    somme des `nb_lignes` : 20      UNION des index : 15      recouvrement : 5

> *Ne jamais additionner des sources qui se recoupent -- calculer l'UNION.*

⚠️ ET L'UNION N'A DE SENS QUE SI LES INDEX SONT COMPARABLES. Verifie par AST
AVANT de l'ecrire : `controler_qualite` ne REAFFECTE JAMAIS `df`, donc toutes
les anomalies sont reperees dans le MEME referentiel -- celui de l'entree.
*Une union d'index pris dans deux referentiels n'aurait aucun sens.*

═══ ⛔⛔ `services/C7` -- LA CAUSE DU PLAFOND N'ATTEIGNAIT QUE 2 SURFACES SUR 6 ═══

`raisons_plafond` existe pour qu'un statut AMBRE dise POURQUOI. Mesure : elle
atteignait `modeles.export_html` et `modeles.export_word`. **Ni l'Excel A6, ni
les trois formats du rapport d'equipe** -- c'est-a-dire ni les formats qui
partent au CAC.

> *Une cause de plafond qui n'atteint qu'un tiers des livrables laisse les deux
> autres tiers afficher AMBRE sans dire pourquoi* -- exactement le defaut que
> `raisons_plafond` existe pour fermer.

La SOURCE reste `rapport_modeles_tarif` : les deux autres surfaces l'IMPORTENT,
elles ne la reconstituent pas.

═══ LES TROIS AUTRES ═══

`qualite/C5` -- l'en-tete citait `A1._evaluer_qualite` comme source
d'autorite. **Une seule occurrence du nom dans tout le depot : cette phrase.**
*Un renvoi a une fonction qui n'existe pas envoie le lecteur chercher une
autorite qu'il ne trouvera jamais.*

`a6/C7` -- `_calculer_courbes` annoncait << les 3 meilleurs modeles >> et ne
les utilisait pas : `top_modeles` recu, cite UNE fois -- sa signature. La
courbe trie la CIBLE OBSERVEE. *A decharge, le nom `gini_observe` etait
honnete : c'est la docstring qui sur-annoncait, pas le graphique.*

`a6/C10` -- << 7 tests >> pour **30** methodes, l'ecart le plus large de tout
l'audit.
"""

from __future__ import annotations

import ast
import glob
import inspect
import pathlib
import unittest

import numpy as np
import pandas as pd

import core.qualite_donnees as _qmod
from core.plan_tarifaire import PlanTarifaire
from core.qualite_donnees import controler_qualite
from direction_non_vie.tarification.a6_comparaison import agent as _a6mod
from direction_non_vie.tarification.services import (
    rapport_equipe_tarif as _eq,
)
from direction_non_vie.tarification.services.rapport_modeles_tarif import (
    synthese_raisons_plafond,
)

_SRC_Q = pathlib.Path(_qmod.__file__).read_text(encoding='utf-8')
_SRC_A6 = pathlib.Path(_a6mod.__file__).read_text(encoding='utf-8')
_SERVICES = pathlib.Path(_eq.__file__).parent
_DOSSIER_A6 = pathlib.Path(_a6mod.__file__).parent


def _rapport_avec_recouvrement():
    """Deux anomalies qui frappent des lignes COMMUNES -- le cas ou la somme
    et l'union divergent."""
    n = 200
    df = pd.DataFrame({
        'id_contrat': [f'C{i}' for i in range(n)],
        'expo': np.ones(n), 'nb_sin': np.zeros(n),
        'cout': np.zeros(n), 'age': np.arange(n) * 1.0,
    })
    df.loc[0:9, 'nb_sin'] = -1.0        # 10 lignes
    df.loc[5:14, 'cout'] = -3.0         # 10 lignes, dont 5 communes
    plan = PlanTarifaire.depuis_dict({
        'lob': 'ctrl', 'version': '1', 'auteur': 'controle',
        'exposition': 'expo', 'cible_frequence': 'nb_sin',
        'cible_cout': 'cout', 'identifiant_contrat': 'id_contrat',
        'facteurs': [{'nom': 'age', 'type': 'continu'}],
    })
    return controler_qualite(df, plan)


class TestDernierLot(unittest.TestCase):
    """Cinq constats : `qualite/C5` `C6`, `a6/C7` `C10`, `services/C7`."""

    # ── `qualite/C6` — la part touchee, en UNION ───────────────────────────

    def test_DL_1_LE_TEST_QUI_FERME_resume_publie_la_part_TOUCHEE(self):
        """`qualite/C6` : et c'est une UNION, pas une somme."""
        rap = _rapport_avec_recouvrement()
        res = rap.resume()
        for cle in ('lignes_touchees', 'proportion_touchee',
                    'proportion_exclue'):
            self.assertIn(cle, res,
                          f"`resume()` ne publie pas '{cle}' : la part du "
                          f"portefeuille touchee reste a soustraire a la main")
        toutes = rap.exclusions + rap.corrections + rap.signalements
        somme = sum(a.nb_lignes for a in toutes)
        union = len({i for a in toutes for i in a.index})
        self.assertLess(
            union, somme,
            f"le cas de controle ne produit AUCUN recouvrement "
            f"(somme={somme}, union={union}) : il ne prouve alors rien")
        self.assertEqual(
            res['lignes_touchees'], union,
            f"la part publiee vaut {res['lignes_touchees']} au lieu de "
            f"l'UNION {union} -- une SOMME compterait {somme}, et deux "
            f"anomalies sur la meme ligne la feraient mentir")

    def test_DL_2_et_les_index_sont_dans_le_MEME_referentiel(self):
        """`qualite/C6`, la premisse : sans elle, l'union n'a aucun sens.

        ⚠️ Si `controler_qualite` reaffectait `df` en cours de route, les
        index des anomalies suivantes porteraient sur une AUTRE trame, et les
        unir reviendrait a rattacher par la POSITION -- le defaut que cet
        audit poursuit.
        """
        for n in ast.walk(ast.parse(_SRC_Q)):
            if not (isinstance(n, ast.FunctionDef)
                    and n.name == 'controler_qualite'):
                continue
            reaffectations = [
                x.lineno for x in ast.walk(n) if isinstance(x, ast.Assign)
                and any(getattr(t, 'id', None) == 'df' for t in x.targets)]
            self.assertEqual(
                reaffectations, [],
                f"`controler_qualite` reaffecte `df` en l.{reaffectations} : "
                f"les index des anomalies ne sont plus comparables, et "
                f"`proportion_touchee` devient un chiffre sans signification")
            return
        self.fail('controler_qualite introuvable')

    # ── `qualite/C5` — un renvoi vers une fonction inexistante ────────────

    def test_DL_3_l_en_tete_ne_cite_plus_une_fonction_inexistante(self):
        """`qualite/C5` : le nom n'existe nulle part -- verifie, pas suppose."""
        racine = pathlib.Path(_qmod.__file__).parent.parent
        definitions = []
        for chemin in glob.glob(str(racine / '**' / '*.py'), recursive=True):
            if 'audit_2026_08' in chemin or '.venv' in chemin:
                continue
            try:
                arbre = ast.parse(pathlib.Path(chemin).read_text(
                    encoding='utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue
            definitions += [n.name for n in ast.walk(arbre)
                            if isinstance(n, ast.FunctionDef)
                            and n.name == '_evaluer_qualite']
        entete = _SRC_Q.split('"""')[1]
        if definitions:
            self.assertIn(
                '_evaluer_qualite', entete,
                "la fonction existe desormais : l'en-tete peut la citer")
        else:
            self.assertNotIn(
                "déjà pensée dans A1 (`_evaluer_qualite`)", entete,
                "l'en-tete renvoie encore a `A1._evaluer_qualite`, qui "
                "n'est definie nulle part")
            self.assertIn('qualite/C5', entete,
                          "le constat n'est pas nomme la ou il est repare")

    # ── `a6/C7` — un argument passe et jamais lu ──────────────────────────

    def test_DL_4_LE_TEST_QUI_FERME_plus_d_argument_mort(self):
        """`a6/C7` : la docstring annoncait un calcul qui n'avait pas lieu."""
        for n in ast.walk(ast.parse(_SRC_A6)):
            if not (isinstance(n, ast.FunctionDef)
                    and n.name == '_calculer_courbes'):
                continue
            args = [a.arg for a in n.args.args]
            self.assertNotIn(
                'top_modeles', args,
                "`top_modeles` est de nouveau recu : *un argument qu'on "
                "passe sans qu'il serve fait croire a un calcul qui n'a pas "
                "lieu*")
            doc = ast.get_docstring(n) or ''
            annonce = doc.split('⚠️')[0]
            self.assertNotIn(
                '3 meilleurs mod', annonce,
                f"la docstring annonce encore les 3 meilleurs modeles : "
                f"{annonce}")
            self.assertIn('OBSERV', annonce.upper(),
                          "elle ne dit pas que la courbe trie la valeur "
                          "OBSERVEE")
            return
        self.fail('_calculer_courbes introuvable')

    def test_DL_5_aucun_en_tete_d_a6_n_annonce_un_compte_de_tests(self):
        """`a6/C10` : << 7 tests >> pour 30 methodes."""
        import re
        motif = re.compile(r'\b\d+\s+tests?\b', re.IGNORECASE)
        for chemin in glob.glob(str(_DOSSIER_A6 / '*.py')):
            tete = pathlib.Path(chemin).read_text(
                encoding='utf-8').split('"""')[1:2]
            if not tete:
                continue
            # La ligne qui EXPLIQUE le constat cite l'ancien compte.
            lignes = [l for l in tete[0].split('\n')
                      if motif.search(l) and 'a6/C10' not in tete[0]]
            self.assertEqual(
                lignes, [],
                f'{pathlib.Path(chemin).name} annonce un compte de tests : '
                f'{lignes}')

    # ── `services/C7` — la cause du plafond atteint les six surfaces ──────

    def test_DL_6_LE_TEST_QUI_FERME_la_cause_atteint_les_SIX_surfaces(self):
        """`services/C7` : deux sur six, mesure -- dont aucune au CAC."""
        # ⚠️⚠️ L'ASSIETTE EST L'APPEL, PAS LA MENTION. Ma premiere version
        # cherchait le NOM dans le fichier -- et le sceau l'a demasquee : un
        # plant qui neutralise l'appel (`_synth_pl = None`) laisse l'IMPORT
        # en place, donc le nom aussi. *Une mention n'est pas un appel* --
        # meme famille que la citation, sur un autre support.
        # ⚠️ `rapport_modeles_tarif` est la SOURCE : ses deux formats
        # publiaient deja la cause par `_bloc_raisons_html`, plus riche. Ce
        # sont les DEUX AUTRES fichiers qui ne la publiaient pas du tout.
        src_source = (_SERVICES / 'rapport_modeles_tarif.py').read_text(
            encoding='utf-8')
        self.assertIn(
            'def synthese_raisons_plafond', src_source,
            'la source unique de la phrase a disparu')
        self.assertIn(
            'raisons_plafond(result_a6)', src_source,
            'la synthese ne consulte plus `raisons_plafond` : elle la '
            'RECONSTITUERAIT, et divergerait du test qui decide')
        for nom in ('rapport_equipe_tarif.py', 'tarif_excel.py'):
            src = (_SERVICES / nom).read_text(encoding='utf-8')
            appels = [n.lineno for n in ast.walk(ast.parse(src))
                      if isinstance(n, ast.Call)
                      and (getattr(n.func, 'id', None)
                           or getattr(n.func, 'attr', None))
                      == 'synthese_raisons_plafond']
            self.assertTrue(
                appels,
                f"{nom} n'APPELLE pas `synthese_raisons_plafond` : un statut "
                f"AMBRE y reste sans motif, meme si le symbole est importe")
        # Et le rendu equipe la LIT : une cle sans libelle est rendue nulle
        # part -- c'est `conformite/C15` qui l'a appris a cet audit.
        libelles = {c for c, _ in _eq._LABELS_SYNTHESES}
        self.assertIn('plafond', libelles,
                      "la cle 'plafond' n'a pas de libelle : elle serait "
                      "calculee et rendue NULLE PART")

    def test_DL_7_et_la_synthese_se_TAIT_quand_il_n_y_a_rien(self):
        """`services/C7`, second sens : un avertissement permanent ne se lit plus.

        ⚠️ Publier une ligne vide a chaque execution ferait exactement ce que
        `raisons_plafond` combat : du bruit que l'actuaire cesse de lire.
        """
        self.assertIsNone(synthese_raisons_plafond(None))
        self.assertIsNone(synthese_raisons_plafond({'statut_rag': 'VERT'}))
        txt = synthese_raisons_plafond({
            'statut_rag': 'AMBRE',
            'audit_trail': {'raisons_plafond': ['signature actuaire absente']},
        })
        self.assertIsNotNone(txt)
        self.assertIn('signature actuaire absente', txt)
        self.assertIn('AMBRE', txt)
        # La SOURCE n'est pas reconstituee : c'est la meme fonction.
        src = inspect.getsource(synthese_raisons_plafond)
        self.assertIn('raisons_plafond(result_a6)', src)


if __name__ == '__main__':
    unittest.main(verbosity=2)
