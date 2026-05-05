# Folio — 智慧個人書庫

**語言：** [English](README.md) | 繁體中文 | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

自架式個人書庫系統。將 PDF、EPUB、TXT、Markdown 檔案放入指定資料夾，Folio 即自動以 LLM 提取後設資料、建立語意搜尋索引，並提供簡潔的瀏覽器介面供瀏覽、搜尋與閱讀。

---

> [!WARNING]
> **Token 用量警告 — 強烈建議使用本地 LLM**
>
> Folio 在處理**每一本書**時都會呼叫 LLM 來提取後設資料（書名、作者、摘要、標籤、分類）。書庫較大時，累積的 Token 用量相當可觀。若使用 OpenAI 或 Anthropic 等商業 API，費用可能迅速累積。
> **強烈建議透過 [Ollama](https://ollama.ai) 在本機執行模型，既免費又保有隱私。**
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
- **OCR 支援** — 選配 PaddleOCR，處理純圖片掃描 PDF

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
│   │   └── ocr.py         # 選配 PaddleOCR
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

選配 OCR 支援：

```bash
uv sync --extra ocr
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
| `search_settings.top_k` | 語意搜尋回傳結果數 | `10` |
| `search_settings.max_pages_to_analyze` | 文字提取時讀取的最大頁數 | `20` |
| `ocr.enabled` | 啟用 PaddleOCR 處理圖片 PDF | `true` |
| `ocr.min_chars_threshold` | 低於此字元數才觸發 OCR | `50` |
| `default_open_mode` | 開啟書藉方式：`system`、`browser`、`download` | `"system"` |
| `content_language` | AI 產生內容的語言：`en`、`zh-TW`、`zh-CN`、`ja` | `"en"` |

LLM 提供者欄位（適用於 `extraction_model`、`embedding_model`、`chat_model`）：

| 欄位 | 說明 |
|---|---|
| `provider` | `openai`、`ollama` 或 `anthropic` |
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
| PDF | PyMuPDF（+ 選配 OCR） | 第一頁渲染 |
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

若要變更資料目錄，請在 `config.json` 的 `storage_paths.*` 中設定絕對路徑。

---

## 重建索引

更換嵌入模型後，現有向量索引會與新模型不相容。請至 **Settings → Re-index**（或 `POST /api/reindex`）重建。SQLite 的書藉記錄會保留；僅 ChromaDB 索引在下次掃描時重建。

---

## 授權

MIT
