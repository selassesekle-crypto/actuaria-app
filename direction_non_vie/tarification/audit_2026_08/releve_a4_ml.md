# RELEVÉ A4 — TARIFICATION MACHINE LEARNING

**Lu intégralement** : `a4_ml/agent.py` **2 988 l** + `test_a4_ml.py` **546 l**.

## ① Le compte

**19 affirmations mesurées** — 13 constats · 6 vérifiées bonnes.

## ② Le classement

### A — Publie du FAUX à un actuaire qui signe (6)

**C1 — Le « tarif optimal » publié est une constante : −20 %, toujours.**

```
  {}                          -> optimal = -20 %
  {'prime_moyenne': 1200.0}   -> optimal = -20 %
  {'nb_contrats': 50000}      -> optimal = -20 %
  {'elasticite': -2.0}        -> optimal = -20 %
  chaine PUBLIEE : "Tarif optimal : +-20% → Prime 360€ → CA 5031k€ (+11.8% vs base)"
```

Avec ε = −1.5, le CA vaut `p^(1+ε) = p^(−0,5)` — **décroissant en p** : l'optimum est mécaniquement la borne basse de la grille. `gini_meilleur` est reçu **et jamais utilisé** (1 occurrence, la signature). `prime_moyenne=450`, `nb_contrats=10000`, `elasticite=−1.5`, `Loss Ratio 70 %` sont codés en dur. Le graphique `optimisation_tarifaire` titre « ✅ Tarif optimal : −20 % → CA max ». **Recommander une baisse tarifaire de 20 % à un actuaire, indépendamment de ses données, est le constat le plus lourd de cet agent.**

**C2 — Le monitoring de dérive est intégralement simulé.**
```
  distributions tirees par np.random.beta = True
  PSI identique sur 2 portefeuilles DIFFERENTS = True  (0.0792)
  KS identique = True
```
`scores_ref = np.random.beta(2, 5, 1000)`, `scores_actuels = np.random.beta(2.2, 4.8, 1000)`, `seed=42` → **le PSI est une constante du module**. Les 12 mois d'« historique Gini » sont eux aussi simulés (`gini_reference * (1 − 0.002·i + N(0, 0.003))`). Publié sous le titre « Monitoring de la dérive des modèles ML **en production** », avec la recommandation « ✅ Modèle stable — prochaine révision dans 3 mois ». **À décharge** : `psi_source = "simulé"` figure dans le message H2, et la docstring le dit. Le graphique `monitoring_gini`, lui, ne porte aucune marque.

**C3 — Le graphique d'overfitting affiche un Gini test nul pour tous les modèles.**
```
  trace "Gini Test"  = [0, 0, 0, 0, 0, 0]
  valeurs REELLES    = [0.3405, 0.2946, 0.2886, 0.2536, 0.2349, 0.1156]
```
Cause : `m.get('gini', 0)` — la clé du classement est `gini_test`. Les couleurs, calculées sur ce zéro, sortent toutes en **rouge**. Le graphique est intitulé « Barres Train vs Test » avec la légende « un grand écart = surapprentissage ».

**C4 — Deux validations contradictoires dans le même dictionnaire de retour.**
```
  hypotheses.h4    = ROUGE  (ecart = 55.56 %)   <- calculee AVEC X_test/y_test
  validation_ml.h4 = AMBRE  (ecart = None)      <- calculee SANS
```
`_valider_modele_ml` est appelée **quatre fois** dans le même `return`, dont trois sans les données de test. **L'Excel lit `validation_ml`** ; le verrou d'A6 lit `hypotheses`. Sur ce portefeuille, l'actuaire lit AMBRE « non testée » là où la mesure dit ROUGE.

**C5 — La courbe de Lorenz est tracée, pas mesurée** — même formule qu'A3 (`t ** (1/(1+2g))`). Ici s'ajoute une contradiction d'axe : l'abscisse annonce « % contrats (**du moins au plus risqué**) » alors que le Gini trie **décroissant**, le plus risqué d'abord.

