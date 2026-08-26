"""Produit un rapport de tarification Non-Vie COMPLET, hors interface.

Rejoue la chaine A1 -> A2 -> A3 -> A4 -> A6 puis appelle le generateur de
rapport avec les TROIS resultats (A3, A4, A6). A4 sait deja generer un rapport
en fin de run(), mais SANS A6 : la section 5 (backtesting walk-forward) y est
donc vide. Ce lanceur passe les trois, et ecrit les fichiers sur disque.

A quoi il sert : REGARDER le livrable tel qu'un actuaire le recevra, plutot que
de deduire son contenu du code. C'est par lui que sont apparus, entre autres,
le classement sans note de lecture, la sentinelle de calibration publiee comme
une mesure et les journaux eteints a l'import.

Portefeuille : le generateur DETERMINISTE du depot
(demos/pipeline_3lob_a1_a6_demo.portefeuille_auto), graine 2026. Rien n'est
telecharge, rien n'est fabrique pour l'occasion.

Usage :
    py scripts/rapport_tarif_local.py [dossier_de_sortie] [nb_contrats]
"""
import logging
import os
import sys
import tempfile
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from core.plan_tarifaire import PlanTarifaire
from demos.pipeline_3lob_a1_a6_demo import portefeuille_auto
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
from direction_non_vie.tarification.services.rapport_modeles_tarif import (
    generer_rapport_tarification,
)

TMP = os.path.join(tempfile.gettempdir(), 'actuaria_rapport_tarif')


def verifier_journal_ouvert():
    """Le journal d'`actuaria` est-il encore audible ? On le dit AVANT.

    ⚠️ CE CONTROLE EXISTE PARCE QUE LE DEFAUT A EXISTE. La demo dont ce
    lanceur importe le generateur de portefeuille reglait `actuaria` a ERROR
    et `actuaria.tarif.rapport` a CRITICAL AU NIVEAU MODULE : le seul import
    eteignait le journal, et ce lanceur perdait sa ligne finale sans qu'aucun
    message ne le signale. Corrige a la source — mais un silence qui revient
    doit se VOIR, pas se deviner.
    """
    muets = [nom for nom in ('actuaria', 'actuaria.tarif.rapport')
             if logging.getLogger(nom).getEffectiveLevel() > logging.INFO]
    if muets:
        print(f"  /!\\ JOURNAL ETEINT PAR UN IMPORT : {', '.join(muets)}")
        print('      un module importe a reconfigure le journal du processus ;'
              ' la sortie ci-dessous est INCOMPLETE.')
    return not muets


