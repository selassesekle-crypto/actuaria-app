# ruff: noqa
"""PASSAGE LIBELLES -- quel champ atteint REELLEMENT un livrable ?

⚠️⚠️ CONCLU PAR EXECUTION, JAMAIS PAR LECTURE. Sur un seul champ
(`justification_regl`), trois methodes ont donne trois reponses :
    grep du nom          -> "aucun lecteur"   FAUX : il est lu par `.items()`
    lecture de la boucle -> "publie"          FAUX : un filtre isinstance l'ecarte
    EXECUTION            -> non publie        verifie dans les cellules produites
On PRODUIT donc le livrable et on lit ce qu'il contient.

⚠️ Un .docx et un .xlsx sont des ARCHIVES ZIP : chercher un marqueur dans
leurs octets bruts ne prouve rien. On decompresse.

⚠️⚠️ LES TROIS ANGLES MORTS DE CE BANC, ET COMMENT ON LES LEVE. Un « muet »
n'est une trouvaille que si les trois sont ecartes :

  1. ITERATION GENERIQUE -- un champ atteint par `for k, v in d.items()` n'est
     jamais NOMME : `grep` ne le voit pas. On execute.
  2. CLE vs VALEUR -- un champ CONSOMME PUIS REFORMATE parait muet a tort
     (`synthese_exclusions` republie le nom de colonne, pas le motif). On
     marque AUSSI les cles -- voir `main()` en fin de fichier.
  3. MISE EN FORME -- un marqueur pose sur un NOMBRE est detruit par
     l'arrondi : `1.5757` sort en `1.576`. **Les marqueurs doivent etre des
     CHAINES.** Pour un champ numerique, le banc ne conclut pas : il faut
     verifier si l'information arrive par une AUTRE source (mesure : le Gini,
     le score et le RMSE de la fiche arrivaient deja par `modele_production`).

⚠️ ET LE DOCUMENT N'EST PAS LE SEUL CHEMIN VERS L'ACTUAIRE : l'ECRAN en est un
autre. Mesure complementaire par AST sur `actuaria_app.py` -- elle ne lit
jamais `fiche_decision`, mais elle lit `commentaire`, `gini`, `classement`,
`statut_rag`, `rapport` et `audit_trail` directement.
"""
import io
import logging
import sys
import warnings
import zipfile

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')
if __name__ == '__main__':
    logging.disable(logging.CRITICAL)

import openpyxl


def M(nom: str) -> str:
    """Marqueur unique et sans separateur : il doit traverser tout formatage."""
    return 'ZQMARQ' + nom.replace('.', '').replace('_', '') + 'ZQ'


def texte_livrable(sortie) -> str:
    """Le texte REELLEMENT contenu dans un livrable, quel que soit son format."""
    if isinstance(sortie, (bytes, bytearray)):
        if sortie[:2] == b'PK':
            z = zipfile.ZipFile(io.BytesIO(sortie))
            if any(n.startswith('xl/') for n in z.namelist()):
                wb = openpyxl.load_workbook(io.BytesIO(sortie))
                return "\n".join(
                    str(c.value) for ws in wb.worksheets
                    for row in ws.iter_rows() for c in row
                    if c.value is not None)
            return "\n".join(z.read(n).decode('utf-8', 'replace')
                             for n in z.namelist() if n.endswith('.xml'))
        return sortie.decode('utf-8', 'replace')
    return str(sortie)


def fiche_marquee() -> dict:
    return {
        'modele_recommande':  M('fiche.modele_recommande'),
        'profil_utilise':     M('fiche.profil_utilise'),
        'score_final':        0.8373,
        'gini':               0.2145,
        'overfit_ratio':      1.07,
        'forces':             [M('fiche.forces')],
        'faiblesses':         [M('fiche.faiblesses')],
        'risques':            [M('fiche.risques')],
        'alternatives':       [M('fiche.alternatives')],
        'questions_actuaire': [M('fiche.questions_actuaire')],
        'justification_regl': [M('fiche.justification_regl')],
        'decision_finale':    M('fiche.decision_finale'),
    }


