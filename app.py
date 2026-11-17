from __future__ import annotations

import html
import inspect

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from benchmark_generator import (ARCHETYPES, DEFAULT_ARCHETYPE, POPULAR_TICKERS, fetch_live_nse_ticker, get_archetype_df,
                                 get_blank_template_bytes, normalize_ticker, rebalance_to_pbt_anchor)
from corporate_engine import (RECEIPT_LABELS, STAKEHOLDER_LABELS, YEARS, compute_corporate_anatomy_and_vas,
                              generate_deterministic_diagnostics, sanitize_statement_df, simulate_margin_shock)

st.set_page_config(page_title="MEROS | Corporate Value-Added & Stakeholder Economics Terminal", page_icon="🧾",
                   layout="wide", initial_sidebar_state="expanded")

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
SRC_ARCH, SRC_LIVE, SRC_UP = ("Pre-Loaded Public Archetypes", "Live NSE / BSE Ticker (Yahoo Finance)",
                              "Upload Custom 3-Year Statement (.csv/.xlsx)")
QUICK_NONE = "— use the symbol typed above —"
GRID = "rgba(244,241,234,0.06)"
LEG_BELOW = dict(orientation="h", yanchor="top", y=-0.26, xanchor="center", x=0.5, font=dict(size=10))
RECEIPT_STAMP = '<div class="receipt-stamp">VERIFIED LEDGER · <b>MEROS</b> ENGINE BY <b>DINU DENNY CULAS</b></div>'
COLOPHON = ('<div class="colophon"><span><b>MEROS</b> (<em>μέρος</em>) — Corporate Value-Added &amp; Stakeholder Economics Engine</span>'
            '<span class="by">Architected &amp; Engineered by <b>Dinu Denny Culas</b> · Open-Source Strategic Finance</span></div>')
