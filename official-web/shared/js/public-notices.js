(function () {
  var PAGE_SIZE = 20;
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
  var PROGRESS_CHIPS = [
    { value: "", label: "全部" },
    { value: "upcoming", label: "将开始" },
    { value: "ongoing", label: "进行中" },
    { value: "ended", label: "已结束" },
  ];
  var BUDGET_CHIPS = [
    { value: "", label: "全部" },
    { value: "0-50000", label: "5万以下" },
    { value: "50000-100000", label: "5-10万" },
    { value: "100000-500000", label: "10-50万" },
    { value: "500000-", label: "50万以上" },
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
    budgetRange: "",
  };
  var me = null;
  var meReady = null;
  var sites = [];
  var noticeKinds = [];
  var lastTotal = 0;

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
    return (
      TABS.find(function (tab) {
        return tab.id === state.tab;
      }) || TABS[0]
    );
  }

  function portalLoginUrl() {
    return "/portal/?from=site#notices";
  }

  function fetchMe() {
    if (window.__portalFetchMe) {
      return window.__portalFetchMe().then(function (account) {
        me = account || null;
        return me;
      });
    }
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

  function parseNoticeTime(value) {
    if (!value) return null;
    var text = String(value).trim();
    if (!text) return null;
    if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
      var dayStamp = Date.parse(text + "T00:00:00+08:00");
      return Number.isNaN(dayStamp) ? null : dayStamp;
    }
    if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(text) && !/(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(text)) {
      var normalized = text.replace(" ", "T");
      if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(normalized)) normalized += ":00";
      var localStamp = Date.parse(normalized + "+08:00");
      return Number.isNaN(localStamp) ? null : localStamp;
    }
    var stamp = Date.parse(text.indexOf("T") >= 0 ? text : text.replace(" ", "T"));
    return Number.isNaN(stamp) ? null : stamp;
  }

  function formatCountdown(ms) {
    var remain = Math.max(0, Number(ms) || 0);
    var totalMin = Math.floor(remain / 60000);
    var days = Math.floor(totalMin / (60 * 24));
    var hours = Math.floor((totalMin % (60 * 24)) / 60);
    var mins = totalMin % 60;
    function pad(n) {
      return ("0" + n).slice(-2);
    }
    return pad(days) + "天 " + pad(hours) + "时 " + pad(mins) + "分";
  }

  function isClosedNoticeKind(item) {
    var text = String(item.noticeKind || "") + " " + String(item.title || "");
    return /验收|合同公告|成交结果|结果公告|终止|废标|失败公告|成交公告/.test(text);
  }

  function countdownInfo(item) {
    var now = Date.now();
    var start = parseNoticeTime(item.startTime);
    var end = parseNoticeTime(item.endTime);
    var status = String(item.progressStatus || "").toLowerCase();
    var label = String(item.progressLabel || "");

    if (isClosedNoticeKind(item) && status !== "ongoing" && status !== "upcoming") {
      status = "ended";
      label = "已截止";
    } else if (!status || status === "unknown") {
      if (end && end < now) {
        status = "ended";
        label = "已截止";
      } else if (start && start > now) {
        status = "upcoming";
        label = "未开始";
      } else if (end && end >= now) {
        status = "ongoing";
        label = "进行中";
      } else if (start && start <= now) {
        status = "ongoing";
        label = "进行中";
      }
    }

    if (status === "upcoming" || label === "未开始") {
      return {
        label: "未开始",
        text: start ? "距开始 " + formatCountdown(start - now) : "即将开始",
        tone: "upcoming",
      };
    }
    if (status === "ongoing" || label === "进行中") {
      return {
        label: "进行中",
        text: end ? "距结束 " + formatCountdown(end - now) : "进行中",
        tone: "ongoing",
      };
    }
    if (status === "ended" || label === "已截止" || label === "已结束") {
      return { label: "已截止", text: "", tone: "ended" };
    }
    return { label: label || "未知", text: "", tone: "unknown" };
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
    if (state.progress) params.set("progress", state.progress);
    if (state.budgetRange) params.set("budgetRange", state.budgetRange);
    var site = qs("site");
    if (site) params.set("site", site);
    var next = params.toString();
    history.replaceState(null, "", next ? "/notices?" + next : "/notices");
  }

  function readStateFromUrl() {
    var tab = qs("tab") || "opportunity";
    if (
      !TABS.some(function (item) {
        return item.id === tab;
      })
    ) {
      tab = "opportunity";
    }
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
    state.progress = qs("progress");
    state.budgetRange = qs("budgetRange");
  }

  function applyBudgetRange(params) {
    if (!state.budgetRange) return;
    var parts = String(state.budgetRange).split("-");
    var min = parts[0];
    var max = parts[1];
    if (min) params.set("budgetMin", min);
    if (max) params.set("budgetMax", max);
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
    applyBudgetRange(params);
    return params;
  }

  function maskText(value, loggedIn) {
    var text = String(value || "").trim();
    if (!text) return "—";
    if (loggedIn) return text;
    if (text.length <= 2) return "**";
    return text.slice(0, 1) + "***";
  }

  function chipRow(label, chips, activeValue, dataKey) {
    return (
      '<div class="sourcing-filter-row">' +
      '<label class="label">' +
      escapeHtml(label) +
      "</label>" +
      '<div class="sourcing-chips">' +
      chips
        .map(function (chip) {
          var value = chip.value == null ? chip : chip.value;
          var text = chip.label == null ? chip : chip.label;
          return (
            '<button type="button" class="sourcing-chip' +
            (String(activeValue || "") === String(value) ? " active" : "") +
            '" data-chip="' +
            escapeHtml(dataKey) +
            '" data-value="' +
            escapeHtml(value) +
            '">' +
            escapeHtml(text) +
            "</button>"
          );
        })
        .join("") +
      "</div></div>"
    );
  }

  function normalizeDateInput(value) {
    var text = String(value || "").trim();
    if (!text) return "";
    var iso = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    var slash = text.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);
    var us = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    var y;
    var m;
    var d;
    if (iso) {
      y = iso[1];
      m = iso[2];
      d = iso[3];
    } else if (slash) {
      y = slash[1];
      m = slash[2];
      d = slash[3];
    } else if (us) {
      y = us[3];
      m = us[1];
      d = us[2];
    } else {
      return "";
    }
    m = ("0" + m).slice(-2);
    d = ("0" + d).slice(-2);
    var stamp = Date.parse(y + "-" + m + "-" + d + "T00:00:00");
    if (Number.isNaN(stamp)) return "";
    return y + "-" + m + "-" + d;
  }

  function collectAdvanced(root) {
    if (!root) return;
    var region = root.querySelector("[name=regionName]");
    var projectCode = root.querySelector("[name=projectCode]");
    var projectName = root.querySelector("[name=projectName]");
    var buyerName = root.querySelector("[name=buyerName]");
    var from = root.querySelector("[name=publishDateFrom]");
    var to = root.querySelector("[name=publishDateTo]");
    if (region) state.regionName = (region.value || "").trim();
    if (projectCode) state.projectCode = (projectCode.value || "").trim();
    if (projectName) state.projectName = (projectName.value || "").trim();
    if (buyerName) state.buyerName = (buyerName.value || "").trim();
    if (from) {
      state.publishDateFrom = normalizeDateInput(from.value);
      from.value = state.publishDateFrom;
    }
    if (to) {
      state.publishDateTo = normalizeDateInput(to.value);
      to.value = state.publishDateTo;
    }
  }

  function collectSearch() {
    var bar = document.getElementById("sourcing-searchbar");
    if (!bar) return;
    var input = bar.querySelector("[name=search]");
    if (input) state.search = (input.value || "").trim();
  }

  function runSearch() {
    collectSearch();
    collectAdvanced(document.getElementById("sourcing-filters"));
    state.page = 1;
    loadList();
  }

  function resetFilters() {
    state.search = "";
    state.siteId = "";
    state.noticeKind = "";
    state.regionName = "";
    state.projectCode = "";
    state.projectName = "";
    state.buyerName = "";
    state.publishDateFrom = "";
    state.publishDateTo = "";
    state.progress = "";
    state.budgetRange = "";
    state.page = 1;
    renderSearchBar();
    renderFilters();
    loadList();
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
        state.progress = "";
        renderFilters();
        loadList();
      });
    });
  }

  function renderSearchBar() {
    var root = document.getElementById("sourcing-searchbar");
    if (!root) return;
    root.innerHTML =
      '<input name="search" type="search" placeholder="请输入关键字" value="' +
      escapeHtml(state.search) +
      '" />' +
      '<button class="btn" type="button" data-role="search">搜索</button>' +
      '<button class="btn ghost" type="button" data-role="reset">重置</button>';
    root.querySelector("[data-role=search]").onclick = runSearch;
    root.querySelector("[data-role=reset]").onclick = resetFilters;
    root.querySelector("[name=search]").addEventListener("keydown", function (event) {
      if (event.key === "Enter") runSearch();
    });
  }

  function bindChips(root) {
    root.querySelectorAll("[data-chip]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var key = btn.getAttribute("data-chip");
        var value = btn.getAttribute("data-value") || "";
        if (key === "siteId") state.siteId = value;
        if (key === "noticeKind") state.noticeKind = value;
        if (key === "progress") state.progress = value;
        if (key === "budgetRange") state.budgetRange = value;
        state.page = 1;
        renderFilters();
        loadList();
      });
    });
  }

  function renderFilters() {
    var root = document.getElementById("sourcing-filters");
    if (!root) return;
    var tab = currentTab();
    var siteChips = [{ value: "", label: "全部" }].concat(
      sites.map(function (site) {
        return { value: site.id, label: site.label };
      })
    );
    var kindChips = [{ value: "", label: "全部" }].concat(
      noticeKinds.map(function (kind) {
        return { value: kind, label: kind };
      })
    );
    var html = "";
    html += chipRow("站点", siteChips, state.siteId, "siteId");
    html += chipRow("公告类型", kindChips, state.noticeKind, "noticeKind");
    if (tab.id === "opportunity") {
      html += chipRow("状态", PROGRESS_CHIPS, state.progress, "progress");
    }
    html += chipRow("采购预算", BUDGET_CHIPS, state.budgetRange, "budgetRange");
    html +=
      '<div class="sourcing-filter-row">' +
      '<label class="label">更多条件</label>' +
      '<div class="sourcing-advanced">' +
      '<label class="field"><span>所属区域</span><input name="regionName" type="text" placeholder="区域" value="' +
      escapeHtml(state.regionName) +
      '" /></label>' +
      '<label class="field"><span>项目编号</span><input name="projectCode" type="text" placeholder="项目编号" value="' +
      escapeHtml(state.projectCode) +
      '" /></label>' +
      '<label class="field"><span>项目名称</span><input name="projectName" type="text" placeholder="项目名称" value="' +
      escapeHtml(state.projectName) +
      '" /></label>' +
      '<label class="field"><span>采购单位</span><input name="buyerName" type="text" placeholder="采购单位" value="' +
      escapeHtml(state.buyerName) +
      '" /></label>' +
      '<label class="field"><span>发布起</span><input name="publishDateFrom" class="date-input" type="text" data-datepicker placeholder="yyyy-mm-dd" maxlength="10" autocomplete="off" value="' +
      escapeHtml(state.publishDateFrom) +
      '" /></label>' +
      '<label class="field"><span>发布止</span><input name="publishDateTo" class="date-input" type="text" data-datepicker placeholder="yyyy-mm-dd" maxlength="10" autocomplete="off" value="' +
      escapeHtml(state.publishDateTo) +
      '" /></label>' +
      "</div></div>";
    root.innerHTML = html;
    bindChips(root);
    root.querySelectorAll("input").forEach(function (input) {
      input.addEventListener("keydown", function (event) {
        if (event.key === "Enter") runSearch();
      });
    });
    if (window.ycDatePicker) {
      window.ycDatePicker.bindAll(root, "input.date-input", {
        onChange: function () {
          /* 选中后保持筛选框值，点搜索再提交 */
        },
      });
    } else {
      root.querySelectorAll("input.date-input").forEach(function (input) {
        input.addEventListener("blur", function () {
          var raw = String(input.value || "").trim();
          if (!raw) {
            input.value = "";
            return;
          }
          var next = normalizeDateInput(raw);
          if (next) input.value = next;
        });
      });
    }
  }

  function renderResultBar(total, totalPages) {
    var root = document.getElementById("sourcing-resultbar");
    if (!root) return;
    root.innerHTML =
      "<div>共 <strong>" +
      total +
      "</strong> 个结果 · 每页 " +
      PAGE_SIZE +
      " 条</div>" +
      '<div class="pager-mini">' +
      '<button type="button" data-dir="-1" aria-label="上一页">&lt;</button>' +
      "<span>" +
      state.page +
      " / " +
      totalPages +
      "</span>" +
      '<button type="button" data-dir="1" aria-label="下一页">&gt;</button>' +
      "</div>";
    root.querySelectorAll("button").forEach(function (btn) {
      btn.onclick = function () {
        var next = state.page + Number(btn.getAttribute("data-dir"));
        if (next < 1 || next > totalPages) return;
        state.page = next;
        loadList();
      };
    });
  }

  function cardTags(item) {
    var tags = [];
    if (item.siteLabel) tags.push(item.siteLabel);
    if (item.noticeKind) tags.push(item.noticeKind);
    if (item.regionName) tags.push(item.regionName);
    return tags.slice(0, 3);
  }

  function renderList(payload) {
    var list = document.getElementById("notice-list");
    var empty = document.getElementById("notice-empty");
    var pager = document.getElementById("notice-pager");
    if (!list) return;
    var items = payload.items || [];
    var loggedIn = Boolean(me);
    lastTotal = Number(payload.total || 0);
    var totalPages = Math.max(1, Math.ceil(lastTotal / PAGE_SIZE));
    renderResultBar(lastTotal, totalPages);

    if (!items.length) {
      list.innerHTML = "";
      if (empty) empty.hidden = false;
    } else {
      if (empty) empty.hidden = true;
      list.innerHTML = items
        .map(function (item) {
          var buyer = maskText(item.buyerName, loggedIn);
          var amount = loggedIn ? money(item.budgetAmount || item.dealAmount) : "登录可见";
          var clock = countdownInfo(item);
          var tags = cardTags(item);
          return (
            '<article class="notice-card' +
            (loggedIn ? "" : " is-masked") +
            '" data-id="' +
            escapeHtml(item.id) +
            '">' +
            "<h3>" +
            escapeHtml(item.title || "未命名公告") +
            "</h3>" +
            '<div class="notice-card-status tone-' +
            escapeHtml(clock.tone) +
            '"><strong>' +
            escapeHtml(clock.label) +
            "</strong><em class='countdown'>" +
            escapeHtml(clock.text || "") +
            "</em></div>" +
            '<div class="notice-card-fields">' +
            "<div>采购预算：<b>" +
            escapeHtml(amount) +
            "</b></div>" +
            "<div>发布时间：" +
            escapeHtml(formatDate(item.publishTime || item.publishedAt)) +
            "</div>" +
            "<div>采购单位：" +
            escapeHtml(buyer) +
            "</div>" +
            "</div>" +
            '<div class="notice-card-tags">' +
            tags
              .map(function (tag) {
                return "<span>" + escapeHtml(tag) + "</span>";
              })
              .join("") +
            "</div>" +
            '<button type="button" class="card-action">查看详情</button>' +
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
          window.open("/notices/" + encodeURIComponent(id), "_blank", "noopener,noreferrer");
        });
      });
    }

    if (pager) {
      pager.innerHTML =
        "<span>共 " +
        lastTotal +
        " 条 · 第 " +
        state.page +
        " / " +
        totalPages +
        " 页 · 每页 " +
        PAGE_SIZE +
        " 条</span>" +
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
        return res.text().then(function (text) {
          var body = null;
          if (text) {
            try {
              body = JSON.parse(text);
            } catch (error) {
              throw new Error(res.ok ? "接口返回异常" : "加载失败（" + res.status + "）");
            }
          }
          if (!res.ok) throw new Error((body && body.detail) || "加载失败（" + res.status + "）");
          return body || {};
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
    renderSearchBar();
    renderFilters();
    fetchMe().then(function (account) {
      me = account || null;
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
            escapeHtml(
              [detail.siteLabel, detail.noticeKind, formatDate(detail.publishTime || detail.publishedAt)]
                .filter(Boolean)
                .join(" · ")
            ) +
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
