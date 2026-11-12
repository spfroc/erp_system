/**
 * 官网：会员登录入口（同域读 portal_session）+ 首页最新公告滚动。
 * 用法：
 *   <a href="/portal/?from=site" data-portal-entry>会员登录</a>
 *   <div id="home-notices" data-notice-detail="public|portal">…</div>
 *   <script src="/js/portal-home.js"></script>
 */
(function () {
  var PORTAL_BASE = "/portal/";
  var PAGE_SIZE = 10;
  var SCROLL_MS = 3800;
  var me = null;
  var meReady = null;

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatDate(value) {
    if (!value) return "";
    var text = String(value);
    return text.length >= 10 ? text.slice(0, 10) : text;
  }

  function siteQuery() {
    return new URLSearchParams(window.location.search).get("site") || "";
  }

  function withSiteParam(path) {
    var site = siteQuery();
    if (!site) return path;
    var hash = "";
    var bare = path;
    var hashIdx = path.indexOf("#");
    if (hashIdx >= 0) {
      hash = path.slice(hashIdx);
      bare = path.slice(0, hashIdx);
    }
    var sep = bare.indexOf("?") >= 0 ? "&" : "?";
    return bare + sep + "site=" + encodeURIComponent(site) + hash;
  }

  function portalUrl(hash) {
    var params = new URLSearchParams();
    params.set("from", "site");
    var q = params.toString();
    return PORTAL_BASE + (q ? "?" + q : "") + (hash || "");
  }

  function ensureStyles() {
    if (document.getElementById("portal-home-styles")) return;
    var style = document.createElement("style");
    style.id = "portal-home-styles";
    style.textContent =
      ".home-notices{position:relative;z-index:2;}" +
      ".home-notices-inner{display:flex;align-items:center;gap:14px;padding:10px 0;min-height:42px;}" +
      ".home-notices-label{flex:0 0 auto;font-size:13px;font-weight:700;letter-spacing:.06em;padding:4px 10px;border-radius:999px;background:rgba(255,255,255,.18);color:inherit;}" +
      ".home-notices-viewport{flex:1;min-width:0;overflow:hidden;height:1.6em;position:relative;}" +
      ".home-notices-track{list-style:none;margin:0;padding:0;position:absolute;left:0;right:0;top:0;transition:transform .45s ease;}" +
      ".home-notices-track li{height:1.6em;line-height:1.6em;display:flex;align-items:center;gap:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}" +
      ".home-notices-track a{color:inherit;text-decoration:none;overflow:hidden;text-overflow:ellipsis;font-size:14px;}" +
      ".home-notices-track a:hover{text-decoration:underline;}" +
      ".home-notices-track .hn-time{flex:0 0 auto;opacity:.75;font-size:12px;}" +
      ".home-notices-more{flex:0 0 auto;font-size:13px;color:inherit;text-decoration:none;opacity:.92;border-bottom:1px solid currentColor;padding-bottom:1px;}" +
      ".home-notices-more:hover{opacity:1;}" +
      ".home-notices.is-light{background:#f5f8fc;color:#1a3a5c;border-top:1px solid rgba(0,51,102,.08);border-bottom:1px solid rgba(0,51,102,.08);}" +
      ".home-notices.is-light .home-notices-label{background:#e8f0fa;color:#0d4a9c;}" +
      ".home-notices.is-on-hero{margin-top:28px;padding:0;background:transparent;color:inherit;}" +
      ".home-notices.is-on-hero .home-notices-inner{padding:0;justify-content:center;max-width:920px;margin:0 auto;}" +
      ".home-notices.is-on-hero .home-notices-viewport{text-align:left;}" +
      ".portal-login-toast{position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(16,28,40,.45);padding:20px;}" +
      ".portal-login-toast[hidden]{display:none!important;}" +
      ".portal-login-card{width:min(380px,100%);background:#fffdf8;border-radius:16px;padding:22px 20px 16px;box-shadow:0 18px 48px rgba(20,32,28,.22);color:#241c14;}" +
      ".portal-login-card h3{margin:0 0 8px;font-size:18px;}" +
      ".portal-login-card p{margin:0 0 16px;color:#74685a;font-size:14px;line-height:1.55;}" +
      ".portal-login-actions{display:flex;gap:10px;justify-content:flex-end;}" +
      ".portal-login-actions button,.portal-login-actions a{font:inherit;border-radius:10px;padding:8px 14px;cursor:pointer;text-decoration:none;}" +
      ".portal-login-actions .ghost{background:#fff;border:1px solid #eadfce;color:#241c14;}" +
      ".portal-login-actions .primary{background:linear-gradient(180deg,#2f7d52,#1b5c3b);border:0;color:#f7f4ec;}";
    document.head.appendChild(style);
  }

  function fetchMe() {
    if (meReady) return meReady;
    meReady = fetch("/api/portal/me/", {
      credentials: "include",
      headers: { Accept: "application/json" },
    })
      .then(function (response) {
        if (!response.ok) throw new Error("unauthorized");
        return response.json();
      })
      .then(function (body) {
        me = body && body.data ? body.data : null;
        return me;
      })
      .catch(function () {
        me = null;
        return null;
      });
    return meReady;
  }

  function displayName(account) {
    if (!account) return "";
    return account.customerName || account.name || account.phone || "客户";
  }

  function bindPortalEntries() {
    var nodes = document.querySelectorAll("[data-portal-entry]");
    if (!nodes.length) return;
    nodes.forEach(function (el) {
      if (!el.getAttribute("href") || /portal\.qlyc\.co/i.test(el.getAttribute("href"))) {
        el.setAttribute("href", portalUrl());
      }
    });
    fetchMe().then(function (account) {
      nodes.forEach(function (el) {
        el.setAttribute("href", portalUrl());
        if (account) {
          var name = displayName(account);
          el.textContent = "会员中心";
          el.setAttribute("title", (name ? name + " · " : "") + "进入会员中心");
          el.setAttribute("alt", name || "会员中心");
          el.setAttribute("data-portal-authed", "1");
          el.removeAttribute("data-portal-label");
        } else {
          el.textContent = "会员登录";
          el.setAttribute("title", "会员登录");
          el.setAttribute("data-portal-label", "会员登录");
          el.removeAttribute("data-portal-authed");
        }
      });
    });
  }

  function ensureLoginToast() {
    var root = document.getElementById("portal-login-toast");
    if (root) return root;
    root = document.createElement("div");
    root.id = "portal-login-toast";
    root.className = "portal-login-toast";
    root.hidden = true;
    root.innerHTML =
      '<div class="portal-login-card" role="dialog" aria-modal="true" aria-labelledby="portal-login-toast-title">' +
        '<h3 id="portal-login-toast-title">需要登录</h3>' +
        '<p id="portal-login-toast-msg">登录后查看更多</p>' +
        '<div class="portal-login-actions">' +
          '<button type="button" class="ghost" data-toast-close>稍后再说</button>' +
          '<a class="primary" data-toast-login href="' + escapeHtml(portalUrl()) + '">会员登录</a>' +
        "</div>" +
      "</div>";
    document.body.appendChild(root);
    root.addEventListener("click", function (event) {
      if (event.target === root || event.target.getAttribute("data-toast-close") != null) {
        root.hidden = true;
      }
    });
    return root;
  }

  function promptLogin(message, hash) {
    var root = ensureLoginToast();
    var msg = document.getElementById("portal-login-toast-msg");
    var link = root.querySelector("[data-toast-login]");
    if (msg) msg.textContent = message || "登录后查看更多";
    if (link) link.setAttribute("href", portalUrl(hash || ""));
    root.hidden = false;
  }

  function noticeDetailMode(root) {
    return (root.getAttribute("data-notice-detail") || "public").toLowerCase();
  }

  function noticeHref(item, mode) {
    if (!item || !item.id) return portalUrl("#notices");
    if (mode === "portal") return portalUrl("#notices");
    return withSiteParam("/notices/" + encodeURIComponent(item.id));
  }

  function bindNoticeClick(anchor, item, mode) {
    anchor.addEventListener("click", function (event) {
      if (mode !== "portal") return;
      event.preventDefault();
      fetchMe().then(function (account) {
        if (account) {
          window.location.href = portalUrl("#notices");
          return;
        }
        promptLogin("登录后查看公告详情", "#notices");
      });
    });
  }

  function renderTrack(track, items, mode) {
    if (!items.length) {
      track.innerHTML = '<li><span>暂无公开公告</span></li>';
      return;
    }
    track.innerHTML = items
      .map(function (item) {
        var href = noticeHref(item, mode);
        var title = escapeHtml(item.title || "未命名公告");
        var time = escapeHtml(formatDate(item.publishedAt));
        return (
          "<li>" +
          '<a href="' +
          escapeHtml(href) +
          '" data-notice-id="' +
          escapeHtml(item.id || "") +
          '">' +
          title +
          "</a>" +
          (time ? '<span class="hn-time">' + time + "</span>" : "") +
          "</li>"
        );
      })
      .join("");
    Array.prototype.forEach.call(track.querySelectorAll("a[data-notice-id]"), function (anchor) {
      var id = anchor.getAttribute("data-notice-id");
      var item = items.filter(function (row) {
        return String(row.id) === String(id);
      })[0];
      bindNoticeClick(anchor, item, mode);
    });
  }

  function startScroll(track, count) {
    if (count <= 1) return;
    var index = 0;
    window.setInterval(function () {
      index = (index + 1) % count;
      track.style.transform = "translateY(-" + index * 1.6 + "em)";
    }, SCROLL_MS);
  }

  function bindMore(button) {
    if (!button) return;
    button.addEventListener("click", function (event) {
      event.preventDefault();
      fetchMe().then(function (account) {
        if (account) {
          window.location.href = portalUrl("#notices");
          return;
        }
        promptLogin("登录后查看更多", "#notices");
      });
    });
  }

  function loadHomeNotices() {
    var root = document.getElementById("home-notices");
    if (!root) return;
    ensureStyles();
    var track = document.getElementById("home-notices-track");
    var more = root.querySelector("[data-notices-more]");
    // 同源爬虫公告：详情需登录门户；覆盖 CMS public 模式，避免跳到运营 notices 页 404
    var mode = "portal";
    bindMore(more);
    if (!track) return;

    var url = new URL("/api/public/crawled-notices/", window.location.origin);
    url.searchParams.set("page", "1");
    url.searchParams.set("page_size", String(PAGE_SIZE));

    fetch(url.toString(), { headers: { Accept: "application/json" } })
      .then(function (response) {
        return response.json().catch(function () {
          return {};
        }).then(function (body) {
          if (!response.ok) throw new Error((body && body.detail) || "加载失败");
          return body;
        });
      })
      .then(function (payload) {
        var items = (payload.items || []).map(function (item) {
          if (item && !item.publishedAt && item.publishTime) {
            item.publishedAt = item.publishTime;
          }
          return item;
        });
        renderTrack(track, items, mode);
        startScroll(track, items.length);
      })
      .catch(function () {
        track.innerHTML = "<li><span>公告暂时无法加载</span></li>";
      });
  }

  function boot() {
    ensureStyles();
    bindPortalEntries();
    loadHomeNotices();
  }

  window.__portalFetchMe = fetchMe;
  window.__portalShowLoginToast = function () {
    promptLogin("登录后查看公告详情", "#notices");
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
