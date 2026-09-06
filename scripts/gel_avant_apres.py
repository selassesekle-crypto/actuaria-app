"""Le gel des livrables, EXECUTE en avant/apres autour d'un correctif.

A quoi il sert : rendre la condition (4) -- << aucun euro n'a bouge >> --
MESURABLE au lieu d'etre affirmee. Il produit les livrables signes de toute la
chaine A1->A6 plus les deux rapports, en calcule l'empreinte normalisee
(`services/gel_livrables`), et la depose dans un fichier. Deux fichiers pris
avant et apres un correctif se comparent ensuite ecart par ecart, chacun nomme
par sa surface, sa feuille et sa coordonnee.

    py scripts/gel_avant_apres.py --sortie <fichier.json>
    py scripts/gel_avant_apres.py --comparer <avant.json> <apres.json>

⚠️⚠️ LE FICHIER SE DEPOSE HORS DU DEPOT. C'est une mesure derivee, volumineuse,
propre a un arbre : la versionner ferait entrer dans un depot PUBLIC le
contenu de livrables de demonstration. Aucun chemin par defaut n'est donc
propose -- `--sortie` est obligatoire, et c'est voulu.

⚠️⚠️ DEUX EMPREINTES NE SE COMPARENT QUE SI ELLES VIENNENT DU MEME JEU
D'ENTREE. Le fichier porte donc sa graine, sa taille de portefeuille et son
arrete, et `--comparer` REFUSE deux fichiers qui n'ont pas les memes. *Un
ecart lu entre deux assiettes differentes mesurerait le jeu de donnees, pas le
correctif* -- et il aurait l'air d'une mesure.

⚠️ CE QUI EST COMPARE SE DECLARE : le verdict publie son assiette et la liste
des surfaces qu'il n'a PAS su lire. Un << 0 ecart >> qui tairait trois
surfaces illisibles serait le pire resultat possible ici.
"""
import argparse
import json
import logging
import os
import subprocess
import sys
import time
import warnings

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)

#: Le jeu d'entree. ⚠️ Il voyage AVEC la mesure, dans le fichier produit.
GRAINE = 7
TAILLE = 1200
ARRETE = '2026-06-30'
ANNEES = (2021, 2022, 2023, 2024, 2025)


def _tete_git() -> str:
    """La tete, ET l'etat de l'arbre de travail.

    ⚠️⚠️ `rev-parse HEAD` SEUL EST UN PIEGE ICI. Une empreinte prise sur un
    arbre modifie porterait le meme identifiant qu'une empreinte prise sur
    l'arbre propre : deux mesures de deux codes differents, etiquetees
    pareil. *La cle doit suivre la donnee.* Le suffixe `+modifie` le dit.
    """
    try:
        tete = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                              cwd=RACINE, capture_output=True, text=True,
                              timeout=20, check=False).stdout.strip() or '?'
        sale = subprocess.run(['git', 'status', '--porcelain'],
                              cwd=RACINE, capture_output=True, text=True,
                              timeout=30, check=False).stdout
        modifie = any(not ligne.startswith('??')
                      for ligne in sale.splitlines() if ligne.strip())
        return f'{tete}+modifie' if modifie else tete
    except Exception:                                              # noqa: BLE001
        return '?'


def produire_la_chaine() -> dict:
    """Les resultats des huit sources : A1..A6 et les deux rapports."""
    import numpy as np

    from core.plan_tarifaire import PlanTarifaire
    from core.qualite_donnees import preambule_qualite
    from direction_non_vie.tarification import test_plan_invariants as T
    from direction_non_vie.tarification.a1_ingestion.agent import (
        AgentA1Ingestion,
    )
    from direction_non_vie.tarification.a2_preprocessing.agent import (
        AgentA2Preprocessing,
    )
    from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
    from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
    from direction_non_vie.tarification.a6_comparaison.agent import (
        AgentA6Comparaison,
    )
    from direction_non_vie.tarification.services import (
        rapport_equipe_tarif as RE,
    )
    from direction_non_vie.tarification.services import (
        rapport_modeles_tarif as RM,
    )

    plan = PlanTarifaire.depuis_yaml(os.path.join(RACINE, 'plans', 'auto.yaml'))
    np.random.seed(GRAINE)
    donnees = T.portefeuille_auto(TAILLE, GRAINE)
    # ⚠️ Sans colonne temporelle, A6 ne fait aucun walk-forward et son
    # chapitre de backtesting se vide : l'assiette serait plus etroite que
    # celle d'un vrai dossier.
    donnees['annee_souscription'] = np.random.default_rng(GRAINE).choice(
        list(ANNEES), len(donnees))
    base = {'audit_path': '/tmp', 'verbose': False}

    r1 = AgentA1Ingestion(**base).run(branche='non_vie', sous_branche='auto',
                                      dataframe=donnees, plan=plan)
    qualite = preambule_qualite(r1.get('dataframe'), plan,
                                qualite_validee_par='Gel', horodatage=None)
    r2 = AgentA2Preprocessing(**base).run(
        result_a1={**r1, 'dataframe': qualite.dataframe_propre}, plan=plan)
    r3 = AgentA3GLM(models_path='/tmp', audit_path='/tmp').run(
        result_a2=r2, plan=plan, col_frequence=plan.cible_frequence,
        col_cout=plan.cible_cout, generer_graphiques=True)
    r4 = AgentA4ML(models_path='/tmp', audit_path='/tmp').run(
        result_a2=r2, result_a3=r3, plan=plan, col_cible='nb_sinistres',
        ponderer_par_exposition=True, calcul_shap=False,
        generer_graphiques=True)
    r5: dict = {}
    try:
        from direction_non_vie.tarification.a5_deep_learning.agent import (
            AgentA5DeepLearning,
        )
        r5 = AgentA5DeepLearning(models_path='/tmp', audit_path='/tmp').run(
            result_a2=r2, result_a3=r3, plan=plan, col_cible='nb_sinistres',
            generer_graphiques=True)
    except ImportError as erreur:
        print(f'  ⚠ A5 hors assiette : torch absent ({erreur})', flush=True)
    r6 = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp').run(
        result_a2=r2, result_a3=r3, result_a4=r4,
        result_a5=r5 if r5.get('success') else None,
        col_cible='nb_sinistres', plan=plan, environnement='production',
        profil_valide_par='Gel', generer_graphiques=True,
        generer_rapport_equipe=False)
    return {
        'a1': r1, 'a2': r2, 'a3': r3, 'a4': r4, 'a5': r5, 'a6': r6,
        'rapport_modeles': RM.generer_rapport_tarification(
            result_a3=r3, result_a4=r4, result_a6=r6,
            result_a5=r5 if r5.get('success') else None,
            ref_client='GEL', arrete=ARRETE, audit_id='GEL',
            formats=['html', 'word']),
        'rapport_equipe': RE.generer_rapport_equipe_tarification(
            {'a1': r1, 'a2': r2, 'a3': r3, 'a4': r4, 'a5': r5, 'a6': r6},
            branche='non_vie', arrete=ARRETE, audit_id='GEL',
            formats=['html', 'word', 'excel']),
    }


