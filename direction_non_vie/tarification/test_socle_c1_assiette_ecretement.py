"""Controles positifs -- `socle/C1` : l'assiette du seuil d'ecretement.

═══ ⛔⛔ LE CONSTAT, ET CE QUE LA MESURE A AJOUTE ═══

`severite.py` annoncait << quantile des couts au-dela duquel **un sinistre**
est dit GRAVE >> et ecretait le **cout TOTAL du contrat**.

Mesure du 01/09/2026 sur `data/PG_2017_CLAIMS_YEAR0.csv` -- **12 391 sinistres
versionnes, une ligne = un sinistre** -- severites REELLES, frequence balayee :

    sin./contrat   vrais graves   RATES par l'assiette << total >>
             1.1             37                                18
             4.0            101                                76
             8.0            198                               173

**A 8 sinistres par contrat, l'assiette << total >> rate 87 % des vrais
sinistres graves.** Elle n'ecrete pas les graves : elle ecrete les NOMBREUX.

═══ ⛔⛔ ET AUCUN CALCUL NE RATTRAPE CA DEPUIS LA DONNEE AU CONTRAT ═══

Le cout MOYEN par sinistre (`cout/nb`), seule forme calculable sans montants
individuels, n'attrape que **25 des 193** graves a 8 sinistres/contrat : la
moyenne DILUE le grave.

> *L'information du maximum n'est ni dans la somme, ni dans le compte.*

D'ou une SOURCE declaree au plan -- `cout_par_sinistre` -- et jamais une
reconstruction. C'est le patron deja valide quatre fois : `unite_exposition`,
`Chargements`, `identifiant_contrat`, `echeance`.

═══ ⚠️⚠️ AUCUN EURO NE BOUGE, ET C'EST EPINGLE PAR UN CHIFFRE ═══

**0 / 20 plans declarent `cout_par_sinistre`.** Sans elle, l'assiette reste le
total du contrat et les trois grandeurs publiees sont IDENTIQUES a ce qu'elles
etaient : `SC-2` les fige sur la donnee reelle versionnee -- seuil 7 390 EUR,
severite moyenne 950,95 EUR, 56 contrats ecretes. *Une phrase << aucun euro n'a
bouge >> ne vaut rien sans le chiffre qui la mesure.*

Ce qui change sans la source, c'est ce que le rapport DIT : combien de contrats
sont ecretes parce que NOMBREUX plutot que GRAVES (18 sur 56 = 32 % sur la
donnee reelle), et le seuil exprime en sinistres moyens (7,3 -- mais **26,8** a
8 sinistres/contrat : il croit avec la frequence, et c'est la mesure meme du
defaut).
"""

from __future__ import annotations

import ast
import glob
import pathlib
import unittest

import numpy as np
import pandas as pd

import core.severite as _smod
from core.plan_tarifaire import EMPREINTE_SCHEMA, PlanTarifaire
from core.severite import (
    construire_cible_severite,
    synthese_assiette_ecretement,
)

_RACINE = pathlib.Path(_smod.__file__).parents[1]
_SINISTRES = _RACINE / 'data' / 'PG_2017_CLAIMS_YEAR0.csv'
_PLANS = str(_RACINE / 'plans' / '*.yaml')

#: ⚠️ LE GOLDEN DE L'INVARIANCE. Mesure faite AVANT ce lot sur la donnee
#: versionnee : c'est ce qui prouve qu'aucun euro n'a bouge, plutot que de
#: l'affirmer. Il ne doit changer QUE si l'assiette par defaut change.
_GOLDEN_TOTAL = {'seuil': 7390.0, 'severite_moyenne': 950.95, 'n_graves': 56}


def _portefeuille_reel():
    """Les contrats reconstitues depuis la table AU SINISTRE.

    ⚠️ RGPD : rien de cette fonction ne sort d'ici, et aucun controle ne
    publie d'identifiant -- seulement des agregats.
    """
    sin = pd.read_csv(_SINISTRES)
    sin = sin[sin['claim_amount'] > 0].copy()
    sin['contrat'] = (sin['id_client'].astype(str) + '|'
                      + sin['id_vehicle'].astype(str))
    g = sin.groupby('contrat')['claim_amount']
    cout, nb = g.sum(), g.count()
    montants = [x.to_numpy(float) for _, x in g]
    expo = pd.Series(np.ones(len(cout)), index=cout.index)
    return cout, nb, expo, montants


