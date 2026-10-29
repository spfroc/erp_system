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


def bare_host(value: str | None) -> str:
    host = normalize_host(value)
    return host[4:] if host.startswith("www.") else host


def _normalize_domains(value: Any, primary: str = "") -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = re.split(r"[\r\n,]+", value)
    else:
        items = []
    result: list[str] = []
    seen: set[str] = set()
    for raw in items:
        host = normalize_host(raw)
        if not host:
            continue
        key = bare_host(host)
        if key in seen:
            continue
        seen.add(key)
        result.append(host)
    primary_host = normalize_host(primary)
    if primary_host:
        primary_bare = bare_host(primary_host)
        result = [item for item in result if bare_host(item) != primary_bare]
        result.insert(0, primary_host)
    return result


def _text_item(value: Any, *keys: str, default: str = "") -> str:
    if not isinstance(value, dict):
        return default
    for key in keys:
        text = str(value.get(key) or "").strip()
        if text:
            return text
    return default


def _normalize_contact(value: Any, fallback: dict[str, Any] | None = None) -> dict[str, str]:
    src = value if isinstance(value, dict) else {}
    fb = fallback or {}
    file_id = _text_item(src, "wechatQrFileId", "wechat_qr_file_id")
    qr_url = _text_item(src, "wechatQrUrl", "wechat_qr_url")
    if file_id and not qr_url:
        qr_url = f"/api/documents/{file_id}/"
    return {
        "hotline": _text_item(src, "hotline", "phone") or str(fb.get("phone") or fb.get("hotline") or "").strip(),
        "mobile": _text_item(src, "mobile"),
        "wechatQrUrl": qr_url or "/image/wx.png",
        "wechatQrFileId": file_id,
        "email": _text_item(src, "email") or str(fb.get("email") or "").strip(),
        "contactName": _text_item(src, "contactName", "contact_name"),
        "address": _text_item(src, "address") or str(fb.get("address") or "").strip(),
    }


def _normalize_named_list(value: Any, *, name_keys: tuple[str, ...] = ("title", "name", "label")) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, str]] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        title = ""
        for key in name_keys:
            title = str(raw.get(key) or "").strip()
            if title:
                break
        if not title:
            continue
        items.append(
            {
                "title": title,
                "description": str(raw.get("description") or raw.get("text") or "").strip(),
                "icon": str(raw.get("icon") or "").strip(),
                "name": str(raw.get("name") or title).strip(),
                "label": str(raw.get("label") or title).strip(),
                "value": str(raw.get("value") or title).strip(),
                "url": str(raw.get("url") or raw.get("href") or "").strip(),
                "contentHtml": str(raw.get("contentHtml") or raw.get("content") or "").strip(),
            }
        )
    return items


def _normalize_industries(value: Any) -> list[dict[str, str]]:
    return [
        {"title": item["title"], "description": item["description"], "icon": item["icon"]}
        for item in _normalize_named_list(value, name_keys=("title", "name"))
    ]


def _normalize_inquiry_platforms(value: Any) -> list[dict[str, str]]:
    return [
        {"label": item["label"], "value": item["value"]}
        for item in _normalize_named_list(value, name_keys=("label", "name", "title", "value"))
    ]


def _normalize_footer_platforms(value: Any) -> list[dict[str, str]]:
    return [
        {"name": item["name"], "url": item["url"]}
        for item in _normalize_named_list(value, name_keys=("name", "title", "label"))
    ]


def _normalize_footer_services(value: Any) -> list[dict[str, str]]:
    return [
        {"title": item["title"], "contentHtml": item["contentHtml"], "url": item["url"]}
        for item in _normalize_named_list(value, name_keys=("title", "name", "label"))
    ]


def _normalize_footer(value: Any) -> dict[str, Any]:
    src = value if isinstance(value, dict) else {}
    return {
        "platforms": _normalize_footer_platforms(src.get("platforms")),
        "services": _normalize_footer_services(src.get("services")),
        "keywords": str(src.get("keywords") or "").strip(),
    }


