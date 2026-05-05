import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Monitor, Globe, Download, Edit3, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { useLang } from '@/lib/LangContext'

interface Book {
  id: string; title: string; author: string | null
  genre_path: string | null; summary: string | null; tags_json: string | null
  file_format?: string
}

interface Props {
  book: Book
  defaultOpenMode: 'system' | 'browser' | 'download'
  anchorRect: DOMRect
  onEdit: () => void
  onRemove: () => void
  onClose: () => void
}

const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'

async function openBook(bookId: string, mode: 'system' | 'browser' | 'download', fileFormat?: string) {
  const effectiveMode = (mode === 'system' && !isLocalhost) ? 'browser' : mode
  if (effectiveMode === 'system') {
    await api.post(`/books/${bookId}/open`, {})
  } else if (effectiveMode === 'browser') {
    if (fileFormat === 'epub') {
      window.open(`/reader/${bookId}`, '_blank')
    } else {
      window.open(`/api/books/${bookId}/file?mode=inline`, '_blank')
    }
  } else {
    const a = document.createElement('a')
    a.href = `/api/books/${bookId}/file?mode=download`
    a.click()
  }
}

export function BookContextMenu({ book, defaultOpenMode, anchorRect, onEdit, onRemove, onClose }: Props) {
  const { t } = useLang()
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  const handleOpen = async (e: React.MouseEvent, mode: 'system' | 'browser' | 'download') => {
    e.stopPropagation()
    onClose()
    await openBook(book.id, mode, book.file_format)
  }

  const top = anchorRect.bottom + 4
  const right = window.innerWidth - anchorRect.right

  return createPortal(
    <div ref={menuRef}
      style={{ position: 'fixed', top, right, zIndex: 9999 }}
      className="w-48 bg-white rounded-xl shadow-lg border border-slate-100 py-1 text-sm"
      onClick={e => e.stopPropagation()}>
      <button
        onClick={e => handleOpen(e, defaultOpenMode)}
        className="w-full text-left px-3 py-2 font-medium text-slate-800 hover:bg-slate-50 transition-colors">
        {t('book.open') as string}
      </button>
      <div className="border-t border-slate-100 my-1" />
      <button
        onClick={e => handleOpen(e, 'system')}
        disabled={!isLocalhost}
        title={!isLocalhost ? t('book.localOnly') as string : undefined}
        className={cn('w-full text-left px-3 py-2 flex items-center gap-2 transition-colors',
          isLocalhost ? 'text-slate-600 hover:bg-slate-50' : 'text-slate-300 cursor-not-allowed')}>
        <Monitor className="w-3.5 h-3.5 shrink-0" /> {t('book.openInApp') as string}
      </button>
      <button onClick={e => handleOpen(e, 'browser')}
        className="w-full text-left px-3 py-2 flex items-center gap-2 text-slate-600 hover:bg-slate-50 transition-colors">
        <Globe className="w-3.5 h-3.5 shrink-0" /> {t('book.openInBrowser') as string}
      </button>
      <button onClick={e => handleOpen(e, 'download')}
        className="w-full text-left px-3 py-2 flex items-center gap-2 text-slate-600 hover:bg-slate-50 transition-colors">
        <Download className="w-3.5 h-3.5 shrink-0" /> {t('book.download') as string}
      </button>
      <div className="border-t border-slate-100 my-1" />
      <button onClick={e => { e.stopPropagation(); onClose(); onEdit() }}
        className="w-full text-left px-3 py-2 flex items-center gap-2 text-slate-600 hover:bg-slate-50 transition-colors">
        <Edit3 className="w-3.5 h-3.5 shrink-0" /> {t('book.editInfo') as string}
      </button>
      <button onClick={e => { e.stopPropagation(); onClose(); onRemove() }}
        className="w-full text-left px-3 py-2 flex items-center gap-2 text-red-500 hover:bg-red-50 transition-colors">
        <Trash2 className="w-3.5 h-3.5 shrink-0" /> {t('book.removeFromLib') as string}
      </button>
    </div>,
    document.body
  )
}

export { openBook }
