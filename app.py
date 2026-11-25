"""MEROS: Corporate Value-Added & Stakeholder Economics Tool.

Flow: welcome -> pick an NSE company (typable dropdown) -> Yahoo Finance fetch (usually 3-4 annual years) -> optional Screener
Excel upload for 5 / 10 years / since inception -> editable verification grid -> six analysis tabs -> Excel download.
Educational and academic use only; see the disclaimer badge at the bottom right of every page."""
from __future__ import annotations

from datetime import date, datetime
from urllib.parse import urlencode

import numpy as np
import streamlit as st

from analytics import (bridge_numbers, capital_returns, dupont, dupont_change, employee_state, health_checks, plain_notes, plain_summary,
                       provenance_frame, rebalance_to_pbt, select_window)
from corporate_engine import RECEIPT_LABELS, compute_corporate_anatomy_and_vas, generate_deterministic_diagnostics, sanitize_statement_df
from excel_export import build_export_workbook, export_filename
from meros_assumptions import DEFAULT_COE_PCT, HISTORY_OPTIONS
from screener_source import company_match_note, cross_check, download_guide, load_screener, screener_tables
from tabs_core import render_tab1, render_tab2, render_tab3
from tabs_more import assumption_rows, render_tab4, render_tab5, render_tab6
from tickers import (clean_symbol, exchange_of, label_to_symbol, listing_note, load_tickers, options as ticker_options, rename_hint,
                     symbol_info, symbol_to_label)
from ui_style import (ARCHITECT_HTML, COLOPHON, DL_KW, XLSX_MIME, download_card_html, fmt_cr, fmt_lakh, fmt_pct, fmt_rs, fmt_x, guide_html,
                      health_strip_html, inject_css, inject_disclaimer, kpi_card, kpi_grid, mast_html, notice_html, set_show_notes,
                      summary_html, welcome_html)
from yahoo_source import build_company_data as build_yahoo_cd, fetch_yahoo_raw, raw_tables as yahoo_raw_tables

st.set_page_config(page_title="MEROS | Corporate Value-Added & Stakeholder Economics Tool", page_icon="🪙", layout="wide",
                   initial_sidebar_state="expanded")
inject_css()
inject_disclaimer()

PICK_NONE = "— choose a company —"
VER_LABELS = ["Consolidated", "Standalone", "Not sure"]
VER_KEYS = {"Consolidated": "consolidated", "Standalone": "standalone", "Not sure": "unknown"}
HIST_LABELS = [lab for lab, _ in HISTORY_OPTIONS]
HIST_VALUES = dict(HISTORY_OPTIONS)


@st.cache_data(ttl=3600, show_spinner="Fetching audited filings from Yahoo Finance...")
def load_yahoo_raw(yahoo_symbol: str) -> dict:
    return fetch_yahoo_raw(yahoo_symbol)


def compare_loader(symbol_text: str) -> dict:
    s = str(symbol_text)
    return build_yahoo_cd(load_yahoo_raw(f"{clean_symbol(s)}.{exchange_of(s)}"))


def _bump_reset() -> None:
    st.session_state["grid_reset"] = int(st.session_state.get("grid_reset", 0)) + 1


def finish() -> None:
    st.markdown(COLOPHON, unsafe_allow_html=True)
    st.stop()


def qget(key: str, default: str = "") -> str:
    try:
        v = st.query_params.get(key)
    except Exception:  # noqa: BLE001
        v = None
    return default if v is None else str(v)


def qnum(key: str, default: float, lo: float, hi: float) -> float:
    try:
        v = float(qget(key, str(default)))
    except ValueError:
        v = float(default)
    return min(max(v, lo), hi)


def source_name(cd: dict) -> str:
    return "Screener" if cd.get("source") == "screener" else "Yahoo Finance"


# --------------------------------------------------------------------------------------
# Ticker list and query-string defaults
# --------------------------------------------------------------------------------------
tdf, tmsg = load_tickers()
opts = ticker_options(tdf)

