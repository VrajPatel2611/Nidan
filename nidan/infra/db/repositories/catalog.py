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

from nidan.infra.db.repositories.base import Repository


class CatalogRepository(Repository):
    """The two master menus. Read-only; T-044 gives admins the editor."""

    def examinations(self) -> Sequence[Mapping[str, object]]:
        return self._menu("examinations")

    def investigations(self) -> Sequence[Mapping[str, object]]:
        return self._menu("investigations")

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
