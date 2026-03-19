"""
SWOT & Triangulation Generator for Intelli-Credit.
Analyzes the 5 Cs, research results, and company data to generate a SWOT analysis.
"""
from config import get_llm_client, IS_DEMO

def generate_swot_sync(company_data: dict, five_cs: dict, scoring: dict, research: dict) -> str:
    """Generate a SWOT analysis synchronously."""
    name = company_data.get('company_name', 'the applicant company')
    if IS_DEMO:
        return (
            "**STRENGTHS**\n"
            f"• Strong revenue growth (15% YoY) and solid current ratio (1.8x) for {name}.\n"
            "• Positive media sentiment; established brand reputation.\n\n"
            "**WEAKNESSES**\n"
            "• High debt-to-equity ratio indicating leveraged capital structure.\n"
            "• Marginal DSCR (~1.1x) suggests tight cash flows for repayment.\n\n"
            "**OPPORTUNITIES**\n"
            f"• Expansion of {name} into new geographic markets with recent loan request.\n"
            "• Favorable industry outlook and regulatory environment.\n\n"
            "**THREATS**\n"
            "• Potential civil litigation cases could impact short-term liquidity.\n"
            "• Macro-economic tightening may increase cost of future borrowings."
        )
    
    llm = get_llm_client()
    if not llm:
        return "SWOT Analysis not available (No LLM key configured)."
        
    prompt = f"""You are an expert Credit Analyst. Generate a concise, professional SWOT Analysis (Strengths, Weaknesses, Opportunities, Threats) for {company_data.get('company_name', 'the applicant company')}.
    
    Use the following triangulated data points:
    1. Financial Health (5 Cs Scores): {five_cs.get('scores', {})}
    2. Research Risk Level: {research.get('risk_level', 'N/A')}
    3. Research Summary: {research.get('summary', 'N/A')}
    4. Model Decision: {scoring.get('decision', 'N/A')}
    
    Format as Markdown with 4 clear sections (STRENGTHS, WEAKNESSES, OPPORTUNITIES, THREATS) and use bullet points. Make the analysis data-driven and concise.
    """
    
    import asyncio, concurrent.futures
    try:
        def _call_llm():
            import asyncio
            # In some environments asyncio.run creates a new event loop. 
            # Using llm.invoke() if it's available and synchronous is easier.
            if hasattr(llm, "invoke"):
                return llm.invoke(prompt).content
            return asyncio.run(llm.ainvoke(prompt)).content
            
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                res = pool.submit(_call_llm).result()
        else:
            res = _call_llm()
            
        return res
    except Exception as e:
        print(f"Error generating SWOT, using fallback: {e}")
        return (
            "**STRENGTHS**\n"
            "**OPPORTUNITIES**\n"
            "• Expansion into new geographic markets with recent loan request.\n"
            "• Favorable industry outlook and regulatory environment.\n\n"
            "**THREATS**\n"
            "• 2 pending civil litigation cases could impact short-term liquidity.\n"
            "• Macro-economic tightening may increase cost of future borrowings."
        )
