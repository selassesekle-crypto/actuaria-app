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
| **S1** | **Rien de faux n'est publié** | ⛔ **129 constats ouverts** |
| **S2** | **Rien de fermé ne peut régresser** | 🟡 **18 fermés sur 19 sont épinglés** par un contrôle positif nommé — `a5/C5` ne l'est pas |
| **S3** | **Un tarif signé se rejoue à l'identique** | ⛔ **1 sur 4** : le tarif déclaratif est reproductible **au bit près** (0,00e+00) ; le tarif DL ne l'est pas (aucun seed) ; le livrable porte un horodatage ; l'empreinte du plan n'a pas de version de schéma |
| **S4** | **Un seul chemin — ou des chemins également gardés** | ⛔ **5 assemblages dans l'app**, un seul complet ; l'orchestrateur a **0 appelant** ; le chemin agent n'a **aucune couche qualité** |
| **S5** | **Tout ce qui tarife est atteignable par une gate** | 🟡 `actuaria_app.py` est **importable depuis le lot 0.1** (`07be8c0`) — **29 fonctions atteignables contre 0** ; restent **3 modules jamais audités** (1 170 l) |

⚠️⚠️ **ET UN CRITÈRE QUI N'EN EST PAS UN : LE NOMBRE DE TESTS.** Mesuré par
résolution d'import vers un chemin de fichier : **23 882 lignes, 1 940 tests,
12 lignes par test.** Le périmètre est **densément testé** — et il a livré
**143 constats**. *L'archive l'écrivait dès le premier jour : « testé n'a jamais
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
| constats relevés (vagues 1 + 2) | **146** (85 + 61) |
| fermés **et épinglés** | **18** |
| corrigé, **non épinglé** | **1** (`a5/C5`) |
| **⛔ OUVERTS** | **129** |
| lignes lues intégralement | **22 693** sur 23 863 du périmètre |
| jamais auditées | **1 170 l** + `actuaria_app.py` (5 181 l) |
| preuves qui se relancent | **35, 0 échec** |

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
| **0.2 Le compte de référence de la gate NV** | ✅ **CLOS** | **`Ran 1403 tests` — `OK (skipped=3)`**, 2 089 s. Voir ci-dessous |

### ⚠️ LOT 0.2 — CE QUE LE COMPTE DE RÉFÉRENCE A TRANCHÉ

```
  gate direction_non_vie   ->   Ran 1403 tests in 2088.882s
                                OK (skipped=3)
```

| | |
|---|---|
| **référence établie** | **1403** |
| mesuré à L0 | 1395 — **+8** |
| ce que j'annonçais attendre | ~1440 — **−37, mon attente était FAUSSE** |

⚠️ **L'incertitude « 1395 mesuré, ~1440 attendu » est close.** Le ~1440 était
une **estimation de ma part**, jamais mesurée. *C'est exactement le motif de cet
audit, appliqué à mon propre chiffre.*

⚠️ **3 tests sont SKIPPÉS, et la sortie ne les nomme pas.** Je ne les identifie
donc pas et je ne le devine pas. Mesuré en revanche : l'environnement porte
`openpyxl`, `plotly`, `kaleido`, `python-docx`, `torch`, `xgboost`, `lightgbm`,
`catboost`, `shap`, `optuna` — et **il lui manque `xlsxwriter`, `weasyprint` et
`streamlit`**. *Un test sauté est un contrôle qui ne surveille pas : à verser au
tri.*

## RANG 1 — LE PRIX SORT FAUX, DEVANT UN ACTUAIRE, AUJOURD'HUI · **3 lots · 10 constats**

| lot | constats | ce que ça ferme |
|---|---|---|
| **1.1 Les branches de l'app + les fuites d'A5** | ✅ `a5/C6` `a5/C7` **FERMÉS** · ✅ `app/prime_ml` `app/prime_dl` **ARBITRÉS — REPORTÉS À LA MIGRATION** | A5 : trois jeux **68/12/20**, jeu de validation **exigé** (`raise`, aucun repli) ; `seed` déclaré et **inscrit au rapport**. **⚠️ L'optimisme mesuré : TabNet −13,2 %** (0,2269 → 0,1970) ; l'irreproductibilité valait **11 % d'étendue** sur le Gini **qui sert à A6 pour arbitrer**. POS-A5d + POS-A5e (6 contrôles, 2 violations plantées). **⚠️⚠️ LES BRANCHES DE L'APP NE SERONT PAS CORRIGÉES : arbitrage de Selasse du 25/08 — l'app Streamlit disparaît, on n'y touche pas, même pour une phrase.** L'exigence est écrite pour la suivante : [`EXIGENCES_MIGRATION.md`](EXIGENCES_MIGRATION.md) — **deux modes, et l'absence de comparaison jamais silencieuse** |
| **1.2 Le plan ne laisse plus déclarer ce qu'il interdit** | ✅ **FERMÉS** `plan/C1` `plan/C2` `plan/C3` — **et `plan/C9` en prime** | la garde B9 contournée par les **interactions** → **prime non proportionnelle à l'exposition (1,8339 au lieu de 2,0000)** · la **cible** déclarable en facteur · un `type` mal orthographié **détruit un facteur en silence**, `ampute=False`. **Regroupement franc** : même geste — valider l'**appartenance**, pas la combinaison. ✅ **Fermé au lot 1.2** : contrôle sur **trois surfaces** (nom source · opérandes d'interaction · colonnes produites), valeurs admises **dérivées des `Literal`** et jamais recopiées, et un **filet** — *un facteur qui ne produit aucune colonne est refusé*. ⚠️⚠️ **LA RACINE ÉTAIT DANS LA SPEC, PAS DANS LE CODE** : `plan_execution_6_actions.md` l.294 demandait le contrôle **sur `colonnes_produites()`** — le code le faisait exactement. **11 contrôles positifs**, 20/20 plans intacts |
| **1.3 Les exclusions qui détruisent un facteur légitime** | ✅ **FERMÉS** `conformite/C2` `C3` `C5` — **et `C6` en prime** | la variable de **TAILLE** écartée comme « la cible déguisée » · les **6 variables de B5** toujours détruites · **6 modalités légitimes** tuées par les mots métriques. *Un facteur détruit ampute le tarif — B5 l'a chiffré à −17,4 % de Gini*. ✅ **Fermé au lot 1.3** : le test des mots métriques passe de la **sous-chaîne au MOT ENTIER** (`imprimerie` ⊅ `prime`) → **3 modalités récupérées**, et **B6 reste bloqué** (le second sens, vérifié). ⚠️⚠️ **RECADRAGE MESURÉ : sur le chemin déclaratif — celui des 6 appelants de production — RIEN n'est détruit** (`exclusions = {}`) ; C3 et C5 ne vivent que sur le chemin rétrocompat. Le reste est corrigé **par le motif** (leçon B7) : plus de « aucune action » quand une action existe, et plus d'instruction impossible à suivre. **9 contrôles positifs** |

