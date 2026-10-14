import http from "node:http";

const SITE_SEO = {
  qlyc: {
    brand: "壹采",
    siteName: "壹采政企采购电商服务平台",
    description: "壹采公开采购公告、意向公开、竞价项目与结果公告，了解山东省政府采购相关信息。",
    canonicalOrigin: "https://www.qlyc.co",
  },
  yizhichan: {
    brand: "壹采",
    siteName: "壹采政企采购电商服务平台",
    description: "壹采公开采购公告、意向公开、竞价项目与结果公告，了解山东省政府采购相关信息。",
    canonicalOrigin: "https://www.yizhichan.co",
  },
  jinanyunji: {
    brand: "济南云济",
    siteName: "济南云济政企采购服务平台",
    description: "济南云济公开采购公告、意向公开、竞价项目与结果公告。",
    canonicalOrigin: "https://www.jinanyunji.com",
  },
  qinghuicai: {
    brand: "青慧采",
    siteName: "青慧采政企采购服务平台",
    description: "青慧采公开采购公告与政企采购服务信息。",
    canonicalOrigin: "https://www.qinghuicai.cn",
  },
};

const seoCache = new Map();
const SEO_CACHE_TTL_MS = 60_000;

export function getSiteSeo(siteKey, remote = null) {
  const base = SITE_SEO[siteKey] || SITE_SEO.qlyc;
  if (!remote) return base;
  return {
    ...base,
    brand: remote.brand || base.brand,
    description: remote.seoDescription || base.description,
    homeTitle: remote.seoTitle || "",
    keywords: remote.seoKeywords || "",
    ogImageUrl: remote.ogImageUrl || "",
    robotsTxt: remote.robotsTxt || "",
    sitemapUrls: Array.isArray(remote.sitemapUrls) ? remote.sitemapUrls : [],
    jsonLd: remote.jsonLd || "",
    baiduSiteVerification: remote.baiduSiteVerification || "",
    googleSiteVerification: remote.googleSiteVerification || "",
    canonicalOrigin: remote.domain
      ? `https://${String(remote.domain).replace(/^https?:\/\//, "").replace(/\/$/, "")}`
      : base.canonicalOrigin,
  };
}

export function fetchOfficialSeo(host) {
  const cacheKey = String(host || "").toLowerCase();
  const hit = seoCache.get(cacheKey);
  if (hit && Date.now() - hit.at < SEO_CACHE_TTL_MS) {
    return Promise.resolve(hit.data);
  }
  const backend = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const target = new URL(`/api/public/official-seo/?host=${encodeURIComponent(host || "")}`, `${backend}/`);
  return new Promise((resolve) => {
    const req = http.request(
      target,
      {
        method: "GET",
        headers: { accept: "application/json", "user-agent": "official-web-seo", host: target.host },
        timeout: 8000,
      },
      (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          try {
            const body = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
            const data = res.statusCode && res.statusCode < 400 ? body.data || null : null;
            if (data) seoCache.set(cacheKey, { at: Date.now(), data });
            resolve(data);
          } catch {
            resolve(null);
          }
        });
      },
    );
    req.on("timeout", () => {
      req.destroy();
      resolve(null);
    });
    req.on("error", () => resolve(null));
    req.end();
  });
}

export function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

export function absoluteUrl(origin, pathname) {
  const base = String(origin || "").replace(/\/$/, "");
  const path = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return `${base}${path}`;
}

export function requestOrigin(req, siteKey) {
  const seo = getSiteSeo(siteKey);
  const host = String(req.headers["x-forwarded-host"] || req.headers.host || "")
    .split(",")[0]
    .trim()
    .toLowerCase();
  const proto = String(req.headers["x-forwarded-proto"] || "http").split(",")[0].trim();
  if (!host || /^(localhost|127\.0\.0\.1|182\.168\.|192\.168\.|10\.)/i.test(host)) {
    return seo.canonicalOrigin;
  }
  if (host.includes("qlyc.co") || host.includes("yizhichan.co") || host.includes("jinanyunji.com") || host.includes("qinghuicai.cn")) {
    return `${proto === "https" ? "https" : "http"}://${host.split(":")[0]}`;
  }
  return seo.canonicalOrigin;
}

export function truncateText(value, max = 160) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

export function formatDate(value) {
  if (!value) return "";
  const text = String(value);
  return text.length >= 10 ? text.slice(0, 10) : text;
}

export function money(value) {
  if (value == null || value === "" || Number.isNaN(Number(value))) return "—";
  try {
    return new Intl.NumberFormat("zh-CN", {
      style: "currency",
      currency: "CNY",
      maximumFractionDigits: 2,
    }).format(Number(value));
  } catch {
    return String(value);
  }
}

export function buildMetaTags({
  title,
  description,
  canonical,
  ogType = "website",
  publishedTime = "",
  keywords = "",
  ogImageUrl = "",
  baiduSiteVerification = "",
  googleSiteVerification = "",
}) {
  const lines = [
    `<title>${escapeHtml(title)}</title>`,
    `<meta name="description" content="${escapeAttr(description)}" />`,
    keywords ? `<meta name="keywords" content="${escapeAttr(keywords)}" />` : "",
    `<link rel="canonical" href="${escapeAttr(canonical)}" />`,
    `<meta property="og:type" content="${escapeAttr(ogType)}" />`,
    `<meta property="og:title" content="${escapeAttr(title)}" />`,
    `<meta property="og:description" content="${escapeAttr(description)}" />`,
    `<meta property="og:url" content="${escapeAttr(canonical)}" />`,
    ogImageUrl ? `<meta property="og:image" content="${escapeAttr(ogImageUrl)}" />` : "",
    `<meta property="og:locale" content="zh_CN" />`,
    `<meta name="twitter:card" content="summary" />`,
    `<meta name="twitter:title" content="${escapeAttr(title)}" />`,
    `<meta name="twitter:description" content="${escapeAttr(description)}" />`,
    `<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large" />`,
    baiduSiteVerification ? `<meta name="baidu-site-verification" content="${escapeAttr(baiduSiteVerification)}" />` : "",
    googleSiteVerification ? `<meta name="google-site-verification" content="${escapeAttr(googleSiteVerification)}" />` : "",
  ].filter(Boolean);
  if (publishedTime) {
    lines.push(`<meta property="article:published_time" content="${escapeAttr(publishedTime)}" />`);
  }
  return lines.join("\n  ");
}

export function jsonLdScript(data) {
  return `<script type="application/ld+json">${JSON.stringify(data).replace(/</g, "\\u003c")}</script>`;
}
