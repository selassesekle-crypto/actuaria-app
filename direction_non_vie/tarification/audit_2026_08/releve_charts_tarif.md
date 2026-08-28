# RELEVÉ — `core/charts_tarif.py`, LES FIGURES PUBLIÉES

**Lu intégralement** : `core/charts_tarif.py` **476 l**. Aucun échantillon,
aucun filtre. Quatrième fichier du relevé ②.

Une figure signée par un actuaire est un livrable comme un autre. On mesure ce
qu'elle affiche, **ce qu'elle tait**, et si ses seuils sont ceux du reste du
système.

## ① Le compte

**21 affirmations mesurées** — **10 constats** · **11 vérifiées bonnes**.

⚠️ **MIS À JOUR LE 24/08/2026 (soir)** : `C9` et `C10` ajoutés — deux défauts
de **lisibilité** trouvés en rendant les deux chartes côte à côte. Voir plus bas.
**1 de mes mesures fausse et corrigée** (un import sous alias).

## ② Le classement

### A — Publie un nombre ou une image trompeuse (3)

**C1 — Le badge « % du discriminable » n'a aucune borne.** L'expression
l.269-270 est `100 * mod / obs`, gardée par le seul `obs > 0`. Mesuré :

```
  cas nominal      obs=0,8320  mod=0,1780  -> « soit 21 % du discriminable »
  modele > plafond obs=0,2000  mod=0,2500  -> « soit 125 % du discriminable »
  modele NEGATIF   obs=0,2000  mod=-0,0105 -> « soit -5 % du discriminable »
  plafond ~ nul    obs=1e-6    mod=0,1800  -> « soit 18000000 % du discriminable »
```

⚠️ **Le cas à 125 % n'est pas théorique — la docstring elle-même explique
pourquoi il arrive** : « *le plafond est calculé sur le portefeuille entier, le
Gini du modèle sur la seule base de test* ». Deux assiettes différentes peuvent
donc s'inverser. Et le cas négatif est celui que le module de conformité
documente noir sur blanc (BLOQUANT B7 : « *GLM réellement livré : Gini
−0,0105* »).

> ✅ **`charts/C1`** · **FERMÉ le 28/08/2026.** Le badge ne publie une part que
> si c'en est une. **Une seule condition couvre les trois cas mesurés, et elle
> n'invente AUCUN seuil** : le rapport n'est une part que si `0 <= mod <= obs`.
> ⚠️⚠️ **ON N'ÉCRÊTE PAS À [0, 100], ET C'EST LA LEÇON DU LOT F1 D'A7** : juger
> une valeur écrêtée est une tautologie, et l'écrêtement **cache** la
> divergence au lieu de la dire. Le 125 % n'était pas une aberration de calcul
> — le relevé le disait déjà : *« le plafond est calculé sur le portefeuille
> entier, le Gini du modèle sur la seule base de test »*. **Deux assiettes.**
> ⚠️ **REJOUÉ** : 21 % publié · 125 %, −5 % et 18 000 000 % remplacés par un
> motif qui NOMME la cause.
> ⚠️⚠️ **ET LES TROIS CAS DONNENT DEUX MOTIFS, PAS TROIS — c'est une décision.**
> `obs = 1e-6, mod = 0,18` tombe dans « dépasse le plafond », et c'est exact
> (`0,18 > 1e-6`). Distinguer « plafond dégénéré » exigerait un **seuil sur ce
> qu'est un plafond trop petit** : *un seuil fabriqué serait le défaut même que
> cet audit poursuit.* Un test fige cette décision pour qu'on ne la « corrige »
> pas par accident.
> **Épinglé par `test_bandes_et_badge.py`, 4 contrôles**, dont un SECOND SENS
> en premier : le cas nominal publie toujours sa part — *un correctif qui
> éteindrait le badge fermerait le constat en détruisant l'information.*

**C2 — La bande verte de la figure est PLUS LARGE que la tolérance du gate.**
Trois bandes coexistent dans le même système :

| source | bande |
|---|---|
| `chart_walkforward_ae` — rectangle vert (l.354) | **0,85 – 1,15** |
| `chart_walkforward_ae` — point VERT (l.347) | 0,95 – 1,05 |
| `avertissement_walk_forward` — « bande acceptable » | **0,90 – 1,10** |

Mesuré, en confrontant la figure au gate :

