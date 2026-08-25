# RELEVÉ A3 — TARIFICATION GLM

**Lu intégralement** : `a3_glm/agent.py` **3 214 l** + `test_a3_glm.py` **425 l**.

## ① Le compte

**24 affirmations mesurées** — 18 constats · 6 vérifiées bonnes.

## ② Le classement

### A — Publie du FAUX à un actuaire qui signe (7)

**C1 — Le Tweedie est ajusté SANS offset et prédit AVEC.** C'est le défaut que `0d2b9c2` a corrigé au fit, resté au predict.

```
  l.1352  pred_test = modele_final.predict(X_test)            <- fit : PAS d offset
  l.1461  self.modeles['tweedie'].predict(X, offset=offset)   <- portefeuille : offset

  MESURE : corr(prime_pure_tweedie, exposition) = +0.5058
           expo<0.3 -> 23.02 EUR   expo>0.9 -> 100.91 EUR   = x4.38
  TEMOIN : frequence_annuelle       corr = -0.0093  (propre)
```

Sa propre docstring l'interdit : *« Ajouter offset=log(expo) appliquerait l'exposition DEUX FOIS »*. **Portée mesurée** : aucun consommateur hors A3 ; à l'intérieur, c'est la **2ᵉ source du lissage géographique** quand `prime_pure` est indisponible ([l.3014](direction_non_vie/tarification/a3_glm/agent.py:3014)). **Le tarif principal n'est pas touché.**

**C2 — H1 rend VERT sur des valeurs codées en dur quand la donnée manque.** Sans colonne de fréquence : `ratio=1.30, moyenne=0.05, variance=0.065` → *« Var/E = 1.30 < 2 → Distribution Poisson valide ✅ »*. **H1 est l'une des six plafonnantes d'A6.**

**C3 — H4 « non testée » vaut VERT.** C'est **exactement** le défaut corrigé dans A4 par le lot A de la série A→B→C→D, et **non reporté sur A3** :

```
  A3 : statut=VERT   msg='Stabilité relativités non testée…'
  A4 : statut=AMBRE  (corrigé)
```

**C4 — Les infobulles publient un IC 95 % faux ou tronqué.**
```
  coefficients_glm    : 'IC 95% : [0.0000, 0.0000]'   <- deux zeros codes en dur
  relativites_poisson : 'IC 95% : ['                  <- crochet ouvert, rien dedans
```
Les vraies bornes existent (`ic95_low`/`ic95_high`) et ne sont pas passées.

**C5 — La courbe de Lorenz publiée n'est pas mesurée, elle est tracée.** [l.2161](direction_non_vie/tarification/a3_glm/agent.py:2161) : `lorenz = t ** (1 / (1 + gini * 2))`. C'est une fonction analytique du seul scalaire Gini — **deux portefeuilles différents de même Gini donnent la même courbe au pixel près**. Le graphique s'intitule « Courbe de Lorenz » et son infobulle annonce « % contrats / % sinistres cumulés ». Les vrais cumuls sont calculés dans `_calculer_gini` et jetés.

**C6 — Le Gini du Tweedie n'existe pas et vaut 0 partout.** `_calibrer_tweedie` ne pose aucune clé `gini`. G3, G4 et H3 lisent `.get('gini', 0)` → le Tweedie est publié à **0.0000** dans trois endroits, y compris `h3_ajustement['gini_tweedie']`.

**C7 — `meilleur_modele` compare deux Gini incomparables.** `{'poisson': 0.3856, 'gamma': 0.0507}` → « meilleur = poisson ». Le Poisson est évalué sur **tout** le test (fréquence), le Gamma sur les **sinistrés seuls** (sévérité). Ce ne sont pas deux candidats pour la même tâche.

### B — Affirme plus que le code ne porte (5)

**C8 — H3 : le seuil annoncé n'est pas le seuil appliqué.** La docstring dit « Gini ∈ [0.08, 0.15] → acceptable ⚠️ ». Mesuré : `0.12 → VERT`. Le code a **quatre** bandes, la docstring **trois**.

> ✅ **FERMÉ.** La scorecard se construit désormais **depuis les hypothèses réellement calculées** (`val_glm.items()`), et la légende dérive de `len(items)`. Mesuré : **5 hypothèses calculées → 5 listées → légende « 5 ✅ »** (avant : légende 3, liste 4, calculées 5 — *trois comptes pour la même chose dans le même graphique*). `h5_deviance`, une plafonnante, apparaît enfin.
> ⚠️ **Effet de bord voulu** : la ligne H4 lisait `.get("h4_stabilite", {}).get("statut", "VERT")` — une hypothèse ABSENTE s'affichait VERTE. En construisant depuis les clés présentes, elle **n'apparaît plus** au lieu d'apparaître verte. *`a3/C3` reste ouvert sur le CALCUL ; ce qui est fermé, c'est la scorecard qui l'affichait.*

