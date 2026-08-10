# -*- coding: utf-8 -*-
"""Tests D3 — la date d'arrêté de l'entité, typée et unique.

⚠️ GATE : `py -m unittest discover -s core -t .` — le module a rejoint
`core/` : la date d'arrêté n'est pas une notion IFRS 17.
"""
import os
import unittest
from datetime import date, datetime

from core.arrete import (
    ANNEE_MAX, ANNEE_MIN, FINS_DE_PERIODE, FORMATS, Arrete, ArreteInvalide,
    dernier_trimestre_clos, est_fin_de_periode, iso, libelle, lire,
    resume_confirmation)


class T1_LesFormatsDuDepot(unittest.TestCase):
    """T1 — les deux formats qui coexistent réellement dans le dépôt."""

    def test_les_deux_formats_rencontres_sont_lus(self):
        """'2026-07-31' et '31/12/2025' existent tous deux dans le code."""
        a = lire('2026-06-30')
        b = lire('30/06/2026')
        self.assertEqual(a.valeur, b.valeur)
        self.assertEqual(a.format_lu, 'AAAA-MM-JJ')
        self.assertEqual(b.format_lu, 'JJ/MM/AAAA')
        print(f"    OK T1 : {len(FORMATS)} formats lus, meme date "
              f"({iso(a)}), format d'origine conserve")

    def test_le_format_lu_est_conserve_pour_lever_l_ambiguite(self):
        """03/04 : le 3 avril ou le 4 mars ? Le format lu tranche."""
        a = lire('03/04/2026')
        self.assertEqual(a.valeur, date(2026, 4, 3))
        self.assertIn('JJ/MM/AAAA', resume_confirmation(a))
        print(f"    OK T1b : {a.texte_origine} lu comme {iso(a)} "
              f"(format {a.format_lu}), affiche pour confirmation")

    def test_une_date_ou_un_datetime_passent_aussi(self):
        self.assertEqual(lire(date(2026, 12, 31)).valeur, date(2026, 12, 31))
        self.assertEqual(lire(datetime(2026, 12, 31, 18, 30)).valeur,
                         date(2026, 12, 31))
        self.assertEqual(lire(lire('2026-12-31')).valeur, date(2026, 12, 31))
        print("    OK T1c : date, datetime et Arrete sont idempotents")


class T2_CeQuiEstRefuse(unittest.TestCase):
    """T2 — il n'y a pas de clôture partielle : on lève."""

    def test_un_libelle_libre_est_refuse(self):
        """⚠️ C'EST LE CŒUR DU LOT. 'Q2 2026' était la valeur la plus
        répandue dans le dépôt — un libellé qui ne se compare pas, ne
        s'ordonne pas, et ne peut pas servir de clé d'archivage."""
        with self.assertRaises(ArreteInvalide) as ctx:
            lire('Q2 2026')
        self.assertIn('ne se compare pas', str(ctx.exception))
        print("    OK T2 : « Q2 2026 » refuse, et le message dit pourquoi")

    def test_une_date_vide_ou_absente_est_refusee(self):
        """⚠️ `None` EXISTE DANS LE DEPOT : `date_arrete: str = None` chez
        A13 et EP5. Il doit dire << aucune date fournie >>, pas
        << texte indechiffrable : None >>."""
        for vide in ('', '   ', None):
            with self.assertRaises(ArreteInvalide) as ctx:
                lire(vide)
            self.assertIn('Aucune date', str(ctx.exception))
        print("    OK T2b : vide et None refuses, avec le bon message")

    def test_hors_bande_de_plausibilite(self):
        for absurde in ('1889-12-31', '2999-12-31'):
            with self.assertRaises(ArreteInvalide) as ctx:
                lire(absurde)
            self.assertIn('hors bande', str(ctx.exception))
        self.assertEqual(lire(f'{ANNEE_MIN}-12-31').valeur.year, ANNEE_MIN)
        self.assertEqual(lire(f'{ANNEE_MAX}-12-31').valeur.year, ANNEE_MAX)
        print(f"    OK T2c : bande [{ANNEE_MIN}, {ANNEE_MAX}], bornes incluses")


