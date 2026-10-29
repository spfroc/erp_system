import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { backendApiUrl } from "./apiConfig";
import { AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";

type ScriptArg = { key: string; label: string; type: string; default?: unknown; optional?: boolean };
type ScriptItem = { key: string; label: string; kind: string; queue: string; argSchema: ScriptArg[] };
type JobItem = {
  id: number;
  scriptKey: string;
  scriptLabel: string;
  kind: string;
  name: string;
  enabled: boolean;
  scheduleType: string;
  intervalSeconds: number | null;
  cronExpr: string;
  args: Record<string, unknown>;
  lastRunAt: string;
  nextRunAt: string;
};
type RunItem = {
  id: number;
  jobId: number;
  jobName: string;
  scriptKey: string;
  trigger: string;
  status: string;
  startedAt: string;
  finishedAt: string;
  stdout: string;
  stderr: string;
  createdAt: string;
};

type NoticeFn = (notice: { type: "success" | "error"; message: string }) => void;

async function readJson<T>(response: Response): Promise<T> {
  const data = (await response.json()) as T & { detail?: string };
  if (response.status === 401) throw new AuthExpiredError();
  if (!response.ok) throw new Error(data.detail || "请求失败");
  return data;
}

function scheduleLabel(job: JobItem) {
  if (job.scheduleType === "interval") return `每 ${job.intervalSeconds || "?"} 秒`;
  if (job.scheduleType === "cron") return job.cronExpr || "cron";
  return "手动";
}

/** 运维任务时间统一按东八区展示（后端存 UTC aware）。 */
function formatRunTime(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value.replace("T", " ").slice(0, 19);
  }
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")}:${get("second")}`;
}

