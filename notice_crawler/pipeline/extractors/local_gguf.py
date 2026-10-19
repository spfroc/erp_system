from __future__ import annotations

from typing import Any, Dict

from pipeline.extractors.base import BaseExtractor, build_prompt, parse_json_loose
from pipeline.extractors.heuristic import HeuristicExtractor


class LocalGGUFExtractor(BaseExtractor):
    """本地 GGUF（llama-cpp-python），适合 CPU / 消费级显卡。

    把 .gguf 路径配到 LOCAL_MODEL_PATH，例如：
    models/qwen2.5-3b-instruct-q4_k_m.gguf
    或自训导出的 GGUF。
    """

    name = "local_gguf"

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 4096,
        n_gpu_layers: int = 0,
        max_new_tokens: int = 1024,
    ) -> None:
        if not model_path:
            raise RuntimeError("LOCAL_MODEL_PATH 未配置，无法加载 GGUF 模型")
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.max_new_tokens = max_new_tokens
        self._llm = None
        self._fallback = HeuristicExtractor()

    def _load(self) -> None:
        if self._llm is not None:
            return
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "请安装: pip install llama-cpp-python"
            ) from exc
        self._llm = Llama(
            model_path=self.model_path,
            n_ctx=self.n_ctx,
            n_gpu_layers=self.n_gpu_layers,
            verbose=False,
        )

    def extract(self, text: str, title: str = "") -> Dict[str, Any]:
        self._load()
        # 预留模板 / 输出 token，避免超出 n_ctx（常见 4096）
        max_chars = max(800, min(4500, self.n_ctx * 2 - 2500))
        prompt = build_prompt(title, text, max_chars=max_chars)
        # 通用 instruct 模板；自训模型若模板不同可改这里
        full = (
            "<|im_start|>system\n你只输出合法 JSON。<|im_end|>\n"
            f"<|im_start|>user\n{prompt}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        result = self._llm(
            full,
            max_tokens=self.max_new_tokens,
            temperature=0.1,
            stop=["<|im_end|>", "</s>"],
        )
        content = result["choices"][0]["text"]
        try:
            data = parse_json_loose(content)
        except Exception:  # noqa: BLE001
            data = self._fallback.extract(text, title=title)
            if not isinstance(data.get("extra"), dict):
                data["extra"] = {}
            data["extra"]["gguf_raw"] = content[:4000]
            data["extra"]["extractor"] = f"{self.name}+heuristic_fallback"
            data["confidence"] = min(float(data.get("confidence") or 0.2), 0.25)
            return data

        if not isinstance(data, dict):
            data = self._fallback.extract(text, title=title)
            if not isinstance(data.get("extra"), dict):
                data["extra"] = {}
            data["extra"]["extractor"] = f"{self.name}+heuristic_fallback"
            return data

        if not isinstance(data.get("extra"), dict):
            data["extra"] = {}
        data["extra"]["extractor"] = self.name
        data["extra"]["model_path"] = self.model_path
        if data.get("confidence") is None:
            data["confidence"] = 0.7
        base = self._fallback.extract(text, title=title)
        for k, v in base.items():
            if k in {"goods", "quotes", "suppliers", "extra"}:
                continue
            if data.get(k) in (None, "", []):
                data[k] = v
        if not data.get("goods"):
            data["goods"] = base.get("goods") or []
        if not data.get("quotes"):
            data["quotes"] = base.get("quotes") or []
        return data
