# Knowledge-to-Action MVP（Step 1）

## プロジェクト概要

SNS・Webで保存した情報（ブックマーク、スキ、保存）を自動収集・分析し、
ユーザーの生活改善タスクや事業アイデアに変換するサービスのプロトタイプ。

**Step 1のゴール：**
CLIツールとして「URLを入力 → 情報取得 → AI分析 → 構造化された結果出力」を実現する。
まず開発者本人（1人）が日常的に使えるレベルを目指す。

## 技術スタック

- **言語**: Python 3.11+
- **パッケージ管理**: pip（requirements.txt）
- **DB**: SQLite（sqlite3標準ライブラリ）
- **AI**: Anthropic Claude API（claude-sonnet-4-20250514）
- **OGP取得**: requests + BeautifulSoup4
- **CLI**: 標準のargparse（シンプルに保つ）

## ディレクトリ構成

```
knowledge-to-action/
├── CLAUDE.md              # このファイル
├── README.md              # セットアップ手順
├── requirements.txt       # 依存パッケージ
├── .env.example           # 環境変数テンプレート
├── src/
│   ├── __init__.py
│   ├── main.py            # CLIエントリーポイント
│   ├── scraper.py         # OGPメタデータ・本文取得
│   ├── analyzer.py        # Claude APIによるAI分析
│   ├── database.py        # SQLiteデータ管理
│   ├── models.py          # データモデル定義
│   ├── importer.py        # Raindropエクスポート(CSV/JSON)インポート
│   └── reporter.py        # 分析結果のレポート出力
├── tests/
│   ├── test_scraper.py
│   ├── test_analyzer.py
│   └── test_database.py
└── docs/
    └── architecture.md    # アーキテクチャメモ
```

## 機能要件（Step 1）

### 1. URL入力と情報取得（scraper.py）
- 単一URLを受け取り、OGPメタデータ（title, description, image, type, site_name）を取得
- OGPがない場合は `<title>`, `<meta name="description">` にフォールバック
- ページ本文のテキスト抽出（HTMLタグ除去、主要コンテンツ部分を推定）
- 取得できた情報をdictで返す
- User-Agentヘッダーを適切に設定（ブロック回避）
- タイムアウト10秒、リトライ1回

### 2. Raindropエクスポートインポート（importer.py）
- RaindropのCSVエクスポートファイルを読み込み
- 各行のURLに対してscraper.pyで情報取得
- レート制限（1リクエスト/秒）を守る
- 進捗表示（tqdmまたはprint）

### 3. AI分析（analyzer.py）
- Claude APIを使用（model: claude-sonnet-4-20250514）
- 分析は2段階：
  - **個別分析**: 各URLの内容を要約・カテゴリ分類・キーワード抽出
  - **バッチ分析**: 蓄積された全データを横断分析し、以下を生成
    - メタカテゴリ（ユーザーの関心領域の抽出）
    - 関心の強度スコア（保存頻度・時系列から推定）
    - 具体的なアクション提案（マイクロアクション3つ）
    - 根拠の提示（どの保存情報からその提案に至ったか）
- APIレスポンスはJSON形式で構造化

#### 個別分析のプロンプト設計
```
あなたは情報分析の専門家です。
以下のWebページの情報を分析し、JSON形式で結果を返してください。

入力情報:
- URL: {url}
- タイトル: {title}
- 説明: {description}
- 本文（抜粋）: {body_text[:2000]}

以下のJSON形式で回答してください（他のテキストは不要）:
{
  "summary": "100字以内の要約",
  "category": "メインカテゴリ（健康, テクノロジー, ビジネス, 学習, 趣味, ライフスタイル, 食事, 旅行, 金融, その他）",
  "subcategory": "サブカテゴリ（自由記述）",
  "keywords": ["キーワード1", "キーワード2", "キーワード3"],
  "actionability": "high/medium/low（実行可能なアクションにつながるか）",
  "intent_guess": "このページを保存した意図の推測"
}
```

#### バッチ分析のプロンプト設計
```
あなたはパーソナルナレッジコーチです。
以下はユーザーが過去に保存したWebページの分析結果一覧です。
これらを横断的に分析し、ユーザーの隠れた関心パターンと
具体的なアクションを提案してください。

保存情報一覧:
{entries_json}

以下のJSON形式で回答してください（他のテキストは不要）:
{
  "meta_categories": [
    {
      "name": "メタカテゴリ名（例：身体改善プロジェクト）",
      "description": "このカテゴリの説明",
      "intensity": "high/medium/low",
      "related_entries": [関連するエントリーのID配列],
      "insight": "このパターンから読み取れるインサイト"
    }
  ],
  "micro_actions": [
    {
      "action": "明日できる具体的なアクション",
      "rationale": "なぜこのアクションを提案するか（根拠となる保存情報を引用）",
      "difficulty": "easy/medium/hard",
      "time_estimate": "所要時間の目安"
    }
  ],
  "business_seeds": [
    {
      "idea": "保存情報から見えるビジネスの種",
      "rationale": "根拠",
      "next_step": "検証するための最小アクション"
    }
  ]
}
```

### 4. データベース（database.py）
- SQLiteで以下のテーブルを管理:
  - `entries`: 保存情報（url, title, description, body_text, og_image, source, created_at）
  - `analyses`: 個別分析結果（entry_id, summary, category, subcategory, keywords_json, actionability, intent_guess）
  - `batch_reports`: バッチ分析結果（report_json, created_at）
- CRUD操作を提供
- 重複URLの検出と無視

### 5. CLIインターフェース（main.py）
以下のコマンドを実装:

```bash
# 単一URL追加＆分析
python -m src.main add "https://example.com/article"

# RaindropのCSVインポート
python -m src.main import raindrop export.csv

# 保存済みエントリー一覧
python -m src.main list [--category カテゴリ名] [--limit 20]

# バッチ分析（全エントリーを横断分析してアクション提案）
python -m src.main analyze

# レポート表示（最新のバッチ分析結果）
python -m src.main report
```

### 6. レポート出力（reporter.py）
- バッチ分析結果を人間が読みやすい形式で表示
- ターミナルでの色付き出力（ANSI color）
- メタカテゴリ → 関連エントリー → アクション提案の階層表示

## コーディング規約

- **言語**: Python 3.11+、型ヒント必須
- **docstring**: Google style
- **エラーハンドリング**: 外部APIコール・HTTP通信は必ずtry/exceptで処理
- **ログ**: loggingモジュール使用（print文ではなく）
- **テスト**: pytest、主要関数にユニットテスト
- **日本語**: UIテキスト・ログメッセージは日本語（コード・変数名は英語）

## 環境変数

```
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

## 注意事項

- Step 1は自分専用ツールなので、認証・セキュリティは不要
- OGPスクレイピングはサイトの利用規約を尊重し、過度なアクセスをしない
- Claude API呼び出しはコスト意識を持つ（Sonnetモデルを使用、不要な再分析を避ける）
- SQLiteのDBファイルは `data/knowledge.db` に保存
- .gitignoreで .env と data/ を除外
