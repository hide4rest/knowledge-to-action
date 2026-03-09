# 改修指示書：analyzeコマンドの改善（v0.2）

## 概要

Step 1のプロトタイプを実際に使用した結果、以下3点の改善が必要と判明した。
この指示書に基づき、既存コードを改修すること。

### 改善要件
1. **ベイビーステップの導入** — アクション提案に段階的アプローチを追加
2. **レポートのボリューム増加** — 分析の深さと提案数を拡充
3. **期間指定分析 + 2層レポート構造** — 短期フォーカスと長期傾向の2層構造

---

## 改修1：CLIの `analyze` コマンドにオプション追加（main.py）

### 現状
```bash
python -m src.main analyze
# → 全エントリーを一括分析
```

### 改修後
```bash
# 直近7日間のエントリーを分析（デフォルト）
python -m src.main analyze

# 期間を指定して分析
python -m src.main analyze --days 7
python -m src.main analyze --days 14
python -m src.main analyze --days 30

# 全期間分析
python -m src.main analyze --days 0

# 直近N件を分析
python -m src.main analyze --recent 20

# 2層レポート（短期 + 長期）を同時生成 ★推奨
python -m src.main analyze --full
```

### 実装詳細

`main.py` の analyze サブコマンドに以下の引数を追加:

```python
analyze_parser.add_argument('--days', type=int, default=7,
    help='分析対象の日数（0で全期間）')
analyze_parser.add_argument('--recent', type=int, default=None,
    help='直近N件を分析')
analyze_parser.add_argument('--full', action='store_true',
    help='2層レポート（短期7日+長期全期間）を同時生成')
```

`--full` が指定された場合:
1. 短期分析（直近7日）を実行
2. 長期分析（全期間）を実行
3. 両方の結果を統合して1つの2層レポートとして保存

---

## 改修2：database.py にフィルタリング機能を追加

### 追加メソッド

```python
def get_entries_by_period(self, days: int) -> list[dict]:
    """指定日数以内のエントリーを取得する。
    
    Args:
        days: 遡る日数。0の場合は全件取得。
    
    Returns:
        エントリーのリスト
    """
    if days == 0:
        # 全件取得
        ...
    else:
        # WHERE created_at >= datetime('now', f'-{days} days')
        ...

def get_recent_entries(self, limit: int) -> list[dict]:
    """直近N件のエントリーを取得する。
    
    Args:
        limit: 取得件数
    
    Returns:
        エントリーのリスト（created_at降順）
    """
    # ORDER BY created_at DESC LIMIT {limit}
    ...

def get_entry_count_by_period(self, days: int) -> int:
    """指定期間内のエントリー数を返す。
    分析前の件数チェックに使用。
    """
    ...
```

---

## 改修3：analyzer.py のプロンプト改修

### 3-A. 個別分析プロンプト（変更なし）
現状のままで良い。

### 3-B. 短期バッチ分析プロンプト（新規作成）

`analyze_batch_short_term` メソッドを新設する。

```python
SHORT_TERM_PROMPT = """
あなたはパーソナルナレッジコーチです。
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
      "related_entries": [関連エントリーのID配列],
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
}}
"""
```

### 3-C. 長期バッチ分析プロンプト（既存プロンプトを改修）

既存の `analyze_batch` メソッドを `analyze_batch_long_term` にリネームし、
プロンプトを以下に差し替える。

```python
LONG_TERM_PROMPT = """
あなたはパーソナルナレッジコーチです。
以下はユーザーが「全期間」にわたって保存したWebページの分析結果一覧です。

長期的な視点で、ユーザー自身も気づいていない関心パターンや、
複数の関心領域が交差するポイントを発見してください。

■ 重要なルール:
- メタカテゴリ（表面的なカテゴリではなく、複数の保存が束になった上位テーマ）を3〜5個抽出すること
- 各メタカテゴリについて「関心の強度」と「時間的な変化」（増加傾向/安定/減少傾向）を分析すること
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
      "related_entries": [関連エントリーのID配列],
      "insight": "このパターンから読み取れる深いインサイト",
      "entry_count": "このカテゴリに属するエントリー数"
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
}}
"""
```

---

## 改修4：analyzer.py に2層分析メソッドを追加

```python
def analyze_full(self, db) -> dict:
    """2層レポート（短期+長期）を生成する。
    
    Returns:
        {
            "short_term": 短期分析結果のdict,
            "long_term": 長期分析結果のdict,
            "generated_at": ISO形式のタイムスタンプ
        }
    """
    # 1. 短期分析（直近7日）
    short_entries = db.get_entries_by_period(days=7)
    if len(short_entries) < 3:
        # 7日で3件未満なら14日に拡張
        short_entries = db.get_entries_by_period(days=14)
    short_result = self.analyze_batch_short_term(short_entries)
    
    # 2. 長期分析（全期間）
    all_entries = db.get_entries_by_period(days=0)
    long_result = self.analyze_batch_long_term(all_entries)
    
    # 3. 統合
    return {
        "short_term": short_result,
        "long_term": long_result,
        "generated_at": datetime.now().isoformat()
    }
```

---

## 改修5：reporter.py のレポート表示を2層構造に対応

