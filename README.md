# ActuarIA

Chaîne actuarielle Non-Vie — tarification (A1→A6), provisionnement (A7),
réglementation (A10→A14). Les documents que la chaîne produit sont
**signés par un actuaire** et lus par un commissaire aux comptes et par
l'ACPR : chaque chiffre publié y porte son origine, et chaque absence s'y
déclare.

## ⚠️ LANCER LES TESTS — LA SORTIE DOIT ÊTRE EN UTF-8

```bash
PYTHONUTF8=1 py -B -m unittest discover -s direction_non_vie/tarification -t .
```

Sur Windows en français, la console par défaut est en **cp1252**, et les
messages des contrôles portent des caractères qu'elle ne sait pas écrire
(`⚠`, `→`, `é` dans certains contextes). Sans `PYTHONUTF8=1`, Python lève
alors `UnicodeEncodeError` **au moment d'afficher**, et le harnais rend
des erreurs qui n'en sont pas : le calcul était juste, c'est l'affichage
qui a échoué.

Mesure du 13/09/2026 : **32 fichiers de test et 418 sites de `print`** du
périmètre tarification + core portent au moins un caractère non
représentable en cp1252.

*Un développeur qui lit dix erreurs qui n'en sont pas cesse de croire le
harnais — c'est le coût réel de ce défaut d'accueil.*

### Ce qui est déjà protégé, et ne demande rien

- **La chaîne de production.** `core/sortie_console.afficher_sans_echouer`
  existe pour cela et est appelé dans les **six agents A1→A6** : sur la
  même console, un agent qui affiche un caractère non représentable écrit
  un substitut et **continue**. Sans lui, A3 basculait de
  `success=True / VERT` à `success=False / ROUGE` — un défaut d'affichage
  qui changeait un verdict.
- **La gate officielle.** `scripts/gate.py` pose `PYTHONUTF8=1` et
  `PYTHONIOENCODING` lui-même : `py -B scripts/gate.py <zone>` est immune,
  quelle que soit la console qui la lance.

L'exposition résiduelle est donc étroite et connue : **lancer `unittest`
à la main sans la variable**. C'est ce que cette page ferme.

> ⚠️ Ces trois faits ne sont pas affirmés ici : ils sont **mesurés** par
> `direction_non_vie/tarification/test_console_qui_ne_ment_pas.py`, qui
> relance un processus enfant à sortie cp1252 et regarde ce qui se passe.
> Si l'un d'eux cessait d'être vrai, ce contrôle rougirait — et cette page
> serait à relire.

## La gate

```bash
py -B scripts/gate.py direction_non_vie/tarification --sortie gate.txt
```

⚠️ **Le verdict se lit DANS LE FICHIER, jamais au code de sortie** : on
cherche la **dernière** ligne `Ran N tests in …`, on ne lit que ce qui la
suit, et on n'accepte qu'une ligne nue `OK` ou `FAILED`. Les `print` des
contrôles arrivent **après** le verdict et ressemblent à des verdicts.

## Propreté

```bash
py -B scripts/proprete.py
```

Jamais `ruff` nu : `scripts/proprete.py` mesure l'**écart** introduit par
le lot en cours, distingue les codes à corriger de la dette arbitrée, et
c'est cet écart qui doit être nul.
