"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — CIBLE DE SÉVÉRITÉ : LA SOURCE UNIQUE                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Ce que le modèle de coût doit ajuster — et ce qu'il met de côté.            ║
║                                                                              ║
║  POURQUOI CE MODULE EXISTE                                                   ║
║  ─────────────────────────                                                   ║
║  Cette définition existait DEUX fois, et les deux se contredisaient :        ║
║                                                                              ║
║    · pipeline_complet (déclaratif) : cout_ecrete / nb_sinistres, masque      ║
║      (cout_ecrete > 0) & (nb > 0), écrêtement q0.995 → CORRECT.              ║
║    · A3._calibrer_gamma (agent)    : cout_total_sinistres, masque cout > 0,  ║
║      aucun écrêtement → il déclarait 'cout_moyen' et ajustait le TOTAL.      ║
║                                                                              ║
║  Conséquence MESURÉE sur un portefeuille décennale 100k à structure causale  ║
║  connue : le coefficient de `montant` du Gamma d'A3 absorbait AUSSI l'effet  ║
║  fréquence (plus de montant → plus de sinistres → plus de coût TOTAL). Pente ║
║  surestimée, donc prédiction effondrée hors de l'échantillon des sinistrés : ║
║  32 178 € au lieu de 36 797 € (−12,6 %), et Σ primes / Σ charge = 0,85 —     ║
║  A3 SOUS-TARIFIAIT de 15 %. Le chemin déclaratif, lui, tombait à 0,07 % de   ║
║  la vérité du DGP. Une définition dupliquée n'est pas un doublon : c'est une ║
║  divergence en attente.                                                      ║
║                                                                              ║
║  AUTEUR    : ActuarIA                                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

# ⚠️ CONSTAT `socle/C3` — `CibleSeverite` EST EXPORTÉE SANS ÊTRE NOMMÉE.
# Mesuré par AST le 01/09/2026 : zéro occurrence hors de ce module, tests
# compris. Elle reste dans `__all__` parce qu'elle est LE TYPE DE RETOUR de
# `construire_cible_severite` : ses trois appelants l'utilisent — ils lisent
# `.n_retenus`, `.seuil` — sans jamais écrire son nom. *L'exporter est ce qui
# permet de l'annoter ; ne pas dire pourquoi la ferait passer pour un oubli.*
__all__ = ["CibleSeverite", "construire_cible_severite",
           "synthese_assiette_ecretement"]


@dataclass(frozen=True)
class CibleSeverite:
    """Le contrat de la cible de sévérité, immuable.

    Attributs
    ─────────
    masque : np.ndarray (bool)
        Contrats retenus pour l'ajustement — ceux où un coût est OBSERVÉ.
    severite : np.ndarray
        cout_ecrete / nb_sinistres sur le masque : le coût PAR SINISTRE.
    seuil_ecretement : float
        Quantile des coûts au-delà duquel un sinistre est dit GRAVE. 0.0 si
        aucun coût observé.
    prime_grave_unitaire : float
        Charge écrêtée, mutualisée PAR UNITÉ D'EXPOSITION. ⚠ À RÉINJECTER dans
        la prime pure : sans elle, on écrête les graves du prix mais pas de la
        réalité — le tarif sous-estime la charge.
    n_retenus, n_graves : int
        Volumétrie, pour les rapports.
    """
    masque:               np.ndarray
    severite:             np.ndarray
    seuil_ecretement:     float
    prime_grave_unitaire: float
    n_retenus:            int
    n_graves:             int
    #: ⚠️⚠️ CONSTAT `socle/C1` — SUR QUOI LE SEUIL A RÉELLEMENT PORTÉ.
    #: `'par_sinistre'` quand le plan a déclaré une source de coûts par
    #: sinistre et qu'elle a été fournie ; `'total_contrat'` sinon. *Un seuil
    #: dont on ne sait pas sur quoi il porte ne peut pas être contesté.*
    assiette_seuil:       str = 'total_contrat'
    #: Contrats écrêtés dont le coût MOYEN par sinistre reste SOUS le seuil :
    #: leur total dépasse parce qu'ils sont NOMBREUX, pas parce qu'un sinistre
    #: est grave. `0` quand l'assiette est déjà `par_sinistre`.
    n_ecretes_par_nombre: int = 0
    #: Le seuil, exprimé en nombre de sinistres MOYENS — le chiffre le plus
    #: lisible du diagnostic. Mesuré le 01/09 : 7,3 sur le portefeuille réel
    #: versionné, mais **26,8 à 8 sinistres/contrat**. Il croît avec la
    #: fréquence : c'est la mesure même du défaut que `socle/C1` décrit.
    seuil_en_sinistres_moyens: float = 0.0
    #: ⚠️⚠️ D'OU VIENT LE SEUIL : `'declare'` quand le plan l'a pose,
    #: `'quantile'` quand il a ete calcule sur les couts observes. La
    #: distinction n'est pas cosmetique : dans le second cas, c'est LE
    #: PORTEFEUILLE QUI DEFINIT CE QUI, EN LUI, EST ANORMAL -- une hypothese,
    #: et elle doit se dire. Voir `phrase_seuil_suppose`.
    source_seuil: str = 'quantile'


