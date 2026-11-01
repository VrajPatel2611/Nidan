# Nidan — API Contract

---

## Contents

**1. Document control**

&nbsp;&nbsp;&nbsp;&nbsp;1.1 The rule that matters most  
**2. Conventions**

&nbsp;&nbsp;&nbsp;&nbsp;2.1 Versioning  
&nbsp;&nbsp;&nbsp;&nbsp;2.2 Authentication  
&nbsp;&nbsp;&nbsp;&nbsp;2.3 Content type  
&nbsp;&nbsp;&nbsp;&nbsp;2.4 Timestamps and identifiers  
&nbsp;&nbsp;&nbsp;&nbsp;2.5 Pagination  
&nbsp;&nbsp;&nbsp;&nbsp;2.6 Error envelope  
&nbsp;&nbsp;&nbsp;&nbsp;2.7 Status codes  
&nbsp;&nbsp;&nbsp;&nbsp;2.8 Idempotency  
&nbsp;&nbsp;&nbsp;&nbsp;2.9 Rate limits  
&nbsp;&nbsp;&nbsp;&nbsp;2.10 CORS  
**3. Authentication flows**

&nbsp;&nbsp;&nbsp;&nbsp;3.1 Signup  
&nbsp;&nbsp;&nbsp;&nbsp;3.2 Trial → account  
&nbsp;&nbsp;&nbsp;&nbsp;3.3 Token refresh  
**4. Endpoints — identity**

**5. Endpoints — catalogue**

**6. Endpoints — consultation**

**7. Endpoints — history and progress**

**8. Endpoints — billing**

**9. Endpoints — admin**

**10. Error code catalogue**

**11. Contract tests**

**12. Client generation**

**13. Open questions**


---

---

# 1. Document control

| Field | Value |
|---|---|
| **Document** | Nidan API Contract |
| **Version** | v1.0 |
| **Base URL** | `https://api.nidan.app/v1` |
| **Machine-readable** | `openapi.yaml` — **the source of truth** |
| **Depends on** | `PRD.md` §6 · `DATA_MODEL.md` · `ADR-0002`, `ADR-0006`, `ADR-0007` |

## 1.1 The rule that matters most

> **`openapi.yaml` changes in the same commit as the endpoint.** This prose document explains intent; the YAML is what generates client types and what tests validate against. If they disagree, the YAML is correct and this document is stale.

TypeScript types for Next.js and React Native are generated from the YAML, so a drift between backend and frontend becomes a compile error rather than a runtime surprise.

---

# 2. Conventions

## 2.1 Versioning

Path-based: `/v1/...`. A breaking change means `/v2`, with `/v1` supported for at least 6 months.

**Breaking:** removing a field, renaming a field, narrowing a type, adding a required request field, changing status-code semantics.
**Non-breaking:** adding an optional request field, adding a response field, adding an endpoint, adding an enum value **to a response** (clients must tolerate unknown values).

## 2.2 Authentication

Supabase-issued JWT in the `Authorization` header (`ADR-0002`).

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

The backend verifies the signature against Supabase's JWKS (cached, 10-minute TTL), extracts `sub` as the user id, and loads the profile. **The backend never sees a password.**

| Auth level | Meaning |
|---|---|
| `public` | No token |
| `anonymous` | No token; `X-Anonymous-Id` cookie identifies a trial session |
| `user` | Valid JWT |
| `pro` | Valid JWT and `subscription_tier = 'pro'` |
| `admin` | Valid JWT and `role = 'admin'` |

## 2.3 Content type

`application/json; charset=utf-8` on request and response. `snake_case` field names throughout — matching the database, so no translation layer.

## 2.4 Timestamps and identifiers

ISO 8601 with timezone: `2026-08-22T14:31:07.482Z`. Always UTC.
Identifiers are UUID v4 strings. Sequence numbers are integers.

## 2.5 Pagination

Cursor-based on all collections. Offset pagination is not offered — it produces duplicates and gaps when rows are inserted mid-scroll.

