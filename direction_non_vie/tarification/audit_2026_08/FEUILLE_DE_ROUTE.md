# FEUILLE DE ROUTE — RENDRE LE MODULE TARIFICATION ULTRA SOLIDE

**Version finale, 25/08/2026.** Elle remplace toute version antérieure et
**elle seule ordonne**. [CARTE.md](CARTE.md) reste l'**inventaire** (les
constats, leurs mesures, les preuves).

---

# ① CE QUE « ULTRA SOLIDE » VEUT DIRE — cinq critères, tous mesurables

*Sans définition mesurable, « solide » est un adjectif. Voici la définition, et
l'état d'aujourd'hui.*

| # | critère | état mesuré aujourd'hui |
|---|---|---|
| **S1** | **Rien de faux n'est publié** | ⛔ **79 constats ouverts** — *dérivés le 29/08 des clés de fermeture, méthode au §②* |
| **S2** | **Rien de fermé ne peut régresser** | 🟡 **75 fermés, 1 partiel (`pipeline/C1`).** ✅ `a5/C5` n'est plus « corrigé sans être épinglé » : il est fermé ET épinglé, et le lot a montré qu'il se reproduisait encore par une SECONDE cause. ✅ **Et l'archive ne peut plus RETARDER sur le code** : `test_archive_fermeture_reportee.py` fait tomber la gate dès qu'un constat épinglé par un test n'a pas son bloc de fermeture -- le défaut mesuré le 28/08, où douze lots avaient été poussés sans être reportés. ⚠️ L'archive elle-même est désormais épinglée : `test_archive_cles_fermeture.py` fait tomber la gate sur un bloc de fermeture qui ne nomme pas son constat. ⚠️⚠️ **ET SON EXEMPTION EST SCOPÉE PAR FICHIER, mesuré le 29/08** : une exemption portant la seule clé aurait laissé passer un futur test qui ÉPINGLERAIT vraiment ce constat sans écrire son bloc — le défaut même que ce filet attrape. *Un garde-fou qui exclut la seule chose qui compte n'en est pas un.* Le fichier du garde-fou sort de sa propre assiette, sinon déclarer une exemption pour `x/Cn` créerait la mention que le filet reproche aussitôt |
| **S3** | **Un tarif signé se rejoue à l'identique** | 🟡 **RE-MESURÉ LE 27/08 — 2 fermés, 1 hérité, 1 PARTIEL.** ✅ **l'empreinte du plan est versionnée** : `s1:9b6d4f70080ad771`, **rejouée identique** sur les 20 plans (`2cb43ef`). ✅ **le livrable ne publie plus un `now()` sous l'étiquette « Arrêté »** : **0** site `_bandeau(… now …)`, contre **28** à l'origine ; absent → « non déclaré », illisible → « non déclaré (illisible : …) » (`ea37564`). ⬜ *hérité, non re-mesuré ici* : le tarif **déclaratif** reproductible au bit près (0,00e+00). ⚠️ **PARTIEL — le tarif DL** : le `seed` est **déclaré** (paramètre de `A5.run`), **appliqué** à `torch.manual_seed` et `np.random.seed` (l.528-529) et **inscrit au rapport**. ⚠️⚠️ **Mais la reproductibilité bout-en-bout n'est PAS prouvée ici** : elle demande un double run d'A5, non fait. *Le seed posé n'est pas la reproductibilité mesurée.* |
| **S4** | **Un seul chemin — ou des chemins également gardés** | ⛔ **RE-MESURÉ LE 27/08 — inchangé, et l'asymétrie est nette.** **L'orchestrateur a toujours 0 appelant de production** (2 importeurs au total, tous hors production — relevé par AST). ⚠️⚠️ **Et la couche qualité départage les deux chemins** : `pipeline_tarifaire` (déclaratif) importe `core.qualite_donnees` **et** `core.conformite_reglementaire` ; `pipeline_agents` **n'en importe AUCUN**. *Deux chemins vers un tarif signé, un seul gardé.* ⬜ *non re-derivable* : le « 5 assemblages dans l'app » date d'une définition non consignée — **je ne le réaffirme pas sans la refaire**. |
| **S5** | **Tout ce qui tarife est atteignable par une gate** | 🟡 **RE-MESURÉ LE 27/08, ET LA NUANCE COMPTE.** `actuaria_app.py` (**5 208 l**) est **importable** depuis le lot 0.1 (`07be8c0`) — mais **AUCUN test ne l'importe** ; **4 le LISENT comme un fichier** (`core/test_imports_app.py` le dit lui-même : *« ce test relit le fichier, il ne l'importe pas »*). ⚠️ *Ce qui est exercé, c'est sa STRUCTURE, pas son comportement.* ✅ `core/elasticite.py` (**988 l**) n'est plus hors de portée : **2 tests l'importent** (`test_elasticite.py`, `test_a4_ml.py`) — ⚠️ **testé n'est toujours pas audité**, il reste à l'ouverture HORS RANG. ⛔ `services/excel_helpers.py` (**151 l**) : **0 test ne l'importe**. |

⚠️⚠️ **ET UN CRITÈRE QUI N'EN EST PAS UN : LE NOMBRE DE TESTS.** Mesuré par
résolution d'import vers un chemin de fichier : **23 882 lignes, 1 940 tests,
12 lignes par test.** Le périmètre est **densément testé** — et il a livré
**147 constats**. *L'archive l'écrivait dès le premier jour : « testé n'a jamais
voulu dire audité ».* **Ajouter des tests ne rendra pas ce module solide.
Fermer ce qui est faux, et l'épingler, oui.**

⚠️ **Un seul module du périmètre n'est importé par aucun test** :
`core/severite.py` (131 l) — la **source unique** de la cible de sévérité,
partagée par A3 et les deux pipelines, et dont la duplication avait coûté
**−15 % de tarif**. Il est exercé *indirectement*; il n'est **jamais testé pour
lui-même**.

---

# ② L'ÉTAT, EN CHIFFRES

| | |
|---|---|
| constats relevés (vagues 1 + 2) | **154** — *`services/C12` ouvert ET fermé le 30/08 (la synthèse qualité ne sortait que par le prompt) ; `qualite/C7` ouvert ET fermé le 30/08 (l'identifiant jugé par le détecteur des grandeurs) ; `a2/C17` ouvert le 29/08 par la re-mesure de `a2/C8` et `a2/C9` ; recomptés le 29/08 ; `a3/C19`, `services/C10`, `a5/C10` et `services/C11` sont des constats NEUFS, ouverts et fermés dans leur propre lot* |
| fermés **et épinglés** | **79** |
| corrigé, **non épinglé** | **0** — `a5/C5` épinglé le 29/08 · **partiel** : `pipeline/C1` |
| corrigé, épinglé, **NON REPORTÉ** (4e état) | **0** — `a6/C1` `a6/C2` `a6/C4` nommés le 30/08 |
| **⛔ OUVERTS** | **75** |
| lignes lues intégralement | **22 693** sur 23 863 du périmètre |
| jamais auditées | **1 170 l** + `actuaria_app.py` (5 181 l) |
| preuves qui se relancent | **35, 0 échec** |
| gates de lot au **28/08** | `core` **197 OK** · `tarification` **549 OK** · `provisionnement` **782 OK** · **`direction_non_vie` 1610 OK** |

## ⚠️⚠️ CES CHIFFRES SE DÉRIVENT — ET LE MÉCANISME EST DANS LA GATE

**Recomptés le 27/08/2026. Les précédents — « 146 · 18 · 129 », puis « 147 · 40
· 107 » — étaient FAUX, et pour la même raison.**

- **154 constats** = en-têtes des 14 `releve_*.md`, **DEUX formes** :
  `**Cn — …**` et `**Cn** — …`. *N'en compter qu'une en rate douze.*
- **37 fermés** = les **38 clés d'attribution** portées par les blocs `> ✅`,
  **moins `pipeline/C1`** qui n'est fermé que **pour l'illisibilité**.
- **1 partiel** : `pipeline/C1`. ⚠️ **Arbitré : il compte OUVERT** — c'est le
  sens sûr de l'erreur.

⚠️⚠️ **POURQUOI LE COMPTE A ÉTÉ FAUX DEUX FOIS, ET CE QUI L'EMPÊCHE MAINTENANT**

Les blocs de fermeture ne **nommaient pas** leur constat : ils étaient
seulement *placés à côté*. Et le placement n'était pas uniforme —
**le lot du 25/08 écrit le bloc AVANT l'en-tête du constat qu'il ferme**, tous
les autres APRÈS. Un parseur « en-tête → en-tête suivant » attribuait donc dix
blocs au mauvais constat. *Le chiffre était faux dans un document qui fait foi,
et rien ne pouvait le montrer.*

⚠️ **UNIFORMISER LE PLACEMENT AURAIT DÉPLACÉ LE PROBLÈME, PAS RÉSOLU** : la
main suivante n'aurait eu aucun moyen de savoir dans quel sens écrire.
**Chaque bloc porte désormais SA CLÉ** — `> ✅ **`a3/C8`** · …` — et la position
n'a plus d'importance, pour un parseur comme pour un lecteur.

✅ **ÉPINGLÉ** par `test_archive_cles_fermeture.py` (6 contrôles) : un bloc sans
clé, ou une clé qui ne désigne aucun constat du fichier, **fait tomber la
gate**. ⚠️ Il distingue **l'attribution** (le marqueur d'ouverture, avant le
`·`) du **renvoi** (« même geste qu'`a3/C9` ») — écrit sans cette distinction,
il accusait quatre renvois légitimes.

⚠️ **ET LE COMPTE NE DÉPEND PLUS QUE D'UNE SOURCE** : les trois constats que
seul `REMESURE` déclarait fermés (`a3/C1`, `a4/C1`, `a5/C2`) ont reçu leur
propre bloc, chacun **re-vérifié au code d'aujourd'hui** — `predict(X)` sans
offset l.1512 · `_optimisation_tarifaire` **0 mention** · `historiques.get(…)`
l.2014.

⚠️⚠️ **CE COMPTE MESURE CE QUI EST ENREGISTRÉ, PAS CE QUE LE CODE FAIT.** Une
fermeture non reportée reste comptée **OUVERTE** — se tromper vers « ouvert »
rouvre un dossier clos ; vers « fermé », on laisse un défaut dans un livrable
signé.


---

# ③ L'ORDRE

**L'axe : ce qui publie un faux, pondéré par ce qui TOURNE.** Un constat de
classe A sur une fonction que personne n'appelle passe **après** un constat de
classe B sur le chemin de l'écran.

## RANG 0 — LES PRÉREQUIS · **2 lots** · ✅ **CLOS le 25/08/2026**

*Ni des constats, ni des correctifs : les conditions sans lesquelles on ne peut
ni fermer ni prouver.*

| lot | ferme | pourquoi en premier |
|---|---|---|
| **0.1 Le garde `__main__`** | ✅ **CLOS** (`07be8c0`) | **SIX** instructions exécutantes au niveau module (et non cinq : `page = st.session_state.page` m'avait échappé). Elles passent sous `main()` + garde ; les **21 affectations de données restent**. Contrôle positif **structurel par AST**, calibré dans les deux sens : il **échouait** avant, il attrape **4 violations plantées sur 4**. **29 fonctions désormais importables, contre 0.** ⚠️ Réserve assumée : il prouve que rien ne s'exécute à l'import, **pas** que l'interface fonctionne |
| **0.2 Le compte de référence de la gate NV** | ✅ **CLOS** | **RE-MESURÉ le 28/08 : `Ran 1610 tests` — `OK (skipped=3)`**, 1 840 s. L'ancienne référence **1403** (25/08) est PÉRIMÉE. Voir ci-dessous |

### ⚠️ LOT 0.2 — CE QUE LE COMPTE DE RÉFÉRENCE A TRANCHÉ

```
  gate direction_non_vie   ->   Ran 1403 tests in 2088.882s
                                OK (skipped=3)
```

| | |
|---|---|
| **référence établie** | ~~1403~~ (25/08) → **1610** (28/08, confirmé par la nocturne verte `33190782424`) |
| mesuré à L0 | 1395 — **+8** |
| ce que j'annonçais attendre | ~1440 — **−37, mon attente était FAUSSE** |

⚠️ **L'incertitude « 1395 mesuré, ~1440 attendu » est close.** Le ~1440 était
une **estimation de ma part**, jamais mesurée. *C'est exactement le motif de cet
audit, appliqué à mon propre chiffre.*

⚠️ **3 tests étaient SKIPPÉS, et la sortie ne les nommait pas.** ✅ **IDENTIFIÉS
LE 28/08, sans les journaux**, par recensement AST des sites de saut puis
évaluation de chaque condition contre `requirements.txt` :

| test | cause |
|---|---|
| `services/test_nv_triangle_io.py` `test_parquet_round_trip_reel` | `pyarrow` absent **de ce poste** |
| `tarification/a1_ingestion/test_a1_ingestion.py` (round-trip parquet) | `pyarrow` absent **de ce poste** |
| `tarification/test_mapping_llm.py` `test_5_integration_reelle` | **clé `ANTHROPIC_API_KEY` délibérément absente** |

⚠️⚠️ **ET LE MODÈLE A ÉTÉ VALIDÉ DANS L'AUTRE SENS** : il prédisait 3 sauts ici,
l'exécution en a rendu 3 ; il en prédisait **1** sur la CI (où `pyarrow` est au
cœur), et le résumé de la nocturne affiche **1**. *Un modèle qui prédit
exactement le connu peut se lire sur l'inconnu.*

⚠️ **L'environnement de ce poste, re-mesuré le 28/08** : il porte `openpyxl`, `plotly`, `kaleido`, `python-docx`, `torch`, `xgboost`, `lightgbm`, `catboost`, `shap`, `optuna`, `statsmodels`, `anthropic` — et **il lui manque `pyarrow`, `cairosvg`, `xlsxwriter`, `weasyprint` et `streamlit`**. *Les deux premiers expliquent l'écart de sauts entre ce poste (3) et la CI (1).* *Un test sauté est un contrôle qui ne surveille pas : à verser au
tri.*

## RANG 1 — LE PRIX SORT FAUX, DEVANT UN ACTUAIRE, AUJOURD'HUI · **3 lots · 10 constats**

| lot | constats | ce que ça ferme |
|---|---|---|
| **1.1 Les branches de l'app + les fuites d'A5** | ✅ `a5/C6` `a5/C7` **FERMÉS** · ✅ `app/prime_ml` `app/prime_dl` **ARBITRÉS — REPORTÉS À LA MIGRATION** | A5 : trois jeux **68/12/20**, jeu de validation **exigé** (`raise`, aucun repli) ; `seed` déclaré et **inscrit au rapport**. **⚠️ L'optimisme mesuré : TabNet −13,2 %** (0,2269 → 0,1970) ; l'irreproductibilité valait **11 % d'étendue** sur le Gini **qui sert à A6 pour arbitrer**. POS-A5d + POS-A5e (6 contrôles, 2 violations plantées). **⚠️⚠️ LES BRANCHES DE L'APP NE SERONT PAS CORRIGÉES : arbitrage de Selasse du 25/08 — l'app Streamlit disparaît, on n'y touche pas, même pour une phrase.** L'exigence est écrite pour la suivante : [`EXIGENCES_MIGRATION.md`](EXIGENCES_MIGRATION.md) — **deux modes, et l'absence de comparaison jamais silencieuse** |
| **1.2 Le plan ne laisse plus déclarer ce qu'il interdit** | ✅ **FERMÉS** `plan/C1` `plan/C2` `plan/C3` — **et `plan/C9` en prime** | la garde B9 contournée par les **interactions** → **prime non proportionnelle à l'exposition (1,8339 au lieu de 2,0000)** · la **cible** déclarable en facteur · un `type` mal orthographié **détruit un facteur en silence**, `ampute=False`. **Regroupement franc** : même geste — valider l'**appartenance**, pas la combinaison. ✅ **Fermé au lot 1.2** : contrôle sur **trois surfaces** (nom source · opérandes d'interaction · colonnes produites), valeurs admises **dérivées des `Literal`** et jamais recopiées, et un **filet** — *un facteur qui ne produit aucune colonne est refusé*. ⚠️⚠️ **LA RACINE ÉTAIT DANS LA SPEC, PAS DANS LE CODE** : `plan_execution_6_actions.md` l.294 demandait le contrôle **sur `colonnes_produites()`** — le code le faisait exactement. **11 contrôles positifs**, 20/20 plans intacts |
| **1.3 Les exclusions qui détruisent un facteur légitime** | ✅ **FERMÉS** `conformite/C3` `C5` · ✅ **`C2` ET `C6` FERMÉS le 29/08** — code déjà correct, **jamais épinglé** (voir l'encadré) | la variable de **TAILLE** écartée comme « la cible déguisée » · les **6 variables de B5** toujours détruites · **6 modalités légitimes** tuées par les mots métriques. *Un facteur détruit ampute le tarif — B5 l'a chiffré à −17,4 % de Gini*. ✅ **Fermé au lot 1.3** : le test des mots métriques passe de la **sous-chaîne au MOT ENTIER** (`imprimerie` ⊅ `prime`) → **3 modalités récupérées**, et **B6 reste bloqué** (le second sens, vérifié). ⚠️⚠️ **RECADRAGE MESURÉ : sur le chemin déclaratif — celui des 6 appelants de production — RIEN n'est détruit** (`exclusions = {}`) ; C3 et C5 ne vivent que sur le chemin rétrocompat. Le reste est corrigé **par le motif** (leçon B7) : plus de « aucune action » quand une action existe, et plus d'instruction impossible à suivre. **9 contrôles positifs** |

> ⛔⛔ **CE TABLEAU AFFIRMAIT `conformite/C2` ET `C6` FERMÉS. C'EST FAUX —
> mesuré le 29/08/2026.** Ni l'un ni l'autre n'a de bloc de fermeture dans
> `releve_conformite_reglementaire.md` : le relevé n'y porte que `C1`+`C7`,
> `C3`, `C5`, `C7`. Le compte publié (**56 fermés / 95 ouverts**) est donc
> **juste** — il se dérive de l'archive, pas de cette prose ; c'était **la
> phrase qui mentait**, pas le chiffre.
>
> ✅⚠️ **TRANCHÉ LE 29/08/2026, AU SITE : C'EST LA SECONDE LECTURE.** Le code
> des DEUX était corrigé au lot 1.3 ; **rien ne l'épinglait** — le troisième
> état que le §④ nomme, et qui compte OUVERT. Les deux sont désormais fermés
> avec **8 contrôles positifs** et **6 violations plantées**.
>
> ⚠️⚠️ **ET UN TEXTE ÉTAIT RESTÉ FAUX SUR `C6`** : la docstring de
> `synthese_exclusions` annonçait « Trois motifs » alors que le tri en sépare
> **cinq** depuis le lot 1.3 — et c'était **la preuve citée par le constat**.
> *Quand un comportement change, le texte qui l'accompagne se relit.*
>
> ⚠️ **CE QU'ILS DISENT** : `C2`, une variable de TAILLE (`effectif`,
> `nb_salaries`) écartée comme « la cible déguisée » alors qu'en RC Pro
> l'effectif joue le rôle de l'exposition — et l'exposition, elle, est
> exemptée. `C6`, une fuite détectée PAR L'EFFET présentée comme une dérivée
> de la sinistralité, le tri se faisant par **sous-chaîne** (`'fuite' in
> m.lower()`) sur quatre motifs dont la docstring n'en connaît que trois.

