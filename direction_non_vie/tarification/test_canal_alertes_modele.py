# -*- coding: utf-8 -*-
"""
=============================================================================
  OU VA VRAIMENT `alertes_modele` ? -- la phrase et la mesure
=============================================================================

`core/plan_tarifaire.alerte_modele_ampute` affirmait, dans sa docstring, que
son entree etait *<< agregee par A6 [...] et RENDUE DANS LES 3 LIVRABLES >>*.

Mesure du 03/09/2026, par EXECUTION, sur les SIX surfaces signees : un
temoin unique depose dans `alertes_modele` n'apparait dans **AUCUNE**.
**0 sur 6.** Son seul lecteur est `pipeline_agents`, qui n'en garde que le
`code` et jette le message.

  *Un canal ne publie pas parce qu'une docstring l'affirme.*

-----------------------------------------------------------------------------
ET POURTANT IL N'Y A PAS DE TROU FONCTIONNEL
-----------------------------------------------------------------------------
Le CONTENU atteint bien les livrables, par une AUTRE route :
`synthese_colonnes_plan_manquantes` alimente la cle `plan_ampute` des
syntheses reglementaires, rendue en html, word ET excel. C'est la phrase qui
decrivait mal le chemin, pas le chemin qui manquait.

⚠️ CE FICHIER TIENT LES DEUX MOITIES, et c'est necessaire : ne verifier que
la premiere ferait croire a une information perdue ; ne verifier que la
seconde laisserait la docstring mentir a nouveau.

-----------------------------------------------------------------------------
POURQUOI CETTE PHRASE MERITAIT UN FILET
-----------------------------------------------------------------------------
Elle a DEJA trompe, dans ce depot. Le lot `services/C13` avait appende un
avertissement dans `alertes_modele` en la croyant ; son constat l'ecrit :
*<< ce n'etait pas le bon canal non plus >>*. Une phrase fausse qui a deja
coute un lot en coutera un autre.
=============================================================================
"""

import io
import unittest
import zipfile

from core.plan_tarifaire import alerte_modele_ampute
from direction_non_vie.tarification.services import (
    rapport_equipe_tarif as RE,
)
from direction_non_vie.tarification.services import (
    rapport_modeles_tarif as RM,
)
from direction_non_vie.tarification.services import (
    tarif_excel as TX,
)

_TEMOIN = 'ZZTEMOINCANALZZ'


def _docx(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return z.read('word/document.xml').decode('utf-8')


def _xlsx(blob: bytes) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(blob))
    return '\n'.join(str(c.value) for ws in wb.worksheets
                     for row in ws.iter_rows() for c in row
                     if c.value is not None)


def _r6(**extra):
    base = {'success': True, 'statut_rag': 'AMBRE', 'branche': 'auto',
            'modele_production': {'modele': 'GLM'}, 'backtest': {},
            'audit_trail': {}, 'classement': [], 'metriques': {}}
    base.update(extra)
    return base


def _les_six(r6) -> dict:
    """Le texte des SIX surfaces signees, pour un meme `result_a6`."""
    res = {'a6': r6}
    sorties = {
        'equipe.html': RE.export_html_equipe(res),
        'equipe.word': _docx(RE.export_word_equipe(res)),
        'equipe.excel': _xlsx(RE.export_excel_equipe(res)),
    }
    try:
        sorties['modeles.html'] = RM.export_html({}, {}, r6)
        sorties['modeles.word'] = _docx(RM.export_word({}, {}, r6))
    except Exception as exc:                                 # noqa: BLE001
        sorties['modeles.html'] = sorties['modeles.word'] = (
            f'INDISPONIBLE {type(exc).__name__}')
    try:
        sorties['a6.excel'] = _xlsx(TX.export_excel_a6(r6))
    except Exception as exc:                                 # noqa: BLE001
        sorties['a6.excel'] = f'INDISPONIBLE {type(exc).__name__}'
    return sorties


