# ruff: noqa
"""PASSAGE LIBELLES -- quel champ atteint REELLEMENT un livrable ?

⚠️⚠️ CONCLU PAR EXECUTION, JAMAIS PAR LECTURE. Sur un seul champ
(`justification_regl`), trois methodes ont donne trois reponses :
    grep du nom          -> "aucun lecteur"   FAUX : il est lu par `.items()`
    lecture de la boucle -> "publie"          FAUX : un filtre isinstance l'ecarte
    EXECUTION            -> non publie        verifie dans les cellules produites
On PRODUIT donc le livrable et on lit ce qu'il contient.

⚠️ Un .docx et un .xlsx sont des ARCHIVES ZIP : chercher un marqueur dans
leurs octets bruts ne prouve rien. On decompresse.

⚠️⚠️ LES TROIS ANGLES MORTS DE CE BANC, ET COMMENT ON LES LEVE. Un « muet »
n'est une trouvaille que si les trois sont ecartes :

  1. ITERATION GENERIQUE -- un champ atteint par `for k, v in d.items()` n'est
     jamais NOMME : `grep` ne le voit pas. On execute.
  2. CLE vs VALEUR -- un champ CONSOMME PUIS REFORMATE parait muet a tort
     (`synthese_exclusions` republie le nom de colonne, pas le motif). On
     marque AUSSI les cles -- voir `main()` en fin de fichier.
  3. MISE EN FORME -- un marqueur pose sur un NOMBRE est detruit par
     l'arrondi : `1.5757` sort en `1.576`. **Les marqueurs doivent etre des
     CHAINES.** Pour un champ numerique, le banc ne conclut pas : il faut
     verifier si l'information arrive par une AUTRE source (mesure : le Gini,
     le score et le RMSE de la fiche arrivaient deja par `modele_production`).

⚠️⚠️ QUATRIEME ANGLE MORT : LE DOCUMENT N'EST PAS LE SEUL CHEMIN VERS
L'ACTUAIRE -- L'ECRAN EN EST UN AUTRE. Un champ muet dans les cinq livrables
peut etre affiche par l'application, et le declarer « perdu » serait faux.

⚠️⚠️ ET LA METHODE Y CHANGE, IL FAUT LE DIRE : le chemin DOCUMENT se conclut
par EXECUTION ; le chemin ECRAN se mesure par AST SEULEMENT.
    POURQUOI : `streamlit` est ABSENT de l'environnement (mesure au lot 0.2),
    l'application ne peut donc pas etre executee ici. Et elle disparait a la
    migration -- installer une bibliotheque pour executer du code condamne
    n'a pas ete juge utile (arbitrage du 25/08).
    CE QUE CELA COUTE : un relevé statique voit ce qui est NOMME et ce qui est
    ITERE, il ne voit pas ce que l'ecran affiche REELLEMENT a l'execution.
    C'est une borne du banc, pas un resultat -- elle est publiee comme telle.

⚠️ LE MEME ANGLE MORT S'Y APPLIQUE : l'app porte 12 iterations generiques
(`for k, v in <dict>.items()`), dont sur `graphiques`. Un champ atteint par
l'une d'elles n'est JAMAIS NOMME : un relevé par `.get('X')` le dirait muet a
tort. On releve donc les DEUX, et on les distingue dans le verdict.
"""
import io
import logging
import pathlib
import sys
import warnings
import zipfile

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')
if __name__ == '__main__':
    logging.disable(logging.CRITICAL)

import openpyxl


def M(nom: str) -> str:
    """Marqueur unique et sans separateur : il doit traverser tout formatage."""
    return 'ZQMARQ' + nom.replace('.', '').replace('_', '') + 'ZQ'


