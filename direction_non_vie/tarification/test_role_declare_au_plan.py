r"""
==============================================================================
  UN ROLE DECLARE AU PLAN NE SE REDECIDE PAS PAR UN LITTERAL
==============================================================================

⚠️⚠️ LA CLASSE, PAS LES TROIS CAS. Le plan tarifaire est le document
OPPOSABLE : il declare quelle colonne porte l'exposition, la frequence, le
cout. Quand le code renomme ces roles par un litteral -- un defaut de
signature, un `df['exposition']` en dur -- il pose une SECONDE declaration,
et c'est elle qui gagne. Le plan devient decoratif.

  Trois exemplaires mesures le 12/09/2026, et ils ne viennent pas du meme
  endroit : deux etaient dans les rapports d'audit, le troisieme non.

⚠️ CE QUI SEPARE UN DEFAUT VIVANT D'UN DEFAUT INERTE, ET CELA SE MESURE.
Un defaut de signature est INERTE si tout appelant de production passe la
valeur ; il est VIVANT si aucun ne la passe -- le litteral gouverne alors
la production. Mesure du 12/09 : **4 vivants sur 15**. `col_frequence` est
passe depuis `plan.cible_frequence` par le pipeline ; `col_exposition` ne
l'etait par personne, sur 310 fichiers de production balayes.

⚠️⚠️ ET LE PLUS DANGEREUX N'EST PAS LE PLANTAGE. Sur le plan
`auto_fr_reel` (colonne `Exposure`), le site Poisson etait GARDE : offset
pose a ZERO, un `warning`, et le run continue. Le site Gamma ne l'etait
pas et levait `KeyError`. *Le plantage etait un accident d'incoherence,
pas un filet.* Si le Gamma avait ete garde comme le Poisson, le defaut
aurait ete une tarification fausse entierement MUETTE -- agregat identique
a 0,0000 %, et des rapports individuels de x0,431 a x22,18.

  C'est pourquoi ce sceau ne verifie pas << le run ne plante plus >> : il
  verifie que **la grandeur publiee est MESUREE et non FABRIQUEE**.

⚠️ LA COINCIDENCE QUI MASQUAIT TOUT. Sur des donnees saines, le chemin qui
mesure et le chemin qui invente rendent TOUS DEUX 100,0 : l'egalite des
valeurs cachait l'inegalite des comportements. Il a fallu ABIMER la donnee
-- 600 lignes sur 6 000 a exposition 3,5 -- pour que le defaut se voie :
100,0 d'un cote, 90,0 de l'autre. *Un controle sur donnees saines n'aurait
jamais mordu.*
==============================================================================
"""
from __future__ import annotations

import ast
import logging
import os
import pathlib
import subprocess
import sys
import unittest
import warnings

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

#: Les litteraux qui NOMMENT un role que le plan declare.
_LITTERAUX_DE_ROLE = {'exposition', 'nb_sinistres', 'cout_total',
                      'cout_sinistres'}


def _fichiers_de_production() -> list[str]:
    """Ce que git publie, hors tests -- l'assiette du controle de classe."""
    try:
        sortie = subprocess.run(
            ['git', 'ls-files'], cwd=str(_RACINE), capture_output=True,
            text=True, encoding='utf-8', errors='replace', timeout=120,
            check=False).stdout
        rels = [f for f in sortie.split('\n') if f.endswith('.py')
                and not f.split('/')[-1].startswith('test_')]
        if rels:
            return [f for f in rels if (_RACINE / f).is_file()]
    except (OSError, subprocess.SubprocessError):
        pass
    return [str(p.relative_to(_RACINE)).replace('\\', '/')
            for p in _RACINE.rglob('*.py')
            if p.is_file() and not p.name.startswith('test_')
            and '.git' not in p.parts]


