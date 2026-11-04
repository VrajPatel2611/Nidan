/**
 * The component library (UX_SPEC §3.5, T-032 criterion 4).
 *
 * The inventory test reads the spec's table, so a component added to the spec
 * fails here until it is built. The rest test the behaviour the table names:
 * loading and disabled buttons, the focus trap, keyboard tabs, the 4-second
 * toast, the error state of a field.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import * as ui from "./index";
import { initials } from "./Simple";
import { TOAST_MS } from "./Toast";

describe("the inventory", () => {
  const spec = readFileSync(resolve(__dirname, "../../../../docs/spec/UX_SPEC.md"), "utf8");
  const table = spec.slice(spec.indexOf("## 3.5 Component inventory"), spec.indexOf("# 4. Responsive"));
  const names = [...table.matchAll(/^\|\s*`([A-Za-z]+)`\s*\|/gm)].map((m) => m[1]!);

  it("lists components", () => expect(names.length).toBeGreaterThanOrEqual(19));

  it.each(names)("%s is exported", (name) => {
    const exported = name === "Toast" ? ui.ToastProvider : (ui as Record<string, unknown>)[name];
    // A function component, or the object React.forwardRef returns.
    const isComponent = typeof exported === "function" ||
      (typeof exported === "object" && exported !== null && "$$typeof" in exported);
    expect(isComponent).toBe(true);
  });
});

describe("Button", () => {
  it("is disabled and busy while loading, and shows the loading label", () => {
    const onClick = vi.fn();
    render(<ui.Button loading loadingLabel="Creating account…" onClick={onClick}>Create account</ui.Button>);
    const button = screen.getByRole("button", { name: "Creating account…" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("defaults to type=button so it never submits a form by accident", () => {
    render(<ui.Button>Go</ui.Button>);
    expect(screen.getByRole("button")).toHaveAttribute("type", "button");
  });
});

describe("TextInput", () => {
  it("ties the error to the field for screen readers", () => {
    render(<ui.TextInput label="Email" error="Enter a valid email address" />);
    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("Enter a valid email address");
  });

  it("counts characters against maxLength", () => {
    render(<ui.TextInput label="Question" maxLength={10} counter />);
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "abc" } });
    expect(screen.getByText("3 / 10")).toBeInTheDocument();
  });
});

describe("Modal", () => {
  function Harness() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button onClick={() => setOpen(true)}>Open</button>
        <ui.Modal open={open} title="Your session expired" onClose={() => setOpen(false)}
                  actions={<><button>Sign out</button><button>Sign back in</button></>}>
          <input aria-label="Email" />
        </ui.Modal>
      </>
    );
  }

  it("moves focus in, traps Tab, closes on Escape and returns focus", () => {
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open" });
    opener.focus();
    fireEvent.click(opener);

    const dialog = screen.getByRole("dialog", { name: "Your session expired" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByLabelText("Email")).toHaveFocus();

    screen.getByRole("button", { name: "Sign back in" }).focus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(screen.getByLabelText("Email")).toHaveFocus();          // wrapped forwards
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(screen.getByRole("button", { name: "Sign back in" })).toHaveFocus();   // and back

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});

describe("Tabs", () => {
  it("moves with the arrow keys and keeps only the active tab in the Tab order", () => {
    render(<ui.Tabs tabs={[
      { id: "exam", label: "Examine", panel: "exam panel" },
      { id: "tests", label: "Tests", panel: "tests panel" },
      { id: "notes", label: "Notes", panel: "notes panel" },
    ]} />);
    const [exam, tests, notes] = screen.getAllByRole("tab");
    expect(exam).toHaveAttribute("tabindex", "0");
    expect(tests).toHaveAttribute("tabindex", "-1");

    fireEvent.keyDown(exam!, { key: "ArrowRight" });
    expect(tests).toHaveAttribute("aria-selected", "true");
    expect(tests).toHaveFocus();
    expect(screen.getByText("tests panel")).toBeVisible();

    fireEvent.keyDown(tests!, { key: "End" });
    expect(notes).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(notes!, { key: "ArrowRight" });            // wraps
    expect(exam).toHaveAttribute("aria-selected", "true");
  });
});

describe("Toast", () => {
  it("appears and is gone after 4 seconds", () => {
    vi.useFakeTimers();
    function Trigger() {
      const show = ui.useToast();
      return <button onClick={() => show("You've been signed out")}>go</button>;
    }
    render(<ui.ToastProvider><Trigger /></ui.ToastProvider>);
    fireEvent.click(screen.getByText("go"));
    expect(screen.getByRole("status")).toHaveTextContent("You've been signed out");
    act(() => { vi.advanceTimersByTime(TOAST_MS); });
    expect(screen.queryByText("You've been signed out")).not.toBeInTheDocument();
    vi.useRealTimers();
  });
});

describe("Tooltip", () => {
  it("shows on keyboard focus, not only on hover", () => {
    render(<ui.Tooltip text="Reference range 3.5–5.0"><button>K⁺</button></ui.Tooltip>);
    fireEvent.focus(screen.getByRole("button"));
    expect(screen.getByRole("tooltip")).toHaveTextContent("Reference range 3.5–5.0");
    fireEvent.keyDown(screen.getByRole("button"), { key: "Escape" });
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });
});

describe("the smaller ones", () => {
  it("Chip reports its selected state", () => {
    render(<ui.Chip selected>ECG</ui.Chip>);
    expect(screen.getByRole("button", { name: "ECG" })).toHaveAttribute("aria-pressed", "true");
  });

  it("Banner can be dismissed", () => {
    const onDismiss = vi.fn();
    render(<ui.Banner tone="warning" onDismiss={onDismiss}>Heads up</ui.Banner>);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalled();
    expect(screen.queryByText("Heads up")).not.toBeInTheDocument();
  });

  it("an error Banner is announced as an alert", () => {
    render(<ui.Banner tone="error">That email or password doesn&apos;t match.</ui.Banner>);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("Accordion opens and closes", () => {
    render(<ui.Accordion items={[{ id: "a", title: "Examinations", body: "the scorecard" }]} />);
    const trigger = screen.getByRole("button", { name: /Examinations/ });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("the scorecard")).toBeVisible();
  });

  it("ProgressBar clamps and reports its value", () => {
    render(<ui.ProgressBar value={120} label="History covered" />);
    const bar = screen.getByRole("progressbar", { name: "History covered" });
    expect(bar).toHaveAttribute("aria-valuenow", "120");
    expect(bar.firstElementChild).toHaveStyle({ width: "100%" });
  });

  it.each([["Asha Rao", "AR"], ["yogesh", "Y"], ["dr.priya.mehta@example.com", "DM"], ["  ", "?"]])(
    "Avatar initials of %j are %s", (name, expected) => expect(initials(name)).toBe(expected));
});
