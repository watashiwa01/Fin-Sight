"""
e-Courts Agent for Intelli-Credit.
Searches for litigation records via NJDG (National Judicial Data Grid).
In demo mode, returns realistic simulated litigation data.
"""
from config import IS_DEMO, has_tavily_key, TAVILY_API_KEY, SAMPLE_DATA_DIR
from utils import load_json


def lookup_litigation(company_name: str, promoter_names: list[str] = None) -> dict:
    """
    Look up litigation records for a company and its promoters.
    Returns case details and litigation risk score.
    """
    if IS_DEMO or not has_tavily_key():
        return _get_demo_litigation()

    return _search_litigation_live(company_name, promoter_names or [])


def _get_demo_litigation() -> dict:
    """Return simulated litigation data."""
    sample = load_json(SAMPLE_DATA_DIR / "sample_company.json")
    lit = sample["litigation_data"]

    return {
        "company_name": sample["company_name"],
        "total_cases": lit["total_cases"],
        "pending_cases": lit["pending_cases"],
        "disposed_cases": lit["disposed_cases"],
        "cases": lit["cases"],
        "risk_score": lit["litigation_risk_score"],
        "risk_level": "LOW" if lit["litigation_risk_score"] < 30 else "MODERATE",
        "criminal_cases": 0,
        "civil_cases": 2,
        "consumer_cases": 1,
        "total_exposure_cr": sum(c["amount_cr"] for c in lit["cases"]),
        "summary": f"Total {lit['total_cases']} cases found: {lit['disposed_cases']} disposed, {lit['pending_cases']} pending. "
                   f"No criminal cases. 1 pending consumer complaint (Rs 0.12 Cr). "
                   f"All civil cases resolved. Low litigation risk.",
        "sources_checked": ["NJDG (njdg.gov.in)", "Pune District Court", "Maharashtra State Consumer Commission"],
        "method": "demo",
    }


def _search_litigation_live(company_name: str, promoter_names: list[str]) -> dict:
    """Search for litigation data via web search."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)

        queries = [
            f"{company_name} court case litigation India",
            f"{company_name} NCLT NCLAT case",
        ]
        for name in promoter_names[:2]:
            queries.append(f"{name} court case litigation")

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

        risk_score = 30 + len(findings) * 5  # Higher findings = higher risk

        return {
            "company_name": company_name,
            "web_findings": findings,
            "total_results": len(findings),
            "risk_score": min(risk_score, 100),
            "risk_level": "LOW" if risk_score < 30 else "MODERATE" if risk_score < 60 else "HIGH",
            "summary": f"Found {len(findings)} web results related to litigation for {company_name}.",
            "sources_checked": [q for q in queries],
            "method": "tavily_live",
            "note": "For comprehensive litigation data, direct NJDG portal access is recommended.",
        }

    except Exception as e:
        result = _get_demo_litigation()
        result["method"] = "ecourts_fallback"
        result["error"] = str(e)
        return result
