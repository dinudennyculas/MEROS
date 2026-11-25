"""MEROS screens 4-6 (shock simulator, audit & transparency, company comparison).

ctx keys (built by app.py):
  results, cd, active_fy, source_label, emp_state, ke_pct                       (all tabs)
  Tab 5: provenance (DataFrame), health (list), xcheck (dict | None), raw_tables ({title: DataFrame} | None),
         audit (hygiene dict), raw_df (grid as received), clean_df
  Tab 6: ticker_df (tickers.load_tickers table | None), compare_loader (callable: symbol -> company data, may raise ValueError)
render_tab4 returns the shock result (or None), render_tab6 returns the comparison dict (or None), assumption_rows(cd) returns
the register rows with their live state (for the Excel export)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics import PROV_VALUE_COL, bridge_numbers, comparison_frame, select_window
from corporate_engine import RECEIPT_LABELS, SCHEMA, compute_corporate_anatomy_and_vas, sanitize_statement_df, simulate_margin_shock
from meros_assumptions import ASSUMPTION_REGISTER, SCOPE_TITLES, assumption_state
from tickers import clean_symbol, label_to_symbol, options as ticker_options
from ui_style import (CRIMSON, CYAN, GOLD, JADE, LEG_BELOW, PEWTER, PROV_TONE, RECEIPT_COLORS, RECEIPT_NAMES, RECEIPT_STAMP, STATE_TONE,
                      STAKE_BR, STAKE_COLORS, chip, esc, fmt_cr, fmt_int, fmt_pct, fmt_rs, fmt_unit, fmt_x, health_cards_html, kpi_card,
                      kpi_grid, notice_html, pad_range, receipt_html, receipt_row, render_table, sgn_cr, show_chart, style_fig)


def _head(title_html: str, sub: str) -> None:
    st.markdown(f'<div class="section-h">{title_html}</div><div class="section-sub">{sub}</div>', unsafe_allow_html=True)


def _f(v: object) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


# --------------------------------------------------------------------------------------
# Tab 4: margin shock simulator (applied to the latest year)
# --------------------------------------------------------------------------------------
def render_tab4(ctx: dict) -> dict | None:
    res = ctx["results"]
    years, inputs, vas_abs = res["years"], res["inputs"], res["vas_abs"]
    last = years[-1]
    emp_state = ctx.get("emp_state", "reported")
    _head('Macroeconomic &amp; inflation <em>pass-through</em> shock simulator',
          f"Shock {esc(last)} input costs, wages and interest rates, choose how much of the pain is passed on to consumers, and watch the ₹100 receipt "
          "and every stakeholder payout re-balance. It always uses the latest year as its baseline.")
    with st.container(border=True):
        st.markdown(f'<div class="kpi-label">Shock control panel · applied to {esc(last)} actuals</div>', unsafe_allow_html=True)
        p1, p2 = st.columns(2, gap="large")
        mat = p1.slider("Raw Material & Supply Chain Inflation Shock (%)", min_value=-20.0, max_value=40.0, value=10.0, step=1.0,
                        format="%.1f", key="t4_mat", help="Percentage change applied to the latest-year cost of materials (COGS_MAT).")
        wage = p2.slider("Workforce Wage & Benefit Hike (%)", min_value=-10.0, max_value=30.0, value=8.0, step=1.0, format="%.1f",
                         key="t4_wage", help="Percentage change applied to the latest-year employee benefit expenses (EMP_COST).")
        p3, p4 = st.columns(2, gap="large")
        bps = p3.slider("Interest Rate / Borrowing Cost Shock (bps)", min_value=-200, max_value=400, value=100, step=25, format="%d",
                        key="t4_bps", help="Basis-point change applied to the latest-year total debt (TOTAL_DEBT).")
        passt = p4.slider("Consumer Price Pass-Through (%) · 0 = Company Absorbs All, 100 = Consumers Absorb All", min_value=0, max_value=100,
                          value=35, step=5, format="%d", key="t4_pass",
                          help="Share of total cost inflation recovered through higher prices on revenue from operations.")
        st.caption(f"Selected shocks: materials {mat:+.1f}% · wages {wage:+.1f}% · rates {int(bps):+d} bps · pass-through {int(passt)}%")
    if emp_state in ("not_reported", "partial"):
        st.info("Employee cost is not reported by the data source, so the wage shock has nothing to act on and will show no effect. "
                "Type the payroll figure into the override grid (live Yahoo data) to simulate wage changes.")
    if _f(res["pnl"].loc["Total_Income", last]) <= 0:
        st.warning(f"{last} total income is zero or negative; the shock simulator needs a positive latest-year baseline.")
        return None

    sim = simulate_margin_shock(res, float(mat), float(wage), float(bps), float(passt))
    base_m, sim_m, shocks, rc = sim["baseline"], sim["simulated"], sim["shocks"], sim["receipt"]
    base_rc = rc.loc[RECEIPT_LABELS, "Baseline"].to_numpy(dtype="float64")
    sim_rc = rc.loc[RECEIPT_LABELS, "Simulated"].to_numpy(dtype="float64")
    rev_last = _f(inputs.loc["REV_OPS", last])

    d_pat = sim_m["PAT"] - base_m["PAT"]
    d_pat_pct = d_pat / abs(base_m["PAT"]) * 100.0 if abs(base_m["PAT"]) > 0 else float("nan")
    d_roe = sim_m["ROE_Pct"] - base_m["ROE_Pct"]
    base_bite, sim_bite = float(base_rc[6] + base_rc[7]), float(sim_rc[6] + sim_rc[7])
    d_bite, be_pct = sim_bite - base_bite, float(sim["Breakeven_Price_Hike_Pct"])
    implied_hike = shocks["Delta_Rev"] / rev_last * 100.0 if rev_last > 0 else 0.0

    def tone(d: float) -> str:
        return "t-green" if d > 1e-9 else ("t-red" if d < -1e-9 else "t-gold")

    st.markdown("<div style='height:.9rem'></div>", unsafe_allow_html=True)
    st.markdown(kpi_grid([
        kpi_card(f"Simulated {last} profit after tax", fmt_cr(sim_m["PAT"]), f"Baseline {fmt_cr(base_m['PAT'])}",
                 f"Δ {sgn_cr(d_pat)} ({fmt_pct(d_pat_pct, 1, True)})", tone(d_pat),
                 "Yearly profit after tax if your cost shocks happen, compared with the actual figure."),
        kpi_card("Simulated ROE vs baseline", fmt_pct(sim_m["ROE_Pct"], 2), f"Baseline {fmt_pct(base_m['ROE_Pct'], 2)}",
                 f"Δ {d_roe:+.2f} pts", tone(d_roe), "Return to shareholders (attributable profit) under the scenario."),
        kpi_card("Consumer Net Profit Bite", f"{fmt_rs(sim_bite)} per ₹100", f"Baseline {fmt_rs(base_bite)} per ₹100",
                 f"Δ {d_bite * 100:+.0f} paise", tone(d_bite), "Profit left from each ₹100 of income once the shock is absorbed."),
        kpi_card("Break-Even Price Hike (0% Pass-Through)", fmt_pct(be_pct, 2),
                 f"Cost inflation {fmt_cr(sim['Total_Cost_Inflation'], 0)} ÷ {last} revenue", f"Selected pass-through = {implied_hike:.2f}% price hike",
                 "t-green" if be_pct <= 0 else ("t-amber" if be_pct < 5.0 else "t-red"),
                 "The price rise needed to fully offset the cost shock and keep pre-tax profit unchanged."),
    ]), unsafe_allow_html=True)

    base_stake = vas_abs[last].to_numpy(dtype="float64")
    sim_stake = np.array([_f(inputs.loc["EMP_COST", last]) + shocks["Delta_Emp"], _f(inputs.loc["FIN_COST", last]) + shocks["Delta_Fin"],
                          sim_m["Tax_Expense"], _f(inputs.loc["DIV_PAID", last]),
                          sim_m["Retained_Earnings"] + _f(inputs.loc["DEP_AMORT", last])], dtype="float64")
    sc_left, sc_right = st.columns([1.6, 1], gap="large")
    with sc_left:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=STAKE_BR, y=base_stake, name=f"Baseline {last}", marker_color=PEWTER, texttemplate="%{y:,.0f}",
                             textposition="outside", cliponaxis=False, hovertemplate="<b>%{x}</b><br>Baseline: ₹%{y:,.2f} Cr<extra></extra>"))
        fig.add_trace(go.Bar(x=STAKE_BR, y=sim_stake, name=f"Simulated {last}", marker_color=GOLD, customdata=sim_stake - base_stake,
                             texttemplate="%{y:,.0f}", textposition="outside", cliponaxis=False,
                             hovertemplate="<b>%{x}</b><br>Simulated: ₹%{y:,.2f} Cr<br>Δ vs baseline: %{customdata:+,.2f} Cr<extra></extra>"))
        style_fig(fig, f"Stakeholder Payouts · Baseline vs Simulated {last} (₹ Cr)", 440)
        fig.update_layout(barmode="group", xaxis=dict(tickangle=0), yaxis=dict(tickprefix="₹", ticksuffix=" Cr", range=pad_range(base_stake, sim_stake)),
                          legend=LEG_BELOW)
        show_chart(fig, "t4_payout_chart")
        st.caption(f"Baseline GVA {fmt_cr(base_m['GVA'])} → Simulated GVA {fmt_cr(sim_m['GVA'])} · Simulated VAS closure (Σ 5 stakeholders = GVA): "
                   f"{'Verified ✅' if sim['vas_closure_check'] else 'Breach ⚠️'}")
    with sc_right:
        rows = [("Δ Materials & supply chain", shocks["Delta_COGS"]), ("Δ Workforce wages & benefits", shocks["Delta_Emp"]),
                ("Δ Finance cost (bps × debt)", shocks["Delta_Fin"])]
        rows_html = "".join(f'<div class="receipt-row"><span>{esc(nm)}</span><span class="amt">{sgn_cr(float(v))}</span></div>' for nm, v in rows)
        st.markdown('<div class="receipt"><div class="receipt-head">SHOCK DECOMPOSITION</div>'
                    f'<div class="receipt-meta">{esc(last)} baseline · ₹ Crores</div>{rows_html}'
                    f'<div class="receipt-total"><span>TOTAL COST INFLATION</span><span>{sgn_cr(shocks["Total_Cost_Inflation"])}</span></div>'
                    '<div class="receipt-row"><span>Revenue offset via price pass-through</span>'
                    f'<span class="amt" style="color:{JADE}">{sgn_cr(shocks["Delta_Rev"])}</span></div>'
                    '<div class="receipt-row"><span>Unrecovered cost absorbed by company</span>'
                    f'<span class="amt" style="color:{CRIMSON}">{sgn_cr(shocks["Unrecovered_Cost"])}</span></div>'
                    f'<div class="receipt-meta" style="margin-top:.8rem">Pass-through {int(passt)}% · '
                    f'Baseline tax rate {sim["assumptions"]["baseline_effective_tax_rate_pct"]:.2f}%<br>'
                    f'{esc(sim["assumptions"]["dividend_policy"])}</div>' + RECEIPT_STAMP + '</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-h">₹100 consumer receipt · <em>before vs after</em> the shock</div>', unsafe_allow_html=True)

    def card(title: str, vals: np.ndarray, deltas: np.ndarray | None) -> str:
        body = ""
        for i in range(8):
            dtxt = ""
            if deltas is not None:
                d = float(deltas[i])
                col = PEWTER if abs(d) < 0.005 else ((JADE if d > 0 else CRIMSON) if i >= 6 else (CRIMSON if d > 0 else JADE))
                dtxt = f'<span style="color:{col};margin-left:.6rem;font-size:.72rem">{d:+.2f}</span>'
            body += receipt_row(RECEIPT_NAMES[i], RECEIPT_COLORS[i], fmt_rs(vals[i]), dtxt)
        return receipt_html(title, "Amount paid by customer: ₹100.00", body, "TOTAL ALLOCATED", fmt_rs(float(np.sum(vals))), bool(sim["receipt_check"]["all_ok"]))

    r_left, r_right = st.columns(2, gap="large")
    r_left.markdown(card(f"BASELINE ₹100 SPLIT · {last}", base_rc, None), unsafe_allow_html=True)
    r_right.markdown(card(f"POST-SHOCK ₹100 SPLIT · {last}", sim_rc, sim_rc - base_rc), unsafe_allow_html=True)

    st.markdown('<div class="section-h">Scenario <em>P&amp;L</em> comparison</div>', unsafe_allow_html=True)
    cmp_df = sim["comparison"]

    def row(key: str, label: str, unit: str) -> tuple[str, str, list[str]]:
        b, s = float(cmp_df.loc[key, "Baseline"]), float(cmp_df.loc[key, "Simulated"])
        if unit == "cr":
            d = s - b
            pc = f" ({d / abs(b) * 100.0:+.1f}%)" if abs(b) > 0 else ""
            return ("row", label, [fmt_cr(b), fmt_cr(s), sgn_cr(d) + pc])
        if unit == "icr":
            if b >= 999.0 or s >= 999.0:
                return ("row", label, ["∞" if b >= 999.0 else f"{b:.2f}x", "∞" if s >= 999.0 else f"{s:.2f}x", "—"])
            return ("row", label, [f"{b:.2f}x", f"{s:.2f}x", f"{s - b:+.2f}x"])
        return ("row", label, [fmt_pct(b, 2), fmt_pct(s, 2), f"{s - b:+.2f} pts"])

    spec = [("Total_Income", "Total Income", "cr"), ("GVA", "Gross Value Added (GVA)", "cr"), ("EBITDA", "EBITDA", "cr"), ("EBIT", "EBIT", "cr"),
            ("PBT", "Profit Before Tax (PBT)", "cr"), ("Tax_Expense", "Tax Expense", "cr"), ("PAT", "Profit After Tax (PAT)", "cr"),
            ("PAT_Attributable", "Profit attributable to shareholders", "cr"), ("GVA_Margin_Pct", "GVA Margin", "pct"),
            ("EBITDA_Margin_Pct", "EBITDA Margin", "pct"), ("PAT_Margin_Pct", "PAT Margin", "pct"), ("ROE_Pct", "ROE", "pct"),
            ("Interest_Coverage_Ratio", "Interest Coverage Ratio", "icr")]
    st.markdown(render_table([f"Metric ({last})", "Baseline", "Simulated", "Change"], [row(*s) for s in spec]), unsafe_allow_html=True)
    st.caption("A one-period static what-if: volumes and other costs do not react, dividends are held constant and tax uses the latest effective rate "
               "if profit stays positive (assumption E10). Use it for sensitivity, not forecasting.")
    return sim


# --------------------------------------------------------------------------------------
# Tab 5 helpers
# --------------------------------------------------------------------------------------
def assumption_rows(cd: dict) -> list[tuple]:
    """Register rows with their live state, e.g. for the Excel export: (id, scope, area, assumption, why, effect, state)."""
    return [(rid, scope, area, what, why, eff, assumption_state(scope, rid, cd.get("status"), cd.get("source")))
            for rid, scope, area, what, why, eff in ASSUMPTION_REGISTER]


def render_register(cd: dict) -> str:
    heads = ["ID", "Assumption", "Why it is needed (reasoning)", "Effect & how to override", "Status"]
    head = "".join(f"<th>{esc(h)}</th>" for h in heads)
    body: list[str] = []
    last = None
    for rid, scope, area, what, why, effect, state in assumption_rows(cd):
        if scope != last:
            body.append(f'<tr class="section"><td colspan="{len(heads)}">{esc(SCOPE_TITLES[scope])}</td></tr>')
            last = scope
        glyph = "● " if state == "ACTIVE" else ""
        body.append(f'<tr><td class="rid">{rid}</td><td><b>{esc(area)}</b><br>{esc(what)}</td><td>{esc(why)}</td><td>{esc(effect)}</td>'
                    f'<td><span class="kpi-badge {STATE_TONE.get(state, "t-mute")}">{glyph}{state}</span></td></tr>')
    return ('<div class="glass-card" style="overflow-x:auto;padding:.6rem .9rem;">'
            f'<table class="vas-table reg-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def build_bridge_html(cd: dict, res: dict) -> str:
    b = bridge_numbers(cd, res)
    years = res["years"]

    def cr(a: np.ndarray) -> list[str]:
        return [fmt_cr(x) for x in a]

    def var(a: np.ndarray) -> list[str]:
        return ["n/a" if not np.isfinite(x) else ("0.0000" if abs(x) < 5e-5 else f"{x:+.4f}") for x in a]

    def badge(c_ok: bool, a_ok: bool) -> str:
        if c_ok and a_ok:
            return chip("✅ Match", "t-green")
        return chip("⚠ Edited", "t-amber") if c_ok else chip("❌ Break", "t-red")

    if bool(b["close_ok"].all()) and bool(b["anchor_ok"].all()):
        overall = chip("✅ Verified Match", "t-green")
    elif bool(b["close_ok"].all()):
        overall = chip("⚠ Override variance vs source", "t-amber")
    else:
        overall = chip("❌ Closure break", "t-red")
    src = "Screener" if cd.get("source") == "screener" else "Yahoo"
    rows: list[tuple[str, str, list[str]]] = [
        ("section", f"A. {src.upper()} REPORTED ANCHORS (₹ CR)", []),
        ("row", f"Total revenue ({src})", cr(b["tr"]) + [""]),
        ("row", f"Profit before tax ({src})", cr(b["pb"]) + [""]),
        ("row", f"Profit attributable to shareholders ({src})", cr(b["pa"]) + [""]),
        ("row", f"Tax reported ({src})", cr(b["tp"]) + [""]),
        ("section", "B. MEROS LADDER (FROM THE CURRENT GRID)", []),
        ("row", "Total income (revenue + other income)", cr(b["ti"]) + [""]),
        ("row", "Gross value added (GVA)", cr(b["gva"]) + [""]),
        ("row", "PBT (GVA − employee − depreciation − finance cost)", cr(b["pbt"]) + [""]),
        ("row", "Tax used (as reported where available)", cr(b["tax"]) + [""]),
        ("row", "PAT = PBT − tax (before minority interest)", cr(b["pat"]) + [""]),
        ("row", "Less: minority interest, associates & other items", cr(b["adj"]) + [""]),
        ("row", "Profit attributable to shareholders", cr(b["pat_attr"]) + [""]),
        ("section", "C. VARIANCE & CLOSURE (TARGET 0.0000)", []),
        ("row", f"PBT variance vs {src}", var(b["v_pbt"]) + [""]),
        ("row", f"Attributable-profit variance vs {src}", var(b["v_pat"]) + [""]),
        ("row", "VAS closure residual (GVA − Σ 5 stakeholders)", var(b["resid"]) + [""]),
        ("row", "₹100 receipt closure (Σ 8 components − ₹100.00)", var(b["rcpt"]) + [""]),
        ("total", "Verification status", [badge(bool(c), bool(a)) for c, a in zip(b["close_ok"], b["anchor_ok"])] + [overall]),
    ]
    heads = ["Reconciliation line (₹ Cr)"] + [f"{y} · {lab}" for y, lab in zip(years, cd["period_labels"])] + ["Status"]
    return render_table(heads, rows)


def build_xcheck_html(xc: dict) -> str:
    rows = []
    for r in xc.get("rows", []):
        rp, pp = r.get("revenue_diff_pct"), r.get("profit_diff_pct")
        rows.append(("row", f"{r['year']} · {r['period_end']}",
                     [fmt_cr(r["revenue_screener"]), fmt_cr(r["revenue_yahoo"]), fmt_pct(rp if rp is not None else float('nan'), 2, True),
                      fmt_cr(r["profit_screener"]), fmt_cr(r["profit_yahoo"]), fmt_pct(pp if pp is not None else float('nan'), 2, True),
                      chip("⚠ differs", "t-amber") if r["flag"] else chip("✅ agrees", "t-green")]))
    return render_table(["Year", "Revenue (Screener)", "Revenue (Yahoo)", "Diff", "Profit (Screener)", "Profit (Yahoo)", "Diff", "Result"], rows)


def build_prov_html(prov_df: pd.DataFrame, cd: dict) -> str:
    years = cd["years"]
    rows: list[tuple[str, str, list[str]]] = []
    for lid, name, _cat in SCHEMA:
        recs = prov_df[prov_df["Line_ID"] == lid].to_dict("records")
        cells, details = [], []
        for r in recs:
            v = _f(r[PROV_VALUE_COL])
            num = fmt_int(v) if lid == "HEADCOUNT" else fmt_rs(v).replace("₹", "")
            tip = esc(str(r["Source / rule"]))
            cells.append(f'<span title="{tip}">{num}</span> {chip(str(r["Status"]).upper(), PROV_TONE.get(r["Status"], "t-mute"))}')
            details.append(str(r["Source / rule"]))
        detail = details[0] if details and len(set(details)) == 1 else (f"Varies by year · latest: {details[-1]}" if details else "")
        cells.append(f'<span style="white-space:normal;display:inline-block;max-width:340px;text-align:left">{esc(detail)}</span>')
        rows.append(("row", name, cells))
    heads = ["Schedule III line"] + [f"{y} · {lab}" for y, lab in zip(years, cd["period_labels"])] + ["Source / rule (hover a cell for its own)"]
    return render_table(heads, rows)


_FORMULAS = {
    "Gross Value Added and the P&L ladder": """Total_Income        = REV_OPS + REV_OTH
