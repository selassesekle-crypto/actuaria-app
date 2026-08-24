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
"""RELEVE A2 -- chaque constat porte sa mesure, ou n'est pas rendu.

⚠️ POSTURE : A2 a ete refondu avec soin (Phase 2 : encodage pilote par le plan,
troisieme implementation supprimee). On part de l'hypothese qu'il est bon.
Chaque bloc essaie de FAIRE TOMBER une affirmation ; s'il n'y arrive pas,
l'affirmation est classee VERIFIEE BONNE.
"""
import pathlib
import re
import sys
import tempfile

RACINE = pathlib.Path(r'C:\Users\selse\actuaria-app')
sys.path.insert(0, str(RACINE))

import numpy as np
import pandas as pd
import yaml

from core.plan_tarifaire import PlanTarifaire

PLAN = PlanTarifaire.depuis_yaml(str(RACINE / 'plans' / 'auto.yaml'))
SRC = (RACINE / 'direction_non_vie/tarification/a2_preprocessing/agent.py'
       ).read_text(encoding='utf-8')
RES = []


def dire(cle, verdict, detail):
    RES.append((cle, verdict, detail))
    print(f'  [{verdict:9}] {cle:38} {detail}')


def _r_a1(n=600, **extra):
    rng = np.random.default_rng(7)
    df = pd.DataFrame({
        'id_contrat':           range(n),
        'nb_sinistres':         rng.poisson(0.08, n),
        'cout_total_sinistres': rng.exponential(800, n),
        'exposition':           rng.uniform(0.1, 1.0, n),
        'age':                  rng.integers(18, 75, n),
        'bonus_malus':          rng.uniform(50, 350, n),
        'puissance_fiscale':    rng.integers(4, 15, n),
        'zone_geographique':    rng.choice(['A', 'B', 'C'], n),
        'carburant':            rng.choice(['Essence', 'Diesel'], n),
        'age_vehicule':         rng.integers(0, 20, n),
        'valeur_venale':        rng.uniform(2000, 40000, n),
        'kilometrage_annuel':   rng.uniform(3000, 40000, n),
        'csp':                  rng.choice(['Cadre', 'Employe', 'Retraite'], n),
        'usage':                rng.choice(['Prive', 'Pro'], n),
        'milieu_geographique':  rng.choice(['Urbain', 'Periurbain', 'Rural'], n),
        'antecedents_sinistres_n1': rng.integers(0, 3, n),
        'garantie':             rng.choice(['Tiers', 'TousRisques'], n),
    })
    for k, v in extra.items():
        df[k] = v
    return {'success': True, 'dataframe': df, 'branche': 'auto',
            'statut_rag': 'VERT', 'erreur': None}


def agent(**kw):
    from direction_non_vie.tarification.a2_preprocessing.agent import (
        AgentA2Preprocessing,
    )
    d = tempfile.mkdtemp(prefix='a2_')
    return AgentA2Preprocessing(models_path=d, audit_path=d, verbose=False, **kw)


# =====================================================================
# N1 -- le nombre de variables winsorisees PUBLIE a l'actuaire
# =====================================================================
def n1():
    ag = agent()
    r = ag.run(result_a1=_r_a1(), plan=PLAN)
    reel = len(r['rapport']['transformations']['winsorisation'])
    m = re.search(r'Winsoris\w+\s*:\s*(\d+)\s*variable', r['commentaire'])
    publie = int(m.group(1)) if m else None
    m2 = re.search(r'Winsorisation sur (\d+) variable', r['commentaire'])
    publie2 = int(m2.group(1)) if m2 else None
    faux = (publie is not None and publie != reel)
    dire('N1 nb winsorisees publie', 'CONSTAT' if faux else 'BON',
         f'REEL={reel} · publie niveau 1 = {publie} · publie diagnostic = {publie2}')


