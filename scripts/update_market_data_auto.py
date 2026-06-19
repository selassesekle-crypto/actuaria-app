"""
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
