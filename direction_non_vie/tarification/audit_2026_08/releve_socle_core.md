# RELEVÉ — LE SOCLE `core` : `derivations` · `severite` · `mapping_client` · `mapping_llm`

**Lus intégralement** : `core/derivations.py` **60 l** · `core/severite.py`
**130 l** · `core/mapping_client.py` **220 l** · `core/mapping_llm.py` **199 l**
— **609 lignes**. Aucun échantillon, aucun filtre. Septième et dernier fichier
du relevé ②.

Quatre fichiers qui se disent chacun **source unique** de quelque chose.
⚠️ **Aucun appel à l'API n'a été fait** : le caviardage est mesuré localement,
le reste par AST.

## ① Le compte

**22 affirmations mesurées** — **5 constats** · **17 vérifiées bonnes**.

C'est, de loin, **le meilleur rapport constats/vérifiées des sept relevés**.

## ② Le classement

### A — Un point de méthode que je ne tranche pas (1)

**C1 — L'écrêtement porte sur le TOTAL DU CONTRAT ; la docstring dit « un
SINISTRE ».** `severite.py` l.51 : « *Quantile des coûts au-delà duquel **un
sinistre** est dit GRAVE* ». Le code l.110 calcule
`cout[cout > 0].quantile(0.995)` où `cout` est le **coût total du contrat**.
Mesuré sur une flotte où **chaque sinistre coûte exactement 800 €** :

```
  flotte : 3,97 sinistres/contrat, CHAQUE sinistre = 800 EUR
  seuil d'ecretement (q0,995 du cout TOTAL par contrat) = 8 000 EUR
     soit 10 sinistres -- aucun sinistre n'est grave, ils sont tous a 800 EUR

  n_graves = 12 contrats ecretes
  ex. nb=11  cout total=8 800  cout PAR SINISTRE reel = 800
      severite RETENUE = 727,27   (= seuil / 11)

  charge reinjectee = 3,40 EUR / unite d'exposition
```

**Douze contrats sont écrêtés « comme graves » alors qu'aucun sinistre ne l'est.**
Ce qui est écrêté sur ce portefeuille n'est pas la **sévérité**, c'est la
**fréquence** : la sévérité des contrats nombreux est mécaniquement abaissée
(727,27 € au lieu de 800 €), et l'excédent part dans
`prime_grave_unitaire` — donc mutualisé au lieu d'être porté par les contrats
qui le génèrent.

⚠️⚠️ **JE NE TRANCHE PAS, ET JE VOUS LE RENDS.** C'est un point de méthode
actuarielle, pas un point de code :

- La donnée du dépôt est **au contrat** (`cout_total_sinistres`, `nb_sinistres`)
  — **un écrêtement par sinistre n'y est pas calculable**. L'implémentation fait
  donc la seule chose que la donnée permet.
- Mais la décomposition qu'elle sert, `E[S] = E[N] × E[C|N>0]`, suppose que
  l'écrêtement porte sur `C`. Sur un portefeuille à forte fréquence, il porte en
  partie sur `N`.
- Le dépôt contient `flotte_automobile.yaml` — le régime où cela se produit.

⚠️ **Sans conséquence sur la charge totale** : la conservation est exacte
(voir D). C'est la **répartition** entre relativités et mutualisation qui est en
jeu, pas le niveau.

### B — Complet, validé, et câblé nulle part (2)

**C2 — Le moteur de mapping — 419 lignes, deux fichiers — n'a aucun appelant de
production.** Relevé par AST :

```
  [CONSTAT] preparer_fichier_client   production=0  tests=1
  [CONSTAT] appliquer_mapping         production=0  tests=1
  [CONSTAT] valider_mapping           production=0  tests=1
  [CONSTAT] charger_mapping           production=0  tests=1
  [CONSTAT] proposer_mapping          production=0  tests=1
  [CONSTAT] MappingIncoherent         production=0  tests=2
  [CONSTAT] MappingLLMIndisponible    production=0  tests=1

            synthese_mapping          production=3   <-- les 3 livrables
```