```
  A/E=0.87  figure: point ROUGE, DANS la bande verte   | gate: AVERTIT
  A/E=0.92  figure: point AMBRE, DANS la bande verte   | gate: silence
  A/E=1.00  figure: point VERT , DANS la bande verte   | gate: silence
  A/E=1.13  figure: point ROUGE, DANS la bande verte   | gate: AVERTIT
```

À A/E = 0,87 le rapport publie « **⚠ BIAIS DE TARIFICATION** — hors de la bande
acceptable [0,90 ; 1,10] » **et** une figure où le point tombe à l'intérieur du
rectangle que le docstring appelle « bande d'acceptabilité ». ⚠️ *La couleur du
point, elle, est juste* — c'est le rectangle qui dit autre chose que le texte.

> ✅ **`charts/C2`** · **FERMÉ le 28/08/2026.** La figure **ne possède plus
> aucun seuil** : elle REÇOIT les deux bandes de qui décide
> (`AE_FENETRE_ACCEPTABLE`, `AE_FENETRE_STRICTE` dans
> `core/conformite_reglementaire`). Rectangle dessiné mesuré : **(0,90 ; 1,10)
> = la bande de la règle**. Le cas du relevé, **A/E = 0,87**, sort désormais du
> rectangle ET est peint en ROUGE.
> ⚠️ **LE REMÈDE N'EST PAS DE RECOPIER LE BON NOMBRE** : une copie correcte
> aujourd'hui diverge au premier ajustement — exactement les 30 définitions
> locales de couleurs avant `STATUT_RAG`. Les bandes sont **requises**, sans
> défaut : *« présent mais VIDE » a déjà mordu trois fois dans cet audit.*
> ⚠️ **ET LE MODULE RESTE PUR.** Les bornes arrivent en PARAMÈTRE plutôt que par
> un import : la dépendance irait dans le bon sens (la présentation lit la
> règle), mais elle rendrait **fausse** la phrase d'en-tête qui promet que
> `charts_tarif` ne dépend que de plotly et numpy.
> ⚠️⚠️ **UN HOMONYME A ÉTÉ ÉPARGNÉ, ET C'EST LE POINT DÉLICAT DU LOT.** A6
> gradue aussi le A/E **PAR SEGMENT** sur `0,90 – 1,10` — mais là c'est le
> **VERT** (« non biaisé sur ce segment »), avec un AMBRE à `0,80 – 1,20`. Sur
> une **FENÊTRE**, `0,90 – 1,10` est l'**AMBRE**. *Deux échelles, deux objets,
> les mêmes nombres.* Unifier les six sites sous une constante les aurait
> mélangés : **quatre sites rewirés, celui du segment INTOUCHÉ**, et un test
> fige la distinction.
> ⚠️ **Et le libellé publié suit** : « Recalibrer si A/E sort de [0.90, 1.10] »
> dérive désormais de la constante — même geste que `SEUIL_CV_INSTABLE`.

**C3 — Une figure vide est visuellement indiscernable d'une figure pleine.**
Les **sept** fonctions rendent un objet complet — fond navy, titre or, axes
titrés, bande verte — avec zéro point tracé, et **aucune ne le dit** :

```
  [CONSTAT] QQ-plot, 1 residu        points traces = 0   la figure le dit : False
  [CONSTAT] QQ-plot, 0 residu        points traces = 0   la figure le dit : False
  [CONSTAT] QQ-plot, que des NaN     points traces = 0   la figure le dit : False
  [CONSTAT] distribution, 0 valeur   points traces = 0   la figure le dit : False
  [CONSTAT] lift, 0 decile           points traces = 0   la figure le dit : False
  [CONSTAT] relativites, 0 variable  points traces = 0   la figure le dit : False
  [CONSTAT] walk-forward, 0 fenetre  points traces = 0   la figure le dit : False
```

Le QQ-plot est le cas le plus net : `if n >= 2:` (l.456) et rien dans le `else`.
Un actuaire feuilletant le rapport voit un panneau titré « QQ-plot des résidus
de Pearson » et conclut que le diagnostic a été fait.

### B — Affirme plus que le code ne porte (2)

**C4 — « SOURCE UNIQUE du style graphique de la tarification » : les quatre
agents portent leur propre charte.** Relevé sur tout le dépôt : **52 fichiers**
construisent une figure plotly hors de ce module. Pour les quatre agents de
tarification, en comparant leurs couleurs à la charte V3 :

