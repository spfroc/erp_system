import { useState } from "react";
import type { ReactNode } from "react";
import { Check, Copy, Search, X } from "lucide-react";

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
}: {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}) {
  if (total <= pageSize) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return (
    <div className="pagination">
      <span>{start}-{end} / {total}</span>
      <button className="ghost" disabled={page <= 1} onClick={() => onPageChange(1)}>首页</button>
      <button className="ghost" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>上一页</button>
      <strong>{page} / {totalPages}</strong>
      <button className="ghost" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>下一页</button>
      <button className="ghost" disabled={page >= totalPages} onClick={() => onPageChange(totalPages)}>末页</button>
    </div>
  );
}
