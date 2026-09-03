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

> ✅ **`charts/C3`** · **FERMÉ le 28/08/2026.** Les **sept** fonctions déclarent
> désormais « **AUCUNE DONNÉE — …** » au centre de la figure quand rien n'est
> tracé, **et le message NOMME ce qui manque** (résidus · déciles · variables ·
> fenêtres · points de la courbe · prédictions).
> ⚠️ **UN SEUL ENDROIT DÉCIDE** — `_declarer_assiette`, et les sept l'appellent.
> Sept messages recopiés auraient divergé, comme les 30 définitions de couleurs
> avant `STATUT_RAG`.
> ⚠️⚠️ **SECOND SENS, ET IL COMPTE PLUS QUE LE PREMIER** : une annotation posée
> sur TOUTES les figures ne vaudrait rien — elle cesserait d'être un signal. Un
> témoin vérifie qu'une figure PLEINE ne déclare **rien**.
> ⚠️ **ET J'AI PRODUIT DEUX FAUSSES LECTURES EN TRAÇANT CE LOT** :
> `chart_distribution_predictions([])` et `chart_lift_decile` semblaient LEVER
> — c'était ma sonde (`or` sur un tableau numpy, et un `[]` passé là où un
> `float` était attendu). *Une sonde qui lève accuse le code à tort aussi
> sûrement qu'une sonde qui ne trouve rien l'absout à tort.*

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

> ⚠️⚠️ **`charts/C4` — REDESCRIPTION AU CODE DU 29/08/2026, SANS CLASSEMENT.**
> Le constat n'a **PAS** bougé, et je corrige mon propre relevé de la veille.
>
> | agent | couleurs | dont V3 *(base du constat)* | dont V3+RAG |
> |---|---|---|---|
> | `a3_glm` | 10 | **1** | 3 |
> | `a4_ml` | 11 | **1** | 3 |
> | `a5_deep_learning` | 7 | **1** | 1 |
> | `a6_comparaison` | 9 | **1** | 1 |
>
> ⚠️ **J'avais écrit « a3 3/10, a4 3/11 — l'arbitrage 2 l'a amélioré ». C'EST
> FAUX** : je comparais à une base ÉLARGIE (V3 **+** les six couleurs RAG), là
> où le constat compare aux **8 couleurs V3**. Sur SA base, c'est toujours
> **1 sur 7 à 11**, à l'identique. *Un compte n'est comparable que si l'assiette
> est la même — appliqué à mon propre chiffre.*
> ⚠️ Ce qui a réellement changé : `a3` et `a4` partagent maintenant **2
> couleurs RAG** via `couleur_rag`. C'est un progrès sur l'axe RAG, **aucun** sur
> l'axe palette.
> ⚠️ Et le balayage : **54 fichiers** construisent une figure plotly hors du
> module, contre **52** au relevé. **NON CLASSÉ, NON OUVERT.**

