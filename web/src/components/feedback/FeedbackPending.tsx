"use client";

/**
 * S-12 on the feedback route: the API answered `feedback_not_ready`. Asks
 * again after its `retry_after_ms`, and gives up into S-12's "Failed" state
 * after a while rather than spinning for ever.
 */
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AssessmentPending } from "./AssessmentPending";

export const GIVE_UP_AFTER = 8;          // attempts, ≈ 12 s at the API's 1.5 s

export function FeedbackPending({ retryAfterMs }: { retryAfterMs: number }) {
  const router = useRouter();
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (attempt >= GIVE_UP_AFTER) return;
    const t = setTimeout(() => { setAttempt((a) => a + 1); router.refresh(); }, retryAfterMs);
    return () => clearTimeout(t);
  }, [attempt, retryAfterMs, router]);

  return <AssessmentPending failed={attempt >= GIVE_UP_AFTER} onRetry={() => { setAttempt(0); router.refresh(); }} />;
}
