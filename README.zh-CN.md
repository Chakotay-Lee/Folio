# Folio — 智能个人书库

**语言：** [English](README.md) | [繁體中文](README.zh-TW.md) | 简体中文 | [日本語](README.ja.md)

自托管个人书库系统。将 PDF、EPUB、TXT、Markdown 文件放入指定目录，Folio 即自动以 LLM 提取元数据、建立语义搜索索引，并提供简洁的浏览器界面供浏览、搜索与阅读。

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
- **OCR 支持** — 可选配 PaddleOCR，处理纯图片扫描 PDF

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
│   │   └── ocr.py         # 可选 PaddleOCR
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

可选 OCR 支持：

```bash
uv sync --extra ocr
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
| `search_settings.top_k` | 语义搜索返回结果数 | `10` |
| `search_settings.max_pages_to_analyze` | 文字提取时读取的最大页数 | `20` |
| `ocr.enabled` | 启用 PaddleOCR 处理图片 PDF | `true` |
| `ocr.min_chars_threshold` | 低于此字符数才触发 OCR | `50` |
| `default_open_mode` | 打开书籍方式：`system`、`browser`、`download` | `"system"` |
| `content_language` | AI 生成内容的语言：`en`、`zh-TW`、`zh-CN`、`ja` | `"en"` |

LLM 提供商字段（适用于 `extraction_model`、`embedding_model`、`chat_model`）：

| 字段 | 说明 |
|---|---|
| `provider` | `openai`、`ollama` 或 `anthropic` |
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
| PDF | PyMuPDF（+ 可选 OCR） | 第一页渲染 |
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

若要更改数据目录，请在 `config.json` 的 `storage_paths.*` 中设置绝对路径。

---

## 重建索引

更换嵌入模型后，现有向量索引将与新模型不兼容。请至 **Settings → Re-index**（或 `POST /api/reindex`）重建。SQLite 的书籍记录会保留；仅 ChromaDB 索引在下次扫描时重建。

---

## 许可证

MIT
