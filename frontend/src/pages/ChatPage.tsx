import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Send, Loader2, Trash2, Plus, ArrowLeft, Check, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { api } from '@/lib/api'
import { useLang } from '@/lib/LangContext'

type Session = { session_id: string; title: string; message_count: number; updated_at: string; messages?: Message[] }
type Message = { role: 'user' | 'assistant'; content: string }

function renderContent(content: string, bookId: string) {
  // Match [img_001], [img_001: page 5, "desc"], [img_1], etc.
  const parts = content.split(/(\[img_\d+[^\]]*\])/g)
  return parts.map((part, i) => {
    const m = part.match(/^\[img_(\d+)/)
    if (m) {
      const imgId = `img_${m[1].padStart(3, '0')}`
      const imgSrc = `/api/books/${bookId}/analysis/images/${imgId}.png`
      return (
        <span key={i} className="inline-block my-1">
          <img
            src={imgSrc}
            alt={imgId}
            className="max-w-xs max-h-48 rounded-lg border border-slate-200 cursor-pointer hover:opacity-90"
            onClick={() => window.open(imgSrc, '_blank')}
          />
        </span>
      )
    }
    return (
      <div key={i} className="prose prose-sm prose-slate max-w-none
          prose-p:my-1 prose-p:leading-relaxed
          prose-headings:font-semibold prose-headings:mt-3 prose-headings:mb-1
          prose-ul:my-1 prose-ul:pl-4 prose-ol:my-1 prose-ol:pl-4
          prose-li:my-0
          prose-code:bg-slate-100 prose-code:px-1 prose-code:rounded prose-code:text-xs prose-code:font-mono
          prose-pre:bg-slate-100 prose-pre:rounded-xl prose-pre:p-3 prose-pre:text-xs prose-pre:overflow-x-auto
          prose-blockquote:border-l-2 prose-blockquote:border-amber-300 prose-blockquote:pl-3 prose-blockquote:text-slate-500
          prose-strong:font-semibold prose-strong:text-slate-800
          prose-a:text-amber-600 prose-a:underline
          prose-hr:border-slate-200">
        <ReactMarkdown>{part}</ReactMarkdown>
      </div>
    )
  })
}