### レポート表示の構成

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📋 Knowledge-to-Action レポート
  生成日時: 2026-03-09 15:30:00
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

╔══════════════════════════════════════════╗
║  🔥 第1部：今週のフォーカス（直近7日間）   ║
║  対象: XX件の保存情報                     ║
╚══════════════════════════════════════════╝

■ 今のあなたの関心テーマ
  🎯 [テーマ名] ⚡緊急度: 高
     → 説明テキスト
     → 関連: 記事A, 記事B, 記事C

■ 今すぐできるアクション（ベイビーステップ付き）

  [1/5] 🏃 アクションタイトル
        なぜ？: 提案理由
        根拠: 「記事タイトル」より
        
        📌 Step 1（5分）: xxxxxxxxxx
        📌 Step 2（30分）: xxxxxxxxxx
        📌 Step 3（3日）: xxxxxxxxxx
        
        ✅ 期待される成果: xxxxxxxxxx
  
  [2/5] 🏃 アクションタイトル
        ...

■ 今日のクイックウィン 🎉
  ・xxxxxxxxxx
  ・xxxxxxxxxx

╔══════════════════════════════════════════╗
║  🗺️ 第2部：あなたの関心マップ（全期間）    ║
║  対象: 全XX件の保存情報                    ║
╚══════════════════════════════════════════╝

■ メタカテゴリ（あなたの隠れた関心パターン）

  [1] 📂 カテゴリ名  強度:🔴高  傾向:📈上昇中
      → インサイト説明
      → 関連エントリー数: XX件

  [2] 📂 カテゴリ名  強度:🟡中  傾向:➡️安定
      ...

■ カテゴリ交差インサイト 💡
  ・「カテゴリA」×「カテゴリB」
    → ユニークな視点の説明
    → あなたの強み: xxxxxxxxxx

■ 中長期アクション（1〜3ヶ月）

  [1] 🚀 アクションタイトル
      📌 今週: xxxxxxxxxx
      📌 今月: xxxxxxxxxx
      📌 3ヶ月後: xxxxxxxxxx

■ ビジネスシード 💰

  [1] 💡 アイデア名
      独自性: xxxxxxxxxx
      検証の次の一手: xxxxxxxxxx

■ 見落としているかもしれない視点 👀
  ・xxxxxxxxxx

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 実装上の注意
- ANSIカラーコードを使用してターミナルで色付き表示
- 各セクションの区切りを明確に
- エントリー数が0の場合は「保存情報が不足しています。URLを追加してください」と案内
- 短期分析のエントリーが3件未満の場合は「直近の保存が少ないため14日間に拡張しました」と表示

---

## 改修6：batch_reports テーブルのスキーマ拡張（database.py）

既存の `batch_reports` テーブルに `report_type` カラムを追加する。

```sql
-- マイグレーション
ALTER TABLE batch_reports ADD COLUMN report_type TEXT DEFAULT 'legacy';
-- 新しいレポートでは 'short_term', 'long_term', 'full' のいずれかを設定
-- 'full' は short_term と long_term を統合した2層レポート

ALTER TABLE batch_reports ADD COLUMN period_days INTEGER DEFAULT 0;
-- 分析対象の日数（0 = 全期間）
```

既存データとの互換性を保つため、ALTER TABLEで追加する。
テーブルが存在しない場合は新しいスキーマで作成する。

```sql
CREATE TABLE IF NOT EXISTS batch_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT DEFAULT 'full',
    report_json TEXT NOT NULL,
    period_days INTEGER DEFAULT 0,
    entry_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## テストの追加（tests/）

以下のテストケースを追加:

### test_database.py に追加
- `test_get_entries_by_period`: 日数指定でのフィルタリングが正しく動作すること
- `test_get_recent_entries`: 直近N件の取得が正しく動作すること
- `test_get_entries_by_period_zero`: days=0で全件取得されること

### test_analyzer.py に追加
- `test_short_term_prompt_format`: 短期プロンプトが正しくフォーマットされること
- `test_long_term_prompt_format`: 長期プロンプトが正しくフォーマットされること
- `test_analyze_full_integration`: 2層分析が正しいdict構造を返すこと

---

## 実装の優先順位

1. database.py のフィルタリング機能追加（依存なし）
2. analyzer.py のプロンプト改修（database.pyに依存）
3. main.py のCLIオプション追加（analyzer.pyに依存）
4. reporter.py の2層レポート表示（全てに依存）
5. テスト追加（全体完成後）

この順番で実装すること。各ステップ完了時にテストを実行して動作確認すること。

---

## 完了条件

- [ ] `python -m src.main analyze` で直近7日間の短期分析が実行される
- [ ] `python -m src.main analyze --days 30` で30日間の分析が実行される
- [ ] `python -m src.main analyze --full` で2層レポートが生成される
- [ ] `python -m src.main report` で2層レポートが見やすく表示される
- [ ] 各アクション提案に3段階のベイビーステップが含まれている
- [ ] アクション提案が5〜7個出力される
- [ ] 既存データ（legacy形式のreport）があっても正常に動作する
- [ ] `pytest tests/ -v` が全てパスする
