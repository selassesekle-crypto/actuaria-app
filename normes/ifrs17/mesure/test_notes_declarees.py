# -*- coding: utf-8 -*-
"""Tests N3 — les cinq informations qui se RESTITUENT, jamais ne se calculent.

⚠️ GATE : `py -m unittest discover -s normes -t .`
"""
import unittest

from normes.ifrs17.mesure.lrc_paa import RefusMesure
from normes.ifrs17.mesure.notes_declarees import (
    FORME_FOURCHETTE,
    FORME_MOYENNE_PONDEREE,
    FORMES_DU_120,
    MOTIF_COURBE_SANS_TAUX,
    MOTIF_MOYENNE_SANS_PONDERATION,
    MOTIF_NOTE_MANQUANTE,
    PONDERATION_EST_UNE_DECISION,
    PRESENCE_N_EST_PAS_OPPOSABILITE,
    fourchette,
    relever,
)

COURBE = ((1, 0.021), (2, 0.0245), (3, 0.0263), (5, 0.0288))

BASE = {
    'condition_53_69': "§53 b) — les 2 000 contrats couvrent au plus un an",
    'ajustement_valeur_temps': "oui, §56 sur les groupes a financement",
    'methode_frais_acquisition': "frais actives, §59 a) non exercee",
    'niveau_confiance': "quantile 75 %",
    'courbe': COURBE,
}


def _relever(**kw):
    return relever(**{**BASE, **kw})


class N3_LesCinqInformationsSeRestituent(unittest.TestCase):
    """⚠️ Ce module ne calcule rien — sauf la fourchette, qui ne suppose
    rien."""

    def test_les_cinq_sont_restituees(self):
        n = _relever()
        self.assertIn('§53 b)', n.condition_53_69)
        self.assertIn('§56', n.ajustement_valeur_temps)
        self.assertIn('§59 a)', n.methode_frais_acquisition)
        self.assertEqual(n.niveau_confiance, 'quantile 75 %')
        self.assertEqual(len(n.courbe), 4)
        print("    OK N3 : les 5 informations du §97 a) b) c), §119 et §120 "
              "sont restituees")

    def test_chaque_champ_manquant_est_refuse_NOMMEMENT(self):
        """⚠️ « Non vide » n'est pas « renseigné » : `A_RENSEIGNER` doit
        tomber comme le vide."""
        for champ in ('condition_53_69', 'ajustement_valeur_temps',
                      'methode_frais_acquisition', 'niveau_confiance'):
            for valeur in ('', '   ', 'A_RENSEIGNER', 'TBD'):
                with self.assertRaises(RefusMesure,
                                       msg=f'{champ}={valeur}') as e:
                    _relever(**{champ: valeur})
                self.assertIn('renseigné', str(e.exception))
        print("    OK N3b : 4 champs x 4 formes de vide -> 16 refus")

    def test_le_refus_du_97c_dit_que_c_est_une_DECISION_D_ENTITE(self):
        """⚠️ §59 a) n'est pas bâti : la plateforme ne peut que recevoir."""
        with self.assertRaises(RefusMesure) as e:
            _relever(methode_frais_acquisition='')
        self.assertIn("DÉCISION DE L'ENTITÉ", str(e.exception))
        self.assertIn('§59 a)', str(e.exception))

    def test_le_119_admet_une_AUTRE_technique_et_le_refus_le_dit(self):
        """⚠️ §119 : « si elle a appliqué une technique autre que celle du
        niveau de confiance, elle doit indiquer la technique appliquée ET le
        niveau de confiance auquel son résultat correspond »."""
        n = _relever(niveau_confiance="cout du capital, equivalent 78 %")
        self.assertIn('cout du capital', n.niveau_confiance)
        with self.assertRaises(RefusMesure) as e:
            _relever(niveau_confiance='')
        self.assertIn('autre technique', str(e.exception))


