"use client";

import { useEffect, useRef, useState } from "react";
import { TextInput } from "@/components/ui";
import s from "./auth.module.css";

/** Password with a show/hide toggle (S-02). No strength meter — U1. */
export function PasswordField({ name = "password", label = "Password", hint, error, autoComplete }: {
  name?: string; label?: string; hint?: string; error?: string; autoComplete: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <TextInput
      name={name} label={label} hint={hint} error={error} autoComplete={autoComplete}
      type={visible ? "text" : "password"} required
      trailing={
        <button type="button" className={s.reveal} onClick={() => setVisible((v) => !v)}
                aria-label={visible ? "Hide password" : "Show password"} aria-pressed={visible}>
          {visible ? "Hide" : "Show"}
        </button>
      }
    />
  );
}

/**
 * What every auth form carries besides what the person typed: where to go
 * afterwards, their timezone (POST /me records it), and a trial to claim.
 */
export function CarriedFields({ next, anonymousId }: { next?: string | null; anonymousId?: string | null }) {
  // Written to the DOM after hydration rather than rendered: the server cannot
  // know the browser's timezone, and rendering it would mismatch.
  const tz = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (tz.current) tz.current.value = Intl.DateTimeFormat().resolvedOptions().timeZone;
  }, []);
  return (
    <>
      {next && <input type="hidden" name="next" value={next} />}
      {anonymousId && <input type="hidden" name="anonymous_id" value={anonymousId} />}
      <input ref={tz} type="hidden" name="tz" defaultValue="" />
    </>
  );
}

/**
 * Seconds until `until` (epoch ms, from the server), ticking each second —
 * a rate-limited form's live countdown (S-03, S-06). 0 when unlocked.
 */
export function useCountdown(until: number | undefined): number {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    if (!until) return;
    const tick = () => setNow(Date.now());
    const first = setTimeout(tick, 0);
    const id = setInterval(tick, 1000);
    return () => { clearTimeout(first); clearInterval(id); };
  }, [until]);
  if (!until) return 0;
  if (now === null) return 1;            // locked until the first tick lands
  return Math.max(0, Math.ceil((until - now) / 1000));
}

export function formatWait(seconds: number): string {
  const m = Math.floor(seconds / 60), s = seconds % 60;
  return m ? `${m}:${String(s).padStart(2, "0")}` : `${s}s`;
}
