"""
direction_non_vie/tarification/pipeline_tarifaire.py — LE PRODUIT VENDABLE.

Assemble, à partir d'un PlanTarifaire SIGNÉ et d'un portefeuille, le tarif
complet — sans connaître la moindre LoB. C'est ce qui répond à « tarifez-moi ce
contrat » (étape 5) et ce qui tarife la décennale par YAML seul (étape 7).

Chaîne :
    A2.fit(df, plan).transform(df)                 → contrat A2→A3 (INV-1)
    construire_matrice_x(..., plan=plan, df, cible) → conformité déclarative (INV-2/3/4)
    GLM fréquence (Poisson, offset log-exposition)
    GLM coût moyen  — FAMILLE DÉCLARÉE DANS LE PLAN (plan.famille_severite)
    écrêtement des graves + coefficient d'équilibre (étape 6, INV-8)
    → TarifNonVie.tarifer(contrat)                 → reproduit le portefeuille (INV-7)
      ⚠️ VRAI DEPUIS LE 05/09/2026 SEULEMENT, ET C'EST UN CHANGEMENT DE PRIX.
      `tarifer()` retenait UN AN dès que l'appelant se taisait, **même quand
      le contrat déclarait sa durée** : 299 contrats sur 300 divergeaient du
      chemin vectoriel, écart médian +39,90 EUR. Le silence de l'appelant veut
      désormais dire « prends l'exposition du contrat ». Un an n'est supposé
      que si PERSONNE ne la déclare — et cela se dit.
      Voir `predire_portefeuille` et `test_deux_chemins_du_prix`.

Rien ici ne « sait » ce qu'est une voiture ou un chantier : tout vient du plan.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
import dataclasses
# ⚠️ `families` n'est plus importé ici : la seule construction de famille de ce
# module était celle du GLM de fréquence, partie dans `core/frequence.py` avec
# le reste du moteur. *Un import qui survit à son usage devient une piste
# fausse pour qui cherche où le modèle est ajusté.*

from core.plan_tarifaire import CHARGEMENTS_DEFAUT, PlanTarifaire
from core.conformite_reglementaire import construire_matrice_x, source_exposition
from core.frequence import ajuster_glm_frequence
from core.validation_tarif import (
    MINIMUM_POUR_INTERVALLE,
    gini_lorenz as gini_socle,
    mesurer_discrimination,
    publication as publication_validation,
    valider,
)
# ⚠️ `QualiteBloquante` n'est plus importée ici : la levée a suivi le préambule
# dans `core.qualite_donnees`. Vérifié avant de la retirer — **aucun module ne
# l'importait DEPUIS ce fichier** (mesuré). *Un ré-export tacite se casse en
# silence ; celui-ci n'existait pas.*
from core.qualite_donnees import preambule_qualite
# ⚠️⚠️ LES PRIMITIVES DE SEVERITE VIVENT DESORMAIS DANS `core/severite.py`.
# Elles etaient ici, dans la direction, et A3 -- l'autre moteur -- codait la
# famille Gamma EN DUR faute de pouvoir les atteindre. *Deux chemins qui
# ajustent la meme grandeur avec deux codes finissent par diverger.*
from core.severite import (ModeleCout, ajuster_glm_cout,
                           construire_cible_severite, seuil_declare)
from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing

# ⚠️ Le journal de la zone, au nom de la famille `actuaria.*` déjà en place
# (`core/conformite_reglementaire.py`). Il n'est PAS réglé ici : régler un
# niveau au niveau module éteindrait le journal de l'appelant au seul fait
# d'importer ce fichier — c'est le défaut que `core/test_journaux_importables`
# verrouille. On se contente d'obtenir le journal, jamais de le configurer.
logger = logging.getLogger('actuaria.tarif.pipeline')

# ⚠️⚠️ `CHARGEMENTS_DEFAUT` N'EST PLUS DÉFINI ICI — IL EST IMPORTÉ DU SOCLE.
# Il portait quatre littéraux qui doublaient EXACTEMENT les valeurs par défaut
# de `core.plan_tarifaire.Chargements` (frais 0,15 · commission 0,10 · marge
# 0,03 · taxes 0,33, vérifié par exécution). *Deux listes de quatre littéraux
# finissent par diverger ; une dérivation ne le peut pas.*
#   Le nom reste atteignable ICI, et c'est délibéré : `test_portes_du_plan` et
#   les preuves d'audit le lisent sous ce chemin. Ce n'est donc pas un
#   ré-export tacite — c'est celui-là même que le module utilise, à quatre
#   endroits ci-dessous.


# ══════════════════════════════════════════════════════════════════════════════
#  GLM de COÛT MOYEN — la famille est DÉCLARÉE, plus codée en dur (schéma étendu)
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
#  TarifNonVie — le livrable commercial (étape 5)
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class TarifNonVie:
    plan: PlanTarifaire
    a2: AgentA2Preprocessing          # fitté sur le portefeuille
    glm_frequence: Any                # GLMResults (Poisson, offset log-expo)
    glm_cout: ModeleCout              # famille déclarée dans le plan
    features: List[str]               # colonnes conformes réellement ajustées
    ecretement: float = 0.0           # prime de graves unitaire (étape 6)
    coefficient_equilibre: float = 1.0  # k (INV-8)
    chargements: Dict[str, float] = field(default_factory=lambda: dict(CHARGEMENTS_DEFAUT))
    # Rapport de la couche qualité (exclusions/corrections/signalements) — surfacé
    # dans les livrables, jamais un traitement silencieux. None si la couche n'a
    # pas tourné (ex. appelée hors pipeline_complet).
    rapport_qualite: Optional[Any] = None
    #: ⚠️⚠️ CE QUE LE TARIF SAIT DE LUI-MÊME — lot 14. Cet objet portait le
    #: plan, deux GLM, un écrêtement et des chargements : **aucun Gini, aucun
    #: statut, aucun garde-fou**. Le pouvoir discriminant de ses modèles vivait
    #: chez A3, dans un rapport qu'il ne lit pas. *Un objet qui produit un prix
    #: sans savoir ce que vaut son modèle ne peut pas refuser de le produire.*
    #: `None` = la validation n'a pas été mesurée (appel hors
    #: `pipeline_complet`) — ce n'est pas « aucun défaut ».
    validation: Any | None = None

    # ── Prédiction interne, partagée par tarifer() et le portefeuille (INV-7) ──
    def _design(self, df: pd.DataFrame) -> pd.DataFrame:
        X = self.a2.transform(df)
        return sm.add_constant(X[self.features], has_constant="add")

    def _taux_frequence(self, Xc) -> np.ndarray:
        # offset=0 → taux annuel PAR UNITÉ d'exposition (la prime le remultiplie).
        return np.asarray(
            self.glm_frequence.predict(Xc, offset=np.zeros(len(Xc))), dtype=float)

    def predire_portefeuille(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prédictions vectorisées sur un portefeuille — **le même prix** que
        `tarifer()` sur le même contrat, depuis le 05/09/2026.

        ⚠️⚠️ CE N'ÉTAIT PAS VRAI, ET LA PHRASE L'AFFIRMAIT QUAND MÊME. Elle
        disait « MÊME chemin que `tarifer()` ». Mesuré : ici l'exposition vient
        de la COLONNE du portefeuille (`df[plan.exposition]`) ; dans
        `tarifer()`, l'appelant silencieux obtenait `EXPO_ANNUELLE = 1,0`
        **même quand le contrat déclarait sa durée**. Sur 300 contrats de
        `auto` : **299 divergeaient de plus d'un centime**, écart médian
        **+39,90 EUR**, maximum **402,43 EUR**.

        ⚠️ **ET AUCUN ORACLE N'EXERÇAIT LE CAS QUI DIVERGEAIT.** `INV-7a`
        compare le chemin vectoriel À LUI-MÊME ; `INV-7b` compare bien la
        paire, mais **en passant `exposition=float(row["exposition"])`** —
        donc dans le seul cas où elle s'accordait. *Un oracle qui ne traverse
        pas le cas ne le couvre pas.* `test_deux_chemins_du_prix` ferme ce
        trou, et `DC-2` exige désormais la COÏNCIDENCE.

        ⚠️⚠️ IL RESTE UN CAS OÙ LES DEUX DIFFÈRENT, ET IL EST DÉCLARÉ : quand
        le contrat ne porte AUCUNE exposition, `tarifer()` en suppose une d'un
        an et le DIT. Cet écart-là n'est pas une simple mise à l'échelle de
        durée : `a2` dérive `kilometrage_annuel / max(exposition, 0,01)`, un
        PRÉDICTEUR — sur `auto`, le prix supposé ne se corrige pas en le
        multipliant par la durée réelle (rapport réel 1,1538 contre 1,1420
        pour la durée seule, **jusqu'à 128,11 EUR**). Sur les plans sans
        facteur dérivé (`mrh`, `rcpro`, `flotte_automobile`), il s'y corrige
        **exactement**.

        ⚠️⚠️ CONSTAT `pipeline/C7` — LA PRÉCISION ANNONCÉE N'ÉTAIT PAS
        OBSERVABLE SUR LA SORTIE DE `tarifer()`. Cette phrase promettait « que
        l'un reproduise l'autre à 1e-6 » ; or `tarifer()` **arrondit
        `prime_pure` à deux décimales** (l.265). *Une promesse au milliardième
        sur un nombre publié au centime ne peut pas être vérifiée par celui qui
        la lit.*

        Ce qui est vrai, et ce que l'oracle du dépôt mesure réellement : **les
        deux chemins sont le MÊME calcul** — `_design` puis `_taux_frequence`
        puis `glm_cout` — et c'est cette identité qui vaut 1e-6, entre valeurs
        NON arrondies. `test_scoring_unitaire_reproduit_le_portefeuille_a_1e6`
        compare le chemin vectoriel à lui-même ; l'écart mesuré entre
        `tarifer()` et ce chemin est **0,0036 €** sur 6 contrats — l'arrondi au
        centime, rien de plus.
        ⚠️ **ET CE 0,0036 € A CHANGÉ DE PORTÉE DEUX FOIS EN UN JOUR** — il est
        relu à chaque fois, plutôt que laissé derrière. Il valait pour un
        appelant qui FOURNIT l'exposition ; l'appelant silencieux, lui,
        obtenait +39,90 € d'écart médian. Depuis le cas (a), **il vaut pour
        les deux** : le silence prend la durée du contrat. Il ne cesse de
        valoir que dans le cas (b) — aucune durée nulle part — où l'écart
        n'est plus un arrondi mais une hypothèse, et elle est déclarée.
        *Un chiffre publié se relit chaque fois que le comportement qu'il
        décrit change.*

        ⚠️ *L'oracle était juste ; c'est la phrase qui promettait au-delà de ce
        qu'elle pouvait montrer.* (INV-7)
        """
        Xc = self._design(df)
        expo = pd.to_numeric(df[self.plan.exposition], errors="coerce").to_numpy(dtype=float)
        freq = self._taux_frequence(Xc)
        cout = self.glm_cout.predict(Xc)
        prime_pure = self.coefficient_equilibre * (freq * cout + self.ecretement) * expo
        return pd.DataFrame({
            "frequence_annuelle": freq, "cout_moyen": cout,
            "prime_pure": prime_pure, "exposition": expo,
        }, index=df.index)

    def anomalies_du_contrat(self, contrat: dict) -> list:
        """Ce qui, dans ce contrat, n'est pas LISIBLE au regard du plan signé.

        ⚠️⚠️ CONSTAT `pipeline/C1`. `tarifer()` acceptait n'importe quoi et
        rendait un prix sans un mot. Mesuré sur un contrat de référence à
        28,50 € :

            bonus_malus = 'beaucoup'   ->  64,99 €   success=True   +128 %
            bonus_malus = ''           ->  64,99 €   success=True   +128 %
            bonus_malus = None         ->  64,99 €   success=True   +128 %
            bonus_malus = -999         ->  22,96 €   success=True   -19,4 %
            bonus_malus = 1e12         ->  149,79 €  success=True   +425,6 %

        **Les trois premières rendent LA MÊME prime** : elles sont coercées
        vers le même repli — l'imputation d'A2. *Le souscripteur reçoit la
        prime du contrat MOYEN en croyant tarifer le sien, et rien ne le
        signale.*

        ⚠️ Le plan porte déjà la vérité : un facteur `categoriel` déclare ses
        **modalités figées**, un `continu` attend un nombre. On ne devine
        rien — on compare au plan signé, comme A2 le fait déjà en refusant
        une modalité inconnue (piège V9).

        ⚠️⚠️ ELLE JUGE DESORMAIS LA PLAUSIBILITE — MAIS SEULEMENT CE QUE LE
        PLAN DECLARE. `bonus_malus = -999` et `1e12` sont *lisibles* : aucune
        borne ne les refusait, et **aucune borne n'était déclarable**.
        `Facteur.bornes` existe depuis le 31/08/2026.

        *Le plan déclarait le TYPE d'un facteur continu, jamais son DOMAINE* —
        exactement la forme d'`unite_exposition`, qui déclarait le RÔLE de
        l'exposition et jamais son UNITÉ.

        ⚠️ AUCUNE BORNE N'EST INVENTÉE ICI : ce sont des choix actuariels qui
        demandent une source. Facteur sans borne déclarée = comportement
        d'aujourd'hui, à l'identique. **0/20 plans en déclarent : aucun euro
        ne bouge le jour de la pose.**
        """
        anomalies = []
        for f in self.plan.facteurs:
            if f.nom not in contrat:
                continue                       # absence = amputation, autre sujet
            valeur = contrat[f.nom]
            if f.type == 'categoriel' and f.modalites:
                if valeur not in f.modalites:
                    anomalies.append(
                        f"facteur '{f.nom}' : modalite {valeur!r} INCONNUE — "
                        f"le plan declare {list(f.modalites)}. Tarifer "
                        f"reviendrait a imputer une valeur que l'assure n'a "
                        f"pas fournie.")
                continue
            if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
                anomalies.append(
                    f"facteur '{f.nom}' : valeur ABSENTE ({valeur!r}) — elle "
                    f"serait imputee, et la prime rendue serait celle du "
                    f"contrat MOYEN, pas celle de ce contrat.")
                continue
            try:
                x = float(valeur)
            except (TypeError, ValueError):
                anomalies.append(
                    f"facteur '{f.nom}' : valeur ILLISIBLE ({valeur!r}) — un "
                    f"facteur numerique attend un nombre. Elle serait imputee "
                    f"en silence.")
                continue
            if not math.isfinite(x):
                anomalies.append(
                    f"facteur '{f.nom}' : valeur non finie ({valeur!r}).")
                continue
            # ⚠️⚠️ LA PLAUSIBILITE, ET SEULEMENT SI LE PLAN L'A DECLAREE —
            # constat `pipeline/C1`, residu. Le motif dit la BORNE SIGNEE :
            # l'actuaire doit pouvoir vérifier le refus contre son plan.
            if f.bornes is not None:
                bas, haut = f.bornes
                if not (bas <= x <= haut):
                    anomalies.append(
                        f"facteur '{f.nom}' : valeur {x!r} HORS DU DOMAINE "
                        f"declare au plan [{bas}, {haut}]. Elle est lisible, "
                        f"mais le modele n'a jamais vu cette plage : la prime "
                        f"rendue serait une EXTRAPOLATION, pas une "
                        f"tarification.")
        return anomalies

    def tarifer(self, contrat: dict,
                exposition: float | None = None) -> dict:
        """« Tarifez-moi ce contrat. » Le livrable qui vend (étape 5).

        CONTRAT DE SORTIE STABLE, directement consommable par une API REST/JSON :
          · toutes les valeurs sont NATIVES (bool / float / str) — jamais de
            numpy.float64 ni de type pandas (casts float() explicites) ;
          · une erreur est CAPTURÉE et renvoyée en {success: False, erreur: ...},
            jamais propagée brute — aligné sur la convention {success, ..., erreur}
            des agents A1..A6 du projet ;
          · success / plan_empreinte / date_calcul sont TOUJOURS présents (succès
            comme erreur) : la réponse reste tracée même en cas d'échec.
        """
        date_calcul = datetime.now(timezone.utc).isoformat()   # ISO 8601 (UTC)
        empreinte = self.plan.empreinte()
        # ⚠️⚠️ ON REFUSE AVANT DE TARIFER — constat `pipeline/C1`. Un facteur
        # illisible etait impute en silence par A2, et la prime du contrat
        # MOYEN sortait avec `success: True`. Le contrat de sortie declare
        # deja la voie de l'echec (`{success: False, erreur}`) : on l'emprunte
        # plutot que de signer un prix qu'on sait faux.
        _anomalies = self.anomalies_du_contrat(contrat)
        if _anomalies:
            return {
                "success": False,
                "erreur": ("contrat NON TARIFABLE — "
                           + " · ".join(_anomalies)),
                "anomalies_contrat": _anomalies,
                "plan_empreinte": empreinte,
                "date_calcul": date_calcul,
            }
        # ⚠️⚠️ D'OÙ VIENT L'EXPOSITION — constat `G.17`, mesuré le 05/09/2026.
        # La ligne ci-dessous posait le paramètre APRÈS le contrat, donc il
        # l'écrasait ; et comme il valait `1.0` par défaut, un contrat
        # déclarant une demi-année était tarifé pour une année entière, avec
        # `success: True` : 1 649,30 EUR au lieu de 792,68 (rapport 2,0807).
        #   ⚠️ LE DÉFAUT EST DEVENU `None` POUR RENDRE LES DEUX CAS
        #   DISCERNABLES — « l'appelant a passé 1,0 » et « l'appelant n'a rien
        #   passé » étaient jusqu'ici la même chose. **Le prix ne bouge pas** :
        #   sans paramètre, l'exposition retenue reste 1,0. Ce qui change,
        #   c'est qu'on DIT laquelle a servi, et qu'on signale l'autre.
        expo_retenue, expo_source, expo_phrase = source_exposition(
            contrat.get(self.plan.exposition), exposition)
        try:
            df = pd.DataFrame(
                [{**contrat, self.plan.exposition: expo_retenue}])
            Xc = self._design(df)
            freq = float(self._taux_frequence(Xc)[0])
            cout = float(self.glm_cout.predict(Xc)[0])
            prime_pure = (self.coefficient_equilibre
                          * (freq * cout + self.ecretement)
                          * float(expo_retenue))
            ch = self.chargements
            pc = (prime_pure * (1 + ch["frais"]) * (1 + ch["marge"])
                  / (1 - ch["commission"]))
            return {
                "success": True,
                "frequence_annuelle": round(freq, 5),
                "cout_moyen": round(cout, 2),
                "prime_pure": round(prime_pure, 2),
                "prime_commerciale_ht": round(pc, 2),
                "prime_ttc": round(pc * (1 + ch["taxes"]), 2),
                # ⚠️ L'HYPOTHESE VOYAGE AVEC LE PRIX — constat `pipeline/C5`.
                # `None` quand le plan declare : rien a signaler.
                "chargements_supposes": phrase_chargements_non_declares(
                    self.plan),
                # ⚠️ Constat `pipeline/C1`, residu : la porte existe, aucun
                # plan ne la remplit — l'hypothese doit donc etre DITE.
                "domaines_non_declares": phrase_domaines_non_declares(
                    self.plan),
                # ⚠️⚠️ L'EXPOSITION QUI A SERVI AU PRIX, ET D'OÙ ELLE VIENT.
                # Une prime sans sa durée n'est pas contestable : 1 649,30 EUR
                # pour un an et 792,68 pour six mois sont le MÊME tarif.
                # `exposition_hypothese` est `None` quand il n'y a rien à
                # signaler — une phrase qui s'affiche toujours ne se lit plus.
                "exposition_retenue": float(expo_retenue),
                "exposition_source": expo_source,
                "exposition_hypothese": expo_phrase,
                # ⚠️⚠️ CE QUE VAUT LE MODÈLE QUI PRODUIT CE PRIX — lot 14.
                # Gini de holdout (fréquence et sévérité), son intervalle de
                # confiance et le nombre d'observations qui le fonde. *Un Gini
                # sans son effectif ne se conteste pas.*
                # `None` = validation NON MESURÉE, jamais « aucun défaut ».
                "validation": (publication_validation(self.validation)
                               if self.validation is not None else None),
                "plan_empreinte": empreinte,          # traçabilité ACPR (ex-clé 'plan')
                "date_calcul": date_calcul,
            }
        except Exception as e:
            return {
                "success": False,
                "erreur": str(e),
                "plan_empreinte": empreinte,
                "date_calcul": date_calcul,
            }

    def grille(self, variable: str) -> pd.DataFrame:
        """Relativités exportables (ce que l'assureur met dans son SI).

        ⚠️⚠️ CONSTAT `pipeline/C6` — LA MOITIÉ DU TARIF MANQUAIT À LA GRILLE.
        Elle ne rendait que `relativite_frequence`, alors que la prime pure est
        **fréquence × coût moyen**. *L'assureur était invité à mettre dans son
        SI une grille dont il manquait un facteur sur deux.*

        Trois colonnes désormais, et la troisième est le produit des deux
        premières : c'est elle qui porte le tarif complet. ⚠️ **Aucun euro** —
        `grille()` n'entre dans aucun calcul de prime ; elle EXPOSE ce que les
        deux GLM portent déjà.
        """
        lignes = []
        for f in self.plan.facteurs:
            if f.nom != variable:
                continue
            for col in f.colonnes_produites():
                if col not in self.features:
                    continue
                # ⚠️ Lien log des deux cotes (et OLS sur log pour la
                # lognormale) : `exp(coef)` est la relativite MULTIPLICATIVE
                # dans les trois familles declarables.
                c_freq = float(
                    getattr(self.glm_frequence, "params", {}).get(col, 0.0))
                c_cout = float(
                    getattr(getattr(self.glm_cout, "_res", None), "params",
                            {}).get(col, 0.0))
                r_freq, r_cout = float(np.exp(c_freq)), float(np.exp(c_cout))
                lignes.append((col, round(r_freq, 4), round(r_cout, 4),
                               round(r_freq * r_cout, 4)))
        return pd.DataFrame(
            lignes,
            columns=["colonne", "relativite_frequence", "relativite_cout",
                     "relativite_prime_pure"])


