# RELEVÉ A2 — PREPROCESSING & FEATURE ENGINEERING

**Lu intégralement** : `a2_preprocessing/agent.py` **1 627 l** + `test_a2_preprocessing.py` **158 l**.

## ① Le compte

**24 affirmations mesurées** — 17 constats · 7 vérifiées bonnes · 2 de mes instruments réfutés en cours de route. ⚠️ **`C17` a été ouvert le 29/08 par la re-mesure de `C8` et `C9`** : il n'était dans aucun relevé.

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

### B — Affirme plus que le code ne porte (8)

**C3 — L'en-tête annonce « Weight of Evidence (WoE) · Target Encoding · One-Hot ».** Le code n'implémente que `label` et `one_hot` ; les 20 plans n'utilisent que ces deux-là. **Ni WoE ni Target Encoding n'existent.** Le commentaire [l.144](direction_non_vie/tarification/a2_preprocessing/agent.py:144) va plus loin : « l'encodage WoE est préféré pour les GLM ».

**C4 — L'en-tête annonce « Winsorisation (méthode IQR) ».** Le code winsorise aux quantiles `(0.01, 0.99)`. **Une seule mention d'IQR dans les 1 627 lignes : la bannière l.17.** Aucun `1.5 × IQR`, aucun `Q3−Q1`.

**C5 — « exposition = 0 → contrat de durée nulle → à exclure »** ([l.1088](direction_non_vie/tarification/a2_preprocessing/agent.py:1088)). Mesuré : 40 lignes à 0 → **400 lignes avant, 400 après**, `lignes_exclues = 0`, `valeurs_corrigees = 40`. Le code **impute par la médiane**, il n'exclut pas. `stats['lignes_exclues']` est déclaré et jamais incrémenté.

**C6 — « Supprime également les colonnes non utilisables »** ([l.1204](direction_non_vie/tarification/a2_preprocessing/agent.py:1204)). Le code dit l'inverse trois lignes plus bas : « On ne supprime pas ». `colonnes_supprimees` reste `[]`, `id_contrat` est toujours là.

**C7 — `STRATEGIES_IMPUTATION` n'est jamais lu.** 1 seule mention dans le fichier : sa propre définition. Les stratégies sont ré-écrites en dur dans `_imputer`.

> ✅ **`a2/C7`** · **FERMÉ le 29/08/2026, AVEC `a2/C8`** — arbitré : *« il
> voyage avec `a2/C8`, même défaut vu des deux côtés »*. Il était classé rang 6
> (« déclaration morte ») ; c'était le **même** défaut que `C8`, pas un voisin.
> *Preuve : `test_imputation_par_la_table.py`, 2 contrôles.*
>
> ⚠️⚠️ **LE CONTRÔLE QUI FERME N'EST PAS « la table existe » — C'EST « la table
> est LUE ».** On remplace `numerique_symetrique: 'mean'` par `'median'` dans la
> table déclarée et **le comportement doit suivre** : mesuré, `age` passe de
> *moyenne 49,926* à *médiane 50,000*. *Aucun `grep` ne peut prouver cela ; une
> exécution si.* La violation plantée — réécrire la stratégie en dur — le fait
> tomber.
> ⚠️ Un second contrôle exerce **les quatre** catégories déclarées par le chemin
> de production : une table dont trois entrées sur quatre seraient mortes serait
> le même défaut, en plus discret.

**C8 — La stratégie `'binaire' → 'mode'` n'est appliquée à rien.** Mesuré sur une colonne 0/1 (mode = 1.0) : imputée par la **moyenne, 0.789**.

