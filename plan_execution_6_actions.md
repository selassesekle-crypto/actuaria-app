# ActuarIA — Tarification Non-Vie
## Plan d'exécution : de 3 LoB cassées à 12 LoB tarifables

**Principe directeur, tiré de huit cycles d'audit :**

> Les 9 bloquants trouvés venaient tous d'une **désynchronisation entre listes**
> ou d'un **contrat implicite entre deux agents**. On ne les corrige pas un par
> un. On supprime la possibilité de les écrire.

---

## Étape 0 — Les invariants. **Avant** le code. (½ jour)

C'est la spec. Si un invariant ne passe pas, le code est faux — pas l'invariant.

Pour **chaque** garde-fou, deux invariants : ce qu'il doit **attraper**, et ce
qu'il ne doit **jamais casser**. Le second n'a jamais été écrit — c'est lui qui
a produit B5, B7 et B9.

| # | Invariant | Attrape |
|---|---|---|
| **INV-1** | `plan.colonnes_produites() ⊆ A2.transform(df).columns` | contrat A2→A3 rompu (les 9 variables perdues) |
| **INV-2** | `construire_matrice_x(plan.colonnes_produites(), df, cible) == plan.colonnes_produites()` | facteur déclaré détruit (B5, B7) |
| **INV-3** | une colonne genre **déclarée dans le plan** est **quand même** rejetée | le plan ne doit pas neutraliser la CJUE |
| **INV-4** | une fuite **déclarée dans le plan** est **quand même** rejetée par l'effet | le plan ne doit pas neutraliser l'anti-fuite |
| **INV-5** | pour chaque famille (GLM Poisson/Gamma/Tweedie, GBM, XGB, LGBM, DL) : ∃ un portefeuille sain → **VERT** | B8 (un GLM ne pouvait jamais être certifié) |
| **INV-6** | `\|gini_wf − gini_test\| / gini_test < 0,40` | B9 (spécification ou métrique divergente) |
| **INV-7** | `tarifer(contrat_i) ≈ prediction_portefeuille[i]` à 1e-6 | la fonction de scoring ne reproduit pas le modèle |
| **INV-8** | `Σ primes_pures ≈ Σ charge_observée` à ±1 % | déséquilibre technique (les +7 % actuels) |
| **INV-9** | la décennale se tarife **par YAML seul**, sans toucher au code | le test de vérité de l'architecture |

