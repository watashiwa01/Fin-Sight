"""
Sector Agent for Intelli-Credit.
Analyzes industry outlook, regulatory environment, and sector-specific risks.
"""
import json
from config import IS_DEMO, has_tavily_key, TAVILY_API_KEY, SAMPLE_DATA_DIR, get_llm_client, has_llm_key
from utils import load_json


def analyze_sector(company_name: str, industry: str, nic_code: str = "") -> dict:
    """
    Analyze industry sector outlook and regulatory environment.
    """
    if has_tavily_key() and has_llm_key():
        return _analyze_live(company_name, industry, nic_code)
    
    # Use the free Pollinations AI API if API keys are missing so the user gets the REAL THING.
    return _analyze_free(company_name, industry)

def _analyze_free(company_name: str, industry: str) -> dict:
    """Analyze sector via free pollinations AI API."""
    import requests
    prompt = f"""You are a financial credit analyst. Provide the sector analysis for '{company_name}' in the '{industry}' sector in India. Return ONLY a valid JSON object with the following fields:
- "major_sector" (string)
- "major_competitors" (list of strings, 3 to 5 key competitors)
- "market_sentiment" (string, 2 sentences explaining market sentiment and consumer impact)
- "outlook" (string: "Positive", "Stable", or "Negative")
- "outlook_score" (int, 0-100)
- "regulatory_risk" (string: "Low", "Moderate", "High")
- "regulatory_risk_score" (int, 0-100)
- "key_factors" (list of strings, 3 growth drivers/risks)
- "summary" (string, 2 sentence summary)"""
    try:
        r = requests.post(
            'https://text.pollinations.ai/openai',
            json={
                "messages": [{"role": "user", "content": prompt}],
                "jsonMode": True
            },
            timeout=15
        )
        # text.pollinations.ai/openai returns a standard OpenAI chat completion JSON wrapped object
        api_resp = r.json()
        content_text = api_resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if "```json" in content_text:
            content_text = content_text.split("```json")[1].split("```")[0]
        elif "```" in content_text:
            content_text = content_text.split("```")[1].split("```")[0]
            
        data = json.loads(content_text.strip())
        
        out_score = data.get("outlook_score", 65)
        reg_score = data.get("regulatory_risk_score", 35)
        risk_score = int(( (100 - out_score) * 0.6 ) + ( reg_score * 0.4 ))
        
        return {
            "industry": industry,
            "major_sector": data.get("major_sector", industry),
            "major_competitors": data.get("major_competitors", []),
            "market_sentiment": data.get("market_sentiment", "Sentiment data analyzed successfully."),
            "outlook": data.get("outlook", "Stable"),
            "outlook_score": out_score,
            "regulatory_risk": data.get("regulatory_risk", "Moderate"),
            "regulatory_risk_score": reg_score,
            "risk_score": risk_score,
            "key_factors": data.get("key_factors", []),
            "summary": data.get("summary", f"Live sector analysis completed for {industry}."),
            "method": "pollinations_ai_live",
        }
    except Exception as e:
        print(f"Pollinations AI failed: {e}")
        return _get_demo_sector(company_name, industry)


def _get_demo_sector(company_name: str, industry: str = "Diversified Conglomerate") -> dict:
    """Return simulated sector analysis."""
    sample = load_json(SAMPLE_DATA_DIR / "sample_company.json")
    sector = sample["sector_data"]
    
    # Guess industry if empty
    if not industry:
        industry = "Diversified Conglomerate"

    import hashlib
    seed = int(hashlib.md5((company_name + industry).lower().encode()).hexdigest(), 16) % 1000
    
    # Randomize scores
    out_score = 60 + (seed % 30)   # 60-89
    reg_score = 15 + (seed % 40)   # 15-54
    total_risk = 20 + (seed % 20)  # 20-39
    
    # Mock Competitors and Sentiment
    major_sector = f"{industry} / General" 
    competitors = [f"{company_name} Alpha", f"{company_name} Beta", "National " + industry.split()[0] + " Ltd"]
    sentiment = "The market sentiment is largely stable. Analysts believe that while there are global headwinds, domestic demand remains robust."
    
    if "tata" in company_name.lower():
        major_sector = "Automobiles & Manufacturing"
        competitors = ["Maruti Suzuki", "Mahindra & Mahindra", "Hyundai India"]
        sentiment = "Positive market sentiment driven by EV expansion and strong SUV sales."
    elif "reliance" in company_name.lower():
        major_sector = "Diversified Conglomerate"
        competitors = ["Adani Enterprises", "Tata Sons", "Aditya Birla Group"]
        sentiment = "Strong positive sentiment driven by Green Energy initiatives and Retail sector dominance."

    return {
        "industry": industry,
        "major_sector": major_sector,
        "major_competitors": competitors,
        "market_sentiment": sentiment,
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


def _analyze_live(company_name: str, industry: str, nic_code: str) -> dict:
    """Analyze sector via web search and LLM extraction."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)

        queries = [
            f"{company_name} {industry} India major competitors",
            f"{company_name} {industry} market sentiment impact on people consumers",
            f"{industry} India sector outlook 2024 2025 regulatory risk challenges",
        ]

        search_context = []
        for query in queries:
            try:
                result = client.search(query=query, max_results=3, search_depth="basic")
                for r in result.get("results", []):
                    search_context.append(f"Source: {r.get('url')}\nContent: {r.get('content')[:500]}")
            except Exception:
                continue
                
        if not search_context:
            raise Exception("No search results found.")

        llm = get_llm_client()
        prompt = f"""You are a financial credit analyst. Extract the sector analysis for '{company_name}' in the '{industry}' sector in India based on the following web search context.

Context:
{chr(10).join(search_context[:10])}

Return ONLY a valid JSON object with the following fields:
- "major_sector" (string, the broad sector/macro-industry)
- "major_competitors" (list of strings, 3 to 5 key competitors)
- "market_sentiment" (string, 2-3 sentences explaining the overarching market sentiment on the company and competitors, and any impact on people/consumers)
- "outlook" (string: "Positive", "Stable", or "Negative")
- "outlook_score" (int, 0 to 100 where higher means better outlook)
- "regulatory_risk" (string: "Low", "Moderate", or "High")
- "regulatory_risk_score" (int, 0 to 100 where higher means higher risk)
- "key_factors" (list of strings, 3 to 4 key growth drivers or risks)
- "summary" (string, a 2 sentence summary of the sector environment)
"""
        response = llm.invoke(prompt)
        content = response.content

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())
        
        # Calculate risk score heuristic
        out_score = data.get("outlook_score", 65)
        reg_score = data.get("regulatory_risk_score", 35)
        risk_score = int(( (100 - out_score) * 0.6 ) + ( reg_score * 0.4 ))
        
        return {
            "industry": industry,
            "major_sector": data.get("major_sector", industry),
            "major_competitors": data.get("major_competitors", []),
            "market_sentiment": data.get("market_sentiment", "Sentiment data unavailable."),
            "outlook": data.get("outlook", "Stable"),
            "outlook_score": out_score,
            "regulatory_risk": data.get("regulatory_risk", "Moderate"),
            "regulatory_risk_score": reg_score,
            "risk_score": risk_score,
            "key_factors": data.get("key_factors", []),
            "summary": data.get("summary", f"Live sector analysis completed for {industry}."),
            "method": "tavily_llm_live",
        }

    except Exception as e:
        print(f"Sector analysis live failed: {e}")
        result = _get_demo_sector(company_name, industry)
        result["method"] = "sector_fallback"
        result["error"] = str(e)
        return result
