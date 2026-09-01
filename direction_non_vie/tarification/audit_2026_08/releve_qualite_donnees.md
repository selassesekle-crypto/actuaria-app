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

⚠️ **Portée** : latent tant qu'aucun plan ne déclarait l'identifiant (**0/20 au 30/08 ;
**20/20 au 01/09**) —
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
> **0 des 20 plans ne déclarait d'unité AU 31/08 — aucun euro n'a bougé,
> mesuré.** ⚠️⚠️ **Au 01/09 ils la déclarent TOUS (`annee`, étape 5) :
> toujours aucun euro, mais la règle 3 est VIVANTE.** *La phrase avait survécu
> quatre jours à sa propre mesure ; `PM-1` la dérive désormais des plans réels.*
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

**C9 — `synthese_qualite_donnees` rend `None` quand la couche N'A PAS
TOURNÉ comme quand elle a tourné SANS RIEN TROUVER : le livrable ne distingue
pas << pas vérifié >> de << vérifié, rien à signaler >>.**

> ✅ **`qualite/C9`** · **CONSTAT NEUF, OUVERT ET FERMÉ le 01/09/2026 —
> arbitré par Selasse.** Il ne vient d'aucune relecture : il vient de la
> **vérification chiffrée** que Selasse a demandée sur son propre résumé du
> sujet.
>
> ```
>   10 000 contrats, 600 a frequence negative (6 %), chemin AGENT :
>      A1 DETECTE      aberrants = {'nb_sinistres_negatifs': 600}
>      A1 ESCALADE     score 100,00 -> 99,25   statut VERT -> ROUGE
>      A1 N AGIT PAS   10 000 lignes entrent, 10 000 sortent, les 600 restent
>      controler_qualite / preambule_qualite : appeles par AUCUN des deux
>                                              modules du chemin agent (AST)
>      synthese_qualite_donnees(None) = None  <- IDENTIQUE a un portefeuille sain
> ```
>
> ⚠️⚠️ **LE SILENCE PAR DÉFAUT N'ÉTAIT PAS UNE ABSENCE D'INFORMATION, C'ÉTAIT
> UNE AFFIRMATION — ET ELLE ÉTAIT FAUSSE.** Un actuaire qui lit une section
> qualité vide comprend << la couche a regardé et n'a rien trouvé >>. Sur le
> chemin agent, elle n'avait rien regardé du tout.
>
> **Quatre surfaces de production, TROIS traitements différents** — relevées
> par AST avant tout code :
>
> | surface | ce qu'elle faisait du `None` |
> |---|---|
> | `services/tarif_excel.py` | ligne **absente** de l'Excel A6 |
> | `services/rapport_equipe_tarif.py` | ligne **absente** de l'Excel équipe |
> | `rapport_modeles_tarif` (Word + HTML) | **bloc absent du rapport SIGNÉ** |
> | `rapport_modeles_tarif` (prompt LLM) | « *Aucun traitement de qualité de données à signaler (ou couche non exécutée sur ce chemin)* » |
>
> ⚠️ **La dernière ligne est le défaut ÉCRIT EN TOUTES LETTRES** : la
> parenthèse offrait les deux lectures dans une seule phrase. *Une phrase qui
> offre deux lectures n'en affirme aucune — et celui qui signe ne peut pas
> savoir laquelle il signe.*
>
> **Le correctif** : `synthese_qualite_donnees(None)` rend désormais
> `PHRASE_QUALITE_NON_EXECUTEE`, et `None` ne subsiste QUE pour le silence
> légitime. C'est le patron d'`avertissement_fuite_par_effet`, déjà en
> service : *un contrôle qui n'a pas eu lieu le dit ; un contrôle qui n'a rien
> trouvé se tait.*
>
> ⚠️⚠️ **ET LE BADGE ÉTAIT LA MOITIÉ DU CORRECTIF.** Les deux Excel dérivent
> leur pastille du TEXTE (`"EXCLUE" in ...`). La phrase « non exécuté » ne
> contient aucun de ces trois mots : **elle serait sortie en VERT**. *Publier
> « rien n'a été vérifié » sous une pastille verte aurait été pire que le
> silence corrigé* — le correctif à côté de la surface signée, le motif que
> cet audit poursuit. Le marqueur est une **source unique** importée, jamais un
> littéral recopié (`QNE-5`).
>
> ⚠️ **AUCUN EURO, ET C'EST `QNE-8` QUI LE PROUVE** :
> `synthese_qualite_donnees` n'appelle rien qui touche aux données (vérifié par
> AST sur son corps, docstring exclue), et le badge Excel est une couleur de
> cellule sans effet sur le statut RAG. **2 000 lignes avant, 2 000 après.**
>
> Épinglé par `QNE-1` à `QNE-8`, dont **`QNE-3` sur le rapport SIGNÉ** (exigé
> par Selasse : bloc présent et nommant l'absence de contrôle quand la couche
> n'a pas tourné, bloc ABSENT sur un portefeuille sain) et **`QNE-7`, le second
> sens** — *un correctif qui ferait parler la couche dans les DEUX cas serait
> aussi faux que le silence.*

**C10 — Le commentaire de la règle 2 affirme « Aucun des 20 plans ne
déclare d'unité » pour justifier « aucun euro » : c'est faux depuis l'étape 5
du même chantier, et rien ne le mesurait.**

> ✅ **`qualite/C10`** · **CONSTAT NEUF, OUVERT ET FERMÉ le 01/09/2026 —
> étape ① du chantier 1-B, décidée par Selasse.** Je l'avais signalé moi-même
> en vérifiant son résumé ; il a demandé de le refermer avant d'avancer.
>
> ```
>   core/qualite_donnees.py, regle 2 -- ecrit a l ETAPE 2 du chantier :
>       << Aucun des 20 plans ne declare d unite, donc aucun euro ne bouge
>          sur l existant -- mesure >>
>
>   RE-MESURE DU 01/09, sur les 20 fichiers de plan :
>       unite_exposition    20 / 20   (toutes 'annee')   <- l ETAPE 5
>       identifiant_contrat 20 / 20
>       echeance            20 / 20
>       cout_par_sinistre    0 / 20   cha* 0 / 20   bornes 0 / 20
> ```
>
> ⚠️⚠️ **LA CONCLUSION TENAIT, LA JUSTIFICATION NON.**
> `borne_exposition('annee')` vaut 1,0, exactement `PLAFOND_EXPOSITION` :
> **aucun euro n'a jamais bougé.** Mais la phrase qui le justifiait était morte
> depuis quatre jours. *Une conclusion juste tenue par une prémisse fausse est
> une dette, pas une garantie* — et `PM-2` prouve désormais le zéro euro **par
> la borne**, plus par le compte de plans.
>
> ⚠️ **ET LA CONSÉQUENCE N'ÉTAIT PAS QUE TEXTUELLE** : puisque l'unité EST
> déclarée, la **règle 3 est VIVANTE en production**, ce que le commentaire ne
> disait nulle part. Mesuré : **une seule ligne à 1,02 an sur 20 000 produit un
> signal sur 100 % des lignes**, donc une escalade, donc un blocage à
> signature. C'est l'objet de l'étape ②.
>
> **SECOND DÉFAUT DE LA MÊME FAMILLE, TROUVÉ EN TRAÇANT.** La feuille de route
> affirmait que le chemin agent tarifie sur **60 lignes** à fréquence ou coût
> négatifs. `qualite/C8`, fermé le 31/08 **après** cette mesure, a sorti le
> coût de la règle 1 : il est SIGNALÉ et GARDÉ par les DEUX chemins.
>
> ```
>   RE-MESURE, fichier identique (1 000 lignes, 30 + 30 + 30) :
>     couche qualite : 60 EXCLUSIONS + 30 SIGNALEMENTS (cout net, gardes)
>                      escalade par l UNION 90/1000 = 9 %  (aucun type >= 5 %)
>     chemin agent   : A1 1000 -> 1000 (il n exclut RIEN)
>                      A2 1000 ->  970 (les 30 d exposition)
>     DELTA REEL DE 1-B :  30 lignes, pas 60
> ```
>
> ⚠️⚠️ **LE REMÈDE N'EST PAS DE RÉÉCRIRE LA PHRASE.** Le patron existait déjà
> deux fois dans le dépôt — `A3-8` et `A4-3` re-vérifient leur mesure à chaque
> gate *« au lieu de recopier cette mesure »*. Ici, rien ne le faisait.
> `PM-1` à `PM-4` dérivent désormais les quatre affirmations des **fichiers de
> plan réels** et du **comportement exécuté**.
>
> ⚠️ **DEUX NATURES DE PHRASE, ET SEULE LA SECONDE ÉTAIT FAUSSE** : une phrase
> HISTORIQUE (vraie à sa date) se **date** ; une phrase VIVANTE se
> **re-mesure**. Les trois historiques ont reçu leur date, les deux vivantes
> ont été corrigées. `PM-4` interdit la forme qui affirme au présent **et
> autorise la forme datée** — second sens prouvé au sceau : *un remède qui
> interdirait de tracer l'histoire du défaut détruirait la trace qu'il existe
> pour garder.*
>
> ⚠️ **AUCUN EURO** : aucune ligne de code exécutable n'a changé dans ce lot —
> seuls des commentaires, des documents et un fichier de contrôles neuf.
> Vérifié par AST : **0 corps de fonction modifié**.
>
> ⛔ **NOMMÉ, NON TRAITÉ** : quatre affirmations voisines de la même forme
> restent non dérivées — `a2/agent.py` (encodages, colonne `a2/C13`,
> `auto_fr_reel`) et `pipeline_agents.py` (« 19 des 20 plans »). Elles sont
> hors de la zone de ce lot ; les nommer vaut mieux que de les élargir.

**C11 — `unite_exposition_contredite` sort avec un masque TOTAL
(`np.ones(len(df))`) : une seule ligne d'arrondi fait escalader le signal à
100 % et BLOQUE le fichier entier.**

> ✅ **`qualite/C11`** · **CONSTAT NEUF, OUVERT ET FERMÉ le 01/09/2026 —
> étape ② du chantier 1-B, décidée par Selasse.**
>
> ```
>   20 000 contrats, UNE SEULE ligne a 1,02 an  =  0,0050 %
>     AVANT : signal 20 000 l. = 100,0000 %  ->  escalade  ->  BLOQUE
>     APRES : signal      1 l. =   0,0050 %  ->  signale, rien de bloque
> ```
>
> *Une ligne d'arrondi refusait le tarif de vingt mille contrats, et elle le
> refusait par l'IMPRÉCISION DU SIGNAL, pas par la gravité du fait.*
>
> ⚠️⚠️ **L'ASSIETTE EST ASYMÉTRIQUE, ET C'EST LA CONCEPTION.** La
> contradiction se lit dans DEUX sens, et **la preuve n'a pas la même forme** :
>
> | sens | exemple | ce qui est la preuve | escalade |
> |---|---|---|---|
> | donnée **trop grande** | `annee` déclarée, max 1,02 | les lignes au-dessus de la borne, **et elles seules** | non, si elles sont rares |
> | donnée **trop petite** | `mois` déclarée, max 0,9 | **TOUTES** — aucune ne dépasse 12, et c'est précisément ça | oui |
>
> ⛔⛔ **RESTREINDRE LES DEUX SENS AURAIT DÉTRUIT LA SECONDE MOITIÉ EN
> SILENCE** : `_ajouter` ignore un masque vide, donc une déclaration `mois`
> fausse serait redevenue **muette** — exactement le décor que `UX-12` existe
> pour empêcher, et il l'exige bloquant. *Le correctif du sens évident aurait
> emporté le sens que personne ne regardait.* `MP-3` tient cette moitié, et le
> sceau la plante.
>
> ⚠️ **ET `MP-4` EMPÊCHE QUE `MP-1` NE DEVIENNE UNE PASSOIRE** : une donnée
> réellement mensuelle sous un plan `annee` désigne **19 985 à 20 000 lignes
> sur 20 000** et bloque toujours. *Sinon le correctif aurait échangé un faux
> blocage contre un vrai silence.*
>
> ⚠️⚠️ **AUCUN EURO, PROUVÉ DEUX FOIS** (`MP-5`) :
> ① la règle 3 n'écrit nulle part — vérifié par AST sur les **cibles**
> d'affectation ; *mon premier contrôle lisait `df[col]` en LECTURE et le
> comptait comme une écriture : refait sur `ast.Assign.targets`* ;
> ② le dataframe produit **sans signature** après le correctif est identique
> **ligne à ligne** à celui produit **avec signature** — 20 000 lignes,
> exposition totale 20 000,0000, la ligne à 1,02 toujours plafonnée à 1,0 par
> la règle 2.
>
> *Ce que ce correctif retire est une SIGNATURE, pas une correction.* Aucun
> prix ne change sur une ligne déjà tarifée ; un calcul qui était REFUSÉ
> aboutit, et il aboutit exactement au résultat que la signature donnait.
>
> Épinglé par `MP-1` à `MP-7`, dont `MP-2` (le masque nomme les BONNES lignes
> — *un compte juste sur les mauvaises lignes reste faux*), `MP-6` (second
> sens, dans les deux directions) et `MP-7` (le texte publié DIT sur quelle
> assiette il porte — *passer de 20 000 à 1 sans le dire laisserait croire à
> une perte de détection*).

**C12 — Le chemin agent n'a AUCUN canal de signature qualité : le
geste qui existe sur le chemin déclaratif (`qualite_validee_par`) n'a pas de
jumeau, et rien ne dit pourquoi.**

> ✅ **`qualite/C12`** · **CONSTAT NEUF, OUVERT ET FERMÉ le 01/09/2026 —
> étape ③ du chantier 1-B, décidée par Selasse.**
>
> `pipeline_agents` portait déjà **deux** canaux de signature nominative
> (`profil_valide_par`, `valide_par_actuaire_dl`) : la convention existait,
> celui de la qualité manquait. *L'asymétrie entre voisins, encore.*
>
> ⚠️⚠️ **ET C'EST LA CONCEPTION QUI ÉTAIT LE SUJET, PAS LE PARAMÈTRE.** Un
> canal accepté que **rien ne consomme** est exactement la silhouette de
> `socle/C2` — de la plomberie posée que rien n'alimente. **Pire ici
> qu'ailleurs**, parce qu'il porte un NOM D'ACTUAIRE :
>
> > *Un canal qui avale une signature sans rien valider laisse croire à une
> > validation qui n'a pas eu lieu.*
>
> Le canal existe donc — typé, documenté, **au même nom et au même sens** que
> sur le chemin déclaratif — et il **REFUSE** (`SignatureSansObjet`), en
> nommant la cause (`qualite/C4`), l'étape qui lui donnera un objet (1-B,
> étape ⑤) et **où aller aujourd'hui** (`pipeline_complet`, qui porte la
> couche). *Un refus qui ne dit pas où aller transforme un garde-fou en mur.*
>
> ⚠️ **POURQUOI IL N'A PAS ENCORE D'OBJET — MESURÉ, PAS SUPPOSÉ.** Le chemin
> agent n'appelle pas `controler_qualite`, et A1 **score sans agir** : 600
> fréquences négatives sur 10 000 le font virer au ROUGE et **les 10 000
> lignes ressortent**. Il n'y a donc aucun blocage à lever.
>
> ⚠️ **SOURCE UNIQUE** : les deux entrées partagent
> `exiger_canal_sans_objet` — *deux messages divergents auraient donné deux
> doctrines*. `SG-4` vérifie **par AST** qu'aucune ne recopie la levée.
>
> ⚠️ **AUCUN EURO** (`SG-5`) : le paramètre vaut `None` par défaut et le run
> est identique **ligne à ligne**, score inchangé, avec et sans lui. *Le canal
> ne gêne personne tant qu'on ne lui demande rien.*
>
> ⛔ **ET LE SECOND SENS EST INDISPENSABLE** (`SG-7`) : un garde-fou qui
> refuserait la signature PARTOUT aurait cassé le seul chemin où elle a un
> objet. *Le refus porte sur le chemin agent, pas sur le geste.* Le sceau le
> plante : déplacer le refus dans `controler_qualite` fait tomber `SG-7`.
>
> ⚠️ **`SG-6` A ATTRAPÉ MA PROPRE OMISSION** : la docstring d'`A1.run` disait
> « en nommant l'étape qui lui donnera un objet » **sans jamais la nommer**.
> *Une phrase qui annonce qu'elle va dire quelque chose n'est pas cette
> chose.* Corrigée avant la gate.
>
> Épinglé par `SG-1` à `SG-7`. **L'étape ⑤ remplace le refus par l'appel
> réel** — et elle déplace un prix, donc elle attend un arbitrage nominatif.

