(function () {
  var PAGE_SIZE = 10;

  function qs(name) {
    return new URLSearchParams(window.location.search).get(name) || "";
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

  function formatDate(value) {
    if (!value) return "—";
    var text = String(value);
    if (text.length >= 10) return text.slice(0, 10);
    return text;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function listPath(options) {
    options = options || {};
    var params = new URLSearchParams();
    if (options.page && options.page > 1) params.set("page", String(options.page));
    if (options.kind && options.kind !== "全部") params.set("kind", options.kind);
    if (options.search) params.set("search", options.search);
    var qsText = params.toString();
    return qsText ? "/notices?" + qsText : "/notices";
  }

  function detailPath(id) {
    return "/notices/" + encodeURIComponent(id);
  }

  function fetchJson(url) {
    var controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    var timer = controller
      ? setTimeout(function () {
          controller.abort();
        }, 12000)
      : null;
    return fetch(url, {
      headers: { Accept: "application/json" },
      signal: controller ? controller.signal : undefined,
    })
      .then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (body) {
          if (!response.ok) {
            throw new Error((body && body.detail) || ("HTTP " + response.status));
          }
          return body;
        });
      })
      .catch(function (error) {
        if (error && error.name === "AbortError") {
          throw new Error("请求超时，请刷新重试");
        }
        throw error;
      })
      .finally(function () {
        if (timer) clearTimeout(timer);
      });
  }

  function renderFilters(kinds, active) {
    var root = document.getElementById("notice-filters");
    if (!root) return;
    var items = ["全部"].concat(kinds || []);
    root.innerHTML = items.map(function (kind) {
      var current = active || "全部";
      var href = listPath({ page: 1, kind: kind, search: state.search });
      return '<a class="notice-filter ' + (kind === current ? "active" : "") + '" href="' + escapeHtml(href) + '" data-kind="' + escapeHtml(kind) + '">' + escapeHtml(kind) + "</a>";
    }).join("");
  }

  function renderList(payload) {
    var list = document.getElementById("notice-list");
    var empty = document.getElementById("notice-empty");
    var pager = document.getElementById("notice-pager");
    if (!list) return;
    var items = payload.items || [];
    if (!items.length) {
      list.innerHTML = "";
      if (empty) {
        empty.hidden = false;
        empty.textContent = "暂无公开公告";
      }
      if (pager) pager.innerHTML = "";
      return;
    }
    if (empty) empty.hidden = true;
    list.innerHTML = items.map(function (item) {
      return (
        '<a class="notice-item" href="' + detailPath(item.id) + '">' +
          "<div>" +
            "<h2>" + escapeHtml(item.title) + "</h2>" +
            '<div class="meta">' +
              "<span>项目编号 " + escapeHtml(item.projectNumber || "—") + "</span>" +
              "<span>" + escapeHtml(item.department || "—") + "</span>" +
              "<span>" + escapeHtml(formatDate(item.publishedAt)) + "</span>" +
              "<span>" + escapeHtml(money(item.amount)) + "</span>" +
            "</div>" +
          "</div>" +
          '<span class="kind">' + escapeHtml(item.noticeKind || "公告") + "</span>" +
        "</a>"
      );
    }).join("");

    if (!pager) return;
    var page = payload.page || 1;
    var totalPages = Math.max(1, Math.ceil((payload.total || 0) / (payload.page_size || PAGE_SIZE)));
    var prevHref = page > 1 ? listPath({ page: page - 1, kind: state.kind, search: state.search }) : "";
    var nextHref = page < totalPages ? listPath({ page: page + 1, kind: state.kind, search: state.search }) : "";
    pager.innerHTML =
      (prevHref ? '<a class="pager-link" href="' + escapeHtml(prevHref) + '" rel="prev">上一页</a>' : '<span class="pager-link disabled">上一页</span>') +
      "<strong>" + page + " / " + totalPages + "（共 " + (payload.total || 0) + " 条）</strong>" +
      (nextHref ? '<a class="pager-link" href="' + escapeHtml(nextHref) + '" rel="next">下一页</a>' : '<span class="pager-link disabled">下一页</span>');
  }

  var state = {
    page: Math.max(1, Number(qs("page") || "1") || 1),
    kind: qs("kind") || qs("noticeKind") || "全部",
    search: qs("search") || "",
  };

  function loadList(options) {
    options = options || {};
    state.page = options.page || state.page || 1;
    state.kind = options.kind || state.kind || "全部";
    if (typeof options.search === "string") state.search = options.search;
    var loading = document.getElementById("notice-loading");
    var list = document.getElementById("notice-list");
    var empty = document.getElementById("notice-empty");
    if (loading) loading.hidden = false;
    if (list) list.innerHTML = "";
    if (empty) empty.hidden = true;

    var url = new URL("/api/public/notices/", window.location.origin);
    url.searchParams.set("page", String(state.page));
    url.searchParams.set("page_size", String(PAGE_SIZE));
    if (state.search) url.searchParams.set("search", state.search);
    if (state.kind && state.kind !== "全部") url.searchParams.set("noticeKind", state.kind);

    return fetchJson(url.toString())
      .then(function (payload) {
        renderFilters(payload.kinds, state.kind);
        renderList(payload);
        if (options.pushState !== false && window.history && window.history.replaceState) {
          window.history.replaceState({}, "", listPath(state));
        }
      })
      .catch(function (error) {
        if (empty) {
          empty.hidden = false;
          empty.textContent = "公告加载失败：" + (error.message || "请稍后重试");
        }
      })
      .finally(function () {
        if (loading) loading.hidden = true;
      });
  }

  function bindListPage() {
    var searchInput = document.getElementById("notice-search");
    var searchBtn = document.getElementById("notice-search-btn");
    var ssr = document.body.getAttribute("data-ssr") === "1";

    if (searchInput && !searchInput.value && state.search) {
      searchInput.value = state.search;
    }

    if (searchBtn && searchInput) {
      searchBtn.addEventListener("click", function () {
        window.location.href = listPath({ page: 1, kind: state.kind, search: searchInput.value.trim() });
      });
      searchInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
          event.preventDefault();
          window.location.href = listPath({ page: 1, kind: state.kind, search: searchInput.value.trim() });
        }
      });
    }

    // SSR 页面已有可抓取内容；筛选/分页走真实链接整页刷新，利于 SEO。
    // 仅在非 SSR 兜底时用客户端拉取。
    if (!ssr) {
      loadList({ page: state.page, kind: state.kind, search: state.search, pushState: false });
    }
  }

  function bindDetailPage() {
    if (document.body.getAttribute("data-ssr") === "1") return;
    var id = qs("id");
    if (!id) {
      var parts = window.location.pathname.split("/").filter(Boolean);
      if (parts[0] === "notices" && parts[1]) id = decodeURIComponent(parts[1]);
    }
    var root = document.getElementById("notice-detail");
    if (!root) return;
    if (!id) {
      root.innerHTML = "<p>未指定公告。</p>";
      return;
    }
    root.innerHTML = "<p>加载中...</p>";
    fetchJson("/api/public/notices/" + encodeURIComponent(id) + "/")
      .then(function (body) {
        var item = body.data || {};
        document.title = (item.title || "公告详情") + " | 壹采";
        root.innerHTML =
          "<h1>" + escapeHtml(item.title || "未命名公告") + "</h1>" +
          '<div class="detail-grid">' +
            "<div><span>公告类型</span><strong>" + escapeHtml(item.noticeKind || "—") + "</strong></div>" +
            "<div><span>项目编号</span><strong>" + escapeHtml(item.projectNumber || "—") + "</strong></div>" +
            "<div><span>采购单位</span><strong>" + escapeHtml(item.department || "—") + "</strong></div>" +
            "<div><span>供应商</span><strong>" + escapeHtml(item.supplierName || "—") + "</strong></div>" +
            "<div><span>状态</span><strong>" + escapeHtml(item.bidStatus || "—") + "</strong></div>" +
            "<div><span>金额</span><strong>" + escapeHtml(money(item.amount)) + "</strong></div>" +
            "<div><span>发布时间</span><strong>" + escapeHtml(formatDate(item.publishedAt)) + "</strong></div>" +
            "<div><span>联系人</span><strong>" + escapeHtml([item.contactName, item.contactPhone].filter(Boolean).join(" ") || "—") + "</strong></div>" +
          "</div>" +
          (item.content ? '<div class="detail-content">' + escapeHtml(item.content) + "</div>" : "") +
          '<div class="detail-actions">' +
            '<a class="btn secondary" href="/notices">返回公告列表</a>' +
            (item.detailUrl ? '<a class="btn" href="' + escapeHtml(item.detailUrl) + '" target="_blank" rel="noreferrer">查看原始详情</a>' : "") +
            '<a class="btn" href="/index.html#contact">咨询入驻</a>' +
          "</div>";
      })
      .catch(function (error) {
        root.innerHTML = "<p>公告加载失败：" + escapeHtml(error.message || "请稍后重试") + "</p>";
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var menuBtn = document.querySelector(".mobile-menu-btn");
    var menu = document.querySelector(".nav-menu");
    if (menuBtn && menu) {
      menuBtn.addEventListener("click", function () {
        menu.classList.toggle("active");
      });
    }
    if (document.body.getAttribute("data-page") === "notice-list") bindListPage();
    if (document.body.getAttribute("data-page") === "notice-detail") bindDetailPage();
  });
})();
