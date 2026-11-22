import Link from "next/link";
import { Badge, Button, EmptyState } from "@/components/ui";
import type { SessionSummary } from "@/lib/api";
import { VERDICTS, relativeDay, type Verdict } from "@/lib/dashboard";
import s from "./app.module.css";

/**
 * S-14 · History. Reverse-chronological: case, relative date, verdict badge,
 * coverage %. A completed case opens its read-only feedback (S-15); an
 * active one resumes; an abandoned one has nothing to open.
 */
export function HistoryList({ rows, now, timezone, olderHref, newestHref }: {
  rows: SessionSummary[]; now: Date; timezone?: string | null; olderHref: string | null; newestHref: string | null;
}) {
  if (rows.length === 0 && !newestHref) {
    return (
      <EmptyState icon="◷" heading="No sessions yet — your completed cases will appear here."
                  action={<Button href="/dashboard">Start a case</Button>} />
    );
  }

  return (
    <>
      <ul className={s.list}>
        {rows.map((r) => {
          const id = encodeURIComponent(r.session_id ?? "");
          const verdict = r.verdict && r.verdict in VERDICTS ? VERDICTS[r.verdict as Verdict] : null;
          const href = r.status === "completed" ? `/history/${id}` : r.status === "active" ? `/case/${id}` : null;
          const title = r.case_title || "Case";
          return (
            <li key={r.session_id} className={s.historyRow}>
              {href ? <Link href={href} className={s.rowTitle}>{title}</Link> : <span className={s.rowTitle}>{title}</span>}
              <span className={s.rowWhen}>{r.started_at ? relativeDay(r.started_at, now, timezone) : ""}</span>
              {verdict ? <Badge tone={verdict.tone}>{verdict.icon} {verdict.label}</Badge>
                : <Badge>{r.status === "active" ? "In progress" : r.status === "abandoned" ? "Abandoned" : "No result"}</Badge>}
              <span className={s.rowCoverage}>
                {r.coverage_pct == null ? "—" : `${Math.round(r.coverage_pct)}%`}
                <span className="visually-hidden"> history covered</span>
              </span>
            </li>
          );
        })}
      </ul>
      {(olderHref || newestHref) && (
        <nav className={s.pager} aria-label="Pages">
          {newestHref ? <Link href={newestHref}>← Newest</Link> : <span />}
          {olderHref && <Link href={olderHref}>Older sessions →</Link>}
        </nav>
      )}
    </>
  );
}
