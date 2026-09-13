# Nidan — Product Requirements Document

---

# 1. Document control

| Field | Value |
|---|---|
| **Document** | Nidan Product Requirements Document |
| **Version** | v1.0 |
| **Status** | Draft — awaiting sign-off on §9 pricing and §3.1 persona |
| **Owners** | Vraj Patel, Yogesh Bagotia |
| **Last updated** | 2026-08-22 |
| **Supersedes** | — |
| **Related** | `UX_SPEC.md` · `DATA_MODEL.md` · `API_CONTRACT.md` · `TECH_SPEC.md` · `BUILD_PLAN.md` |

## 1.1 Purpose of this document

This PRD defines **what** Nidan v1 is and **why**. It does not describe implementation — that lives in `TECH_SPEC.md`.

It exists to serve as a **build contract**. Every functional requirement in §6 carries acceptance criteria and edge cases, so that implementation is mechanical and disagreements surface here rather than mid-build.

## 1.2 How to read it

| If you are… | Read |
|---|---|
| Deciding scope | §2, §5, §9 |
| Building a feature | §6 (your feature), §7, §8 |
| Designing screens | §7, §8 — then `UX_SPEC.md` |
| Writing the schema | §6, §9 — then `DATA_MODEL.md` |
| Judging whether v1 succeeded | §10 |

## 1.3 Decisions requiring sign-off

Marked **⟨DECIDE⟩** throughout. Collected in §11.

---

# 2. Problem

## 2.1 The user's problem

A medical student can name the causes of chest pain. Under time pressure with an actual patient, that knowledge does not automatically become a safe diagnostic process.

The gap is not knowledge. It is **process**: which questions to ask, when to stop asking, and whether to seriously consider the possibility that your first idea is wrong.

Existing study tools reinforce the knowledge half and leave the process half untrained:

- **Question banks** present a stem and five options. The differential is handed to you. You never practise generating one, and you never practise deciding you have gathered enough.
- **Clinical placements** provide real process practice, but feedback is scarce, inconsistent, and depends entirely on which registrar you happen to be working under.
- **Existing virtual patients** simulate the encounter, then grade the answer. A student who guesses correctly with no workup is marked correct.

The result is a specific, common failure: learners who score well on written exams and reason unsafely in practice — and who receive no signal that this is happening.

## 2.2 Why this is worth solving

Cognitive bias in diagnosis is a documented cause of preventable harm, and the three most implicated patterns — anchoring, premature closure, confirmation bias — are process failures, not knowledge failures. They are trainable, but only if they can be *observed*.

Our pilot demonstrated the observation is possible: **five of eight participants reached the correct diagnosis on their first case while seven of eight were simultaneously flagged for premature closure.** Conventional assessment would have congratulated most of them.

## 2.3 Why now

| Factor | Relevance |
|---|---|
| LLMs make realistic conversational patients cheap | A free-text patient interview cost a scripted-content team months to build in 2020. It now costs cents per session. |
| Medical students already pay for digital study tools | The willingness-to-pay behaviour is established; we are not creating a new spending category. |
| Our detection method is validated | 94 % accuracy, 100 % sensitivity across 54 decisions — the instrument works before the product ships. |

## 2.4 Competitive landscape

| Product | What it does | What it does not do |
|---|---|---|
| **UWorld, Amboss** | Large MCQ banks with strong explanations | Differential is given; no process practice; no reasoning feedback |
| **Body Interact, i-Human** | Virtual patient encounters, often institution-licensed | Grades outcome and checklist completion, not reasoning pattern |
| **Human Dx** | Crowdsourced diagnostic cases | Community answers, no individual process measurement |
| **Osmosis, Lecturio** | Video-led content | Passive; not an interactive encounter |
| **ChatGPT used ad hoc** | Free, flexible roleplay | No structure, no measurement, no record, will reveal the answer if asked |

**The gap we occupy:** nobody scores *how* the learner reasoned. Every competitor scores what they concluded.

**The honest competitive risk:** a learner can approximate the experience by prompting ChatGPT to roleplay a patient. What they cannot get is a consistent trap-based case design, a measurement of their questioning pattern, or a record of whether that pattern is improving. **Our defensibility is the measurement, not the roleplay.** That must remain visible in the product, or we are a worse ChatGPT wrapper.

---

# 3. Users

## 3.1 Primary persona — ✅ DECIDED (9 September 2026)

> **DECIDED: clinical-phase medical students and early trainees (years 3–5, plus
> interns and first-year residents).**
>
> Rationale: this is who we validated with — pilot participants were years 2–5 —
> so the research and the product stay aligned. Choosing a persona the pilot
> never tested would have weakened the link between the paper and the product.
> It is also the group whose reasoning habits are still forming, and the group
> already paying for study tools.
>
> **Consequence for authoring:** cases 6–10 are pitched at clinical-phase
> reasoning — undifferentiated acute presentations where the obvious answer is
> wrong, not rare-disease recall.

### Persona A — "Aarav", 4th-year medical student

| | |
|---|---|
| **Context** | Mid-clinical rotations, preparing for OSCEs and final exams |
| **Current tools** | A question bank subscription, lecture notes, ward experience |
| **Frustration** | Performs well on MCQs, freezes on undifferentiated presentations. Nobody tells him *why* his approach was weak, only that his answer was wrong |
| **Motivation** | Exam performance first; competence a close second |
| **Constraint** | Studies in 20–40 minute blocks between commitments |
| **Willingness to pay** | Already pays for question banks; price-sensitive but not price-blind |

