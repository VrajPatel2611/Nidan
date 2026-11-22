/**
 * S-14, S-15 and S-16 as rendered (T-037), one block per BUILD_PLAN criterion.
 */
import { render, screen, within } from "@testing-library/react";
import { HistoryList } from "./HistoryList";
import { ProgressView } from "./ProgressView";
import { FeedbackView } from "@/components/feedback/FeedbackView";
import type { Feedback, Progress, SessionSummary } from "@/lib/api";

vi.mock("@/app/case/[id]/feedback/actions", () => ({ rate: vi.fn() }));
vi.mock("@/app/(app)/actions", () => ({ startCase: vi.fn(async () => ({})) }));

const NOW = new Date("2026-11-23T12:00:00Z");
const BANNED = /(bias|anchor|premature closure|wrong|failed|poor|should have)/i;

const rows: SessionSummary[] = [
  { session_id: "a", case_title: "Breathlessness, 29F", status: "active", verdict: null, coverage_pct: null, started_at: "2026-11-23T10:00:00Z" },
  { session_id: "b", case_title: "Chest pain, 48M", status: "completed", verdict: "anchored", coverage_pct: 62.5, started_at: "2026-11-22T10:00:00Z" },
  { session_id: "c", case_title: "Fatigue, 34F", status: "abandoned", verdict: null, coverage_pct: null, started_at: "2026-11-10T10:00:00Z" },
];

describe("criterion 1 — paginated history; detail reuses the feedback layout read-only", () => {
  it("lists case, date, verdict and coverage, newest first", () => {
    const { container } = render(<HistoryList rows={rows} now={NOW} timezone="UTC" olderHref={null} newestHref={null} />);
    const items = screen.getAllByRole("listitem");
    expect(items.map((li) => li.textContent?.split(/today|yesterday|\d+ Nov/)[0])).toEqual(
      ["Breathlessness, 29F", "Chest pain, 48M", "Fatigue, 34F"]);
    expect(within(items[1]!).getByText(/Worth reconsidering/)).toBeInTheDocument();
    expect(within(items[1]!).getByText("63%")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(BANNED);
  });

  it("opens completed sessions read-only, resumes active ones, links nothing for abandoned", () => {
    render(<HistoryList rows={rows} now={NOW} timezone="UTC" olderHref={null} newestHref={null} />);
    expect(screen.getByRole("link", { name: "Chest pain, 48M" })).toHaveAttribute("href", "/history/b");
    expect(screen.getByRole("link", { name: "Breathlessness, 29F" })).toHaveAttribute("href", "/case/a");
    expect(screen.queryByRole("link", { name: "Fatigue, 34F" })).not.toBeInTheDocument();
  });

  it("pages by cursor, with a way back to the newest", () => {
    render(<HistoryList rows={rows} now={NOW} timezone="UTC" olderHref="/history?cursor=abc" newestHref="/history" />);
    expect(screen.getByRole("link", { name: "Older sessions →" })).toHaveAttribute("href", "/history?cursor=abc");
    expect(screen.getByRole("link", { name: "← Newest" })).toHaveAttribute("href", "/history");
  });

  it("has S-14's empty state", () => {
    render(<HistoryList rows={[]} now={NOW} timezone="UTC" olderHref={null} newestHref={null} />);
    expect(screen.getByText("No sessions yet — your completed cases will appear here.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start a case" })).toHaveAttribute("href", "/dashboard");
  });

  it("S-15: the feedback layout without the rating or the start button", () => {
    const f: Feedback = { verdict: "correct", diagnosis_submitted: "GERD", summary: { question_count: 6 },
      tutor_feedback: { lines: ["Good."], generator: "llm" }, coverage: { topics_hit: [], topics_missed: [] },
      reasoning: [], answer: { correct_diagnosis: "GERD" } };
    render(<FeedbackView sessionId="b" f={f} readOnly />);
    expect(screen.getByText("Correct diagnosis")).toBeInTheDocument();
    expect(screen.queryByText("Was this helpful?")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start another case" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to history" })).toHaveAttribute("href", "/history");
  });
});

const base: Progress = {
  sessions_completed: 14, has_sufficient_data: true, mean_coverage_last10: 66,
  coverage_series: [40, 55, 62.5, 70, 75].map((c, i) => ({ session_index: i + 1, coverage_pct: c, at: null })),
  reasoning_trends: [
    { id: "diagnostic_focus", label: "Diagnostic focus", last10_rate: 0.2, prev10_rate: 0.75, direction: "improving" },
    { id: "history_completeness", label: "History completeness", last10_rate: 0.6, prev10_rate: 0.25, direction: "declining" },
    { id: "evidence_exploration", label: "Evidence exploration", last10_rate: 0.3, prev10_rate: 0.25, direction: "stable" },
  ],
  verdict_distribution: { correct: 6, partial: 4, anchored: 3, other: 1 },
};

describe("criterion 2 — progress needs three completed cases", () => {
  it.each([0, 1, 2])("shows the empty state with %i completed", (n) => {
    render(<ProgressView p={{ ...base, sessions_completed: n, has_sufficient_data: false }} />);
    expect(screen.getByText("Not enough data yet")).toBeInTheDocument();
    expect(screen.getByText(`${n} of 3 completed`)).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();          // no chart drawn from too little
  });

  it("draws the three sections at three or more", () => {
    render(<ProgressView p={base} />);
    expect(screen.getByRole("img", { name: /History coverage over your last 5 cases/ })).toBeInTheDocument();
    expect(screen.getByText("How often each pattern came up")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Correct diagnosis: 6, On the right track: 4, Worth reconsidering: 3, Not quite: 1/ })).toBeInTheDocument();
  });
});

describe("criterion 3 — decline shown neutrally, no alarm styling", () => {
  it("states a rise in the same shape as a fall", () => {
    render(<ProgressView p={base} />);
    const lines = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(lines).toContain("Diagnostic focus flagged in 2 of your last 10 cases, down from 3.");
    expect(lines).toContain("History completeness flagged in 6 of your last 10 cases, up from 1.");
  });

  it("styles every pattern line alike — nothing marks a decline", () => {
    render(<ProgressView p={base} />);
    const items = screen.getByText("How often each pattern came up").parentElement!.querySelectorAll("li");
    const styles = [...items].map((li) => li.className + "|" + li.getAttribute("style"));
    expect(new Set(styles).size).toBe(1);
    expect(document.body.textContent).not.toMatch(/worse|declin|warning|careful|!/i);
  });

  it("uses none of the banned words", () => {
    const { container } = render(<ProgressView p={base} />);
    expect(container.textContent).not.toMatch(BANNED);
  });
});
