# RELEVÉ — LES SERVICES DE RAPPORT

**Lu intégralement** : `rapport_modeles_tarif.py` **2 475 l** · `tarif_excel.py` **1 049 l** · `rapport_equipe_tarif.py` **957 l** · `excel_helpers.py` **139 l** · `test_rapport_modeles_tarif.py` **1 850 l**. **6 470 lignes.**

## ① Le compte

**17 affirmations mesurées** — 9 constats · 8 vérifiées bonnes.

## ② Le classement

### A — Publie du FAUX à un actuaire qui signe (5)

**C1 — « Arrêté : » publie l'horodatage de génération.**
```
  valeurs trouvees dans le classeur = ['23/08/2026 14:38', …]  -> portent une HEURE
  28 bandeaux recoivent `now` au lieu de l arrete
```
`_bandeau` rend « Arrêté : {date_str} » et **28 sites** lui passent `now`. L'arrêté réel, transmis par l'appelant, n'apparaît qu'**une seule fois** (un KPI de l'onglet 1 du rapport équipe). Sur un livrable réglementaire, l'arrêté est une date de référence, pas une date d'impression.

> ✅ **`services/C1`** · **FERMÉ le 27/08/2026 — `ea37564`. Deux méthodes.**
> **① AST** : **0** site `_bandeau(… now …)` — *l'origine en mesurait 28.*
> **② Exécution** de `libelle_arrete` : absent → « non déclaré » · vide →
> « non déclaré » · illisible → « non déclaré (illisible : …) » · déclaré →
> la date d'arrêté. **Un `now()` ne peut plus se glisser sous l'étiquette** ;
> les horodatages restants sont étiquetés « GÉNÉRÉ LE (impression) ».
> Épinglé par `test_horodatage_livrable.py` (8 contrôles).

**C2 — La référence Wüthrich de l'Excel A5 n'est pas celle du modèle.**
```
  AGENT A5 : Wüthrich, M.V. & Merz, M. (2019), "Editorial: Yes, we CANN!"
  EXCEL A5 : Wüthrich (2019), 'Neural Networks Applied to Chain-Ladder Reserving'
```
L'onglet s'intitule « Fidélité CANN Wüthrich (2019) » et cite un article de **provisionnement chain-ladder**, pas l'article CANN de tarification que l'agent implémente. C'est le motif `Art. 77` : une citation attribuée au mauvais texte, dans un document signé.

> ✅ **`services/C2`** · **FERMÉ le 27/08/2026 — `f63be18` (+ `d2dc672`). Deux méthodes.**
> **① Lecture** : la citation chain-ladder a disparu du source.
> **② Exécution** : l'Excel A5 cite « Wüthrich, M.V. & Merz, M. (2019),
> *Editorial: Yes, we CANN!*, ASTIN Bulletin 49(1), 1-3, doi:10.1017/asb.2018.42 ».
> ⚠️ **Référence vérifiée EN EXTERNE** (Cambridge Core, site officiel d'ASTIN
> Bulletin), pas par simple appariement à ce que l'agent cite.
> Épinglé par `test_lot1_services.py`.

**C3 — « 8 modèles » republié dans trois livrables.**
```
  Excel A4      : "8 modèles comparés"    -> True
  Excel equipe  : "×8 modèles"            -> True
  HTML equipe   : "×8 modèles"            -> True
```
La boucle d'A4 en calibre **6**. Le rapport consolidé « destiné à l'actuaire responsable et à la Direction » republie le faux compte dans ses trois formats.

> ✅ **`services/C3`** · **FERMÉ le 27/08/2026 — `d2dc672`. Deux méthodes.**
> **① Lecture** : **0** littéral « 8 modèles » / « ×8 » hors commentaire dans
> les **trois** producteurs (`tarif_excel`, `rapport_equipe_tarif`,
> `rapport_modeles_tarif`).
> **② Exécution** : le compte **dérive** du classement réel — 3 modèles →
> « 3 modèles comparés », 6 → « 6 », 11 → « 11 ». *Le dénominateur n'est plus
> inventé.* Épinglé par `test_lot1_services.py`.

**C4 — `h5_deviance` : plafonnante chez A6, absente du tableau des hypothèses.**
```
  8 hypotheses au tableau du chapitre 4
  3 plafonnantes GLM chez A6
  plafonnante(s) ABSENTE(S) du tableau = ['h5_deviance']
```
C'est le fait du lot ①, retrouvé par l'autre bout : `HYPOTHESES` énumère H1–H4 GLM et H1–H4 ML. La déviance résiduelle, qui peut plafonner le statut, n'a pas de ligne.

> ✅ **`services/C4`** · **FERMÉ le 27/08/2026 — `d2dc672`. Deux méthodes.**
> **① Lecture** : `h5_deviance` figure dans `HYPOTHESES`, avec le commentaire
> qui dit pourquoi — *« PLAFONNANTE (A6) : elle peut bloquer le VERT »*.
> **② Exécution** : le tableau compte **9** hypothèses, contre **8** à l'origine.
> Épinglé par `test_lot1_services.py` (`TestC4_H5DevianceDansLeTableau`).

**C5 — Trois valeurs du modèle retenu échappent à la règle du module.**
```
  contexte du modele : ['score_global','overfit_ratio','gini_test',
                        'overfit_ratio','interpretabilite']
  tableau Word       : ['gini_test','overfit_ratio']
  la regle « NE VAUT PAS ZÉRO » est ecrite dans le MEME fichier = True
```
`.get(clé, 0)` formaté en `:.4f` — exactement ce que le module condamne quinze lignes plus haut et que ses tests V3/T4 verrouillent partout ailleurs. Le contexte lu par le modèle de narration reçoit donc « Gini=0.0000 » là où rien n'a été calculé.

### B — Ce qu'une surface dit et qu'une autre tait (3)

**C12 — La synthèse QUALITÉ n'atteint le rapport signé que par le prompt du LLM.**

⚠️⚠️ **CONSTAT NEUF, ouvert le 30/08/2026 en vérifiant autre chose** — la
question de Selasse sur l'indépendance vis-à-vis de l'IA — **et fermé dans le
même lot**. *C'est `services/C10` mot pour mot, sur une autre fonction.*

`synthese_qualite_donnees` a **trois** points de sortie de production, mesurés
par AST :

```
  rapport_equipe_tarif.py:179   syntheses_reglementaires   -> sans IA ✅
  tarif_excel.py:872            export_excel_a6            -> sans IA ✅
  rapport_modeles_tarif.py:1326 _construire_contexte_tarif -> LE PROMPT ⛔
```

**Le document qui part au CAC et à l'ACPR n'avait qu'un chemin, et c'était le
prompt.** Sans clé, sans réseau, ou sur une narration tronquée, l'information
disparaissait — pendant que le rapport d'équipe et l'Excel la publiaient, ce
qui rendait le trou d'autant plus difficile à voir.

⚠️ **Ce que cela couvre désormais** : l'étape 2 du chantier `plan/C7` crée
`doublon_identifiant_sans_echeance` — des lignes **conservées** dont on ne peut
dire si elles sont un doublon ou un historique. *Créer cet avertissement sans
lui donner un chemin non-IA aurait construit un garde-fou qui s'évapore : c'est
pourquoi les deux étapes sont un seul lot.*

> ✅ **`services/C12`** · **FERMÉ le 30/08/2026** — *preuve :
> `test_echeance_et_avertissement_qualite.py`, 9 contrôles, 9 violations
> plantées.*
>
> `avertissement_qualite` + `_bloc_qualite_html`, **sur le modèle exact de
> `avertissement_dl` / `_bloc_dl_html`**, insérés **dans les deux formats** —
> HTML et Word. *Le Word part au CAC comme le HTML : n'en corriger qu'un
> laisserait la moitié du livrable signé muette.*
>
> ⚠️⚠️ **LA PREUVE SE FAIT SANS CLÉ API**, méthode exacte qui a démasqué
> `services/C10` : on lit **le livrable**, pas la table des fonctions. Mesuré —
> le HTML et le `.docx` portent le titre, le code et le remède.
>
> ⚠️ **LE TEXTE N'EST PAS RÉÉCRIT** : il vient de `synthese_qualite_donnees`,
> la source unique déjà partagée avec le rapport d'équipe et l'Excel — un
> contrôle vérifie l'égalité **caractère pour caractère**.
>
> ⚠️ **SECOND SENS** : portefeuille sain → **aucun bloc**, ni texte ni HTML.
> *Un avertissement affiché toujours cesse d'être un signal.*
>
> ⚠️ **RGPD** : aucun identifiant client dans le bloc ni dans le HTML signé,
> vérifié par sentinelle.

> ✅ **`services/C5`** · **FERMÉ le 27/08/2026 — `d2dc672`. Deux méthodes.**
> **① Lecture, sur SON assiette** — les valeurs du modèle retenu : **0** site
> `.get(champ, 0)` sur `score_global`, `overfit_ratio`, `gini_test` et
> `interpretabilite`. Elles passent par `F.nombre`.
> **② Exécution** : `F.nombre(None)` → **« — »**, quand `F.nombre(0.0)` →
> « 0.0000 ». ⚠️ **Les deux sont désormais DISCERNABLES** — c'était tout
> l'enjeu : un zéro fabriqué se lisait comme un zéro mesuré.
> ⚠️⚠️ **ET UN SITE DE LA MÊME FAMILLE SURVIT, HORS DE CETTE ASSIETTE** :
> `rapport_modeles_tarif.py:1088` formate `cred6.get('k', 0):.4f` et
> `cred6.get('z_moyen', 0):.4f` — crédibilité Bühlmann-Straub, pas le modèle
> retenu. Il est gardé par `if cred6.get('appliquee')`, mais **il fabrique
> quand même un `0` là où ses voisins appellent `F.nombre`**. *Constat NEUF, ni
> corrigé ni classé ici — rendu à l'arbitrage.*

**C6 — Le rapport ÉQUIPE : l'Excel avertit, le HTML et le Word se taisent.**
```
  avertissement proxy walk-forward   : xl=True  html=False  word=False
  colonnes ecartees (conformite)     : xl=True  html=False  word=False
  colonnes du plan non produites     : xl=True  html=False  word=False
```
L'Excel équipe porte **six synthèses réglementaires** (`avertissement_walk_forward`, exclusions, alertes d'expérience, DL, qualité, mapping, plan amputé) que ses trois autres formats — HTML, Word, PDF — **n'ont pas du tout**. Trois d'entre elles sont mesurées ci-dessus. C'est le même rapport, sous quatre formes, dont une seule avertit.

