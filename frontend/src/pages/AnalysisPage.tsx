import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Loader2, X, Play, Pause, Volume2, Download, BookOpen, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { useLang } from '@/lib/LangContext'
import { useAudioPlayer } from '@/lib/AudioPlayerContext'

type Progress = {
  status: string
  stage: string
  current_page: number
  total_pages: number
  eta_seconds: number | null
  error?: string | null
}

type Manifest = {
  chapters?: { index: number; title: string }[]
  status?: string
}

export function AnalysisPage() {
  const { uuid } = useParams<{ uuid: string }>()
  const navigate = useNavigate()
  const { t } = useLang()
  const { playTrack, togglePlay, currentTrack, isPlaying } = useAudioPlayer()
  const isDevMode = new URLSearchParams(window.location.search).get('dev') === '1'
  const [progress, setProgress] = useState<Progress | null>(null)
  const [bookTitle, setBookTitle] = useState('')
  const [manifest, setManifest] = useState<Manifest | null>(null)
  const [audioUrls, setAudioUrls] = useState<Record<string, string>>({})
  const [generatingAudio, setGeneratingAudio] = useState<Record<string, boolean>>({})
  const [audioError, setAudioError] = useState<string | null>(null)
  const [cachedAudio, setCachedAudio] = useState<Record<string, string>>({})
  const [rebuildingHtml, setRebuildingHtml] = useState(false)
  const [rebuildMsg, setRebuildMsg] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!uuid) return

    api.get<{ title: string }>(`/books/${uuid}`)
      .then(b => setBookTitle(b.title))
      .catch(() => {})

    const poll = () => {
      api.get<Progress>(`/books/${uuid}/analysis/progress`)
        .then(p => {
          setProgress(p)
          if (p.status === 'done' || p.status === 'failed') {
            clearInterval(intervalRef.current!)
          }
        })
        .catch(() => {})
    }

    poll()
    intervalRef.current = setInterval(poll, 2000)
    return () => clearInterval(intervalRef.current!)
  }, [uuid])

  // Load manifest + TTS cache when done
  useEffect(() => {
    if (progress?.status === 'done' && uuid) {
      api.get<Manifest>(`/books/${uuid}/analysis/manifest`).then(setManifest).catch(() => {})
      api.get<Record<string, string>>(`/books/${uuid}/analysis/tts-cache`)
        .then(setCachedAudio).catch(() => {})
    }
  }, [progress?.status, uuid])

  const generateAudio = async (chIdx: number, mode: 'summary' | 'full', force = false) => {
    if (!uuid) return
    const key = `${chIdx}-${mode}`
    setGeneratingAudio(prev => ({ ...prev, [key]: true }))
    if (force) {
      setAudioUrls(prev => { const n = { ...prev }; delete n[key]; return n })
      setCachedAudio(prev => { const n = { ...prev }; delete n[key]; return n })
    }
    try {
      setAudioError(null)
      const { audio_url } = await api.post<{ audio_url: string }>(`/books/${uuid}/analysis/tts`, { chapter: chIdx, mode, force })
      setAudioUrls(prev => ({ ...prev, [key]: audio_url }))
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'TTS failed'
      try { setAudioError(JSON.parse(msg).detail ?? msg) } catch { setAudioError(msg) }
    } finally {
      setGeneratingAudio(prev => ({ ...prev, [key]: false }))
    }
  }

  const handleRebuildHtml = async () => {
    if (!uuid) return
    setRebuildingHtml(true)
    setRebuildMsg(null)
    try {
      const r = await api.post<{ chapters: number; files: number }>(`/books/${uuid}/analysis/rebuild-html`, {})
      setRebuildMsg(`Rebuilt ${r.files} files (${r.chapters} chapters)`)
    } catch {
      setRebuildMsg('Rebuild failed')
    } finally {
      setRebuildingHtml(false)
    }
  }

  const handleCancel = async () => {
    if (!uuid) return
    try {
      await api.post(`/books/${uuid}/analysis/cancel`, {})
      navigate(-1)
    } catch {
      navigate(-1)
    }
  }

  const percent = progress && progress.total_pages > 0
    ? Math.round((progress.current_page / progress.total_pages) * 100)
    : 0

  const etaLabel = progress?.eta_seconds != null
    ? (() => {
        const s = Math.ceil(progress.eta_seconds)
        if (s < 60) return `${s}s`
        const m = Math.floor(s / 60), r = s % 60
        return r === 0 ? `${m}m` : `${m}m ${r}s`
      })()
    : '—'

  return (
    <div className="max-w-xl mx-auto pt-16 px-4">
      <h2 className="text-2xl font-bold text-slate-900 mb-1">{t('analysis.progress') as string}</h2>
      {bookTitle && <p className="text-slate-500 text-sm mb-8">{bookTitle}</p>}

      {!progress ? (
        <div className="flex items-center gap-2 text-slate-400">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>{t('analysis.loading') as string}</span>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Progress bar */}
          <div>
            <div className="flex justify-between text-xs text-slate-500 mb-1">
              <span>{t('analysis.page') as string} {progress.current_page} / {progress.total_pages}</span>
              <span>{percent}%</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2.5">
              <div
                className="bg-amber-400 h-2.5 rounded-full transition-all duration-500"
                style={{ width: `${percent}%` }}
              />
            </div>
          </div>

          {/* Stage + ETA */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wider mb-0.5">{t('analysis.stage') as string}</p>
              <p className="font-medium text-slate-700 truncate">{progress.stage}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wider mb-0.5">{t('analysis.eta') as string}</p>
              <p className="font-medium text-slate-700">{etaLabel}</p>
            </div>
          </div>

          {/* Status */}
          <p className={`text-sm font-medium ${
            progress.status === 'done' ? 'text-emerald-600' :
            progress.status === 'failed' ? 'text-red-500' :
            'text-amber-600'
          }`}>
            {t(`analysis.status.${progress.status}` as Parameters<typeof t>[0]) as string}
          </p>
          {progress.status === 'failed' && progress.error && (
            <p className="text-xs text-red-400 bg-red-50 border border-red-100 rounded-xl px-3 py-2 font-mono break-all">
              {progress.error}
            </p>
          )}

          {/* Cancel button (only while active) */}
          {(progress.status === 'analyzing' || progress.status === 'queued') && (
            <button
              onClick={handleCancel}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-red-200 text-red-500 hover:bg-red-50 text-sm rounded-xl transition-colors">
              <X className="w-3.5 h-3.5" />
              {t('analysis.cancel') as string}
            </button>
          )}

          {/* Done: export + chapters with TTS */}
          {progress.status === 'done' && uuid && (
            <div className="space-y-4 pt-2">
              <div className="flex flex-wrap gap-2">
                <a
                  href={`/api/books/${uuid}/analysis/chapters/index.html`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 border border-amber-200 text-amber-700 hover:bg-amber-100 text-sm rounded-xl transition-colors">
                  <BookOpen className="w-3.5 h-3.5" />
                  {t('analysis.browseChapters') as string}
                </a>
                <a
                  href={`/api/books/${uuid}/analysis/export`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 text-slate-600 hover:bg-slate-50 text-sm rounded-xl transition-colors">
                  <Download className="w-3.5 h-3.5" />
                  {t('analysis.exportHtml') as string}
                </a>
                {isDevMode && (
                  <button
                    onClick={handleRebuildHtml}
                    disabled={rebuildingHtml}
                    title="Re-generate HTML from existing text files (no re-analysis)"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 text-slate-500 hover:bg-slate-50 text-sm rounded-xl transition-colors disabled:opacity-50">
                    {rebuildingHtml
                      ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      : <RefreshCw className="w-3.5 h-3.5" />}
                    Rebuild HTML
                  </button>
                )}
              </div>
              {rebuildMsg && (
                <p className="text-xs text-slate-500 bg-slate-50 border border-slate-100 rounded-lg px-3 py-1.5">
                  {rebuildMsg}
                </p>
              )}

              {audioError && (
                <p className="text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                  {audioError}
                </p>
              )}

              {manifest?.chapters && manifest.chapters.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-700 mb-3">{t('analysis.chapters') as string}</h3>
                  <div className="space-y-3">
                    {manifest.chapters.map(ch => (
                      <div key={ch.index} className="bg-white border border-slate-100 rounded-xl p-3 space-y-2">
                        <p className="text-sm font-medium text-slate-700">{ch.index}. {ch.title}</p>
                        <div className="flex flex-wrap gap-2 items-center">
                          {(['summary', 'full'] as const).map(mode => {
                            const key = `${ch.index}-${mode}`
                            const url = audioUrls[key] || cachedAudio[key]
                            const busy = generatingAudio[key]
                            const label = mode === 'summary' ? t('analysis.listenSummary') as string : t('analysis.listenChapter') as string
                            const active = currentTrack?.url === url && !!url

                            if (busy) return (
                              <span key={key} className="flex items-center gap-1 px-2 py-1 text-xs text-slate-400">
                                <Loader2 className="w-3 h-3 animate-spin" />{t('analysis.generating') as string}
                              </span>
                            )
                            if (url) return (
                              <div key={key} className="flex items-center gap-1">
                                <button
                                  onClick={() => active ? togglePlay() : playTrack({ url, title: label, subtitle: bookTitle })}
                                  className={cn(
                                    'flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-lg border transition-colors',
                                    active && isPlaying
                                      ? 'bg-amber-400 border-amber-400 text-slate-900 font-medium'
                                      : active
                                        ? 'bg-amber-50 border-amber-300 text-amber-700'
                                        : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                                  )}>
                                  {active && isPlaying
                                    ? <><Pause className="w-3 h-3" />{t('analysis.pause') as string}</>
                                    : <><Play className="w-3 h-3" />{label}</>}
                                </button>
                                <button
                                  onClick={() => generateAudio(ch.index, mode, true)}
                                  title={t('analysis.regenerate') as string}
                                  className="p-1 text-slate-300 hover:text-amber-500 transition-colors">
                                  <RefreshCw className="w-3 h-3" />
                                </button>
                              </div>
                            )
                            return (
                              <button key={key}
                                onClick={() => generateAudio(ch.index, mode)}
                                className="flex items-center gap-1 px-2 py-1 text-xs border border-slate-200 rounded-lg text-slate-500 hover:bg-slate-50">
                                <Volume2 className="w-3 h-3" />{label}
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
