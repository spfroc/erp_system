from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import business_license, invoice, trademark
from app.services.business_license_parser import _ocr_engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        import numpy as np
        from PIL import Image, ImageDraw

        engine = _ocr_engine()
        warmup = Image.new("RGB", (640, 320), "white")
        draw = ImageDraw.Draw(warmup)
        draw.text((40, 60), "BUSINESS LICENSE", fill="black")
        draw.text((40, 150), "91370200 TEST COMPANY", fill="black")
        engine(np.asarray(warmup))
    except Exception as error:
        # Local Python may lack rapidocr-onnxruntime; PDF text-layer OCR still works.
        print(f"OCR engine warmup skipped: {error}")
    yield


app = FastAPI(title="Yicai ERP OCR Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(business_license.router, prefix="/api/ocr/business-license", tags=["ocr"])
app.include_router(invoice.router, prefix="/api/ocr/invoice", tags=["ocr"])
app.include_router(trademark.router, prefix="/api/ocr/trademark", tags=["ocr"])


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "ocr-service"}
