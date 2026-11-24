"""
The column list every `leakage_flags` read selects.

Its own module so that `LeakageRepository` and the trial subclass in
`anonymous.py` cannot drift apart, and so a column added to the table has one
place to be added to rather than four query strings to be found in.

`c.slug` is here, not `cv.case_id`: `case_versions.case_id` is a UUID
referencing `cases(id)`, and the human-readable name is `cases.slug`. An
administrator triaging the queue needs to know which persona is leaking,
and either UUID tells them nothing without a second lookup — which is why
every read here joins `cases` as well as `case_versions`.
"""

from __future__ import annotations

from typing import Final

COLUMNS: Final[str] = """
    f.id, f.session_id, f.event_seq, f.leaked_topics, f.severity,
    f.reviewed, f.confirmed, f.reviewed_by, f.reviewed_at, f.created_at,
    c.slug AS case_slug, cv.version AS case_version,
    cv.title AS case_title, s.status AS session_status
"""
