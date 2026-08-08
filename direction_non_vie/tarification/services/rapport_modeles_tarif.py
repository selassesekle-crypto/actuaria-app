"""
ActuarIA — Rapport Tarification Non-Vie
Direction Non-Vie · Équipe Tarification · BLOC 5

4 formats : HTML · Word (.docx) · PDF (weasyprint) · Excel (via tarif_excel.py)
Narration : Claude API → commentaire agent → données seules (3 niveaux)

Structure du rapport (8 chapitres) :
  §1 — Contexte & Qualité des données
  §2 — Résultats GLM (Poisson / Gamma / Tweedie)
  §3 — Classement ML (8 modèles) & Sélection finale
  §4 — Validation des hypothèses actuarielles (H1–H4)
  §5 — Backtesting temporel Walk-Forward & Test A/E
  §6 — Relativités tarifaires exp(β) — GLM Poisson
  §7 — Commentaire actuariel
  §8 — Recommandations & Audit Trail

Auteur   : ActuarIA v1.0
Version  : 1.0.0
"""

from __future__ import annotations
import base64, io, logging, re
from core.conformite_reglementaire import (
    avertissement_walk_forward, synthese_exclusions, synthese_alertes_experience,
    synthese_modele_dl,
)
from core.qualite_donnees import synthese_qualite_donnees
from core.plan_tarifaire import synthese_colonnes_plan_manquantes
from core.mapping_client import synthese_mapping
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from core import format_fr as F
from core import frontiere_llm


logger = logging.getLogger('actuaria.tarif.rapport')

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY      = '#0F2E52'
NAVY_MID  = '#1B3A5C'
NAVY_L    = '#1E3A5F'
GOLD      = '#C9A84C'
GOLD_L    = '#E2C97E'
ROUGE     = '#C0392B'
VERT      = '#1E8449'
ORANGE    = '#E67E22'
SLATE     = '#8A9BB0'
BG        = '#F5F7FA'
WHITE     = '#FFFFFF'
TEXT      = '#1C2B3A'

# ── Graphiques V3 (core/charts_tarif) — rendu HTML natif interactif ─────────────
# plotly.js chargé UNE FOIS en CDN dans le <head> ; chaque figure rendue via
# to_html(include_plotlyjs=False). Import gardé : si plotly/charts absents, les
# figures sont simplement omises (rétro-compatible, comme synthese_mapping).
try:
    import plotly.offline as _po
    from core.charts_tarif import CONFIG_PLOTLY as _CFG_PLOTLY
    _PLOTLYJS_CDN = (
        f'<script src="https://cdn.plot.ly/plotly-{_po.get_plotlyjs_version()}'
        f'.min.js" charset="utf-8"></script>')
    _CHARTS_HTML_OK = True
except Exception:
    _CFG_PLOTLY = {'displayModeBar': False}
    _PLOTLYJS_CDN = ''
    _CHARTS_HTML_OK = False

# ── Helpers formatage ─────────────────────────────────────────────────────────
# ⚠️ TROIS FORMATEURS ONT ÉTÉ RETIRÉS ICI — `_f`, `_pct` et `_s`. Ils
# reproduisaient la convention d'A7 et n'étaient appelés NULLE PART : vulture
# les signalait, et les 53 nombres du rapport étaient formatés en ligne, chacun
# à sa façon. Le rapport RESSEMBLAIT à A7 sans en appliquer un seul formatage —
# d'où « 2,435 » à l'anglaise à côté de « 10308 » sans séparateur. La
# convention vit désormais dans `core.format_fr`, en un seul endroit.

def _clean(txt) -> str:
    if not txt: return ''
    txt = re.sub(r'[■□▪▸►═╔╗╚╝║─]+', '', str(txt))
    txt = re.sub(r'={4,}', '', txt)
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    return txt.strip()

def _statut_col(s: str) -> str:
    return {'VERT': VERT, 'AMBRE': ORANGE, 'ROUGE': ROUGE}.get(s.upper(), SLATE)

def _statut_emoji(s: str) -> str:
    return {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}.get(s.upper(), '⚪')


# =============================================================================
#  SYSTEM PROMPT CLAUDE API
# =============================================================================
SYSTEM_PROMPT_TARIF = """\
Tu es un actuaire Non-Vie senior certifié par l'Institut des Actuaires (IA), \
expert en tarification Solvabilité 2 et IFRS 17, avec 20 ans d'expérience \
auprès de mutuelles et grands groupes d'assurance.

Tu rédiges le commentaire actuariel d'un rapport de tarification Non-Vie \
destiné à l'actuaire désigné, au Comité des risques et à l'ACPR.

RÈGLES ABSOLUES :
0. FORMAT : §N — TITRE pour les sections, ### pour les sous-titres, \
**gras** pour les termes importants. PAS de tableaux Markdown. Sépare les sections par une ligne vide.
1. LANGUE : Français professionnel actuariel.
2. RIGUEUR : Chaque affirmation est justifiée par les données fournies.
3. CHIFFRES : Gini à 4 décimales, AIC arrondi, p-values à 4 décimales.
4. RÉFÉRENCES : Mildenhall (1999) GLM, Goldburd (2016) GLM P&C, \
Denuit (2019) calibration, Siddiqi (2006) PSI, Wüthrich & Merz (2019) CANN.
5. ALERTES : Ne jamais minimiser. Présenter avec l'implication tarifaire réelle.

STRUCTURE OBLIGATOIRE EN 7 SECTIONS :
§1 — CONTEXTE ET QUALITÉ DES DONNÉES
§2 — VALIDATION DES HYPOTHÈSES ACTUARIELLES (H1–H4)
§3 — RÉSULTATS GLM ET RELATIVITÉS TARIFAIRES
§4 — COMPARAISON DES MODÈLES ML ET SÉLECTION
§5 — BACKTESTING WALK-FORWARD ET TEST A/E
§6 — RISQUES IDENTIFIÉS ET POINTS D'ATTENTION
§7 — CONCLUSION ET RECOMMANDATIONS POUR L'ACTUAIRE DÉSIGNÉ\
"""


