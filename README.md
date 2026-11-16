<div align="center">

# MEROS (μέρος) 🧾
### Corporate Value-Added Statement, Common-Size Anatomy & Stakeholder Economics Engine

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://streamlit.io)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Sovereign Bullion & Carbon Ledger](https://img.shields.io/badge/Aesthetic-Sovereign%20Gold%20%26%20Carbon-gold)](https://github.com)

**MEROS** (Greek: *μέρος* - Portion, Share & Stakeholder Allotment) is an institutional-grade financial engineering terminal built in Python (`Streamlit`, `Pandas`, `NumPy`, `Plotly`) that bridges everyday consumer curiosity with rigorous strategic finance. It transforms public corporate filings into an interactive visual analysis of economic value creation and its 5-way distribution across stakeholders.

</div>

---

##  Core Architectural Pillars

Standard financial platforms view enterprises strictly through an equity investor lens—treating workforce salaries, statutory taxes, and vendor payouts merely as expenses to be minimized. **MEROS** evaluates a corporation as a **value-creation and distribution engine** across competing economic claimants:

1. **Supply Chain & Vendors** (Cost of Materials, Freight, Power, Outsourcing)
2. **Workforce & Human Capital** (Salaries, Benefits, PF, Gratuity)
3. **Capital Providers — Debt & Deposits** (Banks, Bondholders, Lenders)
4. **The State / Exchequer** (Corporate Income Tax, Statutory Levies)
5. **Capital Providers — Equity & Enterprise Retention** (Dividends + Retained Earnings + Depreciation Reinvestment Buffer)

---

## Key Analytical Modules (5-Tab Interactive Terminal)

* **Tab 1: The ₹100 Consumer Anatomy ("Where Does Your Money Go?")**  
  * Traces every ₹100 of customer spending from top-line revenue down through raw materials, logistics, workforce, wear-and-tear, lenders, taxes, and net shareholder retention.
  * Features interactive waterfall charts and itemized thermal receipt vouchers.
* **Tab 2: Stakeholder Value-Added Statement (VAS) & 3-Year Drift**  
  * Computes Gross Value Added (`GVA = Total Income - Bought-In Goods & Services`) and Net Value Added (`NVA`).
  * Reconciles distribution shares across the 5 stakeholder groups with **100% mathematical closure** ($\text{GVA} = \sum \text{Stakeholders}$).
  * Includes a deterministic Python Rule-Based Diagnostic Engine that classifies enterprise archetypes and flags wage-vs-owner drift.
* **Tab 3: Workforce Productivity & Capital Efficiency Terminal**  
  * Evaluates human capital return on investment (`Human Capital ROI`), value added per employee, and average cost per employee.
  * Analyzes capital returns (`ROCE`, `ROE`) against the `Implied Cost of Debt` to visualize positive economic spread and calculate the `Interest Coverage Ratio (ICR)`.
* **Tab 4: Macroeconomic & Inflation Pass-Through Shock Simulator**  
  * Interactive macro sliders allowing users to stress-test raw material inflation, wage hikes, and interest rate basis-point shocks.
  * Models consumer price pass-through elasticity to evaluate margin compression and compute break-even price hikes required to protect target ROE.
* **Tab 5: Glass-Box Formula Audit & Reconciliation Verifier**  
  * Live mathematical closure verifier comparing vectorized engine outputs against independent step-by-step hand calculations within a strict $\vert{}variance\vert{} < 0.0001$ tolerance.
  * Exposes the data hygiene repair log and clean, production-grade vectorized Python source formulas.

---

## Live NSE/BSE Ticker Scraping (`yfinance`)

In addition to pre-loaded Indian enterprise archetypes (FMCG, IT, Auto, Q-Commerce) and custom Schedule III `.csv`/`.xlsx` uploads, **MEROS** features a live ingestion engine powered by `yfinance`. 
* Type any NSE/BSE ticker symbol (e.g., `RELIANCE.NS`, `TCS.NS`, `HDFCBANK.NS`, `ZOMATO.NS`, `TATAMOTORS.NS`) in the sidebar.
* Automatically fetches audited annual statements, converts absolute rupees into ₹ Crores, maps banking (Form B) or manufacturing (Schedule III) lines, and reconciles operating expenses algebraically to guarantee zero-variance VAS closure.
* Includes an interactive Schedule III Verification & Override Grid (`st.data_editor`) for instant line-item tuning.

---

## Technical Stack & Design System

* **Frontend & UI Shell:** Streamlit with custom CSS injecting the **"Sovereign Bullion & Carbon Ledger"** aesthetic.
  * *Color Palette:* Deep Warm Carbon Obsidian (`#0A0A0C`), Smoked Onyx surfaces (`#111215`), and Burnished Sovereign Gold accents (`#E5A93C`).
  * *Typography:* `'Instrument Serif'` (editorial italic accents), `'Plus Jakarta Sans'` (UI hierarchy), and `'JetBrains Mono'` (tabular financial data & receipt vouchers).
  * *Interactions:* Emil Design Engineering smooth hover physics (`cubic-bezier(0.22, 1, 0.36, 1)`) and specular top-edge borders.
* **Calculation Engine:** Vectorized NumPy & Pandas operations optimized for high-performance financial data modeling.
* **Visualizations:** Plotly Interactive Charts with dark obsidian tooltips and custom semantic color tokens.

---

## Project Repository Structure

```text
MEROS/
├── .streamlit/
│   └── config.toml                  # Cupertino OLED dark glass theme & primary colors
├── app.py                           # Unified Streamlit UI, Bento grid, & 5 interactive tabs
├── corporate_engine.py              # Vectorized Pandas sanitizer, VAS engine, & shock simulator
├── benchmark_generator.py           # Pre-loaded public archetypes & live yfinance scraper
├── sample_corporate_statement.csv   # Default downloadable template
├── requirements.txt                 # Production cloud dependencies
├── LICENSE                          # MIT Open-Source License
└── README.md                        # Project documentation
