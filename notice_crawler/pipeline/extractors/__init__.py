from __future__ import annotations

from pipeline.extractors.base import BaseExtractor, EXTRACT_SCHEMA, build_prompt
from pipeline.extractors.heuristic import HeuristicExtractor


def get_extractor(backend: str | None = None):
    """按配置创建本地抽取器（不走云端 API）。"""
    from config import settings

    name = (backend or settings.extractor_backend or "heuristic").lower().strip()
    if name in {"heuristic", "rules", "regex"}:
        return HeuristicExtractor()
    if name in {"local_hf", "hf", "transformers"}:
        from pipeline.extractors.local_hf import LocalHFExtractor

        return LocalHFExtractor(
            model_path=settings.local_model_path,
            device=settings.local_model_device,
            max_new_tokens=settings.local_max_new_tokens,
        )
    if name in {"local_gguf", "gguf", "llama_cpp"}:
        from pipeline.extractors.local_gguf import LocalGGUFExtractor

        return LocalGGUFExtractor(
            model_path=settings.local_model_path,
            n_ctx=settings.local_n_ctx,
            n_gpu_layers=settings.local_n_gpu_layers,
            max_new_tokens=settings.local_max_new_tokens,
        )
    raise ValueError(
        f"未知 EXTRACTOR_BACKEND={name!r}，可选: heuristic / local_hf / local_gguf"
    )


__all__ = [
    "BaseExtractor",
    "EXTRACT_SCHEMA",
    "build_prompt",
    "HeuristicExtractor",
    "get_extractor",
]
