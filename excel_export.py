"""MEROS Excel export: build the downloadable analysis workbook (openpyxl only).

The EVA and DuPont sheets hold LIVE formulas (driven by a 'Model inputs' sheet and a cost-of-equity input cell) plus a
stored-values block so the numbers still show in viewers that do not calculate formulas. Everything else is values.

build_export_workbook(ctx) -> bytes, where ctx is a dict with:
  required: cd (windowed company data), results (engine results), capital (analytics.capital_returns), dupont (analytics.dupont),
            ke_pct, active_fy, source_label, source_kind, summary_text, diagnostics, health, assumptions
            (list of (id, scope, area, assumption, why, effect, state))
  optional: dupont_change ({'3': ..., '5': ...}), bridge, provenance (DataFrame), sim (simulate_margin_shock result),
            comparison (analytics.comparison_frame result), xcheck (screener_source.cross_check result),
            raw ({sheet title: DataFrame}), generated_at, today
"""
from __future__ import annotations

import datetime as _dt
import io
import re

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter as L

from analytics import CAP_LAYOUT
from corporate_engine import SCHEMA
from meros_assumptions import APP_NAME, CREATOR, DATA_SOURCES_NOTE, DISCLAIMER_EXCEL, DISCLAIMER_FULL

GOLD = "E5A93C"
HDR_FILL = PatternFill("solid", fgColor=GOLD)
SEC_FILL = PatternFill("solid", fgColor="FBEFD2")
INPUT_FILL = PatternFill("solid", fgColor="FFF4C2")
STORED_FILL = PatternFill("solid", fgColor="EEF2F7")
HDR_FONT = Font(bold=True, color="1A1204")
TITLE_FONT = Font(bold=True, size=14)
SUB_FONT = Font(italic=True, color="666666")
BOLD = Font(bold=True)
INPUT_FONT = Font(bold=True, color="0000FF")
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(wrap_text=True, vertical="center")

F_CR = "#,##0.00;[Red]-#,##0.00"
F_PCT = "0.00%"
F_PP = "0.00"
F_X = '0.00"x"'
F_INT = "#,##0"
UNIT_FMT = {"cr": F_CR, "pct": '0.00"%"', "x": F_X, "lakh": F_CR, "icr": F_X, "rs": F_CR, "pp": F_PP, "int": F_INT, "text": "@"}

FOOTER_TEXT = f"{APP_NAME} · Educational & academic tool · not investment advice · data may be inaccurate"

MI = "'Model inputs'!"
MI_ROW = {"TI": 5, "GVA": 6, "EBIT": 7, "FIN": 8, "PBT": 9, "TAX": 10, "NI": 11, "DEBT": 12, "EQ": 13, "TA": 14}
MI_FIRST_YEAR_COL = 3


# --------------------------------------------------------------------------------------
# Cell helpers
# --------------------------------------------------------------------------------------
def _clean(v: object) -> object:
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return f if np.isfinite(f) else None
    if isinstance(v, (pd.Timestamp, _dt.datetime, _dt.date)):
        return str(v)[:10]
    return str(v)


def _put(ws, row: int, col: int, value: object, fmt: str | None = None, font: Font | None = None,
         fill: PatternFill | None = None, align: Alignment | None = None):
    c = ws.cell(row=row, column=col)
    v = _clean(value)
    c.value = v
    if isinstance(v, str) and v.startswith("="):
        c.data_type = "s"  # text that merely starts with '=' must not become a formula
    if fmt and isinstance(v, (int, float)) and not isinstance(v, bool):
        c.number_format = fmt
    if font:
        c.font = font
    if fill:
        c.fill = fill
    if align:
        c.alignment = align
    return c


def _formula(ws, row: int, col: int, formula: str, fmt: str | None = None, fill: PatternFill | None = None):
    c = ws.cell(row=row, column=col)
    c.value = formula
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = fill
    return c


def _sheet(wb: Workbook, title: str, desc: str, tab: str | None = None):
    name = re.sub(r"[\[\]\*\?:/\\]", "-", title)[:31]
    base, k = name, 2
    while name in wb.sheetnames:
        name = f"{base[:28]}-{k}"
        k += 1
    ws = wb.create_sheet(name)
    _put(ws, 1, 1, title, font=TITLE_FONT)
    _put(ws, 2, 1, desc, font=SUB_FONT)
    ws.oddFooter.center.text = FOOTER_TEXT
    ws.oddFooter.center.size = 8
    if tab:
        ws.sheet_properties.tabColor = tab
    return ws


def _header(ws, row: int, labels: list[str], start_col: int = 1) -> None:
    for j, lab in enumerate(labels):
        _put(ws, row, start_col + j, lab, font=HDR_FONT, fill=HDR_FILL, align=CENTER)


