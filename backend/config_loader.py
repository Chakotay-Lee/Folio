import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class StoragePaths:
    books_root: Path             # portable library root (~/Documents/Books)
    library_core_db: Path
    user_activity_db: Path
    vector_store: Path
    assets: Path
    pdf_roots: list[Path]       # all indexed folders (scan target)
    watch_folders: list[Path]   # auto-import on new file (subset of pdf_roots)


@dataclass
class LLMModelConfig:
    provider: str
    model_name: str
    temperature: float = 0.1
    max_tokens: int = 1024
    timeout_seconds: int = 60
    base_url: str = ""
    api_key: str = ""
    dimension: int = 0
    extra_body: dict = field(default_factory=dict)


@dataclass
class LLMConfig:
    extraction_model: LLMModelConfig
    embedding_model: LLMModelConfig
    chat_model: LLMModelConfig
    ocr_model: LLMModelConfig | None = None
    analysis_model: LLMModelConfig | None = None  # VLM for figure detection; falls back to extraction_model


@dataclass
class SearchSettings:
    top_k: int = 10
    max_pages_to_analyze: int = 20


@dataclass
class TTSConfig:
    provider: str = "openai"          # "openai" | "local"
    model: str = "tts-1"
    voice: str = "alloy"
    api_key: str = ""
    binary_path: str = ""             # path to local TTS binary (Kokoro/Piper)
    chunk_size: int = 4000            # max chars per TTS request


@dataclass
class OCRConfig:
    enabled: bool = True
    min_chars_threshold: int = 50


@dataclass
class AppConfig:
    base_dir: Path
    storage: StoragePaths
    llms: LLMConfig
    search: SearchSettings
    ocr: OCRConfig
    tts: TTSConfig = field(default_factory=TTSConfig)
    analysis_dir: Path = field(default=None)  # type: ignore[assignment]
    default_open_mode: str = "system"  # "system" | "browser" | "download"
    content_language: str = "en"  # "en" | "zh-TW" | "zh-CN" | "ja"


_REQUIRED_KEYS = {"version", "storage_paths", "llms", "search_settings", "ocr"}
_REQUIRED_LLM_MODELS = {"extraction_model", "embedding_model", "chat_model"}
_REQUIRED_STORAGE_KEYS = {
    "library_core_db_path",
    "user_activity_db_path",
    "vector_store_path",
    "assets_path",
}


def _validate(raw: dict) -> None:
    missing = _REQUIRED_KEYS - raw.keys()
    if missing:
        raise ValueError(f"config.json missing required keys: {missing}")

    llms = raw["llms"]
    missing_models = _REQUIRED_LLM_MODELS - llms.keys()
    if missing_models:
        raise ValueError(f"config.json llms missing: {missing_models}")

    storage = raw["storage_paths"]
    missing_storage = _REQUIRED_STORAGE_KEYS - storage.keys()
    if missing_storage:
        raise ValueError(f"config.json storage_paths missing: {missing_storage}")

    emb = llms.get("embedding_model", {})
    if "dimension" in emb and not isinstance(emb["dimension"], int):
        raise ValueError("config.json llms.embedding_model.dimension must be an integer")


def _parse_llm_model(raw: dict) -> LLMModelConfig:
    return LLMModelConfig(
        provider=raw["provider"],
        model_name=raw["model_name"],
        temperature=raw.get("temperature", 0.1),
        max_tokens=raw.get("max_tokens", 1024),
        timeout_seconds=raw.get("timeout_seconds", 60),
        base_url=raw.get("base_url", ""),
        api_key=raw.get("api_key", ""),
        dimension=raw.get("dimension", 0),
        extra_body=raw.get("extra_body", {}),
    )


def load_config(config_path: str | Path = "./config.json") -> AppConfig:
    config_path = Path(config_path).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"config.json not found at: {config_path}")

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    _validate(raw)

    base_dir = config_path.parent
    s = raw["storage_paths"]

    def resolve(p: str) -> Path:
        expanded = Path(p).expanduser()
        if expanded.is_absolute():
            return expanded.resolve()
        return (base_dir / expanded).resolve()

    books_root_raw = s.get("books_root")
    books_root = resolve(books_root_raw) if books_root_raw else base_dir

    def resolve_storage(key: str, default_rel: str) -> Path:
        if key in s:
            return resolve(s[key])
        return (books_root / ".folio" / default_rel).resolve()

    storage = StoragePaths(
        books_root=books_root,
        library_core_db=resolve_storage("library_core_db_path", "library_core.db"),
        user_activity_db=resolve_storage("user_activity_db_path", "user_activity.db"),
        vector_store=resolve_storage("vector_store_path", "vector_store"),
        assets=resolve_storage("assets_path", "assets"),
        pdf_roots=[resolve(r) for r in s.get("pdf_roots", [str(books_root)])],
        watch_folders=[resolve(r) for r in s.get("watch_folders", s.get("pdf_roots", [str(books_root)]))],
    )

    llm_raw = raw["llms"]
    llms = LLMConfig(
        extraction_model=_parse_llm_model(llm_raw["extraction_model"]),
        embedding_model=_parse_llm_model(llm_raw["embedding_model"]),
        chat_model=_parse_llm_model(llm_raw["chat_model"]),
        ocr_model=_parse_llm_model(llm_raw["ocr_model"]) if "ocr_model" in llm_raw else None,
        analysis_model=_parse_llm_model(llm_raw["analysis_model"]) if "analysis_model" in llm_raw else None,
    )

    ss = raw["search_settings"]
    search = SearchSettings(
        top_k=ss.get("top_k", 10),
        max_pages_to_analyze=ss.get("max_pages_to_analyze", 20),
    )

    ocr_raw = raw.get("ocr", {})
    ocr = OCRConfig(
        enabled=ocr_raw.get("enabled", True),
        min_chars_threshold=ocr_raw.get("min_chars_threshold", 50),
    )

    tts_raw = raw.get("tts", {})
    tts = TTSConfig(
        provider=tts_raw.get("provider", "openai"),
        model=tts_raw.get("model", "tts-1"),
        voice=tts_raw.get("voice", "alloy"),
        api_key=tts_raw.get("api_key", ""),
        binary_path=tts_raw.get("binary_path", ""),
        chunk_size=tts_raw.get("chunk_size", 4000),
    )

    analysis_dir_raw = raw.get("analysis_dir")
    analysis_dir = resolve(analysis_dir_raw) if analysis_dir_raw else books_root / ".folio" / "analysis"

    default_open_mode = raw.get("default_open_mode", "system")
    content_language = raw.get("content_language", "en")

    return AppConfig(base_dir=base_dir, storage=storage, llms=llms, search=search, ocr=ocr,
                     tts=tts, analysis_dir=analysis_dir,
                     default_open_mode=default_open_mode, content_language=content_language)
