"""
Financial Search Agent for Intelli-Credit.
Searches for company financial metrics and enriches them with a live stock quote.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from config import IS_DEMO, TAVILY_API_KEY, get_llm_client, has_llm_key, has_tavily_key
from utils import format_pct_change, format_quote_price

SMART_DEMO_KB = {
    "tata motors": {
        "net_worth_cr": 84918,
        "revenue_cr": 437900,
        "market_cap_cr": 129159,
        "fiscal_year": "2023-24",
        "dscr": 2.1,
        "icr": 4.5,
        "revenue_cagr_3yr": 12.5,
        "ebitda_margin_pct": 11.2,
        "current_ratio": 1.25,
        "de_ratio": 1.8,
        "tangible_net_worth_cr": 72000,
        "promoter_equity_pct": 46.4,
        "source": "Verified Corporate Filings (Smart Demo)",
    },
    "reliance": {
        "net_worth_cr": 742922,
        "revenue_cr": 1000122,
        "market_cap_cr": 1870000,
        "fiscal_year": "2023-24",
        "dscr": 2.45,
        "icr": 6.8,
        "revenue_cagr_3yr": 15.2,
        "ebitda_margin_pct": 17.86,
        "current_ratio": 1.15,
        "de_ratio": 0.44,
        "tangible_net_worth_cr": 712000,
        "promoter_equity_pct": 50.39,
        "source": "Integrated Annual Report (Smart Demo)",
    },
    "infosys": {
        "net_worth_cr": 82450,
        "revenue_cr": 153670,
        "market_cap_cr": 680000,
        "fiscal_year": "2023-24",
        "dscr": 12.0,
        "icr": 45.0,
        "revenue_cagr_3yr": 10.1,
        "ebitda_margin_pct": 24.5,
        "current_ratio": 2.1,
        "de_ratio": 0.05,
        "tangible_net_worth_cr": 78000,
        "promoter_equity_pct": 14.8,
        "source": "Annual Report (Smart Demo)",
    },
}

YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
YAHOO_CHART_URL_TEMPLATE = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT_SEC = 6
COMPANY_STOPWORDS = {
    "the",
    "and",
    "of",
    "limited",
    "ltd",
    "private",
    "pvt",
    "company",
    "co",
    "corporation",
    "corp",
    "inc",
    "plc",
    "llc",
}
APP_INDUSTRY_OPTIONS = [
    "Manufacturing",
    "IT Services",
    "Retail",
    "Healthcare",
    "Financials",
    "Other",
]
INDUSTRY_KEYWORD_MAP = {
    "IT Services": [
        "software",
        "technology",
        "information technology",
        "internet",
        "telecom",
        "communication",
        "digital",
        "semiconductor",
    ],
    "Financials": [
        "financial",
        "bank",
        "insurance",
        "fintech",
        "capital markets",
        "asset management",
        "credit",
        "payments",
    ],
    "Retail": [
        "retail",
        "consumer",
        "ecommerce",
        "apparel",
        "restaurant",
        "food",
        "fmcg",
        "discretionary",
    ],
    "Healthcare": [
        "healthcare",
        "pharma",
        "biotech",
        "medical",
        "hospital",
        "diagnostic",
        "life sciences",
    ],
    "Manufacturing": [
        "manufacturing",
        "industrial",
        "steel",
        "materials",
        "chemicals",
        "energy",
        "oil",
        "gas",
        "automobile",
        "auto",
        "engineering",
        "cement",
        "mining",
        "metals",
        "infrastructure",
    ],
}


def fetch_financial_metrics(company_name: str) -> dict:
    """Search and extract core financials, then enrich them with a live quote."""
    normalized_name = (company_name or "").strip().lower()
    live_quote = _fetch_live_stock_quote(company_name)

    for key in SMART_DEMO_KB:
        if key in normalized_name or (key == "reliance" and "reli" in normalized_name):
            data = SMART_DEMO_KB[key].copy()
            data["method"] = "smart_demo_knowledge_base"
            return _merge_live_quote(data, live_quote)

    if IS_DEMO or not has_tavily_key():
        seed = int(hashlib.md5(normalized_name.encode()).hexdigest(), 16) % 1000
        base_val = (seed * 10) + 1200
        synthetic = {
            "net_worth_cr": base_val,
            "revenue_cr": base_val * 1.8,
            "market_cap_cr": base_val * 4.2,
            "dscr": 1.4 + (seed % 150) / 100.0,
            "icr": 2.8 + (seed % 300) / 100.0,
            "ebitda_margin_pct": 14.0 + (seed % 100) / 10.0,
            "current_ratio": 1.1 + (seed % 90) / 100.0,
            "de_ratio": 0.4 + (seed % 120) / 100.0,
            "revenue_cagr_3yr": 7.0 + (seed % 250) / 10.0,
            "tangible_net_worth_cr": base_val * 0.85,
            "promoter_equity_pct": 48.0 + (seed % 200) / 10.0,
            "source": "Smart Demo (Plausible Simulation)",
            "method": "demo_synthetic",
        }
        return _merge_live_quote(synthetic, live_quote)

    researched = _search_and_extract_financials(company_name)
    return _merge_live_quote(researched, live_quote)


def lookup_company_profile(company_name: str) -> dict:
    """Fetch lightweight company profile details for onboarding autofill."""
    search_name = (company_name or "").strip()
    if not search_name:
        return {
            "company_name": "",
            "matched_name": "",
            "industry": "",
            "sector_raw": "",
            "industry_raw": "",
            "confidence": 0.0,
            "status": "empty",
        }

    try:
        search_candidates = _search_quote_candidates(search_name)
        listing_info = _build_listing_info(search_candidates)
        if not search_candidates:
            return {
                "company_name": search_name,
                "matched_name": "",
                "industry": "",
                "sector_raw": "",
                "industry_raw": "",
                "confidence": 0.0,
                "status": "not_found",
                **listing_info,
            }

        ranked = sorted(
            search_candidates.values(),
            key=lambda item: _score_quote_candidate(item, search_name),
            reverse=True,
        )
        best = ranked[0]
        best_score = _score_quote_candidate(best, search_name)
        confidence = min(1.0, max(0.0, best_score / 35.0))
        sector_raw = (
            best.get("sectorDisp")
            or best.get("sector")
            or ""
        )
        industry_raw = (
            best.get("industryDisp")
            or best.get("industry")
            or ""
        )
        mapped_industry = _map_to_app_industry(sector_raw, industry_raw)
        status = "matched" if best_score >= 8 else "low_confidence"

        return {
            "company_name": search_name,
            "matched_name": best.get("longname") or best.get("shortname") or "",
            "industry": mapped_industry,
            "sector_raw": sector_raw,
            "industry_raw": industry_raw,
            "confidence": round(confidence, 2),
            "status": status,
            **listing_info,
        }
    except Exception as exc:
        return {
            "company_name": search_name,
            "matched_name": "",
            "industry": "",
            "sector_raw": "",
            "industry_raw": "",
            "confidence": 0.0,
            "status": "error",
            "error": str(exc),
        }


def _search_and_extract_financials(company_name: str) -> dict:
    """Search for financials via Tavily and extract using the configured LLM."""
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=TAVILY_API_KEY)
        queries = [
            f"{company_name} latest net worth consolidated total equity 2024",
            f"{company_name} annual revenue turnover FY24 consolidated",
            f"{company_name} market capitalization NSE BSE",
        ]

        search_context = []
        for query in queries:
            try:
                result = client.search(query=query, max_results=2, search_depth="basic")
                for item in result.get("results", []):
                    search_context.append(
                        f"Source: {item.get('url')}\nContent: {item.get('content')}"
                    )
            except Exception:
                continue

        if not search_context:
            return {"error": "No search results found", "method": "tavily_search"}

        if not has_llm_key():
            return {"error": "LLM key missing for extraction", "method": "tavily_search"}

        llm = get_llm_client()
        prompt = f"""Extract the latest consolidated financial metrics for '{company_name}' from the following search results.
