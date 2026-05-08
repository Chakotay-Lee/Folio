# Folio — スマート個人ライブラリ `v0.2.0`

**言語：** [English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md) | 日本語

セルフホスト型の個人ライブラリシステムです。PDF・EPUB・TXT・Markdown ファイルをフォルダに置くだけで、Folio が LLM を使って自動的にメタデータを抽出し、セマンティック検索インデックスを構築します。シンプルなブラウザ UI でコレクションを閲覧・検索・読書できます。

---

> [!WARNING]
> **トークン消費の警告 — ローカル LLM の使用を強く推奨**
>
> Folio は**書籍ごとに** LLM を呼び出してメタデータ（タイトル・著者・概要・タグ・ジャンル）を抽出します。大規模なライブラリでは消費トークン数が膨大になります。OpenAI や Anthropic などの商用 API を使用している場合、予想外のコストが発生する恐れがあります。
> **[Ollama](https://ollama.ai) でローカルモデルを実行することを強く推奨します。無料で利用でき、プライバシーも保たれます。**
>
> **深度解析のトークン消費は大きくなる場合があります**
>
> 深度解析はすべてのページを順番に処理します。図表を含む 300 ページのスキャン書籍では、クラウドモデル使用時に **50 万〜100 万トークン以上** を消費することがあります。まずページ範囲を絞ってテストするか、Quick モードをお試しください。詳細は[深度解析 使用ガイド](docs/deep-analysis.ja.md#トークン消費の目安)をご参照ください。
>
> **OCR にはビジョン対応（マルチモーダル）モデルが必要**
>
> オプションの OCR 機能は、スキャンや画像のみの PDF ページの文字を認識するために、ページ画像を LLM に送信します。この機能には**画像入力に対応したモデル**が必要です。テキスト専用モデルでは動作しません。[Qwen2-VL](https://ollama.ai/library/qwen2-vl)、Gemma 3/4、LLaVA など、マルチモーダル対応モデルの使用を推奨します。

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
- **OCR サポート** — VLM ベースの OCR をオプションで有効化し、スキャン PDF や画像のみの PDF のページ画像から `analysis_model`（または `extraction_model`）でテキストを抽出
- **深度解析** — 書籍ごとに手動で AI 分析パイプラインを起動し、HTML エクスポート・TTS 音声・完全テキスト Book Chat を解放します。章節検出・全文抽出・図形抽出・図形説明生成・章節要約・自己完結型 HTML エクスポートを含みます。オプションの出力言語設定により、指定した言語で章の要約を生成できます。これは個人的な**読書補助**を目的としたものであり、原著の翻訳ではありません。 → [深度解析 使用ガイド](docs/deep-analysis.ja.md)
- **ブック チャット** — 解析済み書籍に対する RAG ベースの Q&A。章の**要約**をベースラインコンテキストとして送信し、詳細が必要な場合のみ **tool calling** で章の全文を取得。大きな書籍でもトークン使用量を抑えられます。図はIDで参照され、会話内にインライン表示されます。会話履歴はローカルに永続保存されます。
- **テキスト読み上げ** — 章の要約または完全な章テキストから音声を生成。**OpenAI TTS API**（モデル：`tts-1`/`tts-1-hd`；音声：alloy、echo、fable、onyx、nova、shimmer）、**AIVIS**（VOICEVOX 互換ローカルサーバー）、**Gemini TTS**、および**ローカルバイナリ**エンジン（Piper、Kokoro、または stdin→stdout MP3 に対応した任意のバイナリ）をサポート。設定ページで構成できます。書籍詳細パネルの「分析結果・TTS」から開けます。

---

## 深度解析と Book Chat

Folio は書籍のインデックスツールにとどまらず、**書籍を読み込んで内容についてAIと対話する**こともできます。

書籍の深度解析を実行すると、Folio は完全な AI 分析パイプラインを走らせます：

1. **章検出** — PDF 全体の章境界を特定
2. **全文抽出** — 章ごとに全文を抽出（スキャンページは VLM OCR を使用）
3. **図表抽出** — 埋め込み画像を検出・クロップし、各図に説明文を生成
4. **章要約** — 設定した LLM で各章の ≤300 字要約を生成。言語設定により指定言語での出力が可能（個人的な読書補助用途であり、原著の複製・翻訳ではありません）
5. **HTML エクスポート** — 要約・図表・メタデータを自己完結型 HTML にまとめる（個人参照用途のみ）

**追加プロンプト（extra prompt）** フィールドで、AI による読解・要約の方法をカスタマイズできます。いくつかの例：

| プロンプト | 効果 |
|---|---|
| `"小学生にもわかる言葉で各章を説明してください"` | 難解な内容をやさしく言い換え |
| `"各段落の末尾に「にゃん」をつけて、猫の口調で解説してください"` | ユニークな語り口で記憶に残る読書体験 |
| `"各章の核心を日常のたとえ話ひとつで説明してください"` | 比喩による深い理解 |
| `"各章のポイントを箇条書き3つにまとめてください。余分な説明は不要です"` | 素早い復習のための要点整理 |

これらの出力は個人的な読書補助です。著作権で保護された著作物から派生した AI 生成コンテンツを外部に配布しないでください。

解析完了後、**Book Chat** を開くと AI と書籍の内容について会話できます。AI は章の要約をベースラインコンテキストとして受け取り、詳細が必要な場合のみ tool calling で章の全文を取得するため、トークン使用量を抑えながら詳細な質問にも答えられます。抽出された図表は会話内にインライン表示されます。

> **深度解析の推奨モデル：** 図表抽出やスキャン PDF の OCR には**マルチモーダル（ビジョン対応）**モデルが必要です。現在のテストでは、**Qwen2-VL / Qwen3**（例：Ollama で `qwen2-vl:7b`）が図表検出・テキスト認識の両面で最も高い精度を示しています。

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
│   │   └── ocr.py         # オプション VLM OCR
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
| `llms.analysis_model` | 深度解析に使用する VLM（図抽出・OCR・図説明）。未設定時は `extraction_model` を使用 | — |
| `tts.provider` | TTS エンジン：`openai`・`aivis`・`gemini`・`local` のいずれか | `"openai"` |
| `tts.model` | TTS モデル（`tts-1`・`tts-1-hd`・`gemini-2.5-flash-preview-tts` など） | `"tts-1"` |
| `tts.voice` | 音声名（OpenAI：`alloy`/`echo`/…；Gemini：`Aoede`/`Charon`/…） | `"alloy"` |
| `tts.api_key` | API キー（`openai` と `gemini` では必須） | `""` |
| `tts.base_url` | AIVIS サーバーのベース URL（例：`http://localhost:10101`） | `""` |
| `tts.speaker_id` | AIVIS の話者/スタイル ID | `0` |
| `tts.binary_path` | ローカル TTS バイナリのパス（`provider: local` の場合） | `""` |
| `tts.chunk_size` | TTS リクエストあたりの最大文字数 | `4000` |
| `search_settings.top_k` | セマンティック検索の返却件数 | `10` |
| `search_settings.max_pages_to_analyze` | テキスト抽出時に読み取る最大ページ数 | `20` |
| `ocr.enabled` | 画像 PDF 向け VLM OCR を有効化 | `true` |
| `ocr.min_chars_threshold` | この文字数未満の場合に OCR を実行 | `50` |
| `default_open_mode` | 書籍を開く方法：`system`・`browser`・`download` | `"system"` |
| `content_language` | AI 生成コンテンツの言語：`en`・`zh-TW`・`zh-CN`・`ja` | `"en"` |

LLM プロバイダーフィールド（`extraction_model`・`embedding_model`・`chat_model` 共通）：

| フィールド | 説明 |
|---|---|
| `provider` | `openai`・`ollama`・`anthropic`・`gemini` のいずれか |
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
| PDF | PyMuPDF（+ オプション VLM OCR） | 1 ページ目レンダリング |
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
| `analysis/{book-uuid}/` | 書籍ごとの深度解析データ：章テキスト・要約・抽出図・音声キャッシュ・HTML エクスポート |

データディレクトリを変更するには、`config.json` の `storage_paths.*` に絶対パスを設定してください。

---

## インデックスの再構築

埋め込みモデルを変更すると、既存のベクトルインデックスが新しいモデルと互換性を失います。**Settings → Re-index**（または `POST /api/reindex`）で再構築してください。SQLite の書籍レコードはそのまま保持され、ChromaDB インデックスのみ次回スキャン時に再構築されます。

---

## 既知の問題

| 問題 | 詳細 |
|---|---|
| スキャン PDF の図表抽出精度 | スキャンページの図表境界検出は VLM のバウンディングボックス推論に依存しており、領域の誤認識や図表の見落としが発生することがあります。テキストレイヤーを持つネイティブ PDF の方が精度は高くなります。 |
| 図表抽出の推奨モデル | 現在のテストでは **Qwen2-VL / Qwen3** が他のモデル（LLaVA、Gemma など）と比べて最も高い図表検出精度を示しています。 |
| 大きな書籍のトークン使用量 | 深度解析はすべてのページを順番に処理するため、非常に大きな書籍（500ページ以上）ではモデルとプロバイダーによっては処理時間とトークン消費が大きくなることがあります。 |

---

## 法的事項

> **本項目は法的アドバイスを構成するものではありません。具体的な法的懸念がある場合は、資格のある弁護士にご相談ください。**

**個人利用のみ。** Folio は、合法的に所有する書籍・文書を管理するための自己ホスト型個人ツールとして設計されています。著作権で保護された著作物の複製・再配布・商業的利用を促進する目的での使用は想定していません。

**コンテンツ合法性の責任はユーザーにあります。** Folio に追加するファイルの保存・インデックス化・処理に関する合法的な権利を保有していることを、ユーザー自身が確認する責任を負います。本プロジェクトの著者は、不正に取得した資料への本ツールの使用を支持・助長しません。

**第三者サービスのプライバシーについて。** クラウド系 LLM プロバイダー（OpenAI・Anthropic・Google Gemini 等）を使用する場合、書籍のテキスト内容（抽出された文章・要約を含む）がそれらのプロバイダーのサーバーに送信され処理されます。使用前に各プロバイダーのプライバシーポリシーおよび利用規約をご確認ください。データを完全にローカルで処理するには、[Ollama](https://ollama.ai) でローカルモデルを使用してください。

**翻訳および二次的著作物について。** 言語出力オプションが生成するのは、ユーザーが合法的に所持する著作物の内容を AI が解釈・要約したものであり、個人的な読書理解を補助することを目的としています。これらの出力は原文の完全な複製や翻訳ではありません。多くの著作権法制において、翻訳権は著作権者の専有権とされています（日本著作権法第 27 条、ベルヌ条約第 8 条など）。ユーザーは、著作権者の許諾なく、本機能を用いて著作物の翻訳版その他の二次的著作物を作成・配布・公開してはなりません。

**無保証。** 本ソフトウェアはいかなる保証もなく現状のまま提供されます。詳細は下記の [MIT ライセンス](#ライセンス) をご参照ください。

---

## ライセンス

MIT
