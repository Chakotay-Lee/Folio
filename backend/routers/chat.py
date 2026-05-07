"""Book Chat API — RAG-based conversational Q&A with a single analyzed book."""
from __future__ import annotations
import json
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/books/{book_uuid}/chat")


def _require_analyzed_book(book_uuid: str, request: Request):
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select

    cfg = request.app.state.config
    with get_core_session() as session:
        book = session.exec(select(Book).where(Book.id == book_uuid)).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if book.analysis_status != "done":
        raise HTTPException(
            status_code=400,
            detail="Book analysis must be complete before chatting",
        )
    return book, cfg


def _chat_dir(cfg, book_uuid: str) -> Path:
    d = cfg.analysis_dir / book_uuid / "chat"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("")
def list_sessions(book_uuid: str, request: Request):
    """List all chat sessions for a book."""
    book, cfg = _require_analyzed_book(book_uuid, request)
    chat_dir = _chat_dir(cfg, book_uuid)

    sessions = []
    for f in sorted(chat_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            raw_messages = data.get("messages", [])
            sessions.append({
                "session_id": f.stem,
                "title": data.get("title", "Untitled"),
                "message_count": len(raw_messages),
                "updated_at": data.get("updated_at", ""),
                "messages": [
                    {"role": m["role"], "content": m["content"]}
                    for m in raw_messages
                ],
            })
        except Exception:
            continue

    return sessions


@router.post("")
def create_session(book_uuid: str, request: Request):
    """Create a new chat session."""
    book, cfg = _require_analyzed_book(book_uuid, request)
    chat_dir = _chat_dir(cfg, book_uuid)

    session_id = str(_uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "session_id": session_id,
        "book_uuid": book_uuid,
        "title": "New Chat",
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }
    (chat_dir / f"{session_id}.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    return {"session_id": session_id}



@router.post("/{session_id}/message")
async def send_message(book_uuid: str, session_id: str, request: Request):
    """Send a user message and stream the LLM response via SSE."""
    from backend.analysis.chat_context import assemble_context, build_image_list
    from backend.llm.factory import get_provider

    book, cfg = _require_analyzed_book(book_uuid, request)
    chat_dir = _chat_dir(cfg, book_uuid)
    session_file = chat_dir / f"{session_id}.json"
    if not session_file.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    body = await request.json()
    user_content = body.get("content", "").strip()
    if not user_content:
        raise HTTPException(status_code=422, detail="content is required")

    session_data = json.loads(session_file.read_text(encoding="utf-8"))
    messages = session_data.get("messages", [])

    # Set session title from first user message
    if not messages:
        session_data["title"] = user_content[:60]

    analysis_dir = cfg.analysis_dir / book_uuid
    book_context = assemble_context(analysis_dir)
    figure_list = build_image_list(analysis_dir)

    if figure_list:
        figure_instruction = (
            "When you want to display a figure, write exactly [img_NNN] using only IDs from the "
            "Available Figures list below. Never invent an img ID that is not in that list.\n\n"
            f"{figure_list}"
        )
    else:
        figure_instruction = "This book has no extracted figures available for display."

    system_prompt = (
        "You are a helpful assistant for the book. Answer questions based on the provided content. "
        "Chapter summaries are provided below. Use the get_chapter_content tool when you need the "
        "full text of a specific chapter to answer in detail.\n"
        f"{figure_instruction}\n\n"
        f"{book_context}"
    )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_chapter_content",
                "description": "Get the full text of a book chapter for detailed analysis.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chapter_index": {
                            "type": "integer",
                            "description": "Chapter number (0-based index, matching chapter order)",
                        }
                    },
                    "required": ["chapter_index"],
                },
            },
        }
    ]

    provider = get_provider(cfg.llms.chat_model)
    chat_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
    chat_messages.append({"role": "user", "content": user_content})

    def stream_response():
        import httpx
        from backend.analysis.chat_context import get_chapter_content as _get_chapter

        url = provider.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"

        full_response = []
        loop_messages = [{"role": "system", "content": system_prompt}] + chat_messages

        try:
            while True:
                payload = {
                    "model": provider.model_name,
                    "messages": loop_messages,
                    "max_tokens": provider.max_tokens,
                    "temperature": provider.temperature,
                    "stream": True,
                    "tools": tools,
                    "tool_choice": "auto",
                }
                if hasattr(provider, "extra_body") and provider.extra_body:
                    payload.update(provider.extra_body)

                content_chunks: list[str] = []
                # tool_calls: index → {id, name, arguments_buf}
                tool_calls_buf: dict[int, dict] = {}
                finish_reason = None

                with httpx.stream("POST", url, json=payload, headers=headers,
                                  timeout=provider.timeout_seconds) as resp:
                    for line in resp.iter_lines():
                        if not line or line == "data: [DONE]":
                            continue
                        if not line.startswith("data: "):
                            continue
                        try:
                            chunk = json.loads(line[6:])
                        except Exception:
                            continue
                        choice = chunk.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        finish_reason = choice.get("finish_reason") or finish_reason

                        # Stream content
                        text = delta.get("content") or ""
                        if text:
                            content_chunks.append(text)
                            full_response.append(text)
                            yield f"data: {json.dumps({'content': text})}\n\n"

                        # Accumulate tool call deltas
                        for tc in delta.get("tool_calls") or []:
                            idx = tc.get("index", 0)
                            if idx not in tool_calls_buf:
                                tool_calls_buf[idx] = {"id": "", "name": "", "arguments": ""}
                            if tc.get("id"):
                                tool_calls_buf[idx]["id"] += tc["id"]
                            fn = tc.get("function", {})
                            if fn.get("name"):
                                tool_calls_buf[idx]["name"] += fn["name"]
                            if fn.get("arguments"):
                                tool_calls_buf[idx]["arguments"] += fn["arguments"]

                if finish_reason != "tool_calls" or not tool_calls_buf:
                    break

                # Add assistant message with tool_calls
                assistant_msg: dict = {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in tool_calls_buf.values()
                    ],
                }
                if content_chunks:
                    assistant_msg["content"] = "".join(content_chunks)
                loop_messages.append(assistant_msg)

                # Execute each tool call
                for tc in tool_calls_buf.values():
                    if tc["name"] != "get_chapter_content":
                        result = f"Unknown tool: {tc['name']}"
                    else:
                        try:
                            args = json.loads(tc["arguments"])
                            ch_idx = int(args.get("chapter_index", 0))
                            yield f"data: {json.dumps({'status': 'reading', 'chapter': ch_idx})}\n\n"
                            result = _get_chapter(analysis_dir, ch_idx)
                        except Exception as e:
                            result = f"Error fetching chapter: {e}"

                    loop_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
            return

        yield "data: [DONE]\n\n"

        # Persist messages
        assistant_content = "".join(full_response)
        now = datetime.now(timezone.utc).isoformat()
        messages.append({"role": "user", "content": user_content, "timestamp": now})
        messages.append({"role": "assistant", "content": assistant_content, "timestamp": now})
        session_data["messages"] = messages
        session_data["updated_at"] = now
        session_file.write_text(json.dumps(session_data, ensure_ascii=False), encoding="utf-8")

    return StreamingResponse(stream_response(), media_type="text/event-stream")


@router.delete("/{session_id}")
def delete_session(book_uuid: str, session_id: str, request: Request):
    """Delete a chat session."""
    book, cfg = _require_analyzed_book(book_uuid, request)
    session_file = _chat_dir(cfg, book_uuid) / f"{session_id}.json"
    if not session_file.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    session_file.unlink()
    return Response(status_code=204)
