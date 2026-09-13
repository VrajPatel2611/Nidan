# Security specification

| | |
|---|---|
| **Status** | Draft — first consolidated version |
| **Owner** | Vraj Patel |
| **Related** | `ADR-0001`, `ADR-0002`, `ADR-0005` · `DATA_MODEL` §10 · `API_CONTRACT` §2 · `UX_SPEC` §6, §8.3, §8.6 · `TECH_SPEC` §5.3, §9, §10 |
| **Last updated** | 5 September 2026 |

---

## 1 · What this document is

Security decisions for this product were made correctly but written down in four
different places. Nobody could answer *"is this secure?"* without reading all
four, which means in practice nobody checked.

This document does three things:

1. **Consolidates** the existing decisions into one security model (§4).
2. **Adds the threat model** — who would attack this, what they want, what stops
   them. That did not exist anywhere (§3).
3. **Fills the real gaps** — security headers, dependency management, secrets
   lifecycle, incident response, legal position (§5–§8).

### What it is not

**It is not the authority on any detail it cites.** Where this document
summarises RLS policies, endpoint auth levels, or the deletion transaction, the
authority remains `DATA_MODEL`, `API_CONTRACT` and `UX_SPEC` respectively.
Duplicating DDL here would guarantee drift. Every claim below carries its source;
**when they disagree, the source wins and this document is the bug.**

### Standing assumption

We have no security reviewer, no security budget, and no experience shipping a
product. Every decision here is shaped by that. The strategy is not to be clever
— it is to **delegate the hard parts to people who do this professionally** and
keep our own attack surface small enough to reason about.

---

## 2 · What we are protecting

Not all of it matters equally. Ranked by what a leak would actually cost.

| # | Asset | Why it matters | Where it lives |
|---|---|---|---|
| **A1** | **Performance data linked to a named professional** — *this doctor reasons poorly under time pressure* | Career-damaging. Uniquely sensitive to this product: it is a judgement about professional competence, attached to a real person | `session_results`, `user_progress` |
| **A2** | Consultation transcripts | The learner's own words, showing what they did and did not think to ask | `session_events.payload` |
| **A3** | Account credentials | Standard, but the blast radius is A1 | **Supabase Auth — never ours** |
| **A4** | Clinical case content | Our IP, and the thing five clinician-reviewed cases will have cost most to produce | `case_versions` |
| **A5** | Research dataset | A published claim depends on it. Corruption is worse than disclosure here | `session_results` + `research_pid` |
| **A6** | Payment details | **Never touches our servers** — Stripe-hosted checkout | Stripe |
| **A7** | API keys and service credentials | Compromise means a bill, and access to everything above | Environment, never the repo |

**A1 is the crown jewel, and it is the one a generic security checklist would
miss.** Most products protect data because users would be embarrassed. This one
holds a structured, quantified assessment of a clinician's diagnostic reasoning,
tied to their identity. That is closer to a medical record about the doctor than
to a usage log.

It has a direct product consequence, in §3.

---

## 3 · Threat model

Six actors. For each: what they want, how they would try, what stops them, and
whether that defence exists yet.

### T1 · A learner who wants free access

*Most likely by far. Low sophistication, high volume.*

| Attempt | Defence | Status |
|---|---|---|
| Clear cookies to repeat the anonymous trial | Trial keyed to browser fingerprint + `anonymous_id`; 1 per browser | `API_CONTRACT` §2.9 ✅ |
| Call the API directly to bypass tier gating | Tier checked server-side per endpoint (`pro` auth level), never in the client | `API_CONTRACT` §2.2 ✅ |
| Share one account widely | Rate limits: 20 sessions/day, 60 questions/hour per user | `API_CONTRACT` §2.9 ✅ |

**Accepted:** determined account sharing is not preventable at our price point
and is not worth engineering against.

### T2 · A learner who wants to game the assessment

*Specific to this product. Not a security breach — a validity breach.*

| Attempt | Defence | Status |
|---|---|---|
| Read the coverage meter to learn what to ask | **There is no coverage meter.** Assessment state is never shown during a consultation | `PRD` P2, contract tests CT-1/CT-2 ⚠️ **tests not written** |
| Prompt-inject the patient into volunteering everything | Runtime leak detection · adversarial CI · disclosure | `TECH_SPEC` §5.3 ❌ **T-040, not built** |
| Inspect network traffic for the answer | Case content is sent progressively, not up front | partial ⚠️ |

