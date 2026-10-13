from fastapi import APIRouter, UploadFile

from app.services.trademark_parser import parse_trademark_certificate

router = APIRouter()


@router.post("")
async def recognize_trademark_certificate(file: UploadFile):
    content = await file.read()
    if not content:
        return {"status": "ocr_error", "message": "上传文件为空。", "data": None}
    result = parse_trademark_certificate(content, file.filename or "", file.content_type)
    return {"filename": file.filename, **result}