qp_tk = qget("tk", "").strip()
qp_base = ""
if qp_tk:
    try:
        qp_base = clean_symbol(qp_tk)
    except ValueError:
        qp_base = ""
qp_label = symbol_to_label(tdf, qp_base) if (qp_base and len(tdf) and exchange_of(qp_tk) == "NS") else None
idx0 = (opts.index(qp_label) + 1) if (qp_label and qp_label in opts) else 0
other_default = "" if (qp_label or not qp_tk) else qp_tk
try:
    qp_n = int(qget("yrs", "4"))
except ValueError:
    qp_n = 4
hist_idx = next((i for i, (_lab, v) in enumerate(HISTORY_OPTIONS) if v == qp_n), 1)
qp_ver = qget("ver", "consolidated")
ver_idx = next((i for i, lab in enumerate(VER_LABELS) if VER_KEYS[lab] == qp_ver), 0)

# --------------------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="brand-title">MEROS <em>μέρος</em></div>'
                '<div class="brand-sub">Value-Added &amp; Stakeholder Economics Tool</div>', unsafe_allow_html=True)
    if opts:
        pick = st.selectbox("Company (click and type to search the NSE list)", [PICK_NONE] + opts, index=idx0,
                            help="Type a name or symbol, for example ITC, Infosys or HDFC. Renamed companies appear under their new symbol (ETERNAL, TMPV, TMCV).")
        typed_other = st.text_input("Symbol not in the list? Type it here", value=other_default,
                                    help="Overrides the list. Add .BO for BSE-only symbols, e.g. 500325.BO is not valid but RELIANCE.BO is.")
    else:
        pick = PICK_NONE
        typed_other = st.text_input("NSE / BSE ticker symbol", value=other_default or qp_tk, help="For example ITC, TCS, HDFCBANK. Add .BO for BSE.")
    st.caption(tmsg)
    hist_label = st.selectbox("History to analyse", HIST_LABELS, index=hist_idx,
                              help="Yahoo Finance usually provides the latest 3 to 4 annual years. For 5, 10 years or since inception, upload a free Screener Excel file.")
    n_req = int(HIST_VALUES[hist_label])
    with st.expander("Longer history & cross-check: upload a Screener Excel file", expanded=(n_req == 0 or n_req >= 5)):
        ver_label = st.radio("Which version did you download?", VER_LABELS, index=ver_idx, horizontal=True,
                             help="The workbook does not say whether it is Consolidated or Standalone, so MEROS needs you to tell it.")
        up = st.file_uploader("Screener .xlsx file", type=["xlsx"], key="scr_file")
        st.caption("Download it from the company's Screener page (the guide appears on the main page when you pick 5 or 10 years). MEROS reads the file "
                   "in your browser session only and stores nothing.")
    ver_key = VER_KEYS[ver_label]
    st.divider()
    fy_slot = st.container()
    ke_pct = st.number_input("Cost of equity for full EVA (%)", min_value=1.0, max_value=40.0, value=qnum("ke", DEFAULT_COE_PCT, 1.0, 40.0),
                             step=0.5, format="%.1f",
                             help="Used for EVA and WACC. Filings contain no cost of equity, so this is YOUR required return; 12% is only an illustrative default.")
    show_notes = st.toggle("Plain-English summary & KPI notes", value=(qget("notes", "1") != "0"))
    st.caption("All monetary values in ₹ Crores. Deterministic Python engine: no AI.")
    dl_side_slot = st.container()
    share_slot = st.container()
    st.markdown(ARCHITECT_HTML, unsafe_allow_html=True)

set_show_notes(show_notes)
ke = float(ke_pct)

mast_slot, guide_slot, editor_slot, export_slot = st.container(), st.container(), st.container(), st.container()

# --------------------------------------------------------------------------------------
# Which company?
# --------------------------------------------------------------------------------------
sym_raw = typed_other.strip() if typed_other.strip() else (label_to_symbol(tdf, pick) if pick != PICK_NONE else "")
if not sym_raw:
    st.markdown(welcome_html(), unsafe_allow_html=True)
    st.info("Choose a company in the sidebar to begin: click the Company box and start typing a name or symbol.")
    finish()
