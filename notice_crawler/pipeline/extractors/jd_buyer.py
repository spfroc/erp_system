"""泉E采 / 青慧采：采购单位解析。

优先用项目名称规则拆分；规则失败再用本地模型对项目名称做短抽取（非整篇公告）。
"""

from __future__ import annotations

import re
from typing import Any, Optional, Tuple

from pipeline.extractors.base import parse_json_loose
from utils import extract_buyer_from_project_name

PLATFORM_HINTS = ("采购服务", "泉易采", "青慧采", "国易采购", "科技投资", "泉E采", "泉e采")

_BUYER_LLM = None
_BUYER_LLM_FAILED = False

_BUYER_PROMPT = """你是政府采购信息抽取助手。
只根据给定「项目名称」提取采购单位（买方机构全称）。
不要编造；无法判断时 buyer_name 填 null。
必须只输出一个 JSON 对象，不要 Markdown。
格式：{{"buyer_name": "单位名称或null"}}

项目名称：{name}
"""


def _clean_api_buyer(api_buyer: Any) -> str:
    api = str(api_buyer).strip() if api_buyer not in (None, "") else ""
    if api and any(h in api for h in PLATFORM_HINTS):
        return ""
    return api


def _prefer_name_buyer(
    name_buyer: Optional[str],
    api_buyer: Any,
    project_name: Optional[str],
) -> Optional[str]:
    """项目名称拆出的单位优先；接口值作兜底。平台服务商名则忽略。"""
    api = _clean_api_buyer(api_buyer)
    name = (name_buyer or "").strip()
    project = project_name or ""
    if name:
        # 接口单位已是名称前缀时保留接口（通常更规范）
        if api and (project.startswith(api) or api in project[: max(len(api) + 8, 24)]):
            return api
        return name
    return api or None


def _get_buyer_llm():
    """懒加载本地 GGUF（仅用于采购单位短抽取）。"""
    global _BUYER_LLM, _BUYER_LLM_FAILED
    if _BUYER_LLM_FAILED:
        return None
    if _BUYER_LLM is not None:
        return _BUYER_LLM
    try:
        from pathlib import Path

        from config import settings

        path = Path(settings.local_model_path)
        if not path.exists() or path.suffix.lower() != ".gguf":
            _BUYER_LLM_FAILED = True
            return None
        from llama_cpp import Llama

        _BUYER_LLM = Llama(
            model_path=str(path),
            n_ctx=min(2048, int(settings.local_n_ctx or 2048)),
            n_gpu_layers=int(settings.local_n_gpu_layers or 0),
            verbose=False,
        )
        return _BUYER_LLM
    except Exception:  # noqa: BLE001
        _BUYER_LLM_FAILED = True
        return None


def extract_buyer_by_local_model(project_name: str | None) -> Optional[str]:
    """仅用项目名称走本地模型，抽取采购单位。"""
    name = (project_name or "").strip()
    if not name:
        return None
    llm = _get_buyer_llm()
    if llm is None:
        return None
    prompt = _BUYER_PROMPT.format(name=name[:300])
    full = (
        "<|im_start|>system\n你只输出合法 JSON。<|im_end|>\n"
        f"<|im_start|>user\n{prompt}<|im_end|>\n"
        "<|im_start|>assistant\n"
    )
    try:
        result = llm(
            full,
            max_tokens=64,
            temperature=0.1,
            stop=["<|im_end|>", "</s>"],
        )
        content = result["choices"][0]["text"]
        data = parse_json_loose(content)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, dict):
        return None
    buyer = data.get("buyer_name")
    if buyer in (None, "", "null", "None"):
        return None
    text = str(buyer).strip()
    text = re.sub(r'^["“]|["”]$', "", text).strip()
    if len(text) < 4 or any(h in text for h in PLATFORM_HINTS):
        return None
    # 模型偶发整段复述项目名称：再跑一遍规则截断
    if text == name or len(text) > max(40, len(name) - 2):
        trimmed = extract_buyer_from_project_name(text)
        if trimmed:
            return trimmed
        if text == name:
            return None
    return text[:256]


def resolve_jd_buyer_name(
    project_name: str | None,
    api_buyer: Any = None,
    *,
    use_local_model: bool = True,
) -> Tuple[Optional[str], Optional[str]]:
    """解析京东采购单位。

    返回 (buyer_name, source)，source 为 rule / local_model / api / None。
    """
    project = (project_name or "").strip()
    rule_buyer = extract_buyer_from_project_name(project)
    preferred = _prefer_name_buyer(rule_buyer, api_buyer, project)
    if rule_buyer and preferred:
        # 规则命中（或规则+更规范的接口前缀）
        if preferred == rule_buyer:
            return preferred, "rule"
        return preferred, "api"

    if use_local_model and project:
        model_buyer = extract_buyer_by_local_model(project)
        if model_buyer:
            return model_buyer, "local_model"

    api = _clean_api_buyer(api_buyer)
    if api:
        return api, "api"
    return None, None
