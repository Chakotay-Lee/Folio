# Folio — Smart Personal Library `v0.2.0`

**Languages:** English | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

A self-hosted personal library system. Drop your PDF, EPUB, TXT, and Markdown files into a folder; Folio automatically extracts metadata with an LLM, builds a semantic search index, and gives you a clean browser UI to browse, search, and read your collection.

---

> [!WARNING]
> **Token Usage — Local LLM Strongly Recommended**
>
> Folio calls an LLM for **every book** it processes to extract metadata (title, author, summary, tags, and genre). On a large library this can consume a significant number of tokens. Using a commercial API such as OpenAI or Anthropic may result in unexpected costs.
> **Running a local model via [Ollama](https://ollama.ai) is strongly recommended.**
>
> **OCR requires a vision-capable (multimodal) model**
>
> The optional OCR feature sends page images to an LLM to extract text from scanned or image-only PDFs. This requires a model that supports **image input** — a text-only model will not work. Recommended options include [Qwen2-VL](https://ollama.ai/library/qwen2-vl), Gemma 3/4, LLaVA, or any other multimodal model available through your provider.

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
- **OCR support** — optional VLM-based OCR pass for scanned/image-only PDFs; uses the configured `analysis_model` (or `extraction_model`) to extract text from page images
- **Deep analysis** — manually trigger per-book AI pipeline: chapter detection, full-text extraction, figure extraction (native PDF via PyMuPDF; scanned PDF via VLM bounding box), per-figure descriptions, chapter summaries, and self-contained HTML export. Configure `llms.analysis_model` in `config.json` (defaults to `extraction_model`).
- **Book Chat** — RAG-based conversational Q&A with any analyzed book. Chapter **summaries** are sent as baseline context; full chapter text is fetched on demand via **tool calling**, keeping token usage low even for large books. Figures are referenced by ID and rendered inline. Persistent sessions stored locally.
- **TTS** — Generate audio from chapter summaries or full chapter text. Supports **OpenAI TTS API** (models: `tts-1`/`tts-1-hd`; voices: alloy, echo, fable, onyx, nova, shimmer) and **local binary** engines (Piper, Kokoro, or any stdin→stdout MP3 binary). Configure in Settings. Access via the book detail panel → **Analysis & TTS**.

---

## Deep Analysis & Book Chat

Folio can do more than index your books — it can **read and discuss them with you**.

After triggering a deep analysis on a book, Folio runs a full AI pipeline:

1. **Chapter detection** — identifies chapter boundaries across the whole PDF
2. **Text extraction** — extracts full text per chapter (VLM OCR for scanned pages)
3. **Figure extraction** — locates and crops embedded images; generates a description for each
4. **Chapter summaries** — produces a ≤300-word summary per chapter using the configured LLM
5. **HTML export** — bundles the summaries, figures, and metadata into a self-contained HTML file

Once analysis is complete, open **Book Chat** to have a conversation with the AI about the book. The AI receives chapter summaries as baseline context and fetches full chapter text on demand via tool calling — keeping token usage low while still being able to answer detailed questions. Extracted figures are displayed inline when referenced.

> **Recommended model for deep analysis:** A **multimodal (vision-capable)** model is required for figure extraction and OCR on scanned PDFs. Currently, **Qwen2-VL / Qwen3** (e.g. `qwen2-vl:7b` via Ollama) provides the best results for both figure detection and text accuracy.

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
│   │   └── ocr.py         # optional VLM OCR
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
| `llms.analysis_model` | VLM used for deep analysis (figure extraction, OCR, descriptions). Falls back to `extraction_model` if unset | — |
| `tts.provider` | TTS engine: `openai` or `local` | `"openai"` |
| `tts.model` | OpenAI TTS model (`tts-1` or `tts-1-hd`) | `"tts-1"` |
| `tts.voice` | OpenAI voice (`alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`) | `"alloy"` |
| `tts.api_key` | OpenAI API key for TTS | `""` |
| `tts.binary_path` | Path to local TTS binary (for `provider: local`) | `""` |
| `tts.chunk_size` | Max characters per TTS request | `4000` |
| `search_settings.top_k` | Number of semantic search results | `10` |
| `search_settings.max_pages_to_analyze` | Pages read during text extraction | `20` |
| `ocr.enabled` | Enable VLM-based OCR for image-only PDFs | `true` |
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
| PDF | PyMuPDF (+ optional VLM OCR) | First page render |
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
| `analysis/{book-uuid}/` | Per-book deep analysis: chapter text, summaries, extracted figures, audio cache, HTML export |

To move the data directory, set `storage_paths.*` in `config.json` to absolute paths.

---

## Re-indexing

If you change the embedding model, the existing vector index becomes incompatible. Go to **Settings → Re-index** (or `POST /api/reindex`) to rebuild it. The existing SQLite book records are preserved; only the ChromaDB index is rebuilt on next scan.

---

## Known Issues

| Issue | Detail |
|---|---|
| Figure extraction accuracy on scanned PDFs | Figure boundary detection on scanned pages relies on VLM bounding-box inference, which can misidentify regions or miss figures entirely. Native (text-layer) PDFs are more reliable. |
| Recommended model for figures | **Qwen2-VL / Qwen3** currently gives the highest figure detection accuracy among tested models. Other VLMs (LLaVA, Gemma) may produce more errors. |
| Large book token usage | Deep analysis processes every page sequentially. Very large books (500+ pages) may take significant time and tokens depending on the model and provider. |

---

## License

MIT
