import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Check, Copy, Search, X } from "lucide-react";

/**
 * 后台列表统一可选每页条数。
 * 新模块分页必须用下方 `Pagination`（首页/尾页/上下页/跳转/每页条数），见规则 admin-list-ui 与 skill admin-list-pagination。
 */
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100] as const;
export type PageSizeOption = (typeof PAGE_SIZE_OPTIONS)[number];

export async function writeClipboardText(text: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Clipboard API can be unavailable in HTTP or embedded deployments.
    }
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("Clipboard write failed");
}

export function QuickCopyButton({ text, label }: { text?: string; label: string }) {
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");
  const value = text?.trim() ?? "";
  if (!value) return null;

  return (
    <button
      type="button"
      className={`quick-copy-btn${status === "copied" ? " is-copied" : ""}${status === "failed" ? " is-failed" : ""}`}
      title={status === "copied" ? `已复制${label}` : status === "failed" ? `${label}复制失败` : `复制${label}`}
      aria-label={`复制${label}`}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        void writeClipboardText(value)
          .then(() => {
            setStatus("copied");
            window.setTimeout(() => setStatus("idle"), 1600);
          })
          .catch(() => {
            setStatus("failed");
            window.setTimeout(() => setStatus("idle"), 1600);
          });
      }}
    >
      {status === "copied" ? <Check size={13} strokeWidth={2.4} /> : <Copy size={13} strokeWidth={2.2} />}
    </button>
  );
}

export function CopyableLine({
  text,
  label,
  children,
  className = "",
  onOpen,
}: {
  text?: string;
  label: string;
  children: ReactNode;
  className?: string;
  onOpen?: () => void;
}) {
  return (
    <span className={`copyable-line ${className}`.trim()}>
      {onOpen ? (
        <button type="button" className="copyable-line-open" onClick={onOpen}>{children}</button>
      ) : (
        <span className="copyable-line-text">{children}</span>
      )}
      <QuickCopyButton text={text} label={label} />
    </span>
  );
}

export function SearchField({
  value,
  onChange,
  placeholder,
  ariaLabel,
  className,
  clearReveal = "always",
  onSubmit,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  ariaLabel?: string;
  className?: string;
  clearReveal?: "always" | "hover";
  onSubmit?: () => void;
}) {
  return (
    <div className={["project-search", className].filter(Boolean).join(" ")}>
      <Search size={16} />
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && onSubmit) {
            event.preventDefault();
            onSubmit();
          }
        }}
        placeholder={placeholder}
        aria-label={ariaLabel ?? placeholder}
      />
      {value ? (
        <button
          type="button"
          className={`search-clear${clearReveal === "hover" ? " is-hover-reveal" : ""}`}
          aria-label="清空搜索"
          onClick={() => onChange("")}
        >
          <X size={14} />
        </button>
      ) : null}
    </div>
  );
}

export function PanelTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="panel-title">
      <div>
        <h2>{title}</h2>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
    </div>
  );
}

export function Pagination({
  page,
  totalPages,
  total,
  pageSize,
  onPageChange,
  onPageSizeChange,
  setPageSize,
  pageSizeOptions = PAGE_SIZE_OPTIONS,
}: {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  /** 兼容 useServerPagedList 展开：`{...pageState}` */
  setPageSize?: (pageSize: number) => void;
  pageSizeOptions?: readonly number[];
}) {
  const changePageSize = onPageSizeChange ?? setPageSize;
  const safeTotalPages = Math.max(1, totalPages || 1);
  const [jumpValue, setJumpValue] = useState(String(page));

  useEffect(() => {
    setJumpValue(String(page));
  }, [page]);

  if (total <= 0) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  const sizeChoices = pageSizeOptions.includes(pageSize)
    ? pageSizeOptions
    : [...pageSizeOptions, pageSize].sort((a, b) => a - b);

  function goJump() {
    const next = Number.parseInt(String(jumpValue).trim(), 10);
    if (!Number.isFinite(next)) {
      setJumpValue(String(page));
      return;
    }
    onPageChange(Math.min(safeTotalPages, Math.max(1, next)));
  }

  return (
    <div className="pagination" role="navigation" aria-label="分页">
      <span className="pagination-summary">{start}-{end} / {total}</span>
      <label className="pagination-size">
        <span>每页</span>
        <select
          value={pageSize}
          disabled={!changePageSize}
          aria-label="每页条数"
          onChange={(event) => {
            if (!changePageSize) return;
            const next = Number(event.target.value);
            if (!Number.isFinite(next) || next === pageSize) return;
            changePageSize(next);
          }}
        >
          {sizeChoices.map((size) => (
            <option key={size} value={size}>{size}</option>
          ))}
        </select>
        <span>条</span>
      </label>
      <div className="pagination-actions">
        <button type="button" className="ghost" disabled={page <= 1} onClick={() => onPageChange(1)}>首页</button>
        <button type="button" className="ghost" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>上一页</button>
        <strong className="pagination-page">{page} / {safeTotalPages}</strong>
        <button type="button" className="ghost" disabled={page >= safeTotalPages} onClick={() => onPageChange(page + 1)}>下一页</button>
        <button type="button" className="ghost" disabled={page >= safeTotalPages} onClick={() => onPageChange(safeTotalPages)}>末页</button>
      </div>
      <label className="pagination-jump">
        <span>跳至</span>
        <input
          type="number"
          min={1}
          max={safeTotalPages}
          value={jumpValue}
          aria-label="跳转到页码"
          onChange={(event) => setJumpValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              goJump();
            }
          }}
        />
        <span>页</span>
        <button type="button" className="ghost" onClick={goJump}>跳转</button>
      </label>
    </div>
  );
}
