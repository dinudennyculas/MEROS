"""MEROS benchmark data: 4 Indian enterprise archetypes (₹ Crores) + live NSE/BSE ingestion via Yahoo Finance."""
from __future__ import annotations

import datetime as _dt
import re

import numpy as np
import pandas as pd

YEARS: list[str] = ["FY24", "FY25", "FY26"]

SCHEMA: list[tuple[str, str, str]] = [
    ("REV_OPS", "Revenue from Operations", "Income"),
    ("REV_OTH", "Other Income", "Income"),
    ("COGS_MAT", "Cost of Materials & Stock-in-Trade", "Bought-In Cost"),
    ("OPEX_EXT", "Other Operating Expenses (Freight, Power, Marketing, Vendors)", "Bought-In Cost"),
    ("EMP_COST", "Employee Benefit Expenses", "Workforce"),
    ("FIN_COST", "Finance Costs (Interest Expense)", "Lenders"),
    ("DEP_AMORT", "Depreciation & Amortization", "Capital Consumption"),
    ("TAX_EXP", "Total Tax Expense", "Government"),
    ("DIV_PAID", "Equity Dividends Paid", "Shareholders"),
    ("TOTAL_DEBT", "Total Borrowings (Long-Term + Short-Term Debt)", "Balance Sheet"),
    ("TOTAL_EQUITY", "Total Shareholders' Equity (Net Worth)", "Balance Sheet"),
    ("HEADCOUNT", "Total Permanent Employees (Integer count)", "Workforce Disclosure"),
]

DEFAULT_ARCHETYPE: str = "FMCG Leader (ITC / HUL Archetype)"

_ARCHETYPE_DATA: dict[str, dict[str, tuple[float, float, float]]] = {
    "FMCG Leader (ITC / HUL Archetype)": {
        "REV_OPS": (58200.0, 60900.0, 64100.0),
        "REV_OTH": (1300.0, 1450.0, 1600.0),
        "COGS_MAT": (25600.0, 26700.0, 28000.0),
        "OPEX_EXT": (10800.0, 11300.0, 12000.0),
        "EMP_COST": (2700.0, 2850.0, 3000.0),
        "FIN_COST": (90.0, 95.0, 85.0),
        "DEP_AMORT": (1100.0, 1150.0, 1250.0),
        "TAX_EXP": (4900.0, 5165.0, 5450.0),
        "DIV_PAID": (12200.0, 12900.0, 13600.0),
        "TOTAL_DEBT": (1000.0, 950.0, 900.0),
        "TOTAL_EQUITY": (58000.0, 60500.0, 63200.0),
        "HEADCOUNT": (24500.0, 24900.0, 25300.0),
    },
    "IT Services Giant (TCS / Infosys Archetype)": {
        "REV_OPS": (180000.0, 192000.0, 206000.0),
        "REV_OTH": (4200.0, 4600.0, 5000.0),
        "COGS_MAT": (600.0, 650.0, 700.0),
        "OPEX_EXT": (36000.0, 38200.0, 40400.0),
        "EMP_COST": (94000.0, 100500.0, 108000.0),
        "FIN_COST": (600.0, 640.0, 680.0),
        "DEP_AMORT": (4800.0, 5100.0, 5500.0),
        "TAX_EXP": (12300.0, 13150.0, 14250.0),
        "DIV_PAID": (25000.0, 27500.0, 29500.0),
        "TOTAL_DEBT": (6000.0, 6200.0, 6500.0),
        "TOTAL_EQUITY": (90000.0, 96000.0, 102000.0),
        "HEADCOUNT": (550000.0, 570000.0, 585000.0),
    },
    "Industrial & Auto Major (Tata Motors / M&M Archetype)": {
        "REV_OPS": (105000.0, 118000.0, 126000.0),
        "REV_OTH": (1800.0, 2000.0, 2200.0),
        "COGS_MAT": (66000.0, 73500.0, 78000.0),
        "OPEX_EXT": (15500.0, 17200.0, 18800.0),
        "EMP_COST": (8800.0, 9600.0, 10400.0),
        "FIN_COST": (3600.0, 3500.0, 3300.0),
        "DEP_AMORT": (5800.0, 6300.0, 6800.0),
        "TAX_EXP": (1850.0, 2570.0, 2830.0),
        "DIV_PAID": (1100.0, 1900.0, 2300.0),
        "TOTAL_DEBT": (40000.0, 38000.0, 36000.0),
        "TOTAL_EQUITY": (42000.0, 48000.0, 54000.0),
        "HEADCOUNT": (78000.0, 80500.0, 83000.0),
    },
    "New-Age Q-Commerce & Food Tech (Zomato / Swiggy Archetype)": {
        "REV_OPS": (12000.0, 20500.0, 33500.0),
        "REV_OTH": (900.0, 1150.0, 1300.0),
        "COGS_MAT": (1500.0, 4800.0, 9500.0),
        "OPEX_EXT": (9200.0, 13450.0, 20800.0),
        "EMP_COST": (1950.0, 2400.0, 3000.0),
        "FIN_COST": (140.0, 160.0, 210.0),
        "DEP_AMORT": (520.0, 700.0, 950.0),
        "TAX_EXP": (30.0, 45.0, 85.0),
        "DIV_PAID": (0.0, 0.0, 0.0),
        "TOTAL_DEBT": (1200.0, 1300.0, 1800.0),
        "TOTAL_EQUITY": (18500.0, 19200.0, 19900.0),
        "HEADCOUNT": (7800.0, 9400.0, 12500.0),
    },
}

