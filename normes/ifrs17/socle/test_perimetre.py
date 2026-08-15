# -*- coding: utf-8 -*-
"""Tests X1 — le périmètre publié, et ses contrôles de non-applicabilité.

⚠️ GATE : `py -m unittest discover -s normes -t .` — voir test_contrat.py.
"""
import re
import unittest

from normes.ifrs17.socle.contrat import EXIGENCES, SOURCE_IFRS17
from normes.ifrs17.socle.perimetre import (
    BATI,
    BATI_N_EST_PAS_OPPOSABLE,
    CONTROLES,
    COUVERT,
    ETATS,
    HORS_PERIMETRE,
    NON_CONSTRUIT,
    OPPOSABILITES,
    PERIMETRE,
    SOUS_RESERVE,
    Element,
    elements,
    mention_directions,
    signaler,
    texte,
)


def _paragraphes(reference):
    """Les numéros de paragraphe cités par une référence."""
    return {('B' + b) if b else n
            for n, b in re.findall(r'§?(\d+)|B(\d+)', reference)}


class T0_LeQuatriemeEtatEtSonVERROU(unittest.TestCase):
    """⚠️⚠️ `NON_CONSTRUIT` DISAIT DEUX CHOSES OPPOSÉES, ET C'ÉTAIT MESURÉ :
    « rien n'existe » (§93-132) et « 20 modules, 5 182 lignes, 378 tests avec
    des manques nommés » (§33-37, §55-59, §60-70A, §78-92). Un client ne
    pouvait pas les distinguer — et le préambule du même document
    revendiquait ces quatre pans.

    ⚠️ LE VERROU EST LE CŒUR DE CE LOT. Corriger les états d'aujourd'hui sans
    empêcher ceux de demain aurait laissé la dérive se reformer : c'est la
    leçon du lot précédent — une exclusion que personne ne contrôle est une
    intention.
    """

    def test_UN_PAN_NON_CONSTRUIT_NE_PEUT_PAS_PORTER_DE_MODULES(self):
        """⚠️⚠️ LE VERROU. `mesure.PARAGRAPHE_DES_MODULES` est le registre
        que les modules tiennent d'eux-mêmes. Un pan qui y figure a du code ;
        le déclarer « rien n'existe encore » est faux, et c'est exactement ce
        qui s'était produit sur quatre pans.

        ⚠️ Il est placé DANS LE SOCLE, qui publie le périmètre : c'est à
        celui qui AFFIRME de crier quand son affirmation cesse d'être vraie.
        """
        from normes.ifrs17.mesure import PARAGRAPHE_DES_MODULES
        avec_code = set(PARAGRAPHE_DES_MODULES.values())
        fautifs = [e.reference for e in elements(NON_CONSTRUIT)
                   if e.reference in avec_code]
        self.assertEqual(
            fautifs, [],
            f"{len(fautifs)} pan(s) déclarés NON_CONSTRUIT portent pourtant "
            f"des modules au registre de la mesure : {fautifs}. Un pan qui a "
            f"du code n'est pas « rien n'existe encore » — il est BATI, et sa "
            f"raison dit ce qui lui manque à l'intérieur.")
        print(f"    OK T0 : {len(elements(NON_CONSTRUIT))} pans NON_CONSTRUIT, "
              "aucun ne porte de module")

    def test_UN_PAN_BATI_DOIT_PORTER_DES_MODULES(self):
        """⚠️ LE VERROU DANS L'AUTRE SENS, et il compte autant. Déclarer
        « bâti » un pan sans code serait la sur-affirmation symétrique — la
        faute que le préambule commettait."""
        from normes.ifrs17.mesure import PARAGRAPHE_DES_MODULES
        avec_code = set(PARAGRAPHE_DES_MODULES.values())
        fautifs = [e.reference for e in elements(BATI)
                   if e.reference not in avec_code]
        self.assertEqual(
            fautifs, [],
            f"{len(fautifs)} pan(s) déclarés BATI ne portent AUCUN module : "
            f"{fautifs}. « Bâti » se prouve par du code, pas par une "
            f"étiquette.")
        print(f"    OK T0b : {len(elements(BATI))} pans BATI, tous adosses a "
              "des modules du registre")

    def test_tout_pan_BATI_declare_son_OPPOSABILITE(self):
        """⚠️ BÂTI N'EST PAS OPPOSABLE. Un pan bâti dont l'opposabilité n'est
        pas dite se ferait lire comme opposable — la sur-affirmation par
        omission."""
        for e in elements(BATI):
            self.assertIn(e.opposabilite, OPPOSABILITES, e.reference)
            if e.opposabilite == SOUS_RESERVE:
                self.assertTrue(
                    e.reserve.strip(),
                    f"{e.reference} réserve son opposabilité sans dire "
                    f"pourquoi — une réserve sans motif est une omission "
                    f"déguisée, comme une exclusion sans raison")

    def test_le_defaut_d_opposabilite_est_VIDE_et_non_SANS_OBJET(self):
        """⚠️ UN DÉFAUT QUI VAUT UNE RÉPONSE VALIDE ferait passer un champ non
        renseigné pour une décision. « Non vide n'est pas renseigné », et le
        dépôt l'a déjà payé une fois."""
        self.assertEqual(Element('x', COUVERT, 'y').opposabilite, '')
        self.assertNotIn('', OPPOSABILITES)


