# -*- coding: utf-8 -*-
"""UNE VALEUR ABSENTE NE VAUT PAS UN LITTERAL — LA CAUSE COMMUNE DU MODULE.

Le defaut central de la tarification n'est pas une erreur de calcul : c'est
une valeur qu'on n'a pas mesuree, remplacee par un nombre. Elle traverse
ensuite tout, parce qu'un nombre ne se distingue pas d'une mesure.

CE QUI A ETE MESURE LE 05/09/2026, sur la fixture `_portefeuille_auto` :

  1. `999` COMME RMSE. Le Tweedie ne publie PAS de `rmse_test` (la cle est
     ABSENTE de sa famille). A6 posait `met.get('rmse_test', 999)`. Sur la
     cible `prime_pure`, le Tweedie est le SEUL modele du catalogue : le
     commentaire signe publiait donc, sur le modele de PRODUCTION,
     << RMSE test : 999.00 >>. Et sur un catalogue peuple, ce 999 devenait le
     maximum qui normalise le critere pour tous les autres.

  2. UN RATIO QUI EXPLOSE AU LIEU DE REFUSER. `ratio_sur_apprentissage`
     faisait `gini_train / max(gini_test, 1e-6)`. Avec le Gamma mesure a
     **-0,0298**, le ratio valait **39 534,31** ; avec TabNet a -0,0201, il
     valait **-9 387,61**. Ce -9 387 devenait le `min_of` de la
     normalisation `1 - (r - min) / (max - min)` : TabNet recevait
     `s_stab = 1.0`, **la MEILLEURE note de stabilite du catalogue**, et tous
     les autres tombaient a ~0. TabNet se classait 4e ; mesure apres
     correction, il est 9e.

  3. UN GINI D'ENTRAINEMENT FABRIQUE, QUI NEUTRALISAIT SA PROPRE GARDE. A4
     posait `gini_train = gini_test * 1.10` quand la mesure manquait. Le
     ratio valait alors MECANIQUEMENT 1/1,10 = 0,909, donc >= 0,90, donc H1
     publiait << Pas d'overfitting >>. La branche `if ratio_of is None`,
     ecrite juste en dessous pour dire << NON MESURABLE >>, etait
     inatteignable des que `gini_test` existait.

  4. UN GINI DE REFERENCE D'ALLURE CREDIBLE. A5 posait `gini_glm_ref = 0.10`
     quand A3 manquait. Un chiffre plausible est plus dangereux qu'un zero :
     personne ne le remarque en relecture, et il decide le statut de H3.

  5. TROIS ZEROS DANS UN CLASSEUR SIGNE. Le Gamma et le Tweedie ne publient
     pas `deviance_nulle`, le Tweedie pas `pseudo_r2` : la feuille
     << 1-Synthese >> du classeur A3 affichait << GLM Tweedie -- Pseudo-R2 :
     0 >>, c'est-a-dire *le modele n'explique rien*, a chaque run normal.

  6. UNE GARDE QUI SE TESTAIT A TRAVERS SON PROPRE DEFAUT.
     `meilleur.get('gini_test', 0) is not None` est VRAI meme quand la cle
     manque.

Ce que cette sentinelle exige :
  AD-1   la primitive generale rend le MOT, jamais un nombre invente, et
         `gini_texte` / `gini_arrondi` n'en sont que des noms ;
  AD-2   un ratio ne se calcule pas sur un Gini de test <= 0 ;
  AD-3   **LE CONTROLE QUI DERIVE** : aucun site de la tarification ne lit
         une cle de mesure avec un defaut numerique -- et l'ensemble des cles
         se DERIVE des producteurs, il ne s'enumere pas ;
  AD-4   une valeur non mesuree SORT du score et le modele le DECLARE ;
  AD-5   une valeur non mesuree ne deplace ni le min ni le max de la
         normalisation, donc pas le score des autres ;
  AD-6   H1 d'A4 dit << non mesurable >>, jamais << pas d'overfitting >> ;
  AD-7   H3 d'A5 dit << non evaluable >> sans reference mesuree ;
  AD-8   le classeur SIGNE ecrit le mot, pas un zero ;
  AD-9   A6 refuse de prononcer un statut sur un Gini de production absent.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""
import ast
import glob
import io
import os
import pathlib
import sys
import unittest

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

from core.conformite_reglementaire import (
    NON_MESURE,
    gini_arrondi,
    gini_texte,
    mesure_arrondie,
    mesure_texte,
    ratio_sur_apprentissage,
)
from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison

# =============================================================================
#  AD-1, AD-2 — LE SOCLE
# =============================================================================

class TestPrimitiveGenerale(unittest.TestCase):

    def test_AD1_le_mot_remplace_toute_valeur_inexistante(self):
        for absente in (None, float('nan'), float('inf'), float('-inf')):
            self.assertEqual(mesure_texte(absente), NON_MESURE, repr(absente))
            self.assertEqual(mesure_arrondie(absente), NON_MESURE, repr(absente))

    def test_AD1b_une_vraie_mesure_reste_un_nombre(self):
        self.assertEqual(mesure_texte(0.26514, 4), '0.2651')
        self.assertEqual(mesure_arrondie(0.26514, 4), 0.2651)
        # ⚠️ ZERO EST UNE MESURE. Le confondre avec l'absence serait le meme
        # defaut dans l'autre sens : un modele qui ne discrimine pas doit
        # pouvoir le dire.
        self.assertEqual(mesure_texte(0.0, 4), '0.0000')
        self.assertEqual(mesure_arrondie(0.0, 4), 0.0)
        self.assertEqual(mesure_texte(-0.0298, 4), '-0.0298')

    def test_AD1c_gini_texte_et_gini_arrondi_ne_sont_QUE_des_noms(self):
        """Source unique : deux contrats identiques ne peuvent pas diverger
        s'il n'y en a qu'un."""
        for valeur in (None, float('nan'), 0.0, -0.0298, 0.2651, 1.75):
            self.assertEqual(gini_texte(valeur), mesure_texte(valeur), repr(valeur))
            self.assertEqual(gini_arrondi(valeur), mesure_arrondie(valeur),
                             repr(valeur))

    def test_AD2_un_ratio_ne_se_calcule_pas_sur_un_gini_de_test_negatif(self):
        """⚠️⚠️ MESURE : avec `max(gini_test, 1e-6)`, le Gamma a -0,0298
        rendait 39 534,31 et TabNet a -0,0201 rendait -9 387,61. Ces nombres
        devenaient les bornes de la normalisation de stabilite."""
        self.assertIsNone(ratio_sur_apprentissage(0.0395, -0.0298),
                          'un Gini de test negatif produit encore un ratio')
        self.assertIsNone(ratio_sur_apprentissage(0.0395, 0.0),
                          'un Gini de test nul produit encore un ratio')
        self.assertIsNone(ratio_sur_apprentissage(None, 0.20))
        self.assertIsNone(ratio_sur_apprentissage(0.20, None))
        self.assertIsNone(ratio_sur_apprentissage(float('nan'), 0.20))

    def test_AD2b_un_ratio_mesurable_reste_mesure_a_l_identique(self):
        """La correction ne doit PAS changer le ratio quand il existe."""
        self.assertAlmostEqual(ratio_sur_apprentissage(0.2100, 0.1912),
                               0.2100 / 0.1912, places=12)


