# RELEVÉ A1 — INGESTION & VALIDATION

**Lu intégralement** : `a1_ingestion/agent.py` **1 084 l** + `test_a1_ingestion.py` **195 l**. Aucun échantillon, aucun filtre.

## ① Le compte

**24 affirmations mesurées** — 10 constats · 13 vérifiées bonnes · 1 de mes soupçons réfuté. **2 non mesurables ici** (textes hors dépôt).

## ② Le classement

### A — Publie du FAUX à un actuaire qui signe (1)

**C1 — Les doublons sont comptés sur une colonne qui n'est pas un identifiant.**
[agent.py:727](direction_non_vie/tarification/a1_ingestion/agent.py:727) sélectionne la colonne d'identifiant par sous-chaîne `'id'` ou `'pol'`, et retient **la première dans l'ordre du fichier**.

```
  MEME DONNEE, 200 lignes, ZERO doublon reel
  forme_juridique en 1er -> nb_doublons=196 (98,0 %)  statut ROUGE
  id_contrat      en 1er -> nb_doublons=0   (0,0 %)   statut VERT
```

Mesuré sur le vocabulaire réel (261 noms, 20 plans + `SYNONYMES_COLONNES`) : **4 faux positifs, tous facteurs déclarés** — `forme_juridique` (rcpro), `caution_solidaire` (GLI), `antecedents_accidents_3ans` (auto), `poids`. Tous contiennent `id` (jur**id**ique, sol**id**aire, acc**id**ents, po**id**s).

> ✅ **`a1/C1`** · **FERMÉ le 30/08/2026 — ET IL ÉTAIT CORRIGÉ *ET* ÉPINGLÉ
> DEPUIS UN MOMENT.** *Preuve : `test_a1_ingestion.py`, classe
> `T_L_Identite_D_Un_Contrat_Se_Declare`, 3 violations plantées.*
>
> Le correctif, lu au site : l'identifiant vient **d'abord** de
> `plan.identifiant_contrat` ([l.761](direction_non_vie/tarification/a1_ingestion/agent.py:761)),
> la devinette par sous-chaîne n'est plus qu'un **repli qui ne se tait plus** —
> `source_identifiant` vaut `plan`, `devinee` ou `aucune`, **chacun avec son
> avertissement**. Le contrôle plante exactement le scénario du relevé :
> `forme_juridique` (qui contient « id ») **avant** `id_contrat`, et A1 retient
> `id_contrat`.
>
> ⚠️⚠️ **CE QUI MANQUAIT N'ÉTAIT NI LE CODE NI LE CONTRÔLE : C'ÉTAIT LE LIEN.**
> Aucun test ne **nommait** `a1/C1`. `ARCH-1` n'exige un bloc de fermeture que
> pour un constat **nommé** par un test : il ne pouvait donc pas voir celui-ci,
> et le constat comptait OUVERT alors qu'il était fait. **Quatrième état,
> distinct du troisième** (« corrigé, aucun contrôle »). Le nommage est posé
> dans la classe de test — c'est lui, autant que le bloc, qui ferme.
>
> ⚠️ **Le repli reste, et c'est délibéré** : les vingt plans du dépôt ne
> déclarent rien. *Il est légitime tant qu'il se déclare.*

⚠️ **Atteint la production** : l'app appelle `a1.run(dataframe=df, …)` ([actuaria_app.py:3540](actuaria_app.py:3540)) avec le fichier client **dans son ordre d'origine**. Le sens de l'erreur est un **faux ROUGE** — il rejette du bon, il ne laisse pas passer du mauvais.

### B — Affirme plus que le code ne porte (4)

