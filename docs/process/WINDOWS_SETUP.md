# Windows setup — getting Yogesh running

Everything needed to go from a fresh Windows machine to being able to edit,
test, commit and open a pull request on this project.

Written for Windows 10/11 with PowerShell. Where a command differs from the
macOS version in `COMMANDS.md`, the difference is called out.

**Budget about an hour**, most of it downloads.

---

## 0 · What changed while you were away

Phase 0 landed on 8 September — seven tasks, 293 tests, CI. Two things affect
how you work from now on:

**`main` is protected.** You cannot push to it directly. Every change goes
through a branch and a pull request, and six automated checks must pass before
it can merge. §5 covers the workflow.

**The code moved.** The flat prototype is now a `nidan/` package with three
layers. `python app.py` no longer exists — it is `python -m nidan`.

Read [`docs/PROJECT_MAP.md`](../PROJECT_MAP.md) first; it is the annotated tree
of the whole repository and takes ten minutes.

---

## 1 · Install these five things

| | Why | Where |
|---|---|---|
| **Git for Windows** | version control, and it brings Git Bash | git-scm.com |
| **Python 3.11 or newer** | the package refuses to install on older | python.org |
| **VS Code** | editor | code.visualstudio.com |
| **Docker Desktop** | runs the app with Postgres | docker.com |
| **A Groq API key** | the patient's replies | console.groq.com — free |

### Python — one box that matters

During installation, tick **"Add python.exe to PATH"** on the first screen. It
is off by default, and without it `python` is not a command and every later step
fails with something unhelpful.

**First, check what you already have.** In a **new** PowerShell window:

```powershell
py -0
```

That lists every Python on the machine, like `-V:3.13 *` or `-V:3.11`.

| What it shows | What to do |
|---|---|
| **3.11, 3.12, 3.13 or newer** | You are fine. Use that number in §4 — e.g. `py -3.13 -m venv venv` |
| **only 3.10 or older** | Install a newer one, below |
| **nothing, or "No suitable Python runtime found"** | Install one, below |

`requires-python = ">=3.11"`, so anything from 3.11 up works.

**If you need to install:** get **Python 3.11.x** from python.org — not
necessarily the newest release. CI runs 3.11 and the container is
`python:3.11-slim`, so matching it removes a class of "works locally, fails in
CI" problem. Newer works too; there is just no upside to differing.

Close and reopen PowerShell afterwards, or `py` will not see it.

### Docker Desktop — needs WSL2

Docker on Windows runs Linux containers inside WSL2. The installer usually sets
this up, but if it complains:

```powershell
wsl --install
```

Then restart. You do not need to learn WSL — Docker just uses it underneath.

Docker is only needed when you want the database. Everything else — the app, the
tests — runs without it.

---

## 2 · Configure git, once

Run these in PowerShell. The first two put your name on your commits.

```powershell
git config --global user.name "Yogesh Bagotia"
```

```powershell
git config --global user.email "your-github-email@example.com"
```

Use the email attached to your GitHub account, or your commits will not be
linked to you.

### Two settings that are Windows-specific

```powershell
git config --global core.autocrlf true
```

Windows uses a different invisible character to end each line. Without this, a
file you save looks *entirely rewritten* in a diff — every line changed — and
review becomes impossible. The repository now has a `.gitattributes` that
handles the important cases, and this setting completes it.

```powershell
git config --global core.longpaths true
```

Windows has a 260-character path limit that git hits on deeply nested files.
This lifts it.

---

## 3 · Get the project

```powershell
cd $HOME\Desktop
```

```powershell
git clone https://github.com/VrajPatel2611/A-bias-aware-vp-simulator.git
```

```powershell
cd A-bias-aware-vp-simulator
```

Everything from here runs from inside this folder. Being in the wrong directory
is the most common cause of a confusing error.

---

## 4 · Set up Python

**Create the virtual environment** — a private copy of Python for this project,
so its packages never collide with anything else on your machine:

```powershell
py -3.11 -m venv venv
```

Substitute whichever version `py -0` showed — `py -3.13 -m venv venv` and so on.
If this says **"No suitable Python runtime found"**, that version is not
installed; go back to §1.

**Activate it:**

```powershell
venv\Scripts\Activate.ps1
```