# =============================================================================
#  AD-3 — LE CONTROLE QUI DERIVE
# =============================================================================

#: Les repertoires ou la regle s'applique. ⚠️ `audit_2026_08` en est exclu :
#: ce sont des scripts de PREUVE d'audit, pas du code de production.
_ZONES = ('direction_non_vie/tarification/**/*.py',)


def _fichiers_de_production():
    vus = set()
    for motif in _ZONES:
        for f in glob.glob(os.path.join(_RACINE, motif), recursive=True):
            chemin = f.replace('\\', '/')
            nom = pathlib.Path(chemin).name
            if ('__pycache__' in chemin or 'audit_2026_08' in chemin
                    or nom.startswith('test_')):
                continue
            vus.add(chemin)
    return sorted(vus)


def _arbres():
    for chemin in _fichiers_de_production():
        try:
            yield chemin, ast.parse(pathlib.Path(chemin).read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):                   # pragma: no cover
            continue


def _fonctions_pouvant_rendre_none(arbres):
    """Les fonctions dont un `return` vaut `None`, explicitement."""
    noms = set()
    for _, arbre in arbres:
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for sous in ast.walk(noeud):
                if isinstance(sous, ast.Return) and (
                        sous.value is None
                        or (isinstance(sous.value, ast.Constant)
                            and sous.value.value is None)):
                    noms.add(noeud.name)
                    break
    return noms


def _cles_que_les_producteurs_laissent_vides(arbres):
    """⚠️⚠️ IL DERIVE, IL N'ENUMERE PAS. Est << cle de mesure >> toute cle a
    laquelle un producteur de la tarification affecte, quelque part, soit le
    litteral `None`, soit le RESULTAT D'UNE FONCTION QUI PEUT RENDRE `None`.

    ⚠️ Le second cas est le principal, et l'oublier vide le controle : les
    agents n'ecrivent presque jamais `'gini': None`, ils ecrivent
    `'gini': self._calculer_gini(...)`. Une premiere version de ce controle ne
    regardait que le litteral et derivait ZERO cle -- elle serait restee verte
    en ne surveillant rien.

    Une liste tenue a la main aurait diverge le jour ou un agent publie une
    metrique nouvelle -- et l'assiette du controle se serait retrecie sans que
    personne le voie.
    """
    nullables = _fonctions_pouvant_rendre_none(arbres)

    def _source_nullable(noeud):
        if isinstance(noeud, ast.Constant) and noeud.value is None:
            return True
        if isinstance(noeud, ast.Call):
            nom = (noeud.func.id if isinstance(noeud.func, ast.Name)
                   else getattr(noeud.func, 'attr', None))
            return nom in nullables
        if isinstance(noeud, ast.IfExp):
            return _source_nullable(noeud.body) or _source_nullable(noeud.orelse)
        return False

    cles = set()
    for _, arbre in arbres:
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Dict):
                for cle, valeur in zip(noeud.keys, noeud.values):
                    if (isinstance(cle, ast.Constant)
                            and isinstance(cle.value, str)
                            and _source_nullable(valeur)):
                        cles.add(cle.value)
            elif isinstance(noeud, ast.Assign) and len(noeud.targets) == 1:
                cible = noeud.targets[0]
                if (isinstance(cible, ast.Subscript)
                        and isinstance(cible.slice, ast.Constant)
                        and isinstance(cible.slice.value, str)
                        and _source_nullable(noeud.value)):
                    cles.add(cible.slice.value)
    return cles


