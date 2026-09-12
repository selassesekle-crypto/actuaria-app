"""
Sceau — une clé lue sous un nom que personne ne produit rend son repli, pour
toujours, et ne le dit jamais.

CE QUE CE SCEAU DÉFEND (D40, D14, D15, D25, D37)
L'audit avait relevé 745 accès `.get(clé, littéral numérique)` dans le
périmètre, dont 671 avec le défaut `0`, et les avait classés **mineurs** faute
d'avoir pu les instruire un par un. Ce sceau tranche autrement : il ne juge pas
les 726 accès (relevé de ce jour), il pose sur eux **une question fermée** —
*cette clé est-elle produite quelque part dans le périmètre ?*

Un repli est légitime quand la clé existe PARFOIS : il couvre l'exécution
partielle. Il est MUET quand la clé n'existe JAMAIS : la valeur publiée est
alors le littéral, définitivement, et aucune exécution ne le révélera. C'est
une faute de NOM, pas une donnée manquante — et une faute de nom ne se voit ni
à la lecture du producteur, ni à la lecture du lecteur, seulement en les
confrontant.

LES DIX CLÉS TROUVÉES, TOUTES VÉRIFIÉES PAR EXÉCUTION
  risk_adjustment_p3   P4 publiait **908 € de Risk Adjustment là où P3 avait
                       calculé 454 €** — exactement le double, sur le QRT S.14.
                       Le commentaire annonçait « priorité au calcul CoC de
                       P3 » : la priorité était écrite, jamais tenue.
  tp_sante / tp_prev   la ligne « TP = BE + RA » de l'onglet « Provisions » du
                       classeur signé sortait **vide dans les trois colonnes**.
  mcr_prevoyance       lu par un TEST, qui asserte `mcr >= 0` sur le repli `0` :
                       **l'assertion ne pouvait pas échouer**. Le test portait
                       le nom du plancher absolu et ne le vérifiait pas.
  m6 / m12             replis littéraux 0,40 et 0,20 derrière un chemin qui
                       aboutit : morts aujourd'hui, donc invérifiables demain.
  lr_poste             une colonne du classeur signé affichait « — » sur toutes
                       les lignes de toutes les exécutions depuis toujours.
  taux_ss              branche morte derrière `remb_ss`.
  bv01_stress_100/200  et `csm` : dans des modules que **personne n'importait**
                       (voir plus bas). Le défaut était réel, sa portée nulle.

⚠️ CE QUE LA MESURE A CORRIGÉ DANS MON PROPRE CONSTAT
J'ai d'abord annoncé « CSM publié à 0 € au lieu de 328 530 € » et « BV01 à 0 €
au lieu de −389 € ». C'est arithmétiquement exact et **sans aucune portée** :
`m_rapport_regl_sante.py` et `m_rapport_regl_prev.py` ne sont importés par
personne. Un défaut dans du code mort n'est pas un euro déplacé, et le dire
autrement serait exactement la faute que cet audit reproche au module.

Le relevé complet a trouvé **sept** modules jamais importés — l'audit n'en
citait qu'un (D37, `sp_diagnostics.py`). Les six autres sont une même famille
`m_rapport_*`, portant chacune les **neuf mêmes fonctions d'assistance,
identiques à l'AST**. 1 736 lignes supprimées.

⚠️ ET CE QUE LE RELEVÉ NE VOIT PAS — vérifié, pas supposé.
Le relevé AST des imports avait classé `sp_rapport_sante.py` parmi les morts.
**C'est faux** : il est chargé par un `import_module` construit à partir d'une
CHAÎNE, et enregistré comme `Site` dans `core/frontiere_llm.py`. Un relevé
d'imports ne voit pas un nom de module calculé. C'est pourquoi la suppression
n'a été décidée qu'après un second relevé, AU TEXTE, sur le dépôt entier.
"""
import ast
import io
import os
import unittest


def _est_nombre(noeud):
    """Littéral numérique, signe compris — `-1` est un `UnaryOp`, pas une
    constante."""
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, (int, float)):
        return True
    if isinstance(noeud, ast.UnaryOp) and isinstance(noeud.op, (ast.USub, ast.UAdd)):
        return _est_nombre(noeud.operand)
    return False


