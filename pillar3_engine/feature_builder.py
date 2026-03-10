"""
5 Cs Feature Builder for Intelli-Credit.
Maps extracted financial data + research findings to the 5 Cs of Credit framework:
Character, Capacity, Capital, Collateral, Conditions.
"""
from utils import safe_divide, clamp, compute_cagr
from config import FIVE_CS_WEIGHTS


def _get_val(data: dict, key: str, default: float = 0.0) -> float:
    """Safely get numeric value from a key that might be a dict or float."""
    val = data.get(key, default)
    if isinstance(val, dict):
        return val.get("value", default)
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def build_features(financials: dict, research: dict, gst_validation: dict = None,
                   collateral: dict = None, qualitative_notes: list = None) -> dict:
    """
    Build the 5 Cs feature vector from all available data sources.

    Returns dict with:
    - features: {character: {}, capacity: {}, capital: {}, collateral: {}, conditions: {}}
    - scores: {character: 0-100, capacity: 0-100, ...}
    - composite_score: weighted 0-100
    - feature_vector: flat list for ML model input
    """
    character = _build_character(research)
    capacity = _build_capacity(financials)
    capital = _build_capital(financials)
    collateral_features = _build_collateral(collateral, financials)
    conditions = _build_conditions(research, qualitative_notes, gst_validation)

    # Compute per-C scores (0-100)
    scores = {
        "character": _score_character(character),
        "capacity": _score_capacity(capacity),
        "capital": _score_capital(capital),
        "collateral": _score_collateral(collateral_features),
        "conditions": _score_conditions(conditions),
    }

    # Weighted composite
    composite = sum(scores[c] * FIVE_CS_WEIGHTS[c] for c in scores)

    # Build flat feature vector for ML model
    feature_vector = _build_feature_vector(character, capacity, capital, collateral_features, conditions)

    return {
        "features": {
            "character": character,
            "capacity": capacity,
            "capital": capital,
            "collateral": collateral_features,
            "conditions": conditions,
        },
        "scores": scores,
        "composite_score": round(composite, 1),
        "feature_vector": feature_vector,
        "feature_names": _get_feature_names(),
    }


def _build_character(research: dict) -> dict:
    """Character: Trustworthiness and track record."""
    news = research.get("news", {})
    mca = research.get("mca", {})
    litigation = research.get("litigation", {})

    return {
        "litigation_count": litigation.get("total_cases", 0),
        "pending_cases": litigation.get("pending_cases", 0),
        "criminal_cases": litigation.get("criminal_cases", 0),
        "news_sentiment_score": news.get("overall_sentiment", 0),
        "mca_compliance_score": mca.get("compliance", {}).get("compliance_score",
                                                               mca.get("risk_score", 50)),
        "prior_defaults": 0,  # From CIBIL data if available
        "director_disqualifications": 0,
        "roc_notices": mca.get("compliance", {}).get("roc_notices", 0),
    }


def _build_capacity(financials: dict) -> dict:
    """Capacity: Ability to repay."""
    fy_latest = financials.get("fy_2024", financials)
    fy_prev = financials.get("fy_2023", {})
    fy_oldest = financials.get("fy_2022", {})

    revenue_latest = _get_val(fy_latest, "revenue_cr", 0)
    revenue_oldest = _get_val(fy_oldest, "revenue_cr", revenue_latest)

    return {
        "dscr": _get_val(fy_latest, "dscr", 0),
        "icr": _get_val(fy_latest, "icr", 0),
        "revenue_cr": revenue_latest,
        "revenue_cagr_3yr": compute_cagr(revenue_oldest, revenue_latest, 2),
        "ebitda_margin_pct": _get_val(fy_latest, "ebitda_margin_pct", 0),
        "pat_cr": _get_val(fy_latest, "pat_cr", 0),
        "operating_cash_flow_cr": _get_val(fy_latest, "operating_cash_flow_cr", 0),
        "current_ratio": _get_val(fy_latest, "current_ratio", 0),
    }


