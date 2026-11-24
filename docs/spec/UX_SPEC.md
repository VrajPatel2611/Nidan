# Nidan — UX Specification

---

## Contents

**1. Document control**

&nbsp;&nbsp;&nbsp;&nbsp;1.1 Purpose  
&nbsp;&nbsp;&nbsp;&nbsp;1.2 What this document does not cover  
**2. UX principles**

**3. Design system**

&nbsp;&nbsp;&nbsp;&nbsp;3.0 Visual reference — Claude Design canvas  
&nbsp;&nbsp;&nbsp;&nbsp;3.1 Colour tokens  
&nbsp;&nbsp;&nbsp;&nbsp;3.2 Typography  
&nbsp;&nbsp;&nbsp;&nbsp;3.3 Spacing and radius  
&nbsp;&nbsp;&nbsp;&nbsp;3.4 Elevation  
&nbsp;&nbsp;&nbsp;&nbsp;3.5 Component inventory  
**4. Responsive strategy**

&nbsp;&nbsp;&nbsp;&nbsp;4.1 The phone decision  
**5. Global patterns**

&nbsp;&nbsp;&nbsp;&nbsp;5.1 Navigation  
&nbsp;&nbsp;&nbsp;&nbsp;5.2 Loading  
&nbsp;&nbsp;&nbsp;&nbsp;5.3 Errors  
&nbsp;&nbsp;&nbsp;&nbsp;5.4 Empty states  
&nbsp;&nbsp;&nbsp;&nbsp;5.5 Destructive confirmation  
&nbsp;&nbsp;&nbsp;&nbsp;5.6 Toasts  
**6. Authentication**

&nbsp;&nbsp;&nbsp;&nbsp;6.1 How authentication actually works  
&nbsp;&nbsp;&nbsp;&nbsp;6.2 S-01 · Landing  
&nbsp;&nbsp;&nbsp;&nbsp;6.3 S-02 · Signup  
&nbsp;&nbsp;&nbsp;&nbsp;6.4 S-03 · Login  
&nbsp;&nbsp;&nbsp;&nbsp;6.5 S-22 · OAuth callback  
&nbsp;&nbsp;&nbsp;&nbsp;6.6 S-04 / S-05 · Password reset  
&nbsp;&nbsp;&nbsp;&nbsp;6.7 S-06 · Email verification  
&nbsp;&nbsp;&nbsp;&nbsp;6.8 S-23 · Session expired  
**7. Core product screens**

**8. Account, subscription and privacy**

&nbsp;&nbsp;&nbsp;&nbsp;8.1 Structure  
&nbsp;&nbsp;&nbsp;&nbsp;8.2 S-19a · Profile  
&nbsp;&nbsp;&nbsp;&nbsp;8.3 S-19b · Account and security  
&nbsp;&nbsp;&nbsp;&nbsp;8.4 S-19c · Subscription  
&nbsp;&nbsp;&nbsp;&nbsp;8.5 S-19d · Research participation  
&nbsp;&nbsp;&nbsp;&nbsp;8.6 S-19e · Data and privacy  
&nbsp;&nbsp;&nbsp;&nbsp;8.7 S-20 · Delete account  
&nbsp;&nbsp;&nbsp;&nbsp;8.8 S-17 · Pricing  
&nbsp;&nbsp;&nbsp;&nbsp;8.9 S-18 · Checkout return  
**9. Motion**

**10. Accessibility**

**11. Voice and tone**

&nbsp;&nbsp;&nbsp;&nbsp;11.1 Principles  
&nbsp;&nbsp;&nbsp;&nbsp;11.2 Banned vocabulary in user-facing copy  
&nbsp;&nbsp;&nbsp;&nbsp;11.3 Feedback tone examples  
**12. Admin console**

&nbsp;&nbsp;&nbsp;&nbsp;12.1 Access and shell  
&nbsp;&nbsp;&nbsp;&nbsp;12.2 A-01 · Admin dashboard  
&nbsp;&nbsp;&nbsp;&nbsp;12.3 A-02 · Case bank  
&nbsp;&nbsp;&nbsp;&nbsp;12.4 A-03 · Case editor ⭐  
&nbsp;&nbsp;&nbsp;&nbsp;12.5 A-04 · Playtest ⭐  
&nbsp;&nbsp;&nbsp;&nbsp;12.6 A-05 · Review queue  
&nbsp;&nbsp;&nbsp;&nbsp;12.7 A-06 · Clinical content  
&nbsp;&nbsp;&nbsp;&nbsp;12.8 A-07 · Topic lexicon  
&nbsp;&nbsp;&nbsp;&nbsp;12.9 A-08 · AI operations  
&nbsp;&nbsp;&nbsp;&nbsp;12.10 A-09 · Users and support  
&nbsp;&nbsp;&nbsp;&nbsp;12.11 A-10 · System  
**13. Open UX questions**


---

---

# 1. Document control

| Field | Value |
|---|---|
| **Document** | Nidan UX Specification |
| **Version** | v1.0 |
| **Status** | Draft |
| **Owners** | Vraj Patel, Yogesh Bagotia |
| **Depends on** | `PRD.md` §6 (requirements), §7 (flows), §8 (screen inventory) |
| **Consumed by** | `BUILD_PLAN.md`, frontend implementation |

## 1.1 Purpose

Screen-by-screen specification detailed enough to build from without asking questions. Every screen defines its **loading, empty, error and success states**, its copy, and its interaction rules.

## 1.2 What this document does not cover

Visual polish beyond tokens (shadows, illustration style, marketing pages) and admin console visual design (functional spec only — see §12).

---

# 2. UX principles

Derived from `PRD` §4. Where a UI decision is contested, these settle it.

### U1 — Calm, not gamified

Our users are professionals under real time pressure. No confetti, no badges, no aggressive streak-shaming, no red notification dots. Progress is shown factually.

*Test:* would this element feel patronising to a first-year resident at 11pm? If yes, remove it.

### U2 — The measurement is invisible during, visible after

**Nothing in the consultation UI reveals how the user is being assessed.** No coverage meter, no question counter, no topic hints, no "you might want to ask about…", no completeness nudge before submitting.

*Why:* `PRD` P2. A visible metric teaches the metric, not the skill.

### U3 — Every judgement shows its evidence

A flag is never a bare score. It states what the user did or omitted, in their own words where possible.

### U4 — The learner is never labelled

Interface copy never contains *bias*, *anchoring*, *premature closure*, or *confirmation bias*. Section headings describe the behaviour neutrally: **"Diagnostic focus"**, **"History completeness"**, **"Evidence exploration"**.

### U5 — Fail visibly, never silently

If an LLM call fails, say so and offer a retry. Never lose a typed question. Never show a blank state where content should be.

---

# 3. Design system

## 3.0 Visual reference — Claude Design canvas

> **Source of visual truth:** a Claude Design canvas produced during the research
> phase is the reference for look and feel — layout proportion, colour warmth,
> type treatment and overall visual character.
>
> | | |
> |---|---|
> | **Canvas** | ⟨LINK PENDING — paste the Claude Design URL here⟩ |
> | **Status** | To be reconciled with the tokens below |
> | **Precedence** | Where the canvas and §3.1–3.5 disagree, **the canvas wins on visual character** (colour feel, spacing rhythm, type personality). **This document wins on semantics** (what amber *means*, which states must exist, accessibility minimums). |
>
> **Why the split:** the canvas encodes taste, which is hard to write down and
> easy to lose. This document encodes rules that protect the measurement (U2) and
> the learner (U1, U4), which a visual mock cannot express. Neither supersedes the
> other wholesale.
>
> **Action:** once the canvas is available, extract its palette and type scale into
> §3.1 and §3.2, keeping the semantic bindings in §3.1 intact. Any token that has no
> equivalent in the canvas stays as specified here.


## 3.1 Colour tokens

```css
/* Core */
--ink:          #13272F;   /* primary text, dark surfaces */
--ink-2:        #1C3641;   /* raised surface on dark */
--paper:        #FFFFFF;   /* page background */
--surface:      #F4F7F8;   /* cards, panels */
--surface-2:    #EAF1F3;   /* hover, secondary fill */
--rule:         #DFE7EA;   /* borders, dividers */
--muted:        #6C838D;   /* secondary text */

/* Brand + action */
--teal:         #1F7A8C;   /* primary action */
--teal-hover:   #186474;
--teal-subtle:  #E7F1F3;

/* Semantic — these carry meaning, use consistently */
--amber:        #D97D34;   /* attention, flags, "needs work" */
--amber-subtle: #FDF3E9;
--green:        #37785B;   /* correct, key done */
--green-subtle: #E9F3EE;
--red:          #A93B2C;   /* missed, error, destructive */
--red-subtle:   #FBECEA;

/* Focus */
--focus-ring:   #1F7A8C;
```

**Semantic discipline:** amber always means *"this needs your attention"* — a flagged pattern, a missed key item, a warning. It is never decorative. Green means *done correctly*. Red means *missed or failed*. A developer must not use these for visual variety.

## 3.2 Typography

| Token | Size / line-height | Weight | Use |
|---|---|---|---|
| `--t-display` | 40 / 46 | 700 | Landing hero only |
| `--t-h1` | 30 / 38 | 700 | Page title |
| `--t-h2` | 22 / 30 | 600 | Section heading |
| `--t-h3` | 18 / 26 | 600 | Card heading |
| `--t-body` | 16 / 26 | 400 | Default |
| `--t-body-sm` | 14 / 22 | 400 | Secondary |
| `--t-caption` | 12 / 18 | 500 | Labels, metadata |
| `--t-mono` | 14 / 22 | 400 | Lab values, reference ranges |

**Font stack**
```css
--font-ui:   'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'SF Mono', 'Cascadia Mono', Consolas, monospace;
```

Monospace is used **only** for laboratory values and reference ranges, where column alignment aids reading.

## 3.3 Spacing and radius

4 px base scale: `4 · 8 · 12 · 16 · 24 · 32 · 48 · 64`.

```css
--r-sm: 6px;    /* inputs, chips */
--r-md: 10px;   /* cards */
--r-lg: 14px;   /* modals, large panels */
--r-full: 999px;
```

