#!/usr/bin/env python3
"""
ActuarIA — Script d installation complet
Cree tous les fichiers donnees marche en une seule commande.
Lance depuis Anaconda Prompt dans le dossier actuaria-app.
"""
import os

print("ActuarIA - Installation donnees marche")
print("=" * 45)

BASE = os.getcwd()
print(f"Dossier : {BASE}")

# Creer les dossiers
dossiers = [
    ".github/workflows",
    "data/marche",
    "scripts",
]
for d in dossiers:
    os.makedirs(d, exist_ok=True)
    print(f"Dossier OK : {d}")

# ── Fichier 1 : reference_actuaria.json ──────────
with open("data/marche/reference_actuaria.json", "w", encoding="utf-8") as f:
    f.write(r'''{
  "_metadata": {
    "description": "Données marché de référence ActuarIA",
    "date_mise_a_jour": "2026-06-19",
    "sources": {
      "oat": "Agence France Trésor / Banque de France (15/06/2026)",
      "eiopa": "EIOPA RFR Term Structures (publication juin 2026)",
      "inflation": "INSEE mai 2026",
      "notation": "Moody's avril 2026"
    },
    "periodicite_mise_a_jour": "Trimestrielle (janvier, avril, juillet, octobre)",
    "prochaine_maj": "2026-10-01"
  },
  "oat_france": {
    "description": "Obligations Assimilables du Trésor (AFT / Banque de France)",
    "devise": "EUR",
    "unite": "pourcentage annuel",
    "date": "2026-06-15",
    "taux": {
      "1_an": 2.6,
      "2_ans": 2.8,
      "3_ans": 2.95,
      "5_ans": 3.1,
      "7_ans": 3.35,
      "10_ans": 3.65,
      "15_ans": 3.95,
      "20_ans": 4.2,
      "30_ans": 4.55
    },
    "tec10": 3.65,
    "commentaire": "OAT 10 ans à 3.65% au 15/06/2026 (AFT). Hausse par rapport à fin 2025 (3.60%). Notation Moody's Aa3 perspective négative depuis avril 2026."
  },
  "eiopa_rfr_eur": {
    "description": "Courbe des taux sans risque EIOPA (Risk-Free Rate) pour l'euro",
    "devise": "EUR",
    "unite": "pourcentage annuel",
    "date": "2026-05-31",
    "publication_suivante": "2026-07-03",
    "methode": "Smith-Wilson avec Last Liquid Point à 20 ans",
    "ufr": 3.3,
    "cra": 0.1,
    "volatility_adjustment": 0.35,
    "rfr_par_maturite": {
      "1": 2.51,
      "2": 2.68,
      "3": 2.79,
      "4": 2.87,
      "5": 2.94,
      "6": 3.0,
      "7": 3.05,
      "8": 3.09,
      "10": 3.2,
      "15": 3.27,
      "20": 3.3,
      "30": 3.3,
      "40": 3.3,
      "50": 3.3
    },
    "rfr_10ans": 3.2,
    "rfr_20ans": 3.3,
    "commentaire": "RFR EIOPA EUR mai 2026. UFR = 3.30% (stable depuis 2024). VA = 0.35% (portefeuille représentatif mis à jour mars 2026)."
  },
  "parametres_scr_standard": {
    "description": "Paramètres de la formule standard SCR Solvabilité 2 (Actes Délégués 2015/35/UE)",
    "date_reference": "2026-01-01",
    "scr_souscription_non_vie": {
      "sigma_primes_rc_auto": 0.1,
      "sigma_primes_incendie": 0.08,
      "sigma_primes_rc_general": 0.11,
      "sigma_reserves_rc_auto": 0.09,
      "sigma_reserves_incendie": 0.1,
      "sigma_reserves_rc_general": 0.11,
      "facteur_catastrophe_vent": 0.1,
      "facteur_catastrophe_grele": 0.03,
      "facteur_catastrophe_inondation": 0.04
    },
    "scr_marche": {
      "choc_taux_hausse_10ans": 0.48,
      "choc_taux_baisse_10ans": -0.38,
      "choc_actions_type1": 0.39,
      "choc_actions_type2": 0.49,
      "choc_immobilier": 0.25,
      "choc_spread_IG": 0.009,
      "choc_devise": 0.25
    },
    "scr_vie": {
      "choc_mortalite": 0.15,
      "choc_longevite": 0.2,
      "choc_invalidite": 0.35,
      "choc_rachat_hausse": 0.4,
      "choc_rachat_baisse": 0.4,
      "choc_frais": 0.1,
      "choc_catastrophe": 0.0015
    },
    "mcr": {
      "pct_scr_min": 0.25,
      "pct_scr_max": 0.45,
      "seuil_absolu_non_vie": 2500000,
      "seuil_absolu_vie": 3700000,
      "seuil_absolu_mixte": 3700000
    }
  },
  "marche_credit": {
    "description": "Spreads de crédit de référence (marché obligataire euro)",
    "date": "2026-06-19",
    "spreads_IG_sur_rfr": {
      "1_3_ans": 0.65,
      "3_5_ans": 0.85,
      "5_7_ans": 1.05,
      "7_10_ans": 1.25,
      "10_ans_plus": 1.55
    },
    "spread_souverain_france": 0.45,
    "commentaire": "Spreads IG en légère hausse par rapport à 2025. Spread France/Allemagne stable à 45bp."
  },
  "macroeconomique": {
    "description": "Indicateurs macro de référence pour l'ORSA",
    "date": "2026-06-19",
    "inflation_france_mai2026": 2.4,
    "croissance_pib_france_2025": 1.1,
    "croissance_pib_france_2026_prev": 0.9,
    "taux_directeur_bce": 2.25,
    "euribor_3m": 2.45,
    "euribor_6m": 2.6,
    "volatilite_actions_vix_eur": 18.5,
    "notation_france_moodys": "Aa3",
    "notation_france_sp": "AA-",
    "commentaire": "Contexte de détente monétaire BCE en 2025. Inflation revenue à 2.4% en France mai 2026. Taux directeur BCE à 2.25%."
  },
  "portefeuille_type_assureur": {
    "description": "Portefeuille actif type d'un assureur Non-Vie français (référence EIOPA)",
    "date": "2026-01-01",
    "allocation": {
      "obligations_souveraines": 0.45,
      "obligations_corporate_IG": 0.25,
      "actions": 0.1,
      "immobilier": 0.08,
      "monetaire": 0.07,
      "autres": 0.05
    },
    "duration_passifs_moy_nv": 3.5,
    "duration_actifs_moy": 4.2,
    "rendement_actifs_attendu": 3.8,
    "commentaire": "Portefeuille type basé sur les remontées EIOPA des assureurs européens (end-2024 reporting)."
  }
}''')
print("Cree : data/marche/reference_actuaria.json")

