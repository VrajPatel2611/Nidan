# Reaching `/admin` on a local machine

The console has no sign-in page of its own. `ADR-0002` gives Supabase the job of
issuing credentials and leaves this backend only the job of verifying them, so
signing in locally means obtaining a real Supabase token and letting the app
check it. There is no development bypass, and that is deliberate: a second way
in is a second thing to get wrong.

Verified end to end on 28 October 2026 against the `Nidan` project
(`eu-central-1`, `ADR-0017`).

---

## Read this first: every failure looks the same

`UX_SPEC` §12.1 requires every admin refusal to return an **identical 404** — no
token, expired token, signed in without privilege. A 403 would tell someone
probing that there is a console here; so would a 404 that differs between those
cases.

The consequence for you is that **the response tells you nothing about what is
wrong.** Four quite different mistakes all produce the same blank 404. Work
through the steps in order rather than guessing, and use the table at the end.

One exception, and it is useful: a **500 is not a refusal.** It means you got
past the privilege check and the handler itself broke. If you see a 500, your
authentication is working.

---

## 1 · Point the app at the project

In `.env` — both values are public, and `SUPABASE_URL` is the only one the
backend needs:

```
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_JWT_AUDIENCE=authenticated
```

`jwks_url` and `jwt_issuer` are both derived from `SUPABASE_URL` in
`nidan/config.py`, so there is nothing else to keep in step. Leave `SUPABASE_URL`
empty and `jwks.py` refuses to fetch a key set it has no address for — every
admin route then 404s, which looks exactly like a permissions problem.

> **Never put the `service_role` key in `.env`.** It bypasses RLS entirely and
> would undo every policy in migrations 016 and 020–024. Nothing here uses it.
> The `anon` key is the publishable one and is only needed in step 4.

## 2 · Rebuild the image, do not just restart it

```bash
docker compose up -d --build app
```

**`--build` is not optional.** A stale image is the single most confusing failure
in this list, because the container keeps serving an older copy of the
application: an image built before T-014 has no `nidan.infra.auth` at all, and
one built before the packaging fix of 28 October has no `admin/` templates, so
`/admin` 500s with `TemplateNotFound` however correct your token is.

Confirm the container actually sees the configuration:

```bash
docker compose exec -T app printenv SUPABASE_URL SUPABASE_JWT_AUDIENCE
```

Empty output means `docker-compose.yml` is not passing them through.

## 3 · Bring the local database to head, and give yourself a profile

```bash
docker compose up -d db
DATABASE_URL="postgresql://nidan:nidan_local_dev_only@localhost:5433/nidan" alembic upgrade head
```

Note **port 5433**: compose maps the container's 5432 to 5433 on the host, so
5432 is either nothing or some other PostgreSQL you have running.

A database below migration 022 has no `platform_role` column — which is the
column `require_role` reads — so `/admin` cannot work at any token. Check:

```bash
docker compose exec -T db psql -U nidan -d nidan -c "SELECT version_num FROM alembic_version;"
```

Then create the account. In the Supabase dashboard: **Authentication → Users →
Add user → Create new user**, and **tick "Auto Confirm User"** — without it the
token request in step 4 fails with `email_not_confirmed`. Copy the **User UID**.

Supabase holds the account; your local Postgres holds the profile, and the two
are joined by that UID, so both rows are needed:

```bash
docker compose exec -T db psql -U nidan -d nidan \
  -c "INSERT INTO auth.users (id) VALUES ('<uid>') ON CONFLICT (id) DO NOTHING;" \
  -c "INSERT INTO profiles (id, display_name, platform_role, timezone) VALUES ('<uid>', '<your name>', 'admin', 'Asia/Kolkata') ON CONFLICT (id) DO UPDATE SET platform_role = 'admin';"
```

Use `'reviewer'` in place of `'admin'` to see the console as a clinician does.
Worth doing once while building T-023: that is the role which reaches the review
queue and nothing else, and `current_reviewer()` is what those routes must use.

## 4 · Get an access token

From **Settings → API**, copy the **`anon` `public`** key. Then:

```bash
printf 'email: '; read -r EMAIL; printf 'anon key: '; read -rs ANON; echo; printf 'password: '; read -rs PW; echo; PAYLOAD=$(EMAIL="$EMAIL" PW="$PW" python3 -c 'import os,json;print(json.dumps({"email":os.environ["EMAIL"],"password":os.environ["PW"]}))'); curl -s "$SUPABASE_URL/auth/v1/token?grant_type=password" -H "apikey: $ANON" -H "Content-Type: application/json" -d "$PAYLOAD" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("access_token") or d)'
```

`read -rs` keeps the key and password off the screen and out of shell history.
The JSON body is built in Python rather than interpolated by the shell, so a
password containing a quote, a backslash or a `$` does not silently corrupt the
request.

Tokens last about an hour. When the console starts 404ing again, this is the
step to repeat.

## 5 · Check it before touching the browser

`bearer_token()` accepts an `Authorization` header as well as the cookie
(`API_CONTRACT` §2.2 specifies the header, `SECURITY_SPEC` L2 the cookie; the
server-rendered prototype needs both), so the whole chain can be tested in one
command:

```bash
printf 'token: '; read -rs TOK; echo; curl -s -o /dev/null -w 'admin -> %{http_code}\n' -H "Authorization: Bearer $TOK" http://localhost:8000/admin
```

**200** means the token verified against the project's JWKS, `aud` and `iss`
matched, the profile was found and the role was sufficient.

## 6 · Set the cookie, for actual browsing

A browser cannot send the header, so with the app at `http://localhost:8000`,
open dev tools → **Application** → **Cookies** and add:

```
name   sb-access-token
value  <access_token>
path   /
```

Then open `http://localhost:8000/admin`.

---

## When it 404s

In the order worth checking:

| Cause | How to tell |
|---|---|
| Token expired | Most likely if it worked an hour ago. Redo step 4 |
| Cookie not set, or set on the wrong host | Dev tools → Application → Cookies. Must be `localhost:8000`, path `/` |
| `SUPABASE_URL` not reaching the container | `docker compose exec -T app printenv SUPABASE_URL` |
| Database below 022 | `SELECT version_num FROM alembic_version;` |
| No profile row, or the wrong role | `SELECT id, platform_role FROM profiles;` — the id must equal the token's `sub` |
| Stale image | Rebuild with `--build` |

The response will not distinguish these, but **the logs will**:

```bash
docker compose logs app --tail 50
```

Every request is logged with its `request_id`, and an exception is logged with
its traceback even though the response body says only "Not found." That
asymmetry is the point of the design: silent outward, legible inward.
