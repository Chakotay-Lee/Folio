import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { X, Monitor, Globe, Download, Edit3, Trash2, FileText, Sparkles, Loader2, MessageSquare, Volume2 } from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { bookCoverColor, parseTags, tagColor, formatBytes } from '@/lib/bookUtils'
import { openBook } from './BookContextMenu'
import { EditBookModal } from './EditBookModal'
import { ConfirmRemoveModal } from './ConfirmRemoveModal'
import { useLang } from '@/lib/LangContext'

const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'

export type DetailBook = {
  id: string
  title: string
  author: string | null
  genre_path: string | null
  summary: string | null
  tags_json: string | null
  file_format?: string
  file_size_bytes?: number
  created_at?: string
  analysis_status?: string
}

interface Props {
  book: DetailBook
  defaultOpenMode?: 'system' | 'browser' | 'download'
  onClose: () => void
  onRemoved?: (id: string) => void
  onUpdated?: (book: DetailBook) => void
}

export function BookDetailModal({ book, defaultOpenMode = 'system', onClose, onRemoved, onUpdated }: Props) {
  const { t } = useLang()
  const navigate = useNavigate()
  const [imgFailed, setImgFailed] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [showRemove, setShowRemove] = useState(false)
  const [analysisStatus] = useState(book.analysis_status ?? 'none')
  const [triggeringAnalysis, setTriggeringAnalysis] = useState(false)

  const handleTriggerAnalysis = async () => {
    setTriggeringAnalysis(true)
    try {
      await api.post(`/books/${book.id}/analysis/trigger`, {})
      onClose()
      navigate(`/books/${book.id}/analysis`)
    } catch {
      setTriggeringAnalysis(false)
    }
  }

  const handleOpenChat = () => {
    onClose()
    navigate(`/books/${book.id}/chat`)
  }

  const handleViewAnalysis = () => {
    onClose()
    navigate(`/books/${book.id}/analysis`)
  }

  const handleExportHtml = () => {
    window.open(`/api/books/${book.id}/analysis/export`, '_blank')
  }

  const tags = parseTags(book.tags_json)
  const genreParts = book.genre_path?.split(' > ') ?? []

  const handleOpen = (mode: 'system' | 'browser' | 'download') => {
    onClose()
    openBook(book.id, mode, book.file_format)
  }

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[200] bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-[201] flex items-center justify-center p-4 pointer-events-none">
        <div
          className="pointer-events-auto bg-white rounded-2xl shadow-2xl w-full max-w-xl max-h-[90vh] flex flex-col overflow-hidden"
          onClick={e => e.stopPropagation()}>

          {/* Header: cover + title block */}
          <div className="flex gap-5 p-6 pb-4">
            {/* Cover */}
            <div className="w-24 h-32 rounded-xl overflow-hidden shrink-0 shadow-md">
              {!imgFailed ? (
                <img
                  src={`/api/books/${book.id}/cover`}
                  alt=""
                  className="w-full h-full object-cover"
                  onError={() => setImgFailed(true)}
                />
              ) : (
                <div className={cn('w-full h-full', bookCoverColor(book.title))} />
              )}
            </div>

            {/* Title / author / genre */}
            <div className="flex-1 min-w-0 pt-1">
              <p className="text-lg font-bold text-slate-900 leading-snug">{book.title}</p>
              {book.author && (
                <p className="text-sm text-slate-500 mt-1">{book.author}</p>
              )}
              {genreParts.length > 0 && (
                <div className="flex flex-wrap items-center gap-1 mt-2">
                  {genreParts.map((part, i) => (
                    <span key={i} className="text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
                      {part}
                    </span>
                  ))}
                </div>
              )}
              {(book.file_format || book.file_size_bytes) && (
                <div className="flex items-center gap-2 mt-3">
                  {book.file_format && (
                    <span className="flex items-center gap-1 text-xs text-slate-400 uppercase font-mono">
                      <FileText className="w-3 h-3" />{book.file_format}
                    </span>
                  )}
                  {book.file_size_bytes != null && (
                    <span className="text-xs text-slate-400">{formatBytes(book.file_size_bytes)}</span>
                  )}
                </div>
              )}
            </div>

            {/* Close button */}
            <button
              onClick={onClose}
              className="shrink-0 w-7 h-7 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-400 transition-colors">
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Tags */}
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 px-6 pb-3">
              {tags.map(tag => (
                <span key={tag} className={cn('px-2 py-0.5 rounded-full text-xs border', tagColor(tag))}>
                  {tag}
                </span>
              ))}
            </div>
          )}

          {/* Summary */}
          {book.summary ? (
            <div className="px-6 pb-4 overflow-y-auto flex-1">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">{t('book.summary') as string}</p>
              <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-line">{book.summary}</p>
            </div>
          ) : (
            <div className="flex-1" />
          )}

          {/* Actions */}
          <div className="px-6 py-4 border-t border-slate-100 flex items-center gap-2 flex-wrap">
            <button
              onClick={() => handleOpen(defaultOpenMode)}
              className="px-4 py-2 bg-amber-400 hover:bg-amber-500 text-slate-900 text-sm font-semibold rounded-xl transition-colors">
              {t('book.open') as string}
            </button>
            <button
              onClick={() => handleOpen('system')}
              disabled={!isLocalhost}
              title={!isLocalhost ? t('book.localOnly') as string : undefined}
              className={cn(
                'p-2 rounded-xl border text-sm transition-colors',
                isLocalhost
                  ? 'border-slate-200 text-slate-600 hover:bg-slate-50'
                  : 'border-slate-100 text-slate-300 cursor-not-allowed'
              )}>
              <Monitor className="w-4 h-4" />
            </button>
            <button
              onClick={() => handleOpen('browser')}
              className="p-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 text-sm transition-colors">
              <Globe className="w-4 h-4" />
            </button>
            <button
              onClick={() => handleOpen('download')}
              className="p-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 text-sm transition-colors">
              <Download className="w-4 h-4" />
            </button>
            <div className="flex-1" />
            <button
              onClick={() => setShowEdit(true)}
              className="p-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 text-sm transition-colors">
              <Edit3 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setShowRemove(true)}
              className="p-2 rounded-xl border border-red-100 text-red-400 hover:bg-red-50 text-sm transition-colors">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>

          {/* Analysis row */}
          <div className="px-6 pb-4 flex items-center gap-2 flex-wrap">
            {analysisStatus === 'none' || analysisStatus === 'failed' ? (
              <button
                onClick={handleTriggerAnalysis}
                disabled={triggeringAnalysis}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-50 hover:bg-violet-100 text-violet-700 border border-violet-200 text-xs font-medium rounded-xl transition-colors disabled:opacity-50">
                {triggeringAnalysis
                  ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  : <Sparkles className="w-3.5 h-3.5" />}
                {t(analysisStatus === 'failed' ? 'analysis.reanalyze' : 'analysis.deepAnalysis') as string}
              </button>
            ) : analysisStatus === 'done' ? (
              <button
                onClick={handleTriggerAnalysis}
                disabled={triggeringAnalysis}
                className="flex items-center gap-1.5 px-3 py-1.5 text-slate-500 hover:bg-slate-50 border border-slate-200 text-xs rounded-xl transition-colors disabled:opacity-50">
                <Sparkles className="w-3.5 h-3.5" />
                {t('analysis.reanalyze') as string}
              </button>
            ) : (
              <span className="flex items-center gap-1.5 px-3 py-1.5 text-amber-600 text-xs">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                {t(`analysis.status.${analysisStatus}` as Parameters<typeof t>[0]) as string}
              </span>
            )}

            {analysisStatus === 'done' && (
              <>
                <button
                  onClick={handleViewAnalysis}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-slate-600 hover:bg-slate-50 border border-slate-200 text-xs rounded-xl transition-colors">
                  <Volume2 className="w-3.5 h-3.5" />
                  {t('analysis.viewResults') as string}
                </button>
                <button
                  onClick={handleExportHtml}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-slate-600 hover:bg-slate-50 border border-slate-200 text-xs rounded-xl transition-colors">
                  {t('analysis.exportHtml') as string}
                </button>
                <button
                  onClick={handleOpenChat}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-slate-600 hover:bg-slate-50 border border-slate-200 text-xs rounded-xl transition-colors">
                  <MessageSquare className="w-3.5 h-3.5" />
                  {t('chat.title') as string}
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {showEdit && (
        <EditBookModal
          book={book as Parameters<typeof EditBookModal>[0]['book']}
          onSaved={updated => { setShowEdit(false); onUpdated?.(updated as DetailBook) }}
          onCancel={() => setShowEdit(false)}
        />
      )}
      {showRemove && (
        <ConfirmRemoveModal
          bookId={book.id}
          bookTitle={book.title}
          onConfirm={() => { setShowRemove(false); onRemoved?.(book.id); onClose() }}
          onCancel={() => setShowRemove(false)}
        />
      )}
    </>,
    document.body
  )
}
