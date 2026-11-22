/**
 * S-07 and S-08 as they render (T-033). The actions are mocked — these test
 * what the learner sees and can press, not the API.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { AppHeader } from "@/components/app/AppHeader";
import { DashboardView } from "@/components/app/DashboardView";
import { Onboarding } from "@/components/onboarding/Onboarding";
import { buildDashboard, type DashboardInput } from "@/lib/dashboard";

vi.mock("@/app/(app)/actions", () => ({
  finishOnboarding: vi.fn(async () => ({})),
  startCase: vi.fn(async () => ({})),
  abandonCase: vi.fn(async () => ({})),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const NOW = new Date("2026-11-15T13:30:00Z");
const base: DashboardInput = { displayName: "Aarav", timezone: "UTC", tier: "free", remaining: 3,
  resetsAt: "2026-12-01T00:00:00Z", sessions: [], progress: null, now: NOW };
const completed = { session_id: "s1", case_title: "Chest pain, 48M", started_at: "2026-11-14T10:00:00Z",
  status: "completed", verdict: "anchored" };

// The words PRD P1 / UX_SPEC §9 keep off every learner-facing screen.
// No \b: textContent joins elements without spaces ("2 days agoanchored"),
// so word boundaries would let a banned word through beside another element.
const BANNED = /(bias|anchor|premature closure|wrong|failed|poor|should have)/i;

describe("S-07 · onboarding", () => {
  it("asks the year only of roles that have one", () => {
    render(<Onboarding />);
    fireEvent.click(screen.getByLabelText("Medical student"));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("What year are you in?")).toBeInTheDocument();
    expect(screen.getByText("Step 2 of 2")).toBeInTheDocument();
  });

  it.each(["Physician", "Other"])("goes straight to the end for %s", (label) => {
    render(<Onboarding />);
    fireEvent.click(screen.getByLabelText(label));
    expect(screen.queryByRole("button", { name: "Next" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start my first case" })).toBeEnabled();
  });

  it("can be skipped from either step, and the skip says what it skips", () => {
    render(<Onboarding />);
    expect(screen.getByRole("button", { name: "Skip" })).toHaveAttribute("value", "skip-all");
    fireEvent.click(screen.getByLabelText("Resident / Registrar"));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("button", { name: "Skip" })).toHaveAttribute("value", "skip-year");
  });

  it("uses the spec's copy", () => {
    render(<Onboarding />);
    expect(screen.getByRole("heading", { name: "Welcome to Nidan" })).toBeInTheDocument();
    expect(screen.getByText("Two quick questions so we can pitch cases at the right level.")).toBeInTheDocument();
  });
});

describe("S-08 · dashboard", () => {
  it("empty: the first-case hero, and no stat tiles", () => {
    render(<DashboardView d={buildDashboard(base)} />);
    expect(screen.getByText("Your first case is waiting")).toBeInTheDocument();
    expect(screen.queryByText("day streak")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start a case" })).toBeEnabled();
  });

  it("normal: tiles and the recent list, with the verdict worded per S-13", () => {
    const { container } = render(<DashboardView d={buildDashboard({ ...base, sessions: [completed],
      progress: { sessions_completed: 4, mean_coverage_last10: 71.4 } })} />);
    expect(screen.getByText("Ready for a case?")).toBeInTheDocument();
    expect(screen.getByText("71%")).toBeInTheDocument();
    expect(screen.getByText(/Worth reconsidering/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(BANNED);
  });

  it("limit reached: start disabled, and when the next case unlocks", () => {
    render(<DashboardView d={buildDashboard({ ...base, remaining: 0, sessions: [completed] })} />);
    expect(screen.getByText("You've used your free cases this month")).toBeInTheDocument();
    expect(screen.getByText("Your next free case unlocks on 1 December.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start a case" })).toBeDisabled();
  });

  it("unfinished session: the banner, and abandon asks first", () => {
    render(<DashboardView d={buildDashboard({ ...base, sessions: [
      { session_id: "live", case_title: "Breathlessness, 29F", started_at: "2026-11-15T12:00:00Z", status: "active" },
    ] })} />);
    expect(screen.getByText(/You have a consultation in progress — Breathlessness, 29F, started today/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start a case" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Abandon" }));
    const dialog = screen.getByRole("dialog", { name: "Abandon this consultation?" });
    expect(within(dialog).getByText(/still counts as one of this month/)).toBeInTheDocument();
  });
});

describe("the allowance (U2)", () => {
  it("is in the header for the free tier", () => {
    render(<AppHeader active="dashboard" name="Aarav" allowance={{ remaining: 1 }} />);
    expect(screen.getByText("1 case left this month")).toBeInTheDocument();
  });

  it("is absent when not given — which is how the consultation screen must use it", () => {
    const { container } = render(<AppHeader active="dashboard" name="Aarav" />);
    expect(container.textContent).not.toMatch(/left this month/);
  });
});
