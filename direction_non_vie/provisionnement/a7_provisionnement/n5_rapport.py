# =============================================================================
#  ActuarIA — Agent A7 Ibrahim v5.0
#  n5_rapport.py  —  Export Word (.docx) + PDF professionnel
#
#  Structure : 6 sections, pas de duplication, graphiques embarqués via kaleido
#  Palette   : Navy #0F2E52 / Gold #C9A84C
# =============================================================================

from __future__ import annotations
import io, logging, re
from datetime import datetime
from typing import Dict
import numpy as np

logger = logging.getLogger('actuaria.a7.rapport')

NAVY = '0F2E52'; NAVY_L = '1A3F6B'; GOLD = 'C9A84C'
BLANC = 'FFFFFF'; GRIS = '8A9BB0'; ROUGE = 'C0392B'
VERT = '27AE60'; AMBRE = 'F39C12'


# ── Helpers numériques ────────────────────────────────────────────────────────

def _f(v, dec=0):
    if v is None: return '—'
    try:
        fv = float(v)
        if np.isnan(fv) or np.isinf(fv): return '—'
        return f"{fv:,.0f} €".replace(',', ' ') if dec == 0 else f"{fv:,.{dec}f}".replace(',', ' ')
    except: return '—'

def _pct(v, dec=1):
    if v is None: return '—'
    try:
        fv = float(v)
        return '—' if (np.isnan(fv) or np.isinf(fv)) else f"{fv:.{dec}f} %"
    except: return '—'

def _ok(b): return 'VALIDÉE' if b else 'REJETÉE'

def _clean(txt):
    """Nettoyer les caractères illisibles du commentaire."""
    if not txt: return ''
    txt = re.sub(r'[■□▪▸►═╔╗╚╝║]+', '', txt)
    txt = re.sub(r'─+', '', txt)
    txt = re.sub(r'={4,}', '', txt)
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    return txt.strip()


# ── Export PNG graphiques ─────────────────────────────────────────────────────

def _pngs(graphiques: Dict, w=900, h=360) -> Dict[str, bytes]:
    out = {}
    if not graphiques: return out
    try:
        import plotly.io as pio
        for nom, fig in graphiques.items():
            try:
                out[nom] = pio.to_image(fig, format='png', width=w, height=h, scale=2)
            except Exception as e:
                logger.debug(f"PNG {nom} : {e}")
    except ImportError:
        logger.info("kaleido absent — graphiques omis")
    return out


# =============================================================================
#  EXPORT WORD
# =============================================================================

