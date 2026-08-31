"""Controles positifs — `a2` : neuf constats, dont un RESIDU dans mon propre lot.

═══ ⛔⛔ `a2/C5` — LE CODE ETAIT CORRIGE, LE RAPPORT MENTAIT ═══

Le constat disait : << exposition = 0 -> a exclure >>, et le code IMPUTAIT par
la mediane. **L'etape 1b du chantier `unite_exposition` l'a corrige** : mesure
du 01/09, 400 lignes en entree, 40 a exposition nulle, **360 en sortie**. La
ligne est bien EXCLUE.

⚠️⚠️ MAIS LE RAPPORT SIGNE DISAIT AUTRE CHOSE, ET C'EST MON LOT QUI L'A ECRIT :

```
  OK 40 ligne(s) CORRIGEE(S) : 40x exposition_non_positive_exclue
                               (ligne EXCLUE (impossible)).
     !! 40 ligne(s) d'exposition <= 0 EXCLUE(S). ...
     !! EFFET SUR LE TOTAL de « exposition » : 299 -> 299 (+0.0 %).
  lignes : 360 -> 360
```

**Trois defauts dans un seul message :**

1. **<< CORRIGEE(S) >> pour des lignes EXCLUES** -- le verbe contredit son
   propre detail deux lignes plus bas. Racine : `_noter` codait `regle=2` EN
   DUR, donc toute mutation d'A2 devenait une correction ; et le rapport
   rangeait tout dans `corrections` sans regarder la regle. *La classe portait
   deja le champ ; c'est l'appelant qui ne le remplissait pas.*
2. **<< EFFET SUR LE TOTAL : 299 -> 299 (+0,0 %) >>** -- *le chiffre publie
   RASSURAIT sur un geste qui retire 10 % du fichier.* Retirer des lignes
   d'exposition NULLE ne change evidemment aucun total d'exposition : la
   grandeur qui bouge est le COMPTE DE LIGNES. C'est `qualite/C3` a l'envers --
   la un compte cachait un effet, ici un effet cache un compte.
3. **`lignes_initiales` valait 360** -- pris APRES le geste. *Un compte pris
   apres l'acte ne peut pas montrer l'acte.*

⚠️⚠️ ET UNE TROISIEME ASYMETRIE, TROUVEE DANS MON PROPRE CORRECTIF. L'etape 4
du chantier `unite_exposition` a fait publier leur description aux CORRECTIONS,
puis aux SIGNALEMENTS -- et a laisse les EXCLUSIONS muettes. *Une exclusion est
pourtant le geste le plus fort des trois : elle RETIRE des contrats du calcul.*

═══ LES HUIT AUTRES — DES PHRASES QUI DECRIVENT UN AUTRE CODE ═══

| constat | ce que le fichier annoncait | ce que le code fait |
|---|---|---|
| `C3` | << Weight of Evidence · Target Encoding >> | `label` et `one_hot`, rien d'autre |
| `C4` | << Winsorisation (methode IQR) >> | quantiles 0,01 / 0,99 |
| `C6` | << Supprime egalement les colonnes >> | << On ne supprime pas >>, 3 lignes plus bas |
| `C10` | `agent_a2.run(result_a1)`, 3 fois | le module REFUSE cet appel (`plan=` exige) |
| `C11` | << relancer avec une configuration d'encodage etendue >> | cette configuration n'existe plus |
| `C12` | << RESTE A TRAITER ... les trois entrees ci-dessous >> | `SEUILS_WINSOR` est supprime |
| `C13` | `log_cout_total_sinistres` au dictionnaire ACPR | produite par AUCUN des 20 plans |
| `C14` | << 7 tests >> | 2 methodes |

⚠️ `C13` : l'entree est **conservee et MARQUEE**, pas retiree. *La retirer
effacerait la trace du contrat qu'un plan pourra vouloir honorer ; la laisser
muette la ferait passer pour une colonne vivante.*

═══ CE QUI RESTE OUVERT, ET POURQUOI ═══

⛔ **`a2/C9`** -- une moyenne rangee sous la cle `medianes`. **Rang 5, arbitre**
par Selasse : renommer la cle change le format d'un JSON persiste.

⛔ **`a2/C16`** -- `__init__` cree `/tmp/actuaria`. **Il a un JUMEAU OUVERT chez
le voisin : `a1/C7`, meme mecanisme.** Le corriger d'un seul cote recreerait
tres exactement l'asymetrie que cet audit poursuit, et ce n'est pas un texte :
instancier cesserait d'ecrire sur le disque, ce qui est un changement de
comportement. *Les deux ensemble, dans leur propre lot.*
"""

from __future__ import annotations

import glob
import inspect
import logging
import pathlib
import unittest
import warnings

from core.plan_tarifaire import PlanTarifaire
from core.qualite_donnees import synthese_qualite_donnees
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing import agent as _a2mod
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
)
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)

