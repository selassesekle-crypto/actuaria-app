# RELEVÉ — `core/plan_tarifaire.py`, LA SOURCE UNIQUE

**Lu intégralement** : `core/plan_tarifaire.py` **486 l**. Aucun échantillon,
aucun filtre. Troisième fichier du relevé ②.

C'est le fichier qui déplace la charge de la preuve — d'« ActuarIA l'a codé en
dur » vers « l'actuaire l'a signé ». Il annonce remplacer **quatre listes**,
rendre la désynchronisation **impossible par construction**, et rendre la fuite
structurelle B9 **inexprimable dès la déclaration**.

## ① Le compte

**24 affirmations mesurées** — **11 constats** · **13 vérifiées bonnes**.
**2 de mes hypothèses réfutées par la mesure**, puis instruites.

## ② Le classement

### A — Le plan laisse déclarer ce qu'il dit rendre indéclarable (2)

**C1 — La garde B9 est contournée par les INTERACTIONS, et le symptôme
apparaît.** Le `__post_init__` (l.231-252) interdit de déclarer l'exposition
comme facteur, et le commentaire conclut : « *Le plan rend cette erreur
INEXPRIMABLE dès la déclaration.* » Mesuré — le contrôle porte sur
`colonnes_produites()`, et les interactions y entrent **sans passer par la liste
des interdits** :

```
  facteur nomme 'exposition'                    refuse
  facteur nomme comme self.exposition ('expo')  refuse
  'expo' avec transformation log                refuse
  INTERACTION age x expo                        ACCEPTE -> ('age', 'inter_age_expo')
```

Et le pipeline réel la retient :

```
  pipeline_complet tourne. features retenues = ['age','bonus_malus','inter_age_expo']
  prime totale a expo=0,5 :    271866.18
  prime totale a expo=1,0 :    498580.97
  rapport = 1,8339            (2,0000 attendu si proportionnel)
```

⚠️ **C'est exactement le symptôme que le commentaire nomme** : « *la prime cesse
d'être proportionnelle à l'exposition* ». Écart mesuré : **−8,3 %**. Le
garde-fou existe, il est correct, et il regarde une liste où l'interaction ne
figure pas.

