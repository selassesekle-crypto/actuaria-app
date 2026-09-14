"""AR-1..AR-5 — UN FACTEUR TARIFAIRE NE SE LIT PAS SUR L'HORLOGE.

Constat `A2-2` du 2e audit de tarification, reproduit au site le
14/09/2026 et fermé par ce lot.

    `_calculer_indicateurs_derives` posait `_annee_ref = datetime.now().year`.
    Un correctif antérieur avait remplacé un 2024 FIGÉ — faux d'un an de
    plus chaque année — par l'année d'EXÉCUTION, c'est-à-dire une année
    QUI BOUGE. *Ni l'une ni l'autre n'est la référence DÉCLARÉE.*

Ce n'est pas cosmétique : `plans/mrh.yaml` déclare `age_logement` (l.63)
et `logement_ancien` (l.65) sous la clé `facteurs:`. Mesuré deux fois,
sur deux tirages indépendants de 3 000 logements :

    ==================  auditeur 11/09  ce dépôt 14/09
    age_logement        100,00 %        100,00 %       décalé de +1 an
    logement_ancien     1,17 % (35)     1,13 % (34)    basculent 0 -> 1
    cohorte             1976            1976

*Deux tirages, la même cohorte : ce n'est pas du bruit.* Un GLM réajusté
le 1er janvier sur un portefeuille INCHANGÉ rend un autre tarif.

⚠️⚠️ CE SCEAU MESURE UN COMPORTEMENT, JAMAIS UN TEXTE. `AR-1` et `AR-2`
font avancer l'horloge et comparent les colonnes produites ; ils ne
cherchent nulle part la chaîne `annee_reference` dans une source. Un
correctif qui renommerait la variable sans changer le comportement les
laisserait verts — et c'est voulu : ce n'est pas le nom qui coûte.

⚠️ `AR-2` PORTE LE SECOND SENS, et il est le plus important des cinq :
déclarer l'année ne doit PAS figer en douce le comportement de ceux qui
ne la déclarent pas. Sans `annee_reference`, l'horloge reste, à
l'identique — seule sa SOURCE devient dite. Sans ce contrôle, un
correctif « prudent » qui figerait une année par défaut passerait pour
une fermeture alors qu'il déplacerait le tarif de tout le monde.

⚠️ `AR-5` MESURE L'ASSIETTE DU SCEAU LUI-MÊME. `AR-1` ne coûte un euro
que parce que le plan déclare ces deux colonnes comme FACTEURS. Le jour
où `mrh.yaml` cesserait de le faire, `AR-1` resterait vert en ne
surveillant plus rien : `AR-5` tombe alors, et dit pourquoi.
"""
import ast
import datetime as _dt
import os
import pathlib
import sys
import unittest

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../')))

import yaml

from direction_non_vie.tarification.a2_preprocessing import agent as _a2mod
from direction_non_vie.tarification.test_plan_invariants import (
    MRH,
    _a2,
    portefeuille_mrh,
)

_RACINE = pathlib.Path(__file__).resolve().parent.parent.parent
_DERIVEES_DE_MILLESIME = ('age_logement', 'logement_ancien')


class _Horloge:
    """Un `datetime` dont `now()` rend l'année demandée, et rien d'autre.

    ⚠️ ON NE TOUCHE PAS À L'HORLOGE DE LA MACHINE : on remplace l'objet
    `datetime` DANS LE MODULE mesuré, le temps de l'appel, et on le
    remet dans un `finally`.
    """

    def __init__(self, annee):
        self.annee = annee

    def now(self, *a, **k):
        #: ⚠️ AVEC FUSEAU (`DTZ001`). Le site mesuré lit `.year` d'un
        #: `datetime.now()` NAÏF : le fuseau ne change donc pas ce qu'on
        #: mesure, et une date de test sans fuseau est précisément la
        #: forme que la propreté du dépôt refuse.
        return _dt.datetime(self.annee, 6, 15, 12, 0, 0,
                            tzinfo=_dt.timezone.utc)

    def __getattr__(self, nom):
        return getattr(_dt.datetime, nom)