> ✅ **`services/C6`** · **FERMÉ le 27/08/2026 — `4534ea7`. Deux méthodes.**
> **① AST** : les **quatre** exports (`excel`, `html`, `word`, et `pdf` via
> `html`) délèguent au constructeur partagé `_syntheses_ou_calcul` —
> l'orchestrateur les calcule **une fois** et les partage.
> ⚠️ *Un relevé par symbole disait « html 2/7 » : il ne voyait pas
> l'indirection. C'est l'exécution qui tranche.*
> **② Exécution** sur un jeu déclenchant 3 synthèses : **3/3 retrouvées dans
> l'Excel, le HTML ET le Word** — l'origine mesurait `xl=True html=False
> word=False`. Épinglé par `test_c6_syntheses.py` (5 contrôles).

**C7 — `raisons_plafond` atteint 2 surfaces sur 6** (mesuré au lot ①, avec témoin positif) : `modeles.export_html` et `modeles.export_word`. Ni l'Excel A6, ni les trois formats du rapport équipe.

### C — Imprécis ou daté (2)

**C8 — `export_excel_a3` annonce 5 onglets, en produit 6.** Corrigé après ma première mesure : **c'est le seul écart** — a1, a2, a4, a5 et a6 sont exacts.

> ✅ **`services/C8`** · **FERMÉ le 31/08/2026.** *Preuve : `TRI-5`.*
> ⚠️⚠️ **LES DEUX CÔTÉS SONT DÉRIVÉS, jamais l'annonce seule.** Écrire « 6 » en
> dur aurait reproduit le défaut au lot suivant : `TRI-5` **compte les
> `create_sheet` du code** par AST et les compare au nombre de la docstring.
> *Un compte écrit à la main ne se répare pas par un autre compte écrit à la
> main — il se remplace par une dérivation.*

