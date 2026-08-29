# RELEVÉ A5 — DEEP LEARNING (CANN + TabNet)

**Lu intégralement** : `a5_deep_learning/agent.py` **2 232 l** + `test_a5_deep_learning.py` **268 l**.

## ① Le compte

**17 affirmations mesurées** — 9 constats · 8 vérifiées bonnes. **C'est l'agent au meilleur ratio du lot**, et son défaut central est d'une seule cause.

## ② Le classement

### A — Publie du FAUX à un actuaire qui signe (6)

> ✅ **`a5/C2`** · **FERMÉ — vérifié le 27/08/2026 par deux méthodes.**
> **① Code d'aujourd'hui** : `histo_h1 = historiques.get(_cle_h1) or []` (l.2014) — H1 lit l'historique **réel**, elle n'en simule plus.
> **② `REMESURE_A3_A4_A5.md` (25/08)** l'établissait déjà, l.2004-2014.

> ✅ **`a5/C1`** · **LA CAUSE NOMMÉE PAR CE CONSTAT EST DÉJÀ FERMÉE.** Mesuré le 25/08/2026 :
> `_valider_hypotheses_dl` lit `metriques.get('cann', {}).get('gini_test', 0)` —
> **la bonne clé**. Le `.get('gini', 0)` a disparu. *Correctif présent dans le
> code, jamais reporté ici.*
>
> ⚠️⚠️ **MAIS LA MESURE A TROUVÉ UN DÉFAUT ADJACENT, ET JE LE DISTINGUE DU
> CONSTAT** : `gini_dl_max = max(gini_cann, gini_tabnet, **0**)` — un plancher
> à zéro qui publiait « Gini DL = **0.0000** » là où la mesure valait
> **−0,1083**. *Un zéro qui signifie « écrêté » est indiscernable d'un zéro
> mesuré* — même famille qu'`a3/C6`. Un Gini négatif est une **information** :
> il dit que le modèle classe à l'envers ; l'écrêter le fait passer pour « sans
> pouvoir discriminant », ce qui est plus flatteur que la réalité. **Corrigé.**
> ⚠️ **CE QUI CHANGE ET CE QUI NE CHANGE PAS, séparément** : le **VERDICT** est
> identique (ROUGE avant, ROUGE après) ; **le NOMBRE PUBLIÉ** change.
>
> ⚠️⚠️ **ET LE SYMPTÔME DU CONSTAT N'EST PAS REPRODUIT** : « trois hypothèses
> ROUGE sur un CANN **excellent** ». Sur le portefeuille du banc, le CANN
> obtient **−0,1103** — il n'est pas excellent, et le ROUGE y est justifié.
> *Je ne peux donc pas vérifier que la correction de clé suffit : il faudrait un
> portefeuille où le DL discrimine réellement.* **À instruire, pas à clore.**

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

