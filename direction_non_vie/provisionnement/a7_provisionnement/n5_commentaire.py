# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n5_commentaire.py  —  Commentaire narratif style actuaire senior
# =============================================================================
#
#  Le commentaire est le coeur différenciateur d'ActuarIA vs tous les
#  concurrents (ResQ, Excel, cabinets). Il ne résume pas les chiffres —
#  il les interprète, les contextualise, les questionne et recommande.
#
#  Structure en 8 sections (style rapport actuaire désigné ACPR) :
#
#  §1  Contexte et périmètre de l'analyse
#  §2  Qualité des données et du triangle
#  §3  Validation des hypothèses actuarielles — diagnostic complet
#  §4  Analyse des méthodes et convergence
#  §5  Best Estimate S2 — analyse et positionnement
#  §6  Incertitude de réserve et distribution stochastique
#  §7  SCR provisions et exigences S2
#  §8  Recommandations opérationnelles et points de vigilance
#
#  Deux modes de génération :
#
#  Mode "statique" (défaut) :
#    Narration structurée générée en Python, très complète et experte,
#    sans appel API externe. Toujours disponible.
#
#  Mode "LLM" (optionnel, si api_key fourni) :
#    Enrichissement de la narration statique par Claude Sonnet.
#    Le LLM reçoit les données structurées et produit une narration
#    encore plus fluide, avec des formulations plus naturelles.
#    Le mode statique reste la base — le LLM est un enrichissement.
#
# =============================================================================

import logging
from datetime import datetime
from typing import Dict, Optional

from .n2_hypotheses_bfcc import lignes_hypotheses_bfcc
from .n3.bf_cape_cod import libelle_loss_ratio
from .n4_best_estimate import s2_non_calculable, MSG_S2_NON_CALCULABLE

logger = logging.getLogger('actuaria.a7')


# =============================================================================
#  UTILITAIRES DE FORMATAGE
# =============================================================================

def _e(v) -> str:
    """Formater un montant en euros."""
    if v is None or (isinstance(v, float) and v != v):
        return "—"
    return f"{float(v):,.0f} €".replace(",", "\u202f")


def _p(v, d=1) -> str:
    """Formater un pourcentage."""
    if v is None:
        return "—"
    return f"{float(v):.{d}f}%"


def _statut_txt(s) -> str:
    if s == 'VERT':  return "CONFORME"
    if s == 'AMBRE': return "A SURVEILLER"
    return "ATTENTION"


def _qualif_ecart(ecart_pct: float) -> str:
    """Qualifier un écart inter-méthodes."""
    if ecart_pct < 3:
        return "remarquable — les méthodes convergent vers une estimation robuste"
    if ecart_pct < 7:
        return "satisfaisante — niveau de dispersion habituel sur ce type de portefeuille"
    if ecart_pct < 15:
        return "acceptable mais à surveiller — réviser les hypothèses de l'a priori BF"
    return "préoccupante — divergence significative nécessitant une analyse approfondie"


# =============================================================================
#  SECTION 1 — CONTEXTE ET PÉRIMÈTRE
# =============================================================================

def _s1_contexte(n1: Dict, n2: Dict, n3: Dict, lob: str, lob_label: str) -> str:
    taille     = n1.get('taille', '—')
    mode       = n1.get('mode_detecte', '—')
    n_ann      = n1.get('n_annees', 0)
    n_dev      = n1.get('n_dev', 0)
    methode_cl = n3.get('methode_cl', '—')
    methode_rec= n2.get('methode_recommandee', '—')
    date_str   = datetime.now().strftime('%d %B %Y')

    mode_desc = {
        'cumule':     "triangle déjà cumulé fourni directement",
        'non_cumule': "triangle incrémental converti en cumulé automatiquement",
        'brutes':     "sinistres individuels agrégés en triangle de développement",
    }.get(mode, mode)

    lignes = [
        f"Le présent rapport porte sur l'analyse actuarielle du provisionnement",
        f"Non-Vie arrêtée au {date_str}, branche : {lob_label}.",
        "",
        f"Le triangle de développement analysé couvre {n_ann} années de survenance",
        f"et {n_dev} périodes de développement ({taille}, {mode_desc}).",
        f"La méthode Chain Ladder retenue pour ce calcul est la variante",
        f"'{methode_cl}', sélectionnée automatiquement sur la base de",
        f"l'analyse des hypothèses actuarielles de Mack (1993).",
        f"La méthode principale recommandée par l'analyse N2 est",
        f"'{methode_rec.replace('_', ' ').title()}'.",
    ]

    alertes_n1 = n1.get('alertes', [])
    if alertes_n1:
        lignes += [
            "",
            f"QUALITÉ DES DONNÉES : {len(alertes_n1)} point(s) d'attention identifié(s)",
            "lors de l'ingestion du triangle. Ces points sont détaillés à la section §2.",
        ]

    return "\n".join(lignes)


# =============================================================================
#  SECTION 2 — QUALITÉ DES DONNÉES
# =============================================================================

def _s2_qualite(n1: Dict) -> str:
    statut   = n1.get('statut', 'AMBRE')
    alertes  = n1.get('alertes', [])
    infos    = n1.get('infos', [])
    taille   = n1.get('taille', '—')
    n_ann    = n1.get('n_annees', 0)
    n_dev    = n1.get('n_dev', 0)

    statut_desc = {
        'VERT':  "Le triangle présente une qualité satisfaisante. "
                 "Aucune anomalie bloquante n'a été détectée.",
        'AMBRE': "Le triangle présente des irrégularités mineures qui "
                 "méritent attention mais ne remettent pas en cause "
                 "la fiabilité globale des calculs.",
        'ROUGE': "ATTENTION — Le triangle présente des anomalies significatives "
                 "qui peuvent affecter la fiabilité des résultats. "
                 "Une vérification approfondie des données source est indispensable.",
    }.get(statut, "")

    lignes = [statut_desc, ""]

    if n_ann < 5:
        lignes.append(
            f"AVERTISSEMENT : Avec seulement {n_ann} années de survenance, "
            f"le triangle est de petite taille. Les estimations sur les "
            f"premières colonnes reposent sur peu d'observations — "
            f"les résultats doivent être interprétés avec prudence. "
            f"Un trianglestandard de marché couvre 10 à 15 années."
        )
    elif n_ann >= 15:
        lignes.append(
            f"Le triangle de {n_ann} années est de taille confortable "
            f"et permet une estimation robuste des facteurs de développement "
            f"sur l'ensemble des colonnes."
        )

    if n_dev < n_ann:
        lignes.append(
            f"Le triangle est rectangulaire ({taille}) : "
            f"{n_dev} périodes de développement disponibles pour {n_ann} années. "
            f"Le tail factor est particulièrement important dans ce cas "
            f"pour compenser le développement résiduel non observé."
        )

    for a in alertes[:6]:
        clean = a.encode('ascii', 'ignore').decode('ascii').strip()
        if clean:
            lignes.append(f"• {clean}")

    if not alertes:
        lignes.append(
            "Aucune alerte sur la qualité des données. "
            "Le triangle est propre et directement exploitable."
        )

    return "\n".join(lignes)


# =============================================================================
#  SECTION 3 — VALIDATION DES HYPOTHÈSES
# =============================================================================

