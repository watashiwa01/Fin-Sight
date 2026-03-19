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
        return _get_demo_litigation(company_name)

    return _search_litigation_live(company_name, promoter_names or [])


def _get_demo_litigation(company_name: str = "Bharat Steel Industries") -> dict:
    """Return simulated litigation data."""
    sample = load_json(SAMPLE_DATA_DIR / "sample_company.json")
    lit = sample["litigation_data"]
    
    cname = company_name if company_name else sample["company_name"]
    import hashlib
    seed = int(hashlib.md5(cname.lower().encode()).hexdigest(), 16) % 1000
    
    # Randomize case counts
    total_cases = 5 + (seed % 15)           # 5-19
    pending_cases = seed % 5                # 0-4
    disposed_cases = total_cases - pending_cases
    risk_score = 10 + (seed % 30)           # 10-39
    
    return {
        "company_name": cname,
        "total_cases": total_cases,
        "pending_cases": pending_cases,
        "disposed_cases": disposed_cases,
        "cases": lit["cases"][:max(1, total_cases // 4)], 
        "risk_score": risk_score,
        "risk_level": "LOW" if risk_score < 30 else "MODERATE",
        "criminal_cases": 0,
        "civil_cases": disposed_cases - 1,
        "consumer_cases": 1,
        "total_exposure_cr": 0.5 + (seed % 100) / 10.0,
        "summary": f"A total of {total_cases} litigation cases were found for {cname}, with {pending_cases} currently pending. "
                   f"The majority of cases are civil and consumer-related, with a low overall risk profile.",
        "sources_checked": ["NJDG (njdg.gov.in)", "District Courts", "State Commissions"],
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
        result = _get_demo_litigation(company_name)
        result["method"] = "ecourts_fallback"
        result["error"] = str(e)
        return result
