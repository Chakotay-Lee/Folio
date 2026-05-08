import { X, Play, Pause, Volume2, VolumeX, Volume1 } from 'lucide-react'
import { useAudioPlayer } from '@/lib/AudioPlayerContext'

function fmt(s: number) {
  if (!isFinite(s) || s < 0) return '0:00'
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

function TrackBar({
  value, max, onChange, color = 'bg-amber-400',
}: {
  value: number; max: number; onChange: (v: number) => void; color?: string
}) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div className="relative h-5 flex items-center group cursor-pointer">
      {/* Track background */}
      <div className="absolute inset-x-0 h-1 bg-slate-700 rounded-full" />
      {/* Fill */}
      <div className={`absolute left-0 h-1 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      {/* Thumb dot — visible on hover */}
      <div
        className="absolute w-3 h-3 bg-white rounded-full shadow -translate-x-1/2 scale-0 group-hover:scale-100 transition-transform"
        style={{ left: `${pct}%` }}
      />
      {/* Invisible native range handles all interactions */}
      <input
        type="range" min={0} max={max || 1} step={max > 60 ? 0.5 : 0.02} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="absolute inset-0 w-full opacity-0 cursor-pointer"
      />
    </div>
  )
}

export function GlobalAudioPlayer() {
  const {
    currentTrack, isPlaying, currentTime, duration, volume,
    togglePlay, seek, setVolume, close,
  } = useAudioPlayer()

  if (!currentTrack) return null

  const VolumeIcon = volume === 0 ? VolumeX : volume < 0.5 ? Volume1 : Volume2

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 h-16 bg-slate-900 border-t border-slate-800 flex items-center px-5 gap-4 shadow-2xl">

      {/* Track info */}
      <div className="w-48 shrink-0 min-w-0">
        <p className="text-white text-xs font-semibold truncate leading-tight">{currentTrack.title}</p>
        {currentTrack.subtitle && (
          <p className="text-slate-400 text-xs truncate mt-0.5">{currentTrack.subtitle}</p>
        )}
      </div>

      {/* Play / Pause */}
      <button
        onClick={togglePlay}
        className="shrink-0 w-9 h-9 bg-amber-400 hover:bg-amber-300 rounded-full flex items-center justify-center transition-colors shadow">
        {isPlaying
          ? <Pause className="w-4 h-4 text-slate-900" />
          : <Play className="w-4 h-4 text-slate-900 ml-0.5" />}
      </button>

      {/* Seek bar */}
      <div className="flex flex-1 items-center gap-2 min-w-0">
        <span className="text-slate-400 text-xs shrink-0 w-9 text-right tabular-nums">{fmt(currentTime)}</span>
        <div className="flex-1 min-w-0">
          <TrackBar value={currentTime} max={duration} onChange={seek} color="bg-amber-400" />
        </div>
        <span className="text-slate-400 text-xs shrink-0 w-9 tabular-nums">{fmt(duration)}</span>
      </div>

      {/* Volume */}
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={() => setVolume(volume > 0 ? 0 : 0.8)}
          className="text-slate-400 hover:text-white transition-colors">
          <VolumeIcon className="w-4 h-4" />
        </button>
        <div className="w-24">
          <TrackBar value={volume} max={1} onChange={setVolume} color="bg-slate-400" />
        </div>
      </div>

      {/* Close */}
      <button onClick={close} className="shrink-0 text-slate-600 hover:text-slate-300 transition-colors">
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}
