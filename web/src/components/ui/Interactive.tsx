"use client";

/**
 * The components with behaviour (UX_SPEC §3.5): Banner, Modal, Tabs,
 * Accordion, Tooltip. Toast is in Toast.tsx because it needs a provider.
 */
import {
  useCallback, useEffect, useId, useRef, useState,
  type KeyboardEvent, type ReactElement, type ReactNode,
} from "react";
import { Button } from "./Button";
import s from "./ui.module.css";
import { cx } from "./cx";

// ── Banner ────────────────────────────────────────────────────────────

const BANNER = { info: s.info, success: s.success, warning: s.warning, error: s.errorBanner };

export function Banner({ tone = "info", children, onDismiss }:
  { tone?: keyof typeof BANNER; children: ReactNode; onDismiss?: () => void }) {
  const [open, setOpen] = useState(true);
  if (!open) return null;
  return (
    <div className={cx(s.banner, BANNER[tone])} role={tone === "error" ? "alert" : "status"}>
      <div className={s.bannerBody}>{children}</div>
      {onDismiss && (
        <button type="button" className={s.dismiss} aria-label="Dismiss"
                onClick={() => { setOpen(false); onDismiss(); }}>×</button>
      )}
    </div>
  );
}

// ── Modal ─────────────────────────────────────────────────────────────

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Focus-trapped (UX_SPEC §3.5). Focus moves in on open, Tab cycles inside,
 * Escape closes, and focus returns to whatever opened it.
 */
export function Modal({ open, title, onClose, children, actions, variant = "default", dismissible = true }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode;
  actions?: ReactNode; variant?: "default" | "destructive"; dismissible?: boolean;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const first = panel.current?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? panel.current)?.focus();
    return () => opener?.focus?.();
  }, [open]);

  const onKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape" && dismissible) { e.stopPropagation(); onClose(); return; }
    if (e.key !== "Tab" || !panel.current) return;
    const items = [...panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
    if (items.length === 0) { e.preventDefault(); return; }
    const first = items[0]!, last = items[items.length - 1]!;
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }, [dismissible, onClose]);

  if (!open) return null;
  return (
    <div className={s.overlay} onMouseDown={(e) => { if (dismissible && e.target === e.currentTarget) onClose(); }}>
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
           className={cx(s.modal, variant === "destructive" && s.modalDestructive)} onKeyDown={onKeyDown}>
        <h2 id={titleId} className={s.modalTitle}>{title}</h2>
        {children}
        {actions && <div className={s.modalActions}>{actions}</div>}
      </div>
    </div>
  );
}

/** A destructive confirmation (UX_SPEC §5.5): the confirm button is red and never focused first. */
export function ConfirmModal({ open, title, children, confirmLabel, onConfirm, onClose, loading }: {
  open: boolean; title: string; children: ReactNode; confirmLabel: string;
  onConfirm: () => void; onClose: () => void; loading?: boolean;
}) {
  return (
    <Modal open={open} title={title} onClose={onClose} variant="destructive"
           actions={<>
             <Button variant="secondary" onClick={onClose}>Cancel</Button>
             <Button variant="destructive" onClick={onConfirm} loading={loading}>{confirmLabel}</Button>
           </>}>
      {children}
    </Modal>
  );
}

// ── Tabs ──────────────────────────────────────────────────────────────

export type TabItem = { id: string; label: string; panel: ReactNode };

/** Keyboard-navigable: ←/→ move, Home/End jump, and only the active tab is in the Tab order. */
export function Tabs({ tabs, initial, onChange }: { tabs: TabItem[]; initial?: string; onChange?: (id: string) => void }) {
  const [active, setActive] = useState(initial ?? tabs[0]?.id);
  const base = useId();
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  const select = (i: number) => {
    const tab = tabs[(i + tabs.length) % tabs.length]!;
    setActive(tab.id);
    onChange?.(tab.id);
    refs.current[(i + tabs.length) % tabs.length]?.focus();
  };

  const onKeyDown = (e: KeyboardEvent, i: number) => {
    const move = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
    if (move === undefined) return;
    e.preventDefault();
    select(move);
  };

  return (
    <div>
      <div role="tablist" className={s.tablist}>
        {tabs.map((t, i) => (
          <button key={t.id} ref={(el) => { refs.current[i] = el; }}
                  role="tab" type="button" id={`${base}-tab-${t.id}`}
                  aria-selected={t.id === active} aria-controls={`${base}-panel-${t.id}`}
                  tabIndex={t.id === active ? 0 : -1} className={s.tab}
                  onClick={() => select(i)} onKeyDown={(e) => onKeyDown(e, i)}>
            {t.label}
          </button>
        ))}
      </div>
      {tabs.map((t) => (
        <div key={t.id} role="tabpanel" id={`${base}-panel-${t.id}`}
             aria-labelledby={`${base}-tab-${t.id}`} hidden={t.id !== active} tabIndex={0}>
          {t.panel}
        </div>
      ))}
    </div>
  );
}

// ── Accordion ─────────────────────────────────────────────────────────

export function Accordion({ items }: { items: Array<{ id: string; title: ReactNode; body: ReactNode; open?: boolean }> }) {
  const [openIds, setOpenIds] = useState(() => new Set(items.filter((i) => i.open).map((i) => i.id)));
  const base = useId();
  const toggle = (id: string) => setOpenIds((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  return (
    <div className={s.accordion}>
      {items.map((item) => {
        const open = openIds.has(item.id);
        return (
          <div key={item.id} className={s.accordionItem}>
            <button type="button" className={s.accordionTrigger} aria-expanded={open}
                    aria-controls={`${base}-${item.id}`} onClick={() => toggle(item.id)}>
              {item.title}<span className={s.chevron} aria-hidden>▾</span>
            </button>
            <div id={`${base}-${item.id}`} role="region" hidden={!open} className={s.accordionPanel}>
              {item.body}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Tooltip ───────────────────────────────────────────────────────────

/** Keyboard-accessible: shows on focus as well as hover, Escape hides. The child must be focusable. */
export function Tooltip({ text, children }: { text: string; children: ReactElement }) {
  const [shown, setShown] = useState(false);
  const id = useId();
  return (
    <span className={s.tooltipWrap}
          onMouseEnter={() => setShown(true)} onMouseLeave={() => setShown(false)}
          onFocus={() => setShown(true)} onBlur={() => setShown(false)}
          onKeyDown={(e) => { if (e.key === "Escape") setShown(false); }}
          aria-describedby={shown ? id : undefined}>
      {children}
      {shown && <span role="tooltip" id={id} className={s.tooltip}>{text}</span>}
    </span>
  );
}
