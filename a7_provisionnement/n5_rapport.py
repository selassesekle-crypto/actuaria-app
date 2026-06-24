# =============================================================================
#  ActuarIA — Agent A7 Ibrahim v5.0
#  n5_rapport.py  —  Export Word (.docx) + PDF
#  Générateur : python-docx (Word) + reportlab (PDF)
#  Pas de dépendance système (pas Node.js, pas LibreOffice)
# =============================================================================

import io
import logging
import os
from datetime import datetime
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger('actuaria.a7')

# Palette
NAVY    = '#0F2E52'
GOLD    = '#C9A84C'
BLANC   = '#FFFFFF'
GRIS    = '#8A9BB0'


# =============================================================================
#  HELPERS COMMUNS
# =============================================================================

def _f(v, decimals=0) -> str:
    """Formate un float en string lisible, '--' si None/NaN."""
    if v is None:
        return '—'
    try:
        fv = float(v)
        if np.isnan(fv) or np.isinf(fv):
            return '—'
        if decimals == 0:
            return f"{fv:,.0f} €".replace(',', ' ')
        return f"{fv:,.{decimals}f}".replace(',', ' ')
    except Exception:
        return '—'


def _pct(v, decimals=1) -> str:
    """Formate un float en pourcentage."""
    if v is None:
        return '—'
    try:
        fv = float(v)
        if np.isnan(fv) or np.isinf(fv):
            return '—'
        return f"{fv:.{decimals}f} %"
    except Exception:
        return '—'


def _ok(b: bool) -> str:
    return '✓ VALIDÉE' if b else '✗ REJETÉE'


# =============================================================================
#  EXPORT PNG DES GRAPHIQUES (optionnel — kaleido)
# =============================================================================

def exporter_graphiques_png(graphiques: Dict, width: int = 900, height: int = 380) -> Dict[str, bytes]:
    pngs = {}
    try:
        import plotly.io as pio
        for nom, fig in graphiques.items():
            try:
                png = pio.to_image(fig, format='png', width=width, height=height)
                pngs[nom] = png
            except Exception as e:
                logger.debug(f"PNG {nom} ignoré : {e}")
    except Exception:
        logger.info("kaleido absent — graphiques PNG désactivés dans le rapport")
    return pngs


# =============================================================================
#  EXPORT WORD  (python-docx)
# =============================================================================

