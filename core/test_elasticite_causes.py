"""⚠️⚠️ UNE BIBLIOTHEQUE ABSENTE SE DISAIT << LE MODELE N'A PAS CONVERGE >>.

Constats `socle/C7` et `socle/C8`, ouverts le 03/09/2026 en auditant
`core/elasticite.py` -- le dernier et le plus gros des trois modules que la
carte declarait << jamais audites >> (988 lignes).

═══ `socle/C7` -- LE MOTIF NE SUIVAIT PAS LA CAUSE ═══

`_ajuster_logit` rendait le MEME tuple `(None, None, None, False, None)` dans
QUATRE situations, dont l'absence de `statsmodels`. L'appelant publiait alors,
pour toutes :

> << L'ajustement du modele de resiliation n'a pas converge >>

Prouve par execution : `statsmodels` rendu introuvable, le rapport signe
affirmait une non-convergence du MODELE -- c'est-a-dire une chose FAUSSE sur
la donnee de l'actuaire, pour une cause qui lui est totalement etrangere.

> *Un controle qui n'a pas eu lieu le DIT ; il ne se confond pas avec un
> controle qui n'a rien trouve.* (`conformite/C1`, `qualite/C9`.)

═══ `socle/C8` -- UNE CONTRAINTE ECRITE DANS UN COMMENTAIRE ═══

`SOURCES_ADMISES` existait << pour empecher qu'une regle maison passe
silencieusement pour une obligation >> -- et RIEN ne l'appliquait : mesure,
zero usage interne, zero import. Le champ `source` portait le commentaire
<< l'un de SOURCES_ADMISES >>, et une exigence declarant `source='IFRS 17 §32'`
serait entree sans un mot.

> *Une contrainte ecrite dans un commentaire n'est pas une contrainte ; c'est
> une intention.*

C'est le motif que ce module poursuit LUI-MEME : son en-tete insiste
qu'**aucun texte reglementaire ne fixe une elasticite-prix**.
"""
from __future__ import annotations

import builtins
import unittest

import numpy as np

from core.elasticite import (
    CAUSE_AJUSTEMENT_ECHOUE,
    CAUSE_ERREUR_TYPE,
    CAUSE_NON_CONVERGENCE,
    CAUSE_OUTIL_ABSENT,
    EXIGENCES,
    MOTIF_PAR_CAUSE,
    SOURCE_CONVENTION,
    SOURCES_ADMISES,
    _ajuster_logit,
    _et,
    _exigence,
)


def _echantillon(n=400, graine=3):
    rng = np.random.default_rng(graine)
    X = np.column_stack([rng.normal(size=n)])
    p = 1 / (1 + np.exp(-(0.5 * X[:, 0] - 1)))
    return (rng.random(n) < p).astype(float), X


class _SansStatsmodels:
    """Rend `statsmodels` introuvable, et lui SEUL."""

    def __enter__(self):
        self._vrai = builtins.__import__

        def faux(nom, *a, **kw):
            if nom.startswith('statsmodels'):
                raise ImportError('simule : statsmodels absent')
            return self._vrai(nom, *a, **kw)

        builtins.__import__ = faux
        return self

    def __exit__(self, *exc):
        builtins.__import__ = self._vrai
        return False


