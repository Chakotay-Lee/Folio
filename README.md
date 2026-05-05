# Folio — Smart Personal Library

**Languages:** English | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

A self-hosted personal library system. Drop your PDF, EPUB, TXT, and Markdown files into a folder; Folio automatically extracts metadata with an LLM, builds a semantic search index, and gives you a clean browser UI to browse, search, and read your collection.

---

## Features

- **Auto-ingestion** — watches configured folders and processes new files automatically
- **LLM metadata extraction** — generates title, author, summary, tags, and genre path using any OpenAI-compatible, Ollama, or Anthropic model
- **Semantic search** — vector search via ChromaDB; find books by meaning, not just keywords
- **Duplicate detection** — SimHash near-duplicate filtering prevents double indexing
- **Cover extraction** — extracts cover image from PDF/EPUB, falls back to generated color
- **Browser reader** — inline PDF viewer and built-in EPUB reader
- **Book upload** — drag-and-drop or file picker to add books from the browser
- **i18n UI** — interface language switchable between English, 繁體中文, 简体中文, 日本語
- **AI output language** — summary, tags, and genre can be generated in any supported language
- **OCR support** — optional PaddleOCR pass for scanned/image-only PDFs

---

## Architecture

```
Library/
├── backend/               # FastAPI + SQLModel + ChromaDB
│   ├── main.py            # API routes, app lifespan
│   ├── config_loader.py   # config.json → AppConfig dataclass
│   ├── ingestion/
│   │   ├── pipeline.py    # ingest_file(): extract → dedup → LLM → DB → vector
│   │   ├── extractor.py   # text extraction (PDF/EPUB/TXT/MD)
│   │   ├── cover.py       # cover image extraction
│   │   ├── dedup.py       # SimHash near-duplicate check
│   │   └── ocr.py         # optional PaddleOCR
│   ├── llm/
│   │   ├── prompts.py     # multilingual extraction prompt builder
│   │   ├── openai_provider.py
│   │   ├── ollama_provider.py
│   │   └── anthropic_provider.py
│   ├── db/
│   │   ├── core.py        # SQLite via SQLModel (books)
│   │   └── activity.py    # user activity DB
│   ├── vector_store.py    # ChromaDB wrapper
│   └── watcher.py         # filesystem watcher (watchdog)
│
├── frontend/              # React 19 + Vite + Tailwind
│   └── src/
│       ├── pages/
│       │   ├── DashboardPage.tsx   # library overview + upload
│       │   ├── NotesPage.tsx       # browse + filter by genre/tag
│       │   ├── DiscoverPage.tsx    # semantic search
│       │   ├── ProfilePage.tsx     # stats
│       │   ├── FoldersPage.tsx     # watch folders + scan
│       │   └── SettingsPage.tsx    # LLM config + language
│       ├── lib/
│       │   ├── i18n.ts             # translation dictionaries
│       │   └── LangContext.tsx     # React context + localStorage sync
│       └── components/
│
├── config.json            # runtime configuration (gitignored)
├── config.json.example    # template
└── Procfile               # foreman / overmind start commands
```

---

## Requirements