> ⛔ **`a2/C8` — RE-MESURÉ LE 29/08/2026 SUR UNE VRAIE FIXTURE D'IMPUTATION.**
> **RANG 2**, classement accepté par Selasse. *Sur données propres, `_imputer`
> sort avant toute imputation : le constat ne s'y reproduit pas — c'est
> pourquoi la première re-mesure ne concluait rien.*
>
> Fixture : 40 NaN dans quatre colonnes de quatre natures, chemin `A1 -> A2.run`.
> ⚠️ **A1 ne nettoie pas les NaN** — les 40 survivent. La protection amont notée
> pour `a2/C5` portait sur l'exposition nulle, elle ne s'étend pas ici.
>
> Colonne 0/1, mode = 1.0 : **imputée par la moyenne 0,8152**. La colonne sort
> avec **trois valeurs distinctes** `[0.0, 0.8152, 1.0]` — **40 lignes portent
> une valeur qui n'est pas une modalité**.
>
> ⚠️⚠️ **ET RIEN NE L'ATTRAPE, ALORS QUE LE VOISIN EST GARDÉ.**
> `_appliquer_facteur` vérifie les modalités connues pour l'encodage `label`
> ([l.906](direction_non_vie/tarification/a2_preprocessing/agent.py:906)) et ne
> vérifie **rien** pour `binaire`
> ([l.891](direction_non_vie/tarification/a2_preprocessing/agent.py:891) :
> `pd.to_numeric(...).astype(float)`). *Un GLM reçoit une variable dite binaire
> dont le coefficient ne contraste plus deux états.*
>
> ⚠️ **PORTÉE, BORNÉE** : l'imputation est l'**étape 1**, les binaires du plan
> auto (`jeune_conducteur`...) sont **dérivés à l'étape 5** — ils ne peuvent
> pas porter de NaN. `C8` n'est atteignable que par un binaire **présent à la
> source**. Le dépôt ne livre aucun catalogue de plans, mais le seul plan MRH
> qu'il contient (`test_plan_invariants.py`) déclare **`alarme`,
> `double_vitrage`, `garantie_vol`** en `binaire`, et **aucun des trois n'est
> dans le catalogue de dérivations** (9 entrées) : ce sont des colonnes de
> source.
>
> ⚠️⚠️ **`C7` ET `C8` SONT LE MÊME DÉFAUT VU DES DEUX CÔTÉS** — la table n'est
> pas lue (`C7`), donc la seule entrée sans équivalent en dur n'est jamais
> appliquée (`C8`). Le tri classait `C7` au rang 6 ; **un correctif qui fait
> lire la table ferme les deux**. *Arbitré : ils voyagent ensemble.*

> ✅ **`a2/C8`** · **FERMÉ le 29/08/2026** (rang 2). *Preuve :
> `test_imputation_par_la_table.py`, 5 contrôles, 7 violations plantées.*
>
> **Deux gestes, et l'arbitrage exigeait les deux** :
> ① `_imputer` **lit** `STRATEGIES_IMPUTATION` — le `binaire -> mode` déclaré
> s'applique enfin. Mesuré : la colonne 0/1 passe de *moyenne 0,8152* à
> **mode 1,0**, et sort en `[0.0, 1.0]`.
> ② `_verifier_modalites_binaires` **lève**, sur le modèle exact de
> `_verifier_modalites_connues` : *l'asymétrie était le défaut* — un `label` à
> modalité inconnue s'arrêtait, un `binaire` ne passait par aucun contrôle.
>
> ⚠️⚠️ **L'ORDRE DE CLASSEMENT N'EST PAS LIBRE** : un binaire **est** numérique.
> Testé après le dtype, il retombait dans `numerique_symetrique` et recevait la
> moyenne — *c'est exactement par là que le constat passait*. La violation
> plantée « le binaire n'est plus testé en premier » le prouve.
> ⚠️ **Et c'est le PLAN qui dit ce qui est binaire**, pas la forme des données :
> deviner sur les valeurs observées ferait dépendre une stratégie d'imputation
> du hasard d'un lot.
>
> ⚠️ **CE QUE LA MESURE A CORRIGÉ DANS MON PROPRE TEST** : j'attendais une
> `ValueError` à travers `run`. Mesuré, `run` **échoue proprement** —
> `success=False`, **statut ROUGE**, motif dans le `commentaire` que lit
> l'actuaire. C'est le contrat d'agent, et c'est mieux : épingler la seule levée
> aurait laissé passer une A2 qui **plante le pipeline** au lieu de rendre un
> statut. Les deux niveaux sont désormais épinglés.

