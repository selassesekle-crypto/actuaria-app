"""Un correctif ne peut plus fermer un constat sans le REPORTER a l'archive.

CE QUE CE FICHIER PROUVE, ET POURQUOI IL EXISTE
────────────────────────────────────────────────
⚠️⚠️ LE DEFAUT MESURE, LE 28/08/2026. L'archive s'arretait a `5bccc33`
(27/08 20:00). DOUZE commits de correction ont suivi -- cinq d'entre eux
fermant un constat nomme (`a3/C4` `a3/C14` `a4/C10` `a6/C6` `a6/C8`) -- et
AUCUN n'avait produit de bloc de fermeture. Le compte publie disait
`37 fermes / 110 ouverts` la ou le vrai etat etait `42 / 105`.

⚠️ ET LE FILET EXISTANT NE POUVAIT PAS LE VOIR. `test_archive_cles_fermeture`
verifie qu'un bloc PRESENT porte une cle valide. Il ne dit rien d'un bloc
ABSENT. *C'est le motif de tout cet audit applique a notre propre outillage :
un controle qui ATTESTE sans SURVEILLER.*

LE SIGNAL RETENU, ET POURQUOI CELUI-LA
──────────────────────────────────────
Quand un lot ferme un constat, il ecrit un test qui l'epingle, et ce test
NOMME le constat : `test_pvalue_non_fabriquee` nomme `a3/C14`,
`test_ic95_infobulles` nomme `a3/C4`, etc. **33 cles sont ainsi nommees dans
les tests de tarification.** L'invariant est donc :

    toute cle de constat nommee dans un test DOIT porter un bloc de fermeture

⚠️ IL AURAIT TIRE LE 27/08 : les cinq fichiers de test des lots du rang 3
existaient deja, et aucun des cinq blocs n'etait ecrit.

⚠️⚠️ ET CE N'EST PAS UN CONTROLE PAR `git log`, DELIBEREMENT. La CI clone en
PROFONDEUR 1 (`actions/checkout` sans `fetch-depth`) : un controle qui
interroge l'historique serait vert par accident sur la machine ou il compte le
plus. On n'interroge que des fichiers versionnes.
"""

from __future__ import annotations

import pathlib
import re
import unicodedata
import unittest

#: La racine de l'audit, et celle des tests de tarification.
_TARIF = pathlib.Path(__file__).resolve().parent
_ARCHIVE = _TARIF / 'audit_2026_08'

#: Une cle de constat : `zone/Cn`. Les zones sont celles des 14 releves.
_ZONES = ('a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'plan', 'conformite', 'qualite',
          'services', 'agents', 'charts', 'pipeline', 'socle')
_CLE = re.compile(r'\b(' + '|'.join(_ZONES) + r')/C(\d+)\b')

#: L'en-tete d'un constat, DEUX formes -- n'en compter qu'une en rate douze.
_ENTETE = re.compile(r'^\*\*(C\d+)\*\*\s*—|^\*\*(C\d+)\s*—')

