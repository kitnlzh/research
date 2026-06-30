# battery_research_rag

定置用蓄電池の複数市場参加研究（スポット市場・一次調整力市場・二次調整力市場の同時参加最適化）を支援する、最小構成の **RAG ＋ 実験結果管理 ＋ 考察生成** ツールです。

- 文書（PDF / txt / md / csv）を取り込み、ローカルベクトルDB（Chroma）に保存
- 質問に対して関連根拠を検索し、OpenAI があれば日本語で回答（根拠の出典付き）
- 実験結果CSVを整理し、研究発表・論文向けの考察を9項目で生成
- **OpenAI APIキーが無くても、文書取り込み・CSV整理・ローカルDB保存までは動作**します

> 重要な概念: SOC, DoD, 劣化コスト, 1次元/2次元ピースワイズ劣化モデル, MILP, Gurobi, 30分×48時刻, 目的関数値, 市場収益。
> 本ツールは既存の最適化コード（Gurobi 等）を改変しません。結果CSVを介して接続します。

---

## 1. セットアップ手順（Windows / PowerShell）

### 仮想環境の作り方
```powershell
cd battery_research_rag
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
> 実行ポリシーで止まる場合: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

### requirements のインストール
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```
> 最低限 `pandas` だけでも CSV整理・考察テンプレートは動きます。RAG（取り込み・検索）には `chromadb` と `pypdf` が必要です。

### src をパッケージとして使えるようにする
`python -m battery_rag.xxx` を実行できるよう、`src` を PYTHONPATH に通します。

PowerShell:
```powershell
$env:PYTHONPATH = "src"
```
または毎回 `-` で指定:
```powershell
python -c "import sys; sys.path.insert(0,'src')"   # 確認用
```
（恒久的にしたい場合は `pip install -e .` 用の設定を今後追加予定。現状は PYTHONPATH 方式。）

### .env の書き方
`.env.example` を `.env` にコピーして編集します。
```powershell
Copy-Item .env.example .env
notepad .env
```
OpenAI を使う場合のみ `OPENAI_API_KEY` を設定してください（無くても動きます）。
APIキーはコードに直書きせず、必ず `.env` で管理します。

---

## 2. 文書の投入方法

`data/` 配下にファイルを置きます（サブフォルダは自由、再帰的に読み込みます）。
```
data/
├─ papers/        … 論文PDFなど
├─ market_docs/   … 市場ルール・制度資料
├─ my_thesis/     … 自分の卒論・原稿（txt/md/pdf）
└─ results/       … 実験結果CSV
```

## 3. RAG の実行方法

### 取り込み（インデックス作成）
```powershell
python -m battery_rag.ingest --data-dir data --persist-dir chroma_db
```

### 質問する
```powershell
python -m battery_rag.ask "2次元劣化モデルを入れる意味を説明して" --k 6
```
- `OPENAI_API_KEY` があれば日本語の回答を生成し、根拠（ファイル名・ページ・チャンク）を表示します。
- 無い場合は、検索でヒットした根拠チャンクをそのまま表示します。

## 4. 実験結果CSVの置き方と利用

`data/results/` に CSV を置きます。想定列（無くても落ちません）:

| 列 | 意味 |
|----|------|
| experiment_id | 実験ID |
| date | 日付 |
| case | ケース名 |
| market_pattern | 参加市場の組み合わせ |
| objective_value | 目的関数値 |
| spot_revenue | スポット市場収益 |
| reserve_revenue | 調整力市場収益 |
| degradation_cost | 劣化コスト |
| avg_soc / min_soc / max_soc | SOC 指標 |
| total_charge / total_discharge | 充放電量 |
| max_dod | 最大 DoD |
| comment | 備考 |

### 結果の確認
```powershell
python -m battery_rag.result_loader --csv data/results/sample_results.csv
```

### 結果の考察
```powershell
python -m battery_rag.result_analyzer --csv data/results/sample_results.csv
```
9項目（実験条件 / 数値結果 / Case間の違い / SOC運用 / 劣化コスト / 市場運用上の解釈 / 主張候補 / 追加実験案 / 文章案）で出力します。
APIキーが無い場合は数値ベースのテンプレート考察、ある場合は LLM 生成の考察になります。

> `examples/sample_results.csv` で動作確認できます。

---

## 5. よくあるエラー

| 症状 | 原因 / 対処 |
|------|------------|
| `ModuleNotFoundError: battery_rag` | `$env:PYTHONPATH = "src"` を設定したか確認 |
| `'pandas' が見つかりません` | `pip install -r requirements.txt` |
| `'chromadb' が見つかりません` | RAG（ingest/ask）には `pip install chromadb` が必要 |
| PDFからテキストが取れない | 画像PDFの可能性。`PyMuPDF` を試すか OCR 前処理が必要 |
| 日本語が文字化け | txt は UTF-8 推奨（cp932 も自動試行します） |
| ベクトルDBが空 | 先に `ingest` を実行 |
| OpenAI エラー | `.env` の `OPENAI_API_KEY` と利用枠を確認。未設定でも検索表示は可能 |

---

## 6. 今後の拡張案

- `pip install -e .`（pyproject.toml）でパッケージ化し PYTHONPATH 設定を不要に
- ローカル embedding（sentence-transformers）の常用化と精度評価
- Gurobi 最適化コードからの結果CSV自動出力フックを追加
- matplotlib による SOC 推移・収益内訳の自動可視化
- 市場価格データとの突き合わせ（時刻別収益分解）
- 簡易 Web UI（Streamlit 等）

---

## ファイル構成と役割

```
battery_research_rag/
├─ README.md
├─ requirements.txt
├─ .env.example          … 設定テンプレート（.env にコピー）
├─ data/                 … 投入文書・結果CSV（中身は git 管理外）
├─ chroma_db/            … ローカルベクトルDB（git 管理外）
├─ prompts/
│  ├─ system_prompt.txt  … 質問応答のシステムプロンプト
│  └─ analysis_prompt.txt… 考察生成のプロンプト
├─ src/battery_rag/
│  ├─ config.py          … .env からの設定読み込み
│  ├─ loaders.py         … PDF/txt/md/csv 読み込み
│  ├─ chunking.py        … 文書のチャンク分割
│  ├─ vector_store.py    … Chroma + embedding（OpenAI/ローカル/簡易の3段fallback）
│  ├─ ingest.py          … 取り込みCLI
│  ├─ ask.py             … 質問応答CLI
│  ├─ result_loader.py   … 実験結果CSV整理CLI
│  ├─ result_analyzer.py … 考察生成CLI
│  └─ utils.py           … ロギング等の共通処理
└─ examples/
   ├─ sample_question.txt
   └─ sample_results.csv
```

## 制限事項

- 簡易ハッシュ embedding は動作確認用で、意味検索の精度は限定的です。実利用では OpenAI もしくは sentence-transformers を推奨します。
- 画像のみのPDF（スキャン）はテキスト抽出できません（OCR 未対応）。
- LlamaIndex/LangChain は使わず、chromadb を直接利用する軽量実装にしています（依存を減らし、APIキー無しでの動作を優先）。