## ⚠️⚠️ PASSAGE LIBELLÉS (25/08/2026) — LE RANG 2 EST RECOMPOSÉ

**Fait AVANT d'ouvrir le rang 2, à la granularité du CHAMP, conclu par
EXÉCUTION** (`preuves/passage_libelles.py`). Il a invalidé le classement que
j'avais proposé :

| ce que j'affirmais | mesuré |
|---|---|
| `a6/C5` est « le seul publié dans un livrable » | **il n'atteint aucun des 5 livrables** — retenu par un `isinstance(v, str)` |
| `agents/C2` mérite le rang 2 | `pipeline_agents.py` : **0 importeur de production** |
| `conformite/C1` mérite le rang 2 | la propriété qui ment a **0 lecteur** — couverte par `C7` |

⚠️ **LE LOT 2.1 TEL QUE COMPOSÉ EST À DÉFAIRE** : il réunissait un constat
couvert, un vivant et un sur module mort. Ils n'ont pas la même urgence.

⚠️⚠️ **QUATRE COUPLAGES MESURÉS — un constat peut être rendu inoffensif par un
autre, et le corriger seul PUBLIE le défaut** : `conformite/C1` ← `C7` ·
`agents/C2..C6` ← `agents/C1` · `socle/C4` `C5` ← `socle/C2` · **`a6/C5` ← un
filtre de type**, le plus fragile des quatre.

⚠️ **AUCUN CONSTAT N'EST DISQUALIFIÉ.** Un latent reste vrai : le plan est un
document opposable, « exprimable » suffit. Le passage change **l'ordre**, pas
la **validité**. **11 latents nommés, en attente.**

> ⛔⛔ **CE « 11 » N'EST PAS RE-DÉRIVABLE, ET C'EST DÉCLARÉ PLUTÔT QUE CORRIGÉ
> (29/08/2026).** Les onze ne sont **énumérés nulle part** — ni ici, ni dans
> `CARTE.md`, ni dans les relevés. Un relevé par le mot « latent » sur la même
> ligne qu'une clé rend **six** constats (`a3/C4` `a3/C7` `a3/C14` `a4/C2`
> `a5/C4` `pipeline/C1`), et cette méthode **sur-compte** (un simple renvoi
> suffit) **et sous-compte** (un latent décrit sans le mot).
>
> ⚠️ **AU MOINS UN DES ONZE EST FERMÉ DEPUIS** : `a5/C4`, rouvert par Selasse
> et clos le 29/08 (`462841a`). Le chiffre est donc **périmé d'au moins un**,
> mais *je ne publie pas « 10 » à la place : je ne peux pas le prouver.*
> **Ne pas publier un chiffre incertain à la place d'un autre.**
>
> ⚠️ **CE QU'IL FAUDRAIT POUR LE RENDRE VRAI** : énumérer les onze clés à cet
> endroit, une fois, puis les dériver comme le compte global l'est déjà par
> `ARCH-5`. Tant que la liste n'existe pas, **cette phrase est une affirmation
> de portée non mesurable** — la même dette que les comptes figés que ce
> document a déjà purgés ailleurs.

✅ **ET IL A PRODUIT UN CONSTAT NEUF** : `a6/C11` — **la fiche d'aide à la
décision est publiée à 25 %** (3 champs sur 12 ; forces, faiblesses, risques,
alternatives et questions à poser n'atteignent aucun livrable). Sur 24 champs
porteurs de texte d'A6, **18 sont muets**.

### ✅ LOT ① CLOS — `a6/C11` + `a6/C5`, ENSEMBLE

**12/12 champs** de la fiche atteignent le classeur (3/12 avant), et
l'attestation de conformité S2 est **conditionnée** à `avertissement_walk_forward`
et au statut.

⚠️⚠️ **L'ORDRE INTERNE ÉTAIT LE FOND DU LOT** : publier la fiche sans
conditionner son attestation aurait **mis une conformité Solvabilité 2 fausse
dans le classeur qui part au CAC**. Le correctif aurait *créé* le dommage que
le constat annonçait. `C5` posé **d'abord**, dans le même changement.
**9 contrôles positifs**, dont une classe entière qui **lit le classeur** pour
qu'on ne puisse plus les dissocier.

### ✅ LOT ② CLOS — `conformite/C1` + `conformite/C7`, ENSEMBLE

La propriété `controle_effet_execute` atteste désormais **l'EXÉCUTION** et non la fourniture des arguments, et elle **atteint le livrable** avec son MOTIF. ⚠️ Le couplage était orienté : la publier avant de la rendre véridique aurait attesté un contrôle qui n'avait examiné aucune colonne.
⚠️⚠️ **LA GATE A ATTRAPÉ UNE RÉGRESSION QUE J'AVAIS INTRODUITE** — `INV-11c`, un invariant écrit il y a des cycles : *l'échec du contrôle par l'effet doit LEVER*. Ma source unique s'exécutait avant et changeait le type levé. **Le test existait ; je ne l'ai pas dupliqué.** 9 contrôles positifs.

**Reste ouvert dans l'ordre arbitré** :
### ✅ LOT ③ CLOS — `qualite/C1` `C2` · `a1/C3` `C4`

**Les valeurs LIMITES et les valeurs ABSENTES.** `detecter_illisible` voit enfin ce que `to_numeric(coerce)` détruisait ; l'escalade regarde **l'union** en plus de chaque type (motif mesuré : `union_des_anomalies (196/1000, 19.6%)`) ; et les deux bornes d'A1 disent enfin ce que leur docstring déclare. ⚠️ **Aucun euro déplacé** : l'absence est SIGNALÉE (règle 3), jamais exclue. **12 contrôles positifs, chacun avec son second sens.**

**Reste ouvert dans l'ordre arbitré** : · puis **le banc étendu à A3/A4/A5 avant
leurs ~40 constats** · puis les **11 latents**.
⚠️ **`alertes_modele`, `validation_selection.verdict`, `backtest.stabilite`
restent À INSTRUIRE, pas en constats** : le banc ne prouve pas qu'aucune autre
forme d'entrée ne les publie ailleurs.

## ⚠️⚠️ RE-MESURE DES 40 (25/08) — [REMESURE_A3_A4_A5.md](REMESURE_A3_A4_A5.md)

**15 des 40 sont DÉJÀ FERMÉS**, corrigés dans le code et jamais reportés dans
les relevés — dont **`a3/C1`**, le seul que j'avais désigné comme déplaçant un
euro. **21 ouverts, 4 à lire.**

⚠️⚠️ **ET LA RE-MESURE ELLE-MÊME A FAILLI MENTIR** : un premier passage par
sondes `regex` a rendu **deux faux « fermés »** (`a3/C5`, `a4/C5` — la courbe de
Lorenz analytique est toujours là, ma regex était fausse). *Une absence de
`grep` n'est pas une absence de défaut.* **Chaque « fermé » est confirmé par une
SECONDE méthode** ; ceux qui ne le sont pas sont marqués « à lire », jamais
fermés.

## ⚠️⚠️ CLASSEMENT DES 40 CONSTATS D'A3/A4/A5 (25/08) — [CLASSEMENT_A3_A4_A5.md](CLASSEMENT_A3_A4_A5.md)

Le banc a été appliqué. **Il tranche 12 constats sur 40**, et le dire est le
résultat principal :

- **10 VIVANTS** — le champ atteint l'actuaire (`hypotheses`, `validation_*`,
  `commentaire`, `statut_rag`), dont quatre sur des **scorecards et statuts**
  qu'un actuaire lit pour signer ;
- **2 LATENTS** — `monitoring` **0/10 publié**, `sensibilite_tarifaire` **0/3** ;
- **28 HORS PORTÉE** — valeurs numériques, figures, hygiène.

