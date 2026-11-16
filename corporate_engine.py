"""CORP-TRACE core engine: hygiene, common-size anatomy, VAS, KPIs, diagnostics, stress-test.
Pure Python / Pandas / NumPy. Zero LLMs, zero external API calls."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

YEARS: list[str] = ["FY24", "FY25", "FY26"]

REQUIRED_IDS: list[str] = [
    "REV_OPS", "REV_OTH", "COGS_MAT", "OPEX_EXT", "EMP_COST", "FIN_COST",
    "DEP_AMORT", "TAX_EXP", "DIV_PAID", "TOTAL_DEBT", "TOTAL_EQUITY", "HEADCOUNT",
]

SCHEMA_NAMES: dict[str, str] = {
    "REV_OPS": "Revenue from Operations",
    "REV_OTH": "Other Income",
    "COGS_MAT": "Cost of Materials & Stock-in-Trade",
    "OPEX_EXT": "Other Operating Expenses (Freight, Power, Marketing, Vendors)",
    "EMP_COST": "Employee Benefit Expenses",
    "FIN_COST": "Finance Costs (Interest Expense)",
    "DEP_AMORT": "Depreciation & Amortization",
    "TAX_EXP": "Total Tax Expense",
    "DIV_PAID": "Equity Dividends Paid",
    "TOTAL_DEBT": "Total Borrowings (Long-Term + Short-Term Debt)",
    "TOTAL_EQUITY": "Total Shareholders' Equity (Net Worth)",
    "HEADCOUNT": "Total Permanent Employees (Integer count)",
}

SCHEMA_CATEGORIES: dict[str, str] = {
    "REV_OPS": "Income", "REV_OTH": "Income", "COGS_MAT": "Bought-In Cost",
    "OPEX_EXT": "Bought-In Cost", "EMP_COST": "Workforce", "FIN_COST": "Lenders",
    "DEP_AMORT": "Capital Consumption", "TAX_EXP": "Government", "DIV_PAID": "Shareholders",
    "TOTAL_DEBT": "Balance Sheet", "TOTAL_EQUITY": "Balance Sheet", "HEADCOUNT": "Workforce Disclosure",
}

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
    "PBT", "Tax_Expense", "PAT", "Retained_Earnings",
})


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


def _cagr_pct(start: float, end: float, periods: int = 2) -> float:
    """(end/start)**(1/periods) - 1 in %, NaN when either endpoint is non-positive."""
    if start > 0 and end > 0:
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
def sanitize_statement_df(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    if not isinstance(raw_df, pd.DataFrame):
        raise TypeError("raw_df must be a pandas DataFrame.")

    df = raw_df.copy()
    if "Line_ID" not in [str(c).strip() for c in df.columns] and str(df.index.name).strip() == "Line_ID":
        df = df.reset_index()

    canon = {c.lower(): c for c in ["Line_ID", "Line_Item_Name", "Category"] + YEARS}
    df.columns = [canon.get(str(c).strip().lower().replace(" ", "_"), str(c).strip()) for c in df.columns]

    missing_cols = [c for c in ["Line_ID"] + YEARS if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Input is missing required columns: {missing_cols}")
    for meta in ("Line_Item_Name", "Category"):
        if meta not in df.columns:
            df[meta] = np.nan
    df = df[["Line_ID", "Line_Item_Name", "Category"] + YEARS].reset_index(drop=True)

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
    for yr in YEARS:
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
                **{yr: np.zeros(len(absent), dtype="float64") for yr in YEARS},
            }
        )
        df = pd.concat([df, add], ignore_index=True)
        repaired += len(absent) * (1 + len(YEARS))
        for k in absent:
            log.append(f"Line_ID '{k}' absent from input: inserted with 0.0 for all fiscal years.")

    clean = df.set_index("Line_ID").loc[REQUIRED_IDS]
    clean.index.name = "Line_ID"
    for yr in YEARS:
        clean[yr] = clean[yr].astype("float64")

    total_cells = len(REQUIRED_IDS) * (1 + len(YEARS))
    audit = {
        "total_cells": int(total_cells),
        "cells_repaired": int(repaired),
        "repair_pct": round(float(repaired) / total_cells * 100.0, 2),
        "repair_log": log,
    }
    return clean, audit


def _extract_inputs(clean_df: pd.DataFrame) -> pd.DataFrame:
    df = clean_df.copy()
    if "Line_ID" in df.columns:
        df = df.set_index("Line_ID")
    df.index = df.index.astype(str).str.strip().str.upper()
    df = df[~df.index.duplicated(keep="first")]
    missing_ids = [k for k in REQUIRED_IDS if k not in df.index]
    if missing_ids:
        raise ValueError(f"clean_df is missing required Line_IDs: {missing_ids}")
    missing_years = [y for y in YEARS if y not in df.columns]
    if missing_years:
        raise ValueError(f"clean_df is missing fiscal-year columns: {missing_years}")
    num = df.loc[REQUIRED_IDS, YEARS].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return num.astype("float64")


# --------------------------------------------------------------------------------------
# 2. Anatomy, VAS and KPIs
# --------------------------------------------------------------------------------------
def compute_corporate_anatomy_and_vas(clean_df: pd.DataFrame) -> dict:
    inputs = _extract_inputs(clean_df)
    x = {k: inputs.loc[k, YEARS].to_numpy(dtype="float64") for k in REQUIRED_IDS}

    lad = _ladder(
        x["REV_OPS"], x["REV_OTH"], x["COGS_MAT"], x["OPEX_EXT"], x["EMP_COST"],
        x["DEP_AMORT"], x["FIN_COST"], x["TAX_EXP"], x["DIV_PAID"],
    )
    ti, gva, ebitda, ebit, pbt, pat, re_ = (
        lad["Total_Income"], lad["GVA"], lad["EBITDA"], lad["EBIT"], lad["PBT"],
        lad["PAT"], lad["Retained_Earnings"],
    )

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
            "Dividends_Paid": x["DIV_PAID"],
            "Retained_Earnings": re_,
            "NVA": lad["NVA"],
        },
        index=YEARS,
    ).T

    # ---- Common-size ₹100 receipt ----------------------------------------------------
    receipt = _receipt_frames(
        _receipt_components(
            x["COGS_MAT"], x["OPEX_EXT"], x["EMP_COST"], x["DEP_AMORT"],
            x["FIN_COST"], x["TAX_EXP"], x["DIV_PAID"], re_,
        ),
        ti,
        YEARS,
    )

    # ---- Value-Added Statement -------------------------------------------------------
    stake_mat = np.vstack([x["EMP_COST"], x["FIN_COST"], x["TAX_EXP"], x["DIV_PAID"], re_ + x["DEP_AMORT"]])
    stake_sum = stake_mat.sum(axis=0)
    residual = gva - stake_sum
    closure_by_year = np.abs(residual) < 1e-4
    pct_mat = _safe_div(stake_mat, gva) * 100.0

    vas_abs = pd.DataFrame(stake_mat, index=STAKEHOLDER_LABELS, columns=YEARS)
    vas_pct = pd.DataFrame(pct_mat, index=STAKEHOLDER_LABELS, columns=YEARS)
    vas_long = pd.DataFrame(
        {
            "Year": np.tile(YEARS, len(STAKEHOLDER_LABELS)),
            "Stakeholder": np.repeat(STAKEHOLDER_LABELS, len(YEARS)),
            "Amount_Cr": vas_abs.to_numpy().ravel(),
            "Pct_of_GVA": vas_pct.to_numpy().ravel(),
        }
    )

    # ---- Strategic & credit KPIs -----------------------------------------------------
    debt, equity, fin, hc = x["TOTAL_DEBT"], x["TOTAL_EQUITY"], x["FIN_COST"], x["HEADCOUNT"]
    capital_employed = debt + equity
    roce = _safe_div(ebit, capital_employed) * 100.0
    cost_of_debt = np.where(debt > 0, fin / np.where(debt > 0, debt, 1.0) * 100.0, 0.0)
    icr = np.where(fin > 0, ebit / np.where(fin > 0, fin, 1.0), 999.0)
    spread = roce - cost_of_debt
    debt_to_ebitda = np.where(ebitda > 0, debt / np.where(ebitda > 0, ebitda, 1.0), np.where(debt > 0, 999.0, 0.0))

    kpis = pd.DataFrame(
        {
            "Bought_In_Costs_Pct": _safe_div(lad["Bought_In_Costs"], ti) * 100.0,
            "Labor_Share_of_GVA_Pct": _safe_div(x["EMP_COST"], gva) * 100.0,
            "GVA_Margin_Pct": _safe_div(gva, ti) * 100.0,
            "EBITDA_Margin_Pct": _safe_div(ebitda, ti) * 100.0,
            "PAT_Margin_Pct": _safe_div(pat, ti) * 100.0,
            "Human_Capital_ROI": _safe_div(x["REV_OPS"], x["EMP_COST"]),
            "Value_Added_Per_Emp_Lakhs": _safe_div(gva * 100.0, hc),
            "Avg_Cost_Per_Emp_Lakhs": _safe_div(x["EMP_COST"] * 100.0, hc),
            "Capital_Employed": capital_employed,
            "ROCE_Pct": roce,
            "ROE_Pct": _safe_div(pat, equity) * 100.0,
            "Implied_Cost_of_Debt_Pct": cost_of_debt,
            "Economic_Spread_Pct": spread,
            "EVA_Spread_Proxy_Cr": spread / 100.0 * capital_employed,
            "Interest_Coverage_Ratio": icr,
            "Debt_to_EBITDA": debt_to_ebitda,
            "Effective_Tax_Rate_Pct": _safe_div(x["TAX_EXP"], pbt) * 100.0,
            "Value_Retention_Ratio_Pct": _safe_div(re_ + x["DEP_AMORT"], gva) * 100.0,
        },
        index=YEARS,
    ).T

    cagr = {
        "Revenue_CAGR_Pct": _cagr_pct(x["REV_OPS"][0], x["REV_OPS"][2]),
        "Total_Income_CAGR_Pct": _cagr_pct(ti[0], ti[2]),
        "GVA_CAGR_Pct": _cagr_pct(gva[0], gva[2]),
        "EMP_COST_CAGR_Pct": _cagr_pct(x["EMP_COST"][0], x["EMP_COST"][2]),
        "PAT_CAGR_Pct": _cagr_pct(pat[0], pat[2]),
    }

    return {
        "years": list(YEARS),
        "inputs": inputs,
        "pnl": pnl,
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
        "vas_residual": dict(zip(YEARS, residual.astype(float).tolist())),
        "vas_closure_by_year": dict(zip(YEARS, [bool(v) for v in closure_by_year])),
        "vas_closure_check": bool(np.all(closure_by_year)),
        "kpis": kpis,
        "cagr": cagr,
    }


# --------------------------------------------------------------------------------------
# 3. Deterministic rule-based diagnostics
# --------------------------------------------------------------------------------------
def _cr(v: float) -> str:
    return f"₹{v:,.0f} Cr"


def _xfmt(v: float) -> str:
    return "n/a (no interest burden)" if v >= 999.0 else f"{v:.1f}x"


def generate_deterministic_diagnostics(results: dict) -> list[dict]:
    k, inp, pnl, cagr = results["kpis"], results["inputs"], results["pnl"], results["cagr"]

    def kv(name: str, yr: str = "FY26") -> float:
        return float(k.loc[name, yr])

    cards: list[dict] = []

    # ---- 1) Value Creation Archetype -------------------------------------------------
    bic, lab, gva_m = kv("Bought_In_Costs_Pct"), kv("Labor_Share_of_GVA_Pct"), kv("GVA_Margin_Pct")
    gva26 = float(pnl.loc["GVA", "FY26"])
    if gva26 <= 0:
        title, badge, sev = "Value Creation Archetype", "Value Destruction", "danger"
        text = (
            f"FY26 Gross Value Added is {_cr(gva26)}: bought-in costs absorb {bic:.1f}% of total income, "
            "so the enterprise creates no distributable value after paying suppliers."
        )
    elif bic >= 85.0:
        title, badge, sev = "Value Creation Archetype", "Thin-Spread Platform", "warning"
        text = (
            f"Bought-in costs absorb {bic:.1f}% of FY26 total income, leaving a GVA margin of only {gva_m:.1f}%. "
            f"Labor takes {lab:.1f}% of that GVA. This is a high-throughput, thin-spread model where small "
            "leakages in vendor, logistics or promotion spend move profit disproportionately."
        )
    elif bic >= 70.0:
        title, badge, sev = "Value Creation Archetype", "Supply-Chain Intensive", "warning"
        text = (
            f"Bought-in costs consume {bic:.1f}% of FY26 total income (GVA margin {gva_m:.1f}%), and the workforce "
            f"captures {lab:.1f}% of GVA. Value is created through procurement, scale and asset utilization, "
            "so margins are most exposed to raw-material and freight inflation."
        )
    elif lab >= 50.0:
        title, badge = "Value Creation Archetype", "Human-Capital Intensive"
        sev = "warning" if lab >= 75.0 else "info"
        text = (
            f"The workforce takes {lab:.1f}% of FY26 GVA while bought-in costs are only {bic:.1f}% of income "
            f"(GVA margin {gva_m:.1f}%). Value is created by people, so wage inflation, attrition and "
            "utilization are the primary margin risks."
        )
    elif bic < 70.0 and lab < 35.0:
        title, badge, sev = "Value Creation Archetype", "Brand / Franchise Compounder", "positive"
        text = (
            f"Bought-in costs consume {bic:.1f}% of FY26 income, leaving a {gva_m:.1f}% GVA margin, and the workforce "
            f"takes only {lab:.1f}% of that pool. Most value accrues to the state, capital providers and reinvestment."
        )
    else:
        title, badge, sev = "Value Creation Archetype", "Balanced Value Chain", "info"
        text = (
            f"Bought-in costs are {bic:.1f}% of FY26 income (GVA margin {gva_m:.1f}%) and labor share of GVA is "
            f"{lab:.1f}%, a balanced mix of supplier, workforce and capital contribution."
        )
    cards.append({"title": title, "badge_text": badge, "severity": sev, "narrative": text})

    # ---- 2) Labor vs Capital Drift ---------------------------------------------------
    emp24, emp26 = float(inp.loc["EMP_COST", "FY24"]), float(inp.loc["EMP_COST", "FY26"])
    pat24, pat26 = float(pnl.loc["PAT", "FY24"]), float(pnl.loc["PAT", "FY26"])
    lab24 = kv("Labor_Share_of_GVA_Pct", "FY24")
    title = "3-Year Labor vs. Capital Drift"
    if emp24 <= 0 or emp26 <= 0:
        badge, sev = "Insufficient Workforce Data", "info"
        text = "Employee cost is not reported for FY24 or FY26, so labor-versus-profit drift cannot be computed."
    elif pat24 > 0 and pat26 > 0:
        emp_g, pat_g = cagr["EMP_COST_CAGR_Pct"], cagr["PAT_CAGR_Pct"]
        gap = emp_g - pat_g
        base = (
            f"Employee cost compounded at {emp_g:.1f}% a year versus {pat_g:.1f}% for PAT (FY24 to FY26); "
            f"labor share of GVA moved from {lab24:.1f}% to {lab:.1f}%."
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
    elif pat24 <= 0 < pat26:
        emp_g = cagr["EMP_COST_CAGR_Pct"]
        badge, sev = "Profit Turnaround", "positive"
        text = (
            f"PAT swung from {_cr(pat24)} in FY24 to {_cr(pat26)} in FY26 while employee cost compounded at "
            f"{emp_g:.1f}% a year. Labor share of GVA moved from {lab24:.1f}% to {lab:.1f}%, "
            "showing scale is being absorbed into profit."
        )
    elif pat24 > 0 >= pat26:
        badge, sev = "Profit Erosion", "danger"
        text = (
            f"PAT fell from {_cr(pat24)} in FY24 to {_cr(pat26)} in FY26 while employee cost rose from "
            f"{_cr(emp24)} to {_cr(emp26)}: labor cost growth has not been backed by profit."
        )
    elif pat26 > pat24:
        badge, sev = "Losses Narrowing", "warning"
        text = (
            f"PAT improved from {_cr(pat24)} to {_cr(pat26)} but remains non-positive, "
            f"with employee cost at {_cr(emp26)} ({lab:.1f}% of GVA)."
        )
    else:
        badge, sev = "Persistent Losses", "danger"
        text = (
            f"PAT stands at {_cr(pat26)} in FY26 versus {_cr(pat24)} in FY24 with employee cost at "
            f"{_cr(emp26)}; the cost base is not being covered by value added."
        )
    cards.append({"title": title, "badge_text": badge, "severity": sev, "narrative": text})

    # ---- 3) Capital Efficiency & Economic Spread -------------------------------------
    roce, cod = kv("ROCE_Pct"), kv("Implied_Cost_of_Debt_Pct")
    roce24, roe = kv("ROCE_Pct", "FY24"), kv("ROE_Pct")
    debt26 = float(inp.loc["TOTAL_DEBT", "FY26"])
    ce26 = kv("Capital_Employed")
    debt_share = debt26 / ce26 * 100.0 if ce26 > 0 else 0.0
    spread = roce - cod
    title = "Capital Efficiency & Economic Spread"
    trend = f"ROCE moved from {roce24:.1f}% in FY24 to {roce:.1f}% in FY26 (ROE {roe:.1f}%)."
    if debt26 <= 0 or debt_share < 5.0:
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
    ebitda26 = float(pnl.loc["EBITDA", "FY26"])
    fin26 = float(inp.loc["FIN_COST", "FY26"])
    title = "Credit & Solvency Cushion"
    metrics = f"Interest coverage is {_xfmt(icr)} and Debt/EBITDA is {d_ebitda:.2f}x on {_cr(debt26)} of borrowings."
    if debt26 <= 0 and fin26 <= 0:
        badge, sev = "Debt-Free Fortress", "positive"
        text = "FY26 shows no borrowings and no finance cost, so there is no creditor claim on operating cash flow."
    elif ebitda26 <= 0:
        badge, sev = "No Cash Earnings to Service Debt", "danger"
        text = f"FY26 EBITDA is {_cr(ebitda26)} against {_cr(debt26)} of borrowings. {metrics} Debt service depends on external funding."
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
# 4. Macro & inflation pass-through stress test
# --------------------------------------------------------------------------------------
def _scenario_metrics(lad, rev_ops, fin, tax, equity) -> dict[str, float]:
    ti = lad["Total_Income"]
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
        "Retained_Earnings": lad["Retained_Earnings"],
        "GVA_Margin_Pct": _safe_div(lad["GVA"], ti) * 100.0,
        "EBITDA_Margin_Pct": _safe_div(lad["EBITDA"], ti) * 100.0,
        "PAT_Margin_Pct": _safe_div(lad["PAT"], ti) * 100.0,
        "ROE_Pct": _safe_div(lad["PAT"], equity) * 100.0,
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
    base = results["inputs"]["FY26"]

    def a(name: str) -> np.ndarray:
        return np.array([float(base[name])], dtype="float64")

    rev_ops, rev_oth, cogs, opex = a("REV_OPS"), a("REV_OTH"), a("COGS_MAT"), a("OPEX_EXT")
    emp, dep, fin, tax = a("EMP_COST"), a("DEP_AMORT"), a("FIN_COST"), a("TAX_EXP")
    div, debt, equity = a("DIV_PAID"), a("TOTAL_DEBT"), a("TOTAL_EQUITY")

    base_tax_rate = float(results["kpis"].loc["Effective_Tax_Rate_Pct", "FY26"]) / 100.0

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

    base_m = _scenario_metrics(base_lad, rev_ops, fin, tax, equity)
    sim_m = _scenario_metrics(sim_lad, sim_rev_ops, sim_fin, sim_tax, equity)

    names = list(base_m.keys())
    b_vals = np.array([base_m[n] for n in names], dtype="float64")
    s_vals = np.array([sim_m[n] for n in names], dtype="float64")
    change = s_vals - b_vals
    is_money = np.array([n in _MONEY_METRICS for n in names])
    change_pct = np.where(is_money, _safe_div(change, np.abs(b_vals)) * 100.0, np.nan)
    comparison = pd.DataFrame(
        {"Baseline_FY26": b_vals, "Simulated_FY26": s_vals, "Change": change, "Change_Pct": change_pct},
        index=names,
    )

    pair = lambda b, s: np.concatenate([b, s])  # noqa: E731
    receipt = _receipt_frames(
        _receipt_components(
            pair(cogs, sim_cogs), pair(opex, opex), pair(emp, sim_emp), pair(dep, dep),
            pair(fin, sim_fin), pair(tax, sim_tax), pair(div, div),
            pair(base_lad["Retained_Earnings"], sim_lad["Retained_Earnings"]),
        ),
        pair(base_lad["Total_Income"], sim_lad["Total_Income"]),
        ["Baseline_FY26", "Simulated_FY26"],
    )
    receipt_df = receipt["rupees"].copy()
    receipt_df["Change"] = receipt_df["Simulated_FY26"] - receipt_df["Baseline_FY26"]

    sim_stake_sum = float(
        (sim_emp + sim_fin + sim_tax + div + (sim_lad["Retained_Earnings"] + dep)).reshape(-1)[0]
    )
    sim_gva = float(sim_lad["GVA"].reshape(-1)[0])

    rev_ops_f = float(rev_ops[0])
    breakeven = float(_safe_div(total_cost_inflation, rev_ops).reshape(-1)[0] * 100.0)

    return {
        "assumptions": {
            "mat_inflation_pct": float(mat_inflation_pct),
            "wage_hike_pct": float(wage_hike_pct),
            "rate_shock_bps": float(rate_shock_bps),
            "price_passthrough_pct": float(price_passthrough_pct),
            "dividend_policy": "Held constant at FY26 baseline; shortfall is drawn from retained earnings.",
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
            "baseline_sum": receipt["sum_rounded"]["Baseline_FY26"],
            "simulated_sum": receipt["sum_rounded"]["Simulated_FY26"],
            "all_ok": receipt["all_ok"],
        },
        "simulated_revenue_ops": float(sim_rev_ops[0]) if rev_ops_f >= 0 else rev_ops_f,
        "vas_closure_check": bool(abs(sim_gva - sim_stake_sum) < 1e-4),
    }