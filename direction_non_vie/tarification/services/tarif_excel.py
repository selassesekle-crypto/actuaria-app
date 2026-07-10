"""
ActuarIA — Service partagé : Rapport Excel Tarification Non-Vie
Direction Non-Vie · Équipe Tarification

Produit des rapports Excel multi-onglets pour A3 (GLM), A4 (ML) et A6 (Comparaison).
Palette Navy/Gold ActuarIA, formats €/%, audit trail intégré.

ONGLETS PAR AGENT :
  A3 GLM  : Synthèse · Relativités · Métriques GLM · Hypothèses · Audit
  A4 ML   : Synthèse · Classement · SHAP · Hypothèses · Monitoring · Audit
  A6      : Synthèse · Classement final · Backtesting A/E · Fiche décision · Audit
"""

import io
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger('actuaria.tarif.excel')

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False
    logger.warning("openpyxl non disponible — export Excel désactivé")

# ── Palette ActuarIA ──────────────────────────────────────────────────────────
NAVY   = "0F2E52"
OR     = "C9A84C"
BLANC  = "F0F4F8"
GRIS   = "8A9AB0"
VERT_H = "2ECC71"
AMBRE  = "F39C12"
ROUGE  = "E74C3C"
NAVY_L = "1B3A5C"
GRIS_L = "EAF0F6"
NOIR   = "1A1A1A"

FMT_EUR  = '# ##0 €;-# ##0 €'
FMT_PCT  = '0.00%'
FMT_DEC4 = '0.0000'
FMT_NB   = '# ##0'

# ── Helpers ───────────────────────────────────────────────────────────────────

def _font(bold=False, color=BLANC, size=10, italic=False):
    return Font(name="Arial", bold=bold, color=color, size=size, italic=italic)

def _fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)

def _border():
    s = Side(style="thin", color="CCCCCC")
    return Border(left=s, right=s, top=s, bottom=s)

def _align(h="left", v="center", wrap=False):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

def _statut_fill(statut: str) -> str:
    return {"VERT": VERT_H, "AMBRE": AMBRE, "ROUGE": ROUGE}.get(statut.upper(), GRIS)

def _col_w(ws, col: int, width: float):
    ws.column_dimensions[get_column_letter(col)].width = width

def _cell(ws, row, col, val, bold=False, cf=BLANC, fill=None,
          ah="left", fmt=None, border=True, wrap=False):
    c = ws.cell(row=row, column=col, value=val)
    c.font      = _font(bold=bold, color=cf)
    c.alignment = _align(h=ah, wrap=wrap)
    if fill:
        c.fill = _fill(fill)
    if border:
        c.border = _border()
    if fmt:
        c.number_format = fmt
    return c

def _header(ws, row, col, text, width=18):
    _cell(ws, row, col, text, bold=True, cf=BLANC, fill=NAVY, ah="center")
    _col_w(ws, col, width)

def _section(ws, row, titre, n_cols=8):
    c = ws.cell(row=row, column=1, value=f"  {titre}")
    c.font      = _font(bold=True, color=OR, size=11)
    c.fill      = _fill(NAVY_L)
    c.alignment = _align(h="left")
    c.border    = _border()
    if n_cols > 1:
        ws.merge_cells(start_row=row, start_column=1,
                       end_row=row, end_column=n_cols)
    ws.row_dimensions[row].height = 20

def _kpi(ws, row, label, value, statut=None, fmt=None, wrap=False):
    _cell(ws, row, 1, label, bold=True, cf=NOIR, fill=GRIS_L, wrap=wrap)
    _col_w(ws, 1, 38)
    _cell(ws, row, 2, value, bold=True, cf=NOIR, fill=None, ah="left" if wrap else "right",
          fmt=fmt, wrap=wrap)
    _col_w(ws, 2, 50 if wrap else 22)
    if statut:
        txt = {"VERT": "✓ Conforme", "AMBRE": "△ À surveiller", "ROUGE": "✗ Attention"}.get(statut, statut)
        _cell(ws, row, 3, txt, bold=True, cf=BLANC,
              fill=_statut_fill(statut), ah="center")
        _col_w(ws, 3, 18)

def _bandeau(ws, titre, sous_titre, agent, audit_id, date_str, n_cols=8):
    ws.row_dimensions[1].height = 32
    ws.row_dimensions[2].height = 22
    ws.row_dimensions[3].height = 18
    ws.row_dimensions[4].height = 16
    ws.row_dimensions[5].height = 14
    for r, (txt, sz, bold) in enumerate([
        (f"ActuarIA — {titre}", 14, True),
        (sous_titre,             11, False),
        (f"Agent : {agent}",      10, False),
        (f"Arrêté : {date_str}",  9, False),
        (f"Audit ID : {audit_id}", 9, False),
    ], 1):
        c = ws.cell(row=r, column=1, value=txt)
        c.font      = _font(bold=bold, color=OR if bold else BLANC, size=sz)
        c.fill      = _fill(NAVY)
        c.alignment = _align(h="left")
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=n_cols)


