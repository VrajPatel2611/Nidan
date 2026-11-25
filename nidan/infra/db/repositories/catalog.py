"""
The universal examination and investigation menus (`API_CONTRACT` §5).

**Reads the master lists, and nothing case-specific.** `examinations` and
`investigations` hold the menu every learner sees on every case; which of them
matters for the case in front of them lives in `case_versions.content` and is
never joined here. `PRD` FR-5.1 and FR-6.1 are the reason: if the menu differed
by case, the menu would be the answer.

That is contract test CT-3, and this repository is where it is cheapest to
honour — the SELECT does not name a column that could leak relevance, so no
later serialiser has to remember to drop one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from nidan.infra.db.repositories.base import Repository

# The two master lists the editor may touch, with the case-content key that
# references each and the column only investigations have. A lookup rather
# than a parameter: every f-string below interpolates from here, so a table
# name never comes from a request. A KeyError on anything else is the guard.
_COLUMNS: dict[str, tuple[str, str]] = {
    "examinations":   ("examination",    "NULL"),
    "investigations": ("investigations", "m.reference_range"),
}


class DuplicateKey(ValueError):
    """The key is taken, by a live item or a retired one. Keys are never reused."""


def _known(table: str) -> None:
    if table not in _COLUMNS:
        raise ValueError(f"not a catalogue table: {table!r}")


class CatalogRepository(Repository):
    """The two master menus: the learner's read, and T-044's editor."""

    def examinations(self) -> Sequence[Mapping[str, object]]:
        return self._menu("examinations")

    def investigations(self) -> Sequence[Mapping[str, object]]:
        return self._menu("investigations")

    def master_entry(self, table: str, key: str) -> Mapping[str, object] | None:
        """
        One master-list row INCLUDING `normal_result`, or None if the key is
        unknown. Server-side only.

        `normal_result` is deliberately absent from `_menu` above: it is the
        text a learner sees when they order something irrelevant, and shipping
        all 91 of them in the catalogue response would let a client diff them
        against what a case actually returns — the CT-3 leak by a longer
        route. Ordering needs it, and ordering returns exactly one.

        Returning the row rather than a bool also collapses two questions
        into one query. "Is this a real key?" and "what is the normal
        finding?" have the same answer, and asking separately invites a
        handler that checks one and forgets the other.
        """
        if table not in ("examinations", "investigations"):   # pragma: no cover
            raise ValueError(f"not a catalogue table: {table!r}")
        return self._conn.execute(sa.text(
            f"SELECT key, label, normal_result FROM {table} "  # noqa: S608
            f"WHERE key = :key AND is_active"
        ), {"key": key}).mappings().first()

    # ── the clinical-content editor (T-044, `UX_SPEC` A-06) ──────────────

    def admin_list(self, table: str) -> Sequence[Mapping[str, object]]:
        """
        Every row, inactive ones included, with how many cases use each key.

        **"Used by" counts the latest live version of each case**, drafts
        included, the same way `CaseRepository.bank()` lists them. An author
        retiring an item needs to know whether a case they are still writing
        depends on it, and a count of published cases only would say "0" for
        all ten of today's drafts.

        Case content keys these as `examination` (singular) and
        `investigations`, which is the domain's shape (`cases.py`), not a typo
        here.
        """
        self._require_admin("the clinical-content editor")
        _known(table)
        column, normal = _COLUMNS[table]
        return self._conn.execute(sa.text(f"""
            WITH latest AS (
              SELECT DISTINCT ON (case_id) case_id, content
                FROM case_versions
               WHERE retired_at IS NULL
            ORDER BY case_id, version DESC
            )
            SELECT m.key, m.label, m.group_name, m.normal_result,
                   {normal} AS reference_range,
                   m.display_order, m.is_active,
                   (SELECT count(*) FROM latest
                     WHERE latest.content -> '{column}' ? m.key) AS used_by
              FROM {table} m
          ORDER BY m.display_order
        """)).mappings().all()  # noqa: S608 — table and column are from _COLUMNS

    def admin_entry(self, table: str, key: str) -> Mapping[str, object] | None:
        """One row for the edit form, or None. Inactive rows included."""
        return next((r for r in self.admin_list(table) if r["key"] == key), None)

    def case_count(self) -> int:
        """How many live cases a new item would appear on — A-06's warning."""
        return int(self._conn.execute(sa.text(
            "SELECT count(DISTINCT case_id) FROM case_versions "
            "WHERE retired_at IS NULL")).scalar_one())

    def add_entry(self, table: str, *, key: str, label: str, group_name: str,
                  normal_result: str,
                  reference_range: str | None = None) -> Mapping[str, object]:
        """
        A new menu item, at the end of the menu.

        `display_order` is max + 1 so the menu learners see stays dense and
        tie-free, which `tests/db/test_seed.py` asserts for the seeded list.
        A duplicate key raises `DuplicateKey`; the route turns that into a
        sentence, because a key that already exists is a typo, not a crash.
        """
        self._require_admin("adding a menu item")
        _known(table)
        params = {"key": key, "label": label, "group": group_name,
                  "normal": normal_result}
        extra_col = extra_val = ""
        if table == "investigations":
            extra_col, extra_val = ", reference_range", ", :ref"
            params["ref"] = reference_range or None
        statement = sa.text(f"""
            INSERT INTO {table} (key, label, group_name, normal_result,
                                 display_order{extra_col})
            VALUES (:key, :label, :group, :normal,
                    (SELECT COALESCE(max(display_order) + 1, 0) FROM {table})
                    {extra_val})
            RETURNING key, label, group_name, display_order
        """)  # noqa: S608
        try:
            # A savepoint, so a duplicate key leaves the caller's transaction
            # usable for the audit row and the re-rendered form.
            with self._conn.begin_nested():
                return self._conn.execute(statement, params).mappings().one()
        except IntegrityError:
            raise DuplicateKey(key) from None

    def update_entry(self, table: str, key: str, *, label: str,
                     group_name: str, normal_result: str,
                     reference_range: str | None = None) -> bool:
        """
        Change everything except the key.

        **The key is not a parameter, so it cannot be changed.** `UX_SPEC`
        A-06: keys appear inside stored session events, and a renamed key
        would leave every historical `investigation` event pointing at
        nothing. Editing `normal_result` affects future sessions only, since
        each session stores the result it was shown.
        """
        self._require_admin("editing a menu item")
        _known(table)
        params = {"key": key, "label": label, "group": group_name,
                  "normal": normal_result}
        extra = ""
        if table == "investigations":
            extra = ", reference_range = :ref"
            params["ref"] = reference_range or None
        return self._conn.execute(sa.text(f"""
            UPDATE {table}
               SET label = :label, group_name = :group,
                   normal_result = :normal{extra}
             WHERE key = :key
        """), params).rowcount == 1  # noqa: S608

    def set_active(self, table: str, key: str, active: bool) -> bool:
        """
        Retire or restore an item. The only removal there is.

        No `delete_entry` exists and migration 036 grants no DELETE, so a
        route that tried would be refused twice. A retired item drops out of
        `_menu` (the learner's menu) and `master_entry` (ordering), and a case
        that still references it keeps its stored results.
        """
        self._require_admin("retiring a menu item")
        _known(table)
        return self._conn.execute(sa.text(
            f"UPDATE {table} SET is_active = :a WHERE key = :key"  # noqa: S608
        ), {"a": active, "key": key}).rowcount == 1

    def _require_admin(self, what: str) -> None:
        from nidan.infra.db.actor import AdminUser
        if not isinstance(self._actor, AdminUser):
            raise PermissionError(
                f"{what} writes clinical content and needs an AdminUser; this "
                f"scope was opened as {type(self._actor).__name__}")

    def _menu(self, table: str) -> Sequence[Mapping[str, object]]:
        """
        One shape for both, because the contract gives them one shape.

        `table` is interpolated, which is safe only because the two callers
        above are the only callers and both pass a literal. It is not a
        parameter the API can reach: §5 declares two endpoints, not a
        table-name lookup.
        """
        if table not in ("examinations", "investigations"):   # pragma: no cover
            raise ValueError(f"not a catalogue table: {table!r}")
        return self._conn.execute(sa.text(
            f"SELECT key, label, group_name, display_order "  # noqa: S608
            f"FROM {table} WHERE is_active ORDER BY display_order"
        )).mappings().all()
