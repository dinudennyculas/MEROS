"""MEROS static text and tiny helpers: disclaimer, history options, Screener guide, and the Assumptions Register.

No calculations live here. Other modules import these constants so the wording is identical everywhere
(app, Excel export, assumptions tab)."""
from __future__ import annotations

from urllib.parse import quote, quote_plus

APP_NAME = "MEROS"
CREATOR = "Dinu Denny Culas"

# --------------------------------------------------------------------------------------
# History window options. The number is how many recent annual periods to analyse; 0 means "all available".
# --------------------------------------------------------------------------------------
HISTORY_OPTIONS: list[tuple[str, int]] = [
    ("Last 3 years", 3),
    ("Last 4 years", 4),
    ("Last 5 years", 5),
    ("Last 10 years", 10),
    ("Since inception (all available years)", 0),
]
MIN_YEARS = 3
YAHOO_TYPICAL_MAX_YEARS = 4
DEFAULT_COE_PCT = 12.0
SCREENER_KNOWN_VERSIONS = ("2.1",)

# --------------------------------------------------------------------------------------
# Disclaimer
# --------------------------------------------------------------------------------------
DISCLAIMER_BADGE = "Educational & academic tool · not investment advice · data may be inaccurate"

DISCLAIMER_FULL = (
    "MEROS is an educational and academic analytical tool. It is not investment, tax, legal or accounting advice, and it does not "
    "recommend buying, holding or selling any security. "
    "The financial data comes from third parties (Yahoo Finance through the yfinance library, and Screener Excel exports that you "
    "download and upload yourself). It may be incomplete, delayed, restated or wrong, so always verify against the company's official "
    "filings. Where a figure is estimated, derived or defaulted, it is flagged in the app and explained in the Assumptions Register. "
    "The author accepts no liability for any loss, damage or decision arising from the use of this tool or its outputs. "
    "MEROS is not affiliated with, endorsed by or connected to NSE, BSE, Yahoo, Screener or any listed company."
)

DISCLAIMER_EXCEL = (
    "Educational and academic tool, not investment, tax, legal or accounting advice. Data comes from third parties (Yahoo Finance, "
    "Screener exports) and may be incomplete or inaccurate; verify with official filings. The author accepts no liability for decisions "
    "based on this file."
)

DATA_SOURCES_NOTE = (
    "Sources: Yahoo Finance (live, usually the latest three to four annual periods) and Screener.in Excel exports uploaded by the user "
    "(typically about ten years). MEROS does not scrape any website and stores no company data."
)

# --------------------------------------------------------------------------------------
# Screener download guide
# --------------------------------------------------------------------------------------


def screener_company_url(symbol: str, version: str = "consolidated") -> str:
    slug = quote(str(symbol).strip().upper(), safe="&-")
    ver = "consolidated" if version.lower().startswith("cons") else "standalone"
    return f"https://www.screener.in/company/{slug}/{ver}/"


def google_search_url(symbol: str) -> str:
    return "https://www.google.com/search?q=" + quote_plus(f"{str(symbol).strip().upper()} screener")


def screener_steps(symbol: str, version: str = "consolidated") -> list[tuple[str, str]]:
    """Step-by-step instructions (title, detail) for getting a Screener Excel export of the typed company."""
    sym = str(symbol).strip().upper() or "your company"
    return [
        ("Open the company page on Screener",
         f"Use the link below, or search Google for '{sym} screener'. The page address looks like {screener_company_url(sym, version)}"),
        ("Choose Consolidated or Standalone",
         "Screener shows a Consolidated / Standalone switch near the top of the page. Pick one and remember it: MEROS asks which version you "
         "downloaded. Consolidated includes subsidiaries; Standalone is the parent company only."),
        ("Log in if Screener asks",
         "Screener may ask you to sign in before it lets you export. A free account is enough. Use your own account and follow Screener's terms."),
        ("Click the download icon",
         "At the top of the company page, next to the Follow button, click the download icon (Export to Excel). Save the .xlsx file to your device."),
        ("Upload the file here",
         "Come back to MEROS and drop the .xlsx file into the upload box. MEROS reads its 'Data Sheet' tab, checks the numbers against each other "
         "and then runs the full analysis."),
    ]


SCREENER_STEPS_NOTE = (
    "Screener's page layout and button names can change. If you cannot find the download icon, look for 'Export to Excel' near the company name. "
    "MEROS is not affiliated with Screener."
)

