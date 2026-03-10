"""
Sector Agent for Intelli-Credit.
Analyzes industry outlook, regulatory environment, and sector-specific risks.
"""
from config import IS_DEMO, has_tavily_key, TAVILY_API_KEY, SAMPLE_DATA_DIR
from utils import load_json


def analyze_sector(industry: str, nic_code: str = "") -> dict:
    """
    Analyze industry sector outlook and regulatory environment.
    """
    if IS_DEMO or not has_tavily_key():
        return _get_demo_sector()

    return _analyze_live(industry, nic_code)


def _get_demo_sector() -> dict:
    """Return simulated sector analysis."""
    sample = load_json(SAMPLE_DATA_DIR / "sample_company.json")
    sector = sample["sector_data"]

    return {
        "industry": sector["industry"],
        "outlook": sector["outlook"],
        "outlook_score": sector["outlook_score"],
        "regulatory_risk": sector["regulatory_risk"],
        "regulatory_risk_score": sector["regulatory_risk_score"],
        "key_factors": sector["key_factors"],
        "rbi_circulars": sector["rbi_circulars"],
        "risk_score": 28,
        "summary": "Steel manufacturing sector outlook is positive, driven by government infrastructure push "
                   "(PM Gati Shakti). Anti-dumping duties protect domestic players. Rising coking coal prices "
                   "and mandatory BIS certification are moderate headwinds. RBI's revised MSME lending guidelines "
                   "are favorable for credit access.",
        "method": "demo",
    }


def _analyze_live(industry: str, nic_code: str) -> dict:
    """Analyze sector via web search."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)

        queries = [
            f"{industry} India sector outlook 2024 2025",
            f"RBI circular {industry} lending India recent",
            f"{industry} India regulatory risk challenges",
        ]

        findings = []
        for query in queries:
            try:
                result = client.search(query=query, max_results=3, search_depth="basic")
                for r in result.get("results", []):
                    findings.append({
                        "source": r.get("url", ""),
                        "title": r.get("title", ""),
                        "content": r.get("content", "")[:400],
                    })
            except Exception:
                continue

        return {
            "industry": industry,
            "web_findings": findings,
            "total_results": len(findings),
            "outlook_score": 65,  # Default moderate positive
            "regulatory_risk_score": 35,
            "risk_score": 30,
            "summary": f"Found {len(findings)} web results about {industry} sector in India.",
            "method": "tavily_live",
        }

    except Exception as e:
        result = _get_demo_sector()
        result["method"] = "sector_fallback"
        result["error"] = str(e)
        return result
