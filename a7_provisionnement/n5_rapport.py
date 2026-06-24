# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n5_rapport.py  —  Export Word (.docx) + PDF
# =============================================================================
#
#  Génère le rapport Word professionnel calqué sur Rapport_Actuariel_Q2_2026.docx
#  Style : dense, peu d'espaces, tableaux propres, graphiques PNG embarqués,
#          en-tête/pied de page, numérotation, "CONFIDENTIEL" en rouge.
#
#  Structure en 5 sections (calquée sur le rapport de référence) :
#  1. Page de garde (titre centré + tableau KPI 4 colonnes)
#  2. Synthèse exécutive (KPIs + points saillants)
#  3. Provisionnement Non-Vie (méthodologie + résultats par branche/méthode)
#  4. Validation hypothèses + incertitude stochastique
#  5. SCR provisions + recommandations + signature
#
#  Le rapport Word est généré via un script Node.js (docx@9.6.1).
#  Les graphiques Plotly sont exportés en PNG via kaleido avant embarquement.
#  Le PDF est produit par conversion LibreOffice du Word.
#
# =============================================================================

import io
import json
import logging
import os
import subprocess
import tempfile
import zipfile
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger('actuaria.a7')

# Chemin vers le script Node.js générateur
_SCRIPT_DIR = Path(__file__).parent


# =============================================================================
#  EXPORT GRAPHIQUES PNG (pour embarquement Word/PDF)
# =============================================================================

def exporter_graphiques_png(
    graphiques: Dict,
    width:  int = 900,
    height: int = 380,
) -> Dict[str, bytes]:
    """
    Exporte les graphiques Plotly en PNG via kaleido.

    Parameters
    ----------
    graphiques : dict {nom: go.Figure}
    width, height : dimensions en pixels

    Returns
    -------
    dict {nom: bytes_png}
    """
    pngs = {}
    try:
        import plotly.io as pio
        for nom, fig in graphiques.items():
            try:
                png = pio.to_image(fig, format='png', width=width, height=height)
                pngs[nom] = png
            except Exception as e:
                logger.warning(f"PNG {nom} échoué : {e}")
    except ImportError:
        logger.warning("plotly.io non disponible — graphiques PNG désactivés")
    return pngs


# =============================================================================
#  DONNÉES STRUCTURÉES POUR LE RAPPORT
# =============================================================================