def _section(ws, row: int, text: str, ncols: int) -> None:
    for j in range(ncols):
        _put(ws, row, 1 + j, text if j == 0 else None, font=BOLD, fill=SEC_FILL)


def _table(ws, df: pd.DataFrame, row: int, index: bool = True, index_label: str = "", fmt: str = F_CR,
           row_formats: dict | None = None, text_wrap_cols: tuple[int, ...] = ()) -> int:
    headers = ([index_label] if index else []) + [str(c) for c in df.columns]
    _header(ws, row, headers)
    r = row + 1
    for idx, rec in zip(df.index, df.itertuples(index=False, name=None)):
        vals = ([idx] if index else []) + list(rec)
        rf = (row_formats or {}).get(str(idx), fmt)
        for j, v in enumerate(vals, start=1):
            c = _put(ws, r, j, v, fmt=rf)
            if j in text_wrap_cols:
                c.alignment = WRAP
        r += 1
    return r + 1


def _kv(ws, rows: list[tuple[str, object]], row: int) -> int:
    for k, v in rows:
        _put(ws, row, 1, k, font=BOLD, align=WRAP)
        _put(ws, row, 2, v, align=WRAP)
        row += 1
    return row + 1


def _autowidth(ws, cap: int = 58, floor: int = 8) -> None:
    widths: dict[int, int] = {}
    for row in ws.iter_rows(min_row=3):
        for c in row:
            if c.value is None or c.data_type == "f":
                continue
            ln = len(str(c.value))
            if ln > 70:
                continue
            widths[c.column] = max(widths.get(c.column, floor), ln + 2)
    for col, w in widths.items():
        ws.column_dimensions[L(col)].width = min(cap, w)


def _kpi_unit(name: str) -> str:
    if name.endswith("_Pct"):
        return "%"
    if "Lakhs" in name:
        return "₹ Lakh"
    if name == "Capital_Employed" or name.endswith("_Cr"):
        return "₹ Cr"
    if name in ("Interest_Coverage_Ratio", "Debt_to_EBITDA", "Human_Capital_ROI"):
        return "x"
    return ""


def export_filename(ctx: dict) -> str:
    cd = ctx.get("cd") or {}
    sym = re.sub(r"[^A-Za-z0-9_-]", "", str(cd.get("symbol") or ctx.get("source_label") or "company")) or "company"
    years = ctx["results"]["years"]
    today = ctx.get("today") or _dt.date.today()
    return f"MEROS_{sym}_{years[0]}-{years[-1]}_{today:%Y%m%d}.xlsx"


# --------------------------------------------------------------------------------------
# Sheets with formulas
# --------------------------------------------------------------------------------------
def _model_inputs(ws, ctx: dict) -> None:
    cd, res = ctx["cd"], ctx["results"]
    years, n = res["years"], len(res["years"])
    pnl, inp = res["pnl"], res["inputs"]
    opening = cd.get("opening") or {}
    ta = (cd.get("extras") or {}).get("TOTAL_ASSETS") or [None] * n

    _put(ws, 3, 1, "Period end", font=SUB_FONT)
    _put(ws, 3, 2, opening.get("label"), font=SUB_FONT)
    for j in range(n):
        _put(ws, 3, MI_FIRST_YEAR_COL + j, cd["period_labels"][j], font=SUB_FONT)
    _header(ws, 4, ["Line (₹ Cr)", "Opening balance"] + list(years))

    def series(key: str) -> list:
        if key == "TI":
            return pnl.loc["Total_Income", years].tolist()
        if key == "GVA":
            return pnl.loc["GVA", years].tolist()
        if key == "EBIT":
            return pnl.loc["EBIT", years].tolist()
        if key == "FIN":
            return inp.loc["FIN_COST", years].tolist()
        if key == "PBT":
            return pnl.loc["PBT", years].tolist()
        if key == "TAX":
            return pnl.loc["Tax_Expense", years].tolist()
        if key == "NI":
            return res["pat_attr"].tolist()
        if key == "DEBT":
            return inp.loc["TOTAL_DEBT", years].tolist()
        if key == "EQ":
            return inp.loc["TOTAL_EQUITY", years].tolist()
        return list(ta)

    labels = {"TI": "Total income", "GVA": "Gross value added", "EBIT": "EBIT (operating profit before finance cost)",
              "FIN": "Finance cost", "PBT": "Profit before tax", "TAX": "Tax expense (as reported)",
              "NI": "Profit attributable to shareholders", "DEBT": "Total debt (borrowings)",
              "EQ": "Shareholders' equity", "TA": "Total assets"}
    open_vals = {"DEBT": opening.get("TOTAL_DEBT"), "EQ": opening.get("TOTAL_EQUITY"), "TA": opening.get("TOTAL_ASSETS")}
    for key, r in MI_ROW.items():
        _put(ws, r, 1, labels[key], font=BOLD)
        _put(ws, r, 2, open_vals.get(key), fmt=F_CR)
        for j, v in enumerate(series(key)):
            _put(ws, r, MI_FIRST_YEAR_COL + j, v, fmt=F_CR)
    _put(ws, 16, 1, "Blank cells mean the source does not report that figure. The EVA and DuPont sheets read these numbers; "
                    "edit them here to test your own figures.", font=SUB_FONT)
    ws.column_dimensions["A"].width = 44
    for j in range(2, 3 + n):
        ws.column_dimensions[L(j)].width = 16
    ws.freeze_panes = "C5"