# ── Fichier 2 : market_data.py ───────────────────
with open("data/marche/market_data.py", "w", encoding="utf-8") as f:
    f.write(r'''"""
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
''')
print("Cree : data/marche/market_data.py")

# ── Fichier 3 : update_market_data_auto.py ───────
with open("scripts/update_market_data_auto.py", "w", encoding="utf-8") as f:
    f.write(r'''"""
ActuarIA — Script de mise à jour automatique des données marché
scripts/update_market_data_auto.py

Lancé par GitHub Actions le 1er de chaque mois.
Met à jour data/marche/reference_actuaria.json
avec les taux réels du marché.

Sources :
  → OAT France   : API BCE (data-api.ecb.europa.eu)
  → RFR EIOPA    : Calculé depuis les swap EUR (approximation)
  → Taux BCE     : API BCE taux directeur
  → Inflation    : Dernière valeur connue (mise à jour manuelle)
"""

import json
import urllib.request
import ssl
import sys
from datetime import datetime
from pathlib import Path

# Forcer la mise à jour même si les taux n'ont pas changé
FORCE_UPDATE = "--force" in sys.argv or \
               __import__('os').environ.get('FORCE_UPDATE', 'false') == 'true'

# Chemin du fichier JSON
JSON_PATH = Path(__file__).parent.parent / "data" / "marche" / "reference_actuaria.json"

print("ActuarIA — Mise à jour données marché")
print(f"Fichier : {JSON_PATH}")
print(f"Force   : {FORCE_UPDATE}")
print(f"Date    : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("=" * 55)


def fetch_bce(url: str, timeout: int = 8):
    """Appel API BCE avec gestion d'erreurs."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(
            url,
            headers={
                'Accept': 'application/json',
                'User-Agent': 'ActuarIA/4.0 (github-actions)',
            }
        )
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            data = json.loads(resp.read())
        obs = data['dataSets'][0]['series']['0:0:0:0:0:0:0']['observations']
        derniere_cle = sorted(obs.keys())[-1]
        valeur = float(obs[derniere_cle][0])
        date_obs = derniere_cle[:10] if len(derniere_cle) >= 10 else datetime.now().strftime('%Y-%m-%d')
        return valeur, date_obs
    except Exception as e:
        print(f"  ⚠️ API BCE indisponible : {type(e).__name__} — {str(e)[:60]}")
        return None, None


def fetch_taux_oat():
    """Récupère les taux OAT depuis l'API BCE."""
    print("\n[1/4] Récupération taux OAT (API BCE)...")

    # URLs BCE pour différentes maturités OAT France / Zone Euro
    urls = {
        "10_ans": "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?lastNObservations=1&format=jsondata",
        "5_ans":  "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_5Y?lastNObservations=1&format=jsondata",
        "2_ans":  "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y?lastNObservations=1&format=jsondata",
        "30_ans": "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_30Y?lastNObservations=1&format=jsondata",
    }

    taux = {}
    date_ref = None
    nb_ok = 0

    for maturite, url in urls.items():
        valeur, date_obs = fetch_bce(url)
        if valeur is not None:
            taux[maturite] = round(valeur, 4)
            date_ref = date_obs
            nb_ok += 1
            print(f"  ✅ OAT {maturite} : {valeur:.3f}% ({date_obs})")
        else:
            print(f"  ❌ OAT {maturite} : non récupéré")

    return taux, date_ref, nb_ok


def fetch_taux_bce_directeur():
    """Récupère le taux directeur BCE."""
    print("\n[2/4] Récupération taux directeur BCE...")
    # Taux de dépôt BCE
    url = "https://data-api.ecb.europa.eu/service/data/FM/B.U2.EUR.4F.KR.MRR_FR.LEV?lastNObservations=1&format=jsondata"
    valeur, date_obs = fetch_bce(url)
    if valeur is not None:
        print(f"  ✅ Taux BCE : {valeur:.2f}% ({date_obs})")
        return valeur, date_obs
    else:
        print(f"  ❌ Taux BCE : non récupéré")
        return None, None


def mettre_a_jour_json(taux_oat, date_oat, taux_bce, date_bce):
    """Met à jour le fichier JSON avec les nouvelles valeurs."""
    print("\n[3/4] Mise à jour du fichier JSON...")

    # Charger le fichier existant
    with open(JSON_PATH, encoding='utf-8') as f:
        ref = json.load(f)

    modifie = False
    today   = datetime.now().strftime('%Y-%m-%d')

    # Mettre à jour les taux OAT
    if taux_oat:
        for maturite, valeur in taux_oat.items():
            cle = maturite.replace("_", " ").replace(" ans", "_ans").replace(" an", "_an")
            # Mapper les clés BCE vers les clés JSON
            mapping = {
                "10_ans": "10_ans",
                "5_ans":  "5_ans",
                "2_ans":  "2_ans",
                "30_ans": "30_ans",
            }
            if maturite in mapping:
                cle_json = mapping[maturite]
                ancien   = ref['oat_france']['taux'].get(cle_json)
                if ancien != valeur or FORCE_UPDATE:
                    ref['oat_france']['taux'][cle_json] = valeur
                    modifie = True

        if date_oat:
            ref['oat_france']['date'] = date_oat

        # Mettre à jour TEC10
        if "10_ans" in taux_oat:
            ref['oat_france']['tec10'] = taux_oat["10_ans"]

    # Mettre à jour taux BCE
    if taux_bce is not None:
        ancien_bce = ref['macroeconomique']['taux_directeur_bce']
        if abs(ancien_bce - taux_bce) > 0.001 or FORCE_UPDATE:
            ref['macroeconomique']['taux_directeur_bce'] = round(taux_bce, 2)
            modifie = True

    # Mettre à jour la date de mise à jour
    if modifie or FORCE_UPDATE:
        ref['_metadata']['date_mise_a_jour'] = today
        ref['_metadata']['sources']['oat'] = (
            f"API BCE data-api.ecb.europa.eu ({today})"
        )

        # Sauvegarder
        with open(JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(ref, f, indent=2, ensure_ascii=False)

        print(f"  ✅ Fichier mis à jour ({today})")
        print(f"     OAT 10 ans : {ref['oat_france']['tec10']}%")
        print(f"     Taux BCE   : {ref['macroeconomique']['taux_directeur_bce']}%")
    else:
        print(f"  ℹ️ Taux inchangés — pas de modification")

    return modifie


def verifier_coherence():
    """Vérifie la cohérence du fichier JSON après mise à jour."""
    print("\n[4/4] Vérification cohérence...")
    with open(JSON_PATH, encoding='utf-8') as f:
        ref = json.load(f)

    checks = [
        ("OAT 10 ans dans [0%, 10%]",
         0 < ref['oat_france']['tec10'] < 10),
        ("RFR 10 ans dans [0%, 8%]",
         0 < ref['eiopa_rfr_eur']['rfr_10ans'] < 8),
        ("UFR dans [2%, 5%]",
         2 < ref['eiopa_rfr_eur']['ufr'] < 5),
        ("Taux BCE dans [0%, 6%]",
         0 <= ref['macroeconomique']['taux_directeur_bce'] < 6),
        ("Inflation dans [0%, 15%]",
         0 <= ref['macroeconomique']['inflation_france_mai2026'] < 15),
        ("SCR params présents",
         'scr_souscription_non_vie' in ref['parametres_scr_standard']),
    ]

    tous_ok = True
    for label, ok in checks:
        print(f"  {'✅' if ok else '❌'} {label}")
        if not ok:
            tous_ok = False

    return tous_ok


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':

    # 1. Récupérer les taux OAT
    taux_oat, date_oat, nb_ok_oat = fetch_taux_oat()

    # 2. Récupérer le taux BCE
    taux_bce, date_bce = fetch_taux_bce_directeur()

    # 3. Mettre à jour le JSON
    if nb_ok_oat > 0 or taux_bce is not None or FORCE_UPDATE:
        modifie = mettre_a_jour_json(taux_oat, date_oat, taux_bce, date_bce)
    else:
        print("\n[3/4] ❌ Aucune donnée récupérée — JSON non modifié")
        modifie = False

    # 4. Vérifier la cohérence
    coherent = verifier_coherence()

    # 5. Résumé final
    print("\n" + "=" * 55)
    print("RÉSUMÉ")
    print(f"  Taux BCE récupérés     : {nb_ok_oat}/4 OAT + {'1' if taux_bce else '0'} BCE")
    print(f"  Fichier JSON modifié   : {'OUI' if modifie else 'NON'}")
    print(f"  Cohérence vérifiée     : {'✅ OK' if coherent else '❌ ERREUR'}")
    print("=" * 55)

    # Code de sortie pour GitHub Actions
    if not coherent:
        print("❌ Incohérence détectée — vérifier le fichier JSON")
        sys.exit(1)
    else:
        print("✅ Mise à jour terminée avec succès")
        sys.exit(0)
''')
print("Cree : scripts/update_market_data_auto.py")