def texte_livrable(sortie) -> str:
    """Le texte REELLEMENT contenu dans un livrable, quel que soit son format."""
    if isinstance(sortie, (bytes, bytearray)):
        if sortie[:2] == b'PK':
            z = zipfile.ZipFile(io.BytesIO(sortie))
            if any(n.startswith('xl/') for n in z.namelist()):
                wb = openpyxl.load_workbook(io.BytesIO(sortie))
                return "\n".join(
                    str(c.value) for ws in wb.worksheets
                    for row in ws.iter_rows() for c in row
                    if c.value is not None)
            return "\n".join(z.read(n).decode('utf-8', 'replace')
                             for n in z.namelist() if n.endswith('.xml'))
        return sortie.decode('utf-8', 'replace')
    return str(sortie)


class HarnaisNonValide(RuntimeError):
    """Le banc n'a pas pu prouver qu'il regarde au bon endroit.

    ⚠️⚠️ CETTE EXCEPTION EST LA LEÇON LA PLUS CHÈRE DE CE BANC. Le premier
    essai sur A3/A4/A5 a rendu **tous les champs muets** — non parce qu'ils le
    sont, mais parce que ma fixture posait ses marqueurs sur des clés que les
    exportateurs ne lisent pas : ils lisent `validation_glm.conclusion`, PAS
    `commentaire`, et ils le lisent **niché**, pas à la racine.
    **J'aurais fabriqué une quarantaine de faux constats, tous avec
    l'apparence de la mesure.**

    *Un banc qui rend « muet » parce qu'il regarde au mauvais endroit est
    indiscernable d'un banc qui a trouvé quelque chose.* La garde est donc
    BLOQUANTE, pas informative : on ne publie aucun verdict muet tant qu'au
    moins un champ connu n'a pas été retrouvé PUBLIÉ.
    """


def chemins_lus(chemin_service: str, nom_export: str, racine: str) -> list:
    """Les CHEMINS DE LECTURE, y compris NICHÉS, d'un exportateur — par AST.

    ⚠️ Relever les NOMS lus ne suffit pas : `export_excel_a3` lit
    `result_a3['validation_glm']['conclusion']`. Un marqueur posé à la racine
    sur `conclusion` n'apparaît jamais. On suit donc les alias
    (`val = result_a3.get('validation_glm', {})`) pour reconstituer le chemin.
    """
    import ast
    arbre = ast.parse(pathlib.Path(chemin_service).read_text(encoding='utf-8'))
    fn = next(n for n in ast.walk(arbre)
              if isinstance(n, ast.FunctionDef) and n.name == nom_export)
    alias = {racine: ()}
    for _ in range(4):                      # les alias se chaînent
        for n in ast.walk(fn):
            if (isinstance(n, ast.Assign) and len(n.targets) == 1
                    and isinstance(n.targets[0], ast.Name)
                    and isinstance(n.value, ast.Call)
                    and isinstance(n.value.func, ast.Attribute)
                    and n.value.func.attr == 'get' and n.value.args
                    and isinstance(n.value.args[0], ast.Constant)
                    and isinstance(n.value.func.value, ast.Name)
                    and n.value.func.value.id in alias):
                alias[n.targets[0].id] = (alias[n.value.func.value.id]
                                          + (n.value.args[0].value,))
    trouves = set()
    for n in ast.walk(fn):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'get' and n.args
                and isinstance(n.args[0], ast.Constant)
                and isinstance(n.args[0].value, str)
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id in alias):
            trouves.add(alias[n.func.value.id] + (n.args[0].value,))
    return sorted(trouves)


