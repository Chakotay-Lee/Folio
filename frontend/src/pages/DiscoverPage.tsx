import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, Sparkles, BookOpen } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api, ApiError } from '@/lib/api'
import { parseTags, tagColor } from '@/lib/bookUtils'
import { BookCover } from '@/components/BookCover'
import { BookDetailModal } from '@/components/BookDetailModal'
import { useLang } from '@/lib/LangContext'

type Book = {
  id: string; title: string; author: string | null
  genre_path: string | null; tags_json: string | null
  file_format: string; summary: string | null
}
type SearchResult = Book & { score: number }

const QUICK_SEARCHES = ['Python', 'Machine Learning', '投資理財', '設計', 'Data Science', 'JavaScript', '管理', '哲學']

export function DiscoverPage() {
  const { t } = useLang()
  const [searchParams, setSearchParams] = useSearchParams()
  const [totalBooks, setTotalBooks] = useState(0)
  const [results, setResults] = useState<SearchResult[] | null>(null)
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [detailBook, setDetailBook] = useState<SearchResult | null>(null)

  useEffect(() => {
    api.get<{ total: number }>('/books?page=1&limit=1')
      .then(data => setTotalBooks(data.total))
      .catch(() => {})

    const q = searchParams.get('q')
    if (q) {
      setQuery(q)
      performSearch(q)
    }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  const performSearch = async (q: string) => {
    if (!q.trim()) { setResults(null); return }
    setLoading(true)
    setError(null)
    try {
      const data = await api.get<{ results: SearchResult[] }>(`/search/semantic?q=${encodeURIComponent(q)}`)
      setResults(data.results)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError('Search index is stale. Go to Settings → Re-index to rebuild.')
      } else {
        setError('Search failed. Make sure the backend is running.')
      }
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setSearchParams({ q: query })
    performSearch(query)
  }

  const quickSearch = (s: string) => {
    setQuery(s)
    setSearchParams({ q: s })
    performSearch(s)
  }

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-amber-500" />
          {t('disc.title') as string}
        </h2>
        <p className="text-slate-500 text-sm mt-0.5">
          {(t('disc.subtitle') as (n: number) => string)(totalBooks)}
        </p>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="relative group">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4.5 h-4.5 text-slate-400 group-focus-within:text-amber-500 transition-colors" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={t('disc.placeholder') as string}
            className="w-full pl-11 pr-28 py-4 bg-white border border-slate-200 rounded-2xl text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-amber-400/40 focus:border-amber-400 transition-all"
          />
          <button type="submit" disabled={loading || !query.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 px-5 py-2.5 bg-amber-400 hover:bg-amber-500 disabled:opacity-40 rounded-xl text-sm font-semibold text-slate-900 transition-colors">
            {loading ? '…' : t('disc.search') as string}
          </button>
        </div>
      </form>

      {error && (
        <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600">
          {error}
        </div>
      )}

      {results === null && !loading && (
        <div className="text-center py-8">
          <BookOpen className="w-12 h-12 mx-auto mb-3 text-amber-400 opacity-40" />
          <p className="text-slate-500 text-sm font-medium">{t('disc.emptyTitle') as string}</p>
          <p className="text-slate-400 text-xs mt-1">{t('disc.emptySubtitle') as string}</p>
          <div className="flex flex-wrap justify-center gap-2 mt-5">
            {QUICK_SEARCHES.map(s => (
              <button key={s} onClick={() => quickSearch(s)}
                className="px-3 py-1.5 bg-white border border-slate-200 rounded-full text-xs text-slate-600 hover:border-amber-400 hover:text-amber-700 hover:bg-amber-50 transition-colors shadow-sm">
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {results !== null && (
        <div className="space-y-4">
          <p className="text-sm text-slate-500">
            {loading
              ? t('disc.searching') as string
              : (t('disc.results') as (n: number, q: string) => string)(results.length, searchParams.get('q') || '')}
          </p>

          {results.length === 0 && !loading && (
            <div className="text-center py-12 text-slate-400">
              <p className="text-sm">{t('disc.noResults') as string}</p>
            </div>
          )}

          {results.map(book => {
            const tags = parseTags(book.tags_json)
            const score = Math.round(book.score * 100)
            return (
              <div key={book.id} className="flex gap-4 bg-white rounded-2xl border border-slate-100 shadow-sm p-4 hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => setDetailBook(book)}>
                <BookCover book={book} className="w-12 h-16 rounded-xl shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-semibold text-slate-800">{book.title}</p>
                    <span className={cn(
                      'shrink-0 px-2 py-0.5 rounded-full text-xs font-bold border',
                      score >= 70 ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                      score >= 50 ? 'bg-amber-50 text-amber-700 border-amber-200' :
                      'bg-slate-50 text-slate-600 border-slate-200'
                    )}>
                      {score}%
                    </span>
                  </div>
                  {book.author && <p className="text-xs text-slate-400 mt-0.5">{book.author}</p>}
                  {book.genre_path && (
                    <p className="text-xs text-amber-600 mt-1 font-medium">{book.genre_path}</p>
                  )}
                  {book.summary && (
                    <p className="text-sm text-slate-500 mt-2 line-clamp-2">{book.summary}</p>
                  )}
                  {tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {tags.slice(0, 6).map(tag => (
                        <span key={tag} className={cn('px-2 py-0.5 rounded-full text-xs border', tagColor(tag))}>
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
      {detailBook && (
        <BookDetailModal
          book={detailBook}
          onClose={() => setDetailBook(null)}
          onUpdated={updated => {
            setResults(rs => rs ? rs.map(r => r.id === updated.id ? { ...r, ...updated } : r) : rs)
            setDetailBook(prev => prev ? { ...prev, ...updated } : null)
          }}
          onRemoved={id => {
            setResults(rs => rs ? rs.filter(r => r.id !== id) : rs)
            setDetailBook(null)
          }}
        />
      )}
    </div>
  )
}
