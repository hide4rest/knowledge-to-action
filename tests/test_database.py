"""database.py のユニットテスト。"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.database import Database
from src.models import Analysis, Entry


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """テスト用の一時データベース。"""
    return Database(db_path=tmp_path / "test.db")


def _make_entry(url: str = "https://example.com", days_ago: int = 0) -> Entry:
    created_at = datetime.now() - timedelta(days=days_ago)
    return Entry(
        url=url,
        title="テストタイトル",
        description="テスト説明",
        body_text="テスト本文",
        og_image=None,
        source="manual",
        created_at=created_at,
    )


def _add_entry_with_analysis(db: Database, url: str, days_ago: int = 0) -> int:
    """エントリーと分析結果をセットで追加するヘルパー。"""
    entry = _make_entry(url=url, days_ago=days_ago)
    entry_id = db.add_entry(entry)
    assert entry_id is not None
    analysis = Analysis(
        entry_id=entry_id,
        summary="要約",
        category="テクノロジー",
        subcategory="AI",
        keywords=["AI"],
        actionability="high",
        intent_guess="学習",
    )
    db.add_analysis(analysis)
    return entry_id


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


# ------------------------------------------------------------------ #
# 新規テスト: get_entries_by_period
# ------------------------------------------------------------------ #


def test_get_entries_by_period(db: Database) -> None:
    """日数指定でのフィルタリングが正しく動作すること。"""
    _add_entry_with_analysis(db, "https://new.com", days_ago=3)
    _add_entry_with_analysis(db, "https://old.com", days_ago=30)

    result = db.get_entries_by_period(days=7)
    urls = [e["url"] for e in result]
    assert "https://new.com" in urls
    assert "https://old.com" not in urls


def test_get_entries_by_period_zero(db: Database) -> None:
    """days=0で全件取得されること。"""
    _add_entry_with_analysis(db, "https://new.com", days_ago=3)
    _add_entry_with_analysis(db, "https://old.com", days_ago=30)

    result = db.get_entries_by_period(days=0)
    urls = [e["url"] for e in result]
    assert "https://new.com" in urls
    assert "https://old.com" in urls
    assert len(result) == 2


def test_get_recent_entries(db: Database) -> None:
    """直近N件の取得が正しく動作すること。"""
    for i in range(5):
        _add_entry_with_analysis(db, f"https://example.com/{i}", days_ago=i)

    result = db.get_recent_entries(limit=3)
    assert len(result) == 3
    # created_at降順なので最新3件が返る
    urls = [e["url"] for e in result]
    assert "https://example.com/0" in urls
    assert "https://example.com/1" in urls
    assert "https://example.com/2" in urls
    assert "https://example.com/4" not in urls


def test_get_entry_count_by_period(db: Database) -> None:
    """指定期間内のエントリー数が正しく返ること。"""
    _add_entry_with_analysis(db, "https://new.com", days_ago=2)
    _add_entry_with_analysis(db, "https://old.com", days_ago=20)

    assert db.get_entry_count_by_period(days=7) == 1
    assert db.get_entry_count_by_period(days=0) == 2