# ══════════════════════════════════════════════════════════════════════════
# ⚠️⚠️ POURQUOI IL N'Y A PAS ICI DE DERIVATION AUTOMATIQUE DE FIXTURE
# ══════════════════════════════════════════════════════════════════════════
# J'ai ecrit puis RETIRE une fonction `chemins_conteneurs()` censee deviner,
# par AST, quels chemins l'exportateur traite comme des conteneurs plutot que
# comme des valeurs. **Elle rendait zero.** Et la cause n'est pas un bug de
# detail : elle est structurelle.
#
#     met = result_a3.get('metriques', {})       <- ce chemin, l'AST le voit
#     for nom, m in met.items():
#         m.get('gini')                          <- CELUI-CI, non
#
# `m` est une VARIABLE DE BOUCLE. L'acces se fait au niveau de l'ELEMENT, pas
# du chemin : aucun relevé par chemin ne peut le reconstituer. Poser un
# marqueur CHAINE sur `metriques` fait donc lever `AttributeError: 'str'
# object has no attribute 'get'`, exception que le `try` de l'exportateur
# avale, et `export_excel_a3` rend `b''`.
#
# ⚠️ **LE BANC CONCLURAIT ALORS « TOUT EST MUET » SUR UN LIVRABLE QUI N'A
# JAMAIS ETE PRODUIT.** C'est exactement ce que `exiger_harnais_valide`
# empeche -- et c'est ce qui s'est produit : trois refus sur trois agents.
#
# LA VOIE QUI RESTE : ne pas DEVINER la fixture, la PRENDRE d'un vrai
# resultat d'agent. C'est un lot en soi, et il n'est pas fait.
# Une fixture devinee ne s'ameliore pas : elle se remplace.


def fixture_marquee(chemins: list, agent: str) -> dict:
    """Un résultat dont CHAQUE chemin réellement lu porte son marqueur.

    ⚠️ Les chemins INTERMÉDIAIRES deviennent des dicts, les FEUILLES portent
    le marqueur. **Cela ne suffit PAS** — voir le bloc ci-dessus : une feuille
    qui est en réalité un conteneur casse l'exportateur. Cette fonction est
    donc un point de départ, jamais une fixture valide en soi.
    """
    intermediaires = {c[:i] for c in chemins for i in range(1, len(c))}
    vides = intermediaires
    racine: dict = {}
    for c in chemins:
        noeud = racine
        for seg in c[:-1]:
            noeud = noeud.setdefault(seg, {})
        if c in vides:
            noeud.setdefault(c[-1], {})
        else:
            noeud[c[-1]] = M(f"{agent}.{'.'.join(c)}")
    return racine


def exiger_harnais_valide(agent: str, textes: dict, chemins: list) -> list:
    """⚠️⚠️ BLOQUANT. Rend les champs retrouvés PUBLIÉS, ou LÈVE.

    Tant qu'aucun champ connu n'est retrouvé, le banc n'a rien prouvé et ses
    « muets » ne valent rien. *C'est cette garde qui a fait la différence entre
    un vrai arrêt et quarante faux constats.*
    """
    tout = "\n".join(textes.values())
    publies = [c for c in chemins if M(f"{agent}.{'.'.join(c)}") in tout]
    if not publies:
        raise HarnaisNonValide(
            f"[{agent}] AUCUN des {len(chemins)} champs lus par l'exportateur "
            f"n'a ete retrouve dans les livrables produits ({len(tout)} "
            f"caracteres). Le harnais regarde au mauvais endroit, ou les "
            f"livrables ont pris un chemin degrade. AUCUN VERDICT « MUET » "
            f"N'EST PUBLIABLE DANS CET ETAT.")
    return publies


