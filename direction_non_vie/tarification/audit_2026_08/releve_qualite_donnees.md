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

### A — Ce que les quatre règles ne voient pas (3)

**C7 — L'identifiant de contrat est jugé par le détecteur des GRANDEURS, et un numéro de police normal fait BLOQUER le fichier.**

⚠️⚠️ **CONSTAT NEUF, ouvert le 30/08/2026** par la conception du chantier
`plan/C7`, et **fermé dans le même lot**. Il n'était dans aucun relevé.

`controler_qualite` faisait passer `identifiant_contrat` par
`detecter_illisible`, aux côtés de trois **grandeurs**. Ce détecteur compte
comme illisible « ce que `to_numeric` a détruit ». Or un numéro de police est
un **libellé** — `P2024-00123`, `AUTO/45/8891` — jamais un nombre.

```
  400 contrats, AUCUN doublon reel
  identifiant « C0001 » (alphanumerique)  -> 100 % d'illisibles -> BLOQUE
  identifiant « 1..400 » (numerique)      -> 0 anomalie         -> passe
```

⚠️ **Portée** : latent tant qu'aucun plan ne déclare l'identifiant (**0/20**) —
mais **il bloquait tout le chantier `plan/C7`** : déclarer le rôle rendait
inutilisable tout fichier client à identifiant alphanumérique, c'est-à-dire la
quasi-totalité.

> ✅ **`qualite/C7`** · **FERMÉ le 30/08/2026** — *preuve :
> `test_identifiant_est_un_libelle.py`, 6 contrôles, 7 violations plantées.*
>
> **Deux gestes, et le second est le plus important** : ① l'identifiant sort de
> la boucle des grandeurs ; ② il reçoit `detecter_absent` — `None`, `NaN`,
> chaîne vide — en **règle 3**. *Retirer le rôle sans le remplacer aurait fermé
> le constat en détruisant une détection légitime : une ligne sans identifiant
> ne peut être rattachée à aucun contrat, et le dédoublonnage ne peut pas en
> juger.*
>
> ⚠️ **SECOND SENS ÉPINGLÉ** : les trois grandeurs **gardent** leur détection
> d'illisibilité — resserrer une assiette ne doit pas la raboter.
>
> ⚠️ **RGPD, vérifié par sentinelle** : le message ne cite **ni valeur ni
> index** — un rôle, un nom de colonne, un compte. Une violation plantée qui y
> insère deux valeurs client fait tomber le contrôle.
>
> ⚠️⚠️ **ET J'AI RETIRÉ UN CONTRÔLE QUE J'AVAIS ÉCRIT.** J'avais composé
> `detecter_illisible` à partir de `detecter_absent` et épinglé cette
> composition. **La violation plantée ne l'a pas fait tomber** : mesuré sur
> **25 formes**, `_num().isna()` seul est **équivalent** — tout absent est déjà
> détruit par `to_numeric`. Le terme ajouté ne servait à rien et le test ne
> prouvait rien. *Un contrôle qui ne peut pas échouer est du décor.*
> **`detecter_illisible` est rendu INTACT** ; la relation entre les deux
> détecteurs est écrite, mesurée, dans la docstring de `detecter_absent`.
>
> ⚠️ **BORNE DÉCLARÉE** : `'None'`, `'null'`, `'NaN'` écrits **en texte** sont
> comptés PRÉSENTS. Ce sont peut-être des artefacts de sérialisation — *mais
> rien dans la donnée ne le dit, et accuser sans savoir serait pire que se
> taire.*

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