- **Python 3.10+** with [uv](https://github.com/astral-sh/uv)
- **Node.js 18+**
- One of:
  - [Ollama](https://ollama.ai) running locally (free, private)
  - OpenAI API key
  - Anthropic API key

---

## Setup

### 1. Clone and configure

```bash
cp config.json.example config.json
```

Edit `config.json` to point to your LLM provider and set your book folder:

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

### 2. Install backend dependencies

```bash
cd backend
uv sync
```

Optional OCR support:

```bash
uv sync --extra ocr
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install
```

### 4. Start both servers

Using [foreman](https://github.com/ddollar/foreman) or [overmind](https://github.com/DarthSim/overmind):

```bash
foreman start
# or
overmind start
```

Or start manually in separate terminals:

```bash
# Terminal 1 — backend (port 5201)
cd backend
uv run uvicorn backend.main:app --reload --port 5201

# Terminal 2 — frontend (port 5200)
cd frontend
npm run dev
```

Open **http://localhost:5200** in your browser.

---

## Configuration reference

| Field | Description | Default |
|---|---|---|
| `storage_paths.pdf_roots` | Folders to scan for books | `["books"]` |
| `storage_paths.watch_folders` | Folders watched for new files (subset of pdf_roots) | same as pdf_roots |
| `llms.extraction_model` | LLM used for metadata extraction | — |
| `llms.embedding_model` | Model used for semantic embeddings | — |
| `llms.chat_model` | Model used for chat features | — |
| `search_settings.top_k` | Number of semantic search results | `10` |
| `search_settings.max_pages_to_analyze` | Pages read during text extraction | `20` |
| `ocr.enabled` | Enable PaddleOCR for image-only PDFs | `true` |
| `ocr.min_chars_threshold` | Character count below which OCR is triggered | `50` |
| `default_open_mode` | How books open: `system`, `browser`, `download` | `"system"` |
| `content_language` | Language for AI-generated content: `en`, `zh-TW`, `zh-CN`, `ja` | `"en"` |

LLM provider fields (for each of `extraction_model`, `embedding_model`, `chat_model`):

| Field | Description |
|---|---|
| `provider` | `openai`, `ollama`, or `anthropic` |
| `model_name` | Model identifier |
| `base_url` | API base URL (required for Ollama and custom OpenAI endpoints) |
| `api_key` | API key (leave empty for Ollama) |
| `temperature` | Sampling temperature |
| `max_tokens` | Maximum response tokens |
| `dimension` | Embedding vector dimension (embedding model only) |

---

## Supported file formats

| Format | Text extraction | Cover extraction |
|---|---|---|
| PDF | PyMuPDF (+ optional OCR) | First page render |
| EPUB | ebooklib | Cover image from manifest |
| TXT | Direct read | — |
| Markdown | Direct read | — |

---

## API overview

All endpoints are under `/api`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/books` | Paginated book list with filter (`page`, `limit`, `genre`, `tag`, `q`) |
| `GET` | `/books/stats` | Aggregated counts: books, bytes, genres, tags, format breakdown |
| `GET` | `/books/tags` | All tags with occurrence count |
| `GET` | `/books/genres` | All genre paths with occurrence count |
| `POST` | `/books/upload` | Upload a book file (multipart) |
| `GET` | `/books/{id}` | Single book detail |
| `PUT` | `/books/{id}` | Update book metadata |
| `DELETE` | `/books/{id}` | Remove book (optionally delete file) |
| `GET` | `/books/{id}/cover` | Cover image |
| `GET` | `/books/{id}/file` | Book file (`?mode=inline` or `?mode=download`) |
| `POST` | `/books/{id}/open` | Open book in system app (localhost only) |
| `POST` | `/books/{id}/reclassify` | Re-run LLM extraction on a single book |
| `POST` | `/books/reclassify-all` | Re-run LLM extraction on all books |
| `GET` | `/search/semantic` | Vector search (`?q=query`) |
| `GET` | `/folders` | Watch folder status |
| `POST` | `/folders/scan` | Trigger scan of all watch folders |
| `POST` | `/folders/scan-path` | Scan a one-off directory path |
| `GET` | `/ingestion/logs` | Recent ingestion log (last 100 entries) |
| `GET` | `/config` | Read current config.json |
| `PUT` | `/config` | Deep-merge patch into config.json and reload |

---

## Data storage

All persistent data lives alongside `config.json` by default:

| Path | Contents |
|---|---|
| `library_core.db` | SQLite — book records |
| `user_activity.db` | SQLite — reading activity |
| `vector_store/` | ChromaDB — embedding index |
| `assets/` | Extracted cover images |

To move the data directory, set `storage_paths.*` in `config.json` to absolute paths.

---

## Re-indexing

If you change the embedding model, the existing vector index becomes incompatible. Go to **Settings → Re-index** (or `POST /api/reindex`) to rebuild it. The existing SQLite book records are preserved; only the ChromaDB index is rebuilt on next scan.

---

## License

MIT
