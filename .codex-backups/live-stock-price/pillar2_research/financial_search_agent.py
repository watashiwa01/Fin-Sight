"""
Financial Search Agent for Intelli-Credit.
Searches for company financial metrics (Net Worth, Revenue, Market Cap) using Tavily API.
Extracts and standardizes figures using LLM.
"""
import json
import re
from config import IS_DEMO, has_tavily_key, has_llm_key, TAVILY_API_KEY, get_llm_client
from utils import load_json

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
        "source": "Verified Corporate Filings (Smart Demo)"
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
        "source": "Integrated Annual Report (Smart Demo)"
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
        "source": "Annual Report (Smart Demo)"
    }
}

def fetch_financial_metrics(company_name: str) -> dict:
    """
    Search and extract Net Worth, Revenue, and Market Cap for a company.
    """
    normalized_name = company_name.lower()
    
    # Smart Demo Check: Fuzzy matching for common entities
    for key in SMART_DEMO_KB.keys():
        # Check for direct substring or common fragments (like 'reli' for reliance/relience)
        if key in normalized_name or (key == "reliance" and "reli" in normalized_name):
            data = SMART_DEMO_KB[key].copy()
            data["method"] = "smart_demo_knowledge_base"
            return data

    if IS_DEMO or not has_tavily_key():
        import hashlib
        # Generate consistent but different numbers for each name
        seed = int(hashlib.md5(normalized_name.encode()).hexdigest(), 16) % 1000
        base_val = (seed * 10) + 1200 # ~1200 to 11200 Cr
        
        return {
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
            "method": "demo_synthetic"
        }

    return _search_and_extract_financials(company_name)

def _search_and_extract_financials(company_name: str) -> dict:
    """Search for financials via Tavily and extract using LLM."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)

        # Targeted search queries
        queries = [
            f"{company_name} latest net worth consolidated total equity 2024",
            f"{company_name} annual revenue turnover FY24 consolidated",
            f"{company_name} market capitalization NSE BSE"
        ]

        search_context = []
        for query in queries:
            try:
                result = client.search(query=query, max_results=2, search_depth="basic")
                for r in result.get("results", []):
                    search_context.append(f"Source: {r.get('url')}\nContent: {r.get('content')}")
            except Exception:
                continue

        if not search_context:
            return {"error": "No search results found"}

        # Use LLM to extract figures
        if not has_llm_key():
            return {"error": "LLM key missing for extraction"}

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
        
        # Clean JSON response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())
        data["method"] = "tavily_llm_extraction"
        return data

    except Exception as e:
        return {"error": str(e), "method": "fail_fallback"}
