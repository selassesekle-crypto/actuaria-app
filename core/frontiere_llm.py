# -*- coding: utf-8 -*-
"""C1 — la frontière unique par laquelle une donnée sort vers l'API.

⚠️ POURQUOI CE MODULE EXISTE. Treize sites du dépôt instanciaient chacun leur
propre client `anthropic`, répartis sur les quatre directions. Une politique de
confidentialité réimplémentée à treize endroits ne se garantit pas : il suffit
qu'un site diverge pour que l'affirmation faite au client — et au régulateur —
soit fausse. Ce module est le SEUL point par lequel une donnée sort, et
`test_frontiere_llm.py` interdit qu'il en existe un autre.

⚠️ CE LOT NE CHANGE AUCUN COMPORTEMENT. Les mêmes données partent, aux mêmes
endroits, avec les mêmes modèles, les mêmes plafonds de jetons et les mêmes
exceptions. Le caviardage (C2) et l'anonymisation (C3) se brancheront ici —
en un seul endroit, vérifiable par un seul test.

CE QUE CE MODULE NE FAIT PAS. Il ne parse pas, ne juge pas, ne se substitue à
aucune validation. Il possède la SORTIE, pas la lecture de la réponse : les
deux formes d'extraction rencontrées dans le dépôt sont nommées ci-dessous et
rendues telles quelles, parce qu'elles diffèrent et que ce lot ne les unifie
pas.
"""
import os
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple

# =============================================================================
#  LES IDENTIFIANTS DE MODÈLE — SOURCE UNIQUE
# =============================================================================
# ⚠️ SOURCE UNIQUE N'EST PAS VALEUR UNIQUE, ET C'EST DÉLIBÉRÉ. Deux
# identifiants coexistent dans le dépôt. Les unifier déplacerait dix sites d'un
# modèle à l'autre : ce serait un changement de comportement, que ce lot
# s'interdit. Ils sont donc NOMMÉS ici, une fois, avec leur relevé — et les
# unifier devient une ligne dans un seul fichier, mesurable séparément.
#
# ⚠️ ET LA COUPURE N'EST PAS CE QU'ON CROIT. Ce n'est pas « narration contre
# correspondance » : `rapport_modeles_tarif` est une narration et utilise le
# modèle récent. C'est une DÉRIVE CHRONOLOGIQUE — les trois modules écrits en
# dernier portent l'un, les dix autres portent l'autre. Aucune décision
# actuarielle ne s'y attache, exactement comme pour les σ et les taux.

MODELE_RECENT = 'claude-sonnet-5'
MODELE_ETABLI = 'claude-sonnet-4-6'

MODELES_CONNUS = (MODELE_RECENT, MODELE_ETABLI)

# ⚠️ NOMMÉS ICI PARCE QUE C'EST ICI QU'ON LE SAIT. Ce module est le seul du
# dépôt qui importe `anthropic` pour appeler ; tout autre fichier qui écrirait
# ce nom le recopierait. Les deux registres art. 30 (C5) les lisent d'ici.
FOURNISSEUR = 'Anthropic'
SERVICE = "API Claude (messages), appelée depuis le poste où tourne le logiciel"


class Site(NamedTuple):
    """Un appelant de la frontière, et le modèle qu'il porte aujourd'hui."""
    chemin: str
    modele: str
    usage: str


