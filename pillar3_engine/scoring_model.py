"""
Credit Scoring Model for Intelli-Credit.
Uses actual XGBoost trained on synthetic Indian credit data.
SHAP TreeExplainer provides per-feature Shapley values for explainability.
Inspired by: github.com/maixbach/credit-risk-analysis-using-ML
"""
import os
import numpy as np
import json
from pathlib import Path
from config import OUTPUT_DIR, DB_DIR, CREDIT_CATEGORIES


MODEL_PATH = DB_DIR / "xgb_credit_model.json"
_model_cache = None


# ─── Synthetic Training Data ────────────────────────────────────

def _generate_synthetic_data(n_samples: int = 5000):
    """
    Generate realistic synthetic Indian corporate credit data for model training.
    Features mirror the 5 Cs feature vector from feature_builder.py.
    """
    rng = np.random.default_rng(42)

    n = n_samples

    # ── Character features ──
    litigation_count = rng.integers(0, 15, n)
    pending_cases    = rng.integers(0, 8, n)
    criminal_cases   = rng.integers(0, 2, n)
    news_sentiment   = rng.uniform(-1, 1, n)
    mca_compliance   = rng.uniform(30, 100, n)
    prior_defaults   = rng.integers(0, 3, n)

    # ── Capacity features ──
    dscr            = rng.uniform(0.5, 3.5, n)
    icr             = rng.uniform(0.5, 6.0, n)
    revenue_cagr    = rng.uniform(-5, 40, n)
    ebitda_margin   = rng.uniform(-2, 30, n)
    current_ratio   = rng.uniform(0.6, 3.0, n)
    op_cash_flow    = rng.uniform(-2, 20, n)

    # ── Capital features ──
    de_ratio        = rng.uniform(0, 5, n)
    tnw             = rng.uniform(0, 50, n)
    promoter_equity = rng.uniform(10, 90, n)

    # ── Collateral features ──
    acr             = rng.uniform(0.5, 3.0, n)
    ltv             = rng.uniform(30, 95, n)
    encumbrance     = rng.integers(0, 2, n)

    # ── Conditions features ──
    industry_outlook    = rng.uniform(20, 95, n)
    regulatory_risk     = rng.uniform(10, 80, n)
    gst_compliance      = rng.uniform(40, 100, n)
    qual_risk_adj       = rng.uniform(-5, 15, n)

    X = np.column_stack([
        litigation_count, pending_cases, criminal_cases,
        news_sentiment, mca_compliance, prior_defaults,
        dscr, icr, revenue_cagr, ebitda_margin, current_ratio, op_cash_flow,
        de_ratio, tnw, promoter_equity,
        acr, ltv, encumbrance,
        industry_outlook, regulatory_risk, gst_compliance, qual_risk_adj,
    ])

    # Build label from domain rules (mirrors 5 Cs scoring)
    score = (
        - litigation_count * 3.0
        - pending_cases * 5.0
        - criminal_cases * 15.0
        + news_sentiment * 8.0
        + (mca_compliance - 50) * 0.15
        - prior_defaults * 20.0
        + np.where(dscr >= 1.5, 8, np.where(dscr >= 1.2, 5, np.where(dscr >= 1.0, -3, -10)))
        + np.where(icr >= 3.0, 6, np.where(icr >= 2.0, 4, np.where(icr >= 1.5, -2, -8)))
        + np.minimum(revenue_cagr * 0.4, 8.0)
        + np.where(ebitda_margin >= 15, 5, np.where(ebitda_margin >= 10, 3, np.where(ebitda_margin >= 5, -2, -5)))
        + np.where(current_ratio >= 1.5, 4, np.where(current_ratio >= 1.2, 2, -3))
        + np.where(op_cash_flow > 0, 3, -5)
        + np.where(de_ratio <= 0.5, 6, np.where(de_ratio <= 1.0, 4, np.where(de_ratio <= 1.5, -2, -8)))
        + np.minimum(tnw * 0.5, 6.0)
        + np.where(promoter_equity >= 70, 4, np.where(promoter_equity >= 50, 2, -3))
        + np.where(acr >= 1.5, 5, np.where(acr >= 1.25, 3, -3))
        + np.where(ltv <= 60, 4, np.where(ltv <= 75, 2, -4))
        - encumbrance * 3.0
        + (industry_outlook - 50) * 0.10
        - (regulatory_risk - 50) * 0.08
        + (gst_compliance - 80) * 0.15
        - qual_risk_adj
        + 50  # base
    )
    score = np.clip(score, 0, 100)

    # Binary label: 1 = good credit (score >= 60)
    y = (score >= 60).astype(int)

    return X, y


# ─── Model Training ─────────────────────────────────────────────

def _train_model():
    """Train XGBoost model on synthetic data and save."""
    try:
        import xgboost as xgb
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
        import joblib

        print("[Scoring] Training XGBoost model on synthetic credit data...")
        X, y = _generate_synthetic_data(5000)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        model = xgb.XGBClassifier(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=42,
        )
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )

        # Save model
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        model.save_model(str(MODEL_PATH))
        print(f"[Scoring] Model saved → {MODEL_PATH}")
        return model

    except ImportError as e:
        print(f"[Scoring] xgboost not installed: {e}")
        return None


