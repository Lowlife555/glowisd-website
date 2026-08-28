import zh from '@/locales/zh.json'
import en from '@/locales/en.json'

export type Lang = 'zh' | 'en'

export function getTranslations(lang: Lang) {
  return lang === 'en' ? en : zh
}

export function t(key: string, lang: Lang): string {
  const dict = getTranslations(lang) as Record<string, unknown>
  let cur: unknown = dict
  for (const part of key.split('.')) {
    if (cur && typeof cur === 'object') {
      cur = (cur as Record<string, unknown>)[part]
    } else {
      return key
    }
  }
  return typeof cur === 'string' ? cur : key
}
