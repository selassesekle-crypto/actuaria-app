"""⚠️⚠️ QUATRE ALERTES PEUVENT ARRÊTER UN TARIF. LES ONZE AUTRES, JAMAIS.

Étape ⑤-① du chantier 1-B, arbitrée par Selasse le 02/09/2026 sur les chiffres
de l'étape ④ — et le chiffre qui a tranché est celui-ci :

```
  DONNEE REELLE, 12 654 contrats
    AVANT : cout_net_negatif 8,82 % >= 5 %  ->  escalade  ->  BLOQUE
    APRES : hors liste  ->  bloque = False  ->  12 654 / 12 654 lignes tarifees
```

Une charge **nette** négative est un recours, un sauvetage, une subrogation :
c'est **normal**. Elle bloquait un vrai portefeuille. *Un blocage qu'on lève
chaque semaine n'est plus un blocage, c'est une formalité.*

⚠️ LE CRITÈRE D'ADMISSION DANS LA LISTE : l'alerte établit un fait
**impossible** (pas ambigu) **et** le laisser passer fausse le tarif de façon
non détectable en aval. *Bloquer sur l'ambiguïté transfère à la machine une
décision actuarielle.*

⚠️⚠️ LE FILTRE PORTE SUR LES DEUX CRITÈRES — le type seul ET l'union. Laisser
un type hors liste entrer dans l'union le rendrait bloquant **par la bande** :
un garde-fou qu'on croit désarmé et qui tire. `LD-4` le tient.

⚠️ ET LES MESSAGES ONT ÉTÉ RÉÉCRITS POUR CELUI QUI SIGNE. L'ancien disait
« cible_frequence ('nb_sinistres') < 0 » : une colonne technique, aucun compte,
aucune conséquence, aucune consigne. *Un message que l'actuaire doit traduire
avant de décider n'est pas un message, c'est un code source.*
"""
import ast
import dataclasses
import pathlib
import re
import unittest
from unittest import mock

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire
from core.qualite_donnees import (
    CODES_DISQUALIFIANTS,
    SEUIL_ESCALADE,
    Anomalie,
    RapportQualite,
    compte_union_lignes,
    controler_qualite,
    phrase_ampleur_exclusion,
    synthese_qualite_donnees,
)

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_PLAN = PlanTarifaire.depuis_yaml(str(_RACINE / 'plans' / 'auto.yaml'))
_E, _F, _C = _PLAN.exposition, _PLAN.cible_frequence, _PLAN.cible_cout
_ID, _ECH = _PLAN.identifiant_contrat, _PLAN.echeance

_ATTENDUS = {'frequence_negative', 'exposition_non_positive',
             'doublon_identifiant', 'unite_exposition_contredite'}


def _cadre(n=1_000, seed=77):
    rng = np.random.default_rng(seed)
    nb = rng.integers(0, 3, n).astype(float)
    return pd.DataFrame({
        _E: np.ones(n), _F: nb,
        _C: np.where(nb > 0, rng.uniform(500, 5000, n).round(2), 0.0),
        'prime_acquise': (200 + np.arange(n) * 0.01).round(2)})


def _toutes(rapport):
    return ((rapport.exclusions or []) + (rapport.corrections or [])
            + (rapport.signalements or []))


def _anomalie(rapport, code):
    for a in _toutes(rapport):
        if a.code == code:
            return a
    return None


def _les_quatre():
    """Un cas par type disqualifiant, chacun a 40 % pour depasser le seuil."""
    k = 400
    d1 = _cadre()
    d1.loc[:k - 1, _F] = -1.0
    d2 = _cadre()
    d2.loc[:k - 1, _E] = 0.0
    d3 = _cadre()
    d3[_ID] = [f'P{i:05d}' for i in range(len(d3))]
    d3[_ECH] = pd.to_datetime('2024-01-01')
    d3.loc[:k - 1, _ID] = 'P99999'
    return (('frequence_negative', d1, _PLAN),
            ('exposition_non_positive', d2, _PLAN),
            ('doublon_identifiant', d3, _PLAN),
            ('unite_exposition_contredite', _cadre(),
             dataclasses.replace(_PLAN, unite_exposition='mois')))