def lecture_par_l_ecran(chemin_app: str, champs) -> dict:
    """Ce que l'ECRAN lit d'un resultat d'agent -- releve PAR AST.

    Rend {champ: 'nomme' | 'generique' | 'absent'} :
      · `nomme`     -- lu explicitement (`.get('X')` ou `['X']`) ;
      · `generique` -- le champ est un CONTENEUR itere (`for k, v in X.items()`),
                       donc son CONTENU atteint l'ecran sans etre nomme ;
      · `absent`    -- ni l'un ni l'autre.

    ⚠️⚠️ CE RELEVE EST ASYMETRIQUE, ET C'EST CE QUI LE REND UTILISABLE.
    Il matche des NOMS DE CLE n'importe ou dans l'application -- il ne sait pas
    si le `rapport` lu l.1961 est celui d'A6 ou d'un autre agent.
      · `absent`  est FIABLE : un nom jamais lu nulle part n'est certainement
        pas lu pour A6. C'est le seul sens qui autorise a conclure.
      · `nomme` / `generique` sont un DOUTE, pas une preuve : ils suffisent a
        NE PAS declarer un champ perdu, jamais a affirmer qu'il est affiche.
    On ne se sert donc de ce relevé que pour RETIRER des accusations, jamais
    pour en ajouter -- c'est la regle d'asymetrie appliquee a un banc.
    """
    import ast
    src = pathlib.Path(chemin_app).read_text(encoding='utf-8')
    arbre = ast.parse(src)
    nommes, conteneurs = set(), set()
    for n in ast.walk(arbre):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'get' and n.args
                and isinstance(n.args[0], ast.Constant)):
            nommes.add(n.args[0].value)
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant):
            nommes.add(n.slice.value)
        # ⚠️ L'ITERATION GENERIQUE : le contenu passe sans etre nomme.
        if (isinstance(n, ast.For) and isinstance(n.iter, ast.Call)
                and isinstance(n.iter.func, ast.Attribute)
                and n.iter.func.attr in ('items', 'values', 'keys')):
            texte = ast.unparse(n.iter.func.value)
            for c in champs:
                if f"'{c}'" in texte or f'.{c}' in texte or texte.endswith(c):
                    conteneurs.add(c)
    etat = {}
    for c in champs:
        etat[c] = ('nomme' if c in nommes
                   else ('generique' if c in conteneurs else 'absent'))
    return etat


def fiche_marquee() -> dict:
    return {
        'modele_recommande':  M('fiche.modele_recommande'),
        'profil_utilise':     M('fiche.profil_utilise'),
        'score_final':        0.8373,
        'gini':               0.2145,
        'overfit_ratio':      1.07,
        'forces':             [M('fiche.forces')],
        'faiblesses':         [M('fiche.faiblesses')],
        'risques':            [M('fiche.risques')],
        'alternatives':       [M('fiche.alternatives')],
        'questions_actuaire': [M('fiche.questions_actuaire')],
        'justification_regl': [M('fiche.justification_regl')],
        'decision_finale':    M('fiche.decision_finale'),
    }


def resultat_a6_marque() -> dict:
    modele = {'modele': M('modele_production.modele'), 'famille': 'GBM',
              'gini_test': 0.2145, 'gini_train': 0.23, 'overfit_ratio': 1.07,
              'score_global': 0.8373, 'rmse_test': 12.3}
    return {
        'success': True, 'branche': 'auto', 'statut_rag': 'AMBRE',
        'classement': [dict(modele, rang=1)], 'modele_production': modele,
        'backtest': {'disponible': True, 'n_fenetres': 3, 'gini_moyen': 0.20,
                     'stabilite': M('backtest.stabilite'),
                     'methode': 'walk_forward'},
        'lift_ratio': 1.4, 'lift_statut': M('lift_statut'),
        'exclusions_conformite': {'colX': M('exclusions_conformite')},
        'alertes_conformite': {'colY': {'spearman': 0.99}},
        'alertes_modele': [{'modele': 'GBM', 'severite': 'AMBRE',
                            'message': M('alertes_modele.message')}],
        'exclusions_cible': [M('exclusions_cible')],
        'valide_par_actuaire_dl': M('valide_par_actuaire_dl'),
        'rapport_qualite': None, 'rapport_mapping': None,
        'colonnes_plan_manquantes': None, 'courbes': {}, 'graphiques': {},
        'graphiques_validation': {},
        'validation_selection': {'verdict': M('validation_selection.verdict')},
        'fiche_decision': fiche_marquee(),
        'rapport': {'etapes': [M('rapport.etapes')]},
        'commentaire': M('commentaire'), 'audit_id': 'A6-PASSAGE',
        'hypotheses': {'h1': M('hypotheses.h1')},
        'audit_trail': {'profil_ponderation': M('audit_trail.profil_ponderation'),
                        'environnement': 'test', 'profil_valide_par': None,
                        'gouvernance_ok': False},
    }