**C9 — Un ROUGE se publie « ✗ Attention ».** `_kpi` traduit `{VERT: '✓ Conforme', AMBRE: '△ À surveiller', ROUGE: '✗ Attention'}`. « Attention » est plus faible que « À surveiller » ; le mot le plus fort du triptyque est le moins alarmant.

> ✅ **`services/C9`** · **FERMÉ le 31/08/2026 — DEUX DÉFAUTS SUR LA MÊME LIGNE.**
> *Preuve : `TRI-6`.*
>
> **① Le mot.** ROUGE dit désormais **« Non conforme »**, qui domine sans
> ambiguïté le « À surveiller » d'AMBRE. *L'escalade s'inversait sur le seul mot
> que l'actuaire lit en diagonale.*
>
> **② Le glyphe, trouvé en corrigeant le mot.** `_kpi` **redéclarait** `✓ △ ✗`
> en littéral, alors que `GLYPHE_RAG_EXCEL` est l'exception **nommée** de la
> charte. Il vient maintenant de `glyphe_rag(statut, cible='excel')`. *Le lot de
> la charte avait annoncé « 30 définitions locales → 0 » : il en restait une,
> cachée dans une chaîne qui portait aussi un mot.*


**C10 — Un garde-fou réglementaire ne sortait que par le prompt du LLM.**