class T1_LesQuatreEtats(unittest.TestCase):
    """T1 — confondre deux états trompe, quel que soit le couple."""

    def test_quatre_etats_et_pas_trois(self):
        """⚠️ CE TEST EXIGEAIT TROIS ÉTATS, ET IL AVAIT RAISON QUAND IL A ÉTÉ
        ÉCRIT. Le même argument — « confondre tromperait dans les deux
        sens » — en a exigé un quatrième dès que des pans ont été bâtis avec
        des manques nommés."""
        self.assertEqual(set(ETATS), {COUVERT, BATI, HORS_PERIMETRE,
                                      NON_CONSTRUIT})
        for etat in ETATS:
            self.assertTrue(elements(etat), f"état {etat} vide")
        detail = ' · '.join(f'{e} {len(elements(e))}' for e in ETATS)
        print(f"    OK T1 : {detail}")

    def test_une_exclusion_sans_raison_est_une_omission_deguisee(self):
        for e in PERIMETRE:
            if e.etat != COUVERT:
                self.assertTrue(e.raison.strip(),
                                f"{e.reference} ({e.etat}) sans raison")
        n = sum(1 for e in PERIMETRE if e.etat != COUVERT)
        print(f"    OK T1b : les {n} elements non couverts portent tous "
              f"leur raison")

    def test_aucun_etat_hors_vocabulaire(self):
        for e in PERIMETRE:
            self.assertIn(e.etat, ETATS, e.reference)
        with self.assertRaises(KeyError):
            elements('INVENTE')
        print(f"    OK T1c : {len(PERIMETRE)} elements, etats tous connus")


class T2_LePerimetreNeRevendiquePasPlusQueLeSocle(unittest.TestCase):
    """T2 — l'anti-dérive : la promesse ne peut pas dépasser le code."""

    def test_chaque_element_couvert_est_nomme_par_contrat_py(self):
        """⚠️ SANS CE VERROU, LA PROMESSE COMMERCIALE DERIVERAIT DU CODE.

        C'est le sens meme de ce module : un perimetre qui revendique une
        exigence que le socle ne nomme pas est un perimetre qui ment.
        """
        connus = set()
        for e in EXIGENCES.values():
            if e.source == SOURCE_IFRS17:
                connus |= _paragraphes(e.reference)
        for element in elements(COUVERT):
            cites = _paragraphes(element.reference)
            self.assertTrue(
                cites & connus,
                f"« {element.reference} » est declare COUVERT mais aucun de "
                f"ses paragraphes n'est nomme dans contrat.EXIGENCES")
        print(f"    OK T2 : les {len(elements(COUVERT))} elements couverts "
              f"sont adosses aux {len(EXIGENCES)} exigences du socle")

    def test_ce_qui_est_BATI_n_est_pas_pour_autant_declare_couvert(self):
        """⚠️ CE TEST DISAIT « la mesure PAA, la réassurance et la
        présentation NE SONT PAS COUVERTES », et il avait raison. Il en
        tirait qu'elles étaient NON_CONSTRUITES, et c'était la faute inverse
        — mesuré : 18 modules, 3 913 lignes, 279 tests sur ces trois pans.

        ⚠️ SA GARDE SURVIT INTACTE : `BATI` n'est pas `COUVERT`. Le premier
        dit qu'un mécanisme existe, le second qu'il est adossé aux exigences
        que `contrat.EXIGENCES` nomme. Les confondre serait la
        sur-affirmation que ce test existe pour empêcher.
        """
        batis = ' '.join(e.reference for e in elements(BATI))
        for attendu in ('§55-59', '§60-70A', '§78-92', '§33-37'):
            self.assertIn(attendu, batis)
        non_construits = ' '.join(e.reference for e in
                                  elements(NON_CONSTRUIT))
        self.assertIn('§93-132', non_construits)
        couverts = ' '.join(e.reference for e in elements(COUVERT))
        for interdit in ('§55', '§60', '§80', '§100', '§130'):
            self.assertNotIn(interdit, couverts)
        print("    OK T2b : mesure, reassurance et presentation sont BATIES "
              "-- jamais annoncees COUVERTES, les annexes restent non "
              "construites")