def _s3_hypotheses(n2: Dict) -> str:
    h1  = n2.get('h1_independance',     {})
    h2  = n2.get('h2_stabilite',        {})
    h4  = n2.get('h4_homosc_bootstrap', {})
    rec = n2.get('methode_recommandee', '—')
    rcl = n2.get('raison_cl', '')
    rr  = n2.get('raison_recommandation', '')

    lignes = []

    # ── H1 ────────────────────────────────────────────────────────────────────
    h1_ok   = h1.get('ok', True)
    corr    = h1.get('corr_moy', 0)
    n_sig   = h1.get('n_colonnes_sig', 0)
    n_test  = h1.get('n_colonnes_testees', 0)
    seuil   = h1.get('seuil_utilise', 0.50)

    if h1_ok:
        lignes.append(
            f"H1 — INDÉPENDANCE (Mack 1993) : VALIDÉE [score {h1.get('score',0)}/100]"
        )
        lignes.append(
            f"La corrélation de Spearman moyenne entre facteurs de colonnes "
            f"consécutives est de {corr:.2f}, inférieure au seuil {seuil:.2f}. "
            f"Sur {n_test} paires testées, aucune ne présente de dépendance "
            f"statistiquement significative. L'hypothèse fondamentale de Mack "
            f"est respectée : les années de survenance se développent "
            f"indépendamment les unes des autres. Cette validation autorise "
            f"l'utilisation du Chain Ladder et de Mack comme méthodes principales."
        )
    else:
        lignes.append(
            f"H1 — INDÉPENDANCE (Mack 1993) : REJETÉE [score {h1.get('score',0)}/100]"
        )
        lignes.append(
            f"La corrélation de Spearman moyenne de {corr:.2f} dépasse le seuil "
            f"{seuil:.2f}. {n_sig} paire(s) de colonnes sur {n_test} testées "
            f"présentent une dépendance statistiquement significative (p < 0.05). "
            f"Cela signifie que certaines années de survenance ont un comportement "
            f"systématiquement différent des autres — une mauvaise ou bonne année "
            f"tend à l'être sur plusieurs périodes de développement. "
            f"Dans ce contexte, les estimateurs Chain Ladder et Mack sont biaisés "
            f"et doivent être utilisés avec prudence, voire remplacés par "
            f"Bornhuetter-Ferguson ou Cape Cod qui s'ancrent sur un a priori "
            f"indépendant du triangle."
        )

    lignes.append("")

    # ── H2 ────────────────────────────────────────────────────────────────────
    h2_ok  = h2.get('ok', True)
    cv     = h2.get('cv_moy', 0)
    derive = h2.get('derive_moy', 0)
    s_cv   = h2.get('seuil_cv', 0.15)
    s_der  = h2.get('seuil_derive', 0.20)

    if h2_ok:
        lignes.append(
            f"H2 — STABILITÉ DES FACTEURS : VALIDÉE [score {h2.get('score',0)}/100]"
        )
        lignes.append(
            f"Le coefficient de variation moyen des facteurs de développement "
            f"est de {_p(cv*100)} (seuil branche : {_p(s_cv*100)}), "
            f"et la dérive temporelle est de {_p(derive*100)} "
            f"(seuil : {_p(s_der*100)}). "
            f"Les facteurs sont stables dans le temps : "
            f"les années récentes se développent de la même façon que les "
            f"années anciennes. Cette stabilité est un prérequis fondamental "
            f"pour la fiabilité des projections Chain Ladder."
        )
    else:
        ok_cv    = h2.get('ok_cv', True)
        ok_der   = h2.get('ok_derive', True)
        cause    = []
        if not ok_cv:
            cause.append(f"CV élevé ({_p(cv*100)} > {_p(s_cv*100)})")
        if not ok_der:
            cause.append(f"dérive temporelle ({_p(derive*100)} > {_p(s_der*100)})")

        lignes.append(
            f"H2 — STABILITÉ DES FACTEURS : REJETÉE [score {h2.get('score',0)}/100]"
        )
        lignes.append(
            f"Cause(s) : {' et '.join(cause)}. "
        )
        if not ok_cv:
            lignes.append(
                f"Le CV de {_p(cv*100)} révèle une forte hétérogénéité des "
                f"facteurs entre années de survenance — certaines années se "
                f"développent beaucoup plus vite que d'autres pour la même "
                f"période. La méthode médiane ou trimmed_mean est plus robuste "
                f"dans ce contexte car elle n'est pas influencée par les "
                f"facteurs aberrants."
            )
        if not ok_der:
            lignes.append(
                f"La dérive de {_p(derive*100)} indique une évolution "
                f"systématique des facteurs dans le temps — les facteurs "
                f"récents diffèrent significativement des facteurs anciens. "
                f"Cela peut refléter une évolution du portefeuille (mix produits, "
                f"pratiques de règlement, inflation) ou un changement "
                f"réglementaire. La pondération volume favorise les facteurs "
                f"récents dans ce cas."
            )

    lignes.append("")

    # ── BFCC-H1..H5 — les hypothèses propres à BF et Cape Cod ─────────────────
    # L'ancienne « H3 a priori BF » vivait ici. Elle lisait `n2['h3_apriori_bf']`,
    # dont le loss ratio était calculé sur la dernière cellule OBSERVÉE et non
    # sur l'ultime, et pouvait provenir d'un proxy inventé quand aucune prime
    # n'était fournie. Les cinq verdicts la remplacent, sur le loss ratio que N3
    # emploie réellement.
    lignes.append("HYPOTHÈSES PROPRES À BORNHUETTER-FERGUSON ET CAPE COD")
    for ligne in lignes_hypotheses_bfcc(n2):
        lignes.append(f"{ligne['libelle']} : {ligne['statut']}")
        lignes.append(ligne['message'])

    recoupement = n2.get('bfcc', {}).get('recoupement_lr', {})
    if recoupement.get('comparable'):
        lignes.append(recoupement['message'])

    # ── H4 ────────────────────────────────────────────────────────────────────
    h4_ok = h4.get('ok', True)
    phi   = h4.get('phi', 0)
    cv_v  = h4.get('cv_var', 0)

    lignes.append(
        f"H4 — HOMOSCÉDASTICITÉ (Bootstrap ODP) : "
        f"{'VALIDÉE' if h4_ok else 'HÉTÉROSCÉDASTICITÉ DÉTECTÉE'} "
        f"[score {h4.get('score',0)}/100]"
    )

    lignes.append(
        f"Le facteur de sur-dispersion φ = {phi:.6f} "
        f"et le CV des variances est de {cv_v:.2f}. "
    )

    if h4_ok:
        lignes.append(
            f"La variance des résidus est homogène entre colonnes (CV < 1.0). "
            f"Le modèle Bootstrap ODP (England & Verrall 2002) est "
            f"applicable — les résidus de Pearson sont rééchantillonnables "
            f"de façon fiable. Les percentiles P90 et P99.5 sont robustes."
        )
    else:
        lignes.append(
            f"L'hétéroscédasticité détectée signifie que la variance des "
            f"résidus n'est pas constante entre colonnes. Le Bootstrap ODP "
            f"est moins fiable dans ce contexte — les intervalles de confiance "
            f"doivent être interprétés avec prudence. "
            f"Privilégier l'incertitude Mack (σ) pour le SCR provisions."
        )

    lignes += [
        "",
        f"DÉCISION MÉTHODOLOGIQUE : {rr}",
        f"Variante CL : {rcl}",
    ]

    return "\n".join(lignes)


# =============================================================================
#  SECTION 4 — ANALYSE DES MÉTHODES
# =============================================================================

def _s4_methodes(n3: Dict, n4: Dict) -> str:
    cl   = n3['chain_ladder']
    mack = n3['mack']
    bf   = n3['bf']
    cc   = n3['cape_cod']
    boot = n3.get('bootstrap', {})
    tail = cl.get('tail_factor', {})

    cl_r  = cl.get('reserve_totale', 0)
    mk_r  = mack.get('reserve_best_estimate', 0)
    bf_r  = bf.get('reserve_totale', 0)
    cc_r  = cc.get('reserve_totale', 0)
    be    = n4.get('best_estimate', 0)

    methodes_all = {'Chain Ladder': cl_r, 'Mack 1993': mk_r, 'BF': bf_r, 'Cape Cod': cc_r}
    r_max  = max(methodes_all.values())
    r_min  = min(methodes_all.values())
    r_moy  = sum(methodes_all.values()) / len(methodes_all)
    cv_all = abs(r_max - r_min) / r_moy * 100 if r_moy > 0 else 0

    methodes_inc = n4.get('methodes_incluses', [])
    methodes_exc = n4.get('methodes_exclues', [])
    poids        = n4.get('poids', {})

    label_map = {
        'chain_ladder':'Chain Ladder', 'mack':'Mack 1993',
        'bornhuetter_ferguson':'Bornhuetter-Ferguson', 'cape_cod':'Cape Cod',
    }

    lignes = [
        f"Quatre méthodes actuarielles ont été calculées :",
        f"  • Chain Ladder ({cl.get('methode','').split('(')[1].rstrip(')') if '(' in cl.get('methode','') else 'standard'}) : {_e(cl_r)}",
        f"  • Mack 1993 (stochastique)                         : {_e(mk_r)}",
        f"  • Bornhuetter-Ferguson (LR={libelle_loss_ratio(bf)}, {bf.get('source_lr','—')}) : {_e(bf_r)}",
        f"  • Cape Cod (LR_CC={libelle_loss_ratio(cc, 'lr_cape_cod')})                    : {_e(cc_r)}",
        "",
    ]

    # ── Convergence ──────────────────────────────────────────────────────────
    lignes.append(
        f"La fourchette des estimations s'étend de {_e(r_min)} à {_e(r_max)}, "
        f"soit un écart de {_p(cv_all)} de la moyenne. "
        f"Cette convergence est {_qualif_ecart(cv_all)}."
    )

    ecart_cl_bf = abs(cl_r - bf_r) / max(cl_r, 1e-9) * 100
    if ecart_cl_bf > 10:
        lignes.append(
            f"L'écart CL/BF de {_p(ecart_cl_bf)} mérite une attention "
            f"particulière. Il reflète l'influence de l'a priori BF "
            f"sur les années récentes peu développées : "
            f"{'le CL sur-estime' if cl_r > bf_r else 'le CL sous-estime'} "
            f"les provisions par rapport à l'a priori. "
            f"Sur les portefeuilles jeunes ou en croissance rapide, "
            f"BF est généralement plus conservateur et prudent."
        )

    lignes.append("")

    # ── Chain Ladder ──────────────────────────────────────────────────────────
    tail_val = tail.get('tail_factor', 1.0) if isinstance(tail, dict) else 1.0
    if tail_val > 1.005:
        lignes.append(
            f"TAIL FACTOR : {tail_val:.4f} (+{(tail_val-1)*100:.2f}%). "
            f"Le développement ne s'achève pas à la dernière colonne du triangle. "
            f"Ce tail factor a été estimé par régression log-linéaire sur les "
            f"derniers facteurs de développement, ce qui représente "
            f"{_e((tail_val-1)*cl_r)} de provisions additionnelles. "
            f"{'Pour une branche à longue queue (RC, Construction), ce tail est normal.' if tail_val > 1.02 else 'Ce tail factor modéré est caractéristique des branches à développement court (MRH, Auto matériel).'}"
        )
    else:
        lignes.append(
            f"TAIL FACTOR ≈ 1.000 — le développement est considéré complet "
            f"à la dernière colonne du triangle. "
            f"Cette hypothèse est raisonnable pour les branches à courte queue."
        )

    lignes.append("")

    # ── Mack ─────────────────────────────────────────────────────────────────
    sigma = mack.get('sigma_total', 0)
    cv_m  = mack.get('cv_pct', 0)
    p90_m = mack.get('reserve_p90', 0)
    lignes.append(
        f"MACK 1993 : L'incertitude de réserve totale est σ = {_e(sigma)} "
        f"(CV = {_p(cv_m)}). "
    )
    if cv_m < 10:
        lignes.append(
            f"Ce niveau d'incertitude est faible — le triangle est bien "
            f"développé et les facteurs sont stables. La provision de "
            f"stress test P90 = {_e(p90_m)} représente une majoration "
            f"de {_p((p90_m/max(mk_r,1)-1)*100)} par rapport au BE Mack. "
            f"La distribution log-normale calibrée sur (BE, σ) "
            f"est conforme aux exigences QIS5 TP.5.26."
        )
    elif cv_m < 20:
        lignes.append(
            f"Ce niveau d'incertitude modéré (AMBRE EIOPA) reflète "
            f"une variabilité des facteurs dans la plage habituelle "
            f"pour ce type de branche. Le P90 = {_e(p90_m)} est à "
            f"utiliser pour le calibrage du buffer de prudence."
        )
    else:
        lignes.append(
            f"Ce niveau d'incertitude élevé (ROUGE EIOPA — CV > 20%) "
            f"est préoccupant. Il peut indiquer un triangle trop court, "
            f"des données hétérogènes, ou un portefeuille en forte "
            f"évolution. Le P90 = {_e(p90_m)} doit être utilisé comme "
            f"plancher conservateur, et une analyse par cohortes est recommandée."
        )

    lignes.append("")

    # ── Bootstrap ────────────────────────────────────────────────────────────
    # `or 0` sur chaque grandeur d'incertitude : depuis l'audit modèle, un
    # Bootstrap NON CALCULÉ les rend à None au lieu de fabriquer des zéros —
    # un CV de 0 % se lirait « aucune incertitude ». Le garde `boot_dispo`
    # décide de l'affichage ; les valeurs ne sont lues que s'il est vrai.
    boot_dispo = boot.get('disponible', True)
    be_boot  = boot.get('be_bootstrap', 0) or 0
    cv_boot  = (boot.get('cv_bootstrap') or 0) * 100
    p995     = boot.get('p99_5') or 0
    phi      = boot.get('phi') or 0
    n_sim    = boot.get('n_simulations', 0)

    if be_boot > 0 and boot_dispo:
        ecart_mack_boot = abs(mk_r - be_boot) / max(mk_r, 1e-9) * 100
        lignes.append(
            f"BOOTSTRAP ODP (England & Verrall 2002 — {n_sim:,} simulations) : "
            f"BE Bootstrap = {_e(be_boot)}, soit un écart de {_p(ecart_mack_boot)} "
            f"avec Mack. "
            f"Le facteur de sur-dispersion φ = {phi:.4f} "
            f"{'(> 1 : sur-dispersion par rapport au modèle Poisson pur)' if phi > 1 else '(< 1 : sous-dispersion)'}. "
            f"Le P99.5 Bootstrap de {_e(p995)} constitue l'estimation "
            f"stochastique du SCR provisions — "
            f"{'comparable' if abs(p995/max(be_boot,1)-1) < 0.5 else 'significativement différent'} "
            f"du P99.5 Mack."
        )
    else:
        lignes.append(
            "BOOTSTRAP ODP : non disponible sur ce triangle "
            "(données insuffisantes pour le rééchantillonnage)."
        )

    lignes += ["", "MÉTHODES DANS LE BE S2 :"]
    for m in methodes_inc:
        w = poids.get(m, 0)
        r = {'chain_ladder':cl_r,'mack':mk_r,'bornhuetter_ferguson':bf_r,'cape_cod':cc_r}.get(m, 0)
        lignes.append(f"  ✅ {label_map.get(m,m):30s} {_e(r):>18s}  poids={_p(w*100,0)}")
    for m in methodes_exc:
        r = {'chain_ladder':cl_r,'mack':mk_r,'bornhuetter_ferguson':bf_r,'cape_cod':cc_r}.get(m, 0)
        lignes.append(f"  ❌ {label_map.get(m,m):30s} {_e(r):>18s}  [exclu — score insuffisant]")

    return "\n".join(lignes)


