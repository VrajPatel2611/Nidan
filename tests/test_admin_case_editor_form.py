"""
The case editor's form round-trips a case without losing anything (T-021 fix).

The form used to rebuild the whole content dict from its fields. Every field it
did not render — exam `key` flags, investigation categories other than "key",
`alternative_topics` (saved under another name), `patient.intro` (read and
written under another name), a free-text `anchor_topic` (offered only as a
dropdown of lexicon keys) — was silently replaced or dropped on the first save.
Examinations and investigations were set to `{}` outright.

So the test is the plainest one there is: open a real case in the editor,
submit the form exactly as a browser would without touching anything, and the
stored content must be identical. Then change one field, and only that field
may change.

Against copies of the five seeded cases in a real database, so the form under
test is the one the template actually renders.
"""

from __future__ import annotations

import copy
import uuid
from html.parser import HTMLParser

import pytest
import sqlalchemy as sa

from nidan.app import create_app
from nidan.domain.content.cases import MASTER_EXAMINATIONS, MASTER_INVESTIGATIONS
from nidan.infra.db.repositories import AdminUser, repo_scope

pytestmark = pytest.mark.usefixtures("live_db")

SEEDED = ("chest-pain-gerd", "breathlessness-pulmonary-embolism",
          "confusion-delirium-uti", "fatigue-hypothyroidism",
          "vomiting-diabetic-ketoacidosis")


class _Form(HTMLParser):
    """The fields of #case-editor-form, as a browser would submit them."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fields: list[tuple[str, str]] = []
        self._in_form = False
        self._textarea: str | None = None
        self._select: str | None = None
        self._options: list[tuple[str, bool]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form" and a.get("id") == "case-editor-form":
            self._in_form = True
        if not self._in_form:
            return
        if tag == "input" and a.get("name"):
            kind = a.get("type", "text")
            if kind == "checkbox" and "checked" not in a:
                return
            self.fields.append((a["name"], a.get("value", "on" if kind == "checkbox" else "")))
        elif tag == "textarea" and a.get("name"):
            self._textarea, self._text = a["name"], ""
        elif tag == "select" and a.get("name"):
            self._select, self._options = a["name"], []
        elif tag == "option" and self._select:
            self._options.append((a.get("value", ""), "selected" in a))

    def handle_data(self, data):
        if self._textarea is not None:
            self._text += data

    def handle_endtag(self, tag):
        if tag == "form":
            self._in_form = False
        elif tag == "textarea" and self._textarea is not None:
            # A browser drops one leading newline after <textarea>.
            text = self._text[1:] if self._text.startswith("\n") else self._text
            self.fields.append((self._textarea, text))
            self._textarea = None
        elif tag == "select" and self._select:
            chosen = [v for v, sel in self._options if sel] or [self._options[0][0]]
            self.fields.append((self._select, chosen[0]))
            self._select = None


def _form_of(html: str) -> dict[str, list[str]]:
    parser = _Form()
    parser.feed(html)
    data: dict[str, list[str]] = {}
    for name, value in parser.fields:
        data.setdefault(name, []).append(value)
    return data


@pytest.fixture
def admin(live_db, authority):
    uid = uuid.uuid4()
    with live_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": uid})
        c.execute(sa.text("INSERT INTO profiles (id, platform_role) VALUES (:id, 'admin')"),
                  {"id": uid})
    yield uid, {"Authorization": f"Bearer {authority.token(sub=str(uid))}"}
    with live_db.begin() as c:
        # TRUNCATE, because audit_log refuses DELETE by design; the test
        # database holds no audit rows worth keeping.
        c.exec_driver_sql("TRUNCATE audit_log")
        c.execute(sa.text("DELETE FROM profiles WHERE id = :id"), {"id": uid})
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": uid})


@pytest.fixture
def copy_of(live_db, admin):
    """A fresh draft holding a seeded case's content, removed afterwards."""
    made: list[uuid.UUID] = []

    def _copy(slug: str):
        with live_db.connect() as c:
            content = c.execute(sa.text(
                "SELECT cv.content FROM case_versions cv JOIN cases c ON c.id = cv.case_id "
                "WHERE c.slug = :s"), {"s": slug}).scalar_one()
        with repo_scope(AdminUser(admin[0])) as db:
            case_id = db.cases.create_case(slug=f"copy-{uuid.uuid4().hex[:8]}")
            version_id = db.cases.create_draft(case_id, content)
        made.append(case_id)
        return case_id, version_id, content

    yield _copy

    with live_db.begin() as c:
        for case_id in made:
            c.execute(sa.text("DELETE FROM case_versions WHERE case_id = :id"), {"id": case_id})
            c.execute(sa.text("DELETE FROM cases WHERE id = :id"), {"id": case_id})