def _derive(df, annee_horloge, annee_declaree=None):
    """Les colonnes produites par A2, sous une horloge choisie."""
    a2 = (_a2(annee_reference=annee_declaree) if annee_declaree is not None
          else _a2())
    vrai = _a2mod.datetime
    try:
        _a2mod.datetime = _Horloge(annee_horloge)
        return a2.fit(df, MRH).transform(df), a2._annee_reference_utilisee
    finally:
        _a2mod.datetime = vrai


class AR1_AnneeDeclareeFigeLaDerivee(unittest.TestCase):
    """AR-1 — année DÉCLARÉE ⇒ la dérivée ne bouge pas d'un 1er janvier."""

    def test_AR1_les_deux_facteurs_sont_stables_quand_l_horloge_avance(self):
        df = portefeuille_mrh(n=3000, seed=3)
        a, _ = _derive(df, 2026, annee_declaree=2026)
        b, _ = _derive(df, 2027, annee_declaree=2026)
        for col in _DERIVEES_DE_MILLESIME:
            bougent = int((a[col] != b[col]).sum())
            self.assertEqual(
                bougent, 0,
                f"`{col}` bouge sur {bougent} contrat(s) alors que l'annee de "
                f"reference est DECLAREE : la derivee suit encore l'horloge, "
                f"et le meme portefeuille se tarife autrement le 1er janvier.")


class AR2_SansDeclarationRienNeBouge(unittest.TestCase):
    """AR-2 — le SECOND SENS : sans déclaration, l'horloge reste."""

    def test_AR2_sans_declaration_le_comportement_est_celui_de_l_horloge(self):
        df = portefeuille_mrh(n=1200, seed=7)
        millesime = df['annee_construction']
        for annee in (2026, 2027):
            out, source = _derive(df, annee)
            attendu = annee - millesime
            self.assertTrue(
                bool((out['age_logement'] == attendu).all()),
                f"sans `annee_reference`, `age_logement` doit valoir "
                f"{annee} - annee_construction A L'IDENTIQUE : figer une "
                f"annee par defaut deplacerait le tarif de tous les "
                f"appelants qui n'ont rien demande.")
            self.assertTrue(
                bool((out['logement_ancien']
                      == (attendu > 50).astype(int)).all()),
                "sans `annee_reference`, `logement_ancien` doit suivre "
                "`age_logement > 50` a l'identique.")
            self.assertIsNotNone(
                source,
                "l'annee retenue n'est pas publiee : une derivee qui depend "
                "de l'horloge et ne le DIT pas est le defaut d'origine.")
            self.assertIn(
                'NON', source['source'],
                f"la source publiee doit dire que l'annee n'est PAS "
                f"declaree ; elle dit : {source['source']!r}")


class AR3_LaSourceVoyageJusquALaRacine(unittest.TestCase):
    """AR-3 — publiée à la RACINE, là où A6 et les services regardent."""

    def test_AR3_run_publie_l_annee_a_la_racine_de_son_resultat(self):
        import logging
        import warnings

        from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
        df = portefeuille_mrh(n=400, seed=5)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            precedent = logging.root.manager.disable
            logging.disable(logging.CRITICAL)
            try:
                r1 = AgentA1Ingestion(audit_path='/tmp', verbose=False).run(
                    dataframe=df, branche='non_vie', sous_branche='mrh')
                r2 = _a2(annee_reference=2019).run(r1, plan=MRH)
            finally:
                logging.disable(precedent)
        self.assertIn(
            'annee_reference_derivees', r2,
            "la cle est absente de la RACINE du resultat d'A2. Elle peut "
            "tres bien vivre dans `rapport` : A6 et les services lisent la "
            "racine, et ce qui n'atteint aucun livrable n'existe pas "
            "(lecon `A1-1` de ce depot).")
        publiee = r2['annee_reference_derivees']
        self.assertIsNotNone(
            publiee, "la cle est a la racine mais vaut None sur un dossier "
                     "qui a bien derive `age_logement`.")
        self.assertEqual(
            publiee['annee'], 2019,
            f"l'annee publiee ({publiee['annee']}) n'est pas celle que "
            f"l'appelant a declaree (2019) : le document dirait une annee "
            f"et le facteur en utiliserait une autre.")
        self.assertIn('appelant', publiee['source'])


