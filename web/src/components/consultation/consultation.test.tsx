/**
 * S-10 and S-11 as they render (T-034). Criteria 4–6 are the U2 guarantees,
 * and BUILD_PLAN asks a reviewer to check them explicitly — so each is a test.
 */
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { Consultation, type ConsultationProps } from "./Consultation";
import { ask, orderOne } from "@/app/case/actions";
import { groupMenu } from "@/lib/consultation";

vi.mock("@/app/case/actions", () => ({ ask: vi.fn(), orderOne: vi.fn(), diagnose: vi.fn() }));
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const props: ConsultationProps = {
  sessionId: "s1",
  patient: { name: "Ramesh Kumar", age: 48, sex: "male", presenting_complaint: "Chest pain" },
  turns: [{ id: "opening", who: "patient", text: "I've had this chest pain for three days now." }],
  ordered: [],
  examinations: groupMenu([
    { key: "vitals", label: "Vital signs", group: "General & vitals", display_order: 1 },
    { key: "cardiovascular", label: "Cardiovascular", group: "Cardiovascular", display_order: 2 },
  ]),
  investigations: groupMenu([
    { key: "ecg", label: "ECG (12-lead)", group: "Cardiology", display_order: 1 },
    { key: "troponin_0h", label: "High-sensitivity Troponin (0 h)", group: "Cardiology", display_order: 2 },
    { key: "fbc", label: "Full blood count", group: "Haematology", display_order: 3 },
  ]),
  resumedFrom: null,
  capReached: false,
};

const askMock = vi.mocked(ask);
const orderMock = vi.mocked(orderOne);
beforeEach(() => vi.clearAllMocks());

async function type(text: string) {
  fireEvent.change(screen.getByLabelText("Ask a question"), { target: { value: text } });
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Send" })); });
}

describe("criterion 4 — none present: counter, coverage, suggestions, timer", () => {
  it("shows none of them, before or after a question", async () => {
    askMock.mockResolvedValue({ ok: true, question: "Is it burning?", reply: "Burning, mostly." });
    const { container } = render(<Consultation {...props} />);
    await type("Is it burning?");
    // The consultation as a learner at ≥ 768 px sees it: §4.1's small-screen
    // note ("View my progress") is in the DOM but hidden at that width.
    const shown = container.cloneNode(true) as HTMLElement;
    shown.querySelector('[role="note"]')?.remove();
    const text = shown.textContent ?? "";
    // No \b at either end: textContent joins elements with no space, so a
    // counter beside the buttons reads "Send3/40Give diagnosis" and word
    // boundaries miss it on both sides. (?!\d) stops "3/400" matching instead.
    expect(text).not.toMatch(/\d+\s*(\/|of)\s*40(?!\d)/);              // "3/40", "3 of 40"
    expect(text).not.toMatch(/question(s)? (asked|left|remaining)/i);
    expect(text).not.toMatch(/coverage|progress|complete|%/i);
    expect(text).not.toMatch(/you (may|might) want|try asking|suggest/i);
    expect(text).not.toMatch(/\b\d{1,2}:\d{2}\b|time (left|elapsed)|timer/i);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();  // no top navigation
  });

  it("does not count what has been ordered, and marks no item as relevant", () => {
    render(<Consultation {...props} ordered={[
      { kind: "investigation", key: "ecg", label: "ECG (12-lead)", text: "Normal sinus rhythm.", at: "2026-11-22T10:00:00Z" }]} />);
    expect(screen.getByRole("tab", { name: "Ordered" })).toHaveTextContent(/^Ordered$/);
    for (const badge of ["key", "reasonable", "low value", "recommended", "relevant"]) {
      expect(screen.queryByText(new RegExp(`\\b${badge}\\b`, "i"))).not.toBeInTheDocument();
    }
  });
});

describe("criterion 5 — investigation search filters by name only", () => {
  it("keeps the fixed order and never matches a group or a key", () => {
    render(<Consultation {...props} />);
    fireEvent.click(screen.getByRole("tab", { name: "Investigations" }));
    const search = screen.getByLabelText("Search investigations");
    fireEvent.change(search, { target: { value: "t" } });
    const names = () => screen.getAllByRole("button", { pressed: false }).map((b) => b.textContent);
    expect(names()).toEqual(["High-sensitivity Troponin (0 h)", "Full blood count"]);
    fireEvent.change(search, { target: { value: "haematology" } });
    expect(screen.getByText("No investigation by that name.")).toBeInTheDocument();
    fireEvent.change(search, { target: { value: "fbc" } });
    expect(screen.getByText("No investigation by that name.")).toBeInTheDocument();
  });
});