_DIRTY_PLANS: dict[str, list[tuple[str, str, str]]] = {
    "FMCG Leader (ITC / HUL Archetype)": [
        ("REV_OPS", "FY24", "rupee"),
        ("COGS_MAT", "FY25", "cr"),
        ("FIN_COST", "FY24", "none"),
        ("EMP_COST", "ID", "id_trail"),
        ("TAX_EXP", "ID", "id_lower"),
    ],
    "IT Services Giant (TCS / Infosys Archetype)": [
        ("REV_OPS", "FY24", "rupee"),
        ("COGS_MAT", "FY26", "cr"),
        ("FIN_COST", "FY25", "blank"),
        ("EMP_COST", "ID", "id_trail"),
        ("TAX_EXP", "ID", "id_lower"),
    ],
    "Industrial & Auto Major (Tata Motors / M&M Archetype)": [
        ("REV_OPS", "FY24", "rupee"),
        ("COGS_MAT", "FY25", "cr"),
        ("DIV_PAID", "FY24", "padded"),
        ("EMP_COST", "ID", "id_trail"),
        ("TAX_EXP", "ID", "id_lower"),
    ],
    "New-Age Q-Commerce & Food Tech (Zomato / Swiggy Archetype)": [
        ("REV_OPS", "FY24", "rupee"),
        ("COGS_MAT", "FY25", "cr"),
        ("DIV_PAID", "FY24", "none"),
        ("DIV_PAID", "FY25", "blank"),
        ("EMP_COST", "ID", "id_trail"),
    ],
}

ARCHETYPES: dict[str, dict[str, tuple[float, float, float]]] = _ARCHETYPE_DATA


def _clean_frame(archetype_name: str) -> pd.DataFrame:
    data = _ARCHETYPE_DATA[archetype_name]
    records = {
        "Line_ID": [s[0] for s in SCHEMA],
        "Line_Item_Name": [s[1] for s in SCHEMA],
        "Category": [s[2] for s in SCHEMA],
    }
    for i, yr in enumerate(YEARS):
        records[yr] = [float(data[s[0]][i]) for s in SCHEMA]
    return pd.DataFrame(records)


