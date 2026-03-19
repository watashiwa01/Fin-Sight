"""
Intelli-Credit Configuration Manager
Handles environment variables, mode detection, and path constants.
"""
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# --- Paths ---
BASE_DIR = Path(__file__).parent
SAMPLE_DATA_DIR = BASE_DIR / "sample_data"


def _pick_runtime_dir() -> Path:
    """
    Pick a writable runtime directory for generated artifacts and caches.

    Serverless platforms (e.g. Vercel) often mount the project directory as read-only.
    In that case we fall back to a temp directory.
    """
    override = os.getenv("FIN_SIGHT_RUNTIME_DIR") or os.getenv("RUNTIME_DIR") or ""

    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))

    candidates.extend([
        BASE_DIR,
        Path(tempfile.gettempdir()) / "fin-sight",
    ])

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_path = candidate / ".write_test"
            test_path.write_text("ok", encoding="utf-8")
            test_path.unlink(missing_ok=True)
            return candidate
        except Exception:
            continue

    fallback = Path(tempfile.gettempdir()) / "fin-sight"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


RUNTIME_DIR = _pick_runtime_dir()
OUTPUT_DIR = RUNTIME_DIR / "output"
DB_DIR = RUNTIME_DIR / "data"
CHROMA_DIR = DB_DIR / "chromadb"
TEMP_UPLOAD_DIR = RUNTIME_DIR / "temp_uploads"
SQLITE_PATH = DB_DIR / "intelli_credit.db"

# Ensure writable directories exist
for d in [OUTPUT_DIR, DB_DIR, CHROMA_DIR, TEMP_UPLOAD_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# --- App Mode ---
APP_MODE = os.getenv("APP_MODE", "live").lower()  # "demo" or "live"
IS_DEMO = APP_MODE == "demo"

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TESSERACT_PATH = os.getenv("TESSERACT_PATH", "")

# --- Object Storage (S3 / Cloudflare R2 / etc.) ---
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_PREFIX = os.getenv("S3_PREFIX", "uploads")
S3_REGION = os.getenv("S3_REGION", "auto")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
S3_ADDRESSING_STYLE = os.getenv("S3_ADDRESSING_STYLE", "auto")  # auto|virtual|path
S3_UPLOAD_MAX_MB = float(os.getenv("S3_UPLOAD_MAX_MB", "50"))
S3_DELETE_AFTER_PROCESS = os.getenv("S3_DELETE_AFTER_PROCESS", "false").strip().lower() in {"1", "true", "yes"}

# --- Azure Document Intelligence ---
AZURE_DI_ENDPOINT = os.getenv("AZURE_DI_ENDPOINT", "")
AZURE_DI_KEY = os.getenv("AZURE_DI_KEY", "")

# --- Databricks ---
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")
DATABRICKS_WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "")
DATABRICKS_CATALOG = os.getenv("DATABRICKS_CATALOG", "intelli_credit")
DATABRICKS_SCHEMA = os.getenv("DATABRICKS_SCHEMA", "credit_engine")

# --- LLM Config ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()  # "openai" or "anthropic"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o" if LLM_PROVIDER == "openai" else "claude-sonnet-4-20250514")
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 4096

# --- Credit Scoring Config ---
CREDIT_SCORE_THRESHOLD = 60  # Out of 100
CREDIT_CATEGORIES = {
    "APPROVED": (70, 100),
    "REFERRED": (50, 69),
    "REJECTED": (0, 49),
}

# --- Document Types ---
DOC_TYPES = [
    "annual_report",
    "bank_statement",
    "gst_return",
    "legal_notice",
    "sanction_letter",
    "balance_sheet",
    "profit_loss",
    "other",
]

# --- 5 Cs Framework Weights ---
FIVE_CS_WEIGHTS = {
    "character": 0.20,
    "capacity": 0.25,
    "capital": 0.20,
    "collateral": 0.20,
    "conditions": 0.15,
}


def has_openai_key() -> bool:
    return bool(OPENAI_API_KEY) and OPENAI_API_KEY != "your_openai_api_key_here"


def has_anthropic_key() -> bool:
    return bool(ANTHROPIC_API_KEY) and ANTHROPIC_API_KEY != "your_anthropic_api_key_here"


def has_openrouter_key() -> bool:
    return bool(OPENROUTER_API_KEY) and OPENROUTER_API_KEY != "your_openrouter_api_key_here"

def has_s3_storage() -> bool:
    """
    Check if S3-compatible object storage is configured.

    Requires bucket + access keys. Endpoint is optional (AWS default if omitted).
    """
    access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    return bool(S3_BUCKET) and bool(access_key) and bool(secret_key)


def has_llm_key() -> bool:
    """Check if any LLM provider key is available."""
    return has_openai_key() or has_anthropic_key() or has_openrouter_key()


def has_tavily_key() -> bool:
    return bool(TAVILY_API_KEY) and TAVILY_API_KEY != "your_tavily_api_key_here"


def has_azure_di() -> bool:
    return bool(AZURE_DI_ENDPOINT) and bool(AZURE_DI_KEY)


def has_databricks() -> bool:
    return bool(DATABRICKS_HOST) and bool(DATABRICKS_TOKEN)


def get_llm_client():
    """Get the configured LLM client (OpenRouter, OpenAI or Anthropic).
    OpenRouter is the highest priority since we have that key configured.
    """
    if has_openrouter_key() or LLM_PROVIDER == "openrouter":
        return _get_openrouter_client()
    elif LLM_PROVIDER == "anthropic" and has_anthropic_key():
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=LLM_MODEL, temperature=LLM_TEMPERATURE, api_key=ANTHROPIC_API_KEY)
    elif has_openai_key():
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE, api_key=OPENAI_API_KEY)
    return None


# Free models available on OpenRouter (fallback chain)
OPENROUTER_FREE_MODELS = [
    "openrouter/auto",
    "google/gemma-3-27b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-r1:free",
    "qwen/qwen-2.5-72b-instruct:free",
]


def _get_openrouter_client(model_index: int = 0):
    """Create an OpenRouter ChatOpenAI client with the given model index."""
    from langchain_openai import ChatOpenAI
    model_name = os.getenv("OPENROUTER_MODEL", "") or OPENROUTER_FREE_MODELS[model_index % len(OPENROUTER_FREE_MODELS)]
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        model=model_name,
        temperature=LLM_TEMPERATURE,
        max_tokens=3000,
        default_headers={
            "HTTP-Referer": "https://intellicredit.ai",
            "X-Title": "Intelli-Credit AI Engine",
        }
    )


def get_mode_display() -> str:
    if IS_DEMO:
        return "🟡 Demo Mode (Mock Data)"
    parts = []
    if has_llm_key():
        if has_openrouter_key():
            parts.append("LLM: OpenRouter")
        else:
            parts.append(f"LLM: {LLM_PROVIDER.title()}")
    if has_tavily_key():
        parts.append("Web Search")
    if has_azure_di():
        parts.append("Azure DI")
    if has_databricks():
        parts.append("Databricks")
    if parts:
        return f"🟢 Live Mode ({', '.join(parts)})"
    else:
        return "🔴 Live Mode Configured but Missing API Keys"