def export_word(
    n1: Dict, n2: Dict, n3: Dict, n4: Dict,
    commentaire: str = '',
    ref_client:  str = '',
    arrete:      str = '',
    audit_id:    str = '',
    lob_label:   str = '',
    graphiques:  Dict = None,
) -> bytes:
    """
    Génère le rapport Word professionnel via python-docx.
    Retourne bytes du .docx, ou b'' si échec.
    """
    try:
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_ALIGN_VERTICAL
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        import lxml.etree as etree
    except ImportError as e:
        logger.error(f"python-docx non disponible : {e}")
        return b''

    try:
        doc = Document()

        # ── Marges ────────────────────────────────────────────────────────
        for section in doc.sections:
            section.top_margin    = Cm(2.0)
            section.bottom_margin = Cm(2.0)
            section.left_margin   = Cm(2.5)
            section.right_margin  = Cm(2.5)

        # ── Couleurs RGB ───────────────────────────────────────────────────
        NAVY_RGB = RGBColor(0x0F, 0x2E, 0x52)
        GOLD_RGB = RGBColor(0xC9, 0xA8, 0x4C)
        GRIS_RGB = RGBColor(0x8A, 0x9B, 0xB0)
        ROUGE_RGB = RGBColor(0xC0, 0x39, 0x2B)

        def _style_run(run, bold=False, size=10, color=None, italic=False):
            run.bold   = bold
            run.italic = italic
            run.font.size = Pt(size)
            if color:
                run.font.color.rgb = color

        def _heading(text, level=1, color=None):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after  = Pt(4)
            run = p.add_run(text)
            sz  = {1: 14, 2: 11, 3: 10}.get(level, 10)
            _style_run(run, bold=True, size=sz, color=color or NAVY_RGB)
            return p

        def _para(text, size=9, color=None, bold=False, space_after=4):
            p = doc.add_paragraph()
            p.paragraph_format.space_after  = Pt(space_after)
            p.paragraph_format.space_before = Pt(0)
            run = p.add_run(str(text))
            _style_run(run, bold=bold, size=size, color=color)
            return p

        def _separator():
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after  = Pt(2)
            run = p.add_run('─' * 80)
            run.font.size  = Pt(7)
            run.font.color.rgb = GRIS_RGB

        def _table_simple(headers, rows, col_widths=None):
            t = doc.add_table(rows=1 + len(rows), cols=len(headers))
            t.style = 'Table Grid'
            # Header row
            hdr = t.rows[0]
            for i, h in enumerate(headers):
                cell = hdr.cells[i]
                cell.text = h
                run = cell.paragraphs[0].runs[0] if cell.paragraphs[0].runs else cell.paragraphs[0].add_run(h)
                run.bold = True
                run.font.size = Pt(8)
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                # Fond navy
                tc  = cell._tc
                tcp = tc.get_or_add_tcPr()
                shd = OxmlElement('w:shd')
                shd.set(qn('w:fill'), '0F2E52')
                shd.set(qn('w:color'), 'auto')
                shd.set(qn('w:val'), 'clear')
                tcp.append(shd)
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            # Data rows
            for ri, row in enumerate(rows):
                tr = t.rows[ri + 1]
                for ci, val in enumerate(row):
                    cell = tr.cells[ci]
                    cell.text = str(val)
                    run = cell.paragraphs[0].runs[0] if cell.paragraphs[0].runs else cell.paragraphs[0].add_run(str(val))
                    run.font.size = Pt(8)
                    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                    # Alternance gris clair
                    if ri % 2 == 1:
                        tc  = cell._tc
                        tcp = tc.get_or_add_tcPr()
                        shd = OxmlElement('w:shd')
                        shd.set(qn('w:fill'), 'EEF2F7')
                        shd.set(qn('w:color'), 'auto')
                        shd.set(qn('w:val'), 'clear')
                        tcp.append(shd)
            if col_widths:
                for i, w in enumerate(col_widths):
                    for row in t.rows:
                        row.cells[i].width = Cm(w)
            doc.add_paragraph()
            return t

        def _embed_png(png_bytes: bytes, label: str, width_cm=15):
            if not png_bytes:
                _para(f'[Graphique : {label}]', size=8, color=GRIS_RGB, italic=True)
                return
            try:
                img_stream = io.BytesIO(png_bytes)
                doc.add_picture(img_stream, width=Cm(width_cm))
                _para(f'Figure : {label}', size=7, color=GRIS_RGB, italic=True)
            except Exception as e:
                _para(f'[Graphique {label} — erreur : {e}]', size=8, color=GRIS_RGB)

        # Exporter graphiques PNG si kaleido dispo
        pngs = exporter_graphiques_png(graphiques or {})

        # Données
        cl   = n3.get('chain_ladder', {})
        mack = n3.get('mack', {})
        bf   = n3.get('bf', {})
        cc   = n3.get('cape_cod', {})
        boot = n3.get('bootstrap', {})
        scr  = n4.get('scr', {})
        h1   = n2.get('h1_independance', {})
        h2   = n2.get('h2_stabilite', {})
        h3   = n2.get('h3_apriori_bf', {})
        h4   = n2.get('h4_homosc_bootstrap', {})

        be_val = float(n4.get('best_estimate', 0) or 0)
        sigma  = float(n4.get('sigma_mack', mack.get('sigma_total', 0)) or 0)
        cv_val = float(n4.get('cv_inter_methodes', 0) or 0)
        p75    = float(n4.get('reserve_p75', 0) or 0)
        p90    = float(n4.get('reserve_p90', mack.get('reserve_p90', 0)) or 0)
        p99    = float(n4.get('reserve_p99_5', 0) or 0)
        scr_prov = float(scr.get('scr_prov', be_val * 0.10 * 3) if scr else be_val * 0.10 * 3)

        date_str  = datetime.now().strftime('%d/%m/%Y')
        arrete_s  = arrete or date_str
        client_s  = ref_client or 'ActuarIA'
        lob_s     = lob_label or n2.get('lob_label', '—')
        methode_s = n4.get('methode_facteurs', n2.get('methode_recommandee', '—'))

        # ══════════════════════════════════════════════════════════════════
        # PAGE DE GARDE
        # ══════════════════════════════════════════════════════════════════
        doc.add_paragraph()
        p_titre = doc.add_paragraph()
        p_titre.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p_titre.add_run('RAPPORT ACTUARIEL\nPROVISIONNEMENT NON-VIE')
        run.bold = True
        run.font.size = Pt(22)
        run.font.color.rgb = NAVY_RGB

        doc.add_paragraph()
        p_sub = doc.add_paragraph()
        p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run2 = p_sub.add_run(f'Arrêté : {arrete_s}  ·  Branche : {lob_s}\n{client_s}')
        run2.font.size = Pt(12)
        run2.font.color.rgb = GOLD_RGB

        doc.add_paragraph()
        p_conf = doc.add_paragraph()
        p_conf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run3 = p_conf.add_run('CONFIDENTIEL — USAGE STRICTEMENT ACTUARIEL')
        run3.bold = True
        run3.font.color.rgb = ROUGE_RGB
        run3.font.size = Pt(10)

        doc.add_paragraph()
        _table_simple(
            ['Référence', 'Méthode retenue', 'Date', 'Audit ID'],
            [[client_s, methode_s, date_str, audit_id or '—']],
            col_widths=[4.5, 4.5, 3, 4]
        )

        doc.add_page_break()

        # ══════════════════════════════════════════════════════════════════
        # 1. SYNTHÈSE EXÉCUTIVE
        # ══════════════════════════════════════════════════════════════════
        _heading('1. SYNTHÈSE EXÉCUTIVE', level=1)
        _separator()

        _table_simple(
            ['KPI', 'Valeur', 'KPI', 'Valeur'],
            [
                ['Best Estimate S2', _f(be_val),  'σ Mack total',    _f(sigma)],
                ['Provision P75',    _f(p75),      'CV inter-méthodes', _pct(cv_val)],
                ['Provision P90',    _f(p90),      'SCR provisions',  _f(scr_prov)],
                ['Provision P99.5',  _f(p99),      'Ratio SCR/BE',    _pct(scr_prov / be_val * 100 if be_val else 0)],
            ],
            col_widths=[4, 3.5, 4, 3.5]
        )

        if commentaire:
            _heading('Points saillants', level=2, color=GOLD_RGB)
            # Garder les 800 premiers caractères pour la synthèse
            _para(commentaire[:800] + ('…' if len(commentaire) > 800 else ''), size=9)

        doc.add_page_break()

        # ══════════════════════════════════════════════════════════════════
        # 2. MÉTHODOLOGIE ET RÉSULTATS
        # ══════════════════════════════════════════════════════════════════
        _heading('2. PROVISIONNEMENT NON-VIE — RÉSULTATS PAR MÉTHODE', level=1)
        _separator()

        poids = n4.get('poids', {})
        _table_simple(
            ['Méthode', 'Réserve (€)', 'Poids BE', 'Score /100', 'Statut'],
            [
                ['Chain Ladder',       _f(cl.get('reserve_totale')),  _pct(poids.get('chain_ladder', 0) * 100),  str(n2.get('scores_confiance', {}).get('chain_ladder', '—')),  '✓'],
                ['Mack 1993',          _f(mack.get('reserve_best_estimate')), _pct(poids.get('mack', 0) * 100), str(n2.get('scores_confiance', {}).get('mack', '—')),  '✓'],
                ['Bornhuetter-Ferguson', _f(bf.get('reserve_totale')),  _pct(poids.get('bf', 0) * 100),    str(n2.get('scores_confiance', {}).get('bf', '—')),    '✓'],
                ['Cape Cod',           _f(cc.get('reserve_totale')),   _pct(poids.get('cape_cod', 0) * 100), str(n2.get('scores_confiance', {}).get('cape_cod', '—')), '✓'],
                ['⭐ BEST ESTIMATE S2', _f(be_val),                    '100 %',                              '—',                                                        '→ Bilan'],
            ],
            col_widths=[4.5, 3.5, 2.5, 2.5, 2]
        )

        # Triangle heatmap
        if pngs.get('g1_heatmap'):
            _heading('Triangle de développement', level=2, color=GOLD_RGB)
            _embed_png(pngs['g1_heatmap'], 'Triangle de développement cumulé')

        # Facteurs
        if pngs.get('g2_facteurs_cl'):
            _heading('Facteurs de développement ±2σ', level=2, color=GOLD_RGB)
            _embed_png(pngs['g2_facteurs_cl'], 'Facteurs Chain Ladder ±2σ')

        # IBNR
        if pngs.get('g3_ibnr'):
            _heading('IBNR par année de survenance', level=2, color=GOLD_RGB)
            _embed_png(pngs['g3_ibnr'], 'IBNR par année')

        # Convergence
        if pngs.get('g4_convergence'):
            _heading('Convergence des méthodes', level=2, color=GOLD_RGB)
            _embed_png(pngs['g4_convergence'], 'Convergence CL / Mack / BF / Cape Cod')

        doc.add_page_break()

        # ══════════════════════════════════════════════════════════════════
        # 3. VALIDATION DES HYPOTHÈSES
        # ══════════════════════════════════════════════════════════════════
        _heading('3. VALIDATION DES HYPOTHÈSES ACTUARIELLES', level=1)
        _separator()

        _table_simple(
            ['Hypothèse', 'Résultat', 'Score', 'Indicateur clé', 'Message'],
            [
                ['H1 — Indépendance',    _ok(h1.get('ok', True)), str(h1.get('score', '—')),
                 f"corr_moy={h1.get('corr_moy', '—')}", str(h1.get('message', '—'))[:80]],
                ['H2 — Stabilité',       _ok(h2.get('ok', True)), str(h2.get('score', '—')),
                 f"CV={h2.get('cv_moy', '—')}", str(h2.get('message', '—'))[:80]],
                ['H3 — A priori BF',     _ok(h3.get('ok', True)), str(h3.get('score', '—')),
                 f"LR={h3.get('lr_apriori', '—')}", str(h3.get('message', '—'))[:80]],
                ['H4 — Homoscédasticité', _ok(h4.get('ok', True)), str(h4.get('score', '—')),
                 f"φ={h4.get('phi', '—')}", str(h4.get('message', '—'))[:80]],
            ],
            col_widths=[3.5, 2.5, 1.5, 3, 5.5]
        )

        # Bootstrap
        _heading('Incertitude stochastique — Bootstrap ODP (England-Verrall 2002)', level=2, color=GOLD_RGB)
        _table_simple(
            ['Quantile', 'P50', 'P75', 'P90', 'P99.5'],
            [['Provision (€)',
              _f(boot.get('reserve_p50', be_val)),
              _f(p75), _f(p90), _f(p99)]],
            col_widths=[4, 3, 3, 3, 3]
        )

        if pngs.get('g5_bootstrap'):
            _embed_png(pngs['g5_bootstrap'], 'Distribution Bootstrap ODP')

        doc.add_page_break()

        # ══════════════════════════════════════════════════════════════════
        # 4. SCR PROVISIONS (Art. 105 S2)
        # ══════════════════════════════════════════════════════════════════
        _heading('4. SCR PROVISIONS — ART. 105 SOLVABILITÉ 2', level=1)
        _separator()

        scr_ratio = scr_prov / be_val * 100 if be_val else 0
        _table_simple(
            ['Composante', 'Valeur', 'Commentaire'],
            [
                ['Best Estimate S2',  _f(be_val),   'Art. 77 Directive S2'],
                ['Facteur σ EIOPA',   '10 %',        f'LoB : {lob_s}'],
                ['SCR provisions',    _f(scr_prov),  'SCR = 3 × σ × BE'],
                ['Ratio SCR/BE',      _pct(scr_ratio), 'Cible < 35 %'],
            ],
            col_widths=[5, 4, 7]
        )

        doc.add_page_break()

        # ══════════════════════════════════════════════════════════════════
        # 5. COMMENTAIRE COMPLET & SIGNATURE
        # ══════════════════════════════════════════════════════════════════
        _heading('5. COMMENTAIRE ACTUARIEL COMPLET', level=1)
        _separator()

        if commentaire:
            # Découper le commentaire par sections
            import re
            sections = re.split(r'(?=\d+\.\s+[A-ZÀÂÉÈÊ])', commentaire.strip())
            for sec in sections:
                sec = sec.strip()
                if not sec:
                    continue
                lines = sec.split('\n', 1)
                titre_sec = lines[0].strip()
                corps_sec = lines[1].strip() if len(lines) > 1 else ''
                corps_sec = re.sub(r'─+', '', corps_sec).strip()
                if titre_sec:
                    _heading(titre_sec, level=2, color=GOLD_RGB)
                if corps_sec:
                    _para(corps_sec, size=9)
        else:
            _para('Commentaire non disponible.', size=9, color=GRIS_RGB)

        _separator()
        doc.add_paragraph()
        _heading('Jugement actuariel documenté', level=2, color=GOLD_RGB)
        jugement = n4.get('jugement', '')
        if jugement:
            import re
            sections_j = re.split(r'(?=\d+\.\s+[A-ZÀÂÉÈÊ])', jugement.strip())
            for sec in sections_j:
                sec = sec.strip()
                if not sec:
                    continue
                lines = sec.split('\n', 1)
                titre_sec = lines[0].strip()
                corps_sec = lines[1].strip() if len(lines) > 1 else ''
                corps_sec = re.sub(r'─+', '', corps_sec).strip()
                if titre_sec:
                    _heading(titre_sec, level=3, color=NAVY_RGB)
                if corps_sec:
                    _para(corps_sec, size=9)

        doc.add_paragraph()
        _separator()
        _para(
            f"Rapport généré par ActuarIA · {date_str} · Arrêté {arrete_s} · "
            f"Audit ID : {audit_id or '—'} · CONFIDENTIEL",
            size=7, color=GRIS_RGB
        )

        # Sérialiser
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        word_bytes = buf.read()
        logger.info(f"Word généré (python-docx) : {len(word_bytes):,} bytes")
        return word_bytes

    except Exception as e:
        logger.error(f"export_word échoué : {e}", exc_info=True)
        return b''


