# FEUILLE DE ROUTE — CE QUI RESTE, DANS L'ORDRE

**Reconstruite depuis zéro le 24/08/2026 (soir).** Elle **remplace l'ordre** de
[CARTE.md](CARTE.md), qui reste l'**inventaire** (les 125 constats, leurs
mesures, les preuves). *Deux documents qui ordonnent la même chose, c'est
exactement le défaut que cet audit poursuit : il n'y en a qu'un, et c'est
celui-ci.*

## CE QUI A CHANGÉ DEPUIS LA CARTE — mes révisions, nommées

| # | ce que j'avais dit | ce que je dis maintenant | ce qui m'a fait changer |
|---|---|---|---|
| **R1** | « l'architecture au **rang 6** » | **dédoublée** : les **branches de l'app → rang 1**, le **câblage de l'orchestrateur → reste rang 6** | j'avais mesuré les appelants de `pipeline_agents.py` (**0**) **sans mesurer les branches de l'app**. Elle assemble la chaîne de **5 façons**, une seule complète |
| **R2** | `tarifer()` = mon constat le plus direct, **rang 1** | **rang 3** | `tarifer()` a **un** appelant, et c'est une **démo**. L'app ne l'appelle jamais. Le **+128 %** est **latent** |
| **R3** | l'écrêtement = **classe A**, « je ne tranche pas » | **hors rang**, recommandation **garder l'assiette** | mon −9,1 % était l'écart **sur les contrats écrêtés**, pas la moyenne, et sur une sévérité **constante**. Réel : **−1,07 %**, jamais plus de **2,4 %**, et **le signe change** |
| **R4** | « les 4 agents portent **leur propre** charte » | **il n'y a pas deux chartes** : **1 palette copiée 59 fois** + **1 charte déclarée à 7 usages** | les agents portent **intégralement** la palette de l'app (11/11, 12/12, 10/10, 12/12, **0 inconnue**), et **personne ne l'importe** — l'app s'exécute à l'import |
| **R5** | « **67** ouverts en vague 1 » | **66** | le tableau « Les 17 fermés » en portait **18**, toutes distinctes |
| **R6** | *(absent)* | **UN RANG 0 : LES PRÉREQUIS** | le garde `__main__` n'est **pas un constat** — c'est la **condition** sans laquelle aucun constat de l'app ne peut être épinglé |
| **R7** | *(absent)* | `conformite/C14` inscrit | arbitrage de Selasse : la Vie est hors périmètre, **le constat qui en sort ne l'est pas** |
| **R8** | « **243** seuils RAG réénoncés dans l'app » | **retiré** — ~78 usages de **variables de couleur**, 80 chaînes, **35** vraies décisions RAG | mon `grep` comptait les **noms de constantes** |

---

## L'AXE

**Ce qui publie un faux, et à qui — pondéré par ce qui TOURNE.** C'est la
différence avec la carte : un constat de classe A sur une fonction que personne
n'appelle passe **après** un constat de classe B sur le chemin de l'écran.

---

# RANG 0 — LES PRÉREQUIS · **2 lots**

*Ce ne sont pas des constats. Ce sont les conditions sans lesquelles on ne peut
ni fermer ni prouver.*

### 0.1 — Le garde `__main__` sur `actuaria_app.py` · **1 lot, quelques lignes**
**Pourquoi en premier** : **aucun `if __name__ == "__main__"`**. `set_page_config`,
l'init du `session_state`, le style, **`render_sidebar()`** et le dispatch
s'exécutent au niveau module. **Importer l'app l'exécute** → aucune gate ne la
découvre → **34 fonctions, 4 727 lignes, 0 test possible**.
**Sans lui, tout constat de l'app sera épinglé par un test qui relit du texte.**
⚠️ Contrainte : `set_page_config` doit rester le premier appel Streamlit — il
descend **en tête du `main()`**.
🔵 **Décision de portée pour Selasse** : touche un fichier de production hors
tarification.

### 0.2 — Rétablir le compte de la gate NV · **1 lot, une exécution**
**Pourquoi** : **1 395 mesuré, ~1 440 attendu**, et **non revérifié depuis L0**.
*On n'ouvre pas quatorze lots sur un compte de référence qu'on ne connaît pas.*

---

# RANG 1 — CE QUI PUBLIE UN PRIX FAUX, AUJOURD'HUI, DEVANT UN ACTUAIRE · **3 lots**