def _build_report_data(
    n1:         Dict,
    n2:         Dict,
    n3:         Dict,
    n4:         Dict,
    commentaire: str,
    ref_client: str,
    arrete:     str,
    audit_id:   str,
    lob_label:  str,
) -> Dict:
    """
    Construit le dict de données structurées pour le générateur Node.js.
    Toutes les valeurs sont sérialisables JSON (pas de numpy, pas de Figure).
    """
    def _f(v):
        """Float ou None."""
        if v is None: return None
        try: return float(v)
        except: return None

    cl   = n3.get('chain_ladder', {})
    mack = n3.get('mack', {})
    bf   = n3.get('bf', {})
    cc   = n3.get('cape_cod', {})
    boot = n3.get('bootstrap', {})
    scr  = n4.get('scr', {})

    return {
        # Méta
        'ref_client':  ref_client or 'ActuarIA',
        'arrete':      arrete or datetime.now().strftime('%d/%m/%Y'),
        'audit_id':    audit_id or '',
        'date_rapport': datetime.now().strftime('%d/%m/%Y'),
        'lob_label':   lob_label or n2.get('lob_label', '—'),

        # N1
        'n1': {
            'taille':       n1.get('taille', '—'),
            'n_annees':     n1.get('n_annees', 0),
            'n_dev':        n1.get('n_dev', 0),
            'mode_detecte': n1.get('mode_detecte', '—'),
            'statut':       n1.get('statut', 'AMBRE'),
            'alertes':      [str(a) for a in n1.get('alertes', [])],
            'infos':        [str(i) for i in n1.get('infos', [])],
        },

        # N2
        'n2': {
            'h1_independance': {
                'ok':     bool(n2.get('h1_independance', {}).get('ok', True)),
                'score':  n2.get('h1_independance', {}).get('score', 0),
                'corr_moy': _f(n2.get('h1_independance', {}).get('corr_moy', 0)),
                'n_colonnes_sig': n2.get('h1_independance', {}).get('n_colonnes_sig', 0),
                'n_colonnes_testees': n2.get('h1_independance', {}).get('n_colonnes_testees', 0),
                'seuil_utilise': _f(n2.get('h1_independance', {}).get('seuil_utilise', 0.5)),
                'message': str(n2.get('h1_independance', {}).get('message', '—')),
            },
            'h2_stabilite': {
                'ok':         bool(n2.get('h2_stabilite', {}).get('ok', True)),
                'score':      n2.get('h2_stabilite', {}).get('score', 0),
                'cv_moy':     _f(n2.get('h2_stabilite', {}).get('cv_moy', 0)),
                'derive_moy': _f(n2.get('h2_stabilite', {}).get('derive_moy', 0)),
                'seuil_cv':   _f(n2.get('h2_stabilite', {}).get('seuil_cv', 0.15)),
                'message':    str(n2.get('h2_stabilite', {}).get('message', '—')),
            },
            'h3_apriori_bf': {
                'ok':        bool(n2.get('h3_apriori_bf', {}).get('ok', True)),
                'score':     n2.get('h3_apriori_bf', {}).get('score', 0),
                'lr_apriori': _f(n2.get('h3_apriori_bf', {}).get('lr_apriori', 0)),
                'source':    str(n2.get('h3_apriori_bf', {}).get('source', '—')),
                'message':   str(n2.get('h3_apriori_bf', {}).get('message', '—')),
            },
            'h4_homosc_bootstrap': {
                'ok':     bool(n2.get('h4_homosc_bootstrap', {}).get('ok', True)),
                'score':  n2.get('h4_homosc_bootstrap', {}).get('score', 0),
                'phi':    _f(n2.get('h4_homosc_bootstrap', {}).get('phi', 0)),
                'message': str(n2.get('h4_homosc_bootstrap', {}).get('message', '—')),
            },
            'scores_confiance':      {k: int(v) for k, v in n2.get('scores_confiance', {}).items()},
            'methode_recommandee':   str(n2.get('methode_recommandee', '—')),
            'methode_cl_retenue':    str(n2.get('methode_cl_retenue', '—')),
            'raison_recommandation': str(n2.get('raison_recommandation', '—')),
            'raison_cl':             str(n2.get('raison_cl', '—')),
            'statut_global':         str(n2.get('statut_global', 'AMBRE')),
            'alertes': [str(a) for a in n2.get('alertes', [])],
            'infos':   [str(i) for i in n2.get('infos', [])],
        },

        # N3
        'n3': {
            'methode_cl': str(n3.get('methode_cl', '—')),
            'facteurs':   [_f(f) for f in cl.get('facteurs', [])],
            'chain_ladder': {
                'reserve_totale':   _f(cl.get('reserve_totale', 0)),
                'ibnr_par_annee':   [_f(v) for v in cl.get('ibnr_par_annee', [])],
                'ultimates':        [_f(v) for v in cl.get('ultimates', [])],
                'pct_developpe':    [_f(v) for v in cl.get('pct_developpe', [])],
                'last_diagonale':   [_f(v) for v in cl.get('last_diagonale', [])],
                'methode':          str(cl.get('methode', '—')),
            },
            'mack': {
                'reserve_best_estimate': _f(mack.get('reserve_best_estimate', 0)),
                'sigma_total':           _f(mack.get('sigma_total', 0)),
                'cv_pct':                _f(mack.get('cv_pct', 0)),
                'reserve_p75':           _f(mack.get('reserve_p75', 0)),
                'reserve_p90':           _f(mack.get('reserve_p90', 0)),
                'reserve_p99_5':         _f(mack.get('reserve_p99_5', 0)),
                'statut':                str(mack.get('statut', '—')),
                'message':               str(mack.get('message', '—')),
            },
            'bf': {
                'reserve_totale': _f(bf.get('reserve_totale', 0)),
                'lr_apriori':     _f(bf.get('lr_apriori', 0)),
                'source_lr':      str(bf.get('source_lr', '—')),
                'ibnr_par_annee': [_f(v) for v in bf.get('ibnr_par_annee', [])],
                'message':        str(bf.get('message', '—')),
            },
            'cape_cod': {
                'reserve_totale': _f(cc.get('reserve_totale', 0)),
                'lr_cape_cod':    _f(cc.get('lr_cape_cod', 0)),
                'message':        str(cc.get('message', '—')),
            },
            'bootstrap': {
                'be_bootstrap':   _f(boot.get('be_bootstrap', 0)),
                'std_bootstrap':  _f(boot.get('std_bootstrap', 0)),
                'cv_bootstrap':   _f(boot.get('cv_bootstrap', 0)),
                'p50':            _f(boot.get('p50', 0)),
                'p75':            _f(boot.get('p75', 0)),
                'p90':            _f(boot.get('p90', 0)),
                'p95':            _f(boot.get('p95', 0)),
                'p99_5':          _f(boot.get('p99_5', 0)),
                'ic_95_inf':      _f(boot.get('ic_95_inf', 0)),
                'ic_95_sup':      _f(boot.get('ic_95_sup', 0)),
                'phi':            _f(boot.get('phi', 0)),
                'n_simulations':  int(boot.get('n_simulations', 0)),
                'statut':         str(boot.get('statut', '—')),
                'message':        str(boot.get('message', '—')),
            },
            'tail_factor': {
                'tail_factor': _f(
                    cl.get('tail_factor', {}).get('tail_factor', 1.0)
                    if isinstance(cl.get('tail_factor'), dict) else 1.0
                ),
                'message': str(
                    cl.get('tail_factor', {}).get('message', '—')
                    if isinstance(cl.get('tail_factor'), dict) else '—'
                ),
                'statut': str(
                    cl.get('tail_factor', {}).get('statut', '—')
                    if isinstance(cl.get('tail_factor'), dict) else '—'
                ),
            },
        },

        # N4
        'n4': {
            'best_estimate':       _f(n4.get('best_estimate', 0)),
            'reserve_p75':         _f(n4.get('reserve_p75', 0)),
            'reserve_p90':         _f(n4.get('reserve_p90', 0)),
            'reserve_p99_5':       _f(n4.get('reserve_p99_5', 0)),
            'sigma_mack':          _f(n4.get('sigma_mack', 0)),
            'cv_inter_methodes':   _f(n4.get('cv_inter_methodes', 0)),
            'methodes_incluses':   [str(m) for m in n4.get('methodes_incluses', [])],
            'methodes_exclues':    [str(m) for m in n4.get('methodes_exclues', [])],
            'poids': {k: _f(v) for k, v in n4.get('poids', {}).items()},
            'sensibilites': {k: _f(v) for k, v in n4.get('sensibilites', {}).items()},
            'statut':  str(n4.get('statut', 'AMBRE')),
            'message': str(n4.get('message', '—')),
            'jugement': str(n4.get('jugement', '')),
            'scr': {
                'scr_provisions':  _f(scr.get('scr_provisions', 0)),
                'sigma_eiopa':     _f(scr.get('sigma_eiopa', 0)),
                'ratio_scr_be':    _f(scr.get('ratio_scr_be', 0)),
                'lob':             str(scr.get('lob', '—')),
                'lob_label':       str(scr.get('lob_label', '—')),
                'message':         str(scr.get('message', '—')),
            },
        },

        # Commentaire complet
        'commentaire': commentaire,

        # Statut global
        'statut_rag': str(n4.get('statut', 'AMBRE')),
    }


# =============================================================================
#  GÉNÉRATEUR NODE.JS (script embarqué)
# =============================================================================

