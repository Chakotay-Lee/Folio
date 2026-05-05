const COVER_COLORS = [
  'bg-violet-400', 'bg-blue-500', 'bg-emerald-500', 'bg-amber-400',
  'bg-rose-400', 'bg-cyan-500', 'bg-orange-400', 'bg-pink-400',
  'bg-indigo-400', 'bg-teal-500', 'bg-fuchsia-400', 'bg-lime-500',
]

const TAG_PALETTES = [
  'bg-violet-100 text-violet-700 border-violet-200',
  'bg-blue-100 text-blue-700 border-blue-200',
  'bg-emerald-100 text-emerald-700 border-emerald-200',
  'bg-amber-100 text-amber-700 border-amber-200',
  'bg-rose-100 text-rose-700 border-rose-200',
  'bg-cyan-100 text-cyan-700 border-cyan-200',
  'bg-orange-100 text-orange-700 border-orange-200',
  'bg-pink-100 text-pink-700 border-pink-200',
  'bg-indigo-100 text-indigo-700 border-indigo-200',
  'bg-teal-100 text-teal-700 border-teal-200',
]

function strHash(s: string): number {
  return s.split('').reduce((a, c) => a + c.charCodeAt(0), 0)
}

export function bookCoverColor(title: string): string {
  return COVER_COLORS[strHash(title) % COVER_COLORS.length]
}

export function tagColor(tag: string): string {
  return TAG_PALETTES[strHash(tag) % TAG_PALETTES.length]
}

export function parseTags(tagsJson: string | null | undefined): string[] {
  if (!tagsJson) return []
  try {
    const raw = JSON.parse(tagsJson)
    return [...new Set<string>(Array.isArray(raw) ? raw : [])]
  } catch { return [] }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
