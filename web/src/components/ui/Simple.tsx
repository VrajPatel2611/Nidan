/**
 * The presentational components with no behaviour of their own (UX_SPEC §3.5):
 * Chip, Card, Badge, ProgressBar, StatTile, Avatar, Skeleton, EmptyState.
 */
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import s from "./ui.module.css";
import { cx } from "./cx";

/** Examinations and investigations. `selected` maps to aria-pressed. */
export function Chip({ selected = false, className, children, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean }) {
  return (
    <button type="button" className={cx(s.chip, className)} aria-pressed={selected} {...rest}>
      {children}
    </button>
  );
}

export function Card({ variant = "flat", className, ...rest }:
  HTMLAttributes<HTMLDivElement> & { variant?: "flat" | "elevated" }) {
  return <div className={cx(s.card, variant === "elevated" && s.elevated, className)} {...rest} />;
}

const BADGE = { neutral: s.badgeNeutral, green: s.badgeGreen, amber: s.badgeAmber, red: s.badgeRed };

/** Scorecard rows. Colours are semantic (§3.1): amber needs attention, green done, red missed. */
export function Badge({ tone = "neutral", children }: { tone?: keyof typeof BADGE; children: ReactNode }) {
  return <span className={cx(s.badge, BADGE[tone])}>{children}</span>;
}

/**
 * **Feedback screen only** (UX_SPEC §3.5, `PRD` P2). Never during a
 * consultation: a visible meter teaches the meter, not the skill.
 */
export function ProgressBar({ value, max = 100, label }: { value: number; max?: number; label: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className={s.progress} role="progressbar" aria-label={label}
         aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
      <div className={s.progressFill} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function StatTile({ value, label }: { value: ReactNode; label: string }) {
  return (
    <div className={s.stat}>
      <span className={s.statValue}>{value}</span>
      <span className={s.statLabel}>{label}</span>
    </div>
  );
}

export function initials(name: string): string {
  // For an email address, only the part before the @ is a name.
  const parts = name.trim().split("@")[0]!.split(/[\s._-]+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0]![0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1]![0] ?? "" : "";
  return (first + last).toUpperCase();
}

export function Avatar({ name, src, size = 32 }: { name: string; src?: string | null; size?: number }) {
  return (
    <span className={s.avatar} style={{ width: size, height: size }} aria-label={name} role="img">
      {/* eslint-disable-next-line @next/next/no-img-element -- avatars are tiny and external */}
      {src ? <img src={src} alt="" /> : initials(name)}
    </span>
  );
}

export function Skeleton({ variant = "text", lines = 3 }: { variant?: "text" | "card" | "list"; lines?: number }) {
  if (variant === "card") return <span className={cx(s.skeleton, s.skeletonCard)} aria-hidden />;
  const rowClass = variant === "list" ? s.skeletonRow : s.skeletonText;
  return (
    <span className={variant === "list" ? s.skeletonList : undefined} aria-hidden style={{ display: "block" }}>
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className={cx(s.skeleton, rowClass)}
              style={variant === "text" && i === lines - 1 ? { width: "60%" } : undefined} />
      ))}
    </span>
  );
}

export function EmptyState({ icon, heading, body, action }:
  { icon?: ReactNode; heading: string; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className={s.empty}>
      {icon && <span className={s.emptyIcon} aria-hidden>{icon}</span>}
      <h3 className={s.emptyHeading}>{heading}</h3>
      {body && <p className={s.emptyBody}>{body}</p>}
      {action}
    </div>
  );
}