**C9 — Une moyenne rangée sous la clé `medianes`.** `parametres['medianes']['age'] = 45.83` — la médiane réelle vaut 45.0. Ce dict est le paramètre de reproductibilité invoqué au titre de l'exigence S2.

> ✅ **`a2/C9`** · **FERMÉ le 01/09/2026 — version complète arbitrée par Selasse (renommage + format auto-descriptif + mécanisme de version).**
>
> **La cause** : `cle = 'modes' if strategie == 'mode' else 'medianes'` — toute stratégie non-mode, donc la MOYENNE, atterrissait sous une étiquette qui dit médiane. Mesuré en déclenchant l'imputation : `medianes = {'age': 50,6468}` pour une médiane RÉELLE de **50,0**. La clé DÉRIVE désormais de la stratégie (`_CLE_PARAMETRE`), comme `_LIBELLE_IMPUTATION` juste à côté.
>
> ⚠️⚠️ **CE N'ÉTAIT PAS UN NOM QUI MANQUAIT, C'ÉTAIT UNE INFORMATION.** Un fichier de schéma 1 porte `{'age': 50,6468}` **sans dire** si c'est une médiane ou une moyenne, et la stratégie n'est **pas re-dérivable** depuis le JSON : `_categorie_imputation` a besoin de la SÉRIE DE DONNÉES, pas du nom de colonne. Chaque entrée porte donc désormais SA stratégie — `{'valeur': v, 'strategie': 'mean'}` — et la redondance avec le nom du seau est **voulue** : *deux sources en désaccord est un état DÉTECTABLE, là où un nom seul se contente de mentir* (`AC-3`).
>
> **La transition** : `PARAMS_SCHEMA` — patron d'`EMPREINTE_SCHEMA` — passe à **2**, et un lecteur, `lire_parametres_a2`, migre **sans jamais deviner** :
> · `modes` migre **sans perte** — en schéma 1, la ligne n'y mettait QUE la stratégie `mode` : l'information est CERTAINE ;
> · `medianes`, ambigu, est **conservé tel quel** sous `imputations_heritees`, avec `strategie: None` et la note qui dit pourquoi. *Marché, jamais effacé — le patron d'`a2/C13`* ;
> · un schéma **plus récent que le code LÈVE** : le lire comme un ancien produirait des paramètres faux en silence.
>
> ⚠️ **LE LECTEUR N'EXISTAIT PAS.** `charger_parametres` avait été supprimée (mécanisme mort), donc le fichier était **écrit et relu par personne** : *un format persisté sans lecteur n'est pas un format, c'est un dépôt.* Vérifié sur les **deux fichiers réels** de `C:/tmp/actuaria` et sur 155 artefacts de test — tous en schéma 1, tous relus après le renommage.
>
> Épinglé par `AC-1` à `AC-7`, dont `AC-5` (rien n'est deviné) et `AC-7` (un fichier déjà au schéma courant passe INTACT — *migrer ce qui n'en a pas besoin serait pire*).

> ⚠️ **`a2/C9` — RE-MESURÉ LE 29/08/2026. RANG 5**, classement accepté par
> Selasse. Sur la fixture d'imputation : `age = 49,926` pour une médiane réelle
> de **50,0**, `alarme = 0,8152` pour une médiane de **1,0** — **2 entrées sur
> 3 mal nommées**, seul `valeur_venale` est une vraie médiane.
>
> ⚠️⚠️ **CE QUE CE N'EST PAS : un nombre faux.** Les deux branches relisent la
> même clé, donc la valeur *appliquée* est correcte. C'est un **libellé faux**.
>
> ⚠️ **ET IL NE REMONTE PAS AU LIVRABLE, MESURÉ** : le dict n'est lu que dans
> A2 ([l.1028-1039](direction_non_vie/tarification/a2_preprocessing/agent.py:1028))
> et par le script d'audit ; **`median` a zéro occurrence dans `services/`**.
> Même borne déclarée que `conformite/C10`. *Le renommer touche le format d'un
> JSON persisté : c'est une décision de conception, pas une retouche.*

