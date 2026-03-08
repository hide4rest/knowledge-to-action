# Knowledge-to-Action MVP

SNS・Webで保存した情報をAIが分析し、具体的なアクションに変換するCLIツール。

## セットアップ

```bash
# リポジトリをクローン
cd knowledge-to-action

# 仮想環境作成
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存パッケージインストール
pip install -r requirements.txt

# 環境変数設定
cp .env.example .env
# .env を編集して ANTHROPIC_API_KEY を設定

# データディレクトリ作成
mkdir -p data
```

## 使い方

```bash
# 単一URLを追加して分析
python -m src.main add "https://note.com/example/n/n123456"

# Raindropのエクスポートファイルをインポート
python -m src.main import raindrop ~/Downloads/raindrop_export.csv

# 保存済みエントリー一覧
python -m src.main list
python -m src.main list --category テクノロジー --limit 10

# 全エントリーを横断分析してアクション提案を生成
python -m src.main analyze

# 最新のレポートを表示
python -m src.main report
```

## Raindropエクスポートの取得方法

1. [Raindrop.io](https://app.raindrop.io) にログイン
2. Settings → Export → CSV形式でダウンロード
3. `python -m src.main import raindrop ダウンロードしたファイル.csv`

## テスト

```bash
pytest tests/ -v
```

## アーキテクチャ

```
URL入力 / CSVインポート
    ↓
OGPメタデータ取得 + 本文抽出（scraper.py）
    ↓
SQLiteに保存（database.py）
    ↓
Claude APIで個別分析（analyzer.py）
    ↓
バッチ横断分析 → メタカテゴリ抽出 + アクション提案
    ↓
ターミナルレポート出力（reporter.py）
```