### Persona B — "Dr. Meera", first-year resident

| | |
|---|---|
| **Context** | Newly responsible for real decisions |
| **Frustration** | Aware she rushes under load; no safe environment to test it |
| **Motivation** | Not being the doctor who missed something |
| **Constraint** | Very time-poor; 15 minutes, irregularly |
| **Willingness to pay** | Higher than a student; expects polish |

## 3.2 Jobs to be done

| # | Job |
|---|---|
| JTBD-1 | *When I face an undifferentiated presentation, I want to practise working it up without the answer options in front of me, so that exams and real patients feel like the same skill.* |
| JTBD-2 | *When I finish a case, I want to know whether my **process** was safe — not just whether I got lucky — so I can build habits that transfer.* |
| JTBD-3 | *When I have 20 minutes, I want a complete, self-contained practice encounter, so it fits my study pattern.* |
| JTBD-4 | *When I have practised for a month, I want evidence that my reasoning is improving, so I keep going.* |

JTBD-4 is the retention mechanic. A product that measures process but never shows a trend gives the user no reason to return.

## 3.3 Anti-personas

Explicitly **not** our users in v1. Naming them prevents scope drift.

| Not for | Why |
|---|---|
| Pre-clinical / pre-med students | No clinical knowledge base; the traps require differential knowledge to be meaningful |
| Experienced consultants | Cases are calibrated to trainee level; would find them trivial |
| Nurses, paramedics, allied health | Different reasoning frameworks and scope of practice. Possible later, not v1 |
| Patients or the general public | Actively harmful — this is not a symptom checker |
| Institutions buying cohort licences | Deliberately deferred (`ADR-0015`); schema keeps the door open |

## 3.4 Access and equity note

Our users are global and their ability to pay varies enormously — a resident in India and one in the US differ by an order of magnitude. Regional pricing is addressed in §9.4. A product priced only for high-income markets excludes most of the world's medical trainees, which is both a commercial and an ethical loss.

---

# 4. Product principles

Non-negotiable rules. When a future decision is contested, these settle it.

### P1 — Never label the learner

The product never says "you have anchoring bias." It asks *"most of your questions explored one explanation — what would you have expected to find if that were wrong?"*

*Why:* labelling produces defensiveness and identity threat; reflective questions produce reflection. This is the pedagogical basis of the whole design.

### P2 — Measurement integrity outranks engagement

We will not add a feature that improves engagement metrics at the cost of measurement validity.

*Concretely:* no live coverage meter during a consultation, no "you might want to ask about X" hints, no confirmation prompt before submitting a diagnosis. Each would improve the numbers by teaching the metric rather than the skill.

*Why:* the measurement is the product. A gamed measurement is worthless.

### P3 — Every judgement is traceable

Any flag shown to a user must cite the user's own actions. No unexplained scores.

*Why:* an unexplained flag teaches nothing and cannot be trusted or contested.

### P4 — Educational simulation, never clinical guidance

All patients are synthetic. The product never advises on a real case, and actively blocks attempts to enter real patient data.

*Why:* it is what keeps us outside medical-device regulation, and it is the honest description of what we do.

### P5 — The learner's data is theirs

Performance data is sensitive. No public leaderboards, no sharing by default, no third party sees an individual's transcripts.

---

# 5. Scope

## 5.1 In scope for v1

| Area | Included |
|---|---|
| Accounts | Signup, login, Google + Apple OAuth, password reset, delete, export |
| Trial | One complete case before signup is required |
| Consultation | Free-text history, 27 examinations, 86 investigations, diagnosis submission |
| Assessment | Diagnosis verdict, three bias detectors, coverage, scorecards |
| Feedback | LLM Socratic feedback with rule-based fallback |
| Progress | Session history, streak, per-bias trend |
| Content | 8–10 published cases ⟨DECIDE §5.4⟩ |
| Monetization | Free tier with monthly limit, Pro subscription via Stripe |
| Admin | Case editor, Playtest, clinical review queue, AI cost dashboard |
| Platform | Responsive web (desktop + tablet) |
| Legal | Privacy policy, terms, disclaimers, consent |

## 5.2 Explicitly out of scope for v1

Recording these prevents mid-build argument.

| Excluded | Reason |
|---|---|
| Native mobile apps | Web validates the product faster; no review cycle. `ADR-0006` |
| Case Factory | 8–10 hand-authored cases suffice to launch. Automation is post-launch |
| Embedding-based matching | Keywords work today; upgrade needs a calibration corpus |
| Educator / cohort features | `ADR-0015` — B2C first |
| Leaderboards, social, sharing | Violates P5; also distorts P2 |
| Spaced repetition scheduling | Needs usage data we do not have |
| Offline mode | Consultations require the LLM |
| Multi-language | English only at launch |
| Real-time intervention during a consultation | Violates P2; research direction, not v1 |
| Phone-sized consultation UI | Three-pane clinical interface degrades below ~768 px. Feedback and dashboard remain phone-usable |

## 5.3 Deferred to v1.x

Mobile apps · Case Factory · embeddings + threshold calibration · case variants · additional specialties · post-session confidence rating.

## 5.4 Launch content — ✅ DECIDED (9 September 2026)

