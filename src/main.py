"""CLIエントリーポイント。

使用例:
    python -m src.main add "https://example.com/article"
    python -m src.main import raindrop export.csv
    python -m src.main list [--category カテゴリ名] [--limit 20]
    python -m src.main analyze
    python -m src.main report
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from .analyzer import analyze_entry, run_batch_analysis
from .database import Database
from .importer import import_raindrop_csv
from .models import Entry
from .reporter import print_entries, print_report
from .scraper import scrape

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_DB_PATH = Path("data/knowledge.db")


def cmd_add(args: argparse.Namespace, db: Database) -> int:
    """単一URLを追加・分析するコマンド。

    Args:
        args: CLIパース済み引数。
        db: Databaseオブジェクト。

    Returns:
        終了コード（0: 成功、1: 失敗）。
    """
    url: str = args.url
    print(f"URLを取得中: {url}")

    page = scrape(url)
    if not page.success:
        print(f"エラー: ページの取得に失敗しました — {page.error}", file=sys.stderr)
        return 1

    entry = Entry(
        url=page.url,
        title=page.title,
        description=page.description,
        body_text=page.body_text,
        og_image=page.og_image,
        source="manual",
        created_at=datetime.now(),
    )

    entry_id = db.add_entry(entry)
    if entry_id is None:
        print("このURLは既に登録済みです。")
        return 0

    entry.id = entry_id
    print(f"登録完了: [{entry_id}] {page.title or url}")

    print("AI分析中...")
    analysis = analyze_entry(entry, db)
    if analysis is None:
        print("警告: AI分析に失敗しました（エントリーは保存済みです）。", file=sys.stderr)
        return 0

    print(f"カテゴリ: {analysis.category} / {analysis.subcategory}")
    print(f"要約: {analysis.summary}")
    print(f"キーワード: {', '.join(analysis.keywords)}")
    print(f"アクション可能性: {analysis.actionability}")
    return 0


def cmd_import(args: argparse.Namespace, db: Database) -> int:
    """CSVインポートコマンド。

    Args:
        args: CLIパース済み引数。
        db: Databaseオブジェクト。

    Returns:
        終了コード（0: 成功、1: 失敗）。
    """
    csv_path = Path(args.file)
    try:
        result = import_raindrop_csv(csv_path, db, analyze=True)
    except FileNotFoundError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

    print(
        f"\nインポート完了 — 追加: {result['added']}件  スキップ: {result['skipped']}件  失敗: {result['failed']}件"
    )
    return 0


def cmd_list(args: argparse.Namespace, db: Database) -> int:
    """エントリー一覧表示コマンド。

    Args:
        args: CLIパース済み引数。
        db: Databaseオブジェクト。

    Returns:
        終了コード（常に0）。
    """
    print_entries(db, category=args.category, limit=args.limit)
    return 0


def cmd_analyze(_args: argparse.Namespace, db: Database) -> int:
    """バッチ分析コマンド。

    Args:
        _args: CLIパース済み引数（未使用）。
        db: Databaseオブジェクト。

    Returns:
        終了コード（0: 成功、1: 失敗）。
    """
    total = db.count_entries()
    if total == 0:
        print("エントリーがありません。先に `add` または `import` コマンドを実行してください。")
        return 1

    print(f"{total}件のエントリーをバッチ分析中...")
    report = run_batch_analysis(db)
    if report is None:
        print("エラー: バッチ分析に失敗しました。", file=sys.stderr)
        return 1

    n_cats = len(report.get("meta_categories", []))
    n_actions = len(report.get("micro_actions", []))
    print(f"分析完了: メタカテゴリ {n_cats}件、アクション提案 {n_actions}件")
    print("`report` コマンドで結果を確認できます。")
    return 0


def cmd_report(_args: argparse.Namespace, db: Database) -> int:
    """レポート表示コマンド。

    Args:
        _args: CLIパース済み引数（未使用）。
        db: Databaseオブジェクト。

    Returns:
        終了コード（常に0）。
    """
    print_report(db)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """CLIパーサーを構築する。

    Returns:
        ArgumentParserオブジェクト。
    """
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Knowledge-to-Action: 保存情報をアクションに変換するCLIツール",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="単一URLを追加・分析する")
    p_add.add_argument("url", help="追加するURL")

    # import
    p_import = sub.add_parser("import", help="CSVファイルをインポートする")
    p_import.add_argument("source", choices=["raindrop"], help="インポートソース")
    p_import.add_argument("file", help="CSVファイルパス")

    # list
    p_list = sub.add_parser("list", help="保存済みエントリー一覧を表示する")
    p_list.add_argument("--category", "-c", default=None, help="カテゴリでフィルタ")
    p_list.add_argument("--limit", "-n", type=int, default=20, help="表示件数（デフォルト: 20）")

    # analyze
    sub.add_parser("analyze", help="全エントリーをバッチ分析してアクション提案を生成する")

    # report
    sub.add_parser("report", help="最新のバッチ分析レポートを表示する")

    return parser


def main() -> None:
    """CLIエントリーポイント。"""
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "add": cmd_add,
        "import": cmd_import,
        "list": cmd_list,
        "analyze": cmd_analyze,
        "report": cmd_report,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    with Database(db_path=_DB_PATH) as db:
        exit_code = handler(args, db)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
