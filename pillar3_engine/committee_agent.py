"""
AI Credit Committee Agent for Intelli-Credit.
Synthesizes findings from all 3 Pillars (Extraction, Research, Scoring) 
into a cohesive qualitative verdict and 'AI Investment Rationale'.
"""
import json
from config import get_llm_client, LLM_PROVIDER

COMMITTEE_PROMPT = """
You are the 'Intelli-Credit AI Committee', an elite panel of senior credit officers.
Your task is to review a credit application by triangulating data from multiple sources.

### INPUT DATA:
1. **Company Info**: {company_data}
2. **Financial Extraction**: {financials}
3. **Research Insights**: {research}
4. **GST & Bank Validation**: {gst_validation}
5. **Scorecard Results**: {scoring}

### YOUR MANDATE:
- **Triangulation**: Do the financial numbers align with research and GST data? 
  (e.g., If revenue is ₹100Cr, do GST filings and Bank credits support this?)
- **Risk Identification**: Identify hidden risks (Management quality, industry headwinds, circular trading).
- **Verdict**: Provide a final 'Approve', 'Reject', or 'Refer' recommendation with deep reasoning.

Return a valid JSON object:
{{
  "verdict": "APPROVE" | "REJECT" | "REFER",
  "confidence": float (0.0-1.0),
  "rationale": string (Expert narrative),
  "triangulation_check": string (Analysis of data consistency),
  "key_strengths": [string],
  "key_concerns": [string],
  "mitigants": [string]
}}
"""

class CommitteeAgent:
    def __init__(self):
        self.client = get_llm_client()

    async def deliberate(self, company_data: dict, financials: dict, research: dict, 
                         gst_validation: dict, scoring: dict) -> dict:
        """
        Synthesize all inputs and provide a senior credit committee verdict.
        """
        if not self.client:
            return self._get_fallback_verdict(scoring)

        prompt = COMMITTEE_PROMPT.format(
            company_data=json.dumps(company_data, indent=2),
            financials=json.dumps(financials, indent=2),
            research=json.dumps(research, indent=2),
            gst_validation=json.dumps(gst_validation, indent=2),
            scoring=json.dumps(scoring, indent=2)
        )

        try:
            response = await self.client.ainvoke(prompt)
            content = response.content
            
            # Clean JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content.strip())
        except Exception as e:
            return self._get_fallback_verdict(scoring, error=str(e))

    def _get_fallback_verdict(self, scoring: dict, error: str = None) -> dict:
        score = scoring.get("credit_score", 50)
        verdict = "REFER"
        if score > 75: verdict = "APPROVE"
        elif score < 40: verdict = "REJECT"
        
        return {
            "verdict": verdict,
            "confidence": 0.5,
            "rationale": f"Fallback verdict based on scorecard alone. (Error: {error})" if error else "LLM not available.",
            "triangulation_check": "Pending manual review.",
            "key_strengths": ["Automated scorecard result"],
            "key_concerns": ["LLM synthesis failed"],
            "mitigants": ["Verify documents manually"]
        }
