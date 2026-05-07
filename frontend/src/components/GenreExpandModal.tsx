import { useState } from 'react'
import { createPortal } from 'react-dom'
import { X, ChevronDown, ChevronRight, Edit2, Check } from 'lucide-react'
import { api } from '@/lib/api'
import { useLang } from '@/lib/LangContext'

interface BookItem { id: string; title: string }
interface SubGenre {
  path: string
  description: string
  book_ids: string[]
  books: BookItem[]
}
interface ExpandResult {
  genre_prefix: string
  total_books: number
  sub_genres: SubGenre[]
}

interface Props {
  genrePath: string
  onClose: () => void
  onApplied: () => void
}

function EditableField({ value, onChange, placeholder, multiline }: {
  value: string; onChange: (v: string) => void; placeholder?: string; multiline?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)

  if (!editing) {
    return (
      <span className="inline-flex items-center gap-1 group cursor-pointer" onClick={() => { setDraft(value); setEditing(true) }}>
        <span className={value ? 'text-slate-700' : 'text-slate-400 italic'}>{value || placeholder}</span>
        <Edit2 className="w-3 h-3 text-slate-300 group-hover:text-slate-500 shrink-0" />
      </span>
    )
  }

  const commit = () => { onChange(draft); setEditing(false) }

  return multiline ? (
    <div className="flex items-start gap-1">
      <textarea
        autoFocus value={draft} onChange={e => setDraft(e.target.value)} rows={2}
        className="flex-1 text-sm px-2 py-1 border border-amber-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-400/40 resize-none"
      />
      <button onClick={commit} className="mt-1 p-1 text-emerald-600 hover:text-emerald-700">
        <Check className="w-4 h-4" />
      </button>
    </div>
  ) : (
    <div className="flex items-center gap-1">
      <input
        autoFocus value={draft} onChange={e => setDraft(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && commit()}
        className="flex-1 text-sm px-2 py-1 border border-amber-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-400/40"
      />
      <button onClick={commit} className="p-1 text-emerald-600 hover:text-emerald-700">
        <Check className="w-4 h-4" />
      </button>
    </div>
  )
}

export function GenreExpandModal({ genrePath, onClose, onApplied }: Props) {
  const { t } = useLang()
  const [state, setState] = useState<'idle' | 'loading' | 'preview' | 'applying' | 'done'>('idle')
  const [loadingMsg, setLoadingMsg] = useState('')
  const [result, setResult] = useState<ExpandResult | null>(null)
  const [subGenres, setSubGenres] = useState<SubGenre[]>([])
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)
  const [appliedCount, setAppliedCount] = useState(0)
  const [error, setError] = useState('')

  const BATCH_SIZE = 15

  const runExpand = async () => {
    setState('loading')
    setError('')
    try {
      // Phase 1: get sub-genre names + full book list
      setLoadingMsg('建議子分類中…')
      const phase1 = await api.post<{
        genre_prefix: string
        sub_genres: Array<{ path: string; description: string }>
        books: Array<{ id: string; title: string; tags: string[] }>
        total_books: number
      }>('/books/genres/expand/names', { genre_prefix: genrePath })

      const { sub_genres: suggestedGenres, books: allBooks, total_books } = phase1
      setLoadingMsg(`建議子分類完成，開始分配書籍…`)

      // Phase 2: assign books in batches
      const assignments: Record<string, string> = {}
      for (let i = 0; i < allBooks.length; i += BATCH_SIZE) {
        const batch = allBooks.slice(i, i + BATCH_SIZE)
        setLoadingMsg(`分配書籍 ${Math.min(i + BATCH_SIZE, allBooks.length)} / ${allBooks.length}…`)
        const phase2 = await api.post<{ assignments: Array<{ id: string; path: string }> }>(
          '/books/genres/expand/assign',
          { genre_prefix: genrePath, sub_genres: suggestedGenres, books: batch }
        )
        for (const a of phase2.assignments) {
          assignments[a.id] = a.path
        }
      }

      // Build result
      const sgMap: Record<string, SubGenre> = {}
      for (const sg of suggestedGenres) {
        sgMap[sg.path] = { path: sg.path, description: sg.description, book_ids: [], books: [] }
      }
      for (const book of allBooks) {
        const path = assignments[book.id]
        if (path && sgMap[path]) {
          sgMap[path].book_ids.push(book.id)
          sgMap[path].books.push({ id: book.id, title: book.title })
        }
      }
      const finalSubGenres = Object.values(sgMap).filter(sg => sg.book_ids.length > 0)
      const resultData: ExpandResult = {
        genre_prefix: genrePath,
        total_books,
        sub_genres: finalSubGenres,
      }
      setResult(resultData)
      setSubGenres(finalSubGenres)
      setState('preview')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed')
      setState('idle')
    }
  }

  const updateSubGenre = (idx: number, patch: Partial<SubGenre>) => {
    setSubGenres(prev => prev.map((sg, i) => i === idx ? { ...sg, ...patch } : sg))
  }

  const totalBooks = subGenres.reduce((s, sg) => s + sg.book_ids.length, 0)

  const handleApply = async () => {
    setState('applying')
    try {
      const body = {
        sub_genres: subGenres.map(sg => ({
          path: sg.path,
          description: sg.description,
          book_ids: sg.book_ids,
        }))
      }
      const res = await api.post<{ updated: number }>('/books/genres/expand/apply', body)
      setAppliedCount(res.updated)
      setState('done')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Apply failed')
      setState('preview')
    }
  }

  return createPortal(
    <>
      <div className="fixed inset-0 z-[300] bg-black/50 backdrop-blur-sm" onClick={state === 'loading' || state === 'applying' ? undefined : onClose} />
      <div className="fixed inset-0 z-[301] flex items-center justify-center p-4 pointer-events-none">
        <div className="pointer-events-auto bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden"
          onClick={e => e.stopPropagation()}>

          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
            <div>
              <h3 className="text-base font-semibold text-slate-800">
                {(t('genre.expandTitle') as (g: string) => string)(genrePath)}
              </h3>
              {state === 'preview' && result && (
                <p className="text-xs text-slate-500 mt-0.5">
                  {(t('genre.expandDesc') as (n: number) => string)(result.total_books)}
                </p>
              )}
            </div>
            <button onClick={onClose} disabled={state === 'loading' || state === 'applying'}
              className="text-slate-400 hover:text-slate-600 disabled:opacity-30">
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto px-6 py-4">

            {state === 'idle' && (
              <div className="text-center py-8">
                <p className="text-sm text-slate-500 mb-4">
                  AI 會分析此分類下所有書籍的書名、標籤，建議合適的子分類，並讓你預覽後確認。
                </p>
                <button onClick={runExpand}
                  className="px-6 py-2 bg-amber-400 hover:bg-amber-500 text-slate-900 text-sm font-semibold rounded-xl transition-colors">
                  {t('genre.expand') as string}
                </button>
              </div>
            )}

            {state === 'loading' && (
              <div className="text-center py-8 space-y-2">
                <div className="inline-flex items-center gap-2 text-amber-600">
                  <div className="w-4 h-4 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm">{t('genre.expanding') as string}</span>
                </div>
                {loadingMsg && <p className="text-xs text-slate-400">{loadingMsg}</p>}
              </div>
            )}

            {(state === 'preview' || state === 'applying') && (
              <div className="space-y-3">
                {subGenres.map((sg, idx) => (
                  <div key={idx} className="border border-slate-200 rounded-xl overflow-hidden">
                    <div className="px-4 py-3 bg-slate-50">
                      {/* Path */}
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-xs font-medium text-slate-400 w-14 shrink-0">{t('genre.subGenrePath') as string}</span>
                        <div className="flex-1 font-medium text-sm text-slate-800">
                          <EditableField
                            value={sg.path}
                            onChange={v => updateSubGenre(idx, { path: v })}
                            placeholder="分類路徑"
                          />
                        </div>
                        <span className="text-xs text-slate-400 shrink-0">
                          {(t('genre.subGenreBooks') as (n: number) => string)(sg.book_ids.length)}
                        </span>
                      </div>
                      {/* Description */}
                      <div className="flex items-start gap-2">
                        <span className="text-xs font-medium text-slate-400 w-14 shrink-0 pt-0.5">{t('genre.subGenreDesc') as string}</span>
                        <div className="flex-1 text-sm">
                          <EditableField
                            value={sg.description}
                            onChange={v => updateSubGenre(idx, { description: v })}
                            placeholder="（點擊編輯說明）"
                            multiline
                          />
                        </div>
                      </div>
                    </div>

                    {/* Book list toggle */}
                    <button
                      onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                      className="w-full flex items-center gap-1 px-4 py-2 text-xs text-slate-500 hover:bg-slate-50 transition-colors border-t border-slate-100">
                      {expandedIdx === idx
                        ? <ChevronDown className="w-3 h-3" />
                        : <ChevronRight className="w-3 h-3" />}
                      {sg.books.length} 本書
                    </button>

                    {expandedIdx === idx && (
                      <div className="px-4 pb-3 space-y-1 max-h-40 overflow-y-auto">
                        {sg.books.map(b => (
                          <p key={b.id} className="text-xs text-slate-600 truncate">· {b.title}</p>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {state === 'done' && (
              <div className="text-center py-8">
                <p className="text-sm text-emerald-600 font-medium">
                  {(t('genre.expandDone') as (n: number) => string)(appliedCount)}
                </p>
              </div>
            )}

            {error && <p className="text-xs text-red-500 mt-2">{error}</p>}
          </div>

          {/* Footer */}
          <div className="flex gap-2 px-6 py-4 border-t border-slate-100">
            {state === 'done' ? (
              <button onClick={() => { onApplied(); onClose() }}
                className="flex-1 px-4 py-2 text-sm font-medium text-slate-900 bg-amber-400 hover:bg-amber-500 rounded-xl transition-colors">
                完成
              </button>
            ) : (
              <>
                <button onClick={onClose} disabled={state === 'loading' || state === 'applying'}
                  className="flex-1 px-4 py-2 text-sm text-slate-600 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 rounded-xl transition-colors">
                  {t('edit.cancel') as string}
                </button>
                {(state === 'preview' || state === 'applying') && (
                  <button onClick={handleApply} disabled={state === 'applying' || subGenres.length === 0}
                    className="flex-1 px-4 py-2 text-sm font-medium text-slate-900 bg-amber-400 hover:bg-amber-500 disabled:opacity-50 rounded-xl transition-colors">
                    {state === 'applying'
                      ? t('genre.expandApplying') as string
                      : (t('genre.expandApply') as (n: number) => string)(totalBooks)}
                  </button>
                )}
              </>
            )}
          </div>

        </div>
      </div>
    </>,
    document.body
  )
}
