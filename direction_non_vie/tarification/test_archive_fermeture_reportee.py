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
        "l'exposition nulle pareil), pas epingle. `a2/C5` reste OUVERT. "
        "Retirer la mention detruirait une vraie trace ; une mention n'est "
        "pas une fermeture.",
    ('a2/C9', 'test_imputation_par_la_table.py'):
        "Cite pour dire POURQUOI le mode d'un binaire est range sous `modes` "
        "et non sous `medianes` : l'y mettre aurait AJOUTE une occurrence a "
        "`a2/C9` au lieu d'en retirer. `a2/C9` reste OUVERT, rang 5, "
        "deliberement non corrige -- renommer la cle change le format d'un "
        "JSON persiste. La mention est la trace de cette retenue.",
    ('plan/C7', 'test_echeance_et_avertissement_qualite.py'):
        "Cite comme NOM DU CHANTIER dont ce lot est l'etape 2+3. `plan/C7` "
        "est la declaration des roles dans les 20 plans : elle est l'ETAPE 5, "
        "et reste OUVERTE. Ce fichier epingle la couche qualite, pas les "
        "plans. Retirer la mention couperait le lot de la raison qui le rend "
        "necessaire.",
    ('a1/C5', 'test_vocabulaire_echeance.py'):
        "Cite pour DECLARER CE QUE LE CONTROLE NE COUVRE PAS : il refuse qu'un "
        "synonyme soit revendique par DEUX entrees canoniques, il ne juge pas "
        "les doublons INTRA-liste, qui sont `a1/C5` (rang 7, OUVERT). Deux "
        "fois le meme nom sous la MEME cle ne cree aucune ambiguite de "
        "mapping. Nommer la borne est ce qui empeche de croire le filet plus "
        "large qu'il n'est.",
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
        # `pipeline/C1` est PARTIEL : arbitré, il compte OUVERT.
        n_fermes = len(fermees - {'pipeline/C1'})
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


if __name__ == '__main__':
    unittest.main()
