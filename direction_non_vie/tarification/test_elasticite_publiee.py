"""⚠️⚠️ 988 LIGNES DE CALCUL N'ATTEIGNAIENT AUCUN LIVRABLE.

Constat `socle/C9`, ouvert le 03/09/2026 en fermant les deux points restants
de `core/elasticite.py`. Les deux n'en font qu'UN, et il est plus large que ce
que j'avais annonce.

LA CHAINE, MESUREE DE BOUT EN BOUT :

```
  core/elasticite.py (988 l) -> A4 range `elasticite` + `sensibilite_tarifaire`
     -> A4 compose un paragraphe dans SON commentaire
        -> ce commentaire n'atteint le rapport QU'EN REPLI, apres A6
           -> A6 a TOUJOURS un commentaire (1 138 car. mesures)
              =>  le repli ne tire JAMAIS
     -> et A6 ne relayait NI l'un NI l'autre
        =>  les 3 surfaces ne pouvaient meme pas les lire
```

> ### *Un calcul qui n'atteint aucun livrable n'existe pas.*
> (`services/C7`, `socle/C1` -- la meme lecon, sur le plus gros calcul du
> module.)

⚠️⚠️ ET CE N'EST PAS UN AJOUT DE CONTENU : L'INTENTION ETAIT DEJA ECRITE.
A4 porte en commentaire, mot pour mot : << CE QUI N'EST PAS PRIS EN COMPTE SE
DIT AUSSI. L'actuaire qui lit ce commentaire doit savoir que la dimension
elasticite-prix n'entre pas dans l'analyse -- et pourquoi. Le silence
laisserait croire qu'elle a ete consideree. >> Ce lot livre ce qui etait concu
pour l'etre.

⚠️ ET LE FICHIER M'A AVERTI LUI-MEME. `_LABELS_SYNTHESES` est un tuple que le
HTML et le Word ITERENT : *<< une cle sans libelle est rendue NULLE PART, en
silence, dans les formats qui partent au CAC >>* (constat `CF-9`). Sans le
libelle, l'elasticite aurait ete calculee, relayee, publiee dans l'Excel A6 --
et invisible au CAC.
"""
from __future__ import annotations

import ast
import contextlib
import io
import logging
import pathlib
import unittest

from core.elasticite import (
    ELASTICITE_ESTIMEE,
    ELASTICITE_NON_FOURNIE,
    synthese_elasticite,
)

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_SERVICES = _RACINE / 'direction_non_vie' / 'tarification' / 'services'


def _muet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return fn(*a, **kw)
        finally:
            logging.disable(precedent)


