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

> ✅ **`a4/C1`** · **FERMÉ — vérifié le 27/08/2026 par deux méthodes.**
> **① Code d'aujourd'hui, par AST** : **aucune** définition contenant `optimisation` dans A4, et **0** mention textuelle de `_optimisation_tarifaire`. La fonction n'existe plus.
> **② `REMESURE_A3_A4_A5.md` (25/08)** : retirée au lot L0.
> ⚠️ *Le « tarif optimal −20 %, toujours » ne peut plus être publié : il n'a plus de producteur.*

**C2 — Le monitoring de dérive est intégralement simulé.**
```
  distributions tirees par np.random.beta = True
  PSI identique sur 2 portefeuilles DIFFERENTS = True  (0.0792)
  KS identique = True
```
`scores_ref = np.random.beta(2, 5, 1000)`, `scores_actuels = np.random.beta(2.2, 4.8, 1000)`, `seed=42` → **le PSI est une constante du module**. Les 12 mois d'« historique Gini » sont eux aussi simulés (`gini_reference * (1 − 0.002·i + N(0, 0.003))`). Publié sous le titre « Monitoring de la dérive des modèles ML **en production** », avec la recommandation « ✅ Modèle stable — prochaine révision dans 3 mois ». **À décharge** : `psi_source = "simulé"` figure dans le message H2, et la docstring le dit. Le graphique `monitoring_gini`, lui, ne porte aucune marque.

> ✅ **`a4/C2`** · **FERMÉ — vérifié le 26/08/2026 par DEUX méthodes indépendantes.**
> **① Lecture du code** : zéro appel `np.random.*` dans tout `a4_ml/agent.py`
> (relevé **par AST**). Le PSI vient de `_psi_reel(X_train, X_test)` sur les
> features réelles ; le KS des scores réels ; et la courbe ne porte plus que
> **deux points mesurés** — « Référence A3 » et « Modèle retenu (test) », pas
> treize points simulés. La figure porte enfin sa marque : *« ce graphique ne
> mesure PAS la dérive en production »*. Un PSI non mesuré affiche
> « PSI non mesuré », jamais un nombre.
> **② Exécution** : PSI = **0,056** sur deux portefeuilles proches contre
> **7,59** sur deux éloignés. *La grandeur répond aux données* — le
> « PSI identique sur 2 portefeuilles = True » du constat est mort.
> Épinglé par `test_monitoring_derive_reel.py` (6 contrôles).
>
> ⚠️⚠️ **MAIS LA FERMETURE S'ÉTAIT PÉRIMÉE EN SILENCE AILLEURS.** Six
> semaines après la correction, `FIGURES_ECARTEES` retirait toujours
> `monitoring_gini` du rapport **SIGNÉ** au motif de « données FABRIQUÉES »,
> en citant `np.random.beta(2,5)` — **un code qui n'existe plus**. *Une figure
> mesurée restait accusée.* Le motif énonce désormais l'état réel, et un
> nouveau contrôle **fait tomber la gate sur toute accusation périmée**.
> ⚠️ Le garde-fou qui existait ne pouvait pas le voir : il tombe sur une
> figure **nouvelle** ni au plan ni écartée, jamais sur un **motif qui
> vieillit**. Son assiette couvrait les ajouts, pas le vieillissement —
> *un garde-fou qui exclut la seule chose qui compte n'en est pas un.*
> ⚠️ **RESTE À ARBITRER** : le retour de `monitoring_gini` au plan du rapport
> signé. La figure est mesurée et marquée ; la décision n'est pas prise.

**C3 — Le graphique d'overfitting affiche un Gini test nul pour tous les modèles.**
```
  trace "Gini Test"  = [0, 0, 0, 0, 0, 0]
  valeurs REELLES    = [0.3405, 0.2946, 0.2886, 0.2536, 0.2349, 0.1156]
```
Cause : `m.get('gini', 0)` — la clé du classement est `gini_test`. Les couleurs, calculées sur ce zéro, sortent toutes en **rouge**. Le graphique est intitulé « Barres Train vs Test » avec la légende « un grand écart = surapprentissage ».

> ✅ **`a4/C4`** · **DÉJÀ FERMÉ — constaté le 25/08/2026 en le RE-MESURANT, pas en le relisant.** Mesuré sur un vrai run : `validation_ml` et `hypotheses` sont **identiques sur toutes les clés** — h1 VERT, h2 VERT, h3 ROUGE, h4 AMBRE, statut_global ROUGE. Aucune divergence.
> ⚠️ *Le correctif était dans le code, jamais reporté ici. L'archive prévient elle-même : « ils mesurent l'état ACTUEL, pas celui du jour de l'audit — lire le chiffre, pas l'étiquette ». Épinglé désormais par `test_hypotheses_non_testees.py`.*