class T3_LesExclusionsQueLeTexteImpose(unittest.TestCase):
    """T3 — le relevé, et ce qu'il a ajouté à ma propre liste."""

    def test_le_test_du_champ_d_application_est_declare_non_fait(self):
        """⚠️ TROUVE EN RELISANT LE TEXTE, ABSENT DE MA LISTE INITIALE. La
        plateforme ne verifie JAMAIS qu'un contrat qu'on lui remet EST un
        contrat d'assurance (§3, §7, §8A, appendice A, B2-B30)."""
        champ = [e for e in PERIMETRE if '§3,' in e.reference]
        self.assertEqual(len(champ), 1)
        self.assertEqual(champ[0].etat, HORS_PERIMETRE)
        self.assertIn('ne vérifie pas', champ[0].libelle)
        self.assertIn('§8A', champ[0].raison)
        print("    OK T3 : le test du champ d'application est declare "
              "NON FAIT, avec sa raison")

    def test_les_trois_exclusions_du_cahier_des_charges(self):
        hors = {e.reference: e for e in elements(HORS_PERIMETRE)}
        self.assertIn('§32, §38-52', hors)                  # modèle général
        self.assertIn('annexe C', hors)                     # transition
        self.assertIn('B72 b) à e), B73', hors)             # révision B73
        b73 = hors['B72 b) à e), B73'].raison
        # ⚠️ « §53 a) » ET NON « §53 b) » : l'argument de B72 s'appuyait sur
        # la porte (b) fermee pour conclure qu'aucun cas §56 ne survient.
        # Premisse refutee — voir test_B72_n_ecarte_plus_le_taux ci-dessous.
        for mesure in ('cinq usages', 'ABSENTE en PAA', '§56', '§53 a)'):
            self.assertIn(mesure, b73)
        print("    OK T3b : les 3 exclusions portent leur raison mesuree")

    def test_le_texte_publie_ne_promet_pas_un_blocage_qu_il_ne_fait_pas(self):
        """⚠️ PROMETTRE UN BLOCAGE QU'ON NE FAIT PAS EST PIRE QUE DE NE RIEN
        PROMETTRE : le lecteur cesse de surveiller.

        Le texte publie affirmait que les contrats hors perimetre << ne sont
        jamais mesures a tort >>. Or `signaler()` rend des alertes et NE LEVE
        JAMAIS -- voir `test_signaler_ne_refuse_jamais`, qui disait deja la
        verite pendant que le texte la contredisait.
        """
        publie = texte()
        self.assertNotIn('jamais', publie.split('SIGNALÉS')[-1][:220])
        self.assertIn('NE', publie)
        self.assertIn('BLOQUE PAS LA MESURE', publie)
        self.assertIn('actuaire signataire', publie)
        print("    OK T3f : le texte publie dit que le signalement ne bloque "
              "pas — il ne promet plus un refus qu'il ne fait pas")

    def test_le_perimetre_dit_CE_QUI_EST_BATI_dans_la_mesure(self):
        """⚠️ LE PERIMETRE A DEJA VIEILLI DEUX FOIS, ET TOUJOURS DE MON FAIT.

        Chaque lot de construction rend une raison fausse : elle continue de
        dire << reste a batir >> quand le module existe. C'est la faute
        corrigee en C4-0 (le par. 78-92 disait << aucun n'est encore
        produit >>), et elle est revenue des que F1 et F2 ont ete pousses.

        Ce test ne la previent pas -- il la CONSTATE sur ce qui est bati
        aujourd'hui. Le verrou mecanique qui l'empecherait de revenir est
        propose, non ouvert : il exigerait un registre module -> paragraphe
        que le gate ferait respecter.
        """
        refs = {e.reference: e for e in PERIMETRE}
        mesure = refs['§55-59, B125-B126'].raison
        for bati in ('§55 a) et b)', '§56', '§57 et §58', 'B125-B126'):
            self.assertIn(bati, mesure, bati)
        self.assertIn('BÂTIS', mesure)
        self.assertNotIn('la mesure elle-même reste à bâtir', mesure)
        # ⚠️ QUATRIEME MORSURE DE CE TEST, QUATRIEME FOIS QU'IL A RAISON. Le
        # par. 59 b) est bati depuis L1 ; il ne reste que le par. 59 a), qui
        # est une OPTION de l'entite et non une regle. Les assertions suivent
        # l'etat, elles ne retablissent pas les mots d'avant.
        self.assertIn('§59 b), le passif au titre des sinistres survenus — '
                      'BÂTI', mesure)
        self.assertIn('RESTE NON BÂTI', mesure)
        self.assertIn('§59 a)', mesure)
        # ⚠️ et la reserve qui rend ce pan NON OPPOSABLE doit y figurer
        self.assertIn('CADENCES INVENTÉES', mesure)
        self.assertIn("N'EST OPPOSABLE", mesure)
        flux = refs['§33-37, B36-B92'].raison
        self.assertIn('SQUELETTE', flux)
        self.assertIn('AUCUNE source externe', flux)
        self.assertIn('flux RÉELS', flux)
        print("    OK T3i : le perimetre dit ce qui est bati (§55-58, §56, "
              "B125) et ce qui ne l'est pas (§59 a) et b))")

    def test_le_92_a_son_PROPRE_element_et_nomme_IAS_21(self):
        """⚠️⚠️ IL ETAIT AVALE PAR L'INTITULE DE PLAGE << §78-92 >>.

        Ni le libelle ni la raison de la plage ne mentionnaient les ecarts
        de change, IAS 21 ni le §30 : introuvable pour qui le cherchait.
        C'est la faute corrigee en C4-0, ou la seconde interdiction du §85
        disparaissait sous une raison qui ne parlait que de la premiere.

        ⚠️ ET C'EST UNE TROISIEME NATURE. Les ecarts de change ne relevent NI
        de la presentation du resultat d'assurance (§80 a), NI des produits
        et charges financiers (§80 b) : ils viennent d'IAS 21 par le renvoi
        du §30. Une phrase ajoutee a la plage les laisserait dependre de la
        bonne volonte du lecteur.
        """
        refs = {e.reference: e for e in PERIMETRE}
        self.assertIn('§92, §30, IAS 21', refs)
        e = refs['§92, §30, IAS 21']
        self.assertEqual(e.etat, NON_CONSTRUIT)
        self.assertIn('change', e.libelle)
        for cle in ('IAS 21', 'ÉLÉMENT', 'MONÉTAIRE', 'NON BÂTI'):
            self.assertIn(cle, e.raison, cle)
        # ⚠️ et il est trouvable par une recherche sur chacun de ses termes
        for terme in ('§92', '§30', 'IAS 21'):
            self.assertIn(terme, e.reference + ' ' + e.raison, terme)
        print("    OK T3j : §92 a son propre element, IAS 21 et §30 nommes")

    def test_le_defaut_latent_de_la_devise_est_NOMME_la_ou_on_le_cherche(self):
        """⚠️ SIGNALE, NON TRAITE -- IL VIT DANS `core/`, HORS DE CE
        CHANTIER. Mais un defaut archive dans une note que personne ne relit
        est un defaut perdu. Il est donc NOMME a l'endroit ou quelqu'un le
        chercherait : la raison du pan qui en depend.
        """
        e = {x.reference: x for x in PERIMETRE}['§92, §30, IAS 21']
        for cle in ('core/courbe_rfr.py', 'NE LIT JAMAIS LA DEVISE',
                    'EN SILENCE', 'B79'):
            self.assertIn(cle, e.raison, cle)
        print("    OK T3k : le defaut latent de la devise est nomme dans la "
              "raison du §92 — signale, non traite")

    def test_le_87_dit_ce_qui_manque_ET_pourquoi(self):
        """⚠️ << PARTIELLEMENT BATI >> SANS LE DETAIL SERAIT UNE ETIQUETTE
        DE PLUS. La raison doit dire QUOI manque et POURQUOI."""
        e = {x.reference: x for x in PERIMETRE}['§78-92']
        self.assertIn('PARTIELLEMENT BÂTIS', e.raison)
        self.assertIn('SINISTRES SURVENUS ET L\'EFFET DES VARIATIONS DE '
                      'TAUX SONT DÉSORMAIS BÂTIS', e.raison)
        # ⚠️ et ce qui manque encore est nomme SANS le confondre avec ce qui
        # vient d'etre bati -- une premiere redaction disait dans la meme
        # phrase que l'effet de taux etait bati PUIS qu'il manquait.
        self.assertIn('MANQUE ENCORE : §87 b)', e.raison)
        self.assertIn('RISQUE FINANCIER', e.raison)
        self.assertIn('cadences', e.raison)        # la reserve descend
        self.assertIn('SANS OBJET', e.raison)      # §90 et §91
        print("    OK T3l : §87 dit ce qui vient d'etre bati, ce qui manque "
              "encore (§87 b), et la reserve qui rend le tout non opposable")

    def test_le_85_porte_ses_DEUX_interdictions(self):
        """⚠️ UNE ETIQUETTE QUI NE COUVRE PAS CE QU'ELLE ANNONCE.

        §85 interdit deux choses : les composantes d'investissement dans les
        produits et charges, ET la presentation en resultat net de primes
        non conformes au §83. La seconde n'a RIEN a voir avec la premiere,
        et elle disparaissait sous un motif qui ne parlait que d'elle.
        """
        hors = {e.reference: e for e in elements(HORS_PERIMETRE)}
        e85 = hors['§85']
        self.assertIn('Deux interdictions', e85.libelle)
        self.assertIn('§83', e85.libelle)
        self.assertIn('PREMIÈRE PHRASE', e85.raison)
        self.assertIn('SECONDE PHRASE', e85.raison)
        self.assertIn('§83', e85.raison)
        print("    OK T3g : §85 porte ses DEUX interdictions, la seconde ne "
              "disparait plus sous la premiere")

    def test_le_78_92_ne_sous_affirme_plus(self):
        """⚠️ LA FAUTE INVERSE DE C2-0, ET ELLE TROMPE AUTANT.

        La raison disait << aucun n'est encore produit >>. Faux des que la
        mesure a existe. Sous-affirmer fait croire qu'un travail deja fait
        reste a faire.

        ⚠️ CE TEST A DEJA MORDU DEUX FOIS, ET LES DEUX FOIS IL AVAIT RAISON :
        une premiere quand le bilan a ete bati, une seconde quand le §80 l'a
        ete. Il ne fige pas une redaction -- il exige que la raison suive
        l'etat. Ses assertions se mettent donc a jour AVEC lui, jamais en
        retablissant les mots d'avant.

        ⚠️⚠️ ET IL SURVEILLAIT LA RAISON EN ETANT AVEUGLE A L'ETIQUETTE. Deux
        fois il a fait corriger la prose de ce pan, et deux fois il a laisse
        `NON_CONSTRUIT` intact -- sur trois modules bâtis et 34 tests. La
        sous-affirmation qu'il combattait vivait donc, tout ce temps, dans le
        champ d'à côté. Un controle qui verifie un axe ne voit pas l'autre :
        c'est le motif de ce depot, applique a un test.
        """
        refs = {e.reference: e for e in PERIMETRE}
        e = refs['§78-92']
        self.assertEqual(e.etat, BATI)
        self.assertNotIn("aucun n'est encore produit", e.raison)
        # ⚠️ ce qui est BATI doit etre nomme comme tel
        self.assertIn('§78-79, LA PRÉSENTATION AU BILAN : BÂTIE', e.raison)
        self.assertIn('§80, LE COMPTE DE RÉSULTAT : BÂTI', e.raison)
        self.assertIn('CROISÉE', e.raison)
        # ⚠️ et ce qui NE l'est pas doit le rester, sinon la raison
        # sur-affirmerait cette fois
        self.assertIn('§78 c) et d)', e.raison)
        # ⚠️ TROISIEME FOIS QUE CE TEST MORD, TROISIEME FOIS QU'IL A RAISON.
        # Le pan §87-92 n'est plus un bloc << non bati >> : §87 est
        # PARTIELLEMENT bati, §88-89 sont arbitres, §90-91 sont SANS OBJET
        # par construction, et §92 a son propre element. Les assertions
        # suivent l'etat -- elles ne retablissent pas les mots d'avant.
        self.assertIn('PARTIELLEMENT BÂTIS', e.raison)
        self.assertIn('SANS OBJET', e.raison)
        self.assertIn('§92 a son PROPRE élément', e.raison)
        # ⚠️ et la contrainte de licence est ECRITE dans le livrable publie
        self.assertIn("AUCUNE VALEUR DE CETTE SOURCE N'EST REPRISE", e.raison)
        print("    OK T3h : §78-92 dit ce qui est calcule, ce qui manque, "
              "et qu'aucune source ne pourra confronter l'assemblage")

    def test_B72_n_ecarte_plus_le_taux_par_un_raisonnement_refute(self):
        """⚠️ UN ARGUMENT REFUTE NE RESTE PAS EN PLACE EN SILENCE.

        La raison de B72 concluait que les cas pluriannuels declenchant §56
        « echouent au §53 b) », donc qu'aucun cas ne survient. C2-0 a refute
        la premisse, et l'oracle ICA 5.6.1 exhibe le cas : trois ans, en
        PAA, avec §56. La CONCLUSION (ne pas batir le magasin) survit ; le
        RAISONNEMENT qui la portait, non.
        """
        hors = {e.reference: e for e in elements(HORS_PERIMETRE)}
        b72 = hors['B72 b) à e), B73'].raison
        self.assertNotIn("déclencheraient échouent au §53 b)", b72)
        # ce que la raison doit desormais distinguer : le taux, et le magasin
        self.assertIn('entrée déclarée', b72)
        self.assertIn('magasin', b72)
        self.assertIn('5.6.1', b72)
        print("    OK T3e : B72 separe le taux fourni du magasin de courbes, "
              "et ne s'appuie plus sur une premisse refutee")

    def test_les_flux_d_execution_sont_dus_en_PAA_pas_exclus(self):
        """⚠️ CE QUE §59 b) IMPOSE, ET QUE LE PÉRIMÈTRE DÉCLARAIT EXCLU.

        §59 b) : l'entité en PAA « DOIT evaluer le passif au titre des
        sinistres survenus [...] conformement aux paragraphes 33 a 37 et B36
        a B92 ». Choisir la PAA n'ecarte donc pas ces paragraphes, elle les
        appelle. Les ranger sous un << §32-52 hors perimetre >> les faisait
        passer pour ecartes quand ils sont dus.
        """
        refs = {e.reference: e for e in PERIMETRE}
        self.assertIn('§33-37, B36-B92', refs)
        flux = refs['§33-37, B36-B92']
        self.assertEqual(flux.etat, BATI)
        self.assertIn('§59 b)', flux.raison)
        hors = ' '.join(e.reference for e in elements(HORS_PERIMETRE))
        self.assertNotIn('§32-52', hors)
        for paragraphe in ('33', '34', '35', '36', '37'):
            self.assertNotIn(f'§{paragraphe},', hors)
        print("    OK T3d : §33-37 et B36-B92 sont NON CONSTRUITS et dus "
              "(§59 b), plus jamais declares hors perimetre")

    def test_l_option_OCI_se_declare_comme_methode_comptable(self):
        """Le §88 impose de CHOISIR : ne pas choisir n'est pas une option."""
        oci = next(e for e in PERIMETRE if '§88-89' in e.reference)
        self.assertIn('MÉTHODE COMPTABLE', oci.raison)
        self.assertIn('annexe', oci.raison)
        print("    OK T3c : l'option OCI est declaree comme methode "
              "comptable, a mentionner en annexe")


