from fastapi import APIRouter, HTTPException, UploadFile

from app.services.business_license_parser import parse_business_license

router = APIRouter()


@router.post("")
async def recognize_business_license(file: UploadFile):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")
    result = parse_business_license(content, file.filename or "", file.content_type)
    return {
        "filename": file.filename,
        **result,
    }
