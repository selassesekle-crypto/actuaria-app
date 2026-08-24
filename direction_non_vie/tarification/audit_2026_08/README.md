# AUDIT DU MODULE TARIFICATION — août 2026

Sept relevés, **28 560 lignes lues à 100 %**, **141 affirmations mesurées**,
**85 constats** et **55 affirmations vérifiées bonnes**.

> ⚠️ **CES RELEVÉS ONT FAILLI DISPARAÎTRE.** Ils ont été rendus en
> conversation, et la conversation se compacte. Ils sont ici parce qu'un
> constat qui ne survit pas dans le dépôt redevient un soupçon six mois plus
> tard — et que quelqu'un rouvrira ce qui est déjà fermé s'il ne trouve pas la
> marque.

## La posture de l'audit

Ce module a été construit avec soin. La posture était donc : **partir de
l'hypothèse qu'il est bon et prouver le contraire, jamais l'inverse.**

- **Rien ne se signale sans mesure reproductible.** Un soupçon non prouvé se
  dit comme tel, ou ne se dit pas.
- **Ce qui est classé BON est mesuré autant que ce qui est signalé** — 55 des
  141 affirmations sont dans ce cas, et elles comptent.
- **Aucun filtre** : tests, fixtures, docstrings et commentaires compris.
- **Balayage par symbole ET en prose** — l'un ne voit pas ce que l'autre voit.

## Les preuves

`preuves/` porte les **huit scripts de mesure** utilisés. Chacun se relance
seul. ⚠️ **Ce sont des scripts d'archive**, écrits un jour donné pour établir
un fait : ils ne sont pas maintenus, et ils portent **83 écarts `ruff`
déclarés comme tels** — la CI ne lint pas, ils ne font échouer aucune gate.

⚠️⚠️ **ILS MESURENT L'ÉTAT ACTUEL, PAS CELUI DU JOUR DE L'AUDIT — et c'est ce
qui en fait aussi des contrôles de non-régression.** Leurs **libellés**
décrivent le constat tel qu'il était ; leurs **chiffres** sont recalculés à
chaque exécution. Exemple mesuré : `audit_a1.py::M2b` porte encore l'étiquette
« le résultat dépend de l'ORDRE des colonnes » et affiche désormais
`nb_doublons=0` — parce que `35dac12` a fermé A1/C1. **Lire le chiffre, pas
l'étiquette** : l'étiquette est l'histoire, le chiffre est le présent.

### Deux propriétés vérifiées en constituant cette archive

**① Le déterminisme.** Deux exécutions successives, hors horodatages de log :
**8 scripts sur 8 rendent des mesures identiques.** Le seul écart apparent
était `audit_services::U1`, qui varie sur l'horodatage **qu'il mesure** — et
c'est précisément son constat : *« Arrêté : publie l'horodatage de
génération »*. **Sa variation EST sa preuve.**

**② Une preuve qui ne s'exécute plus est la preuve d'une fermeture.**
`audit_a4::q2` mesurait `_optimisation_tarifaire`. Le lot L0 a supprimé cette
méthode ; le script rend donc désormais :

```
  [NON MESURE] Q2   AttributeError: 'AgentA4ML' object has no attribute
                    '_optimisation_tarifaire'
```

⚠️ **Ce n'est pas une panne de l'archive, c'est son verdict** : le symbole
mesuré n'existe plus, donc le constat A4/C1 est bien fermé. Un `[NON MESURE]`
sur un constat marqué OUVERT, en revanche, serait à instruire.

⚠️ **Le nettoyage de propreté a été fait sous vérification** : les 25 écarts
`ruff` sont déclarés en tête de fichier (`# ruff: noqa`, avec le motif), les
13 locales mortes ont été retirées, et **les 8 sorties ont été comparées avant
et après — identiques**. Une pièce à conviction ne se réécrit pas à l'aveugle.

