# ROADMAP ActuarIA — Feuille de route officielle

**Dernière mise à jour :** 10 juillet 2026
**Développeur :** Selasse Sekle
**Statut global :** Audit en cours (certificateur IA France / ACPR / AIA)

---

## ✅ COMPLÉTÉ

### Audit V4 — Équipe Tarification Non-Vie (résiduels post-certification v3)

5 points IMPORTANT identifiés par l'audit V4 (rapport certificateur indépendant, 10/07/2026) — **tous corrigés et validés numériquement** :

| # | Point | SHA | Validation |
|---|---|---|---|
| 1 | Filet genre A3 (CJUE C-236/09) — inconditionnel, ne dépend plus du nom de branche | `0633dfac` | 3/3 scénarios testés, y compris branche non reconnue |
| 2 | DATA_DICTIONNAIRE — 13 interactions manquantes, génération auto depuis INTERACTIONS | `43cfd52e` | 16/16 vérifications, synchronisation garantie par construction |
| 3 | `POIDS_CRITERES` global mutable — variable locale, race condition éliminée | `82f60384` | Test 2 threads simultanés, isolation confirmée |
| 5 | Bühlmann-Straub σ²_intra — formule dimensionnellement incohérente corrigée (σ²_intra=μ_marché, Bühlmann-Gisler 2005 §4.2) | `493fbfa5` | Sous-estimation ~275× quantifiée puis corrigée, Z_moyen 0.97→0.61 sur cas réaliste |
| 6 | CANN non conforme Wüthrich — GLM Tweedie réellement gelé (`requires_grad=False`), résiduel init à zéro, offset exposition | `85ccaaf6` + fix `bffe201d` | Vérification numérique CANN(époque0)≡GLM : écart 1e-6 |

