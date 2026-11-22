#!/usr/bin/env bash
#
# One command to bring the demo up: database, migrations, published cases,
# a warm LLM, the API, and the web app.
#
#     ./scripts/demo_up.sh              # everything, web app in the foreground
#     ./scripts/demo_up.sh --api-only   # no Next.js (for curl or the prototype)
#     ./scripts/demo_up.sh --no-warm    # skip the LLM warm-up call
#
# Ctrl+C stops both servers. The API's output goes to logs/api.log, because
# interleaving two servers' logs in one terminal makes both unreadable.
#
# ## Why each step is here, and not just "start the two servers"
#
# Three things have broken a local run of this project before, and none of
# them says what is wrong at the point you notice:
#
#   * **Every case is a `draft`.** `SelectionRepository.candidates()` returns
#     only published versions, so `POST /v1/sessions` answers 503
#     `no_cases_available` and the dashboard's Start button fails. The test
#     suite never sees it; its fixtures publish a case themselves.
#   * **The first LLM call of an idle period is a cold start.** Measured at
#     114 s, against ~800 ms warm. Unwarmed, the first question anyone asks
#     looks like a hang.
#   * **A migration arrived with someone else's merge.** `alembic upgrade
#     head` is idempotent and costs a second; a schema one revision behind
#     fails somewhere that does not mention migrations.
#
# So this runs the checks in the order that makes a failure legible, and
# refuses to start the web app at all if its two Supabase values are empty —
# because `npm run dev` succeeds without them and the failure lands on the
# sign-in screen instead.

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
mkdir -p logs          # step 5 writes warm.log before step 6 would create this

API_ONLY=0
WARM=1
for arg in "$@"; do
  case "$arg" in
    --api-only) API_ONLY=1 ;;
    --no-warm)  WARM=0 ;;
    -h|--help)  sed -n '3,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown flag: $arg (try --help)" >&2; exit 2 ;;
  esac
done

bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
N=0
step()  { N=$((N + 1)); printf '\n\033[1m[%s/%s] %s\033[0m\n' "$N" "$TOTAL" "$1"; }
warn()  { printf '\033[33m  !  %s\033[0m\n' "$*"; }
die()   { printf '\033[31m\n  x  %s\033[0m\n' "$*" >&2; exit 1; }

TOTAL=6   # the web app starts after the six, and is not one of them

PY="$ROOT/venv/bin/python"
[ -x "$PY" ] || die "no venv at venv/bin/python — run: python3 -m venv venv && source venv/bin/activate && pip install -e ."

# ---------------------------------------------------------------- 1. preflight
step "Preflight"

[ -f .env ] || die ".env is missing. Copy .env.example and put your GROQ_API_KEY in it."
grep -q '^GROQ_API_KEY=.\+' .env || die "GROQ_API_KEY is empty in .env — the patient cannot speak without it."
echo "  .env has a GROQ_API_KEY"

# `migrations/env.py` reads `os.getenv("DATABASE_URL")` and nothing else, while
# the application reads `.env` through pydantic-settings. So alembic and the
# `scripts/` that import `nidan.config` disagree about whether the database is
# configured, and alembic is the one that loses. Export the single variable
# rather than sourcing the whole file: `.env` holds the Groq key, and `set -a;
# . ./.env` would put it in the environment of everything below, including npm.
if [ -z "${DATABASE_URL:-}" ]; then
  if grep -q '^DATABASE_URL=.\+' .env; then
    DATABASE_URL="$(grep -m1 '^DATABASE_URL=' .env | cut -d= -f2-)"
    export DATABASE_URL
    echo "  DATABASE_URL exported from .env"
  else
    die ".env has no DATABASE_URL. The app reads .env, but alembic only reads the
     environment, so migrations cannot run without it. Add (checking the port
     against POSTGRES_PORT in .env — this stack publishes 5433, not 5432):

       DATABASE_URL=postgresql://nidan:nidan_local_dev_only@localhost:5433/nidan"
  fi
else
  echo "  DATABASE_URL already set in the environment"
fi

