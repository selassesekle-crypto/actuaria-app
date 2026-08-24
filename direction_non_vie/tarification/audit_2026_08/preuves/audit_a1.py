# ruff: noqa
# ⚠️ SCRIPT D'ARCHIVE — PREUVE D'AUDIT, PAS DU CODE MAINTENU.
# Il a ete ecrit un jour donne pour ETABLIR UN FAIT, et il est conserve
# tel qu'il a ete execute. Le relire aux regles du code de production
# reviendrait a reecrire une piece a conviction : les 25 ecarts qu'il
# porte (10 F841, 8 BLE001, 3 PLW1510, 2 UP031, 1 S110, 1 RUF015) sont
# DECLARES ici plutot que corriges. Les BLE001 sont d'ailleurs voulus :
# un script qui mesure si quelque chose casse doit tout attraper.
# ⚠️ DETERMINISME VERIFIE : sur deux executions successives, 7 des 8
# scripts rendent des mesures IDENTIQUES. Le huitieme, audit_services,
# ne varie que sur l'horodatage QU'IL MESURE -- et c'est precisement son
# constat U1 : << Arrete : publie l'horodatage de generation >>.
"""RELEVE A1 -- chaque constat porte sa mesure, ou n'est pas rendu.

⚠️ POSTURE : on part de l'hypothese que A1 est bon. Chaque bloc ci-dessous
essaie de FAIRE TOMBER une affirmation du module ; s'il n'y arrive pas,
l'affirmation est classee VERIFIEE BONNE et dite comme telle.
"""
import os
import pathlib
import shutil
import sys
import tempfile
import warnings

RACINE = pathlib.Path(r'C:\Users\selse\actuaria-app')
sys.path.insert(0, str(RACINE))

import pandas as pd

RES = []


def dire(cle, verdict, detail):
    RES.append((cle, verdict, detail))
    print(f'  [{verdict:9}] {cle:34} {detail}')


# =========================================================================
# M1 -- Le garde-fou de perimetre empeche-t-il d'ingerer un fichier VIE ?
# =========================================================================
# AFFIRMATION MESUREE (agent.py l. 161-162) : << Empeche qu'un portefeuille
# Vie ou Sante soit ingere par erreur dans le pipeline de tarification
# Non-Vie. >>
def m1():
    warnings.filterwarnings('default')
    from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
    base = pathlib.Path(tempfile.mkdtemp(prefix='a1_m1_'))
    (base / 'vie').mkdir(parents=True)
    df = pd.DataFrame({'id_contrat': range(20), 'age': [40] * 20,
                       'exposition': [1.0] * 20, 'nb_sinistres': [0] * 20})
    df.to_csv(base / 'vie' / 'portefeuille_vie.csv', index=False)
    ag = AgentA1Ingestion(base_path=str(base), audit_path=str(base / 'audit'),
                          verbose=False)
    r = ag.run(branche='non_vie', sous_branche='auto',
               fichier='portefeuille_vie.csv')
    charge = bool(r.get('success')) and len(r.get('dataframe', [])) == 20
    dire('M1 fichier depuis data/vie/',
         'CONSTAT' if charge else 'BON',
         f"charge={charge} — le loader parcourt {['non_vie','vie','sante_prevoyance']}"
         if charge else 'le loader ne sort pas du perimetre')
    shutil.rmtree(base, ignore_errors=True)