def _est_numerique(noeud):
    if isinstance(noeud, ast.Constant):
        return (isinstance(noeud.value, (int, float))
                and not isinstance(noeud.value, bool))
    return (isinstance(noeud, ast.UnaryOp)
            and isinstance(noeud.operand, ast.Constant)
            and isinstance(noeud.operand.value, (int, float)))


#: Les grandeurs dont l'absence FABRIQUE une mesure. Ce sont celles que les
#: agents publient comme resultat d'un calcul statistique -- pas les libelles
#: (`branche`, `note`, `erreur`), pour lesquels un defaut textuel est honnete.
#:
#: ⚠️⚠️ CE N'EST PLUS UN FILTRE : C'EST UN PLANCHER -- constat `EXCEL-1`,
#: 14/09/2026. Cette liste RESTREIGNAIT l'assiette derivee par une
#: intersection : `surveillees = {c for c in _MESURES if c in derivees}`.
#: Mesure du jour : le controle DERIVE **72** cles et n'en surveillait que
#: **6**. Les 66 autres -- dont `pvalue` et `ae_ratio` -- etaient derivees
#: puis JETEES, parce qu'aucune main ne les avait ajoutees ici.
#:
#: *C'est exactement le defaut que la docstring de
#: `_cles_que_les_producteurs_laissent_vides` dit eviter : << une liste
#: tenue a la main aurait diverge le jour ou un agent publie une metrique
#: nouvelle -- et l'assiette du controle se serait retrecie sans que
#: personne le voie >>. Elle s'etait retrecie a 6 sur 72.*
#:
#: ⚠️ ET LE CONTROLE NE GARDAIT QU'UN SEUL SENS. `test_AD3b` exige que
#: chaque cle d'ici soit derivee ; RIEN n'exigeait l'inverse, donc une cle
#: derivee absente d'ici sortait de l'assiette EN SILENCE. `test_AD3d`
#: ferme ce second sens.
#:
#: L'elargissement a l'assiette derivee entiere fait mordre **exactement
#: TROIS sites** -- et ce sont les trois que l'auditeur avait trouves a la
#: lecture (`tarif_excel.py:194`, `:221`, `:920`). *L'auditeur les a
#: trouves en lisant ; le garde les trouve en derivant, des qu'il cesse de
#: se retrecir a la main.*
_MESURES = ('gini', 'gini_test', 'gini_train', 'rmse_test', 'overfit_ratio',
            'cout_moyen_pred')


#: ⚠️⚠️ LES DEUX SEULES EXEMPTIONS DE `AD-3f`, ET ELLES SONT DECLAREES AVEC
#: LEUR RAISON. La derivation les attrape parce qu'un producteur les met a
#: `None` quelque part, mais ce ne sont PAS des grandeurs mesurees : un
#: LIBELLE absent se dit << non renseignee >>, un HORODATAGE absent se dit
#: << N/A >>, et leur imposer le mot des mesures appauvrirait le document.
#: *Une exemption declaree avec sa raison est saine ; c'est le
#: retrecissement SILENCIEUX qui ne l'est pas -- et c'est justement celui
#: que ce lot vient de fermer.*
_PAS_DES_MESURES = ('note', 'timestamp')

#: ⚠️ `_GARDES` RETIRE AVEC `AD-3e` — quatrieme piece de la meme depouille.
#: Il listait les fonctions par lesquelles une grandeur passe avant un
#: texte, et seul `_passe_par_un_garde` le lisait. `vulture` ne l'a PAS
#: signale : il flaire les fonctions mortes, pas les constantes mortes.
#: Releve AST : pose une fois, LU nulle part. *Le nettoyage d'un sceau
#: retire ne se confie pas a un outil -- il se mesure.*


#: ⚠️ TROIS AIDES RETIREES AVEC `AD-3e` : `_cle_derivee_lue`, `_FONCTIONS`
#: et `_passe_par_un_garde` ne servaient qu'a lui. Les laisser aurait ete
#: de la plomberie posee que rien n'alimente -- la forme exacte du constat
#: `socle/C2` -- et `vulture` l'a dit des le premier passage (0 -> 2).
#: *Un sceau qu'on retire emporte ses outils ; sinon le suivant croit
#: qu'ils servent.*


