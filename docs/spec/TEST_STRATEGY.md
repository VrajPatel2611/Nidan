# Test strategy

| | |
|---|---|
| **Status** | Living document — updated as each testing task lands |
| **Owner** | Vraj Patel |
| **Related** | `BUILD_PLAN.md` T-002, T-003, T-004 · `API_CONTRACT.md` §10 · `ADR-0004`, `ADR-0005` |
| **Last updated** | 5 September 2026 (after T-001) |

---

## 1 · Why this document exists

"Did you test it?" is a useless question, because it has no wrong answer.
Everything has been tested in some sense. The useful questions are:

- **What kind** of test is that?
- **What can it catch**, and what will it happily let through?
- **When does it run**, and what happens when it fails?

This document answers those for every check in the repository. If you read one
section, read §3 — the table of what each kind of test cannot catch. That is
where the real risk lives.

There is a specific reason this project needs it written down. Most software can
be judged by whether it works. This project makes a **research claim** — that
three rule-based detectors identify reasoning patterns at 94% accuracy — and
that claim is only worth anything if the number is reproducible. So the test
suite here is doing two different jobs at once: the ordinary engineering job of
stopping regressions, and the unusual job of **defending a published result**.
Those two jobs need different kinds of test, and confusing them is how a number
quietly drifts.

---

## 2 · What we are actually protecting

Everything below serves these. A test that does not trace back to one of them is
probably not worth its maintenance cost.

| # | Property | Source | How it is defended |
|---|---|---|---|
| **P1** | The LLM never marks. Every flag, score and verdict is deterministic Python. | `ADR-0005` | `test_layering.py` forbids `groq` in `domain/` · reviewed in code review |
| **P2** | Every judgement is traceable to the learner's own questions or omissions. | `ADR-0004` | `validate_detectors.py` recomputes flags from stored questions |
| **P3** | The event log is the source of truth; derived state is reproducible from it. | `ADR-0003` | requires a pure `domain/` — `test_layering.py` |
| **P4** | Detector accuracy stays ≥ 94%. | `CLAUDE.md` | `validate_detectors.py`, gated in CI by T-004 |
| **P5** | Assessment state is never visible during a consultation. | `PRD` P2 | contract tests CT-1, CT-2 — *not yet written* |
| **P6** | Bias vocabulary never appears in user-facing text. | `PRD` P1 | contract test CT-5 — *not yet written* |
| **P7** | Anchor keywords never overlap contradictory clues. | `DATA_MODEL` §8.1 invariant C-4 | lexicon disjointness test — **T-003, not yet written** |

P7 deserves attention. Overlapping keywords is not a hypothetical: it is the
exact bug that held the confirmation-bias detector at **14% sensitivity** until
it was found. A test that would have caught it in a second did not exist. T-003
writes it.

---

## 3 · The kinds of test we use

Six kinds, each answering a different question. The last column is the
important one.

| Kind | The question it answers | Cost to run | **What it cannot catch** |
|---|---|---|---|
| **Smoke** | Is it plugged in? | ~0.3 s | Whether any answer is *right*. A route returning a confidently wrong diagnosis passes. |
| **Structural** | Does the code obey its own architecture? | ~0.1 s | Whether the architecture is any good. It checks the rule, not the wisdom of the rule. |
| **Unit** | Does this function compute the right answer? | fast | Whether the pieces work together. Every unit can pass while the app is broken. |
| **Contract** | Does the system honour a promise we made to users? | seconds | Promises nobody wrote down. |
| **Validation** | Is the research claim still true? | ~2 s | Whether 94% is *good enough*. That is a clinical judgement, not a test result. |
| **Integration** | Does the database enforce what we think it enforces? | ~6 s, needs Docker | Anything above the query. And it **skips** when Docker is absent, so a guard that lives only here is untested on those runs (`tests/test_db_actor.py` exists for that reason). |

**All six kinds now exist.** Unit and contract arrived with T-002 and T-004;
integration with T-010, which starts a real PostgreSQL 16 in a container because
every guarantee it checks — partial unique indexes, CHECK constraints,
append-only triggers, the publication gate, Row-Level Security — is a PostgreSQL
feature that would be tested nowhere else. T-012 extended it from "the policies
are written correctly" to "the policies deny the application". §8 tracks what is
still missing.

**Two of these kinds exist to check each other.** The structural tests
(`test_layering.py`, `test_db_access.py`) prove nobody *wrote* a bypass; the
integration tests prove the database would *refuse* one anyway. Either alone is
a single point of failure — a correct policy that never applies looks exactly
like a working system.

### Why not "just write more tests"

