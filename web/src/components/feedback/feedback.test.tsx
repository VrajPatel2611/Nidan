/**
 * S-12 and S-13 (T-036), one block per BUILD_PLAN criterion.
 */
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { FeedbackView } from "./FeedbackView";
import { AssessmentPending, SLOW_AFTER_MS } from "./AssessmentPending";
import { rate } from "@/app/case/[id]/feedback/actions";
import type { Feedback } from "@/lib/api";
import { scorecardRows, scorecardSummary, summaryParts, topicLabel } from "@/lib/feedback";

vi.mock("@/app/case/[id]/feedback/actions", () => ({ rate: vi.fn(async () => ({ ok: true })) }));
vi.mock("@/app/(app)/actions", () => ({ startCase: vi.fn(async () => ({})) }));

const F: Feedback = {
  session_id: "s1",
  diagnosis_submitted: "Angina",
  verdict: "anchored",
  summary: { question_count: 8, examination_count: 3, investigation_count: 4, coverage_pct: 75, duration_seconds: 1140 },
  tutor_feedback: { lines: ["You went to the heart quickly.", "What made you rule out the stomach?"], generator: "llm" },
  coverage: { topics_hit: ["pain_character", "meal_relationship"], topics_missed: ["family_history"] },
  examination_scorecard: { key_done: ["Vital Signs"], key_missed: ["Abdominal Examination"], relevant_done: ["General Inspection"], extra_done: [] },
  investigation_scorecard: { key_done: ["ECG (12-lead)"], key_missed: ["OGD (Gastroscopy)"], reasonable_done: [], low_value_done: ["CT Coronary Angiogram"], extra_done: [] },
  reasoning: [
    { id: "diagnostic_focus", label: "Diagnostic focus", flagged: true, status_line: "consider broadening",
      reason: "6 of your 8 questions explored a cardiac cause. You asked 1 question about other possibilities." },
    { id: "history_completeness", label: "History completeness", flagged: false, status_line: null,
      reason: "You covered 6 of 8 key areas before concluding." },
    { id: "evidence_exploration", label: "Evidence exploration", flagged: true, status_line: "look for what doesn't fit",
      reason: "You explored 1 of 6 findings that pointed elsewhere." },
  ],
  answer: { correct_diagnosis: "GERD, NSAID-induced", anchor_topic: "cardiac / heart disease" },
};

// UX_SPEC §9's banned list, scanned over rendered text. No \b: textContent
// joins elements without spaces, and a boundary would miss "…agoanchored".
const BANNED = /(bias|anchor|premature closure|wrong|failed|poor|should have)/i;

const visibleText = (root: HTMLElement) => root.textContent ?? "";