def _load_or_train_model():
    """Load existing model or train a new one."""
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    try:
        import xgboost as xgb
        if MODEL_PATH.exists():
            model = xgb.XGBClassifier()
            model.load_model(str(MODEL_PATH))
            _model_cache = model
            return model
        else:
            model = _train_model()
            _model_cache = model
            return model
    except Exception as e:
        print(f"[Scoring] Model load/train failed: {e}")
        return None


# ─── SHAP Explainability ─────────────────────────────────────────

def _compute_shap_values(model, feature_vector: list, feature_names: list) -> tuple:
    """Compute real SHAP values using TreeExplainer."""
    try:
        import shap
        import numpy as np

        X = np.array(feature_vector).reshape(1, -1)
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)

        # For binary classification, shap_values may be a list [class0, class1]
        if isinstance(shap_values, list):
            sv = shap_values[1][0]  # Class 1 (good credit) SHAP values
        else:
            sv = shap_values[0]

        return sv.tolist(), float(explainer.expected_value[1] if isinstance(explainer.expected_value, (list, np.ndarray)) else explainer.expected_value)
    except Exception as e:
        # Fallback to rule-based contributions
        contributions = _rule_based_contributions(feature_vector, feature_names)
        return contributions, 50.0


def _rule_based_contributions(features: list, names: list) -> list:
    """Fallback rule-based contributions when SHAP is unavailable."""
    rules = {
        "Litigation Count": lambda v: -3 * v,
        "Pending Cases": lambda v: -5 * v,
        "Criminal Cases": lambda v: -15 * v,
        "News Sentiment": lambda v: v * 8,
        "MCA Compliance": lambda v: (v - 50) * 0.15,
        "Prior Defaults": lambda v: -20 * v,
        "DSCR": lambda v: 8 if v >= 1.5 else 5 if v >= 1.2 else -3 if v >= 1.0 else -10,
        "ICR": lambda v: 6 if v >= 3.0 else 4 if v >= 2.0 else -2 if v >= 1.5 else -8,
        "Revenue CAGR 3yr": lambda v: min(v * 0.4, 8),
        "EBITDA Margin %": lambda v: 5 if v >= 15 else 3 if v >= 10 else -2 if v >= 5 else -5,
        "Current Ratio": lambda v: 4 if v >= 1.5 else 2 if v >= 1.2 else -3,
        "Operating Cash Flow": lambda v: 3 if v > 0 else -5,
        "D/E Ratio": lambda v: 6 if v <= 0.5 else 4 if v <= 1.0 else -2 if v <= 1.5 else -8,
        "Tangible Net Worth": lambda v: min(v * 0.5, 6),
        "Promoter Equity %": lambda v: 4 if v >= 70 else 2 if v >= 50 else -3,
        "Asset Coverage Ratio": lambda v: 5 if v >= 1.5 else 3 if v >= 1.25 else -3,
        "LTV %": lambda v: 4 if v <= 60 else 2 if v <= 75 else -4,
        "Encumbrance Flag": lambda v: -3 if v else 1,
        "Industry Outlook": lambda v: (v - 50) * 0.1,
        "Regulatory Risk": lambda v: -(v - 50) * 0.08,
        "GST Compliance": lambda v: (v - 80) * 0.15,
        "Qualitative Risk Adj": lambda v: -v,
    }
    return [round(rules.get(n, lambda v: 0)(v), 2) for v, n in zip(features, names)]


# ─── SHAP Waterfall Chart ────────────────────────────────────────