def construire_cible_severite(
    cout_total,
    nb_sinistres,
    exposition,
    *,
    quantile_ecretement: float = 0.995,
    seuil: float | None = None,
    couts_par_sinistre=None,
) -> CibleSeverite:
    """E[coût PAR SINISTRE], écrêté, là où un coût est OBSERVÉ.

    TROIS décisions, réunies ici parce qu'elles sont indissociables — les
    séparer, c'est exactement ce qui a laissé les deux chemins diverger.

    1. CIBLE — `cout_ecrete / nb_sinistres`, le coût PAR SINISTRE, jamais le
       total. Un contrat à 3 sinistres a un coût total ≈ 3× celui d'un contrat
       à 1 sinistre : ajuster le total, c'est mélanger sévérité et FRÉQUENCE.
       Recombiné en prime pure avec E[N], le nombre est alors compté DEUX FOIS,
       et la pente du facteur de coût absorbe l'effet fréquence.
       Réf. : E[S] = E[N] × E[C | N>0] — la décomposition fréquence-sévérité.

    2. MASQUE — `(cout_ecrete > 0) & (nb_sinistres > 0)` : un coût OBSERVÉ, pas
       seulement un sinistre COMPTÉ. Sur données réelles (freMTPL2), ~9 100
       contrats ont ClaimNb > 0 SANS montant enregistré : leur sévérité vaudrait
       0 et casserait le Gamma (support strictement positif). La FRÉQUENCE, elle,
       garde tous les contrats — le comptage, lui, est observé.

    3. ÉCRÊTEMENT — au quantile `quantile_ecretement`. L'excédent n'est PAS jeté :
       il est mutualisé dans `prime_grave_unitaire`. Sans écrêtement, quelques
       sinistres graves pilotent seuls les relativités du Gamma ; sans
       réinjection, ils disparaissent du tarif. Les deux vont ensemble.

    Paramètres
    ──────────
    seuil : float, optionnel
        None  → le seuil est APPRIS sur ces données (portefeuille d'ajustement).
        float → le seuil FOURNI est appliqué, sans recalcul.
        ⚠ C'est le piège V9, payé cher : on apprend sur le TRAIN et on applique
        au TEST. Recalculer un seuil sur le test y ferait fuiter sa distribution.
    couts_par_sinistre : séquence de séquences, optionnel
        Les montants INDIVIDUELS, une séquence par contrat, dans l'ordre de
        `cout_total`. Fournie → **le seuil porte sur CHAQUE SINISTRE**, comme
        arbitré le 01/09/2026. Absente → l'assiette reste le TOTAL du contrat,
        et le diagnostic ci-dessous le dit.

        ⚠️⚠️ CONSTAT `socle/C1` — POURQUOI CE PARAMÈTRE EXISTE. La docstring de
        `seuil_ecretement` annonce « au-delà duquel **un sinistre** est dit
        GRAVE », et le code écrêtait le **total du contrat**. Mesuré le
        01/09/2026 sur `data/PG_2017_CLAIMS_YEAR0.csv` (12 391 sinistres
        versionnés, une ligne = un sinistre), sévérités réelles, fréquence
        balayée :

            sin./contrat   vrais graves   RATÉS par l'assiette « total »
                     1.1             37                               18
                     4.0            101                               76
                     8.0            198                              173

        **À 8 sinistres par contrat, l'assiette « total » rate 87 % des vrais
        sinistres graves** : elle n'écrête pas les graves, elle écrête les
        nombreux.

        ⚠️ ET AUCUN ESTIMATEUR NE RATTRAPE ÇA DEPUIS LA DONNÉE AU CONTRAT.
        Mesuré : le coût MOYEN par sinistre (`cout/nb`), seule forme calculable
        sans montants individuels, n'attrape que **25 des 193** graves à 8
        sinistres/contrat — la moyenne dilue le grave. *L'information du
        maximum n'est ni dans la somme, ni dans le compte.* D'où une SOURCE
        déclarée au plan, jamais une reconstruction.
    """
    cout = pd.to_numeric(pd.Series(cout_total), errors="coerce").astype(float).fillna(0.0)
    nb   = pd.to_numeric(pd.Series(nb_sinistres), errors="coerce").astype(float).fillna(0.0)
    expo = pd.to_numeric(pd.Series(exposition), errors="coerce").astype(float)

    # ── L'ASSIETTE DU SEUIL — constat `socle/C1`, arbitré le 01/09/2026 ──────
    par_sinistre = couts_par_sinistre is not None
    montants = None
    if par_sinistre:
        montants = [np.asarray(m, dtype=float) for m in couts_par_sinistre]
        if len(montants) != len(cout):
            raise ValueError(
                f"`couts_par_sinistre` porte {len(montants)} contrats et "
                f"`cout_total` en porte {len(cout)} : les deux sont alignés "
                f"POSITIONNELLEMENT, un décalage tarifierait le mauvais "
                f"contrat.")
        # ⚠️ LE CONTRAT DE DONNÉES SE VÉRIFIE, IL NE SE SUPPOSE PAS. Des
        # montants dont la somme ne fait pas le total du contrat signalent une
        # jointure fausse — et une jointure fausse écrêterait au hasard.
        somme = np.array([float(m.sum()) for m in montants])
        ecart = np.abs(somme - cout.to_numpy(dtype=float))
        pire = int(np.argmax(ecart)) if len(ecart) else 0
        if len(ecart) and ecart[pire] > max(1e-6, 1e-6 * abs(float(cout.iloc[pire]))):
            raise ValueError(
                f"`couts_par_sinistre` ne somme pas à `cout_total` : écart "
                f"maximal {ecart[pire]:,.4f} EUR sur un contrat à "
                f"{float(cout.iloc[pire]):,.2f} EUR. La jointure entre la "
                f"table des sinistres et celle des contrats est fausse.")

    # ⚠⚠ UN SEUIL DECLARE NE SE REPLIE JAMAIS SUR LE QUANTILE. Il etait
    # accepte sans aucune verification : un montant negatif ou nul traversait
    # `float(seuil)` puis desactivait silencieusement l'ecretement au `if
    # seuil > 0` -- l'actuaire aurait cru tarifer sous son traite de
    # reassurance pendant que le code n'ecretait rien.
    #   *Un seuil declare puis ignore en silence est pire que pas de seuil.*
    source_seuil = 'quantile' if seuil is None else 'declare'
    if seuil is not None:
        try:
            seuil_lu = float(seuil)
        except (TypeError, ValueError) as _e:
            raise ValueError(
                f"seuil de sinistre grave illisible : {seuil!r}. Aucun repli "
                f"sur le quantile n'est fait -- corrigez la declaration au "
                f"plan.") from _e
        if not np.isfinite(seuil_lu) or seuil_lu <= 0:
            raise ValueError(
                f"seuil de sinistre grave = {seuil_lu} : il doit etre "
                f"strictement positif et fini. Aucun repli sur le quantile "
                f"n'est fait.")
        seuil = seuil_lu
    if seuil is None:
        if par_sinistre:
            tous = np.concatenate(montants) if montants else np.empty(0)
            tous = tous[tous > 0]
            seuil = float(np.quantile(tous, quantile_ecretement)) if tous.size else 0.0
        else:
            seuil = (float(cout[cout > 0].quantile(quantile_ecretement))
                     if (cout > 0).any() else 0.0)
    seuil = float(seuil)

    if par_sinistre and seuil > 0:
        # CHAQUE sinistre est écrêté, jamais le cumul de l'année.
        cout_ecrete = pd.Series(
            [float(np.minimum(m, seuil).sum()) for m in montants],
            index=cout.index)
    else:
        cout_ecrete = cout.clip(upper=seuil) if seuil > 0 else cout
    charge_grave = float((cout - cout_ecrete).sum())
    total_expo = float(expo.sum())
    prime_grave_unitaire = charge_grave / total_expo if total_expo > 0 else 0.0

    masque = ((cout_ecrete > 0) & (nb > 0)).to_numpy()
    severite = (cout_ecrete.to_numpy()[masque] / nb.to_numpy()[masque]).astype(float) \
        if masque.any() else np.empty(0, dtype=float)

    # ── LE DIAGNOSTIC — il ne s'allume que sur l'assiette « total » ─────────
    cps = (cout / nb.replace(0.0, np.nan)) if seuil > 0 else None
    if par_sinistre:
        n_graves = int(sum(int((m > seuil).sum()) for m in montants)) if seuil > 0 else 0
        n_par_nombre = 0
    else:
        n_graves = int((cout > seuil).sum()) if seuil > 0 else 0
        # Écrêté alors que son coût MOYEN par sinistre reste sous le seuil :
        # le total ne dépasse que parce que les sinistres sont NOMBREUX.
        n_par_nombre = (int(((cout > seuil) & (cps <= seuil)).sum())
                        if seuil > 0 else 0)
    cout_moyen_sinistre = float(cps[cps.notna()].mean()) if cps is not None and cps.notna().any() else 0.0
    en_sinistres = (seuil / cout_moyen_sinistre) if cout_moyen_sinistre > 0 else 0.0

    return CibleSeverite(
        masque=masque,
        severite=severite,
        seuil_ecretement=seuil,
        prime_grave_unitaire=prime_grave_unitaire,
        n_retenus=int(masque.sum()),
        n_graves=n_graves,
        assiette_seuil='par_sinistre' if par_sinistre else 'total_contrat',
        source_seuil=source_seuil,
        n_ecretes_par_nombre=n_par_nombre,
        seuil_en_sinistres_moyens=round(float(en_sinistres), 2),
    )


