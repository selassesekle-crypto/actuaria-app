# -*- coding: utf-8 -*-
"""LE GEL DES LIVRABLES : COMPARER DU CONTENU, PAS DES OCTETS.

Cet outil rend mesurable la phrase << aucun euro n'a bouge >>. Il produit
l'empreinte normalisee des surfaces signees avant et apres un correctif, et
nomme chaque ecart par sa feuille et sa coordonnee.

Trois mesures du 05/09/2026 fondent sa forme, et chacune a sa sentinelle :

  1. DEUX RUNS IDENTIQUES NE RENDENT PAS LES MEMES OCTETS. Un `.docx` de
     contenu identique produit a deux instants differe : le ZIP horodate ses
     entrees. Et sa TAILLE bouge aussi (41 588 puis 41 589 octets) parce que
     `deflate` comprime differemment un horodatage qui a change de minute.
     -> comparer des octets, ou des tailles, c'est un rouge par minute.

  2. IL Y A DEUX CONVENTIONS D'HEURE dans les surfaces signees :
     `entete_livrable.genere_le()` rend << 05/09/2026 01:46 >>, et
     `rapport_modeles_tarif.valeur_audit()` rend << 05/09/2026 a 01 h 46 >>.
     Un normaliseur qui n'en connait qu'une rougit une minute sur deux.

  3. ET ON NE PEUT PAS EFFACER TOUTE DATE. `libelle_arrete()` rend
     << 30/06/2026 >> -- la date d'ARRETE, du contenu signe, de forme
     identique a une impression. La distinction retenue est STRUCTURELLE :
     une date SUIVIE D'UNE HEURE est une impression, une date SEULE est du
     metier.

Ce que cette sentinelle exige :
  GEL-1   l'horodatage du VRAI producteur est neutralise, aucun chiffre ne
          survit ;
  GEL-2   le rendu francais de la piste d'audit l'est aussi ;
  GEL-3   la date d'ARRETE, elle, SURVIT -- sinon le gel est aveugle au champ
          le plus lourd du document ;
  GEL-4   deux Word de contenu identique, d'octets differents, ont la MEME
          empreinte ;
  GEL-5   l'extraction Word ne lit QUE `<w:t>` : un changement de style ne
          produit aucun ecart, un changement de texte en produit un ;
  GEL-6   une cellule Excel changee est vue, NOMMEE par feuille et coordonnee ;
  GEL-7   une surface presente d'un seul cote est un ECART, pas un silence ;
  GEL-8   une surface devenue ILLISIBLE est un ecart, et le verdict publie son
          assiette ;
  GEL-9   l'inventaire des livrables ENUMERE : une cle `_bytes` ajoutee demain
          entre dans la mesure sans toucher au code ;
  GEL-10  aucune taille en octets n'entre dans l'empreinte ;
  GEL-11  la chaine est reellement DETERMINISTE : A3 deux fois, meme empreinte.
  GEL-12  l'assiette couvre TOUTE la chaine -- chaque source porte une surface
          REELLE, et l'assiette mesuree se declare dans le message ;
  GEL-13  l'instrument ROUGIT quand un chiffre publie change, dans TOUTES les
          surfaces qui le portent -- et reste muet quand rien ne change.

⚠️⚠️ POURQUOI GEL-12 ET GEL-13 EXISTENT -- constat `TR-2`, mesure du
06/09/2026. Le module etait juste et son assiette effective etait **l'Excel
d'A3, et rien d'autre** : son seul consommateur etait `GEL-11`, qui fait
tourner A1->A2->A3. Mesure de la chaine reelle : **14 livrables non vides**
sur huit sources (A1..A6 + les deux rapports). *Les quatre constats publies de
l'audit vivent tous dans des surfaces que le gel ne regardait pas.*

⚠️⚠️ ET LE DETERMINISME A ETE MESURE AVANT D'ETENDRE QUOI QUE CE SOIT, parce
que sans lui l'outil MENT : deux runs complets, meme processus, **0 ecart sur
les 14 surfaces** -- A4 entraine pourtant six modeles ML et A5 deux reseaux
torch. Un << 0 >> pouvant aussi etre un instrument qui ne mesure rien, il a
ete INSTRUIT : la date d'arrete rend 16 ecarts sur 5 surfaces, un
`score_global` decale de 0,0137 en rend 7, le nom du modele retenu 7. C'est ce
que `GEL-13` fige.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""
import io
import os
import sys
import unittest
import warnings
import zipfile

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

from direction_non_vie.tarification.services import entete_livrable as EL
from direction_non_vie.tarification.services import gel_livrables as G
from direction_non_vie.tarification.services.rapport_modeles_tarif import (
    valeur_audit,
)


def _lire_texte(chemin: str) -> str:
    """Le texte d'un fichier, lu ET REFERME.

    ⚠️ `open(...).read()` laisse le descripteur a la merci du ramasse-miettes.
    Sur Windows un fichier reste alors verrouille assez longtemps pour qu'une
    ecriture suivante echoue -- et le sceau de ce lot REECRIT precisement ce
    fichier-la, sept fois."""
    import pathlib as _pl
    return _pl.Path(chemin).read_text(encoding='utf-8')


# =============================================================================
#  FABRIQUES — de vrais fichiers, jamais des octets simules
# =============================================================================

def _docx(paragraphes, largeur=2400, fond='EEF2F7'):
    """Un vrai .docx : un tableau d'une colonne, style parametrable."""
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = Document()
    table = doc.add_table(rows=len(paragraphes), cols=1)
    for indice, texte in enumerate(paragraphes):
        cellule = table.rows[indice].cells[0]
        cellule.paragraphs[0].add_run(str(texte))
        proprietes = cellule._tc.get_or_add_tcPr()
        largeur_el = OxmlElement('w:tcW')
        largeur_el.set(qn('w:w'), str(largeur))
        largeur_el.set(qn('w:type'), 'dxa')
        proprietes.append(largeur_el)
        ombre = OxmlElement('w:shd')
        ombre.set(qn('w:val'), 'clear')
        ombre.set(qn('w:fill'), fond)
        proprietes.append(ombre)
    flux = io.BytesIO()
    doc.save(flux)
    return flux.getvalue()


