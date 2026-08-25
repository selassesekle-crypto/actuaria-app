# RELEVÉ — `pipeline_tarifaire.py`, LE CHEMIN QUI CALCULE LE PRIX

**Lu intégralement** : `pipeline_tarifaire.py` **343 l**. Aucun échantillon,
aucun filtre. Premier fichier du relevé ②, celui du chemin déclaratif.

## ① Le compte

**19 affirmations mesurées** — **9 constats** · **10 vérifiées bonnes**.
**1 de mes soupçons corrigé par l'oracle du dépôt.**

## ② Le classement

### A — Publie du FAUX à un actuaire qui signe (1)

**C1 — Un facteur tarifaire ILLISIBLE produit une prime, et `success = True`.**
`tarifer()` accepte n'importe quoi et rend un prix sans un mot.

```
  contrat de reference          prime_pure =  28.50   success=True
  bonus_malus = 'beaucoup'      prime_pure =  64.99   success=True   +128.0 %
  bonus_malus = ''              prime_pure =  64.99   success=True   +128.0 %
  bonus_malus = None            prime_pure =  64.99   success=True   +128.0 %
  bonus_malus = -999            prime_pure =  22.96   success=True    -19.4 %
  bonus_malus = 1e12            prime_pure = 149.79   success=True   +425.6 %
```

Les trois premières valeurs rendent **la même** prime : elles sont toutes
coercées vers le même repli (l'imputation d'A2). Le souscripteur reçoit donc
**la prime du contrat moyen** en croyant tarifer le sien, et **rien ne le
signale** — le contrat de sortie dit `success: True`.

⚠️ **Le chemin vectoriel ne dit rien non plus** : `predire_portefeuille` sur un
`bonus_malus = 'beaucoup'` rend `[38.36, 128.81, 3.65]` sans lever.

