from unittest.mock import MagicMock

import pytest

from app.repositories import preference_repository as repo
from app.schemas.preference import Preferences


def prefs(name="HR"):
    return Preferences(name=name, email="hr@example.com", company="", retention="0", reasons=[], members=[],
                       deleted=[], jobDeleted=False)


def row(row_id, user_id, name):
    return {**prefs(name).model_dump(mode="json"), "id": row_id, "user_id": user_id, "job_deleted": False}


@pytest.fixture
def table(monkeypatch):
    sb = MagicMock()
    monkeypatch.setattr(repo, "supabase", sb)
    return sb.table.return_value


def test_each_user_writes_their_own_row(table):
    repo.update_preferences(prefs("A"), "user-a")
    repo.update_preferences(prefs("B"), "user-b")
    written = [c.args[0] for c in table.upsert.call_args_list]
    # One shared "default" primary key let the last writer take everyone's row.
    assert [(r["id"], r["user_id"]) for r in written] == [("user-a", "user-a"), ("user-b", "user-b")]


def test_get_reads_only_the_callers_rows(table):
    query = table.select.return_value.eq.return_value
    query.execute.return_value.data = [row("user-a", "user-a", "A")]
    assert repo.get_preferences("user-a").name == "A"
    table.select.return_value.eq.assert_called_once_with("user_id", "user-a")


def test_get_prefers_own_row_over_legacy_default(table):
    query = table.select.return_value.eq.return_value
    query.execute.return_value.data = [row("default", "user-a", "old"), row("user-a", "user-a", "new")]
    assert repo.get_preferences("user-a").name == "new"


def test_get_falls_back_to_legacy_default_row(table):
    # Settings saved before this fix live in the "default" row of whoever saved last: keep them for that user.
    query = table.select.return_value.eq.return_value
    query.execute.return_value.data = [row("default", "user-a", "legacy")]
    assert repo.get_preferences("user-a").name == "legacy"