> **Recommendation: 10 cases at launch, all in general internal medicine / acute presentations.**
>
> Rationale: a free user completing 3/month needs ~3 months before exhausting the bank; a Pro user needs enough to feel unlimited. Depth in one domain beats breadth across five — it makes the product legible ("the acute-presentation trainer") and keeps the master menu coherent.
>
> **DECIDED: 10.** You have 5, so **five more must be authored and clinically
> reviewed before launch.**
>
> This is the critical path (`BUILD_PLAN` §11.1) and it is content work, not
> engineering — no task in the build plan produces a case. It can and should
> start before the case editor exists (T-021), because the editor unblocks
> *review*, not *drafting*.

---

## 5.5 Launch market — ✅ DECIDED (11 September 2026), and the question it opened

> **DECIDED: global English-speaking from day one** — India, UK, Commonwealth,
> US and Australia together, with regional pricing (§9.4) doing the work of
> making it affordable in each.

### What this settles

**Payments: Stripe, confirmed.** An India-first launch would have been awkward —
RBI e-mandate rules make recurring card payments materially harder, and a
domestic provider such as Razorpay would likely have been the better fit,
invalidating T-041 as written. A global launch removes that: Stripe handles
multi-currency and regional pricing natively. *(Stripe was assumed throughout
`BUILD_PLAN` and `DATA_MODEL` but never recorded in an ADR. It now has a
reason.)*

### What this does NOT settle

**The Supabase region is still open** (`SECURITY_SPEC` S-4). "Global" does not
mean multi-region — there is one database, in one place, and that place has
legal consequences. UK and EU users bring GDPR transfer obligations if data
sits outside the EU. This must be chosen deliberately before launch.

**Three legal regimes now apply, not one:** UK/EU GDPR, India's DPDP Act, and
US state law such as CCPA. That is a real cost for a two-person team and it
belongs in the launch checklist (`SECURITY_SPEC` §8), not in someone's memory.

---

## D-9 Clinical convention — ✅ DECIDED (12 September 2026)

**A global launch means one set of cases is read by students trained in
different conventions, and the existing five are not neutral.**

Measured in `nidan/domain/content/cases.py`:

| | | |
|---|---|---|
| `mmol/L` | 24 | SI units — UK, India, Australia. **US uses mg/dL** |
| `g/L` | 23 | **US uses g/dL** |
| `paracetamol` | 1 | **US says acetaminophen** |
| `haemo…` | 10 | British spelling |
| `oesophag…` / `esophag…` | 11 / 14 | **inconsistent with itself** |

The cases are written in Commonwealth convention, which matches `CLAUDE.md`'s
house style — but a US student reading *"glucose 7.8 mmol/L"* must convert to
140 mg/dL before they can reason about it. **For a product whose whole subject
is interpreting clinical values, that is not cosmetic friction.**

**Options:**

| | |
|---|---|
| **A · Commonwealth only** | Matches existing content and house style. Accepts friction for US users. Cheapest |
| **B · Locale-aware display** | Store SI, render mg/dL for US users. Real feature work, and it must not change what the detectors match on |
| **C · Dual notation** | `7.8 mmol/L (140 mg/dL)` in the case text. No code, some clutter, works immediately |

> **DECIDED: option A — Commonwealth convention, unchanged.**

### Why the cheapest option was also the right one

The concern was overstated on first inspection, and reading the actual content
corrected it. **Every lab value already carries its own interpretation and
reference range:**

```
27.4 mmol/L (CRITICALLY HIGH — normal 4-7)
4.2 mmol/L (SEVERE ketosis — normal <0.6; DKA requires >3.0)
Na 133 mmol/L (mildly LOW — hyponatraemia in hypothyroidism…)
```

A reader who has never seen `mmol/L` still knows 27.4 is critical, because the
case says so and states the range. **The cases are self-explaining by design**,
which is why the units are not the barrier they appear to be.

Dual notation on every value would add a second number to keep correct in each
future case, for a problem the annotations already solve. Locale-aware rendering
is real feature work for the same modest gain — and the converted text must
never change what the detectors match on, which makes it riskier than it looks.

### What WAS fixed

Two things had no annotation and no US equivalent, so a reader could not carry
themselves:

| Was | Now |
|---|---|
| `Occasional paracetamol` | `Occasional paracetamol (acetaminophen)` |
| `PaCO₂ 3.2 kPa (LOW)` | `PaCO₂ 3.2 kPa / 24 mmHg (LOW)` |
| `PaCO₂ 2.6 kPa (LOW — Kussmaul…)` | `PaCO₂ 2.6 kPa / 20 mmHg (LOW — Kussmaul…)` |
| `PaO₂ 12.4 kPa · PaCO₂ 5.0 kPa` | `PaO₂ 12.4 kPa / 93 mmHg · PaCO₂ 5.0 kPa / 38 mmHg` |

Blood gases are the one place SI and US notation diverge *without* the case
annotating the difference. Four edits, in display text only — neither string is
read by any detector, verified before editing, and the 94% gate is unchanged.

### The rule for cases 6–10

**Write in Commonwealth convention, and annotate every value with its
interpretation and reference range** — the pattern the existing five already
follow. Add a US equivalent only where a value has no annotation to carry it,
as with blood gases.

### Related, and NOT decided here

The annotations sometimes go further than interpretation and state the
conclusion:

```
27.4 mmol/L (CRITICALLY HIGH — normal 4-7). → Diagnostic of hyperglycaemia;
DKA must be excluded
```