class T4_LesControlesDeNonApplicabilite(unittest.TestCase):
    """T4 — les drapeaux posés en D1 servent ici."""

    def test_aucune_alerte_sur_un_inventaire_ordinaire(self):
        lignes = [{'portefeuille': 'rc_auto', 'date_emission': '2026-03-15'}]
        self.assertEqual(signaler(lignes), ())
        print("    OK T4 : aucun faux positif sur un inventaire ordinaire")

    def test_un_contrat_a_participation_directe_est_signale(self):
        lignes = [{'portefeuille': 'epargne', 'participation_directe': 'oui'},
                  {'portefeuille': 'epargne', 'participation_directe': True},
                  {'portefeuille': 'rc_auto'}]
        alertes = signaler(lignes)
        self.assertEqual(len(alertes), 1)
        self.assertEqual(alertes[0].champ, 'participation_directe')
        self.assertEqual(alertes[0].nb_lignes, 2)
        self.assertIn('§45', alertes[0].reference)
        self.assertIn('HORS PÉRIMÈTRE', alertes[0].message)
        print(f"    OK T4b : {alertes[0].nb_lignes} contrats VFA signales, "
              f"{alertes[0].reference}")

    def test_une_composante_d_investissement_est_signalee(self):
        alertes = signaler([{'composante_investissement': 'VRAI'}])
        self.assertEqual(alertes[0].reference, '§85')
        self.assertIn('exclue des produits', alertes[0].message)
        print("    OK T4c : composante d'investissement signalee (§85)")

    def test_le_drapeau_se_lit_quelle_que_soit_son_ecriture(self):
        for valeur in ('oui', 'OUI', 'Oui', 'yes', 'true', 'VRAI', '1', 'x',
                       True):
            self.assertEqual(len(signaler(
                [{'participation_directe': valeur}])), 1, repr(valeur))
        for valeur in ('non', 'no', 'false', '0', '', None, False):
            self.assertEqual(signaler([{'participation_directe': valeur}]),
                             (), repr(valeur))
        print("    OK T4d : 9 ecritures du drapeau lues, 7 negations "
              "correctement ignorees")

    def test_signaler_ne_refuse_jamais(self):
        """Un inventaire PEUT contenir des contrats qu'on ne mesure pas ;
        ce qui serait fautif, c'est de les mesurer quand meme."""
        alertes = signaler([{'participation_directe': 'oui'}])
        self.assertIsInstance(alertes, tuple)
        self.assertEqual(set(CONTROLES), {'participation_directe',
                                          'composante_investissement'})
        print("    OK T4e : signaler() rend des alertes, ne leve jamais")


