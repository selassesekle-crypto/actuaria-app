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

> ✅ **`a3/C1`** · **FERMÉ — vérifié le 27/08/2026 par deux méthodes.**
> **① Code d'aujourd'hui, par AST** : `self.modeles['tweedie'].predict(X)` à la l.1512 — **sans `offset`**. Le Poisson garde le sien (l.1455), ce qui est correct : c'est lui qui modélise un comptage.
> **② `REMESURE_A3_A4_A5.md` (25/08)** l'établissait déjà par deux méthodes : le correctif est complet, **au fit ET au predict**.
> ⚠️ *C'était le seul constat que j'avais désigné comme déplaçant un euro — et il était fermé avant que je l'ouvre.*

> ✅ **`a3/C2`** · **DÉJÀ FERMÉ — constaté le 25/08/2026 en le RE-MESURANT, pas en le relisant.** Mesuré : sans colonne de fréquence, H1 rend **AMBRE** — « Sur-dispersion NON mesurée » — et `ratio_disp` vaut `None`. Aucun chiffre inventé n'est publié.
> ⚠️ *Le correctif était dans le code, jamais reporté ici. L'archive prévient elle-même : « ils mesurent l'état ACTUEL, pas celui du jour de l'audit — lire le chiffre, pas l'étiquette ». Épinglé désormais par `test_hypotheses_non_testees.py`.*

**C2 — H1 rend VERT sur des valeurs codées en dur quand la donnée manque.** Sans colonne de fréquence : `ratio=1.30, moyenne=0.05, variance=0.065` → *« Var/E = 1.30 < 2 → Distribution Poisson valide ✅ »*. **H1 est l'une des six plafonnantes d'A6.**

> ✅ **`a3/C3`** · **DÉJÀ FERMÉ — constaté le 25/08/2026 en le RE-MESURANT, pas en le relisant.** Mesuré : H4 rend **AMBRE** par défaut — « Stabilité relativités NON testée » — et `cv_max` vaut `None`.
> ⚠️ *Le correctif était dans le code, jamais reporté ici. L'archive prévient elle-même : « ils mesurent l'état ACTUEL, pas celui du jour de l'audit — lire le chiffre, pas l'étiquette ». Épinglé désormais par `test_hypotheses_non_testees.py`.*

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
> ✅ **`a3/C4`** · **FERMÉ le 27/08/2026 — `271d50d`.** Les deux infobulles
> publient les VRAIES bornes, passées par `customdata`.
> ⚠️⚠️ **ET LE DÉFAUT NE VENAIT PAS D'UNE NÉGLIGENCE — c'est ce qu'il apprend.**
> Un `hovertemplate` plotly est UNE chaîne pour TOUTES les barres : une f-string
> n'y place qu'un SCALAIRE, jamais une valeur PAR POINT. L'auteur n'avait pas de
> mécanisme, il a mis `0`. *Une valeur fabriquée faute de mécanisme reste une
> valeur fabriquée : elle se déclare, ou on trouve le mécanisme.*
> ⚠️ **Aucun euro déplacé, aucun statut modifié.** Seule la valeur AFFICHÉE
> change — de `[0.0000, 0.0000]` aux bornes que traçaient DÉJÀ les barres
> d'erreur du même graphique.

**C5 — La courbe de Lorenz publiée n'est pas mesurée, elle est tracée.** [l.2161](direction_non_vie/tarification/a3_glm/agent.py:2161) : `lorenz = t ** (1 / (1 + gini * 2))`. C'est une fonction analytique du seul scalaire Gini — **deux portefeuilles différents de même Gini donnent la même courbe au pixel près**. Le graphique s'intitule « Courbe de Lorenz » et son infobulle annonce « % contrats / % sinistres cumulés ». Les vrais cumuls sont calculés dans `_calculer_gini` et jetés.