For a product about diagnostic reasoning, *"DKA must be excluded"* does part of
the thinking for the learner. That is a content-design question adjacent to
`PRD` P2, not a units question, and it deserves a clinician's judgement before
five more cases are written in the same style. **Raised, not settled.**

**Still outstanding:** the `oesophageal`/`esophageal` mix (11 and 14
occurrences) is an internal inconsistency regardless of market. Not changed —
unlike the four edits above it is not a comprehension barrier, and it touches
far more text.

---

# 6. Functional requirements

Format: **FR-n** · description · user stories · acceptance criteria (testable) · edge cases.

---

## FR-1 · Account and authentication

**Description.** Users create an account with email/password, Google, or Apple. Authentication is delegated to Supabase Auth (`ADR-0002`).

**User stories**
- As a visitor, I can create an account with my email so my progress is saved.
- As a returning user, I can log in and resume where I left off.
- As a user, I can reset a forgotten password.
- As a user, I can permanently delete my account and data.

**Acceptance criteria**

| # | Criterion |
|---|---|
| 1.1 | Signup with email + password ≥ 8 characters; weak passwords rejected with a specific reason |
| 1.2 | Verification email sent on signup; unverified accounts may complete one case then are prompted to verify |
| 1.3 | Google OAuth and Sign in with Apple both available (Apple mandatory per App Store policy) |
| 1.4 | Password reset email expires in 60 minutes and is single-use |
| 1.5 | Login errors never reveal whether an email is registered |
| 1.6 | Failed login rate-limited: 5 attempts per 15 min per email, 20 per hour per IP |
| 1.7 | Session persists 30 days; refresh token rotates on use |
| 1.8 | Account deletion removes identifying fields within 24 h; anonymised results retained (see `DATA_MODEL` §8) |
| 1.9 | Data export produces JSON of all sessions within 24 h |

**Edge cases**

| Case | Behaviour |
|---|---|
| Apple private-relay email | Treated as a valid address; never blocked |
| Signup with an existing email | Generic "check your inbox" message; email sent to the existing account noting the attempt |
| OAuth email matches an existing password account | Accounts linked after email verification; never silently merged |
| Deletion requested with an active subscription | Subscription cancelled first; user warned no refund is automatic |
| Verification email undelivered | "Resend" available after 60 s, max 5 per day |

---

## FR-2 · Trial and onboarding

**Description.** A visitor can complete one full case — including feedback — before creating an account.

*Rationale: requiring registration before the user has experienced the product is the largest avoidable drop-off in a consumer funnel.*

**User stories**
- As a visitor, I can try a real case without signing up.
- As a visitor who finished a trial, I can create an account and keep that result.

**Acceptance criteria**

| # | Criterion |
|---|---|
| 2.1 | Trial reachable in one click from the landing page |
| 2.2 | Trial is a complete case — no truncated feedback |
| 2.3 | Trial session stored server-side against an anonymous id in a `httpOnly` cookie |
| 2.4 | On signup within 30 days, the trial session is claimed and appears in history |
| 2.5 | Exactly one trial per browser; a second attempt prompts signup |
| 2.6 | Onboarding collects role and training year — **two questions maximum** |
| 2.7 | Onboarding is skippable; skipping does not block usage |

**Edge cases**

| Case | Behaviour |
|---|---|
| Cookies cleared mid-trial | Session unrecoverable; user starts again. Accepted limitation |
| Trial abandoned mid-consultation | Resumable for 7 days from the same browser |
| Signup after 30 days | Trial not claimed; account starts empty |

---

## FR-3 · Case selection

**Description.** The system selects which case a user attempts. Users do not browse and pick.

*Rationale: free choice lets users avoid uncomfortable specialties, repeat familiar cases, and — once answers circulate — pick the one they have been told about. System selection also enables the anti-answer-sharing measures in `TECH_SPEC`.*

**User stories**
- As a user, I can start a new case in one click without choosing.
- As a user, I am not shown a case I have already completed until I have seen the others.
- As a Pro user, I can retry a previous case deliberately.

**Acceptance criteria**

| # | Criterion |
|---|---|
| 3.1 | "Start a case" selects from published cases the user has not completed, chosen at random |
| 3.2 | If all cases are completed, the least-recently attempted is offered, clearly marked as a repeat |
| 3.3 | Free users are blocked at the monthly limit with an upgrade prompt (§9) |
| 3.4 | The case's true diagnosis, trap, and key tests are never present in any pre-consultation payload |
| 3.5 | A started case is reserved; refreshing does not reroll it |

**Edge cases**

| Case | Behaviour |
|---|---|
| A case is retired mid-session | The active session completes normally on its pinned version |
| User has an unfinished session | Prompted to resume or abandon; abandoning counts toward the monthly limit |
| No published cases available | Friendly error; alert raised to admin |

---

## FR-4 · Consultation — history taking

**Description.** The user asks free-text questions; an LLM-driven patient replies in character, revealing information only when directly asked.

**User stories**
- As a user, I can ask any question in my own words.
- As a user, I receive a realistic reply that does not volunteer things I did not ask about.
- As a user, I can scroll back through the conversation.

**Acceptance criteria**

| # | Criterion |
|---|---|
| 4.1 | Free-text input, max 500 characters |
| 4.2 | Patient reply returned in p95 < 6 s |
| 4.3 | Every question and reply persisted as an ordered event before the reply is displayed |
| 4.4 | Typing indicator shown while awaiting a reply |
| 4.5 | Input disabled while a reply is pending; no double-submit |
| 4.6 | Question count hard-capped at 40 per session |
| 4.7 | **No coverage indicator, topic hint, or question counter is displayed** (P2) |
| 4.8 | Conversation history is scrollable and complete |

