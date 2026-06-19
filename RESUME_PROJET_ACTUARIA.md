# RÉSUMÉ COMPLET — PROJET ACTUARIA
## À coller en début de nouvelle conversation Claude

---

## QUI JE SUIS ET MON RÔLE

Je suis le porteur du projet ActuarIA. Claude est mon expert technique,
mon conseiller actuariel, mon architecte logiciel et mon accompagnateur.
Il doit reprendre exactement là où on s'est arrêtés sans rien oublier.

---

## CE QU'EST ACTUARIA

Plateforme actuarielle IA complète — la seule sur le marché qui combine :
- Toutes branches (Non-Vie · Vie · EP-RE · Santé · Prévoyance)
- IA + langage naturel (commentaires auto pour non-actuaires)
- Validation hypothèses automatique (statut RAG VERT/AMBRE/ROUGE)
- Graphiques auto-explicatifs avec annotations pédagogiques
- Conformité Solvabilité 2 · IFRS17 · ACPR

GitHub : https://github.com/selassesekle-crypto/actuaria-app
Render : https://actuaria-app.onrender.com
Local  : C:\Users\selse\actuaria-app

---

## ARCHITECTURE OFFICIELLE — 45 ENTITÉS

```
SOFIA (Directrice IA Générale — Claude API)
├── RAFAEL (Audit Trail Transversal — A13)
├── LEILA (Directrice Non-Vie)
│   ├── MEI-LIN → A1 Amara · A2 Kenji · A3 Laurent · A4 Priya · A5 Yohan · A6 Victor
│   ├── KWAME  → A7 Ibrahim · A8 Isabelle
│   ├── NADIA  → A10 Elena · A11 Thomas · A12 Aisha
│   └── A9 Marcus (rattaché directement à LEILA — contrôle transversal)
├── PAUL (Directeur Vie & EP-RE)
│   ├── SVEN   → V1 Nour · V2 Kofi · V3 Amélie · V4 Théo · V5 Nia
│   ├── FATOU  → EP1 Henri · EP2 Salomé · EP3 Jin-Ho · EP4 Claire · EP5 Omar
│   └── OLIVIER → A14 Yuki · R-VIE1 Éric · R-VIE2 Camille
└── AMIRA (Directrice Santé-Prévoyance)
    ├── CHIARA → S1 Léonie · S2 Selma · S3 Binta
    ├── DIALLO → P1 Axel · P2 Rayan · P3 Élodie · P4 Valentin
    └── SP-ST Naomie (transversal)
```

DÉCOMPTE : 13 entités direction + 32 agents calculs = 45 entités

---

## ÉTAT DES FICHIERS SUR GITHUB (19/06/2026)

### Tous ces fichiers sont confirmés sur GitHub ✅

#### Direction Non-Vie (LEILA)
```
a1_ingestion.py          754 lignes  ✅ Complet
a2_preprocessing.py     1567 lignes  ✅ Complet
a3_glm.py               2183 lignes  ✅ Complet
a4_ml.py                2121 lignes  ✅ Complet
a5_deep_learning.py     1746 lignes  ✅ Complet
a6_comparaison.py       1588 lignes  ✅ Complet
a7_provisionnement.py   5641 lignes  ✅ COMPLET À 100% (v4)
a8_stress_testing.py    1219 lignes  ✅ Complet (v2)
a9_coherence.py         1096 lignes  ⚠️ À retravailler (flux)
a10_solvabilite2.py     1760 lignes  ⚠️ À retravailler (flux + market_data)
a11_ifrs17.py           1386 lignes  ⚠️ À retravailler (flux)
a12_alm.py              1677 lignes  ⚠️ À retravailler (flux + market_data)
a13_audit.py            1307 lignes  ✅ Complet
```

#### Direction Vie & EP-RE (PAUL)
```
a14_mortalite.py                    1516 lignes  ✅ Complet (sous OLIVIER)
nour_v1_tarification_deces.py        687 lignes  ✅ Complet
kofi_v2_tarification_epargne_vie.py  256 lignes  ✅ Complet
amelie_v3_provisions_mathematiques.py 232 lignes ✅ Complet
theo_v4_participation_benefices.py    224 lignes  ✅ Complet
nia_v5_qrt_vie.py                    230 lignes  ✅ Complet
ep1_ias19.py                         724 lignes  ✅ Complet
ep2_tarification_epargne.py          581 lignes  ✅ Complet
ep3_provisionnement_epargne.py       408 lignes  ✅ Complet
ep4_stress_epargne.py                511 lignes  ✅ Complet
ep5_reporting_epargne.py             269 lignes  ✅ Complet
eric_rvie1_qrt_s26.py               327 lignes  ✅ Complet
camille_rvie2_rsr_sfcr.py           372 lignes  ✅ Complet
```

