import { useEffect, useState } from "react";
import { Bell, RefreshCw, X } from "lucide-react";
import { createCollectionItem, createId, patchCollectionItem, queryCollection, AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";
import type {
  AppData,
  Notice,
  NoticeBidStatus,
  NoticeCollectionRun,
  NoticeCollectionSource,
  NoticeKind,
  PermissionKey,
} from "./types";

type CanAccess = (permission: PermissionKey) => boolean;

const PAGE_SIZE = 10;

const NOTICE_KINDS: Array<NoticeKind | "全部"> = [
  "全部",
  "竞价项目",
  "意向公开",
  "采购公告",
  "结果公告",
  "更正公告",
  "终止公告",
  "合同公告",
  "验收公告",
  "单一来源公示",
  "其他",
];

const BID_STATUSES: Array<NoticeBidStatus | "全部"> = ["全部", "竞价中", "已完成", "终止", "失败", "结果待确认"];

function apiUrl(path: string) {
  const url = new URL(path, window.location.origin);
  if (import.meta.env.DEV) url.port = "8000";
  return url.toString();
}

async function runNoticeCollection(payload: { sourceId?: string; ensureSample?: boolean; force?: boolean }) {
  const response = await fetch(apiUrl("/api/notices/collection-runs/"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (response.status === 401) throw new AuthExpiredError();
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "采集失败");
  return body.data as NoticeCollectionRun;
}

function useDebounced(value: string, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function money(value?: number) {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 2 }).format(value);
}

export function NoticesPanel({
  data,
  applyData,
  onNotice,
  can,
}: {
  data: AppData;
  applyData: (data: AppData) => void;
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  can: CanAccess;
}) {
  const canManage = can("notice.manage");
  const [tab, setTab] = useState<"list" | "collection">("list");
  const [search, setSearch] = useState("");
  const [noticeKind, setNoticeKind] = useState<string>("全部");
  const [bidStatus, setBidStatus] = useState<string>("全部");
  const [publicFilter, setPublicFilter] = useState<string>("全部");
  const debouncedSearch = useDebounced(search);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Notice[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);
  const [running, setRunning] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    title: "",
    projectNumber: "",
    department: "",
    category: "",
    noticeKind: "竞价项目" as NoticeKind,
    bidStatus: "竞价中" as NoticeBidStatus,
    amount: "",
    contactName: "",
    contactPhone: "",
    detailUrl: "",
    isPublic: true,
  });

  const [sources, setSources] = useState<NoticeCollectionSource[]>([]);
  const [runs, setRuns] = useState<NoticeCollectionRun[]>([]);
  const [sourceReload, setSourceReload] = useState(0);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, noticeKind, bidStatus, publicFilter]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void queryCollection<Notice>("notices", {
      page,
      pageSize: PAGE_SIZE,
      search: debouncedSearch,
      filters: {
        noticeKind: noticeKind === "全部" ? undefined : noticeKind,
        bidStatus: bidStatus === "全部" ? undefined : bidStatus,
        isPublic: publicFilter === "公开" ? "true" : publicFilter === "不公开" ? "false" : undefined,
      },
    })
      .then((result) => {
        if (cancelled) return;
        setItems(result.items);
        setTotal(result.total);
      })
      .catch((error) => {
        if (cancelled || error instanceof AuthExpiredError) return;
        onNotice({ type: "error", message: error instanceof Error ? error.message : "公告列表加载失败" });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page, debouncedSearch, noticeKind, bidStatus, publicFilter, reloadTick, data.notices, onNotice]);

  useEffect(() => {
    if (tab !== "collection") return;
    let cancelled = false;
    void Promise.all([
      queryCollection<NoticeCollectionSource>("noticeCollectionSources", { page: 1, pageSize: 50 }),
      queryCollection<NoticeCollectionRun>("noticeCollectionRuns", { page: 1, pageSize: 20 }),
    ])
      .then(([sourceResult, runResult]) => {
        if (cancelled) return;
        setSources(sourceResult.items);
        setRuns(runResult.items);
      })
      .catch((error) => {
        if (cancelled || error instanceof AuthExpiredError) return;
        onNotice({ type: "error", message: error instanceof Error ? error.message : "采集任务加载失败" });
      });
    return () => {
      cancelled = true;
    };
  }, [tab, sourceReload, data.noticeCollectionSources, data.noticeCollectionRuns, onNotice]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  async function togglePublic(item: Notice) {
    if (!canManage) return;
    try {
      const saved = await patchCollectionItem<Notice>("notices", item.id, { ...item, isPublic: !item.isPublic });
      applyData({
        ...data,
        notices: data.notices.some((row) => row.id === saved.id)
          ? data.notices.map((row) => (row.id === saved.id ? saved : row))
          : [saved, ...data.notices],
      });
      setReloadTick((value) => value + 1);
      onNotice({ type: "success", message: saved.isPublic ? "已公开到官网" : "已取消公开" });
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "更新失败" });
    }
  }

  async function saveNotice() {
    if (!canManage) return;
    const title = form.title.trim();
    if (!title) {
      window.alert("请填写公告标题");
      return;
    }
    const now = new Date().toISOString();
    const payload: Notice = {
      id: createId("notice"),
      title,
      projectNumber: form.projectNumber.trim(),
      department: form.department.trim(),
      category: form.category.trim(),
      noticeKind: form.noticeKind,
      bidStatus: form.bidStatus,
      amount: Number(form.amount || 0),
      contactName: form.contactName.trim(),
      contactPhone: form.contactPhone.trim(),
      detailUrl: form.detailUrl.trim(),
      isPublic: form.isPublic,
      source: "manual",
      publishedAt: now,
      createdAt: now,
      updatedAt: now,
    };
    try {
      const saved = await createCollectionItem<Notice>("notices", payload);
      applyData({ ...data, notices: [saved, ...data.notices] });
      setShowCreate(false);
      setReloadTick((value) => value + 1);
      onNotice({ type: "success", message: "公告已保存" });
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败" });
    }
  }

  async function triggerCollection(sourceId?: string, ensureSample = false) {
    if (!canManage || running) return;
    setRunning(true);
    try {
      const run = await runNoticeCollection({ sourceId, ensureSample, force: true });
      applyData({
        ...data,
        noticeCollectionRuns: [run, ...data.noticeCollectionRuns.filter((item) => item.id !== run.id)],
      });
      setSourceReload((value) => value + 1);
      setReloadTick((value) => value + 1);
      onNotice({
        type: run.status === "成功" ? "success" : "error",
        message: run.status === "成功"
          ? `采集完成：新增 ${run.createdCount}，更新 ${run.updatedCount}，商机 ${run.leadCount}`
          : (run.errorMessage || "采集失败"),
      });
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "采集失败" });
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>公告管理</h2>
            <p>维护竞价与政采公告，控制是否公开到官网；采集任务命中关键字后写入商机。</p>
          </div>
          <div className="panel-title-buttons">
            <div className="segmented">
              <button type="button" className={tab === "list" ? "active" : ""} onClick={() => setTab("list")}>
                <Bell size={14} />公告列表
              </button>
              <button type="button" className={tab === "collection" ? "active" : ""} onClick={() => setTab("collection")}>
                <RefreshCw size={14} />采集任务
              </button>
            </div>
            {tab === "list" && canManage && (
              <button type="button" className="primary" onClick={() => setShowCreate(true)}>新增公告</button>
            )}
            {tab === "collection" && canManage && (
              <button type="button" className="primary" disabled={running} onClick={() => void triggerCollection(undefined, true)}>
                {running ? "采集中..." : "运行示例采集"}
              </button>
            )}
          </div>
        </div>

        {tab === "list" && (
          <>
            <div className="platform-account-toolbar">
              <SearchField
                value={search}
                onChange={setSearch}
                placeholder="搜索标题、项目编号、单位、供应商"
                ariaLabel="搜索公告"
              />
            </div>
            <div className="segmented">
              {(["全部", "公开", "不公开"] as const).map((item) => (
                <button
                  key={item}
                  type="button"
                  className={publicFilter === item ? "active" : ""}
                  onClick={() => setPublicFilter(item)}
                >
                  {item === "全部" ? "全部公开状态" : item}
                </button>
              ))}
            </div>
            <div className="segmented">
              {NOTICE_KINDS.map((item) => (
                <button
                  key={item}
                  type="button"
                  className={noticeKind === item ? "active" : ""}
                  onClick={() => setNoticeKind(item)}
                >
                  {item === "全部" ? "全部类型" : item}
                </button>
              ))}
            </div>
            <div className="segmented">
              {BID_STATUSES.map((item) => (
                <button
                  key={item || "empty"}
                  type="button"
                  className={bidStatus === item ? "active" : ""}
                  onClick={() => setBidStatus(item)}
                >
                  {item === "全部" ? "全部状态" : item}
                </button>
              ))}
            </div>
            <div className="table">
              <div className="table-row notice-table head">
                <span>公告</span>
                <span>单位/供应商</span>
                <span>类型/状态</span>
                <span>金额</span>
                <span>公开</span>
                <span>操作</span>
              </div>
              {loading && <div className="table-empty">加载中...</div>}
              {!loading && items.map((item) => (
                <div className="table-row notice-table" key={item.id}>
                  <span className="notice-main-cell">
                    <CopyableLine text={item.title} label="公告标题">
                      <strong>{item.title}</strong>
                    </CopyableLine>
                    <CopyableLine text={item.projectNumber} label="项目编号" className="is-secondary">
                      <em>项目编号 {item.projectNumber || "—"}</em>
                    </CopyableLine>
                    {item.detailUrl ? (
                      <a className="copy-link" href={item.detailUrl} target="_blank" rel="noreferrer">查看详情</a>
                    ) : null}
                  </span>
                  <span className="notice-main-cell">
                    <CopyableLine text={item.department} label="采购单位">
                      <strong>{item.department || "—"}</strong>
                    </CopyableLine>
                    <em>{item.supplierName || item.publisher || "—"}</em>
                    {(item.contactName || item.contactPhone) ? (
                      <em>{[item.contactName, item.contactPhone].filter(Boolean).join(" ")}</em>
                    ) : null}
                  </span>
                  <span className="notice-main-cell">
                    <strong>{item.noticeKind}</strong>
                    <em>{item.bidStatus || "—"}</em>
                    <em>{item.category || "—"}</em>
                  </span>
                  <span>{money(item.amount)}</span>
                  <span>{item.isPublic ? "公开" : "不公开"}</span>
                  <span className="option-actions">
                    {canManage && (
                      <button type="button" className="copy-link" onClick={() => void togglePublic(item)}>
                        {item.isPublic ? "取消公开" : "公开到官网"}
                      </button>
                    )}
                  </span>
                </div>
              ))}
              {!loading && items.length === 0 && <div className="table-empty">暂无公告</div>}
            </div>
            <Pagination
              page={page}
              totalPages={totalPages}
              total={total}
              pageSize={PAGE_SIZE}
              onPageChange={setPage}
            />
          </>
        )}

        {tab === "collection" && (
          <>
            <div className="table">
              <div className="table-row notice-source-table head">
                <span>采集源</span>
                <span>类型</span>
                <span>关键字</span>
                <span>最近运行</span>
                <span>操作</span>
              </div>
              {sources.map((source) => (
                <div className="table-row notice-source-table" key={source.id}>
                  <span className="notice-main-cell">
                    <CopyableLine text={source.name} label="采集源名称">
                      <strong>{source.name}</strong>
                    </CopyableLine>
                    <em>{source.enabled ? "启用" : "停用"}</em>
                  </span>
                  <span>{source.kind}</span>
                  <span>{(source.keywords || []).join("、") || "—"}</span>
                  <span className="notice-main-cell">
                    <strong>{source.lastStatus || "—"}</strong>
                    <em>{source.lastRunAt || "尚未运行"}</em>
                  </span>
                  <span className="option-actions">
                    {canManage && (
                      <button type="button" className="copy-link" disabled={running} onClick={() => void triggerCollection(source.id)}>
                        立即采集
                      </button>
                    )}
                  </span>
                </div>
              ))}
              {sources.length === 0 && (
                <div className="table-empty">暂无采集源。可先点「运行示例采集」创建示例源并拉取演示公告。</div>
              )}
            </div>
            <div className="panel-title" style={{ marginTop: 20 }}>
              <div>
                <h2>最近采集记录</h2>
              </div>
            </div>
            <div className="table">
              <div className="table-row notice-run-table head">
                <span>来源</span>
                <span>状态</span>
                <span>新增/更新/商机</span>
                <span>时间</span>
              </div>
              {runs.map((run) => (
                <div className="table-row notice-run-table" key={run.id}>
                  <span>
                    <CopyableLine text={run.sourceName} label="采集来源">
                      {run.sourceName}
                    </CopyableLine>
                  </span>
                  <span>{run.status}{run.errorMessage ? `：${run.errorMessage}` : ""}</span>
                  <span>{run.createdCount}/{run.updatedCount}/{run.leadCount}</span>
                  <span>{run.startedAt}</span>
                </div>
              ))}
              {runs.length === 0 && <div className="table-empty">暂无采集记录</div>}
            </div>
          </>
        )}
      </div>

      {showCreate && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-label="新增公告">
            <div className="modal-head">
              <div>
                <h2>新增公告</h2>
                <p>手工录入公告，可勾选公开到官网。</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setShowCreate(false)} aria-label="关闭">
                <X size={18} />
              </button>
            </div>
            <div className="form-grid">
              <label><span>标题</span><input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label>
              <label><span>项目编号</span><input value={form.projectNumber} onChange={(event) => setForm({ ...form, projectNumber: event.target.value })} /></label>
              <label><span>采购单位</span><input value={form.department} onChange={(event) => setForm({ ...form, department: event.target.value })} /></label>
              <label><span>分类</span><input value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} /></label>
              <label>
                <span>类型</span>
                <select value={form.noticeKind} onChange={(event) => setForm({ ...form, noticeKind: event.target.value as NoticeKind })}>
                  {NOTICE_KINDS.filter((item) => item !== "全部").map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
              </label>
              <label>
                <span>状态</span>
                <select value={form.bidStatus} onChange={(event) => setForm({ ...form, bidStatus: event.target.value as NoticeBidStatus })}>
                  {BID_STATUSES.filter((item) => item !== "全部").map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
              </label>
              <label><span>金额</span><input value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
              <label><span>联系人</span><input value={form.contactName} onChange={(event) => setForm({ ...form, contactName: event.target.value })} /></label>
              <label><span>电话</span><input value={form.contactPhone} onChange={(event) => setForm({ ...form, contactPhone: event.target.value })} /></label>
              <label><span>详情链接</span><input value={form.detailUrl} onChange={(event) => setForm({ ...form, detailUrl: event.target.value })} /></label>
              <label className="checkbox-field">
                <input type="checkbox" checked={form.isPublic} onChange={(event) => setForm({ ...form, isPublic: event.target.checked })} />
                <span>公开到官网</span>
              </label>
            </div>
            <div className="modal-actions">
              <button type="button" className="ghost" onClick={() => setShowCreate(false)}>取消</button>
              <button type="button" className="primary" onClick={() => void saveNotice()}>保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