# =============================================================================
#  EXPORT A3 — GLM
#  5 onglets : Synthèse · Relativités Poisson · Relativités Gamma
#              Hypothèses H1-H4 · Audit Trail
# =============================================================================

def export_excel_a3(result_a3: Dict, audit_id: str = "") -> bytes:
    """Génère le rapport Excel A3 GLM (5 onglets). Retourne bytes ou b''."""
    if not OPENPYXL_OK or not result_a3 or not result_a3.get('success'):
        return b''
    try:
        wb  = Workbook()
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        aid = audit_id or result_a3.get('audit_id', 'N/A')
        met = result_a3.get('metriques', {})
        val = result_a3.get('validation_glm', {})

        # ── Onglet 1 : Synthèse ───────────────────────────────────────────────
        ws1 = wb.active
        ws1.title = "1-Synthèse"
        _bandeau(ws1, "Rapport Tarification GLM", "Synthèse des résultats",
                 "A3 — GLM Poisson/Gamma/Tweedie", aid, now)
        r = 7
        _section(ws1, r, "▶ MÉTRIQUES GLM"); r += 1
        for modele, label in [('poisson','GLM Poisson'), ('gamma','GLM Gamma'), ('tweedie','GLM Tweedie')]:
            m = met.get(modele, {})
            if m:
                _kpi(ws1, r, f"{label} — Gini test",     round(m.get('gini', 0), 4), fmt=FMT_DEC4)
                r += 1
                _kpi(ws1, r, f"{label} — AIC",            round(m.get('aic', 0), 0),  fmt=FMT_NB)
                r += 1
                _kpi(ws1, r, f"{label} — Déviance nulle", round(m.get('deviance_nulle', 0), 2))
                r += 1
                _kpi(ws1, r, f"{label} — Pseudo-R²",      round(m.get('pseudo_r2', 0), 4))
                r += 1
                _kpi(ws1, r, f"{label} — Vars retenues",  m.get('nb_vars_retenues', 0))
                r += 2

        _section(ws1, r, "▶ STATUT GLOBAL"); r += 1
        statut = val.get('statut_global', 'N/A')
        _kpi(ws1, r, "Statut validation", statut, statut=statut); r += 1
        _kpi(ws1, r, "Conclusion", val.get('conclusion', ''), wrap=True); r += 1

        # ── Onglet 2 : Relativités Poisson ───────────────────────────────────
        ws2 = wb.create_sheet("2-Relativités Poisson")
        _bandeau(ws2, "Relativités Tarifaires", "GLM Poisson — exp(β) avec IC 95%",
                 "A3 — GLM Poisson", aid, now)
        rels_p = result_a3.get('relativites_poisson', {})
        r = 7
        _section(ws2, r, "▶ RELATIVITÉS GLM POISSON — exp(β)  [Source : Mildenhall 1999]"); r += 1
        for col, txt, w in [(1,"Variable",28),(2,"β",12),(3,"Relativité exp(β)",20),
                             (4,"IC 95% bas",16),(5,"IC 95% haut",16),
                             (6,"p-value",12),(7,"Significatif",14),(8,"Sens",14)]:
            _header(ws2, r, col, txt, w)
        r += 1
        for var, d in sorted(rels_p.items(), key=lambda x: -abs(x[1].get('beta', 0))):
            vals = [var, d.get('beta',0), d.get('relativite',0),
                    d.get('ic95_low',0), d.get('ic95_high',0),
                    d.get('pvalue',0), "Oui" if d.get('significatif') else "Non",
                    d.get('sens','')]
            fmts = [None, FMT_DEC4, FMT_DEC4, FMT_DEC4, FMT_DEC4, FMT_DEC4, None, None]
            bg = GRIS_L if list(rels_p.keys()).index(var) % 2 == 0 else None
            for j, (v, f) in enumerate(zip(vals, fmts), 1):
                _cell(ws2, r, j, v, cf=NOIR, fill=bg, fmt=f, ah="right" if isinstance(v,(int,float)) else "left")
            # Couleur sens
            col_sens = 8
            fill_s = "EAF3DE" if d.get('sens') == 'allegant' else "FCEBEB"
            ws2.cell(row=r, column=col_sens).fill = _fill(fill_s)
            r += 1

        # ── Onglet 3 : Relativités Gamma ─────────────────────────────────────
        ws3 = wb.create_sheet("3-Relativités Gamma")
        _bandeau(ws3, "Relativités Tarifaires", "GLM Gamma — exp(β) avec IC 95%",
                 "A3 — GLM Gamma", aid, now)
        rels_g = result_a3.get('relativites_gamma', {})
        r = 7
        _section(ws3, r, "▶ RELATIVITÉS GLM GAMMA — exp(β) (coût moyen)"); r += 1
        for col, txt, w in [(1,"Variable",28),(2,"β",12),(3,"Relativité exp(β)",20),
                             (4,"IC 95% bas",16),(5,"IC 95% haut",16),
                             (6,"p-value",12),(7,"Significatif",14),(8,"Sens",14)]:
            _header(ws3, r, col, txt, w)
        r += 1
        for var, d in sorted(rels_g.items(), key=lambda x: -abs(x[1].get('beta', 0))):
            vals = [var, d.get('beta',0), d.get('relativite',0),
                    d.get('ic95_low',0), d.get('ic95_high',0),
                    d.get('pvalue',0), "Oui" if d.get('significatif') else "Non",
                    d.get('sens','')]
            fmts = [None, FMT_DEC4, FMT_DEC4, FMT_DEC4, FMT_DEC4, FMT_DEC4, None, None]
            bg = GRIS_L if list(rels_g.keys()).index(var) % 2 == 0 else None
            for j, (v, f) in enumerate(zip(vals, fmts), 1):
                _cell(ws3, r, j, v, cf=NOIR, fill=bg, fmt=f, ah="right" if isinstance(v,(int,float)) else "left")
            r += 1

        # ── Onglet 4 : Hypothèses H1-H4 ──────────────────────────────────────
        ws4 = wb.create_sheet("4-Hypothèses H1-H4")
        _bandeau(ws4, "Validation Hypothèses GLM", "H1 Distribution · H2 Homoscédasticité · H3 Gini · H4 Stabilité",
                 "A3 — Validation réglementaire", aid, now)
        r = 7
        hyp_map = [
            ("h1_poisson",  "H1 — Sur-dispersion Poisson",         "ratio_disp"),
            ("h2_homosc",   "H2 — Homoscédasticité résidus",       "cv_max"),
            ("h3_ajustement","H3 — Qualité ajustement (Gini)",     "gini_max"),
            ("h4_stabilite","H4 — Stabilité relativités bootstrap","cv_max"),
        ]
        for hkey, hlabel, hval_key in hyp_map:
            h = val.get(hkey, {})
            if not h:
                continue
            st = h.get('statut', 'N/A')
            _section(ws4, r, f"▶ {hlabel}"); r += 1
            _kpi(ws4, r, "Statut",     st,                    statut=st); r += 1
            _kpi(ws4, r, "Valeur",     round(h.get(hval_key, 0), 4)); r += 1
            _kpi(ws4, r, "Message",    h.get('message', ''),  wrap=True); r += 1
            _kpi(ws4, r, "Conseil",    h.get('conseil', ''),  wrap=True); r += 2

        # ── Onglet 5 : Audit Trail ────────────────────────────────────────────
        ws5 = wb.create_sheet("5-Audit Trail")
        _bandeau(ws5, "Audit Trail", "Traçabilité ACPR — Agent A3 GLM",
                 "A3 — Audit", aid, now)
        r = 7
        _section(ws5, r, "▶ INFORMATIONS AUDIT"); r += 1
        _kpi(ws5, r, "Audit ID",    aid);  r += 1
        _kpi(ws5, r, "Date",        now);  r += 1
        _kpi(ws5, r, "Agent",       "A3 GLM Poisson/Gamma/Tweedie"); r += 1
        _kpi(ws5, r, "Branche",     result_a3.get('branche', 'N/A')); r += 1
        _kpi(ws5, r, "Statut RAG",  result_a3.get('statut_rag', 'N/A'),
             statut=result_a3.get('statut_rag')); r += 1
        _kpi(ws5, r, "Nb obs train",result_a3.get('metriques',{}).get('poisson',{}).get('nb_obs_train',0),
             fmt=FMT_NB); r += 1
        _kpi(ws5, r, "Nb obs test", result_a3.get('metriques',{}).get('poisson',{}).get('nb_obs_test',0),
             fmt=FMT_NB); r += 1
        _kpi(ws5, r, "Vars retenues (Poisson)",
             ', '.join(result_a3.get('metriques',{}).get('poisson',{}).get('vars_retenues', [])),
             wrap=True); r += 1

        # ── Onglet 6 : Crédibilité Bühlmann-Straub & Lissage Géographique ────
        # Réf. : Bühlmann & Straub (1970) ASTIN Bulletin ; Gelfand et al. (2010)
        cred = result_a3.get('credibilite', {})
        geo  = result_a3.get('lissage_geo', {})
        ws6 = wb.create_sheet("6-Crédibilité & Géo")
        _bandeau(ws6, "Crédibilité & Lissage Géo", "Modules avancés P2 — Agent A3 GLM",
                 "A3 — Bühlmann-Straub / Krigeage", aid, now)
        r = 7
        _section(ws6, r, "▶ CRÉDIBILITÉ BÜHLMANN-STRAUB"); r += 1
        if cred.get('appliquee'):
            _kpi(ws6, r, "Statut", "✓ Appliquée", statut="VERT"); r += 1
            _kpi(ws6, r, "Colonne de groupe", cred.get('col_groupe', 'N/A')); r += 1
            _kpi(ws6, r, "Nombre de groupes", cred.get('n_groupes', 0), fmt=FMT_NB); r += 1
            _kpi(ws6, r, "Facteur k (σ²intra/σ²entre)", round(cred.get('k', 0), 4), fmt=FMT_DEC4); r += 1
            _kpi(ws6, r, "Z moyen", round(cred.get('z_moyen', 0), 4), fmt=FMT_DEC4); r += 1
            _kpi(ws6, r, "Z min — Z max",
                 f"{cred.get('z_min',0):.4f} — {cred.get('z_max',0):.4f}"); r += 1
            _kpi(ws6, r, "μ marché (taux global)", round(cred.get('mu_marche', 0), 6), fmt=FMT_DEC4); r += 1
            _kpi(ws6, r, "σ²intra", round(cred.get('sigma2_intra', 0), 8), fmt=FMT_DEC4); r += 1
            _kpi(ws6, r, "σ²entre", round(cred.get('sigma2_entre', 0), 8), fmt=FMT_DEC4); r += 1
            r += 1
            _section(ws6, r, "▶ PRIMES CRÉDIBILISÉES PAR GROUPE (top 20)"); r += 1
            headers = ['Groupe', 'Exposition', 'Taux observé', 'Z', 'Prime crédibilisée']
            for ci, h in enumerate(headers, 1):
                _header(ws6, r, ci, h, width=20)
            r += 1
            for ligne in cred.get('primes_par_groupe', [])[:20]:
                vals = list(ligne.values())
                for ci, v in enumerate(vals, 1):
                    _cell(ws6, r, ci, v, ah="center")
                r += 1
            r += 1
            _kpi(ws6, r, "Référence", cred.get('reference', ''), wrap=True); r += 1
        else:
            _kpi(ws6, r, "Statut", "○ Non applicable", statut="AMBRE"); r += 1
            _kpi(ws6, r, "Raison", cred.get('raison', 'N/A'), wrap=True); r += 1

        r += 2
        _section(ws6, r, "▶ LISSAGE GÉOGRAPHIQUE"); r += 1
        if geo.get('applique'):
            _kpi(ws6, r, "Statut", "✓ Appliqué", statut="VERT"); r += 1
            _kpi(ws6, r, "Méthode", geo.get('methode', 'N/A')); r += 1
            _kpi(ws6, r, "Colonne géographique", geo.get('col_geo', 'N/A')); r += 1
            _kpi(ws6, r, "Nombre de zones", geo.get('n_zones', 0), fmt=FMT_NB); r += 1
            _kpi(ws6, r, "Source de la prime", geo.get('source_prime', 'N/A')); r += 1
            if 'mu_global' in geo:
                _kpi(ws6, r, "μ global", round(geo.get('mu_global', 0), 6), fmt=FMT_DEC4); r += 1
            if 'bandwidth_h' in geo:
                _kpi(ws6, r, "Bandwidth h (krigeage)", geo.get('bandwidth_h', 0), fmt=FMT_DEC4); r += 1
            r += 1
            if geo.get('zones'):
                _section(ws6, r, "▶ PRIMES LISSÉES PAR ZONE"); r += 1
                headers = ['Zone', 'N obs', 'Exposition', 'Prime moy.', 'Z géo', 'Prime lissée']
                for ci, h in enumerate(headers, 1):
                    _header(ws6, r, ci, h, width=20)
                r += 1
                for ligne in geo.get('zones', [])[:20]:
                    vals = list(ligne.values())
                    for ci, v in enumerate(vals, 1):
                        _cell(ws6, r, ci, v, ah="center")
                    r += 1
                r += 1
            _kpi(ws6, r, "Référence", geo.get('reference', ''), wrap=True); r += 1
        else:
            _kpi(ws6, r, "Statut", "○ Non applicable", statut="AMBRE"); r += 1
            _kpi(ws6, r, "Raison", geo.get('raison', 'N/A'), wrap=True); r += 1

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    except Exception as e:
        logger.error(f"export_excel_a3 échoué : {e}", exc_info=True)
        return b''