# ══════════════════════════════════════════════════════════════════════════════
#  Stabilité temporelle — UNE SEULE fonction Gini pour le test ET le walk-forward
# ══════════════════════════════════════════════════════════════════════════════
def gini_lorenz(y_true, y_pred) -> float:
    """Gini de concentration (2·aire de Lorenz − 1), en triant les contrats par
    la PRÉDICTION.

    ⚠️⚠️ CONSTAT `pipeline/C3` — CETTE PHRASE AFFIRMAIT PLUS QUE SA PORTÉE.
    Elle disait « UNE SEULE définition ». C'est vrai **dans ce module** — le
    Gini de test et le Gini walk-forward passent tous deux par ICI, et c'est ce
    qui rend impossible la « métrique divergente » de B9 (INV-6). Ce n'est
    **pas** vrai à l'échelle du dépôt.

    ⚠️⚠️ **ELLE NE CALCULE PLUS : ELLE DÉLÈGUE AU SOCLE** (lot 14). Le
    contrôle `pipeline/C3` a mesuré le 05/09/2026 qu'un **neuvième** Gini
    venait d'entrer au dépôt, dans `core/validation_tarif.py`. Plutôt que d'en
    laisser deux identiques de part et d'autre de la frontière, le calcul
    canonique vit dans `core.validation_tarif.gini_lorenz` et **celle-ci
    l'appelle**. *Deux chemins qui calculent la même grandeur avec deux codes
    finissent par diverger.*

    ⚠️ **ET LA CONVERSION EST ÉCRITE, PAS TUE.** Le socle rend `None` quand le
    Gini n'est pas calculable ; cette fonction publie un `float` depuis
    toujours, et `evaluer_stabilite_temporelle` en dépend. Le `0.0` de repli
    reste donc ici, **à la frontière, visible** — il n'est pas remonté dans le
    socle, où il redeviendrait « une absence qui se dit zéro ».

    ⚠️⚠️ **DEUX CAS DÉGÉNÉRÉS CHANGENT, ET ILS SONT DITS PLUTÔT QUE TUS.** Le
    socle refuse ce que l'ancien code calculait quand même :
      · **une seule ligne** — l'ancien rendait `-1.0`, un extrême fabriqué à
        partir d'un point ; il rend désormais `0.0`. *Un Gini sur une ligne
        n'existe pas, et `-1.0` le faisait passer pour le pire modèle
        possible.*
      · **longueurs incohérentes** — l'ancien levait un `IndexError`, il rend
        désormais `0.0`.
    Les deux seuls appelants de production sont `_gini_sur` (fenêtres du
    walk-forward, toujours pleines et de même longueur des deux côtés) et une
    preuve d'audit hors périmètre : **aucun n'atteint ces cas** (mesuré).

    Mesuré par AST le 01/09/2026, **méthode publiée avec le chiffre** : sur les
    fonctions de production dont le nom porte `gini`, **8 sont comptées** par
    le critère large (leur corps emploie `cumsum`, `trapz` ou le mot Lorenz —
    le nom de la fonction en fait partie) et 2 ne calculent rien (une réserve,
    un verdict). ⚠️ **Mais seulement 3 CALCULENT vraiment** — critère étroit,
    ajouté le 05/09/2026 : le corps SANS SA DOCSTRING emploie `cumsum`. Les 3 :
    `core.validation_tarif.gini_lorenz` (**le canonique**), `a6`
    (`_gini_lorenz`) et `conformite` (`_gini_trie_par`).

    ⚠️⚠️ **ELLES ÉTAIENT SIX, ET ELLES N'ÉTAIENT PAS D'ACCORD** — lot 3.
    `a3`, `a4` et `a5` **délèguent** désormais au socle, dont le calcul traite
    les EX AEQUO et ne dépend plus de l'ordre des lignes. Les deux qui restent
    portent chacune SA raison, écrite dans leur code et vérifiée par `GU-6` :
    `a6` accumule un TAUX quand `expo` est fourni et son axe de population est
    `linspace(0, 1, n)` — ce n'est pas le même trapèze ; `conformite` trie par
    une COVARIABLE et non par une prédiction, et décide des verdicts du
    contrôle anti-fuite.

    ⚠️⚠️ **ET LA MESURE ÉTROITE A CORRIGÉ LA PROSE DE CE MODULE.** Elle
    annonçait « `charts` la sienne pour la figure ». **Faux** :
    `core.charts_tarif.chart_lorenz_gini` reçoit `lorenz_x`/`lorenz_y` déjà
    calculés et **DESSINE** — elle n'a ni `cumsum` ni `trapz`. Le critère large
    la comptait sur le seul mot « lorenz » de son nom. *Un relevé au texte
    sur-compte, et il faut le mesurer pour savoir de combien.* Celle-ci et
    `_gini_sur` sont les deux autres du large : elles délèguent.

    ⚠️⚠️ **ET LES SIX NE SONT PAS D'ACCORD — MESURÉ, PAS SUPPOSÉ.** `a3` trie
    par `argsort(-y_pred)` sans `mergesort`, `a4` et `a5` par
    `argsort(y_pred)[::-1]`, qui inverse l'ordre des EX AEQUO. Sur 500 lignes
    et 8 modalités de prédiction, les trois tris rendent **0,027476**,
    **0,046857** et **0,035429** pour la même donnée ; sur des prédictions
    toutes égales, deux d'entre eux sont **de signes opposés**. *Les faire
    déléguer déplacerait le classement d'A6, donc le modèle de production
    publié* — ce n'est pas le périmètre de ce lot, et c'est nommé ici plutôt
    que laissé à découvrir.

    ⚠️ **LE CRITÈRE LARGE EST UNE HEURISTIQUE, ET LE SENS DE SON ERREUR EST
    DIT** : il compte des délégations qui ne calculent pas. *Il SUR-compte, il
    ne sous-compte pas* — d'où la seconde mesure, plus étroite, qui compte les
    corps employant `cumsum`.

    **Ce qui est garanti ici est l'identité ENTRE LES DEUX USAGES DE CE
    MODULE**, pas l'unicité dans le dépôt. *Une phrase qui LIMITE est sûre ;
    une phrase qui AFFIRME au-delà de ce qu'elle tient est une dette.*
    """
    valeur = gini_socle(y_true, y_pred)
    # ⚠️ Le contrat PUBLIÉ de cette fonction est un `float` : ses appelants
    # (INV-6, le walk-forward) comparent des nombres. La conversion de
    # l'absence est donc faite ICI, et elle est écrite.
    return 0.0 if valeur is None else valeur


