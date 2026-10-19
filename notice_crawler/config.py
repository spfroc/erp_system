from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    db_url: str = os.getenv(
        "NOTICE_DB_URL",
        "mysql+pymysql://root:yicai-root@127.0.0.1:13306/yicai_erp?charset=utf8mb4",
    )
    sd_site_code: str = os.getenv("SD_SITE_CODE", "sdzfcg")
    sd_region_guid: str = os.getenv("SD_REGION_GUID", "1487001")
    sd_region_code: str = os.getenv("SD_REGION_CODE", "370001")
    # 供应商抓取（TouchCustomer）：列表加密，本地 node js/decode.js 解密
    sd_supplier_list_url: str = os.getenv(
        "SD_SUPPLIER_LIST_URL",
        "https://ggzyjyzx.shandong.gov.cn:8182/gpmall-basic/api/supplier/v1/ignore/getSupplierByAgreement",
    )
    sd_store_url: str = os.getenv(
        "SD_STORE_URL",
        "https://ggzyjyzx.shandong.gov.cn:8182/gateway/gpmall-goodslibrary/api/store/v1/ignore/store",
    )
    # 可选：已有 token；否则用账号密码登录自动获取
    sd_access_token: str = os.getenv("SD_ACCESS_TOKEN", "")
    sd_account: str = os.getenv("SD_ACCOUNT", "")
    sd_password: str = os.getenv("SD_PASSWORD", "")
    # 验证码 OCR（对齐 vip-rebuild qlyc:login）
    qlyc_captcha_url: str = os.getenv("QLYC_CAPTCHA_URL", "http://verify.qlyc.co/upload_image")
    jd_contract_num: str = os.getenv("JD_CONTRACT_NUM", "VSP-20250526220758")
    jd_app_source: str = os.getenv("JD_APP_SOURCE", "CLT")
    jd_impersonate: str = os.getenv("JD_IMPERSONATE", "chrome131")
    # api=云端 OpenAI 兼容；heuristic=规则；local_gguf / local_hf=本地模型
    extractor_backend: str = os.getenv("EXTRACTOR_BACKEND", "local_gguf")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    local_model_path: str = os.getenv(
        "LOCAL_MODEL_PATH",
        str(ROOT / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"),
    )
    local_model_device: str = os.getenv("LOCAL_MODEL_DEVICE", "auto")
    local_max_new_tokens: int = int(os.getenv("LOCAL_MAX_NEW_TOKENS", "1024"))
    local_n_ctx: int = int(os.getenv("LOCAL_N_CTX", "4096"))
    local_n_gpu_layers: int = int(os.getenv("LOCAL_N_GPU_LAYERS", "0"))
    attachment_dir: Path = Path(os.getenv("ATTACHMENT_DIR", str(ROOT / "data" / "attachments")))
    request_interval: float = float(os.getenv("REQUEST_INTERVAL", "0.4"))


settings = Settings()
settings.attachment_dir.mkdir(parents=True, exist_ok=True)
(ROOT / "models").mkdir(parents=True, exist_ok=True)
