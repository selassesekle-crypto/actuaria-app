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

> ✅ **`socle/C1`** · **FERMÉ le 01/09/2026 — ARBITRÉ PAR SELASSE, ET SON ARBITRAGE RENVERSE MA RECOMMANDATION DU 24/08** (« garder l'assiette, corriger la phrase »). Décision : **le seuil s'applique à CHAQUE SINISTRE individuellement, jamais au cumul d'un contrat sur l'année.**
>
> ⚠️⚠️ **ET LA MESURE DU 01/09 LUI DONNE RAISON PLUS FORT QUE MON RELEVÉ.** Sur `data/PG_2017_CLAIMS_YEAR0.csv` — **12 391 sinistres versionnés, une ligne = un sinistre** — sévérités réelles, fréquence balayée :
>
> ```
>   sin./contrat   vrais graves   RATES par l'assiette << total >>
>            1.1             37                                18
>            4.0            101                                76
>            8.0            198                               173
> ```
>
> **À 8 sinistres par contrat, l'assiette « total » rate 87 % des vrais sinistres graves.** Elle n'écrête pas les graves, elle écrête les NOMBREUX. Mon chiffre de 2,4 % portait sur la SÉVÉRITÉ moyenne — il était juste, et il regardait la mauvaise grandeur : ce qui bouge est la **charge mutualisée (+55 % à 6 sinistres/contrat)** et le nombre de graves **ratés**.
>
> ⚠️⚠️ **ET AUCUN CALCUL NE RATTRAPE ÇA DEPUIS LA DONNÉE AU CONTRAT.** Le coût MOYEN par sinistre (`cout/nb`), seule forme calculable sans montants individuels, n'attrape que **25 des 193** graves à 8 sinistres/contrat : *l'information du maximum n'est ni dans la somme, ni dans le compte.* D'où une **SOURCE déclarée au plan** — `cout_par_sinistre` — et jamais une reconstruction. Patron déjà validé quatre fois : `unite_exposition`, `Chargements`, `identifiant_contrat`, `echeance`.
>
> ⚠️ **AUCUN EURO NE BOUGE, ET C'EST ÉPINGLÉ PAR UN CHIFFRE, PAS PAR UNE PHRASE** : `SC-2` fige les trois grandeurs publiées sans la source sur la donnée réelle versionnée (seuil **7 390 EUR**, sévérité moyenne **950,95 EUR**, **56** contrats écrêtés), et `SC-3` vérifie que **0/20 plans** déclarent la source.
>
> Ce qui change sans la source, c'est ce que le rapport **DIT** : **18 contrats sur 56 (32 %)** sont écrêtés parce que NOMBREUX, et le seuil vaut **7,3 sinistres moyens** — mais **26,8 à 8 sinistres/contrat**. *Il croît avec la fréquence : c'est la mesure même du défaut.* ⚠️ Ce diagnostic vivait dans un `logger.info` d'A3 ; il est désormais dans `result_a3` et dans le rapport — la leçon de `services/C7`, fermée le matin même.
>
> Épinglé par `SC-1` à `SC-9` ; bump d'empreinte `s4` → **`s5`**, golden dans le MÊME commit.

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

## ⚠️⚠️ INSTRUIT LE 24/08/2026 — ET LA MESURE M'A RÉFUTÉ

**Selasse a demandé une recommandation motivée avant d'arbitrer. Elle est dans
[CARTE.md](CARTE.md#️️-lassiette-de-lécrêtement--ma-recommandation-motivée).
Ce qui suit corrige ce relevé.**

⚠️⚠️ **LE CHIFFRE −9,1 % CI-DESSUS EST JUSTE ET MAL CADRÉ.** C'est l'écart **sur
les contrats effectivement écrêtés**, pas la moyenne du segment — et il suppose
une sévérité **strictement constante**, régime où le quantile du total n'est
plus qu'un quantile du **nombre**. Mesuré sur `data/PG_2017_CLAIMS_YEAR0.csv`
(**14 243 sinistres versionnés, une ligne = un sinistre**, cv réel = **2,41**) :

```
  severite moyenne, par nombre de sinistres :  +0,44 % · -0,53 % · -1,01 % · -0,90 %
  prime pure                                :  +0,22 % · -0,63 % · -1,07 % · -0,95 %
  contrats ecretes sans porter un sinistre grave : 12 sur 55 (0,10 % du portefeuille)
```

Et sur toute la grille (fréquence 0,15→8, dispersion cv 0→2,5), **l'écart moyen
ne dépasse jamais 2,4 %**, et **change de signe** : négatif à basse fréquence,
positif à haute fréquence et forte dispersion. **Aucun des deux régimes n'est
uniformément prudent.**

⚠️ **Ma recommandation** : **garder l'assiette, corriger la phrase, publier
combien de contrats sont écrêtés parce que NOMBREUX plutôt que GRAVES (12/55 =
22 %).** Le gain plafonne à 2,4 % ; le coût est un **contrat de données
nouveau**. *Détail et motivation dans [CARTE.md](CARTE.md).*

*Preuves : `preuves/audit_ecretement.py` et `audit_ecretement_bis.py`.*

### Ce qui suit était mon analyse initiale — conservée, et corrigée ci-dessus

C'est un point de méthode actuarielle, pas un point de code :

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

> ✅ **`socle/C2`** · **FERMÉ le 01/09/2026 — NOMMÉ, pas supprimé.** Ce n'est pas du code mort : la couche est conçue pour être appelée par CELUI QUI APPELLE le pipeline, avant lui, et sa jonction est `pipeline_agents(rapport_mapping=...)` — dont le rapport voyage jusqu'aux trois livrables via `synthese_mapping`. **Aucun code de ce dépôt ne joue ce rôle**, et la docstring le dit désormais, avec la jonction attendue. ⚠️⚠️ ET LA MESURE A TROUVÉ PLUS QUE LE CONSTAT : **il existe un SECOND moteur de mapping, dans A1** — `_appliquer_mapping_client`, même métier, autre format (`{client_id}_mapping.json`), et A1 n'importe PAS ce module. *Deux moteurs pour un seul geste, et rien ne le disait.* Les unifier déplacerait un comportement : c'est nommé, pas tranché. `SO-1` et `SO-2` tiennent les deux phrases dans LES DEUX SENS.

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

> ✅ **`socle/C3`** · **FERMÉ le 01/09/2026 — et il ne se fermait PAS en retirant les symboles.** `DERIVATIONS` est LA TABLE que `sources_brutes` interroge ; `CibleSeverite` est LE TYPE DE RETOUR de `construire_cible_severite`, que ses trois appelants utilisent — ils lisent `.n_retenus`, `.seuil` — **sans jamais écrire son nom**. *Un symbole exporté sans consommateur n'est pas un défaut ; ne pas dire lequel des deux il est, si.* Chaque `__all__` porte son motif, et `SO-3` le tient dans les deux sens : si un consommateur externe apparaît, c'est le motif qui doit tomber.

### C — Deux docstrings que le code contredit (2)

**C4 — `proposer_mapping` promet une « Température 0 » que le fichier a
retirée.** L.178 : « *Température 0 pour la reproductibilité (même convention
que le reste du projet)* ». Mesuré :

> ✅ **`socle/C4`** · **FERMÉ le 01/09/2026.** La docstring promettait une « Température 0 pour la reproductibilité » que le fichier avait retirée le 07/08/2026 — **parce que le modèle la REFUSE** (400, « deprecated for this model »). Elle dit maintenant pourquoi `None` signifie « paramètre non transmis ». `SO-4` vérifie le TEXTE **et le FAIT** (`_TEMPERATURE_DEFAUT is None`), et son assiette est ce que la docstring ANNONCE, pas ce qu'elle CITE — même distinction qu'à `conformite/C9`.

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

> ✅ **`socle/C5`** · **FERMÉ le 01/09/2026.** Le FAIT était déjà épinglé par `test_apercu_caviarde` (T4 : la valeur du paramètre n'influence pas l'aperçu) ; c'est le TEXTE qui manquait — la docstring publique n'en disait **rien du tout**. Elle dit désormais que le paramètre est sans effet, pourquoi (le caviardage RGPD), et pourquoi il reste dans la signature. ⚠️ **Et il a un HOMONYME VIVANT** dans `nv_triangle_mapping_llm`, où deux fonctions le lisent vraiment : *un relevé par symbole ne voit pas l'homonyme.* `SO-5` porte sur le texte sans redire T4, `SO-6` tient l'homonyme.

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

---

**C6 — 49 imports payaient une surface publique que PERSONNE n'utilise :
importer `core.arrete` (233 l) en chargeait 4 429.**

> ✅ **`socle/C6`** · **CONSTAT NEUF, OUVERT ET FERMÉ le 03/09/2026 — premier
> lot de l'audit des 1 170 lignes « jamais auditées », ouvert par Selasse.**
>
> **Le constat.** `core/__init__.py` ré-exportait vingt symboles par des
> `from .x import y` exécutés **à l'import du paquet**. Or importer n'importe
> quel sous-module (`from core import arrete`) exécute ce fichier.
>
> ```
>   from core import arrete   AVANT : 6 modules, 4 429 lignes, 0,183 s
>                             APRES : 1 module,    233 lignes, 0,013 s
> ```
>
> ⚠️⚠️ **ET LA SURFACE AINSI PAYÉE A ZÉRO CONSOMMATEUR.** Relevé par AST sur
> tout le dépôt : **49 imports `from core import X`, et les 49 importent un
> SOUS-MODULE** (`arrete`, `frontiere_llm`, `traitement_ia`, `format_fr`…).
> Aucun n'importe un symbole d'`__all__`.
>
> ### *Une porte que personne ne franchit et que tout le monde paye.*
>
> ⚠️⚠️ **LE RÉ-EXPORT N'EST PAS SUPPRIMÉ, IL EST RENDU PARESSEUX (PEP 562),
> ET C'EST UNE DÉCISION.** Le dépôt est **public** : `from core import
> PlanTarifaire` peut vivre dans un carnet qu'on ne voit pas. *Retirer une API
> publique parce qu'aucun appelant INTERNE ne l'utilise, c'est mesurer sur la
> mauvaise assiette.* Le contrat est conservé à l'identique, le coût disparaît,
> et `SC6-6` fige la mesure qui a justifié ce choix — **le jour où un appelant
> interne utilisera la surface, il tombera, et ce sera le signal que la
> justification a changé.**
>
> **SECOND DÉFAUT, DANS LE FICHIER QUI SERT À DÉCLARER LA SURFACE.**
> `construire_lx` et `insee_qx_prospectif` étaient importés **sans figurer dans
> `__all__`**. Prouvé par exécution : joignables par `from core import X`,
> **invisibles** à `from core import *`. Les deux sont vivants (`a14_mortalite`,
> `v1_tarification_deces`). *Une surface déclarée qui ment sur la surface
> réelle.* `import *` passe de **18 à 20** symboles.
>
> ⚠️ **`__all__` RESTE UN LITTÉRAL, ET C'EST `PLE0605` QUI A RAISON** : un
> `__all__` calculé est invisible à l'outillage statique. La divergence est
> interdite par `SC6-1`, sur le patron du golden d'`EMPREINTE_SCHEMA`.
> *Ce qui doit rester lisible se déclare ; ce qui doit rester vrai se teste.*
>
> ⚠️ **`SC6-2` MESURE DANS UN INTERPRÉTEUR NEUF** : dans celui de la gate, les
> modules sont déjà chargés par les tests voisins et la mesure ne prouverait
> rien. *Un témoin contaminé par ses voisins ne mesure que ses voisins.*
>
> ⛔ **ET JE ME SUIS TROMPÉ DE NUMÉRO, LA SECONDE FOIS DE LA SESSION.** J'avais
> écrit `socle/C3` — **qui existe déjà** et désigne un autre constat. La
> collision est pire qu'un trou : corrigée sur 15 mentions avant la gate.
>
> ═══ CE QUE CE LOT MESURE AUSSI, ET QUI RÉFUTE LA CARTE ═══
>
> La carte annonçait `core/__init__.py` à **42 l** et `excel_helpers.py` à
> **139 l** ; mesuré : **41** et **166**. *Les comptes de la carte sont
> périmés* — le total « 1 170 » est approximatif.
>
> Épinglé par `SC6-1` à `SC6-6`. Sceau : six violations plantées, cinq
> tombent, et la sixième — un import avide remis dans un **commentaire** — ne
> tombe pas.

---

**C7 — Une bibliothèque absente se disait « le modèle n'a pas convergé » : le
rapport signé affirmait une chose FAUSSE sur la donnée de l'actuaire.**

> ✅ **`socle/C7`** · **CONSTAT NEUF, OUVERT ET FERMÉ le 03/09/2026 —
> troisième et dernier lot de l'audit des 1 170 lignes « jamais auditées ».**
>
> **Le constat.** `_ajuster_logit` rendait le **même tuple**
> `(None, None, None, False, None)` dans **quatre** situations, dont l'absence
> de `statsmodels`. L'appelant publiait pour toutes :
>
> > « L'ajustement du modèle de résiliation n'a pas convergé »
>
> **Prouvé par exécution** : `statsmodels` rendu introuvable, le rapport
> annonçait une **non-convergence du modèle** — c'est-à-dire une affirmation
> sur **la donnée de l'actuaire**, pour une cause qui lui est totalement
> étrangère.
>
> ### *Un contrôle qui n'a pas eu lieu le DIT ; il ne se confond pas avec un contrôle qui n'a rien trouvé.*
>
> C'est `conformite/C1` et `qualite/C9`, la même leçon un étage plus bas.
>
> **Le correctif** : quatre causes nommées, un motif par cause en **source
> unique**. Celui de l'outil absent **disculpe explicitement la donnée** :
> *« Aucune conclusion ne peut être tirée de cette absence sur le comportement
> de votre portefeuille. »* `EC-2` tient les deux sens — les trois autres
> motifs, eux, parlent bien du **modèle**.
>
> Épinglé par `EC-1`, `EC-2`, `EC-3`.

---

**C8 — `SOURCES_ADMISES` existait « pour empêcher qu'une règle maison passe
pour une obligation », et RIEN ne l'appliquait.**

> ✅ **`socle/C8`** · **CONSTAT NEUF, OUVERT ET FERMÉ le 03/09/2026.**
>
> **Le constat.** Mesuré : `SOURCES_ADMISES` avait **zéro usage interne, zéro
> import**. Le champ `Exigence.source` portait le commentaire « l'un de
> `SOURCES_ADMISES` », et une exigence déclarant `source='IFRS 17 §32'` serait
> entrée **sans un mot**.
>
> ### *Une contrainte écrite dans un commentaire n'est pas une contrainte ; c'est une intention.*
>
> ⚠️⚠️ **ET C'EST LE MOTIF QUE CE MODULE POURSUIT LUI-MÊME.** Son en-tête
> insiste qu'**aucun texte réglementaire ne fixe une élasticité-prix**.
> Laisser passer une source normative inventée aurait donné à une convention
> maison **l'apparence d'une obligation**, dans un document signé.
>
> **Le correctif** : `_exigence()`, seule porte d'entrée du catalogue, qui
> **vérifie** la source et lève. ⚠️ `EC-5` tient les **deux** moitiés — que les
> sources soient admises, **et** que toutes les entrées passent par la porte.
>
> ⛔ **LE SCEAU A DÉMASQUÉ CE CONTRÔLE.** Sa première version ne vérifiait que
> l'**état final** : une entrée écrite `Exigence(...)` au lieu de
> `_exigence(...)` contournait la porte et passait. *Un contrôle qui lit
> l'état final ne voit pas la porte qu'on a contournée pour l'atteindre.*
>
> ═══ CE QUE CE LOT A MESURÉ SANS TROUVER DE DÉFAUT ═══
>
> ⚠️⚠️ **ET J'AI DÛ ME CORRIGER SUR `_et`.** Je l'avais annoncée **morte** à
> Selasse, sur une marche d'atteignabilité qui ne suivait que les corps de
> fonctions. **Elle est appelée QUATRE FOIS au niveau module**, à la
> construction d'`EXIGENCES`. *Une mesure qui ignore le code exécuté à
> l'import déclare morte une fonction vivante.*
>
> ⚠️ Restent nommés, non traités sur ce module : **`sensibilite_tarifaire` est
> calculée puis lue par personne** (forme de `socle/C2`, sur une vraie
> computation), et **6 des 8 fonctions publiques n'ont aucun importateur
> externe** — elles sont internes, et publiques sans nécessité.
>
> Épinglé par `EC-4` et `EC-5`. Sceau (commun à `C7` et `C8`) : six violations
> plantées, cinq tombent, et la sixième — la cause nommée dans un
> **commentaire** — ne tombe pas.