# Le relevé, parti du code et non d'une liste : treize sites, trois sources
# d'identifiant avant ce lot (neuf littéraux, `_MODELE_CLAUDE` ×2,
# `CLAUDE_MODEL_TARIF` ×1).
SITES: Tuple[Site, ...] = (
    Site('core/mapping_llm.py', MODELE_RECENT, 'correspondance de colonnes'),
    Site('direction_non_vie/services/nv_triangle_mapping_llm.py',
         MODELE_RECENT, 'correspondance de colonnes'),
    Site('direction_non_vie/tarification/services/rapport_modeles_tarif.py',
         MODELE_RECENT, 'narration'),
    Site('actuaria_app.py', MODELE_ETABLI, 'conversation'),
    Site('core/managers_directeurs.py', MODELE_ETABLI, 'conversation'),
    Site('direction_non_vie/provisionnement/a7_provisionnement/n5_rapport.py',
         MODELE_ETABLI, 'narration'),
    Site('direction_vie_epre/services/rapport_vie.py',
         MODELE_ETABLI, 'narration'),
    Site('direction_vie_epre/services/rapport_rvie2.py',
         MODELE_ETABLI, 'narration'),
    Site('direction_vie_epre/services/rapport_epre.py',
         MODELE_ETABLI, 'narration'),
    Site('direction_sante_prevoyance/services/sp_rapport_sante.py',
         MODELE_ETABLI, 'narration'),
    Site('direction_sante_prevoyance/services/sp_rapport_prevoyance.py',
         MODELE_ETABLI, 'narration'),
    Site('direction_sante_prevoyance/sante/rapport_sante/agent.py',
         MODELE_ETABLI, 'narration'),
    Site('direction_sante_prevoyance/prevoyance/rapport_prevoyance/agent.py',
         MODELE_ETABLI, 'narration'),
)

VARIABLE_CLE = 'ANTHROPIC_API_KEY'

# =============================================================================
#  LES PARAMÈTRES QU'UN MODÈLE REFUSE
# =============================================================================
# ⚠️ MESURÉ CONTRE L'API le 2026-08-07, avec la clé et le paquet :
#
#     anthropic.BadRequestError: Error code: 400
#     '`temperature` is deprecated for this model.'
#
# ⚠️ LE PARAMÈTRE EST DÉPRÉCIÉ POUR CE MODÈLE, QUELLE QUE SOIT SA VALEUR — ce
# n'est pas « une valeur non-défaut est refusée ». Trois sites du dépôt
# associaient les deux, et leurs appels étaient donc TOUS rejetés.
#
# La provenance vit dans la donnée, comme pour les paramètres de la formule
# standard : une entrée sans mesure n'a rien à faire ici.
PARAMETRES_REFUSES: Dict[str, Tuple[str, ...]] = {
    MODELE_RECENT: ('temperature',),
}


class FrontiereLLMIndisponible(RuntimeError):
    """Aucun texte exploitable n'a pu être obtenu. Famille, et cas de base.

    ⚠️ TROIS CAUSES DISTINCTES, ET LES CONFONDRE COÛTE CHER. Levée
    DIRECTEMENT, elle signifie « l'ENVIRONNEMENT n'a pas ce qu'il faut » :
    paquet absent, clé absente. Ses deux filles nomment les deux autres
    causes — `RequeteRefusee` (la requête est fautive) et
    `ReponseInexploitable` (le service a répondu, sa réponse ne sert à rien).

    ⚠️ N'EST PAS LEVÉE POUR UNE DÉFAILLANCE DU TRANSPORT. Les erreurs du
    client `anthropic` (authentification, quota, réseau, HTTP) remontent
    INCHANGÉES, parce que plusieurs appelants les distinguent par leur type et
    que les envelopper changerait leur comportement.
    """


class RequeteRefusee(FrontiereLLMIndisponible):
    """La requête est FAUTIVE — un défaut du dépôt, pas une dégradation.

    ⚠️ C'EST LA DISTINCTION QUI MANQUAIT, ET QUI A PERMIS LE SILENCE. Un repli
    parce que le paquet manque est une dégradation ATTENDUE : l'environnement
    n'a pas ce qu'il faut, le repli local est la bonne réponse. Un repli parce
    que la requête est REFUSÉE est un DÉFAUT : la plateforme envoie une requête
    qu'elle n'aurait jamais dû construire. Les deux tombaient dans le même
    `except Exception` et produisaient le même repli muet.

    Hérite de FrontiereLLMIndisponible pour que tout appelant qui capturait
    déjà celle-ci continue de capturer celle-ci — la distinction s'ajoute,
    elle ne casse personne.
    """


