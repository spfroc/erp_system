import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  fetchAllPublicNoticeIds,
  renderNoticeDetailPage,
  renderNoticeListPage,
  renderNoticesSitemapXml,
} from "./lib/notices-ssr.mjs";
import { fetchOfficialHomeConfig, injectHomeConfigIntoHtml } from "./lib/home-config.mjs";
import { fetchOfficialSeo, getSiteSeo, requestOrigin } from "./lib/seo.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 5180);
const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const DEFAULT_SITE_KEY = process.env.DEFAULT_SITE_KEY || "qlyc";
const PROXY_TIMEOUT_MS = Number(process.env.PROXY_TIMEOUT_MS || 15000);

const HOST_TO_SITE = {
  "www.qlyc.co": "qlyc",
  "qlyc.co": "qlyc",
  "www.yizhichan.co": "yizhichan",
  "yizhichan.co": "yizhichan",
  "www.jinanyunji.com": "jinanyunji",
  "jinanyunji.com": "jinanyunji",
  "www.qinghuicai.cn": "qinghuicai",
  "qinghuicai.cn": "qinghuicai",
  "preview.qlyc.co": "qlyc",
  "yizhichan.qlyc.co": "yizhichan",
  "preview.qinghuicai.cn": "qinghuicai",
  "portal.qlyc.co": "portal",
};

const PREVIEW_CONFIG_HOST = {
  "preview.qlyc.co": "www.qlyc.co",
  "yizhichan.qlyc.co": "www.yizhichan.co",
  "preview.qinghuicai.cn": "www.qinghuicai.cn",
};

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".mjs": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
  ".xml": "application/xml; charset=utf-8",
  ".map": "application/json; charset=utf-8",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".eot": "application/vnd.ms-fontobject",
  ".otf": "font/otf",
  ".pdf": "application/pdf",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};

function normalizeHost(value) {
  let host = String(value || "").trim().toLowerCase();
  if (!host) return "";
  if (host.includes("://")) host = host.split("://", 2)[1];
  host = host.split("/", 1)[0];
  host = host.split(":", 1)[0];
  return host;
}

function resolveSiteKey(req, url) {
  const queryHost = url.searchParams.get("host");
  const querySite = url.searchParams.get("site");
  if (querySite && fs.existsSync(path.join(__dirname, "sites", querySite))) return querySite;
  const candidates = [
    queryHost,
    req.headers["x-forwarded-host"],
    req.headers.host,
  ];
  for (const raw of candidates) {
    if (!raw) continue;
    const host = normalizeHost(String(raw).split(",")[0]);
    // IP / localhost 预览时不要把 182.168.1.120 解析成 sites/182
    if (!host || /^(localhost|127\.0\.0\.1)$/i.test(host) || /^\d{1,3}(\.\d{1,3}){3}$/.test(host)) continue;
    if (HOST_TO_SITE[host]) return HOST_TO_SITE[host];
    const bare = host.startsWith("www.") ? host.slice(4) : host;
    if (HOST_TO_SITE[bare]) return HOST_TO_SITE[bare];
    if (HOST_TO_SITE[`www.${bare}`]) return HOST_TO_SITE[`www.${bare}`];
    const key = bare.split(".")[0];
    if (key && fs.existsSync(path.join(__dirname, "sites", key))) return key;
  }
  return DEFAULT_SITE_KEY;
}

function siteRoot(siteKey) {
  return path.join(__dirname, "sites", siteKey);
}

function safeJoin(root, urlPath) {
  const decoded = decodeURIComponent(urlPath.split("?")[0] || "/");
  const relative = decoded.replace(/^\/+/, "");
  const full = path.normalize(path.join(root, relative));
  if (!full.startsWith(root)) return null;
  return full;
}

function contentType(filePath) {
  return MIME[path.extname(filePath).toLowerCase()] || "application/octet-stream";
}

function sendFile(res, filePath) {
  res.writeHead(200, {
    "Content-Type": contentType(filePath),
    "Cache-Control": filePath.endsWith(".html") ? "no-store" : "public, max-age=3600",
  });
  fs.createReadStream(filePath).pipe(res);
}