def assiette_surveillee(derivees) -> set:
    """L'assiette de `AD-3` — UNE definition, interrogeable par son sceau.

    ⚠️ Elle existe pour que `AD-3d` puisse VERIFIER l'assiette au lieu d'en
    recalculer une copie : une copie rendrait le controle tautologique, et
    c'est precisement la faute qu'il surveille. *Un controle qui recalcule
    ce qu'il verifie ne verifie que lui-meme.*

    Tout ce qui est DERIVE est surveille. `_MESURES` est un plancher
    (`AD-3b`), jamais un plafond.
    """
    return set(derivees)


class TestControleQuiDerive(unittest.TestCase):

    def test_AD3_aucun_defaut_numerique_sur_une_cle_de_mesure(self):
        """⚠️⚠️ ZERO EXEMPTION, ET C'EST LE POINT. Un controle a liste
        d'exceptions grandit ; celui-ci ne le peut pas. Mesure du
        05/09/2026 : 101 sites portaient un tel defaut avant ce lot."""
        arbres = list(_arbres())
        self.assertGreater(len(arbres), 10,
                           "aucun fichier de production trouve : le controle "
                           "ne mesure rien")
        derivees = _cles_que_les_producteurs_laissent_vides(arbres)
        #: ⚠️⚠️ L'ASSIETTE EST CE QUI EST DERIVE, POINT. Elle valait
        #: `{c for c in _MESURES if c in derivees}` : 6 cles sur 72, et le
        #: rétrécissement venait d'une liste tenue a la main. `_MESURES`
        #: reste un PLANCHER, verifie par `AD-3b` ; il ne plafonne plus.
        surveillees = assiette_surveillee(derivees)
        self.assertTrue(surveillees, 'aucune cle de mesure derivee')
        self.assertTrue(
            set(_MESURES) <= surveillees,
            'le plancher `_MESURES` n est plus inclus dans l assiette '
            f'derivee : {sorted(set(_MESURES) - surveillees)}')

        fautes = []
        for chemin, arbre in arbres:
            lignes = pathlib.Path(chemin).read_text(encoding='utf-8').splitlines()
            for noeud in ast.walk(arbre):
                if not (isinstance(noeud, ast.Call)
                        and isinstance(noeud.func, ast.Attribute)
                        and noeud.func.attr == 'get' and len(noeud.args) == 2):
                    continue
                cle, defaut = noeud.args
                if (isinstance(cle, ast.Constant) and cle.value in surveillees
                        and _est_numerique(defaut)):
                    fautes.append(
                        f'{pathlib.Path(chemin).name}:{noeud.lineno} '
                        f'{cle.value} = {ast.unparse(defaut)} | '
                        f'{lignes[noeud.lineno - 1].strip()[:80]}')
        self.assertEqual(fautes, [], 'une valeur non mesuree recevrait un '
                                     'nombre :\n  ' + '\n  '.join(fautes))

    def test_AD3b_les_cles_surveillees_sont_bien_DERIVEES_des_producteurs(self):
        """⚠️ Sans ceci, `_MESURES` deviendrait une liste tenue a la main : le
        jour ou un agent cesse de publier `None` sur une cle, elle sortirait
        de l'assiette EN SILENCE et le controle resterait vert."""
        derivees = _cles_que_les_producteurs_laissent_vides(list(_arbres()))
        manquantes = [c for c in _MESURES if c not in derivees]
        self.assertEqual(manquantes, [],
                         'ces grandeurs ne sont plus publiees comme pouvant '
                         'valoir None par aucun producteur : '
                         f'{manquantes} -- le controle AD-3 ne les surveille '
                         'donc plus. Relire le lot avec ce changement.')

    def test_AD3d_l_assiette_n_est_pas_RETRECIE_par_une_liste_a_la_main(self):
        """⚠️⚠️ LE SECOND SENS, ET IL MANQUAIT — constat `EXCEL-1`.

        `AD-3b` garde un seul sens : toute clé de `_MESURES` doit être
        dérivée. Rien ne gardait l'inverse, et c'est l'inverse qui a cédé :
        le contrôle DÉRIVAIT 72 clés et n'en surveillait que **6**, parce
        que l'assiette passait par `{c for c in _MESURES if c in derivees}`.
        Les 66 autres — dont `pvalue` et `ae_ratio` — sortaient EN SILENCE.

        *Une assiette qui se rétrécit sans que rien ne le dise est la forme
        la plus discrète du contrôle qui atteste sans surveiller.* Ce
        contrôle-ci exige que tout ce qui est dérivé soit surveillé.
        """
        arbres = list(_arbres())
        derivees = _cles_que_les_producteurs_laissent_vides(arbres)
        self.assertGreater(
            len(derivees), len(_MESURES),
            'la derivation ne trouve pas plus que le plancher : soit les '
            'producteurs ont change, soit la derivation est cassee')
        #: ⚠️ ON INTERROGE LA FONCTION QUE `AD-3` UTILISE, pas une copie
        #: de son calcul. Une premiere redaction de ce controle recalculait
        #: l'assiette ici (`surveillees = set(derivees)`) puis comparait
        #: `derivees - surveillees` : TAUTOLOGIQUE, toujours vide, incapable
        #: de mordre. *Le defaut que ce lot corrige, reproduit dans son
        #: propre correctif.*
        non_surveillees = sorted(derivees - assiette_surveillee(derivees))
        self.assertEqual(
            non_surveillees, [],
            f'{len(non_surveillees)} cle(s) DERIVEE(S) sortent de '
            f'l assiette sans que rien ne le dise : {non_surveillees[:12]}')

    #: ⚠️⚠️ UN SCEAU ENVISAGE, MESURE, ET **NON POSE** -- et le dire vaut
    #: mieux que de l'ecrire bancal. Constat `A4-1` : un `{x:.4f}` NU sur une
    #: grandeur qui peut valoir `None` LEVE, ou publie << nan >>. Le site
    #: nomme est corrige dans ce lot ; le GARDE GENERAL, lui, ne tient pas :
    #:
    #:   sans suivi de variable        -> **0** site trouve : aveugle, car
    #:                                    `rmse` est une variable locale
    #:   suivi dans tout le module     -> **64** sites : il relie un format a
    #:                                    n'importe quelle affectation du nom
    #:   suivi borne a la FONCTION     -> **54** sites : a peine mieux
    #:
    #: La cause est nette : le controle ne voit pas les gardes en AMONT
    #: (`if gini is not None:` quelques lignes plus haut), et les distinguer
    #: demande une ANALYSE DE FLOT -- une vraie architecture, pas un reglage.
    #: *Un sceau qui accuse cinquante-quatre sites corrects n'est pas un
    #: sceau : c'est du bruit que l'on apprend a ignorer, et le jour ou il
    #: dit vrai personne ne l'ecoute.*
    #: `AD-3f` ci-dessous, lui, tient : il juge un DEFAUT ECRIT, pas un flot.

    def test_AD3f_aucun_defaut_TEXTUEL_invente_sur_une_cle_de_mesure(self):
        """⚠️ Constat `A6-2`, elargi par derivation. `.get(cle, 'N/A')` a
        DEUX defauts : le repli n'est jamais lu quand la cle EXISTE et vaut
        `None` -- le depot le dit lui-meme dans `rapport_modeles_tarif` --
        et `'N/A'` n'est pas le mot de ce depot. Mesure du 14/09 : **sept**
        sites, dont cinq dans un rapport SIGNE, alors que le remede
        (`_valeur_ou_absente`) vivait a une ligne et n'etait applique qu'a
        UN site sur quatre."""
        arbres = list(_arbres())
        derivees = _cles_que_les_producteurs_laissent_vides(arbres)
        fautes = []
        for chemin, arbre in arbres:
            for noeud in ast.walk(arbre):
                if not (isinstance(noeud, ast.Call)
                        and isinstance(noeud.func, ast.Attribute)
                        and noeud.func.attr == 'get' and len(noeud.args) == 2
                        and isinstance(noeud.args[0], ast.Constant)
                        and noeud.args[0].value in derivees):
                    continue
                cle, defaut = noeud.args[0].value, noeud.args[1]
                if cle in _PAS_DES_MESURES:
                    continue          # exemption DECLAREE, avec sa raison
                if (isinstance(defaut, ast.Constant)
                        and isinstance(defaut.value, str) and defaut.value
                        and defaut.value != NON_MESURE):
                    fautes.append(f'{pathlib.Path(chemin).name}:'
                                  f'{noeud.lineno} .get({cle!r}, '
                                  f'{defaut.value!r})')
        self.assertEqual(
            fautes, [],
            'une grandeur qui peut valoir None recoit un repli TEXTUEL '
            'invente, et ce repli ne sera meme pas lu sur un `None` :\n  '
            + '\n  '.join(fautes))

    def test_AD3c_le_999_n_existe_plus_nulle_part(self):
        """Le littéral nomme, cherche au texte : il ne doit plus etre le
        repli d'une RMSE dans aucun agent."""
        for chemin in _fichiers_de_production():
            texte = pathlib.Path(chemin).read_text(encoding='utf-8')
            self.assertNotIn("rmse_test', 999", texte, chemin)
            self.assertNotIn('rmse_test", 999', texte, chemin)


