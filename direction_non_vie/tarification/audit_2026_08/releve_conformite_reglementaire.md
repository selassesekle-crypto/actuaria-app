# RELEVÉ — `core/conformite_reglementaire.py`, LES GARDE-FOUS

**Lu intégralement** : `core/conformite_reglementaire.py` **1 318 l**. Aucun
échantillon, aucun filtre. Deuxième fichier du relevé ②.

C'est le fichier le plus chargé d'histoire du module : sept cycles d'audit
(V7 → V14) y ont laissé leur correctif, et il porte quatre garde-fous, deux
listes noires, une liste blanche, un contrôle par l'effet, un objet immuable et
quatre « sources uniques » de texte pour les livrables.

## ① Le compte

**28 affirmations mesurées** — **14 constats** · **14 vérifiées bonnes**.
**1 de mes soupçons réfuté par la mesure** · **1 de mes hypothèses réfutée puis
établie par instruction.**

⚠️ **MIS À JOUR LE 24/08/2026** : le point que j'avais laissé à l'arbitrage en
§③ a été tranché par Selasse — **la direction Vie est hors périmètre**, mais
**un constat en sort et il est du périmètre** : c'est `C14`, ci-dessous.

## ② Le classement

### A — Laisse passer, ou détruit, en disant le contraire (2)

**C1 — `controle_effet_execute = True` alors que le contrôle n'a examiné AUCUNE
colonne.** Le module écrit l.870 : « *Un contrôle dont on ne vérifie pas
l'exécution n'est pas un contrôle* », et il ajoute à `MatriceX` une propriété
dédiée (V14, constat I7) pour que l'actuaire sache si le garde-fou n°4 a tourné.
Mesuré, avec une fuite déclarée par l'actuaire (`zorglub` = la cible + un bruit
de 1e-6, donc elle passe la liste blanche) :

```
  cible presente dans df   controle_effet_execute = True   fuite ecartee = True    avertissement = False
  cible ABSENTE de df      controle_effet_execute = True   fuite ecartee = False   avertissement = False
  cible CONSTANTE          controle_effet_execute = True   fuite ecartee = False   avertissement = False
```

`detecter_fuites_par_effet` **rend `{}` sans un mot** dans deux cas : quand
`col_cible` n'est pas dans `df.columns` (l.1128-1129) et quand la cible est de
variance nulle (l.1133-1135). Or `controle_effet_execute` est calculé
l.862 **avant l'appel**, sur la seule présence des arguments :
`not (df is None or not cibles)`. La propriété atteste donc la fourniture des
arguments, pas l'exécution du contrôle.

> ✅ **`conformite/C1` + `conformite/C7`** ·  **`C1` ET `C7` FERMÉS ENSEMBLE — le couplage est ORIENTÉ.**
> Publier `C7` sans corriger `C1` aurait mis dans le livrable l'attestation
> **fausse** « garde-fou n°4 exécuté » sur une matrice où il n'avait examiné
> aucune colonne. **`C1` a donc été corrigé d'abord, dans le même changement.**
>
> **`C1`** — nouvelle **source unique** `motif_controle_effet_impossible(df,
> col_cible)`, consultée par **les deux** endroits qui divergeaient :
> `detecter_fuites_par_effet` pour ses deux `return {}` muets, et
> `construire_matrice_x` pour calculer la propriété. Elle vaut désormais
> « au moins une cible a réellement été examinée », plus « les arguments ont
> été passés ». Mesuré :
> ```
>   cible presente et variable   execute=True    aucun motif
>   cible ABSENTE du df          execute=False   motif nomme
>   cible CONSTANTE              execute=False   motif nomme
>   df absent                    execute=False   motif nomme
> ```
> ⚠️ **Le motif voyage avec le drapeau** : un booléen dit QUE, jamais POURQUOI.
> Et la couverture **partielle** (une cible sur deux, cas réel d'A3 qui en passe
> deux) est déclarée, pas arrondie au meilleur.
>
> **`C7`** — nouvelle source unique `avertissement_controle_effet`, **à côté de
> `avertissement_walk_forward`**, et le drapeau propagé sur la chaîne qui
> existait déjà et était éprouvée : `MatriceX` → A3/A4/A5 → A6 → l'Excel.
> ⚠️ **L'agrégation d'A6 se fait par le PIRE** : si un seul des trois agents n'a
> pas pu faire tourner le garde-fou, le tarif n'en est pas protégé.
>
> ⚠️⚠️ **ET LA GATE A ATTRAPÉ UNE RÉGRESSION QUE J'AVAIS INTRODUITE.**
> `INV-11c` — *« l'échec du contrôle par l'effet doit LEVER, jamais retourner
> aucune fuite »* — a échoué : ma fonction s'exécutant **avant**
> `detecter_fuites_par_effet`, une exception brute la traversait et changeait
> le type levé. Corrigé : elle lève `EchecControleEffet`, comme l'autre.
> *Une source unique doit honorer le contrat aux DEUX endroits, pas seulement
> là où il était écrit.* **Le test existait ; je ne l'ai pas dupliqué.**
>
> ⚠️ Et mon propre message d'alerte affirmait « appelée SANS df et/ou SANS
> col_cible » alors que les deux étaient fournis — **un en-tête qui contredit
> le motif qu'il porte.** Corrigé, et verrouillé par un contrôle.
>
> ⚠️⚠️ **RÉOUVERT PUIS REFERMÉ LE MÊME JOUR — LE CORRECTIF PORTAIT LE DÉFAUT
> QU'IL CORRIGEAIT.** Une question de Selasse sur l'interaction avec la couche
> qualité l'a trouvé : mon garde testait `float(serie.std()) == 0.0`, et sur
> une colonne **entièrement vide** `std()` vaut **NaN** — or **`NaN == 0.0` est
> FAUX**. Aucun motif n'était produit, `controle_effet_execute` valait `True`,
> **et le classeur qui part au CAC écrivait « exécuté sur toutes les cibles »
> sur une cible qui n'existe pas.** *C'est `qualite/C1` — l'aveuglement au NaN
> — reproduit dans la correction de `conformite/C1`, qui portait précisément
> sur un contrôle qui s'atteste sans avoir rien examiné.*
> **Le garde teste désormais ce qui RESTE** (`.dropna()`), jamais une borne.
>
> ⚠️ **ET LA COUVERTURE PARTIELLE EST DÉCLARÉE, PAS ARRONDIE.** Une cible à
> moitié vide laissait le contrôle tourner sur la moitié des lignes **sans le
> dire**. `reserve_controle_effet` distingue désormais l'**empêchement** (rien
> n'a été examiné → non exécuté) de la **réserve** (il a tourné sur un
> sous-ensemble → PARTIEL). *Ni au pire, ni au mieux.*
>
> ⚠️⚠️ **POURQUOI MES 15 CONTRÔLES NE L'AVAIENT PAS VU : LE TÉMOIN MANQUAIT.**
> Mes fixtures portaient « cible ABSENTE de la table » et « cible CONSTANTE » —
> **jamais « cible PRÉSENTE mais entièrement vide »**. Ce trou précis m'a
> échappé **trois fois dans la même journée**. La fixture porte maintenant les
> **CINQ états** (variable · moitié vide · vide · constante · absente), et un
> test épingle la fixture elle-même pour qu'aucun n'en disparaisse.
>
> Contrôles positifs : `test_controle_effet.py`, **20 tests**, dont
> `POS_Effet_LeCouplageEstVerrouille` qui **lit le classeur produit**.
>
> ⚠️⚠️ **DEUX QUESTIONS DE SELASSE ONT TROUVÉ CE QUI MANQUAIT — le rapport
> AFFIRMAIT deux choses qu'aucun test nommé n'appuyait.**
>
> **① « A6 agrège par le pire » n'était pas mesuré.** Le verdict tient — A3 en
> échec, A4 et A5 sains → `execute=False`, motif conservé. **Mais la mesure a
> trouvé autre chose** : l'agrégat était clé par CIBLE seule, et **deux agents
> en échec sur la MÊME cible s'écrasaient — un motif sur deux disparaissait**,
> sans qu'aucun ne nomme l'agent concerné. Le drapeau restait juste, donc rien
> de faux n'était publié ; **l'actuaire perdait une des deux causes.**
> Corrigé : `agreger_controle_effet` est une **source unique**, clés par
> **(AGENT, CIBLE)**. *Un agrégat qui perd une cause est un agrégat qui masque.*
>
> **② Le couplage n'était montré que dans un sens.** Mesuré par **violation
> plantée** : `C7` débranché seul, `C1` intact → le classeur bascule sur
> « exécuté sur toutes les cibles » et **atteste un contrôle qui n'a rien
> examiné**. **4 contrôles échouent**, dont celui du couplage. Le sens inverse
> est désormais épinglé par `POS_Effet_LeCouplageTientDANS_LES_DEUX_SENS`.
>
> *Les deux tenaient sur le fond ; aucun des deux n'était prouvé. « Mesurer dans
> les deux sens » vaut aussi pour ce que j'écris dans un rapport.*

