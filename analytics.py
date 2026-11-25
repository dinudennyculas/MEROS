"""MEROS analytics: history window, rebalance, provenance, reconciliation bridge, average-balance returns, full EVA,
DuPont (3-step and 5-step, with change attribution), data-health checks, plain-English text and company comparison.

Pure Python / NumPy / pandas. No network, no Streamlit, no AI, and no estimates: anything the source does not report
stays 'not reported' and the metrics that depend on it come out as NaN."""
from __future__ import annotations

import copy
import datetime as _dt

import numpy as np
import pandas as pd

from corporate_engine import META_COLS, RECEIPT_LABELS, SCHEMA
from meros_assumptions import HISTORY_OPTIONS

PROV_VALUE_COL = "Value (₹ Cr; headcount in persons)"
ANCHOR_TOL = 0.01
CLOSURE_TOL = 1e-4

CAP_LAYOUT: list[tuple[str, str, str]] = [
    ("section", "A. RETURNS ON CAPITAL: YEAR-END vs AVERAGE BALANCES", ""),
    ("CE_END", "Capital employed, year-end (debt + equity)", "cr"),
    ("CE_AVG", "Capital employed, average of opening and closing", "cr"),
    ("ROCE_END", "ROCE on year-end capital (headline figure)", "pct"),
    ("ROCE_AVG", "ROCE on average capital", "pct"),
    ("ROE_END", "ROE on year-end equity (headline figure)", "pct"),
    ("ROE_AVG", "ROE on average equity", "pct"),
    ("section", "B. FULL ECONOMIC VALUE ADDED (USES YOUR COST OF EQUITY)", ""),
    ("T_RATE", "Tax rate on operating profit (reported tax ÷ PBT, clipped to 0-40%)", "pct"),
    ("NOPAT", "NOPAT = EBIT x (1 − tax rate)", "cr"),
    ("WACC", "WACC (year-end book-value weights)", "pct"),
    ("CHARGE", "Capital charge = WACC x year-end capital employed", "cr"),
    ("EVA", "Economic Value Added = NOPAT − capital charge", "cr"),
    ("ROIC", "ROIC = NOPAT ÷ year-end capital employed", "pct"),
    ("SPREAD", "ROIC − WACC", "pct"),
]

DUPONT_LAYOUT: list[tuple[str, str, str]] = [
    ("section", "A. 3-STEP DUPONT", ""),
    ("NM", "Net profit margin (attributable profit ÷ total income)", "pct"),
    ("AT", "Asset turnover (total income ÷ total assets)", "x"),
    ("EM", "Equity multiplier (total assets ÷ equity)", "x"),
    ("ROE3", "ROE = margin x turnover x multiplier", "pct"),
    ("section", "B. 5-STEP DUPONT", ""),
    ("TB", "Tax & minority burden (attributable profit ÷ PBT)", "x"),
    ("IB", "Interest burden (PBT ÷ EBIT)", "x"),
    ("EBITM", "EBIT margin (EBIT ÷ total income)", "pct"),
    ("ROE5", "ROE = burden x burden x EBIT margin x turnover x multiplier", "pct"),
    ("section", "C. CHECK", ""),
    ("ROE_DIRECT", "ROE measured directly (attributable profit ÷ year-end equity)", "pct"),
    ("RESIDUAL", "Direct ROE − 3-step ROE (should be 0.00)", "pp"),
]
DUPONT_FACTORS = {"3": ["NM", "AT", "EM"], "5": ["TB", "IB", "EBITM", "AT", "EM"]}
DUPONT_FACTOR_NAMES = {"NM": "Net profit margin", "AT": "Asset turnover", "EM": "Equity multiplier", "TB": "Tax & minority burden",
                       "IB": "Interest burden", "EBITM": "EBIT margin"}


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------
def _arr(lst: list | None, n: int) -> np.ndarray:
    if lst is None:
        return np.full(n, np.nan)
    out = np.array([np.nan if v is None else v for v in lst], dtype="float64")
    return out if out.shape[0] == n else np.full(n, np.nan)


def _row(df: pd.DataFrame, name: str, years: list[str]) -> np.ndarray:
    return df.loc[name, years].to_numpy(dtype="float64")


def _div(num: np.ndarray, den: np.ndarray, positive: bool = True) -> np.ndarray:
    mask = (den > 0) if positive else (den != 0)
    out = np.full(np.shape(num), np.nan)
    np.divide(num, den, out=out, where=mask & np.isfinite(num) & np.isfinite(den))
    return out


def _ys(mask: np.ndarray, labels: list[str]) -> str:
    return ", ".join(y for y, m in zip(labels, mask) if bool(m))


def _it(level: str, code: str, title: str, detail: str) -> dict:
    return {"level": level, "code": code, "title": title, "detail": detail}