class T5_LaMentionDePerimetrePartiel(unittest.TestCase):
    """T5 — un jeu partiel pris pour un jeu complet est ce qu'un CAC relève."""

    def test_une_seule_direction(self):
        m = mention_directions(['Non-Vie'])
        self.assertIn('limités aux groupes de la direction Non-Vie', m)
        self.assertIn('périmètre partiel', m)
        print(f"    OK T5 : « {m} »")

    def test_plusieurs_directions(self):
        m = mention_directions(['Santé-Prévoyance', 'Non-Vie'])
        self.assertIn('Non-Vie, Santé-Prévoyance', m)
        self.assertIn('périmètre partiel', m)
        print("    OK T5b : plusieurs directions, mention triee et partielle")

    def test_aucune_direction_leve(self):
        with self.assertRaises(ValueError):
            mention_directions([])
        print("    OK T5c : des etats portent toujours sur un perimetre")


class T6_LeTextePublie(unittest.TestCase):
    """T6 — ce qui se remet à un actuaire ou à un commissaire."""

    def test_le_texte_porte_les_quatre_sections_et_les_raisons(self):
        t = texte()
        for attendu in ('PÉRIMÈTRE IFRS 17', 'CE QUI EST COUVERT',
                        'BÂTI ET TESTÉ', "RIEN N'EXISTE ENCORE",
                        'DÉCISIONS ASSUMÉES', 'SIGNALÉS par'):
            self.assertIn(attendu, t)
        for e in elements(HORS_PERIMETRE):
            self.assertIn(e.reference, t)
        print(f"    OK T6 : {len(texte().splitlines())} lignes, "
              "4 sections, toutes les references citees")

    def test_le_preambule_NE_SUR_AFFIRME_PLUS(self):
        """⚠️⚠️ IL DISAIT « la plateforme COUVRE l'évaluation, la
        présentation et la clôture » et « conserve les clôtures
        successives ». Les trois étaient faux : §93-132 n'est pas bâti, et la
        persistance des soldes n'existe pas. ⚠️ Et le corps du MÊME document
        déclarait NON_CONSTRUIT les pans que le préambule revendiquait."""
        t = texte()
        for disparu in ('couvre', 'conserve les clôtures successives'):
            self.assertNotIn(disparu, t.split('CE QUI EST COUVERT')[0])
        self.assertIn(BATI_N_EST_PAS_OPPOSABLE, t)
        self.assertIn("BÂTI N'EST PAS OPPOSABLE", t)

    def test_le_texte_publie_porte_les_RESERVES_d_opposabilite(self):
        """⚠️ Un pan bâti dont la réserve ne descend pas se lirait comme
        opposable. C'est la seule chose qui sépare « la plateforme sait le
        calculer » de « ce montant peut être signé »."""
        t = texte()
        self.assertIn('OPPOSABILITÉ RÉSERVÉE', t)
        self.assertIn('CADENCES INVENTÉES', t)
        for e in elements(BATI):
            if e.opposabilite == SOUS_RESERVE:
                self.assertIn(e.reserve, t, e.reference)

    def test_aucun_element_n_est_oublie_du_texte(self):
        t = texte()
        for e in PERIMETRE:
            self.assertIn(e.libelle.split('\n')[0][:40], t, e.reference)
        self.assertEqual(set(Element._fields),
                         {'reference', 'etat', 'libelle', 'raison',
                          'opposabilite', 'reserve'})
        print(f"    OK T6b : les {len(PERIMETRE)} elements figurent au texte")


