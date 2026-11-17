"""MEROS benchmark data: 4 synthetic Indian enterprise archetypes (₹ Crores) + live NSE/BSE ingestion via Yahoo Finance."""
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
EMP_LAKHS_PER_HEAD: float = 12.0

POPULAR_TICKERS: list[str] = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS", "HINDUNILVR.NS", "BAJFINANCE.NS",
    "SBIN.NS", "MARUTI.NS", "LT.NS", "ASIANPAINT.NS", "NESTLEIND.NS", "ZOMATO.NS", "ETERNAL.NS", "TATAMOTORS.NS",
]

EMP_MODE_LABELS: dict[str, str] = {
    "sector": "Sector-based estimate (default)",
    "custom": "Custom % of revenue",
    "none": "Do not estimate (leave 0 and flag)",
}

# Employee cost as % of revenue: (typical, low, high, label, Yahoo 'Cost Of Revenue' mostly contains people cost?)
# These are ROUGH RULES OF THUMB from general knowledge of Indian listed-company annual reports.
# They are NOT computed from Yahoo data or from a dataset analysed by the author; ranges are wide.
SECTOR_EMP_PCT: dict[str, tuple[float, float, float, str, bool]] = {
    "technology": (40.0, 20.0, 55.0, "Technology", True),
    "financial services": (9.0, 5.0, 14.0, "Financial services", False),
    "consumer defensive": (5.0, 3.0, 9.0, "Consumer defensive", False),
    "consumer cyclical": (6.0, 3.0, 12.0, "Consumer cyclical", False),
    "industrials": (9.0, 4.0, 16.0, "Industrials", False),
    "basic materials": (4.0, 2.0, 8.0, "Basic materials", False),
    "energy": (2.0, 1.0, 5.0, "Energy", False),
    "utilities": (4.0, 2.0, 8.0, "Utilities", False),
    "healthcare": (15.0, 9.0, 22.0, "Healthcare", False),
    "communication services": (8.0, 3.0, 15.0, "Communication services", False),
    "real estate": (6.0, 3.0, 12.0, "Real estate", False),
}
INDUSTRY_EMP_PCT: list[tuple[str, tuple[float, float, float, str, bool]]] = [
    ("information technology services", (50.0, 45.0, 58.0, "IT services", True)),
]
DEFAULT_EMP_PCT: tuple[float, float, float, str, bool] = (7.0, 3.0, 15.0, "Unclassified sector", False)


def lookup_emp_ratio(sector: object, industry: object) -> dict:
    """Pick the employee-cost-to-revenue rule of thumb from Yahoo's industry (first) or sector."""
    ind, sec = str(industry or "").lower(), str(sector or "").lower().strip()
    hit = None
    for keyword, tup in INDUSTRY_EMP_PCT:
        if keyword in ind:
            hit = tup
            break
    if hit is None:
        hit = SECTOR_EMP_PCT.get(sec, DEFAULT_EMP_PCT)
    typ, lo, hi, label, carve = hit
    return {"typical": typ, "low": lo, "high": hi, "label": label, "cogs_has_emp": carve}


_SECTOR_TXT = "; ".join(
    f"{v[3]} {v[0]:.0f}% (range {v[1]:.0f}-{v[2]:.0f}%)"
    for v in [INDUSTRY_EMP_PCT[0][1]] + list(SECTOR_EMP_PCT.values()) + [DEFAULT_EMP_PCT]
)

