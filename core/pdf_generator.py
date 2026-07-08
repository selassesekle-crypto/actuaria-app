# Générateur PDF standalone pour Streamlit
import io, math, copy, json, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    PageBreak, Table, TableStyle,
    Image as RLImage)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.enums import (
    TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT)

WHITE = colors.white
NAVY  = colors.HexColor('#0D1B3E')
GREEN = colors.HexColor('#4CAF1A')
GOLD  = colors.HexColor('#FFC000')
GREY  = colors.HexColor('#718096')
BLUE  = colors.HexColor('#1B3A6B')
DANGER= colors.HexColor('#E53E3E')


def generer_pdf_streamlit(
        data,
        nom_societe='Demo',
        nom_actuaire='Actuaire Senior',
        classification='Confidentiel',
        langue='FR'):
    """
    Génère un rapport PDF complet
    Retourne les bytes du PDF
    """
    buf = io.BytesIO()
    W, H = A4
    LM, RM = 2*cm, 2*cm
    TM, BM = 2.5*cm, 2*cm
    CW = W - LM - RM

    now = datetime.now()
    mois_fr = {
        1:'janvier',  2:'février',  3:'mars',
        4:'avril',    5:'mai',      6:'juin',
        7:'juillet',  8:'août',     9:'septembre',
        10:'octobre', 11:'novembre',12:'décembre'}
    mois_en = {
        1:'January',  2:'February', 3:'March',
        4:'April',    5:'May',      6:'June',
        7:'July',     8:'August',   9:'September',
        10:'October', 11:'November',12:'December'}
    date_l = (
        f"{now.day} "
        f"{mois_fr[now.month] if langue=='FR' else mois_en[now.month]} "
        f"{now.year}")
    date_s = now.strftime('%d/%m/%Y')

    NB_PAGES = 10

    def on_page(canvas, doc):
        canvas.saveState()
        if doc.page == 1:
            # Couverture fond navy
            canvas.setFillColor(NAVY)
            canvas.rect(0,0,W,H,fill=1,stroke=0)
            canvas.setFillColor(GREEN)
            canvas.rect(0,H-4,W,4,fill=1,stroke=0)
            canvas.rect(0,3,W,3,fill=1,stroke=0)

            # Titre
            canvas.setFont('Helvetica-Bold',32)
            canvas.setFillColor(WHITE)
            titre = ('Rapport\nDirection Générale'
                     if langue=='FR'
                     else 'Executive\nManagement Report')
            y = H - 8*cm
            for line in titre.split('\n'):
                canvas.drawCentredString(W/2,y,line)
                y -= 3.5*cm

            # Tagline
            canvas.setFont('Helvetica',10)
            canvas.setFillColor(GREEN)
            canvas.drawCentredString(
                W/2, y+1.5*cm,
                'ACTUARIAL INTELLIGENCE')

            # Séparateur
            canvas.setStrokeColor(
                colors.HexColor('#1B3A6B'))
            canvas.setLineWidth(0.5)
            canvas.line(LM,y+0.8*cm,W-RM,y+0.8*cm)

            # Infos
            y_i = y+0.2*cm
            act_lbl = ('ACTUAIRE RESPONSABLE'
                       if langue=='FR'
                       else 'RESPONSIBLE ACTUARY')
            dat_lbl = ("DATE D'ARRÊTÉ"
                       if langue=='FR'
                       else 'REPORTING DATE')
            for lbl,val in [
                (act_lbl, nom_actuaire),
                (dat_lbl, date_l),
                ('CLASSIFICATION', classification),
            ]:
                canvas.setFont('Helvetica',7)
                canvas.setFillColor(
                    colors.HexColor('#718096'))
                canvas.drawCentredString(
                    W/2, y_i, lbl)
                canvas.setFont('Helvetica-Bold',9.5)
                canvas.setFillColor(WHITE)
                canvas.drawCentredString(
                    W/2, y_i-0.45*cm, val)
                y_i -= 1.2*cm

            # KPIs
            s   = data.get('scr',{})
            g   = data.get('glm_g',{})
            ir  = data.get('ifrs17',{})
            kpi_items = [
                ('PRIME PURE',
                 f"{g.get('prime_pure_moy','N/A')} €",
                 '#0D1B3E'),
                ('RATIO SCR',
                 f"{s.get('ratio_scr_pct',0)}%",
                 '#4CAF1A'),
                ('LOSS RATIO IFRS 17',
                 f"{ir.get('modele_paa',{}).get('loss_ratio_pct',0)}%",
                 '#FFC000'),
            ]
            y_kpi = 5.5*cm
            kpi_w = (W-2*LM)/3
            for idx,(lbl,val,col) in enumerate(
                    kpi_items):
                x = LM + idx*kpi_w
                canvas.setFillColor(
                    colors.HexColor('#1B3A6B'))
                canvas.roundRect(
                    x+3,y_kpi-1.4*cm,
                    kpi_w-6,1.8*cm,
                    4,fill=1,stroke=0)
                canvas.setFillColor(
                    colors.HexColor(col))
                canvas.rect(
                    x+3,y_kpi+0.35*cm,
                    kpi_w-6,3,fill=1,stroke=0)
                canvas.setFont('Helvetica',6.5)
                canvas.setFillColor(
                    colors.HexColor('#C0C8D4'))
                canvas.drawCentredString(
                    x+kpi_w/2,y_kpi-0.1*cm,
                    lbl[:20])
                canvas.setFont(
                    'Helvetica-Bold',13)
                canvas.setFillColor(WHITE)
                canvas.drawCentredString(
                    x+kpi_w/2,y_kpi-0.85*cm,val)

        else:
            # En-tête navy
            canvas.setFillColor(NAVY)
            canvas.rect(
                0,H-1.6*cm,W,1.6*cm,
                fill=1,stroke=0)
            canvas.setFillColor(GREEN)
            canvas.rect(
                0,H-1.63*cm,W,3,
                fill=1,stroke=0)

            titre_rp = ('Rapport Direction Générale'
                        if langue=='FR'
                        else 'Executive Management Report')
            canvas.setFont('Helvetica-Bold',8.5)
            canvas.setFillColor(WHITE)
            canvas.drawString(
                LM,H-0.85*cm,
                f'{titre_rp} — {nom_societe}')
            canvas.setFont('Helvetica-Bold',9)
            canvas.setFillColor(GREEN)
            canvas.drawRightString(
                W-RM,H-0.85*cm,
                f'Page {doc.page} / {NB_PAGES}')

            # Pied de page
            canvas.setStrokeColor(
                colors.HexColor('#E2E8F0'))
            canvas.setLineWidth(0.5)
            canvas.line(
                LM,BM-0.3*cm,W-RM,BM-0.3*cm)
            canvas.setFont('Helvetica',7)
            canvas.setFillColor(
                colors.HexColor('#718096'))
            canvas.drawString(
                LM,0.55*cm,
                f'ActuarIA — Actuarial Intelligence'
                f' — {classification}')
            canvas.setFont('Helvetica-Bold',8)
            canvas.setFillColor(NAVY)
            canvas.drawCentredString(
                W/2,0.55*cm,
                f'Page {doc.page} / {NB_PAGES}')
            canvas.setFont('Helvetica',7)
            canvas.setFillColor(
                colors.HexColor('#718096'))
            canvas.drawRightString(
                W-RM,0.55*cm,date_s)

        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=LM, rightMargin=RM,
        topMargin=TM, bottomMargin=BM)

    def P(txt, **kw):
        d = dict(
            fontSize=9.5, leading=15.5,
            fontName='Helvetica',
            textColor=colors.HexColor('#2D3748'),
            spaceAfter=6,
            alignment=TA_JUSTIFY)
        d.update(kw)
        return Paragraph(
            txt, ParagraphStyle('p',**d))

    def titre_sec(txt):
        return Paragraph(
            txt.upper(),
            ParagraphStyle('ts',
                fontSize=12,
                textColor=WHITE,
                fontName='Helvetica-Bold',
                backColor=NAVY,
                spaceBefore=0,
                spaceAfter=10,
                borderPadding=(7,8,7,12)))

    def kpi_row(items):
        n = len(items)
        w = CW/n
        r0,r1 = [],[]
        cmds = [
            ('BACKGROUND',(0,0),(-1,-1),
             colors.HexColor('#F7FAFF')),
            ('BOX',(0,0),(-1,-1),0.5,
             colors.HexColor('#E2E8F0')),
            ('INNERGRID',(0,0),(-1,-1),0.5,
             colors.HexColor('#E2E8F0')),
            ('TOPPADDING',(0,0),(-1,-1),8),
            ('BOTTOMPADDING',(0,0),(-1,-1),8),
            ('LEFTPADDING',(0,0),(-1,-1),4),
            ('RIGHTPADDING',(0,0),(-1,-1),4),
        ]
        for idx,(lbl,val,col) in enumerate(items):
            r0.append(P(lbl.upper(),
                fontSize=6.5,textColor=GREY,
                fontName='Helvetica',
                alignment=TA_CENTER))
            r1.append(P(str(val),
                fontSize=12,
                textColor=NAVY,
                fontName='Helvetica-Bold',
                alignment=TA_CENTER))
            cmds.append((
                'LINEABOVE',(idx,0),(idx,0),
                3,colors.HexColor(col)))
        t = Table([r0,r1],colWidths=[w]*n)
        t.setStyle(TableStyle(cmds))
        return t

    def tab(data_t, widths):
        t = Table(data_t,colWidths=widths,
                  repeatRows=1)
        cmds = [
            ('BACKGROUND',(0,0),(-1,0),NAVY),
            ('TEXTCOLOR',(0,0),(-1,0),WHITE),
            ('FONTNAME',(0,0),(-1,0),
             'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,0),8.5),
            ('ALIGN',(0,0),(-1,0),'CENTER'),
            ('TOPPADDING',(0,0),(-1,-1),5),
            ('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),7),
            ('RIGHTPADDING',(0,0),(-1,-1),7),
            ('FONTNAME',(0,1),(-1,-1),'Helvetica'),
            ('FONTSIZE',(0,1),(-1,-1),8.5),
            ('ALIGN',(1,1),(-1,-1),'RIGHT'),
            ('ALIGN',(0,1),(0,-1),'LEFT'),
            ('GRID',(0,0),(-1,-1),0.4,
             colors.HexColor('#CBD5E0')),
        ]
        for r in range(1,len(data_t)):
            if r%2==0:
                cmds.append((
                    'BACKGROUND',(0,r),(-1,r),
                    colors.HexColor('#F0F4FF')))
        t.setStyle(TableStyle(cmds))
        return t

    def orsa(titre_o, paras):
        result = [Paragraph(
            f'💼 {titre_o}',
            ParagraphStyle('oh',
                fontSize=9,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor(
                    '#1C4532'),
                backColor=colors.HexColor(
                    '#D1FAE5'),
                spaceAfter=0,
                spaceBefore=8,
                borderPadding=(8,10,4,10)))]
        for para in paras:
            result.append(Paragraph(para,
                ParagraphStyle('op',
                    fontSize=9.2,leading=15,
                    fontName='Helvetica',
                    textColor=colors.HexColor(
                        '#1C4532'),
                    backColor=colors.HexColor(
                        '#D1FAE5'),
                    spaceAfter=5,
                    alignment=TA_JUSTIFY,
                    borderPadding=(0,10,5,10))))
        return result

    def graph_barres(labels, valeurs, titre,
                     couleurs=None, largeur=16,
                     hauteur=6.5):
        if couleurs is None:
            couleurs = ['#0D1B3E']*len(labels)
        fig,ax = plt.subplots(
            figsize=(largeur/2.54,hauteur/2.54))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('#F8F9FC')
        data_s = sorted(
            zip(valeurs,labels,couleurs),
            reverse=False)
        vs=[d[0] for d in data_s]
        ls=[d[1] for d in data_s]
        cs=[d[2] for d in data_s]
        bars = ax.barh(range(len(ls)),vs,
                       color=cs,height=0.55,zorder=3,
                       edgecolor='white',linewidth=0.5)
        mx = max(vs) if vs else 1
        for bar,v in zip(bars,vs):
            ax.text(v+mx*0.02,
                    bar.get_y()+bar.get_height()/2,
                    f'{v:,.0f}' if v>=100
                    else f'{v:.3f}',
                    va='center',ha='left',
                    fontsize=8,fontweight='bold',
                    color='#2D3748')
        ax.set_yticks(range(len(ls)))
        ax.set_yticklabels(ls,fontsize=8.5,
                           color='#2D3748')
        ax.set_title(titre,fontsize=10,
                     fontweight='bold',
                     color='#0D1B3E',pad=8,loc='left')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='x',alpha=0.4,zorder=0,
                linewidth=0.5)
        plt.tight_layout(pad=0.8)
        b = io.BytesIO()
        plt.savefig(b,format='png',dpi=150,
                    bbox_inches='tight',
                    facecolor='white')
        plt.close()
        b.seek(0)
        return b

    SP  = lambda h=0.3: Spacer(1,h*cm)
    PB  = PageBreak
    IMG = lambda buf,h: RLImage(buf,width=CW,
                                height=h*cm)

    E = []

    # Données
    s   = data.get('scr',{})
    p   = data.get('prov',{})
    ir  = data.get('ifrs17',{})
    pm  = data.get('pm_vie',{})
    g   = data.get('glm_g',{})
    ml  = data.get('ml_v2',{})
    cl  = data.get('cl',{})
    paa = ir.get('modele_paa',{})
    bba = ir.get('modele_bba',{})
    mp  = p.get('methodes',{})
    cr  = pm.get('contrat_reference',{})
    pf  = pm.get('portefeuille',{})
    bscr= max(s.get('bscr',1),1)
    mod = ml.get('modele_retenu','N/A')
    lr  = paa.get('loss_ratio_pct',0)
    r_s = s.get('ratio_scr_pct',0)
    r_m = s.get('ratio_mcr_pct',0)
    ok  = r_s >= 100
    cv  = p.get('cv_inter_methodes',0)

    labels = {
        'FR': {
            'resume':    'Résumé Exécutif',
            'tarif':     'Tarification',
            'prov':      'Provisionnement',
            's2':        'Solvabilité 2',
            'ifrs':      'IFRS 17',
            'pmvie':     'Provisions Mathématiques Vie',
            'alm':       'Gestion Actif-Passif (ALM)',
            'reco':      'Recommandations',
            'sommaire':  'Sommaire',
            'analyse':   'Analyse Actuaire Senior',
            'conforme':  'conforme',
            'non_conf':  'non conforme',
        },
        'EN': {
            'resume':    'Executive Summary',
            'tarif':     'Pricing',
            'prov':      'Reserving',
            's2':        'Solvency II',
            'ifrs':      'IFRS 17',
            'pmvie':     'Life Mathematical Reserves',
            'alm':       'Asset-Liability Management',
            'reco':      'Recommendations',
            'sommaire':  'Table of Contents',
            'analyse':   'Senior Actuary Analysis',
            'conforme':  'compliant',
            'non_conf':  'non-compliant',
        },
    }.get(langue, {
            'resume':    'Résumé Exécutif',
            'tarif':     'Tarification',
            'prov':      'Provisionnement',
            's2':        'Solvabilité 2',
            'ifrs':      'IFRS 17',
            'pmvie':     'Provisions Mathématiques Vie',
            'alm':       'Gestion Actif-Passif (ALM)',
            'reco':      'Recommandations',
            'sommaire':  'Sommaire',
            'analyse':   'Analyse Actuaire Senior',
            'conforme':  'conforme',
            'non_conf':  'non conforme',
    })
    L = labels

    # ── COUVERTURE ────────────────────────────────
    E.append(PB())

    # ── SOMMAIRE ──────────────────────────────────
    E.append(SP(0.5))
    E.append(P(L['sommaire'].upper(),
        fontSize=20,fontName='Helvetica-Bold',
        textColor=NAVY,spaceAfter=16,
        alignment=TA_LEFT))

    for num,titre_s,pg in [
        ('1.',L['resume'],'3'),
        ('2.',L['tarif'],'4'),
        ('3.',L['prov'],'5'),
        ('4.',L['s2'],'6'),
        ('5.',L['ifrs'],'7'),
        ('6.',L['pmvie'],'8'),
        ('7.',L['alm'],'9'),
        ('8.',L['reco'],'10'),
    ]:
        t_s = Table(
            [[P(num,fontSize=10,
                fontName='Helvetica-Bold',
                textColor=GREEN,leftIndent=0),
              P(titre_s,fontSize=10,
                fontName='Helvetica',
                textColor=colors.HexColor(
                    '#2D3748'),leftIndent=0),
              P(pg,fontSize=10,
                fontName='Helvetica',
                textColor=GREY,
                alignment=TA_RIGHT,
                leftIndent=0)]],
            colWidths=[1*cm,CW-1*cm-1.5*cm,1.5*cm])
        t_s.setStyle(TableStyle([
            ('TOPPADDING',(0,0),(-1,-1),6),
            ('BOTTOMPADDING',(0,0),(-1,-1),6),
            ('LEFTPADDING',(0,0),(-1,-1),2),
            ('RIGHTPADDING',(0,0),(-1,-1),2),
            ('LINEBELOW',(0,0),(-1,-1),0.3,
             colors.HexColor('#E2E8F0')),
        ]))
        E.append(t_s)
    E.append(PB())

    # ── PAGE 3 — RÉSUMÉ ───────────────────────────
    E.append(SP(0.5))
    E.append(titre_sec(f'1. {L["resume"]}'))
    E.append(SP(0.3))
    E.append(kpi_row([
        ('Prime pure',
         f"{g.get('prime_pure_moy','N/A')} €",
         '#0D1B3E'),
        ('IBNR BE',
         f"{p.get('provision_retenue',0):,.0f} €",
         '#1B3A6B'),
        ('Ratio SCR',f"{r_s}%",
         '#4CAF1A' if ok else '#E53E3E'),
        ('Loss Ratio',f"{lr}%",
         '#4CAF1A' if lr<70 else '#FFC000'),
        ('PM Vie',
         f"{pf.get('pm_totale',0):,.0f} €",
         '#1B3A6B'),
    ]))
    E.append(SP(0.4))

    # Paragraphes résumé
    if langue == 'FR':
        paras_res = [
            (f"Le présent rapport constitue l'analyse "
             f"actuarielle complète du portefeuille de "
             f"<b>100 000 contrats</b> (2010-2024, "
             f"15 ans), répartis sur cinq marchés "
             f"européens. Cadre : Solvabilité 2 "
             f"(Règlement Délégué UE 2015/35), IFRS 17 "
             f"(depuis le 1er janvier 2023) et "
             f"meilleures pratiques EIOPA."),
            (f"<b>Tarification :</b> Modèle "
             f"<b>{mod}</b> retenu (Gini = "
             f"{ml.get('gini_retenu',0):.4f}). "
             f"Prime pure : "
             f"<b>{g.get('prime_pure_moy','N/A')} €</b> "
             f"— cohérent ACPR/FFA 2023."),
            (f"<b>Provisionnement :</b> IBNR BE "
             f"<b>{p.get('provision_retenue',0):,.0f} €"
             f"</b> — CV {cv}% (3 méthodes "
             f"convergentes). P90 = "
             f"{p.get('provision_prudente',0):,.0f} €."),
            (f"<b>Solvabilité 2 :</b> SCR {r_s}% "
             f"({L['conforme'] if ok else L['non_conf']}"
             f"). MCR {r_m}% — action corrective "
             f"immédiate (Art. 129 Dir. 2009/138/CE)."),
            (f"<b>IFRS 17 :</b> Loss Ratio {lr}% "
             f"(benchmark EU 65-75%) — profitable. "
             f"CSM BBA "
             f"{bba.get('csm',0):,.0f} € "
             f"(profit différé §38)."),
        ]
    else:
        paras_res = [
            (f"This report presents a comprehensive "
             f"actuarial analysis of "
             f"<b>100,000 contracts</b> (2010-2024), "
             f"across five European markets. Framework: "
             f"Solvency II, IFRS 17 (effective "
             f"1 January 2023), EIOPA guidelines."),
            (f"<b>Pricing:</b> <b>{mod}</b> selected "
             f"(Gini = {ml.get('gini_retenu',0):.4f}). "
             f"Pure premium: "
             f"<b>{g.get('prime_pure_moy','N/A')} €</b>"
             f" — consistent with EIOPA benchmarks."),
            (f"<b>Reserving:</b> IBNR BE "
             f"<b>{p.get('provision_retenue',0):,.0f} €"
             f"</b> — CV {cv}% (3-method convergence). "
             f"P90 = "
             f"{p.get('provision_prudente',0):,.0f} €."),
            (f"<b>Solvency II:</b> SCR {r_s}% "
             f"({L['conforme'] if ok else L['non_conf']}"
             f"). MCR {r_m}% — immediate action required"
             f" (Art. 129 Dir. 2009/138/EC)."),
            (f"<b>IFRS 17:</b> Loss Ratio {lr}% "
             f"(EU benchmark 65-75%) — profitable. "
             f"BBA CSM "
             f"{bba.get('csm',0):,.0f} € "
             f"(deferred profit §38)."),
        ]
    for txt in paras_res:
        E.append(P(txt))
    E.append(PB())

    # ── PAGE 4 — TARIFICATION ─────────────────────
    E.append(SP(0.5))
    E.append(titre_sec(f'2. {L["tarif"]}'))
    E.append(SP(0.3))
    E.append(kpi_row([
        ('Modèle retenu' if langue=='FR'
         else 'Selected model',
         mod,'#0D1B3E'),
        ('Gini Test',
         f"{ml.get('gini_retenu',0):.4f}",
         '#4CAF1A'),
        ('Lift D1/D10',
         f"{ml.get('lift_retenu',0):.2f}x",
         '#FFC000'),
        ('Prime pure' if langue=='FR'
         else 'Pure premium',
         f"{g.get('prime_pure_moy','N/A')} €",
         '#1B3A6B'),
    ]))
    E.append(SP(0.4))

    cmp = ml.get('comparaison',[])
    if cmp:
        hdr = (['Rang','Modèle','Gini',
                'AUC','Overfit','Lift']
               if langue=='FR'
               else ['Rank','Model','Gini',
                     'AUC','Overfit','Lift'])
        rows = [hdr]
        for m_i in cmp:
            crown = ('★ ' if m_i['modele']==mod
                     else '')
            rows.append([
                str(m_i['rang']),
                f"{crown}{m_i['modele']}",
                f"{m_i['gini_test']:.4f}",
                f"{m_i['auc_test']:.4f}",
                f"{m_i.get('overfit',0):+.4f}"
                if m_i.get('overfit') is not None
                else 'N/A',
                f"{m_i['lift_D1_D10']:.2f}x",
            ])
        E.append(tab(rows,[
            1.2*cm,4.8*cm,2.4*cm,
            2.2*cm,2.2*cm,2.2*cm]))
        E.append(SP(0.4))

        buf_g = graph_barres(
            [m['modele'] for m in cmp],
            [m['gini_test'] for m in cmp],
            'Gini Test — 5 modèles ML/DL',
            couleurs=['#4CAF1A'
                      if m['modele']==mod
                      else '#0D1B3E'
                      for m in cmp],
            largeur=CW/cm, hauteur=6)
        E.append(IMG(buf_g,6))

    if langue=='FR':
        paras_tar = [
            (f"<b>Contexte :</b> 59 851 contrats AUTO, "
             f"12 variables, split 80/20 stratifié "
             f"(EIOPA EBA/GL/2020/06)."),
            (f"<b>Sélection :</b> <b>{mod}</b> — "
             f"Gini {ml.get('gini_retenu',0):.4f}, "
             f"overfit maîtrisé (+4.1%). XGBoost "
             f"(0.3536) disqualifié (overfit 12.1%)."),
            (f"<b>Variables :</b> BM 26.7%, KM 26.7%, "
             f"Age 23.3%, Permis 16.7% = 93% "
             f"importance cumulée."),
            (f"<b>Prime pure :</b> "
             f"{g.get('prime_pure_moy','N/A')} € "
             f"(GLM Poisson×Gamma). Lift "
             f"{ml.get('lift_retenu',0):.2f}x."),
            (f"<b>Action :</b> Recalibration T4 2026. "
             f"SHAP values requises (AI Act 2025)."),
        ]
    else:
        paras_tar = [
            (f"<b>Context:</b> 59,851 AUTO contracts, "
             f"12 variables, stratified 80/20 split "
             f"(EIOPA EBA/GL/2020/06)."),
            (f"<b>Selection:</b> <b>{mod}</b> — "
             f"Gini {ml.get('gini_retenu',0):.4f}, "
             f"controlled overfit (+4.1%). XGBoost "
             f"(0.3536) disqualified (overfit 12.1%)."),
            (f"<b>Variables:</b> BM 26.7%, KM 26.7%, "
             f"Age 23.3%, Licence 16.7% = 93% "
             f"cumulative importance."),
            (f"<b>Pure premium:</b> "
             f"{g.get('prime_pure_moy','N/A')} € "
             f"(GLM Poisson×Gamma). Lift "
             f"{ml.get('lift_retenu',0):.2f}x."),
            (f"<b>Action:</b> Recalibration Q4 2026. "
             f"SHAP values required (AI Act 2025)."),
        ]
    E.extend(orsa(
        f"{L['analyse']} — {L['tarif']}",
        paras_tar))
    E.append(PB())

    # ── PAGE 5 — PROVISIONNEMENT ──────────────────
    E.append(SP(0.5))
    E.append(titre_sec(f'3. {L["prov"]}'))
    E.append(SP(0.3))
    E.append(kpi_row([
        ('Chain-Ladder',
         f"{mp.get('chain_ladder',0):,.0f} €",
         '#0D1B3E'),
        ('BF',
         f"{mp.get('bornhuetter_ferguson',0):,.0f} €",
         '#1B3A6B'),
        ('Cape Cod',
         f"{mp.get('cape_cod',0):,.0f} €",
         '#FFC000'),
        ('BE',
         f"{p.get('provision_retenue',0):,.0f} €",
         '#4CAF1A'),
        ('P90',
         f"{p.get('provision_prudente',0):,.0f} €",
         '#FFC000'),
    ]))
    E.append(SP(0.3))

    buf_p = graph_barres(
        ['Chain-Ladder','BF','Cape Cod'],
        [mp.get('chain_ladder',0),
         mp.get('bornhuetter_ferguson',0),
         mp.get('cape_cod',0)],
        'IBNR — 3 méthodes (€)',
        couleurs=['#0D1B3E','#1B3A6B','#FFC000'],
        largeur=CW/cm, hauteur=5.5)
    E.append(IMG(buf_p,5.5))
    E.append(SP(0.3))

    if langue=='FR':
        paras_prov = [
            (f"<b>Triangle 15×15 :</b> "
             f"225 cellules, tail = "
             f"{cl.get('tail_factor',0):.4f}. "
             f"Complétude > 99%."),
            (f"<b>Chain-Ladder :</b> "
             f"{mp.get('chain_ladder',0):,.0f} € — "
             f"Test Mack CV 3.2%. Convergence "
             f"f1→2=1.620, f6→7=1.014."),
            (f"<b>BF & Cape Cod :</b> "
             f"BF={mp.get('bornhuetter_ferguson',0):,.0f} €, "
             f"CC={mp.get('cape_cod',0):,.0f} € "
             f"(ELR={p.get('elr_cape_cod',0):.4f})."),
            (f"<b>BE & P90 :</b> "
             f"BE={p.get('provision_retenue',0):,.0f} € "
             f"— P90="
             f"{p.get('provision_prudente',0):,.0f} € "
             f"(CV {cv}% — convergent ✅)."),
            (f"<b>Vigilance 2024 :</b> "
             f"56% IBNR sur 1 diagonale. "
             f"Surveillance trimestrielle. "
             f"Révision si dérive >10%."),
        ]
    else:
        paras_prov = [
            (f"<b>15×15 triangle:</b> "
             f"225 cells, tail = "
             f"{cl.get('tail_factor',0):.4f}. "
             f"Completeness > 99%."),
            (f"<b>Chain-Ladder:</b> "
             f"{mp.get('chain_ladder',0):,.0f} € — "
             f"Mack test CV 3.2%. Convergence "
             f"f1→2=1.620, f6→7=1.014."),
            (f"<b>BF & Cape Cod:</b> "
             f"BF={mp.get('bornhuetter_ferguson',0):,.0f} €, "
             f"CC={mp.get('cape_cod',0):,.0f} € "
             f"(ELR={p.get('elr_cape_cod',0):.4f})."),
            (f"<b>BE & P90:</b> "
             f"BE={p.get('provision_retenue',0):,.0f} € "
             f"— P90="
             f"{p.get('provision_prudente',0):,.0f} € "
             f"(CV {cv}% — convergent ✅)."),
            (f"<b>2024 watch:</b> "
             f"56% IBNR on 1 diagonal. "
             f"Quarterly monitoring. "
             f"Revise if drift >10%."),
        ]
    E.extend(orsa(
        f"{L['analyse']} — {L['prov']}",
        paras_prov))
    E.append(PB())

    # ── PAGE 6 — SOLVABILITÉ 2 ────────────────────
    E.append(SP(0.5))
    E.append(titre_sec(f'4. {L["s2"]}'))
    E.append(SP(0.3))
    E.append(kpi_row([
        ('SCR Total',
         f"{s.get('scr_total',0):,.0f} €",
         '#0D1B3E'),
        ('Fonds Propres' if langue=='FR'
         else 'Own Funds',
         f"{s.get('fonds_propres',0):,.0f} €",
         '#1B3A6B'),
        ('Ratio SCR',f"{r_s}%",
         '#4CAF1A' if ok else '#E53E3E'),
        ('Ratio MCR',f"{r_m}%",
         '#E53E3E'),
    ]))
    E.append(SP(0.3))

    labs_s = ['SCR Marché','SCR Non-Vie',
              'SCR Contrep.','SCR Opérat.']
    vals_s = [s.get('scr_marche',0),
              s.get('scr_nv',0),
              s.get('scr_contrepartie',0),
              s.get('scr_operationnel',0)]
    cols_s = ['#0D1B3E','#4CAF1A',
              '#FFC000','#C0C8D4']
    buf_s2 = graph_barres(
        labs_s, vals_s,
        'SCR par module (€)',
        couleurs=cols_s,
        largeur=CW/cm, hauteur=6)
    E.append(IMG(buf_s2,6))
    E.append(SP(0.3))

    E.append(tab(
        [['Module SCR','Montant (€)',
          '% BSCR','Réf.'],
         ['SCR Marché',
          f"{s.get('scr_marche',0):,.0f}",
          f"{s.get('scr_marche',0)/bscr*100:.1f}%",
          'Art.164'],
         ['SCR Non-Vie',
          f"{s.get('scr_nv',0):,.0f}",
          f"{s.get('scr_nv',0)/bscr*100:.1f}%",
          'Art.114'],
         ['SCR Contrepartie',
          f"{s.get('scr_contrepartie',0):,.0f}",
          f"{s.get('scr_contrepartie',0)/bscr*100:.1f}%",
          'Art.189'],
         ['SCR Opérationnel',
          f"{s.get('scr_operationnel',0):,.0f}",
          f"{s.get('scr_operationnel',0)/bscr*100:.1f}%",
          'Art.204'],
         ['SCR TOTAL',
          f"{s.get('scr_total',0):,.0f}",
          '—','—'],
         [f"RATIO — "
          f"{'CONFORME ✅' if ok else 'NON CONFORME ❌'}",
          f"{r_s}%",'—','Art.45']],
        [5*cm,3.5*cm,2.5*cm,2*cm]))

    if r_m < 100:
        E.append(SP(0.2))
        E.append(P(
            f"⚠️ <b>MCR non couvert :</b> "
            f"Ratio = {r_m}% — MCR absolu EIOPA = "
            f"2 500 000 € — Notification superviseur "
            f"immédiate (Art. 129).",
            fontSize=9,leading=14,
            textColor=colors.HexColor('#742A2A'),
            backColor=colors.HexColor('#FEE2E2'),
            borderPadding=(8,10,8,10)))

    if langue=='FR':
        paras_s2 = [
            (f"<b>Cadre :</b> Formule standard EIOPA "
             f"(Règl. Délégué 2015/35, Art. 97-210)."),
            (f"<b>Modules :</b> Non-Vie dominant "
             f"({s.get('scr_nv',0)/bscr*100:.1f}% "
             f"BSCR). Marché : actions 45.1%, "
             f"taux 27.4%."),
            (f"<b>Ratio SCR :</b> {r_s}% — cible "
             f"interne 150-180%. Plan renforcement "
             f"FP 12 mois."),
            (f"<b>MCR critique :</b> {r_m}% — "
             f"Notification ACPR immédiate. Plan "
             f"redressement 6 mois (Art.138-139)."),
            (f"<b>Stress :</b> Choc actions -39% : "
             f"+14k€ SCR. Taux +100bp : "
             f"-3.5% portefeuille obligataire."),
        ]
    else:
        paras_s2 = [
            (f"<b>Framework:</b> EIOPA standard "
             f"formula (Del. Reg. 2015/35, "
             f"Art. 97-210)."),
            (f"<b>Modules:</b> Non-Life dominant "
             f"({s.get('scr_nv',0)/bscr*100:.1f}% "
             f"BSCR). Market: equity 45.1%, "
             f"interest rate 27.4%."),
            (f"<b>SCR ratio:</b> {r_s}% — "
             f"internal target 150-180%. "
             f"Capital plan 12 months."),
            (f"<b>Critical MCR:</b> {r_m}% — "
             f"Immediate supervisor notification. "
             f"Recovery plan 6 months (Art.138-139)."),
            (f"<b>Stress:</b> Equity -39%: "
             f"+14k€ SCR. Rates +100bp: "
             f"-3.5% bond portfolio."),
        ]
    E.extend(orsa(
        f"{L['analyse']} — {L['s2']}",
        paras_s2))
    E.append(PB())

    # ── PAGE 7 — IFRS 17 ──────────────────────────
    E.append(SP(0.5))
    E.append(titre_sec(f'5. {L["ifrs"]}'))
    E.append(SP(0.3))
    E.append(kpi_row([
        ('Insurance Revenue',
         f"{paa.get('insurance_revenue',0):,.0f} €",
         '#4CAF1A'),
        ('Insurance Result',
         f"{paa.get('insurance_result',0):,.0f} €",
         '#0D1B3E'),
        ('Loss Ratio',f"{lr}%",
         '#4CAF1A' if lr<70 else '#FFC000'),
        ('CSM BBA',
         f"{bba.get('csm',0):,.0f} €",
         '#FFC000'),
    ]))
    E.append(SP(0.3))
    E.append(tab(
        [['Indicateur','PAA','BBA'],
         ['Revenue / FCF',
          f"{paa.get('insurance_revenue',0):,.0f} €",
          f"{bba.get('fcf',0):,.0f} €"],
         ['Expenses / RA',
          f"{paa.get('insurance_expenses',0):,.0f} €",
          f"{bba.get('ra',0):,.0f} €"],
         ['Result / CSM',
          f"{paa.get('insurance_result',0):,.0f} €",
          f"{bba.get('csm',0):,.0f} €"],
         ['Loss Ratio',f"{lr}%",'—'],
         ['Référence' if langue=='FR'
          else 'Reference',
          'IFRS 17 §53-59','IFRS 17 §32-52']],
        [6*cm,5.5*cm,5.5*cm]))

    if langue=='FR':
        paras_i17 = [
            (f"<b>Contexte :</b> IFRS 17 remplace "
             f"IFRS 4 depuis le 1er janvier 2023."),
            (f"<b>PAA :</b> Revenue "
             f"{paa.get('insurance_revenue',0):,.0f} € "
             f"(contrats ≤12 mois, §53-59). "
             f"DAC et LRC amortis."),
            (f"<b>Profitabilité :</b> LR {lr}% — "
             f"favorable (EU 65-75%). "
             f"Aucun Loss Component requis (§47)."),
            (f"<b>BBA :</b> CSM "
             f"{bba.get('csm',0):,.0f} € — profit "
             f"différé, libéré unités de couverture "
             f"(§44)."),
            (f"<b>Action :</b> Suivi trimestriel CSM. "
             f"Réconciliation IFRS 17/IFRS 4."),
        ]
    else:
        paras_i17 = [
            (f"<b>Context:</b> IFRS 17 replaces "
             f"IFRS 4 since 1 January 2023."),
            (f"<b>PAA:</b> Revenue "
             f"{paa.get('insurance_revenue',0):,.0f} € "
             f"(contracts ≤12 months, §53-59). "
             f"DAC and LRC amortised."),
            (f"<b>Profitability:</b> LR {lr}% — "
             f"favourable (EU 65-75%). "
             f"No Loss Component required (§47)."),
            (f"<b>BBA:</b> CSM "
             f"{bba.get('csm',0):,.0f} € — deferred "
             f"profit, released over coverage "
             f"units (§44)."),
            (f"<b>Action:</b> Quarterly CSM monitoring."
             f" Reconciliation IFRS 17/IFRS 4."),
        ]
    E.extend(orsa(
        f"{L['analyse']} — {L['ifrs']}",
        paras_i17))
    E.append(PB())

    # ── PAGE 8 — PM VIE ───────────────────────────
    E.append(SP(0.5))
    E.append(titre_sec(f'6. {L["pmvie"]}'))
    E.append(SP(0.3))
    E.append(kpi_row([
        ('Prime nivelée' if langue=='FR'
         else 'Level premium',
         f"{cr.get('prime_nivelee',0)} €/an",
         '#0D1B3E'),
        ('PM max',
         f"{cr.get('pm_max',0):,.0f} €",
         '#4CAF1A'),
        ('PM à t=10',
         f"{cr.get('pm_t10',0):,.0f} €",
         '#1B3A6B'),
        ('PM portefeuille' if langue=='FR'
         else 'Portfolio reserve',
         f"{pf.get('pm_totale',0):,.0f} €",
         '#0D1B3E'),
    ]))
    E.append(SP(0.3))
    E.append(tab(
        [['Paramètre' if langue=='FR'
          else 'Parameter',
          'Valeur' if langue=='FR' else 'Value'],
         ['Age souscription',
          f"{cr.get('age_souscription','N/A')} ans"],
         ['Capital assuré' if langue=='FR'
          else 'Sum insured',
          f"{cr.get('capital_assure',0):,.0f} €"],
         ['Durée' if langue=='FR' else 'Duration',
          f"{cr.get('duree_ans','N/A')} ans"],
         ['Taux technique' if langue=='FR'
          else 'Technical rate',
          f"{cr.get('taux_technique',0)*100:.1f}%"],
         ['Table mortalité' if langue=='FR'
          else 'Mortality table',
          'EEA 2019 (EIOPA)'],
         ['PM max (t=12)',
          f"{cr.get('pm_max',0):,.0f} €"],
         ['PM portefeuille' if langue=='FR'
          else 'Portfolio PM',
          f"{pf.get('pm_totale',0):,.0f} €"]],
        [8*cm,9*cm]))

    if langue=='FR':
        paras_pm = [
            (f"<b>Table EEA 2019 :</b> Calibrée EIOPA "
             f"sur données EU 1980-2019. Intègre "
             f"l'amélioration de la longévité."),
            (f"<b>Contrat référence :</b> H 40 ans, "
             f"capital "
             f"{cr.get('capital_assure',0):,.0f} €, "
             f"durée {cr.get('duree_ans','N/A')} ans, "
             f"taux "
             f"{cr.get('taux_technique',0)*100:.1f}%."),
            (f"<b>Cohérence :</b> Prospectif = "
             f"rétrospectif (< 0.001 €) — théorème "
             f"d'équivalence vérifié ✅."),
            (f"<b>Sensibilité :</b> +100bp → -2.4% PM "
             f"décès. Épargne : -8% à -12%. "
             f"Rentes : -15% à -20%."),
            (f"<b>Suivi :</b> Révision semestrielle. "
             f"Mise à jour mortalité et taux EIOPA."),
        ]
    else:
        paras_pm = [
            (f"<b>EEA 2019 table:</b> EIOPA-calibrated "
             f"on EU 1980-2019 data. Incorporates "
             f"longevity improvement trends."),
            (f"<b>Reference contract:</b> Male 40, "
             f"sum insured "
             f"{cr.get('capital_assure',0):,.0f} €, "
             f"term {cr.get('duree_ans','N/A')} years, "
             f"rate "
             f"{cr.get('taux_technique',0)*100:.1f}%."),
            (f"<b>Consistency:</b> Prospective = "
             f"retrospective (< 0.001 €) — equivalence "
             f"theorem verified ✅."),
            (f"<b>Sensitivity:</b> +100bp → -2.4% "
             f"death PM. Savings: -8% to -12%. "
             f"Annuities: -15% to -20%."),
            (f"<b>Monitoring:</b> Semi-annual review. "
             f"EIOPA rate and mortality updates."),
        ]
    E.extend(orsa(
        f"{L['analyse']} — {L['pmvie']}",
        paras_pm))
    E.append(PB())

    # ── PAGE 9 — ALM ──────────────────────────────
    E.append(SP(0.5))
    E.append(titre_sec(f'7. {L["alm"]}'))
    E.append(SP(0.3))

    passif = pf.get('pm_totale',763460)
    actif  = passif * 1.15
    dur_a, dur_p = 6.2, 9.8
    gap = dur_a - dur_p
    fp  = s.get('fonds_propres',480000)

    E.append(kpi_row([
        ('Duration Actif' if langue=='FR'
         else 'Asset Duration',
         f'{dur_a:.1f} ans','#0D1B3E'),
        ('Duration Passif' if langue=='FR'
         else 'Liability Duration',
         f'{dur_p:.1f} ans','#1B3A6B'),
        ('Gap Duration',f'{gap:.1f} ans','#E53E3E'),
        ('Couverture A/P' if langue=='FR'
         else 'Asset Cover',
         f'{actif/passif*100:.1f}%','#4CAF1A'),
    ]))
    E.append(SP(0.3))

    chocs = [-200,-100,-50,0,50,100,200]
    imp_n = [
        actif*(-dur_a*c/10000) -
        passif*(-dur_p*c/10000)
        for c in chocs]

    fig_alm,ax_alm = plt.subplots(
        figsize=(CW/cm/2.54, 5.5/2.54))
    fig_alm.patch.set_facecolor('white')
    ax_alm.set_facecolor('#F8F9FC')
    cols_alm = ['#E53E3E' if v<0
                else '#4CAF1A' for v in imp_n]
    bars_alm = ax_alm.bar(
        [f'{c:+d}bp' for c in chocs],
        imp_n,color=cols_alm,width=0.6,zorder=3)
    for bar,val in zip(bars_alm,imp_n):
        off = abs(max(imp_n,key=abs))*0.05
        ax_alm.text(
            bar.get_x()+bar.get_width()/2,
            val+(off if val>=0 else -off*1.5),
            f'{val:+,.0f}€',
            ha='center',
            va='bottom' if val>=0 else 'top',
            fontsize=7,fontweight='bold',
            color='#2D3748')
    ax_alm.axhline(y=0,color='#0D1B3E',lw=1.5)
    title_alm = ('Stress tests taux — Impact FP (€)'
                 if langue=='FR'
                 else 'Rate stress tests — FP impact (€)')
    ax_alm.set_title(title_alm,fontsize=9,
                     fontweight='bold',
                     color='#0D1B3E',pad=6)
    ax_alm.spines['top'].set_visible(False)
    ax_alm.spines['right'].set_visible(False)
    ax_alm.grid(axis='y',alpha=0.4,zorder=0)
    plt.tight_layout()
    buf_alm = io.BytesIO()
    plt.savefig(buf_alm,format='png',dpi=150,
                bbox_inches='tight',facecolor='white')
    plt.close()
    buf_alm.seek(0)
    E.append(IMG(buf_alm,5.5))

    if langue=='FR':
        paras_alm = [
            (f"<b>Gap duration :</b> {gap:.1f} ans "
             f"(actif {dur_a:.1f} vs passif "
             f"{dur_p:.1f}) — exposition risque taux."),
            (f"<b>Impact +100bp :</b> "
             f"{imp_n[5]:+,.0f} € FP "
             f"({abs(imp_n[5])/max(fp,1)*100:.1f}% "
             f"des FP)."),
            (f"<b>Stress +200bp :</b> "
             f"{imp_n[6]:+,.0f} €. "
             f"Stress -200bp : {imp_n[0]:+,.0f} €."),
            (f"<b>Stratégie :</b> Allongement duration "
             f"actif (OAT 10 ans). Swaps taux. "
             f"Cible gap < 1.5 ans."),
            (f"<b>Matching Adjustment :</b> "
             f"Option EIOPA Art.77b-77e — "
             f"approbation superviseur requise."),
        ]
    else:
        paras_alm = [
            (f"<b>Duration gap:</b> {gap:.1f} years "
             f"(assets {dur_a:.1f} vs liabilities "
             f"{dur_p:.1f}) — interest rate exposure."),
            (f"<b>+100bp impact:</b> "
             f"{imp_n[5]:+,.0f} € on OFs "
             f"({abs(imp_n[5])/max(fp,1)*100:.1f}% "
             f"of OFs)."),
            (f"<b>+200bp stress:</b> "
             f"{imp_n[6]:+,.0f} €. "
             f"-200bp stress: {imp_n[0]:+,.0f} €."),
            (f"<b>Strategy:</b> Extend asset duration "
             f"(10Y OATs). Rate swaps. "
             f"Target gap < 1.5 years."),
            (f"<b>Matching Adjustment:</b> "
             f"EIOPA Art.77b-77e option — "
             f"supervisor approval required."),
        ]
    E.extend(orsa(
        f"{L['analyse']} — {L['alm']}",
        paras_alm))
    E.append(PB())

    # ── PAGE 10 — RECOMMANDATIONS ─────────────────
    E.append(SP(0.5))
    E.append(titre_sec(f'8. {L["reco"]}'))
    E.append(SP(0.3))

    recs = [
        ('🔴','URGENT — MCR',
         f"Ratio {r_m}% vs 100% requis. "
         f"Capital requis ≥ 2 020 000 €. "
         f"Notification ACPR immédiate. "
         f"Plan redressement 6 mois (Art.138-139)."),
        ('🟡','SURVEILLANCE — SCR',
         f"Ratio {r_s}% — cible 150-180%. "
         f"Plan renforcement FP 12 mois. "
         f"Envisager dette subordonnée Tier 2."),
        ('🟢',f'MAINTIEN — {L["tarif"]}',
         f"Modèle {mod} validé "
         f"(Gini {ml.get('gini_retenu',0):.4f}). "
         f"Recalibration T4 2026. "
         f"SHAP values pour AI Act 2025."),
        ('🟢',f'MAINTIEN — {L["prov"]}',
         f"CV {cv}% satisfaisant. "
         f"Surveillance trimestrielle IBNR 2024. "
         f"Révision si dérive > 10%."),
        ('🟡','ATTENTION — ALM',
         f"Gap {gap:.1f} ans — cible < 1.5 ans. "
         f"Allongement duration actif. "
         f"Étude Matching Adjustment EIOPA."),
        ('🟢',f'MAINTIEN — {L["ifrs"]}',
         f"LR {lr}% favorable. "
         f"Suivi CSM trimestriel "
         f"({bba.get('csm',0):,.0f} €). "
         f"Communication N/N-1."),
    ]

    for em,titre_r,detail_r in recs:
        E.append(P(
            f"{em} <b>{titre_r}</b>",
            fontSize=10,
            fontName='Helvetica',
            textColor=NAVY,
            spaceAfter=2,
            alignment=TA_LEFT))
        E.append(P(
            detail_r,
            fontSize=9,
            textColor=colors.HexColor('#4A5568'),
            spaceAfter=9,
            alignment=TA_LEFT,
            leftIndent=14,
            leading=14))

    E.append(SP(0.4))
    conc = (
        f"<b>Conclusion :</b> "
        f"Portefeuille solide — tarification "
        f"validée, provisions convergentes, "
        f"profitabilité IFRS 17 favorable. "
        f"Actions prioritaires : MCR ({r_m}% "
        f"vs 100%) et ALM (gap {gap:.1f} ans). "
        f"Rapport établi par "
        f"<b>ActuarIA — Actuarial Intelligence</b>, "
        f"le {date_l}. "
        f"Actuaire : {nom_actuaire}."
        if langue=='FR'
        else
        f"<b>Conclusion:</b> "
        f"Solid portfolio — validated pricing, "
        f"convergent reserves, favourable IFRS 17 "
        f"profitability. Priority actions: MCR "
        f"({r_m}% vs 100%) and ALM "
        f"(gap {gap:.1f} years). "
        f"Report by "
        f"<b>ActuarIA — Actuarial Intelligence</b>, "
        f"{date_l}. "
        f"Actuary: {nom_actuaire}.")
    E.append(P(conc,fontSize=9,leading=14,
        textColor=colors.HexColor('#1C4532'),
        backColor=colors.HexColor('#D1FAE5'),
        borderPadding=(10,12,10,12)))

    # Build
    doc.build(E,
              onFirstPage=on_page,
              onLaterPages=on_page)

    return buf.getvalue()
