"""CONTROLE POSITIF — chaque bloc de fermeture de l'archive NOMME son constat.

POURQUOI CE FICHIER EXISTE
──────────────────────────
L'archive `audit_2026_08/` compte les constats fermes en lisant les blocs
`> ✅` des `releve_*.md`. Pendant des semaines, ces blocs n'ont PAS nomme le
constat qu'ils fermaient : ils etaient seulement POSITIONNES a cote. Et la
position n'etait pas uniforme —

  · le lot du 25/08 place le bloc AVANT l'en-tete du constat qu'il ferme ;
  · tous les autres lots le placent APRES.

⚠️⚠️ RESULTAT MESURE : le compte publie a ete FAUX DEUX FOIS (40, puis 39).
Un parseur « en-tete -> en-tete suivant » attribuait les blocs du 25/08 au
constat PRECEDENT. Le chiffre etait faux dans un document qui fait foi, et
personne ne pouvait le voir.

⚠️ LE CORRECTIF N'EST PAS D'UNIFORMISER LE PLACEMENT — ce serait deplacer le
probleme : la main suivante n'aurait aucun moyen de savoir dans quel sens
ecrire, et l'erreur reviendrait en silence. Le correctif est que CHAQUE BLOC
PORTE SA CLE. Alors la position n'a plus d'importance, pour un parseur comme
pour un lecteur.

CE QUE CE CONTROLE EXIGE
────────────────────────
  ① tout bloc `> ✅` porte au moins une cle `agent/Cn` dans son MARQUEUR
    d'ouverture — la zone avant le premier `·` ;
  ② cette cle designe un constat qui EXISTE dans ce fichier ;
  ③ son prefixe correspond au fichier ou elle est ecrite.

Il ne dit RIEN du placement : c'est le but.

⚠️ ET IL DISTINGUE L'ATTRIBUTION DU RENVOI. Un bloc peut legitimement CITER
un constat d'un autre agent (« meme geste qu'`a3/C9` ») : ces citations sont
libres. Seul le MARQUEUR D'OUVERTURE dit ce que le bloc ferme. Ce controle a
d'abord ete ecrit sans cette distinction, et il a fait tomber quatre renvois
parfaitement legitimes -- il accusait ce qu'il aurait du laisser passer.
"""
import os
import re
import sys
import unicodedata
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

ARCHIVE = os.path.join(os.path.dirname(__file__), 'audit_2026_08')

#: prefixe de cle par fichier de releve — resolu vers un CHEMIN REEL, jamais
#: devine : un fichier absent fait tomber le test plutot que d'etre ignore.
PREFIXE = {
    'releve_a1_ingestion.md': 'a1',
    'releve_a2_preprocessing.md': 'a2',
    'releve_a3_glm.md': 'a3',
    'releve_a4_ml.md': 'a4',
    'releve_a5_deep_learning.md': 'a5',
    'releve_a6_comparaison.md': 'a6',
    'releve_charts_tarif.md': 'charts',
    'releve_conformite_reglementaire.md': 'conformite',
    'releve_pipeline_agents.md': 'agents',
    'releve_pipeline_tarifaire.md': 'pipeline',
    'releve_plan_tarifaire.md': 'plan',
    'releve_qualite_donnees.md': 'qualite',
    'releve_services_rapport.md': 'services',
    'releve_socle_core.md': 'socle',
}

_ENTETE = re.compile(r'^\*\*(C\d+[a-z]?)(?:\*\*)?\s*—', re.MULTILINE)
_BLOC = re.compile(r'^> ✅', re.MULTILINE)
_CLE = re.compile(r'`([a-z0-9_]+)/(C\d+[a-z]?)`')


def _lire(nom):
    chemin = os.path.join(ARCHIVE, nom)
    with open(chemin, encoding='utf-8') as f:
        return unicodedata.normalize('NFC', f.read())


def _marqueur(bloc):
    """La zone d'ATTRIBUTION : le debut du bloc, avant le premier `·`.

    ⚠️ Au-dela, ce sont des RENVOIS — un bloc cite volontiers le constat d'un
    autre agent, et cela ne dit rien de ce qu'il ferme.
    """
    tete = bloc.split('·', 1)[0]
    return tete if len(tete) < 160 else bloc[:160]


def _blocs(texte):
    """Chaque bloc `> ✅`, coupe au prochain en-tete de constat."""
    entetes = [m.start() for m in _ENTETE.finditer(texte)]
    for m in _BLOC.finditer(texte):
        debut = m.start()
        fin = min([e for e in entetes if e > debut] + [len(texte)])
        yield debut, texte[debut:fin]


