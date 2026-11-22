"use client";

/**
 * S-13 · Feedback — the product's actual value (T-036).
 *
 * Eight sections, in UX_SPEC's order: outcome first, then process, then the
 * answer last so the learner engages with how they reasoned before learning
 * what it was. Fallback feedback (`rule_fallback`) renders exactly like model
 * feedback, with no badge and no apology — the component never reads
 * `generator` at all.
 */
import { useActionState, useState } from "react";
import { startCase, type ActionState } from "@/app/(app)/actions";
import { rate } from "@/app/case/[id]/feedback/actions";
import { Accordion, Banner, Button, ProgressBar } from "@/components/ui";
import type { Feedback } from "@/lib/api";
import { scorecardRows, scorecardSummary, summaryParts, topicLabel, verdictView, type Row } from "@/lib/feedback";
import s from "./feedback.module.css";

function Rows({ rows }: { rows: Row[] }) {
  return (
    <ul className={s.rows}>
      {rows.map((r) => (
        <li key={`${r.meaning}:${r.label}`} className={`${s.row} ${s[r.tone]}`}>
          <span className={s.icon} aria-hidden>{r.icon}</span>
          <span>{r.label}<span className="visually-hidden"> — {r.meaning}</span></span>
        </li>
      ))}
    </ul>
  );
}

/**
 * `readOnly` is S-15: the same layout opened from history, with no rating
 * control and "Back to history" in place of the actions — the learner is
 * looking back, not finishing a case.
 */
export function FeedbackView({ sessionId, f, readOnly = false }: { sessionId: string; f: Feedback; readOnly?: boolean }) {
  const verdict = verdictView(f.verdict);
  const verdictClass = s[f.verdict && f.verdict in { correct: 1, partial: 1, anchored: 1 } ? f.verdict : "other"];
  const hit = f.coverage?.topics_hit ?? [];
  const missed = f.coverage?.topics_missed ?? [];
  const examSummary = scorecardSummary("Examination", f.examination_scorecard);
  const testSummary = scorecardSummary("Investigations", f.investigation_scorecard);

  const [revealed, setRevealed] = useState(false);
  const [rated, setRated] = useState<boolean | null>(null);
  const [rateFailed, setRateFailed] = useState(false);
  const [started, start, starting] = useActionState<ActionState>(startCase, {});

  async function sendRating(helpful: boolean) {
    const res = await rate(sessionId, helpful);
    if (res.ok) setRated(helpful); else setRateFailed(true);
  }

  return (
    <main className={s.main}>
      {/* 1 · Verdict */}
      <section aria-label="Verdict" className={`${s.verdict} ${verdictClass}`}>
        <p className={s.verdictLabel}><span aria-hidden>{verdict.icon} </span>{verdict.label}</p>
        {f.diagnosis_submitted && <span className={s.verdictAnswer}>Your answer: “{f.diagnosis_submitted}”</span>}
      </section>

      {/* 2 · Process summary */}
      <section aria-label="Summary" className={s.summary}>
        {summaryParts(f.summary ?? {}).map((part) => <span key={part}>{part}</span>)}
      </section>

      {/* 3 · Tutor — each line its own block, never numbered */}
      <section className={s.section} aria-labelledby="tutor">
        <h2 id="tutor" className={s.sectionTitle}>Your tutor</h2>
        {(f.tutor_feedback?.lines ?? []).map((line, i) => <p key={i} className={s.tutorLine}>{line}</p>)}
        {!readOnly && <div className={s.rating}>
          {rated === null ? (<>
            <span id="helpful">Was this helpful?</span>
            <Button size="sm" variant="secondary" aria-describedby="helpful" onClick={() => sendRating(true)}>Yes</Button>
            <Button size="sm" variant="secondary" aria-describedby="helpful" onClick={() => sendRating(false)}>No</Button>
          </>) : <span role="status">Thanks — that helps us improve the feedback.</span>}
        </div>}
        {rateFailed && rated === null && <Banner tone="error" onDismiss={() => setRateFailed(false)}>We couldn&apos;t save that. Please try again.</Banner>}
      </section>

      {/* 4 · History covered — the only progress bar in the product, and only now */}
      <section className={s.section} aria-labelledby="history">
        <h2 id="history" className={s.sectionTitle}>
          History covered <span className={s.sectionMeta}>{hit.length} of {hit.length + missed.length}</span>
        </h2>
        <ProgressBar value={Math.round(f.summary?.coverage_pct ?? 0)} label="History covered" />
        <ul className={s.topics}>
          {hit.map((t) => <li key={t} className={s.hit}>{topicLabel(t)}<span className="visually-hidden"> — covered</span></li>)}
          {missed.map((t) => <li key={t} className={s.missed}>{topicLabel(t)}<span className="visually-hidden"> — not covered</span></li>)}
        </ul>
      </section>

      {/* 5 / 6 · Scorecards — collapsed; investigations hidden when the case has no key tests */}
      <section className={s.section}>
        <Accordion items={[
          { id: "exam", title: examSummary ?? "Examination", body: <Rows rows={scorecardRows(f.examination_scorecard)} /> },
          ...(testSummary ? [{ id: "tests", title: testSummary, body: <Rows rows={scorecardRows(f.investigation_scorecard)} /> }] : []),
        ]} />
      </section>

      {/* 7 · Your approach — behavioural headings, amber or green, never red */}
      <section className={s.section} aria-labelledby="approach">
        <h2 id="approach" className={s.sectionTitle}>Your approach</h2>
        {(f.reasoning ?? []).map((r) => (
          <article key={r.id} className={`${s.approach} ${r.flagged ? s.flagged : s.clear}`}>
            <h3 className={s.approachHead}>
              <span className={s.approachIcon} aria-hidden>{r.flagged ? "↓" : "✓"}</span>
              {r.label}{r.flagged && r.status_line ? ` — ${r.status_line}` : ""}
            </h3>
            <p className={s.reason}>{r.reason}</p>
          </article>
        ))}
      </section>

      {/* 8 · The answer — last, and collapsed until asked for (FR-8.8) */}
      <section className={s.section} aria-labelledby="answer">
        <h2 id="answer" className={s.sectionTitle}>The answer</h2>
        {revealed ? (
          <div className={s.answer}>
            <p><strong>{f.answer?.correct_diagnosis ?? "Not recorded for this case."}</strong></p>
            {f.answer?.anchor_topic && <p>The case was built around a tempting alternative: {f.answer.anchor_topic}.</p>}
          </div>
        ) : (
          <Button variant="secondary" onClick={() => setRevealed(true)} aria-expanded={false}>Reveal diagnosis</Button>
        )}
      </section>

      {readOnly ? (
        <div className={s.actions}><Button variant="secondary" href="/history">Back to history</Button></div>
      ) : (<>
        {started.error && <Banner tone="error">{started.error}</Banner>}
        <form action={start} className={s.actions}>
          <Button type="submit" loading={starting} loadingLabel="Starting…">Start another case</Button>
          <Button variant="secondary" href="/dashboard">Back to dashboard</Button>
        </form>
      </>)}
    </main>
  );
}
