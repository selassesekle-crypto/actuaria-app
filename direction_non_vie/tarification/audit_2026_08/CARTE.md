# LA CARTE — L'INVENTAIRE DE CE QUI RESTE

> ## ⚠️⚠️ L'ORDRE VIT DANS [**FEUILLE_DE_ROUTE.md**](FEUILLE_DE_ROUTE.md)
> Reconstruite depuis zéro le 24/08 au soir, elle **remplace l'ordre de ce
> document** — avec un **rang 0 (les prérequis)**, les **8 révisions nommées**,
> la répartition **Selasse / moi**, et la **recommandation sur la charte**.
> **Ce document reste l'INVENTAIRE** : les constats, leurs mesures, les preuves.
> *Deux documents qui ordonnent la même chose seraient exactement le défaut
> que cet audit poursuit.*

**Établie le 24/08/2026**, sur demande de Selasse : *« Donne-moi l'ORDRE
COMPLET de ce qui reste, tous constats confondus — les 67 de la première vague
et les 58 de la seconde MÉLANGÉS. Un constat trouvé hier et un trouvé
aujourd'hui se valent s'ils publient le même faux. »*

## ⚠️ LE COMPTE, RECTIFIÉ

| | |
|---|---|
| constats relevés (vague 1 + vague 2) | **143** (85 + 58) |
| fermés, épinglés par un contrôle positif | **18** |
| corrigés, **non épinglés** | **1** (`a5/C5`) |
| **ouverts** | **124** (66 + 58) |
| **+ inscrit le 24/08** sur arbitrage | **1** (`conformite/C14`) |
| **⛔ OUVERTS AU TOTAL** | **125** |

⚠️ **Le tableau « Les 17 fermés » en portait 18**, toutes distinctes, mesurées.
La vague 1 compte donc **66 ouverts, pas 67**. *Le total que vous citiez —
125 — tombe juste, mais par un autre chemin : 66 + 58 + 1.*

---

# ⚠️⚠️ RÉVISION DU 24/08/2026 (SOIR) — J'AVAIS MESURÉ TROP ÉTROIT

**Selasse a demandé : « la roadmap complète et l'architecture d'abord — ou bien
il y a encore autre chose ? »** Il y avait autre chose, **et cela déplace deux
rangs de cette carte.**

## ① L'ARCHITECTURE N'EST PAS CELLE QUE J'AI MESURÉE

J'ai placé l'architecture au **rang 6** en mesurant les appelants de
`pipeline_agents.py` (**0**). **Je n'avais pas mesuré les branches de
l'application.** Mesuré maintenant, par AST :

```
  besoin == 'prime_glm'   l.3554  ->  A3 + pipeline_complet
                                      (COMPLET : qualite, conformite, 2 cibles)
  besoin == 'prime_ml'    l.3572  ->  A4 SEUL            -> resultats["principal"]
  besoin == 'prime_dl'    l.3578  ->  A5 SEUL            -> resultats["principal"]
  besoin == 'selection'   l.3593  ->  A3 + A6 avec result_a3 SEUL
  besoin == 'sinistres'   l.3421  ->  A1 + A2
```

⚠️⚠️ **L'APPLICATION ASSEMBLE LA CHAÎNE DE CINQ FAÇONS. UNE SEULE EST
COMPLÈTE.** Les quatre autres n'ont ni couche qualité, ni challenger, ni
arbitrage — et **deux d'entre elles écrivent leur résultat dans
`resultats["principal"]`**, c'est-à-dire dans ce que l'actuaire lit.

⚠️⚠️ **ET LA PIRE EST `prime_dl`.** Elle publie un prix **Deep Learning** comme
résultat principal, et A5 porte **deux constats de classe A OUVERTS** :

| | |
|---|---|
| `a5/C6` | **l'early stopping se règle sur le jeu de TEST** — une fuite |
| `a5/C7` | **aucun seed** — deux exécutions, deux modèles, deux prix |

**Ce n'est pas « une absence d'arbitrage ». C'est un prix faux, publié,
aujourd'hui.** Mon argument du rang 6 — *« un arbitrage manquant est moins grave
qu'un arbitrage faux »* — **ne s'applique pas ici** : il y a les deux.

## ② CE QUI CHANGE DANS L'ORDRE

