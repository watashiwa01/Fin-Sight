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
        return _get_demo_sector(industry)

    return _analyze_live(industry, nic_code)


def _get_demo_sector(industry: str = "Diversified Conglomerate") -> dict:
    """Return simulated sector analysis."""
    sample = load_json(SAMPLE_DATA_DIR / "sample_company.json")
    sector = sample["sector_data"]
    
    # Guess industry if empty
    if not industry:
        industry = "Diversified Conglomerate"

    import hashlib
    seed = int(hashlib.md5(industry.lower().encode()).hexdigest(), 16) % 1000
    
    # Randomize scores
    out_score = 60 + (seed % 30)   # 60-89
    reg_score = 15 + (seed % 40)   # 15-54
    total_risk = 20 + (seed % 20)  # 20-39
    
    return {
        "industry": industry,
        "outlook": "Positive" if out_score > 75 else "Stable",
        "outlook_score": out_score,
        "regulatory_risk": "Low" if reg_score < 30 else "Moderate",
        "regulatory_risk_score": reg_score,
        "key_factors": sector["key_factors"],
        "rbi_circulars": sector["rbi_circulars"],
        "risk_score": total_risk,
        "summary": f"The outlook for the {industry} sector is {('positive' if out_score > 75 else 'stable')}. "
                   "Growth is supported by favorable domestic policies. Regulatory risk is "
                   f"{('low' if reg_score < 30 else 'manageable')}, though monitoring of recent guidelines is advised.",
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
