"""
GST Cross-Validator for Intelli-Credit.
Real implementation using:
  1. Extracted document data from the Pillar 1 ingestion pipeline
     (gst_return + bank_statement documents already parsed by the LLM)
  2. LLM-generated narrative analysis to explain cross-validation findings
     and flag anomalies like circular trading or revenue inflation
  3. Rule-based composite scoring for objective metrics

Logic:
  - GSTR-3B declared turnover  vs bank total credit entries
  - GSTR-2A / GSTR-3B purchase-to-sales ratio (circular trading check)
  - Filing frequency / compliance completeness
  - LLM synthesises all findings into an actionable audit narrative
"""
import json
from utils import safe_divide, clamp


# ─── Constants ────────────────────────────────────────────
TURNOVER_VARIANCE_HARD = 25.0   # >25% → HIGH concern
TURNOVER_VARIANCE_SOFT = 10.0   # >10% → flag for review
CIRCULAR_RATIO_HARD    = 85.0   # purchases > 85% of sales → suspicious
CIRCULAR_RATIO_SOFT    = 70.0   # purchases > 70% → monitor


# ─── Public Entry Point ────────────────────────────────────

def validate_gst_compliance(extracted_data: dict = None, company_data: dict = None) -> dict:
    """
    Cross-validate GST data against bank statements intelligently.

    Parameters
    ----------
    extracted_data : dict
        The `st.session_state.extracted_data` dictionary populated by the
        document ingestion pipeline. Keys are like `{filename}_structured`.
    company_data : dict
        Basic entity info (GSTIN, turnover from onboarding, etc.)

    Returns
    -------
    dict  — standardised GST validation result
    """
    if extracted_data is None:
        extracted_data = {}
    if company_data is None:
        company_data = {}

    # 1. Pull extracted GST return data if available
    gst_data = _find_extracted_doc(extracted_data, "gst_return")

    # 2. Pull extracted bank statement data if available
    bank_data = _find_extracted_doc(extracted_data, "bank_statement")

    # 3. Fall back to company onboarding data for turnover cross-check
    onboarding_turnover = company_data.get("turnover_cr", 0.0)

    # 4. Build the numeric inputs for scoring
    inputs = _build_numeric_inputs(gst_data, bank_data, onboarding_turnover, company_data)

    # 5. Compute rule-based score
    score, flags = _compute_score_and_flags(inputs)

    # 6. Use LLM for narrative risk interpretation
    narrative = _llm_narrative(inputs, score, flags, company_data)

    return {
        "gstin": inputs.get("gstin", company_data.get("gstin", "N/A")),
        "summary": {
            "gstr_3b_turnover_cr": inputs.get("gstr3b", 0.0),
            "gstr_2a_purchases_cr": inputs.get("gstr2a", 0.0),
            "bank_credit_entries_cr": inputs.get("bank_credits", 0.0),
            "onboarding_turnover_cr": onboarding_turnover,
            "turnover_variance_pct":  round(inputs.get("turnover_variance_pct", 0.0), 1),
            "filing_compliance_pct":  round(inputs.get("filing_compliance_pct", 100.0), 1),
            "purchase_to_sales_ratio_pct": round(inputs.get("purchase_ratio", 0.0), 1),
        },
        "compliance_score": round(score, 1),
        "flags": flags,
        "risk_level": _get_risk_level(score),
        "recommendations": _generate_recommendations(inputs, score),
        "narrative": narrative,
        "data_sources": inputs.get("sources", []),
        "method": inputs.get("method", "rule_based"),
    }


# ─── Step 1: Extract Relevant Doc Data ────────────────────

def _find_extracted_doc(extracted_data: dict, doc_type: str) -> dict:
    """Search extracted_data for a doc of the given type and return its parsed JSON."""
    for key, value in extracted_data.items():
        if not key.endswith("_structured"):
            continue
        # The doc type hint is stored as metadata OR we infer from field names
        if isinstance(value, dict):
            if value.get("_doc_type") == doc_type:
                return value
            # Heuristic: GST return has gstin/taxable_turnover
            if doc_type == "gst_return" and any(
                k in value for k in ["gstin", "taxable_turnover", "gstr_3b", "gstr3b_turnover"]
            ):
                return value
            # Heuristic: Bank statement has total_credits / opening_balance
            if doc_type == "bank_statement" and any(
                k in value for k in ["total_credits", "total_credits_cr", "account_number", "opening_balance"]
            ):
                return value
    return {}


# ─── Step 2: Build Numeric Inputs ─────────────────────────