class TestCauseDeLEchec(unittest.TestCase):

    def test_EC_1_LE_CONSTAT_outil_absent_et_non_convergence_se_DISTINGUENT(
            self):
        """⚠️⚠️ LA MESURE QUI A OUVERT `socle/C7`, DEVENUE CONTROLE."""
        y, X = _echantillon()
        ok = _ajuster_logit(y, X)
        self.assertTrue(ok[3], 'le temoin ne converge pas : il ne prouve rien')
        self.assertIsNone(ok[5], 'un succes ne porte aucune cause d echec')

        with _SansStatsmodels():
            absent = _ajuster_logit(y, X)
        self.assertFalse(absent[3])
        self.assertEqual(
            absent[5], CAUSE_OUTIL_ABSENT,
            "l'absence de `statsmodels` ne se distingue pas d'un echec "
            "d'ajustement : le rapport signe affirmerait une non-convergence "
            "du MODELE pour une cause etrangere a la donnee")
        print(f"    EC-1 avec l'outil : converge, cause=None ; sans l'outil : "
              f"cause={absent[5]!r}")

    def test_EC_2_le_MOTIF_publie_dit_que_la_donnee_n_est_PAS_en_cause(self):
        """⚠️⚠️ CE QUE L'ACTUAIRE LIT, ET C'EST TOUT L'OBJET.

        Le message de l'outil absent doit dire, sans ambiguite, que rien ne
        peut etre conclu sur SON portefeuille.
        """
        motif = MOTIF_PAR_CAUSE[CAUSE_OUTIL_ABSENT]
        for attendu in ("PAS UN DÉFAUT DE VOS", 'statsmodels',
                        'Aucune conclusion', 'Installez'):
            self.assertIn(attendu, motif,
                          f"le motif ne dit pas << {attendu} >>")
        # ⚠️ SECOND SENS : les trois autres causes, elles, parlent bien du
        # MODELE -- sinon on aurait remplace une confusion par une autre.
        for cause in (CAUSE_NON_CONVERGENCE, CAUSE_ERREUR_TYPE,
                      CAUSE_AJUSTEMENT_ECHOUE):
            m = MOTIF_PAR_CAUSE[cause]
            self.assertNotIn('statsmodels', m)
            self.assertIn('ajustement', m.lower())
        print(f"    EC-2 le motif de l'outil absent disculpe la donnee "
              f"({len(motif)} car.) ; les 3 autres parlent du modele")

    def test_EC_3_les_QUATRE_causes_ont_un_motif_et_AUCUN_ne_se_repete(self):
        """⚠️ Une table de motifs incomplete leverait `KeyError` au pire
        moment ; deux causes partageant un texte referaient la confusion que
        ce lot ferme."""
        causes = (CAUSE_OUTIL_ABSENT, CAUSE_NON_CONVERGENCE,
                  CAUSE_ERREUR_TYPE, CAUSE_AJUSTEMENT_ECHOUE)
        self.assertEqual(set(MOTIF_PAR_CAUSE), set(causes),
                         'la table des motifs et les causes ont diverge')
        textes = [MOTIF_PAR_CAUSE[c] for c in causes]
        self.assertEqual(len(set(textes)), len(causes),
                         'deux causes publient le MEME texte : la confusion '
                         'que ce lot ferme est simplement deplacee')
        print(f"    EC-3 {len(causes)} causes, {len(set(textes))} motifs "
              f"distincts, aucune sans texte")

    def test_EC_4_socle_C8_une_source_NON_ADMISE_est_REFUSEE(self):
        """⚠️⚠️ *Une contrainte ecrite dans un commentaire n'est pas une
        contrainte.* `SOURCES_ADMISES` avait zero usage : le champ `source`
        acceptait n'importe quoi, y compris une reference normative INVENTEE.
        """
        with self.assertRaises(ValueError) as capt:
            _exigence('x', 'IFRS 17 §32', 'une regle maison deguisee', _et())
        msg = str(capt.exception)
        self.assertIn('IFRS 17', msg)
        self.assertIn('CONVENTION', msg)
        # ⚠️ SECOND SENS : la source admise, elle, passe.
        ex = _exigence('conception L2', SOURCE_CONVENTION, 'legitime', _et())
        self.assertEqual(ex.source, SOURCE_CONVENTION)
        print(f"    EC-4 source normative inventee -> ValueError ; source "
              f"admise -> acceptee ({len(SOURCES_ADMISES)} admise(s))")

    def test_EC_5_TOUT_le_catalogue_passe_par_la_porte_qui_verifie(self):
        """⚠️⚠️ SANS CECI, LA PORTE EXISTERAIT SANS ETRE FRANCHIE.

        C'est la forme de `socle/C2` : un garde-fou pose que rien n'alimente.
        Assiette : les sources REELLES du catalogue charge.
        """
        self.assertTrue(EXIGENCES, 'le catalogue est vide')
        hors = {n: e.source for n, e in EXIGENCES.items()
                if e.source not in SOURCES_ADMISES}
        self.assertEqual(hors, {},
                         f'des exigences portent une source non admise : '
                         f'{hors}')
        # ⚠️⚠️ ET LE CHEMIN, PAS SEULEMENT LE RESULTAT — LE SCEAU A DU ME
        # L'APPRENDRE. Verifier que les sources SONT admises ne dit rien du
        # fait qu'elles ont ete VERIFIEES : une entree ecrite `Exigence(...)`
        # au lieu de `_exigence(...)` contourne la porte et passe, tant que
        # sa source est bonne. *Un controle qui lit l'etat final ne voit pas
        # la porte qu'on a contournee pour l'atteindre.*
        import ast
        import pathlib
        src = (pathlib.Path(__file__).with_name('elasticite.py')
               .read_text(encoding='utf-8'))
        arbre = ast.parse(src)
        catalogue = next(
            n.value for n in ast.walk(arbre)
            if isinstance(n, ast.AnnAssign)
            and getattr(n.target, 'id', '') == 'EXIGENCES')
        constructeurs = {getattr(v.func, 'id', ast.unparse(v.func))
                         for v in catalogue.values if isinstance(v, ast.Call)}
        self.assertEqual(
            constructeurs, {'_exigence'},
            f"des entrees du catalogue sont construites par {constructeurs} "
            f"au lieu de la porte `_exigence` : elles CONTOURNENT la "
            f"verification de source")
        print(f"    EC-5 les {len(EXIGENCES)} exigences portent une source "
              f"admise ET passent toutes par la porte {constructeurs}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
