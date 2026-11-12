import http from "node:http";
import {
  absoluteUrl,
  buildMetaTags,
  escapeAttr,
  escapeHtml,
  fetchOfficialSeo,
  formatDate,
  getSiteSeo,
  jsonLdScript,
  money,
  requestOrigin,
  splitSeoKeywords,
  truncateText,
} from "./seo.mjs";

const PAGE_SIZE = 10;
const FETCH_TIMEOUT_MS = 12000;

function fetchJson(pathnameWithQuery) {
  const backend = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const target = new URL(pathnameWithQuery, `${backend}/`);
  return new Promise((resolve, reject) => {
    const req = http.request(
      target,
      {
        method: "GET",
        headers: {
          accept: "application/json",
          "user-agent": "official-web-ssr",
          host: process.env.BACKEND_HTTP_HOST || target.host,
        },
        timeout: FETCH_TIMEOUT_MS,
      },
      (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          let body = {};
          try {
            body = text ? JSON.parse(text) : {};
          } catch {
            body = { detail: text.slice(0, 200) };
          }
          if ((res.statusCode || 500) >= 400) {
            reject(new Error(body.detail || `HTTP ${res.statusCode}`));
            return;
          }
          resolve(body);
        });
      },
    );
    req.on("timeout", () => req.destroy(new Error("Upstream timeout")));
    req.on("error", reject);
    req.end();
  });
}

export async function fetchNoticeList({ page = 1, search = "", kind = "" } = {}) {
  const params = new URLSearchParams({
    page: String(Math.max(1, Number(page) || 1)),
    page_size: String(PAGE_SIZE),
  });
  if (search) params.set("search", search);
  if (kind && kind !== "全部") params.set("noticeKind", kind);
  return fetchJson(`/api/public/notices/?${params.toString()}`);
}

export async function fetchNoticeDetail(id) {
  const body = await fetchJson(`/api/public/notices/${encodeURIComponent(id)}/`);
  return body.data || null;
}

export async function fetchAllPublicNoticeIds(limit = 500) {
  const items = [];
  let page = 1;
  while (items.length < limit) {
    const payload = await fetchNoticeList({ page, search: "", kind: "" });
    const batch = payload.items || [];
    if (!batch.length) break;
    items.push(...batch);
    const total = Number(payload.total || 0);
    if (items.length >= total || batch.length < PAGE_SIZE) break;
    page += 1;
    if (page > 50) break;
  }
  return items.slice(0, limit);
}

function listUrl({ page = 1, kind = "", search = "" } = {}) {
  const params = new URLSearchParams();
  if (page > 1) params.set("page", String(page));
  if (kind && kind !== "全部") params.set("kind", kind);
  if (search) params.set("search", search);
  const qs = params.toString();
  return qs ? `/notices?${qs}` : "/notices";
}

function detailUrl(id) {
  return `/notices/${encodeURIComponent(id)}`;
}

function renderFilters(kinds, active, { search = "" } = {}) {
  const items = ["全部"].concat(kinds || []);
  return items
    .map((kind) => {
      const href = listUrl({ page: 1, kind, search });
      const current = active || "全部";
      const cls = kind === current ? "active" : "";
      return `<a class="notice-filter ${cls}" href="${escapeAttr(href)}" data-kind="${escapeAttr(kind)}">${escapeHtml(kind)}</a>`;
    })
    .join("");
}

function renderListItems(items) {
  if (!items.length) return "";
  return items
    .map(
      (item) =>
        `<a class="notice-item" href="${escapeAttr(detailUrl(item.id))}">` +
        "<div>" +
        `<h2>${escapeHtml(item.title || "未命名公告")}</h2>` +
        '<div class="meta">' +
        `<span>项目编号 ${escapeHtml(item.projectNumber || "—")}</span>` +
        `<span>${escapeHtml(item.department || "—")}</span>` +
        `<span>${escapeHtml(formatDate(item.publishedAt) || "—")}</span>` +
        `<span>${escapeHtml(money(item.amount))}</span>` +
        "</div></div>" +
        `<span class="kind">${escapeHtml(item.noticeKind || "公告")}</span>` +
        "</a>",
    )
    .join("");
}

function renderPager({ page, total, pageSize, kind, search }) {
  const totalPages = Math.max(1, Math.ceil((total || 0) / (pageSize || PAGE_SIZE)));
  const prev = page > 1 ? listUrl({ page: page - 1, kind, search }) : "";
  const next = page < totalPages ? listUrl({ page: page + 1, kind, search }) : "";
  return (
    (prev
      ? `<a class="pager-link" href="${escapeAttr(prev)}" rel="prev">上一页</a>`
      : `<span class="pager-link disabled">上一页</span>`) +
    `<strong>${page} / ${totalPages}（共 ${total || 0} 条）</strong>` +
    (next
      ? `<a class="pager-link" href="${escapeAttr(next)}" rel="next">下一页</a>`
      : `<span class="pager-link disabled">下一页</span>`)
  );
}