⚠️ **`-999` et `1e12` sont acceptés tels quels** — un bonus-malus négatif et un
bonus-malus de mille milliards produisent des primes que le module signe.
**Aucune borne de plausibilité n'existe sur le chemin déclaratif** : A1 en
porte (`[16, 99]` pour l'âge), mais **le chemin déclaratif ne passe pas par
A1** — le commentaire l.276 le dit lui-même.

*Preuve : `preuves/audit_pipeline_ter.py`.*

> ✅ **FERMÉ POUR L'ILLISIBILITÉ — lot `pipeline/C1`. ET PAS POUR LA
> PLAUSIBILITÉ : les deux ne se confondent pas.**
>
> `tarifer()` refuse désormais **avant** de tarifer, via
> `anomalies_du_contrat()` qui compare le contrat **au plan signé** — comme A2
> le fait déjà en refusant une modalité inconnue (piège V9). Mesuré :
> ```
>   bonus_malus = 'beaucoup'   success=False   « valeur ILLISIBLE »
>   bonus_malus = ''           success=False   « valeur ABSENTE »
>   bonus_malus = None         success=False   « valeur ABSENTE »
> ```
> ⚠️ Le motif dit **pourquoi le prix serait faux** : *« la prime rendue serait
> celle du contrat MOYEN, pas celle de ce contrat »*. Un refus sans motif
> renvoie l'actuaire à la devinette.
> ⚠️ Le contrat de sortie **reste stable en refus** — `success`,
> `plan_empreinte`, `date_calcul`, sérialisable JSON : c'est ce que la
> docstring promet, succès comme erreur.
>
> ⚠️⚠️ **CE QUI RESTE OUVERT, ET C'EST DÉLIBÉRÉ** : `-999` et `1e12` sont
> encore tarifés. Ils sont **lisibles** — et **aucune borne de plausibilité
> n'est déclarée dans le plan**. En inventer une ici serait poser un chiffre
> actuariel que personne n'a signé. **Un test épingle cette limite** : s'il se
> met à échouer, c'est qu'une borne a été ajoutée, et il faudra vérifier
> qu'elle vient du PLAN.
>
> ⚠️ **`predire_portefeuille` N'EST PAS TRAITÉ, et c'est une question de
> conception** : il reçoit un portefeuille entier par le même chemin. Refuser
> tout parce qu'une ligne est illisible serait faux ; signaler ligne par ligne
> demande de décider ce que le contrat de sortie vectoriel doit porter. Rendu.
>
> ⚠️ **La modalité catégorielle inconnue était DÉJÀ couverte** par `INV-7c` —
> je ne l'ai pas dupliquée, et elle passe toujours.
> Contrôle positif : `test_tarifer_contrat.py`, **6 tests**, dont **3 dans le
> second sens** (contrat valide, nombre écrit en texte, limite épinglée).

### B — Affirme plus que le code ne porte (5)

**C2 — Le repli « dégénéré mais défini » n'est JAMAIS atteint.** Le commentaire
l.323 annonce « aucun coût observé : coût moyen constant (dégénéré mais
défini) ». Mesuré sur un portefeuille sans aucun sinistre :

```
  n_retenus = 0            -> le repli l.323 EST bien la branche visee
  ValueError: The first guess on the deviance function returned a nan
  leve a pipeline_tarifaire.py:305   <-- le GLM de FREQUENCE
```

**Le pipeline meurt vingt lignes plus tôt**, sur le GLM de fréquence, avant
d'atteindre le repli du coût. Le repli existe, il est correct, et il est
inaccessible dans le seul cas qu'il prétend couvrir.

**C3 — « UNE SEULE définition » du Gini, et il y en a cinq.** La docstring
l.193-196 dit : « UNE SEULE définition, utilisée à l'identique pour le Gini de
test ET le Gini walk-forward — c'est ce qui rend impossible la *métrique
divergente* de B9 (INV-6) ». Mesuré :

```
  autres definitions : a6_comparaison::_gini_lorenz
                       a3_glm::_calculer_gini
                       a4_ml::_calculer_gini
                       a5_deep_learning::_calculer_gini
```

L'affirmation est vraie **à l'intérieur de ce fichier** — le test et le
walk-forward y partagent bien `gini_lorenz`. Elle est fausse à l'échelle du
module, et c'est ainsi qu'elle se lit.

**C4 — Les chargements « déclarables dans le plan » ne le sont pas.** Le
commentaire l.35-36 dit « Déclarables dans le plan (étape 6) ; ici en repli
neutre ». Mesuré : `PlanTarifaire` **ne porte aucun champ `chargements`** — le
repli est le seul chemin, et l'étape 6 annoncée n'existe pas.

**C5 — « Taxes : auto 33 %, MRH 30 %, RC 9 % » — un seul taux est appliqué.**
Le commentaire l.36 énumère trois taux par LoB. `CHARGEMENTS_DEFAUT` porte
`"taxes": 0.33` **en dur, pour toute LoB**. Une MRH tarifée par ce chemin
reçoit la taxe auto.

**C6 — `grille()` annonce des relativités exportables et ne porte que la
fréquence.** Docstring l.177 : « Relativités exportables (ce que l'assureur met
dans son SI) ». Mesuré : `colonnes = ['colonne', 'relativite_frequence']`. La
prime pure est `fréquence × coût moyen` — **la moitié du tarif manque à la
grille que l'assureur est invité à mettre dans son SI.**

### C — Imprécis ou daté (3)

**C7 — La docstring attribue à `tarifer()` une précision que seul le chemin
vectoriel tient.** L.122-123 : « MÊME chemin que `tarifer()`, pour que l'un
reproduise l'autre à 1e-6 ». Or `tarifer()` **arrondit** `prime_pure` à deux
décimales (l.162) : la coïncidence à 1e-6 n'est pas observable sur sa sortie.
⚠️ **L'oracle du dépôt, lui, est juste** — et c'est lui qui m'a corrigé :
`test_scoring_unitaire_reproduit_le_portefeuille_a_1e6` compare le chemin
vectoriel **à lui-même, non arrondi**, et `test_tarifer_livrable_reproduit_au_centime`
est un test **séparé**, au centime. Les tests distinguent les deux précisions ;
la docstring les confond.

**C8 — Asymétrie de protection contre les NaN dans la même fonction.**
Mesuré : `fillna` présent sur `cout_total` (l.314), **absent** sur `expo`
(l.299) et sur `y_freq` (l.300). Les trois passent par `pd.to_numeric(...,
errors="coerce")`, qui produit des NaN silencieux ; un seul les traite.
⚠️ **Sans conséquence observée** : une exposition illisible provoque un arrêt
*loud* (voir D). Mais la protection tient par accident, pas par construction.

**C9 — Deux horodatages, deux fuseaux, dans la même chaîne.** `tarifer()` pose
`datetime.now(timezone.utc)` (l.146) ; `pipeline_complet` passe
`horodatage=datetime.now()` (l.279), en heure locale. Deux traces du même
calcul ne portent pas la même heure.

### D — Vérifié comme BON (10)

| affirmation | mesure |
|---|---|
| `tarifer()` reproduit `predire_portefeuille` | écart max **0,0036 €** sur 6 contrats — l'arrondi au centime, rien de plus |
| le taux de fréquence est **par unité d'exposition** | Σobs / Σfreq = 0,6012 · **Σobs / Σ(freq × expo) = 1,0000** |
| le coefficient d'équilibre ramène à ±1 % | **Σprime / Σcharge = 1,0000** (k = 0,9574) |
| le seuil INV-6 annoncé (0,40) est **appliqué** | oui, dans `test_plan_invariants.py` |
| une exposition illisible **arrête loud** | `ValueError: NaN, inf or invalid value detected in endog` — jamais un silence |
| le **filtre genre** (CJUE C-236/09) tient | `'sexe'` ajouté au portefeuille → **absent des features ajustées** |
| la couche qualité **BLOQUE** au-delà de 5 % | 13 % d'expositions négatives → `QualiteBloquante` levée |
| le walk-forward produit ce qu'il annonce | 4 fenêtres demandées, **4 produites**, écart relatif 0,2518 |
| la formule de prime commerciale | `pc = 22,14` = `pp × (1+frais) × (1+marge) / (1−commission)`, au centime |
| **reproductibilité** de l'ajustement | deux ajustements identiques → écart **0,00e+00** |

### Mon soupçon corrigé par le dépôt

J'ai d'abord classé la précision « 1e-6 » comme une affirmation invérifiable.
**L'oracle `INV-7` du dépôt m'a corrigé** : il vérifie 1e-6 sur le chemin
vectoriel et « au centime » sur `tarifer()` — deux tests distincts, chacun
juste. Le défaut est dans la docstring, pas dans la mesure. C'est un cas où
**le test en savait plus que le commentaire**.

## ③ Ce que je n'ai pas lu — et ce que je ne peux pas trancher ici

**Rien n'est resté non lu** : 343 lignes, intégralement.

Deux points **non tranchables dans ce fichier**, qui relèvent des modules
qu'il appelle et que je lirai ensuite :

- **`construire_matrice_x`** (`core/conformite_reglementaire.py`, 1 318 l) —
  j'ai vérifié qu'il **écarte le genre** ; je n'ai pas vérifié la fuite ni
  l'antériorité, qui sont ses deux autres garde-fous annoncés.
- **`controler_qualite`** (`core/qualite_donnees.py`, 334 l) — j'ai vérifié
  qu'il **bloque à 13 %** ; je n'ai pas vérifié les quatre règles une par une,
  ni le seuil exact de 5 %.

## ④ Les preuves

`preuves/audit_pipeline.py` (19 mesures), `audit_pipeline_bis.py`
(instruction de C2 et du contrat de sortie), `audit_pipeline_ter.py` (le
facteur illisible, la ligne qui lève, l'oracle INV-7). Chacune se relance
seule.

⚠️ **Ma première fixture était écrite à la main et elle s'est périmée
immédiatement** — deux facteurs du plan manquaient. Elle est désormais
**construite depuis le plan**, comme le contrôle POS-A2a.

---

**Mon appréciation d'ensemble.** Ce fichier est **le meilleur du module sur ce
qui décide** : l'équilibre technique tombe à 1,0000, la fréquence est
exactement par unité d'exposition, le filtre genre tient, la couche qualité
bloque vraiment, et l'ajustement est reproductible au bit près. Les sept
mécanismes qu'il annonce comme siens fonctionnent.

⚠️ **Le seul constat grave ne vient pas de son calcul, mais de sa PORTE
D'ENTRÉE** : `tarifer()` accepte une valeur écrite en toutes lettres et rend
un prix en disant `success: True`. Le chemin déclaratif ne passe pas par A1 —
son commentaire l.276 l'assume — et **personne d'autre ne vérifie la
plausibilité de ce qui entre.**
