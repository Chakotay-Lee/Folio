import { useState } from 'react'
import { MoreHorizontal } from 'lucide-react'
import { cn } from '@/lib/utils'
import { bookCoverColor } from '@/lib/bookUtils'
import { BookContextMenu, openBook } from './BookContextMenu'
import { ConfirmRemoveModal } from './ConfirmRemoveModal'
import { EditBookModal } from './EditBookModal'

interface Book {
  id: string; title: string; author: string | null
  genre_path: string | null; summary: string | null; tags_json: string | null
  file_format?: string
}

interface BookCoverProps {
  book: Book
  className?: string
  children?: React.ReactNode
  defaultOpenMode?: 'system' | 'browser' | 'download'
  onRemoved?: (id: string) => void
  onUpdated?: (book: Book) => void
}

export function BookCover({
  book, className, children,
  defaultOpenMode = 'system',
  onRemoved, onUpdated,
}: BookCoverProps) {
  const [imgFailed, setImgFailed] = useState(false)
  const [menuAnchor, setMenuAnchor] = useState<DOMRect | null>(null)
  const [showRemove, setShowRemove] = useState(false)
  const [showEdit, setShowEdit] = useState(false)

  const handleCoverClick = (e: React.MouseEvent) => {
    if (menuAnchor) return
    e.stopPropagation()
    openBook(book.id, defaultOpenMode).catch(() => {})
  }

  return (
    <div className={cn('relative group', className)}>
      {/* Cover image or color fallback — overflow-hidden here to clip image to border-radius */}
      <div className="absolute inset-0 cursor-pointer overflow-hidden"
        style={{ borderRadius: 'inherit' }}
        onClick={handleCoverClick}>
        {!imgFailed ? (
          <img src={`/api/books/${book.id}/cover`} alt=""
            className="w-full h-full object-cover"
            onError={() => setImgFailed(true)} />
        ) : (
          <div className={cn('w-full h-full', bookCoverColor(book.title))} />
        )}
      </div>

      {/* Children (format badge etc.) */}
      {children && <div className="relative z-10">{children}</div>}

      {/* Context menu trigger */}
      <div className="absolute top-1 right-1 z-20 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={e => {
            e.stopPropagation()
            const rect = menuAnchor ? null : e.currentTarget.getBoundingClientRect()
            setMenuAnchor(rect)
          }}
          className="w-6 h-6 rounded-md bg-black/40 hover:bg-black/60 flex items-center justify-center transition-colors">
          <MoreHorizontal className="w-3.5 h-3.5 text-white" />
        </button>
        {menuAnchor && (
          <BookContextMenu
            book={book}
            defaultOpenMode={defaultOpenMode}
            anchorRect={menuAnchor}
            onEdit={() => { setMenuAnchor(null); setShowEdit(true) }}
            onRemove={() => { setMenuAnchor(null); setShowRemove(true) }}
            onClose={() => setMenuAnchor(null)}
          />
        )}
      </div>

      {showRemove && (
        <ConfirmRemoveModal
          bookId={book.id}
          bookTitle={book.title}
          onConfirm={() => { setShowRemove(false); onRemoved?.(book.id) }}
          onCancel={() => setShowRemove(false)}
        />
      )}
      {showEdit && (
        <EditBookModal
          book={book}
          onSaved={updated => { setShowEdit(false); onUpdated?.(updated as Book) }}
          onCancel={() => setShowEdit(false)}
        />
      )}
    </div>
  )
}
