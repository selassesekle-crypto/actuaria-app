# RE-MESURE DES 40 CONSTATS AU CODE D'AUJOURD'HUI

**25/08/2026.** Ce document remplace le classement établi sur les relevés :
**il mesure le code, pas ce que le relevé disait.**

---

## ⚠️⚠️ POURQUOI CETTE RE-MESURE, ET CE QU'ELLE A COÛTÉ DE NE PAS L'AVOIR FAITE

Sur les cinq constats du lot « hypothèses VERT sans test », **quatre étaient
déjà fermés** — corrigés dans le code, jamais reportés. Je les avais classés
« vivants » sur la foi du relevé. *L'archive prévient elle-même : « ils mesurent
l'état ACTUEL, pas celui du jour de l'audit — lire le chiffre, pas
l'étiquette ».*

⚠️⚠️ **ET LA RE-MESURE ELLE-MÊME A FAILLI MENTIR.** Un premier passage par
sondes `regex` a rendu **deux faux « fermés »** :

```
  a3/C5  sonde: t ** (1 / (1 + 2 * g))   -> "plus present"   FAUX
  reel : t ** (1 / (1 + gini * 2))       -> a3:2193, a4:2069  ENCORE LA
```

*Une absence de `grep` n'est pas une absence de défaut.* **Chaque « fermé » de
ce document a donc été confirmé par une SECONDE méthode** — exécution, lecture
du site, ou test. Ceux qui ne l'ont pas été sont marqués **à lire**, jamais
« fermés ».

---

## FERMÉS — confirmés par deux méthodes

| constat | ce qui l'établit |
|---|---|
| `a3/C1` | **le Tweedie ne prédit plus AVEC offset** — le correctif est complet (fit *et* predict), commenté l.1473-1483. *C'était le seul constat que j'avais désigné comme déplaçant un euro.* |
| `a3/C2` | H1 sans fréquence → **AMBRE**, `ratio_disp = None` (exécution) |
| `a3/C3` | H4 par défaut → **AMBRE**, `cv_max = None` (exécution) |
| `a3/C8` | `0.12 → AMBRE`, 4 bandes cohérentes (exécution sur 5 bornes) |
| `a3/C9` `a3/C10` | scorecard dérivée · docstring alignée (lot du 25/08, testés) |
| `a4/C1` | `_optimisation_tarifaire` **absent du module** (lot L0) |
| `a4/C4` | `validation_ml` ≡ `hypotheses` sur toutes les clés (exécution) |
| `a4/C6` `a4/C8` `a4/C9` | dénominateur dérivé · légende dérivée · seuil nommé (lot du 25/08, testés) |
| `a5/C1` | la cause nommée — `.get('gini', 0)` — est fermée : le code lit `gini_test`. ⚠️ **Le symptôme d'origine reste à instruire** (voir plus bas) |
| `a5/C2` | H1 **ne simule plus** : elle lit `historiques.get(...)`, l'historique réel (l.2004-2014) |
| `a5/C6` `a5/C7` | lot 1.1, testés |
| `a3/C6` | **`b0ae396`** — le Tweedie calcule son Gini (mesuré **−0,078**, négatif : *le zéro fabriqué était flatteur*). Un Gini non mesurable vaut `None`, jamais `0`, et A6 l'écarte en le déclarant. Épinglé par `test_gini_tweedie_arbitrage.py` (8 contrôles) |
| `a4/C2` | **`16c6566`** — zéro `np.random.*` dans A4 (AST) ; PSI de `_psi_reel` sur features réelles, **mesuré par exécution : 0,056 sur deux portefeuilles proches contre 7,59 sur deux éloignés**. Épinglé par `test_monitoring_derive_reel.py` (6 contrôles) |

**17 fermés sur 40** — 15 au 25/08, plus `a3/C6` et `a4/C2` le 26/08.

