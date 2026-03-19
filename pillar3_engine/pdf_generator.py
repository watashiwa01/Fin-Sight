from fpdf import FPDF
import os
from datetime import datetime
from config import OUTPUT_DIR

class CAM_PDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 15)
        self.cell(0, 10, 'CREDIT APPRAISAL MEMORANDUM', border=False, ln=1, align='C')
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 5, 'Confidential | Powered by Intelli-Credit AI Engine', border=False, ln=1, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()} | Generated on {datetime.now().strftime("%d-%b-%Y %H:%M")}', align='C')

def generate_pdf_cam(company_data, five_cs, scoring, research, swot_analysis, committee_verdict, charts):
    pdf = CAM_PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Executive Summary
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(59, 130, 246)
    pdf.cell(0, 10, f"1. Executive Summary: {company_data.get('company_name', 'N/A') if company_data else 'N/A'}", ln=1)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('helvetica', '', 10)
    
    scoring = scoring or {}
    decision = scoring.get("decision", "REFER")
    pdf.cell(0, 8, f"Final Verdict: {decision}", ln=1)
    pdf.cell(0, 8, f"Credit Score: {float(scoring.get('credit_score', 0)):.0f}/100", ln=1)
    
    loan = company_data.get("loan_request", {}) if company_data else {}
    loan_text = f"Loan Request: INR {loan.get('amount_cr', 0)} Cr ({loan.get('type', 'Term Loan')}) for {loan.get('purpose', 'N/A')}"
    pdf.multi_cell(0, 8, loan_text.encode('latin-1', 'replace').decode('latin-1'))
    pdf.ln(5)
    
    # Financial Trends Image
    if charts and 'trends' in charts and os.path.exists(charts['trends']):
        pdf.image(charts['trends'], x=10, w=190)
        pdf.ln(5)

    # 5 Cs Analysis
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(59, 130, 246)
    pdf.cell(0, 10, "2. Five Cs Pillar Analysis", ln=1)
    pdf.set_text_color(0, 0, 0)
    
    if charts and 'radar' in charts and os.path.exists(charts['radar']):
        pdf.image(charts['radar'], x=50, w=110)
        pdf.ln(5)
        
    # SWOT Analysis
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(59, 130, 246)
    pdf.cell(0, 10, "3. Integrated SWOT Analysis", ln=1)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('helvetica', '', 10)
    swot_safe = (swot_analysis if swot_analysis else "No SWOT analysis available.").encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 6, swot_safe)
    pdf.ln(5)
    
    # Committee Rationale
    if committee_verdict:
        pdf.set_font('helvetica', 'B', 14)
        pdf.set_text_color(59, 130, 246)
        pdf.cell(0, 10, "4. AI Committee Rationale", ln=1)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('helvetica', '', 10)
        rationale_safe = committee_verdict.get("rationale", "N/A").encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 6, rationale_safe)

    # Save
    filename = f"CAM_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    path = OUTPUT_DIR / filename
    pdf.output(str(path))
    return str(path)