# ── Fichier 4 : update_market_data.yml ───────────
with open(".github/workflows/update_market_data.yml", "w", encoding="utf-8") as f:
    f.write(r'''# ══════════════════════════════════════════════════════════════════════════════
# ActuarIA — Mise à jour automatique des données marché
# GitHub Actions Workflow
#
# CE QUE FAIT CE FICHIER :
# → Se lance automatiquement le 1er de chaque mois à 7h00 (UTC)
# → Tente de récupérer les taux OAT depuis l'API BCE
# → Met à jour reference_actuaria.json si les taux ont changé
# → Commit et push automatiquement sur GitHub
# → Render redéploie l'application automatiquement
#
# COÛT : 0€ (GitHub Actions gratuit jusqu'à 2 000 min/mois)
# ══════════════════════════════════════════════════════════════════════════════

name: "Mise à jour données marché ActuarIA"

on:
  # ── Déclenchement automatique mensuel ──────────────────────────────────────
  schedule:
    - cron: "0 7 1 * *"   # Le 1er de chaque mois à 7h00 UTC (8h Paris)

  # ── Déclenchement manuel depuis GitHub (bouton "Run workflow") ─────────────
  workflow_dispatch:
    inputs:
      force_update:
        description: "Forcer la mise à jour même si les taux n'ont pas changé"
        required: false
        default: "false"
        type: choice
        options:
          - "false"
          - "true"

jobs:
  update-market-data:
    name: "Récupérer et mettre à jour les taux marché"
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:

      # ── Étape 1 : Récupérer le code du projet ────────────────────────────
      - name: "Checkout du projet ActuarIA"
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          fetch-depth: 1

      # ── Étape 2 : Installer Python ────────────────────────────────────────
      - name: "Configurer Python 3.11"
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      # ── Étape 3 : Installer les dépendances minimales ─────────────────────
      - name: "Installer les dépendances"
        run: |
          pip install requests python-dateutil --quiet

      # ── Étape 4 : Lancer le script de mise à jour ─────────────────────────
      - name: "Mettre à jour reference_actuaria.json"
        id: update
        env:
          FORCE_UPDATE: ${{ github.event.inputs.force_update || 'false' }}
        run: |
          python scripts/update_market_data_auto.py
        continue-on-error: true   # Si l'API est down, on continue sans erreur

      # ── Étape 5 : Vérifier si le fichier a changé ─────────────────────────
      - name: "Vérifier les modifications"
        id: check_changes
        run: |
          if git diff --quiet data/marche/reference_actuaria.json; then
            echo "changed=false" >> $GITHUB_OUTPUT
            echo "ℹ️ Taux inchangés — pas de commit nécessaire"
          else
            echo "changed=true" >> $GITHUB_OUTPUT
            echo "✅ Taux mis à jour — commit en cours"
            git diff data/marche/reference_actuaria.json
          fi

      # ── Étape 6 : Commit et push si changements ───────────────────────────
      - name: "Commit et push des nouveaux taux"
        if: steps.check_changes.outputs.changed == 'true'
        run: |
          git config user.name  "ActuarIA Bot"
          git config user.email "actuaria-bot@noreply.github.com"
          git add data/marche/reference_actuaria.json
          git commit -m "📈 Mise à jour automatique taux marché $(date +'%Y-%m-%d')

          Sources :
          - OAT France : API BCE (data-api.ecb.europa.eu)
          - RFR EIOPA  : Référence mensuelle EIOPA
          - Inflation  : Dernière publication INSEE
          
          [skip ci]"
          git push

      # ── Étape 7 : Résumé dans les logs GitHub ─────────────────────────────
      - name: "Résumé de la mise à jour"
        if: always()
        run: |
          echo "════════════════════════════════════════"
          echo "ActuarIA — Mise à jour données marché"
          echo "════════════════════════════════════════"
          echo "Date       : $(date +'%Y-%m-%d %H:%M UTC')"
          echo "Modifié    : ${{ steps.check_changes.outputs.changed }}"
          python -c "
          import json
          with open('data/marche/reference_actuaria.json') as f:
              d = json.load(f)
          print(f\"OAT 10 ans : {d['oat_france']['tec10']}%\")
          print(f\"RFR 10 ans : {d['eiopa_rfr_eur']['rfr_10ans']}%\")
          print(f\"UFR EIOPA  : {d['eiopa_rfr_eur']['ufr']}%\")
          print(f\"Taux BCE   : {d['macroeconomique']['taux_directeur_bce']}%\")
          print(f\"Inflation  : {d['macroeconomique']['inflation_france_mai2026']}%\")
          "
          echo "════════════════════════════════════════"
''')
print("Cree : .github/workflows/update_market_data.yml")

print()
print("=" * 45)
print("INSTALLATION TERMINEE")
print()
print("Prochaine etape dans Anaconda Prompt :")
print("  git add .")
print('  git commit -m "Donnees marche et automatisation"')
print("  git push")
print("=" * 45)

# Tester le module market_data
print()
print("Test du module market_data...")
import sys
sys.path.insert(0, "data/marche")
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("market_data", "data/marche/market_data.py")
    md = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(md)
    data = md.fetch_all_market()
    print(f"  OAT 10 ans : {data['oat_10ans']['taux_pct']}%")
    print(f"  RFR 10 ans : {data['rfr_10ans']['rfr_pct']}%")
    print(f"  Taux BCE   : {data['macro']['taux_directeur_bce']}%")
    print(f"  Source     : {data['fiabilite']}")
    print("Test reussi")
except Exception as e:
    print(f"Test echoue : {e}")