| ce qui bouge | avant | après | pourquoi |
|---|---|---|---|
| **les branches de l'app** | rang 6 (« architecture ») | ⬆️ **RANG 1** | `prime_dl` et `prime_ml` publient un prix non arbitré, et A5 est en fuite |
| `a5/C6` `a5/C7` | rang 1, lot L1.4 | **rang 1, couplé aux branches** | même défaut vivant, même lot |
| `pipeline/C1` (`tarifer()`) | rang 1, lot L1.1 | ⬇️ **rang 3** | **`tarifer()` a 1 appelant, et c'est une démo.** L'app ne l'appelle **jamais**. Le +128 % est **latent**, pas vivant |
| câbler l'orchestrateur | rang 6 | **reste rang 6** | c'est le *remède*, pas le *défaut* |

⚠️ **Ce que je maintiens** : câbler `pipeline_agents` **avant** de fermer les
rangs 1-4 reste une erreur. Mais **fermer les branches de l'app** n'est pas
câbler l'orchestrateur — c'est **supprimer les assemblages qui publient sans
arbitrage**, ce qui peut se faire en amont et se fait plus vite.

## ③ CE QUI N'A TOUJOURS PAS ÉTÉ AUDITÉ — mesuré

Le périmètre atteint depuis les deux pipelines : **21 modules, 23 863 lignes.**
**18 audités (22 693 l) · 3 non audités (1 170 l)** — plus l'application.

| lignes | fichier | état |
|---|---|---|
| **5 181** | `actuaria_app.py` | ⛔ **jamais dans le périmètre**, et c'est lui qui assemble les cinq branches |
| **989** | `core/elasticite.py` | ⛔ **jamais audité, et VIVANT** — appelé par A4 (`etat_elasticite`, `sensibilite_tarifaire`), publié dans `resultats["principal"]` |
| 139 | `services/excel_helpers.py` | ⛔ |
| 42 | `core/__init__.py` | ⛔ |

⚠️⚠️ **`core/elasticite.py`, C'EST MON CODE — écrit il y a deux jours dans le
chantier ⑤, et jamais tenu au standard que j'ai appliqué à tout le reste.**
8 fonctions publiques, 16 constantes, **56 tests** — et l'archive écrit
elle-même : *« testé n'a jamais voulu dire audité »*. Au taux mesuré (1 constat
/ 225 l en vague 1, **1 / 66 l** en vague 2), **4 à 15 constats y sont
attendus**.

⚠️ **Et je suis mal placé pour l'auditer.** Le relire, c'est relire mes propres
intentions. **Recommandation de méthode : ne pas le lire — le mesurer.** Planter
les violations d'abord, lire ensuite seulement ce que la mesure a désigné.

⚠️ **Mesuré aussi** : sur ses 8 fonctions publiques, **6 n'ont aucun appelant de
production**. Seules `etat_elasticite` et `sensibilite_tarifaire` sortent, via
A4 — et **les trois livrables ne les lisent pas**. La sensibilité tarifaire
n'atteint donc **que l'écran de l'application**.

## ④ L'APPLICATION — MES RECOMMANDATIONS, MESURÉES

**Demandées le 24/08. `actuaria_app.py` : 5 181 l · 34 fonctions · 0 classe ·
91 % du volume dans des fonctions · 699 appels Streamlit · 35 valeurs de
`besoin` sur les TROIS directions, dont 5 seulement en tarification.**

### ⚠️⚠️ ① JE CONTESTE L'AUDIT DU FICHIER ENTIER

Au taux mesuré de la vague 2 (**1 constat / 66 lignes**), 5 181 lignes
annoncent **~78 constats** — *plus que toute la vague 2*. Et l'app est l'UI de
**toute la plateforme** : 20 de ses 35 branches ne sont ni Non-Vie ni
tarification. Sur 699 appels Streamlit (143 `markdown`, 89 `columns`), la
majorité de la récolte serait de la **mise en page**.

**Coût estimé : 6 à 8 lots. Rendement en constats qui publient un prix :
faible.** ⚠️ *C'est le seul endroit de cet audit où je recommande de ne PAS
lire intégralement — et je le motive par une mesure, pas par le volume.*

### ⚠️⚠️ ② LE FAIT QUI COMMANDE TOUT : L'APP N'EST PAS GATABLE PAR CONSTRUCTION

**Il n'y a aucun `if __name__ == "__main__"`.** Mesuré par AST, ce qui
s'exécute au niveau module :

```
  l.15     st.set_page_config(...)
  l.37     for k, v in {...}.items()      -- initialisation du session_state
  l.217    st.markdown("<style>...")
  l.5171   render_sidebar()               <-- ELLE REND
  l.5173   page = st.session_state.page
  l.5174   if page == 'accueil': ...      <-- le dispatch
```