⚠️ **C'est le motif que ce module a été écrit pour interdire, reproduit dans la
fonction qui l'interdit** : le module nomme lui-même ce défaut deux fois — bug
V6 (l.1223) et BLOQUANT B2 (l.869) — « un résultat indiscernable de *le contrôle
n'a pas tourné* ». Ici la fuite entre dans la matrice X, aucun WARNING n'est
émis, et l'objet livré à l'actuaire déclare le contrôle exécuté.

**C2 — Une variable de TAILLE est écartée comme « la cible déguisée », et le
rapport dit « aucune action ».** Le BLOQUANT B7 (V13) a établi que
l'antériorité est le critère, pas la corrélation — mais le correctif ne protège
que **les noms qui portent un marqueur de passé** (`MARQUEURS_EXPERIENCE_PASSEE`,
l.238). `effectif` et `nb_salaries` sont **déclarés facteurs légitimes**
(l.381) et n'en portent aucun. Or en RC Pro l'effectif joue exactement le rôle
que l'exposition joue en auto — et l'exposition, elle, est exemptée (l.1123).

Mon hypothèse était qu'ils étaient déjà détruits. **La mesure m'a réfuté** : à
4,0 sinistres/an — la flotte que le module cite lui-même l.1180 — le signal
plafonne à **0,7875** contre un seuil de **0,80**. Une marge de 0,0125 ne se
commente pas : je l'ai instruite.

```
    freq/an   spearman   gini_norm   verdict (seuil 0.8)
        1.0     0.5226      0.5660   gardee
        2.0     0.6580      0.6716   gardee
        4.0     0.7906      0.7875   gardee          <-- la flotte citee l.1180
        6.0     0.8392      0.8332   ECARTEE -- « la cible deguisee »
        8.0     0.8718      0.8661   ECARTEE
       12.0     0.9125      0.9076   ECARTEE
       40.0     0.9702      0.9683   ECARTEE
```

`effectif` est une **connaissance parfaite de λ** : aucun bruit du côté de la
variable, tout le bruit est du côté de la cible (Poisson). Son signal ne dépend
donc que de la fréquence, et il franchit le seuil **à partir de ~6
sinistres/an/contrat** — une flotte de VTC, une RC Pro de grande entreprise, un
portefeuille santé collectif. Le motif alors publié est celui de la fuite :
« *cette variable EST la cible déguisée* », et la synthèse conclut
« *Exclusion obligatoire, aucune action.* » **C'est très exactement le texte que
B7 a jugé pire que le silence : une instruction erronée.**

⚠️ **La différence avec B7 n'est pas de nature, elle est de nom** : la
sinistralité passée est protégée parce qu'elle *dit* qu'elle est passée. Une
variable de volume, elle, ne dit rien — et rien ne la protège.

> ⚠️ **TRAITÉ AU LOT 1.3 — ET IL FAUT DIRE EXACTEMENT CE QUI A CHANGÉ.**
> **La variable reste écartée** : le contrôle par l'effet est une mesure, pas
> une opinion, et le laisser passer par défaut rouvrirait la porte aux vraies
> fuites. **Ce qui change, c'est le texte publié.** Il disait
> « *Exclusion obligatoire, aucune action* » — le texte que B7 a jugé **pire
> que le silence**, puisqu'une action existe et qu'il la niait.
> Il dit maintenant que l'exclusion est **MESURÉE et ne distingue pas une
> fuite d'une variable de VOLUME légitime**, que **l'effectif joue en RC Pro le
> rôle que l'exposition joue en auto**, et que si la variable est **connue à la
> souscription**, l'action est de **la déclarer exemptée au plan
> (`anteriorite=True`) et de relancer**.
> ⚠️⚠️ **CE QUI N'A PAS ÉTÉ FAIT, ET POURQUOI** : je n'ai pas exempté les
> variables de volume automatiquement. Il n'existe **aucun critère par le nom**
> qui sépare `effectif` (volume, légitime) d'une vraie fuite — et en inventer un
> serait refaire la faute que ce module documente à chaque page. *C'est
> l'actuaire qui sait si sa variable est connue à la souscription ; le plan est
> l'endroit où il le dit, et il est désormais renvoyé là.*