**This is the most under-defended area in the product, and `TECH_SPEC` §5.3 says
so plainly.** The consequence is not a data breach — it is that coverage measures
the model instead of the learner, and the measurement becomes invalid. For a
product whose entire claim is the quality of its measurement, that is an
existential bug rather than a security one.

### T3 · An employer or institution wanting to see an individual's results

*The one that shapes the product, not just the infrastructure.*

A trainee will not use this honestly if they believe their hospital can see their
scores. The moment it becomes an appraisal tool, every user optimises for looking
competent rather than learning — and the product stops working.

| Attempt | Defence | Status |
|---|---|---|
| Buy institutional access and demand individual data | **Institutional reporting must be aggregate-only, with a floor on group size** | ❌ **not specified anywhere** |
| Ask support for a user's results | Support access requires a mandatory `reason` written to an append-only `audit_log` | `DATA_MODEL` §7.4 ✅ |
| Compel disclosure legally | Out of scope; standard legal process | — |

**Action required.** ADR-0015 preserves an institutional path but no document
states what an institution can and cannot see. **This needs an ADR before any
institutional feature is designed**, because it is a product-defining constraint,
not an implementation detail.

### T4 · A credential-stuffing bot

*Automated, indiscriminate, continuous once you are indexed.*

| Attempt | Defence | Status |
|---|---|---|
| Reused passwords from other breaches | **Supabase Auth** owns credentials; we never see a password | `ADR-0002` ✅ |
| Brute force | 5 attempts / 15 min per email · 20 / hour per IP | `API_CONTRACT` §2.9 ✅ |
| Stolen session token | httpOnly cookies — JavaScript cannot read them; refresh rotates on use | `UX_SPEC` §6.1.3 ✅ |
| Account enumeration via error messages | ⚠️ **Not specified.** Sign-in and password-reset must not reveal whether an email exists | ❌ **gap** |

### T5 · An opportunistic attacker scanning for known vulnerabilities

*No interest in us specifically. Scanning everything.*

| Attempt | Defence | Status |
|---|---|---|
| SQL injection | ORM with parameterised queries; **plus RLS as a second line** — an injected query still cannot read another user's rows | `DATA_MODEL` §10.1 ✅ |
| XSS → session theft | httpOnly cookies mean XSS cannot exfiltrate the session; React escapes by default; CSP | ⚠️ **CSP not specified — §5.3** |
| Known CVE in a dependency | Automated dependency scanning | ❌ **not specified — §5.2** |
| Leaked secret in the repository | `gitleaks` in CI | `BUILD_PLAN` T-006 ✅ **done** |
| Forged Stripe webhook granting `pro` | Stripe signature verification | `API_CONTRACT` `/v1/webhooks/stripe` ✅ |

### T6 · Us — accident, not malice

*Statistically the most likely cause of an actual incident.*

| Attempt | Defence | Status |
|---|---|---|
| Secret committed to git | `gitleaks` in CI | T-006 ✅ **done** |
| Production database queried by hand, data pasted somewhere | Access via migrations and admin console; direct access logged | ⚠️ partial |
| Admin account compromised | MFA on admin accounts | ❌ **not specified — §5.5** |
| PII written to logs | Structured logging, `send_default_pii=False`, never raw question text at INFO | `TECH_SPEC` §10 ✅ |
| Staging seeded with real user data | Staging uses an anonymised copy | `TECH_SPEC` §9.3 ✅ |

### T7 · A third party we depend on is breached

Supabase, Groq, Stripe, Render. **We cannot prevent this; we can limit blast
radius.**

| Provider | Holds | If breached |
|---|---|---|
| Supabase | Everything — database and auth | Total. This is the concentration risk accepted in `ADR-0001` |
| Groq | Prompts in transit | Limited: **prompt and response bodies are never stored** (`DATA_MODEL` §10.3), and prompts carry no name or email |
| Stripe | Payment details | Their liability, their compliance surface. This is why we never touch cards |
| Render | Runtime, environment variables | Secrets exposed → rotate everything (§5.1) |