def _inject_corruptions(df: pd.DataFrame, plan: list[tuple[str, str, str]]) -> pd.DataFrame:
    out = df.copy()
    out["Line_ID"] = out["Line_ID"].astype(object)
    for yr in YEARS:
        out[yr] = out[yr].astype(object)
    row_of = {lid: i for i, lid in enumerate(df["Line_ID"].tolist())}

    for line_id, target, mode in plan:
        row = row_of[line_id]
        if target == "ID":
            if mode == "id_trail":
                out.at[row, "Line_ID"] = f"{line_id} "
            elif mode == "id_lower":
                out.at[row, "Line_ID"] = f" {line_id.lower()} "
            continue
        value = float(df.at[row, target])
        if mode == "rupee":
            out.at[row, target] = f"₹ {value:,.2f}"
        elif mode == "cr":
            out.at[row, target] = f"{value:,.2f} Cr"
        elif mode == "padded":
            out.at[row, target] = f"  {value:,.2f} "
        elif mode == "none":
            out.at[row, target] = None
        elif mode == "blank":
            out.at[row, target] = ""
    return out


def get_archetype_df(archetype_name: str, inject_dirty_data: bool = True) -> pd.DataFrame:
    """Return the canonical 12-row statement for an archetype, optionally with ERP-style corruptions."""
    if archetype_name not in _ARCHETYPE_DATA:
        raise KeyError(
            f"Unknown archetype '{archetype_name}'. Available: {list(_ARCHETYPE_DATA.keys())}"
        )
    df = _clean_frame(archetype_name)
    if inject_dirty_data:
        df = _inject_corruptions(df, _DIRTY_PLANS[archetype_name])
    return df


def get_blank_template_bytes() -> bytes:
    """Return a clean CSV template (12-row schema, zeroed FY columns) as UTF-8 bytes."""
    template = pd.DataFrame(
        {
            "Line_ID": [s[0] for s in SCHEMA],
            "Line_Item_Name": [s[1] for s in SCHEMA],
            "Category": [s[2] for s in SCHEMA],
            "FY24": [0.0] * len(SCHEMA),
            "FY25": [0.0] * len(SCHEMA),
            "FY26": [0.0] * len(SCHEMA),
        }
    )
    return template.to_csv(index=False).encode("utf-8")


# ======================================================================================
# Live NSE / BSE ingestion via Yahoo Finance (yfinance)
# ======================================================================================
CRORE: float = 1e7
EMP_SGA_SHARE: float = 0.55
EMP_REV_SHARE: float = 0.07
EMP_LAKHS_PER_HEAD: float = 12.0

POPULAR_TICKERS: list[str] = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS", "HINDUNILVR.NS", "BAJFINANCE.NS",
    "SBIN.NS", "MARUTI.NS", "LT.NS", "ASIANPAINT.NS", "NESTLEIND.NS", "ZOMATO.NS", "ETERNAL.NS", "TATAMOTORS.NS",
]

_BASE_RE = re.compile(r"^[A-Z0-9&_\-]+$")


def normalize_ticker(symbol: str) -> str:
    """Strip whitespace, uppercase, and default to the NSE suffix unless .NS / .BO is already present."""
    s = re.sub(r"\s+", "", str(symbol or "")).upper()
    if not s:
        raise ValueError("Enter a ticker symbol, e.g. RELIANCE, TCS or HDFCBANK.")
    if not (s.endswith(".NS") or s.endswith(".BO")):
        s += ".NS"
    if not _BASE_RE.match(s[:-3]):
        raise ValueError(f"'{symbol}' is not a valid NSE/BSE ticker symbol.")
    return s