> ✅ **`conformite/C2`** · **FERMÉ le 29/08/2026 — LE CODE ÉTAIT CORRIGÉ,
> RIEN NE L'ÉPINGLAIT.** *Preuve : `test_exclusions_motif_par_motif.py`,
> 3 contrôles.*
>
> ⚠️⚠️ **LA FEUILLE DE ROUTE LE DISAIT FERMÉ, L'ARCHIVE NE PORTAIT AUCUN BLOC.**
> Deux issues étaient possibles — code jamais corrigé, ou code corrigé jamais
> épinglé. **Mesuré au site : la seconde.** Le texte publié dit « ⚠ ACTION
> REQUISE », que l'exclusion est **MESURÉE** et **ne distingue pas une fuite
> d'une variable de VOLUME légitime**, et il renvoie au PLAN
> (`anteriorite=True`). *C'était le troisième état — celui que la règle de
> fermeture du §④ nomme, et qui compte OUVERT.*
>
> ⚠️⚠️ **SECOND SENS, ET IL EST LE CŒUR DU CONSTAT** : le genre et la dérivée
> de sinistralité gardent « aucune action ». *Un correctif qui alerterait sur
> tout fermerait le constat en détruisant l'information* — c'est précisément
> le signal que `C2` veut rendre lisible.

### B — Affirme plus que le code ne porte (6)

**C3 — La « RÈGLE DE PRINCIPE » ferme le garde-fou n°3 et laisse le n°1
ouvert.** Le module écrit l.228-232 qu'il remplace la liste de noms exacts par
une règle de principe, et nomme les six variables que l'ancienne liste
détruisait. Mesuré :

```
  [BON    ] les 6 de B5 : 6/6 survivent au filtre anti-fuite  (garde-fou 3)
  [CONSTAT] les 6 de B5 : 0/6 passent la LISTE BLANCHE        (garde-fou 1)
```

`charge_sinistres_n1`, `cout_total_sinistres_anterieurs`,
`historique_sinistres_3ans`, `montant_sinistres_anterieurs`,
`nb_sinistres_passes`, `sinistres_anterieurs_5ans` sont **toujours détruites**
sur le chemin non déclaratif — par le garde-fou n°1 au lieu du n°3.
`MARQUEURS_EXPERIENCE_PASSEE` n'est consulté nulle part dans
`est_facteur_autorise`.

⚠️ **Ce que le correctif a réellement obtenu est réel et doit être dit** : le
motif est passé de « *dérivée de sinistralité — exclusion obligatoire, aucune
action* » à « **⚠ ACTION REQUISE** — … déclarez-la et relancez la
tarification ». L'actuaire est désormais invité à réagir. Mais la variable est
toujours hors du modèle, et le texte du module se lit comme si la destruction
avait cessé.

> ✅ **`conformite/C3`** · **FERMÉ — lot 1.3, PAR LA PRÉCISION DU TEXTE, PAS PAR UN ÉLARGISSEMENT.**
> Le commentaire du module inscrit maintenant les deux chiffres côte à côte —
> *garde-fou n°3 : 6/6 survivent · garde-fou n°1 : 0/6 passent* — et dit
> lequel la règle de principe a corrigé.
> ⚠️⚠️ **ET LA MESURE A RECADRÉ LE CONSTAT** : ce n'est **pas** un défaut de
> production. Les six appelants passent tous `plan=`, et sur ce chemin la liste
> blanche **EST le plan signé** : une variable d'expérience passée déclarée
> entre dans la matrice X — mesuré, `exclusions = {}`. Le garde-fou n°1 codé en
> dur ne gouverne que le chemin rétrocompat.
> ⚠️ **JE N'AI PAS ÉLARGI LA LISTE BLANCHE, ET C'EST DÉLIBÉRÉ** : accepter
> « tout ce qui porte un marqueur de passé » y ferait entrer **`prime_anterieure`**
> — la prime précédente, que `core/plan_tarifaire.py` interdit explicitement
> comme facteur. *Le remède n'est pas d'allonger la liste, c'est de déclarer un
> plan.*

**C4 — L'exemption par le plan est SILENCIEUSE, celle par le nom est
signalée.** Deux chemins exemptent du contrôle par l'effet.
`plan.facteurs_anteriorite()` alimente `cols_exemptees` (l.839), et
`detecter_fuites_par_effet` fait `continue` l.1157 : **ni exclusion, ni alerte,
ni log**. Le chemin par le nom, lui, alimente `alertes` et produit un texte de
rapport. Mesuré sur **deux colonnes qui sont la même grandeur** (la cible + 1e-6) :

```
  matrice X : ['age', 'sinistres_anterieurs_3ans', 'score_experience']
  alertes   : {'sinistres_anterieurs_3ans': {'spearman': 0.9945, 'gini_normalise': 1.0}}
  exclusions: []
```

`score_experience`, exempté par le plan signé, **n'apparaît nulle part**. Or le
module fonde l'alerte du chemin par le nom sur un risque qui vaut identiquement
ici : « *un signal aussi fort peut trahir une colonne MAL ÉTIQUETÉE* » (l.1293).
Une liste qui exempte ouvre un trou ; celle-ci n'a rien qui la compense.

**C5 — Six modalités légitimes de one-hot sont détruites par les mots
métriques.** `MOTS_METRIQUES_INTERDITS` (l.424) est testé **en sous-chaîne** sur
le suffixe. Mesuré sur des modalités réelles :

```
  [CONSTAT] garantie_perte_exploitation        autorise=False   LA garantie centrale de la RC Pro
  [CONSTAT] type_garantie_perte_exploitation   autorise=False   idem, via type_garantie
  [CONSTAT] garantie_perte_financiere          autorise=False   garantie RC Pro courante
  [CONSTAT] secteur_activite_imprimerie        autorise=False   'imprimerie' contient 'prime'
  [CONSTAT] secteur_activite_couture           autorise=False   'couture' contient 'cout'
  [CONSTAT] secteur_activite_primeur           autorise=False   'primeur' contient 'prime'
  [bon    ] garantie_incendie                  autorise=True    temoin
  [bon    ] carburant_diesel                   autorise=True    temoin
  [bon    ] garantie_montant_regle             autorise=False   B6 -- doit etre rejete
```

