#!/usr/bin/env python
# =============================================================================
#  ActuarIA — LE MESSAGE DE COMMIT SE REFUSE, IL NE SE RAPPELLE PAS
# =============================================================================
#
#  ⚠️ POURQUOI CE FICHIER EXISTE. Trois règles permanentes de Selasse portent
#  sur le message de commit : sujet sur UNE ligne d'au plus 76 caractères,
#  aucune ligne du corps au-delà de 76, aucun caractère non-ASCII. Elles sont
#  écrites, datées, motivées — et elles ont été enfreintes TROIS FOIS en cinq
#  jours, avec le même dépassement d'un caractère :
#
#      8bc1ddf (14/08) — sujet à 77, lu APRÈS le push
#      a032bd4 (15/08) — la règle mord, même violation attrapée avant
#      ad9595b (18/08) — cinq lignes à 77, lues APRÈS le push
#
#  La cause est toujours la même : la vérification est placée dans le MÊME
#  bloc de commandes que le `git commit`, pour gagner un aller-retour. Elle
#  s'exécute alors après, et rapporte la violation quand il est trop tard.
#
#  ⚠️ UNE RÈGLE QUI A ÉCHOUÉ DEUX FOIS ET TENU UNE FOIS N'EST PAS TENUE PAR LE
#  FAIT D'ÊTRE ÉCRITE. Ce module ne rappelle rien : il REFUSE. C'est le
#  principe du dépôt — « c'est le contrôle qui a attrapé la prose, pas
#  l'inverse » — appliqué à la procédure de commit elle-même.
#
#  Il vit dans le dépôt, donc versionné, relisible dans un diff, et vérifié
#  par la gate `core` (`core/test_verif_message_commit.py`). Le déclencheur,
#  lui, est local (`.git/hooks/commit-msg`) : git ne versionne pas les hooks.
# =============================================================================

from __future__ import annotations

import sys
from typing import List

#: La limite, identique pour le sujet et pour toute ligne du corps.
LARGEUR_MAX = 76

#: git insère cette ligne quand `commit.verbose` est actif ; tout ce qui suit
#: est le diff, jamais le message. Le hook reçoit le fichier AVANT nettoyage.
CISEAUX = '# ------------------------ >8 ------------------------'


def lignes_du_message(texte: str) -> List[str]:
    """Les lignes réellement enregistrées, débarrassées de ce que git retire.

    ⚠️ CE FILTRE N'EST PAS UN CONFORT, IL EST NÉCESSAIRE. Le hook `commit-msg`
    reçoit le fichier BRUT : il contient les lignes de commentaire que git
    ajoute (`# Please enter the commit message...`), souvent longues et — en
    locale française — accentuées. Les compter ferait échouer TOUS les
    commits, y compris conformes : un garde-fou qui refuse le légitime est
    pire que pas de garde-fou.
    """
    lignes: List[str] = []
    for ligne in texte.splitlines():
        if ligne.rstrip() == CISEAUX:
            break
        if ligne.startswith('#'):
            continue
        lignes.append(ligne)
    return lignes


def verifier(texte: str) -> List[str]:
    """Les violations du message, en clair. Liste vide = conforme.

    Trois règles, et seulement trois — celles que Selasse a nommées :
      1. le sujet tient sur UNE ligne d'au plus 76 caractères ;
      2. aucune ligne du corps ne dépasse 76 caractères ;
      3. aucun caractère non-ASCII, nulle part.
    """
    lignes = lignes_du_message(texte)
    utiles = [l for l in lignes if l.strip()]
    if not utiles:
        return ['message vide']

    violations: List[str] = []

    # ── 1. le sujet ──────────────────────────────────────────────────────────
    sujet = utiles[0]
    if len(sujet) > LARGEUR_MAX:
        violations.append(
            f'sujet : {len(sujet)} caracteres (maximum {LARGEUR_MAX})')

    # ⚠️ LE SUJET TIENT SUR UNE LIGNE, DONC UNE LIGNE VIDE LE SÉPARE DU CORPS.
    # Sans ce contrôle, un message dont la 2e ligne est du texte verrait git
    # la coller au sujet dans tout affichage court (`--oneline`, GitHub).
    idx = lignes.index(sujet)
    if len(lignes) > idx + 1 and lignes[idx + 1].strip():
        violations.append(
            'le sujet doit etre suivi d une ligne vide')

    # ── 2. les lignes du corps ───────────────────────────────────────────────
    for n, ligne in enumerate(lignes, 1):
        if ligne is sujet:
            continue
        if len(ligne) > LARGEUR_MAX:
            violations.append(
                f'ligne {n} : {len(ligne)} caracteres (maximum '
                f'{LARGEUR_MAX}) -- {ligne[:46]}...')

    # ── 3. l'ASCII ───────────────────────────────────────────────────────────
    for n, ligne in enumerate(lignes, 1):
        hors = sorted({c for c in ligne if ord(c) > 127})
        if hors:
            violations.append(
                f'ligne {n} : caracteres non-ASCII {hors} -- {ligne[:46]}...')

    return violations


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print('usage : py scripts/verif_message_commit.py <fichier-message>',
              file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding='utf-8') as f:
            texte = f.read()
    except OSError as e:
        print(f'message illisible : {e}', file=sys.stderr)
        return 2

    violations = verifier(texte)
    if not violations:
        return 0

    print('', file=sys.stderr)
    print('=' * 70, file=sys.stderr)
    print('  MESSAGE DE COMMIT REFUSE', file=sys.stderr)
    print('=' * 70, file=sys.stderr)
    for v in violations:
        print(f'  - {v}', file=sys.stderr)
    print('', file=sys.stderr)
    print('  Regles : sujet <= 76 sur une ligne, corps <= 76 par ligne,',
          file=sys.stderr)
    print('           aucun caractere non-ASCII.', file=sys.stderr)
    print('  Le message est conserve : corrigez-le et relancez le commit.',
          file=sys.stderr)
    print('', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
