"""Claude APIによるAI分析モジュール。"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

import anthropic

from .database import Database
from .models import Analysis, Entry

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-20250514"
_CATEGORIES = ["健康", "テクノロジー", "ビジネス", "学習", "趣味", "ライフスタイル", "食事", "旅行", "金融", "その他"]
_MAX_ENTRIES_SHORT = 50   # 短期分析でプロンプトに渡す上限
_MAX_ENTRIES_LONG = 80    # 長期分析でプロンプトに渡す上限


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


def run_batch_short_term(entries: list[dict], days: int) -> Optional[dict]:
    """短期バッチ分析を実行する（APIコールのみ、DB保存なし）。

    Args:
        entries: エントリーと分析結果を含むdictのリスト。
        days: 分析対象の日数。

    Returns:
        短期分析レポートのdict。失敗時はNone。
    """
    if not entries:
        logger.warning("分析対象のエントリーがありません。")
        return None

    # プロンプトサイズ制限
    if len(entries) > _MAX_ENTRIES_SHORT:
        logger.info("短期分析: %d件 → 上位%d件に絞って分析します", len(entries), _MAX_ENTRIES_SHORT)
        entries = entries[:_MAX_ENTRIES_SHORT]

    prompt = _build_short_term_prompt(entries, days)

    try:
        client = _get_client()
        message = client.messages.create(
            model=_MODEL,
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        report = _parse_json_response(raw)
    except anthropic.APIError as e:
        logger.error("Claude API エラー (短期バッチ): %s", e)
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error("短期バッチレスポンスの解析失敗: %s", e)
        return None

    logger.info(
        "短期バッチ分析完了: days=%d entries=%d actions=%d",
        days,
        len(entries),
        len(report.get("baby_step_actions", [])),
    )
    return report


def run_batch_long_term(entries: list[dict]) -> Optional[dict]:
    """長期バッチ分析を実行する（APIコールのみ、DB保存なし）。

    Args:
        entries: エントリーと分析結果を含むdictのリスト。

    Returns:
        長期分析レポートのdict。失敗時はNone。
    """
    if not entries:
        logger.warning("分析対象のエントリーがありません。")
        return None

    # プロンプトサイズ制限
    if len(entries) > _MAX_ENTRIES_LONG:
        logger.info("長期分析: %d件 → 上位%d件に絞って分析します", len(entries), _MAX_ENTRIES_LONG)
        entries = entries[:_MAX_ENTRIES_LONG]

    prompt = _build_long_term_prompt(entries)

    try:
        client = _get_client()
        message = client.messages.create(
            model=_MODEL,
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        report = _parse_json_response(raw)
    except anthropic.APIError as e:
        logger.error("Claude API エラー (長期バッチ): %s", e)
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error("長期バッチレスポンスの解析失敗: %s", e)
        return None

    logger.info(
        "長期バッチ分析完了: entries=%d meta_categories=%d",
        len(entries),
        len(report.get("meta_categories", [])),
    )
    return report


def run_full_analysis(db: Database) -> Optional[dict]:
    """2層レポート（短期+長期）を生成してDBに保存する。

    Args:
        db: Databaseオブジェクト。

    Returns:
        統合レポートのdict。失敗時はNone。
    """
    # 短期分析（直近7日、3件未満なら14日に拡張）
    short_entries = db.get_entries_by_period(days=7)
    expanded = False
    if len(short_entries) < 3:
        short_entries = db.get_entries_by_period(days=14)
        expanded = True
    short_days = 14 if expanded else 7

    # 長期分析（全期間）
    all_entries = db.get_entries_by_period(days=0)
    if not all_entries:
        logger.warning("分析済みエントリーがありません。")
        return None

    logger.info("短期分析開始: %d件 (%d日間)", len(short_entries), short_days)
    short_result = run_batch_short_term(short_entries, short_days)
    if short_result is None:
        return None

    logger.info("長期分析開始: %d件 (全期間)", len(all_entries))
    long_result = run_batch_long_term(all_entries)
    if long_result is None:
        return None

    report = {
        "short_term": short_result,
        "long_term": long_result,
        "generated_at": datetime.now().isoformat(),
        "expanded_period": expanded,
    }

    db.save_batch_report(
        report,
        report_type="full",
        period_days=short_days,
        entry_count=len(all_entries),
    )
    logger.info("2層分析完了: short=%d日 long=%d件", short_days, len(all_entries))
    return report


def run_batch_analysis(db: Database) -> Optional[dict]:
    """全エントリーを横断分析し、バッチレポートを生成する（後方互換）。

    Args:
        db: Databaseオブジェクト。

    Returns:
        バッチ分析レポートのdict。失敗時はNone。
    """
    entries = db.get_entries_with_analyses()
    if not entries:
        logger.warning("分析済みエントリーがありません。先に個別分析を実行してください。")
        return None

    report = run_batch_long_term(entries)
    if report is None:
        return None

    db.save_batch_report(
        report,
        report_type="long_term",
        period_days=0,
        entry_count=len(entries),
    )
    return report


# ------------------------------------------------------------------ #
# プロンプト構築
# ------------------------------------------------------------------ #


def _slim_entries(entries: list[dict]) -> list[dict]:
    """エントリーリストをトークン節約のため必要フィールドのみに絞る。

    Args:
        entries: エントリーと分析結果を含むdictのリスト。

    Returns:
        必要フィールドのみのdictのリスト。
    """
    return [
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


def _build_short_term_prompt(entries: list[dict], days: int) -> str:
    """短期バッチ分析用プロンプトを構築する。

    Args:
        entries: エントリーと分析結果を含むdictのリスト。
        days: 分析対象の日数。

    Returns:
        プロンプト文字列。
    """
    count = len(entries)
    entries_json = json.dumps(_slim_entries(entries), ensure_ascii=False, indent=2)
    return f"""あなたはパーソナルナレッジコーチです。
