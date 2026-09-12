r"""
==============================================================================
  LES DEUX SURFACES DU MEME PRIX REFUSENT LA MEME DONNEE
==============================================================================

⚠️⚠️ CE QUE CE CONTROLE EXISTE POUR EMPECHER, ET IL EST ARRIVE. Le prix
sort par deux chemins. `TarifNonVie.tarifer(contrat)` REFUSAIT un facteur
illisible depuis le constat `pipeline/C1` ; `pipeline_complet(portefeuille)`
-- l'autre surface du MEME prix -- ne le voyait pas. La couche qualite
n'interrogeait que TROIS roles (exposition, cible frequence, cible cout) ;
aucun FACTEUR n'etait regarde.

MESURE DU 11/09/2026, plan `auto`, 1 500 lignes, UN `bonus_malus =
'beaucoup'` :

    signalements de la couche qualite      0
    prime de la ligne, donnee saine        344,99 EUR
    prime de la ligne, donnee sale         288,85 EUR   (-16,27 %)
    TOTAL du portefeuille                  +0,0000 %
    `tarifer()` sur le meme contrat        success=False, NON TARIFABLE

⚠️⚠️ ET C'EST LE PIEGE DANS SA FORME PURE. *Le coefficient d'equilibre
ramene le total : la divergence vit entierement dans la REPARTITION, et
AUCUN controle agrege ne pouvait la voir.* Dans l'autre sens, sur
`predire_portefeuille`, un `bonus_malus` illisible fait payer 39,38 EUR au
lieu de 17,12 EUR (+130 %), par substitution de la moyenne du portefeuille.

⚠️⚠️ UNE DEFINITION, DEUX SANCTIONS, ET C'EST VOULU. Le criterion vit
desormais dans `Facteur.motif_illisible` -- une seule ecriture, que les
deux surfaces LISENT. Mais sur un contrat isole on REFUSE (le prix est
signe individuellement) et sur un portefeuille on SIGNALE (regle 3 :
ambigu, ni exclu ni corrige). *Ce qui doit etre commun est le CRITERE, pas
la decision.*

CE QUE CES CONTROLES SURVEILLENT. L'ACCORD des deux surfaces, valeur par
valeur, dans LES DEUX SENS : ce que l'une refuse, l'autre le signale ; ce
que l'une accepte, l'autre se tait. Ils ne verifient jamais qu'une
fonction precise est appelee -- une reecriture correcte doit rester verte,
une divergence doit rougir, quelle qu'en soit la cause.
==============================================================================
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

_CACHE: dict = {}

#: ⚠️ LES CINQ FORMES MESUREES PAR L'AUDITEUR, plus les bornes. Chacune est
#: un chemin DIFFERENT de `motif_illisible` : modalite inconnue, chaine
#: vide, absence, decimale a la francaise, blanc. *Une seule d'entre elles
#: aurait laisse quatre portes ouvertes.*
_ILLISIBLES = ('beaucoup', '', None, '12,5', ' ')


def _plan():
    if 'plan' not in _CACHE:
        from core.plan_tarifaire import PlanTarifaire
        _CACHE['plan'] = PlanTarifaire.depuis_yaml(
            str(_RACINE / 'plans' / 'auto.yaml'))
    return _CACHE['plan']


class _SurfaceContrat:
    """La surface `tarifer()`, reduite a ce qui DECIDE du refus.

    ⚠️ `anomalies_du_contrat` ne lit que `self.plan` : l'appeler ainsi
    exerce le VRAI code sans exiger un pipeline ajuste. *Un controle qui
    dependrait de tout l'ajustement accuserait le prix pour une panne
    ailleurs.*
    """

    def __init__(self, plan):
        self.plan = plan

    def refuse(self, contrat) -> list:
        from direction_non_vie.tarification.pipeline_tarifaire import (
            TarifNonVie,
        )
        return TarifNonVie.anomalies_du_contrat(self, contrat)


def _signale(df, plan):
    """Les codes `valeur_illisible_facteur` vus par la couche qualite."""
    import logging
    import warnings

    from core.qualite_donnees import preambule_qualite
    warnings.filterwarnings('ignore')
    niveau = logging.getLogger().level
    logging.disable(logging.CRITICAL)
    try:
        r = preambule_qualite(df, plan, horodatage='2026-09-13T00:00:00')
    finally:
        logging.disable(niveau)
    return r


def _codes(rapport, seau=None):
    """Les codes vus, par seau de regle ou tous seaux confondus.

    ⚠️ `RapportQualite` range les anomalies en TROIS listes -- exclusions
    (regle 1), corrections (regle 2), signalements (regle 3). Interroger
    une seule sans le dire laisserait croire a une absence la ou il y a
    seulement un autre seau.
    """
    seaux = (seau,) if seau else ('exclusions', 'corrections',
                                  'signalements')
    return sorted({a.code for s in seaux
                   for a in (getattr(rapport, s, None) or ())})


def _portefeuille(n=40, **remplace):
    """Un portefeuille SAIN au regard du plan `auto`, sauf ce qu'on remplace."""
    import numpy as np
    import pandas as pd
    r = np.random.default_rng(5)
    d = pd.DataFrame({
        'id_contrat': np.arange(1, n + 1), 'date_echeance': '2023-01-01',
        'exposition': np.clip(r.uniform(0.3, 1.0, n), 0.02, 1.0),
        'age': r.integers(25, 70, n),
        'bonus_malus': np.round(r.uniform(0.55, 1.40, n), 2),
        'anciennete_permis': r.integers(2, 40, n),
        'puissance_fiscale': r.integers(4, 12, n),
        'age_vehicule': r.integers(0, 15, n),
        'valeur_venale': np.round(np.exp(r.normal(9.3, 0.4, n)), 2),
        'garantie': r.choice(['Tiers', 'TousRisques'], n),
        'carburant': r.choice(['Essence', 'Diesel'], n),
        'csp': r.choice(['Cadre', 'Employe', 'Retraite'], n),
        'usage': r.choice(['Prive', 'Pro'], n),
        'antecedents_sinistres_n1': r.poisson(0.2, n),
        'kilometrage_annuel': r.integers(5000, 25000, n),
        'milieu_geographique': r.choice(['Urbain', 'Periurbain', 'Rural'], n),
        'nb_sinistres': r.poisson(0.12, n),
        'cout_total_sinistres': 0.0})
    for col, (ligne, valeur) in remplace.items():
        d[col] = d[col].astype(object)
        d.loc[ligne, col] = valeur
    return d