class ReponseInexploitable(FrontiereLLMIndisponible):
    """Le service a RÉPONDU, et sa réponse ne porte aucun texte utilisable.

    ⚠️ CE N'EST NI L'UN NI L'AUTRE, ET SURTOUT PAS << API INDISPONIBLE >>.
    L'API était disponible : elle a répondu 200. Dire le contraire envoie
    chercher la panne au mauvais endroit — c'est ce qui est arrivé, et le
    dépôt en porte déjà la trace : le commentaire d'en-tête de `n5_rapport.py`
    raconte le MÊME motif, un défaut de code journalisé comme une panne d'API.

    Hérite de FrontiereLLMIndisponible : la distinction s'ajoute sans casser
    les appelants qui capturaient déjà la famille.
    """


def cle_api(explicite: Optional[str] = None) -> str:
    """Rend la clé, ou lève. Ordre : valeur explicite, puis l'environnement.

    ⚠️ LES SECRETS STREAMLIT NE SONT PAS LUS ICI. Deux appelants les lisent,
    dans deux ordres opposés ; ils continuent de le faire eux-mêmes et passent
    le résultat par `explicite`. Résoudre à leur place imposerait un ordre à
    l'autre, et un ordre imposé est un changement de comportement.
    """
    cle = explicite or os.environ.get(VARIABLE_CLE) or ''
    if not cle:
        raise FrontiereLLMIndisponible(f'{VARIABLE_CLE} non définie')
    return cle


def cle_api_ou_secrets() -> str:
    """Environnement, PUIS secrets Streamlit — l'ordre de neuf appelants.

    ⚠️ L'ORDRE INVERSE EXISTE AUSSI DANS LE DÉPÔT : un appelant lit les
    secrets d'abord. Il n'est pas rapatrié ici — lui imposer cet ordre-ci
    changerait son comportement le jour où les deux sources divergent. Il
    résout donc lui-même et passe le résultat par `cle`.
    """
    cle = os.environ.get(VARIABLE_CLE) or ''
    if not cle:
        try:
            import streamlit as st
            cle = st.secrets.get(VARIABLE_CLE) or ''
        except Exception:
            cle = ''
    if not cle:
        raise FrontiereLLMIndisponible(f'{VARIABLE_CLE} non définie')
    return cle


def appeler(*, modele: str, systeme: str,
            messages: Sequence[Dict[str, Any]], max_tokens: int,
            temperature: Optional[float] = None,
            cle: Optional[str] = None) -> Any:
    """LE SEUL APPEL SORTANT DU DÉPÔT. Rend la réponse BRUTE du modèle.

    `temperature` n'est transmise que si elle est fournie : les onze sites qui
    n'en passaient pas envoient exactement la même requête qu'avant.
    """
    if modele not in MODELES_CONNUS:
        raise FrontiereLLMIndisponible(
            f'modèle « {modele} » inconnu de la frontière ; '
            f'connus : {", ".join(MODELES_CONNUS)}')
    # ⚠️ REFUS EN AMONT, AVANT LE RÉSEAU. Laisser partir une requête vouée au
    # 400 coûte un aller-retour et rend une erreur opaque, loin de sa cause.
    # Et `temperature` reste un paramètre PUBLIC de deux modules : retirer sa
    # valeur par défaut n'empêche pas un appelant d'en passer une. Ce contrôle
    # est le seul endroit qui puisse l'attraper — et il est testable, ce que le
    # 400 n'est pas (aucune clé en vérification).
    if temperature is not None and 'temperature' in PARAMETRES_REFUSES.get(
            modele, ()):
        raise RequeteRefusee(
            f'le modèle « {modele} » refuse le paramètre « temperature » '
            f'(déprécié pour ce modèle, mesuré le 2026-08-07) ; '
            f'ne pas le transmettre')
    try:
        import anthropic
    except Exception as e:          # paquet absent : dégradation propre
        raise FrontiereLLMIndisponible(
            f"paquet 'anthropic' indisponible ({e})") from e

    client = anthropic.Anthropic(api_key=cle_api(cle))
    parametres: Dict[str, Any] = {
        'model': modele, 'max_tokens': max_tokens,
        'system': systeme, 'messages': list(messages),
    }
    if temperature is not None:
        parametres['temperature'] = temperature
    return client.messages.create(**parametres)