def _normalize_beian(value: Any) -> dict[str, str]:
    src = value if isinstance(value, dict) else {}
    return {
        "copyright": _text_item(src, "copyright"),
        "icpText": _text_item(src, "icpText", "icp_text"),
        "icpUrl": _text_item(src, "icpUrl", "icp_url") or "https://beian.miit.gov.cn/#/Integrated/index",
        "telecomLicense": _text_item(src, "telecomLicense", "telecom_license"),
        "policeText": _text_item(src, "policeText", "police_text"),
        "policeUrl": _text_item(src, "policeUrl", "police_url") or "https://beian.mps.gov.cn/#/query/webSearch",
    }


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
        "phone": data.get("phone") or data.get("contact", {}).get("hotline") or "",
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
    contact = _normalize_contact(
        payload.get("contact"),
        {
            "phone": payload.get("phone"),
            "email": payload.get("email"),
            "address": payload.get("address"),
            "hotline": payload.get("phone"),
        },
    )
    domains = _normalize_domains(payload.get("domains"), primary=domain)
    if not domains and domain:
        domains = [domain]
    phone = (payload.get("phone") or "").strip() or contact.get("hotline") or ""
    email = (payload.get("email") or "").strip() or contact.get("email") or ""
    address = (payload.get("address") or "").strip() or contact.get("address") or ""
    return {
        **payload,
        "id": payload.get("id") or f"site-{key}",
        "key": key,
        "name": (payload.get("name") or "").strip() or key,
        "domain": domain or (domains[0] if domains else ""),
        "domains": domains,
        "mirrorKey": (payload.get("mirrorKey") or key).strip() or key,
        "brand": (payload.get("brand") or "").strip(),
        "companyName": (payload.get("companyName") or "").strip(),
        "phone": phone,
        "email": email,
        "address": address,
        "contact": contact,
        "industries": _normalize_industries(payload.get("industries")),
        "inquiryPlatforms": _normalize_inquiry_platforms(payload.get("inquiryPlatforms")),
        "footer": _normalize_footer(payload.get("footer")),
        "beian": _normalize_beian(payload.get("beian")),
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


def public_home_config(site_data: dict[str, Any] | None) -> dict[str, Any]:
    data = normalize_site_payload(dict(site_data or {}))
    return {
        "key": data.get("key") or "",
        "mirrorKey": data.get("mirrorKey") or data.get("key") or "",
        "brand": data.get("brand") or "",
        "companyName": data.get("companyName") or "",
        "domains": list(data.get("domains") or []),
        "contact": data.get("contact") or {},
        "industries": list(data.get("industries") or []),
        "inquiryPlatforms": list(data.get("inquiryPlatforms") or []),
        "footer": data.get("footer") or {"platforms": [], "services": [], "keywords": ""},
        "beian": data.get("beian") or {},
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

_YICAI_CONTACT = {
    "hotline": "0531-86099058",
    "mobile": "13105315957",
    "wechatQrUrl": "/image/wx.png",
    "email": "Wangyunlei@yizhichan.co",
    "contactName": "王老师",
    "address": "济南市市中区大观园街道纬二路49号汇宝大厦2106A",
}

_YICAI_INDUSTRIES = [
    {"title": "办公用品", "description": "笔、纸、文件夹、办公耗材等各类办公用品供应商", "icon": "fa-pencil-alt"},
    {"title": "办公设备", "description": "打印机、复印机、扫描仪等办公设备供应商", "icon": "fa-print"},
    {"title": "IT设备", "description": "计算机、服务器、网络设备等IT设备供应商", "icon": "fa-laptop"},
    {"title": "电器类", "description": "空调、冰箱、电视等家用及商用电器供应商", "icon": "fa-tv"},
    {"title": "生活日用品", "description": "清洁用品、个人护理等生活日用品供应商", "icon": "fa-home"},
    {"title": "五金工具", "description": "手动工具、电动工具、五金配件等供应商", "icon": "fa-tools"},
    {"title": "消防救援", "description": "消防器材、应急救援设备等供应商", "icon": "fa-fire-extinguisher"},
    {"title": "系统集成", "description": "舞台灯光、音响设备、会议系统、安防监控、信息化系统集成等服务供应商", "icon": "fa-server"},
]

_YICAI_INQUIRY_PLATFORMS = [
    {"label": "齐鲁云采", "value": "齐鲁云采"},
    {"label": "框架协议", "value": "框架协议"},
    {"label": "泉E采", "value": "泉E采"},
    {"label": "多个平台", "value": "多个平台"},
]

_YICAI_FOOTER = {
    "platforms": [
        {"name": "泉e采阳光采购平台/泉易采", "url": "https://qyc.zhongcy.cn/login"},
        {"name": "齐鲁云采", "url": "http://ggzyjyzx.shandong.gov.cn:8282/gpmall-main-web/index?regionguid=1487001"},
        {"name": "框架协议", "url": "https://ggzyjyzx.shandong.gov.cn:8182/gpfa-main-web/index?regionguid=1487001"},
        {"name": "济南市公共资源交易中心", "url": "https://jnggzy.jinan.gov.cn/"},
        {"name": "山东省政府采购信息公开平台", "url": "https://www.ccgp-shandong.gov.cn/xxgk"},
    ],
    "services": [
        {"title": "采购公告", "contentHtml": "", "url": "/notices"},
        {"title": "平台入驻服务", "contentHtml": "", "url": "#"},
        {"title": "技术对接服务", "contentHtml": "", "url": "#"},
        {"title": "运营指导服务", "contentHtml": "", "url": "#"},
        {"title": "资源整合服务", "contentHtml": "", "url": "#"},
    ],
    "keywords": "",
}

_YICAI_BEIAN = {
    "copyright": "© 2023-2025 山东壹知产数字科技有限公司 版权所有",
    "icpText": "鲁ICP备2021004355号",
    "icpUrl": "https://beian.miit.gov.cn/#/Integrated/index",
    "telecomLicense": "电信增值业务许可证：鲁B2-20210548",
    "policeText": "鲁公网安备 37010302001675",
    "policeUrl": "https://beian.mps.gov.cn/#/query/webSearch",
}

_QHC_FOOTER = {
    "platforms": [
        {"name": "青岛政企阳光采购平台", "url": "https://qhc.zhongcy.cn/login"},
        {"name": "青岛国易采购", "url": "https://qhc.zhongcy.cn/login"},
        {"name": "青岛市公共资源交易网", "url": "http://ggzy.qingdao.gov.cn"},
        {"name": "齐鲁云采", "url": "http://ggzyjyzx.shandong.gov.cn:8282/gpmall-main-web/index?regionguid=1487001"},
        {"name": "框架协议", "url": "https://ggzyjyzx.shandong.gov.cn:8182/gpfa-main-web/index?regionguid=1487001"},
        {"name": "山东省政府采购信息公开平台", "url": "https://www.ccgp-shandong.gov.cn/xxgk"},
    ],
    "services": [
        {"title": "平台介绍", "contentHtml": "", "url": "#intro"},
        {"title": "入驻条件", "contentHtml": "", "url": "#conditions"},
        {"title": "入驻流程", "contentHtml": "", "url": "#process"},
        {"title": "服务内容", "contentHtml": "", "url": "#services"},
        {"title": "入驻代办/代运营", "contentHtml": "", "url": "#agency-service"},
    ],
    "keywords": "青慧采 | 青慧采入驻代办 | 青慧采代运营 | 青慧采项目商机 | 青岛政企阳光采购平台 | 青岛政府采购 | 青岛国企采购 | 京东政企合作 | 小额零星采购",
}

_QHC_BEIAN = {
    "copyright": "© 2023-2025 山东壹知产数字科技有限公司 版权所有",
    "icpText": "鲁ICP备2021004355号",
    "icpUrl": "https://beian.miit.gov.cn/#/Integrated/index",
    "telecomLicense": "电信增值业务许可证：鲁B2-20210548",
    "policeText": "鲁公网安备 37010302001037",
    "policeUrl": "https://beian.mps.gov.cn/#/query/webSearch",
}

SITE_SEEDS = [
    {
        "id": "site-qlyc",
        "key": "qlyc",
        "name": "壹采官网",
        "domain": "www.qlyc.co",
        "domains": ["www.qlyc.co", "www.yizhichan.co"],
        "mirrorKey": "qlyc",
        "brand": "壹采",
        "companyName": "山东壹知产数字科技有限公司",
        "phone": "0531-86099058",
        "email": "Wangyunlei@yizhichan.co",
        "address": "济南市市中区大观园街道纬二路49号汇宝大厦2106A",
        "contact": _YICAI_CONTACT,
        "industries": _YICAI_INDUSTRIES,
        "inquiryPlatforms": _YICAI_INQUIRY_PLATFORMS,
        "footer": _YICAI_FOOTER,
        "beian": _YICAI_BEIAN,
        "logoUrl": "/image/logo.png",
        "primaryColor": "#0066cc",
        **OFFICIAL_SEO_DEFAULTS["qlyc"],
        "status": "启用",
        "homePublished": True,
    },
    {
        "id": "site-jinanyunji",
        "key": "jinanyunji",
        "name": "济南云集官网",
        "domain": "www.jinanyunji.com",
        "domains": ["www.jinanyunji.com"],
        "mirrorKey": "jinanyunji",
        "brand": "济南云集",
        "companyName": "山东壹知产数字科技有限公司",
        "phone": "0531-86099058",
        "contact": {**_YICAI_CONTACT},
        "industries": list(_YICAI_INDUSTRIES),
        "inquiryPlatforms": [],
        "footer": {"platforms": [], "services": [], "keywords": ""},
        "beian": {**_YICAI_BEIAN},
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
        "domains": ["www.qinghuicai.cn"],
        "mirrorKey": "qinghuicai",
        "brand": "青慧采",
        "companyName": "山东壹知产数字科技有限公司",
        "phone": "0531-86099058",
        "email": "Wangyunlei@yizhichan.co",
        "address": "济南市市中区大观园街道纬二路49号汇宝大厦2106A",
        "contact": {**_YICAI_CONTACT},
        # 青慧采首页无「常见行业」区块，保持空列表。
        "industries": [],
        "inquiryPlatforms": [{"label": "青慧采", "value": "青慧采"}],
        "footer": _QHC_FOOTER,
        "beian": _QHC_BEIAN,
        "primaryColor": "#1f7a4d",
        **OFFICIAL_SEO_DEFAULTS["qinghuicai"],
        "status": "启用",
        "homePublished": True,
    },
]

_HOME_CONFIG_FIELDS = ("domains", "mirrorKey", "contact", "industries", "inquiryPlatforms", "footer", "beian")

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
        "domains": list(data.get("domains") or []),
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


def _is_empty_home_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, dict):
        if not value:
            return True
        # footer/contact/beian: empty if all nested values empty
        return all(_is_empty_home_value(item) for item in value.values())
    return False


def _merge_home_config_defaults(data: dict[str, Any], seed: dict[str, Any]) -> bool:
    changed = False
    for field in _HOME_CONFIG_FIELDS:
        if field not in seed:
            continue
        if _is_empty_home_value(data.get(field)) and not _is_empty_home_value(seed.get(field)):
            data[field] = deepcopy(seed.get(field))
            changed = True
    # Always ensure yizhichan alias on qlyc when missing
    if (data.get("key") or seed.get("key")) == "qlyc":
        domains = _normalize_domains(data.get("domains"), primary=data.get("domain") or seed.get("domain") or "")
        for alias in ("www.yizhichan.co", "yizhichan.co"):
            if bare_host(alias) not in {bare_host(item) for item in domains}:
                domains.append(normalize_host(alias))
                changed = True
        if domains != list(data.get("domains") or []):
            data["domains"] = domains
            changed = True
    return changed


def _retire_legacy_yizhichan_site() -> None:
    """qlyc/yizhichan 共用 site-qlyc；旧 site-yizhichan 软删除避免 host 解析抢占。"""
    from django.utils import timezone as dj_tz

    legacy = OfficialSiteRecord.objects.filter(id="site-yizhichan", is_deleted=False).first()
    if not legacy:
        return
    now = dj_tz.now()
    legacy.is_deleted = True
    legacy.deleted_at = now
    legacy.deleted_by = "system:merge-domains"
    legacy.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])
    page = OfficialPageRecord.objects.filter(id="page-site-yizhichan-home", is_deleted=False).first()
    if page:
        page.is_deleted = True
        page.deleted_at = now
        page.deleted_by = "system:merge-domains"
        page.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])


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
    _retire_legacy_yizhichan_site()
    created_sites: list[OfficialSiteRecord] = []
    for seed in SITE_SEEDS:
        payload = normalize_site_payload(deepcopy(seed))
        existing = OfficialSiteRecord.objects.filter(id=payload["id"]).first()
        if existing and existing.is_deleted:
            # 尊重后台删除，不再自动恢复种子站点。
            continue
        if existing:
            # 已有站点：仅补齐空的 SEO / 首页运营字段，避免覆盖运营配置。
            data = dict(existing.data or {})
            changed = False
            for field in _SEO_FIELDS:
                if data.get(field) in (None, "", [], {}) and payload.get(field) not in (None, "", [], {}):
                    data[field] = payload.get(field)
                    changed = True
            if _merge_home_config_defaults(data, seed):
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
        elif payload["key"] == "qinghuicai" and page_existing.status != "published" and seed.get("homePublished"):
            # 青慧采首页纳入运营配置后默认发布，便于公开 API 返回 homeConfig 配套 page
            page_existing.status = "published"
            data = dict(page_existing.data or {})
            data["status"] = "published"
            page_existing.data = data
            page_existing.save(update_fields=["status", "data", "updated_at"])
    return created_sites


def _site_matches_host(site: OfficialSiteRecord, bare: str) -> bool:
    if bare_host(site.domain) == bare:
        return True
    data = site.data or {}
    for item in data.get("domains") or []:
        if bare_host(item) == bare:
            return True
    return False


def find_official_site_by_host(host: str) -> OfficialSiteRecord | None:
    ensure_default_official_sites()
    normalized = normalize_host(host)
    bare = bare_host(normalized)
    if not bare:
        return None
    # Prefer explicit domain column matches, then domains[] aliases.
    for candidate in (normalized, f"www.{bare}", bare):
        site = OfficialSiteRecord.objects.filter(is_deleted=False, status="启用", domain=candidate).first()
        if site:
            return site
    for site in OfficialSiteRecord.objects.filter(is_deleted=False, status="启用").iterator():
        if _site_matches_host(site, bare):
            return site
    key = bare.split(".")[0]
    return OfficialSiteRecord.objects.filter(is_deleted=False, status="启用", key=key).first()


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
    site_data = site.data or {}
    return {
        "site": site_data,
        "page": page.data if page else None,
        "homeConfig": public_home_config(site_data),
    }