try:
    sym = clean_symbol(sym_raw)
except ValueError as exc:
    st.error(str(exc))
    finish()
ex = exchange_of(sym_raw)
ysym = f"{sym}.{ex}"
info = symbol_info(tdf, sym)
list_name = info["name"] if info else ""
hint_msgs = [m for m in (rename_hint(sym_raw, tdf), listing_note(tdf, sym_raw)) if m]

# --------------------------------------------------------------------------------------
# Load data: Yahoo (always tried) and Screener (if uploaded)
# --------------------------------------------------------------------------------------
yahoo_raw, yahoo_cd, yahoo_err = None, None, ""
try:
    yahoo_raw = load_yahoo_raw(ysym)
    yahoo_cd = build_yahoo_cd(yahoo_raw)
except ValueError as exc:
    yahoo_err = str(exc)
except Exception as exc:  # noqa: BLE001
    yahoo_err = f"Could not reach Yahoo Finance for {ysym}: {exc}"

scr_cd, scr_parsed, scr_err, xcheck = None, None, "", None
if up is not None:
    hints: dict = {}
    if yahoo_cd is not None:
        yg = yahoo_cd["grid"].set_index("Line_ID")
        hints = {"company_name": yahoo_cd["company_name"], "sector": yahoo_cd.get("sector", ""), "industry": yahoo_cd.get("industry", ""),
                 "is_financial": bool(yahoo_cd.get("is_financial")), "headcount": float(yg.loc["HEADCOUNT", yahoo_cd["years"][-1]])}
    elif list_name:
        hints = {"company_name": list_name}
    try:
        scr_cd, scr_parsed = load_screener(up, ver_key, sym, hints)
    except ValueError as exc:
        scr_err = str(exc)
    except Exception as exc:  # noqa: BLE001
        scr_err = f"Could not read the Screener file: {exc}"

cd_full, src, version_text = None, "", ("consolidated" if ver_key == "unknown" else ver_key)
if scr_cd is not None:
    xcheck = cross_check(scr_cd, yahoo_cd)
    cd_full, src = scr_cd, "screener"
elif yahoo_cd is not None:
    cd_full, src = yahoo_cd, "yahoo"

need_guide = cd_full is None or (src == "yahoo" and (n_req == 0 or n_req > len(yahoo_cd["years"])))
with guide_slot:
    for m in hint_msgs:
        st.info(m)
    if scr_err:
        st.error("Screener file: " + scr_err)
    if scr_cd is not None:
        mm = company_match_note(scr_cd.get("file_company_name", ""), list_name or (yahoo_cd or {}).get("company_name", ""))
        if mm:
            st.warning(mm)
        if yahoo_err:
            st.warning("Yahoo Finance data was not available (" + yahoo_err + "), so the cross-check and the headcount were skipped.")
    if cd_full is None:
        st.error(yahoo_err or "No data could be loaded for this company.")
    elif need_guide:
        avail = len(yahoo_cd["years"]) if yahoo_cd else 0
        st.info(f"You asked for \"{hist_label}\", but Yahoo Finance provides only {avail} annual years for {sym}. MEROS is showing those {avail} years. "
                "For a longer history, follow the steps below and upload the Screener file in the sidebar.")
    if need_guide:
        st.markdown(guide_html(download_guide(sym, version_text), sym, version_text), unsafe_allow_html=True)
if cd_full is None:
    finish()

# --------------------------------------------------------------------------------------
# Window, editable grid, engine
# --------------------------------------------------------------------------------------
cd = select_window(cd_full, n_req)
years = cd["years"]
company_name = cd.get("company_name") or sym
source_label = f"{company_name} ({sym})"

