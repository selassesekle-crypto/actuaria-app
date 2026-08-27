# CLASSEMENT DES 40 CONSTATS D'A3, A4 ET A5 — ce qui décide, mesuré

> ⚠️⚠️ **CE DOCUMENT EST DÉPASSÉ SUR UN POINT ESSENTIEL — LIRE
> [`REMESURE_A3_A4_A5.md`](REMESURE_A3_A4_A5.md) D'ABORD.**
> Il classait les constats **sur ce que les relevés disaient**, sans re-mesurer
> le code. La re-mesure du 25/08 établit que **15 des 40 sont déjà fermés**,
> dont `a3/C1` — le seul que ce document désignait comme déplaçant un euro.
> *Ce qui reste valable ici : la mesure du banc (quel champ atteint un
> livrable) et la distinction des surfaces non outillées.*

**Établi le 25/08/2026, une fois le banc opérationnel.** Ce document **ne ferme
aucun constat** : il dit, pour chacun, **ce qui doit décider de son rang**.

---

## ⚠️⚠️ CE QUE LE BANC PEUT DIRE, ET CE QU'IL NE PEUT PAS

Le banc (`preuves/passage_libelles.py`) répond à **une seule question** :
*ce champ atteint-il un livrable ?* Il ne dit **pas** si sa valeur est fausse.

**Mesuré sur les vrais résultats des trois agents :**

| famille de champs | A3 | A4 | A5 |
|---|---|---|---|
| `validation_*` | **14/22 publiés** | **14/19** | **2/15** |
| `hypotheses` | **12/22** | **12/19** | — |
| `classement` | — | **14/21** | **6/6** |
| `commentaire` | **publié** | **publié** | **publié** |
| `monitoring` | — | **0/10 — MUET** | — |
| `sensibilite_tarifaire` | — | **0/3 — MUET** | — |
| `rapport` | 0/112 — MUET | 0/51 — MUET | 0/24 — MUET |
| `metriques` | 1/83 | — | — |

