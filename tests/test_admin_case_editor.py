"""
Admin Case Editor Tests (BUILD_PLAN T-021, UX_SPEC §12.4).

Tests for C-4 validation enforcement, draft creation from published versions,
concurrent edit protection, 404 security rules, and audit logging.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from nidan.app import create_app
from nidan.infra.db.repositories.cases import ConcurrentEdit


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-used")
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret")
    app = create_app({"TESTING": True})
    return app.test_client()


# ── 1. Editor 404 Access Control ─────────────────────────────────────

def test_editor_route_404s_for_unauthorized(client, authority):
    """
    Anonymous and non-admin users get 404 on editor routes.
    """
    case_id = uuid4()
    version_id = uuid4()
    url = f"/admin/cases/{case_id}/versions/{version_id}"

    # Anonymous -> 404
    res_anon = client.get(url)
    assert res_anon.status_code == 404

    # Non-admin user -> 404
    user_id = uuid4()
    token = authority.token(sub=str(user_id))
    mock_profile = {"id": user_id, "platform_role": "user"}

    mock_db = MagicMock()
    mock_db.profiles.get.return_value = mock_profile

    with patch("nidan.api.auth.repo_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = mock_db
        res_user = client.get(url, headers={"Authorization": f"Bearer {token}"})

    assert res_user.status_code == 404
    assert res_anon.data == res_user.data  # Identical 404 response


# ── 2. C-4 Violation Blocks Saving ───────────────────────────────────

def test_case_with_c4_violation_cannot_be_saved(client, authority):
    """
    C-4 invariant violation (anchor keyword overlapping contradictory clue)
    blocks saving with a 400 refusal.
    """
    admin_id = uuid4()
    case_id = uuid4()
    version_id = uuid4()
    token = authority.token(sub=str(admin_id))

    mock_profile = {"id": admin_id, "platform_role": "admin"}
    mock_db = MagicMock()
    mock_db.profiles.get.return_value = mock_profile
    mock_db.cases.for_editing.return_value = {
        "id": version_id,
        "case_id": case_id,
        "version": 1,
        "status": "draft",
        "title": "Chest Pain",
        "updated_at": datetime.now(UTC),
    }

    # Payload with C-4 violation: anchor "heart" vs clue "heartburn"
    invalid_content = {
        "title": "Chest Pain",
        "anchor_topic": "cardiac",
        "anchor_keywords": ["heart", "cardiac"],
        "contradictory_clues": [["heartburn", "acid"]],
        "accepted_diagnoses": ["GERD", "Reflux"],
        "minimum_questions": 7,
        "required_topics": ["pain_character"],
        "investigations": {"ecg": {"category": "key"}},
    }

    with patch("nidan.api.auth.repo_scope") as mock_auth_scope, \
         patch("nidan.web.admin.cases.routes.repo_scope") as mock_route_scope:
        mock_auth_scope.return_value.__enter__.return_value = mock_db
        mock_route_scope.return_value.__enter__.return_value = mock_db

        res = client.post(
            f"/admin/cases/{case_id}/versions/{version_id}/save",
            json=invalid_content,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 400
    json_data = res.get_json()
    assert json_data["error"] == "c4_violation"
    assert "collisions" in json_data
    assert any("heart" in col for col in json_data["collisions"])
    mock_db.cases.update_draft.assert_not_called()


def test_c4_error_names_offending_term_and_clue_set(client, authority):
    """
    C-4 refusal explicitly names the colliding anchor term and clue set.
    """
    admin_id = uuid4()
    case_id = uuid4()
    version_id = uuid4()
    token = authority.token(sub=str(admin_id))

    mock_profile = {"id": admin_id, "platform_role": "admin"}
    mock_db = MagicMock()
    mock_db.profiles.get.return_value = mock_profile
    mock_db.cases.for_editing.return_value = {
        "id": version_id,
        "case_id": case_id,
        "version": 1,
        "status": "draft",
        "updated_at": datetime.now(UTC),
    }

    colliding_content = {
        "title": "Test Case",
        "anchor_topic": "cardiac",
        "anchor_keywords": ["angina"],
        "contradictory_clues": [["normal"], ["angina pain"]],
        "accepted_diagnoses": ["A", "B"],
        "minimum_questions": 5,
        "required_topics": ["topic"],
        "investigations": {"test": {"category": "key"}},
    }

    with patch("nidan.api.auth.repo_scope") as mock_auth_scope, \
         patch("nidan.web.admin.cases.routes.repo_scope") as mock_route_scope:
        mock_auth_scope.return_value.__enter__.return_value = mock_db
        mock_route_scope.return_value.__enter__.return_value = mock_db

        res = client.post(
            f"/admin/cases/{case_id}/versions/{version_id}/save",
            json=colliding_content,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 400
    collisions = res.get_json()["collisions"]
    assert len(collisions) >= 1
    assert 'anchor "angina"' in collisions[0]
    assert 'clue[1] "angina pain"' in collisions[0]


# ── 3. Saving Published Version Creates New Draft ────────────────────

def test_saving_edit_to_published_version_creates_new_draft(client, authority):
    """
    Saving an edit to a published version creates a new draft version.
    """
    admin_id = uuid4()
    case_id = uuid4()
    published_version_id = uuid4()
    new_draft_id = uuid4()
    token = authority.token(sub=str(admin_id))

    mock_profile = {"id": admin_id, "platform_role": "admin"}
    mock_db = MagicMock()
    mock_db.profiles.get.return_value = mock_profile
    mock_db.cases.for_editing.return_value = {
        "id": published_version_id,
        "case_id": case_id,
        "version": 2,
        "status": "published",
    }
    mock_db.cases.create_draft.return_value = new_draft_id

    valid_content = {
        "title": "Published Case Edit",
        "anchor_topic": "cardiac",
        "anchor_keywords": ["mi", "ecg"],
        "contradictory_clues": [["reflux"], ["gerd"], ["acid"], ["antacid"]],
        "accepted_diagnoses": ["GERD", "Reflux"],
        "minimum_questions": 7,
        "required_topics": ["pain_character"],
        "investigations": {"ecg": {"category": "key"}},
    }

    with patch("nidan.api.auth.repo_scope") as mock_auth_scope, \
         patch("nidan.web.admin.cases.routes.repo_scope") as mock_route_scope:
        mock_auth_scope.return_value.__enter__.return_value = mock_db
        mock_route_scope.return_value.__enter__.return_value = mock_db

        res = client.post(
            f"/admin/cases/{case_id}/versions/{published_version_id}/save",
            json=valid_content,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["status"] == "created_draft"
    assert json_data["new_version_id"] == str(new_draft_id)
    mock_db.cases.create_draft.assert_called_once()
    mock_db.audit.record.assert_called_once()


# ── 4. Concurrent Edit Protection ────────────────────────────────────

def test_stale_updated_at_refused_concurrent_edit(client, authority):
    """
    A save carrying a stale updated_at timestamp is refused with a 409 concurrent edit error.
    """
    admin_id = uuid4()
    case_id = uuid4()
    version_id = uuid4()
    token = authority.token(sub=str(admin_id))

    mock_profile = {"id": admin_id, "platform_role": "admin"}
    mock_db = MagicMock()
    mock_db.profiles.get.return_value = mock_profile
    mock_db.cases.for_editing.return_value = {
        "id": version_id,
        "case_id": case_id,
        "version": 1,
        "status": "draft",
        "updated_at": datetime.now(UTC),
    }
    mock_db.cases.update_draft.side_effect = ConcurrentEdit("Changed by someone else")

    valid_content = {
        "title": "Draft Edit",
        "anchor_topic": "cardiac",
        "anchor_keywords": ["mi"],
        "contradictory_clues": [["reflux"]],
        "accepted_diagnoses": ["A", "B"],
        "minimum_questions": 5,
        "required_topics": ["topic"],
        "investigations": {"ecg": {"category": "key"}},
        "expected_updated_at": "2026-01-01T00:00:00+00:00",
    }

    with patch("nidan.api.auth.repo_scope") as mock_auth_scope, \
         patch("nidan.web.admin.cases.routes.repo_scope") as mock_route_scope:
        mock_auth_scope.return_value.__enter__.return_value = mock_db
        mock_route_scope.return_value.__enter__.return_value = mock_db

        res = client.post(
            f"/admin/cases/{case_id}/versions/{version_id}/save",
            json=valid_content,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 409
    assert res.get_json()["error"] == "concurrent_edit"