# =====================================================================
# N2 -- les methodes d'encodage ANNONCEES par l'en-tete
# =====================================================================
# En-tete l. 19-20 : << Weight of Evidence (WoE) . Target Encoding . One-Hot >>
def n2():
    import inspect

    from direction_non_vie.tarification.a2_preprocessing.agent import (
        AgentA2Preprocessing,
    )
    corps = inspect.getsource(AgentA2Preprocessing._appliquer_facteur)
    supportes = sorted(set(re.findall(r'f\.encodage == "(\w+)"', corps)))
    annonces = []
    for mot, cle in (('Weight of Evidence', 'WoE'), ('Target Encoding', 'target'),
                     ('One-Hot', 'one_hot')):
        if mot.lower() in SRC[:3000].lower():
            annonces.append(cle)
    # Et ce que le PLAN accepte comme valeur d'encodage
    valeurs_plan = set()
    for y in sorted((RACINE / 'plans').glob('*.yaml')):
        d = yaml.safe_load(y.read_text(encoding='utf-8')) or {}
        for f in (d.get('facteurs') or []):
            if isinstance(f, dict) and f.get('encodage'):
                valeurs_plan.add(f['encodage'])
    manquants = [a for a in annonces if a not in ('one_hot',)]
    dire('N2 encodages annonces vs codes',
         'CONSTAT' if manquants else 'BON',
         f'en-tete annonce {annonces} · code supporte {supportes} · '
         f'20 plans utilisent {sorted(valeurs_plan)}')


# =====================================================================
# N3 -- << Winsorisation (methode IQR) >> (en-tete l. 17)
# =====================================================================
def n3():
    from direction_non_vie.tarification.a2_preprocessing.agent import (
        AgentA2Preprocessing,
    )
    q = AgentA2Preprocessing._WINSOR_Q
    dit_iqr = 'IQR' in SRC[:3000]
    # Une winsorisation IQR utiliserait Q1-1.5*IQR / Q3+1.5*IQR, pas des quantiles
    utilise_iqr = bool(re.search(r'1\.5\s*\*|iqr|q3\s*-\s*q1', SRC, re.IGNORECASE))
    dire('N3 methode de winsorisation', 'CONSTAT' if (dit_iqr and not utilise_iqr) else 'BON',
         f'en-tete dit IQR={dit_iqr} · code = quantiles {q} · trace de calcul IQR={utilise_iqr}')


# =====================================================================
# N4 -- STRATEGIES_IMPUTATION est-il LU par le code ?
# =====================================================================
def n4():
    lectures = [i for i, l in enumerate(SRC.splitlines(), 1)
                if 'STRATEGIES_IMPUTATION' in l]
    definition = [i for i in lectures if 'STRATEGIES_IMPUTATION = {' in SRC.splitlines()[i - 1]]
    dire('N4 STRATEGIES_IMPUTATION lu ?',
         'CONSTAT' if len(lectures) == len(definition) else 'BON',
         f'{len(lectures)} mention(s) l.{lectures}, dont la definition — aucune lecture'
         if len(lectures) == len(definition) else f'lu en l.{lectures}')


# =====================================================================
# N5 -- la strategie 'binaire' -> 'mode' est-elle appliquee ?
# =====================================================================
def n5():
    ag = agent()
    n = 400
    r1 = _r_a1(n)
    # colonne BINAIRE 0/1 avec des trous ; mode = 1 (majoritaire), moyenne ~0.75
    col = np.array([1.0] * 300 + [0.0] * 80 + [np.nan] * 20)
    r1['dataframe']['alarme'] = col
    r1['dataframe'] = r1['dataframe'].iloc[:n]
    r = ag.run(result_a1=r1, plan=PLAN)
    imput = r['rapport']['transformations']['imputation']['colonnes_imputees'].get('alarme', {})
    meth, val = imput.get('methode'), imput.get('valeur')
    dire('N5 imputation d une binaire 0/1',
         'CONSTAT' if meth != 'mode' else 'BON',
         f"methode={meth!r} valeur={val} (mode attendu par STRATEGIES_IMPUTATION = 1.0)")


# =====================================================================
# N6 -- une MOYENNE rangee sous la cle 'medianes'
# =====================================================================
def n6():
    ag = agent()
    n = 400
    r1 = _r_a1(n)
    a = r1['dataframe']['age'].astype(float).values.copy()
    a[:30] = np.nan
    r1['dataframe']['age'] = a
    r = ag.run(result_a1=r1, plan=PLAN)
    imput = r['rapport']['transformations']['imputation']['colonnes_imputees']['age']
    stocke = r['parametres']['medianes'].get('age')
    dire('N6 moyenne stockee sous "medianes"',
         'CONSTAT' if imput['methode'] == 'moyenne' and stocke is not None else 'BON',
         f"methode={imput['methode']!r} · parametres['medianes']['age']={stocke:.4f} "
         f"(mediane reelle={np.nanmedian(a):.4f})")


