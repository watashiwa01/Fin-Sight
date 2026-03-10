"""
MCA Agent for Intelli-Credit.
Looks up Ministry of Corporate Affairs (MCA21) data for a company.
In demo mode, returns realistic simulated MCA data.
In live mode, performs web search for publicly available MCA filings.
"""
from config import IS_DEMO, has_tavily_key, TAVILY_API_KEY, SAMPLE_DATA_DIR
from utils import load_json


def lookup_mca_data(company_name: str, cin: str = "") -> dict:
    """
    Look up MCA21 data for a company.
    Returns director info, charges, compliance status.
    """
    if IS_DEMO or not has_tavily_key():
        return _get_demo_mca()

    return _search_mca_live(company_name, cin)


def _get_demo_mca() -> dict:
    """Return simulated MCA data."""
    sample = load_json(SAMPLE_DATA_DIR / "sample_company.json")
    mca = sample["mca_data"]
    promoters = sample["promoters"]

    return {
        "company_name": sample["company_name"],
        "cin": sample["cin"],
        "incorporation_date": sample["incorporation_date"],
        "registered_office": sample["registered_office"],
        "directors": [
            {
                "name": p["name"],
                "din": p["din"],
                "designation": p["designation"],
                "status": "Active",
                "other_directorships": 1 if i == 0 else 0,
                "disqualified": False,
            }
            for i, p in enumerate(promoters)
        ],
        "charges": {
            "total_registered": mca["charges_registered"],
            "satisfied": mca["charges_satisfied"],
            "open": mca["charges_open"],
            "details": mca["charges_detail"],
        },
        "compliance": {
            "annual_returns_filed": mca["annual_returns_filed"],
            "last_agm_date": mca["last_agm_date"],
            "roc_notices": mca["roc_notices"],
            "compliance_score": mca["compliance_score"],
        },
        "risk_score": 18,  # Low risk
        "risk_flags": [],
        "summary": "Company has clean MCA records. 1 open charge in favor of SBI (working capital). "
                   "No ROC notices or director disqualifications. Annual returns filed on time.",
        "method": "demo",
    }


def _search_mca_live(company_name: str, cin: str) -> dict:
    """Search for MCA data via web search."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)

        queries = [
            f"{company_name} MCA21 company details charges India",
            f"site:mca.gov.in {cin}" if cin else f"{company_name} CIN India company registration",
        ]

        findings = []
        for query in queries:
            try:
                result = client.search(query=query, max_results=3, search_depth="basic")
                for r in result.get("results", []):
                    findings.append({
                        "source": r.get("url", ""),
                        "content": r.get("content", "")[:500],
                    })
            except Exception:
                continue

        # Parse findings into structured format
        risk_flags = []
        risk_score = 30  # Default moderate

        return {
            "company_name": company_name,
            "cin": cin or "Not found",
            "web_findings": findings,
            "risk_score": risk_score,
            "risk_flags": risk_flags,
            "summary": f"Found {len(findings)} web results about MCA filings for {company_name}.",
            "method": "tavily_live",
            "note": "Live MCA data requires direct MCA21 portal access for full details.",
        }

    except Exception as e:
        result = _get_demo_mca()
        result["method"] = "mca_fallback"
        result["error"] = str(e)
        return result