class TestSocleC1AssietteEcretement(unittest.TestCase):
    """L'assiette du seuil : declaree, mesuree, et dite."""

    @classmethod
    def setUpClass(cls):
        cls.cout, cls.nb, cls.expo, cls.montants = _portefeuille_reel()

    # ── Le comportement decide : le seuil porte sur CHAQUE SINISTRE ─────────

    def test_SC_1_LE_TEST_QUI_FERME_le_seuil_porte_sur_chaque_sinistre(self):
        """`socle/C1` : par EXECUTION, sur les 12 391 sinistres versionnes."""
        c = construire_cible_severite(self.cout, self.nb, self.expo,
                                      couts_par_sinistre=self.montants)
        self.assertEqual(c.assiette_seuil, 'par_sinistre')
        # Le seuil est le quantile des montants INDIVIDUELS, jamais des totaux.
        tous = np.concatenate(self.montants)
        attendu = float(np.quantile(tous[tous > 0], 0.995))
        self.assertAlmostEqual(c.seuil_ecretement, attendu, places=6)
        # Et il ecrete bien SINISTRE PAR SINISTRE : le cout retenu d'un contrat
        # est la somme de ses montants plafonnes, jamais son total plafonne.
        attendu_total = float(sum(
            float(np.minimum(m, attendu).sum()) for m in self.montants))
        obtenu = float((c.severite * self.nb.to_numpy(float)[c.masque]).sum())
        self.assertAlmostEqual(obtenu, attendu_total, delta=1.0)
        # Sur cette assiette, le diagnostic n'a plus lieu d'etre.
        self.assertEqual(c.n_ecretes_par_nombre, 0)

    def test_SC_2_et_SANS_la_source_AUCUN_EURO_NE_BOUGE(self):
        """⚠️⚠️ LE CHIFFRE QUI TIENT LA PROMESSE, pas la phrase.

        Les trois grandeurs publiees quand aucune source n'est declaree --
        c'est-a-dire sur les 20 plans d'aujourd'hui.
        """
        c = construire_cible_severite(self.cout, self.nb, self.expo)
        self.assertEqual(c.assiette_seuil, 'total_contrat')
        self.assertAlmostEqual(c.seuil_ecretement, _GOLDEN_TOTAL['seuil'],
                               delta=1.0)
        self.assertAlmostEqual(float(c.severite.mean()),
                               _GOLDEN_TOTAL['severite_moyenne'], delta=0.01)
        self.assertEqual(c.n_graves, _GOLDEN_TOTAL['n_graves'])

    def test_SC_3_aucun_des_20_plans_ne_declare_la_source(self):
        """⚠️ L'autre moitie de << aucun euro >> : personne ne l'a activee."""
        plans = glob.glob(_PLANS)
        self.assertGreater(len(plans), 10, 'les plans sont introuvables')
        declarants = [pathlib.Path(f).stem
                      for f in plans
                      if PlanTarifaire.depuis_yaml(f).cout_par_sinistre]
        self.assertEqual(
            declarants, [],
            f"{declarants} declare(nt) `cout_par_sinistre` : l'assiette du "
            f"seuil y change, donc les relativites du modele de cout. Ce "
            f"n'est plus 'aucun euro' -- il faut le mesurer et le dire.")

    # ── Le diagnostic publie quand la source manque ────────────────────────

    def test_SC_4_LE_TEST_QUI_FERME_le_diagnostic_dit_le_vrai_chiffre(self):
        """`socle/C1` : combien sont ecretes parce que NOMBREUX."""
        c = construire_cible_severite(self.cout, self.nb, self.expo)
        cps = (self.cout / self.nb).to_numpy(float)
        cout = self.cout.to_numpy(float)
        attendu = int(((cout > c.seuil_ecretement)
                       & (cps <= c.seuil_ecretement)).sum())
        self.assertEqual(c.n_ecretes_par_nombre, attendu)
        self.assertGreater(
            attendu, 0,
            'la donnee versionnee ne porte aucun contrat ecrete par son '
            'NOMBRE : ce controle ne prouverait alors rien')
        # Le seuil en sinistres moyens : le chiffre le plus lisible.
        moyen = float(cps[cps > 0].mean())
        self.assertAlmostEqual(c.seuil_en_sinistres_moyens,
                               round(c.seuil_ecretement / moyen, 2), places=2)

    def test_SC_5_la_synthese_parle_et_SE_TAIT_quand_il_le_faut(self):
        """⚠️ Les deux sens : *un avertissement permanent ne se lit plus.*"""
        total = construire_cible_severite(self.cout, self.nb, self.expo)
        txt = synthese_assiette_ecretement(total)
        self.assertIsNotNone(txt)
        for attendu in ('COÛT TOTAL', 'NOMBREUX', 'cout_par_sinistre'):
            self.assertIn(attendu, txt,
                          f"la synthese ne porte pas '{attendu}' : {txt}")
        # Assiette par sinistre -> plus rien a signaler.
        par_sin = construire_cible_severite(self.cout, self.nb, self.expo,
                                            couts_par_sinistre=self.montants)
        self.assertIsNone(synthese_assiette_ecretement(par_sin))
        # Aucun contrat ecrete par son nombre -> silence aussi.
        muet = construire_cible_severite(
            pd.Series([100.0, 200.0, 300.0]), pd.Series([1.0, 1.0, 1.0]),
            pd.Series([1.0, 1.0, 1.0]))
        self.assertIsNone(synthese_assiette_ecretement(muet))

    # ── Le contrat de donnees se VERIFIE ───────────────────────────────────

    def test_SC_6_une_jointure_fausse_LEVE_au_lieu_d_ecreter_au_hasard(self):
        """⚠️⚠️ Des montants qui ne somment pas au total = jointure fausse."""
        with self.assertRaises(ValueError) as ctx:
            construire_cible_severite(
                self.cout, self.nb, self.expo,
                couts_par_sinistre=self.montants[:-1])
        self.assertIn('alignés', str(ctx.exception))
        faux = [m.copy() for m in self.montants]
        faux[0] = faux[0] * 2.0
        with self.assertRaises(ValueError) as ctx:
            construire_cible_severite(self.cout, self.nb, self.expo,
                                      couts_par_sinistre=faux)
        self.assertIn('jointure', str(ctx.exception))

    # ── Le plan : un ROLE, jamais un facteur ───────────────────────────────

    def test_SC_7_le_plan_refuse_une_declaration_fautive(self):
        """`socle/C1` : un montant de sinistre en predicteur = fuite."""
        base = {'lob': 'ctrl', 'version': '1', 'auteur': 'a',
                'exposition': 'e', 'cible_frequence': 'f', 'cible_cout': 'c',
                'facteurs': [{'nom': 'age', 'type': 'continu'}]}
        p = PlanTarifaire.depuis_dict(dict(base, cout_par_sinistre='montant'))
        self.assertEqual(p.cout_par_sinistre, 'montant')
        # ⚠️ Elle vit dans une table AU SINISTRE : jamais dans les colonnes
        # attendues du fichier des contrats.
        self.assertNotIn('montant', p.colonnes_sources())
        self.assertNotIn('montant', p.colonnes_produites())
        with self.assertRaises(TypeError):
            PlanTarifaire.depuis_dict(dict(base, cout_par_sinistre=123))
        with self.assertRaises(ValueError):
            PlanTarifaire.depuis_dict(dict(base, cout_par_sinistre='age'))

    def test_SC_8_la_declaration_est_OPPOSABLE_donc_dans_l_empreinte(self):
        """`socle/C1` : elle change l'assiette, donc ce qui est ecrete."""
        base = {'lob': 'ctrl', 'version': '1', 'auteur': 'a',
                'exposition': 'e', 'cible_frequence': 'f', 'cible_cout': 'c',
                'facteurs': [{'nom': 'age', 'type': 'continu'}]}
        sans = PlanTarifaire.depuis_dict(dict(base)).empreinte()
        avec = PlanTarifaire.depuis_dict(
            dict(base, cout_par_sinistre='montant')).empreinte()
        self.assertNotEqual(
            sans, avec,
            "declarer `cout_par_sinistre` ne bouge pas l'empreinte : deux "
            "plans qui n'ecretent pas les memes contrats porteraient la meme "
            "signature")
        self.assertGreaterEqual(
            EMPREINTE_SCHEMA, 5,
            'le champ est entre au schema 5 : le schema ne peut pas etre '
            'anterieur')

    # ── La publication : hors du log, dans le rapport ──────────────────────

    def test_SC_9_LE_TEST_QUI_FERME_l_assiette_sort_du_log(self):
        """`socle/C1` : *un `logger.info` n'est pas dans le rapport signe.*"""
        src_a3 = (_RACINE / 'direction_non_vie' / 'tarification' / 'a3_glm'
                  / 'agent.py').read_text(encoding='utf-8')
        cles = set()
        for n in ast.walk(ast.parse(src_a3)):
            if isinstance(n, ast.Dict):
                cles |= {k.value for k in n.keys
                         if isinstance(k, ast.Constant)
                         and isinstance(k.value, str)}
        self.assertIn(
            'ecretement_severite', cles,
            "A3 ne publie pas l'assiette du seuil dans son resultat : elle ne "
            "vit que dans un `logger.info`")
        src_rap = (_RACINE / 'direction_non_vie' / 'tarification' / 'services'
                   / 'rapport_modeles_tarif.py').read_text(encoding='utf-8')
        self.assertIn(
            'ecretement_severite', src_rap,
            'le rapport ne lit pas le diagnostic : il serait calcule et rendu '
            'nulle part -- la lecon de `conformite/C15`')


if __name__ == '__main__':
    unittest.main(verbosity=2)