**Discipline non négociable :** chaque invariant est d'abord exécuté sur le code
**actuel** et doit **échouer**. Un invariant qui passe avant le correctif ne
teste rien. (INV-1, 2, 5, 6, 8, 9 échouent aujourd'hui.)

---

## Étape 1 — `core/plan_tarifaire.py` (1 jour) ✅ *écrit et testé*

**La source unique.** Remplace les quatre listes qui se désynchronisaient :

| Ancien | Nouveau |
|---|---|
| `A1.MOTS_CLES_DETECTION` | supprimée — l'actuaire déclare sa LoB |
| `A2.VARS_CATEGORIELLES` | `plan.config_encodage()` |
| `A3.VARS_GLM` | `plan.colonnes_produites()` |
| `core.FACTEURS_TARIFAIRES_AUTORISES` | `plan.colonnes_produites()` |

La méthode `colonnes_produites()` **est** le contrat A2→A3. A2 les crée, A3 les
attend, la conformité les autorise — depuis la **même fonction**.

```python
# La désynchronisation devient inexprimable
plan.colonnes_produites()
# → ('age', 'age_carre', 'bonus_malus', ..., 'garantie_tousrisques',
#    'carburant_diesel', 'carburant_electrique', 'csp_enc', 'usage_enc',
#    'antecedents_sinistres_n1', 'inter_age_bonus_malus')
```

**Points de conception à ne pas rater :**

- `modalites` **obligatoires** pour un one-hot → sinon le nom des colonnes est
  indéterminé, et le contrat A2→A3 redevient implicite. C'est le bug d'origine.
- `reference` : la modalité omise (base du one-hot). Sans elle, colinéarité
  parfaite avec la constante.
- `anteriorite: true` : exempte du contrôle par l'effet (critère V14). C'est la
  **seule** exemption, et elle est **déclarée**, donc traçable.
- `empreinte()` : SHA-256 du plan, à inscrire dans l'`audit_trail` et les trois
  rapports. **C'est ce qui rend le plan opposable devant l'ACPR.**

**Argument réglementaire, et il est décisif :** le plan déclaratif n'affaiblit
pas la conformité, il la **renforce**. On passe de « ActuarIA a codé la liste en
dur » à « l'actuaire a signé son plan de tarification, versionné et horodaté ».
C'est exactement ce que le régulateur demande.

---

## Étape 2 — A2 : `fit` / `transform` (1 jour) — **le pivot**

Aujourd'hui `A2.run(result_a1)` fait tout en une passe. **C'est ce qui rend le
scoring impossible.**

```python
class AgentA2Preprocessing:
    def fit(self, df: pd.DataFrame, plan: PlanTarifaire) -> "AgentA2Preprocessing":
        """Apprend UNIQUEMENT sur le portefeuille d'apprentissage.
        Fige : modalités, médianes d'imputation, bornes de winsorisation."""
        manquantes = plan.valider_contre(df.columns)
        if manquantes:
            raise ValueError(f"Fichier client incomplet : {manquantes}")
        self._plan = plan
        self._medianes = {...}      # imputation
        self._bornes = {...}        # winsorisation
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applique les MÊMES paramètres. Utilisable sur 1 contrat
        comme sur 1 million."""
        out = df.copy()
        for f in self._plan.facteurs:
            out = self._appliquer(out, f)
        # garantie : on produit EXACTEMENT ce que le plan annonce
        attendues = set(self._plan.colonnes_produites())
        assert attendues <= set(out.columns), attendues - set(out.columns)  # INV-1
        return out
```

**Deux effets, et ils sont énormes :**
1. `transform` sur un contrat neuf → **débloque l'action 4** (`tarifer`).
2. L'`assert` final **est** INV-1. Le contrat A2→A3 se vérifie à chaque appel.

⚠️ **Piège à éviter :** ne jamais recalculer les modalités dans `transform`. Une
modalité absente du contrat neuf → colonne one-hot à 0. Une modalité **inconnue**
→ lever, ne pas ignorer. (Le module a déjà payé cher les échecs silencieux.)

---

## Étape 3 — A3 : brancher sur le plan (½ jour)

```python
# AVANT
vars_prioritaires = VARS_GLM[sous_branche]        # ← désynchronisée
# ... puis le bloc d'extension '_enc' (source du BLOQUANT B1)

# APRÈS
vars_prioritaires = list(plan.colonnes_produites())
```

**Supprimer :**
- `VARS_GLM` (les 3 configs)
- le bloc d'extension `'_enc' in c` — il n'a plus de raison d'être : le plan dit
  tout
- le matching `key in sous_branche or sous_branche in key` — il n'existe plus de
  sous-branche à deviner

---

## Étape 4 — Conformité : la liste blanche devient le plan (½ jour)

```python
def construire_matrice_x(colonnes, plan, df, col_cible, contexte="") -> MatriceX:
    conformes = []
    for c in colonnes:
        # ① LISTE BLANCHE — désormais : « déclaré dans le plan signé »
        if c not in plan.colonnes_produites():
            exclusions[c] = "non declaree dans le plan de tarification"
            continue
        # ② GENRE — inchangé, agnostique à la LoB, NON contournable par le plan
        if _est_variable_genre(c):
            exclusions[c] = "variable de genre (CJUE C-236/09)"
            continue
        # ③ FUITE PAR LE NOM — inchangé
        if _est_derivee_sinistralite(c) and not _est_experience_passee(c):
            exclusions[c] = "derivee de la sinistralite observee"
            continue
        conformes.append(c)

    # ④ FUITE PAR L'EFFET — inchangé. Exemptions = celles DÉCLARÉES.
    fuites, alertes = detecter_fuites_par_effet(
        df, conformes, col_cible,
        cols_exemptees=plan.facteurs_anteriorite(),   # ← plus de devinette
    )
    ...
```

**Ce qui disparaît :** `FACTEURS_TARIFAIRES_AUTORISES`, `est_facteur_autorise()`,
la règle de préfixe (source de **B6**), les `MOTS_METRIQUES_INTERDITS`,
`facteurs_supplementaires` (code mort).

**Ce qui survit — et c'est le trésor :** le filtre genre, le contrôle par
l'effet, le critère d'antériorité, `MatriceX`, la source unique de restitution.
**Ces quatre-là sont agnostiques à la LoB.** Ils fonctionnent tels quels sur les
12 LoB. Tu ne jettes rien de ce qui t'a coûté huit cycles.

⚠️ **INV-3 et INV-4 sont ici.** Un actuaire qui déclarerait `sexe` ou
`prime_pure` dans son plan doit **quand même** être bloqué. Le plan autorise, il
ne dispense pas.

---

## Étape 5 — `tarifer(contrat)` (1 jour) — **le livrable commercial**

```python
@dataclass
class TarifNonVie:
    plan: PlanTarifaire
    a2: AgentA2Preprocessing        # fitté
    glm_frequence: GLMResultsWrapper
    glm_cout: GLMResultsWrapper
    ecretement: float
    chargements: dict

    def tarifer(self, contrat: dict, exposition: float = 1.0) -> dict:
        df = pd.DataFrame([contrat])
        X = self.a2.transform(df)[list(self.plan.colonnes_produites())]
        Xc = sm.add_constant(X, has_constant='add')

        freq = float(self.glm_frequence.predict(Xc)[0])        # taux annuel
        cout = float(self.glm_cout.predict(Xc)[0])             # cout moyen
        prime_pure = freq * cout * exposition

        pc = prime_pure * (1 + self.chargements['frais']) \
                        * (1 + self.chargements['marge']) \
                        / (1 - self.chargements['commission'])
        return {
            'frequence_annuelle': round(freq, 5),
            'cout_moyen': round(cout, 2),
            'prime_pure': round(prime_pure, 2),
            'prime_commerciale_ht': round(pc, 2),
            'prime_ttc': round(pc * (1 + self.chargements['taxes']), 2),
            'plan': self.plan.empreinte(),     # traçabilité
        }

    def grille(self, variable: str) -> pd.DataFrame:
        """Relativités exportables — ce que l'assureur met dans son SI."""
```

**INV-7** : `tarifer()` appliqué à un contrat du portefeuille doit reproduire à
1e-6 la prédiction du modèle. Sinon `transform` diverge de `fit`.

**C'est le point 5 qui vend.** Un prospect ne demandera jamais ton rapport de
certification. Il dira : *« tarifez-moi ce contrat »*.

---

## Étape 6 — Écrêtement, chargements, équilibre (1 jour)

**Écrêtement des graves** — indispensable en MRH (incendie) et RC Pro :

```python
seuil = df[cout].quantile(0.995)              # ou fixé par l'actuaire
cout_ecrete = df[cout].clip(upper=seuil)
charge_grave = (df[cout] - cout_ecrete).sum()
# → réintégrée en charge MOYENNE sur tout le portefeuille, pas au contrat
prime_grave_unitaire = charge_grave / df[exposition].sum()
```
Sans cela, ton GLM Gamma est piloté par trois sinistres. (Et c'est probablement
pourquoi `relativites_gamma` sort **vide** aujourd'hui.)

**Équilibre technique** — le +7 % actuel est inacceptable :

```python
k = df[cible_cout].sum() / (prime_pure_predite * df[exposition]).sum()
prime_pure_equilibree = prime_pure_predite * k       # INV-8 : |k − 1| < 0,01
```

**Chargements** : frais généraux, commission, marge, réassurance, taxes
(auto 33 %, MRH 30 %, RC 9 %). Déclarés dans le plan, pas codés en dur.

---

## Étape 7 — Le test de vérité (½ jour)

```python
def test_INV9_nouvelle_lob_sans_code():
    """Tarifer la décennale SANS toucher au code."""
    plan = PlanTarifaire.depuis_yaml("plans/decennale.yaml")
    tarif = pipeline_complet(portefeuille_decennale, plan)

    p = tarif.tarifer({
        'montant_travaux_eur': 850_000, 'nb_lots': 4,
        'anciennete_entreprise_ans': 12, 'type_ouvrage': 'Collectif',
        'qualification_entreprise': 'Qualibat', 'nature_marche': 'Prive',
        'sinistres_3ans_anterieurs': 0,
    })
    assert p['prime_ttc'] > 0
```

**Si ce test passe, tu couvres les 12 LoB.** S'il ne passe pas, tu as trois
démos — quel que soit le nombre de configs ajoutées.

---

## Ordre, effort, et ce qu'il ne faut surtout pas faire

| Étape | Effort | Débloque |
|---|---|---|
| 0 — Invariants | ½ j | la spec (tout le reste en dépend) |
| 1 — `PlanTarifaire` | 1 j | ✅ fait |
| 2 — A2 `fit`/`transform` | 1 j | **le scoring** + INV-1 |
| 3 — A3 sur le plan | ½ j | fin de `VARS_GLM` |
| 4 — Conformité déclarative | ½ j | **les 12 LoB** |
| 5 — `tarifer()` | 1 j | **le produit vendable** |
| 6 — Écrêtement / chargements / équilibre | 1 j | la crédibilité actuarielle |
| 7 — Décennale par YAML | ½ j | la preuve |

**≈ 6 jours.**

### Ce qu'il ne faut **pas** faire

- ❌ **Ne pas ajouter de config LoB.** Chaque config ajoutée est une dette de plus
  à resynchroniser. Le but est d'en avoir **zéro**.
- ❌ **Ne pas corriger B9, I7, I10, I11 avant l'étape 4.** Ils vivent dans du code
  qui va disparaître. (Sauf B9 — l'offset — qui reste, lui : `exposition` et
  `log_exposition` ne doivent **jamais** figurer dans `colonnes_produites()`. À
  inscrire comme garde dans `PlanTarifaire.__post_init__`.)

  > ⚠️⚠️ **CETTE INSTRUCTION ÉTAIT TROP ÉTROITE — corrigée au lot 1.2 (audit
  > d'août 2026).** La garde a été écrite exactement comme demandé ici, et elle
  > restait contournable : une **interaction** produit `inter_age_expo`, qui
  > n'est ni `exposition` ni `log_exposition`. Mesuré jusqu'à la prime :
  > **rapport 1,8339 au lieu de 2,0000** quand l'exposition double, soit
  > **−8,3 %**. *Ne pas ré-appliquer la formulation ci-dessus telle quelle* :
  > le contrôle doit porter sur la **propriété** — « cette déclaration
  > dérive-t-elle d'un rôle fixe ? » — sur les **trois** surfaces (nom source
  > du facteur, opérandes d'interaction, colonnes produites), et il vaut aussi
  > pour `cible_frequence` et `cible_cout`. Voir
  > `direction_non_vie/tarification/audit_2026_08/releve_plan_tarifaire.md`.
- ❌ **Ne pas faire les 12 LoB d'un coup.** Fais l'auto + la décennale. Si la
  décennale marche par YAML seul, les 10 autres sont un après-midi de YAML chacune.
- ❌ **Ne pas rester sur du synthétique.** À l'étape 7, fais tourner l'auto sur
  `freMTPL2freq` (CASdatasets, libre, 678 000 contrats auto français réels).
  L'exposition y est réellement dispersée — c'est exactement ce qui a fait
  exploser B9.

---

## Le mot de la fin

Ton architecture actuelle **sait** ce qu'est une voiture. C'est confortable pour
une démo, et c'est un mur pour un produit. Emblem, Radar, Akur8 et Earnix ne
savent rien de l'automobile — et c'est précisément pour ça qu'ils tarifent la
décennale, le maritime et le cyber.

**Tu n'atteindras pas les 12 LoB en ajoutant de la connaissance métier au moteur.
Tu les atteindras en la lui retirant.**
