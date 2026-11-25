#!/usr/bin/env python3
"""
An access token for the admin console, ready to paste into the browser.

    python scripts/admin_token.py              # the admin account
    python scripts/admin_token.py --reviewer   # the clinician
    python scripts/admin_token.py --email someone@example.com

## Why this exists

`/admin` has no sign-in page, and that is deliberate: `ADR-0002` gives
Supabase the job of issuing credentials and leaves this backend only the job
of verifying them. A second way in is a second thing to get wrong.

The consequence is that reaching the console means obtaining a real Supabase
token and putting it in a cookie, because a browser cannot send an
`Authorization` header by itself. `LOCAL_ADMIN_ACCESS.md` §4 does that with a
`curl` one-liner you have to read carefully. This is the same request with the
awkward parts handled: it finds the project and the publishable key, reads the
password out of `logs/demo-accounts.txt`, and prints the exact line to paste
into the browser console -- **and copies it to the clipboard on macOS**, which
is the difference between a smooth demo and a minute of squinting at a 900
character token on a projector.

It is a convenience, not a bypass. The token it returns is an ordinary
Supabase token and the app verifies it exactly as it verifies any other:
signature, `aud` and `iss`, then the profile's `platform_role`.

## Tokens last about an hour

When the console starts answering a blank 404 again, run this again. Every
admin refusal is an identical 404 by design (`UX_SPEC` §12.1), so the page
cannot tell you that expiry is what happened -- which is why that is the
first thing to try.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from seed_demo_accounts import (  # noqa: E402
    CREDENTIALS_FILE,
    DOMAIN,
    existing_password,
    supabase_credentials,
)


def fetch_token(url: str, key: str, email: str, password: str) -> str:
    body = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{url}/auth/v1/token?grant_type=password", data=body, method="POST",
        headers={"apikey": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read())["access_token"]
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")[:300]
        raise SystemExit(
            f"Supabase refused the sign-in for {email}: {err.code}\n{detail}\n\n"
            f"If the password in {CREDENTIALS_FILE} is stale, re-run\n"
            f"  python scripts/seed_demo_accounts.py --password '<the real one>'"
        ) from None


def copy_to_clipboard(text: str) -> bool:
    """True if it landed on the clipboard. macOS only; silent elsewhere."""
    if sys.platform != "darwin":
        return False
    try:
        subprocess.run(["pbcopy"], input=text.encode(), check=True)
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    who = p.add_mutually_exclusive_group()
    who.add_argument("--reviewer", action="store_true",
                     help="the clinician account instead of the admin one")
    who.add_argument("--email", default=None,
                     help="any account; its password must be the shared one")
    p.add_argument("--password", default=None,
                   help="override the password in logs/demo-accounts.txt")
    p.add_argument("--raw", action="store_true",
                   help="print the token alone, for piping into curl")
    args = p.parse_args()

    email = args.email or (f"demo.reviewer@{DOMAIN}" if args.reviewer
                           else f"demo.admin@{DOMAIN}")
    password = args.password or existing_password()
    if not password:
        raise SystemExit(
            f"No password found in {CREDENTIALS_FILE}.\n"
            "Run `python scripts/seed_demo_accounts.py` first, or pass "
            "--password.")

    url, key = supabase_credentials()
    token = fetch_token(url, key, email, password)
    snippet = f'document.cookie = "sb-access-token={token}; path=/"'

    if args.raw:
        print(token)
        return 0

    copied = copy_to_clipboard(snippet)
    print(f"account  {email}")
    print("expires  in about an hour\n")
    print("1. Open  http://localhost:8000/admin")
    print("2. Open DevTools  (⌥⌘I)  ->  Console")
    if copied:
        print("3. Paste (⌘V) and press Return  -- the line is on your clipboard")
    else:
        print("3. Paste the line below and press Return")
    print("4. Reload the page\n")
    if not copied:
        print(snippet)
        print()
    print("If /admin still shows a blank 404: the cookie must be on "
          "localhost:8000\nwith path / -- check DevTools -> Application -> "
          "Cookies. Every refusal\nlooks the same, so work through "
          "docs/process/LOCAL_ADMIN_ACCESS.md in order.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
