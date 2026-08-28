# RELEVÉ — `pipeline_agents.py`, L'ORCHESTRATEUR

**Lu intégralement** : `direction_non_vie/tarification/pipeline_agents.py`
**317 l**. Aucun échantillon, aucun filtre. Sixième fichier du relevé ②.

Il porte **trois règles déclarées non négociables** (décisions actuaires),
**trois cibles** et **un contrat de sérialisation**. Il a été écrit pour réparer
trois défauts nommés dans son propre en-tête.

## ① Le compte

**16 affirmations mesurées** — **6 constats** · **10 vérifiées bonnes**.

## ② Le classement

### A — Le constat qui domine tous les autres (2)

**C1 — L'orchestrateur n'a AUCUN appelant de production, et les trois défauts
qu'il répare sont intacts partout.** Relevé **par AST** sur tout le dépôt :

```
  [CONSTAT] pipeline_agents    production=0  tests=1
  [CONSTAT] ResultatAgents     production=0  tests=1
  [CONSTAT] ArbitrageCible     production=0  tests=1
  [CONSTAT] CIBLE_COUT         production=0  tests=1
  [CONSTAT] CIBLE_PRIME_PURE   production=0  tests=1
```

Son en-tête décrit trois défauts. **Les trois sont encore là**, mesurés :

**① « chaque appelant assemblait la chaîne à la main »** — neuf fichiers
instancient trois agents ou plus, dont trois hors tests :

```
  [⚠] actuaria_app.py                     CHAINE COMPLETE (les 6 agents)
  [⚠] demos/pipeline_3lob_a1_a6_demo.py   5/6  (sans A5)
  [⚠] scripts/rapport_tarif_local.py      5/6  (sans A5)
```

**② « `result_a5` valait `None` PARTOUT »** — toujours vrai en production :

```
  [CONSTAT] demos/pipeline_3lob_a1_a6_demo.py   l.151  result_a5=None
  [CONSTAT] scripts/rapport_tarif_local.py      l.111  result_a5=None
           pipeline_agents.py                   l.259  result_a5=r5 if r5.get('success') else None
```

**③ « LA MOITIÉ DU TARIF N'ÉTAIT JAMAIS CHALLENGÉE »** — les deux appelants de
production n'arbitrent que la fréquence :

```
  demos/pipeline_3lob_a1_a6_demo.py   l.151  A6  col_cible='nb_sinistres'
  scripts/rapport_tarif_local.py      l.111  A6  col_cible='nb_sinistres'
```

⚠️⚠️ **Et l'application fait moins que cela.** `actuaria_app.py` instancie bien
les six agents, mais **jamais en une chaîne** : il aiguille par « besoin ». Pour
`selection` (l.3599-3609), il enchaîne A2 → A3 → **A6**, en passant à A6
`result_a3` **seul** — ni `result_a4`, ni `result_a5`, ni `col_cible`. A5 est
lancé ailleurs, **seul**, sur `nb_sinistres` (l.3589-3592), et son résultat
n'entre dans aucun arbitrage.

⚠️ *Ce que A6 fait alors d'un catalogue à une seule famille est une question
d'A6, déjà relevée — je ne la tranche pas ici.* Le fait mesuré est celui-ci :
**dans l'application, l'arbitrage ne reçoit que le GLM.**

**C2 — `.success` vaut `True` alors que l'arbitrage a échoué.** La propriété
teste `self.frequence.a6 is not None` (l.112). Or `_arbitrer` rend **toujours**
un dict `a6`, y compris quand A6 a échoué. Mesuré :

```
  a6 = {'success': False, 'erreur': 'A6 a echoue', 'classement': []}

  [CONSTAT] ResultatAgents.success = True
            statut_rag  = None
            n_candidats = 0
            resume()['success'] = True   modele_production = None
```

Le `resume()` — que la docstring appelle **« le livrable d'audit »** — publie
`success: True`, `modele_production: null`, `classement: []`. ⚠️ **Sur un échec
d'A3, en revanche, `.success` est correctement `False`** : c'est le seul des
deux échecs que la propriété regarde.

### B — Affirme plus que le code ne porte (2)

**C3 — La cible FRÉQUENCE n'est pas protégée, les deux autres le sont.** La
docstring l.216-219 : « *Un arbitrage peut échouer là où un autre réussit […]
c'est rendu dans `<cible>.erreur`, jamais masqué, et n'empêche pas les autres
d'aboutir.* » Mesuré par AST :

```
  les trois appels a _arbitrer sont aux lignes [272, 288, 308]
  [CONSTAT] _arbitrer l.272  protege par un try : False    <-- FREQUENCE
            _arbitrer l.288  protege par un try : True     <-- COUT
            _arbitrer l.308  protege par un try : True     <-- PRIME PURE
```