**Supabase is a single point of failure for A1 through A5.** That was accepted
knowingly in ADR-0001 — the alternative was operating our own Postgres with no
DBA, which is worse. It is recorded here as an accepted risk (§9), not solved.

---

## 4 · The security model

Seven layers. Each cites its authority; details live there.

### L1 · We never handle passwords — `ADR-0002`

Supabase Auth owns credentials. The backend verifies a JWT against Supabase's
JWKS (cached, 10-minute TTL) and reads `sub` as the user id. **The backend never
sees a password.**

Building our own was costed at ~15 developer-days plus permanent liability,
against ~1 day to integrate. With no security reviewer, custom auth for medical
professionals' accounts is the worst available option.

### L2 · Tokens in httpOnly cookies — `UX_SPEC` §6.1.3

```
sb-access-token    httpOnly · Secure · SameSite=Lax · ~1 h
sb-refresh-token   httpOnly · Secure · SameSite=Lax · 30 d, rotates on use
```

`httpOnly` means JavaScript cannot read the cookie at all. The Supabase SDK
defaults to `localStorage`, which any injected script can read — one XSS bug
would leak a 30-day session. With cookies, XSS is still serious but cannot steal
the session.

`SameSite=Lax` rather than `Strict` because `Strict` breaks the OAuth callback,
which arrives from an external origin.

### L3 · The database refuses other people's rows — `DATA_MODEL` §10.1

Row-Level Security on eight tables. A forgotten `WHERE user_id = ...` in
application code returns **nothing** rather than another user's data.

This is the layer most teams skip, and it is the one that converts a routine
application bug into a non-event.

**The exception is documented and bounded:** anonymous trial sessions have no
`auth.uid()`, so they are served through a service-role connection with an
explicit `anonymous_id` filter. That path is short, isolated, and separately
tested — deliberately, because it is the one place the safety net is off.

### L4 · Ownership failures return 404 — `API_CONTRACT` §2.7

A 403 confirms the resource exists. Another user's session is indistinguishable
from a session that does not exist. Admin routes behave the same way: an admin
surface should not confirm its own existence to a non-admin.

### L5 · Rate limits — `API_CONTRACT` §2.9

Login attempts, questions per hour, sessions per day, admin ingestion runs. These
serve two purposes: stopping brute force, and stopping someone running up the
Groq bill. The second is easy to forget and arrives as an invoice.

### L6 · The LLM is outside the trust boundary — `ADR-0005`

Every flag, score and verdict is deterministic Python. The model voices the
patient and writes feedback prose. **It cannot influence a result**, so prompt
injection cannot change anyone's score — the worst it achieves is a strange
patient reply.

This was chosen for measurement integrity, not security. It happens to remove an
entire class of attack, and it is worth understanding as a security property:
*the untrusted component has no authority.*

Enforced structurally by `tests/test_layering.py`, which forbids `groq` in
`domain/` (`TEST_STRATEGY` §5).

### L7 · Deletion, retention, and audit — `DATA_MODEL` §10.2, §10.3, §7.4

Account deletion nulls personal fields, redacts free text, and cancels billing in
one transaction. `session_results` and the `research_pid` link **survive**, so
published analyses stay reproducible — and `UX_SPEC` S-20 must say so plainly on
the confirmation screen. A user has a right to know what does not disappear.

Every admin action writes to an append-only `audit_log` with a mandatory `reason`
for support access to a user's session.

---

## 5 · What this document adds

Gaps in the existing specification. Nothing below is written anywhere else.

### 5.1 · Secrets lifecycle

`BUILD_PLAN` T-006 covers detection (`gitleaks`) but not handling.

**Rules**

1. No secret in the repository. Ever. `.env` is git-ignored; `.env.example`
   documents every variable with a **placeholder, never a real value**.
2. Secrets live in the platform's environment configuration (Render), not in
   files on disk, not in CI YAML, not in a shared document.
3. Different values per environment. **Staging must never hold a production
   credential** — that silently makes staging a production-grade target.
4. Every secret has a named owner and a rotation date.

**Rotation schedule**

| Secret | Rotate | On compromise |
|---|---|---|
| `GROQ_API_KEY` | 12 months | Immediately; revoke old key first |
| Supabase service-role key | 12 months | Immediately — **this bypasses RLS** |
| `FLASK_SECRET_KEY` | 12 months | Immediately; invalidates all sessions |
| Stripe secret key | 12 months | Via Stripe dashboard; roll webhook secret too |
| Database password | 12 months | Immediately |

