r"""
==============================================================================
  LA PISTE D'AUDIT PUBLIEE PORTE TOUTES SES LIGNES
==============================================================================

⚠️⚠️ CE QUE CE CONTROLE EXISTE POUR EMPECHER, ET IL EST ARRIVE. Les deux
surfaces du meme chapitre filtraient
`isinstance(v, (str, int, float, bool))` : toute valeur LISTE, DICT ou
`None` faisait disparaitre **la ligne entiere**.

MESURE DU 13/09/2026, sur la chaine reellement produite -- piste d'audit
A6, 18 cles :

    publiees   15
    PERDUES     3
        raisons_plafond           list   POURQUOI le statut a ete plafonne
                                         (<< Gini = 0.1034 < 0.15 >>)
        poids_criteres            dict   les poids qui ont DESIGNE le
                                         modele de production
        valide_par_actuaire_dl    None   la gouvernance

*Ce qui disparaissait est exactement ce qu'un commissaire aux comptes
vient chercher.* Et ce n'etait pas un oubli isole : la docstring de
`libelle_audit` promet en toutes lettres << une cle inconnue reste
VISIBLE -- mise en forme, jamais effacee : une piste d'audit amputee ne
serait plus une piste d'audit >>. **La promesse portait sur le LIBELLE ;
le filtre effacait la LIGNE.**

⚠️⚠️ `None` SE DIT << NON RENSEIGNE >> ET RIEN DE PLUS. Selon la cle il
signifie << non mesure >> ou << non declare >>, et trancher dans le
formateur inventerait une cause. *Le libelle porte le sens, la valeur
porte l'absence.*

CE QUE CES CONTROLES SURVEILLENT : les LIGNES REELLEMENT PRESENTES dans
les deux documents produits, jamais l'absence d'un filtre precis. Un
futur filtre ecrit autrement, ou pose ailleurs, doit les faire rougir.
==============================================================================
"""
from __future__ import annotations

import io
import os
import pathlib
import sys
import unittest
import zipfile

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from direction_non_vie.tarification.services import (
    rapport_modeles_tarif as RM,
)

#: ⚠️ UNE PISTE D'AUDIT QUI PORTE LES TROIS NATURES QUE LE FILTRE EFFACAIT,
#: plus deux natures saines pour la contre-epreuve.
_AUDIT = {
    'audit_id': 'GEL-2026',
    'timestamp': '2026-06-30T00:00:00',
    'n_contrats': 1500,
    'gini_retenu': 0.1034,
    'modele_valide': True,
    #: les trois que le filtre faisait disparaitre
    'raisons_plafond': ['Gini = 0.1034 < 0.15 -- pouvoir discriminant',
                        'ratio de sur-apprentissage non mesure'],
    'poids_criteres': {'gini': 0.4, 'stabilite': 0.3, 'interpretabilite': 0.3},
    'valide_par_actuaire_dl': None,
}
_EFFACEES = ('raisons_plafond', 'poids_criteres', 'valide_par_actuaire_dl')