⚠️⚠️ **CONSTAT NEUF, mesuré le 29/08/2026 par EXÉCUTION du pipeline réel** —
ouvert et fermé dans le même lot. Les modèles d'A5 concourent **déjà** au choix
du modèle de production, et ce n'est pas une hypothèse :

```
  frequence   9 candidats {GLM 1, Deep Learning 2, ML 6}   DL_CANN rang 2
  cout        8 candidats {Deep Learning 1, GLM 1, ML 6}   DL_TABNET RANG 1
              -> modele_production = DL_TABNET
```

Sur ce dossier, le rapport signé publiait *« Chapitre 6 — Modèle de production
retenu : DL_TABNET, Deep Learning »* puis *« RECOMMANDATION : → **Déployer
DL_TABNET** comme modèle de tarification »*. L'alerte
`dl_validation_humaine_requise` s'était **bien déclenchée** dans
`alertes_modele`, et `synthese_modele_dl` produisait le bon texte.

**Le HTML contenait pourtant ZÉRO occurrence** de « validation actuarielle
humaine », « ACTION REQUISE », « alerte », « requise ».

⚠️⚠️ **LA CAUSE, VÉRIFIÉE AU SITE** : dans ce rapport, `synthese_modele_dl`
n'avait **qu'un seul point de sortie** — `_construire_contexte_tarif`, qui
construit **le prompt envoyé au LLM**. Sans clé, sans réseau, ou sur une
narration tronquée, l'avertissement disparaissait. *Un garde-fou réglementaire
ne peut pas dépendre d'un appel réseau.*

⚠️ **LE RAPPORT D'ÉQUIPE ET L'EXCEL LE PUBLIENT, EUX** (`rapport_equipe_tarif`
l.157/176/413, `tarif_excel` l.861). C'est exactement
[[correctif-a-cote-de-la-surface]] : présent sur deux surfaces, **absent de la
troisième, la signée**.

