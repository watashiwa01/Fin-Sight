# Fin-Sight (DrishtiCredit)

AI-powered credit appraisal engine with a FastAPI backend serving a simple static frontend.

## Run locally

1. Install deps:
   - `python -m pip install -r requirements.txt`
   - full local stack: `python -m pip install -r requirements-full.txt`
2. Configure env (optional but recommended):
   - copy `.env.example` -> `.env`
   - set keys like `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `TAVILY_API_KEY` / `AZURE_DI_ENDPOINT` / `AZURE_DI_KEY`
3. Start the app:
   - `python api.py`
   - or PowerShell: `./scripts/run.ps1`
   - or bash: `./scripts/run.sh`
   - optional: `PORT` env var (default `8140`)
4. Open:
   - UI: `http://127.0.0.1:8140`
   - API docs: `http://127.0.0.1:8140/docs`
   - Health check: `http://127.0.0.1:8140/health`

## Deploy on Render

This avoids Vercel's ~4.5MB serverless upload limit (so PDF uploads can work without S3/R2).

1. Go to Render → **New** → **Blueprint** and connect this GitHub repo.
2. Render should detect `render.yaml` automatically. Create the service.
3. After deploy, open:
   - UI: `https://<your-render-domain>/`
   - Health: `https://<your-render-domain>/health`

## Notes

- PDF generation uses `fpdf2`. If it isn't installed, the API still starts and `/api/generate-report` returns `pdf_path: null`.

## Large uploads (Vercel)

Vercel serverless functions reject request bodies larger than ~4.5MB. To support bigger PDFs on the hosted demo, Fin‑Sight can upload directly to S3-compatible object storage (AWS S3 / Cloudflare R2) using a presigned POST, then the backend processes the file from storage.

### Enable S3/R2 uploads

1. Create a bucket (AWS S3 or Cloudflare R2).
2. Set these environment variables (see `.env.example`):
   - `S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
   - optional: `S3_ENDPOINT_URL` (needed for R2), `S3_REGION` (R2 uses `auto`)
   - optional: `S3_UPLOAD_MAX_MB`, `S3_PREFIX`, `S3_DELETE_AFTER_PROCESS`
3. Configure bucket CORS to allow browser uploads from your deployed origin:
   - Methods: `POST`, `GET`, `HEAD`
   - Headers: `*`
   - Origins: your Vercel domain (and custom domain if any)
4. Redeploy.