def _relever(racine):
    """Rend `(lues, produites)` sur tout le périmètre.

    `lues` : clé -> [(fichier, ligne)] pour les `.get(clé, littéral numérique)`.
    `produites` : clé -> {fichiers}, tous modes d'écriture confondus.
    """
    lues, produites = {}, {}
    for dossier, sous, fichiers in os.walk(racine):
        sous[:] = [s for s in sous if s != "__pycache__"]
        for fichier in sorted(fichiers):
            if not fichier.endswith(".py"):
                continue
            chemin = os.path.join(dossier, fichier)
            rel = os.path.relpath(chemin, racine).replace("\\", "/")
            arbre = ast.parse(io.open(chemin, encoding="utf-8").read())
            for n in ast.walk(arbre):
                # LECTURE : x.get("cle", <litteral numerique>)
                if (isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and n.func.attr == "get"
                        and len(n.args) == 2
                        and isinstance(n.args[0], ast.Constant)
                        and isinstance(n.args[0].value, str)
                        and _est_nombre(n.args[1])):
                    lues.setdefault(n.args[0].value, []).append((rel, n.lineno))
                # PRODUCTION : {"cle": ...}
                if isinstance(n, ast.Dict):
                    for c in n.keys:
                        if isinstance(c, ast.Constant) and isinstance(c.value, str):
                            produites.setdefault(c.value, set()).add(rel)
                # PRODUCTION : d["cle"] = ...  et  d["cle"] += ...
                if isinstance(n, (ast.Assign, ast.AugAssign)):
                    cibles = (n.targets if isinstance(n, ast.Assign)
                              else [n.target])
                    for t in cibles:
                        if (isinstance(t, ast.Subscript)
                                and isinstance(t.slice, ast.Constant)
                                and isinstance(t.slice.value, str)):
                            produites.setdefault(t.slice.value, set()).add(rel)
                # PRODUCTION : dict(cle=...)
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                        and n.func.id == "dict"):
                    for kw in n.keywords:
                        if kw.arg:
                            produites.setdefault(kw.arg, set()).add(rel)
    return lues, produites


RACINE = os.path.dirname(os.path.abspath(__file__))


class TestAucuneCleLueN_EstOrpheline(unittest.TestCase):
    """Le contrôle central : lire un nom que personne n'écrit."""

    @classmethod
    def setUpClass(cls):
        cls.lues, cls.produites = _relever(RACINE)

    def test_toute_cle_lue_avec_repli_est_produite_quelque_part(self):
        orphelines = sorted(k for k in self.lues if k not in self.produites)
        detail = "\n".join(
            "    %-28s lue en %s"
            % (k, ", ".join("%s:%d" % s for s in self.lues[k][:3]))
            for k in orphelines)
        self.assertEqual(
            [], orphelines,
            "%d cle(s) lue(s) avec un repli numerique que PERSONNE ne produit "
            "dans le perimetre. La valeur publiee sera le repli, pour "
            "toujours, et aucune execution ne le revelera :\n%s\n"
            "Soit la cle change de nom pour celui du producteur, soit le "
            "producteur la publie." % (len(orphelines), detail))

    def test_le_releve_porte_sur_une_assiette_non_triviale(self):
        """Un contrôle qui ne lit rien passe toujours.

        Sans cette borne, supprimer le périmètre rendrait le test ci-dessus
        vert. C'est la question « sur quelle assiette ? » posée au contrôle
        lui-même.
        """
        total = sum(len(v) for v in self.lues.values())
        self.assertGreater(
            total, 400,
            "Seulement %d acces releves : l'assiette du controle s'est "
            "effondree, son verdict ne vaut plus rien." % total)
        self.assertGreater(len(self.produites), 500)


