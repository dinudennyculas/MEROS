"""MEROS core engine: hygiene, common-size anatomy, value-added statement, KPIs, diagnostics and stress test.

Works on ANY number of annual periods (the year labels are passed in). Pure Python / pandas / NumPy:
no AI, no network calls. Data modules (Yahoo, Screener) build the 12-line grid; this module only analyses it."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------------------
# Schema (the 12 canonical lines every data source must fill)
# --------------------------------------------------------------------------------------
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
REQUIRED_IDS: list[str] = [s[0] for s in SCHEMA]
SCHEMA_NAMES: dict[str, str] = {s[0]: s[1] for s in SCHEMA}
SCHEMA_CATEGORIES: dict[str, str] = {s[0]: s[2] for s in SCHEMA}
META_COLS: list[str] = ["Line_ID", "Line_Item_Name", "Category"]

RECEIPT_LABELS: list[str] = [
    "Materials (COGS_MAT)",
    "External Vendors & Ops (OPEX_EXT)",
    "Workforce (EMP_COST)",
    "Depreciation (DEP_AMORT)",
    "Lenders (FIN_COST)",
    "Government Tax (TAX_EXP)",
    "Shareholder Dividends (DIV_PAID)",
    "Retained Profit (Retained_Earnings)",
]

STAKEHOLDER_LABELS: list[str] = [
    "Workforce (EMP_COST)",
    "Debt Capital Providers (FIN_COST)",
    "Government (TAX_EXP)",
    "Equity Dividends (DIV_PAID)",
    "Entity Reinvestment (Retained Earnings + Depreciation)",
]

_MISSING_TOKENS = frozenset({"", "none", "nan", "null", "nil", "na", "n/a", "-", "--", "—", "–"})

_MONEY_METRICS = frozenset({
    "Revenue_from_Operations", "Total_Income", "Bought_In_Costs", "GVA", "EBITDA", "EBIT",
    "PBT", "Tax_Expense", "PAT", "PAT_Attributable", "Retained_Earnings",
})


# --------------------------------------------------------------------------------------
# Year labels
# --------------------------------------------------------------------------------------
def fy_label(period_end: Any) -> str:
    """Indian fiscal-year label of a period end: April-December of year X -> FY(X+1); January-March of year X -> FY(X)."""
    d = pd.Timestamp(period_end)
    fy = d.year + 1 if d.month >= 4 else d.year
    return f"FY{fy % 100:02d}"


def make_year_labels(period_ends: Sequence[Any]) -> list[str]:
    """Unique labels for a list of period ends (a duplicate gets a '-2' style suffix)."""
    labels: list[str] = []
    seen: dict[str, int] = {}
    for p in period_ends:
        base = fy_label(p)
        seen[base] = seen.get(base, 0) + 1
        labels.append(base if seen[base] == 1 else f"{base}-{seen[base]}")
    return labels


def build_grid(values: dict[str, Sequence[float]], years: Sequence[str]) -> pd.DataFrame:
    """The canonical grid: Line_ID, Line_Item_Name, Category, then one float column per year. Missing lines become 0.0."""
    ylist = [str(y) for y in years]
    frame: dict[str, list] = {
        "Line_ID": [s[0] for s in SCHEMA],
        "Line_Item_Name": [s[1] for s in SCHEMA],
        "Category": [s[2] for s in SCHEMA],
    }
    for j, yr in enumerate(ylist):
        col: list[float] = []
        for lid, _name, _cat in SCHEMA:
            v = 0.0
            if lid in values:
                try:
                    v = float(values[lid][j])
                except (TypeError, ValueError, IndexError):
                    v = 0.0
            col.append(v if np.isfinite(v) else 0.0)
        frame[yr] = col
    return pd.DataFrame(frame)


def _resolve_years(df: pd.DataFrame, years: Sequence[str] | None) -> list[str]:
    if years is not None:
        ylist = [str(y).strip() for y in years]
    else:
        ylist = [str(c).strip() for c in df.columns if str(c).strip() not in META_COLS]
    if not ylist:
        raise ValueError("No fiscal-year columns were found in the statement.")
    return ylist


# --------------------------------------------------------------------------------------
# Vectorized helpers
# --------------------------------------------------------------------------------------
def _safe_div(num: Any, den: Any, fill: float = 0.0, positive_only: bool = True) -> np.ndarray:
    """Vectorized division guarded with np.where. Denominator must be >0 (or !=0) else `fill`."""
    n = np.asarray(num, dtype="float64")
    d = np.asarray(den, dtype="float64")
    mask = (d > 0) if positive_only else (d != 0)
    safe_d = np.where(mask, d, 1.0)
    return np.where(mask, n / safe_d, fill)


def _cagr_pct(start: float, end: float, periods: int) -> float:
    """(end/start)**(1/periods) - 1 in %, NaN when either endpoint is non-positive or there is only one period."""
    if periods >= 1 and start > 0 and end > 0:
        return float(((end / start) ** (1.0 / periods) - 1.0) * 100.0)
    return float("nan")


def _ladder(rev_ops, rev_oth, cogs, opex, emp, dep, fin, tax, div) -> dict[str, np.ndarray]:
    total_income = rev_ops + rev_oth
    bought_in = cogs + opex
    gva = total_income - bought_in
    ebitda = gva - emp
    ebit = ebitda - dep
    pbt = ebit - fin
    pat = pbt - tax
    retained = pat - div
    nva = gva - dep
    return {
        "Total_Income": total_income,
        "Bought_In_Costs": bought_in,
        "GVA": gva,
        "EBITDA": ebitda,
        "EBIT": ebit,
        "PBT": pbt,
        "PAT": pat,
        "Retained_Earnings": retained,
        "NVA": nva,
    }


def _receipt_components(cogs, opex, emp, dep, fin, tax, div, retained) -> dict[str, np.ndarray]:
    return {
        RECEIPT_LABELS[0]: np.asarray(cogs, dtype="float64"),
        RECEIPT_LABELS[1]: np.asarray(opex, dtype="float64"),
        RECEIPT_LABELS[2]: np.asarray(emp, dtype="float64"),
        RECEIPT_LABELS[3]: np.asarray(dep, dtype="float64"),
        RECEIPT_LABELS[4]: np.asarray(fin, dtype="float64"),
        RECEIPT_LABELS[5]: np.asarray(tax, dtype="float64"),
        RECEIPT_LABELS[6]: np.asarray(div, dtype="float64"),
        RECEIPT_LABELS[7]: np.asarray(retained, dtype="float64"),
    }


def _receipt_frames(
    components: dict[str, np.ndarray], total_income: np.ndarray, columns: list[str]
) -> dict[str, Any]:
    """Normalize components per ₹100 of Total_Income; allocate paise by largest remainder so each
    column sums to exactly ₹100.00 (10,000 paise)."""
    labels = list(components.keys())
    mat = np.vstack([np.asarray(components[k], dtype="float64") for k in labels])
    ti = np.asarray(total_income, dtype="float64")

    exact = _safe_div(mat * 100.0, ti)
    raw_paise = exact * 100.0
    floors = np.floor(raw_paise)
    remainders = raw_paise - floors
    deficit = np.rint(10000.0 - floors.sum(axis=0)).astype("int64")
    ranks = np.argsort(np.argsort(-remainders, axis=0, kind="stable"), axis=0, kind="stable")
    bump = (ranks < deficit).astype("int64")
    paise = np.where(ti > 0, floors.astype("int64") + bump, 0).astype("int64")
    rupees = paise / 100.0

    exact_sum = exact.sum(axis=0)
    ok = (np.abs(exact_sum - 100.0) < 1e-6) & (paise.sum(axis=0) == 10000) & (ti > 0)

    whole = np.trunc(rupees).astype("int64")
    sub_paise = paise - whole * 100
    long_df = pd.DataFrame(
        {
            "Period": np.tile(columns, len(labels)),
            "Component": np.repeat(labels, len(columns)),
            "Rupees": rupees.ravel(),
            "Rupees_Whole": whole.ravel(),
            "Paise": sub_paise.ravel(),
        }
    )
    return {
        "exact": pd.DataFrame(exact, index=labels, columns=columns),
        "rupees": pd.DataFrame(rupees, index=labels, columns=columns),
        "paise": pd.DataFrame(paise, index=labels, columns=columns),
        "long": long_df,
        "sum_exact": dict(zip(columns, exact_sum.astype(float).tolist())),
        "sum_rounded": dict(zip(columns, (paise.sum(axis=0) / 100.0).astype(float).tolist())),
        "ok_by_period": dict(zip(columns, [bool(v) for v in ok])),
        "all_ok": bool(np.all(ok)),
    }


# --------------------------------------------------------------------------------------
# 1. Hygiene pipeline
# --------------------------------------------------------------------------------------
def sanitize_statement_df(raw_df: pd.DataFrame, years: Sequence[str] | None = None) -> tuple[pd.DataFrame, dict]:
    """Clean a statement grid: normalise Line_IDs, strip currency text, fix negatives, impute blanks as 0.0 and log every repair.

    Returns (clean DataFrame indexed by Line_ID with Line_Item_Name, Category and the year columns, hygiene audit dict).
    """
    if not isinstance(raw_df, pd.DataFrame):
        raise TypeError("raw_df must be a pandas DataFrame.")

    df = raw_df.copy()
    if "Line_ID" not in [str(c).strip() for c in df.columns] and str(df.index.name).strip() == "Line_ID":
        df = df.reset_index()

    canon = {c.lower(): c for c in META_COLS}
    df.columns = [canon.get(str(c).strip().lower().replace(" ", "_"), str(c).strip()) for c in df.columns]
    if "Line_ID" not in df.columns:
        raise ValueError("Input is missing the required column: Line_ID")

    ylist = _resolve_years(df, years)
    missing_cols = [c for c in ylist if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Input is missing year columns: {missing_cols}")
    for meta in ("Line_Item_Name", "Category"):
        if meta not in df.columns:
            df[meta] = np.nan
    df = df[META_COLS + ylist].reset_index(drop=True)

    log: list[str] = []
    repaired = 0

    # ---- Line_ID normalization -------------------------------------------------------
    raw_ids = df["Line_ID"].astype(str)
    norm_ids = raw_ids.str.strip().str.upper().str.replace(r"[\s\-]+", "_", regex=True)
    valid = norm_ids.isin(REQUIRED_IDS)
    dup = norm_ids.duplicated(keep="first") & valid

    for i in np.flatnonzero(~valid.to_numpy()):
        log.append(f"Row {i + 1}: unrecognized or blank Line_ID {raw_ids.iloc[i]!r} dropped.")
    for i in np.flatnonzero(dup.to_numpy()):
        log.append(f"Row {i + 1}: duplicate Line_ID '{norm_ids.iloc[i]}' dropped (first occurrence kept).")

    keep = valid & ~dup
    df = df.loc[keep].reset_index(drop=True)
    raw_ids = raw_ids.loc[keep].reset_index(drop=True)
    norm_ids = norm_ids.loc[keep].reset_index(drop=True)

    id_changed = (raw_ids != norm_ids).to_numpy()
    for i in np.flatnonzero(id_changed):
        log.append(f"Line_ID {raw_ids.iloc[i]!r} normalized to '{norm_ids.iloc[i]}'.")
    repaired += int(id_changed.sum())
    df["Line_ID"] = norm_ids

    # ---- Numeric coercion ------------------------------------------------------------
    id_arr = norm_ids.to_numpy()
    for yr in ylist:
        col = df[yr]
        direct = pd.to_numeric(col, errors="coerce")
        direct_arr = direct.to_numpy(dtype="float64")
        direct_ok = np.isfinite(direct_arr)

        cleaned = (
            col.astype(str)
            .str.replace("\u2212", "-", regex=False)
            .str.replace(r"\s+", "", regex=True)
            .str.replace(r"(?i)(crores?|cr\.?|rs\.?|inr|usd|[₹$€£])", "", regex=True)
            .str.replace(",", "", regex=False)
        )
        is_missing = (col.isna() | cleaned.str.lower().isin(_MISSING_TOKENS)).to_numpy()
        paren = cleaned.str.match(r"^\(.+\)$")
        body = cleaned.str.replace(r"^\((.*)\)$", r"\1", regex=True)
        body = body.where(~paren, "-" + body)
        parsed = pd.to_numeric(body, errors="coerce").replace([np.inf, -np.inf], np.nan)
        parsed_arr = parsed.to_numpy(dtype="float64")
        parsed_ok = np.isfinite(parsed_arr)

        final = np.where(direct_ok, direct_arr, np.where(parsed_ok & ~is_missing, parsed_arr, 0.0))

        needs_repair = ~direct_ok
        miss_idx = np.flatnonzero(needs_repair & is_missing)
        fix_idx = np.flatnonzero(needs_repair & ~is_missing & parsed_ok)
        bad_idx = np.flatnonzero(needs_repair & ~is_missing & ~parsed_ok)

        for i in miss_idx:
            log.append(f"{id_arr[i]} {yr}: missing/blank value ({col.iloc[i]!r}) imputed as 0.0.")
        for i in fix_idx:
            log.append(f"{id_arr[i]} {yr}: reformatted {col.iloc[i]!r} -> {final[i]:,.2f}.")
        for i in bad_idx:
            log.append(f"{id_arr[i]} {yr}: unparseable value {col.iloc[i]!r} imputed as 0.0.")

        repaired += int(needs_repair.sum())
        df[yr] = final.astype("float64")

    # ---- Metadata fill + missing schema rows -----------------------------------------
    for meta, lookup in (("Line_Item_Name", SCHEMA_NAMES), ("Category", SCHEMA_CATEGORIES)):
        blank = df[meta].isna() | (df[meta].astype(str).str.strip() == "")
        df[meta] = df[meta].astype(object).where(~blank, df["Line_ID"].map(lookup))
        df[meta] = df[meta].astype(str).str.strip()

    absent = [k for k in REQUIRED_IDS if k not in set(df["Line_ID"].tolist())]
    if absent:
        add = pd.DataFrame(
            {
                "Line_ID": absent,
                "Line_Item_Name": [SCHEMA_NAMES[k] for k in absent],
                "Category": [SCHEMA_CATEGORIES[k] for k in absent],
                **{yr: np.zeros(len(absent), dtype="float64") for yr in ylist},
            }
        )
        df = pd.concat([df, add], ignore_index=True)
        repaired += len(absent) * (1 + len(ylist))
        for k in absent:
            log.append(f"Line_ID '{k}' absent from input: inserted with 0.0 for all fiscal years.")

    clean = df.set_index("Line_ID").loc[REQUIRED_IDS].copy()
    clean.index.name = "Line_ID"
    for yr in ylist:
        clean[yr] = clean[yr].astype("float64")

    total_cells = len(REQUIRED_IDS) * (1 + len(ylist))
    audit = {
        "total_cells": int(total_cells),
        "cells_repaired": int(repaired),
        "repair_pct": round(float(repaired) / total_cells * 100.0, 2),
        "repair_log": log,
        "years": list(ylist),
    }
    return clean, audit


def _extract_inputs(clean_df: pd.DataFrame, ylist: list[str]) -> pd.DataFrame:
    df = clean_df.copy()
    if "Line_ID" in df.columns:
        df = df.set_index("Line_ID")
    df.index = df.index.astype(str).str.strip().str.upper()
    df = df[~df.index.duplicated(keep="first")]
    missing_ids = [k for k in REQUIRED_IDS if k not in df.index]
    if missing_ids:
        raise ValueError(f"clean_df is missing required Line_IDs: {missing_ids}")
    missing_years = [y for y in ylist if y not in df.columns]
    if missing_years:
        raise ValueError(f"clean_df is missing fiscal-year columns: {missing_years}")
    num = df.loc[REQUIRED_IDS, ylist].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return num.astype("float64")


def _as_adj(attr_adj: Sequence[float] | None, n: int) -> np.ndarray:
    if attr_adj is None:
        return np.zeros(n, dtype="float64")
    arr = np.nan_to_num(np.asarray(list(attr_adj), dtype="float64"), nan=0.0)
    if arr.shape[0] != n:
        raise ValueError(f"attr_adj has {arr.shape[0]} values but the statement has {n} years.")
    return arr


# --------------------------------------------------------------------------------------
# 2. Anatomy, VAS and KPIs
# --------------------------------------------------------------------------------------
def compute_corporate_anatomy_and_vas(
    clean_df: pd.DataFrame, years: Sequence[str] | None = None, attr_adj: Sequence[float] | None = None
) -> dict:
    """P&L ladder, common-size ₹100 receipt, value-added statement and KPIs for every year in `years`.

    attr_adj: optional per-year gap = (PBT - Tax) - reported profit attributable to shareholders (minority interest,
    associates and other items). When given, ROE uses attributable profit while tax and retained earnings stay as reported.
    """
    ylist = _resolve_years(clean_df, years)
    n = len(ylist)
    inputs = _extract_inputs(clean_df, ylist)
    x = {k: inputs.loc[k, ylist].to_numpy(dtype="float64") for k in REQUIRED_IDS}
    adj = _as_adj(attr_adj, n)

    lad = _ladder(
        x["REV_OPS"], x["REV_OTH"], x["COGS_MAT"], x["OPEX_EXT"], x["EMP_COST"],
        x["DEP_AMORT"], x["FIN_COST"], x["TAX_EXP"], x["DIV_PAID"],
    )
    ti, gva, ebitda, ebit, pbt, pat, re_ = (
        lad["Total_Income"], lad["GVA"], lad["EBITDA"], lad["EBIT"], lad["PBT"],
        lad["PAT"], lad["Retained_Earnings"],
    )
    pat_attr = pat - adj

    pnl = pd.DataFrame(
        {
            "Revenue_from_Operations": x["REV_OPS"],
            "Other_Income": x["REV_OTH"],
            "Total_Income": ti,
            "Bought_In_Costs": lad["Bought_In_Costs"],
            "GVA": gva,
            "Employee_Cost": x["EMP_COST"],
            "EBITDA": ebitda,
            "Depreciation_Amortization": x["DEP_AMORT"],
            "EBIT": ebit,
            "Finance_Costs": x["FIN_COST"],
            "PBT": pbt,
            "Tax_Expense": x["TAX_EXP"],
            "PAT": pat,
            "Minority_Associates_Adj": adj,
            "PAT_Attributable": pat_attr,
            "Dividends_Paid": x["DIV_PAID"],
            "Retained_Earnings": re_,
            "NVA": lad["NVA"],
        },
        index=ylist,
    ).T

    # ---- Common-size ₹100 receipt ----------------------------------------------------
    receipt = _receipt_frames(
        _receipt_components(
            x["COGS_MAT"], x["OPEX_EXT"], x["EMP_COST"], x["DEP_AMORT"],
            x["FIN_COST"], x["TAX_EXP"], x["DIV_PAID"], re_,
        ),
        ti,
        ylist,
    )

    # ---- Value-Added Statement -------------------------------------------------------
    stake_mat = np.vstack([x["EMP_COST"], x["FIN_COST"], x["TAX_EXP"], x["DIV_PAID"], re_ + x["DEP_AMORT"]])
    stake_sum = stake_mat.sum(axis=0)
    residual = gva - stake_sum
    closure_by_year = np.abs(residual) < 1e-4
    pct_mat = _safe_div(stake_mat, gva) * 100.0

    vas_abs = pd.DataFrame(stake_mat, index=STAKEHOLDER_LABELS, columns=ylist)
    vas_pct = pd.DataFrame(pct_mat, index=STAKEHOLDER_LABELS, columns=ylist)
    vas_long = pd.DataFrame(
        {
            "Year": np.tile(ylist, len(STAKEHOLDER_LABELS)),
            "Stakeholder": np.repeat(STAKEHOLDER_LABELS, len(ylist)),
            "Amount_Cr": vas_abs.to_numpy().ravel(),
            "Pct_of_GVA": vas_pct.to_numpy().ravel(),
        }
    )

    # ---- Strategic & credit KPIs -----------------------------------------------------
    debt, equity, fin, hc, emp = x["TOTAL_DEBT"], x["TOTAL_EQUITY"], x["FIN_COST"], x["HEADCOUNT"], x["EMP_COST"]
    capital_employed = debt + equity
    roce = _safe_div(ebit, capital_employed) * 100.0
    cost_of_debt = np.where(debt > 0, fin / np.where(debt > 0, debt, 1.0) * 100.0, 0.0)
    icr = np.where(fin > 0, ebit / np.where(fin > 0, fin, 1.0), 999.0)
    spread = roce - cost_of_debt
    debt_to_ebitda = np.where(ebitda > 0, debt / np.where(ebitda > 0, ebitda, 1.0), np.where(debt > 0, 999.0, 0.0))
    va_per_emp = np.where(hc > 0, gva * 100.0 / np.where(hc > 0, hc, 1.0), np.nan)
    cost_per_emp = np.where((hc > 0) & (emp > 0), emp * 100.0 / np.where(hc > 0, hc, 1.0), np.nan)
    hc_roi = np.where(emp > 0, x["REV_OPS"] / np.where(emp > 0, emp, 1.0), np.nan)

    kpis = pd.DataFrame(
        {
            "Bought_In_Costs_Pct": _safe_div(lad["Bought_In_Costs"], ti) * 100.0,
            "Labor_Share_of_GVA_Pct": _safe_div(emp, gva) * 100.0,
            "GVA_Margin_Pct": _safe_div(gva, ti) * 100.0,
            "EBITDA_Margin_Pct": _safe_div(ebitda, ti) * 100.0,
            "PAT_Margin_Pct": _safe_div(pat, ti) * 100.0,
            "Human_Capital_ROI": hc_roi,
            "Value_Added_Per_Emp_Lakhs": va_per_emp,
            "Avg_Cost_Per_Emp_Lakhs": cost_per_emp,
            "Capital_Employed": capital_employed,
            "ROCE_Pct": roce,
            "ROE_Pct": _safe_div(pat_attr, equity) * 100.0,
            "Implied_Cost_of_Debt_Pct": cost_of_debt,
            "Economic_Spread_Pct": spread,
            "EVA_Spread_Proxy_Cr": spread / 100.0 * capital_employed,
            "Interest_Coverage_Ratio": icr,
            "Debt_to_EBITDA": debt_to_ebitda,
            "Effective_Tax_Rate_Pct": _safe_div(x["TAX_EXP"], pbt) * 100.0,
            "Value_Retention_Ratio_Pct": _safe_div(re_ + x["DEP_AMORT"], gva) * 100.0,
        },
        index=ylist,
    ).T

    periods = max(n - 1, 0)
    cagr = {
        "Revenue_CAGR_Pct": _cagr_pct(x["REV_OPS"][0], x["REV_OPS"][-1], periods),
        "Total_Income_CAGR_Pct": _cagr_pct(ti[0], ti[-1], periods),
        "GVA_CAGR_Pct": _cagr_pct(gva[0], gva[-1], periods),
        "EMP_COST_CAGR_Pct": _cagr_pct(emp[0], emp[-1], periods),
        "PAT_CAGR_Pct": _cagr_pct(pat[0], pat[-1], periods),
        "PAT_Attr_CAGR_Pct": _cagr_pct(pat_attr[0], pat_attr[-1], periods),
    }

    return {
        "years": list(ylist),
        "n_years": n,
        "inputs": inputs,
        "pnl": pnl,
        "pat_attr": pd.Series(pat_attr, index=ylist),
        "attr_adj": adj,
        "common_size": receipt["rupees"],
        "common_size_exact": receipt["exact"],
        "common_size_paise": receipt["paise"],
        "common_size_long": receipt["long"],
        "receipt_check": {
            "exact_sum_by_year": receipt["sum_exact"],
            "rounded_sum_by_year": receipt["sum_rounded"],
            "ok_by_year": receipt["ok_by_period"],
            "all_ok": receipt["all_ok"],
        },
        "vas_abs": vas_abs,
        "vas_pct": vas_pct,
        "vas_long": vas_long,
        "vas_residual": dict(zip(ylist, residual.astype(float).tolist())),
        "vas_closure_by_year": dict(zip(ylist, [bool(v) for v in closure_by_year])),
        "vas_closure_check": bool(np.all(closure_by_year)),
        "kpis": kpis,
        "cagr": cagr,
    }


# --------------------------------------------------------------------------------------
# 3. Deterministic rule-based diagnostics
# --------------------------------------------------------------------------------------
def _fmt_cr(v: float) -> str:
    return f"₹{v:,.0f} Cr"


def _xfmt(v: float) -> str:
    return "n/a (no interest burden)" if v >= 999.0 else f"{v:.1f}x"


def generate_deterministic_diagnostics(results: dict) -> list[dict]:
    """Four executive cards (title, badge_text, severity, narrative). severity is one of positive / warning / danger / info."""
    k, inp, pnl, cagr = results["kpis"], results["inputs"], results["pnl"], results["cagr"]
    ys = results["years"]
    first, last, n = ys[0], ys[-1], len(ys)

    def kv(name: str, yr: str | None = None) -> float:
        return float(k.loc[name, yr or last])

    cards: list[dict] = []
    emp_last = float(inp.loc["EMP_COST", last])
    emp_rep = emp_last > 0

    # ---- 1) Value Creation Archetype -------------------------------------------------
    bic, lab, gva_m = kv("Bought_In_Costs_Pct"), kv("Labor_Share_of_GVA_Pct"), kv("GVA_Margin_Pct")
    gva_last = float(pnl.loc["GVA", last])
    lab_txt = f" Labor takes {lab:.1f}% of that GVA." if emp_rep else ""
    if gva_last <= 0:
        title, badge, sev = "Value Creation Archetype", "Value Destruction", "danger"
        text = (
            f"{last} Gross Value Added is {_fmt_cr(gva_last)}: bought-in costs absorb {bic:.1f}% of total income, "
            "so the enterprise creates no distributable value after paying suppliers."
        )
    elif bic >= 85.0:
        title, badge, sev = "Value Creation Archetype", "Thin-Spread Platform", "warning"
        text = (
            f"Bought-in costs absorb {bic:.1f}% of {last} total income, leaving a GVA margin of only {gva_m:.1f}%.{lab_txt} "
            "This is a high-throughput, thin-spread model where small leakages in vendor, logistics or promotion spend "
            "move profit disproportionately."
        )
    elif bic >= 70.0:
        title, badge, sev = "Value Creation Archetype", "Supply-Chain Intensive", "warning"
        text = (
            f"Bought-in costs consume {bic:.1f}% of {last} total income (GVA margin {gva_m:.1f}%)."
            + (f" The workforce captures {lab:.1f}% of GVA." if emp_rep else "")
            + " Value is created through procurement, scale and asset utilization, so margins are most exposed to "
            "raw-material and freight inflation."
        )
    elif not emp_rep:
        title, badge, sev = "Value Creation Archetype", "Workforce Cost Not Reported", "info"
        text = (
            f"Bought-in costs are {bic:.1f}% of {last} total income (GVA margin {gva_m:.1f}%). Employee cost is not reported in the "
            "source data, so the workforce share of value added cannot be assessed and the archetype cannot be classified further."
        )
    elif lab >= 50.0:
        title, badge = "Value Creation Archetype", "Human-Capital Intensive"
        sev = "warning" if lab >= 75.0 else "info"
        text = (
            f"The workforce takes {lab:.1f}% of {last} GVA while bought-in costs are only {bic:.1f}% of income "
            f"(GVA margin {gva_m:.1f}%). Value is created by people, so wage inflation, attrition and "
            "utilization are the primary margin risks."
        )
    elif bic < 70.0 and lab < 35.0:
        title, badge, sev = "Value Creation Archetype", "Brand / Franchise Compounder", "positive"
        text = (
            f"Bought-in costs consume {bic:.1f}% of {last} income, leaving a {gva_m:.1f}% GVA margin, and the workforce "
            f"takes only {lab:.1f}% of that pool. Most value accrues to the state, capital providers and reinvestment."
        )
    else:
        title, badge, sev = "Value Creation Archetype", "Balanced Value Chain", "info"
        text = (
            f"Bought-in costs are {bic:.1f}% of {last} income (GVA margin {gva_m:.1f}%) and labor share of GVA is "
            f"{lab:.1f}%, a balanced mix of supplier, workforce and capital contribution."
        )
    cards.append({"title": title, "badge_text": badge, "severity": sev, "narrative": text})

    # ---- 2) Labor vs Capital Drift ---------------------------------------------------
    emp_first = float(inp.loc["EMP_COST", first])
    pat_first, pat_last = float(pnl.loc["PAT", first]), float(pnl.loc["PAT", last])
    lab_first = kv("Labor_Share_of_GVA_Pct", first)
    title = f"{n}-Year Labor vs. Capital Drift"
    span = f"{first} to {last}"
    if n < 2:
        badge, sev = "Insufficient History", "info"
        text = "At least two annual periods are needed to compare labor cost growth with profit growth."
    elif emp_first <= 0 or emp_last <= 0:
        badge, sev = "Employee Cost Not Reported", "info"
        text = (f"Employee cost is not reported for {first} or {last} in the source data, so labor-versus-profit drift "
                "cannot be computed.")
    elif pat_first > 0 and pat_last > 0:
        emp_g, pat_g = cagr["EMP_COST_CAGR_Pct"], cagr["PAT_CAGR_Pct"]
        gap = emp_g - pat_g
        base = (
            f"Employee cost compounded at {emp_g:.1f}% a year versus {pat_g:.1f}% for PAT ({span}); "
            f"labor share of GVA moved from {lab_first:.1f}% to {lab:.1f}%."
        )
        if gap > 15.0:
            badge, sev = "Labor Outpacing Profit", "danger"
            text = base + " Payroll is growing far faster than bottom-line profit, a sharp margin squeeze."
        elif gap > 5.0:
            badge, sev = "Wage Drift Squeezing Profit", "warning"
            text = base + " Payroll growth is running ahead of profit growth and is eroding operating leverage."
        elif gap < -5.0:
            badge, sev = "Operating Leverage Working", "positive"
            text = base + " Profit is growing faster than payroll, so scale is converting into shareholder value."
        else:
            badge, sev = "Balanced Drift", "info"
            text = base + " Labor and capital returns are growing in step."
    elif pat_first <= 0 < pat_last:
        emp_g = cagr["EMP_COST_CAGR_Pct"]
        badge, sev = "Profit Turnaround", "positive"
        text = (
            f"PAT swung from {_fmt_cr(pat_first)} in {first} to {_fmt_cr(pat_last)} in {last} while employee cost compounded at "
            f"{emp_g:.1f}% a year. Labor share of GVA moved from {lab_first:.1f}% to {lab:.1f}%, "
            "showing scale is being absorbed into profit."
        )
    elif pat_first > 0 >= pat_last:
        badge, sev = "Profit Erosion", "danger"
        text = (
            f"PAT fell from {_fmt_cr(pat_first)} in {first} to {_fmt_cr(pat_last)} in {last} while employee cost moved from "
            f"{_fmt_cr(emp_first)} to {_fmt_cr(emp_last)}: labor cost growth has not been backed by profit."
        )
    elif pat_last > pat_first:
        badge, sev = "Losses Narrowing", "warning"
        text = (
            f"PAT improved from {_fmt_cr(pat_first)} to {_fmt_cr(pat_last)} but remains non-positive, "
            f"with employee cost at {_fmt_cr(emp_last)} ({lab:.1f}% of GVA)."
        )
    else:
        badge, sev = "Persistent Losses", "danger"
        text = (
            f"PAT stands at {_fmt_cr(pat_last)} in {last} versus {_fmt_cr(pat_first)} in {first} with employee cost at "
            f"{_fmt_cr(emp_last)}; the cost base is not being covered by value added."
        )
    cards.append({"title": title, "badge_text": badge, "severity": sev, "narrative": text})

    # ---- 3) Capital Efficiency & Economic Spread -------------------------------------
    roce, cod = kv("ROCE_Pct"), kv("Implied_Cost_of_Debt_Pct")
    roce_first, roe = kv("ROCE_Pct", first), kv("ROE_Pct")
    debt_last = float(inp.loc["TOTAL_DEBT", last])
    ce_last = kv("Capital_Employed")
    debt_share = debt_last / ce_last * 100.0 if ce_last > 0 else 0.0
    spread = roce - cod
    title = "Capital Efficiency & Economic Spread"
    trend = f"ROCE moved from {roce_first:.1f}% in {first} to {roce:.1f}% in {last} (ROE {roe:.1f}%)."
    if debt_last <= 0 or debt_share < 5.0:
        if roce >= 15.0:
            badge, sev = "Equity-Funded Capital Engine", "positive"
            text = (
                f"Debt is only {debt_share:.1f}% of capital employed, so returns are earned on owners' capital. "
                f"{trend} The business earns well above any plausible cost of capital without leverage."
            )
        elif roce >= 8.0:
            badge, sev = "Modest Equity-Funded Returns", "info"
            text = f"Debt is only {debt_share:.1f}% of capital employed. {trend} Returns are adequate but not exceptional."
        else:
            badge, sev = "Weak Returns on Idle Capital", "warning"
            text = f"Debt is only {debt_share:.1f}% of capital employed, yet {trend} Capital is under-earning."
    elif spread >= 8.0:
        badge, sev = "Value-Accretive Leverage", "positive"
        text = (
            f"ROCE of {roce:.1f}% exceeds the implied cost of debt of {cod:.1f}% by {spread:.1f} points. {trend} "
            "Borrowed capital is earning well above its price."
        )
    elif spread >= 3.0:
        badge, sev = "Positive Spread", "info"
        text = (
            f"ROCE of {roce:.1f}% clears the implied cost of debt of {cod:.1f}% by {spread:.1f} points. {trend} "
            "The spread is positive but leaves limited cushion against rate or margin shocks."
        )
    elif spread >= 0.0:
        badge, sev = "Razor-Thin Spread", "warning"
        text = (
            f"ROCE of {roce:.1f}% barely exceeds the implied cost of debt of {cod:.1f}% ({spread:.1f} points). {trend} "
            "Leverage adds almost no value for shareholders."
        )
    else:
        badge, sev = "Negative Spread", "danger"
        text = (
            f"ROCE of {roce:.1f}% is below the implied cost of debt of {cod:.1f}% (spread {spread:.1f} points). {trend} "
            "Every rupee borrowed currently destroys value until operating returns exceed the interest rate."
        )
    cards.append({"title": title, "badge_text": badge, "severity": sev, "narrative": text})

    # ---- 4) Credit & Solvency Cushion ------------------------------------------------
    icr, d_ebitda = kv("Interest_Coverage_Ratio"), kv("Debt_to_EBITDA")
    ebitda_last = float(pnl.loc["EBITDA", last])
    fin_last = float(inp.loc["FIN_COST", last])
    title = "Credit & Solvency Cushion"
    metrics = f"Interest coverage is {_xfmt(icr)} and Debt/EBITDA is {d_ebitda:.2f}x on {_fmt_cr(debt_last)} of borrowings."
    if debt_last <= 0 and fin_last <= 0:
        badge, sev = "Debt-Free Fortress", "positive"
        text = f"{last} shows no borrowings and no finance cost, so there is no creditor claim on operating cash flow."
    elif ebitda_last <= 0:
        badge, sev = "No Cash Earnings to Service Debt", "danger"
        text = f"{last} EBITDA is {_fmt_cr(ebitda_last)} against {_fmt_cr(debt_last)} of borrowings. {metrics} Debt service depends on external funding."
    elif d_ebitda < 0.5 and icr >= 20.0:
        badge, sev = "Fortress Balance Sheet", "positive"
        text = f"{metrics} Debt could be repaid from under six months of EBITDA; solvency is not a constraint."
    elif icr < 1.5 or d_ebitda > 4.0:
        badge, sev = "Thin Debt-Service Cushion", "danger"
        text = f"{metrics} Operating earnings leave little headroom: a modest margin or rate shock could breach covenants."
    elif icr < 3.0 or d_ebitda > 3.0:
        badge, sev = "Watchlist Leverage", "warning"
        text = f"{metrics} Coverage is serviceable but below the comfort zone of 3x, so rate or margin shocks matter."
    elif icr >= 6.0 and d_ebitda <= 2.0:
        badge, sev = "Strong Credit Cushion", "positive"
        text = f"{metrics} Earnings cover interest comfortably and leverage is conservative."
    else:
        badge, sev = "Adequate Credit Cushion", "info"
        text = f"{metrics} Coverage and leverage are within normal investment-grade ranges."
    cards.append({"title": title, "badge_text": badge, "severity": sev, "narrative": text})

    return cards


# --------------------------------------------------------------------------------------
# 4. Macro & inflation pass-through stress test (applied to the LATEST year)
# --------------------------------------------------------------------------------------
def _scenario_metrics(lad, rev_ops, fin, tax, equity, adj) -> dict[str, float]:
    ti = lad["Total_Income"]
    pat_attr = lad["PAT"] - adj
    raw = {
        "Revenue_from_Operations": rev_ops,
        "Total_Income": ti,
        "Bought_In_Costs": lad["Bought_In_Costs"],
        "GVA": lad["GVA"],
        "EBITDA": lad["EBITDA"],
        "EBIT": lad["EBIT"],
        "PBT": lad["PBT"],
        "Tax_Expense": tax,
        "PAT": lad["PAT"],
        "PAT_Attributable": pat_attr,
        "Retained_Earnings": lad["Retained_Earnings"],
        "GVA_Margin_Pct": _safe_div(lad["GVA"], ti) * 100.0,
        "EBITDA_Margin_Pct": _safe_div(lad["EBITDA"], ti) * 100.0,
        "PAT_Margin_Pct": _safe_div(lad["PAT"], ti) * 100.0,
        "ROE_Pct": _safe_div(pat_attr, equity) * 100.0,
        "Interest_Coverage_Ratio": _safe_div(lad["EBIT"], fin, fill=999.0),
    }
    return {name: float(np.asarray(v, dtype="float64").reshape(-1)[0]) for name, v in raw.items()}


def simulate_margin_shock(
    results: dict,
    mat_inflation_pct: float,
    wage_hike_pct: float,
    rate_shock_bps: float,
    price_passthrough_pct: float,
) -> dict:
    """One-period static what-if on the latest year. The minority/associates adjustment is held at its latest-year value."""
    last = results["years"][-1]
    base = results["inputs"][last]
    adj = np.array([float(results["attr_adj"][-1])], dtype="float64")

    def a(name: str) -> np.ndarray:
        return np.array([float(base[name])], dtype="float64")

    rev_ops, rev_oth, cogs, opex = a("REV_OPS"), a("REV_OTH"), a("COGS_MAT"), a("OPEX_EXT")
    emp, dep, fin, tax = a("EMP_COST"), a("DEP_AMORT"), a("FIN_COST"), a("TAX_EXP")
    div, debt, equity = a("DIV_PAID"), a("TOTAL_DEBT"), a("TOTAL_EQUITY")

    base_tax_rate = float(results["kpis"].loc["Effective_Tax_Rate_Pct", last]) / 100.0

    delta_cogs = cogs * (float(mat_inflation_pct) / 100.0)
    delta_emp = emp * (float(wage_hike_pct) / 100.0)
    delta_fin = debt * (float(rate_shock_bps) / 10000.0)
    total_cost_inflation = delta_cogs + delta_emp + delta_fin
    delta_rev = total_cost_inflation * (float(price_passthrough_pct) / 100.0)

    base_lad = _ladder(rev_ops, rev_oth, cogs, opex, emp, dep, fin, tax, div)

    sim_rev_ops = rev_ops + delta_rev
    sim_cogs, sim_emp, sim_fin = cogs + delta_cogs, emp + delta_emp, fin + delta_fin
    pre_tax = _ladder(sim_rev_ops, rev_oth, sim_cogs, opex, sim_emp, dep, sim_fin, np.zeros(1), div)
    sim_tax = np.where(pre_tax["PBT"] > 0, pre_tax["PBT"] * base_tax_rate, 0.0)
    sim_lad = _ladder(sim_rev_ops, rev_oth, sim_cogs, opex, sim_emp, dep, sim_fin, sim_tax, div)

    base_m = _scenario_metrics(base_lad, rev_ops, fin, tax, equity, adj)
    sim_m = _scenario_metrics(sim_lad, sim_rev_ops, sim_fin, sim_tax, equity, adj)

    names = list(base_m.keys())
    b_vals = np.array([base_m[nm] for nm in names], dtype="float64")
    s_vals = np.array([sim_m[nm] for nm in names], dtype="float64")
    change = s_vals - b_vals
    is_money = np.array([nm in _MONEY_METRICS for nm in names])
    change_pct = np.where(is_money, _safe_div(change, np.abs(b_vals)) * 100.0, np.nan)
    comparison = pd.DataFrame(
        {"Baseline": b_vals, "Simulated": s_vals, "Change": change, "Change_Pct": change_pct},
        index=names,
    )

    def pair(b: np.ndarray, s: np.ndarray) -> np.ndarray:
        return np.concatenate([b, s])

    receipt = _receipt_frames(
        _receipt_components(
            pair(cogs, sim_cogs), pair(opex, opex), pair(emp, sim_emp), pair(dep, dep),
            pair(fin, sim_fin), pair(tax, sim_tax), pair(div, div),
            pair(base_lad["Retained_Earnings"], sim_lad["Retained_Earnings"]),
        ),
        pair(base_lad["Total_Income"], sim_lad["Total_Income"]),
        ["Baseline", "Simulated"],
    )
    receipt_df = receipt["rupees"].copy()
    receipt_df["Change"] = receipt_df["Simulated"] - receipt_df["Baseline"]

    sim_stake_sum = float(
        (sim_emp + sim_fin + sim_tax + div + (sim_lad["Retained_Earnings"] + dep)).reshape(-1)[0]
    )
    sim_gva = float(sim_lad["GVA"].reshape(-1)[0])
    breakeven = float(_safe_div(total_cost_inflation, rev_ops).reshape(-1)[0] * 100.0)

    return {
        "base_year": last,
        "assumptions": {
            "mat_inflation_pct": float(mat_inflation_pct),
            "wage_hike_pct": float(wage_hike_pct),
            "rate_shock_bps": float(rate_shock_bps),
            "price_passthrough_pct": float(price_passthrough_pct),
            "dividend_policy": "Held constant at the latest-year baseline; any shortfall is drawn from retained earnings.",
            "baseline_effective_tax_rate_pct": base_tax_rate * 100.0,
        },
        "shocks": {
            "Delta_COGS": float(delta_cogs[0]),
            "Delta_Emp": float(delta_emp[0]),
            "Delta_Fin": float(delta_fin[0]),
            "Total_Cost_Inflation": float(total_cost_inflation[0]),
            "Delta_Rev": float(delta_rev[0]),
            "Unrecovered_Cost": float(total_cost_inflation[0] - delta_rev[0]),
        },
        "Total_Cost_Inflation": float(total_cost_inflation[0]),
        "Delta_Rev": float(delta_rev[0]),
        "Breakeven_Price_Hike_Pct": breakeven,
        "baseline": base_m,
        "simulated": sim_m,
        "comparison": comparison,
        "receipt": receipt_df,
        "receipt_paise": receipt["paise"],
        "receipt_check": {
            "baseline_sum": receipt["sum_rounded"]["Baseline"],
            "simulated_sum": receipt["sum_rounded"]["Simulated"],
            "all_ok": receipt["all_ok"],
        },
        "vas_closure_check": bool(abs(sim_gva - sim_stake_sum) < 1e-4),
    }