with editor_slot:
    with st.expander("Verification & Custom Override Grid (Editable)", expanded=False):
        st.caption(f"The 12-line Schedule III grid built from {source_name(cd)} (₹ Crores; headcount in persons). Edit any cell, for example employee "
                   "cost or headcount when the source does not report them, and every KPI, chart and the Excel file recompute. "
                   "Cells marked 'Not reported' in Tab 5 show 0 here.")
        c_a, c_b = st.columns([3, 1])
        rebalance_on = c_a.checkbox("Keep the source's profit-before-tax (auto-rebalance Other Operating Expenses after my edits)", value=True, key="grid_rebalance")
        c_b.button("Reset grid", key="grid_reset_btn", on_click=_bump_reset)
        cfg = {"Line_ID": st.column_config.TextColumn("Line ID", width="small"),
               "Line_Item_Name": st.column_config.TextColumn("Schedule III line item", width="large"),
               "Category": st.column_config.TextColumn("Category", width="small")}
        for yr, lab in zip(years, cd["period_labels"]):
            cfg[yr] = st.column_config.NumberColumn(f"{yr} · {lab}", format="%.2f", step=0.01)
        ed_key = f"grid_{src}_{sym}_{ex}_{n_req}_{ver_key}_{int(st.session_state.get('grid_reset', 0))}"
        edited = st.data_editor(cd["grid"], key=ed_key, hide_index=True, num_rows="fixed",
                                disabled=["Line_ID", "Line_Item_Name", "Category"], column_config=cfg)
        grid_final = rebalance_to_pbt(edited, cd["anchors"]["PBT"], years) if rebalance_on else edited
        st.caption("Auto-rebalance ON: edits to employee cost, depreciation and similar lines are balanced by Other Operating Expenses so profit before tax "
                   "stays at the source's figure. Turn it off to edit those rows freely; the Tab 5 bridge then shows the variance.")

try:
    clean_df, audit = sanitize_statement_df(grid_final, years)
    results = compute_corporate_anatomy_and_vas(clean_df, years, cd["attr_adj"])
except (ValueError, TypeError) as exc:
    st.error(f"The statement could not be processed: {exc}")
    finish()

with fy_slot:
    fy_opts = years[::-1]
    qfy = qget("fy", "")
    active_fy = st.selectbox("Active fiscal year", fy_opts, index=fy_opts.index(qfy) if qfy in fy_opts else 0,
                             help="The year used for the receipt, KPI cards and DuPont/EVA highlights. Growth rates always run over the whole window.")
    st.caption(" · ".join(f"{y} → {lab}" for y, lab in zip(years, cd["period_labels"])))

pnl, kpis, cagr, inputs, cs = results["pnl"], results["kpis"], results["cagr"], results["inputs"], results["common_size"]
if float(pnl.loc["Total_Income", active_fy]) <= 0:
    st.error(f"Total income for {active_fy} is zero or negative. Choose another year or correct the grid.")
    finish()

emp_state = employee_state(cd, inputs)
capret = capital_returns(results, cd, ke)
dp = dupont(results, cd)
dchg = {"3": dupont_change(dp, "3"), "5": dupont_change(dp, "5")}
health = health_checks(results, cd, xcheck)
prov_df = provenance_frame(cd, inputs, rebalanced=rebalance_on)
diagnostics = generate_deterministic_diagnostics(results)
nt = plain_notes(results, active_fy, cd)
summary_text = plain_summary(cd, results, active_fy, emp_state)
if src == "screener":
    raw_tbls = screener_tables(scr_parsed)
else:
    raw_tbls = yahoo_raw_tables(yahoo_raw, yahoo_cd["used_rows"])

# ---- shareable link ------------------------------------------------------------------------
qp_out = {"tk": sym_raw, "yrs": str(n_req), "ver": ver_key, "ke": f"{ke:g}", "notes": "1" if show_notes else "0", "fy": active_fy}
try:
    st.query_params.from_dict(qp_out)
except Exception:  # noqa: BLE001
    pass
with share_slot:
    with st.expander("Share this view"):
        st.caption("Add this to your app's web address. It stores only your selections, never the data. Uploaded Screener files cannot be shared by link.")
        st.code("?" + urlencode(qp_out), language="text")