class TestLesTroisCorrectifsDeCeLot(unittest.TestCase):
    """Chaque clé réparée, vérifiée à sa surface — pas seulement au relevé."""

    def _source(self, *elements):
        return io.open(os.path.join(RACINE, *elements), encoding="utf-8").read()

    def test_p4_lit_le_risk_adjustment_que_p3_publie(self):
        src = self._source("prevoyance", "p4_reporting", "agent.py")
        self.assertNotIn(
            "src.get('risk_adjustment_p3'", src,
            "P4 relit une cle que P3 ne produit pas : le QRT S.14 republierait "
            "le double du Risk Adjustment calcule.")
        self.assertIn('lire_premiere_cle', src)
        self.assertIn("'source_ra'", src,
                      "La provenance du Risk Adjustment doit etre publiee.")

    def test_le_rapport_combine_produit_les_tp_que_son_classeur_lit(self):
        src = self._source("rapport_actuariel", "agent.py")
        for cle in ('"tp_sante"', '"tp_prev"'):
            with self.subTest(cle=cle):
                self.assertIn(
                    cle, src,
                    "Sans %s, la ligne « TP = BE + RA » du classeur signe "
                    "sort vide." % cle)

    def test_le_test_du_plancher_mcr_verifie_le_plancher(self):
        src = self._source("prevoyance", "p4_reporting", "test_p4_valentin.py")
        self.assertNotIn(
            'r_p4.get("mcr_prevoyance", 0)', src,
            "Le test relit une cle absente : son assertion `mcr >= 0` "
            "s'appliquerait a nouveau au repli 0 et ne pourrait pas echouer.")
        self.assertIn("PLANCHER_ACTIF", src)
        self.assertIn("3_700_000", src)


class TestAucunCheminDeMachineNiDivisionNueSubsiste(unittest.TestCase):
    """D15 et D25 — deux défauts dormants, fermés au même endroit."""

    def test_aucun_chemin_de_machine_de_developpement(self):
        """Le dépôt est public.

        ⚠️ L'ASSIETTE SE MESURE PAR L'AST, PAS AU TEXTE. Un relevé au texte
        accusait quatre fichiers qui ne font que **citer** le motif pour
        expliquer le défaut — dont ce sceau lui-même. Exempter des NOMS DE
        FICHIER aurait été une assiette trop étroite, et donc un futur
        mensonge. Un contrôle qui accuse une explication ne sert à rien ; un
        contrôle exempté par liste ne surveille bientôt plus rien.

        Ce qui est interdit, c'est un chemin de machine **utilisé comme
        valeur** : une chaîne littérale qui atteint le code. Les commentaires
        n'entrent pas dans l'AST, et les docstrings sont écartées
        explicitement. La distinction est comportementale, pas nominale.

        UNE SEULE EXCLUSION, ET ELLE EST STRUCTURELLE : ce fichier-ci. Un
        contrôle dont le sujet est « citer telle chaîne » ne peut pas être son
        propre sujet — il doit bien nommer ce qu'il interdit. L'exclusion porte
        sur `__file__`, pas sur un motif de nom : rien d'autre ne peut s'y
        glisser, et le test suivant vérifie que l'exclusion ne vaut que pour un
        fichier.
        """
        fautifs = []
        moi = os.path.abspath(__file__)
        exclus = []
        for dossier, sous, fichiers in os.walk(RACINE):
            sous[:] = [s for s in sous if s != "__pycache__"]
            for fichier in sorted(fichiers):
                if not fichier.endswith(".py"):
                    continue
                chemin = os.path.join(dossier, fichier)
                if os.path.abspath(chemin) == moi:
                    exclus.append(fichier)
                    continue
                arbre = ast.parse(io.open(chemin, encoding="utf-8").read())
                # Les docstrings EXPLIQUENT, elles n'agissent pas.
                docs = set()
                for n in ast.walk(arbre):
                    if isinstance(n, (ast.Module, ast.ClassDef,
                                      ast.FunctionDef, ast.AsyncFunctionDef)):
                        corps = getattr(n, "body", None) or []
                        if (corps and isinstance(corps[0], ast.Expr)
                                and isinstance(corps[0].value, ast.Constant)
                                and isinstance(corps[0].value.value, str)):
                            docs.add(id(corps[0].value))
                for n in ast.walk(arbre):
                    if (isinstance(n, ast.Constant)
                            and isinstance(n.value, str)
                            and id(n) not in docs):
                        for motif in ("/home/claude", "/tmp/"):
                            if n.value.startswith(motif):
                                fautifs.append(
                                    "%s:%d  %r"
                                    % (os.path.relpath(chemin, RACINE),
                                       n.lineno, n.value[:40]))
        self.assertEqual(
            [os.path.basename(moi)], exclus,
            "L'exclusion doit porter sur CE fichier et sur aucun autre ; "
            "exclus : %s" % exclus)
        self.assertEqual(
            [], fautifs,
            "Chemin(s) de machine ATTEIGNANT LE CODE dans un depot public :"
            "\n  %s" % "\n  ".join(fautifs))

    def test_les_blocs_de_demonstration_ecrivent_dans_un_temporaire_reel(self):
        """`/tmp/p1` sous Windows n'est pas invalide : c'est `C:\\tmp\\p1`,
        cree a la racine du disque."""
        attendus = [
            ("prevoyance", "p1_tarification"), ("prevoyance", "p2_tables_morbidite"),
            ("prevoyance", "p3_provisionnement"), ("prevoyance", "p4_reporting"),
            ("sante", "s1_tarification"), ("sante", "s2_provisionnement"),
            ("sante", "s3_reporting"),
        ]
        for parties in attendus:
            with self.subTest(agent=parties[-1]):
                src = io.open(os.path.join(RACINE, *parties, "agent.py"),
                              encoding="utf-8").read()
                self.assertIn(
                    "repertoire_demonstration", src,
                    "%s ecrit encore dans un chemin POSIX litteral."
                    % parties[-1])

    def test_aucune_division_nue_dans_la_coordination(self):
        """D25 — la seule division du fichier sans garde, parmi douze."""
        src = io.open(os.path.join(RACINE, "coordination", "sp_coord", "agent.py"),
                      encoding="utf-8").read()
        arbre = ast.parse(src)
        lignes = src.splitlines()
        nues = []
        for n in ast.walk(arbre):
            if not (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)):
                continue
            den = n.right
            if isinstance(den, ast.Constant) and den.value not in (0, 0.0):
                continue
            if isinstance(den, ast.Call) and getattr(den.func, "id", "") == "max":
                continue
            nues.append("l.%d  %s" % (n.lineno, lignes[n.lineno - 1].strip()[:70]))
        self.assertEqual(
            [], nues,
            "Division(s) sans garde dans sp_coord : un SCR consolide nul leve "
            "ZeroDivisionError et AUCUN document n'est produit.\n  %s"
            % "\n  ".join(nues))


