import type { AssistantBlock } from "./assistantTypes";
import { AssistantStatsChart, type AssistantChartSpec } from "./AssistantStatsChart";

function asItems(data?: Record<string, unknown>): Array<Record<string, unknown>> {
  const items = data?.items;
  return Array.isArray(items) ? (items as Array<Record<string, unknown>>) : [];
}

function noticeIdOf(item: Record<string, unknown>): number | null {
  const value = item.id ?? item.notice_id ?? item.noticeRawId;
  const num = Number(value);
  return Number.isFinite(num) && num > 0 ? num : null;
}

export function AssistantResultRenderer({
  blocks,
  onNavigate,
  onFollowUp,
  onOpenNotice,
  onConfirmAction,
  confirming,
}: {
  blocks: AssistantBlock[];
  onNavigate?: (viewId: string) => void;
  onFollowUp?: (text: string) => void;
  onOpenNotice?: (noticeId: number) => void;
  onConfirmAction?: (executionId: number, token: string) => void;
  confirming?: boolean;
}) {
  if (!blocks?.length) return null;

  return (
    <div className="assistant-blocks">
      {blocks.map((block, index) => {
        const key = `${block.type}-${index}`;
        if (block.type === "clarification") {
          // 气泡正文已展示 clarification 文案，避免重复
          return null;
        }

        if (block.type === "text" || block.type === "error") {
          return (
            <div key={key} className={`assistant-block assistant-block-${block.type}`}>
              <p>{String(block.data?.text || block.data?.message || "")}</p>
            </div>
          );
        }

        if (block.type === "notice_list") {
          const items = asItems(block.data);
          return (
            <div key={key} className="assistant-block">
              <div className="table">
                <div className="table-row assistant-result-table head">
                  <span>标题</span>
                  <span>区域</span>
                  <span>发布时间</span>
                  <span>操作</span>
                </div>
                {items.map((item) => {
                  const id = noticeIdOf(item);
                  return (
                    <div className="table-row assistant-result-table" key={String(item.id)}>
                      <strong>{String(item.title || item.noticeTitle || "-")}</strong>
                      <span>{String(item.region || item.regionName || "-")}</span>
                      <span>{String(item.publish_time || item.publishTime || "-")}</span>
                      <span className="option-actions">
                        {id ? (
                          <button
                            type="button"
                            className="copy-link"
                            onClick={() => (onOpenNotice ? onOpenNotice(id) : onFollowUp?.(`打开公告 ${id}`))}
                          >
                            打开
                          </button>
                        ) : null}
                      </span>
                    </div>
                  );
                })}
                {items.length === 0 && <div className="table-empty">暂无公告</div>}
              </div>
              <em>
                共 {String(block.data?.total ?? items.length)} 条
                {block.data?.page ? ` · 第 ${String(block.data.page)} 页` : ""}
              </em>
            </div>
          );
        }

        if (block.type === "notice_detail") {
          const item = (block.data?.item || {}) as Record<string, unknown>;
          const id = noticeIdOf(item) ?? (Number(block.data?.notice_id || 0) || null);
          const goods = Array.isArray(item.goods) ? (item.goods as Array<Record<string, unknown>>) : [];
          return (
            <div key={key} className="assistant-block assistant-block-notice-detail">
              <p>
                <strong>{String(item.title || item.noticeTitle || `公告 #${id || ""}`)}</strong>
              </p>
              <div className="assistant-detail-grid">
                <span>采购单位</span>
                <strong>{String(item.buyerName || item.buyer_name || "-")}</strong>
                <span>区域</span>
                <strong>{String(item.regionName || item.region || "-")}</strong>
                <span>类型</span>
                <strong>{String(item.noticeKind || item.notice_kind || "-")}</strong>
                <span>发布时间</span>
                <strong>{String(item.publishTime || item.publish_time || "-")}</strong>
                <span>预算/成交</span>
                <strong>
                  {String(item.budgetAmount ?? item.budget_amount ?? "-")} /{" "}
                  {String(item.dealAmount ?? item.deal_amount ?? "-")}
                </strong>
                <span>商品明细</span>
                <strong>{goods.length ? `${goods.length} 行` : "无"}</strong>
              </div>
              {id ? (
                <div className="option-actions">
                  <button type="button" className="primary" onClick={() => onOpenNotice?.(id)}>
                    查看完整详情
                  </button>
                </div>
              ) : null}
            </div>
          );
        }

        if (block.type === "goods_table" || block.type === "erp_record_list") {
          const items = asItems(block.data);
          return (
            <div key={key} className="assistant-block">
              <div className="table">
                <div className="table-row assistant-result-table head">
                  <span>名称</span>
                  <span>摘要</span>
                  <span>操作</span>
                </div>
                {items.map((item, i) => {
                  const name =
                    item.title ||
                    item.name ||
                    item.product_name ||
                    item.productName ||
                    item.order_no ||
                    item.project_no ||
                    item.id ||
                    "-";
                  const summaryParts = [
                    item.summary,
                    item.customer_name,
                    item.invoice_status ? `开票:${item.invoice_status}` : "",
                    item.service_end_date ? `到期:${item.service_end_date}` : "",
                    item.onboarding_expire_date ? `入驻到期:${item.onboarding_expire_date}` : "",
                    item.buyer_name,
                    item.summary ? "" : item.status,
                    item.brand,
                    item.region,
                    item.amount,
                    item.trigger ? `触发:${item.trigger}` : "",
                    item.script_key ? `脚本:${item.script_key}` : "",
                  ].filter(Boolean);
                  const summary = summaryParts.join(" · ");
                  const noticeId = noticeIdOf({
                    id: item.notice_id || item.noticeRawId,
                  });
                  return (
                    <div className="table-row assistant-result-table" key={String(item.id || i)}>
                      <strong>{String(name)}</strong>
                      <span>{String(summary || "-")}</span>
                      <span className="option-actions">
                        {noticeId ? (
                          <button
                            type="button"
                            className="copy-link"
                            onClick={() =>
                              onOpenNotice ? onOpenNotice(noticeId) : onFollowUp?.(`打开公告 ${noticeId}`)
                            }
                          >
                            来源公告
                          </button>
                        ) : null}
                        {!noticeId && String(block.data?.collection || "") === "devopsRuns" && onNavigate ? (
                          <button type="button" className="copy-link" onClick={() => onNavigate("devOps")}>
                            打开定时任务
                          </button>
                        ) : null}
                      </span>
                    </div>
                  );
                })}
                {items.length === 0 && <div className="table-empty">暂无数据</div>}
              </div>
              <em>共 {String(block.data?.total ?? items.length)} 条</em>
            </div>
          );
        }

        if (block.type === "buyer_profile") {
          const profile = (block.data?.profile || {}) as Record<string, unknown>;
          const history = asItems({ items: block.data?.recent_notices });
          return (
            <div key={key} className="assistant-block">
              <p>
                <strong>{String(profile.name || "采购人")}</strong>
                {profile.region ? ` · ${String(profile.region)}` : ""}
              </p>
              <em>关联公告 {String(block.data?.total ?? history.length)} 条</em>
              <div className="table">
                {history.slice(0, 8).map((item) => {
                  const id = noticeIdOf(item);
                  return (
                    <div className="table-row assistant-result-table" key={String(item.id)}>
                      <strong>{String(item.title || "-")}</strong>
                      <span>{String(item.publish_time || item.publishTime || "-")}</span>
                      <span />
                      <span className="option-actions">
                        {id ? (
                          <button
                            type="button"
                            className="copy-link"
                            onClick={() =>
                              onOpenNotice ? onOpenNotice(id) : onFollowUp?.(`打开公告 ${id}`)
                            }
                          >
                            打开
                          </button>
                        ) : null}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        }

        if (block.type === "navigation") {
          const items = asItems(block.data);
          return (
            <div key={key} className="assistant-block">
              <div className="stack">
                {items.map((item) => (
                  <button
                    key={String(item.id)}
                    type="button"
                    className="ghost"
                    onClick={() => onNavigate?.(String(item.id))}
                  >
                    打开「{String(item.label || item.id)}」
                  </button>
                ))}
              </div>
            </div>
          );
        }

        if (block.type === "tool_preview") {
          const executionId = Number(block.data?.execution_id || 0);
          const token = String(block.data?.confirmation_token || "");
          const toolName = String(block.data?.tool_name || "");
          const params = (block.data?.params || {}) as Record<string, unknown>;
          const invoiceNo = String(params.invoice_no || params.invoice_id || "");
          return (
            <div key={key} className="assistant-block assistant-block-preview">
              <p>
                待确认操作：<strong>{String(block.data?.description || toolName || "")}</strong>
              </p>
              {toolName === "erp.invoice.delete" ? (
                <div className="assistant-detail-grid">
                  <span>发票号</span>
                  <strong>{invoiceNo || "-"}</strong>
                  <span>操作</span>
                  <strong>软删除（不可恢复至列表）</strong>
                </div>
              ) : (
                <pre className="assistant-json">{JSON.stringify(params, null, 2)}</pre>
              )}
              <div className="option-actions">
                <button
                  type="button"
                  className="primary"
                  disabled={!executionId || !token || confirming}
                  onClick={() => onConfirmAction?.(executionId, token)}
                >
                  {confirming ? "执行中…" : "确认执行"}
                </button>
              </div>
            </div>
          );
        }

        if (block.type === "tool_result") {
          const deleted = Boolean(block.data?.deleted);
          const invoiceNo = String(block.data?.invoice_no || "");
          if (deleted && invoiceNo) {
            return (
              <div key={key} className="assistant-block">
                <p>
                  已删除发票 <strong>{invoiceNo}</strong>
                </p>
              </div>
            );
          }
          return (
            <div key={key} className="assistant-block">
              <pre className="assistant-json">{JSON.stringify(block.data, null, 2)}</pre>
            </div>
          );
        }

        if (block.type === "statistics") {
          const items = Array.isArray(block.data?.items)
            ? (block.data?.items as Array<Record<string, unknown>>)
            : [];
          const charts = Array.isArray(block.data?.charts)
            ? (block.data?.charts as AssistantChartSpec[])
            : block.data?.chart
              ? [block.data.chart as AssistantChartSpec]
              : [];
          return (
            <div key={key} className="assistant-block">
              {block.data?.title ? <p><strong>{String(block.data.title)}</strong></p> : null}
              {items.length > 0 ? (
                <div className="assistant-detail-grid">
                  {items.flatMap((item, index) => [
                    <span key={`l-${index}`}>{String(item.label || "")}</span>,
                    <strong key={`v-${index}`}>{String(item.value ?? "-")}</strong>,
                  ])}
                </div>
              ) : null}
              {charts.map((chart, chartIndex) => (
                <AssistantStatsChart key={`${key}-chart-${chartIndex}`} chart={chart} />
              ))}
              {items.length === 0 && charts.length === 0 ? (
                <pre className="assistant-json">{JSON.stringify(block.data, null, 2)}</pre>
              ) : null}
            </div>
          );
        }

        return null;
      })}
    </div>
  );
}
