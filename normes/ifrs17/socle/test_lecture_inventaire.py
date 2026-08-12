# -*- coding: utf-8 -*-
"""Tests D2a — le lecteur d'inventaire de contrats.

⚠️ GATE : `py -m unittest discover -s normes -t .` — voir test_contrat.py.
"""
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from normes.ifrs17.socle.contrat import EXIGENCES
from normes.ifrs17.socle.groupe import _lire_date
from normes.ifrs17.socle.lecture_inventaire import (
    MOTIF_AUCUNE_LIGNE,
    MOTIF_COLONNES_CONCURRENTES,
    MOTIF_FORMAT,
    MOTIF_SANS_DATE_EMISSION,
    MOTIF_SANS_PORTEFEUILLE,
    PAR_DECLARATION,
    PAR_SYNONYME,
    PAR_SYNONYME_AMBIGU,
    RefusLecture,
    diagnostic,
    lire,
)

#: Un inventaire réaliste : noms de colonnes tels qu'un assureur les sort.
REALISTE = {
    'POLICE':       ['P-0001', 'P-0002', 'P-0003', 'P-0004'],
    'BRANCHE':      ['RC_AUTO', 'RC_AUTO', 'MRH', 'CONSTRUCTION'],
    'DT_SOUSCRIPTION': ['2024-03-04', '2025-07-12', '2025-11-30',
                        '2026-01-15'],
    'DT_ECHEANCE':  ['2025-03-03', '2026-07-11', '2026-11-29', '2029-01-14'],
    'PRIME_HT':     [820.0, 910.5, 340.0, 12_500.0],
    'DEVISE':       ['EUR', 'EUR', 'EUR', 'EUR'],
    'CODE_AGENCE':  ['A12', 'A12', 'B07', 'C31'],
    'ZONE':         ['IDF', 'IDF', 'PACA', 'OCC'],
}


def _ecrire(dico, suffixe='.csv', sep=';', onglets=None):
    """Écrit un tableau temporaire et rend son chemin."""
    d = Path(tempfile.mkdtemp())
    chemin = d / f"inventaire{suffixe}"
    df = pd.DataFrame(dico)
    if suffixe == '.csv':
        df.to_csv(chemin, index=False, sep=sep, encoding='utf-8')
    else:
        with pd.ExcelWriter(chemin) as w:
            for nom, contenu in (onglets or {'Contrats': df}).items():
                contenu.to_excel(w, sheet_name=nom, index=False)
    return chemin


