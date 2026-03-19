"""
OCR & PDF Parsing Engine for Intelli-Credit.
Extraction priority:
  1. Azure Document Intelligence (Primary — best for Indian scanned PDFs)
  2. pdfplumber (Digital PDFs with layout preservation)
  3. pytesseract + pdf2image (Fallback OCR for scanned PDFs)
"""
import io
from pathlib import Path


def extract_text_from_pdf(pdf_path: str | Path = None, pdf_bytes: bytes = None, max_pages: int = 20) -> dict:
    """
    Extract text from a PDF file using the best available engine.
    Returns: {pages: [{page_num, text, tables}], full_text, num_pages, method}
    """
    if pdf_bytes:
        return _extract_best(pdf_bytes=pdf_bytes, max_pages=max_pages)
    elif pdf_path:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        return _extract_best(pdf_bytes=pdf_bytes, pdf_path=str(pdf_path), max_pages=max_pages)
    else:
        return {"pages": [], "full_text": "", "num_pages": 0, "method": "none", "error": "No input provided"}


def _extract_best(pdf_bytes: bytes, pdf_path: str = None, max_pages: int = 20) -> dict:
    """Try extraction engines in priority order."""
    from config import has_azure_di

    # 1. Try Azure Document Intelligence first
    if has_azure_di():
        result = _extract_with_azure_di(pdf_bytes, max_pages=max_pages)
        if result.get("method") != "error":
            return result

    # 2. Try pdfplumber
    result = _extract_with_pdfplumber(pdf_bytes=pdf_bytes, max_pages=max_pages)
    if result.get("method") != "error" and len(result.get("full_text", "").strip()) > 50:
        return result

    # 3. Fallback to Tesseract OCR
    return _extract_with_ocr(pdf_bytes=pdf_bytes, max_pages=max_pages)


def _extract_with_azure_di(pdf_bytes: bytes, max_pages: int = 20) -> dict:
    """
    Extract text using Azure Document Intelligence (AI Document Intelligence).
    Handles scanned PDFs, mixed-language (Hindi/English), and complex table layouts.
    """
    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential
        from config import AZURE_DI_ENDPOINT, AZURE_DI_KEY

        client = DocumentIntelligenceClient(
            endpoint=AZURE_DI_ENDPOINT,
            credential=AzureKeyCredential(AZURE_DI_KEY),
        )

        # Use prebuilt-layout model for general document understanding
        poller = client.begin_analyze_document(
            "prebuilt-layout",
            body=pdf_bytes,
            content_type="application/pdf",
        )
        result = poller.result()

        pages = []
        full_text_parts = []

        # Limit page iteration
        result_pages = result.pages[:max_pages] if len(result.pages) > max_pages else result.pages

        for page in result_pages:
            page_text = ""
            for line in page.lines:
                page_text += line.content + "\n"

            tables = []
            # Extract tables for this page
            for table in (result.tables or []):
                if any(cell.bounding_regions and cell.bounding_regions[0].page_number == page.page_number
                       for cell in table.cells):
                    table_data = []
                    current_row = []
                    current_row_idx = 0
                    for cell in sorted(table.cells, key=lambda c: (c.row_index, c.column_index)):
                        if cell.row_index != current_row_idx:
                            if current_row:
                                table_data.append(current_row)
                            current_row = []
                            current_row_idx = cell.row_index
                        current_row.append(cell.content)
                    if current_row:
                        table_data.append(current_row)
                    tables.append(table_data)

            pages.append({
                "page_num": page.page_number,
                "text": page_text,
                "tables": tables,
                "confidence": getattr(page, 'confidence', None),
            })
            full_text_parts.append(page_text)

        return {
            "pages": pages,
            "full_text": "\n\n".join(full_text_parts),
            "num_pages": len(pages),
            "method": "azure_document_intelligence",
            "model": "prebuilt-layout",
        }

    except ImportError:
        return {"pages": [], "full_text": "", "num_pages": 0, "method": "error",
                "error": "azure-ai-documentintelligence not installed. Run: pip install azure-ai-documentintelligence"}
    except Exception as e:
        return {"pages": [], "full_text": "", "num_pages": 0, "method": "error",
                "error": f"Azure DI failed: {str(e)}"}