> ✅ **`a5/C4`** · **FERMÉ le 29/08/2026 — ET PAS EN SEMANT LE BRUIT.**
> *Preuve : `test_avertissement_dl_et_courbe.py`, 5 contrôles.*
>
> ⚠️⚠️ **LE REMÈDE ÉVIDENT ÉTAIT LE MAUVAIS.** J'avais moi-même annoncé
> « semer le bruit » — c'était faux, et je le corrige ici : semer aurait rendu
> une courbe **fabriquée** reproductible, donc **crédible**. On aurait échangé
> un défaut visible contre un défaut invisible. *Un aléa retiré d'une donnée
> inventée ne la rend pas mesurée.*
>
> ⚠️⚠️ **LES VRAIES PERTES EXISTAIENT DÉJÀ, ET ÉTAIENT JETÉES.**
> `_calibrer_cann` et `_calibrer_tabnet` empilent `{'epoch','train','val'}`
> époque par époque (l.1188 et l.1342) ; le résultat les porte sous
> `historique_cann` / `historique_tabnet`, avec `n_epochs_reels`. La figure
> les ignorait et simulait.
>
> ⚠️ **ET LE CORRECTIF ÉTAIT DÉJÀ ARRIVÉ À CÔTÉ UNE FOIS.** Un lot antérieur
> avait fait cesser la simulation dans **la validation** — le commentaire
> l'annonce noir sur blanc : *« H1 NE SIMULE PLUS SES LOSSES »*. La **FIGURE**,
> elle, continuait. *Corrigé dans ce qui juge, pas dans ce qui est montré* —
> le motif de [[correctif-a-cote-de-la-surface]].
>
> **Mesuré après correctif, deux exécutions identiques :**
>
> ```
>   epoques tracees = (1, 2, 3)          <- le releve en simulait 50
>   train tracee = [1727.661, 1623.403, 1466.265]
>   train REELLE = [1727.661, 1623.403, 1466.265]   <- egalite exacte
>   val   tracee = [1717.849, 1588.604, 1441.543]
>   val   REELLE = [1717.849, 1588.604, 1441.543]
>   COURBES IDENTIQUES ENTRE LES DEUX RUNS : True
> ```
>
> ⚠️ **LA ZONE « CONVERGENCE » NE S'AFFICHE PLUS SOUS 6 ÉPOQUES** : sur 3, un
> « dernier tiers » couvrirait presque toute la courbe. *Un repère qui couvre
> tout ne repère rien.*
> ⚠️ **SANS HISTORIQUE, LA FIGURE LE DÉCLARE** (« AUCUNE DONNÉE — historique
> d'entraînement ») et ne trace **aucun** point — elle ne se rabat sur aucune
> formule. Leçon de `charts/C3`.
> ⚠️ **`numpy` A DISPARU DE L'IMPORT DES FIGURES A5**, et c'est le signal du
> lot : il ne servait qu'à fabriquer. *Ces figures ne calculent plus rien.*
> ⚠️ **DEUX FILETS, PAS UN** : un test par l'EFFET (deux appels, même figure)
> et un test par AST (`0 np.random.*`). Un tirage **semé** passerait le second
> et serait pourtant une courbe fabriquée — les deux ensemble disent « ni
> fabriqué, ni aléatoire ».
> ⚠️ **CE CONSTAT ÉTAIT L'UN DES QUATRE LATENTS**, fermés à toute ouverture.
> Selasse l'a rouvert explicitement le 29/08. Il en reste **trois**.

**C5 — Le graphique « DL vs GLM » met les deux modèles DL à zéro.**
```
  barres [GLM, CANN, TabNet] = [0.14, 0, 0]
  Gini REELS  CANN / TabNet  = [0.4781, 0.0950]
```
La légende dit « Les barres bleue/dorée doivent dépasser la ligne pointillée (GLM). Si non → DL non justifié. » — **elles ne le peuvent pas.**

> ✅ **`a5/C5`** · **FERMÉ le 29/08/2026 — ET IL SE REPRODUISAIT ENCORE.**
> *Preuve : `test_convergence_et_barres_dl.py`, 4 contrôles.*
>
> ⚠️ **LA PREMIÈRE CAUSE ÉTAIT DÉJÀ CORRIGÉE, JAMAIS ÉPINGLÉE.** L'archive le
> classait « corrigé, non épinglé » : la figure lisait la mauvaise clé, elle
> lit la bonne depuis. Mesuré : `[0,14 · 0,4781 · 0,0950]`, les Gini réels.
>
> ⚠️⚠️ **MAIS LE SYMPTÔME DU RELEVÉ SE REPRODUISAIT, PAR UNE AUTRE CAUSE** —
> mesuré AVANT ce lot :
>
> ```
>   les deux modeles ENTRAINES        barres = [0.14, 0.4781, 0.095]
>   CANN ABSENT (calibration echouee) barres = [0.14, 0.0,    0.095]
>   LES DEUX ABSENTS                  barres = [0.14, 0.0,    0.0]
> ```
>
> `self.metriques['cann']` n'existe **que** si la calibration a réussi ; le
> `.get(..., 0)` transformait une absence en performance nulle. **La dernière
> ligne rend EXACTEMENT les nombres du relevé** (`[0.14, 0, 0]`).
> *Épingler sans fermer cette cause aurait certifié un constat qui se
> reproduit encore* — un filet à l'assiette trop étroite.
>
> **CORRECTIF** : un modèle non calibré est **retiré** de la figure, et son
> absence est **écrite sous l'axe** (« Non tracé(s), car non calibré(s) : … —
> absence, pas Gini nul »), patron de `charts/C5`. Si **aucun** DL n'est
> calibré, la figure déclare « AUCUNE DONNÉE » au centre — la légende promet
> des « barres bleue/dorée » qui n'existeraient pas.
> ⚠️ *Un zéro qui signifie « jamais entraîné » est indiscernable d'un zéro
> mesuré* — même leçon qu'`a3/C6` et que le plancher d'A5.
> ⚠️ La palette suit le nombre de barres : sans cela, le modèle restant
> aurait pris la couleur de l'absent.