```
  charte V3        :  8 couleurs -> #0B1E3D #122A4F #F0F4F8 #8A9BB0
                                    #F0D060 #D4AF37 #1A3A60 #00E5A0
  a3_glm           : 11 couleurs, dont  1 de la charte
  a4_ml            : 12 couleurs, dont  1 de la charte
  a5_deep_learning : 10 couleurs, dont  1 de la charte
  a6_comparaison   : 12 couleurs, dont  1 de la charte
```

Les quatre partagent **la même palette étrangère**, répétée à l'identique :
`#0F2E52 #1B3A5C #243F6A #2ECC71 #3498DB #8A9AB0 #C9A84C #E74C3C #E8C96A
#F39C12`.

## ⚠️⚠️ COMPLÉTÉ LE 24/08/2026 (SOIR) — CE N'EST PAS « UNE SECONDE CHARTE »

**J'avais écrit « une seconde charte, dupliquée quatre fois ». C'est faux, et
la vérité est plus simple : c'est LA PREMIÈRE.** Mesuré par AST — la palette
est déclarée au **niveau module de `actuaria_app.py`, l.23-34** :

```
  NAVY #0F2E52 · NAVY_L #1B3A5C · NAVY_LL #243F6A · OR #C9A84C · OR_L #E8C96A
  BLANC #F0F4F8 · GRIS #8A9AB0 · VERT #2ECC71 · AMBRE #F39C12 · ROUGE #E74C3C
  BLEU #3498DB · VIOLET #9B59B6
```

Et les quatre agents l'utilisent **intégralement, sans une seule couleur
étrangère** :

```
  a3_glm            11 couleurs · 11 de l'APP · 1 de la charte V3 · 0 inconnue
  a4_ml             12 couleurs · 12 de l'APP · 1 de la charte V3 · 0 inconnue
  a5_deep_learning  10 couleurs · 10 de l'APP · 1 de la charte V3 · 0 inconnue
  a6_comparaison    12 couleurs · 12 de l'APP · 1 de la charte V3 · 0 inconnue

  charte V3 ∩ palette de l'app  =  {#F0F4F8}   -- UNE couleur sur douze
```

