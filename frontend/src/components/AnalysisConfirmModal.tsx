import { useState } from 'react'
import { createPortal } from 'react-dom'
import { X, ChevronDown, ChevronUp, Sparkles, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/LangContext'

export interface AnalysisOptions {
  language: string
  extra_prompt: string
  analysis_model: {
    model_name: string
    base_url: string
    api_key: string
    temperature: number
    max_tokens: number
  } | null
  page_start: number | null
  page_end: number | null
  mode: 'full' | 'quick'
}

interface Props {
  bookTitle: string
  isReanalyze?: boolean
  onConfirm: (opts: AnalysisOptions) => void
  onCancel: () => void
}

const defaultOpts = (): AnalysisOptions => ({
  language: '',
  extra_prompt: '',
  analysis_model: null,
  page_start: null,
  page_end: null,
  mode: 'full',
})

export function AnalysisConfirmModal({ bookTitle, isReanalyze = false, onConfirm, onCancel }: Props) {
  const { t } = useLang()
  const [opts, setOpts] = useState<AnalysisOptions>(defaultOpts)
  const [showOptions, setShowOptions] = useState(false)
  const [useCustomModel, setUseCustomModel] = useState(false)
  const [confirming, setConfirming] = useState(false)

  const setOpt = <K extends keyof AnalysisOptions>(key: K, value: AnalysisOptions[K]) => {
    setOpts(prev => ({ ...prev, [key]: value }))
  }

  const setModelField = (field: string, value: string | number) => {
    setOpts(prev => ({
      ...prev,
      analysis_model: {
        model_name: '',
        base_url: '',
        api_key: '',
        temperature: 0.1,
        max_tokens: 4096,
        ...(prev.analysis_model ?? {}),
        [field]: value,
      },
    }))
  }

  const handleConfirm = () => {
    setConfirming(true)
    const finalOpts: AnalysisOptions = {
      ...opts,
      analysis_model: useCustomModel ? opts.analysis_model : null,
    }
    onConfirm(finalOpts)
  }

  return createPortal(
    <>
      <div className="fixed inset-0 z-[300] bg-black/50 backdrop-blur-sm" onClick={onCancel} />
      <div className="fixed inset-0 z-[301] flex items-center justify-center p-4 pointer-events-none">
        <div
          className="pointer-events-auto bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col overflow-hidden"
          onClick={e => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-start gap-3 p-5 pb-3">
            <div className="w-9 h-9 rounded-xl bg-violet-100 flex items-center justify-center shrink-0">
              <Sparkles className="w-4.5 h-4.5 text-violet-600" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-slate-900 text-[0.95rem]">
                {isReanalyze
                  ? t('analysis.confirmReanalyzeTitle') as string
                  : t('analysis.confirmTitle') as string}
              </p>
              <p className="text-sm text-slate-500 mt-0.5 truncate">{bookTitle}</p>
            </div>
            <button
              onClick={onCancel}
              className="shrink-0 w-7 h-7 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-400 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {isReanalyze && (
            <div className="mx-5 mb-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700">
              {t('analysis.confirmReanalyzeWarning') as string}
            </div>
          )}

          {/* Options toggle */}
          <button
            onClick={() => setShowOptions(v => !v)}
            className="mx-5 mb-3 flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 transition-colors"
          >
            {showOptions ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            {t('analysis.optionsToggle') as string}
          </button>

          {/* Options panel */}
          {showOptions && (
            <div className="mx-5 mb-4 space-y-4 border border-slate-100 rounded-xl p-4 bg-slate-50">

              {/* Language */}
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  {t('analysis.optLanguage') as string}
                </label>
                <input
                  type="text"
                  value={opts.language}
                  onChange={e => setOpt('language', e.target.value)}
                  placeholder={t('analysis.optLanguagePlaceholder') as string}
                  className="w-full text-sm px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-300 bg-white"
                />
              </div>

              {/* Extra prompt */}
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  {t('analysis.optExtraPrompt') as string}
                </label>
                <textarea
                  value={opts.extra_prompt}
                  onChange={e => setOpt('extra_prompt', e.target.value)}
                  placeholder={t('analysis.optExtraPromptPlaceholder') as string}
                  rows={2}
                  className="w-full text-sm px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-300 bg-white resize-none"
                />
              </div>

              {/* Page range */}
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  {t('analysis.optPageRange') as string}
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={1}
                    value={opts.page_start !== null ? opts.page_start + 1 : ''}
                    onChange={e => setOpt('page_start', e.target.value ? parseInt(e.target.value) - 1 : null)}
                    placeholder={t('analysis.optPageFrom') as string}
                    className="w-24 text-sm px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-300 bg-white"
                  />
                  <span className="text-slate-400 text-sm">–</span>
                  <input
                    type="number"
                    min={1}
                    value={opts.page_end ?? ''}
                    onChange={e => setOpt('page_end', e.target.value ? parseInt(e.target.value) : null)}
                    placeholder={t('analysis.optPageTo') as string}
                    className="w-24 text-sm px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-300 bg-white"
                  />
                </div>
                <p className="text-xs text-slate-400 mt-1">{t('analysis.optPageRangeHint') as string}</p>
              </div>

              {/* Mode */}
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1.5">
                  {t('analysis.optMode') as string}
                </label>
                <div className="flex gap-2">
                  {(['full', 'quick'] as const).map(m => (
                    <button
                      key={m}
                      onClick={() => setOpt('mode', m)}
                      className={cn(
                        'px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors',
                        opts.mode === m
                          ? 'bg-violet-600 text-white border-violet-600'
                          : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                      )}
                    >
                      {t(`analysis.optMode${m.charAt(0).toUpperCase() + m.slice(1)}` as Parameters<typeof t>[0]) as string}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  {opts.mode === 'quick'
                    ? t('analysis.optModeQuickHint') as string
                    : t('analysis.optModeFullHint') as string}
                </p>
              </div>

              {/* Custom model toggle */}
              <div>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={useCustomModel}
                    onChange={e => setUseCustomModel(e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-xs font-medium text-slate-600">
                    {t('analysis.optCustomModel') as string}
                  </span>
                </label>
              </div>

              {/* Custom model fields */}
              {useCustomModel && (
                <div className="space-y-2 pl-4 border-l-2 border-violet-100">
                  {[
                    { field: 'model_name', label: t('settings.modelName') as string, placeholder: 'e.g. gpt-4o' },
                    { field: 'base_url', label: t('settings.baseUrl') as string, placeholder: 'https://api.openai.com/v1' },
                    { field: 'api_key', label: t('settings.apiKey') as string, placeholder: 'sk-…', type: 'password' },
                  ].map(({ field, label, placeholder, type }) => (
                    <div key={field}>
                      <label className="block text-xs text-slate-500 mb-0.5">{label}</label>
                      <input
                        type={type ?? 'text'}
                        value={(opts.analysis_model as Record<string, string> | null)?.[field] ?? ''}
                        onChange={e => setModelField(field, e.target.value)}
                        placeholder={placeholder}
                        className="w-full text-xs px-2.5 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-300 bg-white"
                      />
                    </div>
                  ))}
                  <div className="flex gap-2">
                    <div className="flex-1">
                      <label className="block text-xs text-slate-500 mb-0.5">{t('settings.temperature') as string}</label>
                      <input
                        type="number"
                        step="0.1" min="0" max="2"
                        value={opts.analysis_model?.temperature ?? 0.1}
                        onChange={e => setModelField('temperature', parseFloat(e.target.value))}
                        className="w-full text-xs px-2.5 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-300 bg-white"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="block text-xs text-slate-500 mb-0.5">{t('settings.maxTokens') as string}</label>
                      <input
                        type="number"
                        step="512" min="256"
                        value={opts.analysis_model?.max_tokens ?? 4096}
                        onChange={e => setModelField('max_tokens', parseInt(e.target.value))}
                        className="w-full text-xs px-2.5 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-300 bg-white"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="px-5 pb-5 flex items-center justify-end gap-2">
            <button
              onClick={onCancel}
              className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 border border-slate-200 rounded-xl transition-colors"
            >
              {t('remove.cancel') as string}
            </button>
            <button
              onClick={handleConfirm}
              disabled={confirming}
              className="flex items-center gap-1.5 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold rounded-xl transition-colors disabled:opacity-60"
            >
              {confirming
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <Sparkles className="w-4 h-4" />}
              {isReanalyze
                ? t('analysis.reanalyze') as string
                : t('analysis.deepAnalysis') as string}
            </button>
          </div>
        </div>
      </div>
    </>,
    document.body
  )
}
