# RELEVÉ A2 — PREPROCESSING & FEATURE ENGINEERING

**Lu intégralement** : `a2_preprocessing/agent.py` **1 627 l** + `test_a2_preprocessing.py` **158 l**.

## ① Le compte

**23 affirmations mesurées** — 16 constats · 7 vérifiées bonnes · 2 de mes instruments réfutés en cours de route.

## ② Le classement

### A — Publie du FAUX à un actuaire qui signe (2)

**C1 — « Winsorisées : 0 variable(s) » alors que 9 facteurs l'ont été.**
[l.1440](direction_non_vie/tarification/a2_preprocessing/agent.py:1440) lit `winsor.get('colonnes_winsorisees', {})`, mais `_appliquer_plan` retourne un dict **directement indexé par nom de colonne** ([l.719](direction_non_vie/tarification/a2_preprocessing/agent.py:719)). La clé n'existe pas → le compte est **toujours 0**.

```
  winsorisation REELLE : 9 facteurs  ['age','age_vehicule','anciennete_permis',
                                      'antecedents_sinistres_n1','bonus_malus',
                                      'km_par_an_normalise', ...]
  ACTUAIRE LIT >  Winsorisées  : 0 variable(s)
```

Le diagnostic VERT dirait de même « La Winsorisation sur **0** variable(s) réduit l'influence des valeurs extrêmes ».

> ✅ **`a2/C1`** · **FERMÉ le 29/08/2026 — LE CODE ÉTAIT CORRIGÉ, RIEN NE
> L'ÉPINGLAIT.** *Preuve : `test_comptes_a2_publies.py`, 3 contrôles.*
>
> Le troisième état, trouvé par le tri : `nb_winsor = len(winsor)` — le
> dictionnaire EST celui des colonnes écrêtées, la clé `colonnes_winsorisees`
> n'a jamais existé. Mesuré : « Winsorisées : **7** » pour **7** facteurs
> réellement plafonnés.
> ⚠️ **ON N'ÉPINGLE PAS LE NOMBRE 7** — il dépend du plan et du portefeuille.
> On épingle l'**égalité** entre ce qui est écrit et ce qui a été fait. *Ce qui
> LIMITE est sûr, ce qui AFFIRME est une dette.*
> ⚠️ Un contrôle vérifie aussi que chaque entrée porte ses **bornes** et son
> compte : sans elles, `len()` compterait encore — mais sur quoi ?

**C2 — « 5 colonne(s) n'ont pas pu être encodées » — les 5 sont encodées. Et cette phrase fausse plafonne le statut.**

```
  garantie             -> ENCODEE : ['garantie_tousrisques']
  carburant            -> ENCODEE : ['carburant_diesel','carburant_electrique']
  csp                  -> ENCODEE : ['csp_employe','csp_retraite']
  usage                -> ENCODEE : ['usage_enc']
  milieu_geographique  -> ENCODEE : ['milieu_geographique_enc']
```

`_valider_sortie` compte les colonnes `object` **restantes** ; or A2 **ajoute** les colonnes encodées et **conserve** la colonne brute. Chaque facteur catégoriel produit donc un faux signalement — et `_calculer_statut_rag` plafonne à AMBRE dès qu'il y en a un.

**Conséquence mesurée : `VERT` est structurellement inatteignable.**

```
  20 plans, donnees COMPLETES et propres
  -> VERT atteint par 0/20 plans : AUCUN
  (colonnes_object_restantes == nombre de facteurs categoriels, plan par plan)
```

> ✅ **`a2/C2`** · **FERMÉ le 29/08/2026 — MÊME TROISIÈME ÉTAT.**
> *Preuve : `test_comptes_a2_publies.py`, 4 contrôles.*
>
> Le critère est devenu une propriété de la **SORTIE** : une source est non
> encodée si **aucune** colonne `<nom>_*` n'existe. Mesuré sur données propres :
> `colonnes_non_encodees = []` et **statut VERT** — il était structurellement
> inatteignable.
>
> ⚠️⚠️ **LE PLAFOND N'A PAS ÉTÉ SUPPRIMÉ, IL A ÉTÉ RENDU JUSTE.** Une colonne
> vraiment non encodable doit TOUJOURS plafonner à AMBRE : les modèles ne
> mangent pas de chaînes. Mesuré — une colonne `commentaire_libre` injectée est
> signalée **et** fait tomber à AMBRE. *Un correctif qui aurait retiré le
> plafond aurait fermé le constat en détruisant le signal.* La violation
> plantée le confirme.
>
> ⚠️ **ET MON PROPRE TEST A ÉTÉ CORRIGÉ PAR SON ÉCHEC** : il filtrait sur
> `dtype == object`, or les colonnes sortent en **dtype `str`** — l'hypothèse
> exacte que le `Pandas4Warning` de ce module dénonce, et dans laquelle ma
> sonde est tombée. Le test porte désormais sur « **pas numérique** ».