| script | ce qu'il établit |
|---|---|
| `audit_a1.py` · `audit_a1_bis.py` | les 12 mesures d'A1, le vocabulaire réel des 261 noms, l'audit trail |
| `audit_a2.py` | les 12 causes de plafond d'A2, plantées une par une |
| `audit_a3.py` | les 5 hypothèses GLM, l'offset Tweedie, les seuils |
| `audit_a4.py` | le monitoring, les deux validations, le classement |
| `audit_a5.py` | les trois hypothèses DL, les courbes, l'early stopping |
| `audit_a6.py` | l'A/E, les segments, le verrou de décision |
| `audit_services.py` | les trois formats de livrable, les mentions publiées |

---

## ⚠️ L'ÉTAT DES 85 CONSTATS

**La règle est stricte : un constat n'est FERMÉ que si un CONTRÔLE POSITIF
l'épingle.** Un code corrigé sans contrôle peut régresser sans un mot — c'est
un troisième état, et il se distingue.

| état | compte | ce que ça veut dire |
|---|---|---|
| ✅ **FERMÉ** | **17** | corrigé **et** épinglé par un contrôle positif nommé |
| ⚠️ **CORRIGÉ, NON ÉPINGLÉ** | **1** | le code a changé, **rien n'empêche la régression** |
| ⛔ **OUVERT** | **67** | ni corrigé ni épinglé |

### Les 17 fermés

| relevé | constat | contrôle | commit |
|---|---|---|---|
| A1 | **C1** doublons comptés sur une colonne qui n'est pas un identifiant | `POS-A1a` `POS-A1b` `POS-A1c` `POS-A1d` | `35dac12` |
| A2 | **C1** « Winsorisées : 0 variable(s) » alors que 9 l'ont été | `POS-A2b` | `6bc3efe` |
| A2 | **C2** « 5 colonnes non encodées » — les 5 sont encodées, et ça plafonne le statut | `POS-A2a` | `6bc3efe` |
| A3 | **C1** le Tweedie est ajusté SANS offset et prédit AVEC | `POS-A3d` | `ff8a49e` |
| A3 | **C2** H1 rend VERT sur des valeurs codées en dur | `POS-A3a` | `ff8a49e` |
| A3 | **C3** H4 « non testée » vaut VERT | `POS-A3b` | `ff8a49e` |
| A3 | **C8** H3 : le seuil annoncé n'est pas le seuil appliqué | `POS-A3c` | `ff8a49e` |
| A4 | **C1** le « tarif optimal » est une constante : −20 %, toujours | `POS-A4e` `POS-A4f` `POS-A4g` `POS-A4h` | `02bedb9` puis `0bc33d6` |
| A4 | **C2** le monitoring de dérive est intégralement simulé | `POS-A4a` | `98dba85` |
| A4 | **C3** le graphique d'overfitting affiche un Gini test nul | `POS-A4c` | `98dba85` |
| A4 | **C4** deux validations contradictoires dans le même retour | `POS-A4b` | `98dba85` |
| A4 | **C11** la clé `gini` n'existe pas dans le classement | `POS-A4c` | `98dba85` |
| A5 | **C1** les trois hypothèses DL sont ROUGE sur un CANN excellent | `POS-A5a` | `1b296ce` |
| A5 | **C2** H1 « Convergence » ne mesure pas la convergence, elle la fabrique | `POS-A5b` | `1b296ce` |
| A5 | **C3** les courbes d'apprentissage sont trois lignes à zéro | `POS-A5c` | `1b296ce` |
| A6 | **C1** le « Test A/E » ne compare pas l'observé à l'attendu | `POS-A6c` `POS-A6d` | `e8182b2` |
| A6 | **C2** le A/E par segment déclare ROUGE 11 segments sur 12 | `POS-A6e` `POS-A6f` | `e8182b2` |
| A6 | **C4** les graphiques de validation lisent une clé qui n'existe pas | `POS-A6a` `POS-A6b` | `1b296ce` |

### Le corrigé non épinglé

