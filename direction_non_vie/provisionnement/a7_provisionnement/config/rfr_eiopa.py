# =============================================================================
#  ActuarIA — Courbe des taux sans risque EIOPA (Risk-Free Rate)
#  rfr_eiopa.py
#
#  Source  : EIOPA Risk-Free Interest Rate Term Structures
#  Devise  : EUR
#  Date    : 31 mars 2025 (Q1 2025)
#  Méthode : Taux spot sans VA (Volatility Adjustment), sans CRA
#  Réf.    : Art. 77 Directive Solvabilité 2 + Règlement Délégué 2015/35
#
#  ⚠️  MISE À JOUR REQUISE : cette courbe doit être mise à jour depuis
#      https://www.eiopa.europa.eu/tools-and-data/
#      risk-free-interest-rate-term-structures_en
#      EIOPA publie MENSUELLEMENT (et non trimestriellement, comme l'affirmait
#      cet en-tête). Sa péremption n'est plus laissée à la vigilance du lecteur :
#      `diagnostic_peremption()` la mesure et la remonte dans `erreur`.
#
#  Utilisation :
#      from config.rfr_eiopa import get_taux_rfr, DATE_COURBE
#      taux_t = get_taux_rfr(t)  # taux spot à la maturité t (années)
# =============================================================================

from __future__ import annotations
import numpy as np
from typing import Optional, Union

# ── Métadonnées ───────────────────────────────────────────────────────────────
DATE_COURBE    = "2025-03-31"
DEVISE         = "EUR"
SOURCE         = "EIOPA RFR Term Structures — Q1 2025"
AVEC_VA        = False   # Sans Volatility Adjustment (base)
AVEC_CRA       = False   # Sans Credit Risk Adjustment

# ── Courbe EIOPA RFR EUR au 31/03/2025 ───────────────────────────────────────
# Taux spot annuel en % pour les maturités clés (1 à 150 ans)
# Interpolation linéaire pour les maturités intermédiaires
_MATURITES_CLE = [
     1,  2,  3,  4,  5,  6,  7,  8,  9, 10,
    11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
    25, 30, 40, 50, 60, 70, 80, 90, 100, 150,
]

_TAUX_PCT = [
    2.626, 2.617, 2.618, 2.630, 2.648, 2.668, 2.689, 2.710, 2.730, 2.749,
    2.767, 2.784, 2.799, 2.813, 2.826, 2.838, 2.849, 2.859, 2.868, 2.876,
    2.907, 2.926, 2.946, 2.954, 2.958, 2.960, 2.961, 2.961, 2.962, 2.962,
]

# Pré-calculer l'interpolation pour maturités 1 à 150 ans
_mats_arr  = np.array(_MATURITES_CLE, dtype=float)
_taux_arr  = np.array(_TAUX_PCT,      dtype=float)


def get_taux_rfr(maturite: Union[int, float]) -> float:
    """
    Retourne le taux sans risque EIOPA EUR pour une maturité donnée.

    Parameters
    ----------
    maturite : int ou float
        Maturité en années (1 à 150).

    Returns
    -------
    float : taux annuel en décimal (ex: 0.02749 pour 2.749%)
    """
    maturite = max(1.0, min(float(maturite), 150.0))
    taux_pct = float(np.interp(maturite, _mats_arr, _taux_arr))
    return taux_pct / 100.0


def get_courbe_rfr(maturites_max: int = 30) -> list[float]:
    """
    Retourne la courbe complète jusqu'à maturites_max ans.

    Returns
    -------
    list[float] : taux en décimal pour t = 1, 2, ..., maturites_max
    """
    return [get_taux_rfr(t) for t in range(1, maturites_max + 1)]


def get_facteur_actualisation(t: int) -> float:
    """
    Facteur d'actualisation à la maturité t : 1 / (1 + r_t)^t

    Parameters
    ----------
    t : int — maturité en années (t ≥ 1)

    Returns
    -------
    float : facteur d'actualisation
    """
    r_t = get_taux_rfr(t)
    return 1.0 / (1.0 + r_t) ** t


# =============================================================================
#  FONCTIONS DE SUBSTITUTION — courbe manuelle ou fichier Excel
# =============================================================================