```http
GET /v1/sessions?limit=20&cursor=eyJpZCI6IjlmM2E...
```

```jsonc
{
  "data": [ /* … */ ],
  "pagination": {
    "next_cursor": "eyJpZCI6ImE0YjJk…",   // null when exhausted
    "has_more": true
  }
}
```

`limit` defaults to 20, maximum 100.

## 2.6 Error envelope

Every 4xx and 5xx returns the same shape. No endpoint invents its own.

```jsonc
{
  "error": {
    "code": "session_already_concluded",
    "message": "This consultation has already been submitted.",
    "details": { "session_id": "9f3a…", "submitted_at": "2026-08-22T14:31:07Z" },
    "request_id": "req_01J8XQ2K7M"
  }
}
```

| Field | Purpose |
|---|---|
| `code` | Stable machine-readable identifier. **Never changes once shipped** |
| `message` | Human-readable, safe to display. Follows `UX_SPEC` §11 tone |
| `details` | Optional context. Never contains internal state or stack traces |
| `request_id` | Correlates with server logs. Shown to users on 500 (`UX_SPEC` S-21) |

**Clients branch on `code`, never on `message`.** Messages are copy and may be reworded or localised.

## 2.7 Status codes

| Code | Used when |
|---|---|
| 200 | Success with a body |
| 201 | Resource created |
| 204 | Success, no body |
| 400 | Malformed request |
| 401 | Missing or invalid token |
| 403 | Authenticated but not permitted (includes tier gating) |
| 404 | Not found, **or found but not yours** — see below |
| 409 | Conflict with current state |
| 422 | Well-formed but semantically invalid |
| 429 | Rate limited |
| 500 | Server error |
| 503 | Dependency unavailable (LLM provider down) |

**404 rather than 403 for another user's resource.** Returning 403 confirms the resource exists, which leaks information. Ownership failures are indistinguishable from non-existence.

## 2.8 Idempotency

Required on `POST /sessions/{id}/diagnosis` and honoured on all mutating endpoints.

```http
Idempotency-Key: 8f14e45f-ea4c-4b0e-9d3a-2b1c7f0d5e6a
```

Behaviour: first request executes and the response is stored for 24 h. A repeat with the same key and the same body replays the stored response. A repeat with the same key and a **different** body returns `422 idempotency_key_reused`.

## 2.9 Rate limits

| Scope | Limit | Header |
|---|---|---|
| Questions per session | 40 total | — |
| Questions per user | 60 / hour | `X-RateLimit-*` |
| Sessions started per user | 20 / day | `X-RateLimit-*` |
| Login attempts | 5 / 15 min per email; 20 / hour per IP | — |
| Anonymous trial | 1 per browser | — |
| Admin ingestion runs | 5 / day | — |

429 responses carry `Retry-After` in seconds.

## 2.10 CORS

Allowed origins: the web app, and the mobile app scheme. Credentials permitted for the anonymous-trial cookie only.

---

# 3. Authentication flows

Supabase handles credentials. Our API handles profile lifecycle.

## 3.1 Signup

```
Client                    Supabase                 Nidan API
  │─ signUp(email,pw) ──────► │                        │
  │ ◄──── JWT + user.id ───── │                        │
  │                                                    │
  │─ POST /v1/me  (Bearer JWT) ───────────────────────►│  creates profiles row
  │ ◄──────────────── 201 Profile ────────────────────│
```

The profile row is created by our API, not by a Supabase trigger — creation needs `research_pid` generation, timezone capture, and optional trial claiming, which belong in application code.

## 3.2 Trial → account

```
POST /v1/trial/sessions          → anonymous session, sets X-Anonymous-Id cookie
  … consultation …
POST /v1/me  { anonymous_id }    → creates profile AND claims the trial session
```

Claim window is 30 days (`PRD` FR-2.4).

## 3.3 Token refresh

Handled client-side by the Supabase SDK. Our API only ever validates. A 401 with `code: "token_expired"` instructs the client to refresh and retry once.

