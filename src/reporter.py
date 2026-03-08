"""分析結果のレポート出力モジュール。"""

from __future__ import annotations

from typing import Optional

from .database import Database

# ANSI カラーコード
_RESET = "\033[0m"
_BOLD = "\033[1m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_MAGENTA = "\033[35m"
_DIM = "\033[2m"

_INTENSITY_COLOR = {
    "high": "\033[31m",    # 赤
    "medium": "\033[33m",  # 黄
    "low": "\033[32m",     # 緑
}
_DIFFICULTY_COLOR = {
    "easy": "\033[32m",
    "medium": "\033[33m",
    "hard": "\033[31m",
}


def print_report(db: Database) -> None:
    """最新のバッチ分析レポートをターミナルに出力する。

    Args:
        db: Databaseオブジェクト。
    """
    report = db.get_latest_batch_report()
    if report is None:
        print("レポートがありません。先に `analyze` コマンドを実行してください。")
        return

    created_at = report.get("_created_at", "不明")
    print(f"\n{_BOLD}{_CYAN}{'=' * 60}{_RESET}")
    print(f"{_BOLD}{_CYAN}  Knowledge-to-Action レポート{_RESET}")
    print(f"{_DIM}  生成日時: {created_at}{_RESET}")
    print(f"{_BOLD}{_CYAN}{'=' * 60}{_RESET}\n")

    # メタカテゴリ
    meta_cats = report.get("meta_categories", [])
    if meta_cats:
        print(f"{_BOLD}{_MAGENTA}◆ 関心パターン（メタカテゴリ）{_RESET}")
        for cat in meta_cats:
            intensity = cat.get("intensity", "medium")
            color = _INTENSITY_COLOR.get(intensity, _RESET)
            print(f"\n  {_BOLD}{cat['name']}{_RESET}  [{color}{intensity.upper()}{_RESET}]")
            print(f"  {cat.get('description', '')}")
            insight = cat.get("insight", "")
            if insight:
                print(f"  {_DIM}💡 {insight}{_RESET}")
            related = cat.get("related_entries", [])
            if related:
                print(f"  {_DIM}関連エントリーID: {related}{_RESET}")

    # マイクロアクション
    micro_actions = report.get("micro_actions", [])
    if micro_actions:
        print(f"\n{_BOLD}{_GREEN}◆ 今すぐできるアクション{_RESET}")
        for i, action in enumerate(micro_actions, 1):
            difficulty = action.get("difficulty", "medium")
            diff_color = _DIFFICULTY_COLOR.get(difficulty, _RESET)
            print(f"\n  {_BOLD}[{i}] {action['action']}{_RESET}")
            print(f"  難易度: {diff_color}{difficulty}{_RESET}  所要時間: {action.get('time_estimate', '不明')}")
            rationale = action.get("rationale", "")
            if rationale:
                print(f"  {_DIM}根拠: {rationale}{_RESET}")

    # ビジネスシード
    biz_seeds = report.get("business_seeds", [])
    if biz_seeds:
        print(f"\n{_BOLD}{_YELLOW}◆ ビジネスの種{_RESET}")
        for seed in biz_seeds:
            print(f"\n  {_BOLD}{seed['idea']}{_RESET}")
            rationale = seed.get("rationale", "")
            if rationale:
                print(f"  {_DIM}根拠: {rationale}{_RESET}")
            next_step = seed.get("next_step", "")
            if next_step:
                print(f"  次のアクション: {next_step}")

    print(f"\n{_BOLD}{_CYAN}{'=' * 60}{_RESET}\n")


def print_entries(db: Database, category: Optional[str] = None, limit: int = 20) -> None:
    """エントリー一覧をターミナルに出力する。

    Args:
        db: Databaseオブジェクト。
        category: カテゴリでフィルタする場合に指定。
        limit: 表示件数の上限。
    """
    entries = db.list_entries(category=category, limit=limit)
    total = db.count_entries()

    cat_label = f"（カテゴリ: {category}）" if category else ""
    print(f"\n{_BOLD}保存済みエントリー一覧{cat_label}  {_DIM}全{total}件中{len(entries)}件表示{_RESET}")
    print(f"{_DIM}{'-' * 60}{_RESET}")

    if not entries:
        print("エントリーがありません。")
        return

    for entry in entries:
        analysis = db.get_analysis(entry.id) if entry.id else None
        cat_str = f"[{analysis.category}]" if analysis else "[未分析]"
        print(f"{_BOLD}{cat_str}{_RESET} {entry.title or entry.url}")
        print(f"  {_DIM}{entry.url}{_RESET}")
        if analysis and analysis.summary:
            print(f"  {analysis.summary}")
        print()
