# Folio — 智慧個人書庫 `v0.2.0`

**語言：** [English](README.md) | 繁體中文 | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

自架式個人書庫系統。將 PDF、EPUB、TXT、Markdown 檔案放入指定資料夾，Folio 即自動以 LLM 提取後設資料、建立語意搜尋索引，並提供簡潔的瀏覽器介面供瀏覽、搜尋與閱讀。

---

> [!WARNING]
> **Token 用量警告 — 強烈建議使用本地 LLM**
>
> Folio 在處理**每一本書**時都會呼叫 LLM 來提取後設資料（書名、作者、摘要、標籤、分類）。書庫較大時，累積的 Token 用量相當可觀。若使用 OpenAI 或 Anthropic 等商業 API，費用可能迅速累積。
> **強烈建議透過 [Ollama](https://ollama.ai) 在本機執行模型，既免費又保有隱私。**
>
> **深度解析的 Token 消耗可能相當可觀**
>
> 深度解析會逐頁處理整本書。一本含圖表的 300 頁掃描書籍，使用雲端模型時可能消耗 **50 萬至 100 萬以上 Token**。建議先用頁碼範圍進行小規模測試，或使用 Quick 模式。詳見[深度解析使用指南](docs/deep-analysis.zh-TW.md#token-消耗估算)。
>
> **OCR 功能需要支援視覺（多模態）的模型**
>
> 選配的 OCR 功能會將頁面圖片傳送給 LLM，以辨識純圖片或掃描版 PDF 中的文字。此功能需要支援**圖片輸入**的模型，純文字模型無法使用。建議選擇 [Qwen2-VL](https://ollama.ai/library/qwen2-vl)、Gemma 3/4、LLaVA 或其他支援多模態輸入的模型。

---

## 功能特色

- **自動匯入** — 監聽指定資料夾，有新檔案即自動處理
- **LLM 後設資料提取** — 使用任意 OpenAI 相容、Ollama 或 Anthropic 模型，自動產生書名、作者、摘要、標籤、分類路徑
- **語意搜尋** — 透過 ChromaDB 向量搜尋；依語意找書，不只靠關鍵字
- **重複偵測** — SimHash 近似雜湊過濾，防止重複建立索引
- **封面提取** — 從 PDF/EPUB 提取封面圖片，無法提取時自動產生色塊
- **瀏覽器閱讀** — 內嵌 PDF 檢視器與 EPUB 閱讀器
- **書藉上傳** — 直接從瀏覽器拖拉或選取檔案上傳
- **多語系介面** — 支援 English、繁體中文、简体中文、日本語
- **AI 輸出語言** — 摘要、標籤、分類可用任意支援語言產生
- **OCR 支援** — 選配 VLM 辨識，將掃描版/純圖片 PDF 的頁面圖片送交 `analysis_model`（或 `extraction_model`）提取文字
- **深度解析** — 手動觸發逐本 AI 分析管道，完成後解鎖 HTML 匯出、TTS 語音及完整內文 Book Chat。包含章節偵測、全文提取、圖形擷取、圖形描述、章節摘要及自含式 HTML 匯出。選配的輸出語言設定，可讓 AI 以指定語言產生章節摘要，作為個人**閱讀輔助**用途，並非原著的翻譯版本。 → [深度解析使用指南](docs/deep-analysis.zh-TW.md)
- **書籍對話** — 對已解析書籍進行 RAG 問答。以章節**摘要**作為基準上下文傳送給 LLM；完整章節內文透過 **tool calling** 按需取得，即使書籍篇幅龐大也能維持低 token 用量。圖形以 ID 參照並於對話中內嵌顯示。對話記錄本地持久化儲存。
- **文字轉語音** — 從章節摘要或完整章節內文生成音訊。支援 **OpenAI TTS API**（模型：`tts-1`/`tts-1-hd`；語音：alloy、echo、fable、onyx、nova、shimmer）、**AIVIS**（VOICEVOX 相容本地伺服器）、**Gemini TTS**，以及**本地執行檔**引擎（Piper、Kokoro 或任何支援 stdin→stdout MP3 的執行檔）。可在設定頁面配置。從書籍詳細面板點選「分析結果與 TTS」進入。

---

## 深度解析與 Book Chat

Folio 不只是書藉索引工具，它還能**閱讀書籍，並和你一起討論內容**。

對一本書觸發深度解析後，Folio 會執行完整的 AI 分析管道：

1. **章節偵測** — 識別整份 PDF 的章節邊界
2. **全文提取** — 逐章提取全文（掃描頁面使用 VLM OCR）
3. **圖表擷取** — 定位並裁切內嵌圖片，並為每張圖產生文字描述
4. **章節摘要** — 以設定的 LLM 為每章產生 ≤300 字摘要；選配的語言設定可輸出指定語言的摘要，作為個人閱讀輔助，並非對原著的重製或翻譯
5. **HTML 匯出** — 將摘要、圖表與後設資料打包成自含式 HTML 檔案，僅供個人參考使用

**額外提示詞（extra prompt）** 欄位讓你自訂 AI 解讀和摘要書籍的方式。以下是一些範例：

| 提示詞 | 效果 |
|---|---|
| `"用小學生也能懂的方式解說每一章"` | 語言簡化，適合快速掌握陌生領域 |
| `"每段結尾加「喵」，用貓咪的口吻解說"` | 趣味呈現，幫助記憶枯燥內容 |
| `"用一個生活中的比喻來說明每章的核心概念"` | 以類比加深理解 |
| `"每章給我 3 條重點，不要廢話"` | 快速複習用的精煉摘要 |

這些輸出為個人閱讀輔助，請勿對外散布從受著作權保護著作衍生的 AI 生成內容。

分析完成後，開啟 **Book Chat** 即可讓 AI 陪你討論這本書的內容。AI 以章節摘要作為基準上下文，並在需要時透過 tool calling 按需取得完整章節內文，在維持低 token 用量的同時，仍能回答具體細節問題。擷取的圖表會在對話中內嵌顯示。

> **深度解析推薦模型：** 圖表擷取與掃描 PDF OCR 需要**多模態（支援視覺輸入）**的模型。目前測試中，**Qwen2-VL / Qwen3**（例如透過 Ollama 使用 `qwen2-vl:7b`）在圖表偵測與文字辨識準確度上表現最佳。

---

## 架構

```
Library/
├── backend/               # FastAPI + SQLModel + ChromaDB
│   ├── main.py            # API 路由、應用程式生命週期
│   ├── config_loader.py   # config.json → AppConfig 資料類別
│   ├── ingestion/
│   │   ├── pipeline.py    # ingest_file()：提取 → 去重 → LLM → DB → 向量
│   │   ├── extractor.py   # 文字提取（PDF/EPUB/TXT/MD）
│   │   ├── cover.py       # 封面圖片提取
│   │   ├── dedup.py       # SimHash 近似重複檢查
│   │   └── ocr.py         # 選配 VLM OCR
│   ├── llm/
│   │   ├── prompts.py     # 多語系提取 prompt 產生器
│   │   ├── openai_provider.py
│   │   ├── ollama_provider.py
│   │   └── anthropic_provider.py
│   ├── db/
│   │   ├── core.py        # SQLite（書藉資料，透過 SQLModel）
│   │   └── activity.py    # 使用者活動資料庫
│   ├── vector_store.py    # ChromaDB 包裝
│   └── watcher.py         # 檔案系統監聽（watchdog）
│
├── frontend/              # React 19 + Vite + Tailwind
│   └── src/
│       ├── pages/
│       │   ├── DashboardPage.tsx   # 書庫總覽 + 上傳
│       │   ├── NotesPage.tsx       # 瀏覽 + 依分類/標籤過濾
│       │   ├── DiscoverPage.tsx    # 語意搜尋
│       │   ├── ProfilePage.tsx     # 統計資料
│       │   ├── FoldersPage.tsx     # 監控資料夾 + 掃描
│       │   └── SettingsPage.tsx    # LLM 設定 + 語言
│       ├── lib/
│       │   ├── i18n.ts             # 翻譯字典
│       │   └── LangContext.tsx     # React Context + localStorage 同步
│       └── components/
│
├── config.json            # 執行期設定（已加入 .gitignore）
├── config.json.example    # 設定範本
└── Procfile               # foreman / overmind 啟動指令
```

---

## 系統需求

- **Python 3.10+** 搭配 [uv](https://github.com/astral-sh/uv)
- **Node.js 18+**
- 以下擇一：
  - [Ollama](https://ollama.ai) 在本機執行（免費、離線）
  - OpenAI API 金鑰
  - Anthropic API 金鑰

---

## 安裝與設定

### 1. 複製並設定設定檔

```bash
cp config.json.example config.json
```

編輯 `config.json`，設定 LLM 提供者與書庫資料夾：

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

### 2. 安裝後端相依套件

```bash
cd backend
uv sync
```

### 3. 安裝前端相依套件

```bash
cd frontend
npm install
```

### 4. 啟動服務

使用 [foreman](https://github.com/ddollar/foreman) 或 [overmind](https://github.com/DarthSim/overmind)：

```bash
foreman start
# 或
overmind start
```

或分別在兩個終端機手動啟動：

```bash
# 終端機 1 — 後端（埠號 5201）
cd backend
uv run uvicorn backend.main:app --reload --port 5201

# 終端機 2 — 前端（埠號 5200）
cd frontend
npm run dev
```

在瀏覽器開啟 **http://localhost:5200**。

---

## 設定參數說明

| 欄位 | 說明 | 預設值 |
|---|---|---|
| `storage_paths.pdf_roots` | 要掃描書藉的資料夾 | `["books"]` |
| `storage_paths.watch_folders` | 監控新檔案的資料夾（pdf_roots 的子集） | 同 pdf_roots |
| `llms.extraction_model` | 用於後設資料提取的 LLM | — |
| `llms.embedding_model` | 用於語意嵌入的模型 | — |
| `llms.chat_model` | 用於對話功能的模型 | — |
| `llms.analysis_model` | 深度解析使用的 VLM（圖形擷取、OCR、圖形描述）。未設定時沿用 `extraction_model` | — |
| `tts.provider` | TTS 引擎：`openai`、`aivis`、`gemini` 或 `local` | `"openai"` |
| `tts.model` | TTS 模型（`tts-1`、`tts-1-hd`、`gemini-2.5-flash-preview-tts` 等） | `"tts-1"` |
| `tts.voice` | 語音名稱（OpenAI：`alloy`/`echo`/…；Gemini：`Aoede`/`Charon`/…） | `"alloy"` |
| `tts.api_key` | API 金鑰（`openai` 和 `gemini` 提供者必填） | `""` |
| `tts.base_url` | AIVIS 伺服器基礎 URL（例：`http://localhost:10101`） | `""` |
| `tts.speaker_id` | AIVIS 說話者/風格 ID | `0` |
| `tts.binary_path` | 本地 TTS 執行檔路徑（`provider: local` 時使用） | `""` |
| `tts.chunk_size` | 每次 TTS 請求的最大字元數 | `4000` |
| `search_settings.top_k` | 語意搜尋回傳結果數 | `10` |
| `search_settings.max_pages_to_analyze` | 文字提取時讀取的最大頁數 | `20` |
| `ocr.enabled` | 啟用 VLM OCR 處理圖片 PDF | `true` |
| `ocr.min_chars_threshold` | 低於此字元數才觸發 OCR | `50` |
| `default_open_mode` | 開啟書藉方式：`system`、`browser`、`download` | `"system"` |
| `content_language` | AI 產生內容的語言：`en`、`zh-TW`、`zh-CN`、`ja` | `"en"` |

LLM 提供者欄位（適用於 `extraction_model`、`embedding_model`、`chat_model`）：

| 欄位 | 說明 |
|---|---|
| `provider` | `openai`、`ollama`、`anthropic` 或 `gemini` |
| `model_name` | 模型識別碼 |
| `base_url` | API 基礎 URL（Ollama 及自訂端點必填） |
| `api_key` | API 金鑰（Ollama 可留空） |
| `temperature` | 採樣溫度 |
| `max_tokens` | 最大回應 token 數 |
| `dimension` | 嵌入向量維度（僅 embedding_model） |

---

## 支援格式

| 格式 | 文字提取 | 封面提取 |
|---|---|---|
| PDF | PyMuPDF（+ 選配 VLM OCR） | 第一頁渲染 |
| EPUB | ebooklib | 從 manifest 提取封面圖片 |
| TXT | 直接讀取 | — |
| Markdown | 直接讀取 | — |

---

## API 概覽

所有端點均在 `/api` 路徑下。

| 方法 | 路徑 | 說明 |
|---|---|---|
| `GET` | `/books` | 分頁書藉列表，支援過濾（`page`、`limit`、`genre`、`tag`、`q`） |
| `GET` | `/books/stats` | 彙總數字：書藉數、容量、分類數、標籤數、格式分布 |
| `GET` | `/books/tags` | 所有標籤及出現次數 |
| `GET` | `/books/genres` | 所有分類路徑及出現次數 |
| `POST` | `/books/upload` | 上傳書藉檔案（multipart） |
| `GET` | `/books/{id}` | 單本書藉詳細資料 |
| `PUT` | `/books/{id}` | 更新書藉後設資料 |
| `DELETE` | `/books/{id}` | 移除書藉（可選擇同時刪除實體檔案） |
| `GET` | `/books/{id}/cover` | 封面圖片 |
| `GET` | `/books/{id}/file` | 書藉檔案（`?mode=inline` 或 `?mode=download`） |
| `POST` | `/books/{id}/open` | 在系統應用程式中開啟（僅限本機） |
| `POST` | `/books/{id}/reclassify` | 對單本書重新執行 LLM 提取 |
| `POST` | `/books/reclassify-all` | 對所有書重新執行 LLM 提取 |
| `GET` | `/search/semantic` | 向量搜尋（`?q=查詢字串`） |
| `GET` | `/folders` | 監控資料夾狀態 |
| `POST` | `/folders/scan` | 觸發掃描所有監控資料夾 |
| `POST` | `/folders/scan-path` | 掃描指定的一次性目錄 |
| `GET` | `/ingestion/logs` | 最近匯入記錄（最後 100 筆） |
| `GET` | `/config` | 讀取目前 config.json |
| `PUT` | `/config` | 深度合併更新 config.json 並重新載入 |

---

## 資料儲存位置

預設情況下，所有持久化資料存放於 `config.json` 旁邊：

| 路徑 | 內容 |
|---|---|
| `library_core.db` | SQLite — 書藉記錄 |
| `user_activity.db` | SQLite — 使用者活動 |
| `vector_store/` | ChromaDB — 嵌入索引 |
| `assets/` | 提取的封面圖片 |
| `analysis/{book-uuid}/` | 每本書的深度解析資料：章節文字、摘要、擷取圖形、音訊快取、HTML 匯出 |

若要變更資料目錄，請在 `config.json` 的 `storage_paths.*` 中設定絕對路徑。

---

## 重建索引

更換嵌入模型後，現有向量索引會與新模型不相容。請至 **Settings → Re-index**（或 `POST /api/reindex`）重建。SQLite 的書藉記錄會保留；僅 ChromaDB 索引在下次掃描時重建。

---

## 已知問題

| 問題 | 說明 |
|---|---|
| 掃描 PDF 圖表擷取準確度 | 掃描頁面的圖表邊界偵測依賴 VLM 邊界框推斷，可能發生區域誤判或圖表遺漏。原生 PDF（含文字層）的準確度較高。 |
| 圖表擷取推薦模型 | 目前測試中，**Qwen2-VL / Qwen3** 在圖表偵測準確度上優於其他模型（如 LLaVA、Gemma）。 |
| 大型書藉 token 用量 | 深度解析會依序處理每一頁，書藉頁數較多（500頁以上）時，依模型與供應商不同，所需時間與 token 消耗可能相當可觀。 |

---

## 法律聲明

> **本聲明不構成法律建議。如有具體法律疑慮，請諮詢合格律師。**

**僅供個人使用。** Folio 是一款自架式個人書庫管理工具，設計用途為管理使用者依法擁有的書籍與文件，不得用於重製、再散布或商業利用他人受著作權保護的作品。

**內容合法性責任由使用者自負。** 使用者須自行確認對加入 Folio 的任何檔案擁有合法的儲存、索引與處理權利。本專案作者不支持、也不鼓勵將本工具用於未經授權取得的資料。

**第三方服務隱私聲明。** 使用雲端 LLM 提供者（OpenAI、Anthropic、Google Gemini 等）時，書籍的文字內容（包含擷取的段落與摘要）將傳送至該提供者的伺服器進行處理。使用前請詳閱各提供者的隱私政策與服務條款。如需完全在本地端處理資料，請透過 [Ollama](https://ollama.ai) 使用本地模型。

**翻譯與衍生著作。** 語言輸出選項所產生的是 AI 對書籍內容的摘要解讀，以指定語言呈現，目的是輔助使用者理解其合法持有的著作，並非對原文的完整重製或翻譯。依多數著作權法制，翻譯權屬著作財產權人專有（如台灣著作權法第 28 條、伯恩公約第 8 條）。使用者不得利用本功能製作、散布或發行受著作權保護著作的翻譯版本或其他衍生著作，除非已取得著作財產權人之授權。

**無擔保聲明。** 本軟體依現況提供，不附任何形式的擔保。詳見下方 [MIT 授權](#授權) 條款。

---

## 授權

MIT
