"""
sp_contrats.py — lire ce qu'un agent publie vraiment, et non ce qu'on suppose.

LE DÉFAUT QUE CE MODULE FERME (D39, D14)
Un relevé croisé des clés lues par les modules de rapport et des clés réellement
produites par les agents en a trouvé **29 qui n'existaient dans aucun contrat de
sortie**. Toutes portaient un repli numérique : elles échouaient donc en silence,
et la valeur publiée était le repli, jamais la donnée.

Trois de ces clés coûtaient cher :

  `alm['lcr']`      lu comme un nombre alors que SP-ALM publie un DICTIONNAIRE.
                    `float({...})` lève `TypeError`, non rattrapé : le rapport
                    Prévoyance sortait en **HTML de 106 octets et Word de 0
                    octet** — et seulement quand la chaîne allait jusqu'au bout,
                    puisque le crash exige que le résultat ALM soit fourni.
                    Plus la chaîne était complète, moins le document existait.

  `s3['mcr']`       S3 publie `mcr_sante`. Le rapport Santé affichait donc un
                    **MCR de 0 €** par repli silencieux.

  `risk_adjustment_p3`  jamais produit par P3 : le repli à 6 % du BE de P4
                    s'appliquait dans 100 % des exécutions, contrairement à ce
                    qu'annonçait son propre commentaire.

LE PRINCIPE
Une lecture rend toujours un COUPLE `(valeur, trouvee)`. Un appelant qui veut
savoir si la donnée existait peut le savoir ; un appelant qui s'en moque garde
une ligne courte. Ce qui disparaît, c'est le troisième cas — celui où la valeur
manque et où personne ne l'apprend.
"""

__all__ = ["lire_alm", "lire_nombre", "lire_premiere_cle", "valeur_qrt"]


def _nombre(valeur, defaut=0.0):
    """Convertit en flottant sans jamais lever, y compris sur un dictionnaire."""
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return defaut


def lire_nombre(source, cle, defaut=0.0):
    """Lit une valeur numérique et dit si la clé existait.

    Returns
    -------
    (float, bool) : la valeur, et `True` si la clé était présente ET convertible.
    """
    source = source or {}
    if cle not in source:
        return defaut, False
    brut = source[cle]
    valeur = _nombre(brut, None)
    if valeur is None:
        return defaut, False
    return valeur, True


def lire_premiere_cle(source, *cles, defaut=0.0):
    """Lit la première clé présente parmi plusieurs orthographes possibles.

    Sert aux contrats dont le nom a changé : on cherche le nom canonique
    d'abord, l'ancien ensuite, et on rend AUSSI le nom effectivement trouvé,
    pour qu'un rapport puisse dire d'où vient son chiffre.

    Returns
    -------
    (float, str | None) : la valeur, et le nom de la clé retenue (None si aucune).
    """
    source = source or {}
    for cle in cles:
        valeur, trouvee = lire_nombre(source, cle, defaut=None)
        if trouvee:
            return valeur, cle
    return defaut, None


def lire_alm(alm):
    """Aplatit le contrat imbriqué de SP-ALM en grandeurs directement affichables.

    SP-ALM publie `duration`, `bv01`, `lcr` et `gap` comme des SOUS-DICTIONNAIRES.
    Les modules de rapport les lisaient comme des scalaires de premier niveau :
    d'où un repli à 0 pour les durations, et une `TypeError` fatale sur le LCR.

    Cette fonction lit la structure réelle, ne lève jamais, et expose
    `disponible` pour qu'un rapport puisse écrire « ALM non fournie » au lieu
    d'afficher des zéros qu'un lecteur prendrait pour des mesures.
    """
    alm = alm or {}
    duration = alm.get("duration") or {}
    bv01 = alm.get("bv01") or {}
    lcr = alm.get("lcr") or {}
    gap = alm.get("gap") or {}

    return {
        "duration_actif":     _nombre(duration.get("actif")),
        "duration_passif":    _nombre(duration.get("passif")),
        "duration_modifiee":  _nombre(duration.get("actif_modifiee")),
        "duration_rentes_ip": _nombre(duration.get("passif_rentes_ip")),
        "gap_duration":       _nombre(duration.get("gap")),
        "statut_gap":         duration.get("statut_gap") or gap.get("statut") or "—",

        "lcr_ratio":          _nombre(lcr.get("lcr_ratio")),
        "lcr_conforme":       bool(lcr.get("conforme", False)),
        "lcr_reference":      lcr.get("reference") or "Art. L212-7 CSS",

        "bv01_net":           _nombre(bv01.get("bv01_net")),
        "bv01_actif":         _nombre(bv01.get("bv01_actif")),
        "bv01_passif":        _nombre(bv01.get("bv01_passif")),
        "impact_100bp":       _nombre(bv01.get("impact_100bp")),
        "impact_200bp":       _nombre(bv01.get("impact_200bp")),

        "redington_ok":       alm.get("redington_ok"),
        "statut_rag":         alm.get("statut_rag") or "—",

        # Permet au gabarit de dire « non fournie » plutot que d afficher
        # des zeros qu un lecteur prendrait pour des mesures.
        "disponible":         bool(duration or lcr or bv01),
    }


def valeur_qrt(qrt, code_ligne, colonne, defaut=None):
    """Lit une ligne de QRT par son CODE, jamais par son rang.

    LE DEFAUT FERME (D24)
    `pa_sante = qrt_s13["lignes"][-1][...]` attrapait la valeur par la DERNIERE
    LIGNE du QRT. Toute ligne ajoutee -- un total, une ligne de controle, une
    ventilation supplementaire -- deplacait la lecture sans la moindre erreur.
    Planté : en ajoutant une ligne « Total » en fin de QRT, `pa_sante` devenait
    ce total, le consolide etait faux, et AUCUNE exception n etait levee.
    Le producteur ne garantissait par ailleurs aucun ordre : les lignes sont
    construites par appends successifs, sans contrat ni test le verrouillant.

    Returns
    -------
    (valeur, trouvee) : `trouvee` vaut False si le code est absent -- la
    fonction DIT qu elle n a pas trouve au lieu d inventer un zero.
    """
    for ligne in (qrt or {}).get("lignes", []):
        if str(ligne.get("code", "")).strip() == str(code_ligne).strip():
            if colonne in ligne:
                return ligne[colonne], True
            return defaut, False
    return defaut, False
