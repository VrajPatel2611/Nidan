"use client";

import { useCallback, useEffect, useId, useRef, type TextareaHTMLAttributes } from "react";
import s from "./ui.module.css";
import { cx } from "./cx";

const MAX_ROWS = 4;   // UX_SPEC §3.5: auto-grow to 4 rows

type Props = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  hint?: string;
  error?: string;
};

export function TextArea({ label, hint, error, id, onChange, rows = 1, ...rest }: Props) {
  const autoId = useId();
  const areaId = id ?? autoId;
  const ref = useRef<HTMLTextAreaElement>(null);

  const grow = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const line = parseFloat(getComputedStyle(el).lineHeight) || 26;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, line * MAX_ROWS + 16)}px`;
    el.style.overflowY = el.scrollHeight > line * MAX_ROWS + 16 ? "auto" : "hidden";
  }, []);

  useEffect(grow, [grow, rest.value]);

  return (
    <div className={s.field}>
      <label className={s.label} htmlFor={areaId}>{label}</label>
      <div className={cx(s.control, error && s.invalid)}>
        <textarea
          ref={ref}
          id={areaId}
          rows={rows}
          className={s.textarea}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${areaId}-error` : hint ? `${areaId}-hint` : undefined}
          onChange={(e) => { grow(); onChange?.(e); }}
          {...rest}
        />
      </div>
      {error && <span id={`${areaId}-error`} className={s.error}>{error}</span>}
      {hint && !error && <span id={`${areaId}-hint`} className={s.meta}>{hint}</span>}
    </div>
  );
}
