r"""
==============================================================================
  LA RACINE SE DERIVE DU FICHIER -- AUCUN CHEMIN LOCAL DANS UN DEPOT PUBLIC
==============================================================================

⚠️⚠️ CE QUE CE LOT FERME, ET C'EST UNE DONNEE PERSONNELLE PUBLIEE. Ce depot
est PUBLIC, deliberement. Il portait le chemin local d'une personne reelle --
donc son nom d'utilisateur -- dans **37 fichiers versionnes, 62 occurrences**,
toutes sous `audit_2026_08/preuves/` (mesure du 10/09/2026, relevee sur
`git ls-files`, donc sur ce qui est REELLEMENT publie).

  Le depot enonce lui-meme la regle : *`declare_par` est un ROLE, JAMAIS un
  nom.* Le commit `1a76521` l'a fermee pour UNE fixture. Elle survivait dans
  37 fichiers de preuve, ecrits bien avant, que le scan d'avant-poussee ne
  pouvait pas voir -- **il ne lit que le DIFF, jamais l'etat du depot**.

⚠️ ET LA DERIVATION REPARE UN SECOND DEFAUT AU PASSAGE : ces fichiers ne
s'executaient que sur UNE machine, celle de leur auteur.

⚠️⚠️ L'ASSIETTE DE CE CONTROLE EST LE DEPOT ENTIER, PAS `preuves/`. Le defaut
etait concentre la ; le limiter la reviendrait a surveiller l'endroit ou on
vient de nettoyer. *La question a tout garde-fou est << sur quelle
assiette ? >>.*
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import re
import subprocess
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

#: ⚠️ Les trois formes d'un repertoire personnel : `<disque>:` suivi de
#: `Users`, `/home/<compte>/`, et `/Users/<compte>/` sur macOS. Un chemin
#: absolu vers un disque partage n'en est pas un.
#:
#: ⚠️⚠️ ET CE FICHIER NE DOIT PAS SE FAIRE ROUGIR LUI-MEME. Les motifs sont
#: DECRITS, jamais reproduits : le controle ci-dessous lit TOUS les fichiers
#: suivis, y compris celui-ci. Mesure du 10/09/2026 : ma premiere redaction
#: citait le motif en clair dans deux docstrings, et `RD-1` rougissait sur son
#: propre fichier des qu'il etait indexe. *Le motif du chantier applique au
#: FILET, une fois de plus.*
_CHEMIN_PERSONNEL = re.compile(r'([A-Za-z]:[\\/]+Users[\\/]+'
                               r'|/home/[a-z0-9_.-]+/'
                               r'|/Users/[A-Za-z0-9_.-]+/)')

_PREUVES = _RACINE / 'direction_non_vie' / 'tarification' / 'audit_2026_08' \
    / 'preuves'

#: Les extensions ou un chemin en dur est un texte publie, pas un binaire.
_LISIBLES = ('.py', '.md', '.yaml', '.yml', '.json', '.txt', '.cfg', '.toml',
             '.ini', '.rst')


def _fichiers_suivis() -> list[pathlib.Path]:
    """Ce que git PUBLIE reellement -- et rien d'autre.

    ⚠️ Un `.gitignore` peut cacher un fichier au disque ; seul `git ls-files`
    dit ce qui part chez le lecteur du depot public.
    """
    try:
        sortie = subprocess.run(
            ['git', 'ls-files'], cwd=str(_RACINE), capture_output=True,
            text=True, encoding='utf-8', errors='replace',
            timeout=120, check=False).stdout
        rels = [f for f in sortie.split('\n') if f.endswith(_LISIBLES)]
        if rels:
            return [_RACINE / r for r in rels if (_RACINE / r).is_file()]
    except (OSError, subprocess.SubprocessError):
        pass
    return [f for f in _RACINE.rglob('*')
            if f.is_file() and f.suffix in _LISIBLES
            and '.git' not in f.parts]


class TestAucunCheminPersonnelPublie(unittest.TestCase):

    def test_RD1_LE_SCEAU_aucun_fichier_SUIVI_ne_porte_un_chemin_personnel(
            self):
        """⚠️⚠️ LE CONTROLE CENTRAL, ET SON ASSIETTE EST TOUT LE DEPOT SUIVI.
        Un plant qui remettrait un seul chemin personnel -- dans n'importe
        quel fichier publie, pas seulement dans `preuves/` -- doit faire
        rougir ceci."""
        fautifs = []
        for p in _fichiers_suivis():
            try:
                txt = p.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            for numero, ligne in enumerate(txt.split('\n'), 1):
                if _CHEMIN_PERSONNEL.search(ligne):
                    fautifs.append(f"{p.relative_to(_RACINE)}:{numero}")
        self.assertEqual(
            fautifs, [],
            f"{len(fautifs)} occurrence(s) d'un repertoire personnel dans un "
            f"depot PUBLIC : {fautifs[:10]}")
        print(f"    RD-1 SCEAU : 0 chemin personnel sur "
              f"{len(_fichiers_suivis())} fichiers publies")

    def test_RD2_les_preuves_DERIVENT_leur_racine(self):
        """⚠️ Le miroir de RD-1 : l'absence de chemin en dur pourrait venir
        d'une SUPPRESSION. Ici on verifie que la derivation est bien POSEE."""
        sans = []
        for p in sorted(_PREUVES.glob('*.py')):
            try:
                arbre = ast.parse(p.read_text(encoding='utf-8'))
            except (SyntaxError, OSError):
                sans.append(f"{p.name} (illisible)")
                continue
            noms = {t.id for n in ast.walk(arbre) if isinstance(n, ast.Assign)
                    for t in n.targets if isinstance(t, ast.Name)}
            if '_RACINE_DERIVEE' not in noms:
                sans.append(p.name)
        self.assertEqual(
            sans, [],
            f"{len(sans)} preuve(s) ne posent pas `_RACINE_DERIVEE` : {sans}")
        print(f"    RD-2 les {len(list(_PREUVES.glob('*.py')))} preuves "
              f"posent leur racine derivee")

    def test_RD3_la_derivation_rend_la_racine_REELLE_pour_CHACUNE(self):
        """⚠️⚠️ MESUREE SUR LES 37, PAS SUR UN EXEMPLAIRE. *Une derivation qui
        pointerait ailleurs remplacerait une faute par une panne* -- et un
        seul fichier deplace d'un niveau suffirait. Ce controle relit le
        `parents[N]` reellement ecrit dans chaque fichier et verifie qu'il
        retombe sur la racine du depot."""
        faux = []
        for p in sorted(_PREUVES.glob('*.py')):
            try:
                arbre = ast.parse(p.read_text(encoding='utf-8'))
            except (SyntaxError, OSError):
                continue
            for n in ast.walk(arbre):
                if not (isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name)
                                and t.id == '_RACINE_DERIVEE'
                                for t in n.targets)):
                    continue
                niveaux = [k.slice.value for k in ast.walk(n)
                           if isinstance(k, ast.Subscript)
                           and isinstance(k.value, ast.Attribute)
                           and k.value.attr == 'parents'
                           and isinstance(k.slice, ast.Constant)]
                if not niveaux:
                    faux.append(f"{p.name} : aucun `parents[N]` lisible")
                    continue
                niveau = niveaux[0]
                parents = p.resolve().parents
                if niveau >= len(parents):
                    faux.append(f"{p.name} : parents[{niveau}] hors bornes")
                elif parents[niveau] != _RACINE.resolve():
                    faux.append(f"{p.name} : parents[{niveau}] -> "
                                f"{parents[niveau].name}")
        self.assertEqual(
            faux, [],
            f"{len(faux)} derivation(s) ne retombent pas sur la racine : "
            f"{faux}")
        # ⚠️ ET LA CONTRE-EPREUVE DE LA RACINE ELLE-MEME : `plans/` s'y
        # trouve. Sans elle, une racine « juste » pourrait etre n'importe
        # quel repertoire du bon niveau.
        self.assertTrue((_RACINE / 'plans').is_dir(),
                        "la racine derivee ne contient pas `plans/` : ce "
                        "n'est pas la racine du depot")
        print(f"    RD-3 les {len(list(_PREUVES.glob('*.py')))} derivations "
              f"retombent sur la racine, et `plans/` s'y trouve")

    def test_RD4_les_preuves_COMPILENT_toutes(self):
        """⚠️ La substitution a touche 37 fichiers a la fois. Une seule
        syntaxe cassee et la preuve concernee n'existe plus."""
        casses = []
        for p in sorted(_PREUVES.glob('*.py')):
            try:
                compile(p.read_text(encoding='utf-8'), str(p), 'exec')
            except (SyntaxError, ValueError) as e:
                casses.append(f"{p.name} : {type(e).__name__}")
        self.assertEqual(casses, [], f"preuve(s) cassee(s) : {casses}")
        print(f"    RD-4 les {len(list(_PREUVES.glob('*.py')))} preuves "
              f"compilent")

    def test_RD5_le_chemin_HORS_DEPOT_ne_pointe_pas_dans_le_depot(self):
        """⚠️⚠️ UN SEUL DES 62 CHEMINS NE POUVAIT PAS SE DERIVER DE LA RACINE :
        un repertoire de RENDU. Le deriver de la racine ferait ecrire des PNG
        dans le depot -- une faute remplacee par une autre. Il passe par le
        repertoire temporaire du systeme, et ce controle le tient."""
        import tempfile
        temporaire = pathlib.Path(tempfile.gettempdir()).resolve()
        vus = 0
        for p in sorted(_PREUVES.glob('*.py')):
            try:
                arbre = ast.parse(p.read_text(encoding='utf-8'))
            except (SyntaxError, OSError):
                continue
            for n in ast.walk(arbre):
                if not (isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'SORTIE'
                                for t in n.targets)):
                    continue
                vus += 1
                source = ast.unparse(n.value)
                self.assertIn(
                    'gettempdir', source,
                    f"{p.name} : `SORTIE` ne passe pas par le repertoire "
                    f"temporaire du systeme -- {source[:70]}")
                self.assertNotIn(
                    '_RACINE_DERIVEE', source,
                    f"{p.name} : un repertoire de RENDU derive de la racine "
                    f"ecrirait dans le depot")
        self.assertGreaterEqual(
            vus, 1,
            "aucun `SORTIE` releve : l'assiette de ce controle est vide, il "
            "n'atteste plus rien")
        self.assertFalse(
            str(temporaire).startswith(str(_RACINE.resolve())),
            "le repertoire temporaire du systeme est DANS le depot : le "
            "rendu polluerait quand meme")
        print(f"    RD-5 {vus} repertoire(s) de rendu, hors du depot")


if __name__ == '__main__':
    unittest.main(verbosity=2)
