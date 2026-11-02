"""统计类工具的图表参数：默认不附带图表，仅显式请求时启用。"""

from __future__ import annotations

from typing import Any


def resolve_chart_type(params: dict[str, Any]) -> str | None:
    """仅当显式传入 chart_type 时返回 bar|line|pie；默认 None。"""
    raw = str(
        params.get("chart_type") or params.get("chartType") or params.get("chart") or ""
    ).strip().lower()
    if not raw or raw in {"none", "null", "false", "0", "no", "无", "off"}:
        return None
    if raw in {"bar", "柱状", "柱状图", "条形", "条形图"}:
        return "bar"
    if raw in {"line", "折线", "折线图", "趋势"}:
        return "line"
    if raw in {"pie", "饼图", "饼状", "饼状图"}:
        return "pie"
    if raw in {"true", "yes", "1", "chart", "图表", "echarts"}:
        return "bar"
    return "bar"