# (id, scope, area, assumption, why it is needed, effect and how to override). scope: Live | All | Archetype
ASSUMPTION_REGISTER: list[tuple[str, str, str, str, str, str]] = [
    ("L01", "Live", "Units & currency",
     "Yahoo's figures are Indian rupees. Every amount is divided by 10,000,000 and rounded to 2 decimals to give ₹ Crores.",
     "Yahoo returns absolute currency units while Indian disclosure uses crores (1 Cr = 10 million). The currency tag is read from Yahoo's 'financialCurrency'.",
     "Exact if the company reports in INR. A non-INR tag raises a warning but nothing is converted, so the scale would be wrong."),
    ("L02", "Live", "Fiscal-year labels",
     "The latest three annual periods are labelled FY24, FY25, FY26 by position, oldest to newest.",
     "MEROS has three fixed year columns and Yahoo returns period-end dates, not Indian fiscal-year names. The real period ends are shown beside every label.",
     "If the newest filing is older than March 2026, 'FY26' just means 'latest year'. Check the dates in the sidebar and the bridge."),
    ("L03", "Live", "Statement alignment",
     "Balance-sheet and cash-flow columns are matched to income-statement periods by nearest date, within 45 days.",
     "Yahoo serves the three statements as separate tables whose columns are not guaranteed to line up. Date matching keeps a year's debt, equity and dividends with that year's profit.",
     "A year with no match falls back to 0 for that item. It is visible and editable in the override grid."),
    ("L04", "Live", "Revenue line",
     "Revenue from operations = 'Operating Revenue', else 'Total Revenue', else 'Interest Income' (banks).",
     "Yahoo's line items follow a global taxonomy, not Schedule III. Banks have no 'operating revenue', so interest income is the closest top line.",
     "Gross interest income for a bank is not comparable with a manufacturer's sales."),
    ("L05", "Live", "Other income",
     "Other income = Yahoo's 'Other Income Expense' or 'Non Operating Income Net Other' if positive, otherwise the gap Total Revenue minus Operating Revenue (never below 0).",
     "Yahoo has no clean 'Other income' row. Those lines are net figures and can include non-operating expenses.",
     "Other income can be over- or under-stated. Pretax income is unaffected because the balancing figure (L09) absorbs the difference."),
    ("L06", "Live", "Cost of revenue as 'materials'",
     "COGS_MAT = Yahoo's 'Cost Of Revenue' (0 if absent).",
     "It is the nearest Yahoo line to 'materials and stock-in-trade'.",
     "Not Schedule III. For IT firms it mostly holds people cost and for banks it is absent. Total bought-in cost is fixed by PBT, so only the materials-versus-other split moves."),
    ("L07", "Live", "Employee cost",
     "Employee cost = Yahoo's 'Salaries And Wages' when present (taken as the complete payroll). Otherwise it is estimated as a % of revenue by your chosen mode: sector rule of thumb (default), custom %, or left at 0 and flagged.",
     "Yahoo rarely carries Schedule III 'Employee benefit expense' for Indian companies. The sector table (% of revenue: " + _SECTOR_TXT
     + ") is a rule of thumb from typical Indian annual reports, not data computed from Yahoo, and its ranges are wide. The earlier '55% of SG&A' rule was dropped because SG&A contents differ by company.",
     "In live mode GVA = PBT + employee cost + depreciation + finance cost, so every ₹1 Cr of error here moves GVA, labour share, value added per employee and Human Capital ROI by the same amount. PBT, PAT, ROCE, ROE and coverage are unaffected. Type the real figure into the override grid."),
    ("L08", "Live", "IT-services carve-out",
     "For Technology and IT services, an estimated employee cost is carved out of 'Cost Of Revenue' first instead of being added on top.",
     "In IT-services filings most cost of revenue is people cost, so adding a separate payroll estimate would double count it and the balancing figure would run out of room.",
     "Total bought-in plus workforce cost is unchanged; only the split moves. Not applied when payroll is reported."),
    ("L09", "Live", "Other operating expenses = balancing figure",
     "OPEX_EXT = (REV_OPS + REV_OTH) - PBT - COGS - EMP - DEP - FIN.",
     "Yahoo bundles many Schedule III lines (freight, power, marketing, provisions, exceptional items) and has no 'other expenses' row. Solving for it reproduces Yahoo's Pretax Income and, with L11, Net Income to the paisa, so VAS closure is exact.",
     "It absorbs every cost not otherwise classified, including exceptional items and, for banks, provisions. It is the least 'observed' cost line in live mode."),
    ("L10", "Live", "Negative balancing figure",
     "If the balancing figure would be negative it is set to 0 and Other Income is raised by the shortfall.",
     "A negative expense is meaningless, and raising income keeps Pretax Income exact.",
     "Other Income is overstated in those years. The gold notice names the years and amounts."),
    ("L11", "Live", "Tax expense",
     "TAX_EXP = Pretax Income minus Net Income. Yahoo's 'Tax Provision' is used only to flag differences.",
     "This makes PAT equal Yahoo's Net Income exactly. The two differ when there are minority interests, associates or exceptional items.",
     "Those items are counted as 'Government' in the value-added statement. The notice lists years where they differ by more than ₹0.05 Cr."),
    ("L12", "Live", "Depreciation source",
     "Depreciation = 'Reconciled Depreciation', else 'Depreciation And Amortization In Income Statement', else the cash-flow D&A line.",
     "Yahoo does not always populate the same line, so a fixed cascade is used.",
     "Cash-flow D&A can include items such as impairments that are not in the P&L. Marked ACTIVE only when the fallback is used."),
    ("L13", "Live", "Finance cost for banks",
     "Without an 'Interest Expense' row, finance cost = Interest Income minus Net Interest Income.",
     "Net interest income is a result, not a cost. Gross interest expense is the difference, so using it directly would put income in a cost line.",
     "An exact identity when both rows exist; otherwise finance cost is 0."),
    ("L14", "Live", "Dividends",
     "Dividends = cash dividends paid in the cash-flow statement (absolute value), 0 if missing.",
     "Yahoo has no 'declared dividend' line. The cash-flow figure is what actually left the company.",
     "Timing differs from declared dividends and may include payouts to minority holders."),
    ("L15", "Live", "Debt definition",
     "Debt = Yahoo's 'Total Debt', else long-term plus current debt.",
     "It is the closest Yahoo item to total borrowings.",
     "Total Debt can include lease liabilities (Ind AS 116), which raises 'debt'. For banks, deposits are not debt, so ROCE and coverage are not comparable with non-financials."),
    ("L16", "Live", "Equity definition",
     "Equity = 'Stockholders Equity' (parent's equity), else 'Total Equity Gross Minority Interest'.",
     "ROE uses profit attributable to common holders, so the matching denominator is the parent's equity.",
     "The fallback includes minority interest and makes ROE slightly inconsistent. Marked ACTIVE only when used."),
    ("L17", "Live", "Headcount",
     "Headcount = Yahoo's single current 'fullTimeEmployees' applied to all three years. If missing, it is estimated as employee cost divided by your cost-per-employee setting (default ₹12 lakh).",
     "Yahoo gives only a snapshot, not a history, and often nothing for Indian firms. ₹12 lakh is a blunt cross-sector average (IT, FMCG and banks differ widely) and is editable in the sidebar.",
     "Value added per employee and cost per employee for earlier years are approximate. A headcount estimated from an estimated payroll inherits both errors."),
    ("L18", "Live", "Banks and financial companies",
     "Banks and NBFCs are processed with the same value-added template.",
     "MEROS has one schema, and for lenders interest is both the main revenue and the main cost.",
     "Indicative only: deposits are not debt, COGS is 0 and gross interest income is the top line."),
    ("E01", "All", "Government share",
     "The government slice is income-tax expense only.",
     "The statements read here do not show GST, customs, excise or property tax collected or paid, and Schedule III revenue is net of GST.",
     "It understates the state's full tax take. Read it as direct tax on profits."),
    ("E02", "All", "The '₹100 receipt' base",
     "'₹100 spent by the customer' = ₹100 of Total Income (operating revenue plus other income).",
     "The audited P&L is the only record of what customers paid the company. GST, discounts and channel margins sit outside it.",
     "Other income is treated as if it came from customers. It is a presentation device, not consumer-spending data."),
    ("E03", "All", "Entity reinvestment",
     "Entity reinvestment = retained earnings + depreciation.",
     "GVA is gross of depreciation, so the part that stays inside the firm is retained profit plus the capital consumed.",
     "If retained earnings are negative (a loss or high payout) this slice becomes small or negative."),
    ("E04", "All", "Retained earnings timing",
     "Retained earnings = PAT minus dividends paid in the same year.",
     "Needed for exact closure with only three years of data and no reserve movements.",
     "Dividends paid often relate to the previous year's profit, so single-year retention can look odd, even negative."),
    ("E05", "All", "Year-end capital base",
     "ROCE, ROE and implied cost of debt use year-end balances, not averages.",
     "FY24's opening balance is not available in a three-year window, so year-end values keep every year comparable.",
     "Overstates returns for fast-growing firms and understates them for shrinking ones."),
    ("E06", "All", "Economic spread (EVA proxy)",
     "Economic spread = ROCE minus implied cost of debt.",
     "A true EVA needs WACC (cost of equity, beta, market values), which filings do not contain.",
     "It ignores the cost of equity, so a positive spread does not prove value creation."),
    ("E07", "All", "Zero-debt / zero-interest guards",
     "No debt shows 0% cost of debt, and no interest shows coverage as infinite (stored as 999).",
     "Avoids division by zero while keeping the maths vectorised.",
     "999 is a sentinel, not a real ratio."),
    ("E08", "All", "Blank cells",
     "Blank, missing or unparseable input cells are imputed as 0.0 and logged.",
     "A blank is more often a nil line (no dividend, no debt) than an unknown number, and every imputation appears in the repair log.",
     "If the blank was really unknown, that line is understated. Check the audit log."),
    ("E09", "All", "Diagnostic thresholds",
     "Diagnostic cut-offs are fixed rules of thumb, e.g. bought-in 85% or more = thin-spread, ROCE 15% or more = strong, interest cover below 3x = watchlist.",
     "The engine is deterministic and explainable, and there is no peer dataset here to calibrate against.",
     "They are screening labels, not ratings. Sector norms differ (banks, utilities, IT)."),
    ("E10", "All", "Shock simulator",
     "One-period, static what-if: volumes and other costs do not react; the materials shock hits COGS only, wages hit employee cost, the rate shock hits year-end debt immediately, price pass-through lifts operating revenue only, dividends stay constant, and tax uses the FY26 effective rate if PBT is positive.",
     "A transparent first-order sensitivity needs a fixed rule set. Behavioural response (demand elasticity, hedging, repricing lags) needs data we do not have.",
     "Real outcomes will differ. Use it for sensitivity, not forecasting."),
    ("A01", "Archetype", "Synthetic companies",
     "The four pre-loaded companies are synthetic archetypes, not real filings.",
     "They illustrate four business models (FMCG, IT services, auto, quick-commerce) so the engine can be demonstrated without a live feed. Figures were designed to have realistic proportions.",
     "Never cite them as ITC, HUL, TCS, Infosys, Tata Motors, M&M, Zomato or Swiggy numbers."),
    ("A02", "Archetype", "Dirty-data simulation",
     "'Dirty ERP formatting' is deliberately injected into 4 to 5 cells.",
     "To exercise and demonstrate the hygiene pipeline.",
     "Imputed blanks (e.g. FY24 finance cost in the FMCG archetype) change that year's ratios. Untick the box to see the clean data."),
]