def resultat_a6_marque() -> dict:
    modele = {'modele': M('modele_production.modele'), 'famille': 'GBM',
              'gini_test': 0.2145, 'gini_train': 0.23, 'overfit_ratio': 1.07,
              'score_global': 0.8373, 'rmse_test': 12.3}
    return {
        'success': True, 'branche': 'auto', 'statut_rag': 'AMBRE',
        'classement': [dict(modele, rang=1)], 'modele_production': modele,
        'backtest': {'disponible': True, 'n_fenetres': 3, 'gini_moyen': 0.20,
                     'stabilite': M('backtest.stabilite'),
                     'methode': 'walk_forward'},
        'lift_ratio': 1.4, 'lift_statut': M('lift_statut'),
        'exclusions_conformite': {'colX': M('exclusions_conformite')},
        'alertes_conformite': {'colY': {'spearman': 0.99}},
        'alertes_modele': [{'modele': 'GBM', 'severite': 'AMBRE',
                            'message': M('alertes_modele.message')}],
        'exclusions_cible': [M('exclusions_cible')],
        'valide_par_actuaire_dl': M('valide_par_actuaire_dl'),
        'rapport_qualite': None, 'rapport_mapping': None,
        'colonnes_plan_manquantes': None, 'courbes': {}, 'graphiques': {},
        'graphiques_validation': {},
        'validation_selection': {'verdict': M('validation_selection.verdict')},
        'fiche_decision': fiche_marquee(),
        'rapport': {'etapes': [M('rapport.etapes')]},
        'commentaire': M('commentaire'), 'audit_id': 'A6-PASSAGE',
        'hypotheses': {'h1': M('hypotheses.h1')},
        'audit_trail': {'profil_ponderation': M('audit_trail.profil_ponderation'),
                        'environnement': 'test', 'profil_valide_par': None,
                        'gouvernance_ok': False},
    }


CHAMPS = ([f'fiche.{k}' for k in fiche_marquee()] +
          ['modele_production.modele', 'backtest.stabilite', 'lift_statut',
           'exclusions_conformite', 'alertes_modele.message',
           'exclusions_cible', 'valide_par_actuaire_dl',
           'validation_selection.verdict', 'rapport.etapes', 'commentaire',
           'hypotheses.h1', 'audit_trail.profil_ponderation'])


