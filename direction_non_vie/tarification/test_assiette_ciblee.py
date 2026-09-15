"""UNE ASSIETTE REDUITE NE SE CROIT PAS — ELLE SE REJOUE SUR DES VRAIS ROUGES.

Cet outil decide quels sceaux tournent pour un lot. **S'il se trompe, il ne
rend pas un faux rouge : il rend un faux VERT** — le plus cher des deux, et
le seul qui ne se remarque pas. Cette sentinelle est donc ecrite contre
l'outil, pas pour lui.

⚠️⚠️ LA QUESTION N'EST PAS << COMBIEN DE TESTS ECONOMISE-T-ON >>, C'EST
<< CETTE ASSIETTE AURAIT-ELLE ATTRAPE LES ROUGES QUE LA GATE COMPLETE A
REELLEMENT TROUVES ? >>. Le dépôt en a quatre, mesures le 14/09/2026 :

  BP-4  `test_bloc_prix_assiette`          <- a6_comparaison/agent.py
        il IMPORTE et il NOMME
  CM-4  `test_conditions_mesure`           <- a6_comparaison/agent.py
        ⚠️ il N'IMPORTE PAS : il relit le TEXTE de l'agent par AST.
        **C'est le rouge qui prouve que le critere `N` est indispensable.**
  AG-6  `test_agents_quatre_constats`      <- pipeline_agents.py + appelant
        une PHRASE DE PORTEE, pas un comportement
  RD-7  `test_racine_derivee`              <- n'importe quel fichier
  VC-4  `test_verdict_independant_de_la_console`
        ⚠️⚠️ CES DEUX-LA NE NOMMENT NI N'IMPORTENT RIEN. Ils BALAIENT le
        depot. **Ce sont eux qui ont rougi le 14/09 au soir, et une
        assiette `I | N` les aurait rates tous les deux.**

⛔⛔ ET L'ERREUR QUE J'AI FAITE EN ECRIVANT L'OUTIL EST SCELLEE ICI :
ma premiere version comptait `ast.walk()` comme un balayage de disque et
classait **124 modules sur 194** en balayeurs — l'assiette devenait le
corpus entier et le gain disparaissait, sans qu'aucun test ne s'en plaigne.
`AC-5` interdit ce retour.

CE QUE CETTE SENTINELLE EXIGE :

  AC-1  TOUT balayeur est dans l'assiette, quoi qu'on touche
  AC-2  un sceau qui NOMME sans importer est retenu   (le cas `CM-4`)
  AC-3  un sceau qui IMPORTE est retenu               (le cas `BP-4`)
  AC-4  **LE REJEU** : les cinq rouges reels ci-dessus sont dans
        l'assiette de leur lot
  AC-5  `ast.walk` n'est PAS un balayage de disque
  AC-6  le TEMOIN : l'assiette n'est ni vide ni le corpus entier par
        accident, et l'outil DIT quand elle vaut le corpus
  AC-7  le verdict n'est pas relu ici : il est IMPORTE de `gate.py`.
        *Une seconde lecture de verdict divergerait au premier correctif —
        c'est exactement ce que `GATE-1` a coute.*
"""
import ast
import os
import pathlib
import sys
import unittest

