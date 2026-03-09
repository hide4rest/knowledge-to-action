"""分析結果のレポート出力モジュール。"""

from __future__ import annotations

from typing import Optional

from .database import Database

# ANSI カラーコード
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_MAGENTA = "\033[35m"
_RED = "\033[31m"
_BLUE = "\033[34m"

_INTENSITY_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}
_TREND_ICON = {"increasing": "📈", "stable": "➡️", "decreasing": "📉"}
_URGENCY_LABEL = {"high": f"{_RED}高{_RESET}", "medium": f"{_YELLOW}中{_RESET}", "low": f"{_GREEN}低{_RESET}"}
_DIFFICULTY_COLOR = {"easy": _GREEN, "medium": _YELLOW, "hard": _RED}


def print_report(db: Database) -> None:
    """最新のバッチ分析レポートをターミナルに出力する。

    Args:
        db: Databaseオブジェクト。
    """
    report = db.get_latest_batch_report()
    if report is None:
        print("レポートがありません。先に `analyze` コマンドを実行してください。")
        return

    report_type = report.get("_report_type", "legacy")
    created_at = report.get("_created_at", "不明")

    _print_header(created_at)

    if report_type == "full":
        _print_full_report(report)
    elif report_type == "short_term":
        _print_short_term_section(report)
        _print_footer()
    elif report_type == "long_term":
        _print_long_term_section(report)
        _print_footer()
    else:
        _print_legacy_report(report)


def _print_header(created_at: str) -> None:
    print(f"\n{_BOLD}{_CYAN}{'━' * 56}{_RESET}")
    print(f"{_BOLD}{_CYAN}  📋 Knowledge-to-Action レポート{_RESET}")
    print(f"{_DIM}  生成日時: {created_at}{_RESET}")
    print(f"{_BOLD}{_CYAN}{'━' * 56}{_RESET}")


def _print_footer() -> None:
    print(f"\n{_BOLD}{_CYAN}{'━' * 56}{_RESET}\n")


def _print_full_report(report: dict) -> None:
    """2層レポート（short_term + long_term）を表示する。"""
    short = report.get("short_term", {})
    long = report.get("long_term", {})
    expanded = report.get("expanded_period", False)

    # ── 第1部: 短期 ──────────────────────────────────────
    period = short.get("period", "7日間")
    entry_count = short.get("entry_count", 0)
    print(f"\n{_BOLD}╔{'═' * 54}╗{_RESET}")
    print(f"{_BOLD}║  🔥 第1部：今週のフォーカス（直近{period}）{'':>16}║{_RESET}")
    print(f"{_BOLD}║  対象: {entry_count}件の保存情報{'':>36}║{_RESET}")
    print(f"{_BOLD}╚{'═' * 54}╝{_RESET}")
    if expanded:
        print(f"{_DIM}  ※ 直近7日間の保存が少ないため14日間に拡張しました{_RESET}")
    _print_short_term_section(short)

    # ── 第2部: 長期 ──────────────────────────────────────
    total = long.get("total_entries", 0)
    print(f"\n{_BOLD}╔{'═' * 54}╗{_RESET}")
    print(f"{_BOLD}║  🗺️  第2部：あなたの関心マップ（全期間）{'':>14}║{_RESET}")
    print(f"{_BOLD}║  対象: 全{total}件の保存情報{'':>35}║{_RESET}")
    print(f"{_BOLD}╚{'═' * 54}╝{_RESET}")
    _print_long_term_section(long)

    _print_footer()


def _print_short_term_section(report: dict) -> None:
    """短期レポートセクションを表示する。"""

    # 現在のフォーカステーマ
    focuses = report.get("current_focus", [])
    if focuses:
        print(f"\n{_BOLD}{_MAGENTA}■ 今のあなたの関心テーマ{_RESET}")
        for focus in focuses:
            urgency = focus.get("urgency", "medium")
            urgency_label = _URGENCY_LABEL.get(urgency, urgency)
            print(f"\n  🎯 {_BOLD}{focus.get('theme', '')}{_RESET}  ⚡緊急度: {urgency_label}")
            desc = focus.get("description", "")
            if desc:
                print(f"     → {desc}")
            related = focus.get("related_entries", [])
            if related:
                print(f"     {_DIM}関連エントリーID: {related}{_RESET}")

    # ベイビーステップアクション
    actions = report.get("baby_step_actions", [])
    if actions:
        print(f"\n{_BOLD}{_GREEN}■ 今すぐできるアクション（ベイビーステップ付き）{_RESET}")
        for i, action in enumerate(actions, 1):
            difficulty = action.get("difficulty", "medium")
            diff_color = _DIFFICULTY_COLOR.get(difficulty, _RESET)
            title = action.get("action_title", "")
            print(f"\n  [{i}/{len(actions)}] 🏃 {_BOLD}{title}{_RESET}")
            desc = action.get("description", "")
            if desc:
                print(f"        なぜ？: {desc}")
            rationale = action.get("rationale", "")
            if rationale:
                print(f"        {_DIM}根拠: 「{rationale}」より{_RESET}")
            print(f"        難易度: {diff_color}{difficulty}{_RESET}")

            steps = action.get("steps", [])
            for step in steps:
                num = step.get("step_number", "")
                step_desc = step.get("description", "")
                time_est = step.get("time_estimate", "")
                print(f"\n        📌 Step {num}（{time_est}）: {step_desc}")

            outcome = action.get("expected_outcome", "")
            if outcome:
                print(f"\n        ✅ 期待される成果: {_DIM}{outcome}{_RESET}")

    # クイックウィン
    quick_wins = report.get("quick_wins", [])
    if quick_wins:
        print(f"\n{_BOLD}{_YELLOW}■ 今日のクイックウィン 🎉{_RESET}")
        for win in quick_wins:
            print(f"  ・{win}")