| relevé | constat | état |
|---|---|---|
| A5 | **C5** le graphique « DL vs GLM » met les deux modèles DL à zéro | la figure lit désormais `gini_test` (corrigé par `1b296ce`, dans la même passe que C1), mais **aucun contrôle ne l'épingle**. Une régression passerait. |

### Les deux affirmations non mesurables au relevé, tranchées depuis

| sujet | ce qui a été établi | commit |
|---|---|---|
| `Code de la route Art. R.221-1` | **Vérifié au texte.** R. 221-1 ne porte AUCUNE condition d'âge. Les âges sont à **R. 221-5** : 16 ans (A1, B1), **17 ans (catégorie B)**, 18/21/24. ⚠️ **Aucun texte ne fixe d'âge maximal** — le 99 est une convention du module. | `6bc3efe` |
| `Commission Tarification IA France (2019)` | **Purgée, 20 sites** — pas 12 : la forme courte « IA France §4.2 » échappait au premier relevé. Le § variait selon le fichier (§3.2.4, §3.2.5, §4.2) sous le même titre. Trois sites étaient dans l'Excel qui part au commissaire, dont une **citation entre guillemets**. | les cinq premiers commits |

---

## ⚠️⚠️ DÉCISION — LES 67 OUVERTS SERONT TOUS TRAITÉS

**Aucun ne sera abandonné, y compris ceux qu'un lecteur classerait comme du
bruit.** Ni maintenant, ni dans l'ordre de gravité — mais tous.

> **Ceci n'est PAS une dette assumée.** C'est une file d'attente. Quiconque lit
> cette liste dans six mois doit le savoir : un constat resté ouvert n'a pas
> été jugé négligeable, il n'a pas encore eu son tour.

**Le bruit documentaire se traitera EN LOTS GROUPÉS** — vingt en-têtes périmés
dans un passage plutôt que vingt lots.

### Les regroupements naturels, mesurés

| lot groupé | constats | pourquoi ils vont ensemble |
|---|---|---|
| **En-têtes de test périmés** | `a1/C10` `a2/C14` `a3/C18` `a4/C13` `a5/C9` `a6/C10` | six fichiers annoncent « 7 tests » et en portent 9, ?, 4, 11, 3, ? — **même défaut, même correction** |
| **Symboles jamais lus** | `a1/C9` `a2/C7` `a2/C8` `a3/C11` `a3/C13` `a6/C9` | `verifier_tous_fichiers`, `STRATEGIES_IMPUTATION`, `VARS_GLM`, `durbin_watson`, `INTERPRETABILITE` — du mort qui se retire d'un geste |
| **En-têtes de module annonçant l'absent** | `a2/C3` `a2/C4` `a4/C6` `a4/C7` `services/C3` | WoE, Target Encoding, Winsorisation IQR, « ML ×8 » (12 mentions, 6 modèles), « 8 modèles » republié dans trois livrables |
| **`COLS_A_EXCLURE`** | `a3/C16` `a4/C12` `a5/C8` | le même symbole dans trois agents |
| **Scorecards « 3 ✅ = validé »** | `a3/C9` `a4/C8` | annoncent 3, listent 4, et 5 hypothèses sont calculées |
| **Figures qui n'affichent pas ce qu'elles nomment** | `a3/C5` `a4/C5` `a6/C3` | Lorenz tracée et non mesurée (×2), « Score par profil » qui n'affiche pas le score |
| **`filterwarnings('ignore')` au niveau module** | `a1/C6` `a2/C15` | **tout le process** devient muet, pas seulement l'agent |
| **Écriture disque à l'instanciation** | `a1/C7` `a2/C16` | `/tmp/actuaria` créé par un simple `__init__` |
| **Exemples d'usage périmés** | `a2/C10` `a3/C17` | l'en-tête montre un appel qui ne marche plus |

**Environ 30 constats en 9 passages.** Les ~37 autres sont substantiels et
demandent un traitement propre — parmi eux, ceux à ouvrir en premier sont
signalés plus bas.