class T1_LectureRealiste(unittest.TestCase):
    """T1 — le cas qu'on montrera à un assureur."""

    def test_le_diagnostic_dit_ce_qu_il_a_compris_et_ce_qui_manque(self):
        df, r = lire(_ecrire(REALISTE))
        self.assertEqual(r.conteneur, 'CSV')
        self.assertIn('« ; »', r.detail_conteneur)
        self.assertEqual(r.nb_lignes, 4)
        self.assertEqual(r.nb_colonnes, 8)
        self.assertEqual(
            set(r.champs_lus),
            {'identifiant_contrat', 'portefeuille', 'date_emission',
             'fin_couverture', 'prime', 'devise'})
        self.assertEqual(set(r.colonnes_ignorees), {'CODE_AGENCE', 'ZONE'})
        self.assertEqual(r.granularite, 'contrat par contrat')
        self.assertEqual(list(df.columns), [c.champ for c in
                                            r.correspondances])
        texte = diagnostic(r)
        for attendu in ('INVENTAIRE LU', 'COLONNES RECONNUES',
                        'À CONFIRMER AVANT SCELLEMENT',
                        'CE QUE JE PEUX PRODUIRE',
                        'CE QUI MANQUE, ET CE QUE CELA COÛTE',
                        'NON DEMANDÉ ICI'):
            self.assertIn(attendu, texte)
        print(f"    OK T1 : {r.nb_lignes} lignes, "
              f"{len(r.champs_lus)} champs reconnus, "
              f"{len(r.colonnes_ignorees)} colonnes ignorees")

    def test_les_capacites_viennent_de_D1_et_ne_sont_pas_reinventees(self):
        """Le diagnostic cite les paragraphes de `contrat.py`, pas les siens."""
        _, r = lire(_ecrire(REALISTE))
        self.assertEqual(set(r.capacites), set(EXIGENCES))
        possibles = {n for n, ok in r.capacites.items() if ok}
        self.assertEqual(possibles, {
            'portefeuilles', 'cohortes_annuelles', 'eligibilite_paa_verifiee',
            'lrc', 'revenu', 'courbe_dans_la_monnaie'})
        self.assertIn('§22, §25', diagnostic(r))
        print(f"    OK T1b : {len(possibles)} exigences atteignables sur "
              f"{len(EXIGENCES)}, citees par leur paragraphe")

    def test_les_champs_scelles_sont_signales(self):
        """§16, §22 et §53 s'apprecient a la creation du groupe."""
        _, r = lire(_ecrire(REALISTE))
        self.assertEqual({c.champ for c in r.a_confirmer},
                         {'portefeuille', 'date_emission'})
        print(f"    OK T1c : {len(r.a_confirmer)} champs signales "
              "a confirmer avant scellement")

    def test_les_paragraphes_sortent_dans_l_ordre_de_la_norme(self):
        """Un actuaire lit §14, §22, §36… puis l'annexe B — pas l'alphabet.

        ⚠️ CE TEST GARDE UN PIÈGE RENCONTRÉ. Le tri extrayait le numéro avec
        `str.isdigit()`, qui accepte les chiffres UNICODE : '④'.isdigit()
        vaut True, mais int('④') lève — et la règle ActuarIA porte justement
        « décision produit ④ ». Trois tests sont tombés d'un coup.
        """
        d = dict(REALISTE)
        d['NB_POLICES'] = [1, 1, 1, 1]      # fait entrer §17
        _, r = lire(_ecrire(d))
        texte = diagnostic(r)
        bloc = texte.split('CE QUE JE PEUX PRODUIRE')[1].split('\n\n')[0]
        # ⚠️ Extraire le SEUL numéro de paragraphe : une extraction naïve
        # ramasserait aussi le « 17 » d'IFRS 17 et comparerait du bruit.
        numeros = [int(m.group(1))
                   for m in (re.match(r'  OK  IFRS 17 §(\d+)', l)
                             for l in bloc.splitlines()) if m]
        self.assertEqual(numeros, sorted(numeros),
                         f"paragraphes dans le desordre : {numeros}")
        self.assertIn('B126', bloc.splitlines()[-1])
        print(f"    OK T1d : paragraphes ordonnes {numeros}, annexe B en fin")


class T2_Conteneurs(unittest.TestCase):
    """T2 — CSV et Excel, et le lecteur dit ce qu'il a pris."""

    def test_csv_separateur_detecte_et_affiche(self):
        for sep, libelle in ((';', '« ; »'), (',', '« , »'),
                             ('\t', 'tabulation'), ('|', '« | »')):
            _, r = lire(_ecrire(REALISTE, sep=sep))
            self.assertEqual(r.conteneur, 'CSV')
            self.assertIn(libelle, r.detail_conteneur)
        print("    OK T2 : 4 separateurs detectes et affiches")

    def test_excel_onglet_pris_et_nomme(self):
        onglets = {'Notice': pd.DataFrame({'texte': ['bla']}),
                   'Contrats': pd.DataFrame(REALISTE)}
        chemin = _ecrire(REALISTE, suffixe='.xlsx', onglets=onglets)
        with self.assertRaises(RefusLecture) as ctx:
            lire(chemin)                       # premier onglet = Notice
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_DATE_EMISSION)
        _, r = lire(chemin, onglet='Contrats')
        self.assertEqual(r.conteneur, 'Excel')
        self.assertIn('Contrats', r.detail_conteneur)
        print("    OK T2b : onglet nomme dans le rapport ; le premier "
              "onglet n'est jamais suppose bon")


