import { createContext, useContext, useRef, useState } from 'react'

export type AudioTrack = {
  url: string
  title: string
  subtitle?: string
}

type AudioPlayerState = {
  currentTrack: AudioTrack | null
  isPlaying: boolean
  currentTime: number
  duration: number
  volume: number
  playTrack: (track: AudioTrack) => void
  togglePlay: () => void
  seek: (time: number) => void
  setVolume: (vol: number) => void
  close: () => void
}

const Ctx = createContext<AudioPlayerState | null>(null)

export function AudioPlayerProvider({ children }: { children: React.ReactNode }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [currentTrack, setCurrentTrack] = useState<AudioTrack | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(0.8)

  const playTrack = (track: AudioTrack) => {
    const audio = audioRef.current
    if (!audio) return
    audio.src = track.url
    audio.volume = volume
    audio.play().catch(() => {})
    setCurrentTrack(track)
    setCurrentTime(0)
    setDuration(0)
  }

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio || !currentTrack) return
    if (isPlaying) audio.pause()
    else audio.play().catch(() => {})
  }

  const seek = (time: number) => {
    const audio = audioRef.current
    if (!audio) return
    audio.currentTime = time
    setCurrentTime(time)
  }

  const handleSetVolume = (vol: number) => {
    const audio = audioRef.current
    if (audio) audio.volume = vol
    setVolume(vol)
  }

  const close = () => {
    const audio = audioRef.current
    if (audio) { audio.pause(); audio.src = '' }
    setCurrentTrack(null)
    setIsPlaying(false)
    setCurrentTime(0)
    setDuration(0)
  }

  return (
    <Ctx.Provider value={{
      currentTrack, isPlaying, currentTime, duration, volume,
      playTrack, togglePlay, seek, setVolume: handleSetVolume, close,
    }}>
      {children}
      <audio
        ref={audioRef}
        onTimeUpdate={() => setCurrentTime(audioRef.current?.currentTime ?? 0)}
        onLoadedMetadata={() => setDuration(audioRef.current?.duration ?? 0)}
        onDurationChange={() => setDuration(audioRef.current?.duration ?? 0)}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
      />
    </Ctx.Provider>
  )
}

export function useAudioPlayer() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAudioPlayer used outside AudioPlayerProvider')
  return ctx
}