**C6 — L'early stopping se règle sur le jeu de TEST.**
```
  _calibrer_cann   : val_loss sur X_test_t (X_test_t <- X_test) · best_state selectionne dessus
  _calibrer_tabnet : idem
  jeu de VALIDATION distinct : False (aucun)
```
La docstring annonce « la perte de **validation** ». Il n'y a pas de jeu de validation : les poids retenus sont ceux qui minimisent la perte **sur le test**, et le Gini test publié est donc optimiste. Le module cite pourtant Kaufman et al. (2012) sur la fuite — et l'évite correctement pour le scaler.

> ✅ **`a5/C6`** · **FERMÉ — lot 1.1.** Trois jeux désormais : **68 % train · 12 % validation · 20 % test**, la validation découpée **avant** le scaler comme le test. Les deux calibrateurs **exigent** `X_val`/`y_val` (`raise ValueError`) : aucun repli silencieux vers le test ne peut rouvrir la fuite. `y_test` n'est même plus tensorisé.
> **⚠️ L'OPTIMISME QUE CETTE FUITE CACHAIT, mesuré à seed constant :**
> ```
>   CANN     0.3019 -> 0.2998    -0.0021    -0.7 %
>   TabNet   0.2269 -> 0.1970    -0.0299   -13.2 %
> ```
> Le CANN bouge peu, il est ancré sur un GLM gelé. **TabNet publiait un Gini 13 % trop haut.** Contrôle positif `POS_A5e` (3 tests), relevé **par AST** sur la ligne `pred_val = modele(...)`, avec **violation plantée** — un retour au test est attrapé.
> ⚠️ **POS-A5a survit** : le DL reste devant le GLM (0,2998 > 0,1400). La correction **baisse le chiffre sans inverser le verdict**.

### B — Affirme plus que le code ne porte (1)

**C7 — Aucun seed n'est fixé : le modèle n'est pas reproductible.**
```
  0 appel a un seed dans le module
  deux runs IDENTIQUES -> Gini TabNet 0.0432 puis 0.0649
```
Le fichier de test le note lui-même : *« A5 n'en fixe AUCUN → sans ces lignes le Gini diffère à chaque exécution »* — et le compense de l'extérieur. Le dépôt invoque ailleurs « Exigence S2 : tout calcul actuariel doit être reproductible ».

> ✅ **`a5/C7`** · **FERMÉ — lot 1.1.** `run(seed=42)` : paramètre **déclaré, surchargeable, et inscrit au rapport** — un actuaire qui rejoue un tarif retrouve le seed. Posé dans `run()`, **jamais au niveau module** (ce serait le défaut `a1/C6` sous un autre nom).
> **⚠️ CE QUE LA NON-REPRODUCTIBILITÉ COÛTAIT**, trois exécutions strictement identiques :
> ```
>   CANN    0.3027 · 0.3018 · 0.3033   etendue 0.0015    0.5 %
>   TabNet  0.2158 · 0.2379 · 0.2420   etendue 0.0262     11 %
> ```
> **C'est sur ce Gini qu'A6 ARBITRE** : deux exécutions du même portefeuille pouvaient retenir deux modèles différents. Après correctif, étendue **0,0000**.
> ⚠️ **CE QUE LE SEED NE GOUVERNE PAS**, et c'est délibéré : la **partition** des jeux garde un `random_state=42` fixe. Une partition qui suivrait le seed changerait le jeu de test d'une exécution à l'autre — comparer deux seeds ne voudrait plus rien dire. *La partition est une propriété du protocole, l'aléa d'optimisation une propriété du calibrage.*
> Contrôle positif `POS_A5d` (3 tests), **dans les deux sens** : même seed → identique, **seed 7 vs 8 → différent** (sans ce second sens, un `seed` jamais lu passerait le premier).

