這是一份為您量身定制的、涵蓋所有需求與決策的**《Smart Personal PDF Library System - 完整技術規格書 (v1.0)》**。

這份文檔已結構化，可直接作為 **System Prompt** 輸入給 Claude Code、Cursor 或任何開發團隊。

---

# 📘 Smart Personal PDF Library System
## Technical Specification Document (v1.0)

### 1. Project Overview (專案概述)
*   **目標**：構建一個純本地化、全格式支援（PDF/EPUB/TXT/MD）、具備智能分層分類與多語言檢索能力的個人知識管理系統。
*   **核心價值**：隱私安全、數據可攜性（移動磁碟可用）、智能推薦、雙庫隔離。
*   **運行環境**：macOS (Optimized for Apple Silicon M2/M3 Ultra, 192GB RAM)。
*   **開發語言**：Backend (Python + `uv`), Frontend (React + Vite + TypeScript)。

---

### 2. System Architecture (系統架構)
採用 **前後端分離** 的模組化微服務架构，通過 RESTful API 與 WebSocket 通信。

#### 2.1 Tech Stack
| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Backend** | Python 3.10+, FastAPI, `uv` (Package Mgr) | 強大 AI/OCR生態，高性能 Web Server。 |
| **Frontend** | React (Vite), TypeScript, Tailwind CSS, shadcn/ui | 現代化 UI，極速開發體驗。 |
| **DB (Relational)** | SQLite (`sqlite3`) + SQLAlchemy/SQLModel | 輕量、零配置，完美支援相對路徑。分為 `library_core.db` (館藏) 與 `user_activity.db` (個人)。 |
| **DB (Vector)** | ChromaDB 或 LanceDB (Local Mode) | 支援本地運行，高效 Embedding。結構化存儲 UUID + Metadata. |
| **AI/LLM** | Ollama (Local), OpenAI/Claude API, Qwen-VL (OCR) | 靈活切換本地/雲端模型。Qwen/V-L 用於多模態 OCR。 |
| **Process Mgr** | `Overmind` / `Tauri` (Future) | 管理前後端進程，實現單一啟動入口。 |

#### 2.2 Directory Structure (Portable Design)
系統需支援將整個文件夾（含數據庫、PDF 源）移動到任何磁碟/電腦並正常運行。
```text
/project_root/                 <-- 移動的根目錄 (Root of Truth)
├── config.json                # [Config] 全局配置，LLM URL, API Keys
├── .library_fingerprint.json  # [Lock] Embedding Model Version & Dimension Lock
├── library_core.db            # [Core DB] 館藏數據 (書目、分類、路徑)
├── user_activity.db           # [Private DB] 個人進度、高亮 (與 Core隔離)
├── vector_store/              # [Vector Data] 本地向量庫文件 (ChromaDB/Lance)
├── assets/                    # [Cache] 縮圖、臨時文件 (assets/thumbnails/{uuid}.jpg)
├── books/                     # [Content] PDF/EPUB/TXT 源文件 (相對路徑引用)
├── backend/                   # [Source] Python Codebase
│   ├── main.py                # FastAPI Entry Point
│   ├── config_loader.py       # 讀取 JSON & Fingerprint Validator
│   └── ...                    # Core Logic (Ingestion, Search)
├── frontend/                  # [Source] React Codebase
│   ├── src/components         # UI Components (BookCard, GraphView)
│   └── ...                    # Pages & Hooks
├── .uv/                       # uv cache (可排除在移動範圍外，或重建)
└── Procfile                   # Overmind config for local dev/run
```

---

### 3. Data Model & Strategy (數據模型與策略)

#### 3.1 Dual-Database Separation
*   **Library Core (`library_core.db`)**:
    *   存儲：`id (UUID)`, `relative_path`, `title`, `author`, `genre_tree`, `created_at`.
    *   **不可變性**：除新增/更新元數據外，保持只讀。
*   **User Activity (`user_activity.db`)**:
    *   存儲：`book_id (FK)`, `progress_percent`, `highlights_json`, `last_read_at`.
    *   **隔離機制**：刪除或重裝此文件不會影響 `library_core.db`。提供「清除個人數據」按鈕，僅刪除本庫文件。

#### 3.2 Vector & Indexing Strategy
*   **Hybrid Search**: Combine `Keyword Match` (Tags) + `Semantic Similarity`.
*   **Embedding**: Use a single unified Vector Store.
    *   **Input**: Book Summary + Translated/Unified Tags (Multi-lingual support).
    *   **Model**: Configurable via `config.json` (e.g., `text-embedding-3-large`, `bge-m3`).
    *   **Fingerprint Lock**: On startup, compare current config vs `.library_fingerprint.json`. If mismatch -> **Block Search & Trigger Re-index**.
*   **Multi-lingual Handling**: No direct keyword translation. Rely on Embedding Model's cross-language capability + LLM-generated unified tags (e.g., generate both "Python" and "財金管理").

#### 3.3 Smart Content Extraction
*   **Pages**: Extract first ~10-20 pages (skip covers, TOC).
*   **OCR**: If page is image-only -> Trigger Qwen-VL / PaddleOCR.
*   **Metadata Generation**: LLM outputs JSON (`title`, `summary`, `tags`, `genre_path`).

---

### 4. Functional Modules (功能模組)

#### A. Ingestion Engine
*   **Smart Folder Sync**: Monitor `books/` (and configured watch folders). Auto-detect new files.
*   **Deduplication**: SimHash + Content Embedding check against existing DB. If match > 95% -> Reject/Log version conflict.
*   **Versioning**: If same book exists but newer, update metadata (optional: keep history).