> ✅ **`a3/C5`** · **FERMÉ le 29/08/2026 PAR SUPPRESSION — arbitrage de Selasse.**
> *Preuve : `test_sensibilite_profils.py`, 4 contrôles.*>
> ⚠️⚠️ **CE N'ÉTAIT PAS UN DOUBLON INOFFENSIF, C'ÉTAIT UN DOUBLON FAUX.** La
> courbe n'était pas mesurée mais **reconstruite du seul scalaire Gini**
> (`t ** (1/(1+gini*2))`) : deux portefeuilles différents de même Gini
> donnaient la même courbe **au pixel près**. La figure publiée,
> `chart_lorenz_gini`, reçoit elle des points **mesurés**
> (`np.cumsum(y_sort)/np.sum(y_sort)`).
>
> ⚠️⚠️ **SUPPRIMÉ PAR SITE, JAMAIS PAR NOM.** A6 définit aussi une clé
> `'lorenz'` — mais c'est le dictionnaire des points RÉELS qui alimente la
> figure publiée. *Une suppression par le nom aurait détruit la bonne courbe.*
> Un test plante cet homonyme.
> ⚠️ **ET LA FORMULE PART AVEC LA FIGURE** : balayée sur tout le dépôt (code de
> production), `t ** (1/(1+gini*2))` n'existe **plus nulle part**. *Supprimer
> le graphique seul aurait laissé le vrai défaut en place, caché.*

**C6 — Le Gini du Tweedie n'existe pas et vaut 0 partout.** `_calibrer_tweedie` ne pose aucune clé `gini`. G3, G4 et H3 lisent `.get('gini', 0)` → le Tweedie est publié à **0.0000** dans trois endroits, y compris `h3_ajustement['gini_tweedie']`.

> ✅ **`a3/C6`** · **FERMÉ le 26/08/2026 — `b0ae396`.** `_calibrer_tweedie` calcule désormais
> son Gini sur (prime pure observée, prédite). **Mesuré : −0,078** — *négatif*.
> Le `0` fabriqué par `.get('gini', 0)` n'était donc pas neutre, il était
> **flatteur**, comme le plancher d'A5.
> ⚠️⚠️ **ET IL RENDAIT INERTE UN GARDE-FOU QUI EXISTAIT** : A6 force le statut à
> **ROUGE** dès qu'un Gini est négatif (anti-sélection, auto-audit du
> 11/07/2026). La règle n'avait jamais pu se déclencher sur le Tweedie —
> *le garde-fou surveillait un littéral.* Statut mesuré sur le chemin de l'app,
> candidat unique : **AMBRE → ROUGE**.
> ⚠️ Un Gini non mesurable vaut désormais `None`, **jamais `0`**, et A6 écarte
> le modèle **en le déclarant**. Épinglé par `test_gini_tweedie_arbitrage.py`
> (8 contrôles, violation plantée dans chacun).

**C7 — `meilleur_modele` compare deux Gini incomparables.** `{'poisson': 0.3856, 'gamma': 0.0507}` → « meilleur = poisson ». Le Poisson est évalué sur **tout** le test (fréquence), le Gamma sur les **sinistrés seuls** (sévérité). Ce ne sont pas deux candidats pour la même tâche.

### B — Affirme plus que le code ne porte (5)

> ✅ **`a3/C8`** · **DÉJÀ FERMÉ — constaté le 25/08/2026 en le RE-MESURANT, pas en le relisant.** Mesuré sur les cinq bornes : `0.07→ROUGE · 0.09→AMBRE · 0.12→AMBRE · 0.16→VERT · 0.30→VERT`. **`0.12` ne sort plus VERT**, et les quatre bandes sont cohérentes avec le commentaire.
> ⚠️ *Le correctif était dans le code, jamais reporté ici. L'archive prévient elle-même : « ils mesurent l'état ACTUEL, pas celui du jour de l'audit — lire le chiffre, pas l'étiquette ». Épinglé désormais par `test_hypotheses_non_testees.py`.*

**C8 — H3 : le seuil annoncé n'est pas le seuil appliqué.** La docstring dit « Gini ∈ [0.08, 0.15] → acceptable ⚠️ ». Mesuré : `0.12 → VERT`. Le code a **quatre** bandes, la docstring **trois**.

