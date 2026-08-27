# RELEVÉ — `core/qualite_donnees.py`, LES QUATRE RÈGLES

**Lu intégralement** : `core/qualite_donnees.py` **334 l**. Aucun échantillon,
aucun filtre. Cinquième fichier du relevé ②.

C'est le fichier que j'avais explicitement laissé ouvert dans le relevé de
`pipeline_tarifaire` : *« j'ai vérifié qu'il bloque à 13 % ; je n'ai pas vérifié
les quatre règles une par une, ni le seuil exact de 5 % »*. C'est fait.

Son principe directeur tient en une ligne : **« jamais de correction ou
d'exclusion SILENCIEUSE ».**

## ① Le compte

**20 affirmations mesurées** — **6 constats** · **14 vérifiées bonnes**.
**1 de mes relevés refait** : je l'avais mené au texte, il comptait des mentions
en docstring comme des appels.

## ② Le classement

### A — Ce que les quatre règles ne voient pas (2)

**C1 — Une valeur MANQUANTE ou ILLISIBLE n'est vue par AUCUNE des quatre
règles.** Tous les détecteurs passent par `pd.to_numeric(..., errors="coerce")`,
et toutes les comparaisons rendent `False` sur un NaN (`NaN < 0` est faux,
`NaN <= 0` est faux, `NaN > 1` est faux ; `detecter_non_entier` exclut
explicitement les NaN par `s.notna()`). Mesuré :

```
  [CONSTAT] 50 % d'expositions NaN        anomalies=0  bloque=False  1000 -> 1000
  [CONSTAT] 100 % d'expositions NaN       anomalies=0  bloque=False  1000 -> 1000
  [CONSTAT] 50 % de frequences NaN        anomalies=0  bloque=False  1000 -> 1000
  [CONSTAT] 50 % de couts NaN             anomalies=0  bloque=False  1000 -> 1000
  [CONSTAT] 50 % d'expositions en texte   anomalies=0  bloque=False  1000 -> 1000
            synthese = None
```

**Une colonne d'exposition entièrement vide traverse la couche qualité avec
zéro anomalie**, et la synthèse destinée aux livrables rend `None` — c'est-à-dire
« rien à signaler ». Une exposition écrite `'douze mois'` fait de même.

⚠️ **Le principe directeur n'est pas violé** — il n'y a ici ni correction ni
exclusion, donc rien de silencieux au sens strict. Mais la couche dont c'est le
métier de juger la qualité des données **déclare bonnes des données absentes**.

> ✅ **`qualite/C1`** · **FERMÉ — lot ③.** Nouveau détecteur `detecter_illisible` : **le seul qui
> regarde ce que `to_numeric(coerce)` a détruit**, sur les quatre colonnes de
> RÔLE. Mesuré : les quatre formes d'absence (NaN partiel, NaN total, texte
> `« douze mois »`, chaîne vide) sont désormais signalées, et un portefeuille
> complet ne déclenche **rien**.
> ⚠️ **RÈGLE 3, PAS RÈGLE 1 — et c'est un choix, pas un oubli.** Une valeur
> manquante est **ambiguë** : vrai zéro mal encodé, erreur de transmission, ou
> grandeur réellement inconnue — *rien dans la donnée ne le dit*. La doctrine
> du module est explicite (impossible → exclure · implausible → corriger ·
> **ambigu → signaler et laisser**). Exclure trancherait à la place de
> l'actuaire et **déplacerait des lignes** sur un jugement que la donnée ne
> porte pas. **Aucun euro n'est déplacé par ce correctif.**
> Contrôles : `POS_Qualite_C1_UneValeurAbsenteEstVUE`, 4 tests.

⚠️ **Sans conséquence catastrophique en aval, et il faut le dire** : mesuré au
relevé de `pipeline_tarifaire`, une exposition illisible provoque un arrêt
*loud* — `ValueError: NaN, inf or invalid value detected in endog`. Le GLM
attrape ce que la couche qualité laisse passer. Mais le message que reçoit
l'actuaire est alors une erreur `statsmodels`, pas un rapport de qualité.