#: ⚠️ EXCEPTIONS DECLAREES : une cle NOMMEE dans un test sans y etre FERMEE.
#: Toute entree doit porter SA RAISON -- une exception muette est exactement ce
#: que cet audit poursuit.
#:
#: ⚠️⚠️ ET ELLE EST SCOPEE PAR FICHIER, PAS PAR CLE. Une exemption portant la
#: seule cle laisserait passer un futur test qui EPINGLERAIT vraiment ce
#: constat en oubliant son bloc d'archive -- c'est-a-dire exactement le defaut
#: que ce fichier existe pour attraper. La cle (constat, fichier) fait qu'un
#: AUTRE fichier nommant la meme cle rallume le filet.
_HORS_ASSIETTE: dict[tuple[str, str], str] = {
    ('a2/C5', 'test_comptes_a2_publies.py'):
        "Cite comme RAISON du chemin choisi par l'aide `_executer` (A1 -> A2 "
        "plutot que fit/transform : les deux chemins ne traitent pas "
        "l'exposition nulle pareil), pas epingle. "
        "Retirer la mention detruirait une vraie trace ; une mention n'est "
        "pas une fermeture.",
    ('a2/C9', 'test_a2_neuf_constats.py'):
        "Cite dans la section << CE QUI RESTE OUVERT >> de l'en-tete, avec sa "
        "raison, jamais epingle. `a2/C9` -- une moyenne rangee sous la cle "
        "`medianes` -- est RANG 5, arbitre par Selasse : renommer la cle change "
        "le format d'un JSON persiste. *Un lot qui ferme neuf "
        "constats doit dire lesquels il ne ferme pas, et pourquoi.*",
    ('a2/C16', 'test_a2_neuf_constats.py'):
        "Cite dans la section << CE QUI RESTE OUVERT >>, avec sa raison, jamais "
        "epingle. `__init__` cree `/tmp/actuaria` -- et le constat a un JUMEAU "
        "chez le voisin, `a1/C7`, MEME MECANISME. Le corriger d'un seul "
        "cote recreerait tres exactement l'asymetrie entre voisins que cet "
        "audit poursuit ; et ce n'est pas un texte : instancier cesserait "
        "d'ecrire sur le disque, ce qui est un changement de comportement. "
        "**Les deux ensemble, dans leur propre lot.**",
    ('a1/C7', 'test_a2_neuf_constats.py'):
        "Cite comme LE JUMEAU de `a2/C16`, jamais epingle -- et c'est la "
        "mention qui rend la retenue lisible. `a1/C7` dit qu'instancier A1 "
        "ecrit sur le disque (`/tmp/actuaria/{audit,config}`) ; `a2/C16` dit "
        "la meme chose d'A2. *Nommer le jumeau est ce qui empeche de fermer "
        "l'un en laissant l'autre.*",
    ('a2/C5', 'test_portes_du_plan.py'):
        "Cite comme MOTIF DU REJET d'une des deux solutions envisagees pour "
        "`pipeline/C8`, jamais epingle. Face a des NaN qui tuent le GLM, un "
        "`fillna` en aval etait la reparation evidente -- et c'est exactement "
        "`a2/C5` : imputer EN SILENCE sur une donnee illisible. Le lot a donc "
        "choisi de REFUSER en nommant la cause. `a2/C5` est rang 5. "
        "*Retirer la mention couperait le correctif de la raison qui a ecarte "
        "l'autre solution.*",
    ('a2/C9', 'test_imputation_par_la_table.py'):
        "Cite pour dire POURQUOI le mode d'un binaire est range sous `modes` "
        "et non sous `medianes` : l'y mettre aurait AJOUTE une occurrence a "
        "`a2/C9` au lieu d'en retirer. `a2/C9` est rang 5, "
        "deliberement non corrige -- renommer la cle change le format d'un "
        "JSON persiste. La mention est la trace de cette retenue.",
    ('plan/C7', 'test_echeance_et_avertissement_qualite.py'):
        "Cite comme NOM DU CHANTIER dont ce lot est l'etape 2+3. `plan/C7` "
        "est la declaration des roles dans les 20 plans : elle est l'ETAPE 5, "
        "Ce fichier epingle la couche qualite, pas les "
        "plans. Retirer la mention couperait le lot de la raison qui le rend "
        "necessaire.",
    ('socle/C2', 'test_charge_nette_negative.py'):
        "Cite comme COMPARAISON, jamais epingle : `vulture` avait signale "
        "`question_charges_negatives` comme fonction MORTE, et le controle de "
        "cablage explique que c'est LA FORME de `socle/C2` -- de la plomberie "
        "posee que rien n'alimente. `socle/C2` designe le moteur de MAPPING, "
        "un tout autre code, au rang 7. Retirer la mention "
        "couperait le controle de la lecon qui le justifie.",
    ('socle/C2', 'test_colonnes_plan_ecartees.py'):
        "Cite comme MOTIF que `CPE-9` existe pour eviter, jamais epingle. Ce "
        "lot ajoute une SOURCE UNIQUE de libelle "
        "(`synthese_colonnes_plan_ecartees`) : une source unique que personne "
        "n'appellerait serait de la plomberie posee que rien n'alimente -- la "
        "forme de `socle/C2`. `CPE-9` verifie donc PAR AST que les TROIS "
        "services la publient. `socle/C2` designe le moteur de MAPPING, un "
        "tout autre code, au rang 7. C'est la TROISIEME "
        "mention de cette cle : la portee (constat, fichier) rallume bien le "
        "filet sur chaque fichier neuf.",
    ('charts/C8', 'test_tri_a5_charts_services.py'):
        "Cite par la passe de tri, avec sa raison, "
        "et un controle qui en garde le SECOND SENS -- jamais epingle. "
        "`charts/C8` vit dans `actuaria_app.py`, et **l'app Streamlit est hors "
        "perimetre par arbitrage de Selasse du 25/08** : elle disparait, on n'y "
        "touche pas, meme pour une phrase. ⚠️ Le constat est par ailleurs "
        "REFUTE sur un point : il disait << Meme valeur aujourd'hui >>, or "
        "`CONFIG_PLOTLY` porte `responsive: True` que le litteral de l'app n'a "
        "pas, sur DEUX sites et non un. `TRI-8` epingle cette divergence : le "
        "jour ou les deux coincideront, il tombera, et ce sera le signal qu'il "
        "faut reecrire le constat.",
    ('services/C7', 'test_tri_a5_charts_services.py'):
        "Cite par la passe de tri, avec sa raison, "
        "jamais epingle. `raisons_plafond` atteint 2 surfaces sur 6 ; le porter "
        "aux quatre autres (Excel A6 + les trois formats du rapport equipe) "
        "ajoute une phrase a QUATRE LIVRABLES SIGNES. C'est un lot de "
        "PUBLICATION a lui seul, de la meme famille que l'etape 4 du chantier "
        "`unite_exposition`, et il doit porter ses propres controles -- la "
        "lecon du jour etant precisement qu'une surface signee peut changer "
        "sous 812 tests verts. **Ne pas l'empiler dans une passe de tri.**",
    ('qualite/C4', 'test_preambule_qualite.py'):
        "Cite comme RAISON D'ETRE de l'etape 1-A, jamais epingle -- et la "
        "distinction est le coeur du lot. `qualite/C4` dit que LE CHEMIN AGENT "
        "N'A AUCUNE COUCHE QUALITE. Or 1-A extrait seulement la porte et la "
        "branche au chemin DECLARATIF, qui l'avait deja : elle ne donne "
        "toujours rien a l'autre chemin. **C'est l'etape 1-B qui fermerait "
        "`qualite/C4`, et elle deplace un prix** -- mesure du 31/08 : le "
        "chemin agent tarife sur 30 lignes a frequence negative que cette "
        "couche ecarte, et le branchement introduirait un blocage. "
        "-- RE-MESURE DU 01/09 : la mesure du 31/08 disait 60 lignes "
        "<< a frequence OU COUT negatifs >>, et `qualite/C8`, ferme le meme "
        "soir APRES elle, a sorti le cout de la regle 1 : il est SIGNALE et "
        "GARDE par les deux chemins. Le blocage vient de l'UNION (9 %), aucun "
        "type seul n'atteignant 5 %. `qualite/C4` est au rang 6 GELE. *Le "
        "fermer sur l'extraction ferait croire que le chemin agent est "
        "protege.*",
    ('qualite/C4', 'test_qualite_non_executee.py'):
        "Cite comme CAUSE NOMMEE de l'absence de rapport qualite, jamais "
        "epingle. La phrase publiee dans les livrables dit POURQUOI la couche "
        "n'a pas tourne, et `QNE-2` exige qu'elle le dise : *un avertissement "
        "qui annonce une absence sans sa raison envoie l'actuaire chercher un "
        "defaut de donnees la ou il manque un branchement.* Retirer la mention "
        "couperait l'avertissement de sa cause. `qualite/C9` corrige ce que le "
        "livrable DIT de l'absence ; il ne touche pas a l'absence elle-meme, "
        "qui est la fusion 1-B.",
    ('qualite/C4', 'test_canal_signature_agent.py'):
        "Cite comme CAUSE du refus, jamais epingle. Le canal de signature du "
        "chemin agent n'a pas d'objet PARCE QUE ce chemin n'appelle pas la "
        "couche qualite : le message de `SignatureSansObjet` nomme la cle, et "
        "`SG-3` exige qu'il la nomme -- *un refus qui ne dit pas POURQUOI "
        "transforme un garde-fou en mur.* `qualite/C12` pose le canal et le "
        "fait refuser ; c'est l'etape 5 qui lui donnera un objet, et elle "
        "deplace un prix.",
    ('socle/C2', 'test_preambule_qualite.py'):
        "Cite comme MOTIF que le controle PQ-7 existe pour eviter, jamais "
        "epingle. L'etape 1-A pose une porte `preambule_qualite` que SEUL le "
        "chemin declaratif appelle : branchee a moitie, elle a exactement la "
        "silhouette de `socle/C2` -- de la plomberie posee que rien "
        "n'alimente. PQ-7 exige donc que la porte DECLARE elle-meme qu'elle "
        "attend l'etape 1-B, et pourquoi (1-B deplace un prix). `socle/C2` "
        "designe le moteur de MAPPING, un tout autre code, au "
        "rang 7. C'est la SECONDE mention de cette cle, apres "
        "test_charge_nette_negative.py : la cle (constat, fichier) a bien "
        "rallume le filet sur un fichier neuf, comme prevu.",
    # ⚠️⚠️ L'EXEMPTION DE `qualite/C3` A ETE RETIREE LE 31/08/2026. Elle disait
    # << `qualite/C3` reste donc OUVERT >> : c'est devenu FAUX le jour ou
    # l'etape 2 a declare `unite_exposition` au plan et fait deriver la borne.
    # Le constat porte desormais son bloc de fermeture dans
    # `releve_qualite_donnees.md`, et ce filet n'a plus rien a exempter.
    # *Une exemption dont la RAISON est perimee ment sur l'etat de l'audit --
    # exactement ce que ce fichier existe pour empecher.*
    # ⚠️ L'EXEMPTION `('socle/C1', 'test_socle_quatre_constats.py')` A ETE
    # RETIREE LE 01/09/2026. Elle disait << il attend son arbitrage >> --
    # devenu FAUX le jour ou Selasse a tranche et ou le constat a ete ferme
    # par `test_socle_c1_assiette_ecretement`. La mention subsiste chez le
    # voisin, mais elle n'a plus besoin d'etre exemptee : la cle porte son
    # bloc de fermeture. *Seconde fois de la session, meme mecanisme.*

    # ⚠️ L'EXEMPTION `('a1/C5', 'test_vocabulaire_echeance.py')` A ETE RETIREE
    # LE 01/09/2026. Elle disait « les doublons INTRA-liste, qui sont `a1/C5`
    # (rang 7, OUVERT) » -- devenu FAUX le jour ou `a1/C5` a ete ferme et
    # epingle par `A1-4` de `test_a1_six_constats.py`. La mention subsiste dans
    # le voisin, mais elle n'a plus besoin d'etre exemptee : la cle porte
    # desormais son bloc de fermeture.
}


