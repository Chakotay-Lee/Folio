import { useEffect, useState } from 'react'
import { Save, CheckCircle, AlertCircle, Cpu, Search, Eye, Globe } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api, ApiError } from '@/lib/api'
import { useLang } from '@/lib/LangContext'
import { LANGUAGES } from '@/lib/i18n'

type ModelConfig = {
  provider: string; model_name: string; base_url: string; api_key: string
  temperature: number; max_tokens: number; timeout_seconds: number; dimension?: number
}

type ConfigShape = {
  llms: {
    extraction_model: ModelConfig
    embedding_model: ModelConfig
    chat_model: ModelConfig
  }
  search_settings: { top_k: number; max_pages_to_analyze: number }
  ocr: { enabled: boolean; provider: string; min_chars_threshold: number }
}

const PROVIDERS = ['openai', 'ollama', 'anthropic']

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{label}</label>
      {children}
    </div>
  )
}

function inputCls() {
  return 'w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/40 focus:border-amber-400 transition-all'
}

function ModelSection({
  title, icon: Icon, value, onChange,
}: {
  title: string; icon: React.ElementType
  value: ModelConfig; onChange: (patch: Partial<ModelConfig>) => void
}) {
  const { t } = useLang()
  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 space-y-4">
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 bg-amber-400/15 rounded-lg flex items-center justify-center">
          <Icon className="w-3.5 h-3.5 text-amber-600" />
        </div>
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      </div>

      <Field label={t('settings.provider') as string}>
        <select
          value={value.provider}
          onChange={e => onChange({ provider: e.target.value })}
          className={inputCls()}>
          {PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label={t('settings.modelName') as string}>
          <input type="text" value={value.model_name} onChange={e => onChange({ model_name: e.target.value })} className={inputCls()} />
        </Field>
        <Field label={t('settings.apiKey') as string}>
          <input type="password" value={value.api_key} onChange={e => onChange({ api_key: e.target.value })} className={inputCls()} />
        </Field>
      </div>

      <Field label={t('settings.baseUrl') as string}>
        <input type="text" value={value.base_url} onChange={e => onChange({ base_url: e.target.value })} className={inputCls()} />
      </Field>

      <div className="grid grid-cols-3 gap-3">
        <Field label={t('settings.temperature') as string}>
          <input type="number" step="0.1" value={value.temperature} onChange={e => onChange({ temperature: Number(e.target.value) })} className={inputCls()} />
        </Field>
        <Field label={t('settings.maxTokens') as string}>
          <input type="number" value={value.max_tokens} onChange={e => onChange({ max_tokens: Number(e.target.value) })} className={inputCls()} />
        </Field>
        <Field label={t('settings.timeout') as string}>
          <input type="number" value={value.timeout_seconds} onChange={e => onChange({ timeout_seconds: Number(e.target.value) })} className={inputCls()} />
        </Field>
      </div>

      {value.dimension !== undefined && (
        <Field label={t('settings.embeddingDim') as string}>
          <input type="number" value={value.dimension} onChange={e => onChange({ dimension: Number(e.target.value) })} className={inputCls()} />
        </Field>
      )}
    </div>
  )
}