# =============================================================================
#  EXPORT A4 — ML
#  5 onglets : Synthèse · Classement · SHAP · Hypothèses H1-H4 · Audit
# =============================================================================

def export_excel_a4(result_a4: Dict, audit_id: str = "") -> bytes:
    """Génère le rapport Excel A4 ML (5 onglets). Retourne bytes ou b''."""
    if not OPENPYXL_OK or not result_a4 or not result_a4.get('success'):
        return b''
    try:
        wb  = Workbook()
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        aid = audit_id or result_a4.get('audit_id', 'N/A')
        val = result_a4.get('validation_ml', {})

        # ── Onglet 1 : Synthèse ───────────────────────────────────────────────
        ws1 = wb.active
        ws1.title = "1-Synthèse"
        _bandeau(ws1, "Rapport Tarification ML", "8 modèles comparés — Sélection multicritères",
                 "A4 — Machine Learning", aid, now)
        r = 7
        _section(ws1, r, "▶ MODÈLE SÉLECTIONNÉ"); r += 1
        classement = result_a4.get('classement', [])
        if classement:
            best = classement[0]
            _kpi(ws1, r, "Modèle retenu",    best.get('modele', 'N/A')); r += 1
            _kpi(ws1, r, "Gini test",         round(best.get('gini_test', 0), 4), fmt=FMT_DEC4); r += 1
            _kpi(ws1, r, "RMSE test",         round(best.get('rmse_test', 0), 4), fmt=FMT_DEC4); r += 1
            _kpi(ws1, r, "Overfit ratio",     round(best.get('overfit_ratio', 0), 3)); r += 2

        _section(ws1, r, "▶ STATUT VALIDATION"); r += 1
        statut = val.get('statut_global', 'N/A')
        _kpi(ws1, r, "Statut global",  statut, statut=statut); r += 1
        _kpi(ws1, r, "Conclusion",     val.get('conclusion', ''), wrap=True); r += 1

        # ── Onglet 2 : Classement ─────────────────────────────────────────────
        ws2 = wb.create_sheet("2-Classement modèles")
        _bandeau(ws2, "Classement des modèles ML", "Grille multicritères actuarielle",
                 "A4 — Comparaison", aid, now)
        r = 7
        _section(ws2, r, "▶ CLASSEMENT MULTICRITÈRES (Gini 40% · Stabilité 30% · Interprét. 20% · RMSE 10%)"); r += 1
        for col, txt, w in [(1,"#",6),(2,"Modèle",28),(3,"Famille",14),
                             (4,"Gini test",14),(5,"RMSE test",14),
                             (6,"Overfit ratio",16),(7,"Score global",16),(8,"Alerte",12)]:
            _header(ws2, r, col, txt, w)
        r += 1
        for rank, m in enumerate(classement, 1):
            bg = GRIS_L if rank % 2 == 0 else None
            alerte = "⚠ Overfit" if m.get('overfit_alerte') else "✓ OK"
            vals = [rank, m.get('modele',''), m.get('famille',''),
                    round(m.get('gini_test',0),4), round(m.get('rmse_test',0),4),
                    round(m.get('overfit_ratio',0),3), round(m.get('score_global',0),4), alerte]
            fmts = [None,None,None,FMT_DEC4,FMT_DEC4,FMT_DEC4,FMT_DEC4,None]
            for j, (v, f) in enumerate(zip(vals, fmts), 1):
                _cell(ws2, r, j, v, cf=NOIR, fill=bg, fmt=f,
                      ah="right" if isinstance(v,(int,float)) else "left",
                      bold=(rank==1))
            r += 1

        # ── Onglet 3 : SHAP Values ────────────────────────────────────────────
        ws3 = wb.create_sheet("3-SHAP Values")
        _bandeau(ws3, "Feature Importance SHAP", "Interprétabilité AI Act 2025",
                 "A4 — SHAP (Shapley 1953)", aid, now)
        shap_vals = result_a4.get('shap_values', {})
        r = 7
        _section(ws3, r, "▶ IMPORTANCE FEATURES (SHAP moyen |valeur|)"); r += 1
        _header(ws3, r, 1, "Feature", 32)
        _header(ws3, r, 2, "Importance SHAP", 22)
        _header(ws3, r, 3, "Rang", 10)
        r += 1
        if isinstance(shap_vals, dict) and shap_vals:
            importance = shap_vals.get('importance_globale', shap_vals)
            if isinstance(importance, dict):
                sorted_feats = sorted(importance.items(), key=lambda x: -abs(x[1]))
                for rang, (feat, imp) in enumerate(sorted_feats[:30], 1):
                    bg = GRIS_L if rang % 2 == 0 else None
                    _cell(ws3, r, 1, feat, cf=NOIR, fill=bg)
                    _cell(ws3, r, 2, round(float(imp), 6), cf=NOIR, fill=bg,
                          fmt=FMT_DEC4, ah="right")
                    _cell(ws3, r, 3, rang, cf=NOIR, fill=bg, ah="center")
                    r += 1
        else:
            _cell(ws3, r, 1, "SHAP non disponible — installer le package 'shap'",
                  cf=GRIS, fill=None, border=False)

        # ── Onglet 4 : Hypothèses H1-H4 ──────────────────────────────────────
        ws4 = wb.create_sheet("4-Hypothèses H1-H4")
        _bandeau(ws4, "Validation Hypothèses ML",
                 "H1 Overfitting · H2 PSI réel · H3 Gini · H4 Calibration",
                 "A4 — Validation", aid, now)
        r = 7
        hyp_map = [
            ("h1_overfitting",  "H1 — Absence d'overfitting",         "ratio"),
            ("h2_psi",          "H2 — Stabilité PSI réel",            "psi"),
            ("h3_gini",         "H3 — Performance Gini",              "gini"),
            ("h4_calibration",  "H4 — Calibration reliability",       "ecart_moy_pct"),
        ]
        for hkey, hlabel, hval_key in hyp_map:
            h = val.get(hkey, {})
            if not h:
                continue
            st = h.get('statut', 'N/A')
            _section(ws4, r, f"▶ {hlabel}"); r += 1
            _kpi(ws4, r, "Statut",  st,                   statut=st); r += 1
            _kpi(ws4, r, "Valeur",  round(h.get(hval_key, 0), 4)); r += 1
            _kpi(ws4, r, "Message", h.get('message', ''), wrap=True); r += 1
            _kpi(ws4, r, "Conseil", h.get('conseil', ''), wrap=True); r += 2

        # ── Onglet 5 : Audit Trail ────────────────────────────────────────────
        ws5 = wb.create_sheet("5-Audit Trail")
        _bandeau(ws5, "Audit Trail", "Traçabilité ACPR — Agent A4 ML",
                 "A4 — Audit", aid, now)
        r = 7
        _section(ws5, r, "▶ INFORMATIONS AUDIT"); r += 1
        _kpi(ws5, r, "Audit ID",       aid); r += 1
        _kpi(ws5, r, "Date",           now); r += 1
        _kpi(ws5, r, "Agent",          "A4 — Machine Learning ×8 modèles"); r += 1
        _kpi(ws5, r, "Branche",        result_a4.get('branche', 'N/A')); r += 1
        _kpi(ws5, r, "Statut RAG",     result_a4.get('statut_rag', 'N/A'),
             statut=result_a4.get('statut_rag')); r += 1
        _kpi(ws5, r, "Nb modèles",     len(classement), fmt=FMT_NB); r += 1
        if classement:
            _kpi(ws5, r, "Modèle retenu", classement[0].get('modele','')); r += 1
            _kpi(ws5, r, "Gini retenu",   round(classement[0].get('gini_test',0),4),
                 fmt=FMT_DEC4); r += 1
        opt = result_a4.get('rapport', {}).get('optuna_xgboost')
        if opt:
            _kpi(ws5, r, "Optuna XGBoost — trials", opt.get('trials', 0)); r += 1
            _kpi(ws5, r, "Optuna XGBoost — best Gini",
                 round(opt.get('best_gini', 0), 4), fmt=FMT_DEC4); r += 1

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    except Exception as e:
        logger.error(f"export_excel_a4 échoué : {e}", exc_info=True)
        return b''