def _xlsx(feuilles):
    """Un vrai .xlsx : {nom de feuille: {coordonnee: valeur}}."""
    from openpyxl import Workbook

    classeur = Workbook()
    classeur.remove(classeur.active)
    for nom, cellules in feuilles.items():
        feuille = classeur.create_sheet(nom)
        for coordonnee, valeur in cellules.items():
            feuille[coordonnee] = valeur
    flux = io.BytesIO()
    classeur.save(flux)
    return flux.getvalue()


def _rehorodater(octets, decalage_s=120):
    """Le MEME contenu, un ZIP horodate autrement.

    ⚠️⚠️ POURQUOI PAS UN `time.sleep()` : **mesure du 05/09/2026**, l'horodatage
    ZIP avance par pas de DEUX secondes (58 -> 0 -> 2). Une pause d'une seconde
    retombe une fois sur deux dans le meme palier, les octets sortent
    identiques, et le test rougit au hasard. C'est le sceau qui l'a trouve, en
    relancant la suite six fois. Ici le decalage est impose, donc reproductible.
    """
    lu = zipfile.ZipFile(io.BytesIO(octets))
    flux = io.BytesIO()
    with zipfile.ZipFile(flux, 'w', zipfile.ZIP_DEFLATED) as ecrit:
        for info in lu.infolist():
            annee, mois, jour, heure, minute, seconde = info.date_time
            minute = (minute + decalage_s // 60) % 60
            neuf = zipfile.ZipInfo(info.filename,
                                   (annee, mois, jour, heure, minute, seconde))
            neuf.compress_type = info.compress_type
            ecrit.writestr(neuf, lu.read(info.filename))
    return flux.getvalue()


def _empreinte(livrables):
    return G.empreinte(livrables)


def _ecarts(avant, apres):
    return G.comparer(_empreinte(avant), _empreinte(apres))


# =============================================================================
#  GEL-1 a GEL-3 — LA NORMALISATION, LIEE AUX VRAIS PRODUCTEURS
# =============================================================================

class TestNormalisationLieeAuxProducteurs(unittest.TestCase):
    """La regle n'est pas recopiee ici : elle est verifiee sur la source."""

    def test_GEL1_l_horodatage_de_genere_le_ne_survit_pas(self):
        """⚠️ On appelle le VRAI producteur. Une liste de formats recopiee se
        met a jour a moitie ; un controle qui appelle la source suit."""
        brut = EL.genere_le()
        neutre = G.neutraliser(brut)
        self.assertNotEqual(brut, neutre,
                            f"l'horodatage de production {brut!r} n'a pas ete "
                            "neutralise")
        self.assertFalse(any(c.isdigit() for c in neutre),
                         f"des chiffres survivent dans {neutre!r} : deux runs "
                         "a une minute d'ecart rougiraient")

    def test_GEL1b_la_phrase_complete_du_livrable_est_neutralisee(self):
        """C'est la phrase telle qu'elle figure dans les classeurs."""
        phrase = f'Généré le : {EL.genere_le()}'
        neutre = G.neutraliser(phrase)
        self.assertNotIn(':', neutre.replace('Généré le :', ''),
                         f'une heure survit dans {neutre!r}')
        self.assertFalse(any(c.isdigit() for c in neutre), neutre)

    def test_GEL2_le_rendu_francais_de_la_piste_d_audit_ne_survit_pas(self):
        """`valeur_audit` rend << 05/09/2026 a 01 h 46 >>. Mesure : c'est le
        SEUL ecart qui restait entre deux runs de la chaine complete."""
        rendu = valeur_audit('2026-09-05T01:46:12.123456')
        self.assertIn(' h ', rendu,
                      f'le producteur a change de forme : {rendu!r} -- la '
                      'sentinelle doit etre relue avec lui')
        neutre = G.neutraliser(rendu)
        self.assertFalse(any(c.isdigit() for c in neutre),
                         f'des chiffres survivent dans {neutre!r}')

    def test_GEL3_la_date_d_arrete_SURVIT_a_la_neutralisation(self):
        """⚠️⚠️ LE COEUR. Une date d'arrete a la meme forme qu'une impression.
        L'effacer rendrait le gel aveugle au champ le plus lourd du document.

        ⚠️⚠️ ET CE TEST A DEJA ATTESTE SANS SURVEILLER. Ecrit d'abord sur
        `30/06/2026`, il passait -- mais `core/arrete.py` DERIVE une fin de
        trimestre en << T2 2026 >>, qui n'a AUCUNE collision de forme avec un
        horodatage. Le cas dangereux est la date HORS fin de trimestre, seule
        a ressortir en `jj/mm/aaaa`. Mesure du 05/09/2026 :
            30/06/2026 -> << T2 2026 >>     (libelle derive, aucun risque)
            15/05/2026 -> << 15/05/2026 >>  (COLLISION -- le vrai cas)
        """
        derive = EL.libelle_arrete('30/06/2026')
        self.assertNotRegex(derive, r'\d{2}/\d{2}/\d{4}',
                            'core/arrete a change de rendu : ce test doit '
                            'etre relu avec lui')
        collision = EL.libelle_arrete('15/05/2026')
        self.assertRegex(collision, r'^15/05/2026$',
                         "le cas de COLLISION n'existe plus sous cette forme : "
                         'sans lui ce test ne surveille rien')
        self.assertEqual(G.neutraliser(collision), collision,
                         "la date d'arrete a ete neutralisee : un changement "
                         "d'arrete passerait desormais inapercu")

    def test_GEL3b_un_arrete_qui_change_produit_un_ecart(self):
        """La contre-epreuve, sur le cas de COLLISION exclusivement."""
        avant = {'Word': _docx([f'Arrêté : {EL.libelle_arrete("15/05/2026")}',
                                f'Généré le : {EL.genere_le()}'])}
        apres = {'Word': _docx([f'Arrêté : {EL.libelle_arrete("16/05/2026")}',
                                f'Généré le : {EL.genere_le()}'])}
        ecarts = _ecarts(avant, apres)
        self.assertEqual(len(ecarts), 1, G.rapport_ecarts(
            ecarts, _empreinte(avant), _empreinte(apres)))
        self.assertIn('15/05/2026', str(ecarts[0].avant))
        self.assertIn('16/05/2026', str(ecarts[0].apres))

    def test_GEL3c_un_identifiant_d_audit_PREFIXE_est_neutralise(self):
        """⚠️⚠️ `\\b\\d{8}_\\d{6}\\b` NE MORD PAS `A3_20260905_015505` : entre
        `_` et `2` il n'y a pas de frontiere de mot. Le motif ne voyait que la
        forme nue. Trouve par GEL-11, pas par relecture."""
        for identifiant in ('A3_20260905_015505', 'Audit ID : A6_20260905_015505',
                            '20260905_015505', 'A5_20260905_015505_v2'):
            neutre = G.neutraliser(identifiant)
            self.assertIn('<horodatage>', neutre,
                          f'{identifiant!r} reste horodate : deux runs a une '
                          'seconde d ecart rougiraient')


# =============================================================================
#  GEL-4, GEL-5, GEL-10 — LE WORD : DU CONTENU, NI OCTETS NI STYLE
# =============================================================================

class TestWordContenuSeul(unittest.TestCase):

    def test_GEL4_meme_contenu_octets_differents_empreinte_identique(self):
        """⚠️⚠️ LA MESURE FONDATRICE. Deux .docx de contenu identique produits
        a deux instants n'ont PAS les memes octets (le ZIP horodate ses
        entrees). Un gel par empreinte SHA-256 serait rouge en permanence."""
        textes = ['Prime pure moyenne', '412,55 EUR', 'Arrêté : 15/05/2026']
        premier = _docx(textes)
        second = _rehorodater(premier)
        self.assertNotEqual(premier, second,
                            'les octets sont identiques : la mesure qui fonde '
                            'cet outil ne se reproduit plus, relire le lot')
        self.assertEqual(_ecarts({'Word': premier}, {'Word': second}), [],
                         'du contenu identique produit un ecart')

    def test_GEL5_un_changement_de_STYLE_ne_produit_aucun_ecart(self):
        """⚠️⚠️ `<w:t[^>]*>` mord aussi `<w:tcPr>` et `<w:tcW>`. Mesure du
        05/09/2026 : l'extraction remontait des largeurs de colonne comme du
        contenu signe. Une largeur qui change n'est pas un tarif qui change."""
        textes = ['Modèle retenu', 'GLM Poisson']
        etroit = _docx(textes, largeur=2400, fond='EEF2F7')
        large = _docx(textes, largeur=5953, fond='FFFFFF')
        self.assertNotEqual(etroit, large, 'les deux docx sont identiques : '
                                           'le plant ne teste rien')
        ecarts = _ecarts({'Word': etroit}, {'Word': large})
        self.assertEqual(ecarts, [], 'un changement de style a ete annonce '
                                     'comme un changement de contenu :\n'
                         + G.rapport_ecarts(ecarts, _empreinte({'Word': etroit}),
                                            _empreinte({'Word': large})))

    def test_GEL5b_un_changement_de_TEXTE_produit_un_ecart_nomme(self):
        """La contre-epreuve du meme plant : le filet voit-il encore ?"""
        avant = _docx(['Modèle retenu', 'GLM Poisson'])
        apres = _docx(['Modèle retenu', 'LightGBM'])
        ecarts = _ecarts({'Word': avant}, {'Word': apres})
        self.assertEqual(len(ecarts), 1, G.rapport_ecarts(
            ecarts, _empreinte({'Word': avant}), _empreinte({'Word': apres})))
        self.assertEqual(ecarts[0].avant, 'GLM Poisson')
        self.assertEqual(ecarts[0].apres, 'LightGBM')
        self.assertIn('word/document.xml', ecarts[0].emplacement)

    def test_GEL10_aucune_taille_n_entre_dans_l_empreinte(self):
        """⚠️ Le resultat d'A6 publie `livrables_tailles`. Mesure : cette
        table bouge entre deux runs identiques. Elle ne doit atteindre ni
        l'inventaire des livrables, ni l'empreinte."""
        resultat = {'word_bytes': _docx(['a']),
                    'livrables_tailles': {'Word tarification': 41588}}
        inventaire = G.livrables_d_un_resultat(resultat)
        self.assertNotIn('livrables_tailles', inventaire)
        self.assertEqual(sorted(inventaire), ['Word'])
        textuel = repr(_empreinte(inventaire).contenus)
        self.assertNotIn('41588', textuel)


# =============================================================================
#  GEL-6 — L'EXCEL : LA COORDONNEE VOYAGE AVEC LA VALEUR
# =============================================================================

class TestExcelCoordonnee(unittest.TestCase):

    def test_GEL6_une_cellule_changee_est_vue_et_NOMMEE(self):
        avant = _xlsx({'1-Synthèse': {'A1': 'Prime pure', 'B1': 412.55,
                                      'A2': 'Gini', 'B2': 0.2651}})
        apres = _xlsx({'1-Synthèse': {'A1': 'Prime pure', 'B1': 418.90,
                                      'A2': 'Gini', 'B2': 0.2651}})
        ecarts = _ecarts({'Excel': avant}, {'Excel': apres})
        self.assertEqual(len(ecarts), 1, G.rapport_ecarts(
            ecarts, _empreinte({'Excel': avant}), _empreinte({'Excel': apres})))
        self.assertIn('1-Synthèse', ecarts[0].emplacement)
        self.assertIn('B1', ecarts[0].emplacement)
        self.assertEqual((ecarts[0].avant, ecarts[0].apres), (412.55, 418.90))

    def test_GEL6b_une_feuille_ajoutee_est_vue(self):
        avant = _xlsx({'1-Synthèse': {'A1': 'x'}})
        apres = _xlsx({'1-Synthèse': {'A1': 'x'}, '2-Classement': {'A1': 'y'}})
        ecarts = _ecarts({'Excel': avant}, {'Excel': apres})
        self.assertTrue(ecarts, 'une feuille entiere ajoutee est passee')
        self.assertTrue(any('2-Classement' in e.emplacement for e in ecarts),
                        [str(e) for e in ecarts])

    def test_GEL6c_deux_classeurs_identiques_ne_produisent_rien(self):
        cellules = {'1-Synthèse': {'A1': 'Prime', 'B1': 412.55,
                                   'A4': f'Généré le : {EL.genere_le()}',
                                   'A5': 'Audit ID : A3_20260905_015505'}}
        premier = _xlsx(cellules)
        second = _rehorodater(_xlsx(cellules))
        self.assertNotEqual(premier, second)
        self.assertEqual(_ecarts({'Excel': premier}, {'Excel': second}), [])


# =============================================================================
#  GEL-7, GEL-8 — L'ABSENCE ET L'ILLISIBLE SONT DES VALEURS
# =============================================================================

class TestAbsenceEtIllisible(unittest.TestCase):

    def test_GEL7_une_surface_presente_d_un_seul_cote_est_un_ecart(self):
        """⚠️⚠️ LE PIEGE DU RELAIS FIDELE A UNE ABSENCE. Un controle qui
        compare deux `None` reste vert sans avoir rien surveille."""
        avant = {'Excel': _xlsx({'S': {'A1': 'x'}}), 'Word': _docx(['y'])}
        apres = {'Excel': _xlsx({'S': {'A1': 'x'}}), 'Word': b''}
        ecarts = _ecarts(avant, apres)
        self.assertEqual(len(ecarts), 1, [str(e) for e in ecarts])
        self.assertEqual(ecarts[0].surface, 'Word')
        self.assertEqual(ecarts[0].apres, G.ABSENT)

    def test_GEL7b_deux_absences_reelles_ne_sont_pas_un_ecart(self):
        """La contre-epreuve : le gel ne crie pas sur un PDF jamais demande."""
        self.assertEqual(_ecarts({'PDF': b''}, {'PDF': None}), [])

    def test_GEL7c_une_surface_qui_n_existe_meme_plus_est_un_ecart(self):
        """⚠️ CAS DISTINCT DE GEL-7, et il etait NON COUVERT : la surface n'est
        pas vide, elle a disparu de l'inventaire. Le sceau l'a montre -- le
        plant qui neutralisait cette branche ne faisait rougir personne."""
        avant = {'Excel': _xlsx({'S': {'A1': 'x'}})}
        apres = {'Excel': _xlsx({'S': {'A1': 'x'}}),
                 'Rapport equipe PDF': _docx(['nouveau livrable'])}
        ecarts = _ecarts(avant, apres)
        self.assertEqual(len(ecarts), 1, [str(e) for e in ecarts])
        self.assertEqual(ecarts[0].surface, 'Rapport equipe PDF')
        self.assertEqual(ecarts[0].avant, G.ABSENT)

    def test_GEL8_une_surface_devenue_illisible_est_un_ecart(self):
        """Sinon un export casse passerait pour << rien n'a change >>."""
        bon = _xlsx({'S': {'A1': 'x'}})
        casse = b'PK\x03\x04' + b'\x00' * 60
        ecarts = _ecarts({'Excel': bon}, {'Excel': casse})
        self.assertTrue(ecarts, "un classeur devenu illisible n'a produit "
                                'aucun ecart')

    def test_GEL8b_le_verdict_publie_son_assiette_et_ses_non_lues(self):
        """⚠️ << 0 ecart >> ne peut pas taire une surface illisible.
        Un chiffre se publie avec la methode qui l'a produit."""
        illisible = b'%PDF-1.4 corrompu'
        emp = _empreinte({'Excel': _xlsx({'S': {'A1': 'x'}}), 'PDF': illisible})
        texte = G.rapport_ecarts(G.comparer(emp, emp), emp, emp)
        self.assertIn('0 ecart', texte)
        self.assertIn('assiette', texte)
        self.assertIn('NON LUES', texte, texte)
        self.assertIn('PDF', texte)


# =============================================================================
#  GEL-9 — L'INVENTAIRE ENUMERE, IL NE DECLARE PAS
# =============================================================================

class TestListesComparees(unittest.TestCase):
    """GEL-14 — UNE INSERTION NE DOIT PAS FAIRE ROUGIR TOUT CE QUI SUIT.

    ⚠️⚠️ TROUVE EN M'EN SERVANT, AU LOT 3. Ajouter deux libelles au chapitre 5
    du rapport d'equipe rendait **169 ecarts**, dont 167 n'etaient que le
    decalage des lignes suivantes. C'est le defaut que ce module nomme deja
    pour l'Excel -- la coordonnee voyage avec la valeur -- et qu'il n'avait pas
    ferme pour les listes. *Un verdict noye dans son propre bruit ne se lit
    plus, et c'est au lot qui deplace un prix qu'il faudra le lire.*
    """

    @staticmethod
    def _comparer(avant, apres):
        return G.comparer(G.Empreinte(contenus={'S': avant}),
                          G.Empreinte(contenus={'S': apres}))

    def test_GEL14_une_insertion_ne_rougit_QUE_la_ligne_inseree(self):
        avant = ['a', 'b', 'c', 'd', 'e']
        apres = ['a', 'b', 'NOUVELLE', 'c', 'd', 'e']
        ecarts = self._comparer(avant, apres)
        self.assertEqual(
            len(ecarts), 1,
            f'{len(ecarts)} ecart(s) pour UNE insertion : les lignes '
            f'suivantes sont comptees comme changees. {[str(e) for e in ecarts]}')
        self.assertIn('NOUVELLE', str(ecarts[0]))
        print('    GEL-14 insertion : 1 ecart, pas 4')

    def test_GEL14b_a_longueur_EGALE_le_couple_avant_apres_est_conserve(self):
        """⚠️ LE SECOND SENS. Comparer par multi-ensemble PARTOUT decouperait
        une modification en place en une disparition et une apparition, sans
        les relier -- et `GEL-3b` comme `GEL-5b` exigent ce couple. La regle
        est : meme longueur -> par le RANG, longueur differente -> par le
        CONTENU."""
        ecarts = self._comparer(['a', '30/06/2026', 'c'],
                                ['a', '31/12/2026', 'c'])
        self.assertEqual(len(ecarts), 1)
        self.assertEqual(ecarts[0].avant, '30/06/2026')
        self.assertEqual(ecarts[0].apres, '31/12/2026')
        print('    GEL-14b modification en place : couple avant/apres conserve')

    def test_GEL14c_une_ligne_en_DOUBLE_reste_un_ecart(self):
        """⚠️ Le MULTI-ensemble, pas l'ensemble : un `set` effacerait une
        ligne presente deux fois avant et une seule fois apres."""
        ecarts = self._comparer(['x', 'x', 'y'], ['x', 'y'])
        self.assertTrue(ecarts, "la perte d'un doublon n'est pas vue")


class TestInventaireEnumere(unittest.TestCase):

    def test_GEL9_une_cle_bytes_INCONNUE_entre_dans_la_mesure(self):
        """⚠️⚠️ Une table tenue a la main aurait diverge le jour ou un export
        nouveau apparait -- et l'assiette se serait retrecie en silence."""
        resultat = {'excel_bytes': b'x', 'csv_bytes': b'y', 'statut_rag': 'VERT'}
        inventaire = G.livrables_d_un_resultat(resultat)
        self.assertIn('csv', inventaire,
                      "une cle `_bytes` inconnue n'entre pas dans la mesure : "
                      "l'inventaire DECLARE au lieu d'ENUMERER")
        self.assertNotIn('statut_rag', inventaire)

    def test_GEL9b_le_rapport_equipe_est_ouvert_d_un_cran(self):
        resultat = {'rapport_equipe': {'excel_bytes': b'a', 'pdf_bytes': b'b'}}
        inventaire = G.livrables_d_un_resultat(resultat)
        self.assertEqual(sorted(inventaire),
                         ['Rapport equipe Excel', 'Rapport equipe PDF'])

    def test_GEL9c_le_format_se_derive_des_octets_pas_de_la_cle(self):
        """Une cle qui ment sur son contenu ne trompe pas la lecture."""
        self.assertEqual(G.format_livrable(_xlsx({'S': {'A1': 1}})), 'xlsx')
        self.assertEqual(G.format_livrable(_docx(['a'])), 'docx')
        self.assertEqual(G.format_livrable(b'<!DOCTYPE html><p>x</p>'), 'html')
        self.assertEqual(G.format_livrable(b''), 'vide')


# =============================================================================
#  GEL-11 — LA CHAINE EST-ELLE REELLEMENT DETERMINISTE ?
# =============================================================================

class TestDeterminismeReel(unittest.TestCase):
    """Sans cette propriete l'outil ment : il attribuerait a un correctif un
    ecart que la chaine produit toute seule."""

    def test_GEL11_A3_deux_fois_rend_la_meme_empreinte(self):
        warnings.filterwarnings('ignore')
        import numpy as np

        from core.qualite_donnees import preambule_qualite
        from direction_non_vie.tarification import test_pipeline_agents as T
        from direction_non_vie.tarification.a1_ingestion.agent import (
            AgentA1Ingestion,
        )
        from direction_non_vie.tarification.a2_preprocessing.agent import (
            AgentA2Preprocessing,
        )
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM

        def un_run():
            np.random.seed(7)
            donnees = T._portefeuille_auto(1200)
            plan = T._PLAN_AUTO
            base = {'audit_path': '/tmp', 'verbose': False}
            r1 = AgentA1Ingestion(**base).run(branche='non_vie',
                                              sous_branche='auto',
                                              dataframe=donnees)
            qualite = preambule_qualite(r1.get('dataframe'), plan,
                                        qualite_validee_par='Actuaire Test',
                                        horodatage=None)
            r1 = {**r1, 'dataframe': qualite.dataframe_propre}
            r2 = AgentA2Preprocessing(**base).run(result_a1=r1, plan=plan)
            r3 = AgentA3GLM(models_path='/tmp', audit_path='/tmp').run(
                result_a2=r2, plan=plan, col_frequence=plan.cible_frequence,
                col_cout=plan.cible_cout, generer_graphiques=False)
            return G.empreinte(G.livrables_d_un_resultat(r3))

        premier, second = un_run(), un_run()
        # ⚠️⚠️ L'ASSIETTE SE DECLARE. Sans ces trois lignes, un run ou A3 ne
        # produirait PLUS AUCUN classeur laisserait ce test vert : trois
        # surfaces `<livrable absent>` des deux cotes sont fidelement egales.
        # Un relais fidele a une absence est encore une absence.
        self.assertEqual(premier.non_lues, {}, premier.non_lues)
        reelles = [nom for nom, contenu in premier.contenus.items()
                   if contenu != G.ABSENT]
        self.assertIn('Excel', reelles,
                      "A3 n'a produit aucun classeur lisible : ce controle ne "
                      f'mesurerait rien. Surfaces vues : {premier.surfaces()}')
        self.assertGreaterEqual(
            sum(len(cellules) for cellules in premier.contenus['Excel'].values()),
            50, 'le classeur mesure est presque vide')
        ecarts = G.comparer(premier, second)
        self.assertEqual(ecarts, [], G.rapport_ecarts(ecarts, premier, second))


# =============================================================================
#  GEL-12, GEL-13 — L'ASSIETTE COUVRE-T-ELLE LA CHAINE, ET REPOND-ELLE ?
# =============================================================================

#: Les sources attendues dans l'assiette. ⚠️ Cette liste ne CONSTRUIT rien :
#: `livrables_de_la_chaine` enumere ce qu'on lui donne. Elle dit ce que le
#: chantier EXIGE de couvrir, pour qu'une source qui cesserait de produire
#: fasse rougir au lieu de retrecir l'assiette en silence.
_SOURCES_ATTENDUES = ('a1', 'a2', 'a3', 'a4', 'a5', 'a6',
                      'rapport_modeles', 'rapport_equipe')


def _volume(contenu) -> int:
    """Le nombre de valeurs comparables d'une surface, quel que soit sa forme."""
    if isinstance(contenu, dict):
        return sum(_volume(v) for v in contenu.values())
    if isinstance(contenu, (list, tuple)):
        return sum(_volume(v) for v in contenu)
    return 1


class TestAssietteDeLaChaine(unittest.TestCase):
    """⚠️⚠️ CE QUE LE GEL NE REGARDE PAS, IL LE CERTIFIE SANS L'AVOIR VU.

    La chaine tourne UNE fois pour toute la classe : c'est la partie chere
    (~55 s), et les deux controles la partagent.
    """

    _empreinte = None
    _motif_a5 = ''

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        import numpy as np

        from core.qualite_donnees import preambule_qualite
        from direction_non_vie.tarification import test_pipeline_agents as T
        from direction_non_vie.tarification.a1_ingestion.agent import (
            AgentA1Ingestion,
        )
        from direction_non_vie.tarification.a2_preprocessing.agent import (
            AgentA2Preprocessing,
        )
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        from direction_non_vie.tarification.a6_comparaison.agent import (
            AgentA6Comparaison,
        )

        np.random.seed(7)
        plan = T._PLAN_AUTO
        donnees = T._portefeuille_auto(1200)
        # ⚠️ SANS COLONNE TEMPORELLE, A6 NE FAIT PAS DE WALK-FORWARD et son
        # chapitre de backtesting se vide : l'assiette mesuree serait plus
        # etroite que celle d'un vrai dossier.
        donnees['annee_souscription'] = np.random.default_rng(7).choice(
            [2021, 2022, 2023, 2024, 2025], len(donnees))
        base = {'audit_path': '/tmp', 'verbose': False}

        r1 = AgentA1Ingestion(**base).run(branche='non_vie',
                                          sous_branche='auto',
                                          dataframe=donnees, plan=plan)
        qualite = preambule_qualite(r1.get('dataframe'), plan,
                                    qualite_validee_par='Actuaire Test',
                                    horodatage=None)
        r2 = AgentA2Preprocessing(**base).run(
            result_a1={**r1, 'dataframe': qualite.dataframe_propre}, plan=plan)
        r3 = AgentA3GLM(models_path='/tmp', audit_path='/tmp').run(
            result_a2=r2, plan=plan, col_frequence=plan.cible_frequence,
            col_cout=plan.cible_cout, generer_graphiques=True)
        r4 = AgentA4ML(models_path='/tmp', audit_path='/tmp').run(
            result_a2=r2, result_a3=r3, plan=plan, col_cible='nb_sinistres',
            ponderer_par_exposition=True, calcul_shap=False,
            generer_graphiques=True)
        # ⚠️ A5 depend de `torch`, declare dans requirements-optional. Son
        # ABSENCE se declare (`_motif_a5`) et fait SAUTER le controle de sa
        # source ; toute autre panne doit rougir.
        r5: dict = {}
        try:
            from direction_non_vie.tarification.a5_deep_learning.agent import (
                AgentA5DeepLearning,
            )
            r5 = AgentA5DeepLearning(models_path='/tmp',
                                     audit_path='/tmp').run(
                result_a2=r2, result_a3=r3, plan=plan,
                col_cible='nb_sinistres', generer_graphiques=True)
        except ImportError as erreur:
            cls._motif_a5 = f'torch absent : {erreur}'
        r6 = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp').run(
            result_a2=r2, result_a3=r3, result_a4=r4,
            result_a5=r5 if r5.get('success') else None,
            col_cible='nb_sinistres', plan=plan, environnement='production',
            profil_valide_par='Actuaire Test', generer_graphiques=True,
            generer_rapport_equipe=False)

        cls._a3, cls._a4, cls._a5, cls._a6 = r3, r4, r5, r6
        cls._amont = {'a1': r1, 'a2': r2}
        resultats = {'a1': r1, 'a2': r2, 'a3': r3, 'a4': r4, 'a5': r5,
                     'a6': r6,
                     'rapport_modeles': cls._rapport_modeles(r6),
                     'rapport_equipe': cls._rapport_equipe(r1, r2, r3, r4,
                                                           r5, r6)}
        cls._empreinte = G.empreinte(G.livrables_de_la_chaine(resultats))

    @classmethod
    def _rapport_modeles(cls, r6, formats=('html', 'word')):
        from direction_non_vie.tarification.services import (
            rapport_modeles_tarif as RM,
        )
        return RM.generer_rapport_tarification(
            result_a3=cls._a3, result_a4=cls._a4, result_a6=r6,
            result_a5=cls._a5 if cls._a5.get('success') else None,
            ref_client='GEL', arrete='2026-06-30', audit_id='GEL-12',
            formats=list(formats))

    @classmethod
    def _rapport_equipe(cls, r1, r2, r3, r4, r5, r6,
                        formats=('html', 'word', 'excel')):
        from direction_non_vie.tarification.services import (
            rapport_equipe_tarif as RE,
        )
        return RE.generer_rapport_equipe_tarification(
            {'a1': r1, 'a2': r2, 'a3': r3, 'a4': r4, 'a5': r5, 'a6': r6},
            branche='non_vie', arrete='2026-06-30', audit_id='GEL-12',
            formats=list(formats))

    # ── GEL-12 ───────────────────────────────────────────────────────────────
    def test_GEL12_chaque_source_de_la_chaine_porte_une_surface_REELLE(self):
        """⚠️⚠️ COMPTER LES SURFACES NE SUFFIT PAS : trois `<livrable absent>`
        des deux cotes sont fidelement egaux, et un gel qui les compterait
        rendrait << 0 ecart >> en n'ayant rien regarde. On exige donc, PAR
        SOURCE, au moins une surface au contenu REEL.
        """
        empreinte = self._empreinte
        self.assertEqual(empreinte.non_lues, {},
                         f'surfaces illisibles : {empreinte.non_lues}')
        volumes: dict[str, dict[str, int]] = {}
        for nom, contenu in empreinte.contenus.items():
            if contenu == G.ABSENT:
                continue
            source = nom.split(' ', 1)[0]
            volumes.setdefault(source, {})[nom] = _volume(contenu)

        assiette = ' | '.join(
            f'{source}: ' + ', '.join(f'{n.split(" ", 1)[1]}={v}'
                                      for n, v in sorted(surfaces.items()))
            for source, surfaces in sorted(volumes.items()))
        for source in _SOURCES_ATTENDUES:
            with self.subTest(source=source):
                if source == 'a5' and self._motif_a5:
                    self.skipTest(self._motif_a5)
                reelles = volumes.get(source, {})
                self.assertTrue(
                    reelles,
                    f"la source « {source} » ne porte AUCUNE surface reelle : "
                    f"le gel la certifierait sans l'avoir vue.\n"
                    f'assiette mesuree -- {assiette}')
                self.assertGreaterEqual(
                    max(reelles.values()), 20,
                    f"la plus grosse surface de « {source} » ne porte que "
                    f'{max(reelles.values())} valeurs comparables : ce n est '
                    f'pas un livrable.\nassiette mesuree -- {assiette}')
        total = sum(len(s) for s in volumes.values())
        self.assertGreaterEqual(
            total, 12,
            f'assiette trop etroite : {total} surfaces reelles.\n{assiette}')
        print(f'    GEL-12 assiette : {len(volumes)} sources, {total} surfaces '
              f'reelles, 0 illisible')

    # ── GEL-13 ───────────────────────────────────────────────────────────────
    def test_GEL13_un_chiffre_publie_qui_change_ROUGIT_TOUTES_ses_surfaces(self):
        """⚠️⚠️ UN GEL QUI NE ROUGIT PAS EST UN GEL QUI ATTESTE SANS
        SURVEILLER. Le controle negatif (rien ne change -> 0) est declare ici
        AVEC le controle positif : sans lui, un instrument mort passerait les
        deux.

        Rendu HTML seul : c'est le format le moins cher, et il suffit a
        prouver que la reponse existe dans les DEUX rapports.
        """
        import copy

        def empreinte_html(r6):
            livrables = G.livrables_de_la_chaine({
                'rapport_modeles': self._rapport_modeles(r6, formats=('html',)),
                'rapport_equipe': self._rapport_equipe(
                    self._amont['a1'], self._amont['a2'], self._a3, self._a4,
                    self._a5, r6, formats=('html',)),
            })
            return G.empreinte(livrables)

        reference = empreinte_html(self._a6)
        portantes = [n for n, c in reference.contenus.items()
                     if c != G.ABSENT]
        self.assertEqual(
            len(portantes), 2,
            f'les deux rapports devaient rendre un HTML : {portantes}')

        # ── controle NEGATIF, declare : rien ne change -> aucun ecart
        muet = G.comparer(reference, empreinte_html(self._a6))
        self.assertEqual(muet, [], G.rapport_ecarts(muet, reference, reference))

        # ── controle POSITIF : le nom du modele retenu change
        perturbe = copy.deepcopy(self._a6)
        perturbe['modele_production']['modele'] = 'MODELE_PLANTE_XYZ'
        ecarts = G.comparer(reference, empreinte_html(perturbe))
        self.assertTrue(
            ecarts,
            'le modele de production a change et le gel est reste MUET : il '
            'atteste sans surveiller.')
        touchees = {e.surface for e in ecarts}
        self.assertEqual(
            touchees, set(portantes),
            f'le changement n a ete vu que dans {sorted(touchees)} alors que '
            f'{sorted(portantes)} le publient : le gel voit une surface sur '
            f'deux, exactement le defaut qu il doit attraper.')
        print(f'    GEL-13 muet a l identique · {len(ecarts)} ecart(s) sur '
              f'{len(touchees)} surface(s) quand le modele retenu change')


