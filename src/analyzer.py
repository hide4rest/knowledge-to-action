"""Claude APIによるAI分析モジュール。"""

import json
import logging
import os
from typing import Optional

import anthropic

from .database import Database
from .models import Analysis, Entry, ScrapedPage

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-20250514"
_CATEGORIES = ["健康", "テクノロジー", "ビジネス", "学習", "趣味", "ライフスタイル", "食事", "旅行", "金融", "その他"]


def _get_client() -> anthropic.Anthropic:
    """Anthropicクライアントを取得する。

    Returns:
        Anthropicクライアント。

    Raises:
        ValueError: ANTHROPIC_API_KEYが設定されていない場合。
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY が設定されていません。.env ファイルを確認してください。")
    return anthropic.Anthropic(api_key=api_key)


def analyze_entry(entry: Entry, db: Database) -> Optional[Analysis]:
    """単一エントリーを個別分析する。

    Args:
        entry: 分析するEntryオブジェクト。
        db: Databaseオブジェクト（分析結果の保存先）。

    Returns:
        分析結果のAnalysisオブジェクト。失敗時はNone。
    """
    if entry.id is None:
        logger.error("エントリーIDがありません: %s", entry.url)
        return None

    prompt = _build_individual_prompt(entry)

    try:
        client = _get_client()
        message = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        data = _parse_json_response(raw)
    except anthropic.APIError as e:
        logger.error("Claude API エラー: %s", e)
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error("レスポンスの解析失敗: %s", e)
        return None

    analysis = Analysis(
        entry_id=entry.id,
        summary=data.get("summary", ""),
        category=data.get("category", "その他"),
        subcategory=data.get("subcategory", ""),
        keywords=data.get("keywords", []),
        actionability=data.get("actionability", "medium"),
        intent_guess=data.get("intent_guess", ""),
    )
    db.add_analysis(analysis)
    logger.info("個別分析完了: entry_id=%d category=%s", entry.id, analysis.category)
    return analysis


def run_batch_analysis(db: Database) -> Optional[dict]:
    """全エントリーを横断分析し、バッチレポートを生成する。

    Args:
        db: Databaseオブジェクト。

    Returns:
        バッチ分析レポートのdict。失敗時はNone。
    """
    entries = db.get_entries_with_analyses()
    if not entries:
        logger.warning("分析済みエントリーがありません。先に個別分析を実行してください。")
        return None

    prompt = _build_batch_prompt(entries)

    try:
        client = _get_client()
        message = client.messages.create(
            model=_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        report = _parse_json_response(raw)
    except anthropic.APIError as e:
        logger.error("Claude API エラー (バッチ): %s", e)
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error("バッチレスポンスの解析失敗: %s", e)
        return None

    db.save_batch_report(report)
    logger.info(
        "バッチ分析完了: meta_categories=%d micro_actions=%d",
        len(report.get("meta_categories", [])),
        len(report.get("micro_actions", [])),
    )
    return report


# ------------------------------------------------------------------ #
# プロンプト構築
# ------------------------------------------------------------------ #


def _build_individual_prompt(entry: Entry) -> str:
    """個別分析用プロンプトを構築する。

    Args:
        entry: 分析するEntryオブジェクト。

    Returns:
        プロンプト文字列。
    """
    body_excerpt = entry.body_text[:2000] if entry.body_text else "（本文なし）"
    categories_str = ", ".join(_CATEGORIES)
    return f"""あなたは情報分析の専門家です。
以下のWebページの情報を分析し、JSON形式で結果を返してください。

入力情報:
- URL: {entry.url}
- タイトル: {entry.title}
- 説明: {entry.description}
- 本文（抜粋）: {body_excerpt}

以下のJSON形式で回答してください（他のテキストは不要）:
{{
  "summary": "100字以内の要約",
  "category": "メインカテゴリ（{categories_str}）",
  "subcategory": "サブカテゴリ（自由記述）",
  "keywords": ["キーワード1", "キーワード2", "キーワード3"],
  "actionability": "high/medium/low（実行可能なアクションにつながるか）",
  "intent_guess": "このページを保存した意図の推測"
}}"""


def _build_batch_prompt(entries: list[dict]) -> str:
    """バッチ分析用プロンプトを構築する。

    Args:
        entries: エントリーと分析結果を含むdictのリスト。

    Returns:
        プロンプト文字列。
    """
    # トークン節約のため各エントリーの主要フィールドのみ渡す
    slim = [
        {
            "id": e["id"],
            "title": e["title"],
            "url": e["url"],
            "summary": e.get("summary", ""),
            "category": e.get("category", ""),
            "subcategory": e.get("subcategory", ""),
            "keywords": e.get("keywords", []),
            "actionability": e.get("actionability", ""),
            "intent_guess": e.get("intent_guess", ""),
        }
        for e in entries
    ]
    entries_json = json.dumps(slim, ensure_ascii=False, indent=2)
    return f"""あなたはパーソナルナレッジコーチです。
以下はユーザーが過去に保存したWebページの分析結果一覧です。
これらを横断的に分析し、ユーザーの隠れた関心パターンと
具体的なアクションを提案してください。

保存情報一覧:
{entries_json}

以下のJSON形式で回答してください（他のテキストは不要）:
{{
  "meta_categories": [
    {{
      "name": "メタカテゴリ名（例：身体改善プロジェクト）",
      "description": "このカテゴリの説明",
      "intensity": "high/medium/low",
      "related_entries": [関連するエントリーのID配列],
      "insight": "このパターンから読み取れるインサイト"
    }}
  ],
  "micro_actions": [
    {{
      "action": "明日できる具体的なアクション",
      "rationale": "なぜこのアクションを提案するか（根拠となる保存情報を引用）",
      "difficulty": "easy/medium/hard",
      "time_estimate": "所要時間の目安"
    }}
  ],
  "business_seeds": [
    {{
      "idea": "保存情報から見えるビジネスの種",
      "rationale": "根拠",
      "next_step": "検証するための最小アクション"
    }}
  ]
}}"""


def _parse_json_response(text: str) -> dict:
    """APIレスポンスからJSONを抽出・パースする。

    コードブロック（```json ... ```）で囲まれている場合も対応する。

    Args:
        text: APIレスポンスのテキスト。

    Returns:
        パースされたdict。

    Raises:
        json.JSONDecodeError: JSONのパースに失敗した場合。
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # 最初と最後のコードフェンスを除去
        inner = lines[1:-1] if lines[-1].startswith("```") else lines[1:]
        text = "\n".join(inner).strip()
    return json.loads(text)