def _defauts_de_signature(arbre: ast.AST) -> list[tuple]:
    """(fonction, parametre, litteral, ligne) pour un defaut nommant un role.

    ⚠️⚠️ SEULES LES FONCTIONS QUI RECOIVENT LE PLAN SONT CONCERNEES, et ce
    n'est pas une commodite : *une fonction qui n'a pas le plan ne peut pas
    en deriver quoi que ce soit.* L'obligation porte la ou le document
    opposable est disponible -- la porte d'entree des agents.

    Mesure du 12/09 qui a impose ce critere : une lecture plus large
    accusait six fabriques de modeles d'`a4_ml` portant
    `col_cible='nb_sinistres'`. Aucune ne recoit le plan, et cinq d'entre
    elles sont appelees POSITIONNELLEMENT (`_fabriquer_estimateur_nu(nom,
    col_cible)`) -- un relevé limite aux mots-cles les voyait vivantes.
    *Un controle trop large accuse la ou il n'y a rien a corriger.*
    """
    out = []
    for n in ast.walk(arbre):
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        a = n.args
        pos = list(a.posonlyargs) + list(a.args)
        noms = {x.arg for x in pos} | {x.arg for x in a.kwonlyargs}
        if 'plan' not in noms:
            continue
        paires = list(zip(pos[len(pos) - len(a.defaults):], a.defaults))
        paires += [(x, d) for x, d in zip(a.kwonlyargs, a.kw_defaults)
                   if d is not None]
        for arg, d in paires:
            if (isinstance(d, ast.Constant) and isinstance(d.value, str)
                    and d.value in _LITTERAUX_DE_ROLE):
                out.append((n.name, arg.arg, d.value, n.lineno))
    return out


def _mots_cles_passes(arbre: ast.AST) -> set:
    """(fonction appelee, mot-cle) reellement passes par ce fichier.

    ⚠️⚠️ LE COUPLE, PAS LE MOT-CLE SEUL, ET C'EST UN PLANT QUI L'A IMPOSE.
    Une premiere redaction collectait les mots-cles NUS. Consequence
    mesuree le 12/09 : une methode neuve portant `col_cout='cout_total'`,
    que personne n'appelait, etait declaree INERTE parce qu'un AUTRE site
    du depot passait `col_cout=` a une autre fonction. *Le nom d'un
    parametre n'appartient pas a une fonction : l'exoneration voyageait
    d'une fonction a l'autre.* Le plant `P5` est reste vert, et c'est ainsi
    que le trou s'est vu.
    """
    out = set()
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Call):
            continue
        if isinstance(n.func, ast.Name):
            appele = n.func.id
        elif isinstance(n.func, ast.Attribute):
            appele = n.func.attr
        else:
            continue
        for kw in n.keywords:
            if kw.arg:
                out.add((appele, kw.arg))
    return out


def _derives_du_plan(arbre: ast.AST) -> set:
    """(fonction, parametre) que la fonction REDERIVE depuis le plan.

    ⚠️⚠️ SANS CETTE LECTURE, LE CONTROLE ACCUSE LE CODE CORRIGE. Le
    correctif ne retire pas le defaut de signature : il le REND INOPERANT
    en reaffectant le parametre depuis `plan.exposition` des l'entree de la
    fonction. Un relevé qui ne verrait que la FORME du defaut rougirait sur
    la reparation elle-meme. *La question n'est pas << y a-t-il un litteral
    en signature >> mais << le plan gouverne-t-il ce parametre >>.*
    """
    out = set()
    for n in ast.walk(arbre):
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for x in ast.walk(n):
            if not isinstance(x, ast.Assign):
                continue
            source = ast.unparse(x.value)
            if 'plan' not in source:
                continue
            for t in x.targets:
                if isinstance(t, ast.Name):
                    out.add((n.name, t.id))
    return out


