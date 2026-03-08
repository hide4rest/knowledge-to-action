"""analyzer.py のユニットテスト。"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.analyzer import _parse_json_response, analyze_entry
from src.database import Database
from src.models import Entry


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