def _build_capital(financials: dict) -> dict:
    """Capital: Financial strength."""
    fy_latest = financials.get("fy_2024", financials)

    return {
        "de_ratio": _get_val(fy_latest, "de_ratio", 0),
        "tangible_net_worth_cr": _get_val(fy_latest, "tangible_net_worth_cr", 0),
        "net_worth_cr": _get_val(fy_latest, "net_worth_cr", 0),
        "promoter_equity_pct": _get_val(fy_latest, "promoter_equity_pct", 0),
        "total_debt_cr": _get_val(fy_latest, "total_debt_cr", 0),
        "total_assets_cr": _get_val(fy_latest, "total_assets_cr", 0),
    }


def _build_collateral(collateral: dict, financials: dict) -> dict:
    """Collateral: Security coverage."""
    if not collateral:
        collateral = {}

    return {
        "asset_coverage_ratio": collateral.get("asset_coverage_ratio", 1.0),
        "ltv_pct": collateral.get("ltv_pct", 75.0),
        "security_type": collateral.get("security_type", "unknown"),
        "collateral_value_cr": collateral.get("collateral_value_cr", 0),
        "encumbrance_flag": 1 if collateral.get("encumbrance") else 0,
    }


def _build_conditions(research: dict, qualitative_notes: list = None, gst_validation: dict = None) -> dict:
    """Conditions: External environment."""
    sector = research.get("sector", {})

    # Process qualitative notes into a risk adjustment
    qual_risk_adjustment = 0
    if qualitative_notes:
        for note in qualitative_notes:
            note_lower = note.lower()
            if any(w in note_lower for w in ["capacity", "underutiliz", "idle", "shutdown"]):
                qual_risk_adjustment += 5
            elif any(w in note_lower for w in ["strong", "growth", "expansion", "order"]):
                qual_risk_adjustment -= 3
            elif any(w in note_lower for w in ["risk", "concern", "issue", "problem"]):
                qual_risk_adjustment += 3

    gst_score = 90
    if gst_validation:
        gst_score = gst_validation.get("compliance_score", 90)

    return {
        "industry_outlook_score": sector.get("outlook_score", 50),
        "regulatory_risk_score": sector.get("regulatory_risk_score", 50),
        "gst_compliance_score": gst_score,
        "qualitative_risk_adjustment": qual_risk_adjustment,
        "qualitative_notes_count": len(qualitative_notes) if qualitative_notes else 0,
    }


# --- Scoring Functions ---

def _score_character(c: dict) -> float:
    score = 100
    score -= c["litigation_count"] * 5
    score -= c["pending_cases"] * 10
    score -= c["criminal_cases"] * 25
    score += c["news_sentiment_score"] * 15
    score -= c["roc_notices"] * 8
    score -= c["prior_defaults"] * 30
    if c["mca_compliance_score"] > 0:
        score = score * 0.6 + c["mca_compliance_score"] * 0.4
    return clamp(score)


def _score_capacity(c: dict) -> float:
    score = 0
    # DSCR scoring
    if c["dscr"] >= 1.5:
        score += 30
    elif c["dscr"] >= 1.2:
        score += 20
    elif c["dscr"] >= 1.0:
        score += 10
    # ICR scoring
    if c["icr"] >= 3.0:
        score += 20
    elif c["icr"] >= 2.0:
        score += 15
    elif c["icr"] >= 1.5:
        score += 10
    # Revenue CAGR
    if c["revenue_cagr_3yr"] >= 15:
        score += 20
    elif c["revenue_cagr_3yr"] >= 8:
        score += 15
    elif c["revenue_cagr_3yr"] >= 0:
        score += 10
    # EBITDA margin
    if c["ebitda_margin_pct"] >= 15:
        score += 15
    elif c["ebitda_margin_pct"] >= 10:
        score += 10
    elif c["ebitda_margin_pct"] >= 5:
        score += 5
    # Current ratio
    if c["current_ratio"] >= 1.5:
        score += 15
    elif c["current_ratio"] >= 1.2:
        score += 10
    elif c["current_ratio"] >= 1.0:
        score += 5
    return clamp(score)