function maskSensitive(value) {
  const text = String(value == null ? "" : value).trim();
  if (!text || text === "—") return "—";
  if (text.length <= 2) return "**";
  return `${text.slice(0, 1)}***`;
}

function renderDetailArticle(item, { masked = true } = {}) {
  // SSR 默认按未登录遮蔽关键字段，避免闪出明文后再被客户端打码
  const buyer = masked ? maskSensitive(item.department || item.buyerName || "—") : item.department || item.buyerName || "—";
  const project = masked
    ? maskSensitive(item.projectNumber || item.projectCode || "—")
    : item.projectNumber || item.projectCode || "—";
  const amount = masked ? "登录可见" : money(item.amount || item.budgetAmount || item.dealAmount);
  const contact = masked ? "登录可见" : [item.contactName, item.contactPhone].filter(Boolean).join(" ") || "—";
  return (
    `<h1>${escapeHtml(item.title || "未命名公告")}</h1>` +
    `<p class="muted">${escapeHtml([item.siteLabel, item.noticeKind, formatDate(item.publishedAt)].filter(Boolean).join(" · "))}</p>` +
    '<div class="notice-detail-grid">' +
    `<div><span>采购单位</span><strong>${escapeHtml(buyer)}</strong></div>` +
    `<div><span>项目编号</span><strong>${escapeHtml(project)}</strong></div>` +
    `<div><span>区域</span><strong>${escapeHtml(item.regionName || "—")}</strong></div>` +
    `<div><span>金额</span><strong>${escapeHtml(amount)}</strong></div>` +
    `<div><span>进度</span><strong>${escapeHtml(item.progressLabel || item.bidStatus || "—")}</strong></div>` +
    `<div><span>联系人</span><strong>${escapeHtml(contact)}</strong></div>` +
    "</div>" +
    (masked
      ? '<div class="detail-content is-masked"><p>正文与关键信息已隐藏，登录后可查看完整公告。</p><p><a class="btn" href="/portal/?from=site">会员登录</a></p></div>'
      : item.content
        ? `<div class="detail-content">${escapeHtml(item.content)}</div>`
        : "") +
    '<div class="detail-actions">' +
    '<a class="btn secondary" href="/notices">返回壹采寻源</a>' +
    (masked
      ? '<a class="btn" href="/portal/?from=site">登录后查看原文</a>'
      : item.detailUrl || item.sourceUrl
        ? `<a class="btn" href="${escapeAttr(item.detailUrl || item.sourceUrl)}" target="_blank" rel="noreferrer">打开原文</a>`
        : "") +
    "</div>"
  );
}