class T2bis_LesFormesDEntree(unittest.TestCase):
    """T2-bis — les formes qu'un assureur produit réellement.

    ⚠️ CINQ DE CES SIX CAS ONT ÉTÉ TROUVÉS EN FABRIQUANT DES FICHIERS, pas en
    lisant le code. Aucun ne serait apparu sur les données synthétiques du
    socle, qui sont propres, en UTF-8 et en dates ISO.
    """

    def _ecrire_texte(self, contenu, encodage='utf-8', suffixe='.csv'):
        p = Path(tempfile.mkdtemp()) / f"inv{suffixe}"
        p.write_text(contenu, encoding=encodage)
        return p

    def test_un_csv_en_cp1252_est_lu_et_l_encodage_est_dit(self):
        """⚠️ C'ETAIT UN DEFAUT, PAS UNE LACUNE : cp1252 -- l'encodage par
        defaut des systemes d'assurance francais -- produisait une TRACE DE
        PILE, pas un diagnostic. Le seul endroit du socle ou la promesse
        << jamais de refus global, toujours un diagnostic >> etait rompue."""
        p = self._ecrire_texte(
            "BRANCHE;DT_SOUSCRIPTION;DATE_ÉCHÉANCE\n"
            "RC_AUTO;2026-03-15;2027-03-14\nMRH;2026-04-02;2027-04-01\n",
            encodage='cp1252')
        _, r = lire(p)
        self.assertIn('cp1252', r.detail_conteneur)
        self.assertEqual(r.nb_lignes, 2)
        print(f"    OK T2bis : cp1252 lu, {r.detail_conteneur}")

    def test_l_encodage_est_essaye_dans_l_ordre_utf8_d_abord(self):
        """Un fichier UTF-8 se decoderait SANS ERREUR en cp1252, avec des
        accents faux. L'ordre est donc une garantie, pas une commodite.

        ⚠️ ET LA FIXTURE DOIT PORTER UN ACCENT. Mon premier test employait
        `REALISTE`, dont aucune colonne n'en a : son cp1252 est byte a byte
        identique a son utf-8, et le test ne mesurait rien.
        """
        contenu = ("BRANCHE;DT_SOUSCRIPTION;DATE_ÉCHÉANCE\n"
                   "RC_AUTO;2026-03-15;2027-03-14\n")
        _, r = lire(self._ecrire_texte(contenu, encodage='utf-8'))
        self.assertIn('utf-8', r.detail_conteneur)
        self.assertNotIn('cp1252', r.detail_conteneur)
        self.assertIn('DATE_ÉCHÉANCE', [c.colonne for c in
                                        r.correspondances])
        print("    OK T2bis-b : utf-8 essaye avant cp1252, accent conserve")

    def test_les_quatre_formes_de_date_qui_manquaient(self):
        """Compacte, annee sur 2 chiffres, mois en lettres, serie Excel."""
        for brut, attendu in (('20260315', date(2026, 3, 15)),
                              ('15/03/26', date(2026, 3, 15)),
                              ('15-mars-2026', date(2026, 3, 15)),
                              ('45731', date(2025, 3, 15)),
                              (45731, date(2025, 3, 15))):
            self.assertEqual(_lire_date(brut), attendu, f"forme {brut!r}")
        print("    OK T2bis-c : 5 formes de date supplementaires lues")

    def test_un_nombre_hors_bande_n_est_pas_lu_comme_une_date(self):
        """⚠️ Un montant ou un identifiant ne doit JAMAIS devenir une date."""
        for pas_une_date in ('999', '12345678901', 'RC_AUTO', '0'):
            self.assertIsNone(_lire_date(pas_une_date), repr(pas_une_date))
        print("    OK T2bis-d : hors bande de plausibilite, rien n'est lu")

    def test_un_titre_au_dessus_des_entetes_est_recadre(self):
        """⚠️ SEPARATEUR ET LIGNE D'EN-TETE SE RESOLVENT ENSEMBLE. Mesure : le
        renifleur de `csv` rend << , >> sur ce fichier pourtant en << ; >> --
        le titre, sans separateur, l'egare. Et sans le bon separateur, aucune
        ligne ne se decoupe en champs reconnaissables."""
        p = self._ecrire_texte(
            "Inventaire des contrats\nExtraction du 31/12/2026\n\n"
            "BRANCHE;DT_SOUSCRIPTION;PRIME_HT\n"
            "RC_AUTO;2026-03-15;820\nMRH;2026-04-02;340\n")
        _, r = lire(p)
        self.assertEqual(r.nb_lignes, 2)
        self.assertIn('« ; »', r.detail_conteneur)
        self.assertIn('en-tête à la ligne 4', r.detail_conteneur)
        print(f"    OK T2bis-e : {r.detail_conteneur[-58:]}")

    def test_une_ligne_de_total_est_ecartee_et_nommee(self):
        """Deux signaux exiges : libelle de total ET date d'emission absente."""
        p = self._ecrire_texte(
            "BRANCHE;DT_SOUSCRIPTION;PRIME_HT\nRC_AUTO;2026-03-15;820\n"
            "MRH;2026-04-02;340\nTOTAL;;1160\n")
        _, r = lire(p)
        self.assertEqual(r.nb_lignes, 2)
        self.assertEqual(r.lignes_ecartees, ('TOTAL',))
        self.assertIn('LIGNES ÉCARTÉES', diagnostic(r))
        print(f"    OK T2bis-f : {len(r.lignes_ecartees)} ligne de total "
              "ecartee, et NOMMEE")

    def test_un_portefeuille_nomme_TOTAL_avec_une_date_est_conserve(self):
        """Le second signal protege un vrai contrat du meme nom."""
        p = self._ecrire_texte(
            "BRANCHE;DT_SOUSCRIPTION\nTOTAL;2026-03-15\nMRH;2026-04-02\n")
        _, r = lire(p)
        self.assertEqual(r.nb_lignes, 2)
        self.assertEqual(r.lignes_ecartees, ())
        print("    OK T2bis-g : un contrat dont le portefeuille s'appelle "
              "TOTAL mais qui porte une date est CONSERVE")

    def test_un_xls_est_refuse_avec_la_raison(self):
        """⚠️ ANNONCER UN FORMAT QU'ON NE SAIT PAS LIRE EST PIRE QUE DE LE
        REFUSER : `.xls` exige `xlrd`, absent, et echouait sur un message
        pandas qui ne disait rien au client."""
        p = self._ecrire_texte("BRANCHE;DT_SOUSCRIPTION\nRC_AUTO;2026-03-15\n",
                               suffixe='.xls')
        with self.assertRaises(RefusLecture) as ctx:
            lire(p)
        self.assertEqual(ctx.exception.motif, MOTIF_FORMAT)
        self.assertIn('xlrd', str(ctx.exception))
        self.assertIn('.xlsx', str(ctx.exception))
        print("    OK T2bis-h : .xls refuse, avec la raison et le remede")