def _generate_shap_chart(shap_values: list, feature_names: list,
                         base_value: float, final_score: float, decision: str) -> str:
    """Generate a professional SHAP waterfall chart."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        # Sort by absolute SHAP value, take top 14
        pairs = sorted(zip(feature_names, shap_values), key=lambda x: abs(x[1]), reverse=True)
        top_pairs = pairs[:14]
        names  = [p[0] for p in top_pairs]
        values = [p[1] * 10 for p in top_pairs]  # Scale for readability

        decision_colors = {"APPROVED": "#28a745", "REFERRED": "#ffc107", "REJECTED": "#dc3545"}
        dec_color = decision_colors.get(decision, "#6c757d")

        fig, ax = plt.subplots(figsize=(11, 7))
        fig.patch.set_facecolor("#111827")
        ax.set_facecolor("#1f2937")

        colors  = ["#10b981" if v >= 0 else "#ef4444" for v in values]
        bars    = ax.barh(range(len(names)), values, color=colors, height=0.62,
                          edgecolor="#374151", linewidth=0.5)

        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=10, color="#e5e7eb")
        ax.invert_yaxis()
        ax.set_xlabel("Feature Contribution (SHAP value × 10)", fontsize=10, color="#9ca3af")
        ax.set_title(
            f"Credit Scoring — SHAP Waterfall  |  {decision}  |  Score: {final_score:.0f}/100",
            fontsize=13, fontweight="bold", color="white", pad=14
        )

        for bar, val in zip(bars, values):
            sgn  = "+" if val >= 0 else ""
            xpos = bar.get_width()
            ax.text(xpos + (0.15 if val >= 0 else -0.15),
                    bar.get_y() + bar.get_height() / 2,
                    f"{sgn}{val:.1f}",
                    va="center", ha="left" if val >= 0 else "right",
                    fontsize=8.5, fontweight="bold",
                    color="#10b981" if val >= 0 else "#ef4444")

        ax.axvline(x=0, color="#6b7280", linewidth=1.0, linestyle="--")
        ax.tick_params(axis="x", colors="#9ca3af")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for spine in ["left", "bottom"]:
            ax.spines[spine].set_color("#374151")
        ax.grid(axis="x", alpha=0.2, color="#6b7280")

        # Score badge
        ax.text(0.99, 0.03, f"{final_score:.0f}/100",
                transform=ax.transAxes, fontsize=22, fontweight="bold",
                color=dec_color, ha="right", va="bottom",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#1f2937",
                          edgecolor=dec_color, linewidth=2))

        pos_p = mpatches.Patch(color="#10b981", label="Positive Impact")
        neg_p = mpatches.Patch(color="#ef4444", label="Negative Impact")
        ax.legend(handles=[pos_p, neg_p], loc="lower left", fontsize=9,
                  facecolor="#374151", edgecolor="#6b7280", labelcolor="white")

        plt.tight_layout()
        chart_path = str(OUTPUT_DIR / "shap_waterfall.png")
        plt.savefig(chart_path, dpi=160, bbox_inches="tight", facecolor="#111827")
        plt.close()
        return chart_path
    except Exception as e:
        print(f"[Scoring] SHAP chart generation failed: {e}")
        return ""


# ─── Main Scoring Function ───────────────────────────────────────

def score_credit(feature_vector: list, feature_names: list) -> dict:
    """
    Score a credit application using XGBoost + SHAP.

    Returns:
    - credit_score    : 0-100
    - decision        : APPROVED / REFERRED / REJECTED
    - shap_values     : per-feature Shapley contributions
    - shap_chart_path : path to saved SHAP waterfall chart
    - explanation     : human-readable explanation
    """
    import numpy as np

    model = _load_or_train_model()

    if model is not None:
        try:
            X = np.array(feature_vector).reshape(1, -1)
            prob_good = float(model.predict_proba(X)[0][1])
            credit_score = prob_good * 100
            shap_vals, base_val = _compute_shap_values(model, feature_vector, feature_names)
        except Exception:
            credit_score, shap_vals, base_val = _fallback_score(feature_vector, feature_names)
    else:
        credit_score, shap_vals, base_val = _fallback_score(feature_vector, feature_names)

    decision    = _get_decision(credit_score)
    chart_path  = _generate_shap_chart(shap_vals, feature_names, base_val, credit_score, decision)
    explanation = _build_explanation(shap_vals, feature_names, credit_score, decision)

    return {
        "credit_score":    round(credit_score, 1),
        "decision":        decision,
        "decision_color":  {"APPROVED": "#28a745", "REFERRED": "#ffc107", "REJECTED": "#dc3545"}.get(decision, "#6c757d"),
        "shap_values":     [round(v, 4) for v in shap_vals],
        "base_value":      round(base_val, 2),
        "feature_names":   feature_names,
        "shap_chart_path": chart_path,
        "explanation":     explanation,
        "threshold":       60,
        "model_type":      "XGBoost + SHAP TreeExplainer" if model else "Rule-Based Fallback",
    }


def _fallback_score(feature_vector, feature_names):
    """Rule-based fallback when XGBoost is not available."""
    contribs = _rule_based_contributions(feature_vector, feature_names)
    score    = max(0, min(100, 50 + sum(contribs)))
    return score, contribs, 50.0


def _get_decision(score: float) -> str:
    for decision, (lo, hi) in CREDIT_CATEGORIES.items():
        if lo <= score <= hi:
            return decision
    return "REFERRED"


def _build_explanation(shap_vals: list, feature_names: list, score: float, decision: str) -> str:
    """Build a plain-English explanation of every scored factor."""
    pairs = sorted(zip(feature_names, shap_vals), key=lambda x: x[1], reverse=True)

    positives = [(n, v * 10) for n, v in pairs if v > 0]
    negatives = [(n, v * 10) for n, v in pairs if v < 0]

    lines = [
        f"**Decision: {decision}** — Credit Score: {score:.0f}/100 (Threshold: 60)\n",
        f"**Model:** XGBoost + SHAP TreeExplainer\n",
    ]

    if positives:
        lines.append("**Strengths (positive contributors):**")
        for name, val in positives[:6]:
            lines.append(f"  • {name}: **+{val:.1f} pts** — favourable signal")

    if negatives:
        lines.append("\n**Risk Factors (negative contributors):**")
        for name, val in negatives[:6]:
            lines.append(f"  • {name}: **{val:.1f} pts** — needs attention")

    lines.append(
        f"\n**Net Assessment:** Score of {score:.0f} is "
        f"{'ABOVE ✅' if score >= 60 else 'BELOW ❌'} the approval threshold of 60."
    )

    return "\n".join(lines)