def _extract_with_pdfplumber(pdf_path: str = None, pdf_bytes: bytes = None, max_pages: int = 20) -> dict:
    """Extract text using pdfplumber (best for digital PDFs)."""
    try:
        import pdfplumber

        pages = []
        full_text_parts = []

        open_args = {"path_or_fp": pdf_path} if pdf_path else {"path_or_fp": io.BytesIO(pdf_bytes)}

        with pdfplumber.open(**open_args) as pdf:
            pdf_pages = pdf.pages[:max_pages] if len(pdf.pages) > max_pages else pdf.pages
            for i, page in enumerate(pdf_pages):
                page_text = page.extract_text() or ""
                tables = []

                try:
                    raw_tables = page.extract_tables()
                    for table in raw_tables:
                        if table:
                            tables.append(table)
                except Exception:
                    pass

                pages.append({
                    "page_num": i + 1,
                    "text": page_text,
                    "tables": tables,
                })
                full_text_parts.append(page_text)

            full_text = "\n\n".join(full_text_parts)
            if len(full_text.strip()) < 50 and len(pdf.pages) > 0:
                return {"pages": [], "full_text": "", "num_pages": 0, "method": "error",
                        "error": "pdfplumber extracted minimal text — likely scanned PDF"}

            return {
                "pages": pages,
                "full_text": full_text,
                "num_pages": len(pages),
                "method": "pdfplumber",
            }

    except ImportError:
        return {"pages": [], "full_text": "", "num_pages": 0, "method": "error",
                "error": "pdfplumber not installed"}
    except Exception as e:
        return {"pages": [], "full_text": "", "num_pages": 0, "method": "error",
                "error": str(e)}


def _extract_with_ocr(pdf_path: str = None, pdf_bytes: bytes = None, max_pages: int = 20) -> dict:
    """Extract text using pytesseract OCR (fallback for scanned PDFs)."""
    try:
        import pytesseract
        from pdf2image import convert_from_path, convert_from_bytes
        from config import TESSERACT_PATH

        if TESSERACT_PATH:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

        if pdf_path:
            images = convert_from_path(pdf_path, dpi=300, first_page=1, last_page=max_pages)
        elif pdf_bytes:
            images = convert_from_bytes(pdf_bytes, dpi=300, first_page=1, last_page=max_pages)
        else:
            return {"pages": [], "full_text": "", "num_pages": 0, "method": "error",
                    "error": "No input for OCR"}

        pages = []
        full_text_parts = []

        for i, img in enumerate(images):
            # Use eng+hin for handling Devanagari headers in Indian docs
            text = pytesseract.image_to_string(img, lang="eng")
            pages.append({
                "page_num": i + 1,
                "text": text,
                "tables": [],
            })
            full_text_parts.append(text)

        return {
            "pages": pages,
            "full_text": "\n\n".join(full_text_parts),
            "num_pages": len(pages),
            "method": "tesseract_ocr",
        }

    except ImportError:
        return {"pages": [], "full_text": "", "num_pages": 0, "method": "error",
                "error": "pytesseract or pdf2image not installed. Install Tesseract OCR for scanned PDF support."}
    except Exception as e:
        return {"pages": [], "full_text": "", "num_pages": 0, "method": "error",
                "error": f"OCR failed: {str(e)}"}


def extract_text_from_uploaded_file(uploaded_file) -> dict:
    """Extract text from a Streamlit UploadedFile object."""
    pdf_bytes = uploaded_file.read()
    uploaded_file.seek(0)
    result = extract_text_from_pdf(pdf_bytes=pdf_bytes)
    result["filename"] = uploaded_file.name
    return result