---

# 4. Endpoints — identity

## `POST /v1/me`
Create the profile after Supabase signup. **Idempotent** — returns the existing profile if already created.

**Auth:** `user`

```jsonc
// Request
{
  "display_name": "Aarav",            // optional
  "professional_role": "medical_student",
  "year_of_training": 4,
  "country": "IN",
  "timezone": "Asia/Kolkata",
  "anonymous_id": "anon_8f14e45f"     // optional, claims a trial session
}
```

```jsonc
// 201
{
  "id": "9f3a…",
  "display_name": "Aarav",
  "professional_role": "medical_student",
  "year_of_training": 4,
  "country": "IN",
  "timezone": "Asia/Kolkata",
  "subscription_tier": "free",
  "subscription_ends": null,
  "onboarded_at": "2026-08-22T14:31:07Z",
  "consent_research": false,
  "claimed_trial_session_id": "3c2d…",   // null if none
  "created_at": "2026-08-22T14:31:07Z"
}
```

| Status | Code | When |
|---|---|---|
| 200 | — | Profile already exists |
| 422 | `invalid_timezone` | Not a recognised IANA zone |
| 422 | `trial_expired` | Anonymous session older than 30 days |

---

## `GET /v1/me`
**Auth:** `user`

Returns the profile plus derived allowance — the dashboard needs both and one round trip is better than two.

```jsonc
{
  "id": "9f3a…",
  "display_name": "Aarav",
  "professional_role": "medical_student",
  "year_of_training": 4,
  "timezone": "Asia/Kolkata",
  "subscription_tier": "free",
  "subscription_ends": null,
  "consent_research": false,
  "allowance": {
    "cases_used_this_month": 2,
    "cases_limit": 3,                 // null when unlimited
    "resets_at": "2026-09-01T00:00:00Z"
  },
  "active_session_id": "7b1e…"        // null if none in progress
}
```

`active_session_id` drives the "resume" banner in `UX_SPEC` S-08.

---

## `PATCH /v1/me`
**Auth:** `user` · Fields: `display_name`, `professional_role`, `year_of_training`, `country`, `timezone`, `consent_research`

Setting `consent_research: true` requires `consent_version`; the server records `consent_at`.

| Status | Code |
|---|---|
| 422 | `consent_version_required` |

---

## `POST /v1/me/export`
**Auth:** `user` → `202 Accepted`. Generates a JSON export, emailed within 24 h (`PRD` FR-11.3).

```jsonc
{ "status": "queued", "estimated_ready_at": "2026-08-23T14:31:07Z" }
```

## `DELETE /v1/me`
**Auth:** `user` · Requires `{ "confirmation": "DELETE" }` → `204`.

Executes §10.2 of `DATA_MODEL`. Irreversible.

| Status | Code |
|---|---|
| 422 | `confirmation_required` |

---

# 5. Endpoints — catalogue

## `GET /v1/catalog/examinations`
## `GET /v1/catalog/investigations`

**Auth:** `anonymous` or `user` · Cacheable, `Cache-Control: public, max-age=3600`

```jsonc
{
  "data": [
    { "key": "vitals", "label": "Vital Signs", "group": "General & Vitals", "display_order": 2 },
    { "key": "cardiovascular", "label": "Cardiovascular Examination", "group": "Cardiovascular", "display_order": 5 }
  ]
}
```

> ⚠️ **The response must never include `category`, `is_key`, or any case-specific field.** These are the universal menus (`PRD` FR-5.1, FR-6.1); leaking relevance here would defeat the entire design. An automated test asserts the response schema contains no such field.

---

# 6. Endpoints — consultation

## `POST /v1/sessions`
Start a case. The server selects it (`PRD` FR-3).

**Auth:** `user`

```jsonc
// Request
{ "confidence_pre": 3 }     // optional, 1–5
```

