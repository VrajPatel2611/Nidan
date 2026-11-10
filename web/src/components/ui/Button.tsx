import type { ButtonHTMLAttributes } from "react";
import { Spinner } from "./Spinner";
import s from "./ui.module.css";
import { cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "md" | "lg";
  /** Shows a spinner and blocks clicks. `loadingLabel` replaces the text if given. */
  loading?: boolean;
  loadingLabel?: string;
  block?: boolean;
};

export function Button({
  variant = "primary", size = "md", loading = false, loadingLabel, block,
  disabled, className, children, type = "button", ...rest
}: Props) {
  return (
    <button
      type={type}
      className={cx(s.button, s[variant], s[size], block && s.block, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && <Spinner size="sm" label="" />}
      {loading && loadingLabel ? loadingLabel : children}
    </button>
  );
}
