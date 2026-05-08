# Deep Analysis Guide

Deep analysis is an optional AI pipeline that unlocks several advanced features for a book. Until you run it, features like HTML export, TTS audio, and full-context Book Chat are not available.

---

## Features unlocked by deep analysis

| Feature | Where to find it after analysis |
|---|---|
| **Chapter summaries** | Analysis page → chapter list |
| **Extracted figures** | Embedded in chapter summaries |
| **HTML export** | Analysis page → Export HTML button |
| **TTS audio** | Analysis page → each chapter → play button |
| **Full-context Book Chat** | Book detail panel → Chat button |

---

## How to trigger deep analysis

1. Open any book in your library
2. Click **Analyze** (sparkle icon) in the book detail panel
3. A confirmation dialog appears — you can adjust options before starting
4. Click **Deep Analysis** to begin

The analysis runs in the background. You can navigate away and return — the progress indicator will continue updating.

---

## Analysis options

### Output language
Leave blank to match the book's original language. Enter a language name (e.g. `English`, `繁體中文`, `日本語`) to have summaries and descriptions generated in that language.

> These are AI-produced reading aids, not translations of the original work. See the [Legal Notice](../README.md#legal-notice) for details.

### Extra prompt
Customise how the AI reads and summarises each chapter. Examples:

| Prompt | Effect |
|---|---|
| `"Explain each chapter as if I were a primary school student"` | Simplified language, great for unfamiliar subjects |
| `"End every paragraph with 'meow' and narrate in a cat's voice"` | Playful retelling — useful for making dense content memorable |
| `"Illustrate each chapter's core idea with one real-world analogy"` | Conceptual understanding through comparison |
| `"Give me 3 bullet-point takeaways per chapter, no filler"` | Rapid, structured review |

### Page range
Analyse only a portion of the book. Useful for:
- Testing settings before committing to a full run
- Analysing only the chapters you care about

### Mode
| Mode | What it does |
|---|---|
| **Full** | Complete pipeline: OCR, figure extraction, summaries, HTML export |
| **Quick** | Summaries only — skips figure extraction; much faster and cheaper |

---

## Token cost

Deep analysis is significantly more expensive than regular ingestion. Rough estimates per book:

| Stage | Approximate token use |
|---|---|
| OCR (scanned pages) | ~1,000–3,000 per page (includes image tokens) |
| Chapter summary | ~2,000–5,000 per chapter |
| Figure description | ~500–1,500 per figure |

A 300-page scanned book with 10 chapters and 30 figures can consume **500,000–1,000,000+ tokens** when using a cloud model.

**Recommendations:**
- Use **Quick mode** first to check results before running Full
- Use a **local model via [Ollama](https://ollama.ai)** to avoid cloud API costs entirely
- Use the **page range** option to test on a small section first

---

## Re-analysis

You can re-run deep analysis on a book at any time. A warning will appear to confirm, as existing results (summaries, audio cache, HTML) will be overwritten.

---

## Recommended models

A **vision-capable (multimodal)** model is required for figure extraction and OCR on scanned PDFs.

| Use case | Recommended |
|---|---|
| Best overall | **Qwen2-VL / Qwen3** via Ollama |
| Cloud, cost-conscious | Gemini 2.5 Flash |
| Text-only PDFs (no figures) | Any capable text model |

---

## Output files

All analysis data is stored in `analysis/{book-uuid}/` alongside your library data:

| Path | Contents |
|---|---|
| `text/ch_NN.txt` | Full extracted text per chapter |
| `text/ch_NN_summary.txt` | Chapter summary (used for TTS and Book Chat) |
| `figures/` | Extracted figure images |
| `audio/` | Cached TTS audio files |
| `book.html` | Self-contained HTML export |