# =============================================================================
#  SECTION 5 — BEST ESTIMATE S2
# =============================================================================

def _s5_best_estimate(n4: Dict) -> str:
    be     = n4.get('best_estimate', 0)

    # BE négatif (reprise nette) → percentiles / SCR / RM / PT non définis : on
    # affiche le message unique au lieu de chiffres trompeurs (les valeurs ont été
    # neutralisées à 0 en amont uniquement pour la sûreté du formatage).
    if s2_non_calculable(n4):
        return "\n".join([
            f"BEST ESTIMATE — RÉSERVE BRUTE (Art. 77 ; actualisation S2 par A10) : {_e(be)}",
            "",
            MSG_S2_NON_CALCULABLE,
            "",
            "Le Best Estimate est négatif : les méthodes retenues projettent, en net, "
            "une REPRISE de provision (recours / sur-développement) supérieure aux "
            "charges à payer restantes. Aucun percentile log-normal, SCR (3×σ×BE), "
            "Risk Margin ni provision technique S2 n'est défini sur cette base. "
            "L'actuaire désigné doit statuer sur la réalité de la reprise avant "
            "toute inscription au bilan.",
        ])

    p75    = n4.get('reserve_p75', 0)
    p90    = n4.get('reserve_p90', 0)
    p995   = n4.get('reserve_p99_5', 0)
    sigma  = n4.get('sigma_mack', 0)
    cv     = n4.get('cv_inter_methodes', 0)
    statut = n4.get('statut', 'AMBRE')

    lignes = [
        f"BEST ESTIMATE — RÉSERVE BRUTE (Art. 77 ; actualisation S2 par A10) : {_e(be)}",
        "",
        f"Le Best Estimate est la valeur attendue des flux futurs de règlement "
        f"de sinistres, moyenne pondérée des méthodes retenues. Il s'agit d'une "
        f"réserve BRUTE (non actualisée) : l'actualisation à la courbe RFR EIOPA "
        f"— la valeur actuelle au sens de l'Art. 77 — est opérée en aval par "
        f"A10 (Solvabilité 2).",
        "",
        f"Distribution log-normale composée (σ Mack ⊕ σ modèle) — percentiles retenus (QIS5 TP.5.26) :",
        f"  • Provision prudentielle P75  : {_e(p75)}  (+{_p((p75/max(be,1)-1)*100)} vs BE)",
        f"  • Provision stress test P90   : {_e(p90)}  (+{_p((p90/max(be,1)-1)*100)} vs BE)",
        f"  • Provision extrême P99.5     : {_e(p995)} (+{_p((p995/max(be,1)-1)*100)} vs BE)",
        f"  • Incertitude Mack σ          : {_e(sigma)}",
        f"  • CV inter-méthodes           : {_p(cv)}",
        "",
    ]

    if cv < 5:
        lignes.append(
            f"La convergence des méthodes est excellente (CV = {_p(cv)}). "
            f"Le Best Estimate de {_e(be)} est robuste et peut être "
            f"directement inscrit au bilan S2 sous réserve de validation "
            f"par l'actuaire désigné. La faible dispersion inter-méthodes "
            f"confirme la cohérence des données et des hypothèses."
        )
    elif cv < 15:
        lignes.append(
            f"La convergence des méthodes est acceptable (CV = {_p(cv)}). "
            f"Le Best Estimate de {_e(be)} est utilisable, mais l'écart "
            f"entre méthodes suggère une sensibilité aux hypothèses "
            f"qui mérite d'être documentée dans le rapport actuaire désigné. "
            f"Une provision de risque complémentaire peut être envisagée "
            f"si la direction financière souhaite une couverture au P75."
        )
    else:
        lignes.append(
            f"La divergence inter-méthodes est significative (CV = {_p(cv)}). "
            f"Le Best Estimate de {_e(be)} doit être présenté à l'actuaire "
            f"désigné avec l'ensemble du dossier de calcul avant toute "
            f"inscription au bilan. Le P90 de {_e(p90)} est recommandé "
            f"comme plancher conservateur en attendant une validation formelle."
        )

    return "\n".join(lignes)


# =============================================================================
#  SECTION 6 — INCERTITUDE ET STOCHASTIQUE
# =============================================================================

def _s6_incertitude(n3: Dict, n4: Dict) -> str:
    mack = n3.get('mack', {})
    boot = n3.get('bootstrap', {})

    p90_compose  = n4.get('reserve_p90', 0)
    sig_compose  = n4.get('sigma_total_compose', n4.get('sigma_mack', 0))
    p90_mack_re  = n4.get('reserve_p90_mack', p90_compose)
    sig_mack     = n4.get('sigma_mack', 0)
    p90_mack_nat = mack.get('reserve_p90', 0)
    sig_mack_nat = mack.get('sigma_total', 0)
    p90_boot     = boot.get('p90', 0)
    p995_boot    = boot.get('p99_5', 0)
    p995_mack    = mack.get('reserve_p99_5', 0)
    sig_boot     = boot.get('std_bootstrap') or 0
    boot_ok      = bool(boot.get('disponible', True)) and (boot.get('be_bootstrap', 0) or 0) > 0

    lignes = [
        "DIAGNOSTIC — décomposition de l'incertitude "
        "(outil analytique interne, non destiné au bilan)",
        "",
        "Le Best Estimate retient le P90 composé (incertitude composée "
        "σ Mack ⊕ σ modèle). L'incertitude se décompose selon plusieurs "
        "approches : Mack (1993), distribution-free, sépare l'erreur de paramètre "
        "et de processus (termes croisés inclus, Theorem 3) ; le Bootstrap ODP "
        "(England & Verrall 2002) simule les scénarios de développement. Les quatre "
        "lignes ci-dessous diffèrent par le σ et/ou le point de centrage — "
        "à titre de contrôle :",
        "",
        f"  • Incertitude composée (retenue) : P90 = {_e(p90_compose)} — "
        f"σ composé {_e(sig_compose)}, centré sur le BE pondéré.",
        f"  • Mack recentré : P90 = {_e(p90_mack_re)} — "
        f"σ Mack {_e(sig_mack)}, centré sur le BE pondéré.",
        f"  • Mack natif : P90 = {_e(p90_mack_nat)} — "
        f"σ Mack {_e(sig_mack_nat)}, centré sur la réserve Mack.",
    ]
    if boot_ok:
        lignes.append(
            f"  • Bootstrap ODP : P90 = {_e(p90_boot)} — "
            f"σ bootstrap {_e(sig_boot)}, centré sur la réserve Bootstrap."
        )
    else:
        lignes.append("  • Bootstrap ODP : non disponible sur ce triangle.")

    if p995_mack > 0 and p995_boot > 0:
        ecart_p995 = abs(p995_mack - p995_boot) / max(p995_mack, 1e-9) * 100
        if ecart_p995 > 15:
            lignes += [
                "",
                f"SIGNAL : écart P99.5 Mack ({_e(p995_mack)}) vs Bootstrap "
                f"({_e(p995_boot)}) de {_p(ecart_p995)} — possible non-normalité "
                f"ou hétéroscédasticité. Pour le SCR, retenir le maximum des deux.",
            ]

    return "\n".join(lignes)


# =============================================================================
#  SECTION 7 — SCR PROVISIONS
# =============================================================================

def _s7_scr(n4: Dict) -> str:
    scr      = n4.get('scr', {})
    be       = n4.get('best_estimate', 0)
    scr_prov = scr.get('scr_provisions', 0)
    sigma_e  = scr.get('sigma_eiopa', 0)
    lob_lbl  = scr.get('lob_label', '—')
    ratio    = scr.get('ratio_scr_be', 0)

    lignes = [
        f"SCR PROVISIONS — FORMULE STANDARD (Art. 105 Règlement 2015/35)",
        "",
        f"Pour la branche {lob_lbl} :",
        f"  SCR_prov = 3 × σ(LoB) × BE",
        f"           = 3 × {_p(sigma_e*100)} × {_e(be)}",
        f"           = {_e(scr_prov)}",
        f"  Ratio SCR/BE = {_p(ratio*100)}",
        "",
        f"Le facteur 3 correspond au quantile 99.5% d'une loi normale "
        f"standardisée, conformément à la calibration EIOPA.",
        f"Le facteur σ(LoB) = {_p(sigma_e*100)} est le facteur de volatilité "
        f"réglementaire EIOPA pour cette branche "
        f"(Annexe II, Règlement Délégué UE 2015/35).",
        "",
        f"IMPORTANT : Le SCR calculé ici est le SCR provisions isolé "
        f"(une seule LoB). L'agrégation avec les autres LoB se fait "
        f"au niveau du tableau de bord consolidé via la matrice de "
        f"corrélation EIOPA Non-Vie 12×12 (Annexe IV, Rgt 2015/35).",
        "",
    ]

    if ratio > 0.40:
        lignes.append(
            f"Le ratio SCR/BE de {_p(ratio*100)} est élevé pour cette branche. "
            f"Cela est cohérent avec le facteur de volatilité EIOPA "
            f"σ = {_p(sigma_e*100)} qui reflète l'incertitude structurelle "
            f"de ce type de risque. L'exigence de fonds propres S2 "
            f"sera significative — vérifier la couverture du SCR total."
        )
    elif ratio > 0.25:
        lignes.append(
            f"Le ratio SCR/BE de {_p(ratio*100)} est dans la plage habituelle "
            f"pour cette branche. La charge en capital est gérable."
        )
    else:
        lignes.append(
            f"Le ratio SCR/BE de {_p(ratio*100)} est relativement faible, "
            f"reflétant la faible volatilité réglementaire de cette branche."
        )

    return "\n".join(lignes)


