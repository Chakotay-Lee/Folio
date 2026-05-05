# Folio — スマート個人ライブラリ

**言語：** [English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md) | 日本語

セルフホスト型の個人ライブラリシステムです。PDF・EPUB・TXT・Markdown ファイルをフォルダに置くだけで、Folio が LLM を使って自動的にメタデータを抽出し、セマンティック検索インデックスを構築します。シンプルなブラウザ UI でコレクションを閲覧・検索・読書できます。

---

## 機能

- **自動取り込み** — 設定フォルダを監視し、新しいファイルを自動処理
- **LLM メタデータ抽出** — OpenAI 互換・Ollama・Anthropic の任意モデルを使用してタイトル・著者・概要・タグ・ジャンルパスを自動生成
- **セマンティック検索** — ChromaDB によるベクトル検索；キーワードではなく意味で本を探せる
- **重複検出** — SimHash 近似ハッシュで重複インデックスを防止
- **カバー抽出** — PDF/EPUB からカバー画像を抽出、取得不可時は生成カラーにフォールバック
- **ブラウザ内閲覧** — インライン PDF ビューアと内蔵 EPUB リーダー
- **本のアップロード** — ブラウザからドラッグ＆ドロップまたはファイル選択でアップロード
- **多言語 UI** — English・繁體中文・简体中文・日本語 に切り替え可能
- **AI 出力言語** — 概要・タグ・ジャンルをサポート言語で生成可能
- **OCR サポート** — PaddleOCR をオプションで有効化し、スキャン PDF に対応

---

## アーキテクチャ

```
Library/
├── backend/               # FastAPI + SQLModel + ChromaDB
│   ├── main.py            # API ルーティング、アプリライフサイクル
│   ├── config_loader.py   # config.json → AppConfig データクラス
│   ├── ingestion/
│   │   ├── pipeline.py    # ingest_file()：抽出 → 重複排除 → LLM → DB → ベクトル
│   │   ├── extractor.py   # テキスト抽出（PDF/EPUB/TXT/MD）
│   │   ├── cover.py       # カバー画像抽出
│   │   ├── dedup.py       # SimHash 近似重複チェック
│   │   └── ocr.py         # オプション PaddleOCR
│   ├── llm/
│   │   ├── prompts.py     # 多言語抽出プロンプトビルダー
│   │   ├── openai_provider.py
│   │   ├── ollama_provider.py
│   │   └── anthropic_provider.py
│   ├── db/
│   │   ├── core.py        # SQLite（書籍データ、SQLModel 経由）
│   │   └── activity.py    # ユーザーアクティビティ DB
│   ├── vector_store.py    # ChromaDB ラッパー
│   └── watcher.py         # ファイルシステム監視（watchdog）
│
├── frontend/              # React 19 + Vite + Tailwind
│   └── src/
│       ├── pages/
│       │   ├── DashboardPage.tsx   # ライブラリ概要 + アップロード
│       │   ├── NotesPage.tsx       # ブラウズ + ジャンル/タグ絞り込み
│       │   ├── DiscoverPage.tsx    # セマンティック検索
│       │   ├── ProfilePage.tsx     # 統計
│       │   ├── FoldersPage.tsx     # 監視フォルダ + スキャン
│       │   └── SettingsPage.tsx    # LLM 設定 + 言語
│       ├── lib/
│       │   ├── i18n.ts             # 翻訳辞書
│       │   └── LangContext.tsx     # React Context + localStorage 同期
│       └── components/
│
├── config.json            # 実行時設定（.gitignore 済み）
├── config.json.example    # 設定テンプレート
└── Procfile               # foreman / overmind 起動コマンド
```

---

## 動作要件

