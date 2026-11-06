import { useEffect, useState } from "react";
import { backendApiUrl } from "./apiConfig";
import { AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";


const STATUS_FILTERS = [
  { key: "", label: "全部" },
  { key: "completed", label: "已完成" },
  { key: "failed", label: "失败" },
  { key: "running", label: "执行中" },
  { key: "awaiting_confirmation", label: "待确认" },
] as const;

const STATUS_LABEL: Record<string, string> = {
  pending: "待执行",
  running: "执行中",
  awaiting_confirmation: "待确认",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

type McpLogItem = {
  id: number;
  userId: string;
  userName: string;
  toolName: string;
  status: string;
  summary: string;
  errorCode: string;
  durationMs: number | null;
  parameters: Record<string, unknown>;
  createdAt: string;
  completedAt: string;
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

function formatParams(params: Record<string, unknown>) {
  const keys = Object.keys(params || {});
  if (!keys.length) return "—";
  try {
    const text = JSON.stringify(params);
    return text.length > 120 ? `${text.slice(0, 117)}…` : text;
  } catch {
    return "—";
  }
}

async function fetchMcpLogs(options: {
  page: number;
  pageSize: number;
  search: string;
  status: string;
}): Promise<{ items: McpLogItem[]; total: number }> {
  const params = new URLSearchParams({
    page: String(options.page),
    page_size: String(options.pageSize),
  });
  if (options.search.trim()) params.set("search", options.search.trim());
  if (options.status) params.set("status", options.status);
  const response = await fetch(backendApiUrl(`/api/assistant/mcp-logs/?${params.toString()}`), {
    credentials: "include",
  });
  if (response.status === 401) throw new AuthExpiredError();
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "MCP 调用日志加载失败");
  return {
    items: Array.isArray(body.items) ? body.items : [],
    total: Number(body.total) || 0,
  };
}

export function McpCallLogs({
  onNotice,
}: {
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
}) {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounced(search);
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(20);
  const [items, setItems] = useState<McpLogItem[]>([]);
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
    void fetchMcpLogs({
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
        if (cancelled || error instanceof AuthExpiredError) return;
        onNotice({ type: "error", message: error instanceof Error ? error.message : "MCP 调用日志加载失败" });
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
            <h2>MCP调用日志</h2>
            <p>记录企微连接器等 MCP 工具调用；仅开发相关角色可查看。</p>
          </div>
        </div>

        <div className="platform-account-toolbar">
          <SearchField value={search} onChange={setSearch} placeholder="搜索工具名、用户、摘要…" />
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
          <div className="table-row mcp-log-table head">
            <span>工具</span>
            <span>调用人</span>
            <span>状态</span>
            <span>摘要</span>
            <span>参数</span>
            <span>耗时</span>
            <span>时间</span>
          </div>
          {items.map((item) => (
            <div className="table-row mcp-log-table" key={item.id}>
              <div className="mcp-log-main-cell">
                <CopyableLine text={item.toolName} label="工具名">
                  <strong>{item.toolName}</strong>
                </CopyableLine>
                <em>#{item.id}</em>
              </div>
              <div className="mcp-log-main-cell">
                <CopyableLine text={item.userName || item.userId} label="调用人">
                  <strong>{item.userName || item.userId || "—"}</strong>
                </CopyableLine>
                {item.userName && item.userId && item.userName !== item.userId ? <em>{item.userId}</em> : null}
              </div>
              <div>
                <span className="tag">{STATUS_LABEL[item.status] || item.status || "—"}</span>
                {item.errorCode ? <em>{item.errorCode}</em> : null}
              </div>
              <div className="mcp-log-summary-cell">{item.summary || "—"}</div>
              <div className="mcp-log-summary-cell">{formatParams(item.parameters)}</div>
              <span>{item.durationMs != null ? `${item.durationMs} ms` : "—"}</span>
              <div className="mcp-log-main-cell">
                <span>{formatTime(item.createdAt)}</span>
                {item.completedAt ? <em>完成 {formatTime(item.completedAt)}</em> : null}
              </div>
            </div>
          ))}
          {items.length === 0 && (
            <div className="table-empty">{loading ? "加载中…" : "暂无数据"}</div>
          )}
        </div>

        <Pagination page={page} totalPages={totalPages} total={total} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />
      </div>
    </div>
  );
}
