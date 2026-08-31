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

> ✅ **`pipeline/C1`** · **FERMÉ POUR L'ILLISIBILITÉ — lot `pipeline/C1`. ET PAS POUR LA
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

> ✅ **`pipeline/C2`** · **FERMÉ le 01/09/2026 — ET LE CONSTAT EST RÉFUTÉ SUR
> SA FORME, CE QUI RESTE ÉTANT PIRE.** *Preuve : `PC-1`, `PC-2`, `PC-3`.*
>
> Il concluait « branche JAMAIS atteinte » à partir d'un portefeuille **sans
> aucun sinistre**. Ce cas-là meurt bien vingt lignes plus tôt — mais sur le
> **GLM de fréquence**, pas faute d'atteindre le repli. *Le constat visait
> juste et se trompait de porte.*
>
> **La branche EST atteinte par l'autre cas** : des sinistres **comptés**,
> aucun coût **positif**. Et mesuré le 01/09 — **elle meurt elle-même**, l.570,
> parce qu'elle ajustait un GLM Gamma sur **UNE observation** et ~24
> paramètres. *« Dégénéré mais défini » n'était ni l'un ni l'autre.*
>
> ⚠️⚠️ **ET LES DEUX MORTS PORTAIENT LE MESSAGE DE `pipeline/C8`** — « *the
> deviance function returned a nan … should be reported* ». *L'actuaire était
> invité à signaler un bug à `statsmodels` là où son portefeuille n'avait
> simplement aucun sinistre.* Les deux impossibilités sont désormais **nommées
> avant le solveur**, et la seconde renvoie au signalement que la couche
> qualité produit déjà (`incoherence_sin_sans_cout`).
>
> ⚠️ **Aucun euro : il n'y avait pas de prix, il n'y en a toujours pas — mais
> on dit pourquoi.** `PC-3` vérifie le second sens : un portefeuille normal
> tarife.

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

> ✅ **`pipeline/C1` — LE RÉSIDU EST FERMÉ le 31/08/2026.** Il n'est donc plus
> PARTIEL : *l'exception codée en dur qui l'excluait du compte a été retirée.*
> *Preuve : `PTE-5`, `PTE-6`, `PTE-7`, `PTE-12`.*
>
> Il était fermé pour l'**illisibilité**, ouvert pour la **plausibilité** :
> `bonus_malus = -999` est un flottant parfaitement LISIBLE et rendait toujours
> un prix (−19,4 %). *Le plan déclarait le TYPE d'un facteur continu, jamais son
> DOMAINE* — exactement la forme d'`unite_exposition`. `modalites` bornait les
> catégoriels ; **le continu n'avait rien**.
>
> `Facteur.bornes` existe, est validé à la déclaration (triplet, `min >= max`,
> non-nombre, borne sur un catégoriel : refusés), **est dans l'empreinte** — une
> borne refuse un contrat, donc elle change ce qui est tarifé — et le refus
> **nomme la borne signée** : *l'actuaire doit pouvoir vérifier le refus contre
> son plan.*
>
> ⚠️⚠️ **ET LA FERMETURE AURAIT ÉTÉ À MOITIÉ SANS LA PHRASE.** **0/20 plans
> déclarent des bornes** : `-999` est donc toujours tarifé aujourd'hui. Sans le
> dire, on aurait fermé sur le mécanisme seul. `tarifer()` publie désormais
> `domaines_non_declares` — 9 facteurs continus sans bornes sur `auto` — et se
> tait dès que tous sont bornés (`PTE-12`). *Le même piège qu'`unite_exposition`
> aurait eu si l'hypothèse annuelle était restée muette.*
>
> ⚠️ **Aucune borne n'est inventée** : ce sont des choix actuariels qui
> demandent une source. **Aucun euro ne bouge**, `PTE-6` et `PTE-11` le tiennent.

**C4 — Les chargements « déclarables dans le plan » ne le sont pas.** Le
commentaire l.35-36 dit « Déclarables dans le plan (étape 6) ; ici en repli
neutre ». Mesuré : `PlanTarifaire` **ne porte aucun champ `chargements`** — le
repli est le seul chemin, et l'étape 6 annoncée n'existe pas.

**C5 — « Taxes : auto 33 %, MRH 30 %, RC 9 % » — un seul taux est appliqué.**
Le commentaire l.36 énumère trois taux par LoB. `CHARGEMENTS_DEFAUT` porte
`"taxes": 0.33` **en dur, pour toute LoB**. Une MRH tarifée par ce chemin
reçoit la taxe auto.