_BASE_RE = re.compile(r"^[A-Z0-9&_\-]+$")
INFO_KEYS = ("longName", "shortName", "sector", "industry", "financialCurrency", "currency", "fullTimeEmployees")


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


def fetch_yahoo_raw(ticker_symbol: str) -> dict:
    """Network step only: pull the three annual statements and a few info fields. Raises (so Streamlit never caches a failure)."""
    sym = normalize_ticker(ticker_symbol)
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ValueError("The 'yfinance' package is not installed. Run: pip install yfinance") from exc
    try:
        tk = yf.Ticker(sym)
        inc, bs, cf = tk.income_stmt, tk.balance_sheet, tk.cashflow
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Yahoo Finance request failed for {sym}: {exc}") from exc
    try:
        raw_info = dict(tk.info or {})
    except Exception:  # noqa: BLE001
        raw_info = {}

    def _frame(x: object) -> pd.DataFrame:
        return x.copy() if isinstance(x, pd.DataFrame) else pd.DataFrame()

    inc_df = _frame(inc)
    if inc_df.empty:
        raise ValueError(
            f"Yahoo Finance returned no income statement for {sym}. The symbol may be wrong, renamed or delisted, "
            "Yahoo may be rate-limiting you, or you may be offline. Try again in a minute or use the .BO suffix."
        )
    return {"symbol": sym, "inc": inc_df, "bs": _frame(bs), "cf": _frame(cf), "info": {k: raw_info.get(k) for k in INFO_KEYS}}