**Importer `actuaria_app` exécute l'application.** Donc **aucune gate ne peut
la découvrir**, et **les 34 fonctions — 4 727 lignes, 91 % du fichier — ne sont
atteignables par aucun test.**

⚠️ **Le dépôt le sait déjà et l'a écrit** : `core/test_arrete.py:180` —
*« `actuaria_app.py` VIT A LA RACINE ET AUCUNE GATE NE LE DECOUVRE »*, et son
test **relit le fichier au lieu de l'importer**.

> **MA RECOMMANDATION LA PLUS FORTE N'EST PAS UN AUDIT, C'EST UN GARDE.**
> Mettre ces **cinq instructions** sous `if __name__ == "__main__":` rend les 34
> fonctions importables et testables. Les 20 `Assign` de données (palette,
> `AGENTS`, `STRUCTURE`, prompts) restent au niveau module — elles sont pures.
>
> ⚠️ **Contrainte connue** : `st.set_page_config` doit rester le **premier**
> appel Streamlit exécuté — il descend donc dans le `main()`, en tête, pas
> avant lui.
>
> **Un lot, quelques lignes, et il débloque tout le reste** : sans lui, tout
> constat trouvé dans l'app sera épinglé par un test qui **relit du texte**,
> jamais par un test qui **exécute**.

### ③ AUDITER L'ASSEMBLAGE, PAS LE FICHIER — périmètre mesuré

| | |
|---|---|
| `_executer_analyse` (l.3398) | **799 l** — c'est là que les 5 branches s'assemblent |
| le bloc de tarification | l.3529 → 4375, **846 l** |
| **total** | **~980 lignes · 1 lot** |

C'est là que vivent les constats **déjà mesurés** (`prime_ml` → A4 seul,
`prime_dl` → A5 seul), et ~134 lignes y publient un nombre formaté.

**Le reste de l'app — navigation, mise en page, les 20 branches des autres
directions — HORS PÉRIMÈTRE, déclaré comme tel.**

### ④ CE QUE JE NE RECOMMANDE PAS