> ✅ **`pipeline/C4` + `pipeline/C5`** · **FERMÉS ENSEMBLE le 31/08/2026 — C'EST
> UNE SEULE QUESTION, PAS DEUX.** *Preuve : `test_portes_du_plan.py`,
> 11 contrôles, **10 violations plantées**.*
>
> `C4` disait que les chargements « déclarables dans le plan (étape 6) » ne
> l'étaient pas ; `C5` en est la **conséquence** sur l'entrée la plus chère.
> *Les corriger séparément aurait réparé deux fois le même défaut.*
>
> **Impact mesuré sur la prime TTC** — `PTE-4` le vérifie par exécution :
>
> ```
>   MRH : 33 % au lieu de 30 %  ->  x 1,0231   (+2,31 %)
>   RC  : 33 % au lieu de  9 %  ->  x 1,2202  (+22,02 %)
> ```
>
> ⚠️ **LATENT, ET IL FAUT LE DIRE** : `prime_ttc` n'a **qu'une occurrence**
> dans le dépôt — sa propre construction. Aucun service ne la lit ; seuls des
> tests l'assertent `> 0`. *C'est la surface publique de `tarifer()`, pas un
> rapport signé.*
>
> **`PlanTarifaire.chargements`** est déclarable, validé (`commission >= 1`
> divise par zéro → refusé), **et dans l'empreinte** : une taxe décide de la
> prime payée, donc elle est opposable. Ordre explicite : **l'appelant, puis
> le PLAN, puis le repli** — et *quand le repli s'applique, il est DIT*
> (`chargements_supposes`, publié par `tarifer()`, `None` si le plan déclare).
>
> ⚠️⚠️ **AUCUN TAUX N'EST INVENTÉ.** Les vrais taux par LoB demandent une
> source (le CGI) : **0/20 plans déclarent**, le repli s'applique partout à
> l'identique, **aucun euro ne bouge**. `PTE-11` le tient. *Le jour où un plan
> déclarera sa vraie taxe, l'euro bougera — jusqu'à −22 % sur la RC — et ce
> sera un ARBITRAGE, pas un effet de bord.*


> ✅ **`pipeline/C3`** · **FERMÉ le 01/09/2026 — LA PHRASE LIMITE DÉSORMAIS SA
> PORTÉE.** *Preuve : `PC-4`, `PC-5`.*
>
> Elle disait « UNE SEULE définition ». C'est **vrai dans ce module** — le Gini
> de test et le Gini walk-forward passent tous deux par là, et c'est ce qui rend
> impossible la « métrique divergente » de B9. Ce n'est **pas vrai à l'échelle
> du dépôt**.
>
> ⚠️ **LE CHIFFRE ET SA MÉTHODE, CÔTE À CÔTE.** Le constat annonçait cinq
> définitions ; mesuré par AST le 01/09, **8 fonctions de production calculent
> réellement un coefficient** — critère publié : leur corps emploie `cumsum`,
> `trapz` ou une courbe de Lorenz — et 2 autres portent `gini` dans leur nom
> sans en calculer (une réserve, un verdict). ⚠️ **Le sens de l'erreur est
> dit** : le critère **sur-compte**, il ne sous-compte pas. `PC-5` re-dérive le
> nombre au lieu de croire la phrase.
>
> ⚠️ *Une phrase qui LIMITE est sûre ; une phrase qui AFFIRME au-delà de ce
> qu'elle tient est une dette.*

**C6 — `grille()` annonce des relativités exportables et ne porte que la
fréquence.** Docstring l.177 : « Relativités exportables (ce que l'assureur met
dans son SI) ». Mesuré : `colonnes = ['colonne', 'relativite_frequence']`. La
prime pure est `fréquence × coût moyen` — **la moitié du tarif manque à la
grille que l'assureur est invité à mettre dans son SI.**

### C — Imprécis ou daté (3)

> ✅ **`pipeline/C6`** · **FERMÉ le 01/09/2026 — LA GRILLE PORTE LES DEUX
> MOITIÉS DU TARIF.** *Preuve : `PC-6`, `PC-7`.*
>
> Elle ne rendait que `relativite_frequence`, alors que la prime pure est
> **fréquence × coût moyen**. *L'assureur était invité à mettre dans son SI une
> grille dont il manquait un facteur sur deux.*
>
> Trois colonnes désormais — et `PC-6` vérifie que la troisième **est le
> produit** des deux premières, pas deux nombres posés côte à côte. ⚠️ **Aucun
> euro** : `grille()` n'entre dans aucun calcul de prime, elle EXPOSE ce que les
> deux GLM portent déjà. `PC-7` tient le second sens : une variable inconnue
> rend une grille **vide**, colonnes stables.

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