**Edge cases**

| Case | Behaviour |
|---|---|
| LLM call fails after retries | Inline error, question **not** consumed, retry offered. Never a dead end |
| LLM returns empty | Treated as a failure; retried |
| Rate limit reached | "The patient needs a moment" + automatic retry with backoff |
| Empty or whitespace question | Rejected client-side, no server call |
| User pastes real patient data | Detected and blocked with a warning (P4); question not sent |
| Browser closed mid-session | Session resumable for 7 days |
| 40-question cap reached | Further questions blocked; user prompted to examine, investigate, or conclude |

---

## FR-5 · Consultation — examination

**Description.** 27 examination systems, identical for every case.

**Acceptance criteria**

| # | Criterion |
|---|---|
| 5.1 | All 27 shown for every case, grouped anatomically, in a fixed order |
| 5.2 | Selecting one returns its finding — case-specific if defined, otherwise the normal finding |
| 5.3 | Each recorded once; repeat selection re-displays without a duplicate event |
| 5.4 | Findings remain visible for the rest of the session |
| 5.5 | No visual distinction between relevant and irrelevant options before selection |
| 5.6 | Response is immediate (no LLM call) |

**Edge cases**

| Case | Behaviour |
|---|---|
| All 27 performed | Allowed; over-examination is itself a signal |
| Session concluded with none performed | Allowed; reflected in the scorecard |

---

## FR-6 · Consultation — investigations

**Description.** 86 investigations, identical for every case, grouped by specialty.

**Acceptance criteria**

| # | Criterion |
|---|---|
| 6.1 | All 86 shown for every case, grouped by specialty, fixed order |
| 6.2 | Returns case-specific result if defined, otherwise the normal reference result |
| 6.3 | Each recorded once |
| 6.4 | Ordered tests and results remain visible for the rest of the session |
| 6.5 | Search filters by name only — **never ranked by relevance to the case** (P2) |
| 6.6 | Category (key / reasonable / low-value) is never exposed before the feedback screen |

**Edge cases**

| Case | Behaviour |
|---|---|
| Many low-value tests ordered | Allowed; surfaced in the scorecard |
| Search returns nothing | Empty state suggests clearing the filter |

---

## FR-7 · Diagnosis submission

**Description.** The user submits a free-text diagnosis, ending the consultation.

**Acceptance criteria**

| # | Criterion |
|---|---|
| 7.1 | Free-text input, max 200 characters |
| 7.2 | Submission is **irreversible**; a single confirmation dialog states this |
| 7.3 | The confirmation dialog contains **no** hint about readiness or completeness (P2) |
| 7.4 | Assessment computes in p95 < 500 ms |
| 7.5 | Session status set to `completed`; `ended_at` recorded |
| 7.6 | Idempotent — a repeat submission does not produce a second assessment or a second LLM charge |
| 7.7 | Empty submission rejected |

**Edge cases**

| Case | Behaviour |
|---|---|
| Zero questions asked | Permitted. Assessment runs and flags premature closure — this is a real signal, observed in the pilot |
| Assessment engine raises | Session marked `completed`, results computed asynchronously, user shown a "preparing your feedback" state |
| Feedback LLM fails | Rule-based fallback used; user still receives complete feedback |
| Network drops during submission | Idempotency key ensures one assessment on retry |

---

## FR-8 · Assessment and feedback

**Description.** On submission the system evaluates the diagnosis, computes coverage and scorecards, runs the three bias detectors, and generates Socratic feedback.

**Acceptance criteria**

| # | Criterion |
|---|---|
| 8.1 | Diagnosis classified as `correct` / `partial` / `anchored` / `other` |
| 8.2 | Three bias detectors each return flag, score, plain-English reason, and evidence |
| 8.3 | Coverage computed only over the current case's required topics |
| 8.4 | Examination and investigation scorecards categorise every item |
| 8.5 | Feedback is 3–5 lines and **never** contains "bias", "anchoring", "premature closure", or "confirmation bias" (P1) |
| 8.6 | When the diagnosis is wrong, feedback does **not** state the correct answer |
| 8.7 | Every displayed flag cites the user's own questions or omissions (P3) |
| 8.8 | The true diagnosis is revealed after feedback is displayed |
| 8.9 | Results persisted with the engine version that produced them |

**Edge cases**

| Case | Behaviour |
|---|---|
| LLM feedback names a forbidden term | Post-generation filter rejects it and falls back to rule-based |
| Correct diagnosis but all biases flagged | Fully supported and expected — the product's core insight |
| No key investigations defined for a case | Investigation scorecard hidden rather than showing 0/0 |

---

## FR-9 · Progress and history

**Description.** Users see their history and whether their reasoning is improving (JTBD-4).

**Acceptance criteria**

| # | Criterion |
|---|---|
| 9.1 | History lists all completed sessions: date, case, verdict, coverage |
| 9.2 | Any past session's full feedback is re-openable |
| 9.3 | Dashboard shows sessions completed, current streak, longest streak |
| 9.4 | Per-bias trend shown over the last 10 sessions |
| 9.5 | Trend requires ≥ 3 completed sessions; below that an encouraging empty state is shown |
| 9.6 | Streak increments once per calendar day in the user's local timezone |
| 9.7 | Free users see the same progress features as Pro |