class T7_LaNarrationLLM_EstECARTEE_ET_LE_VERROU_TIENT(unittest.TestCase):
    """⚠️⚠️ UNE EXCLUSION QUE PERSONNE NE CONTRÔLE EST UNE INTENTION.

    Cette classe est le second demi-verrou. Le premier vit dans
    `core/test_frontiere_llm.py` : il interdit d'appeler l'API hors de la
    frontière, dans TOUT le dépôt — un quatorzième site DOIT donc importer
    la frontière. Celui-ci interdit qu'un fichier de `normes/` l'importe.

    ⚠️ NI L'UN NI L'AUTRE NE SUFFIT SEUL : sans le premier, un module de
    `normes/` pourrait instancier son propre client ; sans le second, il
    suffirait de passer par la frontière pour rédiger une annexe signée.
    """

    #: L'élément, repéré par sa référence — qui ne cite AUCUN paragraphe,
    #: et c'est délibéré : la norme ne dit pas qui tient la plume.
    REFERENCE = 'aucun paragraphe — production du livrable'

    def _element(self):
        trouves = [e for e in PERIMETRE if e.reference == self.REFERENCE]
        self.assertEqual(len(trouves), 1, "l'exclusion LLM a disparu")
        return trouves[0]

    def test_l_exclusion_est_une_DECISION_ASSUMEE_pas_un_chantier(self):
        """⚠️ HORS_PERIMETRE et non NON_CONSTRUIT : rien ne viendra la
        combler. La confondre avec un chantier laisserait croire l'inverse."""
        self.assertEqual(self._element().etat, HORS_PERIMETRE)
        print("    OK T7 : la narration LLM est HORS PERIMETRE, assumee")

    def test_elle_ne_cite_aucun_paragraphe_ET_LE_DIT(self):
        """⚠️ CITER UN PARAGRAPHE SERAIT LUI INVENTER UN APPUI. Aucun
        paragraphe d'IFRS 17 n'interdit une prose générée — c'est
        exactement pourquoi la ligne doit exister."""
        e = self._element()
        self.assertEqual(_paragraphes(e.reference), set())
        self.assertIn("AUCUN PARAGRAPHE D'IFRS 17 NE L'INTERDIT", e.raison)
        self.assertIn("aucun texte n'arrête", e.raison)

    def test_elle_porte_sur_le_LIVRABLE_et_pas_sur_la_plateforme(self):
        """⚠️ SANS CETTE PRÉCISION, ELLE SE LIRAIT COMME UNE INTERDICTION
        GÉNÉRALE — et le mapping de colonnes tomberait avec."""
        r = self._element().raison
        self.assertIn('LE CONTENU DU LIVRABLE, NON SUR LA PLATEFORME', r)
        self.assertIn('reconnaissance de colonnes', r)
        self.assertIn('un PÉRIMÈTRE, pas un mécanisme', r)

    def test_AUCUN_fichier_de_normes_n_atteint_le_modele_de_langage(self):
        """⚠️⚠️ LE VERROU RÉEL, MESURÉ SUR LE CODE ET NON DÉCLARÉ.

        Le jour où le rendu des états sera bâti, la chaîne A7 sera le modèle
        évident à reprendre — elle porte `_narration_claude_api`. Ce test
        échoue AVANT que la ligne ne parte chez un client.

        ⚠️ IL SE LIT SUR L'AST, ET LA PREMIÈRE VERSION SE LISAIT SUR LE
        TEXTE : elle échouait sur ELLE-MÊME, en trouvant les chaînes qu'elle
        cherchait dans sa propre prose. Le dépôt avait déjà payé cette leçon
        avec `test_aucune_dependance_au_socle`. Mesuré ici : « appeler »
        apparaît trois fois dans `normes/`, TOUJOURS en français — « l'appeler
        directement contourne ce contrôle » — et JAMAIS comme identifiant. Un
        relevé textuel rendrait trois faux positifs ; l'AST en rend zéro.
        """
        import ast
        from pathlib import Path
        racine = Path(__file__).resolve().parents[2]
        fautifs, balayes = [], 0
        for f in racine.rglob('*.py'):
            balayes += 1
            arbre = ast.parse(f.read_text(encoding='utf-8'))
            noms = set()
            for n in ast.walk(arbre):
                if isinstance(n, ast.Import):
                    noms |= {a.name.split('.')[0] for a in n.names}
                elif isinstance(n, ast.ImportFrom):
                    noms.add((n.module or '').split('.')[0])
                    noms |= {a.name for a in n.names}
                elif isinstance(n, ast.Attribute):
                    noms.add(n.attr)
                elif isinstance(n, ast.Name):
                    noms.add(n.id)
            atteint = noms & {'anthropic', 'appeler'}
            if atteint:
                fautifs.append(f'{f.name} ({sorted(atteint)})')
        self.assertEqual(
            fautifs, [],
            f"{len(fautifs)} fichier(s) de normes/ atteignent le modèle de "
            f"langage : {fautifs}. Le périmètre publié affirme qu'aucun texte "
            f"des états financiers n'en provient — voir « {self.REFERENCE} ».")
        print(f"    OK T7b : {balayes} fichiers de normes/ balayes sur "
              "l'AST, AUCUN n'atteint le modele de langage")

    def test_le_releve_des_narrations_du_depot_est_BRUYANT(self):
        """⚠️ LA RAISON PUBLIÉE CITE « 13 sites, dont 9 narrations ». Un
        chiffre écrit dans un livrable et jamais confronté redevient faux
        sans bruit — celui-ci tombe si le relevé bouge."""
        from core.frontiere_llm import SITES
        narrations = [s for s in SITES if s.usage == 'narration']
        self.assertEqual((len(SITES), len(narrations)), (13, 9))
        dans_normes = [s.chemin for s in SITES
                       if s.chemin.startswith('normes/')]
        self.assertEqual(dans_normes, [], "un site LLM est apparu dans normes/")
        print(f"    OK T7c : {len(SITES)} sites declares, {len(narrations)} "
              "narrations, AUCUNE dans normes/")


if __name__ == '__main__':
    unittest.main(verbosity=2)