class TestElasticitePubliee(unittest.TestCase):

    def test_EP_1_LE_CONSTAT_A6_relaie_les_deux_cles(self):
        """⚠️⚠️ SANS CE RELAIS, LES TROIS SURFACES NE PEUVENT RIEN LIRE.

        Elles lisent toutes `result_a6`. A6 ne portait ni `elasticite` ni
        `sensibilite_tarifaire` : la chaine etait coupee AVANT elles.

        Assiette : les DEUX dicts de sortie d'A6, par AST -- une moitie des
        appelants ne verrait rien autrement (la lecon de `OB-11`).
        """
        src = (_RACINE / 'direction_non_vie' / 'tarification'
               / 'a6_comparaison' / 'agent.py').read_text(encoding='utf-8')
        arbre = ast.parse(src)
        for cle in ('elasticite', 'sensibilite_tarifaire'):
            n = [c.lineno for x in ast.walk(arbre) if isinstance(x, ast.Dict)
                 for c in x.keys
                 if isinstance(c, ast.Constant) and c.value == cle]
            self.assertEqual(
                len(n), 2,
                f"A6 relaie '{cle}' dans {len(n)} dict(s) de sortie au lieu "
                f"des DEUX : une moitie des appelants ne la verrait pas")
        print("    EP-1 A6 relaie les 2 cles dans ses 2 dicts de sortie")

    def test_EP_2_la_synthese_PARLE_quand_l_elasticite_n_est_pas_prise(self):
        """⚠️⚠️ *Le silence laisserait croire qu'elle a ete consideree.*"""
        etat = {'etat': ELASTICITE_NON_FOURNIE,
                'motif': 'Aucune donnee de comportement declaree.',
                'ce_que_cela_coute': "Aucune recommandation de variation."}
        t = synthese_elasticite(etat) or ''
        self.assertIn('NON PRISE EN COMPTE', t)
        self.assertIn(ELASTICITE_NON_FOURNIE, t)
        self.assertIn('Aucune donnee de comportement', t)
        self.assertIn('Aucune recommandation', t,
                      "le COUT de l'absence n'est pas publie : l'actuaire lit "
                      "qu'il manque quelque chose sans savoir ce que cela lui "
                      "retire")
        print(f"    EP-2 etat + motif + cout de l'absence publies "
              f"({len(t)} car.)")

    def test_EP_3_estimee_elle_publie_l_IC_et_la_RESERVE_jamais_eps_seul(self):
        """⚠️⚠️ *Un eps seul se lirait comme une certitude* -- c'est ce que le
        << Tarif optimal : -20 % >> faisait, et que le lot L0 a retire."""
        etat = {'etat': ELASTICITE_ESTIMEE,
                'estimation': {'elasticite': -1.23, 'ic_bas': -1.80,
                               'ic_haut': -0.66, 'voie': 'residuelle',
                               'n_lignes': 12000, 'n_resiliations': 900,
                               'reserve': "Exogeneite non demontree."}}
        t = synthese_elasticite(etat) or ''
        self.assertIn('-1.2300', t)
        self.assertIn('IC 95 %', t)
        self.assertIn('Exogeneite non demontree', t,
                      'la reserve disparait : un chiffre sans sa reserve se '
                      'lit comme une certitude')
        print("    EP-3 estimee : eps, IC 95 % et RESERVE publies ensemble")

    def test_EP_4_second_sens_aucun_etat_produit_elle_se_TAIT(self):
        """⚠️ *Un controle qui n'a rien a dire se tait.* Sans ce sens, la
        synthese crierait sur chaque run."""
        self.assertIsNone(synthese_elasticite(None))
        self.assertIsNone(synthese_elasticite({}))
        self.assertIsNone(synthese_elasticite({'etat': ''}))
        print("    EP-4 second sens : aucun etat -> None, aucune ligne publiee")

    def test_EP_5_les_TROIS_surfaces_publient_la_synthese(self):
        """⚠️⚠️ *Une source unique que personne n'appelle est du decor.*

        Assiette : les APPELS, par AST, dans les trois services signes.
        """
        attendus = {'tarif_excel.py', 'rapport_equipe_tarif.py',
                    'rapport_modeles_tarif.py'}
        vus = set()
        for nom in attendus:
            arbre = ast.parse((_SERVICES / nom).read_text(encoding='utf-8'))
            if any(isinstance(n, ast.Call)
                   and getattr(n.func, 'id', '') == 'synthese_elasticite'
                   for n in ast.walk(arbre)):
                vus.add(nom)
        self.assertEqual(
            vus, attendus,
            f"la synthese n'atteint que {sorted(vus)} : les surfaces "
            f"manquantes {sorted(attendus - vus)} partent au CAC sans elle")
        print(f"    EP-5 les {len(vus)} surfaces signees appellent la synthese")

    def test_EP_6_la_cle_a_son_LIBELLE_sinon_le_CAC_ne_voit_rien(self):
        """⛔⛔ LE PIEGE QUE LE FICHIER DECRIT LUI-MEME (`CF-9`).

        `_LABELS_SYNTHESES` est un TUPLE que le HTML et le Word iterent : une
        cle produite sans libelle est rendue NULLE PART, en silence, dans les
        formats qui partent au CAC. *Publier n'est pas afficher.*
        """
        src = (_SERVICES / 'rapport_equipe_tarif.py').read_text(
            encoding='utf-8')
        arbre = ast.parse(src)
        labels = next(
            n.value for n in ast.walk(arbre)
            if isinstance(n, ast.Assign) and n.targets
            and getattr(n.targets[0], 'id', '') == '_LABELS_SYNTHESES')
        cles = {e.elts[0].value for e in labels.elts
                if isinstance(e, ast.Tuple)}
        self.assertIn(
            'elasticite', cles,
            "la cle `elasticite` est produite mais n'a pas de libelle : elle "
            "sera calculee, relayee, publiee dans l'Excel A6 -- et rendue "
            "NULLE PART en html/word/pdf")
        print(f"    EP-6 `elasticite` a son libelle parmi les {len(cles)} "
              f"synthese(s) rendues au CAC")


if __name__ == '__main__':
    unittest.main(verbosity=2)
