import { useEffect, useRef, useState } from "react";

const WEEKDAY_LABELS = ["日", "一", "二", "三", "四", "五", "六"];

function formatLocalDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function localDateTimeInputValue(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function parsePickerDate(value?: string) {
  if (!value) return null;
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/);
  if (!match) return null;
  const date = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
    Number(match[4] ?? "0"),
    Number(match[5] ?? "0"),
  );
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatPickerDisplay(value: string, mode: "date" | "datetime", format: "zh" | "iso" = "zh") {
  const date = parsePickerDate(value);
  if (!date) return "";
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  if (format === "iso") {
    const text = `${y}-${m}-${d}`;
    if (mode === "datetime") {
      return `${text} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
    }
    return text;
  }
  const text = `${y}年${m}月${d}日`;
  if (mode === "datetime") {
    return `${text} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
  }
  return text;
}

function emitPickerValue(date: Date, mode: "date" | "datetime") {
  return mode === "datetime" ? localDateTimeInputValue(date) : formatLocalDate(date);
}

export function DateTimeField({
  value,
  onChange,
  mode = "date",
  format = "zh",
  className = "",
  placeholder,
  ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  mode?: "date" | "datetime";
  format?: "zh" | "iso";
  className?: string;
  placeholder?: string;
  ariaLabel?: string;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const selected = parsePickerDate(value);
  const [open, setOpen] = useState(false);
  const [viewYear, setViewYear] = useState(() => selected?.getFullYear() ?? new Date().getFullYear());
  const [viewMonth, setViewMonth] = useState(() => selected?.getMonth() ?? new Date().getMonth());

  useEffect(() => {
    if (!open) return;
    const current = parsePickerDate(value) ?? new Date();
    setViewYear(current.getFullYear());
    setViewMonth(current.getMonth());
  }, [open, value]);

  useEffect(() => {
    if (!open) return;
    function onDoc(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  function shiftMonth(delta: number) {
    const next = new Date(viewYear, viewMonth + delta, 1);
    setViewYear(next.getFullYear());
    setViewMonth(next.getMonth());
  }

  function applyDate(day: number, closeAfter: boolean) {
    const base = selected ?? new Date();
    const next = new Date(
      viewYear,
      viewMonth,
      day,
      mode === "datetime" ? base.getHours() : 0,
      mode === "datetime" ? base.getMinutes() : 0,
    );
    onChange(emitPickerValue(next, mode));
    if (closeAfter) setOpen(false);
  }

  function applyTime(hours: number, minutes: number) {
    const base = selected ?? new Date();
    onChange(emitPickerValue(new Date(base.getFullYear(), base.getMonth(), base.getDate(), hours, minutes), mode));
  }

  const firstWeekday = new Date(viewYear, viewMonth, 1).getDay();
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const now = new Date();
  const cells: Array<number | null> = [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
  ];

  return (
    <div className={`date-time-field ${className}`.trim()} ref={rootRef} lang="zh-CN">
      <input
        readOnly
        value={formatPickerDisplay(value, mode, format)}
        placeholder={placeholder ?? (mode === "datetime" ? "选择日期时间" : format === "iso" ? "yyyy-mm-dd" : "选择日期")}
        aria-label={ariaLabel ?? (mode === "datetime" ? "选择日期时间" : "选择日期")}
        className="date-time-field-input"
        onClick={() => setOpen(true)}
        onFocus={() => setOpen(true)}
      />
      {open && (
        <div className="date-time-calendar" role="dialog" aria-label="选择日期" lang="zh-CN">
          <div className="date-time-calendar-head">
            <button type="button" className="ghost" onClick={() => shiftMonth(-1)} aria-label="上个月">
              ‹
            </button>
            <strong>
              {viewYear}年{viewMonth + 1}月
            </strong>
            <button type="button" className="ghost" onClick={() => shiftMonth(1)} aria-label="下个月">
              ›
            </button>
          </div>
          <div className="date-time-weekdays">
            {WEEKDAY_LABELS.map((label) => (
              <span key={label}>{label}</span>
            ))}
          </div>
          <div className="date-time-days">
            {cells.map((day, index) => {
              if (!day) return <span key={`empty-${index}`} />;
              const isSelected = Boolean(
                selected && selected.getFullYear() === viewYear && selected.getMonth() === viewMonth && selected.getDate() === day,
              );
              const isToday = now.getFullYear() === viewYear && now.getMonth() === viewMonth && now.getDate() === day;
              return (
                <button
                  type="button"
                  key={day}
                  className={`${isSelected ? "is-selected" : ""} ${isToday ? "is-today" : ""}`.trim()}
                  onClick={() => applyDate(day, mode === "date")}
                >
                  {day}
                </button>
              );
            })}
          </div>
          {mode === "datetime" && (
            <div className="date-time-clock">
              <label>
                <span>时</span>
                <select
                  value={selected ? selected.getHours() : 0}
                  onChange={(event) => applyTime(Number(event.target.value), selected?.getMinutes() ?? 0)}
                >
                  {Array.from({ length: 24 }, (_, hour) => (
                    <option key={hour} value={hour}>
                      {String(hour).padStart(2, "0")}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>分</span>
                <select
                  value={selected ? selected.getMinutes() : 0}
                  onChange={(event) => applyTime(selected?.getHours() ?? 0, Number(event.target.value))}
                >
                  {Array.from({ length: 60 }, (_, minute) => (
                    <option key={minute} value={minute}>
                      {String(minute).padStart(2, "0")}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
          <div className="date-time-calendar-actions">
            <button
              type="button"
              className="ghost"
              onClick={() => {
                onChange("");
                setOpen(false);
              }}
            >
              清除
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() => {
                onChange(emitPickerValue(new Date(), mode));
                setOpen(false);
              }}
            >
              今天
            </button>
            {mode === "datetime" && (
              <button type="button" className="primary" onClick={() => setOpen(false)}>
                确定
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
