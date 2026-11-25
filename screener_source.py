"""MEROS Screener source: read a Screener.in Excel export (the 'Data Sheet' tab) and convert it into the standard MEROS
'company data' package, with a real cost check (profit-before-tax is rebuilt from the cost lines, not plugged).
No estimates: anything the file does not report is flagged 'Not reported'. Also: Yahoo cross-check and the raw-table viewer."""
from __future__ import annotations

import datetime as _dt
import io
import re
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from corporate_engine import build_grid, make_year_labels
from meros_assumptions import (SCREENER_KNOWN_VERSIONS, SCREENER_STEPS_NOTE, google_search_url, screener_company_url,
                               screener_steps)

DATA_SHEET_NAME = "Data Sheet"
COST_TOLERANCE_CR = 0.5
GAP_TOLERANCE_CR = 0.05
MIN_YEARS = 3

SECTION_KEYS = {"meta": "meta", "profitloss": "pl", "quarters": "q", "balancesheet": "bs",
                "cashflow": "cf", "price": "price", "derived": "derived"}
SECTION_TITLES = {"pl": "Profit & Loss", "bs": "Balance Sheet", "cf": "Cash Flow"}
USED_LABELS = {
    "pl": {"sales", "rawmaterialcost", "changeininventory", "powerandfuel", "othermfrexp", "employeecost", "sellingandadmin",
           "otherexpenses", "expenses", "otherincome", "depreciation", "interest", "profitbeforetax", "tax", "netprofit",
           "dividendamount"},
    "bs": {"equitysharecapital", "reserves", "borrowings", "otherliabilities", "total"},
    "cf": set(),
}
NAME_STOPWORDS = {"ltd", "limited", "the", "and", "co", "company", "pvt", "private", "corp", "corporation", "inc"}


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------
def norm_key(name: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _read_bytes(file: object) -> bytes:
    if isinstance(file, (bytes, bytearray)):
        return bytes(file)
    if isinstance(file, (str, Path)):
        return Path(file).read_bytes()
    if hasattr(file, "getvalue"):
        return file.getvalue()
    if hasattr(file, "read"):
        data = file.read()
        try:
            file.seek(0)
        except Exception:  # noqa: BLE001
            pass
        return data
    raise ValueError("Unsupported file object: expected an uploaded .xlsx file.")


def _to_ts(v: object) -> pd.Timestamp:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return pd.NaT
    if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
        f = float(v)
        if 20000.0 < f < 80000.0:
            return pd.Timestamp("1899-12-30") + pd.to_timedelta(f, unit="D")
        return pd.NaT
    try:
        ts = pd.Timestamp(v)
    except Exception:  # noqa: BLE001
        return pd.NaT
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts


def _version_text(val: object) -> str:
    try:
        return f"{float(val):g}"
    except (TypeError, ValueError):
        return str(val).strip()


def _find_data_sheet(wb) -> object:
    for ws in wb.worksheets:
        if str(ws.title).strip().lower() == DATA_SHEET_NAME.lower():
            return ws
    for ws in wb.worksheets:
        for row in ws.iter_rows(min_row=1, max_row=200, max_col=1, values_only=True):
            if row and row[0] is not None and norm_key(row[0]) == "profitloss":
                return ws
    raise ValueError("This does not look like a Screener export: no 'Data Sheet' tab with a PROFIT & LOSS block was found. "
                     "Download the Excel file with Screener's 'Export to Excel' button and upload that file unchanged.")


# --------------------------------------------------------------------------------------
# Step 1: parse the workbook into labelled blocks
# --------------------------------------------------------------------------------------
def parse_screener_workbook(file: object) -> dict:
    """Read the 'Data Sheet' tab. Returns {'company_name', 'version', 'blocks': {'pl'|'bs'|'cf'|...: {'dates': [...], 'rows': [(label, values)]}}}."""
    data = _read_bytes(file)
    try:
        wb = load_workbook(io.BytesIO(data), data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Could not open the file as an Excel .xlsx workbook ({exc}). Upload the file exactly as Screener downloaded it.") from exc
    ws = _find_data_sheet(wb)
    rows = [list(r) for r in ws.iter_rows(values_only=True)]

    meta: dict = {"company_name": "", "version": ""}
    for r in rows[:15]:
        lab = norm_key(r[0]) if r and r[0] is not None else ""
        val = r[1] if len(r) > 1 else None
        if lab == "companyname" and val:
            meta["company_name"] = str(val).strip()
        elif lab == "currentversion" and val is not None:
            meta["version"] = _version_text(val)
        elif lab == "latestversion" and val is not None and not meta["version"]:
            meta["version"] = _version_text(val)

    starts: list[tuple[str, int]] = []
    for i, r in enumerate(rows):
        lab = r[0] if r else None
        if lab is None:
            continue
        key = SECTION_KEYS.get(norm_key(lab))
        if key:
            starts.append((key, i))

    blocks: dict = {}
    for j, (key, s) in enumerate(starts):
        end = starts[j + 1][1] if j + 1 < len(starts) else len(rows)
        if key in blocks or key not in ("pl", "bs", "cf"):
            continue
        dates: list = []
        series: list[tuple[str, list]] = []
        seen_dates = False
        for r in rows[s + 1:end]:
            if not r or r[0] is None or str(r[0]).strip() == "":
                continue
            label = str(r[0]).strip()
            if not seen_dates:
                if norm_key(label) == "reportdate":
                    dates = [_to_ts(v) for v in r[1:]]
                    seen_dates = True
                continue
            series.append((label, list(r[1:])))
        if seen_dates:
            blocks[key] = {"dates": dates, "rows": series}

    if "pl" not in blocks or not blocks["pl"]["rows"]:
        raise ValueError("The 'Data Sheet' tab has no readable PROFIT & LOSS block (no 'Report Date' row found).")
    return {"company_name": meta["company_name"], "version": meta["version"], "blocks": blocks}


def _block_map(block: dict) -> dict[str, list[np.ndarray]]:
    dates = block["dates"]
    n = len(dates)
    out: dict[str, list[np.ndarray]] = {}
    for label, vals in block["rows"]:
        v = list(vals[:n]) + [None] * max(0, n - len(vals))
        arr = pd.to_numeric(pd.Series(v, dtype="object"), errors="coerce").to_numpy(dtype="float64")
        out.setdefault(norm_key(label), []).append(arr)
    return out


def _get(mp: dict, key: str, occurrence: int = 0) -> np.ndarray | None:
    lst = mp.get(key)
    if not lst:
        return None
    return lst[-1] if occurrence < 0 else lst[min(occurrence, len(lst) - 1)]


def _align(arr: np.ndarray, block_dates: list, master: list) -> np.ndarray:
    pos: dict = {}
    for i, d in enumerate(block_dates):
        if not pd.isna(d):
            pos.setdefault(pd.Timestamp(d).normalize(), i)
    out = np.full(len(master), np.nan)
    for j, m in enumerate(master):
        i = pos.get(pd.Timestamp(m).normalize())
        if i is not None and i < len(arr):
            out[j] = arr[i]
    return out


# --------------------------------------------------------------------------------------
# Step 2: parsed workbook -> MEROS company data
# --------------------------------------------------------------------------------------
def build_company_data(parsed: dict, version: str = "unknown", symbol: str = "", hints: dict | None = None) -> dict:
    """hints (all optional, usually from Yahoo): company_name, sector, industry, is_financial, headcount."""
    hints = dict(hints or {})
    blocks = parsed["blocks"]
    plmap = _block_map(blocks["pl"])
    pl_dates = blocks["pl"]["dates"]

    for need, label in (("sales", "Sales"), ("profitbeforetax", "Profit before tax")):
        if need not in plmap:
            found = ", ".join(sorted({lab for lab, _ in blocks["pl"]["rows"]})[:12])
            raise ValueError(f"The Screener file's Profit & Loss block has no '{label}' row (rows found: {found}).")
    if "tax" not in plmap and "netprofit" not in plmap:
        raise ValueError("The Screener file has neither a 'Tax' nor a 'Net profit' row, so profit after tax cannot be built.")

    order = [i for i, _ in sorted(((i, d) for i, d in enumerate(pl_dates) if not pd.isna(d)), key=lambda t: t[1])]
    master = [pd.Timestamp(pl_dates[i]).normalize() for i in order]
    if not master:
        raise ValueError("The Profit & Loss block has no readable report dates.")

    def full(key: str, occurrence: int = 0) -> np.ndarray:
        arr = _get(plmap, key, occurrence)
        if arr is None:
            return np.full(len(order), np.nan)
        return np.asarray(arr, dtype="float64")[order]

    sales_a, pbt_a, tax_a, npf_a = full("sales"), full("profitbeforetax"), full("tax"), full("netprofit")
    valid = np.isfinite(sales_a) & np.isfinite(pbt_a) & (np.isfinite(tax_a) | np.isfinite(npf_a))
    idxs = np.flatnonzero(valid)
    if idxs.size == 0:
        raise ValueError("The Screener file has no year with Sales, Profit before tax and Tax / Net profit all filled in.")
    last = int(idxs[-1])
    first = last
    while first - 1 >= 0 and valid[first - 1]:
        first -= 1
    sel = np.arange(first, last + 1)
    n = int(sel.size)
    if n < MIN_YEARS:
        raise ValueError(f"The Screener file has only {n} consecutive usable annual year(s); MEROS needs at least {MIN_YEARS}.")

    dates = [master[i] for i in sel]
    years = make_year_labels(dates)

    def col(key: str, occurrence: int = 0) -> np.ndarray:
        return full(key, occurrence)[sel]

    z = lambda a: np.nan_to_num(np.asarray(a, dtype="float64"), nan=0.0)  # noqa: E731

    sales, pbt = sales_a[sel], pbt_a[sel]
    oi, dep, intr = col("otherincome"), col("depreciation"), col("interest")
    rm, ci = col("rawmaterialcost"), col("changeininventory")
    ec = col("employeecost")
    layout = "standard" if any(k in plmap for k in ("rawmaterialcost", "powerandfuel", "othermfrexp", "sellingandadmin",
                                                      "otherexpenses", "employeecost")) else "aggregate"
    if layout == "aggregate" and "expenses" not in plmap:
        raise ValueError("The Screener file has no cost lines (no raw material, employee, other expenses or an aggregate Expenses row).")

    # ---- Costs and the real cost check -------------------------------------------------
    if layout == "standard":
        base_opex = z(col("powerandfuel")) + z(col("othermfrexp")) + z(col("sellingandadmin")) + z(col("otherexpenses"))
        emp_rep = np.isfinite(ec)
        emp_val = np.where(emp_rep, ec, 0.0)
        gap_sum = {}
        for sgn in (-1.0, 1.0):
            cogs_try = z(rm) + sgn * z(ci)
            rebuilt_try = z(sales) + z(oi) - (cogs_try + base_opex + emp_val) - z(dep) - z(intr)
            gap_sum[sgn] = float(np.sum(np.abs(rebuilt_try - pbt)))
        sgn = min(gap_sum, key=gap_sum.get)
        cogs = z(rm) + sgn * z(ci)
        rebuilt = z(sales) + z(oi) - (cogs + base_opex + emp_val) - z(dep) - z(intr)
    else:
        sgn = -1.0
        base_opex = z(col("expenses"))
        emp_rep = np.zeros(n, dtype=bool)
        emp_val = np.zeros(n)
        cogs = np.zeros(n)
        rebuilt = z(sales) + z(oi) - base_opex - z(dep) - z(intr)

    adj = rebuilt - pbt
    opex_pre = base_opex + adj
    neg = opex_pre < 0.0
    lift = np.where(neg, -opex_pre, 0.0)
    rev_oth = np.round(z(oi) + lift, 4)
    opex = np.round(np.where(neg, 0.0, opex_pre), 4)
    cogs = np.round(cogs, 4)
    emp = np.round(emp_val, 4)
    eng_pbt = z(sales) + rev_oth - cogs - opex - emp - z(dep) - z(intr)
    if float(np.max(np.abs(eng_pbt - pbt))) > 1e-3:
        raise ValueError("Internal check failed: profit-before-tax could not be reproduced from the Screener cost lines.")
    flagged = np.abs(adj) > COST_TOLERANCE_CR

    # ---- Tax and attributable profit ----------------------------------------------------
    tax_arr, npf_arr = tax_a[sel], npf_a[sel]
    tax_rep = np.isfinite(tax_arr)
    tax = np.round(np.where(tax_rep, tax_arr, pbt - npf_arr), 4)
    npf = np.round(np.where(np.isfinite(npf_arr), npf_arr, pbt - tax_arr), 4)
    attr_adj = np.round((pbt - tax) - npf, 2)
    gap_flag = np.abs(attr_adj) > GAP_TOLERANCE_CR

    # ---- Dividends, balance sheet --------------------------------------------------------
    div_arr = col("dividendamount")
    div_rep = np.isfinite(div_arr)
    div = z(div_arr)

    bs_block = blocks.get("bs")
    bsmap = _block_map(bs_block) if bs_block else {}

    def bcol(key: str, occurrence: int = 0) -> np.ndarray:
        arr = _get(bsmap, key, occurrence)
        if arr is None or not bs_block:
            return np.full(n, np.nan)
        return _align(arr, bs_block["dates"], master)[sel]

    sc, res, bor, ol = bcol("equitysharecapital"), bcol("reserves"), bcol("borrowings"), bcol("otherliabilities")
    tl, ta = bcol("total", 0), bcol("total", -1)
    equity_rep, debt_rep = np.isfinite(res), np.isfinite(bor)
    equity, debt = np.round(z(sc) + z(res), 4), np.round(z(bor), 4)
    bs_check = np.isfinite(sc) & np.isfinite(res) & np.isfinite(bor) & np.isfinite(ol) & np.isfinite(tl)
    bs_bad = bs_check & (np.abs(sc + res + bor + ol - tl) > 0.5)

    # ---- Headcount (Yahoo hint, latest year only) ------------------------------------------
    hc = np.zeros(n)
    hc_applied = False
    try:
        h = int(float(hints.get("headcount")))
    except (TypeError, ValueError):
        h = 0
    if h > 0:
        hc[-1] = float(h)
        hc_applied = True

    emp_status = "reported" if emp_rep.all() else ("partial" if emp_rep.any() else "not_reported")

    def yrs(mask: np.ndarray) -> str:
        return ", ".join(y for y, m in zip(years, mask) if bool(m))

    # ---- Provenance ------------------------------------------------------------------------
    def pv(status: str, detail: str) -> list:
        return [status, detail]

    oi_rep = np.isfinite(oi)
    inv_txt = "Raw Material Cost − Change in Inventory" if sgn < 0 else "Raw Material Cost + Change in Inventory"
    prov = {
        "REV_OPS": [pv("Reported", "Screener 'Sales'") for _ in range(n)],
        "REV_OTH": [pv("Balancing", f"Screener 'Other Income' + ₹{lift[i]:,.2f} Cr lifted so Other Operating Expenses stay at or above 0")
                    if lift[i] > 0 else (pv("Reported", "Screener 'Other Income'") if oi_rep[i] else pv("Not reported", "No Other Income value; shown as 0"))
                    for i in range(n)],
        "COGS_MAT": [pv("Derived", inv_txt) if (layout == "standard" and (np.isfinite(rm[i]) or np.isfinite(ci[i])))
                     else pv("Not reported", "No raw-material rows in the file; shown as 0") for i in range(n)],
        "OPEX_EXT": [],
        "EMP_COST": [pv("Reported", "Screener 'Employee Cost'") if emp_rep[i]
                     else pv("Not reported", "No Employee Cost value in the file; shown as 0, not estimated") for i in range(n)],
        "FIN_COST": [pv("Reported", "Screener 'Interest'") if np.isfinite(intr[i]) else pv("Not reported", "No Interest value; shown as 0")
                     for i in range(n)],
        "DEP_AMORT": [pv("Reported", "Screener 'Depreciation'") if np.isfinite(dep[i]) else pv("Not reported", "No Depreciation value; shown as 0")
                      for i in range(n)],
        "TAX_EXP": [pv("Reported", "Screener 'Tax'") if tax_rep[i] else pv("Derived", "Profit before tax − Net profit (no Tax value)")
                    for i in range(n)],
        "DIV_PAID": [pv("Reported", "Screener 'Dividend Amount'") if div_rep[i] else pv("Not reported", "No Dividend Amount value; shown as 0")
                     for i in range(n)],
        "TOTAL_DEBT": [pv("Reported", "Screener 'Borrowings'") if debt_rep[i] else pv("Not reported", "No Borrowings value; shown as 0")
                       for i in range(n)],
        "TOTAL_EQUITY": [pv("Reported", "Screener 'Equity Share Capital' + 'Reserves'") if equity_rep[i]
                         else pv("Not reported", "No Reserves value; shown as 0") for i in range(n)],
        "HEADCOUNT": [pv("Reported", f"Yahoo 'fullTimeEmployees' = {h:,}, a current snapshot (Screener has no headcount)") if (hc_applied and i == n - 1)
                      else pv("Not reported", "Screener has no headcount") for i in range(n)],
    }
    for i in range(n):
        if layout == "aggregate":
            d = "Screener 'Expenses' (aggregate line)"
        else:
            d = "Power and Fuel + Other Mfr. Exp + Selling and admin + Other Expenses"
        if neg[i]:
            prov["OPEX_EXT"].append(pv("Balancing", "Set to 0: the cost lines exceeded what profit-before-tax allows, so Other Income was lifted instead"))
        elif flagged[i]:
            prov["OPEX_EXT"].append(pv("Balancing", f"{d}, plus ₹{adj[i]:,.2f} Cr because the cost lines do not rebuild Screener's profit-before-tax"))
        elif abs(adj[i]) > 1e-9:
            prov["OPEX_EXT"].append(pv("Derived", f"{d} (includes a rounding difference of ₹{adj[i]:,.4f} Cr so profit-before-tax matches exactly)"))
        else:
            prov["OPEX_EXT"].append(pv("Derived", d))

    # ---- Notes, warnings, status -------------------------------------------------------------
    ver_key = str(version or "unknown").strip().lower()
    ver_text = {"consolidated": "Consolidated", "standalone": "Standalone"}.get(ver_key, "")
    basis_note = (f"You told MEROS this file is the {ver_text} version. The workbook itself does not say, so please make sure that is right."
                  if ver_text else "You did not say whether this file is the Consolidated or the Standalone version, and the workbook does not say.")

    if emp_status == "reported":
        emp_note = f"Employee cost is Screener's 'Employee Cost' line for all {n} years."
    else:
        emp_note = (f"⚠ EMPLOYEE COST NOT REPORTED in this Screener file for {yrs(~emp_rep)}. MEROS does not estimate it: those years show 0 on the "
                    "employee line and the cost stays inside Other Operating Expenses, so GVA is understated and workforce metrics are not meaningful. "
                    "You can type the figure into the override grid.")
    hc_note = (f"Headcount {h:,} comes from Yahoo (Screener has none) and is applied to {years[-1]} only; per-employee metrics exist for that year only "
               "unless you type earlier headcounts." if hc_applied else
               "Screener has no headcount and none was available from Yahoo, so per-employee metrics are not available unless you type the headcount.")
    if gap_flag.any():
        tax_note = ("Reported tax is kept as the Government share. (Profit before tax − Tax) exceeds reported net profit attributable to shareholders by "
                    + ", ".join(f"₹{attr_adj[i]:,.2f} Cr ({years[i]})" for i in range(n) if gap_flag[i])
                    + " (minority interest, associates and other items). ROE and DuPont use attributable profit.")
    else:
        tax_note = "Reported tax and reported net profit reconcile with profit before tax in all years."
    if layout == "aggregate":
        opex_note = ("This file has no cost breakdown, so Screener's aggregate 'Expenses' line is used as Other Operating Expenses and the cost of materials "
                     "and employee cost are not reported (assumption S13). Best effort, especially for banks.")
    elif flagged.any():
        opex_note = (f"⚠ Cost check: the mapped cost lines do NOT rebuild Screener's profit-before-tax in {yrs(flagged)} (differences "
                     + ", ".join(f"₹{adj[i]:,.2f} Cr" for i in range(n) if flagged[i])
                     + f"). The difference was added to Other Operating Expenses and flagged (assumption S06). Tolerance ₹{COST_TOLERANCE_CR} Cr.")
    else:
        opex_note = (f"Cost check passed: the mapped cost lines rebuild Screener's profit-before-tax within ₹{COST_TOLERANCE_CR} Cr in all {n} years "
                     f"(inventory change taken as '{inv_txt}'; assumptions S03, S06).")

    warnings: list[str] = []
    file_ver = str(parsed.get("version") or "").strip()
    if file_ver and file_ver not in SCREENER_KNOWN_VERSIONS:
        warnings.append(f"This Screener file is layout version {file_ver}; MEROS knows {', '.join(SCREENER_KNOWN_VERSIONS)}. Check the results carefully (assumption S02).")
    if not file_ver:
        warnings.append("The file does not state a layout version, so MEROS cannot confirm its layout (assumption S02).")
    if bs_bad.any():
        warnings.append(f"The balance-sheet lines do not add up to Screener's total in {yrs(bs_bad)}; check the file.")
    if layout == "aggregate":
        warnings.append("This file has no cost breakdown (common for banks). Value-added, ROCE, DuPont and EVA figures are indicative only (assumption S13).")
    total_valid = int(valid.sum())
    if total_valid > n:
        warnings.append(f"The file has {total_valid} usable years but only the latest unbroken run of {n} years is used (older years are separated by a gap).")

    is_fin = bool(hints.get("is_financial")) if "is_financial" in hints else (layout == "aggregate")
    status: dict[str, str] = {k: "always" for k in ("S01", "S02", "S08", "S09", "S10", "S11", "S15")}
    status["S03"] = "active" if (layout == "standard" and bool(np.isfinite(rm).any() or np.isfinite(ci).any())) else "inactive"
    status["S04"] = "always" if layout == "standard" else "inactive"
    status["S05"] = "active" if emp_status != "reported" else "inactive"
    status["S06"] = "active" if bool(flagged.any()) else "inactive"
    status["S07"] = "active" if bool(gap_flag.any()) else "inactive"
    status["S12"] = "active" if hc_applied else "inactive"
    status["S13"] = "active" if layout == "aggregate" else "inactive"
    status["S14"] = "inactive"

    values = {
        "REV_OPS": np.round(z(sales), 4), "REV_OTH": rev_oth, "COGS_MAT": cogs, "OPEX_EXT": opex, "EMP_COST": emp,
        "FIN_COST": np.round(z(intr), 4), "DEP_AMORT": np.round(z(dep), 4), "TAX_EXP": tax, "DIV_PAID": np.round(div, 4),
        "TOTAL_DEBT": debt, "TOTAL_EQUITY": equity, "HEADCOUNT": hc,
    }
    grid = build_grid(values, years)
    lst = lambda a: [None if not np.isfinite(x) else float(x) for x in np.asarray(a, dtype="float64")]  # noqa: E731

    company = str(hints.get("company_name") or parsed.get("company_name") or symbol or "Company").strip()
    return {
        "source": "screener",
        "symbol": str(symbol or "").strip().upper(),
        "company_name": company,
        "file_company_name": str(parsed.get("company_name") or ""),
        "sector": str(hints.get("sector") or ""),
        "industry": str(hints.get("industry") or ""),
        "currency": "INR",
        "is_financial": is_fin,
        "version": ver_key,
        "file_version": file_ver,
        "basis_note": basis_note,
        "layout": layout,
        "years": years,
        "period_ends": [d.strftime("%Y-%m-%d") for d in dates],
        "period_labels": [d.strftime("%b %Y") for d in dates],
        "n_years_in_file": total_valid,
        "grid": grid,
        "attr_adj": [float(x) for x in attr_adj],
        "anchors": {"TOTAL_REVENUE": lst(sales), "PBT": lst(pbt), "PAT_ATTR": lst(npf),
                    "TAX_REPORTED": lst(np.where(tax_rep, tax_arr, np.nan))},
        "extras": {"TOTAL_ASSETS": lst(ta)},
        "opening": {"TOTAL_DEBT": None, "TOTAL_EQUITY": None, "TOTAL_ASSETS": None, "label": None},
        "provenance": prov,
        "status": status,
        "emp_status": emp_status,
        "hc_status": "snapshot_latest" if hc_applied else "not_reported",
        "notes": {"emp": emp_note, "headcount": hc_note, "tax": tax_note, "opex": opex_note},
        "warnings": warnings,
        "payroll_candidates": [],
        "cost_check": {"inventory_sign": int(sgn), "gap_per_year": [float(x) for x in adj], "flagged_years": [y for y, f in zip(years, flagged) if bool(f)],
                       "tolerance": COST_TOLERANCE_CR, "passed": not bool(flagged.any())},
        "fetched_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }


def load_screener(file: object, version: str = "unknown", symbol: str = "", hints: dict | None = None) -> tuple[dict, dict]:
    """Parse an uploaded Screener file and build the company data. Returns (company data, parsed workbook for the raw viewer)."""
    parsed = parse_screener_workbook(file)
    return build_company_data(parsed, version, symbol, hints), parsed


# --------------------------------------------------------------------------------------
# Cross-check against Yahoo, name check, raw viewer, download guide
# --------------------------------------------------------------------------------------
def cross_check(screener_cd: dict, yahoo_cd: dict | None, tol_pct: float = 1.0) -> dict:
    """Compare revenue and attributable profit for years present in both sources. Also sets assumption S14 on the Screener data."""
    if not yahoo_cd:
        screener_cd["status"]["S14"] = "inactive"
        return {"status": "skipped", "rows": [], "message": "Yahoo data was not available, so the cross-check was skipped (assumption S14)."}
    s_dates = pd.to_datetime(pd.Series(screener_cd["period_ends"]))
    rows: list[dict] = []
    for j, ds in enumerate(yahoo_cd["period_ends"]):
        d = pd.Timestamp(ds)
        gaps = np.abs((s_dates - d).dt.days.to_numpy())
        if gaps.size == 0:
            continue
        i = int(np.argmin(gaps))
        if gaps[i] > 45:
            continue

        def pct(a: float | None, b: float | None) -> float | None:
            if a is None or b is None or not np.isfinite(a) or not np.isfinite(b) or b == 0:
                return None
            return (a - b) / abs(b) * 100.0

        rs, ry = screener_cd["anchors"]["TOTAL_REVENUE"][i], yahoo_cd["anchors"]["TOTAL_REVENUE"][j]
        ps, py = screener_cd["anchors"]["PAT_ATTR"][i], yahoo_cd["anchors"]["PAT_ATTR"][j]
        rp, pp = pct(rs, ry), pct(ps, py)
        rows.append({"year": screener_cd["years"][i], "period_end": screener_cd["period_ends"][i], "revenue_screener": rs, "revenue_yahoo": ry,
                     "revenue_diff_pct": rp, "profit_screener": ps, "profit_yahoo": py, "profit_diff_pct": pp,
                     "flag": bool((rp is not None and abs(rp) > tol_pct) or (pp is not None and abs(pp) > tol_pct))})
    if not rows:
        screener_cd["status"]["S14"] = "inactive"
        return {"status": "skipped", "rows": [], "message": "Yahoo and the Screener file share no matching year-end, so the cross-check was skipped."}
    bad = [r for r in rows if r["flag"]]
    if bad:
        screener_cd["status"]["S14"] = "active"
        detail = "; ".join(f"{r['year']}: revenue {r['revenue_diff_pct']:+.1f}%, profit {r['profit_diff_pct']:+.1f}%"
                           for r in bad if r["revenue_diff_pct"] is not None and r["profit_diff_pct"] is not None) or "see the table"
        return {"status": "flag", "rows": rows, "message": (
            f"Screener and Yahoo differ by more than {tol_pct:g}% in {len(bad)} of {len(rows)} overlapping year(s) ({detail}). The usual cause is a "
            "Consolidated file compared with Standalone figures (or the reverse), or a restatement. Try the other Consolidated/Standalone download. "
            "It can also be that Yahoo defines revenue differently. This is a prompt to look closer, not proof that either source is wrong.")}
    screener_cd["status"]["S14"] = "always"
    return {"status": "ok", "rows": rows, "message": f"Screener agrees with Yahoo within {tol_pct:g}% on revenue and attributable profit in all {len(rows)} overlapping year(s)."}


def company_match_note(file_company_name: str, expected_name: str) -> str:
    """Warning when the uploaded file's company looks unrelated to the one the user selected. Empty string when fine or unknown."""
    def tokens(s: str) -> set:
        return {t for t in re.findall(r"[a-z0-9]+", str(s).lower()) if t not in NAME_STOPWORDS}
    a, b = tokens(file_company_name), tokens(expected_name)
    if not a or not b or (a & b):
        return ""
    return (f"The file is for '{file_company_name}' but you selected '{expected_name}'. Check that you downloaded the right company "
            "(the analysis will still run on whatever the file contains).")


def screener_tables(parsed: dict) -> dict[str, pd.DataFrame]:
    """The file's untouched Profit & Loss, Balance Sheet and Cash Flow blocks (₹ Cr) with a tick against every row MEROS read."""
    out: dict[str, pd.DataFrame] = {}
    for key, title in SECTION_TITLES.items():
        blk = parsed["blocks"].get(key)
        if not blk or not blk["rows"]:
            continue
        dates = blk["dates"]
        cols: list[str] = []
        for j, d in enumerate(dates):
            name = f"col{j + 1}" if pd.isna(d) else pd.Timestamp(d).strftime("%b %Y")
            cols.append(name if name not in cols else f"{name} ({j + 1})")
        counts: dict[str, int] = {}
        idx, data, used = [], [], []
        for label, vals in blk["rows"]:
            k = norm_key(label)
            counts[k] = counts.get(k, 0) + 1
            idx.append(label if counts[k] == 1 else f"{label} ({counts[k]})")
            row = list(vals[:len(dates)]) + [None] * max(0, len(dates) - len(vals))
            data.append(pd.to_numeric(pd.Series(row, dtype="object"), errors="coerce").to_numpy(dtype="float64"))
            used.append("✔" if k in USED_LABELS[key] else "")
        df = pd.DataFrame(np.vstack(data), index=idx, columns=cols)
        df.insert(0, "Used by MEROS", used)
        out[title] = df
    return out


def download_guide(symbol: str, version: str = "consolidated") -> dict:
    """Everything the UI needs to show the step-by-step Screener download instructions."""
    sym = str(symbol or "").strip().upper()
    return {"url": screener_company_url(sym, version), "google_url": google_search_url(sym),
            "steps": screener_steps(sym, version), "note": SCREENER_STEPS_NOTE}