Si l'arbitrage de fréquence lève, l'exception **remonte** : `pipeline_agents`
n'a plus de retour, et les deux autres cibles — qui auraient pu aboutir — sont
perdues. La promesse vaut pour deux cibles sur trois.

**C4 — `resume()` génère un horodatage, là où deux modules frères refusent
explicitement de le faire.** L.157 : `"date_calcul": datetime.now().isoformat()`.
Mesuré, deux appels sur **le même objet** :

```
  champs qui different : ['date_calcul']
    ('date_calcul', '2026-08-24T16:14:00.384865', '2026-08-24T16:14:00.384929')
```

À comparer :

| module | ce qu'il écrit |
|---|---|
| `core/qualite_donnees.py` | « *Ne génère aucun horodatage — réutilise celui fourni par l'appelant* » |
| `core/conformite_reglementaire.py` | « *aucune date n'est générée ici : on réutilise* » |
| `pipeline_agents.py` l.157 | `datetime.now().isoformat()` |

Deux exécutions identiques produisent deux livrables d'audit différents.

> ✅ **`agents/C4`** · **FERMÉ le 28/08/2026.** `ResultatAgents` porte désormais
> `date_calcul`, **capturé UNE FOIS par le run** et transporté ; `resume()` le
> RÉUTILISE. Deux rendus du même objet sont identiques, champ par champ.
> ⚠️⚠️ **CE QUI N'ÉTAIT PAS LE DÉFAUT, ET LA DISTINCTION EST DE FOND** : le run
> lit bien l'horloge (`t0`, pour `audit_id`) — c'est légitime, un RUN a le droit
> d'avoir une date. Le défaut était de la RELIRE À CHAQUE RENDU. *Un livrable
> doit pouvoir se re-rendre à l'identique.*
> ⚠️ **LE CHAMP EST REQUIS, PAS À DÉFAUT** : `''` ou `None` laisserait un site
> de construction l'omettre en silence et publier un vide sous une étiquette de
> date. *« Présent mais VIDE » a déjà mordu trois fois dans cet audit.* Les cinq
> sites de construction le passent explicitement.
> ⚠️⚠️ **ET IL N'EST PAS DÉRIVÉ DE `audit_id`, BIEN QUE CELUI-CI L'ENCODE** :
> `audit_id` est une ÉTIQUETTE, faite pour être lue. *Lire une donnée dans une
> étiquette est exactement le défaut que cet audit poursuit* (cf. la décision
> réglementaire qui lisait un emoji, `236dcf2`).
> ⚠️ `astimezone()` rend l'horodatage non ambigu (offset explicite) **sans
> toucher `audit_id`** : la chaîne locale `%Y%m%d_%H%M%S` est identique, vérifié.
> **Épinglé par `test_horodatage_agents.py` (5 contrôles), dont deux SECONDS
> SENS** : omettre le champ LÈVE, et deux runs distincts portent bien deux dates
> — *un correctif qui figerait la date fermerait le constat en détruisant
> l'information.*

### C — Imprécis (2)

**C5 — `_vue_sinistres` annonce un dict et rend un tuple.**

```
  annonce  -> Dict[str, Any]
  retourne -> ({**result_a2, 'dataframe': df_sin}, cible)
```

La docstring est juste sur le fond (« *Retourne un result_a2 de MÊME FORME* »)
et tait le second membre, qui est l'objet `CibleSeverite` utilisé juste après
pour le seuil des 100 sinistrés.

**C6 — Le message d'échec de la prime pure accuse le mauvais coupable, et il ne
concerne qu'un plan — celui bâti sur les données réelles.** L.301-305 : si la
colonne manque, l'erreur dit « *contrat de données V7 B2 rompu —
`_calculer_prime_pure`* ». Mesuré, la vraie cause est ailleurs :
`A2._calculer_prime_pure` (l.663-667) lit **`'cout_total_sinistres'` et
`'exposition'` en dur**, pas `plan.cible_cout` / `plan.exposition`.

```
  plans ou A2 peut calculer prime_pure : 19/20

  auto_fr_reel.yaml   exposition=Exposure   cible_freq=ClaimNb   cible_cout=ClaimAmountTotal   NON
```

⚠️ **Le seul plan concerné est `auto_fr_reel.yaml`** — celui construit sur le
jeu de données français réel. La troisième cible y est perdue, et le message
oriente l'actuaire vers un contrat de données rompu plutôt que vers deux noms de
colonnes codés en dur. ⚠️ *L'en-tête l.77-78 dit d'ailleurs « HORS plan » : le
fait est connu, c'est le message d'erreur qui ne le reflète pas.*