def history_label(n: int) -> str:
    for lab, v in HISTORY_OPTIONS:
        if v == int(n or 0):
            return lab
    return f"Last {int(n)} years" if int(n or 0) > 0 else "Since inception (all available years)"


# --------------------------------------------------------------------------------------
# History window
# --------------------------------------------------------------------------------------
def select_window(cd: dict, n_years: int) -> dict:
    """Cut company data to the latest `n_years` annual periods (0 = all). The year just before the window supplies the opening balance."""
    years_all = list(cd["years"])
    total = len(years_all)
    requested = int(n_years or 0)
    use = total if requested <= 0 else min(requested, total)
    start = total - use
    keep = years_all[start:]
    sl = slice(start, total)

    out = copy.deepcopy({k: v for k, v in cd.items() if k != "grid"})
    grid_all = cd["grid"]
    out["grid"] = grid_all[META_COLS + keep].copy()
    out["years"] = keep
    out["period_ends"] = list(cd["period_ends"][sl])
    out["period_labels"] = list(cd["period_labels"][sl])
    out["attr_adj"] = list(cd["attr_adj"][sl])
    out["anchors"] = {k: list(v[sl]) for k, v in cd["anchors"].items()}
    out["extras"] = {k: list(v[sl]) for k, v in (cd.get("extras") or {}).items()}
    out["provenance"] = {k: [list(x) for x in v[sl]] for k, v in cd["provenance"].items()}

    opening = dict(cd.get("opening") or {})
    for key in ("TOTAL_DEBT", "TOTAL_EQUITY", "TOTAL_ASSETS", "label"):
        opening.setdefault(key, None)
    if start > 0:
        prev, prev_year = start - 1, years_all[start - 1]
        eq_status = cd["provenance"]["TOTAL_EQUITY"][prev][0]
        if eq_status != "Not reported":
            g = grid_all.set_index("Line_ID")
            ta_list = (cd.get("extras") or {}).get("TOTAL_ASSETS") or [None] * total
            opening = {"TOTAL_DEBT": float(g.loc["TOTAL_DEBT", prev_year]), "TOTAL_EQUITY": float(g.loc["TOTAL_EQUITY", prev_year]),
                       "TOTAL_ASSETS": ta_list[prev], "label": cd["period_labels"][prev]}
        else:
            opening = {"TOTAL_DEBT": None, "TOTAL_EQUITY": None, "TOTAL_ASSETS": None, "label": None}
    out["opening"] = opening

    status = dict(cd.get("status") or {})
    if cd.get("source") == "yahoo":
        status["Y18"] = "active" if opening["TOTAL_EQUITY"] is not None else "inactive"
    out["status"] = status

    note = ""
    if requested > 0 and use < requested:
        note = f"You asked for {requested} years but only {use} are available from this source, so {use} are used."
    out["window"] = {"requested": requested, "used": use, "available": total, "start_index": start, "note": note,
                     "label": history_label(requested)}
    return out


# --------------------------------------------------------------------------------------
# Rebalance after user edits, employee state, provenance
# --------------------------------------------------------------------------------------
def rebalance_to_pbt(grid: pd.DataFrame, pbt_anchor: list, years: list[str]) -> pd.DataFrame:
    """Re-solve Other Operating Expenses (lifting Other Income if it would go negative) so PBT still equals the source's figure after edits."""
    out = grid.copy()
    pos = {str(k).strip().upper(): i for i, k in enumerate(out["Line_ID"])}
    need = ["REV_OPS", "REV_OTH", "COGS_MAT", "OPEX_EXT", "EMP_COST", "DEP_AMORT", "FIN_COST"]
    if any(k not in pos for k in need):
        return out
    pbt = np.asarray([np.nan if v is None else v for v in pbt_anchor], dtype="float64")
    for j, yr in enumerate(years):
        if yr not in out.columns or j >= pbt.shape[0] or not np.isfinite(pbt[j]):
            continue
        v = pd.to_numeric(out[yr], errors="coerce").fillna(0.0).to_numpy(dtype="float64")
        rev_oth = v[pos["REV_OTH"]]
        ti = v[pos["REV_OPS"]] + rev_oth
        opex = ti - pbt[j] - v[pos["COGS_MAT"]] - v[pos["EMP_COST"]] - v[pos["DEP_AMORT"]] - v[pos["FIN_COST"]]
        if opex < 0.0:
            rev_oth, opex = rev_oth - opex, 0.0
        col = out.columns.get_loc(yr)
        out.iloc[pos["REV_OTH"], col] = round(float(rev_oth), 4)
        out.iloc[pos["OPEX_EXT"], col] = round(float(opex), 4)
    return out


def employee_state(cd: dict, final_inputs: pd.DataFrame) -> str:
    """'user' if the employee-cost row was edited, otherwise the source's own status (reported / partial / not_reported)."""
    years = cd["years"]
    base = cd["grid"].set_index("Line_ID").loc["EMP_COST", years].to_numpy(dtype="float64")
    now = final_inputs.loc["EMP_COST", years].to_numpy(dtype="float64")
    return "user" if not np.allclose(base, now, atol=1e-9) else str(cd.get("emp_status", "reported"))