**Edge cases**

| Case | Behaviour |
|---|---|
| Fewer than 3 sessions | "Complete 3 cases to see your trend" |
| Timezone change | Streak uses the timezone at session time; never retroactively broken |
| Trend worsening | Shown honestly, framed neutrally — never "you are getting worse" |

---

## FR-10 · Subscription and billing

**Description.** Free tier with a monthly cap; Pro removes it. Stripe on web.

**Acceptance criteria**

| # | Criterion |
|---|---|
| 10.1 | Free users limited to N cases per calendar month ⟨DECIDE §9.1⟩ |
| 10.2 | Remaining allowance visible on the dashboard **before** starting, not during a consultation |
| 10.3 | Upgrade completes without losing session state |
| 10.4 | Stripe webhooks update subscription status idempotently |
| 10.5 | Failed payment enters a 7-day grace period before downgrade |
| 10.6 | Cancellation retains Pro until period end |
| 10.7 | Downgrade never deletes history |
| 10.8 | Prices shown inclusive of tax where required |

**Edge cases**

| Case | Behaviour |
|---|---|
| Limit reached mid-month | Blocked at case start, never mid-consultation |
| Webhook arrives before checkout redirect | Status resolved by webhook; UI reconciles on next load |
| Duplicate webhook | Idempotency key prevents double-processing |
| Chargeback | Subscription cancelled, account retained, admin alerted |
| Subscription expires with a session in progress | Session completes; the next one is blocked |

---

## FR-11 · Account management

**Acceptance criteria**

| # | Criterion |
|---|---|
| 11.1 | Editable: display name, professional role, training year, timezone |
| 11.2 | Email change requires verification of the new address |
| 11.3 | Data export delivered as JSON within 24 h |
| 11.4 | Account deletion requires typed confirmation and is irreversible |
| 11.5 | Research participation is opt-in, default **off**, revocable at any time |

---

## FR-12 · Admin console (v1 minimum)

Full design in `TECH_SPEC`. v1 requires only:

| # | Criterion |
|---|---|
| 12.1 | Case bank browser with status filters |
| 12.2 | Case editor with anchor/clue overlap validation that **blocks save on conflict** |
| 12.3 | Playtest with live detector instrumentation |
| 12.4 | Clinical review queue: assign, approve, reject with comments |
| 12.5 | **No case reaches a user without an approving clinical review record** |
| 12.6 | AI usage and cost dashboard |
| 12.7 | Examination and investigation editors |
| 12.8 | Every admin action written to the audit log |

---

# 7. User flows

## 7.1 First-time visitor → completed trial

```
Landing page
   └─► "Try a case" ─────────────► anonymous session created
            │
            ▼
     Case preview (patient intro)  ─── no diagnosis hints
            │
            ▼
     Consultation ◄──────────────┐
       ├─ ask question ──────────┤
       ├─ examine ───────────────┤
       └─ investigate ───────────┘
            │
            ▼
     Submit diagnosis (confirm — irreversible)
            │
            ▼
     Feedback screen
            │
            ▼
     "Save your progress" ──► signup ──► trial claimed ──► dashboard
```

## 7.2 Returning free user, limit reached

```
Dashboard ──► "Start a case"
                  │
                  ▼
          allowance check
           │            │
      remaining      exhausted
           │            │
           ▼            ▼
      consultation   upgrade prompt
                        ├─► Stripe checkout ─► Pro ─► consultation
                        └─► dismiss ─────────► dashboard (resets on the 1st)
```

## 7.3 Consultation loop

```
                ┌──────────────────────────────┐
                │  ask · examine · investigate │◄──┐
                └──────────────┬───────────────┘   │
                               │                   │
                        (any order, any number)────┘
                               │
                               ▼
                     Submit diagnosis
                               │
                               ▼
                    Assessment (< 500 ms)
                               │
                               ▼
                     Feedback screen
```

No enforced order. A user may investigate before asking anything — that is itself a measurable pattern.

## 7.4 Account deletion

```
Settings ──► Delete account ──► warning (irreversible, subscription cancelled)
                                     │
                                type "DELETE"
                                     │
                                     ▼
                     cancel subscription → anonymise profile
                     → retain pseudonymous results → sign out
```

---

# 8. Screen inventory

Detailed layouts, states, and copy live in `UX_SPEC.md`. This is the complete list, so nothing is discovered late.

| ID | Screen | Auth | Key states |
|---|---|---|---|
| S-01 | Landing | Public | default |
| S-02 | Signup | Public | default · validating · error · success |
| S-03 | Login | Public | default · error · rate-limited |
| S-04 | Password reset request | Public | default · sent |
| S-05 | Password reset | Public | valid · expired token |
| S-06 | Email verification | Public | pending · verified · expired |
| S-07 | Onboarding | Auth | step 1 · step 2 · skipped |
| S-08 | Dashboard | Auth | empty (0 sessions) · normal · limit reached |
| S-09 | Case preview | Both | loading · ready |
| S-10 | Consultation | Both | idle · awaiting reply · error · question cap reached |
| S-11 | Diagnosis confirm | Both | default · submitting |
| S-12 | Assessment pending | Both | computing · slow (> 3 s) |
| S-13 | Feedback | Both | full · fallback feedback |
| S-14 | Session history | Auth | empty · populated |
| S-15 | Session detail | Auth | default |
| S-16 | Progress | Auth | insufficient data (< 3) · populated |
| S-17 | Upgrade / pricing | Auth | default · processing |
| S-18 | Checkout return | Auth | success · cancelled · pending |
| S-19a | Account · Profile | Auth | default · dirty · saving · error |
| S-19b | Account · Security | Auth | password auth · OAuth auth |
| S-19c | Account · Subscription | Auth | free · pro · cancelled · past due · expired |
| S-19d | Account · Research | Auth | opted out · opted in |
| S-19e | Account · Data | Auth | idle · export requested · export ready |
| S-20 | Delete account | Auth | warning · confirming |
| S-21 | Error / 404 | Both | 404 · 500 · offline · maintenance |
| S-22 | OAuth callback | Public | signing in · cancelled · failed |
| S-23 | Session expired | Auth | modal over current context |
| A-01…A-10 | Admin console | Admin | see `UX_SPEC` §12 — dashboard, case bank, editor, playtest, review, content, lexicon, AI ops, users, system |