describe("criterion 6 — the diagnosis modal holds no readiness hint", () => {
  it("says only that it cannot be undone", () => {
    render(<Consultation {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Give diagnosis" }));
    const dialog = screen.getByRole("dialog", { name: "Your diagnosis" });
    expect(within(dialog).getByText("What do you think is going on with Ramesh?")).toBeInTheDocument();
    expect(within(dialog).getByText("This ends the consultation and can't be undone.")).toBeInTheDocument();
    expect(dialog.textContent).not.toMatch(/\d|only asked|haven't (ordered|examined)|most students|are you sure|ready/i);
    expect(within(dialog).getByRole("button", { name: "Submit diagnosis" })).toBeDisabled();
    expect(within(dialog).getByLabelText("What do you think is going on with Ramesh?")).toHaveFocus();
  });
});

describe("criterion 3 — a failed reply keeps the question and offers retry", () => {
  it("leaves the typed text in the box and retries it", async () => {
    askMock.mockResolvedValueOnce({ ok: false, code: "patient_unavailable", status: 503 });
    render(<Consultation {...props} />);
    await type("Does it go to your arm?");
    expect(screen.getByText(/The patient couldn.t respond just now/)).toBeInTheDocument();
    expect(screen.getByLabelText("Ask a question")).toHaveValue("Does it go to your arm?");

    askMock.mockResolvedValueOnce({ ok: true, question: "Does it go to your arm?", reply: "No, it stays in my chest." });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Try again" })); });
    expect(askMock).toHaveBeenLastCalledWith("s1", "Does it go to your arm?");
    expect(screen.getByText("No, it stays in my chest.")).toBeInTheDocument();
    expect(screen.getByLabelText("Ask a question")).toHaveValue("");
  });
});

describe("criterion 2 — the other states", () => {
  it("cap reached: input disabled, S-10's note, still no number but the cap itself", async () => {
    askMock.mockResolvedValue({ ok: false, code: "question_limit_reached", status: 429 });
    render(<Consultation {...props} />);
    await type("One more?");
    expect(screen.getByLabelText("Ask a question")).toBeDisabled();
    expect(screen.getByText(/You've asked 40 questions — that's plenty/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Give diagnosis" })).toBeEnabled();
  });

  it("cap already met on load (a resumed session) starts disabled", () => {
    render(<Consultation {...props} capReached />);
    expect(screen.getByLabelText("Ask a question")).toBeDisabled();
  });

  it("blocked input: the guard's modal, and the question is discarded", async () => {
    askMock.mockResolvedValue({ ok: false, code: "patient_data_detected", status: 422 });
    render(<Consultation {...props} />);
    await type("My patient John Smith, DOB 01/02/1960, has chest pain");
    expect(screen.getByRole("dialog", { name: "Please don't enter real patient information" })).toBeInTheDocument();
    expect(screen.getByLabelText("Ask a question")).toHaveValue("");
  });

  it("rate limited: says so, and retries without being asked", async () => {
    vi.useFakeTimers();
    askMock.mockResolvedValueOnce({ ok: false, code: "rate_limited", status: 429, retryAfter: 5 })
           .mockResolvedValueOnce({ ok: true, question: "Any fever?", reply: "No fever." });
    render(<Consultation {...props} />);
    await type("Any fever?");
    expect(screen.getByText("The patient needs a moment…")).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(askMock).toHaveBeenCalledTimes(2);
    expect(screen.getByText("No fever.")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("resuming: says when from", () => {
    render(<Consultation {...props} resumedFrom="yesterday" />);
    expect(screen.getByText("Resumed from yesterday.")).toBeInTheDocument();
  });

  it("a concluded session goes to its feedback", async () => {
    askMock.mockResolvedValue({ ok: false, code: "session_concluded", status: 409 });
    render(<Consultation {...props} />);
    await type("Hello?");
    expect(push).toHaveBeenCalledWith("/case/s1/feedback");
  });
});

describe("criterion 7 — keyboard and screen readers", () => {
  it("the conversation is a polite live log", () => {
    render(<Consultation {...props} />);
    const log = screen.getByRole("log", { name: "Conversation" });
    expect(log).toHaveAttribute("aria-live", "polite");
  });

  it("Enter sends, Shift+Enter does not", async () => {
    askMock.mockResolvedValue({ ok: true, question: "Q", reply: "R" });
    render(<Consultation {...props} />);
    const box = screen.getByLabelText("Ask a question");
    fireEvent.change(box, { target: { value: "Line one" } });
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(askMock).not.toHaveBeenCalled();
    await act(async () => { fireEvent.keyDown(box, { key: "Enter" }); });
    expect(askMock).toHaveBeenCalledWith("s1", "Line one");
  });

  it("chips are real buttons grouped under a legend", () => {
    render(<Consultation {...props} />);
    const group = screen.getByRole("group", { name: "Cardiovascular" });
    expect(within(group).getByRole("button", { name: "Cardiovascular" })).toBeInTheDocument();
  });
});

describe("examining", () => {
  it("adds the finding to Ordered, switches there, and marks the chip done", async () => {
    orderMock.mockResolvedValue({ ok: true, key: "vitals", label: "Vital signs", text: "HR 76 bpm regular.", at: "2026-11-22T10:00:00Z" });
    render(<Consultation {...props} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Vital signs" })); });
    expect(screen.getByRole("tab", { name: "Ordered" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("HR 76 bpm regular.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Examinations" }));
    expect(screen.getByRole("button", { name: /Vital signs/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("a done chip re-views rather than ordering twice", async () => {
    render(<Consultation {...props} ordered={[
      { kind: "examination", key: "vitals", label: "Vital signs", text: "HR 76", at: "2026-11-22T10:00:00Z" }]} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /Vital signs/ })); });
    expect(orderMock).not.toHaveBeenCalled();
    expect(screen.getByRole("tab", { name: "Ordered" })).toHaveAttribute("aria-selected", "true");
  });
});