⚠️⚠️ **DEUX SURFACES NE SONT PAS OUTILLÉES, ET C'EST DIT PLUTÔT QUE CONTOURNÉ** :
les **figures** (8 constats) et les **valeurs numériques** (5). Le banc marque
des chaînes — *un marqueur posé sur un nombre est détruit par l'arrondi*, et
`metriques` **1/83 n'est pas un verdict, c'est un angle mort.**

## RANG 2 — CE QUI AUTORISE CE PRIX · ✅ **RE-CLOS le 29/08/2026 — 10 sur 10**

> ⚠️⚠️ **IL A ÉTÉ ROUVERT PUIS REFERMÉ LE MÊME JOUR.** Clos 9/9, la re-mesure
> d'`a2/C8` sur une vraie fixture d'imputation l'a rouvert à **9 sur 10** ; le
> lot 2.4 le referme à **10 sur 10**. *Un rang clos peut être rouvert par une
> mesure — le dire vaut mieux que garder un compte flatteur.*

| lot | constats | ce que ça ferme |
|---|---|---|
| **2.1 Les garde-fous qui attestent sans surveiller** | ✅ **FERMÉS** `conformite/C1` `qualite/C2` · ✅ **`agents/C2` FERMÉ le 29/08** (`is not None` répondait à la mauvaise question : `_arbitrer` rend TOUJOURS un dict `a6`, échec compris) | `controle_effet_execute` atteste **la fourniture des arguments** · l'escalade compte **par type** (19,6 % exclus sans blocage) · `.success = True` **alors qu'A6 a échoué**. *Un contrôle qui atteste sans surveiller est pire qu'un contrôle absent : il ferme la question* |
| **2.2 La couche qualité ne voit pas l'absence** | `qualite/C1` `a1/C3` `a1/C4` | **100 % de NaN → 0 anomalie** · `prime_pure > 0` · le double verdict sur `exposition = 0` |
| **2.4 Un binaire imputé cesse d'être binaire** ✅ **CLOS** | ✅ **FERMÉS** `a2/C8` **et `a2/C7`** — arbitré : *ils voyagent ensemble, même défaut vu des deux côtés* · ✅ **`a2/C17` fermé PAR RETRAIT** dans le même lot | la table `STRATEGIES_IMPUTATION` est **lue** (prouvé en la changeant : `age` bascule de *moyenne 49,926* à *médiane 50,000*), le binaire reçoit le **mode** et sort en `[0.0, 1.0]`, et `_verifier_modalites_binaires` **lève** comme le fait `label` depuis toujours. *L'asymétrie entre les deux contrôles était le vrai défaut.* ⚠️ **7 violations plantées, 7 chutes** |
| **2.3 La conformité affirmée sans condition** | ✅ **FERMÉS** `a6/C5` `conformite/C7` · ✅ **`conformite/C14` FERMÉ le 29/08** — l'en-tête borne enfin sa portée surveillée (**Non-Vie seule** ; `direction_vie_epre` **0** et `direction_sante_prevoyance` **0** importateurs, re-mesuré sur **446** fichiers), la règle CJUE restant universelle | conformité **affirmée sans condition** dans la fiche de décision · « **POUR TOUTE BRANCHE** » alors que seule la Non-Vie est surveillée · `controle_effet_execute` **n'atteint aucun livrable**. *C'est ce qui part au CAC et à l'ACPR* |

## RANG 3 — LA STATISTIQUE, ET LES API LATENTES · ✅ **CLOS le 27/08/2026**

⚠️ **Reporté à l'archive le 28/08**, avec un jour de retard : les cinq lots avaient été codés et poussés sans qu'aucun bloc de fermeture ne soit écrit. **C'est le défaut que le nouveau contrôle `test_archive_fermeture_reportee.py` empêche désormais de se reproduire.**

| lot | constats |
|---|---|
| **3.1 Les statistiques fausses d'A3** | ~~`a3/C6` Gini Tweedie nul~~ ✅ **FERMÉ `b0ae396`** (mesuré **−0,078** — le zéro venait d'un défaut de `get`, et il était **flatteur** ; épinglé par `test_gini_tweedie_arbitrage.py`) · restent `a3/C4` IC 95 % faux · `a3/C7` deux Gini incomparables comparés · `a3/C14` p-value fabriquée |
| *(hors 3.1)* | ~~`a4/C2` monitoring simulé~~ ✅ **FERMÉ `16c6566`** — PSI mesuré **0,056 vs 7,59** par exécution ; ce qui restait était son **étiquette**, pas son code. Épinglé par `test_monitoring_derive_reel.py` |
| **3.2 Les scores et les rangs d'A4/A6** | ✅ **FERMÉS** `a4/C6` `a4/C9` (`5bccc33`) · `a4/C10` (`6d5eeb9`) · `a6/C6` (`e808fc7`) · `a6/C8` (`c41a6a5`) — ⚠️ `a6/C7` **versé au rang 7** |
| *(A3, hors 3.1)* | ✅ **FERMÉS** `a3/C4` (`271d50d`) · `a3/C14` (`b3dc60c`, déclaration seule) — ⚠️ `a3/C7` reste **LATENT** |
| **3.3 L'API latente** | ✅ **`pipeline/C1` FERMÉ pour l'ILLISIBILITÉ** (la plausibilité reste ouverte, faute de borne déclarée au plan ; `predire_portefeuille` rendu en conception) · `pipeline/C1` (**`tarifer()`**, +128 % sur un facteur illisible) — **descendu du rang 1** : 1 appelant, une **démo**. *Une API publique sans borne est une régression qui attend un appelant* |

## RANG 4 — LES FIGURES ET LA CHARTE · ✅ **CLOS le 29/08/2026 — 11 sur 11**

✅ **LOT 4.1 CLOS le 28/08/2026** — `charts/C1` et `charts/C2`, les deux seuls constats du rang qui publiaient un **nombre ou un verdict FAUX** sur une figure signée.

✅ **LOT 4.2 CLOS le 28/08/2026** — `charts/C3` et `charts/C5`, les SILENCES : *une figure doit déclarer ce qu'elle ne montre pas.* Les sept fonctions disent « AUCUNE DONNÉE — … » et **nomment ce qui manque** ; les trois troncatures mesurées s'écrivent sous la figure. ⚠️ **On DÉCLARE, on n'élargit pas** — `top=15` reste, un test l'exige. ⚠️⚠️ **Et le sous-cas (c) du relevé est déclaré INEXISTANT** : « distribution 1 000 → 500 » ne se reproduit pas — **1 000 sur 1 000**. *Un sous-cas qui ne se reproduit pas se déclare, il ne se corrige pas*, et un test fige cette absence.

⚠️⚠️ **ET LE DÉCOUPAGE A ÉTÉ REFAIT PAR MESURE, PAS SUR LE PAPIER.** J'allais classer les courbes analytiques en premier. Le plan des figures dit autre chose : `a3/C5` (`lorenz_glm`), `a4/C5` (`lorenz`), `a5/C4` (`convergence_loss`) et `a6/C3` (`scores_profils`) visent des figures **ÉCARTÉES du rapport signé**, chacune avec son motif écrit. Et la courbe qui EST publiée, `chart_lorenz_gini`, reçoit des points **mesurés**. *Le doublon analytique ne l'atteint pas.* ⚠️ Borne déclarée : je n'ai pas mesuré le chemin Excel ni l'app — la latence est bornée au rapport signé.

⚠️ **ET MA SONDE A PRODUIT QUATRE FAUX « FERMÉS »**, dont `a3/C5` et `a4/C5` — *les deux constats sur lesquels ce document m'avait déjà averti*. Ma regex attendait `1/(1+2g)` ; le code écrit `(1 + gini * 2)`. **Troisième fois.** Les 11 sont ouverts, aucun n'était fermé.

🔓 **SON SEUL PRÉREQUIS DÉCLARÉ — l'arbitrage 2 — EST CLOS** (27/08). Le rang est ouvrable.
✅ **LOT 4.3 CLOS le 29/08/2026** — `charts/C9` et `charts/C10`, la LISIBILITÉ. Le gradient rend **0 inversion et un écart minimal de 0,0109** (relevé : 4 et 0,0035) ⚠️ **par ÉCHANTILLONNAGE à luminance régulière, pas par une ancre chanceuse** — les deux extrémités, qui portent le sens, ne bougent pas. Et les **trois** couleurs de point lisent la source RAG.

⚠️⚠️ **UN TEST DE CE LOT A RÉFUTÉ MON ATTENTE, ET C'EST LE RÉSULTAT LE PLUS UTILE** : passer de l'or à l'ambre RAG ne sépare PAS le point du décor — contraste **1,04**, et le VERT est à **1,00** contre l'or. *La couleur ne ferme pas `charts/C10` ; le SYMBOLE le ferme.* `SYMBOLE_RAG`, déclaré depuis le lot de la charte et employé nulle part, l'est enfin — et il est **nécessaire, pas décoratif**.

✅ **LOT 4.4 CLOS le 29/08/2026** (`9c0a278`) — **`charts/C4`**, et le défaut n'était **pas l'esthétique** : les listes décoratives d'A4 et A6 contenaient `couleur_rag('VERT'/'AMBRE'/'ROUGE')` — **les couleurs de STATUT** — consommées en cycle POSITIONNEL. *Le modèle n° 5 était peint en rouge RAG parce qu'il était cinquième.* Refus motivé de migrer vers la charte : la prémisse du constat est périmée (les quatre partagent UNE palette) et l'or des agents est à **1,09** de contraste de celui de la charte. ⚠️ **Deux de mes accusations retirées par la mesure** — les trois navies sont des FONDS, et 0 paire sur 15 fusionne en deuteranopie.

✅ **LOT 4.5 CLOS le 29/08/2026** (`462841a`) — **`a5/C4`**, l'un des latents, **ROUVERT PAR SELASSE**. La courbe de convergence trace les **vraies pertes** au lieu d'une exponentielle bruitée sur 50 époques codées en dur. ⚠️ **Le remède évident était le mauvais** : semer le bruit aurait rendu une courbe FABRIQUÉE reproductible, donc crédible.

## ✅ LE RANG 4 EST CLOS — LES TROIS GELÉS FERMÉS **PAR SUPPRESSION** (4.8)

✅ **LOT 4.8 CLOS le 29/08/2026** — `a3/C5`, `a4/C5`, `a6/C3`. Arbitrage de
Selasse : **plutôt que de les garder gelés indéfiniment, supprimer le code qui
produisait ces figures.** Ce n'étaient pas des doublons inoffensifs :

| constat | figure | ce qu'elle publiait |
|---|---|---|
| `a3/C5` | `lorenz_glm` | une courbe **reconstruite du seul Gini** — deux portefeuilles de même Gini, même courbe au pixel près |
| `a4/C5` | `lorenz` | idem, plus une contradiction d'axe |
| `a6/C3` | `scores_profils` | **0,56** là où le score réel du même modèle valait **0,9001** |

⚠️⚠️ **SUPPRIMÉ PAR SITE, JAMAIS PAR NOM** — A6 définit un homonyme `'lorenz'`
qui porte les points **mesurés** de la figure publiée. Un test plante la
confusion. **222 lignes retirées**, entrées d'écart comprises, et la formule
`t ** (1/(1+gini*2))` **n'existe plus dans le code de production**.

⚠️⚠️ **ET LA QUESTION DE `a6/C3` EST PUBLIÉE À LA PLACE.** Elle était la seule à
demander *« le classement changerait-il sous un autre profil ? »*. Mesuré sur
quatre portefeuilles : **le vainqueur bascule dans 3 cas sur 4 sur la cible
coût**, marges #1-#2 à **0,008 · 0,016 · 0,021**. *Le profil est un levier sur
le prix.* La trace existante n'y répondait pas — `gouvernance_validee` vérifie
**un nom non vide**, elle dit QUI a assumé, jamais CE QUE le choix a changé.
Un **tableau** (pas une figure : quatre points seraient un « tableau déguisé »)
est publié au **chapitre 6**, HTML et Word, recalculé avec
`_calculer_scores_multicriteres` — **la formule qui décide**.

⚠️⚠️ **« GELÉ » N'EST PAS « FERMÉ », ET CE N'EST PAS NON PLUS « DÉFINITIF ».**
Les trois restent **comptés OUVERTS** dans le total : le défaut existe toujours
dans le code, vérifié au site le 29/08. Ce qui est arbitré, c'est qu'on **ne les
ouvre pas** — leurs figures sont **écartées du rapport signé**, chacune avec son
motif écrit dans `FIGURES_ECARTEES`, et le motif a été vérifié PAR EXÉCUTION :
`chart_lorenz_gini`, la courbe qui EST publiée, reçoit des points **mesurés**
(`np.cumsum(y_sort)/np.sum(y_sort)`) ; `scores_multicriteres`, la grille
publiée, lit `score_global` — **la formule qui décide**, sans la recalculer.

⚠️⚠️ **ET LE GEL SE LÈVE — IL S'EST DÉJÀ LEVÉ UNE FOIS.** `a5/C4` était le
quatrième latent ; Selasse l'a rouvert le 29/08 et il est CLOS. *Un latent
n'est pas une catégorie définitive, c'est une décision de ne pas ouvrir
aujourd'hui.*

⚠️ **BORNE DÉCLARÉE, INCHANGÉE** : la latence est bornée **au rapport signé**.
Je n'ai mesuré ni le chemin Excel ni l'app. Un lot qui voudrait les classer
définitivement devrait d'abord mesurer ces deux surfaces.