> ✅ **`a3/C9`** · **FERMÉ.** La scorecard se construit désormais **depuis les hypothèses réellement calculées** (`val_glm.items()`), et la légende dérive de `len(items)`. Mesuré : **5 hypothèses calculées → 5 listées → légende « 5 ✅ »** (avant : légende 3, liste 4, calculées 5 — *trois comptes pour la même chose dans le même graphique*). `h5_deviance`, une plafonnante, apparaît enfin.
> ⚠️ **Effet de bord voulu** : la ligne H4 lisait `.get("h4_stabilite", {}).get("statut", "VERT")` — une hypothèse ABSENTE s'affichait VERTE. En construisant depuis les clés présentes, elle **n'apparaît plus** au lieu d'apparaître verte. *`a3/C3` reste ouvert sur le CALCUL ; ce qui est fermé, c'est la scorecard qui l'affichait.*

**C9 — La scorecard annonce « 3 ✅ = GLM validé », liste 4 items, et 5 hypothèses sont calculées.** H5 (déviance) — une plafonnante — **n'apparaît pas** dans la scorecard.

> ✅ **`a3/C10`** · **FERMÉ — en alignant la PHRASE sur le CODE, et je dis pourquoi ce sens-là.** Faire entrer le Tweedie dans le statut importerait son Gini, dont **`a3/C6` établit qu'il vaut 0 partout** : on ferait décider un verdict réglementaire par une métrique connue comme cassée. ⚠️ **Deux constats couplés, l'ordre est contraint** — le jour où `a3/C6` sera fermé, la question de l'inclure se reposera. Un test épingle l'absence du Tweedie dans le statut et échouera si on l'y met.

**C10 — `_calculer_statut_rag` annonce « convergence des 3 modèles », en lit 2** : `['gamma', 'poisson']`. Le Tweedie n'entre jamais dans le statut.

> ✅ **`a3/C7` `a3/C11` `a3/C12` `a3/C13` `a3/C15` `a3/C16` `a3/C17` `a3/C18`** · **FERMÉS le 01/09/2026 — LA ZONE `a3` EST CLOSE.** *Preuve : `test_a3_huit_constats.py`, 12 contrôles, **12 violations plantées**.*
>
> ### ⛔⛔ `C7` — LE « MEILLEUR MODÈLE » ÉTAIT PRÉDÉTERMINÉ
>
> `max()` sur `{'poisson': 0,1688, 'gamma': 0,042}` — mais le **Poisson est
> évalué sur TOUT le test** (fréquence) et le **Gamma sur les SINISTRÉS SEULS**
> (sévérité). *Ce ne sont pas deux candidats pour la même tâche : ce sont les
> deux FACTEURS d'un même produit — prime = fréquence × coût.* Un Gini de
> fréquence sur le portefeuille entier dépasse presque toujours un Gini de
> sévérité sur les seuls sinistrés : **`max()` ne mesurait rien, il rendait
> toujours le même nom.**
>
> La clé est **conservée et mise à `None`**, avec son motif — le patron déjà
> validé pour la référence A3 absente d'`a4/C11`. *La retirer casserait un
> lecteur en silence ; la laisser mentir est pire.* Et `comparaison_gini` porte
> désormais **sa population**, pour qu'on ne puisse plus lire deux nombres côte
> à côte comme un classement.
>
> ### ⛔⛔ `C13` — UNE FIGURE ABSENTE QUE PERSONNE NE RÉCLAMAIT
>
> La jauge lisait `h2_homosc["dw_stat"]` ; H2 rend `ratio_variance` depuis
> `87e0609`. Le `KeyError` tombait dans un `except` large : **trois figures de
> validation produites, jamais celle-ci.** *Un `except` large transforme une
> figure ABSENTE en figure JAMAIS RÉCLAMÉE.* ⚠️ **Et le nom change avec la
> grandeur** — Durbin-Watson mesure l'**autocorrélation**, pas
> l'homoscédasticité : garder l'ancien titre sur la nouvelle mesure aurait fait
> publier un nom faux. **Quatre figures désormais.**
>
> ### ⛔ `C15` — LE REPLI CASSAIT LUI-MÊME, ET IL AVAIT UN JUMEAU
>
> `np.full(...)` rend un `ndarray`, qui n'a pas `.values`. *Le chemin de secours
> levait un `AttributeError` à la place de l'erreur qu'il était censé absorber*
> — **la forme de `pipeline/C2`, sur un autre agent.** ⚠️⚠️ **Le constat n'en
> nommait qu'un ; il y en avait DEUX** — la branche fréquence *et* la branche
> sévérité. *Corriger une seule aurait laissé le défaut vivant sur la sévérité,
> et l'asymétrie serait devenue invisible.* `A3-7` les compte par AST.
>
> ### LES CINQ AUTRES
>
> `C11` cinq renvois à `VARS_GLM`, **supprimée** · `C12` `0.05` en dur à deux
> sites à côté de `SEUIL_PVALUE` · `C16` cinq entrées Vie/Santé **conservées et
> dites** (même arbitrage qu'`a5/C8` : en ôter une **ajouterait** une variable ;
> `A3-8` monte la garde) · `C17` un exemple, 3 fois, que le module **refuse**
> (`A3-11` le vérifie *par exécution*) · `C18` « 7 tests » pour **4** méthodes.

