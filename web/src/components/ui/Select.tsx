import { useId, type SelectHTMLAttributes } from "react";
import s from "./ui.module.css";
import { cx } from "./cx";

/** A native `<select>` — which is what mobile needs (UX_SPEC §3.5). */
export function Select({ label, error, id, children, ...rest }:
  SelectHTMLAttributes<HTMLSelectElement> & { label: string; error?: string }) {
  const autoId = useId();
  const selectId = id ?? autoId;
  return (
    <div className={s.field}>
      <label className={s.label} htmlFor={selectId}>{label}</label>
      <div className={cx(s.control, error && s.invalid)}>
        <select id={selectId} className={s.select} aria-invalid={error ? true : undefined}
                aria-describedby={error ? `${selectId}-error` : undefined} {...rest}>
          {children}
        </select>
      </div>
      {error && <span id={`${selectId}-error`} className={s.error}>{error}</span>}
    </div>
  );
}