class TestListeDisqualifiante(unittest.TestCase):

    def test_LD_1_la_liste_est_EXACTEMENT_celle_qui_a_ete_arbitree(self):
        """⚠️ Une liste qui s'allonge sans arbitrage rendrait bloquant un type
        que personne n'a jugé. *Elle se relit, elle ne se complète pas.*"""
        self.assertEqual(
            set(CODES_DISQUALIFIANTS), _ATTENDUS,
            "la liste disqualifiante a change sans arbitrage")
        print(f"    OK LD-1 {len(CODES_DISQUALIFIANTS)} types disqualifiants, "
              f"exactement les arbitres")

    def test_LD_2_les_quatre_escaladent_bien_SEULS(self):
        """⚠️ Une liste qui n'arrête rien serait du décor."""
        for code, df, plan in _les_quatre():
            rapport = controler_qualite(df.copy(), plan)
            a = _anomalie(rapport, code)
            self.assertIsNotNone(a, f'{code} ne se declenche pas')
            self.assertGreaterEqual(a.proportion, SEUIL_ESCALADE)
            self.assertTrue(
                rapport.bloque,
                f"{code} depasse le seuil et n'arrete PAS le tarif")
            self.assertIn(code, ' '.join(rapport.anomalies_au_dela_seuil))
        print("    OK LD-2 les 4 types disqualifiants arretent le tarif, "
              "chacun sous son propre nom")

    def test_LD_3_un_type_HORS_liste_n_escalade_JAMAIS_meme_a_100_pct(self):
        """⚠️⚠️ LE CHIFFRE QUI A TRANCHÉ L'ARBITRAGE.

        `cout_net_negatif` touche **8,82 %** des contrats de la seule donnée
        réelle du dépôt, et bloquait. Une charge nette négative est un recours
        légitime. Ici on le pousse à **100 %** : il ne doit toujours rien
        arrêter.
        """
        df = _cadre()
        df[_C] = -500.0
        rapport = controler_qualite(df.copy(), _PLAN)
        a = _anomalie(rapport, 'cout_net_negatif')
        self.assertIsNotNone(a)
        self.assertEqual(a.proportion, 1.0, 'le temoin ne couvre pas tout')
        self.assertFalse(
            rapport.bloque,
            "un type HORS liste arrete encore le tarif")
        self.assertIsNotNone(rapport.dataframe_propre)
        print(f"    OK LD-3 cout_net_negatif a {a.proportion:.0%} : signale, "
              f"n'arrete rien")

    def test_LD_4_un_type_hors_liste_n_entre_PAS_dans_l_union(self):
        """⚠️⚠️ SANS CECI, IL BLOQUERAIT PAR LA BANDE.

        Deux types hors liste à 4 % chacun : leur union vaut 8 %, au-dessus du
        seuil. Si l'union les comptait, ils arrêteraient le tarif sans jamais
        avoir été admis dans la liste. *Un garde-fou qu'on croit désarmé et qui
        tire est pire qu'un garde-fou absent.*
        """
        df = _cadre()
        df.loc[:39, _C] = -500.0                     # cout_net_negatif, 4 %
        df.loc[40:79, _F] = 1.5                      # frequence_non_entiere
        rapport = controler_qualite(df.copy(), _PLAN)
        vus = {a.code: a.proportion for a in _toutes(rapport)}
        self.assertIn('cout_net_negatif', vus)
        self.assertIn('frequence_non_entiere', vus)
        for code, part in vus.items():
            self.assertLess(part, SEUIL_ESCALADE,
                            f'{code} atteint le seuil SEUL : le temoin ne '
                            f'mesure plus l union')
            self.assertNotIn(code, CODES_DISQUALIFIANTS)
        self.assertFalse(
            rapport.bloque,
            "des types hors liste bloquent par leur UNION")
        print(f"    OK LD-4 {len(vus)} types hors liste, union > seuil, "
              f"aucun blocage")

    def test_LD_5_les_messages_parlent_a_un_ACTUAIRE_pas_a_un_developpeur(
            self):
        """⚠️⚠️ CE QUE SELASSE A VALIDÉ, MOT POUR MOT.

        Chaque message disqualifiant doit dire ce qui a été trouvé, sur combien
        de lignes, ce que ça signifie pour un vrai contrat, et **quoi faire**.
        Et il ne doit plus porter de jargon de modèle ni de nom de colonne
        technique.
        """
        jargon = ('offset', 'cible_frequence', 'cible_cout', 'to_numeric',
                  'coerce', 'NaN', 'dataframe', 'regle 1', 'proportion')
        for code, df, plan in _les_quatre():
            a = _anomalie(controler_qualite(df.copy(), plan,
                                            qualite_validee_par='t'), code)
            self.assertIsNotNone(a, code)
            for mot in jargon:
                self.assertNotIn(
                    mot, a.description,
                    f"{code} : le message porte encore du jargon ({mot!r})")
            self.assertIn('CE QUE VOUS DEVEZ FAIRE', a.description,
                          f'{code} : le message ne dit pas quoi faire')
            self.assertIn('CE QUI SE PASSE SI LE TARIF EST PRODUIT',
                          a.description,
                          f'{code} : le message ne dit pas la consequence')
            self.assertGreater(len(a.description), 250,
                               f'{code} : message trop court pour expliquer')
        print("    OK LD-5 les 4 messages : 0 jargon, une consequence et une "
              "consigne dans chacun")

    def test_LD_6_le_compte_de_la_phrase_se_DERIVE_du_masque(self):
        """⚠️⚠️ UN NOMBRE ÉCRIT À LA MAIN À CÔTÉ D'UN MASQUE FINIT PAR MENTIR.

        Le rapport SIGNÉ porte ce compte. S'il était retapé au site d'appel, il
        divergerait le jour où le détecteur change — et l'actuaire signerait un
        chiffre faux.
        """
        for code, df, plan in _les_quatre():
            a = _anomalie(controler_qualite(df.copy(), plan,
                                            qualite_validee_par='t'), code)
            tete = a.description.split('.')[0]
            nombres = [int(x.replace(' ', '').replace(' ', ''))
                       for x in re.findall(r'(\d[\d  ]*) (?:contrat|ligne)',
                                           tete)]
            self.assertTrue(nombres, f'{code} : aucun compte dans la phrase')
            self.assertEqual(
                nombres[0], a.nb_lignes,
                f'{code} : la phrase annonce {nombres[0]} lignes, le masque '
                f'en porte {a.nb_lignes}')
            self.assertIn(f'{a.proportion:.1%}'.replace('.', ',')
                          .replace('%', ' %'), a.description,
                          f'{code} : la proportion publiee ne suit pas le '
                          f'masque')
        print("    OK LD-6 les 4 comptes publies == nb_lignes du masque")

    def test_LD_7_RGPD_aucun_message_ne_cite_de_ligne_ni_de_valeur(self):
        """⚠️⚠️ LE PLANT RGPD DEMANDÉ PAR SELASSE.

        Le rapport signé CIRCULE. Il porte un compte et un pourcentage, jamais
        la position d'une ligne ni la valeur d'un contrat. On plante l'anomalie
        à une position reconnaissable et on vérifie qu'elle ne ressort pas.
        """
        df = _cadre()
        df.loc[777, _F] = -424242.0
        rapport = controler_qualite(df.copy(), _PLAN, qualite_validee_par='t')
        a = _anomalie(rapport, 'frequence_negative')
        self.assertIsNotNone(a)
        self.assertIn(777, a.index, "le temoin n'est pas a la position visee")
        self.assertNotIn('777', a.description,
                         'la POSITION de la ligne fuit dans le message')
        self.assertNotIn('424242', a.description,
                         'la VALEUR du contrat fuit dans le message')
        for autre in _toutes(rapport):
            self.assertNotIn('777', autre.description, autre.code)
            self.assertNotIn('424242', autre.description, autre.code)
        print("    OK LD-7 RGPD : ni la position 777 ni la valeur -424242 "
              "dans aucun message")

    def test_LD_8_second_sens_le_filtre_ne_peut_qu_ENLEVER_des_escalades(self):
        """⚠️⚠️ LE SECOND SENS, ET IL EST STRUCTUREL.

        Restreindre l'escalade à quatre types ne doit JAMAIS en créer une
        nouvelle. On le vérifie par construction : l'ensemble des types
        au-dessus du seuil publié est inclus dans l'ensemble de TOUS les types
        au-dessus du seuil.
        """
        df = _cadre()
        df.loc[:59, _F] = -1.0          # disqualifiant, 6 %
        df.loc[100:299, _C] = -500.0    # hors liste, 20 %
        rapport = controler_qualite(df.copy(), _PLAN, qualite_validee_par='t')
        tous = {a.code for a in _toutes(rapport)
                if a.proportion >= SEUIL_ESCALADE}
        publies = {c for c in rapport.anomalies_au_dela_seuil
                   if not c.startswith('union_')}
        self.assertTrue(
            publies <= tous,
            f'le filtre a AJOUTE une escalade : {publies - tous}')
        self.assertIn('cout_net_negatif', tous)
        self.assertNotIn('cout_net_negatif', publies)
        self.assertIn('frequence_negative', publies)
        print(f"    OK LD-8 {len(tous)} types au-dela du seuil, {len(publies)} "
              f"escaladent : le filtre RETIRE, il n'ajoute jamais")

    def test_LD_9_la_signature_nominative_leve_toujours_le_blocage(self):
        """⚠️ Le mécanisme construit à l'étape ③ reste la seule échappatoire, et
        elle reste TRACÉE. *Un blocage contournable en silence n'est pas un
        blocage.*"""
        df = _cadre()
        df.loc[:399, _F] = -1.0
        sans = controler_qualite(df.copy(), _PLAN)
        self.assertTrue(sans.bloque)
        self.assertIsNone(sans.dataframe_propre)
        avec = controler_qualite(df.copy(), _PLAN,
                                 qualite_validee_par='Selasse Sekle')
        self.assertFalse(avec.bloque)
        self.assertEqual(avec.validee_par, 'Selasse Sekle')
        self.assertEqual(len(avec.dataframe_propre), len(df) - 400,
                         'les lignes impossibles ne sont pas retirees')
        print(f"    OK LD-9 blocage leve par signature nominative, "
              f"{len(df)} -> {len(avec.dataframe_propre)} lignes, trace")

    def test_LD_10_le_code_technique_reste_publie_comme_ETIQUETTE(self):
        """⚠️ Le message parle à l'actuaire ; l'auditeur, lui, doit retrouver le
        code. *Chasser le jargon de la phrase ne doit pas effacer la trace.*"""
        # ⚠️⚠️ LES DEUX RÉGIMES, ET C'EST LE SCEAU QUI L'A EXIGÉ. Ma première
        # version ne regardait qu'un rapport BLOQUÉ — or l'en-tête de blocage
        # publie déjà les codes, donc retirer le code du DÉTAIL ne faisait rien
        # tomber. *Un contrôle qui n'observe qu'un régime laisse l'autre sans
        # garde.* Le rapport NON bloqué ne porte le code qu'au détail.
        from core.qualite_donnees import synthese_qualite_donnees
        bloquant = _cadre()
        bloquant.loc[:399, _F] = -1.0
        calme = _cadre()
        calme.loc[:29, _F] = -1.0          # 3 %, sous le seuil : aucun blocage
        for libelle, df, doit_bloquer in (('bloque', bloquant, True),
                                          ('non bloque', calme, False)):
            rapport = controler_qualite(df.copy(), _PLAN)
            self.assertEqual(rapport.bloque, doit_bloquer, libelle)
            texte = synthese_qualite_donnees(rapport)
            self.assertIn(
                'frequence_negative', texte,
                f"{libelle} : le code technique a disparu du rapport — "
                f"l'auditeur ne peut plus relier la phrase au controle")
            self.assertIn('Nombre de sinistres négatif', texte,
                          f'{libelle} : la phrase lisible a disparu')
        print("    OK LD-10 la phrase ET le code coexistent dans le rapport "
              "signe")


    def test_LD_11_la_question_atteint_l_actuaire_SANS_blocage(self):
        """⚠️⚠️ CE QUE LA LISTE A FAILLI EMPORTER AVEC ELLE.

        `qualite/C8` posait la question des charges négatives — recours
        légitime ou erreur de saisie ? — **dans la levée `QualiteBloquante`**,
        avec ce motif : *« le blocage est le moment où l'actuaire décide : la
        question doit y être. »* Vrai tant que `cout_net_negatif` pouvait
        bloquer. La liste le lui a retiré, et la question ne pouvait plus
        atteindre personne.

        > *Un correctif qui retire un blocage emporte tout ce que ce blocage
        > portait.*

        Elle suit désormais l'anomalie, pas le blocage.
        """
        from core.qualite_donnees import synthese_qualite_donnees
        # ⚠️ Position DISTINCTIVE, et c'est mon propre contrôle qui l'exige :
        # sa première version balayait toutes les positions de 0 à 999 et
        # trouvait « 1 » dans « 1 000 contrat(s) ». *Un contrôle RGPD qui
        # cherche un petit entier dans un texte chiffré accuse à tort.*
        df = _cadre()
        df.loc[813, _C] = -500.0
        rapport = controler_qualite(df.copy(), _PLAN)
        self.assertFalse(rapport.bloque, 'le temoin bloque : la mesure ne '
                                         'prouve plus rien')
        texte = synthese_qualite_donnees(rapport)
        self.assertIsNotNone(texte)
        self.assertIn('NE PEUT PAS TRANCHER', texte,
                      "la question n'atteint plus l'actuaire sans blocage")
        self.assertIn('CONSERVER tout', texte)
        self.assertIn('Empreinte des cas', texte)
        # ⚠️ RGPD : la question CIRCULE désormais. Elle ne doit porter aucune
        # position ni valeur de ligne — la sentinelle voisine
        # (`test_charge_nette_negative`) garde le mot, celle-ci garde le fait.
        self.assertNotIn('position', texte.lower())
        self.assertIn(813, _anomalie(rapport, 'cout_net_negatif').index)
        self.assertNotIn('813', texte, 'la POSITION de la ligne fuit')
        print("    OK LD-11 la question atteint l'actuaire SANS blocage, "
              "et sans publier une seule position")


