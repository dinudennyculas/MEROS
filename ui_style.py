"""MEROS UI helpers: the Sovereign Bullion & Carbon Ledger look, number formatters, HTML builders and chart styling.

No analysis logic lives here. app.py must call st.set_page_config() first, then inject_css()."""
from __future__ import annotations

import html
import inspect

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from meros_assumptions import APP_NAME, CREATOR, DISCLAIMER_BADGE, DISCLAIMER_FULL

# --------------------------------------------------------------------------------------
# Palette and shared labels
# --------------------------------------------------------------------------------------
GOLD, JADE, COPPER, CYAN = "#E5A93C", "#10B981", "#F97316", "#38BDF8"
CRIMSON, VIOLET, SLATE, CHAMPAGNE, PEWTER = "#F43F5E", "#A855F7", "#64748B", "#F4F1EA", "#8E929F"
COPPER_SOFT = "#FDBA74"
RECEIPT_COLORS = [COPPER, COPPER_SOFT, CYAN, SLATE, VIOLET, CRIMSON, JADE, CHAMPAGNE]
RECEIPT_NAMES = ["Materials & Stock-in-Trade", "External Vendors & Operations", "Workforce Wages & Benefits",
                 "Depreciation (Asset Wear)", "Lenders (Interest)", "Government Tax", "Shareholder Dividends", "Retained Profit"]
WF_FULL = ["Total Income", "Materials", "External Vendors", "Workforce", "Depreciation", "Lenders",
           "Government Tax", "Dividends", "Retained Profit"]
WF_TICKS = ["Total<br>Income", "Materials", "Vendors", "Workforce", "Deprec.", "Lenders", "Govt<br>Tax", "Dividends", "Retained<br>Profit"]
STAKE_SHORT = ["Workforce", "Lenders", "Government", "Shareholder Dividends", "Entity Retention"]
STAKE_BR = ["Workforce", "Lenders", "Government", "Shareholder<br>Dividends", "Entity<br>Retention"]
STAKE_COLORS = [CYAN, VIOLET, CRIMSON, JADE, CHAMPAGNE]
SEV_TONE = {"positive": "t-green", "warning": "t-amber", "danger": "t-red", "info": "t-cyan"}
HEALTH_TONE = {"alert": "t-red", "warn": "t-amber", "info": "t-cyan", "ok": "t-green"}
HEALTH_TXT = {"alert": "ALERT", "warn": "WARNING", "info": "NOTE", "ok": "OK"}
PROV_TONE = {"Reported": "t-green", "Derived": "t-cyan", "Balancing": "t-violet", "Not reported": "t-red",
             "Your edit": "t-gold", "Re-balanced": "t-violet"}
STATE_TONE = {"ALWAYS ON": "t-cyan", "ACTIVE": "t-amber", "NOT TRIGGERED": "t-green", "OTHER SOURCE": "t-mute"}
GRID = "rgba(244,241,234,0.06)"
LEG_BELOW = dict(orientation="h", yanchor="top", y=-0.26, xanchor="center", x=0.5, font=dict(size=10))

RECEIPT_STAMP = f'<div class="receipt-stamp">VERIFIED LEDGER · <b>{APP_NAME}</b> ENGINE BY <b>{CREATOR.upper()}</b></div>'
COLOPHON = (f'<div class="colophon"><span><b>{APP_NAME}</b> (<em>μέρος</em>) — Corporate Value-Added &amp; Stakeholder Economics Tool</span>'
            f'<span class="by">Architected &amp; Engineered by <b>{CREATOR}</b> · Strategic Finance</span></div>')
ARCHITECT_HTML = (f'<div class="architect"><small>ARCHITECTED &amp; ENGINEERED BY</small><strong>{CREATOR}</strong>'
                  '<span>Strategic Finance &amp; Quantitative Engineering</span></div>')
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_PLOTLY_HAS_WIDTH = "width" in inspect.signature(st.plotly_chart).parameters
DL_KW = {"width": "stretch"} if "width" in inspect.signature(st.download_button).parameters else {"use_container_width": True}
_SHOW_NOTES = True


def set_show_notes(flag: bool) -> None:
    """Turn the plain-English notes under the KPI cards on or off for this run."""
    global _SHOW_NOTES
    _SHOW_NOTES = bool(flag)


