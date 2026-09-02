"""⚠️⚠️ UN RUN PEUT ETRE VERT ET N'AVOIR PRODUIT AUCUN DOCUMENT.

Constat `services/C13`, ouvert par Selasse le 02/09/2026 apres la question
<< est-ce qu'a ce stade tout va bien avec certitude ? >>.

Les **neuf** exportateurs du module partagent une seule et meme forme :

```
  try:   ... construire le classeur ...  return octets
  except Exception as e:
      logger.error(...);  return b''
```

Ce n'est PAS silencieux dans le journal -- c'est silencieux dans le VERDICT.
Mesure du 02/09, defaut simule dans le rendu :

```
  Excel A6 sain  : 15 437 octets
  Excel A6 casse :      0 octet
  success        : True        <- inchange
  statut RAG     : inchange    <- inchange
```

> *C'est le mecanisme qui a cache `conformite/C16` : un Excel entier disparu
> sur un logger.warning, sous une gate verte de 1 013 tests.*

═══ CE QUE LE CORRECTIF FAIT, ET CE QU'IL NE FAIT PAS ═══

⚠️⚠️ L'INVENTAIRE SE DERIVE DES OCTETS REELS. Un inventaire tenu a la main
divergerait le jour ou un export change -- c'est la doctrine d'`_entete_alerte`
(*le chiffre et la ligne qu'il decrit viennent de la meme source*), et le
defaut que `78f1a4e` a corrige ce matin.

⚠️ LA TABLE PORTE LA DEMANDE, PAS SEULEMENT LE RESULTAT : une entree n'existe
que si le livrable a ete DEMANDE. Sans cela l'avertissement crierait sur chaque
run sans PDF, *et un avertissement permanent cesse d'etre lu.*

⚠️ IL NE DEGRADE PAS LE STATUT RAG, delibrement. Le RAG mesure la qualite du
TARIF ; un document manquant est un incident de RENDU. *Rendre a chacun sa
propre question* -- l'arbitrage de `qualite/C16`, applique ici.

⛔⛔ ET IL NE MET PAS L'AVERTISSEMENT DANS LES DOCUMENTS. Deux raisons mesurees,
pas supposees : un document ne peut pas annoncer sa PROPRE absence, et les
surfaces sont rendues AVANT que l'inventaire soit complet. *L'avertissement
appartient au compte rendu du run.* `SC-6` epingle cette limite au lieu de la
taire.

═══ ⛔⛔ CE QUE LA MESURE A REFUTE DANS MON PREMIER CORRECTIF ═══

J'avais appende l'avertissement -- une CHAINE -- dans `alertes_modele`.
`pipeline_agents` y lit `x.get('code')` : ces alertes sont des DICTS, et le
chemin agent aurait leve `AttributeError`.

> **Un canal existant n'accepte pas n'importe quelle forme parce qu'il porte un
> nom qui convient.**

Et ce n'etait pas le bon canal non plus : `alertes_modele` n'atteint AUCUNE des
trois surfaces signees. `SC-7` tient les deux moities de cette lecon.
"""
from __future__ import annotations

import ast
import contextlib
import io
import logging
import pathlib
import unittest
from unittest import mock

import direction_non_vie.tarification.services.tarif_excel as _xl
from core.conformite_reglementaire import (
    MARQUEUR_LIVRABLE_ABSENT,
    avertissement_livrables_absents,
)
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
)
from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
from direction_non_vie.tarification.a6_comparaison.agent import (
    AgentA6Comparaison,
)
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)

_RACINE = pathlib.Path(__file__).resolve().parents[2]


def _muet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return fn(*a, **kw)
        finally:
            logging.disable(precedent)


def _jusqu_a_a3(n=400, seed=4):
    df = _portefeuille_auto(n, seed=seed)
    r1 = _muet(AgentA1Ingestion(audit_path='/tmp', verbose=False).run,
               dataframe=df, branche='non_vie', sous_branche='auto')
    r2 = _muet(AgentA2Preprocessing(audit_path='/tmp', verbose=False).run,
               r1, plan=_PLAN_AUTO)
    r3 = _muet(AgentA3GLM(audit_path='/tmp', verbose=False).run,
               r2, plan=_PLAN_AUTO, generer_graphiques=False)
    return r1, r2, r3


def _a6(r1, r2, r3):
    return _muet(AgentA6Comparaison(audit_path='/tmp', verbose=False).run,
                 result_a3=r3, result_a1=r1, result_a2=r2,
                 generer_graphiques=False, generer_rapport_equipe=False)