**C9 — La scorecard annonce « 3 ✅ = GLM validé », liste 4 items, et 5 hypothèses sont calculées.** H5 (déviance) — une plafonnante — **n'apparaît pas** dans la scorecard.

> ✅ **FERMÉ — en alignant la PHRASE sur le CODE, et je dis pourquoi ce sens-là.** Faire entrer le Tweedie dans le statut importerait son Gini, dont **`a3/C6` établit qu'il vaut 0 partout** : on ferait décider un verdict réglementaire par une métrique connue comme cassée. ⚠️ **Deux constats couplés, l'ordre est contraint** — le jour où `a3/C6` sera fermé, la question de l'inclure se reposera. Un test épingle l'absence du Tweedie dans le statut et échouera si on l'y met.

**C10 — `_calculer_statut_rag` annonce « convergence des 3 modèles », en lit 2** : `['gamma', 'poisson']`. Le Tweedie n'entre jamais dans le statut.

**C11 — `VARS_GLM` est supprimé, et 5 lignes y renvoient encore** (l.289, 295, 599, 616, 624) — dont la docstring de `_preparer_donnees` : « On part des variables prioritaires de la sous-branche (VARS_GLM) ».

**C12 — `significatif` code `0.05` en dur** (2 sites) alors que `SEUIL_PVALUE` existe — et il est **toujours vrai**, le stepwise ne retenant que p ≤ 0.05. Un champ sans information.

### C — Imprécis ou daté (6)

**C13 — Le graphique `durbin_watson` n'est jamais produit.** Il lit `val_glm["h2_homosc"]["dw_stat"]` ; H2 rend `ratio_variance` depuis la réparation `87e0609`. `KeyError` avalé → `graphiques_validation = ['gini_comparaison_glm', 'scorecard_validation_glm', 'sur_dispersion_poisson']`. Trois graphiques sur quatre.
**C14 — Une p-value fabriquée à 1.0** sur erreur numérique, 2 sites — elle n'a pas été calculée. La variable écartée est aussi arbitraire (`vars_actives[-1]`), pas celle qui a échoué.
**C15 — Le repli de `predict` casse lui-même** : `np.full(...)` puis `.values` (l.912 et 1146) — un `ndarray` n'a pas `.values`.
**C16 — `COLS_A_EXCLURE`** : 5 entrées sur 23 sont Vie/Santé (`id_salarie`, `id_beneficiaire`, `id_adherent`, `cotisation_mensuelle_eur`, `charge_ij_annuelle_eur`).
**C17 — L'exemple d'usage `run(result_a2)`**, 3 fois dans le module, est refusé par le module.
**C18 — En-tête de test : « 7 tests », 4 méthodes.**

### D — Vérifié comme BON (6)

| affirmation | mesure |
|---|---|
| plan absent → erreur propre | `success=False` |
| aucune variable de genre retenue | 0 sur les vars du GLM |
| aucune fuite de sinistralité | `['bonus_malus']` seul retenu |
| graves réinjectés dans la prime | `prime_grave_unitaire` présent |
| **Gini non écrêté à zéro** | `np.clip(gini, -1.0, 1.0)` — l'anti-sélection reste visible |
| sévérité par la source unique | `construire_cible_severite` |

## ③ Ce que je n'ai pas lu

**Rien** : 3 214 + 425 lignes intégralement. Restent non vérifiables ici les mêmes références hors dépôt — `Commission Tarification IA France (2019) §3.2.4` (l.727, 752), et les références bibliographiques (Mildenhall 1999, Goldburd 2016, Bühlmann & Straub 1970, Frees & Valdez 1998, Nadaraya/Watson 1964, Gelfand 2010) que je n'ai pas les ouvrages pour contrôler.

## ④ Preuve

`audit_a3.py` en scratchpad — 19 blocs, chacun relançable seul.

---

**Mon appréciation** : le **noyau actuariel d'A3 est sain** — la cible de sévérité passe par la source unique, les graves sont réinjectés, le Gini n'est plus écrêté, et les deux tests de conformité genre tiennent sur des cas construits pour les faire tomber. Les 18 constats se concentrent sur **la couche de validation et de restitution** : les hypothèses H1/H3/H4 (seuils et replis), les graphiques (IC, Lorenz, Durbin-Watson), et les comptes annoncés. Deux ont un effet réel : **C1** (le Tweedie, borné au lissage géographique) et **C2/C3** (deux plafonnantes qui peuvent rendre VERT sans avoir rien testé).