def provenance_frame(cd: dict, final_inputs: pd.DataFrame, rebalanced: bool = True) -> pd.DataFrame:
    """One row per (line, year): value, status and the exact source row or rule. Edited cells are marked 'Your edit' / 'Re-balanced'."""
    base = cd["grid"].set_index("Line_ID")
    years = cd["years"]
    rows = []
    for lid, name, _cat in SCHEMA:
        for j, yr in enumerate(years):
            status, detail = cd["provenance"][lid][j]
            b, v = float(base.loc[lid, yr]), float(final_inputs.loc[lid, yr])
            if abs(v - b) > 1e-9:
                if rebalanced and lid in ("OPEX_EXT", "REV_OTH"):
                    status, detail = "Re-balanced", f"Re-solved after your edits so PBT stays at the source's figure (original value {b:,.2f})"
                else:
                    status, detail = "Your edit", f"You overrode the original value {b:,.2f} in the grid"
            rows.append({"Line_ID": lid, "Line item": name, "Year": yr, "Period end": cd["period_ends"][j],
                         PROV_VALUE_COL: v, "Status": status, "Source / rule": detail})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Reconciliation bridge numbers
# --------------------------------------------------------------------------------------
def bridge_numbers(cd: dict, results: dict) -> dict:
    """Source anchors against the MEROS ladder, plus variances. Tolerance 0.01 Cr for anchors, 0.0001 Cr for closure."""
    years = results["years"]
    pnl, anc = results["pnl"], cd["anchors"]
    n = len(years)
    tr, pb, pa, tp = (_arr(anc[k], n) for k in ("TOTAL_REVENUE", "PBT", "PAT_ATTR", "TAX_REPORTED"))
    resid = np.array([results["vas_residual"][y] for y in years], dtype="float64")
    rcpt = results["common_size"][years].sum(axis=0).to_numpy(dtype="float64") - 100.0
    out = {
        "years": years, "tr": tr, "pb": pb, "pa": pa, "tp": tp,
        "ti": _row(pnl, "Total_Income", years), "gva": _row(pnl, "GVA", years), "pbt": _row(pnl, "PBT", years),
        "tax": _row(pnl, "Tax_Expense", years), "pat": _row(pnl, "PAT", years), "adj": _row(pnl, "Minority_Associates_Adj", years),
        "pat_attr": _row(pnl, "PAT_Attributable", years), "resid": resid, "rcpt": rcpt,
    }
    out["v_pbt"] = out["pbt"] - pb
    out["v_pat"] = out["pat_attr"] - pa
    out["v_tax"] = np.where(np.isfinite(tp), out["tax"] - tp, np.nan)
    out["close_ok"] = (np.abs(resid) < CLOSURE_TOL) & (np.abs(rcpt) < CLOSURE_TOL)
    out["anchor_ok"] = (np.abs(out["v_pbt"]) < ANCHOR_TOL) & (np.abs(out["v_pat"]) < ANCHOR_TOL)
    return out


# --------------------------------------------------------------------------------------
# Average-balance returns and full EVA
# --------------------------------------------------------------------------------------
def capital_returns(results: dict, cd: dict | None, ke_pct: float) -> dict:
    years = results["years"]
    inp, pnl, k = results["inputs"], results["pnl"], results["kpis"]
    debt, eq, fin = _row(inp, "TOTAL_DEBT", years), _row(inp, "TOTAL_EQUITY", years), _row(inp, "FIN_COST", years)
    ebit, pbt, tax = _row(pnl, "EBIT", years), _row(pnl, "PBT", years), _row(pnl, "Tax_Expense", years)
    pat_attr = results["pat_attr"].to_numpy(dtype="float64")
    ce = debt + eq

    op = (cd or {}).get("opening") or {}
    od = oe = np.nan
    if op.get("TOTAL_DEBT") is not None and op.get("TOTAL_EQUITY") is not None:
        od, oe = float(op["TOTAL_DEBT"]), float(op["TOTAL_EQUITY"])
    prev_ce = np.concatenate([[od + oe], ce[:-1]])
    prev_eq = np.concatenate([[oe], eq[:-1]])
    avg_ce, avg_eq = (ce + prev_ce) / 2.0, (eq + prev_eq) / 2.0

    ke = float(ke_pct) / 100.0
    with np.errstate(all="ignore"):
        roce_avg = _div(ebit, avg_ce) * 100.0
        roe_avg = _div(pat_attr, avg_eq) * 100.0
        t = np.clip(np.where(pbt > 0, tax / np.where(pbt > 0, pbt, 1.0), 0.0), 0.0, 0.40)
        nopat = ebit * (1.0 - t)
        kd = np.where(debt > 0, fin / np.where(debt > 0, debt, 1.0), 0.0)
        tot = debt + eq
        we = _div(eq, tot)
        wacc = we * ke + (1.0 - we) * kd * (1.0 - t)
        charge = wacc * ce
        eva = nopat - charge
        roic = _div(nopat, ce) * 100.0
        spread = roic - wacc * 100.0
    return {"CE_END": ce, "CE_AVG": avg_ce, "ROCE_END": _row(k, "ROCE_Pct", years), "ROCE_AVG": roce_avg,
            "ROE_END": _row(k, "ROE_Pct", years), "ROE_AVG": roe_avg, "T_RATE": t * 100.0, "NOPAT": nopat,
            "WACC": wacc * 100.0, "CHARGE": charge, "EVA": eva, "ROIC": roic, "SPREAD": spread}