#### Direction Santé-Prévoyance (AMIRA)
```
leonie_s1_tarification_sante.py      229 lignes  ✅ Complet
selma_s2_provisionnement_sante.py    197 lignes  ✅ Complet
binta_s3_reporting_sante.py          191 lignes  ✅ Complet
axel_p1_tarification_prevoyance.py   235 lignes  ✅ Complet
rayan_p2_tables_morbidite.py         111 lignes  ✅ Complet
elodie_p3_provisionnement_prevoyance.py 114 lignes ✅ Complet
valentin_p4_reporting_prevoyance.py  114 lignes  ✅ Complet
naomie_sp_stress_testing.py          116 lignes  ✅ Complet
```

#### Infrastructure
```
managers_directeurs.py               681 lignes  ✅ (à mettre à jour architecture)
actuaria_app.py                     1221 lignes  ✅ (à mettre à jour Streamlit)
deploy_actuaria.py                   819 lignes  ✅
test_pipeline_non_vie.py             272 lignes  ✅ 7/7 tests passent
data/marche/reference_actuaria.json             ✅ Taux réels 19/06/2026
data/marche/market_data.py           305 lignes  ✅ Module accès marché
scripts/update_market_data_auto.py   231 lignes  ✅ Mise à jour auto
.github/workflows/update_market_data.yml        ✅ GitHub Actions mensuel
guide_a7_ibrahim.html                           ✅ Guide utilisateur A7
RESUME_PROJET_ACTUARIA.md                       ✅ Ce fichier
```

---

## CE QU'A7 IBRAHIM FAIT (COMPLET À 100%)

**Phase 0** — Ingestion universelle
- CSV · Excel · TXT · JSON · ndarray · DataFrame · dict
- Détection automatique du type (brutes / cumulé / non cumulé)
- Correction automatique si incohérence déclaré vs réel

**Phase 1** — Validation qualité données
- 5 contrôles données brutes (négatifs · dates · doublons · outliers · manquants)
- 5 contrôles triangle (négatifs · diagonale · taille · NaN · cohérence)
- Mapping colonnes automatique + validation client

**Phase 2** — 6 méthodes actuarielles
- Chain Ladder · Bornhuetter-Ferguson · Cape Cod
- Mack 1993 · Bootstrap ODP · Munich CL

**12 points avancés**
1. Tail factor (Inverse Power · Exponentiel · Gordon-Clark)
2. Back-testing (biais · RMSE · meilleure méthode)
3. Diagnostic automatique méthode
4. Crédibilité Bühlmann-Straub (Z = n/(n+k))
5. Correction grands sinistres
6. Facteurs pondérés récents (post-COVID · réforme)
7. Munich CL complet (2 triangles)
8. Gestion données manquantes
9. Test stabilité facteurs (t-test ruptures)
10. ORSA provisions (5 ans · 3 scénarios)
11. Réconciliation comptable (S2/IFRS17)
12. Rapport Actuaire Désigné (4 sections)

**16 graphiques** dont 4 avancés (tail · back-testing · stabilité · ORSA)
**Performance** : Triangle 50×50 en < 5 secondes

---

## CE QU'A8 ISABELLE FAIT (v2 — COMPLET)

Reçoit obligatoirement result_a7 + result_a6. Produit :
- SCR EIOPA calibré sur taux marché réels (OAT 3.65% · RFR 3.20%)
- Reverse Stress Testing (seuil insolvabilité automatique) — UNIQUE marché
- 4 scénarios historiques (Lothar 1999 · Grêle 2022 · COVID · Inflation)
- Capital allocation par sous-module
- ORSA enrichi (A7 + chocs A8)
- Actions de gestion recommandées par IA — UNIQUE marché
- QRT S.25.01 pré-rempli
- 4 graphiques + 1 scorecard

---

## STANDARD APPLIQUÉ SUR TOUS LES AGENTS