- **Python 3.10+** と [uv](https://github.com/astral-sh/uv)
- **Node.js 18+**
- 以下のいずれか：
  - [Ollama](https://ollama.ai)（ローカルで実行、無料・オフライン）
  - OpenAI API キー
  - Anthropic API キー

---

## セットアップ

### 1. 設定ファイルのコピーと編集

```bash
cp config.json.example config.json
```

`config.json` を編集して LLM プロバイダーと書籍フォルダを設定します：

```json
{
  "storage_paths": {
    "pdf_roots": ["/Users/you/Books"],
    "watch_folders": ["/Users/you/Books"]
  },
  "llms": {
    "extraction_model": {
      "provider": "ollama",
      "model_name": "llama3.2",
      "base_url": "http://localhost:11434"
    },
    "embedding_model": {
      "provider": "ollama",
      "model_name": "nomic-embed-text",
      "dimension": 768,
      "base_url": "http://localhost:11434"
    }
  }
}
```

### 2. バックエンド依存パッケージのインストール

```bash
cd backend
uv sync
```

OCR サポートを有効にする場合（任意）：

```bash
uv sync --extra ocr
```

### 3. フロントエンド依存パッケージのインストール

```bash
cd frontend
npm install
```

### 4. サーバーの起動

[foreman](https://github.com/ddollar/foreman) または [overmind](https://github.com/DarthSim/overmind) を使用する場合：

```bash
foreman start
# または
overmind start
```

個別に起動する場合：

```bash
# ターミナル 1 — バックエンド（ポート 5201）
cd backend
uv run uvicorn backend.main:app --reload --port 5201

# ターミナル 2 — フロントエンド（ポート 5200）
cd frontend
npm run dev
```

ブラウザで **http://localhost:5200** を開きます。

---

## 設定パラメーター

| フィールド | 説明 | デフォルト |
|---|---|---|
| `storage_paths.pdf_roots` | 書籍をスキャンするフォルダ | `["books"]` |
| `storage_paths.watch_folders` | 新ファイルを監視するフォルダ（pdf_roots のサブセット） | pdf_roots と同じ |
| `llms.extraction_model` | メタデータ抽出に使用する LLM | — |
| `llms.embedding_model` | セマンティック埋め込みに使用するモデル | — |
| `llms.chat_model` | チャット機能に使用するモデル | — |
| `search_settings.top_k` | セマンティック検索の返却件数 | `10` |
| `search_settings.max_pages_to_analyze` | テキスト抽出時に読み取る最大ページ数 | `20` |
| `ocr.enabled` | 画像 PDF 向け PaddleOCR を有効化 | `true` |
| `ocr.min_chars_threshold` | この文字数未満の場合に OCR を実行 | `50` |
| `default_open_mode` | 書籍を開く方法：`system`・`browser`・`download` | `"system"` |
| `content_language` | AI 生成コンテンツの言語：`en`・`zh-TW`・`zh-CN`・`ja` | `"en"` |

LLM プロバイダーフィールド（`extraction_model`・`embedding_model`・`chat_model` 共通）：

| フィールド | 説明 |
|---|---|
| `provider` | `openai`・`ollama`・`anthropic` のいずれか |
| `model_name` | モデル識別子 |
| `base_url` | API ベース URL（Ollama およびカスタムエンドポイントは必須） |
| `api_key` | API キー（Ollama は空欄可） |
| `temperature` | サンプリング温度 |
| `max_tokens` | 最大レスポンストークン数 |
| `dimension` | 埋め込みベクトル次元数（embedding_model のみ） |

---

## サポートファイル形式

| 形式 | テキスト抽出 | カバー抽出 |
|---|---|---|
| PDF | PyMuPDF（+ オプション OCR） | 1 ページ目レンダリング |
| EPUB | ebooklib | マニフェストからカバー画像 |
| TXT | 直接読み取り | — |
| Markdown | 直接読み取り | — |

---

## API 概要

すべてのエンドポイントは `/api` 以下にあります。

| メソッド | パス | 説明 |
|---|---|---|
| `GET` | `/books` | ページネーション付き書籍一覧（`page`・`limit`・`genre`・`tag`・`q` でフィルタ） |
| `GET` | `/books/stats` | 集計値：書籍数・容量・ジャンル数・タグ数・形式別内訳 |
| `GET` | `/books/tags` | 全タグと出現回数 |
| `GET` | `/books/genres` | 全ジャンルパスと出現回数 |
| `POST` | `/books/upload` | 書籍ファイルのアップロード（multipart） |
| `GET` | `/books/{id}` | 書籍の詳細情報 |
| `PUT` | `/books/{id}` | 書籍メタデータの更新 |
| `DELETE` | `/books/{id}` | 書籍の削除（実ファイルの削除も選択可） |
| `GET` | `/books/{id}/cover` | カバー画像 |
| `GET` | `/books/{id}/file` | 書籍ファイル（`?mode=inline` または `?mode=download`） |
| `POST` | `/books/{id}/open` | システムアプリで開く（ローカルホストのみ） |
| `POST` | `/books/{id}/reclassify` | 1 冊の LLM 抽出を再実行 |
| `POST` | `/books/reclassify-all` | 全書籍の LLM 抽出を再実行 |
| `GET` | `/search/semantic` | ベクトル検索（`?q=クエリ文字列`） |
| `GET` | `/folders` | 監視フォルダの状態 |
| `POST` | `/folders/scan` | 全監視フォルダのスキャンを開始 |
| `POST` | `/folders/scan-path` | 指定ディレクトリを一度だけスキャン |
| `GET` | `/ingestion/logs` | 最近の取り込みログ（直近 100 件） |
| `GET` | `/config` | 現在の config.json を取得 |
| `PUT` | `/config` | config.json にパッチを深くマージして再読み込み |

---

## データの保存場所

デフォルトでは、すべての永続データは `config.json` と同じ場所に保存されます：

| パス | 内容 |
|---|---|
| `library_core.db` | SQLite — 書籍レコード |
| `user_activity.db` | SQLite — ユーザーアクティビティ |
| `vector_store/` | ChromaDB — 埋め込みインデックス |
| `assets/` | 抽出したカバー画像 |

データディレクトリを変更するには、`config.json` の `storage_paths.*` に絶対パスを設定してください。

---

## インデックスの再構築

埋め込みモデルを変更すると、既存のベクトルインデックスが新しいモデルと互換性を失います。**Settings → Re-index**（または `POST /api/reindex`）で再構築してください。SQLite の書籍レコードはそのまま保持され、ChromaDB インデックスのみ次回スキャン時に再構築されます。

---

## ライセンス

MIT