# --------------------------------------------------------------------------------------
# DuPont
# --------------------------------------------------------------------------------------
def dupont(results: dict, cd: dict | None) -> dict:
    """3-step and 5-step DuPont on a single year-end base (so the factors multiply back to ROE exactly)."""
    years = results["years"]
    n = len(years)
    pnl, inp = results["pnl"], results["inputs"]
    ni = results["pat_attr"].to_numpy(dtype="float64")
    ti, pbt, ebit = _row(pnl, "Total_Income", years), _row(pnl, "PBT", years), _row(pnl, "EBIT", years)
    eq = _row(inp, "TOTAL_EQUITY", years)
    ta = _arr(((cd or {}).get("extras") or {}).get("TOTAL_ASSETS"), n)
    ta = np.where(ta > 0, ta, np.nan)

    with np.errstate(all="ignore"):
        nm = _div(ni, ti) * 100.0
        at = _div(ti, ta)
        em = _div(ta, eq)
        roe3 = nm * at * em
        tb = _div(ni, pbt)
        ib = _div(pbt, ebit)
        ebitm = _div(ebit, ti) * 100.0
        roe5 = tb * ib * ebitm * at * em
        direct = _div(ni, eq) * 100.0
        residual = direct - roe3
    values = {"NM": nm, "AT": at, "EM": em, "ROE3": roe3, "TB": tb, "IB": ib, "EBITM": ebitm, "ROE5": roe5,
              "ROE_DIRECT": direct, "RESIDUAL": residual}
    available = bool(np.isfinite(roe3).any())
    reason = ""
    if not available:
        reason = ("Total assets are not available from this data source, so DuPont cannot be built." if not np.isfinite(ta).any()
                  else "DuPont needs positive total income, total assets and equity; at least one of them is missing or not positive.")
    return {"years": years, "values": values, "layout": DUPONT_LAYOUT, "available": available, "reason": reason,
            "bank": bool((cd or {}).get("is_financial"))}


def dupont_change(dp: dict, which: str = "3", i0: int = 0, i1: int | None = None) -> dict | None:
    """Exact log-mean (LMDI) attribution of the ROE change between two years to each DuPont factor, in percentage points.

    Returns None when a factor or ROE is not positive in either year (the method needs positive numbers)."""
    vals = dp["values"]
    n = len(dp["years"])
    i1 = n - 1 if i1 is None else i1
    keys = DUPONT_FACTORS[which]
    roe_key = "ROE3" if which == "3" else "ROE5"
    try:
        f0 = np.array([vals[k][i0] for k in keys], dtype="float64")
        f1 = np.array([vals[k][i1] for k in keys], dtype="float64")
        r0, r1 = float(vals[roe_key][i0]), float(vals[roe_key][i1])
    except (KeyError, IndexError):
        return None
    if not (np.all(np.isfinite(f0)) and np.all(np.isfinite(f1)) and np.isfinite(r0) and np.isfinite(r1)):
        return None
    if np.any(f0 <= 0) or np.any(f1 <= 0) or r0 <= 0 or r1 <= 0:
        return None
    weight = r0 if abs(r1 - r0) < 1e-12 else (r1 - r0) / (np.log(r1) - np.log(r0))
    contrib = {k: float(weight * np.log(b / a)) for k, a, b in zip(keys, f0, f1)}
    return {"keys": keys, "contrib": contrib, "roe_first": r0, "roe_last": r1, "total": r1 - r0,
            "check": float(sum(contrib.values()) - (r1 - r0)), "first": dp["years"][i0], "last": dp["years"][i1]}


