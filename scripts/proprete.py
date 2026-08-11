"""Mesure la proprete d'un lot : ruff, vulture, et les locales mortes.

A quoi il sert : rendre REPRODUCTIBLE une mesure qui vivait dans une habitude.
Trois pieges d'outillage ont fausse cette mesure au moins une fois chacun, et
chacun est desamorce ici plutot que d'etre rappele a qui s'en souviendra.

  1. RUFF NE RESOUT PAS LA MEME CONFIGURATION HORS DU DEPOT. Comparer un
     fichier de reference ecrit dans un dossier temporaire donne des comptes
     qui n'ont rien a voir. La reference passe donc par `--stdin-filename`,
     au chemin EXACT du fichier mesure.

  2. VULTURE TAIT LES METHODES `test_*` SELON LE NOM DU FICHIER. Une
     reference nommee autrement affichait 97 signalements au lieu de 23. Le
     fichier temoin garde donc le meme prefixe de nom.

  3. `ruff --fix` CORRIGE DES DEFAUTS ANTERIEURS. Deux fois dans la meme
     journee il a touche une douzaine de hunks hors du lot. Cet outil ne
     l'appelle jamais : il MESURE, il ne corrige pas.

Et il porte la regle arbitrée le 10/08/2026 : le zero n'est strict que sur
les codes de CORRECTION. `RUF012` et `UP009` sont des preferences de style —
une divergence s'y declare au lieu de faire deplacer une fixture au mauvais
endroit. Une regle de proprete qui arbitre la conception a cesse de servir.

Usage :
    py scripts/proprete.py                  # les fichiers du diff courant
    py scripts/proprete.py a.py b.py        # des fichiers nommes
"""
import ast
import os
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Les classes de test sont decouvertes par REFLEXION : vulture ne peut pas
#: le voir. Le motif vaut mieux qu'une liste blanche, qui deviendrait une
#: liste a tenir.
MOTIF_VULTURE = 'T[0-9]*_*,V[0-9]_*,TRFR*,GOUV_*,S[0-9]_*,F5_*'

#: Ce sur quoi le zero est STRICT : des defauts, pas des gouts.
CODES_STRICTS = ('F', 'E', 'W', 'UP0', 'DTZ', 'ISC', 'W605', 'RUF010', 'BLE')

#: Ce dont une divergence se DECLARE : des preferences de style.
CODES_TOLERES = ('RUF012', 'UP009')


def _run(args, entree=None):
    return subprocess.run(args, capture_output=True, text=True,
                          encoding='utf-8', errors='replace',
                          input=entree, cwd=RACINE, check=False).stdout


def fichiers_du_diff():
    sortie = _run(['git', 'diff', '--name-only'])
    return [f for f in sortie.split('\n') if f.strip().endswith('.py')]


def contenu_head(chemin):
    """Le fichier tel qu'il est au dernier commit, ou None s'il est neuf."""
    r = subprocess.run(['git', 'show', f'HEAD:{chemin}'], capture_output=True,
                       text=True, encoding='utf-8', errors='replace',
                       cwd=RACINE, check=False)
    return r.stdout if r.returncode == 0 else None


def codes_ruff(sortie):
    """Les codes signales, par nom, depuis une sortie `--output-format=concise`."""
    codes = {}
    for ligne in sortie.split('\n'):
        morceaux = ligne.split(': ', 1)
        if len(morceaux) != 2:
            continue
        code = morceaux[1].split(' ', 1)[0]
        if code[:1].isupper():
            codes[code] = codes.get(code, 0) + 1
    return codes


def ruff(chemin, source=None):
    """Les codes ruff. `source` mesure un contenu AU CHEMIN de `chemin`."""
    args = ['py', '-m', 'ruff', 'check', '--output-format=concise']
    if source is None:
        return codes_ruff(_run(args + [chemin]))
    # ⚠️ PIEGE 1 : la reference passe par le MEME chemin, jamais par un
    # fichier temporaire hors du depot.
    return codes_ruff(_run(args + ['--stdin-filename', chemin, '-'], source))


