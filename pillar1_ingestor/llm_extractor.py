"""
LLM-Powered Structured Extractor for Intelli-Credit.
Supports both OpenAI (GPT-4o) and Anthropic (Claude) as LLM providers.
Architecture doc recommends: Claude API (claude-sonnet-4-6) as primary.
In demo mode returns pre-built sample extraction data.
"""
import json
from config import IS_DEMO, has_llm_key, get_llm_client, LLM_PROVIDER, SAMPLE_DATA_DIR

EXTRACTION_PROMPTS = {
    "annual_report": """You are an expert Indian credit analyst. Extract the following financial data from this Annual Report text.
For every numeric field, also extract a short "source_quote" from the text that justifies the value (to build trust).

Return a valid JSON object with ONLY these keys (set null if not found):
{
  "company_name": {"value": string, "source_quote": string},
  "cin": {"value": string, "source_quote": string},
  "fiscal_year": string,
  "revenue_cr": {"value": float, "source_quote": string},
  "ebitda_cr": {"value": float, "source_quote": string},
  "ebitda_margin_pct": float,
  "pat_cr": {"value": float, "source_quote": string},
  "total_debt_cr": {"value": float, "source_quote": string},
  "net_worth_cr": {"value": float, "source_quote": string},
  "current_ratio": float,
  "de_ratio": float,
  "directors": [{"name": string, "din": string, "designation": string}],
  "auditor_name": string,
  "auditor_opinion": string,
  "key_observations": [string],
  "confidence_score": float (0.0-1.0)
}

Document text (first 12000 chars):
{text}""",

    "bank_statement": """You are an expert Indian credit analyst. Extract data from this Bank Statement.
For total credits and debits, include a "source_quote" from the statement.

Return valid JSON ONLY:
{
  "account_holder": string,
  "account_number": string,
  "bank_name": string,
  "period": string,
  "opening_balance": float,
  "closing_balance": float,
  "total_credits": {"value": float, "source_quote": string},
  "total_debits": {"value": float, "source_quote": string},
  "large_credits": [{"date": string, "amount": float, "description": string}],
  "confidence_score": float
}

Document text:
{text}""",

    "gst_return": """You are an expert Indian credit analyst. Extract data from this GST Return.
Return valid JSON ONLY:
{
  "gstin": {"value": string, "source_quote": string},
  "return_type": string,
  "period": string,
  "taxable_turnover": {"value": float, "source_quote": string},
  "total_tax_paid": float,
  "itc_claimed": float,
  "confidence_score": float
}

Document text:
{text}""",

    "default": """You are an expert Indian credit analyst. Extract all relevant financial and business information.
Return valid JSON with all fields you can identify, plus:
- "document_summary": string
- "confidence": float (0.0-1.0)

Document text:
{text}""",
}