**Décision actée sur le CANN (point #6)** : réparation complète (Option A) plutôt que requalification, car le temps était disponible pour le faire correctement. Le CANN est désormais un vrai CANN au sens Wüthrich & Merz (2019) — les coefficients extractibles de `glm_layer` sont strictement identiques au GLM Tweedie audité par A3, gelés pendant tout l'entraînement. Fallback honnête (`glm_gele=False`, logué clairement) si `result_a3` non fourni.

**Tests : 6/6 sur toute la direction après chaque correction.**

## ✅ COMPLÉTÉ

### Direction Non-Vie — Tarification (A1–A6) — CERTIFIÉE v3 (90/100)

**Trajectoire de certification : v1 (66/100) → v2 (84/100, sous conditions) → v3 (90/100, CERTIFIÉE)**
SHAs v3 : A1=da1993ca · A2=2cd096ee · A3=6a5f2e95 · A4=2e05908f · A5=4ec08c4d · A6=9e0e9fc2

| Item | Statut | SHA final | Référence |
|---|---|---|---|
| R4 — Exclusion `sexe` RC Auto | ✅ | `3f1feb68` | CJUE C-236/09 (Test-Achats) |
| R3 — Data leakage StandardScaler | ✅ | `4ec08c4d` | Kaufman et al. (2012) ACM TKDD |
| R2 — Garde-fou ElasticNet → PoissonRegressor | ✅ | `2e05908f` | Agresti (2015) §7 |
| R5 — Score composite documenté + audit_trail | ✅ | `718b4350` | ACPR-2022-P-01 §4.3 |
| R1 — Split temporel (A3, A4, A5) | ✅ | `a08c75fe` / `2e05908f` / `4ec08c4d` | IA France Commission Tarification (2019) §3.2.4 |
| SHAP obligatoire — alerte + plafond AMBRE si absent | ✅ | `2e05908f` | ACPR-2022-P-01 §4.3 ; AI Act 2025 Art. 13 |

**Tests A1–A6 : 6/6 ✅**

### Direction Non-Vie — Provisionnement (A7 Ibrahim)

| Item | Statut | SHA final |
|---|---|---|
| Option B incertitude composée σ²_total = σ²_Mack + σ²_modèle | ✅ | `de710836` |
| Correction bug N4 clé `h4_homosc_bootstrap` | ✅ | `de710836` |
| Correction N2 import math au niveau module | ✅ | `5d57c138` |

**Tests A7 (37/37) ✅ — Validation bout-en-bout 5 triangles ✅**

### Direction Non-Vie — Réglementation (A8–A14)

**Tests : A8 1/1 · A9 7/7 · A10 10/10 · A11 10/10 · A12 9/9 · A13 7/7 · A14 7/7 ✅**

### Direction Santé-Prévoyance

**Tests : 112/112 ✅**

---

## 🔄 EN COURS

### Audit externe (certificateur IA France / ACPR / AIA)

| Prompt | Périmètre | Statut |
|---|---|---|
| Prompt 1 — Tarification NV | A1–A6 | ✅ Rapport reçu + corrections appliquées |
| Prompt 2 — Provisionnement NV | A7 | ⏳ À envoyer |
| Prompt 3 — Réglementation NV | A8–A14 | ⏳ À envoyer |
| Prompt 4 — Vie/EP-RE | V1–V9, EP1–EP7, R-VIE1/2 | ⏳ À envoyer |
| Prompt 5 — Santé-Prévoyance | S1–S3, P1–P4, SP-* | ⏳ À envoyer |
| Prompt 6 — Synthèse & Certification | Plateforme complète | ⏳ À envoyer après 1–5 |

---

## 📋 ROADMAP PRIORITAIRE

### P0 — Bloquant (avant toute mise en production réglementaire)

| Item | Description | Effort | Référence |
|---|---|---|---|
| Export XBRL QRT S.25.01 | Le QRT JSON ne peut pas être soumis à l'ACPR. Format XBRL requis (taxonomie EIOPA v2.8.0). | Élevé | Instruction ACPR 2016-I-22 ; Règlement 2015/2452/UE |
| LRC test IFRS 17 §47–52 | Test de suffisance des primes absent dans A11. Bloquant pour premier reporting IFRS 17. | Moyen | IFRS 17 §47–52 |
| Transition IFRS 17 §C3–C22 | Approche rétrospective / juste valeur absente. A11 inutilisable pour premier rapport IFRS 17. | Élevé | IFRS 17 §C3–C22 |
| `temperature=0` API Claude | ⚠️ **RELEVÉ CORRIGÉ (lot C1, `ec71697`) : 13 appels API, pas 11.** Le relevé parti de `messages.create` en trouve treize ; deux manquaient à cette ligne (`core/mapping_llm.py`, `nv_triangle_mapping_llm.py`). Tous passent désormais par `core/frontiere_llm.py`, et les identifiants de modèle y sont nommés une seule fois : unifier la valeur est **une ligne dans un seul fichier**. ⚠⚠ **MAIS NE PAS GÉNÉRALISER `claude-sonnet-5` + `temperature=0` AVANT DE L'AVOIR VÉRIFIÉ CONTRE UN APPEL RÉEL.** La documentation de l'API indique que les paramètres d'échantillonnage non-défaut sont refusés (HTTP 400) sur ce modèle ; cela n'a **pas pu être vérifié** dans l'environnement de développement (paquet `anthropic` absent, `ANTHROPIC_API_KEY` non définie). Trois sites sont **déjà** dans cette combinaison (`core/mapping_llm.py`, `nv_triangle_mapping_llm.py`, `rapport_modeles_tarif.py`) : les faire tourner une fois tranche la question. Si le 400 se confirme, ces trois sites sont en panne silencieuse et c'est `temperature` qu'il faut retirer, pas étendre. | À vérifier avant tout changement — 3 sites concernés, 10 en attente | GL EIOPA ORSA GL 56 |
| Mention limitation réglementaire | Toutes les sorties doivent porter "Outil d'aide — validation actuaire désigné obligatoire". | Très faible | Normes professionnelles IA France §3.2 |

### P1 — Important (avant certification interne)

| Item | Description | Effort | Référence |
|---|---|---|---|
| Bornes RM A10 (3%–12% BE) | Plancher/plafond non prévus par Art. 77 §5 S2. À supprimer. | Faible | Art. 77 §5 S2 ; GL EIOPA TP.5.17 |
| σ RC Auto documentation | Valeur 11% dans les mémoires incorrecte (code juste : 10%/9%). À corriger dans la doc. | Très faible | Annexe II Rgt 2015/35 |
| Bootstrap ODP ≥ 2000 simulations | 300 sim insuffisantes pour P99.5 SCR (±20% d'incertitude). | Faible | England & Verrall (2002) §5.3 |
| Coefficients MCR par LoB | MCR mono-LoB actuel. Multi-LoB requis pour portefeuilles mixtes. | Moyen | Annexe XVIII Rgt 2015/35 |
| ORSA conformité GL EIOPA 56–58 | Vérifier les 3 sections obligatoires et l'horizon 3–5 ans dans A8. | Moyen | GL EIOPA 56–58 |

### P1bis — Résiduels mineurs Tarification v3 — STATUT

| Item | Description | Statut | Agent | SHA |
|---|---|---|---|---|
| Forçage de types A1 | `_forcer_types()` avec `pd.to_numeric`/`pd.to_datetime` `errors='coerce'`, alertes journalisées, exposé dans `rapport['coercition_types']`. | ✅ FAIT | A1 | `541f7aa2` |
| XGBoost objective Poisson | `_creer_xgboost(col_cible)` bascule sur `objective='count:poisson'` si `col_cible ∈ COLS_COMPTAGE` (miroir garde-fou R2). | ✅ FAIT | A4 | `6b17bd60` |
| Gouvernance profil A6 | `profil_valide_par` + `environnement` dans `run()`. Statut plafonné AMBRE si `environnement='production'` et `profil_valide_par=None`. Journalisé dans `audit_trail`. | ✅ FAIT | A6 | `948cd5a1` |
| Test non-discrimination proxy | Corrélation variables retenues / proxies de critères interdits (ex. code postal). | ⛔ BLOQUÉ | A2/A3 | — |

**Note sur le point bloqué :** le test de non-discrimination proxy nécessite une source de données externe (INSEE ou équivalent) que le projet n'a pas. L'implémenter sur données synthétiques donnerait un faux sentiment de conformité sans valeur de détection réelle. Reste inscrit au chantier P4 (données réelles), à traiter une fois une source de référence identifiée et son usage validé juridiquement (RGPD — données sensibles proxy).

### P2 — Amélioration (après validation Vie/EP-RE et SP sur données réelles)

| Item | Description | Effort | Prérequis |
|---|---|---|---|
| **Crédibilité Bühlmann-Straub** | Tarification flotte et portefeuilles avec historique individuel. Écart estimé : 8–20% sur prime individuelle vs concurrent avec crédibilité. À intégrer dans A3 ou nouvel agent A3bis. | Élevé | Données réelles avec `id_assure` + historique multi-années. Référence : Bühlmann & Straub (1970) ASTIN ; Mack (1994) crédibilité actuarielle. |
| **Krigeage spatial / effets géographiques** | Lissage géographique par zone (krigeage simple ou GLM avec splines spatiales). Différenciateur vs Earnix/Radar Live qui l'ont nativement. À intégrer dans A3. | Élevé | Données réelles avec coordonnées GPS ou code IRIS. Variables `milieu_geographique` catégorielle insuffisante. Référence : Gelfand et al. (2010) Handbook of Spatial Statistics. |
| GLM sur triangles (Renshaw-Verrall) | Alternative stochastique au Chain Ladder standard. Présent dans ResQ, absent d'ActuarIA. | Élevé | — |
| Munich Chain Ladder — validation | Implémenté dans A7 mais non testé sur données réelles. | Moyen | Données réelles avec triangles paid + incurred. Référence : Quarg & Mack (2004) Blätter DGVFM. |
| Backtesting temporel complet A6 | Recalibrer le modèle sur chaque fenêtre walk-forward (vs test de stationnarité actuel). | Moyen | — |

---

## 🗓️ CALENDRIER CIBLE

| Phase | Contenu | Cible |
|---|---|---|
| **Phase 1** (actuelle) | Audit certificateur 5 directions + corrections P0/P1 | Juillet–Août 2026 |
| **Phase 2** | Données réelles NV + P2 Crédibilité + Krigeage | Septembre–Octobre 2026 |
| **Phase 3** | Migration React/FastAPI + Auth Supabase | Novembre 2026–Janvier 2027 |
| **Phase 4** | Export XBRL + Certification réglementaire formelle | T1 2027 |

---

## 📌 DÉCISIONS ACTÉES

- **Option B EIOPA TP.5.22** : σ²_total = σ²_Mack + σ²_modèle — approche validée, différenciateur vs ResQ/Addactis
- **CoC = 6% EIOPA** (Art. 77 §5) — pas 8%
- **IFRS 17 §B91** : RA par VaR P75 — standard PAA Non-Vie
- **Taux IFRS 17 bottom-up** : RFR + 60bps illiq premium
- **`LR_CTIP_ITT_MARCHE = 0.68`** : médiane CTIP 2023 — source de vérité
- **Tables TH0002/TF0002** : valeurs W-H officielles arrêté 27/07/2006 depuis `core/tables_mortalite.py`
- **Crédibilité Bühlmann-Straub** : inscrite roadmap P2, bloquée sur données réelles
- **Krigeage spatial** : inscrit roadmap P2, bloqué sur données réelles (GPS/IRIS requis)