class TestLivrablesAbsents(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.socle = _jusqu_a_a3()

    def test_SC_1_LE_CONSTAT_un_run_VERT_perd_un_document_et_le_DIT(self):
        """⚠️⚠️ LA MESURE QUI A OUVERT LE CONSTAT, DEVENUE CONTROLE.

        On fait tomber le rendu de l'Excel A6 comme le ferait un vrai defaut,
        et on verifie que le run le DIT au lieu de rendre `b''` en silence.
        """
        sain = _a6(*self.socle)
        self.assertGreater(len(sain.get('excel_bytes') or b''), 0,
                           'le temoin sain ne produit deja pas d Excel : le '
                           'controle ne prouve rien')
        self.assertEqual(sain.get('livrables_absents'), [],
                         'le run sain declare un livrable absent')

        with mock.patch.object(_xl, '_kpi',
                               side_effect=RuntimeError('defaut simule')):
            casse = _a6(*self.socle)
        self.assertEqual(len(casse.get('excel_bytes') or b''), 0,
                         'la panne simulee n a pas atteint l Excel')
        self.assertEqual(
            casse.get('livrables_absents'), ['Excel A6'],
            "l'Excel a disparu et le verdict du run n'en dit rien : c'est "
            "exactement le mecanisme qui a cache `conformite/C16`")
        self.assertIn(MARQUEUR_LIVRABLE_ABSENT,
                      casse.get('avertissement_livrables') or '')
        print(f"    SC-1 sain {sain['livrables_tailles']} -> casse "
              f"{casse['livrables_tailles']}, absent "
              f"{casse['livrables_absents']}")

    def test_SC_2_l_inventaire_DERIVE_des_octets_il_ne_se_declare_pas(self):
        """⚠️⚠️ *Le chiffre et la chose qu'il decrit viennent de la meme
        source, ou ils finiront par se contredire.* La lecon de `78f1a4e`,
        appliquee au meme jour sur un autre couple.

        Assiette : les tailles publiees DOIVENT egaler la longueur des octets
        rendus, livrable par livrable.
        """
        r = _a6(*self.socle)
        tailles = r.get('livrables_tailles') or {}
        self.assertTrue(tailles, 'aucun livrable inventorie')
        attendu = {
            'Excel A6': len(r.get('excel_bytes') or b''),
            'Word tarification': len(r.get('word_bytes') or b''),
            'HTML tarification': len(r.get('html_bytes') or b''),
        }
        for nom, n in attendu.items():
            self.assertEqual(
                tailles.get(nom), n,
                f"'{nom}' : l'inventaire annonce {tailles.get(nom)} et les "
                f"octets rendus en font {n} -- l'inventaire est DECLARE, pas "
                f"derive")
        # ⚠️ SECOND SENS : la liste des absents derive de la MEME table.
        self.assertEqual(
            sorted(r.get('livrables_absents') or []),
            sorted(k for k, v in tailles.items() if not v),
            'la liste des absents ne derive pas des tailles publiees')
        print(f"    SC-2 {len(tailles)} livrables, chaque taille == len(octets)")

    def test_SC_3_second_sens_rien_de_manquant_RIEN_de_publie(self):
        """⚠️ Un avertissement permanent est un avertissement qu'on cesse de
        lire. Et un livrable NON DEMANDE n'est pas un livrable manquant."""
        self.assertIsNone(avertissement_livrables_absents(
            {'Excel A6': b'xxx', 'Word': b'yyy'}))
        self.assertIsNone(avertissement_livrables_absents({}),
                          'un run qui ne demande rien declenche l alerte')
        self.assertIsNone(avertissement_livrables_absents(None))
        r = _a6(*self.socle)
        self.assertIsNone(r.get('avertissement_livrables'),
                          'le run sain publie un avertissement')
        print("    SC-3 second sens : tout produit -> None ; rien demande "
              "-> None")

    def test_SC_4_le_texte_porte_le_TOTAL_pas_seulement_les_manquants(self):
        """⚠️ *Un compte sans son total ne dit rien.* << 1 document manquant >>
        n'a pas le meme poids selon qu'on en attendait deux ou dix."""
        texte = avertissement_livrables_absents(
            {'a': b'', 'b': b'xx', 'c': b'yy'}) or ''
        self.assertIn('1 document(s) sur 3', texte)
        self.assertIn('a', texte)
        # ⚠️ Il dit aussi que le TARIF reste valide : la panne est un incident
        # de RENDU, pas une remise en cause du calcul.
        self.assertIn('reste valide', texte)
        self.assertIn('RESTITUTION', texte)
        print(f"    SC-4 le texte porte manquants/total et distingue le "
              f"CALCUL du RENDU ({len(texte)} car.)")

    def test_SC_5_l_orchestrateur_publie_l_inventaire_dans_SON_verdict(self):
        """⚠️⚠️ *Un calcul qui n'atteint aucun livrable n'existe pas* -- la
        lecon de `services/C7` et `socle/C1`.

        Assiette : le `resume()` de `pipeline_agents`, par AST. C'est le
        compte rendu serialisable du run, celui qui part a l'appelant.
        """
        src = (_RACINE / 'direction_non_vie' / 'tarification'
               / 'pipeline_agents.py').read_text(encoding='utf-8')
        cles = {c.value for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.Dict)
                for c in n.keys
                if isinstance(c, ast.Constant) and isinstance(c.value, str)}
        for attendue in ('livrables_absents', 'livrables_tailles'):
            self.assertIn(
                attendue, cles,
                f"l'orchestrateur ne publie pas '{attendue}' : l'inventaire "
                f"s'arrete a A6 et n'atteint pas le compte rendu du run")
        print("    SC-5 le resume() du run porte l'inventaire des livrables")

    def test_SC_6_le_statut_RAG_n_est_PAS_degrade_et_c_est_ARBITRE(self):
        """⚠️⚠️ LA LIMITE, EPINGLEE PLUTOT QUE TUE.

        Le RAG mesure la qualite du TARIF ; un document manquant est un
        incident de RENDU. Les confondre referait le defaut de `qualite/C16`,
        ou A1 jugeait une question qui n'etait pas la sienne.

        ⚠️ Et l'avertissement n'entre PAS dans les documents : un document ne
        peut pas annoncer sa propre absence, et les surfaces sont rendues
        AVANT que l'inventaire soit complet. *Cette limite est reelle ; la
        dire vaut mieux que de laisser croire le contraire.*
        """
        sain = _a6(*self.socle)
        with mock.patch.object(_xl, '_kpi',
                               side_effect=RuntimeError('defaut simule')):
            casse = _a6(*self.socle)
        self.assertEqual(
            casse.get('statut_rag'), sain.get('statut_rag'),
            "le statut RAG a bouge sur un incident de RENDU : il mesurerait "
            "deux questions a la fois")
        self.assertTrue(casse.get('success'),
                        'un document manquant fait echouer le run : '
                        "l'arbitrage disait le contraire")
        print(f"    SC-6 RAG {sain.get('statut_rag')} inchange, success True "
              f"-- le rendu et le tarif restent deux questions")

    def test_SC_7_l_avertissement_n_entre_PAS_dans_alertes_modele(self):
        """⛔⛔ LE BUG QUE J'AI FAILLI LIVRER, DEVENU CONTROLE.

        J'avais appende l'avertissement -- une CHAINE -- dans
        `alertes_modele`. `pipeline_agents` y lit `x.get('code')` : ces
        alertes sont des DICTS, et le chemin agent aurait leve
        `AttributeError`.

        > **Un canal existant n'accepte pas n'importe quelle forme parce qu'il
        > porte un nom qui convient.**
        """
        # ⚠️⚠️ CE CONTROLE A ETE REFAIT : SA PREMIERE VERSION ETAIT DU DECOR.
        # Elle bouclait sur `alertes_modele` du temoin -- une liste VIDE -- et
        # passait donc quoi qu'il arrive. *Un controle qui ne peut pas
        # distinguer les deux cas qu'il oppose ne prouve rien.*
        #
        # PIECE 1 : L'ENJEU EST REEL. Le consommateur de production LEVE sur
        # une chaine ; sans cela, l'invariant de type serait cosmetique.
        consommateur = [str(x.get('code')) for x in [{'code': 'ok'}]]
        self.assertEqual(consommateur, ['ok'], 'premisse : la forme attendue')
        with self.assertRaises(AttributeError):
            [str(x.get('code')) for x in ['une chaine']]

        # PIECE 2 : LE CODE D'A6 N'APPEND QUE DES DICTS. Assiette : les appels
        # `.append(...)` sur `_alertes_modele`, par AST -- la ou ma premiere
        # version du correctif avait mis un f-string.
        src = (_RACINE / 'direction_non_vie' / 'tarification'
               / 'a6_comparaison' / 'agent.py').read_text(encoding='utf-8')
        appendus = [ast.unparse(n.args[0])
                    for n in ast.walk(ast.parse(src))
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'append'
                    and getattr(n.func.value, 'id', '') == '_alertes_modele'
                    and n.args]
        self.assertTrue(appendus, "plus aucun append sur `_alertes_modele` : "
                                  "ce controle ne surveille plus rien")
        for expr in appendus:
            self.assertNotIn(
                'avertissement', expr.lower(),
                f"A6 appende un avertissement TEXTE dans `alertes_modele` "
                f"({expr}) : `pipeline_agents` y fait `.get('code')` et le "
                f"chemin agent leverait `AttributeError`")
            self.assertFalse(
                expr.startswith(("f'", 'f"', "'", '"')),
                f"A6 appende un litteral CHAINE dans `alertes_modele` "
                f"({expr[:40]}) : le canal attend des dicts")

        # PIECE 3 : ET SUR LE RUN REEL, la forme tient dans les deux cas.
        sain = _a6(*self.socle)
        with mock.patch.object(_xl, '_kpi',
                               side_effect=RuntimeError('defaut simule')):
            casse = _a6(*self.socle)
        for etiquette, r in (('sain', sain), ('casse', casse)):
            for a in (r.get('alertes_modele') or []):
                self.assertIsInstance(
                    a, dict,
                    f"run {etiquette} : `alertes_modele` porte un "
                    f"{type(a).__name__} au lieu d'un dict")
        print(f"    SC-7 le consommateur LEVE sur une chaine ; "
              f"{len(appendus)} append(s) dans A6, aucun texte")


if __name__ == '__main__':
    unittest.main(verbosity=2)