```jsonc
// 201
{
  "session_id": "7b1e…",
  "sequence_index": 5,
  "status": "active",
  "started_at": "2026-08-22T14:31:07Z",
  "case": {
    "title": "The Chest Pain Trap",
    "patient": {
      "name": "Ramesh Kumar",
      "age": 48,
      "sex": "male",
      "presenting_complaint": "Chest pain for 3 days",
      "intro": "Ramesh is a 48-year-old accountant who…"
    },
    "opening_line": "I've had this chest pain for about three days now…"
  }
}
```

> ⚠️ **Critical constraint (`PRD` FR-3.4).** The `case` object contains **only** presentation fields. It must not contain `correct_diagnosis`, `anchor_topic`, `anchor_keywords`, `required_topics`, `contradictory_clues`, `investigations`, `examination`, or `system_prompt`. A contract test asserts the serialised response contains none of these keys.

| Status | Code | When |
|---|---|---|
| 403 | `monthly_limit_reached` | Free tier exhausted. `details` carries `resets_at` |
| 409 | `session_already_active` | An unfinished session exists. `details` carries `session_id` |
| 503 | `no_cases_available` | No published cases — alerts admin |

---

## `POST /v1/trial/sessions`
Anonymous equivalent. **Auth:** `public` · Sets an `httpOnly` `X-Anonymous-Id` cookie. Same response shape.

| Status | Code |
|---|---|
| 409 | `trial_already_used` |

---

## `GET /v1/sessions/{id}`
Full state, for resuming (`PRD` FR-4).

**Auth:** `user` or `anonymous` (owner only)

```jsonc
{
  "session_id": "7b1e…",
  "status": "active",
  "started_at": "2026-08-22T14:31:07Z",
  "last_activity_at": "2026-08-22T14:48:12Z",
  "case": { /* as above */ },
  "transcript": [
    { "seq": 1, "type": "question",      "text": "Is the pain burning or crushing?", "at": "…" },
    { "seq": 2, "type": "patient_reply", "text": "Burning, mostly.",                 "at": "…" }
  ],
  "examinations_done": [
    { "key": "vitals", "label": "Vital Signs", "finding": "HR 78, BP 132/84…", "at": "…" }
  ],
  "investigations_done": [
    { "key": "ecg", "label": "ECG (12-lead)", "result": "Normal sinus rhythm…", "at": "…" }
  ],
  "questions_remaining": 34
}
```

**`questions_remaining` is included deliberately** — it is a hard cap, not a progress metric, and the UI surfaces it only when it approaches zero (`UX_SPEC` S-10). It is not a coverage indicator and does not violate U2.

---

## `POST /v1/sessions/{id}/questions`
Ask the patient. **The highest-volume endpoint.**

**Auth:** owner · **Idempotency:** recommended

```jsonc
// Request
{ "text": "Does the pain get worse after meals?" }
```

```jsonc
// 201
{
  "seq": 7,
  "question": { "text": "Does the pain get worse after meals?", "at": "…" },
  "reply":    { "text": "Yes, especially after dinner.",        "at": "…" },
  "questions_remaining": 33
}
```

> ⚠️ The response **must not** include `matched_topics`, coverage, or any assessment state (`PRD` FR-4.7, U2). Those are computed and stored server-side but never returned during a consultation.

| Status | Code | When |
|---|---|---|
| 409 | `session_concluded` | Already submitted |
| 422 | `question_too_long` | > 500 characters |
| 422 | `patient_data_detected` | Real-patient-data guard fired. **Question is not consumed** |
| 429 | `question_limit_reached` | 40-question cap |
| 503 | `patient_unavailable` | LLM failed after retries. **Question is not consumed** — client retries with the same text |

**`patient_unavailable` must not consume the question.** `UX_SPEC` S-10 requires the typed text be preserved and retryable; consuming it on failure would lose the user's work.

---

## `POST /v1/sessions/{id}/examinations`
## `POST /v1/sessions/{id}/investigations`

**Auth:** owner

```jsonc
// Request
{ "key": "ecg" }
```