# =============================================================================
#  LA LECTURE DE LA RÉPONSE — UNE SEULE FORME
# =============================================================================
# ⚠️⚠️ IL Y EN AVAIT DEUX, ET LA DIVERGENCE ÉTAIT UNE PANNE EN ATTENTE. Onze
# sites lisaient `reponse.content[0].text` ; deux concaténaient les blocs de
# texte. Sur une réponse à un seul bloc de texte, identique. Sur une réponse
# dont le PREMIER bloc n'est pas du texte — un bloc de raisonnement porte
# `.thinking`, pas `.text` — la première lève `AttributeError`.
#
# MESURÉ À L'USAGE : six appels ont abouti en 200 OK et leurs six réponses ont
# été JETÉES, le rapport repliant sur le commentaire d'agent. J'avais documenté
# cet écart en C1 en le classant « amélioration, donc changement de
# comportement ». C'était un mauvais classement : c'était une panne en attente.

def texte_des_blocs(reponse: Any) -> str:
    """Le texte de la réponse : tous les blocs « text », concaténés.

    ⚠️ LÈVE PLUTÔT QUE DE RENDRE UNE CHAÎNE VIDE. Sans cela on échangerait une
    panne muette contre une autre : une narration VIDE étiquetée « venue de
    l'API », qu'aucun appelant ne distinguerait d'une narration réussie.

    Le message nomme les TYPES de blocs reçus — jamais leur contenu : c'est ce
    qui permet de diagnostiquer sans rien divulguer.
    """
    blocs = list(getattr(reponse, 'content', None) or ())
    texte = ''.join(b.text for b in blocs
                    if getattr(b, 'type', None) == 'text')
    if not texte.strip():
        types = [str(getattr(b, 'type', '?')) for b in blocs] or ['aucun bloc']
        raise ReponseInexploitable(
            f'le service a répondu, mais sa réponse ne porte aucun texte '
            f'exploitable — {len(blocs)} bloc(s) reçu(s) : {", ".join(types)}')
    return texte


#: Le motif d'arrêt qui signale une réponse COUPÉE par la limite de jetons.
MOTIF_TRONQUEE = 'max_tokens'

#: ⚠️⚠️ LA MENTION VIT ICI, ET PAS DANS CHAQUE RAPPORT. Elle est née dans A7 ;
#: la recopier dans les trois autres chaînes qui publient une narration en
#: aurait fait QUATRE copies — et quatre copies divergent au premier
#: ajustement. C'est ce qui était arrivé aux deux tables de libellés avant
#: qu'on les fonde en une.
#:
#: ⚠️ ELLE DIT QUE LE TEXTE EST INCOMPLET — le seul fait qu'on connaisse.
#: Elle n'affirme PAS ce qui manque : personne ne le sait. Et elle ne dit pas
#: que ce qui précède est faux — il ne l'est pas, il est SEULEMENT interrompu.
PORTEE_NARRATION_TRONQUEE = (
    "⚠️ NARRATION INTERROMPUE — le modèle a atteint sa limite de longueur et "
    "le texte ci-dessus s'arrête avant sa fin. Ce qui précède n'est pas "
    "invalidé : il est INCOMPLET. Les sections manquantes sont absentes, "
    "non erronées — et personne ne peut dire ce qu'elles auraient contenu.")


