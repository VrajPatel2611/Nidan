"use client";

/**
 * S-10 · Consultation (T-034) — the screen where U2 is enforced absolutely.
 *
 * Deliberately absent, and tested as absent: a question counter, a coverage
 * or progress meter, suggested questions, a timer, "you may want to examine…"
 * hints, a count of what has been ordered, relevance badges, and the top
 * navigation. The component is never given anything to build them from.
 */
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { ask, orderOne } from "@/app/case/actions";
import { Banner, Button, Chip, Modal, Spinner, Tabs, TextInput } from "@/components/ui";
import {
  MAX_QUESTION, SHOW_COUNTER_FROM, askFailure, filterMenu,
  type AskFailure, type MenuGroup, type Ordered,
} from "@/lib/consultation";
import { DiagnosisModal } from "./DiagnosisModal";
import { SmallScreen } from "./SmallScreen";
import s from "./consultation.module.css";

export type Turn = { id: string; who: "patient" | "doctor"; text: string };

export type ConsultationProps = {
  sessionId: string;
  patient: { name?: string; age?: number; sex?: string; presenting_complaint?: string };
  turns: Turn[];
  ordered: Ordered[];
  examinations: MenuGroup[];
  investigations: MenuGroup[];
  /** "2 hours ago" when the learner is coming back to it, otherwise null. */
  resumedFrom: string | null;
  capReached: boolean;
};

type Tab = "examinations" | "investigations" | "ordered";