# =============================================================================
#  AD-4, AD-5 — LE SCORE : UNE ASSIETTE REDUITE, ET DECLAREE
# =============================================================================

def _catalogue(**remplacements):
    """Trois modeles comparables, dont un modifiable par le test."""
    base = [
        {'modele': 'GLM_POISSON', 'famille': 'GLM', 'gini_test': 0.19,
         'rmse_test': 0.71, 'overfit_ratio': 0.97, 'interpretabilite': 1.0},
        {'modele': 'ML_GBM', 'famille': 'ML', 'gini_test': 0.13,
         'rmse_test': 0.74, 'overfit_ratio': 3.58, 'interpretabilite': 0.5},
        {'modele': 'ML_XGBOOST', 'famille': 'ML', 'gini_test': 0.10,
         'rmse_test': 0.74, 'overfit_ratio': 5.48, 'interpretabilite': 0.5},
    ]
    for i, modif in remplacements.items():
        base[int(i[1:])].update(modif)
    return base


def _scorer(catalogue):
    agent = AgentA6Comparaison.__new__(AgentA6Comparaison)
    poids = {'gini': 0.40, 'stabilite': 0.30, 'interpretabilite': 0.20,
             'rmse': 0.10}
    return agent._calculer_scores_multicriteres(catalogue, poids)


