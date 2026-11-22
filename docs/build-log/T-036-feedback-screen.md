# T-036 · Feedback screen

| | |
|---|---|
| **Task** | T-036, BUILD_PLAN Phase 3 |
| **Status** | 🟡 Built — **not yet seen after a live consultation** (§6) |
| **Branch** | `feat/t-036-feedback` |
| **Estimated** | 3 days |
| **Specification** | `UX_SPEC` S-12, S-13 · `API_CONTRACT` §6 · `PRD` FR-8.8 · UX-3 |
| **Behaviour change** | `/case/{id}/feedback` is S-13, with S-12 while feedback is being written; S-12 also shows full-screen while a diagnosis is submitted. A learner can now finish a case and read how they reasoned. |

---

## 1 · Summary

```
web/src/app/case/[id]/feedback/page.tsx        S-13, or S-12 while `feedback_not_ready`
web/src/app/case/[id]/feedback/actions.ts      the UX-3 rating
web/src/components/feedback/FeedbackView.tsx   the eight sections
web/src/components/feedback/AssessmentPending.tsx   S-12, never blank
web/src/components/feedback/FeedbackPending.tsx     polls at the API's retry_after_ms, then gives up
web/src/lib/feedback.ts                        topic labels, summary, scorecard rows
web/src/components/consultation/DiagnosisModal.tsx  shows S-12 while submitting
web/src/components/ui/ui.module.css            a Button with href no longer underlines
openapi.yaml · web/src/api/schema.ts           Feedback and the rating body reconciled (§4.1)
tests/test_openapi.py                          two tests pointed at the real field names
```

**197 web tests** (20 new); 988 backend tests.

---

## 2 · Definition of done

| # | Criterion | Met by | Verified |
|---|---|---|---|
| 1 | Eight sections in the specified order | `FeedbackView` | rendered text positions checked in order; seen in a browser |
| 2 | Headings: Diagnostic focus / History completeness / Evidence exploration | the API's `reasoning[].label`, rendered | exact heading list tested; flagged amber ↓, clear green ✓, never red |
| 3 | Banned vocabulary absent — automated copy test over rendered output | — | scan over the whole page, all four verdicts, answer revealed; **broken on purpose** (printing the raw verdict fails 2 tests) |
| 4 | Answer collapsed until requested | "Reveal diagnosis" | tested |
| 5 | Fallback renders identically, with no apology | the view never reads `generator` | HTML compared between `llm` and `rule_fallback`; **broken on purpose** (a "(fallback)" badge fails it) |
| 6 | "Was this helpful?" writes a rating | `rate()` → `POST …/feedback/rating {was_helpful}` | tested |

---

## 3 · Decisions

### 3.1 S-12 is shown where the wait actually is

`POST …/diagnosis` assesses, writes the tutor's prose (or the rule-based
fallback) and only then returns `feedback_ready: true`. So the slow part is the
diagnosis request, and S-12 covers the screen while it runs. The feedback route
shows S-12 too if the API answers `feedback_not_ready` — polling at its
`retry_after_ms` and, after eight tries, falling to S-12's "Failed" copy with
Try again rather than spinning for ever.

### 3.2 The page never sees a detector

Section 7 renders `reasoning[]` as the API sends it: `reasoning.py` has
already replaced the detector names and their `reason` strings (which contain
the banned words) with behavioural labels and counter-built sentences
(CT-4/CT-5). There is nothing here that could leak `bias_detail`.

### 3.3 The answer, without a trap explanation

§6's `answer.trap_explanation` does not exist (API-8). The answer section shows
the correct diagnosis and "The case was built around a tempting alternative:
{anchor_topic}." — written to avoid the vocabulary the anchor field is named
for.

### 3.4 Not here

- **The trial user's sticky footer** ("Save this result — create a free
  account"): a trial cannot reach this page through `/v1` (V-10).
- **"We'll email you when it's ready"** is S-12's copy; nothing sends that email
  (API-10's export has the same gap). The copy is the spec's; the mail is not
  built.

---

## 4 · Found along the way

### 4.1 `openapi.yaml`'s `Feedback` schema had drifted from everything

It described `diagnosis_verdict`, a top-level `correct_diagnosis`, `narrative`
and `generator: model|fallback`, and had no summary, coverage or scorecards.
`API_CONTRACT` §6 and `conclusion.py` agreed with each other on `verdict`,
`summary`, `tutor_feedback.lines`, `coverage`, both scorecards, `reasoning`
`{id, label, flagged, status_line, reason}` and `answer` — and the database
allows `llm|rule_fallback`. The rating body said `helpful`; the handler reads
`was_helpful`. Reconciled to §6 and the code, types regenerated.
`test_openapi.py` had pinned two of the stale names (`heading`, `evidence`);
they keep their purpose and now check `label` and `reason`.

**Third contract drift in three tasks** (T-034's diagnosis field, these two).
Each was invisible until a client was built from the types, because nothing
compares a request or response body to its schema. Raised with Vraj (V-11).

### 4.2 A link-button underlined

`Button` with `href` renders an `<a>`, which inherited the page's link
underline. Fixed in the button style.

---

## 5 · How to undo

1. `git revert` the T-036 commit
2. No migration

---

## 6 · Before this is called done

A real consultation through to this page — which needs a published case.
Worth checking then: a slow model (S-12's second line appears), and the
rule-based fallback looking exactly like model feedback.

---

## 7 · Verification

```bash
cd web && npm run check:api && npm run typecheck && npm run lint && npm test && npm run build
#   197 passed · 0 vulnerabilities · /case/[id]/feedback built
pytest -q                          # 988 passed
```
