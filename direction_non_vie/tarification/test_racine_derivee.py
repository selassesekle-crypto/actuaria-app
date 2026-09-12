r"""
==============================================================================
  UN DEPOT PUBLIC NE PORTE NI CHEMIN LOCAL NI IDENTITE CIVILE
==============================================================================

⚠️⚠️ CE FICHIER COUVRE DEUX FUITES DE LA MEME NATURE, ET LA SECONDE A ETE
AJOUTEE LE 12/09/2026. `RD-1` a ete ecrit pour le CHEMIN local -- donc pour
un nom de compte. Il ne voyait pas le nom de la PERSONNE, qui vivait dans
265 occurrences du perimetre de tarification : valeurs de champ signees,
assertions qui les relisent, et citations d'arbitrage en commentaire.

  *Le chemin et le nom sont la meme donnee personnelle publiee ; les
  separer en deux controles dont un seul existe, c'est surveiller la
  moitie de la fuite.*

⚠️ QUATRE DENTS, ET CHACUNE DIT SON ASSIETTE :
  · `RD-6` le DETECTEUR lui-meme recoit les deux sens, avant tout le reste ;
  · `RD-7` un champ de signature du perimetre porte un ROLE -- detection par
    la FORME, donc un nom JAMAIS VU est visible ;
  · `RD-8` l'identite protegee n'apparait NULLE PART dans le perimetre, ni
    en champ, ni en commentaire, ni en docstring ;
  · `RD-9` le reste du depot est une DETTE MESUREE sous plafond gele : elle
    ne peut que decroitre.

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
import collections
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

#: ── L'IDENTITE, SECONDE FUITE DE LA MEME NATURE ──────────────────────────
#:
#: ⚠️⚠️ ET LE MOTIF NE PEUT PAS S'ECRIRE EN CLAIR ICI, pour la raison qui
#: vaut deja pour le chemin : `RD-7` relit TOUS les fichiers suivis, celui-ci
#: compris. Ecrit tel quel, il rougirait sur sa propre source. Il est donc
#: ASSEMBLE -- ce fichier porte les morceaux, jamais l'identite.
_IDENTITE_PROTEGEE = re.compile('Sel' + 'asse' + '|' + 'Sek' + 'le',
                                re.IGNORECASE)

#: Le perimetre du lot : les zones nettoyees, ou l'exigence est ZERO.
_PERIMETRE = ('direction_non_vie/tarification/', 'core/', 'scripts/')

#: ⚠️⚠️ `plans/` EST EXEMPTE, ET C'EST UNE DECISION, PAS UN OUBLI. Un plan
#: tarifaire de PRODUCTION est un document signe : son champ `auteur` porte
#: la signature opposable de qui l'a redige, et cette signature ENTRE dans
#: l'empreinte du plan (mesure : `s10:a88e376` -> `s10:840436f` si elle
#: change). Arbitre le 12/09/2026, option (b) : les 20 plans ne bougent pas.
#: *Une fixture versionnee porte un role ; un document signe porte sa
#: signature.* La ligne de partage est la, et elle est ecrite ici pour que
#: l'exemption se lise en meme temps que le controle.
_EXEMPTES = ('plans/',)

#: Les champs qui designent QUI signe, relu, valide ou redige.
_CHAMPS_IDENTITE = {
    'declare_par', 'decide_par', 'qualite_validee_par', 'valide_par',
    'relu_par', 'signataire', 'verifie_par', 'actuaire_nom', 'auteur',
    'qui', 'actuaire_resp', 'profil_valide_par',
}

#: ⚠️⚠️ LE DETECTEUR MARCHE A L'ENVERS D'UNE LISTE NOIRE. Une liste de noms
#: exacts ne voit que ce qu'elle connait deja -- elle n'aurait jamais vu
#: `'Marie Durand'` ni `'S. S.'`, tous deux trouves ici le 12/09. Celui-ci
#: connait le vocabulaire des ROLES et signale ce qui n'en releve pas : un
#: nom jamais vu devient visible.
_MOTS_DE_ROLE = {
    'direction', 'technique', 'actuaire', 'actuariat', 'test', 'tests',
    'souscription', 'controle', 'contrôle', 'lot', 'qualite', 'qualité',
    'signataire', 'validation', 'sceau', 'schema', 'schéma', 'temoin',
    'témoin', 'ctrl', 'reserve', 'réserve', 'cac', 'acpr', 'service',
    'cellule', 'pole', 'pôle', 'comite', 'comité', 'ia', 'du', 'de', 'la',
    'le', 'des', 'et', 'golden', 'auto', 'decennale', 'mrh', 'rcpro',
}

#: une initiale suivie d'un patronyme, ou deux initiales
_FORME_INITIALE = re.compile(r'^[A-Z]\.\s*[A-Z]')

#: ⚠️ PLAFOND GELE DE LA DETTE HORS PERIMETRE, mesure du 12/09/2026 :
#: 83 occurrences, dont 74 dans `normes/ifrs17/` -- un autre chantier, que
#: ce lot n'ouvre pas. Le plafond ne sert pas a tolerer : il sert a ce que
#: la dette ne puisse que DECROITRE pendant qu'on ne la traite pas.
_DETTE_GELEE = 83


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


def _suivis_relatifs() -> list[str]:
    """Les chemins RELATIFS suivis -- pour pouvoir trier par zone."""
    return [str(p.relative_to(_RACINE)).replace('\\', '/')
            for p in _fichiers_suivis()]


def _zone(rel: str, zones: tuple, sauf: tuple = ()) -> bool:
    if any(rel.startswith(x) for x in sauf):
        return False
    return any(rel.startswith(z) for z in zones) if zones else True


def _est_identite_civile(valeur: str) -> bool:
    """La FORME d'un etat civil, jamais un nom connu d'avance.

    ⚠️ SA LIMITE EST DECLAREE, et le sens de son erreur avec : un patronyme
    SEUL (<< Dupont >>) reste invisible, faute de pouvoir le distinguer d'un
    nom de methode actuarielle -- Mack, Benktander, Bornhuetter en sont. Ce
    detecteur SOUS-compte donc, il n'accuse pas.
    """
    valeur = valeur.strip()
    if _FORME_INITIALE.match(valeur):
        return True
    mots = [m for m in re.split(r'[\s,]+', valeur) if m]
    #: plus de trois mots : c'est une PHRASE, pas un etat civil
    if not 2 <= len(mots) <= 3:
        return False
    #: un jeton qui porte un CHIFFRE (<< V9 >>) ou qui tient en UNE lettre
    #: (<< X >>) est un marqueur de fixture, jamais un element d'etat civil
    capitalises = [m for m in mots if m[:1].isupper()
                   and not any(c.isdigit() for c in m)
                   and len(re.sub(r'[^\w]', '', m)) > 1]
    if len(capitalises) < 2:
        return False
    return any(re.sub(r'[^\w]', '', m).lower() not in _MOTS_DE_ROLE
               for m in capitalises)


def _champs_identite(rel: str) -> list[tuple]:
    """(champ, valeur, ligne) pour chaque champ de signature du fichier."""
    p = _RACINE / rel
    try:
        txt = p.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    trouves = []
    if p.suffix == '.py':
        try:
            arbre = ast.parse(txt)
        except SyntaxError:
            return []
        for n in ast.walk(arbre):
            paires = []
            if (isinstance(n, ast.keyword) and n.arg in _CHAMPS_IDENTITE
                    and isinstance(n.value, ast.Constant)):
                paires = [(n.arg, n.value.value, n.value.lineno)]
            elif isinstance(n, ast.Dict):
                paires = [(k.value, v.value, k.lineno)
                          for k, v in zip(n.keys, n.values)
                          if isinstance(k, ast.Constant)
                          and k.value in _CHAMPS_IDENTITE
                          and isinstance(v, ast.Constant)]
            elif isinstance(n, ast.Assign):
                paires = [(t.id, n.value.value, n.lineno)
                          for t in n.targets
                          if isinstance(t, ast.Name)
                          and t.id.lower().lstrip('_') in _CHAMPS_IDENTITE
                          and isinstance(n.value, ast.Constant)]
            trouves += [(c, v, li) for c, v, li in paires
                        if isinstance(v, str)]
    elif p.suffix in ('.yaml', '.yml'):
        for i, ligne in enumerate(txt.split('\n'), 1):
            m = re.match(r'\s*([a-z_]+)\s*:\s*[\'"]?([^\'"#]*)', ligne)
            if m and m.group(1) in _CHAMPS_IDENTITE:
                trouves.append((m.group(1), m.group(2).strip(), i))
    return trouves


class TestAucuneIdentiteCivilePubliee(unittest.TestCase):
    """⚠️⚠️ LA SECONDE FUITE : le nom de la PERSONNE, pas celui du compte."""

    def test_RD6_LE_DETECTEUR_dit_VRAI_sur_un_nom_et_FAUX_sur_un_role(self):
        """⚠️⚠️ CE CONTROLE PASSE AVANT LES DEUX AUTRES, ET C'EST VOULU. Un
        detecteur qui rendrait toujours `False` rendrait `RD-7` vert sur un
        depot plein de noms : *le controle attesterait sans rien surveiller*.
        Ici il recoit les deux sens.

        ⚠️ Les identites de gauche sont SYNTHETIQUES -- des patronymes de
        convention, choisis pour ne designer personne."""
        roles = ('Direction Technique', 'Actuaire Test', 'Controle du lot',
                 'sceau-schema', 'X', 'temoin', 'Direction Technique, IA',
                 'Test V9', 'Actuaire X',
                 'VERIFICATION LOCALE - aucun actuaire responsable')
        identites = ('Marie Durand', 'M. Dupont', 'Jean-Pierre Martin',
                     'A. Nkemelu', 'S. S.', 'Paul Martin')
        for v in roles:
            with self.subTest(role=v):
                self.assertFalse(
                    _est_identite_civile(v),
                    f"{v!r} est un ROLE : le detecteur accuse a tort, et un "
                    f"controle qui accuse finit desactive")
        for v in identites:
            with self.subTest(identite=v):
                self.assertTrue(
                    _est_identite_civile(v),
                    f"{v!r} a la forme d'un etat civil et passe : le "
                    f"detecteur n'atteste rien")
        print(f"    RD-6 detecteur : {len(roles)} roles laisses, "
              f"{len(identites)} identites vues")

    def test_RD7_aucun_champ_de_signature_du_perimetre_ne_porte_un_NOM(self):
        """⚠️⚠️ L'ASSIETTE EST LE PERIMETRE ENTIER, PAS LES FICHIERS NETTOYES.
        Limiter ce controle aux fichiers touches par le lot reviendrait a
        surveiller l'endroit ou l'on vient de nettoyer."""
        fautifs = []
        for rel in _suivis_relatifs():
            if not _zone(rel, _PERIMETRE, _EXEMPTES):
                continue
            for champ, valeur, li in _champs_identite(rel):
                if _est_identite_civile(valeur):
                    fautifs.append(f"{rel}:{li} {champ}={valeur!r}")
        self.assertEqual(
            fautifs, [],
            f"{len(fautifs)} champ(s) de signature portent un etat civil "
            f"dans un depot PUBLIC : {fautifs[:8]}")
        print("    RD-7 SCEAU : 0 identite civile dans les champs signes")

    def test_RD8_l_identite_protegee_n_apparait_NULLE_PART_au_perimetre(self):
        """⚠️⚠️ ET CELUI-CI NE REGARDE PAS QUE LES CHAMPS. Le nom vivait
        surtout dans la PROSE -- 44 commentaires et 69 docstrings citant des
        arbitrages. Un controle limite aux champs aurait rendu vert sur 113
        citations."""
        fautifs = []
        for rel in _suivis_relatifs():
            if not _zone(rel, _PERIMETRE, _EXEMPTES):
                continue
            try:
                txt = (_RACINE / rel).read_text(encoding='utf-8',
                                                errors='replace')
            except OSError:
                continue
            for numero, ligne in enumerate(txt.split('\n'), 1):
                if _IDENTITE_PROTEGEE.search(ligne):
                    fautifs.append(f"{rel}:{numero}")
        self.assertEqual(
            fautifs, [],
            f"{len(fautifs)} occurrence(s) de l'identite protegee dans le "
            f"perimetre : {fautifs[:8]}")
        print("    RD-8 SCEAU : 0 citation nominative au perimetre")

    def test_RD9_la_dette_HORS_perimetre_est_mesuree_et_ne_peut_que_baisser(
            self):
        """⚠️⚠️ CE QUI RESTE SALE EST DIT, PAS TU. 83 occurrences vivent hors
        du perimetre de ce lot -- 74 dans `normes/ifrs17/`. Les corriger
        depuis ici ouvrirait un chantier qui n'est pas celui-la.

        *Une assiette qu'on retrecit sans le dire est un controle qui ment ;
        une dette qu'on mesure sous plafond est une dette qu'on tient.* Le
        plafond ne peut que baisser : toute nouvelle citation le casse."""
        reste = 0
        zones = collections.Counter()
        for rel in _suivis_relatifs():
            if _zone(rel, _PERIMETRE) or _zone(rel, _EXEMPTES):
                continue
            try:
                txt = (_RACINE / rel).read_text(encoding='utf-8',
                                                errors='replace')
            except OSError:
                continue
            n = len(_IDENTITE_PROTEGEE.findall(txt))
            if n:
                reste += n
                zones[rel.split('/')[0] if '/' in rel else '<racine>'] += n
        self.assertLessEqual(
            reste, _DETTE_GELEE,
            f"la dette hors perimetre AUGMENTE : {reste} > {_DETTE_GELEE}. "
            f"Une citation nominative neuve a ete ajoutee : {dict(zones)}")
        #: ⚠️ ET LE SECOND SENS : si elle a baisse, le plafond doit suivre,
        #: sinon il cesse d'etre un plafond et devient une tolerance.
        self.assertGreaterEqual(
            reste, _DETTE_GELEE,
            f"la dette hors perimetre a BAISSE : {reste} < {_DETTE_GELEE}. "
            f"Abaisser `_DETTE_GELEE` a {reste} dans le meme commit.")
        print(f"    RD-9 dette hors perimetre : {reste} occurrence(s), "
              f"plafond {_DETTE_GELEE}, reparties {dict(zones)}")


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
