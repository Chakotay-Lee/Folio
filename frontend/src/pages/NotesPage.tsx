import { useEffect, useState, useMemo, useCallback } from 'react'
import { BookOpen, ChevronDown, CheckCircle2, AlertTriangle, Loader2, Info } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { parseTags, tagColor } from '@/lib/bookUtils'
import { BookCover } from '@/components/BookCover'
import { GenreTreeNode } from '@/components/GenreTreeNode'
import { GenreExpandModal } from '@/components/GenreExpandModal'
import { BookDetailModal, type DetailBook } from '@/components/BookDetailModal'
import { Pagination } from '@/components/Pagination'
import { buildGenreTree } from '@/lib/genreTree'
import { useLang } from '@/lib/LangContext'

type Book = {
  id: string; title: string; author: string | null
  genre_path: string | null; tags_json: string | null
  file_format: string; summary: string | null; created_at: string
  analysis_status?: string
}
type BooksPage = { items: Book[]; total: number; page: number; pages: number }
type TagEntry = { tag: string; count: number }
type GenreEntry = { genre_path: string; count: number }

export function NotesPage() {
  const { t } = useLang()
  const [books, setBooks] = useState<Book[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [page, setPage] = useState(1)

  const [allTags, setAllTags] = useState<TagEntry[]>([])
  const [genreData, setGenreData] = useState<GenreEntry[]>([])
  const [config, setConfig] = useState<{ default_open_mode?: string }>({})

  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const [selectedGenrePath, setSelectedGenrePath] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)

  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [detailBook, setDetailBook] = useState<DetailBook | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [expandingGenre, setExpandingGenre] = useState<string | null>(null)

  // Load sidebar data + config once
  useEffect(() => {
    api.get<TagEntry[]>('/books/tags').then(setAllTags).catch(() => {})
    api.get<GenreEntry[]>('/books/genres').then(setGenreData).catch(() => {})
    api.get<{ default_open_mode?: string }>('/config').then(setConfig).catch(() => {})
  }, [])

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput)
      setPage(1)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchInput])

  // Fetch current page whenever filters or page change
  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), limit: '24' })
    if (selectedGenrePath) params.set('genre', selectedGenrePath)
    if (selectedTag) params.set('tag', selectedTag)
    if (search.trim()) params.set('q', search.trim())

    setLoading(true)
    api.get<BooksPage>(`/books?${params}`)
      .then(data => {
        setBooks(data.items)
        setTotal(data.total)
        setTotalPages(data.pages)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [page, selectedGenrePath, selectedTag, search, refreshKey])

  const defaultOpenMode = (config.default_open_mode as 'system' | 'browser' | 'download') || 'system'

  const genreTree = useMemo(() => buildGenreTree(genreData), [genreData])

  const clearFilters = () => {
    setSelectedTag(null)
    setSelectedGenrePath(null)
    setSearchInput('')
    setSearch('')
    setPage(1)
  }
  const hasFilter = selectedTag || selectedGenrePath || search

  const handleGenreSelect = useCallback((fullPath: string) => {
    setSelectedGenrePath(p => p === fullPath ? null : fullPath)
    setSelectedTag(null)
    setPage(1)
  }, [])

  const removeBook = (id: string) => {
    setBooks(bs => bs.filter(b => b.id !== id))
    setTotal(t => t - 1)
    setRefreshKey(k => k + 1)
  }
  const updateBook = (updated: { id: string }) => {
    setBooks(bs => bs.map(b => b.id === updated.id ? { ...b, ...updated } : b))
    api.get<GenreEntry[]>('/books/genres').then(setGenreData).catch(() => {})
  }

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-56 shrink-0 border-r border-slate-200 bg-white overflow-y-auto">
        <div className="p-4 space-y-5">
          {/* Genre tree */}
          <div className="space-y-1">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">{t('browse.genre') as string}</p>
            <button
              onClick={() => { setSelectedGenrePath(null); setSelectedTag(null); setPage(1) }}
              className={cn('w-full text-left px-2.5 py-1.5 rounded-lg text-sm transition-colors',
                !selectedGenrePath ? 'bg-amber-400/10 text-amber-700 font-medium' : 'text-slate-500 hover:bg-slate-100'
              )}>
              {(t('browse.all') as (n: number) => string)(total)}
            </button>
            {genreTree.map(node => (
              <GenreTreeNode key={node.fullPath} node={node}
                selected={selectedGenrePath}
                onSelect={handleGenreSelect}
                onExpand={setExpandingGenre} />
            ))}
          </div>

          {/* Tags */}
          {allTags.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{t('browse.topTags') as string}</p>
              {allTags.slice(0, 20).map(({ tag, count }) => (
                <button key={tag}
                  onClick={() => { setSelectedTag(selectedTag === tag ? null : tag); setSelectedGenrePath(null); setPage(1) }}
                  className={cn('w-full text-left px-2.5 py-1.5 rounded-lg text-sm transition-colors truncate',
                    selectedTag === tag ? 'bg-amber-400/10 text-amber-700 font-medium' : 'text-slate-500 hover:bg-slate-100'
                  )}>
                  {tag}
                  <span className="ml-1 text-xs opacity-60">·{count}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-4">
          <div className="flex items-center gap-3">
            <input
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              placeholder={t('browse.placeholder') as string}
              className="flex-1 px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/40 focus:border-amber-400 shadow-sm"
            />
            {hasFilter && (
              <button onClick={clearFilters}
                className="px-3 py-2 text-xs text-slate-500 hover:text-slate-700 bg-white border border-slate-200 rounded-xl shadow-sm transition-colors">
                {t('browse.clear') as string}
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-xs text-slate-400">{(t('browse.count') as (n: number) => string)(total)}</p>
            {selectedGenrePath && (
              <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-xs flex items-center gap-1">
                {selectedGenrePath}
                <button onClick={() => { setSelectedGenrePath(null); setPage(1) }} className="ml-0.5 opacity-60 hover:opacity-100">×</button>
              </span>
            )}
            {selectedTag && (
              <span className={cn('px-2 py-0.5 rounded-full text-xs border flex items-center gap-1', tagColor(selectedTag))}>
                {selectedTag}
                <button onClick={() => { setSelectedTag(null); setPage(1) }} className="ml-0.5 opacity-60 hover:opacity-100">×</button>
              </span>
            )}
          </div>

          {loading && books.length === 0 ? (
            <div className="text-center py-16 text-slate-300">
              <BookOpen className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">{t('browse.loading') as string}</p>
            </div>
          ) : total === 0 ? (
            <div className="text-center py-16 text-slate-400">
              <BookOpen className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">{hasFilter ? t('browse.noMatch') as string : t('browse.empty') as string}</p>
            </div>
          ) : (
            <>
              {books.map(book => {
                const tags = parseTags(book.tags_json)
                const genreParts = book.genre_path?.split(' > ') || []
                const isExpanded = expandedId === book.id
                return (
                  <div key={book.id}
                    className={cn(
                      'flex gap-4 bg-white rounded-2xl border shadow-sm p-4 transition-all cursor-pointer',
                      isExpanded ? 'border-amber-200 shadow-md' : 'border-slate-100 hover:shadow-md'
                    )}
                    onClick={() => setExpandedId(isExpanded ? null : book.id)}>
                    <BookCover book={book} className="w-10 h-14 rounded-xl shrink-0"
                      defaultOpenMode={defaultOpenMode}
                      onRemoved={removeBook}
                      onUpdated={updateBook} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start gap-2">
                        <p className="font-semibold text-slate-800 flex-1 leading-snug">{book.title}</p>
                        {book.analysis_status === 'analyzing' && (
                          <span title={t('analysis.status.analyzing') as string}>
                            <Loader2 className="shrink-0 w-3.5 h-3.5 text-amber-500 animate-spin mt-0.5" />
                          </span>
                        )}
                        {book.analysis_status === 'done' && (
                          <span title={t('analysis.status.done') as string}>
                            <CheckCircle2 className="shrink-0 w-3.5 h-3.5 text-emerald-500 mt-0.5" />
                          </span>
                        )}
                        {book.analysis_status === 'failed' && (
                          <span title={t('analysis.status.failed') as string}>
                            <AlertTriangle className="shrink-0 w-3.5 h-3.5 text-red-400 mt-0.5" />
                          </span>
                        )}
                        {book.analysis_status === 'queued' && (
                          <span className="shrink-0 text-xs px-1 py-0 bg-slate-100 text-slate-400 rounded mt-0.5" title={t('analysis.status.queued') as string}>Q</span>
                        )}
                        <span className="shrink-0 text-xs font-mono px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded">
                          {book.file_format}
                        </span>
                        <button
                          onClick={e => { e.stopPropagation(); setDetailBook(book) }}
                          className="shrink-0 p-0.5 text-slate-300 hover:text-amber-500 transition-colors"
                          title={t('book.editInfo') as string}>
                          <Info className="w-3.5 h-3.5" />
                        </button>
                        {book.summary && (
                          <ChevronDown className={cn(
                            'shrink-0 w-4 h-4 text-slate-300 transition-transform duration-200',
                            isExpanded && 'rotate-180 text-amber-400'
                          )} />
                        )}
                      </div>
                      {book.author && <p className="text-xs text-slate-400 mt-0.5">{book.author}</p>}
                      {genreParts.length > 0 && (
                        <div className="flex items-center gap-1 mt-1.5 flex-wrap">
                          {genreParts.map((part, i) => (
                            <span key={i} className="flex items-center gap-1">
                              {i > 0 && <span className="text-slate-300 text-xs">›</span>}
                              <button
                                onClick={e => { e.stopPropagation(); handleGenreSelect(genreParts.slice(0, i + 1).join(' > ')) }}
                                className="text-xs text-amber-600 font-medium hover:underline">
                                {part}
                              </button>
                            </span>
                          ))}
                        </div>
                      )}
                      {book.summary && (
                        <p className={cn(
                          'text-sm text-slate-500 mt-2 leading-relaxed',
                          !isExpanded && 'line-clamp-3'
                        )}>
                          {book.summary}
                        </p>
                      )}
                      {tags.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2.5">
                          {tags.map(tag => (
                            <button key={tag}
                              onClick={e => { e.stopPropagation(); setSelectedTag(tag); setSelectedGenrePath(null); setPage(1) }}
                              className={cn('px-2 py-0.5 rounded-full text-xs border transition-opacity hover:opacity-80', tagColor(tag))}>
                              {tag}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
              <Pagination page={page} totalPages={totalPages} total={total} onPage={p => { setPage(p); setExpandedId(null) }} />
            </>
          )}
        </div>
      </div>

      {expandingGenre && (
        <GenreExpandModal
          genrePath={expandingGenre}
          onClose={() => setExpandingGenre(null)}
          onApplied={() => {
            api.get<GenreEntry[]>('/books/genres').then(setGenreData).catch(() => {})
            setRefreshKey(k => k + 1)
          }}
        />
      )}

      {detailBook && (
        <BookDetailModal
          book={detailBook}
          defaultOpenMode={defaultOpenMode}
          onClose={() => setDetailBook(null)}
          onRemoved={id => { removeBook(id); setDetailBook(null) }}
          onUpdated={updated => { updateBook(updated as Book); setDetailBook(null) }}
        />
      )}
    </div>
  )
}
