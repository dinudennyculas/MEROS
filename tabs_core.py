"""MEROS screens 1-3 (₹100 anatomy, value-added statement, workforce / capital / DuPont / EVA).

Each render_tabN(ctx) draws one screen for ANY number of years. ctx is a dict built by app.py:
  cd            windowed company data (source, years, period_labels, opening, is_financial, ...)
  results       corporate_engine.compute_corporate_anatomy_and_vas(...)
  active_fy     the selected year label (one of results['years'])
  source_label  text shown on receipts
  emp_state     'reported' | 'partial' | 'not_reported' | 'user'
  ke_pct        cost of equity in %
  capital       analytics.capital_returns(...)
  dupont        analytics.dupont(...)
  dupont_change {'3': analytics.dupont_change(...), '5': ...}
  notes         analytics.plain_notes(...)
  diagnostics   corporate_engine.generate_deterministic_diagnostics(...)
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from analytics import CAP_LAYOUT, DUPONT_FACTOR_NAMES, DUPONT_LAYOUT
from corporate_engine import STAKEHOLDER_LABELS
from ui_style import (CHAMPAGNE, CRIMSON, CYAN, GOLD, JADE, LEG_BELOW, PEWTER, RECEIPT_COLORS, RECEIPT_NAMES, STAKE_COLORS,
                      STAKE_SHORT, VIOLET, WF_FULL, WF_TICKS, diag_cards_html, esc, fmt_cr, fmt_lakh, fmt_pct, fmt_rs, fmt_unit,
                      fmt_x, kpi_card, kpi_grid, notice_html, pad_range, receipt_html, receipt_row, render_table, show_chart, style_fig)


def _head(title_html: str, sub: str) -> None:
    st.markdown(f'<div class="section-h">{title_html}</div><div class="section-sub">{sub}</div>', unsafe_allow_html=True)


def _f(v: object) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _any_finite(*arrs: object) -> bool:
    return any(bool(np.isfinite(np.asarray(a, dtype="float64")).any()) for a in arrs)


# --------------------------------------------------------------------------------------
# Tab 1: where does your ₹100 go
# --------------------------------------------------------------------------------------
def render_tab1(ctx: dict) -> None:
    res, fy, label = ctx["results"], ctx["active_fy"], ctx["source_label"]
    years, cs = res["years"], res["common_size"]
    n = len(years)
    _head('Where does your <em>₹100</em> actually go?',
          f"Every ₹100 of {esc(fy)} total income, traced from the customer's wallet to suppliers, staff, lenders, the state, shareholders "
          "and the company's own reserves.")
    col_chart, col_receipt = st.columns([1.35, 1], gap="large")
    fy_cs = cs[fy].to_numpy(dtype="float64")

    with col_chart:
        view = st.radio("Chart view", ["Waterfall (active year)", "Stacked bars (all years)"], horizontal=True,
                        label_visibility="collapsed", key="t1_view")
        if view.startswith("Waterfall"):
            cum = np.concatenate([[0.0], np.cumsum(fy_cs[:7])])
            wf_base = [0.0] + [float(100.0 - cum[i + 1]) for i in range(7)] + [0.0]
            wf_h = [100.0] + [float(v) for v in fy_cs[:7]] + [float(fy_cs[7])]
            wf_text = ["₹100.00"] + [fmt_rs(-float(v)) for v in fy_cs[:7]] + [fmt_rs(float(fy_cs[7]))]
            wf_hover = ["₹100.00 paid by the customer"] + [f"{fmt_rs(float(v))} of every ₹100" for v in fy_cs]
            fig = go.Figure(go.Bar(x=WF_TICKS, y=wf_h, base=wf_base, marker_color=[GOLD] + RECEIPT_COLORS, text=wf_text,
                                   textposition="outside", cliponaxis=False,
                                   customdata=[[nm, h] for nm, h in zip(WF_FULL, wf_hover)],
                                   hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>"))
            style_fig(fig, f"₹100.00 Customer Spend Decomposition · {fy}", 480)
            fig.update_layout(showlegend=False, xaxis=dict(tickangle=0, tickfont=dict(size=10)),
                              yaxis=dict(tickprefix="₹", range=pad_range(wf_base, np.array(wf_base) + np.array(wf_h))))
        else:
            fig = go.Figure()
            for i in range(8):
                vals = cs.iloc[i][years].to_numpy(dtype="float64")
                fig.add_trace(go.Bar(y=years, x=vals, orientation="h", name=RECEIPT_NAMES[i], marker_color=RECEIPT_COLORS[i],
                                     text=[f"{v:.1f}" if abs(v) >= 3.0 else "" for v in vals], textposition="inside",
                                     textfont=dict(color="#0A0A0C"),
                                     hovertemplate="<b>%{fullData.name}</b><br>%{y}: ₹%{x:.2f} per ₹100<extra></extra>"))
            style_fig(fig, f"Common-Size ₹100 Anatomy · {years[0]} to {years[-1]}", max(480, 150 + 36 * n))
            fig.update_layout(barmode="stack", yaxis=dict(autorange="reversed"), xaxis=dict(tickprefix="₹"), legend=LEG_BELOW)
        show_chart(fig, "t1_main_chart")

    with col_receipt:
        rows_html = "".join(receipt_row(RECEIPT_NAMES[i], RECEIPT_COLORS[i], fmt_rs(fy_cs[i])) for i in range(8))
        ok_fy = bool(res["receipt_check"]["ok_by_year"][fy])
        meta = f"{esc(label)} · {esc(fy)}<br>Amount paid by customer: ₹100.00"
        st.markdown(receipt_html("CONSUMER ITEMIZED RECEIPT", meta, rows_html, "TOTAL ALLOCATED", fmt_rs(fy_cs.sum()), ok_fy), unsafe_allow_html=True)
        emp_state = ctx.get("emp_state", "reported")
        if emp_state in ("not_reported", "partial"):
            where = "all years" if emp_state == "not_reported" else "some years"
            st.markdown(notice_html([f"Employee cost is not reported by the data source for {where}, so the Workforce line above is not real. "
                                     "The true payroll sits inside the Vendors & operations line, so treat the split between those two as unknown."],
                                    head="WORKFORCE LINE "), unsafe_allow_html=True)
        if st.toggle(f"Show common-size comparison for all {n} years", value=False, key="t1_cmp"):
            rows: list[tuple[str, str, list[str]]] = []
            for i in range(8):
                v = cs.iloc[i][years].to_numpy(dtype="float64")
                rows.append(("row", RECEIPT_NAMES[i], [fmt_rs(x) for x in v] + [f"{v[-1] - v[0]:+.2f}"]))
            tot = cs[years].sum(axis=0).to_numpy(dtype="float64")
            rows.append(("total", "Total per ₹100", [fmt_rs(x) for x in tot] + [""]))
            st.markdown(render_table(["Per ₹100 spent"] + list(years) + [f"Δ {years[0]}→{years[-1]}"], rows), unsafe_allow_html=True)


# --------------------------------------------------------------------------------------
# Tab 2: stakeholder value-added statement
# --------------------------------------------------------------------------------------
def render_tab2(ctx: dict) -> None:
    res, fy = ctx["results"], ctx["active_fy"]
    years, pnl, inputs = res["years"], res["pnl"], res["inputs"]
    vas_abs, vas_pct = res["vas_abs"], res["vas_pct"]
    gva_fy = _f(pnl.loc["GVA", fy])
    closure_txt = "Verified ✅" if res["vas_closure_check"] else "Breach ⚠️"
    _head('Stakeholder value-added statement &amp; <em>drift over time</em>',
          "Rule-based diagnostics, then how the Gross Value Added pie is sliced among workforce, lenders, the state, shareholders "
          "and the enterprise itself.")
    st.markdown(diag_cards_html(ctx["diagnostics"]), unsafe_allow_html=True)

    c_left, c_right = st.columns([1.4, 1], gap="large")
    with c_left:
        fig = go.Figure()
        for i in range(5):
            pcts = vas_pct.iloc[i][years].to_numpy(dtype="float64")
            amts = [fmt_cr(x) for x in vas_abs.iloc[i][years].to_numpy(dtype="float64")]
            fig.add_trace(go.Bar(x=years, y=pcts, name=STAKE_SHORT[i], marker_color=STAKE_COLORS[i], customdata=amts,
                                 text=[f"{p:.1f}%" if abs(p) >= 3.0 else "" for p in pcts], textposition="inside",
                                 textfont=dict(color="#0A0A0C", size=10 if len(years) > 6 else 12),
                                 hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.2f}% of GVA<br>%{customdata}<extra></extra>"))
        style_fig(fig, "How the GVA Pie Shifted · 100% Stacked", 420)
        fig.update_layout(barmode="stack", yaxis=dict(ticksuffix="%"), legend=LEG_BELOW)
        show_chart(fig, "t2_stacked_chart")

    with c_right:
        raw_vals = vas_abs[fy].to_numpy(dtype="float64")
        pie_vals = np.clip(raw_vals, 0.0, None)
        if pie_vals.sum() <= 0:
            st.warning(f"GVA for {fy} is not positive, so there is no distributable value to chart.")
        else:
            fig = go.Figure(go.Pie(labels=STAKE_SHORT, values=pie_vals, hole=0.62, sort=False, direction="clockwise",
                                   marker=dict(colors=STAKE_COLORS, line=dict(color="#0A0A0C", width=2)), textinfo="percent",
                                   textfont=dict(family="JetBrains Mono, monospace", color="#0A0A0C"),
                                   hovertemplate="<b>%{label}</b><br>₹%{value:,.2f} Cr<br>%{percent} of GVA<extra></extra>"))
            style_fig(fig, f"{fy} GVA Distribution", 420)
            fig.update_layout(showlegend=False)
            fig.add_annotation(text=f"<b>GVA</b><br>{fmt_cr(gva_fy)}", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
                               font=dict(size=13, family="JetBrains Mono, monospace", color=GOLD))
            show_chart(fig, "t2_donut_chart")
            if (raw_vals < 0).any():
                st.caption("Negative components (loss-absorbing items) are left out of the donut; see the table below.")

    st.markdown('<div class="section-h">Corporate value-added statement <em>(reconciliation)</em></div>', unsafe_allow_html=True)

    def ser(s) -> list[str]:
        return [fmt_rs(float(s[y])) for y in years]

    nva_pct = _f(pnl.loc["NVA", fy]) / gva_fy * 100.0 if gva_fy > 0 else float("nan")
    dash = ["—"]
    rows: list[tuple[str, str, list[str]]] = [
        ("section", "A. GENERATION OF GROSS VALUE ADDED", []),
        ("row", "Revenue from Operations", ser(pnl.loc["Revenue_from_Operations"]) + dash),
        ("row", "Add: Other Income", ser(pnl.loc["Other_Income"]) + dash),
        ("subtotal", "Total Income", ser(pnl.loc["Total_Income"]) + dash),
        ("row", "Less: Cost of Materials & Stock-in-Trade", ser(inputs.loc["COGS_MAT"]) + dash),
        ("row", "Less: Other Operating Expenses (Freight, Power, Marketing, Vendors)", ser(inputs.loc["OPEX_EXT"]) + dash),
        ("subtotal", "Total Bought-In Goods & Services", ser(pnl.loc["Bought_In_Costs"]) + dash),
        ("total", "Gross Value Added (GVA)", ser(pnl.loc["GVA"]) + ["100.00%"]),
        ("section", "B. APPLICATION OF GROSS VALUE ADDED", []),
    ]
    for i in range(5):
        rows.append(("row", STAKEHOLDER_LABELS[i], ser(vas_abs.iloc[i]) + [fmt_pct(_f(vas_pct.iloc[i][fy]), 2)]))
        if i == 4:
            rows.append(("memo", "   of which: Retained Earnings (profit after tax − dividends)", ser(pnl.loc["Retained_Earnings"]) + dash))
            rows.append(("memo", "   of which: Depreciation & Amortization", ser(pnl.loc["Depreciation_Amortization"]) + dash))
            rows.append(("memo", "   memo: profit attributable to shareholders (after minority interest)", ser(pnl.loc["PAT_Attributable"]) + dash))
    rows += [
        ("total", "Total Application of GVA (Σ 5 Stakeholders)", ser(vas_abs.sum(axis=0)) + [fmt_pct(_f(vas_pct[fy].sum()), 2)]),
        ("memo", "Net Value Added (NVA = GVA − Depreciation)", ser(pnl.loc["NVA"]) + [fmt_pct(nva_pct, 2)]),
        ("memo", "Closure residual (GVA − Σ Stakeholders)", [f"{res['vas_residual'][y]:.6f}" for y in years] + [closure_txt]),
    ]
    st.markdown(render_table(["Particulars (₹ Cr)"] + list(years) + [f"% of GVA ({fy})"], rows), unsafe_allow_html=True)
    st.caption("Accounting identity: GVA = Employee Cost + Finance Cost + Tax + Dividends + (Retained Earnings + Depreciation). "
               "Retained earnings include the minority shareholders' share of profit; the memo row shows profit attributable to shareholders.")


# --------------------------------------------------------------------------------------
# Tab 3: workforce, capital efficiency, DuPont, EVA
# --------------------------------------------------------------------------------------
def _ret_tone(v: float) -> str:
    if not np.isfinite(v):
        return "t-mute"
    return "t-green" if v >= 15.0 else ("t-gold" if v >= 8.0 else ("t-amber" if v > 0.0 else "t-red"))


RATIO_SPEC: list[tuple] = [
    ("section", "PROFITABILITY & VALUE CREATION"),
    ("GVA_Margin_Pct", "GVA Margin (GVA ÷ Total Income)", "pct", True),
    ("EBITDA_Margin_Pct", "EBITDA Margin", "pct", True),
    ("PAT_Margin_Pct", "PAT Margin", "pct", True),
    ("section", "WORKFORCE PRODUCTIVITY"),
    ("Human_Capital_ROI", "Human Capital ROI (Revenue ÷ Employee Cost)", "x", True),
    ("Value_Added_Per_Emp_Lakhs", "Value Added per Employee (₹ L)", "lakh", True),
    ("section", "CAPITAL EFFICIENCY"),
    ("ROCE_Pct", "ROCE (EBIT ÷ Capital Employed)", "pct", True),
    ("ROE_Pct", "ROE (attributable profit ÷ Equity)", "pct", True),
    ("Implied_Cost_of_Debt_Pct", "Implied Cost of Debt", "pct", False),
    ("section", "CREDIT & TAX"),
    ("Interest_Coverage_Ratio", "Interest Coverage Ratio (EBIT ÷ Finance Cost)", "icr", True),
    ("Effective_Tax_Rate_Pct", "Effective Tax Rate (Tax ÷ PBT)", "pct", None),
]


def _ratio_cell(key: str, unit: str, yr: str, kpis, pnl) -> str:
    v = _f(kpis.loc[key, yr])
    if key == "Effective_Tax_Rate_Pct" and _f(pnl.loc["PBT", yr]) <= 0:
        return "n/a"
    if not np.isfinite(v):
        return "n/a"
    if unit == "icr":
        return "∞" if v >= 999.0 else f"{v:.2f}x"
    if unit == "pct":
        return fmt_pct(v, 2)
    if unit == "x":
        return fmt_x(v)
    return fmt_lakh(v, 2)


def _ratio_trend(key: str, unit: str, good_up, years: list[str], kpis, pnl) -> str:
    a, b = _f(kpis.loc[key, years[0]]), _f(kpis.loc[key, years[-1]])
    if not (np.isfinite(a) and np.isfinite(b)):
        return "—"
    if unit == "icr" and (a >= 999.0 or b >= 999.0):
        return "—"
    if key == "Effective_Tax_Rate_Pct" and (_f(pnl.loc["PBT", years[0]]) <= 0 or _f(pnl.loc["PBT", years[-1]]) <= 0):
        return "—"
    delta = b - a
    txt = {"pct": f"{delta:+.2f} pts", "x": f"{delta:+.2f}x", "icr": f"{delta:+.2f}x", "lakh": f"{delta:+.2f} L"}[unit]
    if abs(delta) < 0.005:
        arrow, col = "▶", PEWTER
    else:
        up = delta > 0
        arrow = "▲" if up else "▼"
        col = CYAN if good_up is None else (JADE if up == good_up else CRIMSON)
    return f'<span style="color:{col}">{arrow} {txt}</span>'


def _attribution_fig(d: dict, title: str) -> go.Figure:
    keys = d["keys"]
    names = [DUPONT_FACTOR_NAMES.get(k, k).replace(" burden", "<br>burden").replace(" margin", "<br>margin") for k in keys] + ["Total<br>ROE change"]
    vals = [d["contrib"][k] for k in keys] + [d["total"]]
    colors = [JADE if v >= 0 else CRIMSON for v in vals[:-1]] + [GOLD]
    fig = go.Figure(go.Bar(x=names, y=vals, marker_color=colors, text=[f"{v:+.1f}" for v in vals], textposition="outside", cliponaxis=False,
                           hovertemplate="<b>%{x}</b><br>%{y:+.2f} percentage points of ROE<extra></extra>"))
    style_fig(fig, f"{title} · {d['first']} → {d['last']}: ROE {d['roe_first']:.1f}% → {d['roe_last']:.1f}%", 400)
    fig.update_layout(showlegend=False, xaxis=dict(tickangle=0, tickfont=dict(size=10)),
                      yaxis=dict(ticksuffix=" pp", range=pad_range(vals)))
    return fig


def render_tab3(ctx: dict) -> None:
    res, fy = ctx["results"], ctx["active_fy"]
    years, kpis, pnl, inputs = res["years"], res["kpis"], res["pnl"], res["inputs"]
    n = len(years)
    cap, dp, nt, cd = ctx["capital"], ctx["dupont"], ctx["notes"], ctx["cd"]
    ke = float(ctx["ke_pct"])
    emp_state = ctx.get("emp_state", "reported")
    _head('Workforce productivity, <em>capital efficiency</em>, DuPont &amp; EVA',
          "Does each employee create more value than they cost, does every rupee of capital earn more than it is charged, and what drives "
          f"the return to shareholders? Selected year: {esc(fy)}.")

    roce_v, roe_v = _f(kpis.loc["ROCE_Pct", fy]), _f(kpis.loc["ROE_Pct", fy])
    cod_v, spread_v = _f(kpis.loc["Implied_Cost_of_Debt_Pct", fy]), _f(kpis.loc["Economic_Spread_Pct", fy])
    eva_v, icr_v = _f(kpis.loc["EVA_Spread_Proxy_Cr", fy]), _f(kpis.loc["Interest_Coverage_Ratio", fy])
    ce_v, debt_v, pat_v = _f(kpis.loc["Capital_Employed", fy]), _f(inputs.loc["TOTAL_DEBT", fy]), _f(res["pat_attr"][fy])

    if icr_v >= 999.0:
        icr_txt, icr_badge, icr_tone = "∞", "No interest burden", "t-green"
    else:
        icr_txt = fmt_x(icr_v)
        icr_badge, icr_tone = (("Comfortable cushion", "t-green") if icr_v >= 6.0 else ("Adequate cover", "t-gold") if icr_v >= 3.0
                               else ("Watchlist cover", "t-amber") if icr_v >= 1.5 else ("Thin cover", "t-red"))
    st.markdown(kpi_grid([
        kpi_card("ROCE", fmt_pct(roce_v, 2), f"{fy} · EBIT ÷ (Debt + Equity)", f"Capital Employed {fmt_cr(ce_v, 0)}", _ret_tone(roce_v), nt["roce"]),
        kpi_card("ROE", fmt_pct(roe_v, 2), f"{fy} · attributable profit ÷ Equity", f"Profit {fmt_cr(pat_v, 0)}", _ret_tone(roe_v), nt["roe"]),
        kpi_card("Implied Cost of Debt", fmt_pct(cod_v, 2), f"{fy} · Finance Cost ÷ Total Debt",
                 "Debt-Free" if debt_v <= 0 else f"Debt {fmt_cr(debt_v, 0)}", "t-green" if debt_v <= 0 else "t-violet", nt["cod"]),
        kpi_card("Economic Spread", f"{spread_v:+.2f} pts" if np.isfinite(spread_v) else "n/a", f"{fy} · ROCE − Implied Cost of Debt",
                 f"EVA proxy {fmt_cr(eva_v, 0)}", "t-green" if spread_v > 0 else "t-red", nt["spread"]),
        kpi_card("Interest Coverage", icr_txt, f"{fy} · EBIT ÷ Finance Cost", icr_badge, icr_tone, nt["icr"]),
    ]), unsafe_allow_html=True)
    if emp_state in ("not_reported", "partial"):
        st.warning("Employee cost is not reported by the data source" + (" for some years" if emp_state == "partial" else "") + ", and MEROS does not estimate it. "
                   "Workforce figures below (cost per employee, labour share, Human Capital ROI) are unavailable or not meaningful, and GVA is understated "
                   "by the missing payroll. Type the figure into the override grid if you know it.")

    ch_left, ch_right = st.columns(2, gap="large")
    cost_s = kpis.loc["Avg_Cost_Per_Emp_Lakhs", years].to_numpy(dtype="float64")
    va_s = kpis.loc["Value_Added_Per_Emp_Lakhs", years].to_numpy(dtype="float64")
    roi_s = kpis.loc["Human_Capital_ROI", years].to_numpy(dtype="float64")
    with ch_left:
        if not _any_finite(cost_s, va_s, roi_s):
            st.info("Per-employee metrics are not available: the data source reports no headcount or employee cost for this company, and MEROS does not "
                    "estimate them. Enter them in the verification grid (live Yahoo data) to see this chart.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=years, y=cost_s, name="Avg Cost / Employee (₹ L)", marker_color=CYAN,
                                 text=[f"{v:,.1f}" if np.isfinite(v) else "" for v in cost_s], textposition="outside", cliponaxis=False,
                                 hovertemplate="<b>%{fullData.name}</b><br>%{x}: ₹%{y:,.2f} L<extra></extra>"))
            fig.add_trace(go.Bar(x=years, y=va_s, name="GVA / Employee (₹ L)", marker_color=GOLD,
                                 text=[f"{v:,.1f}" if np.isfinite(v) else "" for v in va_s], textposition="outside", cliponaxis=False,
                                 hovertemplate="<b>%{fullData.name}</b><br>%{x}: ₹%{y:,.2f} L<extra></extra>"))
            fig.add_trace(go.Scatter(x=years, y=roi_s, name="Human Capital ROI (x)", yaxis="y2", mode="lines+markers",
                                     line=dict(color=CHAMPAGNE, width=2.5), marker=dict(size=9, color=CHAMPAGNE),
                                     hovertemplate="<b>Human Capital ROI</b><br>%{x}: %{y:.2f}x (Revenue ÷ Employee Cost)<extra></extra>"))
            style_fig(fig, "Cost per Employee vs Value Added per Employee", 440)
            roi_max = float(np.nanmax(roi_s)) if np.isfinite(roi_s).any() else 1.0
            fig.update_layout(barmode="group", yaxis=dict(title="₹ Lakhs per employee", range=pad_range(cost_s, va_s)),
                              yaxis2=dict(title="Human Capital ROI (x)", overlaying="y", side="right", showgrid=False, ticksuffix="x",
                                          automargin=True, range=[0.0, max(roi_max, 1.0) * 1.3]),
                              legend=LEG_BELOW)
            show_chart(fig, "t3_workforce_chart")

    with ch_right:
        roce_s = kpis.loc["ROCE_Pct", years].to_numpy(dtype="float64")
        roe_s = kpis.loc["ROE_Pct", years].to_numpy(dtype="float64")
        cod_s = kpis.loc["Implied_Cost_of_Debt_Pct", years].to_numpy(dtype="float64")
        labelled = n <= 6
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=years, y=cod_s, name="Implied Cost of Debt %", mode="lines+markers",
                                 line=dict(color=VIOLET, width=2, dash="dash"), marker=dict(size=8),
                                 hovertemplate="<b>Implied Cost of Debt</b><br>%{x}: %{y:.2f}%<extra></extra>"))
        fig.add_trace(go.Scatter(x=years, y=roce_s, name="ROCE %", mode="lines+markers+text" if labelled else "lines+markers", fill="tonexty",
                                 fillcolor="rgba(229,169,60,0.12)", line=dict(color=GOLD, width=3), marker=dict(size=9),
                                 text=[f"{v:.1f}%" if np.isfinite(v) else "" for v in roce_s], textposition="top center",
                                 hovertemplate="<b>ROCE</b><br>%{x}: %{y:.2f}%<extra></extra>"))
        fig.add_trace(go.Scatter(x=years, y=roe_s, name="ROE %", mode="lines+markers+text" if labelled else "lines+markers",
                                 line=dict(color=JADE, width=3), marker=dict(size=9),
                                 text=[f"{v:.1f}%" if np.isfinite(v) else "" for v in roe_s], textposition="bottom center",
                                 hovertemplate="<b>ROE</b><br>%{x}: %{y:.2f}%<extra></extra>"))
        style_fig(fig, "Capital Efficiency & Return Trajectory", 440)
        fig.update_layout(yaxis=dict(ticksuffix="%", zeroline=True, range=pad_range(roce_s, roe_s, cod_s, pad_low=True)), legend=LEG_BELOW)
        show_chart(fig, "t3_capital_chart")
        st.caption("Gold band = ROCE earned above the implied cost of debt. For debt-free firms the cost line sits at 0%.")

    # ---- Strategic ratio matrix --------------------------------------------------------
    st.markdown('<div class="section-h">Strategic finance &amp; <em>credit appraisal</em> matrix</div>', unsafe_allow_html=True)
    matrix: list[tuple[str, str, list[str]]] = []
    for spec in RATIO_SPEC:
        if spec[0] == "section":
            matrix.append(("section", spec[1], []))
            continue
        key, lab, unit, good_up = spec
        matrix.append(("row", lab, [_ratio_cell(key, unit, y, kpis, pnl) for y in years] + [_ratio_trend(key, unit, good_up, years, kpis, pnl)]))
    st.markdown(render_table(["Strategic ratio"] + list(years) + [f"Trend / Δ ({years[0]}→{years[-1]})"], matrix), unsafe_allow_html=True)
    st.caption("n/a means the source does not report the inputs (for example employee cost or headcount). ICR shows ∞ when there is no finance cost; "
               "effective tax rate shows n/a when PBT is not positive. Trend arrows are jade when the move is favorable, crimson when adverse, cyan when neutral.")

    # ---- Returns on capital and EVA ------------------------------------------------------
    st.markdown('<div class="section-h">Returns on capital: <em>average balances</em> &amp; full EVA</div>'
                '<div class="section-sub">The same returns measured on the average of opening and closing capital, then a full Economic Value Added that '
                f'charges for equity too, using the {ke:.1f}% cost of equity you set in the sidebar.</div>', unsafe_allow_html=True)
    cap_rows: list[tuple[str, str, list[str]]] = []
    for key, lab, unit in CAP_LAYOUT:
        if key == "section":
            cap_rows.append(("section", lab, []))
        else:
            cap_rows.append(("row", lab, [fmt_unit(_f(v), unit) for v in cap[key]]))
    st.markdown(render_table(["Return on capital & EVA"] + list(years), cap_rows), unsafe_allow_html=True)
    open_lab = (cd.get("opening") or {}).get("label")
    st.caption((f"The first year's average uses the {open_lab} balance sheet as its opening balance. " if open_lab
                else "The first year's average needs an opening balance sheet, which is not available, so it shows n/a. ")
               + f"EVA uses your {ke:.1f}% cost of equity (assumption E11) and book-value weights (E12)."
               + (" For a bank or financial company, EVA and ROCE are not meaningful." if cd.get("is_financial") else ""))

    eva_l, eva_r = st.columns(2, gap="large")
    with eva_l:
        eva = np.asarray(cap["EVA"], dtype="float64")
        fig = go.Figure(go.Bar(x=years, y=eva, marker_color=[JADE if (np.isfinite(v) and v >= 0) else CRIMSON for v in eva],
                               text=[fmt_cr(v, 0) if np.isfinite(v) else "" for v in eva], textposition="outside", cliponaxis=False,
                               hovertemplate="<b>%{x}</b><br>EVA ₹%{y:,.2f} Cr<extra></extra>"))
        style_fig(fig, f"Economic Value Added (₹ Cr) at {ke:.1f}% cost of equity", 400)
        fig.update_layout(showlegend=False, yaxis=dict(tickprefix="₹", ticksuffix=" Cr", zeroline=True, range=pad_range(eva)))
        show_chart(fig, "t3_eva_chart")
    with eva_r:
        roic, wacc = np.asarray(cap["ROIC"], dtype="float64"), np.asarray(cap["WACC"], dtype="float64")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=years, y=wacc, name="WACC %", mode="lines+markers", line=dict(color=VIOLET, width=2, dash="dash"),
                                 marker=dict(size=8), hovertemplate="<b>WACC</b><br>%{x}: %{y:.2f}%<extra></extra>"))
        fig.add_trace(go.Scatter(x=years, y=roic, name="ROIC %", mode="lines+markers", fill="tonexty", fillcolor="rgba(229,169,60,0.12)",
                                 line=dict(color=GOLD, width=3), marker=dict(size=9), hovertemplate="<b>ROIC</b><br>%{x}: %{y:.2f}%<extra></extra>"))
        style_fig(fig, "ROIC vs WACC: is value being created?", 400)
        fig.update_layout(yaxis=dict(ticksuffix="%", zeroline=True, range=pad_range(roic, wacc, pad_low=True)), legend=LEG_BELOW)
        show_chart(fig, "t3_roic_wacc_chart")

    # ---- DuPont ----------------------------------------------------------------------------
    st.markdown('<div class="section-h"><em>DuPont</em> analysis: what drives the return to shareholders</div>'
                '<div class="section-sub">ROE split into profitability, efficiency and leverage. All factors use year-end balances and attributable profit, '
                'so they multiply back to ROE exactly. No industry comparison is included (assumption E22).</div>', unsafe_allow_html=True)
    if not dp.get("available"):
        st.warning("DuPont is not available: " + str(dp.get("reason") or "required data is missing."))
    else:
        if dp.get("bank"):
            st.info("This is a bank or financial company. DuPont figures are indicative only, because assets and equity mean something different for lenders.")
        dp_rows: list[tuple[str, str, list[str]]] = []
        for key, lab, unit in DUPONT_LAYOUT:
            if key == "section":
                dp_rows.append(("section", lab, []))
            else:
                dp_rows.append(("row", lab, [fmt_unit(_f(v), unit) for v in dp["values"][key]]))
        st.markdown(render_table(["DuPont component"] + list(years), dp_rows), unsafe_allow_html=True)
        st.caption("Tax & minority burden = attributable profit ÷ PBT: it captures tax AND the minority shareholders' and associates' share. "
                   "The check row should read 0.00.")
        chg = ctx.get("dupont_change") or {}
        a_l, a_r = st.columns(2, gap="large")
        for col, which, title, key in ((a_l, "3", "3-step: what moved ROE", "t3_dupont3_chart"), (a_r, "5", "5-step: what moved ROE", "t3_dupont5_chart")):
            with col:
                d = chg.get(which)
                if d:
                    show_chart(_attribution_fig(d, title), key)
                else:
                    st.info(f"{title}: not available. The exact attribution needs ROE and every factor to be positive in both the first and last year.")
        st.caption("Bars show how many percentage points of the change in ROE each factor explains between the first and last year "
                   "(exact log-mean attribution; the bars add up to the total).")