# =============================================================================
#  SECTION 8 — RECOMMANDATIONS
# =============================================================================

def _s8_recommandations(n1: Dict, n2: Dict, n3: Dict, n4: Dict, lob: str) -> str:
    statut   = n4.get('statut', 'AMBRE')
    be       = n4.get('best_estimate', 0)
    p90      = n4.get('reserve_p90', 0)
    p995     = n4.get('reserve_p99_5', 0)
    scr_prov = n4.get('scr', {}).get('scr_provisions', 0)
    cv       = n4.get('cv_inter_methodes', 0)
    h1_ok    = n2.get('h1_independance', {}).get('ok', True)
    h2_ok    = n2.get('h2_stabilite', {}).get('ok', True)
    h3_src   = n3.get('bf', {}).get('source_lr', '')

    lignes = []

    # ── Avis actuariel ────────────────────────────────────────────────────────
    if statut == 'VERT':
        lignes += [
            "AVIS ACTUARIEL : FAVORABLE",
            "",
            f"Les méthodes convergent satisfaisamment (CV = {_p(cv)}). "
            f"Le Best Estimate de {_e(be)} peut être retenu pour "
            f"inscription au bilan S2.",
        ]
    elif statut == 'AMBRE':
        lignes += [
            "AVIS ACTUARIEL : FAVORABLE AVEC RÉSERVES",
            "",
            f"Une divergence modérée est observée entre méthodes (CV = {_p(cv)}). "
            f"Le Best Estimate de {_e(be)} est utilisable sous réserve de "
            f"validation par l'actuaire désigné et de documentation "
            f"des hypothèses dans le dossier actuariel.",
        ]
    else:
        lignes += [
            "AVIS ACTUARIEL : DÉFAVORABLE EN L'ÉTAT",
            "",
            f"La divergence inter-méthodes est significative (CV = {_p(cv)}). "
            f"Le Best Estimate de {_e(be)} ne doit pas être inscrit au bilan "
            f"S2 sans validation formelle préalable de l'actuaire désigné.",
        ]

    lignes += ["", "ACTIONS RECOMMANDÉES :"]

    # Actions selon statut
    if statut == 'VERT':
        lignes += [
            f"1. Transmettre {_e(be)} (réserve brute) à A10 pour actualisation avant inscription au bilan S2 (Art. 77).",
            f"2. Retenir {_e(p90)} pour le calcul du SCR provisions "
            f"   (stress test P90, formule standard Art. 105).",
            f"3. SCR provisions calculé : {_e(scr_prov)}.",
            f"4. Documenter la méthodologie et les hypothèses dans le rapport "
            f"   actuaire désigné.",
            f"5. Archiver ce rapport et l'audit trail associé (traçabilité ACPR).",
            f"6. Revue trimestrielle recommandée pour suivre l'évolution des facteurs.",
        ]
    elif statut == 'AMBRE':
        lignes += [
            f"1. Soumettre ce dossier à la validation de l'actuaire désigné.",
            f"2. Si validation obtenue : inscrire {_e(be)} au bilan S2.",
            f"3. Envisager une provision de risque complémentaire "
            f"   ({_e(p90)} au lieu du BE) si la direction financière "
            f"   privilégie la prudence.",
            f"4. SCR provisions indicatif : {_e(scr_prov)}.",
            f"5. Réviser les hypothèses à la prochaine clôture.",
        ]
    else:
        lignes += [
            f"1. NE PAS inscrire ce BE au bilan sans validation préalable.",
            f"2. Consulter l'actuaire désigné impérativement.",
            f"3. Vérifier la qualité des données source (triangle / sinistres bruts).",
            f"4. Analyser la cause de la divergence inter-méthodes.",
            f"5. Considérer une provision conservatrice de {_e(p995)} "
            f"   en attendant la résolution.",
        ]

    lignes.append("")
    lignes.append("POINTS DE VIGILANCE POUR LE PROCHAIN ARRÊTÉ :")

    # Points de vigilance selon les hypothèses
    if not h1_ok:
        lignes.append(
            "• H1 rejetée : surveiller si la dépendance inter-années persiste. "
            "Si oui, envisager une segmentation du portefeuille."
        )
    if not h2_ok:
        lignes.append(
            "• H2 rejetée : analyser la cause de l'instabilité des facteurs "
            "(évolution du mix, pratiques de règlement, inflation)."
        )
    # BRANCHE RÉPARÉE, ELLE NE POUVAIT PAS SE DÉCLENCHER. Elle comparait
    # `source_lr`, produit par N3, à `'proxy_sans_primes'` — une valeur de
    # l'ancienne H3 de N2 que N3 n'a jamais émise. La recommandation la plus
    # utile à l'actuaire ne sortait donc jamais. Les sources réelles sont
    # 'manuel', 'ultime_apriori', 'matures', 'refuse' et 'non calculée'.
    if h3_src in ('refuse', 'non calculée', ''):
        lignes.append(
            "• Fournir une mesure d'exposition, ou un loss ratio a priori "
            "(tarification, plan à moyen terme, benchmark de marché, jugement "
            "d'expert — guide IA 2023 §2.b.i p14) : Bornhuetter-Ferguson n'a "
            "pas pu être calculée, le Best Estimate perd un avis indépendant."
        )
    elif h3_src == 'matures':
        lignes.append(
            "• Le loss ratio a priori est dérivé des ultimes Chain Ladder : "
            "Bornhuetter-Ferguson corrige la répartition entre années sans "
            "corriger le niveau. Un loss ratio exogène rendrait au Best "
            "Estimate un second avis sur le niveau."
        )

    tail_v = n3.get('chain_ladder', {}).get('tail_factor', {})
    if isinstance(tail_v, dict) and tail_v.get('tail_factor', 1) > 1.03:
        lignes.append(
            f"• Tail factor = {tail_v.get('tail_factor',1):.4f} — "
            f"surveiller l'évolution du développement résiduel au prochain arrêté."
        )

    return "\n".join(lignes)


# =============================================================================
#  NARRATION SPÉCIFIQUE PAR BRANCHE (LoB)
# =============================================================================

# Données marché de référence par branche (FFA Non-Vie 2024 / MACSF / Sham)
_LR_MARCHE = {
    'mrh':                  ('68%',  'FFA Non-Vie 2024 — MRH'),
    'rc_auto_materiel':     ('72%',  'FFA Non-Vie 2024 — RC Auto matériels'),
    'rc_auto_corporels':    ('85%',  'FFA Non-Vie 2024 — RC Auto corporels'),
    'rc_generale':          ('78%',  'FFA Non-Vie 2024 — RC Générale'),
    'rc_medicale':          ('92%',  'MACSF/Sham — RC Médicale 2024'),
    'construction':         ('88%',  'FFA Non-Vie 2024 — Construction'),
    'marine_aviation_transport': ('82%', 'FFA Non-Vie 2024 — Marine/Transport'),
}


def _narration_lob(
    lob:  str,
    n1:   Dict,
    n2:   Dict,
    n3:   Dict,
    n4:   Dict,
) -> Dict[str, str]:
    """
    Retourne des blocs de narration spécifiques à la branche (LoB).

    Structure retournée :
        {
          'contexte'      : paragraphe §1 — spécificités de la branche
          'hypotheses'    : paragraphe §3 — points de vigilance H spécifiques
          'methodes'      : paragraphe §4 — lecture actuarielle LoB des résultats
          'recommandations': paragraphe §8 — actions LoB spécifiques
        }
    """
    fn = _LOB_HANDLERS.get(lob, _lob_generique)
    return fn(n1, n2, n3, n4)


# ── MRH — Multirisque Habitation ──────────────────────────────────────────────

def _lob_mrh(n1, n2, n3, n4):
    n_ann = n1.get('n_annees', 0)
    tail  = n3.get('chain_ladder', {}).get('tail_factor', {})
    tail_val = tail.get('tail_factor', 1.0) if isinstance(tail, dict) else 1.0
    be    = n4.get('best_estimate', 0)
    alertes_n1 = n1.get('alertes', [])
    h2_ok = n2.get('h2_stabilite', {}).get('ok', True)
    cv    = n2.get('h2_stabilite', {}).get('cv_moy', 0)

    contexte = (
        "SPÉCIFICITÉS BRANCHE MRH : "
        "La Multirisque Habitation est une branche à développement court (3-5 ans). "
        "Elle est caractérisée par un volume élevé de sinistres attritionnels "
        "(dégâts des eaux, incendie, vol) et une grande homogénéité des facteurs "
        "de développement. Le triangle CL doit converger rapidement — "
        f"avec {n_ann} années de survenance, l'estimation est {'robuste' if n_ann >= 8 else 'à confirmer sur plus de données'}. "
        "Deux risques spécifiques méritent attention sur cette branche : "
        "(1) les événements CAT NAT (tempêtes, inondations, grêle) qui faussent "
        "les facteurs de développement s'ils ne sont pas isolés avant le calcul CL ; "
        "(2) l'inflation des matériaux BTP post-2021 qui a significativement "
        "augmenté le coût moyen des sinistres incendie et travaux. "
        "Vérifier que ces deux effets sont correctement pris en compte "
        "dans les données source."
    )

    hypotheses = ""
    if not h2_ok:
        hypotheses = (
            f"SIGNAL MRH — H2 rejetée (CV={_p(cv*100)}) : "
            "Sur MRH, un CV élevé des facteurs est inhabituel pour cette branche "
            "naturellement homogène. Causes probables : "
            "(1) présence d'un ou plusieurs événements CAT NAT non isolés "
            "dans le triangle — ils créent une saisonnalité artificielle ; "
            "(2) changement de barème de règlement ou de sous-traitants ; "
            "(3) évolution rapide du mix garanties (dommages électriques, "
            "vol, RC). Une analyse colonne par colonne est recommandée "
            "avant de valider les facteurs."
        )
    else:
        hypotheses = (
            "COHÉRENCE MRH — Les hypothèses H1 et H2 sont compatibles avec "
            "le profil attendu d'un portefeuille MRH stable. "
            "Les facteurs de développement sont homogènes, "
            "ce qui confirme l'absence d'événements CAT NAT non isolés "
            "dans le triangle analysé."
        )

    # Vérifier si le tail est anormalement élevé pour MRH
    methodes = ""
    if tail_val > 1.02:
        methodes = (
            f"SIGNAL MRH — Tail factor = {tail_val:.4f} (+{(tail_val-1)*100:.2f}%) : "
            "Ce tail est atypique pour MRH (attendu < 1%). "
            "Un tail élevé sur une branche courte suggère soit un triangle "
            "tronqué (colonnes manquantes), soit un problème dans les données "
            "des dernières périodes. Vérifier la complétude des dernières colonnes "
            "avant d'accepter ce tail factor. "
            "Référence marché FFA : LR MRH ≈ 68% (FFA Non-Vie 2024)."
        )
    else:
        methodes = (
            f"COHÉRENCE MRH — Tail factor ≈ {tail_val:.4f} : conforme à une branche courte. "
            "Le développement est considéré complet dans la dernière colonne. "
            f"Référence marché FFA : LR MRH ≈ 68% (FFA Non-Vie 2024). "
            f"Comparer le LR BF retenu avec cette référence."
        )

    recommandations = (
        "ACTIONS SPÉCIFIQUES MRH : "
        "1. Vérifier que les sinistres CAT NAT (Xynthia, tempêtes hivernales, "
        "sécheresse) ont été isolés du triangle avant calcul — "
        "les intégrer fausse systématiquement les facteurs de développement. "
        "2. Contrôler l'évolution du coût moyen incendie sur les 3 dernières années "
        "(impact de l'inflation matériaux BTP : +15 à +25% entre 2021 et 2024). "
        "3. Analyser la saisonnalité de la diagonale Q4 "
        "(dégâts des eaux hiver, gel) pour valider H2. "
        "4. Le S/P MRH doit être comparé à la moyenne marché (68% FFA 2024) — "
        "un écart > 5 pts doit être documenté dans le dossier actuariel."
    )

    return {
        'contexte':        contexte,
        'hypotheses':      hypotheses,
        'methodes':        methodes,
        'recommandations': recommandations,
    }


