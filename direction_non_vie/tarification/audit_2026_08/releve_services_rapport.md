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

**C2 — La référence Wüthrich de l'Excel A5 n'est pas celle du modèle.**
```
  AGENT A5 : Wüthrich, M.V. & Merz, M. (2019), "Editorial: Yes, we CANN!"
  EXCEL A5 : Wüthrich (2019), 'Neural Networks Applied to Chain-Ladder Reserving'
```
L'onglet s'intitule « Fidélité CANN Wüthrich (2019) » et cite un article de **provisionnement chain-ladder**, pas l'article CANN de tarification que l'agent implémente. C'est le motif `Art. 77` : une citation attribuée au mauvais texte, dans un document signé.

**C3 — « 8 modèles » republié dans trois livrables.**
```
  Excel A4      : "8 modèles comparés"    -> True
  Excel equipe  : "×8 modèles"            -> True
  HTML equipe   : "×8 modèles"            -> True
```
La boucle d'A4 en calibre **6**. Le rapport consolidé « destiné à l'actuaire responsable et à la Direction » republie le faux compte dans ses trois formats.

**C4 — `h5_deviance` : plafonnante chez A6, absente du tableau des hypothèses.**
```
  8 hypotheses au tableau du chapitre 4
  3 plafonnantes GLM chez A6
  plafonnante(s) ABSENTE(S) du tableau = ['h5_deviance']
```
C'est le fait du lot ①, retrouvé par l'autre bout : `HYPOTHESES` énumère H1–H4 GLM et H1–H4 ML. La déviance résiduelle, qui peut plafonner le statut, n'a pas de ligne.

**C5 — Trois valeurs du modèle retenu échappent à la règle du module.**
```
  contexte du modele : ['score_global','overfit_ratio','gini_test',
                        'overfit_ratio','interpretabilite']
  tableau Word       : ['gini_test','overfit_ratio']
  la regle « NE VAUT PAS ZÉRO » est ecrite dans le MEME fichier = True
```
`.get(clé, 0)` formaté en `:.4f` — exactement ce que le module condamne quinze lignes plus haut et que ses tests V3/T4 verrouillent partout ailleurs. Le contexte lu par le modèle de narration reçoit donc « Gini=0.0000 » là où rien n'a été calculé.

### B — Ce qu'une surface dit et qu'une autre tait (2)

**C6 — Le rapport ÉQUIPE : l'Excel avertit, le HTML et le Word se taisent.**
```
  avertissement proxy walk-forward   : xl=True  html=False  word=False
  colonnes ecartees (conformite)     : xl=True  html=False  word=False
  colonnes du plan non produites     : xl=True  html=False  word=False
```
L'Excel équipe porte **six synthèses réglementaires** (`avertissement_walk_forward`, exclusions, alertes d'expérience, DL, qualité, mapping, plan amputé) que ses trois autres formats — HTML, Word, PDF — **n'ont pas du tout**. Trois d'entre elles sont mesurées ci-dessus. C'est le même rapport, sous quatre formes, dont une seule avertit.

**C7 — `raisons_plafond` atteint 2 surfaces sur 6** (mesuré au lot ①, avec témoin positif) : `modeles.export_html` et `modeles.export_word`. Ni l'Excel A6, ni les trois formats du rapport équipe.

### C — Imprécis ou daté (2)

**C8 — `export_excel_a3` annonce 5 onglets, en produit 6.** Corrigé après ma première mesure : **c'est le seul écart** — a1, a2, a4, a5 et a6 sont exacts.
**C9 — Un ROUGE se publie « ✗ Attention ».** `_kpi` traduit `{VERT: '✓ Conforme', AMBRE: '△ À surveiller', ROUGE: '✗ Attention'}`. « Attention » est plus faible que « À surveiller » ; le mot le plus fort du triptyque est le moins alarmant.

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