Le garde-fou de B6 fonctionne. Mais **la perte d'exploitation est la garantie
centrale de la RC Pro**, et le module déclare précisément la RC Pro dans sa
liste blanche. L'exclusion est journalisée en « ACTION REQUISE » — donc
visible — mais l'actuaire doit deviner que le motif est un mot dans le nom.

> ✅ **`conformite/C5`** · **FERMÉ — lot 1.3, EN DEUX TEMPS, ET LES DEUX DOIVENT ÊTRE DITS.**
>
> **① Le bug de SOUS-CHAÎNE — 3 des 6 récupérées.** Le test était
> `any(m in suffixe for m in MOTS_METRIQUES_INTERDITS)`. Mesuré :
> ```
>   secteur_activite_imprimerie   'imprimerie' contient 'prime'   -> RECUPEREE
>   secteur_activite_couture      'couture'    contient 'cout'    -> RECUPEREE
>   secteur_activite_primeur      'primeur'    contient 'prime'   -> RECUPEREE
> ```
> Une modalité est faite de **mots** séparés par `_` : on teste les mots.
> ⚠️ **LE SECOND SENS EST VÉRIFIÉ ET C'EST L'OBJET DU LOT** :
> `garantie_montant_regle` (**BLOQUANT B6, Gini 0,0709 → 0,9222**) reste
> détruit, ainsi que `garantie_perte_charge`, `garantie_perte_ratio`,
> `garantie_montant_perte`. *Récupérer un faux positif en rouvrant un vrai
> négatif aurait été pire que le défaut.*
>
> **② `perte_exploitation` et `perte_financiere` — NON récupérées, et j'ai
> mesuré pourquoi je ne le fais pas.** `perte` y est un **mot entier**. Retirer
> `perte` de la liste laisserait passer :
> ```
>   garantie_perte_moyenne    garantie_perte_annuelle    garantie_perte
> ```
> — des **montants**. *Rien dans le nom ne sépare le péril « perte
> d'exploitation » du montant « perte moyenne ».* Et je n'ai pas ajouté de
> liste de garanties normalisées : ce serait la maladie que ce module nomme
> lui-même à chaque page.
> ⚠️⚠️ **CE QUI EST CORRIGÉ À LA PLACE : LE MOTIF, ET C'EST LA LEÇON DE B7.**
> Il disait « *à déclarer dans `FACTEURS_TARIFAIRES_AUTORISES`* » — or
> **`garantie` Y EST DÉJÀ** : suivre l'instruction ne changeait rien.
> **Une instruction qu'on ne peut pas suivre est pire qu'un silence.** Le motif
> dit maintenant que la redéclaration en liste blanche **ne changera RIEN**, et
> renvoie à l'action qui marche : **déclarer la modalité DANS LE PLAN SIGNÉ** —
> mesuré, le chemin déclaratif l'accepte.
>
> **③ Et le tri des motifs devait suivre**, sinon le nouveau texte tombait dans
> « Autres exclusions » et perdait son ACTION REQUISE. Les **quatre** motifs
> sont désormais triés séparément et **exclusivement** — ce qui ferme aussi
> **`C6`**. ⚠️ *Ma première version classait `garantie_perte_exploitation` dans
> DEUX lignes, son motif contenant les mots « liste blanche » : le défaut du
> tri par sous-chaîne, reproduit dans le correctif du tri par sous-chaîne.*
> Contrôles positifs `POS_Conf_C5` (4 tests) et `POS_Conf_C2_C5` (5 tests).

**C6 — Une fuite détectée PAR L'EFFET est présentée comme une dérivée de la
sinistralité, « aucune action ».** `construire_matrice_x` produit **quatre**
motifs distincts ; `synthese_exclusions` n'en connaît que **trois** (sa
docstring l.936 le dit : « Trois motifs »). Le tri se fait par sous-chaîne :
`'fuite' in m.lower()` (l.948) capture aussi bien « dérivée de la sinistralité —
**fuite** de données » que « **FUITE** DÉTECTÉE PAR L'EFFET ». Mesuré :

```
  ✔ 1 colonne(s) exclue(s) comme dérivée(s) de la sinistralité observée (fuite de
  données — inconnues au moment de tarifer un contrat neuf) : zorglub. Exclusion
  obligatoire, aucune action.
```

`zorglub` n'a **rien d'une dérivée de la sinistralité par le nom** — elle a été
écartée sur un critère statistique. Or c'est précisément le seul motif que
l'actuaire peut légitimement contester : B7 l'a prouvé au prix fort, et C2
ci-dessus montre que le cas se reproduit. **Le seul motif discutable est celui
qui est publié comme indiscutable.**

> ✅ **`conformite/C6`** · **FERMÉ le 29/08/2026 — CODE CORRIGÉ AU LOT 1.3,
> MAIS UN TEXTE ÉTAIT RESTÉ FAUX.** *Preuve :
> `test_exclusions_motif_par_motif.py`, 5 contrôles.*
>
> Le tri est **exclusif et ordonné** depuis le lot 1.3 : chaque colonne
> appartient à UN seul motif, le premier qui la reconnaît. La colonne écartée
> **PAR L'EFFET** a sa propre ligne et n'est plus fondue dans « dérivée de la
> sinistralité, aucune action ». Mesuré : **5 motifs → 5 lignes distinctes**,
> et chaque colonne apparaît **exactement une fois**.
>
> ⚠️⚠️ **MAIS LA DOCSTRING ANNONÇAIT ENCORE « TROIS MOTIFS » — et c'était la
> PREUVE CITÉE PAR LE CONSTAT.** Le comportement avait changé, le texte qui
> l'accompagne était resté. *Quand un comportement change, relire le texte,
> pas seulement le code qui l'exécute.* Corrigé : cinq motifs, avec leur
> gravité, et le motif contestable nommé.
>
> ⚠️ **ET MA PREMIÈRE SONDE A ACCUSÉ LE CODE À TORT** : j'avais écrit le motif
> `'FUITE DETECTEE PAR L EFFET'` (sans apostrophe) là où le module teste
> `"PAR L'EFFET"`. La colonne retombait dans « aucune action » et le défaut
> semblait vivant. *Une sonde qui invente un motif mesure sa propre
> invention.* Les fixtures reprennent désormais les motifs **tels que le
> module les écrit**.