> ✅ **`charts/C4`** · **FERMÉ le 29/08/2026, ET PAS PAR OÙ IL ÉTAIT ÉCRIT.**
> *Preuve : `test_repli_et_palette.py`, 5 contrôles.*
>
> **Selasse a arbitré : la couleur est mon choix, l'exigence est « pertinent et
> beau pour le client ».** J'ai donc mesuré avant de décider, et la mesure a
> déplacé le constat.
>
> ### ⛔ CE QUE JE NE FAIS PAS : migrer les quatre agents vers la charte
>
> ⚠️ **La prémisse du constat est PÉRIMÉE.** Il dit « les quatre agents portent
> leur propre charte ». Re-mesuré au code du 29/08 : ils partagent **UNE seule**
> palette — 3 fonds `NAVY/NAVY_L/NAVY_LL` + 4 accents (`OR` `BLANC` `GRIS`
> `BLEU`) **identiques chez les quatre**. Il n'y a pas quatre chartes.
>
> ⚠️ **Et la migration n'achèterait presque rien à l'œil** : l'or des agents
> `#C9A84C` est à **1,09** de contraste de l'or de la charte `#D4AF37`.
> *Toucher ~54 fichiers pour un écart invisible n'est pas un correctif, c'est
> un déplacement.*
>
> ### ⚠️⚠️ CE QUE JE CORRIGE : LE DÉFAUT EST SÉMANTIQUE, PAS ESTHÉTIQUE
>
> Les deux listes décoratives contenaient **`couleur_rag('VERT'/'AMBRE'/
> 'ROUGE')` — les couleurs de STATUT** — consommées en cycle **positionnel** :
>
> ```
>   a4 : COULEURS_MODELES = [OR, VERT, "#3498DB", "#9B59B6", AMBRE, ROUGE]
>   a6 : COULEURS         = [OR, VERT, BLEU, AMBRE, ROUGE, "#9B59B6", GRIS]
>        ... consommees par  COULEURS[idx % len(COULEURS)]
> ```
>
> **Le modèle n° 5 était peint en ROUGE RAG parce qu'il était cinquième.** Un
> lecteur entraîné par tout le reste du rapport y lit une alerte. *C'est le
> motif de `charts/C10`, retourné : là un statut portait la couleur du décor,
> ici le décor porte la couleur d'un statut.*
>
> ⚠️ **Second défaut, dur et mesuré** : `#9B59B6` vaut **2,49** sur le fond de
> tracé `#1B3A5C` — sous le seuil WCAG 1.4.11 (3:1, objet non textuel).
>
> ### Le cycle retenu — **choisi par mesure, pas au goût**
>
> `[OR #C9A84C, BLEU #3498DB, MAUVE #C89BD4, PERVENCHE #B8C4F0, ROSE #C2678F,
> GRIS #8A9AB0]`, plus `BLANC #F0F4F8` en 7ᵉ pour a6.
>
> | critère | mesure |
> |---|---|
> | aucune valeur `couleur_rag` | 0 sur 7 |
> | WCAG 1.4.11 sur `#1B3A5C` | minimum **3,12** — les 7 au-dessus de 3:1 |
> | familles de teinte | **6** distinctes (44°, 204°, 215°, 227°, 287°, 334°) |
> | deuteranopie, paire la plus proche | **L1 = 59** (seuil pratique 40) |
>
> ⚠️ **L'OR RESTE, ET L'EXCEPTION EST DÉCLARÉE** : sa teinte (44°) est dans la
> famille ambre. Il n'a jamais désigné un statut, c'est l'accent maison, et en
> A6 il **porte une information** (`OR if est_prod else ...` marque le modèle de
> production). *On déclare l'exception, on ne la cache pas dans un seuil.*
>
> ⚠️⚠️ **ET DEUX DE MES PROPRES ACCUSATIONS SONT RETIRÉES PAR LA MESURE :**
> - j'ai accusé `#0F2E52 #1B3A5C #243F6A` d'être à 1,21 / 1,43 / 1,57, sous le
>   seuil. **Vérifié au site : ce sont `NAVY / NAVY_L / NAVY_LL`, les FONDS.**
>   Le critère 1.4.11 ne les concerne pas — *j'appliquais un seuil de série à
>   une toile* ;
> - j'ai accusé **six paires** d'être « trop proches » (contraste < 1,5).
>   Simulé en deuteranopie : **0 paire sur 15 fusionne**. Le contraste mesure la
>   **luminance**, pas la couleur — il **sur-accusait**.
>
> ⚠️ Et deux cycles que j'avais proposés ont été **refusés par le critère
> daltonien** avant d'être écrits : mauve/cyan à L1 = 20, puis mauve/ardoise à
> 17. *La palette a été mesurée, pas choisie.*
>
> ⚠️ **RESTE HORS ASSIETTE, NOMMÉ** : `#9B59B6` vit aussi dans `a9` `a10` `a11`
> `a12` et `provisionnement/n5_graphiques.py` — **hors du chantier
> tarification**, non touché.

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

