import http from "node:http";
import { escapeAttr, escapeHtml } from "./seo.mjs";

const homeCache = new Map();
const HOME_CACHE_TTL_MS = 60_000;

export function fetchOfficialHomeConfig(host) {
  const cacheKey = String(host || "").toLowerCase();
  const hit = homeCache.get(cacheKey);
  if (hit && Date.now() - hit.at < HOME_CACHE_TTL_MS) {
    return Promise.resolve(hit.data);
  }
  const backend = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const target = new URL(`/api/public/official-site/?host=${encodeURIComponent(host || "")}`, `${backend}/`);
  return new Promise((resolve) => {
    const req = http.request(
      target,
      {
        method: "GET",
        headers: { accept: "application/json", "user-agent": "official-web-home", host: target.host },
        timeout: 8000,
      },
      (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          try {
            const body = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
            const data = res.statusCode && res.statusCode < 400 ? body.data?.homeConfig || null : null;
            if (data) homeCache.set(cacheKey, { at: Date.now(), data });
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

function buildApplyScript(homeConfig) {
  const payload = JSON.stringify(homeConfig).replace(/</g, "\\u003c");
  return `<script>window.__OFFICIAL_HOME_CONFIG__=${payload};</script>
<script>
(function () {
  var cfg = window.__OFFICIAL_HOME_CONFIG__;
  if (!cfg || !cfg.contact) return;
  var c = cfg.contact || {};
  var footer = cfg.footer || {};
  var beian = cfg.beian || {};

  function setText(el, text) {
    if (el && text != null && String(text) !== "") el.textContent = String(text);
  }

  function applySideBar() {
    var bar = document.querySelector(".side-contact-bar");
    if (!bar) return;
    var items = bar.querySelectorAll("a.contact-item, .contact-item.wechat-contact-side");
    items.forEach(function (item) {
      var label = (item.querySelector(".contact-label") || {}).textContent || "";
      var text = item.querySelector(".contact-text");
      if (label.indexOf("咨询热线") >= 0 && c.hotline) {
        if (item.tagName === "A") item.setAttribute("href", "tel:" + c.hotline);
        setText(text, c.hotline);
      } else if (label.indexOf("手机") >= 0 && c.mobile) {
        if (item.tagName === "A") item.setAttribute("href", "tel:" + c.mobile);
        setText(text, c.mobile);
      } else if ((label.indexOf("联系我们") >= 0 || label.indexOf("邮箱") >= 0 || (text && text.textContent.indexOf("邮箱") >= 0)) && c.email) {
        if (item.tagName === "A") item.setAttribute("href", "mailto:" + c.email);
      }
      var img = item.querySelector(".wechat-qr-side img");
      if (img && c.wechatQrUrl) img.setAttribute("src", c.wechatQrUrl);
    });
  }

  function applyIndustries() {
    var list = cfg.industries || [];
    var wrap = document.querySelector("#industries .industries");
    if (!wrap || !list.length) return;
    wrap.innerHTML = list.map(function (item) {
      var icon = item.icon ? '<div class="industry-icon"><i class="fas ' + String(item.icon).replace(/"/g, "") + '"></i></div>' : "";
      return '<div class="industry-card">' + icon + "<h3>" + String(item.title || "") + "</h3><p>" + String(item.description || "") + "</p></div>";
    }).join("");
  }

  function applyInquiryPlatforms() {
    var options = cfg.inquiryPlatforms || [];
    var select = document.querySelector("#platform, select[name='platform_name']");
    var hidden = document.querySelector("input[type='hidden'][name='platform_name']");
    if (select && select.tagName === "SELECT" && options.length) {
      var html = '<option value="">请选择</option>';
      options.forEach(function (item) {
        html += '<option value="' + String(item.value || item.label || "").replace(/"/g, "&quot;") + '">' + String(item.label || item.value || "") + "</option>";
      });
      select.innerHTML = html;
    } else if (hidden && options.length === 1) {
      hidden.value = options[0].value || options[0].label || hidden.value;
    }
  }

  function applyContactSection() {
    var section = document.querySelector("#contact");
    if (!section) return;
    var html = section.innerHTML;
    if (c.contactName) html = html.replace(/(联系人[：:]\\s*)([^<]+)/, "$1" + c.contactName);
    if (c.mobile || c.hotline) {
      var phones = [c.mobile, c.hotline].filter(Boolean).join(" / ");
      html = html.replace(/(电话[：:]\\s*)([^<]+)/, "$1" + phones);
    }
    if (c.email) html = html.replace(/(邮箱[：:]\\s*)([^<]+)/, "$1" + c.email);
    if (c.address) html = html.replace(/(地址[：:]\\s*)([^<]+)/, "$1" + c.address);
    section.innerHTML = html;

    // 青慧采联系区多为段落堆叠，再补一次侧栏同源电话到 footer 联系我们
  }

  function applyFooter() {
    var footerEl = document.querySelector("footer");
    if (!footerEl) return;
    var sections = footerEl.querySelectorAll(".footer-section");
    sections.forEach(function (sec) {
      var h = sec.querySelector("h3");
      if (!h) return;
      var title = h.textContent || "";
      if (title.indexOf("官方平台") >= 0 && (footer.platforms || []).length) {
        var ul = sec.querySelector("ul") || document.createElement("ul");
        ul.className = "footer-links";
        ul.innerHTML = footer.platforms.map(function (item) {
          return '<li><a href="' + String(item.url || "#") + '" target="_blank" rel="noopener">' + String(item.name || "") + "</a></li>";
        }).join("");
        sec.innerHTML = "";
        sec.appendChild(h);
        sec.appendChild(ul);
      } else if ((title.indexOf("我们的服务") >= 0 || title.indexOf("快速链接") >= 0) && (footer.services || []).length) {
        var list = document.createElement("ul");
        list.className = title.indexOf("快速链接") >= 0 ? "footer-links" : "";
        list.innerHTML = footer.services.map(function (item) {
          var label = item.title || item.name || "";
          var href = item.url || "#";
          var extra = item.contentHtml ? ("<div>" + item.contentHtml + "</div>") : "";
          return "<li><a href=\"" + href + "\">" + label + "</a>" + extra + "</li>";
        }).join("");
        sec.innerHTML = "";
        sec.appendChild(h);
        sec.appendChild(list);
      } else if (title.indexOf("平台关键词") >= 0 && footer.keywords) {
        var p = sec.querySelector("p") || document.createElement("p");
        p.textContent = footer.keywords;
        sec.innerHTML = "";
        sec.appendChild(h);
        sec.appendChild(p);
      } else if (title.indexOf("联系我们") >= 0) {
        var lines = [];
        if (c.hotline) lines.push("电话: " + c.hotline);
        if (c.mobile && c.mobile !== c.hotline) lines.push("手机: " + c.mobile);
        if (c.email) lines.push("邮箱: " + c.email);
        if (c.address) lines.push("地址: " + c.address);
        if (!lines.length) return;
        var box = sec.querySelector("ul") || sec.querySelector("p") || document.createElement("ul");
        if (box.tagName === "UL") {
          box.innerHTML = lines.map(function (line) { return "<li>" + line + "</li>"; }).join("");
        } else {
          box.innerHTML = lines.map(function (line) {
            return "<i class=\"fas fa-phone\"></i> " + line + "<br>";
          }).join("");
        }
        sec.innerHTML = "";
        sec.appendChild(h);
        sec.appendChild(box);
      }
    });

    var copyright = footerEl.querySelector(".copyright p, .copyright");
    if (copyright && (beian.copyright || beian.icpText || beian.policeText)) {
      var parts = [];
      if (beian.copyright) parts.push(beian.copyright);
      if (beian.icpText) {
        parts.push(beian.icpUrl
          ? '<a href="' + beian.icpUrl + '" target="_blank" rel="noopener">' + beian.icpText + "</a>"
          : beian.icpText);
      }
      if (beian.telecomLicense) parts.push(beian.telecomLicense);
      if (beian.policeText) {
        parts.push(beian.policeUrl
          ? '<a href="' + beian.policeUrl + '" target="_blank" rel="noopener">' + beian.policeText + "</a>"
          : beian.policeText);
      }
      var target = copyright.tagName === "P" ? copyright : copyright.querySelector("p") || copyright;
      target.innerHTML = parts.join(" | ");
    }
  }

  function run() {
    applySideBar();
    applyIndustries();
    applyInquiryPlatforms();
    applyContactSection();
    applyFooter();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
</script>`;
}

export function injectHomeConfigIntoHtml(html, homeConfig) {
  if (!html || !homeConfig) return html;
  const script = buildApplyScript(homeConfig);
  if (/<\/body>/i.test(html)) {
    return html.replace(/<\/body>/i, `${script}\n</body>`);
  }
  return `${html}\n${script}`;
}

export function homeConfigMetaComment(homeConfig) {
  if (!homeConfig) return "";
  return `<!-- official-home-config key=${escapeAttr(homeConfig.key || "")} domains=${escapeHtml((homeConfig.domains || []).join(","))} -->`;
}