class TestScoreSurAssietteReduite(unittest.TestCase):

    def test_AD4_une_rmse_absente_sort_du_score_et_se_DECLARE(self):
        avec = _scorer(_catalogue())
        sans = _scorer(_catalogue(m0={'rmse_test': None}))
        self.assertEqual(avec[0]['criteres_non_mesures'], ())
        self.assertEqual(sans[0]['criteres_non_mesures'], ('rmse',),
                         "le modele ne declare pas ce qu'il n'a pas mesure")
        self.assertIsNone(sans[0]['score_rmse'])
        self.assertIsNotNone(sans[0]['score_global'])

    def test_AD5_une_absence_se_comporte_comme_une_ABSENCE(self):
        """⚠️⚠️ LE COEUR DU DEFAUT, ET J'AI D'ABORD ECRIT L'INVARIANT FAUX.

        Ma premiere version exigeait que le score des AUTRES ne bouge pas
        quand un ratio devient non mesure. C'est impossible et ce serait
        meme faux : la normalisation est un min-max, retirer une valeur de
        l'ensemble change legitimement l'etendue.

        Le bon invariant est celui-ci : un ratio NON MESURE doit produire
        exactement le meme effet qu'un modele ABSENT de ce critere -- ni plus
        (il ne borne rien), ni moins (il ne disparait pas du classement). Un
        litteral, lui, BORNE.
        """
        non_mesure = {m['modele']: m['score_stabilite']
                      for m in _scorer(_catalogue(m0={'overfit_ratio': None}))}
        absent = {m['modele']: m['score_stabilite']
                  for m in _scorer(_catalogue()[1:])}
        for nom in ('ML_GBM', 'ML_XGBOOST'):
            self.assertEqual(non_mesure[nom], absent[nom],
                             f"la stabilite de {nom} differe selon qu'un autre "
                             "modele a un ratio NON MESURE ou est ABSENT : "
                             "l'absence borne encore quelque chose")
        self.assertIsNone(non_mesure['GLM_POISSON'])
        self.assertIn('GLM_POISSON', non_mesure,
                      "le modele a disparu du classement au lieu d'y figurer "
                      'sans note de stabilite')

    def test_AD5c_un_litteral_ne_DEPLACE_PLUS_les_autres(self):
        """⚠️⚠️ CE TEST A CHANGE DE SENS LE 06/09/2026, ET C'EST LA PREUVE QUE
        `A6-2` EST FERME. Il prouvait l'INVERSE : que poser un litteral
        `overfit_ratio = 1.0` DEPLACAIT le score de stabilite des AUTRES
        modeles, parce que la note valait `1 - (r - min)/(max - min)` et que
        le litteral devenait le `min` du catalogue.

        La note est desormais une distance a 1 sur une echelle ABSOLUE : la
        stabilite d'un modele ne depend plus d'aucun autre. *Le danger que ce
        controle documentait n'existe plus ; il fige donc son absence.*

        ⚠️ ET LA RAISON POUR LAQUELLE `ratio_sur_apprentissage` REFUSE UN
        LITTERAL N'A PAS DISPARU -- elle a EMPIRE. Sous une distance a 1, un
        ratio fabrique a 1,0 est le score PARFAIT, par construction et sans
        condition. C'est le constat `A4-3`, corrige dans le meme lot.
        """
        avec_litteral = {m['modele']: m['score_stabilite']
                         for m in _scorer(_catalogue(m0={'overfit_ratio': 1.0}))}
        non_mesure = {m['modele']: m['score_stabilite']
                      for m in _scorer(_catalogue(m0={'overfit_ratio': None}))}
        for autre in ('ML_GBM', 'ML_XGBOOST'):
            with self.subTest(modele=autre):
                self.assertEqual(
                    avec_litteral[autre], non_mesure[autre],
                    f'le score de {autre} depend encore de ce qu un AUTRE '
                    f'modele porte comme ratio')
        # et le litteral vaut bien, pour CELUI qui le porte, le score parfait
        self.assertAlmostEqual(avec_litteral['GLM_POISSON'], 1.0, places=9,
                               msg='un ratio fabrique a 1,0 doit valoir le '
                                   'score PARFAIT : c est pourquoi A4 rend None')

    def test_AD5b_un_ratio_absurde_n_ECRASE_PLUS_la_normalisation(self):
        """⚠️⚠️ MEME RETOURNEMENT, avec le nombre REELLEMENT mesure : -9 387,61.

        Ce controle montrait ce que la normalisation relative faisait subir au
        catalogue : le fautif recevait la note PARFAITE et tous les autres
        s'effondraient sous 0,01. Mesure du 06/09 sur dix LoB : l'ecart de
        note entre `r = 1` et `r = 2` valait 0,08 sur un catalogue allant a
        13,06 contre 0,61 sur un catalogue allant a 2,60 -- sept fois moins,
        pour la meme stabilite.

        Sur une echelle absolue, un ratio absurde ne touche plus personne : il
        se note lui-meme a zero, et c'est tout.
        """
        sain = {m['modele']: m['score_stabilite'] for m in _scorer(_catalogue())}
        pollue = {m['modele']: m['score_stabilite']
                  for m in _scorer(_catalogue(m0={'overfit_ratio': -9387.61}))}
        for autre in ('ML_GBM', 'ML_XGBOOST'):
            with self.subTest(modele=autre):
                self.assertEqual(
                    sain[autre], pollue[autre],
                    f'la note de {autre} s effondre encore a cause du ratio '
                    f'absurde d un AUTRE modele')
        self.assertAlmostEqual(pollue['GLM_POISSON'], 0.0, places=9,
                               msg='un ratio absurde doit se noter lui-meme a '
                                   'zero')
        # ... et `ratio_sur_apprentissage` REFUSE toujours de le produire :
        # un non-sens se declare, il ne se borne pas.
        self.assertIsNone(ratio_sur_apprentissage(0.0094, -0.0201))

    def test_AD4b_le_facteur_de_reassiette_vaut_1_quand_rien_ne_manque(self):
        """⚠️ La renormalisation ne doit rien changer quand rien ne manque :
        le facteur vaut exactement 1,0. Sans ce test, le correctif pourrait
        deplacer un prix en croyant ne rien faire.

        ⚠️⚠️ L'ATTENDU NE RECOPIE PLUS AUCUNE FORMULE. Il codait `0.30 * 1.0`
        pour la stabilite -- vrai seulement tant que ce modele etait le
        MINIMUM du catalogue, donc dependant de la formule de `A6-2`. Il se
        derive desormais des notes PUBLIEES par l'agent : le controle porte
        sur le FACTEUR, et sur lui seul.
        """
        scores = _scorer(_catalogue())
        modele = scores[0]
        attendu = (0.40 * modele['score_gini']
                   + 0.30 * modele['score_stabilite']
                   + 0.20 * modele['score_interpretabilite']
                   + 0.10 * modele['score_rmse'])
        self.assertEqual(modele['criteres_non_mesures'], ())
        self.assertAlmostEqual(modele['score_global'], round(attendu, 4),
                               places=4)


