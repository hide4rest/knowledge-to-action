"""database.py のユニットテスト。"""

from datetime import datetime
from pathlib import Path

import pytest

from src.database import Database
from src.models import Analysis, Entry


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """テスト用の一時データベース。"""
    return Database(db_path=tmp_path / "test.db")


def _make_entry(url: str = "https://example.com") -> Entry:
    return Entry(
        url=url,
        title="テストタイトル",
        description="テスト説明",
        body_text="テスト本文",
        og_image=None,
        source="manual",
        created_at=datetime.now(),
    )


def test_add_and_get_entry(db: Database) -> None:
    entry = _make_entry()
    entry_id = db.add_entry(entry)

    assert entry_id is not None
    fetched = db.get_entry(entry_id)
    assert fetched is not None
    assert fetched.url == entry.url
    assert fetched.title == entry.title


def test_duplicate_url_returns_none(db: Database) -> None:
    entry = _make_entry()
    first_id = db.add_entry(entry)
    second_id = db.add_entry(entry)

    assert first_id is not None
    assert second_id is None


def test_list_entries(db: Database) -> None:
    for i in range(3):
        db.add_entry(_make_entry(f"https://example.com/{i}"))

    entries = db.list_entries(limit=10)
    assert len(entries) == 3


def test_add_and_get_analysis(db: Database) -> None:
    entry = _make_entry()
    entry_id = db.add_entry(entry)
    assert entry_id is not None

    analysis = Analysis(
        entry_id=entry_id,
        summary="テスト要約",
        category="テクノロジー",
        subcategory="AI",
        keywords=["AI", "機械学習"],
        actionability="high",
        intent_guess="学習目的",
    )
    db.add_analysis(analysis)

    fetched = db.get_analysis(entry_id)
    assert fetched is not None
    assert fetched.summary == "テスト要約"
    assert fetched.keywords == ["AI", "機械学習"]


def test_batch_report_save_and_load(db: Database) -> None:
    report = {"meta_categories": [], "micro_actions": [{"action": "テスト"}]}
    db.save_batch_report(report)

    loaded = db.get_latest_batch_report()
    assert loaded is not None
    assert loaded["micro_actions"][0]["action"] == "テスト"


def test_count_entries(db: Database) -> None:
    assert db.count_entries() == 0
    db.add_entry(_make_entry("https://a.com"))
    db.add_entry(_make_entry("https://b.com"))
    assert db.count_entries() == 2
