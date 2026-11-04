"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import s from "./ui.module.css";
import { cx } from "./cx";

/** UX_SPEC §3.5: success or error, bottom-right, gone after 4 s. */
export const TOAST_MS = 4000;

type Toast = { id: number; tone: "success" | "error"; text: string };
type Show = (text: string, tone?: Toast["tone"]) => void;

const ToastContext = createContext<Show | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(1);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const show = useCallback<Show>((text, tone = "success") => {
    const id = next.current++;
    setToasts((t) => [...t, { id, tone, text }]);
    timers.current.set(id, setTimeout(() => {
      setToasts((t) => t.filter((x) => x.id !== id));
      timers.current.delete(id);
    }, TOAST_MS));
  }, []);

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(clearTimeout);
  }, []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className={s.toasts} aria-live="polite" aria-atomic="false">
        {toasts.map((t) => (
          <div key={t.id} role={t.tone === "error" ? "alert" : "status"}
               className={cx(s.toast, t.tone === "error" && s.toastError)}>
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): Show {
  const show = useContext(ToastContext);
  if (!show) throw new Error("useToast() outside <ToastProvider>");
  return show;
}