# ── RC Auto matériels ─────────────────────────────────────────────────────────

def _lob_rc_auto_materiel(n1, n2, n3, n4):
    tail  = n3.get('chain_ladder', {}).get('tail_factor', {})
    tail_val = tail.get('tail_factor', 1.0) if isinstance(tail, dict) else 1.0
    n_ann = n1.get('n_annees', 0)
    h1_ok = n2.get('h1_independance', {}).get('ok', True)

    contexte = (
        "SPÉCIFICITÉS RC AUTO MATÉRIELS : "
        "La RC Auto matériels est une branche à développement court (4-6 ans). "
        "Le portefeuille est régi par la convention IDA (Indemnisation Directe de "
        "l'Assuré) pour les sinistres bilatéraux — les recours inter-compagnies "
        "doivent être traités séparément du triangle principal. "
        "L'inflation des pièces détachées et de la main-d'œuvre carrosserie "
        "(+8 à +12% par an depuis 2022) est un facteur structurel "
        "qui peut biaiser les facteurs de développement récents. "
        f"Le triangle de {n_ann} années est "
        f"{'suffisant' if n_ann >= 6 else 'à la limite — des années supplémentaires amélioreraient la robustesse'}."
    )

    hypotheses = (
        "COHÉRENCE RC AUTO MATÉRIELS : "
        + (
            "H1 validée — les années de survenance sont indépendantes, "
            "ce qui est attendu sur RC Auto matériels (portefeuille fréquence). "
            if h1_ok else
            "H1 rejetée sur RC Auto matériels — inhabituel sur un portefeuille de masse. "
            "Vérifier l'homogénéité du mix assuré (VP/utilitaires/deux-roues) "
            "et l'absence d'effet de cohorte lié à l'évolution du barème IDA. "
        )
        + "Surveiller la dérive des facteurs récents liée à l'inflation carrosserie "
        "— si les 2-3 dernières colonnes montrent des facteurs systématiquement "
        "plus élevés que les colonnes anciennes, H2 sera rejetée sur la dérive "
        "et la variante volume_weighted doit être privilégiée."
    )

    methodes = (
        "LECTURE RC AUTO MATÉRIELS : "
        f"Tail factor = {tail_val:.4f} — "
        + (
            "conforme à une branche courte (tail < 1%). "
            if tail_val < 1.015 else
            f"atypique pour RC Auto matériels (attendu < 1%). "
            "Vérifier la complétude des dernières colonnes. "
        )
        + "Le LR Cape Cod est particulièrement pertinent sur cette branche "
        "car les primes sont bien connues (tarification automobile précise). "
        "Référence marché FFA : LR RC Auto matériels ≈ 72% (FFA Non-Vie 2024). "
        "Les recours IDA reçus et payés doivent être traités en net "
        "pour cohérence avec les primes nettes."
    )

    recommandations = (
        "ACTIONS SPÉCIFIQUES RC AUTO MATÉRIELS : "
        "1. Vérifier que les recours IDA sont bien en net dans le triangle "
        "(recours reçus en déduction, recours payés en ajout). "
        "2. Contrôler l'évolution du coût moyen sur les 2-3 dernières années "
        "(signal inflation carrosserie : +8 à +12%/an depuis 2022). "
        "3. Comparer le S/P avec la moyenne marché (72% FFA 2024). "
        "4. Pour les flottes et les deux-roues, un traitement séparé "
        "est recommandé si leur poids dans le portefeuille dépasse 15%."
    )

    return {
        'contexte':        contexte,
        'hypotheses':      hypotheses,
        'methodes':        methodes,
        'recommandations': recommandations,
    }


# ── RC Générale ────────────────────────────────────────────────────────────────

def _lob_rc_generale(n1, n2, n3, n4):
    n_ann = n1.get('n_annees', 0)
    h1_ok = n2.get('h1_independance', {}).get('ok', True)
    h2_ok = n2.get('h2_stabilite', {}).get('ok', True)
    bf_lr = n3.get('bf', {}).get('lr_apriori') or 0.0
    be    = n4.get('best_estimate', 0)
    tail  = n3.get('chain_ladder', {}).get('tail_factor', {})
    tail_val = tail.get('tail_factor', 1.0) if isinstance(tail, dict) else 1.0

    contexte = (
        "SPÉCIFICITÉS RC GÉNÉRALE : "
        "La RC Générale est une branche à queue moyenne (8-15 ans). "
        "Elle présente une forte hétérogénéité : sinistres fréquence attritionnels "
        "(petits accidents, dommages matériels) coexistent avec des sinistres graves "
        "à développement long (préjudices corporels, produits défectueux). "
        f"Avec {n_ann} années, le triangle "
        f"{'capture bien la queue' if n_ann >= 12 else 'est insuffisant pour la queue — les sinistres graves des premières années peuvent ne pas être totalement développés'}. "
        "Deux risques spécifiques : "
        "(1) les sinistres sériels (défaut de produit, contamination) "
        "qui créent des corrélations inter-années et invalident H1 ; "
        "(2) l'émergence tardive — certains sinistres RC Générale "
        "sont déclarés 3 à 8 ans après le fait générateur. "
        "Le triangle doit inclure les sinistres tardifs pour être complet."
    )

    hypotheses = (
        "VIGILANCE RC GÉNÉRALE : "
        + (
            "H1 validée — pas de corrélation inter-années détectée. "
            "Surveiller néanmoins l'émergence de sinistres sériels "
            "qui pourraient invalider H1 aux prochains arrêtés. "
            if h1_ok else
            "H1 rejetée — corrélation inter-années significative. "
            "Sur RC Générale, cela suggère la présence de sinistres sériels "
            "(une mauvaise année tend à rester mauvaise sur plusieurs développements). "
            "BF ou Cape Cod sont nettement préférables à CL dans ce contexte. "
            "Identifier les années concernées et vérifier si un sinistre "
            "exceptionnel (produit défectueux, contamination) en est la cause. "
        )
        + (
            "" if h2_ok else
            "H2 rejetée — facteurs instables. Sur RC Générale, cela peut refléter "
            "une évolution du mix produits (part des sinistres graves) "
            "ou une modification des pratiques de règlement (externalisation, "
            "changement de gestionnaire). Analyser les facteurs par sous-branche "
            "(RC exploitation vs RC produits) si les données le permettent. "
        )
    )

    methodes = (
        "LECTURE RC GÉNÉRALE : "
        f"Le tail factor de {tail_val:.4f} "
        + (
            "est significatif — normal pour RC Générale (queue 8-15 ans). "
            "Ce tail représente le développement résiduel des sinistres graves "
            "au-delà de la dernière colonne du triangle. "
            if tail_val > 1.02 else
            "est faible — vérifier que le triangle est suffisamment long "
            "pour capturer les sinistres graves tardifs. "
        )
        + f"Le LR BF = {_p(bf_lr*100)} — "
        + (
            "cohérent avec la référence marché RC Générale (~78% FFA 2024). "
            if 0.65 < bf_lr < 0.92 else
            "à valider par rapport à la référence marché (~78% FFA 2024). "
            "Un écart significatif doit être documenté (mix produits, sinistralité atypique). "
        )
        + "Sur RC Générale, la séparation des gros sinistres (Large Loss Threshold) "
        "est recommandée si un sinistre dépasse 10% du total — "
        "les traiter en CAS-BY-CAS et réintégrer dans le BE final."
    )

    recommandations = (
        "ACTIONS SPÉCIFIQUES RC GÉNÉRALE : "
        "1. Identifier et documenter les sinistres sériels dans le triangle "
        "(produits défectueux, contamination, RC décennale courte). "
        "2. Vérifier que tous les sinistres à déclaration tardive (> 3 ans) "
        "sont bien intégrés dans le triangle. "
        "3. Appliquer un Large Loss Threshold si un sinistre > 10% du portefeuille "
        "— traitement séparé obligatoire pour ne pas biaiser les facteurs CL. "
        "4. Comparer le S/P avec la référence marché (78% FFA 2024). "
        "5. Surveiller l'évolution jurisprudentielle sur la RC produits "
        "(directive 85/374/CEE — révision en cours au niveau européen)."
    )

    return {
        'contexte':        contexte,
        'hypotheses':      hypotheses,
        'methodes':        methodes,
        'recommandations': recommandations,
    }


# ── RC Auto corporels ──────────────────────────────────────────────────────────