def evaluer_stabilite_temporelle(portefeuille: pd.DataFrame, plan: PlanTarifaire,
                                 col_temps: Optional[str] = None,
                                 n_fenetres: int = 4,
                                 models_path: str = "/tmp/actuaria",
                                 audit_path: str = "/tmp/actuaria") -> Dict[str, Any]:
    """Compare le Gini de TEST (une coupe train/test) au Gini WALK-FORWARD
    (fenêtres glissantes), avec la MÊME fonction gini_lorenz et la MÊME
    spécification (le pipeline plan) des deux côtés. INV-6 : l'écart relatif doit
    rester < 0,40 — sinon la métrique ou la spécification diverge (B9)."""
    df = portefeuille.copy().reset_index(drop=True)
    if col_temps and col_temps in df.columns:
        df = df.sort_values(col_temps, kind="mergesort").reset_index(drop=True)
    n = len(df)
    col_freq, col_expo = plan.cible_frequence, plan.exposition

    def _gini_sur(tarif, sous_df):
        pred = tarif.predire_portefeuille(sous_df)
        attendu = pred["frequence_annuelle"].to_numpy() * pred["exposition"].to_numpy()
        return gini_lorenz(sous_df[col_freq].to_numpy(), attendu)

    def _fit(sous_df):
        return pipeline_complet(sous_df, plan, equilibrer=False,
                                models_path=models_path, audit_path=audit_path)

    # ── Gini de TEST : derniers 20 % en test, le reste en apprentissage ──────
    cut = int(n * 0.8)
    tarif_tt = _fit(df.iloc[:cut])
    gini_test = _gini_sur(tarif_tt, df.iloc[cut:])

    # ── Gini WALK-FORWARD : fenêtres glissantes (fenêtre étendue) ────────────
    bornes = np.linspace(int(n * 0.4), n, n_fenetres + 1).astype(int)
    ginis = []
    for i in range(n_fenetres):
        tr_end, te_end = int(bornes[i]), int(bornes[i + 1])
        if te_end <= tr_end:
            continue
        tarif_i = _fit(df.iloc[:tr_end])
        ginis.append(_gini_sur(tarif_i, df.iloc[tr_end:te_end]))
    gini_wf = float(np.mean(ginis)) if ginis else 0.0

    ecart = (abs(gini_wf - gini_test) / abs(gini_test)
             if gini_test else float("inf"))
    return {"gini_test": gini_test, "gini_wf": gini_wf,
            "ginis_fenetres": ginis, "ecart_relatif": ecart}