def seuil_declare(plan) -> float | None:
    """Le montant du seuil grave déclaré au plan, ou ``None``.

    ⚠️ SOURCE UNIQUE POUR LES TROIS CHEMINS qui construisent une cible de
    sévérité (A3, `pipeline_tarifaire`, `pipeline_agents`). Trois lectures
    séparées de `plan.seuil_grave` finiraient par diverger — c'est
    exactement ce qui a laissé les deux GLM diverger.

    ⚠️ Elle ne valide RIEN : `SeuilGrave` refuse déjà à la construction, et
    `construire_cible_severite` refuse à l'usage. Une troisième validation
    ici serait une troisième vérité possible.
    """
    declare = getattr(plan, 'seuil_grave', None)
    return None if declare is None else float(declare.montant)


def phrase_seuil_suppose(cible: CibleSeverite, plan=None) -> str | None:
    """L'hypothèse du seuil d'écrêtement, DITE — jamais supposée en silence.

    ⚠️⚠️ SANS ELLE, LE PORTEFEUILLE DÉFINIT CE QUI, EN LUI, EST ANORMAL. Le
    seuil de gravité retombait toujours sur le quantile 0,995 des coûts
    observés. Or un seuil de sinistre grave est une donnée de RÉASSURANCE :
    il vient d'un traité, d'une politique de souscription, d'une note du
    client. Le calculer sur les données rend le tarif circulaire — un
    portefeuille très sinistré se donne un seuil élevé, donc écrête peu, donc
    charge la prime pure de sinistres que le traité aurait pris.

    ⚠️ Même forme que `phrase_chargements_non_declares` : elle ne s'ajoute
    QUE si rien n'est déclaré. *Un avertissement permanent est un
    avertissement qu'on cesse de lire.*

    Rend `None` quand le plan a déclaré son seuil : il n'y a plus
    d'hypothèse à signaler.
    """
    if cible is None or getattr(cible, 'source_seuil', '') != 'quantile':
        return None
    if cible.seuil_ecretement <= 0:
        return None
    lob = getattr(plan, 'lob', None) or '?'
    return (
        f"SEUIL DE SINISTRE GRAVE NON DECLARE au plan '{lob}' : le seuil "
        f"d'ecretement a ete SUPPOSE — quantile des couts observes, soit "
        f"{cible.seuil_ecretement:,.0f} EUR, sur l'assiette "
        f"'{cible.assiette_seuil}'. C'est le portefeuille qui definit ici ce "
        f"qui, en lui, est anormal. Le vrai seuil vient de votre traite de "
        f"reassurance ou de votre politique de souscription : declarez "
        f"`seuil_grave` au plan (montant, assiette, source)."
    )