def _lob_rc_auto_corporels(n1, n2, n3, n4):
    n_ann    = n1.get('n_annees', 0)
    h1_ok    = n2.get('h1_independance', {}).get('ok', True)
    bf_lr    = n3.get('bf', {}).get('lr_apriori') or 0.0
    tail     = n3.get('chain_ladder', {}).get('tail_factor', {})
    tail_val = tail.get('tail_factor', 1.0) if isinstance(tail, dict) else 1.0
    p995     = n4.get('reserve_p99_5', 0)
    be       = n4.get('best_estimate', 0)

    _suffisance_tri = (
        "est suffisant pour l'estimation des sinistres graves"
        if n_ann >= 15 else
        "est insuffisant pour une branche à queue 15-25 ans"
        " — le tail factor est critique et doit être validé avec soin"
    )
    contexte = (
        "SPÉCIFICITÉS RC AUTO CORPORELS : "
        "La RC Auto corporels est la branche à queue la plus longue du Non-Vie "
        "français (15 à 25 ans de développement). "
        "Elle est dominée par les sinistres graves — tétraplégies, paraplégies, "
        "polytraumatismes — dont le règlement (rente ou capital) s'étale sur "
        "plusieurs décennies. "
        f"Avec {n_ann} années de survenance, le triangle {_suffisance_tri}. "
        "Points de vigilance réglementaires majeurs : "
        "(1) Révisions régulières du barème Dintilhac (préjudices corporels) "
        "qui peuvent modifier rétrospectivement les charges ; "
        "(2) Taux de capitalisation des rentes (Barème de capitalisation 2022) ; "
        "(3) Inflation médicale différenciée (honoraires, hospitalisation, "
        "appareillage) structurellement supérieure à l'inflation générale ; "
        "(4) Recours FGAO (Fonds de Garantie des Assurances Obligatoires) "
        "à isoler du triangle principal."
    )

    hypotheses = (
        "VIGILANCE RC AUTO CORPORELS : "
        + (
            "H1 validée — cohérent avec un portefeuille homogène de sinistres corporels. "
            if h1_ok else
            "H1 rejetée — sur RC Auto corporels, la dépendance inter-années "
            "peut refléter des effets de cohorte (millésimes d'accidents "
            "marqués par des changements jurisprudentiels : arrêts Cour de cassation, "
            "révisions du barème Dintilhac). "
            "BF est fortement recommandé pour s'affranchir de ces corrélations. "
        )
        + "Attention particulière sur H2 : la dérive des facteurs récents "
        "est attendue sur cette branche (hausse de l'inflation médicale "
        "post-COVID, révision des barèmes). "
        "La variante volume_weighted doit être systématiquement privilégiée "
        "pour donner plus de poids aux années récentes. "
        "Le test H4 (homoscédasticité Bootstrap) est crucial car "
        "la distribution des sinistres corporels graves est très asymétrique "
        "— quelques sinistres extrêmes peuvent dominer les résidus."
    )

    methodes = (
        "LECTURE RC AUTO CORPORELS : "
        f"Tail factor = {tail_val:.4f} "
        + (
            f"(+{(tail_val-1)*100:.2f}%) — "
            "ce tail représente le développement résiduel des sinistres "
            "graves au-delà de la dernière colonne. "
            + (
                "SIGNAL : tail > 5% sur RC Auto corporels peut indiquer "
                "un triangle insuffisamment long — les sinistres graves "
                "des premières années ne sont peut-être pas soldés. "
                if tail_val > 1.05 else
                "Niveau cohérent avec la longueur de développement observée. "
            )
        )
        + f"LR BF = {_p(bf_lr*100)} vs référence marché ≈ 85% (FFA 2024). "
        + (
            "Cohérent. " if 0.75 < bf_lr < 0.95 else
            f"Écart significatif — documenter la cause (mix sinistres, millésimes atypiques). "
        )
        + f"Le P99.5 Bootstrap = {_e(p995)} "
        f"({'+' if p995 > be else ''}{_p((p995/max(be,1)-1)*100)} vs BE) "
        "est le chiffre critique pour le SCR provisions — "
        "sur RC Auto corporels, un ratio P99.5/BE > 1.5 est courant "
        "compte tenu de la forte volatilité des sinistres graves. "
        "La distribution Bootstrap doit être analysée avec soin : "
        "une asymétrie marquée vers la droite est attendue."
    )

    recommandations = (
        "ACTIONS SPÉCIFIQUES RC AUTO CORPORELS : "
        "1. Vérifier que les rentes servies (IARD vie) sont bien valorisées "
        "au taux de capitalisation du barème 2022 — un changement de taux "
        "peut modifier significativement le BE. "
        "2. Isoler les recours FGAO (reçus et payés) du triangle principal. "
        "3. Analyser l'impact des révisions Dintilhac sur les millésimes ouverts "
        "(préjudice d'établissement, tierce personne, déficit fonctionnel permanent). "
        "4. Intégrer l'inflation médicale différenciée dans l'a priori BF "
        "si elle diffère significativement de l'inflation générale. "
        "5. Consulter l'actuaire désigné pour la validation du tail factor "
        "et du taux de capitalisation des rentes avant inscription au bilan S2. "
        "6. Envisager un modèle de développement Clark (log-logistique) "
        "pour mieux calibrer la queue de distribution sur les sinistres graves."
    )

    return {
        'contexte':        contexte,
        'hypotheses':      hypotheses,
        'methodes':        methodes,
        'recommandations': recommandations,
    }


# ── RC Médicale ────────────────────────────────────────────────────────────────

def _lob_rc_medicale(n1, n2, n3, n4):
    n_ann    = n1.get('n_annees', 0)
    tail     = n3.get('chain_ladder', {}).get('tail_factor', {})
    tail_val = tail.get('tail_factor', 1.0) if isinstance(tail, dict) else 1.0
    be       = n4.get('best_estimate', 0)
    p90      = n4.get('reserve_p90', 0)
    bf_lr    = n3.get('bf', {}).get('lr_apriori') or 0.0

    contexte = (
        "SPÉCIFICITÉS RC MÉDICALE : "
        "La RC Médicale est la branche la plus longue et la plus complexe "
        "du Non-Vie français (20 à 30 ans de développement). "
        "Elle couvre les praticiens libéraux, les établissements de santé "
        "et les produits de santé (dispositifs médicaux, médicaments). "
        f"Avec {n_ann} années de survenance, "
        + (
            "le triangle est insuffisant pour cette branche — "
            "les sinistres graves (infections nosocomiales, accidents chirurgicaux) "
            "se développent sur 20 à 30 ans. Le tail factor est CRITIQUE "
            "et doit être validé par l'actuaire désigné. "
            if n_ann < 15 else
            "le triangle commence à capturer la queue mais une analyse "
            "des sinistres ouverts les plus anciens est nécessaire "
            "pour valider la complétude. "
        )
        + "Cadre réglementaire spécifique : "
        "(1) Loi Kouchner (2002) — obligation d'assurance RC médicale, "
        "procédure CRCI/CCI (Commission de Conciliation et d'Indemnisation) ; "
        "(2) ONIAM (Office National d'Indemnisation des Accidents Médicaux) "
        "pour les aléas thérapeutiques — recours à isoler ; "
        "(3) Délais de prescription : 10 ans à compter de la consolidation "
        "du dommage, ce qui explique les déclarations très tardives ; "
        "(4) Inflation médicale différenciée : honoraires (+3-4%/an), "
        "hospitalisation (+4-5%/an), appareillage (+2-3%/an)."
    )

    hypotheses = (
        "VIGILANCE RC MÉDICALE — HYPOTHÈSES : "
        "Sur RC Médicale, le rejet de H1 est fréquent et attendu : "
        "les années de mauvaise sinistralité (épidémies, séries d'erreurs "
        "dans un établissement) tendent à se propager sur plusieurs colonnes "
        "de développement. BF avec a priori externe (benchmarks MACSF/Sham) "
        "est la méthode de référence du marché. "
        "Le rejet de H2 est également attendu : "
        "l'évolution jurisprudentielle (augmentation des indemnisations, "
        "reconnaissance de nouveaux préjudices) crée une dérive structurelle "
        "des facteurs. La variante volume_weighted est obligatoire. "
        "Le test H4 (Bootstrap) doit être interprété avec prudence : "
        "la distribution RC Médicale est très leptokurtique "
        "(queue épaisse à droite), la normalité des résidus est douteuse."
    )

    methodes = (
        "LECTURE RC MÉDICALE — RÉSULTATS : "
        f"Tail factor = {tail_val:.4f} "
        + (
            f"(+{(tail_val-1)*100:.2f}%) — "
            + (
                "ATTENTION : tail élevé sur RC Médicale. "
                "Ce niveau peut être normal si le triangle est court (< 15 ans) "
                "mais doit être validé par rapport aux benchmarks MACSF/Sham. "
                if tail_val > 1.08 else
                "niveau modéré — vérifier la cohérence avec la longueur du triangle. "
                "Sur RC Médicale, un tail < 3% avec moins de 20 ans de données "
                "sous-estime probablement le développement résiduel. "
                if tail_val < 1.03 and n_ann < 20 else
                "cohérent avec la longueur du triangle. "
            )
        )
        + f"LR BF = {_p(bf_lr*100)} vs référence marché ≈ 92% (MACSF/Sham 2024). "
        + (
            "Cohérent. " if 0.80 < bf_lr < 1.05 else
            f"Écart vs référence marché — le LR RC Médicale est structurellement "
            "élevé (charge sinistres graves, indemnisations en hausse). "
        )
        + "Le discount (actualisation des flux futurs) est obligatoire "
        "en S2 pour les rentes long terme — vérifier que le BE intègre "
        "la valeur actuelle des rentes et pas leur valeur nominale."
    )

    recommandations = (
        "ACTIONS SPÉCIFIQUES RC MÉDICALE : "
        "1. Valider le tail factor avec l'actuaire désigné et par comparaison "
        "avec les benchmarks de marché MACSF/Sham. "
        "2. Vérifier l'intégration des recours ONIAM (reçus et payés) "
        "dans le triangle. "
        "3. Appliquer l'actualisation S2 (discount) sur les rentes "
        "à long terme (Art. 77 — flux futurs actualisés). "
        "4. Documenter l'impact des évolutions jurisprudentielles récentes "
        "sur le LR a priori BF (préjudice d'anxiété, contamination). "
        "5. Envisager une analyse par sous-portefeuille "
        "(praticiens libéraux vs établissements vs produits de santé) "
        "si le volume le permet. "
        "6. La validation par l'actuaire désigné est IMPÉRATIVE "
        "avant inscription au bilan S2 sur cette branche."
    )

    return {
        'contexte':        contexte,
        'hypotheses':      hypotheses,
        'methodes':        methodes,
        'recommandations': recommandations,
    }


