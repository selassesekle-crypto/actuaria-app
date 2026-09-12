r"""
==============================================================================
  UNE VALEUR ABSENTE NE DETRUIT PAS UN DOCUMENT SIGNE
==============================================================================

⚠️⚠️ CE QUE CE CONTROLE EXISTE POUR EMPECHER, ET IL EST ARRIVE. Six sites
de `rapport_modeles_tarif` formataient une grandeur en `:.4f`, `:.2f` ou
`:.4g` derriere le garde `if 'cle' in d`. Ce garde a EXACTEMENT l'angle
mort que le module denonce ailleurs pour `.get(cle, defaut)` : *il ne
protege de rien quand la cle EXISTE et vaut `None`.*

MESURE DU 11/09/2026, chaine complete A1->A6 sur `auto` :

    contrats refuses parmi les 10 du detail   HTML          Word
    donnee saine                       0      22 026 car.   39 979 o
    UN bonus_malus='beaucoup' ligne 0  1      22 329 car.   **0 o**
    le meme defaut ligne 400           0      22 336 car.   40 125 o

    ERROR | export_word tarification : unsupported format string passed
            to NoneType.__format__
    INFO  | Rapport tarification : HTML=36 956b  Word=0b
    ERROR | LIVRABLE NON PRODUIT -- 1 document(s) sur 3

⚠️⚠️ ET LE `None` N'EST PAS UN ACCIDENT : `tarif_publie` le POSE a dessein.
Sa docstring le dit -- << Un contrat NON TARIFABLE n'est pas ecarte : il
figure au detail avec ses primes a `None`. >> *Le format n'a donc pas a se
defendre d'une anomalie : il doit supporter une valeur que le module
publie EXPRES.*

⚠️⚠️ LA SURFACE JUMELLE ETAIT DEJA PROTEGEE. L'HTML passe ses trois valeurs
par `_c(v)` et rend le tiret ; le Word n'en gardait qu'UNE sur trois. *Le
garde avait ete pose a une porte et pas a sa jumelle.* C'est pourquoi ces
controles interrogent LES DEUX FORMATS a chaque fois : une asymetrie entre
jumeaux est le revelateur le moins cher.

CE QUE CES CONTROLES SURVEILLENT. Le COMPORTEMENT : un document est-il
encore PRODUIT, et porte-t-il la marque d'absence ? Ils ne verifient
jamais la presence de `_mesure` -- un futur site ecrit autrement, mais
correct, doit rester vert ; un site correct aujourd'hui qui casserait
demain doit rougir.
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

#: le tiret que le module pose sur une absence -- sa source unique
_ABSENT = '—'


def _docx(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return z.read('word/document.xml').decode('utf-8')


def _r6(**extra):
    base = {'success': True, 'statut_rag': 'AMBRE', 'branche': 'auto',
            'modele_production': {'modele': 'GLM', 'score_global': 0.8123,
                                  'interpretabilite': 0.65},
            'backtest': {}, 'audit_trail': {}, 'classement': [],
            'metriques': {}}
    base.update(extra)
    return base


def _publie(**trous):
    """Le payload que `tarif_publie` remet aux deux formats.

    ⚠️ On injecte AU POINT DE JONCTION, la ou la valeur arrive au format.
    Reconstruire un `TarifNonVie` entier ferait dependre ce controle de
    toute la chaine -- et un echec ailleurs l'accuserait a tort.
    """
    ligne = {'rang': 1, 'facteurs': {'bonus_malus': 'beaucoup'},
             'exposition': 0.7412, 'prime_pure': 344.99,
             'prime_commerciale_ht': 512.40, 'prime_ttc': 624.61}
    ligne.update(trous)
    return {
        'detail': [ligne],
        'total': {
            'n_contrats': 600, 'n_lignes_detail': 1,
            'somme_prime_pure': 187433.20, 'prime_pure_moyenne': 312.39,
            'somme_prime_commerciale_ht': 264190.11,
            'somme_prime_ttc': 322311.93,
            'n_sans_prime_commerciale': 0, 'n_contrats_imputes': 0,
            'rangs_imputes': [], 'phrase_imputes': None,
        },
        'chargements': None, 'regime_fiscal': None,
        'validation_hypothese': None,
        'origine': 'GLM Gamma, modele recommande',
        'plan_empreinte': '7fe1c1a952d57c2a',
    }


class _AvecPayload:
    """Substitue `tarif_publie` le temps d'un appel, et le REMET ensuite.

    ⚠️ Sans la remise en place, ce fichier laisserait le module truque pour
    ses voisins : *un test qui abime l'etat commun fait mentir le suivant.*
    """

    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        self._vrai = RM.tarif_publie
        RM.tarif_publie = lambda *_a, **_k: self._payload
        return self

    def __exit__(self, *_exc):
        RM.tarif_publie = self._vrai
        return False


def _les_deux_formats(payload, r6=None):
    """Rend `(html, word_bytes)` pour un meme payload."""
    r6 = r6 or _r6()
    with _AvecPayload(payload):
        html = RM.export_html({}, {}, r6, tarif=object())
        word = RM.export_word({}, {}, r6, tarif=object())
    return html, word


class TestUneAbsenceNeSupprimePasLeLivrable(unittest.TestCase):

    #: les trois valeurs du detail que `tarif_publie` peut poser a `None`
    TROUS = ('exposition', 'prime_pure', 'prime_commerciale_ht')

    def test_WD1_SCEAU_chaque_valeur_du_detail_peut_etre_None(self):
        """⚠️⚠️ LE SCEAU, UNE VALEUR A LA FOIS. Le defaut n'a ete vu que
        parce qu'UNE des trois manquait. Les tester ensemble aurait laisse
        passer le cas ou deux sont gardees et la troisieme non -- c'est
        exactement l'etat d'avant."""
        for cle in self.TROUS:
            with self.subTest(valeur=cle):
                html, word = _les_deux_formats(_publie(**{cle: None}))
                self.assertTrue(
                    word,
                    f"`{cle}` a None : le Word vaut 0 octet. Le livrable "
                    f"signe est PERDU, et le seul temoin est un warning.")
                self.assertGreater(
                    len(word), 10_000,
                    f"`{cle}` a None : Word de {len(word)} octets, trop "
                    f"court pour etre un document complet.")
                self.assertIn(
                    _ABSENT, _docx(word),
                    f"`{cle}` a None : le Word est produit mais ne porte "
                    f"aucune marque d'absence -- un lecteur ne peut pas "
                    f"distinguer une valeur manquante d'une valeur nulle.")
                #: ⚠️ LA SURFACE JUMELLE, A CHAQUE FOIS : l'asymetrie entre
                #: deux formats du meme detail est ce qui a produit ce
                #: defaut. On ne repare pas l'un en laissant l'autre.
                self.assertTrue(
                    html and _ABSENT in html,
                    f"`{cle}` a None : l'HTML ne porte pas la marque "
                    f"d'absence.")
        print(f"    WD-1 SCEAU : les {len(self.TROUS)} valeurs du detail "
              f"peuvent etre None, les deux formats survivent")

    def test_WD2_SCEAU_les_TROIS_valeurs_ensemble_aussi(self):
        """⚠️ Le cas reel du contrat NON TARIFABLE : `tarifer()` ne rend que
        cinq cles, donc les TROIS sont absentes en meme temps."""
        html, word = _les_deux_formats(
            _publie(exposition=None, prime_pure=None,
                    prime_commerciale_ht=None, prime_ttc=None))
        self.assertGreater(
            len(word), 10_000,
            "un contrat entierement NON TARIFABLE dans le detail detruit "
            "encore le Word.")
        self.assertIn(_ABSENT, _docx(word))
        self.assertIn(_ABSENT, html)
        print(f"    WD-2 SCEAU : contrat non tarifable complet, Word "
              f"{len(word)} octets, HTML {len(html)} car.")

    def test_WD3_SCEAU_les_grandeurs_du_MODELE_aussi(self):
        """⚠️⚠️ LES TROIS AUTRES SITES, ceux que l'auditeur disait ARMES.
        `score_global`, `interpretabilite` et la p-value etaient formates
        derriere `if 'cle' in d` -- le garde qui ne protege pas d'un `None`.
        *Aucun agent n'en emet aujourd'hui ; c'est precisement ce qui rend
        le defaut invisible jusqu'au jour ou l'un d'eux le fera.*"""
        for cle in ('score_global', 'interpretabilite'):
            with self.subTest(valeur=cle):
                r6 = _r6()
                r6['modele_production'][cle] = None
                html, word = _les_deux_formats(_publie(), r6)
                self.assertGreater(
                    len(word), 10_000,
                    f"`modele_production['{cle}'] = None` detruit le Word.")
                self.assertTrue(
                    html,
                    f"`modele_production['{cle}'] = None` detruit l'HTML -- "
                    f"et `export_html` n'a AUCUN `try/except` : "
                    f"l'exception sort et les DEUX documents disparaissent.")
        print("    WD-3 SCEAU : score_global et interpretabilite a None, "
              "les deux formats survivent")

    def test_WD4_CONTRE_EPREUVE_une_valeur_PRESENTE_est_publiee_telle_quelle(
            self):
        """⚠️⚠️ LE SECOND SENS, ET IL EST INDISPENSABLE. Un correctif qui
        rendrait le tiret PARTOUT aurait supprime le defaut en supprimant
        la mesure. *Un controle qui ne verifie qu'un sens accuse.*"""
        html, word = _les_deux_formats(_publie())
        texte = _docx(word)
        for attendu, ou in (('344.99', 'la prime pure'),
                            ('512.40', 'la prime commerciale HT'),
                            ('0.7412', "l'exposition")):
            self.assertIn(
                attendu, texte,
                f"{ou} saine ({attendu}) n'apparait plus dans le Word : le "
                f"correctif a remplace la valeur par son absence.")
        self.assertIn('0.8123', texte,
                      'le score global sain a disparu du Word')
        #: ⚠️ et rien n'a ete marque absent alors que tout etait present
        self.assertNotIn(
            f'expo {_ABSENT}', texte,
            "une valeur presente est publiee comme absente")
        #: ⚠️⚠️ LA SURFACE JUMELLE AUSSI. Tout ce lot vient d'un garde pose a
        #: une porte et pas a l'autre : la contre-epreuve ne peut pas ne
        #: regarder qu'un format. L'HTML arrondit a deux decimales via
        #: `_c(v)`, donc on y verifie les deux montants, pas l'exposition.
        for attendu, ou in (('344.99', 'la prime pure'),
                            ('512.40', 'la prime commerciale HT')):
            self.assertIn(
                attendu, html,
                f"{ou} saine ({attendu}) a disparu de l'HTML.")
        print(f"    WD-4 contre-epreuve : valeurs saines intactes, Word "
              f"{len(word)} octets")

    def test_WD5_LE_FIXTURE_NE_DERIVE_PAS_DE_LA_VRAIE_SORTIE(self):
        """⚠️⚠️ CE QUI SURVEILLE LE SURVEILLANT. Le payload ci-dessus est
        ECRIT A LA MAIN : il atteste ce qu'on a pense a y mettre, pas ce
        que `tarif_publie` produit. Une cle ajoutee demain y manquerait, et
        les quatre controles passeraient sur un payload qui n'existe plus.

        *Une assiette ecrite a la main se verifie contre sa source.* On
        releve donc PAR AST les cles que `tarif_publie` construit, et on
        exige que le fixture les porte toutes."""
        import ast
        src = pathlib.Path(RM.__file__).read_bytes().decode('utf-8')
        fn = next((n for n in ast.walk(ast.parse(src))
                   if isinstance(n, ast.FunctionDef)
                   and n.name == 'tarif_publie'), None)
        self.assertIsNotNone(
            fn, "`tarif_publie` est introuvable : ce controle surveillerait "
                "le vide.")

        #: ⚠️⚠️ `tarif_publie` a PLUSIEURS `return` : le dict vide, celui du
        #: REFUS D'ASSIETTE (`{'refus_assiette': ...}`, une forme legitime
        #: que `export_word` traite a part) et celui du prix. On vise
        #: nommement celui qui porte `detail` -- prendre << le dernier vu >>
        #: revenait a surveiller la mauvaise sortie, et ce controle l'a
        #: signale des son premier passage.
        attendues, du_total = set(), set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict):
                cles = {k.value for k in n.value.keys
                        if isinstance(k, ast.Constant)}
                if 'detail' in cles:
                    attendues = cles
            if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict)
                    and any(getattr(t, 'id', None) == 'total'
                            for t in n.targets)):
                du_total = {k.value for k in n.value.keys
                            if isinstance(k, ast.Constant)}
        self.assertTrue(attendues and du_total,
                        'le relevé AST n a rien trouvé : il ne surveille rien')

        p = _publie()
        manquantes = sorted(attendues - set(p))
        self.assertEqual(
            manquantes, [],
            f"cle(s) produites par `tarif_publie` et absentes du fixture : "
            f"{manquantes}. Les controles de ce fichier tournent sur un "
            f"payload qui ne ressemble plus a la vraie sortie.")
        manque_total = sorted(du_total - set(p['total']))
        self.assertEqual(
            manque_total, [],
            f"cle(s) du bloc `total` absentes du fixture : {manque_total}.")
        print(f"    WD-5 le fixture porte les {len(attendues)} cles de "
              f"sortie et les {len(du_total)} du total")


if __name__ == '__main__':
    unittest.main(verbosity=2)