# --------------------------------------------------------------------------------------
# Data-health checks
# --------------------------------------------------------------------------------------
def health_checks(results: dict, cd: dict | None = None, xcheck: dict | None = None, today: _dt.date | None = None) -> list[dict]:
    today = today or _dt.date.today()
    years = results["years"]
    n = len(years)
    pnl, inp = results["pnl"], results["inputs"]
    ti, gva, pbt, tax = (_row(pnl, k, years) for k in ("Total_Income", "GVA", "PBT", "Tax_Expense"))
    pat_attr = results["pat_attr"].to_numpy(dtype="float64")
    emp, rev, oth = (_row(inp, k, years) for k in ("EMP_COST", "REV_OPS", "REV_OTH"))
    eq, div = _row(inp, "TOTAL_EQUITY", years), _row(inp, "DIV_PAID", years)
    adj = np.asarray(results["attr_adj"], dtype="float64")
    c = cd or {}
    issues: list[dict] = []
    oks: list[dict] = []

    if results["vas_closure_check"] and results["receipt_check"]["all_ok"]:
        oks.append(_it("ok", "H01", "Accounting closure holds",
                       f"GVA equals the sum of its five stakeholder shares and the ₹100 receipt sums to exactly ₹100.00 in all {n} years."))
    else:
        issues.append(_it("alert", "H01", "Accounting closure broken",
                          "GVA does not equal the sum of its stakeholder shares, or the ₹100 receipt does not sum to ₹100.00. Inspect the input grid."))
    if (gva <= 0).any():
        issues.append(_it("alert", "H02", "Gross value added is zero or negative",
                          f"GVA is not positive in {_ys(gva <= 0, years)}. Bought-in costs exceed income, so share-of-GVA percentages are not meaningful there."))
    if (eq <= 0).any():
        issues.append(_it("alert", "H03", "Equity is zero or negative",
                          f"Shareholders' equity is not positive in {_ys(eq <= 0, years)}. ROE, DuPont and book-value weights are not meaningful there."))

    sector, industry = str(c.get("sector") or "").lower(), str(c.get("industry") or "").lower()
    is_it = ("technology" in sector) or ("information technology" in industry)
    thr = 0.75 if is_it else 0.60
    with np.errstate(all="ignore"):
        emp_share = np.where(ti > 0, emp / np.where(ti > 0, ti, 1.0), 0.0)
    if ((emp_share > thr) & (emp > 0)).any():
        issues.append(_it("warn", "H04", "Unusually high employee cost",
                          f"Employee cost is above {thr * 100:.0f}% of total income in {_ys(emp_share > thr, years)}. Outside services businesses this often means the payroll figure is wrong or includes other costs."))
    if n >= 2:
        prev, cur = rev[:-1], rev[1:]
        with np.errstate(all="ignore"):
            yoy = np.where(prev > 0, cur / np.where(prev > 0, prev, 1.0) - 1.0, np.nan)
            jump = (yoy > 1.0) | (yoy < -0.5)
        if jump.any():
            issues.append(_it("info", "H05", "Large revenue swing",
                              f"Revenue moved by more than +100% or -50% in {_ys(jump, years[1:])}. This is often a merger, demerger, new listing or accounting change, so year-on-year ratios may not be like-for-like."))
    over = (pat_attr > 0) & (div > pat_attr)
    if over.any():
        issues.append(_it("info", "H08", "Dividends exceed profit",
                          f"Dividends are larger than attributable profit in {_ys(over, years)}, so retained earnings are negative. This can be a special dividend or a payout from earlier reserves."))
    with np.errstate(all="ignore"):
        etr = np.where(pbt > 0, tax / np.where(pbt > 0, pbt, 1.0), np.nan)
        odd_tax = (etr < 0) | (etr > 0.45)
        oth_share = np.where(ti > 0, oth / np.where(ti > 0, ti, 1.0), 0.0)
    if odd_tax.any():
        issues.append(_it("info", "H09", "Unusual effective tax rate",
                          f"Tax is below 0% or above 45% of pretax profit in {_ys(odd_tax, years)}. Exceptional items, deferred tax or one-off gains can cause this."))
    if (oth_share > 0.25).any():
        issues.append(_it("info", "H10", "Profit leans on other income",
                          f"Other income is above 25% of total income in {_ys(oth_share > 0.25, years)}, so headline margins include a lot of non-operating income."))
    if n >= 2:
        spike = np.zeros(n, dtype=bool)
        spike[1:] = (oth[1:] > 3.0 * np.maximum(oth[:-1], 1e-9)) & (oth[1:] > 0.10 * np.maximum(ti[1:], 1e-9))
        if spike.any():
            issues.append(_it("info", "H10b", "Other income spiked",
                              f"Other income jumped to more than three times the previous year, and above 10% of income, in {_ys(spike, years)}. This is usually a one-off gain; it inflates profit and ROE for that year."))
    with np.errstate(all="ignore"):
        big_gap = np.abs(adj) > 0.10 * np.maximum(np.abs(pbt), 1e-9)
    if big_gap.any():
        issues.append(_it("info", "H23", "Large minority-interest / associates gap",
                          f"Reported attributable profit differs from (PBT − tax) by more than 10% of PBT in {_ys(big_gap, years)}. Minority shareholders or associates matter a lot for this company."))

    emp_status = str(c.get("emp_status", ""))
    if emp_status == "not_reported":
        issues.append(_it("warn", "H07", "Employee cost not reported",
                          "The data source has no employee-cost figure. MEROS does not estimate it, so workforce share, value added per employee and Human Capital ROI are not meaningful until you type the figure into the override grid."))
    elif emp_status == "partial":
        issues.append(_it("warn", "H07", "Employee cost missing in some years", "The source reports employee cost for only some of the years."))
    hc_status = str(c.get("hc_status", ""))
    if hc_status == "not_reported":
        issues.append(_it("info", "H06", "Headcount not reported", "No headcount is available, so per-employee metrics are shown as n/a unless you type the headcount into the override grid."))
    elif hc_status == "snapshot_latest":
        issues.append(_it("info", "H06", "Headcount for the latest year only", "Only a current employee count exists, so per-employee metrics are shown for the latest year only."))

    if c:
        try:
            ends = [_dt.date.fromisoformat(s) for s in c["period_ends"]]
        except (ValueError, KeyError, TypeError):
            ends = []
        if ends:
            age = (today - ends[-1]).days
            if age > 456:
                issues.append(_it("warn", "H11", "Latest filing looks stale",
                                  f"The newest annual period ends {ends[-1]:%d %b %Y}, about {age / 30.44:.0f} months ago. Newer results may exist that the source has not loaded."))
            gaps = [(ends[i + 1] - ends[i]).days for i in range(len(ends) - 1)]
            if any(gp < 330 or gp > 400 for gp in gaps):
                issues.append(_it("warn", "H12", "Periods are not twelve months apart",
                                  "The gaps between period ends are " + ", ".join(f"{gp} days" for gp in gaps)
                                  + ". A change of year-end or a transition period makes the years not strictly comparable."))
        if str(c.get("currency", "INR")).upper() != "INR":
            issues.append(_it("alert", "H13", "Reporting currency is not INR",
                              f"The source reports this company in {c.get('currency')}. MEROS labelled the figures ₹ Crores without converting them, so the scale is wrong."))
        if c.get("is_financial"):
            issues.append(_it("info", "H15", "Bank or financial company",
                              "Revenue is interest-based and deposits are not treated as debt. Value-added, ROCE, DuPont and EVA figures are indicative only."))
        if c.get("layout") == "aggregate":
            issues.append(_it("warn", "H24", "No cost breakdown in the file",
                              "The Screener file has only an aggregate Expenses line, so materials and employee cost are not reported. Treat value-added results as indicative."))
        st = c.get("status") or {}
        if st.get("Y09") == "active":
            issues.append(_it("info", "H16", "Other income was lifted",
                              "Reported costs exceeded income in at least one year, so Other Income was raised to keep Other Operating Expenses non-negative (see the notice)."))
        if st.get("S06") == "active":
            issues.append(_it("alert", "H16", "Screener cost lines do not add up",
                              "The mapped cost lines do not rebuild Screener's own profit-before-tax in at least one year. The difference was added to Other Operating Expenses. Check the file and the notice."))
        opn = c.get("opening") or {}
        if opn.get("TOTAL_EQUITY") is None:
            issues.append(_it("info", "H18", "No opening balance sheet",
                              "There is no balance sheet before the first year, so the first year's average-balance ratios show n/a."))
        src = c.get("source")
        if src == "screener" and str(c.get("version", "unknown")) not in ("consolidated", "standalone"):
            issues.append(_it("warn", "H20", "Consolidated or standalone not stated",
                              "The workbook does not say which version it is and you did not tell MEROS, so the basis of the figures is unknown."))
        elif src == "yahoo":
            issues.append(_it("info", "H21", "Yahoo does not state the basis",
                              "Yahoo Finance does not say whether its figures are consolidated or standalone. Compare with a Screener export if this matters."))
        w = (c.get("window") or {}).get("note")
        if w:
            issues.append(_it("info", "H25", "Fewer years than requested", w))
    if xcheck and xcheck.get("status") == "flag":
        issues.append(_it("warn", "H19", "Screener and Yahoo disagree", xcheck.get("message", "")))
    elif xcheck and xcheck.get("status") == "ok":
        oks.append(_it("ok", "H19", "Screener agrees with Yahoo", xcheck.get("message", "")))

    order = {"alert": 0, "warn": 1, "info": 2}
    issues.sort(key=lambda d: order[d["level"]])
    if not issues and not oks:
        oks.append(_it("ok", "H00", "No issues flagged", "None of the automated screens found a problem. These are rough tripwires, not an audit."))
    return issues + oks


