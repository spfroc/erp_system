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
      progress: "ongoing,upcoming,ended",
      // 正向包含开放类公告，避免 exclude 多类型时 SQL 过重
      noticeKinds: "采购公告,竞价公告,询比公告,更正公告,单一来源公示,竞价项目",
      excludeNoticeKinds: "",
      kindLabel: "采购方式",
      kindChips: [
        { value: "", label: "全部" },
        { value: "竞价", label: "竞价" },
        { value: "反拍", label: "反拍" },
        { value: "询比", label: "询比" },
        { value: "招标", label: "招标" },
      ],
      kindMode: "procurementMode",
      hint: "进行中 / 未开始 / 已结束的采购机会",
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
    { value: "upcoming", label: "未开始" },
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
    { field: "publishTime", label: "公告发布时间" },
    { field: "endTime", label: "截止时间" },
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

  function formatDateTime(value) {
    if (!value) return "—";
    var text = String(value).trim().replace("T", " ");
    if (text.length >= 16) return text.slice(0, 16);
    if (text.length >= 10) return text.slice(0, 10);
    return text;
  }

  var SHANDONG_CITIES = [
    "济南",
    "青岛",
    "淄博",
    "枣庄",
    "东营",
    "烟台",
    "潍坊",
    "济宁",
    "泰安",
    "威海",
    "日照",
    "临沂",
    "德州",
    "聊城",
    "滨州",
    "菏泽",
  ];

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

  function countdownInfo(item, options) {
    var opts = options || {};
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
        text: opts.hideStartCountdown
          ? ""
          : start
            ? "距开始 " + formatCountdown(start - now)
            : "即将开始",
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
    var tab = currentTab();
    if (tab && tab.id === "intent") {
      return [{ field: "publishTime", label: "发布时间" }];
    }
    return canSortByStartTime() ? SORT_FIELDS_WITH_START : SORT_FIELDS_BASE;
  }

  function normalizeSortForTab() {
    var fields = currentSortFields().map(function (item) {
      return item.field;
    });
    var field = sortFieldOf(state.sort);
    if (field && fields.indexOf(field) < 0) {
      state.sort = DEFAULT_SORT;
    }
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
    normalizeSortForTab();
  }

  function renderSortChips() {
    var fields = currentSortFields();
    return fields
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
          '<button type="button" class="sourcing-sort-link' +
          (active ? " active" : "") +
          '" data-sort-field="' +
          escapeHtml(item.field) +
          '" title="' +
          escapeHtml(title) +
          '" aria-label="' +
          escapeHtml(title) +
          '">' +
          escapeHtml(item.label) +
          (arrow
            ? '<span class="sort-arrow" aria-hidden="true">' + arrow + "</span>"
            : '<span class="sort-arrow muted" aria-hidden="true">↕</span>') +
          "</button>"
        );
      })
      .join("");
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
    // 区域由级联组件直接写入 state.regionName
    state.buyerName = "";
  }

  function regionCascadeLabel() {
    var city = state.regionName || "";
    if (city && SHANDONG_CITIES.indexOf(city) >= 0) return "山东省 / " + city;
    if (city) return city;
    return "全部";
  }

  function regionCascadeHtml() {
    var city = state.regionName || "";
    var provinceOpen = city && SHANDONG_CITIES.indexOf(city) >= 0;
    var labelText = city ? regionCascadeLabel() : "请选择";
    return (
      '<div class="field region-cascader sourcing-region-inline" data-region-cascader>' +
      '<span class="field-label">所属区域：</span>' +
      '<button type="button" class="region-cascader-trigger" data-role="region-trigger" aria-haspopup="listbox" aria-expanded="false">' +
      '<em data-role="region-label">' +
      escapeHtml(labelText) +
      "</em><i></i></button>" +
      '<div class="region-cascader-panel" data-role="region-panel" hidden>' +
      '<div class="region-cascader-col" data-level="1">' +
      '<button type="button" class="region-cascader-option' +
      (!city ? " active" : "") +
      '" data-province="">全部</button>' +
      '<button type="button" class="region-cascader-option' +
      (provinceOpen || city === "山东省" ? " active" : "") +
      '" data-province="山东省">山东省</button>' +
      "</div>" +
      '<div class="region-cascader-col" data-level="2"' +
      (provinceOpen ? "" : " hidden") +
      ">" +
      SHANDONG_CITIES.map(function (name) {
        return (
          '<button type="button" class="region-cascader-option' +
          (city === name ? " active" : "") +
          '" data-city="' +
          escapeHtml(name) +
          '">' +
          escapeHtml(name) +
          "</button>"
        );
      }).join("") +
      "</div></div></div>"
    );
  }

  function closeRegionCascade(root) {
    if (!root) return;
    var panel = root.querySelector("[data-role=region-panel]");
    var trigger = root.querySelector("[data-role=region-trigger]");
    if (panel) panel.hidden = true;
    if (trigger) trigger.setAttribute("aria-expanded", "false");
  }

  function bindRegionCascade(root) {
    if (!root) return;
    var wrap = root.querySelector("[data-region-cascader]");
    if (!wrap) return;
    var trigger = wrap.querySelector("[data-role=region-trigger]");
    var panel = wrap.querySelector("[data-role=region-panel]");
    var cityCol = wrap.querySelector('[data-level="2"]');
    var label = wrap.querySelector("[data-role=region-label]");
    if (!trigger || !panel) return;

    function applyRegion(next) {
      var value = String(next || "").trim();
      if (state.regionName === value) {
        closeRegionCascade(root);
        return;
      }
      state.regionName = value;
      if (label) label.textContent = value ? regionCascadeLabel() : "请选择";
      closeRegionCascade(root);
      state.page = 1;
      loadList();
    }

    trigger.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      var open = panel.hidden;
      panel.hidden = !open;
      trigger.setAttribute("aria-expanded", open ? "true" : "false");
    });

    panel.addEventListener("click", function (event) {
      event.stopPropagation();
      var btn = event.target.closest("button[data-province],button[data-city]");
      if (!btn) return;
      if (btn.hasAttribute("data-city")) {
        applyRegion(btn.getAttribute("data-city") || "");
        return;
      }
      var province = btn.getAttribute("data-province") || "";
      if (!province) {
        if (cityCol) cityCol.hidden = true;
        panel.querySelectorAll("[data-province]").forEach(function (item) {
          item.classList.toggle("active", !item.getAttribute("data-province"));
        });
        applyRegion("");
        return;
      }
      // 选中省级后展开市级，等选城市再生效
      if (cityCol) cityCol.hidden = false;
      panel.querySelectorAll("[data-province]").forEach(function (item) {
        item.classList.toggle("active", item.getAttribute("data-province") === province);
      });
    });

    if (!bindRegionCascade._docBound) {
      document.addEventListener("click", function () {
        // 区域级联在结果工具栏，不在 filters
        closeRegionCascade(document.getElementById("sourcing-resultbar"));
        closeRegionCascade(document.getElementById("sourcing-filters"));
      });
      bindRegionCascade._docBound = true;
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
    html += chipRow("采购平台", siteChips, state.siteId, "siteId");
    if (tab.kindChips && tab.kindChips.length) {
      var activeKind = tab.kindMode === "procurementMode" ? state.procurementMode : state.resultKind;
      html += chipRow(tab.kindLabel || "公告类型", tab.kindChips, activeKind, tab.kindMode);
    }
    if (tab.id === "opportunity") {
      html += chipRow("状态", PROGRESS_CHIPS, state.progress, "progress");
    }
    html += chipRow("采购预算", BUDGET_CHIPS, state.budgetRange, "budgetRange");
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

  function bindToolbarControls(root, totalPages) {
    if (!root) return;
    root.querySelectorAll("[data-sort-field]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        cycleSortField(btn.getAttribute("data-sort-field") || "");
        state.page = 1;
        renderFilters();
        loadList();
      });
    });
    bindRegionCascade(root);
    root.querySelectorAll("button[data-mini-page]").forEach(function (btn) {
      btn.onclick = function () {
        if (btn.disabled) return;
        var action = btn.getAttribute("data-mini-page");
        if (action === "prev") goPage(state.page - 1, totalPages);
        else if (action === "next") goPage(state.page + 1, totalPages);
      };
    });
  }

  function renderTopToolbar(total, totalPages) {
    var resultBar = document.getElementById("sourcing-resultbar");
    if (!resultBar) return;
    normalizeSortForProgress();
    var pages = Math.max(1, totalPages || 1);
    resultBar.innerHTML =
      '<div class="sourcing-toolbar-left">' +
      '<div class="sourcing-sort-inline">' +
      renderSortChips() +
      "</div>" +
      regionCascadeHtml() +
      "</div>" +
      '<div class="sourcing-toolbar-right pager-mini">' +
      '<span class="pager-total">共' +
      Number(total || 0) +
      "个结果</span>" +
      '<span class="pager-sep">|</span>' +
      '<button type="button" data-mini-page="prev" aria-label="上一页"' +
      (state.page <= 1 ? " disabled" : "") +
      ">&lt;</button>" +
      "<strong>" +
      state.page +
      "/" +
      pages +
      "</strong>" +
      '<button type="button" data-mini-page="next" aria-label="下一页"' +
      (state.page >= pages ? " disabled" : "") +
      ">&gt;</button>" +
      "</div>";
    bindToolbarControls(resultBar, pages);
  }

  function renderPagination(total, totalPages) {
    var pager = document.getElementById("notice-pager");
    var pages = Math.max(1, totalPages || 1);
    var summary =
      "共 <strong>" +
      total +
      "</strong> 条 · 第 " +
      state.page +
      " / " +
      pages +
      " 页";
    renderTopToolbar(total, pages);
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
      pages +
      "</strong>" +
      '<button type="button" class="btn ghost" data-page="' +
      (state.page + 1) +
      '"' +
      (state.page >= pages ? " disabled" : "") +
      ">下一页</button>" +
      '<button type="button" class="btn ghost" data-page="' +
      pages +
      '"' +
      (state.page >= pages ? " disabled" : "") +
      ">末页</button>" +
      "</div>" +
      '<label class="pagination-jump">跳至' +
      '<input type="number" min="1" max="' +
      pages +
      '" value="' +
      state.page +
      '" data-role="jump-page" />页' +
      '<button type="button" class="btn ghost" data-role="jump-go">跳转</button></label>' +
      "</div>";

    pager.querySelectorAll("button[data-page]").forEach(function (btn) {
      btn.onclick = function () {
        if (btn.disabled) return;
        goPage(btn.getAttribute("data-page"), pages);
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
      goPage(jumpInput && jumpInput.value, pages);
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
    if (item.procurementMode) tags.push(item.procurementMode);
    if (item.regionName) tags.push(item.regionName);
    return tags.slice(0, 3);
  }

  function noticeKindPrefix(item) {
    var kind = String((item && item.noticeKind) || "").trim();
    if (!kind) return "";
    return "【" + kind + "】";
  }

  function renderCardBody(item, tab) {
    var method = methodLabel(item);
    var tags = cardTags(item);
    var statusHtml = "";
    var fieldsHtml = "";

    if (tab.id === "result") {
      fieldsHtml =
        "<div>成交金额：<b>" +
        escapeHtml(money(item.dealAmount)) +
        "</b></div>" +
        "<div>预算金额：<b>" +
        escapeHtml(money(item.budgetAmount)) +
        "</b></div>" +
        "<div>成交时间：" +
        escapeHtml(formatDateTime(item.endTime || item.publishTime || item.publishedAt)) +
        "</div>" +
        "<div>发布时间：" +
        escapeHtml(formatDateTime(item.publishTime || item.publishedAt)) +
        "</div>" +
        "<div>采购方式：" +
        escapeHtml(method || "—") +
        "</div>";
    } else if (tab.id === "intent") {
      // 采购意向不展示开始/结束状态条
      statusHtml = "";
      fieldsHtml =
        "<div>采购预算：<b>" +
        escapeHtml(money(item.budgetAmount || item.dealAmount)) +
        "</b></div>" +
        "<div>发布时间：" +
        escapeHtml(formatDateTime(item.publishTime || item.publishedAt)) +
        "</div>" +
        "<div>采购单位：" +
        escapeHtml(item.buyerName || "—") +
        "</div>";
    } else {
      var clock = countdownInfo(item);
      statusHtml =
        '<div class="notice-card-status tone-' +
        escapeHtml(clock.tone) +
        '"><strong>' +
        escapeHtml(clock.label) +
        "</strong><em class='countdown'>" +
        escapeHtml(clock.text || "") +
        "</em></div>";
      fieldsHtml =
        "<div>采购预算：<b>" +
        escapeHtml(money(item.budgetAmount || item.dealAmount)) +
        "</b></div>" +
        "<div>开始时间：" +
        escapeHtml(formatDateTime(item.startTime)) +
        "</div>" +
        "<div>结束时间：" +
        escapeHtml(formatDateTime(item.endTime)) +
        "</div>" +
        "<div>采购方式：" +
        escapeHtml(method || "—") +
        "</div>" +
        "<div>采购单位：" +
        escapeHtml(item.buyerName || "—") +
        "</div>";
    }

    return (
      statusHtml +
      '<div class="notice-card-fields">' +
      fieldsHtml +
      "</div>" +
      '<div class="notice-card-tags">' +
      tags
        .map(function (tag) {
          return "<span>" + escapeHtml(tag) + "</span>";
        })
        .join("") +
      "</div>"
    );
  }

  function renderList(payload) {
    var list = document.getElementById("notice-list");
    var empty = document.getElementById("notice-empty");
    if (!list) return;
    var tab = currentTab();
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
        var href = "/notices/" + encodeURIComponent(item.id);
        var kindPrefix = noticeKindPrefix(item);
        return (
          '<a class="notice-card" href="' +
          escapeHtml(href) +
          '" data-id="' +
          escapeHtml(item.id) +
          '">' +
          "<h3>" +
          (kindPrefix ? '<span class="notice-kind-prefix">' + escapeHtml(kindPrefix) + "</span>" : "") +
          escapeHtml(item.title || "未命名公告") +
          "</h3>" +
          renderCardBody(item, tab) +
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
        var nextSites = Array.isArray(body.sites) ? body.sites : [];
        if (nextSites.length) {
          var prev = sites
            .map(function (site) {
              return String(site.id) + ":" + String(site.label);
            })
            .join("|");
          var next = nextSites
            .map(function (site) {
              return String(site.id) + ":" + String(site.label);
            })
            .join("|");
          if (prev !== next) {
            sites = nextSites;
            renderFilters();
          }
        }
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
    normalizeSortForTab();
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
    // 列表不依赖登录态，并行探测会员，避免首屏被 /api/portal/me 阻塞
    fetchMe();
    loadList();
  }

  function sanitizeNoticeHtml(raw) {
    var text = String(raw == null ? "" : raw);
    if (!text) return "";
    return text
      .replace(/<(script|style|iframe|object|embed)[\s\S]*?<\/\1>/gi, "")
      .replace(/on[a-z]+\s*=\s*(['"]).*?\1/gi, "")
      .replace(/on[a-z]+\s*=\s*[^\s>]+/gi, "")
      .replace(/\s(href|src)\s*=\s*(['"])\s*javascript:[^'"]*\2/gi, ' $1="#"');
  }

  function maskSensitiveNoticeText(value, extras) {
    var text = String(value == null ? "" : value);
    if (!text) return text;
    text = text.replace(
      /((?:项目|采购人|采购单位)?联系人|联系方式|联系电话|手机号码?|电话(?:号码)?)\s*[:：]\s*([^\n\r<，,；;。、]{1,30})/g,
      "$1：登录可见"
    );
    text = text.replace(/(?<!\d)(1[3-9]\d{9})(?!\d)/g, "登录可见");
    // 未标注固话要求带分隔符，避免误伤项目编号
    text = text.replace(/(?<!\d)(0\d{2,3}-\d{7,8})(?!\d)/g, "登录可见");
    text = text.replace(/[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}/g, "登录可见");
    (extras || []).forEach(function (extra) {
      var token = String(extra || "").trim();
      if (token.length < 2 || token === "登录可见") return;
      text = text.split(token).join("登录可见");
    });
    return text;
  }

  function neutralizeAttachmentLinks(html) {
    return String(html || "").replace(
      /<a\b([^>]*?)href\s*=\s*(['"])(.*?)\2([^>]*)>([\s\S]*?)<\/a>/gi,
      function (all, pre, q, href, post, inner) {
        var label = String(inner || "").replace(/<[^>]+>/g, "");
        if (/\.(pdf|docx?|xlsx?|xls|zip|rar|7z|wps|ofd|csv|pptx?)(\?|#|$)/i.test(href) || /附件/.test(label)) {
          return '<span class="attachment-locked">登录后可下载附件</span>';
        }
        return all;
      }
    );
  }

  function wrapGuestContent(innerHtml, isHtml) {
    return (
      '<div class="detail-content-clamp">' +
      '<div class="detail-content' +
      (isHtml ? " is-html" : "") +
      '">' +
      innerHtml +
      "</div>" +
      '<div class="detail-content-fade" aria-hidden="true"></div>' +
      '<div class="detail-login-gate">' +
      "<p>登录后查看完整公告正文与附件</p>" +
      '<a class="btn" href="' +
      escapeHtml(portalLoginUrl()) +
      '">会员登录</a>' +
      "</div>" +
      "</div>"
    );
  }

  function renderDetailContent(detail, loggedIn) {
    var extras = [
      detail.contactName,
      detail.buyerContactName,
      detail.contactPhone,
      detail.buyerPhone,
    ];
    var html = String(detail.contentHtml || "").trim();
    var text = String(detail.content || detail.contentText || "").trim();
    if (!loggedIn) {
      html = neutralizeAttachmentLinks(maskSensitiveNoticeText(html, extras));
      text = neutralizeAttachmentLinks(maskSensitiveNoticeText(text, extras));
    }
    if (html) {
      var safeHtml = sanitizeNoticeHtml(html);
      if (!loggedIn) return wrapGuestContent(safeHtml, true);
      return '<div class="detail-content is-html">' + safeHtml + "</div>";
    }
    if (text) {
      var safeText = escapeHtml(text);
      if (!loggedIn) return wrapGuestContent(safeText, false);
      return '<div class="detail-content">' + safeText + "</div>";
    }
    return '<div class="detail-content muted">暂无正文内容</div>';
  }

  function renderDetailHtml(detail, loggedIn) {
    var buyer = detail.buyerName || detail.department || "—";
    var amount = money(detail.budgetAmount || detail.dealAmount || detail.amount);
    var contactName = String(detail.contactName || detail.buyerContactName || "").trim();
    var contactPhone = String(detail.contactPhone || detail.buyerPhone || "").trim();
    var maskedContact =
      '<span class="contact-masked">登录可见</span> <a class="link-login" href="' +
      escapeHtml(portalLoginUrl()) +
      '">会员登录</a>';
    var projectCode = detail.projectCode || detail.projectNumber || "—";
    var projectName = detail.projectName || "—";
    var sourceUrl = detail.sourceUrl || detail.detailUrl || "";
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
      "<div><span>项目名称</span><strong>" +
      escapeHtml(projectName) +
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
      "<div><span>开始时间</span><strong>" +
      escapeHtml(formatDateTime(detail.startTime || detail.startAt)) +
      "</strong></div>" +
      "<div><span>结束时间</span><strong>" +
      escapeHtml(formatDateTime(detail.endTime || detail.endAt)) +
      "</strong></div>" +
      "<div><span>联系人</span><strong>" +
      (loggedIn ? escapeHtml(contactName || "—") : maskedContact) +
      "</strong></div>" +
      "<div><span>联系方式</span><strong>" +
      (loggedIn ? escapeHtml(contactPhone || "—") : maskedContact) +
      "</strong></div>" +
      "</div>" +
      renderDetailContent(detail, loggedIn) +
      '<div class="detail-actions">' +
      '<a class="btn secondary" href="/notices">返回壹采寻源</a>' +
      (loggedIn && sourceUrl
        ? '<a class="btn" href="' +
          escapeHtml(sourceUrl) +
          '" target="_blank" rel="noopener">打开原文</a>'
        : "") +
      (!loggedIn
        ? '<a class="btn ghost" href="' + escapeHtml(portalLoginUrl()) + '">会员登录查看全文与附件</a>'
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
        if (!me) {
          root.addEventListener("click", function (event) {
            var anchor = event.target && event.target.closest ? event.target.closest("a[href]") : null;
            if (!anchor || !root.contains(anchor)) return;
            var href = anchor.getAttribute("href") || "";
            var label = String(anchor.textContent || "");
            if (/\.(pdf|docx?|xlsx?|xls|zip|rar|7z|wps|ofd|csv|pptx?)(\?|#|$)/i.test(href) || /附件|下载/.test(label)) {
              event.preventDefault();
              window.location.href = portalLoginUrl();
            }
          });
        }
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