### 1.1 — Les branches de l'app + les fuites d'A5 · **1 lot** · 3 constats
`app/branches` · `a5/C6` · `a5/C7`
**Pourquoi rang 1** : `prime_dl` écrit un prix **Deep Learning** dans
`resultats["principal"]` — sans challenger, sans arbitrage — et A5 porte
**l'early stopping réglé sur le jeu de TEST** et **aucun seed**. *Un prix non
reproductible, issu d'un modèle en fuite, sort aujourd'hui.* `prime_ml` fait de
même avec A4 seul.

### 1.2 — Le plan ne laisse plus déclarer ce qu'il interdit · **1 lot** · 3 constats
`plan/C1` `plan/C2` `plan/C3`
**Pourquoi rang 1** : la garde B9 contournée par les **interactions** →
**prime non proportionnelle à l'exposition (1,8339 au lieu de 2,0000)**. Et un
`type` mal orthographié **détruit un facteur en silence** avec `ampute=False`.
**Regroupement franc** : les trois sont dans les deux `__post_init__`, même
geste — valider l'**appartenance**, pas la combinaison.

### 1.3 — Les exclusions qui détruisent un facteur légitime · **1 lot** · 3 constats
`conformite/C2` `conformite/C3` `conformite/C5`
**Pourquoi rang 1** : un facteur détruit ampute le tarif aussi sûrement qu'un
facteur faux l'égare — B5 l'a chiffré à **−17,4 % de Gini**.

---

# RANG 2 — CE QUI AUTORISE CE PRIX · **3 lots**

### 2.1 — Les garde-fous qui attestent sans surveiller · **1 lot** · 3 constats
`conformite/C1` `qualite/C2` `agents/C2`
**Pourquoi rang 2** : ils ne produisent pas le faux, ils le **laissent passer**
en disant l'avoir vérifié. *Un contrôle qui atteste sans surveiller est pire
qu'un contrôle absent : il ferme la question.*

### 2.2 — La couche qualité ne voit pas l'absence · **1 lot** · 3 constats
`qualite/C1` `a1/C3` `a1/C4`
**Pourquoi ici et pas rang 1** : le GLM s'arrête **loud** en aval. Le dégât est
un **message illisible**, pas un prix faux.

### 2.3 — La conformité affirmée sans condition · **1 lot** · 3 constats
`a6/C5` `conformite/C14` `conformite/C7`
**Pourquoi rang 2** : c'est ce qui part au CAC et à l'ACPR. Une portée
sur-annoncée y est une dette d'opposabilité.

---

# RANG 3 — LA STATISTIQUE, ET LES API LATENTES · **3 lots**

### 3.1 — Les statistiques publiées fausses d'A3 · **1 lot** · 4 constats
`a3/C4` `a3/C6` `a3/C7` `a3/C14` — IC 95 % faux · Gini Tweedie nul · deux Gini
incomparables comparés · p-value fabriquée.

### 3.2 — Les scores et les rangs d'A4/A6 · **1 lot** · 6 constats
`a4/C6` `a4/C9` `a4/C10` `a6/C6` `a6/C7` `a6/C8`

### 3.3 — Les API latentes · **1 lot** · 2 constats
`pipeline/C1` (**`tarifer()`**, +128 %) · `charts/…` *(la borne du badge y est
déjà au rang 4)* — **descendu depuis le rang 1** : 1 appelant, une démo.
**Pourquoi les traiter quand même** : une API publique sans borne est une
régression qui attend un appelant.

---

# RANG 4 — LES FIGURES · **1 lot** · 8 constats · **le meilleur ratio**

`a3/C5` `a4/C5` `a5/C4` `a6/C3` `charts/C1` `charts/C2` `charts/C3` `charts/C5`
Lorenz tracée non mesurée (×2) · « Convergence » analytique · « Score par
profil » sans score · badge sans borne (**125 %**, **−5 %**, **18 000 000 %**) ·
**bande verte plus large que le gate** · **7/7 figures vides indiscernables** ·
**4 troncatures silencieuses**.
🔵 **Précédé d'un arbitrage de Selasse : la charte** (voir plus bas).

---

# RANG 5 — LES LIVRABLES · **1 lot** · 6 constats

`services/C1→C5` `agents/C4` — « Arrêté : » publie l'horodatage · référence
Wüthrich · « 8 modèles » ×3 · `h5_deviance` absente · 3 valeurs hors règle ·
`resume()` génère une date.

---

# RANG 6 — LE CÂBLAGE · **1 lot** · 4 constats