# ══════════════════════════════════════════════════════════════════════════════
#  pipeline_complet — de A1 au tarif, piloté PAR LE PLAN (étapes 2→6)
# ══════════════════════════════════════════════════════════════════════════════
def _chargements_effectifs(explicites, plan) -> dict[str, float]:
    """L'appelant, puis LE PLAN, puis le repli — et le repli se DIT.

    ⚠️⚠️ CONSTATS `pipeline/C4` + `C5`, LA MEME QUESTION. `CHARGEMENTS_DEFAUT`
    porte `taxes: 0.33` -- le taux AUTO -- et servait de defaut aux 20 LoB,
    alors que son propre commentaire enumerait << auto 33 %, MRH 30 %,
    RC 9 % >>. Impact mesure sur la prime TTC : MRH +2,31 %, RC +22,02 %.

    ⚠️ AUCUN TAUX N'EST INVENTE ICI. Tant qu'un plan ne declare rien, le repli
    d'aujourd'hui s'applique a l'identique -- **aucun euro ne bouge** -- mais
    `tarifer()` publie desormais que la taxe a ete SUPPOSEE.
    """
    if explicites is not None:
        return dict(explicites)
    declares = getattr(plan, 'chargements', None)
    if declares is not None:
        return dataclasses.asdict(declares)
    return dict(CHARGEMENTS_DEFAUT)


