"""
=============================================================================
  ActuarIA — LA DÉCISION DE L'ACTUAIRE FACE AU VERDICT DU SYSTÈME
=============================================================================

CE N'EST JAMAIS L'ACCORD QU'IL FAUT ENREGISTRER, C'EST LE DÉSACCORD.

⚠️⚠️ POURQUOI CE MODULE EXISTE — arbitrage du 08/09/2026, après deux audits
indépendants qui l'ont demandé séparément. Le dépôt produit un verdict
(`statut_rag` : VERT, AMBRE, ROUGE), publie des réserves d'arbitrage, et fait
signer un actuaire nommé. **Il n'enregistrait nulle part ce que cet actuaire a
DÉCIDÉ de ce verdict.** Mesuré le 08/09/2026 : `fiche_decision` est une *aide*
— « questions à poser avant signature » —, et la seule décision humaine tracée
est `profil_valide_par`, qui valide un profil de pondération, pas un tarif.

  *Un journal où l'actuaire suit toujours la recommandation ne prouve rien.
  Ce qu'un contrôleur cherche, c'est la fois où il ne l'a pas suivie.*

CE QUE LE MODULE REFUSE
  Un **désaccord sans motif**. Passer outre un AMBRE ou un ROUGE est une
  décision légitime — c'est l'actuaire qui signe, pas le système. Mais elle
  engage, et une décision qui engage sans dire pourquoi n'est pas opposable.
  À l'inverse, un ACCORD n'exige aucun motif : suivre le verdict n'a pas à se
  justifier.

⚠️ ET L'ABSENCE DE DÉCISION N'EST PAS UN ACCORD. Sans décision enregistrée,
le document écrit « aucune décision d'actuaire enregistrée » — jamais
« l'actuaire a suivi ». *C'est le défaut `… else "VERT"` que ce chantier a
déjà trouvé cinq fois : un statut par défaut qui certifie ce qu'il n'a pas
regardé.*

⚠️ LE PATRON EST CELUI DE `QualiteBloquante` : l'échappatoire d'un blocage
n'est jamais un `try/except`, c'est un **champ nominatif**. Ici, l'échappatoire
d'un verdict défavorable n'est pas de l'ignorer : c'est de le passer outre,
nommément et avec un motif.
=============================================================================
"""

from __future__ import annotations

import dataclasses

from core.charts_tarif import STATUT_RAG

__all__ = [
    'ACCORD', 'DECISIONS_ADMISES', 'PASSE_OUTRE', 'REFUS',
    'STATUTS_ADMIS', 'DecisionActuaire', 'decision_depuis_dict',
    'divergence', 'synthese_decision',
]

#: ⚠️ DÉRIVÉ DE LA SOURCE UNIQUE, JAMAIS RECOPIÉ. Le dépôt a déjà payé sept
#: valeurs distinctes de VERT/AMBRE/ROUGE dans sept fichiers, sans source —
#: `core.charts_tarif.STATUT_RAG` est la table qui a fermé ce défaut. Une
#: huitième liste ici divergerait au premier statut ajouté.
#:
#: ⚠️⚠️ ET LA DÉRIVATION SE VÉRIFIE : `STATUT_RAG` est indexé par FOND
#: (`sombre`, `clair`), pas par statut. Ma première écriture prenait ses clés
#: EXTÉRIEURES et rendait `('clair', 'sombre')` — une liste de statuts qui
#: n'en contenait aucun. *Dériver d'une table ne dispense pas de regarder sa
#: forme ; ça déplace seulement l'endroit où l'on peut se tromper.*
#:
#: L'INTERSECTION des deux palettes, et pas les clés de l'une d'elles : si un
#: statut n'existait que sur un fond, prendre le premier venu l'accepterait en
#: silence. Ici, une divergence entre les deux palettes rétrécit la liste et
#: se voit.
STATUTS_ADMIS = tuple(sorted(
    set.intersection(*(set(table) for table in STATUT_RAG.values()))))

#: Les trois décisions qu'un actuaire peut prendre face à un verdict.
#: ⚠️ `ACCORD` n'est pas « ne rien faire » : c'est une décision, prise et
#: datée. Ce qui n'est pas une décision, c'est l'ABSENCE de décision — et le
#: module la distingue par `None`, jamais par un accord implicite.
ACCORD = 'ACCORD'            # l'actuaire suit le verdict
PASSE_OUTRE = 'PASSE_OUTRE'  # il signe malgré un AMBRE ou un ROUGE
REFUS = 'REFUS'              # il refuse malgré un VERT
DECISIONS_ADMISES = (ACCORD, PASSE_OUTRE, REFUS)