def _construire_contexte_tarif(
    result_a3: Dict, result_a4: Dict, result_a6: Dict,
    branche: str, arrete: str
) -> str:
    met3  = result_a3.get('metriques', {}) if result_a3 else {}
    hyp3  = result_a3.get('hypotheses', {}) if result_a3 else {}
    rels  = result_a3.get('relativites_poisson', {}) if result_a3 else {}
    cl4   = result_a4.get('classement', []) if result_a4 else []
    hyp4  = result_a4.get('hypotheses', {}) if result_a4 else {}
    bt6   = result_a6.get('backtest', {}) if result_a6 else {}
    val6  = result_a6.get('validation_selection', {}) if result_a6 else {}
    prod  = result_a6.get('modele_production', {}) if result_a6 else {}

    m_poi = met3.get('poisson', {})
    gini_p = m_poi.get('gini', 0)
    aic_p  = m_poi.get('aic', 0)
    vars_r = m_poi.get('vars_retenues', [])

    # Modules avancés P2 (A3) et gouvernance (A6)
    cred6 = result_a3.get('credibilite', {}) if result_a3 else {}
    geo6  = result_a3.get('lissage_geo', {}) if result_a3 else {}
    at6   = result_a6.get('audit_trail', {}) if result_a6 else {}

    lines = [
        f"DOSSIER TARIFICATION — {branche.upper()} — Arrêté {arrete}",
        "",
        "=== DONNÉES ===",
        f"Nb obs train : {m_poi.get('nb_obs_train', '—')} | Nb obs test : {m_poi.get('nb_obs_test', '—')}",
        f"Variables retenues : {', '.join(vars_r) or '—'}",
        "",
        "=== GLM ===",
        f"Poisson : Gini={gini_p:.4f} | AIC={aic_p:.0f} | Pseudo-R²={m_poi.get('pseudo_r2',0):.4f}",
        f"Gamma   : Gini={met3.get('gamma',{}).get('gini',0):.4f} | AIC={met3.get('gamma',{}).get('aic',0):.0f}",
        f"Tweedie : Gini={met3.get('tweedie',{}).get('gini',0):.4f} | AIC={met3.get('tweedie',{}).get('aic',0):.0f}",
        "",
        "=== HYPOTHÈSES GLM ===",
        f"H1 Sur-dispersion : {hyp3.get('h1_poisson',{}).get('statut','?')} | Var/E={hyp3.get('h1_poisson',{}).get('ratio_disp','—')}",
        f"H2 Homoscédasticité : {hyp3.get('h2_homosc',{}).get('statut','?')} | Ratio var={hyp3.get('h2_homosc',{}).get('ratio_variance','—')}",
        f"H3 Gini : {hyp3.get('h3_ajustement',{}).get('statut','?')} | Gini max={hyp3.get('h3_ajustement',{}).get('gini_max','—')}",
        f"H4 Stabilité relativités : {hyp3.get('h4_stabilite',{}).get('statut','?')} | CV max={hyp3.get('h4_stabilite',{}).get('cv_max','—')} | Instables={hyp3.get('h4_stabilite',{}).get('vars_instables',[])}",
        "",
        "=== RELATIVITÉS POISSON (top 5) ===",
    ]
    for var, d in list(rels.items())[:5]:
        lines.append(f"  {var} : exp(β)={d.get('relativite',0):.4f} | p={d.get('pvalue',0):.4f} | {d.get('sens','')} | sig={'oui' if d.get('significatif') else 'non'}")

    # === CRÉDIBILITÉ BÜHLMANN-STRAUB (P2) ===
    lines += ["", "=== CRÉDIBILITÉ BÜHLMANN-STRAUB ==="]
    if cred6.get('appliquee'):
        lines.append(
            f"Appliquée : k={cred6.get('k',0):.4f} | Z_moyen={cred6.get('z_moyen',0):.4f} "
            f"| n_groupes={cred6.get('n_groupes',0)} | colonne={cred6.get('col_groupe','—')}"
        )
    else:
        lines.append(f"Non applicable : {cred6.get('raison', '—')}")

    # === LISSAGE GÉOGRAPHIQUE (P2) ===
    lines += ["", "=== LISSAGE GÉOGRAPHIQUE ==="]
    if geo6.get('applique'):
        lines.append(
            f"Appliqué : méthode={geo6.get('methode','—')} | n_zones={geo6.get('n_zones',0)} "
            f"| source={geo6.get('source_prime','—')}"
        )
    else:
        lines.append(f"Non applicable : {geo6.get('raison', '—')}")

    # Mapping client (couche 2) — section CONDITIONNELLE (rien si aucun mapping,
    # contrairement aux sections qualité/colonnes qui affichent un repli). Même
    # source-unique partagée avec Excel A6 / rapport équipe.
    _synth_map6 = synthese_mapping(result_a6.get('rapport_mapping') if result_a6 else None)
    _lignes_map6 = (["=== MAPPING CLIENT (renommage du fichier avant tarification) ===",
                     _synth_map6, ""] if _synth_map6 else [])

    # ⚠️ LE CLASSEMENT ÉTAIT EXTRAIT PUIS JETÉ — `ruff F841` le signalait depuis
    # toujours. Le prompt ordonne pourtant « §4 — COMPARAISON DES MODÈLES ML ET
    # SÉLECTION », et sa règle 9 interdit « les phrases génériques sans
    # données » : le modèle recevait UN modèle et devait en comparer sept.
    # Mesuré sur le rapport réel produit avant ce lot : §4 citait 1 modèle sur
    # 7, aucun contrôle de sélection, et pas une occurrence de « comparaison »
    # hors de son propre titre. Il n'inventait pas — il remplissait la section
    # avec autre chose, ce qui est le bon comportement face à un contexte vide.
    lines += ["", f"=== CLASSEMENT ML ({len(cl4)} modèle(s) comparé(s)) ==="]
    for rang, m in enumerate(cl4, 1):
        # ⚠️ « NON CALCULÉ » NE VAUT PAS ZÉRO : un Gini à 0,0000 affirmerait un
        # pouvoir discriminant nul. Même garde que le tableau du rapport.
        def _n(cle, dec=4):
            v = m.get(cle)
            return f'{float(v):.{dec}f}' if isinstance(v, (int, float)) else '—'
        lines.append(
            f"{rang}. {m.get('modele','—')} | famille={m.get('famille','—')} | "
            f"Gini={_n('gini_test')} | RMSE={_n('rmse_test')} | "
            f"overfit={_n('overfit_ratio', 3)} | score={_n('score_global')}")
    if not cl4:
        lines.append("aucun classement transmis — la comparaison des modèles "
                     "ne peut pas être commentée")

    lines += [
        "",
        "=== ML — MODÈLE RETENU ===",
        f"Modèle production : {prod.get('modele','—')} | Score={prod.get('score_global',0):.4f} | Gini={prod.get('gini_test',0):.4f}",
        f"Overfit ratio : {prod.get('overfit_ratio',0):.3f}",
    ]

    # ⚠️ LES TROIS CONTRÔLES DE SÉLECTION, EUX AUSSI EXTRAITS PUIS JETÉS. Ils
    # disent si la comparaison était robuste, si les modèles se distinguaient,
    # et si le choix est cohérent avec le classement. Sans eux, la SÉLECTION du
    # titre de la section n'a rien derrière elle.
    lines += ["", "=== CONTRÔLES DE SÉLECTION ==="]
    for _cle, _libelle in (('c1_nb_modeles', 'C1 — nombre de modèles comparés'),
                           ('c2_ecart_gini', 'C2 — écart de Gini entre modèles'),
                           ('c3_coherence', 'C3 — cohérence du modèle retenu')):
        _c = val6.get(_cle) or {}
        lines.append(f"{_libelle} : {_c.get('statut', 'non calculé')} | "
                     f"{_c.get('message', '—')}")

    lines += [
        "",
        "=== HYPOTHÈSES ML ===",
        f"H1 Overfitting : {hyp4.get('h1_overfitting',{}).get('statut','?')} | ratio={hyp4.get('h1_overfitting',{}).get('ratio','—')}",
        f"H2 PSI réel : {hyp4.get('h2_psi',{}).get('statut','?')} | PSI={hyp4.get('h2_psi',{}).get('psi','—')}",
        f"H3 Gini : {hyp4.get('h3_gini',{}).get('statut','?')} | Gini={hyp4.get('h3_gini',{}).get('gini','—')}",
        f"H4 Calibration : {hyp4.get('h4_calibration',{}).get('statut','?')} | écart moy={hyp4.get('h4_calibration',{}).get('ecart_moy_pct','—')}%",
        "",
        "=== BACKTESTING A/E (walk-forward recalibré) ===",
        f"A/E ratio : {bt6.get('ae_ratio','—')} | {bt6.get('interpretation','—')}",
        f"Walk-forward : {bt6.get('n_fenetres','—')} fenêtres | stabilité={bt6.get('stabilite_wf','—')} | CV={bt6.get('ae_cv_wf','—')}",
        f"Modèle recalibré par fenêtre : {bt6.get('modele_recalibre','—')} | Gini WF moyen={bt6.get('gini_wf_moyen','—')}",
        # Audit V11 : sans cette ligne, le modèle de narration ignorait que la
        # validation temporelle avait pu porter sur un AUTRE modèle que celui
        # retenu — et rédigeait un commentaire faussement rassurant.
        (avertissement_walk_forward(bt6) or
         "Validation temporelle : porte bien sur le modèle de production."),
        "",
        "=== COLONNES ÉCARTÉES DE LA MATRICE X (conformité) ===",
        (synthese_exclusions(result_a6.get('exclusions_conformite') if result_a6 else None)
         or "Aucune colonne écartée : toutes les variables candidates sont conformes."),
        "",
        "=== SINISTRALITÉ PASSÉE CONSERVÉE (à vérifier par l'actuaire) ===",
        (synthese_alertes_experience(result_a6.get('alertes_conformite') if result_a6 else None)
         or "Aucune variable d'expérience passée à signal atypique."),
        "",
        "=== MODÈLE DEEP LEARNING EN PRODUCTION (validation humaine) ===",
        (synthese_modele_dl(result_a6.get('modele_production') if result_a6 else None,
                            result_a6.get('valide_par_actuaire_dl') if result_a6 else None,
                            at6.get('timestamp'))
         or "Aucun modèle Deep Learning retenu : pas de validation humaine spécifique requise."),
        "",
        "=== QUALITÉ DES DONNÉES (traitements de la couche générique, chemin déclaratif) ===",
        (synthese_qualite_donnees(result_a6.get('rapport_qualite') if result_a6 else None)
         or "Aucun traitement de qualité de données à signaler (ou couche non exécutée sur ce chemin)."),
        "",
        "=== COLONNES DU PLAN NON PRODUITES (modèle amputé) ===",
        (synthese_colonnes_plan_manquantes(
            result_a6.get('colonnes_plan_manquantes') if result_a6 else None)
         or "Aucune : toutes les colonnes déclarées au plan ont été produites."),
        "",
        *_lignes_map6,
        "=== GOUVERNANCE DU PROFIL DE PONDÉRATION ===",
        f"Profil retenu : {at6.get('profil_ponderation','—')} | Environnement={at6.get('environnement','—')}",
        f"Validé par : {at6.get('profil_valide_par') or 'NON VALIDÉ'} | Conforme={at6.get('gouvernance_ok','—')}",
        "",
        "Rédige le commentaire actuariel complet en 7 sections, en intégrant "
        "la crédibilité, le lissage géographique et la gouvernance du profil "
        "si ces éléments sont pertinents pour la branche analysée.",
    ]
    return '\n'.join(lines)