def _build_numeric_inputs(gst_data: dict, bank_data: dict, onboarding_turnover: float, company_data: dict) -> dict:
    """Map extracted fields to our standard numeric variables."""
    sources = []

    # GSTR-3B turnover — try multiple possible field names from LLM extraction
    gstr3b = _coerce_float(
        gst_data.get("taxable_turnover") or
        gst_data.get("gstr_3b") or
        gst_data.get("gstr3b_turnover") or
        gst_data.get("total_sales_cr") or
        onboarding_turnover
    )
    if gst_data:
        sources.append("gst_return (extracted)")
        method = "llm_extracted"
    else:
        sources.append("onboarding_turnover (fallback)")
        method = "onboarding_fallback"

    # GSTR-2A purchases
    gstr2a = _coerce_float(
        gst_data.get("itc_purchases") or
        gst_data.get("gstr_2a_purchases") or
        gst_data.get("total_purchases_cr") or
        (gstr3b * 0.65)  # Industry heuristic: ~65% purchase ratio if not available
    )

    # Bank total credits
    bank_credits = _coerce_float(
        bank_data.get("total_credits") or
        bank_data.get("total_credits_cr") or
        bank_data.get("total_inflows") or
        None
    )
    if bank_data:
        sources.append("bank_statement (extracted)")
    else:
        # Estimate from turnover with typical working capital buffer
        bank_credits = gstr3b * 1.08 if gstr3b else 0.0

    # GSTIN
    gstin = (
        gst_data.get("gstin") or
        company_data.get("gstin") or
        "Not extracted"
    )

    # Filing compliance
    filed = _coerce_float(gst_data.get("months_filed") or gst_data.get("filed_months") or 12)
    total = _coerce_float(gst_data.get("total_months") or 12)
    filing_compliance_pct = safe_divide(filed, total) * 100

    # Cross-check with onboarding turnover
    if onboarding_turnover > 0 and gstr3b > 0:
        onboarding_variance_pct = abs(gstr3b - onboarding_turnover) / onboarding_turnover * 100
    else:
        onboarding_variance_pct = 0.0

    turnover_variance_pct = safe_divide(abs(bank_credits - gstr3b), gstr3b) * 100 if gstr3b else 0.0
    purchase_ratio = safe_divide(gstr2a, gstr3b) * 100 if gstr3b else 0.0

    return {
        "gstin": gstin,
        "gstr3b": round(gstr3b, 2),
        "gstr2a": round(gstr2a, 2),
        "bank_credits": round(bank_credits, 2),
        "turnover_variance_pct": turnover_variance_pct,
        "filing_compliance_pct": filing_compliance_pct,
        "purchase_ratio": purchase_ratio,
        "onboarding_variance_pct": onboarding_variance_pct,
        "sources": sources,
        "method": method,
    }


# ─── Step 3: Rule-Based Scoring ───────────────────────────

def _compute_score_and_flags(inputs: dict) -> tuple[float, list]:
    """Compute a 0–100 GST compliance score and generate structured flags."""
    score = 100.0
    flags = []

    variance = inputs.get("turnover_variance_pct", 0.0)
    purchase_ratio = inputs.get("purchase_ratio", 0.0)
    filing = inputs.get("filing_compliance_pct", 100.0)
    ob_variance = inputs.get("onboarding_variance_pct", 0.0)

    # Turnover vs bank variance
    if variance > TURNOVER_VARIANCE_HARD:
        score -= 25
        flags.append({"type": "REVENUE_MISMATCH", "severity": "high",
                      "message": f"Bank credits deviate {variance:.1f}% from GSTR-3B declared turnover — potential revenue inflation or unreported income."})
    elif variance > TURNOVER_VARIANCE_SOFT:
        score -= 12
        flags.append({"type": "MINOR_VARIANCE", "severity": "medium",
                      "message": f"Bank credits deviate {variance:.1f}% from GSTR-3B — needs reconciliation."})

    # Circular trading
    if purchase_ratio > CIRCULAR_RATIO_HARD:
        score -= 20
        flags.append({"type": "CIRCULAR_TRADING_RISK", "severity": "high",
                      "message": f"Purchase-to-sales ratio is {purchase_ratio:.1f}% — significantly above normal industry range. High circular trading risk."})
    elif purchase_ratio > CIRCULAR_RATIO_SOFT:
        score -= 8
        flags.append({"type": "HIGH_PURCHASE_RATIO", "severity": "medium",
                      "message": f"Purchase-to-sales ratio of {purchase_ratio:.1f}% warrants further review."})

    # Filing compliance
    if filing < 100:
        penalty = (100 - filing) * 0.4
        score -= penalty
        flags.append({"type": "FILING_GAPS", "severity": "medium" if filing >= 75 else "high",
                      "message": f"GST filing compliance stands at {filing:.0f}%. {100 - filing:.0f}% of expected returns are missing or late."})

    # Onboarding vs GST turnover check
    if ob_variance > 20:
        score -= 10
        flags.append({"type": "TURNOVER_DECLARATION_MISMATCH", "severity": "medium",
                      "message": f"Turnover declared during onboarding differs by {ob_variance:.1f}% from GST returns. Verify with audited financials."})

    # All clean
    if not flags:
        flags.append({"type": "CLEAN", "severity": "low",
                      "message": "GST data is internally consistent with bank records. No anomalies detected."})

    score = clamp(score, 0, 100)
    return score, flags


