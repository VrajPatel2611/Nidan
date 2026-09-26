# Phase 2 briefs — the admin console

Self-contained task briefs for the frontend/admin track (Owner **Y**), written
to be followed without this repository's author sitting next to you and without
Claude. Each one names what to build, which spec sections to read, which files
you own, which files you must not touch, and what "done" means.

**They live in the repository on purpose.** The first set was handed over as
files, and by the time T-020 was being built the copy in hand had been
superseded — which is how two people came to write the same migration twice.
A brief you `git pull` is a brief that cannot go stale in someone's downloads
folder.

| File | Read when |
|---|---|
| `FIX_T-020_FIRST.md` | now, if the T-020 pull request is still red |
| `00_START_HERE.md` | before touching anything — setup, git workflow, file ownership |
| `01_T-021_case_editor.md` | 5 d · the case editor |
| `02_T-022_playtest.md` | 4 d · playtest with live instrumentation |
| `03_T-023_clinical_review.md` | 2 d · clinical review — the gate for the whole project |

Strictly in that order; each task genuinely depends on the one before.

The authoritative task definitions are in `docs/spec/BUILD_PLAN.md` §6 and the
screens in `docs/spec/UX_SPEC.md` §12. These briefs point at those rather than
restating them, and where they disagree, **the spec wins**.
