from fastapi import APIRouter, HTTPException, UploadFile

from app.services.invoice_parser import parse_invoice_pdf_bytes

router = APIRouter()


@router.post("")
async def recognize_invoice(file: UploadFile):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF invoice recognition is implemented.")
    result = parse_invoice_pdf_bytes(content)
    return {
        "filename": file.filename,
        **result,
    }
