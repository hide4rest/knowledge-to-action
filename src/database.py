"""SQLiteデータ管理モジュール。"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Analysis, Entry

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/knowledge.db")


class Database:
    """SQLiteデータベース操作クラス。"""

    def __init__(self, db_path: Path = _DEFAULT_DB_PATH) -> None:
        """データベースを初期化する。

        Args:
            db_path: SQLiteファイルのパス。
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.debug("データベース接続: %s", self.db_path)

    def close(self) -> None:
        """データベース接続を閉じる。"""
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # エントリー操作
    # ------------------------------------------------------------------ #

    def add_entry(self, entry: Entry) -> Optional[int]:
        """エントリーを追加する。URLが重複している場合はスキップする。

        Args:
            entry: 追加するEntryオブジェクト。

        Returns:
            追加されたエントリーのID。重複時はNone。
        """
        if self.get_entry_by_url(entry.url) is not None:
            logger.info("重複URLをスキップ: %s", entry.url)
            return None

        cur = self._conn.execute(
            """
            INSERT INTO entries (url, title, description, body_text, og_image, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.url,
                entry.title,
                entry.description,
                entry.body_text,
                entry.og_image,
                entry.source,
                entry.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        entry_id = cur.lastrowid
        logger.info("エントリー追加: id=%d url=%s", entry_id, entry.url)
        return entry_id

    def get_entry_by_url(self, url: str) -> Optional[Entry]:
        """URLでエントリーを検索する。

        Args:
            url: 検索するURL。

        Returns:
            見つかった場合はEntryオブジェクト。存在しない場合はNone。
        """
        row = self._conn.execute(
            "SELECT * FROM entries WHERE url = ?", (url,)
        ).fetchone()
        return _row_to_entry(row) if row else None

    def get_entry(self, entry_id: int) -> Optional[Entry]:
        """IDでエントリーを取得する。

        Args:
            entry_id: エントリーID。

        Returns:
            見つかった場合はEntryオブジェクト。存在しない場合はNone。
        """
        row = self._conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()
        return _row_to_entry(row) if row else None

    def list_entries(
        self, category: Optional[str] = None, limit: int = 20
    ) -> list[Entry]:
        """エントリー一覧を取得する。

        Args:
            category: カテゴリでフィルタする場合に指定。
            limit: 取得件数の上限。

        Returns:
            Entryオブジェクトのリスト（新しい順）。
        """
        if category:
            rows = self._conn.execute(
                """
                SELECT e.* FROM entries e
                JOIN analyses a ON a.entry_id = e.id
                WHERE a.category = ?
                ORDER BY e.created_at DESC
                LIMIT ?
                """,
                (category, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM entries ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_entry(r) for r in rows]

    def count_entries(self) -> int:
        """エントリー総数を返す。

        Returns:
            エントリー総数。
        """
        return self._conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]

    # ------------------------------------------------------------------ #
    # 分析結果操作
    # ------------------------------------------------------------------ #

    def add_analysis(self, analysis: Analysis) -> int:
        """分析結果を保存する。既存の場合は更新する。

        Args:
            analysis: 保存するAnalysisオブジェクト。

        Returns:
            保存された分析結果のID。
        """
        existing = self._conn.execute(
            "SELECT id FROM analyses WHERE entry_id = ?", (analysis.entry_id,)
        ).fetchone()

        keywords_json = json.dumps(analysis.keywords, ensure_ascii=False)

        if existing:
            self._conn.execute(
                """
                UPDATE analyses
                SET summary=?, category=?, subcategory=?, keywords_json=?,
                    actionability=?, intent_guess=?
                WHERE entry_id=?
                """,
                (
                    analysis.summary,
                    analysis.category,
                    analysis.subcategory,
                    keywords_json,
                    analysis.actionability,
                    analysis.intent_guess,
                    analysis.entry_id,
                ),
            )
            self._conn.commit()
            logger.debug("分析結果を更新: entry_id=%d", analysis.entry_id)
            return existing["id"]

        cur = self._conn.execute(
            """
            INSERT INTO analyses (entry_id, summary, category, subcategory,
                                  keywords_json, actionability, intent_guess)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis.entry_id,
                analysis.summary,
                analysis.category,
                analysis.subcategory,
                keywords_json,
                analysis.actionability,
                analysis.intent_guess,
            ),
        )
        self._conn.commit()
        analysis_id = cur.lastrowid
        logger.debug("分析結果を保存: id=%d entry_id=%d", analysis_id, analysis.entry_id)
        return analysis_id

    def get_analysis(self, entry_id: int) -> Optional[Analysis]:
        """エントリーIDに対応する分析結果を取得する。

        Args:
            entry_id: エントリーID。

        Returns:
            見つかった場合はAnalysisオブジェクト。存在しない場合はNone。
        """
        row = self._conn.execute(
            "SELECT * FROM analyses WHERE entry_id = ?", (entry_id,)
        ).fetchone()
        return _row_to_analysis(row) if row else None

    def list_analyses(self) -> list[Analysis]:
        """全分析結果を取得する。

        Returns:
            Analysisオブジェクトのリスト。
        """
        rows = self._conn.execute("SELECT * FROM analyses").fetchall()
        return [_row_to_analysis(r) for r in rows]

    def get_entries_with_analyses(self) -> list[dict]:
        """エントリーと分析結果を結合して取得する。

        Returns:
            エントリーと分析結果を含むdictのリスト。
        """
        rows = self._conn.execute(
            """
            SELECT e.id, e.url, e.title, e.description, e.created_at,
                   a.summary, a.category, a.subcategory, a.keywords_json,
                   a.actionability, a.intent_guess
            FROM entries e
            JOIN analyses a ON a.entry_id = e.id
            ORDER BY e.created_at DESC
            """
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["keywords"] = json.loads(d.pop("keywords_json", "[]"))
            result.append(d)
        return result

    # ------------------------------------------------------------------ #
    # バッチレポート操作
    # ------------------------------------------------------------------ #

    def save_batch_report(self, report: dict) -> int:
        """バッチ分析レポートを保存する。

        Args:
            report: レポートデータのdict。

        Returns:
            保存されたレポートのID。
        """
        cur = self._conn.execute(
            "INSERT INTO batch_reports (report_json, created_at) VALUES (?, ?)",
            (json.dumps(report, ensure_ascii=False), datetime.now().isoformat()),
        )
        self._conn.commit()
        logger.info("バッチレポートを保存: id=%d", cur.lastrowid)
        return cur.lastrowid

    def get_latest_batch_report(self) -> Optional[dict]:
        """最新のバッチ分析レポートを取得する。

        Returns:
            レポートデータのdict。存在しない場合はNone。
        """
        row = self._conn.execute(
            "SELECT report_json, created_at FROM batch_reports ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        report = json.loads(row["report_json"])
        report["_created_at"] = row["created_at"]
        return report

    # ------------------------------------------------------------------ #
    # プライベートメソッド
    # ------------------------------------------------------------------ #

    def _create_tables(self) -> None:
        """テーブルを作成する（存在しない場合のみ）。"""
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT    NOT NULL UNIQUE,
                title       TEXT    NOT NULL DEFAULT '',
                description TEXT    NOT NULL DEFAULT '',
                body_text   TEXT    NOT NULL DEFAULT '',
                og_image    TEXT,
                source      TEXT    NOT NULL DEFAULT 'manual',
                created_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS analyses (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id      INTEGER NOT NULL UNIQUE REFERENCES entries(id),
                summary       TEXT    NOT NULL DEFAULT '',
                category      TEXT    NOT NULL DEFAULT '',
                subcategory   TEXT    NOT NULL DEFAULT '',
                keywords_json TEXT    NOT NULL DEFAULT '[]',
                actionability TEXT    NOT NULL DEFAULT 'medium',
                intent_guess  TEXT    NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS batch_reports (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                report_json TEXT    NOT NULL,
                created_at  TEXT    NOT NULL
            );
            """
        )
        self._conn.commit()


# ------------------------------------------------------------------ #
# ヘルパー関数
# ------------------------------------------------------------------ #


def _row_to_entry(row: sqlite3.Row) -> Entry:
    """DBのRowをEntryオブジェクトに変換する。

    Args:
        row: SQLiteのRowオブジェクト。

    Returns:
        Entryオブジェクト。
    """
    return Entry(
        id=row["id"],
        url=row["url"],
        title=row["title"],
        description=row["description"],
        body_text=row["body_text"],
        og_image=row["og_image"],
        source=row["source"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_analysis(row: sqlite3.Row) -> Analysis:
    """DBのRowをAnalysisオブジェクトに変換する。

    Args:
        row: SQLiteのRowオブジェクト。

    Returns:
        Analysisオブジェクト。
    """
    return Analysis(
        id=row["id"],
        entry_id=row["entry_id"],
        summary=row["summary"],
        category=row["category"],
        subcategory=row["subcategory"],
        keywords=json.loads(row["keywords_json"]),
        actionability=row["actionability"],
        intent_guess=row["intent_guess"],
    )