**C2 — Le garde-fou de périmètre n'empêche pas ce qu'il annonce.** Le commentaire [l.161](direction_non_vie/tarification/a1_ingestion/agent.py:161) dit « Empêche qu'un portefeuille Vie ou Santé soit ingéré ». Mesuré : un fichier placé dans `data/vie/` est **chargé** — `_charger_fichier` parcourt `['non_vie','vie','sante_prevoyance']` ([l.475](direction_non_vie/tarification/a1_ingestion/agent.py:475)). Le garde bloque le *paramètre* `branche`, pas le *chemin*. **Non atteint par l'app** (elle ne passe jamais `fichier=`).

**C3 — `prime_pure > 0` annoncé, `< 0` testé.** Docstring [l.719](direction_non_vie/tarification/a1_ingestion/agent.py:719). Mesuré : 100 lignes à `prime_pure = 0` → `aberrants = aucun`.

> ✅ **`a1/C3` + `a1/C4`** · **`C3` ET `C4` FERMÉS — lot ③. Dans les deux cas, LE CODE CONTREDISAIT SA PROPRE DOCSTRING.**
> `C4` : la docstring déclarait « Exposition : **0 < exposition ≤ 1** » et le code écrivait `between(0, 1)`, **inclusif des deux bornes**. Corrigé en `inclusive='right'` — mesuré, `expo_ok_pct` passe de 100,0 à 80,0 sur 20 % d'expositions nulles, et **concorde enfin avec l'alerte 4d**. ⚠️ Second sens : une exposition de **1,0 reste saine** — la borne haute ne bouge pas.
> `C3` : la docstring déclarait « Montants : **prime_pure > 0** » et le code testait `< 0` sur un groupe de quatre colonnes. ⚠️ **Les quatre ne partagent pas le même contrat** : `cout_total_sinistres = 0` est le cas **NORMAL** d'un contrat sans sinistre. Les traiter en bloc, c'était appliquer à l'une le contrat de l'autre. `prime_pure` est sortie du groupe et testée `<= 0` ; les trois autres restent en `< 0`.
> ⚠️ **`prime_commerciale = 0` reste À INSTRUIRE, pas corrigé** : une prime commerciale nulle est probablement aberrante, mais aucune docstring ne le déclare — je ne l'étends pas de moi-même.
> Contrôles : `POS_A1_C3_C4_LesBornesDisentCeQueLaDocstringDeclare`, 4 tests.

**C4 — `exposition = 0` reçoit deux verdicts dans la même fonction.** Contrôle 3 (`between`, inclusif) → `expo_ok_pct = 100.0` ; contrôle 4d → `exposition_nulle_ou_negative`. Le score dit sain, l'alerte dit aberrant.

**C10 — L'en-tête du fichier de test annonce « 7 tests », il y en a 9.**

### C — Imprécis ou daté (5)

**C5** — `SYNONYMES_COLONNES` porte 2 doublons : `id_police` et `nb_sin`, chacun deux fois.
**C6** — `warnings.filterwarnings('ignore')` au niveau **module** ([l.52](direction_non_vie/tarification/a1_ingestion/agent.py:52)) : mesuré, après l'import le premier filtre du process est `('ignore', None, <class 'Warning'>, None, 0)`. **Tout le process** est muet, pas seulement A1.

> ✅ **`a1/C6`** · **FERMÉ le 30/08/2026 — ET IL AVAIT ÉTÉ CORRIGÉ PAR LE LOT
> D'UNE AUTRE ZONE, SANS QUE PERSONNE NE LE SACHE.**
> *Preuve : `test_avertissements_non_avales.py`, violation plantée sur A1 seul.*
>
> ⚠️⚠️ **LE JUMEAU INTER-ZONES.** Le lot mesurait **`a2/C15`** — le *même*
> défaut, relevé dans la zone A2, à **40 sites** — et son correctif a traité
> **les six agents**, donc A1. Le site porte le numéro `a2/C15` ; `a1/C6` est
> resté **OUVERT au compte** tout ce temps.
>
> > ### **Un correctif mesuré dans une zone peut fermer un constat d'une AUTRE zone. Si rien ne le nomme, le compte publié reste faux.**
>
> Mesuré au site : **aucun `filterwarnings` actif** dans A1, il ne reste que le
> commentaire qui raconte le retrait. Le filet couvre les six agents, et la
> violation plantée le confirme **sur A1 seul** — *un filet qui ne tirerait que
> sur le total n'aurait rien prouvé pour cette zone.*
**C7** — Instancier A1 **écrit sur le disque** : `/tmp/actuaria/{audit,config}` créés. L'app le fait à chaque run (`base_path` non passé).
**C8** — **L'audit trail persisté est perdu en silence.** Dossier écrivable → `A1_….json` écrit. Dossier inécrivable → aucun fichier, `success=True`, `erreur=None`, `alertes=[]`. Le dict `audit_trail` reste dans le résultat ; c'est la **trace persistée** qui disparaît sans un mot.
**C9** — `verifier_tous_fichiers` : **1 mention, 0 appel**, et elle annonce des fichiers Vie/Santé hors périmètre depuis le 11/07.

