from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict

# 商品明细：一条公告可有多条
GOODS_ITEM_SCHEMA: Dict[str, Any] = {
    "name": None,  # 产品名称
    "category": None,  # 分类
    "quantity": None,  # 购买数量
    "unit": None,  # 单位
    "brand": None,  # 品牌
    "model": None,  # 型号
    "unit_price": None,  # 单价（成交/报价单价优先，否则最高限价）
    "spec": None,  # 参数/规格
    "amount": None,  # 金额小计（若有）
}

EXTRACT_SCHEMA: Dict[str, Any] = {
    "project_code": None,
    "project_name": None,
    "notice_title": None,
    "buyer_name": None,
    "buyer_contact_name": None,  # 项目联系人
    "buyer_phone": None,  # 项目联系电话
    "buyer_address": None,  # 项目/采购人地址
    "buyer_contact": None,  # 兼容旧字段：联系人+电话合并串
    "region_name": None,
    "budget_amount": None,
    "deal_amount": None,
    "deal_supplier": None,
    "deal_supplier_phone": None,  # 成交供应商电话
    "deal_supplier_address": None,  # 成交供应商地址
    "quote_count": None,
    "notice_kind": None,
    "procurement_mode": None,
    "publish_time": None,
    "start_time": None,  # 采购/竞价开始时间
    "end_time": None,  # 截止时间
    "delivery_address": None,
    "goods": [GOODS_ITEM_SCHEMA],
    "quotes": [
        {
            "supplier_name": None,
            "quote_amount": None,
            "rank": None,
            "is_winner": False,
            "phone": None,
            "address": None,
        }
    ],
    "suppliers": [],
    "extra": {},
    "confidence": 0.0,
}

SYSTEM_PROMPT = """你是政府采购公告信息抽取助手。
只根据给定正文抽取字段，不要编造。
不确定的字段填 null 或空数组。
金额、单价、数量输出纯数字（可带小数），不要货币符号和千分位。
时间统一为 YYYY-MM-DD HH:MM:SS；若只有日期则 YYYY-MM-DD。
goods 必须是数组：公告里有几条产品就输出几条，不要合并成一条。
成交供应商的电话/地址填 deal_supplier_phone / deal_supplier_address；
项目联系人填 buyer_contact_name / buyer_phone / buyer_address。
必须只输出一个 JSON 对象，不要 Markdown。
字段模板：
""" + json.dumps(EXTRACT_SCHEMA, ensure_ascii=False, indent=2)


# 附件只抽产品明细，统一按 goods 入库（货物/工程/服务/租赁/项目等）
ATTACHMENT_EXTRACT_SCHEMA: Dict[str, Any] = {
    "goods": [
        {
            "name": None,
            "category": None,  # 货物/工程/服务/租赁/项目/其他
            "quantity": None,
            "unit": None,
            "brand": None,
            "model": None,
            "unit_price": None,
            "spec": None,
            "amount": None,
        }
    ],
}

ATTACHMENT_SYSTEM_PROMPT = """你是采购附件「产品清单」抽取助手。
只抽取可入库的产品/标的行，全部放进 goods 数组。不要抽联系人、公告正文、评分办法。
禁止编造；正文没有的字段填 null。

产品包含：货物、耗材、设备、工程分项、服务项、租赁项、项目包等，一律当商品行。
规则：
- 有几条就输出几条，禁止合并成一条项目总称
- category 填：货物 / 工程 / 服务 / 租赁 / 项目 / 其他
- name=产品或分项名称；规格参数放 spec；品牌/型号有则填
- 数量、单价、金额只输出纯数字
- 纯评分/资质且无清单时 goods=[]

只输出一个 JSON 对象，不要 Markdown。
字段模板：
""" + json.dumps(ATTACHMENT_EXTRACT_SCHEMA, ensure_ascii=False, indent=2)


def build_prompt(title: str, text: str, max_chars: int = 12000) -> str:
    body = (text or "")[:max_chars]
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"公告标题: {title or ''}\n\n"
        f"正文:\n{body}\n\n"
        "请输出 JSON："
    )


def build_attachment_prompt(title: str, text: str, max_chars: int = 4500) -> str:
    body = (text or "")[:max_chars]
    return (
        f"{ATTACHMENT_SYSTEM_PROMPT}\n\n"
        f"附件标题: {title or ''}\n\n"
        f"附件正文:\n{body}\n\n"
        "请输出 JSON："
    )


def parse_json_loose(content: str) -> Dict[str, Any]:
    content = (content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", content)
        if not m:
            raise
        return json.loads(m.group(0))


class BaseExtractor(ABC):
    name: str = "base"

    @abstractmethod
    def extract(self, text: str, title: str = "") -> Dict[str, Any]:
        raise NotImplementedError