class AR4_AucuneAutreDeriveeNeLitLHorloge(unittest.TestCase):
    """AR-4 — l'ASSIETTE : qui d'autre dérive une colonne d'un `now()` ?"""

    def test_AR4_aucun_agent_ne_derive_une_colonne_produite_d_un_now(self):
        fautifs = []
        for nom in ('a1_ingestion', 'a2_preprocessing', 'a3_glm', 'a4_ml',
                    'a5_deep_learning', 'a6_comparaison'):
            p = pathlib.Path(__file__).parent / nom / 'agent.py'
            arbre = ast.parse(p.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                #: une AFFECTATION de colonne : `out[...] = ...` / `df[...]`
                if not isinstance(noeud, ast.Assign):
                    continue
                colonnes = [c for c in noeud.targets
                            if isinstance(c, ast.Subscript)]
                if not colonnes:
                    continue
                source = ast.unparse(noeud.value)
                #: ⚠️ ON MESURE L'APPEL, PAS LE MOT. `datetime.now()` dans un
                #: commentaire ou une docstring n'est pas une lecture.
                lit = any(isinstance(x, ast.Call)
                          and ast.unparse(x.func).endswith(
                              ('datetime.now', 'date.today', 'time.time'))
                          for x in ast.walk(noeud.value))
                if lit:
                    fautifs.append(f"{nom}/agent.py:{noeud.lineno} "
                                   f"{ast.unparse(noeud.targets[0])} = "
                                   f"{source[:60]}")
        self.assertEqual(
            fautifs, [],
            "une colonne de donnees est derivee DIRECTEMENT d'une lecture "
            "d'horloge. C'est le defaut `A2-2` a un autre site : si un plan "
            "declare cette colonne comme facteur, le meme portefeuille se "
            "tarife autrement demain.\n  " + "\n  ".join(fautifs))


class AR5_LAssietteDuSceauEstReelle(unittest.TestCase):
    """AR-5 — `AR-1` ne coûte un euro que si le plan le déclare FACTEUR."""

    def test_AR5_mrh_declare_bien_les_deux_colonnes_comme_facteurs(self):
        chemin = _RACINE / 'plans' / 'mrh.yaml'
        self.assertTrue(
            chemin.exists(),
            f"`{chemin}` est introuvable : l'assiette d'`AR-1` est vide, il "
            f"attesterait sans rien surveiller.")
        plan = yaml.safe_load(chemin.read_text(encoding='utf-8'))
        noms = {f['nom'] for f in (plan.get('facteurs') or [])}
        absents = [c for c in _DERIVEES_DE_MILLESIME if c not in noms]
        self.assertEqual(
            absents, [],
            f"`mrh.yaml` ne declare plus {absents} comme FACTEUR(S). `AR-1` "
            f"resterait vert en ne surveillant plus un euro : soit le plan a "
            f"change et ce sceau doit etre reecrit, soit la declaration a ete "
            f"perdue. Les deux se disent, aucun ne se tait.")


if __name__ == '__main__':
    # ⚠️ LE BLOC EN FIN DE FICHIER, DERRIERE TOUTES LES DEFINITIONS.
    # `unittest.main()` ne collecte que ce qui est defini AU MOMENT ou il
    # s'execute : place plus haut, il rendrait `OK` en taisant les classes
    # qui le suivent (constat `COLLECTE-1`, sceau `GD-1..GD-4`).
    unittest.main(verbosity=2)