### B — Affirme plus que le code ne porte (7)

**C3 — L'en-tête annonce « Weight of Evidence (WoE) · Target Encoding · One-Hot ».** Le code n'implémente que `label` et `one_hot` ; les 20 plans n'utilisent que ces deux-là. **Ni WoE ni Target Encoding n'existent.** Le commentaire [l.144](direction_non_vie/tarification/a2_preprocessing/agent.py:144) va plus loin : « l'encodage WoE est préféré pour les GLM ».

**C4 — L'en-tête annonce « Winsorisation (méthode IQR) ».** Le code winsorise aux quantiles `(0.01, 0.99)`. **Une seule mention d'IQR dans les 1 627 lignes : la bannière l.17.** Aucun `1.5 × IQR`, aucun `Q3−Q1`.

**C5 — « exposition = 0 → contrat de durée nulle → à exclure »** ([l.1088](direction_non_vie/tarification/a2_preprocessing/agent.py:1088)). Mesuré : 40 lignes à 0 → **400 lignes avant, 400 après**, `lignes_exclues = 0`, `valeurs_corrigees = 40`. Le code **impute par la médiane**, il n'exclut pas. `stats['lignes_exclues']` est déclaré et jamais incrémenté.

**C6 — « Supprime également les colonnes non utilisables »** ([l.1204](direction_non_vie/tarification/a2_preprocessing/agent.py:1204)). Le code dit l'inverse trois lignes plus bas : « On ne supprime pas ». `colonnes_supprimees` reste `[]`, `id_contrat` est toujours là.

**C7 — `STRATEGIES_IMPUTATION` n'est jamais lu.** 1 seule mention dans le fichier : sa propre définition. Les stratégies sont ré-écrites en dur dans `_imputer`.

**C8 — La stratégie `'binaire' → 'mode'` n'est appliquée à rien.** Mesuré sur une colonne 0/1 (mode = 1.0) : imputée par la **moyenne, 0.789**.

**C9 — Une moyenne rangée sous la clé `medianes`.** `parametres['medianes']['age'] = 45.83` — la médiane réelle vaut 45.0. Ce dict est le paramètre de reproductibilité invoqué au titre de l'exigence S2.

### C — Imprécis ou daté (7)

**C10** — L'exemple d'usage du module, **présent 3 fois** (bannière l.45, docstring de classe l.328, bloc `__main__` l.1608), est `agent_a2.run(result_a1)` — **que le module refuse** depuis la Phase 2 (`success=False`). L'exemple appelle aussi A1 sans `sous_branche`, que A1 refuse depuis la Phase 1.
**C11** — Le conseil AMBRE dit « Relancer A2 avec une configuration d'encodage étendue » : cette configuration (`VARS_CATEGORIELLES`) **n'existe plus**.
**C12** — Le commentaire l.130-135 dit « RESTE À TRAITER … les trois entrées ci-dessous » : `SEUILS_WINSOR` **a été supprimé** (l.1055 le confirme). Deux commentaires du même fichier se contredisent.
**C13** — `log_cout_total_sinistres` est documenté au `DATA_DICTIONNAIRE` (traçabilité ACPR §3.2) et **produit par aucun plan, aucune dérivée**.
**C14** — En-tête du fichier de test : « 7 tests », **2 méthodes**.
**C15** — `warnings.filterwarnings('ignore')` au niveau module ([l.86](direction_non_vie/tarification/a2_preprocessing/agent.py:86)) — mécanisme identique à A1, où je l'ai mesuré : filtre global du process.