class TestLaReferenceDeContenu(unittest.TestCase):
    """GEL-15 — LE GEL ETAIT UN INSTRUMENT, PAS UNE SENTINELLE.

    ⚠️⚠️ LE SEUL MANQUE STRUCTUREL SUR LEQUEL DEUX AUDITS INDEPENDANTS
    TOMBENT D'ACCORD (08/09/2026, signal (4) des deux passes). Tout ce que
    GEL-1 a GEL-14 verifie est juste, et rien de tout cela ne se declenche
    seul : la comparaison est toujours << ce run contre ce run >>, et
    `scripts/gel_avant_apres.py` exige `--sortie` sans defaut, HORS DEPOT.
    *Un changement commite sans que quelqu'un lance la comparaison laissait
    la gate VERTE.* Trois des constats publies de la passe 1 sont exactement
    des changements de livrable que personne n'a vus.

    ⚠️⚠️ ELLE NE VERSIONNE AUCUNE DONNEE. Le fichier de reference ne porte,
    par surface, qu'un sha256 de l'empreinte NORMALISEE. Le depot est PUBLIC :
    c'est la condition pour que cette reference puisse y vivre. L'argument
    << on ne peut pas versionner les livrables >> vaut pour les OCTETS (le ZIP
    horodate, `deflate` varie -- mesure : 41 588 puis 41 589 octets pour un
    contenu identique) ; il ne vaut pas pour un condense.

    ⚠️ LE DETERMINISME A ETE MESURE AVANT D'ECRIRE CETTE CLASSE, et entre
    PROCESSUS DISTINCTS cette fois -- deux invocations separees du lanceur,
    **0 ecart sur les 14 surfaces**, 105 s et 103 s. Sans cela la sentinelle
    serait instable, et une sentinelle instable est pire que pas de
    sentinelle : on apprend a la relancer.

    ⚠️ ET UN ECART N'EST PAS UN ECHEC, C'EST UNE QUESTION. Le message nomme
    les surfaces qui ont bouge et renvoie a `--comparer`, qui dit ecart par
    ecart ce qui a change. Le desarmement (`--figer`) est un geste explicite,
    a justifier au commit.
    """

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        import json
        cls._json = json
        cls._chemin = os.path.join(_ICI, 'reference_gel.json')

    def test_GEL15_la_reference_de_contenu_existe_et_ne_porte_aucune_donnee(
            self):
        """⚠️ LE PREMIER SENS : la reference EXISTE, et elle est publiable.

        Un depot public ne peut pas versionner le contenu d'un livrable de
        demonstration ; il peut versionner un condense. On l'exige."""
        self.assertTrue(
            os.path.exists(self._chemin),
            'la reference de contenu est absente : le gel est redevenu un '
            'instrument qu on lance, et la gate ne voit plus les documents. '
            '`py scripts/gel_avant_apres.py --figer`')
        ref = self._json.loads(_lire_texte(self._chemin))
        self.assertTrue(ref.get('surfaces'), 'aucune surface figee')
        for nom, valeur in ref['surfaces'].items():
            with self.subTest(surface=nom):
                self.assertRegex(
                    str(valeur), r'^sha256:[0-9a-f]{64}$',
                    f'la surface « {nom} » porte autre chose qu un condense : '
                    f'une reference qui porte du CONTENU ne peut pas vivre '
                    f'dans un depot public')
        # ⚠️ ET L'ASSIETTE SE DECLARE A COTE DU VERDICT. Un « 0 ecart » ne
        # vaut que sur l'assiette qui l'a produit -- celle-ci ne porte AUCUN
        # mapping client, et le taire ferait passer un correctif de cette
        # zone pour neutre.
        self.assertTrue(
            ref.get('_assiette_non_couverte'),
            "la reference ne declare pas ce qu'elle NE couvre PAS")
        self.assertTrue(ref.get('jeu', {}).get('graine') is not None,
                        'le jeu d entree ne voyage pas avec la reference')
        print(f'    GEL-15 reference : {len(ref["surfaces"])} surfaces, '
              f'condenses seuls, assiette declaree')

    def test_GEL15b_le_contenu_des_livrables_signes_n_a_pas_bouge(self):
        """⚠️⚠️ LE SECOND SENS, ET C'EST LUI QUI GARDE. On rejoue la chaine
        et on compare surface par surface au condense fige.

        ⚠️ Une surface ILLISIBLE fait rougir avant toute comparaison : un
        « 0 ecart » qui tairait trois surfaces illisibles serait le pire
        resultat possible -- c'est la doctrine que le lanceur porte deja."""
        import hashlib
        import importlib.util
        chemin_script = os.path.join(_RACINE, 'scripts', 'gel_avant_apres.py')
        spec = importlib.util.spec_from_file_location('_gel_lanceur',
                                                      chemin_script)
        lanceur = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lanceur)
        from direction_non_vie.tarification.services import gel_livrables as G

        ref = self._json.loads(_lire_texte(self._chemin))
        # ⚠️ LE JEU D'ENTREE SE VERIFIE : un ecart lu entre deux assiettes
        # differentes mesurerait le jeu de donnees, pas le correctif.
        jeu = {'graine': lanceur.GRAINE, 'taille': lanceur.TAILLE,
               'arrete': lanceur.ARRETE, 'annees': list(lanceur.ANNEES)}
        self.assertEqual(
            ref.get('jeu'), jeu,
            'le jeu d entree du lanceur a change depuis le figeage : la '
            'reference ne porte plus sur la meme assiette. Re-figer, et '
            'justifier.')

        emp = G.empreinte(G.livrables_de_la_chaine(lanceur.produire_la_chaine()))
        self.assertEqual(
            emp.non_lues, {},
            f'des surfaces sont ILLISIBLES : un « 0 ecart » les tairait. '
            f'{emp.non_lues}')
        actuel = {nom: 'sha256:' + hashlib.sha256(
            self._json.dumps(contenu, sort_keys=True, ensure_ascii=False,
                             default=str).encode('utf-8')).hexdigest()
            for nom, contenu in emp.contenus.items()}
        attendu = dict(ref['surfaces'])
        self.assertEqual(
            set(actuel), set(attendu),
            f'le NOMBRE de surfaces produites a change : '
            f'apparues={sorted(set(actuel) - set(attendu))} '
            f'disparues={sorted(set(attendu) - set(actuel))}')
        bouge = sorted(n for n in actuel if actuel[n] != attendu[n])
        self.assertEqual(
            bouge, [],
            f'LE CONTENU DE CES LIVRABLES SIGNES A CHANGE : '
            f'{", ".join(bouge)}\n'
            f'Si le changement est VOULU : `py scripts/gel_avant_apres.py '
            f'--figer` et JUSTIFIEZ-LE dans le message de commit. Pour voir '
            f'ce qui a bouge, ecart par ecart : `--sortie A`, `--sortie B` '
            f'de part et d autre, puis `--comparer A B`.')
        # ⚠️⚠️ CE QUE CETTE REFERENCE COUVRE VRAIMENT — constat `D4`. Cette
        # phrase annoncait « 32 surfaces signees » alors que QUINZE d'entre
        # elles valent `ABSENT` : leur producteur rend zero octet, et leur
        # sha256 est celui de la chaine `<livrable absent>`, IDENTIQUE pour
        # toutes. *Un « 0 ecart » ne disait rien de ces quinze, et la phrase
        # qui l'accompagnait etait quinze fois trop genereuse.*
        #   Le jumeau `deposer()` distinguait depuis toujours : il calcule
        #   `reelles` et l'annonce. Deux fonctions du meme fichier ne
        #   disaient pas la meme chose de la meme mesure.
        absentes = sorted(n for n, c in emp.contenus.items()
                          if c == G.ABSENT)
        declarees = (ref.get('_surfaces_absentes') or {})
        self.assertEqual(
            sorted(declarees.get('noms') or []), absentes,
            f'la reference ne declare pas les surfaces ABSENTES qu elle '
            f'porte. mesurees={absentes} declarees='
            f'{sorted(declarees.get("noms") or [])}. Re-figer, et '
            f'justifier : une surface qui cesse d etre absente -- ou qui le '
            f'devient -- change ce que cette reference COUVRE.')
        print(f'    GEL-15b {len(actuel)} surfaces, dont '
              f'{len(actuel) - len(absentes)} REELLES et {len(absentes)} '
              f'ABSENTES ; contenu des reelles inchange')


if __name__ == '__main__':
    unittest.main(verbosity=2)