> ✅ **`plan/C1`** · **FERMÉ — lot 1.2.** Le contrôle porte désormais sur **trois surfaces** :
> le **nom source** du facteur, les **opérandes d'interaction**, et les
> **colonnes produites** (le contrôle d'origine, conservé). Refusé au
> chargement du plan, donc avant qu'aucune prime ne soit calculée.
> ⚠️⚠️ **ET LA RACINE N'ÉTAIT PAS DANS LE CODE, ELLE ÉTAIT DANS LA SPEC.**
> `plan_execution_6_actions.md` l.294 demandait : « *`exposition` et
> `log_exposition` ne doivent jamais figurer dans `colonnes_produites()`* ».
> **Le code faisait EXACTEMENT cela.** L'implémentation était fidèle ; c'est la
> spécification qui décrivait une liste là où il fallait une propriété.
> ⚠️ **`C9` se ferme du même geste** — le relevé l'annonçait comme « la même
> faille de forme que C1 », et la mesure le confirme : `expo` en one-hot
> (`expo_long`) est refusé par la surface n°1.
> Contrôle positif `POS_Plan_C1` (3 tests), dont **les trois surfaces** et
> **une interaction légitime préservée** (`age × bonus_malus`, déclarée par
> `auto.yaml`).

**C2 — Le plan accepte de déclarer LA CIBLE comme facteur, et ce qui l'arrête
ensuite est fragile.** Aucune garde ne protège `cible_frequence` ni
`cible_cout`, là où l'exposition en a une :

```
  la CIBLE de frequence declaree en facteur   ACCEPTE -> ('nb',)
  la CIBLE de cout declaree en facteur        ACCEPTE -> ('cout',)
```

**Mon hypothèse d'une fuite était trop rapide, et la mesure m'a réfuté** : sur
le pipeline complet, le Gini ne bouge pas (0,1983 avec la cible en facteur
contre 0,1994 sans). Instruit, voici pourquoi :

```
  col_cible='nb'          (UNE seule)  -> matrice X = ['age','bonus_malus','nb']
  col_cible=['nb','cout'] (les DEUX)   -> matrice X = ['age','bonus_malus']
       motif = FUITE DETECTEE PAR L'EFFET -- spearman 0,9988
```

**C'est la DEUXIÈME cible qui dénonce la première.** `exemptees`
(`conformite_reglementaire` l.1123-1125) contient la cible *en cours d'examen*,
pas les autres : passer les deux fait que chacune contrôle l'autre. Or, relevé
par AST :

```
  demos/fremtpl2_demo.py       LISTE      [plan.cible_frequence, plan.cible_cout]
  pipeline_tarifaire.py        LISTE      [col_freq, col_cout]
  a3_glm/agent.py              LISTE      [col_freq, col_cout]
  a4_ml/agent.py               une seule  col_cible
  a5_deep_learning/agent.py    une seule  col_cible
  a6_comparaison/agent.py      une seule  col_cible
```

Vérifié dans les signatures : `col_cible: str` en A4/A5/A6 — **une chaîne, une
seule cible à la fois** (A5 l'écrit : « *'nb_sinistres' (fréquence) ou
'cout_moyen' (sévérité)* »). **La protection qui sauve A3 et
`pipeline_tarifaire` n'existe donc pas en A4, A5 et A6.**

⚠️ **Et elle s'effondre aussi quand la seconde cible ne varie pas** — un coût
de variance nulle (portefeuille sans sinistre observé, prestation forfaitaire
constante) :

```
  cout forfaitaire (500 EUR par sinistre) : matrice X = ['age','bonus_malus']  exclusions = ['nb']
  cout CONSTANT (variance nulle)          : matrice X = ['age','bonus_malus','nb']  exclusions = []
                                            controle_effet_execute = True
```

C'est le constat **C1 du relevé `conformite_reglementaire`** qui se referme ici
par une porte réaliste : la cible entre dans sa propre matrice X, rien n'est
exclu, et l'objet déclare le contrôle exécuté.

⚠️ **Ce qui rattrape le cas courant** : un nom de cible standard
(`nb_sinistres`, `cout_total_sinistres`, `prime_pure`) est capté par le filtre
anti-fuite **par le nom**. `nb` et `cout` ne le sont pas — et le plan laisse
l'actuaire nommer ses cibles librement.

> ✅ **`plan/C2`** · **FERMÉ — lot 1.2.** Les deux cibles ont désormais **la même garde que
> l'exposition**, sur les mêmes trois surfaces. Refusé au chargement du plan —
> donc la protection ne dépend plus du nombre d'arguments que l'appelant a
> passés, et **A4/A5/A6 (`col_cible: str`, une seule cible) sont couverts comme
> A3**.
> ⚠️ **POURQUOI CE N'EST PAS UN ARBITRAGE DE MÉTHODE** : `exposition` entre
> comme **OFFSET**, `cible_frequence` comme **RÉPONSE** du modèle de fréquence
> et comme **POIDS** du modèle de coût moyen, `cible_cout` comme **RÉPONSE**.
> Les trois entrent avec un **rôle FIXE** ; les refuser comme facteurs libres,
> c'est refuser de prédire une grandeur par elle-même. **La sinistralité passée
> légitime est une autre colonne, sur une autre période** — le plan la porte
> déjà (`anteriorite=True`, critère V14), et le contrôle positif vérifie
> qu'elle n'est **pas** cassée : le BLOQUANT B5 a coûté **−17,4 % de Gini**
> pour un seul facteur d'antériorité détruit.
> Contrôle positif `POS_Plan_C2` (3 tests).

### B — Affirme plus que le code ne porte (5)

**C3 — Un `type` ou un `encodage` mal orthographié fait disparaître le facteur
EN SILENCE, et le détecteur d'amputation annonce `ampute=False`.**
`Facteur.__post_init__` valide trois cohérences, mais **jamais que `type` et
`encodage` sont des valeurs connues** — `TypeFacteur` et `Encodage` sont des
`Literal`, que Python n'applique pas :

```
  [CONSTAT] type INCONNU 'ordinal'        ACCEPTE -> colonnes_produites() = ()
  [CONSTAT] encodage INCONNU 'onehot'     ACCEPTE -> colonnes_produites() = ()
            binaire + one_hot + modalites ACCEPTE -> ('x',)   encodage ignore
```

Et l'amputation qui en résulte est **invisible au détecteur prévu pour elle** :

```
  plan avec un facteur de type 'ordinal' :
    colonnes_produites()     = ('age',)
    verifier_completude_plan -> ampute=False  n_attendues=1  manquantes=[]
```

`bonus_malus` est **dans les données**, **déclaré au plan**, et n'atteint aucun
modèle. `verifier_completude_plan` compare `colonnes_produites()` aux données —
et le facteur perdu n'est justement pas dans `colonnes_produites()`.

⚠️ C'est le BLOQUANT B5 dans une forme nouvelle : **un seul facteur détruit avait
coûté −17,4 % de Gini**, et le module s'est doté d'un détecteur pour cela. Ce
détecteur ne voit pas cette amputation-ci.

> ✅ **`plan/C3`** · **FERMÉ — lot 1.2.** `Facteur.__post_init__` valide désormais
> **l'APPARTENANCE avant la combinaison** : `type`, `encodage` et
> `transformation` doivent être des valeurs connues. ⚠️ **Les jeux de valeurs
> sont DÉRIVÉS des `Literal` par `get_args`, jamais recopiés** — une valeur
> ajoutée au type est acceptée sans toucher au contrôle. *Recopier ces listes
> aurait rouvert la désynchronisation que ce fichier existe pour supprimer ;
> `famille_severite`, qui recopiait son tuple à la main, est passée au même
> régime.*
> ⚠️ Le cas **`binaire` + encodage** est refusé aussi : l'encodage y était
> **silencieusement ignoré** — l'actuaire signait un one-hot et obtenait autre
> chose, sur un document opposable.
>
> ⚠️⚠️ **ET UN FILET AU NIVEAU DE LA PROPRIÉTÉ, PARCE QUE LE DÉTECTEUR RESTE
> AVEUGLE.** `verifier_completude_plan` est *structurellement* incapable de voir
> cette perte : il compare `colonnes_produites()` aux données, et le facteur
> perdu n'est justement plus dedans. Nommer les trois causes mesurées ne
> suffisait donc pas. **Un facteur déclaré qui ne produit AUCUNE colonne est
> refusé, quelle qu'en soit la cause** — et ce filet a immédiatement attrapé un
> cas qui n'est dans aucun constat : *un one-hot à modalité unique égale à la
> référence*, qui ne produit rien et qu'aucun contrôle nommé ne refusait.
> Contrôle positif `POS_Plan_C3` (4 tests) + `POS_Plan_LesVingtPlansDuDepotChargent`.

**C4 — `config_encodage()` annonce être « ce que A2 consomme », et personne ne
l'appelle.** Relevé par AST sur 418 fichiers :

```
  [CONSTAT] config_encodage    production= 0  tests= 0
```

**Zéro appelant, pas même un test.** Sa docstring dit « *Ce que A2 consomme —
remplace VARS_CATEGORIELLES* ». Mesuré ailleurs : A2 honore bien le plan (voir
D), mais **il le lit directement**, pas par cette méthode. L'abstraction est
morte, et son texte décrit un contrat qui passe ailleurs.

**C5 — `depuis_dict` accepte en silence toute clé inconnue ou mal
orthographiée.** Le plan est le document opposable ; sa porte d'entrée ne
signale rien :

```
  [CONSTAT] identifiant_contract (anglais)  ACCEPTE en silence  identifiant_contrat = None
  [CONSTAT] echeances (pluriel)             ACCEPTE en silence  echeance = None
  [CONSTAT] famille_severity (anglais)      ACCEPTE en silence  famille_severite = 'gamma'
  [CONSTAT] cle totalement inventee         ACCEPTE en silence
```

Un actuaire qui déclare `famille_severity: lognormal` **signe une log-normale et
obtient une gamma**. Un actuaire qui déclare `echeances` obtient le
comportement de doublon que le commentaire l.214-218 décrit comme refusant le
fichier à 67 %.

**C6 — Deux formes de dict pour « plan amputé », dans le même fichier, et le
mélange échoue vers « rien à signaler ».**

```
  verifier_completude_plan -> {'plan','n_attendues','n_presentes','colonnes_manquantes','ampute'}
  synthese_colonnes_plan_manquantes lit -> {'plan','colonnes_non_produites','facteurs_absents'}

  synthese_colonnes_plan_manquantes(rapport de verifier_completude_plan) -> None
```

Sur un rapport qui dit `ampute: True`, la synthèse destinée aux livrables rend
`None` — c'est-à-dire « rien à afficher ». Les deux fonctions sont à **60 lignes
l'une de l'autre**.

⚠️ **Aucun appelant réel ne fait cette erreur aujourd'hui** (voir D : A2 produit
la bonne forme, la synthèse la consomme). Le défaut est la **forme du piège**,
pas un dégât constaté.