if [ "$API_ONLY" -eq 0 ]; then
  ENVLOCAL="web/.env.local"
  [ -f "$ENVLOCAL" ] || die "$ENVLOCAL is missing. Copy web/.env.example to it."
  missing=()
  for key in NEXT_PUBLIC_SUPABASE_URL NEXT_PUBLIC_SUPABASE_ANON_KEY \
             NIDAN_API_URL NEXT_PUBLIC_SITE_URL; do
    grep -q "^${key}=.\+" "$ENVLOCAL" || missing+=("$key")
  done
  if [ ${#missing[@]} -gt 0 ]; then
    printf '\033[31m\n  x  %s is incomplete — these are empty:\033[0m\n' "$ENVLOCAL" >&2
    printf '       %s\n' "${missing[@]}" >&2
    cat >&2 <<'MSG'

     The first two come from the Supabase dashboard:
       Project Settings -> API -> Project URL, and the anon / publishable key.
       NOT the service_role key — that bypasses RLS and must never be in this app.

     `npm run dev` starts fine without them and fails on the sign-in screen,
     which is why this stops here instead.
MSG
    exit 1
  fi
  echo "  web/.env.local has all four values"

  command -v npm >/dev/null || die "npm is not on PATH, and the web app needs it. Use --api-only to skip it."
  [ -d web/node_modules ] || die "web/node_modules is missing — run: cd web && npm ci"
fi

# ---------------------------------------------------------------- 2. database
step "Postgres"

command -v docker >/dev/null || die "docker is not on PATH. Start Docker Desktop."
docker compose up -d db >/dev/null
printf '  waiting for pg_isready'
for i in $(seq 1 60); do
  state=$(docker inspect -f '{{.State.Health.Status}}' nidan-db 2>/dev/null || echo starting)
  [ "$state" = "healthy" ] && break
  printf '.'; sleep 1
done
printf '\n'
[ "${state:-}" = "healthy" ] || die "nidan-db is '$state' after 60 s. Check: docker compose logs db"
echo "  nidan-db healthy"

# ---------------------------------------------------------------- 3. migrations
step "Schema"
# Not `| grep ... || true`: a pipeline's status is the last command's, so the
# grep's success hid a failed upgrade and the line below then said "at head"
# about a schema that had not moved. That is the one kind of wrong output worth
# writing extra code to avoid — it reads as a pass.
if ! "$ROOT/venv/bin/alembic" upgrade head >logs/alembic.log 2>&1; then
  grep -v '^INFO' logs/alembic.log >&2 || cat logs/alembic.log >&2
  die "alembic upgrade head failed — full output in logs/alembic.log"
fi
# `grep -c` exits 1 when the count is zero, which under `pipefail` ended the
# whole script immediately after printing a success line. Count without a
# pipeline whose status can fail.
applied=$(grep -c 'Running upgrade' logs/alembic.log || true)
echo "  ${applied:-0} migration(s) applied, now at head"

# ------------------------------------------------------------ 4. published case
step "Published cases"
# Idempotent: it only selects draft versions, so a second run prints
# "Nothing to do." It goes through migration 007's approval trigger by
# inserting a review, never around it, and refuses any non-local database.
# Piping through sed would hand the pipeline sed's exit status under
# `pipefail`... in the other direction: a Python traceback would end the script
# with no line saying which step died. Capture, then decide.
if ! out=$("$PY" scripts/publish_for_demo.py --all 2>&1); then
  printf '%s\n' "$out" >&2
  die "publish_for_demo.py failed — without a published case, POST /v1/sessions
     answers 503 no_cases_available and the dashboard's Start button fails."
fi
printf '%s\n' "$out" | sed 's/^/  /'

# ------------------------------------------------------------------ 5. warm LLM
if [ "$WARM" -eq 1 ]; then
  step "Warming the LLM (this is the slow one — up to ~2 min cold)"
  if "$PY" -u test_api.py >logs/warm.log 2>&1; then
    echo "  the configured model answered"
  else
    warn "test_api.py failed — see logs/warm.log"
    warn "Usually a retired GROQ_MODEL or a bad key. The app will start, but"
    warn "the patient will answer 503 patient_unavailable."
  fi
else
  step "Warming the LLM — skipped (--no-warm)"
  warn "The first question of the session may take ~2 minutes."
fi

# ---------------------------------------------------------------------- 6. API
step "API"
# `docker-compose.yml`'s `app` service publishes 8000 and carries
# `restart: unless-stopped`, so it comes back by itself after a reboot — and
# its image is **baked at build time** with no source mount. Left running it
# would both take the port and serve whatever the code looked like when it was
# last built, which is the worse of the two failures: the demo works, quietly,
# on old code. `python -m nidan` below runs the working tree.
if [ "$(docker inspect -f '{{.State.Running}}' nidan-app 2>/dev/null || echo false)" = "true" ]; then
  warn "the nidan-app container holds port 8000, and its image is a stale build"
  warn "stopping it so this runs the working tree instead"
  docker compose stop app >/dev/null 2>&1 || true
fi

if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  printf '\033[31m\n  x  something is already listening on port 8000:\033[0m\n' >&2
  lsof -nP -iTCP:8000 -sTCP:LISTEN >&2
  die "stop it, or set PORT in .env to something else"
fi

"$PY" -m nidan >logs/api.log 2>&1 &
API_PID=$!
cleanup() {
  printf '\n'
  if kill -0 "$API_PID" 2>/dev/null; then
    echo "stopping the API (pid $API_PID)"
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

printf '  waiting for /healthz'
for i in $(seq 1 40); do
  if curl -fsS -m 2 http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
    ready=1; break
  fi
  kill -0 "$API_PID" 2>/dev/null || { printf '\n'; cat logs/api.log; die "the API exited during startup"; }
  printf '.'; sleep 1
done
printf '\n'
[ "${ready:-}" = 1 ] || { cat logs/api.log; die "no /healthz after 40 s"; }
echo "  http://127.0.0.1:8000  (log: logs/api.log)"

# ------------------------------------------------------------------- 7. web app
if [ "$API_ONLY" -eq 1 ]; then
  printf '\n'; bold "API only. Ctrl+C to stop."
  wait "$API_PID"
  exit 0
fi

printf '\n'
bold "Starting the web app. Demo at http://localhost:3000 — Ctrl+C stops both."
printf '\n'
cd web && exec npm run dev
