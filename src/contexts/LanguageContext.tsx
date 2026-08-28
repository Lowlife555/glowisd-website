'use client'

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { t as translate, type Lang } from '@/lib/i18n'

interface LanguageContextValue {
  lang: Lang
  toggle: () => void
  t: (key: string) => string
}

const LanguageContext = createContext<LanguageContextValue>({
  lang: 'zh',
  toggle: () => {},
  t: (key: string) => key,
})

export function LanguageProvider({
  children,
  initialLang,
}: {
  children: ReactNode
  initialLang: Lang
}) {
  const [lang, setLang] = useState<Lang>(initialLang)

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const toggle = () => {
    const next: Lang = lang === 'zh' ? 'en' : 'zh'
    document.cookie = `lang=${next}; path=/; max-age=31536000; samesite=lax`
    window.location.reload()
  }

  const t = (key: string) => translate(key, lang)

  return (
    <LanguageContext.Provider value={{ lang, toggle, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  return useContext(LanguageContext)
}