def _docx(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return z.read('word/document.xml').decode('utf-8')


def _r6():
    return {'success': True, 'statut_rag': 'AMBRE', 'branche': 'auto',
            'modele_production': {'modele': 'GLM'}, 'backtest': {},
            'audit_trail': dict(_AUDIT), 'classement': [], 'metriques': {}}


def _les_deux():
    r6 = _r6()
    return RM.export_html({}, {}, r6), _docx(RM.export_word({}, {}, r6))


class TestLaPisteDAuditEstComplete(unittest.TestCase):

    def test_PA1_SCEAU_les_DEUX_documents_portent_TOUTES_les_cles(self):
        """⚠️⚠️ LE SCEAU, ET IL PORTE SUR LES DEUX SURFACES A LA FOIS. Le
        filtre etait ecrit deux fois, une fois avec des espaces et une fois
        sans -- c'est ainsi qu'un releve litteral n'en voyait qu'un.
        *Corriger une surface et pas sa jumelle ferait mentir l'une des
        deux.*"""
        html, word = _les_deux()
        for surface, texte in (('HTML', html), ('Word', word)):
            for cle in _AUDIT:
                libelle = RM.libelle_audit(cle)
                with self.subTest(surface=surface, cle=cle):
                    self.assertIn(
                        libelle, texte,
                        f"{surface} : la ligne « {libelle} » ({cle}) a "
                        f"DISPARU de la piste d'audit. Une piste d'audit "
                        f"amputee n'est plus une piste d'audit.")
        print(f"    PA-1 SCEAU : les {len(_AUDIT)} cles atteignent les DEUX "
              f"documents")

    def test_PA2_SCEAU_les_trois_natures_EFFACEES_portent_leur_CONTENU(self):
        """⚠️⚠️ PUBLIER LE LIBELLE NE SUFFIT PAS. Une ligne presente dont la
        valeur serait vide rendrait le chapitre plus trompeur encore : le
        lecteur croirait avoir lu. *On exige donc la SUBSTANCE, pas la
        presence d'une etiquette.*"""
        html, word = _les_deux()
        attendus = {
            'raisons_plafond': '0.1034',
            'poids_criteres': 'gini',
            'valide_par_actuaire_dl': 'non renseigne',
        }
        for surface, texte in (('HTML', html), ('Word', word)):
            for cle, temoin in attendus.items():
                with self.subTest(surface=surface, cle=cle):
                    self.assertIn(
                        temoin, texte,
                        f"{surface} : « {cle} » est nommee mais son contenu "
                        f"({temoin!r}) n'apparait pas -- la ligne est vide.")
        print("    PA-2 SCEAU : liste, dict et absence portent leur contenu "
              "dans les deux formats")

    def test_PA3_SCEAU_une_ABSENCE_se_dit_sans_inventer_sa_cause(self):
        """⚠️⚠️ LE PIEGE QUE CE CORRECTIF NE DOIT PAS CREER. `None` signifie
        selon la cle << non mesure >> ou << non declare >> : ecrire l'un des
        deux dans le formateur INVENTERAIT une cause que la donnee ne porte
        pas. *Le libelle porte le sens, la valeur porte l'absence.*"""
        rendu = RM.valeur_audit(None, 'valide_par_actuaire_dl')
        self.assertEqual(rendu, 'non renseigne')
        for interdit in ('non mesure', 'non declare', 'non applicable',
                         'aucun actuaire', 'refuse'):
            self.assertNotIn(
                interdit, rendu,
                f"le formateur invente une cause ({interdit!r}) que la "
                f"donnee ne porte pas.")
        #: ⚠️ et une liste VIDE n'est pas une absence : elle dit qu'on a
        #: cherche et qu'il n'y avait rien.
        self.assertEqual(RM.valeur_audit([], 'raisons_plafond'), 'aucune')
        self.assertNotEqual(RM.valeur_audit([], 'raisons_plafond'),
                            RM.valeur_audit(None, 'raisons_plafond'))
        print(f"    PA-3 SCEAU : None -> {rendu!r}, liste vide -> "
              f"{RM.valeur_audit([], 'raisons_plafond')!r}, distinctes")

    def test_PA4_CONTRE_EPREUVE_les_valeurs_SAINES_ne_changent_pas(self):
        """⚠️ Le second sens : en apprenant a dire les listes et les dicts,
        le formateur ne doit rien changer a ce qu'il disait deja."""
        cas = {'audit_id': 'GEL-2026', 'n_contrats': '1500',
               'gini_retenu': '0.1034'}
        for cle, attendu in cas.items():
            self.assertIn(
                attendu, str(RM.valeur_audit(_AUDIT[cle], cle)),
                f"« {cle} » saine n'est plus rendue telle quelle")
        self.assertEqual(RM.valeur_audit(True, 'modele_valide'), 'oui')
        self.assertEqual(RM.valeur_audit(False, 'modele_valide'), 'non')
        print("    PA-4 contre-epreuve : chaines, nombres et booleens "
              "inchanges")

    def test_PA5_SCEAU_les_deux_surfaces_publient_LE_MEME_NOMBRE_de_lignes(
            self):
        """⚠️⚠️ LA SYMETRIE, MESUREE ET NON SUPPOSEE. Le defaut vient de deux
        ecritures du meme filtre ; rien n'empeche qu'une seule soit corrigee
        demain. On compare donc les DEUX documents sur le meme dossier, cle
        par cle, plutot que de verifier chacun dans son coin."""
        html, word = _les_deux()
        absentes = {'html': [], 'word': []}
        for cle in _AUDIT:
            lib = RM.libelle_audit(cle)
            if lib not in html:
                absentes['html'].append(cle)
            if lib not in word:
                absentes['word'].append(cle)
        self.assertEqual(
            absentes['html'], absentes['word'],
            f"les deux surfaces ne publient pas la meme piste d'audit : "
            f"manquent en HTML {absentes['html']}, en Word "
            f"{absentes['word']}. L'une des deux ment.")
        self.assertEqual(absentes['html'], [],
                         f"cles absentes des DEUX : {absentes['html']}")
        print(f"    PA-5 SCEAU : HTML et Word publient les memes "
              f"{len(_AUDIT)} lignes")

    def test_PA6_SCEAU_le_RELEVE_du_filtre_tolere_les_espaces(self):
        """⚠️⚠️ LA LECON DU LOT, POSEE EN GARDE-FOU. Le filtre etait ecrit
        `(str, int, float, bool)` en HTML et `(str,int,float,bool)` en Word :
        **une recherche litterale n'en voyait qu'un**, et j'ai failli
        conclure que l'auditeur se trompait. *Ce controle cherche le motif
        en tolerant les espaces, sur tout le module.*"""
        import re
        src = pathlib.Path(RM.__file__).read_bytes().decode('utf-8')
        #: on ignore les commentaires : ils DECRIVENT le defaut
        vivant = '\n'.join(l for l in src.splitlines()
                           if not l.lstrip().startswith('#'))
        motif = re.compile(r'isinstance\(\s*\w+\s*,\s*\(\s*str\s*,\s*int\s*,'
                           r'\s*float\s*,\s*bool\s*\)\s*\)')
        trouves = motif.findall(vivant)
        self.assertEqual(
            trouves, [],
            f"{len(trouves)} filtre(s) de nature sur la piste d'audit sont "
            f"revenus : {trouves[:3]}")
        print("    PA-6 SCEAU : 0 filtre de nature, espaces toleres dans "
              "le releve")


if __name__ == '__main__':
    unittest.main(verbosity=2)
