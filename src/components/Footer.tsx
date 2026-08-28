'use client'

import Link from 'next/link'
import { useLanguage } from '@/contexts/LanguageContext'

export default function Footer() {
  const { t } = useLanguage()

  return (
    <footer className="bg-dark text-white">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 md:grid-cols-3">
        <div>
          <div className="text-xl font-bold text-primary">Glowisd</div>
          <p className="mt-3 text-sm text-gray-300">{t('footer.tagline')}</p>
        </div>
        <div>
          <div className="font-medium text-white">{t('footer.quickLinks')}</div>
          <div className="mt-3 flex flex-col gap-2 text-sm text-gray-300">
            <Link href="/" className="hover:text-primary">
              {t('nav.home')}
            </Link>
            <Link href="/products" className="hover:text-primary">
              {t('nav.products')}
            </Link>
            <Link href="/about" className="hover:text-primary">
              {t('nav.about')}
            </Link>
            <Link href="/contact" className="hover:text-primary">
              {t('nav.contact')}
            </Link>
          </div>
        </div>
        <div>
          <div className="font-medium text-white">{t('footer.contactUs')}</div>
          <div className="mt-3 space-y-1 text-sm text-gray-300">
            <p>Email: placeholder@glowisd.com</p>
            <p>Tel: +86-xxx-xxxx-xxxx</p>
            <p>Addr: 中国 · 常州</p>
            <p>Mon–Fri 9:00–18:00</p>
          </div>
        </div>
      </div>
      <div className="border-t border-gray-700 py-4 text-center text-xs text-gray-400">
        {t('footer.rights')}
      </div>
    </footer>
  )
}