# =========================================================================
# M2 -- La colonne servant au comptage des doublons
# =========================================================================
# CODE : cols_id = [c for c in df.columns if 'id' in c.lower() or 'pol' in c.lower()]
#        nb_doublons = df.duplicated(subset=[cols_id[0]]).sum()
# `densite_population` contient 'pol' ET est une colonne STANDARD declaree
# dans SYNONYMES_COLONNES.
def m2():
    from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
    ag = AgentA1Ingestion(audit_path=tempfile.mkdtemp(), verbose=False)
    n = 200
    # densite_population AVANT id_contrat, et volontairement peu de modalites
    df = pd.DataFrame({
        'densite_population': [10.0, 20.0] * (n // 2),   # 2 modalites -> 198 doublons
        'id_contrat':         range(n),                   # unique -> 0 doublon
        'exposition':         [1.0] * n,
        'age':                [40] * n,
    })
    q = ag._valider_qualite(df)
    cols_id = [c for c in df.columns if 'id' in c.lower() or 'pol' in c.lower()]
    faux = q['nb_doublons'] > 0
    dire('M2 colonne des doublons', 'CONSTAT' if faux else 'BON',
         f"retenue={cols_id[0]!r} -> nb_doublons={q['nb_doublons']} "
         f"(reel sur id_contrat = {int(df.duplicated(subset=['id_contrat']).sum())})")
    # Contre-mesure : l'ordre inverse donne-t-il le bon resultat ?
    df2 = df[['id_contrat', 'densite_population', 'exposition', 'age']]
    q2 = ag._valider_qualite(df2)
    dire('M2b meme donnee, ordre inverse', 'CONSTAT' if q2['nb_doublons'] != q['nb_doublons'] else 'BON',
         f"nb_doublons={q2['nb_doublons']} — le resultat depend de l'ORDRE des colonnes")


# =========================================================================
# M3 -- << Montants : prime_pure > 0 si disponible >> (docstring l. 719)
# =========================================================================
def m3():
    from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
    ag = AgentA1Ingestion(audit_path=tempfile.mkdtemp(), verbose=False)
    n = 100
    df = pd.DataFrame({'id_contrat': range(n), 'exposition': [1.0] * n,
                       'age': [40] * n, 'prime_pure': [0.0] * n})
    q = ag._valider_qualite(df)
    vu = any('prime_pure' in k for k in q['aberrants'])
    dire('M3 prime_pure = 0 (docstring dit > 0)', 'BON' if vu else 'CONSTAT',
         f"aberrants={list(q['aberrants']) or 'aucun'} — 100 lignes a prime_pure=0")


# =========================================================================
# M4 -- << Exposition dans [0, 1] >> : 0 est-il accepte ou refuse ?
# =========================================================================
def m4():
    from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
    ag = AgentA1Ingestion(audit_path=tempfile.mkdtemp(), verbose=False)
    n = 100
    df = pd.DataFrame({'id_contrat': range(n), 'age': [40] * n,
                       'exposition': [0.0] * n})
    q = ag._valider_qualite(df)
    dire('M4 exposition = 0', 'CONSTAT' if q['expo_ok_pct'] == 100.0 else 'BON',
         f"expo_ok_pct={q['expo_ok_pct']} (controle 3, `between` INCLUSIF) "
         f"mais aberrants={list(q['aberrants'])} (controle 4d) — deux verdicts")


# =========================================================================
# M5 -- Doublons dans SYNONYMES_COLONNES
# =========================================================================
def m5():
    from direction_non_vie.tarification.a1_ingestion import agent as A
    dup = {k: [s for s in set(v) if v.count(s) > 1]
           for k, v in A.SYNONYMES_COLONNES.items()
           if len(v) != len(set(v))}
    dire('M5 doublons dans SYNONYMES', 'CONSTAT' if dup else 'BON',
         f'{dup}' if dup else 'aucun doublon')


# =========================================================================
# M6 -- `warnings.filterwarnings('ignore')` au niveau MODULE
# =========================================================================
def m6():
    import subprocess
    code = (
        "import warnings, sys; sys.path.insert(0, r'%s');"
        "avant = len(warnings.filters);"
        "import direction_non_vie.tarification.a1_ingestion.agent;"
        "apres = warnings.filters[0] if warnings.filters else None;"
        "print(apres)" % RACINE
    )
    out = subprocess.run([sys.executable, '-c', code], capture_output=True,
                         text=True, cwd=str(RACINE),
                         env={**os.environ, 'PYTHONUTF8': '1'})
    prem = out.stdout.strip()
    global_ignore = prem.startswith("('ignore', None, <class 'Warning'>")
    dire('M6 filtre global de warnings', 'CONSTAT' if global_ignore else 'BON',
         f'1er filtre apres import = {prem[:58]}')


# =========================================================================
# M7 -- L'instanciation ECRIT-ELLE sur le disque ?
# =========================================================================
def m7():
    import subprocess
    code = (
        "import sys, pathlib; sys.path.insert(0, r'%s');"
        "from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion;"
        "p = pathlib.Path('/tmp/actuaria');"
        "import shutil; shutil.rmtree(p, ignore_errors=True);"
        "avant = p.exists(); AgentA1Ingestion(verbose=False);"
        "print(avant, p.exists(), sorted(x.name for x in p.iterdir()) if p.exists() else [])"
        % RACINE
    )
    out = subprocess.run([sys.executable, '-c', code], capture_output=True,
                         text=True, cwd=str(RACINE),
                         env={**os.environ, 'PYTHONUTF8': '1'})
    dire('M7 ecriture disque a l instanciation', 'CONSTAT' if 'True' in out.stdout else 'BON',
         f'avant/apres/contenu = {out.stdout.strip() or out.stderr.strip()[:60]}')


# =========================================================================
# M8 -- L'audit trail perdu en SILENCE si l'ecriture echoue
# =========================================================================
def m8():
    from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
    d = pathlib.Path(tempfile.mkdtemp(prefix='a1_m8_'))
    ag = AgentA1Ingestion(audit_path=str(d), verbose=False)
    # On rend le dossier d'audit INECRIVABLE en le remplacant par un fichier
    shutil.rmtree(d, ignore_errors=True)
    d.write_text('je ne suis pas un dossier', encoding='utf-8')
    n = 60
    df = pd.DataFrame({'id_contrat': range(n), 'age': [40] * n,
                       'exposition': [0.8] * n, 'nb_sinistres': [0] * n})
    r = ag.run(branche='non_vie', sous_branche='auto', dataframe=df)
    silencieux = bool(r.get('success')) and not r.get('erreur')
    dire('M8 audit non ecrit -> silence', 'CONSTAT' if silencieux else 'BON',
         f"success={r.get('success')} erreur={r.get('erreur')} "
         f"alertes={len(r.get('rapport', {}).get('alertes', []))}")
    d.unlink(missing_ok=True)


# =========================================================================
# M9 -- `verifier_tous_fichiers` annonce des fichiers Vie/Sante
# =========================================================================
def m9():
    import subprocess
    out = subprocess.run(
        ['git', 'grep', '-n', 'verifier_tous_fichiers'],
        capture_output=True, text=True, cwd=str(RACINE))
    lignes = [x for x in out.stdout.splitlines() if x.strip()]
    hors_def = [x for x in lignes if 'def verifier_tous_fichiers' not in x]
    dire('M9 verifier_tous_fichiers appele ?', 'CONSTAT' if not hors_def else 'BON',
         f'{len(lignes)} mention(s), {len(hors_def)} hors definition')


# =========================================================================
# M10 -- Le compte annonce par l'entete du fichier de test
# =========================================================================
def m10():
    import re
    t = (RACINE / 'direction_non_vie/tarification/a1_ingestion'
         / 'test_a1_ingestion.py').read_text(encoding='utf-8')
    annonce = re.search(r'(\d+)\s+tests', t)
    reels = len(re.findall(r'^\s+def (test_\w+)', t, re.MULTILINE))
    dire('M10 entete de test << N tests >>',
         'CONSTAT' if annonce and int(annonce.group(1)) != reels else 'BON',
         f'entete annonce {annonce.group(1) if annonce else "?"}, '
         f'methodes de test reelles = {reels}')


# =========================================================================
# M11 -- VERIFICATION POSITIVE : la penalite aberrants vaut-elle bien -3 pts ?
# =========================================================================
# Le commentaire l. 173 affirme << jusqu'a -3 pts >>. On le MESURE.
def m11():
    from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
    ag = AgentA1Ingestion(audit_path=tempfile.mkdtemp(), verbose=False)
    n = 100
    propre = pd.DataFrame({'id_contrat': range(n), 'age': [40] * n,
                           'exposition': [0.8] * n, 'nb_sinistres': [0] * n,
                           'cout_total_sinistres': [0.0] * n,
                           'prime_pure': [100.0] * n})
    sale = propre.copy()
    sale.loc[0, 'nb_sinistres'] = -1        # type 1
    sale.loc[1, 'cout_total_sinistres'] = -5.0  # type 2
    sale.loc[2, 'age'] = 5                  # type 3
    sale.loc[3, 'exposition'] = 0.0         # type 4
    sale.loc[4, 'prime_pure'] = -1.0        # type 5
    qp, qs = ag._valider_qualite(propre), ag._valider_qualite(sale)
    ecart = qp['score_global'] - qs['score_global']
    conforme = abs(ecart - 3.0) < 0.35      # 20 pts * 0.15 = 3.00
    dire('M11 penalite aberrants (annonce -3 pts)', 'BON' if conforme else 'CONSTAT',
         f"{qs['nb_types_aberrants']} types -> ecart de score = {ecart:.2f} pts")


# =========================================================================
# M12 -- VERIFICATION POSITIVE : le plafond RAG sur aberrants mord-il ?
# =========================================================================
def m12():
    from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
    ag = AgentA1Ingestion(audit_path=tempfile.mkdtemp(), verbose=False)
    n = 100
    df = pd.DataFrame({'id_contrat': range(n), 'age': [40] * n,
                       'exposition': [0.8] * n, 'nb_sinistres': [0] * n})
    vert = ag._calculer_statut_rag(ag._valider_qualite(df))
    df1 = df.copy(); df1.loc[0, 'age'] = 5              # 1 ligne = 1 %
    ambre = ag._calculer_statut_rag(ag._valider_qualite(df1))
    df2 = df.copy(); df2.loc[0:9, 'age'] = 5            # 10 lignes = 10 % > 5 %
    rouge = ag._calculer_statut_rag(ag._valider_qualite(df2))
    ok = (vert, ambre, rouge) == ('VERT', 'AMBRE', 'ROUGE')
    dire('M12 plafond RAG sur aberrants', 'BON' if ok else 'CONSTAT',
         f'propre={vert} · 1 aberrant={ambre} · 10 % aberrants={rouge}')


def main() -> int:
    print('  RELEVE A1 -- chaque ligne est une mesure\n')
    for f in (m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12):
        try:
            f()
        except Exception as e:
            dire(f.__name__.upper(), 'NON MESURE', f'{type(e).__name__}: {e}')
    print('\n  ' + '=' * 74)
    for v in ('CONSTAT', 'BON', 'NON MESURE'):
        n = sum(1 for _, x, _ in RES if x == v)
        print(f'  {v:11} : {n}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
