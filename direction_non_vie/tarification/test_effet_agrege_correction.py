"""Controles positifs — `qualite/C3` : une correction publie son EFFET, pas son
compte de lignes.

CE QUE CE FICHIER PROUVE, ET POURQUOI C'EST UN RANG 1
─────────────────────────────────────────────────────

Le plafond a 1.0 est une hypothese d'UNITE, sur un role dont le plan declare le
ROLE et jamais l'UNITE. Sur le meme portefeuille exprime en MOIS, mesure le
30/08/2026 :

```
  exposition declaree par le client : 10 083
  exposition apres plafond a 1.0    :  1 000     -90,1 %
  prime pure : 87,88 EUR/unite  ->  886,04 EUR/unite     x 10,08
```

⚠️⚠️ ET LE MESSAGE QUI DECIDE EN DISAIT ENCORE MOINS QUE L'AUTRE. Mesure avant
ce lot, les deux etats compares :

```
  AVANT validation (BLOQUE, le moment de la decision) :
     « CONTROLE QUALITE BLOQUE — anomalie(s) [exposition_sup_1] ... »
     « exposition ('exposition') > 1 — implausible pour un contrat annuel. »
     -> ni compte de lignes, ni effet

  APRES validation :
     « 1000 ligne(s) CORRIGEE(S) : 1000x exposition_sup_1 (plafond a 1.0). »
     -> un compte de lignes, toujours aucun effet
```

*L'actuaire signait sur « implausible pour un contrat annuel » et obtenait une
prime multipliee par dix.*

═══ CE QUE LE CORRECTIF FAIT ═══

⚠️⚠️ L'EFFET SE CALCULE A LA DETECTION, JAMAIS A L'APPLICATION. Le message qui
DECIDE est celui du rapport BLOQUE, et un rapport bloque n'applique par
construction aucune correction : le mesurer a l'application l'aurait rendu
absent du seul moment ou il sert. Il se derive du MEME masque et du MEME
plafond que l'application.

⚠️ LE MECANISME EST GENERIQUE, LA PHRASE DU DENOMINATEUR NE L'EST PAS. Toute
correction de regle 2 publie son effet sur le total. Mais « ce total est un
DENOMINATEUR » est une propriete du ROLE `exposition`, pas de la regle :
l'affirmer pour une colonne dont on ne sait rien serait exactement le defaut
que cet audit poursuit.

⚠️ RGPD : un total et un pourcentage. Aucune valeur de ligne, aucun index,
aucun identifiant -- verifie par sentinelle ci-dessous.

⚠️ CE LOT NE DEPLACE AUCUN EURO, et c'est controle : le plafond garde sa valeur,
les lignes corrigees sont les memes, le dataframe propre est identique. Seul le
TEXTE change. *Le vrai correctif -- declarer l'UNITE au plan -- est un chantier
de conception, ouvert separement.*
"""

from __future__ import annotations

import logging
import unittest
import warnings

from core.qualite_donnees import (
    PLAFOND_EXPOSITION,
    EffetAgrege,
    controler_qualite,
    synthese_qualite_donnees,
)
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)


def _controler(df, validee_par=None):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return controler_qualite(df, _PLAN_AUTO,
                                     qualite_validee_par=validee_par,
                                     horodatage='2026-08-30T00:00:00')
        finally:
            logging.disable(precedent)


def _en_mois(n=1000):
    """Le MEME portefeuille, exprime en mois -- un fichier client parfaitement
    normal dont personne n'a declare l'unite."""
    df = _portefeuille_auto(n, seed=3)
    df['exposition'] = df['exposition'] * 12
    return df