def main() -> None:
    from direction_non_vie.tarification.services import rapport_equipe_tarif as RE
    from direction_non_vie.tarification.services import rapport_modeles_tarif as RM
    from direction_non_vie.tarification.services.tarif_excel import export_excel_a6

    res = resultat_a6_marque()
    livrables = {}
    for nom, appel in (
        ('excel A6',     lambda: export_excel_a6(res, audit_id='A6-PASSAGE')),
        ('html equipe',  lambda: RE.export_html_equipe({'a6': res}, branche='auto')),
        ('word equipe',  lambda: RE.export_word_equipe({'a6': res}, branche='auto')),
        ('html modeles', lambda: RM.export_html(res)),
        ('word modeles', lambda: RM.export_word(res)),
    ):
        try:
            livrables[nom] = texte_livrable(appel())
        except Exception as exc:
            livrables[nom] = ''
            print(f"  [INDISPONIBLE] {nom} : {type(exc).__name__}: {exc}")

    # ⚠️ CONTROLE DE VALIDITE DU BANC : un livrable qui ne porte AUCUN marqueur
    # a probablement pris un chemin degrade -- ses zeros ne prouvent rien.
    print("=" * 78)
    print("  VALIDITE DU BANC -- un livrable sans aucun marqueur ne prouve rien")
    print("=" * 78)
    for nom, txt in livrables.items():
        n = sum(1 for c in CHAMPS if M(c) in txt)
        etat = '[VALIDE ]' if n else '[SUSPECT]'
        print(f"  {etat} {nom:14s} {len(txt):8d} car  {n} marqueur(s)")

    print()
    print("=" * 78)
    print("  QUEL LIVRABLE PORTE QUEL CHAMP ?  (X = present)")
    print("=" * 78)
    entetes = list(livrables)
    print(f"  {'champ':38s} " + " ".join(f"{n[:12]:>13s}" for n in entetes))
    muets = []
    for champ in CHAMPS:
        cases = [('X' if M(champ) in livrables[n] else '.') for n in entetes]
        if 'X' not in cases:
            muets.append(champ)
        print(f"  {champ:38s} " + " ".join(f"{c:>13s}" for c in cases))

    print()
    print("=" * 78)
    print(f"  {len(muets)}/{len(CHAMPS)} CHAMPS N'ATTEIGNENT AUCUN DES "
          f"{len(entetes)} LIVRABLES")
    print("=" * 78)
    for c in muets:
        print(f"    {c}")

    fiche = [c for c in CHAMPS if c.startswith('fiche.')]
    publies = [c for c in fiche if c not in muets]
    print()
    print(f"  LA FICHE D'AIDE A LA DECISION : {len(publies)}/{len(fiche)} "
          f"champs publies ({100 * len(publies) // len(fiche)} %)")
    print(f"    publies : {publies}")

    # ── ⚠️⚠️ LA LIMITE DU BANC, ET COMMENT ON LA LEVE ────────────────────────
    # Un marqueur absent prouve que la VALEUR n'est pas publiee VERBATIM. Il ne
    # prouve pas que le champ est ignore : un service peut le CONSOMMER puis le
    # REFORMATER. `synthese_exclusions` republie ainsi le NOM DE COLONNE et non
    # le motif -- `exclusions_conformite` paraissait muet alors qu'il est lu.
    # On distingue donc les deux en marquant AUSSI LES CLES.
    print()
    print("=" * 78)
    print("  CONSOMME-ET-REFORMATE  vs  VRAIMENT MUET  (marqueur dans la CLE)")
    print("=" * 78)
    res2 = resultat_a6_marque()
    res2['exclusions_conformite'] = {'ZQCLEEXCLZQ': 'un motif quelconque'}
    res2['alertes_modele'] = [{'modele': 'ZQCLEMODZQ', 'severite': 'AMBRE',
                               'message': 'ZQCLEMSGZQ'}]
    res2['validation_selection'] = {'verdict': 'ZQCLEVERDZQ', 'conforme': False}
    res2['backtest'] = {'disponible': True, 'n_fenetres': 3, 'gini_moyen': 0.2,
                        'stabilite': 'ZQCLESTABZQ', 'methode': 'ZQCLEMETHZQ'}
    tout = ''
    for appel in (lambda: export_excel_a6(res2, audit_id='X'),
                  lambda: RE.export_html_equipe({'a6': res2}, branche='auto'),
                  lambda: RE.export_word_equipe({'a6': res2}, branche='auto'),
                  lambda: RM.export_html(res2),
                  lambda: RM.export_word(res2)):
        try:
            tout += texte_livrable(appel())
        except Exception:
            pass
    for marque, quoi in (('ZQCLEEXCLZQ', 'exclusions_conformite  (la CLE)'),
                         ('ZQCLEMODZQ', 'alertes_modele.modele'),
                         ('ZQCLEMSGZQ', 'alertes_modele.message'),
                         ('ZQCLEVERDZQ', 'validation_selection.verdict'),
                         ('ZQCLESTABZQ', 'backtest.stabilite'),
                         ('ZQCLEMETHZQ', 'backtest.methode')):
        etat = 'CONSOMME' if marque in tout else 'MUET'
        print(f"  [{etat:8s}] {quoi}")


if __name__ == '__main__':
    main()
