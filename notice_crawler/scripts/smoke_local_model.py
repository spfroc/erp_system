#!/usr/bin/env python3
"""本地抽取器冒烟：加载模型并对样例公告做一次抽取。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402
from pipeline.extractors import get_extractor  # noqa: E402


SAMPLE_TITLE = "某某单位办公设备采购成交公告"
SAMPLE_TEXT = """
项目编号：SD-2024-00123
项目名称：办公设备采购项目
采购人：某某市某某局
项目联系人：张三
电话：0531-12345678
地址：某某市某某区某某路88号
预算金额：50000.00元
成交金额：48500.00元
成交供应商：某某科技有限公司
供应商电话：0531-87654321
供应商地址：某某市高新区创新路66号
采购方式：询比
公告类型：成交公告
开始时间：2024-05-01 09:00:00
截止时间：2024-05-10 17:00:00
交货地点：某某市某某区某某路1号
商品明细：
1. 台式电脑，分类：IT设备，品牌：联想，型号：启天M428，数量：10，单价：3500，参数：i5/16G/512G SSD
2. 激光打印机，分类：办公外设，品牌：惠普，型号：M404dn，数量：2，单价：2200，参数：黑白双面网络打印
报价供应商共3家。
"""


def main() -> int:
    print("EXTRACTOR_BACKEND =", settings.extractor_backend)
    print("LOCAL_MODEL_PATH  =", settings.local_model_path)
    path = Path(settings.local_model_path)
    if settings.extractor_backend.lower().strip() in {
        "local_gguf",
        "gguf",
        "llama_cpp",
        "local_hf",
        "hf",
        "transformers",
    }:
        if not path.exists():
            print(f"模型文件不存在: {path}", file=sys.stderr)
            print("请先运行: bash scripts/download_gguf.sh", file=sys.stderr)
            return 1

    extractor = get_extractor()
    print("加载并推理中…")
    data = extractor.extract(SAMPLE_TEXT, title=SAMPLE_TITLE)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("ok, extractor =", data.get("extra", {}).get("extractor") or extractor.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