# ── Construction ───────────────────────────────────────────────────────────────

def _lob_construction(n1, n2, n3, n4):
    n_ann    = n1.get('n_annees', 0)
    n_dev    = n1.get('n_dev', 0)
    tail     = n3.get('chain_ladder', {}).get('tail_factor', {})
    tail_val = tail.get('tail_factor', 1.0) if isinstance(tail, dict) else 1.0
    alertes  = n1.get('alertes', [])
    h2_ok    = n2.get('h2_stabilite', {}).get('ok', True)

    contexte = (
        "SPÉCIFICITÉS CONSTRUCTION (RC Décennale / DO) : "
        "La Construction est une branche à structure très particulière : "
        "la garantie décennale court pendant 10 ans après la réception des travaux, "
        "ce qui signifie que la DÉCLARATION peut intervenir jusqu'à 10 ans "
        "après la réception. "
        "Conséquence directe : les premières colonnes du triangle "
        "(années 1 à 4) sont structurellement CREUSES — peu de sinistres "
        "sont déclarés les premières années. "
        f"Avec {n_ann} années × {n_dev} colonnes, "
        + (
            "le triangle est court pour cette branche — "
            "la zone de développement [0-3 ans] comporte peu de sinistres "
            "déclarés, ce qui rend les facteurs CL des premières colonnes "
            "peu robustes. BF est obligatoire sur les années récentes. "
            if n_ann < 12 else
            "le triangle commence à couvrir les 10 ans de développement. "
            "Vérifier que les millésimes les plus anciens sont bien soldés. "
        )
        + "Autres risques spécifiques : "
        "(1) insolvabilités des constructeurs — "
        "les recours en garantie peuvent être perdus ; "
        "(2) sinistres sériels (défaut de conception, matériaux défectueux) ; "
        "(3) sous-assurance DO (Dommages-Ouvrage) fréquente sur les petits chantiers."
    )

    hypotheses = (
        "VIGILANCE CONSTRUCTION — HYPOTHÈSES : "
        "Sur Construction, les hypothèses de Mack sont structurellement "
        "difficiles à valider du fait des triangles creux : "
        "H1 et H2 peuvent être rejetées non pas à cause d'une pathologie "
        "du portefeuille mais à cause de la structure naturelle de la branche. "
        + (
            "H2 rejetée — sur Construction, vérifier si l'instabilité "
            "vient des premières colonnes (zone creuse) ou des colonnes "
            "intermédiaires (5-8 ans). Si l'instabilité est concentrée "
            "dans les premières colonnes, BF est nettement préférable. "
            if not h2_ok else
            "H2 validée — résultat encourageant sur une branche structurellement "
            "difficile. Vérifier que les facteurs des premières colonnes "
            "sont estimés sur suffisamment d'observations. "
        )
        + "BF est la méthode de RÉFÉRENCE sur Construction "
        "pour les années récentes (< 5 ans de développement) "
        "car le triangle y est trop creux pour calibrer CL de façon fiable."
    )

    methodes = (
        "LECTURE CONSTRUCTION — RÉSULTATS : "
        f"Tail factor = {tail_val:.4f} "
        + (
            f"(+{(tail_val-1)*100:.2f}%) — "
            "sur Construction, un tail modéré est attendu (3-6%). "
            + (
                "SIGNAL : tail élevé — vérifier que le triangle couvre "
                "bien les 12-15 ans de développement attendus. "
                if tail_val > 1.07 else
                "SIGNAL : tail faible — vérifier que les sinistres tardifs "
                "(déclarés après 8 ans) sont bien intégrés. "
                if tail_val < 1.02 else
                "Cohérent avec la longueur du triangle. "
            )
        )
        + "L'analyse des IBNR par année de survenance est particulièrement "
        "importante sur Construction : les années récentes (< 5 ans) "
        "ont des IBNR très élevés (triangle creux) et sont "
        "très sensibles à l'a priori BF. "
        "Référence marché FFA : LR Construction ≈ 88% (FFA Non-Vie 2024)."
    )

    recommandations = (
        "ACTIONS SPÉCIFIQUES CONSTRUCTION : "
        "1. Distinguer RC Décennale (10 ans garantie) et DO "
        "(Dommages-Ouvrage — l'assureur DO se retourne ensuite contre les constructeurs). "
        "2. Identifier les chantiers en litige avec insolvabilité du constructeur "
        "— les recours en garantie doivent être dépréciés. "
        "3. Appliquer BF systématiquement sur les années < 5 ans "
        "(zone creuse — CL non fiable). "
        "4. Analyser les sinistres sériels par type de désordre "
        "(fondations, étanchéité, charpente) pour détecter des lots défectueux. "
        "5. Vérifier la couverture DO / RC Dec de chaque chantier majeur "
        "pour identifier les sous-assurances potentielles. "
        "6. Le tail factor doit être validé en cohérence avec la courbe "
        "de déclaration Construction (pic à 7-9 ans)."
    )

    return {
        'contexte':        contexte,
        'hypotheses':      hypotheses,
        'methodes':        methodes,
        'recommandations': recommandations,
    }


# ── Marine / Aviation / Transport ──────────────────────────────────────────────

def _lob_marine(n1, n2, n3, n4):
    n_ann = n1.get('n_annees', 0)
    be    = n4.get('best_estimate', 0)
    cl_r  = n3.get('chain_ladder', {}).get('reserve_totale', 0)

    contexte = (
        "SPÉCIFICITÉS MARINE / AVIATION / TRANSPORT : "
        "La branche Marine/Transport est caractérisée par une forte "
        "CONCENTRATION du risque : un seul sinistre (naufrage, crash, "
        "contamination cargaison) peut représenter 30 à 50% du portefeuille. "
        "Cette concentration rend les méthodes CL standard très sensibles "
        "aux années atypiques. "
        f"Avec {n_ann} années de survenance, "
        + (
            "la taille est suffisante mais la concentration impose "
            "une analyse sinistre par sinistre sur les grands risques. "
            if n_ann >= 8 else
            "le triangle est court — les résultats doivent être interprétés "
            "avec précaution (effet d'un seul sinistre potentiellement dominant). "
        )
        + "Points de vigilance : "
        "(1) Séparation obligatoire BRUT / NET de réassurance "
        "— les recouvrements réassuranciels peuvent être très différents "
        "selon les couches (XL vs proportionnel) ; "
        "(2) Exposition aux événements géopolitiques (zones de guerre, embargos) ; "
        "(3) Sinistres CAT maritimes (tempêtes, typhons) à isoler. "
        "Le facteur de volatilité EIOPA σ=17% reflète cette incertitude élevée."
    )

    hypotheses = (
        "VIGILANCE MARINE/TRANSPORT — HYPOTHÈSES : "
        "Sur Marine/Transport, le rejet de H1 est quasi-systématique "
        "si un sinistre catastrophique est présent dans le triangle "
        "(l'année du sinistre se développe différemment des autres). "
        "BF ou Cape Cod sont les méthodes de référence. "
        "Un Large Loss Threshold (LLT) doit être appliqué AVANT le calcul CL "
        "pour extraire les sinistres > 10% du portefeuille. "
        "Ces sinistres sont traités séparément (réservation cas par cas) "
        "et réintégrés dans le BE final. "
        "Les méthodes stochastiques (Mack, Bootstrap) doivent être "
        "interprétées avec prudence — la distribution des sinistres "
        "Marine est très asymétrique (Pareto heavy tail)."
    )

    methodes = (
        "LECTURE MARINE/TRANSPORT — RÉSULTATS : "
        f"BE = {_e(be)} vs CL = {_e(cl_r)} — "
        + (
            f"divergence de {_p(abs(be-cl_r)/max(cl_r,1)*100)} : "
            "normale si BF ou Cape Cod ont un LR a priori différent du LR CL. "
            if abs(be - cl_r) / max(cl_r, 1e-9) > 0.10 else
            "bonne convergence méthodes. "
        )
        + "La séparation brut/net de réassurance est critique : "
        "le BE brut (avant réassurance) peut être très différent du BE net. "
        "Vérifier que les primes et sinistres sont en COHÉRENCE "
        "(tout en brut ou tout en net). "
        "Référence marché : LR Marine ≈ 82% (FFA Non-Vie 2024), "
        "mais avec une très forte dispersion selon les sous-branches "
        "(corps de navires vs RC transporteurs vs cargaison)."
    )

    recommandations = (
        "ACTIONS SPÉCIFIQUES MARINE/TRANSPORT : "
        "1. Appliquer un Large Loss Threshold (LLT) AVANT tout calcul CL "
        "— extraire les sinistres > 10% du portefeuille pour traitement CAS-BY-CAS. "
        "2. Vérifier la cohérence brut/net réassurance "
        "(primes nettes vs sinistres nets des recouvrements). "
        "3. Documenter les sinistres CAT maritimes "
        "(tempêtes, événements géopolitiques) et leur traitement. "
        "4. Le SCR LoB 6 (σ=17%) est particulièrement élevé "
        "— anticiper une exigence de capital importante. "
        "5. Envisager une analyse par sous-branche "
        "(corps, RC, cargaison) si le volume le permet. "
        "6. Consulter les conditions de réassurance "
        "avant toute décision de provisionnement net."
    )

    return {
        'contexte':        contexte,
        'hypotheses':      hypotheses,
        'methodes':        methodes,
        'recommandations': recommandations,
    }


# ── Petits triangles (n < 5) ──────────────────────────────────────────────────

def _avertissement_petit_triangle(n_ann: int) -> str:
    """Génère un avertissement fort pour les triangles de petite taille."""
    if n_ann >= 5:
        return ''
    return (
        f"⚠️  AVERTISSEMENT CRITIQUE — TRIANGLE PETIT ({n_ann} ANNÉES) : "
        "Avec seulement {n_ann} années de survenance, les estimations "
        "actuarielles sont peu robustes sur l'ensemble des colonnes. "
        "Les facteurs de développement reposent sur 2 à 4 observations "
        "par colonne — un seul sinistre atypique peut modifier "
        "radicalement les résultats. "
        "Recommandations impératives : "
        "(1) Traiter ces résultats comme des indicateurs préliminaires, "
        "pas comme un BE S2 définitif ; "
        "(2) Utiliser BF avec un a priori externe fiable "
        "(données marché, benchmarks sectoriels) ; "
        "(3) Demander la validation de l'actuaire désigné avant "
        "tout usage bilan ; "
        "(4) Travailler à l'enrichissement du triangle "
        "(données historiques supplémentaires, données de place). "
        "Un triangle standard de marché couvre 10 à 15 années "
        "de survenance — en-dessous de 5 ans, le S2 ne reconnaît "
        "pas la méthode CL comme suffisamment fiable."
    )