⚠️⚠️ **`charts/C4` REDÉCRIT LE 29/08, ET JE CORRIGE MON PROPRE CHIFFRE DE LA VEILLE.** J'avais écrit « a3 3/10, a4 3/11 — l'arbitrage 2 l'a amélioré ». **C'est FAUX** : je comparais à une base ÉLARGIE (V3 **+** RAG) là où le constat compare aux **8 couleurs V3**. Sur SA base : **1 sur 10 · 1 sur 11 · 1 sur 7 · 1 sur 9** — *identique au relevé*. Le constat n'a pas bougé. *Un compte n'est comparable que si l'assiette est la même — appliqué à mon propre chiffre.* Le balayage passe de **52 à 54 fichiers**. ✅ **CLASSÉ ET CLOS** par le lot 4.4.

`a3/C5` `a4/C5` `a5/C4` `a6/C3` `charts/C1` `C2` `C3` **`C4`** `C5` **`C9`** **`C10`**

Lorenz tracée non mesurée (×2) · « Convergence » analytique · « Score par
profil » sans score · badge sans borne (**125 %**, **−5 %**, **18 000 000 %**) ·
**bande verte plus large que le gate** · **7/7 figures vides indiscernables** ·
**4 troncatures silencieuses** · ⚠️ **`C9` le gradient n'est pas monotone en
luminance** (4 inversions, **0,0035** entre deux déciles voisins : *deux déciles
différents se lisent pareil*) · ⚠️ **`C10` l'ambre du RAG EST l'or des axes**
(`#D4AF37`, teinte **0°**, contraste **1,00** — la même couleur).

🔵 **Précédé de l'arbitrage 2 — la charte** (§⑤).

## RANG 5 — LES LIVRABLES · ✅ **CLOS le 28/08/2026**

✅ **FERMÉS** — `services/C1` `C2` `C3` `C4` `C5` **et `C6`** (`ea37564`, `d2dc672`, `f63be18`, `4534ea7`, reportés par `4ede1cb`).

⛔ **`a2/C9` ALLOUÉ ICI le 29/08** (classement accepté) — une **moyenne** rangée sous la clé `medianes` : `age = 49,926` pour une médiane réelle de **50,0**, `alarme = 0,8152` pour **1,0**. ⚠️ **Libellé faux, pas nombre faux** — la valeur appliquée est correcte. ⚠️ **Et il ne remonte pas au livrable, mesuré** : `median` a **zéro occurrence dans `services/`**. *Le renommer touche le format d'un JSON persisté : décision de conception.*

✅ **`agents/C4` FERMÉ** — `resume()` ne génère plus de date, elle est capturée une fois par le run et réutilisée. ⚠️ **Et le nouveau garde-fou a tiré sur ce lot même**, une heure après avoir été écrit : le test épinglait `agents/C4` avant que son bloc n'existe. *Il fonctionne sur un cas réel, pas seulement sur sa violation plantée.*

## RANG 6 — LE CÂBLAGE · ❄️ **GELÉ PAR ARBITRAGE le 29/08/2026 — PAS OUBLIÉ**

> ### ❄️ **ARBITRÉ PAR SELASSE : le branchement de l'orchestrateur attend la VRAIE migration d'interface, pas un point d'entrée temporaire.**
>
> **LA RAISON, TELLE QU'ELLE A ÉTÉ DONNÉE** : finir toute la direction Non-Vie,
> puis **attaquer l'interface prochainement, avant les autres directions**.
> Construire un point d'entrée séparé maintenant serait **du travail jeté
> presque aussitôt**.
>
> **LA CONDITION DE LEVÉE, UNE SEULE** : ⚠️ **le début du chantier de migration
> d'interface**. Le rang 6 se rouvre à ce moment-là, et pas avant.
>
> ⚠️⚠️ **GELÉ N'EST PAS FERMÉ, ET LE COMPTE NE DOIT PAS L'OUBLIER.**
> `agents/C1`, `qualite/C4` et `socle/C2` **restent OUVERTS** dans les 82 : ils
> sont comptés, mesurés, intacts. *Un rang gelé qui glisserait vers « clos »
> serait exactement le compte flatteur que cet audit poursuit.*
>
> ⚠️ **ET LES TROIS DÉFAUTS D'`agents/C1` CONTINUENT DE COÛTER PENDANT LE GEL** —
> notamment le troisième : **la moitié du tarif, le COÛT, n'est jamais
> challengée**. Le gel décale le remède, il ne suspend pas le défaut. *Ce qui
> suit reste vrai et doit être relu tel quel le jour de la levée.*

### L'ÉTAT AU MOMENT DU GEL · 🟡 **1 sur 4 CLOS · les 3 autres RE-MESURÉS, INCHANGÉS**

`agents/C1` `qualite/C4` `socle/C2` + le chantier ④.
✅ **`conformite/C10` FERMÉ le 29/08/2026, ET IL N'APPARTENAIT PAS À CE RANG** :
ce n'était pas du câblage mais **un garde-fou dont l'assiette est trop
étroite** — une colonne non numérique lui échappait EN SILENCE. Corrigé : elle
est nommée. ⚠️ **Ampleur mesurée, non gonflée** : 0 colonne texte sur 22 appels
réels du détecteur (agent ET déclaratif) — défaut réel dans la fonction,
**latent** sur les chemins.

## ⚠️⚠️ RE-MESURE COMPLÈTE DU RANG 6 (29/08/2026) — ET ELLE CORRIGE MA PROPRE MESURE

> ### ⛔⛔ CE DOCUMENT A PORTÉ, PENDANT UN LOT, UNE AFFIRMATION FAUSSE QUE J'Y AI ÉCRITE.

J'avais annoncé que `qualite/C4` et `socle/C2` **avaient changé de statut** —
« `detecter_negatifs` 2 appels », « `valider_mapping` 2 ». **C'est FAUX.** Mon
compteur additionnait les appels **internes au module qui définit la fonction** :
`controler_qualite` appelle ses propres détecteurs, `mapping_llm` appelle
`valider_mapping` de `mapping_client`. Ce ne sont pas des appelants — c'est un
module qui se sert de lui-même.

> ### **Un compte d'APPELANTS doit exclure le module qui DÉFINIT la fonction — sinon tout module cohérent paraît câblé.**

**RE-MESURE, MÉTHODE REJOUABLE** : parcourir les `.py` hors `.venv`, **exclure
les fichiers `test_*` ET les modules de définition**, compter les `ast.Call`
dont le nom est celui de la fonction.

| constat | appelants EXTERNES de production |
|---|---|
| `agents/C1` — `pipeline_agents` | **0** |
| `qualite/C4` — les 7 détecteurs | **0** |
| `socle/C2` — le moteur de mapping (5 symboles) | **0** |

**LES TROIS SONT INCHANGÉS DEPUIS LEUR RELEVÉ. Aucun n'est dans le « troisième
état ».** Le câblage ne s'est pas fait en chemin : je l'avais cru sur une mesure
fausse.

### ⚠️ ET LES TROIS DÉFAUTS D'`agents/C1` SONT INTACTS, VÉRIFIÉS UN PAR UN

**①** quatre fichiers de production assemblent la chaîne à la main —
`actuaria_app.py` **6/6**, `demos/pipeline_3lob_a1_a6_demo.py` **5/6**,
`scripts/rapport_tarif_local.py` **5/6**, et `demos/fremtpl2_demo.py` **3/6**
(celui-là est NOUVEAU depuis le relevé).
**②** `result_a5=None` subsiste en production : `pipeline_3lob_a1_a6_demo.py:152`
et `rapport_tarif_local.py:112`.
**③** les trois appelants ne passent que `col_cible='nb_sinistres'` : **la moitié
du tarif — le COÛT — n'est toujours jamais challengée.**

### ⛔ CE QUE LE RANG 6 DEMANDE VRAIMENT

Ce n'est pas un lot de correction : **c'est un câblage**, et il touche des
surfaces arbitrées. `actuaria_app.py` est **intouchable** (arbitré, l'app
disparaît). Restent les deux scripts et les démos — et la question de fond,
*qui doit appeler l'orchestrateur*, est une décision d'architecture, pas une
correction de constat.

✅ **ET ELLE A ÉTÉ TRANCHÉE LE 29/08/2026** : l'orchestrateur sera branché **par
la migration d'interface**, pas par un point d'entrée intermédiaire. La question
n'est donc plus ouverte — elle est **datée**. Voir le gel en tête de rang.

**Toujours dernier des rangs** : c'est le **remède**, pas le défaut. Câbler
l'orchestrateur avant les rangs 1-4 propagerait leurs défauts sur **trois**
arbitrages au lieu d'un. ⚠️ *Distinct de 1.1 : fermer les branches de l'app
n'est pas câbler l'orchestrateur.*

## RANG 7 — LE BRUIT GROUPÉ · **12 passages · 38 constats**

9 passages de la vague 1 (recouvrements retirés) + 3 de la vague 2 :
docstrings que le code contredit (6) · messages qui accusent le mauvais
coupable (3) · annotations et exports morts (3).

## HORS RANG — LES AUDITS · **3 ouvertures**

*Ce ne sont pas des lots de correction : on ne sait pas encore ce qu'il y a.*

| quoi | l. | pourquoi |
|---|---|---|
| **`core/elasticite.py`** | **989** | **vivant** (A4 → `resultats["principal"]`), **jamais audité**, et **c'est mon code**. 4 à 15 constats attendus. ⚠️ **Le mesurer, pas le lire** — planter les violations d'abord |
| **l'assemblage de l'app** | ~980 | `_executer_analyse` (799 l) + le bloc tarification (846 l). **Le reste de l'app : hors périmètre, déclaré** |
| `services/excel_helpers.py` | 139 | complète le périmètre |

## HORS RANG — LE TRI · 🟡 **A2, PIPELINE, A1, A3, PLAN, CONFORMITE et A6 · 27 restants**

⚠️⚠️ **ET LE COMPTE ÉTAIT DE 40 : IL EST DE 77.** Le document répartissait
les non alloués en « 38 de bruit » + « 40 non triés », mais **aucun des deux
ensembles n'est énuméré** : ils sont **indiscernables tant que le tri n'est pas
fait**. *Le tri est la seule façon de savoir lequel est lequel.*

⚠️ **LE CHIFFRE ET SA MÉTHODE, CÔTE À CÔTE** — re-dérivés le 30/08 après le tri
d'A6. Méthode rejouable : en-têtes `**Cn —**` des quatorze relevés pour les
constats réels ; clés portées par le **marqueur d'ouverture** des blocs `> ✅`
pour les fermés ; **moins `pipeline/C1`**, partiel et arbitré OUVERT.

| lecture | compte | comment il se dérive |
|---|---|---|
| constats **ouverts** | **75** | clés réelles moins clés fermées — **tenu par `ARCH-5`** |
| dont **zones TRIÉES** (`a2` 11 · `pipeline` 9 · `a3` 8 · `a1` 6 · `conformite` 6 · `plan` 6 · `a6` 2) | **48** | préfixe de la clé |
| ⛔ **jamais tracés** | **27** | le complément — *exact, sans heuristique* |

> ⚠️⚠️ **ET LA VERSION PRÉCÉDENTE DE CE TABLEAU NE TOMBAIT PAS JUSTE.** Elle
> publiait **80** ouverts, **46** triés et **33** non tracés : `80 − 46 = 34`.
> *Trois nombres dont deux seulement pouvaient être vrais, dans un tableau qui
> fait autorité.* Le complément était bon, l'un des deux autres non — et rien
> ne le signalait parce que **`ARCH-5` tient le total, jamais la répartition**.
> Le tableau est re-dérivé ci-dessus d'un seul geste, ligne à ligne.

⚠️⚠️ **ET LE DÉCOUPAGE « ALLOUÉ / NON ALLOUÉ » A ÉTÉ RETIRÉ : IL N'EST PAS
DÉRIVABLE.** Mesuré le 29/08 — **trois méthodes plausibles rendent 7, 9 et
11**. Cause : *ce document ne distingue pas une ALLOCATION d'une MENTION.*
`socle/C4` n'y figure que dans un **graphe de dépendances** ; `a2/C7` est nommé
dans la section du rang 2 **avec les mots « non tranché »**. Un `grep` voit les
deux comme un rangement.

> ### **Un compte identique là où les objets diffèrent est un compte faux.**

⚠️ Le chiffre « 64 » que ce document publiait était celui-là, et il portait la
même fragilité. **Tant que l'allocation n'est pas écrite comme une DONNÉE
(constat -> rang), aucun de ces trois nombres n'a le droit d'être publié comme
un fait.** *Recommandation ouverte, non exécutée : elle demande un accord.*

⚠️ **ET MA PREMIÈRE MESURE DE CE TABLEAU S'EST TROMPÉE, PAR LE PIÈGE CONNU :**
elle cherchait chaque clé comme mot entier et n'en trouvait que **7** tracées,
donc **70** nulle part. Six A2 ouverts sont écrits en **ligne groupée** —
`a2/C3 C4 C6 C10 C11 C12 C14` — que la recherche par clé **ne voit pas**.
*Un relevé par symbole ne voit ni les alias, ni les formes groupées.* Le compte
juste est **13 tracés, 64 restants**, et il tombe sur le même 64 que la section
ci-dessous : les deux se recoupent au lieu de se contredire.

⚠️⚠️ **ET LA PHRASE QUE CE TABLEAU REMPLACE ÉTAIT FAUSSE QUAND JE L'AI ÉCRITE :**
elle disait « **6** seulement sont nommés dans ce document, les **80** autres
ne le sont nulle part » — or le tableau du tri A2, **dans ce même document et
juste en dessous**, en nommait déjà sept de plus. *Un compte publié à côté de
ce qui le contredit.* Le motif du chantier, appliqué à la carte elle-même.

