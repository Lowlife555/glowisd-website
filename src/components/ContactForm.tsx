'use client'

import { useState } from 'react'
import type { Lang } from '@/lib/i18n'

const texts: Record<
  Lang,
  {
    name: string
    company: string
    email: string
    phone: string
    country: string
    category: string
    message: string
    product: string
    submit: string
    sending: string
    success: string
    error: string
    countries: string[]
    categories: string[]
  }
> = {
  zh: {
    name: '姓名',
    company: '公司名称',
    email: '邮箱',
    phone: '电话',
    country: '国家/地区',
    category: '感兴趣分类',
    message: '留言',
    product: '关注产品',
    submit: '提交询价',
    sending: '提交中...',
    success: '提交成功，我们会尽快与您联系！',
    error: '提交失败，请稍后重试',
    countries: ['中国', '中东', '欧洲', '其他'],
    categories: ['传感器', '线缆', '控制手柄', '显示控制器', '接线盒', '其他'],
  },
  en: {
    name: 'Name',
    company: 'Company',
    email: 'Email',
    phone: 'Phone',
    country: 'Country / Region',
    category: 'Product Category',
    message: 'Message',
    product: 'Product of Interest',
    submit: 'Send Inquiry',
    sending: 'Sending...',
    success: 'Submitted! We will contact you soon.',
    error: 'Submission failed, please try again later',
    countries: ['China', 'Middle East', 'Europe', 'Other'],
    categories: ['Sensors', 'Cables', 'Control Handles', 'Displays', 'Junction Boxes', 'Other'],
  },
}

const inputCls =
  'w-full rounded border border-gray-200 px-3 py-2.5 text-base outline-none focus:border-primary'
const labelCls = 'mb-1 block text-sm font-medium text-dark'

export default function ContactForm({ lang, product }: { lang: Lang; product: string }) {
  const t = texts[lang]
  const [status, setStatus] = useState<'idle' | 'sending' | 'success' | 'error'>('idle')

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget
    const fd = new FormData(form)
    const data = Object.fromEntries(fd.entries())
    setStatus('sending')

    try {
      const res = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (res.ok) {
        setStatus('success')
        form.reset()
        setTimeout(() => setStatus('idle'), 3000)
      } else {
        setStatus('error')
        setTimeout(() => setStatus('idle'), 4000)
      }
    } catch {
      setStatus('error')
      setTimeout(() => setStatus('idle'), 4000)
    }
  }

  return (
    <form onSubmit={onSubmit} className="rounded-lg border border-gray-100 bg-white p-6 shadow-sm">
      {/* 蜜罐：真人看不到也不会填，机器人会填 → 后端直接丢弃 */}
      <input
        type="text"
        name="website"
        tabIndex={-1}
        autoComplete="off"
        className="absolute -left-[9999px] h-0 w-0 opacity-0"
        aria-hidden="true"
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className={labelCls}>
            {t.name} <span className="text-red-500">*</span>
          </label>
          <input name="name" required maxLength={100} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>{t.company}</label>
          <input name="company" maxLength={200} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>
            {t.email} <span className="text-red-500">*</span>
          </label>
          <input name="email" type="email" required maxLength={200} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>{t.phone}</label>
          <input name="phone" maxLength={50} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>{t.country}</label>
          <select name="country" className={inputCls} defaultValue="">
            <option value="" disabled>
              {t.country}
            </option>
            {t.countries.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>{t.category}</label>
          <select name="category" className={inputCls} defaultValue="">
            <option value="" disabled>
              {t.category}
            </option>
            {t.categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </div>

      {product && (
        <div className="mt-4">
          <label className={labelCls}>{t.product}</label>
          <input name="productSku" value={product} readOnly className={`${inputCls} bg-gray-50`} />
        </div>
      )}

      <div className="mt-4">
        <label className={labelCls}>
          {t.message} <span className="text-red-500">*</span>
        </label>
        <textarea name="message" required maxLength={2000} rows={5} className={inputCls} />
      </div>

      <button
        type="submit"
        disabled={status === 'sending'}
        className="mt-5 rounded bg-primary px-6 py-3 font-medium text-white transition-colors hover:bg-primary-dark disabled:opacity-60"
      >
        {status === 'sending' ? t.sending : t.submit}
      </button>

      {status === 'success' && (
        <p className="mt-3 rounded bg-green-50 px-3 py-2 text-sm text-green-700">{t.success}</p>
      )}
      {status === 'error' && (
        <p className="mt-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{t.error}</p>
      )}
    </form>
  )
}