def _releve_classe() -> tuple:
    """(defauts, mots-cles passes, couples derives du plan) sur l'assiette."""
    defauts, passes, derives = [], set(), set()
    for rel in _fichiers_de_production():
        try:
            arbre = ast.parse((_RACINE / rel).read_text(encoding='utf-8',
                                                        errors='replace'))
        except (SyntaxError, OSError):
            continue
        for fonc, arg, val, li in _defauts_de_signature(arbre):
            defauts.append((rel, li, fonc, arg, val))
        passes |= _mots_cles_passes(arbre)
        #: ⚠️⚠️ LA DERIVATION EST ATTACHEE A SON FICHIER. Sans le chemin, la
        #: reparation d'A4 exonerait A3 : le couple `('run',
        #: 'col_exposition')` existe des qu'UN agent sur quatre derive du
        #: plan. Mesure du 12/09 : le plant `P1`, qui retire la derivation
        #: d'A3, restait VERT grace a A4, A5 et A6.
        derives |= {(rel, f, a) for f, a in _derives_du_plan(arbre)}
    return defauts, passes, derives


def _gouvernes_par_un_litteral(defauts, passes, derives) -> list:
    """Les defauts qu'AUCUN appelant n'ecrase et que le plan ne regit pas.

    ⚠️ Deux echappatoires LEGITIMES, et une seule suffit :
      · un appelant de production passe la valeur -- le defaut est inerte ;
      · la fonction rederive le parametre depuis le plan -- il est inoperant.
    """
    return [(rel, li, fonc, arg, val)
            for rel, li, fonc, arg, val in defauts
            if (fonc, arg) not in passes and (rel, fonc, arg) not in derives]


def _jeu(n=700, expo_abimee=0):
    """Un portefeuille SYNTHETIQUE, deterministe. Aucune donnee reelle."""
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(20260912)
    expo = np.clip(rng.beta(1.2, 1.6, n), 0.02, 1.0)
    bonus = np.clip(rng.normal(60, 18, n), 50, 200)
    drivage = rng.integers(18, 85, n)
    vehpower = rng.integers(4, 15, n)
    lam = 0.09 * np.exp(0.012 * (bonus - 60) - 0.008 * (drivage - 45))
    nb = rng.poisson(lam * expo)
    cout = np.where(nb > 0, rng.gamma(2.0, 900.0, n) * nb, 0.0)
    if expo_abimee:
        expo = expo.copy()
        expo[:expo_abimee] = 3.5
    return pd.DataFrame({
        'IDpol': np.arange(1, n + 1), 'date_echeance': '2023-01-01',
        'Exposure': expo, 'ClaimNb': nb, 'ClaimAmountTotal': cout,
        'DrivAge': drivage, 'VehPower': vehpower,
        'VehAge': rng.integers(0, 25, n), 'BonusMalus': bonus,
        'Density': np.exp(rng.normal(5.5, 1.4, n)),
        'Area': rng.choice(list('ABCDEF'), n),
        'VehGas': rng.choice(['Regular', 'Diesel'], n),
        'VehBrand': rng.choice(['B1', 'B2', 'B3'], n),
        'Region': rng.choice(['R11', 'R21', 'R22'], n)})


def _plan_nommant(colonne: str, dossier):
    """Le plan `auto_fr_reel`, avec la SEULE ligne d'exposition changee."""
    from core.plan_tarifaire import PlanTarifaire
    source = (_RACINE / 'plans' / 'auto_fr_reel.yaml').read_text(
        encoding='utf-8')
    texte = source.replace('exposition: Exposure',
                           f'exposition: {colonne}', 1)
    cible = pathlib.Path(dossier) / f'plan_{colonne}.yaml'
    cible.write_text(texte, encoding='utf-8')
    return PlanTarifaire.depuis_yaml(str(cible))


def _qualite_a1(colonne, dossier, expo_abimee=0):
    """Le rapport qualite d'A1, pour un plan qui nomme SA colonne."""
    from direction_non_vie.tarification.a1_ingestion.agent import (
        AgentA1Ingestion,
    )
    df = _jeu(expo_abimee=expo_abimee)
    if colonne != 'Exposure':
        df = df.rename(columns={'Exposure': colonne})
    agent = AgentA1Ingestion(base_path=str(pathlib.Path(dossier) / 'data'),
                             audit_path=str(pathlib.Path(dossier) / 'audit'),
                             verbose=False)
    r1 = agent.run(branche='non_vie', sous_branche='auto', dataframe=df,
                   plan=_plan_nommant(colonne, dossier))
    return r1, (r1.get('qualite') or {})