⚠️ **C'est DÉCLARÉ, et cela change tout** : `preparer_fichier_client` écrit
elle-même « *à surfacer à côté des livrables (câblage = couche 2)* ». Le
non-câblage est un état annoncé, pas une omission — contrairement à
`pipeline_agents.py` (relevé ⑥), qui décrit ses défauts au passé.

⚠️ **Mais la plomberie d'aval est déjà là** : `synthese_mapping` est appelée par
les **trois livrables**, et `rapport_mapping` est un paramètre d'A6. **Les
rapports savent afficher un rapport de mapping que rien ne produit.**

**C3 — Deux symboles exportés sans consommateur.** `DERIVATIONS` (production 0,
tests 1) et `CibleSeverite` (production **0**, tests **0**) figurent dans les
`__all__` de leurs modules. `CibleSeverite` est le type de retour de
`construire_cible_severite`, qui a trois appelants : ils l'utilisent sans jamais
le nommer. Sans gravité — mais un `__all__` annonce une interface.

### C — Deux docstrings que le code contredit (2)

**C4 — `proposer_mapping` promet une « Température 0 » que le fichier a
retirée.** L.178 : « *Température 0 pour la reproductibilité (même convention
que le reste du projet)* ». Mesuré :

```
  _TEMPERATURE_DEFAUT (l.51) = None
  defaut du parametre        = None
  [CONSTAT] la docstring dit « Température 0 pour la reproductibilité » : True
```

Et le commentaire l.45-49, **130 lignes plus haut dans le même fichier**, dit
l'inverse : « *⚠️ TEMPERATURE RETIRÉE — MESURÉ CONTRE L'API le 2026-08-07 : ce
modèle REFUSE le paramètre (400, « deprecated for this model »)* ». Le correctif
a été fait, l'API publique ne l'a pas suivi.

**C5 — `n_lignes_exemple` est un paramètre public sans effet, et la docstring
n'en dit rien.** Signature : `n_lignes_exemple: int = 5`. Première ligne de la
fonction qui le reçoit : `del n_lignes_exemple  # conservé pour l'API, sans
effet`. La docstring publique ne le mentionne **pas du tout** — un appelant qui
le règle à 50 croit élargir l'aperçu.

### D — Vérifié comme BON (17)

| affirmation | mesure |
|---|---|
| `derivations` — « **miroir EXACT** de `a2._calculer_indicateurs_derives` » | **9 déclarées, 9 produites, identiques** — exécuté contre A2 |
| `sources_brutes` — récursif | `logement_ancien` → **`annee_construction`** (2 niveaux) |
| `sources_brutes` — ordre préservé, dédupliqué | `[km_par_an_normalise, jeune_conducteur]` → `[kilometrage_annuel, exposition, age]` · `[jeune, senior]` → `[age]` |
| `sources_brutes` — une brute passe telle quelle | `[age, colonne_inconnue]` → inchangé |
| aucun cycle dans la table | **0** (le code n'a pas de garde de récursion — la table la rend inutile) |
| le test de cohérence annoncé l.18-20 | **existe** : `direction_non_vie/tarification/test_derivations.py` |
| `severite` — **la charge écrêtée est CONSERVÉE** | écrêtée + grave − totale = **1,164e-10** sur 660 207,50 € |
| la cible est le **coût par sinistre**, jamais le total | contrat à 2 sinistres : sévérité **841,17** = min(coût, seuil)/2 |
| le masque exige un coût **OBSERVÉ** | 50 contrats `nb>0` / `coût=0` → `n_retenus` **449 → 399** ; **aucune sévérité nulle** (min 26,50) |
| le seuil **FOURNI** est appliqué sans recalcul (piège V9) | train **5 287,70** · test ré-appris 5 402,77 · test **fourni → 5 287,70** |
| A3 a cessé de diverger | `_calibrer_gamma` (l.989) **appelle `construire_cible_severite`** et ne fait **aucun** masquage/écrêtement sur place |
| `construire_cible_severite` est bien la source unique | **3 appelants de production** : `a3_glm`, `pipeline_agents`, `pipeline_tarifaire` |
| `mapping_client` — les incohérences sont levées | **4/4** : autre LoB · cible inconnue · collision de cible · doublon créé au renommage |
| le rapport de mapping est complet | correspondances **mortes**, colonnes client **non mappées**, colonnes plan **non couvertes**, `ampute_previsionnel` |
| rétro-compatibilité | `chemin=None` → **le df d'origine**, rapport **None** |
| **le caviardage tient** | 5 valeurs uniques plantées (IBAN, e-mail, téléphone, nom, nombre à 21 chiffres) → **0 dans l'aperçu, 0 dans le prompt entier** (1 315 caractères) |
| `mapping_llm` dégrade proprement | `anthropic` **absent des imports de module** ; df vide, texte sans JSON, JSON non parsable, JSON non-objet → **`MappingLLMIndisponible`**, message actionnable |

⚠️ **Sur le caviardage, le détail vaut d'être écrit** : ni les valeurs, ni les
dates, ni même `50.0` ne traversent. L'aperçu ne transmet que **nom, type,
cardinalité et un profil de forme** :

```
  - iban : str | texte, 1 valeurs distinctes
  - BM   : float64 | décimal, 4 valeurs distinctes
  (Les valeurs du fichier ne sont pas transmises : seules leur forme
   et leur cardinalite le sont)
```

⚠️ Et le modèle annoncé est le bon : la docstring dit « Claude Sonnet », le code
utilise `frontiere_llm.MODELE_RECENT` = **`claude-sonnet-5`**.

## ③ Ce que je ne tranche pas ici

**Rien n'est resté non lu** : 609 lignes, intégralement.

- **C1, l'assiette de l'écrêtement**, est rendu à l'arbitrage — voir ci-dessus.
- **La mesure `~9 100 contrats freMTPL2 avec ClaimNb > 0 sans montant`**
  (`severite.py` l.87-88) n'est pas reproductible ici : le jeu de données réel
  est hors du dépôt. J'ai vérifié le **mécanisme** (un coût nul avec `nb>0` est
  bien écarté), pas le **chiffre**.