def build_live_statement(raw: dict, emp_mode: str = "sector", emp_pct: float | None = None,
                         lakhs_per_head: float = EMP_LAKHS_PER_HEAD) -> tuple[pd.DataFrame, dict]:
    """Pure transformation of raw Yahoo statements into the MEROS 12-row schema (₹ Crores) plus a metadata dict.

    OPEX_EXT is solved algebraically so PBT == Yahoo Pretax Income and PAT == Yahoo Net Income exactly.
    """
    if emp_mode not in EMP_MODE_LABELS:
        raise ValueError(f"Unknown employee-cost mode '{emp_mode}'. Use one of {list(EMP_MODE_LABELS)}.")
    sym = str(raw.get("symbol") or "")
    info = dict(raw.get("info") or {})

    inc = _clean_periods(raw.get("inc"), 3)
    if inc.shape[1] < 3:
        raise ValueError(
            f"Yahoo Finance returned {inc.shape[1]} usable annual period(s) for {sym}; MEROS needs three. "
            "The symbol may be wrong, newly listed, renamed or delisted. Try the .BO suffix or the company's current ticker."
        )
    inc = inc.iloc[:, -3:]
    dates = list(inc.columns)
    bs = _align_periods(_clean_periods(raw.get("bs"), 3), dates)
    cf = _align_periods(_clean_periods(raw.get("cf"), 3), dates)

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
    dep_from_cf = ~np.isfinite(dep_i) & np.isfinite(dep_c)
    dep = np.abs(np.nan_to_num(_cr(np.where(np.isfinite(dep_i), dep_i, dep_c)), nan=0.0))
    fin_r, _ = _pick(inc, ["Interest Expense", "Interest Expense Non Operating"])
    int_inc, _ = _pick(inc, ["Interest Income"])
    nii, _ = _pick(inc, ["Net Interest Income"])
    fin_bank = np.where(np.isfinite(int_inc) & np.isfinite(nii), np.maximum(int_inc - nii, 0.0), 0.0)
    fin_used_bank = ~np.isfinite(fin_r) & (fin_bank > 0.0)
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

    def _yrs(mask: np.ndarray) -> str:
        return ", ".join(y for y, m in zip(YEARS, mask) if bool(m))

    # ---- Employee cost: reported row, else estimate / custom % / leave blank -----------
    sal_raw, _ = _pick(inc, ["Salaries And Wages", "Wages And Salaries"])
    sal = np.abs(_cr(sal_raw))
    reported = np.isfinite(sal)
    est_mask = ~reported
    ratio = lookup_emp_ratio(info.get("sector"), info.get("industry"))
    pct = float(emp_pct) if (emp_mode == "custom" and emp_pct is not None) else float(ratio["typical"])
    pct = max(0.0, min(pct, 95.0))
    ti0 = np.round(rev_ops + rev_oth, 2)
    pool = np.maximum(ti0 - pbt - cogs - dep - fin, 0.0)
    est_raw = np.zeros(3) if emp_mode == "none" else rev_ops * pct / 100.0
    carve_possible = (emp_mode != "none") and bool(ratio["cogs_has_emp"])
    carve_cap = np.where(reported | (not carve_possible), 0.0, np.minimum(est_raw, cogs))
    cap = pool + carve_cap
    capped = est_mask & (est_raw > cap + 1e-9)
    est = np.round(np.clip(est_raw, 0.0, cap), 2)
    carve = np.round(np.minimum(carve_cap, est), 2)
    cogs_final = np.where(reported, cogs, np.round(cogs - carve, 2))
    emp = np.where(reported, np.round(sal, 2), est)

    if not est_mask.any():
        emp_status = "reported"
        emp_note = ("EMP_COST is the reported Yahoo Finance 'Salaries And Wages' line for all three years "
                    "(assumed to be the complete employee cost; see assumption L07).")
    elif emp_mode == "none":
        emp_status = "missing"
        emp_note = (f"⚠ EMPLOYEE COST NOT AVAILABLE for {_yrs(est_mask)}: Yahoo Finance has no payroll line for {sym} and you chose not to "
                    "estimate, so EMP_COST is 0. Workforce share of value added, value added per employee and Human Capital ROI are NOT "
                    "meaningful until you type the real figure into the verification grid.")
    else:
        emp_status = "estimated"
        basis = (f"your custom {pct:.1f}% of revenue" if emp_mode == "custom" else
                 f"{pct:.1f}% of revenue (rule of thumb for {ratio['label']}; typical range {ratio['low']:.0f}-{ratio['high']:.0f}%)")
        extra = ""
        if capped.any():
            extra += f" Capped at the available expense pool in {_yrs(capped)}."
        if bool((carve > 0).any()):
            extra += " The estimate is carved out of Yahoo's Cost Of Revenue (mostly people cost for this sector) instead of being added on top."
        emp_note = (f"EMP_COST is ESTIMATED for {_yrs(est_mask)} at {basis}.{extra} "
                    "Replace it with the annual-report figure in the verification grid.")

    # ---- Algebraic closure: OPEX_EXT absorbs every unclassified expense ---------------
    ti = np.round(rev_ops + rev_oth, 2)
    opex = np.round(ti - pbt - cogs_final - emp - dep - fin, 2)
    neg = opex < 0.0
    lift = np.where(neg, -opex, 0.0)
    rev_oth = np.round(rev_oth + lift, 2)
    opex = np.where(neg, 0.0, opex)
    ti = np.round(rev_ops + rev_oth, 2)
    if float(np.max(np.abs(ti - cogs_final - opex - emp - dep - fin - pbt))) > 1e-6:
        raise ValueError(f"Internal closure check failed for {sym}: PBT could not be reproduced.")
    if neg.any():
        opex_note = ("Reported cost lines exceeded Yahoo's income in " + _yrs(neg) + ": Other Income was raised by "
                     + ", ".join(f"₹{lift[i]:,.2f} Cr ({YEARS[i]})" for i in range(3) if neg[i])
                     + " so Other Operating Expenses stay at zero and Yahoo's Pretax Income is still reproduced exactly (assumption L10).")
    else:
        opex_note = ("OPEX_EXT is the balancing figure (REV_OPS + REV_OTH − PBT − COGS − EMP − DEP − FIN), non-negative in all years: "
                     "Yahoo's Pretax Income and Net Income are reproduced to the paisa (assumption L09).")
    if tax_dev.any():
        tax_note = ("Yahoo 'Tax Provision' differs from Pretax − Net Income by "
                    + ", ".join(f"₹{tax_gap[i]:,.2f} Cr ({YEARS[i]})" for i in range(3) if tax_dev[i])
                    + " (minority interest, associates or exceptional items). TAX_EXP is set to Pretax − Net Income so PAT equals "
                    "Yahoo's Net Income exactly (assumption L11).")
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
    eq1, _ = _pick(bs, ["Stockholders Equity"])
    eq_all, _ = _pick(bs, ["Stockholders Equity", "Total Equity Gross Minority Interest"])
    eq_fallback = ~np.isfinite(eq1) & np.isfinite(eq_all)
    equity = np.nan_to_num(_cr(eq_all), nan=0.0)

    lph = max(float(lakhs_per_head), 0.1)
    try:
        fte = int(float(info.get("fullTimeEmployees")))
    except (TypeError, ValueError):
        fte = 0
    if fte > 0:
        hc_status = "snapshot"
        hc = np.full(3, float(fte))
        hc_note = (f"HEADCOUNT = {fte:,} (Yahoo 'fullTimeEmployees', one current figure) applied to all three years; "
                   "edit per year in the grid if needed (assumption L17).")
    elif bool((emp > 0).any()):
        hc_status = "estimated"
        hc = np.where(emp > 0, np.maximum(np.round(emp * 100.0 / lph), 1.0), 0.0)
        hc_note = (f"Yahoo has no 'fullTimeEmployees' for {sym}: HEADCOUNT is ESTIMATED as EMP_COST ÷ ₹{lph:.0f} Lakhs per employee"
                   + (", so it also inherits the employee-cost estimate's error" if emp_status != "reported" else "")
                   + ". Edit it in the verification grid (assumption L17).")
    else:
        hc_status = "missing"
        hc = np.zeros(3)
        hc_note = (f"HEADCOUNT is NOT AVAILABLE for {sym} (no Yahoo headcount and no employee cost to derive it from): it is 0, so per-employee "
                   "metrics are meaningless until you enter it in the verification grid.")

    # ---- Metadata, warnings and assumption status ------------------------------------
    sector, industry = str(info.get("sector") or ""), str(info.get("industry") or "")
    currency = str(info.get("financialCurrency") or info.get("currency") or "INR").upper()
    is_fin = ("financial" in sector.lower()) or (bool(np.isfinite(int_inc).all()) and not bool((cogs > 0).any()))
    warnings: list[str] = []
    if currency != "INR":
        warnings.append(f"Yahoo reports financials in {currency}, not INR; figures were still divided by 1e7 and labelled ₹ Crores (assumption L01).")
    if is_fin:
        warnings.append("Bank / financial company detected: revenue is interest-based, COGS is 0 and finance cost is Interest Income − "
                        "Net Interest Income. Value-added ratios are indicative for lenders (assumptions L13, L15, L18).")

    status: dict[str, str] = {k: "always" for k in ("L02", "L03", "L04", "L05", "L06", "L09", "L11", "L14", "L15")}
    status["L01"] = "active" if currency != "INR" else "always"
    status["L07"] = "inactive" if emp_status == "reported" else "active"
    status["L08"] = "active" if bool((carve > 0).any()) else "inactive"
    status["L10"] = "active" if bool(neg.any()) else "inactive"
    status["L12"] = "active" if bool(dep_from_cf.any()) else "inactive"
    status["L13"] = "active" if bool(fin_used_bank.any()) else "inactive"
    status["L16"] = "active" if bool(eq_fallback.any()) else "inactive"
    status["L17"] = "always" if hc_status == "snapshot" else "active"
    status["L18"] = "active" if is_fin else "inactive"

    values = {
        "REV_OPS": rev_ops, "REV_OTH": rev_oth, "COGS_MAT": cogs_final, "OPEX_EXT": opex, "EMP_COST": emp,
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
        "emp_mode": emp_mode,
        "emp_status": emp_status,
        "emp_pct_used": float(pct),
        "emp_ratio": ratio,
        "hc_status": hc_status,
        "emp_cost_note": emp_note,
        "headcount_note": hc_note,
        "tax_note": tax_note,
        "opex_note": opex_note,
        "warnings": warnings,
        "assumption_status": status,
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


def fetch_live_nse_ticker(ticker_symbol: str, emp_mode: str = "sector", emp_pct: float | None = None,
                          lakhs_per_head: float = EMP_LAKHS_PER_HEAD) -> tuple[pd.DataFrame, dict]:
    """One-call convenience wrapper: fetch from Yahoo Finance, then build the MEROS statement."""
    return build_live_statement(fetch_yahoo_raw(ticker_symbol), emp_mode, emp_pct, lakhs_per_head)


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