**C7 — Trois rôles ajoutés au plan, déclarés par AUCUN des 20 plans.**

```
  identifiant_contrat : 0/20      echeance : 0/20      comportement : 0/20
```

Le commentaire de `echeance` (l.214-218) porte pourtant une mesure : « *un
historique de renouvellement sur 3 ans porte ~67 % de « doublons » pour un seuil
ROUGE à 5 % — le fichier est refusé avant d'être lu.* » Le mécanisme existe,
il est correct, et **aucun plan ne l'active** : tout client apportant un
historique de renouvellement est refusé par la couche qualité.

Idem pour `identifiant_contrat` : la règle 1 de la couche qualité (dédoublonnage
par identifiant, exclusion sans discussion) n'est **jamais** atteinte ; on
retombe toujours sur la règle 3 (ambiguë, signalée et laissée).

### C — Imprécis ou incomplet (4)

**C8 — L'empreinte n'a pas de numéro de version de schéma, et elle est aveugle
au commentaire.** Mesuré sur 10 variations :

```
  version · auteur · famille_severite · identifiant_contrat · echeance ·
  comportement · anteriorite · interactions · ORDRE des facteurs  -> change
  [CONSTAT] COMMENTAIRE                                           -> ne change pas
  [CONSTAT] AUCUNE cle de version de schema dans le payload
```