### ✅ A2 — LES 16, TRACÉS AU SITE (29/08)

| constat | mesure | classement |
|---|---|---|
| `a2/C15` | ⛔ **40 sites, 39 fichiers** — voir ci-dessous | **✅ FERMÉ ce jour** |
| `a2/C1` | ⚠️ **CORRIGÉ** : « Winsorisées : **7** » pour **7** réelles (le relevé mesurait 0 pour 9) | **✅ FERMÉ ce jour, épinglé** |
| `a2/C2` | ⚠️ **CORRIGÉ** : `colonnes_non_encodees = []`, **VERT atteint** | **✅ FERMÉ ce jour, épinglé** |
| `a2/C8` | ⛔ **VRAI, re-mesuré sur fixture d'imputation** : moyenne 0,8152 sur une colonne 0/1, **40 lignes hors modalité** | **✅ FERMÉ, rang 2** |
| `a2/C9` | ⛔ **VRAI** : 2 entrées sur 3 mal nommées ; borné, ne remonte pas au livrable | **✅ ALLOUÉ RANG 5** |
| `a2/C17` | ⛔ **CONSTAT NEUF** — « Cela évite la fuite de données » : la fuite a lieu. **Latent** (`mode='predict'` : 0 appel) | **✅ FERMÉ par retrait** |
| `a2/C7` `a2/C13` *(C7 seul)* | `a2/C7` était classé rang 6 : c'était le **même défaut** que `a2/C8` | **✅ FERMÉ avec `a2/C8`** |
| `a2/C5` | vrai (ni exclu, ni imputé ; `lignes_exclues` = compteur mort) — ⚠️ **mais les deux chemins de production sont protégés en amont** : A1 corrige, `controler_qualite` exclut (400 → 360). *Cette dépendance n'est pas dite dans A2.* | **7** |
| `a2/C3 C4 C6 C10 C11 C12 C14` | docstrings et commentaires que le code contredit — ⚠️ **C10 vécu** : ma sonde a suivi l'exemple d'usage, A2 l'a refusé | **7** |
| `a2/C7` `a2/C13` | code et déclaration morts | **6** |
| `a2/C16` | `__init__` crée `/tmp/actuaria` | **7** |

⚠️⚠️ **`a2/C15` EST SORTI DU TRI IMMÉDIATEMENT** — classé « imprécis ou daté »
sur un site, il en avait **40**. Il cachait un `FutureWarning` statsmodels sur
**le calcul du BIC, nombre publié au rapport signé**. *Un tri n'est pas un
rangement : c'est une re-mesure.*

### ✅ PIPELINE — LES 9, TRACÉS AU SITE (30/08)

⚠️⚠️ **ET LE TRI A ENCORE RAPPORTÉ UN RANG 2.** *Un tri n'est pas un rangement :
c'est une re-mesure.* Deuxième zone, deuxième trouvaille de rang.