#: En deçà de ce maximum EN VALEUR ABSOLUE, une courbe est lue comme étant en
#: DÉCIMAL et non en pourcentage — et elle est refusée plutôt que divisée par
#: cent une seconde fois.
#:
#: ⚠️ POURQUOI CE GARDE-FOU EXISTE. Les fichiers EIOPA publient les taux en
#: DÉCIMAL — 0,02826 pour 2,826 %. Le code de ce module attend des POURCENTS
#: et divise par cent. Un fichier EIOPA importé tel quel produirait donc une
#: courbe CENT FOIS TROP BASSE, sans lever la moindre erreur. C'est le seul
#: des trois obstacles à un import brut qui échouerait en silence : les deux
#: autres — mauvaise feuille, en-tête absent — s'arrêtent bruyamment.
#:
#: ⚠️ SEUIL CALIBRÉ, PAS CHOISI, et sur le cas le plus défavorable : une
#: courbe légitime en régime de taux NÉGATIFS, tronquée aux seules maturités
#: courtes. Maximum en valeur absolue mesuré :
#:       EIOPA 2026 en décimal ................ 0,0337
#:       EIOPA 2026 en pourcentage ............ 3,3720
#:       EUR fin 2020, complète ............... 3,1500
#:       EUR fin 2020, tronquée à 10 ans ...... 0,6000   ← le cas serré
#: La VALEUR ABSOLUE est ce qui sauve le dernier cas : son court terme vaut
#: −0,60 %, donc 0,60 en module, loin des 0,034 du décimal. Tout seuil de 0,05
#: à 0,50 sépare correctement ; 0,15 est le milieu géométrique des deux
#: extrêmes (√(0,0337 × 0,60) = 0,142), soit un facteur 4,4 de marge de part
#: et d'autre.
TAUX_MIN_PLAUSIBLE_PCT = 0.15

#: Ce que le message doit faire : dire QUOI FAIRE, pas seulement refuser. Un
#: actuaire bloqué sans consigne rouvrira le même fichier et réessaiera.
_CONSIGNE_POURCENT = (
    "Les taux doivent être exprimés EN POURCENTAGE — 2,826 pour 2,826 %. "
    "Les fichiers EIOPA les publient en décimal (0,02826) : multipliez la "
    "colonne par 100 avant l'import. Si votre courbe est réellement de cet "
    "ordre, saisissez-la comme taux manuel plutôt que par fichier."
)


def _diagnostic_unite(taux_pct) -> Optional[str]:
    """Rend un message si la série ressemble à des décimaux, sinon `None`.

    Le zéro est admis sans réserve : un actuaire qui assume une actualisation
    nulle la saisit ainsi, et ce n'est pas une erreur d'unité.
    """
    valeurs = np.asarray([v for v in np.ravel(np.asarray(taux_pct,
                                                         dtype=float))
                          if np.isfinite(v)], dtype=float)
    if valeurs.size == 0:
        return None
    maxi = float(np.abs(valeurs).max())
    if maxi == 0.0 or maxi >= TAUX_MIN_PLAUSIBLE_PCT:
        return None
    return (f"Taux lus comme des décimaux : le plus élevé vaut {maxi:.5f} en "
            f"valeur absolue, là où une courbe en pourcentage dépasse "
            f"{TAUX_MIN_PLAUSIBLE_PCT}. {_CONSIGNE_POURCENT}")


