# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §99 b) : LE RAPPROCHEMENT BOUCLE SUR LE BILAN
=============================================================================

§99 b), verbatim : « présenter pour chaque rapprochement LES VALEURS
COMPTABLES NETTES À L'OUVERTURE ET À LA CLÔTURE de la période, ventilées en
un total pour les portefeuilles de contrats d'assurance qui sont des ACTIFS
et un total pour les portefeuilles de contrats d'assurance qui sont des
PASSIFS, CES VALEURS ÉTANT ÉGALES AUX MONTANTS PRÉSENTÉS DANS L'ÉTAT DE LA
SITUATION FINANCIÈRE EN APPLICATION DU PARAGRAPHE 78. »

⚠️⚠️ CE N'EST PAS UNE RECOMMANDATION, C'EST UNE ÉGALITÉ EXIGÉE — et c'est la
seule articulation du bloc des annexes qui soit entièrement calculable. Elle
ferme la faille que ce dépôt nomme depuis quatre modules : « deux états
produits séparément peuvent chacun boucler sur eux-mêmes et se contredire
entre eux ». Le rapprochement descend du magasin de clôtures, le bilan
descend de la mesure ; rien ne les obligeait à dire la même chose.

⚠️⚠️ ET LA COMPARAISON PORTE SUR DEUX TOTAUX, JAMAIS SUR LE NET. Le net
boucle trivialement : la somme signée des soldes vaut toujours
« passifs − actifs », quelle que soit la ventilation. ⚠️ Comparer le net
serait donc la faute exacte que `bilan` refuse déjà — « un bilan dont le
total est juste et dont les deux lignes sont fausses, une erreur qu'aucun
contrôle d'équilibre ne verrait, puisque l'équilibre tient ». Mesuré : un
portefeuille passé du bon côté à l'autre laisse le net inchangé.

⚠️ LA VENTILATION EST FAITE PAR `bilan.ventiler_par_cote`, PAS RECOPIÉE.
Comparer deux états exige de les ventiler avec LA MÊME règle ; deux règles
proches feraient lire une divergence de méthode comme une divergence de
montants.