**C11 — `VARS_GLM` est supprimé, et 5 lignes y renvoient encore** (l.289, 295, 599, 616, 624) — dont la docstring de `_preparer_donnees` : « On part des variables prioritaires de la sous-branche (VARS_GLM) ».

**C12 — `significatif` code `0.05` en dur** (2 sites) alors que `SEUIL_PVALUE` existe — et il est **toujours vrai**, le stepwise ne retenant que p ≤ 0.05. Un champ sans information.

### C — Imprécis ou daté (6)

**C13 — Le graphique `durbin_watson` n'est jamais produit.** Il lit `val_glm["h2_homosc"]["dw_stat"]` ; H2 rend `ratio_variance` depuis la réparation `87e0609`. `KeyError` avalé → `graphiques_validation = ['gini_comparaison_glm', 'scorecard_validation_glm', 'sur_dispersion_poisson']`. Trois graphiques sur quatre.
**C14 — Une p-value fabriquée à 1.0** sur erreur numérique, 2 sites — elle n'a pas été calculée. La variable écartée est aussi arbitraire (`vars_actives[-1]`), pas celle qui a échoué.
> ✅ **`a3/C14`** · **FERMÉ le 27/08/2026 — `b3dc60c`, en DÉCLARATION SEULE.**
> `pvalue` vaut `None` avec `pvalue_non_testee=True` ; la raison nomme le TYPE
> réel de l'exception sans conclure sur la cause ; le retrait se déclare
> ARBITRAIRE. **Le stepwise est INCHANGÉ, aucun euro déplacé.**
> ⚠️ **LA FRÉQUENCE D'ATTEINTE A ÉTÉ MESURÉE AVANT TOUT CODE** : **0 sur 36**
> exclusions du portefeuille du banc. `statsmodels` ne lève NI sur colinéarité
> parfaite, NI sur colonne constante, NI sur séparation totale — mesuré.
> ⚠️⚠️ **MAIS « JAMAIS ATTEINT SUR CE TEST » N'EST PAS « INATTEIGNABLE »** : le
> `try` couvre ~30 lignes derrière un `except Exception` nu, il attrape aussi
> bien un `KeyError` de `.drop`. *« Erreur numérique » étiquetait une cause que
> rien n'établissait.*
**C15 — Le repli de `predict` casse lui-même** : `np.full(...)` puis `.values` (l.912 et 1146) — un `ndarray` n'a pas `.values`.
**C16 — `COLS_A_EXCLURE`** : 5 entrées sur 23 sont Vie/Santé (`id_salarie`, `id_beneficiaire`, `id_adherent`, `cotisation_mensuelle_eur`, `charge_ij_annuelle_eur`).
**C17 — L'exemple d'usage `run(result_a2)`**, 3 fois dans le module, est refusé par le module.
**C18 — En-tête de test : « 7 tests », 4 méthodes.**

**C19 — Le repli « intercept seul » etait HORS du `try` : les trois calibrations laissaient fuir statsmodels.**

