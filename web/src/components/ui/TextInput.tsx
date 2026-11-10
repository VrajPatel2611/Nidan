"use client";

import { forwardRef, useId, useState, type InputHTMLAttributes, type ReactNode } from "react";
import s from "./ui.module.css";
import { cx } from "./cx";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "size"> & {
  label: string;
  hint?: string;
  error?: string;
  /** Shows "n / maxLength" beneath the field. Needs `maxLength`. */
  counter?: boolean;
  /** A control inside the field's border, e.g. a show/hide toggle. */
  trailing?: ReactNode;
};

export const TextInput = forwardRef<HTMLInputElement, Props>(function TextInput(
  { label, hint, error, counter, trailing, id, maxLength, onChange, value, defaultValue, ...rest },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  const [length, setLength] = useState(String(value ?? defaultValue ?? "").length);
  const describedBy = [error && errorId, hint && hintId].filter(Boolean).join(" ") || undefined;

  return (
    <div className={s.field}>
      <label className={s.label} htmlFor={inputId}>{label}</label>
      <div className={cx(s.control, error && s.invalid)}>
        <input
          ref={ref}
          id={inputId}
          className={s.input}
          maxLength={maxLength}
          value={value}
          defaultValue={defaultValue}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          onChange={(e) => { setLength(e.target.value.length); onChange?.(e); }}
          {...rest}
        />
        {trailing && <span className={s.trailing}>{trailing}</span>}
      </div>
      {error && <span id={errorId} className={s.error}>{error}</span>}
      {(hint || (counter && maxLength)) && (
        <span className={s.meta}>
          <span id={hintId}>{hint}</span>
          {counter && maxLength ? <span aria-live="polite">{length} / {maxLength}</span> : null}
        </span>
      )}
    </div>
  );
});