### D — Vérifié comme BON (13)

| affirmation | mesure |
|---|---|
| pénalité aberrants « jusqu'à −3 pts » | **exactement 3,00 pts** sur 5 types |
| plafond RAG aberrants | propre=**VERT** · 1 aberrant=**AMBRE** · 10 %=**ROUGE** |
| les 6 seuils déclarés = les seuils appliqués | **6/6** aux bornes (79,9/80,1/95,1/5,1/4,9/0,9) |
| `BRANCHES_SUPPORTEES` rejette hors périmètre | **5/5** (vie, sante_prevoyance, sante, vide, None) |
| `sous_branche` obligatoire, jamais de repli `'auto'` | `success=False`, `branche='non_vie'` |
| une LoB inédite est acceptée telle quelle | `'une_lob_jamais_vue'` propagée |
| extension inconnue → erreur propre | `ValueError` nommant les **6** formats |
| sélecteur d'identifiant | **21 des 25** noms attrapés sont de vrais identifiants |

### Mon soupçon réfuté

J'avais lu `densite_population` comme contenant `'pol'`. **Faux** — « population » s'écrit p-o-**p**-u-l. Mesuré, écarté, et c'est ce qui m'a conduit au vrai vocabulaire.

## ③ Ce que je n'ai pas lu — et ce que je ne peux pas trancher ici

**Rien n'est resté non lu** pour A1 : 1 084 + 195 lignes, intégralement.

Deux affirmations **non mesurables dans le dépôt** :
- **`Code de la route Art. R.221-1`** invoqué pour la plage `[16, 99]` ([l.717](direction_non_vie/tarification/a1_ingestion/agent.py:717) et [l.767](direction_non_vie/tarification/a1_ingestion/agent.py:767)). Les deux sites n'en disent pas la même chose — la docstring attribue `16` à l'article, le commentaire parle de « permis B dès 17 ans AAC ». Je n'ai pas le texte. **Je ne dis pas qu'il est faux, je dis que je ne l'ai pas vérifié.**
- **`IA France (2019) §4.2`** ([l.715](direction_non_vie/tarification/a1_ingestion/agent.py:715), [l.741](direction_non_vie/tarification/a1_ingestion/agent.py:741), [l.820](direction_non_vie/tarification/a1_ingestion/agent.py:820)) — même corps que celui en attente de ton arbitrage.

## ④ Les preuves

Trois scripts reproductibles en scratchpad : `audit_a1.py` (12 mesures), `audit_a1_bis.py` (vocabulaire réel + audit trail), plus les mesures de seuils et de garde-fous. Chacune se relance seule et rend le même verdict.

---

**Mon appréciation d'ensemble** : A1 est solide sur ce qui décide — les 6 seuils sont exactement ceux annoncés, le plafond aberrants mord aux bornes documentées, et la Phase 1 a bien supprimé le repli silencieux sur `'auto'`. Le défaut C1 est le seul qui publie du faux, et il vient d'un raccourci de deux caractères (`'id' in c.lower()`), pas d'une erreur de conception.