**If a secret is ever committed, rotating it is mandatory even after the commit
is removed.** Git history is distributed; assume it was cloned. Deleting the
commit is theatre.

The Supabase **service-role key deserves separate care** — it bypasses Row-Level
Security entirely, which means it defeats L3, the layer everything else falls
back on. It should exist in exactly one place in production and never in a
developer's local environment.

### 5.2 · Dependencies and supply chain

**Not mentioned anywhere in the specification today.** For a project whose
frontend will pull hundreds of transitive npm packages, that is a real hole —
`ADR-0006` itself names JavaScript dependency churn as an ongoing cost.

**Rules**

1. **Lock files committed** — `poetry.lock` / `package-lock.json`. An unlocked
   build installs different code on different days.
2. **Automated scanning in CI**, failing the build on High or Critical:
   `pip-audit` for Python, `npm audit --audit-level=high` for JavaScript.
3. **Dependabot** enabled for security updates only. Not feature updates —
   otherwise the noise trains everyone to ignore it.
4. **Adding a dependency is a decision.** Before adding one, ask whether the
   standard library does it. Each one is code we did not write, cannot review,
   and are responsible for.
5. **Pin the base Docker image by digest**, not by tag. `python:3.11-slim` is a
   moving target.

The CI pipeline in `TECH_SPEC` §9.4 already has a `security` step. **This section
defines what that step runs**, which was previously undefined.

### 5.3 · HTTP security headers

Not specified anywhere. Set at the edge, applying to every response.

| Header | Value | Why |
|---|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Browser refuses plain HTTP after first visit |
| `Content-Security-Policy` | see below | The main structural defence against XSS |
| `X-Content-Type-Options` | `nosniff` | Stops MIME-type confusion attacks |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Do not leak our URLs to third parties |
| `X-Frame-Options` | `DENY` | No clickjacking; nothing here should be framed |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | We need none of these |

**CSP starting point**, to be tightened once the frontend exists:

```
default-src 'self';
script-src  'self';
style-src   'self' 'unsafe-inline';
img-src     'self' data:;
connect-src 'self' https://*.supabase.co;
frame-ancestors 'none';
base-uri    'self';
form-action 'self';
```

**Deploy CSP in `Content-Security-Policy-Report-Only` mode first.** A CSP that
breaks the app gets switched off in a hurry and never comes back.

`'unsafe-inline'` for styles is a concession to CSS-in-JS. Removing it needs
nonces, which is a Next.js configuration task rather than a header change.

### 5.4 · Input handling and the three injection classes

| Class | Where | Defence |
|---|---|---|
| **SQL injection** | Any query | ORM with parameterised queries — never string-formatted SQL. **Plus RLS**, so even a successful injection cannot cross a user boundary |
| **XSS** | Learner questions and diagnoses rendered back | React escapes by default. **`dangerouslySetInnerHTML` is banned** — add a lint rule. Plus CSP (§5.3) and httpOnly cookies (L2) |
| **Prompt injection** | Every learner question reaches the model | The model has no authority (L6), so injection cannot alter a score. It **can** break the patient persona — that is T2/T-040, and it is a validity problem, not a security one |

**Additional rules**

- Validate at the boundary with a schema — pydantic in Flask, zod in Next.js.
  Reject unknown fields rather than ignoring them.
- Cap free-text length at the API, not only in the UI. A 2 MB "question" is a
  cost attack on the LLM bill.
- Never interpolate user text into a system prompt. Learner text belongs in a
  `user` message, always.

### 5.5 · Administrative access

The admin console can read every user's session and publish clinical content. It
is the highest-value target in the product and has the fewest users.

| Rule | Status |
|---|---|
| MFA required on every admin account | ❌ **not specified — do this before the first non-founder admin** |
| `role = 'admin'` checked server-side per request, never trusted from a token claim alone | `API_CONTRACT` §2.2 ✅ |
| Admin routes return 404 to non-admins | `API_CONTRACT` §2.7 ✅ |
| Every admin action written to append-only `audit_log` | `DATA_MODEL` §7.4 ✅ |
| Support access to a user's session requires a written `reason` | `DATA_MODEL` §7.4 ✅ |
| Admin accounts are named individuals — **no shared admin login** | ❌ state it here |
| Admin access reviewed when anyone leaves the project | ❌ state it here |