> ✅ **`conformite/C7`** · **FERMÉ — lot ②, INDISSOCIABLE DE `C1`.** Voir le bloc sous `C1` : la propriété est propagée `MatriceX` → A3/A4/A5 → A6 → l'Excel, via la nouvelle source unique `avertissement_controle_effet`. ⚠️ **Elle n'a pu être publiée qu'une fois rendue VÉRIDIQUE** — la publier avant aurait attesté un contrôle qui n'avait examiné aucune colonne.
> ⚠️ **Et l'état SAIN est publié lui aussi** (« exécuté sur toutes les cibles ») : sans cela, l'actuaire ne pourrait pas distinguer « tout va bien » de « rien n'a été vérifié » — le défaut même que `C1` décrivait.

**C7 — La propriété `controle_effet_execute` n'atteint aucun livrable.** Elle a
été ajoutée par l'audit V14 (I7) avec la mention explicite « ⚠ À REMONTER DANS
LES RAPPORTS », et la raison est écrite l.761-763 : « *le WARNING existait dans
les logs, mais l'objet n'en portait aucune trace — donc rien n'atteignait
l'actuaire* ». Relevé **par AST** sur 418 fichiers :

```
  .controle_effet_execute   production= 1  tests= 1   ['demos/fremtpl2_demo.py']
```

**Un seul lecteur, et c'est une démo.** Aucun des trois livrables ne la lit. Le
correctif a rendu l'information disponible dans l'objet et s'est arrêté là :
elle n'est ni dans le log (il n'y a pas de WARNING quand la propriété ment,
cf. C1), ni dans le rapport.

**C14 — « POUR TOUTE BRANCHE » : le module énonce une règle universelle et n'en
surveille qu'une.** *(Inscrit le 24/08/2026 sur arbitrage de Selasse.)*

Trois phrases de l'en-tête portent une **portée universelle**, à l'impératif :

```
  l.5-8   « SOURCE UNIQUE, POUR LES TROIS DIRECTIONS. Ce module doit etre
            importe par TOUT agent, de TOUTE direction »
  l.41-43 « Interdit comme critere de tarification en assurance depuis le
            21 decembre 2012, POUR TOUTE BRANCHE »
```

Mesuré par AST sur **418 fichiers** :

```
  direction_non_vie/           13 importateur(s)
  direction_vie_epre/           0
  direction_sante_prevoyance/   0
```

⚠️ **Le module se donne une exemption, et elle est motivée par le MÉCANISME
alors que la règle porte sur le CRITÈRE.** L.30-37 : « *Elles ne sont pas
exposées aujourd'hui parce que leurs agents de tarification sont PARAMÉTRIQUES
(ils ne construisent pas de matrice X)* ». **Ce fait est vrai et je l'ai
vérifié** — 0 estimateur statistique dans les deux directions. Mais l'absence de
matrice X ne dit **rien** de l'usage du critère : c'est une propriété de la
forme du modèle, pas de ses facteurs.

**Ce qui est donc affirmé et non porté** : la phrase « POUR TOUTE BRANCHE »
décrit l'étendue de la **règle CJUE**, et se lit — dans un module qui s'appelle
`conformite_reglementaire` et qui s'annonce « SOURCE UNIQUE POUR LES TROIS
DIRECTIONS » — comme l'étendue de la **surveillance**. Les deux ne coïncident
pas, et rien dans le fichier ne le dit.

⚠️ **Le correctif est une phrase, pas un mécanisme** : borner explicitement la
portée surveillée (« *ce module est appliqué en Non-Vie ; les autres directions
relèvent de la même règle et ne sont pas couvertes ici* »). ⚠️ *Ce que fait la
direction Vie est **hors du périmètre de cet audit** — voir §③.*

*Preuve : `preuves/audit_conformite_ter.py` (P1) et `audit_conformite_quater.py`
(Q2).*

> ✅ **`conformite/C14`** · **FERMÉ le 29/08/2026 — PAR UNE PHRASE, COMME LE
> CONSTAT LE DEMANDAIT.** *Preuve : `test_succes_et_portee.py`, 4 contrôles.*
>
> L'en-tête **borne désormais la portée surveillée** : « *CE QUE CE MODULE
> SURVEILLE AUJOURD'HUI : la direction NON-VIE, elle seule* », suivi du relevé
> par AST et de sa méthode rejouable, et des deux directions nommées comme
> **non couvertes**.
>
> ⚠️ **LE COMPTE A ÉTÉ RE-MESURÉ, PAS RECOPIÉ** : le relevé disait « 418
> fichiers, 13 importateurs Non-Vie ». Mesuré le 29/08 : **446 fichiers**,
> `core` **2** · `demos` **1** · `direction_non_vie` **19** ·
> `direction_vie_epre` **0** · `direction_sante_prevoyance` **0**.
> *Les chiffres avaient vieilli, la conclusion tient.*
>
> ⚠️⚠️ **SECOND SENS, ET IL EST ESSENTIEL** : borner la SURVEILLANCE ne doit
> pas laisser croire que la RÈGLE est bornée. Test-Achats s'applique à toute
> l'assurance ; affaiblir cette phrase serait un **défaut réglementaire**, pas
> un correctif. Un test l'épingle.
> ⚠️⚠️ **ET CE TEST A ÉTÉ CORRIGÉ PAR SA PROPRE VIOLATION PLANTÉE** : il
> cherchait le fragment « POUR TOUTE BRANCHE », présent **deux fois** depuis
> le correctif. En affaiblissant la phrase qui fait autorité, **le filet ne
> tombait pas** — il trouvait l'autre. Il s'attache désormais à la phrase
> entière. *Un relevé par fragment sur-compte.*
> ⚠️ **L'EXEMPTION PAR LE MÉCANISME EST DÉCLARÉE INSUFFISANTE** : « leurs
> agents sont paramétriques » est vrai, et ne couvre rien — l'absence de
> matrice X est une propriété de la FORME du modèle, pas de l'usage du
> critère. ⚠️ **Le compte de 0 hors Non-Vie est re-dérivé par un test** : il
> tombera le jour où la phrase deviendra fausse.

### C — Imprécis, daté, ou non documenté (6)

**C8 — Le motif lu par l'actuaire contient un dictionnaire Python.**