def _mi(key: str, j: int) -> str:
    return f"{MI}{L(MI_FIRST_YEAR_COL + j)}{MI_ROW[key]}"


def _eva_sheet(ws, ctx: dict) -> None:
    res, cap = ctx["results"], ctx["capital"]
    years, n = res["years"], len(res["years"])
    ke = float(ctx["ke_pct"]) / 100.0

    _put(ws, 4, 1, "Cost of equity (INPUT, edit this cell)", font=BOLD)
    _put(ws, 4, 2, ke, fmt=F_PCT, font=INPUT_FONT, fill=INPUT_FILL)
    _put(ws, 5, 1, "Filings contain no cost of equity: this is YOUR required return, not a market estimate (assumption E11).", font=SUB_FONT)

    _header(ws, 7, ["A. EVA (LIVE FORMULAS)"] + list(years))
    rows = {"ebit": 8, "t": 9, "nopat": 10, "debt": 11, "eq": 12, "ce": 13, "kd": 14, "we": 15, "wacc": 16, "charge": 17, "eva": 18,
            "roic": 19, "spread": 20}
    names = {"ebit": "EBIT", "t": "Tax rate on operating profit (reported tax ÷ PBT, clipped to 0-40%)", "nopat": "NOPAT = EBIT × (1 − tax rate)",
             "debt": "Total debt", "eq": "Shareholders' equity", "ce": "Capital employed (debt + equity)", "kd": "Implied cost of debt (finance cost ÷ debt)",
             "we": "Weight of equity (book value)", "wacc": "WACC = We × Ke + (1 − We) × Kd × (1 − tax rate)",
             "charge": "Capital charge = WACC × capital employed", "eva": "ECONOMIC VALUE ADDED = NOPAT − capital charge",
             "roic": "ROIC = NOPAT ÷ capital employed", "spread": "ROIC − WACC"}
    for key, r in rows.items():
        _put(ws, r, 1, names[key], font=BOLD if key in ("eva", "nopat", "wacc") else None)
    for j in range(n):
        c = 2 + j
        col = L(c)
        _formula(ws, rows["ebit"], c, f"={_mi('EBIT', j)}", F_CR)
        _formula(ws, rows["t"], c, f"=MIN(0.4,MAX(0,IF({_mi('PBT', j)}>0,{_mi('TAX', j)}/{_mi('PBT', j)},0)))", F_PCT)
        _formula(ws, rows["nopat"], c, f"={col}{rows['ebit']}*(1-{col}{rows['t']})", F_CR)
        _formula(ws, rows["debt"], c, f"={_mi('DEBT', j)}", F_CR)
        _formula(ws, rows["eq"], c, f"={_mi('EQ', j)}", F_CR)
        _formula(ws, rows["ce"], c, f"={col}{rows['debt']}+{col}{rows['eq']}", F_CR)
        _formula(ws, rows["kd"], c, f"=IF({col}{rows['debt']}>0,{_mi('FIN', j)}/{col}{rows['debt']},0)", F_PCT)
        _formula(ws, rows["we"], c, f'=IF({col}{rows["ce"]}>0,{col}{rows["eq"]}/{col}{rows["ce"]},"")', F_PCT)
        _formula(ws, rows["wacc"], c, f'=IFERROR({col}{rows["we"]}*$B$4+(1-{col}{rows["we"]})*{col}{rows["kd"]}*(1-{col}{rows["t"]}),"")', F_PCT)
        _formula(ws, rows["charge"], c, f'=IFERROR({col}{rows["wacc"]}*{col}{rows["ce"]},"")', F_CR)
        _formula(ws, rows["eva"], c, f'=IFERROR({col}{rows["nopat"]}-{col}{rows["charge"]},"")', F_CR)
        _formula(ws, rows["roic"], c, f'=IF({col}{rows["ce"]}>0,{col}{rows["nopat"]}/{col}{rows["ce"]},"")', F_PCT)
        _formula(ws, rows["spread"], c, f'=IFERROR({col}{rows["roic"]}-{col}{rows["wacc"]},"")', F_PCT)

    _header(ws, 23, ["B. MEROS STORED VALUES (shown even if your viewer does not calculate formulas)"] + list(years))
    stored = [("T_RATE", "Tax rate on operating profit", F_PCT, 100.0), ("NOPAT", "NOPAT", F_CR, 1.0), ("WACC", "WACC", F_PCT, 100.0),
              ("CHARGE", "Capital charge", F_CR, 1.0), ("EVA", "Economic Value Added", F_CR, 1.0), ("ROIC", "ROIC", F_PCT, 100.0),
              ("SPREAD", "ROIC − WACC", F_PCT, 100.0)]
    srow: dict[str, int] = {}
    for i, (key, label, fmt, div) in enumerate(stored):
        r = 24 + i
        srow[key] = r
        _put(ws, r, 1, label)
        for j in range(n):
            v = float(cap[key][j])
            _put(ws, r, 2 + j, (v / div) if np.isfinite(v) else None, fmt=fmt, fill=STORED_FILL)
    _header(ws, 32, ["C. CHECK: live formula − stored value (0 while the cost of equity is unchanged)"] + list(years))
    for i, (key, label, rkey) in enumerate([("wacc", "WACC difference", "WACC"), ("eva", "EVA difference (₹ Cr)", "EVA")]):
        r = 33 + i
        _put(ws, r, 1, label)
        for j in range(n):
            col = L(2 + j)
            _formula(ws, r, 2 + j, f'=IFERROR({col}{rows[key]}-{col}{srow[rkey]},"")', F_CR if key == "eva" else F_PCT)
    _put(ws, 36, 1, "Notes: book-value weights understate equity for companies trading above book, so WACC is probably too low for them (E12). "
                    "Not meaningful for banks.", font=SUB_FONT)
    ws.column_dimensions["A"].width = 74
    for j in range(n):
        ws.column_dimensions[L(2 + j)].width = 16