def _texte(chemin: pathlib.Path) -> str:
    return unicodedata.normalize(
        'NFC', chemin.read_text(encoding='utf-8', errors='replace'))


def _constats_reels() -> set[str]:
    """Les cles qui designent un constat REEL, lues aux en-tetes des releves.

    ⚠️ C'est ce qui evite d'accuser une cle de FIXTURE : `a3/C99`, forge par
    `test_archive_cles_fermeture` pour son propre controle, ne designe aucun
    constat -- il sort donc de l'assiette sans avoir a etre liste.
    """
    reels: set[str] = set()
    for fichier in sorted(_ARCHIVE.glob('releve_*.md')):
        zone = fichier.stem.replace('releve_', '')
        zone = {'a1_ingestion': 'a1', 'a2_preprocessing': 'a2', 'a3_glm': 'a3',
                'a4_ml': 'a4', 'a5_deep_learning': 'a5', 'a6_comparaison': 'a6',
                'plan_tarifaire': 'plan', 'conformite_reglementaire': 'conformite',
                'qualite_donnees': 'qualite', 'services_rapport': 'services',
                'pipeline_agents': 'agents', 'charts_tarif': 'charts',
                'pipeline_tarifaire': 'pipeline', 'socle_core': 'socle'}[zone]
        for ligne in _texte(fichier).split('\n'):
            trouve = _ENTETE.match(ligne.strip())
            if trouve:
                reels.add(f'{zone}/{trouve.group(1) or trouve.group(2)}')
    return reels