⚠️ CE QUE CE MODULE NE PEUT PAS VÉRIFIER, ET IL LE REFUSE PLUTÔT QUE DE LE
TAIRE : le rapprochement de la RÉASSURANCE DÉTENUE. §98 en exige un séparé,
et §99 b) veut qu'il boucle sur le §78 — mais §78 c) et d) ne sont pas
construits, `Bilan` n'a aucun champ pour eux. Boucler le cédé sur un bilan
qui ne le porte pas donnerait un zéro qui passerait pour un accord.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §78, §98, §99 b), §100.
=============================================================================
"""

from normes.ifrs17.mesure.bilan import ventiler_par_cote
from normes.ifrs17.mesure.lrc_paa import RefusMesure

MOTIF_ARTICULATION_99B = 'rapprochement_99b_discordant_du_bilan'
MOTIF_CEDE_SANS_BILAN = 'reassurance_detenue_sans_ligne_de_bilan'
MOTIF_AUCUN_SOLDE_RAPPROCHE = 'rapprochement_sans_solde'

#: ⚠️ MÊME BORNE QUE L'ARTICULATION DU §80 ET QUE L'EXTINCTION DU §56. Ces
#: deux totaux sont les MÊMES montants lus par deux chemins : le seul écart
#: légitime est l'erreur de virgule flottante. Un écart de présentation se
#: déclare — il ne se tolère pas.
TOLERANCE = 1e-6

#: ⚠️⚠️ POURQUOI LE CÉDÉ EST REFUSÉ ET NON RENDU À ZÉRO. Le motif est le même
#: que celui de `bilan` : deux lignes ABSENTES ne valent pas zéro, et un état
#: à deux lignes lu comme complet ferait conclure qu'il n'y a pas de
#: réassurance. Ici la faute serait pire : l'accord serait CONSTATÉ.
RESERVE_DU_CEDE = (
    "⚠️ LE RAPPROCHEMENT DE LA RÉASSURANCE DÉTENUE NE PEUT PAS BOUCLER "
    "AUJOURD'HUI. §98 en exige un séparé et §99 b) veut qu'il soit égal au "
    "§78 ; or §78 c) et d) — les portefeuilles de réassurance détenue qui "
    "sont des actifs et ceux qui sont des passifs — ne sont pas construits. "
    "⚠️ CE N'EST PAS LA MESURE QUI MANQUE, C'EST LA LIGNE DE BILAN : la "
    "réassurance détenue est mesurée par ailleurs (§60-70A).")


def _totaux(soldes) -> tuple[float, float]:
    """Les deux totaux du §78, par la règle du §78 et non par une copie."""
    actifs, passifs = ventiler_par_cote(soldes)
    return (sum(p.valeur for p in actifs), sum(p.valeur for p in passifs))


def verifier_articulation_99b(*, soldes_du_rapprochement, bilan,
                              nature_du_rapprochement: str,
                              nature_emise: str) -> str:
    """§99 b) — le rapprochement et le bilan disent-ils la même chose ?

    ⚠️ `soldes_du_rapprochement` PORTE LES VALEURS COMPTABLES NETTES DE
    CLÔTURE, un `SoldeGroupe` par groupe — c'est-à-dire la somme des quatre
    soldes du §100 pour ce groupe. Le portefeuille y est un CHAMP DÉCLARÉ,
    jamais lu dans la clé du groupe : parser une clé pour en tirer un
    portefeuille reviendrait à supposer un format, et la ligne de bilan où
    un groupe atterrit ne se devine pas.

    ⚠️ `nature_emise` EST PASSÉE EN PARAMÈTRE pour que ce module n'importe
    pas le socle : la mesure reçoit des valeurs nommées, jamais un objet du
    magasin. Même règle que le verdict du §53 et que le contexte.
    """
    if nature_du_rapprochement != nature_emise:
        raise RefusMesure(MOTIF_CEDE_SANS_BILAN, RESERVE_DU_CEDE)
    lot = list(soldes_du_rapprochement)
    if not lot:
        raise RefusMesure(
            MOTIF_AUCUN_SOLDE_RAPPROCHE,
            "aucun solde de rapprochement fourni. Un accord constaté sur un "
            "ensemble vide le serait trivialement — c'est la faute de la "
            "gate rendant « Ran 0 tests » en sortant 0.")

    actifs, passifs = _totaux(lot)
    ecarts = []
    if abs(actifs - bilan.total_actifs) > TOLERANCE:
        ecarts.append(f"ACTIFS : rapprochement {actifs:.2f}, bilan "
                      f"{bilan.total_actifs:.2f} "
                      f"(écart {actifs - bilan.total_actifs:+.2f})")
    if abs(passifs - bilan.total_passifs) > TOLERANCE:
        ecarts.append(f"PASSIFS : rapprochement {passifs:.2f}, bilan "
                      f"{bilan.total_passifs:.2f} "
                      f"(écart {passifs - bilan.total_passifs:+.2f})")
    if ecarts:
        net_r, net_b = passifs - actifs, (bilan.total_passifs
                                          - bilan.total_actifs)
        muet = ' ⚠️ ET LE NET, LUI, BOUCLE — c\'est exactement ce qu\'un ' \
               'contrôle d\'équilibre aurait laissé passer.' \
            if abs(net_r - net_b) <= TOLERANCE else ''
        raise RefusMesure(
            MOTIF_ARTICULATION_99B,
            f"le rapprochement du §100 et l'état du §78 ne disent pas la "
            f"même chose sur {len(ecarts)} des deux totaux — "
            + ' · '.join(ecarts) + '.' + muet
            + " ⚠️ §99 b) EXIGE L'ÉGALITÉ, pas la vraisemblance : « ces "
              "valeurs étant ÉGALES aux montants présentés dans l'état de "
              "la situation financière en application du paragraphe 78 ». "
              "Un écart signale que deux états produits séparément se "
              "contredisent — chacun peut boucler sur lui-même et rester "
              "faux.")

    return (f"§99 b) — le rapprochement boucle sur l'état du §78 : "
            f"{len(lot)} groupe(s) ventilés sur "
            f"{bilan.nb_portefeuilles} portefeuille(s), actifs "
            f"{actifs:.2f} et passifs {passifs:.2f}. ⚠️ LA COMPARAISON PORTE "
            f"SUR LES DEUX TOTAUX, JAMAIS SUR LE NET : la somme signée "
            f"boucle toujours, quelle que soit la ventilation, et un "
            f"portefeuille passé du mauvais côté ne s'y verrait pas. "
            f"⚠️ CE QUI N'EST PAS ÉTABLI ICI : le rapprochement de la "
            f"réassurance détenue, faute des lignes §78 c) et d). "
            + RESERVE_DU_CEDE)