⚠️ **CETTE TABLE A ÉTÉ CONSTRUITE PAR EXPRESSION RÉGULIÈRE, ET ELLE A MANQUÉ
DEUX CONSTATS SUR 67** (dont `a1/C8`, dont le gras est imbriqué). C'est la
leçon du relevé par symbole, appliquée à l'outil qui indexe l'audit :
**la liste qui fait foi est dans les sept relevés, pas dans cette table.**

## ⛔ LES 67 OUVERTS

Ils sont **dans les relevés, avec leur mesure**. Ce qui suit n'est qu'un index
— *la preuve est dans le relevé, pas ici.*

| relevé | ouverts |
|---|---|
| [A1](releve_a1_ingestion.md) | C2 périmètre · C3 `prime_pure > 0` · C4 double verdict sur `exposition = 0` · C5 doublons de synonymes · C6 `filterwarnings` global · C7 écriture disque à l'instanciation · C8 audit trail perdu en silence · C9 fonction morte · C10 en-tête de test |
| [A2](releve_a2_preprocessing.md) | C3 à C16 — WoE/Target Encoding annoncés, Winsorisation IQR annoncée, `STRATEGIES_IMPUTATION` jamais lu, une moyenne sous la clé `medianes`, … |
| [A3](releve_a3_glm.md) | C4 IC 95 % faux · C5 Lorenz tracée non mesurée · C6 Gini Tweedie nul · C7 Gini incomparables · C9 scorecard · C10 « 3 modèles », 2 lus · C11 `VARS_GLM` · C12 `0.05` en dur · C13 figure jamais produite · C14 p-value fabriquée · C15 repli cassé · C16 · C17 · C18 |
| [A4](releve_a4_ml.md) | C5 Lorenz · C6 « 6/8 » · C7 « ML ×8 » (12 mentions, 6 modèles) · C8 scorecard · C9 ROUGE inatteignable · C10 deux bases de rang · C12 · C13 |
| [A5](releve_a5_deep_learning.md) | C4 « Convergence » exponentielle analytique · **C6 early stopping réglé sur le jeu de TEST** · **C7 aucun seed : non reproductible** · C8 · C9 |
| [A6](releve_a6_comparaison.md) | C3 « Score par profil » n'affiche pas le score · C5 conformité affirmée sans condition · C6 chaîne muette · C7 « 3 meilleurs modèles » non utilisés · C8 plafond de vraisemblance · C9 · C10 |
| [services](releve_services_rapport.md) | C1 « Arrêté : » publie l'horodatage · C2 référence Wüthrich · C3 « 8 modèles » dans trois livrables · C4 `h5_deviance` absente du tableau · C5 · C6 · C7 · C8 · C9 |

⚠️ **Deux ouverts d'A5 méritent d'être lus en premier** : `C6` (l'early
stopping se règle sur le jeu de TEST — c'est une fuite) et `C7` (aucun seed
n'est fixé : le modèle n'est pas reproductible d'un run à l'autre).

---

## ② LE RELEVÉ DU CHEMIN DÉCLARATIF — en cours

| fichier | lignes | état | constats |
|---|---|---|---|
| [`pipeline_tarifaire.py`](releve_pipeline_tarifaire.md) | 343 | ✅ **RELEVÉ** | **9** · 10 vérifiées bonnes |
| [`core/conformite_reglementaire.py`](releve_conformite_reglementaire.md) | 1 318 | ✅ **RELEVÉ** | **13** · 14 vérifiées bonnes |
| `core/plan_tarifaire.py` | 486 | ⛔ à lire | la source unique |
| `core/charts_tarif.py` | 476 | ⛔ à lire | les figures publiées |
| `core/qualite_donnees.py` | 334 | ⛔ à lire | les 4 règles |
| `pipeline_agents.py` | 317 | ⛔ à lire | l'orchestrateur |
| `mapping_client` · `mapping_llm` · `severite` · `derivations` | 609 | ⛔ à lire | |

