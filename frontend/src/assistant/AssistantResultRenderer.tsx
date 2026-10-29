import type { AssistantBlock } from "./assistantTypes";

function asItems(data?: Record<string, unknown>): Array<Record<string, unknown>> {
  const items = data?.items;
  return Array.isArray(items) ? (items as Array<Record<string, unknown>>) : [];
}

export function AssistantResultRenderer({
  blocks,
  onNavigate,
  onFollowUp,
}: {
  blocks: AssistantBlock[];
  onNavigate?: (viewId: string) => void;
  onFollowUp?: (text: string) => void;
}) {
  if (!blocks?.length) return null;

  return (
    <div className="assistant-blocks">
      {blocks.map((block, index) => {
        const key = `${block.type}-${index}`;
        if (block.type === "text" || block.type === "clarification" || block.type === "error") {
          return (
            <div key={key} className={`assistant-block assistant-block-${block.type}`}>
              <p>{String(block.data?.text || block.data?.message || "")}</p>
            </div>
          );
        }

        if (block.type === "notice_list") {
          const single = block.data?.item as Record<string, unknown> | undefined;
          const items = single ? [single] : asItems(block.data);
          return (
            <div key={key} className="assistant-block">
              <div className="table">
                <div className="table-row assistant-result-table head">
                  <span>标题</span>
                  <span>区域</span>
                  <span>发布时间</span>
                  <span>操作</span>
                </div>
                {items.map((item) => (
                  <div className="table-row assistant-result-table" key={String(item.id)}>
                    <strong>{String(item.title || item.noticeTitle || "-")}</strong>
                    <span>{String(item.region || item.regionName || "-")}</span>
                    <span>{String(item.publish_time || item.publishTime || "-")}</span>
                    <span className="option-actions">
                      {!single && (
                        <button
                          type="button"
                          className="copy-link"
                          onClick={() => onFollowUp?.(`打开公告 ${item.id}`)}
                        >
                          打开
                        </button>
                      )}
                    </span>
                  </div>
                ))}
                {items.length === 0 && <div className="table-empty">暂无公告</div>}
              </div>
              <em>
                共 {String(block.data?.total ?? items.length)} 条
                {block.data?.page ? ` · 第 ${String(block.data.page)} 页` : ""}
              </em>
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
                    item.id ||
                    "-";
                  const summary =
                    item.buyer_name ||
                    item.status ||
                    item.brand ||
                    item.region ||
                    item.amount ||
                    "";
                  const noticeId = item.notice_id || item.noticeRawId;
                  return (
                    <div className="table-row assistant-result-table" key={String(item.id || i)}>
                      <strong>{String(name)}</strong>
                      <span>{String(summary || "-")}</span>
                      <span className="option-actions">
                        {noticeId ? (
                          <button
                            type="button"
                            className="copy-link"
                            onClick={() => onFollowUp?.(`打开公告 ${noticeId}`)}
                          >
                            来源公告
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
                {history.slice(0, 8).map((item) => (
                  <div className="table-row assistant-result-table" key={String(item.id)}>
                    <strong>{String(item.title || "-")}</strong>
                    <span>{String(item.publish_time || "-")}</span>
                    <span />
                    <span className="option-actions">
                      <button
                        type="button"
                        className="copy-link"
                        onClick={() => onFollowUp?.(`打开公告 ${item.id}`)}
                      >
                        打开
                      </button>
                    </span>
                  </div>
                ))}
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

        if (block.type === "tool_result" || block.type === "statistics") {
          return (
            <div key={key} className="assistant-block">
              <pre className="assistant-json">{JSON.stringify(block.data, null, 2)}</pre>
            </div>
          );
        }

        return null;
      })}
    </div>
  );
}
