"""⚠️⚠️ UNE SIGNATURE QUI NE VALIDE RIEN EST PIRE QUE PAS DE SIGNATURE.

Étape ③ du chantier 1-B, décidée par Selasse le 01/09/2026 : porter le canal
`qualite_validee_par` sur le chemin agent — `pipeline_agents` et `A1.run`.

⚠️⚠️ ET C'EST LÀ QUE LA CONCEPTION SE JOUE. Un paramètre accepté que **rien ne
consomme** est exactement la silhouette de `socle/C2` : de la plomberie posée
que rien n'alimente. Pire ici qu'ailleurs, parce qu'il porte un NOM D'ACTUAIRE :

> *Un canal qui avale une signature sans rien valider laisse croire à une
> validation qui n'a pas eu lieu.*

Le canal EXISTE donc — typé, documenté, au même nom et au même sens que sur le
chemin déclaratif — et il **REFUSE**, en nommant l'étape qui lui donnera un
objet. L'étape ⑤ remplace le refus par l'appel réel.

⚠️ POURQUOI IL N'A PAS ENCORE D'OBJET, MESURÉ ET NON SUPPOSÉ. Le chemin agent
n'appelle pas `controler_qualite` (`qualite/C4`), et A1 **score sans agir** :
mesuré le 01/09, 600 fréquences négatives sur 10 000 le font virer au ROUGE et
les 10 000 lignes ressortent. Il n'y a donc **aucun blocage à lever**.

⚠️ SOURCE UNIQUE. Les deux points d'entrée partagent `exiger_canal_sans_objet` :
*deux messages divergents auraient donné deux doctrines.*

⚠️ AUCUN EURO — `SG-5` : le run sans signature est identique, ligne à ligne, à
ce qu'il était avant ce lot. Le canal ne gêne personne tant qu'on ne lui
demande rien.
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
    SignatureSansObjet,
    exiger_canal_sans_objet,
)
from direction_non_vie.tarification import pipeline_agents as PA
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_PLAN = PlanTarifaire.depuis_yaml(str(_RACINE / 'plans' / 'auto.yaml'))
_E, _F, _C = _PLAN.exposition, _PLAN.cible_frequence, _PLAN.cible_cout


def _cadre(n=500, seed=9):
    rng = np.random.default_rng(seed)
    nb = rng.integers(0, 3, n).astype(float)
    cout = np.where(nb > 0, rng.uniform(500, 5000, n).round(2), 0.0)
    return pd.DataFrame({
        _E: np.ones(n), _F: nb, _C: cout,
        'prime_acquise': (200 + np.arange(n) * 0.01).round(2)})


def _muet(fonction, *a, **k):
    """A1 imprime un rapport ; on mesure, on ne le lit pas ici."""
    with contextlib.redirect_stdout(io.StringIO()):
        return fonction(*a, **k)


def _parametres(fonction):
    """Les noms de paramètres RÉELS, par signature — jamais au texte."""
    return set(inspect.signature(fonction).parameters)


class TestCanalSignatureAgent(unittest.TestCase):

    def test_SG_1_les_deux_points_d_entree_PORTENT_le_canal(self):
        """⚠️ Le canal doit exister aux DEUX endroits, sous le MÊME nom que sur
        le chemin déclaratif. *Deux noms pour le même geste feraient deux
        doctrines, et c'est le défaut que la fusion 1-B existe pour fermer.*"""
        for nom, fonction in (('pipeline_agents', PA.pipeline_agents),
                              ('A1.run', AgentA1Ingestion.run)):
            self.assertIn(
                'qualite_validee_par', _parametres(fonction),
                f'{nom} ne porte pas le canal de signature')
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        self.assertIn('qualite_validee_par', _parametres(pipeline_complet),
                      'le chemin declaratif a change de nom : les deux '
                      'chemins divergeraient')
        print("    OK SG-1 le canal existe aux 2 entrees agent, meme nom que "
              "sur le chemin declaratif")

    def test_SG_2_une_signature_est_REFUSEE_tant_qu_elle_n_a_pas_d_objet(self):
        """⚠️⚠️ LE CŒUR DU LOT. Avaler le nom en silence serait le défaut.

        ⚠️⚠️ RESSERRÉ SUR `A1.run` LE 02/09/2026. `pipeline_agents` ne refuse
        plus : depuis 1-B il PASSE le nom à la couche, qui seule peut lever le
        blocage — c'est `SG-10` qui le tient. *Le canal n'a pas disparu, il a
        enfin un objet.* `A1.run`, lui, n'appelle toujours pas la couche : pour
        lui le refus reste la seule réponse honnête.
        """
        df = _cadre()
        with self.assertRaises(SignatureSansObjet) as ctx2:
            _muet(AgentA1Ingestion().run, sous_branche='auto',
                  dataframe=df.copy(), plan=_PLAN,
                  qualite_validee_par='Selasse Sekle')
        self.assertEqual(ctx2.exception.appelant, 'A1.run')
        self.assertEqual(ctx2.exception.nom, 'Selasse Sekle')
        print("    OK SG-2 A1.run LEVE SignatureSansObjet et nomme son "
              "appelant ; pipeline_agents a desormais un objet")

    def test_SG_3_le_refus_DIT_pourquoi_et_ou_aller(self):
        """⚠️ Un refus qui ne dit pas où aller transforme un garde-fou en mur.

        *Le message doit nommer l'étape qui donnera un objet au canal ET le
        chemin qui porte la couche aujourd'hui.*
        """
        # ⚠️ Le témoin est `A1.run` depuis 1-B : `pipeline_agents` ne refuse
        # plus, il transmet. *Un refus qui a trouvé son objet cesse d'être un
        # refus.*
        with self.assertRaises(SignatureSansObjet) as ctx:
            _muet(AgentA1Ingestion().run, sous_branche='auto',
                  dataframe=_cadre(), plan=_PLAN, qualite_validee_par='X')
        msg = str(ctx.exception)
        self.assertIn('qualite/C4', msg, 'le refus ne nomme pas la cause')
        self.assertIn('1-B', msg, "le refus ne nomme pas l'etape")
        self.assertIn('pipeline_complet', msg,
                      'le refus ne dit pas ou aller aujourd hui')
        self.assertIn('ne validerait rien', msg)
        print(f"    OK SG-3 le refus nomme la cause, l'etape et l'issue "
              f"({len(msg)} car.)")

    def test_SG_4_le_message_a_une_SOURCE_UNIQUE(self):
        """⚠️ Deux messages divergents auraient donné deux doctrines.

        Assiette : les APPELS réels, par AST — pas les mentions en prose.
        """
        # ⚠️ `pipeline_agents` a QUITTÉ cette liste le 02/09 : il ne refuse
        # plus, il transmet (1-B). *Garder son nom ici aurait exigé un refus
        # qui n'a plus lieu d'être — et le contrôle serait devenu faux.*
        chemin = 'direction_non_vie/tarification/a1_ingestion/agent.py'
        src = (_RACINE / chemin).read_text(encoding='utf-8')
        appels = [n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.Call)
                  and getattr(n.func, 'id', '') == 'exiger_canal_sans_objet']
        self.assertEqual(
            len(appels), 1,
            f'{chemin} : {len(appels)} appels a la source unique')
        leve = [n for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.Raise)
                and 'SignatureSansObjet' in ast.unparse(n)]
        self.assertEqual(
            leve, [],
            f'{chemin} recopie la levee au lieu d appeler la source unique')

        # ⚠️⚠️ ET `pipeline_agents` NE DOIT PLUS REFUSER DU TOUT : un refus
        # residuel avalerait la signature avant que la couche ne la voie.
        src_pa = (_RACINE / 'direction_non_vie' / 'tarification'
                  / 'pipeline_agents.py').read_text(encoding='utf-8')
        residu = [n.lineno for n in ast.walk(ast.parse(src_pa))
                  if isinstance(n, ast.Call)
                  and getattr(n.func, 'id', '') == 'exiger_canal_sans_objet']
        self.assertEqual(
            residu, [],
            f"pipeline_agents refuse encore (ligne(s) {residu}) alors qu'il "
            f"transmet : la signature n'atteindrait jamais la couche")
        print("    OK SG-4 1 appel a la source unique dans A1.run, 0 levee "
              "recopiee, 0 refus residuel dans pipeline_agents")

    def test_SG_10_pipeline_agents_TRANSMET_la_signature_a_la_couche(self):
        """⚠️⚠️ CE QUE `SG-2` NE PEUT PLUS PROUVER, ET QUI EST LE VRAI OBJET.

        Le canal a été construit à l'étape ③ pour être branché à l'étape ⑤. Il
        l'est : `pipeline_agents` passe le nom à `preambule_qualite`, qui seule
        peut lever le blocage. *Un canal qui refuse toujours et un canal qui
        avale en silence échouent de la même façon — on vérifie qu'il PORTE.*
        """
        src = (_RACINE / 'direction_non_vie' / 'tarification'
               / 'pipeline_agents.py').read_text(encoding='utf-8')
        portes = [n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.Call)
                  and getattr(n.func, 'id', '') == 'preambule_qualite']
        self.assertEqual(len(portes), 1, 'la porte doit rester unique')
        passe = [k.arg for k in portes[0].keywords]
        self.assertIn(
            'qualite_validee_par', passe,
            "la porte est appelee SANS la signature : un blocage ne pourrait "
            "jamais etre leve sur le chemin agent")
        print(f"    OK SG-10 pipeline_agents transmet {sorted(passe)} a la "
              f"porte unique")

    def test_SG_5_aucun_euro_le_canal_ne_gene_personne_sans_signature(self):
        """⚠️⚠️ « AUCUN EURO » SE PROUVE : sans signature, rien ne change.

        Le canal est un paramètre par défaut à `None` ; le run doit être
        strictement identique à ce qu'il était avant ce lot.
        """
        df = _cadre()
        avant = _muet(AgentA1Ingestion().run, sous_branche='auto',
                      dataframe=df.copy(), plan=_PLAN)
        apres = _muet(AgentA1Ingestion().run, sous_branche='auto',
                      dataframe=df.copy(), plan=_PLAN,
                      qualite_validee_par=None)
        self.assertTrue(avant['success'] and apres['success'])
        self.assertEqual(len(avant['dataframe']), len(df))
        self.assertTrue(avant['dataframe'].equals(apres['dataframe']),
                        'passer None change le resultat')
        self.assertEqual(float(avant['score_qual']),
                         float(apres['score_qual']))
        self.assertIsNone(exiger_canal_sans_objet(None, 'temoin'))
        print(f"    OK SG-5 aucun euro : {len(df)} lignes identiques avec et "
              f"sans le parametre, score inchange")

    def test_SG_6_le_canal_DECLARE_qu_il_n_a_pas_encore_d_objet(self):
        """⚠️ Une porte prête mais muette ressemble à de la plomberie morte —
        le motif de `socle/C2`, et la leçon de `PQ-7`.

        ⚠️⚠️ ASSIETTE : la DOCSTRING publiée, normalisée sans accents. *Mon
        contrôle jumeau `PQ-7` avait cherché « deplacerait » dans un texte qui
        écrit « déplacerait » : un contrôle sur du français se normalise,
        sinon il mesure l'orthographe et non le fond.*
        """
        import unicodedata
        for nom, fonction in (('pipeline_agents', PA.pipeline_agents),
                              ('A1.run', AgentA1Ingestion.run)):
            doc = unicodedata.normalize(
                'NFKD', inspect.getdoc(fonction) or '')
            doc = ''.join(c for c in doc
                          if not unicodedata.combining(c)).lower()
            self.assertIn('qualite_validee_par', doc,
                          f'{nom} ne declare pas son canal')
            self.assertIn("pas encore d'objet", doc,
                          f'{nom} ne dit pas que le canal est en attente')
            self.assertIn('1-b', doc, f'{nom} ne nomme pas l etape')
        print("    OK SG-6 les 2 entrees DECLARENT que le canal attend 1-B")

    def test_SG_7_second_sens_le_chemin_declaratif_ACCEPTE_toujours(self):
        """⚠️⚠️ LE SECOND SENS, ET IL EST INDISPENSABLE.

        Un garde-fou qui refuserait la signature PARTOUT aurait cassé le seul
        chemin où elle a un objet. *Le refus porte sur le chemin agent, pas
        sur le geste.*
        """
        from core.qualite_donnees import controler_qualite
        df = _cadre(n=1_000, seed=31)
        df.loc[0:59, _F] = -1.0
        df.loc[0:59, _C] = 0.0
        bloque = controler_qualite(df.copy(), _PLAN)
        self.assertTrue(bloque.bloque, 'le temoin ne bloque plus : la mesure '
                                       'ne prouverait rien')
        signe = controler_qualite(df.copy(), _PLAN,
                                  qualite_validee_par='Selasse Sekle')
        self.assertFalse(signe.bloque,
                         'la signature ne leve plus le blocage la ou elle a '
                         'un objet')
        self.assertEqual(signe.validee_par, 'Selasse Sekle')
        print("    OK SG-7 second sens : la signature garde son objet sur le "
              "chemin declaratif")


if __name__ == '__main__':
    unittest.main(verbosity=2)
