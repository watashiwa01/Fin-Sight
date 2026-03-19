# Fin-Sight (DrishtiCredit)

AI-powered credit appraisal engine with a FastAPI backend serving a simple static frontend.

## Run locally

1. Install deps:
   - `python -m pip install -r requirements.txt`
2. Configure env (optional but recommended):
   - copy `.env.example` → `.env`
   - set keys like `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `TAVILY_API_KEY` / `AZURE_DI_ENDPOINT` / `AZURE_DI_KEY`
3. Start the app:
   - `python api.py`
4. Open:
   - UI: `http://127.0.0.1:8140`
   - API docs: `http://127.0.0.1:8140/docs`
   - Health check: `http://127.0.0.1:8140/health`

## Notes

- PDF generation uses `fpdf2`. If it isn't installed, the API still starts and `/api/generate-report` returns `pdf_path: null`.
