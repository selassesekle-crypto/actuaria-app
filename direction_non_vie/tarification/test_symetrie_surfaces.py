r"""
==============================================================================
  UN FAIT PUBLIE SUR UNE SURFACE SIGNEE L'EST SUR SES JUMELLES
==============================================================================

⚠️⚠️ LA CAUSE COMMUNE DES TROIS AUDITS DU 12/09/2026. Trois auditeurs
independants ont converge sur le meme mecanisme : *un correctif atterrit sur
UNE surface signee et pas sur sa jumelle*. Le fait est calcule, il est teste,
et il n'atteint qu'un des trois documents que l'actuaire signe.

  Les trois surfaces sont `rapport_modeles_tarif` (HTML + Word),
  `rapport_equipe_tarif` (HTML + Word) et `tarif_excel`. Elles lisent le
  MEME `result_a6`. Une cle lue par une seule d'entre elles est, par
  defaut, un fait qui manque aux deux autres.

⚠️ L'ORIGINE EST LA SONDE `s54_symetrie` DU TROISIEME AUDITEUR, et sa
structure est reprise telle quelle : les trois fabriques, la table
d'exceptions motivees, le relevé par AST. Ce qui est renforce ici l'a ete
pour une raison MESUREE, jamais par gout.

  TROIS MESURES ONT MONTRE QU'ELLE ACCUSAIT, ET CHACUNE SUR UNE CLE
  DIFFERENTE (12/09/2026, sur cet arbre) :

    1. `modele` -- lue sur `(result_a6 or {}).get('modele_production')`,
       donc cle de SECOND niveau. Son vrai parent `modele_production` est,
       lui, publie par les TROIS surfaces. La sonde comparait deux niveaux.
    2. `commentaire` -- lue par `rapport_modeles_tarif` sous
       `for r in [result_a6, result_a4, result_a3]: r.get('commentaire')`.
       Manquee parce que `r` n'etait pas dans la liste FERMEE des noms
       porteurs. *Un ensemble ferme de noms exacts est un relevé PAR
       SYMBOLE deguise en AST.*
    3. `success` -- lue par `rapport_equipe_tarif` sous
       `for agent, r in results.items()`, meme cause.

  Sur 10 solitaires annoncees, SEPT sont reelles. Les trois autres etaient
  des accusations. *Un controle trop etroit n'est pas prudent : il accuse.*

⚠️⚠️ ET LA LIMITE QUI RESTE EST ECRITE, AVEC LE SENS DE SON ERREUR. Une
boucle sur un dictionnaire d'agents recu en PARAMETRE (`results.items()`)
n'est pas resoluble sans analyse inter-procedurale. Le relevé SOUS-compte
donc les lecteurs : il peut declarer solitaire une cle qui ne l'est pas.
C'est pourquoi aucune cle n'entre dans la dette sans avoir ete verifiee au
site, et pourquoi `success` figure dans les EXCEPTIONS et non dans la dette.

⚠️ DEUX TABLES, ET LES CONFONDRE SERAIT LE DEFAUT.
  · `_EXCEPTIONS` -- l'asymetrie est LEGITIME, la raison est ecrite ;
  · `_DETTE_GELEE` -- l'asymetrie est un TROU, mesure, non encore arbitre.
    Elle ne peut que decroitre, et aucune cle neuve ne peut s'y ajouter.
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

_SERVICES = 'direction_non_vie/tarification/services/'
_FABRIQUES = {
    'modeles (HTML+Word)': _SERVICES + 'rapport_modeles_tarif.py',
    'equipe (HTML+Word)': _SERVICES + 'rapport_equipe_tarif.py',
    'excel (A6+equipe)': _SERVICES + 'tarif_excel.py',
}

#: Les noms qui designent un resultat A6 a la RACINE d'une expression.
_RACINES_PORTEUSES = {'r6', 'result_a6', 'res6', 'a6', 'resultat_a6', '_r6'}

#: ── TABLE 1 : L'ASYMETRIE EST LEGITIME, ET VOICI POURQUOI ────────────────
#:
#: ⚠️⚠️ TROIS ENTREES DE LA TABLE RECUE ONT ETE RETIREES, ET C'EST UNE
#: ERREUR DE CATEGORIE, PAS UN ASSOUPLISSEMENT. Mesure du 12/09/2026 :
#: `excel_bytes` n'est jamais une cle de `result_a6` -- c'est une cle du
#: dictionnaire de SORTIE (`out['excel_bytes'] = export_excel_a6(...)`,
#: `rapport_modeles_tarif` l.3624/3682/3687/3696) ; `graphiques` et
#: `graphiques_validation` sont des PANIERS de figures des agents A3 a A5,
#: nommes dans le catalogue (`('a3', 'graphiques')`), jamais lus sur un
#: `result_a6`. Exempter dans CETTE table des cles qui n'y entrent pas
#: n'exempte rien : cela laisse une ligne qui, le jour ou le nom
#: reapparait pour de bon, passe sans que personne ne l'ait decide.
_EXCEPTIONS = {
    'audit_id': "identifiant d'execution, porte par l'en-tete de chaque "
                "format",
    'fiche_decision': "objet de travail, rendu par un onglet dedie",
    'classement': "le tableau du classement a un rendu propre a chaque "
                  "format",
    'audit_trail': "la piste d'audit a son propre bloc dans les deux "
                   "rapports",
    #: ⚠️ AJOUTEE LE 12/09/2026, ET LA RAISON EST MESUREE. `success` n'est
    #: pas un fait publie : c'est le garde d'entree de chaque fabrique.
    #: `tarif_excel` le lit sur les SIX agents (l.88, 355, 563, 690, 1132,
    #: 1329) et `rapport_equipe_tarif` sur la boucle generique d'agents
    #: (l.199). Aucune des trois ne l'imprime.
    'success': "drapeau technique de reussite du run, lu comme garde "
               "d'entree par les trois fabriques, jamais publie",
}

#: ── TABLE 2 : L'ASYMETRIE EST UN TROU, MESURE, NON ARBITRE ───────────────
#:
#: ⚠️⚠️ CHACUNE A ETE VERIFIEE AU SITE PAR UN RELEVE VOLONTAIREMENT LARGE --
#: au TEXTE, sur les trois fichiers entiers, sans restriction de porteur.
#: Ce relevé SUR-compte par construction : il voit jusqu'aux mots dans les
#: commentaires. *Un zero rendu par un relevé qui sur-compte est decisif.*
#: Mesure du 12/09/2026 : zero occurrence, par n'importe quel chemin, dans
#: les deux surfaces qui ne la portent pas.
#: ⚠️⚠️ SEPT CLES LE 12/09, DEUX LE 13/09 -- ET C'EST LE SCEAU LUI-MEME QUI
#: A EXIGE LA MISE A JOUR. `SY-4` dit qu'une cle qui cesse d'etre solitaire
#: sort de cette table DANS LE MEME COMMIT. Les lots L8 a L11 ont publie
#: cinq faits sans que la constante bouge : la gate complete du 13/09 a
#: rougi dessus, nommement, sur les cinq. *Un garde-fou qui ne constate pas
#: la reparation mais l'EXIGE poste par poste vaut mieux qu'un compte tenu
#: a la main -- et il a mordu sur MON oubli, a travers quatre commits.*
#:
#:     anti_selection_a3 · reserve_gini_a3      -> L8  `9bc30b3`
#:     arbitrage_contestable                    -> L9  `d517c85`
#:     controle_effet                           -> L10 `2cd4112`
#:     sensibilite_profils                      -> L11 `2b9304c`
#:
#: ⚠️ LES DEUX QUI RESTENT NE SONT PAS UN OUBLI : elles sont ISOLEES PAR
#: ARBITRAGE du 12/09, et leur raison est ecrite.
#:   · `stabilite_rang` -- mesure optionnelle, 62,1 s par tirage, aucun
#:     producteur en production ;
#:   · `publication_reglementaire` -- seule sa moitie `non_produit` a ete
#:     publiee sur les deux rapports ; la moitie `possede` duplique ce que
#:     le rapport modeles porte deja. *La cle reste donc en dette, et c'est
#:     exact : elle est encore solitaire sur l'Excel.*
_DETTE_GELEE = {
    'publication_reglementaire': 'excel (A6+equipe)',
    'stabilite_rang': 'modeles (HTML+Word)',
}


def _designe_porteur(n: ast.AST, noms: set) -> bool:
    """L'expression DESIGNE un resultat A6 -- sans traverser un acces.

    ⚠️⚠️ ET CETTE RESTRICTION EST LE COEUR. Ma premiere redaction propageait
    la liaison des que la source MENTIONNAIT un porteur, et testait
    l'appartenance par SOUS-CHAINE. Mesure du 12/09 : l'assiette passait de
    21/27/20 cles a 61/138/123 -- `a6` matchait dans `result_a6`, puis dans
    tout ce que la boule de neige ramassait, et `prod = result_a6.get(...)`
    faisait de `prod` un porteur, ce qui ramenait la confusion de niveaux
    par la porte de derriere. *C'est la forme MIROIR du defaut traque ici :
    une assiette trop LARGE ne surveille pas mieux, elle accuse plus.*
    """
    if isinstance(n, ast.Name):
        return n.id in noms
    if isinstance(n, ast.BoolOp):
        return any(_designe_porteur(v, noms) for v in n.values)
    if isinstance(n, ast.IfExp):
        return (_designe_porteur(n.body, noms)
                or _designe_porteur(n.orelse, noms))
    if isinstance(n, (ast.List, ast.Tuple, ast.Set)):
        return any(_designe_porteur(e, noms) for e in n.elts)
    #: un `.get()`, un `[...]`, un appel : on est DANS le resultat, plus lui
    return False


def _corps_direct(portee: ast.AST) -> list:
    """Les noeuds de CETTE portee, sans descendre dans les portees filles."""
    vus = []

    def _desc(n):
        for f in ast.iter_child_nodes(n):
            if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef, ast.Lambda)):
                continue
            vus.append(f)
            _desc(f)
    _desc(portee)
    return vus


def _porteurs(portee: ast.AST) -> set:
    """Les noms qui portent un resultat A6 DANS CETTE PORTEE.

    ⚠️⚠️ LA PORTEE EST LA CORRECTION LA PLUS CHERE DE CE LOT, ET ELLE VIENT
    D'UN FAUX POSITIF QUE J'AI PRODUIT MOI-MEME. Ma redaction precedente
    resolvait les porteurs a l'echelle du MODULE. Or `r` est un nom local
    banal : `rapport_modeles_tarif` le lie a un `result_a6` dans une
    fonction (l.2167) et au resultat de `tarif.tarifer(contrat)` dans une
    autre (l.973). Module-wide, les deux se confondaient, et le controle
    annoncait `prime_pure`, `prime_commerciale_ht`, `prime_ttc` comme des
    cles solitaires de `result_a6` -- CINQ fausses accusations, sur les
    grandeurs les plus lourdes du dossier. *J'ai reproduit, en miroir,
    exactement le defaut que je reprochais a la sonde recue.*

    ⚠️ ET LA LIAISON EST EXIGEANTE : un nom n'est porteur que si TOUTES ses
    liaisons dans la portee designent un porteur. Une seule liaison vers
    autre chose suffit a le disqualifier -- l'ambiguite ne se tranche pas
    en faveur de l'accusation.
    """
    noms = set(_RACINES_PORTEUSES)
    if isinstance(portee, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = portee.args
        for a in (list(args.posonlyargs) + list(args.args)
                  + list(args.kwonlyargs)):
            if a.arg in _RACINES_PORTEUSES:
                noms.add(a.arg)
    corps = _corps_direct(portee)
    liaisons = {}
    for n in corps:
        source = cibles = None
        if isinstance(n, ast.Assign):
            source, cibles = n.value, n.targets
        elif isinstance(n, (ast.For, ast.AsyncFor)):
            source, cibles = n.iter, [n.target]
        if source is None:
            continue
        for c in cibles:
            for sous in ast.walk(c):
                if isinstance(sous, ast.Name):
                    liaisons.setdefault(sous.id, []).append(source)
    for _ in range(4):                      # la liaison peut se chainer
        avant = len(noms)
        for nom, sources in liaisons.items():
            if nom in noms:
                continue
            if all(_designe_porteur(s, noms) for s in sources):
                noms.add(nom)
        if len(noms) == avant:
            break
    #: ⚠️⚠️ UN NOM DERIVE relie AUSSI a autre chose n'est plus un porteur --
    #: mais une RACINE DECLAREE le reste toujours. Mesure du 12/09 : sans
    #: cette reserve, `r6 = results.get('a6') or {}` disqualifiait `r6`
    #: lui-meme, et `rapport_equipe_tarif` rendait ZERO cle. *Un relevé qui
    #: rend zero n'est pas prudent : il ne surveille plus rien.*
    return {n for n in noms
            if n in _RACINES_PORTEUSES
            or n not in liaisons
            or all(_designe_porteur(s, noms) for s in liaisons[n])}


def _est_direct(recu: ast.AST, porteurs: set) -> bool:
    """Le receveur EST un porteur, et non un acces DANS un porteur.

    ⚠️⚠️ MESURE PAR AST, JAMAIS AU TEXTE. Une lecture au texte coupant sur
    le premier << or >> rend DIRECT sur
    `(result_a6 or {}).get('modele_production') or {}` -- le << or >> est
    DEDANS les parentheses. Mesure du 12/09 : la version au texte disait
    l'exact contraire de la verite sur cette expression.
    """
    n = recu
    while True:
        if isinstance(n, ast.BoolOp) and n.values:
            n = n.values[0]
        elif isinstance(n, ast.IfExp):
            n = n.body
        else:
            break
    return isinstance(n, ast.Name) and n.id in porteurs


def _cles_lues(chemin: pathlib.Path) -> set:
    """Les cles de PREMIER niveau d'un resultat A6 lues par ce fichier.

    ⚠️ Le relevé se fait PORTEE PAR PORTEE : module, puis chaque fonction.
    """
    arbre = ast.parse(chemin.read_text(encoding='utf-8', errors='replace'))
    portees = [arbre] + [n for n in ast.walk(arbre)
                         if isinstance(n, (ast.FunctionDef,
                                           ast.AsyncFunctionDef))]
    out = set()
    for portee in portees:
        porteurs = _porteurs(portee)
        for n in _corps_direct(portee):
            cle = recu = None
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'get' and n.args
                    and isinstance(n.args[0], ast.Constant)
                    and isinstance(n.args[0].value, str)):
                cle, recu = n.args[0].value, n.func.value
            elif (isinstance(n, ast.Subscript)
                  and isinstance(n.slice, ast.Constant)
                  and isinstance(n.slice.value, str)):
                cle, recu = n.slice.value, n.value
            if cle is not None and _est_direct(recu, porteurs):
                out.add(cle)
    return out


def _par_fabrique() -> dict:
    return {nom: _cles_lues(_RACINE / rel)
            for nom, rel in _FABRIQUES.items()
            if (_RACINE / rel).is_file()}


def _absente_ailleurs(cle: str, porteuse: str) -> bool:
    """La cle est-elle absente des DEUX autres fabriques, par TOUT chemin ?

    ⚠️⚠️ LA SECONDE LECTURE, ET ELLE EST INDEPENDANTE DE LA PREMIERE. Le
    relevé par AST propose ; ce relevé-ci dispose. Il cherche le nom dans le
    TEXTE ENTIER des deux autres fichiers, sans aucune notion de porteur --
    il SUR-compte donc par construction : il voit jusqu'aux mots en
    commentaire. *Un zero rendu par un relevé qui sur-compte est decisif ;
    une occurrence suffit a retirer l'accusation.*

    Cette double lecture est ce qui protege des erreurs des DEUX mecanismes
    a la fois : les cinq fausses accusations du 12/09 (`prime_pure` et ses
    voisines) auraient ete retirees ici meme si la portee n'avait pas ete
    corrigee.
    """
    for nom, rel in _FABRIQUES.items():
        if nom == porteuse:
            continue
        p = _RACINE / rel
        if not p.is_file():
            continue
        if cle in p.read_text(encoding='utf-8', errors='replace'):
            return False
    return True


def _solitaires(confirmees: bool = True) -> list:
    par = _par_fabrique()
    toutes = set().union(*par.values()) if par else set()
    trouves = []
    for cle in sorted(toutes):
        porteuses = [n for n, s in par.items() if cle in s]
        if len(porteuses) != 1 or cle in _EXCEPTIONS:
            continue
        if confirmees and not _absente_ailleurs(cle, porteuses[0]):
            continue
        trouves.append((cle, porteuses[0]))
    return trouves


class TestSymetrieDesSurfacesSignees(unittest.TestCase):

    def test_SY1_LE_RELEVE_reconnait_un_porteur_LIE_et_pas_seulement_nomme(
            self):
        """⚠️⚠️ CE CONTROLE PASSE AVANT LES AUTRES, ET C'EST LE MEME MOTIF
        QUE POUR TOUT DETECTEUR : un relevé qui ne verrait aucun porteur
        rendrait ZERO cle partout, donc ZERO solitaire, donc VERT sur un
        depot entierement asymetrique. *Il attesterait sans surveiller.*"""
        arbre = ast.parse(
            "def porte(result_a6, result_a3):\n"
            "    for r in [result_a6, result_a3]:\n"
            "        x = r.get('lue_par_boucle')\n"
            "    secondaire = result_a6\n"
            "    y = secondaire.get('lue_par_alias')\n"
            "    prod = (result_a6 or {}).get('parent') or {}\n"
            "    z = prod.get('imbriquee')\n"
            "    return x, y, z\n"
            "\n"
            "def ne_porte_pas(contrat, tarif):\n"
            "    r = tarif.tarifer(contrat)\n"
            "    return r.get('prime_pure')\n")
        fonctions = {n.name: n for n in ast.walk(arbre)
                     if isinstance(n, ast.FunctionDef)}

        porteurs = _porteurs(fonctions['porte'])
        self.assertIn('r', porteurs, "un nom lie par une BOUCLE dont la "
                                     "source porte un result_a6 est porteur")
        self.assertIn('secondaire', porteurs, "un nom lie par AFFECTATION "
                                              "est porteur")
        lues = set()
        for n in _corps_direct(fonctions['porte']):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'get' and n.args
                    and _est_direct(n.func.value, porteurs)):
                lues.add(n.args[0].value)
        self.assertIn('lue_par_boucle', lues)
        self.assertIn('lue_par_alias', lues)
        #: ⚠️ SECOND SENS : une cle IMBRIQUEE n'est PAS une cle de premier
        #: niveau. C'est ce qui a innocente `modele`.
        self.assertNotIn('imbriquee', lues,
                         "une cle lue DANS un sous-dictionnaire est comptee "
                         "comme cle de result_a6 : deux niveaux confondus")

        #: ⚠️⚠️ TROISIEME SENS, ET C'EST LE FAUX POSITIF QUE J'AI PRODUIT LE
        #: 12/09. Le meme nom `r` porte un tarif ici et un `result_a6` dans
        #: la fonction d'a cote. Sans PORTEE, `prime_pure` etait annoncee
        #: comme une cle solitaire de `result_a6` -- une accusation sur la
        #: grandeur la plus lourde du dossier.
        autres = _porteurs(fonctions['ne_porte_pas'])
        self.assertNotIn(
            'r', autres,
            "`r = tarif.tarifer(contrat)` fait de `r` un porteur : la "
            "resolution ignore la PORTEE et confond deux variables locales")
        print(f"    SY-1 releve : {len(lues)} cle(s) directes, l'imbriquee "
              f"ecartee, la portee tenue")

    def test_SY2_les_trois_fabriques_sont_LUES_et_l_assiette_n_est_pas_vide(
            self):
        """⚠️ L'ASSIETTE SE MESURE AVANT DE CONCLURE. Un fichier renomme ou
        deplace viderait le relevé en silence, et tout serait vert."""
        par = _par_fabrique()
        self.assertEqual(
            sorted(par), sorted(_FABRIQUES),
            f"une fabrique n'a pas ete lue : {sorted(set(_FABRIQUES) - set(par))}")
        for nom, cles in par.items():
            with self.subTest(fabrique=nom):
                self.assertGreaterEqual(
                    len(cles), 10,
                    f"{nom} ne rend que {len(cles)} cle(s) : le relevé ne "
                    f"voit plus ce qu'il lisait, l'assiette s'est videe")
        print("    SY-2 assiette : " + ' · '.join(
            f"{n.split(' ')[0]} {len(c)}" for n, c in sorted(par.items())))

    def test_SY3_AUCUNE_asymetrie_NOUVELLE_entre_surfaces_signees(self):
        """⚠️⚠️ LE SCEAU. Toute cle solitaire qui n'est ni une exception
        motivee ni une dette deja mesuree est un fait qui vient de manquer a
        deux documents signes."""
        trouves = dict(_solitaires())
        neuves = {c: ou for c, ou in trouves.items() if c not in _DETTE_GELEE}
        self.assertEqual(
            neuves, {},
            f"{len(neuves)} fait(s) publie(s) par UNE SEULE surface signee, "
            f"hors exception et hors dette mesuree : {neuves}")
        print(f"    SY-3 SCEAU : 0 asymetrie nouvelle sur "
              f"{len(_EXCEPTIONS)} exception(s) motivee(s)")

    def test_SY4_la_dette_est_NOMMEE_et_ne_peut_que_decroitre(self):
        """⚠️⚠️ CE QUI RESTE ASYMETRIQUE EST DIT, PAS TU. Sept faits sont
        calcules, testes, et n'atteignent qu'un des trois documents signes.
        Les publier ailleurs change ce qu'un actuaire signe : c'est un
        arbitrage, pas un geste de lot.

        *Une dette qu'on mesure sous plafond est une dette qu'on tient.* Et
        le controle mord dans les DEUX SENS : si une cle est reparee, elle
        doit sortir de la table dans le MEME commit, sinon la table ment."""
        trouves = dict(_solitaires())
        encore = {c: ou for c, ou in _DETTE_GELEE.items() if c in trouves}
        reparees = sorted(set(_DETTE_GELEE) - set(trouves))
        self.assertEqual(
            reparees, [],
            f"{len(reparees)} cle(s) ne sont plus solitaires : les retirer "
            f"de `_DETTE_GELEE` dans le meme commit -- {reparees}")
        for cle, ou in encore.items():
            with self.subTest(cle=cle):
                self.assertEqual(
                    trouves[cle], ou,
                    f"`{cle}` a change de surface porteuse : {ou} -> "
                    f"{trouves[cle]}. La dette decrit un etat qui n'est plus")
        print(f"    SY-4 dette : {len(encore)} fait(s) sur une seule "
              f"surface, 0 repare(e) non retiree")

    def test_SY5_chaque_EXCEPTION_declaree_correspond_a_une_cle_REELLE(self):
        """⚠️⚠️ UNE TABLE D'EXEMPTIONS POURRIT SI ON NE LA RELIT PAS. Une
        exception pour une cle que plus personne ne lit n'exempte rien : elle
        reste, et le jour ou la cle revient sous le meme nom, elle la laisse
        passer sans que personne ne l'ait decide."""
        par = _par_fabrique()
        toutes = set().union(*par.values()) if par else set()
        mortes = sorted(c for c in _EXCEPTIONS if c not in toutes)
        self.assertEqual(
            mortes, [],
            f"{len(mortes)} exception(s) ne correspondent a aucune cle lue : "
            f"les retirer, ou dire pourquoi elles restent -- {mortes}")
        for cle, raison in _EXCEPTIONS.items():
            with self.subTest(exception=cle):
                self.assertGreaterEqual(
                    len(raison), 25,
                    f"`{cle}` est exemptee sans raison ecrite : une exemption "
                    f"sans motif est une asymetrie qu'on a cessee de voir")
        print(f"    SY-5 les {len(_EXCEPTIONS)} exceptions portent leur "
              f"raison et visent une cle reelle")


if __name__ == '__main__':
    unittest.main(verbosity=2)