def _cles_fermees() -> set[str]:
    """Les cles d'ATTRIBUTION portees par les blocs `> ✅`.

    ⚠️ L'attribution est ce qui precede le premier `·` : au-dela, une cle est
    un RENVOI (<< meme geste qu'`a3/C9` >>), pas une fermeture.
    """
    fermees: set[str] = set()
    for fichier in sorted(_ARCHIVE.glob('releve_*.md')):
        for ligne in _texte(fichier).split('\n'):
            depouille = ligne.strip()
            if not (depouille.startswith('>') and '✅' in depouille):
                continue
            for zone, num in _CLE.findall(depouille.split('·')[0]):
                fermees.add(f'{zone}/C{num}')
    return fermees


def _cles_nommees_par_les_tests() -> dict[str, set[str]]:
    """Chaque cle nommee dans un test de tarification, et par qui.

    ⚠️⚠️ CE FICHIER-CI EST HORS DE SA PROPRE ASSIETTE, ET C'EST STRUCTUREL.
    Les cles qui y figurent sont des DECLARATIONS d'exemption ou des temoins de
    controle -- jamais des epinglages. Sans cette sortie, declarer une exemption
    pour `x/Cn` CREERAIT une mention de `x/Cn` que le filet reprocherait
    aussitot : le garde-fou s'accuserait lui-meme, et l'exemption serait
    impossible a ecrire. *Mesure : le defaut s'est produit des la premiere
    entree ecrite.*
    ⚠️ La sortie ne couvre QUE ce fichier : tout autre test nommant une cle
    reste dans l'assiette, et la violation plantee le prouve.
    """
    par_cle: dict[str, set[str]] = {}
    for fichier in sorted(_TARIF.rglob('test_*.py')):
        if ('audit_2026_08' in fichier.as_posix()
                or fichier.name == pathlib.Path(__file__).name):
            continue
        for zone, num in _CLE.findall(_texte(fichier)):
            par_cle.setdefault(f'{zone}/C{num}', set()).add(fichier.name)
    return par_cle


