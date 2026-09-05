# -*- coding: utf-8 -*-
"""
ActuarIA — Socle · LE GLM DE FRÉQUENCE, AJUSTÉ À UN SEUL ENDROIT
================================================================

Symétrique de :mod:`core.severite`, qui porte déjà le GLM de coût. Deux
chemins ajustent une fréquence dans ce dépôt — A3 (le moteur qui COMPARE des
modèles) et ``pipeline_complet`` (le chemin déclaratif qui EXÉCUTE un plan
signé) — et ils l'écrivaient chacun de leur côté.

  *Deux chemins qui ajustent la même grandeur avec deux codes finissent par
  diverger.* C'est ce qui avait coûté −15 % de tarif sur la sévérité, avant
  que `core/severite.py` n'en fasse une source unique.

⚠️⚠️ CE MODULE UNIFIE LE CODE, PAS LA MÉTHODE — ET C'EST UN ARBITRAGE, PAS UNE
COMMODITÉ. Les deux appelants ne veulent pas la même chose :

  · **A3 SÉLECTIONNE.** Il compare des modèles ; retirer une variable sans
    signal est son travail.
  · **Le chemin déclaratif NE SÉLECTIONNE PAS.** Il exécute un plan SIGNÉ :
    ses facteurs sont un engagement de l'actuaire, pas une hypothèse à
    tester.

  ⚠️ MESURÉ LE 05/09/2026 SUR LES 18 PLANS, et c'est ce qui a tranché.
  Apporter la sélection au chemin déclaratif ne déplace pas la masse
  (+0,000 % partout, le coefficient d'équilibre la recale) mais **redistribue
  fortement** : 24 % des contrats à plus de 10 % d'écart, jusqu'à 54 % sur
  `mrh`. Et sur quatre plans elle retire des facteurs qui portent un VRAI
  effet, faute de puissance pour l'établir :

      decennale   `sinistres_3ans_anterieurs`   p=0,0737   effet réel +0,40
      mrh         `statut_occupation_locataire` p=0,0594   effet réel +0,30
      rc_produit  `type_produit_alimentaire`    p=0,1020   effet réel +0,40

  Pire, sur `mrh` (324 sinistres) la sélection RETIENT `etage`, qui est du
  bruit pur par construction du générateur. *Ce n'est pas le seuil qui décide,
  c'est le nombre de SINISTRES* — les plans à plus de 900 sinistres retrouvent
  tout leur signal, ceux à moins de 600 le perdent.

  **Le tarif signé garde donc les facteurs que l'actuaire a inscrits.**
  `selection=False` n'est pas un repli : c'est la doctrine du chemin
  déclaratif, et elle est dite ici plutôt que déduite d'une absence de code.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.genmod import families as _familles


def _matrice(df: pd.DataFrame, colonnes: list[str]) -> pd.DataFrame:
    """La matrice de conception, constante comprise.

    ⚠️ ``has_constant='add'`` : sans lui, une colonne déjà constante ferait
    taire l'intercept, et le modèle changerait de spécification en silence.
    """
    if colonnes:
        return sm.add_constant(df[colonnes].fillna(0), has_constant='add')
    # ⚠️ Aucune variable : le modèle à la SEULE CONSTANTE. Il est légitime —
    # c'est un tarif qui ne segmente pas — et il se dit (voir
    # `phrase_puissance_selection`).
    return sm.add_constant(
        pd.DataFrame({'intercept': np.ones(len(df))}, index=df.index),
        has_constant='add')


def ajuster_glm_frequence(df: pd.DataFrame, colonnes: list[str], cible: str,
                          offset, *, selection: bool = False,
                          seuil_pvalue: float | None = None,
                          journal=None) -> dict[str, Any]:
    """Ajuste le GLM de fréquence (Poisson, lien log, offset log-exposition).

    Rend ``{'modele', 'variables', 'exclues', 'iterations'}``.

    ⚠️⚠️ ``selection`` COMMANDE, ET LE DÉFAUT EST ``False``. Le chemin
    déclaratif n'a jamais sélectionné ; en faire le défaut garantit qu'un
    appelant distrait ne modifie pas un tarif signé. A3 demande explicitement
    ``selection=True``.

    ⚠️ ``seuil_pvalue`` EST OBLIGATOIRE DÈS QU'ON SÉLECTIONNE, et il n'a pas
    de valeur par défaut ici : le seuil vit chez celui qui sélectionne
    (``a3_glm.SEUIL_PVALUE``), et un test l'y fige. *Une seconde source du
    même nombre est exactement ce que ce module existe pour empêcher.*

    ⚠️ CE MODULE NE TRADUIT AUCUNE EXCEPTION. Si même le modèle à la seule
    constante échoue, statsmodels remonte tel quel : c'est à l'appelant de
    l'habiller — A3 le fait déjà avec `CalibrationImpossible`, qui nomme la
    cible et les faits. *Le socle ne connaît pas le vocabulaire d'un agent.*
    """
    if selection and seuil_pvalue is None:
        raise ValueError(
            "ajuster_glm_frequence : `seuil_pvalue` est obligatoire quand "
            "`selection=True`. Il vit chez l'appelant qui selectionne, pour "
            "qu'il n'en existe pas deux.")

    y = df[cible]
    actives = [c for c in colonnes if c in df.columns]
    exclues: list[dict[str, Any]] = []
    modele = None
    iterations = 0

    if not selection:
        # ⚠️ LE CHEMIN DÉCLARATIF : toutes les colonnes conformes, aucun
        # retrait. C'est l'ajustement qu'il faisait déjà, mot pour mot.
        modele = sm.GLM(
            y, _matrice(df, actives),
            family=_familles.Poisson(link=_familles.links.Log()),
            offset=offset).fit(maxiter=200, disp=False)
        return {'modele': modele, 'variables': actives, 'exclues': exclues,
                'iterations': 1}

    # ── SÉLECTION DESCENDANTE — retrait de la p-value maximale ─────────────
    while True:
        iterations += 1
        if not actives:
            if journal:
                journal.warning('Plus aucune variable active dans le GLM '
                                'de frequence')
            break
        try:
            candidat = sm.GLM(
                y, _matrice(df, actives),
                family=_familles.Poisson(link=_familles.links.Log()),
                offset=offset).fit(maxiter=200, disp=False)
            pvalues = candidat.pvalues.drop('const', errors='ignore')
            if len(pvalues) == 0 or float(pvalues.max()) <= seuil_pvalue:
                modele = candidat
                break
            pire = str(pvalues.idxmax())
            exclues.append({'variable': pire,
                            'pvalue': round(float(pvalues.max()), 4),
                            'raison': f'p-value > {seuil_pvalue}'})
            actives.remove(pire)
        except Exception as erreur:                          # noqa: BLE001
            # ⚠️⚠️ TROIS AFFIRMATIONS FAUSSES TENAIENT ICI — constat `a3/C14`,
            # et le comportement est repris À L'IDENTIQUE, y compris ce qu'il
            # a d'insatisfaisant :
            #  ① `pvalue` vaut `None`, jamais 1.0 — un 1.0 fabriqué se lirait
            #     « variable non significative » alors que RIEN n'a été testé ;
            #  ② la cause n'est PAS conclue : on nomme le TYPE réel ;
            #  ③ LA VARIABLE RETIRÉE EST ARBITRAIRE — l'exception ne dit pas
            #     laquelle a échoué. Le changer modifierait le modèle ajusté,
            #     donc un prix : c'est DÉCLARÉ, pas corrigé.
            if not actives:
                break
            exclues.append({
                'variable': actives[-1], 'pvalue': None,
                'pvalue_non_testee': True, 'variable_arbitraire': True,
                'raison': (f"echec de l'ajustement ({type(erreur).__name__}: "
                           f"{str(erreur)[:60]}) — variable retiree "
                           f"ARBITRAIREMENT (la derniere), la cause reelle "
                           f"n'est pas etablie"),
            })
            actives.pop()

    if modele is None:
        # ⚠️ Le modèle à la SEULE CONSTANTE. Aucun `try` ici : voir la
        # docstring — l'appelant habille l'échec, le socle ne l'invente pas.
        if journal:
            journal.warning('GLM de frequence : modele intercept seul')
        modele = sm.GLM(
            y, _matrice(df, []),
            family=_familles.Poisson(link=_familles.links.Log()),
            offset=offset).fit(maxiter=200, disp=False)
        actives = []

    return {'modele': modele, 'variables': actives, 'exclues': exclues,
            'iterations': iterations}