# ⚠⚠ CE BLOC AFFIRMAIT UNE GARANTIE QUE LE MODÈLE NE PERMET PLUS. Il
# prescrivait `temperature=0` comme socle de reproductibilité réglementaire.
# MESURÉ CONTRE L'API le 2026-08-07 : ce modèle REFUSE le paramètre (400,
# « deprecated for this model »), quelle que soit sa valeur. La prescription
# ne produisait donc pas du déterminisme : elle produisait un appel rejeté,
# et un repli muet sur le commentaire d'agent.
#
# CE QUI RESTE VRAI, ET QUI ÉTAIT DÉJÀ ÉCRIT ICI : la reproductibilité d'une
# narration n'a JAMAIS été garantie bit-à-bit. Des variations d'infrastructure
# côté fournisseur (répartition de charge, arrondis flottants liés au batching,
# mises à jour internes non annoncées par un changement de nom de modèle)
# peuvent produire un texte différent sur les mêmes entrées. Le paramètre
# retiré apportait donc moins qu'annoncé, et son retrait ne coûte pas la
# garantie — celle-ci n'existait pas.
#
# Réf. : GL EIOPA ORSA GL 56 (déterminisme des processus de calcul S2) ;
# ACPR-2022-P-01 (auditabilité des sorties IA). Ce qui satisfait ces exigences
# n'est pas un réglage d'échantillonnage, c'est la RELECTURE par l'actuaire
# responsable, ci-dessous.
#
# Conséquence pour l'usage réglementaire : le commentaire narratif généré
# doit être traité comme une AIDE À LA RÉDACTION, relue et validée par
# l'actuaire responsable avant diffusion — jamais comme une sortie de
# calcul déterministe au même titre que les modèles GLM/ML eux-mêmes
# (qui, eux, sont reproductibles bit-à-bit sur la même version de
# statsmodels/scikit-learn et les mêmes données).
# L'identifiant vient de la frontière (C1) ; ce nom reste parce que le pied
# de page du rapport le cite au lecteur.
CLAUDE_MODEL_TARIF = frontiere_llm.MODELE_RECENT

# ⚠️ TEMPERATURE RETIRÉE — MESURÉ CONTRE L'API le 2026-08-07 : ce modèle REFUSE
# le paramètre (400, « deprecated for this model »), quelle que soit sa valeur.
# CE SITE ÉTAIT EN PANNE SILENCIEUSE : chaque rapport de tarification tentait
# l'appel, était rejeté, et retombait sur le commentaire d'agent — l'actuaire
# lisait « Source : commentaire_agent » sans savoir que la plateforme avait
# essayé et échoué. `None` = paramètre non transmis.
CLAUDE_TEMPERATURE_TARIF = None

# Sources de narration. TROIS REPLIS, TROIS NOMS : un repli d'ENVIRONNEMENT est
# attendu ; un repli sur REQUÊTE REFUSÉE est un défaut de configuration ; un
# repli sur RÉPONSE INEXPLOITABLE veut dire que le service a répondu et qu'on
# n'a rien su en faire. Les confondre, c'est ce qui a coûté six réponses reçues.
SRC_API = 'claude_api'
SRC_REPLI = 'commentaire_agent'
SRC_DEFAUT = 'commentaire_agent (appel refuse — defaut de configuration)'
SRC_REPONSE = 'commentaire_agent (reponse recue mais inexploitable)'

def _narration_claude(result_a3, result_a4, result_a6, branche, arrete) -> Tuple[str, str]:
    repli = SRC_REPLI
    try:
        ctx = _construire_contexte_tarif(result_a3, result_a4, result_a6, branche, arrete)
        resp = frontiere_llm.appeler(
            modele=CLAUDE_MODEL_TARIF, max_tokens=6000,
            temperature=CLAUDE_TEMPERATURE_TARIF,
            systeme=SYSTEM_PROMPT_TARIF,
            messages=[{'role': 'user', 'content': ctx}],
            cle=frontiere_llm.cle_api_ou_secrets(),
        )
        return frontiere_llm.texte_des_blocs(resp), SRC_API
    except frontiere_llm.RequeteRefusee as e:
        # ⚠️ CE N'EST PAS UNE DÉGRADATION, C'EST UN DÉFAUT. Journalisé en
        # ERREUR, et le livrable le dit — c'est ce qui manquait.
        logger.error(f'Narration NON generee — requete refusee par la '
                     f'frontiere : {e}')
        repli = SRC_DEFAUT
    except frontiere_llm.ReponseInexploitable as e:
        # ⚠️ L'API A REPONDU. Le dire est le contraire de ce que ce site
        # faisait : il journalisait « Claude API indisponible » sur un 200.
        logger.error(f'Narration NON generee — le service a repondu mais sa '
                     f'reponse est inexploitable : {e}')
        repli = SRC_REPONSE
    except Exception as e:
        logger.warning(f'Narration non generee : {e}')
    # Fallback : commentaire agent
    for r in [result_a6, result_a4, result_a3]:
        if r and r.get('commentaire'):
            return _clean(r['commentaire']), repli
    return '', 'aucune'


# =============================================================================
#  HTML
# =============================================================================

def _md_to_html(txt: str) -> str:
    """Conversion Markdown minimal → HTML."""
    if not txt: return ''
    txt = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', txt)
    txt = re.sub(r'\*(.+?)\*', r'<em>\1</em>', txt)
    txt = re.sub(r'^§(\d+)\s*[—\-–]\s*(.+)$', r'<h3 class="s-head">§\1 — \2</h3>', txt, flags=re.MULTILINE)
    txt = re.sub(r'^###\s+(.+)$', r'<h4>\1</h4>', txt, flags=re.MULTILINE)
    txt = re.sub(r'^-\s+(.+)$', r'<li>\1</li>', txt, flags=re.MULTILINE)
    txt = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', txt)
    paragraphs = []
    for line in txt.split('\n'):
        line = line.strip()
        if not line or line.startswith('<h') or line.startswith('<ul') or line.startswith('<li'):
            paragraphs.append(line)
        else:
            paragraphs.append(f'<p>{line}</p>')
    return '\n'.join(paragraphs)