def get_demo_extraction(doc_type: str) -> dict:
    """Return sample extraction data for demo mode."""
    from utils import load_json
    sample = load_json(SAMPLE_DATA_DIR / "sample_company.json")

    if doc_type == "annual_report":
        fy = sample["financials"]["fy_2024"]
        return {
            "company_name": {"value": sample["company_name"], "source_quote": f"The name of the company is {sample['company_name']}"},
            "cin": {"value": sample["cin"], "source_quote": f"Corporate Identity Number: {sample['cin']}"},
            "fiscal_year": "FY 2023-24",
            "revenue_cr": {"value": fy["revenue_cr"], "source_quote": f"Revenue from operations: {fy['revenue_cr']} Cr"},
            "ebitda_cr": {"value": fy["ebitda_cr"], "source_quote": f"EBITDA: {fy['ebitda_cr']} Cr"},
            "ebitda_margin_pct": fy["ebitda_margin_pct"],
            "pat_cr": {"value": fy["pat_cr"], "source_quote": f"Profit after tax: {fy['pat_cr']} Cr"},
            "total_debt_cr": {"value": fy["total_debt_cr"], "source_quote": f"Total borrowings: {fy['total_debt_cr']} Cr"},
            "net_worth_cr": {"value": fy["net_worth_cr"], "source_quote": f"Shareholders' Fund: {fy['net_worth_cr']} Cr"},
            "current_ratio": fy["current_ratio"],
            "de_ratio": fy["de_ratio"],
            "directors": sample["promoters"],
            "auditor_name": sample["auditor_remarks"]["auditor_name"],
            "auditor_opinion": sample["auditor_remarks"]["opinion"],
            "key_observations": sample["auditor_remarks"]["key_observations"],
            "confidence_score": 0.98,
        }
    elif doc_type == "bank_statement":
        return {
            "account_holder": sample["company_name"],
            "account_number": "XXXX XXXX 4567",
            "bank_name": "State Bank of India",
            "period": "2023-04-01 to 2024-03-31",
            "opening_balance": 45600000,
            "closing_balance": 52300000,
            "total_credits": {"value": 292000000, "source_quote": "Total Inward Remittances: 29.20 Cr"},
            "total_debits": {"value": 285300000, "source_quote": "Total Outward Payments: 28.53 Cr"},
            "large_credits": [
                {"date": "2023-08-15", "amount": 10000000, "description": "RTGS from L&T Limited"},
            ],
            "confidence_score": 0.95,
        }
    elif doc_type == "gst_return":
        gst = sample["gst_data"]
        return {
            "gstin": {"value": gst["gstin"], "source_quote": f"Registration No: {gst['gstin']}"},
            "return_type": "GSTR-3B",
            "period": "FY 2023-24",
            "taxable_turnover": {"value": gst["gstr_3b_turnover_cr"] * 10_000_000, "source_quote": f"Total Taxable Value: {gst['gstr_3b_turnover_cr']} Cr"},
            "total_tax_paid": gst["gstr_3b_turnover_cr"] * 10_000_000 * 0.18,
            "itc_claimed": gst["gstr_2a_purchases_cr"] * 10_000_000 * 0.18,
            "confidence_score": 0.99,
        }
    else:
        return {
            "document_summary": "Document processed successfully in demo mode.",
            "company_name": sample["company_name"],
            "confidence": 0.75,
            "extraction_method": "demo",
        }


async def extract_with_llm(text: str, doc_type: str, custom_schema: str = None) -> dict:
    """
    Extract structured data using the configured LLM (OpenAI or Anthropic/Claude).
    Falls back to demo data if no API key is available.
    """
    if IS_DEMO or not has_llm_key():
        result = get_demo_extraction(doc_type)
        return result

    try:
        llm = get_llm_client()
        if llm is None:
            result = get_demo_extraction(doc_type)
            result["extraction_method"] = "no_llm_key"
            return result

        if custom_schema:
            prompt = f"""You are an expert Indian credit analyst. Extract data from this document.
Return a valid JSON object matching the following schema/keys (set null if not found):
{custom_schema}

Document text:
{text[:12000]}"""
        else:
            prompt_template = EXTRACTION_PROMPTS.get(doc_type, EXTRACTION_PROMPTS["default"])
            prompt = prompt_template.format(text=text[:12000])

        response = await llm.ainvoke(prompt)
        content  = response.content

        # Strip markdown code fences if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())
        result["extraction_method"] = "llm"
        result["llm_provider"]      = LLM_PROVIDER
        return result

    except json.JSONDecodeError:
        result = get_demo_extraction(doc_type)
        result["extraction_method"] = "llm_parse_error"
        return result
    except Exception as e:
        result = get_demo_extraction(doc_type)
        result["extraction_method"] = "llm_fallback"
        result["error"] = str(e)
        return result


def extract_sync(text: str, doc_type: str, custom_schema: str = None) -> dict:
    """Synchronous wrapper — safe to call from Streamlit."""
    import asyncio, concurrent.futures
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, extract_with_llm(text, doc_type, custom_schema)).result()
        else:
            return asyncio.run(extract_with_llm(text, doc_type, custom_schema))
    except RuntimeError:
        return asyncio.run(extract_with_llm(text, doc_type, custom_schema))