def _dupont_sheet(ws, ctx: dict) -> None:
    res, dp = ctx["results"], ctx["dupont"]
    years, n = res["years"], len(res["years"])
    v = dp["values"]
    if not dp.get("available"):
        _put(ws, 4, 1, "DuPont is not available: " + str(dp.get("reason") or "required data is missing."), font=BOLD)
    if dp.get("bank"):
        _put(ws, 5, 1, "This is a bank / financial company: DuPont figures are indicative only (assumption E13).", font=SUB_FONT)

    _header(ws, 7, ["A. INPUTS (read from the Model inputs sheet)"] + list(years))
    inputs = [("ti", "Total income", "TI"), ("ni", "Profit attributable to shareholders", "NI"), ("pbt", "Profit before tax", "PBT"),
              ("ebit", "EBIT", "EBIT"), ("ta", "Total assets (year-end)", "TA"), ("eq", "Shareholders' equity (year-end)", "EQ")]
    irow = {k: 8 + i for i, (k, _l, _m) in enumerate(inputs)}
    for k, label, mkey in inputs:
        _put(ws, irow[k], 1, label)
        for j in range(n):
            _formula(ws, irow[k], 2 + j, f'=IF(ISNUMBER({_mi(mkey, j)}),{_mi(mkey, j)},"")', F_CR)

    _header(ws, 15, ["B. DUPONT (LIVE FORMULAS)"] + list(years))
    f = {"nm": 16, "at": 17, "em": 18, "roe3": 19, "tb": 21, "ib": 22, "ebitm": 23, "roe5": 24, "direct": 26, "resid": 27}
    names = {"nm": "Net profit margin = attributable profit ÷ total income", "at": "Asset turnover = total income ÷ total assets",
             "em": "Equity multiplier = total assets ÷ equity", "roe3": "ROE (3-step) = margin × turnover × multiplier",
             "tb": "Tax & minority burden = attributable profit ÷ PBT", "ib": "Interest burden = PBT ÷ EBIT",
             "ebitm": "EBIT margin = EBIT ÷ total income", "roe5": "ROE (5-step) = burden × burden × EBIT margin × turnover × multiplier",
             "direct": "ROE measured directly = attributable profit ÷ equity", "resid": "Direct ROE − 3-step ROE (should be 0)"}
    for k, r in f.items():
        _put(ws, r, 1, names[k], font=BOLD if k in ("roe3", "roe5") else None)
    for j in range(n):
        c = 2 + j
        col = L(c)
        ti, ni, pbt, ebit, ta, eq = (f"{col}{irow[x]}" for x in ("ti", "ni", "pbt", "ebit", "ta", "eq"))
        _formula(ws, f["nm"], c, f'=IFERROR(IF({ti}>0,{ni}/{ti},""),"")', F_PCT)
        _formula(ws, f["at"], c, f'=IFERROR(IF({ta}>0,{ti}/{ta},""),"")', F_X)
        _formula(ws, f["em"], c, f'=IFERROR(IF(AND({ta}>0,{eq}>0),{ta}/{eq},""),"")', F_X)
        _formula(ws, f["roe3"], c, f'=IFERROR({col}{f["nm"]}*{col}{f["at"]}*{col}{f["em"]},"")', F_PCT)
        _formula(ws, f["tb"], c, f'=IFERROR(IF({pbt}>0,{ni}/{pbt},""),"")', F_X)
        _formula(ws, f["ib"], c, f'=IFERROR(IF({ebit}>0,{pbt}/{ebit},""),"")', F_X)
        _formula(ws, f["ebitm"], c, f'=IFERROR(IF({ti}>0,{ebit}/{ti},""),"")', F_PCT)
        _formula(ws, f["roe5"], c, f'=IFERROR({col}{f["tb"]}*{col}{f["ib"]}*{col}{f["ebitm"]}*{col}{f["at"]}*{col}{f["em"]},"")', F_PCT)
        _formula(ws, f["direct"], c, f'=IFERROR(IF({eq}>0,{ni}/{eq},""),"")', F_PCT)
        _formula(ws, f["resid"], c, f'=IFERROR({col}{f["direct"]}-{col}{f["roe3"]},"")', F_PCT)

    _header(ws, 30, ["C. MEROS STORED VALUES (shown even if your viewer does not calculate formulas)"] + list(years))
    stored = [("NM", "Net profit margin", F_PCT, 100.0), ("AT", "Asset turnover", F_X, 1.0), ("EM", "Equity multiplier", F_X, 1.0),
              ("ROE3", "ROE (3-step)", F_PCT, 100.0), ("TB", "Tax & minority burden", F_X, 1.0), ("IB", "Interest burden", F_X, 1.0),
              ("EBITM", "EBIT margin", F_PCT, 100.0), ("ROE5", "ROE (5-step)", F_PCT, 100.0),
              ("ROE_DIRECT", "ROE measured directly", F_PCT, 100.0), ("RESIDUAL", "Direct ROE − 3-step ROE", F_PCT, 100.0)]
    for i, (key, label, fmt, div) in enumerate(stored):
        r = 31 + i
        _put(ws, r, 1, label)
        for j in range(n):
            x = float(v[key][j])
            _put(ws, r, 2 + j, (x / div) if np.isfinite(x) else None, fmt=fmt, fill=STORED_FILL)

    r = 43
    chg = ctx.get("dupont_change") or {}
    for which, title in (("3", "D. WHAT MOVED ROE: 3-STEP ATTRIBUTION"), ("5", "E. WHAT MOVED ROE: 5-STEP ATTRIBUTION")):
        d = chg.get(which)
        if not d:
            _put(ws, r, 1, f"{title}: not available (needs positive ROE and positive factors in both years).", font=SUB_FONT)
            r += 2
            continue
        _header(ws, r, [f"{title} ({d['first']} → {d['last']})", "Contribution (percentage points of ROE)"])
        r += 1
        names_f = {"NM": "Net profit margin", "AT": "Asset turnover", "EM": "Equity multiplier", "TB": "Tax & minority burden",
                   "IB": "Interest burden", "EBITM": "EBIT margin"}
        for k in d["keys"]:
            _put(ws, r, 1, names_f.get(k, k))
            _put(ws, r, 2, d["contrib"][k], fmt=F_PP)
            r += 1
        _put(ws, r, 1, f"Total change in ROE ({d['roe_first']:.2f}% → {d['roe_last']:.2f}%)", font=BOLD)
        _put(ws, r, 2, d["total"], fmt=F_PP, font=BOLD)
        r += 2
    _put(ws, r, 1, "Method: exact log-mean (LMDI) attribution on year-end balances. No industry comparison is included (assumption E22).", font=SUB_FONT)
    ws.column_dimensions["A"].width = 74
    for j in range(n):
        ws.column_dimensions[L(2 + j)].width = 16