Bought_In_Costs     = COGS_MAT + OPEX_EXT
GVA                 = Total_Income - Bought_In_Costs
EBITDA              = GVA - EMP_COST
EBIT                = EBITDA - DEP_AMORT
PBT                 = EBIT - FIN_COST
PAT                 = PBT - TAX_EXP                     # tax is the reported figure
Retained_Earnings   = PAT - DIV_PAID
attr_adj            = (PBT - TAX_EXP) - reported profit attributable to shareholders
PAT_Attributable    = PAT - attr_adj                    # used for ROE and DuPont""",
    "Net value added, guarded ratios and credit metrics": """NVA = GVA - DEP_AMORT

def _safe_div(num, den, fill=0.0, positive_only=True):
    n = np.asarray(num, dtype="float64"); d = np.asarray(den, dtype="float64")
    mask = (d > 0) if positive_only else (d != 0)
    return np.where(mask, n / np.where(mask, d, 1.0), fill)

Implied_Cost_of_Debt_Pct = np.where(TOTAL_DEBT > 0, FIN_COST / np.where(TOTAL_DEBT > 0, TOTAL_DEBT, 1.0) * 100.0, 0.0)
Interest_Coverage_Ratio  = np.where(FIN_COST > 0, EBIT / np.where(FIN_COST > 0, FIN_COST, 1.0), 999.0)
ROCE_Pct                 = _safe_div(EBIT, TOTAL_DEBT + TOTAL_EQUITY) * 100.0
ROE_Pct                  = _safe_div(PAT_Attributable, TOTAL_EQUITY) * 100.0
Value_Added_Per_Emp      = GVA * 100 / HEADCOUNT  if HEADCOUNT > 0 else not available""",
    "Stakeholder shares of GVA and the ₹100 receipt": """stake_mat = np.vstack([EMP_COST, FIN_COST, TAX_EXP, DIV_PAID, Retained_Earnings + DEP_AMORT])
residual  = GVA - stake_mat.sum(axis=0)
vas_closure_check = bool(np.all(np.abs(residual) < 1e-4))
pct_of_gva = _safe_div(stake_mat, GVA) * 100.0

components = np.vstack([COGS_MAT, OPEX_EXT, EMP_COST, DEP_AMORT, FIN_COST, TAX_EXP, DIV_PAID, Retained_Earnings])
exact      = _safe_div(components * 100.0, Total_Income)
raw_paise  = exact * 100.0
floors     = np.floor(raw_paise)
deficit    = np.rint(10000.0 - floors.sum(axis=0)).astype("int64")
ranks      = np.argsort(np.argsort(-(raw_paise - floors), axis=0, kind="stable"), axis=0, kind="stable")
paise      = floors.astype("int64") + (ranks < deficit).astype("int64")   # each column sums to 10,000 paise""",
    "DuPont (3-step, 5-step and the exact change attribution)": """NM    = PAT_Attributable / Total_Income
AT    = Total_Income / Total_Assets
EM    = Total_Assets / TOTAL_EQUITY
ROE_3 = NM * AT * EM                          # equals PAT_Attributable / TOTAL_EQUITY exactly

TB    = PAT_Attributable / PBT                # tax and minority burden
IB    = PBT / EBIT                            # interest burden
EBITM = EBIT / Total_Income
ROE_5 = TB * IB * EBITM * AT * EM

# change in ROE between two years, split exactly across the factors (log-mean / LMDI):
L(a, b)        = (a - b) / (ln(a) - ln(b))
contribution_i = L(ROE_last, ROE_first) * ln(factor_i_last / factor_i_first)""",
    "Full EVA": """t     = clip(TAX_EXP / PBT, 0, 0.40)          (0 if PBT <= 0)
NOPAT = EBIT * (1 - t)
Kd    = FIN_COST / TOTAL_DEBT
We    = TOTAL_EQUITY / (TOTAL_DEBT + TOTAL_EQUITY)          # book-value weights
WACC  = We * Ke + (1 - We) * Kd * (1 - t)                   # Ke is YOUR cost of equity (sidebar)
EVA   = NOPAT - WACC * (TOTAL_DEBT + TOTAL_EQUITY)
ROIC  = NOPAT / (TOTAL_DEBT + TOTAL_EQUITY)""",
    "Inflation pass-through simulation (latest year)": """Delta_COGS           = COGS_MAT   * (mat_inflation_pct / 100.0)
Delta_Emp            = EMP_COST   * (wage_hike_pct / 100.0)
Delta_Fin            = TOTAL_DEBT * (rate_shock_bps / 10000.0)
Total_Cost_Inflation = Delta_COGS + Delta_Emp + Delta_Fin
Delta_Rev            = Total_Cost_Inflation * (price_passthrough_pct / 100.0)

sim_tax = np.where(sim_PBT > 0, sim_PBT * latest_effective_tax_rate, 0.0)
Breakeven_Price_Hike_Pct = Total_Cost_Inflation / REV_OPS * 100.0""",
}