def vulture(chemin, source=None):
    """Le nombre de signalements vulture, motif d'exclusion applique."""
    args = ['py', '-m', 'vulture', '--min-confidence', '60',
            '--ignore-names', MOTIF_VULTURE]
    if source is None:
        return len([x for x in _run(args + [chemin]).split('\n') if x.strip()])
    # ⚠️ PIEGE 2 : le temoin garde le MEME prefixe de nom, sinon vulture
    # cesse de taire les methodes `test_*`.
    dossier, nom = os.path.split(chemin)
    base, _ = os.path.splitext(nom)
    temoin = os.path.join(RACINE, dossier, f'{base}_zz_temoin.py')
    try:
        with open(temoin, 'w', encoding='utf-8', newline='\n') as f:
            f.write(source)
        return len([x for x in _run(args + [temoin]).split('\n') if x.strip()])
    finally:
        if os.path.exists(temoin):
            os.remove(temoin)


def locales_mortes(source):
    """Les locales assignees et jamais relues.

    ⚠️ L'ANGLE MORT DE RUFF : `F841` IGNORE les noms prefixes `_`. Ce
    controle existe parce que quatre variables mortes ont survecu a un lot
    entier sans que l'outil ne dise rien.
    """
    try:
        arbre = ast.parse(source)
    except SyntaxError:
        return -1
    mortes = 0
    for f in ast.walk(arbre):
        if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        assignes, lus = set(), set()
        for n in ast.walk(f):
            if isinstance(n, ast.Name):
                (assignes if isinstance(n.ctx, ast.Store) else lus).add(n.id)
            elif isinstance(n, ast.Attribute):
                lus.add(getattr(n.value, 'id', ''))
            elif isinstance(n, (ast.Global, ast.Nonlocal)):
                lus.update(n.names)
        mortes += len([n for n in assignes - lus if n != '_'])
    return mortes


def _famille(code):
    """A quelle famille appartient un code — LA REGLE, en un seul endroit.

    /!\\ ELLE EST PARTAGEE PAR LE DELTA ET PAR L'ABSOLU. Deux
    classifications donneraient deux chiffres pour le meme fichier selon qui
    mesure — c'est exactement l'erreur commise en annoncant 3 791 defauts la
    ou l'outil en compte 7 618.

    /!\\ UN CODE INCONNU EST UN CODE DE CORRECTION. Defensif et arbitre : un
    code que le projet n'a pas encore examine compte comme un defaut jusqu'a
    ce qu'il soit declare tolere. `I001` et les `RUF` non listes sont dans ce
    cas.
    """
    if code in CODES_TOLERES:
        return 'tolere'
    if code.startswith(CODES_STRICTS):
        return 'correction'
    # /!\ STRICT PAR DEFAUT, ET CE N'EST PAS LA MEME AFFIRMATION. `F401` est
    # un defaut ARBITRE ; `I001` est un code que le projet n'a JAMAIS EXAMINE.
    # Les confondre laisserait croire que 7 618 defauts ont ete juges, quand
    # la moitie n'a jamais ete regardee. Avant ce lot, les deux branches de
    # `_classer` etaient IDENTIQUES : `CODES_STRICTS` ne gouvernait rien.
    return 'jamais_examine'


def _classer(avant, apres):
    """Les codes qui ont AUGMENTE, separes selon la regle arbitrée."""
    stricts, toleres = {}, {}
    for code, n in apres.items():
        ecart = n - avant.get(code, 0)
        if ecart <= 0:
            continue
        if _famille(code) == 'tolere':
            toleres[code] = ecart
        else:
            stricts[code] = ecart
    return stricts, toleres


