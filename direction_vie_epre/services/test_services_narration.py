# -*- coding: utf-8 -*-
"""C5c-0 — le badge d'origine de la narration ne doit rien affirmer de faux.

⚠️ CE QUE CES TESTS EMPÊCHENT DE REVENIR. Les trois rapports Vie affichaient
« ❆ Commentaire actuariel manuel » dès que la narration repliait. Or le repli
n'est pas manuel : c'est le `commentaire` de l'agent appelant, une f-string.
Le document attribuait à un humain le texte d'un gabarit.

⚠️ ET LE BADGE S'AFFICHE SANS CONDITION. Quand aucune narration n'existait, le
corps portait « Narration non disponible » et le badge juste au-dessus
affirmait le contraire — deux phrases contradictoires dans le même bloc.

⚠️ L'ANCRE EST LE TEXTE PUBLIÉ, relu dans le source du module : c'est lui que
le lecteur reçoit, pas une constante intermédiaire.
"""
import ast
import os

MODULES = ('rapport_vie', 'rapport_epre', 'rapport_rvie2')

#: Le vocabulaire honnête, celui d'A7 (`n5_rapport`) : trois états nommés, et
#: le silence quand il n'y a rien à dire.
ETAT_REPLI = 'manuel'
ETAT_VIDE = 'aucune'
ETAT_MODELE = 'claude_api'


def _badge(module):
    """Le dictionnaire `ai_badge` tel qu'il est écrit dans le module."""
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          module + '.py')
    with open(chemin, encoding='utf-8') as f:
        arbre = ast.parse(f.read())
    for n in ast.walk(arbre):
        if not (isinstance(n, ast.Assign)
                and any(getattr(t, 'id', '') == 'ai_badge' for t in n.targets)):
            continue
        if isinstance(n.value, ast.Call) and isinstance(n.value.func,
                                                        ast.Attribute):
            d = n.value.func.value
            if isinstance(d, ast.Dict):
                return {k.value: v.value for k, v in zip(d.keys, d.values)}
    raise AssertionError(f'{module} : aucun dictionnaire `ai_badge` trouve')


def test_aucun_badge_ne_dit_manuel():
    """⚠️ Le mot qui attribuait à un humain le texte d'un gabarit."""
    for module in MODULES:
        for etat, texte in _badge(module).items():
            assert 'manuel' not in texte.lower(), (
                f"{module} : l'etat {etat!r} publie {texte!r} — le repli est "
                f"une f-string de l'agent, pas le texte d'un actuaire")


def test_le_repli_porte_le_vocabulaire_deja_honnete_du_depot():
    """A7 dit « Mode standard » pour le meme cas depuis toujours."""
    for module in MODULES:
        badge = _badge(module)
        assert ETAT_REPLI in badge, f'{module} : etat de repli absent'
        assert 'Mode standard' in badge[ETAT_REPLI], (
            f'{module} : le repli publie {badge[ETAT_REPLI]!r} au lieu du '
            f"vocabulaire d'A7")


def test_sans_narration_le_badge_n_affirme_rien():
    """⚠️ Le badge etant rendu sans condition, le seul texte honnete quand il
    n'y a aucune narration est l'absence de texte."""
    for module in MODULES:
        badge = _badge(module)
        assert ETAT_VIDE in badge, f'{module} : etat vide absent'
        assert badge[ETAT_VIDE] == '', (
            f'{module} : sans narration, le badge affirme encore '
            f'{badge[ETAT_VIDE]!r}')


def test_les_trois_etats_sont_couverts_et_le_modele_reste_annonce():
    """Trois etats, pas deux : la binaire d'origine confondait repli et vide."""
    for module in MODULES:
        badge = _badge(module)
        assert set(badge) == {ETAT_MODELE, ETAT_REPLI, ETAT_VIDE}, (
            f'{module} : etats {sorted(badge)!r}')
        assert badge[ETAT_MODELE], (
            f"{module} : l'etat modele ne dit plus rien")