| constat | mesuré au site le 30/08 | rang proposé |
|---|---|---|
| **`pipeline/C2`** | ⛔⛔ **LE CORRECTIF DU MOIS N'EST PAS ARRIVÉ ICI.** Portefeuille sans aucun sinistre, **les deux chemins mesurés côte à côte** : le chemin **agent** rend `success=False` et *nomme la cause* — « aucun evenement observe : le maximum de vraisemblance de l'intercept vaut log(0) » ; le chemin **déclaratif** meurt sur `pipeline_tarifaire.py:382` avec un `ValueError` **statsmodels** brut — *« This could be a boundary problem and should be reported »*, c'est-à-dire une invitation à signaler un bug à statsmodels. ⚠️ Et le repli « dégénéré mais défini » que le code annonce est **l.400**, dix-huit lignes plus loin : **inatteignable dans le seul cas qu'il prétend couvrir**. ⚠️ `pipeline_complet` est appelé en production par `actuaria_app.py:3574` | **2** |
| **`pipeline/C4`** `pipeline/C5` | `PlanTarifaire` **ne porte aucun champ `chargements`** (12 champs, vérifié) : l'« étape 6 » annoncée n'existe pas, le repli est le seul chemin. Et ce repli met **`"taxes": 0.33` en dur pour toute LoB**, alors que le commentaire annonce « auto 33 %, MRH 30 %, RC 9 % » — **la LoB n'entre jamais dans le calcul**. Une MRH reçoit la taxe auto. ⚠️ **Surchargeable** (`chargements=` l.339) et **personne ne le surcharge** : les deux appels de production passent `kw=[]`. ⚠️ **BORNE** : `prime_ttc` n'existe que dans ce fichier et deux tests — **il n'atteint aucun livrable**, et `tarifer()` n'est appelé en production que par une démo. *API latente.* | **3** *(ensemble)* |
| **`pipeline/C6`** | `grille()` — « Relativités exportables (ce que l'assureur met dans son SI) » — ne rend que `relativite_frequence`, lue du seul `glm_frequence`. La prime pure est *fréquence × coût moyen* : **la moitié du tarif manque à la grille**. ⚠️ **BORNE** : `relativite_frequence` n'existe **que** dans ce fichier, et `grille()` n'a **aucun appelant de production**. *API latente.* | **3** |
| **`pipeline/C9`** | `tarifer()` pose `date_calcul` en **UTC** (l.208) ; `pipeline_complet` passe `horodatage=datetime.now()` en **heure locale** (l.356) au rapport qualité — celui qui porte la **confirmation actuarielle nominative** de la règle 4. Deux traces du même calcul, **deux heures d'écart en été**. ⚠️ *Ce n'est pas cosmétique : c'est l'horodatage d'un acte de validation signé.* | **5** |
| **`pipeline/C3`** | 5 définitions du Gini en production (AST, chemins réels : `pipeline_tarifaire`, `a3`, `a4`, `a5`, `a6`). La docstring l.271 dit « **UNE SEULE définition** … c'est ce qui rend **impossible** la métrique divergente ». Vrai dans le fichier, **faux à l'échelle du module** — et la phrase affirme une impossibilité. | **5** |
| **`pipeline/C7`** | Docstring l.124 : « MÊME chemin que `tarifer()`, pour que l'un reproduise l'autre à **1e-6** » ; `tarifer()` **arrondit à 2 décimales** (l.239). ⚠️ **Les oracles, eux, distinguent les deux précisions** — c'est la docstring qui les confond. | **5** |
| **`pipeline/C8`** | `fillna(0.0)` sur `cout_total` (l.391), **absent** sur `expo` (l.376) et `y_freq` (l.377) ; les trois passent par `to_numeric(errors="coerce")`. ⚠️ **Sans conséquence observée** — une exposition illisible provoque un arrêt *loud*. *La protection tient par accident, pas par construction.* | **7** |
| `pipeline/C1` | **PARTIEL, et son reste est déjà rendu** : `-999` et `1e12` restent tarifés faute de **borne de plausibilité déclarée au plan** (en inventer une serait poser un chiffre que personne n'a signé), et `predire_portefeuille` demande de décider ce que le contrat de sortie **vectoriel** doit porter. *Deux questions de conception, pas du travail non trié.* | *(rendu)* |

⚠️⚠️ **CE QUE CE TRI APPREND, AU-DELÀ DES NEUF** : `pipeline/C2` est la **même
panne** que le repli d'A3 réparé ce mois-ci, restée vivante sur l'autre chemin
de production. *« Corrigé OÙ ? » — la question vaut aussi entre deux chemins qui
font le même métier.* Chercher, pour chaque correctif de ce chantier, s'il a un
jumeau sur le chemin déclaratif est une piste **bon marché et non explorée**.

### ✅ A1 — LES 8, TRACÉS AU SITE (30/08)

✅ **LES DEUX FERMABLES ONT ÉTÉ FERMÉS LE 30/08** (`a1/C1`, `a1/C6`) : trois
violations plantées, trois chutes — *l'épinglage était réel, seul le lien
manquait*. **Il reste 6 constats ouverts en A1.**

⚠️⚠️ **CE QUE CETTE ZONE APPREND : DEUX CONSTATS ÉTAIENT DÉJÀ CORRIGÉS *ET*
ÉPINGLÉS — SEUL LE REPORT MANQUAIT.** C'est un **quatrième état**, distinct du
troisième : ni « corrigé sans contrôle », ni « ouvert », mais **corrigé, épinglé,
non reporté**. ⚠️ Et `ARCH-1` ne peut pas l'attraper : il exige un bloc de
fermeture pour tout constat **nommé** par un test — or ces tests-là **ne nomment
pas** leur constat. *Rien ne relie le contrôle au constat qu'il garde ; c'est
précisément ce que le tri sert à trouver.*

| constat | mesuré au site le 30/08 | rang proposé |
|---|---|---|
| **`a1/C1`** | ✅ **CORRIGÉ** : l'identifiant vient d'abord de `plan.identifiant_contrat` (l.761), la devinette n'est qu'un repli **qui ne se tait plus**. ✅ **ÉPINGLÉ** : `POS-A1c` et `POS-A1d`. ⚠️ Il manquait **le lien**, pas le travail | **✅ FERMÉ le 30/08** |
| **`a1/C6`** | ✅ **CORRIGÉ PAR LE LOT D'UNE AUTRE ZONE** — le correctif d'`a2/C15` a traité **les six agents**, donc A1 ; le site porte le numéro `a2/C15` et `a1/C6` est resté ouvert au compte. ✅ **ÉPINGLÉ**, violation plantée **sur A1 seul** | **✅ FERMÉ le 30/08** |
| **`a1/C8`** | ⛔ **VRAI** — `_sauvegarder_audit` l.1091-1095 : `try / except Exception: pass`. **La trace d'audit persistée disparaît sans un mot**, `success=True`, `erreur=None`, `alertes=[]`. *C'est la pièce que le CAC et l'ACPR viennent chercher.* | **5** |
| **`a1/C2`** | ⛔ **VRAI, inchangé** — le commentaire l.180 dit « Empêche qu'un portefeuille Vie ou Santé soit ingéré » ; `_charger_fichier` parcourt `['non_vie', 'vie', 'sante_prevoyance']` (l.496). Le garde bloque le **paramètre** `branche`, pas le **chemin**. ⚠️ **BORNE** : l'app ne passe **jamais** `fichier=`. *Latent.* | **3** |
| **`a1/C10`** | ⛔ **VRAI, ET LA DÉRIVE CONTINUE** : l'en-tête annonce « 7 tests », le relevé en comptait **9**, il y en a **13** aujourd'hui. *Un compte annoncé qui n'est rattaché à rien vieillit tout seul.* | **7** |
| **`a1/C5`** | ⛔ **VRAI** — `'id_police'` **2 fois** dans `id_contrat`, `'nb_sin'` **2 fois** dans `nb_sinistres`. ⚠️ **BORNE MESURÉE** : les doublons sont **intra-liste**, **aucun synonyme n'est revendiqué par deux colonnes standard** — donc **aucun effet sur le mapping**. Redondance pure. | **7** |
| **`a1/C7`** | ⛔ **VRAI** — `__init__` fait `mkdir` (l.244-245). **Même famille qu'`a2/C16`**, déjà classé 7 : *ils doivent voyager ensemble.* | **7** |
| **`a1/C9`** | ⛔ **VRAI** — `verifier_tous_fichiers` : **1 définition, 0 appel** (AST, tout le dépôt), et elle annonce des fichiers Vie/Santé hors périmètre. | **7** |

> ⚠️⚠️ **ET `a1/C6` DONNE UNE DEUXIÈME FORME AU JUMEAU** : `pipeline/C2` montre
> un correctif qui n'atteint qu'**un chemin sur deux** ; `a1/C6` montre un
> correctif qui **ferme un constat d'une autre zone sans que le compte le
> sache**. *Les deux se cherchent de la même façon — en partant du SITE, pas du
> numéro.*

> ⚠️⚠️ **ET J'AI FAILLI DÉCLARER `a1/C5` CORRIGÉ, SUR LE MAUVAIS OBJET.**
> Ma première mesure comptait les **clés** du dictionnaire — 15, aucun doublon —
> alors que le constat porte sur les **valeurs des listes**. *Un compte juste sur
> le mauvais objet est un compte faux*, et il aurait fermé un constat vrai.

### ✅ A3 — LES 8, TRACÉS AU SITE (30/08)

⚠️⚠️ **QUATRIÈME ZONE, ET TROIS CONSTATS CONFIRMÉS *PAR EXÉCUTION*, PAS PAR
LECTURE.** Deux d'entre eux, je les avais d'abord mal lus (voir l'encadré).

| constat | mesuré au site le 30/08 | rang proposé |
|---|---|---|
| **`a3/C15`** | ⛔ **VRAI — LE REPLI DU REPLI CASSE.** `pred_test = np.full(...)` dans un `except Exception` ([l.1055](direction_non_vie/tarification/a3_glm/agent.py:1055)), puis `pred_test.values` à la ligne suivante ([l.1058](direction_non_vie/tarification/a3_glm/agent.py:1058)) — *un `ndarray` n'a pas `.values`*. **Il est atteint exactement quand `modele_final.predict` échoue**, c'est-à-dire dans le seul cas qu'il existe pour couvrir. ⚠️ **Le relevé comptait 2 sites, il en reste 1** : les quatre autres `np.full` sont sains | **2** |
| **`a3/C7`** | ⛔ **VRAI, MESURÉ PAR EXÉCUTION** : `comparaison_gini = {'poisson': 0.1688, 'gamma': 0.042}` → `meilleur_modele = 'poisson'`. Le Poisson est évalué sur **tout** le test (fréquence), le Gamma sur **les sinistrés seuls** (sévérité) : un `max()` sur deux populations et deux cibles différentes. ⚠️ **ET LE TWEEDIE PUBLIE UN GINI (0,0696) QUI N'ENTRE PAS DANS LA COMPARAISON** — il est pourtant dans `metriques` deux lignes plus haut. ⚠️ **BORNE** : `metriques_globales` n'a **aucun consommateur nommé** dans le dépôt. *Latent.* ⚠️ Attention à l'homonyme : le `meilleur_modele` d'A4 est **un autre objet** | **3** |
| **`a3/C13`** | ⛔ **VRAI, MESURÉ PAR EXÉCUTION** : `graphiques_validation` rend **3 sur 4**, `durbin_watson` **absent**. La jauge lit `h2_homosc["dw_stat"]` ([l.2959](direction_non_vie/tarification/a3_glm/agent.py:2959)), H2 rend `ratio_variance` depuis `87e0609`, le `KeyError` est avalé par le `try`. ⚠️⚠️ **ET LE CORRIGER N'EST PAS UN RENOMMAGE** : la jauge est graduée **0 à 4, « 2 Idéal », bandes 1,5-2,5** — l'échelle d'un Durbin-Watson. Un ratio de variance a des seuils **2,0 / 3,0**. *L'échelle appartient à une statistique que H2 ne calcule plus.* | **4** |
| **`a3/C12`** | ⛔ **VRAI** : `significatif` code `0.05` **en dur** (l.1109, l.1378) alors que `SEUIL_PVALUE` existe (l.200) — et le stepwise ne retenant que `p <= SEUIL_PVALUE`, **le champ est toujours vrai**. *Un champ sans information.* | **5** |
| **`a3/C11`** | ⚠️ **PARTIELLEMENT CORRIGÉ** : sur les 5 renvois, **3 racontent désormais la suppression** (« Phase 1, `VARS_GLM` supprimé ») ; **2 restent faux** — l.699 « On part des variables prioritaires de la sous-branche (VARS_GLM) » et l.724 | **7** |
| **`a3/C16`** | ⛔ **VRAI, 5 entrées sur 23.** ⚠️ **Et mon filtre en avait compté 6** : `cotisation_annuelle` est un terme de prime **non-vie parfaitement légitime**, il ne fait pas partie du constat. *Un filtre par sous-chaîne sur-compte.* | **7** |
| **`a3/C17`** | ⛔ **VRAI**, 3 occurrences (l.48, 322, 3516). ⚠️ **Nuance mesurée** : `plan` a un défaut `None`, donc `run(result_a2)` est **syntaxiquement valide** ; c'est à l'exécution que le module refuse — `success=False`, « A3.run exige un plan ». *L'exemple documenté est un appel que le module rejette.* | **7** |
| **`a3/C18`** | ⛔ **VRAI, ET LA DÉRIVE A CHANGÉ DE SENS** : en-tête « 7 tests » ; le relevé en comptait **4** ; il y en a **8** aujourd'hui. *Troisième zone où un compte annoncé rattaché à rien vieillit tout seul* (`a1/C10`, `a2/C14`) | **7** |

> ⚠️⚠️ **DEUX FOIS DANS CE LOT, MA PREMIÈRE LECTURE A FAILLI FERMER UN CONSTAT
> VRAI — ET LES DEUX FOIS PAR MON INSTRUMENT, PAS PAR LE CODE.**
> ① `a3/C13` : j'ai lu « `dw_stat` : **aucune occurrence** » — ma recherche
> s'arrêtait à ses 14 premières lignes, remplies par `ratio_variance`, **avant**
> d'atteindre la l.2959. *Une limite d'affichage n'est pas une absence.*
> ② `a3/C16` : mon filtre par sous-chaîne comptait `cotisation_annuelle` comme
> Vie/Santé. *Un relevé par symbole sur-compte au texte.*
> **Les deux ont été tranchés en allant au SITE, puis en EXÉCUTANT.**

### ⛔⛔ PLAN — LES 7, TRACÉS AU SITE (30/08) · **ARRÊT DEMANDÉ**

> ## ⛔⛔ `plan/C5` — LA PORTE DU DOCUMENT OPPOSABLE ACCEPTE N'IMPORTE QUOI, ET L'EURO BOUGE.

**Mesuré par exécution, pas lu.** `PlanTarifaire.depuis_dict` accepte **en
silence** toute clé inconnue :

```
  famille_severity (anglais)      ACCEPTE   -> famille_severite = 'gamma'
  identifiant_contract (anglais)  ACCEPTE   -> identifiant_contrat = None
  echeances (pluriel)             ACCEPTE   -> echeance = None
  cle totalement inventee         ACCEPTE   -> aucun signal
```

**L'actuaire qui écrit `famille_severity: lognormal` signe une log-normale et
obtient une gamma.** Ce que cela déplace, mesuré sur 1 500 contrats, même
portefeuille, même graine :

| famille | prime totale | prime moyenne |
|---|---|---|
| `gamma` (ce qu'il obtient) | **4 217 405,34 €** | 702,90 € |
| `lognormal` (ce qu'il a signé) | **4 259 529,66 €** | 709,92 € |

> ### ⛔ **+1,00 % de prime totale · +42 124 € · jusqu'à 525,35 € d'écart sur UN SEUL contrat — pour une faute de frappe que rien ne signale.**

⚠️⚠️ **BORNE, ET ELLE COMPTE** : les **20 plans livrés sont sains** — 0 clé
inconnue, vérifié fichier par fichier contre les 12 champs de la dataclasse.
**Le défaut est un MÉCANISME, pas un dégât constaté aujourd'hui.** *C'est
pourquoi je propose le rang 1 sans affirmer qu'un prix est faux en ce moment :
la porte est ouverte, personne n'est encore entré.*

| constat | mesuré au site le 30/08 | rang proposé |
|---|---|---|
| **`plan/C5`** | voir l'encadré — **mesuré par exécution**, l'écart de prime est chiffré | **1** *(à arbitrer)* |
| **`plan/C7`** | **RE-MESURÉ : 0/20 pour les trois rôles** (`identifiant_contrat`, `echeance`, `comportement`), lu dans les 20 YAML. Le mécanisme d'échéance existe et est correct ; **aucun plan ne l'active**, donc tout client apportant un **historique de renouvellement** (~67 % de « doublons » pour un seuil ROUGE à 5 %) est **refusé avant d'être lu**. ⚠️ *Le corriger n'est pas du code : c'est déclarer, LoB par LoB, quelle colonne porte l'identité et l'échéance.* **Question rendue** | *(conception)* |
| **`plan/C8`** | **DÉJÀ À L'ARDOISE**, arbitré « VERSIONNER, ne pas omettre ». Non re-ouvert ici | *(arbitré)* |
| **`plan/C4`** | ⛔ **VRAI** : `config_encodage` **existe toujours** sur `PlanTarifaire` et n'a **aucune référence dans le dépôt** — ni appel, ni test, ni mention. Sa docstring dit « *Ce que A2 consomme* » : A2 honore le plan mais **le lit directement**. *Même famille qu'`a2/C7` et `a3/C11` : une déclaration morte qui décrit un contrat qui passe ailleurs* | **7** |
| **`plan/C6`** | ⛔ **VRAI, et les deux côtés vivent** : `verifier_completude_plan` produit sa forme pour **3 sites de production** (a3, a4, a5) ; `synthese_colonnes_plan_manquantes` en consomme une autre pour **3 sites de production** (les trois services de rapport). Le mélange rend `None` — « rien à signaler » — sur un plan amputé. ⚠️ **Aucun appelant ne fait l'erreur** : le défaut est **la forme du piège** | **7** |
| **`plan/C10`** | ⛔ **VRAI** : `FACTEURS_TARIFAIRES_AUTORISES` existe et pèse **6 références de production**, toutes dans `core/conformite_reglementaire.py`. La phrase de l'en-tête — « *la désynchronisation devient IMPOSSIBLE PAR CONSTRUCTION* » — décrit le chemin déclaratif, pas le module | **7** |
| **`plan/C11`** | ⛔ **VRAI** : `colonnes_obligatoires` — **production 0**, définition 2 (usage interne), test 1. *Pas du code mort, pas une interface non plus* | **7** |

> ⚠️ **ET MON COMPTEUR D'APPELANTS A DOUBLÉ, RATTRAPÉ AVANT PUBLICATION.** Un
> `ast.Call` dont la fonction est un `ast.Name` était compté **deux fois** :
> j'ai lu « 6 appelants de production » là où il y en a **3**. Corrigé en
> dédupliquant par `(fichier, ligne)`. *Un compte se rend rejouable — et se
> relit avant d'être écrit.*

## ✅ CHANTIER `plan/C7` — LES RÔLES DE DONNÉES · **CLOS, 5 ÉTAPES SUR 5**

> ### ✅ **`plan/C7` FERMÉ le 30/08/2026.** `identifiant_contrat` **20/20**, `echeance` **20/20**.
>
> ⚠️⚠️ **L'ORDRE ÉTAIT LE SUJET.** Appliquer l'étape 5 en premier aurait
> **cassé** tout client à identifiant alphanumérique (100 % d'illisibles) et
> tout historique de renouvellement (66,7 % de faux doublons). **Chaque état
> intermédiaire est resté strictement meilleur que le précédent** — c'est la
> propriété que le réordonnancement visait, et elle a tenu de bout en bout.
>
> **Deux constats neufs ouverts ET fermés en chemin** : `qualite/C7`
> (l'identifiant jugé par le détecteur des grandeurs) et `services/C12` (la
> synthèse qualité ne sortait que par le prompt).
>
### ⚠️⚠️ `comportement` RESTE 0/20 — DÉCISION ASSUMÉE, PAS UN OUBLI

**Confirmé et consigné le 30/08/2026 pour qu'il ne redevienne pas une
question.** Le bloc `comportement` porte **trois champs indissociables** —
`issue` (le contrat a-t-il été renouvelé ou résilié ?), `prime_precedente`,
`prime_proposee` — et `core/plan_tarifaire.py` le dit lui-même :

> *« Une élasticité-prix répond à une VARIATION de prix, pas à un niveau :
> l'issue sans les deux primes ne dit rien, et deux primes sans issue ne disent
> rien non plus. Un bloc à moitié déclaré promettrait une capacité qu'il ne
> porte pas — c'est très exactement le défaut que cet audit poursuit. Le bloc
> ENTIER absent, lui, n'est pas une erreur : aucun des vingt plans n'en a, et
> la chaîne tarife sans. »*

**La raison de ne pas le déclarer maintenant** : les trois champs exigent des
données que le dépôt ne possède pas — l'issue d'échéance et les deux primes
d'un exercice à l'autre. En déclarer un ou deux **promettrait une élasticité**
que rien ne pourrait calculer. *Zéro sur trois est cohérent ; deux sur trois
serait une capacité affichée et absente.*

⚠️ **Condition de réouverture** : le jour où un fichier client porte les
**trois** champs. Pas avant, et pas partiellement.

### ✅ LE POINT D'ESCALADE — PROUVÉ PAR EXÉCUTION SUR LES 20 PLANS LIVRÉS

**Mesuré le 30/08/2026**, portefeuille conforme à chaque plan, 200 contrats ×
3 exercices :

| cas | résultat sur les **20 plans** |
|---|---|
| historique multi-exercice, **la colonne est là** | ✅ **20/20** : escalade `False`, bloque `False`, **600/600 conservées**, aucune anomalie |
| **second sens** — 30 vrais doublons (même exercice) | ✅ **20/20** : exclus en **règle 1** |
| le plan déclare l'échéance, **le fichier ne l'a pas** | ⚠️ **20/20 escaladent** — mais **0 exclusion, 600/600 conservées** ; une confirmation nominative débloque |

> ### ⚠️⚠️ ET J'AVAIS ÉCRIT UNE PHRASE TROP LARGE — JE LA CORRIGE ICI.
>
> Mon rapport de l'étape 5 disait : *« le point d'escalade a disparu de fait :
> l'échéance étant déclarée, un historique ne déclenche plus rien »*. **C'est
> vrai du premier cas, faux du troisième.** Ce qui fait disparaître l'escalade
> n'est pas la **déclaration au plan** — c'est la **présence de la colonne dans
> le fichier client**. *Une affirmation plus large que ce que le code porte :
> le motif même de cet audit, sur ma propre phrase.*
>
> ⚠️ **Et le comportement résiduel reste acceptable, mesuré** : rien n'est
> exclu, rien n'est perdu, le motif nomme le remède, et une signature
> actuarielle débloque. *C'est une demande de confirmation, pas un refus.*

⚠️ **Les 20 déclarent l'échéance — il n'y a AUCUN plan sans**, contrairement à
ce que mon rapport laissait entendre en évoquant « le seul plan restant ».

**Plan validé par Selasse le 30/08**, dans l'ordre mesuré : chaque état
intermédiaire est **strictement meilleur** que le précédent.

| # | étape | état |
|---|---|---|
| **1** | assiette de l'illisibilité + détecteur d'absence (`qualite/C7`) | ✅ **CLOSE le 30/08** |
| **2+3** | paire `(identifiant, échéance)`, règle 1 → 3, **et** sortie non-IA (`services/C12`) | ✅ **CLOSES le 30/08** |
| **4** | vocabulaire : `date_echeance` dans `SYNONYMES_COLONNES` **et** `_roles_attendus` | ✅ **CLOSE le 30/08** |
| **5** | les 20 plans, avec les 7 arbitrages | ✅ **CLOSE le 30/08** |

⚠️⚠️ **POURQUOI L'ÉTAPE 1 VIENT D'ABORD, MESURÉ** : elle frappe **tout
fichier**, même mono-exercice. Placée après l'étape 5, elle aurait livré 20
plans **cassés à la livraison** ; placée après l'étape 4, elle aurait rendu le
mapping LLM **activement trompeur** — Claude proposant la bonne correspondance
et la chaîne la refusant, sans que rien ne désigne le vrai coupable.

✅ **ÉTAPE 4 — LE VOCABULAIRE, DANS LES DEUX SYSTÈMES.** Ajouter le nom
canonique à un seul des deux est **inopérant** : `mapping_llm` n'importe pas
`SYNONYMES_COLONNES`, il dérive du plan. ⚠️⚠️ **Et c'était pire que muet** :
`roles.get(c, 'facteur')` présentait l'échéance au modèle comme un **facteur
tarifaire**, c'est-à-dire une grandeur **à modéliser** — l'inverse exact de ce
que le plan déclare pour ces colonnes. Mesuré : `date_echeance` était la
**seule** colonne à tomber sur ce défaut ; il est désormais **vide**, et un
contrôle épingle la propriété plutôt que le seul cas.
⚠️ **12 synonymes, aucune collision** sur les 126 existants, et **l'échéance
n'a aucun synonyme commun avec `annee_survenance`** — *l'une est la période de
couverture du CONTRAT, l'autre l'année où le SINISTRE est survenu ; dédoublonner
sur la seconde trancherait sur la mauvaise grandeur.*
⚠️ **La valeur est un DISCRIMINANT OPAQUE** : jamais parsée, jamais comparée,
jamais soustraite. *Cela évite un contrat de date là où une clé de partition
suffit.*

⚠️ **RGPD vérifié avant tout code, par sentinelles sur un prompt réel** :
aucun identifiant, aucun nom, aucun montant, aucune date ne sort — seuls des
noms de colonnes et des formes. `apercu_caviarde` est la frontière unique, et
plus aucun `to_csv()` / `.head(` ne mène à un prompt.

✅ **`services/C12` OUVERT ET FERMÉ AVEC L'ÉTAPE 2+3** — la synthèse qualité
n'atteignait le rapport signé que par `_construire_contexte_tarif`, le prompt.
`avertissement_qualite` + `_bloc_qualite_html`, **dans les deux formats**, et
la preuve se fait **sans clé API**.

⛔⛔ **UN POINT DE MÉTHODE RENDU, NON TRANCHÉ PAR MOI.** Sans échéance déclarée,
les lignes sont **conservées** (0 exclusion, 900/900) — mais le signalement à
**66,7 %** déclenche toujours l'**escalade** de la règle 4, donc `bloque=True`
tant qu'aucune **confirmation actuarielle nominative** n'est donnée.
*Ce n'est pas un rejet silencieux et ce n'est pas un blocage total* — une
signature débloque, et le message dit désormais **quoi faire**. Mais un
historique de renouvellement, fichier parfaitement normal, exige cette signature
tant que `echeance` n'est pas déclarée (étape 5).
⚠️ **Je n'ai PAS exempté ce code de l'escalade** : la règle 4 énonce sa propre
**règle d'asymétrie** — *« le nouveau critère ne peut qu'AJOUTER des escalades,
jamais en retirer »*. L'exempter aurait contredit une règle que le module
déclare sur lui-même, sur une porte réglementaire. **Arbitrage rendu.**

### ✅ CONFORMITE — LES 6, TRACÉS AU SITE (30/08) · **4 confirmés PAR EXÉCUTION**

| constat | mesuré au site le 30/08 | rang |
|---|---|---|
| **`conformite/C4`** | ⛔ **VRAI, ET PLUS GRAVE QUE « SILENCIEUX ».** L'exemption ne supprime pas seulement l'exclusion : elle supprime l'**ALERTE**. Mesuré sur une colonne **identique à la cible** (`nb_sinistres + 1e-6`) — *sans* exemption : `alertes = {'antecedents_sinistres_n1': {'spearman': 1.0, 'gini_normalise': 1.0}}` ; *avec* : **`fuites={}` ET `alertes={}`**. Elle traverse **sans une trace**. ⚠️ **Le chemin par le NOM, lui, alimente `alertes`** — *l'asymétrie entre deux contrôles voisins, et c'est le révélateur* | **2** |
| **`conformite/C12`** | ⛔ **VRAI, ET PLUS ÉTROIT QUE LE RELEVÉ.** Sur les **4 branches** de `synthese_exclusions`, **une seule** pointe encore la constante (« *déclarez-la (FACTEURS_TARIFAIRES_AUTORISES)* », l.1267-1268). Les autres disent déjà « *déclarez-les DANS LE PLAN DE TARIFICATION SIGNÉ* » (l.1278) et « *déclarez-la au plan* » (l.1291). *Deux branches corrigées, une oubliée : l'asymétrie entre voisines, encore* | **5** |
| **`conformite/C9`** | ⛔ **VRAI, mesuré par exécution** : la fonction rend `{'zorglub': {'spearman': 1.0, 'gini_normalise': 1.0}}` — un **dict** — quand la docstring annonce `{colonne: corrélation}` et un critère de Spearman ; le code applique `max(spearman, gini_normalise)`. *Le texte ne mentait pas quand il a été écrit ; il est devenu faux.* | **5** |
| **`conformite/C8`** | ⛔ **VRAI, MAIS BORNÉ — et la borne renverse le classement.** Le motif porte bien `{'spearman': 1.0, ...}` et `['nb_sinistres']`, de la syntaxe Python dans un texte. ⚠️ **Il n'atteint AUCUN livrable** : les **trois** surfaces (`rapport_equipe_tarif:174`, `rapport_modeles_tarif:1365`, `tarif_excel:853`) passent par `synthese_exclusions`, qui **réécrit sa propre phrase** — mesuré : **0 accolade, 0 crochet**. Le motif brut reste dans `MatriceX.exclusions` → `exclusions_conformite`. ⚠️ **Le relevé disait « 5 fichiers de production »** ; par AST, en écartant l'**homonyme** `RapportQualite.exclusions`, ils sont **4** | **7** |
| **`conformite/C11`** | ⛔ **VRAI, borné, re-mesuré** : le log porte `LISTE BLANCHE`, **pas** `C-236/09` ni « traçabilité ». ⚠️ **Mais `MatriceX.exclusions` porte bien « genre ou proxy de genre — CJUE C-236/09 »**, et c'est lui qui atteint l'actuaire. *La traçabilité existe — pas là où la docstring la place* | **7** |
| **`conformite/C13`** | ⛔ **VRAI** : A2 **n'écrit jamais** `valeur_mobilier` — **0 affectation**, mesuré ; elle la **lit** (l.664-666) pour construire `valeur_par_m2`. Colonne **source**, pas dérivée. Autorisée dans les deux cas, donc sans conséquence | **7** |

> ⚠️⚠️ **CE QUE CETTE ZONE APPREND : L'ASYMÉTRIE ENTRE VOISINS, DEUX FOIS.**
> `C4` — le chemin par le nom alerte, celui par le plan se tait.
> `C12` — trois branches disent « au plan », la quatrième dit encore « en liste
> blanche ». *Chercher ce qui protège le voisin et pas celui-ci reste le
> révélateur le moins cher de cet audit.*
>
> ⚠️ **ET UNE BORNE A RENVERSÉ UN CLASSEMENT** : `conformite/C8` semblait un
> défaut de texte publié — jusqu'à ce que la mesure montre que **la synthèse
> réécrit**. *Vérifier ce qui atteint le livrable, pas ce qui est écrit dans le
> code.*

### ✅ A6 — LES 6, TRACÉS AU SITE (30/08) · **4 FERMÉS LE JOUR MÊME**

> ### ✅ **`a6/C1`, `a6/C2` et `a6/C4` FERMÉS le 30/08/2026 — SANS TOUCHER AU CODE DE PRODUCTION.**
>
> Le tri les avait mesurés en **quatrième état** : corrigés, épinglés par des
> contrôles qui **discriminent**, mais **nommés par aucun test**. Le lot court
> n'a fait qu'une chose : **écrire la clé à côté du contrôle qui la tient**, et
> le bloc de fermeture dans le relevé. **0 ligne de production modifiée.**
> *Trois constats de la classe A — « publie du faux à un actuaire qui signe » —
> passent de invisibles à fermés pour le coût d'une docstring.*

| constat | mesuré au site le 30/08 | rang |
|---|---|---|
| **`a6/C1`** | ✅ **FERMÉ — corrigé et épinglé de longue date, nommé ce jour.** `ae` vaut `somme_obs / somme_att` où l'attendu est `pred x exposition` (l.1549-1555), et l'unité est **mesurée, pas supposée** (`Σy/Σ(pred×expo) = 1,0000` contre `Σy/Σpred = 0,5533`). Le chemin sans colonne temporelle rend `ae_ratio = None` et publie le rapport de stationnarité **sous son propre nom**. ⚠️ **Violation plantée** (`ae = m_te / m_tr`) : **2 contrôles tombent** | ✅ **FERMÉ** |
| **`a6/C2`** | ✅ **FERMÉ — corrigé et épinglé de longue date, nommé ce jour.** La prédiction de la fenêtre est **conservée** (`preds_par_annee`, l.1584) ; chaque segment se compare à ce que **le modèle prédit POUR LUI** (l.1617-1621). Les quintiles sont découpés sur le risque **prédit**, plus sur la cible observée. ⚠️ **Violation plantée** (attendu = moyenne du train) : **1 contrôle tombe** | ✅ **FERMÉ** |
| **`a6/C4`** | ✅ **FERMÉ — corrigé et épinglé de longue date, nommé ce jour.** Barres `gini_test` (l.3234), radar sur `score_stabilite` / `score_rmse` (l.3299-3301). ⚠️ **Deux violations plantées séparément** — `gini_test`→`gini`, puis `score_*`→`stabilite`/`rmse_norm` : **un contrôle tombe à chaque fois** | ✅ **FERMÉ** |
| **`a6/C9`** | ✅ **FERMÉ le 30/08 — arbitrage de Selasse : LEVER, pas retomber.** Les 3 entrées mortes étaient exactes ; **la moitié qui décide** ne l'était pas : `xgboost_tweedie`, calibré à **chaque** run (59 occ. dans une gate réelle), classé, et **absent de la table**. Trois défauts nus `0.5`/`0.6`/`0.7` remplacés par **une porte unique sans défaut**, `interpretabilite_de`. ⚠️ **Aucun euro déplacé, et c'est un contrôle** : `0.60` reproduit exactement l'ancien défaut d'A4. **2 violations plantées** (4 contrôles tombent, puis 1) | ✅ **FERMÉ** |
| **`a6/C7`** | ⛔ **VRAI, borné.** `top_modeles` est reçu (l.1848) et **jamais lu** : 0 usage dans les 47 lignes du corps, mesuré par AST. La docstring annonce « les 3 meilleurs modèles ». ⚠️ **Aucun livrable n'est touché** : `courbes` n'a **aucun consommateur de production** hors A6 (AST, chemins réels), et `chart_lorenz_gini` reçoit **les deux** Gini avec le commentaire qui dit lequel est le plafond | **7** |
| **`a6/C10`** | ⛔ **VRAI, et l'écart a DOUBLÉ depuis le relevé** : **7** annoncés, **30** réels (24 au relevé). ⚠️ **Ce n'est pas un défaut d'A6 — c'est un gabarit** : la ligne `N tests ·` existe dans **7** fichiers du dépôt, **6 sont faux**, et les 6 sont les six agents de tarification, **tous à « 7 »**. Le seul juste annonce « 1 test » et en a 1 | **7** |

> ### ⚠️⚠️ CE QUE CETTE ZONE APPREND ① — L'ASYMÉTRIE ENTRE VOISINS, ET ELLE EST ICI DANS SA FORME LA PLUS NETTE
>
> Deux tables jumelles, même forme, même risque de dérive :
>
> | table | `xgboost_tweedie` | ce qu'elle décide | son défaut est-il DÉCLARÉ ? |
> |---|---|---|---|
> | `FAMILLES_MODELES_ML` (A4) | **présent** | un **libellé** de famille | ✅ oui — la docstring nomme le risque (« *tout modèle ajouté ultérieurement sans mise à jour immédiate* ») et le défaut s'appelle `'Autre ML'` |
> | `INTERPRETABILITE` (A6) | ⛔ **absent** | **20 %** du score qui **choisit le modèle qui tarife** | ⛔ non — trois défauts nus, `0.5` / `0.6` / `0.7`, pas un mot |
>
> **La table décorative est gardée et couvre le modèle ; la table qui décide
> n'est ni gardée ni complète.** ⚠️ Et **aucun test n'exerce la table** :
> `INTERPRETABILITE` n'est **nommée par aucun test** (0 occurrence), et les
> **14** sites de fixture qui portent la clé `interpretabilite` la
> **fournissent en dur** — pas un seul ne passe par la recherche qui a le
> défaut. ⚠️ *Compté par AST en écartant l'**homonyme** : la même clé désigne
> un **poids** dans un dict de pondération (1 site) et une **valeur** dans un
> dict de modèle (14). Un `grep` les additionnait à 15.*
>
> ### ⚠️⚠️ ② LA VALEUR EST JUSTE — PAR COÏNCIDENCE, ET JE NE LA JUSTIFIE PAS
>
> `xgboost_tweedie` reçoit `0.6`, exactement ce que `xgboost` déclare. **Rien ne
> l'a voulu** : c'est le défaut d'A4 qui vaut la valeur modale des modèles d'A4.
> Mesuré, sur une fixture où stabilité et RMSE sont **égales** entre les deux
> rivaux, pour que le seul écart soit celui qui vient du défaut :
>
> ```
>   defaut=0.5 (celui ecrit pour A3)  -> #1 ML_XGBOOST          marge +0.0138
>   defaut=0.6 (celui d'A4, ACTIF)    -> #1 ML_XGBOOST_TWEEDIE  marge +0.0062
>   defaut=0.7 (celui ecrit pour A5)  -> #1 ML_XGBOOST_TWEEDIE  marge +0.0262
> ```
>
> **Le vainqueur bascule d'une ligne de défaut à l'autre.** Un pas de `0,1`
> vaut `0,1 × 0,20 = 0,0200` sur le score global — et les marges #1-#2
> **mesurées sur cet agent** au lot `a6/C3` valaient **0,008 · 0,016 · 0,021**.
> *Un pas de défaut dépasse deux des trois marges réelles.*
>
> ⛔ **AUCUN EURO N'A BOUGÉ, ET JE LE DIS AUSSI** : la valeur active est `0.6`,
> déterministe, et c'est celle que la famille porterait. C'est un **mécanisme,
> pas un dégât** — la même forme que `plan/C5`.
>
> ### ✅ ③ LE QUATRIÈME ÉTAT, TROIS FOIS — ET REFERMÉ LE JOUR MÊME
>
> `C1`, `C2` et `C4` étaient **corrigés**, **épinglés par des contrôles qui
> discriminent** (5 contrôles, 4 violations plantées, tous tombent) — et
> **nommés par aucun test**. `ARCH-1` ne pouvait donc pas les voir, et le compte
> les portait ouverts. *C'était la moitié d'A6 : trois constats de la classe A —
> « publie du faux à un actuaire qui signe » — déjà réparés sans que le
> document le sache.*
>
> ⚠️⚠️ **CE QUE CE LOT COÛTE ET CE QU'IL PROUVE.** Il n'a modifié **aucune ligne
> de production** : il a écrit **trois clés** dans les docstrings des contrôles
> qui les tenaient déjà, et **trois blocs** dans le relevé. *Le quatrième état
> n'est pas un défaut de code — c'est un défaut de CHAÎNAGE entre le correctif
> et le document qui fait autorité.* Le chercher coûte une lecture ; le laisser
> coûte un compte faux à l'ACPR.
>
> ⚠️ **Le sceau n'a pas été repris de confiance** : les 4 violations ont été
> replantées **ce jour-là**, en `py -B` avec `PYTHONDONTWRITEBYTECODE=1`.
> *Nommer un constat sur la foi d'un test qu'on n'a pas vu tomber, ce serait
> refaire le défaut qu'on ferme.*

### ⛔ À FAIRE EN FIN DE TRI — LES JUMEAUX ENTRE CHEMINS

> **Arbitré le 30/08 : pas maintenant, mais noté.** `pipeline/C2` a montré qu'un
> correctif peut n'atterrir que sur **un** des deux chemins de production.
> **Reprendre TOUS les constats fermés en août et vérifier, pour chacun, s'il a
> un jumeau vivant sur le chemin déclaratif** — ⚠️ **et aussi un jumeau dans une
> AUTRE ZONE resté ouvert au compte**, comme `a1/C6` fermé par le lot d'`a2/C15`. *« Corrigé OÙ ? » vaut aussi
> entre deux chemins qui font le même métier.* À lancer **quand le tri est
> terminé**, pas avant.

### ⛔ LES 27 AUTRES NE SONT PAS TRACÉS, ET JE LE DIS

**Dérivé le 30/08 par préfixe de clé sur les 79 ouverts — exact, sans
heuristique de texte** ; les sept zones triées en sortent :

`a4` 5 · `socle` 5 · `agents` 4 · `qualite` 4 · `a5` 3 · `charts` 3 ·
`services` 3. **Total 27.**

⚠️ **ET J'AI ÉCRIT CETTE RÉPARTITION AVANT DE LA DÉRIVER, UNE FOIS DE PLUS.**
J'y avais mis `qualite` 3 et un `plan` 1 qui n'a rien à y faire — `plan` est
tracé. *Dérive d'abord, écris ensuite : la règle vaut aussi quand le chiffre
paraît évident.*

⚠️ **La répartition publiée avant celle-ci était fausse** (`a1` 8, `pipeline` 8,
`a3` 7, `a6` 5, `socle` 3...) : elle retranchait en silence les constats nommés
dans une section de rang, c'est-à-dire qu'elle appliquait l'heuristique
mention/allocation que le §② vient d'écarter.
**Aucun rang ne leur sera attribué sans être allé au site** — les classer par
habitude serait exactement ce que ce tri doit éviter.

Vague 1, classes B et C, **non alloués**. **Je ne les ai pas triés et je le
dis** plutôt que de les ranger au jugé.

---

# ④ LA RÈGLE DE FERMETURE — elle vaut pour chaque lot

> **Un constat n'est FERMÉ que si un CONTRÔLE POSITIF NOMMÉ l'épingle.**
> Un code corrigé sans contrôle peut régresser sans un mot : c'est un
> **troisième état**, et il se distingue. *Il y en a déjà un dans l'archive.*

Et par lot, le livrable est invariable : **① propreté · ② diff indexé vérifié ·
③ preuve · ④ gate lue au fichier — puis STOP.**

## ⚠️⚠️ LA QUESTION À POSER À TOUT GARDE-FOU, ET SA FORMULE

> ### **Un garde-fou qui exclut la seule chose qui compte n'en est pas un.**

**Arbitré par Selasse le 26/08/2026, à porter à chaque lot.** Un contrôle peut
être présent, correct, motivé et testé — et ne rien surveiller, parce que son
**assiette** exclut le cas qui survient. Trois instances mesurées dans ce
module, toutes trouvées en cherchant l'assiette et non le contrôle :

| garde-fou | assiette apparente | ce qu'elle excluait |
|---|---|---|
| anti-sélection A6 (`gini < 0` → ROUGE) | tout modèle de production | ceux dont le Gini est un **littéral** — donc le Tweedie, **seul candidat** sur la cible par défaut (`a3/C6`) |
| catalogue des figures | « empêche la liste de se périmer » | les **motifs périmés** : il tombe sur une figure *nouvelle*, jamais sur une *accusation qui vieillit* (`a4/C2`) |
| contrôle par l'effet | « toutes les cibles » | une cible **présente mais vide** — `NaN == 0.0` est faux |

⚠️ **DEUX QUESTIONS, PAS UNE.** À « **sur quelle assiette ?** » s'ajoute
« **cette valeur est-elle mesurée, ou est-ce un défaut de `get` ?** » — un
`dict.get(clef, 0)` fabrique une valeur **indiscernable d'une mesure**, et le
garde-fou la lit sans broncher.

⚠️ **ET LA VALEUR FABRIQUÉE EST PRESQUE TOUJOURS FLATTEUSE** : le `0` du
Tweedie masquait un Gini **négatif**, comme le plancher d'A5 masquait un écart.

---

# ⑤ LES CINQ ARBITRAGES QUI VOUS APPARTIENNENT

*Aucun n'est un lot. Chacun porte ma recommandation.*

### 1 — L'assiette de l'écrêtement
**→ GARDER l'assiette au contrat.** Mesuré sur donnée réelle versionnée
(14 243 sinistres) : l'écart de prime pure vaut **−1,07 % au pire**, et sur
toute la grille (fréquence 0,15→8, dispersion 0→2,5) **il ne dépasse jamais
2,4 % et change de signe**. Le coût d'un écrêtement au sinistre est un
**contrat de données nouveau**. → corriger la phrase (rang 7) et **publier les
12/55 contrats écrêtés parce que NOMBREUX plutôt que GRAVES** (rang 5).

### 2 — La charte · ✅ **CLOS le 27/08/2026** — *et ma recommandation ci-dessous a été RÉFUTÉE*

⚠️⚠️ **CE QUI A ÉTÉ FAIT NE SUIT PAS CE QUI EST RECOMMANDÉ PLUS BAS, ET C'EST
MOTIVÉ.** Trois lots : source unique `7edbf5c` · glyphe à trois états `6b61130`
· interdiction du texte rouge `516692d` · le `icone` local `94562e8` · et
`236dcf2` pour la décision qui lisait un emoji. **AUCUNE COULEUR N'A CHANGÉ.**

⚠️ **Les valeurs `#FFC145` / `#E8452F` recommandées ci-dessous sont ÉCARTÉES** —
elles avaient été mesurées sur la table d'une **SONDE D'AUDIT**, pas sur la
palette de PRODUCTION. Remesurée sur les vraies valeurs, la palette tient :
**6,80 / 6,51 / 3,74** sur le fond des figures, **4,72 / 5,44** sur le blanc des
rapports. *Le défaut n'était pas leur valeur — c'est qu'elles n'étaient tenues
par rien.* **30 définitions locales → 0.**

⚠️⚠️ **LE DÉFAUT RÉEL, MESURÉ** : VERT et AMBRE ont un contraste mutuel de
**1,04** — *la même luminance*. En niveaux de gris ils fusionnent. C'est la
démonstration qu'un **second canal** est nécessaire, et il existe désormais
(glyphe). ⚠️ `MOTIF_RAG` et `SYMBOLE_RAG` sont déclarés mais **employés nulle
part au plan** — mesuré le 28/08 : seul leur propre test les lit.

⚠️ **CE QUE LA CHARTE N'A PAS FERMÉ, ET C'EST VÉRIFIÉ AU SITE EXACT** :
`charts/C9` reste **OUVERT** — le gradient rend toujours **4 inversions** et un
écart minimal de **0,0035**, identique au relevé, à la quatrième décimale.
`charts/C10` reste **OUVERT** aussi : `chart_walkforward_ae` fait toujours
`return COULEURS['or_accent']` pour le point AMBRE. *J'avais conclu C10 fermé en
regardant `STATUT_RAG` au lieu du SITE que le constat nomme — corrigé.*

---

**Recommandation d'origine, conservée pour mémoire (RÉFUTÉE ci-dessus) :**
**→ LA V3 COMME BASE, avec TROIS corrections de rôles.** La V3 gagne les **8
contrastes WCAG** et sépare visiblement le papier du graphique (l'app est
plate). Mais elle porte deux défauts, mesurés hier :

| rôle | avant | après | mesure |
|---|---|---|---|
| gradient | 4 inversions, écart min **0,0035** | bleu → violet → rouge → ambre clair | **0 inversion**, min **0,0086**, et le pire décile se lit **chaud ET clair** |
| `rag_ambre` | `#D4AF37` = **l'or des axes** | **`#FFC145`** | contraste **6,79 → 8,82** ; sort de l'or (1,00 → 1,30) |
| `rag_rouge` | `#F05523` | **`#E8452F`** | se sépare de l'ambre |

⚠️ **Ma recommandation d'avant-hier était fausse** — je la fondais sur **59
copies contre 7 usages**. *Le compte de 59 dit qui a copié quoi ; il ne dit rien
de ce qui se lit.*
⚠️ **Quatrième recommandation, indépendante de la palette** : un RAG encodé par
**la seule couleur** est un risque connu. Le remède est un **second canal** —
rond / triangle / carré selon le statut.
⚠️ **Je retire ma mesure du daltonisme** : deux implémentations, deux résultats.

### 3 — `actuaria_app.py` entre-t-il dans le périmètre ?
**→ OUI, mais scopé à ~980 lignes** (l'assemblage), pas 5 181. Au taux mesuré,
le fichier entier annoncerait **~78 constats**, majoritairement de mise en page,
pour **6 à 8 lots**. *C'est le seul endroit où je recommande de ne PAS lire
intégralement, et je le motive par une mesure.*

### 4 — Les 41 non alloués : traiter ou déclarer bruit ?
**→ TRIER d'abord** (1 passe, sans code), décider ensuite.

### 5 — Le garde `__main__` touche un fichier hors tarification
**→ LE FAIRE.** Il débloque la testabilité de tout le reste, et c'est le seul
prérequis dont dépendent les rangs 1 et hors-rang.

---

# ⑥ À QUI APPARTIENT QUOI

**🔵 Vous** : les 5 arbitrages ci-dessus. Rien d'autre.

**⚫ Moi** : mesurer avant d'affirmer · corriger · **épingler par un contrôle
positif nommé** · prouver · et **vous rendre les réfutations quand la mesure me
contredit**. *Elle l'a fait sept fois depuis le début de ce chantier ; c'est le
meilleur signal que la méthode tient.*

---

# ⑦ LE TOTAL

| rang | ouvertures | constats |
|---|---|---|
| **0** — les prérequis | **2 lots** | — |
| **1** — le prix vivant | **3 lots** | 10 |
| **2** — le verdict | **3 lots** | 9 |
| **3** — la statistique + le latent | **3 lots** | 11 |
| **4** — les figures et la charte | **1 lot** | 11 |
| **5** — les livrables | **1 lot** | 6 |
| **6** — le câblage | **1 lot** | 4 |
| **7** — le bruit | **12 passages** | 38 |
| — les audits | **3 audits** | *4 à 15 attendus* |
| — le tri | **1 passe** | 40 |
| **TOTAL** | **14 lots · 12 passages · 3 audits · 1 tri = 30 ouvertures** | **129** |

*Vérifié : 51 alloués aux rangs 1-6 + 38 groupés + 40 à trier = **129**.*

⚠️ **Les quatre premiers rangs — ce qui publie un prix, un verdict, une
statistique et une figure faux — tiennent en 12 lots.** C'est là que la
solidité se gagne.

---

**Quand les cinq critères S1→S5 sont verts, le module est ultra solide. Pas
avant, et rien d'autre ne le dira.**