# =============================================================================
#  AD-6, AD-7 — LES HYPOTHESES NE SE CONCLUENT PAS SANS MESURE
# =============================================================================

def _h1(modele):
    """L'hypothese H1 d'A4 sur un classement d'un seul modele.

    ⚠️ On appelle la VRAIE methode (`_valider_modele_ml`), pas une copie de sa
    logique : un controle qui recopie le calcul ne surveille que sa copie.
    """
    import numpy as np

    from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
    agent = AgentA4ML.__new__(AgentA4ML)
    zeros = np.zeros((4, 2))
    val = agent._valider_modele_ml([modele], {'psi': 0.05}, 100, 25, zeros,
                                   zeros, np.zeros(4))
    return val.get('h1_overfitting', {})


class TestHypothesesSansMesure(unittest.TestCase):

    def test_AD6_H1_dit_non_mesurable_jamais_pas_d_overfitting(self):
        """⚠️⚠️ `gini_train = gini_test * 1.10` donnait un ratio de 0,909,
        donc >= 0,90, donc << Pas d'overfitting >> -- sur un modele dont
        l'entrainement n'avait jamais ete mesure."""
        h1 = _h1({'modele': 'ML_GBM', 'gini_test': 0.13, 'gini_train': None,
                  'rmse_test': 0.74, 'overfit_ratio': None})
        self.assertEqual(h1.get('statut'), 'AMBRE', h1)
        self.assertIn('NON MESURABLE', h1.get('message', '').upper(), h1)
        self.assertNotIn("pas d'overfitting", h1.get('message', '').lower(), h1)

    def test_AD6b_H1_conclut_normalement_quand_les_DEUX_ginis_existent(self):
        """⚠️ LE NOMBRE EPINGLE A CHANGE D'ORIENTATION, PAS LA PROPRIETE --
        constat `A5-1`, 07/09/2026. H1 publiait `Gini(test)/Gini(train)` =
        0,950 ; il publie desormais `Gini(train)/Gini(test)` = 1,053, la
        RECIPROQUE, sur l'orientation du socle. **Le statut reste VERT sur
        les memes deux Ginis** : ce test prouve exactement ce qu'il prouvait.
        """
        h1 = _h1({'modele': 'ML_GBM', 'gini_test': 0.19, 'gini_train': 0.20,
                  'rmse_test': 0.74, 'overfit_ratio': 1.05})
        self.assertEqual(h1.get('statut'), 'VERT', h1)
        self.assertIn('1.053', h1.get('message', ''), h1)
        self.assertNotIn('0.950', h1.get('message', ''), h1)

    def test_AD6c_un_gini_d_entrainement_NEGATIF_ne_produit_plus_de_ratio(self):
        """`max(gini_train, 0.001)` bornait le denominateur : le ratio
        explosait au lieu de se declarer non mesurable."""
        h1 = _h1({'modele': 'ML_GBM', 'gini_test': 0.13, 'gini_train': -0.02,
                  'rmse_test': 0.74, 'overfit_ratio': None})
        self.assertEqual(h1.get('statut'), 'AMBRE', h1)
        self.assertIn('NON MESURABLE', h1.get('message', '').upper(), h1)

    def test_AD7_le_gini_de_reference_0_10_n_existe_plus(self):
        """⚠️ Un chiffre PLAUSIBLE est plus dangereux qu'un zero : personne ne
        le remarque en relecture, et il decidait le statut de H3."""
        chemin = os.path.join(_ICI, 'a5_deep_learning', 'agent.py')
        texte = pathlib.Path(chemin).read_text(encoding='utf-8')
        self.assertNotIn(".get('gini', 0.10)", texte,
                         'A5 fabrique encore un Gini GLM de reference')
        self.assertNotIn('gini_glm_ref = 0.10', texte)