class TestArchiveClesFermeture(unittest.TestCase):
    """Un bloc de fermeture sans cle est un compte qui ne se verifie pas."""

    def test_les_quatorze_releves_existent(self):
        """⚠️ Un fichier disparu doit FAIRE TOMBER, jamais etre saute en
        silence : le controle porterait alors sur une assiette reduite sans
        que personne ne le sache."""
        for nom in PREFIXE:
            self.assertTrue(
                os.path.isfile(os.path.join(ARCHIVE, nom)),
                f"Relevé manquant : {nom}. Le contrôle des clés porterait sur "
                f"une assiette réduite sans le dire.")

    def test_chaque_bloc_de_fermeture_porte_sa_cle(self):
        """① Aucun bloc `> ✅` ne peut rester anonyme."""
        anonymes = []
        for nom in PREFIXE:
            texte = _lire(nom)
            for debut, bloc in _blocs(texte):
                if not _CLE.search(_marqueur(bloc)):
                    ligne = texte[:debut].count('\n') + 1
                    anonymes.append(f"{nom}:{ligne} — {bloc[:60].strip()}")
        self.assertEqual(
            anonymes, [],
            "Bloc(s) de fermeture SANS clé :\n  " + "\n  ".join(anonymes) +
            "\n⚠️ Un bloc sans clé n'est rattaché que par sa POSITION, et la "
            "position n'est pas fiable : c'est ce qui a rendu le compte des "
            "constats fermés faux deux fois.")

    def test_chaque_cle_designe_un_constat_qui_existe(self):
        """② et ③ — la clé doit pointer vers un constat réel, du bon fichier."""
        fautives = []
        for nom, prefixe in PREFIXE.items():
            texte = _lire(nom)
            constats = {m.group(1) for m in _ENTETE.finditer(texte)}
            for debut, bloc in _blocs(texte):
                for pre, cle in _CLE.findall(_marqueur(bloc)):
                    ligne = texte[:debut].count('\n') + 1
                    if pre != prefixe:
                        fautives.append(
                            f"{nom}:{ligne} — clé `{pre}/{cle}` dans un relevé "
                            f"de préfixe '{prefixe}'")
                    elif cle not in constats:
                        fautives.append(
                            f"{nom}:{ligne} — `{pre}/{cle}` ne correspond à "
                            f"aucun constat de ce fichier")
        self.assertEqual(
            fautives, [],
            "Clé(s) de fermeture fautive(s) :\n  " + "\n  ".join(fautives))

    def test_le_controle_tombe_sur_un_bloc_anonyme(self):
        """⚠️ SECOND SENS — le contrôle doit ÉCHOUER sur la violation.

        On plante un bloc sans clé et on vérifie que la détection le voit.
        Sans cette assertion, un contrôle qui ne détecte plus rien passerait
        pour un contrôle satisfait : *le silence ressemblerait au succès.*
        """
        faux = ("**C1 — un constat.**\n\n"
                "> ✅ **FERMÉ** — mais ce bloc ne nomme aucun constat.\n\n"
                "**C2 — un autre.**\n")
        anonymes = [b for _, b in _blocs(faux) if not _CLE.search(_marqueur(b))]
        self.assertEqual(len(anonymes), 1,
                         "La détection ne voit plus un bloc anonyme.")

    def test_un_renvoi_vers_un_autre_agent_est_LEGITIME(self):
        """⚠️ SECOND SENS INVERSE — le contrôle ne doit PAS accuser un renvoi.

        Un bloc qui ferme `a4/C8` et cite `a3/C9` en comparaison est correct.
        Sans cette assertion, le contrôle redeviendrait trop large et
        interdirait les renvois, qui sont l'une des valeurs de l'archive.
        """
        bloc = ("> ✅ **`a4/C8`** · **FERMÉ** — même geste qu'`a3/C9` : la "
                "légende dérive de `len(items)`.")
        attribues = _CLE.findall(_marqueur(bloc))
        self.assertEqual(attribues, [('a4', 'C8')],
                         "Le renvoi `a3/C9` est compté comme une attribution.")

    def test_le_controle_tombe_sur_une_cle_inexistante(self):
        """⚠️ SECOND SENS — une clé qui ne désigne rien doit être vue."""
        faux = ("**C1 — un constat.**\n\n"
                "> ✅ **`a3/C99`** · FERMÉ — clé vers un constat inexistant.\n")
        constats = {m.group(1) for m in _ENTETE.finditer(faux)}
        trouvees = [c for _, c in _CLE.findall(_marqueur(faux)) if c not in constats]
        self.assertEqual(trouvees, ['C99'],
                         "La détection ne voit plus une clé sans constat.")


if __name__ == '__main__':
    unittest.main()
