"""analyzer.py のユニットテスト。"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.analyzer import (
    _build_long_term_prompt,
    _build_short_term_prompt,
    _parse_json_response,
    analyze_entry,
    run_batch_long_term,
    run_batch_short_term,
    run_full_analysis,
)
from src.database import Database
from src.models import Analysis, Entry


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(db_path=tmp_path / "test.db")


def _make_entry(db: Database) -> Entry:
    entry = Entry(
        url="https://example.com",
        title="テストタイトル",
        description="テスト説明",
        body_text="テスト本文",
        og_image=None,
        source="manual",
        created_at=datetime.now(),
    )
    entry_id = db.add_entry(entry)
    assert entry_id is not None
    entry.id = entry_id
    return entry


def _mock_api_response(data: dict) -> MagicMock:
    content = MagicMock()
    content.text = json.dumps(data, ensure_ascii=False)
    message = MagicMock()
    message.content = [content]
    return message


def _make_sample_entries(n: int = 3) -> list[dict]:
    return [
        {
            "id": i,
            "url": f"https://example.com/{i}",
            "title": f"記事{i}",
            "summary": f"要約{i}",
            "category": "テクノロジー",
            "subcategory": "AI",
            "keywords": ["AI"],
            "actionability": "high",
            "intent_guess": "学習",
        }
        for i in range(1, n + 1)
    ]


def test_parse_json_response_plain() -> None:
    data = {"summary": "テスト", "category": "テクノロジー"}
    result = _parse_json_response(json.dumps(data))
    assert result["summary"] == "テスト"


def test_parse_json_response_with_code_fence() -> None:
    data = {"summary": "テスト"}
    text = f"```json\n{json.dumps(data)}\n```"
    result = _parse_json_response(text)
    assert result["summary"] == "テスト"


@patch("src.analyzer._get_client")
def test_analyze_entry_success(mock_get_client: MagicMock, db: Database) -> None:
    entry = _make_entry(db)
    response_data = {
        "summary": "テスト要約",
        "category": "テクノロジー",
        "subcategory": "AI",
        "keywords": ["AI", "機械学習", "Python"],
        "actionability": "high",
        "intent_guess": "学習目的",
    }
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_api_response(response_data)
    mock_get_client.return_value = mock_client

    analysis = analyze_entry(entry, db)

    assert analysis is not None
    assert analysis.summary == "テスト要約"
    assert analysis.category == "テクノロジー"
    assert analysis.keywords == ["AI", "機械学習", "Python"]

    # DBに保存されているか確認
    saved = db.get_analysis(entry.id)
    assert saved is not None
    assert saved.summary == "テスト要約"


@patch("src.analyzer._get_client")
def test_analyze_entry_api_error(mock_get_client: MagicMock, db: Database) -> None:
    import anthropic
    entry = _make_entry(db)
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = anthropic.APIConnectionError(request=MagicMock())
    mock_get_client.return_value = mock_client

    analysis = analyze_entry(entry, db)
    assert analysis is None


# ------------------------------------------------------------------ #
# 新規テスト: プロンプトフォーマット
# ------------------------------------------------------------------ #


def test_short_term_prompt_format() -> None:
    """短期プロンプトが正しくフォーマットされること。"""
    entries = _make_sample_entries(3)
    prompt = _build_short_term_prompt(entries, days=7)

    assert "直近7日間" in prompt
    assert "3" in prompt  # entry count
    assert "baby_step_actions" in prompt
    assert "Step 1" in prompt
    assert "Step 2" in prompt
    assert "Step 3" in prompt
    assert "quick_wins" in prompt
    # entries_json が含まれていること
    assert "記事1" in prompt


def test_long_term_prompt_format() -> None:
    """長期プロンプトが正しくフォーマットされること。"""
    entries = _make_sample_entries(5)
    prompt = _build_long_term_prompt(entries)

    assert "全期間" in prompt
    assert "5" in prompt  # entry count
    assert "meta_categories" in prompt
    assert "cross_category_insights" in prompt
    assert "long_term_actions" in prompt
    assert "business_seeds" in prompt
    assert "blind_spots" in prompt
    assert "記事1" in prompt


# ------------------------------------------------------------------ #
# 新規テスト: 2層分析の統合
# ------------------------------------------------------------------ #


@patch("src.analyzer._get_client")
def test_analyze_full_integration(mock_get_client: MagicMock, db: Database) -> None:
    """run_full_analysis が正しいdict構造を返すこと。"""
    from datetime import timedelta
    from src.models import Analysis

    # テスト用エントリーを8件追加（7日以内）
    for i in range(8):
        entry = Entry(
            url=f"https://example.com/{i}",
            title=f"記事{i}",
            description="説明",
            body_text="本文",
            og_image=None,
            source="manual",
            created_at=datetime.now() - timedelta(days=i % 5),
        )
        entry_id = db.add_entry(entry)
        assert entry_id is not None
        db.add_analysis(Analysis(
            entry_id=entry_id,
            summary=f"要約{i}",
            category="テクノロジー",
            subcategory="AI",
            keywords=["AI"],
            actionability="high",
            intent_guess="学習",
        ))

    short_response = {
        "period": "7日間",
        "entry_count": 8,
        "current_focus": [],
        "baby_step_actions": [{"action_title": "テスト", "steps": [], "difficulty": "easy"}],
        "quick_wins": ["今日できること"],
    }
    long_response = {
        "total_entries": 8,
        "meta_categories": [{"name": "AI活用", "intensity": "high"}],
        "cross_category_insights": [],
        "long_term_actions": [],
        "business_seeds": [],
        "blind_spots": [],
    }

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _mock_api_response(short_response),
        _mock_api_response(long_response),
    ]
    mock_get_client.return_value = mock_client

    result = run_full_analysis(db)

    assert result is not None
    assert "short_term" in result
    assert "long_term" in result
    assert "generated_at" in result
    assert result["short_term"]["period"] == "7日間"
    assert result["long_term"]["meta_categories"][0]["name"] == "AI活用"

    # DBに保存されているか確認
    saved = db.get_latest_batch_report()
    assert saved is not None
    assert saved["_report_type"] == "full"