**C4 — Deux validations contradictoires dans le même dictionnaire de retour.**
```
  hypotheses.h4    = ROUGE  (ecart = 55.56 %)   <- calculee AVEC X_test/y_test
  validation_ml.h4 = AMBRE  (ecart = None)      <- calculee SANS
```
`_valider_modele_ml` est appelée **quatre fois** dans le même `return`, dont trois sans les données de test. **L'Excel lit `validation_ml`** ; le verrou d'A6 lit `hypotheses`. Sur ce portefeuille, l'actuaire lit AMBRE « non testée » là où la mesure dit ROUGE.

**C5 — La courbe de Lorenz est tracée, pas mesurée** — même formule qu'A3 (`t ** (1/(1+2g))`). Ici s'ajoute une contradiction d'axe : l'abscisse annonce « % contrats (**du moins au plus risqué**) » alors que le Gini trie **décroissant**, le plus risqué d'abord.

> ✅ **`a4/C6`** · **FERMÉ.** Le dénominateur était le littéral `8`, qui ne correspondait **à aucun des trois comptes réels** : 6 candidats dans `modeles_a_calibrer`, 10 dans le catalogue `FAMILLES_MODELES_ML`, 6 réellement testés. Il dérive maintenant de la **liste des candidats**, enregistrée au rapport. Mesuré : « Modèles testés : **6/6** ». *Le numérateur était déjà dérivé ; seul le dénominateur était inventé.*

**C6 — « Modèles testés : 6/8 »** publié dans le commentaire actuaire, alors que la boucle n'en déclare que **6**. Le dénominateur est faux, pas le numérateur.

### B — Affirme plus que le code ne porte (4)

**C7 — « ML ×8 » : 12 mentions de « 8 » dans le module, 6 modèles réels.** La boucle et sa propre docstring disent 6 ; le bloc `__main__` en liste 6. L'en-tête annonce nommément **RandomForest, GAM et RégQuantile**, qui ne sont dans aucune boucle — **GAM n'existe nulle part**, pas même dans `FAMILLES_MODELES_ML`.

> ✅ **`a4/C8`** · **FERMÉ** — même geste qu'`a3/C9` : la légende dérive de `len(items)`. Mesuré : 4 hypothèses → légende « 4 ✅ ».

**C8 — La scorecard annonce « 3 ✅ = modèle validé » et liste 4 items.** Même défaut qu'A3.

> ✅ **`a4/C9`** · **FERMÉ — la docstring porte enfin la SECONDE condition**, et le seuil devient `SEUIL_GINI_ML_EXPLOITABLE = 0.10`, nommé au niveau module. ⚠️ **La règle du code est défendable** — un ML qui discrimine honnêtement sans battre le GLM n'est pas sans valeur — **mais elle était invisible** : un littéral enfoui dans une branche qui décide d'un statut réglementaire. *Un chiffre qui fait la différence entre AMBRE et ROUGE se nomme, sinon personne ne peut le discuter.*

**C9 — Le statut RAG ROUGE annoncé n'est pas atteint.** La docstring dit « ROUGE : Aucun modèle ML ne bat le GLM ». Mesuré : ML 0.14 contre GLM 0.30 → **AMBRE**, parce que la seconde branche accepte `meilleur_gini_ml > 0.10`.

**C10 — Le classement mélange deux bases de rang.** A3 classe sur le **comptage prédit** (avec offset), A4 sur le **taux** — et les deux entrent dans un seul tableau trié par `gini_test`. Le code d'A4 le dit lui-même : « Gini sur le TAUX (rang de risque) ».
> ✅ **`a4/C10`** · **FERMÉ le 27/08/2026 — `6d5eeb9`, DÉCLARATION seule.**
> Chaque Gini déclare sa `base_gini`, et le mélange se dit.
> **AUCUN NOMBRE NE BOUGE, et un test le prouve.**
> ⚠️ **L'ÉCART EST MESURÉ** : base COMPTAGE **0,4339** contre base UNITAIRE
> **0,3675**, soit **+18,1 %** ; à exposition CONSTANTE il tombe à **0,0000**.
> Il vient donc ENTIÈREMENT de la variation d'exposition, et il est
> SYSTÉMATIQUEMENT favorable au comptage. A6 trie sur `gini_test`, pondéré
> 40 % : *une convention non mesurée flattait un camp.*
> ⚠️⚠️ **ET LE DÉFAUT EST PLUS LARGE QUE LE CONSTAT NE LE DIT** : A5 compare
> DÉJÀ deux bases entre SES PROPRES modèles — CANN applique l'offset dans son
> forward, TabNet non. Le constat ne parlait que d'A3 contre A4.
> ⚠️⚠️ **CE QUE CE BLOC NE FERME PAS, ET IL FAUT LE LIRE** : le constat portait
> sur le mélange NON DIT ; il est dit. **L'ALIGNEMENT des bases reste OUVERT**,
> arbitré ainsi parce qu'il DÉPLAÇAIT UN PRIX — mesuré. Il attend une décision
> sur ce que « rang de risque » doit signifier.

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