CHAMPS = ([f'fiche.{k}' for k in fiche_marquee()] +
          ['modele_production.modele', 'backtest.stabilite', 'lift_statut',
           'exclusions_conformite', 'alertes_modele.message',
           'exclusions_cible', 'valide_par_actuaire_dl',
           'validation_selection.verdict', 'rapport.etapes', 'commentaire',
           'hypotheses.h1', 'audit_trail.profil_ponderation'])


def main() -> None:
    from direction_non_vie.tarification.services import rapport_equipe_tarif as RE
    from direction_non_vie.tarification.services import rapport_modeles_tarif as RM
    from direction_non_vie.tarification.services.tarif_excel import export_excel_a6

    res = resultat_a6_marque()
    livrables = {}
    for nom, appel in (
        ('excel A6',     lambda: export_excel_a6(res, audit_id='A6-PASSAGE')),
        ('html equipe',  lambda: RE.export_html_equipe({'a6': res}, branche='auto')),
        ('word equipe',  lambda: RE.export_word_equipe({'a6': res}, branche='auto')),
        ('html modeles', lambda: RM.export_html(res)),
        ('word modeles', lambda: RM.export_word(res)),
    ):
        try:
            livrables[nom] = texte_livrable(appel())
        except Exception as exc:
            livrables[nom] = ''
            print(f"  [INDISPONIBLE] {nom} : {type(exc).__name__}: {exc}")

    # ⚠️ CONTROLE DE VALIDITE DU BANC : un livrable qui ne porte AUCUN marqueur
    # a probablement pris un chemin degrade -- ses zeros ne prouvent rien.
    print("=" * 78)
    print("  VALIDITE DU BANC -- un livrable sans aucun marqueur ne prouve rien")
    print("=" * 78)
    for nom, txt in livrables.items():
        n = sum(1 for c in CHAMPS if M(c) in txt)
        etat = '[VALIDE ]' if n else '[SUSPECT]'
        print(f"  {etat} {nom:14s} {len(txt):8d} car  {n} marqueur(s)")

    print()
    print("=" * 78)
    print("  QUEL LIVRABLE PORTE QUEL CHAMP ?  (X = present)")
    print("=" * 78)
    entetes = list(livrables)
    print(f"  {'champ':38s} " + " ".join(f"{n[:12]:>13s}" for n in entetes))
    muets = []
    for champ in CHAMPS:
        cases = [('X' if M(champ) in livrables[n] else '.') for n in entetes]
        if 'X' not in cases:
            muets.append(champ)
        print(f"  {champ:38s} " + " ".join(f"{c:>13s}" for c in cases))

    print()
    print("=" * 78)
    print(f"  {len(muets)}/{len(CHAMPS)} CHAMPS N'ATTEIGNENT AUCUN DES "
          f"{len(entetes)} LIVRABLES")
    print("=" * 78)
    for c in muets:
        print(f"    {c}")

    # ── ⚠️⚠️ LE QUATRIEME CHEMIN : L'ECRAN ──────────────────────────────────
    # Un champ muet dans les cinq livrables peut etre affiche par l'app. Le
    # declarer « perdu » sans avoir regarde ce chemin serait faux.
    print()
    print("=" * 78)
    print("  L'ECRAN  (actuaria_app.py) -- releve PAR AST, PAS par execution")
    print("=" * 78)
    print("  ⚠️ streamlit est ABSENT de l'environnement : l'app ne peut pas etre")
    print("     executee ici. Ce releve voit ce qui est NOMME et ce qui est")
    print("     ITERE, pas ce que l'ecran affiche reellement. Borne du banc.")
    print()
    # ⚠️ La racine des marqueurs (`fiche.`) n'est PAS la cle du resultat
    # (`fiche_decision`) : sans cette table, le banc interrogerait un nom qui
    # n'existe nulle part et conclurait « absent » pour la mauvaise raison.
    CLE_REELLE = {'fiche': 'fiche_decision'}
    racines = sorted({CLE_REELLE.get(c.split('.')[0], c.split('.')[0])
                      for c in CHAMPS})
    ecran = lecture_par_l_ecran(
        str(pathlib.Path(__file__).resolve().parents[4] / 'actuaria_app.py'),
        racines)
    for cle, etat in sorted(ecran.items()):
        marque = {'nomme': '[LU NOMME  ]', 'generique': '[LU GENERIQUE]',
                  'absent': '[non lu     ]'}[etat]
        print(f"  {marque} {cle}")

    print()
    print("=" * 78)
    print("  VERDICT CROISE — muet dans les livrables ET non lu a l'ecran")
    print("=" * 78)
    perdus, ecran_seul = [], []
    for c in muets:
        _racine = CLE_REELLE.get(c.split('.')[0], c.split('.')[0])
        if ecran.get(_racine, 'absent') == 'absent':
            perdus.append(c)
        else:
            ecran_seul.append(c)
    print(f"  PERDUS des deux cotes ({len(perdus)}) :")
    for c in perdus:
        print(f"      {c}")
    if ecran_seul:
        print(f"  muets en document, mais un nom identique est lu par l'app "
              f"({len(ecran_seul)}) :")
        for c in ecran_seul:
            print(f"      {c}   <-- NE PAS les declarer perdus")
        print("  ⚠️ Ce n'est pas une preuve d'affichage : le relevé matche un")
        print("     NOM, pas la provenance. Il suffit a retirer l'accusation,")
        print("     jamais a affirmer que l'actuaire le voit.")

    fiche = [c for c in CHAMPS if c.startswith('fiche.')]
    publies = [c for c in fiche if c not in muets]
    print()
    print(f"  LA FICHE D'AIDE A LA DECISION : {len(publies)}/{len(fiche)} "
          f"champs publies ({100 * len(publies) // len(fiche)} %)")
    print(f"    publies : {publies}")

    # ── ⚠️⚠️ LA LIMITE DU BANC, ET COMMENT ON LA LEVE ────────────────────────
    # Un marqueur absent prouve que la VALEUR n'est pas publiee VERBATIM. Il ne
    # prouve pas que le champ est ignore : un service peut le CONSOMMER puis le
    # REFORMATER. `synthese_exclusions` republie ainsi le NOM DE COLONNE et non
    # le motif -- `exclusions_conformite` paraissait muet alors qu'il est lu.
    # On distingue donc les deux en marquant AUSSI LES CLES.
    print()
    print("=" * 78)
    print("  CONSOMME-ET-REFORMATE  vs  VRAIMENT MUET  (marqueur dans la CLE)")
    print("=" * 78)
    res2 = resultat_a6_marque()
    res2['exclusions_conformite'] = {'ZQCLEEXCLZQ': 'un motif quelconque'}
    res2['alertes_modele'] = [{'modele': 'ZQCLEMODZQ', 'severite': 'AMBRE',
                               'message': 'ZQCLEMSGZQ'}]
    res2['validation_selection'] = {'verdict': 'ZQCLEVERDZQ', 'conforme': False}
    res2['backtest'] = {'disponible': True, 'n_fenetres': 3, 'gini_moyen': 0.2,
                        'stabilite': 'ZQCLESTABZQ', 'methode': 'ZQCLEMETHZQ'}
    tout = ''
    for appel in (lambda: export_excel_a6(res2, audit_id='X'),
                  lambda: RE.export_html_equipe({'a6': res2}, branche='auto'),
                  lambda: RE.export_word_equipe({'a6': res2}, branche='auto'),
                  lambda: RM.export_html(res2),
                  lambda: RM.export_word(res2)):
        try:
            tout += texte_livrable(appel())
        except Exception:
            pass
    for marque, quoi in (('ZQCLEEXCLZQ', 'exclusions_conformite  (la CLE)'),
                         ('ZQCLEMODZQ', 'alertes_modele.modele'),
                         ('ZQCLEMSGZQ', 'alertes_modele.message'),
                         ('ZQCLEVERDZQ', 'validation_selection.verdict'),
                         ('ZQCLESTABZQ', 'backtest.stabilite'),
                         ('ZQCLEMETHZQ', 'backtest.methode')):
        etat = 'CONSOMME' if marque in tout else 'MUET'
        print(f"  [{etat:8s}] {quoi}")