# =====================================================================
# N7 -- << exposition = 0 -> contrat de duree nulle -> a exclure >>
# =====================================================================
def n7():
    ag = agent()
    n = 400
    r1 = _r_a1(n)
    e = r1['dataframe']['exposition'].values.copy()
    e[:40] = 0.0
    r1['dataframe']['exposition'] = e
    avant = len(r1['dataframe'])
    r = ag.run(result_a1=r1, plan=PLAN)
    st = r['rapport']['transformations']['exposition']
    dire('N7 exposition = 0 : exclue ou imputee ?',
         'CONSTAT' if st['lignes_exclues'] == 0 and len(r['dataframe']) == avant else 'BON',
         f"lignes {avant} -> {len(r['dataframe'])} · lignes_exclues={st['lignes_exclues']} "
         f"· valeurs_corrigees={st['valeurs_corrigees']}")


# =====================================================================
# N8 -- << Supprime egalement les colonnes non utilisables >>
# =====================================================================
def n8():
    ag = agent()
    r = ag.run(result_a1=_r_a1(), plan=PLAN)
    val = r['rapport']['transformations']['validation']
    encore = 'id_contrat' in r['dataframe'].columns
    dire('N8 colonnes "supprimees" par validation',
         'CONSTAT' if encore and not val.get('colonnes_supprimees') else 'BON',
         f"colonnes_supprimees={val.get('colonnes_supprimees', 'ABSENT')} · "
         f"id_contrat encore present = {encore}")


# =====================================================================
# N9 -- les exemples d'usage du module fonctionnent-ils ?
# =====================================================================
def n9():
    from direction_non_vie.tarification.a2_preprocessing.agent import (
        AgentA2Preprocessing,
    )
    ag = AgentA2Preprocessing(models_path=tempfile.mkdtemp(),
                              audit_path=tempfile.mkdtemp(), verbose=False)
    r = ag.run(_r_a1())          # exactement l'exemple de l'en-tete l. 45 et l. 328
    sans_plan = SRC.count('agent_a2.run(result_a1)')
    dire('N9 exemple "run(result_a1)" de l en-tete',
         'CONSTAT' if not r['success'] else 'BON',
         f"success={r['success']} · l exemple figure {sans_plan} fois dans le module")


# =====================================================================
# N10 -- la recommandation AMBRE renvoie a un mecanisme supprime
# =====================================================================
def n10():
    presente = 'configuration d\'encodage étendue' in SRC
    existe = bool(re.search(r'VARS_CATEGORIELLES\s*=', SRC))
    dire('N10 conseil AMBRE "config d encodage"',
         'CONSTAT' if presente and not existe else 'BON',
         f'conseil present={presente} · VARS_CATEGORIELLES existe encore={existe}')


# =====================================================================
# N11 -- << les trois entrees ci-dessous >> (commentaire l. 130-135)
# =====================================================================
def n11():
    seuils = bool(re.search(r'^SEUILS_WINSOR\s*=', SRC, re.MULTILINE))
    renvoi = 'les\ntrois entrées ci-dessous' in SRC or 'trois entrées ci-dessous' in SRC
    dire('N11 commentaire "trois entrees ci-dessous"',
         'CONSTAT' if renvoi and not seuils else 'BON',
         f'renvoi present={renvoi} · SEUILS_WINSOR existe={seuils}')


# =====================================================================
# N12 -- `mots_asymetriques` : faux positifs sur le vocabulaire REEL
# =====================================================================
def n12():
    mots = ['cout', 'prime', 'capital', 'valeur', 'montant', 'encours',
            'charge', 'ij', 'rente', 'ca_annuel', 'provision', 'engagement']
    vocab = set()
    for y in sorted((RACINE / 'plans').glob('*.yaml')):
        d = yaml.safe_load(y.read_text(encoding='utf-8')) or {}
        for f in (d.get('facteurs') or []):
            if isinstance(f, dict) and f.get('nom'):
                vocab.add(str(f['nom']))
    attrapes = sorted(c for c in vocab if any(m in c.lower() for m in mots))
    # Un nom ATTRAPE est-il vraiment une grandeur asymetrique (cout/prime/valeur) ?
    douteux = [c for c in attrapes
               if not any(m in c.lower() for m in
                          ('cout', 'prime', 'capital', 'valeur', 'montant',
                           'charge', 'ca_annuel', 'encours', 'provision', 'engagement'))]
    dire('N12 mots_asymetriques faux positifs',
         'CONSTAT' if douteux else 'BON',
         f'{len(attrapes)} noms attrapes sur {len(vocab)} · douteux={douteux}')