**C17 — « Cela évite la fuite de données » : la fuite a lieu.** La docstring de `_imputer` ([l.975-978](direction_non_vie/tarification/a2_preprocessing/agent.py:975)) garantit que les paramètres sont calculés en `train` et **réutilisés** en `predict`, « ce qui évite la fuite de données (data leakage) qui invaliderait la validation du modèle ».

> ⛔ **`a2/C17` — CONSTAT NEUF, OUVERT LE 29/08/2026** par la re-mesure de `C8`
> et `C9`. **Il n'était dans aucun relevé.** Rang non attribué.
>
> Une colonne saine au `train` ne laisse **aucun paramètre** ; en `predict`, le
> `.get(col, df[col].mean())` **recalcule sur les données de prédiction** :
>
> ```
> en PREDICT, 'age' impute par 51.281818
> moyenne du TRAIN   = 50.654000
> moyenne du PREDICT = 51.281818   <-- la valeur vient des donnees de PREDICT
> ```
>
> ⚠️ **LATENT AUJOURD'HUI, ET C'EST BORNÉ** : `mode='predict'` n'est appelé
> **nulle part** (AST, 0 appel) et `charger_parametres` a **0 appelant**. Le
> mécanisme entier est du code mort — mais la phrase, elle, est publiée dans le
> code que l'actuaire lit. *Le réparer ou le retirer avec sa promesse est une
> question rendue à l'arbitrage.*

