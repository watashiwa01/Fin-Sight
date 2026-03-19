from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import json
import time
import asyncio
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    IS_DEMO, SAMPLE_DATA_DIR, OUTPUT_DIR, get_mode_display
)
from utils import load_json, format_inr
from pillar1_ingestor.ocr_engine import extract_text_from_uploaded_file
from pillar1_ingestor.document_classifier import classify_document
from pillar1_ingestor.llm_extractor import extract_sync
from pillar1_ingestor.gst_validator import validate_gst_compliance
from pillar2_research.agent_orchestrator import run_research_pipeline
from pillar3_engine.feature_builder import build_features
from pillar3_engine.scoring_model import score_credit
from pillar3_engine.committee_agent import CommitteeAgent
from pillar3_engine.swot_generator import generate_swot_sync
from pillar3_engine.cam_generator import generate_cam

app = FastAPI(title="Intelli-Credit API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory "session" state
session_state = {
    "company_data": None,
    "extracted_data": {},
    "doc_classifications": [],
    "research_results": None,
    "five_cs": None,
    "scoring": None,
    "gst_validation": None,
    "committee_verdict": None,
    "cam_path": None,
    "pipeline_step": 0,
    "qualitative_notes": [],
    "swot_analysis": None,
}

class OnboardingData(BaseModel):
    company_name: str
    cin: str
    pan: Optional[str] = ""
    industry: str
    turnover_cr: float
    loan_type: str
    amount_cr: float
    tenor_years: float
    proposed_rate_pct: float

class ExtractionRequest(BaseModel):
    filename: str
    doc_type: str
    schema_: str = Field(alias="schema")
    full_text: str

class ResearchRequest(BaseModel):
    company_name: str

@app.get("/api/config")
async def get_config():
    from config import get_mode_display, IS_DEMO, has_llm_key, has_tavily_key
    return {
        "mode_display": get_mode_display(),
        "is_demo": IS_DEMO,
        "has_llm": has_llm_key(),
        "has_search": has_tavily_key()
    }

@app.post("/api/onboarding")
async def onboarding(data: OnboardingData):
    session_state["company_data"] = {
        "company_name": data.company_name,
        "cin": data.cin,
        "pan": data.pan,
        "industry": data.industry,
        "turnover_cr": data.turnover_cr,
        "loan_request": {
            "type": data.loan_type,
            "amount_cr": data.amount_cr,
            "tenor_years": data.tenor_years,
            "proposed_rate_pct": data.proposed_rate_pct
        }
    }
    session_state["pipeline_step"] = max(session_state["pipeline_step"], 1)
    session_state["research_results"] = None
    session_state["scoring"] = None
    session_state["five_cs"] = None
    session_state["committee_verdict"] = None
    return {"status": "success", "session": session_state}

@app.post("/api/load-sample")
async def load_sample():
    # Allow always for this migration demo
    sample = load_json(SAMPLE_DATA_DIR / "sample_company.json")
    # Add a mock PAN if missing
    if "pan" not in sample:
        sample["pan"] = "ABCDE1234F"
    session_state["company_data"] = sample
    session_state["pipeline_step"] = 1
    session_state["research_results"] = None
    session_state["scoring"] = None
    session_state["five_cs"] = None
    session_state["committee_verdict"] = None
    return {"status": "success", "company_data": sample}

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    # Save file temporarily
    temp_dir = Path("temp_uploads")
    temp_dir.mkdir(exist_ok=True)
    file_path = temp_dir / file.filename
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Text extraction & Classification
    with open(file_path, "rb") as f:
        class MockFile:
            def __init__(self, path, name):
                self.path = path
                self.name = name
                self.size = os.path.getsize(path)
            def read(self):
                with open(self.path, "rb") as f:
                    return f.read()
            def seek(self, offset, whence=0):
                pass
                    
        mock_file = MockFile(file_path, file.filename)
        
        try:
            # We wrap the result to handle large files
            result = extract_text_from_uploaded_file(mock_file)
            
            # Optimization for huge documents (Annual Reports)
            if result.get("num_pages", 0) > 20:
                result["pages"] = result["pages"][:20]
                result["full_text"] = "\n\n".join([p["text"] for p in result["pages"]])
                result["num_pages"] = 20
                result["note"] = "Processing limited to first 20 pages for speed."

            classification = classify_document(file.filename, result["full_text"])
            
            # Persist to session state
            session_state["doc_classifications"].append({
                "filename": file.filename,
                "type": classification,
                "pages": result["num_pages"]
            })
            
            # If we don't have company data yet, try to infer it?
            # (No, onboarding should have done it, but let's be safe)
            
            session_state["pipeline_step"] = max(session_state["pipeline_step"], 1)

            return {
                "filename": file.filename,
                "result": result,
                "classification": classification,
                "step": 1,
                "session": session_state
            }
        except Exception as e:
            print(f"Extraction error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/extract")
async def run_extraction(req: ExtractionRequest):
    extracted = extract_sync(req.full_text, req.doc_type, custom_schema=req.schema_)
    # Add metadata for the validator
    extracted["_doc_type"] = req.doc_type
    
    session_state["extracted_data"][req.filename] = extracted
    
    # Merge into company_data if relevant
    if not session_state["company_data"]:
        session_state["company_data"] = {}
    
    cd = session_state["company_data"]
    
    if req.doc_type == "annual_report":
        if "financials" not in cd: cd["financials"] = {}
        # Map FY 2024 (latest)
        fy_data = {
            "revenue_cr": _soft_get(extracted, "revenue_cr"),
            "ebitda_cr": _soft_get(extracted, "ebitda_cr"),
            "ebitda_margin_pct": extracted.get("ebitda_margin_pct"),
            "pat_cr": _soft_get(extracted, "pat_cr"),
            "total_debt_cr": _soft_get(extracted, "total_debt_cr"),
            "net_worth_cr": _soft_get(extracted, "net_worth_cr"),
            "current_ratio": extracted.get("current_ratio"),
            "de_ratio": extracted.get("de_ratio")
        }
        cd["financials"]["fy_2024"] = fy_data
        cd["financials"]["latest"] = fy_data
        if not cd.get("company_name"): cd["company_name"] = _soft_get(extracted, "company_name")
        if not cd.get("cin"): cd["cin"] = _soft_get(extracted, "cin")
        
    elif req.doc_type == "gst_return":
        if "gst_data" not in cd: cd["gst_data"] = {}
        cd["gst_data"]["gstin"] = _soft_get(extracted, "gstin")
        cd["gst_data"]["taxable_turnover"] = _soft_get(extracted, "taxable_turnover")

    # Ensure classification is recorded if not already
    found = False
    for d in session_state["doc_classifications"]:
        if d["filename"] == req.filename:
            d["type"] = req.doc_type
            found = True
    if not found:
        session_state["doc_classifications"].append({"filename": req.filename, "type": req.doc_type})
        
    return {"status": "success", "extracted": extracted}

def _soft_get(extracted, key):
    val = extracted.get(key)
    if isinstance(val, dict) and "value" in val:
        return val["value"]
    return val

@app.post("/api/gst-validation")
async def gst_validation():
    gst_result = validate_gst_compliance(
        extracted_data=session_state["extracted_data"],
        company_data=session_state["company_data"]
    )
    session_state["gst_validation"] = gst_result
    session_state["pipeline_step"] = max(session_state["pipeline_step"], 2)
    return gst_result

@app.post("/api/research")
async def start_research(req: ResearchRequest):
    company_name = req.company_name
    
    # Reset state if new company is requested to prevent data leakage
    if session_state["company_data"] and session_state["company_data"].get("company_name") != company_name:
        print(f"Company changed to {company_name}. Resetting session state.")
        session_state["research_results"] = None
        session_state["scoring"] = None
        session_state["five_cs"] = None
        session_state["committee_verdict"] = None
        session_state["company_data"] = {"company_name": company_name}

    cd = session_state["company_data"] or {"company_name": company_name}
    promoters = [p["name"] for p in cd.get("promoters", [])]
    cin = cd.get("cin", "")
    industry = cd.get("industry", "")
    
    # For progress callback in API, we might need a websocket or SSE.
    # For simplicity here, we run it synchronously (or use a background task).
    def progress_callback(agent_name, status):
        print(f"Agent: {agent_name}, Status: {status}")

    research = run_research_pipeline(
        company_name=company_name,
        cin=cin,
        industry=industry,
        promoter_names=promoters,
        qualitative_notes=session_state["qualitative_notes"],
        progress_callback=progress_callback,
    )

    session_state["research_results"] = research
    session_state["pipeline_step"] = max(session_state["pipeline_step"], 3)

    # Automatically Merge found Net Worth/Revenue into company_data
    if research.get("financials") and not research.get("financials").get("error"):
        fin_data = research["financials"]
        if not session_state["company_data"]:
            session_state["company_data"] = {}
        
        cd = session_state["company_data"]
        # Ensure company name is set for side panel
        if not cd.get("company_name"):
            cd["company_name"] = research.get("company_name", company_name.title())

        if "financials" not in cd: cd["financials"] = {}
        if "fy_2024" not in cd["financials"]: cd["financials"]["fy_2024"] = {}
        
        fy24 = cd["financials"]["fy_2024"]
        
        # Only overwrite if currently 0 or missing
        for field in ["net_worth_cr", "revenue_cr", "dscr", "icr", "revenue_cagr_3yr", 
                      "ebitda_margin_pct", "current_ratio", "de_ratio", 
                      "tangible_net_worth_cr", "promoter_equity_pct"]:
            if not fy24.get(field) or fy24.get(field) == 0:
                fy24[field] = fin_data.get(field, 0)

        # Update Market Cap (always keep latest from search)
        fy24["market_cap_cr"] = fin_data.get("market_cap_cr", 0)
        
        session_state["company_data"] = cd

    return {
        "research": research,
        "company_data": session_state["company_data"]
    }

@app.post("/api/score")
async def run_scoring():
    if not session_state["research_results"]:
        raise HTTPException(status_code=400, detail="Run research first")
    
    cd = session_state["company_data"] or {}
    five_cs = build_features(
        financials=cd.get("financials", {}),
        research=session_state["research_results"],
        gst_validation=session_state["gst_validation"],
        collateral=cd.get("collateral", {}),
        qualitative_notes=session_state["qualitative_notes"],
    )

    scoring = score_credit(
        five_cs["feature_vector"],
        five_cs["feature_names"],
    )

    session_state["five_cs"] = five_cs
    session_state["scoring"] = scoring

    # AI Committee
    committee = CommitteeAgent()
    verdict = await committee.deliberate(
        company_data=cd,
        financials=cd.get("financials", {}),
        research=session_state["research_results"],
        gst_validation=session_state["gst_validation"],
        scoring=scoring
    )
    session_state["committee_verdict"] = verdict
    session_state["pipeline_step"] = max(session_state["pipeline_step"], 4)
    
    return {
        "scoring": scoring,
        "five_cs": five_cs,
        "verdict": verdict
    }

from fastapi.responses import FileResponse

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join("output", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Dynamic MIME type based on extension
    ext = filename.split(".")[-1].lower()
    mime_type = "application/octet-stream"
    if ext in ["png", "jpg", "jpeg"]:
        mime_type = "image/png"
    elif ext in ["pdf"]:
        mime_type = "application/pdf"
    elif ext in ["docx"]:
        mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        
    return FileResponse(
        file_path, 
        media_type=mime_type,
        filename=filename
    )

from utils.report_utils import generate_report_charts
try:
    from pillar3_engine.pdf_generator import generate_pdf_cam
except ModuleNotFoundError as e:
    if e.name == "fpdf":
        generate_pdf_cam = None
    else:
        raise

@app.get("/api/download-pdf/{filename}")
async def download_pdf(filename: str):
    file_path = os.path.join("output", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        file_path, 
        media_type='application/pdf',
        filename=filename
    )

@app.post("/api/generate-report")
async def generate_report():
    try:
        cd = session_state["company_data"] or {}
        
        # 1. Generate Charts
        charts = generate_report_charts()
        
        # 2. Generate SWOT
        swot_text = generate_swot_sync(
            company_data=cd,
            five_cs=session_state["five_cs"],
            scoring=session_state["scoring"],
            research=session_state["research_results"] or {}
        )
        session_state["swot_analysis"] = swot_text
        
        # 3. Generate DOCX
        cam_path = generate_cam(
            company_data=cd,
            five_cs=session_state["five_cs"],
            scoring=session_state["scoring"],
            research=session_state["research_results"] or {},
            gst_validation=session_state["gst_validation"],
            qualitative_notes=session_state["qualitative_notes"],
            swot_analysis=swot_text,
            committee_verdict=session_state["committee_verdict"],
            charts=charts
        )
        
        # 4. Generate PDF (optional dependency: fpdf)
        pdf_path = None
        if generate_pdf_cam is not None:
            pdf_path = generate_pdf_cam(
                company_data=cd,
                five_cs=session_state["five_cs"],
                scoring=session_state["scoring"],
                research=session_state["research_results"] or {},
                swot_analysis=swot_text,
                committee_verdict=session_state["committee_verdict"],
                charts=charts
            )

        rel_cam_path = f"output/{os.path.basename(cam_path)}"
        rel_pdf_path = f"output/{os.path.basename(pdf_path)}" if pdf_path else None
        
        session_state["cam_path"] = rel_cam_path
        session_state["pdf_path"] = rel_pdf_path
        session_state["pipeline_step"] = 5
        
        return {
            "status": "success", 
            "cam_path": rel_cam_path, 
            "pdf_path": rel_pdf_path,
            "swot": swot_text
        }
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        with open("error_log.txt", "w") as f:
            f.write(err_msg)
        print(f"REPORT ERROR: {err_msg}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/notes")
async def add_note(note: str = Form(...)):
    session_state["qualitative_notes"].append(note)
    return {"status": "success", "notes": session_state["qualitative_notes"]}

@app.get("/api/state")
async def get_state():
    return session_state


@app.get("/health")
async def health():
    return {"status": "ok"}

# Serve static files (Frontend)
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8140)