### D — Vérifié comme BON (10)

| affirmation | mesure |
|---|---|
| **RÈGLE 1** — le masque vient de `construire_cible_severite`, jamais recalculé | **1 seul appel** dans tout le fichier ; **aucun** `duplicated`/`where`/`mask` sur place |
| **RÈGLE 2** — CANN exclu de la cible coût | fréquence `('cann','tabnet')` · coût `('tabnet',)` · prime pure `('tabnet',)` |
| **RÈGLE 3** — aucun poids sur la cible coût | fréquence `ponderer=True` · coût **`False`** · prime pure **`False`** |
| `resume()` — « `json.dumps()` ne lève jamais, y compris sur un échec » | échec total → **686 caractères**, aucune exception |
| …y compris avec des objets lourds dans `a6` | `DataFrame` + `np.float64` + `np.float32` dans le classement → **1 247 caractères**, aucune exception |
| `.success` sur un échec d'**A3** | **`False`** — correct |
| `CIBLE_COUT` = ce qu'A3 déclare | `a3_glm/agent.py:350` → `metriques['gamma']['cible'] = 'cout_moyen'` — **identique** |
| `CIBLE_PRIME_PURE` = ce qu'A3 déclare **et** ce qu'A2 produit | `a3_glm/agent.py:365` → `'prime_pure'` ; `a2:667` → `df['prime_pure'] = …` — **identique** |
| « `pipeline_complet` ne référence ni A4 ni A5 » | **4/4 absents** : `AgentA4ML`, `AgentA5DeepLearning`, `a4_ml`, `a5_deep_learning` |
| la couverture de test | **10 tests**, et ils appellent réellement `pipeline_agents()` — dont `test_cann_present_en_frequence_absent_en_cout` et `test_le_cout_tourne_sur_les_sinistres_seulement` |

## ③ Ce que je ne tranche pas ici

**Rien n'est resté non lu** : 317 lignes, intégralement.

- **Ce que A6 fait d'un catalogue à une seule famille** (le cas de
  l'application) est une question d'A6, déjà couverte par le relevé d'A6 sous un
  autre angle.
- **Le seuil `< 100` sinistrés** (l.281) : le dépôt le teste
  (`test_trop_peu_de_sinistres_le_seuil_est_atteint`) ; je ne l'ai pas mesuré
  moi-même et je ne le compte donc pas comme vérifié.

**Une observation factuelle, pas un constat** : `models_path` et `audit_path`
ont pour défaut `'/tmp'`. Mesuré sur cette machine (win32), le répertoire
**existe** — Python le résout en `C:\tmp`. Les livrables d'audit par défaut
partent donc hors du dépôt, dans un répertoire temporaire ; tous les appelants
réels passent un chemin explicite.

## ④ Les preuves

- `preuves/audit_orchestrateur.py` — les trois règles par AST, le contrat
  `json.dumps` (échec total et objets lourds), la reproductibilité de `resume()`,
  `.success` malgré l'échec d'A6, l'asymétrie des `try`, les annotations et les
  chemins par défaut, et les appelants.
- `preuves/audit_orchestrateur_bis.py` — qui assemble la chaîne à la main, où
  `result_a5=None` subsiste, quelles cibles sont réellement arbitrées, et la
  couverture de test.

Chacune se relance seule.

---

**Mon appréciation d'ensemble.** Le fichier est **bien fait**. Ses trois règles
non négociables sont tenues, vérifiables par AST en trois lignes : un seul appel
à la source unique de sévérité, le CANN présent sur la seule fréquence, la
pondération sur la seule fréquence. Son contrat de sérialisation est **plus
solide qu'annoncé** — il survit à un `DataFrame` et à des scalaires numpy glissés
dans `a6`. Les deux noms de cible correspondent **exactement** à ce qu'A3
déclare. Et il est correctement testé, par dix tests qui l'exécutent vraiment.

⚠️⚠️ **Et il ne sert à rien, aujourd'hui.** Zéro appelant de production. Les
trois défauts que son en-tête décrit — la chaîne assemblée à la main,
`result_a5=None`, la moitié du tarif jamais challengée — **sont exactement aussi
présents qu'avant son écriture**, dans les trois fichiers de production qui
tarifent. L'orchestrateur est la bonne réponse à un problème que personne ne lui
soumet.

⚠️ **C'est une variante du motif du chantier, et peut-être la plus coûteuse** :
d'habitude un instrument affirme plus que le code ne porte. Ici le code porte
**exactement** ce qu'il affirme — et **rien ne l'appelle**. Un correctif qui
n'est câblé nulle part se lit, dans le dépôt, comme un correctif appliqué.