describe("1 · eight sections, in the specified order", () => {
  it("verdict, summary, tutor, history, scorecards, approach, answer — then the actions", () => {
    const { container } = render(<FeedbackView sessionId="s1" f={F} />);
    const text = visibleText(container);
    const order = ["Worth reconsidering", "8 questions", "Your tutor", "History covered",
      "Examination — 1 of 2 key done.", "Investigations — 1 of 2 key done.", "Your approach", "The answer", "Start another case"];
    const positions = order.map((s) => text.indexOf(s));
    expect(positions.every((p) => p >= 0)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
  });
});

describe("2 · reasoning headings are behavioural", () => {
  it("shows exactly the three, flagged in amber with ↓, clear with ✓", () => {
    render(<FeedbackView sessionId="s1" f={F} />);
    const heads = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(heads).toEqual(["↓Diagnostic focus — consider broadening", "✓History completeness",
      "↓Evidence exploration — look for what doesn't fit"]);
  });
});

describe("3 · banned vocabulary absent from the rendered page", () => {
  it("even when the verdict is `anchored` and the answer names the trap", () => {
    const { container } = render(<FeedbackView sessionId="s1" f={F} />);
    fireEvent.click(screen.getByRole("button", { name: "Reveal diagnosis" }));
    expect(visibleText(container)).not.toMatch(BANNED);
  });

  it.each(["correct", "partial", "anchored", "other"] as const)("for verdict %s", (verdict) => {
    const { container } = render(<FeedbackView sessionId="s1" f={{ ...F, verdict }} />);
    expect(visibleText(container)).not.toMatch(BANNED);
  });

  it("the scan itself catches text joined across elements", () => {
    expect("2 days agoanchored").toMatch(BANNED);
  });
});

describe("4 · the answer stays collapsed until requested", () => {
  it("hides the diagnosis, then shows it on click", () => {
    render(<FeedbackView sessionId="s1" f={F} />);
    expect(screen.queryByText("GERD, NSAID-induced")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reveal diagnosis" }));
    expect(screen.getByText("GERD, NSAID-induced")).toBeInTheDocument();
  });
});

describe("5 · fallback feedback renders identically, with no apology", () => {
  it("differs only in the lines themselves", () => {
    const lines = ["Line one.", "Line two."];
    // React's useId differs between two renders; nothing else may.
    const html = (el: HTMLElement) => el.innerHTML.replace(/_r_[0-9a-z]+_/g, "ID");
    const model = render(<FeedbackView sessionId="s1" f={{ ...F, tutor_feedback: { lines, generator: "llm" } }} />);
    const modelHtml = html(model.container);
    model.unmount();
    const fallback = render(<FeedbackView sessionId="s1" f={{ ...F, tutor_feedback: { lines, generator: "rule_fallback" } }} />);
    expect(html(fallback.container)).toBe(modelHtml);
    expect(visibleText(fallback.container)).not.toMatch(/sorry|unavailable|fallback|couldn.t generate|automated/i);
  });
});

describe("6 · 'Was this helpful?' writes a rating", () => {
  it("sends the answer and thanks the learner", async () => {
    render(<FeedbackView sessionId="s1" f={F} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "No" })); });
    expect(rate).toHaveBeenCalledWith("s1", false);
    expect(screen.getByRole("status")).toHaveTextContent("Thanks");
  });
});

describe("S-13's other states", () => {
  it("hides the investigations scorecard when the case has no key tests (never '0 of 0')", () => {
    const { container } = render(<FeedbackView sessionId="s1"
      f={{ ...F, investigation_scorecard: { key_done: [], key_missed: [], reasonable_done: ["FBC"], low_value_done: [], extra_done: [] } }} />);
    expect(visibleText(container)).not.toMatch(/Investigations —|0 of 0/);
  });

  it("history: covered with a check, missed with a circle, names in sentence case, one progress bar", () => {
    render(<FeedbackView sessionId="s1" f={F} />);
    const section = screen.getByRole("heading", { name: /History covered/ }).closest("section")!;
    expect(within(section).getByText("2 of 3")).toBeInTheDocument();
    expect(within(section).getByText("Meal relationship")).toBeInTheDocument();
    expect(screen.getAllByRole("progressbar")).toHaveLength(1);
  });

  it("tutor lines are separate blocks and not numbered", () => {
    const { container } = render(<FeedbackView sessionId="s1" f={F} />);
    expect(container.querySelector("ol")).toBeNull();
    expect(screen.getByText("You went to the heart quickly.").tagName).toBe("P");
  });
});

describe("S-12 · assessment pending", () => {
  it("is never blank, and adds a line after 3 seconds", () => {
    vi.useFakeTimers();
    render(<AssessmentPending />);
    expect(screen.getByText("Reviewing your consultation…")).toBeInTheDocument();
    expect(screen.queryByText("Just putting your feedback together.")).not.toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(SLOW_AFTER_MS); });
    expect(screen.getByText("Just putting your feedback together.")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("on failure says the consultation is safe and offers to try again", () => {
    const retry = vi.fn();
    render(<AssessmentPending failed onRetry={retry} />);
    expect(screen.getByText(/We've saved your consultation/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalled();
  });
});

describe("helpers", () => {
  it("topic labels", () => expect(topicLabel("family_history")).toBe("Family history"));
  it("summary is singular where it is one", () =>
    expect(summaryParts({ question_count: 1, examination_count: 0, investigation_count: 1, coverage_pct: 49.6 }))
      .toEqual(["1 question", "0 examinations", "1 test", "50% history"]));
  it("scorecard rows follow S-13's table, and the only red is a key item missed", () => {
    const rows = scorecardRows(F.investigation_scorecard);
    expect(rows.map((r) => [r.icon, r.tone])).toEqual([["✓", "green"], ["○", "red"], ["⚠", "amber"]]);
  });
  it("no key items, no summary", () => expect(scorecardSummary("Investigations", { key_done: [], key_missed: [] })).toBeNull());
});
