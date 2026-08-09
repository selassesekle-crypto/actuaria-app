# -*- coding: utf-8 -*-
"""T6 — la narration du modèle, analysée UNE fois et rendue dans chaque format.

⚠️ POURQUOI CE MODULE EXISTE. Le dépôt porte DIX fichiers définissant chacun
leur `_md_to_html`. Mesurés sur neuf formes de markdown, ils ne couvrent pas
les mêmes : A7 en convertit six, la tarification quatre, et le Word de la
tarification AUCUNE — il découpait sur « §N » et écrivait chaque ligne telle
quelle. Résultat mesuré sur un rapport réel : « # », « ## » et « --- »
s'affichaient en clair dans le commentaire actuariel.

⚠️ ET LE WORD N'A PAS BESOIN DE HTML, IL A BESOIN DE STRUCTURE. C'est la
raison de fond pour laquelle un `_md_to_html` partagé ne suffisait pas : un
`.docx` ne sait pas lire une balise, il veut des paragraphes, des styles et
des passages en gras. On ANALYSE donc une fois — et les deux formats rendent
la MÊME structure, ce qui rend impossible qu'ils disent des choses
différentes (le défaut que T1 vient de fermer sur la narration entière).

⚠️ CE MODULE REPREND LA COUVERTURE D'A7 ET L'ÉTEND DE DEUX FORMES MESURÉES :
le titre de niveau 1 (« # ») et la citation (« > »), qu'aucun convertisseur du
dépôt ne traitait. Le reste vient d'A7 : « ## », « ### », gras, italique,
puces, tableaux et règle horizontale.

⚠️ ET IL Y A UNE CEINTURE EN AMONT : le prompt demande désormais au modèle de
n'employer aucun marqueur markdown. Une consigne peut se relâcher — le modèle
glisse un marqueur, ou son comportement change d'une version à l'autre ; une
conversion, elle, traite ce qui arrive quoi qu'il arrive. Les deux, pas l'un
ou l'autre.
"""
import re
from typing import Any, List, NamedTuple, Tuple

# Les genres de bloc. Fermés : un genre inconnu n'existe pas.
TITRE1 = 'titre1'
TITRE2 = 'titre2'
TITRE3 = 'titre3'
SECTION = 'section'        # « §4 — COMPARAISON… », la forme que le prompt impose
PARAGRAPHE = 'paragraphe'
PUCE = 'puce'
CITATION = 'citation'
REGLE = 'regle'
TABLEAU = 'tableau'

GENRES = (TITRE1, TITRE2, TITRE3, SECTION, PARAGRAPHE, PUCE, CITATION,
          REGLE, TABLEAU)


class Bloc(NamedTuple):
    """Un bloc de la narration : son genre et son texte, sans marqueur."""
    genre: str
    texte: str


class Segment(NamedTuple):
    """Un passage d'un bloc, avec son emphase. Le Word en fait des « runs »."""
    texte: str
    gras: bool
    italique: bool


# ⚠️ LE NUMÉRO DE SECTION EST CONSERVÉ : le prompt impose la forme
# « §N — TITRE », et le lecteur s'y repère. Seuls les marqueurs
# Markdown sont retirés, jamais le texte voulu par le prompt.
_SECTION = re.compile(r'^\s*(§\s*\d+\s*[—\-–]\s*.+)$')
_TITRE3 = re.compile(r'^\s*###\s+(.+?)\s*#*\s*$')
_TITRE2 = re.compile(r'^\s*##\s+(.+?)\s*#*\s*$')
_TITRE1 = re.compile(r'^\s*#\s+(.+?)\s*#*\s*$')
_PUCE = re.compile(r'^\s*[-*•]\s+(.+)$')
_CITATION = re.compile(r'^\s*>\s?(.*)$')
_REGLE = re.compile(r'^\s*(?:-{3,}|_{3,}|\*{3,})\s*$')
_TABLEAU = re.compile(r'^\s*\|.*\|\s*$')
_SEPARATRICE = re.compile(r'^\s*\|?[\s:|-]{5,}\|?\s*$')   # |---|---| d'un tableau
_CLOTURE = re.compile(r'^\s*```')



