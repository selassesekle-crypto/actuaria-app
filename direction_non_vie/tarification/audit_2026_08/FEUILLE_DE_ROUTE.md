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
| **S5** | **Tout ce qui tarife est atteignable par une gate** | ⛔ `actuaria_app.py` **non gatable par construction** ; **3 modules jamais audités** (1 170 l) |

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

## RANG 0 — LES PRÉREQUIS · **2 lots**

*Ni des constats, ni des correctifs : les conditions sans lesquelles on ne peut
ni fermer ni prouver.*

| lot | ferme | pourquoi en premier |
|---|---|---|
| **0.1 Le garde `__main__`** | *(condition)* | **aucun `if __name__`** : `set_page_config`, l'init du `session_state`, le style, **`render_sidebar()`** et le dispatch s'exécutent à l'import. **34 fonctions, 4 727 lignes, 0 test possible.** Sans lui, tout constat de l'app n'est épinglable que par un test qui **relit du texte** |
| **0.2 Rétablir le compte de la gate NV** | *(condition)* | **1 395 mesuré, ~1 440 attendu**, non revérifié depuis L0. *On n'ouvre pas quatorze lots sur un compte de référence inconnu* |

## RANG 1 — LE PRIX SORT FAUX, DEVANT UN ACTUAIRE, AUJOURD'HUI · **3 lots · 10 constats**

| lot | constats | ce que ça ferme |
|---|---|---|
| **1.1 Les branches de l'app + les fuites d'A5** | `app/prime_ml` `app/prime_dl` `a5/C6` `a5/C7` | `prime_dl` écrit un prix **Deep Learning** dans `resultats["principal"]` sans challenger ni arbitrage — et A5 porte **l'early stopping réglé sur le TEST** et **aucun seed**. *Un prix non reproductible, issu d'un modèle en fuite, sort aujourd'hui* |
| **1.2 Le plan ne laisse plus déclarer ce qu'il interdit** | `plan/C1` `plan/C2` `plan/C3` | la garde B9 contournée par les **interactions** → **prime non proportionnelle à l'exposition (1,8339 au lieu de 2,0000)** · la **cible** déclarable en facteur · un `type` mal orthographié **détruit un facteur en silence**, `ampute=False`. **Regroupement franc** : même geste — valider l'**appartenance**, pas la combinaison |
| **1.3 Les exclusions qui détruisent un facteur légitime** | `conformite/C2` `C3` `C5` | la variable de **TAILLE** écartée comme « la cible déguisée » · les **6 variables de B5** toujours détruites · **6 modalités légitimes** tuées par les mots métriques. *Un facteur détruit ampute le tarif — B5 l'a chiffré à −17,4 % de Gini* |

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
