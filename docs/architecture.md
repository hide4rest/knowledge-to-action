# アーキテクチャメモ

## Step 1: CLIプロトタイプ

### データフロー

```
[入力]
  ├── 単一URL（手動入力）
  └── Raindrop CSVエクスポート（一括インポート）
        ↓
[取得] scraper.py
  ├── HTTP GET → HTMLダウンロード
  ├── OGPメタタグ解析（og:title, og:description, og:image, og:type, og:site_name）
  ├── フォールバック（<title>, <meta description>）
  └── 本文テキスト抽出（<article>, <main>, <p>タグから推定）
        ↓
[保存] database.py
  └── SQLite: entries テーブル
        ↓
[個別分析] analyzer.py
  ├── Claude API (Sonnet) に送信
  ├── 要約・カテゴリ・キーワード・実行可能性・意図推測を取得
  └── SQLite: analyses テーブルに保存
        ↓
[バッチ分析] analyzer.py
  ├── 全エントリーの分析結果を集約
  ├── Claude API (Sonnet) でメタレベル分析
  ├── メタカテゴリ抽出
  ├── マイクロアクション提案
  └── ビジネスシード抽出
        ↓
[出力] reporter.py
  └── ターミナルにカラー表示
```

### テーブル設計

```sql
CREATE TABLE entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    description TEXT,
    body_text TEXT,
    og_image TEXT,
    og_type TEXT,
    site_name TEXT,
    source TEXT DEFAULT 'manual',  -- 'manual', 'raindrop', 'share_sheet'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL REFERENCES entries(id),
    summary TEXT,
    category TEXT,
    subcategory TEXT,
    keywords_json TEXT,  -- JSON array
    actionability TEXT,  -- 'high', 'medium', 'low'
    intent_guess TEXT,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE batch_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_json TEXT NOT NULL,  -- 全分析結果のJSON
    entry_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 将来の拡張ポイント（Step 2以降）

- FastAPI化してWebダッシュボード対応
- PWA + Web Share Target APIでShare Sheet受信
- Raindrop API直接連携（リアルタイム同期）
- ユーザー認証（個人→マルチユーザー）
- 定期バッチ分析（cron or Celery）
- タスク完了トラッキング