`agents/C1` `qualite/C4` `socle/C2` `conformite/C10` + le chantier ④.
**Pourquoi toujours dernier des rangs** : c'est le **remède**, pas le défaut.
Câbler l'orchestrateur avant les rangs 1-4 propagerait leurs défauts sur
**trois** arbitrages au lieu d'un. ⚠️ *Distinct de 1.1 : fermer les branches de
l'app n'est pas câbler l'orchestrateur.*

---

# RANG 7 — LE BRUIT GROUPÉ · **12 passages** · 38 constats

9 passages de la vague 1 (recouvrements retirés) + 3 de la vague 2 :
docstrings que le code contredit (6) · messages qui accusent le mauvais
coupable (3) · annotations et exports morts (3).

---

# HORS RANG — LES AUDITS À FAIRE · **3 ouvertures**

*Ce ne sont pas des lots de correction : on ne sait pas encore ce qu'il y a.*

| quoi | l. | pourquoi |
|---|---|---|
| **`core/elasticite.py`** | **989** | **vivant** (A4 → `resultats["principal"]`), **jamais audité**, et **c'est mon code**. 4 à 15 constats attendus. ⚠️ **Le mesurer, pas le lire** — planter les violations d'abord |
| **l'assemblage de l'app** | ~980 | `_executer_analyse` (799 l) + le bloc tarification (846 l). **Le reste de l'app : hors périmètre** |
| `services/excel_helpers.py` | 139 | complète le périmètre atteint depuis les deux pipelines |

# HORS RANG — LE TRI · **1 passe** · 41 constats

Vague 1, classes B et C, **non alloués**. Une passe de lecture qui les verse
dans les passages du rang 7 ou en extrait ceux qui méritent mieux. **Je ne les
ai pas triés et je le dis** plutôt que de les ranger au jugé.

---

# À QUI APPARTIENT QUOI

## 🔵 À SELASSE — 5 arbitrages, aucun n'est un lot

| # | décision | ma recommandation |
|---|---|---|
| 1 | **l'assiette de l'écrêtement** | **garder l'assiette au contrat** — gain ≤ 2,4 %, coût = contrat de données nouveau |
| 2 | **la charte source** | **la palette de l'application, déplacée dans `core/`** — voir ci-dessous |
| 3 | `actuaria_app.py` dans le périmètre ? | **oui, scopé à ~980 l** — pas les 5 181 |
| 4 | les **41 non alloués** : traiter ou déclarer bruit ? | **trier d'abord**, décider ensuite |
| 5 | le **garde `__main__`** touche un fichier hors tarification | **le faire** — il débloque tout le reste |

## ⚫ À MOI — tout le reste

