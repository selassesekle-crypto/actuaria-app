r"""
==============================================================================
  LE PLAN SE SCELLE EN ENTIER, ET L'ASSIETTE D'UN CONTROLE SE LIT VRAIMENT
==============================================================================

TROIS CONSTATS D'UNE MEME FAMILLE : *ce qu'on croit surveille ne l'est
pas.*

⚠️⚠️ `PLN-1` -- L'EMPREINTE ETAIT AVEUGLE A UN CHAMP AJOUTE. La charge
hachee par `PlanTarifaire.empreinte()` etait ENUMEREE A LA MAIN. Un
vingt-et-unieme champ ajoute au plan et oublie dans la charge ne faisait
rougir AUCUN controle : **deux plans qui different par ce champ portaient
la MEME empreinte**, et l'empreinte est ce qui scelle un tarif signe.
Mesure du 13/09 : 20 champs declares, 20 cites -- le defaut etait LATENT,
et il le serait reste jusqu'au 21e.

⚠️⚠️ `PLN-2` -- UNE REFERENCE QUI N'EXISTE PAS N'ECARTE AUCUNE MODALITE.
`Facteur(one_hot, modalites=('A','B','C'), reference='Z')` etait ACCEPTE
et rendait TROIS colonnes pour trois modalites au lieu de deux. La matrice
de conception devenait colineaire avec la constante. *Le prix ne bouge
pas -- statsmodels resout par pseudo-inverse -- mais les RELATIVITES
PUBLIEES si : la constante s'y repartit arbitrairement.* Mesure du 13/09 :
`reference='Z'` -> 3 colonnes ; `reference='A'` -> 2.

⚠️⚠️ `CWD-1` -- CINQ CONTROLES VERTS EN AYANT REGARDE ZERO PLAN.
`glob.glob('plans/*.yaml')` est relatif au REPERTOIRE COURANT. Lance
depuis ailleurs -- ce que fait tout outil qui decouvre les tests depuis
une copie -- il rend `[]` : la boucle ne tourne pas, l'assertion finale
porte sur un ensemble vide, et **le vert est IDENTIQUE a celui d'un
controle qui a tout verifie**. Mesure du 13/09, le meme controle :

    depuis la racine   TRI-7 : 0 / 20 plans   VERT
    depuis ailleurs    TRI-7 : 0 /  0 plans   VERT AUSSI

⚠️ LE CORRECTIF TIENT DEUX CHOSES, ET IL FAUT LES DEUX : le chemin DERIVE
de `__file__`, et une PREMISSE qui exige une assiette non vide. *Corriger
le chemin sans poser la premisse fermerait l'occurrence en laissant la
CLASSE ouverte -- un `plans/` deplace rendrait le sceau muet a nouveau.*
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys
import types
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from core.plan_tarifaire import Facteur, PlanTarifaire

_ZONE = _RACINE / 'direction_non_vie' / 'tarification'


def _plans():
    """⚠️ DERIVE DE `__file__` -- c'est le geste que ce fichier surveille,
    il ne peut pas etre le premier a l'enfreindre."""
    return sorted((_RACINE / 'plans').glob('*.yaml'))


