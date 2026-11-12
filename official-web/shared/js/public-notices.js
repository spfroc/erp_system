(function () {
  var PAGE_SIZE = 10;
  var TABS = [
    {
      id: "opportunity",
      label: "商机大厅",
      progress: "ongoing,upcoming",
      noticeKinds: "",
      hint: "进行中 / 将开始的采购机会",
    },
    {
      id: "result",
      label: "公告大厅",
      progress: "",
      noticeKinds: "成交公告,成交结果公告,结果公告,失败公告,终止公告,废标公告",
      hint: "成交 / 失败 / 终止等结果类公告",
    },
    {
      id: "intent",
      label: "采购意向",
      progress: "",
      noticeKinds: "意向公开",
      hint: "采购意向公开信息",
    },
  ];

  var state = {
    tab: "opportunity",
    page: 1,
    search: "",
    siteId: "",
    noticeKind: "",
    regionName: "",
    projectCode: "",
    projectName: "",
    buyerName: "",
    publishDateFrom: "",
    publishDateTo: "",
    progress: "",
  };
  var me = null;
  var meReady = null;
  var sites = [];
  var noticeKinds = [];

  function qs(name) {
    return new URLSearchParams(window.location.search).get(name) || "";
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatDate(value) {
    if (!value) return "—";
    var text = String(value);
    return text.length >= 10 ? text.slice(0, 10) : text;
  }

  function money(value) {
    if (value == null || value === "" || Number.isNaN(Number(value))) return "—";
    try {
      return new Intl.NumberFormat("zh-CN", {
        style: "currency",
        currency: "CNY",
        maximumFractionDigits: 2,
      }).format(Number(value));
    } catch (error) {
      return String(value);
    }
  }

  function currentTab() {
    return TABS.find(function (tab) {
      return tab.id === state.tab;
    }) || TABS[0];
  }

  function portalLoginUrl() {
    return "/portal/?from=site#notices";
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
        me = body && body.data ? body.data : null;
        return me;
      })
      .catch(function () {
        me = null;
        return null;
      });
    return meReady;
  }

  function promptLogin() {
    if (typeof window.__portalShowLoginToast === "function") {
      window.__portalShowLoginToast();
      return;
    }
    window.location.href = portalLoginUrl();
  }

  function syncUrl() {
    var params = new URLSearchParams();
    if (state.tab && state.tab !== "opportunity") params.set("tab", state.tab);
    if (state.page > 1) params.set("page", String(state.page));
    if (state.search) params.set("search", state.search);
    if (state.siteId) params.set("siteId", state.siteId);
    if (state.noticeKind) params.set("noticeKind", state.noticeKind);
    if (state.regionName) params.set("regionName", state.regionName);
    if (state.projectCode) params.set("projectCode", state.projectCode);
    if (state.projectName) params.set("projectName", state.projectName);
    if (state.buyerName) params.set("buyerName", state.buyerName);
    if (state.publishDateFrom) params.set("publishDateFrom", state.publishDateFrom);
    if (state.publishDateTo) params.set("publishDateTo", state.publishDateTo);
    var site = qs("site");
    if (site) params.set("site", site);
    var next = params.toString();
    history.replaceState(null, "", next ? "/notices?" + next : "/notices");
  }

  function readStateFromUrl() {
    var tab = qs("tab") || "opportunity";
    if (!TABS.some(function (item) { return item.id === tab; })) tab = "opportunity";
    state.tab = tab;
    state.page = Math.max(1, Number(qs("page") || 1) || 1);
    state.search = qs("search");
    state.siteId = qs("siteId");
    state.noticeKind = qs("noticeKind") || qs("kind");
    state.regionName = qs("regionName");
    state.projectCode = qs("projectCode");
    state.projectName = qs("projectName");
    state.buyerName = qs("buyerName");
    state.publishDateFrom = qs("publishDateFrom");
    state.publishDateTo = qs("publishDateTo");
  }

  function buildQuery() {
    var tab = currentTab();
    var params = new URLSearchParams({
      page: String(state.page),
      page_size: String(PAGE_SIZE),
    });
    if (state.search) params.set("search", state.search);
    if (state.siteId) params.set("siteId", state.siteId);
    if (state.noticeKind) {
      params.set("noticeKind", state.noticeKind);
    } else if (tab.noticeKinds) {
      params.set("noticeKinds", tab.noticeKinds);
    }
    if (state.regionName) params.set("regionName", state.regionName);
    if (state.projectCode) params.set("projectCode", state.projectCode);
    if (state.projectName) params.set("projectName", state.projectName);
    if (state.buyerName) params.set("buyerName", state.buyerName);
    if (state.publishDateFrom) params.set("publishDateFrom", state.publishDateFrom);
    if (state.publishDateTo) params.set("publishDateTo", state.publishDateTo);
    if (state.progress) params.set("progress", state.progress);
    else if (tab.progress) params.set("progress", tab.progress);
    return params;
  }

  function maskText(value, loggedIn) {
    var text = String(value || "").trim();
    if (!text) return "—";
    if (loggedIn) return text;
    if (text.length <= 2) return "**";
    return text.slice(0, 1) + "***";
  }

  function renderTabs() {
    var root = document.getElementById("sourcing-tabs");
    if (!root) return;
    root.innerHTML = TABS.map(function (tab) {
      return (
        '<button type="button" class="sourcing-tab' +
        (tab.id === state.tab ? " active" : "") +
        '" data-tab="' +
        escapeHtml(tab.id) +
        '">' +
        escapeHtml(tab.label) +
        "</button>"
      );
    }).join("");
    root.querySelectorAll("[data-tab]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.tab = btn.getAttribute("data-tab");
        state.page = 1;
        state.noticeKind = "";
        loadList();
      });
    });
  }

  function renderFilters() {
    var root = document.getElementById("sourcing-filters");
    if (!root) return;
    var tab = currentTab();
    root.innerHTML =
      '<p class="sourcing-hint">' +
      escapeHtml(tab.hint) +
      "</p>" +
      '<input name="search" type="search" placeholder="搜索标题、项目编号、采购单位" value="' +
      escapeHtml(state.search) +
      '" />' +
      '<select name="siteId"><option value="">全部站点</option>' +
      sites
        .map(function (site) {
          return (
            '<option value="' +
            escapeHtml(site.id) +
            '"' +
            (state.siteId === site.id ? " selected" : "") +
            ">" +
            escapeHtml(site.label) +
            "</option>"
          );
        })
        .join("") +
      "</select>" +
      '<select name="noticeKind"><option value="">类型（页签默认）</option>' +
      noticeKinds
        .map(function (kind) {
          return (
            '<option value="' +
            escapeHtml(kind) +
            '"' +
            (state.noticeKind === kind ? " selected" : "") +
            ">" +
            escapeHtml(kind) +
            "</option>"
          );
        })
        .join("") +
      "</select>" +
      '<input name="regionName" type="text" placeholder="区域" value="' +
      escapeHtml(state.regionName) +
      '" />' +
      '<input name="projectCode" type="text" placeholder="项目编号" value="' +
      escapeHtml(state.projectCode) +
      '" />' +
      '<input name="projectName" type="text" placeholder="项目名称" value="' +
      escapeHtml(state.projectName) +
      '" />' +
      '<input name="buyerName" type="text" placeholder="采购单位" value="' +
      escapeHtml(state.buyerName) +
      '" />' +
      '<input name="publishDateFrom" type="date" value="' +
      escapeHtml(state.publishDateFrom) +
      '" />' +
      '<input name="publishDateTo" type="date" value="' +
      escapeHtml(state.publishDateTo) +
      '" />' +
      '<button class="btn" type="button" data-role="search">搜索</button>' +
      '<button class="btn ghost" type="button" data-role="reset">重置</button>';

    function collect() {
      state.search = (root.querySelector("[name=search]").value || "").trim();
      state.siteId = root.querySelector("[name=siteId]").value || "";
      state.noticeKind = root.querySelector("[name=noticeKind]").value || "";
      state.regionName = (root.querySelector("[name=regionName]").value || "").trim();
      state.projectCode = (root.querySelector("[name=projectCode]").value || "").trim();
      state.projectName = (root.querySelector("[name=projectName]").value || "").trim();
      state.buyerName = (root.querySelector("[name=buyerName]").value || "").trim();
      state.publishDateFrom = root.querySelector("[name=publishDateFrom]").value || "";
      state.publishDateTo = root.querySelector("[name=publishDateTo]").value || "";
      state.page = 1;
      loadList();
    }
    root.querySelector("[data-role=search]").onclick = collect;
    root.querySelector("[data-role=reset]").onclick = function () {
      state.search = "";
      state.siteId = "";
      state.noticeKind = "";
      state.regionName = "";
      state.projectCode = "";
      state.projectName = "";
      state.buyerName = "";
      state.publishDateFrom = "";
      state.publishDateTo = "";
      state.page = 1;
      renderFilters();
      loadList();
    };
    root.querySelector("[name=search]").addEventListener("keydown", function (event) {
      if (event.key === "Enter") collect();
    });
  }

  function renderList(payload) {
    var list = document.getElementById("notice-list");
    var empty = document.getElementById("notice-empty");
    var pager = document.getElementById("notice-pager");
    if (!list) return;
    var items = payload.items || [];
    var loggedIn = Boolean(me);
    if (!items.length) {
      list.innerHTML = "";
      if (empty) empty.hidden = false;
    } else {
      if (empty) empty.hidden = true;
      list.innerHTML = items
        .map(function (item) {
          var buyer = maskText(item.buyerName, loggedIn);
          var amount = loggedIn ? money(item.budgetAmount || item.dealAmount) : "登录可见";
          return (
            '<article class="notice-card' +
            (loggedIn ? "" : " is-masked") +
            '" data-id="' +
            escapeHtml(item.id) +
            '">' +
            '<div class="notice-card-main">' +
            "<h3>" +
            escapeHtml(item.title || "未命名公告") +
            "</h3>" +
            '<div class="notice-card-meta">' +
            "<span>" +
            escapeHtml(item.siteLabel || "—") +
            "</span>" +
            "<span>" +
            escapeHtml(item.noticeKind || "公告") +
            "</span>" +
            "<span>" +
            escapeHtml(item.progressLabel || "—") +
            "</span>" +
            "<span>" +
            escapeHtml(item.regionName || "—") +
            "</span>" +
            "<span>" +
            escapeHtml(formatDate(item.publishTime || item.publishedAt)) +
            "</span>" +
            "</div>" +
            '<div class="notice-card-sub">' +
            "<span>采购单位：" +
            escapeHtml(buyer) +
            "</span>" +
            "<span>金额：" +
            escapeHtml(amount) +
            "</span>" +
            "</div>" +
            "</div>" +
            '<button type="button" class="btn">查看详情</button>' +
            "</article>"
          );
        })
        .join("");
      list.querySelectorAll(".notice-card").forEach(function (card) {
        card.addEventListener("click", function () {
          var id = card.getAttribute("data-id");
          if (!me) {
            promptLogin();
            return;
          }
          window.location.href = "/notices/" + encodeURIComponent(id);
        });
      });
    }

    var total = Number(payload.total || 0);
    var totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (pager) {
      pager.innerHTML =
        "<span>共 " +
        total +
        " 条 · 第 " +
        state.page +
        " / " +
        totalPages +
        " 页</span>" +
        "<div>" +
        '<button class="btn ghost" type="button" data-dir="-1">上一页</button>' +
        '<button class="btn ghost" type="button" data-dir="1">下一页</button>' +
        "</div>";
      pager.querySelectorAll("button").forEach(function (btn) {
        btn.onclick = function () {
          var next = state.page + Number(btn.getAttribute("data-dir"));
          if (next < 1 || next > totalPages) return;
          state.page = next;
          loadList();
        };
      });
    }
  }

  function loadList() {
    var loading = document.getElementById("notice-loading");
    if (loading) loading.hidden = false;
    syncUrl();
    fetch("/api/public/crawled-notices/?" + buildQuery().toString(), {
      headers: { Accept: "application/json" },
    })
      .then(function (res) {
        return res.json().then(function (body) {
          if (!res.ok) throw new Error((body && body.detail) || "加载失败");
          return body;
        });
      })
      .then(function (body) {
        if (Array.isArray(body.sites) && body.sites.length) sites = body.sites;
        if (Array.isArray(body.noticeKinds) && body.noticeKinds.length) noticeKinds = body.noticeKinds;
        renderFilters();
        renderList(body);
      })
      .catch(function (error) {
        var list = document.getElementById("notice-list");
        if (list) list.innerHTML = '<p class="notice-empty">' + escapeHtml(error.message || "加载失败") + "</p>";
      })
      .finally(function () {
        if (loading) loading.hidden = true;
      });
  }

  function bootList() {
    readStateFromUrl();
    renderTabs();
    fetchMe().then(function () {
      loadList();
    });
  }

  function bootDetail() {
    var root = document.getElementById("notice-detail");
    if (!root) return;
    var parts = location.pathname.split("/").filter(Boolean);
    var id = parts[parts.length - 1];
    fetchMe().then(function (account) {
      if (!account) {
        root.innerHTML =
          '<div class="notice-empty">请先登录后查看公告详情。<p style="margin-top:12px"><a class="btn" href="' +
          portalLoginUrl() +
          '">会员登录</a></p></div>';
        promptLogin();
        return;
      }
      fetch("/api/public/notices/" + encodeURIComponent(id) + "/", { headers: { Accept: "application/json" } })
        .then(function (res) {
          return res.json().then(function (body) {
            if (!res.ok) throw new Error((body && body.detail) || "加载失败");
            return body.data || body;
          });
        })
        .then(function (detail) {
          root.innerHTML =
            "<h2>" +
            escapeHtml(detail.title || "公告详情") +
            "</h2>" +
            '<p class="muted">' +
            escapeHtml([detail.siteLabel, detail.noticeKind, formatDate(detail.publishTime || detail.publishedAt)].filter(Boolean).join(" · ")) +
            "</p>" +
            '<div class="notice-detail-grid">' +
            "<div><span>采购单位</span><strong>" +
            escapeHtml(detail.buyerName || detail.department || "—") +
            "</strong></div>" +
            "<div><span>项目编号</span><strong>" +
            escapeHtml(detail.projectCode || detail.projectNumber || "—") +
            "</strong></div>" +
            "<div><span>区域</span><strong>" +
            escapeHtml(detail.regionName || "—") +
            "</strong></div>" +
            "<div><span>进度</span><strong>" +
            escapeHtml(detail.progressLabel || detail.bidStatus || "—") +
            "</strong></div>" +
            "</div>" +
            (detail.sourceUrl
              ? '<p style="margin-top:16px"><a class="btn" href="' +
                escapeHtml(detail.sourceUrl) +
                '" target="_blank" rel="noopener">打开原文</a></p>'
              : "");
        })
        .catch(function (error) {
          root.innerHTML = '<p class="notice-empty">' + escapeHtml(error.message || "加载失败") + "</p>";
        });
    });
  }

  function boot() {
    var page = document.body.getAttribute("data-page");
    var menuBtn = document.querySelector(".mobile-menu-btn");
    if (menuBtn) {
      menuBtn.addEventListener("click", function () {
        var menu = document.querySelector(".nav-menu");
        if (menu) menu.classList.toggle("active");
      });
    }
    if (page === "notice-list" || document.getElementById("sourcing-tabs") || document.getElementById("notice-list")) {
      bootList();
    }
    if (page === "notice-detail" || document.getElementById("notice-detail")) {
      bootDetail();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