class TestLesDeuxSurfacesSAccordent(unittest.TestCase):

    def test_PF1_SCEAU_ce_que_le_contrat_REFUSE_le_portefeuille_le_SIGNALE(
            self):
        """⚠️⚠️ LE SCEAU. Pour chacune des cinq formes d'illisibilite
        mesurees, les DEUX surfaces doivent reagir. Une seule qui se tait
        et le souscripteur paie la prime du contrat moyen sans que rien ne
        le dise."""
        plan = _plan()
        surface = _SurfaceContrat(plan)
        for valeur in _ILLISIBLES:
            with self.subTest(valeur=repr(valeur)):
                contrat = _portefeuille(n=1).iloc[0].to_dict()
                contrat['bonus_malus'] = valeur
                refus = surface.refuse(contrat)
                self.assertTrue(
                    refus,
                    f"`tarifer()` ACCEPTE bonus_malus={valeur!r} : la "
                    f"surface contrat ne refuse plus ce qu'elle refusait.")

                rap = _signale(_portefeuille(bonus_malus=(0, valeur)), plan)
                #: ⚠️ DANS `signalements`, ET PAS AILLEURS. La regle 3 dit
                #: << ambigu : on signale, on n'exclut ni ne corrige >>. Le
                #: trouver dans `exclusions` voudrait dire qu'on a ferme le
                #: defaut en ECARTANT des contrats -- donc en deplacant des
                #: euros.
                self.assertIn(
                    'valeur_illisible_facteur', _codes(rap, 'signalements'),
                    f"bonus_malus={valeur!r} : `tarifer()` refuse, la couche "
                    f"qualite ne SIGNALE RIEN. Les deux surfaces du meme "
                    f"prix ont rediverge -- vu : {_codes(rap)}")
                self.assertNotIn(
                    'valeur_illisible_facteur', _codes(rap, 'exclusions'),
                    f"bonus_malus={valeur!r} : le signalement EXCLUT la "
                    f"ligne. Un euro bouge la ou rien ne devait bouger.")
        print(f"    PF-1 SCEAU : les {len(_ILLISIBLES)} formes illisibles "
              f"sont refusees ET signalees")

    def test_PF2_SCEAU_ce_que_le_contrat_ACCEPTE_n_est_PAS_signale(self):
        """⚠️⚠️ LE SECOND SENS, ET IL EST LE PLUS FACILE A PERDRE. Un
        criterion trop large signalerait des contrats sains : l'actuaire
        apprendrait a ignorer le signal, et le jour ou il porte un vrai
        defaut il passerait avec les autres. *Un controle qui accuse ne
        surveille pas.*"""
        plan = _plan()
        surface = _SurfaceContrat(plan)
        for valeur in (0.55, 1.0, 1.40, '0.85'):
            with self.subTest(valeur=repr(valeur)):
                contrat = _portefeuille(n=1).iloc[0].to_dict()
                contrat['bonus_malus'] = valeur
                self.assertEqual(
                    surface.refuse(contrat), [],
                    f"`tarifer()` refuse bonus_malus={valeur!r}, qui est "
                    f"lisible au regard du plan.")
        rap = _signale(_portefeuille(), plan)
        self.assertNotIn(
            'valeur_illisible_facteur', _codes(rap),
            f"portefeuille entierement SAIN, et la couche qualite signale "
            f"un facteur illisible : {_codes(rap)}")
        print("    PF-2 SCEAU : une valeur lisible n est ni refusee ni "
              "signalee")

    def test_PF3_SCEAU_le_signalement_NE_BLOQUE_PAS_et_n_exclut_rien(self):
        """⚠️⚠️ AUCUN EURO NE BOUGE, ET CELA SE MESURE. Une valeur illisible
        est AMBIGUE, pas impossible : la doctrine du module est de la
        signaler et de la laisser (regle 3). Si ce code devenait
        disqualifiant, il ferait BLOQUER des fichiers qui passaient --
        un garde-fou qu'on croit desarme et qui tire."""
        from core.qualite_donnees import CODES_DISQUALIFIANTS
        self.assertNotIn(
            'valeur_illisible_facteur', CODES_DISQUALIFIANTS,
            "le code est devenu DISQUALIFIANT : il peut desormais bloquer "
            "un portefeuille, et des euros bougent.")
        plan = _plan()
        #: ⚠️ LA MOITIE DU PORTEFEUILLE ILLISIBLE -- le pire cas, celui ou
        #: un code bloquant se verrait a coup sur.
        d = _portefeuille(n=40)
        d['bonus_malus'] = d['bonus_malus'].astype(object)
        d.loc[:19, 'bonus_malus'] = 'beaucoup'
        rap = _signale(d, plan)
        self.assertFalse(
            rap.bloque,
            "20 lignes sur 40 illisibles font BLOQUER le portefeuille : le "
            "signalement est devenu une exclusion.")
        self.assertIsNotNone(rap.dataframe_propre,
                             'le dataframe propre a disparu')
        self.assertEqual(
            len(rap.dataframe_propre), 40,
            f"{len(rap.dataframe_propre)}/40 lignes retenues : des contrats "
            f"ont ete ECARTES par un signalement qui ne doit rien exclure.")
        print(f"    PF-3 SCEAU : 20/40 illisibles, bloque={rap.bloque}, "
              f"{len(rap.dataframe_propre)}/40 lignes retenues")

    def test_PF4_CONTRE_EPREUVE_zero_faux_positif_sur_les_plans_reels(self):
        """⚠️⚠️ LA CONTRE-EPREUVE SUR L'ASSIETTE REELLE. Le criterion lit ce
        que le plan DECLARE ; s'il se trompait, il accuserait des plans de
        production. On l'interroge sur les trois plans que l'auditeur a
        mesures, facteur par facteur, avec des valeurs prises DANS leurs
        propres declarations."""
        from core.plan_tarifaire import PlanTarifaire
        vus = {}
        for nom in ('auto', 'mrh', 'rcpro'):
            chemin = _RACINE / 'plans' / f'{nom}.yaml'
            if not chemin.exists():
                continue
            plan = PlanTarifaire.depuis_yaml(str(chemin))
            faux = []
            for f in plan.facteurs:
                if f.type == 'categoriel' and f.modalites:
                    #: chaque modalite DECLAREE doit etre acceptee
                    for m in f.modalites:
                        if f.motif_illisible(m) is not None:
                            faux.append(f'{f.nom}={m!r}')
                elif f.bornes is not None:
                    bas, haut = f.bornes
                    for x in (bas, (bas + haut) / 2, haut):
                        if f.motif_illisible(x) is not None:
                            faux.append(f'{f.nom}={x!r}')
                else:
                    for x in (0.0, 1.0, 42.5):
                        if f.motif_illisible(x) is not None:
                            faux.append(f'{f.nom}={x!r}')
            vus[nom] = len(plan.facteurs)
            self.assertEqual(
                faux, [],
                f"plan {nom} : le criterion accuse des valeurs que le plan "
                f"DECLARE lui-meme : {faux[:6]}")
        self.assertTrue(vus, 'aucun plan reel lu : ce controle ne prouve rien')
        print('    PF-4 contre-epreuve : 0 faux positif sur '
              + ', '.join(f'{k} ({v} facteurs)' for k, v in vus.items()))

    def test_PF6_SCEAU_le_signalement_nomme_LES_BONNES_lignes(self):
        """⚠️⚠️ CE QUE LA VERIFICATION DU CORRECTIF RECU NE REGARDAIT PAS.
        Elle constatait << 1 signalement `valeur_illisible_facteur` nommant
        `bonus_malus` >> -- le CODE et la COLONNE. Elle ne regardait ni le
        NOMBRE de lignes ni LESQUELLES. Or le correctif passait a `_ajouter`
        une liste d'INDICES la ou il attend un MASQUE BOOLEEN :

            valeur fautive a l'index 0    -> AUCUNE anomalie
            a l'index 7                   -> une anomalie designant la ligne 0
            aux index {0, 7}              -> une seule, designant la ligne 1

        *Un signalement qui designe la mauvaise ligne envoie l'actuaire
        verifier un contrat sain et laisse le fautif tranquille.* Ce
        controle lit `index`, pas seulement `code`."""
        plan = _plan()
        for positions in ([0], [7], [0, 7], [3, 11, 29]):
            with self.subTest(lignes=positions):
                d = _portefeuille(n=40)
                d['bonus_malus'] = d['bonus_malus'].astype(object)
                for k in positions:
                    d.loc[k, 'bonus_malus'] = 'beaucoup'
                rap = _signale(d, plan)
                vus = [a for a in (rap.signalements or [])
                       if a.code == 'valeur_illisible_facteur']
                self.assertEqual(
                    len(vus), 1,
                    f"lignes fautives {positions} : {len(vus)} anomalie(s) "
                    f"au lieu d'une.")
                self.assertEqual(
                    sorted(vus[0].index), positions,
                    f"le signalement designe les lignes "
                    f"{sorted(vus[0].index)} alors que les fautives sont "
                    f"{positions}.")
                self.assertEqual(
                    vus[0].nb_lignes, len(positions),
                    f"nb_lignes={vus[0].nb_lignes} pour {len(positions)} "
                    f"ligne(s) fautive(s).")
        print("    PF-6 SCEAU : les lignes nommees sont exactement les "
              "fautives, index 0 compris")

    def test_PF5_SCEAU_le_criterion_n_a_QU_UNE_ecriture(self):
        """⚠️⚠️ LA CAUSE, PAS LE SYMPTOME. Les deux surfaces ont diverge
        parce que la regle etait ECRITE DEUX FOIS -- une copie dans
        `anomalies_du_contrat`, rien dans la couche qualite. Tant qu'il n'y
        a qu'une ecriture, elles ne PEUVENT plus rediverger.

        ⚠️ Le controle porte sur le COMPORTEMENT, pas sur le texte : on
        demande aux deux surfaces de juger les MEMES valeurs et on exige le
        meme verdict. Une seconde copie, meme identique aujourd'hui,
        finirait par diverger -- et ce jour-la ce controle rougira."""
        plan = _plan()
        surface = _SurfaceContrat(plan)
        facteur = next(f for f in plan.facteurs if f.nom == 'bonus_malus')
        desaccords = []
        for valeur in (*_ILLISIBLES, 0.55, 1.0, 1.40, '0.85', -999, 1e12):
            contrat = _portefeuille(n=1).iloc[0].to_dict()
            contrat['bonus_malus'] = valeur
            par_contrat = bool(surface.refuse(contrat))
            par_le_plan = facteur.motif_illisible(valeur) is not None
            if par_contrat != par_le_plan:
                desaccords.append((repr(valeur), par_contrat, par_le_plan))
        self.assertEqual(
            desaccords, [],
            f"la surface contrat et le plan ne jugent pas pareil : "
            f"{desaccords}. Une seconde ecriture du criterion est reapparue.")
        print("    PF-5 SCEAU : contrat et plan rendent le meme verdict sur "
              "11 valeurs")


if __name__ == '__main__':
    unittest.main(verbosity=2)