> ✅ **`qualite/C3`** · **FERMÉ le 31/08/2026 — chantier `unite_exposition`,
> étapes 1 à 2.** *Preuve : `test_unite_exposition_declaree.py` (15 contrôles)
> et `test_borne_exposition_source_unique.py` (6), violations plantées sur les
> deux.*
>
> **Le constat disait deux choses ; les deux sont corrigées.**
>
> **① Le message ne disait pas l'enjeu** — « 1000 lignes corrigées » pour une
> exposition passant de 7 777 à 1 000. `EffetAgrege` publie désormais le TOTAL
> avant/après, le pourcentage, et — l'exposition étant un **dénominateur** — le
> facteur sur la prime. ⚠️ **Calculé à la DÉTECTION** : le message qui décide
> est celui du rapport **bloqué**, et un rapport bloqué n'applique rien.
>
> **② Le plan ne déclarait jamais l'unité.** Il porte `unite_exposition`
> (`annee` · `mois` · `jour`), ensemble fermé **dérivé du `Literal`**, valeur
> inconnue qui **LÈVE**. La borne de plausibilité en **dérive** — 1 · 12 · 366 —
> **à la source unique**, donc pour les **deux** chemins d'un seul geste.
>
> ⚠️⚠️ **ET LA CONTRADICTION EST SIGNALÉE, sans quoi le mécanisme serait
> décoratif.** Déclarer `mois` porte la borne à 12 : plus rien ne peut être
> attrapé, et une déclaration FAUSSE passerait pour juste. Une donnée dont le
> maximum ressemble à une autre unité est donc **signalée (règle 3)**, jamais
> corrigée — *un portefeuille d'assistance à contrats courts ressemble
> légitimement à des années : c'est à l'actuaire de trancher.* Le signal se
> dérive **entièrement de l'ensemble fermé** : aucun seuil inventé.
>
> ⚠️ **Unité non déclarée : comportement d'aujourd'hui, mais DIT.** Borne
> annuelle inchangée, et le message publie l'hypothèse et sa conséquence.
> **0 des 20 plans ne déclare d'unité — aucun euro ne bouge, mesuré.**
>
> ⚠️⚠️ **`EMPREINTE_SCHEMA` a bumpé `1` → `2`.** L'unité entre dans le payload :
> elle décide d'un prix, donc elle est **opposable**. *L'en exclure aurait rendu
> `IDENTIQUE` pour deux plans qui tarifent différemment.*
>
> ⚠️ **RESTE OUVERT, ET NOMMÉ** — les étapes 4 et 5 du chantier (conversion
> explicite vers l'année, puis les 20 plans déclarent `annee`) ne sont **pas**
> `qualite/C3` : mesuré le 31/08, un plan déclarant `mois` produit **exactement
> le même tarif** qu'un plan annuel — `k` identique, ratio par contrat
> `min = médiane = max = 1,000000`. *Le décalage constant `log(12)` est absorbé
> par l'intercept, et le coefficient d'équilibre recalibre le niveau.*

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

> ✅ **`qualite/C5`** · **FERMÉ le 01/09/2026.** L'en-tête citait `A1._evaluer_qualite` comme source d'autorité : **une seule occurrence du nom dans tout le dépôt, cette phrase elle-même.** *Un renvoi à une fonction qui n'existe pas envoie le lecteur chercher une autorité qu'il ne trouvera jamais.* `DL-3` **dérive** l'existence du symbole au lieu de la supposer, et tombe dans les deux sens : si la fonction naît un jour, l'en-tête pourra la citer.

```
  _evaluer_qualite : 1 seule occurrence -> core/qualite_donnees.py:25 (cette phrase)
  A1 porte en realite : ['def _valider_qualite']
```

La fonction a été renommée ; la référence ne l'a pas suivie.

**C6 — `resume()` ne porte aucune proportion totale.** Le dict qui part dans
l'`audit_trail` et les rapports publie `lignes_initiales`, `lignes_retenues`, et
une `proportion` **par anomalie** — jamais la part du portefeuille touchée. Sur
le cas de C2, il faut soustraire deux entiers pour découvrir les 19,6 %.

> ✅ **`qualite/C6`** · **FERMÉ le 01/09/2026 — et la calculer par SOMME aurait donné un chiffre FAUX.** `resume()` publie désormais `lignes_touchees`, `proportion_touchee` et `proportion_exclue`. ⚠️⚠️ LA PART EST UNE **UNION**, jamais une somme : mesuré le 01/09 sur un cas où deux anomalies se recouvrent, **somme = 20, union = 15**. *Ne jamais additionner des sources qui se recoupent.* ⚠️ ET L'UNION N'A DE SENS QUE SI LES INDEX SONT COMPARABLES : vérifié PAR AST **avant** de l'écrire — `controler_qualite` ne réaffecte jamais `df`, donc toutes les anomalies vivent dans le référentiel d'entrée. `DL-2` garde cette prémisse : le jour où elle tombe, c'est la proportion qui perd son sens.

```
  cles du resume : ['anomalies_au_dela_seuil','bloque','corrections',
                    'escalade_declenchee','exclusions','horodatage',
                    'lignes_initiales','lignes_retenues','seuil',
                    'signalements','validee_par']
```

**C8 — La règle 1 classe `cout_total_sinistres < 0` comme IMPOSSIBLE MATHÉMATIQUEMENT, et exclut. Une charge NETTE peut légitimement être négative.**

⛔⛔ **CONSTAT NEUF, OUVERT LE 31/08/2026 — RANG 1.** Il ne vient d'aucune
relecture : **il vient d'une mesure sur la seule donnée réelle versionnée**,
`data/PG_2017_CLAIMS_YEAR0.csv` (14 243 sinistres).

```
  AU SINISTRE : 1 263 montants negatifs / 14 243  =  8,9 %
                median -516,32 EUR · total -645 510 EUR · 5,2 % de la charge positive

  AU CONTRAT  : 1 116 / 12 654  =  8,82 %      <- au-dessus du seuil d escalade (5 %)
                nb_sinistres < 0 : 0
```

⚠️ **La doctrine confond deux grandeurs.** L'en-tête du module range `cout < 0`
sous « *IMPOSSIBLE MATHÉMATIQUEMENT* ». Un **coût** (un prix) est ≥ 0 ; une
**charge nette** (paiements − recours) est de **signe quelconque**. Un recours,
un sauvetage, une subrogation la rendent négative — et c'est **normal**.

**Ce que l'exclusion coûte, mesuré :**

```
  charge NETTE (tous)  : 11 724 608 EUR  ->  prime moyenne   926,55 EUR
  charge si on EXCLUT  : 12 288 358 EUR  ->  prime moyenne 1 065,03 EUR
  -> la prime moyenne AUGMENTE de 14,9 %, et 1 116 contrats sont perdus
```

⚠️⚠️ **ET AUCUN INDICE NE PERMET DE TRANCHER AUTOMATIQUEMENT.** Arbitré par
Selasse : *erreurs de saisie ET vrais recours coexistent, le second cas est
rare, ni l'un ni l'autre n'est la règle par défaut.* Mesure des deux
discriminants sur les 1 116 cas :

```
                                        n     part   ratio median
  AVEC paiement positif au contrat      80    7,2%       0,33
  SANS aucun paiement positif        1 036   92,8%       0,52

  parmi les 80 couverts : 44 DEPASSENT le paiement du contrat
  distributions du ratio  couverts     0,02 -> 1,05
                          non couverts 0,00 -> 1,87
```

> ### **Les deux distributions se chevauchent entièrement. Aucun seuil ne les sépare, et les deux groupes se disqualifient mutuellement** — 44 des 80 « couverts » réclament plus que ce qui a été payé ; et **aucun** des 1 036 « non couverts » n'est aberrant, tous bornés sous 1,87 × le sinistre moyen. *Une erreur de saisie produirait une queue : il n'y en a pas.*

⚠️ **Borne déclarée** : le fichier est un extrait « **Year 0** » — **une seule
année, vérifié**. Les paiements auxquels ces recours se rapportent peuvent être
**hors de l'extrait**. Une seule LoB, un seul fichier : **je ne généralise pas.**

> ✅ **`qualite/C8`** · **FERMÉ le 31/08/2026 — RANG 1, arbitré par Selasse.**
> *Preuve : `test_charge_nette_negative.py`, 15 contrôles, 4 violations
> plantées.*
>
> **Les trois gestes, indissociables, sont posés :**
>
> **A — `cout < 0` passe en RÈGLE 3.** Mesuré sur la vraie donnée : **12 654
> contrats retenus, 0 exclusion**, `cout_net_negatif` signalé sur 1 116. ⚠️ **Et
> les vraies impossibilités restent en règle 1** — `frequence_negative` et
> `exposition_non_positive` sont vérifiées par un second sens.
>
> **B — l'annexe de revue** : **1 116 cas**, chacun avec sa **position**, sa
> charge nette et son ratio. ⚠️⚠️ **Deux surfaces, deux audiences** : la synthèse
> signée reste **sans index ni position** (les deux sentinelles RGPD tiennent,
> vérifié) ; l'annexe ne quitte pas le poste de l'actuaire et **ne porte aucun
> identifiant client**.
>
> ⚠️ **ET LA MESURE A RÉFUTÉ MA PREMIÈRE ANNEXE.** J'y avais mis « la somme des
> montants POSITIFS », que j'appelais *le discriminant n° 1*. **Cette couche ne
> la voit pas** — elle reçoit une ligne par CONTRAT. Le substitut testé,
> `nb_sinistres > 0`, est vrai pour **100 %** des cas : il ne sépare rien.
> *Une colonne que le code ne peut pas remplir est le défaut même de cet audit.*
> Retirée — et l'annexe **dit désormais ce qu'elle ne peut pas montrer**.
>
> **C — la question NEUTRE, à trois issues, avec EMPREINTE.** ⚠️⚠️ La
> formulation d'abord envisagée — *« ces cas SEMBLENT ÊTRE des recours
> légitimes »* — **est interdite par la mesure** : les deux distributions se
> chevauchent entièrement et les deux groupes se disqualifient. Le texte dit
> donc ce qu'il sait **et ce qu'il ne sait pas** : « *CE CONTRÔLE NE PEUT PAS
> TRANCHER — il voit le portefeuille agrégé, jamais le détail des sinistres* ».
>
> ⚠️ **L'empreinte `r1:…` reprend la leçon de `PlanTarifaire.empreinte()`** : un
> préfixe de schéma lisible **sans recalcul**. *Sans elle, on saurait QU'il a
> répondu, pas SUR QUOI — et une réponse survivrait à un changement de fichier.*
>
> ⛔⛔ **ET `vulture` A ATTRAPÉ MON PROPRE DÉFAUT** : `question_charges_negatives`
> n'avait **aucun appelant de production** — *la forme exacte de `socle/C2`,
> dans le lot qui ferme ce motif.* Câblée sur `QualiteBloquante`, **le seul
> endroit qui ait du sens** : le blocage est le moment où l'actuaire décide.
>
> ⚠️ **SCEAU — quatre violations plantées, une par geste** : le coût redevient
> règle 1 → **18 contrôles tombent** ; un identifiant client entre dans l'annexe
> → **1** ; la question redevient orientée → **2** ; l'empreinte disparaît →
> **1**.

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
