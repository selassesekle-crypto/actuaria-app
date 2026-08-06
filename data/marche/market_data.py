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


# ⚠️ `fetch_rfr_eiopa` A ETE RETIREE AU LOT R5, AVEC LE BLOC
# `eiopa_rfr_eur` du fichier de reference. La courbe des taux sans risque
# vit desormais dans `core/courbe_rfr.py`, source unique pour A7, A8, A10,
# A11 et A12 -- tous rendaient 3,1590 % au dix ans quand celle-ci en
# annoncait 3,2000, soit 4,1 points de base d'ecart. Elle etait de surcroit
# PLATE A L'UFR des vingt ans, ce qu'aucune courbe Smith-Wilson ne fait :
# ce n'etait pas une extraction EIOPA mais une esquisse, et aucun agent ne
# la lisait. Ce module n'expose plus de taux d'actualisation.

# ⚠️ `fetch_parametres_scr` A ETE RETIREE, AVEC LE BLOC
# `parametres_scr_standard` du fichier de reference. Les parametres de la
# formule standard vivent dans `reglementation/parametres_fs.py`, source
# unique pour A8 et A10 -- comme les ecarts types vivent dans
# `segments_s2.py` depuis le chantier B10. Ce module ne porte plus aucun
# parametre reglementaire : il ne fait que des DONNEES DE MARCHE.

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
    macro  = fetch_macro()
    ptf    = fetch_portefeuille_type()

    signaux.append(oat10['signal'])
    signaux.append(oat5['signal'])

    # Fiabilité globale
    fiabilite = 'TEMPS_REEL' if any(
        d.get('fiabilite') == 'TEMPS_REEL'
        for d in [oat10, oat5]
    ) else 'REFERENCE'

    source_globale = (
        "✅ Données marché BCE temps réel"
        if fiabilite == 'TEMPS_REEL' else
        f"⚠️ Données de référence uniquement (mise à jour : {oat10['date']}) — "
        f"API BCE indisponible dans cet environnement"
    )

    logger.info(f"fetch_all_market() → {fiabilite} | {oat10['signal'][:50]}")

    return {
        'oat_10ans':      oat10,
        'oat_5ans':       oat5,
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
    # Le taux sans risque ne s'affiche plus ici : `core/courbe_rfr.py` en est
    # la source unique depuis le lot R5.
    print(f"Taux BCE   : {data['macro']['taux_directeur_bce']}%")
    print(f"Inflation  : {data['macro']['inflation_france_mai2026']}%")

    print("\nSignaux :")
    for s in data['signaux']:
        print(f"  {s}")