class TestFermetureReportee(unittest.TestCase):
    """Un correctif epingle produit un bloc de fermeture, ou la gate tombe."""

    def test_toute_cle_epinglee_par_un_test_porte_son_bloc(self):
        """⚠️⚠️ LE CONTROLE QUI MANQUAIT.

        Il aurait tire le 27/08 sur les cinq lots du rang 3.
        """
        reels = _constats_reels()
        fermees = _cles_fermees()
        manquants = {
            cle: sorted(fichiers)
            for cle, fichiers in (
                (c, {f for f in fs if (c, f) not in _HORS_ASSIETTE})
                for c, fs in _cles_nommees_par_les_tests().items())
            if fichiers and cle in reels and cle not in fermees
        }
        self.assertEqual(
            manquants, {},
            f"{len(manquants)} constat(s) épinglé(s) par un test sans bloc de "
            f"fermeture dans l'archive : {manquants}. Un correctif qui ferme "
            f"un constat l'écrit dans son relevé, sinon le compte publié ment.")
        print(f"    OK ARCH-1 {len(_cles_nommees_par_les_tests())} clés nommées "
              f"par les tests, toutes reportées")

    def test_les_exceptions_declarees_portent_leur_raison(self):
        """⚠️ Une exception muette est le défaut que cet audit poursuit."""
        for (cle, fichier), raison in _HORS_ASSIETTE.items():
            self.assertRegex(cle, r'^\w+/C\d+$', f'clé mal formée : {cle}')
            self.assertRegex(fichier, r'^test_\w+\.py$',
                             f'{cle} : fichier mal formé : {fichier}')
            self.assertTrue(
                (_TARIF / fichier).exists() or any(
                    _TARIF.rglob(fichier)),
                f'{cle} : exemption sur un fichier absent : {fichier}')
            self.assertGreaterEqual(
                len(raison.strip()), 20,
                f'{cle} : exception sans raison lisible')
        print(f"    OK ARCH-2 {len(_HORS_ASSIETTE)} exception(s) déclarée(s), "
              f"toutes motivées")

    def test_ARCH_7_aucune_raison_ne_REAFFIRME_un_etat(self):
        """⚠️⚠️ LE CONTRÔLE QUI MANQUAIT, ET 11 RAISONS SUR 13 ÉTAIENT FAUSSES.

        `ARCH-2` vérifie qu'une exception porte une raison. Il ne dit rien de
        la VÉRACITÉ de cette raison. Mesuré le 01/09/2026, après la fermeture
        de `socle/C1` et `a2/C9` : **onze des treize raisons affirmaient
        « reste OUVERT » sur des clés désormais FERMÉES.**

        > *Une exemption dont la raison est périmée ment sur l'état de
        > l'audit — exactement ce que ce fichier existe pour empêcher.*

        Le remède n'est pas de réécrire onze textes à chaque fermeture : ce
        serait une dette perpétuelle. **Une raison ne réaffirme jamais un état
        qui vit ailleurs** — elle dit POURQUOI le fichier cite la clé sans
        l'épingler, et l'état se dérive de l'archive.

        ⚠️ L'ASSIETTE EXCLUT LES CITATIONS. Une raison peut nommer une section
        intitulée « CE QUI RESTE OUVERT » : c'est un TITRE cité, pas une
        affirmation. *Une citation n'est pas une affirmation* — huitième
        occurrence de la session, et la première sur ce fichier-ci.
        """
        citation = re.compile(r'<<.*?>>', re.DOTALL)
        affirmation = re.compile(
            r'reste[nt]?\s+OUVERTE?S?|LAISSE\s+OUVERT|JUMEAU\s+OUVERT',
            re.IGNORECASE)
        fautives = []
        for (cle, fichier), raison in _HORS_ASSIETTE.items():
            nu = citation.sub('', raison)
            trouve = affirmation.search(nu)
            if trouve:
                fautives.append(f'{cle} @ {fichier} : « {trouve.group(0)} »')
        self.assertEqual(
            fautives, [],
            f"raison(s) d'exemption qui RÉAFFIRMENT un état vivant ailleurs : "
            f"{fautives}. L'état d'un constat se DÉRIVE de l'archive ; le "
            f"recopier dans une raison le condamne à périmer en silence.")
        print(f"    OK ARCH-7 {len(_HORS_ASSIETTE)} raison(s), aucune ne "
              f"réaffirme un état")

    def test_le_controle_voit_une_fermeture_NON_reportee(self):
        """⚠️⚠️ SECOND SENS — le filet discrimine, il ne dit pas toujours OUI.

        On retire une clé réelle de l'ensemble des fermées, comme si son bloc
        n'avait jamais été écrit, et le contrôle doit la nommer.
        """
        reels = _constats_reels()
        nommees = _cles_nommees_par_les_tests()
        temoin = next(c for c in sorted(nommees) if c in reels
                      and c in _cles_fermees())
        fermees_amputees = _cles_fermees() - {temoin}
        manquants = [c for c in nommees
                     if c in reels and c not in fermees_amputees]
        self.assertIn(
            temoin, manquants,
            "le contrôle ne voit pas une fermeture retirée : il ne prouve rien")
        print(f"    OK ARCH-3 violation plantée sur « {temoin} » : détectée")

    def test_le_controle_ne_voit_pas_une_cle_de_FIXTURE(self):
        """⚠️ SECOND SENS — `a3/C99` est forgé par `test_archive_cles_fermeture`
        pour son propre contrôle. Il ne désigne aucun constat : accuser cette
        clé serait un faux positif, et il n'a pas fallu la lister pour
        l'écarter — c'est l'assiette « constat RÉEL » qui l'exclut."""
        reels = _constats_reels()
        self.assertNotIn('a3/C99', reels,
                         "`a3/C99` désigne un constat réel : l'assiette du "
                         "contrôle doit être revue")
        self.assertIn('a3/C99', _cles_nommees_par_les_tests(),
                      "la clé de fixture a disparu des tests : ce contrôle ne "
                      "prouve plus rien")
        print("    OK ARCH-4 la clé de fixture `a3/C99` est hors assiette, "
              "sans liste d'exception")

    def test_le_compte_derive_est_celui_que_la_feuille_publie(self):
        """⚠️⚠️ ET LE COMPTE PUBLIÉ NE PEUT PLUS DIVERGER DU COMPTE DÉRIVÉ.

        C'est l'autre moitié du défaut : l'archive peut être à jour et la
        feuille de route, elle, porter encore l'ancien chiffre.
        """
        reels = _constats_reels()
        fermees = _cles_fermees()
        # ⚠️⚠️ L'EXCEPTION `pipeline/C1` A ÉTÉ RETIRÉE LE 31/08/2026. Elle
        # disait « PARTIEL : arbitré, il compte OUVERT » — devenu FAUX le jour
        # où son résidu (la plausibilité) a été fermé par `Facteur.bornes`.
        # *Une exception dont la raison est périmée ment sur l'état du compte,
        # exactement comme une exemption d'archive périmée.*
        n_fermes = len(fermees)
        n_ouverts = len(reels) - n_fermes
        feuille = _texte(_ARCHIVE / 'FEUILLE_DE_ROUTE.md')
        self.assertIn(
            f'| fermés **et épinglés** | **{n_fermes}** |', feuille,
            f"la feuille de route ne publie pas {n_fermes} fermés")
        self.assertIn(
            f'| **⛔ OUVERTS** | **{n_ouverts}** |', feuille,
            f"la feuille de route ne publie pas {n_ouverts} ouverts")
        print(f"    OK ARCH-5 feuille et archive concordent : {len(reels)} "
              f"constats, {n_fermes} fermés, {n_ouverts} ouverts")

    def test_la_REPARTITION_par_zone_ne_peut_plus_perimer_en_silence(self):
        """⚠️⚠️ `ARCH-5` TIENT LE TOTAL, JAMAIS LA RÉPARTITION — et le tableau
        du TRI a péri DEUX fois pour cette raison exacte.

        Le 29/08 il publiait `80 − 46 = 33` (trois nombres dont deux seulement
        pouvaient être vrais). Corrigé, il a re-péri le 31/08 : `plan` 6 et
        `qualite` 4 alors que `plan/C5` et `qualite/C3` venaient d'être fermés.

        ⚠️ **ET L'AVERTISSEMENT ÉTAIT ÉCRIT DANS LE DOCUMENT, deux paragraphes
        sous la ligne fautive.** *Un avertissement écrit n'est pas un garde-fou :
        seul un contrôle qui ÉCHOUE en est un.* Celui-ci échoue.

        ⚠️ Assiette déclarée : la LIGNE de répartition du tableau du TRI. Il ne
        contrôle pas les autres comptes en prose du document — ceux-là restent
        non tenus, et c'est dit plutôt que supposé.
        """
        ouverts = _constats_reels() - _cles_fermees()
        par_zone: dict[str, int] = {}
        for cle in ouverts:
            zone = cle.split('/')[0]
            par_zone[zone] = par_zone.get(zone, 0) + 1

        feuille = _texte(_ARCHIVE / 'FEUILLE_DE_ROUTE.md')
        ligne = next((l for l in feuille.split('\n')
                      if 'zones TRIÉES' in l), None)
        self.assertIsNotNone(
            ligne, "la ligne de répartition du tableau du TRI a disparu : "
                   "ce contrôle ne surveille plus rien")

        # ⚠️⚠️ LES ZONES NON TRACÉES SE LISENT AU DOCUMENT, ELLES NE SONT PAS
        # ÉCRITES ICI. Ma première version portait `('a5','charts','services')`
        # en dur : la passe de tri du 31/08 les a toutes tracées, et le
        # contrôle serait devenu faux le jour même où le document devenait
        # juste. *Un garde-fou qui recopie ce qu'il surveille périme avec lui.*
        ligne_non_tracees = next(
            (l for l in feuille.split('\n') if 'jamais tracés' in l), '')
        non_tracees = tuple(re.findall(r'`(\w+)` \d+', ligne_non_tracees))

        # ⚠️⚠️ ON PARSE, ON NE CHERCHE PAS DES SOUS-CHAÎNES. Ma première version
        # testait `` `zone` n `` avec un espace final : elle ratait `` `a6` 2) ``
        # en fin de parenthèse et accusait une ligne JUSTE. *Un relevé par
        # sous-chaîne se casse sur la ponctuation ; on dérive les deux côtés et
        # on compare des structures.*
        publiee = {z: int(n) for z, n in re.findall(r'`(\w+)` (\d+)', ligne)}
        attendue = {z: n for z, n in par_zone.items() if z not in non_tracees}
        self.assertEqual(
            publiee, attendue,
            f"la répartition publiée ne correspond plus à l'archive.\n"
            f"  publiée : {dict(sorted(publiee.items()))}\n"
            f"  dérivée : {dict(sorted(attendue.items()))}")

        total_trie = sum(attendue.values())
        self.assertIn(
            f'| **{total_trie}** |', ligne,
            f"le total des zones triées vaut {total_trie}, la feuille publie "
            f"autre chose : {ligne.strip()[:200]}")
        print(f"    OK ARCH-6 répartition par zone concordante : "
              f"{total_trie} triés + "
              f"{sum(par_zone.get(z, 0) for z in non_tracees)} jamais tracés")


if __name__ == '__main__':
    unittest.main()
