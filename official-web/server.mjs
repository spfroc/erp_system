import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 5180);
const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const DEFAULT_SITE_KEY = process.env.DEFAULT_SITE_KEY || "qlyc";

const HOST_TO_SITE = {
  "www.qlyc.co": "qlyc",
  "qlyc.co": "qlyc",
  "www.yizhichan.co": "yizhichan",
  "yizhichan.co": "yizhichan",
  "www.jinanyunji.com": "jinanyunji",
  "jinanyunji.com": "jinanyunji",
  "www.qinghuicai.cn": "qinghuicai",
  "qinghuicai.cn": "qinghuicai",
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
    if (!host || /^(localhost|127\.0\.0\.1)$/i.test(host)) continue;
    if (HOST_TO_SITE[host]) return HOST_TO_SITE[host];
    const bare = host.startsWith("www.") ? host.slice(4) : host;
    if (HOST_TO_SITE[bare]) return HOST_TO_SITE[bare];
    if (HOST_TO_SITE[`www.${bare}`]) return HOST_TO_SITE[`www.${bare}`];
    const key = bare.split(".")[0];
    if (fs.existsSync(path.join(__dirname, "sites", key))) return key;
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

function sendText(res, status, text, type = "text/plain; charset=utf-8") {
  res.writeHead(status, { "Content-Type": type });
  res.end(text);
}

async function proxyApi(req, res, url) {
  const target = new URL(url.pathname + url.search, BACKEND_URL);
  const headers = { ...req.headers, host: new URL(BACKEND_URL).host };
  delete headers["content-length"];
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const body = Buffer.concat(chunks);
  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body: ["GET", "HEAD"].includes(req.method || "GET") ? undefined : body,
  });
  const buffer = Buffer.from(await upstream.arrayBuffer());
  const outHeaders = {
    "Content-Type": upstream.headers.get("content-type") || "application/json",
  };
  res.writeHead(upstream.status, outHeaders);
  res.end(buffer);
}

function resolveStaticFile(root, pathname) {
  let filePath = safeJoin(root, pathname === "/" ? "/index.html" : pathname);
  if (!filePath) return null;
  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, "index.html");
  }
  if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    // pretty path without .html
    const htmlPath = `${filePath}.html`;
    if (fs.existsSync(htmlPath) && fs.statSync(htmlPath).isFile()) return htmlPath;
    return null;
  }
  return filePath;
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);

    if (url.pathname === "/api" || url.pathname.startsWith("/api/")) {
      await proxyApi(req, res, url);
      return;
    }

    const siteKey = resolveSiteKey(req, url);
    const root = siteRoot(siteKey);
    if (!fs.existsSync(root)) {
      sendText(res, 404, `Site mirror not found: ${siteKey}`);
      return;
    }

    const filePath = resolveStaticFile(root, url.pathname);
    if (!filePath) {
      sendText(res, 404, "Not Found", "text/html; charset=utf-8");
      return;
    }
    sendFile(res, filePath);
  } catch (error) {
    console.error(error);
    sendText(res, 502, `official-web error: ${error.message}`);
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`official-web static mirrors on :${PORT}, backend=${BACKEND_URL}, default=${DEFAULT_SITE_KEY}`);
});