export function SettingsPage() {
  const { lang, setLang, t } = useLang()
  const [config, setConfig] = useState<ConfigShape | null>(null)
  const [status, setStatus] = useState<'loading' | 'idle' | 'saving' | 'ok' | 'error'>('loading')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    api.get<ConfigShape>('/config')
      .then(data => { setConfig(data); setStatus('idle') })
      .catch(() => setStatus('error'))
  }, [])

  const patchModel = (key: keyof ConfigShape['llms']) => (patch: Partial<ModelConfig>) =>
    setConfig(c => c ? { ...c, llms: { ...c.llms, [key]: { ...c.llms[key], ...patch } } } : c)

  const handleSave = async () => {
    if (!config) return
    setStatus('saving')
    try {
      await api.put('/config', config)
      setStatus('ok')
      setTimeout(() => setStatus('idle'), 2500)
    } catch (e) {
      setErrorMsg(e instanceof ApiError ? e.message : String(e))
      setStatus('error')
      setTimeout(() => setStatus('idle'), 3000)
    }
  }

  if (status === 'loading') return (
    <div className="p-8 text-slate-400 text-sm flex items-center gap-2">
      <div className="w-4 h-4 border-2 border-slate-200 border-t-amber-400 rounded-full animate-spin" />
      {t('settings.loading') as string}
    </div>
  )
  if (!config) return (
    <div className="p-8 text-red-500 text-sm flex items-center gap-2">
      <AlertCircle className="w-4 h-4" /> Failed to load config.json
    </div>
  )

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">{t('settings.title') as string}</h2>
        <p className="text-slate-500 text-sm mt-0.5">{t('settings.subtitle') as string}</p>
      </div>

      {/* Language */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 space-y-4">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 bg-amber-400/15 rounded-lg flex items-center justify-center">
            <Globe className="w-3.5 h-3.5 text-amber-600" />
          </div>
          <h3 className="text-sm font-semibold text-slate-800">{t('settings.language') as string}</h3>
        </div>
        <p className="text-xs text-slate-400">{t('settings.languageDesc') as string}</p>
        <div className="flex flex-wrap gap-2">
          {(Object.entries(LANGUAGES) as [import('@/lib/i18n').Lang, string][]).map(([code, name]) => (
            <button
              key={code}
              onClick={() => setLang(code)}
              className={cn(
                'px-4 py-2 rounded-xl text-sm font-medium border transition-colors',
                lang === code
                  ? 'bg-amber-400 border-amber-400 text-slate-900'
                  : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-amber-300 hover:bg-amber-50'
              )}>
              {name}
            </button>
          ))}
        </div>
      </div>

      <ModelSection title={t('settings.extractionModel') as string} icon={Cpu} value={config.llms.extraction_model} onChange={patchModel('extraction_model')} />
      <ModelSection title={t('settings.embeddingModel') as string} icon={Search} value={config.llms.embedding_model} onChange={patchModel('embedding_model')} />
      <ModelSection title={t('settings.chatModel') as string} icon={Eye} value={config.llms.chat_model} onChange={patchModel('chat_model')} />

      {/* Search */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-800">{t('settings.searchSection') as string}</h3>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t('settings.topK') as string}>
            <input type="number" value={config.search_settings.top_k} className={inputCls()}
              onChange={e => setConfig(c => c ? { ...c, search_settings: { ...c.search_settings, top_k: Number(e.target.value) } } : c)} />
          </Field>
          <Field label={t('settings.maxPages') as string}>
            <input type="number" value={config.search_settings.max_pages_to_analyze} className={inputCls()}
              onChange={e => setConfig(c => c ? { ...c, search_settings: { ...c.search_settings, max_pages_to_analyze: Number(e.target.value) } } : c)} />
          </Field>
        </div>
      </div>

      {/* OCR */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 space-y-3">
        <h3 className="text-sm font-semibold text-slate-800">{t('settings.ocrSection') as string}</h3>
        <label className="flex items-center gap-3 cursor-pointer group">
          <div className={cn(
            'w-10 h-6 rounded-full transition-colors relative',
            config.ocr.enabled ? 'bg-amber-400' : 'bg-slate-200'
          )}>
            <div className={cn(
              'absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform',
              config.ocr.enabled ? 'translate-x-5' : 'translate-x-1'
            )} />
            <input type="checkbox" className="sr-only" checked={config.ocr.enabled}
              onChange={e => setConfig(c => c ? { ...c, ocr: { ...c.ocr, enabled: e.target.checked } } : c)} />
          </div>
          <span className="text-sm text-slate-700">{t('settings.ocrEnable') as string}</span>
        </label>
        {config.ocr.enabled && (
          <div className="ml-13 pl-1">
            <Field label={t('settings.minChars') as string}>
              <input type="number" value={config.ocr.min_chars_threshold} className={cn(inputCls(), 'max-w-32')}
                onChange={e => setConfig(c => c ? { ...c, ocr: { ...c.ocr, min_chars_threshold: Number(e.target.value) } } : c)} />
            </Field>
          </div>
        )}
      </div>

      {/* Save */}
      <div className="flex items-center gap-3 pt-2">
        <button onClick={handleSave} disabled={status === 'saving'}
          className="flex items-center gap-2 px-5 py-2.5 bg-amber-400 hover:bg-amber-500 disabled:opacity-50 rounded-xl text-sm font-semibold text-slate-900 transition-colors shadow-sm">
          <Save className="w-3.5 h-3.5" />
          {status === 'saving' ? t('settings.saving') as string : t('settings.save') as string}
        </button>
        {status === 'ok' && (
          <span className="text-sm text-emerald-600 flex items-center gap-1.5">
            <CheckCircle className="w-4 h-4" /> {t('settings.saved') as string}
          </span>
        )}
        {status === 'error' && (
          <span className="text-sm text-red-500 flex items-center gap-1.5">
            <AlertCircle className="w-4 h-4" /> {errorMsg || t('settings.saveFailed') as string}
          </span>
        )}
      </div>
    </div>
  )
}