@dataclasses.dataclass(frozen=True)
class DecisionActuaire:
    """Ce que l'actuaire a décidé du verdict, et pourquoi s'il en diverge.

    ⚠️⚠️ `motif` EST OBLIGATOIRE DÈS QU'IL Y A DIVERGENCE, et facultatif
    sinon. C'est toute la doctrine du module : suivre n'a pas à se justifier,
    passer outre si.

    ⚠️ `decide_par` PORTE UN NOM, ici, et c'est voulu — contrairement aux
    `declare_par` des chargements, qui portent un RÔLE parce qu'ils vivent
    dans un YAML versionné publiquement. Cette décision-ci n'est jamais
    versionnée : elle arrive au moment du run et va dans un document remis au
    client, où le signataire doit être identifiable. *La règle n'est pas
    « jamais de nom » : elle est « jamais de nom dans le dépôt ».*
    """
    verdict_systeme: str
    decision: str
    decide_par: str
    decide_le: str              # 'AAAA-MM-JJ'
    motif: str = ''

    def __post_init__(self):
        if self.verdict_systeme not in STATUTS_ADMIS:
            raise ValueError(
                f"decision_actuaire : verdict '{self.verdict_systeme}' "
                f"inconnu — attendu l'un de {', '.join(STATUTS_ADMIS)}. Le "
                f"vocabulaire vient de `core.charts_tarif.STATUT_RAG`, source "
                f"unique du dépôt.")
        if self.decision not in DECISIONS_ADMISES:
            raise ValueError(
                f"decision_actuaire : decision '{self.decision}' inconnue — "
                f"attendu l'une de {', '.join(DECISIONS_ADMISES)}.")
        for champ in ('decide_par', 'decide_le'):
            if not str(getattr(self, champ) or '').strip():
                raise ValueError(
                    f"decision_actuaire : `{champ}` est obligatoire. Une "
                    f"décision que personne ne signe et qu'aucune date ne "
                    f"situe n'est pas opposable.")
        # ⚠️⚠️ LE CŒUR DU MODULE. Un désaccord sans motif est refusé ; un
        # accord n'en demande aucun. *Exiger un motif partout reviendrait à
        # faire écrire « RAS » mille fois, et le jour où il compte vraiment
        # personne ne le lirait.*
        if divergence(self) and not str(self.motif or '').strip():
            raise ValueError(
                f"decision_actuaire : `{self.decision}` sur un verdict "
                f"'{self.verdict_systeme}' est un DESACCORD avec le systeme, "
                f"et il EXIGE un motif. Passer outre est une decision "
                f"legitime -- c'est l'actuaire qui signe -- mais elle engage, "
                f"et une decision qui engage sans dire pourquoi n'est pas "
                f"opposable devant un controleur.")


def divergence(decision: DecisionActuaire | None) -> bool:
    """L'actuaire s'écarte-t-il du verdict du système ?

    ⚠️⚠️ ``False`` POUR UNE ABSENCE DE DÉCISION, ET CE N'EST PAS UN ACCORD.
    L'appelant doit distinguer les deux : `None` veut dire « rien n'a été
    enregistré », pas « l'actuaire a suivi ». :func:`synthese_decision` les
    sépare explicitement ; cette fonction-ci ne répond qu'à la question du
    désaccord.
    """
    if decision is None:
        return False
    return decision.decision in (PASSE_OUTRE, REFUS)


def decision_depuis_dict(d) -> DecisionActuaire | None:
    """Construit la décision depuis le contexte du run, ou ``None``.

    ⚠️ ``None`` quand rien n'est fourni : le document dira qu'aucune décision
    n'est enregistrée. Il ne se taira pas, et il n'inventera pas un accord.
    """
    if not d:
        return None
    if isinstance(d, DecisionActuaire):
        return d
    if not isinstance(d, dict):
        raise TypeError(
            f"decision_actuaire : attendu un bloc ou une `DecisionActuaire`, "
            f"reçu {type(d).__name__}.")
    champs = {f.name for f in dataclasses.fields(DecisionActuaire)}
    inconnues = sorted(set(d) - champs)
    if inconnues:
        raise ValueError(
            f"decision_actuaire : clé(s) inconnue(s) {inconnues}. Admis : "
            f"{sorted(champs)}.")
    return DecisionActuaire(**d)


#: Le titre publié. ⚠️ Il nomme le DÉSACCORD, pas la décision : c'est ce que
#: le lecteur d'un document signé cherche.
TITRE_DECISION = ("Decision de l'actuaire signataire, et son ecart eventuel "
                  "avec le verdict du systeme")


def synthese_decision(decision: DecisionActuaire | None,
                      verdict_systeme: str | None = None) -> str:
    """La phrase publiable — source UNIQUE de cette rédaction.

    ⚠️⚠️ TROIS ÉTATS, ET ILS NE SE CONFONDENT PAS : aucune décision
    enregistrée · un accord · un désaccord motivé. Le premier est le plus
    dangereux à mal écrire, parce qu'un document muet se lit comme un accord.
    """
    if decision is None:
        return (
            "AUCUNE DECISION D'ACTUAIRE ENREGISTREE"
            + (f" (verdict du systeme : {verdict_systeme})."
               if verdict_systeme else ".")
            + " Ce document ne dit pas que l'actuaire a suivi le verdict : il "
              "dit que sa decision n'a pas ete enregistree. Les deux ne se "
              "valent pas devant un controleur.")
    tete = (f"Verdict du systeme : {decision.verdict_systeme}. "
            f"Decision de l'actuaire : {decision.decision}, par "
            f"{decision.decide_par} le {decision.decide_le}.")
    if not divergence(decision):
        return tete + " L'actuaire SUIT le verdict du systeme."
    return (
        tete
        + f" /!\\ DESACCORD : l'actuaire s'ECARTE du verdict du systeme. "
          f"Motif declare : << {decision.motif} >>.")