_RACINE = pathlib.Path(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if str(_RACINE / 'scripts') not in sys.path:
    sys.path.insert(0, str(_RACINE / 'scripts'))

import assiette_ciblee as AC

_A6 = 'direction_non_vie/tarification/a6_comparaison/agent.py'
_PIPE = 'direction_non_vie/tarification/pipeline_agents.py'
_LOCAL = 'scripts/rapport_tarif_local.py'
#: Les rouges REELS, et le lot qui les a produits. *Un rejeu sur des cas
#: inventes ne prouverait que mon imagination.*
_REJEU = {
    'direction_non_vie/tarification/test_bloc_prix_assiette.py': [_A6],
    'direction_non_vie/tarification/test_conditions_mesure.py': [_A6],
    'direction_non_vie/tarification/test_agents_quatre_constats.py':
        [_PIPE, _LOCAL],
    'direction_non_vie/tarification/test_racine_derivee.py': [_A6],
    'direction_non_vie/tarification/test_verdict_independant_de_la_console.py':
        [_A6],
}


class TestAssietteCiblee(unittest.TestCase):

    # ── AC-1 — tout balayeur tourne toujours ────────────────────────────
    def test_AC1_tout_balayeur_est_dans_l_assiette(self):
        """Un lot qui ne touche RIEN de ce qu'ils nomment ou importent doit
        quand meme les faire tourner : ce sont les garde-fous transverses,
        et ils rougissent sur un fichier qu'ils n'ont jamais nomme."""
        #: un fichier que personne n'importe ni ne nomme
        retenus = AC.assiette(['core/un_fichier_qui_n_existe_pas.py'])
        balayeurs = set()
        for rel in AC.modules_de_test(AC._ZONE_DEFAUT):
            arbre = AC._arbre(rel)
            if arbre is not None and AC._est_balayeur(arbre):
                balayeurs.add(rel)
        self.assertTrue(balayeurs, 'temoin mort : aucun balayeur recense')
        manquants = sorted(balayeurs - set(retenus))
        self.assertEqual(
            manquants, [],
            f'{len(manquants)} sceau(x) qui BALAIENT le depot sont hors de '
            f"l'assiette : ils rougiraient a la gate complete, un lot trop "
            f'tard. {manquants[:6]}')

    # ── AC-2 — nommer sans importer suffit ──────────────────────────────
    def test_AC2_un_sceau_qui_NOMME_sans_importer_est_retenu(self):
        """Le cas `CM-4`, mesure : il relit le TEXTE de l'agent par AST et
        n'en importe rien. Une assiette bâtie sur les seuls imports le
        raterait — et ce depot est plein de sceaux de cette forme."""
        rel = 'direction_non_vie/tarification/test_conditions_mesure.py'
        source = (_RACINE / rel).read_text(encoding='utf-8', errors='replace')
        self.assertNotIn(
            'a6_comparaison.agent import', source,
            'temoin mort : ce sceau importe desormais l agent, il ne '
            'demontre plus rien sur le critere `N`')
        raisons = AC.assiette([_A6]).get(rel, set())
        self.assertTrue(
            any(r.startswith('N') for r in raisons),
            f'le critere `N` ne retient plus {rel} : raisons={raisons}')

    # ── AC-3 — importer suffit, ET LE CRITERE PORTE SON POIDS ───────────
    def test_AC3_un_sceau_qui_IMPORTE_est_retenu(self):
        """⚠️⚠️ CE CONTROLE A ETE ECRIT FAUX, ET LE PLANT L'A DIT. Sa
        premiere version verifiait seulement que le module etait DANS
        l'assiette. Or `test_bloc_prix_assiette` y entre AUSSI par `N` :
        retirer entierement le critere `I` de l'outil laissait ce controle
        VERT. *La sentinelle verifiait la PRESENCE et non la RAISON --
        exactement le defaut de sceau deja inscrit au recueil.*

        Mesure qui tranche : `I` est la SEULE raison de **22 modules** pour
        un lot A6, dont `test_a6_comparaison` lui-meme. Le critere n'est
        donc pas redondant, et son retrait doit MORDRE."""
        retenus = AC.assiette([_A6])
        rel = 'direction_non_vie/tarification/test_bloc_prix_assiette.py'
        self.assertIn(
            'I import', retenus.get(rel, set()),
            f'{rel} n est plus retenu PAR L IMPORT : le critere `I` ne '
            f'fonctionne plus, meme si un autre critere le rattrape')
        seuls = sorted(m for m, r in retenus.items() if r == {'I import'})
        self.assertTrue(
            seuls,
            "AUCUN module n'est retenu par le SEUL import : le critere `I` "
            'ne porte plus aucun poids propre, et son retrait passerait '
            'inapercu')

    # ── AC-4 — LE REJEU sur les rouges reels ────────────────────────────
    def test_AC4_les_rouges_reels_du_14_09_sont_tous_dans_l_assiette(self):
        """*Une reduction d'assiette qui n'est pas rejouee sur des rouges
        VECUS est une opinion.*"""
        rates = []
        for rel, touches in _REJEU.items():
            if rel not in AC.assiette(touches):
                rates.append(rel)
        self.assertEqual(
            rates, [],
            f'{len(rates)} rouge(s) REELLEMENT survenu(s) le 14/09 ne '
            f"seraient pas attrapes par l'assiette ciblee : {rates}")

    # ── AC-5 — ast.walk n'est pas un balayage ───────────────────────────
    def test_AC5_ast_walk_n_est_pas_un_balayage_de_disque(self):
        """L'erreur que j'ai faite : compter `ast.walk` faisait passer les
        balayeurs de 54 a 124 sur 194, et l'assiette devenait le corpus
        entier — un gain nul, et rien pour le signaler."""
        que_ast = ast.parse(
            'import ast\n'
            'def f(a):\n'
            '    return [n for n in ast.walk(a)]\n')
        self.assertEqual(
            AC._est_balayeur(que_ast), set(),
            '`ast.walk` est compte comme un balayage de disque : '
            "l'assiette va gonfler jusqu'au corpus entier sans que rien "
            'ne le dise')
        vrai = ast.parse('import os\n'
                         'def g(d):\n'
                         '    return list(os.walk(d))\n')
        self.assertTrue(
            AC._est_balayeur(vrai),
            'un vrai `os.walk` n est plus reconnu : le critere `B` est '
            'mort, et les garde-fous transverses sortent de l assiette')

    # ── AC-6 — le temoin ────────────────────────────────────────────────
    def test_AC6_l_assiette_n_est_ni_vide_ni_le_corpus_par_accident(self):
        tous = AC.modules_de_test(AC._ZONE_DEFAUT)
        self.assertTrue(tous, 'temoin mort : aucun module de test recense')
        retenus = AC.assiette([_PIPE])
        self.assertTrue(
            retenus, "l'assiette est VIDE pour un lot reel : l'outil ne "
                     'selectionne plus rien, donc il n atteste rien')
        self.assertLess(
            len(retenus), len(tous),
            "l'assiette vaut le corpus entier pour un lot peripherique : "
            'le critere ne separe plus rien')

    # ── AC-8 — un ORACLE qui n'est pas un `.py` entre dans l'assiette ───
    def test_AC8_un_fichier_non_python_touche_est_vu(self):
        """⚠️⚠️ TROU TROUVE EN SERVICE, 15/09. `fichiers_touches()` filtrait
        sur `.py` : un lot qui regenerait `reference_gel.json` -- un ORACLE
        -- ne declenchait donc PAS la sentinelle qui le lit. *L'outil etait
        aveugle a la seule categorie de fichier qui ne porte QUE des
        oracles.*

        Deux sens : le fichier doit ressortir de `fichiers_touches()` quand
        git le signale, ET l'assiette doit retenir le sceau qui le nomme.
        """
        oracle = 'direction_non_vie/tarification/reference_gel.json'
        self.assertTrue(
            (_RACINE / oracle).is_file(),
            f'temoin mort : {oracle} n existe plus, ce controle ne mesure '
            f'plus rien')
        #: ⚠️⚠️ ON APPELLE `fichiers_touches` AVEC UNE SORTIE GIT
        #: FABRIQUEE, au lieu de relire son code. Premiere redaction de ce
        #: controle : il verifiait (a) `assiette([oracle])` -- qui ne passe
        #: PAS par `fichiers_touches`, donc ne mesurait pas le filtre -- et
        #: (b) l'ABSENCE d'une ligne de code, que le plant a contournee en
        #: ecrivant `.py` autrement. **Il est reste VERT sur le plant.**
        #: *Un sceau qui lit du texte se contourne ; un sceau qui appelle la
        #: fonction, non.*
        rendus = AC.fichiers_touches(f' M {oracle}\n M core/plan_tarifaire.py\n')
        self.assertIn(
            oracle, rendus,
            f'`fichiers_touches` ecarte un fichier non-python : un lot qui '
            f'REGENERE un ORACLE ne declencherait pas la sentinelle qui le '
            f'lit. Rendu : {rendus}')
        self.assertIn('core/plan_tarifaire.py', rendus,
                      'temoin : les `.py` doivent evidemment passer aussi')
        #: et le SECOND SENS : une fois vu, il DOIT retenir la sentinelle
        gel = 'direction_non_vie/tarification/test_gel_livrables.py'
        retenus = AC.assiette([oracle])
        self.assertIn(
            gel, retenus,
            "la sentinelle du gel n'entre pas dans l'assiette d'un lot qui "
            "REGENERE sa reference")
        self.assertTrue(
            any(r.startswith('N') for r in retenus[gel]),
            f'elle y entre, mais pas par le NOM : raisons={retenus[gel]}')

    # ── AC-7 — une seule lecture de verdict dans ce depot ───────────────
    def test_AC7_le_verdict_n_est_pas_relu_ici_mais_importe(self):
        """`GATE-1` a coute assez cher pour qu'il n'existe qu'UNE lecture de
        verdict. Ce controle interdit qu'une seconde apparaisse ici."""
        source = (_RACINE / 'scripts' / 'assiette_ciblee.py').read_text(
            encoding='utf-8')
        arbre = ast.parse(source)
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.Constant)
                    and isinstance(noeud.value, str)):
                continue
            self.assertNotIn(
                'Ran ', noeud.value,
                "cet outil relit lui-meme le verdict au lieu de l'importer "
                'de `gate.py` : deux lectures divergeront au premier '
                'correctif, et `GATE-1` recommencera')
        importe = any(
            (isinstance(n, ast.Import) and any(a.name == 'gate'
                                               for a in n.names))
            or (isinstance(n, ast.ImportFrom) and n.module == 'gate')
            for n in ast.walk(arbre))
        self.assertTrue(
            importe,
            "l'outil n'importe plus `gate` : sa lecture de verdict et son "
            "environnement d'enfants ne viennent plus de la source unique")


if __name__ == '__main__':
    unittest.main(verbosity=2)
