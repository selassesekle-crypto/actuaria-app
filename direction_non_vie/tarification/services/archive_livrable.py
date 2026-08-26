# -*- coding: utf-8 -*-
"""
ActuarIA — Tarification · ARCHIVE VÉRIFIABLE DU LIVRABLE (sur le modèle A7)
==========================================================================

Le pendant, pour la tarification, de `verifier_archive` du provisionnement
(a7…/agent.py). Il conserve le dossier signé ET prouve, plus tard, qu'aucun
fichier n'a été altéré depuis l'écriture.

⚠️ MIROIR, PAS PARTAGE. Le code d'A7 vit dans le provisionnement ; l'importer
d'ici créerait une dépendance tarification → provisionnement (autre zone). On
DUPLIQUE volontairement : une dépendance inter-zones serait pire. L'extraction
vers un socle commun est une consolidation future, hors de ce lot.

⚠️ L'EMPREINTE EST LE CŒUR, PAS L'ÉCRITURE (leçon A7). Un fichier écrit sans
empreinte ne prouve rien — rien n'interdit de le remplacer. Le sha256 ne vaut
que parce que `verifier_archive` sait s'en servir. Sans elle, l'empreinte est
décorative.

⚠️ LE MANIFESTE EST SÉPARÉ DES FICHIERS (voie B, arbitrée). Le sha256 est
persisté dans `{audit_path}/{audit_id}.archive.json`, À CÔTÉ du dossier
`{audit_id}/`, jamais dedans : altérer un fichier sans toucher le manifeste est
alors détectable. On NE réordonne PAS le flux d'audit existant d'A6 — le
manifeste est un enregistrement dédié, écrit après les rapports.
"""
import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Tuple

#: En deçà, un export binaire n'est pas un livrable mais un repli (un `.docx`
#: vide pèse ~10 ko) : 512 o transforme un « 0 octet » silencieux en anomalie.
_TAILLE_MIN_LIVRABLE = 512

#: ⚠️⚠️ CE QUE L'ARCHIVE PROUVE, ET LES TROIS CHOSES QU'ELLE NE PROUVE PAS.
#: Écrite ICI, publiée dans le manifeste persisté ET rendue par
#: `verifier_archive` — aux trois endroits où quelqu'un pourrait croire le
#: contraire. La tarification porte DEUX empreintes : celle du PLAN (`s1:`,
#: le contenu se rejoue) et celle du DOCUMENT (ce sha256, le fichier n'a pas
#: bougé). Les confondre ferait de ce mécanisme ce que l'audit combat — un
#: dispositif qui atteste plus qu'il ne porte.
PORTEE_ARCHIVE_TARIF = (
    "dossier conserve et verifiable : l'empreinte du DOCUMENT prouve que le "
    "fichier relu est celui qui a ete ecrit. Elle ne prouve NI que le tarif "
    "est JUSTE (cela, c'est l'empreinte du PLAN, prefixe 's1:', et la "
    "reproductibilite du contenu), NI que le document a ete SIGNE ou assume, "
    "NI qu'il est opposable au sens juridique. La relecture publiee dans le "
    "rapport reste DECLARATIVE : le nom saisi n'est verifie par personne."
)

#: Clé du dict d'octets (sortie de `generer_rapport_*`) → nom de fichier archivé.
_NOMS: Tuple[Tuple[str, str], ...] = (
    ('html_bytes',  'rapport.html'),
    ('word_bytes',  'rapport.docx'),
    ('pdf_bytes',   'rapport.pdf'),
    ('excel_bytes', 'rapport.xlsx'),
)


def archiver_livrable(audit_path, audit_id: str,
                      out: Dict[str, bytes]) -> Tuple[dict, Optional[str]]:
    """Écrit les livrables signés + leurs EMPREINTES, persiste un manifeste séparé.

    Rend `(archive, erreur)` où
    `archive = {dossier, fichiers:{nom:{octets,sha256}}, porte}`.
    Les fichiers vont dans `{audit_path}/{audit_id}/` ; le manifeste (le sha256)
    dans `{audit_path}/{audit_id}.archive.json`, SÉPARÉ du dossier.

    ⚠️ `except OSError` SEUL, et c'est un choix de fond : un `except` nu
    attraperait aussi un bug de CE code (un `TypeError` sur les octets) et le
    publierait comme un « échec d'écriture », rendant le vrai défaut invisible.
    Seuls les échecs du DISQUE (plein, droits, chemin) sont rattrapés.
    ⚠️ L'ÉCHEC REMONTE, il n'est pas avalé : un dossier qu'on croit conservé et
    qui ne l'est pas est pire que pas d'archivage. L'appelant lit `erreur`.
    """
    try:
        base = Path(audit_path)
        dossier = base / str(audit_id)
        dossier.mkdir(parents=True, exist_ok=True)
        fichiers: Dict[str, dict] = {}
        for cle, nom in _NOMS:
            octets = out.get(cle) or b''
            if len(octets) < _TAILLE_MIN_LIVRABLE:
                continue          # un livrable absent ou en repli n'est pas archivé
            (dossier / nom).write_bytes(octets)
            fichiers[nom] = {
                'octets': len(octets),
                'sha256': hashlib.sha256(octets).hexdigest(),
            }
        archive = {
            'dossier':  str(dossier),
            'fichiers': fichiers,
            'porte':    PORTEE_ARCHIVE_TARIF,
        }
        # Manifeste persisté, SÉPARÉ du dossier des fichiers (voie B).
        (base / f"{audit_id}.archive.json").write_text(
            json.dumps(archive, indent=2, ensure_ascii=False), encoding='utf-8')
        return archive, None
    except OSError as e:
        return {}, f'echec: {e}'


def charger_manifeste(audit_path, audit_id: str) -> Optional[dict]:
    """Relit le manifeste persisté `{audit_id}.archive.json`, ou None s'il manque."""
    chemin = Path(audit_path) / f"{audit_id}.archive.json"
    if not chemin.exists():
        return None
    return json.loads(chemin.read_text(encoding='utf-8'))


def verifier_archive(archive: dict) -> dict:
    """Le dossier archivé est-il intact ? Relit les fichiers, compare (modèle A7).

    ⚠️ SANS CETTE FONCTION, L'EMPREINTE EST DÉCORATIVE. Écrire un sha256 que
    personne ne sait vérifier ne prouve rien de plus qu'un fichier sans
    empreinte — c'est un contrôle qui atteste surveiller.

    Rend `{'verifiable', 'intact', 'ecarts', 'porte'}`. `ecarts` nomme chaque
    fichier absent ou altéré ; `intact` est False dès le premier.
    """
    fichiers = (archive or {}).get('fichiers') or {}
    dossier = (archive or {}).get('dossier')
    if not fichiers or not dossier:
        return {'verifiable': False, 'intact': None, 'ecarts': [],
                'raison': "aucun dossier archive pour ce run",
                'porte': PORTEE_ARCHIVE_TARIF}
    ecarts = []
    for nom, attendu in fichiers.items():
        chemin = Path(dossier) / nom
        if not chemin.exists():
            ecarts.append(f'{nom} : absent du dossier')
            continue
        octets = chemin.read_bytes()
        if hashlib.sha256(octets).hexdigest() != attendu.get('sha256'):
            ecarts.append(f'{nom} : empreinte differente — fichier altere')
        elif len(octets) != attendu.get('octets'):
            ecarts.append(f'{nom} : taille differente')
    return {'verifiable': True, 'intact': not ecarts, 'ecarts': ecarts,
            'porte': PORTEE_ARCHIVE_TARIF}
