import { useEffect, useState, useMemo } from 'react'
import { BookOpen, HardDrive, Tag, TrendingUp, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { tagColor, formatBytes } from '@/lib/bookUtils'
import { useLang } from '@/lib/LangContext'

type Stats = {
  total_books: number; total_bytes: number; genre_count: number; tag_count: number
  formats: Record<string, number>
}
type TagEntry = { tag: string; count: number }
type GenreEntry = { genre_path: string; count: number }
type Log = { uuid: string; title: string; status: string; message: string; created_at: string }

const STATUS_STYLE: Record<string, string> = {
  success: 'text-emerald-600',
  duplicate: 'text-amber-600',
  error: 'text-red-500',
}

export function ProfilePage() {
  const { t } = useLang()
  const [stats, setStats] = useState<Stats | null>(null)
  const [tags, setTags] = useState<TagEntry[]>([])
  const [genres, setGenres] = useState<GenreEntry[]>([])
  const [logs, setLogs] = useState<Log[]>([])

  useEffect(() => {
    api.get<Stats>('/books/stats').then(setStats).catch(() => {})
    api.get<TagEntry[]>('/books/tags').then(setTags).catch(() => {})
    api.get<GenreEntry[]>('/books/genres').then(setGenres).catch(() => {})
    api.get<Log[]>('/ingestion/logs').then(setLogs).catch(() => {})
  }, [])

  const topGenres = useMemo(() => {
    const topMap = new Map<string, number>()
    genres.forEach(g => {
      const top = g.genre_path.split(' > ')[0]
      topMap.set(top, (topMap.get(top) || 0) + g.count)
    })
    return Array.from(topMap.entries()).sort((a, b) => b[1] - a[1]).slice(0, 10)
  }, [genres])

  const maxGenreCount = topGenres[0]?.[1] || 1
  const topTags = tags.slice(0, 18)

  const logStatus = useMemo(() => logs.reduce<Record<string, number>>((a, l) => {
    a[l.status] = (a[l.status] || 0) + 1; return a
  }, {}), [logs])

  const statCards = [
    { label: t('stats.booksIndexed') as string, value: stats?.total_books ?? '—', icon: BookOpen, color: 'text-amber-500' },
    { label: t('stats.totalSize') as string, value: stats ? formatBytes(stats.total_bytes) : '—', icon: HardDrive, color: 'text-blue-500' },
    { label: t('stats.uniqueTags') as string, value: stats?.tag_count ?? '—', icon: Tag, color: 'text-violet-500' },
    { label: t('stats.imports') as string, value: logs.length, icon: TrendingUp, color: 'text-emerald-500' },
  ]

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">{t('stats.title') as string}</h2>
        <p className="text-slate-500 text-sm mt-0.5">{t('stats.subtitle') as string}</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {statCards.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 text-center space-y-1">
            <Icon className={cn('w-5 h-5 mx-auto', color)} />
            <p className="text-2xl font-bold text-slate-900">{value}</p>
            <p className="text-xs text-slate-400">{label}</p>
          </div>
        ))}
      </div>

      {/* Formats */}
      {stats && Object.keys(stats.formats).length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">{t('stats.formats') as string}</h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(stats.formats).map(([fmt, count]) => (
              <div key={fmt} className="flex items-center gap-2 px-4 py-2 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-sm font-mono font-bold text-slate-700 uppercase">{fmt}</span>
                <span className="text-xs text-slate-400">{count} files</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Genre bar chart */}
      {topGenres.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">{t('stats.topGenres') as string}</h3>
          <div className="space-y-3">
            {topGenres.map(([genre, count]) => (
              <div key={genre} className="flex items-center gap-3">
                <span className="w-28 text-xs text-slate-600 truncate">{genre}</span>
                <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-amber-400 h-full rounded-full transition-all duration-500"
                    style={{ width: `${(count / maxGenreCount) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-slate-400 w-5 text-right font-medium">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top tags cloud */}
      {topTags.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">{t('stats.topics') as string}</h3>
          <div className="flex flex-wrap gap-2">
            {topTags.map(({ tag, count }) => (
              <span key={tag}
                className={cn('px-3 py-1.5 rounded-full text-xs border flex items-center gap-1.5', tagColor(tag))}>
                {tag}
                <span className="opacity-60 font-semibold">{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Import log summary */}
      {logs.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-100 flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <h3 className="text-sm font-semibold text-slate-700">{t('stats.history') as string}</h3>
            <div className="ml-auto flex gap-3">
              {Object.entries(logStatus).map(([status, count]) => (
                <span key={status} className={cn('text-xs font-medium', STATUS_STYLE[status] || 'text-slate-500')}>
                  {count} {status}
                </span>
              ))}
            </div>
          </div>
          <div className="divide-y divide-slate-50 max-h-64 overflow-y-auto">
            {logs.slice(0, 30).map((log, i) => (
              <div key={i} className="flex items-center gap-3 px-5 py-2.5 text-xs">
                <span className={cn('font-semibold shrink-0 w-16', STATUS_STYLE[log.status] || 'text-slate-500')}>
                  {log.status}
                </span>
                <span className="flex-1 text-slate-600 truncate">{log.title || log.uuid}</span>
                {log.message && <span className="text-slate-400 truncate max-w-32">{log.message}</span>}
                <span className="text-slate-400 shrink-0">{new Date(log.created_at).toLocaleDateString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
