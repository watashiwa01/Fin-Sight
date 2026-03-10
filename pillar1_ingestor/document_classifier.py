"""
Document Classifier for Intelli-Credit.
Routes uploaded PDFs to the correct parser based on filename patterns
and content keyword analysis. In live mode, uses LLM zero-shot classification.
"""
import re
from pathlib import Path

# Keyword patterns for rule-based classification
CLASSIFICATION_RULES = {
    "annual_report": {
        "filename_patterns": [r"annual.?report", r"ar[\s_-]?\d{4}", r"directors.?report"],
        "content_keywords": ["directors' report", "annual report", "auditor", "balance sheet",
                             "profit and loss", "shareholders", "board of directors"],
    },
    "bank_statement": {
        "filename_patterns": [r"bank.?stat", r"account.?stat", r"transaction"],
        "content_keywords": ["account number", "opening balance", "closing balance",
                             "debit", "credit", "withdrawal", "deposit", "cheque"],
    },
    "gst_return": {
        "filename_patterns": [r"gstr", r"gst.?return", r"3b", r"2a", r"gst"],
        "content_keywords": ["gstin", "gstr-3b", "gstr-2a", "taxable value", "integrated tax",
                             "input tax credit", "outward supplies", "inward supplies"],
    },
    "balance_sheet": {
        "filename_patterns": [r"balance.?sheet", r"bs[\s_-]?\d{4}"],
        "content_keywords": ["balance sheet", "assets", "liabilities", "equity",
                             "current assets", "non-current assets", "reserves"],
    },
    "profit_loss": {
        "filename_patterns": [r"profit.?(and)?[\s_-]?loss", r"p[\s_&]?l", r"income.?stat"],
        "content_keywords": ["profit and loss", "income statement", "revenue from operations",
                             "total income", "total expenses", "net profit"],
    },
    "legal_notice": {
        "filename_patterns": [r"legal", r"notice", r"court", r"litigation"],
        "content_keywords": ["legal notice", "court order", "petition", "respondent",
                             "plaintiff", "defendant", "jurisdiction"],
    },
    "sanction_letter": {
        "filename_patterns": [r"sanction", r"loan.?letter", r"facility.?letter"],
        "content_keywords": ["sanction letter", "loan sanctioned", "facility", "rate of interest",
                             "repayment schedule", "security", "terms and conditions"],
    },
}


def classify_document(filename: str, content_text: str = "") -> dict:
    """
    Classify a document based on filename and content.
    Returns: {type, confidence, method}
    """
    filename_lower = filename.lower()
    content_lower = content_text.lower() if content_text else ""

    best_match = "other"
    best_score = 0
    method = "rule_based"

    for doc_type, rules in CLASSIFICATION_RULES.items():
        score = 0

        # Check filename patterns
        for pattern in rules["filename_patterns"]:
            if re.search(pattern, filename_lower):
                score += 3  # Filename match is strong signal

        # Check content keywords
        if content_lower:
            keyword_matches = sum(1 for kw in rules["content_keywords"] if kw in content_lower)
            score += keyword_matches

        if score > best_score:
            best_score = score
            best_match = doc_type

    confidence = min(best_score / 8.0, 1.0)  # Normalize to 0-1

    return {
        "type": best_match,
        "confidence": round(confidence, 2),
        "method": method,
        "filename": filename,
    }


async def classify_document_llm(filename: str, content_text: str, llm_client) -> dict:
    """
    Classify a document using LLM zero-shot classification.
    Used in live mode for higher accuracy.
    """
    from config import DOC_TYPES

    prompt = f"""Classify this document into one of these categories: {', '.join(DOC_TYPES)}

Filename: {filename}
Content (first 2000 chars):
{content_text[:2000]}

Respond with ONLY a JSON object:
{{"type": "<category>", "confidence": <0.0-1.0>}}"""

    try:
        response = await llm_client.ainvoke(prompt)
        import json
        result = json.loads(response.content)
        result["method"] = "llm"
        result["filename"] = filename
        return result
    except Exception:
        # Fallback to rule-based
        result = classify_document(filename, content_text)
        result["method"] = "rule_based_fallback"
        return result