# --------------------------------------------------------------------------------------
# Plain English
# --------------------------------------------------------------------------------------
def plain_summary(cd: dict, results: dict, fy: str, emp_state: str = "reported") -> str:
    pnl, cs, k, cagr, inp = results["pnl"], results["common_size"], results["kpis"], results["cagr"], results["inputs"]
    years = results["years"]
    ti, gva = float(pnl.loc["Total_Income", fy]), float(pnl.loc["GVA", fy])
    v = [float(cs.loc[lab, fy]) for lab in RECEIPT_LABELS]
    bic = float(k.loc["Bought_In_Costs_Pct", fy])
    roce, cod = float(k.loc["ROCE_Pct", fy]), float(k.loc["Implied_Cost_of_Debt_Pct", fy])
    debt = float(inp.loc["TOTAL_DEBT", fy])
    g = float(cagr["Revenue_CAGR_Pct"])
    name = str(cd.get("company_name") or "The company")
    first = f"{name} brought in ₹{ti:,.0f} Cr in {fy}"
    if np.isfinite(g) and len(years) >= 2:
        first += f", and its revenue grew about {g:.1f}% a year over {years[0]} to {years[-1]}."
    else:
        first += "."
    parts = [first]
    if gva > 0:
        parts.append(f"After paying suppliers and outside service providers ({bic:.0f}% of its income) it created ₹{gva:,.0f} Cr of new value.")
    else:
        parts.append("After paying suppliers and outside service providers it had no new value left to share out.")
    kept = (f"₹{v[7]:.0f} stayed in the business as retained profit" if v[7] >= 0 else f"it lost about ₹{abs(v[7]):.0f}, which had to come out of reserves")
    emp_part = f"₹{v[2]:.0f} to employees" if emp_state in ("reported", "user") else "an unknown amount to employees (not reported)"
    parts.append(f"Of every ₹100 customers paid, roughly ₹{v[0] + v[1]:.0f} went to suppliers, {emp_part}, ₹{v[4]:.0f} to lenders, "
                 f"₹{v[5]:.0f} to the government as tax and ₹{v[6]:.0f} to shareholders as dividends; {kept} (and ₹{v[3]:.0f} covers wear and tear on assets).")
    if debt <= 0:
        parts.append(f"It carries no debt and earned {roce:.1f}% a year on its capital.")
    else:
        verdict = "borrowed money is earning more than it costs." if roce > cod else "borrowed money is currently costing more than it earns."
        parts.append(f"It earned {roce:.1f}% on its capital while paying about {cod:.1f}% on its debt, so {verdict}")
    if emp_state == "not_reported":
        parts.append("Caution: employee cost is not reported by the data source, so the workforce share is missing and value added is understated. Profit figures are unaffected.")
    elif emp_state == "partial":
        parts.append("Caution: employee cost is missing for some years, so workforce figures for those years are not meaningful.")
    elif emp_state == "user":
        parts.append("Employee cost was set by you in the verification grid.")
    return " ".join(parts)


