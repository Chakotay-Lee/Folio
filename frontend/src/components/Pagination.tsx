import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/LangContext'

interface Props {
  page: number
  totalPages: number
  total: number
  onPage: (p: number) => void
}

export function Pagination({ page, totalPages, total, onPage }: Props) {
  const { t } = useLang()
  if (totalPages <= 1) return null

  return (
    <div className="flex items-center justify-between mt-4 select-none">
      <p className="text-xs text-slate-400">
        {(t('page.info') as (p: number, ps: number, tot: number) => string)(page, totalPages, total)}
      </p>
      <div className="flex items-center gap-1">
        <button onClick={() => onPage(page - 1)} disabled={page <= 1}
          className={cn('w-7 h-7 flex items-center justify-center rounded-lg text-slate-500 transition-colors',
            page <= 1 ? 'opacity-30 cursor-not-allowed' : 'hover:bg-slate-100')}>
          <ChevronLeft className="w-4 h-4" />
        </button>
        {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
          const p = totalPages <= 7 ? i + 1
            : page <= 4 ? i + 1
            : page >= totalPages - 3 ? totalPages - 6 + i
            : page - 3 + i
          return (
            <button key={p} onClick={() => onPage(p)}
              className={cn('w-7 h-7 flex items-center justify-center rounded-lg text-xs transition-colors',
                p === page ? 'bg-amber-400 text-slate-900 font-semibold' : 'text-slate-500 hover:bg-slate-100')}>
              {p}
            </button>
          )
        })}
        <button onClick={() => onPage(page + 1)} disabled={page >= totalPages}
          className={cn('w-7 h-7 flex items-center justify-center rounded-lg text-slate-500 transition-colors',
            page >= totalPages ? 'opacity-30 cursor-not-allowed' : 'hover:bg-slate-100')}>
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
