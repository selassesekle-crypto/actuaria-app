"""
=============================================================================
  ActuarIA — LES CONDITIONS DE MESURE DU CLASSEMENT, DÉCLARÉES
=============================================================================

⚠️⚠️ CE QUE CE MODULE EXISTE POUR RENDRE VISIBLE. A6 range côte à côte les
Gini d'A3, d'A4 et d'A5, et le premier du classement devient le modèle de
PRODUCTION. Or **rien dans le document signé ne disait sur quelle découpe ces
Gini avaient été mesurés**, ni qu'elle n'est **déclarée nulle part**.

MESURE DU 08/09/2026 — POURQUOI ÇA COMPTE
  Les mêmes six candidats, notés sur deux découpes 80/20 des mêmes données :
  recouvrement des holdouts **19,2 % à 22,5 %**, Gini jusqu'à **×3,8**
  (`catboost` 0,1725 contre 0,0459), et **3 à 5 modèles sur 6 changent de
  rang**. *Le vainqueur a tenu sur les deux tirages ; l'ordre en dessous,
  non.* Un lecteur qui ignore la découpe ne peut pas juger ce classement.

⚠️⚠️ DEUX RÉGIMES COEXISTENT, ET UN SEUL EST DÉCLARÉ
  · **α** — A3/A4/A5 : temporelle si une colonne temporelle existe, sinon
    aléatoire graine 42, 80/20. C'est ce régime qui décide du modèle de
    production, et **aucun plan ne le déclare**.
  · **β** — `pipeline_complet.validation` et la comparaison de prix : la
    `decoupe_validation` DU PLAN. Mesuré : **0 des 20 plans en déclare une.**

⚠️ CE LOT NE CHANGE PAS α, IL LE DIT. Le rendre refusable ferait cesser la
sélection de modèle sur 20/20 plans : c'est un arbitrage séparé (`D-3b`), et
il attend une mesure de son effet sur le PRIX. *On publie d'abord ce qui est,
on décide ensuite.*

⚠️⚠️ CHAQUE AGENT DÉCLARE LA SIENNE, LÀ OÙ ELLE A LIEU. Les redériver ailleurs
reviendrait à recopier le mécanisme qu'on surveille — l'avertissement est
écrit dans A4 lui-même, au-dessus de son propre diagnostic. *Un relevé qui
recalcule ce qu'il observe périme avec lui.*

⚠️ ET L'ASSIETTE D'APPRENTISSAGE SE PUBLIE AVEC. A5 réserve une part de
validation pour son arrêt anticipé : mesuré par exécution, il apprend sur
**1 360 lignes quand A3 et A4 en ont 1 600** — 68 % contre 80 %, 12 points.
Leur holdout est pourtant **identique** (400/400 lignes communes). *Le
classement les compare sans que rien ne le dise.* On ne les égalise pas —
égaliser changerait les ajustements d'A3/A4, donc le modèle retenu, pour une
symétrie cosmétique. **On le dit.**
=============================================================================
"""

from __future__ import annotations

import dataclasses

__all__ = [
    'REGLE_ALEATOIRE', 'REGLE_TEMPORELLE', 'ConditionsDeMesure',
    'phrase_conditions_de_mesure',
]

#: ⚠️ Les deux règles que le dépôt applique, et elles viennent d'une SOURCE
#: UNIQUE : `colonne_temporelle()` dans `core`, lue à l'identique par A3, A4,
#: A5 et le diagnostic d'évaluation.
REGLE_TEMPORELLE = 'temporelle'
REGLE_ALEATOIRE = 'aleatoire_graine_42'
REGLES = (REGLE_TEMPORELLE, REGLE_ALEATOIRE)