> ✅ **`a2/C17`** · **FERMÉ le 29/08/2026 PAR RETRAIT** — arbitré : *« retire le
> mécanisme mort avec sa fausse promesse, plutôt que de le réparer »*.
> *Preuve : `test_imputation_par_la_table.py`, 3 contrôles.*
>
> Retirés : le paramètre `mode` de `run`, les branches `predict` d'`_imputer`,
> `charger_parametres` (**21 lignes**), et **la phrase**. ⚠️ **Vérifié avant le
> retrait, comme demandé** : `'predict'`, `charger_parametres` et `params_a2_`
> n'apparaissaient **que dans A2** — 6 occurrences, **0 appelant**, et aucun
> appelant du dépôt ne passait `mode` à `run` (mesuré par AST : tous passent
> `plan=` en mot-clé, donc **aucun décalage d'argument positionnel**).
>
> ⚠️ **CE QUI N'A PAS ÉTÉ RETIRÉ, ET POURQUOI** : `_sauvegarder_parametres`
> reste. C'est une **trace d'audit**, pas une promesse — le retirer aurait
> dépassé l'arbitrage et supprimé une piste. Elle n'est simplement plus
> conditionnée à un mode.
>
> ⚠️⚠️ **ET LE FILET N'ÉPINGLE PAS LE MOT « fuite » : IL ÉPINGLE L'AFFIRMATION.**
> Le fichier en parle encore — il raconte pourquoi le mécanisme est parti, et
> c'est voulu. Un filet qui chercherait le mot tomberait sur ce récit et ne
> discriminerait rien. Il cherche les **phrases qui affirment** (« Cela évite la
> fuite », « utilise les paramètres sauvegardés ») et **exige que `a2/C17` reste
> cité** : sans sa raison écrite, quelqu'un remettra le mécanisme.

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
> ✅ **`a2/C3` `a2/C4` `a2/C5` `a2/C6` `a2/C10` `a2/C11` `a2/C12` `a2/C13` `a2/C14`** · **FERMÉS le 01/09/2026.** *Preuve : `test_a2_neuf_constats.py`,
> 13 contrôles, **13 violations plantées**, une par contrôle.*
>
> ### ⛔⛔ `C5` — LE CODE ÉTAIT CORRIGÉ, LE RAPPORT MENTAIT, ET C'EST MON LOT
>
> Le constat disait « exposition = 0 → à exclure » quand le code **imputait par
> la médiane**. L'étape 1b du chantier `unite_exposition` l'a corrigé : mesuré,
> **400 lignes → 360**, la ligne est bien exclue. ⚠️ **Mais le rapport SIGNÉ
> disait autre chose — trois défauts dans un seul message :**
>
> ```
>   ✔ 40 ligne(s) CORRIGEE(S) : 40x exposition_non_positive_exclue
>                               (ligne EXCLUE (impossible)).
>      ⚠ EFFET SUR LE TOTAL de « exposition » : 299 -> 299 (+0.0 %).
>   lignes : 360 -> 360
> ```
>
> **①** « CORRIGÉE(S) » pour des lignes **EXCLUES** — le verbe contredit son
> propre détail deux lignes plus bas. *Racine : `_noter` codait `regle=2` **en
> dur**, et le rapport rangeait tout dans `corrections` sans regarder la règle.
> La classe portait déjà le champ ; c'est l'appelant qui ne le remplissait pas.*
>
> **②** « **+0,0 %** » sur un geste qui retire **10 % du fichier**. *Retirer des
> lignes d'exposition NULLE ne change évidemment aucun total d'exposition : la
> grandeur qui bouge est le COMPTE DE LIGNES.* C'est `qualite/C3` **à
> l'envers** — là un compte cachait un effet, ici un effet cachait un compte.
>
> **③** `lignes_initiales` valait **360**, pris **après** le geste. *Un compte
> pris après l'acte ne peut pas montrer l'acte.*
>
> ⚠️⚠️ **ET UNE TROISIÈME ASYMÉTRIE, TROUVÉE DANS MON PROPRE CORRECTIF.**
> L'étape 4 d'`unite_exposition` a fait publier leur description aux
> **corrections**, puis aux **signalements** — et a laissé les **exclusions**
> muettes. *Une exclusion est pourtant le geste le plus fort des trois : elle
> RETIRE des contrats du calcul.*
>
> ### LES HUIT AUTRES — des phrases qui décrivaient un AUTRE code
>
> `C3` WoE et Target Encoding annoncés, **jamais implémentés** · `C4` « méthode
> IQR » pour des **quantiles 0,01 / 0,99** · `C6` « Supprime également les
> colonnes » **trois lignes au-dessus de « On ne supprime pas »** · `C10` un
> exemple, **3 fois**, que le module **refuse** (`A2-9` le vérifie *par
> exécution*) · `C11` un conseil renvoyant à une configuration **supprimée** ·
> `C12` deux commentaires du même fichier qui **se contredisaient** · `C13` une
> colonne au dictionnaire ACPR **produite par aucun des 20 plans** · `C14`
> « 7 tests » pour **2 méthodes**.
>
> ⚠️ **`C13` est MARQUÉ, pas effacé** : *la retirer effacerait la trace du
> contrat qu'un plan pourra vouloir honorer ; la laisser muette la ferait
> passer pour une colonne vivante.* `A2-12` **re-dérive l'orphelinat** au lieu
> de recopier une mesure d'hier.
>
> ### ⛔ CE QUI RESTE OUVERT, ET POURQUOI
>
> **`a2/C9`** — rang 5, arbitré : renommer la clé change un JSON persisté.
>
> **`a2/C16`** — `__init__` crée `/tmp/actuaria`. **Il a un JUMEAU OUVERT chez
> le voisin : `a1/C7`, même mécanisme.** *Le corriger d'un seul côté recréerait
> exactement l'asymétrie que cet audit poursuit* — et ce n'est pas un texte :
> instancier cesserait d'écrire sur le disque. **Les deux ensemble, dans leur
> propre lot.**

**C16** — `__init__` crée `/tmp/actuaria` ([l.363](direction_non_vie/tarification/a2_preprocessing/agent.py:363)) — même mécanisme qu'A1.

> ✅ **`a2/C16`** · **FERMÉ le 01/09/2026, avec son jumeau `a1/C7`** — traités ensemble, comme annoncé, *parce que corriger un seul côté recréerait exactement l'asymétrie que cet audit poursuit*. ⚠️ Et la mesure a trouvé **quatre jumeaux de plus** : `a3`, `a4`, `a5` et `a6` créaient aussi leurs dossiers dans `__init__`. Six agents corrigés, deux constats numérotés. Épinglé par `A1-5` · `A1-6` · `A1-7` de `test_a1_six_constats.py`.

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

---

**C18 — Le système refuse d'inventer sur TROIS colonnes et invente sur CENT
SOIXANTE : la valeur d'un facteur tarifaire absent est comblée en silence,
par une stratégie déduite du NOM de la colonne.**

> ✅ **`a2/C18`** · **CONSTAT NEUF, OUVERT ET FERMÉ le 02/09/2026 — point ①
> des quatre restants, arbitré par Selasse sur trois questions posées avant
> tout code.**
>
> **Le constat.** `a2/C17` (`valeurs_absentes`) a fermé l'invention silencieuse
> sur les **trois grandeurs** — un trou non déclaré y **arrête le run**. Les
> **~160 facteurs des 20 plans** restaient hors portée : leur valeur absente
> était comblée par `_categorie_imputation`, qui déduit médiane, moyenne ou
> mode **du NOM de la colonne** (`'cout'`, `'prime'`, `'valeur'`…) ou du dtype.
>
> ### *Un système qui refuse d'inventer sur trois colonnes et invente sur cent soixante n'a pas une doctrine, il en a deux.*
>
> ⚠️ **ET IL FABRIQUAIT UNE MODALITÉ.** Une catégorielle sans mode calculable
> recevait la valeur littérale `'INCONNU'` — une modalité qu'aucun contrat ne
> porte, qui entrait ensuite dans l'encodage comme une vraie. *Inventer une
> valeur catégorielle est le même geste qu'inventer une valeur numérique ; il
> est simplement plus difficile à voir, parce qu'il porte un nom.*
>
> **LES TROIS ARBITRAGES DE SELASSE, POSÉS AVANT TOUT CODE :**
>
> | question | décision |
> |---|---|
> | (a) portée de la déclaration | **GLOBALE au plan**, pas facteur par facteur |
> | (b) un facteur non déclaré | **EXCLUT la ligne et le dit** ; l'ARRÊT reste aux 3 grandeurs |
> | (c) la modalité `'INCONNU'` | **SUPPRIMÉE** |
>
> *Arrêter sur trois colonnes protège le tarif ; arrêter sur cent soixante
> rendrait tout fichier client imparfait intarifable.* **Deux portes, deux
> gestes** — et `VA-9` ne tient plus une limite, il tient cette distinction.
>
> ⚠️⚠️ **CE QUE LA MESURE A TROUVÉ DANS MON PROPRE CORRECTIF, ET C'EST LE
> POINT LE PLUS UTILE DE CE LOT.** Ma première version comptait les absences
> avec `detecter_illisible` — qui signifie *non convertible en nombre*. Sur un
> témoin dont **une seule** colonne était trouée, elle nommait **six facteurs,
> dont cinq intacts** :
>
> ```
>   log observe : facteurs absents : 40 ligne(s) EXCLUE(S) sur
>                 ['age', 'carburant', 'csp', 'garantie',
>                  'milieu_geographique', 'usage']
>   trouees reellement : age, et age seul
> ```
>
> **Le rapport signé aurait dit « valeur absente sur `carburant`, 1 000
> lignes » d'une colonne pleine de « Essence » et « Diesel ».** Le type vient
> désormais du **PLAN**, jamais du dtype — déjà la doctrine de
> `_categorie_imputation` pour les binaires. `VA-12` le plante.
>
> ⚠️ *Cette coïncidence — six noms pour un trou — a été instruite, pas
> commentée. C'est elle qui a livré le défaut.*
>
> **AUCUN EURO SUR LA DONNÉE RÉELLE, ET C'EST MESURÉ :**
>
> ```
>   donnee reelle du depot, 14 243 lignes x 20 plans : 0 facteur absent
>   temoin sain, 1 000 lignes                        : 1 000 -> 1 000, DELTA 0
>   temoin a 40 trous sur `age`                      : 1 000 ->   960
> ```
>
> Ce qui apparaît est une **exclusion publiée** sur les fichiers portant des
> trous — jamais une valeur inventée.
>
> ⚠️ **UN FACTEUR ENTIÈREMENT VIDE EST UN ARRÊT, PAS UNE EXCLUSION** (`VA-15`)
> : tout exclure viderait le portefeuille, et *un agent aval prendrait un
> dataframe vide pour un portefeuille sans risque.*
>
> ⛔ **LE SCEAU A DÉMASQUÉ UN DE MES CONTRÔLES, UNE FOIS DE PLUS.** Le plant
> qui faisait diverger les positions de l'annexe du compte publié ne tombait
> sur **aucun** contrôle : `VA-14` ne trouait qu'un facteur **continu**, où les
> deux détecteurs coïncident. *Un témoin qui ne peut pas distinguer les deux
> cas qu'il oppose ne prouve rien* — la leçon de `VA-3`, réapprise sur un autre
> couple. `VA-12` porte désormais les deux types.
>
> ⛔⛔ **ET LA GATE A TROUVÉ UNE RÉGRESSION EN EUROS QUE J'AVAIS INTRODUITE LE
> JOUR MÊME.** Neuf contrôles de la famille `IMP` / `AC` sont tombés d'un coup.
> Ma première version routait **tout** facteur déclaré vers médiane/moyenne dès
> que le plan déclarait `imputer_*` :
>
> ### *un facteur BINAIRE aurait donc reçu **0,8152** — très exactement le défaut que `a2/C8` avait fermé*
>
> — et cette valeur serait entrée dans le GLM comme une grandeur continue.
> *Le plan déclare comment compléter un NOMBRE ; une MODALITÉ ne se moyenne
> pas.* La table garde donc les modalités et y répond par le **MODE**, qui est
> une modalité RÉELLE de la colonne.
>
> ⚠️⚠️ **CE N'EST PAS UN ÉCHEC DE TEST, C'EST LE FILET QUI A FONCTIONNÉ.** Les
> neuf contrôles disaient tous la même chose : *la table d'imputation n'était
> exercée QUE par des facteurs déclarés*, et ce lot leur retire ce chemin.
>
> **CE QUE LA SURFACE DE LA TABLE EST DEVENUE, ET LES TÉMOINS L'ONT SUIVIE :**
>
> ```
>   colonne NON declaree au plan     -> la TABLE decide (les 2 numeriques)
>   facteur declare, type `continu`  -> le PLAN decide
>   facteur declare, MODALITE        -> la TABLE decide (mode)
> ```
>
> Les quatre entrées de `STRATEGIES_IMPUTATION` vivent donc toujours, mais plus
> aux mêmes endroits. *Un contrôle mesure le mécanisme là où il gouverne, pas
> là où il gouvernait* — et sans ce déplacement, `IMP-1` à `IMP-4` et `AC-2`,
> `AC-3` seraient devenus du décor tout en restant verts sur un autre témoin.
>
> ⚠️ **Sans le correctif, `binaire` devenait structurellement inatteignable** :
> `_categorie_imputation` n'a qu'un appelant, et son ensemble `binaires` ne
> vient que du plan. *La forme de `socle/C2`, créée par le lot même qui
> poursuit ce motif — la seconde fois de la journée.*
>
> Épinglé par `VA-9` (réécrit) et `VA-11` à `VA-16`, plus `IMP-1` à `IMP-4` et
> `AC-2`/`AC-3` redirigés. Sceau : six violations plantées, cinq tombent, et la
> sixième — `'INCONNU'` remis dans un **commentaire** — ne tombe pas.