def phrase_chargements_non_declares(plan) -> str | None:
    """L'hypothese de chargement, DITE — le coeur de `pipeline/C5`.

    ⚠️ Ne s'ajoute QUE si le plan ne declare rien : *un avertissement permanent
    est un avertissement qu'on cesse de lire.*
    """
    if getattr(plan, 'chargements', None) is not None:
        return None
    return (f"CHARGEMENTS NON DECLARES au plan '{getattr(plan, 'lob', '?')}' : "
            f"le repli AUTO a ete suppose, dont une taxe de "
            f"{CHARGEMENTS_DEFAUT['taxes']:.0%}. Les taux varient par LoB "
            f"(auto 33 %, MRH 30 %, RC 9 %) : declarez `chargements` au plan, "
            f"sans quoi la prime TTC d'une LoB non-auto est surestimee.")


def phrase_domaines_non_declares(plan) -> str | None:
    """Les facteurs continus dont le plan ne borne pas le domaine — `C1` residu.

    ⚠️⚠️ SANS CETTE PHRASE, LA FERMETURE SERAIT A MOITIE. La porte `bornes`
    existe, mais **0/20 plans en declarent** : `bonus_malus = -999` rend donc
    toujours un prix, et rien ne le dirait. *Le meme piege qu'`unite_exposition`
    aurait eu si l'hypothese annuelle etait restee muette.*

    ⚠️ Se tait des que TOUS les continus sont bornes : un avertissement
    permanent est un avertissement qu'on cesse de lire.
    """
    sans = [f.nom for f in getattr(plan, 'facteurs', ())
            if f.type == 'continu' and f.bornes is None]
    if not sans:
        return None
    return (f"DOMAINES NON DECLARES au plan '{getattr(plan, 'lob', '?')}' : "
            f"{len(sans)} facteur(s) continu(s) sans bornes -- "
            + ", ".join(sorted(sans)) +
            ". Une valeur LISIBLE mais implausible (par exemple -999) est donc "
            "tarifee : la prime rendue serait une EXTRAPOLATION. Declarez "
            "`bornes` sur ces facteurs pour qu'elle soit refusee.")


class CalculImpossibleBloquant(Exception):
    """Le modele ne peut PAS etre ajuste sur cette donnee — `pipeline/C2`.

    ⚠️ Distincte de `DonneeIllisibleBloquante` : la donnee est parfaitement
    LISIBLE, c'est le calcul qui n'a pas d'objet. *Deux causes, deux
    exceptions : l'appelant qui rattrape ne traite pas les deux pareil.*
    """


def _refuser_frequence_sans_sinistre(y_freq, lob, col_freq):
    """Un portefeuille SANS AUCUN sinistre ne peut pas ajuster un GLM Poisson.

    ⚠️⚠️ Mesure du 01/09 : il mourait sur `The first guess on the deviance
    function returned a nan. This could be a boundary problem and should be
    reported.` *L'actuaire etait invite a signaler un bug a statsmodels la ou
    son portefeuille n'avait simplement aucun sinistre.*

    ⚠️ AUCUN EURO : il n'y avait pas de prix, il n'y en a toujours pas — mais
    on dit pourquoi.
    """
    total = float(np.nansum(np.asarray(y_freq, dtype=float)))
    if total > 0:
        return
    raise CalculImpossibleBloquant(
        f"Tarification REFUSEE pour le plan '{lob}' : la cible de frequence "
        f"'{col_freq}' est NULLE sur tout le portefeuille (somme = 0). Un GLM "
        f"de Poisson a lien log n'a alors pas de solution -- son intercept "
        f"tendrait vers moins l'infini. Sans sinistre observe, il n'y a aucune "
        f"frequence a estimer : ce n'est pas un defaut de donnee, c'est "
        f"l'absence d'experience.")