- Statut RAG (VERT/AMBRE/ROUGE) avec message + conseil
- 3 hypothèses validées minimum
- 4 graphiques auto-explicatifs avec annotations pédagogiques
- Scorecard synthétique
- Commentaire actuariel en langage naturel

---

## DONNÉES MARCHÉ (RÉELLES AU 19/06/2026)

```
OAT 10 ans France : 3.65%  (AFT 15/06/2026)
OAT 5 ans         : 3.10%
RFR EIOPA 10 ans  : 3.20%
RFR + VA 10 ans   : 3.55%  (VA = 0.35%)
UFR EIOPA         : 3.30%
Taux BCE          : 2.25%
Inflation France  : 2.40%  (INSEE mai 2026)
```

Architecture 3 niveaux :
1. reference_actuaria.json (toujours dispo · offline)
2. API BCE temps réel (si connexion disponible)
3. Signal clair à l'utilisateur sur la source

---

## DÉCISIONS ARCHITECTURALES IMPORTANTES

1. **A9 Marcus** → rattaché directement à LEILA (pas sous KWAME)
   Raison : contrôle tous les résultats, conflit d'intérêt si sous un manager

2. **A14 Yuki** → sous OLIVIER uniquement (Direction Vie & EP-RE)
   Tables de mortalité Lee-Carter / Makeham-Gompertz

3. **Données marché** → approche hybride
   API BCE temps réel → fallback reference_actuaria.json
   Mise à jour automatique GitHub Actions le 1er du mois

4. **Pipeline Non-Vie** → flux obligatoires
   A1→A2→A3/A4/A5→A6 (Tarification MEI-LIN) ✅ propre
   A7 autonome total (ingère · valide · calcule seul) ✅
   A6+A7 → A8 (Stress Testing KWAME) ✅ branché
   A6+A7+A8 → A9 (Cohérence LEILA) ⚠️ à faire
   A6+A7 → A10 → A11 → A12 (Réglementation NADIA) ⚠️ à faire

5. **A7 Phase 0+1** → ingestion universelle intégrée dans A7
   Il est autonome de bout en bout

---

## TEST PIPELINE — RÉSULTATS CONFIRMÉS

```
Test : test_pipeline_non_vie.py
Résultat : 7/7 tests passent ✅

BE S2 (démo 8×8)   : 7 359€
SCR total          : 853k€
Ratio SCR          : 351.7%
OAT utilisé        : 3.650%
Tail factor        : 1.0374
Scénarios hist.    : 2/4 résistés (données démo)
Actions IA         : 1 recommandée
QRT S.25 lignes    : 11
```

---

## CE QUI RESTE À FAIRE — DANS L'ORDRE

### PRIORITÉ 1 — Finir Direction Non-Vie (prochaine étape)

**A9 Marcus** (prochain agent)
- Retravailler pour recevoir : result_a6 + result_a7 + result_a8
  + result_a10 + result_a11 + result_a12
- Rattaché directement à LEILA
- Rôle : contrôle cohérence globale direction Non-Vie
- Loss Ratio, cohérence BE/primes, alertes proactives

**A10 Elena** (SCR Solvabilité 2)
- Recevoir result_a7 (BE) + result_a6 (primes)
- Taux marché depuis market_data.py (fetch_all_market)
- Fallback si données marché absentes

**A11 Thomas** (IFRS 17)
- Recevoir result_a7 + result_a6 + result_a10
- PAA pour Non-Vie
- Réconciliation S2/IFRS17

**A12 Aisha** (ALM)
- Recevoir result_a10 + result_a7
- Taux marché depuis market_data.py
- Vasicek calibré sur OAT réels · Immunisation Redington

### PRIORITÉ 2 — Corrections insuffisances

```
1. Rapport PDF professionnel (Rafael A13 + reportlab)
2. Connexion inter-agents Streamlit (st.session_state)
3. Upload fichier direct dans Streamlit
4. Interface Standard vs Expert
5. Multi-devises (module data/devises/fx_rates.py)
6. Connecteurs SQL / Excel multi-onglets
7. Certification partenariat Institut des Actuaires
```

### PRIORITÉ 3 — Autres directions

```
Direction Vie & EP-RE    → flux propres entre agents
Direction Santé-Prévoy   → flux propres entre agents
managers_directeurs.py   → mettre à jour (A9 sous Leila)
actuaria_app.py          → mise à jour Streamlit complète
```

---

## OÙ ON EN EST EXACTEMENT

