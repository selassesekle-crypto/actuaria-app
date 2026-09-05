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

Rien ici ne « sait » ce qu'est une voiture ou un chantier : tout vient du plan.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
import dataclasses
from statsmodels.genmod import families as _families

from core.plan_tarifaire import CHARGEMENTS_DEFAUT, PlanTarifaire
from core.conformite_reglementaire import construire_matrice_x, source_exposition
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

    # ── Prédiction interne, partagée par tarifer() et le portefeuille (INV-7) ──
    def _design(self, df: pd.DataFrame) -> pd.DataFrame:
        X = self.a2.transform(df)
        return sm.add_constant(X[self.features], has_constant="add")

    def _taux_frequence(self, Xc) -> np.ndarray:
        # offset=0 → taux annuel PAR UNITÉ d'exposition (la prime le remultiplie).
        return np.asarray(
            self.glm_frequence.predict(Xc, offset=np.zeros(len(Xc))), dtype=float)

    def predire_portefeuille(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prédictions vectorisées sur un portefeuille — MÊME chemin que
        `tarifer()`.

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

    Mesuré par AST le 01/09/2026 — **méthode publiée avec le chiffre** : sur
    les fonctions de production dont le nom porte `gini`, **8 calculent
    réellement un coefficient** (critère retenu : leur corps emploie `cumsum`,
    `trapz` ou une courbe de Lorenz) et 2 n'en calculent pas (une réserve, un
    verdict). Parmi les 8 : `a3`, `a4`, `a5` ont chacune leur `_calculer_gini`,
    `a6` son `_gini_lorenz`, `conformite` son `_gini_trie_par`, `charts` la
    sienne pour la figure — plus celle-ci et son enveloppe locale `_gini_sur`.

    ⚠️ **LE CRITÈRE EST UNE HEURISTIQUE, ET LE SENS DE SON ERREUR EST DIT** :
    il peut compter une aide qui n'est pas une définition à part entière ; il
    ne peut pas en manquer une qui calcule vraiment. *Il SUR-compte, il ne
    sous-compte pas.*

    **Ce qui est garanti ici est l'identité ENTRE LES DEUX USAGES DE CE
    MODULE**, pas l'unicité dans le dépôt. *Une phrase qui LIMITE est sûre ;
    une phrase qui AFFIRME au-delà de ce qu'elle tient est une dette.*
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if len(y_true) == 0:
        return 0.0
    ordre = np.argsort(-y_pred, kind="mergesort")
    y = y_true[ordre]
    total = float(y.sum())
    if total <= 0:
        return 0.0
    cum_y = np.cumsum(y) / total
    cum_pop = np.arange(1, len(y) + 1) / len(y)
    _trap = getattr(np, "trapezoid", None) or np.trapz
    return float(2.0 * _trap(cum_y, cum_pop) - 1.0)


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
    glm_freq = sm.GLM(y_freq, Xc,
                      family=_families.Poisson(link=_families.links.Log()),
                      offset=np.log(expo)).fit(maxiter=200, disp=False)

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