- **Les 11 handlers `except: pass`** : mesurés un par un, ils gardent des
  boutons de téléchargement et des rendus de graphique. **Bénins.** Un seul
  mérite un œil : `l.4161` (« *A13 non bloquant* » — un résultat d'agent avalé).
- **Découper le fichier** : 4 fonctions font 71 % du volume
  (`page_analyse` 1052 l, `page_resultats` 919, `page_dashboard` 898,
  `_executer_analyse` 799). Le découpage ne ferme **aucun** constat. *Après le
  garde, pas avant.*

### ⑤ DEUX DE MES MESURES ÉTAIENT FAUSSES

| ce que j'avais dit | ce que la mesure dit |
|---|---|
| « 243 seuils RAG réénoncés dans l'app » | **faux** — ~78 usages de **variables de couleur**, 80 chaînes littérales, et **35 vraies décisions RAG** |
| « les 4 agents portent leur propre charte » | **faux** — ils portent **celle de l'application**, intégralement (11/11, 12/12, 10/10, 12/12, **0 couleur inconnue**). Voir [`releve_charts_tarif.md`](releve_charts_tarif.md) |

### ⑥ L'ORDRE QUE JE RECOMMANDE POUR L'APP

1. **Le garde `__main__`** — quelques lignes, et il rend testable tout le reste.
2. **Les branches `prime_ml` / `prime_dl`** — déjà au rang 1 révisé.
3. **L'audit de l'assemblage** (~980 l, 1 lot).
4. **Le reste : hors périmètre**, et écrit comme tel dans l'archive.

## ⑤ UNE ERREUR DE MESURE DE MA PART, CORRIGÉE

J'ai d'abord relevé que `capacites` et `exigences_hors_portee` de
`core/elasticite.py` étaient appelées par `normes/ifrs17/socle/lecture_inventaire.py`.
**C'est faux** : ce fichier importe de `normes.ifrs17.socle.contrat`. **Ce sont
des HOMONYMES.**

> ⚠️⚠️ **TROISIÈME FORME DE LA MÊME ERREUR CETTE SEMAINE.** Un relevé par
> symbole ne voit pas ce qui est écrit en français ; il ne voit pas ce qui est
> importé **sous alias** ; et **il confond les HOMONYMES entre modules.**
> Un relevé par nom doit résoudre l'import, ou il ne prouve rien.

---

## L'AXE DE L'ORDRE

**Ce qui est publié faux, et à qui.** Pas la vague, pas le fichier, pas la date.

| rang | ce qui est faux | pourquoi c'est cet ordre |
|---|---|---|
| **1** | **le PRIX** qui sort | un euro faux est signé par un actuaire et payé par un assuré |
| **2** | le **VERDICT** qui autorise ce prix | un VERT faux fait passer un prix faux |
| **3** | la **STATISTIQUE** qui fonde le verdict | un Gini faux fait un verdict faux |
| **4** | la **FIGURE** qui l'illustre | on ne compte pas les barres d'un graphique |
| **5** | le **LIVRABLE** qui le transmet | le CAC lit le livrable, pas le code |
| **6** | l'**ARCHITECTURE** — ce qui n'est pas câblé | ne publie pas un faux : publie une **absence** |
| **7** | le **BRUIT** documentaire | ne publie rien de faux à un actuaire |

---

# ⚠️⚠️ L'ASSIETTE DE L'ÉCRÊTEMENT — MA RECOMMANDATION, MOTIVÉE

**`socle/C1` ne figure dans AUCUN rang de cette carte, et voici pourquoi.**
Selasse a demandé une recommandation motivée avant d'arbitrer. Trois questions,
trois réponses **mesurées**.

## ① La donnée au sinistre existe-t-elle ? — OUI, et ce n'est pas ce qui bloque

```
  plans declarant une colonne AU SINISTRE            :  0 / 20
  champs de PlanTarifaire designant une table seconde:  0 / 12
  dataframes consommes par pipeline_complet / A1     :  1

  data/PG_2017_CLAIMS_YEAR0.csv  --  VERSIONNE DANS LE DEPOT
      14 243 lignes · UNE LIGNE = UN SINISTRE · claim_amount = son montant propre
      12 529 clients · 12,0 % en portent 2 ou plus · jusqu'a 6
```

⚠️ **La donnée est là, et le mapper aussi** : `nv_triangle_mapping.py` (A7) mappe
**déjà** une table sinistres complète (`sinistre_id` + 3 mesures), et A1
reconnaît `id_claim` dans `SYNONYMES_COLONNES` (l.110) — **déclaré, utilisé
nulle part ailleurs**.

**Ce qui manque n'est pas la donnée, c'est la STRUCTURE** : aucun champ au plan
pour déclarer une table sinistres, une seule entrée de données, aucune jointure,
et `construire_cible_severite(cout_total, nb, expo)` reçoit **trois séries déjà
agrégées**. **Ce n'est pas un correctif : c'est un contrat de données nouveau.**

## ② Que coûte l'écart, mesuré ? — **≤ 2,4 %, dans TOUS les régimes**

Sur la donnée réelle versionnée, les deux écrêtements comparés :

```
  seuil AU CONTRAT  (q0,995 du cout total)  = 7 684,48 EUR
  seuil AU SINISTRE (q0,995 du montant)     = 6 712,42 EUR

  contrats ecretes au contrat            : 55
  dont SANS aucun sinistre grave         : 12   (0,10 % du portefeuille)

  severite moyenne, par nombre de sinistres du contrat :
     nb sin       n      AU CONTRAT   AU SINISTRE     ecart
          1   9 598          955,18        950,95    +0,44 %
          2   1 232          839,19        843,67    -0,53 %
          3     141          817,68        826,05    -1,01 %
          4      22          814,86        822,26    -0,90 %
```

Et l'écart en fonction des **deux** paramètres qui le gouvernent :

```
     freq |  cv=0,0  |  cv=0,5  |  cv=1,0  |  cv=2,5 (le reel)
     0,15 |  -1,75 % |  -1,13 % |  -1,30 % |  -0,65 %
     1,00 |  -0,04 % |  -0,07 % |  +0,04 % |  +0,70 %
     4,00 |  -0,04 % |  +0,10 % |  +0,34 % |  +2,00 %
     8,00 |  -0,03 % |  +0,13 % |  +0,40 % |  +2,40 %
```

⚠️⚠️ **MON PROPRE EXEMPLE M'A INDUIT EN ERREUR, ET JE LE RETIRE.** J'avais
annoncé **−9,1 %** sur une flotte. Ce chiffre est **juste mais mal cadré** :
c'est l'écart **sur les 12 contrats écrêtés**, pas la moyenne du segment. Et il
supposait une sévérité **strictement constante** — un régime où le quantile du
total n'est plus qu'un quantile du **nombre**. Dès que la sévérité est dispersée
(cv réel = **2,41**), le quantile du total est dominé par la **queue des
montants** et l'effet s'effondre. **L'écart moyen ne dépasse 2,4 % dans aucun
régime mesuré.**

⚠️ **Et le signe n'est même pas constant** : négatif à basse fréquence, positif
à haute fréquence et forte dispersion. **Aucun des deux régimes n'est
uniformément prudent.**

## ③ Est-ce que ça déplace un TARIF ? — oui, de ~1 %, et à charge constante

```
  prime pure, par nombre de sinistres :
     nb sin   au contrat   au sinistre     ecart
          1     1 004,67      1 002,42    +0,22 %
          2     1 727,86      1 738,80    -0,63 %
          3     2 502,51      2 529,62    -1,07 %
          4     3 308,94      3 340,53    -0,95 %
```

**La charge totale est conservée dans les deux régimes** (mesuré au relevé :
écart **1,16e-10**). Ce qui bouge est la **répartition**, de **1 % au plus**, sur
les **1,4 %** de contrats à 3 sinistres ou plus.

## ⚠️⚠️ MA RECOMMANDATION

> **GARDER l'assiette au contrat. Corriger la docstring. N'ouvrir AUCUN chantier
> de structure.**

**Motivée par les trois mesures :** le gain plafonne à **2,4 %** et vaut **1 %**
sur le portefeuille réel ; le coût est un **contrat de données nouveau** (plan,
ingestion, jointure, propagation) ; et **aucun des deux régimes n'est
uniformément prudent**, donc on ne remplacerait pas un biais par une garantie.

**Ce que je recommande de faire, et c'est peu :**
1. **Corriger la phrase** — « quantile des coûts au-delà duquel un *sinistre*
   est dit grave » → « *au-delà duquel le coût TOTAL d'un contrat est écrêté* ».
   *Une ligne.* → **verse au rang 7, passage « docstrings contredites ».**
2. **Publier ce que l'écrêtement a fait, pas seulement combien.** `CibleSeverite`
   porte `n_graves` ; elle ne dit pas combien de contrats sont écrêtés **parce
   qu'ils sont nombreux** plutôt que graves — mesuré : **12 sur 55, soit 22 %**.
   C'est un **signalement**, pas un mécanisme. → **verse au rang 5.**

⚠️ **La condition qui rouvrirait le sujet** : une LoB à **forfait** (assistance,
protection juridique, GLI — dispersion faible) **et** à fréquence élevée. Le
tableau ci-dessus dit que même là, l'écart reste sous **0,15 %**. *Je ne vois
pas de régime, dans ce dépôt, qui justifie la refonte.*

---

# RANG 1 — LE PRIX SORT FAUX

**9 constats · 4 lots**

### L1.1 — Les bornes de plausibilité du chemin déclaratif
**1 constat · 1 lot · aucun regroupement possible**

| | |
|---|---|
| ferme | `pipeline/C1` |
| ce que ça ferme | `tarifer()` accepte `bonus_malus='beaucoup'` → prime **+128 %**, `success=True`. `-999` et `1e12` acceptés tels quels. Le chemin déclaratif **ne passe pas par A1**, qui porte les bornes. |

⚠️ **Seul de son espèce, et le plus direct de la carte** : c'est la porte
d'entrée du prix, et rien ne la garde.

### L1.2 — Le plan ne laisse plus déclarer ce qu'il interdit
**3 constats · 1 lot · regroupement FRANC**

| | |
|---|---|
| ferme | `plan/C1` `plan/C2` `plan/C3` |
| ce que ça ferme | la garde B9 contournée par les **interactions** (prime non proportionnelle à l'exposition : **1,8339 au lieu de 2,0000**) · la **cible** déclarable comme facteur · un `type`/`encodage` mal orthographié qui **détruit le facteur en silence**, `ampute=False` |
| pourquoi ensemble | les trois sont dans les deux `__post_init__`, et c'est **le même geste** : valider l'**appartenance** des valeurs, pas seulement la cohérence des combinaisons |

### L1.3 — Les exclusions qui détruisent un facteur légitime
**3 constats · 1 lot · regroupement FRANC**

| | |
|---|---|
| ferme | `conformite/C2` `conformite/C3` `conformite/C5` |
| ce que ça ferme | la variable de **TAILLE** (`effectif`, `nb_salaries`) écartée comme « la cible déguisée » au-delà de ~6 sin/an, avec « aucune action » · les **6 variables de B5** toujours détruites, par le garde-fou n°1 cette fois · **6 modalités légitimes** tuées par les mots métriques (`garantie_perte_exploitation`, `secteur_activite_imprimerie`…) |
| pourquoi ensemble | même fichier, même mécanisme : **la liste blanche détruit du légitime** |

### L1.4 — Les fuites de modélisation d'A5
**2 constats · 1 lot · regroupement FRANC**

| | |
|---|---|
| ferme | ✅ `a5/C6` `a5/C7` — **FERMÉS au lot 1.1** |
| ce que ça ferme | l'**early stopping réglé sur le jeu de TEST** (une fuite) · **aucun seed** : deux exécutions, deux modèles, deux prix |
| pourquoi ensemble | même fichier, même passe |
| ce que la fermeture a mesuré | l'optimisme caché par la fuite : **TabNet −13,2 %** (Gini 0,2269 → 0,1970), CANN −0,7 % · l'irreproductibilité : **11 % d'étendue** sur TabNet. Détail et contrôles positifs dans [`releve_a5_deep_learning.md`](releve_a5_deep_learning.md) |

---

# RANG 2 — LE VERDICT QUI AUTORISE LE PRIX

**9 constats · 3 lots**

### L2.1 — Les garde-fous qui attestent sans surveiller
**3 constats · 1 lot · regroupement PAR MOTIF (3 fichiers)**

| | |
|---|---|
| ferme | `conformite/C1` `qualite/C2` `agents/C2` |
| ce que ça ferme | `controle_effet_execute` atteste **la fourniture des arguments**, pas l'exécution · l'escalade qualité compte **par type** (19,6 % du portefeuille exclu sans blocage) · `.success = True` alors qu'**A6 a échoué** |
| raccourcit ? | **moyennement** — le geste est identique (mesurer ce qu'on atteste), le code est dans trois fichiers. Un lot, trois correctifs. |

### L2.2 — La couche qualité voit ce qui est là, pas ce qui manque
**3 constats · 1 lot · regroupement par SUJET (2 fichiers)**

| | |
|---|---|
| ferme | `qualite/C1` `a1/C3` `a1/C4` |
| ce que ça ferme | **100 % de NaN → 0 anomalie**, synthèse `None` · `prime_pure > 0` · le **double verdict** sur `exposition = 0` |

### L2.3 — La conformité affirmée sans condition
**3 constats · 1 lot · regroupement FRANC**

| | |
|---|---|
| ferme | `a6/C5` `conformite/C14` `conformite/C7` |
| ce que ça ferme | une conformité réglementaire **affirmée sans condition** dans la fiche de décision · « **POUR TOUTE BRANCHE** » alors que seule la Non-Vie est surveillée · `controle_effet_execute` **n'atteint aucun livrable** (1 lecteur, une démo) |
| pourquoi ensemble | les trois disent une **portée** de surveillance que le code ne tient pas |

---

# RANG 3 — LA STATISTIQUE QUI FONDE LE VERDICT

**10 constats · 2 lots**

### L3.1 — Les statistiques publiées fausses d'A3
**4 constats · 1 lot · regroupement FRANC (même fichier)**

| | |
|---|---|
| ferme | `a3/C4` `a3/C6` `a3/C7` `a3/C14` |
| ce que ça ferme | **IC 95 % faux ou tronqué** dans les infobulles · **Gini Tweedie nul partout** · `meilleur_modele` compare **deux Gini incomparables** · une **p-value fabriquée** |

### L3.2 — Les scores et les rangs d'A4/A6
**6 constats · 1 lot · regroupement par voisinage (2 fichiers)**

| | |
|---|---|
| ferme | `a4/C6` `a4/C9` `a4/C10` `a6/C6` `a6/C7` `a6/C8` |
| ce que ça ferme | « 6/8 » · **ROUGE inatteignable** · **deux bases de rang** · chaîne muette · « 3 meilleurs modèles » non utilisés · plafond de vraisemblance |

---

# RANG 4 — LES FIGURES

**8 constats · 1 lot · LE MEILLEUR RATIO DE LA CARTE**

| | |
|---|---|
| ferme | `a3/C5` `a4/C5` `a5/C4` `a6/C3` `charts/C1` `charts/C2` `charts/C3` `charts/C5` |
| ce que ça ferme | la **Lorenz tracée et non mesurée** (deux agents, même formule `t**(1/(1+2g))`) · « Convergence » = une **exponentielle analytique bruitée** · « Score par profil » qui **n'affiche pas le score** · le badge « % du discriminable » **sans borne** (mesuré à **125 %**, **−5 %**, **18 000 000 %**) · la **bande verte plus large que le gate** (0,85–1,15 contre 0,90–1,10) · une **figure vide indiscernable** d'une figure pleine, **7 fonctions sur 7** · **4 troncatures silencieuses** (23→15, 4→2, 1 000→500, 30→15) |
| raccourcit ? | **OUI, franchement.** Huit constats, deux vagues mélangées, **un seul lot** — et c'est exactement ce que Selasse demandait : *un constat d'hier et un d'aujourd'hui se valent s'ils publient le même faux.* |

---

# RANG 5 — LES LIVRABLES

**6 constats · 1 lot · regroupement FRANC**

| | |
|---|---|
| ferme | `services/C1` `services/C2` `services/C3` `services/C4` `services/C5` `agents/C4` |
| ce que ça ferme | « **Arrêté :** » publie l'**horodatage de génération** · la référence **Wüthrich** de l'Excel A5 n'est pas celle du modèle · « **8 modèles** » republié dans **trois** livrables · `h5_deviance` plafonnante chez A6 et **absente du tableau** · trois valeurs du modèle retenu **échappent à la règle du module** · `resume()` **génère un horodatage** (deux exécutions identiques diffèrent) |
| pourquoi ensemble | tous : **le livrable dit autre chose que le calcul** |

---

# RANG 6 — L'ARCHITECTURE

**4 constats · 1 lot · ET C'EST ICI QUE JE LA PLACE**

| | |
|---|---|
| ferme | `agents/C1` `qualite/C4` `socle/C2` `conformite/C10` + le chantier **④ l'équilibre du chemin agent** (arbitré, non codé) |
| ce que ça ferme | l'orchestrateur a **0 appelant** et les trois défauts de son en-tête sont intacts · l'app enchaîne A2→A3→**A6 avec `result_a3` seul** (ni A4, ni A5, ni `col_cible`) · le chemin agent n'a **aucune couche qualité** · le moteur de mapping (419 l) a **0 appelant** (déclaré « couche 2 ») · `FACTEURS_TARIFAIRES_AUTORISES` gouverne encore le chemin sans plan |

## ⚠️⚠️ CE QUI SUIT EST RÉVISÉ — LIRE D'ABORD LA RÉVISION EN TÊTE

**L'argument ci-dessous reste valable pour le CÂBLAGE de l'orchestrateur.** Il
ne l'est **pas** pour les **branches de l'application**, que je n'avais pas
mesurées : `prime_dl` et `prime_ml` publient un prix non arbitré, et A5 porte
deux constats de classe A ouverts. **Elles remontent au rang 1.**

## POURQUOI LE CÂBLAGE DE L'ORCHESTRATEUR RESTE AU RANG 6

**Ma recommandation, et elle conteste le placement naturel.**

**① Les deux chemins sont DÉJÀ convergés sur ce qui compte.** Mesuré par AST :
les **6 appelants de production** de `construire_matrice_x` passent tous
`plan=`, `df=` et `col_cible=` ; `construire_cible_severite` est partagée par
A3, `pipeline_tarifaire` et `pipeline_agents` ; `_slug` produit **exactement**
ce qu'A2 crée. **La conformité, la sévérité et le contrat de colonnes sont
communs.** Ce qui diverge est l'**orchestration** (0 appelant), la **couche
qualité** (1 appelant) et le **câblage de l'app**.

**② Câbler d'abord multiplierait la surface du faux.** Si `pipeline_agents`
devient le chemin de l'application avant que les rangs 1 à 4 soient fermés, les
**trois cibles** héritent d'un coup des défauts de prix, de verdict et de
figure — sur **trois arbitrages au lieu d'un**.

**③ Et les rangs 1 à 4 ne dépendent pas de l'architecture.** Ils vivent dans
`plan_tarifaire`, `conformite_reglementaire`, `charts_tarif`, `a3`, `a5` — tous
**partagés par les deux chemins**. Les fermer profite aux deux, quel que soit le
câblage finalement retenu.

**④ Le contre-argument, et pourquoi je ne le retiens pas.** `agents/C1` est de
classe A et il attend cinq rangs. Mais **ce qu'il publie de faux est une
absence** : l'application tarife avec le GLM seul, sans arbitrage. *Un arbitrage
manquant est moins grave qu'un arbitrage faux* — le premier ne dit rien, le
second dit une chose fausse avec l'autorité d'un verdict.

⚠️ **La condition qui me ferait changer d'avis** : si l'application est mise
devant un actuaire qui signe **avant** que les rangs 1-4 soient fermés, alors
l'absence d'arbitrage devient elle-même un faux publié, et le rang 6 remonte au
rang 2.

---

# RANG 7 — LE BRUIT DOCUMENTAIRE, GROUPÉ

**~42 constats · 12 passages** (9 déjà identifiés, 3 nouveaux de la vague 2)

### Les 9 passages de la vague 1 — **26 constats nets**
Ils sont mesurés et listés dans [README.md](README.md) : en-têtes de test
périmés (6) · symboles jamais lus (6) · en-têtes annonçant l'absent (**3**, voir
ci-dessous) · `COLS_A_EXCLURE` (3) · scorecards « 3 ✅ » (2) · `filterwarnings`
global (2) · écriture disque à l'instanciation (2) · exemples d'usage périmés
(2). Le passage « **figures** » du README (3) **disparaît** : ses trois constats
remontent au **rang 4**.

⚠️ **CINQ RECOUVREMENTS MESURÉS, ET ILS REMONTENT** — un constat n'est alloué
qu'une fois, au rang le plus élevé :

| constat | passage du README | remonte au |
|---|---|---|
| `a3/C5` `a4/C5` `a6/C3` | « figures qui n'affichent pas ce qu'elles nomment » | **rang 4** (le lot figures) |
| `a4/C6` | « en-têtes de module annonçant l'absent » | **rang 3** (les scores) |
| `services/C3` | « en-têtes de module annonçant l'absent » | **rang 5** (les livrables) |

*Le passage « en-têtes de module » passe donc de 5 à 3 constats.*

### Les 3 passages nouveaux de la vague 2

| passage | constats | pourquoi ensemble |
|---|---|---|
| **Docstrings que le code contredit** | `socle/C4` `socle/C5` `charts/C6` `charts/C7` `qualite/C5` `plan/C8` | « Température 0 » retirée 130 l plus haut · un paramètre public supprimé dès la 1re ligne · « \|err\| » sans dire laquelle · « kaleido absent » (il est en 1.3.0) · `_evaluer_qualite` introuvable · l'empreinte sans version de schéma |
| **Messages qui accusent le mauvais coupable** | `conformite/C8` `conformite/C12` `agents/C6` | un `dict` Python interpolé dans le motif lu par l'actuaire · « déclarez dans `FACTEURS_TARIFAIRES_AUTORISES` » alors que le plan fait autorité · « contrat de données rompu » pour deux noms de colonnes codés en dur |
| **Annotations et exports morts** | `agents/C5` `socle/C3` `plan/C11` | `_vue_sinistres` annonce un dict et rend un tuple · `DERIVATIONS` et `CibleSeverite` exportés sans consommateur · `colonnes_obligatoires` sans appelant externe |

---

# ⚠️ CE QUI N'EST PAS ENCORE ALLOUÉ

| | |
|---|---|
| ouverts | **125** |
| alloués nommément aux rangs 1→6 | **46** en **12 lots** |
| alloués aux passages groupés (rang 7), **recouvrements retirés** | **38** en **12 passages** |
| **NON ALLOUÉS** | **41** |

*Vérifié : 46 + 38 + 41 = 125.*

⚠️ **Les 41 non alloués sont tous en vague 1, classes B et C**, et je ne les ai
**pas** répartis un par un : leur tri demande de relire les sept relevés de la
première vague ligne à ligne, ce que je n'ai pas fait dans cette passe. **Je le
dis plutôt que de les ranger au jugé.**

**Le geste suivant pour eux n'est pas un lot, c'est un TRI** — une passe de
lecture qui les verse dans les passages du rang 7 ou en extrait ceux qui
méritent un rang supérieur. *Coût estimé : une passe, sans code.*

---

# LE TOTAL

| rang | lots / passages | constats |
|---|---|---|
| 1 — le prix | **4 lots** | 9 |
| 2 — le verdict | **3 lots** | 9 |
| 3 — la statistique | **2 lots** | 10 |
| 4 — les figures | **1 lot** | 8 |
| 5 — les livrables | **1 lot** | 6 |
| 6 — l'architecture | **1 lot** | 4 |
| 7 — le bruit | **12 passages** | 38 |
| — le tri des non alloués | 1 passe | 41 |
| **TOTAL** | **12 lots + 12 passages + 1 tri** | **125** |

⚠️ **Le regroupement raccourcit fortement** : **125 constats en 24 ouvertures**,
et les quatre premiers rangs — ce qui publie un prix, un verdict, une
statistique et une figure faux — **tiennent en 10 lots**.