export function ChatPage() {
  const { uuid, sessionId: paramSessionId } = useParams<{ uuid: string; sessionId?: string }>()
  const navigate = useNavigate()
  const { t } = useLang()

  const [sessions, setSessions] = useState<Session[]>([])
  const [activeSession, setActiveSession] = useState<string | null>(paramSessionId ?? null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [pendingDelete, setPendingDelete] = useState<string | null>(null)
  const [streaming, setStreaming] = useState(false)
  const [readingChapter, setReadingChapter] = useState<number | null>(null)
  const [bookTitle, setBookTitle] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!uuid) return
    api.get<{ title: string }>(`/books/${uuid}`).then(b => setBookTitle(b.title)).catch(() => {})
    loadSessions()
  }, [uuid])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadSessions = async () => {
    if (!uuid) return
    const list = await api.get<Session[]>(`/books/${uuid}/chat`)
    setSessions(list)
    const target = activeSession
      ? list.find(s => s.session_id === activeSession)
      : list[0]
    if (target) {
      setActiveSession(target.session_id)
      setMessages(target.messages ?? [])
    }
  }

  const loadSessionMessages = (sid: string) => {
    const session = sessions.find(s => s.session_id === sid)
    setMessages(session?.messages ?? [])
  }

  const createSession = async () => {
    if (!uuid) return
    const { session_id } = await api.post<{ session_id: string }>(`/books/${uuid}/chat`, {})
    setSessions(prev => [{ session_id, title: 'New Chat', message_count: 0, updated_at: '' }, ...prev])
    setActiveSession(session_id)
    setMessages([])
    navigate(`/books/${uuid}/chat/${session_id}`, { replace: true })
  }

  const deleteSession = async (sid: string) => {
    if (!uuid) return
    await api.delete(`/books/${uuid}/chat/${sid}`)
    setSessions(prev => prev.filter(s => s.session_id !== sid))
    if (activeSession === sid) {
      setActiveSession(null)
      setMessages([])
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || !activeSession || !uuid || streaming) return
    const content = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content }])
    setStreaming(true)

    const assistantMsg: Message = { role: 'assistant', content: '' }
    setMessages(prev => [...prev, assistantMsg])

    try {
      const resp = await fetch(`/api/books/${uuid}/chat/${activeSession}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      })

      const reader = resp.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        setStreaming(false)
        return
      }

      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const payload = line.slice(6)
            if (payload === '[DONE]') continue
            try {
              const parsed = JSON.parse(payload)
              if (parsed.status === 'reading') {
                setReadingChapter(parsed.chapter)
              } else if (parsed.content) {
                setReadingChapter(null)
                setMessages(prev => {
                  const updated = [...prev]
                  updated[updated.length - 1] = {
                    ...updated[updated.length - 1],
                    content: updated[updated.length - 1].content + parsed.content,
                  }
                  return updated
                })
              }
            } catch { /* ignore */ }
          }
        }
      }
    } catch {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { ...updated[updated.length - 1], content: t('chat.errorResponse') as string }
        return updated
      })
    } finally {
      setStreaming(false)
      setReadingChapter(null)
      loadSessions()
    }
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Sidebar */}
      <div className="w-56 shrink-0 border-r border-slate-100 flex flex-col bg-slate-50">
        <div className="p-3 border-b border-slate-100 flex items-center gap-2">
          <button onClick={() => navigate(-1)} className="p-1 rounded text-slate-400 hover:text-slate-600">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <p className="text-xs font-semibold text-slate-600 flex-1 truncate">{bookTitle}</p>
        </div>
        <div className="p-2">
          <button
            onClick={createSession}
            className="w-full flex items-center gap-1.5 px-2 py-1.5 text-xs text-violet-700 hover:bg-violet-50 rounded-lg transition-colors">
            <Plus className="w-3.5 h-3.5" />
            {t('chat.newChat') as string}
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {sessions.length === 0 && (
            <p className="text-xs text-slate-400 text-center py-4">{t('chat.noSessions') as string}</p>
          )}
          {sessions.map(s => (
            <div
              key={s.session_id}
              className={`group flex items-center gap-1 px-2 py-1.5 rounded-lg cursor-pointer text-xs transition-colors ${
                activeSession === s.session_id ? 'bg-white shadow-sm text-slate-800' : 'text-slate-600 hover:bg-white/70'
              }`}
              onClick={() => { if (pendingDelete !== s.session_id) { setActiveSession(s.session_id); loadSessionMessages(s.session_id) } }}>
              <span className="flex-1 truncate">{s.title}</span>
              {pendingDelete === s.session_id ? (
                <span className="flex items-center gap-0.5 shrink-0">
                  <button
                    onClick={e => { e.stopPropagation(); deleteSession(s.session_id); setPendingDelete(null) }}
                    className="p-0.5 text-red-500 hover:text-red-700 rounded">
                    <Check className="w-3 h-3" />
                  </button>
                  <button
                    onClick={e => { e.stopPropagation(); setPendingDelete(null) }}
                    className="p-0.5 text-slate-400 hover:text-slate-600 rounded">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ) : (
                <button
                  onClick={e => { e.stopPropagation(); setPendingDelete(s.session_id) }}
                  className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-400 hover:text-red-500 transition-opacity">
                  <Trash2 className="w-3 h-3" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Chat panel */}
      <div className="flex-1 flex flex-col min-w-0">
        {!activeSession ? (
          <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
            <div className="text-center">
              <p className="mb-3">{t('chat.noSessions') as string}</p>
              <button
                onClick={createSession}
                className="px-4 py-2 bg-violet-600 text-white text-sm rounded-xl hover:bg-violet-700 transition-colors">
                {t('chat.newChat') as string}
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-lg px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-violet-600 text-white rounded-br-sm'
                      : 'bg-white border border-slate-100 text-slate-700 rounded-bl-sm shadow-sm'
                  }`}>
                    {msg.role === 'assistant' && uuid
                      ? renderContent(msg.content, uuid)
                      : msg.content}
                    {msg.role === 'assistant' && streaming && i === messages.length - 1 && (
                      <span className="inline-block w-1.5 h-4 bg-slate-400 animate-pulse ml-0.5 align-middle" />
                    )}
                  </div>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>

            {/* Reading indicator */}
            {readingChapter !== null && (
              <div className="px-6 py-1 flex items-center gap-2 text-xs text-slate-400">
                <Loader2 className="w-3 h-3 animate-spin" />
                {(t('chat.readingChapter') as string).replace('{chapter}', String(readingChapter))}
              </div>
            )}

            {/* Input */}
            <div className="border-t border-slate-100 p-3 flex gap-2">
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                placeholder={t('chat.placeholder') as string}
                disabled={streaming}
                className="flex-1 px-3 py-2 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-violet-200 disabled:opacity-50"
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || streaming}
                className="px-3 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-xl transition-colors disabled:opacity-40">
                {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