Tests cost something. They have to be read, maintained, and understood when they
fail. A test that fails for reasons unrelated to a real defect is worse than no
test, because it trains people to ignore failures.

So the rule here is: **a test earns its place by protecting a property in §2**.
Coverage percentage is not a target and is not measured.

---

## 4 · Smoke tests — `tests/test_smoke.py`

**11 tests · ~0.3 s · run on every change**

### What they are for

After T-001 moved every file in the codebase, the first question is not "is the
logic correct" — the logic was not touched. It is **"is anything still
connected?"** A smoke test answers that and nothing more. The name comes from
hardware: power it on and see whether smoke comes out.

**T-013 moved half of them out.** Session state became an append-only event
log, so the consultation routes now replay that log on every request and cannot
run without PostgreSQL. Those tests moved to `tests/db/test_routes.py`, where
they became stronger — they now check that a consultation survives the process
that started it. Keeping them here behind a container would have cost this file
the property that makes it worth running on every change: it finishes in well
under a second, with nothing installed and nothing running.

What is left is exactly the routes that read no session state.

### How they are implemented

Flask provides a **test client** — an object that sends requests to the
application in-process, without opening a socket or starting a server. That is
why the whole suite runs in a third of a second.

```python
@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-used")
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret")
    app = create_app({"TESTING": True})
    return app.test_client()
```

Three things are happening here, and each is deliberate:

**`@pytest.fixture`** — a fixture is setup code that pytest runs before any test
that asks for it. Any test with `client` in its signature gets a freshly built
application. Fresh matters: a shared application would let one test's session
state leak into the next, and a test that passes only because of what ran before
it is not a test.

**`monkeypatch.setenv`** — sets an environment variable for the duration of one
test and restores it afterwards. The Groq key is set to a deliberate
non-credential, `"test-key-not-used"`, because of the lazy client construction
described in the T-001 build log: importing the gateway needs no key, and these
tests never reach a real model call. If one ever did, it would fail loudly on an
invalid key rather than quietly spending quota. **That is the intended
behaviour** — a smoke test that silently starts calling a paid API is a bug.

**`create_app({"TESTING": True})`** — the factory from T-001. `TESTING=True`
makes Flask propagate exceptions instead of converting them to a generic 500
page, so a broken route produces a real stack trace rather than an unhelpful
status code.

### What each test checks, and why that one

| Test | Asserts | Why it exists |
|---|---|---|
| `test_index_lists_cases` | `GET /` → 200 | The most basic possible check — the app renders at all |
| `test_pre_case_renders_for_every_case` | `GET /pre_case/case_N` → 200 and contains `name="participant_id"` | Runs for **all five cases**. A case with a malformed dictionary would only break its own page |
| `test_pre_case_post_starts_consultation` | POST with participant data → 200 | The form actually submits and a session begins |
| `test_start_route_bypasses_form` | `GET /start/case_1` → 200 | The demo path, used when showing the system without collecting participant data |
| `test_unknown_case_redirects` | `GET /pre_case/case_999` → 302 or 404 | **A negative test.** Bad input must be refused, not crash |
| `test_examine_without_session_is_rejected` | `POST /examine` with no session → 400 | **A negative test.** Guards against acting on a request with no consultation behind it |
| `test_examine_returns_finding_within_a_session` | after starting a session, `POST /examine` → 200 with `finding` in the JSON | The positive counterpart — proves the rejection above is conditional, not permanent |
| `test_investigate_returns_result_within_a_session` | same shape for investigations | Same reasoning |
| `test_unknown_investigation_key_is_rejected` | `POST /investigate` with a nonsense key → 400 | **A negative test.** A typo must not silently return an empty result |
| `test_feedback_without_session_redirects` | `GET /feedback` with no session → 302 | You cannot read feedback for a consultation that did not happen |
| `test_save_session_wrapper_responds` | `POST /save_session` → 200 | The persistence route is reachable |

### The pattern worth copying: pair every negative with a positive

Four of these are negative tests — they assert that something is *refused*. A
negative test alone is dangerously weak, because a route that is broken and
returns 400 for absolutely everything passes it.

That is why `test_examine_without_session_is_rejected` (400) is always paired
with `test_examine_returns_finding_within_a_session` (200 with real content).
Together they prove the rejection is a decision rather than an accident. On its
own, either one is close to worthless.

### `parametrize` — one test, five cases

```python
@pytest.mark.parametrize("case_id", ["case_1", "case_2", "case_3", "case_4", "case_5"])
def test_pre_case_renders_for_every_case(client, case_id):
    r = client.get(f"/pre_case/{case_id}")
    assert r.status_code == 200
```