class TestRoleDeclareAuPlan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import tempfile
        cls._tmp = tempfile.mkdtemp(prefix='role_plan_')
        cls._silence = logging.getLogger()
        cls._niveau = cls._silence.level
        cls._silence.setLevel(logging.CRITICAL)
        warnings.filterwarnings('ignore')

    @classmethod
    def tearDownClass(cls):
        cls._silence.setLevel(cls._niveau)

    def test_RDP1_LE_RELEVE_distingue_un_defaut_VIVANT_d_un_defaut_INERTE(
            self):
        """⚠️⚠️ CE CONTROLE PASSE AVANT LES AUTRES. Un relevé qui ne verrait
        aucun defaut de signature rendrait `RDP-2` vert sur un depot qui les
        porte tous : *il attesterait sans surveiller*. Il recoit donc les
        deux sens sur une source synthetique."""
        arbre = ast.parse(
            "def agent(df, plan=None, col_exposition='exposition',\n"
            "          col_a='autre'):\n"
            "    return df\n"
            "def fabrique(nom, col_exposition='exposition'):\n"
            "    return nom\n"
            "def appelant(df):\n"
            "    return agent(df, col_frequence='nb_sinistres')\n")
        defauts = _defauts_de_signature(arbre)
        noms = {(f, a, v) for f, a, v, _ in defauts}
        self.assertIn(
            ('agent', 'col_exposition', 'exposition'), noms,
            "un defaut de signature qui NOMME un role du plan n'est pas vu")
        #: ⚠️ SECOND SENS : un defaut qui ne nomme pas un role est laisse.
        self.assertNotIn(
            'col_a', {a for _, a, _, _ in defauts},
            "un defaut sans rapport avec un role du plan est accuse : le "
            "controle accuse au lieu de surveiller")
        #: ⚠️⚠️ TROISIEME SENS : une fonction qui NE RECOIT PAS le plan ne
        #: peut rien en deriver -- l'accuser reviendrait a exiger
        #: l'impossible. C'est ce qui innocente les six fabriques d'`a4_ml`.
        self.assertNotIn(
            'fabrique', {f for f, _, _, _ in defauts},
            "une fonction sans `plan` est accusee : elle n'a aucun moyen de "
            "deriver le role, le controle exige l'impossible")
        passes = _mots_cles_passes(arbre)
        self.assertIn(('agent', 'col_frequence'), passes,
                      "un mot-cle reellement passe n'est pas releve")
        self.assertNotIn(('agent', 'col_exposition'), passes,
                         "un mot-cle JAMAIS passe est compte comme passe : "
                         "tout defaut vivant serait declare inerte")
        #: ⚠️⚠️ ET LE COUPLE TIENT LA FONCTION. Un mot-cle passe a UNE
        #: fonction ne doit pas exonerer une AUTRE fonction du meme nom de
        #: parametre -- c'est le trou que le plant `P5` a revele.
        self.assertNotIn(
            ('autre_fonction', 'col_frequence'), passes,
            "un mot-cle passe a une fonction exonere une autre fonction : "
            "l'exoneration voyage d'une fonction a l'autre")
        print(f"    RDP-1 releve : {len(defauts)} defaut(s) vu(s), "
              f"{len(passes)} mot(s)-cle(s) passe(s), les deux sens tenus")

    def test_RDP2_AUCUN_defaut_de_signature_VIVANT_ne_nomme_un_role_du_plan(
            self):
        """⚠️⚠️ LE SCEAU DE CLASSE. Un defaut qu'AUCUN appelant de production
        n'ecrase gouverne la production. L'assiette est le depot suivi
        entier, pas les quatre agents corriges aujourd'hui : *surveiller
        l'endroit qu'on vient de nettoyer n'est pas surveiller*."""
        defauts, passes, derives = _releve_classe()
        self.assertGreater(
            len(defauts), 4,
            "le relevé ne trouve presque aucun defaut de signature : "
            "l'assiette s'est videe, ce controle n'atteste plus rien")
        self.assertGreaterEqual(
            len(derives), 4,
            f"seulement {len(derives)} parametre(s) sont rederives depuis le "
            f"plan : la lecture des derivations est muette, et tout defaut "
            f"corrige serait alors accuse a tort")
        fautifs = _gouvernes_par_un_litteral(defauts, passes, derives)
        self.assertEqual(
            fautifs, [],
            f"{len(fautifs)} defaut(s) de signature nomment un role que le "
            f"plan declare, sans qu'aucun appelant ne les ecrase ni que la "
            f"fonction les rederive du plan : le litteral gouverne la "
            f"production. {fautifs[:4]}")
        print(f"    RDP-2 SCEAU : 0 role gouverne par un litteral sur "
              f"{len(defauts)} defaut(s) releve(s), {len(derives)} "
              f"derivation(s) du plan")

    def test_RDP3_A1_MESURE_l_exposition_au_lieu_de_la_CERTIFIER(self):
        """⚠️⚠️ LE COEUR, ET IL NE SE VOIT QUE SUR DONNEE ABIMEE. Sur donnees
        saines les deux chemins rendent 100,0 : la coincidence masque tout.
        On abime donc 200 lignes sur 700 -- exposition 3,5, impossible pour
        un contrat annuel -- et un chemin qui MESURE doit descendre sous
        100, tandis qu'un chemin qui INVENTE y reste."""
        for colonne in ('Exposure', 'exposition'):
            with self.subTest(colonne=colonne):
                _, q = _qualite_a1(colonne, self._tmp, expo_abimee=200)
                pct = q.get('expo_ok_pct')
                self.assertIsNotNone(
                    pct, f"`expo_ok_pct` absent pour la colonne {colonne!r}")
                self.assertLess(
                    pct, 100.0,
                    f"colonne {colonne!r} : 200 expositions sur 700 valent "
                    f"3,5 -- impossible -- et le taux publie reste "
                    f"{pct}. Une exposition qu'on n'a pas su lire est "
                    f"certifiee conforme.")
        print("    RDP-3 SCEAU : le taux publie est MESURE sous les deux "
              "noms de colonne")

    def test_RDP4_A1_rend_le_MEME_verdict_quel_que_soit_le_NOM_de_la_colonne(
            self):
        """⚠️ Memes donnees, meme plan, seul le NOM change : toute difference
        est alors imputable au nom, a rien d'autre."""
        _, a = _qualite_a1('Exposure', self._tmp, expo_abimee=200)
        _, b = _qualite_a1('exposition', self._tmp, expo_abimee=200)
        self.assertEqual(
            a.get('expo_ok_pct'), b.get('expo_ok_pct'),
            f"le taux d'exposition depend du NOM de la colonne : "
            f"{a.get('expo_ok_pct')} contre {b.get('expo_ok_pct')}")
        self.assertEqual(
            (a.get('aberrants') or {}).get('exposition_nulle_ou_negative'),
            (b.get('aberrants') or {}).get('exposition_nulle_ou_negative'),
            "l'aberration `exposition <= 0` n'est cherchee que sous un nom")
        print(f"    RDP-4 A1 identique sous les deux noms : "
              f"{a.get('expo_ok_pct')}")

    def test_RDP6_une_exposition_ABSENTE_est_DECLAREE_et_jamais_certifiee(
            self):
        """⚠️⚠️ LA MOITIE MUETTE, ET C'EST UN PLANT QUI A MONTRE QU'ELLE
        N'ETAIT PAS COUVERTE. Les autres controles renomment la colonne des
        DEUX cotes : elle est donc toujours presente, et la branche
        << colonne absente >> n'etait jamais empruntee. *Une violation
        plantee HORS de l'assiette reste verte* -- le plant `P3`, qui
        republiait un 100,0 fabrique, n'a rien fait rougir.

        Ici le plan declare une colonne que le fichier NE PORTE PAS. Le
        taux publie doit alors etre ABSENT, avec son motif : publier 100,0
        certifierait une exposition que personne n'a lue."""
        from direction_non_vie.tarification.a1_ingestion.agent import (
            AgentA1Ingestion,
        )
        df = _jeu()
        df = df.rename(columns={'Exposure': 'duree_contrat'})
        plan = _plan_nommant('Exposure', self._tmp)   # declare ce qui manque
        agent = AgentA1Ingestion(
            base_path=str(pathlib.Path(self._tmp) / 'data'),
            audit_path=str(pathlib.Path(self._tmp) / 'audit'), verbose=False)
        q = (agent.run(branche='non_vie', sous_branche='auto', dataframe=df,
                       plan=plan).get('qualite') or {})
        self.assertIsNone(
            q.get('expo_ok_pct'),
            f"le plan declare `Exposure`, le fichier ne la porte pas, et le "
            f"taux publie vaut {q.get('expo_ok_pct')} : une exposition "
            f"jamais lue est certifiee conforme -- << non mesure = VERT >>.")
        self.assertTrue(
            q.get('expo_non_mesuree_motif'),
            "l'absence est rendue SANS MOTIF : elle redevient muette, et un "
            "lecteur ne peut pas savoir pourquoi le taux manque")
        print(f"    RDP-6 SCEAU : exposition absente -> taux ABSENT et motif "
              f"publie ({str(q.get('expo_non_mesuree_motif'))[:38]}...)")

    def test_RDP5_A2_valide_l_exposition_DECLAREE_et_non_une_colonne_devinee(
            self):
        """⚠️⚠️ `_valider_sortie` cherchait `'exposition'` en dur et comparait
        a `1`, alors que son JUMEAU `_traiter_exposition`, dans le meme
        fichier, lisait deja `plan.exposition` et `borne_exposition(plan)`.
        Et `_calculer_statut_rag` LIT ce champ : un nom de colonne plafonnait
        le statut d'A2 a AMBRE sur des donnees saines."""
        from core.qualite_donnees import preambule_qualite
        from direction_non_vie.tarification.a2_preprocessing.agent import (
            AgentA2Preprocessing,
        )
        vus = {}
        for colonne in ('Exposure', 'exposition'):
            r1, _ = _qualite_a1(colonne, self._tmp)
            plan = _plan_nommant(colonne, self._tmp)
            rq = preambule_qualite(r1.get('dataframe'), plan,
                                   horodatage='2026-09-12T00:00:00')
            r2 = AgentA2Preprocessing(verbose=False).run(
                result_a1={**r1, 'dataframe': rq.dataframe_propre}, plan=plan)
            #: ⚠️ Le rapport d'A2 vit sous `r2['rapport']`, pas au premier
            #: niveau : lire au mauvais etage rend `None` partout, et le
            #: controle passerait pour vert des deux cotes.
            tr = ((r2.get('rapport') or {}).get('transformations') or {})
            val = tr.get('validation') or {}
            vus[colonne] = val.get('exposition_valide')
        self.assertEqual(
            vus['Exposure'], vus['exposition'],
            f"`exposition_valide` depend du NOM de la colonne : {vus}. "
            f"`_calculer_statut_rag` en fait un plafond AMBRE.")
        self.assertIs(
            vus['Exposure'], True,
            f"des donnees SAINES sont declarees invalides : {vus}")
        print(f"    RDP-5 SCEAU : A2 valide l'exposition declaree, "
              f"{vus['Exposure']} sous les deux noms")


if __name__ == '__main__':
    unittest.main(verbosity=2)
