"use client";

/**
 * S-11 · Diagnosis submission.
 *
 * The copy says one thing: this cannot be undone. **No readiness or
 * completeness hint, ever** (`PRD` FR-7.3, U2) — not "you've only asked 3
 * questions", not "you haven't ordered any tests", not "most students…". It
 * receives nothing about the consultation it could build such a hint from.
 */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { diagnose } from "@/app/case/actions";
import { Banner, Button, Modal } from "@/components/ui";
import { MAX_DIAGNOSIS } from "@/lib/consultation";

export function DiagnosisModal({ open, onClose, sessionId, patientFirstName }: {
  open: boolean; onClose: () => void; sessionId: string; patientFirstName: string;
}) {
  const router = useRouter();
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // One key per attempt at concluding: a retried submit is the same conclusion (§2.8).
  const idempotency = useRef<string | null>(null);

  async function submit() {
    if (!text.trim() || submitting) return;
    idempotency.current ??= crypto.randomUUID();
    setSubmitting(true);
    setError(null);
    const res = await diagnose(sessionId, text.trim(), idempotency.current);
    if (res.ok || res.code === "session_concluded") {
      router.push(`/case/${encodeURIComponent(sessionId)}/feedback`);
      return;
    }
    setSubmitting(false);
    setError("We couldn't submit your diagnosis. Your answer is still here — please try again.");
  }

  return (
    <Modal open={open} onClose={onClose} title="Your diagnosis" dismissible={!submitting}
           actions={<>
             <Button variant="secondary" onClick={onClose} disabled={submitting}>Cancel</Button>
             <Button onClick={submit} loading={submitting} loadingLabel="Submitting…" disabled={!text.trim()}>
               Submit diagnosis
             </Button>
           </>}>
      {error && <Banner tone="error">{error}</Banner>}
      <label htmlFor="diagnosis-text" style={{ display: "block", marginBottom: "var(--s-2)" }}>
        What do you think is going on with {patientFirstName}?
      </label>
      <textarea id="diagnosis-text" value={text} maxLength={MAX_DIAGNOSIS} rows={3} disabled={submitting}
                onChange={(e) => setText(e.target.value)}
                style={{ width: "100%", font: "var(--t-body)", padding: "var(--s-2) var(--s-3)",
                         border: "1px solid var(--rule)", borderRadius: "var(--r-sm)", resize: "vertical" }} />
      <p style={{ font: "var(--t-body-sm)", color: "var(--muted)", margin: "var(--s-2) 0 0" }}>
        This ends the consultation and can&apos;t be undone.
      </p>
    </Modal>
  );
}