```jsonc
// 201
{
  "key": "ecg",
  "label": "ECG (12-lead)",
  "result": "Normal sinus rhythm, rate 78. No ST elevation…",
  "at": "2026-08-22T14:52:03Z",
  "already_ordered": false
}
```

`already_ordered: true` returns the stored result without creating a duplicate event (`PRD` FR-5.3, FR-6.3).

> ⚠️ Response must not include `category` or `is_key` (`PRD` FR-6.6).

| Status | Code |
|---|---|
| 404 | `unknown_key` |
| 409 | `session_concluded` |

---

## `POST /v1/sessions/{id}/diagnosis`
Conclude the consultation. **Irreversible.**

**Auth:** owner · **Idempotency: required**

```jsonc
// Request
{ "text": "GERD, likely NSAID-induced" }
```

```jsonc
// 201
{ "session_id": "7b1e…", "status": "completed", "feedback_ready": true }
```

`feedback_ready: false` means assessment succeeded but LLM feedback is still generating; the client polls `GET /feedback` (`UX_SPEC` S-12).

| Status | Code |
|---|---|
| 409 | `session_already_concluded` — returns `details.submitted_at` |
| 422 | `diagnosis_empty` |
| 422 | `diagnosis_too_long` — > 200 characters |
| 422 | `idempotency_key_reused` |

**Zero questions is permitted** (`PRD` FR-7 edge cases). Assessment runs and flags premature closure.

---

## `GET /v1/sessions/{id}/feedback`
**Auth:** owner

```jsonc
{
  "session_id": "7b1e…",
  "diagnosis_submitted": "GERD, likely NSAID-induced",
  "verdict": "correct",

  "summary": {
    "question_count": 8,
    "examination_count": 3,
    "investigation_count": 4,
    "coverage_pct": 75.0,
    "duration_seconds": 1140
  },

  "tutor_feedback": {
    "lines": [
      "Correct, and your history got you there safely.",
      "You didn't examine the abdomen — what were you expecting to find?"
    ],
    "generator": "llm"
  },

  "coverage": {
    "topics_hit":    [ { "key": "pain_character",    "label": "Pain character" } ],
    "topics_missed": [ { "key": "family_history",    "label": "Family history" } ]
  },

  "examination_scorecard": {
    "key_done":   ["Vital Signs", "Cardiovascular Examination"],
    "key_missed": ["Abdominal Examination"],
    "relevant_done": ["General Inspection"],
    "extra_done": []
  },
  "investigation_scorecard": {
    "key_done": ["ECG (12-lead)"], "key_missed": ["OGD (Gastroscopy)"],
    "reasonable_done": ["Full Blood Count"], "low_value_done": ["CT Coronary Angiogram"],
    "extra_done": []
  },

  "reasoning": [
    {
      "id": "diagnostic_focus",
      "label": "Diagnostic focus",
      "flagged": true,
      "status_line": "consider broadening",
      "reason": "6 of your 8 questions explored a cardiac cause. You asked 1 question about other possibilities."
    },
    {
      "id": "history_completeness",
      "label": "History completeness",
      "flagged": false,
      "status_line": null,
      "reason": "You covered 6 of 8 key areas before concluding."
    }
  ],

  "answer": {
    "correct_diagnosis": "GERD (Gastro-oesophageal Reflux Disease), NSAID-induced",
    "trap_explanation": "Chest pain in a 48-year-old man reasonably prompts a cardiac workup…"
  }
}
```

**Three contract points:**

1. `reasoning[].id` uses **behavioural identifiers** — `diagnostic_focus`, `history_completeness`, `evidence_exploration` — never `anchoring`, `premature_closure`, `confirmation_bias` (`PRD` P1, `UX_SPEC` U4). The internal names never cross the API boundary.
2. `reasoning[].reason` is always present and always cites the user's own actions (`PRD` P3).
3. `answer` is included in the payload but the UI keeps it collapsed until requested (`PRD` FR-8.8).

