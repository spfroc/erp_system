/**
 * 官网首页田字格：招标信息 / 泉E采 / 齐鲁云采 / 青慧采
 * 依赖同页 portal-home.js 提供的登录探测与 toast（可选独立 fallback）。
 */
(function () {
  var QUADS = [
    { key: "ccgp", title: "招标信息", siteId: "sd-ccgp", noticeKind: "采购公告", progress: "ongoing" },
    { key: "quanyicai", title: "泉E采", siteId: "jd-quan-yicai", noticeKind: "采购公告", progress: "ongoing" },
    { key: "qlyc", title: "齐鲁云采", siteId: "sd-ggzyjyzx", noticeKind: "采购公告", progress: "ongoing" },
    { key: "qinghuicai", title: "青慧采", siteId: "jd-qing-huicai", noticeKind: "采购公告", progress: "ongoing" },
  ];
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
    return "/portal/?from=site" + (hash || "");
  }

  function ensureStyles() {
    if (document.getElementById("home-notice-quad-styles")) return;
    var style = document.createElement("style");
    style.id = "home-notice-quad-styles";
    style.textContent =
      "#home-notice-quad{padding:36px 0 20px;background:linear-gradient(180deg,#0b1a28 0%,#12283c 100%);color:#e8eef5;}" +
      "#home-notice-quad.is-light{background:#f5f8fc;color:#1a3a5c;}" +
      "#home-notice-quad .hnq-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;}" +
      "#home-notice-quad .hnq-card{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.12);border-radius:16px;padding:16px 16px 10px;min-height:280px;display:flex;flex-direction:column;box-shadow:0 10px 28px rgba(0,0,0,.12);}" +
      "#home-notice-quad.is-light .hnq-card{background:#fff;border-color:#e6edf5;box-shadow:0 8px 24px rgba(26,58,92,.06);}" +
      "#home-notice-quad .hnq-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px;}" +
      "#home-notice-quad .hnq-head h3{margin:0;font-size:17px;font-weight:750;}" +
      "#home-notice-quad .hnq-more{font-size:13px;opacity:.85;text-decoration:none;color:inherit;}" +
      "#home-notice-quad .hnq-more:hover{opacity:1;text-decoration:underline;}" +
      "#home-notice-quad .hnq-list{list-style:none;margin:0;padding:0;flex:1;}" +
      "#home-notice-quad .hnq-list li{display:flex;align-items:flex-start;gap:8px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.08);}" +
      "#home-notice-quad.is-light .hnq-list li{border-bottom-color:#eef2f7;}" +
      "#home-notice-quad .hnq-list li:last-child{border-bottom:0;}" +
      "#home-notice-quad .hnq-list a{flex:1;min-width:0;color:inherit;text-decoration:none;font-size:14px;line-height:1.45;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}" +
      "#home-notice-quad .hnq-list a:hover{color:#4ea1ff;}" +
      "#home-notice-quad.is-light .hnq-list a:hover{color:#0d4a9c;}" +
      "#home-notice-quad .hnq-new{flex:none;margin-top:2px;font-size:11px;font-weight:700;line-height:1;padding:3px 6px;border-radius:999px;background:#e11d48;color:#fff;}" +
      "#home-notice-quad .hnq-empty,#home-notice-quad .hnq-loading{padding:18px 4px;font-size:13px;opacity:.7;}" +
      "@media (max-width:900px){#home-notice-quad .hnq-grid{grid-template-columns:1fr;}#home-notice-quad{padding:24px 0 4px;}}";
    document.head.appendChild(style);
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
        meCache = body && body.data ? body.data : null;
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

  function openItem(item) {
    fetchMe().then(function (account) {
      if (!account) {
        showLoginToast();
        return;
      }
      window.location.href = withSiteParam("/notices/" + encodeURIComponent(item.id));
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
            var badge = isNew(item) ? '<span class="hnq-new">新</span>' : "";
            return (
              "<li>" +
              badge +
              '<a href="#" data-id="' +
              escapeHtml(item.id) +
              '">' +
              escapeHtml(item.title || "未命名公告") +
              "</a></li>"
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
      page_size: "10",
      siteId: quad.siteId,
      noticeKind: quad.noticeKind,
      progress: quad.progress,
    });
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
    grid.className = "hnq-grid container";
    if (!grid.classList.contains("container") && root.closest(".container")) {
      grid.className = "hnq-grid";
    }
    // Prefer nesting inside existing .container if present as parent
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
