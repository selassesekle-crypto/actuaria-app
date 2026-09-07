"""LE MAPPING ATTEINT LE DOCUMENT SIGNE, PAS SEULEMENT LE PROMPT.

Le dernier point du module tarification. `rapport_modeles_tarif` CALCULAIT la
synthese du mapping (`_construire_contexte_tarif`, l.1458) et la versait au
**contexte remis au modele** -- jamais a une section rendue.

  ***Mesure du 07/09/2026, dossier a mapping fautif, huit surfaces : ZERO
  occurrence dans le Word et le HTML de ce rapport, contre l'Excel A6 et les
  trois formats du rapport d'equipe.*** Le CAC lisait un modele << ampute >>
  sans jamais lire la cause.

⚠️ QUATRIEME ET DERNIERE INSTANCE D'UNE CLASSE DEJA FERMEE TROIS FOIS DANS CE
FICHIER : la qualite des donnees (`services/C12`), l'elasticite (<< elle
n'atteignait que le PROMPT >>, commentaire signe au site) et les reserves d'A6
(<< une surface sur six >>). Le correctif copie leur forme, il n'en invente
pas une.

⚠️⚠️ ET LA SOURCE RESTE UNIQUE. `synthese_mapping` rendait `" ".join(lignes)`
-- une SEULE ligne : rendre en puces avec l'idiome voisin (`split("\\n")`)
aurait donne UNE puce de sept phrases, le << pave >> que `_bloc_qualite_html`
interdit nommement. On a donc extrait `core.lignes_mapping` : la liste pour
qui veut des puces, `synthese_mapping` qui la joint pour qui veut la phrase.
*Jamais deux constructions du meme texte.*

Les quatre risques nommes AVANT le code, un controle et un plant chacun :
  R1 le gel dira 0 ecart et ce n'est PAS une preuve  -> MP-6 (egalite socle)
  R2 sans mapping, RIEN ne doit etre gagne           -> MP-3, MP-7
  R3 les deux formats, jamais un seul                -> MP-4, MP-5
  R4 une source, deux formes                         -> MP-1, MP-2, MP-6

  MP-1  `mapping_publie` APPELLE le socle, ne recopie rien ;
  MP-2  une puce PAR CONSTAT -- jamais le pave ;
  MP-3  SECOND SENS a l'unite : sans mapping, () et '' ;
  MP-4  le HTML porte la section, PAR EXECUTION ;
  MP-5  le Word porte la section, PAR EXECUTION ;
  MP-6  `synthese_mapping` == la jointure des lignes, sur 100+ combinaisons ;
  MP-7  SECOND SENS au DOCUMENT : sans mapping, le titre est absent des deux ;
  MP-8  la zone LLM est intacte -- le prompt recoit toujours la synthese, et
        le nombre d'appels de narration n'a pas bouge (F3).

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""

from __future__ import annotations

import ast
import io
import itertools
import os
import pathlib
import sys
import unittest
import zipfile

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

from core.mapping_client import (
    RapportMapping,
    lignes_mapping,
    synthese_mapping,
)
from direction_non_vie.tarification.services import (
    rapport_modeles_tarif as RM,
)

_SRC = (pathlib.Path(_ICI) / 'services' / 'rapport_modeles_tarif.py')

#: ⚠️ La narration est FOURNIE : sans elle `export_*` appellerait le modele.
#: Un test ne franchit pas la frontiere LLM.
_NARRATION = ('Narration fournie par la mesure.', 'MESURE')


def _rapport_fautif() -> RapportMapping:
    """Le dossier reel le plus frequent : un export client renomme en amont."""
    return RapportMapping(
        client='demo', plan='auto', n_renommees=2, n_colonnes_attendues=18,
        colonnes_client_non_mappees=('extra',),
        colonnes_plan_non_couvertes=('date_echeance',),
        correspondances_mortes=('COL_MORTE',),
        cibles_inconnues_du_plan=('age_FAUTE',),
        collisions=(), plan_declare=None, plan_incoherent=False,
        correspondances={'COL_MORTE': 'date_echeance'})


def _a6(avec_mapping: bool) -> dict:
    return {'rapport_mapping': _rapport_fautif() if avec_mapping else None,
            'statut_rag': 'AMBRE', 'branche': 'non_vie'}


def _texte_docx(octets: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(octets)) as z:
        return '\n'.join(z.read(n).decode('utf-8', 'replace')
                         for n in z.namelist() if n.endswith('.xml'))


def _rendre(avec_mapping: bool):
    r6 = _a6(avec_mapping)
    html = RM.export_html(result_a6=r6, ref_client='T', arrete='2026-06-30',
                          audit_id='T', narration_calculee=_NARRATION)
    word = RM.export_word(result_a6=r6, ref_client='T', arrete='2026-06-30',
                          audit_id='T', narration_calculee=_NARRATION)
    return html, _texte_docx(word)


class TestMappingSectionRendue(unittest.TestCase):

    def test_MP1_la_passerelle_APPELLE_le_socle_et_ne_recopie_rien(self):
        """⚠️⚠️ R4. Recopier les phrases ici aurait produit DEUX redactions du
        meme diagnostic -- celle du prompt et celle du document -- qui
        divergeraient au premier changement de libelle. *C'est le defaut que
        ce chantier ferme partout.*"""
        arbre = ast.parse(_SRC.read_text(encoding='utf-8'))
        cible = next(n for n in ast.walk(arbre)
                     if isinstance(n, ast.FunctionDef)
                     and n.name == 'mapping_publie')
        appels = {getattr(c.func, 'attr', getattr(c.func, 'id', None))
                  for c in ast.walk(cible) if isinstance(c, ast.Call)}
        self.assertIn(
            'lignes_mapping', appels,
            '`mapping_publie` ne passe plus par le socle : les phrases y sont '
            'peut-etre recopiees, et les deux redactions divergeront')
        # ⚠️ ET AUCUNE PHRASE N'EST FABRIQUEE AU SITE : les libelles du socle
        # ne doivent apparaitre nulle part dans ce fichier.
        texte = _SRC.read_text(encoding='utf-8')
        for libelle in ('MODELE AMPUTE', 'cible(s) INCONNUE(S)',
                        "CAUSE DE L'AMPUTATION"):
            with self.subTest(libelle=libelle):
                self.assertNotIn(
                    libelle, texte,
                    f'le libelle {libelle!r} est recopie dans le rapport : '
                    f'deux sources pour un seul texte')
        print('    MP-1 la passerelle appelle le socle, aucun libelle recopie')

    def test_MP2_une_puce_PAR_CONSTAT_jamais_le_pave(self):
        """⚠️⚠️ R4, la raison d'etre de `lignes_mapping`. La synthese jointe
        fait ici sept phrases : en une seule puce, le lecteur recoit un pave
        -- ce que `_bloc_qualite_html` interdit nommement au site voisin."""
        lignes = RM.mapping_publie(_a6(True))
        self.assertGreaterEqual(len(lignes), 4,
                                'la fixture n exerce pas le cas multi-constat')
        bloc = RM._bloc_mapping_html(lignes)
        self.assertEqual(
            bloc.count('<li>'), len(lignes),
            f'{len(lignes)} constats rendus en {bloc.count("<li>")} puce(s) : '
            f'le pave est de retour')
        print(f'    MP-2 {len(lignes)} constats -> {bloc.count("<li>")} puces')

    def test_MP3_SECOND_SENS_a_l_unite_sans_mapping_rien(self):
        """⚠️⚠️ R2, ET C'EST LE SENS QUI PROTEGE TOUS LES AUTRES DOSSIERS. La
        plupart des clients n'ont pas de fichier de mapping : un bloc mal
        garde ajouterait une section vide a CHAQUE rapport du depot."""
        for cas, r6 in (('a6 sans rapport', _a6(False)),
                        ('a6 vide', {}),
                        ('a6 absent', None)):
            with self.subTest(cas=cas):
                self.assertEqual(RM.mapping_publie(r6), ())
                self.assertEqual(RM._bloc_mapping_html(RM.mapping_publie(r6)),
                                 '')
        print('    MP-3 sans mapping : () et chaine vide, sur 3 formes')

    def test_MP4_le_HTML_porte_la_section_PAR_EXECUTION(self):
        """⚠️ R3. Lire le code ne conclut pas un chemin de publication."""
        html, _ = _rendre(True)
        self.assertIn(RM.TITRE_MAPPING_CLIENT, html)
        self.assertIn('MODELE AMPUTE', html)
        self.assertIn("CAUSE DE L'AMPUTATION", html)
        print(f'    MP-4 HTML : la section est rendue ({len(html):,} car.)')

    def test_MP5_le_WORD_porte_la_section_PAR_EXECUTION(self):
        """⚠️⚠️ R3. << Le Word part au CAC comme le HTML >> -- le commentaire
        du site voisin, ecrit apres qu'un correctif n'eut touche qu'un format.
        Corriger l'un sans l'autre laisse la moitie du livrable signe muette."""
        _, word = _rendre(True)
        self.assertIn(RM.TITRE_MAPPING_CLIENT, word)
        self.assertIn('MODELE AMPUTE', word)
        self.assertIn("CAUSE DE L'AMPUTATION", word)
        print('    MP-5 Word : la section est rendue')

    def test_MP6_synthese_mapping_est_EXACTEMENT_la_jointure_des_lignes(self):
        """⚠️⚠️ R1 et R4. Trois consommateurs signes dependent de la chaine
        (Excel A6, rapport equipe, contexte LLM) : l'extraction ne doit pas
        deplacer un octet. Mesure exhaustive sur les combinaisons des
        constats -- *le gel ne peut PAS le prouver, son assiette ne porte
        aucun mapping client.*"""
        n = 0
        for nc, mo, ic, co, pd_ in itertools.product(
                ((), ('date_echeance',)), ((), ('COL_MORTE',)),
                ((), ('age_FAUTE',)), ((), ('age',)),
                (None, 'auto', 'mrh')):
            for corr in ({}, {'COL_MORTE': 'date_echeance'}):
                r = RapportMapping(
                    client='demo', plan='auto', n_renommees=3,
                    n_colonnes_attendues=18,
                    colonnes_client_non_mappees=(),
                    colonnes_plan_non_couvertes=nc,
                    correspondances_mortes=mo,
                    cibles_inconnues_du_plan=ic, collisions=co,
                    plan_declare=pd_,
                    plan_incoherent=bool(pd_ and pd_ != 'auto'),
                    correspondances=corr)
                lignes = lignes_mapping(r)
                self.assertEqual(synthese_mapping(r), ' '.join(lignes))
                n += 1
        # ⚠️ L'assiette se DECLARE, et le cas `None` en fait partie.
        self.assertEqual(lignes_mapping(None), ())
        self.assertIsNone(synthese_mapping(None))
        self.assertGreaterEqual(n, 96, "l'assiette a retreci")
        print(f'    MP-6 {n} combinaisons : la jointure est exacte, None -> None')

    def test_MP7_SECOND_SENS_au_DOCUMENT_le_titre_est_absent(self):
        """⚠️⚠️ R2 au niveau du livrable. MP-3 prouve l'unite ; ici on ouvre
        les deux documents PRODUITS et on exige que rien n'y ait pousse."""
        html, word = _rendre(False)
        for nom, texte in (('HTML', html), ('Word', word)):
            with self.subTest(format=nom):
                self.assertNotIn(
                    RM.TITRE_MAPPING_CLIENT, texte,
                    f'une section mapping VIDE apparait dans le {nom} d un '
                    f'dossier SANS mapping : du bruit sur tous les rapports')
        print('    MP-7 sans mapping : aucun titre dans le HTML ni le Word')

    def test_MP8_la_zone_LLM_est_INTACTE(self):
        """⚠️⚠️ LA CONDITION D'ENTREE DE CE LOT : borner. Le contexte remis au
        modele n'est pas touche -- la synthese y part toujours -- et le
        nombre d'appels de narration n'a pas bouge (`F3`, encore ouvert)."""
        arbre = ast.parse(_SRC.read_text(encoding='utf-8'))
        fns = {n.name: n for n in ast.walk(arbre)
               if isinstance(n, ast.FunctionDef)}
        ctx = fns['_construire_contexte_tarif']
        appels_ctx = [getattr(c.func, 'attr', getattr(c.func, 'id', None))
                      for c in ast.walk(ctx) if isinstance(c, ast.Call)]
        self.assertIn(
            'synthese_mapping', appels_ctx,
            'le contexte LLM ne recoit plus la synthese du mapping : le '
            'correctif a DEPLACE au lieu d AJOUTER')
        # ⚠️ F3 : une narration par format, pas deux. Le bloc rendu n'en
        # declenche aucune.
        for nom in ('export_html', 'export_word'):
            with self.subTest(fonction=nom):
                n = sum(1 for c in ast.walk(fns[nom])
                        if isinstance(c, ast.Call)
                        and getattr(c.func, 'attr',
                                    getattr(c.func, 'id', None))
                        == '_narration_claude')
                self.assertEqual(
                    n, 1,
                    f'{nom} declenche {n} narration(s) : F3 a bouge, et ce '
                    f'lot ne devait PAS y toucher')
        print('    MP-8 prompt intact, 1 narration par format (F3 inchange)')


if __name__ == '__main__':
    unittest.main(verbosity=2)
