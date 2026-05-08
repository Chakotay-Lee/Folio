import { NavLink, Outlet } from 'react-router-dom'
import { cn } from '@/lib/utils'
import {
  BookOpen, Search, FolderOpen, Library, BarChart2, Settings, Code2,
} from 'lucide-react'
import { useLang } from '@/lib/LangContext'
import { useAudioPlayer } from '@/lib/AudioPlayerContext'

export function AppLayout() {
  const { t } = useLang()
  const { currentTrack } = useAudioPlayer()

  const navItems = [
    { to: '/', label: t('nav.library') as string, icon: BookOpen, end: true },
    { to: '/discover', label: t('nav.discover') as string, icon: Search },
    { to: '/notes', label: t('nav.browse') as string, icon: Library },
    { to: '/folders', label: t('nav.folders') as string, icon: FolderOpen },
    { to: '/profile', label: t('nav.stats') as string, icon: BarChart2 },
    { to: '/settings', label: t('nav.settings') as string, icon: Settings },
    { to: '/dev', label: t('nav.developer') as string, icon: Code2 },
  ]

  return (
    <div className="flex h-screen bg-stone-50">
      <aside className="w-56 shrink-0 bg-slate-900 flex flex-col">
        <div className="px-4 py-5 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-amber-400 rounded-lg flex items-center justify-center shrink-0">
              <BookOpen className="w-4 h-4 text-slate-900" strokeWidth={2.5} />
            </div>
            <div>
              <h1 className="text-white text-sm font-semibold tracking-tight leading-none">Folio</h1>
              <p className="text-slate-500 text-xs mt-0.5">{t('nav.subtitle') as string}</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-2 py-3 space-y-0.5">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                  isActive
                    ? 'bg-amber-400/15 text-amber-400 font-medium'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                )
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 py-3 border-t border-slate-800">
          <p className="text-xs text-slate-700">v0.2.dev.1</p>
        </div>
      </aside>

      <main className={cn('flex-1 overflow-y-auto', currentTrack && 'pb-16')}>
        <Outlet />
      </main>
    </div>
  )
}