⚠️⚠️ **Il n'y a donc pas une source unique et des dérives : il y a DEUX
CHARTES.** Celle de l'application (12 couleurs, utilisée par l'app **et** les
quatre agents) et celle de `charts_tarif` (8 couleurs, utilisée par **ses 7
fonctions et rien d'autre**). Et c'est la seconde qui s'annonce « SOURCE UNIQUE
du style graphique de la tarification ».

⚠️ **Le gris à un caractère près s'explique enfin** : `GRIS = '#8A9AB0'` dans
l'application, `'texte_2': '#8A9BB0'` dans la charte. **Deux gris, un
caractère, deux systèmes** — et les deux sortent dans le même rapport.

⚠️ **Ce que ça change au remède** : ce n'est pas « ramener les agents à la
charte ». C'est **choisir laquelle des deux est la source**, et le dire une
fois. *Preuve : `preuves/audit_app.py`.*

⚠️ Ces agents produisent **32 figures** de leur cru (`go.Figure` : 9 + 7 + 8 +
8) contre **7** passant par ce module. Seul a6 référence `COULEURS[...]`, trois
fois.

**C5 — Quatre troncatures silencieuses, aucune écrite sur la figure.**

```
  (a) relativites  : 23 fournies  -> 15 tracees   la figure le dit : False
  (b) walk-forward :  4 fenetres  ->  2 tracees   la figure le dit : False
  (c) distribution : 1000 valeurs -> 500 tracees  la figure le dit : False
  (d) SHAP         : 30 features  -> 15 tracees
```

Le plan `auto.yaml` produit **23 colonnes** : la figure des relativités en
publie 15 et son titre dit simplement « Relativités tarifaires GLM exp(β) ».
Pour (b), le commentaire l.337-341 assume le choix — « *le graphique montre ce
qui a été mesuré* » — mais l'axe est `type='category'` : une année écartée
**disparaît sans laisser de trou**. Pour (c), `p[np.isfinite(p)]` écarte la
moitié du portefeuille sans un mot.

### C — Imprécis ou daté (3)

**C6 — `_qnorm` tient sa promesse, mais pas celle qui est écrite.** La docstring
annonce « *|err| < 1.2e-9* ». Mesuré sur **405 003 points** contre
`scipy.stats.norm.ppf` :

```
  erreur ABSOLUE   : coeur 2,201e-09 · queues 5,621e-09 · grille QQ 3,840e-09
                     pire : 5,621e-09     annonce : 1,2e-09   (x 4,7)
  erreur RELATIVE  : 1,129e-09 partout
```

⚠️ **Acklam publie une erreur RELATIVE de 1,15e-9** — et c'est exactement ce
que l'implémentation atteint (**1,129e-9**). **L'algorithme est correct et bien
transcrit** ; la docstring écrit « |err| » sans dire de laquelle il s'agit, et
le chiffre est faux si on le lit en absolu.

**C7 — « kaleido absent aujourd'hui » : il est présent, en 1.3.0.** L'en-tête
l.15 dit « *Excel / Word : image statique (kaleido) — SUIVI (kaleido absent
aujourd'hui)* ». Mesuré :

```
  kaleido installe : version 1.3.0
  [BON] to_image(png) rend 20 826 octets -- l'image statique EST produisible
```

Le suivi est clos et la note ne l'est pas. ⚠️ *Savoir si l'Excel et le Word
rendent effectivement ces images est une question de leurs services, pas de ce
fichier — je ne la tranche pas ici.*

**C8 — La valeur de `CONFIG_PLOTLY` est réécrite en dur dans l'application.**
`actuaria_app.py:4243` passe `config={"displayModeBar":False}` littéralement, au
lieu d'importer la constante. Même valeur aujourd'hui ; deux endroits à changer
demain.

### D — Vérifié comme BON (11)

| affirmation | mesure |
|---|---|
| **module PUR, aucun import d'agent** | imports = `__future__`, `typing`, `numpy`, `plotly` — **rien d'autre** |
| **7 fonctions**, et `__all__` les couvre | 7 `chart_*` trouvées, toutes dans les 13 entrées d'`__all__` |
| « les agents **A3/A4/A6** appellent ces fonctions » | exact — les 4 importateurs sont **a3, a4, a6** et `rapport_modeles_tarif` |
| chacune des 7 a un appelant de production | **7/7**, un chacune : lift·lorenz·walkforward → a6 · relativités·distribution·QQ → a3 · SHAP → a4 |
| `CONFIG_PLOTLY` est bien passée au rendu HTML | `to_html(full_html=False, include_plotlyjs=False, config=_CFG_PLOTLY)` — l.978 de `rapport_modeles_tarif` |
| **`_qnorm` en erreur relative** | **1,129e-09** sur 405 003 points — sous le 1,15e-9 d'Acklam |
| le plafond de Lorenz **ne dépend que de l'observé** | la prédiction n'entre pas dans son calcul : le tri est fait sur `y` |
| « fréquence 0,05 → 0,95 » | mesuré **0,9517** |
| « fréquence 1,50 → 0,44 » | mesuré **0,4393** |
| « sur huit tirages, le plafond varie de 1,8 % » | mesuré **0,6 %** — l'annonce est **plus prudente** que la mesure |
| « une fenêtre sans A/E n'est pas une fenêtre à 1,0 » | le correctif tient : 2 fenêtres à `None` **sortent du tracé**, aucune n'est dessinée à 1,0 |

### ⚠️⚠️ AJOUTÉ LE 24/08/2026 (SOIR) — DEUX CONSTATS DE LISIBILITÉ, MESURÉS AU RENDU

*Trouvés en rendant les deux chartes côte à côte sur de vraies figures, à la
demande de Selasse. Ce sont des défauts de **la V3 elle-même**, et je les ai
trouvés **en la défendant**.*

**C9 — Le gradient n'est pas monotone en luminance : deux déciles différents se
lisent pareil.** `_GRAD_ANCRES` (l.47-51) va bleu → turquoise → orange. Mesuré
sur les 10 déciles que `chart_lift_decile` produit :

```
  luminance D1->D10 : 0.13 0.17 0.22 0.28 0.35 0.34 0.28 0.24 0.23 0.25
  inversions = 4        ecart minimal entre deux deciles VOISINS = 0,0035
```

**Une échelle ORDONNÉE doit être monotone**, sinon le rang cesse d'être
lisible. Ici la luminance **monte jusqu'à D5 puis redescend**, et D8/D9 sont
séparés de **0,0035** — indiscernables à l'œil. ⚠️ *La palette de
l'application a le même défaut (4 inversions), donc ce n'est pas un argument
entre les deux : c'est un défaut à corriger dans le rôle.*

**Correctif mesuré** : une rampe bleu → violet → rouge → ambre clair donne
**0 inversion** et un écart minimal de **0,0086** — et le pire décile s'y lit
**chaud ET clair**, ce que la monotonie seule ne garantit pas.

**C10 — L'ambre du RAG *est* l'or des axes.** Dans `chart_walkforward_ae`
(l.346-351), le point AMBRE utilise `COULEURS['or_accent']` — la **même
couleur** que les lignes de bande et les barres d'erreur d'IC :

```
  rag_ambre #D4AF37  vs  or_accent #D4AF37
      ecart de teinte = 0 deg      contraste = 1,00
```

Un point « AMBRE » a donc exactement la teinte du décor. Il ne se lit pas
comme un avertissement. ⚠️ **Et c'est le seul point où la palette de
l'application fait mieux** : son ambre est un orange (`#F39C12`), sémantiquement
non ambigu. **Le principe entre dans le correctif ; la valeur, non.**

**Correctif mesuré** : `#FFC145` — contraste sur le graphique **6,79 → 8,82**,
et il sort de l'or (**1,00 → 1,30**).

*Preuves : les rendus PNG et les mesures de contraste WCAG, `preuves/`.*

⚠️ **Ce que je RETIRE de cet exercice** : j'ai voulu mesurer si les trois RAG
survivent au daltonisme. **Deux implémentations de la même formule m'ont donné
deux résultats différents.** Je ne publie pas la mesure. **Le principe tient
sans elle** : un RAG encodé par la **seule couleur** est un risque connu, et le
remède n'est pas une couleur — c'est un **second canal** (forme du marqueur).

### Ma mesure fausse, corrigée

J'ai d'abord relevé `CONFIG_PLOTLY` comme ayant **zéro consommateur de
production**. **C'était faux** : `rapport_modeles_tarif` l'importe **sous
alias** (`from core.charts_tarif import CONFIG_PLOTLY as _CFG_PLOTLY`), et mon
relevé AST comptait les occurrences du nom d'origine. La constante est bien
utilisée.

⚠️ C'est la troisième fois cette semaine qu'un relevé par symbole manque
quelque chose : par le français d'abord, par l'alias maintenant.

## ③ Ce que je ne tranche pas ici

**Rien n'est resté non lu** : 476 lignes, intégralement.

- **Les 52 fichiers à figures plotly hors de ce module** : je n'ai mesuré la
  palette que pour les **quatre agents de tarification**. Les 48 autres
  (provisionnement, Vie, Santé, réglementation) sortent du périmètre de ce
  relevé — mais le motif est mesuré, et il ne s'arrête probablement pas ici.
- **Ce que l'Excel et le Word font des figures** : kaleido est installé et
  `to_image` fonctionne ; savoir si `tarif_excel` et le Word les intègrent
  relève de leurs services.

## ④ Les preuves

- `preuves/audit_charts.py` — la pureté, `_qnorm` (405 003 points), le badge de
  Lorenz hors bornes, les trois bandes A/E, les quatre troncatures, les sept
  figures vides, kaleido.
- `preuves/audit_charts_bis.py` — kaleido 1.3.0 et `to_image`, la propagation
  **par AST**, les 52 fichiers à figures, et les quatre mesures chiffrées du
  docstring de Lorenz reproduites.

Chacune se relance seule.

---

**Mon appréciation d'ensemble.** Ce fichier est **le plus honnête du module sur
ce qu'il a corrigé**. La docstring de `chart_lorenz_gini` est un modèle : elle
raconte un badge trompeur, dit pourquoi il l'était, donne quatre mesures — et
**les quatre se reproduisent** (0,95 · 0,44 · le plafond indépendant de la
prédiction · une étendue annoncée plus large que la vraie). Le correctif des
fenêtres sans A/E tient. `_qnorm` est correctement transcrit. Le module est
réellement pur.

⚠️ **Le motif dominant ici n'est pas le faux, c'est le MUET.** Quatre
troncatures et sept figures vides ne mentent sur rien — elles **omettent**. Et
une figure omet plus dangereusement qu'un tableau : personne ne compte les
barres d'un graphique pour vérifier qu'il y en a 23.

⚠️ **Et un constat de forme, mais lourd** : le fichier s'annonce « SOURCE
UNIQUE du style graphique de la tarification » alors que les quatre agents qui
l'appellent produisent **32 figures** avec **leur propre charte**, dupliquée
quatre fois, et dont un gris diffère du sien **d'un seul caractère**. C'est le
mode de défaillance que `conformite_reglementaire` documente sur six cycles —
« *une règle correcte à un endroit, jamais propagée ailleurs* » — appliqué
cette fois à ce qui se voit.