class TestAucunModuleMortDansLePerimetre(unittest.TestCase):
    """D37 — et les six que l'audit n'avait pas vus."""

    def test_tout_module_de_service_est_atteint(self):
        """⚠️ Relevé AST **et** au texte : un `import_module` construit à
        partir d'une chaîne est invisible au premier. `sp_rapport_sante.py`
        était un faux positif de ce relevé-là."""
        dossier = os.path.join(RACINE, "services")
        depot = os.path.dirname(RACINE)
        modules = [f[:-3] for f in sorted(os.listdir(dossier))
                   if f.endswith(".py") and f != "__init__.py"]
        orphelins = []
        for module in modules:
            mentions = 0
            for d, sous, fichiers in os.walk(depot):
                sous[:] = [s for s in sous
                           if s not in ("__pycache__", ".git", ".ruff_cache")]
                for f in fichiers:
                    if not f.endswith(".py") or f == module + ".py":
                        continue
                    try:
                        contenu = io.open(os.path.join(d, f),
                                          encoding="utf-8").read()
                    except (OSError, UnicodeDecodeError):
                        continue
                    if module in contenu:
                        mentions += 1
            if mentions == 0:
                orphelins.append(module)
        self.assertEqual(
            [], orphelins,
            "Module(s) de service que RIEN dans le depot ne mentionne : %s. "
            "Sept l'etaient le 12/09/2026, pour 1 736 lignes." % orphelins)


if __name__ == "__main__":
    unittest.main()