**Every screen must define its loading, empty, and error state.** Undefined empty states are the most common source of late UI rework.

---

# 9. Monetization

## 9.1 Tiers — ✅ DECIDED (9 September 2026)

> **Recommendation**

| | Trial | Free | Pro |
|---|---|---|---|
| Account required | No | Yes | Yes |
| Cases | **1 total** | **3 per month** | Unlimited |
| Feedback | Full | Full | Full |
| History & progress | Not saved | Full | Full |
| Retry a specific case | No | No | Yes |
| Data export | No | Yes | Yes |

**DECIDED: 3 per month.** Enough to experience the product and see one trend
data point; not enough to satisfy a user preparing for exams. Too generous and
conversion collapses; too tight and the free tier fails as a funnel.

**This is a starting point, not a conclusion.** Nobody guesses this correctly.
It is deliberately a configured value rather than a schema constant — the limit
is a `COUNT` query compared against config (`DATA_MODEL` §11.2), so changing it
is a config change and not a migration. **Instrument it and adjust** (§10).

**Why full feedback on free:** the feedback *is* the product. Crippling it would mean free users never understand what they would be paying for.

## 9.2 Price — ✅ DECIDED (11 September 2026)

> **DECIDED: US$8–12/month, or US$60–80/year.** The exact figure within that
> range is set at T-041, when real LLM cost per completed session is known.
>
> Context: Amboss and UWorld sit at roughly $30–50/month. We are a focused single-purpose tool, not a comprehensive question bank, so we should price meaningfully below them. Anchoring near $10 keeps us in "obvious yes" territory for a student already spending on study tools.
>
> Annual should be priced at ~7 months to drive commitment, which materially improves cash flow and retention.

## 9.3 What is deliberately not monetised

| Not gated | Reason |
|---|---|
| Feedback quality | P1/P3 — it is the product |
| Progress tracking | Drives retention; gating it hurts conversion |
| Data export | Ethical baseline (P5) |

## 9.4 Regional pricing — ✅ DECIDED (11 September 2026)

> **DECIDED: implement purchasing-power-adjusted pricing at launch**, not later.
> This matters more given D-7 — a global launch means an Indian resident and a
> US resident hit the same pricing page on day one.
>
> Original reasoning: Retrofitting price tiers after users have anchored on one price causes support pain and resentment. Stripe supports this natively.

## 9.5 Mobile billing (deferred, but plan now)

Apple requires in-app purchase for digital subscriptions and takes 15–30 %. **Web pricing should not assume 100 % margin**, or mobile launch will force either a price rise or a margin loss.

---

# 10. Success metrics

## 10.1 The one metric that matters

**Weekly active users who complete ≥ 1 case.**

Not signups, not page views. A user who completes a case has experienced the product; one who has not, has not.

## 10.2 Funnel

| Stage | Metric | v1 target — ✅ DECIDED |
|---|---|---|
| Acquisition | Landing → trial start | 25 % |
| Activation | Trial start → trial completed | 60 % |
| Signup | Trial completed → account created | 40 % |
| Habit | Account → 3 cases in first 14 days | 30 % |
| Conversion | Free → Pro within 60 days | 5 % |
| Retention | D30 retention of activated users | 25 % |

**DECIDED: accepted as tabled, explicitly provisional.**

No preference was expressed, so these stand as written. They are **hypotheses,
not goals** — none is validated, and a first product has no benchmark to compare
against. Their only purpose is to make under-performance visible early.

**Revisit after the first 100 activated users.** If a number is missed, the
question is whether the target was wrong, not only whether the product was.

## 10.3 Product-health metrics

| Metric | Why | Threshold |
|---|---|---|
| Consultation abandonment rate | UX and data-quality signal | Investigate above 25 % |
| Median questions per session | Very low means users do not understand the task | Investigate below 4 |
| Feedback fallback rate | LLM reliability | Alert above 5 % |
| **Persona leakage rate** | Threatens measurement validity | Alert above 2 % |
| LLM cost per completed session | Unit economics | Alert above $0.05 |
| p95 patient reply latency | Perceived quality | Alert above 6 s |

## 10.4 Learning-outcome metric

**Mean history coverage across a user's first five sessions, trended.**

If users are learning, this rises. If it does not, our central claim is not working in the wild — regardless of how good the retention numbers look. This is the metric that distinguishes an educational product from an engagement product.

*Note: this is observational, not causal. Causal claims require the controlled study in `TECH_SPEC` §10.*