@pytest.fixture
def client(live_db, authority):
    return create_app({"TESTING": True, "SECRET_KEY": "t021-form"}).test_client()


def _stored(live_db, version_id):
    with live_db.connect() as c:
        return c.execute(sa.text("SELECT content FROM case_versions WHERE id = :id"),
                         {"id": version_id}).scalar_one()


def _open_and_save(client, headers, case_id, version_id, edit=None):
    url = f"/admin/cases/{case_id}/versions/{version_id}"
    page = client.get(url, headers=headers)
    assert page.status_code == 200
    data = _form_of(page.get_data(as_text=True))
    if edit:
        edit(data)
    res = client.post(f"{url}/save", headers=headers, data=data)
    assert res.status_code == 302, res.get_data(as_text=True)


@pytest.mark.parametrize("slug", SEEDED)
def test_saving_an_untouched_form_changes_nothing(client, admin, copy_of, live_db, slug):
    case_id, version_id, original = copy_of(slug)
    _open_and_save(client, admin[1], case_id, version_id)
    assert _stored(live_db, version_id) == original


def test_editing_one_finding_changes_only_that_finding(client, admin, copy_of, live_db):
    case_id, version_id, original = copy_of("chest-pain-gerd")

    def edit(data):
        data["exam_vitals"] = ["HR 110 bpm, febrile."]

    _open_and_save(client, admin[1], case_id, version_id, edit)

    expected = copy.deepcopy(original)
    expected["examination"]["vitals"]["finding"] = "HR 110 bpm, febrile."
    assert _stored(live_db, version_id) == expected


def test_a_new_finding_and_a_new_test_are_added(client, admin, copy_of, live_db):
    case_id, version_id, original = copy_of("chest-pain-gerd")
    exam = next(k for k in MASTER_EXAMINATIONS if k not in original["examination"])
    test = next(k for k in MASTER_INVESTIGATIONS if k not in original["investigations"])

    def edit(data):
        data[f"exam_{exam}"] = ["New finding."]
        data[f"test_result_{test}"] = ["New result."]
        data[f"test_key_{test}"] = ["key"]

    _open_and_save(client, admin[1], case_id, version_id, edit)
    stored = _stored(live_db, version_id)

    assert stored["examination"][exam]["finding"] == "New finding."
    assert stored["examination"][exam]["key"] is False
    assert stored["investigations"][test]["result"] == "New result."
    assert stored["investigations"][test]["category"] == "key"


def test_clearing_a_result_removes_the_test_and_unticking_key_demotes_it(
        client, admin, copy_of, live_db):
    case_id, version_id, original = copy_of("chest-pain-gerd")
    assert original["investigations"]["ecg"]["category"] == "key"
    assert original["investigations"]["d_dimer"]["category"] == "low_value"

    def edit(data):
        data.pop("test_key_ecg")
        data["test_result_fbc"] = [""]

    _open_and_save(client, admin[1], case_id, version_id, edit)
    stored = _stored(live_db, version_id)

    assert stored["investigations"]["ecg"]["category"] == "reasonable"
    assert "fbc" not in stored["investigations"]
    assert stored["investigations"]["d_dimer"]["category"] == "low_value"


def test_an_examination_box_shows_the_finding_text_not_the_stored_object(
        client, admin, copy_of):
    case_id, version_id, original = copy_of("chest-pain-gerd")
    page = client.get(f"/admin/cases/{case_id}/versions/{version_id}", headers=admin[1])
    data = _form_of(page.get_data(as_text=True))
    assert data["exam_vitals"] == [original["examination"]["vitals"]["finding"]]