# --------------------------------------------------------------------------------------
# Tab 5: glass-box audit
# --------------------------------------------------------------------------------------
def render_tab5(ctx: dict) -> None:
    res, cd, fy = ctx["results"], ctx["cd"], ctx["active_fy"]
    years, inputs, pnl, cs, vas_abs = res["years"], res["inputs"], res["pnl"], res["common_size"], res["vas_abs"]
    _head('Glass-box formula audit &amp; <em>live reconciliation</em> verifier',
          f"Every headline number re-derived by an independent step-by-step hand calculation for {esc(fy)}, then compared with the vectorized engine output. "
          "Below it: source reconciliation, where every cell came from, data-health checks, raw source tables and every assumption.")

    fy_in = {k: float(inputs.loc[k, fy]) for k in inputs.index}
    h_ti = fy_in["REV_OPS"] + fy_in["REV_OTH"]
    if h_ti <= 0:
        st.warning(f"Total income for {fy} is not positive, so the identity verifier cannot run for that year.")
    else:
        h_gva = h_ti - (fy_in["COGS_MAT"] + fy_in["OPEX_EXT"])
        h_ebit = h_gva - fy_in["EMP_COST"] - fy_in["DEP_AMORT"]
        h_pbt = h_ebit - fy_in["FIN_COST"]
        h_pat = h_pbt - fy_in["TAX_EXP"]
        h_ret = h_pat - fy_in["DIV_PAID"]
        h_stake = fy_in["EMP_COST"] + fy_in["FIN_COST"] + fy_in["TAX_EXP"] + fy_in["DIV_PAID"] + (h_ret + fy_in["DEP_AMORT"])
        parts = [fy_in["COGS_MAT"], fy_in["OPEX_EXT"], fy_in["EMP_COST"], fy_in["DEP_AMORT"], fy_in["FIN_COST"], fy_in["TAX_EXP"], fy_in["DIV_PAID"], h_ret]
        h_rcpt = sum(p / h_ti * 100.0 for p in parts)
        ids = [("1. GVA = Total Income − (COGS_MAT + OPEX_EXT)", _f(pnl.loc["GVA", fy]), h_gva, "cr"),
               ("2. VAS closure: Σ 5 stakeholder allocations = GVA", float(vas_abs[fy].sum()), h_gva, "cr"),
               ("3. ₹100 receipt closure: Σ 8 components = ₹100.00", float(cs[fy].sum()), h_rcpt, "rs"),
               ("4. EBIT = GVA − EMP_COST − DEP_AMORT", _f(pnl.loc["EBIT", fy]), h_ebit, "cr"),
               ("5. Retained earnings = PAT − DIV_PAID", _f(pnl.loc["Retained_Earnings", fy]), h_ret, "cr")]
        id_rows, n_ok = [], 0
        for nm, eng, hand, unit in ids:
            d = eng - hand
            ok = abs(d) < 1e-4
            n_ok += int(ok)
            fmt = (lambda x: fmt_cr(x, 4)) if unit == "cr" else (lambda x: fmt_rs(x).replace("₹", "₹") if False else f"₹{x:,.4f}")
            id_rows.append(("row", nm, [fmt(eng), fmt(hand), "0.0000" if abs(d) < 5e-5 else f"{d:+.4f}",
                                        chip("✅ Verified Match", "t-green") if ok else chip("❌ Variance Detected", "t-red")]))
        tone = "t-green" if n_ok == len(ids) else "t-red"
        txt = (f"All {len(ids)} accounting identities verified for {fy}." if n_ok == len(ids)
               else f"{len(ids) - n_ok} of {len(ids)} identities show a variance for {fy}.")
        st.markdown(f'<div class="diag-card {tone}" style="min-height:0;margin-bottom:1rem"><div class="diag-head">'
                    '<span class="diag-title">Live mathematical closure &amp; identity verifier</span>'
                    f'<span class="diag-pill">{n_ok} / {len(ids)} VERIFIED</span></div>'
                    f'<div class="diag-text">{esc(txt)} Tolerance: |variance| &lt; 0.0001.</div></div>', unsafe_allow_html=True)
        st.markdown(render_table(["Identity", "Engine (vectorized)", "Independent hand calculation", "Variance", "Status"], id_rows), unsafe_allow_html=True)
        trace = [
            f"[1] GVA = ({fy_in['REV_OPS']:,.4f} + {fy_in['REV_OTH']:,.4f}) - ({fy_in['COGS_MAT']:,.4f} + {fy_in['OPEX_EXT']:,.4f}) = {h_ti:,.4f} - "
            f"{fy_in['COGS_MAT'] + fy_in['OPEX_EXT']:,.4f} = {h_gva:,.4f}",
            f"[2] Σ stakeholders = EMP {fy_in['EMP_COST']:,.4f} + FIN {fy_in['FIN_COST']:,.4f} + TAX {fy_in['TAX_EXP']:,.4f} + DIV {fy_in['DIV_PAID']:,.4f} "
            f"+ (RE {h_ret:,.4f} + DEP {fy_in['DEP_AMORT']:,.4f}) = {h_stake:,.4f}  vs  GVA {h_gva:,.4f}",
            f"[3] Σ (component ÷ Total Income × 100) over 8 components = {h_rcpt:.10f}  (engine paise-allocated sum = {float(cs[fy].sum()):.4f})",
            f"[4] EBIT = {h_gva:,.4f} - {fy_in['EMP_COST']:,.4f} - {fy_in['DEP_AMORT']:,.4f} = {h_ebit:,.4f}",
            f"[5] PBT = {h_ebit:,.4f} - {fy_in['FIN_COST']:,.4f} = {h_pbt:,.4f};  PAT = {h_pbt:,.4f} - {fy_in['TAX_EXP']:,.4f} = {h_pat:,.4f};  "
            f"Retained = {h_pat:,.4f} - {fy_in['DIV_PAID']:,.4f} = {h_ret:,.4f}",
        ]
        with st.expander("Step-by-step hand-calculation trace"):
            st.code("\n".join(trace), language="text")

    # ---- Source reconciliation ------------------------------------------------------------
    src_name = "Screener" if cd.get("source") == "screener" else "Yahoo Finance"
    st.markdown(f'<div class="section-h">{esc(src_name)} <em>reconciliation bridge</em></div>'
                '<div class="section-sub">The source\'s own reported figures against the MEROS ladder built from the current grid. The minority-interest gap '
                'is its own line, so reported tax stays honest and attributable profit still matches. Variances appear only if you override cells with '
                'auto-rebalance off.</div>', unsafe_allow_html=True)
    st.markdown(build_bridge_html(cd, res), unsafe_allow_html=True)
    if cd.get("cost_check"):
        cc = cd["cost_check"]
        msg = (f"Cost check passed in all {len(years)} years (tolerance ₹{cc['tolerance']} Cr)." if cc["passed"]
               else "Cost check FAILED for " + ", ".join(cc["flagged_years"]) + ".")
        st.caption("Screener cost check: the mapped cost lines rebuild Screener's own profit-before-tax. " + msg)
    xc = ctx.get("xcheck")
    if xc and xc.get("rows"):
        st.markdown('<div class="section-h">Screener vs Yahoo <em>cross-check</em></div>', unsafe_allow_html=True)
        st.markdown(build_xcheck_html(xc), unsafe_allow_html=True)
        st.caption(xc.get("message", ""))
    elif xc and xc.get("message"):
        st.caption(xc["message"])

    # ---- Provenance ------------------------------------------------------------------------
    prov = ctx.get("provenance")
    if prov is not None and len(prov):
        st.markdown('<div class="section-h">Where every number <em>came from</em></div>'
                    '<div class="section-sub">One row per Schedule III line. The tag shows whether the figure was Reported by the source, Derived from reported rows, '
                    'a Balancing figure, Not reported (shown as 0, never estimated), or changed by you. Hover a value for its exact source row or rule.</div>',
                    unsafe_allow_html=True)
        st.markdown(build_prov_html(prov, cd), unsafe_allow_html=True)

    # ---- Health ----------------------------------------------------------------------------
    st.markdown('<div class="section-h">Data-health <em>screen</em></div>', unsafe_allow_html=True)
    st.markdown(health_cards_html(ctx.get("health") or []), unsafe_allow_html=True)

    # ---- Raw source tables ----------------------------------------------------------------
    raw = ctx.get("raw_tables")
    if raw:
        st.markdown('<div class="section-h">Raw <em>source tables</em></div>'
                    f'<div class="section-sub">The untouched {esc(src_name)} data (₹ Cr). A ✔ marks the rows MEROS actually read, so you can see what was used and what was ignored.</div>',
                    unsafe_allow_html=True)
        for title, frame in raw.items():
            with st.expander(f"{src_name} · {title}"):
                st.dataframe(frame)
        cands = cd.get("payroll_candidates") or []
        if cands:
            st.info("Rows in Yahoo's income statement that look payroll-related but are not used automatically: " + ", ".join(c["row"] for c in cands) + ".")

    # ---- Assumptions ----------------------------------------------------------------------
    st.markdown('<div class="section-h">Assumptions &amp; <em>estimation register</em></div>'
                '<div class="section-sub">Everything MEROS had to assume because it cannot be read directly from the public data: what is assumed, why, and how to '
                'override it. ACTIVE means the assumption changed numbers for the company on screen; ALWAYS ON is a structural rule; OTHER SOURCE applies only to '
                'the other data source.</div>', unsafe_allow_html=True)
    st.markdown(render_register(cd), unsafe_allow_html=True)

    # ---- Hygiene and formulas ---------------------------------------------------------------
    audit = ctx.get("audit")
    if audit:
        st.markdown('<div class="section-h">Data hygiene <em>repair log</em></div>', unsafe_allow_html=True)
        with st.expander(f"Ingestion repairs · {audit['cells_repaired']} of {audit['total_cells']} cells ({audit['repair_pct']:.2f}%)"):
            h1, h2, h3 = st.columns(3)
            h1.metric("Total cells audited", audit["total_cells"])
            h2.metric("Cells repaired", audit["cells_repaired"])
            h3.metric("Repair rate", f"{audit['repair_pct']:.2f}%")
            if audit["repair_log"]:
                st.code("\n".join(audit["repair_log"]), language="text")
            else:
                st.caption("No repairs were needed: the grid was already clean.")
            if ctx.get("clean_df") is not None:
                st.caption("Cleaned grid used by the engine (float64, indexed by Line_ID)")
                st.dataframe(ctx["clean_df"].reset_index())
    st.markdown('<div class="section-h">Exact <em>vectorized</em> formulas</div>', unsafe_allow_html=True)
    for title, code in _FORMULAS.items():
        st.markdown(f"**{title}**")
        st.code(code, language="python")


