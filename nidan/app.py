"""
Application factory.

Builds the Flask app and registers blueprints. Kept deliberately thin: it wires
components together and does nothing else.
"""

import os

from flask import Flask, g, jsonify, request

from nidan.api.routes import bp as web_bp
from nidan.api.v1 import bp as v1_bp
from nidan.config import settings
from nidan.infra.telemetry import (
    bind,
    get_logger,
    new_request_id,
    setup_telemetry,
)

logger = get_logger(__name__)


def create_app(config: dict | None = None) -> Flask:
    """
    Construct the Flask application.

    A factory rather than a module-level app so tests can build an isolated
    instance, and so configuration is injected rather than read at import time.

    Configuration is validated in nidan.config before this runs, so an invalid
    environment fails at start-up rather than mid-consultation (T-006).
    """
    app = Flask(
        __name__,
        template_folder="web/templates",
        static_folder="web/static",
    )

    # A fixed key keeps sessions valid across restarts and, since T-013, across
    # WORKERS: gunicorn imports this module separately in each worker, so an
    # unset key means every worker signs cookies with a different random secret
    # and rejects the others' sessions. At --workers 1 that was merely
    # inconvenient; at 2 it is a broken application, which is why config.py now
    # refuses to start in production without one.
    #
    # The random fallback stays, so a missing key never blocks local
    # development or a test. Validation of the key itself happens once, at
    # import, in nidan.config.
    app.secret_key = settings.FLASK_SECRET_KEY or os.urandom(24)

    if config:
        app.config.update(config)
        # After the update, so a caller can pin the key explicitly — which is
        # what a test needs when it builds two applications that must read each
        # other's cookies.
        if "SECRET_KEY" in config:
            app.secret_key = config["SECRET_KEY"]

    setup_telemetry()
    _register_request_logging(app)
    _register_health_endpoints(app)

    app.register_blueprint(web_bp)
    from nidan.web.admin import bp as admin_bp
    app.register_blueprint(admin_bp)
    # The JSON API (T-014). Mounted at /v1 to match openapi.yaml's
    # servers block; the prototype's server-rendered routes keep the
    # root until T-030 replaces them.
    app.register_blueprint(v1_bp, url_prefix="/v1")
    return app


def _register_request_logging(app: Flask) -> None:
    """
    One log line per request, carrying a correlation id.

    The id is taken from an inbound `X-Request-ID` when present, so a trace
    survives a proxy, and echoed on the response so a user reporting a problem
    can quote something findable.
    """
    import time

    @app.before_request
    def _start_request() -> None:
        g._t0 = time.perf_counter()
        g.request_id = request.headers.get("X-Request-ID") or new_request_id()
        bind(request=g.request_id)

    @app.after_request
    def _log_request(response):
        duration_ms = round((time.perf_counter() - getattr(g, "_t0", 0)) * 1000, 1)
        # Health probes fire every 30s and would drown everything else.
        if request.path not in ("/healthz", "/readyz"):
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    # request.path only — a query string may carry personal data
                    # and must never be logged (SECURITY_SPEC, Privacy).
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        return response


def _register_health_endpoints(app: Flask) -> None:
    """
    Liveness and readiness (TECH_SPEC §10).

    Separate because they answer different questions. Liveness: is the process
    alive — restart me if not. Readiness: can I serve traffic — hold traffic
    back if not. Conflating them means a temporary dependency outage triggers a
    restart loop, which makes the outage worse.
    """

    @app.get("/healthz")
    def healthz():
        """Liveness. Must not touch a dependency."""
        return jsonify({"status": "ok", "release": settings.release_tag}), 200

    @app.get("/readyz")
    def readyz():
        """
        Readiness.

        TECH_SPEC §10 specifies checks for database, migrations and model
        loaded. None of those exist yet — there is no database code until T-010
        — so this reports what is true today rather than pretending. Each check
        is added as its dependency arrives.
        """
        checks = {
            "config": True,                      # validated at import (T-006)
            "cases_loaded": _cases_loaded(),
            "llm_configured": settings.llm_configured,
        }
        # llm_configured is reported, not required: the app serves the case list
        # and feedback fallback without a key.
        ready = checks["config"] and checks["cases_loaded"]
        return jsonify({"status": "ready" if ready else "not ready",
                        "checks": checks}), (200 if ready else 503)


def _cases_loaded() -> bool:
    try:
        from nidan.domain.content.cases import get_all_cases
        return len(get_all_cases()) > 0
    except Exception:          # noqa: BLE001 - a probe must never raise
        return False


# WSGI entry point: `gunicorn nidan.app:app`
app = create_app()