export function Consultation(p: ConsultationProps) {
  const router = useRouter();
  const input = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);

  const [turns, setTurns] = useState(p.turns);
  const [draft, setDraft] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [failure, setFailure] = useState<AskFailure | null>(p.capReached ? { state: "cap" } : null);
  const [blocked, setBlocked] = useState(false);

  const [ordered, setOrdered] = useState(p.ordered);
  const [loadingKey, setLoadingKey] = useState<string | null>(null);
  const [orderError, setOrderError] = useState(false);
  const [tab, setTab] = useState<Tab>("examinations");
  const [query, setQuery] = useState("");
  const [drawer, setDrawer] = useState(false);
  const [diagnosing, setDiagnosing] = useState(false);

  const done = useMemo(() => new Set(ordered.map((o) => `${o.kind}:${o.key}`)), [ordered]);
  const examined = ordered.filter((o) => o.kind === "examination").map((o) => o.label).reverse();
  const capped = failure?.state === "cap";
  const awaiting = pendingQuestion !== null;
  const firstName = p.patient.name?.split(/\s+/)[0] || "the patient";

  useEffect(() => { if (log.current) log.current.scrollTop = log.current.scrollHeight; }, [turns, pendingQuestion]);

  const send = useCallback(async (text: string) => {
    const question = text.trim();
    if (!question || awaiting || capped) return;
    setPendingQuestion(question);
    setFailure(null);
    const res = await ask(p.sessionId, question);
    setPendingQuestion(null);

    if (res.ok) {
      setTurns((t) => [...t,
        { id: `q${t.length}`, who: "doctor", text: res.question },
        { id: `r${t.length}`, who: "patient", text: res.reply }]);
      setDraft("");
      requestAnimationFrame(() => input.current?.focus());    // focus returns after a reply
      return;
    }

    const f = askFailure(res.code, res.status, res.retryAfter);
    switch (f.state) {
      case "concluded": router.push(`/case/${encodeURIComponent(p.sessionId)}/feedback`); return;
      case "gone": router.push(`/login?next=${encodeURIComponent(`/case/${p.sessionId}`)}`); return;
      case "blocked": setDraft(""); setBlocked(true); return;      // discarded, never sent (FR-4)
      default: setFailure(f);                                       // the typed text stays in the box
    }
  }, [awaiting, capped, p.sessionId, router]);

  // "The patient needs a moment…" retries by itself (S-10 "Rate limited").
  useEffect(() => {
    if (failure?.state !== "rate-limited") return;
    const t = setTimeout(() => { void send(draft); }, failure.retryAfter * 1000);
    return () => clearTimeout(t);
  }, [failure, draft, send]);

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {                         // Shift+Enter is a newline
      e.preventDefault();
      void send(draft);
    }
  }

  async function pick(kind: "examination" | "investigation", key: string) {
    if (done.has(`${kind}:${key}`)) { setTab("ordered"); return; }  // re-view, no second order
    if (loadingKey) return;
    setLoadingKey(`${kind}:${key}`);
    setOrderError(false);
    const res = await orderOne(p.sessionId, kind === "examination" ? "examinations" : "investigations", key);
    setLoadingKey(null);
    if (!res.ok) {
      if (res.code === "session_concluded") router.push(`/case/${encodeURIComponent(p.sessionId)}/feedback`);
      else setOrderError(true);
      return;
    }
    setOrdered((o) => [{ kind, key: res.key, label: res.label, text: res.text, at: res.at },
                       ...o.filter((x) => !(x.kind === kind && x.key === res.key))]);
    setTab("ordered");
  }

  const chips = (kind: "examination" | "investigation", groups: MenuGroup[]) => groups.map((g) => (
    <fieldset key={g.group} className={s.group}>
      <legend className={s.groupName}>{g.group}</legend>
      <div className={s.chips}>
        {g.items.map((i) => {
          const id = `${kind}:${i.key}`;
          return (
            <Chip key={i.key} selected={done.has(id)} onClick={() => pick(kind, i.key)}
                  aria-busy={loadingKey === id || undefined}>
              {loadingKey === id ? <Spinner size="sm" label={`Getting ${i.label}`} /> : null}
              {done.has(id) ? "✓ " : ""}{i.label}
            </Chip>
          );
        })}
      </div>
    </fieldset>
  ));

  const panel = (
    <Tabs value={tab} onChange={(id) => setTab(id as Tab)} tabs={[
      { id: "examinations", label: "Examinations", panel: chips("examination", p.examinations) },
      { id: "investigations", label: "Investigations", panel: (
        <>
          <TextInput label="Search investigations" value={query} onChange={(e) => setQuery(e.target.value)}
                     placeholder="Search by name…" autoComplete="off" />
          {chips("investigation", filterMenu(p.investigations, query))}
          {query && filterMenu(p.investigations, query).length === 0 &&
            <p className={s.empty}>No investigation by that name.</p>}
        </>
      ) },
      { id: "ordered", label: "Ordered", panel: ordered.length === 0
        ? <p className={s.empty}>Results appear here as you examine and investigate.</p>
        : ordered.map((o) => (
          <article key={`${o.kind}:${o.key}`} className={s.result}>
            <h3 className={s.resultLabel}>{o.label}</h3>
            <p className={`${s.resultText} ${o.kind === "investigation" ? s.lab : ""}`}>{o.text}</p>
          </article>
        )) },
    ]} />
  );

  const counterVisible = draft.length > SHOW_COUNTER_FROM;   // characters, never questions

  return (
    <>
      <SmallScreen />
      <div className={s.app}>
        <aside className={s.patient} aria-label="Patient">
          <p className={s.patientLabel}>Patient</p>
          <h1 className={s.patientName}>{p.patient.name}</h1>
          <p className={s.patientMeta}>{[p.patient.age, p.patient.sex].filter(Boolean).join(" · ")}</p>
          {p.patient.presenting_complaint && <p className={s.complaint}>{p.patient.presenting_complaint}</p>}
          {examined.length > 0 && (<>
            <hr className={s.divider} />
            <p className={s.patientLabel}>Examined</p>
            <ul className={s.examined}>{examined.map((label) => <li key={label}>{label}</li>)}</ul>
          </>)}
        </aside>

        <main className={s.centre}>
          <div className={s.stripe}>
            <strong>{p.patient.name}</strong>
            <span>{[p.patient.age, p.patient.sex].filter(Boolean).join(" · ")}</span>
            {p.patient.presenting_complaint && <span>· {p.patient.presenting_complaint}</span>}
          </div>

          {p.resumedFrom && <div style={{ padding: "var(--s-3) var(--s-6) 0" }}>
            <Banner tone="info" onDismiss={() => undefined}>Resumed from {p.resumedFrom}.</Banner>
          </div>}

          <div ref={log} className={s.log} role="log" aria-live="polite" aria-label="Conversation">
            {turns.map((t) => (
              <div key={t.id} className={`${s.msg} ${t.who === "patient" ? s.patientMsg : s.doctorMsg}`}>
                <span className="visually-hidden">{t.who === "patient" ? `${firstName}: ` : "You: "}</span>
                {t.text}
              </div>
            ))}
            {awaiting && (<>
              <div className={`${s.msg} ${s.doctorMsg} ${s.pendingMsg}`}>{pendingQuestion}</div>
              <div className={s.dots} aria-label={`${firstName} is replying`}><span /><span /><span /></div>
            </>)}
          </div>

          <div className={s.composer}>
            {failure?.state === "reply-error" && (
              <Banner tone="error">
                The patient couldn&apos;t respond just now.{" "}
                <Button size="sm" variant="ghost" onClick={() => send(draft)}>Try again</Button>
              </Banner>
            )}
            {failure?.state === "rate-limited" && <Banner tone="info">The patient needs a moment…</Banner>}
            {failure?.state === "too-long" && <Banner tone="error">That question is too long — keep it under {MAX_QUESTION} characters.</Banner>}

            <div className={s.inputRow}>
              <label htmlFor="question" className="visually-hidden">Ask a question</label>
              <textarea id="question" ref={input} className={s.input} rows={2} autoFocus
                        value={draft} maxLength={MAX_QUESTION} placeholder="Ask a question…"
                        disabled={awaiting || capped} onKeyDown={onKeyDown}
                        onChange={(e) => setDraft(e.target.value)} />
              <Button onClick={() => send(draft)} loading={awaiting} disabled={!draft.trim() || capped}>
                Send
              </Button>
            </div>
            {counterVisible && <div className={s.chars} aria-live="polite">{draft.length} / {MAX_QUESTION}</div>}
            {capped && (
              <p className={s.note}>
                You&apos;ve asked 40 questions — that&apos;s plenty. Examine, investigate, or give your diagnosis when ready.
              </p>
            )}
          </div>
          <div className={s.diagnose}>
            <Button variant="secondary" onClick={() => setDiagnosing(true)} disabled={awaiting}>Give diagnosis</Button>
          </div>
        </main>

        {drawer && <div className={s.drawerBackdrop} onClick={() => setDrawer(false)} aria-hidden />}
        <aside className={`${s.panel} ${drawer ? s.panelOpen : ""}`} aria-label="Examine and investigate">
          {orderError && <Banner tone="error" onDismiss={() => setOrderError(false)}>We couldn&apos;t get that result. Please try again.</Banner>}
          {panel}
        </aside>
        <Button className={s.drawerButton} onClick={() => setDrawer((d) => !d)} aria-expanded={drawer}>
          {drawer ? "Close" : "Examine / Investigate"}
        </Button>
      </div>

      <DiagnosisModal open={diagnosing} onClose={() => setDiagnosing(false)}
                      sessionId={p.sessionId} patientFirstName={firstName} />

      <Modal open={blocked} title="Please don't enter real patient information" onClose={() => setBlocked(false)}
             actions={<Button onClick={() => setBlocked(false)}>I understand</Button>}>
        <p>Nidan is a training simulation with synthetic patients. It isn&apos;t secure or appropriate for
          real patient data, and it can&apos;t give clinical advice.</p>
      </Modal>
    </>
  );
}
