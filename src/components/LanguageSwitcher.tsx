'use client'

import { useLanguage } from '@/contexts/LanguageContext'

export default function LanguageSwitcher() {
  const { lang, toggle } = useLanguage()

  const base = 'rounded px-2 py-1 text-xs font-medium transition-colors'

  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => lang !== 'en' && toggle()}
        className={`${base} ${
          lang === 'en' ? 'bg-primary text-white' : 'text-dark hover:bg-gray-100'
        }`}
      >
        EN
      </button>
      <button
        type="button"
        onClick={() => lang !== 'zh' && toggle()}
        className={`${base} ${
          lang === 'zh' ? 'bg-primary text-white' : 'text-dark hover:bg-gray-100'
        }`}
      >
        中
      </button>
    </div>
  )
}