class T3_Mapping(unittest.TestCase):
    """T3 — synonymes par defaut, declaration en surcharge."""

    def test_declaration_prime_sur_les_synonymes(self):
        """`ZONE` n'est rien pour les synonymes ; declaree, elle devient un
        champ. Et une colonne deja reconnue peut etre redirigee."""
        _, r = lire(_ecrire(REALISTE),
                    correspondances={'ZONE': 'entite',
                                     'CODE_AGENCE': 'groupe_declare'})
        par_col = {c.colonne: (c.champ, c.par) for c in r.correspondances}
        self.assertEqual(par_col['ZONE'], ('entite', PAR_DECLARATION))
        self.assertEqual(par_col['CODE_AGENCE'],
                         ('groupe_declare', PAR_DECLARATION))
        self.assertEqual(par_col['BRANCHE'][1], PAR_SYNONYME)
        self.assertEqual(r.colonnes_ignorees, ())
        print("    OK T3 : declaration appliquee, synonymes conserves ailleurs")

    def test_declaration_vers_un_champ_inconnu_refusee(self):
        with self.assertRaises(RefusLecture) as ctx:
            lire(_ecrire(REALISTE), correspondances={'ZONE': 'departement'})
        self.assertEqual(ctx.exception.motif, MOTIF_COLONNES_CONCURRENTES)
        print("    OK T3b : une cible inconnue est refusee, pas ignoree")

    def test_synonyme_ambigu_reconnu_mais_signale(self):
        """`prime_acquise` n'est pas la prime attendue de §55 a) i)."""
        d = dict(REALISTE)
        del d['PRIME_HT']
        d['PRIMES_ACQUISES'] = [400.0, 455.0, 170.0, 6_000.0]
        _, r = lire(_ecrire(d))
        self.assertEqual([c.par for c in r.sous_reserve],
                         [PAR_SYNONYME_AMBIGU])
        self.assertIn('SOUS RÉSERVE', diagnostic(r))
        self.assertTrue(r.capacites['lrc'])
        print("    OK T3c : synonyme ambigu accepte, signale, et il "
              "debloque quand meme le LRC")

    def test_granularite_pre_agregee_detectee(self):
        d = dict(REALISTE)
        d['NB_POLICES'] = [120, 310, 45, 3]
        _, r = lire(_ecrire(d))
        self.assertIn('§17', r.granularite)
        self.assertTrue(r.capacites['granularite_declaree'])
        print(f"    OK T3d : granularite = {r.granularite}")

    def test_la_plage_d_emission_est_reconnue_et_verifie_22(self):
        """Sur la voie pre-agregee, §22 passe de DECLARE a VERIFIE."""
        d = dict(REALISTE)
        d['NB_POLICES'] = [120, 310, 45, 3]
        _, sans = lire(_ecrire(d))
        d['PREMIERE_EMISSION'] = ['2024-01-08', '2025-01-03', '2025-10-01',
                                  '2026-01-02']
        d['DERNIERE_EMISSION'] = ['2024-12-30', '2025-12-28', '2025-12-30',
                                  '2026-03-31']
        _, avec = lire(_ecrire(d))
        par_col = {c.colonne: c.champ for c in avec.correspondances}
        self.assertEqual(par_col['PREMIERE_EMISSION'], 'date_emission_min')
        self.assertEqual(par_col['DERNIERE_EMISSION'], 'date_emission_max')
        self.assertFalse(sans.capacites['amplitude_cohorte_verifiee'])
        self.assertTrue(avec.capacites['amplitude_cohorte_verifiee'])
        self.assertIn('amplitude_cohorte_verifiee', sans.hors_portee)
        self.assertNotIn('amplitude_cohorte_verifiee', avec.hors_portee)
        print("    OK T3e : plage reconnue par synonymes, §22 passe de "
              "DECLARE a VERIFIE")