def deposer(chemin: str) -> int:
    from direction_non_vie.tarification.services import gel_livrables as G

    depart = time.time()
    resultats = produire_la_chaine()
    empreinte = G.empreinte(G.livrables_de_la_chaine(resultats))
    reelles = sorted(nom for nom, contenu in empreinte.contenus.items()
                     if contenu != G.ABSENT)
    charge = {
        'jeu': {'graine': GRAINE, 'taille': TAILLE, 'arrete': ARRETE,
                'annees': list(ANNEES)},
        'tete_git': _tete_git(),
        'contenus': empreinte.contenus,
        'non_lues': empreinte.non_lues,
    }
    with open(chemin, 'w', encoding='utf-8') as fichier:
        json.dump(charge, fichier, ensure_ascii=False, default=str)
    print(f'  empreinte deposee : {chemin}', flush=True)
    print(f'  tete git          : {charge["tete_git"]}', flush=True)
    print(f'  surfaces reelles  : {len(reelles)} -- {", ".join(reelles)}',
          flush=True)
    print(f'  non lues          : {empreinte.non_lues or "aucune"}', flush=True)
    print(f'  duree             : {time.time() - depart:.0f} s', flush=True)
    return 0 if not empreinte.non_lues else 1


def comparer(avant: str, apres: str) -> int:
    from direction_non_vie.tarification.services import gel_livrables as G

    with open(avant, encoding='utf-8') as fichier:
        charge_av = json.load(fichier)
    with open(apres, encoding='utf-8') as fichier:
        charge_ap = json.load(fichier)
    if charge_av.get('jeu') != charge_ap.get('jeu'):
        print('  ⛔ JEUX D ENTREE DIFFERENTS -- comparaison REFUSEE.',
              flush=True)
        print(f'      avant : {charge_av.get("jeu")}', flush=True)
        print(f'      apres : {charge_ap.get("jeu")}', flush=True)
        print('  Un ecart lu entre deux assiettes differentes mesurerait le '
              'jeu de donnees, pas le correctif.', flush=True)
        return 2
    emp_av = G.Empreinte(contenus=charge_av['contenus'],
                         non_lues=charge_av['non_lues'])
    emp_ap = G.Empreinte(contenus=charge_ap['contenus'],
                         non_lues=charge_ap['non_lues'])
    ecarts = G.comparer(emp_av, emp_ap)
    print(f'  avant : {charge_av.get("tete_git")}   '
          f'apres : {charge_ap.get("tete_git")}', flush=True)
    print(G.rapport_ecarts(ecarts, emp_av, emp_ap), flush=True)
    return 0 if not ecarts else 1


def main() -> int:
    analyseur = argparse.ArgumentParser(
        description="Le gel des livrables, en avant/apres.")
    analyseur.add_argument('--sortie', metavar='FICHIER',
                           help='depose l empreinte de l arbre courant '
                                '(a placer HORS du depot)')
    analyseur.add_argument('--comparer', nargs=2, metavar=('AVANT', 'APRES'),
                           help='compare deux empreintes deposees')
    arguments = analyseur.parse_args()
    if bool(arguments.sortie) == bool(arguments.comparer):
        analyseur.error('choisir --sortie OU --comparer')
    warnings.filterwarnings('ignore')
    logging.disable(logging.CRITICAL)
    if arguments.sortie:
        return deposer(arguments.sortie)
    return comparer(*arguments.comparer)


if __name__ == '__main__':
    sys.exit(main())