def export_html(
    result_a3: Dict = None, result_a4: Dict = None, result_a6: Dict = None,
    ref_client: str = '', arrete: str = '', audit_id: str = '',
    narration_calculee: Optional[Tuple[str, str]] = None,
) -> str:
    """Génère le rapport HTML tarification. Retourne str HTML ou ''.

    `narration_calculee` : le couple (texte, source) déjà obtenu, à réutiliser.
    ⚠️ SANS LUI, CHAQUE FORMAT PAIE SA PROPRE NARRATION — et rien ne garantit
    qu'ils obtiennent la même. Mesuré sur un rapport réel : le HTML portait les
    18 089 caractères de commentaire actuariel, le Word portait le dépôt
    technique de l'agent. Le fichier qui part chez un commissaire n'avait pas
    le commentaire. `generer_rapport_tarification` calcule donc UNE fois et
    transmet ; appelé seul, cet export calcule pour lui-même comme avant.
    """
    now    = datetime.now().strftime('%d/%m/%Y %H:%M')
    arr    = arrete or datetime.now().strftime('%d/%m/%Y')
    branche = (result_a6 or result_a3 or {}).get('branche', 'non_vie')
    statut  = (result_a6 or result_a3 or {}).get('statut_rag', 'AMBRE')
    s_col   = _statut_col(statut)
    s_emoji = _statut_emoji(statut)

    narration, n_src = (
        narration_calculee if narration_calculee is not None
        else _narration_claude(result_a3, result_a4, result_a6, branche, arr))
    narr_html = _md_to_html(narration) if narration else '<p><em>Narration non disponible.</em></p>'

    met3  = (result_a3 or {}).get('metriques', {})
    rels  = (result_a3 or {}).get('relativites_poisson', {})
    cl4   = (result_a4 or {}).get('classement', [])
    hyp3  = (result_a3 or {}).get('hypotheses', {})
    hyp4  = (result_a4 or {}).get('hypotheses', {})
    bt6   = (result_a6 or {}).get('backtest', {})
    prod  = (result_a6 or {}).get('modele_production', {})
    val6  = (result_a6 or {}).get('validation_selection', {})
    # Priorité A6 (le plus complet — gouvernance + WF recalibré) > A4 > A3
    at    = (
        (result_a6 or {}).get('audit_trail')
        or (result_a4 or {}).get('audit_trail')
        or (result_a3 or {}).get('audit_trail')
        or {}
    )

    # ── Figures V3 (core/charts_tarif) — OPTIONNELLES (absente → rien affiché) ──
    _figs_html = []
    if _CHARTS_HTML_OK:
        for _src, _key, _lbl in [
            (result_a3, 'chart_relativites_glm',          'Relativités GLM Poisson  exp(β)'),
            (result_a3, 'chart_residus_qq',               'QQ-plot des résidus de Pearson'),
            (result_a3, 'chart_distribution_predictions', 'Distribution des fréquences prédites'),
            (result_a4, 'chart_shap_summary',             'Importance SHAP — meilleur modèle ML'),
            (result_a6, 'chart_lift_decile',              'Lift par décile de risque prédit'),
            (result_a6, 'chart_lorenz_gini',              'Courbe de Lorenz & Gini'),
            (result_a6, 'chart_walkforward_ae',           'Backtesting walk-forward A/E'),
        ]:
            _fig = ((_src or {}).get('graphiques', {}) or {}).get(_key)
            if _fig is None:
                continue
            try:
                _frag = _fig.to_html(full_html=False, include_plotlyjs=False,
                                     config=_CFG_PLOTLY)
                _figs_html.append(
                    f'<div style="margin:16px 0;"><div style="color:{GOLD_L};'
                    f'font-weight:600;font-size:13px;margin-bottom:6px;">{_lbl}</div>'
                    f'{_frag}</div>')
            except Exception as _e:
                logger.debug(f"Figure {_key} non rendue : {_e}")
    _plotly_cdn = _PLOTLYJS_CDN if _figs_html else ''
    _section_figures = (
        '<!-- FIGURES V3 --><div class="section"><div class="section-head">'
        'Graphiques de validation</div><div class="section-body">'
        + ''.join(_figs_html) + '</div></div>'
    ) if _figs_html else ''

    def _row(cells, header=False, num=()):
        """Une ligne de tableau. `num` = les index des colonnes NUMÉRIQUES.

        ⚠️ L'ALIGNEMENT SE DÉCLARE, IL NE SE DEVINE PAS. Un tiret « — » d'une
        colonne de chiffres doit s'aligner comme un chiffre ; une heuristique
        sur le contenu de la cellule ne peut pas le savoir, la colonne si.
        Mesuré avant ce lot : 41 cellules numériques sur 95 alignées à droite,
        et les deux tableaux GLM — ceux qu'un actuaire lit en premier — les
        avaient TOUTES à gauche, sous des en-têtes qui annonçaient « right ».
        """
        tag = 'th' if header else 'td'
        return '<tr>' + ''.join(
            f'<{tag} class="right">{c}</{tag}>' if i in num
            else f'<{tag}>{c}</{tag}>'
            for i, c in enumerate(cells)) + '</tr>'

    def _hyp_row(key, label, val_key='', val=''):
        # Cherche dans hyp3 (GLM), puis hyp4 (ML) — clés toujours distinctes.
        # Retourne '' si l'hypothèse n'a pas été calculée (pas de ligne vide dans le HTML).
        h = hyp3.get(key) or hyp4.get(key) or {}
        if not h:
            return ''
        st = h.get('statut', '?')
        em = _statut_emoji(st)
        brut = h.get(val_key, val)
        # ⚠️ LA MÊME COLONNE AFFICHAIT 1, 3 ET 4 DÉCIMALES SELON LA LIGNE —
        # « 1.0 » à côté de « 1.2176 ». Une précision se justifie, elle ne se
        # choisit pas ligne par ligne. Une valeur non numérique (un libellé)
        # passe telle quelle ; une absence rend le tiret de la convention.
        valeur = (F.nombre(brut, F.DEC_GINI)
                  if isinstance(brut, (int, float)) and not isinstance(brut, bool)
                  else (str(brut)[:60] if brut else F.ABSENT))
        return _row([label,
                     f'<span class="badge-{st.lower()}">{em} {st}</span>',
                     valeur,
                     str(h.get('conseil', ''))[:80]], num=(2,))

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rapport Tarification — ActuarIA</title>
{_plotly_cdn}
<style>
:root {{
  --navy:{NAVY}; --navy-mid:{NAVY_MID}; --gold:{GOLD}; --gold-l:{GOLD_L};
  --rouge:{ROUGE}; --vert:{VERT}; --orange:{ORANGE}; --slate:{SLATE};
  --bg:{BG}; --white:{WHITE}; --text:{TEXT};
}}
*{{box-sizing:border-box; margin:0; padding:0;}}
body{{font-family:'Segoe UI',Arial,sans-serif; background:var(--bg); color:var(--text); font-size:13px; line-height:1.6;}}
.page{{max-width:1060px; margin:0 auto; padding:32px 24px;}}
/* Header */
.header{{background:var(--navy); color:#fff; padding:28px 32px; border-radius:8px; margin-bottom:28px;}}
.header h1{{font-size:22px; color:var(--gold); letter-spacing:.5px;}}
.header .sub{{font-size:13px; color:var(--gold-l); margin-top:4px;}}
.header .meta{{font-size:11px; color:#8a9bb0; margin-top:10px; display:flex; gap:24px; flex-wrap:wrap;}}
.badge{{display:inline-block; padding:3px 10px; border-radius:4px; font-size:11px; font-weight:700; color:#fff;}}
.badge-vert{{background:var(--vert);}} .badge-ambre{{background:var(--orange);}} .badge-rouge{{background:var(--rouge);}}
/* Sections */
.section{{background:var(--white); border-radius:8px; margin-bottom:20px; box-shadow:0 1px 4px rgba(0,0,0,.07); overflow:hidden;}}
.section-head{{background:var(--navy-mid); color:var(--gold); padding:10px 18px; font-size:13px; font-weight:700;}}
.section-body{{padding:16px 18px;}}
/* Tables */
table{{width:100%; border-collapse:collapse; font-size:12px; margin-top:8px;}}
th{{background:var(--navy); color:var(--gold); padding:7px 10px; text-align:left;}}
td{{padding:6px 10px; border-bottom:1px solid #e8edf2;}}
tr:nth-child(even) td{{background:#f7f9fc;}}
.right{{text-align:right;}}
.center{{text-align:center;}}
/* Narration */
.narration{{line-height:1.7; font-size:12.5px;}}
.narration h3.s-head{{color:var(--navy); font-size:14px; margin:18px 0 6px; border-left:3px solid var(--gold); padding-left:8px;}}
.narration h4{{color:var(--navy-mid); font-size:13px; margin:10px 0 4px;}}
.narration p{{margin:4px 0;}}
.narration ul{{margin:4px 0 4px 16px;}}
/* Footer */
.footer{{text-align:center; font-size:10px; color:var(--slate); margin-top:28px; padding:10px;}}
.kpi-grid{{display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:10px; margin-top:8px;}}
.kpi{{background:var(--bg); border:1px solid #dde4ee; border-radius:6px; padding:10px 12px;}}
.kpi-label{{font-size:10px; color:var(--slate); text-transform:uppercase; letter-spacing:.4px;}}
.kpi-value{{font-size:18px; font-weight:700; color:var(--navy); margin-top:2px;}}
</style>
</head>
<body>
<div class="page">

<!-- HEADER -->
<div class="header">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px;">
    <div>
      <h1>📊 Rapport de Tarification Non-Vie</h1>
      <div class="sub">{branche.replace('_',' ').title()} · Arrêté {arr}</div>
    </div>
    <div style="text-align:right;">
      <span class="badge badge-{statut.lower()}">{s_emoji} {statut}</span>
      <div class="sub" style="margin-top:6px;">{ref_client or 'Client à renseigner'}</div>
    </div>
  </div>
  <div class="meta">
    <span>🏢 ActuarIA v1.0</span>
    <span>📅 {now}</span>
    <span>🔑 {audit_id or 'N/A'}</span>
    <span>🧠 Narration : {n_src}</span>
  </div>
</div>

<!-- §1 RÉSULTATS GLM -->
<div class="section">
  <div class="section-head">§1 — Résultats GLM Poisson / Gamma / Tweedie</div>
  <div class="section-body">
    <table>
      <tr><th>Modèle</th>{''.join(f'<th class="right">{h}</th>' for h in ['Gini test','AIC','Déviance','Pseudo-R²','Vars retenues'])}</tr>
"""
    for modele in ['poisson', 'gamma', 'tweedie']:
        m = met3.get(modele, {})
        if m:
            html += _row([
                modele.capitalize(),
                F.nombre(m.get('gini'), F.DEC_GINI),
                F.nombre(m.get('aic'), 0),
                F.nombre(m.get('deviance'), 2),
                F.nombre(m.get('pseudo_r2'), F.DEC_GINI),
                F.nombre(m.get('nb_vars_retenues'), 0),
            ], num=(1, 2, 3, 4, 5))
    html += """    </table>
  </div>
</div>

<!-- §2 RELATIVITÉS POISSON -->
<div class="section">
  <div class="section-head">§2 — Relativités Tarifaires GLM Poisson — exp(β)</div>
  <div class="section-body">
    <table>
      <tr><th>Variable</th><th class="right">β</th><th class="right">Relativité exp(β)</th><th class="right">IC 95% bas</th><th class="right">IC 95% haut</th><th class="right">p-value</th><th class="center">Significatif</th><th class="center">Sens</th></tr>
"""
    for var, d in sorted(rels.items(), key=lambda x: -abs(x[1].get('beta',0))):
        sens_col = f'color:{VERT}' if d.get('sens')=='allegant' else f'color:{ROUGE}'
        html += _row([
            var,
            F.nombre(d.get('beta'), F.DEC_GINI),
            f"<strong>{F.nombre(d.get('relativite'), F.DEC_GINI)}</strong>",
            F.nombre(d.get('ic95_low'), F.DEC_GINI),
            F.nombre(d.get('ic95_high'), F.DEC_GINI),
            # Audit V7 IMPORTANT : garde NA — était toujours affiché "0.0000"
            # (indiscernable d'une vraie p-value nulle) si la clé était absente.
            F.nombre(d.get('pvalue'), F.DEC_GINI),
            '✓' if d.get('significatif') else '·',
            f'<span style="{sens_col};font-weight:600">{d.get("sens","")}</span>',
        ], num=(1, 2, 3, 4, 5))
    html += """    </table>
  </div>
</div>

<!-- §3 CLASSEMENT ML -->
<div class="section">
  <div class="section-head">§3 — Classement ML — Grille Multicritères (Gini 40% · Stabilité 30% · Interprét. 20% · RMSE 10%)</div>
  <div class="section-body">
    <table>
      <tr><th>#</th><th>Modèle</th><th>Famille</th><th class="right">Gini test</th><th class="right">RMSE test</th><th class="right">Overfit</th><th class="right">Score global</th><th class="center">⭐</th></tr>
"""
    for rank, m in enumerate(cl4, 1):
        star = '⭐' if rank == 1 else ''
        style = 'font-weight:700; background:#f0f7ff;' if rank == 1 else ''
        html += f'<tr style="{style}">'
        html += f'<td>{rank}</td><td>{m.get("modele","")}</td><td>{m.get("famille","")}</td>'
        html += f'<td class="right">{F.nombre(m.get("gini_test"), F.DEC_GINI)}</td>'
        html += f'<td class="right">{F.nombre(m.get("rmse_test"), F.DEC_GINI)}</td>'
        html += f'<td class="right">{F.nombre(m.get("overfit_ratio"), F.DEC_RATIO)}</td>'
        # Audit V7 IMPORTANT : garde NA — était toujours affiché "0.0000".
        html += f'<td class="right">{F.nombre(m.get("score_global"), F.DEC_GINI)}</td>'
        html += f'<td class="center">{star}</td></tr>\n'
    html += """    </table>
  </div>
</div>

<!-- §4 HYPOTHÈSES H1–H4 -->
<div class="section">
  <div class="section-head">§4 — Validation des Hypothèses Actuarielles H1–H4</div>
  <div class="section-body">
    <table>
      <tr><th>Hypothèse</th><th>Statut</th><th class="right">Valeur</th><th>Conseil</th></tr>
"""
    html += _hyp_row('h1_poisson','H1 — Sur-dispersion Poisson','ratio_disp')
    html += _hyp_row('h2_homosc','H2 — Homoscédasticité résidus Pearson','ratio_variance')
    html += _hyp_row('h3_ajustement','H3 — Qualité ajustement (Gini)','gini_max')
    html += _hyp_row('h4_stabilite','H4 — Stabilité relativités bootstrap','cv_max')
    html += _hyp_row('h1_overfitting','H1 ML — Overfitting','ratio')
    html += _hyp_row('h2_psi','H2 ML — PSI réel','psi')
    html += _hyp_row('h3_gini','H3 ML — Performance Gini','gini')
    html += _hyp_row('h4_calibration','H4 ML — Calibration','ecart_moy_pct')
    html += """    </table>
  </div>
</div>

<!-- §5 BACKTESTING -->
<div class="section">
  <div class="section-head">§5 — Backtesting Walk-Forward & Test A/E</div>
  <div class="section-body">
"""
    if bt6.get('disponible'):
        ae = bt6.get('ae_ratio', 0)
        ae_col = VERT if 0.95<=ae<=1.05 else ORANGE if 0.90<=ae<=1.10 else ROUGE
        html += f"""
    <div class="kpi-grid">
      <div class="kpi"><div class="kpi-label">A/E ratio (N-1→N)</div><div class="kpi-value" style="color:{ae_col}">{ae:.4f}</div></div>
      <div class="kpi"><div class="kpi-label">Interprétation</div><div class="kpi-value" style="font-size:13px;">{bt6.get('interpretation','—')}</div></div>
      <div class="kpi"><div class="kpi-label">Stabilité Walk-Forward</div><div class="kpi-value" style="font-size:13px;">{bt6.get('stabilite_wf','—')}</div></div>
      <div class="kpi"><div class="kpi-label">Fenêtres testées</div><div class="kpi-value">{bt6.get('n_fenetres','—')}</div></div>
      <div class="kpi"><div class="kpi-label">CV A/E WF</div><div class="kpi-value">{bt6.get('ae_cv_wf','—')}</div></div>
      <div class="kpi"><div class="kpi-label">Fenêtres ROUGE</div><div class="kpi-value" style="color:{ROUGE}">{bt6.get('n_fenetres_rouge','—')}</div></div>
    </div>
"""
        wf = bt6.get('walk_forward', [])
        if wf:
            html += """
    <table style="margin-top:12px;">
      <tr><th>Année test</th><th class="right">N train</th><th class="right">N test</th><th class="right">Moy train</th><th class="right">Moy test</th><th class="right">A/E ratio</th><th class="center">Statut</th></tr>
"""
            for w in wf:
                st_w = w.get('statut','')
                bg   = {'VERT':'#eaf3de','AMBRE':'#faeeda','ROUGE':'#fcebeb'}.get(st_w,'')
                html += f'<tr style="background:{bg};">'
                html += f'<td>{w.get("annee_test","")}</td>'
                # ⚠️ « {v:,} » RENDAIT « 2,435 » — le séparateur ANGLAIS,
                # dans un rapport français, à côté de « 10308 » sans aucun
                # séparateur. Trois conventions coexistaient dans ce document.
                html += f'<td class="right">{F.nombre(w.get("n_train"), 0)}</td>'
                html += f'<td class="right">{F.nombre(w.get("n_test"), 0)}</td>'
                html += f'<td class="right">{F.nombre(w.get("moy_train"), F.DEC_GINI)}</td>'
                html += f'<td class="right">{F.nombre(w.get("moy_test"), F.DEC_GINI)}</td>'
                html += f'<td class="right"><strong>{F.nombre(w.get("ae_ratio"), F.DEC_GINI)}</strong></td>'
                html += f'<td class="center"><span class="badge badge-{st_w.lower()}">{st_w}</span></td></tr>\n'
            html += '    </table>'
    else:
        html += f'<p><em>Backtesting non disponible. {bt6.get("note","")}</em></p>'
    html += """
  </div>
</div>

<!-- §6 MODÈLE PRODUCTION -->
<div class="section">
  <div class="section-head">§6 — Modèle de Production Retenu</div>
  <div class="section-body">
"""
    if prod:
        prod_col = _statut_col((result_a6 or {}).get('statut_rag','AMBRE'))
        _score_txt = f"{prod.get('score_global'):.4f}" if 'score_global' in prod else '—'
        html += f"""
    <div class="kpi-grid">
      <div class="kpi"><div class="kpi-label">Modèle retenu</div><div class="kpi-value" style="font-size:15px;color:{NAVY}">{prod.get('modele','—')}</div></div>
      <div class="kpi"><div class="kpi-label">Famille</div><div class="kpi-value" style="font-size:15px;">{prod.get('famille','—')}</div></div>
      <div class="kpi"><div class="kpi-label">Score global</div><div class="kpi-value">{_score_txt}</div></div>
      <div class="kpi"><div class="kpi-label">Gini test</div><div class="kpi-value">{prod.get('gini_test',0):.4f}</div></div>
      <div class="kpi"><div class="kpi-label">Overfit ratio</div><div class="kpi-value">{prod.get('overfit_ratio',0):.3f}</div></div>
      <div class="kpi"><div class="kpi-label">Interprétabilité</div><div class="kpi-value">{prod.get('interpretabilite',0):.2f}/1.0</div></div>
    </div>
    <p style="margin-top:8px; font-size:10px; color:{SLATE}; font-style:italic;">
      ✦ Le « Score global » est une normalisation RELATIVE au meilleur
      modèle du profil de pondération retenu (le meilleur modèle vaut
      toujours ≈ 1,0000) — ce n'est PAS une mesure de performance absolue
      en pourcentage. Réf. : audit V7, recommandation IMPORTANT #1.
    </p>
"""
    if val6:
        html += """
    <table style="margin-top:14px;">
      <tr><th>Contrôle sélection</th><th>Statut</th><th>Message</th></tr>
"""
        for ck, cl in [('c1_nb_modeles','C1 — Nombre de modèles'),
                       ('c2_ecart_gini','C2 — Écart Gini'),
                       ('c3_coherence','C3 — Cohérence')]:
            cv = val6.get(ck, {})
            st = cv.get('statut','?')
            html += _row([cl,
                          f'<span class="badge badge-{st.lower()}">{_statut_emoji(st)} {st}</span>',
                          cv.get('message','')[:80]])
        html += '    </table>'
    html += """
  </div>
</div>
"""
    html += _section_figures
    html += """
<!-- §7 COMMENTAIRE ACTUARIEL -->
<div class="section">
  <div class="section-head">§7 — Commentaire Actuariel</div>
  <div class="section-body narration">
"""
    html += narr_html
    html += f"""
    <p style="margin-top:12px; font-size:10px; color:{SLATE}; font-style:italic;">
      ✦ {f'Narration générée par ActuarIA Intelligence ({CLAUDE_MODEL_TARIF})' if n_src=='claude_api' else f'Source : {n_src}'}
    </p>
  </div>
</div>

<!-- §8 AUDIT TRAIL -->
<div class="section">
  <div class="section-head">§8 — Audit Trail & Traçabilité</div>
  <div class="section-body">
    <table>
      <tr><th>Clé</th><th>Valeur</th></tr>
"""
    for k, v in at.items():
        if isinstance(v, (str, int, float, bool)):
            html += _row([k.replace('_',' ').title(), str(v)[:120]])
    html += f"""    </table>
  </div>
</div>

<div class="footer">
  ActuarIA · {ref_client or 'Client'} · {branche.replace('_',' ').title()} · Arrêté {arr} · {now} · CONFIDENTIEL
</div>
</div>
</body>
</html>"""
    return html


# =============================================================================
#  WORD
# =============================================================================

def export_word(
    result_a3: Dict = None, result_a4: Dict = None, result_a6: Dict = None,
    ref_client: str = '', arrete: str = '', audit_id: str = '',
    narration_calculee: Optional[Tuple[str, str]] = None,
) -> bytes:
    """Génère le rapport Word tarification (.docx). Retourne bytes ou b''.

    `narration_calculee` : voir `export_html`. C'est ce format-ci qui payait le
    plus cher l'appel séparé — il partait sans le commentaire actuariel.
    """
    try:
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError as e:
        logger.error(f'python-docx absent : {e}'); return b''

    try:
        now    = datetime.now().strftime('%d/%m/%Y')
        arr    = arrete or now
        branche= (result_a6 or result_a3 or {}).get('branche', 'non_vie')
        statut = (result_a6 or result_a3 or {}).get('statut_rag', 'AMBRE')
        met3   = (result_a3 or {}).get('metriques', {})
        rels   = (result_a3 or {}).get('relativites_poisson', {})
        cl4    = (result_a4 or {}).get('classement', [])
        hyp3   = (result_a3 or {}).get('hypotheses', {})
        hyp4   = (result_a4 or {}).get('hypotheses', {})
        bt6    = (result_a6 or {}).get('backtest', {})
        prod   = (result_a6 or {}).get('modele_production', {})
        # Priorité A6 (le plus complet — gouvernance + WF recalibré) > A4 > A3
        at     = (
            (result_a6 or {}).get('audit_trail')
            or (result_a4 or {}).get('audit_trail')
            or (result_a3 or {}).get('audit_trail')
            or {}
        )

        narration, n_src = (
            narration_calculee if narration_calculee is not None
            else _narration_claude(result_a3, result_a4, result_a6, branche, arr))

        def rgb(h):
            h = h.lstrip('#')
            return RGBColor(int(h[:2],16), int(h[2:4],16), int(h[4:],16))

        NR = rgb(NAVY); GR = rgb(GOLD); BR = rgb('#FFFFFF')
        GrR= rgb(SLATE); RgR= rgb(ROUGE); VR = rgb(VERT); AR = rgb(ORANGE)

        doc = Document()
        for s in doc.sections:
            s.top_margin=Cm(2); s.bottom_margin=Cm(2)
            s.left_margin=Cm(2.5); s.right_margin=Cm(2.5)

        def _bg(cell, hex6):
            tc=cell._tc; tcp=tc.get_or_add_tcPr()
            sd=OxmlElement('w:shd')
            sd.set(qn('w:fill'), hex6.lstrip('#'))
            sd.set(qn('w:color'), 'auto'); sd.set(qn('w:val'), 'clear')
            tcp.append(sd)

        def _run(p, txt, bold=False, italic=False, sz=10, col=None):
            r=p.add_run(str(txt)); r.bold=bold; r.italic=italic; r.font.size=Pt(sz)
            if col: r.font.color.rgb=col
            return r

        def _h(txt, lv=1, col=None):
            p=doc.add_paragraph()
            p.paragraph_format.space_before=Pt(8); p.paragraph_format.space_after=Pt(3)
            sz={1:16,2:13,3:10}.get(lv,10)
            c=col or (NR if lv==1 else GR)
            _run(p, txt, bold=True, sz=sz, col=c)

        def _sep():
            p=doc.add_paragraph()
            p.paragraph_format.space_before=Pt(2); p.paragraph_format.space_after=Pt(2)
            pPr=p._p.get_or_add_pPr(); pBdr=OxmlElement('w:pBdr')
            bo=OxmlElement('w:bottom')
            bo.set(qn('w:val'),'single'); bo.set(qn('w:sz'),'6')
            bo.set(qn('w:space'),'1'); bo.set(qn('w:color'),'C9A84C')
            pBdr.append(bo); pPr.append(pBdr)

        def _tbl(heads, rows, ws=None, num=()):
            # ⚠️ MESURÉ AVANT CE LOT : 0 cellule numérique sur 69 alignée à
            # droite dans le Word. `num` = les index des colonnes numériques.
            t=doc.add_table(rows=1+len(rows), cols=len(heads)); t.style='Table Grid'
            for i, hd in enumerate(heads):
                c=t.rows[0].cells[i]; _bg(c, '0F2E52')
                pp=c.paragraphs[0]; pp.alignment=WD_ALIGN_PARAGRAPH.CENTER
                r=pp.add_run(str(hd)); r.bold=True; r.font.size=Pt(9); r.font.color.rgb=BR
            for ri, row in enumerate(rows):
                for ci, v in enumerate(row):
                    c=t.rows[ri+1].cells[ci]
                    if ri%2==1: _bg(c, 'EEF2F7')
                    pp=c.paragraphs[0]
                    if ci in num:
                        pp.alignment=WD_ALIGN_PARAGRAPH.RIGHT
                    r=pp.add_run(str(v) if v is not None else '—'); r.font.size=Pt(9)
            if ws:
                for i, w in enumerate(ws):
                    for row in t.rows: row.cells[i].width=Cm(w)
            doc.add_paragraph().paragraph_format.space_after=Pt(2)

        # ── PAGE DE GARDE ─────────────────────────────────────────────────────
        p=doc.add_paragraph()
        _run(p, 'Actuar', bold=True, sz=28, col=NR)
        _run(p, 'IA',     bold=True, sz=28, col=GR)
        doc.add_paragraph()
        p=doc.add_paragraph()
        _run(p, 'RAPPORT DE TARIFICATION NON-VIE\n', bold=True, sz=20, col=NR)
        _run(p, branche.replace('_',' ').title(), bold=True, sz=14, col=GR)
        doc.add_paragraph()
        s_col_r = VR if statut=='VERT' else AR if statut=='AMBRE' else RgR
        p=doc.add_paragraph()
        _run(p, 'Statut : ', sz=11, col=NR)
        _run(p, statut, bold=True, sz=11, col=s_col_r)
        doc.add_paragraph()
        _tbl(['Client','Branche','Arrêté','Audit ID'],
             [[ref_client or 'À renseigner', branche.replace('_',' ').title(), arr, audit_id or 'N/A']],
             ws=[3.5, 4.0, 3.0, 3.5])
        doc.add_page_break()

        # ── §1 : SYNTHÈSE GLM ─────────────────────────────────────────────────
        _h('1. Résultats GLM — Poisson / Gamma / Tweedie'); _sep()
        rows_glm = []
        for modele in ['poisson','gamma','tweedie']:
            m = met3.get(modele, {})
            if m:
                rows_glm.append([
                    modele.capitalize(),
                    F.nombre(m.get('gini'), F.DEC_GINI),
                    F.nombre(m.get('aic'), 0),
                    F.nombre(m.get('pseudo_r2'), F.DEC_GINI),
                    F.nombre(m.get('nb_vars_retenues'), 0),
                ])
        if rows_glm:
            _tbl(['Modèle','Gini test','AIC','Pseudo-R²','Vars retenues'], rows_glm,
                 ws=[3.0,2.5,2.5,2.5,3.5], num=(1, 2, 3, 4))
        doc.add_page_break()

        # ── §2 : RELATIVITÉS ─────────────────────────────────────────────────
        _h('2. Relativités Tarifaires GLM Poisson — exp(β)'); _sep()
        rows_rel = []
        for var, d in sorted(rels.items(), key=lambda x: -abs(x[1].get('beta',0)))[:15]:
            rows_rel.append([
                var,
                f"{d.get('beta',0):.4f}",
                f"{d.get('relativite',0):.4f}",
                f"{d.get('ic95_low',0):.4f}",
                f"{d.get('ic95_high',0):.4f}",
                # Audit V7 IMPORTANT : garde NA cohérent avec le HTML.
                f"{d.get('pvalue'):.4f}" if 'pvalue' in d else '—',
                'Oui' if d.get('significatif') else 'Non',
                d.get('sens',''),
            ])
        if rows_rel:
            _tbl(['Variable','β','Relativité','IC bas','IC haut','p-value','Sig.','Sens'],
                 rows_rel, ws=[3.0,1.8,2.0,1.8,1.8,1.8,1.2,1.6],
                 num=(1, 2, 3, 4, 5))
        doc.add_page_break()

        # ── §3 : CLASSEMENT ML ───────────────────────────────────────────────
        _h('3. Classement ML — Grille Multicritères'); _sep()
        # Audit V7 IMPORTANT : garde NA cohérent avec le HTML.
        rows_ml = [[str(i), m.get('modele',''), m.get('famille',''),
                    F.nombre(m.get('gini_test'), F.DEC_GINI),
                    F.nombre(m.get('overfit_ratio'), F.DEC_RATIO),
                    F.nombre(m.get('score_global'), F.DEC_GINI)]
                   for i, m in enumerate(cl4[:10], 1)]
        if rows_ml:
            _tbl(['#','Modèle','Famille','Gini test','Overfit','Score'],
                 rows_ml, ws=[1.0,4.0,2.5,2.5,2.0,2.0], num=(3, 4, 5))
        doc.add_page_break()

        # ── §4 : HYPOTHÈSES H1-H4 ────────────────────────────────────────────
        _h('4. Validation des Hypothèses Actuarielles H1–H4'); _sep()
        rows_hyp = []
        for hkey, hlabel in [
            ('h1_poisson',   'H1 GLM — Sur-dispersion Poisson'),
            ('h2_homosc',    'H2 GLM — Homoscédasticité résidus'),
            ('h3_ajustement','H3 GLM — Gini ajustement'),
            ('h4_stabilite', 'H4 GLM — Stabilité relativités'),
            ('h1_overfitting','H1 ML — Overfitting'),
            ('h2_psi',       'H2 ML — PSI réel'),
            ('h3_gini',      'H3 ML — Gini performance'),
            ('h4_calibration','H4 ML — Calibration'),
        ]:
            h = hyp3.get(hkey) or hyp4.get(hkey, {})
            if h:
                rows_hyp.append([hlabel, h.get('statut','?'),
                                  str(h.get('message',''))[:70],
                                  str(h.get('conseil',''))[:60]])
        if rows_hyp:
            _tbl(['Hypothèse','Statut','Message','Conseil'], rows_hyp,
                 ws=[4.5,1.8,5.5,4.2])
        doc.add_page_break()

        # ── §5 : BACKTESTING ─────────────────────────────────────────────────
        _h('5. Backtesting Walk-Forward & Test A/E'); _sep()
        if bt6.get('disponible'):
            ae = bt6.get('ae_ratio', 0)
            bt_col = VR if 0.95<=ae<=1.05 else AR if 0.90<=ae<=1.10 else RgR
            p=doc.add_paragraph()
            _run(p, f"A/E ratio (N-1→N) : ", sz=10, col=NR)
            _run(p, f"{ae:.4f}", bold=True, sz=10, col=bt_col)
            _run(p, f" | {bt6.get('interpretation','')} | Stabilité : {bt6.get('stabilite_wf','')}",
                 sz=9, col=NR)
            wf = bt6.get('walk_forward', [])
            if wf:
                rows_wf = [[str(w.get('annee_test','')),
                             F.nombre(w.get('n_train'), 0),
                             F.nombre(w.get('ae_ratio'), F.DEC_GINI),
                             w.get('statut','')]
                           for w in wf]
                _tbl(['Année test','N train','A/E ratio','Statut'], rows_wf,
                     ws=[2.5,2.5,2.5,2.5], num=(1, 2))
        else:
            p=doc.add_paragraph()
            _run(p, f"Backtesting non disponible. {bt6.get('note','')}", sz=9, italic=True)
        doc.add_page_break()

        # ── §6 : MODÈLE PRODUCTION ───────────────────────────────────────────
        _h('6. Modèle de Production Retenu'); _sep()
        if prod:
            p_col = VR if statut=='VERT' else AR if statut=='AMBRE' else RgR
            _score_txt = f"{prod.get('score_global'):.4f}" if 'score_global' in prod else '—'
            _tbl(['Attribut','Valeur','Attribut','Valeur'],
                 [['Modèle retenu', prod.get('modele','—'), 'Famille', prod.get('famille','—')],
                  ['Score global', _score_txt,
                   'Gini test', f"{prod.get('gini_test',0):.4f}"],
                  ['Overfit ratio', f"{prod.get('overfit_ratio',0):.3f}",
                   'Interprétabilité', f"{prod.get('interpretabilite',0):.2f}/1.0"]],
                 ws=[4.0,4.0,4.0,4.0])
            # Audit V7 IMPORTANT #1 : qualification du score composite —
            # normalisation RELATIVE au meilleur modèle du profil retenu
            # (le meilleur vaut toujours ≈ 1,0000), PAS une performance
            # absolue. Absente du livrable avant ce correctif (ne figurait
            # que dans un commentaire de code, jamais vue par le client).
            p = doc.add_paragraph()
            _run(p,
                 "✦ Le « Score global » est une normalisation relative au "
                 "meilleur modèle du profil de pondération retenu (le "
                 "meilleur modèle vaut toujours ≈ 1,0000) — ce n'est pas "
                 "une mesure de performance absolue en pourcentage.",
                 sz=9, italic=True)
        doc.add_page_break()

        # ── §7 : COMMENTAIRE ACTUARIEL ───────────────────────────────────────
        _h('7. Commentaire Actuariel'); _sep()
        if narration:
            sections_n = re.split(r'(?=§\d+\s*[—\-–])', _clean(narration))
            for sec in sections_n:
                sec = sec.strip()
                if not sec: continue
                ls = sec.split('\n', 1)
                if ls[0]: _h(ls[0], lv=2)
                if len(ls) > 1:
                    for ln in ls[1].split('\n'):
                        ln = ln.strip()
                        if ln:
                            p=doc.add_paragraph()
                            p.paragraph_format.space_after=Pt(3)
                            p.paragraph_format.left_indent=Cm(0.3)
                            _run(p, ln, sz=9, col=NR)
            # ⚠️ LE WORD NE NOMMAIT SA SOURCE QU'EN CAS DE SUCCÈS. Un repli y
            # était donc INDISCERNABLE d'une narration réussie, là où l'HTML
            # l'affichait. Une narration calculée une fois qui échoue doit le
            # dire dans les DEUX formats — sinon on remplace deux commentaires
            # divergents par un silence dans l'un des deux.
            p = doc.add_paragraph()
            _run(p, (f'✦ Narration générée par ActuarIA Intelligence '
                     f'({CLAUDE_MODEL_TARIF})' if n_src == SRC_API
                     else f'✦ Source de la narration : {n_src}'),
                 sz=7, italic=True, col=GrR)
        else:
            p=doc.add_paragraph()
            _run(p, f'Narration non disponible — source : {n_src}',
                 sz=9, italic=True)
        doc.add_page_break()

        # ── §8 : AUDIT TRAIL ─────────────────────────────────────────────────
        _h('8. Audit Trail & Traçabilité ACPR'); _sep()
        rows_at = [[k.replace('_',' ').title(), str(v)[:80]]
                   for k, v in at.items() if isinstance(v, (str,int,float,bool))]
        if rows_at:
            _tbl(['Clé','Valeur'], rows_at, ws=[5.0,11.0])

        _sep()
        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        _run(p, f'ActuarIA · {ref_client or "Client"} · {branche.replace("_"," ").title()} · '
                f'Arrêté {arr} · {now} · CONFIDENTIEL',
             sz=7, italic=True, col=GrR)

        buf=io.BytesIO(); doc.save(buf); buf.seek(0)
        wb = buf.read()
        logger.info(f'Word tarification : {len(wb):,} bytes')
        return wb

    except Exception as e:
        logger.error(f'export_word tarification : {e}', exc_info=True)
        return b''


# =============================================================================
#  PDF
# =============================================================================

def export_pdf(
    result_a3: Dict = None, result_a4: Dict = None, result_a6: Dict = None,
    ref_client: str = '', arrete: str = '', audit_id: str = '',
    narration_calculee: Optional[Tuple[str, str]] = None,
) -> bytes:
    """Génère le rapport PDF via weasyprint (HTML→PDF). Retourne bytes ou b''.

    `narration_calculee` : transmis à `export_html` — le PDF est un rendu de
    l'HTML, il doit porter exactement le même commentaire.
    """
    try:
        from weasyprint import HTML as WP_HTML
        html = export_html(result_a3, result_a4, result_a6, ref_client, arrete,
                           audit_id, narration_calculee)
        if not html:
            return b''
        buf = io.BytesIO()
        WP_HTML(string=html).write_pdf(buf)
        buf.seek(0)
        pdf = buf.read()
        logger.info(f'PDF tarification : {len(pdf):,} bytes')
        return pdf
    except ImportError:
        logger.warning('weasyprint absent — PDF non généré')
        return b''
    except Exception as e:
        logger.error(f'export_pdf tarification : {e}', exc_info=True)
        return b''


# =============================================================================
#  POINT D'ENTRÉE UNIFIÉ
# =============================================================================

def generer_rapport_tarification(
    result_a3: Dict = None,
    result_a4: Dict = None,
    result_a6: Dict = None,
    ref_client: str = '',
    arrete: str = '',
    audit_id: str = '',
    formats: List[str] = None,
) -> Dict[str, bytes]:
    """
    Génère tous les formats demandés en un seul appel.
    formats = ['html','word','pdf','excel'] (défaut = html + word)
    Retourne {'html_bytes': ..., 'word_bytes': ..., 'pdf_bytes': ..., 'excel_bytes': ...}
    """
    if formats is None:
        formats = ['html', 'word']

    out: Dict[str, bytes] = {
        'html_bytes':  b'',
        'word_bytes':  b'',
        'pdf_bytes':   b'',
        'excel_bytes': b'',
    }

    # ⚠️ LA NARRATION EST CALCULÉE UNE FOIS, ICI, POUR TOUS LES FORMATS.
    # Avant ce lot, chaque export appelait `_narration_claude` pour son propre
    # compte. Mesuré sur un rapport réel : le HTML portait les 18 089 caractères
    # du commentaire actuariel, le Word portait le dépôt technique de l'agent —
    # le format qui part chez un commissaire n'avait pas le commentaire. Deux
    # narrations divergentes dans un même livrable deviennent désormais
    # IMPOSSIBLES PAR CONSTRUCTION, et le nombre d'appels est divisé par deux.
    arr_narr = arrete or datetime.now().strftime('%d/%m/%Y')
    branche_narr = (result_a6 or result_a3 or {}).get('branche', 'non_vie')
    narration_calculee = _narration_claude(
        result_a3, result_a4, result_a6, branche_narr, arr_narr)

    # HTML d'abord (réutilisé pour PDF)
    html_str = ''
    if 'html' in formats or 'pdf' in formats:
        html_str = export_html(result_a3, result_a4, result_a6, ref_client, arrete,
                               audit_id, narration_calculee)
        out['html_bytes'] = html_str.encode('utf-8') if html_str else b''

    if 'word' in formats:
        out['word_bytes'] = export_word(result_a3, result_a4, result_a6, ref_client,
                                        arrete, audit_id, narration_calculee)

    if 'pdf' in formats:
        if html_str:
            try:
                from weasyprint import HTML as WP_HTML
                buf = io.BytesIO()
                WP_HTML(string=html_str).write_pdf(buf)
                buf.seek(0)
                out['pdf_bytes'] = buf.read()
            except ImportError:
                logger.warning('weasyprint absent — PDF non généré')
        else:
            out['pdf_bytes'] = export_pdf(result_a3, result_a4, result_a6, ref_client,
                                          arrete, audit_id, narration_calculee)

    if 'excel' in formats:
        try:
            from .tarif_excel import export_excel_a6
            if result_a6:
                out['excel_bytes'] = export_excel_a6(result_a6, audit_id)
        except ImportError:
            try:
                from direction_non_vie.tarification.services.tarif_excel import export_excel_a6
                if result_a6:
                    out['excel_bytes'] = export_excel_a6(result_a6, audit_id)
            except ImportError:
                pass

    logger.info(
        f"Rapport tarification : "
        f"HTML={len(out['html_bytes']):,}b "
        f"Word={len(out['word_bytes']):,}b "
        f"PDF={len(out['pdf_bytes']):,}b "
        f"Excel={len(out['excel_bytes']):,}b"
    )
    return out
