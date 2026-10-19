from __future__ import annotations

from typing import Any, Dict, Optional

from pipeline.extractors.base import BaseExtractor, build_prompt, parse_json_loose
from pipeline.extractors.heuristic import HeuristicExtractor


class LocalHFExtractor(BaseExtractor):
    """本地 HuggingFace Transformers 推理（开源或自训权重目录）。

    推荐：
    - 开源：Qwen2.5-1.5B/3B/7B-Instruct、ChatGLM3 等
    - 自训：把微调后的目录路径配到 LOCAL_MODEL_PATH
    """

    name = "local_hf"

    def __init__(
        self,
        model_path: str,
        device: str = "auto",
        max_new_tokens: int = 1024,
    ) -> None:
        if not model_path:
            raise RuntimeError("LOCAL_MODEL_PATH 未配置，无法加载本地 HF 模型")
        self.model_path = model_path
        self.device = device
        self.max_new_tokens = max_new_tokens
        self._tokenizer = None
        self._model = None
        self._fallback = HeuristicExtractor()

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "请安装本地推理依赖: pip install torch transformers accelerate"
            ) from exc

        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_path, trust_remote_code=True
        )
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        kwargs: Dict[str, Any] = {
            "trust_remote_code": True,
            "torch_dtype": dtype,
        }
        if self.device == "auto":
            kwargs["device_map"] = "auto"
        self._model = AutoModelForCausalLM.from_pretrained(self.model_path, **kwargs)
        if self.device not in {"auto", ""} and self.device != "cpu":
            self._model.to(self.device)
        elif self.device == "cpu":
            self._model.to("cpu")
        self._model.eval()

    def extract(self, text: str, title: str = "") -> Dict[str, Any]:
        self._load()
        import torch

        prompt = build_prompt(title, text)
        messages = [
            {"role": "system", "content": "你只输出合法 JSON。"},
            {"role": "user", "content": prompt},
        ]
        # chat template 不可用时退回纯文本
        try:
            input_ids = self._tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_tensors="pt",
            )
        except Exception:  # noqa: BLE001
            enc = self._tokenizer(prompt, return_tensors="pt")
            input_ids = enc["input_ids"]

        if hasattr(input_ids, "to"):
            input_ids = input_ids.to(self._model.device)

        with torch.no_grad():
            out = self._model.generate(
                input_ids,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                temperature=0.1,
                pad_token_id=getattr(self._tokenizer, "eos_token_id", None),
            )
        gen = out[0][input_ids.shape[-1] :]
        content = self._tokenizer.decode(gen, skip_special_tokens=True)
        try:
            data = parse_json_loose(content)
        except Exception:  # noqa: BLE001
            # 模型输出不稳时，回退规则，并把模型原文放进 extra
            data = self._fallback.extract(text, title=title)
            if not isinstance(data.get("extra"), dict):
                data["extra"] = {}
            data["extra"]["hf_raw"] = content[:4000]
            data["extra"]["extractor"] = f"{self.name}+heuristic_fallback"
            data["confidence"] = min(float(data.get("confidence") or 0.2), 0.25)
            return data

        if not isinstance(data, dict):
            data = self._fallback.extract(text, title=title)
        if not isinstance(data.get("extra"), dict):
            data["extra"] = {}
        data["extra"]["extractor"] = self.name
        data["extra"]["model_path"] = self.model_path
        if "confidence" not in data or data["confidence"] is None:
            data["confidence"] = 0.7
        # 规则补洞：本地小模型常漏字段
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
