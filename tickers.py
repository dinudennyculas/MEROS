"""MEROS ticker helpers: load the NSE equity list (EQUITY_L.csv), build the typable dropdown, normalise symbols.

Pure pandas / NumPy, no network and no Streamlit. Never raises on a missing or broken list: it returns an empty
list plus a plain-English status so the app can fall back to a typed symbol."""
from __future__ import annotations

import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

TICKER_FILE_NAME = "EQUITY_L.csv"
LABEL_SEP = " — "
DEFAULT_SYMBOL = "ITC"
SYMBOL_RE = re.compile(r"^[A-Z0-9&_\-]+$")

# Symbols that changed after a rename or restructuring (verified against the NSE list supplied with MEROS).
RENAMED_HINTS: dict[str, list[str]] = {
    "ZOMATO": ["ETERNAL"],
    "TATAMOTORS": ["TMPV", "TMCV"],
}

EMPTY_COLUMNS = ["symbol", "name", "series", "isin", "listing_date", "face_value", "label"]


# --------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------
def find_ticker_file(path: str | Path | None = None) -> Path | None:
    """Look for EQUITY_L.csv: the given path, then data/ next to this file, next to this file, data/ and the folder you ran from."""
    candidates: list[Path] = []
    if path:
        p = Path(path)
        candidates.append(p / TICKER_FILE_NAME if p.is_dir() else p)
    here = Path(__file__).resolve().parent
    for base in (here / "data", here, Path.cwd() / "data", Path.cwd()):
        candidates.append(base / TICKER_FILE_NAME)
    for c in candidates:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        raw = pd.read_csv(path, dtype=str, skipinitialspace=True, encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw = pd.read_csv(path, dtype=str, skipinitialspace=True, encoding="latin-1")
    raw.columns = [str(c).strip().upper() for c in raw.columns]
    return raw


@lru_cache(maxsize=4)
def _load_cached(path_str: str, mtime_ns: int) -> pd.DataFrame:
    raw = _read_csv(Path(path_str))
    if "SYMBOL" not in raw.columns or "NAME OF COMPANY" not in raw.columns:
        raise ValueError("The file must have SYMBOL and NAME OF COMPANY columns.")

    def col(name: str) -> pd.Series:
        return raw[name].astype(str).str.strip() if name in raw.columns else pd.Series([""] * len(raw), index=raw.index)

    df = pd.DataFrame({
        "symbol": col("SYMBOL").str.upper(),
        "name": col("NAME OF COMPANY"),
        "series": col("SERIES"),
        "isin": col("ISIN NUMBER"),
        "listing_date": pd.to_datetime(col("DATE OF LISTING"), format="%d-%b-%Y", errors="coerce"),
        "face_value": col("FACE VALUE"),
    })
    df = df[(df["symbol"] != "") & (df["symbol"].str.lower() != "nan") & (df["name"] != "")]
    df = df.drop_duplicates(subset="symbol", keep="first").sort_values("symbol").reset_index(drop=True)
    df["label"] = df["symbol"] + LABEL_SEP + df["name"]
    return df[EMPTY_COLUMNS]


def load_tickers(path: str | Path | None = None) -> tuple[pd.DataFrame, str]:
    """Return (ticker table, status message). The table is empty (but has the right columns) if the file is missing or unreadable."""
    found = find_ticker_file(path)
    if found is None:
        return (pd.DataFrame(columns=EMPTY_COLUMNS),
                f"The NSE company list was not found. Put {TICKER_FILE_NAME} in a 'data' folder next to app.py "
                "(download it from the NSE website) or type a symbol below.")
    try:
        df = _load_cached(str(found.resolve()), found.stat().st_mtime_ns).copy()
    except Exception as exc:  # noqa: BLE001
        return pd.DataFrame(columns=EMPTY_COLUMNS), f"Could not read {found.name}: {exc}. You can still type a symbol below."
    if df.empty:
        return df, f"{found.name} contains no usable rows. You can still type a symbol below."
    stamp = datetime.fromtimestamp(found.stat().st_mtime).strftime("%d %b %Y")
    return df, f"NSE list loaded: {len(df):,} companies from {found.name} (file dated {stamp}). Newer listings may be missing."


# --------------------------------------------------------------------------------------
# Dropdown helpers
# --------------------------------------------------------------------------------------
def options(df: pd.DataFrame) -> list[str]:
    """Dropdown labels like 'ITC — ITC Limited', sorted by symbol."""
    return df["label"].tolist() if len(df) else []


def label_to_symbol(df: pd.DataFrame, label: str) -> str:
    """Symbol for a dropdown label (falls back to the text before the separator)."""
    if len(df):
        hit = df.loc[df["label"] == label, "symbol"]
        if len(hit):
            return str(hit.iloc[0])
    return str(label).split(LABEL_SEP)[0].strip().upper()


def symbol_to_label(df: pd.DataFrame, symbol: str) -> str | None:
    if not len(df):
        return None
    hit = df.loc[df["symbol"] == str(symbol).strip().upper(), "label"]
    return str(hit.iloc[0]) if len(hit) else None


def default_index(df: pd.DataFrame, symbol: str = DEFAULT_SYMBOL) -> int:
    """Position of `symbol` in the dropdown (0 if absent)."""
    if not len(df):
        return 0
    pos = np.flatnonzero((df["symbol"] == str(symbol).strip().upper()).to_numpy())
    return int(pos[0]) if pos.size else 0


def symbol_info(df: pd.DataFrame, symbol: str) -> dict | None:
    """Name, series, ISIN and listing date for a symbol, or None if it is not in the list."""
    if not len(df):
        return None
    hit = df.loc[df["symbol"] == str(symbol).strip().upper()]
    if hit.empty:
        return None
    r = hit.iloc[0]
    ld = r["listing_date"]
    return {"symbol": str(r["symbol"]), "name": str(r["name"]), "series": str(r["series"]), "isin": str(r["isin"]),
            "listing_date": None if pd.isna(ld) else pd.Timestamp(ld)}


def suggest(df: pd.DataFrame, query: str, limit: int = 6) -> list[str]:
    """Closest dropdown labels for free text (exact symbol, symbol or name prefix, then name or symbol contains)."""
    q = str(query or "").strip().lower()
    if not len(df) or len(q) < 2:
        return []
    sym, nm = df["symbol"].str.lower(), df["name"].str.lower()
    score = np.full(len(df), 9, dtype=int)
    score = np.where(sym.str.contains(q, regex=False), 4, score)
    score = np.where(nm.str.contains(q, regex=False), 3, score)
    score = np.where(nm.str.startswith(q), 2, score)
    score = np.where(sym.str.startswith(q), 1, score)
    score = np.where(sym == q, 0, score)
    hit = score < 9
    if not hit.any():
        return []
    cand = df.loc[hit, ["symbol", "label"]].assign(_s=score[hit]).sort_values(["_s", "symbol"]).head(limit)
    return cand["label"].tolist()


# --------------------------------------------------------------------------------------
# Symbol normalisation
# --------------------------------------------------------------------------------------
def clean_symbol(raw: str) -> str:
    """Plain NSE/BSE symbol: whitespace removed, upper-cased, '.NS' / '.BO' suffix dropped. Raises ValueError if unusable."""
    s = re.sub(r"\s+", "", str(raw or "")).upper()
    if s.endswith(".NS") or s.endswith(".BO"):
        s = s[:-3]
    if not s:
        raise ValueError("Enter a ticker symbol, for example ITC, TCS or HDFCBANK.")
    if not SYMBOL_RE.match(s):
        raise ValueError(f"'{raw}' is not a valid NSE/BSE ticker symbol (letters, digits, & and - only).")
    return s


def exchange_of(raw: str) -> str:
    """'BO' if the text ends with .BO (BSE), otherwise 'NS' (NSE)."""
    return "BO" if re.sub(r"\s+", "", str(raw or "")).upper().endswith(".BO") else "NS"


def to_yahoo_symbol(raw: str) -> str:
    """Yahoo Finance symbol: ITC -> ITC.NS, m&m -> M&M.NS, RELIANCE.BO stays RELIANCE.BO."""
    return f"{clean_symbol(raw)}.{exchange_of(raw)}"


# --------------------------------------------------------------------------------------
# Friendly notes for the UI
# --------------------------------------------------------------------------------------
def rename_hint(raw: str, df: pd.DataFrame | None = None) -> str:
    """Message for renamed tickers, or for a symbol that is not on the NSE list. Empty string when there is nothing to say."""
    try:
        sym = clean_symbol(raw)
    except ValueError:
        return ""
    if sym in RENAMED_HINTS:
        new = " or ".join(RENAMED_HINTS[sym])
        return f"{sym} was renamed or restructured. Try {new} instead."
    if df is not None and len(df) and exchange_of(raw) == "NS" and sym not in set(df["symbol"]):
        close = suggest(df, sym, 3)
        extra = " Closest matches: " + "; ".join(close) + "." if close else ""
        return f"{sym} is not on the loaded NSE list, so it may be misspelt, renamed or newly listed.{extra}"
    return ""


def listing_note(df: pd.DataFrame, raw: str, today: pd.Timestamp | None = None) -> str:
    """Warning for companies listed less than about three years ago (Yahoo cannot have three annual statements for them)."""
    try:
        sym = clean_symbol(raw)
    except ValueError:
        return ""
    info = symbol_info(df, sym)
    if not info or info["listing_date"] is None:
        return ""
    now = today if today is not None else pd.Timestamp.today().normalize()
    age_days = int((now - info["listing_date"]).days)
    if age_days < 3 * 365 + 120:
        return (f"{info['name']} was listed on {info['listing_date']:%d %b %Y}, only {max(age_days, 0) // 30} months ago, "
                "so three full annual statements may not exist yet.")
    return ""