class T3_LeLibelleEstDerive(unittest.TestCase):
    """T3 — un libellé calculé ne peut pas contredire sa date."""

    def test_les_fins_de_trimestre_portent_leur_marque(self):
        attendu = {'2026-03-31': 'T1 2026', '2026-06-30': 'T2 2026',
                   '2026-09-30': 'T3 2026', '2026-12-31': 'T4 2026'}
        for iso_txt, lib in attendu.items():
            self.assertEqual(libelle(lire(iso_txt)), lib)
            self.assertTrue(est_fin_de_periode(lire(iso_txt)))
        self.assertEqual(len(FINS_DE_PERIODE), 4)
        print(f"    OK T3 : {len(attendu)} fins de trimestre libellees")

    def test_une_date_hors_trimestre_est_signalee_pas_refusee(self):
        """Run-off, cession de portefeuille : rare, donc signale."""
        a = lire('15/08/2026')
        self.assertFalse(est_fin_de_periode(a))
        self.assertEqual(libelle(a), '15/08/2026')
        self.assertIn("pas une fin de trimestre", resume_confirmation(a))
        print("    OK T3b : une cloture en milieu de mois passe, signalee")

    def test_le_libelle_ne_peut_pas_contredire_la_date(self):
        """Il est DERIVE : il n'existe aucun moyen de saisir l'un sans
        l'autre, donc aucun moyen de les faire diverger."""
        self.assertEqual(set(Arrete._fields),
                         {'valeur', 'format_lu', 'texte_origine'})
        self.assertNotIn('libelle', Arrete._fields)
        print("    OK T3c : aucun champ `libelle` stockable dans Arrete")


class T4_LePontVersLaCourbe(unittest.TestCase):
    """T4 — la rencontre avec la gouvernance de la courbe, sans confusion."""

    def test_iso_est_la_forme_qu_attend_la_gouvernance_de_courbe(self):
        """`age_courbe_mois` lit `date_valorisation[:10]` en '%Y-%m-%d'."""
        from core.courbe_rfr import age_courbe_mois, courbe_embarquee
        a = lire('31/12/2026')
        mois = age_courbe_mois(courbe_embarquee(), iso(a))
        self.assertIsNotNone(mois)
        self.assertGreater(mois, 0)
        print(f"    OK T4 : iso() accepte par age_courbe_mois "
              f"-> {mois:.1f} mois")

    def test_la_date_de_l_entite_n_est_pas_celle_de_la_courbe(self):
        """⚠️ COLLISION DE NOMS. `CourbeRFR.date_arrete` est l'arrete EIOPA
        auquel la courbe a ete publiee ; `Arrete` est celui auquel l'entite
        etablit ses comptes. Les confondre daterait les comptes sur le
        calendrier d'EIOPA."""
        from core.courbe_rfr import courbe_embarquee
        courbe = courbe_embarquee()
        entite = lire('2026-12-31')
        self.assertNotEqual(iso(entite), courbe.date_arrete)
        print(f"    OK T4b : courbe {courbe.date_arrete} vs entite "
              f"{iso(entite)} — deux notions, deux valeurs")




