"""Official multi-domain CMS: sites, pages, and public host resolution."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .models import OfficialPageRecord, OfficialSiteRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_sitemap_urls(value) -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = re.split(r"[\r\n,]+", value)
    else:
        items = []
    result: list[str] = []
    seen: set[str] = set()
    for raw in items:
        url = str(raw or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        result.append(url)
    return result


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
        "ogImageUrl": (payload.get("ogImageUrl") or "").strip(),
        "robotsTxt": (payload.get("robotsTxt") or "").strip(),
        "sitemapUrls": _normalize_sitemap_urls(payload.get("sitemapUrls")),
        "jsonLd": (payload.get("jsonLd") or "").strip(),
        "baiduSiteVerification": (payload.get("baiduSiteVerification") or "").strip(),
        "googleSiteVerification": (payload.get("googleSiteVerification") or "").strip(),
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


_YICAI_SEO_TITLE = "壹采 - 政企采购电商服务平台 | 齐鲁云采入驻 | 泉E采代办 | 山东省政府采购网上商城 | 济南市政府采购"
_YICAI_SEO_DESCRIPTION = (
    "壹采是专业的政企采购电商服务平台，提供齐鲁云采、框架协议、泉E采等山东省政府采购平台一站式入驻、"
    "技术对接和运营服务。20年服务经验，助力2000+供应商成功入驻，提升采购效率100%。"
)
_YICAI_SEO_KEYWORDS = (
    "壹采, 齐鲁云采, 泉E采, 山东省政府采购网上商城, 济南市政府采购, 政企采购平台, 电商服务平台, "
    "政府采购入驻, 框架协议平台, 供应商服务, 山东壹知产数字科技有限公司, 齐鲁云采入驻条件, "
    "泉E采代办流程, 框架协议平台入围, 政府采购供应商服务, 办公用品政府采购, IT设备供应商入驻, 济南市政府采购平台"
)


def _org_json_ld(*, name: str, alternate: str, url: str, description: str) -> str:
    payload = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": name,
        "alternateName": alternate,
        "url": url,
        "logo": f"{url.rstrip('/')}/image/logo.png",
        "description": description,
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "济南市市中区",
            "streetAddress": "大观园街道纬二路49号汇宝大厦2106A",
        },
        "telephone": "0531-86099058",
        "email": "Wangyunlei@yizhichan.co",
        "areaServed": "山东省",
        "serviceType": "政企采购电商服务",
    }
    import json

    return json.dumps(payload, ensure_ascii=False)


# 从 official-web/sites/*/index.html、robots.txt、sitemap.xml 采集的原官网 SEO 默认值。
OFFICIAL_SEO_DEFAULTS: dict[str, dict[str, Any]] = {
    "qlyc": {
        "seoTitle": _YICAI_SEO_TITLE,
        "seoDescription": _YICAI_SEO_DESCRIPTION,
        "seoKeywords": _YICAI_SEO_KEYWORDS,
        "ogImageUrl": "https://www.qlyc.co/image/logo.png",
        "robotsTxt": "User-agent: *\nAllow: /\n\nSitemap: https://www.qlyc.co/sitemap.xml\nSitemap: https://www.qlyc.co/sitemap-notices.xml",
        "sitemapUrls": ["https://www.qlyc.co/sitemap.xml", "https://www.qlyc.co/sitemap-notices.xml"],
        "jsonLd": _org_json_ld(
            name="山东壹知产数字科技有限公司",
            alternate="壹采",
            url="https://www.qlyc.co",
            description="专业的政企采购电商服务平台，提供齐鲁云采、框架协议、泉E采等政府采购平台一站式入驻与运营服务。",
        ),
    },
    "yizhichan": {
        "seoTitle": _YICAI_SEO_TITLE,
        "seoDescription": _YICAI_SEO_DESCRIPTION,
        "seoKeywords": _YICAI_SEO_KEYWORDS,
        "ogImageUrl": "https://www.yizhichan.co/image/logo.png",
        "robotsTxt": "User-agent: *\nAllow: /\n\nSitemap: https://www.yizhichan.co/sitemap.xml\nSitemap: https://www.yizhichan.co/sitemap-notices.xml",
        "sitemapUrls": ["https://www.yizhichan.co/sitemap.xml", "https://www.yizhichan.co/sitemap-notices.xml"],
        "jsonLd": _org_json_ld(
            name="山东壹知产数字科技有限公司",
            alternate="壹采",
            url="https://www.yizhichan.co",
            description="专业的政企采购电商服务平台，提供齐鲁云采、框架协议、泉E采等政府采购平台一站式入驻与运营服务。",
        ),
    },
    "jinanyunji": {
        "seoTitle": _YICAI_SEO_TITLE,
        "seoDescription": _YICAI_SEO_DESCRIPTION,
        "seoKeywords": _YICAI_SEO_KEYWORDS,
        "ogImageUrl": "https://www.jinanyunji.com/image/logo.png",
        "robotsTxt": (
            "User-agent: *\nAllow: /\n\n"
            "Sitemap: https://www.jinanyunji.com/sitemap.xml\n"
            "Sitemap: https://www.jinanyunji.com/sitemap-notices.xml"
        ),
        "sitemapUrls": ["https://www.jinanyunji.com/sitemap.xml", "https://www.jinanyunji.com/sitemap-notices.xml"],
        "jsonLd": _org_json_ld(
            name="山东壹知产数字科技有限公司",
            alternate="壹采",
            url="https://www.jinanyunji.com",
            description="专业的政企采购电商服务平台，提供齐鲁云采、框架协议、泉E采等政府采购平台一站式入驻与运营服务。",
        ),
    },
    "qinghuicai": {
        "seoTitle": "青慧采入驻代办 | 青慧采代运营 | 青岛政企阳光采购平台 | 项目商机服务",
        "seoDescription": (
            "青慧采是青岛市政府与京东共建的阳光采购平台。提供青慧采入驻代办、青慧采代运营、青慧采项目商机推送服务，"
            "面向青岛行政事业单位及国企，一站式解决小额零星采购入驻及运营难题。"
        ),
        "seoKeywords": (
            "青慧采,青慧采入驻代办,青慧采代运营,青慧采项目商机,青岛政企阳光采购平台,青岛政府采购,"
            "青岛国企采购,京东政企采购,青岛办公用品采购,小额零星采购,青岛国易采购"
        ),
        "ogImageUrl": "https://www.qinghuicai.cn/image/logo.png",
        "robotsTxt": "User-agent: *\nAllow: /\n\nSitemap: https://www.qinghuicai.cn/sitemap.xml",
        "sitemapUrls": ["https://www.qinghuicai.cn/sitemap.xml"],
        "jsonLd": (
            '{"@context":"https://schema.org","@type":"Organization","name":"青慧采 - 青岛政企阳光采购平台",'
            '"alternateName":["青慧采","青岛阳光采购平台"],"url":"https://www.qinghuicai.cn",'
            '"description":"青慧采是青岛市政府与京东共建的阳光采购平台，提供入驻代办、代运营与项目商机服务。",'
            '"telephone":"0531-86099058","email":"Wangyunlei@yizhichan.co","areaServed":"青岛市"}'
        ),
    },
}

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
        **OFFICIAL_SEO_DEFAULTS["qlyc"],
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
        **OFFICIAL_SEO_DEFAULTS["yizhichan"],
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
        **OFFICIAL_SEO_DEFAULTS["jinanyunji"],
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
        **OFFICIAL_SEO_DEFAULTS["qinghuicai"],
        "status": "启用",
        "homePublished": False,
    },
]


_SEO_FIELDS = (
    "seoTitle",
    "seoDescription",
    "seoKeywords",
    "ogImageUrl",
    "robotsTxt",
    "sitemapUrls",
    "jsonLd",
    "baiduSiteVerification",
    "googleSiteVerification",
)


def public_seo_payload(site_data: dict[str, Any]) -> dict[str, Any]:
    data = site_data or {}
    return {
        "id": data.get("id") or "",
        "key": data.get("key") or "",
        "name": data.get("name") or "",
        "domain": data.get("domain") or "",
        "brand": data.get("brand") or "",
        "seoTitle": data.get("seoTitle") or "",
        "seoDescription": data.get("seoDescription") or "",
        "seoKeywords": data.get("seoKeywords") or "",
        "ogImageUrl": data.get("ogImageUrl") or "",
        "robotsTxt": data.get("robotsTxt") or "",
        "sitemapUrls": _normalize_sitemap_urls(data.get("sitemapUrls")),
        "jsonLd": data.get("jsonLd") or "",
        "baiduSiteVerification": data.get("baiduSiteVerification") or "",
        "googleSiteVerification": data.get("googleSiteVerification") or "",
    }


def apply_official_seo_defaults(*, overwrite: bool = False) -> list[dict[str, Any]]:
    """将原官网静态 SEO 写入站点；默认只填空字段，overwrite=True 时覆盖。"""
    ensure_default_official_sites()
    updated: list[dict[str, Any]] = []
    for site in OfficialSiteRecord.objects.filter(is_deleted=False):
        key = (site.key or site.data.get("key") or "").strip()
        defaults = OFFICIAL_SEO_DEFAULTS.get(key)
        if not defaults:
            continue
        data = dict(site.data or {})
        changed = False
        for field in _SEO_FIELDS:
            current = data.get(field)
            empty = current in (None, "", [], {})
            if overwrite or empty:
                if data.get(field) != defaults.get(field):
                    data[field] = defaults.get(field)
                    changed = True
        if not changed:
            continue
        payload = normalize_site_payload({**data, "id": site.id, "createdAt": data.get("createdAt")})
        for attr, value in site_defaults(payload).items():
            setattr(site, attr, value)
        site.is_deleted = False
        site.deleted_at = None
        site.deleted_by = ""
        site.save()
        updated.append(public_seo_payload(site.data))
    return updated


def ensure_default_official_sites() -> list[OfficialSiteRecord]:
    created_sites: list[OfficialSiteRecord] = []
    for seed in SITE_SEEDS:
        payload = normalize_site_payload(deepcopy(seed))
        existing = OfficialSiteRecord.objects.filter(id=payload["id"]).first()
        if existing and existing.is_deleted:
            # 尊重后台删除，不再自动恢复种子站点。
            continue
        if existing:
            # 已有站点：仅补齐空的 SEO 字段，避免每次 ensure 覆盖运营配置。
            data = dict(existing.data or {})
            changed = False
            for field in _SEO_FIELDS:
                if data.get(field) in (None, "", [], {}) and payload.get(field) not in (None, "", [], {}):
                    data[field] = payload.get(field)
                    changed = True
            if changed:
                merged = normalize_site_payload({**data, "id": existing.id, "createdAt": data.get("createdAt")})
                for attr, value in site_defaults(merged).items():
                    setattr(existing, attr, value)
                existing.save(update_fields=["data", "key", "name", "domain", "brand", "company_name", "phone", "status", "updated_at"])
            site = existing
            created = False
        else:
            site = OfficialSiteRecord.objects.create(
                id=payload["id"],
                **site_defaults(payload),
                is_deleted=False,
                deleted_at=None,
                deleted_by="",
            )
            created = True
        if created:
            created_sites.append(site)

        page_id = f"page-{payload['id']}-home"
        page_existing = OfficialPageRecord.objects.filter(id=page_id).first()
        if page_existing and page_existing.is_deleted:
            continue
        if not page_existing:
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
            OfficialPageRecord.objects.create(
                id=page_id,
                **page_defaults(page_payload),
                is_deleted=False,
                deleted_at=None,
                deleted_by="",
            )
    return created_sites


def find_official_site_by_host(host: str) -> OfficialSiteRecord | None:
    ensure_default_official_sites()
    normalized = normalize_host(host)
    bare = normalized[4:] if normalized.startswith("www.") else normalized
    return (
        OfficialSiteRecord.objects.filter(is_deleted=False, status="启用", domain=normalized).first()
        or OfficialSiteRecord.objects.filter(is_deleted=False, status="启用", domain=f"www.{bare}").first()
        or OfficialSiteRecord.objects.filter(is_deleted=False, status="启用", domain=bare).first()
        or OfficialSiteRecord.objects.filter(is_deleted=False, status="启用", key=bare.split(".")[0]).first()
    )


def resolve_public_site(host: str, slug: str = "home") -> dict | None:
    site = find_official_site_by_host(host)
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