class DonneeIllisibleBloquante(Exception):
    """Une valeur illisible sur un rôle que le GLM consomme — constat
    `pipeline/C8`.

    ⚠️ Elle porte le rapport, comme `QualiteBloquante` : *l'actuaire doit
    voir ce sur quoi il décide, pas seulement qu'on a refusé.*
    """

    def __init__(self, rapport, message: str):
        self.rapport = rapport
        super().__init__(message)


def _refuser_illisibles_sur_roles_du_glm(rapport, roles_par_colonne, lob):
    """Refuse de tarifer si un rôle CONSOMMÉ par le GLM porte de l'illisible.

    ⚠️⚠️ ON N'INTERROGE QUE LES RÔLES QU'ON VA UTILISER. Un signalement sur une
    colonne que le GLM ne lit pas ne casse rien : refuser dessus serait un
    garde-fou plus large que sa raison — la 8e forme du piège d'assiette.

    ⚠️ Rapport absent (appel hors `pipeline_complet`) : on ne refuse rien et on
    ne prétend rien. *Un contrôle qui n'a pas tourné ne doit pas ressembler à
    un contrôle qui n'a rien trouvé.*
    """
    if rapport is None:
        return
    coupables = [
        a for a in getattr(rapport, 'signalements', []) or []
        if str(a.code).startswith('valeur_illisible_')
        and a.role in set(roles_par_colonne.values())
    ]
    if not coupables:
        return
    detail = " ; ".join(
        f"{a.colonne} ({a.role}) : {a.nb_lignes} ligne(s), "
        f"{a.proportion:.1%} du portefeuille" for a in coupables)
    raise DonneeIllisibleBloquante(
        rapport,
        f"Tarification REFUSEE pour le plan '{lob}' : une ou plusieurs valeurs "
        f"ILLISIBLES portent sur un role que le modele consomme -- {detail}. "
        f"La couche qualite les a SIGNALEES (regle 3 : ambigu, ni exclu ni "
        f"corrige) ; le calcul, lui, ne peut pas les ignorer. Sans ce refus, "
        f"le GLM echouait sur << the deviance function returned a nan >>, un "
        f"message qui accuse la bibliotheque et non le fichier. Corrigez ces "
        f"valeurs, ou retirez ces lignes en amont -- ActuarIA ne les impute "
        f"pas : imputer une valeur illisible fabriquerait une donnee.")