def get_courbe_taux_plat(taux_pct: float) -> dict:
    """
    Retourne une courbe de taux plat (même taux pour toutes les maturités).

    Parameters
    ----------
    taux_pct : float — taux annuel en % (ex: 3.2 pour 3.2%)

    Returns
    -------
    dict avec 'type', 'taux_pct', 'source', 'date'

    ⚠️ MÊME PIÈGE QUE POUR LE FICHIER, ET IL A DÉJÀ SERVI. Saisir `0.03` en
    pensant 3 % rendait une courbe à 0,030 % sans un mot — l'erreur a été
    commise pendant la conception de ce garde-fou, sur cette fonction même,
    et n'a été vue qu'en relisant le libellé publié.
    """
    alerte = _diagnostic_unite(taux_pct)
    if alerte:
        return {
            'type':      'erreur',
            'taux_fn':   get_taux_rfr,
            'source':    f'{alerte} — courbe embarquée utilisée',
            'date':      DATE_COURBE,
            'label':     'Courbe embarquée (taux manuel refusé)',
            'erreur':    alerte,
        }
    taux_decimal = taux_pct / 100.0
    return {
        'type':        'taux_plat',
        'taux_pct':    taux_pct,
        'taux_fn':     lambda t: taux_decimal,
        'source':      f'Taux manuel saisi par l\u2019actuaire : {taux_pct:.3f}%',
        'date':        'Arrêté courant',
        'label':       f'Taux manuel {taux_pct:.3f}%',
    }


def get_courbe_depuis_excel(fichier_bytes: bytes) -> dict:
    """
    Charge une courbe EIOPA depuis un fichier Excel uploadé.

    Format attendu : deux colonnes dans la première feuille
        - Colonne 1 : maturite (entier, années 1 à 150)
        - Colonne 2 : taux_pct (float, ex: 2.85 pour 2.85%)

    Parameters
    ----------
    fichier_bytes : bytes — contenu du fichier Excel

    Returns
    -------
    dict avec 'type', 'taux_fn', 'source', 'date', 'maturites', 'taux'
    """
    import io
    import numpy as np
    try:
        import pandas as pd
        df = pd.read_excel(io.BytesIO(fichier_bytes))
        # Renommer les colonnes
        df.columns = [str(c).lower().strip() for c in df.columns]
        # Chercher colonnes maturite et taux
        col_mat  = next((c for c in df.columns if 'matur' in c or 'mat' in c or c in ['t', 'annee', 'year']), df.columns[0])
        col_taux = next((c for c in df.columns if 'taux' in c or 'rate' in c or 'rfr' in c or c in ['r', 'pct']), df.columns[1])

        mats = df[col_mat].dropna().astype(float).tolist()
        taux = df[col_taux].dropna().astype(float).tolist()

        if len(mats) < 2 or len(taux) < 2:
            raise ValueError("Fichier invalide — moins de 2 maturités")

        # ⚠️ LE SEUL DES TROIS OBSTACLES QUI ÉCHOUERAIT EN SILENCE. Mauvaise
        # feuille et en-tête absent s'arrêtent bruyamment ; des taux en
        # décimal, eux, passeraient et produiraient une courbe cent fois trop
        # basse. On les refuse, en disant quoi faire.
        alerte = _diagnostic_unite(taux)
        if alerte:
            raise ValueError(alerte)

        mats_arr = np.array(mats)
        taux_arr = np.array(taux)

        def taux_fn(t):
            return float(np.interp(float(t), mats_arr, taux_arr)) / 100.0

        return {
            'type':      'fichier_excel',
            'taux_fn':   taux_fn,
            'source':    'Fichier Excel importé par l\u2019actuaire',
            'date':      f'Courbe personnalisée ({len(mats)} maturités)',
            'label':     f'Fichier Excel ({len(mats)} maturités)',
            'maturites': mats,
            'taux':      taux,
            'erreur':    None,
        }
    except Exception as e:
        return {
            'type':    'erreur',
            'taux_fn': lambda t: get_taux_rfr(t),
            'source':  f'Erreur chargement fichier : {e} — courbe embarquée utilisée',
            'date':    DATE_COURBE,
            'label':   f'Courbe embarquée (erreur fichier)',
            'erreur':  str(e),
        }


#: Au-delà de ce délai, la courbe embarquée est SIGNALÉE comme périmée. EIOPA
#: publie ses structures par terme MENSUELLEMENT ; un trimestre de retard reste
#: usuel entre deux arrêtés, un an ne l'est pas.
MOIS_ALERTE_PEREMPTION  = 3
MOIS_ROUGE_PEREMPTION   = 12