def absolu(codes):
    """L'etat ABSOLU d'un fichier : (a corriger, declares).

    /!\\ POURQUOI CETTE FONCTION EXISTE. L'outil affichait `31 -> 31` sans
    jamais dire que 24 de ces 31 etaient des codes de CORRECTION : le tableau
    avait l'air rassurant. Un defaut committe devenait invisible a
    l'instrument cense l'attraper -- meme famille que la gate rendant
    << Ran 0 tests >> et sortant en 0.

    /!\\ ELLE N'EST PAS UN VERDICT. Le verdict reste sur le DELTA : faire
    echouer un lot sur l'absolu bloquerait toute retouche dans un gros
    fichier. La dette pre-existante se ferme par DECISION DE LOT, annoncee
    dans le message — jamais automatiquement.
    """
    arbitres = sum(n for c, n in codes.items()
                   if _famille(c) == 'correction')
    jamais_vus = sum(n for c, n in codes.items()
                     if _famille(c) == 'jamais_examine')
    declares = sum(n for c, n in codes.items() if _famille(c) == 'tolere')
    return arbitres, jamais_vus, declares


def mesurer(chemins):
    print('=' * 78)
    print('  PROPRETE — mesure du lot')
    print('=' * 78)
    print(f"  {'fichier':<40} {'ruff':<15} {'vulture':<14} locales mortes")
    faute = False
    dette_arb = dette_jam = dette_decl = 0
    for chemin in chemins:
        source_avant = contenu_head(chemin)
        with open(os.path.join(RACINE, chemin), encoding='utf-8') as f:
            source_apres = f.read()
        neuf = source_avant is None

        r_apres = ruff(chemin)
        r_avant = ruff(chemin, source_avant) if not neuf else {}
        v_apres = vulture(chemin)
        v_avant = vulture(chemin, source_avant) if not neuf else 0
        m_apres = locales_mortes(source_apres)
        m_avant = locales_mortes(source_avant) if not neuf else 0

        stricts, toleres = _classer(r_avant, r_apres)
        if stricts or m_apres > m_avant:
            faute = True
        def _etat(avant, apres, neuf=neuf):
            return f'{apres} (neuf)' if neuf else f'{avant} -> {apres}'

        print(f'  {os.path.basename(chemin):<40} '
              f'{_etat(sum(r_avant.values()), sum(r_apres.values())):<15} '
              f'{_etat(v_avant, v_apres):<14} {_etat(m_avant, m_apres)}')
        for code, n in sorted(stricts.items()):
            print(f'      /!\\ {code:<8} +{n}   CODE DE CORRECTION : '
                  f'a corriger')
        for code, n in sorted(toleres.items()):
            print(f'      i   {code:<8} +{n}   preference de style : '
                  f'a DECLARER')
        # /!\ L'ETAT ABSOLU, SUR CHAQUE FICHIER QUI EN PORTE. Le total seul
        # (`31 -> 31`) ne disait pas de quoi il etait fait.
        arb, jam, decl = absolu(r_apres)
        dette_arb += arb
        dette_jam += jam
        dette_decl += decl
        if arb or jam or decl:
            print(f'      ETAT ABSOLU : {arb} arbitres, {jam} jamais '
                  f'examines, {decl} declares')
    print()
    # /!\ TOUJOURS AFFICHE, MEME A ZERO. L'absence d'une ligne ne doit jamais
    # pouvoir se lire comme << je n'ai pas regarde >> — meme lecon que la
    # categorie NON_ETABLI du registre IFRS 17, et que la gate qui rendait
    # << Ran 0 tests >> sans le dire.
    print(f'  DETTE PRE-EXISTANTE DU LOT : {dette_arb} arbitres, '
          f'{dette_jam} jamais examines, {dette_decl} declares.')
    if dette_arb or dette_jam:
        print('  Elle ne fait PAS echouer ce lot : sa fermeture est une '
              'DECISION, a annoncer dans le message.')
    print()
    if faute:
        print('  /!\\ AU MOINS UN ECART SUR UN CODE DE CORRECTION, OU UNE '
              'LOCALE MORTE AJOUTEE.')
    else:
        print('  Aucun ecart sur un code de correction, aucune locale morte '
              'ajoutee.')
    return 1 if faute else 0


def main():
    chemins = sys.argv[1:] or fichiers_du_diff()
    if not chemins:
        print('Aucun fichier Python modifie. Rien a mesurer.')
        return 0
    return mesurer(chemins)


if __name__ == '__main__':
    sys.exit(main())
