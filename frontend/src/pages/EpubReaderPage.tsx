import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight, ArrowLeft, Minus, Plus } from 'lucide-react'
import { api } from '@/lib/api'
import Epub, { Book, Rendition } from 'epubjs'

type BookMeta = { id: string; title: string; author: string | null }

export function EpubReaderPage() {
  const { uuid } = useParams<{ uuid: string }>()
  const navigate = useNavigate()
  const viewerRef = useRef<HTMLDivElement>(null)
  const bookRef = useRef<Book | null>(null)
  const renditionRef = useRef<Rendition | null>(null)

  const [meta, setMeta] = useState<BookMeta | null>(null)
  const [fontSize, setFontSize] = useState(100)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!uuid || !viewerRef.current) return

    api.get<BookMeta>(`/books/${uuid}`).then(setMeta).catch(() => {})

    const book = Epub(`/api/books/${uuid}/file?mode=inline`, { openAs: 'epub' })
    bookRef.current = book

    const rendition = book.renderTo(viewerRef.current, {
      width: '100%',
      height: '100%',
      flow: 'paginated',
      spread: 'none',
    })
    renditionRef.current = rendition

    rendition.display().then(() => setLoading(false)).catch(() => {
      setError('Failed to load EPUB file')
      setLoading(false)
    })

    book.ready.catch(() => {
      setError('Failed to parse EPUB structure')
      setLoading(false)
    })

    const keyHandler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') rendition.next()
      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') rendition.prev()
    }
    window.addEventListener('keydown', keyHandler)

    return () => {
      window.removeEventListener('keydown', keyHandler)
      book.destroy()
    }
  }, [uuid])

  const changeFontSize = (delta: number) => {
    const next = Math.min(200, Math.max(60, fontSize + delta))
    setFontSize(next)
    renditionRef.current?.themes.fontSize(`${next}%`)
  }

  return (
    <div className="flex flex-col h-screen bg-[#f5f0e8]">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-2 bg-white border-b border-slate-200 shrink-0">
        <button
          onClick={() => navigate(-1)}
          className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors text-slate-500">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-800 truncate">{meta?.title ?? 'Loading…'}</p>
          {meta?.author && <p className="text-xs text-slate-400 truncate">{meta.author}</p>}
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => changeFontSize(-10)}
            className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors text-slate-500">
            <Minus className="w-3.5 h-3.5" />
          </button>
          <span className="text-xs text-slate-400 w-10 text-center">{fontSize}%</span>
          <button onClick={() => changeFontSize(10)}
            className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors text-slate-500">
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Reader area */}
      <div className="flex-1 flex items-stretch overflow-hidden">
        <button
          onClick={() => renditionRef.current?.prev()}
          className="w-12 shrink-0 flex items-center justify-center hover:bg-black/5 transition-colors text-slate-400">
          <ChevronLeft className="w-6 h-6" />
        </button>

        <div className="flex-1 relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center text-slate-400 text-sm">
              Loading…
            </div>
          )}
          {error && (
            <div className="absolute inset-0 flex items-center justify-center text-red-500 text-sm">
              {error}
            </div>
          )}
          <div ref={viewerRef} className="w-full h-full" />
        </div>

        <button
          onClick={() => renditionRef.current?.next()}
          className="w-12 shrink-0 flex items-center justify-center hover:bg-black/5 transition-colors text-slate-400">
          <ChevronRight className="w-6 h-6" />
        </button>
      </div>
    </div>
  )
}