if __name__ == '__main__':
    unittest.main(verbosity=2)


class TestUnionJamaisSomme(unittest.TestCase):
    """⛔⛔ `qualite/C18` — LE RAPPORT SIGNE ADDITIONNAIT DES COMPTES QUI SE
    RECOUPENT.

    Trouve le 02/09/2026 en fermant le point 1 (la courbe de sensibilite de
    `a2/C18`). Cinq facteurs troues a 5 % sur 4 000 contrats :

    ```
      somme publiee            : 1 000 ligne(s) EXCLUE(S)
      union reelle             :   904
      lignes vraiment retirees :   904
    ```

    > *Le rapport signe annoncait quatre-vingt-seize exclusions qui n'avaient
    > pas eu lieu -- et il ne disait nulle part que 22,6 % du portefeuille
    > venait de disparaitre.*

    ⚠️⚠️ L'ASYMETRIE ETAIT ENTRE DECIDER ET DIRE : `controler_qualite` calcule
    DEJA l'union pour trancher l'escalade (`qualite/C14`). Elle ne la
    calculait pas pour PUBLIER. *Le defaut n'etait pas dans la regle, il etait
    dans sa restitution.*

    ⚠️ Il PRE-EXISTAIT au lot des facteurs : deux anomalies de regle 1 peuvent
    toucher la meme ligne depuis toujours (frequence negative ET exposition
    nulle sur le meme contrat).
    """

    @staticmethod
    def _anos(chevauchement: bool):
        """Deux anomalies de regle 1, avec ou sans lignes communes."""
        a = Anomalie(code='a', regle=1, role='exposition', colonne='x',
                     nb_lignes=100, proportion=0.10,
                     index=tuple(range(100)), description='a')
        deb = 50 if chevauchement else 100
        b = Anomalie(code='b', regle=1, role='exposition', colonne='y',
                     nb_lignes=100, proportion=0.10,
                     index=tuple(range(deb, deb + 100)), description='b')
        return [a, b]

    def test_UN_1_l_union_remplace_la_somme_des_que_deux_lots_se_recoupent(self):
        """⚠️⚠️ *Ne jamais additionner des sources qui se recoupent.*"""
        n, part = compte_union_lignes(self._anos(chevauchement=True))
        self.assertEqual(n, 150, f'union attendue 150, obtenue {n} : la somme '
                                 f'(200) compte deux fois les lignes communes')
        self.assertAlmostEqual(part, 0.15, places=6)
        print(f"    UN-1 deux lots de 100 avec 50 communs -> {n} lignes "
              f"({part:.1%}), jamais 200")

    def test_UN_2_second_sens_sans_chevauchement_l_union_EGALE_la_somme(self):
        """⚠️ Sans ce sens, un controle qui rend toujours moins passerait pour
        bon. Deux lots DISJOINTS doivent rendre exactement la somme."""
        n, part = compte_union_lignes(self._anos(chevauchement=False))
        self.assertEqual(n, 200, "l'union ampute des lignes reellement "
                                 'distinctes')
        self.assertAlmostEqual(part, 0.20, places=6)
        print(f"    UN-2 second sens : deux lots DISJOINTS -> {n} lignes "
              f"({part:.1%}) = la somme")

    def test_UN_3_sans_index_le_repli_est_EXPLICITE_et_la_part_se_TAIT(self):
        """⚠️⚠️ *Un pourcentage qu'on ne peut pas deriver ne se publie pas.*

        Une anomalie sans `index` rend l'union incalculable : on retombe sur
        la somme -- la seule mesure disponible -- et on NE publie PAS de part,
        plutot que d'en inventer une.
        """
        muette = Anomalie(code='c', regle=1, role='exposition', colonne='z',
                          nb_lignes=40, proportion=0.04, index=(),
                          description='c')
        n, part = compte_union_lignes(self._anos(chevauchement=True) + [muette])
        self.assertEqual(n, 240, 'le repli doit rendre la SOMME')
        self.assertIsNone(part, "une part est publiee alors que l'union n'est "
                                'pas calculable')
        print(f"    UN-3 anomalie sans index -> repli sur la somme ({n}), "
              f"part = {part}")

    def test_UN_5_deux_DENOMINATEURS_differents_la_part_se_TAIT(self):
        """⛔⛔ LE CAS QUE LE SCEAU M'A FAIT AJOUTER.

        `UN-3` couvrait l'absence d'index ; il ne couvrait PAS deux anomalies
        en desaccord sur leur denominateur. Un plant rendant `0.5` au lieu de
        `None` ne tombait donc sur aucun controle.

        Ce n'est pas un cas theorique : deux anomalies calculees a des etapes
        differentes portent deux `n0` differents -- c'est exactement ce qui
        s'est produit aujourd'hui entre `_n0` et `len(df)` dans A2.

        > *Un pourcentage calcule sur deux denominateurs n'a pas de sens ; le
        > taire vaut mieux que d'en choisir un au hasard.*
        """
        a = Anomalie(code='a', regle=1, role='exposition', colonne='x',
                     nb_lignes=100, proportion=0.10,       # n0 = 1 000
                     index=tuple(range(100)), description='a')
        b = Anomalie(code='b', regle=1, role='exposition', colonne='y',
                     nb_lignes=100, proportion=0.05,       # n0 = 2 000
                     index=tuple(range(200, 300)), description='b')
        n, part = compte_union_lignes([a, b])
        self.assertEqual(n, 200, "l'union des index reste juste")
        self.assertIsNone(
            part,
            f'une part ({part}) est publiee alors que les anomalies portent '
            f'DEUX denominateurs (1 000 et 2 000) : le chiffre serait faux '
            f"pour l'une des deux")
        # ⚠️ SECOND SENS : un denominateur COMMUN redonne bien une part.
        b2 = dataclasses.replace(b, proportion=0.10)
        self.assertAlmostEqual(compte_union_lignes([a, b2])[1], 0.20, places=6)
        print(f"    UN-5 deux denominateurs -> part={part} ; un seul -> "
              f"{compte_union_lignes([a, b2])[1]:.1%}")

    def test_UN_4_le_rapport_SIGNE_porte_l_union_ET_la_part(self):
        """⚠️⚠️ LE CONTROLE QUI FERME LE CONSTAT — sur la surface signee.

        *Un compte sans son total ne dit pas l'enjeu* : << 904 lignes >> et
        << 22,6 % du portefeuille >> ne se lisent pas de la meme facon.
        """
        rapport = RapportQualite(
            lignes_initiales=1000, lignes_retenues=850,
            exclusions=self._anos(chevauchement=True), corrections=[],
            signalements=[], escalade_declenchee=False,
            anomalies_au_dela_seuil=[], seuil=0.05, validee_par=None,
            horodatage=None, bloque=False, dataframe_propre=None)
        texte = synthese_qualite_donnees(rapport) or ''
        self.assertIn('150 ligne(s) EXCLUE(S)', texte,
                      f"le rapport publie la somme au lieu de l'union : "
                      f"{texte[:90]}")
        self.assertNotIn('200 ligne(s) EXCLUE(S)', texte)
        self.assertIn('15,0 % du portefeuille', texte,
                      "la part n'est pas publiee, ou pas au format francais")
        print(f"    UN-4 rapport signe : {texte.splitlines()[0][:70]}")