function sendText(res, status, text, type = "text/plain; charset=utf-8", extraHeaders = {}) {
  if (res.headersSent) return;
  res.writeHead(status, { "Content-Type": type, ...extraHeaders });
  res.end(text);
}

function sendJson(res, status, payload) {
  sendText(res, status, JSON.stringify(payload), "application/json; charset=utf-8");
}

function sendHtml(res, status, html) {
  sendText(res, status, html, "text/html; charset=utf-8", {
    "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
  });
}

function redirect(res, location, status = 301) {
  res.writeHead(status, { Location: location, "Cache-Control": "no-store" });
  res.end();
}

function readSiteShell(root, name) {
  const filePath = path.join(root, name);
  if (!fs.existsSync(filePath)) return null;
  return fs.readFileSync(filePath, "utf8");
}

function proxyApi(req, res, url) {
  const target = new URL(url.pathname + url.search, BACKEND_URL);
  const method = (req.method || "GET").toUpperCase();
  const headers = {
    accept: req.headers.accept || "application/json",
    "user-agent": req.headers["user-agent"] || "official-web",
    host: process.env.BACKEND_HTTP_HOST || target.host,
  };
  if (req.headers["content-type"]) headers["content-type"] = req.headers["content-type"];
  if (req.headers.cookie) headers.cookie = req.headers.cookie;
  if (req.headers["content-length"] && method !== "GET" && method !== "HEAD") {
    headers["content-length"] = req.headers["content-length"];
  }

  const upstreamReq = http.request(
    target,
    {
      method,
      headers,
      timeout: PROXY_TIMEOUT_MS,
    },
    (upstreamRes) => {
      const responseHeaders = {
        "Content-Type": upstreamRes.headers["content-type"] || "application/json; charset=utf-8",
        "Cache-Control": "no-store",
      };
      if (upstreamRes.headers["set-cookie"]) responseHeaders["set-cookie"] = upstreamRes.headers["set-cookie"];
      res.writeHead(upstreamRes.statusCode || 502, responseHeaders);
      upstreamRes.pipe(res);
    },
  );

  upstreamReq.on("timeout", () => {
    upstreamReq.destroy(new Error("Upstream timeout"));
  });
  upstreamReq.on("error", (error) => {
    if (res.headersSent) {
      res.destroy(error);
      return;
    }
    sendJson(res, 502, { detail: error.message || "Bad gateway" });
  });

  if (method === "GET" || method === "HEAD") {
    req.resume();
    upstreamReq.end();
    return;
  }
  req.pipe(upstreamReq);
}

function resolveStaticFile(root, pathname) {
  let filePath = safeJoin(root, pathname === "/" ? "/index.html" : pathname);
  if (!filePath) return null;
  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, "index.html");
  }
  if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    const htmlPath = `${filePath}.html`;
    if (fs.existsSync(htmlPath) && fs.statSync(htmlPath).isFile()) return htmlPath;
    return null;
  }
  return filePath;
}

