# EXIGENCES DE MIGRATION — ce que la nouvelle application doit respecter dès sa conception

**Arbitré par Selasse Sekle le 25/08/2026.** Ce document n'ordonne aucun lot et
ne décrit aucun correctif à appliquer à l'application actuelle.

⚠️⚠️ **CE DOCUMENT NE S'EXÉCUTE PAS, IL CONTRAINT.** La feuille de route
([`FEUILLE_DE_ROUTE.md`](FEUILLE_DE_ROUTE.md)) ordonne le travail sur le code
qui existe. Celui-ci fixe ce que le code qui n'existe pas encore devra tenir.
*Deux documents qui ordonneraient la même chose seraient le défaut que cet
audit poursuit.*

⚠️⚠️ **NE PAS TOUCHER À L'APPLICATION STREAMLIT ACTUELLE SUR CES SUJETS.**
Arbitrage explicite de Selasse : elle disparaît à la migration, et y écrire
même une phrase courte n'est pas utile. **Ma recommandation d'y afficher un
avertissement a été écartée, et c'est la bonne décision** : investir dans une
interface condamnée, c'est payer deux fois pour une exigence qui doit vivre
dans la suivante.

---

## M1 — DEUX MODES, JAMAIS TROIS BOUTONS ISOLÉS

**Ce que le client doit voir : LA PRIME SÉLECTIONNÉE parmi plusieurs méthodes,
avec le pourquoi.** Et l'actuaire garde le choix : l'arbitrage complet n'est pas
imposé à chaque fois.

L'application se conçoit donc autour de **deux modes**, et de deux seulement :

| mode | ce qui tourne | ce que l'écran montre |
|---|---|---|
| **rapide** | une seule méthode, choisie par l'actuaire | le résultat — **et TOUJOURS « résultat non comparé, activer l'arbitrage complet ? »** |
| **complet** | toutes les méthodes, puis l'arbitrage | **la prime retenue, et POURQUOI elle est retenue** |

### ⚠️⚠️ RÈGLE NON NÉGOCIABLE

> **L'absence de comparaison ne doit JAMAIS être invisible ou silencieuse.**
> Le mode rapide est un choix assumé par l'actuaire, jamais un défaut caché.

### Ce que l'état actuel apprend à la migration

Mesuré le 25/08/2026 sur `actuaria_app.py` — **à titre de contre-exemple, pas
de correctif** :

```
  besoin == 'prime_glm'   ->  A3 + pipeline_complet
  besoin == 'prime_ml'    ->  A4 SEUL
  besoin == 'prime_dl'    ->  A5 SEUL
  besoin == 'selection'   ->  A3 + A6   <- l'arbitrage
```

**Quatre entrées de menu au même niveau, dont trois produisent un prix sans
comparaison — et l'arbitrage est la quatrième.** Qui ne choisit pas `selection`
obtient un prix d'une seule famille de modèles **sans jamais rien voir
manquer**. *L'arbitrage n'était pas contourné : il était FACULTATIF.* C'est
précisément ce que M1 interdit.

⚠️ **Et la clé `resultats["principal"]` ne distinguait rien** : mesurée à **36
écritures**, c'est le slot générique de chaque page. *Un audit antérieur avait
lu cette étiquette au lieu de mesurer qui écrit dedans.*

### ⚠️⚠️ M1-bis — L'ASSIETTE DE L'AVERTISSEMENT EST L'OBJET RÉSULTAT, PAS L'ÉCRAN

**Arbitré par Selasse le 25/08/2026, retenu sans réserve** : *« un contrôleur
lit le document, pas l'écran »*.

**Un message d'écran n'est pas une propriété du résultat.** La question que cet
audit pose à tout garde-fou est **« sur quelle ASSIETTE ? »**. Si l'assiette de
l'avertissement est l'écran, alors **tout ce qui sort de l'écran en est
exempt** : l'export PDF, le rapport d'équipe, la piste d'audit, et tout agent
en aval qui relit le résultat.

> **EXIGENCE : l'absence de comparaison est portée par L'OBJET RÉSULTAT
> lui-même**, pas seulement affichée. Un résultat non comparé doit être
> *structurellement* reconnaissable, **de sorte qu'un livrable sans cette
> mention devienne IMPOSSIBLE À PRODUIRE** — et non pas seulement déconseillé.

**Ce que cela veut dire concrètement, pour que la conception ne puisse pas s'en
échapper** :

| ce qui est exigé | ce qui ne suffit PAS |
|---|---|
| l'état « comparé / non comparé » est un **champ du résultat**, renseigné à la production | un `st.warning()`, une bannière, un texte d'écran |
| **tout producteur de livrable lit ce champ** — PDF, rapport d'équipe, piste d'audit, API | « le gabarit PDF affiche la mention » |
| un livrable produit à partir d'un résultat non comparé **et qui ne porte pas la mention doit échouer**, pas se dégrader en silence | un défaut à `comparé` quand le champ est absent |
| l'état est **non falsifiable par omission** : absent ⇒ traité comme non comparé | l'absence de champ traitée comme « ancien format, on laisse passer » |