@dataclasses.dataclass(frozen=True)
class ConditionsDeMesure:
    """Comment CET agent a formé son holdout. Déclaré, jamais redérivé.

    ⚠️ `declaree_au_plan` est un CHAMP, pas une constante : le jour où un plan
    déclarera sa découpe et où les agents la suivront (`D-3b`), la phrase
    publiée changera d'elle-même. *Un booléen figé à `False` aurait menti ce
    jour-là, en silence.*
    """
    agent: str                       # 'A3', 'A4', 'A5'
    regle: str                       # REGLE_TEMPORELLE | REGLE_ALEATOIRE
    n_train: int
    n_test: int
    colonne: str | None = None       # la colonne temporelle, si elle a servi
    #: ⚠️⚠️ LA TROISIÈME PART, ET L'OUBLIER FAUSSE LA MESURE QUE CE MODULE
    #: EXISTE POUR PUBLIER. A5 réserve une part de VALIDATION pour son arrêt
    #: anticipé : elle n'est ni dans le train, ni dans le holdout. Ma première
    #: version divisait par `train + test` seulement, et A5 sortait à
    #: **77,3 %** au lieu de **68 %** — un écart affiché de 2,7 points là où il
    #: en vaut **12**. *Le contrôle qui l'a trouvé, c'est mon propre test :
    #: il attendait le chiffre mesuré par exécution, et le code ne le rendait
    #: pas.* Zéro pour un agent qui n'en réserve pas.
    n_validation: int = 0
    declaree_au_plan: bool = False

    def __post_init__(self):
        if self.regle not in REGLES:
            raise ValueError(
                f"conditions de mesure de {self.agent} : regle "
                f"'{self.regle}' inconnue -- attendu {', '.join(REGLES)}.")
        if self.regle == REGLE_TEMPORELLE and not self.colonne:
            raise ValueError(
                f"conditions de mesure de {self.agent} : une decoupe "
                f"TEMPORELLE sans colonne n'est pas une decoupe temporelle. "
                f"La colonne qui a servi se nomme.")
        if self.regle == REGLE_ALEATOIRE and self.colonne:
            raise ValueError(
                f"conditions de mesure de {self.agent} : une decoupe "
                f"ALEATOIRE ne s'appuie sur aucune colonne, or "
                f"'{self.colonne}' est nommee. L'une des deux est fausse.")
        if self.n_train <= 0 or self.n_test <= 0:
            raise ValueError(
                f"conditions de mesure de {self.agent} : train="
                f"{self.n_train}, test={self.n_test}. Une part vide n'est pas "
                f"une decoupe.")
        if self.n_validation < 0:
            raise ValueError(
                f"conditions de mesure de {self.agent} : une part de "
                f"validation negative ({self.n_validation}) n'existe pas.")

    @property
    def n_total(self) -> int:
        """Le jeu entier — les TROIS parts, jamais deux."""
        return self.n_train + self.n_validation + self.n_test

    @property
    def part_apprentissage(self) -> float:
        """La part du JEU ENTIER sur laquelle CET agent a réellement appris.

        ⚠️ Le dénominateur est `n_total`, validation comprise. La diviser par
        `train + test` ferait passer A5 de 68 % à 77,3 % : *l'asymétrie
        publiée serait quatre fois plus petite que la vraie.*
        """
        return self.n_train / float(self.n_total)

    def resume(self) -> dict:
        """Dict sérialisable — c'est ce qui voyage jusqu'au document."""
        return {'agent': self.agent, 'regle': self.regle,
                'colonne': self.colonne, 'n_train': self.n_train,
                'n_validation': self.n_validation, 'n_test': self.n_test,
                'n_total': self.n_total,
                'part_apprentissage': round(self.part_apprentissage, 4),
                'declaree_au_plan': self.declaree_au_plan}


