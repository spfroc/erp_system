(function () {
  var PAGE_SIZE_OPTIONS = [10, 20, 50, 100];
  var DEFAULT_PAGE_SIZE = 20;
  var RESULT_KIND_MAP = {
    成交: "成交公告,成交结果公告,结果公告",
    失败: "失败公告,终止公告,废标公告",
  };
  var TABS = [
    {
      id: "opportunity",
      label: "商机大厅",
      progress: "ongoing,upcoming",
      noticeKinds: "",
      excludeNoticeKinds:
        "意向公开,成交公告,成交结果公告,结果公告,失败公告,终止公告,废标公告,验收公告,合同公告",
      kindLabel: "采购方式",
      kindChips: [
        { value: "", label: "全部" },
        { value: "竞价", label: "竞价" },
        { value: "反拍", label: "反拍" },
        { value: "询比", label: "询比" },
        { value: "招标", label: "招标" },
      ],
      kindMode: "procurementMode",
      hint: "进行中 / 将开始的采购机会",
    },
    {
      id: "result",
      label: "公告大厅",
      progress: "",
      noticeKinds: "成交公告,成交结果公告,结果公告,失败公告,终止公告,废标公告",
      kindLabel: "公告类型",
      kindChips: [
        { value: "", label: "全部" },
        { value: "成交", label: "成交" },
        { value: "失败", label: "失败" },
      ],
      kindMode: "resultKind",
      hint: "成交 / 失败等结果类公告",
    },
    {
      id: "intent",
      label: "采购意向",
      progress: "",
      noticeKinds: "意向公开",
      kindLabel: "",
      kindChips: null,
      kindMode: "",
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
  var SORT_FIELDS_BASE = [
    { field: "publishTime", label: "发布时间" },
    { field: "endTime", label: "结束时间" },
  ];
  var SORT_FIELDS_WITH_START = SORT_FIELDS_BASE.concat([{ field: "startTime", label: "开始时间" }]);
  var ALLOWED_SORTS = {
    "": 1,
    publishTime: 1,
    "-publishTime": 1,
    endTime: 1,
    "-endTime": 1,
    startTime: 1,
    "-startTime": 1,
  };
  var DEFAULT_SORT = "";

  var state = {
    tab: "opportunity",
    page: 1,
    pageSize: DEFAULT_PAGE_SIZE,
    search: "",
    siteId: "",
    noticeKind: "",
    resultKind: "",
    procurementMode: "",
    regionName: "",
    buyerName: "",
    progress: "",
    budgetRange: "",
    sort: DEFAULT_SORT,
  };
  var me = null;
  var meReady = null;
  var sites = [];
  var lastTotal = 0;
  var listRequestSeq = 0;

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
    var host = String((location && location.hostname) || "").toLowerCase();
    if (host === "qlyc.co" || host.slice(-8) === ".qlyc.co") {
      return "/portal/?from=site#notices";
    }
    return (
      "https://portal.qlyc.co/?from=site&return_to=" +
      encodeURIComponent(location.href) +
      "#notices"
    );
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

  function maskSensitive(value, loggedIn) {
    var text = String(value == null ? "" : value).trim();
    if (!text || text === "—") return "—";
    if (loggedIn) return text;
    if (text.length <= 2) return "**";
    return text.slice(0, 1) + "***";
  }

  function syncUrl() {
    var params = new URLSearchParams();
    if (state.tab && state.tab !== "opportunity") params.set("tab", state.tab);
    if (state.page > 1) params.set("page", String(state.page));
    if (state.pageSize !== DEFAULT_PAGE_SIZE) params.set("page_size", String(state.pageSize));
    if (state.search) params.set("search", state.search);
    if (state.siteId) params.set("siteId", state.siteId);
    if (state.procurementMode) params.set("procurementMode", state.procurementMode);
    if (state.resultKind) params.set("resultKind", state.resultKind);
    if (state.regionName) params.set("regionName", state.regionName);
    if (state.buyerName) params.set("buyerName", state.buyerName);
    if (state.progress) params.set("progress", state.progress);
    if (state.budgetRange) params.set("budgetRange", state.budgetRange);
    if (state.sort) params.set("sort", state.sort);
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
    var size = Number(qs("page_size") || qs("pageSize") || DEFAULT_PAGE_SIZE) || DEFAULT_PAGE_SIZE;
    state.pageSize = PAGE_SIZE_OPTIONS.indexOf(size) >= 0 ? size : DEFAULT_PAGE_SIZE;
    state.search = qs("search");
    state.siteId = qs("siteId");
    state.procurementMode = qs("procurementMode");
    state.resultKind = qs("resultKind");
    state.regionName = qs("regionName");
    state.buyerName = qs("buyerName");
    state.progress = qs("progress");
    state.budgetRange = qs("budgetRange");
    state.sort = qs("sort") || DEFAULT_SORT;
    if (!ALLOWED_SORTS[state.sort]) state.sort = DEFAULT_SORT;
  }

  function canSortByStartTime() {
    var tab = currentTab();
    if (!tab || tab.id !== "opportunity") return false;
    return state.progress === "upcoming" || state.progress === "ongoing";
  }

  function currentSortFields() {
    return canSortByStartTime() ? SORT_FIELDS_WITH_START : SORT_FIELDS_BASE;
  }

  function sortFieldOf(sortValue) {
    var text = String(sortValue || "");
    return text.charAt(0) === "-" ? text.slice(1) : text;
  }

  function sortDirOf(sortValue) {
    var text = String(sortValue || "");
    if (!text) return "";
    return text.charAt(0) === "-" ? "desc" : "asc";
  }

  function sortArrow(field) {
    if (sortFieldOf(state.sort) !== field) return "";
    var dir = sortDirOf(state.sort);
    if (dir === "asc") return "↓"; // 正序
    if (dir === "desc") return "↑"; // 倒序
    return "";
  }

  function cycleSortField(field) {
    var currentField = sortFieldOf(state.sort);
    var currentDir = sortDirOf(state.sort);
    if (currentField !== field) {
      // 新字段：先正序
      state.sort = field;
      return;
    }
    if (currentDir === "asc") {
      // 正序 → 倒序
      state.sort = "-" + field;
      return;
    }
    // 倒序 → 关闭，回默认
    state.sort = DEFAULT_SORT;
  }

  function normalizeSortForProgress() {
    if (!canSortByStartTime() && sortFieldOf(state.sort) === "startTime") {
      state.sort = DEFAULT_SORT;
    }
  }

  function renderSortRow() {
    var fields = currentSortFields();
    return (
      '<div class="sourcing-filter-row">' +
      '<label class="label">排序</label>' +
      '<div class="sourcing-chips">' +
      fields
        .map(function (item) {
          var active = sortFieldOf(state.sort) === item.field;
          var arrow = sortArrow(item.field);
          var title =
            !active
              ? "点击按" + item.label + "正序"
              : sortDirOf(state.sort) === "asc"
                ? "当前正序，点击改为倒序"
                : "当前倒序，点击关闭排序";
          return (
            '<button type="button" class="sourcing-chip sourcing-sort-chip' +
            (active ? " active" : "") +
            '" data-sort-field="' +
            escapeHtml(item.field) +
            '" title="' +
            escapeHtml(title) +
            '" aria-label="' +
            escapeHtml(title) +
            '">' +
            escapeHtml(item.label) +
            (arrow ? '<span class="sort-arrow" aria-hidden="true">' + arrow + "</span>" : "") +
            "</button>"
          );
        })
        .join("") +
      "</div></div>"
    );
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
      page_size: String(state.pageSize),
    });
    if (state.search) params.set("search", state.search);
    if (state.siteId) params.set("siteId", state.siteId);
    if (tab.kindMode === "procurementMode" && state.procurementMode) {
      params.set("procurementMode", state.procurementMode);
    }
    if (tab.kindMode === "resultKind" && state.resultKind && RESULT_KIND_MAP[state.resultKind]) {
      params.set("noticeKinds", RESULT_KIND_MAP[state.resultKind]);
    } else if (tab.noticeKinds) {
      params.set("noticeKinds", tab.noticeKinds);
    }
    if (tab.excludeNoticeKinds) {
      params.set("excludeNoticeKinds", tab.excludeNoticeKinds);
    }
    if (state.regionName) params.set("regionName", state.regionName);
    if (state.buyerName) params.set("buyerName", state.buyerName);
    if (state.progress) params.set("progress", state.progress);
    else if (tab.progress) params.set("progress", tab.progress);
    applyBudgetRange(params);
    if (state.sort) params.set("sort", state.sort);
    return params;
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

  function collectAdvanced(root) {
    if (!root) return;
    var region = root.querySelector("[name=regionName]");
    var buyerName = root.querySelector("[name=buyerName]");
    if (region) state.regionName = (region.value || "").trim();
    if (buyerName) state.buyerName = (buyerName.value || "").trim();
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
    state.resultKind = "";
    state.procurementMode = "";
    state.regionName = "";
    state.buyerName = "";
    state.progress = "";
    state.budgetRange = "";
    state.sort = DEFAULT_SORT;
    state.page = 1;
    renderSearchBar();
    renderFilters();
    loadList();
  }

  function clearListPending() {
    var list = document.getElementById("notice-list");
    var empty = document.getElementById("notice-empty");
    var pager = document.getElementById("notice-pager");
    var resultBar = document.getElementById("sourcing-resultbar");
    var loading = document.getElementById("notice-loading");
    if (list) list.innerHTML = "";
    if (empty) empty.hidden = true;
    if (pager) pager.innerHTML = "";
    if (resultBar) resultBar.innerHTML = "";
    if (loading) loading.hidden = false;
  }

  function switchTab(tabId) {
    if (!tabId || tabId === state.tab) {
      renderTabs();
      return;
    }
    state.tab = tabId;
    state.page = 1;
    state.noticeKind = "";
    state.resultKind = "";
    state.procurementMode = "";
    state.progress = "";
    // 先清旧列表，避免异步返回前仍显示上一页签数据
    listRequestSeq += 1;
    clearListPending();
    renderTabs();
    renderFilters();
    loadList();
  }

  function renderTabs() {
    var root = document.getElementById("sourcing-tabs");
    if (!root) return;
    root.innerHTML = TABS.map(function (tab) {
      return (
        '<button type="button" role="tab" aria-selected="' +
        (tab.id === state.tab ? "true" : "false") +
        '" class="sourcing-tab' +
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
        switchTab(btn.getAttribute("data-tab"));
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
        if (key === "procurementMode") state.procurementMode = value;
        if (key === "resultKind") state.resultKind = value;
        if (key === "progress") {
          state.progress = value;
          normalizeSortForProgress();
        }
        if (key === "budgetRange") state.budgetRange = value;
        state.page = 1;
        renderFilters();
        loadList();
      });
    });
    root.querySelectorAll("[data-sort-field]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        cycleSortField(btn.getAttribute("data-sort-field") || "");
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
    normalizeSortForProgress();
    var siteChips = [{ value: "", label: "全部" }].concat(
      sites.map(function (site) {
        return { value: site.id, label: site.label };
      })
    );
    var html = "";
    html += chipRow("站点", siteChips, state.siteId, "siteId");
    if (tab.kindChips && tab.kindChips.length) {
      var activeKind = tab.kindMode === "procurementMode" ? state.procurementMode : state.resultKind;
      html += chipRow(tab.kindLabel || "公告类型", tab.kindChips, activeKind, tab.kindMode);
    }
    if (tab.id === "opportunity") {
      html += chipRow("状态", PROGRESS_CHIPS, state.progress, "progress");
    }
    html += chipRow("采购预算", BUDGET_CHIPS, state.budgetRange, "budgetRange");
    html += renderSortRow();
    html +=
      '<div class="sourcing-filter-row">' +
      '<label class="label">更多条件</label>' +
      '<div class="sourcing-advanced">' +
      '<label class="field"><span>所属区域</span><input name="regionName" type="text" placeholder="区域" value="' +
      escapeHtml(state.regionName) +
      '" /></label>' +
      '<label class="field"><span>采购单位</span><input name="buyerName" type="text" placeholder="采购单位" value="' +
      escapeHtml(state.buyerName) +
      '" /></label>' +
      "</div></div>";
    root.innerHTML = html;
    bindChips(root);
    root.querySelectorAll("input").forEach(function (input) {
      input.addEventListener("keydown", function (event) {
        if (event.key === "Enter") runSearch();
      });
    });
  }

  function goPage(next, totalPages) {
    var page = Math.max(1, Math.min(totalPages, Number(next) || 1));
    if (page === state.page) return;
    state.page = page;
    loadList();
    var top = document.getElementById("sourcing-root");
    if (top && top.scrollIntoView) top.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderPagination(total, totalPages) {
    var pager = document.getElementById("notice-pager");
    var resultBar = document.getElementById("sourcing-resultbar");
    var summary =
      "共 <strong>" +
      total +
      "</strong> 条 · 第 " +
      state.page +
      " / " +
      totalPages +
      " 页";
    if (resultBar) {
      resultBar.innerHTML = "<div>" + summary + "</div>";
    }
    if (!pager) return;
    if (total <= 0) {
      pager.innerHTML = "";
      return;
    }
    pager.innerHTML =
      '<div class="notice-pagination">' +
      '<div class="pagination-summary">' +
      summary +
      "</div>" +
      '<label class="pagination-size">每页' +
      '<select data-role="page-size">' +
      PAGE_SIZE_OPTIONS.map(function (size) {
        return (
          '<option value="' +
          size +
          '"' +
          (size === state.pageSize ? " selected" : "") +
          ">" +
          size +
          "</option>"
        );
      }).join("") +
      "</select></label>" +
      '<div class="pagination-actions">' +
      '<button type="button" class="btn ghost" data-page="1"' +
      (state.page <= 1 ? " disabled" : "") +
      ">首页</button>" +
      '<button type="button" class="btn ghost" data-page="' +
      (state.page - 1) +
      '"' +
      (state.page <= 1 ? " disabled" : "") +
      ">上一页</button>" +
      "<strong>" +
      state.page +
      " / " +
      totalPages +
      "</strong>" +
      '<button type="button" class="btn ghost" data-page="' +
      (state.page + 1) +
      '"' +
      (state.page >= totalPages ? " disabled" : "") +
      ">下一页</button>" +
      '<button type="button" class="btn ghost" data-page="' +
      totalPages +
      '"' +
      (state.page >= totalPages ? " disabled" : "") +
      ">末页</button>" +
      "</div>" +
      '<label class="pagination-jump">跳至' +
      '<input type="number" min="1" max="' +
      totalPages +
      '" value="' +
      state.page +
      '" data-role="jump-page" />页' +
      '<button type="button" class="btn ghost" data-role="jump-go">跳转</button></label>' +
      "</div>";

    pager.querySelectorAll("button[data-page]").forEach(function (btn) {
      btn.onclick = function () {
        if (btn.disabled) return;
        goPage(btn.getAttribute("data-page"), totalPages);
      };
    });
    var sizeSelect = pager.querySelector("[data-role=page-size]");
    if (sizeSelect) {
      sizeSelect.onchange = function () {
        state.pageSize = Number(sizeSelect.value) || DEFAULT_PAGE_SIZE;
        state.page = 1;
        loadList();
      };
    }
    var jumpInput = pager.querySelector("[data-role=jump-page]");
    var jumpGo = pager.querySelector("[data-role=jump-go]");
    function doJump() {
      goPage(jumpInput && jumpInput.value, totalPages);
    }
    if (jumpGo) jumpGo.onclick = doJump;
    if (jumpInput) {
      jumpInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
          event.preventDefault();
          doJump();
        }
      });
    }
  }

  function cardTags(item) {
    var tags = [];
    if (item.siteLabel) tags.push(item.siteLabel);
    if (item.noticeKind) tags.push(item.noticeKind);
    if (item.procurementMode) tags.push(item.procurementMode);
    if (item.regionName) tags.push(item.regionName);
    return tags.slice(0, 4);
  }

  function renderList(payload) {
    var list = document.getElementById("notice-list");
    var empty = document.getElementById("notice-empty");
    if (!list) return;
    var items = payload.items || [];
    lastTotal = Number(payload.total || 0);
    var totalPages = Math.max(1, Math.ceil(lastTotal / state.pageSize) || 1);
    if (state.page > totalPages) {
      state.page = totalPages;
    }
    renderPagination(lastTotal, totalPages);

    if (!items.length) {
      list.innerHTML = "";
      if (empty) empty.hidden = false;
      return;
    }
    if (empty) empty.hidden = true;
    list.innerHTML = items
      .map(function (item) {
        var amount = money(item.budgetAmount || item.dealAmount);
        var clock = countdownInfo(item);
        var tags = cardTags(item);
        var href = "/notices/" + encodeURIComponent(item.id);
        return (
          '<a class="notice-card" href="' +
          escapeHtml(href) +
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
          "<div>结束时间：" +
          escapeHtml(formatDate(item.endTime)) +
          "</div>" +
          "<div>采购单位：" +
          escapeHtml(item.buyerName || "—") +
          "</div>" +
          "</div>" +
          '<div class="notice-card-tags">' +
          tags
            .map(function (tag) {
              return "<span>" + escapeHtml(tag) + "</span>";
            })
            .join("") +
          "</div>" +
          '<span class="card-action">查看详情</span>' +
          "</a>"
        );
      })
      .join("");
  }

  function loadList() {
    var loading = document.getElementById("notice-loading");
    if (loading) loading.hidden = false;
    syncUrl();
    var seq = ++listRequestSeq;
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
        if (seq !== listRequestSeq) return;
        if (Array.isArray(body.sites) && body.sites.length) sites = body.sites;
        renderFilters();
        renderList(body);
      })
      .catch(function (error) {
        if (seq !== listRequestSeq) return;
        var list = document.getElementById("notice-list");
        if (list) list.innerHTML = '<p class="notice-empty">' + escapeHtml(error.message || "加载失败") + "</p>";
      })
      .finally(function () {
        if (seq !== listRequestSeq) return;
        if (loading) loading.hidden = true;
      });
  }

  function bootList() {
    readStateFromUrl();
    // 避免 SSR 旧列表残留造成闪烁
    var list = document.getElementById("notice-list");
    if (list) list.innerHTML = "";
    var empty = document.getElementById("notice-empty");
    if (empty) empty.hidden = true;
    var pager = document.getElementById("notice-pager");
    if (pager) pager.innerHTML = "";
    renderTabs();
    renderSearchBar();
    renderFilters();
    fetchMe().then(function (account) {
      me = account || null;
      loadList();
    });
  }

  function renderDetailHtml(detail, loggedIn) {
    var buyer = maskSensitive(detail.buyerName || detail.department || "—", loggedIn);
    var amount = loggedIn ? money(detail.budgetAmount || detail.dealAmount || detail.amount) : "登录可见";
    var contact = loggedIn
      ? [detail.contactName, detail.contactPhone].filter(Boolean).join(" ") || "—"
      : "登录可见";
    var projectCode = maskSensitive(detail.projectCode || detail.projectNumber || "—", loggedIn);
    var content = "";
    if (detail.content) {
      content = loggedIn
        ? '<div class="detail-content">' + escapeHtml(detail.content) + "</div>"
        : '<div class="detail-content is-masked"><p>正文已隐藏，登录后可查看完整公告内容。</p><p><a class="btn" href="' +
          escapeHtml(portalLoginUrl()) +
          '">会员登录</a></p></div>';
    } else if (!loggedIn) {
      content =
        '<div class="detail-content is-masked"><p>关键信息已隐藏，登录后可查看完整公告。</p><p><a class="btn" href="' +
        escapeHtml(portalLoginUrl()) +
        '">会员登录</a></p></div>';
    }
    return (
      "<h1>" +
      escapeHtml(detail.title || "公告详情") +
      "</h1>" +
      '<p class="muted">' +
      escapeHtml(
        [detail.siteLabel, detail.noticeKind, formatDate(detail.publishTime || detail.publishedAt)]
          .filter(Boolean)
          .join(" · ")
      ) +
      "</p>" +
      '<div class="notice-detail-grid">' +
      "<div><span>采购单位</span><strong>" +
      escapeHtml(buyer) +
      "</strong></div>" +
      "<div><span>项目编号</span><strong>" +
      escapeHtml(projectCode) +
      "</strong></div>" +
      "<div><span>区域</span><strong>" +
      escapeHtml(detail.regionName || "—") +
      "</strong></div>" +
      "<div><span>金额</span><strong>" +
      escapeHtml(amount) +
      "</strong></div>" +
      "<div><span>进度</span><strong>" +
      escapeHtml(detail.progressLabel || detail.bidStatus || "—") +
      "</strong></div>" +
      "<div><span>联系人</span><strong>" +
      escapeHtml(contact) +
      "</strong></div>" +
      "</div>" +
      content +
      '<div class="detail-actions">' +
      '<a class="btn secondary" href="/notices">返回壹采寻源</a>' +
      (detail.sourceUrl || detail.detailUrl
        ? '<a class="btn' +
          (loggedIn ? "" : " ghost") +
          '" href="' +
          (loggedIn ? escapeHtml(detail.sourceUrl || detail.detailUrl) : escapeHtml(portalLoginUrl())) +
          '"' +
          (loggedIn ? ' target="_blank" rel="noopener"' : "") +
          ">" +
          (loggedIn ? "打开原文" : "登录后查看原文") +
          "</a>"
        : "") +
      "</div>"
    );
  }

  function bootDetail() {
    var root = document.getElementById("notice-detail");
    if (!root) return;
    var parts = location.pathname.split("/").filter(Boolean);
    var id = parts[parts.length - 1];
    // 有 SSR 内容时先保留标题骨架，避免整页闪白；登录态判定后再统一套打码/全文
    var hadSsr = Boolean(root.getAttribute("data-ssr-ready") || root.querySelector("h1"));
    if (!hadSsr) {
      root.innerHTML = '<p class="notice-loading">公告加载中…</p>';
    }
    Promise.all([
      fetchMe(),
      fetch("/api/public/notices/" + encodeURIComponent(id) + "/", { headers: { Accept: "application/json" } }).then(
        function (res) {
          return res.json().then(function (body) {
            if (!res.ok) throw new Error((body && body.detail) || "加载失败");
            return body.data || body;
          });
        }
      ),
    ])
      .then(function (pair) {
        var account = pair[0];
        var detail = pair[1];
        me = account || null;
        root.innerHTML = renderDetailHtml(detail, Boolean(me));
        root.setAttribute("data-hydrated", "1");
      })
      .catch(function (error) {
        root.innerHTML = '<p class="notice-empty">' + escapeHtml(error.message || "加载失败") + "</p>";
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