> ✅ **`services/C10`** · **FERMÉ le 29/08/2026.**
> *Preuve : `test_avertissement_dl_et_courbe.py`, 6 contrôles.*
>
> `avertissement_dl(result_a6)` + `_bloc_dl_html` rendent l'avertissement
> **dans le HTML ET dans le Word**, à côté du bloc `raisons_plafond` dont ils
> reprennent exactement le patron. Mesuré sans aucune narration : l'ACTION
> REQUISE est présente dans les deux formats.
>
> ⚠️ **LE TEXTE N'EST PAS RÉÉCRIT** : il vient de `synthese_modele_dl`, la
> source unique déjà partagée. Un test compare **caractère pour caractère**.
> ⚠️⚠️ **SECOND SENS** : sur un modèle GLM, le bloc est **totalement absent**.
> *Un avertissement affiché toujours cesse d'être un signal.* Et une fois la
> validation faite, l'ACTION REQUISE disparaît mais **la trace factuelle reste
> visible** (qui, quand) — les deux états sont épinglés.
> ⚠️ **LES DEUX FORMATS**, parce que le Word part au CAC comme le HTML :
> corriger un seul aurait laissé la moitié du livrable signé sans garde-fou.
>
> ⛔⛔ **ET L'ASSIETTE RÉELLE EST DE SIX, PAS D'UNE — NOMMÉ, NON TRAITÉ.**
> Relevé par AST : les **six** synthèses du rapport (`mapping`, `exclusions`,
> `alertes_experience`, `modele_dl`, `qualite_donnees`,
> `colonnes_plan_manquantes`) vivaient TOUTES dans ce seul prompt. Ce lot n'en
> câble **qu'une**, celle que Selasse a autorisée. **Les cinq autres restent
> invisibles hors narration** — dont `exclusions` (colonnes écartées pour
> conformité) et `alertes_experience` (sinistralité passée conservée), qui
> portent le même type d'obligation. Un test FIGE ce compte de 1 sur 6, pour
> que le fait ne se perde pas entre deux lots.

**C11 — Les figures d'A5 ne pouvaient pas atteindre le rapport, par construction.**

⚠️⚠️ **CONSTAT NEUF, ouvert et fermé le 29/08/2026.** Le motif d'écart disait
« A5 n'entre pas dans la chaîne du rapport ». Il disait vrai de la chaîne des
FIGURES — mais **la cause n'était pas un choix, c'était une signature** :
`generer_rapport_tarification(result_a3, result_a4, result_a6, …)` **n'avait
aucun paramètre `result_a5`**, et `figures_disponibles` ne construisait son
dictionnaire de résultats qu'avec `a3`, `a4`, `a6`. *Aucune décision n'aurait pu
publier une figure d'A5 : l'interface l'interdisait.*

⚠️ Et le motif était **ambigu** : lu comme « A5 ne participe pas », il est
FAUX — mesuré par exécution, les modèles d'A5 concourent au choix du modèle de
production et `DL_TABNET` a gagné la cible coût.

> ✅ **`services/C11`** · **FERMÉ le 29/08/2026.**
> *Preuve : `test_figures_dl_publiees.py`, 10 contrôles.*
>
> `result_a5` descend désormais par `generer_rapport_tarification` →
> `export_html` / `export_word` / `export_pdf` → `figures_disponibles`.
> **Vérifié par exécution sur un pipeline réel** où le DL est candidat :
> 14 figures trouvées, les deux présentes, HTML **1 à 14 sans trou**, et le
> `.docx` porte **14 images** contre 13 avant.
>
> ⚠️⚠️ **`result_a5` EST EN MOT-CLÉ SEUL, ET APRÈS `result_a6`** — jamais entre
> `a4` et `a6` malgré l'ordre de lecture. Relevé par AST **avant** d'écrire la
> première ligne : `export_html` est appelée avec **neuf arguments
> positionnels** en production et dans une trentaine de tests. L'insérer au
> milieu aurait fait glisser `result_a6` dans `result_a5` — *deux
> dictionnaires, aucune erreur de type, et un rapport signé bâti sur les
> mauvaises données.* Le `*` rend l'accident impossible, et un test épingle la
> décision sur les **cinq** fonctions de la chaîne.
>
> ⚠️ **`proprete` A ATTRAPÉ UN TROU DU CÂBLAGE AVANT LA GATE** : `export_pdf`
> passait `result_a5=result_a5` sans avoir le paramètre — `F821`, nom
> indéfini. **Le PDF aurait levé un `NameError` à la première génération.**
>
> ⚠️⚠️ **ET UNE VIOLATION PLANTÉE A RÉVÉLÉ UN TROU DANS MON PROPRE FILET** :
> en retirant `result_a5=result_a5` du site d'appel d'A6, **aucun test du dépôt
> ne tombait**. Tout le câblage pouvait être juste et les figures n'arriver
> jamais, parce que le SEUL appel de production ne les passait pas. Un contrôle
> AST sur ce site ferme le trou. *Je vérifiais le mécanisme, pas le site.*
>
> ⚠️ **LES SIX AUTRES FIGURES D'A5 RESTENT ÉCARTÉES**, et leur motif est
> précisé : elles sont destinées à qui CONSTRUIT le modèle. Leur place est le
> document technique de validation (M4), chantier ouvert sur les 25 écartées.
> Un test fait tomber la gate si le motif ambigu revient.

