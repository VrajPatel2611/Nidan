import Link from "next/link";
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
  /**
   * Navigate instead of act: renders a link that looks like a button. A real
   * <button> inside a <Link> is invalid HTML and announces twice to a screen
   * reader, so it is one element or the other, never both.
   */
  href?: string;
};

export function Button({
  variant = "primary", size = "md", loading = false, loadingLabel, block, href,
  disabled, className, children, type = "button", ...rest
}: Props) {
  const classes = cx(s.button, s[variant], s[size], block && s.block, className);
  if (href && !disabled) {
    return <Link href={href} className={classes}>{children}</Link>;
  }
  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && <Spinner size="sm" label="" />}
      {loading && loadingLabel ? loadingLabel : children}
    </button>
  );
}