**C2 — L'escalade compte PAR TYPE, jamais l'union.** La règle 4 est écrite
« *si UN type d'anomalie (règles 1-3) touche ≥ 5 % des lignes* » — et c'est
exactement ce que fait `[a.code for a in anomalies if a.proportion >= seuil]`
(l.255). Mesuré, avec quatre types à **4,9 %** chacun :

```
  frequence_negative          49 lignes  (4.9%)
  cout_negatif                49 lignes  (4.9%)
  exposition_non_positive     49 lignes  (4.9%)
  doublon_identifiant         49 lignes  (4.9%)

  total exclu : 196 / 1000 = 19,6 %      lignes retenues : 804 / 1000
  [CONSTAT] bloque = False   escalade = False
```

**Un cinquième du portefeuille est exclu, et rien n'est escaladé.** Aucun type
n'atteint le seuil ; leur union le dépasse de quatre fois.

> ✅ **`qualite/C2`** · **FERMÉ — lot ③.** L'escalade regarde désormais **l'union des lignes
> touchées** en plus de chaque type. Mesuré sur le cas exact du constat :
> escalade **déclenchée**, motif publié
> `union_des_anomalies (196/1000 lignes, 19.6%)`.
> ⚠️ **LES DEUX CRITÈRES SONT CONSERVÉS, PAS SUBSTITUÉS** : un type unique à
> 6 % escalade toujours **sous son propre nom** — sinon le motif publié
> désignerait la mauvaise cause. Le nouveau critère ne peut qu'**ajouter** des
> escalades, jamais en retirer : *c'est la règle d'asymétrie — une liste qui
> accuse ne peut pas ouvrir de trou.*
> ⚠️ **Second sens vérifié dans les deux directions** : un portefeuille sain
> n'escalade pas, et un type isolé à 2 % non plus.
> ⚠️⚠️ **MON PREMIER BANC ÉTAIT FAUX** : mes données de témoin portaient
> `cout > 0` avec `nb = 0` sur ~80 % des lignes, si bien que l'incohérence
> dominait tout et que **mon union n'a jamais été exercée**. *Un témoin qui
> n'est pas sain ne mesure rien.*
> Contrôles : `POS_Qualite_C2_L_EscaladeVoitL_UNION`, 4 tests.

⚠️ **Ce n'est PAS silencieux** — la synthèse dit bien « ✔ 196 ligne(s)
EXCLUE(S) (impossible) ». La couche **informe**, elle ne **s'arrête** pas. La
différence est celle entre un rapport et un gate : ce que l'actuaire doit
*confirmer nominativement* reste déterminé par la plus grande anomalie prise
isolément.

⚠️ Et `resume()` — le dict qui part dans l'`audit_trail` — publie une
proportion **par type** et **aucune proportion totale** (voir C6).

### B — Affirme plus que le code ne porte (2)

**C3 — Le plafond `1.0` est une hypothèse d'UNITÉ, sur un rôle dont le plan ne
déclare jamais l'unité.** La règle 2 est décrite comme une correction « établie »
— « *exposition > 1 — implausible pour un contrat annuel* » (l.234). Le plan
déclare le **rôle** `exposition` ; il ne dit nulle part si le client la fournit
en années, en mois ou en jours. Mesuré sur le même portefeuille exprimé en mois :

```
  exposition en mois (0,3 a 12) : bloque=True  escalade=True     <-- l'escalade tient
  AVANT : ⚠ CONTROLE QUALITE BLOQUE — [exposition_sup_1] touchant >= 5% des lignes.

  une fois VALIDEE nominativement :
    ✔ 1000 ligne(s) CORRIGEE(S) : 1000x exposition_sup_1 (plafond a 1.0).
    ✔ Poursuite malgre anomalie(s) >= 5% VALIDEE par « Selasse Sekle » le 24/08/2026.

  exposition totale : 7 777 -> 1 000        (87 % perdue)
```