def _score_capital(c: dict) -> float:
    score = 0
    # D/E ratio
    if c["de_ratio"] <= 0.5:
        score += 30
    elif c["de_ratio"] <= 1.0:
        score += 25
    elif c["de_ratio"] <= 1.5:
        score += 15
    elif c["de_ratio"] <= 2.0:
        score += 5
    # Net worth
    if c["net_worth_cr"] >= 15:
        score += 25
    elif c["net_worth_cr"] >= 10:
        score += 20
    elif c["net_worth_cr"] >= 5:
        score += 15
    elif c["net_worth_cr"] > 0:
        score += 10
    # Promoter equity
    if c["promoter_equity_pct"] >= 70:
        score += 25
    elif c["promoter_equity_pct"] >= 50:
        score += 20
    elif c["promoter_equity_pct"] >= 30:
        score += 10
    # TNW
    if c["tangible_net_worth_cr"] >= 10:
        score += 20
    elif c["tangible_net_worth_cr"] >= 5:
        score += 15
    elif c["tangible_net_worth_cr"] > 0:
        score += 10
    return clamp(score)


def _score_collateral(c: dict) -> float:
    score = 0
    # ACR
    if c["asset_coverage_ratio"] >= 2.0:
        score += 35
    elif c["asset_coverage_ratio"] >= 1.5:
        score += 25
    elif c["asset_coverage_ratio"] >= 1.25:
        score += 15
    elif c["asset_coverage_ratio"] >= 1.0:
        score += 10
    # LTV
    if c["ltv_pct"] <= 50:
        score += 25
    elif c["ltv_pct"] <= 65:
        score += 20
    elif c["ltv_pct"] <= 75:
        score += 15
    elif c["ltv_pct"] <= 85:
        score += 10
    # Security type
    if c["security_type"] == "immovable":
        score += 25
    elif c["security_type"] == "movable":
        score += 15
    else:
        score += 5
    # Encumbrance penalty
    if c["encumbrance_flag"]:
        score -= 10
    return clamp(score)


def _score_conditions(c: dict) -> float:
    score = 0
    score += c["industry_outlook_score"] * 0.35
    score += (100 - c["regulatory_risk_score"]) * 0.25
    score += c["gst_compliance_score"] * 0.30
    score -= c["qualitative_risk_adjustment"]
    return clamp(score, 0, 100)


def _build_feature_vector(character, capacity, capital, collateral, conditions) -> list:
    """Build flat feature vector for ML model."""
    return [
        character["litigation_count"],
        character["pending_cases"],
        character["criminal_cases"],
        character["news_sentiment_score"],
        character["mca_compliance_score"],
        character["prior_defaults"],
        capacity["dscr"],
        capacity["icr"],
        capacity["revenue_cagr_3yr"],
        capacity["ebitda_margin_pct"],
        capacity["current_ratio"],
        capacity["operating_cash_flow_cr"],
        capital["de_ratio"],
        capital["tangible_net_worth_cr"],
        capital["promoter_equity_pct"],
        collateral["asset_coverage_ratio"],
        collateral["ltv_pct"],
        collateral["encumbrance_flag"],
        conditions["industry_outlook_score"],
        conditions["regulatory_risk_score"],
        conditions["gst_compliance_score"],
        conditions["qualitative_risk_adjustment"],
    ]


def _get_feature_names() -> list:
    """Return feature names matching the feature vector."""
    return [
        "Litigation Count", "Pending Cases", "Criminal Cases",
        "News Sentiment", "MCA Compliance", "Prior Defaults",
        "DSCR", "ICR", "Revenue CAGR 3yr", "EBITDA Margin %",
        "Current Ratio", "Operating Cash Flow",
        "D/E Ratio", "Tangible Net Worth", "Promoter Equity %",
        "Asset Coverage Ratio", "LTV %", "Encumbrance Flag",
        "Industry Outlook", "Regulatory Risk",
        "GST Compliance", "Qualitative Risk Adj",
    ]