pytest runs this five times and reports five results. Written as a loop inside
one test it would report one result, and the failure message would not say
*which* case broke. When we add cases 6–10 (business requirement BR-1), this
list grows by one line each.

### What these tests deliberately do not do

They do not check that the patient's reply is medically sensible, that a finding
matches the case, or that a diagnosis is scored correctly. **Every one of those
needs the domain unit tests from T-002.** A smoke test asserting `200` will
happily pass on a system that has become clinically useless.

That is not a flaw in the smoke tests. It is what they are for. The mistake
would be believing they cover more than they do.

---

## 5 · Structural tests — `tests/test_layering.py`

**2 tests · ~0.05 s · plus an equivalent CI contract**

### The problem being solved

`ADR-0009` chose a modular monolith: one deployable process with enforced
internal boundaries. The entire argument for that choice rests on the word
*enforced*. A boundary that exists only in a document is a boundary that will be
crossed on a deadline, by someone with a good reason, and nobody will notice
until the layer is unusable.

So the rule — **`domain/` may not import `infra/` or `api/`** — is a test.

### How it is implemented

By parsing the source rather than running it:

```python
def _imports(path: pathlib.Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module
```

`ast` is Python's own parser. `ast.parse()` turns source text into an **abstract
syntax tree** — a structured representation of the code — and `ast.walk()`
visits every node in it. The two node types matter because Python has two import
forms:

- `import os` → an `ast.Import` node, module names in `.names`
- `from nidan.infra import x` → an `ast.ImportFrom` node, module in `.module`

**Why parse instead of grepping for the word "import".** `grep` would match the
word inside a comment, a docstring, or a string literal, and would miss an
indented import inside a function body. Parsing sees the code as Python sees it.
(This is not theoretical — during T-001 an anchored `sed` pattern missed exactly
such an indented import in `analyze_sessions.py`.)

**Why parse instead of importing the modules and checking `sys.modules`.**
Importing runs module-level code. That is slower, and it means the test can fail
for reasons that have nothing to do with layering.

### The two tests

**Test 1 — no upward imports.**

```python
FORBIDDEN = ("nidan.infra", "nidan.api", "nidan.app")

def test_domain_does_not_import_infra_or_api():
    violations = []
    for py in DOMAIN.rglob("*.py"):
        for mod in _imports(py):
            if mod.startswith(FORBIDDEN):
                violations.append(f"{py.relative_to(DOMAIN.parent)} imports {mod}")
    assert not violations, "domain layer must stay pure:\n  " + "\n  ".join(violations)
```

`rglob("*.py")` walks the whole `domain/` tree, so a new subdirectory is covered
the moment it is created. Nobody has to remember to add it.

**Collect all violations, then assert once.** The test does not `assert` inside
the loop. If it did, it would stop at the first violation and you would fix
them one slow run at a time. Collecting first means one run tells you
everything:

```
AssertionError: domain layer must stay pure:
  domain/session.py imports nidan.infra.storage
  domain/feedback.py imports nidan.infra.llm.gateway
```

The message names the file and the offending import. A test whose failure
message is just `assert False` has wasted the opportunity to explain itself.

**Test 2 — no framework or provider dependency.**

```python
def test_domain_has_no_flask_dependency():
    """A domain module that needs Flask is really a web module."""
    ...
    if mod.split(".")[0] in ("flask", "groq"):
```

This catches something the first test cannot. A file could import `flask`
directly without going through `nidan.api`, and test 1 would pass. But a domain
module that needs a web framework is misfiled by definition, and one that
imports `groq` is a direct threat to **P1 — the LLM never marks**.

Test 1 defends the layer diagram. Test 2 defends the property the diagram exists
to protect. They are not redundant.

### Belt and braces: the import-linter contract

`pyproject.toml` also declares the rule as data:

```toml
[[tool.importlinter.contracts]]
name = "domain must not import infra or api"
type = "forbidden"
source_modules = ["nidan.domain"]
forbidden_modules = ["nidan.infra", "nidan.api", "nidan.app"]
```

```
$ lint-imports
domain must not import infra or api KEPT
Contracts: 1 kept, 0 broken.
```

**Why have both.** They catch different things. The pytest version is direct —
it reads the files and needs no extra tool. import-linter builds a full import
graph and catches **transitive** violations: if `domain/a.py` imports
`domain/b.py`, and `b` imports `infra/`, the AST test sees two individually
legal imports while import-linter sees the illegal path. The pytest version
gives fast local feedback; the contract is what CI enforces in T-004.

---

## 6 · Validation — `validate_detectors.py`

**18 labelled transcripts · 54 detector decisions · ~2 s · the gate on the
research claim**

