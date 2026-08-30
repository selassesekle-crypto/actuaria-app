"""Controles positifs — etape 5, derniere : les roles declares aux 20 plans.

CE QUE CE FICHIER PROUVE
────────────────────────

Les vingt plans du depot ne declaraient **aucun** des trois roles de donnees
(0/20, re-mesure le 30/08/2026). Consequence : la couche qualite ne pouvait
jamais dedoublonner sur l'identite du contrat, et A1 devinait l'identifiant par
sous-chaine (`'id'` ou `'pol'`), attrapant au passage des FACTEURS TARIFAIRES.

⚠️⚠️ CETTE ETAPE EST LA SEULE QUI CHANGE CE QUE LE SYSTEME FAIT SUR DE VRAIS
FICHIERS. Les quatre precedentes l'ont rendue sure, et l'ordre etait mesure :

    ① l'identifiant alphanumerique ne bloque plus (`qualite/C7`)
    ② la cle est la PAIRE, et sans echeance on CONSERVE au lieu d'exclure
    ③ l'avertissement atteint le rapport signe SANS IA (`services/C12`)
    ④ le vocabulaire existe dans les DEUX systemes

Appliquee en premier, elle aurait casse tout client a identifiant
alphanumerique et tout historique de renouvellement.

═══ CE QUI EST ARBITRE, ET OU C'EST ECRIT ═══

L'identite a dedoublonner n'est PAS « le contrat » partout : elle depend de
l'unite assuree. Sept LoB ont ete arbitrees une par une par Selasse le
30/08/2026, et la decision est ecrite DANS LE PLAN SIGNE — c'est la qu'elle est
opposable, pas dans un rapport de session.

⚠️ Les plans ne peuvent PAS deviner le nom de colonne du client : ils declarent
un ROLE et sa colonne canonique. Le mapping client fait la traduction.
"""

from __future__ import annotations

import logging
import pathlib
import unittest
import warnings

import pandas as pd

from core.plan_tarifaire import PlanTarifaire
from core.qualite_donnees import controler_qualite
from direction_non_vie.tarification.test_pipeline_agents import _portefeuille_auto

_PLANS = sorted(pathlib.Path('plans').glob('*.yaml'))

#: Les sept LoB dont l'unite assuree N'EST PAS evidemment « le contrat ».
#: ⚠️ La cle est le MOT QUI FAIT AUTORITE dans le plan, pas une paraphrase.
_ARBITREES = {
    'auto_fr_reel':              'IDENTIFIANT DU JEU freMTPL2',
    'flotte_automobile':         'CONTRAT DE FLOTTE',
    'multirisque_immeuble':      "l'IMMEUBLE",
    'bris_machine':              'la MACHINE',
    'garantie_loyers_impayes':   'le BAIL',
    'marchandises_transportees': "POLICE D'ABONNEMENT",
    'decennale':                 'A TRANCHER PAR FICHIER',
    'risques_agricoles':         'A TRANCHER PAR FICHIER',
}

#: La phrase qui porte la decision. ⚠️ On s'attache a ELLE, pas a un fragment
#: que n'importe quel commentaire pourrait contenir.
_PHRASE = "L'IDENTITE A DEDOUBLONNER EST"


def _charge(chemin):
    return PlanTarifaire.depuis_yaml(str(chemin))