Your prompt should now start with `(venv)`.

> **If PowerShell refuses** with *"running scripts is disabled on this system"*,
> that is Windows' default script policy, not a problem with the project. Fix it
> once:
>
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```
>
> Answer `Y`, then run the activate command again. `CurrentUser` scope means you
> are not changing anything system-wide.

**You must activate it in every new terminal.** If a command suddenly says
"module not found", check for `(venv)` in your prompt first.

**Install the project:**

```powershell
pip install -e ".[dev]"
```

`-e` means *editable* — it links to this folder rather than copying, so your
edits are live with no reinstall. `[dev]` adds the test and lint tools.

---

## 5 · Configure it

```powershell
Copy-Item .env.example .env
```

Open `.env` in VS Code and paste your Groq key into `GROQ_API_KEY=`.

`.env` is git-ignored and must stay that way — it holds a real credential.
`.env.example` is the committed template and never holds a real value.

**You can skip the key for now.** The app starts, the case list works, and all
The suite passes without one. Only the patient's replies need it.

---

## 6 · Check it works

```powershell
pytest
```

**293 passed**, about 10 seconds. If that works, your setup is correct.

```powershell
python validate_detectors.py
```

Must print `PASS: detector accuracy 94.4%`. This is the research result, and CI
fails the build if it drops below 94%.

```powershell
python -m nidan
```

Open http://localhost:8000 — five cases. `Ctrl+C` to stop.

**Optionally, the full stack** (needs Docker Desktop running):

```powershell
docker compose up --build
```

First run takes several minutes. Same URL, plus PostgreSQL on port 5432.

> On Vraj's Mac the database is on **5433**, because Homebrew Postgres already
> holds 5432 there. On your machine 5432 is probably free, so the default works.
> If it says *"address already in use"*, add `POSTGRES_PORT=5433` to your `.env`.

---

## 7 · How to make a change now

**This is the part that is different from before.** `main` is protected: no
direct pushes, and six checks must pass.

**1 · Start from an up-to-date main**

```powershell
git checkout main
```

```powershell
git pull
```

**2 · Make a branch**

```powershell
git checkout -b feature/t-020-admin-shell
```

Name it after the task where there is one.

**3 · Do the work, then check it yourself before pushing**

```powershell
pytest
```

```powershell
ruff check . --fix
```

```powershell
python validate_detectors.py
```

These are three of the six checks CI runs. Running them locally means no
surprises.

**4 · Commit**

```powershell
git add -A
```

```powershell
git commit -m "feat(admin): add the admin shell with audit logging"
```

Write what changed and why, not what file you touched.

**5 · Push and open a pull request**

```powershell
git push -u origin HEAD
```

GitHub prints a link. Open it, click **Create pull request**.

**6 · Wait for CI.** Six checks run for two to three minutes. All must be green
before the merge button works. If one is red, click its name to see why.

**7 · Merge**, then delete the branch when GitHub offers.

### The six checks, and what red means

| Check | Usually means |
|---|---|
| **Lint and types** | `ruff check . --fix` fixes most of it |
| **Tests** | a real failure — the assertion messages name what broke |
| **Detector validation** | **stop.** Something changed the research result. Do not touch the threshold |
| **Case content invariants** | a case edit broke a rule; the message names the offending terms |
| **Security** | a new vulnerable dependency, or a secret in your diff |
| **Docker image builds** | the container no longer builds |

---

## 8 · What is yours to build

Thirteen tasks, 41 days of the plan:

| | Task | Phase | Est |
|---|---|---|---|
| ⬜ | **T-020** Admin shell and auth | 2 | 1 d |
| ⬜ | **T-021** Case editor ⭐ | 2 | 5 d |
| ⬜ | **T-022** Playtest with live instrumentation ⭐ | 2 | 4 d |
| ⬜ | **T-023** Clinical review workflow ⭐ | 2 | 2 d |
| ⬜ | **T-032** Next.js scaffold and auth | 3 | 4 d |
| ⬜ | **T-033** Dashboard and onboarding | 3 | 3 d |
| ⬜ | **T-034** Consultation screen ⭐ | 3 | 6 d |
| ⬜ | **T-036** Feedback screen ⭐ | 3 | 3 d |
| ⬜ | **T-037** History and progress | 3 | 3 d |
| ⬜ | **T-042** Pricing and account screens | 4 | 3 d |
| ⬜ | **T-043** AI usage and cost dashboard | 4 | 2 d |
| ⬜ | **T-044** Master list and lexicon editors | 4 | 3 d |
| ⬜ | **T-045** Launch readiness (with Vraj) | 4 | 2 d |

**Phase 2 is the milestone that matters most.** T-021 and T-022 are what let a
clinician read and test a case without reading Python. Until they exist, the two
clinical reviewers cannot start, and content authoring is the real critical path
to launch.

None of it can start until Phase 1 gives you a database and accounts — that is
Vraj's next 16 days.

---

## 9 · Four rules that are easy to break

From `CLAUDE.md`. Each has a test that will fail if broken, but knowing them
saves the round trip.

**Never show assessment state during a consultation.** No coverage meter, no
question counter, no topic hints, no "you might want to ask about…" prompt. A
visible metric teaches the metric instead of the skill. This bites hardest in
**T-034**, the consultation screen — the specification lists it as criterion 4
precisely because it is tempting.

**Never use bias vocabulary in user-facing text.** Not "bias", "anchoring",
"premature closure", "confirmation bias". The headings are *Diagnostic focus ·
History completeness · Evidence exploration*. Relevant to **T-036**.

**Never edit an ADR.** If a decision changes, write a new record that supersedes
it. The record of a reversed decision is more valuable than the decision.

**Never lower the 94% threshold** to make a red build green. If detector
validation fails, something changed the instrument the paper reports.

---

## 10 · When something goes wrong

| Symptom | Fix |
|---|---|
| `python` is not recognised | Python not on PATH — reinstall and tick "Add to PATH", or use `py` |
| `running scripts is disabled` | `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| `ModuleNotFoundError: nidan` | venv not activated (no `(venv)` in prompt), or `pip install -e ".[dev]"` not run |
| `requires a different Python: 3.9` | wrong Python — delete `venv\`, then recreate with a 3.11+ version |
| `No suitable Python runtime found` | that version is not installed. `py -0` lists what you have |
| `docker: command not found` | Docker Desktop not installed, or not launched |
| `Cannot connect to the Docker daemon` | Docker Desktop installed but not running — start it and wait |
| `address already in use` on 5432 | add `POSTGRES_PORT=5433` to `.env` |
| Every line shows as changed in a diff | `git config --global core.autocrlf true`, then re-clone |
| `push declined` / `protected branch` | you are on `main`. Make a branch — see §7 |
| Tests pass, then fail, nothing changed | stale bytecode: delete `__pycache__` folders |
| `UnicodeDecodeError: 'charmap' codec` | **Fixed on 8 September.** `git pull` on `main`. It was a real bug: file reads without an explicit encoding use cp1252 on Windows, and the repository is UTF-8. CI now runs the suite on Windows so it cannot recur |

`docs/process/COMMANDS.md` has the fuller list. Its commands are written for
macOS; the differences that matter are:

| macOS | Windows |
|---|---|
| `source venv/bin/activate` | `venv\Scripts\Activate.ps1` |
| `python3.11 -m venv venv` | `py -3.11 -m venv venv` |
| `cp .env.example .env` | `Copy-Item .env.example .env` |
| `rm -rf x` | `Remove-Item -Recurse -Force x` |

Everything after activation — `pytest`, `ruff`, `python -m nidan`, `git`,
`docker compose` — is identical on both.

---

## 11 · Where to read what

| You want to… | Read |
|---|---|
| Understand the repository | `docs/PROJECT_MAP.md` |
| See what is done | `docs/build-log/STATUS.md` |
| Build a task | `docs/spec/BUILD_PLAN.md` → the task → only its `Spec` refs |
| Build a screen | `docs/spec/UX_SPEC.md` — that screen's section only |
| Know why something was decided | `docs/spec/adr/` |
| Find a command | `docs/process/COMMANDS.md` |

**Do not read `docs/design/`.** It is 23,000 words of superseded design and it
will confidently describe decisions that have since been reversed. Both files
now open with a banner saying so.

---

*Written 8 September 2026, after Phase 0 landed.*