*Un avertissement dont l'assiette est l'écran est un contrôle qui atteste sans
surveiller.* ⚠️ **Et un défaut permissif sur ce champ rouvrirait exactement le
trou que M1 ferme** — c'est le même raisonnement qui a fait rendre `X_val`
obligatoire dans A5 au lot 1.1 : *un défaut que personne n'utilise et qui
contredit la méthode est un piège, pas une commodité.*

---

## M2 — LE TEMPS : À MESURER, PAS À DEVINER

⚠️ **Avant que la migration ne conçoive quoi que ce soit** : où va le temps
aujourd'hui, **méthode par méthode** ? Cette mesure n'a pas été faite et
**n'est pas au périmètre du lot 1.1** — elle est inscrite ici comme préalable.

### Les trois pistes, dans l'ordre de préférence arbitré

| # | piste | pourquoi elle est préférée |
|---|---|---|
| **①** | faire tourner les méthodes **EN PARALLÈLE** plutôt qu'en série | souvent le gain le plus large, pour le moins de risque |
| **②** | mesurer si chaque méthode **refait des calculs inutiles** en interne | le genre de gaspillage déjà trouvé sur les figures |
| **③** | **réutiliser ce qui a déjà été calculé** sur une relance | — |

### ⚠️⚠️ CE QUI EST EXCLU, SANS DISCUSSION

> **Réduire la précision d'un modèle pour aller plus vite est EXCLU.** C'est le
> genre d'arbitrage qui a produit les défauts que cet audit a trouvés.

### ⚠️ CE QUE J'AI MESURÉ, ET QUI BORNE LA PISTE ① AVANT MÊME DE COMMENCER

Relevé **par AST** (`ast.parse`, signatures de `run` + lectures réelles des
noms dans le corps), le 25/08/2026 :

```
  A1  -> aucun resultat d agent
  A2  -> A1
  A3  -> A2
  A4  -> A2, A3
  A5  -> A2, A3, A4
  A6  -> A1, A2, A3, A4, A5
```

Toutes ces dépendances sont **optionnelles** (défaut `None`) **et réellement
lues** — aucune n'est un paramètre décoratif.

**Le graphe déclaré est donc une CHAÎNE STRICTE : il n'y a rien à
paralléliser.** Mais la nature des dépendances n'est pas la même, et c'est là
que se trouve la marge :

| dépendance | ce qu'elle sert | bloque le parallélisme ? |
|---|---|---|
| **A5 ← A3** | **CALIBRATION** — le CANN est *ancré* sur le GLM gelé (Wüthrich & Merz 2019) | **OUI, irréductible** |
| **A5 ← A4** | **RESTITUTION seule** — `_classer_modeles`, `_generer_graphiques`, `_commenter_actuaire_senior` | **NON — déplaçable** |

⚠️⚠️ **A5 CLASSE LES MODÈLES CONTRE A4 À L'INTÉRIEUR DE LUI-MÊME — c'est-à-dire
qu'il refait le travail d'A6.** Deux classements peuvent diverger. Sortir la
comparaison d'A5 rend **A4 ∥ A5 possible après A3**, et supprime du même geste
une comparaison faite à deux endroits.

**Mais le gain est plafonné, et il faut le dire avant de s'y engager.** Durées
**DÉCLARÉES** par l'application (`actuaria_app.py` — *déclarées, jamais
mesurées ; cet audit a trouvé plusieurs fois l'écart entre les deux*) :

```
  prime_glm  ~15 sec      prime_ml  ~45 sec      prime_dl  ~3-5 min
```

Si ces ordres de grandeur se confirment, **le chemin critique est
A1→A2→A3→A5, et A5 le domine seul.** Paralléliser A4 avec A5 économise au
mieux la durée d'A4 — **environ 45 s sur 4 à 6 minutes**.

> **CONTESTATION RETENUE PAR SELASSE LE 25/08/2026 :** ① est la piste la plus
> sûre, mais probablement **la moins rentable des trois ici**, parce que le
> temps n'est pas réparti — il est concentré dans A5.
> ⚠️⚠️ **L'ORDRE DE PRÉFÉRENCE ①②③ SE RE-ARBITRE APRÈS LA MESURE, PAS AVANT —
> et cette exigence-là ne se lève pas.** C'est ce que l'exigence demande
> elle-même : *mesurer, pas deviner.* Les durées ci-dessus sont **déclarées et
> ne doivent pas être prises pour acquises** ; seule **la structure** a été
> mesurée (par AST), pas les temps.

⚠️ **Et une piste ④ que la mesure fera probablement apparaître d'elle-même** :
si A5 domine, la question utile n'est plus « comment paralléliser les
méthodes » mais **« où va le temps À L'INTÉRIEUR d'A5 »** — ce qui est la piste
② appliquée au seul endroit où elle rapporte. *À vérifier par la mesure, pas à
décider ici.*

---

## Ce que ce document ne dit pas

- Il ne dit **pas** quelle méthode l'arbitrage doit retenir — c'est A6, et A6 a
  ses propres constats ouverts (voir [`releve_a6_comparaison.md`](releve_a6_comparaison.md)).
- Il ne dit **pas** comment l'interface se construit — il dit ce qu'elle ne
  peut pas taire.
- Il ne mesure **pas** les durées : il mesure le graphe qui les contraint.