def _print_long_term_section(report: dict) -> None:
    """長期レポートセクションを表示する。"""

    # メタカテゴリ
    meta_cats = report.get("meta_categories", [])
    if meta_cats:
        print(f"\n{_BOLD}{_MAGENTA}■ メタカテゴリ（あなたの隠れた関心パターン）{_RESET}")
        for i, cat in enumerate(meta_cats, 1):
            intensity = cat.get("intensity", "medium")
            trend = cat.get("trend", "stable")
            intensity_icon = _INTENSITY_ICON.get(intensity, "")
            trend_icon = _TREND_ICON.get(trend, "")
            entry_count = cat.get("entry_count", "?")
            print(
                f"\n  [{i}] 📂 {_BOLD}{cat.get('name', '')}{_RESET}"
                f"  強度:{intensity_icon}{intensity.upper()}"
                f"  傾向:{trend_icon}{trend}"
            )
            desc = cat.get("description", "")
            if desc:
                print(f"      → {desc}")
            insight = cat.get("insight", "")
            if insight:
                print(f"      {_DIM}💡 {insight}{_RESET}")
            print(f"      {_DIM}関連エントリー数: {entry_count}件{_RESET}")

    # 交差インサイト
    cross = report.get("cross_category_insights", [])
    if cross:
        print(f"\n{_BOLD}{_CYAN}■ カテゴリ交差インサイト 💡{_RESET}")
        for item in cross:
            cats = item.get("categories_involved", [])
            print(f"\n  ・「{'」×「'.join(cats)}」")
            insight = item.get("insight", "")
            if insight:
                print(f"    → {insight}")
            strength = item.get("unique_strength", "")
            if strength:
                print(f"    → あなたの強み: {_BOLD}{strength}{_RESET}")

    # 中長期アクション
    lt_actions = report.get("long_term_actions", [])
    if lt_actions:
        print(f"\n{_BOLD}{_GREEN}■ 中長期アクション（1〜3ヶ月）{_RESET}")
        for i, action in enumerate(lt_actions, 1):
            print(f"\n  [{i}] 🚀 {_BOLD}{action.get('action_title', '')}{_RESET}")
            desc = action.get("description", "")
            if desc:
                print(f"      {_DIM}{desc}{_RESET}")
            steps = action.get("steps", [])
            for step in steps:
                time_est = step.get("time_estimate", "")
                step_desc = step.get("description", "")
                print(f"      📌 {time_est}: {step_desc}")
            outcome = action.get("expected_outcome", "")
            if outcome:
                print(f"      ✅ {_DIM}{outcome}{_RESET}")

    # ビジネスシード
    biz_seeds = report.get("business_seeds", [])
    if biz_seeds:
        print(f"\n{_BOLD}{_YELLOW}■ ビジネスシード 💰{_RESET}")
        for i, seed in enumerate(biz_seeds, 1):
            print(f"\n  [{i}] 💡 {_BOLD}{seed.get('idea', '')}{_RESET}")
            uniqueness = seed.get("uniqueness", "")
            if uniqueness:
                print(f"       独自性: {uniqueness}")
            rationale = seed.get("rationale", "")
            if rationale:
                print(f"       {_DIM}根拠: {rationale}{_RESET}")
            validation = seed.get("validation_step", "")
            if validation:
                print(f"       検証の次の一手: {validation}")

    # ブラインドスポット
    blind_spots = report.get("blind_spots", [])
    if blind_spots:
        print(f"\n{_BOLD}■ 見落としているかもしれない視点 👀{_RESET}")
        for spot in blind_spots:
            print(f"  ・{spot}")


def _print_legacy_report(report: dict) -> None:
    """旧形式のレポートを表示する（後方互換）。"""
    meta_cats = report.get("meta_categories", [])
    if meta_cats:
        print(f"\n{_BOLD}{_MAGENTA}◆ 関心パターン（メタカテゴリ）{_RESET}")
        for cat in meta_cats:
            intensity = cat.get("intensity", "medium")
            color = "\033[31m" if intensity == "high" else "\033[33m" if intensity == "medium" else "\033[32m"
            print(f"\n  {_BOLD}{cat['name']}{_RESET}  [{color}{intensity.upper()}{_RESET}]")
            print(f"  {cat.get('description', '')}")
            insight = cat.get("insight", "")
            if insight:
                print(f"  {_DIM}💡 {insight}{_RESET}")
            related = cat.get("related_entries", [])
            if related:
                print(f"  {_DIM}関連エントリーID: {related}{_RESET}")

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