_NODE_SCRIPT = r"""
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, Header, Footer, AlignmentType, HeadingLevel, BorderStyle,
  WidthType, ShadingType, VerticalAlign, PageNumber, LevelFormat,
  TabStopType, TabStopPosition,
} = require('docx');
const fs   = require('fs');
const path = require('path');

// ── Données ──────────────────────────────────────────────────────────────────
const dataPath = process.argv[2];
const outPath  = process.argv[3];
const imgDir   = process.argv[4] || '';
const data     = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
const n1 = data.n1, n2 = data.n2, n3 = data.n3, n4 = data.n4;

// ── Palette ───────────────────────────────────────────────────────────────────
const NAVY  = '0F2E52', GOLD = 'C9A84C', BLANC = 'FFFFFF';
const GRIS  = 'F0F4F8', GRIS2 = 'D0D8E4', NOIR = '1A1A1A';
const VERT  = '1D7A3A', AMBRE = 'B87A00', ROUGE = 'C0392B';
const BLEU  = '378ADD', VIOLET = '9B59B6';

// ── Helpers ───────────────────────────────────────────────────────────────────
function euro(v) {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return Number(v).toLocaleString('fr-FR', { maximumFractionDigits: 0 }) + '\u202f€';
}
function pct(v, d=1) {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return Number(v * 100).toFixed(d) + '\u202f%';
}
function num(v, d=4) {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return Number(v).toFixed(d);
}
function statutColor(s) {
  return s === 'VERT' ? VERT : s === 'ROUGE' ? ROUGE : AMBRE;
}
function statutTxt(s) {
  return s === 'VERT' ? 'Conforme' : s === 'ROUGE' ? 'Attention' : 'A surveiller';
}

const BORDER_CELL = {
  top:    { style: BorderStyle.SINGLE, size: 1, color: GRIS2 },
  bottom: { style: BorderStyle.SINGLE, size: 1, color: GRIS2 },
  left:   { style: BorderStyle.SINGLE, size: 1, color: GRIS2 },
  right:  { style: BorderStyle.SINGLE, size: 1, color: GRIS2 },
};
const BORDER_NONE = {
  top:    { style: BorderStyle.NONE, size: 0, color: BLANC },
  bottom: { style: BorderStyle.NONE, size: 0, color: BLANC },
  left:   { style: BorderStyle.NONE, size: 0, color: BLANC },
  right:  { style: BorderStyle.NONE, size: 0, color: BLANC },
};
const MARGINS = { top: 60, bottom: 60, left: 100, right: 100 };

function cell(children, opts = {}) {
  return new TableCell({
    borders:       opts.borders || BORDER_CELL,
    width:         { size: opts.width || 2256, type: WidthType.DXA },
    shading:       opts.shading || undefined,
    margins:       MARGINS,
    verticalAlign: opts.valign || VerticalAlign.CENTER,
    children,
  });
}

function para(text, opts = {}) {
  const runs = [new TextRun({
    text:    text || '',
    font:    'Arial',
    size:    opts.size || 20,
    bold:    opts.bold || false,
    color:   opts.color || NOIR,
    italics: opts.italic || false,
  })];
  if (opts.extra) runs.push(...opts.extra);
  return new Paragraph({
    alignment: opts.align || AlignmentType.LEFT,
    spacing:   { before: opts.before !== undefined ? opts.before : 40,
                 after:  opts.after  !== undefined ? opts.after  : 40 },
    children:  runs,
    numbering: opts.numbering || undefined,
    border:    opts.border || undefined,
  });
}

function h1(text) {
  return new Paragraph({
    heading:   HeadingLevel.HEADING_1,
    spacing:   { before: 200, after: 80 },
    border:    { bottom: { style: BorderStyle.SINGLE, size: 6, color: GOLD, space: 3 } },
    children:  [new TextRun({ text, font: 'Arial', size: 26, bold: true, color: NAVY })],
  });
}
function h2(text) {
  return new Paragraph({
    heading:  HeadingLevel.HEADING_2,
    spacing:  { before: 120, after: 60 },
    children: [new TextRun({ text, font: 'Arial', size: 22, bold: true, color: NAVY })],
  });
}
function vide(n=1) {
  return Array.from({length:n}, () =>
    new Paragraph({ spacing: { before: 0, after: 0 }, children: [new TextRun('')] })
  );
}
function alerte(text, niveau='INFO') {
  const colors = { INFO: BLEU, VERT: VERT, AMBRE: AMBRE, ROUGE: ROUGE };
  const pfx    = { INFO: '[i]', VERT: '[OK]', AMBRE: '[!]', ROUGE: '[X]' };
  const clean  = (text || '').replace(/[\u2600-\u27ff\u{1f000}-\u{1ffff}]/gu, '').trim();
  return new Paragraph({
    spacing: { before: 30, after: 30 },
    indent:  { left: 300 },
    border:  { left: { style: BorderStyle.SINGLE, size: 10, color: colors[niveau]||BLEU, space: 3 } },
    children: [
      new TextRun({ text: (pfx[niveau]||'[i]') + ' ', font: 'Arial', size: 18, bold: true, color: colors[niveau]||BLEU }),
      new TextRun({ text: clean, font: 'Arial', size: 18, color: NOIR }),
    ],
  });
}

// Tableau KPI 2 colonnes
function tableKV(rows, w0=5000, w1=4026) {
  return new Table({
    width: { size: w0+w1, type: WidthType.DXA },
    columnWidths: [w0, w1],
    rows: rows.map(([label, value, vColor]) =>
      new TableRow({ children: [
        cell([para(label, { bold: true, color: '444444', size: 19 })], { width: w0 }),
        cell([para(value || '—', { color: vColor || NOIR, size: 19 })], { width: w1 }),
      ]})
    ),
  });
}

// Image embarquée
function imgPara(imgBytes, label, w=8200, h=3400) {
  if (!imgBytes) return para(`[Graphique : ${label}]`, { italic: true, color: '888888' });
  try {
    return new Paragraph({
      spacing: { before: 40, after: 40 },
      children: [new ImageRun({
        type:   'png',
        data:   imgBytes,
        transformation: { width: Math.round(w*0.0945), height: Math.round(h*0.0945) },
      })],
    });
  } catch(e) {
    return para(`[Graphique : ${label}]`, { italic: true, color: '888888' });
  }
}

// Charger une image PNG depuis le répertoire temporaire
function loadImg(name) {
  if (!imgDir) return null;
  const p = path.join(imgDir, name + '.png');
  return fs.existsSync(p) ? fs.readFileSync(p) : null;
}

// ── KPI banner (4 colonnes, style rapport de référence) ───────────────────────
function kpiBanner(items) {
  // items = [{label, value, sublabel}]
  const cw = Math.floor(9026 / items.length);
  return new Table({
    width: { size: 9026, type: WidthType.DXA },
    columnWidths: items.map(() => cw),
    rows: [new TableRow({ children: items.map(it =>
      new TableCell({
        borders: BORDER_CELL,
        width:   { size: cw, type: WidthType.DXA },
        shading: { fill: GRIS, type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [
          para(it.label || '', { size: 17, color: '666666', align: AlignmentType.CENTER }),
          para(it.value || '—', { size: 26, bold: true, color: NAVY, align: AlignmentType.CENTER }),
          para(it.sublabel || '', { size: 16, color: statutColor(it.statut||'AMBRE'), align: AlignmentType.CENTER, italic: true }),
        ],
      })
    )})]
  });
}

// ── PAGE DE GARDE ──────────────────────────────────────────────────────────────
function pageDeGarde() {
  const statut = n4.statut || 'AMBRE';
  return [
    para('ActuarIA', { size: 52, bold: true, color: NAVY, align: AlignmentType.CENTER, before: 600, after: 0 }),
    para('Plateforme Actuarielle Intégrée', { size: 22, color: '666666', align: AlignmentType.CENTER, before: 0, after: 200 }),

    // Ligne séparatrice dorée
    new Paragraph({
      spacing: { before: 0, after: 200 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: GOLD, space: 2 } },
      children: [new TextRun('')],
    }),

    para('RAPPORT ACTUARIEL COMPLET', { size: 32, bold: true, color: NAVY, align: AlignmentType.CENTER, before: 200, after: 60 }),
    para(`Arrêté au ${data.arrete} — ${data.lob_label}`, { size: 22, color: '444444', align: AlignmentType.CENTER, before: 0, after: 60 }),
    para(data.ref_client, { size: 20, bold: true, color: NAVY, align: AlignmentType.CENTER, before: 0, after: 200 }),

    para('DOCUMENT CONFIDENTIEL — Usage interne', { size: 18, bold: true, color: ROUGE, align: AlignmentType.CENTER, before: 100, after: 100 }),
  ];
}

// ── SECTION 1 : SYNTHÈSE EXÉCUTIVE ────────────────────────────────────────────
function sectionSynthese() {
  const be    = n4.best_estimate;
  const p90   = n4.reserve_p90;
  const sigma = n4.sigma_mack;
  const cv    = n4.cv_inter_methodes;
  const statut= n4.statut;
  const scr   = n4.scr || {};

  const kpis = kpiBanner([
    { label: 'Best Estimate S2', value: euro(be),   sublabel: statutTxt(statut), statut },
    { label: 'Provision P90',    value: euro(p90),  sublabel: '+' + pct((p90/be)-1) + ' vs BE', statut: 'AMBRE' },
    { label: 'SCR Provisions',   value: euro(scr.scr_provisions), sublabel: 'Art. 105 S2', statut: 'VERT' },
    { label: 'CV méthodes',      value: pct(cv/100), sublabel: cv < 5 ? 'Convergence forte' : cv < 15 ? 'Acceptable' : 'A analyser',
      statut: cv < 5 ? 'VERT' : cv < 15 ? 'AMBRE' : 'ROUGE' },
  ]);

  // Points saillants (depuis commentaire §8)
  const alertesN2 = (n2.alertes || []).slice(0, 5).map(a => {
    const clean = (a || '').replace(/[\u2600-\u27ff\u{1f000}-\u{1ffff}]/gu,'').trim();
    const niv   = a.includes('❌') ? 'ROUGE' : a.includes('⚠️') ? 'AMBRE' : 'INFO';
    return alerte(clean, niv);
  });

  return [
    h1('1. Synthèse Exécutive'),
    para(
      `Le présent rapport consolide les résultats actuariels de provisionnement Non-Vie ` +
      `pour la branche ${data.lob_label}, arrêté au ${data.arrete}. ` +
      `Le triangle de développement ${n1.taille} a été analysé via quatre méthodes ` +
      `actuarielles (Chain Ladder, Mack, Bornhuetter-Ferguson, Cape Cod) ` +
      `et un Bootstrap stochastique (England & Verrall 2002).`,
      { size: 20, color: '333333' }
    ),
    ...vide(1),
    kpis,
    ...vide(1),

    h2('Points saillants'),
    ...alertesN2,
    alerte(
      `Best Estimate S2 = ${euro(be)} | Provision P90 = ${euro(p90)} | ` +
      `SCR provisions = ${euro(scr.scr_provisions)} (σ_EIOPA = ${pct(scr.sigma_eiopa)})`,
      statut
    ),
    alerte(
      `Méthode principale retenue : ${n2.methode_recommandee} | ` +
      `Variante CL : ${n2.methode_cl_retenue} | ` +
      `Statut hypothèses : ${n2.statut_global}`,
      n2.statut_global
    ),
  ];
}

// ── SECTION 2 : DONNÉES ET MÉTHODES ──────────────────────────────────────────
function sectionMethodes() {
  const cl   = n3.chain_ladder;
  const mack = n3.mack;
  const bf   = n3.bf;
  const cc   = n3.cape_cod;
  const boot = n3.bootstrap;
  const be   = n4.best_estimate;

  const elems = [
    h1('2. Provisionnement — Non-Vie'),
    h2('2.1 Méthodologie'),
    para(
      `Les provisions techniques sont estimées selon une approche multi-méthodes : ` +
      `Chain Ladder ${n3.methode_cl} pour l'estimation déterministe, ` +
      `méthode de Mack (1993) pour la quantification de l'incertitude de réserve, ` +
      `Bornhuetter-Ferguson (LR a priori = ${pct(bf.lr_apriori)}) ` +
      `et Cape Cod (LR estimé = ${pct(cc.lr_cape_cod)}) pour l'ancrage sur l'a priori, ` +
      `et un Bootstrap ODP (England & Verrall 2002, ${(boot.n_simulations||0).toLocaleString()} simulations) ` +
      `pour la distribution stochastique complète.`,
      { size: 20, color: '333333' }
    ),
    ...vide(1),

    h2('2.2 Résultats par méthode'),
  ];

  // Tableau résultats méthodes
  const label_map = {
    chain_ladder: 'Chain Ladder', mack: 'Mack 1993',
    bornhuetter_ferguson: 'Bornhuetter-Ferguson', cape_cod: 'Cape Cod'
  };
  const methodes = [
    { k: 'chain_ladder',         r: cl.reserve_totale,         extra: `méthode: ${n3.methode_cl}` },
    { k: 'mack',                 r: mack.reserve_best_estimate, extra: `σ=${euro(mack.sigma_total)} | CV=${pct(mack.cv_pct/100)}` },
    { k: 'bornhuetter_ferguson', r: bf.reserve_totale,          extra: `LR=${pct(bf.lr_apriori)} (${bf.source_lr})` },
    { k: 'cape_cod',             r: cc.reserve_totale,          extra: `LR_CC=${pct(cc.lr_cape_cod)}` },
  ];

  const inc = n4.methodes_incluses || [];
  const poids = n4.poids || {};

  const cw = [3600, 2200, 1800, 1426];
  const methodesTable = new Table({
    width: { size: 9026, type: WidthType.DXA },
    columnWidths: cw,
    rows: [
      new TableRow({ children: [
        cell([para('Méthode', { bold: true, color: BLANC, size: 18, align: AlignmentType.CENTER })],
             { width: cw[0], shading: { fill: NAVY, type: ShadingType.CLEAR } }),
        cell([para('Réserve IBNR', { bold: true, color: BLANC, size: 18, align: AlignmentType.CENTER })],
             { width: cw[1], shading: { fill: NAVY, type: ShadingType.CLEAR } }),
        cell([para('Statut BE', { bold: true, color: BLANC, size: 18, align: AlignmentType.CENTER })],
             { width: cw[2], shading: { fill: NAVY, type: ShadingType.CLEAR } }),
        cell([para('Poids BE', { bold: true, color: BLANC, size: 18, align: AlignmentType.CENTER })],
             { width: cw[3], shading: { fill: NAVY, type: ShadingType.CLEAR } }),
      ]}),
      ...methodes.map(m => {
        const isInc = inc.includes(m.k);
        return new TableRow({ children: [
          cell([
            para(label_map[m.k] || m.k, { bold: isInc, size: 19 }),
            para(m.extra, { size: 16, color: '666666' }),
          ], { width: cw[0] }),
          cell([para(euro(m.r), { bold: isInc, size: 19, align: AlignmentType.RIGHT })], { width: cw[1] }),
          cell([para(isInc ? 'Incluse' : 'Exclue', { bold: true, color: isInc ? VERT : ROUGE, size: 18, align: AlignmentType.CENTER })],
               { width: cw[2], shading: { fill: isInc ? 'EAF3DE' : 'FCEBEB', type: ShadingType.CLEAR } }),
          cell([para(isInc ? pct(poids[m.k]) : '—', { size: 18, align: AlignmentType.CENTER })], { width: cw[3] }),
        ]});
      }),
      // Ligne BE S2
      new TableRow({ children: [
        cell([para('BEST ESTIMATE S2 (Art. 77)', { bold: true, color: GOLD, size: 20 })],
             { width: cw[0], shading: { fill: NAVY, type: ShadingType.CLEAR } }),
        cell([para(euro(be), { bold: true, color: GOLD, size: 22, align: AlignmentType.RIGHT })],
             { width: cw[1], shading: { fill: NAVY, type: ShadingType.CLEAR } }),
        cell([para(statutTxt(n4.statut), { bold: true, color: GOLD, size: 18, align: AlignmentType.CENTER })],
             { width: cw[2], shading: { fill: NAVY, type: ShadingType.CLEAR } }),
        cell([para('100%', { color: GOLD, size: 18, align: AlignmentType.CENTER })],
             { width: cw[3], shading: { fill: NAVY, type: ShadingType.CLEAR } }),
      ]}),
    ],
  });
  elems.push(methodesTable);

  // Graphique convergence
  const gConv = loadImg('g5_convergence');
  if (gConv) {
    elems.push(...vide(1), h2('2.3 Convergence des méthodes'));
    elems.push(imgPara(gConv, 'Convergence méthodes'));
  }

  // Graphique IBNR
  const gIbnr = loadImg('g4_ibnr');
  if (gIbnr) {
    elems.push(...vide(1), h2('2.4 IBNR par année de survenance'));
    elems.push(imgPara(gIbnr, 'IBNR par année'));
  }

  // Cadences
  const gCad = loadImg('g2_cadences');
  if (gCad) {
    elems.push(...vide(1), h2('2.5 Courbes de développement'));
    elems.push(imgPara(gCad, 'Cadences cumulées', 8200, 3600));
  }

  // Bootstrap
  elems.push(...vide(1), h2('2.6 Distribution stochastique — Bootstrap ODP'));
  elems.push(
    tableKV([
      ['BE Bootstrap',         euro(boot.be_bootstrap)],
      ['Écart-type σ',         euro(boot.std_bootstrap)],
      ['CV Bootstrap',         pct(boot.cv_bootstrap)],
      ['IC 95% [inf ; sup]',   euro(boot.ic_95_inf) + ' — ' + euro(boot.ic_95_sup)],
      ['Percentile P90',       euro(boot.p90)],
      ['Percentile P99.5 SCR', euro(boot.p99_5)],
      ['Facteur sur-dispersion φ', num(boot.phi, 4)],
      ['Simulations',          (boot.n_simulations||0).toLocaleString()],
    ])
  );

  const gBoot = loadImg('g6_bootstrap');
  if (gBoot) elems.push(imgPara(gBoot, 'Distribution Bootstrap'));

  return elems;
}

// ── SECTION 3 : HYPOTHÈSES ────────────────────────────────────────────────────
function sectionHypotheses() {
  const h1r  = n2.h1_independance     || {};
  const h2r  = n2.h2_stabilite        || {};
  const h3r  = n2.h3_apriori_bf       || {};
  const h4r  = n2.h4_homosc_bootstrap || {};

  const elems = [
    h1('3. Validation des Hypothèses Actuarielles'),
    para(
      `Les 4 hypothèses de Mack (1993) conditionnent la validité des méthodes actuarielles. ` +
      `Leur validation est effectuée avant tout calcul de provisions.`,
      { size: 20, color: '333333' }
    ),
    ...vide(1),
  ];

  // Tableau synthèse H1-H4
  const cw = [3600, 1600, 1200, 2626];
  const hyps = [
    { lbl: 'H1 — Indépendance (Spearman)', h: h1r, detail: `corr_moy=${num(h1r.corr_moy, 2)} | ${h1r.n_colonnes_sig||0}/${h1r.n_colonnes_testees||0} sig.` },
    { lbl: 'H2 — Stabilité (CV + dérive)', h: h2r, detail: `CV=${pct(h2r.cv_moy)} | dérive=${pct(h2r.derive_moy)}` },
    { lbl: 'H3 — A priori BF',             h: h3r, detail: `LR=${pct(h3r.lr_apriori)} (${h3r.source||'—'})` },
    { lbl: 'H4 — Homoscédasticité Bootstrap', h: h4r, detail: `φ=${num(h4r.phi, 6)}` },
  ];

  const hTable = new Table({
    width: { size: 9026, type: WidthType.DXA },
    columnWidths: cw,
    rows: [
      new TableRow({ children: [
        cell([para('Hypothèse', { bold: true, color: BLANC, size: 18 })],
             { width: cw[0], shading: { fill: NAVY, type: ShadingType.CLEAR } }),
        cell([para('Statut', { bold: true, color: BLANC, size: 18, align: AlignmentType.CENTER })],
             { width: cw[1], shading: { fill: NAVY, type: ShadingType.CLEAR } }),
        cell([para('Score', { bold: true, color: BLANC, size: 18, align: AlignmentType.CENTER })],
             { width: cw[2], shading: { fill: NAVY, type: ShadingType.CLEAR } }),
        cell([para('Indicateurs clés', { bold: true, color: BLANC, size: 18 })],
             { width: cw[3], shading: { fill: NAVY, type: ShadingType.CLEAR } }),
      ]}),
      ...hyps.map(({lbl, h, detail}) => {
        const ok = h.ok;
        return new TableRow({ children: [
          cell([para(lbl, { bold: true, size: 19 })], { width: cw[0] }),
          cell([para(ok ? '✓ Validée' : '✗ Rejetée', { bold: true, color: ok ? VERT : ROUGE, size: 18, align: AlignmentType.CENTER })],
               { width: cw[1], shading: { fill: ok ? 'EAF3DE' : 'FCEBEB', type: ShadingType.CLEAR } }),
          cell([para(String(h.score||0) + '/100', { size: 18, align: AlignmentType.CENTER })], { width: cw[2] }),
          cell([para(detail, { size: 17, color: '444444' })], { width: cw[3] }),
        ]});
      }),
    ],
  });
  elems.push(hTable, ...vide(1));

  // Décision méthodologique
  elems.push(
    alerte(
      `Méthode recommandée : ${n2.methode_recommandee} — ${n2.raison_recommandation}`,
      n2.statut_global || 'AMBRE'
    ),
    alerte(
      `Variante CL retenue : ${n2.methode_cl_retenue} — ${n2.raison_cl}`,
      'INFO'
    ),
    ...vide(1),
  );

  // Graphiques hypothèses
  const gH1 = loadImg('g8_h1');
  if (gH1) { elems.push(h2('3.1 H1 — Corrélations Spearman')); elems.push(imgPara(gH1, 'H1 Indépendance')); }
  const gH2 = loadImg('g9_h2');
  if (gH2) { elems.push(h2('3.2 H2 — Stabilité des facteurs')); elems.push(imgPara(gH2, 'H2 Stabilité')); }
  const gH3 = loadImg('g10_h3');
  if (gH3) { elems.push(h2('3.3 H3 — Loss Ratio a priori')); elems.push(imgPara(gH3, 'H3 LR')); }

  return elems;
}

// ── SECTION 4 : BEST ESTIMATE S2 ─────────────────────────────────────────────
function sectionBestEstimate() {
  const be   = n4.best_estimate;
  const p75  = n4.reserve_p75;
  const p90  = n4.reserve_p90;
  const p995 = n4.reserve_p99_5;
  const sig  = n4.sigma_mack;
  const cv   = n4.cv_inter_methodes;
  const scr  = n4.scr || {};

  const elems = [
    h1('4. Best Estimate S2 et SCR Provisions'),
    h2('4.1 Best Estimate S2 (Art. 77)'),
    alerte(n4.message || '', n4.statut || 'AMBRE'),
    ...vide(1),
    tableKV([
      ['Best Estimate S2 (Art. 77)', euro(be), GOLD],
      ['Provision prudentielle P75', euro(p75)],
      ['Provision stress test P90',  euro(p90)],
      ['Provision extrême P99.5',    euro(p995)],
      ['Incertitude Mack (σ)',        euro(sig)],
      ['CV inter-méthodes',          pct(cv/100)],
    ]),
    ...vide(1),
    h2('4.2 SCR Provisions — Formule standard (Art. 105 S2)'),
    tableKV([
      ['SCR_prov = 3 × σ(LoB) × BE',   euro(scr.scr_provisions), ROUGE],
      ['Facteur σ(LoB) EIOPA',          pct(scr.sigma_eiopa)],
      ['Ratio SCR/BE',                  pct(scr.ratio_scr_be)],
      ['Branche (LoB)',                  scr.lob_label || '—'],
    ]),
    ...vide(1),
  ];

  // Graphique SCR donut
  const gScr = loadImg('g7_scr');
  if (gScr) { elems.push(imgPara(gScr, 'SCR donut')); elems.push(...vide(1)); }

  // Sensibilités
  elems.push(h2('4.3 Analyse de sensibilité'));
  const gSens = loadImg('g12_sensibilites');
  if (gSens) { elems.push(imgPara(gSens, 'Sensibilités')); }

  return elems;
}

// ── SECTION 5 : RECOMMANDATIONS ───────────────────────────────────────────────
function sectionRecos() {
  const statut = n4.statut || 'AMBRE';
  const be     = n4.best_estimate;
  const p90    = n4.reserve_p90;
  const scr    = (n4.scr || {}).scr_provisions;
  const jugement = (n4.jugement || '').split('\n').slice(0, 12);

  const recos = {
    VERT: [
      `Inscrire ${euro(be)} au bilan S2 (Art. 77 DAS).`,
      `Retenir ${euro(p90)} pour le calcul du SCR provisions (formule standard Art. 105).`,
      `SCR provisions calculé : ${euro(scr)}.`,
      `Documenter la méthodologie dans le rapport actuaire désigné.`,
      `Archiver ce rapport et l'audit trail JSON (réf. ${data.audit_id || '—'}).`,
      `Revue trimestrielle recommandée.`,
    ],
    AMBRE: [
      `BE de ${euro(be)} utilisable sous réserve de validation actuaire désigné.`,
      `Valider avant signature du bilan S2.`,
      `Envisager provision prudentielle ${euro(p90)} si direction financière prudente.`,
      `SCR indicatif : ${euro(scr)}.`,
      `Réviser les hypothèses à la prochaine clôture.`,
    ],
    ROUGE: [
      `NE PAS inscrire ce BE au bilan sans correction actuarielle.`,
      `Consulter l'actuaire désigné impérativement.`,
      `Vérifier la qualité des données source.`,
      `Analyser la cause de la divergence inter-méthodes.`,
      `Provision conservatrice : ${euro(n4.reserve_p99_5)}.`,
    ],
  }[statut] || [];

  return [
    h1('5. Recommandations et Conclusions'),
    alerte(
      statut === 'VERT' ? 'AVIS FAVORABLE — Les méthodes convergent. BE fiable pour inscription au bilan S2.' :
      statut === 'AMBRE' ? 'AVIS AVEC RÉSERVES — Divergence modérée. Validation actuaire désigné requise.' :
      'AVIS DÉFAVORABLE — Divergence importante. BE non utilisable en l\'état.',
      statut
    ),
    ...vide(1),
    h2('5.1 Recommandations opérationnelles'),
    ...recos.map((r, i) => new Paragraph({
      spacing: { before: 30, after: 30 },
      numbering: { reference: 'numbers', level: 0 },
      children: [new TextRun({ text: r, font: 'Arial', size: 20 })],
    })),
    ...vide(1),
    h2('5.2 Jugement actuariel'),
    ...jugement.filter(l => l.trim()).slice(0, 8).map(l =>
      para(l.replace(/[✅❌⚠️]/gu, '').trim(), { size: 18, color: '333333' })
    ),
    ...vide(2),

    // Bloc signature
    new Table({
      width: { size: 9026, type: WidthType.DXA },
      columnWidths: [4500, 4526],
      rows: [new TableRow({ children: [
        new TableCell({
          borders: { top: { style: BorderStyle.SINGLE, size: 6, color: NAVY } },
          width: { size: 4500, type: WidthType.DXA },
          margins: MARGINS,
          children: [
            para(`Produit par ActuarIA v5.0`, { size: 18, color: '666666' }),
            para(`Réf. : ${data.audit_id || '—'}`, { size: 16, color: '888888' }),
            para(`Date : ${data.date_rapport}`, { size: 16, color: '888888' }),
          ],
        }),
        new TableCell({
          borders: { top: { style: BorderStyle.SINGLE, size: 6, color: NAVY } },
          width: { size: 4526, type: WidthType.DXA },
          margins: MARGINS,
          children: [
            para("Validé par l'actuaire désigné :", { bold: true, color: NAVY, size: 19 }),
            para('', { before: 80 }),
            para('Signature : ___________________________', { size: 19 }),
            para('Date :      ___________________________', { size: 19 }),
          ],
        }),
      ]})],
    }),
  ];
}

// ── DOCUMENT PRINCIPAL ────────────────────────────────────────────────────────
async function main() {
  const children = [
    ...pageDeGarde(),
    new Paragraph({ children: [new TextRun({ break: 1 })] }),  // saut de page
    ...sectionSynthese(),
    new Paragraph({ children: [new TextRun({ break: 1 })] }),
    ...sectionMethodes(),
    new Paragraph({ children: [new TextRun({ break: 1 })] }),
    ...sectionHypotheses(),
    new Paragraph({ children: [new TextRun({ break: 1 })] }),
    ...sectionBestEstimate(),
    new Paragraph({ children: [new TextRun({ break: 1 })] }),
    ...sectionRecos(),
  ];

  const doc = new Document({
    styles: {
      default: { document: { run: { font: 'Arial', size: 20 } } },
      paragraphStyles: [
        { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
          run:       { size: 26, bold: true, font: 'Arial', color: NAVY },
          paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 0 } },
        { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
          run:       { size: 22, bold: true, font: 'Arial', color: NAVY },
          paragraph: { spacing: { before: 120, after: 60 }, outlineLevel: 1 } },
      ],
    },
    numbering: {
      config: [
        { reference: 'bullets',
          levels: [{ level: 0, format: LevelFormat.BULLET, text: '\u2022', alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
        { reference: 'numbers',
          levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      ],
    },
    sections: [{
      properties: {
        page: {
          size:   { width: 11906, height: 16838 },
          margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 },
        },
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
              spacing:  { before: 0, after: 80 },
              border:   { bottom: { style: BorderStyle.SINGLE, size: 4, color: GOLD, space: 2 } },
              children: [
                new TextRun({ text: `ActuarIA \u2014 Rapport Actuariel ${data.arrete}`, font: 'Arial', size: 16, bold: true, color: NAVY }),
                new TextRun({ text: '\t', font: 'Arial', size: 16 }),
                new TextRun({ text: 'CONFIDENTIEL', font: 'Arial', size: 16, bold: true, color: ROUGE }),
              ],
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
              spacing:  { before: 80, after: 0 },
              border:   { top: { style: BorderStyle.SINGLE, size: 4, color: GRIS2, space: 2 } },
              children: [
                new TextRun({ text: `Arrêté au ${data.arrete} \u00b7 Plateforme ActuarIA v5.0`, font: 'Arial', size: 16, color: '888888' }),
                new TextRun({ text: '\tPage ', font: 'Arial', size: 16, color: '888888' }),
                new TextRun({ children: [PageNumber.CURRENT], font: 'Arial', size: 16, color: '888888' }),
              ],
            }),
          ],
        }),
      },
      children,
    }],
  });

  const buf = await Packer.toBuffer(doc);
  fs.writeFileSync(outPath, buf);
  console.log('OK:' + buf.length);
}

main().catch(e => { console.error('ERR:' + e.message); process.exit(1); });
"""


