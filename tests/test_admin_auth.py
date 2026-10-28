"""
Admin shell & authorization tests (BUILD_PLAN T-020, UX_SPEC §12.1).

Tests for the 404 access rule, role authorization, and audit log recording.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from nidan.app import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-used")
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret")
    app = create_app({"TESTING": True})
    return app.test_client()


# ── 1. Logged-out visitor gets 404 (NEVER 401) ───────────────────────

def test_a_logged_out_visitor_gets_404_not_401(client):
    """
    API_CONTRACT §2.7 & UX_SPEC §12.1 requirement:
    A logged-out visitor must get 404 (Not Found), never 401. Non-admins must
    not learn that an admin console exists.
    """
    res = client.get("/admin")
    assert res.status_code == 404


@pytest.mark.parametrize("subpath", ["/admin/", "/admin/cases", "/admin/reviews", "/admin/content", "/admin/ops", "/admin/users", "/admin/system"])
def test_a_logged_out_visitor_gets_404_on_all_admin_subroutes(client, subpath):
    res = client.get(subpath)
    assert res.status_code == 404


# ── 2. Non-admin user gets 404 (NEVER 403) ───────────────────────────

def test_a_non_admin_gets_404_not_403(client, authority):
    """
    API_CONTRACT §2.7 requirement:
    A authenticated user with role='user' receives 404 (Not Found), never 403.
    """
    user_id = uuid4()
    token = authority.token(sub=str(user_id))

    mock_profile = {
        "id": user_id,
        "display_name": "Learner User",
        "platform_role": "user",
        "subscription_tier": "free",
    }

    mock_db = MagicMock()
    mock_db.profiles.get.return_value = mock_profile

    with patch("nidan.api.auth.repo_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = mock_db
        res = client.get("/admin", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 404


# ── 3. Reviewer role authorization ───────────────────────────────────

def test_a_reviewer_gets_404_on_admin_only_route_but_200_on_reviews(client, authority):
    """
    Reviewers can access /admin/reviews, but get 404 on /admin and admin-only routes.
    """
    reviewer_id = uuid4()
    token = authority.token(sub=str(reviewer_id))

    mock_profile = {
        "id": reviewer_id,
        "display_name": "Dr Reviewer",
        "platform_role": "reviewer",
        "subscription_tier": "pro",
    }

    mock_db = MagicMock()
    mock_db.profiles.get.return_value = mock_profile

    with patch("nidan.api.auth.repo_scope") as mock_scope, \
         patch("nidan.web.admin.routes.repo_scope") as mock_route_scope:
        mock_scope.return_value.__enter__.return_value = mock_db
        mock_route_scope.return_value.__enter__.return_value = mock_db

        res_admin = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
        assert res_admin.status_code == 404

        res_review = client.get("/admin/reviews", headers={"Authorization": f"Bearer {token}"})
        assert res_review.status_code == 200
        assert b"Clinical Review Queue" in res_review.data


# ── 4. Admin user accesses admin shell ───────────────────────────────

def test_an_admin_user_can_access_admin_shell(client, authority):
    """
    Admin user gets 200 and renders the Jinja + HTMX shell with top nav and sidebar.
    """
    admin_id = uuid4()
    token = authority.token(sub=str(admin_id))

    mock_profile = {
        "id": admin_id,
        "display_name": "Admin User",
        "platform_role": "admin",
        "subscription_tier": "pro",
    }

    mock_db = MagicMock()
    mock_db.profiles.get.return_value = mock_profile
    mock_db.audit.recent.return_value = []

    with patch("nidan.api.auth.repo_scope") as mock_scope, \
         patch("nidan.web.admin.routes.repo_scope") as mock_route_scope:
        mock_scope.return_value.__enter__.return_value = mock_db
        mock_route_scope.return_value.__enter__.return_value = mock_db

        res = client.get("/admin", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    assert b"Nidan Admin" in res.data
    assert b"Admin Dashboard" in res.data
    assert b"Cases" in res.data
    assert b"Content" in res.data
    # Plain number in brackets, no red badges
    assert b"Review <span class=\"sidebar-count\">(3)</span>" in res.data


# ── 5. Audit log recording ───────────────────────────────────────────

def test_admin_action_records_audit_log(client, authority):
    """
    Every administrative action calls db.audit.record(...) with the actor's ID.
    """
    admin_id = uuid4()
    token = authority.token(sub=str(admin_id))

    mock_profile = {
        "id": admin_id,
        "display_name": "Admin User",
        "platform_role": "admin",
    }

    mock_db = MagicMock()
    mock_db.profiles.get.return_value = mock_profile
    mock_db.audit.record.return_value = {"id": 101, "actor_id": admin_id, "action": "case_version.published"}

    with patch("nidan.api.auth.repo_scope") as mock_scope, \
         patch("nidan.web.admin.routes.repo_scope") as mock_route_scope:
        mock_scope.return_value.__enter__.return_value = mock_db
        mock_route_scope.return_value.__enter__.return_value = mock_db

        res = client.post(
            "/admin/audit-action",
            data={"action": "case_version.published", "reason": "clinician approved", "entity_type": "case_version"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 200
    assert b"Audit log recorded ID 101" in res.data
    mock_db.audit.record.assert_called_once_with(
        action="case_version.published",
        entity_type="case_version",
        reason="clinician approved",
        metadata={"ip": "127.0.0.1"},
    )
