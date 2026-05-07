import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Clock, BookOpen, ChevronRight, Library, HardDrive, Layers, Tag, Upload } from 'lucide-react'
import { api } from '@/lib/api'
import { parseTags } from '@/lib/bookUtils'
import { BookCover } from '@/components/BookCover'
import { BookDetailModal } from '@/components/BookDetailModal'
import { Pagination } from '@/components/Pagination'
import { useLang } from '@/lib/LangContext'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(i >= 2 ? 1 : 0)} ${units[i]}`
}

type Book = {
  id: string; title: string; author: string | null
  genre_path: string | null; tags_json: string | null
  file_format: string; created_at: string
  summary: string | null
  analysis_status?: string
}
type Stats = {
  total_books: number; total_bytes: number; genre_count: number; tag_count: number
  formats: Record<string, number>
}
type Log = { uuid: string; title: string; status: string; created_at: string; file_format?: string }
type BooksPage = { items: Book[]; total: number; page: number; pages: number }

export function DashboardPage() {
  const { t } = useLang()
  const [stats, setStats] = useState<Stats | null>(null)
  const [books, setBooks] = useState<Book[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [page, setPage] = useState(1)
  const [recentBooks, setRecentBooks] = useState<Book[]>([])
  const [query, setQuery] = useState('')
  const [config, setConfig] = useState<{ default_open_mode?: string }>({})
  const [detailBook, setDetailBook] = useState<Book | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.get<Stats>('/books/stats').then(setStats).catch(() => {})
    api.get<{ default_open_mode?: string }>('/config').then(setConfig).catch(() => {})
  }, [refreshKey])

  // Fetch paginated all-books grid
  useEffect(() => {
    api.get<BooksPage>(`/books?page=${page}&limit=24`)
      .then(data => { setBooks(data.items); setTotal(data.total); setTotalPages(data.pages) })
      .catch(() => {})
  }, [page, refreshKey])

  // Fetch recently added via enriched logs
  useEffect(() => {
    api.get<Log[]>('/ingestion/logs').then(logs => {
      const recent = logs.filter(l => l.status === 'success').slice(0, 6)
      Promise.all(
        recent.map(l => api.get<Book>(`/books/${l.uuid}`).catch(() => null))
      ).then(bs => setRecentBooks(bs.filter(Boolean) as Book[]))
    }).catch(() => {})
  }, [refreshKey])

  const defaultOpenMode = (config.default_open_mode as 'system' | 'browser' | 'download') || 'system'

  const removeBook = (id: string) => {
    setBooks(bs => bs.filter(b => b.id !== id))
    setRecentBooks(bs => bs.filter(b => b.id !== id))
    setRefreshKey(k => k + 1)
  }
  const updateBook = (updated: { id: string }) => {
    setBooks(bs => bs.map(b => b.id === updated.id ? { ...b, ...updated } : b))
    setRecentBooks(bs => bs.map(b => b.id === updated.id ? { ...b, ...updated } : b))
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) navigate(`/discover?q=${encodeURIComponent(query)}`)
  }

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true)
    setUploadMsg(null)
    let success = 0; let fail = 0
    for (const file of Array.from(files)) {
      try {
        await api.upload('/books/upload', file)
        success++
      } catch (e: unknown) {
        fail++
        console.error('Upload failed:', e)
      }
    }
    setUploading(false)
    setUploadMsg(
      fail === 0
        ? (t('dash.uploadQueued') as (n: number) => string)(success)
        : (t('dash.uploadPartial') as (s: number, f: number) => string)(success, fail)
    )
    setTimeout(() => setUploadMsg(null), 5000)
  }

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">{t('dash.title') as string}</h2>
          <p className="text-slate-500 text-sm mt-0.5">
            {stats && stats.total_books > 0 ? t('dash.subtitle') as string : t('dash.empty') as string}
          </p>
        </div>
        <div className="flex gap-2 flex-wrap justify-end items-center">
          {stats && Object.entries(stats.formats).sort((a, b) => b[1] - a[1]).map(([fmt, count]) => (
            <span key={fmt}
              className="px-2.5 py-1 bg-slate-100 rounded-lg text-xs font-semibold text-slate-500 uppercase tracking-wide">
              {fmt} {count}
            </span>
          ))}
          {/* Upload button */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.epub,.txt,.md"
            className="hidden"
            onChange={e => handleUpload(e.target.files)}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-400 hover:bg-amber-500 disabled:opacity-50 text-slate-900 text-xs font-semibold rounded-lg transition-colors">
            <Upload className="w-3.5 h-3.5" />
            {uploading ? t('dash.uploading') as string : t('dash.upload') as string}
          </button>
        </div>
      </div>

      {uploadMsg && (
        <div className="px-4 py-2.5 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-700">
          {uploadMsg}
        </div>
      )}

      {/* Library stats */}
      {stats && stats.total_books > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm px-4 py-3 flex items-center gap-3">
            <div className="w-8 h-8 bg-amber-400/15 rounded-xl flex items-center justify-center shrink-0">
              <Library className="w-4 h-4 text-amber-600" />
            </div>
            <div>
              <p className="text-xl font-bold text-slate-800 leading-none">{stats.total_books}</p>
              <p className="text-xs text-slate-400 mt-0.5">{t('dash.books') as string}</p>
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm px-4 py-3 flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-400/15 rounded-xl flex items-center justify-center shrink-0">
              <HardDrive className="w-4 h-4 text-blue-500" />
            </div>
            <div>
              <p className="text-xl font-bold text-slate-800 leading-none">{formatBytes(stats.total_bytes)}</p>
              <p className="text-xs text-slate-400 mt-0.5">{t('dash.size') as string}</p>
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm px-4 py-3 flex items-center gap-3">
            <div className="w-8 h-8 bg-emerald-400/15 rounded-xl flex items-center justify-center shrink-0">
              <Layers className="w-4 h-4 text-emerald-500" />
            </div>
            <div>
              <p className="text-xl font-bold text-slate-800 leading-none">{stats.genre_count}</p>
              <p className="text-xs text-slate-400 mt-0.5">{t('dash.genres') as string}</p>
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm px-4 py-3 flex items-center gap-3">
            <div className="w-8 h-8 bg-violet-400/15 rounded-xl flex items-center justify-center shrink-0">
              <Tag className="w-4 h-4 text-violet-500" />
            </div>
            <div>
              <p className="text-xl font-bold text-slate-800 leading-none">{stats.tag_count}</p>
              <p className="text-xs text-slate-400 mt-0.5">{t('dash.tags') as string}</p>
            </div>
          </div>
        </div>
      )}

      {/* Search bar */}
      <form onSubmit={handleSearch}>
        <div className="relative group">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-amber-500 transition-colors" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={t('dash.searchPlaceholder') as string}
            className="w-full pl-11 pr-32 py-3.5 bg-white border border-slate-200 rounded-xl text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-amber-400/40 focus:border-amber-400 transition-all"
          />
          <button type="submit" disabled={!query.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-2 bg-amber-400 hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-semibold text-slate-900 transition-colors">
            Search
          </button>
        </div>
      </form>

      {/* Recently added */}
      {recentBooks.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-slate-400" /> {t('dash.recent') as string}
            </h3>
            <button onClick={() => navigate('/notes')}
              className="text-xs text-amber-600 hover:text-amber-700 flex items-center gap-0.5 transition-colors">
              {t('dash.viewAll') as string} <ChevronRight className="w-3 h-3" />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {recentBooks.map(book => (
              <div key={book.id} className="flex items-center gap-3 px-4 py-3 bg-white rounded-xl border border-slate-100 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => setDetailBook(book)}>
                <BookCover book={book} className="w-8 h-10 rounded-md shrink-0"
                  defaultOpenMode={defaultOpenMode}
                  onRemoved={removeBook} onUpdated={updateBook} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">{book.title}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{new Date(book.created_at).toLocaleDateString()}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {detailBook && (
        <BookDetailModal
          book={detailBook}
          defaultOpenMode={defaultOpenMode}
          onClose={() => setDetailBook(null)}
          onRemoved={id => { removeBook(id); setDetailBook(null) }}
          onUpdated={updated => { updateBook(updated as Book); setDetailBook(updated as Book) }}
        />
      )}

      {/* All books grid */}
      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-700">{t('dash.allBooks') as string}</h3>
        {total === 0 ? (
          <div className="text-center py-20 text-slate-400">
            <BookOpen className="w-10 h-10 mx-auto mb-3 opacity-20" />
            <p className="text-sm font-medium">{t('dash.libEmpty') as string}</p>
            <p className="text-xs mt-1">{t('dash.libEmptyHint') as string}</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
              {books.map(book => {
                const tags = parseTags(book.tags_json)
                const genre = book.genre_path?.split(' > ').pop()
                return (
                  <div key={book.id}
                    className="group bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden hover:shadow-md hover:-translate-y-0.5 transition-all cursor-pointer">
                    <BookCover book={book} className="h-20 w-full"
                      defaultOpenMode={defaultOpenMode}
                      onRemoved={removeBook} onUpdated={updateBook}>
                      <div className="absolute bottom-1.5 right-1.5 text-white/90 text-xs font-mono uppercase bg-black/30 rounded px-1">{book.file_format}</div>
                    </BookCover>
                    <div className="p-2.5" onClick={() => setDetailBook(book)}>
                      <p className="text-xs font-semibold text-slate-800 line-clamp-2 leading-tight">{book.title}</p>
                      {book.author && <p className="text-xs text-slate-400 mt-0.5 truncate">{book.author}</p>}
                      {genre && <p className="text-xs text-amber-600 mt-1 truncate font-medium">{genre}</p>}
                      {tags.length > 0 && (
                        <div className="flex flex-wrap gap-0.5 mt-1.5">
                          {tags.slice(0, 2).map(tag => (
                            <span key={tag} className="px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded text-xs">{tag}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
            <Pagination page={page} totalPages={totalPages} total={total} onPage={setPage} />
          </>
        )}
      </section>
    </div>
  )
}