| Status | Code |
|---|---|
| 404 | `feedback_not_ready` — retry after `details.retry_after_ms` |
| 409 | `session_not_concluded` |

---

## `POST /v1/sessions/{id}/feedback/rating`
**Auth:** owner · `{ "was_helpful": true }` → `204`. Implements `UX_SPEC` UX-3.

## `POST /v1/sessions/{id}/abandon`
**Auth:** owner → `204`. Sets status `abandoned`. **Still counts toward the monthly allowance** (`PRD` FR-3 edge cases).

---

# 7. Endpoints — history and progress

## `GET /v1/sessions`
**Auth:** `user` · Paginated, newest first.

```jsonc
{
  "data": [
    {
      "session_id": "7b1e…",
      "case_title": "The Chest Pain Trap",
      "status": "completed",
      "verdict": "correct",
      "coverage_pct": 75.0,
      "started_at": "…", "ended_at": "…"
    }
  ],
  "pagination": { "next_cursor": null, "has_more": false }
}
```

## `GET /v1/progress`
**Auth:** `user`

```jsonc
{
  "sessions_completed": 12,
  "current_streak_days": 4,
  "longest_streak_days": 9,
  "mean_coverage_last10": 71.4,
  "has_sufficient_data": true,          // false when < 3 sessions
  "coverage_series": [
    { "session_index": 3, "coverage_pct": 37.5, "at": "…" },
    { "session_index": 4, "coverage_pct": 62.5, "at": "…" }
  ],
  "reasoning_trends": [
    { "id": "diagnostic_focus", "label": "Diagnostic focus",
      "last10_rate": 0.2, "prev10_rate": 0.5, "direction": "improving" }
  ],
  "verdict_distribution": { "correct": 7, "partial": 3, "anchored": 2, "other": 0 }
}
```

`has_sufficient_data: false` drives the empty state in `UX_SPEC` S-16. `direction` is server-computed so wording stays consistent.

---

# 8. Endpoints — billing

## `POST /v1/billing/checkout`
**Auth:** `user`

```jsonc
// Request
{ "interval": "month", "success_url": "…", "cancel_url": "…" }
```
```jsonc
// 201
{ "checkout_url": "https://checkout.stripe.com/…", "session_id": "cs_test_…" }
```

Pricing and currency are resolved **server-side** from the user's country (`PRD` §9.4). The client never sends a price.

## `POST /v1/billing/portal`
**Auth:** `pro` → `{ "portal_url": "…" }` — Stripe customer portal for cancellation and payment updates.

## `POST /v1/webhooks/stripe`
**Auth:** `public`, verified by Stripe signature.

| Event | Action |
|---|---|
| `checkout.session.completed` | Create subscription, set tier `pro` |
| `customer.subscription.updated` | Sync status and period end |
| `customer.subscription.deleted` | Set tier `free` at period end |
| `invoice.payment_failed` | Status `past_due`, set 7-day `grace_until` |
| `charge.dispute.created` | Cancel subscription, alert admin |

**Idempotent by Stripe event id** (`DATA_MODEL` §7.3). Always returns 200 once persisted — a non-200 causes Stripe to retry, and a retry storm is worse than a delayed reconciliation. Signature failures return 400.

---

# 9. Endpoints — admin

