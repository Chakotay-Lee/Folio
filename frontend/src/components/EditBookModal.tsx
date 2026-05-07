import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Plus, Sparkles, Wand2 } from 'lucide-react'
import { api } from '@/lib/api'
import { parseTags } from '@/lib/bookUtils'
import { useLang } from '@/lib/LangContext'

interface Book {
  id: string; title: string; author: string | null
  genre_path: string | null; summary: string | null; tags_json: string | null
}

interface Props {
  book: Book
  onSaved: (updated: Book) => void
  onCancel: () => void
}

export function EditBookModal({ book, onSaved, onCancel }: Props) {
  const { t } = useLang()
  const [title, setTitle] = useState(book.title)
  const [author, setAuthor] = useState(book.author || '')
  const [genrePath, setGenrePath] = useState(book.genre_path || '')
  const [summary, setSummary] = useState(book.summary || '')
  const [tags, setTags] = useState<string[]>(parseTags(book.tags_json))
  const [tagInput, setTagInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [reclassifying, setReclassifying] = useState(false)
  const [suggesting, setSuggesting] = useState(false)
  const [isNewGenre, setIsNewGenre] = useState(false)
  const [error, setError] = useState('')

  // Genre combobox state
  const [existingGenres, setExistingGenres] = useState<string[]>([])
  const [genreOpen, setGenreOpen] = useState(false)
  const [genreFilter, setGenreFilter] = useState(book.genre_path || '')
  const genreRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.get<{ genre_path: string; count: number }[]>('/books/genres').then(list => {
      setExistingGenres(list.map(g => g.genre_path))
    }).catch(() => {})
  }, [])

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (genreRef.current && !genreRef.current.contains(e.target as Node)) {
        setGenreOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filteredGenres = existingGenres.filter(g =>
    g.toLowerCase().includes(genreFilter.toLowerCase())
  )

  const selectGenre = (g: string) => {
    setGenrePath(g)
    setGenreFilter(g)
    setIsNewGenre(false)
    setGenreOpen(false)
  }

  const handleGenreInput = (val: string) => {
    setGenreFilter(val)
    setGenrePath(val)
    setIsNewGenre(val.trim() !== '' && !existingGenres.includes(val.trim()))
    setGenreOpen(true)
  }

  const addTag = () => {
    const tag = tagInput.trim()
    if (tag && !tags.includes(tag)) { setTags([...tags, tag]); setTagInput('') }
  }
  const removeTag = (tag: string) => setTags(tags.filter(t => t !== tag))

  const handleReclassify = async () => {
    setReclassifying(true); setError('')
    try {
      const updated = await api.post<Book>(`/books/${book.id}/reclassify`, {})
      setTitle(updated.title); setAuthor(updated.author || '')
      const newGenre = updated.genre_path || ''
      setGenrePath(newGenre); setGenreFilter(newGenre)
      setIsNewGenre(newGenre !== '' && !existingGenres.includes(newGenre))
      setSummary(updated.summary || '')
      setTags(parseTags(updated.tags_json))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('edit.errReclassify') as string)
    } finally { setReclassifying(false) }
  }

  const handleSuggestGenre = async () => {
    setSuggesting(true); setError('')
    try {
      const res = await api.post<{ suggested_genre: string; is_new: boolean; description: string }>(
        `/books/${book.id}/suggest-genre`, {}
      )
      setGenrePath(res.suggested_genre)
      setGenreFilter(res.suggested_genre)
      setIsNewGenre(res.is_new)
      // Auto-save description for new genres (backend also does this, but sync locally for dropdown)
      if (res.is_new && res.suggested_genre && !existingGenres.includes(res.suggested_genre)) {
        setExistingGenres(prev => [...prev, res.suggested_genre])
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('edit.errReclassify') as string)
    } finally { setSuggesting(false) }
  }

  const handleSave = async () => {
    setLoading(true); setError('')
    try {
      const updated = await api.put<Book>(`/books/${book.id}`, {
        title, author: author || null, genre_path: genrePath, summary, tags,
      })
      onSaved(updated)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('edit.errSave') as string)
      setLoading(false)
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-[300] flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h3 className="text-base font-semibold text-slate-800">{t('edit.title') as string}</h3>
          <div className="flex items-center gap-2">
            <button onClick={handleReclassify} disabled={reclassifying || loading}
              title={t('edit.reclassify') as string}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-violet-700 bg-violet-50 hover:bg-violet-100 border border-violet-200 rounded-lg transition-colors disabled:opacity-50">
              <Sparkles className={`w-3.5 h-3.5 ${reclassifying ? 'animate-pulse' : ''}`} />
              {reclassifying ? t('edit.reclassifying') as string : t('edit.reclassify') as string}
            </button>
            <button onClick={onCancel} className="text-slate-400 hover:text-slate-600">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="overflow-y-auto flex-1 px-6 py-4 space-y-4">
          {/* Title */}
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">{t('edit.fieldTitle') as string}</label>
            <input value={title} onChange={e => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/40 focus:border-amber-400" />
          </div>

          {/* Author */}
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">{t('edit.fieldAuthor') as string}</label>
            <input value={author} onChange={e => setAuthor(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/40 focus:border-amber-400" />
          </div>

          {/* Genre combobox */}
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">{t('edit.fieldGenre') as string}</label>
            <div className="flex gap-2">
              <div ref={genreRef} className="relative flex-1">
                <input
                  value={genreFilter}
                  onChange={e => handleGenreInput(e.target.value)}
                  onFocus={() => setGenreOpen(true)}
                  placeholder={t('edit.genrePlaceholder') as string}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/40 focus:border-amber-400"
                />
                {isNewGenre && genreFilter.trim() && (
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-semibold text-emerald-600 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded-full">
                    {t('edit.genreNew') as string}
                  </span>
                )}
                {genreOpen && filteredGenres.length > 0 && (
                  <ul className="absolute z-10 left-0 right-0 top-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                    {filteredGenres.map(g => (
                      <li
                        key={g}
                        onMouseDown={() => selectGenre(g)}
                        className={`px-3 py-2 text-sm cursor-pointer hover:bg-amber-50 ${genrePath === g ? 'bg-amber-50 text-amber-700 font-medium' : 'text-slate-700'}`}>
                        {g}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <button
                onClick={handleSuggestGenre}
                disabled={suggesting || reclassifying || loading}
                title={t('edit.suggestGenre') as string}
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-lg transition-colors disabled:opacity-50 shrink-0">
                <Wand2 className={`w-3.5 h-3.5 ${suggesting ? 'animate-pulse' : ''}`} />
                {suggesting ? t('edit.suggestingGenre') as string : t('edit.suggestGenre') as string}
              </button>
            </div>
          </div>

          {/* Summary */}
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">{t('edit.fieldSummary') as string}</label>
            <textarea value={summary} onChange={e => setSummary(e.target.value)} rows={4}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/40 focus:border-amber-400 resize-none" />
          </div>

          {/* Tags */}
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1.5">{t('edit.fieldTags') as string}</label>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {tags.map(tag => (
                <span key={tag} className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded-full text-xs">
                  {tag}
                  <button onClick={() => removeTag(tag)} className="opacity-60 hover:opacity-100">×</button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input value={tagInput} onChange={e => setTagInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addTag()}
                placeholder={t('edit.tagPlaceholder') as string}
                className="flex-1 px-3 py-1.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/40 focus:border-amber-400" />
              <button onClick={addTag}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 rounded-lg text-sm transition-colors">
                <Plus className="w-4 h-4" />
              </button>
            </div>
          </div>

          {error && <p className="text-xs text-red-500">{error}</p>}
        </div>

        <div className="flex gap-2 px-6 py-4 border-t border-slate-100">
          <button onClick={onCancel}
            className="flex-1 px-4 py-2 text-sm text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors">
            {t('edit.cancel') as string}
          </button>
          <button onClick={handleSave} disabled={loading || !title.trim()}
            className="flex-1 px-4 py-2 text-sm font-medium text-slate-900 bg-amber-400 hover:bg-amber-500 disabled:opacity-50 rounded-xl transition-colors">
            {loading ? t('edit.saving') as string : t('edit.save') as string}
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}
