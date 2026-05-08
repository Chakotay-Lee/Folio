# Folio — 智能个人书库 `v0.2.0`

**语言：** [English](README.md) | [繁體中文](README.zh-TW.md) | 简体中文 | [日本語](README.ja.md)

自托管个人书库系统。将 PDF、EPUB、TXT、Markdown 文件放入指定目录，Folio 即自动以 LLM 提取元数据、建立语义搜索索引，并提供简洁的浏览器界面供浏览、搜索与阅读。

---

> [!WARNING]
> **Token 用量警告 — 强烈建议使用本地 LLM**
>
> Folio 在处理**每一本书**时都会调用 LLM 来提取元数据（书名、作者、摘要、标签、分类）。书库较大时，累积的 Token 用量相当可观。若使用 OpenAI 或 Anthropic 等商业 API，费用可能迅速累积。
> **强烈建议通过 [Ollama](https://ollama.ai) 在本地运行模型，既免费又保护隐私。**
>
> **深度解析的 Token 消耗可能相当可观**
>
> 深度解析会逐页处理整本书。一本含图表的 300 页扫描书籍，使用云端模型时可能消耗 **50 万至 100 万以上 Token**。建议先用页码范围进行小范围测试，或使用 Quick 模式。详见[深度解析使用指南](docs/deep-analysis.zh-CN.md#token-消耗估算)。
>
> **OCR 功能需要支持视觉（多模态）的模型**
>
> 可选的 OCR 功能会将页面图片发送给 LLM，以识别纯图片或扫描版 PDF 中的文字。此功能需要支持**图片输入**的模型，纯文本模型无法使用。建议选择 [Qwen2-VL](https://ollama.ai/library/qwen2-vl)、Gemma 3/4、LLaVA 或其他支持多模态输入的模型。

---

## 功能特色

- **自动导入** — 监听指定目录，有新文件即自动处理
- **LLM 元数据提取** — 使用任意 OpenAI 兼容、Ollama 或 Anthropic 模型，自动生成书名、作者、摘要、标签、分类路径
- **语义搜索** — 通过 ChromaDB 向量搜索；依语义找书，不只靠关键字
- **重复检测** — SimHash 近似哈希过滤，防止重复建立索引
- **封面提取** — 从 PDF/EPUB 提取封面图片，无法提取时自动生成色块
- **浏览器阅读** — 内嵌 PDF 查看器与 EPUB 阅读器
- **书籍上传** — 直接从浏览器拖拽或选取文件上传
- **多语言界面** — 支持 English、繁體中文、简体中文、日本語
- **AI 输出语言** — 摘要、标签、分类可用任意支持的语言生成
- **OCR 支持** — 可选配 VLM 识别，将扫描版/纯图片 PDF 的页面图片送交 `analysis_model`（或 `extraction_model`）提取文字
- **深度解析** — 手动触发逐本 AI 分析流程，完成后解锁 HTML 导出、TTS 语音及完整内文 Book Chat。包含章节检测、全文提取、图形提取、图形描述、章节摘要及独立 HTML 导出。可选的输出语言设置，可让 AI 以指定语言生成章节摘要，作为个人**阅读辅助**用途，并非原著的翻译版本。 → [深度解析使用指南](docs/deep-analysis.zh-CN.md)
- **书籍对话** — 对已解析书籍进行 RAG 问答。以章节**摘要**作为基准上下文传送给 LLM；完整章节内文通过 **tool calling** 按需获取，即使书籍篇幅庞大也能维持低 token 用量。图形以 ID 引用并在对话中内嵌显示。对话记录本地持久化存储。
- **文字转语音** — 从章节摘要或完整章节内文生成音频。支持 **OpenAI TTS API**（模型：`tts-1`/`tts-1-hd`；语音：alloy、echo、fable、onyx、nova、shimmer）、**AIVIS**（VOICEVOX 兼容本地服务器）、**Gemini TTS**，以及**本地可执行文件**引擎（Piper、Kokoro 或任何支持 stdin→stdout MP3 的可执行文件）。可在设置页面配置。从书籍详细面板点选「分析结果与 TTS」进入。

---

## 深度解析与 Book Chat

Folio 不只是书籍索引工具，它还能**阅读书籍，并和你一起讨论内容**。

对一本书触发深度解析后，Folio 会执行完整的 AI 分析流程：

1. **章节检测** — 识别整份 PDF 的章节边界
2. **全文提取** — 逐章提取全文（扫描页面使用 VLM OCR）
3. **图表提取** — 定位并裁切内嵌图片，并为每张图生成文字描述
4. **章节摘要** — 使用配置的 LLM 为每章生成 ≤300 字摘要；可选的语言设置可输出指定语言的摘要，作为个人阅读辅助，并非对原著的复制或翻译
5. **HTML 导出** — 将摘要、图表与元数据打包成独立 HTML 文件，仅供个人参考使用

**额外提示词（extra prompt）** 字段让你自定义 AI 解读和摘要书籍的方式。以下是一些示例：

| 提示词 | 效果 |
|---|---|
| `"用小学生也能理解的方式解说每一章"` | 语言简化，适合快速掌握陌生领域 |
| `"每段结尾加「喵」，用猫咪的口吻解说"` | 趣味呈现，帮助记忆枯燥内容 |
| `"用一个生活中的比喻来说明每章的核心概念"` | 以类比加深理解 |
| `"每章给我 3 条重点，不要废话"` | 快速复习用的精炼摘要 |

这些输出为个人阅读辅助，请勿对外传播从受著作权保护作品衍生的 AI 生成内容。

分析完成后，打开 **Book Chat** 即可让 AI 陪你讨论这本书的内容。AI 以章节摘要作为基准上下文，并在需要时通过 tool calling 按需获取完整章节内文，在维持低 token 用量的同时，仍能回答具体细节问题。提取的图表会在对话中内嵌显示。

> **深度解析推荐模型：** 图表提取与扫描 PDF OCR 需要**多模态（支持视觉输入）**的模型。目前测试中，**Qwen2-VL / Qwen3**（例如通过 Ollama 使用 `qwen2-vl:7b`）在图表检测与文字识别准确度上表现最佳。

---

## 架构

```
Library/
├── backend/               # FastAPI + SQLModel + ChromaDB
│   ├── main.py            # API 路由、应用生命周期
│   ├── config_loader.py   # config.json → AppConfig 数据类
│   ├── ingestion/
│   │   ├── pipeline.py    # ingest_file()：提取 → 去重 → LLM → DB → 向量
│   │   ├── extractor.py   # 文字提取（PDF/EPUB/TXT/MD）
│   │   ├── cover.py       # 封面图片提取
│   │   ├── dedup.py       # SimHash 近似重复检查
│   │   └── ocr.py         # 可选 VLM OCR
│   ├── llm/
│   │   ├── prompts.py     # 多语言提取 prompt 生成器
│   │   ├── openai_provider.py
│   │   ├── ollama_provider.py
│   │   └── anthropic_provider.py
│   ├── db/
│   │   ├── core.py        # SQLite（书籍数据，通过 SQLModel）
│   │   └── activity.py    # 用户活动数据库
│   ├── vector_store.py    # ChromaDB 封装
│   └── watcher.py         # 文件系统监听（watchdog）
│
├── frontend/              # React 19 + Vite + Tailwind
│   └── src/
│       ├── pages/
│       │   ├── DashboardPage.tsx   # 书库总览 + 上传
│       │   ├── NotesPage.tsx       # 浏览 + 按分类/标签筛选
│       │   ├── DiscoverPage.tsx    # 语义搜索
│       │   ├── ProfilePage.tsx     # 统计数据
│       │   ├── FoldersPage.tsx     # 监控目录 + 扫描
│       │   └── SettingsPage.tsx    # LLM 配置 + 语言
│       ├── lib/
│       │   ├── i18n.ts             # 翻译字典
│       │   └── LangContext.tsx     # React Context + localStorage 同步
│       └── components/
│
├── config.json            # 运行时配置（已加入 .gitignore）
├── config.json.example    # 配置模板
└── Procfile               # foreman / overmind 启动命令
```

---

## 系统要求

- **Python 3.10+** 配合 [uv](https://github.com/astral-sh/uv)
- **Node.js 18+**
- 以下三选一：
  - [Ollama](https://ollama.ai) 在本地运行（免费、离线）
  - OpenAI API 密钥
  - Anthropic API 密钥

---

## 安装与配置

### 1. 复制并编辑配置文件

```bash
cp config.json.example config.json
```

编辑 `config.json`，设置 LLM 提供商与书库目录：

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

### 2. 安装后端依赖

```bash
cd backend
uv sync
```

### 3. 安装前端依赖

```bash
cd frontend
npm install
```

### 4. 启动服务

使用 [foreman](https://github.com/ddollar/foreman) 或 [overmind](https://github.com/DarthSim/overmind)：

```bash
foreman start
# 或
overmind start
```

或分别在两个终端手动启动：

```bash
# 终端 1 — 后端（端口 5201）
cd backend
uv run uvicorn backend.main:app --reload --port 5201

# 终端 2 — 前端（端口 5200）
cd frontend
npm run dev
```

在浏览器打开 **http://localhost:5200**。

---

## 配置参数说明

| 字段 | 说明 | 默认值 |
|---|---|---|
| `storage_paths.pdf_roots` | 要扫描书籍的目录 | `["books"]` |
| `storage_paths.watch_folders` | 监控新文件的目录（pdf_roots 的子集） | 同 pdf_roots |
| `llms.extraction_model` | 用于元数据提取的 LLM | — |
| `llms.embedding_model` | 用于语义嵌入的模型 | — |
| `llms.chat_model` | 用于对话功能的模型 | — |
| `llms.analysis_model` | 深度解析使用的 VLM（图形提取、OCR、图形描述）。未设置时沿用 `extraction_model` | — |
| `tts.provider` | TTS 引擎：`openai`、`aivis`、`gemini` 或 `local` | `"openai"` |
| `tts.model` | TTS 模型（`tts-1`、`tts-1-hd`、`gemini-2.5-flash-preview-tts` 等） | `"tts-1"` |
| `tts.voice` | 语音名称（OpenAI：`alloy`/`echo`/…；Gemini：`Aoede`/`Charon`/…） | `"alloy"` |
| `tts.api_key` | API 密钥（`openai` 和 `gemini` 提供商必填） | `""` |
| `tts.base_url` | AIVIS 服务器基础 URL（例：`http://localhost:10101`） | `""` |
| `tts.speaker_id` | AIVIS 说话者/风格 ID | `0` |
| `tts.binary_path` | 本地 TTS 可执行文件路径（`provider: local` 时使用） | `""` |
| `tts.chunk_size` | 每次 TTS 请求的最大字符数 | `4000` |
| `search_settings.top_k` | 语义搜索返回结果数 | `10` |
| `search_settings.max_pages_to_analyze` | 文字提取时读取的最大页数 | `20` |
| `ocr.enabled` | 启用 VLM OCR 处理图片 PDF | `true` |
| `ocr.min_chars_threshold` | 低于此字符数才触发 OCR | `50` |
| `default_open_mode` | 打开书籍方式：`system`、`browser`、`download` | `"system"` |
| `content_language` | AI 生成内容的语言：`en`、`zh-TW`、`zh-CN`、`ja` | `"en"` |

LLM 提供商字段（适用于 `extraction_model`、`embedding_model`、`chat_model`）：

| 字段 | 说明 |
|---|---|
| `provider` | `openai`、`ollama`、`anthropic` 或 `gemini` |
| `model_name` | 模型标识符 |
| `base_url` | API 基础 URL（Ollama 及自定义端点必填） |
| `api_key` | API 密钥（Ollama 可留空） |
| `temperature` | 采样温度 |
| `max_tokens` | 最大响应 token 数 |
| `dimension` | 嵌入向量维度（仅 embedding_model） |

---

## 支持格式

| 格式 | 文字提取 | 封面提取 |
|---|---|---|
| PDF | PyMuPDF（+ 可选 VLM OCR） | 第一页渲染 |
| EPUB | ebooklib | 从 manifest 提取封面图片 |
| TXT | 直接读取 | — |
| Markdown | 直接读取 | — |

---

## API 概览

所有端点均在 `/api` 路径下。

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/books` | 分页书籍列表，支持筛选（`page`、`limit`、`genre`、`tag`、`q`） |
| `GET` | `/books/stats` | 汇总数字：书籍数、容量、分类数、标签数、格式分布 |
| `GET` | `/books/tags` | 所有标签及出现次数 |
| `GET` | `/books/genres` | 所有分类路径及出现次数 |
| `POST` | `/books/upload` | 上传书籍文件（multipart） |
| `GET` | `/books/{id}` | 单本书籍详细信息 |
| `PUT` | `/books/{id}` | 更新书籍元数据 |
| `DELETE` | `/books/{id}` | 移除书籍（可选同时删除实体文件） |
| `GET` | `/books/{id}/cover` | 封面图片 |
| `GET` | `/books/{id}/file` | 书籍文件（`?mode=inline` 或 `?mode=download`） |
| `POST` | `/books/{id}/open` | 在系统应用中打开（仅限本地） |
| `POST` | `/books/{id}/reclassify` | 对单本书重新执行 LLM 提取 |
| `POST` | `/books/reclassify-all` | 对所有书重新执行 LLM 提取 |
| `GET` | `/search/semantic` | 向量搜索（`?q=查询字符串`） |
| `GET` | `/folders` | 监控目录状态 |
| `POST` | `/folders/scan` | 触发扫描所有监控目录 |
| `POST` | `/folders/scan-path` | 扫描指定的一次性目录 |
| `GET` | `/ingestion/logs` | 最近导入记录（最后 100 条） |
| `GET` | `/config` | 读取当前 config.json |
| `PUT` | `/config` | 深度合并更新 config.json 并重新加载 |

---

## 数据存储位置

默认情况下，所有持久化数据存放于 `config.json` 旁边：

| 路径 | 内容 |
|---|---|
| `library_core.db` | SQLite — 书籍记录 |
| `user_activity.db` | SQLite — 用户活动 |
| `vector_store/` | ChromaDB — 嵌入索引 |
| `assets/` | 提取的封面图片 |
| `analysis/{book-uuid}/` | 每本书的深度解析数据：章节文字、摘要、提取图形、音频缓存、HTML 导出 |

若要更改数据目录，请在 `config.json` 的 `storage_paths.*` 中设置绝对路径。

---

## 重建索引

更换嵌入模型后，现有向量索引将与新模型不兼容。请至 **Settings → Re-index**（或 `POST /api/reindex`）重建。SQLite 的书籍记录会保留；仅 ChromaDB 索引在下次扫描时重建。

---

## 已知问题

| 问题 | 说明 |
|---|---|
| 扫描 PDF 图表提取准确度 | 扫描页面的图表边界检测依赖 VLM 边界框推断，可能发生区域误判或图表遗漏。原生 PDF（含文字层）的准确度较高。 |
| 图表提取推荐模型 | 目前测试中，**Qwen2-VL / Qwen3** 在图表检测准确度上优于其他模型（如 LLaVA、Gemma）。 |
| 大型书籍 token 用量 | 深度解析会依序处理每一页，书籍页数较多（500页以上）时，依模型与供应商不同，所需时间与 token 消耗可能相当可观。 |

---

## 法律声明

> **本声明不构成法律建议。如有具体法律疑虑，请咨询合格律师。**

**仅供个人使用。** Folio 是一款自托管个人书库管理工具，设计用途为管理用户依法拥有的书籍与文件，不得用于复制、再分发或商业利用他人受著作权保护的作品。

**内容合法性责任由用户自负。** 用户须自行确认对加入 Folio 的任何文件拥有合法的存储、索引与处理权利。本项目作者不支持、也不鼓励将本工具用于未经授权获取的资料。

**第三方服务隐私声明。** 使用云端 LLM 提供商（OpenAI、Anthropic、Google Gemini 等）时，书籍的文字内容（包含提取的段落与摘要）将传送至该提供商的服务器进行处理。使用前请详阅各提供商的隐私政策与服务条款。如需完全在本地处理数据，请通过 [Ollama](https://ollama.ai) 使用本地模型。

**翻译与演绎作品。** 语言输出选项所生成的是 AI 对书籍内容的摘要解读，以指定语言呈现，目的是辅助用户理解其合法持有的著作，并非对原文的完整复制或翻译。依多数著作权法制，翻译权属著作权人专有（如《伯尔尼公约》第 8 条）。用户不得利用本功能制作、传播或发布受著作权保护作品的翻译版本或其他演绎作品，除非已获得著作权人的授权。

**无担保声明。** 本软件依现状提供，不附任何形式的担保。详见下方 [MIT 许可证](#许可证) 条款。

---

## 许可证

MIT