def export_word(
    n1: Dict, n2: Dict, n3: Dict, n4: Dict,
    commentaire='', ref_client='', arrete='',
    audit_id='', lob_label='', graphiques=None,
) -> bytes:
    try:
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError as e:
        logger.error(f"python-docx absent : {e}"); return b''

    try:
        def rgb(h):
            h = h.lstrip('#')
            return RGBColor(int(h[:2],16), int(h[2:4],16), int(h[4:],16))

        NR=rgb(NAVY); GR=rgb(GOLD); BR=rgb(BLANC); GrR=rgb(GRIS)
        RgR=rgb(ROUGE); VR=rgb(VERT); AR=rgb(AMBRE)

        doc = Document()
        for s in doc.sections:
            s.top_margin=Cm(2); s.bottom_margin=Cm(2)
            s.left_margin=Cm(2.5); s.right_margin=Cm(2.5)

        # ── Données ───────────────────────────────────────────────────────────
        cl  = n3.get('chain_ladder',{}); mk = n3.get('mack',{})
        bf  = n3.get('bf',{});           cc = n3.get('cape_cod',{})
        bt  = n3.get('bootstrap',{});    sc = n4.get('scr',{})
        h1=n2.get('h1_independance',{}); h2=n2.get('h2_stabilite',{})
        h3=n2.get('h3_apriori_bf',{});   h4=n2.get('h4_homosc_bootstrap',{})
        pw = n4.get('poids',{})

        BE   = float(n4.get('best_estimate',0) or 0)
        SIG  = float(mk.get('sigma_total', n4.get('sigma_mack',0)) or 0)
        CV   = float(n4.get('cv_inter_methodes',0) or 0)
        P75  = float(n4.get('reserve_p75',0) or 0)
        P90  = float(n4.get('reserve_p90', mk.get('reserve_p90',0)) or 0)
        P99  = float(n4.get('reserve_p99_5',0) or 0)
        SCP  = float(sc.get('scr_prov', BE*0.30) if sc else BE*0.30)
        SCR  = SCP/BE*100 if BE else 0

        dt    = datetime.now().strftime('%d/%m/%Y')
        arr   = arrete or dt
        cli   = ref_client or 'ActuarIA'
        lob   = lob_label or n2.get('lob_label','—')
        meth  = n4.get('methode_facteurs', n2.get('methode_recommandee','—'))
        stat  = n4.get('statut','AMBRE')
        scol  = VR if stat=='VERT' else AR if stat=='AMBRE' else RgR
        semj  = '✅' if stat=='VERT' else '⚠️' if stat=='AMBRE' else '❌'

        imgs = _pngs(graphiques or {})

        # ── Helpers docx ──────────────────────────────────────────────────────
        def bg(cell, hex6):
            tc=cell._tc; tcp=tc.get_or_add_tcPr()
            s=OxmlElement('w:shd')
            s.set(qn('w:fill'),hex6); s.set(qn('w:color'),'auto')
            s.set(qn('w:val'),'clear'); tcp.append(s)

        def run(p, txt, bold=False, italic=False, sz=10, col=None):
            r=p.add_run(str(txt)); r.bold=bold; r.italic=italic; r.font.size=Pt(sz)
            if col: r.font.color.rgb=col
            return r

        def h(txt, lv=1, col=None, sb=8, sa=3):
            p=doc.add_paragraph()
            p.paragraph_format.space_before=Pt(sb)
            p.paragraph_format.space_after=Pt(sa)
            sz={1:16,2:12,3:10}.get(lv,10)
            c=col or (NR if lv==1 else GR)
            run(p,txt,bold=True,sz=sz,col=c)
            return p

        def para(txt, sz=9, col=None, bold=False, italic=False, sa=3, indent=0):
            if not txt: return None
            p=doc.add_paragraph()
            p.paragraph_format.space_after=Pt(sa)
            p.paragraph_format.space_before=Pt(0)
            if indent: p.paragraph_format.left_indent=Cm(indent)
            run(p,_clean(str(txt)),bold=bold,italic=italic,sz=sz,col=col or NR)
            return p

        def sep(col=GOLD):
            p=doc.add_paragraph()
            p.paragraph_format.space_before=Pt(2); p.paragraph_format.space_after=Pt(2)
            pPr=p._p.get_or_add_pPr(); pBdr=OxmlElement('w:pBdr')
            b=OxmlElement('w:bottom')
            b.set(qn('w:val'),'single'); b.set(qn('w:sz'),'6')
            b.set(qn('w:space'),'1'); b.set(qn('w:color'),col)
            pBdr.append(b); pPr.append(pBdr)

        def tbl(heads, rows, ws=None, hbg=NAVY):
            from docx.enum.table import WD_ALIGN_VERTICAL
            t=doc.add_table(rows=1+len(rows), cols=len(heads)); t.style='Table Grid'
            for i,hd in enumerate(heads):
                c=t.rows[0].cells[i]; bg(c,hbg)
                p=c.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                r=p.add_run(str(hd)); r.bold=True; r.font.size=Pt(9); r.font.color.rgb=BR
                c.vertical_alignment=WD_ALIGN_VERTICAL.CENTER
            for ri,row in enumerate(rows):
                for ci,v in enumerate(row):
                    c=t.rows[ri+1].cells[ci]
                    if ri%2==1: bg(c,'EEF2F7')
                    p=c.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                    r=p.add_run(str(v) if v is not None else '—')
                    r.font.size=Pt(9); c.vertical_alignment=WD_ALIGN_VERTICAL.CENTER
            if ws:
                for i,w in enumerate(ws):
                    for row in t.rows: row.cells[i].width=Cm(w)
            doc.add_paragraph().paragraph_format.space_after=Pt(2)

        def img(png, wcm=14.5):
            if not png: return
            try:
                doc.add_picture(io.BytesIO(png), width=Cm(wcm))
                doc.paragraphs[-1].alignment=WD_ALIGN_PARAGRAPH.CENTER
                doc.add_paragraph().paragraph_format.space_after=Pt(4)
            except Exception as e:
                para(f'[Graphique non disponible : {e}]', sz=8, italic=True)

        # =====================================================================
        #  PAGE DE GARDE
        # =====================================================================
        doc.add_paragraph().paragraph_format.space_after=Pt(24)

        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        run(p,'RAPPORT ACTUARIEL\n',bold=True,sz=26,col=NR)
        run(p,'Provisionnement Non-Vie',bold=True,sz=18,col=GR)

        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before=Pt(12)
        run(p,f'{cli}\n',bold=True,sz=14,col=NR)
        run(p,f'Arrêté : {arr}  ·  Branche : {lob}',sz=12,col=rgb(GRIS))

        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before=Pt(8)
        run(p,'Statut : ',sz=11,col=NR)
        run(p,f'{semj} {stat}',bold=True,sz=11,col=scol)

        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before=Pt(6)
        run(p,'CONFIDENTIEL — USAGE STRICTEMENT ACTUARIEL',bold=True,sz=9,col=RgR)

        doc.add_paragraph().paragraph_format.space_after=Pt(8)
        tbl(['Référence client','Branche','Méthode retenue','Date','Audit ID'],
            [[cli, lob, meth.replace('_',' ').title(), dt, audit_id or '—']],
            ws=[3.2,3.0,3.5,2.3,4.0])

        doc.add_page_break()

        # =====================================================================
        #  1. SYNTHÈSE EXÉCUTIVE
        # =====================================================================
        h('1. Synthèse exécutive'); sep()

        tbl(['Indicateur','Valeur','Indicateur','Valeur'],
            [['Best Estimate S2 (Art.77)',_f(BE),'σ Mack total',_f(SIG)],
             ['Provision P75',_f(P75),'CV inter-méthodes',_pct(CV)],
             ['Provision P90',_f(P90),'SCR Provisions',_f(SCP)],
             ['Provision P99.5',_f(P99),'Ratio SCR/BE',_pct(SCR)]],
            ws=[4.5,3.5,4.5,3.5])

        if imgs.get('g5_convergence'):
            h('Convergence des méthodes', lv=2); img(imgs['g5_convergence'])

        doc.add_page_break()

        # =====================================================================
        #  2. RÉSULTATS PAR MÉTHODE
        # =====================================================================
        h('2. Résultats par méthode actuarielle'); sep()

        tbl(['Méthode','Réserve IBNR (€)','Poids BE','Score /100'],
            [['Chain Ladder',
              _f(cl.get('reserve_totale')),
              _pct(pw.get('chain_ladder',0)*100),
              str(n2.get('scores_confiance',{}).get('chain_ladder','—'))],
             ['Mack 1993',
              _f(mk.get('reserve_best_estimate')),
              _pct(pw.get('mack',0)*100),
              str(n2.get('scores_confiance',{}).get('mack','—'))],
             ['Bornhuetter-Ferguson',
              _f(bf.get('reserve_totale')),
              _pct(pw.get('bf',0)*100),
              str(n2.get('scores_confiance',{}).get('bf','—'))],
             ['Cape Cod',
              _f(cc.get('reserve_totale')),
              _pct(pw.get('cape_cod',0)*100),
              str(n2.get('scores_confiance',{}).get('cape_cod','—'))],
             ['⭐ BEST ESTIMATE S2',_f(BE),'100 %','—']],
            ws=[5.0,3.5,2.5,2.5], hbg=NAVY_L)

        # Incertitude Mack
        h('Incertitude de réserve — Mack 1993 & Bootstrap ODP', lv=2)
        tbl(['Approche','BE (€)','P90 (€)','P99.5 (€)','CV (%)'],
            [['Mack 1993 (analytique)',
              _f(BE), _f(P90), _f(P99), _pct(SIG/BE*100 if BE else 0)],
             ['Bootstrap ODP (5 000 sim.)',
              _f(bt.get('reserve_p50',BE)),
              _f(bt.get('reserve_p90',P90)),
              _f(bt.get('reserve_p99_5',P99)),
              _pct(bt.get('cv',CV))]],
            ws=[5.0,3.0,3.0,3.0,2.0])

        # Graphiques résultats
        for gnom, gtit in [
            ('g1_heatmap',    'Triangle de développement cumulé'),
            ('g13_paiements', 'Paiements cumulés par année de survenance'),
            ('g4_ibnr',       'IBNR par année de survenance'),
            ('g2_cadences',   'Cadences cumulées — Chain Ladder'),
            ('g6_bootstrap',  'Distribution Bootstrap ODP — Quantiles'),
        ]:
            if imgs.get(gnom):
                h(gtit, lv=2); img(imgs[gnom])

        doc.add_page_break()

        # =====================================================================
        #  3. VALIDATION DES HYPOTHÈSES
        # =====================================================================
        h('3. Validation des hypothèses actuarielles'); sep()

        # Tableau synthèse
        rows_h = []
        for lbl, hd in [('H1 — Indépendance (Mack)',h1),('H2 — Stabilité facteurs',h2),
                         ('H3 — A priori BF/CC',h3),('H4 — Homoscédasticité ODP',h4)]:
            if not hd: continue
            ok = bool(hd.get('ok',True))
            indic = (f"corr_moy={hd.get('corr_moy','—')}" if 'corr_moy' in hd else
                     f"CV={hd.get('cv_moy','—')}"         if 'cv_moy' in hd else
                     f"LR={hd.get('lr_apriori','—')}"     if 'lr_apriori' in hd else
                     f"φ={hd.get('phi','—')}")
            rows_h.append([lbl, _ok(ok), f"{hd.get('score','—')}/100", indic])
        if rows_h:
            tbl(['Hypothèse','Résultat','Score','Indicateur clé'],
                rows_h, ws=[5.5,2.5,2.0,6.0])

        # Détail narratif de chaque hypothèse
        for lbl, hd in [('H1 — Indépendance (Mack 1993)',h1),
                         ('H2 — Stabilité des facteurs',h2),
                         ('H3 — A priori Bornhuetter-Ferguson',h3),
                         ('H4 — Homoscédasticité Bootstrap ODP',h4)]:
            if not hd: continue
            ok  = bool(hd.get('ok',True))
            msg = _clean(hd.get('message',''))
            if not msg: continue
            h(lbl, lv=2, col=VR if ok else AR)
            para(msg, sz=9, sa=4, indent=0.3)

        # Décision méthodologique
        raison_rec = _clean(n2.get('raison_recommandation',''))
        methode_rec = n2.get('methode_recommandee','—')
        if raison_rec:
            h('Décision méthodologique', lv=2)
            p=doc.add_paragraph(); p.paragraph_format.space_after=Pt(3)
            run(p,'Méthode recommandée : ',bold=True,sz=9,col=NR)
            run(p,methode_rec.replace('_',' ').title(),sz=9,col=GR)
            para(raison_rec, sz=9, indent=0.3)

        # Graphiques hypothèses
        for gnom, gtit in [('g8_h1','H1 — Test indépendance Spearman'),
                            ('g9_h2','H2 — Stabilité des facteurs'),
                            ('g10_h3','H3 — Loss Ratio a priori')]:
            if imgs.get(gnom):
                h(gtit, lv=2); img(imgs[gnom])

        doc.add_page_break()

        # =====================================================================
        #  4. SCR PROVISIONS
        # =====================================================================
        h('4. SCR Provisions — Art. 105 Solvabilité 2'); sep()

        tbl(['Composante','Valeur','Référence réglementaire'],
            [['Best Estimate S2', _f(BE), 'Art. 77 Directive S2'],
             ['Facteur σ EIOPA',  '10 %',  f'LoB : {lob} (Annexe II, Rgt 2015/35)'],
             ['SCR Provisions',   _f(SCP), 'SCR = 3 × σ(LoB) × BE (Art. 105)'],
             ['Ratio SCR/BE',     _pct(SCR),'Cible marché < 35 %']],
            ws=[4.5,3.5,8.0])

        scr_msg = _clean(sc.get('message','') if sc else '')
        if scr_msg: para(scr_msg, sz=9, sa=4)

        if imgs.get('g7_scr'):
            h('Décomposition SCR', lv=2); img(imgs['g7_scr'])

        doc.add_page_break()

        # =====================================================================
        #  5. COMMENTAIRE ACTUARIEL COMPLET
        # =====================================================================
        h('5. Commentaire actuariel complet'); sep()

        if commentaire:
            comm = _clean(commentaire)
            # Supprimer le header répété (RAPPORT DE PROVISIONNEMENT...)
            comm = re.sub(
                r'={4,}.*?AGENT A7 IBRAHIM.*?={4,}',
                '', comm, flags=re.DOTALL
            ).strip()
            # Découper par sections §
            sections_c = re.split(r'(?=§\d+\s*—|\d+\.\s+[A-ZÀÂÉÈÊ])', comm)
            for sec in sections_c:
                sec = sec.strip()
                if not sec: continue
                lignes = sec.split('\n', 1)
                tit_c  = lignes[0].strip()
                corps_c = lignes[1].strip() if len(lignes) > 1 else ''
                if tit_c: h(tit_c, lv=2)
                if corps_c:
                    for ln in corps_c.split('\n'):
                        ln = ln.strip()
                        if ln:
                            p = doc.add_paragraph()
                            p.paragraph_format.space_after  = Pt(2)
                            p.paragraph_format.left_indent  = Cm(0.3)
                            # Bullet points
                            if ln.startswith('•') or ln.startswith('-'):
                                run(p, ln, sz=9, col=NR)
                            else:
                                run(p, ln, sz=9, col=NR)
        else:
            para('Commentaire non disponible.', sz=9, italic=True)

        doc.add_page_break()

        # =====================================================================
        #  6. JUGEMENT ACTUARIEL & RECOMMANDATIONS
        # =====================================================================
        h('6. Jugement actuariel & Recommandations'); sep()

        # Jugement structuré depuis n4
        jugement = _clean(n4.get('jugement',''))
        if jugement:
            sections_j = re.split(r'(?=\d+\.\s+[A-ZÀÂÉÈÊ])', jugement)
            for sec in sections_j:
                sec = sec.strip()
                if not sec: continue
                lignes = sec.split('\n',1)
                tit_j  = lignes[0].strip()
                corps_j = lignes[1].strip() if len(lignes)>1 else ''
                if tit_j: h(tit_j, lv=2)
                if corps_j:
                    for ln in corps_j.split('\n'):
                        ln = ln.strip()
                        if ln: para(ln, sz=9, sa=2, indent=0.3)

        # Alertes spécifiques
        alertes = n4.get('alertes', n2.get('alertes',[]))
        if alertes:
            h('Points de vigilance', lv=2)
            for a in alertes:
                at = _clean(str(a))
                if not at: continue
                p=doc.add_paragraph()
                p.paragraph_format.space_after=Pt(3)
                p.paragraph_format.left_indent=Cm(0.4)
                run(p,'⚠️  ',sz=10,col=AR)
                run(p,at,sz=9,col=NR)

        # Recommandations
        recs = n4.get('recommandations',[])
        if recs:
            h('Actions recommandées', lv=2)
            for i,rec in enumerate(recs,1):
                r=_clean(str(rec))
                if not r: continue
                p=doc.add_paragraph()
                p.paragraph_format.space_after=Pt(3)
                p.paragraph_format.left_indent=Cm(0.4)
                run(p,f'{i}.  ',bold=True,sz=10,col=GR)
                run(p,r,sz=9,col=NR)

        # Avis final
        avis = _clean(n4.get('avis_actuariel',''))
        if avis:
            h('Avis actuariel', lv=2)
            p=doc.add_paragraph()
            p.paragraph_format.space_after=Pt(4)
            p.paragraph_format.left_indent=Cm(0.3)
            col_avis = RgR if 'DÉFAVORABLE' in avis.upper() else VR
            run(p,avis,sz=9,col=col_avis)

        # ── Pied de page ──────────────────────────────────────────────────────
        sep(NAVY)
        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        run(p,
            f'ActuarIA · {cli} · Arrêté {arr} · Audit ID : {audit_id or "—"} · '
            f'{dt} · CONFIDENTIEL',
            sz=7, col=GrR, italic=True)

        buf=io.BytesIO(); doc.save(buf); buf.seek(0)
        wb=buf.read()
        logger.info(f"Word : {len(wb):,} bytes | {len(imgs)} graphiques")
        return wb

    except Exception as e:
        logger.error(f"export_word : {e}", exc_info=True); return b''