def _controler(df, plan, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return controler_qualite(df, plan, horodatage='t', **kw)
        finally:
            logging.disable(precedent)


class TestLesVingtPlansDeclarentLeursRoles(unittest.TestCase):

    def test_LE_TEST_QUI_FERME_les_20_declarent_un_identifiant(self):
        """⚠️⚠️ 0/20 avant ce lot, re-mesure dans les YAML."""
        self.assertEqual(len(_PLANS), 20, f'{len(_PLANS)} plans trouves')
        sans = [f.name for f in _PLANS if not _charge(f).identifiant_contrat]
        self.assertEqual(sans, [], f'plans sans identifiant : {sans}')
        print(f"    P-1 {len(_PLANS)}/20 plans declarent `identifiant_contrat` "
              f"(0/20 avant ce lot)")

    def test_auto_fr_reel_porte_IDpol_et_les_19_autres_id_contrat(self):
        """⚠️ `auto_fr_reel` est le SEUL plan adosse a un jeu reel : freMTPL2 se
        joint par `IDpol`. Les 19 autres suivent la convention canonique."""
        obtenus = {f.stem: _charge(f).identifiant_contrat for f in _PLANS}
        self.assertEqual(obtenus.pop('auto_fr_reel'), 'IDpol')
        faux = {k: v for k, v in obtenus.items() if v != 'id_contrat'}
        self.assertEqual(faux, {}, f'hors convention : {faux}')
        print("    P-2 `auto_fr_reel` -> IDpol ; les 19 autres -> id_contrat")

    def test_les_20_declarent_l_echeance(self):
        """⚠️ Declarer la colonne ne l'EXIGE pas du client : absente du fichier,
        le systeme le dit et conserve les lignes. Mesure : aucune fausse
        amputation du plan."""
        sans = [f.name for f in _PLANS if _charge(f).echeance != 'date_echeance']
        self.assertEqual(sans, [], f'plans sans echeance : {sans}')
        print(f"    P-3 {len(_PLANS)}/20 declarent `echeance: date_echeance`")

    def test_les_SEPT_arbitrages_sont_ECRITS_dans_le_plan_signe(self):
        """⚠️⚠️ UNE DECISION QUI N'EST PAS DANS LE DOCUMENT OPPOSABLE N'EST PAS
        OPPOSABLE. L'unite assuree n'est pas « le contrat » partout ; sept LoB
        ont ete arbitrees une par une, et chaque plan porte SA raison mesuree.
        """
        for f in _PLANS:
            src = f.read_text(encoding='utf-8')
            with self.subTest(plan=f.stem):
                self.assertIn(_PHRASE, src,
                              'le plan ne dit pas quelle identite dedoublonner')
                attendu = _ARBITREES.get(f.stem, 'le CONTRAT')
                self.assertIn(attendu, src,
                              f"l'arbitrage « {attendu} » n'est pas ecrit")
        print(f"    P-4 les {len(_ARBITREES)} arbitrages sont ecrits dans leur "
              f"plan, les 12 autres portent « le CONTRAT »")

    def test_les_roles_ne_sont_JAMAIS_des_facteurs(self):
        """⚠️⚠️ LE GARDE-FOU DE FOND. Si l'identifiant devenait un facteur, il
        entrerait dans `colonnes_produites()` et serait MODELISE — une identite
        qui predit la sinistralite est une fuite structurelle."""
        for f in _PLANS:
            p = _charge(f)
            with self.subTest(plan=f.stem):
                produites = set(p.colonnes_produites())
                for role in (p.identifiant_contrat, p.echeance):
                    self.assertNotIn(role, produites,
                                     f'{role} est PRODUIT par le plan')
                noms = {x.nom for x in p.facteurs}
                self.assertNotIn(p.identifiant_contrat, noms)
                self.assertNotIn(p.echeance, noms)
        print("    P-5 aucun role n'est un facteur ni une colonne produite, "
              "sur les 20 plans")


class TestLeComportementSurUnVRAIFichier(unittest.TestCase):
    """⚠️ On mesure avec le plan LIVRE, pas avec une fixture de test."""

    def setUp(self):
        self.plan = _charge(pathlib.Path('plans/auto.yaml'))
        self.base = _portefeuille_auto(300, seed=3)

    def _hist(self, exercices=(2023, 2024, 2025)):
        return pd.concat(
            [self.base.assign(
                id_contrat=[f'P2024-{i:05d}' for i in range(300)],
                date_echeance=an) for an in exercices], ignore_index=True)

    def test_un_identifiant_ALPHANUMERIQUE_passe(self):
        """⚠️ Sans l'etape 1, ce cas bloquait a 100 % — et c'est la forme
        ordinaire d'un numero de police."""
        r = _controler(self.base.assign(
            id_contrat=[f'P2024-{i:05d}' for i in range(300)]), self.plan)
        self.assertFalse(r.bloque, f'{r.anomalies_au_dela_seuil}')
        self.assertEqual(r.lignes_retenues, 300)
        print("    P-6 fichier mono-exercice, identifiant « P2024-xxxxx » : "
              "300/300, ne bloque pas")

    def test_un_HISTORIQUE_avec_echeance_passe_entier(self):
        """⚠️ Sans l'etape 2, 66,7 % de faux doublons."""
        r = _controler(self._hist(), self.plan)
        self.assertFalse(r.bloque)
        self.assertEqual([a.code for a in r.exclusions], [])
        self.assertEqual(r.lignes_retenues, 900)
        print("    P-7 historique 300 contrats x 3 exercices : 900/900, "
              "0 exclusion")

    def test_SECOND_SENS_un_VRAI_doublon_reste_EXCLU(self):
        """⚠️⚠️ La paire ne doit pas ouvrir de trou : meme contrat, MEME
        exercice reste impossible."""
        h = self._hist()
        r = _controler(pd.concat([h, h.iloc[:40]], ignore_index=True), self.plan)
        excl = {a.code: (a.regle, a.nb_lignes) for a in r.exclusions}
        self.assertEqual(excl.get('doublon_identifiant'), (1, 40))
        print("    P-8 second sens : 40 vrais doublons (meme exercice) exclus "
              "en regle 1")

    def test_SANS_la_colonne_les_lignes_sont_CONSERVEES_et_signalees(self):
        """⚠️⚠️ LE CAS QUE SELASSE A NOMME : certains fichiers clients portent
        l'information de renouvellement, d'autres non. Le systeme doit gerer
        les deux proprement — jamais de rejet silencieux."""
        r = _controler(self._hist().drop(columns=['date_echeance']), self.plan,
                       qualite_validee_par='actuaire test')
        sig = {a.code: (a.regle, a.nb_lignes) for a in r.signalements}
        self.assertIn('doublon_identifiant_sans_echeance', sig)
        self.assertEqual(sig['doublon_identifiant_sans_echeance'][0], 3)
        self.assertEqual([a.code for a in r.exclusions], [],
                         'des lignes sont EXCLUES alors que rien ne permet de '
                         'trancher entre doublon et historique')
        self.assertEqual(r.lignes_retenues, 900)
        print(f"    P-9 sans la colonne : "
              f"{sig['doublon_identifiant_sans_echeance'][1]} lignes signalees "
              f"en regle 3, 900/900 conservees, 0 exclusion")


if __name__ == '__main__':
    unittest.main()