def phrase_aucun_grave(cible: CibleSeverite) -> str | None:
    """Aucun sinistre au-dessus du seuil : la prime grave vaut 0, et on le dit.

    ⚠️⚠️ ZERO EST ICI UNE MESURE, PAS UNE ABSENCE — et c'est exactement pour
    cela qu'il faut l'écrire. Une prime grave nulle publiée sans phrase est
    indiscernable d'un écrêtement qui n'a pas tourné. *L'actuaire doit
    pouvoir distinguer « aucun grave observé » de « le calcul n'a rien
    produit ».*

    Ne s'allume que sur un seuil réellement posé : sans seuil, il n'y a rien
    à dire.
    """
    if cible is None or cible.seuil_ecretement <= 0:
        return None
    if cible.n_graves:
        return None
    origine = ('declare au plan' if getattr(cible, 'source_seuil', '') ==
               'declare' else 'suppose (quantile des couts observes)')
    return (
        f"AUCUN SINISTRE GRAVE — aucun cout n'atteint le seuil de "
        f"{cible.seuil_ecretement:,.0f} EUR ({origine}, assiette "
        f"'{cible.assiette_seuil}'). La prime de charge grave vaut donc 0,00 "
        f"EUR par unite d'exposition : c'est une MESURE, pas un calcul "
        f"absent. Si ce seuil vous parait haut pour ce portefeuille, c'est "
        f"la declaration qu'il faut revoir, pas le tarif."
    )