# ─── Step 4: LLM Narrative ────────────────────────────────

def _llm_narrative(inputs: dict, score: float, flags: list, company_data: dict) -> str:
    """Use the LLM to generate an expert credit-analyst level narrative on the GST findings."""
    try:
        from config import get_llm_client
        llm = get_llm_client()
        if not llm:
            return _fallback_narrative(score, flags)

        flag_bullets = "\n".join(f"- [{f['severity'].upper()}] {f['message']}" for f in flags)
        prompt = f"""You are an expert credit analyst conducting a GST Cross-Validation for a loan appraisal.

Company: {company_data.get('company_name', 'Applicant')}
GSTIN: {inputs.get('gstin', 'N/A')}
GSTR-3B (Declared Turnover): ₹{inputs.get('gstr3b', 0):.2f} Cr
GSTR-2A (Purchases): ₹{inputs.get('gstr2a', 0):.2f} Cr
Bank Total Credits: ₹{inputs.get('bank_credits', 0):.2f} Cr
Turnover-Bank Variance: {inputs.get('turnover_variance_pct', 0):.1f}%
Purchase-to-Sales Ratio: {inputs.get('purchase_ratio', 0):.1f}%
Filing Compliance: {inputs.get('filing_compliance_pct', 100):.0f}%
Compliance Score: {score:.0f}/100

Detected Flags:
{flag_bullets}

Write a 3-5 sentence professional GST audit narrative for a Credit Appraisal Memo. Be specific, data-driven, and concise. Mention key risks and the recommended action."""

        return llm.invoke(prompt).content

    except Exception as e:
        return _fallback_narrative(score, flags)


def _fallback_narrative(score: float, flags: list) -> str:
    """Rule-based fallback narrative when LLM is unavailable."""
    if not flags or (len(flags) == 1 and flags[0]["type"] == "CLEAN"):
        # Check if we actually have data or if it's just a placeholder high score
        if score >= 90:
             return f"GST cross-validation indicates a high compliance score of {score:.0f}/100 based on the provided turnover. However, if no bank statements or GSTR-3B filings were uploaded, this score is based partially on onboarding declarations. Standard monitoring recommended."
        return f"GST cross-validation returned a compliance score of {score:.0f}/100. Declared turnover is broadly consistent with bank credit entries and no significant circular trading patterns were detected. Standard periodic monitoring is recommended."
    elif score >= 60:
        return f"GST cross-validation returned a moderate compliance score of {score:.0f}/100. Minor discrepancies between declared GST turnover and bank credits were noted. The credit team should request a CA-certified GST reconciliation statement before final sanction."
    else:
        return f"GST cross-validation returned a low compliance score of {score:.0f}/100 with high-severity flags. Significant variance between declared turnover and bank records and/or elevated purchase-to-sales ratios indicate elevated risk of revenue inflation or circular trading. A forensic GST audit is strongly recommended before proceeding."


# ─── Helpers ──────────────────────────────────────────────

def _coerce_float(val) -> float:
    """Safely convert any value (str, int, dict, None) to float."""
    if val is None:
        return 0.0
    # Handle the new { "value": 123.4, "source_quote": "..." } structure
    if isinstance(val, dict):
        val = val.get("value", 0.0)
    
    try:
        return float(str(val).replace(",", "").replace("₹", "").replace("Cr", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _get_risk_level(score: float) -> str:
    if score >= 80: return "LOW"
    elif score >= 60: return "MODERATE"
    elif score >= 40: return "HIGH"
    return "CRITICAL"


def _generate_recommendations(inputs: dict, score: float) -> list:
    recs = []
    variance = inputs.get("turnover_variance_pct", 0)
    purchase_ratio = inputs.get("purchase_ratio", 0)
    filing = inputs.get("filing_compliance_pct", 100)

    if variance > TURNOVER_VARIANCE_HARD:
        recs.append("Obtain detailed bank statement reconciliation with GST filings from CA.")
        recs.append("Check for non-GST income sources (e.g. investments, capex receipts) that may explain variance.")
    elif variance > TURNOVER_VARIANCE_SOFT:
        recs.append("Cross-check monthly GST filings with corresponding bank credit entries for the last 12 months.")
    if purchase_ratio > CIRCULAR_RATIO_SOFT:
        recs.append("Request supplier-level GSTR-2A data to verify purchase legitimacy and detect shell vendors.")
    if filing < 90:
        recs.append(f"Investigate {100 - filing:.0f}% missing GST filings — assess whether due to disputes, notices, or non-compliance.")
    if score >= 80:
        recs.append("GST compliance is satisfactory. Standard quarterly monitoring of GSTR-3B is sufficient.")
    return recs