def analyser(markdown: Any) -> Tuple[Bloc, ...]:
    """Découpe la narration en blocs, marqueurs retirés.

    ⚠️ LES CLÔTURES DE CODE SONT ÉCARTÉES, PAS RENDUES. Le prompt interdit les
    blocs de code ; s'il en arrive un, ses ``` ne doivent pas se lire dans un
    rapport signé.
    """
    blocs: List[Bloc] = []
    for ligne in str(markdown or '').split('\n'):
        if _CLOTURE.match(ligne):
            continue
        if not ligne.strip():
            continue
        for motif, genre in ((_REGLE, REGLE), (_SECTION, SECTION),
                             (_TITRE3, TITRE3), (_TITRE2, TITRE2),
                             (_TITRE1, TITRE1), (_PUCE, PUCE),
                             (_CITATION, CITATION)):
            m = motif.match(ligne)
            if m:
                if genre == REGLE:
                    blocs.append(Bloc(REGLE, ''))
                else:
                    texte = m.group(1).strip()
                    if texte or genre == CITATION:
                        blocs.append(Bloc(genre, texte))
                break
        else:
            if _TABLEAU.match(ligne):
                # ⚠️ La ligne SÉPARATRICE d'un tableau markdown (|---|---|)
                # n'a aucun contenu : la rendre afficherait des tirets nus.
                if not _SEPARATRICE.match(ligne):
                    cellules = [c.strip() for c in ligne.strip().strip('|').split('|')]
                    blocs.append(Bloc(TABLEAU, ' · '.join(c for c in cellules if c)))
            else:
                blocs.append(Bloc(PARAGRAPHE, ligne.strip()))
    return tuple(blocs)


def segments(texte: str) -> Tuple[Segment, ...]:
    """Découpe un texte en passages selon **gras** et *italique*.

    C'est ce que le Word consomme : un `.docx` n'a pas de balises, il a des
    passages qui portent chacun leur graisse.
    """
    morceaux: List[Segment] = []
    reste = str(texte or '')
    motif = re.compile(r'\*\*(.+?)\*\*|(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')
    position = 0
    for m in motif.finditer(reste):
        if m.start() > position:
            morceaux.append(Segment(reste[position:m.start()], False, False))
        if m.group(1) is not None:
            morceaux.append(Segment(m.group(1), True, False))
        else:
            morceaux.append(Segment(m.group(2), False, True))
        position = m.end()
    if position < len(reste):
        morceaux.append(Segment(reste[position:], False, False))
    return tuple(morceaux) or (Segment(reste, False, False),)


def _echapper(texte: str) -> str:
    """⚠️ LE TEXTE VIENT D'UN MODÈLE : il ne doit pas pouvoir injecter de
    balise dans un rapport signé."""
    return (str(texte).replace('&', '&amp;')
            .replace('<', '&lt;').replace('>', '&gt;'))


def _inline_html(texte: str) -> str:
    return ''.join(
        f'<strong>{_echapper(s.texte)}</strong>' if s.gras else
        f'<em>{_echapper(s.texte)}</em>' if s.italique else
        _echapper(s.texte)
        for s in segments(texte))


def en_html(markdown: Any, classe_section: str = 's-head') -> str:
    """Le HTML de la narration. ⚠️ BIEN FORMÉ — les listes se ferment.

    L'ancienne conversion enveloppait les `<li>` dans un `<ul>` par une
    substitution de regex, puis passait chaque LIGNE au découpeur de
    paragraphes : la balise `</ul>` se retrouvait à l'intérieur d'un `<p>`.
    Le HTML produit était malformé. Ici la liste est ouverte et fermée par le
    parcours lui-même, elle ne peut pas fuir.
    """
    sortie: List[str] = []
    liste_ouverte = False

    def fermer():
        nonlocal liste_ouverte
        if liste_ouverte:
            sortie.append('</ul>')
            liste_ouverte = False

    for bloc in analyser(markdown):
        if bloc.genre == PUCE:
            if not liste_ouverte:
                sortie.append('<ul>')
                liste_ouverte = True
            sortie.append(f'<li>{_inline_html(bloc.texte)}</li>')
            continue
        fermer()
        contenu = _inline_html(bloc.texte)
        if bloc.genre == SECTION:
            sortie.append(f'<h3 class="{classe_section}">{contenu}</h3>')
        elif bloc.genre == TITRE1:
            sortie.append(f'<h3 class="{classe_section}">{contenu}</h3>')
        elif bloc.genre == TITRE2:
            sortie.append(f'<h4>{contenu}</h4>')
        elif bloc.genre == TITRE3:
            sortie.append(f'<h5>{contenu}</h5>')
        elif bloc.genre == CITATION:
            sortie.append(f'<blockquote>{contenu}</blockquote>')
        elif bloc.genre == REGLE:
            sortie.append('<hr>')
        elif bloc.genre == TABLEAU:
            sortie.append(f'<p class="md-tableau">{contenu}</p>')
        else:
            sortie.append(f'<p>{contenu}</p>')
    fermer()
    return '\n'.join(sortie)