## 10.5 Deliberately not tracked

| Not tracked | Why |
|---|---|
| Time-on-site as a success measure | Longer is not better; a fast, thorough consultation is a good outcome |
| Individual user rankings | P5 |
| Diagnosis accuracy as the headline | Would incentivise easier cases, undermining the traps |

---

# 11. Open decisions

**All eight decided.** D-1, D-2, D-3 and D-8 on 9 September 2026; D-4 to D-7 on 11 September. **D-7 raised a new open question, D-9** — see §5.5.

| # | Decision | Recommendation | Blocks | Status |
|---|---|---|---|---|
| **D-1** | Primary persona (§3.1) | Clinical-phase students + early trainees | UX tone, case difficulty | ✅ **DECIDED** — recommendation accepted |
| **D-2** | Launch case count (§5.4) | 10 — **5 more to author** | Launch date | ✅ **DECIDED** — 10 |
| **D-3** | Free tier limit (§9.1) | 3 per month | gating code (T-017) | ✅ **DECIDED** — 3/month, instrument and adjust |
| **D-4** | Price point (§9.2) | $8–12/mo, $60–80/yr | Stripe setup | ✅ **DECIDED** — range accepted |
| **D-5** | Regional pricing (§9.4) | Yes, at launch | Stripe setup | ✅ **DECIDED** — yes |
| **D-6** | Funnel targets (§10.2) | As tabled | Analytics setup | ✅ **DECIDED** — accepted, provisional |
| **D-7** | Launch market | — | Pricing, legal | ✅ **DECIDED** — global English-speaking |
| **D-9** | **Clinical convention** (§5.5) | Commonwealth, annotations carry it | Case authoring | ✅ **DECIDED** — 12 Sep 2026 |
| **D-8** | Product name / domain | **Nidan** | Everything user-facing | ✅ **DECIDED** — Nidan |

## D-8 — product name — ✅ DECIDED (9 September 2026)

**The product is called Nidan.**

*Nidān* (निदान) is Sanskrit and Hindi for **diagnosis**. Two syllables, five
letters, spells itself after one hearing, and no awkward consonants in any
major language.

**Why a non-English word met the "must work globally" requirement.** Every
short, meaningful English word is already taken in every worthwhile domain —
`hunch`, `weigh`, `sift`, `pivot`, `lens`, `probe`, `trace`, `astute`,
`cogent`, all gone, none available in `.com`. The Apple strategy — owning a
simple concrete word — is not purchasable by a new company at a sane price.

What remains is what Nokia, Toyota, Sanofi and Anki did: **a word from another
language that reads as invented to everyone else.** Anki is Japanese for
"memorisation" and is used daily by medical students who have never wondered
why. Nidan is the same play, and it happens to mean exactly the right thing.

The decisive property is **ownability**. "Astute" was the strongest English
candidate — *an astute clinician* is the phrase users aspire to — but a common
adjective cannot be trademarked in a crowded category and cannot be ranked for
in search. That is a cost paid every year, forever.

**Domains:** `nidan.app` (product) and `nidan.md` (memorable, and reads as
"MD"). `nidan.health` also available. **`nidan.com` is taken** — as is the
`.com` for every other candidate considered, which is the normal state of
affairs in 2026 rather than a compromise. Linear launched on `linear.app`;
Notion ran on `notion.so` for years.

**Secure the domains before the name appears publicly.**

> **The rename is complete.** Done in two deliberate phases rather than allowed
> to leak — documents first (`488ddcf`), then the Python package `vpsim` →
> `nidan` (`be04ed7`). See `docs/process/RENAME_PLAN.md`.
>
> The plan estimated 259 occurrences across 22 documents. The real figure was
> **48 across 15 files**: the original count was case-insensitive and had swept
> in the package identifier. The plan records the correction, because an
> estimate that was wrong by 5× is worth keeping next to the one that replaced
> it.

---

# 12. Assumptions and risks

| # | Assumption | If wrong |
|---|---|---|
| A-1 | Trainees will pay for a focused single-purpose tool | Conversion fails; pivot to institutional (schema already supports it) |
| A-2 | 20-minute sessions fit study habits | Abandonment high; need shorter case format |
| A-3 | Reasoning feedback is perceived as valuable, not as criticism | Retention fails; feedback tone needs rework — P1 becomes critical |
| A-4 | LLM personas hold up against determined extraction | Measurement invalid; leakage monitoring is the mitigation |
| A-5 | 10 cases is enough to retain a paying user for 3+ months | Churn high; Case Factory becomes urgent, not deferred |

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R-1 | Persona leakage corrupts measurement | **High** | Leakage monitor + adversarial CI (`TECH_SPEC` §4.5) |
| R-2 | Users perceive it as "ChatGPT with extra steps" | **High** | Make measurement visible and central; the scorecard is the differentiator |
| R-3 | Case bank too small to retain | Medium | Prioritise authoring; case variants |
| R-4 | Answer sharing degrades case validity | Medium | System-selected cases, variants, difficulty monitoring |
| R-5 | LLM provider price or policy change | Medium | Gateway abstraction; two providers configured |
| R-6 | Clinical error in a published case | **High** | Mandatory clinical review (FR-12.5) |
| R-7 | A user treats feedback as clinical guidance | **High** | P4 disclaimers, real-data input blocking |

---

*End of PRD. §11 requires sign-off before `DATA_MODEL.md` can be finalised.*