class T5_LeDefautDArrete(unittest.TestCase):
    """T5 — le dernier trimestre CLOS, une valeur par défaut qui ne suppose
    rien.

    ⚠️ ELLE VIT DANS `core`, PAS DANS L'INTERFACE. Une interface qui
    calculerait elle-même ses fins de trimestre poserait une seconde
    définition de la même notion — c'est ainsi qu'elle s'est retrouvée sous
    26 formes sur 71 sites.
    """

    def test_le_trimestre_EN_COURS_n_est_jamais_propose(self):
        """⚠️ « CLOS » VEUT DIRE ACHEVÉ. Au 31/12 le T4 court encore : un
        défaut qui le proposerait inviterait à arrêter des comptes sur une
        période inachevée."""
        for aujourd_hui, attendu in ((date(2026, 12, 31), date(2026, 9, 30)),
                                     (date(2026, 3, 31), date(2025, 12, 31)),
                                     (date(2026, 6, 30), date(2026, 3, 31))):
            with self.subTest(aujourd_hui=aujourd_hui):
                self.assertEqual(dernier_trimestre_clos(aujourd_hui), attendu)
        print("    OK T5 : le trimestre en cours n'est jamais propose")

    def test_le_passage_d_annee_recule_sur_l_annee_precedente(self):
        for aujourd_hui, attendu in ((date(2026, 1, 1), date(2025, 12, 31)),
                                     (date(2026, 1, 15), date(2025, 12, 31)),
                                     (date(2027, 1, 1), date(2026, 12, 31))):
            with self.subTest(aujourd_hui=aujourd_hui):
                self.assertEqual(dernier_trimestre_clos(aujourd_hui), attendu)
        print("    OK T5b : en janvier, le defaut est le T4 precedent")

    def test_le_defaut_est_TOUJOURS_une_fin_de_trimestre_lisible(self):
        """La boucle ferme la boucle : ce que la fonction rend doit passer par
        `lire` et sortir un libelle de periode."""
        for mois in range(1, 13):
            for jour in (1, 15, 28):
                d = dernier_trimestre_clos(date(2026, mois, jour))
                a = lire(d)
                self.assertTrue(est_fin_de_periode(a), f'{d}')
                self.assertRegex(libelle(a), r'^T[1-4] \d{4}$')
        print("    OK T5c : 36 dates testees, le defaut est toujours un "
              "trimestre")


class T6_LApplicationSaisitUneDate(unittest.TestCase):
    """T6 — l'interface ne saisit plus un libellé libre.

    ⚠️ `actuaria_app.py` VIT A LA RACINE ET AUCUNE GATE NE LE DECOUVRE — la
    regle Streamlit, qui se defend : l'interface ne se teste pas ici. Mais la
    FORME d'une valeur qui entre dans le calcul n'est pas de l'affichage.
    Le champ etait un texte (« Q2 2026 ») : ni comparable, ni ordonnable, et
    illisible pour `lire` — mesure faite, 6 saisies usuelles sur 11 etaient
    refusees, dont la valeur par defaut de l'application elle-meme.

    Ce test relit le fichier, il ne l'importe pas : `actuaria_app` execute
    Streamlit a l'import.
    """

    CHEMIN = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'actuaria_app.py')

    def _source(self):
        with open(self.CHEMIN, encoding='utf-8') as f:
            return f.read()

    def test_le_champ_d_arrete_est_une_DATE(self):
        src = self._source()
        self.assertIn('key="a7_arrete_date"', src)
        self.assertIn('st.date_input(', src)
        self.assertNotIn('key="a7_arrete"', src,
                         "le champ texte libre est revenu")
        print("    OK T6 : l'arrete se saisit comme une date")

    def test_le_libelle_est_DERIVE_et_la_date_typee_voyage(self):
        """⚠️ DEUX CHAMPS QUI DISENT LE MEME FAIT FINISSENT PAR DIVERGER. Le
        libelle descend toujours vers A7, mais CALCULE : il ne peut plus
        contredire la date qui l'accompagne."""
        src = self._source()
        self.assertIn('_libelle_arrete(', src)
        self.assertIn('"a7_arrete_iso"', src)
        self.assertIn('_arrete_core.iso(', src)
        print("    OK T6b : libelle derive, et la date ISO voyage a cote")

    def test_l_application_ne_REIMPLEMENTE_pas_la_lecture(self):
        """⚠️ CE QUI AVAIT PRODUIT 26 FORMES : chacun relit une date a sa
        facon. L'interface appelle `core.arrete`, elle ne decide rien."""
        src = self._source()
        self.assertIn('from core import arrete as _arrete_core', src)
        self.assertIn('_arrete_core.dernier_trimestre_clos()', src)
        self.assertNotIn('def _dernier_trimestre_clos', src,
                         "l'interface a repris sa propre definition")
        print("    OK T6c : l'interface enveloppe `core.arrete`, elle ne le "
              "double pas")


if __name__ == '__main__':
    unittest.main(verbosity=2)