def texte_ou_mention_troncature(reponse: Any) -> str:
    """Le texte de la réponse, suivi de sa mention SI elle a été coupée.

    ⚠️⚠️ LE GESTE EST LE MÊME POUR LES QUATRE CHAÎNES QUI PUBLIENT UNE
    NARRATION. Mesuré : `texte_des_blocs` a HUIT appelants, mais tous ne
    publient pas de la même façon —
      · QUATRE publient une narration dans un document signé (A7,
        tarification, santé, prévoyance) : une troncature y est SILENCIEUSE ;
      · DEUX parsent le texte en JSON : `json.loads` lève, le défaut est déjà
        bruyant ;
      · DEUX alimentent une conversation : l'utilisateur VOIT le texte coupé.
    Seuls les quatre premiers ont besoin de ceci — et le leur donner ici
    évite d'écrire quatre fois le même `if`.

    ⚠️ ON MARQUE, ON NE LÈVE PAS : le texte déjà produit reste utile — sur le
    cas mesuré, 40 % de la narration était écrite. Faire tomber le rapport
    reproduirait ce que le lot A a fermé.
    """
    texte = texte_des_blocs(reponse)
    if est_tronquee(reponse):
        return texte.rstrip() + '\n\n' + PORTEE_NARRATION_TRONQUEE
    return texte


def motif_arret(reponse: Any) -> str:
    """Pourquoi le modèle s'est arrêté. `''` si la réponse ne le dit pas."""
    return str(getattr(reponse, 'stop_reason', '') or '')


def est_tronquee(reponse: Any) -> bool:
    """La réponse a-t-elle été COUPÉE par la limite de jetons ?

    ⚠️⚠️ CE MODULE FERMAIT DÉJÀ LE CAS VOISIN, ET À MOITIÉ SEULEMENT.
    `texte_des_blocs` lève sur une réponse VIDE, en écrivant pourquoi : « on
    échangerait une panne muette contre une autre — une narration vide
    étiquetée "venue de l'API", qu'aucun appelant ne distinguerait d'une
    narration réussie ». LE MÊME RAISONNEMENT VAUT MOT POUR MOT POUR UNE
    RÉPONSE COUPÉE, et il n'avait pas été appliqué : un texte qui s'arrête
    en pleine phrase est, lui aussi, indiscernable d'un texte abouti.

    ⚠️ L'INFORMATION EXISTAIT ET PERSONNE NE LA LISAIT. Mesure du 21/08 :
    `stop_reason` n'apparaissait NULLE PART dans le dépôt — la réponse était
    jetée une ligne après son arrivée, par `texte_des_blocs`.

    ⚠️ ET AUCUN AUTRE CONTRÔLE NE PEUT LE VOIR. Le verrou C2 mesure la
    PROVENANCE des nombres, jamais la COMPLÉTUDE du texte : mesuré, une
    narration coupée à 420 caractères affichait « 0,0 % d'orphelins » — un
    taux qui se lit comme une qualité alors qu'il ne dit qu'une absence.

    ⚠️ CETTE FONCTION MESURE, ELLE NE SANCTIONNE PAS. Lever ici ferait
    tomber les HUIT chaînes qui appellent `texte_des_blocs` — c'est ce que
    le lot A a fermé, un renderer qui plante sur un garde-fou bien posé.
    C'est à chaque publieur de décider ce qu'il en fait.
    """
    return motif_arret(reponse) == MOTIF_TRONQUEE


def sites_du_modele(modele: str) -> Tuple[Site, ...]:
    """Les sites qui portent ce modèle. Lève si le modèle est inconnu."""
    if modele not in MODELES_CONNUS:
        raise KeyError(modele)
    return tuple(s for s in SITES if s.modele == modele)


def chemins_appelants() -> List[str]:
    """Les chemins des treize sites, tels que le verrou doit les retrouver."""
    return [s.chemin for s in SITES]