A shared admin account destroys the audit log's value: `actor_id` stops
identifying a person, and every entry becomes unattributable.

### 5.6 · Payments

We never see a card number. Stripe-hosted checkout, Stripe-hosted billing portal.
This is not laziness — PCI compliance is a serious undertaking and the correct
amount of it to do ourselves is none.

- Webhook signature verified on every call (`API_CONTRACT`). **An unverified
  webhook endpoint is a "make me `pro`" button.**
- Webhooks are idempotent — Stripe retries, and a replayed event must not grant a
  second subscription period.
- Entitlement is derived from `subscriptions` in our database, never from a
  client claim.

---

## 6 · Incident response

Not specified anywhere. Two people, no on-call rota — so the plan must be simple
enough to follow while panicking at 2 a.m.

### Severity

| Level | Meaning | Response |
|---|---|---|
| **SEV-1** | User data exposed, or credentials compromised | Immediately, whatever the hour |
| **SEV-2** | Vulnerability found, no evidence of exploitation | Same working day |
| **SEV-3** | Low-severity finding, dependency advisory | Next working day |

### The first hour of a SEV-1

1. **Contain before diagnosing.** Rotate the credential, disable the endpoint,
   revoke the sessions. Understanding can wait; the bleeding cannot.
2. **Preserve evidence.** Snapshot logs *before* redeploying. A redeploy commonly
   destroys the only record of what happened.
3. **Write it down as you go**, in a shared file, with timestamps. Memory is
   unreliable under stress and you will need this for the disclosure.
4. **Do not notify anyone yet.** An early, wrong statement is worse than a
   correct one an hour later.

### Then

5. **Scope it.** Which users, which data, over what window. Say *"we do not yet
   know"* when you do not know.
6. **Fix, and write a regression test.** An incident without a test that would
   have caught it will recur.
7. **Notify.** Affected users plainly: what happened, what data, what you have
   done, what they should do. No euphemism — "a security incident" is honest,
   "an unexpected technical issue" is not.
8. **Write it up.** What happened, why, what changed. No blame — a culture that
   punishes the person who caused an incident produces incidents that get hidden.

### Legal notification

**GDPR: 72 hours** to notify the supervisory authority from becoming aware of a
personal-data breach, where there is risk to individuals. Given asset A1, assume
there is risk.
**India DPDP Act:** notification to the Data Protection Board and to affected
users is required; the clock is short. **Confirm the current requirement with
someone qualified before launch** — this document is not legal advice.

### Contacts — ⟨FILL IN BEFORE LAUNCH⟩

| Role | Who |
|---|---|
| Incident lead | ⟨name⟩ |
| Supabase support | ⟨plan tier, support URL⟩ |
| Stripe support | ⟨dashboard⟩ |
| Legal advice | ⟨name — arrange before launch, not during an incident⟩ |
| `security@` address | ⟨set up and publish; a researcher who cannot report to you will publish instead⟩ |

---

## 7 · Legal and regulatory position

**Not legal advice.** This records our understanding and where advice is needed.

| Question | Position |
|---|---|
| Is this a medical device? | **No.** It is educational software for training. It does not diagnose or treat patients, and gives no advice about a real patient. This must stay true — a feature that advises on a real case changes the regulatory category entirely |
| Do we hold patient data? | **No.** All cases are fictional. This is a significant simplification and should be protected |
| Do we hold health data about users? | **No** — but we hold professional competence data (A1), which is sensitive in its own right if not in the regulatory sense |
| GDPR applicable? | **Yes**, if any EU user. Assume yes |
| India DPDP applicable? | **Yes**, if Indian users — likely the launch market given `PRD` §9.4 regional pricing |
| Where does data live? | Wherever the Supabase region is set. **⟨DECIDE⟩ — this must be chosen deliberately before launch, not defaulted** |
| Lawful basis | Contract for service delivery; **explicit opt-in consent** for research use (`consent_research`), separately revocable |
| Under-16 users | Out of scope — medical trainees. Terms should state a minimum age |