## 3.4 Elevation

Two levels only.

```css
--shadow-1: 0 1px 2px rgba(19,39,47,.06), 0 1px 3px rgba(19,39,47,.08);
--shadow-2: 0 4px 12px rgba(19,39,47,.10), 0 2px 4px rgba(19,39,47,.06);
```

Cards sit flat on `--surface`. Elevation is reserved for overlays, dropdowns, and modals.

## 3.5 Component inventory

Every component the build needs. Anything not listed requires a spec addition.

| Component | Variants | Notes |
|---|---|---|
| `Button` | primary · secondary · ghost · destructive | sizes sm/md/lg; loading and disabled states |
| `TextInput` | default · error | label, hint, error message, char counter |
| `TextArea` | default · error | auto-grow to 4 rows |
| `Select` | — | native on mobile |
| `Chip` | default · selected · disabled | used for examinations/investigations |
| `Card` | flat · elevated | |
| `Banner` | info · success · warning · error | inline, dismissible optional |
| `Modal` | default · destructive | focus-trapped |
| `Toast` | success · error | 4 s auto-dismiss, bottom-right |
| `Tabs` | — | keyboard-navigable |
| `Accordion` | — | used in scorecards |
| `ProgressBar` | — | coverage display **on feedback only** |
| `StatTile` | — | large number + label |
| `Avatar` | — | initials fallback |
| `Skeleton` | text · card · list | all loading states |
| `EmptyState` | — | icon + heading + body + optional CTA |
| `Spinner` | sm · md | inline only |
| `Tooltip` | — | keyboard-accessible |
| `Badge` | neutral · green · amber · red | scorecard rows |

---

# 4. Responsive strategy

| Breakpoint | Range | Support |
|---|---|---|
| `sm` | < 768 px | **Consultation not supported.** Dashboard, feedback, history, settings fully supported |
| `md` | 768 – 1023 px | Full support, consultation in two-pane layout |
| `lg` | ≥ 1024 px | Full support, consultation in three-pane layout |

## 4.1 The phone decision

`PRD` §5.2 excludes phone-sized consultation. On `sm`, S-09 and S-10 show a blocking message rather than a degraded layout:

> **Best on a larger screen**
> A consultation needs room for the patient, your questions, and the test panel side by side. Open Nidan on a tablet or computer to start a case.
> *You can still review your past feedback and progress here.*
> `[ View my progress ]`

**Rationale:** a cramped three-pane clinical interface produces worse reasoning and worse data. Refusing is more honest than shipping something unusable.

---

# 5. Global patterns

## 5.1 Navigation

**Authenticated shell** — persistent top bar:

```
┌──────────────────────────────────────────────────────────────────┐
│  Nidan        Dashboard   History   Progress          ⚙  [AV]   │
└──────────────────────────────────────────────────────────────────┘
```

- Logo returns to Dashboard
- Avatar opens a menu: Settings · Help · Sign out
- Free users additionally see a right-aligned text link: *"3 of 3 cases left this month"* → links to pricing
- **The top bar is hidden entirely during a consultation** (S-10) to remove exit temptation and reduce distraction

**Unauthenticated:** logo · "Try a case" · "Log in".

## 5.2 Loading

| Situation | Pattern |
|---|---|
| Full page | Skeleton matching final layout — never a centred spinner |
| Inline action (button) | Spinner inside the button, label → "Saving…", button disabled |
| Patient reply | Animated three-dot indicator in the message stream |
| Assessment (< 500 ms) | Brief full-screen state, see S-12 |

**No layout shift.** Skeletons must occupy the final content's dimensions.

## 5.3 Errors

Three tiers:

| Tier | Pattern | Example |
|---|---|---|
| **Field** | Inline, red text below input, red border | "Password must be at least 8 characters" |
| **Action** | Inline banner above the affected area, with retry | "The patient couldn't respond. [Try again]" |
| **Page** | Full-page error state with a route home | 500, network loss |

**Rules:** never blame the user · always state the next action · never show a raw error code to a user (log it, show a friendly message, include a support reference id on 500).

## 5.4 Empty states