# --------------------------------------------------------------------------------------
# Main builder
# --------------------------------------------------------------------------------------
def build_export_workbook(ctx: dict) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    cd, res, fy = ctx["cd"], ctx["results"], ctx["active_fy"]
    years = res["years"]
    index: list[tuple[str, str]] = []

    def new(title: str, desc: str, tab: str | None = None):
        ws_ = _sheet(wb, title, desc, tab)
        index.append((ws_.title, desc))
        return ws_

    readme = _sheet(wb, "README", "Read me first: what this file is, where the data came from and how to read it", GOLD)

    # ---- Summary ------------------------------------------------------------------------
    ws = new("Summary", "Plain-English summary, headline KPIs and everything you should know before relying on the numbers", GOLD)
    _put(ws, 4, 1, "In plain English", font=BOLD)
    _put(ws, 5, 1, ctx.get("summary_text", ""), align=WRAP)
    ws.merge_cells(start_row=5, start_column=1, end_row=5, end_column=8)
    ws.row_dimensions[5].height = 140
    keys = ["GVA_Margin_Pct", "EBITDA_Margin_Pct", "PAT_Margin_Pct", "ROCE_Pct", "ROE_Pct", "Implied_Cost_of_Debt_Pct",
            "Interest_Coverage_Ratio", "Human_Capital_ROI", "Value_Added_Per_Emp_Lakhs"]
    kp = res["kpis"].loc[keys].copy()
    kp.insert(0, "Unit", [_kpi_unit(k) for k in keys])
    r = _table(ws, kp, 7, index_label="Headline KPI")
    _put(ws, r - 1, 1, "Interest coverage of 999 means there is no interest to pay. Blank = not available (for example employee cost not reported).", font=SUB_FONT)
    r += 1
    _put(ws, r, 1, "Important notes", font=BOLD)
    r += 1
    for lab, key in (("Employee cost", "emp"), ("Headcount", "headcount"), ("Tax and minority gap", "tax"), ("Other operating expenses", "opex")):
        txt = (cd.get("notes") or {}).get(key)
        if txt:
            _put(ws, r, 1, lab, font=BOLD, align=WRAP)
            _put(ws, r, 2, txt, align=WRAP)
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
            r += 1
    for w in cd.get("warnings") or []:
        _put(ws, r, 1, "Warning", font=BOLD)
        _put(ws, r, 2, w, align=WRAP)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        r += 1
    if cd.get("basis_note"):
        _put(ws, r, 1, "Basis", font=BOLD)
        _put(ws, r, 2, cd["basis_note"], align=WRAP)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        r += 1
    r += 1
    _put(ws, r, 1, "Data-health screen", font=BOLD)
    r += 1
    for h in ctx.get("health") or []:
        _put(ws, r, 1, h["level"].upper(), font=BOLD)
        _put(ws, r, 2, f"{h['title']}: {h['detail']}", align=WRAP)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        r += 1
    r += 1
    _put(ws, r, 1, DISCLAIMER_EXCEL, font=SUB_FONT, align=WRAP)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    ws.row_dimensions[r].height = 48
    ws.column_dimensions["A"].width = 34
    for j in range(2, 9):
        ws.column_dimensions[L(j)].width = 16

    # ---- Formula sheets -------------------------------------------------------------------
    ws_mi = new("Model inputs", "Numbers that feed the live EVA and DuPont formulas (₹ Cr). Column B is the opening balance where the source has one.", "7F8C8D")
    _model_inputs(ws_mi, ctx)
    ws_eva = new("EVA", f"Economic Value Added with live formulas. Change the yellow cost-of-equity cell to recalculate (starts at {ctx['ke_pct']:.1f}%).", GOLD)
    _eva_sheet(ws_eva, ctx)
    ws_dp = new("DuPont", "3-step and 5-step DuPont with live formulas, stored values and an exact attribution of what moved ROE.", GOLD)
    _dupont_sheet(ws_dp, ctx)

    # ---- Core value sheets ------------------------------------------------------------------
    ws = new("Schedule III grid", "The 12-line statement the engine used, after any edits you made (₹ Cr; headcount in persons)")
    g = res["inputs"].copy()
    g.insert(0, "Line item", [dict((s[0], s[1]) for s in SCHEMA).get(i, i) for i in g.index])
    _table(ws, g, 4, index_label="Line ID")
    _autowidth(ws)
    ws.freeze_panes = "C5"

    ws = new("P&L ladder", "Total income down to retained earnings, plus net value added (₹ Cr)")
    _table(ws, res["pnl"], 4, index_label="Line (₹ Cr)")
    _autowidth(ws)
    ws.freeze_panes = "B5"

    ws = new("Rs100 receipt", "Common-size: where every ₹100 of income goes")
    r = _table(ws, res["common_size"], 4, index_label="Paise-exact (₹ per ₹100)")
    _table(ws, res["common_size_exact"], r, index_label="Unrounded (₹ per ₹100)")
    _autowidth(ws)

    ws = new("VAS", "Value-added statement: the five stakeholder shares of gross value added")
    r = _table(ws, res["vas_abs"], 4, index_label="Amount (₹ Cr)")
    _table(ws, res["vas_pct"], r, index_label="% of GVA")
    _autowidth(ws)

    ws = new("KPIs", "All strategic, workforce, capital and credit ratios, plus growth rates over the window")
    kp2 = res["kpis"].copy()
    kp2.insert(0, "Unit", [_kpi_unit(k) for k in kp2.index])
    r = _table(ws, kp2, 4, index_label="Ratio")
    cg = pd.DataFrame({"% per year": pd.Series(res["cagr"], dtype="float64")})
    _table(ws, cg, r, index_label=f"Growth {years[0]} → {years[-1]}")
    _autowidth(ws)
    ws.freeze_panes = "C5"

    ws = new("Returns on capital", "Year-end vs average-balance returns and the full EVA build (values)")
    cap = ctx["capital"]
    labels, vals, fmts = [], [], {}
    for key, label, unit in CAP_LAYOUT:
        if key == "section":
            continue
        labels.append(label)
        vals.append(list(cap[key]))
        fmts[label] = UNIT_FMT.get({"cr": "cr", "pct": "pct", "x": "x"}.get(unit, "cr"), F_CR)
    _table(ws, pd.DataFrame(vals, index=labels, columns=years), 4, index_label="Measure", row_formats=fmts)
    _autowidth(ws)

    ws = new("Diagnostics", "Rule-based executive diagnostic cards")
    dd = pd.DataFrame([{"Title": d["title"], "Badge": d["badge_text"], "Severity": d["severity"], "Narrative": d["narrative"]}
                       for d in ctx.get("diagnostics") or []])
    if len(dd):
        _table(ws, dd, 4, index=False, text_wrap_cols=(4,))
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width, ws.column_dimensions["C"].width = 36, 30, 12
    ws.column_dimensions["D"].width = 120

    # ---- Transparency sheets ----------------------------------------------------------------
    ws = new("Health checks", "Automated data-health screens (rough tripwires, not an audit)")
    hh = pd.DataFrame([{"Level": h["level"].upper(), "Code": h["code"], "Check": h["title"], "Detail": h["detail"]} for h in ctx.get("health") or []])
    if len(hh):
        _table(ws, hh, 4, index=False, text_wrap_cols=(4,))
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width, ws.column_dimensions["C"].width = 10, 8, 40
    ws.column_dimensions["D"].width = 130

    b = ctx.get("bridge")
    if b is not None:
        ws = new("Source bridge", "The source's own reported anchors against the MEROS ladder, with variances")
        lab = ["Total revenue (source)", "Profit before tax (source)", "Profit attributable to shareholders (source)", "Tax reported (source)",
               "Total income (MEROS)", "Gross value added (MEROS)", "PBT (MEROS)", "Tax used (MEROS)", "Minority / associates gap (MEROS)",
               "Attributable profit (MEROS)", "PBT variance vs source", "Attributable profit variance vs source", "VAS closure residual",
               "₹100 receipt closure (sum − 100)"]
        data = [b["tr"], b["pb"], b["pa"], b["tp"], b["ti"], b["gva"], b["pbt"], b["tax"], b["adj"], b["pat_attr"], b["v_pbt"], b["v_pat"],
                b["resid"], b["rcpt"]]
        cols = [f"{y} · {l}" for y, l in zip(years, cd["period_labels"])]
        _table(ws, pd.DataFrame([list(x) for x in data], index=lab, columns=cols), 4, index_label="Line (₹ Cr)", fmt="#,##0.0000;[Red]-#,##0.0000")
        _autowidth(ws)

    xc = ctx.get("xcheck")
    if xc and xc.get("rows"):
        ws = new("Cross-check", "Screener against Yahoo for years present in both (revenue and attributable profit)")
        xdf = pd.DataFrame(xc["rows"])
        xdf = xdf.rename(columns={"year": "Year", "period_end": "Period end", "revenue_screener": "Revenue (Screener)", "revenue_yahoo": "Revenue (Yahoo)",
                                  "revenue_diff_pct": "Revenue diff %", "profit_screener": "Profit (Screener)", "profit_yahoo": "Profit (Yahoo)",
                                  "profit_diff_pct": "Profit diff %", "flag": "Flag"})
        _table(ws, xdf, 4, index=False)
        _put(ws, 6 + len(xdf), 1, xc.get("message", ""), font=SUB_FONT)
        _autowidth(ws)

    pr = ctx.get("provenance")
    if pr is not None and len(pr):
        ws = new("Provenance", "Where every number came from: Reported, Derived, Balancing, Not reported, Your edit or Re-balanced")
        _table(ws, pr, 4, index=False)
        _autowidth(ws)
        ws.column_dimensions["G"].width = 100
        ws.freeze_panes = "A5"

    ws = new("Assumptions", "Every assumption: what it is, why it is needed, its effect and whether it is active for this analysis")
    aa = pd.DataFrame([{"ID": a[0], "Scope": a[1], "Area": a[2], "Assumption": a[3], "Why it is needed": a[4],
                        "Effect and how to override": a[5], "Status": a[6]} for a in ctx.get("assumptions") or []])
    if len(aa):
        _table(ws, aa, 4, index=False, text_wrap_cols=(4, 5, 6))
    for col, w in zip("ABCDEFG", (7, 10, 28, 70, 70, 70, 16)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A5"

    sim = ctx.get("sim")
    if sim is not None:
        ws = new("Shock scenario", f"Margin-shock simulator on the latest year ({sim.get('base_year', fy)}): your settings and results")
        r = 4
        _put(ws, r, 1, "Your settings", font=BOLD)
        r = _kv(ws, [(k.replace("_", " "), v) for k, v in sim["assumptions"].items()], r + 1)
        _put(ws, r, 1, "Shock decomposition (₹ Cr)", font=BOLD)
        r = _kv(ws, [(k.replace("_", " "), v) for k, v in sim["shocks"].items()], r + 1)
        r = _table(ws, sim["comparison"], r, index_label="Metric")
        _table(ws, sim["receipt"], r, index_label="₹100 receipt")
        ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 46, 24
        for col in "CDE":
            ws.column_dimensions[col].width = 18

    cmp_ = ctx.get("comparison")
    if cmp_ is not None:
        ws = new("Comparison", "Side-by-side comparison of the latest year of each company")
        frame, units = cmp_["frame"], cmp_["units"]
        _header(ws, 4, ["Measure"] + [str(c) for c in frame.columns])
        r = 5
        for lab in frame.index:
            _put(ws, r, 1, lab, font=BOLD)
            unit = units.get(lab, "cr")
            for j, name in enumerate(frame.columns, start=2):
                val = frame.loc[lab, name]
                if unit == "icr" and isinstance(val, (int, float, np.floating)) and np.isfinite(val) and val >= 999.0:
                    _put(ws, r, j, "no interest to pay")
                elif isinstance(val, (int, float, np.floating)) and not isinstance(val, bool):
                    _put(ws, r, j, val, fmt=UNIT_FMT.get(unit, F_CR))
                else:
                    _put(ws, r, j, val)
            r += 1
        r += 1
        for note in cmp_.get("notes") or []:
            _put(ws, r, 1, note, font=SUB_FONT, align=WRAP)
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=max(3, len(frame.columns) + 1))
            ws.row_dimensions[r].height = 32
            r += 1
        ws.column_dimensions["A"].width = 52
        for j in range(2, len(frame.columns) + 2):
            ws.column_dimensions[L(j)].width = 26

    for title, frame in (ctx.get("raw") or {}).items():
        ws = new(f"Raw {title}", f"Untouched source table in ₹ Cr. 'Used by MEROS' marks the rows the engine read.")
        _table(ws, frame, 4, index_label="Source line item")
        _autowidth(ws)
        ws.freeze_panes = "B5"

    # ---- README (filled last so it can list every sheet) -------------------------------------
    fy_map = pd.DataFrame({"Fiscal-year label": years, "Period ends": cd["period_ends"], "Shown as": cd["period_labels"]})
    win = cd.get("window") or {}
    rows = [
        (APP_NAME, "Corporate Value-Added & Stakeholder Economics tool"),
        ("Architected & engineered by", CREATOR),
        ("Generated", ctx.get("generated_at", "")),
        ("Company", cd.get("company_name") or ctx.get("source_label", "")),
        ("Data source", ctx.get("source_kind", "")),
        ("Basis", cd.get("basis_note", "")),
        ("History window", f"{win.get('label', '')} ({len(years)} years used, {win.get('available', len(years))} available)"),
        ("Active fiscal year", fy),
        ("Units", "₹ Crores unless stated; headcount in persons; ratios in % or x"),
        ("Data sources", DATA_SOURCES_NOTE),
        ("How to read", "Start with Summary, then Health checks and Assumptions. Provenance shows the source of every cell. "
                        "Blank or 'Not reported' means the source has no such figure and MEROS did not guess."),
        ("Live formulas", "The EVA and DuPont sheets recalculate when opened in Excel (change the yellow cost-of-equity cell on EVA). "
                          "Stored values are included in case your viewer shows formulas as blank."),
        ("Disclaimer", DISCLAIMER_FULL),
    ]
    r = _kv(readme, rows, 4)
    _put(readme, r, 1, "Fiscal-year labels", font=BOLD)
    r = _table(readme, fy_map, r + 1, index=False)
    _put(readme, r, 1, "Sheet index", font=BOLD)
    r += 1
    for nm, desc in index:
        _put(readme, r, 1, nm, font=BOLD)
        _put(readme, r, 2, desc, align=WRAP)
        r += 1
    readme.column_dimensions["A"].width = 30
    readme.column_dimensions["B"].width = 120
    readme.column_dimensions["C"].width = 22

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()