```
  FUITE DÉTECTÉE PAR L'EFFET — corrélation de {'spearman': 0.4563,
  'gini_normalise': 1.0} avec la cible ['nb_sinistres'].
```

L.900 interpole `fuites_effet[c]`, qui est un `dict` depuis l'ajout du Gini
normalisé. Ce texte part dans `MatriceX.exclusions`, lu par **5 fichiers de
production**.

**C9 — La docstring de `detecter_fuites_par_effet` décrit un critère qui n'est
plus le sien.** Elle annonce « *Retourne {colonne: corrélation}* … *dont la
corrélation de Spearman … dépasse `seuil`* » (l.1110-1112). Mesuré :

```
  valeur reellement retournee : {'zorglub': {'spearman': 0.4563, 'gini_normalise': 1.0}}
  critere reellement applique : max(spearman, gini_normalise)
```

Sur ce cas précis, **Spearman vaut 0,4563 — bien en dessous du seuil de 0,80** :
si le critère était celui que la docstring décrit, la fuite passerait. Le corps
du module explique très bien pourquoi (l.1060-1077) ; la docstring n'a pas suivi.

**C10 — Les colonnes non numériques sont invisibles au garde-fou n°4.**
`x = df[c].astype(float)` l.1160, dans un `try/except (TypeError, ValueError)`
qui fait `continue`. Mesuré, avec la cible binarisée en texte :

```
  ecartees : ['zorglub']
  -> 'libelle_gravite' est la cible binarisee, en texte. INVISIBLE au garde-fou n.4.
```

> ✅ **`conformite/C10`** · **FERMÉ le 29/08/2026 — LE SILENCE EST SUPPRIMÉ,
> ET L'AMPLEUR EST DÉCLARÉE SANS ÊTRE GONFLÉE.**
> *Preuve : `test_couverture_garde_fou_effet.py`, 7 contrôles.*
>
> ⚠️⚠️ **LE DÉFAUT CONTREDISAIT LA DOCTRINE ÉCRITE DIX LIGNES PLUS BAS.** Le
> `except` GLOBAL de cette même fonction porte *« ÉCHEC VISIBLE, JAMAIS
> SILENCIEUX »* ; le `except (TypeError, ValueError): continue` interne, lui,
> faisait disparaître une colonne **sans un mot**. Reproduit : la cible
> binarisée en texte est invisible, là où la MÊME information en numérique est
> attrapée à **Spearman 0,988**.
>
> **CORRECTIF** : les colonnes non lisibles sont **collectées et NOMMÉES** dans
> un avertissement qui dit aussi **pourquoi c'est grave** (« une fuite en texte
> y serait INVISIBLE ; seuls les contrôles par le NOM protègent alors »).
> ⚠️ **LE `continue` RESTE** : lever désactiverait le garde-fou pour toutes les
> autres colonnes — le défaut V6 que le `except` global raconte. *Ce qui change
> n'est pas le comportement, c'est le silence.*
>
> ⚠️⚠️ **L'AMPLEUR RÉELLE, MESURÉE À LA DEMANDE DE SELASSE ET NON GONFLÉE.**
> Instrumentation du détecteur sur des runs réels :
>
> ```
>   chemin AGENT       20 appels · 22 features · 0 colonne texte
>   chemin DECLARATIF   2 appels · 23 features · 0 colonne texte
> ```
>
> **Aucun chemin de production n'expose le trou aujourd'hui** : `feature_names`
> vient de `plan.colonnes_produites()` et A2 encode les facteurs déclarés. Le
> défaut est **réel dans la fonction, latent sur les chemins** — même état que
> la fuite Optuna d'A4.
>
> ⛔ **CE QUI N'EST DONC PAS FAIT, ET C'EST UNE BORNE DÉCLARÉE** : l'information
> **ne remonte pas au livrable**. Le canal existe (`controle_effet` → `MatriceX`
> → agents → A6 → `avertissement_controle_effet`) mais l'y brancher toucherait
> **cinq sites** pour publier « 0 colonne sautée » sur chaque rapport, d'un fait
> jamais observé. *La leçon de `conformite/C7` — un WARNING seul n'atteint pas
> l'actuaire — vaut pour un fait QUI SE PRODUIT.* Le jour où il se produira, le
> journal le **nommera** : ce sera le signal d'ouvrir le câblage.
>
> ⚠️ **ET `motifs` N'A PAS ÉTÉ RÉUTILISÉ** : il compte des **CIBLES** non
> examinées (« N/M cible(s) »). Y glisser des colonnes aurait fait mentir son
> propre compte — l'exact défaut d'assiette que cet audit poursuit. Un test
> fige la séparation.
> ⚠️ **SECOND SENS DOUBLE** : la même fuite en numérique reste attrapée, et un
> jeu entièrement numérique ne déclenche **aucun** avertissement.

Le module présente ce garde-fou comme « *le seul qui ne dépende d'aucun nom* ».
Il dépend en revanche du **type**, et ce n'est écrit nulle part.

**C11 — Le WARNING « traçabilité ACPR » du filtre genre ne se déclenche jamais
sur le chemin réel.** `filtrer_genre` journalise « *toute suppression
effective — traçabilité requise pour l'audit ACPR* » (l.113-115). Mais la liste
blanche s'applique **avant** (l.547), et elle a déjà retiré `sexe`. Mesuré sur
un appel complet à `construire_matrice_x` :

```
  [CONSTAT] le log porte 'C-236/09'     : False
  [CONSTAT] le log porte 'data leakage' : False
  [BON    ] le log porte 'LISTE BLANCHE': True
  [BON    ] le log porte "ANTI-FUITE PAR L'EFFET" : True
```

⚠️ **Sans conséquence pour l'actuaire** : `MatriceX.exclusions` porte bien le
motif « genre ou proxy de genre — CJUE C-236/09 », et c'est lui qui atteint les
rapports. La traçabilité existe — pas là où la docstring la place.

**C12 — L'instruction donnée à l'actuaire est fausse sur le chemin
déclaratif.** `synthese_exclusions` conclut « *déclarez-la
(FACTEURS_TARIFAIRES_AUTORISES) et relancez* ». Sur le chemin `plan`, la source
de vérité est `plan.colonnes_produites()` : éditer la constante ne change rien.
Le motif d'exclusion, lui, est correct (« non déclarée dans le plan de
tarification signé ») ; c'est le texte de remédiation qui ne l'est pas.