def synthese_assiette_ecretement(cible: CibleSeverite) -> str | None:
    """SOURCE UNIQUE — ce que l'actuaire doit lire sur l'assiette du seuil.

    ⚠️⚠️ CONSTAT `socle/C1`, ARBITRÉ LE 01/09/2026. Tant qu'aucun plan ne
    déclare de source de coûts par sinistre, l'assiette reste le TOTAL du
    contrat — **et le rapport doit dire combien de contrats sont écrêtés parce
    que NOMBREUX plutôt que vraiment GRAVES.** Sans cette phrase, l'écrêtement
    de la fréquence passe pour un écrêtement de la sévérité.

    ⚠️ La phrase ne s'allume QUE sur l'assiette « total », et seulement s'il y
    a quelque chose à dire : *un avertissement permanent est un avertissement
    qu'on cesse de lire.* Sur l'assiette « par sinistre », il n'y a rien à
    signaler — le seuil porte sur ce que son nom annonce.
    """
    if cible is None or cible.seuil_ecretement <= 0:
        return None
    if cible.assiette_seuil == 'par_sinistre':
        return None
    if not cible.n_ecretes_par_nombre:
        return None
    part = cible.n_ecretes_par_nombre / max(cible.n_graves, 1)
    return (
        f"⚠ ASSIETTE DE L'ÉCRÊTEMENT — le seuil porte sur le COÛT TOTAL du "
        f"contrat, pas sur chaque sinistre. {cible.n_ecretes_par_nombre} "
        f"contrat(s) sur {cible.n_graves} écrêté(s) ({part:.0%}) le sont parce "
        f"qu'ils sont NOMBREUX : leur coût moyen par sinistre reste SOUS le "
        f"seuil. Celui-ci vaut {cible.seuil_en_sinistres_moyens:.1f} sinistres "
        f"moyens — plus la fréquence est élevée, plus il écrête le NOMBRE au "
        f"lieu de la GRAVITÉ. Pour que le seuil porte sur chaque sinistre, "
        f"déclarez `cout_par_sinistre` au plan et fournissez les montants "
        f"individuels."
    )