def _key(name: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _clean_periods(df: object, min_values: int = 3) -> pd.DataFrame:
    """Datetime-index the columns, coerce to numeric, drop empty periods, sort oldest -> newest."""
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


def _pick(df: pd.DataFrame, aliases: list[str], n: int = 3) -> tuple[np.ndarray, list]:
    """Per-year fallback cascade: first alias with a finite value wins for each year."""
    vals = np.full(n, np.nan)
    src: list = [None] * n
    if df is None or df.shape[0] == 0 or df.shape[1] < n:
        return vals, src
    lookup: dict[str, object] = {}
    for name in df.index:
        lookup.setdefault(_key(name), name)
    for alias in aliases:
        name = lookup.get(_key(alias))
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


def fetch_live_nse_ticker(ticker_symbol: str) -> tuple[pd.DataFrame, dict]:
    """Scrape the latest 3 annual filings of an NSE/BSE company from Yahoo Finance into the MEROS 12-row schema.

    Returns (DataFrame[Line_ID, Line_Item_Name, Category, FY24, FY25, FY26] in ₹ Crores, metadata dict).
    OPEX_EXT is solved algebraically so PBT == Yahoo Pretax Income and PAT == Yahoo Net Income exactly.
    """
    sym = normalize_ticker(ticker_symbol)
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ValueError("The 'yfinance' package is not installed. Run: pip install yfinance") from exc

    try:
        tk = yf.Ticker(sym)
        inc_raw, bs_raw, cf_raw = tk.income_stmt, tk.balance_sheet, tk.cashflow
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Yahoo Finance request failed for {sym}: {exc}") from exc
    try:
        info = dict(tk.info or {})
    except Exception:  # noqa: BLE001
        info = {}

    # ---- 3 chronological annual periods, oldest -> newest ------------------------------
    inc = _clean_periods(inc_raw, 3)
    if inc.shape[1] < 3:
        raise ValueError(
            f"Yahoo Finance returned {inc.shape[1]} usable annual period(s) for {sym}; MEROS needs three. "
            "The symbol may be wrong, newly listed, renamed or delisted. Try the .BO suffix or the company's current ticker."
        )
    inc = inc.iloc[:, -3:]
    dates = list(inc.columns)
    bs = _align_periods(_clean_periods(bs_raw, 3), dates)
    cf = _align_periods(_clean_periods(cf_raw, 3), dates)

    # ---- Revenue --------------------------------------------------------------------
    rev_raw, rev_src = _pick(inc, ["Operating Revenue", "Total Revenue", "Interest Income"])
    if not np.isfinite(rev_raw).all():
        raise ValueError(f"No revenue line (Operating Revenue / Total Revenue / Interest Income) found for {sym}.")
    rev_ops = _cr(rev_raw)
    ti_raw, _ = _pick(inc, ["Total Revenue"])
    ti_anchor = np.where(np.isfinite(ti_raw), _cr(ti_raw), rev_ops)
    oth_raw, _ = _pick(inc, ["Other Income Expense", "Non Operating Income Net Other"])
    oth = _cr(oth_raw)
    gap = np.maximum(0.0, ti_anchor - rev_ops)
    rev_oth = np.round(np.where(np.nan_to_num(oth, nan=0.0) > 0.0, oth, gap), 2)

    # ---- Cost lines -----------------------------------------------------------------
    cogs_raw, _ = _pick(inc, ["Cost Of Revenue"])
    cogs = np.abs(np.nan_to_num(_cr(cogs_raw), nan=0.0))
    dep_i, _ = _pick(inc, ["Reconciled Depreciation", "Depreciation And Amortization In Income Statement"])
    dep_c, _ = _pick(cf, ["Depreciation And Amortization", "Depreciation Amortization Depletion"])
    dep = np.abs(np.nan_to_num(_cr(np.where(np.isfinite(dep_i), dep_i, dep_c)), nan=0.0))
    fin_r, _ = _pick(inc, ["Interest Expense", "Interest Expense Non Operating"])
    int_inc, _ = _pick(inc, ["Interest Income"])
    nii, _ = _pick(inc, ["Net Interest Income"])
    fin_bank = np.where(np.isfinite(int_inc) & np.isfinite(nii), np.maximum(int_inc - nii, 0.0), 0.0)
    fin = np.abs(_cr(np.where(np.isfinite(fin_r), fin_r, fin_bank)))

    # ---- Pretax / Net income anchors and tax reconciliation ----------------------------
    pat_r, _ = _pick(inc, ["Net Income Common Stockholders", "Net Income", "Net Income Including Noncontrolling Interests"])
    pbt_r, _ = _pick(inc, ["Pretax Income"])
    tax_r, _ = _pick(inc, ["Tax Provision"])
    if bool((~np.isfinite(pat_r) & ~np.isfinite(tax_r)).any()):
        raise ValueError(f"Yahoo Finance has neither Net Income nor Tax Provision for some years of {sym}.")
    pat, pbt, tprov = _cr(pat_r), _cr(pbt_r), _cr(tax_r)
    pbt = np.where(np.isfinite(pbt), pbt, pat + np.nan_to_num(tprov, nan=0.0))
    pat = np.where(np.isfinite(pat), pat, pbt - np.nan_to_num(tprov, nan=0.0))
    if not (np.isfinite(pbt).all() and np.isfinite(pat).all()):
        raise ValueError(f"Pretax Income / Net Income could not be resolved for {sym}.")
    pbt, pat = np.round(pbt, 2), np.round(pat, 2)
    tax = np.round(pbt - pat, 2)
    tax_gap = np.where(np.isfinite(tprov), np.abs(tprov - tax), 0.0)
    tax_dev = tax_gap > 0.05

    # ---- Employee cost (reported row, else deterministic SG&A / revenue estimate) -------
    sal_raw, _ = _pick(inc, ["Salaries And Wages", "Wages And Salaries"])
    sal = np.abs(_cr(sal_raw))
    has_rep = np.isfinite(sal)
    sga_raw, _ = _pick(inc, ["Selling General And Administration"])
    sga = _cr(sga_raw)
    has_sga = np.isfinite(sga)
    est_raw = np.where(has_sga, EMP_SGA_SHARE * sga, EMP_REV_SHARE * rev_ops)
    pool = np.maximum((rev_ops + rev_oth) - pbt - cogs - dep - fin, 0.0)
    capped = est_raw > pool
    est = np.round(np.clip(est_raw, 0.0, pool), 2)
    emp = np.where(has_rep, np.round(sal, 2), est)

    def _yrs(mask: np.ndarray) -> str:
        return ", ".join(y for y, m in zip(YEARS, mask) if bool(m))

    if has_rep.all():
        emp_note = "EMP_COST is the reported Yahoo Finance 'Salaries And Wages' line for all three years."
    else:
        est_mask = ~has_rep
        parts = []
        if bool((est_mask & has_sga).any()):
            parts.append(f"{EMP_SGA_SHARE * 100:.0f}% of reported SG&A ({_yrs(est_mask & has_sga)})")
        if bool((est_mask & ~has_sga).any()):
            parts.append(f"{EMP_REV_SHARE * 100:.0f}% of revenue ({_yrs(est_mask & ~has_sga)})")
        cap_txt = f" Capped at the available expense pool in {_yrs(est_mask & capped)}." if bool((est_mask & capped).any()) else ""
        emp_note = (
            f"Yahoo Finance has no separate employee-cost row for {sym}: EMP_COST is ESTIMATED as " + " and ".join(parts) + "."
            + cap_txt + " Edit it in the verification grid; Other Operating Expenses re-balance so PBT still equals Yahoo's."
        )

    # ---- Algebraic closure: OPEX_EXT absorbs every unclassified expense ---------------
    ti = np.round(rev_ops + rev_oth, 2)
    opex = np.round(ti - pbt - cogs - emp - dep - fin, 2)
    neg = opex < 0.0
    lift = np.where(neg, -opex, 0.0)
    rev_oth = np.round(rev_oth + lift, 2)
    opex = np.where(neg, 0.0, opex)
    ti = np.round(rev_ops + rev_oth, 2)
    if float(np.max(np.abs(ti - cogs - opex - emp - dep - fin - pbt))) > 1e-6:
        raise ValueError(f"Internal closure check failed for {sym}: PBT could not be reproduced.")
    if neg.any():
        opex_note = ("Reported cost lines exceeded Yahoo's income in " + _yrs(neg) + ": Other Income was raised by "
                     + ", ".join(f"₹{lift[i]:,.2f} Cr ({YEARS[i]})" for i in range(3) if neg[i])
                     + " so Other Operating Expenses stay at zero and Yahoo's Pretax Income is still reproduced exactly.")
    else:
        opex_note = ("OPEX_EXT = (REV_OPS + REV_OTH) − PBT − COGS − EMP − DEP − FIN, non-negative in all years: "
                     "Yahoo's Pretax Income and Net Income are reproduced to the paisa.")
    if tax_dev.any():
        tax_note = ("Yahoo 'Tax Provision' differs from Pretax − Net Income by "
                    + ", ".join(f"₹{tax_gap[i]:,.2f} Cr ({YEARS[i]})" for i in range(3) if tax_dev[i])
                    + " (minority interest, associates or exceptional items). TAX_EXP is set to Pretax − Net Income so PAT equals Yahoo's Net Income exactly.")
    else:
        tax_note = "Yahoo 'Tax Provision' reconciles to Pretax Income − Net Income in all three years."

    # ---- Capital, dividends, headcount ----------------------------------------------
    div_r, _ = _pick(cf, ["Cash Dividends Paid", "Common Stock Dividend Paid"])
    div = np.abs(np.nan_to_num(_cr(div_r), nan=0.0))
    debt_r, _ = _pick(bs, ["Total Debt"])
    ltd, _ = _pick(bs, ["Long Term Debt"])
    cud, _ = _pick(bs, ["Current Debt"])
    debt_alt = np.nan_to_num(ltd, nan=0.0) + np.nan_to_num(cud, nan=0.0)
    debt = np.abs(_cr(np.where(np.isfinite(debt_r), debt_r, debt_alt)))
    eq_r, _ = _pick(bs, ["Stockholders Equity", "Total Equity Gross Minority Interest"])
    equity = np.nan_to_num(_cr(eq_r), nan=0.0)

    try:
        fte = int(float(info.get("fullTimeEmployees")))
    except (TypeError, ValueError):
        fte = 0
    if fte > 0:
        hc = np.full(3, float(fte))
        hc_note = (f"HEADCOUNT = {fte:,} (Yahoo 'fullTimeEmployees', a single current figure) applied to all three years; "
                   "edit per year in the grid if needed.")
    else:
        hc = np.maximum(np.round(emp * 100.0 / EMP_LAKHS_PER_HEAD), 1.0)
        hc_note = (f"Yahoo has no 'fullTimeEmployees' for {sym}: HEADCOUNT is ESTIMATED from EMP_COST at "
                   f"₹{EMP_LAKHS_PER_HEAD:.0f} Lakhs per employee. Edit it in the verification grid.")

    # ---- Metadata & warnings ----------------------------------------------------------
    sector = str(info.get("sector") or "")
    industry = str(info.get("industry") or "")
    currency = str(info.get("financialCurrency") or info.get("currency") or "INR").upper()
    is_fin = ("financial" in sector.lower()) or (bool(np.isfinite(int_inc).all()) and not bool((cogs > 0).any()))
    warnings: list[str] = []
    if currency != "INR":
        warnings.append(f"Yahoo reports financials in {currency}, not INR; figures were still divided by 1e7 and labelled ₹ Crores.")
    if is_fin:
        warnings.append("Bank / financial company detected: revenue is interest-based, COGS is 0 and finance cost is "
                        "Interest Income − Net Interest Income. Value-added ratios are indicative for lenders.")

    values = {
        "REV_OPS": rev_ops, "REV_OTH": rev_oth, "COGS_MAT": cogs, "OPEX_EXT": opex, "EMP_COST": emp,
        "FIN_COST": fin, "DEP_AMORT": dep, "TAX_EXP": tax, "DIV_PAID": div, "TOTAL_DEBT": debt,
        "TOTAL_EQUITY": equity, "HEADCOUNT": hc,
    }
    frame = {
        "Line_ID": [s[0] for s in SCHEMA],
        "Line_Item_Name": [s[1] for s in SCHEMA],
        "Category": [s[2] for s in SCHEMA],
    }
    for i, yr in enumerate(YEARS):
        frame[yr] = [float(values[s[0]][i]) for s in SCHEMA]
    df = pd.DataFrame(frame)

    meta = {
        "symbol": sym,
        "company_name": str(info.get("longName") or info.get("shortName") or sym),
        "sector": sector,
        "industry": industry,
        "currency": currency,
        "is_financial": bool(is_fin),
        "period_ends": [d.strftime("%Y-%m-%d") for d in dates],
        "period_labels": [d.strftime("%b %Y") for d in dates],
        "fy_map": {yr: d.strftime("%Y-%m-%d") for yr, d in zip(YEARS, dates)},
        "units_note": "Yahoo Finance reports absolute ₹; every monetary figure was divided by 1e7 to ₹ Crores (2 dp).",
        "emp_cost_note": emp_note,
        "headcount_note": hc_note,
        "tax_note": tax_note,
        "opex_note": opex_note,
        "warnings": warnings,
        "anchors": {
            "TOTAL_REVENUE": _lst(ti_anchor),
            "PBT": _lst(pbt),
            "PAT": _lst(pat),
            "TAX_PROVISION": _lst(tprov),
        },
        "sources": {"REV_OPS": rev_src},
        "fetched_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    return df, meta


def rebalance_to_pbt_anchor(df: pd.DataFrame, pbt_anchor: list) -> pd.DataFrame:
    """Re-solve OPEX_EXT (lifting REV_OTH if it would go negative) so PBT still equals the Yahoo anchor after user edits."""
    out = df.copy()
    pos = {str(k).strip().upper(): i for i, k in enumerate(out["Line_ID"])}
    need = ["REV_OPS", "REV_OTH", "COGS_MAT", "OPEX_EXT", "EMP_COST", "DEP_AMORT", "FIN_COST"]
    if any(k not in pos for k in need):
        return out
    pbt = np.asarray([np.nan if v is None else v for v in pbt_anchor], dtype="float64")
    for j, yr in enumerate(YEARS):
        if not np.isfinite(pbt[j]):
            continue
        v = pd.to_numeric(out[yr], errors="coerce").fillna(0.0).to_numpy(dtype="float64")
        rev_oth = v[pos["REV_OTH"]]
        ti = v[pos["REV_OPS"]] + rev_oth
        opex = ti - pbt[j] - v[pos["COGS_MAT"]] - v[pos["EMP_COST"]] - v[pos["DEP_AMORT"]] - v[pos["FIN_COST"]]
        if opex < 0.0:
            rev_oth, opex = rev_oth - opex, 0.0
        col = out.columns.get_loc(yr)
        out.iloc[pos["REV_OTH"], col] = round(float(rev_oth), 2)
        out.iloc[pos["OPEX_EXT"], col] = round(float(opex), 2)
    return out


if __name__ == "__main__":
    sample = get_archetype_df(DEFAULT_ARCHETYPE, inject_dirty_data=True)
    sample.to_csv("sample_corporate_statement.csv", index=False, encoding="utf-8-sig")
    print(f"Saved sample_corporate_statement.csv ({DEFAULT_ARCHETYPE}, {len(sample)} rows).")