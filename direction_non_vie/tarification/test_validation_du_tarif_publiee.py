r"""
==============================================================================
  CE QUE LE TARIF SAIT DE SA PROPRE QUALITE DOIT ATTEINDRE LE DOCUMENT
==============================================================================

⚠️⚠️ `VAL-1` -- LE MODULE ECRIVAIT QU'IL << PUBLIE >>, ET PUBLIER Y
VOULAIT DIRE << RENDRE DANS UN DICT >>. L'en-tete de
`core/validation_tarif.py` annonce : *<< ce module PUBLIE -- le Gini, son
intervalle, l'effectif du holdout ET le rapport n/p qui dit si la mesure
avait la puissance de conclure. L'actuaire signataire tranche. >>*

Releve du 13/09/2026, par mot, sur les HUIT services de livrable du
depot : `mentions`, `niveau_max`, `ic_bas`, `sinistres_par_parametre`
-> **0 lecture**, partout. *L'actuaire ne peut pas trancher sur une
grandeur qui n'atteint aucun des six documents qu'il signe.*

⚠️ LE CONSTAT EST LATENT, ET ON LE DIT PLUTOT QUE DE L'ENFLER : **0 des
20 plans livres ne declare de decoupe de validation**, donc le bloc vaut
toujours `None` aujourd'hui. Il se produira le jour ou un plan en
declarera une -- et ce jour-la, la mention existera et n'atteindra
personne.

⚠️⚠️ LE CORRECTIF FERME LES DEUX SURFACES QUI RECOIVENT LE TARIF, ET
SEULEMENT CELLES-LA. `rapport_equipe_tarif` et `tarif_excel` ne recoivent
meme pas l'objet `tarif` : y porter la mention demanderait de leur passer
un argument qu'ils n'ont jamais eu -- c'est une question de conception,
pas d'application, et elle n'est pas ouverte ici. *On ferme ce qu'on
peut fermer, et on nomme le reste.*
==============================================================================
"""
from __future__ import annotations

import io
import logging
import os
import pathlib
import sys
import types
import unittest
import zipfile

import pandas as pd

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from core.plan_tarifaire import PlanTarifaire
from core.validation_tarif import Mention, ValidationTarif
from direction_non_vie.tarification.services import rapport_modeles_tarif as RM

_SOURCE = (_RACINE / 'direction_non_vie' / 'tarification' / 'services'
           / 'rapport_modeles_tarif.py').read_bytes().decode('utf-8')

#: Les quatre grandeurs que l'en-tete de `validation_tarif` dit PUBLIER.
_GRANDEURS = ('mentions', 'niveau_max', 'ic_bas', 'sinistres_par_parametre')

_PHRASE_AMBRE = ('POUVOIR DISCRIMINANT NON DISTINGUABLE DE ZERO (severite) : '
                 'Gini de holdout +0.0319 sur 85 observations')
_PHRASE_ROUGE = 'NE DISCRIMINE PAS : Gini de holdout negatif (frequence)'


def _plan_auto() -> PlanTarifaire:
    fichiers = sorted((_RACINE / 'plans').glob('*.yaml'))
    if not fichiers:
        raise AssertionError(
            f"aucun plan sous {_RACINE / 'plans'} : l'assiette du controle "
            f"est VIDE, il attesterait sans rien surveiller")
    return PlanTarifaire.depuis_yaml(
        str(next(f for f in fichiers if f.stem == 'auto')))


def _tarif(plan, validation):
    """Le minimum que `tarif_publie` lit sur un tarif.

    ⚠️ ON NE REJOUE PAS LA CHAINE : le defaut est un RELAIS manquant entre
    l'objet et le document. Un vrai `TarifNonVie` ferait tourner deux GLM
    pour mesurer une phrase qui ne depend d'aucun des deux.

    ⚠️ RENDU PAR UNE FABRIQUE plutot que par une classe : ces trois
    methodes ne sont appelees que par DUCK TYPING depuis le service, jamais
    nommees ici -- des methodes de classe seraient declarees mortes par
    l'analyse statique, et les retirer casserait la mesure."""
    return types.SimpleNamespace(
        plan=plan,
        validation=validation,
        predire_portefeuille=lambda df: {'prime_pure': [100.0] * len(df)},
        tarifer=lambda _contrat: {'prime_pure': 100.0,
                                 'prime_commerciale_ht': 130.0,
                                 'prime_ttc': 155.0, 'success': True},
        anomalies_du_contrat=lambda _contrat: (),
    )


