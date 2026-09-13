# Build log — what this folder is

> **A note on the name.** The product was renamed from **VPSim** to **Nidan** on
> 11 September 2026 (`PRD` D-8). Logs T-001 to T-007 describe work done before
> that and still use the working title — including quoted error output and
> command transcripts.
>
> They are deliberately not rewritten. Editing them would make the record claim
> that Nidan was built before Nidan existed, and the value of a build log is
> that it says what actually happened.
>
> The same applies to **file paths**. These logs say `vpsim/domain/...`; the
> package was renamed to `nidan/` on the same day. `BUILD_PLAN.md` carries the
> current paths — it is the forward-looking contract. This folder is the record.

`docs/spec/` says **what we are going to build and why**. It is written before
the code and it is the contract.

`docs/build-log/` says **what we actually built, and what happened while we
built it**. It is written after the code, one document per BUILD_PLAN task.

The two are different on purpose. A specification that is quietly edited every
time reality disagrees with it stops being a contract and becomes a diary. So
the spec stays as written, and the build log records the places where the work
diverged from it — with the reason.

---

## Where things stand

[`STATUS.md`](STATUS.md) is the progress tracker: every task, its phase, owner,
estimate, dependency and whether it is done, with a link to its build log.

**It is generated, never hand-edited:**

```bash
python scripts/build_status.py
```

It reads `docs/spec/BUILD_PLAN.md` and cannot disagree with it. A status page
maintained by remembering to update it is a status page that is quietly wrong
within a fortnight — the same reasoning as the test that keeps `.env.example`
honest. **Regenerate it when you finish a task, and commit the result.**

---

## One document per task

Every task in `docs/spec/BUILD_PLAN.md` gets a file here when it is finished:

```
docs/build-log/T-001-package-restructure.md
docs/build-log/T-002-test-harness.md
docs/build-log/T-013-event-log.md
...
```

Naming: `T-<number>-<short-kebab-slug>.md`. The slug is for humans scanning the
folder; the number is what actually identifies the task.

UI/UX tasks get one too. A screen that was built differently from `UX_SPEC.md`
is exactly the kind of thing that is forgotten in three weeks and then argued
about.

---

## What every task document must contain

These sections are not optional. They exist because each one answers a question
somebody actually asks later.

| Section | The question it answers |
|---|---|
| **1 · Summary** | *What is this, in thirty seconds?* |
| **2 · The problem** | *Why did we spend a day on this?* |
| **3 · Definition of done** | *What were we allowed to call finished?* — copied verbatim from BUILD_PLAN, not paraphrased |
| **4 · What was built** | *What is the shape of the thing now?* |
| **5 · Step by step** | *If I had to do this again, or check it, what were the moves?* — with the actual commands |
| **6 · Where we diverged from the spec** | *Why does the code not match the document?* |
| **7 · Problems hit** | *Someone will hit this again. What was it and what fixed it?* |
| **8 · Verification** | *How do we know it works?* — see `TEST_STRATEGY.md` |
| **9 · What this changes for you** | *I pulled this branch and now my old command fails. What do I run?* |
| **10 · Known debt left behind** | *What did we knowingly leave broken, and which task fixes it?* |
| **11 · How to undo it** | *This made things worse. How do I get back?* |

Section 7 is the one people skip and the one that pays for itself. Two hours
lost to an error message is worth four lines of writing so that nobody loses
two hours to it again.

Section 10 is the honest one. Leaving something unfinished is normal; leaving it
unfinished and undocumented is how a prototype becomes unmaintainable.

---

## How to write it

Write for the person who was not in the room. Assume they know Python, do not
know this codebase, and are reading because something broke.

- Show the **actual command that was run**, not a description of it.
- Show the **actual error text**, not "there was an import problem".
- When a decision was made, say what the alternative was and why it lost.
- Use British spelling in prose, to match the rest of the docs.
- If the task changed a decision recorded in an ADR, **do not edit the ADR** —
  write a new one that supersedes it, and link it here.

---

## Related documents

| Document | Use it for |
|---|---|
| `docs/spec/BUILD_PLAN.md` | the task list and acceptance criteria |
| `docs/spec/TEST_STRATEGY.md` | what kinds of test we run and what each one can and cannot catch |
| `docs/spec/adr/` | why a decision was made — check before re-arguing one |
| `CLAUDE.md` | the short version of all of the above |

---

## Phase summaries

`PHASE-1.md` covers T-010 … T-018 as a whole: what the phase delivered, the
defects it found, what it taught, and the state entering the next one. Written
the day the phase closed, which is the only reason it is worth having — a
retrospective assembled later is reconstructed rather than observed.

There is no Phase 0 summary, for that reason.