_SOURCE = pathlib.Path(_a2mod.__file__).read_text(encoding='utf-8')
_SOURCE_TEST = (pathlib.Path(_a2mod.__file__).parent
                / 'test_a2_preprocessing.py').read_text(encoding='utf-8')


def _sans_bruit(fn, *a, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return fn(*a, **kw)
        finally:
            logging.disable(precedent)


def _a2(df):
    def _run():
        r1 = AgentA1Ingestion(audit_path='/tmp', verbose=False).run(
            dataframe=df, branche='non_vie', sous_branche='auto')
        return AgentA2Preprocessing(audit_path='/tmp', verbose=False).run(
            r1, plan=_PLAN_AUTO)
    return _sans_bruit(_run)


def _avec_expo_nulle(n=400, seed=3, k=40):
    df = _portefeuille_auto(n, seed=seed)
    df.loc[df.index[:k], 'exposition'] = 0.0
    return df


class TestC5LeRapportNommeLActeReel(unittest.TestCase):
    """⚠️⚠️ LE CODE ETAIT CORRIGE, LE RAPPORT MENTAIT."""

    def test_LE_TEST_QUI_FERME_une_EXCLUSION_est_rangee_en_EXCLUSION(self):
        """⚠️ `_noter` codait `regle=2` en dur : tout devenait correction."""
        r2 = _a2(_avec_expo_nulle())
        rq = r2['rapport_qualite']
        self.assertEqual([(a.code, a.regle) for a in rq.exclusions],
                         [('exposition_non_positive_exclue', 1)])
        self.assertEqual(rq.corrections, [])
        print(f"    A2-1 l'exclusion est en regle 1, dans `exclusions` "
              f"({rq.exclusions[0].nb_lignes} lignes)")

    def test_le_COMPTE_est_pris_AVANT_le_geste(self):
        """⚠️ Il valait `len(df)` APRES exclusion : 360 -> 360 sur un fichier
        de 400. *Un compte pris apres l'acte ne peut pas montrer l'acte.*"""
        rq = _a2(_avec_expo_nulle())['rapport_qualite']
        self.assertEqual((rq.lignes_initiales, rq.lignes_retenues), (400, 360))
        print(f"    A2-2 lignes : {rq.lignes_initiales} -> "
              f"{rq.lignes_retenues}, le geste est VISIBLE")

    def test_l_effet_agrege_TROMPEUR_a_disparu(self):
        """⚠️⚠️ Il publiait « 299 -> 299 (+0,0 %) » sur un geste qui retire
        10 % du fichier. *Retirer des lignes d'exposition NULLE ne change aucun
        total d'exposition : le chiffre rassurait sur la mauvaise grandeur.*"""
        rq = _a2(_avec_expo_nulle())['rapport_qualite']
        self.assertIsNone(rq.exclusions[0].effet_agrege)
        texte = synthese_qualite_donnees(rq)
        self.assertNotIn('+0.0 %', texte)
        print("    A2-3 aucun effet agrege trompeur sur l'exclusion")

    def test_LE_RAPPORT_SIGNE_dit_EXCLUE_et_publie_son_motif(self):
        """⚠️⚠️ LA TROISIEME ASYMETRIE, dans mon propre correctif : l'etape 4
        a fait parler les corrections puis les signalements, et a laisse les
        EXCLUSIONS muettes."""
        texte = synthese_qualite_donnees(_a2(_avec_expo_nulle())
                                         ['rapport_qualite'])
        self.assertIn('EXCLUE(S)', texte)
        self.assertNotIn('CORRIGEE(S)', texte)
        self.assertIn("n'a jamais ete en vigueur", texte)
        print(f"    A2-4 le rapport signe dit EXCLUE **et** pourquoi "
              f"({len(texte.splitlines())} lignes)")

    def test_second_sens_un_portefeuille_SAIN_ne_declenche_RIEN(self):
        """⚠️ Sans ce sens, un rapport qui parlerait toujours passerait."""
        rq = _a2(_portefeuille_auto(400, seed=3))['rapport_qualite']
        self.assertIsNone(rq, f'un portefeuille sain produit un rapport : '
                              f'{rq and [a.code for a in rq.exclusions]}')
        print("    A2-5 portefeuille sain : aucun rapport, rien de publie")


class TestLesHuitPhrases(unittest.TestCase):
    """⚠️ Des phrases qui decrivaient un AUTRE code."""

    def test_C3_ni_WoE_ni_Target_Encoding_ne_sont_annonces(self):
        self.assertNotIn('Weight of Evidence', _SOURCE)
        self.assertNotIn('Target Encoding', _SOURCE)
        # ⚠️ Et les encodages ANNONCES sont ceux que le `Literal` admet.
        from core.plan_tarifaire import _ENCODAGES
        self.assertEqual(_ENCODAGES, {'one_hot', 'label', 'aucun'})
        print(f"    A2-6 aucun encodage fantome ; admis = "
              f"{sorted(_ENCODAGES)}")

    def test_C4_la_banniere_dit_QUANTILES_et_non_IQR(self):
        banniere = _SOURCE[:_SOURCE.index('DATA DICTIONNAIRE')]
        self.assertNotIn('méthode IQR', banniere)
        self.assertIn('QUANTILES', banniere)
        print("    A2-7 la banniere nomme la vraie methode : quantiles")

    def test_C6_la_docstring_ne_dit_plus_l_inverse_du_code(self):
        doc = inspect.getdoc(AgentA2Preprocessing._valider_sortie) or ''
        self.assertNotIn('Supprime également les colonnes', doc)
        self.assertIn('NE supprime AUCUNE colonne', doc)
        # ⚠️ ET ON VERIFIE LE FAIT, pas seulement la phrase : le module ne
        # supprime effectivement aucune colonne.
        self.assertNotIn('colonnes_supprimees.append', _SOURCE)
        print("    A2-8 la docstring et le code disent la meme chose")

    def test_C10_l_exemple_montre_un_appel_que_le_module_ACCEPTE(self):
        """⚠️⚠️ ON VERIFIE PAR EXECUTION, pas par lecture : l'appel sans
        `plan` doit bien etre refuse, sinon l'exemple corrige serait faux."""
        self.assertNotIn('agent_a2.run(result_a1)\n', _SOURCE)
        r1 = _sans_bruit(
            AgentA1Ingestion(audit_path='/tmp', verbose=False).run,
            dataframe=_portefeuille_auto(200, seed=3), branche='non_vie',
            sous_branche='auto')
        sans_plan = _sans_bruit(
            AgentA2Preprocessing(audit_path='/tmp', verbose=False).run, r1)
        self.assertFalse(sans_plan.get('success'),
                         "le module accepte l'appel sans plan : l'exemple "
                         "d'origine n'etait donc pas faux")
        print("    A2-9 l'exemple passe `plan=`, et l'appel sans plan est "
              "bien REFUSE (verifie par execution)")

    def test_C11_le_conseil_renvoie_au_PLAN_pas_a_une_config_disparue(self):
        # ⚠️⚠️ ON ASSERTE SUR LE CONSEIL, PAS SUR LE FICHIER. Ma premiere
        # version interdisait `VARS_CATEGORIELLES` dans tout l'en-tete : or le
        # fichier le CITE pour dire qu'il a ete SUPPRIME. *Une citation n'est
        # pas une affirmation* -- troisieme fois de la session que je m'y
        # reprends. On lit donc le bloc du conseil, et lui seul.
        self.assertNotIn("configuration d'encodage étendue", _SOURCE)
        self.assertIn('DECLARER ces colonnes au PLAN', _SOURCE)
        # ⚠️ Et le fait : la constante n'existe plus comme SYMBOLE.
        self.assertFalse(hasattr(_a2mod, 'VARS_CATEGORIELLES'))
        print("    A2-10 le conseil renvoie au plan, seule voie depuis la "
              "Phase 1")

    def test_C12_le_commentaire_ne_decrit_plus_un_etat_revolu(self):
        self.assertNotIn('RESTE À TRAITER', _SOURCE)
        self.assertIn('CE QUI RESTE VRAI', _SOURCE)
        print("    A2-11 le commentaire decrit l'etat d'aujourd'hui")

    def test_C13_la_colonne_orpheline_est_MARQUEE_pas_effacee(self):
        """⚠️⚠️ ON RE-DERIVE l'orphelinat : le marquer sans le verifier serait
        recopier une mesure d'hier."""
        orpheline = 'log_cout_total_sinistres'
        producteurs = [f for f in sorted(glob.glob('plans/*.yaml'))
                       if orpheline in
                       set(PlanTarifaire.depuis_yaml(f).colonnes_produites())]
        self.assertEqual(producteurs, [],
                         f'{orpheline} est desormais produite par '
                         f'{producteurs} : le marquage est perime')
        self.assertIn(orpheline, _a2mod.DATA_DICTIONNAIRE)
        self.assertIn('produite par aucun plan',
                      _a2mod.DATA_DICTIONNAIRE[orpheline].get('statut', ''))
        print(f"    A2-12 {orpheline} : 0 producteur mesure, entree conservee "
              f"et MARQUEE")

    def test_C14_l_en_tete_ne_porte_plus_de_compte_a_la_main(self):
        import re
        titre = _SOURCE_TEST.split('"""')[1].strip().splitlines()[0]
        self.assertEqual(re.findall(r'(\d+)\s+tests', titre), [])
        print("    A2-13 aucun compte de tests dans la ligne de titre")


if __name__ == '__main__':
    unittest.main()