def _portefeuille(plan) -> pd.DataFrame:
    """Un portefeuille CLIENT : les colonnes sources, aucune derivee.

    ⚠️ `tarif_publie` REFUSE une assiette qui porte une colonne creee par
    A2 -- c'est un garde-fou d'un lot voisin, et il a raison."""
    colonnes = {}
    for f in plan.facteurs:
        colonnes[f.nom] = [1.0, 2.0, 3.0]
    colonnes[plan.exposition] = [1.0, 1.0, 1.0]
    df = pd.DataFrame(colonnes)
    return df.drop(columns=[c for c in plan.colonnes_derivees()
                            if c in df.columns])


def _validation(mentions=True) -> ValidationTarif:
    if not mentions:
        return ValidationTarif(mentions=[])
    return ValidationTarif(mentions=[
        Mention(niveau='AMBRE', grandeur='severite', texte=_PHRASE_AMBRE),
        Mention(niveau='ROUGE', grandeur='frequence', texte=_PHRASE_ROUGE),
    ])


class TestLaValidationDuTarifEstPubliee(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_VA1_SCEAU_les_mentions_entrent_dans_le_TARIF_PUBLIE(self):
        """⚠️⚠️ LE SCEAU. `tarif_publie` est la seule porte par laquelle un
        fait du tarif entre dans un document : si la mention n'y est pas,
        aucune fabrique ne pourra la lire."""
        plan = _plan_auto()
        publie = RM.tarif_publie(_tarif(plan, _validation()),
                                 portefeuille=_portefeuille(plan))
        self.assertNotIn(
            'refus_assiette', publie,
            f"l'assiette de ce controle est refusee par le garde-fou : "
            f"{publie.get('refus_assiette', '')[:120]}")
        self.assertIn(
            'validation_mentions', publie,
            "`tarif_publie` ne porte pas les mentions de validation : ce que "
            "le tarif sait de sa propre qualite n'atteint aucune fabrique")
        rendu = ' | '.join(publie['validation_mentions'])
        for niveau, phrase in (('AMBRE', _PHRASE_AMBRE),
                               ('ROUGE', _PHRASE_ROUGE)):
            self.assertIn(phrase, rendu, f'la mention {niveau} est perdue')
            self.assertIn(f'[{niveau}]', rendu,
                          f'le NIVEAU {niveau} ne voyage pas avec sa phrase')
        print(f"    VA-1 SCEAU : {len(publie['validation_mentions'])} "
              f"mention(s) publiees, niveau compris")

    def test_VA2_SCEAU_les_DEUX_formats_signes_les_portent(self):
        """⚠️⚠️ LES DEUX FORMATS, MESURES PAR EXECUTION SUR LE DOCUMENT
        PRODUIT. Une lecture posee dans un seul format laisserait la moitie
        du livrable signe muette -- le piege de l'avertissement DL, deja
        paye sur ce depot.

        ⚠️ MA PREMIERE REDACTION CHERCHAIT LES DEUX NOMS DE FABRIQUE dans un
        releve AST et accusait `export_html` : le lecteur HTML vit en
        realite dans `_bloc_tarif_html`, que `export_html` appelle. *Un
        controle qui exige un NOM plutot qu'un RESULTAT accuse une
        architecture au lieu de mesurer un fait.*"""
        plan = _plan_auto()
        pf = _portefeuille(plan)
        tarif = _tarif(plan, _validation())
        html = RM.export_html(tarif=tarif, portefeuille=pf)
        self.assertIn(
            _PHRASE_AMBRE, html,
            'le HTML signe ne porte pas la mention de validation du tarif')
        octets = RM.export_word(tarif=tarif, portefeuille=pf)
        z = zipfile.ZipFile(io.BytesIO(octets))
        texte = '\n'.join(z.read(n).decode('utf-8', 'replace')
                          for n in z.namelist() if n.endswith('.xml'))
        self.assertIn(
            _PHRASE_AMBRE, texte,
            'le .docx signe ne porte pas la mention : la moitie du livrable '
            'reste muette')
        print(f"    VA-2 SCEAU : la mention atteint le HTML ({len(html)} "
              f"car.) ET le .docx ({len(octets)} o)")

    def test_VA3_l_ensemble_se_DERIVE_des_mentions_de_l_objet(self):
        """⚠️ UNE LISTE ECRITE A LA MAIN ATTESTE CE QU'ON A PENSE A Y METTRE.
        La cle doit se construire a partir de `tarif.validation.mentions`,
        pas d'une enumeration posee a cote."""
        i = _SOURCE.find("'validation_mentions': tuple(")
        self.assertGreater(i, 0, 'la cle a disparu')
        extrait = _SOURCE[i:i + 340]
        for attendu in ('validation', 'mentions', '_m.niveau', '_m.texte'):
            self.assertIn(
                attendu, extrait,
                f"la construction ne cite pas {attendu!r} : elle ne derive "
                f"plus de l'objet")
        print('    VA-3 : la cle derive de `tarif.validation.mentions`')

    def test_VA4_CONTRE_EPREUVE_sans_mention_le_document_ne_gagne_rien(self):
        """⚠️ LE SECOND SENS. Aujourd'hui AUCUN des 20 plans ne declare de
        decoupe : le bloc vaut `None`, et le document ne doit pas gagner une
        ligne. *Un avertissement permanent est un avertissement qu'on cesse
        de lire.*"""
        plan = _plan_auto()
        pf = _portefeuille(plan)
        for etiq, validation in (('aucune validation', None),
                                 ('validation sans mention',
                                  _validation(mentions=False))):
            publie = RM.tarif_publie(_tarif(plan, validation),
                                     portefeuille=pf)
            self.assertEqual(
                publie.get('validation_mentions'), (),
                f'{etiq} : la cle porte {publie.get("validation_mentions")!r} '
                f'au lieu d un tuple vide')
        print('    VA-4 contre-epreuve : sans mention -> tuple vide, '
              '0 ligne gagnee')

    def test_VA5_l_ETAT_du_depot_est_declare_et_MESURE(self):
        """⚠️⚠️ LE CONSTAT EST LATENT, ET CE CONTROLE LE MESURE PLUTOT QUE DE
        LE CROIRE. Le jour ou un plan declarera une decoupe, ce compteur
        changera -- et le lot qui l'aura ajoute devra relire cette phrase.
        *Une phrase de portee se mesure comme un chiffre.*"""
        avec = [y.stem for y in sorted((_RACINE / 'plans').glob('*.yaml'))
                if getattr(PlanTarifaire.depuis_yaml(str(y)),
                           'decoupe_validation', None)]
        self.assertEqual(
            avec, [],
            f"{len(avec)} plan(s) declarent desormais une decoupe de "
            f"validation : {avec}. Le constat `VAL-1` n'est plus LATENT, et "
            f"les QUATRE surfaces qui ne recoivent pas `tarif` "
            f"(`rapport_equipe_tarif`, `tarif_excel`) doivent etre "
            f"instruites.")
        #: ⚠️⚠️ ET CE QUI RESTE OUVERT SE MESURE, il ne se raconte pas. Les
        #: deux autres fabriques ne recoivent meme pas l'objet `tarif` : leur
        #: fermeture demanderait de leur passer un argument qu'elles n'ont
        #: jamais eu -- de la conception, pas de l'application. Ce compteur
        #: le CHIFFRE, pour que la phrase du lot reste vraie ou rougisse.
        restent = {}
        for nom in ('rapport_equipe_tarif', 'tarif_excel'):
            texte = (_RACINE / 'direction_non_vie' / 'tarification'
                     / 'services' / f'{nom}.py').read_bytes().decode('utf-8')
            restent[nom] = sum(texte.count(g) for g in _GRANDEURS)
        self.assertEqual(
            sorted(restent.values()), [0, 0],
            f"une de ces deux fabriques lit desormais une grandeur de "
            f"validation : {restent}. La phrase du lot -- << elles ne "
            f"recoivent meme pas le tarif >> -- doit etre relue.")
        print(f"    VA-5 : 0 / 20 plans declarent une decoupe -- constat "
              f"latent ; {sorted(restent)} lisent toujours 0 grandeur")


if __name__ == '__main__':
    unittest.main(verbosity=2)