# =============================================================================
#  EXPORT PDF  (reportlab)
# =============================================================================

def export_pdf(word_bytes: bytes = b'', **kwargs) -> bytes:
    """
    Génère le PDF directement via reportlab.
    Accepte aussi les mêmes kwargs que export_word pour génération directe.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak, HRFlowable
        )
        from reportlab.platypus import Image as RLImage
    except ImportError as e:
        logger.error(f"reportlab non disponible : {e}")
        return b''

    try:
        # Récupérer les données depuis kwargs ou valeurs vides
        n1          = kwargs.get('n1', {})
        n2          = kwargs.get('n2', {})
        n3          = kwargs.get('n3', {})
        n4          = kwargs.get('n4', {})
        commentaire = kwargs.get('commentaire', '')
        ref_client  = kwargs.get('ref_client', '')
        arrete      = kwargs.get('arrete', '')
        audit_id    = kwargs.get('audit_id', '')
        lob_label   = kwargs.get('lob_label', '')
        graphiques  = kwargs.get('graphiques', {})

        cl   = n3.get('chain_ladder', {})
        mack = n3.get('mack', {})
        bf   = n3.get('bf', {})
        cc   = n3.get('cape_cod', {})
        boot = n3.get('bootstrap', {})
        scr  = n4.get('scr', {})
        h1   = n2.get('h1_independance', {})
        h2   = n2.get('h2_stabilite', {})
        h3   = n2.get('h3_apriori_bf', {})
        h4   = n2.get('h4_homosc_bootstrap', {})

        be_val   = float(n4.get('best_estimate', 0) or 0)
        sigma    = float(n4.get('sigma_mack', mack.get('sigma_total', 0)) or 0)
        cv_val   = float(n4.get('cv_inter_methodes', 0) or 0)
        p75      = float(n4.get('reserve_p75', 0) or 0)
        p90      = float(n4.get('reserve_p90', mack.get('reserve_p90', 0)) or 0)
        p99      = float(n4.get('reserve_p99_5', 0) or 0)
        scr_prov = float(scr.get('scr_prov', be_val * 0.30) if scr else be_val * 0.30)

        date_str = datetime.now().strftime('%d/%m/%Y')
        arrete_s = arrete or date_str
        client_s = ref_client or 'ActuarIA'
        lob_s    = lob_label or n2.get('lob_label', '—')
        methode_s = n4.get('methode_facteurs', n2.get('methode_recommandee', '—'))
        poids    = n4.get('poids', {})

        # Couleurs RL
        NAVY_RL  = colors.HexColor('#0F2E52')
        GOLD_RL  = colors.HexColor('#C9A84C')
        GRIS_RL  = colors.HexColor('#8A9BB0')
        ROUGE_RL = colors.HexColor('#C0392B')
        BLANC_RL = colors.white
        LGRIS_RL = colors.HexColor('#EEF2F7')

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            topMargin=2*cm, bottomMargin=2*cm,
            leftMargin=2.5*cm, rightMargin=2.5*cm,
            title=f"Rapport Actuariel {arrete_s}",
            author="ActuarIA",
        )

        styles = getSampleStyleSheet()
        S = {
            'titre':   ParagraphStyle('titre',   fontSize=20, fontName='Helvetica-Bold',
                                      textColor=NAVY_RL, alignment=1, spaceAfter=8),
            'sous':    ParagraphStyle('sous',    fontSize=12, fontName='Helvetica',
                                      textColor=GOLD_RL, alignment=1, spaceAfter=6),
            'conf':    ParagraphStyle('conf',    fontSize=9,  fontName='Helvetica-Bold',
                                      textColor=ROUGE_RL, alignment=1, spaceAfter=12),
            'h1':      ParagraphStyle('h1',      fontSize=13, fontName='Helvetica-Bold',
                                      textColor=NAVY_RL, spaceBefore=10, spaceAfter=4),
            'h2':      ParagraphStyle('h2',      fontSize=10, fontName='Helvetica-Bold',
                                      textColor=GOLD_RL, spaceBefore=6, spaceAfter=3),
            'h3':      ParagraphStyle('h3',      fontSize=9,  fontName='Helvetica-Bold',
                                      textColor=NAVY_RL, spaceBefore=4, spaceAfter=2),
            'body':    ParagraphStyle('body',    fontSize=8,  fontName='Helvetica',
                                      textColor=colors.black, spaceAfter=4, leading=12),
            'footer':  ParagraphStyle('footer',  fontSize=6,  fontName='Helvetica',
                                      textColor=GRIS_RL, alignment=1),
        }

        def _tbl_style(header_col=NAVY_RL, alt_col=LGRIS_RL, n_data_rows=1):
            cmds = [
                ('BACKGROUND', (0, 0), (-1, 0), header_col),
                ('TEXTCOLOR',  (0, 0), (-1, 0), BLANC_RL),
                ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE',   (0, 0), (-1, -1), 8),
                ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#D0D8E4')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [BLANC_RL, alt_col]),
                ('TOPPADDING',  (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]
            return TableStyle(cmds)

        def _make_table(headers, rows, col_widths=None):
            data = [[Paragraph(str(h), ParagraphStyle('th', fontSize=8, fontName='Helvetica-Bold',
                               textColor=BLANC_RL, alignment=1)) for h in headers]]
            for row in rows:
                data.append([Paragraph(str(c), ParagraphStyle('td', fontSize=8, fontName='Helvetica',
                             alignment=1)) for c in row])
            t = Table(data, colWidths=col_widths, repeatRows=1)
            t.setStyle(_tbl_style())
            return t

        story = []

        # ── PAGE DE GARDE ─────────────────────────────────────────────────
        story.append(Spacer(1, 3*cm))
        story.append(Paragraph('RAPPORT ACTUARIEL<br/>PROVISIONNEMENT NON-VIE', S['titre']))
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(f'Arrêté : {arrete_s}  ·  Branche : {lob_s}<br/>{client_s}', S['sous']))
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph('CONFIDENTIEL — USAGE STRICTEMENT ACTUARIEL', S['conf']))
        story.append(Spacer(1, 1*cm))
        story.append(_make_table(
            ['Référence', 'Méthode retenue', 'Date', 'Audit ID'],
            [[client_s, methode_s, date_str, audit_id or '—']],
            col_widths=[4*cm, 5*cm, 3*cm, 4*cm]
        ))
        story.append(PageBreak())

        # ── 1. SYNTHÈSE ───────────────────────────────────────────────────
        story.append(Paragraph('1. SYNTHÈSE EXÉCUTIVE', S['h1']))
        story.append(HRFlowable(width='100%', thickness=1, color=NAVY_RL, spaceAfter=6))
        story.append(_make_table(
            ['KPI', 'Valeur', 'KPI', 'Valeur'],
            [
                ['Best Estimate S2', _f(be_val),  'σ Mack total',     _f(sigma)],
                ['Provision P75',    _f(p75),      'CV inter-méthodes', _pct(cv_val)],
                ['Provision P90',    _f(p90),      'SCR provisions',   _f(scr_prov)],
                ['Provision P99.5',  _f(p99),      'Ratio SCR/BE',     _pct(scr_prov / be_val * 100 if be_val else 0)],
            ],
            col_widths=[4*cm, 4*cm, 4*cm, 4*cm]
        ))
        if commentaire:
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph('Points saillants', S['h2']))
            story.append(Paragraph(commentaire[:800].replace('\n', '<br/>'), S['body']))
        story.append(PageBreak())

        # ── 2. RÉSULTATS ──────────────────────────────────────────────────
        story.append(Paragraph('2. RÉSULTATS PAR MÉTHODE', S['h1']))
        story.append(HRFlowable(width='100%', thickness=1, color=NAVY_RL, spaceAfter=6))
        story.append(_make_table(
            ['Méthode', 'Réserve (€)', 'Poids', 'Score', 'Statut'],
            [
                ['Chain Ladder', _f(cl.get('reserve_totale')),
                 _pct(poids.get('chain_ladder', 0)*100), str(n2.get('scores_confiance', {}).get('chain_ladder', '—')), '✓'],
                ['Mack 1993', _f(mack.get('reserve_best_estimate')),
                 _pct(poids.get('mack', 0)*100), str(n2.get('scores_confiance', {}).get('mack', '—')), '✓'],
                ['Bornhuetter-Ferguson', _f(bf.get('reserve_totale')),
                 _pct(poids.get('bf', 0)*100), str(n2.get('scores_confiance', {}).get('bf', '—')), '✓'],
                ['Cape Cod', _f(cc.get('reserve_totale')),
                 _pct(poids.get('cape_cod', 0)*100), str(n2.get('scores_confiance', {}).get('cape_cod', '—')), '✓'],
                ['⭐ BEST ESTIMATE S2', _f(be_val), '100 %', '—', '→ Bilan'],
            ],
            col_widths=[4.5*cm, 3.5*cm, 2.5*cm, 2*cm, 2.5*cm]
        ))

        # Graphiques PNG si dispo
        pngs = exporter_graphiques_png(graphiques or {})
        for nom_g, label_g in [
            ('g1_heatmap', 'Triangle de développement'),
            ('g2_facteurs_cl', 'Facteurs ±2σ'),
            ('g3_ibnr', 'IBNR par année'),
            ('g4_convergence', 'Convergence des méthodes'),
        ]:
            if pngs.get(nom_g):
                story.append(Spacer(1, 0.3*cm))
                story.append(Paragraph(label_g, S['h2']))
                img_stream = io.BytesIO(pngs[nom_g])
                story.append(RLImage(img_stream, width=15*cm, height=6*cm))
        story.append(PageBreak())

        # ── 3. HYPOTHÈSES ─────────────────────────────────────────────────
        story.append(Paragraph('3. VALIDATION DES HYPOTHÈSES', S['h1']))
        story.append(HRFlowable(width='100%', thickness=1, color=NAVY_RL, spaceAfter=6))
        story.append(_make_table(
            ['Hypothèse', 'Résultat', 'Score', 'Indicateur', 'Message'],
            [
                ['H1 — Indépendance', _ok(h1.get('ok', True)), str(h1.get('score','—')),
                 f"corr={h1.get('corr_moy','—')}", str(h1.get('message','—'))[:70]],
                ['H2 — Stabilité', _ok(h2.get('ok', True)), str(h2.get('score','—')),
                 f"CV={h2.get('cv_moy','—')}", str(h2.get('message','—'))[:70]],
                ['H3 — A priori BF', _ok(h3.get('ok', True)), str(h3.get('score','—')),
                 f"LR={h3.get('lr_apriori','—')}", str(h3.get('message','—'))[:70]],
                ['H4 — Homoscédasticité', _ok(h4.get('ok', True)), str(h4.get('score','—')),
                 f"φ={h4.get('phi','—')}", str(h4.get('message','—'))[:70]],
            ],
            col_widths=[3.5*cm, 2.5*cm, 1.5*cm, 3*cm, 5*cm]
        ))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph('Bootstrap ODP — England-Verrall 2002', S['h2']))
        story.append(_make_table(
            ['P50', 'P75', 'P90', 'P99.5'],
            [[_f(boot.get('reserve_p50', be_val)), _f(p75), _f(p90), _f(p99)]],
            col_widths=[4*cm, 4*cm, 4*cm, 4*cm]
        ))
        story.append(PageBreak())

        # ── 4. SCR ────────────────────────────────────────────────────────
        story.append(Paragraph('4. SCR PROVISIONS — ART. 105 SOLVABILITÉ 2', S['h1']))
        story.append(HRFlowable(width='100%', thickness=1, color=NAVY_RL, spaceAfter=6))
        scr_ratio = scr_prov / be_val * 100 if be_val else 0
        story.append(_make_table(
            ['Composante', 'Valeur', 'Note'],
            [
                ['Best Estimate S2', _f(be_val),   'Art. 77'],
                ['Facteur σ EIOPA',  '10 %',        f'LoB : {lob_s}'],
                ['SCR provisions',   _f(scr_prov),  'SCR = 3 × σ × BE'],
                ['Ratio SCR/BE',     _pct(scr_ratio), 'Cible < 35 %'],
            ],
            col_widths=[5*cm, 4*cm, 7*cm]
        ))
        story.append(PageBreak())

        # ── 5. COMMENTAIRE ────────────────────────────────────────────────
        story.append(Paragraph('5. COMMENTAIRE ACTUARIEL', S['h1']))
        story.append(HRFlowable(width='100%', thickness=1, color=NAVY_RL, spaceAfter=6))
        if commentaire:
            import re
            secs = re.split(r'(?=\d+\.\s+[A-ZÀÂÉÈÊ])', commentaire.strip())
            for sec in secs:
                sec = sec.strip()
                if not sec:
                    continue
                lines = sec.split('\n', 1)
                titre_s = lines[0].strip()
                corps_s = lines[1].strip() if len(lines) > 1 else ''
                corps_s = re.sub(r'─+', '', corps_s).strip()
                if titre_s:
                    story.append(Paragraph(titre_s, S['h2']))
                if corps_s:
                    story.append(Paragraph(corps_s.replace('\n', '<br/>'), S['body']))

        jugement = n4.get('jugement', '')
        if jugement:
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph('Jugement actuariel documenté', S['h2']))
            import re
            secs_j = re.split(r'(?=\d+\.\s+[A-ZÀÂÉÈÊ])', jugement.strip())
            for sec in secs_j:
                sec = sec.strip()
                if not sec:
                    continue
                lines = sec.split('\n', 1)
                titre_s = lines[0].strip()
                corps_s = lines[1].strip() if len(lines) > 1 else ''
                corps_s = re.sub(r'─+', '', corps_s).strip()
                if titre_s:
                    story.append(Paragraph(titre_s, S['h3']))
                if corps_s:
                    story.append(Paragraph(corps_s.replace('\n', '<br/>'), S['body']))

        # Footer
        story.append(Spacer(1, 0.5*cm))
        story.append(HRFlowable(width='100%', thickness=0.5, color=GRIS_RL))
        story.append(Paragraph(
            f"ActuarIA · {date_str} · Arrêté {arrete_s} · Audit ID : {audit_id or '—'} · CONFIDENTIEL",
            S['footer']
        ))

        doc.build(story)
        buf.seek(0)
        pdf_bytes = buf.read()
        logger.info(f"PDF généré (reportlab) : {len(pdf_bytes):,} bytes")
        return pdf_bytes

    except Exception as e:
        logger.error(f"export_pdf échoué : {e}", exc_info=True)
        return b''