class TestLeMessageQuiDECIDE(unittest.TestCase):
    """⚠️⚠️ LE CONTROLE QUI FERME — et il porte sur le rapport BLOQUE."""

    def test_LE_TEST_QUI_FERME_le_message_bloque_dit_CE_QU_ON_VALIDE(self):
        """⚠️⚠️ C'est ICI que se prend la decision, et c'est ici que l'enjeu
        manquait le plus. Le message bloque en disait MOINS que celui d'apres
        validation."""
        texte = synthese_qualite_donnees(_controler(_en_mois()))
        self.assertIn('SI VOUS VALIDEZ', texte,
                      "le message de blocage ne dit pas ce que la validation "
                      "produira")
        self.assertIn('10 083', texte, "le total AVANT n'est pas publie")
        self.assertIn('1 000', texte, "le total APRES n'est pas publie")
        self.assertIn('-90.1 %', texte, "la perte relative n'est pas publiee")
        print(f"    EA-1 le message bloque porte l'effet : "
              f"{[l.strip()[:52] for l in texte.splitlines() if 'VALIDEZ' in l]}")

    def test_il_dit_que_ce_TOTAL_est_un_DENOMINATEUR(self):
        """⚠️ Le chiffre seul ne parle pas. Ce qui rend l'enjeu lisible, c'est
        que ce total DIVISE la prime."""
        texte = synthese_qualite_donnees(_controler(_en_mois()))
        self.assertIn('DENOMINATEUR', texte)
        self.assertIn('multipliee par 10.08', texte,
                      "le facteur sur le tarif n'est pas publie")
        print("    EA-2 le message nomme le denominateur et le facteur 10.08")

    def test_le_rapport_SIGNE_porte_LA_MEME_phrase(self):
        """⚠️ Une reformulation entre les deux surfaces ferait diverger ce qui
        est validE de ce qui est tracE."""
        bloque = synthese_qualite_donnees(_controler(_en_mois()))
        signe = synthese_qualite_donnees(_controler(_en_mois(), 'Selasse Sekle'))
        commun = ("EFFET SUR LE TOTAL de « exposition » : 10 083 -> 1 000 "
                  "(-90.1 %).")
        self.assertIn(commun, bloque)
        self.assertIn(commun, signe,
                      "le rapport signe ne porte pas la phrase exacte que "
                      "l'actuaire a validee")
        print("    EA-3 la meme phrase, mot pour mot, avant et apres")

    def test_l_audit_trail_retrouve_l_effet(self):
        """⚠️ Ce qui est publie doit etre retrouvable dans la trace."""
        res = _controler(_en_mois(), 'Selasse Sekle').resume()
        eff = res['corrections'][0]['effet_agrege']
        self.assertEqual(eff['colonne'], 'exposition')
        self.assertAlmostEqual(eff['total_apres'], 1000.0, places=2)
        self.assertGreater(eff['total_avant'], 10000.0)
        print(f"    EA-4 audit_trail : {eff['total_avant']:.0f} -> "
              f"{eff['total_apres']:.0f}")


class TestSecondSens(unittest.TestCase):
    """⚠️⚠️ Un avertissement affiche TOUJOURS cesse d'etre un signal."""

    def test_un_portefeuille_ANNUEL_ne_declenche_RIEN(self):
        """⚠️ Le cas normal -- 20 plans sur 20 supposent une exposition
        annuelle -- ne doit produire aucune correction et aucun effet."""
        r = _controler(_portefeuille_auto(1000, seed=3))
        self.assertEqual([a.code for a in r.corrections], [],
                         'une correction est declenchee sur un portefeuille '
                         'annuel parfaitement normal')
        texte = synthese_qualite_donnees(r) or ''
        self.assertNotIn('EFFET SUR LE TOTAL', texte)
        print("    EA-5 second sens : portefeuille annuel -> 0 correction, "
              "aucun effet publie")

    def test_une_correction_SANS_effet_mesurable_ne_publie_pas_de_facteur(self):
        """⚠️⚠️ LA PHRASE DU DENOMINATEUR EST CONDITIONNELLE, ET C'EST MESURE.
        Une exposition a peine au-dessus de 1 sur quelques lignes corrige un
        total quasi inchange : annoncer « multipliee par 1.00 » serait du bruit
        qui affaiblit le vrai signal."""
        df = _portefeuille_auto(1000, seed=3)
        df.loc[df.index[:3], 'exposition'] = 1.001
        r = _controler(df)
        self.assertTrue(r.corrections, 'premisse : une correction doit exister')
        phrase = synthese_qualite_donnees(r) or ''
        self.assertNotIn('multipliee par', phrase,
                         'un facteur est publie alors que le total est '
                         'inchange : le signal se noie dans le bruit')
        print("    EA-6 second sens : effet negligeable -> aucun facteur publie")

    def test_le_facteur_ne_s_annonce_QUE_pour_le_role_exposition(self):
        """⚠️⚠️ Le mecanisme est generique, la phrase du denominateur non.
        Affirmer « c'est un denominateur » sur une colonne dont on ne sait rien
        serait le defaut meme que cet audit poursuit."""
        e = EffetAgrege(colonne='une_autre', total_avant=100.0, total_apres=10.0)
        from core.qualite_donnees import Anomalie, _phrase_effet_agrege
        for role, attendu in (('exposition', True), ('cible_cout', False)):
            with self.subTest(role=role):
                a = Anomalie(code='x', regle=2, role=role, colonne='une_autre',
                             nb_lignes=1, proportion=0.1, index=(0,),
                             description='', correction='', effet_agrege=e)
                self.assertEqual('DENOMINATEUR' in _phrase_effet_agrege(a),
                                 attendu)
                self.assertIn('EFFET SUR LE TOTAL', _phrase_effet_agrege(a),
                              "l'effet generique doit sortir pour TOUT role")
        print("    EA-7 second sens : l'effet est generique, le denominateur "
              "est reserve au role `exposition`")


