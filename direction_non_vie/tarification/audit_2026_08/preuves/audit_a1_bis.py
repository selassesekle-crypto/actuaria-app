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
"""RELEVE A1 (suite) -- deux verifications que la premiere passe a laissees ouvertes.

M2ter : le selecteur de colonne-identifiant ('id' ou 'pol' en sous-chaine)
        attrape-t-il une colonne NON-identifiante du vocabulaire REEL du depot ?
        (ma premiere tentative inventait `densite_population`, qui ne contient
        pas 'pol' -- p-o-p-u-l. Suspicion REFUTEE, on remesure sur le vrai
        vocabulaire des 20 plans + les colonnes standard d'A1.)

M8bis  : quand le dossier d'audit est inecrivable, le fichier d'audit est-il
         REELLEMENT absent ? (sans quoi il n'y a rien de perdu, et le
         << silence >> ne serait qu'une supposition de ma part.)
"""
import pathlib
import shutil
import sys
import tempfile

RACINE = pathlib.Path(r'C:\Users\selse\actuaria-app')
sys.path.insert(0, str(RACINE))

import pandas as pd
import yaml


def m2ter():
    from direction_non_vie.tarification.a1_ingestion import agent as A
    vocab = set()
    for y in sorted((RACINE / 'plans').glob('*.yaml')):
        d = yaml.safe_load(y.read_text(encoding='utf-8')) or {}
        for f in (d.get('facteurs') or []):
            if isinstance(f, dict) and f.get('nom'):
                vocab.add(str(f['nom']))
        for k in ('cible_frequence', 'cible_cout', 'exposition',
                  'colonne_exposition', 'identifiant'):
            if d.get(k):
                vocab.add(str(d[k]))
    for cible, syns in A.SYNONYMES_COLONNES.items():
        vocab.add(cible)
        vocab.update(syns)
    attrapees = sorted(c for c in vocab
                       if ('id' in c.lower() or 'pol' in c.lower()))
    # Une colonne est un IDENTIFIANT legitime si son nom commence par id_/num_
    # ou finit par _id : tout le reste serait un faux positif.
    def est_id(c):
        b = c.lower()
        return (b.startswith(('id_', 'num_', 'idpol', 'policy'))
                or b.endswith(('_id', '_pol'))
                or b in ('id_contrat', 'id_sinistre', 'id_vehicule', 'idpol'))
    faux = [c for c in attrapees if not est_id(c)]
    print(f'  vocabulaire mesure : {len(vocab)} noms de colonnes '
          f'({len(list((RACINE / "plans").glob("*.yaml")))} plans + SYNONYMES)')
    print(f'  attrapees par le selecteur : {len(attrapees)}')
    print(f'  FAUX POSITIFS (non-identifiants) : {len(faux)}')
    for c in faux:
        print(f'      - {c}')
    if not faux:
        print('  => selecteur SAIN sur le vocabulaire reel du depot.')
    return faux


def m8bis():
    from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
    # (a) cas NORMAL : le fichier d'audit est-il ecrit ?
    ok_dir = pathlib.Path(tempfile.mkdtemp(prefix='a1_ok_'))
    ag = AgentA1Ingestion(audit_path=str(ok_dir), verbose=False)
    n = 60
    df = pd.DataFrame({'id_contrat': range(n), 'age': [40] * n,
                       'exposition': [0.8] * n, 'nb_sinistres': [0] * n})
    r_ok = ag.run(branche='non_vie', sous_branche='auto', dataframe=df)
    ecrits = sorted(p.name for p in ok_dir.glob('*.json'))
    print(f'\n  (a) dossier ECRIVABLE  : success={r_ok["success"]} '
          f'fichiers audit = {ecrits}')

    # (b) cas DEGRADE : dossier remplace par un fichier
    ko_dir = pathlib.Path(tempfile.mkdtemp(prefix='a1_ko_'))
    ag2 = AgentA1Ingestion(audit_path=str(ko_dir), verbose=False)
    shutil.rmtree(ko_dir, ignore_errors=True)
    ko_dir.write_text('pas un dossier', encoding='utf-8')
    r_ko = ag2.run(branche='non_vie', sous_branche='auto', dataframe=df)
    existe = ko_dir.is_file()
    print(f'  (b) dossier INECRIVABLE: success={r_ko["success"]} '
          f'erreur={r_ko.get("erreur")} '
          f'alertes={r_ko.get("rapport", {}).get("alertes", [])}')
    print(f'      -> aucun fichier d audit ecrit (la cible est un fichier : {existe})')
    print(f'      -> audit_trail present dans le resultat : '
          f'{bool(r_ko.get("audit_trail"))}')
    ko_dir.unlink(missing_ok=True)
    shutil.rmtree(ok_dir, ignore_errors=True)
    return r_ok, r_ko


if __name__ == '__main__':
    print('  M2ter -- le selecteur de colonne-identifiant\n')
    m2ter()
    print('\n  M8bis -- l audit trail quand l ecriture echoue')
    m8bis()