def temoin_croise_par_agent() -> None:
    """⚠️⚠️ LE TÉMOIN CROISÉ SUR A3, A4 ET A5 — avec un harnais VALIDÉ.

    Le premier essai avait rendu tous les champs muets, faute d'un harnais
    correct. Ici la fixture est DÉRIVÉE de ce que chaque exportateur lit
    réellement, et `exiger_harnais_valide` LÈVE si rien n'est retrouvé.
    """
    from direction_non_vie.tarification.services import tarif_excel as TE

    SERVICE = str(pathlib.Path(__file__).resolve().parents[4]
                  / 'direction_non_vie' / 'tarification' / 'services'
                  / 'tarif_excel.py')
    AGENTS = (('A3', 'export_excel_a3', 'result_a3'),
              ('A4', 'export_excel_a4', 'result_a4'),
              ('A5', 'export_excel_a5', 'result_a5'))

    print()
    print("=" * 78)
    print("  TEMOIN CROISE SUR A3 / A4 / A5 — harnais DERIVE, garde BLOQUANTE")
    print("=" * 78)
    racines_ecran = set()
    resume = []
    for agent, export, racine in AGENTS:
        chemins = chemins_lus(SERVICE, export, racine)
        fixture = fixture_marquee(chemins, agent)
        fixture.setdefault('success', True)
        try:
            txt = texte_livrable(getattr(TE, export)(fixture, audit_id=agent))
        except Exception as exc:
            print(f"  [{agent}] l'export a LEVE : {type(exc).__name__}: {exc}")
            txt = ''
        try:
            publies = exiger_harnais_valide(agent, {'excel': txt}, chemins)
        except HarnaisNonValide as exc:
            print(f"  [{agent}] ⛔ HARNAIS NON VALIDE — aucun verdict publie.")
            print(f"        {exc}")
            resume.append((agent, None, None))
            continue
        muets = [c for c in chemins if c not in publies]
        print(f"  [{agent}] harnais VALIDE : {len(publies)}/{len(chemins)} "
              f"chemins retrouves publies")
        print(f"        temoin PUBLIE  : {'.'.join(publies[0])}")
        if muets:
            print(f"        temoin MUET    : {'.'.join(muets[0])}")
        racines_ecran.update(c[0] for c in muets)
        resume.append((agent, len(publies), len(muets)))

    if racines_ecran:
        ecran = lecture_par_l_ecran(
            str(pathlib.Path(__file__).resolve().parents[4] / 'actuaria_app.py'),
            sorted(racines_ecran))
        lus = sorted(k for k, v in ecran.items() if v != 'absent')
        print()
        print(f"  croise ECRAN : {len(lus)} racine(s) muette(s) en document "
              f"sont NEANMOINS lues par l'app -> ne pas les declarer perdues")
        for k in lus:
            print(f"      {k}")

    print()
    for agent, pub, muet in resume:
        etat = "NON VALIDE" if pub is None else f"{pub} publies / {muet} muets"
        print(f"    {agent} : {etat}")


if __name__ == '__main__':
    main()
    temoin_croise_par_agent()