def main():
    sortie = sys.argv[1] if len(sys.argv) > 1 else str(RACINE / 'audit')
    nb_contrats = int(sys.argv[2]) if len(sys.argv) > 2 else 12000

    # ⚠️ SANS CECI, LA SORTIE REDIRIGEE EST ILLISIBLE : le journal part sur
    # stderr (sans tampon) et les `print` sur stdout (par blocs des que ce
    # n'est plus un terminal). Dans un fichier, la banniere se retrouvait
    # APRES la centaine de lignes de journal qu'elle est censee introduire.
    sys.stdout.reconfigure(line_buffering=True)

    warnings.filterwarnings('ignore')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%H:%M:%S')

    os.makedirs(TMP, exist_ok=True)
    os.makedirs(sortie, exist_ok=True)
    maintenant = datetime.now(timezone.utc).astimezone()

    # --- la cle est-elle la ? on le dit AVANT, pas apres ---------------------
    cle = os.environ.get('ANTHROPIC_API_KEY')
    print('=' * 74)
    print('  ANTHROPIC_API_KEY : {}'.format(
        'definie -> narration Claude ATTENDUE' if cle
        else 'ABSENTE -> repli sur commentaire agent'))
    print(f'  portefeuille      : {nb_contrats} contrats, generateur'
          f' deterministe du depot')
    print(f'  sortie            : {sortie}')
    verifier_journal_ouvert()
    print('=' * 74)

    df = portefeuille_auto(nb_contrats, np.random.default_rng(2026))
    plan = PlanTarifaire.depuis_yaml(str(RACINE / 'plans' / 'auto.yaml'))

    r1 = AgentA1Ingestion(audit_path=TMP, verbose=False).run(
        branche='non_vie', sous_branche='auto', dataframe=df)
    r2 = AgentA2Preprocessing(audit_path=TMP, verbose=False).run(
        result_a1=r1, plan=plan)
    r3 = AgentA3GLM(models_path=TMP, audit_path=TMP, verbose=False).run(
        result_a2=r2, plan=plan, generer_graphiques=True)
    r4 = AgentA4ML(models_path=TMP, audit_path=TMP, verbose=False).run(
        result_a2=r2, result_a3=r3, plan=plan, calcul_shap=False,
        generer_graphiques=True)
    r6 = AgentA6Comparaison(models_path=TMP, audit_path=TMP, verbose=False).run(
        result_a2=r2, result_a3=r3, result_a4=r4, result_a5=None,
        col_cible='nb_sinistres', generer_graphiques=True,
        generer_rapport_equipe=False, environnement='production',
        # ⚠️ MEME DEFAUT QUE LA DEMO, ET IL ETAIT DANS MON PROPRE OUTIL :
        # << Actuaire >> satisfaisait le controle de gouvernance sans nommer
        # personne. Le rapport produit ici est une verification, pas un
        # livrable signe — il le dit.
        profil_valide_par='VERIFICATION LOCALE - aucun actuaire responsable')

    horodatage = maintenant.strftime('%Y%m%d_%H%M%S')
    rapports = generer_rapport_tarification(
        result_a3=r3, result_a4=r4, result_a6=r6,
        ref_client='PORTEFEUILLE DE DEMONSTRATION',
        # ⚠️ Arrêté NON déclaré, VOLONTAIREMENT : ce script est une VÉRIFICATION,
        # pas un livrable signé (cf. profil_valide_par ci-dessus). Le rapport
        # affichera « Arrêté : non déclaré » plutôt que la date du jour glissée
        # sous cette étiquette — l'absence honnête, jamais un now() masquant.
        audit_id=f'LOCAL_{horodatage}',
        formats=['html', 'word'],          # PDF exclu : weasyprint absent
    )

    print()
    print('=' * 74)
    ecrits = []
    for cle_fmt, ext in (('html_bytes', 'html'), ('word_bytes', 'docx')):
        donnees = rapports.get(cle_fmt) or b''
        if not donnees:
            print(f'  {ext:<12} : VIDE')
            continue
        chemin = os.path.join(sortie,
                              f'rapport_tarification_{horodatage}.{ext}')
        contenu = (donnees if isinstance(donnees, bytes)
                   else donnees.encode('utf-8'))
        with open(chemin, 'wb') as f:
            f.write(contenu)
        ecrits.append(chemin)
        print(f'  {ext:<12} : {len(contenu):>9,} octets -> {chemin}')

    # --- d'ou vient la narration ? c'est LA question du jour -----------------
    html = rapports.get('html_bytes') or b''
    texte = (html.decode('utf-8', 'replace') if isinstance(html, bytes)
             else str(html))
    if 'ActuarIA Intelligence' in texte:
        verdict = 'NARRATION CLAUDE (appel API reussi)'
    elif 'appel refuse' in texte:
        verdict = 'REPLI SUR DEFAUT DE CONFIGURATION (requete refusee)'
    elif "commentaire de l'agent" in texte:
        verdict = 'repli sur commentaire agent (API indisponible)'
    else:
        verdict = 'source indeterminee'
    print()
    print(f'  SOURCE DE LA NARRATION : {verdict}')
    print('=' * 74)
    return 0 if ecrits else 1


if __name__ == '__main__':
    sys.exit(main())