⚠️⚠️ **CONSTAT NEUF, OUVERT ET FERMÉ LE 29/08/2026.** Il ne venait pas du relevé
d'origine : il avait été trouvé lors d'un lot antérieur, noté en mémoire, et
**jamais versé au dépôt**. Il l'est ici. *Une trouvaille qui ne vit que dans une
note n'existe pas pour le prochain lecteur.*

> ✅ **`a3/C19`** · **FERMÉ le 29/08/2026, DANS LE LOT QUI L'A OUVERT.**
> *Preuve : `test_repli_et_palette.py`, 5 contrôles.*
>
> Les trois calibrations d'A3 se replient sur un « intercept seul » quand aucun
> modèle n'a convergé. **Ce repli était HORS de leur `try`** : quand il échouait
> à son tour, une exception BRUTE de statsmodels remontait jusqu'à l'actuaire.
>
> ⚠️⚠️ **LE DÉCLENCHEUR N'EST PAS UNE DONNÉE CORROMPUE** — mesuré sur la vraie
> `_calibrer_poisson` :
>
> ```
>   portefeuille normal                 -> REPOND
>   aucune variable predictive fournie  -> REPOND        (le repli SAIN)
>   PORTEFEUILLE SANS AUCUN SINISTRE    -> *** LEVE ***
>   portefeuille VIDE (0 contrat)       -> *** LEVE ***
>   un NaN dans la cible                -> *** LEVE ***
> ```
>
> Un segment neuf, une branche à faible fréquence : **cas actuariels
> ordinaires**.
>
> ⚠️⚠️ **ET LE MESSAGE PUBLIÉ ÉTAIT CELUI-CI**, mesuré de bout en bout par le
> pipeline :
>
> ```
>   A3 a echoue : The first guess on the deviance function returned a nan.
>   This could be a boundary problem and SHOULD BE REPORTED.
> ```
>
> *Un message interne de statsmodels, qui invite l'actuaire à signaler un bogue
> pour un portefeuille qui n'a simplement pas de sinistre.*
>
> ⚠️⚠️ **ON NE FABRIQUE PAS DE MODÈLE POUR AUTANT — c'est la décision
> actuarielle du lot.** À zéro sinistre, le maximum de vraisemblance de
> l'intercept vaut **log(0)** : aucune valeur finie n'existe. Publier
> « fréquence = 0 » donnerait une **prime pure nulle**, alors que la règle de
> trois donne une borne haute de **3/n**. Le contrat verrouillé par
> `test_pipeline_agents` (PA-4) est le bon : *on ne bricole pas un modèle sur
> rien, on le DIT.* **Ce lot change le CONTENU de l'aveu, pas sa nature.**
>
> ⚠️ **ET LE CONSTAT ÉTAIT PLUS LARGE QUE SON LIBELLÉ** : relevé par AST, les
> **trois** calibrations portaient le même repli nu — Poisson, Gamma, Tweedie.
> Corriger le seul Poisson aurait laissé deux jumeaux identiques.
>
> ⚠️⚠️ **ET J'AI CORRIGÉ UN TEXTE FAUX QUE LA MESURE A DÉMASQUÉ** :
> `test_trop_peu_de_sinistres_le_seuil_est_atteint` disait « à zéro sinistre, **le
> GAMMA** d'A3 meurt avant ». En instrumentant les trois calibrations : c'est le
> **POISSON** qui lève, à l'étape 2 — `_calibrer_gamma` **n'est jamais atteint**.
> La conclusion du test ne bouge pas ; seul le site nommé était faux.
>
> ⚠️ **ET PA-4 S'APPELAIT `erreur_propre` SANS LE VÉRIFIER** : il ne testait que
> `is not None`. Il exige désormais que le message ne contienne pas
> « should be reported » **et** qu'il nomme ce qui a été observé.
>
> ⚠️ `CalibrationImpossible` hérite de `ValueError` **à dessein** : c'est ce que
> statsmodels levait déjà. Un appelant qui filtrait `except ValueError` continue
> de fonctionner — *le correctif enrichit le message, il ne déplace pas le
> type.*

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
