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
