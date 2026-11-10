import s from "./ui.module.css";
import { cx } from "./cx";

/** Inline only (UX_SPEC §3.5). Pass `label=""` when the surrounding text already says what is happening. */
export function Spinner({ size = "md", label = "Loading" }: { size?: "sm" | "md"; label?: string }) {
  return (
    <span
      className={cx(s.spinner, size === "sm" ? s.spinnerSm : s.spinnerMd)}
      role={label ? "status" : undefined}
      aria-label={label || undefined}
      aria-hidden={label ? undefined : true}
    />
  );
}