def age_courbe_mois(date_valorisation=None) -> float:
    """Âge de la courbe embarquée en mois, à la date de valorisation.

    `None` = aujourd'hui. Le paramètre existe pour qu'un arrêté passé soit jugé
    à SA date et non à celle du calcul — un arrêté du 31/12/2025 recalculé en
    2027 ne doit pas déclarer sa courbe périmée à tort.
    """
    from datetime import date, datetime
    if date_valorisation is None:
        ref = date.today()
    elif isinstance(date_valorisation, str):
        ref = datetime.strptime(date_valorisation[:10], '%Y-%m-%d').date()
    else:
        ref = date_valorisation
    courbe = datetime.strptime(DATE_COURBE, '%Y-%m-%d').date()
    return (ref - courbe).days / 30.4375


def diagnostic_peremption(date_valorisation=None) -> dict:
    """Statut de péremption de la courbe embarquée — VERT / AMBRE / ROUGE.

    ⚠️ POURQUOI CE DIAGNOSTIC EXISTE, ET POURQUOI LA COURBE N'EST PAS MISE À JOUR
    ICI. La courbe embarquée date du 31/03/2025 et servait par DÉFAUT sans que
    rien ne signale son âge : `get_courbe_embarquee` déclarait même
    `'erreur': None`, comme si une courbe de Q1 2025 employée en 2026 allait de
    soi. Or la Risk Margin entre au bilan (PT S2 = BE + RM), et elle actualise
    sur cette courbe.

    LES TAUX N'ONT PAS ÉTÉ REMPLACÉS À DESSEIN : la courbe EIOPA en vigueur n'est
    pas accessible depuis ce dépôt, et inventer trente taux « plausibles »
    produirait un chiffre réglementaire fabriqué — exactement ce que ce module ne
    doit pas faire. Le mécanisme d'apport existe déjà et reste la bonne réponse :
    `get_courbe_depuis_excel` charge le fichier EIOPA officiel, et
    `get_courbe_taux_plat` accepte un taux assumé par l'actuaire. Ce diagnostic
    rend simplement le défaut VISIBLE au lieu de le laisser silencieux.
    """
    mois = age_courbe_mois(date_valorisation)
    if mois >= MOIS_ROUGE_PEREMPTION:
        statut = 'ROUGE'
        message = (
            f"⚠️ COURBE DES TAUX PÉRIMÉE — la courbe EIOPA embarquée date du "
            f"{DATE_COURBE}, soit {mois:.0f} mois. La Risk Margin et toute "
            f"actualisation en découlent et ne sont pas à jour. Importer la "
            f"courbe EIOPA en vigueur (fichier officiel) ou saisir un taux "
            f"assumé avant toute inscription au bilan.")
    elif mois >= MOIS_ALERTE_PEREMPTION:
        statut = 'AMBRE'
        message = (
            f"🟡 La courbe EIOPA embarquée date du {DATE_COURBE}, soit "
            f"{mois:.0f} mois. EIOPA publie mensuellement — vérifier qu'elle "
            f"correspond bien à la date d'arrêté retenue.")
    else:
        statut = 'VERT'
        message = (f"Courbe EIOPA du {DATE_COURBE} ({mois:.0f} mois) — à jour "
                   f"pour l'arrêté retenu.")
    return {'statut': statut, 'age_mois': round(mois, 1),
            'date_courbe': DATE_COURBE, 'message': message,
            'seuil_ambre_mois': MOIS_ALERTE_PEREMPTION,
            'seuil_rouge_mois': MOIS_ROUGE_PEREMPTION}


def get_courbe_embarquee(date_valorisation=None) -> dict:
    """Retourne la courbe EIOPA embarquée comme dict standard.

    ⚠️ `erreur` N'EST PLUS INCONDITIONNELLEMENT `None`. Elle porte le message de
    péremption dès que la courbe a dépassé le seuil — c'est ce champ que les
    appelants lisent déjà, donc le signal remonte sans qu'aucun d'eux change.
    """
    diag = diagnostic_peremption(date_valorisation)
    return {
        'type':    'embarquee',
        'taux_fn': get_taux_rfr,
        'source':  SOURCE,
        'date':    DATE_COURBE,
        'label':   f'Courbe EIOPA embarquée ({DATE_COURBE})',
        'peremption': diag,
        'erreur':  None if diag['statut'] == 'VERT' else diag['message'],
    }