Deux plans identiques dont le `commentaire` — la justification écrite par
l'actuaire — diffère portent **la même empreinte**. Et sans version de schéma,
toute nouvelle clé ajoutée au payload (`echeance` et `comportement` l'ont été)
**change l'empreinte de tous les plans archivés**, sans que rien ne le signale.
⚠️ *Ce point est déjà à l'ardoise, arbitré « VERSIONNER, ne pas omettre » —
cette mesure le confirme, elle ne l'ouvre pas.*

**C9 — `'expo' en one_hot` échappe à la garde B9.** `expo_long` n'est pas dans
la liste des interdits. Sans conséquence pratique — une exposition catégorielle
n'a pas de sens actuariel — mais c'est la même faille de forme que C1.

> ✅ **`plan/C9`** · **FERMÉ — lot 1.2, SANS CORRECTIF PROPRE.** Le contrôle de C1 porte
> maintenant sur le **nom source** du facteur, pas seulement sur les colonnes
> produites : `expo` déclaré en one-hot est refusé avant d'avoir produit
> `expo_long`. *C'est la preuve que le correctif visait la propriété et non le
> symptôme — un correctif par liste aurait exigé une seconde entrée.*

**C10 — La quatrième liste annoncée remplacée existe toujours.** L'en-tête
(l.4-8) annonce quatre listes remplacées. Mesuré :

```
  MOTS_CLES_DETECTION            : (introuvable)
  VARS_CATEGORIELLES             : (introuvable)
  VARS_GLM                       : (introuvable)
  FACTEURS_TARIFAIRES_AUTORISES  : core/conformite_reglementaire.py
```

Trois sur quatre ont bien disparu. La quatrième **gouverne encore le chemin sans
plan** (`construire_matrice_x` sans `plan=`). ⚠️ **Sans conséquence en
production** — les six appelants passent tous `plan=` (voir D) — mais
« *la désynchronisation devient IMPOSSIBLE PAR CONSTRUCTION* » (l.16) décrit une
propriété du chemin déclaratif, pas du module.

**C11 — `colonnes_obligatoires()` n'a aucun appelant externe.** Production = 0,
tests = 1. Elle est utilisée en interne par `colonnes_attendues()` et
`valider_contre()` ; ce n'est pas du code mort, mais ce n'est pas non plus une
interface.

### D — Vérifié comme BON (13)

| affirmation | mesure |
|---|---|
| les 20 plans du dépôt se chargent | **20/20**, aucun échec ; 18/20 déclarent un facteur d'antériorité |
| les trois validations de `Facteur` | catégoriel sans encodage · continu avec encodage · one-hot sans modalités → **3 `ValueError`** |
| la garde B9 sur les formes DIRECTES | `exposition`, `expo` (= `self.exposition`), `expo`+transfo log → **3 refus** |
| **`_slug` est exactement ce qu'A2 applique** | 4 modalités accentuées (`Île-de-France`, `Provence-Alpes-Côte d'Azur`, `RHÔNE`) → **4 annoncées, 4 produites, 0 en trop, 0 manquante** |
| A2 rapporte l'amputation dans la forme attendue | `{'plan','facteurs_absents','colonnes_non_produites'}` — **exactement les clés que la synthèse lit** |
| la synthèse produit son texte sur ce dict | `⚠ MODELE AMPUTE — plan 'ampute' : 1 colonne(s)…` |
| `plafonner_statut_si_ampute` **ne remonte jamais** | VERT→**AMBRE** · AMBRE→AMBRE · ROUGE→ROUGE |
| l'empreinte est **déterministe** | deux appels → identiques ; sensible à **9 champs sur 10**, y compris l'**ordre** des facteurs |
| l'empreinte est réellement inscrite | **4 appelants de production** (`pipeline_agents`, `pipeline_tarifaire`, la démo, l'exemple) |
| **tous les appelants de production passent `plan=`** | **6/6** — et tous passent aussi `df=` et `col_cible=` : le garde-fou n°4 tourne partout en production |
| la deuxième cible dénonce la première | `col_cible=['nb','cout']` → `nb` **écartée**, spearman **0,9988** |
| trois des quatre listes ont bien disparu | `MOTS_CLES_DETECTION`, `VARS_CATEGORIELLES`, `VARS_GLM` : **introuvables** |
| la chaîne « amputé » a ses appelants | `verifier_completude_plan`, `alerte_modele_ampute`, `synthese_colonnes_plan_manquantes` : **3 appelants de production chacune** |

### Mes deux hypothèses réfutées par la mesure

**① `valider_contre` ne juge pas incomplet un fichier complet.** J'avais mesuré
que sur `auto.yaml`, un fichier portant exactement `colonnes_attendues()` était
déclaré incomplet — **6 faux positifs**, tous des facteurs dérivés
(`km_par_an_normalise`, `jeune_conducteur`…). **Le site d'appel m'a corrigé** :

```
  valider_contre SUR LE FICHIER BRUT        : 6 manquant(s)
  valider_contre APRES les derivees (a2.fit): 0 manquant(s)
  [BON] a2.fit(fichier complet, plan auto)  : ACCEPTE, ne leve pas
```

`a2.fit` calcule `_calculer_indicateurs_derives` **l.779**, puis appelle
`valider_contre` **l.780**. `valider_contre` n'est jamais appelé sur le fichier
brut, et son unique appelant de production le sait — le commentaire l.782-784
l'écrit et retraduit même le message vers les noms de source. **Constat retiré.**

**② La cible déclarée en facteur ne produit pas de fuite dans le pipeline.**
0,1983 contre 0,1994 : rien. Une coïncidence pareille ne se commente pas — elle
s'instruit, et l'instruction a produit **C2**, qui est plus précis et plus utile
que mon accusation initiale.

## ③ Ce que je n'ai pas lu, et ce que je ne tranche pas ici

**Rien n'est resté non lu** : 486 lignes, intégralement.

Un point **non tranchable dans ce fichier** : `mrh.yaml` et `auto_fr_reel.yaml`
sont les **deux seuls plans sur 20** sans aucun facteur d'antériorité, et
`auto_fr_reel.yaml` produit **39 colonnes pour 9 facteurs** — de loin le ratio le
plus élevé du dépôt. Savoir si c'est justifié relève d'une lecture des plans
eux-mêmes, pas de leur moteur.

## ④ Les preuves

- `preuves/audit_plan.py` — les 20 plans, les validations de `Facteur`, la garde
  B9, `valider_contre`, les deux formes de dict, `depuis_dict`, l'empreinte.
- `preuves/audit_plan_bis.py` — le contrat `_slug` ↔ A2, la forme de dict réelle
  d'A2, la cible déclarée facteur, le type mal orthographié.
- `preuves/audit_plan_ter.py` — la propagation **par AST**, `plan=` chez les six
  appelants, le tableau des 20 plans.
- `preuves/audit_plan_quater.py` — la réfutation de mon M5 par le site d'appel,
  et le Gini du plan « fuite ».
- `preuves/audit_plan_quinquies.py` — l'instruction de C2 (une cible ou deux),
  la cible constante, et le symptôme B9 mesuré jusqu'à la prime.

Chacune se relance seule.

---

**Mon appréciation d'ensemble.** La source unique **tient sur l'essentiel** :
trois des quatre listes ont réellement disparu, les six appelants de production
passent tous le plan, l'empreinte est déterministe et réellement inscrite, et
surtout — le point le plus difficile — **`_slug` produit exactement les noms que
A2 crée**, y compris sur des modalités accentuées et apostrophées. Le contrat
A2→A3 est honoré au caractère près.

⚠️ **Les deux constats graves ont la même origine** : un garde-fou qui regarde
**une liste** au lieu d'une **propriété**. La garde B9 énumère quatre noms
interdits et ne voit pas l'interaction (C1) ; la garde sur les cibles n'existe
pas, et ce qui la remplace dépend du nombre d'arguments que l'appelant a passés
(C2). Dans les deux cas la protection est **exacte sur les formes prévues** et
muette sur les autres.

⚠️ **Et un motif propre à ce fichier** : *il valide la cohérence des
combinaisons, jamais l'appartenance des valeurs.* Un `type` inexistant, un
`encodage` inexistant, une clé YAML mal orthographiée — les trois passent, et
les trois font disparaître quelque chose en silence. Sur un document dont toute
la raison d'être est d'être **opposable**, c'est la porte d'entrée qui ne
vérifie pas ce qu'on y écrit.