**C13 — Le chemin agent ne MESURE pas ce que la couche qualité ferait :
la décision de la brancher (1-B) se prendrait sans chiffre, et le troisième
état — PARTIELLEMENT exécuté — se lit comme un contrôle complet.**

> ✅ **`qualite/C13`** · **CONSTAT NEUF, OUVERT ET FERMÉ le 02/09/2026 —
> étape ④ du chantier 1-B (1-B-observation), décidée par Selasse.**
>
> *Une décision qui déplace un prix se prend sur des fréquences réelles, pas
> sur une intuition.* La couche applique désormais ses règles **pour voir**, et
> n'applique **rien** : aucune ligne exclue, corrigée, ni bloquée.
>
> ⚠️⚠️ **L'ASSIETTE ÉTAIT TOUT LE SUJET, ET LA MESURE L'A TRANCHÉE.**
>
> ```
>   fichier : 30 expositions nulles + 60 frequences negatives
>     observee AVANT A2 : exposition_non_positive 30 + frequence_negative 60
>     observee APRES A2 :                              frequence_negative 60
> ```
>
> A2 exclut **déjà** les expositions non positives. Observer avant lui aurait
> fait publier « 30 lignes, et RIEN n'a été appliqué » sur des lignes que le
> tarif ne porte plus. *Un chiffre juste sur la mauvaise assiette dit une
> chose fausse.* L'observation mesure **ce qui atteint le tarif** et que la
> couche complète aurait écarté — c'est le chiffre de l'arbitrage ⑤.
>
> ⚠️⚠️ **LE DÉFAUT DE `qualite/C9` A REPARU UN CRAN PLUS HAUT, DANS MON PROPRE
> CORRECTIF.** Ma première version rendait `PHRASE_QUALITE_NON_EXECUTEE` dès
> que l'observation ne trouvait rien — c'est-à-dire **sur un portefeuille
> sain**. « Observé, rien trouvé » redisait « pas observé ». *C'est
> l'EXISTENCE de l'observation qui prouve que la couche a tourné, jamais son
> contenu.* `OB-7` tient la distinction.
>
> ⚠️ **LE TROISIÈME ÉTAT, NOMMÉ : PARTIELLEMENT EXÉCUTÉ.** A2 excluait les
> expositions non positives et le publiait **seul** — un actuaire y lisait que
> la couche entière avait tourné. Les deux textes se publient désormais côte à
> côte (`OB-6`), et ils ne disent pas la même chose : **ce qui a ÉTÉ FAIT**,
> puis **ce qui AURAIT été fait**.
>
> ⚠️ **CE QUE LE TEXTE PUBLIE, ET POURQUOI** : par anomalie, le code, la
> règle, le nombre de lignes, la proportion, **et si elle aurait déclenché
> l'escalade**. *La liste des alertes qui doivent bloquer se décide sur des
> fréquences réelles* — c'est la matière de l'arbitrage de Selasse.
>
> ⚠️ **UN JETON, PAS UN NOM** : `controler_qualite` refuse un rapport complet
> sans signature dès que l'escalade se déclenche. L'observation fournit un
> jeton TECHNIQUE, puis le retire (`validee_par=None`). *Un jeton qui
> ressemblerait à un nom finirait par être lu comme une validation* (`OB-3`).
>
> ⚠️⚠️ **AUCUN EURO, PROUVÉ PAR LA STRUCTURE** (`OB-1`, `OB-8`) : le
> dataframe donné à l'observation est **inchangé**, `dataframe_propre` vaut
> `None` pour qu'aucun appelant ne s'y trompe, et l'orchestrateur ne relit
> jamais l'observation — **1 lecture, 0 attribut lu**, vérifié par AST.
>
> ⛔⛔ **ET LE SCEAU A DÉMASQUÉ UN DE MES PROPRES CONTRÔLES.** `OB-4`, qui
> garde l'assiette, lisait l'APPEL `observer_qualite(_df_obs, ...)` puis y
> remplaçait `_df_obs` par `r2` avant d'y chercher `r2` : **il était vrai quoi
> qu'il arrive**, y compris sur `r1`. *Un contrôle qui regarde le NOM d'une
> variable au lieu de sa SOURCE ne mesure rien.* Refait sur l'AFFECTATION ; le
> plant le fait désormais tomber.
>
> Épinglé par `OB-1` à `OB-11`. **L'étape ⑤ — appliquer — déplace un prix et
> attend l'arbitrage de Selasse, y compris LA LISTE des alertes qui doivent
> bloquer.**

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