**Required before launch:** a privacy policy, terms of service, a cookie notice,
and a `security@` address. All four are visible to users, and all four are things
a reviewer or an institution will look for.

---

## 8 · Pre-launch checklist

Nothing here is optional, and none of it is expensive. Losing a week to it is
cheaper than one incident.

**Infrastructure**
- [ ] HTTPS enforced, HTTP redirects, HSTS present
- [ ] All security headers set (§5.3); CSP report-only first, then enforcing
- [ ] Every secret rotated from its development value
- [ ] Supabase region chosen deliberately (§7)
- [ ] Backups on, and **one restore actually performed** (`TECH_SPEC` §9.5)

**Application**
- [ ] RLS on for every user-data table; verified by a test that tries to read another user's row
- [ ] Sign-in and password reset do not reveal whether an email exists (T4 gap)
- [ ] Rate limits verified live, not just configured
- [ ] Stripe webhook signature verification tested with a forged request
- [ ] `dangerouslySetInnerHTML` lint rule active
- [ ] Contract tests CT-1/CT-2/CT-5 written (`TEST_STRATEGY` §8)

**Process**
- [ ] `gitleaks`, `pip-audit`, `npm audit` in CI, failing on High
- [ ] Dependabot on, security updates only
- [ ] MFA on every admin account, and on Supabase, Stripe, Render, GitHub
- [ ] No shared admin login
- [ ] Incident contacts filled in (§6)
- [ ] `security@` address live and monitored

**Legal**
- [ ] Privacy policy, terms, cookie notice published
- [ ] Deletion screen states plainly what is retained (`DATA_MODEL` §10.2)
- [ ] Research consent separate from terms acceptance, and revocable

**A note on penetration testing.** A professional test costs more than this
project will have. The honest substitute: work the checklist above, run the
automated scanners, and publish a `security@` address so that a researcher who
finds something can tell you instead of publishing it.

---

## 9 · Accepted risks

Risks we are choosing to carry. Recorded so the choice is visible rather than
accidental.

| Risk | Why accepted | Revisit when |
|---|---|---|
| **Supabase is a single point of failure for A1–A5** | The alternative is self-managed Postgres with no DBA — worse in every dimension. `ADR-0001` | Revenue supports a DBA, or an institutional contract demands it |
| **No professional security review** | Cost. Mitigated by delegating auth and payments, and by defence in depth | First institutional customer, or first outside funding |
| **Persona leakage is unsolved** | Hard problem; `TECH_SPEC` §5.3 rates it the largest residual risk | **T-040 — before any published claim relies on post-pilot data** |
| **Account sharing is not prevented** | Not preventable at this price point | Sharing measurably affects revenue |
| ~~**Session store is in process memory**~~ | ~~Prototype state; blocker B1~~ | ✅ **Closed by T-013.** Session state is an append-only event log; the app runs on 2 gunicorn workers and survives a restart mid-consultation |

---

## 10 · Open items

| # | Item | Owner | Blocking |
|---|---|---|---|
| S-1 | **ADR: what an institution may see.** Aggregate-only with a group-size floor. T3 — product-defining | V | Any institutional feature |
| S-2 | Email enumeration on sign-in and reset — specify behaviour | V | Launch |
| S-3 | MFA policy for admin accounts | V | First non-founder admin |
| S-4 | Data residency / Supabase region ⟨DECIDE⟩ — **now harder: D-7 chose a global launch, so UK/EU users bring GDPR transfer obligations wherever the single database sits** | V | Launch |
| S-5 | CSP finalised against the real frontend | V | T-030 |
| S-6 | Incident contacts filled in | V | Launch |
| S-7 | Privacy policy, terms, cookie notice | V | Launch |
| S-8 | BUILD_PLAN tasks for §5.2, §5.3 and the checklist | V | — |

**S-1 is the one to do first.** It is not an implementation detail — it decides
whether trainees can trust the product, which decides whether the measurement is
valid at all.

---

## 11 · Change log

| Date | Change |
|---|---|
| 5 Sep 2026 | Created. Consolidated `ADR-0001/0002/0005`, `DATA_MODEL` §10, `API_CONTRACT` §2, `UX_SPEC` §6/§8.3. New: threat model (§3), secrets lifecycle, dependency management, security headers, injection handling, admin access, incident response, legal position, pre-launch checklist. |