⚠️⚠️ **LE « 1/83 » DE `metriques` N'EST PAS UN VERDICT — C'EST UN ANGLE MORT.**
Les feuilles de `metriques` sont des **NOMBRES**, et le banc ne marque que les
**chaînes** (troisième angle mort : un marqueur posé sur un nombre est détruit
par l'arrondi). **Le banc est aveugle sur cette famille par construction.**
*Ne jamais lire ce chiffre comme « les métriques ne sont pas publiées ».*

---

## CE QUI DÉCIDE, CONSTAT PAR CONSTAT

⚠️ **Aucun tri automatique par taux.** Chaque ligne porte **ce qui doit la
trancher**, et le banc n'en décide qu'une partie.

### ⓐ Décidés par le banc — le champ ATTEINT l'actuaire → **vivants**

| constat | ce qu'il dit | canal mesuré |
|---|---|---|
| `a3/C2` | H1 rend VERT sur des valeurs codées en dur | `hypotheses` **publié** |
| `a3/C3` | H4 « non testée » vaut VERT | `hypotheses` **publié** |
| `a3/C8` | le seuil H3 annoncé n'est pas celui appliqué | `validation_glm` **publié** |
| `a3/C9` | scorecard « 3 ✅ », 4 items listés, 5 calculées | `commentaire` **publié** |
| `a3/C10` | « convergence des 3 modèles », 2 lus | `statut_rag` **publié** |
| `a4/C4` | deux validations contradictoires dans le même retour | `validation_ml` **publié** |
| `a4/C6` | « Modèles testés : 6/8 » | `commentaire` **publié** |
| `a4/C8` | scorecard « 3 ✅ », 4 items | `commentaire` **publié** |
| `a4/C9` | le ROUGE annoncé n'est pas atteignable | `validation_ml` **publié** |
| `a5/C1` | trois hypothèses DL ROUGE sur un CANN excellent | `validation_dl` — **2/15 publiés, à vérifier champ par champ** |

### ⓑ Décidés par le banc — le champ N'ATTEINT PERSONNE → **latents**

| constat | ce qu'il dit | canal mesuré |
|---|---|---|
| ~~`a4/C2`~~ | ✅ **FERMÉ le 26/08 — `16c6566`** | *voir ci-dessous* |
| — | *(la sensibilité tarifaire est muette aussi : 0/3)* | `sensibilite_tarifaire` |

> ✅ **`a4/C2` FERMÉ (`16c6566`), et le latent n'était pas où ce tableau le
> plaçait.** Le monitoring ne simulait plus depuis six semaines : zéro
> `np.random.*` dans A4 (AST), PSI mesuré par `_psi_reel` — **0,056 sur deux
> portefeuilles proches contre 7,59 sur deux éloignés** (exécution). Ce qui
> restait, c'était son **étiquette** : `FIGURES_ECARTEES` l'accusait encore de
> « données FABRIQUÉES ». ⚠️ *Un latent classé sur le canal peut être clos sur
> sa source.* Épinglé par `test_monitoring_derive_reel.py` (6 contrôles).

⚠️ **Un latent reste vrai** : un monitoring fabriqué est un défaut, même
inatteignable. Il descend dans l'ordre, il ne sort pas de la liste.

### ⓒ **HORS PORTÉE DU BANC — il ne peut RIEN en dire**

Ces constats portent sur des **valeurs numériques**, des **figures** ou de
l'**hygiène de code**. Le banc mesure des chaînes dans des livrables : il est
**aveugle** ici, et le dire est plus utile que de produire un faux verdict.

| famille | constats | ce qui devra décider |
|---|---|---|
| **calcul faux — déplace des euros** | `a3/C1` (Tweedie ajusté sans offset) | une **mesure de prime**, comme au lot 1.2 |
| **valeurs numériques** | ~~`a3/C6`~~ ✅ **FERMÉ `b0ae396`** · `a3/C7` `a3/C14` · `a4/C10` `a4/C11` | comparer la valeur **publiée** à la valeur **réelle** — le banc ne marque pas les nombres. ⚠️ **`a3/C6` a été fermé exactement par cette méthode** : le Gini du Tweedie mesuré vaut **−0,078**, quand A6 en publiait **0** par défaut de `get`. *Le zéro fabriqué était flatteur.* |
| **figures** | `a3/C4` `a3/C5` `a3/C13` · `a4/C3` `a4/C5` · `a5/C3` `a5/C4` `a5/C5` | produire la figure et **lire ce qu'elle trace** — une seconde surface, non outillée |
| **hygiène / docstring** | `a3/C11` `a3/C12` `a3/C15` `a3/C16` `a3/C17` `a3/C18` · `a4/C7` `a4/C12` `a4/C13` · `a5/C8` `a5/C9` | lecture directe ; aucun livrable en jeu |
| **fermés** | `a5/C6` `a5/C7` | lot 1.1 |

---

## ⚠️ CE QUE CE CLASSEMENT ÉTABLIT, ET CE QU'IL LAISSE OUVERT

**Le banc tranche 12 constats sur 40.** Les 28 autres demandent une autre
mesure — et **deux surfaces ne sont pas outillées** :

1. **les FIGURES** — huit constats en dépendent. Le banc lit du texte dans des
   livrables ; une figure trace des valeurs. *C'est une extension du banc, pas
   une application.*
2. **les VALEURS NUMÉRIQUES** — cinq constats. Le marqueur-chaîne ne les voit
   pas ; il faut comparer publié contre réel, champ par champ.

⚠️ **RECOMMANDATION** : traiter d'abord le groupe ⓐ — dix constats **mesurés
comme atteignant l'actuaire**, dont quatre sur des **scorecards et des
statuts** qu'un actuaire lit pour signer. Puis `a3/C1`, seul du lot à déplacer
un euro, qui demande sa propre mesure de prime.

⚠️ **Et je ne propose pas d'outiller les figures maintenant** : ce serait un
troisième banc, et l'expérience du second dit qu'il coûte plus que son
apparence. *À proposer formellement, chiffré, quand les dix vivants seront
fermés.*