# =============================================================================
#  CORRECTION BUG PYTHON-DOCX ZOOM (si utilisé ailleurs)
# =============================================================================

def _fix_zoom(word_bytes: bytes) -> bytes:
    """Corrige le bug w:zoom sans w:percent (python-docx)."""
    try:
        buf_in  = io.BytesIO(word_bytes)
        buf_out = io.BytesIO()
        with zipfile.ZipFile(buf_in, 'r') as zin, \
             zipfile.ZipFile(buf_out, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == 'word/settings.xml':
                    xml  = data.decode('utf-8')
                    xml  = re.sub(
                        r'(<w:zoom\b(?![^>]*w:percent)[^>]*)(/>)',
                        r'\1 w:percent="100"\2', xml
                    )
                    data = xml.encode('utf-8')
                zout.writestr(item, data)
        return buf_out.getvalue()
    except Exception:
        return word_bytes


# =============================================================================
#  FONCTIONS PUBLIQUES
# =============================================================================

def export_word(
    n1:          Dict,
    n2:          Dict,
    n3:          Dict,
    n4:          Dict,
    commentaire: str,
    graphiques:  Optional[Dict] = None,
    ref_client:  str = '',
    arrete:      str = '',
    audit_id:    str = '',
    lob_label:   str = '',
) -> bytes:
    """
    Génère le rapport Word (.docx) professionnel via Node.js (docx@9.6.1).

    Parameters
    ----------
    n1..n4       : dicts des niveaux N1 à N4
    commentaire  : narration textuelle (depuis n5_commentaire.py)
    graphiques   : dict {nom: go.Figure} (optionnel — exportés en PNG)
    ref_client   : référence client
    arrete       : libellé arrêté
    audit_id     : identifiant audit trail
    lob_label    : libellé branche

    Returns
    -------
    bytes : fichier .docx prêt pour st.download_button()
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # 1. Exporter les graphiques en PNG
            img_dir = str(tmpdir / 'imgs')
            os.makedirs(img_dir)
            if graphiques:
                pngs = exporter_graphiques_png(graphiques)
                for nom, png in pngs.items():
                    (Path(img_dir) / f"{nom}.png").write_bytes(png)
                logger.info(f"Graphiques PNG exportés : {len(pngs)}")

            # 2. Écrire le JSON de données
            data = _build_report_data(
                n1, n2, n3, n4, commentaire,
                ref_client, arrete, audit_id, lob_label
            )
            json_path = str(tmpdir / 'data.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, default=str)

            # 3. Écrire le script Node.js
            js_path  = str(tmpdir / 'gen.js')
            out_path = str(tmpdir / 'rapport.docx')
            with open(js_path, 'w', encoding='utf-8') as f:
                f.write(_NODE_SCRIPT)

            # 4. Exécuter le script Node.js
            result = subprocess.run(
                ['node', js_path, json_path, out_path, img_dir],
                capture_output=True, text=True, timeout=120,
                cwd=str(tmpdir),
            )
            if result.returncode != 0:
                logger.error(f"Node.js échoué : {result.stderr[:500]}")
                return b''

            # 5. Lire le .docx généré
            word_bytes = Path(out_path).read_bytes()
            logger.info(f"Word généré : {len(word_bytes):,} bytes")
            return word_bytes

    except Exception as e:
        logger.error(f"export_word échoué : {e}", exc_info=True)
        return b''


def export_pdf(word_bytes: bytes) -> bytes:
    """
    Convertit le Word en PDF via LibreOffice.

    Parameters
    ----------
    word_bytes : bytes du fichier .docx

    Returns
    -------
    bytes : fichier .pdf, ou b'' si échec
    """
    if not word_bytes:
        return b''

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir    = Path(tmpdir)
            docx_path = tmpdir / 'rapport.docx'
            docx_path.write_bytes(word_bytes)

            # Convertir via LibreOffice (soffice)
            skill_soffice = Path('/mnt/skills/public/docx/scripts/office/soffice.py')
            cmd = ['python3', str(skill_soffice),
                   '--headless', '--convert-to', 'pdf',
                   '--outdir', str(tmpdir),
                   str(docx_path)]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                logger.warning(f"LibreOffice PDF échoué : {result.stderr[:200]}")
                return b''

            pdf_path = tmpdir / 'rapport.pdf'
            if pdf_path.exists():
                pdf_bytes = pdf_path.read_bytes()
                logger.info(f"PDF généré : {len(pdf_bytes):,} bytes")
                return pdf_bytes

            logger.warning("PDF non trouvé après conversion")
            return b''

    except Exception as e:
        logger.error(f"export_pdf échoué : {e}", exc_info=True)
        return b''
