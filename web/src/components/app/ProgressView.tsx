/**
 * S-16 · Progress (T-037). Three things, once there are at least three
 * completed cases: the coverage trend, how often each pattern was flagged
 * against the ten before, and the spread of outcomes.
 *
 * **Decline looks exactly like improvement** — same type, same colour, same
 * sentence shape (S-16, U1). Nothing in the pattern list is coloured by
 * direction, so a learner whose numbers rose is told so, not warned.
 */
import { Button, Card, EmptyState } from "@/components/ui";
import type { Progress } from "@/lib/api";
import { VERDICTS } from "@/lib/dashboard";
import { MIN_SESSIONS, coverageChart, patternSentence, untilTrends, verdictSegments } from "@/lib/progress";
import s from "./progress.module.css";

const W = 560, H = 180;

export function ProgressView({ p }: { p: Progress }) {
  const completed = p.sessions_completed ?? 0;

  if (!p.has_sufficient_data || completed < MIN_SESSIONS) {
    return (
      <EmptyState icon="↗" heading="Not enough data yet"
                  body={<>Complete 3 cases and we&apos;ll start showing how your reasoning is changing.<br /><em>{untilTrends(completed)}</em></>}
                  action={<Button href="/dashboard">Start a case</Button>} />
    );
  }

  const chart = coverageChart(p.coverage_series ?? [], W, H);
  const segments = verdictSegments(p.verdict_distribution);
  const path = chart.points.map((pt, i) => `${i ? "L" : "M"}${pt.x.toFixed(1)},${pt.y.toFixed(1)}`).join(" ");

  return (
    <>
      <Card className={s.block}>
        <h2 className={s.title}>History coverage</h2>
        <p className={s.sub}>Your last {chart.points.length} {chart.points.length === 1 ? "case" : "cases"}
          {chart.mean != null && <> · average {chart.mean}%</>}</p>
        <svg viewBox={`0 0 ${W} ${H}`} className={s.chart} role="img"
             aria-label={`History coverage over your last ${chart.points.length} cases: ${chart.points.map((pt) => `${pt.pct}%`).join(", ")}. Average ${chart.mean}%.`}>
          {[0, 50, 100].map((g) => {
            const y = 8 + (1 - g / 100) * (H - 16);
            // Under its line, except 0% which sits above — above 100% would be clipped.
            return <g key={g}><line x1={0} x2={W} y1={y} y2={y} className={s.grid} /><text x={4} y={g === 0 ? y - 4 : y + 13} className={s.axis}>{g}%</text></g>;
          })}
          {chart.meanY != null && <line x1={0} x2={W} y1={chart.meanY} y2={chart.meanY} className={s.mean} />}
          <path d={path} className={s.line} />
          {chart.points.map((pt, i) => <circle key={i} cx={pt.x} cy={pt.y} r={3.5} className={s.dot} />)}
        </svg>
      </Card>

      <Card className={s.block}>
        <h2 className={s.title}>How often each pattern came up</h2>
        <ul className={s.patterns}>
          {(p.reasoning_trends ?? []).map((t) => <li key={t.id}>{patternSentence(t, completed)}</li>)}
        </ul>
      </Card>

      <Card className={s.block}>
        <h2 className={s.title}>Diagnostic outcomes</h2>
        <div className={s.bar} role="img"
             aria-label={segments.map((seg) => `${VERDICTS[seg.verdict].label}: ${seg.count}`).join(", ")}>
          {segments.map((seg) => (
            <span key={seg.verdict} className={`${s.segment} ${s[seg.verdict]}`} style={{ flexGrow: seg.share }} />
          ))}
        </div>
        <ul className={s.legend}>
          {segments.map((seg) => (
            <li key={seg.verdict}><span className={`${s.swatch} ${s[seg.verdict]}`} aria-hidden />{VERDICTS[seg.verdict].label} · {seg.count}</li>
          ))}
        </ul>
      </Card>
    </>
  );
}
