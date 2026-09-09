"""
=============================================================================
  ActuarIA — CE QUI A PRODUIT LE PRIX, ET CE QUE LE CLASSEMENT RECOMMANDE
=============================================================================

⚠️⚠️ CE QUE CE MODULE FERME, ET C'EST UNE OMISSION, PAS UN MENSONGE. Mesuré le
09/09/2026 sur le document réellement produit :

  · le rapport NOMME un modèle retenu — *« NE PAS déployer GLM_POISSON en
    l'état… soumettre le modèle à la validation de l'actuaire signataire »* ;
  · le bloc PRIX ne dit **rien** de son origine — ni « GLM », ni le nom d'un
    modèle ;
  · et **aucune phrase ne relie les deux** : `GLM_POISSON` n'apparaît jamais à
    côté d'un prix, d'une prime ou d'un tarif.

*Le document ne ment pas : il se tait.* Un lecteur voit « modèle de
production » dans une section et un prix dans une autre, et les relie.
Aujourd'hui il a raison **par coïncidence** — les deux sont bien un GLM
Poisson. Le jour où le classement couronne un modèle ML, il aurait tort, et
rien ne l'avertirait.

⚠️⚠️ ET CE JOUR PEUT ARRIVER, MESURÉ. Le classement et le tarif ne se croisent
NULLE PART : `pipeline_complet` ne lit jamais `result_a6`, et le tarif ajuste
toujours son propre GLM. Or la marge du vainqueur relevée sur un run réel vaut
**0,0357** (GLM_POISSON 0,6602 contre DL_CANN 0,6245), pendant qu'un
changement de découpe fait varier le Gini d'un facteur allant **jusqu'à 3,8**,
pondéré 0,40 dans la grille. *La bascule est possible ; elle ne s'est
simplement pas produite sur les tirages essayés.*

⚠️ CE QUE CE MODULE NE FAIT PAS, ET C'EST DÉLIBÉRÉ. Il ne fait pas alimenter
le prix par le modèle classé : ce serait une refonte du produit, pas une
correction de défaut, et elle déplacerait des euros. **Il dit ce qui est.**

⚠️ IL SE TAIT QUAND LES DEUX COÏNCIDENT. Une phrase d'alerte permanente ne
signalerait plus rien le jour où elle compterait — c'est la doctrine du refus
d'anti-sélection et de la bande de niveau : *on parle quand il y a quelque
chose à dire.*
=============================================================================
"""

from __future__ import annotations

__all__ = ['MODELE_DU_TARIF', 'phrase_origine_du_prix']

#: ⚠️⚠️ LE MODÈLE QUI PRODUIT RÉELLEMENT LE PRIX, ET IL N'EST PAS NÉGOCIABLE
#: PAR LE CLASSEMENT. `pipeline_complet` appelle `ajuster_glm_frequence`, dont
#: la docstring dit « Poisson, lien log, offset log-exposition ». Le coût vient
#: d'un second GLM, dont la famille est DÉCLARÉE au plan.
MODELE_DU_TARIF = 'GLM_POISSON'


def phrase_origine_du_prix(famille_severite=None,
                           modele_recommande=None) -> str:
    """D'où vient ce prix — et s'il diffère de ce que le classement recommande.

    ⚠️ `famille_severite` vient du PLAN, jamais d'un défaut : c'est l'actuaire
    qui déclare la loi de coût. `None` se dit « non déclarée », il ne se
    devine pas.

    ⚠️⚠️ L'ALERTE NE SE DÉCLENCHE QUE SUR UNE VRAIE DIVERGENCE. Comparer un
    nom absent, vide, ou égal au modèle du tarif ne signale rien — sinon le
    document crierait à chaque page et plus personne ne le lirait le jour où
    il aurait raison.
    """
    cout = (str(famille_severite).strip() if famille_severite
            else '') or 'non declaree'
    phrase = (
        f"Origine de ce prix : GLM de FREQUENCE (Poisson, lien log, offset "
        f"log-exposition) multiplie par le GLM de COUT (famille {cout}, "
        f"declaree au plan), ajustes sur 100 % du portefeuille retenu, puis "
        f"cale par le coefficient d'equilibre technique.")
    recommande = str(modele_recommande or '').strip()
    if recommande and recommande.upper() != MODELE_DU_TARIF:
        phrase += (
            f" /!\\ LE MODELE RECOMMANDE PAR LE CLASSEMENT N'EST PAS CELUI QUI "
            f"A PRODUIT CE PRIX : le classement retient '{recommande}', ce "
            f"prix vient de {MODELE_DU_TARIF}. Le classement RECOMMANDE un "
            f"modele ; il ne determine pas le prix publie -- les deux "
            f"mecanismes ne se croisent nulle part. Ne lisez donc pas ce "
            f"montant comme le prix qu'aurait produit '{recommande}'.")
    return phrase