⚠️ **Le garde-fou fonctionne : il bloque, et l'échappatoire est nominative et
tracée.** Ce qui manque est dans le message : l'actuaire lit « 1000 lignes
corrigées », pas « l'exposition totale du portefeuille passe de 7 777 à 1 000 ».
Il valide une ligne de rapport, il obtient une prime divisée par huit.

`1.0` est l'unique constante métier du fichier — mesuré par AST, les seules
constantes numériques de `controler_qualite` sont `[0, 1.0, 2, 3]`, où 1/2/3
sont les numéros de règle.

**C4 — Les sept détecteurs « purs et réutilisables » n'ont aucun appelant, et
`controler_qualite` n'en a qu'un.** Relevé **par AST** :

```
  [CONSTAT] detecter_negatifs        appels=0   mentions=0
  [CONSTAT] detecter_non_positif     appels=0   mentions=0
  [CONSTAT] detecter_sup             appels=0   mentions=0
  [CONSTAT] detecter_non_entier      appels=0   mentions=0
  [CONSTAT] detecter_incoherence     appels=0   mentions=0
  [CONSTAT] detecter_doublons_id     appels=0   mentions=0
  [CONSTAT] detecter_doublons_ligne  appels=0   mentions=0

            controler_qualite        appels=1   -> pipeline_tarifaire.py
```

⚠️ **Un seul appelant de production, et c'est le chemin déclaratif.** Le chemin
agent (A1→A6) **n'appelle jamais la couche qualité** : A1 porte sa propre
détection (`_valider_qualite`, l.708), qui *score* sans agir — exactement le
défaut que l'en-tête l.26-27 reproche à A1.

⚠️ La « convergence future » annoncée l.28 n'est pas faite : **deux
implémentations coexistent**, et A1 n'importe pas ce module.

### C — Imprécis (2)

**C5 — L'en-tête cite une fonction d'A1 qui n'existe nulle part.** L.25 :
« *Réutilise la logique de détection déjà pensée dans A1 (`_evaluer_qualite`)* ».
Mesuré sur tout le dépôt :

```
  _evaluer_qualite : 1 seule occurrence -> core/qualite_donnees.py:25 (cette phrase)
  A1 porte en realite : ['def _valider_qualite']
```

La fonction a été renommée ; la référence ne l'a pas suivie.

**C6 — `resume()` ne porte aucune proportion totale.** Le dict qui part dans
l'`audit_trail` et les rapports publie `lignes_initiales`, `lignes_retenues`, et
une `proportion` **par anomalie** — jamais la part du portefeuille touchée. Sur
le cas de C2, il faut soustraire deux entiers pour découvrir les 19,6 %.

```
  cles du resume : ['anomalies_au_dela_seuil','bloque','corrections',
                    'escalade_declenchee','exclusions','horodatage',
                    'lignes_initiales','lignes_retenues','seuil',
                    'signalements','validee_par']
```

### D — Vérifié comme BON (14)

| affirmation | mesure |
|---|---|
| **R1** — fréquence < 0 exclut la ligne | 20 détectées, règle 1, **1000 → 980** |
| **R1** — coût < 0 exclut la ligne | 20 détectées, règle 1, **1000 → 980** |
| **R1** — exposition ≤ 0 exclut la ligne | testé à **0** et à **−0,5** : 20 chacune, 1000 → 980 |
| **R1** — doublon sur l'identifiant déclaré | 20 détectées, règle 1, 1000 → 980 |
| **R2** — exposition > 1 corrige et conserve | 20 corrigées, **1000 → 1000**, `correction='plafond a 1.0'` |
| **R3** — fréquence non entière : signale, ne touche rien | 20 signalées, **1000 → 1000** |
| **R3** — doublon de ligne SANS identifiant : ambigu | 20 signalés, **1020 → 1020** — aucune ligne retirée |
| **R3** — incohérences, **les deux sens** | coût sans sinistre **15** · sinistre sans coût **10** |
| **R4** — le seuil est exactement `>= 5 %` | 49/1000 = 4,9 % → passe · **50/1000 = 5,0 % → bloque** · 51 → bloque |
| **R4** — l'échappatoire nominative est tracée | 13 % → bloqué ; validée → `bloque=False`, **1000 → 870**, `validee_par='Selasse Sekle'`, date **24/08/2026** |
| `df` n'est **jamais muté en place** | `df.equals(avant)` = **True** après appel ; l'exposition d'entrée reste à 3,0, celle de sortie est à 1,0 |
| **aucun nom de colonne codé en dur** | AST sur `controler_qualite` : **0 littéral** de colonne ; rôles lus = `cible_cout`, `cible_frequence`, `exposition`, + `getattr(plan,'identifiant_contrat')` |
| `synthese_qualite_donnees` atteint les livrables | **3 appelants** : `rapport_equipe_tarif`, `rapport_modeles_tarif`, `tarif_excel` |
| `QualiteBloquante` est levée par `pipeline_complet` | comme sa docstring l'annonce : **0 `raise` dans ce module**, le seul appelant lit `.bloque` et lève |