以下はユーザーが「直近{days}日間」に保存したWebページの分析結果一覧です。

この期間の保存行動から、ユーザーが「今」何に関心を持ち、
何を解決しようとしているかを読み取り、
すぐに実行できる具体的なアクションを提案してください。

■ 重要なルール:
- アクション提案は5〜7個出すこと
- 各アクションは必ず「3段階のベイビーステップ」に分解すること
  - Step 1: 5分以内にできる最小アクション
  - Step 2: 30分〜1時間でできる次のアクション
  - Step 3: 1日〜1週間で達成できる成果目標
- 各アクションの根拠（どの保存情報から導いたか）を明示すること
- ユーザーの「保存した意図」を推測し、それに寄り添った提案をすること

保存情報一覧（直近{days}日間、{count}件）:
{entries_json}

以下のJSON形式で回答してください（他のテキストは不要）:
{{
  "period": "{days}日間",
  "entry_count": {count},
  "current_focus": [
    {{
      "theme": "今この期間でユーザーが注力しているテーマ",
      "description": "テーマの説明（なぜそう判断したか）",
      "related_entries": [1, 2, 3],
      "urgency": "high/medium/low（今すぐ取り組むべきか）"
    }}
  ],
  "baby_step_actions": [
    {{
      "action_title": "アクションのタイトル（20字以内）",
      "description": "このアクションを提案する理由",
      "rationale": "根拠となる保存情報のタイトルとURL",
      "steps": [
        {{
          "step_number": 1,
          "description": "5分以内にできること",
          "time_estimate": "5分"
        }},
        {{
          "step_number": 2,
          "description": "30分〜1時間でできること",
          "time_estimate": "30分"
        }},
        {{
          "step_number": 3,
          "description": "1日〜1週間で達成できること",
          "time_estimate": "3日"
        }}
      ],
      "expected_outcome": "このアクションを完了すると得られる成果",
      "difficulty": "easy/medium/hard"
    }}
  ],
  "quick_wins": [
    "今日中にできる小さな成果（1行で記述）"
  ]
}}"""


def _build_long_term_prompt(entries: list[dict]) -> str:
    """長期バッチ分析用プロンプトを構築する。

    Args:
        entries: エントリーと分析結果を含むdictのリスト。

    Returns:
        プロンプト文字列。
    """
    count = len(entries)
    entries_json = json.dumps(_slim_entries(entries), ensure_ascii=False, indent=2)
    return f"""あなたはパーソナルナレッジコーチです。