> ✅ **`a2/C15`** · **FERMÉ le 29/08/2026 — ET IL ÉTAIT BIEN PLUS LARGE QUE SON
> LIBELLÉ.** *Preuve : `test_avertissements_non_avales.py`, 6 contrôles.*
>
> ⚠️⚠️ **CLASSÉ « C — IMPRÉCIS OU DATÉ », SUR UN SITE. RELEVÉ PAR AST : 40
> SITES DANS 39 FICHIERS DE PRODUCTION**, tous de la même forme nue —
> `direction_sante_prevoyance` **20** · `direction_non_vie` **13** ·
> `direction_vie_epre` **5** · `demos` **2**. *Un filtre posé au niveau module
> s'applique au PROCESSUS ENTIER dès l'import : tout appelant perdait les
> avertissements de modules qu'il n'a jamais importés.*
>
> **CE QU'IL CACHAIT, MESURÉ SUR UN RUN RÉEL** :
>
> ```
>   7x Pandas4Warning   `select_dtypes` -- NOTRE code, rupture pandas 4
>   6x UserWarning      sklearn : « X does not have valid feature names »
>   3x FutureWarning    statsmodels : le calcul du BIC change apres 0.13
> ```
>
> ⚠️⚠️ **LE TROISIÈME PORTE SUR UN NOMBRE PUBLIÉ** : `bic` est écrit à **trois
> sites** des métriques d'A3 et paraît au chapitre 1 du rapport signé. *Un
> nombre publié dont la définition change, et l'avertissement était avalé.*
>
> ⚠️ **ET JE CORRIGE MON PROPRE SOUPÇON** : j'avais avancé qu'un GLM non
> convergent préviendrait sans que personne ne le voie. **Aucun avertissement
> de non-convergence sur ce portefeuille.** Le mécanisme est réel, la
> trouvaille est ailleurs. *Une hypothèse mesurée vaut mieux qu'une hypothèse
> plausible.*
>
> ⚠️ **ASSIETTE DU LOT, DÉCLARÉE** : seuls les **6 agents de tarification**
> sont traités — le chantier en cours. Les **34 sites hors assiette** sont
> **nommés et figés par un test** : s'il en apparaît un de plus, le défaut se
> propage ; s'il en disparaît, quelqu'un les a traités hors relevé.
> ⚠️ **12 filtres subsistent après correctif, TOUS TIERS** (torch 4, numpy 3,
> scipy 2, pandas 1, plotly 1, IPython 1) — vérifié qu'**aucun ne vient de
> nous**. Une bibliothèque tierce qui règle ses propres avertissements n'est
> pas notre affaire.
>
> ⚠️⚠️ **ET UN DE MES FILETS A ÉTÉ RÉÉCRIT PAR SA PROPRE VIOLATION PLANTÉE** :
> il faisait `catch_warnings() + simplefilter('always')`, donc il
> **neutralisait lui-même** le filtre qu'il prétendait détecter — le filtre
> remis, **il ne tombait pas**. Il tourne désormais en SOUS-PROCESSUS, sans
> toucher aux filtres. *Un test qui installe ses propres conditions ne mesure
> plus celles du code.*
>
> ⛔ **NOMMÉ, NON TRAITÉ** : le `Pandas4Warning` vient de NOTRE `select_dtypes`
> et annonce une rupture pandas 4. Le corriger changerait **quelles colonnes
> A2 encode** — un euro peut bouger. **Arbitrage requis, hors de ce lot.**
**C16** — `__init__` crée `/tmp/actuaria` ([l.363](direction_non_vie/tarification/a2_preprocessing/agent.py:363)) — même mécanisme qu'A1.

### D — Vérifié comme BON (7)

| affirmation | mesure |
|---|---|
| plan absent → erreur propre, jamais de repli | `success=False`, message nommant `PlanTarifaire` |
| piège V9 : modalité inconnue → **lève** | `ValueError` nommant la modalité et les modalités figées |
| INV-1 : `transform` produit `colonnes_produites()` | **23/23** |
| **ordre label = ordre du plan** (correctif `254c959`) | `milieu_geographique` → `Urbain:0, Periurbain:1, Rural:2` — l'alphabétique serait `Periurbain/Rural/Urbain`. **Cas discriminant.** |
| **run() == fit/transform** sur cet ordre | codes **identiques** par les deux chemins |
| aucune colonne de genre produite | 0 sur 33 colonnes |
| `mots_asymetriques` (imputation médiane/moyenne) | **0 faux positif** sur 137 noms de facteurs |

Mon premier test d'ordre label portait sur `usage` (2 modalités, ordre du plan = ordre alphabétique) : **il ne discriminait rien**. Je l'ai refait sur un facteur où les deux ordres diffèrent.

## ③ Ce que je n'ai pas lu

**Rien** : 1 627 + 158 lignes, intégralement. Les mêmes deux références hors dépôt qu'en A1 restent non vérifiables ici — `IA France §4.1` et `ACPR-2022-P-01 §3.2` ([l.214](direction_non_vie/tarification/a2_preprocessing/agent.py:214)), plus la note honnête déjà portée par le code lui-même sur la « loi du 1er juillet 2012 » ([l.189-193](direction_non_vie/tarification/a2_preprocessing/agent.py:189)).

## ④ Mes instruments fautifs — deux

Mon test « le code calcule-t-il un IQR ? » rendait **BON à tort** : le regex `iqr` matchait **la bannière qui l'annonce**. C'est le motif déjà payé trois fois — un contrôle qui se déclenche sur le texte qui le décrit. Corrigé en localisant chaque occurrence. Le second : ma fixture ne portait pas tous les facteurs du plan, et `fit()` levait — ce qui était le **bon** comportement du module, pas un défaut.

---

**Mon appréciation** : le cœur de A2 — celui que la Phase 2 a refondu — est **solide et vérifié** : une seule autorité d'encodage pour les deux chemins, l'ordre du plan qui fait foi, la modalité inconnue qui lève, INV-1 qui tient. **Tous les constats portent sur la couche de compte rendu**, pas sur la transformation. Deux d'entre eux publient un chiffre ou une phrase faux à l'actuaire, et le second a un effet de bord réel : le statut VERT n'existe pas.