### C — Imprécis ou daté (2)

**C8 — `COLS_A_EXCLURE`** : 5 entrées Vie/Santé sur 20, comme A3 et A4.
**C9 — En-tête de test : « 7 tests », 3 méthodes.**

**C10 — Le verdict de convergence portait sur le mauvais modèle.**

⚠️⚠️ **CONSTAT NEUF, TROUVÉ PARCE QU'UN CORRECTIF DE LA VEILLE A RENDU VISIBLE
UN DÉFAUT CACHÉ.** Le lot 4.5 a fait tracer les vraies pertes au lieu d'une
courbe simulée. Mesuré ensuite sur deux runs réels :

```
  portefeuille 2500 : classement A5 tete = CANN               -> 3 points
  portefeuille 3000 : classement A5 tete = 'GLM Poisson (A3)' -> 0 point
                      (cann=3 et tabnet=3 historiques EXISTAIENT)
```

`_cle_h1 = classement[0]['modele'].lower()` : le classement **interne** d'A5
contient aussi le GLM d'A3 et le meilleur ML d'A4. Quand l'un d'eux gagne,
`historiques.get('glm poisson (a3)')` ne trouve rien — et H1 publie
« convergence NON mesurée », **statut ROUGE**, sur une hypothèse qui parle de
la convergence du **Deep Learning**. *Le verdict portait sur le mauvais objet,
et il atteint l'Excel (`tarif_excel.py:440`).*

⚠️ **AVANT LE LOT 4.5, CE CAS FABRIQUAIT UNE COURBE PLATE À ZÉRO** étiquetée
« Convergence ». Le correctif a échangé un mensonge silencieux contre un trou
visible — c'est le trou qui a livré le défaut.

> ✅ **`a5/C10`** · **FERMÉ le 29/08/2026.**
> *Preuve : `test_convergence_et_barres_dl.py`, 5 contrôles.*
>
> On parcourt le classement **dans son ordre** et on retient le premier modèle
> qui **possède un historique** : c'est donc le MEILLEUR des DL.
> ⚠️⚠️ **ON FILTRE PAR LA DONNÉE PRÉSENTE, PAS PAR UNE ÉTIQUETTE.** Le
> classement porte bien `type == 'Deep Learning'`, mais s'y fier ferait
> dépendre un verdict réglementaire d'un **libellé** — le défaut que ce
> chantier poursuit (`controle-assiette-et-exemption`, 7ᵉ forme). Seuls les
> modèles DL ont un historique : **avoir une entrée dans `historiques` EST le
> critère**, et il ne peut pas mentir.
> ⚠️ **LE NOM SUIT L'HISTORIQUE** : `modele_nm` valait `classement[0]`, donc
> le conseil aurait dit « GLM Poisson (A3) a bien convergé » en lisant les
> pertes du CANN.
> ⚠️⚠️ **SECOND SENS** : sans aucun DL au classement, le verdict reste ROUGE
> « non mesurée » — le correctif ne fabrique pas de verdict. C'est ce que
> `test_epinglage_fermes_vivants` épingle déjà ; **il passe inchangé**, et le
> nouveau lot le revérifie parce qu'il touche la recherche qu'il exerce.
> ⚠️ **ET UNE VIOLATION PLANTÉE N'EST PAS TOMBÉE** : remplacer
> `historiques.get(_cle)` par `_cle in historiques` ne change rien, parce que
> le `if classement and histo_h1` en aval retient déjà le cas. *J'attribuais
> la protection au mauvais mécanisme* — le test le dit désormais lui-même.

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