# ── Comparatif N-1/N dans la narration ────────────────────────────────────────

def _narration_comparatif(n4: Dict, resultats_precedents: Optional[Dict]) -> str:
    """
    Narration de la variation BE entre arrêtés si N-1 disponible.
    """
    if not resultats_precedents:
        return ''

    be_n   = n4.get('best_estimate', 0)
    be_nm1 = resultats_precedents.get('best_estimate', 0)
    p90_n  = n4.get('reserve_p90',  0)
    p90_nm1= resultats_precedents.get('reserve_p90', 0)
    cv_n   = n4.get('cv_inter_methodes', 0)
    cv_nm1 = resultats_precedents.get('cv_inter_methodes', 0)

    if be_nm1 <= 0:
        return ''

    delta_be  = be_n  - be_nm1
    delta_pct = delta_be / be_nm1 * 100
    delta_p90 = (p90_n - p90_nm1) / max(p90_nm1, 1e-9) * 100 if p90_nm1 > 0 else None

    # Qualifier la variation
    if abs(delta_pct) < 3:
        qualif = "stable — variation dans les normes de révision trimestrielle"
        signal = 'VERT'
    elif abs(delta_pct) < 10:
        qualif = "modérée — à documenter et expliquer dans le dossier actuariel"
        signal = 'AMBRE'
    else:
        qualif = "SIGNIFICATIVE — analyse approfondie requise avant inscription au bilan"
        signal = 'ROUGE'

    direction = "hausse" if delta_be > 0 else "baisse"

    lignes = [
        f"COMPARATIF N-1/N : variation du Best Estimate",
        "",
        f"BE arrêté N   : {_e(be_n)}",
        f"BE arrêté N-1 : {_e(be_nm1)}",
        f"Variation     : {'+' if delta_be >= 0 else ''}{_e(delta_be)} "
        f"({'+' if delta_pct >= 0 else ''}{_p(delta_pct)}) — variation {qualif}",
    ]

    if delta_p90 is not None:
        lignes.append(
            f"P90 N vs N-1  : {'+' if delta_p90 >= 0 else ''}{_p(delta_p90)}"
        )

    if cv_nm1 > 0:
        delta_cv = cv_n - cv_nm1
        lignes.append(
            f"CV méthodes   : {_p(cv_n)} vs {_p(cv_nm1)} arrêté N-1 "
            f"({'amélioration' if delta_cv < 0 else 'dégradation'} de la convergence)"
        )

    lignes += [""]

    # Analyse de la variation
    if abs(delta_pct) < 3:
        lignes.append(
            "La stabilité du BE entre arrêtés est un signal positif "
            "de la robustesse des hypothèses actuarielles. "
            "Les méthodes convergent de façon cohérente d'un arrêté à l'autre."
        )
    elif delta_pct > 10:
        lignes.append(
            f"La hausse de {_p(delta_pct)} du BE mérite une analyse approfondie. "
            "Causes possibles : (1) révision à la hausse des dossiers ouverts ; "
            "(2) émergence de nouveaux sinistres tardifs ; "
            "(3) révision de l'a priori BF (hausse du LR marché) ; "
            "(4) changement de variante CL (passage de standard à médiane). "
            "Documenter la cause principale dans le rapport actuaire désigné."
        )
    elif delta_pct < -10:
        lignes.append(
            f"La baisse de {_p(abs(delta_pct))} du BE doit être expliquée. "
            "Causes possibles : (1) sinistres soldés sur les millésimes anciens ; "
            "(2) révision à la baisse de dossiers ; "
            "(3) amélioration du mix sinistres (moins de sinistres graves). "
            "Vérifier que la baisse n'est pas due à un problème de données "
            "(sinistres manquants, erreur de saisie)."
        )
    else:
        lignes.append(
            f"La variation de {_p(abs(delta_pct))} est dans la plage "
            "habituelle de révision entre arrêtés. "
            "Documenter les facteurs explicatifs principaux "
            "dans le dossier actuariel."
        )

    return "\n".join(lignes)


# ── Registre des handlers LoB ─────────────────────────────────────────────────

def _lob_generique(n1, n2, n3, n4):
    """Fallback — narration générique sans spécificité branche."""
    lob_ref = _LR_MARCHE.get('rc_generale', ('78%', 'FFA Non-Vie 2024'))
    return {
        'contexte': (
            "Branche non identifiée spécifiquement dans la configuration ActuarIA. "
            "Les seuils et seuils génériques (H2 CV=15%, dérive=20%) sont appliqués. "
            "Pour une analyse adaptée à votre branche, préciser le paramètre "
            "'lob' dans l'appel à run() parmi : mrh, rc_auto_materiel, "
            "rc_auto_corporels, rc_generale, rc_medicale, construction, "
            "marine_aviation_transport."
        ),
        'hypotheses':      '',
        'methodes':        '',
        'recommandations': '',
    }


_LOB_HANDLERS = {
    'mrh':                       _lob_mrh,
    'rc_auto_materiel':          _lob_rc_auto_materiel,
    'rc_auto_corporels':         _lob_rc_auto_corporels,
    'rc_generale':               _lob_rc_generale,
    'rc_medicale':               _lob_rc_medicale,
    'construction':              _lob_construction,
    'marine_aviation_transport': _lob_marine,
    'generique':                 _lob_generique,
}


# =============================================================================
#  FONCTION PRINCIPALE
# =============================================================================

def generer_commentaire(
    n1:  Dict,
    n2:  Dict,
    n3:  Dict,
    n4:  Dict,
    lob: str = 'generique',
    lob_label: str = '',
    ref_client: str = '',
    resultats_precedents: Optional[Dict] = None,
) -> str:
    """
    Génère le commentaire actuariel complet en 8 sections enrichies.

    Style rapport actuaire désigné ACPR — narratif dense, expert,
    jamais économe en mots, toujours en posture de conseil senior.

    Chaque section intègre automatiquement :
    · Une narration spécifique à la branche (LoB) — jurisprudence,
      inflation, points de vigilance réglementaires propres à chaque branche
    · Un avertissement renforcé si le triangle est petit (n < 5)
    · Une analyse comparatif N-1/N si resultats_precedents fourni

    Parameters
    ----------
    n1, n2, n3, n4       : dicts des niveaux N1 à N4
    lob                  : identifiant LoB (depuis lob_config)
    lob_label            : libellé lisible de la LoB
    ref_client           : référence client (optionnel)
    resultats_precedents : dict du BE précédent pour comparatif N-1/N
                           {best_estimate, reserve_p90, cv_inter_methodes, sigma_mack}

    Returns
    -------
    str — commentaire complet prêt à afficher / embarquer dans le rapport
    """
    if not lob_label:
        lob_label = n2.get('lob_label', lob)

    date_str = datetime.now().strftime('%d/%m/%Y')
    statut   = n4.get('statut', 'AMBRE')
    be       = n4.get('best_estimate', 0)
    n_ann    = n1.get('n_annees', 0)

    # ── Blocs de narration spécifiques à la branche ───────────────────────────
    blocs_lob = _narration_lob(lob, n1, n2, n3, n4)

    # ── Avertissement petit triangle ──────────────────────────────────────────
    avert_petit = _avertissement_petit_triangle(n_ann)

    # ── Comparatif N-1/N ──────────────────────────────────────────────────────
    comparatif = _narration_comparatif(n4, resultats_precedents)

    # ── §1 enrichi : contexte général + spécificité LoB ──────────────────────
    s1 = _s1_contexte(n1, n2, n3, lob, lob_label)
    if blocs_lob.get('contexte'):
        s1 += "\n\n" + blocs_lob['contexte']
    if avert_petit:
        s1 += "\n\n" + avert_petit

    # ── §2 : qualité données (inchangé) ──────────────────────────────────────
    s2 = _s2_qualite(n1)

    # ── §3 enrichi : hypothèses + vigilance LoB ──────────────────────────────
    s3 = _s3_hypotheses(n2)
    if blocs_lob.get('hypotheses'):
        s3 += "\n\n" + blocs_lob['hypotheses']

    # ── §4 enrichi : méthodes + lecture LoB ──────────────────────────────────
    s4 = _s4_methodes(n3, n4)
    if blocs_lob.get('methodes'):
        s4 += "\n\n" + blocs_lob['methodes']

    # ── §5 : BE S2 (inchangé) ────────────────────────────────────────────────
    s5 = _s5_best_estimate(n4)

    # ── §6 enrichi : incertitude + comparatif N-1/N ──────────────────────────
    s6 = _s6_incertitude(n3, n4)
    if comparatif:
        s6 += "\n\n" + comparatif

    # ── §7 : SCR (inchangé) ──────────────────────────────────────────────────
    s7 = _s7_scr(n4)

    # ── §8 enrichi : recommandations générales + actions LoB spécifiques ─────
    s8 = _s8_recommandations(n1, n2, n3, n4, lob)
    if blocs_lob.get('recommandations'):
        s8 += "\n\n" + blocs_lob['recommandations']

    # ── Assemblage ────────────────────────────────────────────────────────────
    titre = [
        "═" * 70,
        f" RAPPORT DE PROVISIONNEMENT NON-VIE — AGENT A7 IBRAHIM v5.0",
        f" Date : {date_str}",
        f" Branche : {lob_label}",
        f" Référence : {ref_client}" if ref_client else "",
        f" Statut global : {_statut_txt(statut)}",
        f" Best Estimate (brut) : {_e(be)}",
        "═" * 70,
        "",
    ]
    titre = [l for l in titre if l]

    sections_map = {
        "§1 — CONTEXTE ET PÉRIMÈTRE":        s1,
        "§2 — QUALITÉ DES DONNÉES":          s2,
        "§3 — VALIDATION DES HYPOTHÈSES":    s3,
        "§4 — ANALYSE DES MÉTHODES":         s4,
        "§5 — BEST ESTIMATE (réserve brute, Art. 77)": s5,
        "§6 — INCERTITUDE DE RÉSERVE":       s6,
        "§7 — SCR PROVISIONS (Art. 105 S2)": s7,
        "§8 — RECOMMANDATIONS":              s8,
    }

    blocs = list(titre)
    for titre_sec, contenu in sections_map.items():
        blocs += [
            "─" * 70,
            f" {titre_sec}",
            "─" * 70,
            "",
            contenu,
            "",
        ]

    blocs += [
        "═" * 70,
        " FIN DU RAPPORT — ActuarIA v5.0",
        f" Généré le {date_str} | Traçabilité : audit trail JSON associé",
        "═" * 70,
    ]

    return "\n".join(blocs)