# ── La consigne posée au modèle, en un seul endroit ─────────────────────────
#
# ⚠️ ELLE INTERDISAIT TOUT, ET C'ÉTAIT TROP. Mesuré sur le rapport du 09/08 :
# la conversion marchait parfaitement — ZÉRO marqueur brut sur 13 748
# caractères — mais le commentaire n'était plus qu'un mur de prose. 36
# paragraphes, AUCUN sous-titre, AUCUNE liste, AUCUN terme mis en valeur, là
# où le rapport de provisionnement offre des paliers de lecture. Interdire
# les marqueurs a supprimé le défaut ET la texture avec.
#
# ⚠️ TROIS MARQUEURS SONT DONC ROUVERTS, ET TROIS SEULEMENT — CEUX QUE LA
# CHAÎNE SAIT TRAITER DE BOUT EN BOUT. La règle n'est pas « ce que la
# conversion reconnaît » mais « ce que la conversion reconnaît ET que les
# deux formats RENDENT VISIBLEMENT ». Relevé :
#
#   marqueur   genre     HTML            stylé ?   Word
#   « ## »     TITRE2    <h4>            OUI       gras 10 pt navy
#   « - »      PUCE      <ul><li>        OUI       « • » + retrait
#   « **x** »  segment   <strong>        OUI       gras
#   ─────────────────────────────────────────────────────────────────────
#   « ### »    TITRE3    <h5>            NON       gras 9 pt   → REFUSÉ
#   « > »      CITATION  <blockquote>    NON       guillemets  → REFUSÉ
#   « --- »    REGLE     <hr>            NON       séparateur  → REFUSÉ
#   « | »      TABLEAU   <p.md-tableau>  NON       paragraphe  → REFUSÉ
#
# ⚠️ UN MARQUEUR AUTORISÉ MAIS NON RENDU RAMÈNERAIT LE DÉFAUT DE DÉPART :
# un « ### » sortirait converti en `<h5>` qu'aucune règle ne distingue d'un
# paragraphe — le lecteur verrait un titre qui n'en a pas l'air. Les trois
# retenus sont ceux dont le rendu se voit dans les DEUX formats. Un test
# vérifie cette correspondance dans les deux sens : rien d'autorisé qui ne
# soit rendu, rien d'interdit qui soit rendu.
#
# ⚠️ ET LA CONVERSION RESTE LA CEINTURE. Elle continue de traiter les neuf
# formes : si le modèle glisse un « > » malgré la consigne, il ne se lira
# pas en clair dans le rapport. Une consigne se relâche, une conversion non.

#: Les marqueurs autorisés — libellé de la consigne et exemple.
MARQUEURS_AUTORISES = (
    ('##', 'un sous-titre à l\'intérieur d\'une section'),
    ('-', 'une puce, en tête de ligne'),
    ('**', 'un terme mis en valeur, entre doubles astérisques'),
)

#: Ceux qui restent interdits, et ils le sont pour une raison mesurée.
MARQUEURS_INTERDITS = ('#', '###', '*', '>', '---', '|', '```')

def _phrase_consigne() -> str:
    """La consigne, CONSTRUITE à partir des deux tables ci-dessus.

    ⚠️ ELLE ÉTAIT ÉCRITE À LA MAIN, ET LES TABLES À CÔTÉ. Deux listes du même
    fait finissent par diverger — c'est le motif que ce chantier a fermé six
    fois. La consigne les LIT : autoriser un marqueur sans le dire au modèle,
    ou lui interdire quelque chose que la table autorise, devient impossible
    par construction plutôt que rattrapé par un test.
    """
    permis = ' ; '.join('« %s » pour %s' % (m, quoi)
                        for m, quoi in MARQUEURS_AUTORISES)
    bannis = ', '.join('« %s »' % m for m in MARQUEURS_INTERDITS)
    return (
        "FORMAT DU TEXTE RENDU : tu disposes de %d marqueurs, et de %d "
        "seulement. %s. Emploie-les pour aérer la lecture — un sous-titre par "
        "idée, une liste quand tu énumères, le gras sur les grandeurs et les "
        "verdicts. TOUT AUTRE MARQUEUR EST INTERDIT, et notamment %s. Les "
        "sections restent « §N — TITRE » comme demandé ci-dessous. Ce texte "
        "part dans un rapport signé : un marqueur non prévu s'y lirait tel "
        "quel." % (len(MARQUEURS_AUTORISES), len(MARQUEURS_AUTORISES),
                   permis, bannis))


CONSIGNE_MARKDOWN_RESTREINT = _phrase_consigne()