_PLOTLY_HAS_WIDTH = "width" in inspect.signature(st.plotly_chart).parameters
_DL_KW = {"width": "stretch"} if "width" in inspect.signature(st.download_button).parameters else {"use_container_width": True}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');
.stApp{background:radial-gradient(ellipse 80% 35% at 50% -10%,rgba(229,169,60,.10),transparent),#0A0A0C;font-family:'Plus Jakarta Sans',sans-serif;color:#F4F1EA;}
#MainMenu,footer{visibility:hidden;}
.block-container{padding-top:4.8rem;max-width:1440px;}
section[data-testid="stSidebar"]{background:#111215;border-right:1px solid rgba(244,241,234,.08);}
.brand-title{font-family:'Plus Jakarta Sans',sans-serif;font-weight:800;font-size:1.5rem;letter-spacing:.02em;color:#F4F1EA;}
.brand-title em,.mast-etym em,.section-h em{font-family:'Instrument Serif',serif;font-style:italic;font-weight:400;color:#E5A93C;}
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
.notice{background:rgba(229,169,60,.06);border:1px solid rgba(229,169,60,.28);border-left:3px solid #E5A93C;border-radius:8px;padding:.8rem 1rem;margin:.2rem 0 1rem 0;font-size:.78rem;line-height:1.65;color:#C9C6BE;}
.notice b{color:#E5A93C;letter-spacing:.1em;font-size:.66rem;margin-right:.4rem;}
.glass-card,.kpi-card,.diag-card{background:#15171C;border:1px solid rgba(244,241,234,.08);border-top:1px solid rgba(244,241,234,.18);border-radius:10px;padding:1.2rem;transition:transform 220ms cubic-bezier(0.22,1,0.36,1),border-color 220ms ease,box-shadow 220ms ease;}
.glass-card:hover,.kpi-card:hover,.diag-card:hover{transform:translateY(-2px);border-color:rgba(229,169,60,.35);box-shadow:0 12px 28px -8px rgba(0,0,0,.65);}
.t-gold,.t-blue{--c:#E5A93C;--bg:rgba(229,169,60,.12);}.t-green{--c:#10B981;--bg:rgba(16,185,129,.12);}
.t-amber{--c:#F59E0B;--bg:rgba(245,158,11,.12);}.t-red{--c:#F43F5E;--bg:rgba(244,63,94,.12);}
.t-cyan{--c:#38BDF8;--bg:rgba(56,189,248,.12);}.t-violet{--c:#A855F7;--bg:rgba(168,85,247,.12);}
.kpi-grid{display:grid;gap:.7rem;align-items:stretch;margin-bottom:1rem;}
.kpi-grid.n5{grid-template-columns:repeat(5,minmax(0,1fr));}
.kpi-grid.n4{grid-template-columns:repeat(4,minmax(0,1fr));}
@media(max-width:1180px){.kpi-grid.n5,.kpi-grid.n4{grid-template-columns:repeat(2,minmax(0,1fr));}}
@media(max-width:760px){.kpi-grid.n5,.kpi-grid.n4,.diag-grid{grid-template-columns:minmax(0,1fr);}}
.kpi-card{position:relative;overflow:hidden;min-height:168px;height:100%;display:flex;flex-direction:column;justify-content:space-between;gap:.25rem;}
.kpi-card::before{content:"";position:absolute;top:0;left:0;width:44px;height:2px;background:var(--c);}
.kpi-card .kpi-badge{align-self:flex-start;}
.kpi-label{font-size:.7rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#8E929F;}
.kpi-value{font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-weight:700;font-size:1.3rem;margin:.5rem 0 .15rem 0;color:#F4F1EA;word-break:break-word;}
.kpi-sub{font-size:.74rem;color:#8E929F;margin-bottom:.6rem;min-height:1.1rem;}
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
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid rgba(244,241,234,.1);}
.stTabs [data-baseweb="tab"]{background:transparent;border-radius:6px 6px 0 0;padding:.5rem 1rem;font-weight:600;color:#8E929F;}
.stTabs [aria-selected="true"]{color:#E5A93C;}
.stTabs [data-baseweb="tab-highlight"]{background:#E5A93C;}
div[data-testid="stVerticalBlockBorderWrapper"]{background:#15171C;border:1px solid rgba(244,241,234,.08)!important;border-top:1px solid rgba(244,241,234,.18)!important;border-radius:10px;}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner="Fetching audited filings from Yahoo Finance...")
def load_live(symbol: str) -> tuple[pd.DataFrame, dict]:
    return fetch_live_nse_ticker(symbol)


def _bump_reset() -> None:
    st.session_state["live_reset"] = int(st.session_state.get("live_reset", 0)) + 1


def stop_with_footer() -> None:
    st.markdown(COLOPHON, unsafe_allow_html=True)
    st.stop()


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


def _money(v: float, d: int, suffix: str) -> str:
    if v is None or not np.isfinite(v):
        return "n/a"
    body = _indian(v, d)
    neg = v < 0 and float(body.replace(",", "")) > 0
    return f"{'-' if neg else ''}₹{body}{suffix}"


def fmt_cr(v: float, d: int = 2) -> str: return _money(float(v), d, " Cr")
def fmt_lakh(v: float, d: int = 2) -> str: return _money(float(v), d, " L")
def fmt_rs(v: float) -> str: return _money(float(v), 2, "")


def fmt_pct(v: float, d: int = 1, signed: bool = False) -> str:
    if v is None or not np.isfinite(v):
        return "n/a"
    return f"{v:+.{d}f}%" if signed else f"{v:.{d}f}%"


def pad_range(*arrs, pad: float = 0.18, pad_low: bool = False) -> list[float]:
    v = np.concatenate([np.asarray(a, dtype="float64").ravel() for a in arrs])
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
    fig.add_annotation(text="MEROS · Dinu Denny Culas", xref="paper", yref="paper", x=1.0, y=0.0, yshift=-40, xanchor="right",
                       yanchor="top", showarrow=False, font=dict(family="JetBrains Mono, monospace", size=9, color="rgba(229,169,60,0.6)"))
    fig.update_xaxes(gridcolor=GRID, linecolor="rgba(244,241,234,0.18)", zerolinecolor="rgba(244,241,234,0.22)")
    fig.update_yaxes(gridcolor=GRID, linecolor="rgba(244,241,234,0.18)", zerolinecolor="rgba(244,241,234,0.22)", automargin=True)
    return fig


def show_chart(fig: go.Figure, key: str) -> None:
    if _PLOTLY_HAS_WIDTH:
        st.plotly_chart(fig, width="stretch", theme=None, key=key)
    else:
        st.plotly_chart(fig, use_container_width=True, theme=None, key=key)


def kpi_card(label: str, value: str, sub: str, badge: str, tone: str) -> str:
    return (f'<div class="kpi-card {tone}"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>'
            f'<div class="kpi-sub">{sub}</div><span class="kpi-badge">{badge}</span></div>')


def kpi_grid(cards: list[str]) -> str:
    return f'<div class="kpi-grid n{len(cards)}">' + "".join(cards) + "</div>"


def render_table(headers: list[str], rows: list[tuple[str, str, list[str]]]) -> str:
    head = "".join(f'<th{" class=num" if i else ""}>{html.escape(h)}</th>' for i, h in enumerate(headers))
    body = []
    for kind, label, vals in rows:
        if kind == "section":
            body.append(f'<tr class="section"><td colspan="{len(headers)}">{html.escape(label)}</td></tr>')
        else:
            tds = "".join(f'<td class="num">{v}</td>' for v in vals)
            body.append(f'<tr class="{kind}"><td>{html.escape(label)}</td>{tds}</tr>')
    return ('<div class="glass-card" style="overflow-x:auto;padding:.6rem .9rem;">'
            f'<table class="vas-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def load_uploaded(file) -> pd.DataFrame:
    if file.name.lower().endswith(".xlsx"):
        return pd.read_excel(file, dtype=str, engine="openpyxl")
    try:
        return pd.read_csv(file, dtype=str, encoding="utf-8-sig")
    except UnicodeDecodeError:
        file.seek(0)
        return pd.read_csv(file, dtype=str, encoding="latin-1")


def preview_cell(v) -> str:
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return "∅ (None)"
    s = str(v)
    return "∅ (blank)" if s.strip() == "" else s


def notice_block(meta: dict) -> str:
    fy_txt = " · ".join(f"{fy} = {lab}" for fy, lab in zip(YEARS, meta["period_labels"]))
    sector = html.escape(meta["sector"] or "sector n/a")
    lines = [f"<b>SOURCE</b>Yahoo Finance (yfinance) · latest 3 annual filings · {fy_txt} · ₹ Crores · {sector}"]
    for k in ("emp_cost_note", "headcount_note", "tax_note", "opex_note"):
        lines.append("▸ " + html.escape(meta[k]))
    for w in meta["warnings"]:
        lines.append("▸ " + html.escape(w))
    return '<div class="notice">' + "<br>".join(lines) + "</div>"


def build_bridge(meta: dict, pnl: pd.DataFrame, results: dict, cs: pd.DataFrame) -> str:
    anc = meta["anchors"]
    tr, pb, pa = (np.array(anc[k], dtype="float64") for k in ("TOTAL_REVENUE", "PBT", "PAT"))
    tp = np.array([np.nan if v is None else v for v in anc["TAX_PROVISION"]], dtype="float64")

    def row(name: str) -> np.ndarray:
        return pnl.loc[name, YEARS].to_numpy(dtype="float64")

    v_pbt, v_pat = row("PBT") - pb, row("PAT") - pa
    resid = np.array([results["vas_residual"][y] for y in YEARS], dtype="float64")
    rcpt = cs[YEARS].sum(axis=0).to_numpy(dtype="float64") - 100.0
    close_ok = (np.abs(resid) < 1e-4) & (np.abs(rcpt) < 1e-4)
    anchor_ok = (np.abs(v_pbt) < 1e-4) & (np.abs(v_pat) < 1e-4)

    def cr(a: np.ndarray) -> list[str]:
        return [fmt_cr(x) if np.isfinite(x) else "n/a" for x in a]

    def var(a: np.ndarray) -> list[str]:
        return ["0.0000" if abs(x) < 5e-5 else f"{x:+.4f}" for x in a]

    def badge(c_ok: bool, a_ok: bool) -> str:
        if c_ok and a_ok:
            return '<span class="kpi-badge t-green">✅ Match</span>'
        return '<span class="kpi-badge t-amber">⚠ Edited</span>' if c_ok else '<span class="kpi-badge t-red">❌ Break</span>'

    if bool(close_ok.all()) and bool(anchor_ok.all()):
        overall = '<span class="kpi-badge t-green">✅ Verified Match</span>'
    elif bool(close_ok.all()):
        overall = '<span class="kpi-badge t-amber">⚠ Override variance vs Yahoo</span>'
    else:
        overall = '<span class="kpi-badge t-red">❌ Closure break</span>'

    rows: list[tuple[str, str, list[str]]] = [
        ("section", "A. YAHOO FINANCE REPORTED ANCHORS (₹ CR)", []),
        ("row", "Total Revenue (reported)", cr(tr) + [""]),
        ("row", "Pretax Income (reported)", cr(pb) + [""]),
        ("row", "Net Income to common (reported)", cr(pa) + [""]),
        ("row", "Tax Provision (reported)", cr(tp) + [""]),
        ("section", "B. MEROS SCHEDULE III LADDER (FROM THE CURRENT GRID)", []),
        ("row", "Total Income (REV_OPS + REV_OTH)", cr(row("Total_Income")) + [""]),
        ("row", "Gross Value Added (GVA)", cr(row("GVA")) + [""]),
        ("row", "PBT (GVA − Employee − Depreciation − Finance)", cr(row("PBT")) + [""]),
        ("row", "Tax expense used (Pretax − Net Income)", cr(row("Tax_Expense")) + [""]),
        ("row", "PAT (PBT − Tax)", cr(row("PAT")) + [""]),
        ("section", "C. VARIANCE & CLOSURE (TARGET 0.0000)", []),
        ("row", "PBT variance vs Yahoo Pretax Income", var(v_pbt) + [""]),
        ("row", "PAT variance vs Yahoo Net Income", var(v_pat) + [""]),
        ("row", "VAS closure residual (GVA − Σ 5 stakeholders)", var(resid) + [""]),
        ("row", "₹100 receipt closure (Σ 8 components − ₹100.00)", var(rcpt) + [""]),
        ("total", "Verification status", [badge(bool(c), bool(a)) for c, a in zip(close_ok, anchor_ok)] + [overall]),
    ]
    heads = ["Reconciliation line (₹ Cr)"] + [f"{y} · {lab}" for y, lab in zip(YEARS, meta["period_labels"])] + ["Status"]
    return render_table(heads, rows)


with st.sidebar:
    st.markdown('<div class="brand-title">MEROS <em>μέρος</em></div>'
                '<div class="brand-sub">Value-Added &amp; Stakeholder Economics Engine</div>', unsafe_allow_html=True)
    source = st.radio("Data Source", [SRC_ARCH, SRC_LIVE, SRC_UP])
    is_arch, is_live, is_up = source == SRC_ARCH, source == SRC_LIVE, source == SRC_UP
    uploaded, archetype_name, dirty_flag, live_symbol = None, DEFAULT_ARCHETYPE, True, ""
    if is_arch:
        names = list(ARCHETYPES.keys())
        archetype_name = st.selectbox("Corporate Archetype", names, index=names.index(DEFAULT_ARCHETYPE))
        dirty_flag = st.checkbox("Simulate Dirty ERP/Filing Formatting", value=True)
    elif is_live:
        typed_symbol = st.text_input("NSE / BSE Ticker Symbol", value="ITC.NS",
                                     help="Type any NSE ticker e.g. RELIANCE, TCS, HDFCBANK, ZOMATO, TATAMOTORS")
        quick_pick = st.selectbox("Quick-select a popular ticker", [QUICK_NONE] + POPULAR_TICKERS)
        live_symbol = typed_symbol if quick_pick == QUICK_NONE else quick_pick
        st.caption("Bare symbols default to NSE (.NS); use .BO for BSE. Yahoo reports absolute ₹: MEROS converts it to ₹ Crores.")
    else:
        uploaded = st.file_uploader("Upload 3-Year Statement", type=["csv", "xlsx"])
        st.download_button("Download Blank 3-Year Schedule III Template (.csv)", data=get_blank_template_bytes(),
                           file_name="meros_schedule_iii_template.csv", mime="text/csv", **_DL_KW)
    st.divider()
    active_fy = st.selectbox("Active Fiscal Year", ["FY26", "FY25", "FY24"], index=0)
    fy_slot = st.container()
    st.caption("All monetary values in ₹ Crores. Deterministic Python engine: zero LLM calls.")
    st.markdown('<div class="architect"><small>ARCHITECTED &amp; ENGINEERED BY</small><strong>Dinu Denny Culas</strong>'
                '<span>Strategic Finance &amp; Quantitative Engineering</span></div>', unsafe_allow_html=True)

mast_slot, editor_slot = st.container(), st.container()
live_meta, bridge_slot = None, None

if is_arch:
    raw_df, source_label = get_archetype_df(archetype_name, inject_dirty_data=dirty_flag), archetype_name
elif is_live:
    try:
        live_sym = normalize_ticker(live_symbol)
        live_base, live_meta = load_live(live_sym)
    except ValueError as exc:
        st.error(str(exc))
        stop_with_footer()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not reach Yahoo Finance for {live_symbol!r}: {exc}")
        stop_with_footer()
    source_label = f"{live_meta['company_name']} ({live_meta['symbol']})"
    with editor_slot:
        with st.expander("Live Schedule III Verification & Custom Override Grid (Editable)", expanded=False):
            st.caption("Scraped from Yahoo Finance and converted to ₹ Crores. Edit EMP_COST, HEADCOUNT or any other cell: "
                       "every KPI, chart and the reconciliation bridge below recompute instantly.")
            c_a, c_b = st.columns([3, 1])
            rebalance_on = c_a.checkbox("Keep the Yahoo Pretax Income anchor (auto-rebalance Other Operating Expenses after my edits)",
                                        value=True, key="live_rebalance")
            c_b.button("Reset grid", key="live_reset_btn", on_click=_bump_reset)
            cfg = {"Line_ID": st.column_config.TextColumn("Line ID", width="small"),
                   "Line_Item_Name": st.column_config.TextColumn("Schedule III line item", width="large"),
                   "Category": st.column_config.TextColumn("Category", width="small")}
            for yr, lab in zip(YEARS, live_meta["period_labels"]):
                cfg[yr] = st.column_config.NumberColumn(f"{yr} · {lab}", format="%.2f", step=0.01)
            edited = st.data_editor(live_base, key=f"live_editor_{live_meta['symbol']}_{int(st.session_state.get('live_reset', 0))}",
                                    hide_index=True, num_rows="fixed", disabled=["Line_ID", "Line_Item_Name", "Category"],
                                    column_config=cfg)
            raw_df = rebalance_to_pbt_anchor(edited, live_meta["anchors"]["PBT"]) if rebalance_on else edited
            st.caption("Auto-rebalance ON: direct edits to Other Income / Other Operating Expenses are re-solved so PBT equals Yahoo's. "
                       "Turn it off to edit those rows freely; the bridge then shows the variance.")
            bridge_slot = st.container()
    with fy_slot:
        st.caption(" · ".join(f"{fy} → {lab}" for fy, lab in zip(YEARS, live_meta["period_labels"])))
else:
    if uploaded is None:
        st.info("Upload a 3-year statement (.csv/.xlsx) in the sidebar, or download the blank template to fill in.")
        stop_with_footer()
    try:
        raw_df = load_uploaded(uploaded)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not read the uploaded file: {exc}")
        stop_with_footer()
    source_label = uploaded.name

try:
    clean_df, audit = sanitize_statement_df(raw_df)
    results = compute_corporate_anatomy_and_vas(clean_df)
except (ValueError, TypeError) as exc:
    st.error(f"Statement could not be processed: {exc}")
    stop_with_footer()

diagnostics = generate_deterministic_diagnostics(results)
pnl, kpis, cagr, inputs = results["pnl"], results["kpis"], results["cagr"], results["inputs"]
cs, vas_abs, vas_pct = results["common_size"], results["vas_abs"], results["vas_pct"]
if float(pnl.loc["Total_Income", active_fy]) <= 0:
    st.error(f"Total Income for {active_fy} is zero or negative. Populate REV_OPS / REV_OTH to run the analysis.")
    stop_with_footer()

bridge_html = build_bridge(live_meta, pnl, results, cs) if live_meta is not None else ""
if bridge_slot is not None:
    with bridge_slot:
        st.markdown('<div class="kpi-label" style="margin:.4rem 0 .5rem 0">Reconciliation bridge · Yahoo Finance vs MEROS</div>', unsafe_allow_html=True)
        st.markdown(bridge_html, unsafe_allow_html=True)

mode_tag = "Live NSE / BSE feed" if is_live else "Live ledger"
with mast_slot:
    st.markdown(f'<div class="mast"><span class="pill"><i></i>{mode_tag} · {html.escape(source_label)} · {active_fy}</span>'
                '<span class="pill ghost">MEROS TERMINAL · ENGINEERED BY DINU DENNY CULAS</span>'
                '<div class="mast-title">MEROS</div>'
                '<div class="mast-etym"><em>μέρος</em> · Corporate Value-Added Statement, Common-Size Anatomy &amp; Stakeholder Economics</div>'
                '<div class="mast-sub">Greek for portion, share &amp; stakeholder allotment · all figures in ₹ Crores</div>'
                '<div class="mast-rule"></div></div>', unsafe_allow_html=True)
    if live_meta is not None:
        st.markdown(notice_block(live_meta), unsafe_allow_html=True)

ti_fy, gva_fy = float(pnl.loc["Total_Income", active_fy]), float(pnl.loc["GVA", active_fy])
rev_cagr = float(cagr["Revenue_CAGR_Pct"])
pat_bite = float(cs.loc[RECEIPT_LABELS[6], active_fy] + cs.loc[RECEIPT_LABELS[7], active_fy])
pat_margin = float(kpis.loc["PAT_Margin_Pct", active_fy])
closure_ok = bool(results["vas_closure_check"])
closure_txt = "Verified ✅" if closure_ok else "Breach ⚠️"
cagr_tone = "t-gold" if not np.isfinite(rev_cagr) else ("t-green" if rev_cagr >= 10 else ("t-gold" if rev_cagr >= 0 else "t-red"))
pat_tone = "t-green" if pat_margin >= 10 else ("t-amber" if pat_margin > 0 else "t-red")
hyg_tone = "t-red" if not closure_ok else ("t-amber" if audit["cells_repaired"] > 0 else "t-green")

st.markdown(kpi_grid([
    kpi_card("Total Income", fmt_cr(ti_fy), f"{active_fy} · Revenue + Other Income",
             f"3-Yr Revenue CAGR {fmt_pct(rev_cagr, 1, True)}", cagr_tone),
    kpi_card("Gross Value Added", fmt_cr(gva_fy), f"{active_fy} · Income less bought-in costs",
             f"GVA Margin {fmt_pct(float(kpis.loc['GVA_Margin_Pct', active_fy]), 1)}", "t-gold"),
    kpi_card("Consumer Net Profit Bite", f"{fmt_rs(pat_bite)} per ₹100 spent", f"{active_fy} · PAT per ₹100 of income",
             f"PAT Margin {fmt_pct(pat_margin, 2)}", pat_tone),
    kpi_card("Workforce Productivity", f"{fmt_lakh(float(kpis.loc['Value_Added_Per_Emp_Lakhs', active_fy]), 1)} / Emp",
             f"{active_fy} · Value added per employee",
             f"Human Capital ROI {float(kpis.loc['Human_Capital_ROI', active_fy]):.2f}x", "t-cyan"),
    kpi_card("Data Hygiene & Closure", f"{audit['cells_repaired']} cells",
             f"auto-cleaned | {audit['repair_pct']:.1f}% of {audit['total_cells']} cells",
             f"VAS Closure: {closure_txt}", hyg_tone),
]), unsafe_allow_html=True)

with st.expander(f"Data hygiene audit log · {audit['cells_repaired']} repairs"):
    if audit["repair_log"]:
        st.code("\n".join(audit["repair_log"]), language="text")
    else:
        st.caption("No repairs were required: input was already clean.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["1. ₹100 Consumer Anatomy", "2. Stakeholder Value-Added (VAS)",
                                        "3. Workforce & Capital Efficiency", "4. Margin Shock Simulator",
                                        "5. Glass-Box Formula Audit"])

with tab1:
    st.markdown('<div class="section-h">Where does your <em>₹100</em> actually go?</div>'
                f'<div class="section-sub">Every ₹100 of {active_fy} total income, traced from the customer\'s wallet to suppliers, '
                'staff, lenders, the state, shareholders and the company\'s own reserves.</div>', unsafe_allow_html=True)
    col_chart, col_receipt = st.columns([1.35, 1], gap="large")
    fy_cs = cs[active_fy].to_numpy(dtype="float64")

    with col_chart:
        view = st.radio("Chart view", ["Waterfall (Active FY)", "Stacked Bar (FY24 to FY26)"], horizontal=True,
                        label_visibility="collapsed")
        if view.startswith("Waterfall"):
            cum = np.concatenate([[0.0], np.cumsum(fy_cs[:7])])
            wf_base = [0.0] + [float(100.0 - cum[i + 1]) for i in range(7)] + [0.0]
            wf_h = [100.0] + [float(v) for v in fy_cs[:7]] + [float(fy_cs[7])]
            wf_text = ["₹100.00"] + [fmt_rs(-float(v)) for v in fy_cs[:7]] + [fmt_rs(float(fy_cs[7]))]
            wf_hover = ["₹100.00 paid by the customer"] + [f"{fmt_rs(float(v))} of every ₹100" for v in fy_cs]
            fig = go.Figure(go.Bar(x=WF_TICKS, y=wf_h, base=wf_base, marker_color=[GOLD] + RECEIPT_COLORS, text=wf_text,
                                   textposition="outside", cliponaxis=False,
                                   customdata=[[n, h] for n, h in zip(WF_FULL, wf_hover)],
                                   hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>"))
            style_fig(fig, f"₹100.00 Customer Spend Decomposition · {active_fy}", 480)
            fig.update_layout(showlegend=False, xaxis=dict(tickangle=0, tickfont=dict(size=10)),
                              yaxis=dict(tickprefix="₹", range=pad_range(wf_base, np.array(wf_base) + np.array(wf_h))))
        else:
            fig = go.Figure()
            for i in range(8):
                vals = cs.iloc[i][YEARS].to_numpy(dtype="float64")
                fig.add_trace(go.Bar(y=YEARS, x=vals, orientation="h", name=RECEIPT_NAMES[i], marker_color=RECEIPT_COLORS[i],
                                     text=[f"{v:.1f}" if abs(v) >= 3.0 else "" for v in vals], textposition="inside",
                                     textfont=dict(color="#0A0A0C"),
                                     hovertemplate="<b>%{fullData.name}</b><br>%{y}: ₹%{x:.2f} per ₹100<extra></extra>"))
            style_fig(fig, "Common-Size ₹100 Anatomy · FY24 vs FY25 vs FY26", 480)
            fig.update_layout(barmode="stack", yaxis=dict(autorange="reversed"), xaxis=dict(tickprefix="₹"), legend=LEG_BELOW)
        show_chart(fig, "t1_main_chart")

    with col_receipt:
        rows_html = "".join(f'<div class="receipt-row"><span><span class="dot" style="background:{RECEIPT_COLORS[i]}"></span>'
                            f'{html.escape(RECEIPT_NAMES[i])}</span><span class="amt">{fmt_rs(float(fy_cs[i]))}</span></div>'
                            for i in range(8))
        ok_fy = bool(results["receipt_check"]["ok_by_year"][active_fy])
        st.markdown('<div class="receipt"><div class="receipt-head">CONSUMER ITEMIZED RECEIPT</div>'
                    f'<div class="receipt-meta">{html.escape(source_label)} · {active_fy}<br>Amount paid by customer: ₹100.00</div>'
                    f'{rows_html}<div class="receipt-total"><span>TOTAL ALLOCATED</span><span>{fmt_rs(float(fy_cs.sum()))} '
                    f'{"✅" if ok_fy else "⚠️"}</span></div>' + RECEIPT_STAMP + '</div>', unsafe_allow_html=True)
        if st.toggle("Show 3-Year Common-Size Comparison (FY24 vs FY25 vs FY26)", value=False):
            cs_rows: list[tuple[str, str, list[str]]] = []
            for i in range(8):
                v = cs.iloc[i][YEARS].to_numpy(dtype="float64")
                cs_rows.append(("row", RECEIPT_NAMES[i], [fmt_rs(x) for x in v] + [f"{v[2] - v[0]:+.2f}"]))
            tot = cs[YEARS].sum(axis=0).to_numpy(dtype="float64")
            cs_rows.append(("total", "Total per ₹100", [fmt_rs(x) for x in tot] + [""]))
            st.markdown(render_table(["Per ₹100 spent"] + YEARS + ["Δ FY24→26"], cs_rows), unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="section-h">Stakeholder value-added statement &amp; <em>3-year drift</em></div>'
                '<div class="section-sub">Rule-based diagnostics, then how the Gross Value Added pie is sliced among workforce, '
                'lenders, the state, shareholders and the enterprise itself.</div>', unsafe_allow_html=True)
    diag_cards = []
    for card in diagnostics:
        tone = SEV_TONE.get(card["severity"], "t-cyan")
        diag_cards.append(f'<div class="diag-card {tone}"><div class="diag-head"><span class="diag-title">{html.escape(card["title"])}</span>'
                          f'<span class="diag-pill">{html.escape(card["badge_text"])}</span></div>'
                          f'<div class="diag-text">{html.escape(card["narrative"])}</div></div>')
    st.markdown('<div class="diag-grid">' + "".join(diag_cards) + "</div>", unsafe_allow_html=True)

    c_left, c_right = st.columns([1.4, 1], gap="large")
    with c_left:
        fig = go.Figure()
        for i in range(5):
            pcts = vas_pct.iloc[i][YEARS].to_numpy(dtype="float64")
            amts = [fmt_cr(x) for x in vas_abs.iloc[i][YEARS].to_numpy(dtype="float64")]
            fig.add_trace(go.Bar(x=YEARS, y=pcts, name=STAKE_SHORT[i], marker_color=STAKE_COLORS[i], customdata=amts,
                                 text=[f"{p:.1f}%" if abs(p) >= 3.0 else "" for p in pcts], textposition="inside",
                                 textfont=dict(color="#0A0A0C"),
                                 hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.2f}% of GVA<br>%{customdata}<extra></extra>"))
        style_fig(fig, "How the GVA Pie Shifted · 100% Stacked", 420)
        fig.update_layout(barmode="stack", yaxis=dict(ticksuffix="%"), legend=LEG_BELOW)
        show_chart(fig, "t2_stacked_chart")

    with c_right:
        raw_vals = vas_abs[active_fy].to_numpy(dtype="float64")
        pie_vals = np.clip(raw_vals, 0.0, None)
        if pie_vals.sum() <= 0:
            st.warning(f"GVA for {active_fy} is non-positive; no distributable value to chart.")
        else:
            fig = go.Figure(go.Pie(labels=STAKE_SHORT, values=pie_vals, hole=0.62, sort=False, direction="clockwise",
                                   marker=dict(colors=STAKE_COLORS, line=dict(color="#0A0A0C", width=2)), textinfo="percent",
                                   textfont=dict(family="JetBrains Mono, monospace", color="#0A0A0C"),
                                   hovertemplate="<b>%{label}</b><br>₹%{value:,.2f} Cr<br>%{percent} of GVA<extra></extra>"))
            style_fig(fig, f"{active_fy} GVA Distribution", 420)
            fig.update_layout(showlegend=False)
            fig.add_annotation(text=f"<b>GVA</b><br>{fmt_cr(gva_fy)}", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
                               font=dict(size=13, family="JetBrains Mono, monospace", color=GOLD))
            show_chart(fig, "t2_donut_chart")
            if (raw_vals < 0).any():
                st.caption("Negative components (loss-absorbing items) are excluded from the donut; see the VAS table below.")

    st.markdown('<div class="section-h">Corporate value-added statement <em>(reconciliation)</em></div>', unsafe_allow_html=True)

    def trio(s: pd.Series) -> list[str]:
        return [fmt_rs(float(s[y])) for y in YEARS]

    nva_pct = float(pnl.loc["NVA", active_fy]) / gva_fy * 100.0 if gva_fy > 0 else float("nan")
    dash = ["—"]
    vas_rows: list[tuple[str, str, list[str]]] = [
        ("section", "A. GENERATION OF GROSS VALUE ADDED", []),
        ("row", "Revenue from Operations", trio(pnl.loc["Revenue_from_Operations"]) + dash),
        ("row", "Add: Other Income", trio(pnl.loc["Other_Income"]) + dash),
        ("subtotal", "Total Income", trio(pnl.loc["Total_Income"]) + dash),
        ("row", "Less: Cost of Materials & Stock-in-Trade", trio(inputs.loc["COGS_MAT"]) + dash),
        ("row", "Less: Other Operating Expenses (Freight, Power, Marketing, Vendors)", trio(inputs.loc["OPEX_EXT"]) + dash),
        ("subtotal", "Total Bought-In Goods & Services", trio(pnl.loc["Bought_In_Costs"]) + dash),
        ("total", "Gross Value Added (GVA)", trio(pnl.loc["GVA"]) + ["100.00%"]),
        ("section", "B. APPLICATION OF GROSS VALUE ADDED", []),
    ]
    for i in range(5):
        vas_rows.append(("row", STAKEHOLDER_LABELS[i], trio(vas_abs.iloc[i]) + [fmt_pct(float(vas_pct.iloc[i][active_fy]), 2)]))
        if i == 4:
            vas_rows.append(("memo", "   of which: Retained Earnings (PAT − Dividends)", trio(pnl.loc["Retained_Earnings"]) + dash))
            vas_rows.append(("memo", "   of which: Depreciation & Amortization", trio(pnl.loc["Depreciation_Amortization"]) + dash))
    vas_rows += [
        ("total", "Total Application of GVA (Σ 5 Stakeholders)", trio(vas_abs.sum(axis=0)) + [fmt_pct(float(vas_pct[active_fy].sum()), 2)]),
        ("memo", "Net Value Added (NVA = GVA − Depreciation)", trio(pnl.loc["NVA"]) + [fmt_pct(nva_pct, 2)]),
        ("memo", "Closure residual (GVA − Σ Stakeholders)", [f"{results['vas_residual'][y]:.6f}" for y in YEARS] + [closure_txt]),
    ]
    st.markdown(render_table(["Particulars (₹ Cr)"] + YEARS + [f"% of GVA ({active_fy})"], vas_rows), unsafe_allow_html=True)
    st.caption("Accounting identity: GVA = Employee Cost + Finance Cost + Tax + Dividends + (Retained Earnings + Depreciation).")

with tab3:
    st.markdown('<div class="section-h">Workforce productivity &amp; <em>capital efficiency</em></div>'
                '<div class="section-sub">Does each employee create more value than they cost, and does every rupee of capital earn '
                f'more than it is charged? Selected year: {active_fy}.</div>', unsafe_allow_html=True)
    roce_v, roe_v = float(kpis.loc["ROCE_Pct", active_fy]), float(kpis.loc["ROE_Pct", active_fy])
    cod_v, spread_v = float(kpis.loc["Implied_Cost_of_Debt_Pct", active_fy]), float(kpis.loc["Economic_Spread_Pct", active_fy])
    eva_v, icr_v = float(kpis.loc["EVA_Spread_Proxy_Cr", active_fy]), float(kpis.loc["Interest_Coverage_Ratio", active_fy])
    ce_v, debt_v, pat_v = float(kpis.loc["Capital_Employed", active_fy]), float(inputs.loc["TOTAL_DEBT", active_fy]), float(pnl.loc["PAT", active_fy])

    def ret_tone(v: float) -> str:
        return "t-green" if v >= 15.0 else ("t-gold" if v >= 8.0 else ("t-amber" if v > 0.0 else "t-red"))

    if icr_v >= 999.0:
        icr_txt, icr_badge, icr_tone = "∞", "No interest burden", "t-green"
    else:
        icr_txt = f"{icr_v:.2f}x"
        icr_badge, icr_tone = (("Comfortable cushion", "t-green") if icr_v >= 6.0 else ("Adequate cover", "t-gold") if icr_v >= 3.0
                               else ("Watchlist cover", "t-amber") if icr_v >= 1.5 else ("Thin cover", "t-red"))

    st.markdown(kpi_grid([
        kpi_card("ROCE", fmt_pct(roce_v, 2), f"{active_fy} · EBIT ÷ (Debt + Equity)", f"Capital Employed {fmt_cr(ce_v, 0)}", ret_tone(roce_v)),
        kpi_card("ROE", fmt_pct(roe_v, 2), f"{active_fy} · PAT ÷ Shareholders' Equity", f"PAT {fmt_cr(pat_v, 0)}", ret_tone(roe_v)),
        kpi_card("Implied Cost of Debt", fmt_pct(cod_v, 2), f"{active_fy} · Finance Cost ÷ Total Debt",
                 "Debt-Free" if debt_v <= 0 else f"Debt {fmt_cr(debt_v, 0)}", "t-green" if debt_v <= 0 else "t-violet"),
        kpi_card("Economic Spread", f"{spread_v:+.2f} pts", f"{active_fy} · ROCE − Implied Cost of Debt",
                 f"EVA proxy {fmt_cr(eva_v, 0)}", "t-green" if spread_v > 0 else "t-red"),
        kpi_card("Interest Coverage", icr_txt, f"{active_fy} · EBIT ÷ Finance Cost", icr_badge, icr_tone),
    ]), unsafe_allow_html=True)

    ch_left, ch_right = st.columns(2, gap="large")
    with ch_left:
        cost_s = kpis.loc["Avg_Cost_Per_Emp_Lakhs", YEARS].to_numpy(dtype="float64")
        va_s = kpis.loc["Value_Added_Per_Emp_Lakhs", YEARS].to_numpy(dtype="float64")
        roi_s = kpis.loc["Human_Capital_ROI", YEARS].to_numpy(dtype="float64")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=YEARS, y=cost_s, name="Avg Cost / Employee (₹ L)", marker_color=CYAN,
                             text=[f"{v:,.1f}" for v in cost_s], textposition="outside", cliponaxis=False,
                             hovertemplate="<b>%{fullData.name}</b><br>%{x}: ₹%{y:,.2f} L<extra></extra>"))
        fig.add_trace(go.Bar(x=YEARS, y=va_s, name="GVA / Employee (₹ L)", marker_color=GOLD,
                             text=[f"{v:,.1f}" for v in va_s], textposition="outside", cliponaxis=False,
                             hovertemplate="<b>%{fullData.name}</b><br>%{x}: ₹%{y:,.2f} L<extra></extra>"))
        fig.add_trace(go.Scatter(x=YEARS, y=roi_s, name="Human Capital ROI (x)", yaxis="y2", mode="lines+markers",
                                 line=dict(color=CHAMPAGNE, width=2.5), marker=dict(size=9, color=CHAMPAGNE),
                                 hovertemplate="<b>Human Capital ROI</b><br>%{x}: %{y:.2f}x (Revenue ÷ Employee Cost)<extra></extra>"))
        style_fig(fig, "Cost per Employee vs Value Added per Employee", 440)
        fig.update_layout(barmode="group", yaxis=dict(title="₹ Lakhs per employee", range=pad_range(cost_s, va_s)),
                          yaxis2=dict(title="Human Capital ROI (x)", overlaying="y", side="right", showgrid=False, ticksuffix="x",
                                      automargin=True, range=[0.0, max(float(np.nanmax(roi_s)), 1.0) * 1.3]),
                          legend=LEG_BELOW)
        show_chart(fig, "t3_workforce_chart")

    with ch_right:
        roce_s = kpis.loc["ROCE_Pct", YEARS].to_numpy(dtype="float64")
        roe_s = kpis.loc["ROE_Pct", YEARS].to_numpy(dtype="float64")
        cod_s = kpis.loc["Implied_Cost_of_Debt_Pct", YEARS].to_numpy(dtype="float64")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=YEARS, y=cod_s, name="Implied Cost of Debt %", mode="lines+markers",
                                 line=dict(color=VIOLET, width=2, dash="dash"), marker=dict(size=8),
                                 hovertemplate="<b>Implied Cost of Debt</b><br>%{x}: %{y:.2f}%<extra></extra>"))
        fig.add_trace(go.Scatter(x=YEARS, y=roce_s, name="ROCE %", mode="lines+markers+text", fill="tonexty",
                                 fillcolor="rgba(229,169,60,0.12)", line=dict(color=GOLD, width=3), marker=dict(size=9),
                                 text=[f"{v:.1f}%" for v in roce_s], textposition="top center",
                                 hovertemplate="<b>ROCE</b><br>%{x}: %{y:.2f}%<extra></extra>"))
        fig.add_trace(go.Scatter(x=YEARS, y=roe_s, name="ROE %", mode="lines+markers+text", line=dict(color=JADE, width=3),
                                 marker=dict(size=9), text=[f"{v:.1f}%" for v in roe_s], textposition="bottom center",
                                 hovertemplate="<b>ROE</b><br>%{x}: %{y:.2f}%<extra></extra>"))
        style_fig(fig, "Capital Efficiency & Return Trajectory", 440)
        fig.update_layout(yaxis=dict(ticksuffix="%", zeroline=True, range=pad_range(roce_s, roe_s, cod_s, pad_low=True)), legend=LEG_BELOW)
        show_chart(fig, "t3_capital_chart")
        st.caption("Gold band = ROCE earned above the implied cost of debt. For debt-free firms the cost line sits at 0%.")

    st.markdown('<div class="section-h">Strategic finance &amp; <em>credit appraisal</em> matrix</div>', unsafe_allow_html=True)
    ratio_spec: list[tuple] = [
        ("section", "PROFITABILITY & VALUE CREATION"),
        ("GVA_Margin_Pct", "GVA Margin (GVA ÷ Total Income)", "pct", True),
        ("EBITDA_Margin_Pct", "EBITDA Margin", "pct", True),
        ("PAT_Margin_Pct", "PAT Margin", "pct", True),
        ("section", "WORKFORCE PRODUCTIVITY"),
        ("Human_Capital_ROI", "Human Capital ROI (Revenue ÷ Employee Cost)", "x", True),
        ("Value_Added_Per_Emp_Lakhs", "Value Added per Employee (₹ L)", "lakh", True),
        ("section", "CAPITAL EFFICIENCY"),
        ("ROCE_Pct", "ROCE (EBIT ÷ Capital Employed)", "pct", True),
        ("ROE_Pct", "ROE (PAT ÷ Equity)", "pct", True),
        ("Implied_Cost_of_Debt_Pct", "Implied Cost of Debt", "pct", False),
        ("section", "CREDIT & TAX"),
        ("Interest_Coverage_Ratio", "Interest Coverage Ratio (EBIT ÷ Finance Cost)", "icr", True),
        ("Effective_Tax_Rate_Pct", "Effective Tax Rate (Tax ÷ PBT)", "pct", None),
    ]

    def ratio_valid(key: str, unit: str, yr: str) -> bool:
        if key == "Effective_Tax_Rate_Pct" and float(pnl.loc["PBT", yr]) <= 0:
            return False
        return not (unit == "icr" and float(kpis.loc[key, yr]) >= 999.0)

    def ratio_cell(key: str, unit: str, yr: str) -> str:
        v = float(kpis.loc[key, yr])
        if key == "Effective_Tax_Rate_Pct" and not ratio_valid(key, unit, yr):
            return "n/a"
        if unit == "icr":
            return "∞" if v >= 999.0 else f"{v:.2f}x"
        return fmt_pct(v, 2) if unit == "pct" else (f"{v:.2f}x" if unit == "x" else fmt_lakh(v, 2))

    def trend_cell(key: str, unit: str, good_up) -> str:
        if not (ratio_valid(key, unit, YEARS[0]) and ratio_valid(key, unit, YEARS[-1])):
            return "—"
        delta = float(kpis.loc[key, YEARS[-1]]) - float(kpis.loc[key, YEARS[0]])
        txt = {"pct": f"{delta:+.2f} pts", "x": f"{delta:+.2f}x", "icr": f"{delta:+.2f}x", "lakh": f"{delta:+.2f} L"}[unit]
        if abs(delta) < 0.005:
            arrow, col = "▶", PEWTER
        else:
            up = delta > 0
            arrow = "▲" if up else "▼"
            col = CYAN if good_up is None else (JADE if up == good_up else CRIMSON)
        return f'<span style="color:{col}">{arrow} {txt}</span>'

    matrix_rows: list[tuple[str, str, list[str]]] = []
    for spec in ratio_spec:
        if spec[0] == "section":
            matrix_rows.append(("section", spec[1], []))
            continue
        key, label, unit, good_up = spec
        matrix_rows.append(("row", label, [ratio_cell(key, unit, y) for y in YEARS] + [trend_cell(key, unit, good_up)]))
    st.markdown(render_table(["Strategic Ratio"] + YEARS + ["3-Yr Trend / Δ (FY24→FY26)"], matrix_rows), unsafe_allow_html=True)
    st.caption("ICR shows ∞ when there is no finance cost; effective tax rate shows n/a when PBT ≤ 0. "
               "Trend arrows are jade when the move is favorable, crimson when adverse, cyan when neutral.")

with tab4:
    st.markdown('<div class="section-h">Macroeconomic &amp; inflation <em>pass-through</em> shock simulator</div>'
                '<div class="section-sub">Shock FY26 input costs, wages and interest rates, choose how much of the pain is passed on to '
                'consumers, and watch the ₹100 receipt and every stakeholder payout re-balance.</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<div class="kpi-label">Shock Control Panel · applied to FY26 actuals</div>', unsafe_allow_html=True)
        p1, p2 = st.columns(2, gap="large")
        mat_inflation_pct = p1.slider("Raw Material & Supply Chain Inflation Shock (%)", min_value=-20.0, max_value=40.0, value=10.0,
                                      step=1.0, format="%.1f", key="sim_mat",
                                      help="Percentage change applied to FY26 Cost of Materials & Stock-in-Trade (COGS_MAT).")
        wage_hike_pct = p2.slider("Workforce Wage & Benefit Hike (%)", min_value=-10.0, max_value=30.0, value=8.0, step=1.0,
                                  format="%.1f", key="sim_wage", help="Percentage change applied to FY26 Employee Benefit Expenses (EMP_COST).")
        p3, p4 = st.columns(2, gap="large")
        rate_shock_bps = p3.slider("Interest Rate / Borrowing Cost Shock (bps)", min_value=-200, max_value=400, value=100, step=25,
                                   format="%d", key="sim_bps", help="Basis-point change applied to FY26 Total Debt (TOTAL_DEBT).")
        price_passthrough_pct = p4.slider("Consumer Price Pass-Through (%) · 0 = Company Absorbs All, 100 = Consumers Absorb All",
                                          min_value=0, max_value=100, value=35, step=5, format="%d", key="sim_pass",
                                          help="Share of total cost inflation recovered through higher prices on Revenue from Operations.")
        st.caption(f"Selected shocks: materials {mat_inflation_pct:+.1f}% · wages {wage_hike_pct:+.1f}% · "
                   f"rates {int(rate_shock_bps):+d} bps · pass-through {int(price_passthrough_pct)}%")

    if float(pnl.loc["Total_Income", "FY26"]) <= 0:
        st.warning("FY26 Total Income is zero or negative; the shock simulator needs a positive FY26 baseline.")
    else:
        sim = simulate_margin_shock(results, float(mat_inflation_pct), float(wage_hike_pct), float(rate_shock_bps),
                                    float(price_passthrough_pct))
        base_m, sim_m, shocks, rc = sim["baseline"], sim["simulated"], sim["shocks"], sim["receipt"]
        base_rc = rc.loc[RECEIPT_LABELS, "Baseline_FY26"].to_numpy(dtype="float64")
        sim_rc = rc.loc[RECEIPT_LABELS, "Simulated_FY26"].to_numpy(dtype="float64")
        rev_ops_26 = float(inputs.loc["REV_OPS", "FY26"])

        def sgn_cr(v: float, d: int = 2) -> str:
            return ("+" if v >= 0 else "") + fmt_cr(v, d)

        d_pat = sim_m["PAT"] - base_m["PAT"]
        d_pat_pct = d_pat / abs(base_m["PAT"]) * 100.0 if abs(base_m["PAT"]) > 0 else float("nan")
        d_roe = sim_m["ROE_Pct"] - base_m["ROE_Pct"]
        base_bite, sim_bite = float(base_rc[6] + base_rc[7]), float(sim_rc[6] + sim_rc[7])
        d_bite, be_pct = sim_bite - base_bite, float(sim["Breakeven_Price_Hike_Pct"])
        implied_hike = shocks["Delta_Rev"] / rev_ops_26 * 100.0 if rev_ops_26 > 0 else 0.0

        def delta_tone(d: float) -> str:
            return "t-green" if d > 1e-9 else ("t-red" if d < -1e-9 else "t-gold")

        st.markdown("<div style='height:.9rem'></div>", unsafe_allow_html=True)
        st.markdown(kpi_grid([
            kpi_card("Simulated FY26 PAT vs Baseline", fmt_cr(sim_m["PAT"]), f"Baseline {fmt_cr(base_m['PAT'])}",
                     f"Δ {sgn_cr(d_pat)} ({fmt_pct(d_pat_pct, 1, True)})", delta_tone(d_pat)),
            kpi_card("Simulated ROE vs Baseline", fmt_pct(sim_m["ROE_Pct"], 2), f"Baseline {fmt_pct(base_m['ROE_Pct'], 2)}",
                     f"Δ {d_roe:+.2f} pts", delta_tone(d_roe)),
            kpi_card("Consumer Net Profit Bite", f"{fmt_rs(sim_bite)} per ₹100", f"Baseline {fmt_rs(base_bite)} per ₹100",
                     f"Δ {d_bite * 100:+.0f} paise", delta_tone(d_bite)),
            kpi_card("Break-Even Price Hike (0% Pass-Through)", fmt_pct(be_pct, 2),
                     f"Cost inflation {fmt_cr(sim['Total_Cost_Inflation'], 0)} ÷ FY26 revenue",
                     f"Selected pass-through = {implied_hike:.2f}% price hike",
                     "t-green" if be_pct <= 0 else ("t-amber" if be_pct < 5.0 else "t-red")),
        ]), unsafe_allow_html=True)

        base_stake = vas_abs["FY26"].to_numpy(dtype="float64")
        sim_stake = np.array([float(inputs.loc["EMP_COST", "FY26"]) + shocks["Delta_Emp"],
                              float(inputs.loc["FIN_COST", "FY26"]) + shocks["Delta_Fin"], sim_m["Tax_Expense"],
                              float(inputs.loc["DIV_PAID", "FY26"]),
                              sim_m["Retained_Earnings"] + float(inputs.loc["DEP_AMORT", "FY26"])], dtype="float64")

        sc_left, sc_right = st.columns([1.6, 1], gap="large")
        with sc_left:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=STAKE_BR, y=base_stake, name="Baseline FY26", marker_color=PEWTER, texttemplate="%{y:,.0f}",
                                 textposition="outside", cliponaxis=False,
                                 hovertemplate="<b>%{x}</b><br>Baseline: ₹%{y:,.2f} Cr<extra></extra>"))
            fig.add_trace(go.Bar(x=STAKE_BR, y=sim_stake, name="Simulated FY26", marker_color=GOLD, customdata=sim_stake - base_stake,
                                 texttemplate="%{y:,.0f}", textposition="outside", cliponaxis=False,
                                 hovertemplate="<b>%{x}</b><br>Simulated: ₹%{y:,.2f} Cr<br>Δ vs baseline: %{customdata:+,.2f} Cr<extra></extra>"))
            style_fig(fig, "Stakeholder Payouts · Baseline vs Simulated FY26 (₹ Cr)", 440)
            fig.update_layout(barmode="group", xaxis=dict(tickangle=0),
                              yaxis=dict(tickprefix="₹", ticksuffix=" Cr", range=pad_range(base_stake, sim_stake)), legend=LEG_BELOW)
            show_chart(fig, "t4_payout_chart")
            closure_sim = bool(sim["vas_closure_check"])
            st.caption(f"Baseline GVA {fmt_cr(base_m['GVA'])} → Simulated GVA {fmt_cr(sim_m['GVA'])} · "
                       f"Simulated VAS closure (Σ 5 stakeholders = GVA): {'Verified ✅' if closure_sim else 'Breach ⚠️'}")

        with sc_right:
            shock_rows = [("Δ Materials & supply chain", shocks["Delta_COGS"]), ("Δ Workforce wages & benefits", shocks["Delta_Emp"]),
                          ("Δ Finance cost (bps × debt)", shocks["Delta_Fin"])]
            shock_html = "".join(f'<div class="receipt-row"><span>{html.escape(n)}</span><span class="amt">{sgn_cr(float(v))}</span></div>'
                                 for n, v in shock_rows)
            st.markdown('<div class="receipt"><div class="receipt-head">SHOCK DECOMPOSITION</div>'
                        f'<div class="receipt-meta">FY26 baseline · ₹ Crores</div>{shock_html}'
                        f'<div class="receipt-total"><span>TOTAL COST INFLATION</span><span>{sgn_cr(shocks["Total_Cost_Inflation"])}</span></div>'
                        '<div class="receipt-row"><span>Revenue offset via price pass-through</span>'
                        f'<span class="amt" style="color:{JADE}">{sgn_cr(shocks["Delta_Rev"])}</span></div>'
                        '<div class="receipt-row"><span>Unrecovered cost absorbed by company</span>'
                        f'<span class="amt" style="color:{CRIMSON}">{sgn_cr(shocks["Unrecovered_Cost"])}</span></div>'
                        f'<div class="receipt-meta" style="margin-top:.8rem">Pass-through {int(price_passthrough_pct)}% · '
                        f'Baseline tax rate {sim["assumptions"]["baseline_effective_tax_rate_pct"]:.2f}%<br>'
                        f'{html.escape(sim["assumptions"]["dividend_policy"])}</div>' + RECEIPT_STAMP + '</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-h">₹100 consumer receipt · <em>before vs after</em> the shock</div>', unsafe_allow_html=True)

        def receipt_card(title: str, vals: np.ndarray, deltas, ok: bool) -> str:
            body = ""
            for i in range(8):
                dtxt = ""
                if deltas is not None:
                    d = float(deltas[i])
                    col = PEWTER if abs(d) < 0.005 else ((JADE if d > 0 else CRIMSON) if i >= 6 else (CRIMSON if d > 0 else JADE))
                    dtxt = f'<span style="color:{col};margin-left:.6rem;font-size:.72rem">{d:+.2f}</span>'
                body += (f'<div class="receipt-row"><span><span class="dot" style="background:{RECEIPT_COLORS[i]}"></span>'
                         f'{html.escape(RECEIPT_NAMES[i])}</span><span class="amt">{fmt_rs(float(vals[i]))}{dtxt}</span></div>')
            return (f'<div class="receipt"><div class="receipt-head">{html.escape(title)}</div>'
                    f'<div class="receipt-meta">Amount paid by customer: ₹100.00</div>{body}'
                    f'<div class="receipt-total"><span>TOTAL ALLOCATED</span><span>{fmt_rs(float(np.sum(vals)))} {"✅" if ok else "⚠️"}</span></div>' + RECEIPT_STAMP + '</div>')

        rcpt_ok = bool(sim["receipt_check"]["all_ok"])
        r_left, r_right = st.columns(2, gap="large")
        r_left.markdown(receipt_card("BASELINE ₹100 SPLIT · FY26", base_rc, None, rcpt_ok), unsafe_allow_html=True)
        r_right.markdown(receipt_card("POST-SHOCK ₹100 SPLIT · FY26", sim_rc, sim_rc - base_rc, rcpt_ok), unsafe_allow_html=True)

        st.markdown('<div class="section-h">Scenario <em>P&amp;L</em> comparison</div>', unsafe_allow_html=True)
        cmp_df = sim["comparison"]

        def cmp_row(key: str, label: str, unit: str) -> tuple[str, str, list[str]]:
            b, s = float(cmp_df.loc[key, "Baseline_FY26"]), float(cmp_df.loc[key, "Simulated_FY26"])
            if unit == "cr":
                d = s - b
                pc = f" ({d / abs(b) * 100.0:+.1f}%)" if abs(b) > 0 else ""
                return ("row", label, [fmt_cr(b), fmt_cr(s), sgn_cr(d) + pc])
            if unit == "icr":
                if b >= 999.0 or s >= 999.0:
                    return ("row", label, ["∞" if b >= 999.0 else f"{b:.2f}x", "∞" if s >= 999.0 else f"{s:.2f}x", "—"])
                return ("row", label, [f"{b:.2f}x", f"{s:.2f}x", f"{s - b:+.2f}x"])
            return ("row", label, [fmt_pct(b, 2), fmt_pct(s, 2), f"{s - b:+.2f} pts"])

        cmp_rows = [cmp_row("Total_Income", "Total Income", "cr"), cmp_row("GVA", "Gross Value Added (GVA)", "cr"),
                    cmp_row("EBITDA", "EBITDA", "cr"), cmp_row("EBIT", "EBIT", "cr"), cmp_row("PBT", "Profit Before Tax (PBT)", "cr"),
                    cmp_row("Tax_Expense", "Tax Expense", "cr"), cmp_row("PAT", "Profit After Tax (PAT)", "cr"),
                    cmp_row("GVA_Margin_Pct", "GVA Margin", "pct"), cmp_row("EBITDA_Margin_Pct", "EBITDA Margin", "pct"),
                    cmp_row("PAT_Margin_Pct", "PAT Margin", "pct"), cmp_row("ROE_Pct", "ROE", "pct"),
                    cmp_row("Interest_Coverage_Ratio", "Interest Coverage Ratio", "icr")]
        st.markdown(render_table(["Metric (FY26)", "Baseline", "Simulated", "Change"], cmp_rows), unsafe_allow_html=True)
        st.caption("The simulator always uses FY26 as its baseline, regardless of the Active Fiscal Year selector.")

with tab5:
    st.markdown('<div class="section-h">Glass-box formula audit &amp; <em>live reconciliation</em> verifier</div>'
                '<div class="section-sub">Every headline number re-derived by an independent step-by-step hand calculation '
                f'for {active_fy}, then compared against the vectorized engine output.</div>', unsafe_allow_html=True)
    fy_in = {k: float(inputs.loc[k, active_fy]) for k in inputs.index}
    h_total_income = fy_in["REV_OPS"] + fy_in["REV_OTH"]
    h_bought = fy_in["COGS_MAT"] + fy_in["OPEX_EXT"]
    h_gva = h_total_income - h_bought
    h_ebit = h_gva - fy_in["EMP_COST"] - fy_in["DEP_AMORT"]
    h_pbt = h_ebit - fy_in["FIN_COST"]
    h_pat = h_pbt - fy_in["TAX_EXP"]
    h_ret = h_pat - fy_in["DIV_PAID"]
    h_stake_sum = fy_in["EMP_COST"] + fy_in["FIN_COST"] + fy_in["TAX_EXP"] + fy_in["DIV_PAID"] + (h_ret + fy_in["DEP_AMORT"])
    h_parts = [fy_in["COGS_MAT"], fy_in["OPEX_EXT"], fy_in["EMP_COST"], fy_in["DEP_AMORT"], fy_in["FIN_COST"],
               fy_in["TAX_EXP"], fy_in["DIV_PAID"], h_ret]
    h_receipt = sum(p / h_total_income * 100.0 for p in h_parts)
    e_gva, e_stake, e_receipt = float(pnl.loc["GVA", active_fy]), float(vas_abs[active_fy].sum()), float(cs[active_fy].sum())
    e_ebit, e_ret = float(pnl.loc["EBIT", active_fy]), float(pnl.loc["Retained_Earnings", active_fy])

    identities = [("1. GVA = Total Income − (COGS_MAT + OPEX_EXT)", e_gva, h_gva, "cr"),
                  ("2. VAS Closure: Σ 5 Stakeholder Allocations = GVA", e_stake, h_gva, "cr"),
                  ("3. ₹100 Receipt Closure: Σ 8 Components = ₹100.00", e_receipt, h_receipt, "rs"),
                  ("4. EBIT = GVA − EMP_COST − DEP_AMORT", e_ebit, h_ebit, "cr"),
                  ("5. Retained Earnings = PAT − DIV_PAID", e_ret, h_ret, "cr")]
    id_rows: list[tuple[str, str, list[str]]] = []
    n_ok = 0
    for name, eng, hand, unit in identities:
        var = eng - hand
        ok = abs(var) < 1e-4
        n_ok += int(ok)
        eng_txt = fmt_cr(eng, 4) if unit == "cr" else _money(eng, 4, "")
        hand_txt = fmt_cr(hand, 4) if unit == "cr" else _money(hand, 4, "")
        var_txt = "0.0000" if abs(var) < 5e-5 else f"{var:+.4f}"
        badge = ('<span class="kpi-badge t-green">✅ Verified Match</span>' if ok
                 else '<span class="kpi-badge t-red">❌ Variance Detected</span>')
        id_rows.append(("row", name, [eng_txt, hand_txt, var_txt, badge]))

    banner_tone = "t-green" if n_ok == len(identities) else "t-red"
    banner_txt = (f"All {len(identities)} accounting identities verified for {active_fy}." if n_ok == len(identities)
                  else f"{len(identities) - n_ok} of {len(identities)} identities show a variance for {active_fy}.")
    st.markdown(f'<div class="diag-card {banner_tone}" style="min-height:0;margin-bottom:1rem">'
                '<div class="diag-head"><span class="diag-title">Live Mathematical Closure &amp; Identity Verifier</span>'
                f'<span class="diag-pill">{n_ok} / {len(identities)} VERIFIED</span></div>'
                f'<div class="diag-text">{html.escape(banner_txt)} Tolerance: |variance| &lt; 0.0001.</div></div>', unsafe_allow_html=True)
    st.markdown(render_table(["Identity", "Engine Vectorized Output", "Independent Hand Calculation", "Variance", "Status"], id_rows),
                unsafe_allow_html=True)

    if live_meta is not None:
        st.markdown('<div class="section-h">Yahoo Finance <em>reconciliation bridge</em></div>'
                    '<div class="section-sub">Reported Yahoo Finance anchors against the MEROS Schedule III ladder built from the '
                    'current verification grid. Variances appear only if you override cells with auto-rebalance off.</div>', unsafe_allow_html=True)
        st.markdown(bridge_html, unsafe_allow_html=True)

    trace_lines = [
        f"[1] GVA = ({fy_in['REV_OPS']:,.4f} + {fy_in['REV_OTH']:,.4f}) - ({fy_in['COGS_MAT']:,.4f} + {fy_in['OPEX_EXT']:,.4f})"
        f" = {h_total_income:,.4f} - {h_bought:,.4f} = {h_gva:,.4f}",
        f"[2] Σ stakeholders = EMP {fy_in['EMP_COST']:,.4f} + FIN {fy_in['FIN_COST']:,.4f} + TAX {fy_in['TAX_EXP']:,.4f}"
        f" + DIV {fy_in['DIV_PAID']:,.4f} + (RE {h_ret:,.4f} + DEP {fy_in['DEP_AMORT']:,.4f}) = {h_stake_sum:,.4f}  vs  GVA {h_gva:,.4f}",
        f"[3] Σ (component ÷ Total Income × 100) over 8 components = {h_receipt:.10f}  (engine paise-allocated sum = {e_receipt:.4f})",
        f"[4] EBIT = {h_gva:,.4f} - {fy_in['EMP_COST']:,.4f} - {fy_in['DEP_AMORT']:,.4f} = {h_ebit:,.4f}",
        f"[5] PBT = {h_ebit:,.4f} - {fy_in['FIN_COST']:,.4f} = {h_pbt:,.4f};  PAT = {h_pbt:,.4f} - {fy_in['TAX_EXP']:,.4f}"
        f" = {h_pat:,.4f};  Retained = {h_pat:,.4f} - {fy_in['DIV_PAID']:,.4f} = {h_ret:,.4f}",
    ]
    with st.expander("Step-by-step hand-calculation trace"):
        st.code("\n".join(trace_lines), language="text")

    st.markdown('<div class="section-h">Data hygiene <em>repair log</em></div>', unsafe_allow_html=True)
    with st.expander(f"Ingestion repairs · {audit['cells_repaired']} of {audit['total_cells']} cells ({audit['repair_pct']:.2f}%)"):
        h1, h2, h3 = st.columns(3)
        h1.metric("Total cells audited", audit["total_cells"])
        h2.metric("Cells repaired", audit["cells_repaired"])
        h3.metric("Repair rate", f"{audit['repair_pct']:.2f}%")
        if audit["repair_log"]:
            st.code("\n".join(audit["repair_log"]), language="text")
        else:
            st.caption("No repairs were required: input was already clean.")
        pv_raw, pv_clean = st.columns(2, gap="medium")
        with pv_raw:
            st.caption("Raw ingested data (as received)")
            st.dataframe(raw_df.map(preview_cell), hide_index=True)
        with pv_clean:
            st.caption("Cleaned data (float64, indexed by Line_ID)")
            st.dataframe(clean_df.reset_index(), hide_index=True)

    st.markdown('<div class="section-h">Exact <em>vectorized</em> formulas</div>', unsafe_allow_html=True)
    code_gva = """Total_Income    = REV_OPS + REV_OTH
Bought_In_Costs = COGS_MAT + OPEX_EXT
GVA             = Total_Income - Bought_In_Costs

EBITDA            = GVA - EMP_COST
EBIT              = EBITDA - DEP_AMORT
PBT               = EBIT - FIN_COST
PAT               = PBT - TAX_EXP
Retained_Earnings = PAT - DIV_PAID"""
    code_nva = """NVA = GVA - DEP_AMORT

def _safe_div(num, den, fill=0.0, positive_only=True):
    n = np.asarray(num, dtype="float64")
    d = np.asarray(den, dtype="float64")
    mask = (d > 0) if positive_only else (d != 0)
    safe_d = np.where(mask, d, 1.0)
    return np.where(mask, n / safe_d, fill)

Implied_Cost_of_Debt_Pct = np.where(TOTAL_DEBT > 0, FIN_COST / np.where(TOTAL_DEBT > 0, TOTAL_DEBT, 1.0) * 100.0, 0.0)
Interest_Coverage_Ratio  = np.where(FIN_COST > 0, EBIT / np.where(FIN_COST > 0, FIN_COST, 1.0), 999.0)
ROCE_Pct                 = _safe_div(EBIT, TOTAL_DEBT + TOTAL_EQUITY) * 100.0"""
    code_stake = """stake_mat = np.vstack([EMP_COST, FIN_COST, TAX_EXP, DIV_PAID, Retained_Earnings + DEP_AMORT])
residual  = GVA - stake_mat.sum(axis=0)
vas_closure_check = bool(np.all(np.abs(residual) < 1e-4))
pct_of_gva = _safe_div(stake_mat, GVA) * 100.0

components = np.vstack([COGS_MAT, OPEX_EXT, EMP_COST, DEP_AMORT, FIN_COST, TAX_EXP, DIV_PAID, Retained_Earnings])
exact      = _safe_div(components * 100.0, Total_Income)
raw_paise  = exact * 100.0
floors     = np.floor(raw_paise)
deficit    = np.rint(10000.0 - floors.sum(axis=0)).astype("int64")
ranks      = np.argsort(np.argsort(-(raw_paise - floors), axis=0, kind="stable"), axis=0, kind="stable")
paise      = floors.astype("int64") + (ranks < deficit).astype("int64")   # each column sums to 10,000 paise
rupees     = paise / 100.0"""
    code_sim = """Delta_COGS           = COGS_MAT   * (mat_inflation_pct / 100.0)
Delta_Emp            = EMP_COST   * (wage_hike_pct / 100.0)
Delta_Fin            = TOTAL_DEBT * (rate_shock_bps / 10000.0)
Total_Cost_Inflation = Delta_COGS + Delta_Emp + Delta_Fin
Delta_Rev            = Total_Cost_Inflation * (price_passthrough_pct / 100.0)

sim_rev_ops = REV_OPS + Delta_Rev
pre_tax = ladder(sim_rev_ops, REV_OTH, COGS_MAT + Delta_COGS, OPEX_EXT, EMP_COST + Delta_Emp, DEP_AMORT, FIN_COST + Delta_Fin, 0.0, DIV_PAID)
base_tax_rate = Effective_Tax_Rate_Pct_FY26 / 100.0
sim_tax = np.where(pre_tax["PBT"] > 0, pre_tax["PBT"] * base_tax_rate, 0.0)
sim = ladder(sim_rev_ops, REV_OTH, COGS_MAT + Delta_COGS, OPEX_EXT, EMP_COST + Delta_Emp, DEP_AMORT, FIN_COST + Delta_Fin, sim_tax, DIV_PAID)

Sim_ROE_Pct              = _safe_div(sim["PAT"], TOTAL_EQUITY) * 100.0
Breakeven_Price_Hike_Pct = _safe_div(Total_Cost_Inflation, REV_OPS) * 100.0   # hike needed to hold PBT at 0% pass-through"""
    st.markdown("**Gross Value Added (GVA) and the P&L ladder**")
    st.code(code_gva, language="python")
    st.markdown("**Net Value Added (NVA), guarded ratios and credit metrics**")
    st.code(code_nva, language="python")
    st.markdown("**Stakeholder shares of GVA and the ₹100 common-size receipt**")
    st.code(code_stake, language="python")
    st.markdown("**Inflation pass-through simulation**")
    st.code(code_sim, language="python")

st.markdown(COLOPHON, unsafe_allow_html=True)
