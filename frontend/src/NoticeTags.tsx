import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import { backendApiUrl } from "./apiConfig";
import { AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";
import { fetchNoticeDetail, NoticeDetailModal, type NoticeDetail } from "./NoticeDetailModal";

type TagItem = {
  id: number;
  title: string;
  buyerName: string;
  orgType: string;
  nature: string;
  dealKind: string;
  province: string;
  city: string;
  district: string;
  regionName: string;
  dealAmount: string;
  publishTime: string;
  locked: boolean;
  source: string;
  productCount: number;
};

type ProductTag = {
  goodsId: number | null;
  category: string;
  productName: string;
  brand: string;
  locked: boolean;
};

type TagDetail = TagItem & { products: ProductTag[]; orgTypes: string[]; natures: string[]; dealKinds: string[] };

const FALLBACK_DEAL_KINDS = ["商品", "服务", "工程", "未识别"];

const FALLBACK_ORG_TYPES = [
  "幼儿园",
  "小学",
  "中学",
  "大专",
  "大学",
  "教育",
  "医疗卫生",
  "公安系统",
  "司法",
  "财税",
  "公共资源",
  "文化",
  "科研",
  "交通",
  "住建",
  "农业",
  "民政",
  "应急",
  "群团",
  "机关",
  "其他",
];
const FALLBACK_NATURES = ["政府", "事业单位", "国企", "央企", "其他"];

async function readJson<T>(response: Response): Promise<T> {
  const data = (await response.json()) as T & { detail?: string };
  if (response.status === 401) throw new AuthExpiredError();
  if (!response.ok && response.status !== 503) throw new Error(data.detail || "请求失败");
  return data;
}

export function NoticeTags({ onNotice, canManage }: { onNotice: (notice: { type: "success" | "error"; message: string }) => void; canManage: boolean }) {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [regionSearch, setRegionSearch] = useState("");
  const [regionQuery, setRegionQuery] = useState("");
  const [orgType, setOrgType] = useState("全部");
  const [nature, setNature] = useState("全部");
  const [dealKind, setDealKind] = useState("全部");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState<TagItem[]>([]);
  const [orgTypes, setOrgTypes] = useState<string[]>(FALLBACK_ORG_TYPES);
  const [natures, setNatures] = useState<string[]>(FALLBACK_NATURES);
  const [dealKinds, setDealKinds] = useState<string[]>(FALLBACK_DEAL_KINDS);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [detail, setDetail] = useState<TagDetail | null>(null);
  const [saving, setSaving] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [batchOrgType, setBatchOrgType] = useState("");
  const [batchNature, setBatchNature] = useState("");
  const [batchDealKind, setBatchDealKind] = useState("");
  const [batchSaving, setBatchSaving] = useState(false);
  const [identifyingId, setIdentifyingId] = useState<number | null>(null);
  const [noticeDetail, setNoticeDetail] = useState<NoticeDetail | null>(null);
  const [noticeDetailLoading, setNoticeDetailLoading] = useState(false);
  const pageSize = 20;
  const orgFilters = ["全部", ...orgTypes];
  const natureFilters = ["全部", ...natures];
  const dealKindFilters = ["全部", ...dealKinds];

  const pageIds = useMemo(() => items.map((item) => item.id), [items]);
  const allPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.includes(id));
  const somePageSelected = pageIds.some((id) => selectedIds.includes(id));

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    const timer = window.setTimeout(() => setRegionQuery(regionSearch.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [regionSearch]);

  useEffect(() => {
    setPage(1);
    setSelectedIds([]);
  }, [query, regionQuery, orgType, nature, dealKind]);

  useEffect(() => {
    setSelectedIds([]);
  }, [page]);

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (query) params.set("search", query);
    if (regionQuery) params.set("province", regionQuery);
    if (orgType !== "全部") params.set("org_type", orgType);
    if (nature !== "全部") params.set("nature", nature);
    if (dealKind !== "全部") params.set("deal_kind", dealKind);
    let cancelled = false;
    setLoading(true);
    fetch(backendApiUrl(`/api/notices/tags/?${params.toString()}`), { credentials: "include" })
      .then((response) =>
        readJson<{
          items: TagItem[];
          total: number;
          detail?: string;
          orgTypes?: string[];
          natures?: string[];
          dealKinds?: string[];
        }>(response),
      )
      .then((data) => {
        if (cancelled) return;
        setItems(data.items || []);
        setTotal(data.total || 0);
        if (data.orgTypes?.length) setOrgTypes(data.orgTypes);
        if (data.natures?.length) setNatures(data.natures);
        if (data.dealKinds?.length) setDealKinds(data.dealKinds);
        if (data.detail) onNotice({ type: "error", message: data.detail });
      })
      .catch((error: Error) => {
        if (!cancelled) onNotice({ type: "error", message: error.message || "加载标签失败" });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page, query, regionQuery, orgType, nature, dealKind, onNotice, refreshKey]);

  function toggleSelect(id: number) {
    setSelectedIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  function toggleSelectAllPage() {
    if (allPageSelected) {
      setSelectedIds((current) => current.filter((id) => !pageIds.includes(id)));
      return;
    }
    setSelectedIds((current) => Array.from(new Set([...current, ...pageIds])));
  }

  async function runTagging() {
    setRunning(true);
    try {
      const response = await fetch(backendApiUrl("/api/notices/tags/"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ limit: 200 }),
      });
      const data = await readJson<{ tagged: number; skipped: number }>(response);
      onNotice({ type: "success", message: `已识别 ${data.tagged} 条，跳过 ${data.skipped} 条。` });
      setRefreshKey((value) => value + 1);
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "识别失败" });
    } finally {
      setRunning(false);
    }
  }

  async function applyBatch() {
    if (!canManage || selectedIds.length === 0) return;
    if (!batchOrgType && !batchNature && !batchDealKind) {
      onNotice({ type: "error", message: "请至少选择要批量设置的类型、性质或成交。" });
      return;
    }
    setBatchSaving(true);
    try {
      const body: Record<string, unknown> = { ids: selectedIds };
      if (batchOrgType) body.orgType = batchOrgType;
      if (batchNature) body.nature = batchNature;
      if (batchDealKind) body.dealKind = batchDealKind;
      const response = await fetch(backendApiUrl("/api/notices/tags/batch/"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await readJson<{ updated: number; skipped: number }>(response);
      onNotice({
        type: "success",
        message: `已批量修正 ${data.updated} 条${data.skipped ? `，跳过 ${data.skipped} 条` : ""}，并已锁定。`,
      });
      setSelectedIds([]);
      setBatchOrgType("");
      setBatchNature("");
      setBatchDealKind("");
      setRefreshKey((value) => value + 1);
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "批量修正失败" });
    } finally {
      setBatchSaving(false);
    }
  }

  async function identifyOne(item: TagItem) {
    if (!canManage || identifyingId != null) return;
    let force = false;
    if (item.locked) {
      const ok = window.confirm("该标签已锁定。强制重新识别会覆盖并解除锁定，是否继续？");
      if (!ok) return;
      force = true;
    }
    setIdentifyingId(item.id);
    try {
      const postIdentify = (useForce: boolean) =>
        fetch(backendApiUrl(`/api/notices/tags/${item.id}/identify/`), {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ force: useForce }),
        });
      let response = await postIdentify(force);
      if (response.status === 409) {
        const data = (await response.json()) as { detail?: string; locked?: boolean };
        if (!data.locked) throw new Error(data.detail || "识别失败");
        const ok = window.confirm(data.detail || "标签已锁定，是否强制重新识别？");
        if (!ok) return;
        response = await postIdentify(true);
      }
      const saved = await readJson<TagItem>(response);
      setItems((rows) => rows.map((row) => (row.id === saved.id ? { ...row, ...saved } : row)));
      if (detail?.id === saved.id) {
        setDetail((current) => (current ? { ...current, ...saved } : current));
      }
      onNotice({ type: "success", message: `已重新识别：${saved.buyerName || saved.title || saved.id}` });
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "识别失败" });
    } finally {
      setIdentifyingId(null);
    }
  }

  async function openDetail(id: number) {
    try {
      const response = await fetch(backendApiUrl(`/api/notices/tags/${id}/`), { credentials: "include" });
      setDetail(await readJson<TagDetail>(response));
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "加载标签详情失败" });
    }
  }

  async function openNoticeDetail(id: number) {
    setNoticeDetailLoading(true);
    try {
      setNoticeDetail(await fetchNoticeDetail(id));
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "加载公告详情失败" });
    } finally {
      setNoticeDetailLoading(false);
    }
  }

  async function saveDetail() {
    if (!detail) return;
    setSaving(true);
    try {
      const response = await fetch(backendApiUrl(`/api/notices/tags/${detail.id}/`), {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          orgType: detail.orgType,
          nature: detail.nature,
          dealKind: detail.dealKind,
          province: detail.province,
          city: detail.city,
          district: detail.district,
          products: detail.products,
        }),
      });
      const saved = await readJson<TagDetail>(response);
      setDetail(saved);
      setItems((rows) => rows.map((row) => (row.id === saved.id ? { ...row, ...saved } : row)));
      onNotice({ type: "success", message: "标签已保存，并锁定为后续识别词典。" });
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败" });
    } finally {
      setSaving(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="stack">
      <div className="panel">
        <div className="page-toolbar">
          <div className="page-toolbar-actions">
            <SearchField value={search} onChange={setSearch} placeholder="搜索采购人或公告标题" />
            <SearchField value={regionSearch} onChange={setRegionSearch} placeholder="区域，如山东省 / 济南市" />
          </div>
          <div className="page-toolbar-actions">
            {canManage && (
              <button className="primary" type="button" disabled={running} onClick={() => void runTagging()}>
                {running ? "识别中…" : "识别一批"}
              </button>
            )}
          </div>
        </div>
        <div className="segmented" role="tablist" aria-label="采购人类型">
          {orgFilters.map((item) => (
            <button key={item} type="button" className={orgType === item ? "active" : ""} onClick={() => setOrgType(item)}>
              {item}
            </button>
          ))}
        </div>
        <div className="segmented" role="tablist" aria-label="采购人性质">
          {natureFilters.map((item) => (
            <button key={item} type="button" className={nature === item ? "active" : ""} onClick={() => setNature(item)}>
              {item}
            </button>
          ))}
        </div>
        <div className="segmented" role="tablist" aria-label="成交类型">
          {dealKindFilters.map((item) => (
            <button key={item} type="button" className={dealKind === item ? "active" : ""} onClick={() => setDealKind(item)}>
              {item}
            </button>
          ))}
        </div>
        {canManage && selectedIds.length > 0 && (
          <div className="notice-tag-batch-bar">
            <span>已选 {selectedIds.length} 条</span>
            <label>
              类型
              <select value={batchOrgType} onChange={(event) => setBatchOrgType(event.target.value)} aria-label="批量设置类型">
                <option value="">不改</option>
                {orgTypes.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label>
              性质
              <select value={batchNature} onChange={(event) => setBatchNature(event.target.value)} aria-label="批量设置性质">
                <option value="">不改</option>
                {natures.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label>
              成交
              <select value={batchDealKind} onChange={(event) => setBatchDealKind(event.target.value)} aria-label="批量设置成交类型">
                <option value="">不改</option>
                {dealKinds.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <button className="primary" type="button" disabled={batchSaving} onClick={() => void applyBatch()}>
              {batchSaving ? "应用中…" : "批量应用并锁定"}
            </button>
            <button className="ghost" type="button" disabled={batchSaving} onClick={() => setSelectedIds([])}>
              取消选择
            </button>
          </div>
        )}
        <div className="table">
          <div className="table-row notice-tag-table head">
            <span className="notice-tag-check">
              {canManage ? (
                <input
                  type="checkbox"
                  checked={allPageSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = somePageSelected && !allPageSelected;
                  }}
                  onChange={toggleSelectAllPage}
                  aria-label="全选本页"
                />
              ) : null}
            </span>
            <span>采购人</span>
            <span>类型</span>
            <span>性质</span>
            <span>成交</span>
            <span>区域</span>
            <span>商品</span>
            <span>状态</span>
            <span>操作</span>
          </div>
          {items.map((item) => (
            <div className="table-row notice-tag-table" key={item.id}>
              <span className="notice-tag-check">
                {canManage ? (
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(item.id)}
                    onChange={() => toggleSelect(item.id)}
                    aria-label={`选择 ${item.buyerName || item.title || item.id}`}
                  />
                ) : null}
              </span>
              <div className="notice-tag-main">
                <CopyableLine text={item.buyerName} label="采购人">
                  <strong>{item.buyerName || "未识别采购人"}</strong>
                </CopyableLine>
                {item.title ? (
                  <CopyableLine
                    text={item.title}
                    label="公告标题"
                    className="is-secondary"
                    onOpen={() => void openNoticeDetail(item.id)}
                  >
                    <em>{item.title}</em>
                  </CopyableLine>
                ) : (
                  <em>无标题</em>
                )}
              </div>
              <span>{item.orgType || "—"}</span>
              <span>{item.nature || "—"}</span>
              <span>{item.dealKind || "未识别"}</span>
              <span>{[item.province, item.city, item.district].filter(Boolean).join(" ") || item.regionName || "—"}</span>
              <span>{item.productCount}</span>
              <span>{item.locked ? "已锁定" : "规则"}</span>
              <div className="option-actions">
                {canManage && (
                  <button
                    className="copy-link"
                    type="button"
                    disabled={identifyingId != null}
                    onClick={() => void identifyOne(item)}
                  >
                    {identifyingId === item.id ? "识别中…" : "识别"}
                  </button>
                )}
                <button className="copy-link" type="button" onClick={() => void openDetail(item.id)}>
                  {canManage ? "修正" : "查看"}
                </button>
              </div>
            </div>
          ))}
          {!loading && items.length === 0 && <div className="table-empty">暂无标签。有结果公告后，可先执行一次识别。</div>}
        </div>
        <Pagination page={page} totalPages={totalPages} total={total} pageSize={pageSize} onPageChange={setPage} />
      </div>
      {noticeDetail && (
        <NoticeDetailModal
          detail={noticeDetail}
          loading={noticeDetailLoading}
          onClose={() => setNoticeDetail(null)}
          onSelectRelated={(id) => void openNoticeDetail(id)}
        />
      )}
      {detail && (
        <div className="modal-backdrop" role="presentation" onClick={() => setDetail(null)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="修正标签" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <div>
                <h2>{detail.buyerName || "修正标签"}</h2>
                <p>
                  {detail.title ? (
                    <button
                      type="button"
                      className="copy-link"
                      onClick={() => void openNoticeDetail(detail.id)}
                      disabled={noticeDetailLoading}
                    >
                      {detail.title}
                    </button>
                  ) : (
                    "无标题"
                  )}
                </p>
              </div>
              <button className="icon-button" type="button" onClick={() => setDetail(null)} aria-label="关闭">
                <X size={18} />
              </button>
            </div>
            <div className="form-grid">
              <label>
                类型
                <select value={detail.orgType} disabled={!canManage} onChange={(event) => setDetail({ ...detail, orgType: event.target.value })}>
                  {(detail.orgTypes || orgTypes).map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label>
                性质
                <select value={detail.nature} disabled={!canManage} onChange={(event) => setDetail({ ...detail, nature: event.target.value })}>
                  {(detail.natures || natures).map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label>
                成交类型
                <select
                  value={detail.dealKind || "未识别"}
                  disabled={!canManage}
                  onChange={(event) => setDetail({ ...detail, dealKind: event.target.value })}
                >
                  {(detail.dealKinds || dealKinds).map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label>
                省
                <input value={detail.province} disabled={!canManage} onChange={(event) => setDetail({ ...detail, province: event.target.value })} />
              </label>
              <label>
                市
                <input value={detail.city} disabled={!canManage} onChange={(event) => setDetail({ ...detail, city: event.target.value })} />
              </label>
              <label>
                区县
                <input value={detail.district} disabled={!canManage} onChange={(event) => setDetail({ ...detail, district: event.target.value })} />
              </label>
            </div>
            <div className="table">
              <div className="table-row notice-tag-product-table head">
                <span>商品</span>
                <span>类别</span>
                <span>品牌</span>
              </div>
              {detail.products.map((product, index) => (
                <div className="table-row notice-tag-product-table" key={`${product.goodsId}-${index}`}>
                  <span>{product.productName || "—"}</span>
                  <input
                    value={product.category}
                    disabled={!canManage}
                    onChange={(event) => {
                      const products = detail.products.slice();
                      products[index] = { ...product, category: event.target.value };
                      setDetail({ ...detail, products });
                    }}
                  />
                  <input
                    value={product.brand}
                    disabled={!canManage}
                    onChange={(event) => {
                      const products = detail.products.slice();
                      products[index] = { ...product, brand: event.target.value };
                      setDetail({ ...detail, products });
                    }}
                  />
                </div>
              ))}
              {detail.products.length === 0 && <div className="table-empty">这条公告还没有商品行</div>}
            </div>
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setDetail(null)}>
                关闭
              </button>
              {canManage && (
                <button className="primary" type="button" disabled={saving} onClick={() => void saveDetail()}>
                  {saving ? "保存中…" : "保存并锁定"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
