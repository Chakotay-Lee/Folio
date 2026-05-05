import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { type Lang, DEFAULT_LANG, translate } from './i18n'
import { api } from './api'

const LS_KEY = 'folio_lang'

type TKey = Parameters<typeof translate>[1]

interface LangCtx {
  lang: Lang
  setLang: (l: Lang) => void
  t: (key: TKey) => unknown
}

const Ctx = createContext<LangCtx>({
  lang: DEFAULT_LANG,
  setLang: () => {},
  t: (key) => translate(DEFAULT_LANG, key),
})

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const stored = localStorage.getItem(LS_KEY) as Lang | null
    return stored ?? DEFAULT_LANG
  })

  // Sync from backend config on mount
  useEffect(() => {
    api.get<{ content_language?: string }>('/config')
      .then(cfg => {
        if (cfg.content_language) {
          const l = cfg.content_language as Lang
          setLangState(l)
          localStorage.setItem(LS_KEY, l)
        }
      })
      .catch(() => {})
  }, [])

  const setLang = (l: Lang) => {
    setLangState(l)
    localStorage.setItem(LS_KEY, l)
    api.put('/config', { content_language: l }).catch(() => {})
  }

  const t = (key: TKey) => translate(lang, key)

  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>
}

export function useLang() {
  return useContext(Ctx)
}