class TestAmpleurDeLExclusion(unittest.TestCase):
    """⚠️⚠️ `qualite/C19` — LA PASTILLE EST AMBRE A 0,1 % COMME A 67 %.

    `qualite/C18` a fait publier la PART du portefeuille exclue. Mais le badge
    des deux Excel se declenche sur le mot << EXCLUE >>, jamais sur l'ampleur :
    *l'information etait la, la hierarchie n'y etait pas.* Un actuaire qui
    signe vite lit le meme signal aux deux extremites.

    ⛔⛔ LA GRADATION PAR LA COULEUR A ETE ECARTEE, APRES MESURE. Le badge
    ROUGE publie litteralement << Non conforme >> (`_MOT_RAG`, `services/C9`).
    Un tarif calibre sur un portefeuille reduit n'est pas *non conforme*, il
    est *reduit*.

    > *Le rendre rouge affirmerait plus que ce qu'on sait -- exactement le
    > defaut que cet audit poursuit.*

    ⚠️⚠️ ET LE REPERE N'EST PAS INVENTE, IL EST REUTILISE. `SEUIL_ESCALADE`
    est la definition que ce module s'est DEJA donnee d'une proportion qui
    exige une confirmation nominative. *Un chiffre invente pour trancher une
    question actuarielle est precisement ce que ce module a supprime quatre
    fois.*
    """

    @staticmethod
    def _rapport(n, total=4000):
        a = Anomalie(code='facteur_valeur_absente', regle=1, role='facteur',
                     colonne='age', nb_lignes=n, proportion=n / total,
                     index=tuple(range(n)), description='d')
        return RapportQualite(
            lignes_initiales=total, lignes_retenues=total - n, exclusions=[a],
            corrections=[], signalements=[], escalade_declenchee=False,
            anomalies_au_dela_seuil=[], seuil=SEUIL_ESCALADE,
            validee_par=None, horodatage=None, bloque=False,
            dataframe_propre=None)

    def test_AM_1_sous_le_repere_la_phrase_se_TAIT(self):
        """⚠️ *Un avertissement permanent est un avertissement qu'on cesse de
        lire.* A 0,1 %, il n'y a rien a hierarchiser."""
        self.assertIsNone(phrase_ampleur_exclusion(0.001))
        self.assertIsNone(phrase_ampleur_exclusion(SEUIL_ESCALADE - 1e-9))
        self.assertIsNone(phrase_ampleur_exclusion(None),
                          'une part indisponible declenche la phrase')
        texte = synthese_qualite_donnees(self._rapport(4)) or ''
        self.assertNotIn('AMPLEUR', texte)
        print("    AM-1 second sens : 0,1 % -> aucune phrase d'ampleur")

    def test_AM_2_au_dela_elle_COMPARE_a_un_repere_EXISTANT(self):
        """⚠️⚠️ *Le repere n'est pas invente, il est reutilise.*

        Assiette : la phrase doit porter le seuil REEL du module, pas un
        littéral. On le fait varier et on verifie que le texte suit.
        """
        p = phrase_ampleur_exclusion(0.226) or ''
        self.assertIn('4,5 fois', p, 'le rapport a la reference ne se derive '
                                     'pas de la part')
        self.assertIn(f"{SEUIL_ESCALADE:.0%}".replace('%', ' %'), p)
        self.assertIn('77,4 %', p, "l'assiette restante n'est pas publiee")
        # ⚠️ LE REPERE EST LU, PAS RECOPIE : on le deplace et le texte suit.
        with mock.patch('core.qualite_donnees.SEUIL_ESCALADE', 0.10):
            p2 = phrase_ampleur_exclusion(0.20) or ''
        self.assertIn('2,0 fois', p2,
                      f"le seuil a ete deplace a 10 % et le RATIO n'a pas "
                      f"suivi : il recopie un litteral. Obtenu : {p2[:80]}")
        # ⚠️⚠️ ET LE SEUIL AFFICHE AUSSI — le sceau a du me l'apprendre. Un
        # plant qui figeait `_s = '5 %'` ne tombait sur AUCUN controle : je
        # verifiais le RATIO sous le patch, et le SEUIL hors patch. *Deux
        # moities justes ne font pas un controle juste.*
        self.assertIn('10 %', p2,
                      f"le seuil AFFICHE ne suit pas son deplacement : il est "
                      f"recopie. Obtenu : {p2[:110]}")
        self.assertNotIn('seuil de 5 %', p2)
        print("    AM-2 4,5x le seuil de 5 % ; seuil deplace a 10 % -> 2,0x "
              "ET << seuil de 10 % >>")

    def test_AM_3_elle_COMPARE_et_ne_JUGE_pas(self):
        """⚠️⚠️ *Le systeme publie ce chiffre ; il ne le juge pas.*

        La decision -- a partir de quelle perte un portefeuille cesse d'etre
        tarifable -- appartient a l'actuaire signataire. La phrase doit donc
        dire que l'exigence n'a PAS ete declenchee, et rendre la question.
        """
        p = phrase_ampleur_exclusion(0.673) or ''
        self.assertIn('ne declenchent PAS', p,
                      "la phrase laisse croire qu'une exigence s'est "
                      'declenchee')
        self.assertIn('VERIFIEZ', p, "la question n'est pas rendue a "
                                     "l'actuaire")
        for interdit in ('non conforme', 'invalide', 'inacceptable', 'refuse'):
            self.assertNotIn(interdit, p.lower(),
                             f"la phrase JUGE (<< {interdit} >>) au lieu de "
                             f"comparer")
        print("    AM-3 elle compare, dit que rien ne s'est declenche, et "
              "rend la question")

    def test_AM_4_la_PASTILLE_reste_AMBRE_et_c_est_DELIBERE(self):
        """⛔⛔ LA LIMITE, EPINGLEE PLUTOT QUE TUE.

        Le badge ROUGE publie << Non conforme >>. Le passer au rouge sur une
        assiette reduite affirmerait plus que ce qu'on sait.
        """
        from core.qualite_donnees import MARQUEUR_QUALITE_NON_EXECUTEE
        texte = synthese_qualite_donnees(self._rapport(2691)) or ''
        self.assertIn('AMPLEUR', texte, 'la phrase n atteint pas la surface')
        for nom, ancre in (('tarif_excel.py', '_synth_q'),
                           ('rapport_equipe_tarif.py', '_synth_q6')):
            src = (_RACINE / 'direction_non_vie' / 'tarification' / 'services'
                   / nom).read_text(encoding='utf-8')
            expr = next((ast.unparse(n) for n in ast.walk(ast.parse(src))
                         if isinstance(n, ast.IfExp) and 'AMBRE' in
                         ast.unparse(n) and ancre in ast.unparse(n)), None)
            self.assertIsNotNone(expr, f'{nom} : badge introuvable')
            verdict = eval(expr, {}, {
                ancre: texte,
                'MARQUEUR_QUALITE_NON_EXECUTEE': MARQUEUR_QUALITE_NON_EXECUTEE})
            self.assertEqual(
                verdict, 'AMBRE',
                f"{nom} : la pastille vaut '{verdict}' sur une assiette "
                f"reduite -- ROUGE publierait << Non conforme >>, ce que le "
                f"module ne sait pas")
        print("    AM-4 67 % de perte : phrase d'ampleur PUBLIEE, pastille "
              "AMBRE (jamais << Non conforme >>)")