⚠️⚠️ **LE CONSTAT LE PLUS GRAVE DU PREMIER RELEVÉ** : `tarifer()` accepte un
facteur tarifaire écrit **en toutes lettres** et rend un prix en disant
`success: True`. Mesuré — `bonus_malus = 'beaucoup'` → prime **+128 %** ;
`-999` → **−19,4 %** ; `1e12` → **+425,6 %**. **Aucune borne de plausibilité
n'existe sur le chemin déclaratif** : A1 en porte, mais ce chemin ne passe pas
par A1 et son propre commentaire l'assume.

⚠️ **Et ce fichier est par ailleurs le meilleur du module sur ce qui décide** —
équilibre technique à **1,0000**, fréquence exactement par unité d'exposition,
filtre genre qui tient, couche qualité qui bloque vraiment, ajustement
reproductible **au bit près**.

⚠️⚠️ **LES DEUX CONSTATS GRAVES DU DEUXIÈME RELEVÉ** — et ils ont la forme même
que ce fichier combat depuis sept cycles d'audit :

- **`controle_effet_execute` atteste sans surveiller.** La propriété dit
  « exécuté » alors que le contrôle n'a examiné **aucune colonne** : cible
  absente de `df`, ou cible constante → `detecter_fuites_par_effet` rend `{}`
  **sans un mot**, la fuite entre dans la matrice X, et aucun WARNING n'est
  émis. Le module nomme lui-même ce défaut deux fois (bug V6, BLOQUANT B2).
- **Une variable de TAILLE est écartée comme « la cible déguisée ».**
  `effectif` et `nb_salaries` sont déclarés légitimes et ne portent aucun
  marqueur de passé : rien ne les protège. Bascule mesurée **à partir de ~6
  sinistres/an/contrat** (0,7875 à 4/an — la flotte que le module cite —
  **0,8332 à 6/an**). Le rapport conclut alors « *Exclusion obligatoire, aucune
  action* » : c'est le texte même que B7 a jugé **pire que le silence**.

⚠️ **Un point est RENDU À L'ARBITRAGE, non tranché** : le module affirme que le
genre est interdit en tarification **pour toute branche**, et
`v1_tarification_deces` sélectionne la table de mortalité **par le sexe**
(`TH0002`/`TF0002`). Table sexuée licite en provisionnement et IAS 19, ou
manquement Test-Achats ? **Point de méthode, pas point de code.**

⚠️ **Ce fichier écrit mieux ses limites qu'aucun autre** : il nomme les **11
fuites qui lui échappent** — vérifié, elles échappent toujours — et il dit que
son jeton rend le contournement *délibéré*, pas impossible. C'est ce qui rend
les deux constats ci-dessus notables : ce sont les deux endroits où **il a écrit
la règle et ne l'a pas tenue sur lui-même**.

## ⚠️ CE QUI N'A JAMAIS ÉTÉ AUDITÉ — et qui tarife

Les sept relevés couvrent **19 150 lignes** : A1→A6 et les services de
rapport. **3 883 lignes n'ont jamais été lues**, et ce sont celles qui
comptent :

| lignes | fichier | ce qu'il porte |
|---|---|---|
| 1 318 | `core/conformite_reglementaire.py` | **les garde-fous** : genre, fuite, antériorité |
| 486 | `core/plan_tarifaire.py` | la source unique |
| 476 | `core/charts_tarif.py` | les figures publiées |
| 343 | `pipeline_tarifaire.py` | **le calcul du prix** |
| 334 | `core/qualite_donnees.py` | les 4 règles qualité |
| 317 | `pipeline_agents.py` | l'orchestrateur |
| 199 + 220 + 130 + 60 | `mapping_llm` · `mapping_client` · `severite` · `derivations` | |

⚠️⚠️ **ILS SONT TESTÉS, PAS AUDITÉS.** `test_plan_invariants.py` porte
60 tests, `test_invariants.py` 47. Mais **les 85 constats ci-dessus ont été
trouvés dans du code qui était testé aussi.** « Testé » n'a jamais voulu dire
« audité ».

À raison d'un constat toutes les 225 lignes sur la partie auditée, **une
quinzaine de constats y est attendue.**