> ✅ **`charts/C5`** · **FERMÉ le 28/08/2026 — TROIS sous-cas sur quatre, et le
> quatrième est DÉCLARÉ INEXISTANT.** Les troncatures s'écrivent désormais sous
> la figure : « **15 variables sur 23 — les 8 autres ne sont pas tracées** ».
> Mesuré : relativités **23 → 15**, SHAP **30 → 15**, walk-forward **4 → 2**.
> ⚠️ **ON DÉCLARE, ON N'ÉLARGIT PAS.** Tracer 23 relativités rendrait la figure
> illisible : `top=15` est un choix de lisibilité défendable. Ce qui ne l'était
> pas, c'est qu'il soit MUET. *Fermer le constat en supprimant la troncature
> aurait échangé un défaut contre un autre* — un test l'interdit.
> ⚠️⚠️ **LE SOUS-CAS (c) DU RELEVÉ N'EST PAS REPRODUIT** : il annonçait
> « distribution : 1 000 valeurs → 500 tracées ». Mesure d'aujourd'hui :
> **1 000 sur 1 000**, aucune coupe. *Un sous-cas qui ne se reproduit pas se
> DÉCLARE, il ne se corrige pas* — et un test **fige cette absence**, pour
> qu'on n'introduise pas une troncature en croyant fermer un défaut inexistant.
> ⚠️ **Et le nombre ANNONCÉ est comparé au nombre TRACÉ** : une déclaration
> fausse serait pire que le silence.

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

> ✅ **`charts/C6`** · **FERMÉ le 31/08/2026 — C'ÉTAIT LE MOT, PAS LE CALCUL.**
> *Preuve : `TRI-3`.* La docstring nomme désormais l'erreur **RELATIVE** et sa
> borne d'Acklam (1,15e-9), atteinte à **1,129e-9**. L'erreur **absolue** — qui
> monte à 5,62e-9, soit ×4,7 l'ancienne annonce — est publiée à côté, pour que
> le lecteur ne puisse plus confondre les deux.
> ⚠️ **Second sens sans dépendance neuve** : `_qnorm` composée avec la CDF
> redonne `x` à 1e-6 sur sept points, *sans scipy* — le module reste pur.


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

> ✅ **`charts/C7`** · **FERMÉ le 31/08/2026.** *Preuve : `TRI-4`.* L'en-tête
> dit **DISPONIBLE**, et le contrôle vérifie **les deux sens** : la ligne qui
> affirme ne dit plus « absent », **et kaleido est bien installé** (1.3.0) —
> *une en-tête corrigée redeviendrait fausse dans l'autre sens si le paquet
> disparaissait.* ⚠️ La borne du constat est conservée : ce que l'Excel et le
> Word font de ces images relève de **leurs** services, non tranché ici.


**C8 — La valeur de `CONFIG_PLOTLY` est réécrite en dur dans l'application, et
elle a DÉJÀ divergé.**
`actuaria_app.py` passe `config={"displayModeBar": False}` littéralement, au
lieu d'importer la constante.