### Mon relevé refait

J'avais d'abord compté les consommateurs de `synthese_qualite_donnees` **au
texte** : 6 fichiers. Refait **par AST** : **3 appels réels**, et 3 mentions qui
n'en sont pas — `core/mapping_client.py`, `core/plan_tarifaire.py` et
`a6_comparaison/agent.py` **la citent en commentaire** (« *comme
synthese_qualite_donnees() pour la qualité de données* ») sans jamais l'appeler.

⚠️ Un relevé au texte **sur-compte** exactement là où un relevé par symbole
**sous-compte**. Les deux se vérifient l'un l'autre ; aucun ne se suffit.

## ③ Ce que je ne tranche pas ici

**Rien n'est resté non lu** : 334 lignes, intégralement.

- **Ce que A1 fait de sa propre détection.** Il porte `_valider_qualite` et
  compte 2 comparaisons `< 0`, 1 `<= 0`, 1 `> 1` et 3 `duplicated` — la même
  famille de tests, écrite deux fois. Savoir si les deux implémentations
  **divergent** relève d'un relevé d'A1, déjà couvert sous un autre angle.
- **L'absence de couche qualité sur le chemin agent** rejoint le chantier ④
  (« l'équilibre du chemin agent »), arbitré et non codé.

## ④ Les preuves

- `preuves/audit_qualite.py` — les quatre règles une par une, la frontière
  exacte des 5 %, les quatre types à 4,9 %, les valeurs manquantes, l'exposition
  en mois, et qui lève.
- `preuves/audit_qualite_bis.py` — le texte lu par l'actuaire, le relevé **par
  AST** des appelants réels, la non-mutation de `df`, et la fonction d'A1
  introuvable.

Chacune se relance seule.

---

**Mon appréciation d'ensemble.** C'est **le fichier le plus solide des cinq
relevés**. Les quatre règles font exactement ce qu'elles annoncent, une par
une, dans les deux sens : la règle 1 exclut, la 2 corrige et conserve, la 3
signale sans toucher, et la 4 bloque **au centième près** au seuil déclaré. Le
`df` d'entrée n'est jamais muté. Aucun nom de colonne n'est codé en dur — les
quatre rôles viennent du plan, sans exception. Et l'échappatoire est ce qu'elle
prétend être : nominative, tracée, non contournable par un `try/except`.

⚠️ **Les deux constats graves portent sur ce que le contrôle NE MESURE PAS**, et
c'est la même question posée deux fois : **quelle est l'assiette ?** Le contrôle
mesure des valeurs *présentes* (et ne voit donc pas l'absence, C1), et il mesure
*par type* (et ne voit donc pas l'union, C2). Dans les deux cas le mécanisme est
juste sur ce qu'il regarde, et son regard est plus étroit que sa promesse.

⚠️ **Et un point qui n'est pas de ce fichier mais que ce fichier révèle** : le
chemin agent — A1 à A6, celui qui tourne dans l'application — **n'a pas de
couche qualité du tout**. Ce module a **un** appelant de production.
