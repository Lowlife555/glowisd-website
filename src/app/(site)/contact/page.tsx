import { cookies } from 'next/headers'
import type { Lang } from '@/lib/i18n'
import ContactForm from '@/components/ContactForm'

export default async function ContactPage({
  searchParams,
}: {
  searchParams: Promise<{ product?: string }>
}) {
  const sp = await searchParams
  const cookieStore = await cookies()
  const lang: Lang = cookieStore.get('lang')?.value === 'en' ? 'en' : 'zh'

  const title = lang === 'en' ? 'Contact Us' : '联系我们'
  const subtitle =
    lang === 'en'
      ? 'Inquire about products or send us a quotation request'
      : '欢迎咨询产品信息或发送询价'
  const company = lang === 'en' ? 'Company' : '公司'
  const workHours = lang === 'en' ? 'Working hours' : '工作时间'

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-2xl font-bold text-dark md:text-3xl">{title}</h1>
      <p className="mt-2 text-gray-500">{subtitle}</p>

      <div className="mt-8 grid gap-10 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <ContactForm lang={lang} product={sp.product || ''} />
        </div>

        <div className="lg:col-span-2">
          <div className="rounded-lg border border-gray-100 bg-white p-6 shadow-sm">
            <div className="font-semibold text-dark">{company}: Glowisd</div>
            <div className="mt-4 space-y-2 text-sm text-gray-600">
              <p>Email: placeholder@glowisd.com</p>
              <p>Tel: +86-xxx-xxxx-xxxx</p>
              <p>Addr: 中国 · 常州</p>
              <p>
                {workHours}: {lang === 'en' ? 'Mon–Fri 9:00–18:00' : '周一至周五 9:00-18:00'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
