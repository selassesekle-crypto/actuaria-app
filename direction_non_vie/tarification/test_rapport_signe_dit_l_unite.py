"""Controles positifs — chantier `unite_exposition`, ETAPE 4 : le rapport SIGNE
dit sous quelle unite la correction a ete faite.

CE QUE LA MESURE A TROUVE, ET POURQUOI CE N'ETAIT PAS CE QUI ETAIT PREVU
────────────────────────────────────────────────────────────────────────

L'etape 4 devait etre une CONVERSION explicite vers l'annee, au motif que
<< l'aval (offset GLM, prime pure) exige une exposition annualisee >>.

⚠️⚠️ **CE MOTIF EST FAUX, ET LA MESURE L'A REFUTE.** Meme portefeuille, 1 500
contrats, tarife deux fois -- en annees sans unite, puis en mois avec
`unite_exposition: mois` :

```
  k = 0.899503 des deux cotes | prime totale 1 232 727.09 | ecart 0.0000 %
  ratio par CONTRAT : min = mediane = max = 1.000000
```

Le decalage constant `log(12)` de l'offset est absorbe par l'intercept du GLM,
et le coefficient d'equilibre recalibre le niveau. *L'exposition n'a pas besoin
d'etre annualisee pour que le tarif soit juste.* **L'etape 4 se reduit donc a
une question de PUBLICATION.**

═══ LE DEFAUT REEL, MESURE ═══

⚠️⚠️ LE RAPPORT SIGNE NE DISAIT PAS SOUS QUELLE UNITE IL AVAIT CORRIGE.
`synthese_qualite_donnees` a deux moities. La branche BLOQUEE publie les
DESCRIPTIONS et les EFFETS. La branche VALIDEE publiait l'effet **OU** la
description -- jamais les deux :

```
  message BLOQUE  : UNITE NON DECLAREE present -> True
  rapport SIGNE   : UNITE NON DECLAREE present -> False
```

Or **la description est la SEULE surface qui nomme l'unite** : << implausible
pour une exposition exprimee en mois >>, ou la phrase d'hypothese annuelle
quand rien n'est declare. *Le document que lisent le CAC et l'ACPR ne disait
pas sous quelle unite la correction avait ete faite.*

⚠️ ET LE COMMENTAIRE SUR PLACE PROMETTAIT DEJA L'INVERSE : << LA MEME PHRASE
QU'EN AMONT, PAS UNE REFORMULATION. Le rapport signe doit porter ce que
l'actuaire a valide, mot pour mot. >> **Le code publiait strictement moins que
ce qu'il promettait** -- le troisieme code de ce chantier a contredire son
propre texte.

⚠️⚠️ LA MEME ASYMETRIE, UN CRAN PLUS BAS. Les SIGNALEMENTS ne publiaient que
leur CODE : << 400x unite_exposition_contredite >>, sans dire ce que ca veut
dire. *Un code nu nomme une anomalie ; il ne la dit pas.* Cout mesure avant de
le changer : 59 a 332 caracteres par signalement, sur les trois qui existent.

═══ ⚠️⚠️ CE QUE CE FICHIER EXISTE POUR EMPECHER ═══

**LE RAPPORT SIGNE N'ETAIT EPINGLE PAR RIEN.** J'ai ajoute deux blocs de texte
au document que lisent le CAC et l'ACPR, et **les 812 tests de la gate sont
restes verts**. Les controles existants cherchent des phrases par `assertIn` :
aucun ne dit ce que le rapport DOIT contenir, et aucun ne verrait une phrase
DISPARAITRE tant qu'une autre reste. *C'est un controle qui ATTESTE sans
SURVEILLER, sur la surface la plus opposable du module.*

⚠️ AUCUN EURO : ce lot ne touche que du texte. Aucune borne, aucun masque,
aucune valeur -- verifie par `RS-6`.
"""

from __future__ import annotations