class T1_LeCanalNeAtteintAucunLivrable(unittest.TestCase):

    def test_ca_1_alertes_modele_n_atteint_AUCUNE_des_six_surfaces(self):
        """CA-1 : la mesure qui rend la docstring fausse.

        ⚠️ Le temoin est mis dans le `message`, pas dans le `code` :
        `pipeline_agents` ne garde que le `code`, et c'est justement ce qui
        rend le message invisible partout ailleurs.
        """
        alerte = {'modele': 'GLM', 'severite': 'AMBRE', 'code': 'temoin',
                  'message': f'message temoin {_TEMOIN}'}
        atteintes = [nom for nom, texte in _les_six(
            _r6(alertes_modele=[alerte])).items() if _TEMOIN in texte]
        self.assertEqual(
            atteintes, [],
            f"`alertes_modele` atteint desormais {atteintes} : c'est une "
            f"BONNE nouvelle, mais la docstring de `alerte_modele_ampute` "
            f"doit etre remise a jour DANS LE MEME GESTE, sinon elle ment "
            f"a nouveau -- dans l'autre sens.")

    def test_ca_2_la_docstring_ne_reaffirme_plus_les_3_livrables(self):
        """CA-2 : le TEXTE qui accompagnait le defaut a ete relu.

        ⚠️ Ce controle lit de la PROSE, et c'est le plus faible du fichier.
        Ce qui TIENT est `CA-1` et `CA-3`, mesures par execution. Celui-ci
        empeche seulement qu'on retablisse l'affirmation en gardant le
        comportement.
        """
        doc = (alerte_modele_ampute.__doc__ or '').replace('\n', ' ')
        doc = ' '.join(doc.split())
        self.assertNotIn(
            'et rendu dans les 3 livrables', doc,
            "la docstring reaffirme un rendu que la mesure contredit")
        self.assertIn('0 sur 6', doc,
                      "la docstring ne porte pas la mesure qui la corrige")


class T2_MaisLeContenuArriveParUneAutreRoute(unittest.TestCase):

    def test_ca_3_le_contenu_MODELE_AMPUTE_atteint_bien_les_livrables(self):
        """CA-3 : LA SECONDE MOITIE, sans laquelle `CA-1` alarmerait a tort.

        Le fond passe par `synthese_colonnes_plan_manquantes` -> cle
        `plan_ampute` des syntheses reglementaires. *Il n'y avait pas de trou
        fonctionnel : il y avait une phrase qui decrivait mal le chemin.*
        """
        r6 = _r6(colonnes_plan_manquantes={
            'colonnes_non_produites': [_TEMOIN], 'plan': 'auto'})
        sorties = _les_six(r6)
        atteintes = [nom for nom, texte in sorties.items()
                     if _TEMOIN in texte]
        for attendue in ('equipe.html', 'equipe.word', 'equipe.excel'):
            with self.subTest(surface=attendue):
                self.assertIn(
                    attendue, atteintes,
                    f"le contenu << modele ampute >> n'atteint plus "
                    f"{attendue} : la SEULE route qui publiait vraiment "
                    f"cette information vient de se fermer.")

    def test_ca_4_alerte_modele_ampute_rend_toujours_sa_forme_normalisee(self):
        """CA-4 : la fonction elle-meme n'a pas bouge.

        ⚠️ Corriger une docstring ne doit rien changer au comportement --
        et c'est ce qu'on verifie plutot que de le supposer.
        """
        self.assertIsNone(alerte_modele_ampute(None, 'GLM'))
        self.assertIsNone(alerte_modele_ampute({'ampute': False}, 'GLM'))
        alerte = alerte_modele_ampute(
            {'ampute': True, 'colonnes_manquantes': ['a', 'b'],
             'plan': 'auto', 'n_presentes': 8, 'n_attendues': 10}, 'GLM')
        self.assertEqual(
            set(alerte), {'modele', 'severite', 'code', 'message'})
        self.assertEqual(alerte['code'], 'plan_incomplet_modele_ampute')
        self.assertIn('a, b', alerte['message'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