# --------------------------------------------------------------------------------------
# CSS
# --------------------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');
.stApp{background:radial-gradient(ellipse 80% 35% at 50% -10%,rgba(229,169,60,.10),transparent),#0A0A0C;font-family:'Plus Jakarta Sans',sans-serif;color:#F4F1EA;}
#MainMenu,footer{visibility:hidden;}
.block-container{padding-top:4.8rem;padding-bottom:5.5rem;max-width:1440px;}
section[data-testid="stSidebar"]{background:#111215;border-right:1px solid rgba(244,241,234,.08);}
.brand-title{font-family:'Plus Jakarta Sans',sans-serif;font-weight:800;font-size:1.5rem;letter-spacing:.02em;color:#F4F1EA;}
.brand-title em,.mast-etym em,.section-h em,.hero-title em{font-family:'Instrument Serif',serif;font-style:italic;font-weight:400;color:#E5A93C;}
.brand-sub{font-size:.76rem;color:#8E929F;margin-bottom:1rem;}
.mast{margin-bottom:1.1rem;}
.pill{display:inline-flex;align-items:center;font-family:'JetBrains Mono',monospace;font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:.28rem .8rem;border-radius:999px;color:#1A1204;background:linear-gradient(135deg,#F2C35B,#E5A93C 55%,#B9791B);}
.pill i{width:6px;height:6px;border-radius:50%;background:#1A1204;display:inline-block;margin-right:.5rem;}
.pill.ghost{margin-left:.5rem;color:#E5A93C;background:rgba(229,169,60,.08);border:1px solid rgba(229,169,60,.4);}
.mast-title{font-family:'Plus Jakarta Sans',sans-serif;font-weight:800;font-size:3.4rem;line-height:1.02;letter-spacing:-.02em;margin:.7rem 0 .25rem 0;color:#F4F1EA;}
.mast-etym{font-size:1.05rem;color:#C9C6BE;margin-bottom:.2rem;}
.mast-etym em{font-size:1.35rem;}
.mast-sub{color:#8E929F;font-size:.9rem;margin-bottom:.9rem;}
.mast-rule{height:1px;background:linear-gradient(90deg,rgba(229,169,60,.7),rgba(244,241,234,.1) 45%,transparent);}
.hero{padding:1.6rem 0 .6rem 0;}
.hero-title{font-family:'Plus Jakarta Sans',sans-serif;font-weight:800;font-size:2.6rem;line-height:1.1;letter-spacing:-.02em;color:#F4F1EA;margin:.6rem 0 .5rem 0;}
.hero-title em{font-size:3rem;}
.hero-sub{color:#C9C6BE;font-size:1rem;line-height:1.7;max-width:72ch;margin-bottom:1.2rem;}
.step-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.8rem;margin:.6rem 0 1.2rem 0;}
@media(max-width:900px){.step-grid{grid-template-columns:minmax(0,1fr);}}
.step{background:#15171C;border:1px solid rgba(244,241,234,.08);border-top:1px solid rgba(229,169,60,.5);border-radius:10px;padding:1rem 1.1rem;}
.step-n{font-family:'Instrument Serif',serif;font-style:italic;font-size:2rem;color:#E5A93C;line-height:1;}
.step b{display:block;margin:.3rem 0 .25rem 0;font-size:.95rem;}
.step span{display:block;font-size:.8rem;line-height:1.6;color:#A8ABB6;}
.guide{background:rgba(229,169,60,.05);border:1px solid rgba(229,169,60,.28);border-left:3px solid #E5A93C;border-radius:8px;padding:1rem 1.2rem;margin:.4rem 0 1rem 0;}
.guide h4{margin:0 0 .6rem 0;font-size:1rem;color:#F4F1EA;}
.guide ol{margin:0 0 .8rem 1.1rem;padding:0;}
.guide li{font-size:.84rem;line-height:1.65;color:#C9C6BE;margin-bottom:.45rem;}
.guide li b{color:#F4F1EA;}
.guide .note{font-size:.72rem;color:#8E929F;margin-top:.5rem;}
.btn{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:.7rem;font-weight:700;letter-spacing:.06em;padding:.45rem .9rem;margin:0 .5rem .4rem 0;border-radius:6px;border:1px solid rgba(229,169,60,.6);color:#E5A93C!important;text-decoration:none!important;background:rgba(229,169,60,.08);}
.btn:hover{background:rgba(229,169,60,.18);}
.notice{background:rgba(229,169,60,.06);border:1px solid rgba(229,169,60,.28);border-left:3px solid #E5A93C;border-radius:8px;padding:.8rem 1rem;margin:.2rem 0 1rem 0;font-size:.78rem;line-height:1.65;color:#C9C6BE;}
.notice b{color:#E5A93C;letter-spacing:.1em;font-size:.66rem;margin-right:.4rem;}
.notice.alert{background:rgba(244,63,94,.07);border-color:rgba(244,63,94,.35);border-left-color:#F43F5E;}
.notice.alert b{color:#F43F5E;}
.summary{background:rgba(244,241,234,.035);border:1px solid rgba(244,241,234,.1);border-left:3px solid #38BDF8;border-radius:8px;padding:.85rem 1.1rem;margin:.2rem 0 1rem 0;font-size:.88rem;line-height:1.7;color:#E4E0D6;}
.summary b{color:#38BDF8;letter-spacing:.12em;font-size:.64rem;display:block;margin-bottom:.3rem;}
.health-strip{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem;margin:.1rem 0 1rem 0;font-size:.72rem;color:#8E929F;}
.health-strip b{letter-spacing:.12em;font-size:.64rem;color:#C9C6BE;margin-right:.3rem;}
.hc{border:1px solid rgba(244,241,234,.08);border-left:3px solid var(--c);background:#15171C;border-radius:8px;padding:.65rem .9rem;margin-bottom:.5rem;font-size:.8rem;line-height:1.6;color:#C9C6BE;}
.hc b{color:var(--c);letter-spacing:.1em;font-size:.64rem;margin-right:.5rem;}
.hc span{color:#F4F1EA;font-weight:600;}
.dl-card{border:1px solid rgba(229,169,60,.3);border-top:1px solid rgba(229,169,60,.6);background:linear-gradient(160deg,rgba(229,169,60,.09),rgba(21,23,28,.92));border-radius:10px;padding:.85rem 1.1rem;font-size:.8rem;line-height:1.6;color:#C9C6BE;margin-bottom:.5rem;}
.dl-card b{color:#E5A93C;letter-spacing:.1em;font-size:.66rem;display:block;margin-bottom:.2rem;}
.glass-card,.kpi-card,.diag-card{background:#15171C;border:1px solid rgba(244,241,234,.08);border-top:1px solid rgba(244,241,234,.18);border-radius:10px;padding:1.2rem;transition:transform 220ms cubic-bezier(0.22,1,0.36,1),border-color 220ms ease,box-shadow 220ms ease;}
.glass-card:hover,.kpi-card:hover,.diag-card:hover{transform:translateY(-2px);border-color:rgba(229,169,60,.35);box-shadow:0 12px 28px -8px rgba(0,0,0,.65);}
.t-gold,.t-blue{--c:#E5A93C;--bg:rgba(229,169,60,.12);}.t-green{--c:#10B981;--bg:rgba(16,185,129,.12);}
.t-amber{--c:#F59E0B;--bg:rgba(245,158,11,.12);}.t-red{--c:#F43F5E;--bg:rgba(244,63,94,.12);}
.t-cyan{--c:#38BDF8;--bg:rgba(56,189,248,.12);}.t-violet{--c:#A855F7;--bg:rgba(168,85,247,.12);}
.t-mute{--c:#8E929F;--bg:rgba(142,146,159,.10);}
.kpi-grid{display:grid;gap:.7rem;align-items:stretch;margin-bottom:1rem;}
.kpi-grid.n5{grid-template-columns:repeat(5,minmax(0,1fr));}
.kpi-grid.n4{grid-template-columns:repeat(4,minmax(0,1fr));}
.kpi-grid.n3{grid-template-columns:repeat(3,minmax(0,1fr));}
@media(max-width:1180px){.kpi-grid.n5,.kpi-grid.n4,.kpi-grid.n3{grid-template-columns:repeat(2,minmax(0,1fr));}}
@media(max-width:760px){.kpi-grid.n5,.kpi-grid.n4,.kpi-grid.n3,.diag-grid{grid-template-columns:minmax(0,1fr);}}
.kpi-card{position:relative;overflow:hidden;min-height:168px;height:100%;display:flex;flex-direction:column;justify-content:space-between;gap:.25rem;}
.kpi-card::before{content:"";position:absolute;top:0;left:0;width:44px;height:2px;background:var(--c);}
.kpi-card .kpi-badge{align-self:flex-start;}
.kpi-label{font-size:.7rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#8E929F;}
.kpi-value{font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-weight:700;font-size:1.3rem;margin:.5rem 0 .15rem 0;color:#F4F1EA;word-break:break-word;}
.kpi-sub{font-size:.74rem;color:#8E929F;margin-bottom:.6rem;min-height:1.1rem;}
.kpi-note{font-size:.7rem;line-height:1.5;color:#A8ABB6;border-top:1px dotted rgba(244,241,234,.16);padding-top:.5rem;margin-top:.55rem;}
.kpi-badge,.diag-pill{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:.66rem;font-weight:700;padding:.2rem .55rem;border-radius:4px;color:var(--c);background:var(--bg);border:1px solid var(--c);}
.diag-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem;margin-bottom:1rem;}
.diag-grid .diag-card{margin-bottom:0;}
.section-h{font-family:'Plus Jakarta Sans',sans-serif;font-weight:700;font-size:1.55rem;letter-spacing:-.01em;margin:.5rem 0 .1rem 0;color:#F4F1EA;}
.section-h em{font-size:1.75rem;}
.section-sub{color:#8E929F;font-size:.86rem;margin-bottom:.9rem;max-width:78ch;}
.receipt{font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;background:#141519;border:1px solid rgba(244,241,234,.08);border-top:3px double rgba(244,241,234,.3);border-bottom:3px double rgba(244,241,234,.3);border-radius:2px;padding:1.2rem 1.3rem;margin-bottom:1rem;}
.receipt-head{text-align:center;font-weight:700;letter-spacing:.2em;font-size:.82rem;color:#F4F1EA;}
.receipt-meta{text-align:center;font-size:.68rem;color:#8E929F;margin:.25rem 0 .9rem 0;}
.receipt-row{display:flex;justify-content:space-between;gap:.8rem;padding:.42rem 0;border-bottom:1px dotted rgba(244,241,234,.16);font-size:.8rem;}
.receipt-row .amt{font-weight:700;white-space:nowrap;}
.receipt-total{display:flex;justify-content:space-between;padding:.65rem .7rem;margin-top:.6rem;font-weight:700;font-size:.92rem;background:#F4F1EA;color:#0A0A0C;border-radius:2px;}
.receipt-stamp{margin-top:.9rem;padding-top:.6rem;border-top:1px dotted rgba(244,241,234,.16);text-align:center;font-size:.56rem;letter-spacing:.14em;text-transform:uppercase;color:#8E929F;}
.receipt-stamp b{color:#E5A93C;font-weight:700;}
.architect{margin-top:1.6rem;padding:.95rem 1rem;border-radius:10px;background:linear-gradient(160deg,rgba(229,169,60,.12),rgba(21,23,28,.92));border:1px solid rgba(229,169,60,.28);border-top:1px solid rgba(229,169,60,.6);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);}
.architect small{display:block;font-family:'JetBrains Mono',monospace;font-size:.56rem;font-weight:700;letter-spacing:.2em;color:#E5A93C;}
.architect strong{display:block;font-family:'Instrument Serif',serif;font-style:italic;font-weight:400;font-size:1.6rem;line-height:1.1;color:#F4F1EA;margin:.3rem 0 .25rem 0;}
.architect span{display:block;font-size:.7rem;color:#8E929F;}
.colophon{display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap;margin-top:2.6rem;padding:1rem 0 .3rem 0;border-top:1px solid #B9791B;font-size:.72rem;color:#8E929F;}
.colophon b{color:#F4F1EA;font-weight:700;}
.colophon em{font-family:'Instrument Serif',serif;font-style:italic;font-size:.95rem;color:#E5A93C;}
.colophon .by b{color:#E5A93C;}
.disc-wrap{position:fixed;right:14px;bottom:12px;z-index:1000;}
.disc{background:rgba(17,18,21,.93);border:1px solid rgba(229,169,60,.38);border-radius:8px;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);max-width:min(380px,calc(100vw - 28px));}
.disc summary{cursor:pointer;padding:.38rem .7rem;font-size:.62rem;line-height:1.3;color:#A8ABB6;list-style:none;}
.disc summary::-webkit-details-marker{display:none;}
.disc summary:hover{color:#E5A93C;}
.disc[open] .disc-body{position:absolute;right:0;bottom:calc(100% + 6px);width:min(400px,calc(100vw - 28px));background:#15171C;border:1px solid rgba(229,169,60,.4);border-radius:8px;padding:.85rem 1rem;font-size:.72rem;line-height:1.6;color:#C9C6BE;box-shadow:0 14px 30px -8px rgba(0,0,0,.8);}
.disc-body b{color:#E5A93C;letter-spacing:.1em;font-size:.62rem;display:block;margin-bottom:.35rem;}
@media(max-width:760px){.disc summary{font-size:.56rem;padding:.3rem .5rem;}}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:.5rem;}
.diag-card{border-left:3px solid var(--c);min-height:178px;margin-bottom:1rem;}
.diag-head{display:flex;justify-content:space-between;align-items:center;gap:.6rem;margin-bottom:.6rem;}
.diag-title{font-weight:700;font-size:1rem;}
.diag-text{font-size:.86rem;line-height:1.6;color:#C9C6BE;}
.vas-table{width:100%;border-collapse:collapse;font-size:.83rem;}
.vas-table th{font-size:.64rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#8E929F;text-align:left;padding:.6rem .6rem;border-bottom:1px solid rgba(244,241,234,.22);}
.vas-table th.num,.vas-table td.num{text-align:right;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;white-space:nowrap;}
.vas-table td{padding:.5rem .6rem;border-bottom:1px solid rgba(244,241,234,.06);}
.vas-table tr:hover td{background:rgba(244,241,234,.03);}
.vas-table tr.section td{font-weight:700;font-size:.68rem;letter-spacing:.14em;text-transform:uppercase;color:#E5A93C;background:rgba(229,169,60,.07);}
.vas-table tr.subtotal td{font-weight:600;border-top:1px solid rgba(244,241,234,.22);}
.vas-table tr.total td{font-weight:700;border-top:1px solid rgba(244,241,234,.3);border-bottom:3px double rgba(244,241,234,.4);background:rgba(244,241,234,.02);}
.vas-table tr.memo td{font-style:italic;color:#8E929F;font-size:.78rem;}
.reg-table td{vertical-align:top;font-size:.76rem;line-height:1.55;}
.reg-table td.rid{font-family:'JetBrains Mono',monospace;color:#E5A93C;font-weight:700;white-space:nowrap;}
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid rgba(244,241,234,.1);}
.stTabs [data-baseweb="tab"]{background:transparent;border-radius:6px 6px 0 0;padding:.5rem 1rem;font-weight:600;color:#8E929F;}
.stTabs [aria-selected="true"]{color:#E5A93C;}
.stTabs [data-baseweb="tab-highlight"]{background:#E5A93C;}
div[data-testid="stVerticalBlockBorderWrapper"]{background:#15171C;border:1px solid rgba(244,241,234,.08)!important;border-top:1px solid rgba(244,241,234,.18)!important;border-radius:10px;}
</style>
"""


def inject_css() -> None:
    """Call once per run, right after st.set_page_config()."""
    st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------------------
# Number formatting (Indian digit grouping, n/a for anything missing)
# --------------------------------------------------------------------------------------
def _indian(n: float, d: int = 2) -> str:
    ip, _, fp = f"{abs(n):.{d}f}".partition(".")
    if len(ip) > 3:
        head, tail, parts = ip[:-3], ip[-3:], []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        ip = ",".join(parts + [tail])
    return ip + ("." + fp if d > 0 else "")


def _ok(v: object) -> bool:
    try:
        return v is not None and bool(np.isfinite(float(v)))
    except (TypeError, ValueError):
        return False


def _money(v: float, d: int, suffix: str) -> str:
    if not _ok(v):
        return "n/a"
    v = float(v)
    body = _indian(v, d)
    neg = v < 0 and float(body.replace(",", "")) > 0
    return f"{'-' if neg else ''}₹{body}{suffix}"


def fmt_cr(v: float, d: int = 2) -> str: return _money(v, d, " Cr")
def fmt_lakh(v: float, d: int = 2) -> str: return _money(v, d, " L")
def fmt_rs(v: float) -> str: return _money(v, 2, "")


def sgn_cr(v: float, d: int = 2) -> str:
    return "n/a" if not _ok(v) else ("+" if float(v) >= 0 else "") + fmt_cr(v, d)


def fmt_pct(v: float, d: int = 1, signed: bool = False) -> str:
    if not _ok(v):
        return "n/a"
    return f"{float(v):+.{d}f}%" if signed else f"{float(v):.{d}f}%"


def fmt_x(v: float, d: int = 2) -> str:
    return "n/a" if not _ok(v) else f"{float(v):.{d}f}x"


def fmt_int(v: float) -> str:
    return "n/a" if not _ok(v) else f"{int(round(float(v))):,}"


def fmt_unit(v: float, unit: str) -> str:
    """Format by unit code: cr, lakh, rs, pct, x, icr (999 = no interest), pp (plain 2 decimals), int, text."""
    if unit == "text":
        return "n/a" if v is None or (isinstance(v, float) and not np.isfinite(v)) else str(v)
    if not _ok(v):
        return "n/a"
    f = float(v)
    if unit == "cr":
        return fmt_cr(f)
    if unit == "lakh":
        return fmt_lakh(f)
    if unit == "rs":
        return fmt_rs(f)
    if unit == "pct":
        return fmt_pct(f, 2)
    if unit == "icr":
        return "∞" if f >= 999.0 else f"{f:.2f}x"
    if unit == "pp":
        return f"{f:.2f}"
    if unit == "int":
        return fmt_int(f)
    return f"{f:.2f}x"


# --------------------------------------------------------------------------------------
# HTML builders
# --------------------------------------------------------------------------------------
def esc(s: object) -> str:
    return html.escape(str(s))


def chip(text: str, tone: str = "t-gold") -> str:
    return f'<span class="kpi-badge {tone}">{esc(text)}</span>'


def kpi_card(label: str, value: str, sub: str, badge: str, tone: str, note: str = "") -> str:
    extra = f'<div class="kpi-note">{esc(note)}</div>' if (_SHOW_NOTES and note) else ""
    return (f'<div class="kpi-card {tone}"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>'
            f'<div class="kpi-sub">{sub}</div><span class="kpi-badge">{badge}</span>{extra}</div>')


def kpi_grid(cards: list[str]) -> str:
    return f'<div class="kpi-grid n{len(cards)}">' + "".join(cards) + "</div>"


def render_table(headers: list[str], rows: list[tuple[str, str, list[str]]]) -> str:
    """rows: (kind, label, cells). kind: row | subtotal | total | memo | section. Cells are inserted as HTML (escape them yourself)."""
    head = "".join(f'<th{" class=num" if i else ""}>{esc(h)}</th>' for i, h in enumerate(headers))
    body = []
    for kind, label, vals in rows:
        if kind == "section":
            body.append(f'<tr class="section"><td colspan="{len(headers)}">{esc(label)}</td></tr>')
        else:
            tds = "".join(f'<td class="num">{v}</td>' for v in vals)
            body.append(f'<tr class="{kind}"><td>{esc(label)}</td>{tds}</tr>')
    return ('<div class="glass-card" style="overflow-x:auto;padding:.6rem .9rem;">'
            f'<table class="vas-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def diag_cards_html(diagnostics: list[dict]) -> str:
    cards = []
    for c in diagnostics:
        tone = SEV_TONE.get(c.get("severity", "info"), "t-cyan")
        cards.append(f'<div class="diag-card {tone}"><div class="diag-head"><span class="diag-title">{esc(c["title"])}</span>'
                     f'<span class="diag-pill">{esc(c["badge_text"])}</span></div><div class="diag-text">{esc(c["narrative"])}</div></div>')
    return '<div class="diag-grid">' + "".join(cards) + "</div>"


def receipt_row(name: str, color: str, amount: str, delta_html: str = "") -> str:
    return (f'<div class="receipt-row"><span><span class="dot" style="background:{color}"></span>{esc(name)}</span>'
            f'<span class="amt">{amount}{delta_html}</span></div>')


def receipt_html(title: str, meta_html: str, rows_html: str, total_label: str, total_value: str, ok: bool, stamp: bool = True) -> str:
    return (f'<div class="receipt"><div class="receipt-head">{esc(title)}</div><div class="receipt-meta">{meta_html}</div>{rows_html}'
            f'<div class="receipt-total"><span>{esc(total_label)}</span><span>{total_value} {"✅" if ok else "⚠️"}</span></div>'
            + (RECEIPT_STAMP if stamp else "") + "</div>")


def notice_html(lines: list[str], head: str = "NOTE", alert: bool = False) -> str:
    body = "<br>".join(esc(x) for x in lines)
    return f'<div class="{"notice alert" if alert else "notice"}"><b>{esc(head)}</b>{body}</div>'


def summary_html(text: str) -> str:
    return f'<div class="summary"><b>IN PLAIN ENGLISH</b>{esc(text)}</div>'


def health_strip_html(health: list[dict]) -> str:
    n = {k: sum(1 for h in health if h["level"] == k) for k in ("alert", "warn", "info")}
    chips = []
    if n["alert"]:
        chips.append(chip(f"{n['alert']} ALERT{'S' if n['alert'] != 1 else ''}", "t-red"))
    if n["warn"]:
        chips.append(chip(f"{n['warn']} WARNING{'S' if n['warn'] != 1 else ''}", "t-amber"))
    if n["info"]:
        chips.append(chip(f"{n['info']} NOTE{'S' if n['info'] != 1 else ''}", "t-cyan"))
    if not chips:
        chips.append(chip("✅ ALL SCREENS PASSED", "t-green"))
    return ('<div class="health-strip"><b>DATA-HEALTH SCREEN</b>' + "".join(chips)
            + "<span>details in Tab 5 and in the Excel export · rough tripwires, not an audit</span></div>")


def health_cards_html(health: list[dict]) -> str:
    out = []
    for h in health:
        tone = HEALTH_TONE.get(h["level"], "t-cyan")
        out.append(f'<div class="hc {tone}"><b>{HEALTH_TXT.get(h["level"], "NOTE")} · {esc(h["code"])}</b><span>{esc(h["title"])}</span><br>{esc(h["detail"])}</div>')
    return "".join(out)


def mast_html(source_label: str, fy: str, mode_tag: str) -> str:
    return (f'<div class="mast"><span class="pill"><i></i>{esc(mode_tag)} · {esc(source_label)} · {esc(fy)}</span>'
            f'<span class="pill ghost">{APP_NAME} TERMINAL · ENGINEERED BY {CREATOR.upper()}</span>'
            f'<div class="mast-title">{APP_NAME}</div>'
            '<div class="mast-etym"><em>μέρος</em> · Corporate Value-Added Statement, Common-Size Anatomy &amp; Stakeholder Economics</div>'
            '<div class="mast-sub">Greek for portion, share &amp; stakeholder allotment · all figures in ₹ Crores</div>'
            '<div class="mast-rule"></div></div>')


def welcome_html() -> str:
    return ('<div class="hero"><span class="pill"><i></i>Welcome</span>'
            f'<div class="hero-title">Welcome to {APP_NAME} <em>μέρος</em></div>'
            '<div class="hero-sub">See where every rupee a company earns actually goes: to suppliers, employees, lenders, the government, '
            'shareholders and the company itself. Pick a listed company and MEROS does the rest, with every number traced to its source.</div></div>'
            '<div class="step-grid">'
            '<div class="step"><div class="step-n">1</div><b>Pick a company</b><span>Type or choose any NSE-listed company in the sidebar. '
            'MEROS fetches its annual statements from Yahoo Finance automatically, usually the latest three to four years.</span></div>'
            '<div class="step"><div class="step-n">2</div><b>Read the analysis</b><span>Value-added statement, the ₹100 receipt, DuPont, EVA, a '
            'shock simulator and data-health checks, all explained in plain English and downloadable to Excel.</span></div>'
            '<div class="step"><div class="step-n">3</div><b>Want more years?</b><span>Choose 5, 10 years or since inception. MEROS then shows '
            'step-by-step how to download a free Screener Excel file and upload it for a longer history.</span></div></div>')


def guide_html(guide: dict, symbol: str, version: str) -> str:
    """guide: screener_source.download_guide(...)."""
    steps = "".join(f"<li><b>{esc(t)}.</b> {esc(d)}</li>" for t, d in guide["steps"])
    return ('<div class="guide"><h4>How to get a longer history: download the Screener Excel for '
            f'{esc(str(symbol).upper() or "your company")} ({esc(version)})</h4><ol>{steps}</ol>'
            f'<a class="btn" href="{esc(guide["url"])}" target="_blank" rel="noopener noreferrer">OPEN ON SCREENER ↗</a>'
            f'<a class="btn" href="{esc(guide["google_url"])}" target="_blank" rel="noopener noreferrer">SEARCH ON GOOGLE ↗</a>'
            f'<div class="note">{esc(guide["note"])}</div></div>')


def download_card_html(title: str, text: str) -> str:
    return f'<div class="dl-card"><b>{esc(title)}</b>{esc(text)}</div>'


def disclaimer_badge_html() -> str:
    return ('<div class="disc-wrap"><details class="disc"><summary>ⓘ ' + esc(DISCLAIMER_BADGE) + '</summary>'
            f'<div class="disc-body"><b>DISCLAIMER</b>{esc(DISCLAIMER_FULL)}</div></details></div>')


def inject_disclaimer() -> None:
    """The always-visible, expandable disclaimer in the bottom-right corner. Call on every page, including error screens."""
    st.markdown(disclaimer_badge_html(), unsafe_allow_html=True)


# --------------------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------------------
def pad_range(*arrs, pad: float = 0.18, pad_low: bool = False) -> list[float]:
    """Axis range with headroom so outside labels never touch the title or legend."""
    v = np.concatenate([np.asarray(a, dtype="float64").ravel() for a in arrs]) if arrs else np.array([])
    v = v[np.isfinite(v)]
    if v.size == 0:
        return [0.0, 1.0]
    lo, hi = min(float(v.min()), 0.0), max(float(v.max()), 0.0)
    span = (hi - lo) or 1.0
    return [lo - (pad * span if (lo < 0 or pad_low) else 0.0), hi + pad * span]


def style_fig(fig: go.Figure, title: str, height: int = 440) -> go.Figure:
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(t=55, b=55, l=25, r=25), height=height,
                      title=dict(text=title, x=0.0, y=0.96, yanchor="top", font=dict(family="Plus Jakarta Sans, sans-serif", size=15, color=CHAMPAGNE)),
                      font=dict(family="Plus Jakarta Sans, sans-serif", color=CHAMPAGNE),
                      hoverlabel=dict(bgcolor="#15171C", bordercolor="rgba(229,169,60,0.45)",
                                      font=dict(family="JetBrains Mono, monospace", color=CHAMPAGNE, size=12)))
    fig.add_annotation(text=f"{APP_NAME} · {CREATOR}", xref="paper", yref="paper", x=1.0, y=0.0, yshift=-40, xanchor="right",
                       yanchor="top", showarrow=False, font=dict(family="JetBrains Mono, monospace", size=9, color="rgba(229,169,60,0.6)"))
    fig.update_xaxes(gridcolor=GRID, linecolor="rgba(244,241,234,0.18)", zerolinecolor="rgba(244,241,234,0.22)")
    fig.update_yaxes(gridcolor=GRID, linecolor="rgba(244,241,234,0.18)", zerolinecolor="rgba(244,241,234,0.22)", automargin=True)
    return fig


def show_chart(fig: go.Figure, key: str) -> None:
    if _PLOTLY_HAS_WIDTH:
        st.plotly_chart(fig, width="stretch", theme=None, key=key)
    else:
        st.plotly_chart(fig, use_container_width=True, theme=None, key=key)