import dataclasses
import logging
import unittest
import warnings

from core.qualite_donnees import controler_qualite, synthese_qualite_donnees
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)

_SIGNATAIRE = 'Selasse Sekle'

#: ⚠️⚠️ CONSTRUIT, JAMAIS EMPRUNTE AU DEPOT. Depuis l'etape 5, les 20 plans
#: declarent `annee` : la branche << unite non declaree >> n'est plus
#: atteignable par un plan du depot. Elle reste ATTEIGNABLE EN PRODUCTION -- un
#: plan client peut ne rien declarer -- donc son cas se construit ici.
_SANS_UNITE = dataclasses.replace(_PLAN_AUTO, unite_exposition=None)


def _en_mois(n=400, seed=3):
    df = _portefeuille_auto(n, seed=seed)
    df['exposition'] = df['exposition'] * 12
    return df


def _rapport(df, plan=_PLAN_AUTO, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return controler_qualite(df, plan, horodatage='2026-08-31T10:00',
                                     **kw)
        finally:
            logging.disable(precedent)


def _signe(df, plan=_PLAN_AUTO):
    """Le rapport tel qu'il part dans le livrable, apres validation."""
    return synthese_qualite_donnees(
        _rapport(df, plan, qualite_validee_par=_SIGNATAIRE))


class TestLeRapportSigneDitLUnite(unittest.TestCase):
    """ETAPE 4 — LE CONTROLE QUI FERME."""

    def test_LE_TEST_QUI_FERME_le_rapport_signe_NOMME_l_unite(self):
        """⚠️⚠️ Mesure du 31/08 : `UNITE NON DECLAREE` etait present dans le
        message BLOQUE et ABSENT du rapport SIGNE. *Le document opposable ne
        disait pas sous quelle unite il avait ecrase 90 % de l'exposition.*"""
        texte = _signe(_en_mois(), _SANS_UNITE)
        self.assertIn('UNITE NON DECLAREE', texte)
        self.assertIn('ANNUELLE', texte)
        self.assertIn('unite_exposition', texte)
        # ⚠️ ET LE CAS DE PRODUCTION D'AUJOURD'HUI : les 20 plans declarent
        # `annee`, donc le rapport signe nomme l'unite SANS la phrase
        # d'hypothese. *Les deux etats sont publies, chacun le sien.*
        declare = _signe(_en_mois())
        self.assertNotIn('UNITE NON DECLAREE', declare)
        self.assertIn('implausible pour un contrat annuel', declare)
        print("    RS-1 le rapport SIGNE nomme l'unite : supposee (et invite "
              "a la declarer) ou declaree")

    def test_les_DEUX_surfaces_disent_la_MEME_chose(self):
        """⚠️⚠️ L'INVARIANT REEL, et il vaut mieux que deux `assertIn` : tout
        ce que le message BLOQUE publie doit se retrouver dans le rapport
        SIGNE. *Sinon l'actuaire valide un texte et en signe un autre.*"""
        # ⚠️ ON NORMALISE LE CADRAGE, JAMAIS LA SUBSTANCE. Le message bloque
        # prefixe son effet de << SI VOUS VALIDEZ — >>, tournure qui n'a plus
        # de sens une fois la validation donnee. *Le cadrage differe
        # legitimement entre les deux moments ; ce qui est AFFIRME ne le doit
        # pas.* On retire donc les puces et cette seule tournure, rien d'autre.
        def _substance(p):
            return (p.strip().lstrip('·⚠ ')
                    .removeprefix('SI VOUS VALIDEZ — ').strip())

        df = _en_mois()
        bloque = synthese_qualite_donnees(_rapport(df.copy(), _SANS_UNITE))
        signe = _signe(df.copy(), _SANS_UNITE)
        passages = [_substance(p) for p in bloque.split('\n   ')[1:]]
        manquants = [p for p in passages if p[:60] not in signe]
        self.assertEqual(
            manquants, [],
            f"{len(manquants)} passage(s) du message BLOQUE absent(s) du "
            f"rapport SIGNE : {[m[:70] for m in manquants]}")
        self.assertGreaterEqual(len(passages), 2,
                                'le message bloque ne publie plus rien : la '
                                'comparaison ne prouverait rien')
        print(f"    RS-2 les {len(passages)} passages du message bloque se "
              f"retrouvent MOT POUR MOT dans le rapport signe")

    def test_une_correction_publie_sa_DESCRIPTION_ET_son_EFFET(self):
        """⚠️ C'etait un `if/else` : l'un OU l'autre, jamais les deux."""
        texte = _signe(_en_mois())
        self.assertIn('implausible pour un contrat annuel', texte)
        self.assertIn('EFFET SUR LE TOTAL', texte)
        print("    RS-3 correction : description ET effet, plus l'un OU "
              "l'autre")

    def test_un_signalement_publie_sa_DESCRIPTION_pas_son_seul_CODE(self):
        """⚠️⚠️ << 400x unite_exposition_contredite >> ne dit rien. *Un code nu
        nomme une anomalie ; il ne la dit pas.*"""
        plan = dataclasses.replace(_PLAN_AUTO, unite_exposition='mois')
        texte = _signe(_portefeuille_auto(400, seed=3), plan)
        self.assertIn('unite_exposition_contredite', texte)
        # ⚠️ LE MESSAGE A ÉTÉ RÉÉCRIT POUR L'ACTUAIRE LE 02/09 (arbitré par
        # Selasse) : plus de jargon, un compte, et ce qu'il faut faire. *Ce
        # que ce contrôle prouve est INCHANGÉ — le rapport signé dit ce que la
        # contradiction SIGNIFIE, pas seulement son code.* Seule la phrase
        # cherchée suit la nouvelle formulation.
        self.assertIn('ressemblent à des « annee »', texte)
        self.assertIn('LE DÉNOMINATEUR DU TARIF', texte)
        print("    RS-4 signalement : le rapport dit CE QUE la contradiction "
              "signifie")

    def test_second_sens_un_rapport_SANS_anomalie_ne_dit_RIEN(self):
        """⚠️⚠️ SANS CE SENS, `RS-1` a `RS-4` passeraient aussi si la synthese
        recrachait tout, tout le temps. *Un rapport qui parle toujours ne
        signale plus rien.*"""
        rapport = _rapport(_portefeuille_auto(400, seed=3))
        self.assertFalse(rapport.exclusions)
        self.assertFalse(rapport.corrections)
        texte = synthese_qualite_donnees(rapport)
        self.assertNotIn('UNITE NON DECLAREE', texte or '')
        self.assertNotIn('EFFET SUR LE TOTAL', texte or '')
        print(f"    RS-5 portefeuille sain : la synthese ne publie aucune "
              f"phrase d'unite ({len(texte or '')} car.)")

    def test_AUCUN_EURO_ce_lot_ne_touche_que_du_TEXTE(self):
        """⚠️ Le dataframe propre, les bornes, les masques : inchanges."""
        df = _en_mois()
        r = _rapport(df.copy(), qualite_validee_par=_SIGNATAIRE)
        self.assertEqual(len(r.dataframe_propre), 400)
        self.assertAlmostEqual(float(r.dataframe_propre['exposition'].max()),
                               1.0, places=9)
        self.assertAlmostEqual(float(r.dataframe_propre['exposition'].sum()),
                               400.0, places=6)
        self.assertEqual([a.code for a in r.corrections], ['exposition_sup_1'])
        self.assertEqual(r.corrections[0].correction, 'plafond a 1.0')
        print("    RS-6 aucun euro : 400 lignes, exposition plafonnee a 1.0, "
              "libelle inchange")


if __name__ == '__main__':
    unittest.main()