def plain_notes(results: dict, fy: str, cd: dict | None = None) -> dict:
    k, cagr, years = results["kpis"], results["cagr"], results["years"]
    g = float(cagr["Revenue_CAGR_Pct"])
    cost_l, va_l = float(k.loc["Avg_Cost_Per_Emp_Lakhs", fy]), float(k.loc["Value_Added_Per_Emp_Lakhs", fy])
    icr = float(k.loc["Interest_Coverage_Ratio", fy])
    notes = {
        "ti": (f"Sales plus other income for the year. Revenue has grown about {g:.1f}% a year since {years[0]}." if np.isfinite(g) and len(years) >= 2
               else "Sales plus other income for the year."),
        "gva": f"New value created after paying outside suppliers: about ₹{float(k.loc['GVA_Margin_Pct', fy]):.0f} of every ₹100 earned.",
        "bite": "After every cost and tax, this is the profit left from each ₹100 of income.",
        "hyg": "Input cells that had to be cleaned on the way in. 'Verified' means the books add up to the paisa.",
        "roce": "Operating profit earned on every ₹100 of capital (debt plus equity) used in the business.",
        "roe": "Profit that belongs to shareholders for every ₹100 of their money in the business.",
        "cod": "Interest paid divided by borrowings: the price the company pays for its debt.",
        "spread": "Positive means the business earns more than it pays on debt; negative means borrowing is destroying value.",
        "icr": "No interest to pay." if icr >= 999.0 else f"Operating profit could pay the interest bill {icr:.1f} times over.",
    }
    if np.isfinite(cost_l) and np.isfinite(va_l) and cost_l > 0:
        notes["wf"] = f"The average employee cost ₹{cost_l:.1f} L and helped create ₹{va_l:.1f} L of value ({va_l / cost_l:.1f}x their cost)."
    elif np.isfinite(va_l):
        notes["wf"] = f"Each employee helped create ₹{va_l:.1f} L of value. Employee cost is not reported, so their cost cannot be compared."
    else:
        notes["wf"] = "Employee cost or headcount is not reported for this year, so this figure is not available."
    return notes