class T4_LesQuatreRefus(unittest.TestCase):
    """T4 — les quatre seuls motifs, chacun sur son cas."""

    def test_refus_1_sans_date_emission(self):
        d = {k: v for k, v in REALISTE.items() if k != 'DT_SOUSCRIPTION'}
        with self.assertRaises(RefusLecture) as ctx:
            lire(_ecrire(d))
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_DATE_EMISSION)
        msg = str(ctx.exception)
        self.assertIn('§22', msg)
        self.assertIn('SOUSCRIT', msg)
        print("    OK T4-1 : refus sans date d'emission, et il dit pourquoi")

    def test_refus_1bis_le_fichier_de_sinistres_est_nomme(self):
        """L'erreur la plus probable merite un refus qui la nomme."""
        with self.assertRaises(RefusLecture) as ctx:
            lire(_ecrire({'BRANCHE': ['RC_AUTO'],
                          'ANNEE_SURVENANCE': [2024],
                          'MONTANT_PAYE': [1200.0]}))
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_DATE_EMISSION)
        self.assertIn('inventaire de SINISTRES', str(ctx.exception))
        print("    OK T4-1b : un fichier de sinistres est reconnu comme tel")

    def test_refus_2_sans_portefeuille(self):
        d = {k: v for k, v in REALISTE.items() if k != 'BRANCHE'}
        with self.assertRaises(RefusLecture) as ctx:
            lire(_ecrire(d))
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_PORTEFEUILLE)
        self.assertIn('§14', str(ctx.exception))
        print("    OK T4-2 : refus sans axe de portefeuille")

    def test_refus_3_aucune_ligne(self):
        with self.assertRaises(RefusLecture) as ctx:
            lire(_ecrire({k: [] for k in REALISTE}))
        self.assertEqual(ctx.exception.motif, MOTIF_AUCUNE_LIGNE)
        print("    OK T4-3 : refus sur un fichier sans ligne")

    def test_refus_4_deux_colonnes_pour_un_champ(self):
        d = dict(REALISTE)
        d['BRANCHE_2'] = d['BRANCHE']
        with self.assertRaises(RefusLecture) as ctx:
            lire(_ecrire(d), correspondances={'BRANCHE_2': 'portefeuille'})
        self.assertEqual(ctx.exception.motif, MOTIF_COLONNES_CONCURRENTES)
        self.assertIn('portefeuille', str(ctx.exception))
        print("    OK T4-4 : refus sur deux colonnes concurrentes")

    def test_rien_d_autre_ne_refuse(self):
        """Le fichier minimal de quatre colonnes passe, et produit."""
        _, r = lire(_ecrire({
            'BRANCHE':         ['RC_AUTO'],
            'DT_SOUSCRIPTION': ['2025-01-02'],
            'PRIME_HT':        [820.0],
            'DT_ECHEANCE':     ['2026-01-01']}))
        possibles = {n for n, ok in r.capacites.items() if ok}
        self.assertEqual(len(possibles), 5)
        print(f"    OK T4-5 : 4 colonnes -> {len(possibles)} exigences, "
              "aucun refus")


if __name__ == '__main__':
    unittest.main(verbosity=2)
