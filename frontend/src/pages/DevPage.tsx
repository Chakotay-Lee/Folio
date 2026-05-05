import { useEffect, useState } from 'react'
import { CheckCircle, XCircle, Activity, Copy, RefreshCw, Terminal } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

type Log = { uuid: string; title: string; status: string; message: string; created_at: string }

const ENDPOINTS = [
  { method: 'GET',    path: '/api/health',                desc: 'Health check' },
  { method: 'GET',    path: '/api/books',                 desc: 'List all indexed books' },
  { method: 'GET',    path: '/api/search/semantic?q=…',  desc: 'Semantic vector search' },
  { method: 'GET',    path: '/api/folders',               desc: 'Folder status + file counts' },
  { method: 'POST',   path: '/api/folders/scan',          desc: 'Trigger background folder scan' },
  { method: 'GET',    path: '/api/ingestion/logs',        desc: 'Ingestion log entries' },
  { method: 'POST',   path: '/api/ingestion',             desc: 'Ingest a single file (file_path in body)' },
  { method: 'GET',    path: '/api/config',                desc: 'Read config.json' },
  { method: 'PUT',    path: '/api/config',                desc: 'Update config (deep merge)' },
  { method: 'POST',   path: '/api/reindex',               desc: 'Clear stale embedding index flag' },
  { method: 'DELETE', path: '/api/user-data',             desc: 'Wipe user activity database' },
]

const METHOD_COLOR: Record<string, string> = {
  GET: 'text-blue-600 bg-blue-50',
  POST: 'text-emerald-600 bg-emerald-50',
  PUT: 'text-amber-600 bg-amber-50',
  DELETE: 'text-red-500 bg-red-50',
}

const STATUS_STYLE: Record<string, string> = {
  success: 'text-emerald-600',
  duplicate: 'text-amber-600',
  error: 'text-red-500',
}

export function DevPage() {
  const [health, setHealth] = useState<'checking' | 'ok' | 'error'>('checking')
  const [logs, setLogs] = useState<Log[]>([])
  const [ingestPath, setIngestPath] = useState('')
  const [ingestResult, setIngestResult] = useState<string | null>(null)
  const [ingestLoading, setIngestLoading] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)

  useEffect(() => {
    api.get('/health').then(() => setHealth('ok')).catch(() => setHealth('error'))
    api.get<Log[]>('/ingestion/logs').then(setLogs)
  }, [])

  const handleIngest = async () => {
    if (!ingestPath.trim()) return
    setIngestLoading(true)
    setIngestResult(null)
    try {
      const result = await api.post<Record<string, unknown>>('/ingestion', { file_path: ingestPath })
      setIngestResult(JSON.stringify(result, null, 2))
    } catch (e) {
      setIngestResult(`Error: ${e}`)
    } finally {
      setIngestLoading(false)
    }
  }

  const copy = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(text)
    setTimeout(() => setCopied(null), 1500)
  }

  const healthBadge = {
    checking: 'bg-slate-100 text-slate-600 border-slate-200',
    ok: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    error: 'bg-red-50 text-red-600 border-red-200',
  }[health]

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Terminal className="w-5 h-5 text-slate-600" /> Developer Tools
          </h2>
          <p className="text-slate-500 text-sm mt-0.5">API reference and debug utilities</p>
        </div>
        <div className={cn('flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium border', healthBadge)}>
          {health === 'ok' ? <CheckCircle className="w-3.5 h-3.5" /> :
           health === 'error' ? <XCircle className="w-3.5 h-3.5" /> :
           <Activity className="w-3.5 h-3.5 animate-pulse" />}
          {health === 'checking' ? 'Checking…' : health === 'ok' ? 'Backend Online' : 'Backend Offline'}
        </div>
      </div>

      {/* Quick ingest */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 space-y-3">
        <h3 className="text-sm font-semibold text-slate-700">Quick Ingest</h3>
        <p className="text-xs text-slate-400">Process a single file through the full pipeline (text extraction → LLM metadata → DB + vector store)</p>
        <div className="flex gap-2">
          <input
            value={ingestPath}
            onChange={e => setIngestPath(e.target.value)}
            placeholder="/Users/…/book.pdf"
            className="flex-1 px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm font-mono focus:outline-none focus:ring-2 focus:ring-amber-400/40 focus:border-amber-400"
          />
          <button onClick={handleIngest} disabled={ingestLoading || !ingestPath.trim()}
            className="px-4 py-2 bg-amber-400 hover:bg-amber-500 disabled:opacity-40 rounded-xl text-sm font-semibold text-slate-900 transition-colors flex items-center gap-2 shrink-0">
            {ingestLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
            {ingestLoading ? 'Processing…' : 'Ingest'}
          </button>
        </div>
        {ingestResult && (
          <pre className="text-xs bg-slate-900 text-slate-200 rounded-xl p-4 overflow-x-auto leading-relaxed">{ingestResult}</pre>
        )}
      </div>

      {/* Endpoint reference */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-100">
          <h3 className="text-sm font-semibold text-slate-700">API Reference</h3>
        </div>
        <div className="divide-y divide-slate-50">
          {ENDPOINTS.map((ep, i) => (
            <div key={i} className="flex items-center gap-3 px-5 py-2.5 hover:bg-slate-50 group transition-colors">
              <span className={cn('text-xs font-mono font-bold px-1.5 py-0.5 rounded shrink-0 w-14 text-center', METHOD_COLOR[ep.method])}>
                {ep.method}
              </span>
              <code className="text-xs text-slate-700 flex-shrink-0">{ep.path}</code>
              <span className="text-xs text-slate-400 flex-1 truncate ml-1">— {ep.desc}</span>
              <button onClick={() => copy(ep.path)}
                className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-slate-600 transition-all shrink-0">
                {copied === ep.path ? (
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Full ingestion log */}
      {logs.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-700">Ingestion Log</h3>
            <span className="text-xs text-slate-400">{logs.length} entries</span>
          </div>
          <div className="divide-y divide-slate-50 max-h-80 overflow-y-auto">
            {logs.map((log, i) => (
              <div key={i} className="flex items-start gap-3 px-5 py-2.5 text-xs">
                <span className={cn('font-semibold shrink-0 w-16', STATUS_STYLE[log.status] || 'text-slate-500')}>
                  {log.status}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-slate-700 truncate font-medium">{log.title || log.uuid}</p>
                  {log.message && <p className="text-slate-400 mt-0.5">{log.message}</p>}
                </div>
                <span className="text-slate-400 shrink-0">{new Date(log.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