- **La mesure `32 178 € au lieu de 36 797 € (−12,6 %), Σprimes/Σcharge = 0,85`**
  (en-tête de `severite.py`) porte sur un portefeuille décennale 100k à
  structure causale connue, que je n'ai pas reconstruit. J'ai vérifié que **la
  divergence qu'elle décrit est fermée** (A3 utilise la source unique).

## ④ Les preuves

- `preuves/audit_socle.py` — le miroir `derivations`↔A2, `sources_brutes`
  (récursion, ordre, dédup, cycles), la conservation de la charge écrêtée, le
  masque, le seuil train/test, et les quatre incohérences de mapping.
- `preuves/audit_socle_bis.py` — le caviardage (5 valeurs plantées), les deux
  docstrings, les dégradations de `mapping_llm`, la sémantique du seuil sur une
  flotte, la propagation **par AST**, et `_calibrer_gamma`.

Chacune se relance seule. ⚠️ **Aucune n'appelle l'API.**

---

**Mon appréciation d'ensemble.** Ces quatre fichiers sont **ce que le module a
de meilleur**. `derivations` est un miroir exact, vérifié par exécution contre
A2. `severite` conserve la charge à **1,16e-10**, applique le seuil du train au
test sans recalcul, exige un coût observé — et la divergence qui coûtait 15 % de
tarif est **fermée**, A3 utilisant désormais la source unique sans rien
recalculer. `mapping_client` refuse **quatre** incohérences sur quatre. Et
`mapping_llm` ne laisse **rien** passer du fichier client : cinq valeurs uniques
plantées, aucune ne sort, ni dans l'aperçu ni dans le prompt entier.

⚠️ **Le seul point grave n'est pas un défaut de code, c'est une question
d'assiette actuarielle** : l'écrêtement porte sur le total du contrat parce que
la donnée est au contrat, et la docstring l'appelle « un sinistre ». Sur une
flotte, cela écrête la fréquence en croyant écrêter la sévérité. **Je vous le
rends.**

⚠️ **Et deux docstrings contredisent leur propre fichier** — la température
« 0 » retirée 130 lignes plus haut, et un paramètre public supprimé dès la
première ligne. Le motif du chantier, dans sa forme la plus bénigne : *le code a
été corrigé, le texte qui le décrit ne l'a pas été.*
