import { useEffect, useState, useCallback } from 'react'
import { FolderOpen, Eye, RefreshCw, CheckCircle, AlertCircle, Clock, FolderSearch, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api, ApiError } from '@/lib/api'
import { useLang } from '@/lib/LangContext'

type FolderInfo = { path: string; exists: boolean; total_files: number; watched: boolean }
type FoldersData = { folders: FolderInfo[]; total_indexed: number }
type ScanResult = { file: string; status: string; message: string }
type LogEntry = { uuid: string; title: string; status: string; message: string; created_at: string }

const STATUS_STYLE: Record<string, string> = {
  success: 'text-emerald-600',
  duplicate: 'text-amber-600',
  error: 'text-red-500',
}

export function FoldersPage() {
  const { t } = useLang()
  const [folders, setFolders] = useState<FoldersData | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [scanning, setScanning] = useState(false)
  const [scanResults, setScanResults] = useState<ScanResult[] | null>(null)
  const [scanStatus, setScanStatus] = useState<{ status: string; pending_files: number; path?: string } | null>(null)
  const [customPath, setCustomPath] = useState('')
  const [customScanning, setCustomScanning] = useState(false)
  const [customError, setCustomError] = useState('')
  const [reclassifying, setReclassifying] = useState(false)
  const [reclassifyStatus, setReclassifyStatus] = useState<{ total: number } | null>(null)

  const loadData = useCallback(async () => {
    const [f, l] = await Promise.all([
      api.get<FoldersData>('/folders'),
      api.get<LogEntry[]>('/ingestion/logs'),
    ])
    setFolders(f)
    setLogs(l)
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const handleScan = async () => {
    setScanning(true)
    setScanResults(null)
    setScanStatus(null)
    try {
      const res = await api.post<{ status: string; pending_files: number }>('/folders/scan', {})
      setScanStatus(res)
      await loadData()
    } finally {
      setScanning(false)
    }
  }

  const handleReclassifyAll = async () => {
    if (!confirm(t('folder.reclassifyConfirm') as string)) return
    setReclassifying(true)
    setReclassifyStatus(null)
    try {
      const res = await api.post<{ status: string; total: number }>('/books/reclassify-all', {})
      setReclassifyStatus(res)
    } finally {
      setReclassifying(false)
    }
  }

  const handleCustomScan = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!customPath.trim()) return
    setCustomScanning(true)
    setCustomError('')
    setScanStatus(null)
    try {
      const res = await api.post<{ status: string; pending_files: number; path: string }>('/folders/scan-path', { path: customPath.trim() })
      setScanStatus(res)
      setCustomPath('')
      await loadData()
    } catch (err) {
      setCustomError(err instanceof ApiError ? err.message : String(err))
    } finally {
      setCustomScanning(false)
    }
  }

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">{t('folder.title') as string}</h2>
          <p className="text-slate-500 text-sm mt-0.5">
            {t('folder.subtitle') as string}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleReclassifyAll} disabled={reclassifying || scanning}
            title={t('folder.reclassify') as string}
            className="flex items-center gap-2 px-4 py-2 bg-violet-100 hover:bg-violet-200 disabled:opacity-50 border border-violet-200 rounded-xl text-sm font-semibold text-violet-700 transition-colors shadow-sm">
            <Sparkles className={cn('w-3.5 h-3.5', reclassifying && 'animate-pulse')} />
            {reclassifying ? t('folder.reclassifying') as string : t('folder.reclassify') as string}
          </button>
          <button onClick={handleScan} disabled={scanning}
            className="flex items-center gap-2 px-4 py-2 bg-amber-400 hover:bg-amber-500 disabled:opacity-50 rounded-xl text-sm font-semibold text-slate-900 transition-colors shadow-sm">
            <RefreshCw className={cn('w-3.5 h-3.5', scanning && 'animate-spin')} />
            {scanning ? t('folder.scanning') as string : t('folder.scanNow') as string}
          </button>
        </div>
      </div>

      {/* Scan status */}
      {reclassifyStatus && (
        <div className="flex items-center gap-3 px-4 py-3 bg-violet-50 border border-violet-200 rounded-xl text-sm text-violet-700">
          <Sparkles className="w-4 h-4 shrink-0" />
          {(t('folder.reclassifyStarted') as (n: number) => string)(reclassifyStatus.total)}
        </div>
      )}

      {scanStatus && (
        <div className="flex items-center gap-3 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-700">
          <CheckCircle className="w-4 h-4 shrink-0" />
          <span>
            {t('folder.scanStarted') as string}
            {scanStatus.path && <span className="font-mono ml-1 text-xs">({scanStatus.path})</span>}
            {' · '}{(t('folder.scanQueued') as (n: number) => string)(scanStatus.pending_files)}
          </span>
        </div>
      )}

      {/* Folder cards */}
      <div className="space-y-3">
        {folders?.folders.map(f => (
          <div key={f.path} className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 flex items-center gap-4">
            <div className={cn(
              'w-10 h-10 rounded-xl flex items-center justify-center shrink-0',
              f.exists ? 'bg-slate-100' : 'bg-red-50'
            )}>
              <FolderOpen className={cn('w-5 h-5', f.exists ? 'text-amber-500' : 'text-red-400')} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-mono font-medium text-slate-700 truncate">{f.path}</p>
              <p className="text-xs text-slate-400 mt-0.5">
                {f.exists
                  ? (t('folder.supportedFiles') as (n: number) => string)(f.total_files)
                  : t('folder.notFound') as string}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {f.watched && (
                <span title={t('folder.watchingTip') as string} className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-medium cursor-default">
                  <Eye className="w-3 h-3" /> {t('folder.watching') as string}
                </span>
              )}
              {!f.watched && (
                <span title={t('folder.indexedOnlyTip') as string} className="text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-500 border border-slate-200 cursor-default">
                  {t('folder.indexedOnly') as string}
                </span>
              )}
              <span className={cn(
                'text-xs px-2.5 py-1 rounded-full border font-medium',
                f.exists ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-500 border-red-200'
              )}>
                {f.exists ? t('folder.folderExists') as string : t('folder.folderMissing') as string}
              </span>
            </div>
          </div>
        ))}

        {folders && (
          <p className="text-xs text-slate-400 px-1">
            {(t('folder.totalIndexed') as (n: number) => string)(folders.total_indexed)}
          </p>
        )}
      </div>

      {/* One-time scan */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 space-y-3">
        <div className="flex items-center gap-2">
          <FolderSearch className="w-4 h-4 text-slate-400" />
          <h3 className="text-sm font-semibold text-slate-700">{t('folder.tempTitle') as string}</h3>
        </div>
        <p className="text-xs text-slate-400">{t('folder.tempDesc') as string}</p>
        <form onSubmit={handleCustomScan} className="flex gap-2">
          <input
            value={customPath}
            onChange={e => { setCustomPath(e.target.value); setCustomError('') }}
            placeholder={t('folder.tempPlaceholder') as string}
            className="flex-1 px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm font-mono focus:outline-none focus:ring-2 focus:ring-amber-400/40 focus:border-amber-400 transition-all"
          />
          <button type="submit" disabled={!customPath.trim() || customScanning}
            className="flex items-center gap-2 px-4 py-2 bg-amber-400 hover:bg-amber-500 disabled:opacity-50 rounded-xl text-sm font-semibold text-slate-900 transition-colors shrink-0">
            <RefreshCw className={cn('w-3.5 h-3.5', customScanning && 'animate-spin')} />
            {customScanning ? t('folder.scanning') as string : t('folder.scan') as string}
          </button>
        </form>
        {customError && (
          <p className="text-xs text-red-500 flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" /> {customError}
          </p>
        )}
      </div>

      {/* Scan results */}
      {scanResults !== null && (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-100">
            <h3 className="text-sm font-semibold text-slate-700">{(t('folder.scanResults') as (n: number) => string)(scanResults.length)}</h3>
          </div>
          <div className="px-5 py-4">
            {scanResults.length === 0 ? (
              <p className="text-sm text-slate-400 flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-emerald-500" /> All files already indexed.
              </p>
            ) : (
              <div className="space-y-1.5 max-h-48 overflow-y-auto text-sm">
                {scanResults.map((r, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className={cn('font-semibold shrink-0', STATUS_STYLE[r.status] ?? 'text-slate-400')}>
                      {r.status}
                    </span>
                    <span className="truncate text-slate-600">{r.file}</span>
                    {r.message && <span className="text-slate-400 text-xs truncate">— {r.message}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Import log */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-100 flex items-center gap-2">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <h3 className="text-sm font-semibold text-slate-700">{t('folder.recentLog') as string}</h3>
        </div>
        {logs.length === 0 ? (
          <div className="px-5 py-6 text-sm text-slate-400 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" /> {t('folder.noImports') as string}
          </div>
        ) : (
          <div className="divide-y divide-slate-50 max-h-80 overflow-y-auto">
            {logs.map((log, i) => (
              <div key={i} className="flex items-center gap-3 px-5 py-2.5 text-sm">
                <span className={cn('w-16 shrink-0 font-semibold text-xs', STATUS_STYLE[log.status] ?? 'text-slate-400')}>
                  {log.status}
                </span>
                <span className="flex-1 truncate text-slate-700">{log.title || log.uuid}</span>
                {log.message && (
                  <span className="text-xs text-slate-400 truncate max-w-xs">{log.message}</span>
                )}
                <span className="text-xs text-slate-400 shrink-0">
                  {new Date(log.created_at).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
