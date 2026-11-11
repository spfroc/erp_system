import { useEffect, useState } from "react";
import { backendApiUrl } from "./apiConfig";
import { AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";

const STATUS_FILTERS = [
  { key: "", label: "全部" },
  { key: "sent", label: "已发送" },
  { key: "failed", label: "失败" },
  { key: "pending", label: "待发送" },
] as const;

const STATUS_LABEL: Record<string, string> = {
  sent: "已发送",
  failed: "失败",
  pending: "待发送",
};

type PushLogItem = {
  id: number;
  customerAccountId: string;
  accountName: string;
  customerName: string;
  phone: string;
  channel: string;
  digestDate: string;
  openid: string;
  noticeIds: number[];
  matchedCount: number;
  status: string;
  errcode: number;
  errmsg: string;
  createdAt: string;
  updatedAt: string;
};

function useDebounced(value: string, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function formatTime(value?: string) {
  if (!value) return "—";
  return value.replace("T", " ").replace(/\.\d+/, "").slice(0, 19);
}

async function fetchPushLogs(options: {
  page: number;
  pageSize: number;
  search: string;
  status: string;
}): Promise<{ items: PushLogItem[]; total: number }> {
  const params = new URLSearchParams({
    page: String(options.page),
    page_size: String(options.pageSize),
  });
  if (options.search.trim()) params.set("search", options.search.trim());
  if (options.status) params.set("status", options.status);
  const response = await fetch(backendApiUrl(`/api/wechat/mp/push-logs/?${params.toString()}`), {
    credentials: "include",
  });
  if (response.status === 401) throw new AuthExpiredError();
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "推送记录加载失败");
  return {
    items: Array.isArray(body.items) ? body.items : [],
    total: Number(body.total) || 0,
  };
}

export function WechatPushLogs({
  onNotice,
}: {
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
}) {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounced(search);
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(20);
  const [items, setItems] = useState<PushLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const setPageSize = (next: number) => {
    setPageSizeState(next);
    setPage(1);
  };

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, status]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void fetchPushLogs({
      page,
      pageSize,
      search: debouncedSearch,
      status,
    })
      .then((result) => {
        if (cancelled) return;
        setItems(result.items);
        setTotal(result.total);
      })
      .catch((error) => {
        if (cancelled) return;
        if (error instanceof AuthExpiredError) throw error;
        onNotice({ type: "error", message: error instanceof Error ? error.message : "加载失败" });
        setItems([]);
        setTotal(0);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page, pageSize, debouncedSearch, status, onNotice]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>消息推送记录</h2>
            <p>微信服务号模板消息发送日志。订阅命中公告会写入门户消息列表，再汇总推送一条通知。</p>
          </div>
        </div>
        <div className="platform-account-toolbar">
          <SearchField value={search} onChange={setSearch} placeholder="搜索账号、手机号、客户名、openid…" />
        </div>
        <div className="segmented">
          {STATUS_FILTERS.map((item) => (
            <button
              key={item.key || "all"}
              type="button"
              className={status === item.key ? "active" : ""}
              onClick={() => setStatus(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="table">
          <div className="table-row wechat-push-table head">
            <span>账号</span>
            <span>汇总日</span>
            <span>命中</span>
            <span>状态</span>
            <span>时间</span>
            <span>备注</span>
          </div>
          {items.map((item) => (
            <div className="table-row wechat-push-table" key={item.id}>
              <div className="wechat-push-main-cell">
                <CopyableLine text={item.accountName || item.customerAccountId} label="账号">
                  <strong>{item.accountName || item.customerAccountId}</strong>
                </CopyableLine>
                <em>
                  {[item.customerName, item.phone, item.customerAccountId].filter(Boolean).join(" · ")}
                </em>
              </div>
              <span>{item.digestDate || "—"}</span>
              <span>{item.matchedCount}</span>
              <span>{STATUS_LABEL[item.status] || item.status || "—"}</span>
              <span>
                <em>{formatTime(item.updatedAt || item.createdAt)}</em>
              </span>
              <span className="wrap">
                {item.status === "failed"
                  ? `${item.errcode || ""} ${item.errmsg || ""}`.trim() || "失败"
                  : item.openid
                    ? `openid …${item.openid.slice(-8)}`
                    : "—"}
              </span>
            </div>
          ))}
          {items.length === 0 && <div className="table-empty">{loading ? "加载中…" : "暂无数据"}</div>}
        </div>
        <Pagination
          page={page}
          totalPages={totalPages}
          total={total}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
        />
      </div>
    </div>
  );
}