def pipeline_complet(portefeuille: pd.DataFrame, plan: PlanTarifaire,
                     chargements: Optional[dict] = None,
                     quantile_ecretement: float = 0.995,
                     equilibrer: bool = True,
                     qualite_validee_par: Optional[str] = None,
                     models_path: str = "/tmp/actuaria",
                     audit_path: str = "/tmp/actuaria") -> TarifNonVie:
    """Ajuste le tarif complet à partir du seul plan signé. Aucune connaissance
    métier codée : A2 (fit/transform), conformité déclarative, GLM fréquence,
    GLM coût (famille du plan), écrêtement + équilibre (étape 6)."""
    # ── QUALITÉ DE DONNÉES (générique, pilotée par le plan) — AVANT A2.fit ───
    # Jamais d'exclusion/correction SILENCIEUSE : exclut les lignes impossibles
    # (règle 1), corrige les implausibles établies (règle 2, exposition>1→1.0),
    # signale les ambiguës (règle 3), et BLOQUE si une anomalie touche ≥ 5 % des
    # lignes sans confirmation actuarielle nominative (règle 4). Court-circuité
    # jusqu'ici : le chemin déclaratif ne passe pas par A1. A2 reçoit un df PROPRE.
    # ⚠️⚠️ ÉTAPE 1-A DE LA FUSION — LE PRÉAMBULE EST DÉSORMAIS UNE PORTE UNIQUE.
    # Ces trois gestes — contrôler, lever si bloqué, prendre le dataframe propre
    # — vivaient ici seuls. `controler_qualite` n'avait qu'UN appelant de
    # production, et le chemin agent n'a AUCUNE couche qualité : c'est ainsi que
    # les deux ont pu diverger sur la même grandeur. *Une porte unique rend la
    # divergence impossible plutôt que seulement évitable.*
    # ⚠️ Ce lot ne branche PAS le chemin agent — c'est l'étape 1-B, et elle
    # déplace un prix. **Extraire et brancher sont deux décisions.**
    rapport_qualite = preambule_qualite(
        portefeuille, plan, qualite_validee_par=qualite_validee_par,
        # ⚠️⚠️ CONSTAT `pipeline/C9` — DEUX HORODATAGES, DEUX FUSEAUX.
        # `tarifer()` posait `datetime.now(timezone.utc)` et cette ligne
        # `datetime.now()`, en heure LOCALE : *deux traces du meme calcul ne
        # portaient pas la meme heure*, et rien ne disait laquelle etait
        # laquelle. UTC des deux cotes -- un horodatage sans fuseau n'est pas
        # un horodatage, c'est une supposition sur la machine qui l'a ecrit.
        horodatage=datetime.now(timezone.utc).isoformat())
    df = rapport_qualite.dataframe_propre
    col_freq, col_cout, col_expo = (plan.cible_frequence, plan.cible_cout,
                                    plan.exposition)

    # ── A2 : fit / transform (le contrat A2→A3, INV-1) ──────────────────────
    a2 = AgentA2Preprocessing(models_path=models_path, audit_path=audit_path,
                              verbose=False).fit(df, plan)
    X = a2.transform(df)

    # ── Conformité DÉCLARATIVE (liste blanche = plan, INV-2/3/4) ────────────
    mx = construire_matrice_x(
        list(plan.colonnes_produites()), plan=plan, df=X,
        col_cible=[col_freq, col_cout],
        contexte=f"pipeline_complet — {plan.lob}")
    features = list(mx)

    # ⚠️⚠️ CONSTAT `pipeline/C8` — LE SIGNAL EXISTE, PERSONNE NE L'ÉCOUTAIT.
    # Le constat annonçait une asymétrie de `fillna` ; la mesure dit autre
    # chose. La couche qualité **détecte** la valeur illisible et la SIGNALE
    # (règle 3) — c'est sa doctrine, elle ne décide rien. Mais elle la laisse
    # donc dans `dataframe_propre`, et le GLM mourait dessus :
    #
    #   valeur_illisible_exposition        5 lignes   (regle 3, signalee)
    #   valeur_illisible_cible_frequence   4 lignes   (regle 3, signalee)
    #   -> ValueError: deviance function returned a nan ... should be reported
    #
    # *L'actuaire recevait une invitation à signaler un bug à `statsmodels` là
    # où son fichier portait 5 expositions illisibles.* Le défaut n'est pas la
    # DÉTECTION, c'est l'INDIFFÉRENCE au signal détecté.
    #
    # ⚠️ CE QUE CE REFUS N'EST PAS : ni une exclusion (un euro bougerait, et
    # « illisible » est AMBIGU, pas IMPOSSIBLE — la doctrine tranchée par
    # `qualite/C8`), ni un `fillna` (imputer en silence sur une donnée
    # illisible, le motif d'`a2/C5`). *Il n'y avait pas de prix : il n'y en a
    # toujours pas, mais on dit pourquoi.*
    _refuser_illisibles_sur_roles_du_glm(
        rapport_qualite, {col_expo: 'exposition', col_freq: 'cible_frequence',
                          col_cout: 'cible_cout'}, plan.lob)

    Xc = sm.add_constant(X[features], has_constant="add")
    expo = pd.to_numeric(X[col_expo], errors="coerce").clip(lower=1e-9)
    y_freq = pd.to_numeric(X[col_freq], errors="coerce").astype(float)

    # ⚠️ CONSTAT `pipeline/C2` — l'impossibilite se DIT avant le solveur.
    _refuser_frequence_sans_sinistre(y_freq, plan.lob, col_freq)

    # ── GLM FRÉQUENCE (Poisson, offset log-exposition) ──────────────────────
    # ⚠️⚠️ MOTEUR PARTAGÉ AVEC A3 — `core/frequence.py`, symétrique de
    # `core/severite.py` qui porte déjà le GLM de coût. Les deux chemins
    # ajustaient la même grandeur avec deux codes ; *deux codes finissent par
    # diverger*, et c'est ce qui avait coûté −15 % de tarif sur la sévérité.
    #   ⚠️ `selection=False` N'EST PAS UN REPLI, C'EST LA DOCTRINE DE CE
    #   CHEMIN. Il exécute un plan SIGNÉ : ses facteurs sont un engagement de
    #   l'actuaire, pas une hypothèse à tester. Mesuré sur les 18 plans,
    #   apporter la sélection ici retirerait `sinistres_3ans_anterieurs` en
    #   décennale (effet réel +0,40) et `statut_occupation` en MRH (+0,30),
    #   faute de puissance — en retenant `etage`, qui est du bruit.
    #   *Arbitré par Selasse le 05/09/2026 : on unifie le code, pas la
    #   méthode.* Aucun euro ne bouge : l'ajustement est le même, mot pour mot.
    glm_freq = ajuster_glm_frequence(
        pd.concat([Xc, y_freq.rename(col_freq)], axis=1),
        [c for c in Xc.columns if c != 'const'], col_freq,
        np.log(expo), selection=False)['modele']

    # ── CIBLE DE SÉVÉRITÉ — SOURCE UNIQUE (core/severite.py) ────────────────
    # Cible (cout_ecrete/nb), masque (coût OBSERVÉ) et écrêtement des graves
    # sont indissociables : ils sont donc définis À UN SEUL ENDROIT, partagé
    # avec A3. Les séparer est exactement ce qui avait laissé les deux chemins
    # diverger — A3 ajustait le coût TOTAL en l'appelant 'cout_moyen'.
    # La charge grave est réintégrée en charge MOYENNE sur tout le portefeuille
    # (prime_grave_unitaire), pas au contrat.
    cout_total = pd.to_numeric(X[col_cout], errors="coerce").astype(float).fillna(0.0)
    # ⚠️ Meme source que A3 : un seuil declare au plan l'emporte sur le
    # quantile. Ici l'assiette est le portefeuille COMPLET (modele de
    # production), la ou A3 apprend sur le train (modele de validation).
    cible_sev = construire_cible_severite(
        cout_total, y_freq, expo, quantile_ecretement=quantile_ecretement,
        seuil=seuil_declare(plan))
    prime_grave_unitaire = cible_sev.prime_grave_unitaire

    # ── GLM COÛT MOYEN — FAMILLE DÉCLARÉE DANS LE PLAN ──────────────────────
    if cible_sev.n_retenus:
        glm_cout = ajuster_glm_cout(Xc[cible_sev.masque], cible_sev.severite,
                                    plan.famille_severite)
    else:
        # ⚠️⚠️ CONSTAT `pipeline/C2` — CE REPLI N'ÉTAIT NI DÉGÉNÉRÉ NI DÉFINI.
        # Il annonçait « coût moyen constant (dégénéré mais défini) ». Mesuré
        # le 01/09 : il ajustait un GLM Gamma sur **UNE observation** et ~24
        # paramètres, et **mourait lui-même** sur `deviance function returned
        # a nan`.
        #
        # ⚠️ ET LE CONSTAT SE TROMPAIT DE CAS. Il disait la branche « JAMAIS
        # atteinte », mesuré sur un portefeuille SANS aucun sinistre — celui-là
        # meurt vingt lignes plus tôt, sur le GLM de fréquence. La branche est
        # bien atteinte par l'AUTRE cas : des sinistres COMPTÉS, aucun coût
        # POSITIF. *Le constat visait juste et se trompait de porte.*
        #
        # On refuse, et on dit quoi. La couche qualité signale déjà ce cas
        # (`incoherence_sin_sans_cout`, règle 3) : elle constate, le calcul
        # assume — la doctrine posée pour `pipeline/C8`.
        raise CalculImpossibleBloquant(
            f"Tarification REFUSEE pour le plan '{plan.lob}' : "
            f"{int((y_freq > 0).sum())} sinistre(s) sont COMPTES, mais AUCUN "
            f"cout strictement positif n'est observe. Le GLM de cout moyen n'a "
            f"donc rien a ajuster. Le repli precedent pretendait un << cout "
            f"moyen constant, degenere mais defini >> : il ajustait en fait un "
            f"GLM sur UNE observation et echouait lui-meme. Verifiez la colonne "
            f"'{col_cout}' -- des sinistres sans montant sont signales par la "
            f"couche qualite (`incoherence_sin_sans_cout`).")

    tarif = TarifNonVie(
        plan=plan, a2=a2, glm_frequence=glm_freq, glm_cout=glm_cout,
        features=features, ecretement=prime_grave_unitaire,
        coefficient_equilibre=1.0,
        # ⚠️⚠️ TROIS SOURCES, UN ORDRE EXPLICITE — constats `pipeline/C4`
        # et `C5`. L'appelant prime (rétrocompat), puis LE PLAN SIGNÉ,
        # puis le repli. *Le repli n'est plus le seul chemin, et quand il
        # s'applique il est DIT — `tarifer()` le publie.*
        chargements=_chargements_effectifs(chargements, plan),
        rapport_qualite=rapport_qualite)

    # ── CE QUE LE TARIF SAIT DE SA PROPRE QUALITÉ (lot 14) ──────────────────
    # ⚠️⚠️ ON MESURE SUR UN HOLDOUT, ON PRODUIT SUR 100 % — la doctrine posée
    # au lot 13, appliquée ici au chemin déclaratif. Les GLM ci-dessus sont et
    # restent ceux de PRODUCTION, ajustés sur tout le portefeuille : **le
    # tarif ne bouge pas d'un centime**. Ce bloc ajuste, à côté, un modèle de
    # VALIDATION sur 80 % pour mesurer ce que le modèle vaut sur des lignes
    # qu'il n'a pas vues.
    #
    # ⚠️⚠️ ET IL NE BLOQUE RIEN TOUT SEUL — DÉCISION DU 05/09/2026, PRISE
    # CONTRE MA PREMIÈRE PROPOSITION ET SUR MESURE. Une règle de refus sur
    # « intervalle entièrement sous zéro » a été câblée ici, puis RÉFUTÉE par
    # la gate : mesurée sur ce chemin, 18 plans × 3 tailles, elle refuse 2
    # plans à 1 500 lignes, 1 à 3 000, 0 à 4 000 — `auto` bascule du refus à
    # l'accord entre 1 500 et 3 000, MÊMES données, MÊME graine. *Un verdict
    # qui dépend de la taille de l'échantillon mesure du bruit.* Le blocage
    # dur existe toujours, mais il se DÉCLARE au plan.
    _validation = None
    try:
        _n_val = int(len(df) * 0.80)
        if _n_val >= 50 and len(df) - _n_val >= MINIMUM_POUR_INTERVALLE:
            _idx = np.arange(len(df))
            _tr, _te = _idx[:_n_val], _idx[_n_val:]
            _Xtr, _Xte = Xc.iloc[_tr], Xc.iloc[_te]
            _glm_val = ajuster_glm_frequence(
                pd.concat([_Xtr, y_freq.iloc[_tr].rename(col_freq)], axis=1),
                [c for c in Xc.columns if c != 'const'], col_freq,
                np.log(expo.iloc[_tr]), selection=False)['modele']
            _pred_f = np.asarray(
                _glm_val.predict(_Xte, offset=np.zeros(len(_Xte))), dtype=float)
            # ⚠️⚠️ LA PUISSANCE VOYAGE AVEC LE GINI. Le dénominateur d'un GLM
            # de comptage est le nombre de SINISTRES, jamais de contrats —
            # même doctrine qu'au lot 17a pour la sélection de variables.
            # Sans ce rapport, un Gini de holdout négatif n'est pas
            # diagnosticable : on ne peut pas distinguer « ne segmente pas »
            # de « ajusté sur trop peu de sinistres pour le dire ».
            _disc_f = mesurer_discrimination(
                y_freq.iloc[_te].to_numpy(dtype=float), _pred_f,
                n_apprentissage=int(float(y_freq.iloc[_tr].sum())),
                n_parametres=len(_glm_val.params))

            # ⚠️ La sévérité se valide sur les SINISTRÉS du holdout, et sur
            # eux seuls : c'est l'assiette du GLM de coût.
            # ⚠️ LE SEUIL D'ÉCRÊTEMENT EST CELUI DE LA PRODUCTION
            # (`cible_sev.seuil_ecretement`), pas un seuil recalculé sur le
            # sous-jeu : sinon on validerait un modèle qui n'écrête pas la
            # même chose que celui qu'on livre.
            def _cible(indices):
                return construire_cible_severite(
                    X[col_cout].iloc[indices], y_freq.iloc[indices],
                    expo.iloc[indices], seuil=cible_sev.seuil_ecretement)

            _disc_s = None
            _cible_tr, _cible_te = _cible(_tr), _cible(_te)
            if (_cible_te.n_retenus >= MINIMUM_POUR_INTERVALLE
                    and _cible_tr.n_retenus >= MINIMUM_POUR_INTERVALLE):
                _glm_c_val = ajuster_glm_cout(
                    _Xtr[np.asarray(_cible_tr.masque, dtype=bool)],
                    _cible_tr.severite, plan.famille_severite)
                _Xte_sin = _Xte[np.asarray(_cible_te.masque, dtype=bool)]
                _disc_s = mesurer_discrimination(
                    np.asarray(_cible_te.severite, dtype=float),
                    np.asarray(_glm_c_val.predict(_Xte_sin), dtype=float),
                    n_apprentissage=int(_cible_tr.n_retenus),
                    n_parametres=int(_Xtr.shape[1]))
            # ⚠️ `refus_anti_selection` vient du PLAN et de lui seul. Le moteur
            # ne décide jamais qu'un tarif n'existe pas.
            _validation = valider(
                frequence=_disc_f, severite=_disc_s,
                refus_anti_selection=bool(
                    getattr(plan, 'refus_anti_selection', False)))
    except Exception as _e_val:                              # noqa: BLE001
        # ⚠️ Une validation qui échoue ne fabrique PAS un tarif validé : elle
        # laisse `validation=None`, et `None` se lit « non mesurée », jamais
        # « aucun défaut ».
        _validation = None
        logger.warning("Validation du tarif non mesuree : %s", _e_val)

    tarif.validation = _validation
    # ⚠️⚠️ LA SEULE LEVÉE POSSIBLE, ET ELLE VIENT DU PLAN. `refus` reste VIDE
    # tant que `plan.refus_anti_selection` n'est pas déclaré : aucun des 20
    # plans ne le déclare aujourd'hui, donc **cette branche n'est atteinte par
    # aucun d'eux**. Elle n'est pas morte pour autant — `VT-10` la traverse
    # avec un plan qui la déclare, et le sceau la replante.
    if _validation is not None and _validation.refuse:
        raise CalculImpossibleBloquant(
            f"Tarification REFUSEE pour le plan '{plan.lob}' : "
            + " ".join(_validation.refus))

    # ── Coefficient d'ÉQUILIBRE technique k (INV-8) ─────────────────────────
    # k = Σ charge observée / Σ (prime_pure prédite). Après ce calage, la prime
    # pure totale reproduit la charge totale à ±1 %.
    if equilibrer:
        pred = tarif.predire_portefeuille(df)
        somme_predite = float(pred["prime_pure"].sum())
        somme_observee = float(cout_total.sum())
        if somme_predite > 0 and somme_observee > 0:
            tarif.coefficient_equilibre = somme_observee / somme_predite
        # ⚠️⚠️ POURQUOI IL N'Y A PAS DE `else` ICI, ET POURQUOI C'EST MESURÉ.
        # Un `k` resté à 1,0 se lirait « tarif déjà équilibré » alors que
        # l'équilibrage N'AURAIT PAS EU LIEU : c'est la forme exacte du défaut
        # que ce chantier ferme partout. J'ai voulu le déclarer — **la mesure
        # du 05/09/2026 a montré que la branche est INATTEIGNABLE**, et une
        # déclaration inatteignable est un contrôle qui atteste sans
        # surveiller :
        #
        #   `somme_observee <= 0` : les deux voies sont REFUSÉES en amont, dans
        #       cette même fonction — `_refuser_frequence_sans_sinistre` (cible
        #       de fréquence nulle partout) et le refus du GLM de coût
        #       (sinistres comptés, aucun coût strictement positif).
        #   `somme_predite <= 0` : impossible. La prime pure sort d'un lien
        #       log, donc de `exp()`, strictement positif — mesuré sur la
        #       fixture `auto` : min = 129,28 EUR, 0 valeur nulle ou négative
        #       sur 1 200 contrats. Une somme nulle exigerait un portefeuille
        #       VIDE, lui-même refusé plus haut.
        #
        # *Ce n'est donc pas un silence : c'est un cas que deux refus nommés
        # rendent impossible.* `test_equilibrage_non_silencieux` FIGE ce
        # raisonnement — retirer l'un des deux refus le fait tomber.
    return tarif
