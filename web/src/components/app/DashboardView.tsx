"use client";

/**
 * S-08 · Dashboard, rendered from `buildDashboard`'s answer. Presentational
 * except for the two actions — start, and the confirmed abandon.
 */
import Link from "next/link";
import { startTransition, useActionState, useState } from "react";
import { abandonCase, startCase, type ActionState } from "@/app/(app)/actions";
import { Badge, Banner, Button, Card, ConfirmModal, StatTile } from "@/components/ui";
import type { Dashboard } from "@/lib/dashboard";
import s from "./app.module.css";

export function DashboardView({ d }: { d: Dashboard }) {
  const [started, start, starting] = useActionState<ActionState>(startCase, {});
  const [abandoned, abandon, abandoning] = useActionState<ActionState, FormData>(abandonCase, {});
  const [confirming, setConfirming] = useState(false);

  return (
    <>
      <h1 className={s.greeting}>{d.greeting}</h1>

      {d.active && (
        <Banner tone="info">
          <div className={s.bannerRow}>
            <span>You have a consultation in progress — {d.active.caseTitle}, started {d.active.startedAt}.</span>
            <span className={s.bannerActions}>
              <Button size="sm" href={`/case/${encodeURIComponent(d.active.id)}`}>Resume</Button>
              <Button size="sm" variant="secondary" onClick={() => setConfirming(true)}>Abandon</Button>
            </span>
          </div>
        </Banner>
      )}
      {abandoned.error && <Banner tone="error">{abandoned.error}</Banner>}
      {started.error && <Banner tone="error">{started.error}</Banner>}

      <Card variant="elevated" className={s.hero}>
        {d.hero === "limit" ? (
          <>
            <div>
              <h2 className={s.heroTitle}>You&apos;ve used your free cases this month</h2>
              <p className={s.heroBody}>
                {d.allowance?.resetsOn ? `Your next free case unlocks on ${d.allowance.resetsOn}.` : "Your next free case unlocks next month."}
              </p>
            </div>
            <div className={s.heroActions}>
              {/* Billing is T-041: the button is here so the state is complete, and says so. */}
              <Button disabled title="Arrives with billing">Go unlimited</Button>
              <Button variant="ghost" disabled>Start a case</Button>
            </div>
          </>
        ) : (
          <>
            <div>
              <h2 className={s.heroTitle}>{d.hero === "empty" ? "Your first case is waiting" : "Ready for a case?"}</h2>
              <p className={s.heroBody}>
                {d.hero === "empty"
                  ? "You'll interview a patient, decide what to investigate, and get feedback on your reasoning."
                  : "A new patient, about 20 minutes."}
              </p>
            </div>
            <form action={start} className={s.heroActions}>
              <Button type="submit" size="lg" loading={starting} loadingLabel="Starting…" disabled={Boolean(d.active)}>
                Start a case
              </Button>
            </form>
          </>
        )}
      </Card>

      {d.stats && (
        <div className={s.tiles}>
          <StatTile value={d.stats.completed} label={d.stats.completed === 1 ? "case completed" : "cases completed"} />
          {/* Stated factually, never with urgency (U1). */}
          <StatTile value={d.stats.streakDays} label="day streak" />
          <StatTile value={d.stats.coveragePct == null ? "—" : `${d.stats.coveragePct}%`}
                    label={d.stats.coveragePct == null ? "history covered — after 3 cases" : "history covered"} />
        </div>
      )}

      {d.recent.length > 0 && (
        <section>
          <div className={s.sectionHead}>
            <h2 className={s.sectionTitle}>Recent sessions</h2>
            <Link href="/history">View all →</Link>
          </div>
          <ul className={s.list}>
            {d.recent.map((r) => (
              <li key={r.id} className={s.row}>
                <Link href={`/case/${encodeURIComponent(r.id)}/feedback`} className={s.rowTitle}>{r.caseTitle}</Link>
                <span className={s.rowWhen}>{r.when}</span>
                {r.verdict ? <Badge tone={r.verdict.tone}>{r.verdict.icon} {r.verdict.label}</Badge>
                  : <Badge>{r.status === "abandoned" ? "Abandoned" : "No result"}</Badge>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {d.active && (
        <ConfirmModal open={confirming} title="Abandon this consultation?" confirmLabel="Abandon"
                      loading={abandoning} onClose={() => setConfirming(false)}
                      onConfirm={() => {
                        const fd = new FormData();
                        fd.set("session_id", d.active!.id);
                        setConfirming(false);
                        startTransition(() => abandon(fd));
                      }}>
          <p>It still counts as one of this month&apos;s cases, and you won&apos;t get feedback on it.</p>
        </ConfirmModal>
      )}
    </>
  );
}