Every list-bearing screen defines one: icon (line, `--muted`) · heading (what's missing) · one-line body (why / what to do) · primary CTA where an action exists.

## 5.5 Destructive confirmation

Two-step for irreversible actions. Diagnosis submission (S-11) and account deletion (S-20) both use it. Deletion additionally requires typing `DELETE`.

## 5.6 Toasts

Success only, plus non-blocking errors. 4 s, bottom-right, dismissible, `aria-live="polite"`. Never used for anything the user must act on.

---

# 6. Authentication

## 6.1 How authentication actually works

Supabase issues and validates credentials (`ADR-0002`); our application owns the profile lifecycle and every redirect decision.

### 6.1.1 End-to-end flow — email signup

```
Browser                  Next.js server           Supabase Auth        Nidan API
   │                          │                        │                   │
   │─ submit email + pw ─────►│                        │                   │
   │                          │─ signUp() ────────────►│                   │
   │                          │                        │ creates auth.users│
   │                          │◄── session (JWT + rt) ─│                   │
   │                          │                                            │
   │                          │─ set httpOnly cookies ─┐                   │
   │◄── 302 /verify ──────────│◄───────────────────────┘                   │
   │                          │                                            │
   │─ GET /welcome ──────────►│─ POST /v1/me (Bearer) ────────────────────►│
   │                          │◄──────────────── 201 profile ──────────────│
   │◄── onboarding ───────────│                                            │
```

**The profile row is created by our API, not a database trigger.** Creation needs `research_pid` generation, timezone capture, and optional trial claiming — application concerns.

### 6.1.2 OAuth flow — Google / Apple

```
Browser                Next.js            Provider           Supabase         Nidan API
   │─ click Google ──────►│                  │                  │                │
   │                      │─ redirect ──────►│                  │                │
   │◄─────────── consent screen ─────────────│                  │                │
   │─ approve ───────────────────────────────►│                 │                │
   │◄── 302 /auth/callback?code=… ────────────│                 │                │
   │                      │                                                      │
   │─ GET /auth/callback ►│─ exchangeCodeForSession(code) ─────►│                │
   │                      │◄──────────── session ───────────────│                │
   │                      │─ set httpOnly cookies                                │
   │                      │─ POST /v1/me  (idempotent) ─────────────────────────►│
   │                      │◄──────────────── profile ────────────────────────────│
   │◄── 302 (see §6.1.5) ─│                                                      │
```

**Apple private-relay addresses** (`@privaterelay.appleid.com`) are treated as ordinary email. They must never be blocked, and they are the address we send to. `PRD` FR-1 edge cases.

### 6.1.3 Token storage — the security decision

| Option | Verdict |
|---|---|
| **httpOnly cookies via `@supabase/ssr`** | ✅ **Selected.** Refresh token is unreadable by JavaScript, so an XSS bug cannot exfiltrate a long-lived session. Works with Next.js server components and middleware |
| `localStorage` (Supabase SDK default) | ❌ Rejected. Readable by any injected script. For a product holding professional performance data, not acceptable |
| In-memory only | ❌ Rejected. Session lost on every refresh; users would re-authenticate constantly |

```
sb-access-token    httpOnly · Secure · SameSite=Lax · ~1 h
sb-refresh-token   httpOnly · Secure · SameSite=Lax · 30 d, rotates on use
```

`SameSite=Lax` rather than `Strict` — `Strict` breaks the OAuth callback, since the redirect arrives from an external origin.

### 6.1.4 Route protection

Next.js middleware runs before every request:

```
request
  ├─ public route?   → serve
  ├─ session valid?  → serve
  ├─ session expired but refresh valid? → refresh, set cookies, serve
  └─ no session      → 302 /login?next={encoded original path}
```

**Trial routes are public but session-aware** — `/case/{id}` is reachable with only the anonymous cookie.

**Admin routes additionally check `role = 'admin'`** and return 404, not 403 — an admin surface should not confirm its own existence to a non-admin (`API_CONTRACT` §2.7).

### 6.1.5 Where the user lands after authenticating

Deterministic, in priority order. Getting this wrong is the most common cause of a disorienting first session.

| Condition | Destination |
|---|---|
| `?next=` present and same-origin | that path |
| Profile does not exist | `/welcome` (onboarding) |
| Onboarding incomplete | `/welcome` |
| A trial session was just claimed | `/case/{id}/feedback` — show them what they saved |
| Active consultation in progress | `/dashboard` with the resume banner |
| Otherwise | `/dashboard` |

`next` is validated as a same-origin relative path. **An absolute URL is discarded** — open-redirect protection.

### 6.1.6 Token refresh and expiry

The client refreshes silently in the background. If a request returns `401 token_expired`, the client refreshes once and retries. If refresh fails, the user sees S-23 rather than a broken screen.

**Mid-consultation expiry is the case that matters.** A learner 12 questions into a case must never lose work: S-23 appears as a modal over the consultation, and on successful re-auth the consultation resumes exactly where it was — the event log makes this safe (`ADR-0003`).

### 6.1.7 Sign out

```
click Sign out
   ├─ POST to server route → supabase.auth.signOut()
   ├─ clear sb-* cookies
   ├─ clear client cache (TanStack Query)
   └─ 302 → / with toast "You've been signed out"
```

**Sign out does not abandon an active consultation.** The session stays `active` and resumes on next sign-in. Discarding a learner's work on sign-out would be hostile.

Sign out is **not** offered as a confirmation dialog — it is trivially reversible and a dialog would be friction for no benefit.

---

## 6.2 S-01 · Landing

| | |
|---|---|
| **Route** | `/` · **Auth** public |
| **Purpose** | Communicate the differentiator; get the visitor into a trial in one click |

```
┌──────────────────────────────────────────────────────────────────┐
│  Nidan                                    Try a case    Log in   │
├──────────────────────────────────────────────────────────────────┤
│     Getting the diagnosis right isn't                            │
│     the same as reasoning it right.                              │
│                                                                  │
│     Practise clinical reasoning on virtual patients and get      │
│     feedback on how you got there — not just what you concluded. │
│                                                                  │
│     [ Try a case — no signup ]     [ How it works ]              │
├──────────────────────────────────────────────────────────────────┤
│   THE DIFFERENCE                                                 │
│   ┌────────────────────────┐  ┌────────────────────────┐        │
│   │ ✓ Correct diagnosis    │  │ 0%   history covered   │        │
│   │   "GERD"               │  │ 0/4  key tests ordered │        │
│   └────────────────────────┘  └────────────────────────┘        │
│   Most tools would tell this student they did well.              │
├──────────────────────────────────────────────────────────────────┤
│   HOW IT WORKS — Interview · Investigate · Reflect               │
├──────────────────────────────────────────────────────────────────┤
│   About · Privacy · Terms · Contact                              │
│   Nidan is an educational simulation. Not for clinical use.      │
└──────────────────────────────────────────────────────────────────┘
```

| State | Behaviour |
|---|---|
| Default | As above |
| Trial used | Primary CTA → "Create a free account" |
| Authenticated | 302 `/dashboard` |

**The proof block is the differentiator expressed in two cards. Do not move it below the fold.**

---

## 6.3 S-02 · Signup

| | |
|---|---|
| **Route** | `/signup` · **Auth** public |

```
┌────────────────────────────────────────┐
│              Create your account       │
│   Practise clinical reasoning and      │
│   track how you improve.               │
│                                        │
│  ┌──────────────┐  ┌──────────────┐   │
│  │  G  Google   │  │     Apple    │   │   ← OAuth first
│  └──────────────┘  └──────────────┘   │
│                                        │
│  ──────────────  or  ───────────────  │
│                                        │
│  Email                                 │
│  ┌──────────────────────────────────┐ │
│  └──────────────────────────────────┘ │
│                                        │
│  Password                              │
│  ┌──────────────────────────────┬───┐ │
│  │                              │ 👁 │ │
│  └──────────────────────────────┴───┘ │
│  At least 8 characters                 │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │        Create account            │ │
│  └──────────────────────────────────┘ │
│                                        │
│  By creating an account you agree to   │
│  our Terms and Privacy Policy.         │
│                                        │
│  Already have an account? Log in       │
└────────────────────────────────────────┘
```

Max width 420 px, vertically centred, no top navigation.

**OAuth above the fold, deliberately** — most users take it, and burying it below a form costs conversions.

### Fields

| Field | Rules | Error copy |
|---|---|---|
| Email | RFC-valid, trimmed, lowercased | "Enter a valid email address" |
| Password | ≥ 8 characters | "Use at least 8 characters" |
| Password | Not in common-password list | "That password is too common — try something less predictable" |

Show/hide toggle on password. **No strength meter** (U1 — it nags without helping).

### States

| State | Behaviour |
|---|---|
| Default | Email focused |
| Validating | Button spinner, label "Creating account…", form disabled |
| Field error | Inline red text, red border, focus moves to first invalid field |
| **Email already registered** | Generic: "Check your inbox — we've sent you a link." An email goes to the existing account noting the attempt (`PRD` FR-1.5) |
| OAuth cancelled | Return to this screen, no error styling — cancelling is not a failure |
| Provider error | Banner: "We couldn't reach Google. Try again or use email." |
| Success | 302 per §6.1.5 |
| **Claiming a trial** | Banner above the form: "Your case result will be saved to your new account." |

---

## 6.4 S-03 · Login

| | |
|---|---|
| **Route** | `/login` · **Auth** public |

Identical layout to S-02, with "Forgot password?" beneath the password field and "Create one" in the footer.

| State | Behaviour |
|---|---|
| Default | Ready |
| **Invalid credentials** | Banner: "That email or password doesn't match." **Never specify which** — that confirms an account exists |
| Rate limited | Banner: "Too many attempts. Try again in 15 minutes." Submit disabled with a live countdown |
| Unverified email | Login succeeds; routed to S-06 |
| Deleted account | Same generic invalid-credentials message |
| Arrived from `?next=` | Optional inline note: "Log in to continue" |

---

## 6.5 S-22 · OAuth callback

| | |
|---|---|
| **Route** | `/auth/callback` · **Auth** public |
| **Purpose** | Exchange the provider code for a session, create or fetch the profile, redirect |

Never lingers — a spinner with "Signing you in…". If it takes longer than 3 s, add "Almost there."

| State | Behaviour |
|---|---|
| Success | 302 per §6.1.5 |
| `error=access_denied` | 302 `/login` with toast "Sign-in cancelled" |
| Code exchange failed | 302 `/login` with banner "Sign-in didn't complete. Please try again." |
| Profile creation failed | Session is valid but the profile is missing → route to `/welcome`, which retries |

**A user must never be left on this screen.** Every path terminates in a redirect.

---

## 6.6 S-04 / S-05 · Password reset

**S-04 · Request** — `/reset`, email field only.

On submit, **always** the same confirmation regardless of whether the address exists:

> **Check your inbox**
> If an account exists for `{email}`, we've sent a reset link. It expires in 60 minutes.
> `[ Back to log in ]`

**S-05 · Set new password** — `/reset/{token}`

| State | Behaviour |
|---|---|
| Valid token | New password + confirm |
| Expired or used | "This link has expired. `[ Request a new one ]`" |
| Passwords differ | Inline: "Passwords don't match" |
| Success | All other sessions invalidated · toast "Password updated" · 302 `/login` |

**Invalidating other sessions on password change is deliberate** — if the reset was prompted by a compromise, leaving other devices signed in defeats the purpose.

---

## 6.7 S-06 · Email verification

| | |
|---|---|
| **Route** | `/verify` · **Auth** user |

| State | Copy / behaviour |
|---|---|
| Pending | "**Verify your email** — we sent a link to `{email}`." `[ Resend ]` disabled 60 s, max 5/day. Secondary: "Wrong address? `[ Change it ]`" |
| Verified | Toast "Email verified" → 302 per §6.1.5 |
| Expired link | "That link has expired. `[ Send a new one ]`" |
| Already verified | 302 `/dashboard` silently |

**Unverified users may complete one case** (`PRD` FR-1.2). The block appears at the *start* of a second case — never mid-consultation.

---

## 6.8 S-23 · Session expired

Modal, not a page — the user's context is preserved beneath it.

```
┌──────────────────────────────────────────┐
│  Your session expired                    │
│                                          │
│  Sign in again to carry on. Nothing you  │
│  have done has been lost.                │
│                                          │
│  Email     [                          ]  │
│  Password  [                          ]  │
│                                          │
│         [ Sign out ]   [ Sign back in ]  │
└──────────────────────────────────────────┘
```

**"Nothing you have done has been lost" must be true.** It is, because of the event log (`ADR-0003`). On success the modal closes and the user continues exactly where they were — no navigation, no reload.

---

# 7. Core product screens

## S-07 · Onboarding

| | |
|---|---|
| **Route** | `/welcome` |
| **Auth** | Required |
| **Purpose** | Capture role and training year. **Two questions maximum** (FR-2.6) |

### Step 1 — Role
> **What best describes you?**
> Medical student · Intern / F1 · Resident / Registrar · Physician · Other

### Step 2 — Year *(shown only for student/intern/resident)*
> **What year are you in?**
> Selector 1–7 + "Other"

Both steps have a `Skip` text link. Skipping never blocks usage (FR-2.7).

### Copy
| Element | Text |
|---|---|
| H1 | Welcome to Nidan |
| Sub | Two quick questions so we can pitch cases at the right level. |
| Final CTA | Start my first case |

---

## S-08 · Dashboard

| | |
|---|---|
| **Route** | `/dashboard` |
| **Auth** | Required |
| **Purpose** | Get the user into a case in one click; show that progress is being tracked |

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Nidan     Dashboard  History  Progress    3 of 3 left    ⚙ [AV] │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Good evening, Aarav                                            │
│                                                                  │
│   ┌────────────────────────────────────────────────────────┐    │
│   │   Ready for a case?                                     │    │
│   │   A new patient, about 20 minutes.                      │    │
│   │                              [ Start a case ]           │    │
│   └────────────────────────────────────────────────────────┘    │
│                                                                  │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│   │    12    │  │    4     │  │   71%    │                      │
│   │  cases   │  │ day      │  │ history  │                      │
│   │completed │  │ streak   │  │ covered  │                      │
│   └──────────┘  └──────────┘  └──────────┘                      │
│                                                                  │
│   Recent sessions                              View all →        │
│   ┌────────────────────────────────────────────────────────┐    │
│   │ Chest pain, 48M      2 days ago    ✓ Correct     75%  │    │
│   │ Breathlessness, 29F  5 days ago    ◑ Partial     62%  │    │
│   └────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### States

| State | Behaviour |
|---|---|
| **Empty** (0 sessions) | Stat tiles hidden. Hero: "Your first case is waiting" / "You'll interview a patient, decide what to investigate, and get feedback on your reasoning." |
| **Normal** | As above |
| **Limit reached** (free) | Start button disabled. Card becomes: "You've used your 3 cases this month" / "Your next free case unlocks on {date}." `[ Go unlimited — $X/month ]` `[ Maybe later ]` |
| **Unfinished session** | Banner above hero: "You have a consultation in progress — {case}, started {time}." `[ Resume ]` `[ Abandon ]` |
| **Loading** | Skeletons for hero, tiles, list |

### Copy rules
- Greeting varies by local time (Good morning / afternoon / evening)
- **Streak is stated factually, never with urgency.** "4 day streak" — never "Don't lose your streak!" (U1)
- Free allowance shown **here**, never during a consultation (U2)

---

## S-09 · Case preview

| | |
|---|---|
| **Route** | `/case/{sessionId}/preview` |
| **Auth** | Both |
| **Purpose** | Set the scene and let the user commit deliberately |

### Layout
Centred, max-width 620 px.

```
   YOUR PATIENT

   Ramesh Kumar, 48
   ─────────────────────────────────────────
   Ramesh is a 48-year-old accountant who has
   had chest pain for the past three days. It
   tends to come on in the evenings...

   ─────────────────────────────────────────
   Take a history, examine him, order whatever
   investigations you think are appropriate,
   then give your diagnosis.

   There's no time limit.

              [ Begin consultation ]
```

### Critical constraint
**The payload for this screen must not contain the true diagnosis, the trap, key test keys, or required topics** (FR-3.4). Verified by an automated test asserting the response body contains none of those fields.

### States
| State | Behaviour |
|---|---|
| Loading | Skeleton |
| Ready | As above |
| < 768 px | Blocking message (§4.1) |

---

## S-10 · Consultation ⭐

| | |
|---|---|
| **Route** | `/case/{sessionId}` |
| **Auth** | Both |
| **Purpose** | The core experience |

**The single most important screen. It is also the one where U2 must be enforced absolutely.**

### Layout — `lg` (≥ 1024 px)

```
┌───────────────┬─────────────────────────────┬────────────────────┐
│ PATIENT       │                             │ Exams │ Tests │ ✓  │
│               │  ┌───────────────────────┐  │────────────────────│
│ Ramesh Kumar  │  │ I've had this chest   │  │ 🔍 Search…         │
│ 48 · Male     │  │ pain for three days…  │  │                    │
│               │  └───────────────────────┘  │ GENERAL & VITALS   │
│ Chest pain    │                             │ ┌────────────────┐ │
│ 3 days        │      ┌───────────────────┐  │ │ General        │ │
│               │      │ Is it burning or  │  │ │ Vital signs    │ │
│ ───────────   │      │ crushing?         │  │ │ Hydration      │ │
│ EXAMINED      │      └───────────────────┘  │ └────────────────┘ │
│ · Vitals      │                             │                    │
│ · CVS         │  ┌───────────────────────┐  │ CARDIOVASCULAR     │
│               │  │ Burning, mostly.      │  │ ┌────────────────┐ │
│               │  └───────────────────────┘  │ │ Cardiovascular │ │
│               │                             │ │ Peripheral…    │ │
│               │  ● ● ●                      │ └────────────────┘ │
│               │                             │                    │
│               ├─────────────────────────────┤                    │
│               │ Ask a question…      [Send] │                    │
│               ├─────────────────────────────┤                    │
│               │        [ Give diagnosis ]   │                    │
└───────────────┴─────────────────────────────┴────────────────────┘
```

**Column widths at `lg`:** 240 px · flexible · 380 px.

### Layout — `md` (768–1023 px)
Patient card collapses to a 64 px header strip (name, age, complaint). Right panel becomes a slide-over drawer opened by a floating "Examine / Investigate" button. Conversation takes full width.

### Panel: three tabs

| Tab | Contents |
|---|---|
| **Examinations** | All 27, grouped anatomically, fixed order |
| **Investigations** | All 86, grouped by specialty, fixed order, with name-only search |
| **Ordered** | Everything performed/ordered, with results, newest first |

**U2 enforcement on this panel:**
- Search filters by **name only** — never ranked by relevance (FR-6.5)
- No category badges (key/reasonable/low-value) before feedback (FR-6.6)
- No visual distinction between relevant and irrelevant items (FR-5.5)
- No count of how many have been ordered

### Chip states

| State | Appearance |
|---|---|
| Default | `--surface` fill, `--ink` text |
| Hover | `--surface-2` |
| Loading | Spinner replaces label briefly |
| Done | `--teal-subtle` fill, small ✓, remains clickable to re-view |

### Result display
Selecting an item appends a result card to the **Ordered** tab and switches to it. Lab values use `--font-mono` with the reference range beneath in `--t-caption`.

```
┌────────────────────────────────────────┐
│ ECG (12-lead)                          │
│ ────────────────────────────────────── │
│ Normal sinus rhythm, rate 78.          │
│ No ST elevation or depression.         │
│ No T-wave inversion.                   │
└────────────────────────────────────────┘
```

### States

| State | Behaviour |
|---|---|
| **Idle** | Input focused and ready |
| **Awaiting reply** | Input disabled, Send shows spinner, three-dot indicator in stream |
| **Reply error** | Inline banner above input: "The patient couldn't respond just now. `[Try again]`" — **the typed question is preserved in the input** (FR-4, U5) |
| **Rate limited** | "The patient needs a moment…" with automatic retry; no user action needed |
| **Question cap (40)** | Input disabled with note: "You've asked 40 questions — that's plenty. Examine, investigate, or give your diagnosis when ready." |
| **Blocked input** (real patient data detected) | Modal, question not sent (see below) |
| **Resuming** | Full history loaded, banner: "Resumed from {relative time}" |

### Real-patient-data guard (FR-4, `PRD` P4)

On detection of patterns suggesting real patient data (identifiers, dates of birth, hospital numbers, named individuals with clinical detail):

> **Please don't enter real patient information**
> Nidan is a training simulation with synthetic patients. It isn't secure or appropriate for real patient data, and it can't give clinical advice.
> `[ I understand ]`

Question is discarded, not sent. Event logged for admin review.

### Interactions

| Action | Behaviour |
|---|---|
| `Enter` | Send (Shift+Enter for newline) |
| Input | Max 500 chars; counter appears only past 450 |
| Send while pending | Impossible — button and input disabled |
| Browser back | Confirm: "Leave this consultation? Your progress is saved and you can resume." |
| Refresh | Session restored from event log |
| Tab switching | Panel state preserved |

### What is deliberately absent

Listed so no one adds them:

| Absent | Reason |
|---|---|
| Question counter | U2 |
| Coverage / progress meter | U2 |
| Suggested questions | U2 |
| Timer | U1 — adds pressure, changes behaviour |
| "You may want to examine…" hints | U2 |
| Top navigation bar | Focus |

### Accessibility
Conversation is `role="log"` with `aria-live="polite"` so replies are announced. Chips are real `<button>`s, grouped in `<fieldset>` with a `<legend>` per group. Panel tabs follow the WAI-ARIA tabs pattern. Focus returns to the input after a reply arrives.

---

## S-11 · Diagnosis submission

Triggered by `[ Give diagnosis ]`. Modal, focus-trapped.

```
┌──────────────────────────────────────────────┐
│  Your diagnosis                              │
│                                              │
│  What do you think is going on with Ramesh?  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │                                        │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  This ends the consultation and can't be     │
│  undone.                                     │
│                                              │
│         [ Cancel ]   [ Submit diagnosis ]    │
└──────────────────────────────────────────────┘
```

### Critical copy constraint

The dialog states **only** that submission is irreversible. It must **not** contain any readiness or completeness hint (FR-7.3, U2).

**Forbidden copy examples:** *"Are you sure? You've only asked 3 questions."* · *"You haven't ordered any investigations yet."* · *"Most students ask around 8 questions."*

| State | Behaviour |
|---|---|
| Default | Textarea focused, submit disabled while empty |
| Submitting | Submit spinner, modal non-dismissible |
| Error | Inline banner with retry; text preserved |

Max 200 characters.

---

## S-12 · Assessment pending

Full-screen, shown between submission and feedback.

| State | Copy |
|---|---|
| Computing (< 3 s) | "Reviewing your consultation…" + subtle indeterminate bar |
| Slow (> 3 s) | Adds: "Just putting your feedback together." |
| Failed | "We've saved your consultation but couldn't prepare feedback yet. `[Try again]` — we'll email you when it's ready." |

**Never blank.** Assessment computes in < 500 ms; the LLM feedback call is the variable part.

---

## S-13 · Feedback ⭐

| | |
|---|---|
| **Route** | `/case/{sessionId}/feedback` |
| **Auth** | Both |
| **Purpose** | Deliver the product's actual value |

### Ordering principle

Progressive disclosure — outcome first (what they want to know), then process (what they need to know). Reversing this means they scroll past the process to find the verdict.

```
┌──────────────────────────────────────────────────────────────┐
│  1 · VERDICT BANNER                                          │
│      ✓ Correct diagnosis        Your answer: "GERD"          │
├──────────────────────────────────────────────────────────────┤
│  2 · PROCESS SUMMARY                                         │
│      8 questions │ 3 examinations │ 4 tests │ 75% history    │
├──────────────────────────────────────────────────────────────┤
│  3 · YOUR TUTOR                                              │
│      Reflective questions (3–5 lines)                        │
├──────────────────────────────────────────────────────────────┤
│  4 · HISTORY COVERED                        6 of 8           │
│      ✓ pain character   ✓ meals   ○ radiation  ○ family hx   │
├──────────────────────────────────────────────────────────────┤
│  5 · EXAMINATION            ▸ collapsed by default            │
│  6 · INVESTIGATIONS         ▸ collapsed by default            │
├──────────────────────────────────────────────────────────────┤
│  7 · YOUR APPROACH                                           │
│      Diagnostic focus · History completeness · Evidence       │
├──────────────────────────────────────────────────────────────┤
│  8 · THE ANSWER            ▸ collapsed — "Reveal diagnosis"   │
├──────────────────────────────────────────────────────────────┤
│      [ Start another case ]      [ Back to dashboard ]       │
└──────────────────────────────────────────────────────────────┘
```

### 1 · Verdict banner

| Verdict | Fill | Icon | Label |
|---|---|---|---|
| `correct` | `--green` | ✓ | Correct diagnosis |
| `partial` | `--teal` | ◑ | On the right track |
| `anchored` | `--amber` | ↯ | Worth reconsidering |
| `other` | `--muted` | ? | Not quite |

**Note `anchored` uses amber, not red, and reads "Worth reconsidering" — not "Wrong" or "You anchored" (U4).**

### 3 · Tutor feedback
Each line its own block with a left `--teal` rule. Never numbered — numbering implies priority order the model didn't intend.

### 4 · History covered
Two-column grid. Covered: `--green` check. Missed: `--muted` circle. Topic names in sentence case with underscores replaced.

Progress bar shows coverage %. **This is the only progress bar in the product**, and it appears only after the consultation ends.

### 5 / 6 · Scorecards
Collapsed by default (they are long). Header shows a summary: *"Examination — 2 of 3 key done."*

Row format:

| Icon | Meaning | Colour |
|---|---|---|
| ✓ | Key item, done | `--green` |
| ○ | Key item, missed | `--red` |
| · | Relevant, done | `--muted` |
| ⚠ | Low value, ordered | `--amber` |
| · | Not needed here | `--muted`, reduced opacity |

### 7 · Your approach — the bias section

**Headings are behavioural, never diagnostic (U4):**

| Internal detector | User-facing heading |
|---|---|
| `anchoring` | **Diagnostic focus** |
| `premature_closure` | **History completeness** |
| `confirmation_bias` | **Evidence exploration** |

Each shows: heading, a neutral status line, and the traceable reason (U3).

```
┌────────────────────────────────────────────────────────┐
│  ↓  Diagnostic focus — consider broadening              │
│     6 of your 8 questions explored a cardiac cause.     │
│     You asked 1 question about other possibilities.     │
└────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────┐
│  ✓  History completeness                                │
│     You covered 6 of 8 key areas before concluding.     │
└────────────────────────────────────────────────────────┘
```

Flagged uses `--amber` and a ↓ icon. Clear uses `--green` and ✓. **Never red** — this is formative feedback, not a fail.

### 8 · The answer
Collapsed, revealed on click (FR-8.8). Shows the true diagnosis and a short explanation of the trap. Deliberately last so the user engages with their process before learning the answer.

### States

| State | Behaviour |
|---|---|
| Full | All sections |
| Fallback feedback | Section 3 renders rule-based lines; no visual difference, no apology |
| No key investigations for this case | Section 6 hidden entirely, not "0 of 0" |
| Trial user | Sticky footer: "Save this result — create a free account" |

---

## S-14 / S-15 · History and session detail

**S-14** — reverse-chronological list: case, relative date, verdict badge, coverage %. Paginated at 20.

Empty state: "No sessions yet — your completed cases will appear here." + `[ Start a case ]`

**S-15** — reuses the S-13 layout in read-only mode, plus a "Viewed {date}" header and a "Back to history" link.

---

## S-16 · Progress

| | |
|---|---|
| **Route** | `/progress` |
| **Purpose** | JTBD-4 — evidence that reasoning is improving |

### Content

1. **Coverage trend** — line chart, last 10 sessions, with a mean line
2. **Pattern frequency** — for each of the three, the rate over the last 10 sessions versus the 10 before
3. **Diagnostic outcomes** — stacked bar of verdict distribution

### Insufficient data (< 3 sessions)

> **Not enough data yet**
> Complete 3 cases and we'll start showing how your reasoning is changing.
> *2 of 3 completed*
> `[ Start a case ]`

### Copy rules
- Improvement stated plainly: "Diagnostic focus flagged in 2 of your last 10 cases, down from 5."
- **Decline stated equally plainly and neutrally.** No "you're getting worse", no alarm styling. Facts, not judgement (U1).

---

# 8. Account, subscription and privacy

The account area is where a user manages their relationship with the product. It is not a settings dumping ground — each section answers a question the user actually has.

## 8.1 Structure

`/account` with a left sidebar on `md`+, stacked accordion on `sm`.

```
┌──────────────────────────────────────────────────────────────────┐
│  Nidan     Dashboard  History  Progress              ⚙  [AV]     │
├──────────────┬───────────────────────────────────────────────────┤
│              │                                                   │
│  Profile     │   Profile                                         │
│  Account     │   ─────────────────────────────────────────────   │
│  Subscription│   How you appear and how we pitch cases.          │
│  Research    │                                                   │
│  Data        │   Display name                                    │
│              │   ┌─────────────────────────────────────┐        │
│  ──────────  │   └─────────────────────────────────────┘        │
│  Sign out    │                                                   │
│              │   …                                               │
└──────────────┴───────────────────────────────────────────────────┘
```

**Sign out sits at the bottom of the sidebar, visually separated** — it is a different kind of action from the settings above it.

Each section saves independently. **No global "Save all" button** — a user changing their timezone should not be forced to think about their subscription.

| Section | Route | Answers |
|---|---|---|
| Profile | `/account/profile` | "How do I appear, and how are cases pitched to me?" |
| Account | `/account/security` | "How do I sign in, and is it secure?" |
| Subscription | `/account/subscription` | "What am I paying, and how do I stop?" |
| Research | `/account/research` | "Is my data being used for research?" |
| Data | `/account/data` | "What do you hold, and how do I leave?" |

---

## 8.2 S-19a · Profile

**Route** `/account/profile` · **Auth** user

| Field | Control | Notes |
|---|---|---|
| Display name | Text, optional | Empty falls back to the email local-part |
| Professional role | Select | `PRD` §3.1 values |
| Year of training | Select 1–7 + Other | Hidden unless role is student/intern/resident |
| Country | Select | Used for regional pricing (`PRD` §9.4) |
| Timezone | Select, IANA | **Affects streak calculation** — see below |

### Timezone change

Changing timezone shows an inline note:

> Your streak is calculated in your local time. Changing this won't break your current streak.

**And it must not.** `DATA_MODEL` §2.2 stores the timezone at session time; a streak already earned is never retroactively invalidated (`PRD` FR-9 edge cases).

| State | Behaviour |
|---|---|
| Default | Values loaded |
| Dirty | "Save changes" enabled; unsaved-changes guard on navigate away |
| Saving | Button spinner |
| Saved | Toast "Profile updated" |
| Error | Inline banner, values preserved |

---

## 8.3 S-19b · Account and security

**Route** `/account/security` · **Auth** user

### Sign-in method

Shows how this account authenticates, because it determines what can be changed:

```
┌────────────────────────────────────────────────┐
│  Signed in with Google                         │
│  aarav@gmail.com                               │
│                                                │
│  Your password is managed by Google.           │
└────────────────────────────────────────────────┘
```

| Method | Email change | Password change |
|---|---|---|
| Email + password | ✅ requires verification of the new address | ✅ requires current password |
| Google / Apple | ❌ managed by the provider | ❌ managed by the provider |

**OAuth users must not be shown a disabled password field.** Explain where it lives instead — a greyed-out control invites confusion and support tickets.

### Email change

Two-step (`PRD` FR-11.2): enter the new address → verification sent to the **new** address → email updated only when confirmed. A notification also goes to the **old** address, so an account takeover is visible to the real owner.

### Password change

Current password, new password, confirm. On success, **all other sessions are invalidated** and a toast confirms it. Same reasoning as §6.6.

### Active sessions *(deferred — see §13 UX-7)*

Listing devices with a "sign out everywhere" control is good practice but not v1.

---

## 8.4 S-19c · Subscription

**Route** `/account/subscription` · **Auth** user

### Free tier

```
┌────────────────────────────────────────────────┐
│  Free plan                                     │
│  3 cases per month · full feedback             │
│                                                │
│  2 of 3 used this month                        │
│  ████████████░░░░░░  resets 1 September        │
│                                                │
│           [ Go unlimited — ₹XXX/month ]        │
└────────────────────────────────────────────────┘
```

### Pro — active

```
┌────────────────────────────────────────────────┐
│  Pro                                           │
│  Unlimited cases                               │
│                                                │
│  ₹XXX / month · renews 22 September 2026       │
│  Visa ending 4242                              │
│                                                │
│  [ Manage billing ]        [ Cancel plan ]     │
└────────────────────────────────────────────────┘
```

`Manage billing` opens the Stripe customer portal — we do not build card management (`API_CONTRACT` §8).

### States

| State | Display |
|---|---|
| Free | Allowance meter + upgrade |
| Pro active | Renewal date, payment method, manage, cancel |
| **Pro, cancelled** | "Pro until 22 September. You'll move to Free after that." `[ Resume Pro ]` — never treat a cancellation as immediate |
| **Past due** | Amber banner: "We couldn't take payment. Your Pro access continues until 29 August." `[ Update payment ]` |
| Expired | Free display + "Your Pro plan ended on {date}" |
| Apple/Google-billed *(mobile, later)* | Read-only, with "Manage in the App Store" — Apple forbids in-app cancellation flows for IAP |

### Cancellation

Single confirmation, and it states the truth plainly:

> **Cancel Pro?**
> You'll keep unlimited access until **22 September 2026**, then move to the Free plan (3 cases a month).
> **Your history and progress are kept.**
> `[ Keep Pro ]` `[ Cancel plan ]`

**No retention interstitial, no discount offer, no "are you sure?" chain.** Dark patterns on cancellation are the fastest way to lose a professional audience — and in several jurisdictions they are unlawful.

The "history and progress are kept" line is the reassurance that actually matters (`PRD` FR-10.7).

---

## 8.5 S-19d · Research participation

**Route** `/account/research` · **Auth** user

Off by default (`PRD` FR-11.5). This screen must be readable by someone who has never seen a consent form.

```
┌────────────────────────────────────────────────┐
│  Help improve clinical reasoning research      │
│                                                │
│  Nidan began as a research project. With your  │
│  permission we include your anonymised results │
│  in studies of how doctors learn to reason.    │
│                                                │
│  What we would use                             │
│   · Your coverage, questions asked, verdicts   │
│   · Never your name or email                   │
│   · Identified only by a random code (U4B7C…)  │
│                                                │
│  What it does not change                       │
│   · Your experience of the product             │
│   · Your subscription                          │
│                                                │
│  [ ] I agree to my anonymised results being    │
│      used for research                         │
│                                                │
│  Read the full information sheet →             │
└────────────────────────────────────────────────┘
```

| Rule | Detail |
|---|---|
| Default | **Off.** Never pre-ticked |
| Enabling | Records `consent_version` and `consent_at` (`DATA_MODEL` §4.1) |
| Withdrawing | Immediate. Future exports exclude them; already-published aggregate analyses are not retracted — **stated on screen** |
| Version change | If the consent text changes materially, consent is re-requested rather than assumed |

**The honest sentence users deserve:** withdrawing stops future use but cannot un-publish an analysis that already included them. Saying so is the difference between consent and a checkbox.

---

## 8.6 S-19e · Data and privacy

**Route** `/account/data` · **Auth** user

```
┌────────────────────────────────────────────────┐
│  Your data                                     │
│                                                │
│  Download a copy                               │
│  Everything we hold: your profile, sessions,   │
│  questions and feedback, as JSON.              │
│                        [ Request download ]    │
│                                                │
│  ────────────────────────────────────────────  │
│                                                │
│  Delete your account                           │
│  Permanent. This cannot be undone.             │
│                        [ Delete account ]      │
└────────────────────────────────────────────────┘
```

| State | Behaviour |
|---|---|
| Export idle | Button ready |
| Export requested | "We're preparing your download — we'll email you within 24 hours." Button disabled 24 h |
| Export ready | Banner with a signed link, valid 7 days |

---

## 8.7 S-20 · Delete account

**Route** `/account/delete` · **Auth** user · **Full page, not a modal** — deliberately high-friction.

```
┌──────────────────────────────────────────────────────────────┐
│  ← Back to data and privacy                                  │
│                                                              │
│  Delete your account                                         │
│                                                              │
│  What happens                                                │
│   ✕  Your Pro subscription is cancelled immediately          │
│   ✕  Your name, email and profile are removed within 24 h    │
│   ✕  Everything you and the patient typed is redacted,       │
│      and so is the feedback written about it                 │
│   ✕  You are signed out of every device                      │
│                                                              │
│  What we keep, and why                                       │
│   ·  Anonymised results — coverage scores and outcomes —     │
│      linked only to a random code, never to you.             │
│      This keeps published research reproducible.             │
│      Read more →                                             │
│                                                              │
│  ⚠  This cannot be undone. There is no recovery period.      │
│                                                              │
│  Type DELETE to confirm                                      │
│  ┌────────────────────────────────────┐                      │
│  └────────────────────────────────────┘                      │
│                                                              │
│       [ Cancel ]        [ Delete my account ]                │
└──────────────────────────────────────────────────────────────┘
```

| Rule | Detail |
|---|---|
| Confirmation | Must type `DELETE` exactly; button disabled until then |
| Active subscription | Extra line: "You will not be refunded for the remainder of this period" |
| On success | Sign out → landing page → toast "Your account has been deleted" |
| Confirmation email | Sent to the old address before it is removed |
| On 202 | `DELETE /v1/me` answers **202**, not 204 — the data is erased, the external steps follow. Sign out and show the toast; do not wait for anything |

**The "what we keep" section is not legal boilerplate — it is the ethical core of this screen.** `DATA_MODEL` §10.2 retains `research_pid` and results after erasure. A user has an absolute right to know that before they click, not to discover it in a privacy policy afterwards. The 202 response carries the same list in `retained`, so the screen and the API cannot drift apart.

**This screen described something the database refused, for nineteen days.** "The questions you typed are permanently redacted" was printed above the confirmation box while `DELETE /v1/me` returned 501, because §10.2's redaction UPDATEs an append-only table (API-9, settled by `ADR-0018`). The copy has been widened rather than narrowed: the erasure now covers the patient's replies and the feedback prose as well, because feedback cites the learner's own questions by design (`PRD` P3) and a reply can quote the question it answered.

**Both of the promises this screen made beyond the database are now kept — conditionally, and the condition is worth stating.** T-038's worker (`python -m nidan.jobs run`) sends the confirmation and deletes the credential, in that order, because the address lives in `auth.users` and after the deletion there is nothing left to fetch. The condition: the confirmation reaches an inbox only when `EMAIL_ADAPTER` names a real provider — the only adapter built writes each message to a file — and the credential is deleted only when `SUPABASE_SERVICE_ROLE_KEY` is set. **Neither failure is silent.** Both steps refuse, record `job.step_failed` with a reason, and make the run's exit code non-zero; `python -m nidan.jobs status` lists what is outstanding. That is criterion 5 — "the 24 h is met or the failure is visible to an admin" — and it is deliberately the honest half of the pair, because a step recorded as done with nothing behind it would make this screen's promise permanently and invisibly false.

Until the worker has run, an erased account can still present a valid token. Every learner route reaches the profile through `ProfileRepository.get()`, which filters `deleted_at IS NULL`, so the API answers the ordinary 404 to all of it — but the sign-in page will not say the account is gone.

---

## 8.8 S-17 · Pricing

**Route** `/pricing` · **Auth** user or public

Two cards side by side, monthly/annual toggle showing the annual saving.

| Trigger | Heading |
|---|---|
| From navigation | "Choose your plan" |
| From limit reached | "You've used your 3 cases this month" |

**Copy discipline: describe what Pro *adds*, never what Free *lacks*.**

| ✅ Write | ❌ Never write |
|---|---|
| "Unlimited cases" | "No monthly limit" |
| "Retry any case" | "Free users can't retry" |

Prices are rendered from the server-resolved regional price (`PRD` §9.4) — the client never computes or sends a price.

---

## 8.9 S-18 · Checkout return

**Route** `/account/subscription?checkout={status}`

| State | Behaviour |
|---|---|
| Success | Toast "You're on Pro" · subscription section shows the new plan · `[ Start a case ]` |
| Cancelled | Return to pricing, **no error styling** — cancelling is a valid choice |
| Pending | "Confirming your payment…" polls for 30 s, then "We'll email you when it's confirmed." Never leaves the user stuck |

The pending state exists because the Stripe webhook can arrive after the browser redirect (`PRD` FR-10 edge cases). The UI reconciles rather than guessing.

---

# 9. Motion

Minimal and purposeful.

| Element | Duration | Easing |
|---|---|---|
| Button hover | 120 ms | ease-out |
| Modal enter | 180 ms | ease-out (fade + 8 px rise) |
| Toast | 200 ms | ease-out |
| Accordion | 200 ms | ease-in-out |
| Message append | 160 ms | ease-out (fade + 4 px rise) |
| Skeleton shimmer | 1.4 s loop | linear |

**`prefers-reduced-motion: reduce` disables all of the above**, replacing them with instant state changes. Non-negotiable.

No parallax, no scroll-triggered animation, no page transitions.

---

# 10. Accessibility

Target: **WCAG 2.1 AA** on all authenticated screens.

| Requirement | Detail |
|---|---|
| Contrast | 4.5:1 body, 3:1 large text and UI boundaries. `--muted` on `--paper` verified |
| Keyboard | Every action keyboard-reachable; logical tab order; visible 2 px focus ring |
| Focus management | Modals trap focus and restore it on close; route changes move focus to `h1` |
| Screen readers | Conversation `aria-live="polite"`; chips labelled with group context; scorecard icons have text alternatives |
| Colour independence | Every status carries icon + text, never colour alone |
| Forms | Every input has a `<label>`; errors linked via `aria-describedby` |
| Targets | Minimum 44 × 44 px |
| Zoom | Usable at 200 % without horizontal scroll |

**Testing:** axe-core in CI on every screen; manual keyboard pass on the consultation and feedback screens before release.

---

# 11. Voice and tone

## 11.1 Principles

| Principle | Do | Don't |
|---|---|---|
| Peer, not examiner | "You covered 6 of 8 key areas." | "You failed to cover 2 areas." |
| Specific | "You asked 1 question about other possibilities." | "You didn't explore enough." |
| Curious, not corrective | "What would you have expected if that were wrong?" | "You should have considered GERD." |
| Plain | "history covered" | "diagnostic yield of history acquisition" |
| Never label | "Diagnostic focus — consider broadening" | "You showed anchoring bias" |

## 11.2 Banned vocabulary in user-facing copy

`bias` · `anchoring` · `premature closure` · `confirmation bias` · `wrong` (as a verdict) · `failed` · `poor` · `should have`

Enforced by an automated copy test scanning rendered templates and LLM feedback output.

## 11.3 Feedback tone examples

| Situation | Copy |
|---|---|
| Correct, thorough | "Correct, and your workup got you there safely." |
| Correct, rushed | "You reached the right answer. What would you have needed to see to be confident it wasn't cardiac?" |
| Anchored | "Most of your questions explored one explanation. What findings would have made you reconsider?" |
| Very few questions | "You concluded quickly. Which parts of the history were you most confident you could skip?" |

The last is deliberate: it invites the learner to articulate their reasoning rather than accusing them of skipping.

---

# 12. Admin console

Internal, desktop-only, no responsive requirement. Jinja + HTMX (`ADR-0006`). Every action writes to `audit_log`.

## 12.1 Access and shell

Admin uses the **same authentication** as the product (`ADR-0002`) with `role = 'admin'` on the profile. There is no separate admin credential store — a second credential system is a second thing to compromise.

```
/admin/*  →  session valid?  ──no──►  404
          →  role = 'admin'? ──no──►  404
          →  serve
```

**404, never 403.** A non-admin should not learn that an admin console exists (`API_CONTRACT` §2.7).

### Shell

```
┌───────────────────────────────────────────────────────────────────────┐
│ Nidan Admin    Cases  Content  AI Ops  Users  System      admin@… ▾   │
├──────────────┬────────────────────────────────────────────────────────┤
│              │                                                        │
│  Case bank   │   {screen content}                                     │
│  Review (3)  │                                                        │
│  Playtest    │                                                        │
│              │                                                        │
└──────────────┴────────────────────────────────────────────────────────┘
```

Sidebar is contextual to the top-level section. Pending counts (review queue, leakage queue) appear as plain numbers in brackets — **no red badges** (U1 applies to admins too; a permanently red dot stops being information).

---

## 12.2 A-01 · Admin dashboard

**Route** `/admin` — the operational answer to "is anything wrong right now?"

```
┌───────────────────────────────────────────────────────────────────┐
│  Today                                                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │   142    │ │   118    │ │  $1.84   │ │  0.9%    │            │
│  │ sessions │ │completed │ │ LLM cost │ │ leakage  │            │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│                                                                   │
│  Needs attention                                                  │
│  · 3 cases awaiting clinical review          → Review queue       │
│  · 2 leakage flags unreviewed                → AI Ops             │
│  · Feedback fallback rate 6.2% (alert > 5%)  → AI Ops             │
│                                                                   │
│  Content                                                          │
│  10 published cases · 2 drafts · 0 retired                        │
└───────────────────────────────────────────────────────────────────┘
```

"Needs attention" is empty when nothing is wrong, and says so. A dashboard that always shows work is ignored.

---

## 12.3 A-02 · Case bank

**Route** `/admin/cases`

```
┌───────────────────────────────────────────────────────────────────────────┐
│  Cases                                             [ + New case ]         │
│  Status [All ▾]  Origin [All ▾]  Review [All ▾]   🔍                      │
├──────┬────────────────────┬──────────┬─────────┬────────┬───────┬────────┤
│      │ Title              │ Status   │ Review  │Attempts│ Trap  │ Cov.   │
├──────┼────────────────────┼──────────┼─────────┼────────┼───────┼────────┤
│ [ ]  │ The Chest Pain Trap│published │ ✓ Dr A  │  412   │ 61%   │ 58%    │
│ [ ]  │ Breathless & Worried│published│ ✓ Dr B  │  388   │ 54%   │ 62%    │
│ [ ]  │ Confused Elderly Man│in_review│ pending │    0   │  —    │  —     │
│ [ ]  │ Tired Teacher      │ draft    │  —      │    0   │  —    │  —     │
└──────┴────────────────────┴──────────┴─────────┴────────┴───────┴────────┘
   2 selected    [ Assign for review ]  [ Publish ]  [ Retire ]  [ Export ]
```

| Column | Meaning |
|---|---|
| **Trap** | % of attempts ending in an `anchored` verdict — **the case's real difficulty** |
| **Cov.** | Mean history coverage — how thoroughly learners work this case |

**A falling trap rate over time is evidence of answer sharing** (`ADR-0014`, `DATA_MODEL` §11.6). Sort by it descending to see which cases are wearing out.

| State | Behaviour |
|---|---|
| Empty | "No cases yet" + `[ + New case ]` |
| Filtered empty | "No cases match those filters" + `[ Clear ]` |
| Bulk publish, one lacking review | Publishes the eligible ones; names the blocked ones explicitly |

---

## 12.4 A-03 · Case editor ⭐

**Route** `/admin/cases/{id}/versions/{v}` — the screen that lets a non-programmer own clinical content.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ← Cases    The Chest Pain Trap · v2 (draft)      [ Playtest ] [ Save ]   │
├────────────────┬─────────────────────────────────────────────────────────┤
│ ▸ Patient      │  The trap                                               │
│ ▸ Truth        │  ─────────────────────────────────────────────────────  │
│ ▪ The trap     │  Anchor topic                                           │
│ ▸ History      │  ┌───────────────────────────────────────────────────┐ │
│ ▸ Clues        │  │ cardiac / heart disease                           │ │
│ ▸ Examination  │  └───────────────────────────────────────────────────┘ │
│ ▸ Tests        │                                                         │
│ ▸ Persona      │  Anchor keywords                          31 terms      │
│                │  ┌───────────────────────────────────────────────────┐ │
│ ─────────────  │  │ heart ✕  cardiac ✕  angina ✕  ecg ✕  troponin ✕   │ │
│ Validation     │  │ + add                                             │ │
│  ✓ 6 checks    │  └───────────────────────────────────────────────────┘ │
│  ✕ 1 failing   │                                                         │
│                │  ⚠ Conflict with contradictory clues                    │
│                │  "heart" also appears in clue set 4. A learner asking   │
│                │  about the trap would be counted as exploring the       │
│                │  evidence against it.                                   │
│                │  [ Remove from anchor ]  [ Remove from clue set 4 ]     │
└────────────────┴─────────────────────────────────────────────────────────┘
```

### Sections

| Section | Contents |
|---|---|
| Patient | Name, age, sex, presenting complaint, intro, opening line |
| Truth | Correct diagnosis, accepted phrases, partial phrases |
| The trap | Anchor topic, anchor keywords, alternative-hypothesis keywords |
| History | Required topics (multi-select from lexicon), minimum questions |
| Clues | Contradictory clue sets, each a tag list |
| Examination | All 27 — mark key, write the finding (blank = normal) |
| Tests | All 86 — category and result |
| Persona | System prompt, live token counter |

### Validation — the part that matters

The sidebar shows all seven invariants (`DATA_MODEL` §8.1) live as you type.

> **C-4 blocks saving.** If any anchor keyword also appears in a contradictory clue, save is disabled and the conflicting term is named with one-click fixes. **This is the 14 %-sensitivity bug made structurally impossible.**

Other invariants warn but do not block, except C-5/C-6/C-7 which block publication rather than saving — a draft may legitimately be incomplete.

| State | Behaviour |
|---|---|
| Draft, valid | Save enabled |
| **Draft, C-4 violated** | **Save disabled**, conflict panel visible |
| Editing a published version | Banner: "Published content is read-only. Saving creates draft v3." |
| Unsaved changes | Navigation guard |
| Concurrent edit | "This version was changed by {name} 2 minutes ago. `[ Reload ]`" |

---

## 12.5 A-04 · Playtest ⭐

**Route** `/admin/cases/{id}/versions/{v}/playtest` — **the highest-value screen in the console.**

```
┌────────────────────────────────┬─────────────────────────────────────────┐
│  STUDENT VIEW                  │  INSTRUMENTATION                        │
│                                │                                         │
│  ┌──────────────────────────┐  │  Question 2                             │
│  │ I've had this chest pain │  │  ─────────────────────────────────────  │
│  │ for three days now…      │  │  Matched topics                         │
│  └──────────────────────────┘  │   ✓ pain_character   (keyword "burning")│
│                                │                                         │
│      ┌───────────────────────┐ │  Counters                               │
│      │ Is the pain burning?  │ │   q=2   a=0   m=1   c=2/8 (25%)         │
│      └───────────────────────┘ │                                         │
│                                │  Detectors (live)                       │
│  ┌──────────────────────────┐  │   Anchoring       ✗   0.00   —          │
│  │ Burning, mostly. Worse   │  │   Premature       ✓   0.75   P2         │
│  │ after dinner.            │  │   Confirmation    ✗   0.00   —          │
│  └──────────────────────────┘  │                                         │
│                                │  Clues explored  2 / 6                  │
│  [ Ask a question…    ] [→]    │   ✓ burning   ✓ after meal              │
│                                │   ○ ibuprofen ○ antacid ○ lying ○ reflux│
│  [ Examine ▾ ] [ Test ▾ ]      │                                         │
│  [ Give diagnosis ]            │  ⚠ LEAKAGE — reply mentioned "after     │
│                                │     dinner" (meal_relationship) but the │
│  [ ⟲ Reset ]                   │     question did not ask about meals.   │
└────────────────────────────────┴─────────────────────────────────────────┘
```

### What the instrumentation must show

| Panel | Contents |
|---|---|
| Matched topics | Per question, with **why** — which keyword, or which similarity score |
| Counters | Live `q`, `a`, `m`, `c`, `k/K` |
| Detectors | Flag, score, and **which rule fired** (A1/A2/P1/P2/C1/C2) |
| Clues | Which explored, which not |
| **Leakage** | Amber warning when a reply reveals a required topic the question did not ask about |

**This is how a clinician sees *why* a detector fired without reading Python.** It is also where persona leakage is caught during authoring rather than after data collection.

| Rule | Detail |
|---|---|
| Ephemeral | Playtest sessions never appear in user data, analytics, or research export |
| Cost | LLM calls are tagged `purpose=playtest` and excluded from cost-per-session |
| Reset | Clears without leaving the page |
| Draft versions | Playtestable — that is the point |

---

## 12.6 A-05 · Review queue

**Route** `/admin/reviews`

```
┌──────────────────────────────────────────────────────────────────┐
│  Clinical review                                                 │
│  Assigned to me (2)   ·   All pending (3)   ·   Completed        │
├──────────────────────────────────────────────────────────────────┤
│  The Confused Elderly Man · v1        assigned 2 days ago        │
│  UTI/delirium · trap: stroke                    [ Open in Playtest ]│
├──────────────────────────────────────────────────────────────────┤
│  The Tired Teacher · v2               assigned 5 hours ago       │
│  Hypothyroidism · trap: depression              [ Open in Playtest ]│
└──────────────────────────────────────────────────────────────────┘
```

### Review form — presented alongside Playtest, not instead of it

```
┌────────────────────────────────────────────────┐
│  Clinical review · The Confused Elderly Man v1 │
│                                                │
│  Clinical plausibility        ○1 ○2 ○3 ○4 ●5   │
│  Internal consistency         ○1 ○2 ○3 ●4 ○5   │
│  Trap validity                ○1 ○2 ○3 ○4 ●5   │
│  Solvability from the info    ○1 ○2 ○3 ●4 ○5   │
│                                                │
│  Comments                                      │
│  ┌──────────────────────────────────────────┐ │
│  └──────────────────────────────────────────┘ │
│                                                │
│  [ Request changes ]  [ Reject ]  [ Approve ]  │
└────────────────────────────────────────────────┘
```

| Rule | Detail |
|---|---|
| **Any dimension < 4 disables Approve** | With an inline note naming which (`DATA_MODEL` §8.4) |
| Request changes | Requires a comment |
| Reject | Requires a comment |
| Reviewer ≠ author | Warned but not blocked — two-person teams sometimes must |
| Approve | Records the review; publication becomes possible |

**A structured rubric rather than a free-text box** — it makes review consistent between two reviewers and produces data you can report.

---

## 12.7 A-06 · Clinical content

**Route** `/admin/content/examinations` · `/admin/content/investigations`

```
┌───────────────────────────────────────────────────────────────────────┐
│  Investigations (86)                              [ + Add ]           │
│  Group [All ▾]   Active [All ▾]   🔍                                  │
├──────────┬──────────────────────┬───────────────┬────────┬───────────┤
│ Key      │ Label                │ Group         │ Active │ Used by   │
├──────────┼──────────────────────┼───────────────┼────────┼───────────┤
│ ecg      │ ECG (12-lead)        │ Cardiac       │  ✓     │ 4 cases   │
│ d_dimer  │ D-dimer              │ Vascular      │  ✓     │ 2 cases   │
│ ct_head  │ CT Head (non-contrast)│ Imaging      │  ✓     │ 0 cases   │
└──────────┴──────────────────────┴───────────────┴────────┴───────────┘
```

### Adding an item — the warning that matters

```
┌────────────────────────────────────────────────────────────┐
│  Add investigation                                         │
│                                                            │
│  Key         [ troponin_hs                              ]  │
│  Label       [ High-sensitivity Troponin                ]  │
│  Group       [ Cardiac ▾                                ]  │
│  Normal      [ < 14 ng/L                                ]  │
│  Reference   [ 0–14 ng/L                                ]  │
│                                                            │
│  ⚠ This appears on every case immediately.                 │
│    All 10 existing cases will return the normal result.    │
│    If it is obviously relevant to one case, it may hint    │
│    at that diagnosis.                                      │
│                                                            │
│                     [ Cancel ]   [ Add investigation ]     │
└────────────────────────────────────────────────────────────┘
```

The universal menu's entire purpose is that it is identical across cases (`PRD` FR-6.1). Adding an obviously case-specific test leaks that case's diagnosis — the warning states this plainly.

| Rule | Detail |
|---|---|
| `key` immutable once used | Keys appear inside stored session events |
| **Delete is not offered** | Only `is_active = false` (`DATA_MODEL` §5.3) |
| Deactivating a used item | Confirm: "Removes it from the menu. {n} cases reference it; their stored results are unaffected." |
| Editing `normal_result` | Affects future sessions only; historical results are stored per session |

---

## 12.8 A-07 · Topic lexicon

**Route** `/admin/content/lexicon`

```
┌───────────────────────────────────────────────────────────────────────┐
│  Topic lexicon      40 topics · 523 phrases                           │
├──────────────────────┬────────────────────────────────────────────────┤
│ pain_character   14  │  meal_relationship            12 phrases        │
│ meal_relationship 12 │  ────────────────────────────────────────────  │
│ radiation        11  │  after eating ✕   meals ✕   spicy ✕            │
│ medications      13  │  coffee ✕   after food ✕   empty stomach ✕     │
│ family_history    9  │  + add phrase                                  │
│ …                    │                                                │
│                      │  ⚠ 2 phrases have never matched in 90 days:    │
│                      │    "fasting", "trigger food"      [ Review ]   │
│                      │                                                │
│                      │  ── Test a question ─────────────────────────  │
│                      │  ┌──────────────────────────────────────────┐ │
│                      │  │ does a rich evening dinner set it off?   │ │
│                      │  └──────────────────────────────────────────┘ │
│                      │                          [ Test ]              │
│                      │                                                │
│                      │  Keyword matches:   none                       │
│                      │  Result:            NOT COVERED                │
│                      │  → No phrase in this topic matches. Consider   │
│                      │    adding "dinner" or "evening meal".          │
└──────────────────────┴────────────────────────────────────────────────┘
```

**The match tester is the feature that makes this screen worth building.** It answers "why didn't the system recognise that question?" for someone who cannot read the matcher — and it is how the lexicon gets improved by people who understand clinical phrasing.

Once embeddings ship (`ADR-0013`), the tester additionally shows the similarity score and whether it cleared the threshold.

**Dead phrases** (no match in 90 days) are surfaced, not auto-removed. A phrase may be rare but correct.

---

## 12.9 A-08 · AI operations

**Route** `/admin/ai`

### Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│  AI operations                            [ Today ▾ ]                 │
│                                                                       │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐            │
│  │  $1.84    │ │  $0.016   │ │   2.1s    │ │   1.2%    │            │
│  │ spend     │ │ per       │ │ p95       │ │ fallback  │            │
│  │ today     │ │ session   │ │ latency   │ │ rate      │            │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘            │
│                                                                       │
│  Monthly budget  ████████████░░░░░░░░  62% of $120                    │
│                                                                       │
│  By purpose                                                           │
│  patient    1,284 calls   $1.31   p95 2.1s   0 errors                 │
│  feedback     118 calls   $0.53   p95 3.4s   2 fallback               │
└───────────────────────────────────────────────────────────────────────┘
```

**Cost per completed session is the headline number** — it is the unit economic that decides whether the business works (`PRD` §10.3, NFR-7).

Budget behaviour: alert at 80 %, automatic degradation to the cheapest model at 100 % (`TECH_SPEC` §5.1). Degradation is shown here as an amber banner so it is never silent.

### Leakage queue

```
┌───────────────────────────────────────────────────────────────────────┐
│  Leakage flags          2 unreviewed                                  │
├───────────────────────────────────────────────────────────────────────┤
│  ⚠ HIGH   Chest Pain Trap · 22 Aug 14:31                              │
│  Question:  "How long has this been going on?"                        │
│  Reply:     "About three days. It's worse after meals, and the        │
│              ibuprofen I take for my back doesn't help."              │
│  Leaked:    meal_relationship, medications  (neither was asked)        │
│                                                                       │
│  [ Confirm leak ]   [ Not a leak ]   [ Open conversation ]            │
└───────────────────────────────────────────────────────────────────────┘
```

| Action | Effect |
|---|---|
| **Confirm** | Session excluded from research export (`DATA_MODEL` §11.7); counts against the case's persona quality |
| Not a leak | Dismissed; feeds the false-positive rate of the detector |

**This queue is the operational face of the project's largest measurement risk** (`TECH_SPEC` §5.3).

### Conversation sampler

Browse real consultations with filters: case, date, model, flagged, user-reported. Sampling policy (`PLATFORM_SPEC` §4.5): 100 % of reported and flagged, ~1 % random, 100 % of the first 50 after any prompt change.

**Opening a conversation writes to `audit_log`.** Admins reading learner transcripts is a privileged action, not a casual one.

---

## 12.10 A-09 · Users and support

**Route** `/admin/users`

```
┌───────────────────────────────────────────────────────────────────────┐
│  Users                                              🔍 email or code  │
│  Tier [All ▾]  Role [All ▾]  Active [30 days ▾]                       │
├──────────────┬──────────┬───────┬──────────┬──────────┬──────────────┤
│ Code         │ Tier     │ Role  │ Sessions │ Last seen│              │
├──────────────┼──────────┼───────┼──────────┼──────────┼──────────────┤
│ U4B7C21E9AF  │ pro      │ med   │    24    │ 2h ago   │ [ View ]     │
│ U9A1D45C0B2  │ free     │ intern│     3    │ 5d ago   │ [ View ]     │
└──────────────┴──────────┴───────┴──────────┴──────────┴──────────────┘
```

**The directory shows `research_pid`, not email, by default.** Email is revealed only on the detail screen, and only for a stated support reason. Habituating admins to browsing a list of email addresses is how casual snooping starts.

### Support access — bounded by design

Viewing a user's sessions opens a gate first:

```
┌────────────────────────────────────────────────────────────┐
│  Access user sessions                                      │
│                                                            │
│  Why do you need to see this?                              │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Support ticket #482 — user reports feedback showed   │ │
│  │ the wrong coverage figure                            │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  · Access expires in 24 hours                              │
│  · This is recorded in the audit log                       │
│  · The user can see that you accessed their sessions       │
│                                                            │
│                        [ Cancel ]   [ Grant access ]       │
└────────────────────────────────────────────────────────────┘
```

| Control | Rule |
|---|---|
| Reason | Mandatory free text, stored in `audit_log.reason` |
| Duration | 24 hours, then re-request |
| Visibility | Surfaced to the user in `/account/data` |
| **Impersonation** | **Not offered.** Admins view read-only data; they never act as a user |

Stricter than most early products, and the right default for professional performance data (`PLATFORM_SPEC` §4.7).

Also available here: grant a manual subscription (records `provider = 'manual'`), and trigger account deletion on request.

---

## 12.11 A-10 · System

**Route** `/admin/system`

| Panel | Contents |
|---|---|
| **Engine versions** | List with thresholds; current marked. `[ Preview change ]` opens the impact preview |
| **Threshold preview** | Candidate values → how many historical sessions change, plus the validation suite result and delta. Read-only until applied |
| **Validation** | `[ Run validation suite ]` — executes the 18 transcripts, shows the table |
| **Feature flags** | Toggle, rollout percentage |
| **Audit log** | Filterable by actor, action, entity, date |
| **Jobs** | Background job status: exports, expiry sweeps, progress rebuilds |

### Threshold impact preview

```
┌───────────────────────────────────────────────────────────────┐
│  Anchoring concentration threshold    0.60  →  [ 0.55 ]       │
│                                                               │
│  Impact on 1,284 historical sessions                          │
│    would newly flag        +117  (9.1%)                       │
│    would no longer flag       0                               │
│                                                               │
│  Validation suite under proposed values                       │
│    Anchoring         sens 100%   spec  94%   (was 100 / 100)  │
│    Premature         sens 100%   spec  88%   (unchanged)      │
│    Confirmation      sens 100%   spec  82%   (unchanged)      │
│    Overall accuracy  93%  ▼ 1pt from 94%                      │
│                                                               │
│  ⚠ This would drop overall accuracy below the 94% CI gate.    │
│                                                               │
│          [ Cancel ]      [ Apply — creates engine v1.4.0 ]    │
└───────────────────────────────────────────────────────────────┘
```

**Only possible because sessions can be replayed** (`ADR-0003`). This converts a threshold change from a guess into a measured decision — and it is the mechanism that finally closes the "thresholds not tuned with data" limitation from the research report.

---

# 13. Open UX questions

| # | Question | Recommendation |
|---|---|---|
| UX-1 | Should the patient card show vitals before examination? | **No** — vitals are an examination. Showing them free would leak information |
| UX-2 | Can users bookmark a case to retry? | Pro only, `PRD` §9.1. Needs a UI entry point in history |
| UX-3 | Does the tutor feedback need a "was this helpful?" control? | **Yes** — cheap, and the only signal on feedback quality. Two icons, no modal |
| UX-4 | Should coverage % be visible on the history list? | **Yes** — it is the metric users should learn to care about |
| UX-5 | Dark mode at launch? | **No.** Defer. Adds token and testing surface for low early value |
| UX-7 | Show active sessions / "sign out everywhere"? | Deferred. Good practice, low value until accounts are worth stealing |
| UX-8 | Admin dark mode? | No. Same reasoning as UX-5 |
| UX-6 | Illustration style for empty states? | Simple line icons in `--muted`. No character illustration — reads as consumer-app, clashes with U1 |

---

*End of UX Specification. `DATA_MODEL.md` is next.*
