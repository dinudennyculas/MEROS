"""MEROS Yahoo Finance source: fetch the annual statements (network step) and convert them into the standard MEROS
'company data' package (pure step). No estimates: anything Yahoo does not report is flagged 'Not reported'."""
from __future__ import annotations

import datetime as _dt
import re

import numpy as np
import pandas as pd

from corporate_engine import SCHEMA, build_grid, make_year_labels
from tickers import clean_symbol, to_yahoo_symbol

CRORE = 1e7
MIN_YEARS = 3
MIN_USABLE_VALUES = 3
MAX_YEARS = 6
INFO_KEYS = ("longName", "shortName", "sector", "industry", "financialCurrency", "currency", "fullTimeEmployees")

REV_ALIASES = ["Operating Revenue", "Total Revenue", "Interest Income"]
PAYROLL_ALIASES = ["Salaries And Wages", "Wages And Salaries", "Employee Benefits", "Employee Benefit Expense",
                   "Employee Benefits Expense", "Staff Costs", "Personnel Expenses"]
PAYROLL_WORDS = ("salar", "wage", "employee", "staff", "personnel", "compensation", "payroll", "benefit")


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------
def norm_key(name: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _clean_periods(df: object, min_values: int = MIN_USABLE_VALUES) -> pd.DataFrame:
    """Datetime-index the columns, coerce to numeric, drop sparse periods, sort oldest -> newest."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out.columns = pd.to_datetime(out.columns, errors="coerce")
    out = out.loc[:, ~pd.isna(out.columns)]
    out = out.apply(pd.to_numeric, errors="coerce")
    out = out.loc[:, out.notna().sum(axis=0) >= min_values]
    out = out.loc[:, ~out.columns.duplicated()]
    return out.sort_index(axis=1)


def _align_periods(df: pd.DataFrame, dates: list, tol_days: int = 45) -> pd.DataFrame:
    """Re-index a statement onto the income-statement period ends (nearest date within tolerance)."""
    if df is None or df.shape[1] == 0:
        return pd.DataFrame(index=[], columns=dates, dtype="float64")
    cols = []
    for d in dates:
        gaps = np.abs((df.columns - d).days.to_numpy())
        j = int(np.argmin(gaps))
        cols.append(df.iloc[:, j] if gaps[j] <= tol_days else pd.Series(np.nan, index=df.index))
    out = pd.concat(cols, axis=1)
    out.columns = list(dates)
    return out


def _pick(df: pd.DataFrame, aliases: list[str], n: int) -> tuple[np.ndarray, list]:
    """Per-year fallback cascade: for each year the first alias with a finite value wins. Returns (values, source alias per year)."""
    vals = np.full(n, np.nan)
    src: list = [None] * n
    if df is None or df.shape[0] == 0 or df.shape[1] < n:
        return vals, src
    lookup: dict[str, object] = {}
    for name in df.index:
        lookup.setdefault(norm_key(name), name)
    for alias in aliases:
        name = lookup.get(norm_key(alias))
        if name is None:
            continue
        row = df.loc[name]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        arr = pd.to_numeric(row, errors="coerce").to_numpy(dtype="float64")
        for i in range(n):
            if np.isnan(vals[i]) and np.isfinite(arr[i]):
                vals[i], src[i] = arr[i], alias
    return vals, src


def _cr(arr: object) -> np.ndarray:
    """Absolute rupees -> ₹ Crores, rounded to 2 decimals."""
    return np.round(np.asarray(arr, dtype="float64") / CRORE, 2)


def _lst(arr: object) -> list:
    return [None if not np.isfinite(x) else float(x) for x in np.asarray(arr, dtype="float64")]


def _yrs(mask: np.ndarray, years: list[str]) -> str:
    return ", ".join(y for y, m in zip(years, mask) if bool(m))


# --------------------------------------------------------------------------------------
# Network step (cache this one in the app)
# --------------------------------------------------------------------------------------
def fetch_yahoo_raw(symbol: str) -> dict:
    """Pull the annual income statement, balance sheet and cash flow plus a few info fields from Yahoo Finance.

    Raises ValueError with a plain-English message on any failure (so a failed fetch is never cached)."""
    ysym = to_yahoo_symbol(symbol)
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ValueError("The 'yfinance' package is not installed. Run: python -m pip install yfinance") from exc
    try:
        tk = yf.Ticker(ysym)
        inc, bs, cf = tk.income_stmt, tk.balance_sheet, tk.cashflow
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Yahoo Finance request failed for {ysym}: {exc}") from exc
    try:
        raw_info = dict(tk.info or {})
    except Exception:  # noqa: BLE001
        raw_info = {}

    def _frame(x: object) -> pd.DataFrame:
        return x.copy() if isinstance(x, pd.DataFrame) else pd.DataFrame()

    inc_df = _frame(inc)
    if inc_df.empty:
        raise ValueError(
            f"Yahoo Finance returned no income statement for {ysym}. The symbol may be wrong, renamed, delisted or newly listed, "
            "Yahoo may be rate-limiting you, or you may be offline. Try again in a minute."
        )
    return {
        "symbol": clean_symbol(symbol),
        "yahoo_symbol": ysym,
        "inc": inc_df,
        "bs": _frame(bs),
        "cf": _frame(cf),
        "info": {k: raw_info.get(k) for k in INFO_KEYS},
        "fetched_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------------------
# Pure step: raw Yahoo statements -> MEROS company data
# --------------------------------------------------------------------------------------
def build_company_data(raw: dict) -> dict:
    sym, ysym = str(raw.get("symbol") or ""), str(raw.get("yahoo_symbol") or "")
    info = dict(raw.get("info") or {})
    used: set = set()

    def _use(src: list) -> None:
        used.update(s for s in src if s)

    inc_all = _clean_periods(raw.get("inc"))
    if inc_all.shape[1] < MIN_YEARS:
        raise ValueError(
            f"Yahoo Finance returned {inc_all.shape[1]} usable annual period(s) for {ysym}; MEROS needs at least {MIN_YEARS}. "
            "The company may be newly listed, renamed or delisted. Try its current symbol or upload a Screener export."
        )
    inc = inc_all.iloc[:, -MAX_YEARS:]

    # keep only the latest unbroken run of years that have a revenue figure
    rev_try, _ = _pick(inc, REV_ALIASES, inc.shape[1])
    run = 0
    for v in rev_try[::-1]:
        if np.isfinite(v):
            run += 1
        else:
            break
    if run < MIN_YEARS:
        raise ValueError(f"Yahoo Finance has a revenue figure for only {run} consecutive recent year(s) of {ysym}; MEROS needs {MIN_YEARS}.")
    inc = inc.iloc[:, -run:]
    dates = list(inc.columns)
    n = len(dates)
    years = make_year_labels(dates)

    bs_full = _clean_periods(raw.get("bs"))
    bs = _align_periods(bs_full, dates)
    cf = _align_periods(_clean_periods(raw.get("cf")), dates)

    # ---- Revenue --------------------------------------------------------------------
    rev_raw, rev_src = _pick(inc, REV_ALIASES, n)
    _use(rev_src)
    rev_ops = _cr(rev_raw)
    ti_raw, ti_src = _pick(inc, ["Total Revenue"], n)
    _use(ti_src)
    ti_anchor = np.where(np.isfinite(ti_raw), _cr(ti_raw), rev_ops)
    oth_raw, oth_src = _pick(inc, ["Other Income Expense", "Non Operating Income Net Other"], n)
    _use(oth_src)
    oth = _cr(oth_raw)
    gap = np.maximum(0.0, ti_anchor - rev_ops)
    oth_used = np.nan_to_num(oth, nan=0.0) > 0.0
    rev_oth = np.round(np.where(oth_used, oth, gap), 2)

    # ---- Cost lines -----------------------------------------------------------------
    cogs_raw, cogs_src = _pick(inc, ["Cost Of Revenue"], n)
    _use(cogs_src)
    cogs_rep = np.isfinite(cogs_raw)
    cogs = np.abs(np.nan_to_num(_cr(cogs_raw), nan=0.0))
    dep_i, dep_i_src = _pick(inc, ["Reconciled Depreciation", "Depreciation And Amortization In Income Statement"], n)
    dep_c, dep_c_src = _pick(cf, ["Depreciation And Amortization", "Depreciation Amortization Depletion"], n)
    _use(dep_i_src)
    _use(dep_c_src)
    dep_from_cf = ~np.isfinite(dep_i) & np.isfinite(dep_c)
    dep = np.abs(np.nan_to_num(_cr(np.where(np.isfinite(dep_i), dep_i, dep_c)), nan=0.0))
    fin_r, fin_src = _pick(inc, ["Interest Expense", "Interest Expense Non Operating"], n)
    int_inc, ii_src = _pick(inc, ["Interest Income"], n)
    nii, nii_src = _pick(inc, ["Net Interest Income"], n)
    fin_bank = np.where(np.isfinite(int_inc) & np.isfinite(nii), np.maximum(int_inc - nii, 0.0), 0.0)
    fin_used_bank = ~np.isfinite(fin_r) & (fin_bank > 0.0)
    _use(fin_src)
    if bool(fin_used_bank.any()):
        _use(ii_src)
        _use(nii_src)
    fin = np.abs(_cr(np.where(np.isfinite(fin_r), fin_r, fin_bank)))

    # ---- Pretax, tax, attributable profit --------------------------------------------
    ni_raw, ni_src = _pick(inc, ["Net Income Common Stockholders", "Net Income", "Net Income Including Noncontrolling Interests"], n)
    pbt_raw, pbt_src = _pick(inc, ["Pretax Income"], n)
    tax_raw, tax_src = _pick(inc, ["Tax Provision"], n)
    _use(ni_src)
    _use(pbt_src)
    _use(tax_src)
    ni, pbt, tprov = _cr(ni_raw), _cr(pbt_raw), _cr(tax_raw)
    pbt_ok, ni_ok, tp_ok = np.isfinite(pbt), np.isfinite(ni), np.isfinite(tprov)
    for i in range(n):
        if (not pbt_ok[i] and not (ni_ok[i] and tp_ok[i])) or (not ni_ok[i] and not (pbt_ok[i] and tp_ok[i])):
            raise ValueError(f"Yahoo Finance is missing Pretax Income / Net Income / Tax Provision for {years[i]} of {ysym}, "
                             "so profit cannot be reconstructed. Upload a Screener export instead.")
    pbt = np.where(pbt_ok, pbt, ni + np.nan_to_num(tprov, nan=0.0))
    ni = np.where(ni_ok, ni, pbt - np.nan_to_num(tprov, nan=0.0))
    pbt, ni = np.round(pbt, 2), np.round(ni, 2)
    tax_rep = tp_ok
    tax = np.round(np.where(tax_rep, tprov, pbt - ni), 2)
    attr_adj = np.round((pbt - tax) - ni, 2)
    gap_flag = np.abs(attr_adj) > 0.05

    # ---- Employee cost: only from rows that name it ----------------------------------
    emp_raw, emp_src = _pick(inc, PAYROLL_ALIASES, n)
    _use(emp_src)
    emp_rep = np.isfinite(emp_raw)
    emp = np.round(np.where(emp_rep, np.abs(_cr(emp_raw)), 0.0), 2)
    emp_status = "reported" if emp_rep.all() else ("partial" if emp_rep.any() else "not_reported")

    payroll_candidates: list[dict] = []
    alias_keys = {norm_key(a) for a in PAYROLL_ALIASES}
    for name in inc.index:
        k = norm_key(name)
        if k in alias_keys or not any(w in str(name).lower() for w in PAYROLL_WORDS):
            continue
        row = pd.to_numeric(inc.loc[name], errors="coerce")
        payroll_candidates.append({"row": str(name), "values_cr": _lst(_cr(row.to_numpy(dtype="float64")))})
        if len(payroll_candidates) >= 8:
            break

    # ---- Algebraic closure: other operating expenses absorb every unclassified cost ---
    ti = np.round(rev_ops + rev_oth, 2)
    opex = np.round(ti - pbt - cogs - emp - dep - fin, 2)
    neg = opex < 0.0
    lift = np.where(neg, -opex, 0.0)
    rev_oth = np.round(rev_oth + lift, 2)
    opex = np.where(neg, 0.0, opex)
    ti = np.round(rev_ops + rev_oth, 2)
    if float(np.max(np.abs(ti - cogs - opex - emp - dep - fin - pbt))) > 1e-6:
        raise ValueError(f"Internal closure check failed for {ysym}: pretax profit could not be reproduced.")

    # ---- Capital, dividends, headcount -------------------------------------------------
    div_r, div_src = _pick(cf, ["Cash Dividends Paid", "Common Stock Dividend Paid"], n)
    _use(div_src)
    div_rep = np.isfinite(div_r)
    div = np.abs(np.nan_to_num(_cr(div_r), nan=0.0))
    debt_r, debt_src = _pick(bs, ["Total Debt"], n)
    ltd, ltd_src = _pick(bs, ["Long Term Debt"], n)
    cud, cud_src = _pick(bs, ["Current Debt"], n)
    _use(debt_src)
    debt_alt_ok = ~np.isfinite(debt_r) & (np.isfinite(ltd) | np.isfinite(cud))
    if bool(debt_alt_ok.any()):
        _use(ltd_src)
        _use(cud_src)
    debt_val = np.where(np.isfinite(debt_r), debt_r, np.nan_to_num(ltd, nan=0.0) + np.nan_to_num(cud, nan=0.0))
    debt = np.abs(_cr(debt_val))
    eq1, _ = _pick(bs, ["Stockholders Equity"], n)
    eq_all, eq_src = _pick(bs, ["Stockholders Equity", "Total Equity Gross Minority Interest"], n)
    _use(eq_src)
    eq_fallback = ~np.isfinite(eq1) & np.isfinite(eq_all)
    equity_rep = np.isfinite(eq_all)
    equity = np.nan_to_num(_cr(eq_all), nan=0.0)
    ta_raw, ta_src = _pick(bs, ["Total Assets"], n)
    _use(ta_src)
    total_assets = _cr(ta_raw)

    opening: dict = {"TOTAL_DEBT": None, "TOTAL_EQUITY": None, "TOTAL_ASSETS": None, "label": None}
    if bs_full.shape[1] > 0:
        gaps_o = np.array([(dates[0] - c).days for c in bs_full.columns], dtype="float64")
        cand = np.flatnonzero((gaps_o >= 300) & (gaps_o <= 430))
        if cand.size > 0:
            j = int(cand[np.argmin(np.abs(gaps_o[cand] - 365.0))])
            one = bs_full.iloc[:, [j]]
            od, _ = _pick(one, ["Total Debt"], 1)
            ol, _ = _pick(one, ["Long Term Debt"], 1)
            oc, _ = _pick(one, ["Current Debt"], 1)
            oe, _ = _pick(one, ["Stockholders Equity", "Total Equity Gross Minority Interest"], 1)
            ot, _ = _pick(one, ["Total Assets"], 1)
            if np.isfinite(oe[0]):
                od_val = od[0] if np.isfinite(od[0]) else np.nan_to_num(ol[0], nan=0.0) + np.nan_to_num(oc[0], nan=0.0)
                opening = {"TOTAL_DEBT": float(abs(_cr(od_val))), "TOTAL_EQUITY": float(_cr(oe[0])),
                           "TOTAL_ASSETS": (float(_cr(ot[0])) if np.isfinite(ot[0]) else None),
                           "label": bs_full.columns[j].strftime("%b %Y")}

    try:
        fte = int(float(info.get("fullTimeEmployees")))
    except (TypeError, ValueError):
        fte = 0
    hc = np.zeros(n)
    if fte > 0:
        hc[-1] = float(fte)
    hc_status = "snapshot_latest" if fte > 0 else "not_reported"

    # ---- Provenance ---------------------------------------------------------------------
    def pv(status: str, detail: str) -> list:
        return [status, detail]

    p_rev_oth = []
    for i in range(n):
        if oth_used[i]:
            base = ("Reported", f"{oth_src[i]} (a net Yahoo row)")
        elif gap[i] > 0:
            base = ("Derived", "Total Revenue − Operating Revenue")
        else:
            base = ("Not reported", "Yahoo has no other-income row; shown as 0")
        if lift[i] > 0:
            p_rev_oth.append(pv("Balancing", f"{base[1]} + ₹{lift[i]:,.2f} Cr lifted so Other Operating Expenses stay at or above 0"))
        else:
            p_rev_oth.append(pv(base[0], base[1]))

    p_fin = []
    for i in range(n):
        if np.isfinite(fin_r[i]):
            p_fin.append(pv("Reported", str(fin_src[i])))
        elif fin_used_bank[i]:
            p_fin.append(pv("Derived", "Interest Income − Net Interest Income"))
        else:
            p_fin.append(pv("Not reported", "Yahoo has no interest-expense row; shown as 0"))

    p_dep = []
    for i in range(n):
        if np.isfinite(dep_i[i]):
            p_dep.append(pv("Reported", str(dep_i_src[i])))
        elif np.isfinite(dep_c[i]):
            p_dep.append(pv("Reported", f"{dep_c_src[i]} (cash-flow statement)"))
        else:
            p_dep.append(pv("Not reported", "Yahoo has no depreciation row; shown as 0"))

    p_debt = []
    for i in range(n):
        if np.isfinite(debt_r[i]):
            p_debt.append(pv("Reported", str(debt_src[i])))
        elif debt_alt_ok[i]:
            p_debt.append(pv("Derived", "Long Term Debt + Current Debt"))
        else:
            p_debt.append(pv("Not reported", "Yahoo has no debt row; shown as 0"))

    prov = {
        "REV_OPS": [pv("Reported", str(rev_src[i])) for i in range(n)],
        "REV_OTH": p_rev_oth,
        "COGS_MAT": [pv("Reported", str(cogs_src[i])) if cogs_rep[i] else pv("Not reported", "Yahoo has no 'Cost Of Revenue' row; shown as 0")
                     for i in range(n)],
        "OPEX_EXT": [pv("Balancing", "Set to 0: reported costs exceeded income, so Other Income was lifted instead") if neg[i]
                     else pv("Balancing", "Revenue + other income − PBT − materials − employee − depreciation − finance cost, so Pretax Income equals Yahoo's")
                     for i in range(n)],
        "EMP_COST": [pv("Reported", str(emp_src[i])) if emp_rep[i] else pv("Not reported", "Yahoo has no payroll row; shown as 0, not estimated")
                     for i in range(n)],
        "FIN_COST": p_fin,
        "DEP_AMORT": p_dep,
        "TAX_EXP": [pv("Reported", "Tax Provision") if tax_rep[i] else pv("Derived", "Pretax Income − Net Income (no Tax Provision row)")
                    for i in range(n)],
        "DIV_PAID": [pv("Reported", f"{div_src[i]} (cash flow, absolute value)") if div_rep[i] else pv("Not reported", "Yahoo has no dividend row; shown as 0")
                     for i in range(n)],
        "TOTAL_DEBT": p_debt,
        "TOTAL_EQUITY": [pv("Reported", str(eq_src[i])) if equity_rep[i] else pv("Not reported", "Yahoo has no equity row; shown as 0")
                         for i in range(n)],
        "HEADCOUNT": [pv("Reported", f"fullTimeEmployees = {fte:,}, a current snapshot") if (fte > 0 and i == n - 1)
                      else pv("Not reported", "Yahoo gives no headcount history") for i in range(n)],
    }

    # ---- Notes, warnings, assumption status --------------------------------------------
    sector, industry = str(info.get("sector") or ""), str(info.get("industry") or "")
    currency = str(info.get("financialCurrency") or info.get("currency") or "INR").upper()
    is_fin = ("financial" in sector.lower()) or (bool(np.isfinite(int_inc).all()) and not bool(cogs_rep.any()))

    if emp_status == "reported":
        emp_note = f"Employee cost is the reported Yahoo Finance row for all {n} years (assumed to be the complete payroll)."
    else:
        miss = _yrs(~emp_rep, years)
        emp_note = (f"⚠ EMPLOYEE COST NOT REPORTED by Yahoo Finance for {miss}. MEROS does not estimate it: those years show 0 on the employee "
                    "line and the cost stays inside Other Operating Expenses, so GVA is understated and workforce metrics are not meaningful. "
                    "Upload a Screener export (it has an Employee Cost line) or type the figure into the override grid.")
        if payroll_candidates:
            emp_note += " Yahoo does list these possibly related rows (not used automatically): " + ", ".join(c["row"] for c in payroll_candidates) + "."
    if hc_status == "snapshot_latest":
        hc_note = (f"Headcount {fte:,} is Yahoo's single current figure and is applied to {years[-1]} only; earlier years are not reported, "
                   "so per-employee metrics exist for the latest year only unless you type earlier headcounts.")
    else:
        hc_note = "Yahoo reports no headcount for this company, so per-employee metrics are not available unless you type the headcount."
    if gap_flag.any():
        tax_note = ("Reported tax is kept as the Government share. (Pretax − Tax) exceeds reported profit attributable to shareholders by "
                    + ", ".join(f"₹{attr_adj[i]:,.2f} Cr ({years[i]})" for i in range(n) if gap_flag[i])
                    + " (minority interest, associates and other items). ROE and DuPont use attributable profit.")
    else:
        tax_note = "Reported tax and reported attributable profit reconcile with pretax income in all years."
    if neg.any():
        opex_note = ("Reported cost lines exceeded Yahoo's income in " + _yrs(neg, years) + ": Other Income was raised by "
                     + ", ".join(f"₹{lift[i]:,.2f} Cr ({years[i]})" for i in range(n) if neg[i])
                     + " so Other Operating Expenses stay at zero and pretax profit still equals Yahoo's (assumption Y09).")
    else:
        opex_note = ("Other Operating Expenses is the balancing figure, non-negative in all years: pretax profit equals Yahoo's to the paisa "
                     "(assumption Y08). It proves consistency, not that each cost line is individually right.")
    warnings: list[str] = []
    if currency != "INR":
        warnings.append(f"Yahoo reports financials in {currency}, not INR; figures were still divided by 1e7 and labelled ₹ Crores (assumption Y01).")
    if is_fin:
        warnings.append("Bank / financial company detected: revenue is interest-based and finance cost is Interest Income − Net Interest Income. "
                        "Value-added, ROCE, DuPont and EVA figures are indicative only (assumption Y17).")

    status: dict[str, str] = {k: "always" for k in ("Y02", "Y03", "Y04", "Y05", "Y06", "Y08", "Y13", "Y14")}
    status["Y01"] = "active" if currency != "INR" else "always"
    status["Y07"] = "active" if emp_status != "reported" else "inactive"
    status["Y09"] = "active" if bool(neg.any()) else "inactive"
    status["Y10"] = "active" if bool(gap_flag.any()) else "inactive"
    status["Y11"] = "active" if bool(dep_from_cf.any()) else "inactive"
    status["Y12"] = "active" if bool(fin_used_bank.any()) else "inactive"
    status["Y15"] = "active" if bool(eq_fallback.any()) else "inactive"
    status["Y16"] = "active" if hc_status == "snapshot_latest" else "inactive"
    status["Y17"] = "active" if is_fin else "inactive"
    status["Y18"] = "active" if opening["TOTAL_EQUITY"] is not None else "inactive"

    values = {
        "REV_OPS": rev_ops, "REV_OTH": rev_oth, "COGS_MAT": cogs, "OPEX_EXT": opex, "EMP_COST": emp,
        "FIN_COST": fin, "DEP_AMORT": dep, "TAX_EXP": tax, "DIV_PAID": div, "TOTAL_DEBT": debt,
        "TOTAL_EQUITY": equity, "HEADCOUNT": hc,
    }
    grid = build_grid(values, years)

    return {
        "source": "yahoo",
        "symbol": sym,
        "yahoo_symbol": ysym,
        "company_name": str(info.get("longName") or info.get("shortName") or sym),
        "sector": sector,
        "industry": industry,
        "currency": currency,
        "is_financial": bool(is_fin),
        "version": "unknown",
        "basis_note": "Yahoo Finance does not state whether its figures are consolidated or standalone.",
        "years": years,
        "period_ends": [d.strftime("%Y-%m-%d") for d in dates],
        "period_labels": [d.strftime("%b %Y") for d in dates],
        "grid": grid,
        "attr_adj": [float(x) for x in attr_adj],
        "anchors": {"TOTAL_REVENUE": _lst(ti_anchor), "PBT": _lst(pbt), "PAT_ATTR": _lst(ni), "TAX_REPORTED": _lst(tprov)},
        "extras": {"TOTAL_ASSETS": _lst(total_assets)},
        "opening": opening,
        "provenance": prov,
        "status": status,
        "emp_status": emp_status,
        "hc_status": hc_status,
        "notes": {"emp": emp_note, "headcount": hc_note, "tax": tax_note, "opex": opex_note},
        "warnings": warnings,
        "payroll_candidates": payroll_candidates,
        "used_rows": sorted(used),
        "fetched_at": str(raw.get("fetched_at") or _dt.datetime.now().isoformat(timespec="seconds")),
    }


def fetch_company_data(symbol: str) -> dict:
    """Convenience: fetch from Yahoo and build the company data in one call (the app caches the two steps separately)."""
    return build_company_data(fetch_yahoo_raw(symbol))


# --------------------------------------------------------------------------------------
# Raw viewer
# --------------------------------------------------------------------------------------
def raw_tables(raw: dict, used_rows: list[str]) -> dict[str, pd.DataFrame]:
    """Yahoo's untouched statements in ₹ Cr, with a tick against every row MEROS read."""
    used_keys = {norm_key(x) for x in used_rows}

    def one(df: object) -> pd.DataFrame:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return pd.DataFrame({"note": ["Yahoo Finance returned no data for this statement."]})
        out = (df.apply(pd.to_numeric, errors="coerce") / CRORE).round(2)
        cols = []
        for c in out.columns:
            t = pd.to_datetime(c, errors="coerce")
            cols.append(str(c) if pd.isna(t) else t.strftime("%b %Y"))
        out.columns = cols
        out.insert(0, "Used by MEROS", ["✔" if norm_key(i) in used_keys else "" for i in out.index])
        out.index = [str(i) for i in out.index]
        return out

    return {"Income statement": one(raw.get("inc")), "Balance sheet": one(raw.get("bs")), "Cash flow": one(raw.get("cf"))}