### D — Vérifié comme BON (8)

| affirmation | mesure |
|---|---|
| **`monitoring_gini` écartée** pour ses données fabriquées | raison dans le code, « FABRIQUÉES » |
| **`optimisation_tarifaire` écartée** — hors périmètre | le « tarif optimal à −20 % » n'atteint aucun rapport |
| catalogue cohérent titre/source/plan | **13 figures**, aucune orpheline |
| un nom de modèle inconnu n'est jamais remplacé | `MODELE_FUTUR` traverse |
| l'absence de relecture actuarielle se dit | `non_enregistree` |
| troncature déclarée **seulement si elle coupe** | 15/15 → rien ; 15/16 → « sur 16 » |
| un plafond sans cause enregistrée se dénonce | `RAISON_INCONNUE` |
| les fonds RAG survivent à l'impression | `print-color-adjust: exact` |

**Les deux pires constats de mon relevé A4 — le monitoring simulé et le « tarif optimal » constant — n'atteignent aucun livrable**, parce que ce module les a écartés **avec leur raison écrite dans le code**, sous un test qui tombe si une figure nouvelle n'est pas classée. C'est le seul endroit du dépôt où un défaut trouvé ailleurs a été bloqué en aval.

## ③ Ce que je n'ai pas lu

**Rien.** Les 6 470 lignes des services, intégralement. Sur l'ensemble des sept relevés : **19 364 lignes de production + 9 196 de test, lues à 100 %.**

Non vérifiables ici, inchangé : `Commission Tarification IA France (2019)`, `ACPR-2022-P-01`, `AI Act 2025`, et les références bibliographiques.

## ④ Mes instruments fautifs — trois

Une fixture malformée (`exclusions_conformite` attend des chaînes, j'ai passé des dicts) qui rendait quatre classeurs vides ; **deux regex gourmandes** (`.*?` sous `re.S`) qui traversaient les frontières de fonction et m'ont fait annoncer **5 écarts d'onglets sur 6 là où il n'y en a qu'un**, puis capturer une bannière au lieu d'une référence. Corrigées et remesurées avant d'être rendues.

---

**Mon appréciation** : `rapport_modeles_tarif.py` est **la pièce la mieux tenue du dépôt** — vocabulaire unique, numérotation de figures calculée une fois pour deux formats, troncatures déclarées, absence de relecture écrite dans le document, et un catalogue de figures qui **écarte ce qui est fabriqué en disant pourquoi**. Ses 1 850 lignes de test mesurent le livrable, pas le code source.

Les neuf constats se répartissent en deux familles : **ce que les livrables héritent des agents** (le « ×8 », H5, la référence Wüthrich) et **ce qui diverge entre surfaces** — l'arrêté, les six synthèses du rapport équipe, les causes du plafond.

**Le relevé complet est rendu : sept agents et services, 28 560 lignes lues, aucune omission.** J'attends ton arbitrage sur ce qui vaut d'être ouvert.