# --------------------------------------------------------------------------------------
# Masthead, notices, KPI cards
# --------------------------------------------------------------------------------------
lines = [f"{source_name(cd)} · {len(years)} annual periods ({years[0]} to {years[-1]}) · period ends {cd['period_labels'][0]} to {cd['period_labels'][-1]} "
         f"· ₹ Crores · {cd.get('sector') or 'sector not stated'}"]
if cd.get("basis_note"):
    lines.append("Basis: " + cd["basis_note"])
if (cd.get("window") or {}).get("note"):
    lines.append(cd["window"]["note"])
for k in ("emp", "headcount", "tax", "opex"):
    if cd["notes"].get(k):
        lines.append("▸ " + cd["notes"][k])
if emp_state == "user":
    lines.append("▸ You have overridden employee cost in the grid, so the employee-cost note above describes the source data, not the figures now shown.")
for w in cd.get("warnings") or []:
    lines.append("▸ " + w)
if xcheck and xcheck.get("status") in ("flag", "ok"):
    lines.append("▸ Cross-check: " + xcheck["message"])
triggered = sorted(k for k, v in (cd.get("status") or {}).items() if v == "active")
lines.append("▸ Assumptions triggered for this company: " + (", ".join(triggered) if triggered else "none beyond the structural ones")
             + ". Full reasoning: Tab 5 → Assumptions & Estimation Register.")

with mast_slot:
    st.markdown(mast_html(source_label, active_fy, "Screener upload" if src == "screener" else "Yahoo Finance feed"), unsafe_allow_html=True)
    st.markdown(notice_html(lines, head="SOURCE ", alert=(emp_state == "not_reported")), unsafe_allow_html=True)
    if show_notes:
        st.markdown(summary_html(summary_text), unsafe_allow_html=True)
    st.markdown(health_strip_html(health), unsafe_allow_html=True)

fy = active_fy
ti_fy, gva_fy = float(pnl.loc["Total_Income", fy]), float(pnl.loc["GVA", fy])
rev_cagr = float(cagr["Revenue_CAGR_Pct"])
pat_bite = float(cs.loc[RECEIPT_LABELS[6], fy] + cs.loc[RECEIPT_LABELS[7], fy])
pat_margin = float(kpis.loc["PAT_Margin_Pct", fy])
va_emp, hc_roi = float(kpis.loc["Value_Added_Per_Emp_Lakhs", fy]), float(kpis.loc["Human_Capital_ROI", fy])
closure_ok = bool(results["vas_closure_check"])
closure_txt = "Verified ✅" if closure_ok else "Breach ⚠️"
cagr_tone = "t-gold" if not np.isfinite(rev_cagr) else ("t-green" if rev_cagr >= 10 else ("t-gold" if rev_cagr >= 0 else "t-red"))
pat_tone = "t-green" if pat_margin >= 10 else ("t-amber" if pat_margin > 0 else "t-red")
hyg_tone = "t-red" if not closure_ok else ("t-amber" if audit["cells_repaired"] > 0 else "t-green")
emp_flag, k4_tone = "", "t-cyan"
if emp_state == "not_reported":
    emp_flag, k4_tone = " · EMP COST NOT REPORTED", "t-red"
elif emp_state == "partial":
    emp_flag, k4_tone = " · EMP COST PARTIAL", "t-amber"
elif emp_state == "user":
    emp_flag, k4_tone = " · EMP COST USER-SET", "t-gold"
span_txt = f"{len(years) - 1}-yr revenue CAGR" if len(years) >= 2 else "Revenue CAGR"

