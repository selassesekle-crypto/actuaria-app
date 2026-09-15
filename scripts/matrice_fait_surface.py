"""LA MATRICE FAIT x SURFACE — QUELS FAITS ATTEIGNENT UN DOCUMENT SIGNÉ ?

À quoi elle sert : rendre MESURABLE la question que `PUBLICATION-1` pose.
Un fait calculé, testé, et qui n'atteint aucune surface signée **n'existe
pas pour l'actuaire qui signe**, ni pour le CAC qui contrôle.

⚠️⚠️ CE N'EST PAS UN INSTRUMENT, C'EST UNE SENTINELLE — ET LA DIFFÉRENCE
EST LA SEULE LEÇON QUE DEUX AUDITS INDÉPENDANTS ONT ÉCRITE AU MÊME
ENDROIT. `reference_gel.json` la porte, mot pour mot :

    « C'était un INSTRUMENT, pas une SENTINELLE — le seul manque
      structurel sur lequel DEUX audits indépendants tombent d'accord. »

Une référence qu'un script régénère, mais que rien ne vérifie à chaque
gate, laisse passer une dégradation commitée. `test_matrice_fait_surface`
**remesure** la portée à chaque gate ; ce fichier-ci ne fait que produire
et figer.

⚠️⚠️ L'ASSIETTE SE DÉRIVE, ELLE NE S'ÉNUMÈRE PAS. Le relevé ne part
d'AUCUNE liste de noms : il ramasse, à toute profondeur des résultats
d'agents, toute chaîne qui a la forme d'une phrase rendue à un lecteur, et
cherche chacune TELLE QUELLE dans le contenu des surfaces réelles.
*Un ensemble fermé de noms exacts est un relevé par SYMBOLE déguisé en
AST — il a déjà manqué 1 moteur sur 5 dans ce dépôt.*

⚠️ ET LA VALEUR CHERCHÉE EST LA VALEUR RENDUE, jamais une ancre retapée :
une apostrophe typographique ou un tiret insécable suffit à fabriquer une
fausse absence. Ce dépôt en porte 346 exemplaires.

⚠️ TROIS ÉTATS, JAMAIS DEUX : `porte` / `absent` / `muet sur ce jeu`. Un
fait qui rend `None` n'est pas « manquant partout » : il n'y avait rien à
trouver. *Une absence de mesure se déclare ; elle ne se convertit pas en
verdict* — c'est la leçon d'`a3/C6`, appliquée à l'instrument qui mesure.

    py scripts/matrice_fait_surface.py --sortie <fichier.json>
    py scripts/matrice_fait_surface.py --comparer <avant.json> <apres.json>
    py scripts/matrice_fait_surface.py --figer

⚠️ LE FICHIER `--sortie` SE DÉPOSE HORS DU DÉPÔT : il porte les phrases
entières d'un run de démonstration. La RÉFÉRENCE versionnée, elle, ne
porte que des empreintes — voir `figer()`.

⚠️ AUCUNE CHAÎNE N'EST PRODUITE DEUX FOIS ICI, ET AUCUN CACHE N'EST POSÉ.
Garder la chaîne entière — dataframes, modèles, documents — vivante
pendant toute une gate n'est pas gratuit : ce chantier a payé deux
`MemoryError`. Chaque commande produit sa chaîne et la laisse mourir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
import warnings

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)
if os.path.join(RACINE, 'scripts') not in sys.path:
    sys.path.insert(0, os.path.join(RACINE, 'scripts'))

REFERENCE = os.path.join(RACINE, 'direction_non_vie', 'tarification',
                         'reference_matrice.json')

#: ⚠️⚠️ LE PLAFOND DE DETTE, ET IL VIT EN DEUX ENDROITS QUI DOIVENT
#: CONCORDER : ici, et dans la référence. `MFS-6` refuse qu'il se relève
#: en silence dans l'un sans l'autre.
#:
#: Mesure du 14/09/2026, sur le jeu de `gel_avant_apres` : **63 faits
#: rendus par a1..a6, dont 17 à ZÉRO surface et 26 à UNE SEULE — et 25 de
#: ces 26 sont l'Excel de l'agent lui-même.** *L'Excel d'agent est un faux
#: réconfort : le fait y est visible, et personne ne le signe.*
#:
#: ⚠️ CE PLAFOND NE PEUT QUE BAISSER. Il borne la dette CONNUE ; un fait
#: NEUF qui naîtrait à <= 1 surface le franchit et fait rougir `MFS-3`.
PLAFOND_DETTE = 43

#: ⚠️⚠️ LES PRODUCTEURS MESURÉS — LA TARIFICATION, ET ELLE SEULE.
#: `produire_la_chaine()` rend aussi `a7` (provisionnement) : mesuré le
#: 16/09/2026, il apporte **111 faits de plus, dont 37 à zéro surface**.
#: Les inclure ferait passer le relevé de 63 à 174 faits et la dette de 43
#: à 83 — *un chiffre qui mesurerait le périmètre d'un AUTRE chantier.*
#: A7 a son propre audit et ses propres constats ouverts.
#:   ⚠️ L'EXCLUSION EST DÉCLARÉE ET CHIFFRÉE, pas silencieuse : la mesure
#:   déposée porte `hors_perimetre`, et `MFS-7` exige que ce compte reste
#:   > 0 — sinon l'exclusion ne retrancherait plus rien et on l'aurait
#:   oubliée en place.
#: ⚠️ LES SURFACES, ELLES, NE SONT PAS RESTREINTES : un fait de
#: tarification qui n'atteindrait QUE le document d'A7 serait une
#: trouvaille, pas un artefact. On ne se prive pas de la voir.
PRODUCTEURS = ('a1', 'a2', 'a3', 'a4', 'a5', 'a6')

#: ⚠️ CE QUE CETTE MESURE NE COUVRE PAS, ÉCRIT À CÔTÉ DU CHIFFRE. *Un
#: relevé sans son assiette se relit faux six jours plus tard.*
ASSIETTE_NON_COUVERTE = (
    "un seul plan (auto), une seule graine, un seul jeu de donnees "
    "synthetiques ; les phrases de MOINS de 60 caracteres ou de moins de "
    "huit mots ne sont pas ramassees (un libelle de cellule n'est pas un "
    "fait) ; les faits produits par A7 sont COMPTES A PART et exclus de la "
    "dette (autre chantier, autres constats) ; et le compte de faits est "
    "un PLANCHER -- un autre plan en produirait d'autres."
)

#: Les trois etats. ⚠️ `MUET` n'est PAS `ABSENT` : il dit qu'il n'y avait
#: rien a chercher sur ce jeu-la.
PORTE, ABSENT, MUET = 'porte', 'absent', 'muet sur ce jeu'

#: Le filtre de forme : ce qui ressemble a une phrase rendue a un humain.
LONGUEUR_MIN = 60
MOTS_MIN = 8
PROFONDEUR_MAX = 7


def dis(x) -> str:
    return str(x).encode('ascii', 'replace').decode('ascii')


def phrases(obj, chemin: str = '', vus=None, profondeur: int = 0):
    """Toute chaine qui a la forme d'une phrase rendue a un lecteur.

    ⚠️ `vus` casse les cycles ET les partages : un meme dict atteint par
    deux chemins ne serait compte qu'une fois sans lui -- et avec lui, on
    garde le PREMIER chemin, ce que `--comparer` doit savoir.
    """
    if vus is None:
        vus = set()
    if profondeur > PROFONDEUR_MAX or id(obj) in vus:
        return
    vus.add(id(obj))
    if isinstance(obj, str):
        if (len(obj) >= LONGUEUR_MIN and obj.count(' ') >= MOTS_MIN
                and '\n' not in obj[:LONGUEUR_MIN]):
            yield chemin, obj
        return
    if isinstance(obj, dict):
        for cle, valeur in obj.items():
            if isinstance(cle, str):
                yield from phrases(valeur,
                                   f'{chemin}.{cle}' if chemin else str(cle),
                                   vus, profondeur + 1)
        return
    if isinstance(obj, (list, tuple)):
        for i, valeur in enumerate(obj[:40]):
            yield from phrases(valeur, f'{chemin}[{i}]', vus, profondeur + 1)


def empreinte_de(phrase: str) -> str:
    """L'identite d'un fait, sans son texte.

    ⚠️ LA REFERENCE VERSIONNEE NE PORTE PAS LES PHRASES. Elles viennent
    d'un portefeuille SYNTHETIQUE, donc rien de confidentiel -- mais un
    depot PUBLIC n'a pas besoin de soixante-trois paragraphes de prose de
    demonstration pour savoir si une portee a baisse.
    """
    return 'sha256:' + hashlib.sha256(
        phrase.strip().encode('utf-8')).hexdigest()[:32]


def mesurer() -> dict:
    """La matrice, mesuree sur une chaine produite ICI et MAINTENANT."""
    import gel_avant_apres as GA

    from direction_non_vie.tarification.services import gel_livrables as G

    depart = time.time()
    resultats = GA.produire_la_chaine()
    emp = G.empreinte(G.livrables_de_la_chaine(resultats))
    #: ⚠️ ON NE CHERCHE QUE DANS LES SURFACES REELLES. Une surface absente
    #: rend `<livrable absent>` : y chercher une phrase donnerait un
    #: << absent >> qui mesurerait weasyprint, pas la portee du fait.
    contenus = {nom: str(contenu) for nom, contenu in emp.contenus.items()
                if contenu != G.ABSENT}

    ramassees: dict[str, list[str]] = {}
    hors = 0
    for chemin, phrase in phrases(resultats):
        #: ⚠️ LE PRODUCTEUR EST LA PREMIERE COMPOSANTE DU CHEMIN, DERIVEE --
        #: jamais une liste de faits. Voir `PRODUCTEURS`.
        if chemin.split('.')[0].split('[')[0] not in PRODUCTEURS:
            hors += 1
            continue
        ramassees.setdefault(phrase, []).append(chemin)

    faits = []
    for phrase, chemins in ramassees.items():
        tranche = phrase.strip()[:LONGUEUR_MIN]
        porteuses = sorted(nom for nom, texte in contenus.items()
                           if tranche in texte)
        faits.append({
            #: ⚠️ LE PLUS PETIT CHEMIN, ET C'EST UN CHOIX : une meme phrase
            #: atteinte par plusieurs chemins recoit une identite STABLE
            #: d'un run a l'autre. `min` dit ce que `sorted(...)[0]` faisait.
            'chemin': min(chemins),
            'empreinte': empreinte_de(phrase),
            'etat': PORTE if porteuses else ABSENT,
            'portee': len(porteuses),
            'surfaces': porteuses,
        })
    faits.sort(key=lambda f: (f['portee'], f['chemin']))
    return {
        'jeu': {'graine': GA.GRAINE, 'taille': GA.TAILLE,
                'arrete': GA.ARRETE, 'annees': list(GA.ANNEES)},
        'tete_git': GA._tete_git(),
        'surfaces_reelles': sorted(contenus),
        'producteurs': list(PRODUCTEURS),
        #: ⚠️ CE QU'ON A ECARTE, COMPTE. Un zero ici voudrait dire que
        #: l'exclusion ne retranche plus rien -- et `MFS-7` le refuse.
        'hors_perimetre': hors,
        'faits': faits,
        'duree_s': round(time.time() - depart, 1),
    }


def _dette(faits) -> int:
    """Le nombre de faits qui n'atteignent AU PLUS qu'une seule surface."""
    return sum(1 for f in faits if f['portee'] <= 1)


def _resumer(mesure: dict) -> None:
    faits = mesure['faits']
    repartition: dict[int, int] = {}
    for f in faits:
        repartition[f['portee']] = repartition.get(f['portee'], 0) + 1
    print(dis(f"  surfaces reelles  : {len(mesure['surfaces_reelles'])}"))
    print(dis(f"  producteurs       : {', '.join(mesure['producteurs'])}"))
    print(dis(f"  ecartes (hors perimetre) : {mesure['hors_perimetre']} "
              f"phrase(s)"))
    print(dis(f"  faits rendus      : {len(faits)}"))
    for portee in sorted(repartition):
        print(dis(f"    {portee:>2} surface(s) : {repartition[portee]:>3} fait(s)"))
    print(dis(f"  DETTE (<= 1 surface) : {_dette(faits)} "
              f"(plafond declare {PLAFOND_DETTE})"))


def deposer(chemin: str) -> int:
    """Depose la mesure complete -- phrases comprises -- HORS du depot."""
    mesure = mesurer()
    with open(chemin, 'w', encoding='utf-8') as fh:
        json.dump(mesure, fh, ensure_ascii=False, indent=1)
    print(dis('=' * 74))
    print(dis('  MATRICE FAIT x SURFACE'))
    print(dis('=' * 74))
    _resumer(mesure)
    print(dis(f"  tete git          : {mesure['tete_git']}"))
    print(dis(f"  duree             : {mesure['duree_s']} s"))
    print(dis(f"  mesure deposee    : {chemin}"))
    return 0


def figer() -> int:
    """Regenere la reference versionnee.

    ⚠️⚠️ C'EST LE SEUL GESTE QUI DESARME LA SENTINELLE. Toute regeneration
    se JUSTIFIE dans le message de commit : sans cette discipline, on
    remplace un garde-fou par un bouton.
    """
    mesure = mesurer()
    faits = mesure['faits']
    dette = _dette(faits)
    #: ⚠️ ON NE FIGE PAS UNE DETTE QUI DEPASSE SON PLAFOND. Figer
    #: graverait la degradation dans la reference, et le << 0 ecart >> des
    #: runs suivants la tairait pour toujours -- exactement ce que le gel
    #: a paye avec ses quinze surfaces absentes.
    if dette > PLAFOND_DETTE:
        print(dis(f"  *** DETTE {dette} > PLAFOND {PLAFOND_DETTE} : "
                  f"REFERENCE NON ECRITE. Corrigez la portee, ou justifiez "
                  f"et abaissez... non : ce plafond ne se releve pas."))
        return 2
    charge = {
        '_doctrine': (
            "MATRICE FAIT x SURFACE. Pour chaque fait rendu par la chaine "
            "a1..a6, le nombre de surfaces signees qui le PORTENT, et "
            "lesquelles. Elle ne porte AUCUNE phrase : seulement le chemin "
            "du fait et le sha256 de son texte. Regeneree par "
            "`py scripts/matrice_fait_surface.py --figer`, et TOUTE "
            "regeneration se justifie dans le message de commit -- c'est ce "
            "qui fait d'un instrument une sentinelle."),
        '_assiette_non_couverte': ASSIETTE_NON_COUVERTE,
        '_trois_etats': {
            PORTE: "au moins une surface signee contient ce fait",
            ABSENT: "aucune surface ne le contient, et il y avait un texte "
                    "a chercher",
            MUET: "le fait n'a rien rendu sur ce jeu : il n'y avait rien a "
                  "chercher, et ce n'est PAS une absence",
        },
        'jeu': mesure['jeu'],
        'plafond_dette': PLAFOND_DETTE,
        'dette_au_figeage': dette,
        'nb_faits': len(faits),
        'surfaces_reelles': mesure['surfaces_reelles'],
        #: ⚠️ LA CLE EST LE CHEMIN, ET L'EMPREINTE VOYAGE AVEC : un meme
        #: chemin dont le TEXTE change est un fait qui a ete reecrit, pas
        #: un fait qui a bouge de place.
        'faits': {f['chemin']: {'empreinte': f['empreinte'],
                                'etat': f['etat'],
                                'portee': f['portee'],
                                'surfaces': f['surfaces']}
                  for f in faits},
    }
    with open(REFERENCE, 'w', encoding='utf-8') as fh:
        json.dump(charge, fh, ensure_ascii=False, indent=2, sort_keys=False)
    print(dis('=' * 74))
    print(dis('  REFERENCE FIGEE'))
    print(dis('=' * 74))
    _resumer(mesure)
    print(dis(f"  reference         : {REFERENCE}"))
    print(dis(f"  tete git          : {mesure['tete_git']}"))
    print(dis("  /!\\ JUSTIFIEZ CETTE REGENERATION DANS LE MESSAGE DE COMMIT."))
    return 0


def comparer(avant: str, apres: str) -> int:
    """Compare deux mesures deposees, fait par fait.

    ⚠️ DEUX MESURES NE SE COMPARENT QUE SUR LE MEME JEU : un ecart lu
    entre deux assiettes mesurerait les donnees, pas le code.
    """
    with open(avant, encoding='utf-8') as fh:
        a = json.load(fh)
    with open(apres, encoding='utf-8') as fh:
        b = json.load(fh)
    if a['jeu'] != b['jeu']:
        print(dis(f"  *** JEUX DIFFERENTS : {a['jeu']} vs {b['jeu']} — "
                  f"comparaison REFUSEE"))
        return 2
    ia = {f['chemin']: f for f in a['faits']}
    ib = {f['chemin']: f for f in b['faits']}
    print(dis('=' * 74))
    print(dis(f"  avant : {a['tete_git']}   apres : {b['tete_git']}"))
    print(dis('=' * 74))
    degrades = [c for c in ia if c in ib
                and ib[c]['portee'] < ia[c]['portee']]
    gagnes = [c for c in ia if c in ib and ib[c]['portee'] > ia[c]['portee']]
    disparus = sorted(set(ia) - set(ib))
    apparus = sorted(set(ib) - set(ia))
    for etiquette, lot in (('PORTEE DEGRADEE', degrades),
                           ('portee gagnee', gagnes),
                           ('faits DISPARUS du releve', disparus),
                           ('faits apparus', apparus)):
        print(dis(f"  {etiquette:28} {len(lot)}"))
        for chemin in sorted(lot)[:12]:
            if chemin in ia and chemin in ib:
                print(dis(f"      {chemin} : {ia[chemin]['portee']} -> "
                          f"{ib[chemin]['portee']}"))
            else:
                print(dis(f"      {chemin}"))
    print()
    print(dis(f"  dette avant {_dette(a['faits'])} -> apres "
              f"{_dette(b['faits'])} (plafond {PLAFOND_DETTE})"))
    return 0 if not degrades and not disparus else 1


def main() -> int:
    analyseur = argparse.ArgumentParser(
        description='La matrice fait x surface.')
    analyseur.add_argument('--sortie', metavar='FICHIER',
                           help='depose la mesure complete (HORS du depot)')
    analyseur.add_argument('--comparer', nargs=2, metavar=('AVANT', 'APRES'))
    analyseur.add_argument(
        '--figer', action='store_true',
        help="regenere `direction_non_vie/tarification/reference_matrice."
             "json`. Le seul geste qui desarme la sentinelle MFS-4.")
    arguments = analyseur.parse_args()
    choisis = sum(1 for x in (arguments.sortie, arguments.comparer,
                              arguments.figer) if x)
    if choisis != 1:
        analyseur.error('choisir --sortie OU --comparer OU --figer')
    warnings.filterwarnings('ignore')
    logging.disable(logging.CRITICAL)
    if arguments.figer:
        return figer()
    if arguments.sortie:
        return deposer(arguments.sortie)
    return comparer(*arguments.comparer)


if __name__ == '__main__':
    sys.exit(main())
