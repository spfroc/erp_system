from __future__ import annotations

from typing import Any, Dict, Optional

from pipeline.extractors.base import (
    BaseExtractor,
    build_attachment_prompt,
    build_prompt,
    parse_json_loose,
)
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
        max_chars = max(800, min(3000, self.n_ctx - 1200))
        return self._run(
            lambda body: build_prompt(title, body, max_chars=max(len(body), 1)),
            text,
            title,
            merge_heuristic=True,
            body_budget_chars=max_chars,
        )

    def extract_attachment(self, text: str, title: str = "") -> Dict[str, Any]:
        """附件只抽产品 goods；长文按块抽取后合并。"""
        body = (text or "").strip()
        chunk_size = max(600, min(1800, self.n_ctx - 2000))
        if len(body) <= chunk_size + 200:
            return self._extract_attachment_once(body, title, chunk_size)

        chunks = self._split_chunks(body, chunk_size, overlap=120)
        merged: list = []
        seen: set = set()
        last: Dict[str, Any] = {
            "goods": [],
            "extra": {"extractor": "local_gguf_attachment"},
            "confidence": 0.5,
        }
        # 小模型 CPU 很慢：最多 4 块，优先覆盖全文头中尾
        if len(chunks) > 4:
            mid = len(chunks) // 2
            pick = [0, mid // 2, mid, len(chunks) - 1]
            chunks = [chunks[i] for i in sorted(set(pick))]
        for chunk in chunks:
            part = self._extract_attachment_once(chunk, title, chunk_size)
            last = part
            for item in part.get("goods") or []:
                if not isinstance(item, dict):
                    continue
                key = (
                    str(item.get("name") or "").strip(),
                    str(item.get("unit") or "").strip(),
                    str(item.get("quantity") or "").strip(),
                    str(item.get("model") or "").strip()[:40],
                )
                if not key[0] or key in seen:
                    continue
                seen.add(key)
                merged.append(item)
        if not isinstance(last.get("extra"), dict):
            last["extra"] = {}
        last["goods"] = merged
        last["extra"]["extractor"] = "local_gguf_attachment+chunked"
        last["extra"]["chunk_count"] = len(chunks)
        last["confidence"] = 0.65 if merged else float(last.get("confidence") or 0.2)
        return last

    def _extract_attachment_once(
        self, text: str, title: str, body_budget_chars: int
    ) -> Dict[str, Any]:
        return self._run(
            lambda body: build_attachment_prompt(title, body, max_chars=max(len(body), 1)),
            text,
            title,
            source="local_gguf_attachment",
            merge_heuristic=False,
            max_tokens=min(self.max_new_tokens, 768),
            body_budget_chars=body_budget_chars,
        )

    @staticmethod
    def _split_chunks(text: str, size: int, overlap: int = 100) -> list[str]:
        text = text or ""
        if len(text) <= size:
            return [text]
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + size)
            # 尽量在换行处切开
            if end < len(text):
                nl = text.rfind("\n", start + size // 2, end)
                if nl > start:
                    end = nl
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
        return chunks or [text[:size]]

    def _count_tokens(self, text: str) -> int:
        self._load()
        return len(self._llm.tokenize(text.encode("utf-8")))

    def _fit_prompt(
        self,
        build_user_prompt,
        text: str,
        *,
        max_tokens: int,
        body_budget_chars: int,
    ) -> tuple[str, int]:
        """裁正文，保证 prompt_tokens + max_tokens <= n_ctx。"""
        body = (text or "")[:body_budget_chars]
        wrap = (
            "<|im_start|>system\n你只输出合法 JSON。<|im_end|>\n"
            "<|im_start|>user\n{user}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        for _ in range(12):
            user = build_user_prompt(body)
            full = wrap.format(user=user)
            prompt_tokens = self._count_tokens(full)
            # llama.cpp 要求 requested = prompt + n_predict 不超过 n_ctx
            if prompt_tokens + max_tokens <= self.n_ctx:
                return full, max(64, min(max_tokens, self.n_ctx - prompt_tokens - 8))
            # 超了就砍正文；至少留一点
            if len(body) <= 200:
                # 正文已很短仍超：再砍输出额度
                max_tokens = max(64, self.n_ctx - prompt_tokens - 8)
                if max_tokens >= 64 and prompt_tokens + max_tokens <= self.n_ctx:
                    return full, max_tokens
                body = body[: max(50, len(body) // 2)]
            else:
                # 按超出比例收缩
                overflow = prompt_tokens + max_tokens - self.n_ctx
                shrink = max(100, int(len(body) * 0.7) - overflow * 2)
                body = body[: max(200, shrink)]
        user = build_user_prompt(body[:200])
        full = wrap.format(user=user)
        prompt_tokens = self._count_tokens(full)
        return full, max(64, min(256, self.n_ctx - prompt_tokens - 8))

    def _run(
        self,
        build_user_prompt,
        text: str,
        title: str,
        *,
        source: Optional[str] = None,
        merge_heuristic: bool = True,
        max_tokens: Optional[int] = None,
        body_budget_chars: int = 3000,
    ) -> Dict[str, Any]:
        self._load()
        want_out = max_tokens or self.max_new_tokens
        full, out_tokens = self._fit_prompt(
            build_user_prompt,
            text,
            max_tokens=want_out,
            body_budget_chars=body_budget_chars,
        )
        try:
            result = self._llm(
                full,
                max_tokens=out_tokens,
                temperature=0.1,
                stop=["<|im_end|>", "</s>"],
            )
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "exceed context" in msg.lower() or "context window" in msg.lower():
                # 再砍一半正文重试一次
                half = (text or "")[: max(200, body_budget_chars // 2)]
                full, out_tokens = self._fit_prompt(
                    build_user_prompt,
                    half,
                    max_tokens=min(want_out, 256),
                    body_budget_chars=len(half),
                )
                result = self._llm(
                    full,
                    max_tokens=out_tokens,
                    temperature=0.1,
                    stop=["<|im_end|>", "</s>"],
                )
            else:
                raise
        content = result["choices"][0]["text"]
        label = source or self.name
        try:
            data = parse_json_loose(content)
        except Exception:  # noqa: BLE001
            if not merge_heuristic:
                return {
                    "goods": [],
                    "extra": {
                        "extractor": f"{label}+json_fail",
                        "gguf_raw": content[:4000],
                    },
                    "confidence": 0.1,
                }
            data = self._fallback.extract(text, title=title)
            if not isinstance(data.get("extra"), dict):
                data["extra"] = {}
            data["extra"]["gguf_raw"] = content[:4000]
            data["extra"]["extractor"] = f"{label}+heuristic_fallback"
            data["confidence"] = min(float(data.get("confidence") or 0.2), 0.25)
            return data

        if not isinstance(data, dict):
            if not merge_heuristic:
                return {
                    "goods": [],
                    "extra": {"extractor": f"{label}+bad_type", "gguf_raw": content[:4000]},
                    "confidence": 0.1,
                }
            data = self._fallback.extract(text, title=title)
            if not isinstance(data.get("extra"), dict):
                data["extra"] = {}
            data["extra"]["extractor"] = f"{label}+heuristic_fallback"
            return data

        if not isinstance(data.get("extra"), dict):
            data["extra"] = {}
        data["extra"]["extractor"] = label
        data["extra"]["model_path"] = self.model_path
        if data.get("confidence") is None:
            data["confidence"] = 0.7
        if not isinstance(data.get("goods"), list):
            data["goods"] = []
        # 把 item_type 落到 category，便于入库
        for item in data["goods"]:
            if not isinstance(item, dict):
                continue
            item_type = item.get("item_type")
            if item_type and not item.get("category"):
                item["category"] = item_type
        if merge_heuristic:
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
