# RELEVÉ A6 — COMPARAISON & VALIDATION FINALE

**Lu intégralement** : `a6_comparaison/agent.py` **2 916 l** + `test_a6_comparaison.py` **829 l**.

## ① Le compte

**17 affirmations mesurées** — 10 constats · 7 vérifiées bonnes. **Le verrou de décision lui-même est bon sur ses 7 mécanismes** ; les constats portent sur ce qui l'entoure.

## ② Le classement

### A — Publie du FAUX à un actuaire qui signe (5)

**C1 — Le « Test A/E (Actual vs Expected) » ne compare pas l'observé à l'attendu.**
```
  A/E = moyenne(observe_TEST) / moyenne(observe_TRAIN) = True
  la PREDICTION du modele existe (pred_te)              = True
  elle entre dans le A/E                                = False
  valeur publiee = 1.2264
```
C'est un **test de stationnarité de la cible**, pas une mesure de calibration du modèle. Le commentaire du code dit pourtant, deux lignes plus haut : « C'est un vrai backtesting de modèle — **pas un test de stationnarité** ». Le Gini walk-forward, lui, utilise bien la prédiction.

**C2 — Le A/E par segment déclare ROUGE 11 segments sur 12, sur un portefeuille sans hétérogénéité.**
```
  quintiles_risque : ['ROUGE']
  zones            : ['ROUGE','VERT','ROUGE','ROUGE']
  tranches_age     : ['ROUGE','ROUGE','ROUGE','ROUGE','ROUGE','ROUGE']
```
Chaque segment est comparé à **la moyenne globale du train**, pas à ce que le modèle prédit pour lui. Un segment réellement plus risqué sortira donc ROUGE **même si le modèle le tarife parfaitement**. Ce tableau est publié à l'actuaire comme « A/E par segment ».

**C3 — Le graphique « Score par profil » n'affiche pas le score.**
```
  graphique 'scores_profils', profil equilibre = 0.56
  score_global REEL du meme modele             = 0.9001
```
`_generer_graphiques` recalcule le score avec une **formule différente** de `_calculer_scores_multicriteres` (Gini brut au lieu de normalisé, `1/overfit`, `1 − rmse/400`). Deux formules pour la même grandeur, dont une seule décide.

**C4 — Les graphiques de validation de la sélection lisent une clé qui n'existe pas.**
```
  barres Gini        = [0, 0, 0, 0]
  valeurs REELLES    = [0.21, 0.22, 0.16, 0.15]
  radar (5 axes)     = [0.0, 0.8, 0.6, 0.8, 0.9]
```
`m.get('gini', 0)` alors que la clé est `gini_test`. Le radar est pire : sur ses cinq axes, **trois sont des valeurs par défaut** (`stabilite`, `rmse_norm` n'existent pas dans le catalogue ; `score_stabilite`/`score_rmse` si). Le contrôle C2, dans le même fichier, commente explicitement « Clé correcte : `gini_test` (pas `gini`) » — la leçon a été tirée à un endroit et pas à l'autre.

**C5 — Une conformité réglementaire affirmée sans condition.** La fiche de décision publie *« Conformité S2 Pilier 1 : modèle validé sur données de test indépendantes »* **toujours** — `_generer_fiche_decision` ne reçoit ni le backtest, ni le statut. Elle l'écrit même quand le walk-forward a échoué et que le statut est plafonné.

### B — Affirme plus que le code ne porte (3)

**C6 — Une chaîne qui ne matche pas, et elle rend deux choses muettes.**
```
  valeur REELLE   : 'walk_forward_temporel_avec_recalibration'
  comparee a      : 'walk_forward_temporel'  (agent 1x, TEST 2x)
  le commentaire publie-t-il les fenetres WF = False
```
Côté agent : **le commentaire actuaire ne publie jamais** le nombre de fenêtres, le nombre de fenêtres ROUGE ni la stabilité — exactement les quantités sur lesquelles le verrou plafonne. Côté test : **les assertions ST4 (fenêtres) et ST5 (segments) ne s'exécutent jamais** — le test passe sans vérifier ce qu'il annonce.

**C7 — `_calculer_courbes` annonce « les 3 meilleurs modèles » et ne les utilise pas.** `top_modeles` est reçu, cité une seule fois — sa signature. La courbe est le tri de la **valeur observée** : `gini_observe = 0.9734` contre `0.21` pour le modèle. *À décharge* : le nom `gini_observe` est honnête, et `chart_lorenz_gini` reçoit bien **les deux** Gini avec un commentaire qui explique pourquoi. C'est la docstring qui sur-annonce, pas le graphique.

**C8 — Le plafond de vraisemblance du Gini traite toute cible comme une fréquence.** `gini_est_plausible(gini, cible_est_frequence=True)` — codé en dur, alors que `col_cible` peut valoir `cout_moyen` ou `prime_pure`. Le seuil 0,60 est calibré sur la fréquence.

### C — Imprécis ou daté (2)

**C9 — `INTERPRETABILITE`** : 3 entrées sur 13 pour des modèles supprimés (`random_forest`, `quantile_50`, `quantile_90`).
**C10 — En-tête de test : « 7 tests », **24** méthodes.** L'écart le plus large du lot — et dans le bon sens.

### D — Vérifié comme BON (7)

| affirmation | mesure |
|---|---|
| **gouvernance : le vide ne vaut pas validation** | `''`, `'   '`, `None` → False ; un nom → True |
| **prédicat unique, 3 appelants** | 0 réécriture en dur, 3 appels |
| **filtre par cible : les écartés sont surfacés** | 2 modèles écartés, tracés dans `exclusions_cible` |
| **les causes du plafond se nomment en toutes lettres** | phrases > 30 car., aucun nom de variable |
| **`_gini_lorenz` : source unique, signe correct** | parfait > 0,5 · anti-corrélé < −0,4 |
| **plafond de vraisemblance** | Gini 0,93 → **AMBRE** |
| **walk-forward FIDÈLE sur un vrai run** | `modele_recalibre_fidele = True` |

Et le **verrou de décision lui-même** — les six plafonds, l'ordre des lignes, `raisons_plafond` construite dans le même geste que la décision — **tient**. Le test A6 est le meilleur du dépôt : 24 méthodes, des contrôles **comportementaux** (il génère un vrai classeur Excel et lit ce que l'actuaire y voit), et des contrôles **positifs** systématiques (« le garde-fou ne doit pas plafonner en permanence »).

## ③ Ce que je n'ai pas lu

**Rien** : 2 916 + 829 lignes intégralement. Non vérifiables ici : `ACPR-2022-P-01 §4.3`, `Commission Tarification IA France (2019) §3.2.5`, `Saltzer & Schroeder (1975)`, `AI Act 2025`.

## ④ Preuve

`audit_a6.py` en scratchpad — 10 blocs relançables.

---

**Mon appréciation** : **A6 est l'agent le plus solide du lot sur ce qui décide.** Le prédicat de gouvernance, le filtre par cible, les six plafonds, la source unique du Gini et ses cinq sentinelles, la plausibilité — tout cela a été construit contre des défauts réels, chacun documenté par la mesure qui l'a trouvé, et **tout tient à la mesure**. Les 10 constats portent sur **le compte rendu autour de la décision** : le A/E qui n'en est pas un, les segments qui accusent l'hétérogénéité du portefeuille, quatre graphiques nourris de clés absentes, et une chaîne mal orthographiée qui rend muets à la fois le commentaire **et** deux assertions de son propre test.

**Les six agents sont relevés.** Restent les **services de rapport** — et c'est là que le lot ① avait trouvé son premier fait.