#### B. Search & Retrieval
*   **Natural Language Query**: Convert query to Vector -> Similarity search in DB.
*   **Knowledge Graph**: Extract entities from summaries, build node-edge graph for visualization (e.g., "Python" connects to multiple books).
*   **Chapter-Level Bookmarking**: Save highlights with precise location (Page/Section ID) linked to `user_activity.db`.

#### C. AI Features
*   **Auto-Tagging**: LLM assigns hierarchical tags (e.g., `資訊 > 程式語言`).
*   **Cross-Book Linking**: Suggest related books based on shared entities/concepts.
*   **Text-to-Speech (TTS)**: Generate audio streams from chapters for "Listen" mode.
*   **Model Sandbox**: Allow testing new LLMs on a subset of data before full migration.

#### D. Admin & Safety
*   **Re-indexing**: UI trigger to re-process all books with a new Embedding model.
*   **Privacy Redaction**: Option to mask sensitive info (phone, ID) in summary generation.

---

### 5. UI/UX Design Specification (介面設計規格)

#### Layout Philosophy
*   **Style**: Modern, Clean (Notion/Apple Books hybrid). Sidebar navigation + Main Content Area.
*   **Stack**: React Router, Tailwind CSS, Recharts (Charts), ReactFlow (Graph).

#### Navigation Menu
1.  **🏠 Library Dashboard**: Home, Recommendations ("Because you read..."), Recent Reads (with progress bars), Global Search Bar.
2.  **🔍 Discover & Explore**: Semantic search, Knowledge Graph visualization (ReactFlow), Tag Cloud.
3.  **📂 Watch Folders**: List of monitored folders, auto-import logs, manual scan trigger.
4.  **🧠 Knowledge & Notes**: Personal highlights list, Cross-book referencing view (concept linking).
5.  **👤 Profile**: Reading stats, Achievements/Badges, **"Clear Personal Data"** (Critical: Deletes `user_activity.db` only).
6.  **⚙️ Settings**: LLM configuration (Embedding/Chat models), Model Sandbox, Storage paths.
7.  **🛠️ Developer/API**: Swagger UI for API docs, Debug logs (OCR errors).

#### Key Page Workflows
*   **Book Detail**: Three-column layout. Left: Cover (Click to play TTS). Center: Meta + AI Summary. Right/User Panel: Highlights, Progress slider, "Related Concepts".
*   **Reader Mode**: Embedded PDF/EPUB viewer (or system default) with overlay toolbar for highlighting and note-taking. Notes auto-sync to `user_activity.db`.

---

### 6. Deployment & Workflow (部署與工作流)

#### Development Mode
1.  **Backend**: `uv run uvicorn backend.main:app --reload` (Port 8000).
2.  **Frontend**: `npm run dev` (Port 5173, proxying `/api` to localhost:8000).
3.  **Orchestration**: Use `overmind start` to manage both processes simultaneously from root directory.

#### Production/Packaging
*   **Target**: macOS `.app` bundle via `Tauri`.
    *   Tauri bundles the React frontend and runs the Python backend as a subprocess.
*   **Portability**: The `.app` is just an entry point; the actual data lives in `project_root`. User can copy `project_root` to any USB drive.

---

### 7. Configuration Schema (`config.json`)
*Strictly defined JSON structure for AI/LLM configuration.*

```json
{
  "version": 1,
  "storage_paths": {
    "base_dir_relative_to_config": true,
    "pdf_roots": ["books", "../external_books"],
    "library_core_db_path": "./system_index.db",
    "user_activity_db_path": "./_private_user_data.db"
  },
  "llms": {
    "extraction_model": { ... }, 
    "embedding_model": { 
      "model_name": "text-embedding-3-large",
      "dimension": 1536, 
      ...
    },
    "chat_model": { ... }
  },
  "search_settings": {
    "top_k": 10,
    "max_pages_to_analyze": 20
  }
}
```

---

### 🚀 Next Step: Execution Prompt for AI Developer

**To generate the project code, use this prompt:**

> "Act as a Senior Full-Stack Architect. Initialize the 'Smart Personal PDF Library' project based on the attached Technical Specification (v1.0).
> 
> **Requirements:**
> 1.  Initialize a monorepo structure with `backend/` (Python/FastAPI + uv) and `frontend/` (React/Vite).
> 2.  Implement the **Dual-Database Strategy**: Create SQLAlchemy models for `library_core` and separate ones for `user_activity`. Ensure strict separation logic.
> 3.  Implement the **Fingerprint Validator**: A startup middleware that checks `.library_fingerprint.json` against `config.yaml`. If mismatch, return 409 and block search endpoints.
> 4.  Build the **Smart Ingestion Service**: Logic to extract first ~20 pages, handle OCR fallback, call LLM for metadata/summary/tags.
> 5.  Set up **ChromaDB** integration with UUID-based metadata mapping (no direct file paths in vector store).
> 6.  Create basic **React Frontend** scaffolding with `shadcn/ui`, including Sidebar navigation, Home Dashboard (mock data), and Settings page for LLM config.
> 7.  Include a `Procfile` or Makefile script to run both services via Overmind.
> 
> Please output the file structure and key code files (`models.py`, `ingestion_service.py`, `App.tsx` setup)."

---
**這份規格書已涵蓋所有您提出的需求、架構決策及 UI 細節。您可以直接複製此文件並指示 AI 開始執行。**