# =============================================================================
#  EXPORT PDF  (reportlab) — même structure 5 sections
# =============================================================================

def export_pdf(
    n1=None, n2=None, n3=None, n4=None,
    commentaire='', ref_client='', arrete='',
    audit_id='', lob_label='', graphiques=None, **kw,
) -> bytes:
    n1=n1 or {}; n2=n2 or {}; n3=n3 or {}; n4=n4 or {}
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, PageBreak, HRFlowable)
        from reportlab.platypus import Image as RLImage
    except ImportError as e:
        logger.error(f"reportlab absent : {e}"); return b''

    try:
        cl=n3.get('chain_ladder',{}); mk=n3.get('mack',{})
        bf=n3.get('bf',{});           cc=n3.get('cape_cod',{})
        bt=n3.get('bootstrap',{});    sc=n4.get('scr',{})
        h1=n2.get('h1_independance',{}); h2=n2.get('h2_stabilite',{})
        h3=n2.get('h3_apriori_bf',{});   h4=n2.get('h4_homosc_bootstrap',{})
        pw=n4.get('poids',{})

        BE  = float(n4.get('best_estimate',0) or 0)
        SIG = float(mk.get('sigma_total',n4.get('sigma_mack',0)) or 0)
        CV  = float(n4.get('cv_inter_methodes',0) or 0)
        P75 = float(n4.get('reserve_p75',0) or 0)
        P90 = float(n4.get('reserve_p90',0) or 0)
        P99 = float(n4.get('reserve_p99_5',0) or 0)
        SCP = float(sc.get('scr_prov',BE*0.30) if sc else BE*0.30)
        SCR = SCP/BE*100 if BE else 0

        dt=datetime.now().strftime('%d/%m/%Y')
        arr=arrete or dt; cli=ref_client or 'ActuarIA'
        lob=lob_label or n2.get('lob_label','—')
        meth=n4.get('methode_facteurs',n2.get('methode_recommandee','—'))

        NRL=colors.HexColor(f'#{NAVY}'); GRL=colors.HexColor(f'#{GOLD}')
        GrRL=colors.HexColor(f'#{GRIS}'); RgRL=colors.HexColor(f'#{ROUGE}')
        VRL=colors.HexColor(f'#{VERT}'); ARL=colors.HexColor(f'#{AMBRE}')
        WRL=colors.white; LgRL=colors.HexColor('#EEF2F7')

        buf=io.BytesIO()
        doc=SimpleDocTemplate(buf, pagesize=A4,
            topMargin=2*cm, bottomMargin=2*cm,
            leftMargin=2.5*cm, rightMargin=2.5*cm,
            title=f"Rapport Actuariel {arr}", author="ActuarIA")

        def S(n,**kw): return ParagraphStyle(n,**kw)
        st={
            'T': S('T',fontSize=22,fontName='Helvetica-Bold',textColor=NRL,alignment=1,spaceAfter=6),
            'S': S('S',fontSize=13,fontName='Helvetica',textColor=GRL,alignment=1,spaceAfter=4),
            'C': S('C',fontSize=9,fontName='Helvetica-Bold',textColor=RgRL,alignment=1,spaceAfter=10),
            'H1':S('H1',fontSize=14,fontName='Helvetica-Bold',textColor=NRL,spaceBefore=10,spaceAfter=3),
            'H2':S('H2',fontSize=11,fontName='Helvetica-Bold',textColor=GRL,spaceBefore=6,spaceAfter=2),
            'H3':S('H3',fontSize=10,fontName='Helvetica-Bold',textColor=NRL,spaceBefore=3,spaceAfter=2),
            'B': S('B',fontSize=9,fontName='Helvetica',textColor=colors.black,spaceAfter=3,leading=13),
            'F': S('F',fontSize=7,fontName='Helvetica',textColor=GrRL,alignment=1),
        }

        def T(heads, rows, cw=None, hbg=None):
            hbg=hbg or NRL
            th=ParagraphStyle('th',fontSize=9,fontName='Helvetica-Bold',textColor=WRL,alignment=1)
            td=ParagraphStyle('td',fontSize=9,fontName='Helvetica',alignment=1)
            data=[[Paragraph(f'<b>{x}</b>',th) for x in heads]]
            for row in rows:
                data.append([Paragraph(str(v or '—'),td) for v in row])
            t=Table(data,colWidths=cw,repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),hbg),('TEXTCOLOR',(0,0),(-1,0),WRL),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#D0D8E4')),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[WRL,LgRL]),
                ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
            ]))
            return t

        imgs=_pngs(graphiques or {})
        HR=lambda: HRFlowable(width='100%',thickness=1.5,color=GRL,spaceAfter=6)

        def IM(nom, w=15*cm, hh=5.5*cm):
            if not imgs.get(nom): return []
            return [Spacer(1,0.2*cm), RLImage(io.BytesIO(imgs[nom]),width=w,height=hh), Spacer(1,0.2*cm)]

        story=[]

        # Page de garde
        story+=[Spacer(1,2*cm),
                Paragraph('RAPPORT ACTUARIEL<br/>Provisionnement Non-Vie',st['T']),
                Spacer(1,0.4*cm),
                Paragraph(f'{cli}<br/><font size="11">Arrêté : {arr}  ·  Branche : {lob}</font>',st['S']),
                Spacer(1,0.2*cm),
                Paragraph('CONFIDENTIEL — USAGE STRICTEMENT ACTUARIEL',st['C']),
                Spacer(1,0.6*cm),
                T(['Référence','Méthode','Date','Audit ID'],
                  [[cli,meth.replace('_',' ').title(),dt,audit_id or '—']],
                  cw=[4*cm,5*cm,3*cm,4*cm]),
                PageBreak()]

        # 1. Synthèse
        story+=[Paragraph('1. Synthèse exécutive',st['H1']),HR(),
                T(['Indicateur','Valeur','Indicateur','Valeur'],
                  [['Best Estimate S2',_f(BE),'σ Mack total',_f(SIG)],
                   ['Provision P75',_f(P75),'CV inter-méthodes',_pct(CV)],
                   ['Provision P90',_f(P90),'SCR Provisions',_f(SCP)],
                   ['Provision P99.5',_f(P99),'Ratio SCR/BE',_pct(SCR)]],
                  cw=[4*cm,4*cm,4*cm,4*cm])]
        story+=IM('g5_convergence'); story.append(PageBreak())

        # 2. Résultats
        story+=[Paragraph('2. Résultats par méthode',st['H1']),HR(),
                T(['Méthode','Réserve (€)','Poids','Score'],
                  [['Chain Ladder',_f(cl.get('reserve_totale')),
                    _pct(pw.get('chain_ladder',0)*100),
                    str(n2.get('scores_confiance',{}).get('chain_ladder','—'))],
                   ['Mack 1993',_f(mk.get('reserve_best_estimate')),
                    _pct(pw.get('mack',0)*100),
                    str(n2.get('scores_confiance',{}).get('mack','—'))],
                   ['Bornhuetter-Ferguson',_f(bf.get('reserve_totale')),
                    _pct(pw.get('bf',0)*100),
                    str(n2.get('scores_confiance',{}).get('bf','—'))],
                   ['Cape Cod',_f(cc.get('reserve_totale')),
                    _pct(pw.get('cape_cod',0)*100),
                    str(n2.get('scores_confiance',{}).get('cape_cod','—'))],
                   ['⭐ BEST ESTIMATE S2',_f(BE),'100 %','—']],
                  cw=[5*cm,4*cm,3*cm,4*cm],
                  hbg=colors.HexColor(f'#{NAVY_L}'))]
        for gn,gt in [('g1_heatmap','Triangle'),('g13_paiements','Paiements cumulés'),
                       ('g4_ibnr','IBNR par année'),('g6_bootstrap','Bootstrap ODP')]:
            if imgs.get(gn):
                story+=[Paragraph(gt,st['H2'])]+IM(gn)
        story.append(PageBreak())

        # 3. Hypothèses
        rows_h=[]
        for lbl,hd in [('H1 — Indépendance',h1),('H2 — Stabilité',h2),
                        ('H3 — A priori BF',h3),('H4 — Homoscédasticité',h4)]:
            if not hd: continue
            ok=bool(hd.get('ok',True))
            rows_h.append([lbl,_ok(ok),f"{hd.get('score','—')}/100",
                           _clean(hd.get('message',''))[:70]])
        story+=[Paragraph('3. Validation des hypothèses',st['H1']),HR()]
        if rows_h:
            story.append(T(['Hypothèse','Résultat','Score','Message'],rows_h,
                           cw=[4*cm,2.5*cm,2*cm,7.5*cm]))
        for gn,gt in [('g8_h1','H1 — Indépendance'),('g9_h2','H2 — Stabilité')]:
            if imgs.get(gn):
                story+=[Paragraph(gt,st['H2'])]+IM(gn,hh=4.5*cm)
        story.append(PageBreak())

        # 4. SCR
        story+=[Paragraph('4. SCR Provisions — Art. 105 S2',st['H1']),HR(),
                T(['Composante','Valeur','Référence'],
                  [['Best Estimate S2',_f(BE),'Art. 77'],
                   ['Facteur σ EIOPA','10 %',f'LoB : {lob}'],
                   ['SCR Provisions',_f(SCP),'3 × σ × BE'],
                   ['Ratio SCR/BE',_pct(SCR),'< 35 %']],
                  cw=[5*cm,4*cm,7*cm]),
                PageBreak()]

        # 5. Jugement & Recommandations
        story+=[Paragraph('5. Jugement actuariel & Recommandations',st['H1']),HR()]
        jug=_clean(n4.get('jugement',''))
        if jug:
            for sec in re.split(r'(?=\d+\.\s+[A-ZÀÂÉÈÊ])',jug):
                sec=sec.strip()
                if not sec: continue
                ls=sec.split('\n',1)
                if ls[0]: story.append(Paragraph(ls[0],st['H2']))
                if len(ls)>1:
                    for ln in ls[1].split('\n'):
                        ln=ln.strip()
                        if ln: story.append(Paragraph(ln,st['B']))

        # Footer
        story+=[Spacer(1,0.5*cm),
                HRFlowable(width='100%',thickness=0.5,
                           color=colors.HexColor(f'#{GRIS}'),spaceAfter=3),
                Paragraph(f'ActuarIA · {cli} · Arrêté {arr} · '
                          f'Audit ID : {audit_id or "—"} · {dt} · CONFIDENTIEL',
                          st['F'])]

        doc.build(story)
        buf.seek(0); pb=buf.read()
        logger.info(f"PDF : {len(pb):,} bytes")
        return pb

    except Exception as e:
        logger.error(f"export_pdf : {e}", exc_info=True); return b''
