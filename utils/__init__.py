"""
Utility helpers for Intelli-Credit.
"""
import json
import os
from pathlib import Path
from datetime import datetime


def load_json(path: str | Path) -> dict:
    """Load a JSON file and return as dict."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict, path: str | Path):
    """Save a dict as formatted JSON."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def timestamp() -> str:
    """Return current ISO timestamp."""
    return datetime.now().isoformat()


def safe_divide(a: float, b: float, default: float = 0.0) -> float:
    """Safe division with default."""
    return a / b if b != 0 else default


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp a value between lo and hi."""
    return max(lo, min(hi, value))


def format_inr(value_cr: float) -> str:
    """Format a value in crores to Indian currency string."""
    if value_cr >= 1:
        return f"₹ {value_cr:.2f} Cr"
    else:
        lakhs = value_cr * 100
        return f"₹ {lakhs:.2f} Lakh"


def compute_cagr(start: float, end: float, years: int) -> float:
    """Compute Compound Annual Growth Rate."""
    if start <= 0 or years <= 0:
        return 0.0
    return ((end / start) ** (1.0 / years) - 1) * 100
