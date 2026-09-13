"""
Typed configuration (BUILD_PLAN T-006).

Every setting the application reads, in one place, validated once at start-up.

The point is **fail fast**. Configuration read ad hoc with `os.getenv` fails at
the moment the value is first used — which for `GROQ_API_KEY` is the learner's
first question, a third of the way into a consultation. A typo in a variable
name does not fail at all: `getenv` returns None and the code carries on with a
default nobody chose.

Validating at boot converts both into a container that refuses to start, with a
message naming the variable.

This module sits in the package root rather than in `infra/` because `api/` and
`infra/` both read it, and `domain/` reads nothing (ADR-0009).
"""

from __future__ import annotations

import sys

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration, loaded from the environment and `.env`.

    Field order is the order things are likely to break in.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",          # unknown variables are the platform's business
    )

    # ── the language model ───────────────────────────────────────────
    GROQ_API_KEY: str = Field(
        default="",
        description="Groq API key. The app starts without one — the gateway "
                    "builds its client lazily — but the patient will not reply.",
    )
    GROQ_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="Default model for every purpose. Per-purpose overrides use "
                    "GROQ_MODEL_<PURPOSE>; see infra/llm/gateway.py (ADR-0011).",
    )

    # ── the web application ──────────────────────────────────────────
    FLASK_SECRET_KEY: str = Field(
        default="",
        description="Signs browser session cookies. Empty means a random key "
                    "per process — which since T-013 means per gunicorn WORKER, "
                    "so workers reject each other's sessions. Required in "
                    "production; see _require_a_secret_in_production below.",
    )
    PORT: int = Field(default=8000, ge=1, le=65535)
    DEBUG: bool = Field(
        default=False,
        description="Flask debug mode. Never true in production — the debugger "
                    "offers remote code execution (SECURITY_SPEC §3, T5).",
    )

    # ── observability (T-007) ────────────────────────────────────────
    LOG_LEVEL: str = Field(
        default="INFO",
        description="DEBUG | INFO | WARNING | ERROR. Raw question text is never "
                    "logged at INFO or above (TECH_SPEC §10).",
    )
    ENVIRONMENT: str = Field(
        default="development",
        description="development | staging | production. Tags Sentry events so "
                    "a staging error is not investigated as a live one.",
    )
    SENTRY_DSN: str = Field(
        default="",
        description="Empty disables error reporting — the normal state locally "
                    "and in tests.",
    )
    RELEASE: str = Field(
        default="",
        description="Version tag for Sentry. Defaults to the package version.",
    )

    # ── commercial limits (T-017) ────────────────────────────────────
    FREE_TIER_SESSIONS_PER_MONTH: int = Field(
        default=3, ge=0, le=1000,
        description="Cases a free user may start per calendar month, in their "
                    "own timezone (PRD FR-10.1, decided 11 Sep 2026). "
                    "CONFIGURED, NOT SCHEMA — changing the number must never "
                    "need a migration, because it is a pricing decision and "
                    "pricing decisions change faster than schemas. Pro is "
                    "unlimited. Every started session counts, including "
                    "abandoned ones (PRD FR-3 edge cases).",
    )

    # ── authentication (T-014) ───────────────────────────────────────
    SUPABASE_URL: str = Field(
        default="",
        description="Supabase project URL, e.g. https://abc123.supabase.co. "
                    "The JWKS endpoint and the expected token issuer are both "
                    "derived from it, so they cannot disagree.",
    )
    SUPABASE_JWT_AUDIENCE: str = Field(
        default="authenticated",
        description="The `aud` claim every user token must carry. Supabase "
                    "issues 'authenticated'. Verified on every request: without "
                    "an audience check, a token from ANY other Supabase project "
                    "would pass signature verification and authenticate as "
                    "whatever `sub` it names.",
    )

    # ── the database (unused until T-012) ────────────────────────────
    DATABASE_URL: str = Field(
        default="",
        description="PostgreSQL connection string. Set by docker-compose. "
                    "Nothing reads it yet — schema and repositories are T-010/T-012.",
    )

    @field_validator("LOG_LEVEL")
    @classmethod
    def _known_log_level(cls, v: str) -> str:
        """
        A misspelt level would otherwise be accepted by logging and silently
        produce no output at all — the worst possible failure for a logger.
        """
        level = v.strip().upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}, not {v!r}")
        return level

    @field_validator("ENVIRONMENT")
    @classmethod
    def _known_environment(cls, v: str) -> str:
        env = v.strip().lower()
        allowed = {"development", "test", "staging", "production"}
        if env not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {sorted(allowed)}, not {v!r}")
        return env

    @field_validator("GROQ_API_KEY")
    @classmethod
    def _reject_placeholder_key(cls, v: str) -> str:
        """
        Catch the copied-but-not-filled-in `.env`.

        Someone who copies `.env.example` and forgets to paste a real key gets a
        401 from Groq in the middle of a consultation. Naming it at boot is
        cheaper than debugging it from a failed consultation.
        """
        placeholders = {
            "your-groq-api-key-here", "your-api-key-here", "changeme",
            "xxx", "todo", "replace-me", "<your-key>",
        }
        if v.strip().lower() in placeholders:
            raise ValueError(
                "GROQ_API_KEY is still the placeholder from .env.example. "
                "Put a real key in .env, or leave it empty to run without a "
                "patient."
            )
        return v

    @model_validator(mode="after")
    def _require_a_secret_in_production(self) -> Settings:
        """
        Production must set a real key. This became a hard requirement in T-013.

        `app.py` falls back to `os.urandom(24)` when the key is empty, and
        gunicorn imports the application separately in each worker — so with
        `--workers 2` every worker signs session cookies with a different
        secret and rejects the cookies the other one issued. The learner sees
        "No active session" at random, on roughly half their requests, with
        nothing in the logs to explain it.

        At `--workers 1` the same setting was merely inconvenient: sessions did
        not survive a restart. Raising the worker count is what turned it into
        a broken application, so the check belongs to the task that raised it.

        Development and tests keep the random fallback; only production
        refuses.
        """
        if self.ENVIRONMENT == "production" and not self.FLASK_SECRET_KEY.strip():
            raise ValueError(
                "FLASK_SECRET_KEY must be set in production: without it each "
                "gunicorn worker signs session cookies with its own random key "
                "and rejects the others'. Generate one with "
                "python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return self

    @field_validator("FLASK_SECRET_KEY")
    @classmethod
    def _reject_known_weak_secret(cls, v: str) -> str:
        """
        The compose default must never reach a deployed environment.

        docker-compose.yml sets a fixed development secret so sessions survive a
        restart locally. Shipped, it lets anyone forge a session cookie.
        """
        if v.strip() == "local-development-only-not-a-secret":
            raise ValueError(
                "FLASK_SECRET_KEY is the docker-compose development default. "
                "Generate a real one: python -c \"import secrets; "
                "print(secrets.token_hex(32))\""
            )
        return v

    # ── derived ──────────────────────────────────────────────────────
    @property
    def release_tag(self) -> str:
        """Sentry release. Falls back to the package version."""
        if self.RELEASE.strip():
            return self.RELEASE.strip()
        from nidan import __version__
        return f"nidan@{__version__}"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def llm_configured(self) -> bool:
        """Whether a patient can actually reply."""
        return bool(self.GROQ_API_KEY.strip())

    @property
    def auth_configured(self) -> bool:
        """Whether a token can be verified at all."""
        return bool(self.SUPABASE_URL.strip())

    @property
    def jwks_url(self) -> str:
        """
        Where the signing keys live.

        Derived rather than configured separately: two settings that must agree
        are two settings that can disagree, and the failure would be a project
        verifying tokens against another project's keys.
        """
        return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def jwt_issuer(self) -> str:
        """The `iss` claim every token must carry. Derived, for the same reason."""
        return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1"


def load_settings() -> Settings:
    """
    Build settings, or exit with a message a human can act on.

    Deliberately `SystemExit` rather than a raised ValidationError: this runs at
    import time in a container, and pydantic's default traceback buries the one
    line that matters under a stack.
    """
    try:
        return Settings()
    except ValidationError as e:
        print("\nNidan cannot start — configuration is invalid:\n", file=sys.stderr)
        for err in e.errors():
            field = ".".join(str(p) for p in err["loc"]) or "(root)"
            print(f"  {field}: {err['msg']}", file=sys.stderr)
        print("\nSee .env.example for every variable and what it does.\n",
              file=sys.stderr)
        raise SystemExit(78) from e   # EX_CONFIG, sysexits.h


# Module-level singleton. Import this, do not construct Settings() yourself —
# otherwise `.env` is re-read per call and validation errors surface late.
settings = load_settings()
