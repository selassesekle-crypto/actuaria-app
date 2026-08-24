# RELEVÉ — `core/conformite_reglementaire.py`, LES GARDE-FOUS

**Lu intégralement** : `core/conformite_reglementaire.py` **1 318 l**. Aucun
échantillon, aucun filtre. Deuxième fichier du relevé ②.

C'est le fichier le plus chargé d'histoire du module : sept cycles d'audit
(V7 → V14) y ont laissé leur correctif, et il porte quatre garde-fous, deux
listes noires, une liste blanche, un contrôle par l'effet, un objet immuable et
quatre « sources uniques » de texte pour les livrables.

## ① Le compte

**27 affirmations mesurées** — **13 constats** · **14 vérifiées bonnes**.
**1 de mes soupçons réfuté par la mesure** · **1 de mes hypothèses réfutée puis
établie par instruction** · **1 point que je ne tranche pas et vous rends.**

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

### B — Affirme plus que le code ne porte (5)

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

## ③ Ce que je ne tranche pas, et que je vous rends

**Le module accuse une autre direction, et je ne décide pas s'il a raison.**

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

⚠️ **Je ne tranche pas**, et c'est délibéré : la question — une table TH/TF
dans un agent nommé « tarification décès » relève-t-elle de Test-Achats, ou de
l'usage licite de tables sexuées en provisionnement et en évaluation IAS 19 ? —
est un point de méthode actuarielle et réglementaire, pas un point de code.
**Vous m'avez demandé de m'arrêter là.**

⚠️ **Ce que je peux dire sans trancher** : l'exemption que le module s'accorde
pour Vie/Santé est motivée par un **mécanisme** (« ils ne construisent pas de
matrice X »), alors que la règle qu'il invoque porte sur un **critère** (le sexe
comme facteur de prix). L'exemption est donc plus étroite que la règle. Que le
mécanisme soit absent — c'est mesuré et vrai — ne dit rien du critère.

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
