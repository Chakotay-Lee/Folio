from pathlib import Path
from typing import Optional
import chromadb
from chromadb import Collection
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings


class OpenAICompatEmbeddingFunction(EmbeddingFunction):
    """Calls an OpenAI-compatible /v1/embeddings endpoint."""

    def __init__(self, model: str, api_key: str, base_url: str, dimension: int):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._dimension = dimension

    def __call__(self, input: Documents) -> Embeddings:
        response = self._client.embeddings.create(model=self._model, input=list(input))
        return [item.embedding for item in response.data]


_client: Optional[chromadb.ClientAPI] = None
_collection: Optional[Collection] = None
COLLECTION_NAME = "folio_books"


def init_vector_store(store_path: Path, embedding_model: str, api_key: str,
                      base_url: str, dimension: int) -> None:
    global _client, _collection
    store_path.mkdir(parents=True, exist_ok=True)
    _client = chromadb.PersistentClient(path=str(store_path))

    ef = OpenAICompatEmbeddingFunction(
        model=embedding_model,
        api_key=api_key,
        base_url=base_url,
        dimension=dimension,
    )
    _collection = _client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def _get_collection() -> Collection:
    if _collection is None:
        raise RuntimeError("Vector store not initialised — call init_vector_store() first")
    return _collection


def upsert_document(uuid: str, summary: str, tags: list[str], metadata: dict) -> None:
    content = summary + " " + " ".join(tags)
    safe_meta = {k: v for k, v in metadata.items() if isinstance(v, (str, int, float, bool))}
    _get_collection().upsert(ids=[uuid], documents=[content], metadatas=[safe_meta])


def search(query: str, top_k: int = 10) -> list[tuple[str, float]]:
    results = _get_collection().query(query_texts=[query], n_results=top_k)
    ids = results["ids"][0]
    distances = results["distances"][0]
    return list(zip(ids, distances))


def delete_document(uuid: str) -> None:
    _get_collection().delete(ids=[uuid])


def update_metadata(uuid: str, metadata: dict) -> None:
    _get_collection().update(ids=[uuid], metadatas=[metadata])


def get_client() -> chromadb.ClientAPI:
    if _client is None:
        raise RuntimeError("Vector store not initialised")
    return _client