# --------------------------------------------------------------------------------------
# Tab 6: compare companies
# --------------------------------------------------------------------------------------
NONE_PICK = "— choose a company to compare —"


def render_tab6(ctx: dict) -> dict | None:
    cd, res, ke = ctx["cd"], ctx["results"], float(ctx["ke_pct"])
    _head('Compare <em>companies</em>',
          "Put your current company next to a second one: same history window, same definitions, side by side. The second company's data comes live from Yahoo Finance.")
    loader, tdf = ctx.get("compare_loader"), ctx.get("ticker_df")
    if loader is None:
        st.info("Company comparison is not available in this session.")
        return None
    opts = ticker_options(tdf) if tdf is not None and len(tdf) else []
    sym2 = ""
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        if opts:
            pick = st.selectbox("Second company (type to search the NSE list)", [NONE_PICK] + opts, index=0, key="t6_pick")
            sym2 = label_to_symbol(tdf, pick) if pick != NONE_PICK else ""
        else:
            st.caption("The NSE company list is not loaded, so type the symbol instead.")
    with c2:
        typed = st.text_input("…or type any symbol (add .BO for BSE)", value="", key="t6_typed", help="Overrides the list when filled in.")
    if typed.strip():
        sym2 = typed.strip()
    if not sym2:
        st.info("Choose a second company above to see the comparison.")
        return None

    try:
        clean_symbol(sym2)
        cd2_full = loader(sym2)
    except ValueError as exc:
        st.error(str(exc))
        return None
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load {sym2!r}: {exc}")
        return None
    try:
        n_req = int((cd.get("window") or {}).get("requested", 0))
        cd2 = select_window(cd2_full, n_req)
        clean2, _audit2 = sanitize_statement_df(cd2["grid"], cd2["years"])
        res2 = compute_corporate_anatomy_and_vas(clean2, cd2["years"], cd2["attr_adj"])
    except ValueError as exc:
        st.error(f"Could not analyse {sym2!r}: {exc}")
        return None

    name1 = f"{cd.get('company_name') or ctx.get('source_label')}"
    name2 = f"{cd2.get('company_name') or sym2}"
    if name1 == name2:
        name2 += " (2)"
    cmp_ = comparison_frame([{"name": name1, "cd": cd, "results": res}, {"name": name2, "cd": cd2, "results": res2}], ke)
    frame, units = cmp_["frame"], cmp_["units"]

    if cmp_["notes"]:
        st.markdown(notice_html(cmp_["notes"], head="LIKE-FOR-LIKE ", alert=False), unsafe_allow_html=True)
    rows: list[tuple[str, str, list[str]]] = []
    for lab in frame.index:
        unit = units.get(lab, "cr")
        rows.append(("row", lab, [fmt_unit(frame.loc[lab, c], unit) for c in frame.columns]))
    st.markdown(render_table(["Latest year"] + [str(c) for c in frame.columns], rows), unsafe_allow_html=True)
    st.caption(f"EVA and WACC use your {ke:.1f}% cost of equity. n/a means the source does not report the inputs. No industry comparison is included (assumption E22).")

    ch1, ch2 = st.columns(2, gap="large")
    with ch1:
        meas = [("GVA margin", "GVA margin"), ("EBITDA margin", "EBITDA margin"), ("PAT margin", "PAT margin"), ("ROCE", "ROCE"), ("ROE", "ROE"), ("ROIC", "ROIC")]
        fig = go.Figure()
        allv = []
        for col, color in zip(frame.columns, (GOLD, CYAN)):
            vals = [_f(frame.loc[k, col]) for k, _l in meas]
            allv.append(vals)
            fig.add_trace(go.Bar(x=[m for _k, m in meas], y=vals, name=str(col), marker_color=color,
                                 text=[f"{v:.1f}%" if np.isfinite(v) else "n/a" for v in vals], textposition="outside", cliponaxis=False,
                                 hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:.2f}%<extra></extra>"))
        style_fig(fig, "Profitability & returns, latest year", 420)
        fig.update_layout(barmode="group", yaxis=dict(ticksuffix="%", range=pad_range(*allv)), legend=LEG_BELOW)
        show_chart(fig, "t6_ratio_chart")
    with ch2:
        fig = go.Figure()
        allr = []
        for (nm, r), color in zip(((name1, res), (name2, res2)), (GOLD, CYAN)):
            y = r["kpis"].loc["ROE_Pct", r["years"]].to_numpy(dtype="float64")
            allr.append(y)
            fig.add_trace(go.Scatter(x=r["years"], y=y, name=nm, mode="lines+markers", line=dict(color=color, width=3), marker=dict(size=8),
                                     hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.2f}%<extra></extra>"))
        style_fig(fig, "ROE over time", 420)
        fig.update_layout(yaxis=dict(ticksuffix="%", zeroline=True, range=pad_range(*allr, pad_low=True)), legend=LEG_BELOW)
        show_chart(fig, "t6_roe_chart")
    return cmp_