const FALLBACK_NOTICE_KINDS = ["采购公告", "竞价公告", "询比公告", "成交公告", "终止公告", "失败公告", "废标公告"];

export function noticeKindOptions(options?: string[]) {
  const merged = [...(options || []), ...FALLBACK_NOTICE_KINDS];
  const seen = new Set<string>();
  const result: string[] = [];
  for (const kind of merged) {
    const text = (kind || "").trim();
    if (!text || seen.has(text)) continue;
    seen.add(text);
    result.push(text);
  }
  return result;
}

export function NoticeKindMultiSelect({
  options,
  value,
  onChange,
  ariaLabel = "公告类型",
}: {
  options: string[];
  value: string[];
  onChange: (next: string[]) => void;
  ariaLabel?: string;
}) {
  const kinds = noticeKindOptions(options);
  return (
    <div className="segmented notice-kind-multi" role="group" aria-label={ariaLabel}>
      <button type="button" className={value.length === 0 ? "active" : ""} onClick={() => onChange([])}>
        全部类型
      </button>
      {kinds.map((kind) => {
        const active = value.includes(kind);
        return (
          <button
            key={kind}
            type="button"
            className={active ? "active" : ""}
            onClick={() => {
              if (active) onChange(value.filter((item) => item !== kind));
              else onChange([...value, kind]);
            }}
          >
            {kind}
          </button>
        );
      })}
    </div>
  );
}