# --------------------------------------------------------------------------------------
# Assumptions Register: (id, scope, area, assumption, why it is needed, effect and how to override)
# scope: "Yahoo" | "Screener" | "All"
# --------------------------------------------------------------------------------------
SCOPE_TITLES = {
    "Yahoo": "WHEN THE DATA COMES FROM YAHOO FINANCE (LIVE)",
    "Screener": "WHEN THE DATA COMES FROM A SCREENER EXCEL UPLOAD",
    "All": "EVERY DATA SOURCE · ENGINE-WIDE",
}

ASSUMPTION_REGISTER: list[tuple[str, str, str, str, str, str]] = [
    # ------------------------------------------------------------------ Yahoo
    ("Y01", "Yahoo", "Units and currency",
     "Yahoo's amounts are treated as Indian rupees. Every amount is divided by 10,000,000 and rounded to 2 decimals to give ₹ Crores.",
     "Yahoo returns absolute currency units while Indian filings use crores (1 Cr = 10 million). The currency is read from Yahoo's 'financialCurrency' tag.",
     "Exact for INR reporters. A non-INR tag raises a warning, but nothing is converted, so the scale would be wrong."),
    ("Y02", "Yahoo", "Years returned",
     "MEROS uses every annual period Yahoo returns with at least three populated income-statement lines, usually the latest three to four.",
     "Yahoo exposes only a short annual history and sometimes adds an empty latest column. Sparse columns would distort ratios.",
     "More than about four years is not available from Yahoo. For 5 years, 10 years or since inception, upload a Screener export."),
    ("Y03", "Yahoo", "Statement alignment",
     "Balance-sheet and cash-flow columns are matched to income-statement periods by nearest date, within 45 days.",
     "Yahoo serves the three statements as separate tables whose columns do not always line up.",
     "A year with no match shows the item as not reported. It is visible and editable in the override grid."),
    ("Y04", "Yahoo", "Revenue line",
     "Revenue from operations = 'Operating Revenue', else 'Total Revenue', else 'Interest Income' (banks).",
     "Yahoo's rows follow a global taxonomy, not Schedule III. Banks have no operating revenue, so interest income is the nearest top line.",
     "A bank's gross interest income is not comparable with a manufacturer's sales."),
    ("Y05", "Yahoo", "Other income",
     "Other income = Yahoo's 'Other Income Expense' or 'Non Operating Income Net Other' if positive, otherwise Total Revenue minus Operating Revenue (never below 0).",
     "Yahoo has no clean 'Other income' row, and those lines are net figures that can include non-operating expenses.",
     "Other income can be over- or under-stated. Pretax income is unaffected because the balancing figure (Y08) absorbs the difference."),
    ("Y06", "Yahoo", "Cost of revenue as 'materials'",
     "Cost of materials = Yahoo's 'Cost Of Revenue' (0 if absent).",
     "It is the nearest Yahoo row to 'materials and stock-in-trade'.",
     "Not Schedule III. In IT-services filings it often contains people cost, and for banks it is absent."),
    ("Y07", "Yahoo", "Employee cost (no estimates)",
     "Employee cost is read only from Yahoo rows that name it (such as 'Salaries And Wages'). If Yahoo has no such row, it is shown as NOT REPORTED and nothing is estimated.",
     "A rule-of-thumb payroll figure would look like data but is a guess. MEROS prefers an honest blank.",
     "When payroll is missing, it stays inside 'other operating expenses' (Y08), so GVA is understated and workforce metrics are not meaningful. Upload a Screener export, which has an Employee Cost line, or type the figure into the override grid."),
    ("Y08", "Yahoo", "Other operating expenses = balancing figure",
     "Other operating expenses = (revenue + other income) − PBT − cost of materials − employee cost − depreciation − finance cost.",
     "Yahoo bundles many Schedule III lines (power, freight, marketing, provisions, exceptional items) and has no 'other expenses' row. Solving for it reproduces Yahoo's Pretax Income exactly.",
     "It absorbs every cost not otherwise classified, so it is the least observed cost line. Closure proves consistency, not that each line is right."),
    ("Y09", "Yahoo", "Negative balancing figure",
     "If the balancing figure would be negative, it is set to 0 and Other Income is raised by the shortfall.",
     "A negative expense is meaningless, and raising income keeps Pretax Income exact.",
     "Other Income is overstated in those years. The notice names the years and amounts."),
    ("Y10", "Yahoo", "Tax and the attributable-profit gap",
     "Tax = Yahoo's 'Tax Provision' (if missing, Pretax Income − Net Income). Reported 'Net Income' attributable to shareholders is kept as a separate anchor, and the gap to (Pretax − Tax) is tracked as minority interest, associates and other items.",
     "Keeping reported tax makes the Government share honest, while the attributable profit is the right numerator for ROE and DuPont.",
     "VAS retained earnings include the minority holders' share. ROE and DuPont use attributable profit. The bridge shows the gap line by line."),
    ("Y11", "Yahoo", "Depreciation source",
     "Depreciation = 'Reconciled Depreciation', else 'Depreciation And Amortization In Income Statement', else the cash-flow D&A row.",
     "Yahoo does not always populate the same row, so a fixed cascade is used.",
     "Cash-flow D&A can include items such as impairments that are not in the P&L. Marked ACTIVE only when the fallback is used."),
    ("Y12", "Yahoo", "Finance cost for banks",
     "Without an 'Interest Expense' row, finance cost = Interest Income − Net Interest Income.",
     "Net interest income is a result, not a cost. Gross interest expense is the difference, so using it directly would put income in a cost line.",
     "Exact when both rows exist; otherwise finance cost is not reported (0)."),
    ("Y13", "Yahoo", "Dividends",
     "Dividends = cash dividends paid in the cash-flow statement (absolute value), not reported (0) if missing.",
     "Yahoo has no 'declared dividend' row. The cash-flow figure is what actually left the company.",
     "Timing differs from declared dividends and can include payouts to minority holders."),
    ("Y14", "Yahoo", "Debt definition",
     "Debt = Yahoo's 'Total Debt', else long-term plus current debt.",
     "It is the closest Yahoo item to total borrowings.",
     "Total Debt can include lease liabilities (Ind AS 116). For banks, deposits are not debt, so ROCE and coverage are not comparable with non-financials."),
    ("Y15", "Yahoo", "Equity definition",
     "Equity = 'Stockholders Equity' (the parent's equity), else 'Total Equity Gross Minority Interest'.",
     "ROE uses profit attributable to the parent's shareholders, so the matching denominator is the parent's equity.",
     "The fallback includes minority interest and makes ROE slightly inconsistent. Marked ACTIVE only when used."),
    ("Y16", "Yahoo", "Headcount",
     "Headcount = Yahoo's single current 'fullTimeEmployees' figure, applied to the LATEST year only. Earlier years are not reported.",
     "Yahoo gives a snapshot, not a history. Spreading it backwards would invent numbers.",
     "Per-employee metrics are shown only for the latest year unless you type earlier headcounts into the override grid."),
    ("Y17", "Yahoo", "Banks and financial companies",
     "Banks and NBFCs are processed with the same value-added template.",
     "MEROS has one schema, and for lenders interest is both the main revenue and the main cost.",
     "Indicative only: deposits are not debt, cost of materials is 0 and gross interest income is the top line."),
    ("Y18", "Yahoo", "Opening balance sheet",
     "If Yahoo returns a balance sheet dated about twelve months before the first year used (300 to 430 days earlier), it supplies the opening balance for average-capital ratios.",
     "Average balances are more accurate than year-end balances for growing or shrinking firms.",
     "Without it, the first year's average-balance ratios show n/a. All headline ratios still use year-end balances (E05)."),
    # ------------------------------------------------------------------ Screener
    ("S01", "Screener", "Source, units and version",
     "The file is a Screener.in Excel export that YOU downloaded. Amounts are taken as ₹ Crores, as Screener presents them. You tell MEROS whether you downloaded the Consolidated or the Standalone version.",
     "The workbook does not say which version it is, so MEROS cannot detect it.",
     "Screener compiles its figures from company filings and can contain errors or restatements. Spot-check against the annual report."),
    ("S02", "Screener", "Layout read by labels",
     "MEROS reads the 'Data Sheet' tab by looking for section headings and row labels, not fixed row numbers, and warns if the layout version is not one it knows.",
     "Label reading survives small layout changes, but a different layout could still be misread.",
     "If a required row is missing, MEROS says so and falls back where possible (see S13)."),
    ("S03", "Screener", "Cost of materials and the inventory sign",
     "Cost of materials = Raw Material Cost − Change in Inventory. MEROS tests both signs of the inventory line against the reported profit-before-tax and keeps the sign that reproduces it.",
     "Screener lists the inventory change on its own line and the sign convention is not stated in the file. For the ITC file, raw material minus the change reproduced PBT in all 10 years.",
     "If neither sign reproduces PBT, the leftover goes to other operating expenses (S06) and is flagged."),
    ("S04", "Screener", "Other operating expenses",
     "Other operating expenses = Power and Fuel + Other Mfr. Exp + Selling and admin + Other Expenses.",
     "Screener splits these costs across four lines, while MEROS has one 'other operating expenses' line.",
     "The split between this line and the cost of materials is a mapping choice. It does not change profit."),
    ("S05", "Screener", "Employee cost",
     "Employee cost = Screener's 'Employee Cost' line, as Screener compiles it from the company's filing.",
     "This is the reported figure, so no estimate is needed.",
     "If the file has no Employee Cost line, it is shown as NOT REPORTED and nothing is estimated."),
    ("S06", "Screener", "Cost check against reported profit",
     "MEROS rebuilds profit-before-tax from the cost lines and compares it with Screener's own figure. Any year-level difference above ₹0.5 Cr is added to other operating expenses and flagged.",
     "Unlike Yahoo mode, nothing is plugged silently: this is a genuine test that the mapped costs add up.",
     "A flagged year means Screener's lines do not add up for that year, or the layout differs from what MEROS expects."),
    ("S07", "Screener", "Tax and attributable profit",
     "Tax = Screener's 'Tax'. 'Net profit' (profit attributable to shareholders) is kept as a separate anchor, and the gap to (PBT − Tax) is tracked as minority interest, associates and other items.",
     "Reported tax makes the Government share honest, while attributable profit is the right numerator for ROE and DuPont. In the ITC consolidated file the gap was ₹188 to ₹329 Cr a year.",
     "VAS retained earnings include the minority holders' share. ROE and DuPont use attributable profit."),
    ("S08", "Screener", "Dividends",
     "Dividends = Screener's 'Dividend Amount'.",
     "It is the dividend figure Screener provides for each year.",
     "It may differ in timing from cash dividends in the cash-flow statement."),
    ("S09", "Screener", "Debt",
     "Debt = Screener's 'Borrowings'.",
     "It is the closest line to total borrowings.",
     "It can include lease liabilities. For banks, deposits are not part of it, so credit ratios are not comparable with non-financials."),
    ("S10", "Screener", "Equity",
     "Equity = Equity Share Capital + Reserves.",
     "This is how Screener presents shareholders' funds.",
     "It is assumed to exclude minority interest, which Screener lists among other liabilities for consolidated figures."),
    ("S11", "Screener", "Total assets",
     "Total assets = the 'Total' row of the Balance Sheet block.",
     "DuPont needs total assets, and Screener's balance-sheet total is the available figure.",
     "Used only for DuPont (E13)."),
    ("S12", "Screener", "Headcount",
     "Screener has no headcount. If Yahoo also returned a current employee count, it is applied to the LATEST year only; otherwise headcount is not reported.",
     "A single snapshot cannot be spread backwards without inventing history.",
     "Per-employee metrics are shown only where headcount exists. Type earlier headcounts into the override grid if you know them."),
    ("S13", "Screener", "Banks and layouts without a cost breakdown",
     "If the file lacks the manufacturing-style cost lines, MEROS uses an aggregate 'Expenses' line as other operating expenses and employee cost shows NOT REPORTED. Bank files are best effort and untested.",
     "Screener's layout for banks and some other companies can differ from the standard one.",
     "Results for such companies are indicative. Share the file's layout if something looks wrong."),
    ("S14", "Screener", "Cross-check against Yahoo",
     "For years present in both Yahoo and the Screener file, MEROS compares revenue and attributable profit. A difference above 1% raises a flag.",
     "A large mismatch usually means Consolidated was compared with Standalone, or one source restated.",
     "A flag is a prompt to look closer, not proof that either source is wrong. Skipped if Yahoo is unavailable."),
    ("S15", "Screener", "History length and opening balance",
     "'Last N years' means the N most recent annual periods in the file. The year before the chosen window, if present, supplies the opening balance for average-capital ratios.",
     "Using the preceding year gives true average balances without extra data.",
     "'Since inception' really means 'since the earliest year in the file' (usually about ten years), and its first year has no opening balance."),
    # ------------------------------------------------------------------ All sources
    ("E01", "All", "Government share",
     "The government slice is income-tax expense only.",
     "The statements do not show GST, customs, excise or property tax collected or paid, and revenue is net of GST.",
     "It understates the state's full tax take. Read it as direct tax on profits."),
    ("E02", "All", "The '₹100 receipt' base",
     "'₹100 spent by the customer' = ₹100 of Total Income (operating revenue plus other income).",
     "The audited P&L is the only record of what customers paid the company. GST, discounts and channel margins sit outside it.",
     "Other income is treated as if it came from customers. It is a presentation device, not consumer-spending data."),
    ("E03", "All", "Entity reinvestment",
     "Entity reinvestment = retained earnings + depreciation, where retained earnings = profit after tax − dividends.",
     "GVA is gross of depreciation, so the part that stays inside the firm is retained profit plus the capital consumed.",
     "Retained earnings include the minority holders' share of profit (Y10, S07). If they are negative, this slice becomes small or negative."),
    ("E04", "All", "Retained earnings timing",
     "Retained earnings use dividends paid in the same year.",
     "Needed for exact closure without reserve movements.",
     "Dividends often relate to the previous year's profit, so single-year retention can look odd, even negative."),
    ("E05", "All", "Year-end capital base",
     "Headline ROCE, ROE and implied cost of debt use year-end balances. Average-balance versions are shown separately when an opening balance exists.",
     "A year-end base keeps every year comparable and makes the DuPont identity exact.",
     "Year-end balances overstate returns for fast-growing firms and understate them for shrinking ones."),
    ("E06", "All", "Economic spread (EVA proxy)",
     "The headline economic spread = ROCE minus implied cost of debt.",
     "A true EVA needs a cost of equity, which filings do not contain. The full version is shown separately (E11, E12).",
     "The proxy ignores the cost of equity, so a positive spread does not prove value creation."),
    ("E07", "All", "Zero-debt and zero-interest guards",
     "No debt shows 0% cost of debt, and no interest shows coverage as infinite (stored as 999).",
     "Avoids division by zero while keeping the maths vectorised.",
     "999 is a sentinel, not a real ratio."),
    ("E08", "All", "Blank cells",
     "Blank or unparseable cells in a grid you edit are treated as 0.0 and logged.",
     "A blank is more often a nil line than an unknown number, and every imputation appears in the repair log.",
     "If the blank was really unknown, that line is understated. Check the audit log."),
    ("E09", "All", "Diagnostic thresholds",
     "Diagnostic cut-offs are fixed rules of thumb, for example bought-in costs at or above 85% = thin-spread, ROCE at or above 15% = strong, interest cover below 3x = watchlist.",
     "The engine is deterministic and explainable, and there is no peer dataset here to calibrate against.",
     "They are screening labels, not ratings. Sector norms differ (banks, utilities, IT)."),
    ("E10", "All", "Shock simulator",
     "A one-period, static what-if on the latest year: volumes and other costs do not react, the materials shock hits cost of materials only, wages hit employee cost, the rate shock hits year-end debt, price pass-through lifts operating revenue only, dividends stay constant, and tax uses the latest effective rate if PBT is positive.",
     "A transparent first-order sensitivity needs a fixed rule set. Behavioural responses need data we do not have.",
     "Real outcomes will differ. Use it for sensitivity, not forecasting. If employee cost is not reported, the wage shock has no effect."),
    ("E11", "All", "Cost of equity input",
     "Full EVA uses a cost of equity that YOU type in the sidebar (default 12%).",
     "Filings contain no cost of equity: it needs a risk-free rate, a beta and an equity premium. 12% is only an illustrative round figure; no market data was used.",
     "EVA moves strongly with this input. Read it as 'what if my required return is X%'."),
    ("E12", "All", "How full EVA is built",
     "NOPAT = EBIT × (1 − tax rate), with tax rate = reported tax ÷ PBT clipped between 0% and 40%. WACC uses year-end book-value weights and the after-tax implied cost of debt. Capital charge = WACC × year-end capital employed.",
     "Market values of equity are not in the statements, so book weights are the only source-consistent choice. Clipping stops a distorted tax rate from producing absurd NOPAT.",
     "Book weights understate equity for companies trading well above book, so WACC is probably too low for them. Not meaningful for banks."),
    ("E13", "All", "DuPont definitions",
     "3-step: ROE = net margin × asset turnover × equity multiplier. 5-step splits net margin into tax burden × interest burden × EBIT margin. Net profit is attributable profit, income is total income, EBIT = PBT + finance cost, and assets and equity are year-end figures.",
     "Using one consistent year-end base makes the identity exact, so the product of the factors equals ROE.",
     "Different definitions (average balances, operating revenue only) give different splits. Not meaningful for banks. No industry comparison is included (E22)."),
    ("E14", "All", "Data-health screens",
     "The automated checks use fixed heuristics, such as employee cost above 60% of income (75% for IT), revenue swings beyond +100% or −50%, filings older than 15 months, period gaps outside 330 to 400 days, dividends above profit, tax rates outside 0 to 45%, and other income above 25% of income.",
     "They are rough tripwires for common data problems, chosen from general experience, not calibrated on a dataset.",
     "A flag means 'look closer', not 'wrong'. No flag does not mean the data is audited."),
    ("E15", "All", "Plain-English text",
     "The summary and KPI notes are filled in from templates using the numbers on screen. No AI or external service writes them.",
     "Deterministic wording keeps every sentence traceable to a number.",
     "Simplified statements are not advice and can hide nuance. The tables are authoritative."),
    ("E16", "All", "Shareable link",
     "The page address stores only your selections (company, years, version, cost of equity), never the data.",
     "Anyone opening the link re-fetches Yahoo data themselves, so no financial data is sent anywhere by the link.",
     "Results can differ if Yahoo revises data. Uploaded files cannot be shared by link."),
    ("E17", "All", "Company comparison",
     "The Compare tab applies the same history window and settings to both companies.",
     "A like-for-like comparison needs one rule set.",
     "If one company's source or reported employee cost differs from the other's, workforce differences are partly an artefact. The tab flags this."),
    ("E18", "All", "Excel export",
     "The Excel file is a snapshot of what is on screen when you click download, including edits and settings. EVA and DuPont sheets contain live formulas plus stored values.",
     "A reproducible record with its assumptions and sources included.",
     "Formulas recalculate when opened in Excel. Some viewers show only the stored values. Source data may be revised later."),
    ("E19", "All", "History window and growth rates",
     "The window is the N most recent annual periods available. Growth rates (CAGR) run from the first to the last year of the window.",
     "A fixed rule makes results repeatable.",
     "A short window can hide a long-run trend, and a long one can mix business models after mergers or demergers (see the health screens)."),
    ("E20", "All", "Fiscal-year labels",
     "A period ending April to December of year X is labelled FY(X+1), and one ending January to March of year X is labelled FY(X): the Indian April-to-March convention. The real period-end date is always shown.",
     "Annual periods need consistent labels across companies.",
     "Companies with other year-ends are mapped to the Indian year in which their period ends. A transition period of other than twelve months is flagged."),
    ("E21", "All", "'Not reported' versus zero",
     "A line marked NOT REPORTED means the source has no such row. The engine uses 0 for the arithmetic, but dependent metrics are flagged or hidden.",
     "Silently treating a missing figure as a true zero would mislead, and guessing would mislead more.",
     "Check provenance (Tab 5) before relying on any workforce, headcount or per-employee figure."),
    ("E22", "All", "No industry comparison",
     "MEROS does not compare a company against industry averages.",
     "Free, reliable industry averages for Indian sectors are not available, and a made-up benchmark would be misleading.",
     "Use the Compare tab to place two companies side by side, and add industry data yourself from a source you trust."),
]


def assumption_state(scope: str, rid: str, status_map: dict | None, active_source: str | None) -> str:
    """Label shown beside each register row.

    scope: 'Yahoo' | 'Screener' | 'All'; active_source: 'yahoo' | 'screener' | None;
    status_map: {id: 'active' | 'always' | 'inactive'} produced by the data module for the company on screen.
    """
    if scope == "All":
        return "ALWAYS ON"
    mine = {"yahoo": "Yahoo", "screener": "Screener"}.get(str(active_source or "").lower())
    if mine is None or scope != mine:
        return "OTHER SOURCE"
    state = (status_map or {}).get(rid, "inactive")
    return {"active": "ACTIVE", "always": "ALWAYS ON"}.get(state, "NOT TRIGGERED")