function parseNoticeDetailId(pathname) {
  const match = pathname.match(/^\/notices\/([^/]+)\/?$/);
  if (!match) return "";
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

async function handleRobotsTxt(req, res, siteKey, root) {
  const requestHost = normalizeHost(req.headers["x-forwarded-host"] || req.headers.host || "");
  try {
    const remote = await fetchOfficialSeo(PREVIEW_CONFIG_HOST[requestHost] || requestHost);
    const seo = getSiteSeo(siteKey, remote);
    if (seo.robotsTxt) {
      sendText(res, 200, `${seo.robotsTxt}\n`, "text/plain; charset=utf-8", {
        "Cache-Control": "public, max-age=300",
      });
      return true;
    }
  } catch {
    // fall through to static file
  }
  const filePath = path.join(root, "robots.txt");
  if (fs.existsSync(filePath)) {
    sendFile(res, filePath);
    return true;
  }
  sendText(res, 200, "User-agent: *\nAllow: /\n", "text/plain; charset=utf-8");
  return true;
}

async function handleNoticeRoutes(req, res, url, siteKey, root) {
  const pathname = url.pathname;

  if (pathname === "/sitemap-notices.xml") {
    try {
      const origin = requestOrigin(req, siteKey);
      const items = await fetchAllPublicNoticeIds(500);
      const xml = renderNoticesSitemapXml({ origin, items });
      sendText(res, 200, xml, "application/xml; charset=utf-8", {
        "Cache-Control": "public, max-age=300",
      });
    } catch (error) {
      sendText(res, 502, error instanceof Error ? error.message : "sitemap error");
    }
    return true;
  }

  if (pathname === "/notice-detail.html") {
    const id = url.searchParams.get("id") || "";
    if (id) {
      redirect(res, `/notices/${encodeURIComponent(id)}${url.hash || ""}`, 301);
      return true;
    }
  }

  if (pathname === "/notices" || pathname === "/notices.html" || pathname === "/notices/") {
    const shell = readSiteShell(root, "notices.html");
    if (!shell) return false;
    const query = Object.fromEntries(url.searchParams.entries());
    const result = await renderNoticeListPage({ req, siteKey, shellHtml: shell, query });
    sendHtml(res, result.status, result.html);
    return true;
  }

  const detailId = parseNoticeDetailId(pathname);
  if (detailId) {
    const shell = readSiteShell(root, "notice-detail.html");
    if (!shell) return false;
    const result = await renderNoticeDetailPage({ req, siteKey, shellHtml: shell, id: detailId });
    sendHtml(res, result.status, result.html);
    return true;
  }

  return false;
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);

    if (url.pathname === "/api" || url.pathname.startsWith("/api/")) {
      proxyApi(req, res, url);
      return;
    }

    const requestHost = normalizeHost(req.headers["x-forwarded-host"] || req.headers.host || "");
    const portalRoot = path.join(__dirname, "portal");
    // 局域网可用 /portal/；生产 Host portal.qlyc.co 或 ?site=portal 也可进门户
    // 静态资源用绝对路径 /portal/...，避免 ?site=portal 时相对资源丢参导致 echarts 404
    const isPortalHost = requestHost === "portal.qlyc.co" || url.searchParams.get("site") === "portal";
    const isPortalPath = url.pathname === "/portal" || url.pathname.startsWith("/portal/");
    if (isPortalHost || isPortalPath) {
      let portalPath = url.pathname;
      if (isPortalPath) {
        portalPath = url.pathname === "/portal" || url.pathname === "/portal/" ? "/" : url.pathname.slice("/portal".length) || "/";
      } else if (portalPath === "/" || portalPath === "") {
        portalPath = "/";
      }
      const portalFile =
        portalPath === "/" || portalPath === ""
          ? path.join(portalRoot, "index.html")
          : resolveStaticFile(portalRoot, portalPath);
      if (!portalFile) {
        sendText(res, 404, "Not Found", "text/html; charset=utf-8");
        return;
      }
      sendFile(res, portalFile);
      return;
    }

    const siteKey = resolveSiteKey(req, url);
    const root = siteRoot(siteKey);
    if (!fs.existsSync(root)) {
      sendText(res, 404, `Site mirror not found: ${siteKey}`);
      return;
    }

    if (url.pathname === "/robots.txt") {
      await handleRobotsTxt(req, res, siteKey, root);
      return;
    }

    if (await handleNoticeRoutes(req, res, url, siteKey, root)) {
      return;
    }

    const filePath = resolveStaticFile(root, url.pathname);
    if (!filePath) {
      sendText(res, 404, "Not Found", "text/html; charset=utf-8");
      return;
    }

    const isHomeHtml =
      filePath.endsWith(`${path.sep}index.html`) &&
      (url.pathname === "/" || url.pathname === "/index.html" || url.pathname === "");
    if (isHomeHtml) {
      try {
        const requestHost = normalizeHost(req.headers["x-forwarded-host"] || req.headers.host || "");
        const homeConfig = await fetchOfficialHomeConfig(PREVIEW_CONFIG_HOST[requestHost] || requestHost);
        if (homeConfig) {
          const html = fs.readFileSync(filePath, "utf8");
          sendHtml(res, 200, injectHomeConfigIntoHtml(html, homeConfig));
          return;
        }
      } catch {
        // fall through to static file
      }
    }

    sendFile(res, filePath);
  } catch (error) {
    sendText(res, 500, error instanceof Error ? error.message : "Internal Server Error");
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`official-web static mirrors on :${PORT}, backend=${BACKEND_URL}, default=${DEFAULT_SITE_KEY}`);
});