> ⚠️⚠️ **CE CONSTAT A ÉTÉ SOUS-ESTIMÉ, ET RE-MESURÉ LE 03/09/2026.** Il
> annonçait **un** site (`actuaria_app.py:4243`) et concluait « même valeur
> aujourd'hui ; deux endroits à changer demain ». Les deux affirmations sont
> fausses :
>
> - **il y a DEUX sites**, `actuaria_app.py:4188` et `:4248` *(numéros au
>   03/09/2026 ; c'est le COMPTE, 2, que le filet dérive — pas la ligne)* ;
> - **la divergence n'est pas pour demain, elle est là.** La constante vit
>   dans `core/charts_tarif.py` et vaut
>   `{'displayModeBar': False, 'responsive': True}` — **DEUX clés**. Les deux
>   sites n'en passent qu'**une**. `responsive: True` est donc **perdu aux
>   deux endroits**, et le mot `responsive` n'apparaît **nulle part** dans
>   `actuaria_app.py`.
>
> *Le constat décrivait un risque futur ; la mesure montre un écart présent.*
> **C'est la forme même que cet audit poursuit : une phrase qui affirme moins
> que ce que le code porte est aussi trompeuse qu'une qui affirme plus.**
>
> ⛔ **IL RESTE OUVERT, ET C'EST UN ARBITRAGE, PAS UN OUBLI.** Le correctif
> vit dans `actuaria_app.py`, et Selasse a arbitré : **on ne touche pas à
> l'app Streamlit**. Ce qui est corrigé ici, c'est la DESCRIPTION — épinglée
> par `test_charts_c8_mesure.py`, qui dérive le compte et la clé perdue des
> fichiers eux-mêmes et tombera le jour où l'un des deux bougera.

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

> ✅ **`charts/C9`** · **FERMÉ le 29/08/2026.** **0 inversion, écart minimal
> 0,0109** sur dix déciles — contre 4 inversions et 0,0035 au relevé, pour un
> maximum théorique de 0,0138 avec ces extrémités.
> ⚠️ **LES DEUX EXTRÉMITÉS NE CHANGENT PAS** : elles portent le SENS — bleu =
> bas risque, orange = haut. Seule l'ancre médiane bouge, du turquoise
> (luminance **0,3854**, plus clair que les deux bouts — c'était la bosse) vers
> un violet à **0,1817**, *comprise entre les deux*. Ce n'est pas un goût,
> c'est la condition de la monotonie.
> ⚠️⚠️ **ET LE REMÈDE N'EST PAS L'ANCRE, C'EST L'ÉCHANTILLONNAGE.** Mesuré :
> avec la bonne ancre mais un échantillonnage régulier en `t`, l'écart minimal
> ne monte qu'à **0,0044** — l'interpolation est linéaire en RGB, pas en
> luminance. `_gradient_ordonne` vise désormais des **luminances régulières** et
> cherche le `t` correspondant. *La monotonie est obtenue par construction, pas
> par une ancre chanceuse.*
> ⚠️ Un test épingle les deux propriétés ENSEMBLE — monotonie des ancres (que la
> dichotomie SUPPOSE) et régularité du pas obtenu.

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

> ✅ **`charts/C10`** · **FERMÉ le 29/08/2026 — et le constat était PLUS LARGE
> que son libellé.** Mesuré au site : les **TROIS** couleurs de point
> contournaient la source RAG — l'AMBRE prenait `or_accent` (#D4AF37), le VERT
> `ligne_predite` (#00E5A0), le ROUGE un littéral `rgba(240,85,35,0.95)`.
> **Trois définitions locales que le lot de la charte n'avait pas atteintes.**
> Elles lisent désormais `couleur_rag(…, FOND_SOMBRE)`.
> ⚠️⚠️ **ET LA COULEUR NE FERME PAS CE CONSTAT — LE SYMBOLE LE FERME.** J'avais
> écrit un test attendant que l'ambre RAG se sépare de l'or ; **il a réfuté mon
> attente**. Mesuré : teinte 0° → **9,1°**, mais contraste **1,04** — la
> luminance ne bouge pratiquement pas. Pire, le **VERT est à 1,00** contre l'or :
> *exactement la même luminance que le décor.*
> ⚠️ `SYMBOLE_RAG` (cercle · triangle · carré) existait dans la source depuis le
> lot de la charte et **n'était employé nulle part** — une figure à POINTS est
> exactement son usage. Le second canal est donc **nécessaire, pas décoratif**,
> et c'est mesuré.
> ⚠️ **SECOND SENS** : les lignes de bande gardent l'or — c'est du DÉCOR, l'or
> y est légitime. *Repeindre le décor aurait échangé un défaut contre un autre.*
