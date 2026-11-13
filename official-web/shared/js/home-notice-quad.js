/**
 * 官网首页田字格：泉E采 / 青慧采 / 招标信息 / 齐鲁云采
 * 依赖同页 portal-home.js 提供的登录探测与 toast（可选独立 fallback）。
 */
(function () {
  var QUADS = [
    { key: "quanyicai", title: "泉E采", siteId: "jd-quan-yicai", progress: "ongoing", prefix: "mode" },
    { key: "qinghuicai", title: "青慧采", siteId: "jd-qing-huicai", progress: "ongoing", prefix: "mode" },
    { key: "ccgp", title: "招标信息", siteId: "sd-ccgp", progress: "ongoing", prefix: "region" },
    { key: "qlyc", title: "齐鲁云采", siteId: "sd-ggzyjyzx", progress: "ongoing", prefix: "region" },
  ];
  var PAGE_SIZE = 8;
  var NEW_MS = 3 * 60 * 60 * 1000;
  var meCache = null;
  var meReady = null;

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function siteQuery() {
    return new URLSearchParams(window.location.search).get("site") || "";
  }

  function withSiteParam(path) {
    var site = siteQuery();
    if (!site) return path;
    var sep = path.indexOf("?") >= 0 ? "&" : "?";
    return path + sep + "site=" + encodeURIComponent(site);
  }

  function portalUrl(hash) {
    var hashPart = hash || "";
    if (hashPart && hashPart.charAt(0) !== "#") hashPart = "#" + hashPart;
    var host = String((location && location.hostname) || "").toLowerCase();
    if (host === "qlyc.co" || host.slice(-8) === ".qlyc.co") {
      return "/portal/?from=site" + hashPart;
    }
    return (
      "https://portal.qlyc.co/?from=site&return_to=" +
      encodeURIComponent(location.origin + "/") +
      hashPart
    );
  }

  function ensureStyles() {
    var style = document.getElementById("home-notice-quad-styles");
    if (!style) {
      style = document.createElement("style");
      style.id = "home-notice-quad-styles";
      document.head.appendChild(style);
    }
    style.textContent =
      "#home-notice-quad{--hnq-bg:#fff;--hnq-card:#fff;--hnq-line:#e6edf5;padding:36px 0 20px;background:var(--hnq-bg);color:#1a3a5c;}" +
      "#home-notice-quad.is-dark{--hnq-bg:#0f2030;--hnq-card:#0f2030;--hnq-line:rgba(255,255,255,.1);background:var(--hnq-bg);color:#e8eef5;}" +
      "#home-notice-quad.is-light{--hnq-bg:#fff;--hnq-card:#fff;--hnq-line:#e6edf5;background:var(--hnq-bg);color:#1a3a5c;}" +
      "#home-notice-quad .hnq-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;width:100%;box-sizing:border-box;}" +
      "#home-notice-quad .hnq-card{min-width:0;width:100%;max-width:100%;overflow:hidden;background:var(--hnq-card);border:1px solid var(--hnq-line);border-radius:16px;padding:16px 16px 10px;min-height:280px;display:flex;flex-direction:column;box-shadow:none;box-sizing:border-box;}" +
      "#home-notice-quad .hnq-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px;min-width:0;}" +
      "#home-notice-quad .hnq-head h3{margin:0;font-size:17px;font-weight:750;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}" +
      "#home-notice-quad .hnq-more{flex:none;font-size:13px;opacity:.85;text-decoration:none;color:inherit;white-space:nowrap;}" +
      "#home-notice-quad .hnq-more:hover{opacity:1;text-decoration:underline;}" +
      "#home-notice-quad .hnq-list{list-style:none;margin:0;padding:0;flex:1;min-width:0;width:100%;overflow:hidden;}" +
      "#home-notice-quad .hnq-list li{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #eef2f7;width:100%;min-width:0;max-width:100%;overflow:hidden;box-sizing:border-box;}" +
      "#home-notice-quad.is-dark .hnq-list li{border-bottom-color:rgba(255,255,255,.08);}" +
      "#home-notice-quad .hnq-list li:last-child{border-bottom:0;}" +
      "#home-notice-quad .hnq-list a{flex:1 1 0;min-width:0;max-width:100%;width:100%;display:flex;align-items:center;gap:8px;color:inherit;text-decoration:none;font-size:14px;line-height:1.45;overflow:hidden;}" +
      "#home-notice-quad .hnq-list a:hover{color:#0d4a9c;}" +
      "#home-notice-quad.is-dark .hnq-list a:hover{color:#4ea1ff;}" +
      "#home-notice-quad .hnq-main{flex:1 1 0;min-width:0;display:flex;align-items:baseline;overflow:hidden;}" +
      "#home-notice-quad .hnq-prefix{flex:none;color:#0d4a9c;font-weight:600;}" +
      "#home-notice-quad .hnq-title{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}" +
      "#home-notice-quad .hnq-date{flex:none;margin-left:auto;opacity:.72;font-variant-numeric:tabular-nums;white-space:nowrap;}" +
      "#home-notice-quad .hnq-new{position:relative;top:-0.55em;flex:none;margin-left:3px;font-size:10px;font-weight:800;line-height:1;letter-spacing:.02em;color:#e11d48;padding:0;background:transparent;border-radius:0;animation:hnq-new-burst .95s ease-in-out infinite;transform-origin:center;}" +
      "#home-notice-quad .hnq-new::before{content:\"\";position:absolute;left:50%;top:50%;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;background:radial-gradient(circle,rgba(250,204,21,.95) 0%,rgba(250,204,21,.35) 42%,transparent 70%);z-index:-1;animation:hnq-new-flash .95s ease-in-out infinite;}" +
      "#home-notice-quad .hnq-new::after{content:\"\";position:absolute;left:50%;top:50%;width:14px;height:14px;margin:-7px 0 0 -7px;background:conic-gradient(from 0deg,#facc15 0 12%,transparent 12% 25%,#fde047 25% 37%,transparent 37% 50%,#fbbf24 50% 62%,transparent 62% 75%,#facc15 75% 87%,transparent 87% 100%);opacity:.85;z-index:-1;animation:hnq-new-spin .95s linear infinite;}" +
      "@keyframes hnq-new-burst{0%,100%{transform:scale(1) rotate(-6deg);text-shadow:0 0 2px #fde047,0 0 6px rgba(250,204,21,.8);}50%{transform:scale(1.22) rotate(6deg);text-shadow:0 0 4px #fef08a,0 0 10px #facc15,0 0 14px #f59e0b;}}" +
      "@keyframes hnq-new-flash{0%,100%{transform:scale(.7);opacity:.55;}50%{transform:scale(1.35);opacity:1;}}" +
      "@keyframes hnq-new-spin{0%{transform:rotate(0deg) scale(.85);opacity:.7;}50%{transform:rotate(180deg) scale(1.15);opacity:1;}100%{transform:rotate(360deg) scale(.85);opacity:.7;}}" +
      "#home-notice-quad .hnq-empty,#home-notice-quad .hnq-loading{padding:18px 4px;font-size:13px;opacity:.7;}" +
      "@media (max-width:900px){#home-notice-quad .hnq-grid{grid-template-columns:minmax(0,1fr);}#home-notice-quad{padding:24px 0 4px;}}";
  }

  function fetchMe() {
    if (window.__portalFetchMe) return window.__portalFetchMe();
    if (meReady) return meReady;
    meReady = fetch("/api/portal/me/", { credentials: "include", headers: { Accept: "application/json" } })
      .then(function (res) {
        if (!res.ok) throw new Error("unauthorized");
        return res.json();
      })
      .then(function (body) {
        meCache = (body && body.data) || body || null;
        return meCache;
      })
      .catch(function () {
        meCache = null;
        return null;
      });
    return meReady;
  }

  function showLoginToast() {
    if (typeof window.__portalShowLoginToast === "function") {
      window.__portalShowLoginToast();
      return;
    }
    window.location.href = portalUrl("#notices");
  }

  function isNew(item) {
    var raw = item && (item.publishTime || item.publishedAt);
    if (!raw) return false;
    var ts = Date.parse(String(raw).replace(/-/g, "/"));
    if (!ts) return false;
    return Date.now() - ts <= NEW_MS;
  }

  function methodLabel(item) {
    var blob = [item.procurementMode, item.noticeKind, item.title].join(" ");
    if (/反拍|电子反拍/.test(blob)) return "反拍";
    if (/询比/.test(blob)) return "询比";
    if (/竞价/.test(blob)) return "竞价";
    if (/招标|磋商|谈判|单一来源|邀请招标|公开招标/.test(blob)) return "招标";
    var mode = String(item.procurementMode || "").trim();
    if (mode) return mode.replace(/^普通/, "");
    return "";
  }

  function publishDateShort(item) {
    var raw = (item && (item.publishTime || item.publishedAt)) || "";
    var text = String(raw).trim().replace("T", " ");
    return text.length >= 10 ? text.slice(0, 10) : text;
  }

  function linePrefix(quad, item) {
    if (quad.prefix === "mode") {
      var method = methodLabel(item);
      return method ? "【" + method + "】" : "";
    }
    if (quad.prefix === "region") {
      var region = String((item && item.regionName) || "").trim();
      return region ? "【" + region + "】" : "";
    }
    return "";
  }

  function openItem(item) {
    fetchMe().then(function (account) {
      if (!account) {
        showLoginToast();
        return;
      }
      window.open(withSiteParam("/notices/" + encodeURIComponent(item.id)), "_blank", "noopener,noreferrer");
    });
  }

  function renderCard(root, quad, payload) {
    var items = (payload && payload.items) || [];
    var listHtml;
    if (!items.length) {
      listHtml = '<p class="hnq-empty">暂无进行中公告</p>';
    } else {
      listHtml =
        '<ul class="hnq-list">' +
        items
          .map(function (item) {
            var fullTitle = item.title || "未命名公告";
            var prefix = linePrefix(quad, item);
            var date = publishDateShort(item);
            var lineText = (prefix ? prefix : "") + fullTitle + (date ? " " + date : "");
            var safeTitle = escapeHtml(fullTitle);
            var badge = isNew(item) ? '<span class="hnq-new" aria-label="新">New</span>' : "";
            return (
              "<li>" +
              '<a class="hnq-link" href="#" data-id="' +
              escapeHtml(item.id) +
              '" alt="' +
              safeTitle +
              '" title="' +
              escapeHtml(lineText) +
              '">' +
              '<span class="hnq-main">' +
              (prefix ? '<span class="hnq-prefix">' + escapeHtml(prefix) + "</span>" : "") +
              '<span class="hnq-title">' +
              escapeHtml(fullTitle) +
              "</span>" +
              badge +
              "</span>" +
              (date ? '<span class="hnq-date">' + escapeHtml(date) + "</span>" : "") +
              "</a>" +
              "</li>"
            );
          })
          .join("") +
        "</ul>";
    }
    root.innerHTML =
      '<div class="hnq-head"><h3>' +
      escapeHtml(quad.title) +
      '</h3><a class="hnq-more" href="' +
      escapeHtml(withSiteParam("/notices?tab=opportunity&siteId=" + encodeURIComponent(quad.siteId))) +
      '">更多</a></div>' +
      listHtml;
    root.querySelectorAll("a[data-id]").forEach(function (link) {
      link.addEventListener("click", function (event) {
        event.preventDefault();
        var id = link.getAttribute("data-id");
        var item = items.find(function (row) {
          return String(row.id) === String(id);
        });
        if (item) openItem(item);
      });
    });
  }

  function loadQuad(card, quad) {
    card.innerHTML =
      '<div class="hnq-head"><h3>' +
      escapeHtml(quad.title) +
      "</h3></div><p class=\"hnq-loading\">加载中…</p>";
    var params = new URLSearchParams({
      page: "1",
      page_size: String(PAGE_SIZE),
      siteId: quad.siteId,
      progress: quad.progress || "ongoing",
    });
    if (quad.noticeKind) params.set("noticeKind", quad.noticeKind);
    if (quad.noticeKinds) params.set("noticeKinds", quad.noticeKinds);
    fetch("/api/public/crawled-notices/?" + params.toString(), { headers: { Accept: "application/json" } })
      .then(function (res) {
        return res.json().then(function (body) {
          if (!res.ok) throw new Error((body && body.detail) || "加载失败");
          return body;
        });
      })
      .then(function (body) {
        renderCard(card, quad, body);
      })
      .catch(function () {
        card.innerHTML =
          '<div class="hnq-head"><h3>' +
          escapeHtml(quad.title) +
          '</h3></div><p class="hnq-empty">暂时无法加载</p>';
      });
  }

  function boot() {
    var root = document.getElementById("home-notice-quad");
    if (!root) return;
    ensureStyles();
    var grid = document.createElement("div");
    var host = root;
    if (root.querySelector(".container")) {
      host = root.querySelector(".container");
      grid.className = "hnq-grid";
    } else {
      grid.className = "container hnq-grid";
    }
    host.appendChild(grid);
    QUADS.forEach(function (quad) {
      var card = document.createElement("article");
      card.className = "hnq-card";
      card.dataset.quad = quad.key;
      grid.appendChild(card);
      loadQuad(card, quad);
    });
    fetchMe();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