**C13 — `valeur_mobilier` est déclarée comme dérivée d'A2, et A2 ne la produit
pas.** Elle figure l.391 sous « *Indicateurs DÉRIVÉS générés par A2
(_feature_engineering) — recensés exhaustivement sur le code d'A2* ». Mesuré :
A2 la **lit** (l.631-633, pour construire `valeur_par_m2`) et ne l'écrit jamais.
C'est une colonne source, pas une dérivée. Sans conséquence — elle est
autorisée dans les deux cas.

### D — Vérifié comme BON (14)

| affirmation | mesure |
|---|---|
| le **filtre genre** capture casse, langue, one-hot et proxys | **21 noms présentés → 0 survivant** (`sexe`,`SEXE`,`sexe_M`,`gender`,`civilite_Mme`,`titre_enc`,`prenom`,`is_male`…) |
| aucun facteur légitime n'est détruit par le filtre genre | **0 faux positif sur les 65** facteurs déclarés |
| le **filtre anti-fuite par le nom** | **12 grandeurs de sinistralité observée → 0 survivante**, y compris `MONTANT_SINISTRES` (casse) et `total_sinistres_sante` |
| le module dit lui-même que 11 noms lui échappent | **exact : 11/11 passent encore** (`loss_ratio`, `burning_cost`, `provision_dossier`…) — l'aveu l.328 est juste |
| la **règle de principe** sur l'antériorité (garde-fou 3) | **6/6** des variables de B5 survivent au filtre anti-fuite |
| **B6** — `garantie_montant_regle` | **rejeté**, et les 8 témoins légitimes passent (`carburant_diesel`, `inter_bonus_malus_antecedents_sinistres_n1`, `age_carre`…) |
| **MatriceX** ne se forge pas | instanciation directe → `TypeError` · `MatriceX._JETON` **n'existe plus sur la classe** (V12/I6 tenu) |
| **MatriceX** ne se modifie pas | `mx.features=`, `mx._features=`, `del`, `.append` → **4 `AttributeError`** |
| le **contrôle par l'effet** attrape un nom jamais imaginé | `zorglub_machin` (cible + 1e-6) → **gini_normalisé = 1,0000**, écartée |
| la **séparation** fuites / légitimes | fuites **1,0000** · `bonus_malus` 0,2337 · `age` 0,0795 — seuil 0,80 franc |
| **le plan AUTORISE, il ne DISPENSE pas** | un plan déclarant `sexe`, `civilite_Mme` et `prime_pure` → **les trois restent hors** de la matrice X, motifs exacts |
| le garde-fou n°4 se déclare **non exécuté** quand il manque un argument | `False` dans les 3 cas de manque, `True` avec `df`+cible |
| **« TOUS les livrables l'appellent »** | **3/3** — `rapport_equipe_tarif`, `rapport_modeles_tarif`, `tarif_excel` appellent les **quatre** sources uniques |
| **« jamais dupliqué ni réimplémenté »** | **aucune** réimplémentation locale du filtre — mon soupçon était faux (voir ci-dessous) |

### Mon soupçon réfuté par le dépôt

J'ai relevé par AST un littéral de 5 noms de genre dans
`direction_sante_prevoyance/services/sp_data_builder.py:67` et je l'ai suspecté
d'être **un filtre genre réimplémenté localement** — exactement ce que
l'en-tête interdit l.7-8. **Lecture faite, c'est faux** : c'est une table de
**synonymes de mapping**, qui ne filtre rien et normalise au contraire les
variantes client (`genre`, `gender`, `sex`, `civilite`) vers une colonne
canonique `sexe`. Le contraire d'un filtre.

⚠️ Et la mesure a confirmé la note datée du module (l.30-37), toujours exacte au
24/08/2026 : **0 importateur en Vie, 0 en Santé-Prévoyance**, 13 en Non-Vie. Sa
justification tient aussi — **0 fichier** de ces deux directions n'instancie un
estimateur statistique : leurs agents sont bien paramétriques.

## ③ TRANCHÉ LE 24/08/2026 — HORS PÉRIMÈTRE, ET NOTÉ

> **Arbitrage de Selasse** : *« Les agents de tarification sont A1 à A6 ; A7 est
> le provisionnement. La direction Vie n'a rien à faire dans cet audit — tu l'as
> trouvée en vérifiant qui respecte une règle, pas en auditant ton périmètre.
> À NOTER dans l'archive, pas à traiter. »*

⚠️ **Ce qui suit est donc une NOTE, pas un constat, et rien n'en découle pour ce
chantier.** Ce qui EST du périmètre en a été extrait : c'est `C14` ci-dessus.

⚠️ **Et la manière dont je l'ai trouvé est elle-même à retenir** : je vérifiais
*qui respecte la règle du module*, pas *ce que mon périmètre contient*. Un
balayage qui suit une affirmation sort du périmètre par construction. Le
résultat n'est pas nul — il a produit `C14` — mais il n'autorise pas à traiter
ce qu'il a rencontré en chemin.

**La note.**

Il affirme l.41-43 que le genre est « *interdit comme critère de tarification en
assurance depuis le 21 décembre 2012, **POUR TOUTE BRANCHE*** ». Mesuré :

```
  direction_vie_epre/vie/v1_tarification_deces/agent.py
    l.107   table = 'TH0002' if sexe.upper() == 'H' else 'TF0002'
    l.717   {"label": "Sexe", "valeur": result.get("sexe", "H"), ...}
```

L'agent **sélectionne la table de mortalité par le sexe** et publie « Sexe »
comme ligne de son livrable. `sexe` apparaît aussi dans `v2` (épargne), `v3`
(provisions mathématiques), `v9` (embedded value) et `ep1_ias19`.

⚠️⚠️ **CE FAIT EST NOTÉ, IL N'EST PAS INSTRUIT.** Savoir si une table TH/TF
dans un agent nommé « tarification décès » relève de Test-Achats ou de l'usage
licite des tables sexuées en provisionnement et en évaluation IAS 19 est un
point de méthode actuarielle **et il appartient à la direction Vie**, pas à cet
audit. **Aucun lot de ce chantier ne le portera.**

⚠️ **Il reste consigné ici pour une seule raison** : si quelqu'un ouvre un jour
l'audit de la direction Vie, la mesure existe déjà et n'est pas à refaire.

## ④ Ce que je n'ai pas lu, et ce qui reste ouvert

**Rien n'est resté non lu** dans ce fichier : 1 318 lignes, intégralement.