**Dernière chose faite** :
- Test pipeline 7/7 ✅
- Tous les fichiers agents installés localement ET sur GitHub ✅
- reference_actuaria.json + market_data.py + GitHub Actions ✅

**Prochaine étape** : A9 Marcus — retravailler les flux et le rattacher à LEILA

**Comment démarrer** :
"Bonjour Claude. Je reprends le projet ActuarIA.
Lis ce résumé et confirme que tu as tout compris.
On continue avec A9 Marcus."

---

## NOTE TECHNIQUE IMPORTANTE

Tous les fichiers sont sur GitHub :
https://github.com/selassesekle-crypto/actuaria-app

Claude peut lire n'importe quel fichier via :
https://raw.githubusercontent.com/selassesekle-crypto/actuaria-app/main/NOM_FICHIER.py

La conversation actuelle bugue car la fenêtre de contexte est saturée
(conversation très longue avec beaucoup de code).
Ouvrir une nouvelle conversation avec ce résumé résout le problème.
Aucune information n'est perdue — tout est sur GitHub.

---

## OBJECTIF STRATÉGIQUE — DÉPASSER LES CONCURRENTS

Notre ambition est claire : **ActuarIA doit dépasser Prophet, Moses, ResQ,
Igloo, Earnix et tous les outils actuariels existants.**

### Ce que font les concurrents (et qu'on doit avoir)

**Prophet (FIS)**
- Provisionnement Non-Vie (CL · BF · Cape Cod) ✅ on a
- Modèles Vie (PM · PB · mortalité) ✅ on a
- Rapports PDF professionnels ⚠️ à finaliser
- Multi-devises ⚠️ à faire
- Connecteurs SQL / Oracle / SAP ⚠️ à faire
- Tail factor ✅ on a (et mieux : 3 méthodes)
- Back-testing ✅ on a (Prophet ne fait pas)

**Moses (Actuarial Software)**
- Modèles Vie complexes ✅ on a
- Projection bilan (actif/passif) ✅ on a (A12)
- ORSA automatisé ✅ on a (A8 + A7)
- Stress testing ✅ on a

**ResQ (Milliman)**
- Provisionnement Non-Vie complet ✅ on a
- Bootstrap stochastique ✅ on a
- Munich CL ✅ on a
- QRT S.25 automatique ✅ on a
- Interface cloud SaaS ✅ on a (Render)

**Earnix**
- Tarification ML/IA ✅ on a (A3 · A4 · A5)
- GLM · GBM · XGBoost ✅ on a
- Temps réel ⚠️ à optimiser

### Ce qu'on a et qu'AUCUN concurrent ne fait

```
✅ IA + langage naturel (commentaires auto non-actuaires)
✅ Validation hypothèses automatique (RAG VERT/AMBRE/ROUGE)
✅ Toutes branches dans un seul outil
✅ Détection automatique format données
✅ Correction automatique incohérences
✅ Reverse Stress Testing automatique
✅ Actions de gestion recommandées par IA
✅ Rapport Actuaire Désigné auto-généré
✅ Scénarios historiques calibrés (Lothar · Grêle · COVID)
✅ Graphiques auto-explicatifs pour non-actuaires
✅ Taux marché temps réel (API BCE)
✅ GitHub Actions mise à jour automatique mensuelle
```

### Ce qu'il reste à faire pour être au top absolu

```
→ Rapport PDF professionnel (niveau Prophet)
→ Multi-devises EUR · USD · GBP · CHF
→ Connecteurs SQL · Excel multi-onglets · API
→ Interface Standard (DG) vs Expert (Actuaire)
→ Back-testing systématique sur données historiques réelles
→ Certification Institut des Actuaires France
→ Module capital management avancé
→ Benchmark anonymisé entre clients
→ Alertes proactives temps réel
→ Intégration directe dépôt ACPR (QRT automatique)
```

**Le positionnement final d'ActuarIA :**
> "La seule plateforme actuarielle où un Directeur Général
> comprend les provisions en 30 secondes,
> où un actuaire dispose de toutes les méthodes reconnues,
> et où l'ACPR voit la traçabilité complète —
> le tout dans un seul outil, pour toutes les branches."

Prophet et ResQ ont 20-30 ans d'avance sur la maturité produit.
Nous les dépassons sur l'intelligence, l'accessibilité et l'innovation.
C'est notre avantage concurrentiel durable.