## RANG 2 — CE QUI AUTORISE CE PRIX · **3 lots · 9 constats**

| lot | constats | ce que ça ferme |
|---|---|---|
| **2.1 Les garde-fous qui attestent sans surveiller** | `conformite/C1` `qualite/C2` `agents/C2` | `controle_effet_execute` atteste **la fourniture des arguments** · l'escalade compte **par type** (19,6 % exclus sans blocage) · `.success = True` **alors qu'A6 a échoué**. *Un contrôle qui atteste sans surveiller est pire qu'un contrôle absent : il ferme la question* |
| **2.2 La couche qualité ne voit pas l'absence** | `qualite/C1` `a1/C3` `a1/C4` | **100 % de NaN → 0 anomalie** · `prime_pure > 0` · le double verdict sur `exposition = 0` |
| **2.3 La conformité affirmée sans condition** | `a6/C5` `conformite/C14` `conformite/C7` | conformité **affirmée sans condition** dans la fiche de décision · « **POUR TOUTE BRANCHE** » alors que seule la Non-Vie est surveillée · `controle_effet_execute` **n'atteint aucun livrable**. *C'est ce qui part au CAC et à l'ACPR* |

## RANG 3 — LA STATISTIQUE, ET LES API LATENTES · **3 lots · 11 constats**

| lot | constats |
|---|---|
| **3.1 Les statistiques fausses d'A3** | `a3/C4` IC 95 % faux · `a3/C6` Gini Tweedie nul · `a3/C7` deux Gini incomparables comparés · `a3/C14` p-value fabriquée |
| **3.2 Les scores et les rangs d'A4/A6** | `a4/C6` `a4/C9` `a4/C10` `a6/C6` `a6/C7` `a6/C8` |
| **3.3 L'API latente** | `pipeline/C1` (**`tarifer()`**, +128 % sur un facteur illisible) — **descendu du rang 1** : 1 appelant, une **démo**. *Une API publique sans borne est une régression qui attend un appelant* |

## RANG 4 — LES FIGURES ET LA CHARTE · **1 lot · 11 constats** · le meilleur ratio

`a3/C5` `a4/C5` `a5/C4` `a6/C3` `charts/C1` `C2` `C3` **`C4`** `C5` **`C9`** **`C10`**

Lorenz tracée non mesurée (×2) · « Convergence » analytique · « Score par
profil » sans score · badge sans borne (**125 %**, **−5 %**, **18 000 000 %**) ·
**bande verte plus large que le gate** · **7/7 figures vides indiscernables** ·
**4 troncatures silencieuses** · ⚠️ **`C9` le gradient n'est pas monotone en
luminance** (4 inversions, **0,0035** entre deux déciles voisins : *deux déciles
différents se lisent pareil*) · ⚠️ **`C10` l'ambre du RAG EST l'or des axes**
(`#D4AF37`, teinte **0°**, contraste **1,00** — la même couleur).

🔵 **Précédé de l'arbitrage 2 — la charte** (§⑤).

## RANG 5 — LES LIVRABLES · **1 lot · 6 constats**

`services/C1` « Arrêté : » publie l'horodatage · `C2` référence Wüthrich ·
`C3` « 8 modèles » ×3 · `C4` `h5_deviance` absente · `C5` 3 valeurs hors règle ·
`agents/C4` `resume()` génère une date.

## RANG 6 — LE CÂBLAGE · **1 lot · 4 constats**

`agents/C1` `qualite/C4` `socle/C2` `conformite/C10` + le chantier ④.
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

## HORS RANG — LE TRI · **1 passe · 40 constats**

Vague 1, classes B et C, **non alloués**. **Je ne les ai pas triés et je le
dis** plutôt que de les ranger au jugé.

---

# ④ LA RÈGLE DE FERMETURE — elle vaut pour chaque lot

> **Un constat n'est FERMÉ que si un CONTRÔLE POSITIF NOMMÉ l'épingle.**
> Un code corrigé sans contrôle peut régresser sans un mot : c'est un
> **troisième état**, et il se distingue. *Il y en a déjà un dans l'archive.*

Et par lot, le livrable est invariable : **① propreté · ② diff indexé vérifié ·
③ preuve · ④ gate lue au fichier — puis STOP.**

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

### 2 — La charte
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