st.markdown(kpi_grid([
    kpi_card("Total Income", fmt_cr(ti_fy), f"{fy} · Revenue + Other Income", f"{span_txt} {fmt_pct(rev_cagr, 1, True)}", cagr_tone, nt["ti"]),
    kpi_card("Gross Value Added", fmt_cr(gva_fy), f"{fy} · Income less bought-in costs",
             f"GVA Margin {fmt_pct(float(kpis.loc['GVA_Margin_Pct', fy]), 1)}", "t-gold", nt["gva"]),
    kpi_card("Consumer Net Profit Bite", f"{fmt_rs(pat_bite)} per ₹100 spent", f"{fy} · PAT per ₹100 of income",
             f"PAT Margin {fmt_pct(pat_margin, 2)}", pat_tone, nt["bite"]),
    kpi_card("Workforce Productivity", f"{fmt_lakh(va_emp, 1)} / Emp" if np.isfinite(va_emp) else "Not available",
             f"{fy} · Value added per employee{emp_flag}", f"Human Capital ROI {fmt_x(hc_roi)}", k4_tone, nt["wf"]),
    kpi_card("Data Hygiene & Closure", f"{audit['cells_repaired']} cells", f"auto-cleaned | {audit['repair_pct']:.1f}% of {audit['total_cells']} cells",
             f"VAS Closure: {closure_txt}", hyg_tone, nt["hyg"]),
]), unsafe_allow_html=True)

with st.expander(f"Data hygiene audit log · {audit['cells_repaired']} repairs"):
    if audit["repair_log"]:
        st.code("\n".join(audit["repair_log"]), language="text")
    else:
        st.caption("No repairs were needed: the grid was already clean.")

# --------------------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------------------
ctx = {"cd": cd, "results": results, "active_fy": active_fy, "source_label": source_label, "emp_state": emp_state, "ke_pct": ke,
       "capital": capret, "dupont": dp, "dupont_change": dchg, "notes": nt, "diagnostics": diagnostics,
       "provenance": prov_df, "health": health, "xcheck": xcheck, "raw_tables": raw_tbls, "audit": audit, "clean_df": clean_df,
       "ticker_df": tdf, "compare_loader": compare_loader}

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["1. ₹100 Consumer Anatomy", "2. Stakeholder Value-Added (VAS)", "3. Workforce, Capital, DuPont & EVA",
                                              "4. Margin Shock Simulator", "5. Glass-Box Audit & Assumptions", "6. Compare Companies"])
with tab1:
    render_tab1(ctx)
with tab2:
    render_tab2(ctx)
with tab3:
    render_tab3(ctx)
with tab4:
    sim = render_tab4(ctx)
with tab5:
    render_tab5(ctx)
with tab6:
    cmp_ = render_tab6(ctx)

# --------------------------------------------------------------------------------------
# Excel download (built after the tabs so it can include the shock scenario and the comparison)
# --------------------------------------------------------------------------------------
kind_text = "Yahoo Finance (live)" if src == "yahoo" else f"Screener upload ({ver_label}); Yahoo Finance used only for the cross-check and headcount"
xl_ctx = {"cd": cd, "results": results, "capital": capret, "ke_pct": ke, "dupont": dp, "dupont_change": dchg, "diagnostics": diagnostics,
          "health": health, "bridge": bridge_numbers(cd, results), "provenance": prov_df, "assumptions": assumption_rows(cd), "sim": sim,
          "comparison": cmp_, "xcheck": xcheck, "raw": raw_tbls, "summary_text": summary_text, "active_fy": active_fy,
          "source_label": source_label, "source_kind": kind_text, "generated_at": datetime.now().strftime("%d %b %Y %H:%M"), "today": date.today()}
xbytes, xname, xerr = None, "", ""
try:
    xbytes = build_export_workbook(xl_ctx)
    xname = export_filename(xl_ctx)
except Exception as exc:  # noqa: BLE001
    xerr = str(exc)

with export_slot:
    if xbytes:
        st.markdown(download_card_html("DOWNLOAD THE FULL ANALYSIS",
                                       "One Excel file with every table, the EVA and DuPont sheets with live formulas, data-health checks, provenance, "
                                       "assumptions, your edits and the raw source data."), unsafe_allow_html=True)
        st.download_button("⬇ Download full analysis (.xlsx)", data=xbytes, file_name=xname, mime=XLSX_MIME, key="dl_main", **DL_KW)
    else:
        st.warning("The Excel file could not be built: " + xerr)
with dl_side_slot:
    if xbytes:
        st.download_button("⬇ Download full analysis (.xlsx)", data=xbytes, file_name=xname, mime=XLSX_MIME, key="dl_side", **DL_KW)

st.markdown(COLOPHON, unsafe_allow_html=True)