# --------------------------------------------------------------------------------------
# Company comparison
# --------------------------------------------------------------------------------------
COMPARE_ROWS: list[tuple[str, str, str]] = [
    ("period", "Latest year-end", "text"),
    ("n_years", "Years analysed", "int"),
    ("source", "Data source", "text"),
    ("ti", "Total income (₹ Cr)", "cr"),
    ("gva", "Gross value added (₹ Cr)", "cr"),
    ("pat_attr", "Profit attributable to shareholders (₹ Cr)", "cr"),
    ("gva_margin", "GVA margin", "pct"),
    ("ebitda_margin", "EBITDA margin", "pct"),
    ("pat_margin", "PAT margin", "pct"),
    ("emp_share", "Employee cost as % of total income", "pct"),
    ("va_emp", "Value added per employee (₹ L)", "lakh"),
    ("roce", "ROCE", "pct"),
    ("roe", "ROE", "pct"),
    ("cod", "Implied cost of debt", "pct"),
    ("icr", "Interest coverage", "icr"),
    ("nm", "DuPont: net profit margin", "pct"),
    ("at", "DuPont: asset turnover", "x"),
    ("em", "DuPont: equity multiplier", "x"),
    ("roic", "ROIC", "pct"),
    ("wacc", "WACC (book weights)", "pct"),
    ("eva", "Economic value added (₹ Cr)", "cr"),
    ("rev_cagr", "Revenue growth per year over the window", "pct"),
    ("pat_cagr", "Attributable profit growth per year over the window", "pct"),
]


def comparison_frame(entries: list[dict], ke_pct: float) -> dict:
    """entries: [{'name': str, 'cd': company data (already windowed), 'results': engine results}, ...]. Latest year of each company."""
    columns: dict[str, dict] = {}
    notes: list[str] = []
    for e in entries:
        cd, r = e["cd"], e["results"]
        last = r["years"][-1]
        k, pnl, inp = r["kpis"], r["pnl"], r["inputs"]
        cap, dp = capital_returns(r, cd, ke_pct), dupont(r, cd)
        ti = float(pnl.loc["Total_Income", last])
        emp = float(inp.loc["EMP_COST", last])
        col = {
            "period": cd["period_labels"][-1], "n_years": len(r["years"]), "source": str(cd.get("source", "")).title(),
            "ti": ti, "gva": float(pnl.loc["GVA", last]), "pat_attr": float(r["pat_attr"].iloc[-1]),
            "gva_margin": float(k.loc["GVA_Margin_Pct", last]), "ebitda_margin": float(k.loc["EBITDA_Margin_Pct", last]),
            "pat_margin": float(k.loc["PAT_Margin_Pct", last]),
            "emp_share": (emp / ti * 100.0) if (emp > 0 and ti > 0) else np.nan,
            "va_emp": float(k.loc["Value_Added_Per_Emp_Lakhs", last]),
            "roce": float(k.loc["ROCE_Pct", last]), "roe": float(k.loc["ROE_Pct", last]),
            "cod": float(k.loc["Implied_Cost_of_Debt_Pct", last]), "icr": float(k.loc["Interest_Coverage_Ratio", last]),
            "nm": float(dp["values"]["NM"][-1]), "at": float(dp["values"]["AT"][-1]), "em": float(dp["values"]["EM"][-1]),
            "roic": float(cap["ROIC"][-1]), "wacc": float(cap["WACC"][-1]), "eva": float(cap["EVA"][-1]),
            "rev_cagr": float(r["cagr"]["Revenue_CAGR_Pct"]), "pat_cagr": float(r["cagr"]["PAT_Attr_CAGR_Pct"]),
        }
        columns[e["name"]] = col
    labels = [lab for _k, lab, _u in COMPARE_ROWS]
    frame = pd.DataFrame({name: [col[key] for key, _l, _u in COMPARE_ROWS] for name, col in columns.items()}, index=labels, dtype="object")
    units = {lab: unit for _k, lab, unit in COMPARE_ROWS}

    srcs = {str(e["cd"].get("source")) for e in entries}
    if len(srcs) > 1:
        notes.append("The companies use different data sources (Yahoo and Screener), whose definitions differ slightly. Differences of a few percent can be definitional.")
    wins = {len(e["results"]["years"]) for e in entries}
    if len(wins) > 1:
        notes.append("The companies are analysed over different numbers of years, so the growth rates are not over the same span.")
    emp_flags = {str(e["cd"].get("emp_status")) for e in entries}
    if len(emp_flags) > 1:
        notes.append("Employee cost is reported for one company but not the other, so workforce metrics are not like-for-like.")
    ends = {e["cd"]["period_labels"][-1] for e in entries}
    if len(ends) > 1:
        notes.append("The latest year-ends differ, so the figures are not for the same period.")
    banks = [e["name"] for e in entries if e["cd"].get("is_financial")]
    if banks:
        notes.append("Bank or financial company in the comparison (" + ", ".join(banks) + "): ROCE, DuPont and EVA are indicative only and not comparable with non-financials.")
    return {"frame": frame, "units": units, "notes": notes}