class TestLePlanSeScelleEnEntier(unittest.TestCase):

    def test_PLA1_SCEAU_une_reference_hors_modalites_est_REFUSEE(self):
        """⚠️⚠️ LE SCEAU DE `PLN-2`. Une reference absente de l'enumeration
        n'ecarte aucune modalite : le facteur produit k colonnes pour k
        modalites, et la matrice devient colineaire avec la constante."""
        with self.assertRaises(ValueError) as ctx:
            Facteur(nom='zone', type='categoriel', encodage='one_hot',
                    modalites=('A', 'B', 'C'), reference='Z')
        msg = str(ctx.exception)
        #: ⚠️ LE MESSAGE DOIT NOMMER LES MODALITES ADMISES : un refus qui
        #: ne dit pas quoi declarer oblige a relire le code.
        for attendu in ('zone', 'Z', 'A'):
            self.assertIn(attendu, msg,
                          f"le refus ne nomme pas {attendu!r} : {msg[:80]}")
        print(f"    PLA-1 SCEAU : reference hors modalites REFUSEE, message "
              f"de {len(msg)} caracteres")

    def test_PLA2_CONTRE_EPREUVE_une_reference_LEGITIME_passe(self):
        """⚠️ Le second sens : un controle qui refuserait tout ne
        surveillerait rien. Une reference declaree doit ecarter SA
        modalite, et l'absence de reference reste permise."""
        f = Facteur(nom='zone', type='categoriel', encodage='one_hot',
                    modalites=('A', 'B', 'C'), reference='A')
        self.assertEqual(len(f.colonnes_produites()), 2,
                         f"reference legitime : {f.colonnes_produites()}")
        g = Facteur(nom='zone', type='categoriel', encodage='one_hot',
                    modalites=('A', 'B', 'C'), reference=None)
        self.assertEqual(len(g.colonnes_produites()), 2)
        print(f"    PLA-2 contre-epreuve : reference declaree -> "
              f"{f.colonnes_produites()}, aucune reference -> "
              f"{len(g.colonnes_produites())} colonnes")

    def test_PLA3_SCEAU_l_empreinte_couvre_TOUS_les_champs_du_plan(self):
        """⚠️⚠️ LE SCEAU DE `PLN-1`, ET IL PORTE SUR LE COMPORTEMENT. On ne
        verifie pas que la charge cite vingt noms -- on verifie qu'un champ
        NON COUVERT fait LEVER. *Une charge enumeree a la main atteste ce
        qu'on a pense a y mettre ; une charge qui se DERIVE ne peut pas
        oublier en silence.*"""
        plan = PlanTarifaire.depuis_yaml(str(_plans()[0]))
        self.assertTrue(plan.empreinte().startswith('s'),
                        "l'empreinte ne se calcule plus")
        #: ⚠️ ON SIMULE UN 21e CHAMP en faisant mentir `dataclasses.fields`
        #: -- le controle doit le voir et REFUSER de signer.
        #: ⚠️ LE FAUX CHAMP NE PORTE QUE `.name`, PARCE QUE C'EST LE SEUL
        #: ATTRIBUT QUE LE CORRECTIF LIT. Un `dataclasses.field()` truque
        #: laisserait croire qu'il en faut davantage.
        import core.plan_tarifaire as PT
        vrai = PT.dataclasses.fields
        faux = types.SimpleNamespace(name='__champ_ajoute_demain__')

        def _mentir(obj):
            champs = list(vrai(obj))
            if obj is PlanTarifaire or isinstance(obj, PlanTarifaire):
                return tuple(champs) + (faux,)
            return champs

        PT.dataclasses.fields = _mentir
        try:
            with self.assertRaises(ValueError) as ctx:
                plan.empreinte()
            self.assertIn('__champ_ajoute_demain__', str(ctx.exception),
                          'le refus ne NOMME pas le champ oublie')
        finally:
            PT.dataclasses.fields = vrai
        #: ⚠️ ET L'ETAT EST RENDU : sans cette remise, le fichier laisserait
        #: le module truque pour ses voisins.
        self.assertTrue(plan.empreinte().startswith('s'),
                        "l'empreinte ne se recalcule plus apres le plant")
        print(f"    PLA-3 SCEAU : un 21e champ non couvert fait LEVER -- "
              f"{str(ctx.exception)[:54]}")

    def test_PLA4_SCEAU_aucun_controle_ne_lit_les_plans_par_le_CWD(self):
        """⚠️⚠️ LE SCEAU DE `CWD-1`, RELEVE PAR AST SUR TOUTE LA ZONE. Un
        chemin relatif au repertoire courant rend `[]` depuis ailleurs, et
        un controle sur ensemble vide est VERT. *Le vert d'un controle qui
        n'a rien regarde ressemble exactement a celui qui a tout
        verifie.*"""
        fautifs = []
        for p in sorted(_ZONE.rglob('*.py')):
            if '__pycache__' in str(p) or 'audit_2026_08' in str(p):
                continue
            try:
                a = ast.parse(p.read_bytes().decode('utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for n in ast.walk(a):
                #: ⚠️⚠️ LE CRITERE PORTE SUR L'USAGE, PAS SUR LE TEXTE. Ma
                #: premiere redaction signalait TOUTE chaine commencant par
                #: `plans/` -- elle accusait donc les litteraux de sa
                #: PROPRE detection, ici meme et dans `test_racine_derivee`.
                #: *Un controle trop etroit accuse ; un controle qui lit le
                #: TEXTE au lieu de l'USAGE aussi.* On ne retient qu'un
                #: chemin REELLEMENT ouvert : passe a un appel qui lit.
                if not isinstance(n, ast.Call):
                    continue
                nom_appel = (getattr(n.func, 'attr', None)
                             or getattr(n.func, 'id', None) or '')
                if nom_appel not in ('glob', 'open', 'depuis_yaml', 'Path',
                                     'read_text', 'read_bytes', 'iglob'):
                    continue
                for arg in n.args:
                    if (isinstance(arg, ast.Constant)
                            and isinstance(arg.value, str)
                            and arg.value.replace('\\', '/').startswith(
                                'plans/')):
                        fautifs.append(
                            f'{p.relative_to(_RACINE)}:{n.lineno} '
                            f'{nom_appel}({arg.value!r})')
        self.assertEqual(
            fautifs, [],
            "ces chemins vers `plans/` sont relatifs au REPERTOIRE COURANT : "
            "lances depuis ailleurs ils rendent une assiette VIDE, et le "
            "controle passe VERT sans rien regarder.\n  "
            + "\n  ".join(fautifs))
        print('    PLA-4 SCEAU : 0 chemin vers `plans/` relatif au '
              'repertoire courant')

    def test_PLA5_CONTRE_EPREUVE_les_20_plans_gardent_leur_empreinte(self):
        """⚠️⚠️ CE QUE CE LOT NE DOIT SURTOUT PAS DEPLACER. L'empreinte
        scelle un tarif signe : si les plans livres en changeaient, toutes
        les references gelees seraient a refaire, et pour rien."""
        plans = _plans()
        self.assertGreaterEqual(
            len(plans), 20,
            f"seulement {len(plans)} plan(s) lus : l'assiette de cette "
            f"contre-epreuve s'est vidée")
        empreintes = {}
        for y in plans:
            p = PlanTarifaire.depuis_yaml(str(y))
            empreintes[y.stem] = p.empreinte()
        #: ⚠️ UNE VALEUR GELEE, MESUREE AVANT LE LOT : si elle bougeait, le
        #: correctif aurait touche la signature.
        self.assertEqual(
            empreintes.get('auto'), 's10:a88e37662398e81e',
            f"l'empreinte du plan `auto` a BOUGE : "
            f"{empreintes.get('auto')} au lieu de s10:a88e37662398e81e")
        self.assertEqual(len(set(empreintes.values())), len(empreintes),
                         'deux plans portent la MEME empreinte')
        print(f"    PLA-5 contre-epreuve : {len(empreintes)} plans, "
              f"empreintes distinctes, `auto` inchange")


if __name__ == '__main__':
    unittest.main(verbosity=2)