Mesurer avant d'affirmer · corriger · **épingler par un contrôle positif nommé**
(un correctif non épinglé n'est pas fermé) · prouver · et **rendre les
réfutations** quand la mesure me contredit.

---

# 🔵 ARBITRAGE 2 — LA CHARTE : MA RECOMMANDATION MOTIVÉE

## D'abord, le constat est mal posé — y compris par moi

**Il n'y a pas « deux systèmes qui coexistent ».** Mesuré :

```
  59 fichiers de PRODUCTION portent les valeurs de l'app EN DUR
   0 fichier les IMPORTE       -- personne ne le peut : l'app s'execute a l'import
   7 fonctions utilisent la charte V3 -- ce sont celles de charts_tarif lui-meme
   2 fichiers n'utilisent NI L'UNE NI L'AUTRE (core/pdf_generator : 18 couleurs)

  palette app ∩ charte V3  =  {#F0F4F8}     -- UNE couleur sur douze
```

> **Il y a UNE PALETTE COPIÉE 59 FOIS, et UNE CHARTE DÉCLARÉE À 7 USAGES.**
> Et au moins un **troisième** système par-dessus.

## Les deux options pures, et pourquoi je rejette les deux

**Imposer la charte V3** — c'est le choix « architectural » : elle est dans
`core/`, **gatable**, **testée** (`test_charts_tarif.py`), et elle porte une
**validation nommée** (« *validé par Selasse, V3* », l.6).
❌ **Je la rejette** : il faudrait migrer **59 fichiers pour en aligner 7**.
Rapport de 1 à 8. Et surtout — **la V3 n'a AUCUNE couleur de statut RAG.**
`VERT`/`AMBRE`/`ROUGE` sont du **sens métier**, pas de la décoration : imposer
une charte qui ne les porte pas obligerait chaque appelant à les réintroduire,
c'est-à-dire à recréer la duplication qu'on voulait fermer.

**Imposer la palette de l'application** — c'est le choix « de fait » : 59
contre 7.
❌ **Je la rejette telle quelle** : elle vit dans `actuaria_app.py`, **à la
racine, non gatable, exécuté à l'import**. Personne ne peut l'importer — c'est
*pour cela* qu'elle est copiée 59 fois. **En faire la référence là où elle est,
c'est bénir la duplication.**

## ⚠️⚠️ MA RECOMMANDATION

> **Les VALEURS de l'application. La PLACE de la charte V3. Les RÔLES de la
> charte V3.**
>
> Extraire une charte unique dans **`core/`** (p. ex. `core/charte.py`), qui
> porte **les 12 couleurs de l'application** — **inchangées** — **nommées par
> les rôles de la V3** (`papier`, `graphique`, `texte`, `texte_2`, `or_titre`,
> `or_accent`, `hover_*`, `ligne_predite`) **plus les trois du RAG**. Puis
> `charts_tarif` la **consomme** au lieu de la déclarer.

**Quatre raisons, toutes mesurées :**

**① Les valeurs doivent être celles de l'app — 59 contre 7.** Changer les
valeurs, c'est changer l'apparence de **toute la plateforme** (provisionnement,
réglementation, Vie, Santé — mesuré : 54 fichiers hors tarification). Changer
la place n'en change **aucune**.

**② La V3 apporte ce que la palette n'a pas : des RÔLES.** `NAVY`, `OR`, `BLEU`
nomment une **teinte** ; `papier`, `graphique`, `texte_2`, `ligne_predite`
nomment un **usage**. *Une charte se tient par ses rôles, pas par ses teintes* —
c'est ce qui permet d'en changer les valeurs sans toucher un seul appelant.
**On garde les noms de la V3 et on y met les couleurs de l'app.**

**③ La palette de l'app porte le RAG, et le RAG n'est pas de la décoration.**
`VERT`/`AMBRE`/`ROUGE` sont le vocabulaire de décision du dépôt — 35 vraies
décisions RAG dans la seule app. Une charte de figures qui les ignore laisse
chaque appelant les redéfinir.

**④ `core/` est gatable, la racine ne l'est pas.** C'est la seule des deux
places où une règle peut épingler la duplication. ⚠️ *Et cela suppose le
rang 0.1 : tant que l'app s'exécute à l'import, elle ne peut ni importer
proprement ni être contrôlée.*

## Ce que ça coûte, et ce que je ne cache pas

- **Les 7 figures de `charts_tarif` changent d'apparence** — c'est le seul
  effet visible, et **c'est une décision d'identité visuelle qui vous
  appartient**, pas une décision technique.
- **Les 59 copies ne disparaissent pas d'un lot.** La charte unique les rend
  *retirables* ; les retirer est un passage groupé (rang 7), pas un préalable.
- ⚠️ **Le troisième système reste ouvert** : `core/pdf_generator.py` porte
  **18 couleurs** dont **aucune** des deux. Je ne l'ai pas mesuré au-delà du
  compte — **hors périmètre de cet audit**, et signalé.

## Si vous tranchez autrement

**Si vous gardez les deux systèmes**, alors le correctif minimal est **une
phrase** : `charts_tarif` ne s'annonce plus « SOURCE UNIQUE du style graphique
de la tarification » mais « style des figures de ce module ». *C'est
l'équivalent de ma recommandation sur l'écrêtement : quand le remède structurel
coûte plus que l'écart, on corrige la phrase.* ⚠️ **Mais ici l'écart n'est pas
de 1 % — c'est 59 copies d'une constante que personne ne peut importer.** Je ne
recommande pas cette option.

---

# LE TOTAL

| rang | ouvertures | constats |
|---|---|---|
| 0 — prérequis | **2 lots** | — |
| 1 — le prix vivant | **3 lots** | 9 |
| 2 — le verdict | **3 lots** | 9 |
| 3 — la statistique + le latent | **3 lots** | 12 |
| 4 — les figures | **1 lot** | 8 |
| 5 — les livrables | **1 lot** | 6 |
| 6 — le câblage | **1 lot** | 4 |
| 7 — le bruit | **12 passages** | 38 |
| — les audits | **3 audits** | *inconnu (4 à 15 attendus)* |
| — le tri | **1 passe** | 41 |
| **TOTAL** | **14 lots · 12 passages · 3 audits · 1 tri** | **127** |

⚠️ **127 et non 125** : `pipeline/C1` et les branches de l'app sont comptés dans
leur nouveau rang, et **2 constats de l'app** (`prime_ml`, `prime_dl`) sont
désormais nommés séparément de `agents/C1`.