All require `admin`. All write to `audit_log`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/admin/cases` | Bank browser; filters `status`, `origin`, `review_state` |
| `POST` | `/v1/admin/cases` | Create a case shell |
| `POST` | `/v1/admin/cases/{id}/versions` | New draft version |
| `PATCH` | `/v1/admin/case-versions/{id}` | Edit a draft. **422 on C-4 overlap violation** |
| `POST` | `/v1/admin/case-versions/{id}/validate` | Run all invariants, return violations |
| `POST` | `/v1/admin/case-versions/{id}/playtest` | Ephemeral session with instrumentation |
| `POST` | `/v1/admin/case-versions/{id}/reviews` | Record a clinical review |
| `POST` | `/v1/admin/case-versions/{id}/publish` | Publish. **409 if no approving review** |
| `POST` | `/v1/admin/case-versions/{id}/retire` | Retire |
| `GET`/`POST`/`PATCH` | `/v1/admin/examinations` | Master list CRUD. **Delete not offered** |
| `GET`/`POST`/`PATCH` | `/v1/admin/investigations` | Same |
| `GET`/`POST`/`PATCH`/`DELETE` | `/v1/admin/lexicon/topics`, `/phrases` | Lexicon |
| `POST` | `/v1/admin/lexicon/test` | Match tester — `{text}` → matched topics + scores |
| `GET` | `/v1/admin/ai/usage` | Cost, tokens, latency, errors |
| `GET` | `/v1/admin/ai/conversations` | Sampled transcripts |
| `GET`/`PATCH` | `/v1/admin/leakage` | Leakage queue; confirm or dismiss |
| `GET` | `/v1/admin/engine-versions` | List |
| `POST` | `/v1/admin/engine-versions/preview` | **Threshold impact preview** |
| `GET` | `/v1/admin/users` | Directory |
| `GET` | `/v1/admin/users/{id}/sessions` | **Requires `reason` query param**; time-boxed; audited |

## Threshold impact preview

The endpoint that makes calibration a measured decision rather than a guess.

```jsonc
// POST /v1/admin/engine-versions/preview
{ "thresholds": { "anchoring": { "concentration": 0.55 } } }
```
```jsonc
// 200
{
  "sessions_evaluated": 1284,
  "changes": {
    "anchoring": { "newly_flagged": 117, "no_longer_flagged": 0, "pct_change": 9.1 }
  },
  "validation_suite": {
    "anchoring":         { "sensitivity": 1.0, "specificity": 0.94 },
    "premature_closure": { "sensitivity": 1.0, "specificity": 0.88 },
    "confirmation_bias": { "sensitivity": 1.0, "specificity": 0.82 },
    "overall_accuracy": 0.93,
    "delta_from_current": -0.01
  }
}
```

Read-only. Applying creates a new `engine_versions` row.

---

# 10. Error code catalogue

Stable identifiers. **Once shipped, a code is never renamed or repurposed.**

**This table is checked against the code.** `nidan/api/errors.py` holds the same mapping as data and `tests/test_api_contract.py` fails if this table, that mapping and the `openapi.yaml` enum ever disagree. Two codes were missing when the check was first written, on 1 November 2026: `service_unavailable`, which was in the enum and being returned by `require_auth` but absent from this table, and `not_implemented`, which was in neither despite being declared on every unbuilt operation. A catalogue that lives in three places and is compared in none is three catalogues.

| Code | Status | Meaning |
|---|---|---|
| `unauthenticated` | 401 | Missing or malformed token |
| `token_expired` | 401 | Refresh and retry once |
| `forbidden` | 403 | Authenticated, not permitted |
| `pro_required` | 403 | Feature requires Pro |
| `monthly_limit_reached` | 403 | Free allowance exhausted |
| `not_found` | 404 | Absent, or not yours |
| `feedback_not_ready` | 404 | Still generating; retry |
| `session_already_active` | 409 | Unfinished session exists |
| `session_concluded` | 409 | Already submitted |
| `session_not_concluded` | 409 | Feedback requested too early |
| `trial_already_used` | 409 | One trial per browser |
| `no_approving_review` | 409 | Publish blocked (FR-12.5) |
| `validation_failed` | 422 | Generic; `details` lists fields |
| `question_too_long` | 422 | > 500 chars |
| `diagnosis_empty` | 422 | Empty diagnosis |
| `diagnosis_too_long` | 422 | > 200 chars |
| `patient_data_detected` | 422 | Real-patient-data guard |
| `keyword_overlap` | 422 | Case invariant C-4 |
| `idempotency_key_reused` | 422 | Same key, different body |
| `confirmation_required` | 422 | Deletion confirmation missing |
| `invalid_timezone` | 422 | Not an IANA zone |
| `consent_version_required` | 422 | `consent_research: true` without `consent_version` (§4 `PATCH /v1/me`) |
| `trial_expired` | 422 | Claim window passed |
| `unknown_key` | 404 | Unknown examination/investigation |
| `question_limit_reached` | 429 | 40-question cap |
| `rate_limited` | 429 | Generic; see `Retry-After` |
| `patient_unavailable` | 503 | LLM failed; question preserved |
| `no_cases_available` | 503 | Empty published bank |
| `internal_error` | 500 | Unexpected; `request_id` for support |
| `not_implemented` | 501 | Declared in `openapi.yaml`, not built yet (sync point S-1) |
| `service_unavailable` | 503 | An auth dependency is down — **not** 401; the token may be fine and we cannot check it |

---

# 11. Contract tests

Beyond ordinary endpoint tests, these enforce constraints that no compiler can:

| # | Test | Guards |
|---|---|---|
| CT-1 | `POST /sessions` response contains none of: `correct_diagnosis`, `anchor_keywords`, `required_topics`, `contradictory_clues`, `system_prompt`, `investigations`, `examination` | FR-3.4 — the leak that would invalidate everything |
| CT-2 | `POST /questions` response contains no `matched_topics`, `coverage`, or bias field | FR-4.7, U2 |
| CT-3 | Catalogue responses contain no `category` or `is_key` | FR-6.6 |
| CT-4 | Feedback `reasoning[].id` ∈ {`diagnostic_focus`,`history_completeness`,`evidence_exploration`} | P1, U4 |
| CT-5 | No response body anywhere contains "anchoring", "premature closure", "confirmation bias" | P1 |
| CT-6 | Every error response validates against the envelope schema | §2.6 |
| CT-7 | Every 4xx/5xx `code` appears in the §10 catalogue | Prevents undocumented codes |
| CT-8 | Duplicate `Idempotency-Key` with the same body returns the identical response | §2.8 |
| CT-9 | Requesting another user's session returns 404, never 403 | §2.7 |

**CT-1 and CT-5 are the most important tests in the codebase.** CT-1 protects the measurement; CT-5 protects the learner.

---

# 12. Client generation

```bash
npx openapi-typescript openapi.yaml -o packages/api-types/src/schema.d.ts
```

Web and mobile share one generated types package. A backend field rename becomes a TypeScript error at build time rather than an `undefined` at runtime.

CI fails if `openapi.yaml` changes without the generated types being regenerated.

---

# 13. Open questions

| # | Question | Recommendation |
|---|---|---|
| API-1 | Stream patient replies token-by-token (SSE)? | **Not in v1.** Adds complexity to client, error handling and event logging. Revisit if p95 latency stays above 5 s |
| API-2 | Expose a public API for third parties? | No. `ADR-0015` — no partner demand yet |
| API-3 | GraphQL alongside REST? | No. One client shape, known queries |
| API-4 | Version the admin API separately? | No. Internal; ship breaking changes with the console |
| API-5 | Return partial feedback while the LLM generates? | **No.** Partial Socratic feedback reads as broken. Poll instead |
| API-6 | Does `questions_remaining` belong on the session response? | **⟨DECIDE⟩ — the spec contradicts itself, raised 2026-11-01 in T-030 slice 2b.** §6 says it is "included deliberately — a hard cap, not a progress metric… not a coverage indicator and does not violate U2". `tests/test_openapi.py::test_the_session_schema_exposes_no_assessment_state` names the field in its forbidden set, under `PRD` P2 and CT-1/CT-2, so someone considered this exact field and decided the other way. `CLAUDE.md` reads the same way about the monthly allowance: "Never show the remaining allowance during a consultation either… a visible counter teaches the counter." **Implemented as absent**, because omitting a field is one line to reverse and a U2 violation a client has started rendering is not. Settle before T-034 builds the consultation screen, which is where `UX_SPEC` S-10 wants to surface the cap as it approaches zero |

---

*End of API Contract. `openapi.yaml` is the machine-readable source of truth.*