This is not a unit test and should not be thought of as one, even though it runs
from the command line like one. It is the **measurement instrument for the
published result**, and it is the reason `CLAUDE.md` says *do not "fix" a
detector without re-running it*.

### What it does

It runs 18 hand-labelled consultation transcripts through the **real production
pipeline** — the same `create_session`, `update_session` and `detect_all_biases`
that a live consultation uses — and compares each detector's output against the
label a human assigned.

Running it through the production path rather than a test harness is the whole
point. A validation that exercises a parallel code path measures the parallel
path, not the product.

### The three numbers, and why all three are needed

For one detector, each transcript falls into one of four boxes:

|  | Detector said **yes** | Detector said **no** |
|---|---|---|
| **Actually present** | True Positive (TP) | False Negative (FN) — *missed it* |
| **Actually absent** | False Positive (FP) — *false alarm* | True Negative (TN) |

- **Sensitivity** = TP / (TP + FN) — *of the cases where the pattern was really
  there, how many did we catch?* A detector that flags everything scores 100%.
- **Specificity** = TN / (TN + FP) — *of the cases where it was absent, how many
  did we correctly leave alone?* A detector that flags nothing scores 100%.
- **Accuracy** = (TP + TN) / total — the overall proportion correct.

Neither of the first two is meaningful alone, because each is trivially gamed by
a detector that always answers the same way. Reported together they pin the
behaviour down.

### Current results

| Detector | TP | FP | FN | TN | Sensitivity | Specificity | Accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|
| Anchoring | 7 | 0 | 0 | 11 | 100% | 100% | 100% |
| Premature closure | 10 | 1 | 0 | 7 | 100% | 88% | 94% |
| Confirmation bias | 7 | 2 | 0 | 9 | 100% | 82% | 89% |

**Overall: 51/54 = 94%.**

### How to read those numbers honestly

**All three sensitivities are 100%, and every error is a false positive.** That
is not an accident, and it is the right shape for this system. A missed pattern
is silent — the learner gets no feedback on something they actually did. A false
alarm is visible, and because of **P2** every flag cites the learner's own
questions, so a learner who disagrees can see the evidence and judge it.

Given a choice, over-flagging is the safer failure for a teaching tool.

**Confirmation bias at 82% specificity is the weakest number and the honest
one.** It was 14% sensitivity before the keyword-overlap bug was found and
fixed. Reporting 89% accuracy rather than rounding the story up is the point —
this is the detector to improve next, and T-003 exists because of it.

**18 transcripts is a small sample.** Three fewer correct decisions would drop
the overall figure below the 94% gate. That fragility is a reason to grow the
labelled set, and it is a limitation that belongs in any write-up of the result.

### The CI gate

T-004 wires this into CI: **the build fails below 94%.** Not a warning — a
failure. A detector change that improves one case while quietly degrading two
others cannot be merged.

This is the single most important test in the repository. The smoke tests
protect the app. This one protects the claim.

---

## 7 · How to run everything

```bash
source venv/bin/activate
pip install -e ".[dev]"     # once
```

| Command | Runs | Time | Run it when |
|---|---|---|---|
| `pytest` | smoke + structural | 0.3 s | every change — no excuse |
| `pytest -v` | same, one line per test | 0.3 s | you want to see the names |
| `pytest tests/test_smoke.py -k examine` | just matching tests | instant | iterating on one route |
| `lint-imports` | the layering contract | 0.5 s | after moving or adding a module |
| `python validate_detectors.py` | detector validation | 2 s | **any** change to detectors, cases, or keywords |
| `python analyze_sessions.py sessions` | paired statistics | 1 s | after collecting new sessions |

### Reading a failure

pytest prints the failing line, both values, and the assertion message:

```
E       assert 400 == 200
E        +  where 400 = <WrapperTestResponse>.status_code
tests/test_smoke.py:52: AssertionError
```

Useful order of questions:

1. **Which test?** The name says what broke — `test_examine_returns_finding_within_a_session`.
2. **Expected versus actual?** `assert 400 == 200` — we wanted 200, got 400.
3. **What does 400 mean here?** In this app it means "no valid session", so the
   session was not created — the problem is probably upstream of `/examine`.
4. **Did anything else fail?** One root cause often trips several tests. Fix the
   earliest one first and re-run before investigating the rest.

`pytest -x` stops at the first failure; `pytest --lf` re-runs only what failed
last time. Both are useful while fixing.

---

## 8 · What is not tested yet

Stated plainly, because unlisted gaps are the dangerous kind.