**C6 — « Modèles testés : 6/8 »** publié dans le commentaire actuaire, alors que la boucle n'en déclare que **6**. Le dénominateur est faux, pas le numérateur.

### B — Affirme plus que le code ne porte (4)

**C7 — « ML ×8 » : 12 mentions de « 8 » dans le module, 6 modèles réels.** La boucle et sa propre docstring disent 6 ; le bloc `__main__` en liste 6. L'en-tête annonce nommément **RandomForest, GAM et RégQuantile**, qui ne sont dans aucune boucle — **GAM n'existe nulle part**, pas même dans `FAMILLES_MODELES_ML`.

**C8 — La scorecard annonce « 3 ✅ = modèle validé » et liste 4 items.** Même défaut qu'A3.

**C9 — Le statut RAG ROUGE annoncé n'est pas atteint.** La docstring dit « ROUGE : Aucun modèle ML ne bat le GLM ». Mesuré : ML 0.14 contre GLM 0.30 → **AMBRE**, parce que la seconde branche accepte `meilleur_gini_ml > 0.10`.

**C10 — Le classement mélange deux bases de rang.** A3 classe sur le **comptage prédit** (avec offset), A4 sur le **taux** — et les deux entrent dans un seul tableau trié par `gini_test`. Le code d'A4 le dit lui-même : « Gini sur le TAUX (rang de risque) ».

### C — Imprécis ou daté (3)

**C11 — La clé `gini` n'existe pas dans le classement**, et **9 sites** lisent `.get('gini', défaut)`. Les clés réelles sont `gini_test` / `gini_train`. Le défaut `0.25` est ce qui alimente `_optimisation_tarifaire`.
**C12 — `COLS_A_EXCLURE_ML`** : 5 entrées Vie/Santé sur 22, comme A3.
**C13 — En-tête de test : « 7 tests », 11 méthodes.**

### D — Vérifié comme BON (6)

| affirmation | mesure |
|---|---|
| plan absent → erreur propre | `success=False` |
| **H4 non testée → AMBRE** (correctif faux-vert) | `AMBRE` — **le défaut que A3 porte encore** |
| **écart non mesuré → `None`, pas 0.0** | `None` traverse jusqu'au livrable |
| aucune feature de genre | 0 sur 8 features |
| Gini non écrêté à zéro | `clip(2·auc − 1, −1, 1)` |
| fabrique = source unique A4/A6 | 6 délégations à `creer_modele_ml_pour_nom` |

Les deux correctifs de la série A→B→C→D — H4 par défaut AMBRE, et `None` plutôt que `0.0` — **tiennent et sont vérifiés**. Ce sont eux qui manquent encore à A3.

## ③ Ce que je n'ai pas lu

**Rien** : 2 988 + 546 lignes intégralement. Non vérifiables ici : `AI Act 2025 Art. 13` (8 mentions), `ACPR-2022-P-01 §4.3`, `Commission Tarification IA France 2019 §3.2.4`, et les références bibliographiques (Siddiqi 2006, Denuit et al. 2019, Agresti 2015, Shapley 1953, Breiman 2001).

## ④ Preuve

`audit_a4.py` en scratchpad — 14 blocs relançables.

---

**Mon appréciation** : le **cœur ML est le mieux tenu du lot** — l'enveloppe taux+poids pour l'exposition, la fabrique unique A4/A6, le scaler du linéaire, le filtre genre, le Gini honnête : tout cela est solide et documenté par la mesure qui l'a établi. Les 13 constats portent, à une exception près, sur **des couches ajoutées autour du ML** : le monitoring, l'optimisation tarifaire, les graphiques. Deux d'entre eux publient des chiffres qu'un actuaire pourrait prendre pour des mesures de son portefeuille — **le monitoring simulé** et surtout **le « tarif optimal » à −20 %**.