function replaceHeadMeta(html, metaHtml, jsonLd = "") {
  let next = html.replace(/<title>[\s\S]*?<\/title>/i, "");
  next = next.replace(/<meta\s+name=["']description["'][^>]*>\s*/i, "");
  next = next.replace(/<\/head>/i, `  ${metaHtml}\n  ${jsonLd}\n</head>`);
  return next;
}

function setBodyAttr(html, name, value) {
  return html.replace(/<body([^>]*)>/i, (match, attrs) => {
    if (new RegExp(`\\s${name}=`).test(attrs)) {
      return `<body${attrs.replace(new RegExp(`${name}=["'][^"']*["']`), `${name}="${escapeAttr(value)}"`)}>`;
    }
    return `<body${attrs} ${name}="${escapeAttr(value)}">`;
  });
}

function replaceInnerById(html, id, inner, { hidden = null } = {}) {
  const re = new RegExp(`(<[^>]*\\bid=["']${id}["'][^>]*)(>)([\\s\\S]*?)(</[^>]+>)`, "i");
  return html.replace(re, (_, open, gt, _old, close) => {
    let tagOpen = open;
    if (hidden === true && !/\bhidden\b/i.test(tagOpen)) tagOpen += " hidden";
    if (hidden === false) tagOpen = tagOpen.replace(/\shidden\b/i, "");
    return `${tagOpen}${gt}${inner}${close}`;
  });
}

function safeJsonLd(value) {
  if (!value) return null;
  if (typeof value === "object") return value;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

export async function renderNoticeListPage({ req, siteKey, shellHtml, query }) {
  const host = String(req.headers["x-forwarded-host"] || req.headers.host || "").split(",")[0].trim();
  const remoteSeo = await fetchOfficialSeo(host);
  const seo = getSiteSeo(siteKey, remoteSeo);
  const origin = requestOrigin(req, siteKey);
  const page = Math.max(1, Number(query.page || 1) || 1);
  const kind = String(query.kind || query.noticeKind || "全部");
  const search = String(query.search || "").trim();

  let payload = { items: [], total: 0, page, page_size: PAGE_SIZE, kinds: [] };
  let errorMessage = "";
  try {
    payload = await fetchNoticeList({ page, search, kind });
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : "公告加载失败";
  }

  const items = payload.items || [];
  const title =
    kind && kind !== "全部"
      ? `${kind} | 壹采寻源 | ${seo.siteName}`
      : search
        ? `搜索「${search}」| 壹采寻源 | ${seo.siteName}`
        : `壹采寻源 | 商机大厅 公告大厅 采购意向 | ${seo.siteName}`;
  const description = truncateText(
    search
      ? `${seo.brand}壹采寻源搜索：${search}`
      : items.length
        ? `${seo.description} 最新：${items.map((item) => item.title).filter(Boolean).slice(0, 3).join("；")}`
        : `${seo.description} 壹采寻源汇聚商机大厅、公告大厅与采购意向。`,
  );
  const canonical = absoluteUrl(origin, listUrl({ page, kind, search }));
  const keywords = splitSeoKeywords(
    "壹采寻源",
    "商机大厅",
    "公告大厅",
    "采购意向",
    kind && kind !== "全部" ? kind : "",
    search,
    seo.keywords || "",
    seo.brand,
    seo.geoPlacename,
  );
  const meta = buildMetaTags({
    title,
    description,
    canonical,
    ogType: "website",
    keywords,
    ogImageUrl: seo.ogImageUrl || "",
    baiduSiteVerification: seo.baiduSiteVerification || "",
    googleSiteVerification: seo.googleSiteVerification || "",
    geoRegion: seo.geoRegion || "",
    geoPlacename: seo.geoPlacename || "",
    geoPosition: seo.geoPosition || "",
  });
  const listJsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: title,
    description,
    url: canonical,
    isPartOf: { "@type": "WebSite", name: seo.siteName, url: origin },
    mainEntity: {
      "@type": "ItemList",
      numberOfItems: payload.total || items.length,
      itemListElement: items.map((item, index) => ({
        "@type": "ListItem",
        position: (page - 1) * PAGE_SIZE + index + 1,
        url: absoluteUrl(origin, detailUrl(item.id)),
        name: item.title || "采购公告",
      })),
    },
  };
  const jsonLd = [jsonLdScript(listJsonLd), seo.jsonLd ? jsonLdScript(safeJsonLd(seo.jsonLd)) : ""].filter(Boolean).join("\n  ");

  let html = shellHtml;
  html = replaceHeadMeta(html, meta, jsonLd);
  html = setBodyAttr(html, "data-page", "notice-list");
  html = setBodyAttr(html, "data-ssr", "1");
  const isSourcingShell = /id=["']sourcing-root["']|id=["']sourcing-tabs["']/i.test(shellHtml);
  // 壹采寻源壳页由前端渲染卡片列表，SSR 只注入 SEO，避免旧列表闪一下被覆盖
  if (isSourcingShell) {
    html = replaceInnerById(html, "notice-loading", "加载中...", { hidden: false });
    html = replaceInnerById(html, "notice-list", "");
    html = replaceInnerById(html, "notice-empty", "暂无公告", { hidden: true });
    html = replaceInnerById(html, "notice-pager", "");
  } else {
    html = replaceInnerById(html, "notice-filters", renderFilters(payload.kinds || [], kind, { search }));
    html = replaceInnerById(html, "notice-loading", "", { hidden: true });
    if (errorMessage) {
      html = replaceInnerById(html, "notice-list", "");
      html = replaceInnerById(html, "notice-empty", `公告加载失败：${escapeHtml(errorMessage)}`, { hidden: false });
      html = replaceInnerById(html, "notice-pager", "");
    } else if (!items.length) {
      html = replaceInnerById(html, "notice-list", "");
      html = replaceInnerById(html, "notice-empty", "暂无公开公告", { hidden: false });
      html = replaceInnerById(html, "notice-pager", "");
    } else {
      html = replaceInnerById(html, "notice-list", renderListItems(items));
      html = replaceInnerById(html, "notice-empty", "暂无公开公告", { hidden: true });
      html = replaceInnerById(
        html,
        "notice-pager",
        renderPager({
          page: payload.page || page,
          total: payload.total || 0,
          pageSize: payload.page_size || PAGE_SIZE,
          kind,
          search,
        }),
      );
    }
  }

  if (search) {
    html = html.replace(
      /(<input[^>]*\bid=["']notice-search["'][^>]*)(>)/i,
      (_, open, gt) => `${open.replace(/\svalue=["'][^"']*["']/i, "")} value="${escapeAttr(search)}"${gt}`,
    );
  }

  return { status: errorMessage ? 503 : 200, html, canonical };
}

export async function renderNoticeDetailPage({ req, siteKey, shellHtml, id }) {
  const host = String(req.headers["x-forwarded-host"] || req.headers.host || "").split(",")[0].trim();
  const remoteSeo = await fetchOfficialSeo(host);
  const seo = getSiteSeo(siteKey, remoteSeo);
  const origin = requestOrigin(req, siteKey);

  let item = null;
  let errorMessage = "";
  try {
    item = await fetchNoticeDetail(id);
    if (!item) errorMessage = "公告不存在或未公开";
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : "公告加载失败";
  }

  if (!item) {
    const title = `公告未找到 | ${seo.siteName}`;
    const description = seo.description;
    const canonical = absoluteUrl(origin, `/notices/${encodeURIComponent(id)}`);
    const meta = buildMetaTags({ title, description, canonical });
    let html = replaceHeadMeta(shellHtml, meta);
    html = setBodyAttr(html, "data-page", "notice-detail");
    html = setBodyAttr(html, "data-ssr", "1");
    html = replaceInnerById(
      html,
      "notice-detail",
      `<h1>公告未找到</h1><p>${escapeHtml(errorMessage)}</p><div class="detail-actions"><a class="btn secondary" href="/notices">返回公告列表</a></div>`,
    );
    return { status: 404, html, canonical };
  }

  const title = `${item.title || "公告详情"} | 壹采寻源 | ${seo.brand}`;
  const description = truncateText(
    `${item.noticeKind || "采购公告"} ${item.regionName || ""} ${item.title || ""}`.trim() || seo.description,
  );
  const canonical = absoluteUrl(origin, detailUrl(item.id));
  const place = item.regionName || seo.geoPlacename || "";
  const keywords = splitSeoKeywords(
    item.title,
    item.noticeKind,
    item.procurementMode,
    item.regionName,
    item.projectNumber || item.projectCode,
    "壹采寻源",
    seo.brand,
    seo.keywords || "",
    place,
  );
  const meta = buildMetaTags({
    title,
    description,
    canonical,
    ogType: "article",
    publishedTime: item.publishedAt || "",
    keywords,
    ogImageUrl: seo.ogImageUrl || "",
    baiduSiteVerification: seo.baiduSiteVerification || "",
    googleSiteVerification: seo.googleSiteVerification || "",
    geoRegion: seo.geoRegion || "",
    geoPlacename: place || seo.geoPlacename || "",
    geoPosition: seo.geoPosition || "",
  });
  const articleJsonLd = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: item.title || "采购公告",
    description,
    datePublished: item.publishedAt || undefined,
    mainEntityOfPage: canonical,
    author: { "@type": "Organization", name: item.publisher || seo.brand },
    publisher: { "@type": "Organization", name: seo.siteName },
  };
  const org = safeJsonLd(seo.jsonLd);
  const jsonLd = [jsonLdScript(articleJsonLd), org ? jsonLdScript(org) : ""].filter(Boolean).join("\n  ");

  let html = replaceHeadMeta(shellHtml, meta, jsonLd);
  html = setBodyAttr(html, "data-page", "notice-detail");
  html = setBodyAttr(html, "data-ssr", "1");
  // 页面顶栏保留「公告详情」提示，正文唯一 h1 在 article 内，避免重复标题伤害 SEO。
  html = html.replace(/<section class="page-hero">[\s\S]*?<\/section>/i, (block) =>
    block.replace(/<h1>\s*公告详情\s*<\/h1>/i, "<p class=\"hero-kicker\">公告详情</p>"),
  );
  html = replaceInnerById(html, "notice-detail", renderDetailArticle(item, { masked: true }));
  html = html.replace(
    /(<article[^>]*\bid=["']notice-detail["'][^>]*)(>)/i,
    (_, open, gt) => `${open}${/\bdata-ssr-ready=/.test(open) ? "" : ' data-ssr-ready="1"'}${gt}`,
  );
  return { status: 200, html, canonical };
}

export function renderNoticesSitemapXml({ origin, items }) {
  const urls = [
    {
      loc: absoluteUrl(origin, "/notices"),
      lastmod: new Date().toISOString().slice(0, 10),
      changefreq: "hourly",
      priority: "0.9",
    },
    ...items.map((item) => ({
      loc: absoluteUrl(origin, detailUrl(item.id)),
      lastmod: formatDate(item.publishedAt) || new Date().toISOString().slice(0, 10),
      changefreq: "weekly",
      priority: "0.7",
    })),
  ];
  const body = urls
    .map(
      (row) =>
        "  <url>\n" +
        `    <loc>${escapeHtml(row.loc)}</loc>\n` +
        `    <lastmod>${escapeHtml(row.lastmod)}</lastmod>\n` +
        `    <changefreq>${row.changefreq}</changefreq>\n` +
        `    <priority>${row.priority}</priority>\n` +
        "  </url>",
    )
    .join("\n");
  return (
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    `${body}\n` +
    "</urlset>\n"
  );
}
