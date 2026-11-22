"use client";

/**
 * S-12 · Assessment pending. Full-screen between submission and feedback,
 * and **never blank**: the copy changes after 3 s, and a failure says what is
 * safe ("We've saved your consultation") before offering to try again.
 */
import { useEffect, useState } from "react";
import { Button } from "@/components/ui";
import s from "./feedback.module.css";

export const SLOW_AFTER_MS = 3000;

export function AssessmentPending({ failed = false, onRetry }: { failed?: boolean; onRetry?: () => void }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className={s.pending} role="status" aria-live="polite">
      {failed ? (
        <div>
          <p className={s.pendingTitle}>We&apos;ve saved your consultation but couldn&apos;t prepare feedback yet.</p>
          {onRetry && <Button onClick={onRetry}>Try again</Button>}
          <p className={s.pendingNote}>We&apos;ll email you when it&apos;s ready.</p>
        </div>
      ) : (
        <div>
          <p className={s.pendingTitle}>Reviewing your consultation…</p>
          <div className={s.indeterminate} aria-hidden><span /></div>
          {slow && <p className={s.pendingNote}>Just putting your feedback together.</p>}
        </div>
      )}
    </div>
  );
}