class TestAucunEuroDeplace(unittest.TestCase):
    """⚠️⚠️ CONDITION DE LOT : ce lot ne change QUE du texte."""

    def test_le_plafond_garde_sa_valeur_et_sa_forme_publiee(self):
        self.assertEqual(PLAFOND_EXPOSITION, 1.0)
        r = _controler(_en_mois(), 'Selasse Sekle')
        self.assertEqual(r.corrections[0].correction, 'plafond a 1.0',
                         "le libelle publie a change de FORME : `:g` rendait "
                         "« plafond a 1 »")
        print(f"    EA-8 plafond = {PLAFOND_EXPOSITION}, libelle publie "
              f"« {r.corrections[0].correction} » — inchange")

    def test_le_dataframe_propre_est_IDENTIQUE_a_avant_le_lot(self):
        """⚠️ Le seuil, les lignes touchees et la valeur appliquee sont les
        memes : le plafond ramene TOUTE ligne > 1 a exactement 1.0."""
        r = _controler(_en_mois(), 'Selasse Sekle')
        dfp = r.dataframe_propre
        self.assertEqual(len(dfp), 1000)
        self.assertEqual(float(dfp['exposition'].max()), 1.0)
        self.assertEqual(float(dfp['exposition'].sum()), 1000.0)
        print(f"    EA-9 dataframe propre : {len(dfp)} lignes, exposition "
              f"totale {dfp['exposition'].sum():.0f} — le comportement est "
              f"inchange")


class TestRGPD(unittest.TestCase):
    """⚠️⚠️ NON NEGOCIABLE — un total est un agregat, pas une donnee client."""

    def test_le_message_ne_publie_NI_valeur_de_ligne_NI_identifiant(self):
        df = _en_mois()
        sentinelle = 'P2024-SECRET-0001'
        df['id_contrat'] = [f'{sentinelle}-{i}' for i in range(len(df))]
        r = _controler(df, 'Selasse Sekle')
        texte = synthese_qualite_donnees(r)
        self.assertNotIn(sentinelle, texte, 'un identifiant client sort')
        self.assertNotIn('[0,', texte, 'des index de lignes sortent')
        # une valeur de ligne, telle quelle, ne doit pas apparaitre
        val = f"{float(df['exposition'].iloc[0]):.6f}"
        self.assertNotIn(val, texte, 'une valeur de ligne sort')
        self.assertIn('exposition', texte, 'le NOM de la colonne doit sortir')
        print("    EA-10 RGPD : un total, un pourcentage, un nom de colonne — "
              "aucune valeur de ligne, aucun index, aucun identifiant")


if __name__ == '__main__':
    unittest.main()