# =============================================================================
#  EXPORT A6 — COMPARAISON FINALE
#  5 onglets : Synthèse · Classement final · Backtesting A/E · Fiche décision · Audit
# =============================================================================

def export_excel_a6(result_a6: Dict, audit_id: str = "") -> bytes:
    """Génère le rapport Excel A6 Comparaison (5 onglets). Retourne bytes ou b''."""
    if not OPENPYXL_OK or not result_a6 or not result_a6.get('success'):
        return b''
    try:
        wb  = Workbook()
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        aid = audit_id or result_a6.get('audit_id', 'N/A')
        classement   = result_a6.get('classement', [])
        modele_prod  = result_a6.get('modele_production', {})
        backtest     = result_a6.get('backtest', {})
        val_sel      = result_a6.get('validation_selection', {})
        fiche        = result_a6.get('fiche_decision', {})

        # ── Onglet 1 : Synthèse ───────────────────────────────────────────────
        ws1 = wb.active
        ws1.title = "1-Synthèse"
        _bandeau(ws1, "Rapport Comparaison Finale", "Sélection modèle de production",
                 "A6 — Comparaison & Validation", aid, now)
        r = 7
        _section(ws1, r, "▶ MODÈLE DE PRODUCTION RETENU"); r += 1
        if modele_prod:
            _kpi(ws1, r, "Modèle",         modele_prod.get('modele','')); r += 1
            _kpi(ws1, r, "Famille",         modele_prod.get('famille','')); r += 1
            _kpi(ws1, r, "Score global",    round(modele_prod.get('score_global',0),4),
                 fmt=FMT_DEC4); r += 1
            _kpi(ws1, r, "Gini test",       round(modele_prod.get('gini_test',0),4),
                 fmt=FMT_DEC4); r += 1
            _kpi(ws1, r, "Overfit ratio",   round(modele_prod.get('overfit_ratio',0),3)); r += 1
            _kpi(ws1, r, "Interprétabilité",round(modele_prod.get('interpretabilite',0),2)); r += 2

        _section(ws1, r, "▶ BACKTESTING"); r += 1
        if backtest.get('disponible'):
            ae = backtest.get('ae_ratio', 0)
            _kpi(ws1, r, "A/E ratio (N-1→N)", round(ae, 4),
                 statut='VERT' if 0.95<=ae<=1.05 else 'AMBRE' if 0.90<=ae<=1.10 else 'ROUGE'); r += 1
            _kpi(ws1, r, "Interprétation",   backtest.get('interpretation','')); r += 1
            _kpi(ws1, r, "Stabilité WF",     backtest.get('stabilite_wf','N/A')); r += 1
            _kpi(ws1, r, "Fenêtres testées", backtest.get('n_fenetres', 0), fmt=FMT_NB); r += 2

        _section(ws1, r, "▶ VALIDATION SÉLECTION"); r += 1
        statut = val_sel.get('statut_global', 'N/A')
        _kpi(ws1, r, "Statut global", statut, statut=statut); r += 1

        # ── Onglet 2 : Classement final ───────────────────────────────────────
        ws2 = wb.create_sheet("2-Classement final")
        _bandeau(ws2, "Classement Final", "Tous modèles — Score multicritères",
                 "A6 — Sélection", aid, now)
        r = 7
        _section(ws2, r, "▶ CLASSEMENT GLOBAL (GLM · ML · DL)"); r += 1
        for col, txt, w in [(1,"#",6),(2,"Modèle",28),(3,"Famille",12),
                             (4,"Gini test",14),(5,"RMSE test",14),
                             (6,"Overfit",12),(7,"Interprét.",12),(8,"Score final",14)]:
            _header(ws2, r, col, txt, w)
        r += 1
        for rank, m in enumerate(classement, 1):
            bg = GRIS_L if rank % 2 == 0 else None
            prod = rank == 1
            vals = [rank, m.get('modele',''), m.get('famille',''),
                    round(m.get('gini_test',0),4), round(m.get('rmse_test',0),4),
                    round(m.get('overfit_ratio',0),3), round(m.get('interpretabilite',0),2),
                    round(m.get('score_global',0),4)]
            fmts = [None,None,None,FMT_DEC4,FMT_DEC4,FMT_DEC4,FMT_DEC4,FMT_DEC4]
            for j,(v,f) in enumerate(zip(vals,fmts),1):
                _cell(ws2, r, j, v, cf=NOIR, fill=bg, fmt=f, bold=prod,
                      ah="right" if isinstance(v,(int,float)) else "left")
            if prod:
                ws2.cell(row=r, column=2).fill = _fill(OR)
                ws2.cell(row=r, column=2).font = _font(bold=True, color=BLANC, size=10)
            r += 1

        # ── Onglet 3 : Backtesting A/E ────────────────────────────────────────
        ws3 = wb.create_sheet("3-Backtesting AE")
        _bandeau(ws3, "Backtesting Walk-Forward", "Test A/E global et par segment",
                 "A6 — Backtesting", aid, now)
        r = 7
        _section(ws3, r, "▶ WALK-FORWARD TEMPOREL"); r += 1
        if backtest.get('walk_forward'):
            for col, txt, w in [(1,"Année test",14),(2,"N train",12),(3,"N test",10),
                                 (4,"Moy train",14),(5,"Moy test",14),
                                 (6,"A/E ratio",14),(7,"Statut",12)]:
                _header(ws3, r, col, txt, w)
            r += 1
            for wf in backtest.get('walk_forward', []):
                st = wf.get('statut','')
                bg = {"VERT":"EAF3DE","AMBRE":"FAEEDA","ROUGE":"FCEBEB"}.get(st, GRIS_L)
                vals = [wf.get('annee_test',''), wf.get('n_train',0), wf.get('n_test',0),
                        wf.get('moy_train',0), wf.get('moy_test',0), wf.get('ae_ratio',0), st]
                fmts = [None,FMT_NB,FMT_NB,FMT_DEC4,FMT_DEC4,FMT_DEC4,None]
                for j,(v,f) in enumerate(zip(vals,fmts),1):
                    _cell(ws3, r, j, v, cf=NOIR, fill=bg, fmt=f,
                          ah="right" if isinstance(v,(int,float)) else "center")
                r += 1
        r += 1
        # A/E par segment
        segs = backtest.get('ae_par_segment', {})
        for seg_name, seg_data in segs.items():
            if isinstance(seg_data, list) and seg_data:
                _section(ws3, r, f"▶ A/E PAR SEGMENT : {seg_name.upper()}"); r += 1
                first = seg_data[0]
                keys = [k for k in first.keys() if k != 'statut']
                for j, k in enumerate(keys, 1):
                    _header(ws3, r, j, k.replace('_',' ').title(), 16)
                _header(ws3, r, len(keys)+1, "Statut", 12)
                r += 1
                for item in seg_data:
                    st = item.get('statut','')
                    bg = {"VERT":"EAF3DE","AMBRE":"FAEEDA","ROUGE":"FCEBEB"}.get(st, GRIS_L)
                    for j, k in enumerate(keys, 1):
                        v = item.get(k, '')
                        _cell(ws3, r, j, v, cf=NOIR, fill=bg,
                              fmt=FMT_DEC4 if isinstance(v, float) else FMT_NB if isinstance(v, int) else None,
                              ah="right" if isinstance(v,(int,float)) else "left")
                    _cell(ws3, r, len(keys)+1, st, cf=BLANC,
                          fill=_statut_fill(st), ah="center")
                    r += 1
                r += 1

        # ── Onglet 4 : Fiche décision ─────────────────────────────────────────
        ws4 = wb.create_sheet("4-Fiche décision")
        _bandeau(ws4, "Fiche de Décision", "À valider par l'actuaire responsable",
                 "A6 — Décision production", aid, now)
        r = 7
        _section(ws4, r, "▶ CONTRÔLES SÉLECTION"); r += 1
        for ckey, clabel in [("c1_nb_modeles","C1 — Nb modèles"),
                               ("c2_ecart_gini","C2 — Écart Gini"),
                               ("c3_coherence", "C3 — Cohérence")]:
            c = val_sel.get(ckey, {})
            if c:
                st = c.get('statut','')
                _kpi(ws4, r, clabel, st, statut=st); r += 1
                _kpi(ws4, r, "  → Message", c.get('message',''), wrap=True); r += 1
                _kpi(ws4, r, "  → Conseil", c.get('conseil',''), wrap=True); r += 2

        if fiche:
            _section(ws4, r, "▶ FICHE ACTUARIELLE"); r += 1
            for k, v in fiche.items():
                if isinstance(v, str):
                    _kpi(ws4, r, k.replace('_',' ').title(), v, wrap=True); r += 1
        _section(ws4, r, "▶ DÉCISION FINALE"); r += 1
        _kpi(ws4, r, "Décision", "À VALIDER PAR L'ACTUAIRE RESPONSABLE",
             statut="AMBRE"); r += 1
        _kpi(ws4, r, "Modèle proposé",
             modele_prod.get('modele','') if modele_prod else 'N/A'); r += 1
        _kpi(ws4, r, "Date rapport", now); r += 1
        _kpi(ws4, r, "Signature actuaire", ""); r += 1

        # ── Onglet 5 : Audit Trail ────────────────────────────────────────────
        ws5 = wb.create_sheet("5-Audit Trail")
        _bandeau(ws5, "Audit Trail", "Traçabilité ACPR — Agent A6 Comparaison",
                 "A6 — Audit", aid, now)
        r = 7
        _section(ws5, r, "▶ INFORMATIONS AUDIT"); r += 1
        _kpi(ws5, r, "Audit ID",       aid); r += 1
        _kpi(ws5, r, "Date",           now); r += 1
        _kpi(ws5, r, "Agent",          "A6 — Comparaison & Validation Finale"); r += 1
        _kpi(ws5, r, "Branche",        result_a6.get('branche','N/A')); r += 1
        _kpi(ws5, r, "Statut RAG",     result_a6.get('statut_rag','N/A'),
             statut=result_a6.get('statut_rag')); r += 1
        _kpi(ws5, r, "Nb modèles comparés", len(classement), fmt=FMT_NB); r += 1
        _kpi(ws5, r, "Modèle production",
             modele_prod.get('modele','') if modele_prod else 'N/A'); r += 1
        _kpi(ws5, r, "A/E ratio final", round(backtest.get('ae_ratio',0),4),
             fmt=FMT_DEC4); r += 1

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    except Exception as e:
        logger.error(f"export_excel_a6 échoué : {e}", exc_info=True)
        return b''
