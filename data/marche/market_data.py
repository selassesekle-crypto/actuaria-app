"""
ActuarIA — Module Données Marché
market_data.py

Point d'entrée unique pour toutes les données de marché
utilisées par A8 (Stress Testing), A10 (SCR S2) et A12 (ALM).

Architecture en 3 niveaux :
  Niveau 1 — Fichier référence local (toujours disponible, offline)
  Niveau 2 — API BCE en temps réel (si connexion disponible)
  Niveau 3 — Signal clair à l'utilisateur sur la source utilisée

Utilisé par :
  → A8  Isabelle : taux pour calibrer les chocs S2 taux
  → A10 Elena    : RFR EIOPA pour actualiser le BE
  → A12 Aisha    : OAT pour l'immunisation ALM
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("actuaria.market_data")

# Chemin du fichier de référence (relatif à ce fichier)
_REF_FILE = Path(__file__).parent / "reference_actuaria.json"
# Fallback si le fichier est ailleurs (ex: Colab)
_REF_FILE_FALLBACK = Path("data/marche/reference_actuaria.json")

# URLs API BCE (désactivées en environnement sandbox, actives en production)
_BCE_API_BASE = "https://data-api.ecb.europa.eu/service/data"
_BCE_OAT_10Y  = f"{_BCE_API_BASE}/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?lastNObservations=1&format=jsondata"
_BCE_OAT_5Y   = f"{_BCE_API_BASE}/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_5Y?lastNObservations=1&format=jsondata"


def _charger_reference() -> Dict:
    """Charge le fichier de référence local."""
    for path in [_REF_FILE, _REF_FILE_FALLBACK]:
        if path.exists():
            with open(path, encoding='utf-8') as f:
                return json.load(f)
    raise FileNotFoundError(
        f"Fichier reference_actuaria.json introuvable. "
        f"Vérifier : {_REF_FILE} ou {_REF_FILE_FALLBACK}"
    )


def _fetch_bce_api(url: str, timeout: int = 5) -> Optional[float]:
    """
    Tente de récupérer une valeur depuis l'API BCE.
    Retourne None si indisponible (403, timeout, réseau).
    """
    try:
        import urllib.request, ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            url,
            headers={'Accept': 'application/json', 'User-Agent': 'ActuarIA/4.0'}
        )
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            data = json.loads(resp.read())
        obs = data['dataSets'][0]['series']['0:0:0:0:0:0:0']['observations']
        derniere = sorted(obs.keys())[-1]
        return float(obs[derniere][0])
    except Exception:
        return None


def fetch_oat_bce(maturite_ans: int = 10) -> Dict:
    """
    Récupère le taux OAT France pour la maturité demandée.

    Priorité :
      1. API BCE temps réel
      2. Fichier reference_actuaria.json (fallback)

    Retourne :
      {
        'taux_pct': float,       # Taux en %
        'maturite': int,         # Maturité en années
        'source': str,           # 'BCE temps réel' ou 'Référence AAAA-MM-JJ'
        'date': str,             # Date de la donnée
        'fiabilite': str,        # 'TEMPS_REEL' ou 'REFERENCE'
      }
    """
    ref = _charger_reference()
    ref_oat = ref['oat_france']

    # Essayer API BCE
    url_map = {5: _BCE_OAT_5Y, 10: _BCE_OAT_10Y}
    if maturite_ans in url_map:
        valeur_api = _fetch_bce_api(url_map[maturite_ans])
        if valeur_api is not None:
            logger.info(f"OAT {maturite_ans}ans depuis BCE temps réel : {valeur_api:.3f}%")
            return {
                'taux_pct':  round(valeur_api, 4),
                'maturite':  maturite_ans,
                'source':    'BCE temps réel',
                'date':      datetime.now().strftime('%Y-%m-%d'),
                'fiabilite': 'TEMPS_REEL',
                'signal':    f"✅ OAT {maturite_ans}ans = {valeur_api:.3f}% (BCE temps réel)",
            }

    # Fallback fichier référence
    cle = f"{maturite_ans}_ans" if maturite_ans > 1 else f"{maturite_ans}_an"
    taux_ref = ref_oat['taux'].get(cle, ref_oat['tec10'])
    date_ref  = ref_oat['date']

    logger.info(f"OAT {maturite_ans}ans depuis référence ({date_ref}) : {taux_ref:.3f}%")
    return {
        'taux_pct':  round(taux_ref, 4),
        'maturite':  maturite_ans,
        'source':    f"Référence {date_ref}",
        'date':      date_ref,
        'fiabilite': 'REFERENCE',
        'signal':    f"⚠️ OAT {maturite_ans}ans = {taux_ref:.3f}% (référence {date_ref} — API BCE indisponible)",
    }


def fetch_rfr_eiopa(maturite_ans: int = 10) -> Dict:
    """
    Récupère le taux sans risque EIOPA (RFR) pour la maturité demandée.
    Toujours depuis le fichier référence (EIOPA publie mensuellement en Excel).

    Retourne :
      {
        'rfr_pct': float,        # RFR en %
        'rfr_avec_va_pct': float,# RFR + Volatility Adjustment
        'ufr': float,            # Ultimate Forward Rate
        'va': float,             # Volatility Adjustment
        'maturite': int,
        'source': str,
        'fiabilite': str,
      }
    """
    ref = _charger_reference()
    rfr_data = ref['eiopa_rfr_eur']

    cle = str(maturite_ans)
    rfr = rfr_data['rfr_par_maturite'].get(cle)
    if rfr is None:
        # Interpolation simple entre maturités disponibles
        maturites = sorted([int(k) for k in rfr_data['rfr_par_maturite'].keys()])
        for i in range(len(maturites) - 1):
            if maturites[i] <= maturite_ans <= maturites[i+1]:
                t = (maturite_ans - maturites[i]) / (maturites[i+1] - maturites[i])
                rfr_inf = rfr_data['rfr_par_maturite'][str(maturites[i])]
                rfr_sup = rfr_data['rfr_par_maturite'][str(maturites[i+1])]
                rfr = rfr_inf * (1 - t) + rfr_sup * t
                break
        if rfr is None:
            rfr = rfr_data['ufr']

    va  = rfr_data['volatility_adjustment']
    ufr = rfr_data['ufr']
    rfr_avec_va = rfr + va

    date_ref = rfr_data['date']
    pub_suiv = rfr_data['publication_suivante']

    logger.info(f"RFR EIOPA {maturite_ans}ans : {rfr:.3f}% | VA : {va:.2f}% | UFR : {ufr:.2f}%")

    return {
        'rfr_pct':        round(rfr, 4),
        'rfr_avec_va_pct':round(rfr_avec_va, 4),
        'ufr':            ufr,
        'va':             va,
        'cra':            rfr_data['cra'],
        'maturite':       maturite_ans,
        'source':         f"EIOPA RFR EUR ({date_ref})",
        'date':           date_ref,
        'prochaine_pub':  pub_suiv,
        'fiabilite':      'REFERENCE',
        'signal':         f"ℹ️ RFR EIOPA {maturite_ans}ans = {rfr:.3f}% + VA {va:.2f}% = {rfr_avec_va:.3f}% (pub. {date_ref})",
    }


def fetch_parametres_scr() -> Dict:
    """
    Retourne les paramètres de la formule standard SCR S2.
    Utilisé par A8 (chocs) et A10 (calcul SCR).
    """
    ref = _charger_reference()
    params = ref['parametres_scr_standard']
    logger.info(f"Paramètres SCR S2 chargés (ref. {params['date_reference']})")
    return params


def fetch_macro() -> Dict:
    """
    Retourne les indicateurs macroéconomiques de référence.
    Utilisé par A8 (ORSA) et A10 (calibrage chocs).
    """
    ref = _charger_reference()
    macro = ref['macroeconomique']
    logger.info(f"Macro chargés : inflation={macro['inflation_france_mai2026']}% | BCE={macro['taux_directeur_bce']}%")
    return macro


def fetch_portefeuille_type() -> Dict:
    """
    Retourne le portefeuille type d'un assureur Non-Vie français.
    Utilisé par A12 (ALM) pour calibrer la duration actifs.
    """
    ref = _charger_reference()
    ptf = ref['portefeuille_type_assureur']
    logger.info(f"Portefeuille type chargé : rendement={ptf['rendement_actifs_attendu']}%")
    return ptf


def fetch_all_market() -> Dict:
    """
    Point d'entrée principal — toutes les données marché en un appel.
    Retourne un dict complet utilisable par A8, A10 et A12.

    Structure de retour :
    {
        'oat_10ans':     dict,   # OAT 10 ans (source + valeur)
        'oat_5ans':      dict,   # OAT 5 ans
        'rfr_10ans':     dict,   # RFR EIOPA 10 ans
        'rfr_20ans':     dict,   # RFR EIOPA 20 ans (pour A12 ALM)
        'scr_params':    dict,   # Paramètres formule standard
        'macro':         dict,   # Indicateurs macro
        'portefeuille':  dict,   # Portefeuille type
        'source_globale':str,    # Résumé des sources
        'fiabilite':     str,    # 'TEMPS_REEL' si au moins une source live
        'signaux':       list,   # Signaux pour affichage utilisateur
        'date_collecte': str,    # Horodatage de la collecte
    }
    """
    signaux = []

    oat10  = fetch_oat_bce(10)
    oat5   = fetch_oat_bce(5)
    rfr10  = fetch_rfr_eiopa(10)
    rfr20  = fetch_rfr_eiopa(20)
    params = fetch_parametres_scr()
    macro  = fetch_macro()
    ptf    = fetch_portefeuille_type()

    signaux.append(oat10['signal'])
    signaux.append(oat5['signal'])
    signaux.append(rfr10['signal'])
    signaux.append(rfr20['signal'])

    # Fiabilité globale
    fiabilite = 'TEMPS_REEL' if any(
        d.get('fiabilite') == 'TEMPS_REEL'
        for d in [oat10, oat5, rfr10, rfr20]
    ) else 'REFERENCE'

    source_globale = (
        "✅ Données marché BCE temps réel + EIOPA référence"
        if fiabilite == 'TEMPS_REEL' else
        f"⚠️ Données de référence uniquement (mise à jour : {oat10['date']}) — "
        f"API BCE indisponible dans cet environnement"
    )

    logger.info(f"fetch_all_market() → {fiabilite} | {oat10['signal'][:50]}")

    return {
        'oat_10ans':      oat10,
        'oat_5ans':       oat5,
        'rfr_10ans':      rfr10,
        'rfr_20ans':      rfr20,
        'scr_params':     params,
        'macro':          macro,
        'portefeuille':   ptf,
        'source_globale': source_globale,
        'fiabilite':      fiabilite,
        'signaux':        signaux,
        'date_collecte':  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


# ── Test rapide si exécuté directement ────────────────────────────────────
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
        format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')

    print("ActuarIA — Module Données Marché")
    print("=" * 55)

    data = fetch_all_market()

    print(f"\nSource globale : {data['source_globale']}")
    print(f"Fiabilité      : {data['fiabilite']}")
    print(f"Date collecte  : {data['date_collecte']}")

    print(f"\nOAT 10 ans : {data['oat_10ans']['taux_pct']}%  ({data['oat_10ans']['source']})")
    print(f"OAT 5 ans  : {data['oat_5ans']['taux_pct']}%  ({data['oat_5ans']['source']})")
    print(f"RFR 10 ans : {data['rfr_10ans']['rfr_pct']}%  (RFR sans VA)")
    print(f"RFR+VA 10a : {data['rfr_10ans']['rfr_avec_va_pct']}%  (RFR + Volatility Adjustment)")
    print(f"UFR EIOPA  : {data['rfr_10ans']['ufr']}%")
    print(f"Taux BCE   : {data['macro']['taux_directeur_bce']}%")
    print(f"Inflation  : {data['macro']['inflation_france_mai2026']}%")

    print("\nSignaux :")
    for s in data['signaux']:
        print(f"  {s}")