⚠️⚠️ **CES DEUX LIGNES ONT ÉTÉ AJOUTÉES LE 27/08, APRÈS COUP.** Elles étaient
restées dans la table OUVERTS pendant que le code était corrigé et épinglé —
*un pointeur qui survit à sa correction*, exactement le défaut que `a4/C2`
fermait. **Une fermeture se reporte ICI dans le même lot que le correctif.**

---

## OUVERTS — confirmés au code

| constat | mesure |
|---|---|
| `a3/C5` · `a4/C5` | **`lorenz = t ** (1 / (1 + gini * 2))`** — a3:2193, a4:2069. La courbe est **analytique, pas mesurée** |
| `a3/C11` | `VARS_GLM` encore mentionné |
| `a3/C12` | `< 0.05` codé en dur |
| `a3/C13` | `dw_stat` toujours lu |
| `a3/C14` | p-value fabriquée à `1.0` |
| `a3/C17` | `run(result_a2)` encore dans les exemples |
| `a4/C3` · `a4/C11` | `.get('gini', ...)` au lieu de `gini_test` |
| `a4/C7` | `RandomForest` / `GAM` / `RégQuantile` annoncés, absents des boucles |
| `a5/C3` · `a5/C4` · `a5/C5` | courbes lisant `loss_train`/`loss_val` · bruit non semé · `.get('gini', 0)` |
| `a3/C18` `a4/C13` `a5/C9` | en-têtes de test : annoncent **7**, comptent **8 · 18 · 12** |
| `a3/C16` `a4/C12` `a5/C8` | `COLS_A_EXCLURE` : **3** entrées Vie/Santé sur 23·22·20. ⚠️ *Le relevé disait 5 — partiellement réduit, pas fermé* |

**19 ouverts.**

---

## ⚠️ À LIRE — la sonde ne décide pas

| constat | pourquoi la sonde échoue |
|---|---|
| `a3/C4` | l'IC vient de `conf_int()` de statsmodels, pas d'un `1.96` — le constat porte sur **l'infobulle**, pas sur le calcul |
| `a3/C7` | « deux Gini incomparables » : une comparaison de sens, pas de symbole |
| `a3/C15` | le motif `np.full(...).values` n'est plus trouvé — **non confirmé par une seconde méthode** |
| `a4/C10` | « deux bases de rang » : demande de comparer ce qu'A3 et A4 classent, pas un motif |

**4 à lire.**

---

## ⚠️⚠️ CE QUE CETTE RE-MESURE CHANGE POUR L'ORDRE

**`a3/C1` était mon prochain lot** — le seul « qui déplace un euro ». **Il est
fermé.** Aucun des 19 ouverts n'a de chiffre d'impact tarifaire mesuré à ce
jour.

⚠️ **Les 19 ouverts se regroupent en trois familles**, et deux d'entre elles
demandent des outils que le banc n'a pas :

1. **les FIGURES** (`a3/C5` `C13` · `a4/C3` `C5` · `a5/C3` `C4` `C5`) — 7
   constats. *Un troisième banc, non proposé à ce jour.*
2. **les VALEURS lues sous la mauvaise clé** (`a4/C3` · `a4/C11`) — mesurables
   par exécution. ⚠️ `a3/C6` en sortait : fermé le 26/08 (`b0ae396`).
3. **l'hygiène et les en-têtes** (`a3/C11` `C12` `C14` `C16` `C17` `C18` ·
   `a4/C7` `C12` `C13` · `a5/C8` `C9`) — lecture directe, aucun livrable en jeu.

**Et `a4/C2`** — le monitoring simulé — était le seul dont le banc avait mesuré
qu'il **n'atteint aucun livrable**. ⚠️ **Fermé le 26/08 (`16c6566`)** : il ne
simulait plus depuis six semaines, mais un motif d'exclusion l'accusait encore.
*Le latent qui restait n'était pas le défaut — c'était son étiquette.*
