"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — ORCHESTRATEUR DU CHEMIN AGENT : LES TROIS CIBLES DU TARIF        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  A1 → A2 → A3, puis TROIS arbitrages complets — un par cible :               ║
║                                                                              ║
║    FRÉQUENCE  : A4(freq) → A5(freq, CANN+TabNet) → A6(freq)                  ║
║    COÛT       : A4(cout_moyen, sinistrés, sans poids)                        ║
║                 → A5(cout_moyen, TabNet SEUL) → A6(cout_moyen)               ║
║    PRIME PURE : A4(prime_pure, portefeuille ENTIER, sans poids)              ║
║                 → A5(prime_pure, TabNet SEUL) → A6(prime_pure)               ║
║                                                                              ║
║  POURQUOI CE MODULE EXISTE                                                   ║
║  ─────────────────────────                                                   ║
║  La prime pure est fréquence × coût. Or A4 et A5 ne s'entraînaient QUE sur   ║
║  la fréquence : sur la cible coût, A6 n'avait qu'un seul candidat (le GLM    ║
║  Gamma d'A3) et « l'arbitrait » contre personne. LA MOITIÉ DU TARIF N'ÉTAIT  ║
║  JAMAIS CHALLENGÉE. Constaté en re-vérifiant décennale : classement coût =   ║
║  1 ligne, 10 modèles écartés (à raison — ils déclaraient la fréquence).      ║
║                                                                              ║
║  Aucun orchestrateur n'existait : chaque appelant (app, demos, tests)        ║
║  assemblait la chaîne à la main — et `result_a5` valait `None` PARTOUT dans  ║
║  le dépôt : A5 n'était jamais câblé dans A6.                                 ║
║                                                                              ║
║  POURQUOI PAS AILLEURS                                                       ║
║  ─────────────────────                                                       ║
║  · Pas A6 : c'est un ARBITRE. Lui faire déclencher des entraînements         ║
║    inverserait les rôles et le rendrait intestable en isolation.             ║
║  · Pas pipeline_complet : c'est le chemin DÉCLARATIF (GLM pur), qui ne       ║
║    référence ni A4 ni A5. Autre architecture, autre objet.                   ║
║                                                                              ║
║  TROIS RÈGLES NON NÉGOCIABLES (décisions actuaires)                          ║
║  ──────────────────────────────────────────────────                          ║
║  1. Le sous-échantillon sinistrés vient de construire_cible_severite()       ║
║     (core/severite.py) — la SOURCE UNIQUE. On ne recalcule JAMAIS le masque  ║
║     ici : c'est cette duplication qui avait fait diverger A3 du déclaratif   ║
║     et sous-tarifer de 15 % (cf. 25f5711).                                   ║
║  2. CANN EXCLU de la cible coût. Son architecture est                        ║
║     exp(GLM_gelé(x) + offset·log(exposition)) : un modèle de COMPTAGE. La    ║
║     sévérité ne varie pas avec l'exposition — c'est le sens même de la       ║
║     décomposition E[S] = E[N] × E[C|N>0]. A5 reçoit modeles=('tabnet',).     ║
║  3. AUCUN POIDS sur la cible coût pour A4. L'exposition pondère un COMPTAGE, ║
║     pas une sévérité. Aligné sur pipeline_complet, qui ne pondère pas non    ║
║     plus son GLM de coût.                                                    ║
║                                                                              ║
║                                                                              ║
║  CONSTAT `agents/C1` -- CE MODULE N'A AUCUN APPELANT DE PRODUCTION, ET       ║
║  LES TROIS DEFAUTS QU'IL REPARE SONT INTACTS PARTOUT. Releve par AST         ║
║  sur tout le depot le 01/09/2026 : `pipeline_agents`, `ResultatAgents`,      ║
║  `ArbitrageCible`, `CIBLE_COUT` et `CIBLE_PRIME_PURE` ont chacun             ║
║  production=0. Les trois defauts decrits ci-dessus restent vrais chez        ║
║  les DEUX appelants de production hors app :                                 ║
║                                                                              ║
║    demos/pipeline_3lob_a1_a6_demo.py   5 agents sur 6, result_a5=None,       ║
║                                        A6 col_cible='nb_sinistres' seul      ║
║    scripts/rapport_tarif_local.py      idem, l.111                           ║
║                                                                              ║
║  Autrement dit : LA MOITIE DU TARIF N'EST TOUJOURS PAS CHALLENGEE chez       ║
║  eux -- ce module existe, il repare, et personne ne l'appelle.               ║
║                                                                              ║
║  CE N'EST PAS CORRIGE ICI, ET C'EST DELIBERE. Y brancher ces deux            ║
║  appelants leur ferait produire TROIS cibles et un A5 la ou ils n'en         ║
║  produisent qu'une : c'est un changement de SORTIE sur des livrables,        ║
║  pas un correctif de texte. Et `actuaria_app.py`, le troisieme, est          ║
║  hors assiette par arbitrage. *Un module qui repare sans etre appele         ║
║  n'est pas un defaut de code : c'est un cablage qui manque, et le dire       ║
║  vaut mieux que de laisser croire que la reparation a eu lieu.*              ║
║  AUTEUR    : ActuarIA                                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire
from core.qualite_donnees import preambule_qualite
from core.severite import CibleSeverite, construire_cible_severite, seuil_declare
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
from direction_non_vie.tarification.a5_deep_learning.agent import AgentA5DeepLearning
from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison

__all__ = ["ArbitrageCible", "ResultatAgents", "pipeline_agents", "CIBLE_COUT",
           "CIBLE_PRIME_PURE"]

# Nom de la cible de sévérité. DOIT être exactement celui que le GLM Gamma d'A3
# déclare (metriques['gamma']['cible']) : c'est sur cette chaîne que le filtre de
# cible d'A6 apparie les modèles. Une divergence ici et le Gamma serait écarté de
# son propre arbitrage.
CIBLE_COUT = "cout_moyen"

# Nom de la cible de PRIME PURE DIRECTE. DOIT être exactement celui que le GLM
# Tweedie d'A3 déclare (metriques['tweedie']['cible']='prime_pure') ET la colonne
# que A2 produit (_calculer_prime_pure : cout_total/expo, taux annualisé, HORS
# plan). Même contrat d'appariement de cible côté A6 que CIBLE_COUT.
CIBLE_PRIME_PURE = "prime_pure"


@dataclass(frozen=True)
class ArbitrageCible:
    """Un arbitrage complet, pour UNE cible."""
    cible:      str
    a4:         Optional[Dict[str, Any]]
    a5:         Optional[Dict[str, Any]]
    a6:         Optional[Dict[str, Any]]
    statut_rag: Optional[str]
    n_candidats: int          # modèles réellement en compétition
    erreur:     Optional[str] = None


@dataclass(frozen=True)
class ResultatAgents:
    """Les TROIS cibles du tarif, dans un objet unique : FRÉQUENCE et COÛT (dont
    le produit = prime pure par décomposition E[S]=E[N]×E[C|N>0]), et la PRIME
    PURE DIRECTE (route alternative Tweedie sur tout le portefeuille). Le tarif
    primaire reste fréquence×coût ; la prime pure directe est un CHALLENGEUR
    additif (d'où `.success` qui ne dépend que d'A3 + fréquence)."""
    plan:       PlanTarifaire
    a1:         Dict[str, Any]
    a2:         Dict[str, Any]
    a3:         Dict[str, Any]
    frequence:  ArbitrageCible
    cout:       ArbitrageCible
    prime_pure: ArbitrageCible
    audit_id:   str
    #: ⚠️⚠️ L'INSTANT DU RUN, CAPTURÉ UNE FOIS PAR L'APPELANT — jamais généré
    #: ici. `resume()` faisait `datetime.now()` À CHAQUE APPEL : deux appels sur
    #: le MÊME objet rendaient deux livrables d'audit différents (constat
    #: `agents/C4`). Les deux modules frères l'écrivent noir sur blanc —
    #: `core/qualite_donnees` : « ne génère aucun horodatage », et
    #: `core/conformite_reglementaire` : « aucune date n'est générée ici ».
    #: ⚠️ CHAMP REQUIS, ET C'EST DÉLIBÉRÉ. Un défaut (`''` ou `None`) laisserait
    #: un site de construction l'omettre en silence, et publier un vide sous
    #: une étiquette de date. *« Présent mais VIDE » a déjà mordu trois fois
    #: dans cet audit.* Cinq sites le construisent, tous dans le dépôt.
    #: ⚠️ IL N'EST PAS DÉRIVÉ DE `audit_id`, BIEN QU'IL L'ENCODE : `audit_id`
    #: est une ÉTIQUETTE, faite pour être lue. Lire une donnée dans une
    #: étiquette est le défaut même que cet audit poursuit.
    date_calcul: str

    @property
    def success(self) -> bool:
        """Le socle A3 a tenu, ET l'arbitrage FRÉQUENCE a réellement abouti.

        ⚠️⚠️ CONSTAT `agents/C2` — ELLE TESTAIT LA PRÉSENCE, PAS LE SUCCÈS.
        L'ancienne condition était `self.frequence.a6 is not None`. Or
        `_arbitrer` rend **toujours** un dict `a6` : A6 en échec en rend un
        aussi, avec `success: False`. Mesuré :

            a6 = {'success': False, 'erreur': 'A6 a echoue', 'classement': []}
            -> ResultatAgents.success       = True
               resume()['success']          = True
               resume()[...]['modele_production'] = None

        Le `resume()` — que sa propre docstring appelle **« le livrable
        d'audit »** — publiait donc un succès sur un dossier sans modèle et
        sans classement. *Un objet présent n'est pas un objet qui a réussi ;
        `is not None` répond à la mauvaise question.*

        ⚠️ ON LIT LE DRAPEAU D'A6, PAS UNE FORME. A6 pose `success` sur ses
        deux sorties — le retour nominal et `_erreur` — vérifié par exécution
        avant d'écrire cette ligne. Déduire l'échec d'un `classement` vide
        serait deviner par un symptôme.

        ⚠️ LA PORTÉE NE CHANGE PAS : `.success` ne regarde toujours QUE A3 et
        la FRÉQUENCE, comme la docstring de la classe l'explique — la prime
        pure directe est un challengeur additif. Ce lot corrige *ce qui est
        testé*, pas *ce qui est regardé*.
        """
        return (bool(self.a3.get("success"))
                and bool((self.frequence.a6 or {}).get("success")))

    def resume(self) -> Dict[str, Any]:
        """Vue JSON-SÉRIALISABLE des deux arbitrages — le livrable d'audit.

        Même contrat que tarifer() : 100 % types natifs, json.dumps() ne lève
        jamais, y compris sur un échec. Les objets lourds (dataframes, modèles
        sklearn/torch, bytes Excel) restent dans ResultatAgents mais N'ENTRENT PAS
        ici : ce résumé est fait pour être TRACÉ et TRANSMIS, pas pour rejouer le
        pipeline. C'est pourquoi ResultatAgents lui-même n'est pas sérialisable —
        et n'a pas à l'être : il porte de quoi travailler, resume() de quoi rendre
        compte.
        """
        def _f(x):
            return float(x) if isinstance(x, (int, float, np.floating)) else None

        def _arb(a: "ArbitrageCible") -> Dict[str, Any]:
            r6 = a.a6 or {}
            return {
                "cible":       a.cible,
                "statut_rag":  a.statut_rag,
                "n_candidats": int(a.n_candidats),
                "erreur":      a.erreur,
                "modele_production": (r6.get("modele_production") or {}).get("modele"),
                "classement": [
                    {"modele":   str(c.get("modele")),
                     "famille":  str(c.get("famille")),
                     "cible":    str(c.get("cible")),
                     "gini_test":    _f(c.get("gini_test")),
                     "score_global": _f(c.get("score_global"))}
                    for c in (r6.get("classement") or [])
                ],
                "exclusions_cible": [
                    {"modele":       str(e.get("modele")),
                     "cible_modele": str(e.get("cible_modele")),
                     "raison":       str(e.get("raison"))}
                    for e in (r6.get("exclusions_cible") or [])
                ],
                "alertes_modele": [str(x.get("code"))
                                   for x in (r6.get("alertes_modele") or [])],
                # ⚠️⚠️ CONSTAT `services/C13` — UN RUN POUVAIT ETRE VERT SANS
                # AVOIR PRODUIT UN SEUL DOCUMENT. Les neuf exportateurs du
                # module font `logger.error(...)` puis `return b''` : ce n'est
                # pas silencieux dans le JOURNAL, ca l'etait dans le VERDICT.
                # Mesure : Excel A6 de 10 976 octets a 0, `success` toujours
                # True, statut RAG inchange.
                #
                #   *Un document ne peut pas annoncer sa propre absence ; c'est
                #   au compte rendu du run de le faire.*
                #
                # ⚠️ Il ne DEGRADE PAS le statut RAG, delibrement : le RAG
                # mesure la qualite du TARIF, un document manquant est un
                # incident de RENDU. *Rendre a chacun sa propre question.*
                "livrables_absents": list(r6.get("livrables_absents") or []),
                "livrables_tailles": {
                    str(k): int(v) for k, v in
                    (r6.get("livrables_tailles") or {}).items()},
            }

        return {
            "success":        bool(self.success),
            "audit_id":       self.audit_id,
            # ⚠️ RÉUTILISÉ, JAMAIS GÉNÉRÉ : deux appels sur le même objet
            # rendaient deux livrables différents (constat `agents/C4`).
            "date_calcul":    self.date_calcul,
            "plan_lob":       self.plan.lob,
            "plan_empreinte": self.plan.empreinte(),
            "frequence":      _arb(self.frequence),
            "cout":           _arb(self.cout),
            "prime_pure":     _arb(self.prime_pure),
        }


def _vue_sinistres(
    result_a2: Dict[str, Any], plan: PlanTarifaire
) -> tuple[Dict[str, Any], CibleSeverite]:
    """Vue SINISTRÉS de result_a2, prête pour un entraînement sur la sévérité.

    ⚠️⚠️ CONSTAT `agents/C5` — ELLE ANNONÇAIT UN DICT ET RENDAIT UN TUPLE.
    L'annotation disait `Dict[str, Any]` ; la fonction rend
    `({**result_a2, 'dataframe': df_sin}, cible)`. La docstring était juste
    sur le premier membre — « un result_a2 de MÊME FORME » — et TAISAIT le
    second, qui est l'objet `CibleSeverite` dont l'appelant lit `n_retenus`
    juste après, pour le seuil des 100 sinistrés. *Une annotation qui dit
    la moitié du contrat est plus traître qu'une annotation absente : elle
    fait croire que le contrat est connu.*

    Le masque, l'écrêtement et la cible viennent de construire_cible_severite() —
    la SOURCE UNIQUE, la même qu'A3 et pipeline_complet. On ne recalcule rien :
    dupliquer cette définition est exactement ce qui avait fait diverger les deux
    chemins (A3 ajustait le coût TOTAL en l'appelant 'cout_moyen', −15 % de tarif).

    Retourne un result_a2 de MÊME FORME, dont le dataframe est restreint aux
    contrats à coût observé et porte la colonne `CIBLE_COUT` (coût par sinistre,
    écrêté). A4/A5 peuvent alors l'utiliser sans savoir comment elle est faite.
    """
    df = result_a2["dataframe"]
    cible = construire_cible_severite(
        df[plan.cible_cout], df[plan.cible_frequence], df[plan.exposition],
        seuil=seuil_declare(plan))
    df_sin = df[cible.masque].copy().reset_index(drop=True)
    df_sin[CIBLE_COUT] = cible.severite
    return {**result_a2, "dataframe": df_sin}, cible


def _n_candidats(r6: Optional[Dict[str, Any]]) -> int:
    return len((r6 or {}).get("classement") or [])


def pipeline_agents(
    dataframe: pd.DataFrame,
    plan: PlanTarifaire,
    sous_branche: str,
    *,
    branche: str = "non_vie",
    environnement: str = "production",
    profil_valide_par: Optional[str] = None,
    valide_par_actuaire_dl: Optional[str] = None,
    #: ⚠️⚠️ LE CANAL DE SIGNATURE QUALITE — etape 3 du chantier 1-B, 01/09/2026.
    #: Meme nom, meme sens que sur le chemin declaratif
    #: (`pipeline_tarifaire.pipeline_complet`) : *deux noms pour le meme geste
    #: auraient cree deux doctrines.* Il n'a PAS ENCORE d'objet -- le chemin
    #: agent n'appelle pas la couche qualite (`qualite/C4`), donc aucun blocage
    #: n'est a lever -- et il REFUSE plutot que d'avaler un nom en silence.
    #: *Un canal qui accepte une signature sans rien valider laisse croire a
    #: une validation qui n'a pas eu lieu ; c'est la silhouette de `socle/C2`.*
    #: ⚠️ `str | None` et non `Optional[str]` comme ses voisines : la proprete
    #: refuse un ecart sur une ligne de correction, et l'ancienne forme en est
    #: un. *Les voisines sont une dette arbitree ; la rejoindre l'aggraverait.*
    qualite_validee_par: str | None = None,
    rapport_mapping: Optional[Any] = None,
    n_epochs_dl: int = 200,
    batch_size_dl: int = 512,
    calcul_shap: bool = True,
    generer_graphiques: bool = False,
    models_path: str = "/tmp",
    audit_path: str = "/tmp",
    verbose: bool = False,
) -> ResultatAgents:
    """Enchaîne A1→A6 sur les TROIS cibles et rend les trois arbitrages.

    `sous_branche` est DÉCLARÉE (A1 ne devine plus la LoB) ; `plan` est le plan
    signé, autorité de bout en bout. Les agents DL/ML sont appelés TROIS FOIS —
    une fois par cible — plutôt que refactorés en multi-cibles : A6 arbitre déjà
    une cible par appel, et le résultat de chaque agent porte UNE `col_cible`
    que le filtre de cible d'A6 apparie. Le grain existant est le bon.

    Un arbitrage peut échouer là où un autre réussit (COÛT : trop peu de
    sinistres ; PRIME PURE : donnée dégénérée) : c'est rendu dans `<cible>.erreur`,
    jamais masqué, et n'empêche pas les autres d'aboutir. `.success` ne dépend que
    d'A3 + fréquence (le tarif primaire reste fréquence×coût).

    ⚠️⚠️ `qualite_validee_par` : LE CANAL EXISTE, IL N'A PAS ENCORE D'OBJET.
    Le chemin agent n'appelle pas la couche qualité (constat `qualite/C4`),
    donc aucun blocage n'est à lever et une signature ne validerait rien. Il
    LÈVE `SignatureSansObjet` plutôt que d'avaler un nom en silence — **c'est
    l'étape 1-B, et elle déplace un prix**. Pour tarifer AVEC la couche
    qualité aujourd'hui : `pipeline_tarifaire.pipeline_complet`, qui la porte.
    """
    # ⚠️ UN SEUL INSTANT POUR TOUT LE RUN, capturé ici et transporté.
    # `astimezone()` rend l'horodatage NON AMBIGU (offset explicite) sans
    # toucher `audit_id` : la chaîne locale `%Y%m%d_%H%M%S` est identique,
    # vérifié.
    t0 = datetime.now().astimezone()
    audit_id = f"AGENTS_{t0.strftime('%Y%m%d_%H%M%S')}"
    date_calcul = t0.isoformat()
    _a = dict(models_path=models_path, audit_path=audit_path, verbose=verbose)

    # ── SOCLE COMMUN : A1 → A2 → A3 ─────────────────────────────────────────
    r1 = AgentA1Ingestion(audit_path=audit_path, verbose=verbose).run(
        branche=branche, sous_branche=sous_branche, dataframe=dataframe)

    # ── 1-B : LA COUCHE QUALITÉ, LA MÊME QUE LE CHEMIN DÉCLARATIF ───────────
    # ⚠️⚠️ ÉTAPE ⑤ DU CHANTIER 1-B, arbitrée par Selasse le 02/09/2026. Elle
    # FERME `qualite/C4` : `controler_qualite` n'avait qu'UN appelant de
    # production, et les deux chemins ont pu diverger toute une journée sur la
    # même grandeur. *Une porte unique rend la divergence IMPOSSIBLE au lieu
    # de la rendre seulement évitable.*
    #
    # ⚠️ APRÈS A1, AVANT A2 — et l'assiette a été mesurée avant d'être choisie.
    # A1 rend la donnée lisible (types, mapping) sans retirer aucune ligne ;
    # A2, lui, MUTE. Placer la couche après A2 lui ferait rater ce qu'A2 a
    # déjà exclu : mesuré sur le fichier témoin, l'union tombait de 6,0 % à
    # 3,1 % et le blocage disparaissait. *Un garde-fou placé après le geste
    # qu'il surveille ne surveille plus rien.*
    #
    # ⚠️⚠️ CE QUE ÇA DÉPLACE, MESURÉ AVANT D'ÊTRE FAIT :
    #
    #     DONNEE REELLE, 12 654 contrats : 12 654 / 12 654 retenues, DELTA 0,
    #                                      aucun blocage
    #     fichier temoin (30 freq<0 + 30 expo<=0) : BLOQUE, union 6,0 %,
    #                                      -60 lignes apres signature
    #
    # Aucun euro ne bouge sur le seul portefeuille réel du dépôt. Ce qui
    # apparaît, c'est un blocage à signature nominative sur des fichiers qui
    # portent des lignes IMPOSSIBLES — et la liste disqualifiante, arbitrée à
    # l'étape ⑤-①, dit lesquelles.
    #
    # ⚠️ LE CANAL DE SIGNATURE A ENFIN SON OBJET. Il refusait
    # (`SignatureSansObjet`) tant qu'aucun blocage n'existait ; il porte
    # désormais le nom jusqu'à la couche, qui seule peut lever le blocage.
    _rq = preambule_qualite(
        (r1 or {}).get('dataframe'), plan,
        qualite_validee_par=qualite_validee_par, horodatage=date_calcul)
    r1 = {**r1, 'dataframe': _rq.dataframe_propre}

    r2 = AgentA2Preprocessing(audit_path=audit_path, verbose=verbose).run(
        result_a1=r1, plan=plan)

    # ── L'OBSERVATION A ÉTÉ RETIRÉE, PUIS SUPPRIMÉE ────────────────────
    # ⚠⚠ ÉTAPE 4 CLOSE PAR L'ÉTAPE 5, LE 02/09/2026. L'observation publiait
    # « COUCHE QUALITE OBSERVEE, NON APPLIQUEE [...] RIEN n'a ete applique ».
    # Depuis le branchement ci-dessus, elle EST appliquee : cette phrase serait
    # FAUSSE dans le rapport signe.
    #
    #   *Un mecanisme qui survit a sa raison d'etre devient un mensonge.*
    #
    # Elle avait un objet precis -- mesurer ce que la couche FERAIT pour que
    # l'arbitrage se prenne sur des frequences reelles. L'arbitrage est pris,
    # et son outillage (`observer_qualite`, le canal `observation_qualite` a
    # travers A6 et les quatre surfaces) a ete SUPPRIME le jour meme, sur
    # arbitrage de Selasse : *garder un instrument apres qu'il a rendu son
    # verdict n'est pas de la prudence, c'est de la dette.* `QNE-9` tient le
    # retrait complet. Le vrai rapport de la couche dit ce qui a ETE fait.

    # A3 entraîne DÉJÀ ses trois modèles (Poisson fréquence, Gamma coût, Tweedie
    # prime pure) en un seul run : c'est son architecture, on ne la double pas.
    r3 = AgentA3GLM(**_a).run(
        result_a2=r2, plan=plan,
        col_frequence=plan.cible_frequence, col_cout=plan.cible_cout,
        generer_graphiques=generer_graphiques)

    def _echec(cible: str, msg: str) -> ArbitrageCible:
        return ArbitrageCible(cible=cible, a4=None, a5=None, a6=None,
                              statut_rag=None, n_candidats=0, erreur=msg)

    if not r3.get("success"):
        msg = f"A3 a échoué : {r3.get('erreur')}"
        return ResultatAgents(plan=plan, a1=r1, a2=r2, a3=r3,
                              frequence=_echec(plan.cible_frequence, msg),
                              cout=_echec(CIBLE_COUT, msg),
                              prime_pure=_echec(CIBLE_PRIME_PURE, msg),
                              audit_id=audit_id, date_calcul=date_calcul)

    def _arbitrer(cible, r2_cible, *, modeles_dl, ponderer) -> ArbitrageCible:
        """Une cible : A4 → A5 → A6. Les échecs sont rendus, jamais masqués."""
        r4 = AgentA4ML(**_a).run(
            result_a2=r2_cible, result_a3=r3, plan=plan, col_cible=cible,
            ponderer_par_exposition=ponderer, calcul_shap=calcul_shap,
            generer_graphiques=generer_graphiques)
        r5 = AgentA5DeepLearning(**_a).run(
            result_a2=r2_cible, result_a3=r3, result_a4=r4, plan=plan,
            col_cible=cible, modeles=modeles_dl, n_epochs=n_epochs_dl,
            batch_size=batch_size_dl, generer_graphiques=generer_graphiques)
        r6 = AgentA6Comparaison(**_a).run(
            result_a2=r2_cible, result_a3=r3, result_a4=r4,
            result_a5=r5 if r5.get("success") else None,
            # ⚠️ LE MÊME CHAÎNON MANQUANT QUE `rapport_qualite` — constat
            # `A6.7`. `A6.run` accepte `result_a1` depuis toujours et le
            # relaie au rapport d'équipe ; **aucun appelant ne le passait**.
            # L'onglet « Qualité des données (A1) » lisait donc `{}`.
            #   ⚠️⚠️ ET CETTE LIGNE-CI EST INERTE AUJOURD'HUI, IL FAUT LE DIRE :
            #   ce pipeline force `generer_rapport_equipe=False` (l. 464 et
            #   suivantes), donc il ne produit AUCUN rapport d'équipe. Elle est
            #   posée parce qu'elle est juste et gratuite — le jour où ce
            #   drapeau passe à True, la qualité suivra au lieu de manquer.
            #   *Le correctif qui MORD est ailleurs* : la déclaration dans
            #   `rapport_equipe_tarif`, qui protège TOUTE surface recevant un
            #   `result_a1` vide — y compris celles qu'on ne modifie pas ici.
            #   ⚠️ ZÉRO EURO : mesuré par AST, `result_a1` n'est lu, dans tout
            #   A6, QUE pour construire `_results_equipe`.
            result_a1=r1,
            col_cible=cible, plan=plan, environnement=environnement,
            profil_valide_par=profil_valide_par,
            valide_par_actuaire_dl=valide_par_actuaire_dl,
            rapport_mapping=rapport_mapping,
            # ⚠️⚠️ ÉTAPE 1 DU CHANTIER `unite_exposition` — LE CHAÎNON QUI
            # MANQUAIT. `A6.run` accepte `rapport_qualite` depuis toujours et
            # le relaie aux TROIS livrables ; le chemin déclaratif le
            # remplissait, **le chemin agent ne le passait jamais** (0 mention
            # mesurée). *La plomberie était posée, rien ne l'alimentait.*
            # A2 le produit désormais pour ses mutations d'exposition.
            # ⚠⚠ LE RAPPORT DE LA COUCHE PREND LA PLACE DE L'OBSERVATION.
            # A2 publie encore le sien pour ses propres mutations ; la
            # couche, elle, dit ce qu'elle a EXCLU, CORRIGE et SIGNALE sur
            # tout le portefeuille. *Deux rapports, deux gestes -- et la
            # synthese les publie tous les deux, cote a cote.*
            rapport_qualite=(_rq or (r2 or {}).get('rapport_qualite')),
            generer_graphiques=generer_graphiques, generer_rapport_equipe=False)
        return ArbitrageCible(cible=cible, a4=r4, a5=r5, a6=r6,
                              statut_rag=r6.get("statut_rag"),
                              n_candidats=_n_candidats(r6))

    # ── CIBLE 1 : FRÉQUENCE — le portefeuille entier, pondéré par l'exposition ─
    # ⚠️⚠️ CONSTAT `agents/C3` — ELLE ÉTAIT LA SEULE DES TROIS SANS FILET.
    # La docstring de ce module promet : « Un arbitrage peut échouer là où un
    # autre réussit [...] c'est rendu dans `<cible>.erreur`, jamais masqué, et
    # n'empêche pas les autres d'aboutir. » Mesuré : le COÛT et la PRIME PURE
    # sont enveloppés, la FRÉQUENCE ne l'était pas — une exception y remontait
    # hors de `pipeline_agents` et TUAIT les deux autres cibles.
    # ⚠️ AUCUN SUCCÈS N'EST MASQUÉ : `_echec` pose `a6=None`, et
    # `ResultatAgents.success` lit `frequence.a6['success']` — il reste donc
    # `False`. *Rendre l'erreur n'est pas l'avaler.*
    try:
        frequence = _arbitrer(plan.cible_frequence, r2,
                              modeles_dl=("cann", "tabnet"), ponderer=True)
    except Exception as e:  # noqa: BLE001  # pragma: no cover
        frequence = _echec(
            plan.cible_frequence,
            f"Fréquence non modélisable : {type(e).__name__}: {e}")

    # ── CIBLE 2 : COÛT — sinistrés seulement, sans poids, TabNet seul ────────
    try:
        r2_cout, cible_sev = _vue_sinistres(r2, plan)
    except Exception as e:  # noqa: BLE001  # pragma: no cover
        cout = _echec(CIBLE_COUT, f"Vue sinistrés impossible : {type(e).__name__}: {e}")
    else:
        if cible_sev.n_retenus < 100:
            # On ne bricole pas un modèle sur trois sinistres : on le DIT.
            cout = _echec(
                CIBLE_COUT,
                f"Sévérité non modélisable : {cible_sev.n_retenus} contrat(s) à "
                f"coût observé (< 100). Le GLM Gamma d'A3 reste la référence.")
        else:
            cout = _arbitrer(CIBLE_COUT, r2_cout,
                             modeles_dl=("tabnet",), ponderer=False)

    # ── CIBLE 3 : PRIME PURE DIRECTE — portefeuille ENTIER, sans poids, TabNet ─
    # La prime pure (cout/expo, taux annualisé produit par A2 HORS plan) est une
    # cible Tweedie : masse en 0 (non-sinistrés) + queue. On l'entraîne sur TOUT
    # le portefeuille — PAS la vue sinistrés : ici la masse en 0 EST le signal
    # (fréquence × sévérité en un seul modèle). ponderer=False : la cible est déjà
    # annualisée, donc exposure-INDÉPENDANTE (même raison qui exclut le CANN, dont
    # l'offset log-expo est une construction de comptage). Concurrent GLM = le
    # Tweedie d'A3 (cible='prime_pure'). PAS de seuil <100 : le portefeuille entier
    # fournit toujours des lignes ; le signal (fonction du nombre de sinistrés) est
    # évalué par le RAG d'A6. Enveloppé comme le coût : un échec est DIT, pas masqué.
    if CIBLE_PRIME_PURE not in r2["dataframe"].columns:
        # ⚠️⚠️ CONSTAT `agents/C6` — CE MESSAGE ACCUSAIT LE MAUVAIS
        # COUPABLE. Il disait « contrat de données V7 B2 rompu », ce qui
        # envoie l'actuaire chercher une rupture de contrat entre A2 et
        # A3. Mesuré le 01/09 : `A2._calculer_prime_pure` lit
        # `'cout_total_sinistres'` et `'exposition'` EN DUR, pas
        # `plan.cible_cout` / `plan.exposition`. Sur 19 des 20 plans les
        # deux coïncident ; sur `auto_fr_reel.yaml` — celui bâti sur le
        # jeu français réel — ils s'appellent `ClaimAmountTotal` et
        # `Exposure`, et la TROISIÈME CIBLE est perdue.
        # *Une instruction que l'actuaire ne peut pas suivre est pire
        # que le silence* — le jugement déjà porté par le BLOQUANT B7.
        # ⚠️ LA CAUSE, ELLE, N'EST PAS CORRIGÉE ICI : faire lire le plan à
        # `_calculer_prime_pure` FERAIT APPARAÎTRE une troisième cible là
        # où il n'y en a aucune aujourd'hui. C'est un changement de
        # SORTIE sur un plan signé : il est nommé, pas décidé ici.
        prime_pure = _echec(
            CIBLE_PRIME_PURE,
            f"Colonne '{CIBLE_PRIME_PURE}' absente d'A2. CAUSE MESURÉE : "
            f"A2._calculer_prime_pure lit 'cout_total_sinistres' et "
            f"'exposition' EN DUR ; ce plan déclare "
            f"cible_cout='{plan.cible_cout}' et "
            f"exposition='{plan.exposition}'. Tant que les deux ne "
            f"coïncident pas, la cible prime pure ne peut pas être "
            f"produite — ce n'est PAS un contrat de données rompu.")
    else:
        try:
            prime_pure = _arbitrer(CIBLE_PRIME_PURE, r2,
                                   modeles_dl=("tabnet",), ponderer=False)
        except Exception as e:  # noqa: BLE001  # pragma: no cover
            prime_pure = _echec(
                CIBLE_PRIME_PURE,
                f"Prime pure non modélisable : {type(e).__name__}: {e}")

    return ResultatAgents(plan=plan, a1=r1, a2=r2, a3=r3,
                          frequence=frequence, cout=cout,
                          prime_pure=prime_pure, audit_id=audit_id,
                          date_calcul=date_calcul)