def phrase_conditions_de_mesure(conditions) -> str:
    """La phrase publiable — source UNIQUE de cette rédaction.

    ⚠️⚠️ ELLE DIT TROIS CHOSES, ET LA TROISIÈME EST CELLE QUI MANQUAIT : sur
    quelle règle le holdout a été formé, sur combien de lignes chaque agent a
    APPRIS, et que cette découpe **n'est pas celle que le plan déclare**.

    ⚠️ Sans condition remontée, elle ne se tait pas : elle dit qu'aucune n'a
    été déclarée. *Un silence se lirait « rien à signaler ».*
    """
    lignes = [c for c in (conditions or []) if c is not None]
    if not lignes:
        return (
            "CONDITIONS DE MESURE DU CLASSEMENT : aucune n'a ete declaree par "
            "les agents. Le classement ci-dessus a ete etabli sur des "
            "decoupes que ce document ne peut pas nommer -- il ne dit donc "
            "pas sur quelles lignes ces scores ont ete mesures.")
    tete = "CONDITIONS DE MESURE DU CLASSEMENT. "
    for c in sorted(lignes, key=lambda x: x.agent):
        ou = (f"decoupe TEMPORELLE sur '{c.colonne}'"
              if c.regle == REGLE_TEMPORELLE
              else "decoupe ALEATOIRE (graine 42), sans colonne temporelle")
        tete += (f"{c.agent} : {ou} -- apprentissage sur {c.n_train} ligne(s) "
                 f"({100 * c.part_apprentissage:.1f} %), mesure sur "
                 f"{c.n_test}. ")
    parts = {round(c.part_apprentissage, 4) for c in lignes}
    if len(parts) > 1:
        detail = ', '.join(
            f"{c.agent} {100 * c.part_apprentissage:.1f} %"
            for c in sorted(lignes, key=lambda x: x.agent))
        tete += (
            f"/!\\ LES ASSIETTES D'APPRENTISSAGE DIFFERENT ({detail}) : les "
            f"scores ranges cote a cote ne viennent pas de modeles ajustes "
            f"sur autant de donnees. Un modele a besoin d'une part de "
            f"validation pour son arret anticipe ; les autres n'en reservent "
            f"pas. ")
    # ⚠️⚠️ UNE DECLARATION A MOITIE FAITE ETEIGNAIT L'ALARME AU LIEU DE LA
    # LEVER — constat `D5`, report du round 4, confirme le 14/09/2026.
    # Le predicat etait `if not any(c.declaree_au_plan for c in lignes)` :
    # il suffisait qu'UN SEUL agent declare sa decoupe pour que la phrase
    # disparaisse — POUR TOUS LES AUTRES.
    #   Mesure du 14/09, trois agents, meme jeu :
    #       0 / 3 declarees  -> alarme LEVEE    (785 caracteres)
    #       1 / 3 declarees  -> alarme ETEINTE  (396 caracteres)
    #       2 / 3 declarees  -> alarme ETEINTE
    #       3 / 3 declarees  -> alarme ETEINTE  (legitime)
    # *Le classement met cote a cote des scores dont certains reposent sur
    # une hypothese signee et d'autres non, et le document se taisait
    # dessus.*
    # ⚠️ LA DOCTRINE ETAIT DEJA APPLIQUEE A COTE : le bloc juste au-dessus
    # sait dire une divergence PARTIELLE des assiettes d'apprentissage, en
    # nommant chaque agent. On lui emprunte sa forme.
    _declarees = [c.agent for c in sorted(lignes, key=lambda x: x.agent)
                  if c.declaree_au_plan]
    _non_declarees = [c.agent for c in sorted(lignes, key=lambda x: x.agent)
                      if not c.declaree_au_plan]
    if _declarees and _non_declarees:
        tete += (
            f"/!\\ DECLARATION PARTIELLE DE LA DECOUPE : "
            f"{len(_declarees)} agent(s) sur {len(lignes)} la declarent au "
            f"plan ({', '.join(_declarees)}), "
            f"{', '.join(_non_declarees)} non. Les scores ranges cote a "
            f"cote ne reposent donc PAS tous sur une hypothese signee, et "
            f"c'est le premier de ce classement qui devient le modele de "
            f"production. Declarez `decoupe_validation` au plan pour "
            f"{', '.join(_non_declarees)} aussi. ")
    if not _declarees:
        tete += (
            "/!\\ CETTE DECOUPE N'EST DECLAREE DANS AUCUN PLAN. Elle decide "
            "pourtant du modele retenu pour la production. Mesure du "
            "08/09/2026 : les memes six candidats notes sur deux decoupes "
            "80/20 des memes donnees voient 3 a 5 modeles sur 6 changer de "
            "rang, et leur Gini varier d'un facteur allant jusqu'a 3,8. "
            "Declarez `decoupe_validation` au plan pour que la mesure repose "
            "sur une hypothese signee.")
    return tete
