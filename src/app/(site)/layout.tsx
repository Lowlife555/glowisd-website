import { headers } from 'next/headers'
import Header from '@/components/Header'
import Footer from '@/components/Footer'
import { LanguageProvider } from '@/contexts/LanguageContext'
import type { Lang } from '@/lib/i18n'

function parseCookies(cookieHeader: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const part of cookieHeader.split(';')) {
    const idx = part.indexOf('=')
    if (idx > -1) {
      out[part.slice(0, idx).trim()] = part.slice(idx + 1).trim()
    }
  }
  return out
}

export default async function SiteLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const h = await headers()
  const cookies = parseCookies(h.get('cookie') || '')
  const acceptLanguage = (h.get('accept-language') || '').toLowerCase()

  let initialLang: Lang = 'zh'
  if (cookies.lang === 'en' || cookies.lang === 'zh') {
    initialLang = cookies.lang
  } else if (acceptLanguage && !acceptLanguage.includes('zh')) {
    initialLang = 'en'
  }

  return (
    <LanguageProvider initialLang={initialLang}>
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex-1 pt-16">{children}</main>
        <Footer />
      </div>
    </LanguageProvider>
  )
}
