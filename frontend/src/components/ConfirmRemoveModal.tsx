import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Trash2, X } from 'lucide-react'
import { api } from '@/lib/api'
import { useLang } from '@/lib/LangContext'

interface Props {
  bookId: string
  bookTitle: string
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmRemoveModal({ bookId, bookTitle, onConfirm, onCancel }: Props) {
  const { t } = useLang()
  const [deleteFile, setDeleteFile] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleConfirm = async () => {
    setLoading(true)
    try {
      await api.delete(`/books/${bookId}${deleteFile ? '?delete_file=true' : ''}`)
      onConfirm()
    } catch {
      setLoading(false)
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-[300] flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm mx-4 p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center shrink-0">
            <Trash2 className="w-5 h-5 text-red-500" />
          </div>
          <button onClick={onCancel} className="text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <h3 className="text-base font-semibold text-slate-800 mb-1">{t('remove.title') as string}</h3>
        <p className="text-sm text-slate-500 mb-4">
          {(t('remove.confirm') as (title: string) => string)(bookTitle)}
        </p>

        <label className="flex items-center gap-2.5 mb-5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={deleteFile}
            onChange={e => setDeleteFile(e.target.checked)}
            className="w-4 h-4 rounded accent-red-500"
          />
          <span className="text-sm text-slate-600">{t('remove.deleteFile') as string}</span>
        </label>

        <div className="flex gap-2">
          <button onClick={onCancel}
            className="flex-1 px-4 py-2 text-sm text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors">
            {t('remove.cancel') as string}
          </button>
          <button onClick={handleConfirm} disabled={loading}
            className="flex-1 px-4 py-2 text-sm font-medium text-white bg-red-500 hover:bg-red-600 disabled:opacity-50 rounded-xl transition-colors">
            {loading ? t('remove.removing') as string : t('remove.btn') as string}
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}