export function DevOps({ onNotice, canManage }: { onNotice: NoticeFn; canManage: boolean }) {
  const [tab, setTab] = useState<"jobs" | "runs">("jobs");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [scripts, setScripts] = useState<ScriptItem[]>([]);
  const [editing, setEditing] = useState<Partial<JobItem> & { args?: Record<string, unknown> } | null>(null);
  const [runDetail, setRunDetail] = useState<RunItem | null>(null);
  const [saving, setSaving] = useState(false);
  const pageSize = 20;

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [query, tab]);

  useEffect(() => {
    fetch(backendApiUrl("/api/dev-ops/scripts/"), { credentials: "include" })
      .then((response) => readJson<{ items: ScriptItem[] }>(response))
      .then((data) => setScripts(data.items || []))
      .catch((error: Error) => onNotice({ type: "error", message: error.message || "加载脚本目录失败" }));
  }, [onNotice]);

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (query) params.set("search", query);
    const path = tab === "jobs" ? `/api/dev-ops/jobs/?${params}` : `/api/dev-ops/runs/?${params}`;
    let cancelled = false;
    fetch(backendApiUrl(path), { credentials: "include" })
      .then((response) => readJson<{ items: JobItem[] | RunItem[]; total: number }>(response))
      .then((data) => {
        if (cancelled) return;
        setTotal(data.total || 0);
        if (tab === "jobs") setJobs((data.items as JobItem[]) || []);
        else setRuns((data.items as RunItem[]) || []);
      })
      .catch((error: Error) => {
        if (!cancelled) onNotice({ type: "error", message: error.message || "加载失败" });
      });
    return () => {
      cancelled = true;
    };
  }, [page, query, tab, onNotice]);

  function openCreate() {
    const first = scripts[0];
    setEditing({
      id: 0,
      scriptKey: first?.key || "",
      name: first?.label || "",
      enabled: false,
      scheduleType: "manual",
      intervalSeconds: 3600,
      cronExpr: "0 3 * * *",
      args: Object.fromEntries((first?.argSchema || []).map((item) => [item.key, item.default ?? ""])),
    });
  }

  function openEdit(job: JobItem) {
    setEditing({ ...job, args: { ...(job.args || {}) } });
  }

  async function saveJob() {
    if (!editing) return;
    setSaving(true);
    try {
      const payload = {
        scriptKey: editing.scriptKey,
        name: editing.name,
        enabled: Boolean(editing.enabled),
        scheduleType: editing.scheduleType || "manual",
        intervalSeconds: editing.intervalSeconds,
        cronExpr: editing.cronExpr || "",
        args: editing.args || {},
      };
      const isNew = !editing.id;
      const response = await fetch(backendApiUrl(isNew ? "/api/dev-ops/jobs/" : `/api/dev-ops/jobs/${editing.id}/`), {
        method: isNew ? "POST" : "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const saved = await readJson<JobItem>(response);
      setEditing(null);
      onNotice({ type: "success", message: isNew ? "任务已创建" : "任务已保存" });
      setJobs((rows) => {
        if (isNew) return [saved, ...rows];
        return rows.map((row) => (row.id === saved.id ? saved : row));
      });
      if (isNew) setTab("jobs");
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败" });
    } finally {
      setSaving(false);
    }
  }

  async function toggleEnabled(job: JobItem) {
    if (!canManage) return;
    try {
      const response = await fetch(backendApiUrl(`/api/dev-ops/jobs/${job.id}/`), {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !job.enabled }),
      });
      const saved = await readJson<JobItem>(response);
      setJobs((rows) => rows.map((row) => (row.id === saved.id ? saved : row)));
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "更新失败" });
    }
  }

  async function runNow(job: JobItem) {
    if (!canManage) return;
    try {
      const response = await fetch(backendApiUrl(`/api/dev-ops/jobs/${job.id}/run/`), {
        method: "POST",
        credentials: "include",
      });
      await readJson<RunItem>(response);
      onNotice({ type: "success", message: "已入队执行" });
      setTab("runs");
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "执行失败" });
    }
  }

  async function removeJob(job: JobItem) {
    if (!canManage) return;
    if (!window.confirm(`确定删除任务「${job.name}」？`)) return;
    try {
      const response = await fetch(backendApiUrl(`/api/dev-ops/jobs/${job.id}/`), {
        method: "DELETE",
        credentials: "include",
      });
      await readJson<{ ok: boolean }>(response);
      setJobs((rows) => rows.filter((row) => row.id !== job.id));
      onNotice({ type: "success", message: "已删除" });
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "删除失败" });
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const selectedScript = scripts.find((item) => item.key === editing?.scriptKey);

  return (
    <div className="stack">
      <div className="panel">
        <div className="page-toolbar">
          <div className="segmented" role="tablist" aria-label="定时任务子页">
            <button type="button" className={tab === "jobs" ? "active" : ""} onClick={() => setTab("jobs")}>
              任务
            </button>
            <button type="button" className={tab === "runs" ? "active" : ""} onClick={() => setTab("runs")}>
              运行记录
            </button>
          </div>
          <div className="page-toolbar-actions">
            <SearchField value={search} onChange={setSearch} placeholder={tab === "jobs" ? "搜索任务名或脚本" : "搜索运行记录"} />
            {canManage && tab === "jobs" && (
              <button className="primary" type="button" onClick={openCreate}>
                新建任务
              </button>
            )}
          </div>
        </div>
        {tab === "jobs" ? (
          <div className="table">
            <div className="table-row dev-ops-job-table head">
              <span>任务</span>
              <span>调度</span>
              <span>启用</span>
              <span>上次/下次</span>
              <span>操作</span>
            </div>
            {jobs.map((job) => (
              <div className="table-row dev-ops-job-table" key={job.id}>
                <div className="notice-tag-main">
                  <CopyableLine text={job.name} label="任务名">
                    <strong>{job.name}</strong>
                  </CopyableLine>
                  <em>
                    {job.scriptLabel} · {job.kind}
                  </em>
                </div>
                <span>{scheduleLabel(job)}</span>
                <span>{job.enabled ? "是" : "否"}</span>
                <span>
                  <em>{formatRunTime(job.lastRunAt)}</em>
                  <em>{formatRunTime(job.nextRunAt)}</em>
                </span>
                <div className="option-actions">
                  {canManage && (
                    <>
                      <button className="copy-link" type="button" onClick={() => void runNow(job)}>
                        立即执行
                      </button>
                      <button className="copy-link" type="button" onClick={() => void toggleEnabled(job)}>
                        {job.enabled ? "停用" : "启用"}
                      </button>
                      <button className="copy-link" type="button" onClick={() => openEdit(job)}>
                        编辑
                      </button>
                      <button className="copy-link danger-action" type="button" onClick={() => void removeJob(job)}>
                        删除
                      </button>
                    </>
                  )}
                  {!canManage && (
                    <button className="copy-link" type="button" onClick={() => openEdit(job)}>
                      查看
                    </button>
                  )}
                </div>
              </div>
            ))}
            {jobs.length === 0 && <div className="table-empty">暂无任务。开发人员可新建白名单脚本任务。</div>}
          </div>
        ) : (
          <div className="table">
            <div className="table-row dev-ops-run-table head">
              <span>任务</span>
              <span>触发</span>
              <span>状态</span>
              <span>开始时间</span>
              <span>结束时间</span>
              <span>操作</span>
            </div>
            {runs.map((run) => (
              <div className="table-row dev-ops-run-table" key={run.id}>
                <div className="notice-tag-main">
                  <CopyableLine text={run.jobName} label="任务名">
                    <strong>{run.jobName || run.scriptKey}</strong>
                  </CopyableLine>
                  <em>{run.scriptKey}</em>
                </div>
                <span>{run.trigger === "schedule" ? "定时" : "手动"}</span>
                <span>{run.status}</span>
                <span>{formatRunTime(run.startedAt || run.createdAt)}</span>
                <span>{formatRunTime(run.finishedAt)}</span>
                <div className="option-actions">
                  <button className="copy-link" type="button" onClick={() => setRunDetail(run)}>
                    输出
                  </button>
                </div>
              </div>
            ))}
            {runs.length === 0 && (
              <div className="table-empty">
                暂无运行记录。请先在「任务」里点「立即执行」，或将任务设为启用并由定时调度触发；常驻采集容器不会写入本列表。
              </div>
            )}
          </div>
        )}
        <Pagination page={page} totalPages={totalPages} total={total} pageSize={pageSize} onPageChange={setPage} />
      </div>

      {editing && (
        <div className="modal-backdrop" role="presentation" onClick={() => setEditing(null)}>
          <div className="modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <div>
                <h2>{editing.id ? "编辑任务" : "新建任务"}</h2>
                <p>只能选择白名单脚本。</p>
              </div>
              <button className="icon-button" type="button" onClick={() => setEditing(null)} aria-label="关闭">
                <X size={18} />
              </button>
            </div>
            <div className="form-grid">
              <label>
                脚本
                <select
                  value={editing.scriptKey || ""}
                  disabled={!canManage || Boolean(editing.id)}
                  onChange={(event) => {
                    const script = scripts.find((item) => item.key === event.target.value);
                    setEditing({
                      ...editing,
                      scriptKey: event.target.value,
                      name: editing.name || script?.label || "",
                      args: Object.fromEntries((script?.argSchema || []).map((item) => [item.key, item.default ?? ""])),
                    });
                  }}
                >
                  {scripts.map((item) => (
                    <option key={item.key} value={item.key}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                名称
                <input
                  value={editing.name || ""}
                  disabled={!canManage}
                  onChange={(event) => setEditing({ ...editing, name: event.target.value })}
                />
              </label>
              <label>
                调度
                <select
                  value={editing.scheduleType || "manual"}
                  disabled={!canManage}
                  onChange={(event) => setEditing({ ...editing, scheduleType: event.target.value })}
                >
                  <option value="manual">仅手动</option>
                  <option value="interval">固定间隔</option>
                  <option value="cron">cron</option>
                </select>
              </label>
              {editing.scheduleType === "interval" && (
                <label>
                  间隔秒数
                  <input
                    type="number"
                    min={60}
                    value={editing.intervalSeconds ?? 3600}
                    disabled={!canManage}
                    onChange={(event) => setEditing({ ...editing, intervalSeconds: Number(event.target.value) })}
                  />
                </label>
              )}
              {editing.scheduleType === "cron" && (
                <label>
                  cron（分 时 日 月 周）
                  <input
                    value={editing.cronExpr || ""}
                    disabled={!canManage}
                    onChange={(event) => setEditing({ ...editing, cronExpr: event.target.value })}
                  />
                </label>
              )}
              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={Boolean(editing.enabled)}
                  disabled={!canManage}
                  onChange={(event) => setEditing({ ...editing, enabled: event.target.checked })}
                />
                启用调度
              </label>
              {(selectedScript?.argSchema || []).map((field) => (
                <label key={field.key}>
                  {field.label}
                  {field.type === "bool" ? (
                    <input
                      type="checkbox"
                      checked={Boolean(editing.args?.[field.key])}
                      disabled={!canManage}
                      onChange={(event) =>
                        setEditing({ ...editing, args: { ...(editing.args || {}), [field.key]: event.target.checked } })
                      }
                    />
                  ) : (
                    <input
                      value={String(editing.args?.[field.key] ?? "")}
                      disabled={!canManage}
                      onChange={(event) =>
                        setEditing({
                          ...editing,
                          args: {
                            ...(editing.args || {}),
                            [field.key]: field.type === "int" ? Number(event.target.value || 0) : event.target.value,
                          },
                        })
                      }
                    />
                  )}
                </label>
              ))}
            </div>
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setEditing(null)}>
                关闭
              </button>
              {canManage && (
                <button className="primary" type="button" disabled={saving} onClick={() => void saveJob()}>
                  {saving ? "保存中…" : "保存"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {runDetail && (
        <div className="modal-backdrop" role="presentation" onClick={() => setRunDetail(null)}>
          <div className="modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <div>
                <h2>运行输出 #{runDetail.id}</h2>
                <p>
                  {runDetail.status} · {runDetail.trigger === "schedule" ? "定时" : "手动"} · 开始{" "}
                  {formatRunTime(runDetail.startedAt || runDetail.createdAt)} · 结束 {formatRunTime(runDetail.finishedAt)}
                </p>
              </div>
              <button className="icon-button" type="button" onClick={() => setRunDetail(null)} aria-label="关闭">
                <X size={18} />
              </button>
            </div>
            <pre className="dev-ops-output">{runDetail.stdout || "(无标准输出)"}</pre>
            {runDetail.stderr ? <pre className="dev-ops-output is-error">{runDetail.stderr}</pre> : null}
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setRunDetail(null)}>
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
