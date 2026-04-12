"""
Utility helpers for Intelli-Credit.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def load_json(path: str | Path) -> dict:
    """Load a JSON file and return it as a dict."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict, path: str | Path):
    """Save a dict as formatted JSON."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def timestamp() -> str:
    """Return current ISO timestamp."""
    return datetime.now().isoformat()


def safe_divide(a: float, b: float, default: float = 0.0) -> float:
    """Safe division with a default."""
    return a / b if b != 0 else default


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp a value between lo and hi."""
    return max(lo, min(hi, value))


def format_inr(value_cr: float) -> str:
    """Format a value in crores to an Indian currency string."""
    if value_cr >= 1:
        return f"\u20b9 {value_cr:.2f} Cr"
    lakhs = value_cr * 100
    return f"\u20b9 {lakhs:.2f} Lakh"


def format_quote_price(value, currency: str = "INR") -> str:
    """Format a market quote using its native trading currency."""
    if value in (None, ""):
        return ""

    try:
        price = float(value)
    except (TypeError, ValueError):
        return str(value)

    currency = (currency or "INR").upper()
    if currency == "INR":
        return f"\u20b9 {price:,.2f}"
    if currency == "USD":
        return f"${price:,.2f}"
    if currency == "EUR":
        return f"EUR {price:,.2f}"
    if currency == "GBP":
        return f"GBP {price:,.2f}"
    return f"{currency} {price:,.2f}"


def format_pct_change(value) -> str:
    """Format a percentage move with a sign for positive values."""
    if value in (None, ""):
        return ""

    try:
        pct = float(value)
    except (TypeError, ValueError):
        return str(value)

    prefix = "+" if pct > 0 else ""
    return f"{prefix}{pct:.2f}%"


def merge_research_financials(
    company_data: dict | None,
    fin_data: dict | None,
    fallback_company_name: str = "",
) -> dict:
    """Merge researched financial metrics and live quote details into company data."""
    merged = dict(company_data or {})
    fin_data = fin_data or {}

    if not merged.get("company_name") and fallback_company_name:
        merged["company_name"] = fallback_company_name

    if not fin_data:
        return merged

    financials = merged.setdefault("financials", {})
    fy24 = financials.setdefault("fy_2024", {})

    backfill_fields = [
        "net_worth_cr",
        "revenue_cr",
        "dscr",
        "icr",
        "revenue_cagr_3yr",
        "ebitda_margin_pct",
        "current_ratio",
        "de_ratio",
        "tangible_net_worth_cr",
        "promoter_equity_pct",
    ]
    for field in backfill_fields:
        incoming = fin_data.get(field)
        if incoming not in (None, "") and fy24.get(field) in (None, "", 0):
            fy24[field] = incoming

    always_refresh_fields = [
        "market_cap_cr",
        "current_price",
        "current_price_display",
        "price_change_pct",
        "price_change_display",
        "ticker",
        "exchange",
        "listing_exchange",
        "listed_on_nse",
        "nse_listing_status",
        "nse_listing_label",
        "nse_symbol",
        "bse_symbol",
        "quote_currency",
        "quote_source",
        "quote_url",
        "quote_status",
        "quote_error",
        "quote_timestamp",
        "source",
        "source_url",
        "summary",
        "method",
    ]
    for field in always_refresh_fields:
        incoming = fin_data.get(field)
        if incoming not in (None, ""):
            fy24[field] = incoming

    financials["latest"] = fy24
    merged["financials"] = financials
    return merged


def compute_cagr(start: float, end: float, years: int) -> float:
    """Compute compound annual growth rate."""
    if start <= 0 or years <= 0:
        return 0.0
    return ((end / start) ** (1.0 / years) - 1) * 100