# =====================================================================
# N13 -- DATA_DICTIONNAIRE documente-t-il des colonnes jamais produites ?
# =====================================================================
def n13():
    from direction_non_vie.tarification.a2_preprocessing.agent import DATA_DICTIONNAIRE
    ag = agent()
    r = ag.run(result_a1=_r_a1(), plan=PLAN)
    cols = set(r['dataframe'].columns)
    # colonnes produites par TOUS les plans du depot
    toutes = set()
    for y in sorted((RACINE / 'plans').glob('*.yaml')):
        try:
            toutes |= set(PlanTarifaire.depuis_yaml(str(y)).colonnes_produites())
        except Exception:
            pass
    derivees = {'risque_historique', 'km_par_an_normalise', 'jeune_conducteur',
                'senior_conducteur', 'vehicule_recent', 'vehicule_ancien',
                'valeur_par_m2', 'age_logement', 'logement_ancien',
                'log_exposition', 'prime_pure'}
    jamais = [k for k in DATA_DICTIONNAIRE
              if k not in cols and k not in toutes and k not in derivees]
    dire('N13 DATA_DICTIONNAIRE : documente non produit',
         'CONSTAT' if jamais else 'BON',
         f'{len(DATA_DICTIONNAIRE)} entrees · jamais produites nulle part = {jamais}')


# =====================================================================
# N14 -- l'en-tete du fichier de TEST
# =====================================================================
def n14():
    t = (RACINE / 'direction_non_vie/tarification/a2_preprocessing'
         / 'test_a2_preprocessing.py').read_text(encoding='utf-8')
    ann = re.search(r'(\d+)\s+tests', t)
    reels = len(re.findall(r'^\s+def (test_\w+)', t, re.MULTILINE))
    dire('N14 en-tete de test << N tests >>',
         'CONSTAT' if ann and int(ann.group(1)) != reels else 'BON',
         f'annonce {ann.group(1) if ann else "?"} · methodes reelles = {reels}')


# =====================================================================
# N15 -- VERIFICATIONS POSITIVES (ce qui doit marcher)
# =====================================================================
def n15():
    from direction_non_vie.tarification.a2_preprocessing.agent import (
        AgentA2Preprocessing,
    )
    ag = agent()
    # (a) plan absent -> erreur propre, jamais de repli
    r = ag.run(result_a1=_r_a1(), plan=None)
    a = (not r['success']) and 'plan' in (r.get('erreur') or '').lower()
    # (b) piege V9 : modalite INCONNUE -> leve
    r1 = _r_a1(200)
    r1['dataframe'].loc[0, 'carburant'] = 'GPL_INCONNU'
    r2 = ag.run(result_a1=r1, plan=PLAN)
    b = (not r2['success']) and 'INCONNUE' in (r2.get('erreur') or '').upper()
    # (c) INV-1 : transform produit EXACTEMENT colonnes_produites()
    ag2 = AgentA2Preprocessing(models_path=tempfile.mkdtemp(),
                               audit_path=tempfile.mkdtemp(), verbose=False)
    d = _r_a1(300)['dataframe']
    out = ag2.fit(d, PLAN).transform(d)
    c = set(PLAN.colonnes_produites()) <= set(out.columns)
    # (d) ordre des codes label = ordre du PLAN, jamais alphabetique
    f_lab = next((f for f in PLAN.facteurs
                  if getattr(f, 'encodage', None) == 'label' and f.modalites), None)
    dd = True
    if f_lab:
        codes = ag2._codes_label[f_lab.nom]
        dd = list(codes) == [str(m) for m in f_lab.modalites]
    # (e) aucune colonne de genre produite
    e = not any('sexe' in c.lower() or c.lower().startswith('genre')
                for c in out.columns)
    for cle, ok, det in (('N15a plan absent -> erreur propre', a, r.get('erreur', '')[:44]),
                         ('N15b modalite inconnue -> leve', b, (r2.get('erreur') or '')[:44]),
                         ('N15c INV-1 colonnes_produites', c, f'{len(PLAN.colonnes_produites())} colonnes'),
                         ('N15d ordre label = ordre du plan', dd,
                          f'{f_lab.nom if f_lab else "aucun facteur label"}'),
                         ('N15e aucune colonne de genre', e, f'{len(out.columns)} colonnes en sortie')):
        dire(cle, 'BON' if ok else 'CONSTAT', det)


def main() -> int:
    print('  RELEVE A2 -- chaque ligne est une mesure\n')
    for f in (n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, n11, n12, n13, n14, n15):
        try:
            f()
        except Exception as e:
            dire(f.__name__.upper(), 'NON MESURE', f'{type(e).__name__}: {e}')
    print('\n  ' + '=' * 76)
    for v in ('CONSTAT', 'BON', 'NON MESURE'):
        print(f'  {v:11} : {sum(1 for _, x, _ in RES if x == v)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