以下はユーザーが「全期間」にわたって保存したWebページの分析結果一覧です。

長期的な視点で、ユーザー自身も気づいていない関心パターンや、
複数の関心領域が交差するポイントを発見してください。

■ 重要なルール:
- メタカテゴリ（表面的なカテゴリではなく、複数の保存が束になった上位テーマ）を3〜5個抽出すること
- 各メタカテゴリについて「関心の強度」と「時間的な変化」（increasing/stable/decreasing）を分析すること
- 複数のメタカテゴリが交差する「ユニークな強みポイント」を見つけること
- ビジネスシード（事業アイデアの種）は、ユーザーの知識の組み合わせから生まれるユニークなものを提案すること
- 中長期アクション（1ヶ月〜3ヶ月スパン）を3段階のステップで提案すること

保存情報一覧（全{count}件）:
{entries_json}

以下のJSON形式で回答してください（他のテキストは不要）:
{{
  "total_entries": {count},
  "meta_categories": [
    {{
      "name": "メタカテゴリ名（例：テクノロジー×地域課題の融合）",
      "description": "このカテゴリの説明",
      "intensity": "high/medium/low",
      "trend": "increasing/stable/decreasing",
      "related_entries": [1, 2, 3],
      "insight": "このパターンから読み取れる深いインサイト",
      "entry_count": 10
    }}
  ],
  "cross_category_insights": [
    {{
      "categories_involved": ["カテゴリA", "カテゴリB"],
      "insight": "これらのカテゴリが交差することで見える独自の視点",
      "unique_strength": "ユーザーならではの強み"
    }}
  ],
  "long_term_actions": [
    {{
      "action_title": "中長期アクションのタイトル",
      "description": "提案理由",
      "rationale": "根拠となる保存情報",
      "steps": [
        {{
          "step_number": 1,
          "description": "今週やること",
          "time_estimate": "1週間"
        }},
        {{
          "step_number": 2,
          "description": "今月やること",
          "time_estimate": "1ヶ月"
        }},
        {{
          "step_number": 3,
          "description": "3ヶ月後に達成する成果目標",
          "time_estimate": "3ヶ月"
        }}
      ],
      "expected_outcome": "達成時に得られる成果"
    }}
  ],
  "business_seeds": [
    {{
      "idea": "保存情報の組み合わせから生まれるビジネスの種",
      "uniqueness": "なぜこのユーザーだからこそ実現できるか",
      "rationale": "根拠となる保存情報の組み合わせ",
      "validation_step": "最小コストで検証するための次の一手"
    }}
  ],
  "blind_spots": [
    "ユーザーが見落としている可能性がある領域や視点"
  ]
}}"""


def _parse_json_response(text: str) -> dict:
    """APIレスポンスからJSONを抽出・パースする。

    コードブロック（```json ... ```）で囲まれている場合も対応する。
    それでも失敗した場合は最初の { から最後の } を切り出して再試行する。

    Args:
        text: APIレスポンスのテキスト。

    Returns:
        パースされたdict。

    Raises:
        json.JSONDecodeError: JSONのパースに失敗した場合。
    """
    text = text.strip()

    # コードフェンスを除去
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines[-1].startswith("```") else lines[1:]
        text = "\n".join(inner).strip()

    # まず直接パースを試みる
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # { ... } の範囲を切り出して再試行
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 失敗時はデバッグ用にログ出力
    logger.error("JSONパース失敗。生レスポンス末尾200字: ...%s", text[-200:])
    raise json.JSONDecodeError("JSON抽出失敗", text, 0)
