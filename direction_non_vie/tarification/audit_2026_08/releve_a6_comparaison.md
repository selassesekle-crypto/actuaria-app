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

> ⚠️⚠️ **MESURÉ LE 25/08/2026 — CETTE PHRASE N'ATTEINT AUCUN LIVRABLE, ET CE
> QUI L'EN EMPÊCHE EST UN ACCIDENT.** Produit et lu par exécution sur **cinq
> livrables** (Excel A6, HTML et Word équipe *décompressés*, HTML et Word
> modèles) : `justification_regl` n'y figure nulle part.
>
> **Le seul lecteur générique est `tarif_excel.py` l.734** — `for k, v in
> fiche.items()` — **et il filtre `if isinstance(v, str)` (l.735).**
> `justification_regl` est une **liste**. C'est ce filtre de TYPE, et lui seul,
> qui retient l'affirmation.
>
> ⚠️⚠️ **UN ACCIDENT DE TYPAGE QUI DÉCIDE CE QUI EST PUBLIÉ EST PLUS DANGEREUX
> QU'UNE DÉCISION EXPLICITE, PARCE QUE PERSONNE NE LE SAIT.** Écrire
> `"\n".join(justif_regl)` — un refactor parfaitement naturel — **publierait
> une affirmation de conformité Solvabilité 2 fausse dans le classeur qui part
> au CAC**, sans qu'aucun test ne l'attrape.
> **Le constat reste donc ENTIER, et sa correction reste due** : on ne laisse
> pas une affirmation réglementaire fausse en place parce qu'un `isinstance` la
> retient.
>
> ⚠️ **ET TROIS MÉTHODES ONT DONNÉ TROIS RÉPONSES SUR CE SEUL CHAMP** :
> `grep` du nom → « aucun lecteur » (faux, il est atteint par `.items()`) ;
> lecture de la boucle → « publié » (faux, le filtre l'écarte) ; **exécution →
> non publié**. *Un chemin de publication se conclut par exécution.*

**C11 — LA FICHE D'AIDE À LA DÉCISION EST PUBLIÉE À 25 % DE SON CONTENU.**
*(Inscrit le 25/08/2026 — trouvé par le passage libellés, absent des 134
constats précédents.)*

Mesuré par exécution sur les cinq livrables :

```
  publies : modele_recommande · profil_utilise · decision_finale
  MUETS   : score_final · gini · overfit_ratio · forces · faiblesses ·
            risques · alternatives · questions_actuaire · justification_regl

  -> 3 / 12 champs  (25 %)
```

L'agent A6 construit **forces, faiblesses, risques, alternatives et questions à
poser avant signature** — c'est le contenu même d'une aide à la décision — et
l'actuaire n'en voit **aucun**. Ce que le classeur porte de la fiche se réduit
à trois lignes : le nom du modèle, le profil, et « À VALIDER PAR L'ACTUAIRE
RESPONSABLE ».

⚠️ **Portée plus large, mesurée dans le même banc** : sur 24 champs porteurs de
texte du résultat d'A6, **18 n'atteignent aucun des cinq livrables** — dont
`alertes_modele` (le message d'amputation), `validation_selection.verdict` et
`backtest.stabilite`, **muets jusque dans leur clé**.

⚠️⚠️ **CE QUI EST MESURÉ ET CE QUI NE L'EST PAS.** Le banc détecte le passage
**verbatim** d'une valeur. Un champ **consommé puis reformaté** paraît muet à
tort : `exclusions_conformite` en est le cas — `synthese_exclusions` republie
le **nom de colonne**, pas le motif. Le script lève l'ambiguïté en marquant
**aussi les clés**, et c'est ainsi qu'`exclusions_conformite` a été reclassé
**CONSOMMÉ**. *Les trois « muets jusque dans leur clé » ci-dessus ont passé ce
second contrôle ; ils restent néanmoins à instruire agent par agent avant
d'être portés en constats à part entière.*

**Preuve** : `preuves/passage_libelles.py`, relançable seul.

> ✅✅ **`C5` ET `C11` FERMÉS ENSEMBLE — ET ILS NE POUVAIENT PAS L'ÊTRE
> AUTREMENT.** Mesuré après correctif, par exécution : **12/12 champs de la
> fiche atteignent le classeur** (3/12 avant), listes rendues **ligne à ligne**
> et non en `repr` Python.
>
> ⚠️⚠️ **L'ORDRE À L'INTÉRIEUR DU LOT EST LE FOND DU SUJET.** Publier la fiche
> (`C11`) sans conditionner son attestation (`C5`) aurait mis une **conformité
> Solvabilité 2 fausse dans le classeur qui part au CAC** — le correctif aurait
> créé le dommage que le constat annonçait seulement. `C5` a donc été posé
> **d'abord**, dans le même changement.
>
> **`C5`** : `_generer_fiche_decision` **exige** désormais `backtest` et
> `statut_rag` (mots-clés sans défaut — un défaut à `None` rouvrirait la porte
> en silence, même doctrine que le `X_val` d'A5 au lot 1.1). L'appel est
> **déplacé après le calcul de `statut_rag`** : il était construit avant, et ne
> pouvait donc pas en tenir compte. L'attestation est conditionnée à
> `avertissement_walk_forward` — **la source unique que les trois services de
> rapport utilisaient déjà, et que la fiche était seule à ignorer.**
> ⚠️ **L'absence d'attestation ne se fait pas par retrait** : la ligne devient
> « ⚠ CONFORMITÉ S2 PILIER 1 : NON ÉTABLIE À CE STADE — … », motif nommé.
> *Une ligne manquante se lit comme un oubli ; une ligne qui se dénonce se lit
> comme un fait.*
>
> **Contrôles positifs** — `test_fiche_decision.py`, **9 tests, par exécution
> du classeur** :
> ⚠️ le **second sens est premier** ici : `walk-forward réussi + statut VERT →
> la conformité EST attestée`. Sans lui, une garde qui refuserait tout
> passerait les tests négatifs sans rien prouver.
> ⚠️⚠️ Et une classe entière, `POS_Fiche_LeCouplageEstVerrouille`, **lit le
> CLASSEUR et non la fiche** : elle échoue si l'on revient sur `C5`, ou si la
> fiche est publiée par un autre chemin. *On ne peut plus dissocier les deux.*
>
> ⚠️ **Le contrôle positif a fait son travail dès sa première exécution** : mon
> témoin « backtest conforme » ne l'était pas — il lui manquait
> `modele_recalibre_fidele`, et la validation portait donc sur un **proxy**.
> **J'ai corrigé le témoin, pas l'assertion.**

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
