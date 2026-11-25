<div align="center">

# MEROS (μέρος) 🧾
### Corporate Value-Added Statement, Stakeholder Economics, DuPont & EVA Terminal

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://merosfin.streamlit.app)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Architecture: Modular v2](https://img.shields.io/badge/Architecture-MEROS%20v2-E5A93C)](https://github.com/dinudennyculas/MEROS)

**MEROS** (Greek: *μέρος* — Portion, Share & Stakeholder Allotment) is an interactive corporate financial analytics terminal built in Python (`Streamlit`, `Pandas`, `NumPy`, `Plotly`, `openpyxl`). It ingests live NSE/BSE filings from Yahoo Finance and multi-year Screener.in Excel exports to model economic value creation, stakeholder distribution, DuPont ROE attribution, and Economic Value Added (EVA) with zero-variance accounting closure.

</div>

---

## 🌟 Core Philosophy: No Estimates, Full Auditability

Standard financial platforms view enterprises strictly through an equity-only lens. **MEROS** evaluates a corporation as a **value-creation and distribution engine** across five competing economic claimants—**Supply Chain & Vendors**, **Workforce**, **Lenders**, **The State (Exchequer)**, and **Equity & Reinvestment**—while enforcing strict accounting transparency:

* **Zero Silent Estimation:** Missing items (such as unreported employee cost or headcount) are explicitly flagged as `Not reported` rather than guessed or back-filled.
* **Zero-Variance Closure:** Every statement is algebraically reconciled against source anchors (`PBT`, `PAT Attributable`, and minority-interest adjustments `attr_adj`) so $\text{GVA} = \sum \text{Stakeholders}$ and the ₹100 consumer receipt always sums to `₹100.00`.
* **Dynamic History Windows:** Analyze 3, 4, 5, 10, or all available fiscal years, automatically using the prior year-end balance sheet as the opening balance for average-balance returns.

---

## 📊 Analytical Modules (6-Tab Interactive Terminal)

* **Tab 1 — ₹100 Consumer Anatomy ("Where Does Your Money Go?")**  
  Traces every ₹100 of customer spending from revenue through suppliers, workforce, depreciation, lenders, taxes, and shareholder retention via interactive waterfall charts and itemized thermal receipt vouchers.
* **Tab 2 — Stakeholder Value-Added Statement (VAS)**  
  Computes Gross Value Added (`GVA`) and Net Value Added (`NVA`) across all selected years with exact closure checks, an attributable-profit memo row after minority interest, and a deterministic diagnostic engine flagging stakeholder drift.
* **Tab 3 — Workforce, Capital Returns, DuPont & EVA**  
  * **Capital Efficiency:** Average-balance `ROE`, `ROCE`, `ROIC`, `WACC`, and `Interest Coverage Ratio (ICR)`.
  * **DuPont Decomposition:** Exact 3-step and 5-step DuPont tables with log-mean ROE-change attribution showing which factor drove ROE movement between the first and last year.
  * **Economic Value Added (EVA):** Full EVA schedule, capital charge, and ROIC vs. WACC spread charts driven by a configurable Cost of Equity.
* **Tab 4 — Macroeconomic & Inflation Pass-Through Shock Simulator**  
  Interactive stress-testing sliders for raw material inflation, wage hikes, interest rate shocks, and price pass-through elasticity, displaying post-shock PAT, ROE, break-even price hikes, and before/after ₹100 receipts.
* **Tab 5 — Glass-Box Audit, Provenance & Assumptions Register**  
  * Independent verification of 5 core accounting identities (`|variance| < 0.0001`).
  * Source reconciliation bridge (Yahoo / Screener) and cross-source consistency checks.
  * Cell-level data provenance table, automated data-health checks, raw untouched source statements, and a live Assumptions Register (`ACTIVE` / `ALWAYS ON` / `NOT TRIGGERED`).
* **Tab 6 — Peer Company Comparison**  
  Side-by-side benchmarking against any second NSE-listed company fetched live, comparing ratios, DuPont drivers, EVA, and ROE trajectories with automatic like-for-like mismatch warnings.

---

## 🚀 Data Ingestion & Live Excel Export

* **Live NSE Directory & Yahoo Finance (`yfinance`):** Search 2,600+ NSE-listed equities via `data/EQUITY_L.csv` with automatic rename hints (e.g., `ZOMATO` → `ETERNAL`) and recent-listing checks.
* **Screener.in `.xlsx` Parser:** Upload any Screener.in Excel export (Consolidated or Standalone) for up to 10 years of history. Automatically detects inventory-change sign conventions and runs a real cost check rebuilding `PBT` within ₹0.5 Cr.
* **Interactive Override Grid:** Edit line items directly in the app with automatic operating-expense rebalancing to preserve accounting closure.
* **Multi-Sheet Excel Workbook Export (`openpyxl`):** Download a formatted `.xlsx` report containing live Excel formulas on the **EVA** and **DuPont** sheets (edit the yellow Cost of Equity input cell to recalculate live), paired with stored fallback values and full audit/raw sheets.

---

## 📂 Project Repository Structure

```text
MEROS/
├── .streamlit/
│   └── config.toml          # Theme configuration
├── data/
│   └── EQUITY_L.csv         # NSE listed equity directory
├── app.py                   # Main Streamlit shell, sidebar, routing & Excel download
├── corporate_engine.py      # Vectorized sanitizer, VAS engine, shock simulator & diagnostics
├── analytics.py             # History windows, DuPont (3/5-step), EVA, health checks & compare
├── excel_export.py          # Multi-sheet openpyxl workbook builder with live formulas
├── meros_assumptions.py     # Structured assumptions register & metadata
├── tickers.py               # NSE ticker loader, fuzzy search & rename/listing hints
├── yahoo_source.py          # Live Yahoo Finance fetcher & standard data-package builder
├── screener_source.py       # Screener.in Excel parser, cost check & Yahoo cross-check
├── ui_style.py              # Sovereign Gold & Carbon CSS, Indian formatters & disclaimer badge
├── tabs_core.py             # Tabs 1–3 (Receipt, VAS, Workforce/Capital/DuPont/EVA)
├── tabs_more.py             # Tabs 4–6 (Shock Simulator, Audit/Provenance, Peer Compare)
├── meros_icon.png           # Custom browser favicon
├── requirements.txt         # Production dependencies
├── LICENSE                  # MIT Open-Source License
└── README.md                # Project documentation
```

---

## ⚙️ Local Setup

```bash
git clone [https://github.com/dinudennyculas/MEROS.git](https://github.com/dinudennyculas/MEROS.git)
cd MEROS
pip install -r requirements.txt
streamlit run app.py
```

---

## ⚠️ Disclaimer & Data Attribution

MEROS is an **educational and academic financial analysis tool** built by Dinu Denny Culas. It is **not investment advice**, nor a recommendation to buy, sell, or hold any security. Live market statements are sourced via Yahoo Finance (`yfinance`), optional user-uploaded exports are parsed from Screener.in, and the NSE equity list (`EQUITY_L.csv`) is sourced from the National Stock Exchange of India. All third-party data remains the property of its respective providers.