class N3b_LePiegeDu120(unittest.TestCase):
    """⚠️⚠️ UNE MOYENNE PONDÉRÉE DE COURBE EST UNE DÉCISION, PAS UN CALCUL.

    §120 admet « des moyennes pondérées ou des fourchettes » sans dire par
    quoi pondérer. C'est le piège de B73, où la pondération d'une date
    d'émission valait de 3 à 9 jours d'écart.
    """

    def test_la_FOURCHETTE_est_calculee_car_elle_ne_suppose_rien(self):
        self.assertEqual(fourchette(COURBE), (0.021, 0.0288))
        self.assertIn('[2.1000% ; 2.8800%]', _relever().motif)
        print("    OK N3c : la fourchette se lit -- min 2,10 %, max 2,88 %")

    def test_la_MOYENNE_PONDEREE_se_RECOIT_et_exige_sa_ponderation(self):
        with self.assertRaises(RefusMesure) as e:
            _relever(forme_du_120=FORME_MOYENNE_PONDEREE,
                     moyenne_ponderee_declaree='2,55 %')
        self.assertEqual(e.exception.motif, MOTIF_MOYENNE_SANS_PONDERATION)
        self.assertIn('B73', str(e.exception))
        n = _relever(forme_du_120=FORME_MOYENNE_PONDEREE,
                     moyenne_ponderee_declaree='2,55 %',
                     ponderation_du_120='par les flux d execution')
        self.assertEqual(n.ponderation_du_120, 'par les flux d execution')
        print("    OK N3d : la moyenne ponderee se RECOIT, avec sa "
              "ponderation -- jamais calculee")

    def test_la_moyenne_annoncee_SANS_valeur_est_refusee(self):
        with self.assertRaises(RefusMesure) as e:
            _relever(forme_du_120=FORME_MOYENNE_PONDEREE,
                     ponderation_du_120='par les primes')
        self.assertEqual(e.exception.motif, MOTIF_NOTE_MANQUANTE)

    def test_LE_DEFAUT_est_la_FOURCHETTE_celle_qui_ne_suppose_RIEN(self):
        """⚠️⚠️ UN DÉFAUT EST UNE DÉCISION SILENCIEUSE, ET CELLE-CI PENCHE DU
        BON CÔTÉ. Des deux formes que §120 admet, la fourchette se LIT sur
        les taux ; la moyenne pondérée se DÉCIDE. Un appelant qui ne dit rien
        obtient donc celle qui n'affirme rien — et non celle qui suppose une
        pondération qu'il n'a pas choisie."""
        self.assertEqual(_relever().forme_du_120, FORME_FOURCHETTE)
        self.assertEqual(_relever().ponderation_du_120, '')
        print("    OK N3e : le defaut du §120 est la FOURCHETTE -- la forme "
              "qui ne suppose rien")

    def test_la_FORME_du_120_se_declare_et_ne_se_devine_pas(self):
        with self.assertRaises(RefusMesure) as e:
            _relever(forme_du_120='')
        self.assertEqual(e.exception.motif, MOTIF_NOTE_MANQUANTE)
        self.assertIn('ne disent pas la même chose', str(e.exception))
        self.assertEqual(len(FORMES_DU_120), 2)

    def test_une_courbe_VIDE_est_refusee(self):
        with self.assertRaises(RefusMesure) as e:
            _relever(courbe=())
        self.assertEqual(e.exception.motif, MOTIF_COURBE_SANS_TAUX)
        self.assertIn('Ran 0 tests', str(e.exception))

    def test_le_piege_descend_avec_CHAQUE_resultat(self):
        """⚠️ Une leçon qui ne descend qu'en cas d'échec se fait oublier en
        cas de succès."""
        self.assertIn(PONDERATION_EST_UNE_DECISION, _relever().motif)
        self.assertIn('B73', _relever().motif)


class N3c_CeQueLaPresenceNEtablitPas(unittest.TestCase):
    """⚠️ UN RELEVÉ QUI NE DIT PAS SA PORTÉE SE FAIT SURÉVALUER."""

    def test_le_motif_dit_que_la_presence_n_est_PAS_l_opposabilite(self):
        m = _relever().motif
        self.assertIn(PRESENCE_N_EST_PAS_OPPOSABILITE, m)
        self.assertIn('JAMAIS LEUR VALEUR', m)
        self.assertIn('déclarations de démonstration', m)

    def test_ce_module_ne_REEVALUE_pas_la_condition_du_53(self):
        """⚠️ Le socle la SCELLE à la naissance du groupe. La recalculer ici
        en produirait une seconde version, qui divergerait — le motif des
        huit sources de taux."""
        import ast
        import inspect

        from normes.ifrs17.mesure import notes_declarees
        arbre = ast.parse(inspect.getsource(notes_declarees))
        modules = {(n.module or '') for n in ast.walk(arbre)
                   if isinstance(n, ast.ImportFrom)}
        self.assertTrue(all('socle' not in m for m in modules), modules)
        noms = {n.id for n in ast.walk(arbre) if isinstance(n, ast.Name)}
        self.assertNotIn('deriver', noms)
        self.assertNotIn('eligibilite', noms)
        print("    OK N3z : aucune reevaluation -- le verdict du §53 est "
              "restitue, jamais refait")


if __name__ == '__main__':
    unittest.main(verbosity=2)