> ✅ **`pipeline/C8`** · **FERMÉ le 31/08/2026 — ET LA RACINE N'ÉTAIT PAS CELLE
> QUE CE CONSTAT DÉCRIT.** *Preuve : `PTE-8`, `PTE-9`, `PTE-10`.*
>
> Le constat annonce une asymétrie de `fillna`. **Mesuré** :
>
> ```
>   couche qualite -> valeur_illisible_exposition        5 lignes  (regle 3)
>                     valeur_illisible_cible_frequence   4 lignes  (regle 3)
>   NaN SURVIVANTS dans le dataframe PROPRE : exposition=5  freq=4
>   puis : ValueError « deviance function returned a nan ... should be reported »
> ```
>
> **La couche qualité fait son travail : elle SIGNALE et ne décide rien**
> (règle 3, la doctrine tranchée par `qualite/C8`). *Le défaut n'est pas la
> DÉTECTION, c'est l'INDIFFÉRENCE au signal détecté.* L'actuaire recevait une
> invitation à signaler un bug à `statsmodels` là où son fichier portait cinq
> expositions illisibles.
>
> `pipeline_complet` **lit désormais les signalements qu'il vient de recevoir**
> et refuse, avec le rôle, le compte et la proportion.
>
> ⚠️ **CE QUI A ÉTÉ REJETÉ** : reclasser en règle 1 (⛔ un euro bougerait, et
> « illisible » est **ambigu**, pas **impossible**) · un `fillna` en aval
> (⛔ imputer en silence sur une donnée illisible — le motif d'`a2/C5`).
> ⚠️ **Aucun euro : ça mourait déjà. Ça meurt maintenant en disant
> pourquoi.** *(Le `✅` est réservé au MARQUEUR d'ouverture d'un bloc de
> fermeture : `test_archive_cles_fermeture` lit toute ligne `> ✅` comme
> une fermeture et lui réclame sa clé. Un glyphe décoratif y devient un
> constat fantôme.)*
>
> ⚠️⚠️ **ET LE SCEAU A MONTRÉ QU'UN DE MES CONTRÔLES ÉTAIT DU DÉCOR.** Le
> filtre de rôle — ne refuser que sur un rôle que le GLM consomme — **ne peut
> rien filtrer aujourd'hui** : le détecteur `valeur_illisible_*` ne tourne que
> sur `exposition`, `cible_frequence` et `cible_cout`, exactement les trois
> rôles consommés. Le plant qui RETIRE le filtre ne faisait tomber aucun
> contrôle. *Le filtre reste — c'est la bonne assiette pour le jour où un autre
> rôle gagnera un détecteur — mais son cas est désormais **construit**, pas
> emprunté à une couche qui ne le produit jamais.*

Mesuré : `fillna` présent sur `cout_total` (l.314), **absent** sur `expo`
(l.299) et sur `y_freq` (l.300). Les trois passent par `pd.to_numeric(...,
errors="coerce")`, qui produit des NaN silencieux ; un seul les traite.
⚠️ **Sans conséquence observée** : une exposition illisible provoque un arrêt
*loud* (voir D). Mais la protection tient par accident, pas par construction.

> ✅ **`pipeline/C7`** · **FERMÉ le 01/09/2026.** *Preuve : `PC-8`.*
> La docstring promettait « que l'un reproduise l'autre à 1e-6 » ; `tarifer()`
> **arrondit `prime_pure` au centime**. *Une promesse au milliardième sur un
> nombre publié au centime ne peut pas être vérifiée par celui qui la lit.*
> Elle dit maintenant ce qui est vrai — **les deux chemins sont le MÊME
> calcul**, et c'est cette identité qui vaut 1e-6, entre valeurs non arrondies ;
> l'écart observable entre les deux sorties est **0,0036 €** sur 6 contrats.
> ⚠️ *L'oracle du dépôt était juste ; c'est la phrase qui promettait au-delà de
> ce qu'elle pouvait montrer.*

**C9 — Deux horodatages, deux fuseaux, dans la même chaîne.** `tarifer()` pose
`datetime.now(timezone.utc)` (l.146) ; `pipeline_complet` passe
`horodatage=datetime.now()` (l.279), en heure locale. Deux traces du même
calcul ne portent pas la même heure.


> ✅ **`pipeline/C9`** · **FERMÉ le 01/09/2026.** *Preuve : `PC-9`.*
> `tarifer()` posait `datetime.now(timezone.utc)`, `pipeline_complet`
> `datetime.now()` — en heure **locale**. *Deux traces du même calcul ne
> portaient pas la même heure, et rien ne disait laquelle était laquelle.* UTC
> des deux côtés : **un horodatage sans fuseau n'est pas un horodatage, c'est
> une supposition sur la machine qui l'a écrit.**

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