**Every gap this section listed when it was written has since been closed.** The
original seven are kept below the line, with what closed them, because a list
that only ever grows teaches nothing about whether the plan worked.

### Open now

| Gap | Risk while it is open | Closed by |
|---|---|---|
| **No frontend tests.** No template renders correctly, no JavaScript behaves. | Low today, high after T-030 | T-030 |
| **No load or concurrency testing above the single-session level.** T-013 proves 10 parallel appends to one session; nothing exercises many sessions at once, or the connection pool under real traffic. | Low until launch | T-044 |
| **Nothing tests the admin console**, because it does not exist. | None yet | T-020–T-023 |
| **Stripe webhooks are untested** — idempotency, duplicate delivery, out-of-order arrival. `PRD` FR-10.4 requires all three. | High at launch | T-041 |
| **The sixteen backfilled results have no `counters` or `rule_fired`.** They predate `DATA_MODEL` §8.5, so any reader assuming the current shape breaks on exactly the oldest rows. Nothing checks that assumption. | Low — documented in the T-018 build log | when a reader needs them |
| **Persona leakage is measured, not tested.** `TECH_SPEC` §5.3 rates it the largest residual risk; there is no automated check that the patient never volunteers the diagnosis. | **High** — it is the largest residual risk | T-040 |

### Closed since this was written

| Gap | Closed by | How |
|---|---|---|
| No unit tests on the detectors themselves | T-002 | Per-rule tests; a failure now names the rule |
| No test that the LLM is never on the marking path (P1) | T-002 | `tests/test_llm_never_marks.py` |
| No lexicon disjointness test (P7) | T-003 | Invariants C-1…C-9, run in CI |
| Contract tests CT-1 … CT-9 not written | T-004 | Written, and extended in T-015/T-017 for the trial and allowance payloads |
| No CI | T-004 | Eight jobs, branch protection by ruleset |
| No test of the LLM failure path | T-002 | The fallback is asserted, and T-014 added the `generator` column that records when it fired |
| **Assessment could not be replayed** (not listed originally) | T-016 | The golden record over all 16 pilot sessions |

The two originally marked **High** were closed by T-002 and T-003, which is why
those tasks sat immediately after T-001 rather than later. The plan held.

---

## 9 · Rules for adding a test

**Name it after what breaks, not what it calls.**
`test_examine_without_session_is_rejected` — good. `test_examine_2` — useless in
a failure report six weeks from now.

**One reason to fail per test.** A test asserting five unrelated things tells you
one of five things is wrong. Prefer five tests, or `parametrize`.

**Write the failure message.** `assert not violations, "domain layer must stay
pure:\n  " + ...` costs one line and saves the next person a debugging session.

**A negative test needs a positive twin.** Otherwise a permanently broken route
passes by refusing everything.

**Never let a test call a real model.** It costs money, it is slow, and it is
non-deterministic — the same input can produce a different reply, so the test
fails at random and gets ignored. Use the fake gateway from T-002.

**Trace it to §2.** If a test does not defend a property, ask what it is for.
The answer might be good; it should exist.

**When you fix a bug, write the test first.** Confirm it fails, then fix, then
confirm it passes. A test written after a fix has never been observed to fail,
so there is no evidence it can.

---

## 10 · Glossary

| Term | Meaning here |
|---|---|
| **assert** | A statement that must be true. `assert x == 2` passes silently or fails the test. |
| **AST** | Abstract Syntax Tree — code parsed into structure. Used to inspect imports without running anything. |
| **blueprint** | A Flask object grouping routes so they can be registered onto an app as a unit. Namespaces endpoints: `index` becomes `web.index`. |
| **contract test** | A test of a promise made to users, rather than of a function. Ours are CT-1…CT-9 in `API_CONTRACT.md`. |
| **fixture** | pytest setup code, run fresh for each test that requests it by name. |
| **monkeypatch** | pytest tool that changes something (env var, function, attribute) for one test and restores it after. |
| **parametrize** | Run one test function repeatedly with different inputs, reported as separate results. |
| **sensitivity** | Of the cases where the pattern was present, the proportion detected. |
| **specificity** | Of the cases where it was absent, the proportion correctly left alone. |
| **smoke test** | A shallow check that the system is connected and responding. Named after powering on hardware and watching for smoke. |
| **test client** | Flask object that sends requests in-process, with no socket and no server. |
| **transitive import** | A reaches C through B. Invisible to a per-file check; visible to an import graph. |

---

## 11 · Change log

| Date | Change |
|---|---|
| 5 Sep 2026 | Created after T-001. Documents smoke (11), structural (2) and validation (54 decisions). Gaps in §8 are the scope of T-002 to T-004. |