# =============================================================================
#  AD-8, AD-9 — LES SURFACES SIGNEES
# =============================================================================

class TestSurfacesSignees(unittest.TestCase):

    def test_AD8_le_classeur_A3_ecrit_le_MOT_pas_un_zero(self):
        """⚠️⚠️ MESURE DU 05/09/2026 : sur un run NORMAL, la feuille
        << 1-Synthese >> publiait << GLM Tweedie -- Pseudo-R2 : 0 >> et deux
        << Deviance nulle : 0 >>. Le Gamma et le Tweedie ne publient pas ces
        metriques : le zero etait une affirmation que personne n'avait faite,
        dans le document que l'actuaire signe."""
        from openpyxl import load_workbook

        from direction_non_vie.tarification.services.tarif_excel import (
            export_excel_a3,
        )
        # Un resultat A3 fidele a la forme reelle : le Tweedie n'a NI
        # `deviance_nulle` NI `pseudo_r2`, le Gamma n'a pas `deviance_nulle`.
        resultat = {
            'success': True, 'statut_rag': 'AMBRE', 'sous_branche': 'auto',
            'metriques': {
                'poisson': {'gini': 0.1912, 'aic': 3421.61,
                            'deviance_nulle': 1990.87, 'pseudo_r2': 0.0396,
                            'nb_vars_retenues': 7},
                'gamma': {'gini': -0.0298, 'aic': 11816.09,
                          'pseudo_r2': 0.0079, 'nb_vars_retenues': 3},
                'tweedie': {'gini': 0.1901, 'aic': 14954.35,
                            'nb_vars_retenues': 5},
            },
        }
        octets = export_excel_a3(resultat)
        self.assertTrue(octets, "l'export n'a produit aucun classeur")
        feuille = load_workbook(io.BytesIO(octets), data_only=True).worksheets[0]
        publie = {}
        etiquette = None
        for ligne in feuille.iter_rows():
            for cellule in ligne:
                if isinstance(cellule.value, str) and '—' in str(cellule.value):
                    etiquette = cellule.value
                elif etiquette is not None and cellule.value is not None:
                    publie[etiquette] = cellule.value
                    etiquette = None
        for nom in ('GLM Gamma — Déviance nulle', 'GLM Tweedie — Déviance nulle',
                    'GLM Tweedie — Pseudo-R²'):
            self.assertIn(nom, publie, f'{nom} absent du classeur : le test ne '
                                       f'mesure rien. Vu : {sorted(publie)[:8]}')
            self.assertEqual(publie[nom], NON_MESURE,
                             f'{nom} publie {publie[nom]!r} alors que la '
                             'metrique n existe pas')
        # ... et ce qui EST mesure reste un nombre.
        self.assertEqual(publie['GLM Poisson — Pseudo-R²'], 0.0396)
        self.assertEqual(publie['GLM Gamma — Pseudo-R²'], 0.0079)

    def test_AD9_A6_refuse_un_statut_sur_un_gini_de_production_absent(self):
        """Le catalogue ecarte deja ces modeles ; si l'un passe quand meme, on
        le DIT au lieu de prononcer un statut sur une mesure inexistante."""
        agent = AgentA6Comparaison.__new__(AgentA6Comparaison)
        with self.assertRaises(ValueError) as capture:
            agent._calculer_statut_rag(
                {'modele': 'X', 'score_global': 0.9, 'gini_test': None},
                {}, [], 'production', 'Actuaire', None)
        self.assertIn('Gini', str(capture.exception))

    def test_AD9b_le_commentaire_ne_publie_plus_999(self):
        chemin = os.path.join(_ICI, 'a6_comparaison', 'agent.py')
        texte = pathlib.Path(chemin).read_text(encoding='utf-8')
        self.assertNotIn("mp['rmse_test']:.2f", texte,
                         'le commentaire signe formate encore la RMSE sans '
                         'savoir dire quand elle manque')
        self.assertIn("mesure_texte(mp['rmse_test']", texte)


if __name__ == '__main__':
    unittest.main(verbosity=2)