Convert all values into Crores (INR Cr).
1 Lakh Cr = 1,00,000 Cr.
1 Billion USD = ~8,300 Cr.

Search Results:
{chr(10).join(search_context[:5])}

Return ONLY a JSON object with these keys:
- net_worth_cr (float)
- revenue_cr (float)
- market_cap_cr (float)
- currency (e.g. "INR")
- fiscal_year (e.g. "2023-24")
- confidence_score (0.0 to 1.0)
- source_url (string)

If a value is not found, use 0.
"""
        response = llm.invoke(prompt)
        content = response.content

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())
        data["method"] = "tavily_llm_extraction"
        return data

    except Exception as exc:
        return {"error": str(exc), "method": "fail_fallback"}


def _fetch_live_stock_quote(company_name: str) -> dict:
    """Resolve the best Yahoo Finance symbol match and return the latest quote."""
    search_name = (company_name or "").strip()
    if not search_name:
        return {
            "quote_status": "unavailable",
            "quote_error": "Missing company name",
            "nse_listing_status": "unknown",
            "nse_listing_label": "NSE listing unknown",
        }

    try:
        search_candidates = _search_quote_candidates(search_name)
        symbols = list(search_candidates.keys())[:8]
        listing_info = _build_listing_info(search_candidates)
        if not symbols:
            return {
                "quote_status": "unavailable",
                "quote_error": "No listed stock match found for this company",
                **listing_info,
            }

        results = []
        for symbol in symbols:
            chart_response = requests.get(
                YAHOO_CHART_URL_TEMPLATE.format(symbol=quote(symbol, safe="")),
                params={
                    "range": "5d",
                    "interval": "1d",
                    "includePrePost": "false",
                },
                headers=REQUEST_HEADERS,
                timeout=REQUEST_TIMEOUT_SEC,
            )
            chart_response.raise_for_status()
            chart_payload = chart_response.json()
            chart_result = (chart_payload.get("chart", {}) or {}).get("result", [])
            if chart_result:
                meta = (chart_result[0] or {}).get("meta", {}) or {}
                if meta:
                    enriched_meta = {**search_candidates.get(symbol, {}), **meta}
                    results.append(enriched_meta)
        if not results:
            return {
                "quote_status": "unavailable",
                "quote_error": "Quote service returned no prices",
                **listing_info,
            }

        ranked = sorted(
            results,
            key=lambda item: _score_quote_candidate(item, search_name),
            reverse=True,
        )
        best = ranked[0]
        if _score_quote_candidate(best, search_name) < 8:
            return {
                "quote_status": "unavailable",
                "quote_error": "Could not confidently match the company to a listed stock",
                **listing_info,
            }

        return _normalize_quote(best, listing_info)

    except requests.RequestException as exc:
        return {
            "quote_status": "unavailable",
            "quote_error": f"Quote lookup failed: {exc.__class__.__name__}",
            "nse_listing_status": "unknown",
            "nse_listing_label": "NSE listing unknown",
        }
    except Exception as exc:
        return {
            "quote_status": "unavailable",
            "quote_error": f"Quote lookup failed: {exc}",
            "nse_listing_status": "unknown",
            "nse_listing_label": "NSE listing unknown",
        }


def _score_quote_candidate(item: dict, company_name: str) -> int:
    """Prefer confident name matches and Indian cash equity listings."""
    symbol = (item.get("symbol") or "").upper()
    exchange_name = (
        item.get("fullExchangeName")
        or item.get("exchange")
        or item.get("exchangeDisp")
        or ""
    ).lower()
    text = " ".join(
        filter(
            None,
            [
                item.get("longName"),
                item.get("shortName"),
                item.get("displayName"),
                symbol,
            ],
        )
    ).lower()
    tokens = _name_tokens(company_name)
    candidate_tokens = set(re.findall(r"[a-z0-9]+", text))
    symbol_token = re.sub(r"[^a-z0-9]+", "", symbol.lower())

    score = 0
    if item.get("regularMarketPrice") is not None:
        score += 6
    if item.get("quoteType") == "EQUITY":
        score += 4
    if _is_nse_symbol(symbol, item):
        score += 14
    elif _is_bse_symbol(symbol, item):
        score += 12
    elif "national stock exchange" in exchange_name:
        score += 10
    elif "bombay" in exchange_name:
        score += 8

    token_matches = sum(
        1 for token in tokens if token in candidate_tokens or token == symbol_token
    )
    score += token_matches * 5
    if tokens and token_matches == len(tokens):
        score += 6
    elif tokens and token_matches >= max(1, len(tokens) - 1):
        score += 3
    elif tokens and token_matches == 0:
        score -= 10

    if token_matches > 0 and float(item.get("score", 0)) >= 20000:
        score += 2

    return score


def _name_tokens(company_name: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", (company_name or "").lower())
    filtered = [token for token in tokens if len(token) > 1 and token not in COMPANY_STOPWORDS]

    merged = []
    idx = 0
    while idx < len(filtered):
        current = filtered[idx]
        if idx + 1 < len(filtered):
            nxt = filtered[idx + 1]
            if (current.isalpha() and nxt.isdigit()) or (current.isdigit() and nxt.isalpha()):
                merged.append(f"{current}{nxt}")
                idx += 2
                continue
        merged.append(current)
        idx += 1

    final_tokens = list(dict.fromkeys(merged or filtered or tokens[:2]))
    return final_tokens


def _search_quote_candidates(company_name: str) -> dict:
    """Search Yahoo Finance with multiple company-name variants."""
    candidates = {}
    for query in _build_search_queries(company_name):
        search_response = requests.get(
            YAHOO_SEARCH_URL,
            params={
                "q": query,
                "quotesCount": 8,
                "newsCount": 0,
                "enableFuzzyQuery": "true",
            },
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT_SEC,
        )
        search_response.raise_for_status()
        search_payload = search_response.json()
        for item in search_payload.get("quotes", []):
            symbol = item.get("symbol")
            if not symbol:
                continue
            if item.get("quoteType") and item.get("quoteType") not in {"EQUITY", "ETF"}:
                continue
            merged = dict(item)
            merged["search_query"] = query
            previous = candidates.get(symbol)
            if not previous or float(merged.get("score", 0)) > float(previous.get("score", 0)):
                candidates[symbol] = merged
    return candidates


def _build_search_queries(company_name: str) -> list[str]:
    """Generate search-friendly company name variants."""
    base = (company_name or "").strip()
    raw_tokens = re.findall(r"[A-Za-z0-9]+", base)
    filtered_tokens = [token for token in raw_tokens if token.lower() not in COMPANY_STOPWORDS]

    merged_numeric_tokens = []
    idx = 0
    while idx < len(filtered_tokens):
        current = filtered_tokens[idx]
        if idx + 1 < len(filtered_tokens):
            nxt = filtered_tokens[idx + 1]
            if (current.isalpha() and nxt.isdigit()) or (current.isdigit() and nxt.isalpha()):
                merged_numeric_tokens.append(f"{current}{nxt}")
                idx += 2
                continue
        merged_numeric_tokens.append(current)
        idx += 1

    queries = [
        base,
        " ".join(raw_tokens),
        " ".join(filtered_tokens),
        " ".join(merged_numeric_tokens),
    ]
    return [query for query in dict.fromkeys(q.strip() for q in queries if q and q.strip())]


def _build_listing_info(search_candidates: dict) -> dict:
    """Summarize NSE/BSE listing status from the search candidate set."""
    symbols = list(search_candidates.keys())
    nse_symbols = [symbol for symbol in symbols if _is_nse_symbol(symbol, search_candidates.get(symbol, {}))]
    bse_symbols = [symbol for symbol in symbols if _is_bse_symbol(symbol, search_candidates.get(symbol, {}))]

    if nse_symbols:
        return {
            "listed_on_nse": True,
            "nse_listing_status": "listed",
            "nse_listing_label": "Listed on NSE",
            "nse_symbol": nse_symbols[0],
            "bse_symbol": bse_symbols[0] if bse_symbols else "",
        }
    if bse_symbols:
        return {
            "listed_on_nse": False,
            "nse_listing_status": "not_listed",
            "nse_listing_label": "Not listed on NSE",
            "nse_symbol": "",
            "bse_symbol": bse_symbols[0],
        }
    if symbols:
        return {
            "listed_on_nse": False,
            "nse_listing_status": "not_listed",
            "nse_listing_label": "Not listed on NSE",
            "nse_symbol": "",
            "bse_symbol": "",
        }
    return {
        "listed_on_nse": None,
        "nse_listing_status": "unknown",
        "nse_listing_label": "NSE listing unknown",
        "nse_symbol": "",
        "bse_symbol": "",
    }


def _map_to_app_industry(sector_raw: str, industry_raw: str) -> str:
    """Map market sector labels to the onboarding dropdown options."""
    haystack = f"{sector_raw} {industry_raw}".strip().lower()
    if not haystack:
        return ""

    for option, keywords in INDUSTRY_KEYWORD_MAP.items():
        if any(keyword in haystack for keyword in keywords):
            return option

    if "health" in haystack:
        return "Healthcare"
    if "finance" in haystack:
        return "Financials"
    if "retail" in haystack:
        return "Retail"
    if "tech" in haystack:
        return "IT Services"
    return "Other"


def _is_nse_symbol(symbol: str, item: dict | None = None) -> bool:
    item = item or {}
    exchange = (item.get("exchange") or item.get("exchangeName") or item.get("exchDisp") or "").upper()
    return (symbol or "").upper().endswith(".NS") or exchange in {"NSI", "NSE"}


def _is_bse_symbol(symbol: str, item: dict | None = None) -> bool:
    item = item or {}
    exchange = (item.get("exchange") or item.get("exchangeName") or item.get("exchDisp") or "").upper()
    return (symbol or "").upper().endswith(".BO") or exchange in {"BSE", "BOM", "BOMBAY"}


def _normalize_quote(item: dict, listing_info: dict | None = None) -> dict:
    """Map a Yahoo Finance quote result into the app's financial schema."""
    price = item.get("regularMarketPrice")
    if price in (None, ""):
        return {
            "quote_status": "unavailable",
            "quote_error": "Matched a symbol, but no live market price was returned",
            **(listing_info or {}),
        }

    currency = (item.get("currency") or "INR").upper()
    symbol = item.get("symbol", "")
    exchange = item.get("fullExchangeName") or item.get("exchange") or "Yahoo Finance"
    previous_close = item.get("chartPreviousClose")
    price_change_pct = 0.0
    if isinstance(previous_close, (int, float)) and previous_close:
        price_change_pct = ((float(price) - float(previous_close)) / float(previous_close)) * 100
    market_cap_cr = None
    market_cap_value = item.get("marketCap")
    if isinstance(market_cap_value, (int, float)) and currency == "INR":
        market_cap_cr = round(market_cap_value / 10_000_000, 2)

    return {
        "current_price": round(float(price), 2),
        "current_price_display": format_quote_price(price, currency),
        "price_change_pct": round(float(price_change_pct), 2),
        "price_change_display": format_pct_change(price_change_pct),
        "ticker": symbol,
        "exchange": exchange,
        "listing_exchange": exchange,
        "listed_on_nse": (listing_info or {}).get("listed_on_nse"),
        "nse_listing_status": (listing_info or {}).get("nse_listing_status", "unknown"),
        "nse_listing_label": (listing_info or {}).get("nse_listing_label", "NSE listing unknown"),
        "nse_symbol": (listing_info or {}).get("nse_symbol", symbol if _is_nse_symbol(symbol, item) else ""),
        "bse_symbol": (listing_info or {}).get("bse_symbol", symbol if _is_bse_symbol(symbol, item) else ""),
        "quote_currency": currency,
        "quote_source": "Yahoo Finance",
        "quote_url": f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}",
        "quote_status": "live",
        "quote_timestamp": datetime.now(timezone.utc).isoformat(),
        "market_cap_cr": market_cap_cr,
        "source_url": f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}",
        "summary": f"Live stock quote found for {symbol} on {exchange}.",
    }


def _merge_live_quote(financials: dict, live_quote: dict) -> dict:
    """Attach quote fields to researched or synthetic financial metrics."""
    merged = dict(financials or {})
    live_quote = dict(live_quote or {})

    quote_market_cap = live_quote.get("market_cap_cr")
    if quote_market_cap not in (None, 0):
        merged["market_cap_cr"] = quote_market_cap

    for key, value in live_quote.items():
        if value not in (None, ""):
            merged[key] = value

    if live_quote.get("quote_status") == "live":
        base_method = merged.get("method")
        merged["method"] = f"{base_method}+yahoo_quote" if base_method else "yahoo_quote"
        if not merged.get("source"):
            merged["source"] = "Yahoo Finance live quote"
    else:
        merged.setdefault("quote_status", "unavailable")
        merged.setdefault("quote_error", "Live stock quote unavailable")

    return merged
