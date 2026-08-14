# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 : « NON VIDE » N'EST PAS « RENSEIGNÉ »
=============================================================================

⚠️⚠️ POURQUOI CE MODULE EXISTE, ET IL A ÉTÉ MESURÉ, PAS SUPPOSÉ. Les cinq
portes de signature du chantier vérifiaient qu'un champ n'était pas VIDE. Un
producteur de données a livré une déclaration d'ajustement pour risque dont
le signataire s'appelait littéralement `A_RENSEIGNER` et l'arrêté
`A_RENSEIGNER`, avec un statut `A_REMPLACER` et l'avertissement « taux
INVENTÉS ». **Elle a été ACCEPTÉE intégralement.**

    AjustementRisque(montant=1253.29, niveau_confiance='0.75',
                     methode='quantile', arrete='A_RENSEIGNER',
                     actuaire_resp='A_RENSEIGNER')

⚠️ ET AJOUTER UN CONTRÔLE DE « STATUT » N'AURAIT PAS SUFFI. Le signataire
fictif serait passé quand même. Le défaut de fond n'est pas un champ
manquant : c'est que `not valeur.strip()` attrape `''` et les espaces, et
laisse passer `A_RENSEIGNER`, `TBD`, `N/A`, `XXX`, `TODO`.

⚠️ CE QUI REND CE DÉFAUT GRAVE : ces portes sont le mécanisme sur lequel
repose CHAQUE décision d'entité de ce chantier — §54, §59 a), B66 d),
§36 b), §37, le déclenchement du §57, la base de la prime. Une porte
perméable les rend toutes perméables.

⚠️ LE PIÈGE INVERSE A ÉTÉ MESURÉ AVANT DE POSER LE CONTRÔLE. Un refus trop
large bloquerait des valeurs légitimes. Le détecteur a été confronté à 21
valeurs réellement employées dans le chantier — noms d'actuaires, arrêtés,
méthodes, sources, niveaux de confiance, portefeuilles, devises — et à 21
formes de remplissage fictif : ZÉRO rejet à tort, ZÉRO échappement.

⚠️ ET LA COMPARAISON PORTE SUR LA VALEUR ENTIÈRE, JAMAIS SUR UNE
SOUS-CHAÎNE. Sinon `nan` condamnerait « financement », `x` condamnerait
« Xavier », `na` condamnerait « Nanterre ». Vérifié sur ces trois cas et
cinq autres.
=============================================================================
"""

import re
import unicodedata

#: Les formes de remplissage fictif refusées. ⚠️ LISTE FERMÉE ET COMPARÉE À
#: LA VALEUR ENTIÈRE APRÈS NORMALISATION — jamais en sous-chaîne.
PLACEHOLDERS = frozenset({
    'a renseigner', 'a remplacer', 'a completer', 'a definir', 'a determiner',
    'tbd', 'todo', 'na', 'n a', 'nc', 'xxx', 'yyy', 'zzz', '?',
    'null', 'none', 'nan', 'vide', 'inconnu', 'non renseigne', 'non defini',
    'to be defined', 'to be determined', 'placeholder', 'fixme', 'x', '0',
})

MOTIF_NON_RENSEIGNE = 'champ_non_renseigne'


def normaliser(valeur) -> str:
    """La valeur, sans accents, sans casse, séparateurs unifiés.

    ⚠️ `A_RENSEIGNER`, `à renseigner`, `A-RENSEIGNER` et `a  renseigner`
    doivent se ramener à la même forme, sinon le contrôle se contourne par
    la typographie.
    """
    s = unicodedata.normalize('NFKD', str(valeur or ''))
    s = s.encode('ascii', 'ignore').decode()
    s = re.sub(r'[_\-/\\.?]+', ' ', s.lower()).strip()
    return re.sub(r'\s+', ' ', s)


def est_renseigne(valeur) -> bool:
    """Vrai si la valeur dit quelque chose. ⚠️ VIDE ET FICTIF SONT ÉGAUX ICI.

    Une chaîne vide et `A_RENSEIGNER` désignent la même chose — l'absence —
    et le second est le plus dangereux des deux, parce qu'il a l'apparence
    d'une réponse.
    """
    n = normaliser(valeur)
    return bool(n) and n not in PLACEHOLDERS


def exiger(valeur, champ: str, exigence: str, erreur):
    """Rend la valeur nettoyée, ou lève `erreur` en disant ce qui manque.

    ⚠️ `erreur` EST PASSÉE EN PARAMÈTRE pour que ce module n'importe rien :
    chaque porte lève SON type de refus, et celui-ci ne connaît aucune
    d'elles. Le sens de la dépendance compte — un contrôle transversal qui
    connaîtrait ses appelants deviendrait leur maître.
    """
    if est_renseigne(valeur):
        return str(valeur).strip()
    vu = normaliser(valeur)
    raison = ('vide' if not vu
              else f"« {str(valeur).strip()} » — une forme de remplissage "
                   f"fictif, pas une réponse")
    raise erreur(
        MOTIF_NON_RENSEIGNE,
        f"« {champ} » n'est pas renseigné : {raison}. {exigence} "
        f"⚠️ « NON VIDE » N'EST PAS « RENSEIGNÉ » : un champ portant "
        f"`A_RENSEIGNER` ou `TBD` a l'apparence d'une réponse et n'en est "
        f"pas une. Cette porte a déjà laissé passer une déclaration signée "
        f"« A_RENSEIGNER ».")
