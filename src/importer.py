"""Raindropエクスポートファイルのインポートモジュール。"""

import csv
import logging
import time
from datetime import datetime
from pathlib import Path

from .analyzer import analyze_entry
from .database import Database
from .models import Entry
from .scraper import scrape

logger = logging.getLogger(__name__)

_RATE_LIMIT_SEC = 1.0  # リクエスト間隔（秒）


def import_raindrop_csv(csv_path: Path, db: Database, analyze: bool = True) -> dict:
    """RaindropのCSVエクスポートをインポートする。

    Args:
        csv_path: CSVファイルのパス。
        db: Databaseオブジェクト。
        analyze: Trueの場合、各エントリーを個別分析する。

    Returns:
        インポート結果のサマリーdict（added, skipped, failed）。
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {csv_path}")

    urls = _read_csv(csv_path)
    logger.info("CSVから %d 件のURLを読み込みました", len(urls))

    added = skipped = failed = 0

    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url[:80]}", flush=True)

        # スクレイピング
        page = scrape(url)
        if not page.success:
            logger.warning("スクレイピング失敗: %s — %s", url, page.error)
            failed += 1
            time.sleep(_RATE_LIMIT_SEC)
            continue

        entry = Entry(
            url=page.url,
            title=page.title,
            description=page.description,
            body_text=page.body_text,
            og_image=page.og_image,
            source="raindrop",
            created_at=datetime.now(),
        )
        entry_id = db.add_entry(entry)
        if entry_id is None:
            skipped += 1
            continue

        entry.id = entry_id
        added += 1

        # 個別分析
        if analyze:
            analyze_entry(entry, db)

        time.sleep(_RATE_LIMIT_SEC)

    summary = {"added": added, "skipped": skipped, "failed": failed}
    logger.info("インポート完了: %s", summary)
    return summary


def _read_csv(csv_path: Path) -> list[str]:
    """CSVからURL一覧を読み込む。

    RaindropのCSVフォーマット（url列）に対応する。
    url列が見つからない場合は1列目を使用する。

    Args:
        csv_path: CSVファイルのパス。

    Returns:
        URLのリスト（空文字・重複を除去済み）。
    """
    urls: list[str] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        # url列を探す（大文字小文字を無視）
        url_col = next(
            (col for col in fieldnames if col.lower() in ("url", "link")), None
        )
        if url_col:
            for row in reader:
                u = row[url_col].strip()
                if u:
                    urls.append(u)
        else:
            # DictReaderを1列目として再オープン
            f.seek(0)
            plain_reader = csv.reader(f)
            next(plain_reader, None)  # ヘッダースキップ
            for row in plain_reader:
                if row and row[0].strip().startswith("http"):
                    urls.append(row[0].strip())

    # 重複除去（順序保持）
    seen: set[str] = set()
    unique: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique
