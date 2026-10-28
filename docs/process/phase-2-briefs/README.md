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
| `00_START_HERE.md` | before touching anything — setup, git workflow, file ownership |
| `03_T-023_clinical_review.md` | 2 d · clinical review — the gate for the whole project |

**Already done, briefs retired:** T-020 (admin shell, merged 2026-09-30, PR #19),
T-021 (case editor, merged 2026-10-28, PR #22) and T-022 (playtest, merged
2026-10-28, PR #24). Their briefs were removed
rather than left lying about — a finished brief is just one more document that
can be picked up by mistake. What was built is recorded in
`docs/build-log/T-020-admin-shell.md` and the T-021 build log.

The authoritative task definitions are in `docs/spec/BUILD_PLAN.md` §6 and the
screens in `docs/spec/UX_SPEC.md` §12. These briefs point at those rather than
restating them, and where they disagree, **the spec wins**.
