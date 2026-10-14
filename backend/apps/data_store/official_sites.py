"""Official multi-domain CMS: sites, pages, and public host resolution."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from .models import OfficialPageRecord, OfficialSiteRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_host(value: str | None) -> str:
    host = (value or "").strip().lower()
    if not host:
        return ""
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/", 1)[0]
    host = host.split(":", 1)[0]
    if host.startswith("www."):
        bare = host[4:]
    else:
        bare = host
        host = f"www.{bare}" if bare and "." in bare else host
    return host


def site_defaults(payload: dict) -> dict:
    data = normalize_site_payload(payload)
    return {
        "data": data,
        "created_at": data.get("createdAt") or None,
        "key": data.get("key") or "",
        "name": data.get("name") or "",
        "domain": data.get("domain") or "",
        "brand": data.get("brand") or "",
        "company_name": data.get("companyName") or "",
        "phone": data.get("phone") or "",
        "status": data.get("status") or "启用",
    }


def page_defaults(payload: dict) -> dict:
    data = normalize_page_payload(payload)
    return {
        "data": data,
        "created_at": data.get("createdAt") or None,
        "site_id": data.get("siteId") or "",
        "slug": data.get("slug") or "",
        "title": data.get("title") or "",
        "template": data.get("template") or "home",
        "status": data.get("status") or "draft",
        "sort_order": int(data.get("sortOrder") or 0),
    }


def normalize_site_payload(payload: dict) -> dict:
    now = _now()
    domain = normalize_host(payload.get("domain") or payload.get("host"))
    key = (payload.get("key") or "").strip() or (domain.replace("www.", "").split(".")[0] if domain else "")
    return {
        **payload,
        "id": payload.get("id") or f"site-{key}",
        "key": key,
        "name": (payload.get("name") or "").strip() or key,
        "domain": domain,
        "brand": (payload.get("brand") or "").strip(),
        "companyName": (payload.get("companyName") or "").strip(),
        "phone": (payload.get("phone") or "").strip(),
        "email": (payload.get("email") or "").strip(),
        "address": (payload.get("address") or "").strip(),
        "logoUrl": (payload.get("logoUrl") or "").strip(),
        "primaryColor": (payload.get("primaryColor") or "").strip() or "#0066cc",
        "seoTitle": (payload.get("seoTitle") or "").strip(),
        "seoDescription": (payload.get("seoDescription") or "").strip(),
        "seoKeywords": (payload.get("seoKeywords") or "").strip(),
        "status": (payload.get("status") or "启用").strip() or "启用",
        "createdAt": payload.get("createdAt") or now,
        "updatedAt": now,
    }


def normalize_page_payload(payload: dict) -> dict:
    now = _now()
    slug = (payload.get("slug") or "home").strip().strip("/") or "home"
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        blocks = []
    return {
        **payload,
        "id": payload.get("id") or f"page-{(payload.get('siteId') or 'site')}-{slug}",
        "siteId": (payload.get("siteId") or "").strip(),
        "slug": slug,
        "title": (payload.get("title") or "").strip() or slug,
        "template": (payload.get("template") or "home").strip() or "home",
        "status": (payload.get("status") or "draft").strip() or "draft",
        "seoTitle": (payload.get("seoTitle") or "").strip(),
        "seoDescription": (payload.get("seoDescription") or "").strip(),
        "blocks": blocks,
        "sortOrder": int(payload.get("sortOrder") or 0),
        "createdAt": payload.get("createdAt") or now,
        "updatedAt": now,
    }


def _block(block_type: str, data: dict) -> dict:
    return {"type": block_type, "data": data}


def qlyc_home_blocks() -> list[dict]:
    return [
        _block(
            "hero",
            {
                "title": "政企采购电商服务平台",
                "subtitle": "济南泉E采阳光采购平台 | 齐鲁云采 | 框架协议等政府采购平台一站式入驻与运营服务",
                "primaryCta": {"label": "立即咨询入驻", "href": "#contact"},
                "secondaryCta": {"label": "了解平台详情", "href": "#platforms"},
            },
        ),
        _block(
            "stats",
            {
                "items": [
                    {"value": "10年+", "label": "服务经验"},
                    {"value": "2000+", "label": "成功服务客户"},
                    {"value": "365天", "label": "全天候管家式服务"},
                    {"value": "100%", "label": "客户效率提升"},
                ]
            },
        ),
        _block(
            "features",
            {
                "title": "专业的政企采购电商服务平台",
                "subtitle": "致力于为供应商企业提供全方位的服务支持，帮助企业在政府采购市场中快速成长",
                "items": [
                    {
                        "title": "平台入驻服务",
                        "text": "为供应商提供齐鲁云采、框架协议、泉E采等政府采购平台的入驻、入围、运营、规则培训、交易指导等全流程服务。",
                    },
                    {
                        "title": "技术研发支持",
                        "text": "通过技术研发提供 API 接口对接、商品管理、订单统计分析、渠道管理等技术服务，帮助供应商高效管理多平台业务。",
                    },
                    {
                        "title": "资源整合服务",
                        "text": "整合行业资源，提供商标证书、品牌授权、一件代发等服务，帮助供应商降低运营成本，提高市场竞争力。",
                    },
                ],
            },
        ),
        _block(
            "platforms",
            {
                "title": "政企采购平台",
                "items": [
                    {
                        "name": "齐鲁云采",
                        "headline": "山东省政府采购网上商城",
                        "points": [
                            "性质：政府采购专用商城",
                            "地区：山东省全省范围",
                            "采购人：教育、医疗、公检法、各级政府部门等财政拨付单位",
                            "入驻条件：正常经营的公司企业或个体户",
                            "入驻周期：3个工作日快速入驻",
                        ],
                        "tags": ["全省覆盖", "多品类经营", "快速入驻"],
                    },
                    {
                        "name": "泉E采（火热入驻中）",
                        "headline": "济南市政府采购分散采购平台",
                        "points": [
                            "性质：济南市政府与京东合作平台",
                            "采购人：济南财政拨付的单位",
                            "优势：京东60天账期结算，资金安全有保障",
                            "入驻条件：一般纳税人或小规模企业",
                            "费用：1万元押金 + 1%平台使用费",
                        ],
                        "tags": ["京东合作", "账期保障", "B端专营"],
                    },
                    {
                        "name": "框架协议",
                        "headline": "山东省政府采购框架协议平台",
                        "points": [
                            "产品类：生产厂家统一招标入围，授权各地供应商落地",
                            "涉及品目：复印纸、空调、计算机、服务器、打印机等",
                            "服务类：以地市为单位招标入围物业、印刷、汽租等",
                        ],
                        "tags": ["省级招标", "厂家授权", "多地服务"],
                    },
                ],
            },
        ),
        _block(
            "contact",
            {
                "title": "联系我们",
                "subtitle": "留下需求，我们尽快与您联系",
                "phone": "0531-86099058",
                "mobile": "13105315957",
                "email": "Wangyunlei@yizhichan.co",
                "address": "济南市市中区大观园街道纬二路49号汇宝大厦2106A",
            },
        ),
    ]


SITE_SEEDS = [
    {
        "id": "site-qlyc",
        "key": "qlyc",
        "name": "壹采官网",
        "domain": "www.qlyc.co",
        "brand": "壹采",
        "companyName": "山东壹知产数字科技有限公司",
        "phone": "0531-86099058",
        "email": "Wangyunlei@yizhichan.co",
        "address": "济南市市中区大观园街道纬二路49号汇宝大厦2106A",
        "logoUrl": "/image/logo.png",
        "primaryColor": "#0066cc",
        "seoTitle": "壹采 - 政企采购电商服务平台 | 齐鲁云采入驻 | 泉E采代办 | 山东省政府采购网上商城",
        "seoDescription": "壹采是专业的政企采购电商服务平台，提供齐鲁云采、框架协议、泉E采等山东省政府采购平台一站式入驻、技术对接和运营服务。",
        "seoKeywords": "壹采,齐鲁云采,泉E采,山东省政府采购网上商城,济南市政府采购",
        "status": "启用",
        "homePublished": True,
    },
    {
        "id": "site-yizhichan",
        "key": "yizhichan",
        "name": "壹知产官网",
        "domain": "www.yizhichan.co",
        "brand": "壹知产",
        "companyName": "山东壹知产数字科技有限公司",
        "phone": "0531-86099058",
        "email": "Wangyunlei@yizhichan.co",
        "address": "济南市市中区大观园街道纬二路49号汇宝大厦2106A",
        "primaryColor": "#0066cc",
        "seoTitle": "壹知产 - 政企采购电商服务",
        "seoDescription": "山东壹知产数字科技有限公司官方网站。",
        "status": "启用",
        "homePublished": False,
    },
    {
        "id": "site-jinanyunji",
        "key": "jinanyunji",
        "name": "济南云集官网",
        "domain": "www.jinanyunji.com",
        "brand": "济南云集",
        "companyName": "山东壹知产数字科技有限公司",
        "phone": "0531-86099058",
        "primaryColor": "#0066cc",
        "seoTitle": "济南云集 - 政企采购服务",
        "seoDescription": "济南云集官方网站。",
        "status": "启用",
        "homePublished": False,
    },
    {
        "id": "site-qinghuicai",
        "key": "qinghuicai",
        "name": "青慧采官网",
        "domain": "www.qinghuicai.cn",
        "brand": "青慧采",
        "companyName": "山东壹知产数字科技有限公司",
        "phone": "0531-86099058",
        "primaryColor": "#1f7a4d",
        "seoTitle": "青慧采入驻代办",
        "seoDescription": "青慧采入驻代办服务。",
        "status": "启用",
        "homePublished": False,
    },
]


def ensure_default_official_sites() -> list[OfficialSiteRecord]:
    created_sites: list[OfficialSiteRecord] = []
    for seed in SITE_SEEDS:
        payload = normalize_site_payload(deepcopy(seed))
        site, created = OfficialSiteRecord.objects.update_or_create(
            id=payload["id"],
            defaults={**site_defaults(payload), "is_deleted": False, "deleted_at": None, "deleted_by": ""},
        )
        if created:
            created_sites.append(site)

        page_id = f"page-{payload['id']}-home"
        page_payload = normalize_page_payload(
            {
                "id": page_id,
                "siteId": payload["id"],
                "slug": "home",
                "title": "首页",
                "template": "home",
                "status": "published" if seed.get("homePublished") else "draft",
                "seoTitle": payload.get("seoTitle") or "",
                "seoDescription": payload.get("seoDescription") or "",
                "blocks": qlyc_home_blocks() if payload["key"] == "qlyc" else [
                    _block(
                        "hero",
                        {
                            "title": payload.get("brand") or payload.get("name"),
                            "subtitle": "站点内容迁移中，请稍后访问或联系客服。",
                            "primaryCta": {"label": "联系我们", "href": f"tel:{payload.get('phone') or ''}"},
                        },
                    ),
                    _block(
                        "contact",
                        {
                            "title": "联系我们",
                            "phone": payload.get("phone") or "",
                            "email": payload.get("email") or "",
                            "address": payload.get("address") or "",
                        },
                    ),
                ],
            }
        )
        OfficialPageRecord.objects.update_or_create(
            id=page_id,
            defaults={**page_defaults(page_payload), "is_deleted": False, "deleted_at": None, "deleted_by": ""},
        )
    return created_sites


def resolve_public_site(host: str, slug: str = "home") -> dict | None:
    ensure_default_official_sites()
    normalized = normalize_host(host)
    bare = normalized[4:] if normalized.startswith("www.") else normalized
    site = (
        OfficialSiteRecord.objects.filter(is_deleted=False, status="启用", domain=normalized).first()
        or OfficialSiteRecord.objects.filter(is_deleted=False, status="启用", domain=f"www.{bare}").first()
        or OfficialSiteRecord.objects.filter(is_deleted=False, status="启用", domain=bare).first()
        or OfficialSiteRecord.objects.filter(is_deleted=False, status="启用", key=bare.split(".")[0]).first()
    )
    if not site:
        return None
    page = (
        OfficialPageRecord.objects.filter(
            is_deleted=False,
            site_id=site.id,
            slug=(slug or "home").strip() or "home",
            status="published",
        )
        .order_by("sort_order", "id")
        .first()
    )
    return {"site": site.data, "page": page.data if page else None}
