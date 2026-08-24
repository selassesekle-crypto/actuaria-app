# RELEVÉ A5 — DEEP LEARNING (CANN + TabNet)

**Lu intégralement** : `a5_deep_learning/agent.py` **2 232 l** + `test_a5_deep_learning.py` **268 l**.

## ① Le compte

**17 affirmations mesurées** — 9 constats · 8 vérifiées bonnes. **C'est l'agent au meilleur ratio du lot**, et son défaut central est d'une seule cause.

## ② Le classement

### A — Publie du FAUX à un actuaire qui signe (6)

**C1 — Les trois hypothèses DL sont ROUGE sur un CANN excellent. Une clé, trois verdicts faux.**

```
  cles reelles des metriques : ['best_val_loss','gini_test','gini_train','glm_gele',…]
  'gini' presente = False
  statuts PUBLIES : h1_convergence=ROUGE · h2_surapprentissage=ROUGE · h3_apport_dl=ROUGE
  Gini REELS      : CANN = 0.4781   TabNet = 0.0950
```

`_valider_hypotheses_dl` lit partout `.get('gini', 0)` alors que la clé est `gini_test`. Les trois hypothèses partent donc de **zéro**, et la scorecard conclut « ❌ Deep Learning non recommandé — utiliser GLM ou ML classique » **sur un CANN à 0,478**, correctement ancré, vérifié à 0.0 d'écart. Le CANN est bon ; sa validation dit l'inverse.

**C2 — H1 « Convergence » ne mesure pas la convergence : elle la fabrique.** Le code le dit — *« Simuler les losses à partir des métriques disponibles (en prod on utiliserait l'historique réel) »*. `loss_init = 0.50` **constante**, `loss_final = max(0.05, 1 − 2·gini)`. Rendu mesuré : `loss_final = 1`, `ratio = 2.0`, **ROUGE**. **L'historique réel existe** (`res_cann['historique']`, 11 entrées avec les vraies pertes) et n'est jamais transmis à la fonction.

**C3 — Les courbes d'apprentissage publiées sont trois lignes à zéro.**
```
  cles de l historique = ['epoch', 'train', 'val']
  cles LUES            = ['loss_train', 'loss_val', 'gini_val']
  traces produites : Loss Train (11 pts), Loss Val (11), Gini Val (11) — TOUTES A ZERO
```
`gini_val` n'est d'ailleurs enregistré nulle part. Le graphique s'intitule « 📈 CANN — Courbes d'apprentissage » et trace une « Best époque » sur ces zéros. Idem TabNet.

**C4 — Le graphique « Convergence » est une exponentielle analytique bruitée.**
```
  courbe = loss_init·exp(-3e/50) + loss_final·(1-exp(-3e/50))     -> analytique
  bruit  = np.random.normal()  NON SEME                            -> different a chaque run
  50 epoques codees en dur, alors que le run reel en a fait 11
```
Publié avec la légende « 💡 La loss doit diminuer régulièrement (courbe descend) ».

**C5 — Le graphique « DL vs GLM » met les deux modèles DL à zéro.**
```
  barres [GLM, CANN, TabNet] = [0.14, 0, 0]
  Gini REELS  CANN / TabNet  = [0.4781, 0.0950]
```
La légende dit « Les barres bleue/dorée doivent dépasser la ligne pointillée (GLM). Si non → DL non justifié. » — **elles ne le peuvent pas.**

**C6 — L'early stopping se règle sur le jeu de TEST.**
```
  _calibrer_cann   : val_loss sur X_test_t (X_test_t <- X_test) · best_state selectionne dessus
  _calibrer_tabnet : idem
  jeu de VALIDATION distinct : False (aucun)
```
La docstring annonce « la perte de **validation** ». Il n'y a pas de jeu de validation : les poids retenus sont ceux qui minimisent la perte **sur le test**, et le Gini test publié est donc optimiste. Le module cite pourtant Kaufman et al. (2012) sur la fuite — et l'évite correctement pour le scaler.

### B — Affirme plus que le code ne porte (1)

**C7 — Aucun seed n'est fixé : le modèle n'est pas reproductible.**
```
  0 appel a un seed dans le module
  deux runs IDENTIQUES -> Gini TabNet 0.0432 puis 0.0649
```
Le fichier de test le note lui-même : *« A5 n'en fixe AUCUN → sans ces lignes le Gini diffère à chaque exécution »* — et le compense de l'extérieur. Le dépôt invoque ailleurs « Exigence S2 : tout calcul actuariel doit être reproductible ».

### C — Imprécis ou daté (2)

**C8 — `COLS_A_EXCLURE`** : 5 entrées Vie/Santé sur 20, comme A3 et A4.
**C9 — En-tête de test : « 7 tests », 3 méthodes.**

### D — Vérifié comme BON (8)

| affirmation | mesure |
|---|---|
| plan absent → erreur propre | `success=False` |
| **`col_cible` obligatoire** (défaut `prime_pure` supprimé) | `success=False` |
| **CANN ancré : `glm_gele=True`** | **3/3** variables appariées |
| **vérification époque 0 ≡ GLM Tweedie** | **écart = 0.0** |
| mode dégradé → alerte surfacée | `cann_glm_non_ancre` dans `alertes_modele` |
| scaler ajusté sur TRAIN seul | aucune fuite au scaler |
| Gini non écrêté à zéro | `clip(2·auc − 1, −1, 1)` |
| **scorecard : compte exact** | annonce 3 ✅, liste 3 items — **le seul agent où ce compte est juste** |

Le **contrat Wüthrich est tenu et vérifié numériquement** : reprojection d'échelle, gel de la couche, dernière couche résiduelle à zéro, et un écart mesuré de **0.0** entre le CANN à l'époque 0 et le GLM Tweedie seul. C'est la pièce d'ingénierie la plus rigoureuse que j'aie lue dans ce module.

## ③ Ce que je n'ai pas lu

**Rien** : 2 232 + 268 lignes intégralement. Non vérifiables ici : `Wüthrich & Merz (2019) ASTIN Bulletin 49(1)`, `Arik & Pfister (Google, 2021)`, `Kaufman et al. (2012) ACM TKDD 6(4)`, `AI Act 2025`.

## ④ Preuve

`audit_a5.py` en scratchpad — 9 blocs, plus la mesure directe de la fuite d'early stopping.

---

**Mon appréciation** : **le cœur d'A5 est le mieux construit des cinq agents.** L'ancrage CANN est correct, gelé, reprojeté à la bonne échelle et **vérifié numériquement à 0.0** ; le mode dégradé se dénonce ; la cible piégeuse a été supprimée. Les 9 constats se concentrent sur **la couche de validation et de restitution**, et **six d'entre eux ont une seule et même cause** : la lecture de `gini` au lieu de `gini_test`, plus l'usage de valeurs simulées là où l'historique réel existe. Conséquence mesurée : **un CANN à Gini 0,478 est publié « non recommandé »**, avec trois hypothèses rouges et cinq graphiques à zéro.

Reste **A6**, puis les services de rapport.