Deux points **non tranchables ici**, qui relèvent des appelants :

- **La chaîne complète des alertes.** J'ai mesuré que les 3 livrables appellent
  `synthese_alertes_experience`, et que A3/A4/A5 lisent `.alertes`. Je n'ai pas
  vérifié que la valeur **transite** effectivement de l'agent au livrable —
  c'est un relevé d'A3 à A6, déjà couverts par les sept premiers relevés, mais
  sous un autre angle.
- **L'exposition comme prédicteur.** `exposition` et `log_exposition` sont dans
  la liste blanche avec le commentaire « *jamais prédicteur, mais doit traverser
  les filtres* » (l.354). Ce fichier les laisse passer ; savoir si un appelant
  les retire ensuite de la matrice de conception n'est pas mesurable ici.

⚠️ **Une de mes mesures était fausse et je la retire** : mon relevé AST des
colonnes produites par A2 a compté 20 colonnes « détruites par les trois
filtres ». **C'était une erreur de ma part** — mon AST captait tous les
`x['clé'] = …`, y compris les affectations de **dictionnaires de résultat**
(`resultat['timestamp']`, `validation`, `pret_pour_glm`…), qui ne sont pas des
colonnes de DataFrame. Seul `valeur_mobilier` (C13) a été vérifié à la main.

## ⑤ Les preuves

- `preuves/audit_conformite.py` — les 13 mécanismes annoncés, par violation
  plantée (genre, fuite, antériorité, B5, B6, MatriceX, effet, plan, n°4, logs).
- `preuves/audit_conformite_bis.py` — les trous : C1, C3, C4, C5, C6, et la
  traversée des quatre garde-fous par un marqueur de passé.
- `preuves/audit_conformite_ter.py` — le point de bascule de C2, le motif lu par
  l'actuaire, et la propagation **par AST** sur 418 fichiers.
- `preuves/audit_conformite_quater.py` — les livrables, les deux autres
  directions, et la réfutation de mon soupçon sur `sp_data_builder`.

Chacune se relance seule.

---

**Mon appréciation d'ensemble.** Les quatre garde-fous **fonctionnent**, et
plutôt mieux que ce à quoi l'histoire du fichier laissait s'attendre : 21 noms
genrés bloqués sur 21, 12 fuites nominales sur 12, `MatriceX` réellement
inforgeable et immuable, le plan qui autorise sans dispenser, et les trois
livrables qui appellent effectivement les quatre sources uniques. Le module a
gagné ses sept batailles.

⚠️ **Les deux constats graves ont la même forme, et c'est celle que le fichier
combat depuis sept cycles** : un contrôle qui **atteste sans surveiller** (C1 —
la propriété dit « exécuté » quand la fonction n'a rien examiné), et une
exclusion **juste dans son mécanisme, fausse dans son message** (C2 — la
variable de volume écartée comme « cible déguisée », avec « aucune action »).

⚠️ **Et le fichier est, à ma connaissance, celui qui écrit le mieux ses propres
limites.** Il dit que les listes noires ne peuvent pas être exhaustives et
nomme les 11 fuites qui lui échappent — **j'ai vérifié : les 11 échappent
toujours**. Il dit que Python n'offre pas de privé strict et que son jeton rend
le contournement *délibéré*, pas impossible. Cette honnêteté est ce qui rend
C1 et C7 remarquables : **ce sont les deux endroits où il a écrit la règle et
ne l'a pas tenue sur lui-même.**

---

## ⛔⛔ CONSTAT OUVERT LE 31/08/2026 — trouvé par la TRACE de `a5/C8`, pas par une relecture

**C15 — `construire_matrice_x` surveille l'INTERSECTION, jamais l'ABSENCE : un
facteur DÉCLARÉ AU PLAN mangé en amont disparaît sans un mot.**

A3, A4 et A5 construisent leurs features en prenant *tout le dataframe SAUF*
une liste noire statique (`COLS_A_EXCLURE`, `COLS_CONTAMINEES`), **puis**
croisent le résultat avec la liste blanche du plan. La liste blanche ne voit
donc que ce qui a survécu au filtre — *ce qui a été retiré avant elle lui est
invisible.*

**Violation plantée le 31/08**, plan `auto`, 23 colonnes produites :

```
  temoin  (23 colonnes) -> 23 retenues | exclusions 0 | alertes 0
  amputee (22 colonnes) -> 22 retenues | exclusions 0 | alertes 0   <-- RIEN
```

⚠️⚠️ **C'est `plan/C3` rouvert un étage plus bas.** Ce constat-là disait
« *un `type` mal orthographié détruit un facteur en silence* » et il a été
fermé **au niveau du plan** : la porte lève désormais sur toute clé inconnue.
Mais un facteur parfaitement déclaré peut encore être écarté sans un mot **plus
loin dans la chaîne**, par une liste noire qui ne sait rien du plan.

### ⚠️ AMPLEUR MESURÉE, NON GONFLÉE — le défaut est LATENT, pas actif

| mesure | résultat |
|---|---|
| plans dont un facteur figure dans la liste noire | **0 / 20** |
| `COLS_CONTAMINEES` : mots génériques ? | **non** — `log_cout`, `log_prime`, `cout_moyen_attendu`, `lambda_freq`, `prime_pure_obs` |
| donnée réelle versionnée portant une colonne noire | **aucune** |

*La sous-chaîne est donc bien moins dangereuse ici que dans `conformite/C3`,
où les mots étaient génériques (`prime` attrapait `imprimerie`).*

### ⚠️⚠️ UN TÉMOIN MONTE LA GARDE EN ATTENDANT LE CORRECTIF

`TRI-7` (`test_tri_a5_charts_services.py`) vérifie **à chaque gate** qu'aucun
des 20 plans ne déclare une colonne que la liste noire mangerait. *Il ne répare
rien — il empêche le défaut latent de devenir actif sans qu'on le sache.*

### CE QUE LE CORRECTIF DEMANDERAIT — non fait, non arbitré

Faire dire à `construire_matrice_x` ce qu'elle **attendait et n'a pas reçu** :
comparer `plan.colonnes_produites()` aux colonnes qui lui parviennent, et
publier l'écart comme une exclusion nommée. ⚠️ **Cela touche les trois agents
A3/A4/A5 et une surface signée** : c'est un lot à part entière, de la famille de
l'étape 4 d'`unite_exposition`. **Rien ne bougera sans arbitrage.**
