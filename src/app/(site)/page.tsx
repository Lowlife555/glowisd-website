'use client'

import Link from 'next/link'
import { useLanguage } from '@/contexts/LanguageContext'
import type { Lang } from '@/lib/i18n'

const content: Record<
  Lang,
  {
    heroTitle: string
    heroSub: string
    viewProducts: string
    contactUs: string
    categoriesTitle: string
    categories: { slug: string; name: string; desc: string }[]
    whyTitle: string
    why: { name: string; desc: string }[]
    aboutTitle: string
    aboutText: string
    learnMore: string
    factoryPlaceholder: string
  }
> = {
  zh: {
    heroTitle: '专业摊铺机传感器与配件制造',
    heroSub: '为 Vogele、Bomag、Wirtgen 等国际品牌提供高品质替代配件',
    viewProducts: '查看产品',
    contactUs: '联系我们',
    categoriesTitle: '产品分类',
    categories: [
      { slug: 'sensors', name: '传感器', desc: '精确测量，稳定可靠' },
      { slug: 'cables', name: '线缆', desc: '耐用连接，信号稳定' },
      { slug: 'control-handles', name: '控制手柄', desc: '操控精准，手感舒适' },
      { slug: 'displays', name: '显示控制器', desc: '清晰显示，智能监控' },
      { slug: 'junction-boxes', name: '接线盒', desc: '安全防护，稳定连接' },
      { slug: 'complete-kits', name: '套件', desc: '一站式配套方案' },
    ],
    whyTitle: '为什么选择 Glowisd',
    why: [
      { name: '品质保证', desc: '严格质量控制体系' },
      { name: '兼容性强', desc: '适配主流摊铺机品牌' },
      { name: '快速交付', desc: '全球物流网络' },
      { name: '专业服务', desc: '专业技术支持团队' },
    ],
    aboutTitle: '关于 Glowisd',
    aboutText:
      'Glowisd 专注摊铺机传感器、线缆及配件的研发与制造，产品广泛兼容 Vogele、Bomag、Wirtgen 等国际主流品牌，远销中东、欧洲及中国市场。公司坚持品质优先，持续为客户提供稳定可靠的替代配件与专业服务。',
    learnMore: '了解更多',
    factoryPlaceholder: '工厂照片',
  },
  en: {
    heroTitle: 'Professional Paving Machine Sensors & Accessories',
    heroSub: 'High-quality replacement parts for Vogele, Bomag, Wirtgen and more',
    viewProducts: 'View Products',
    contactUs: 'Contact Us',
    categoriesTitle: 'Product Categories',
    categories: [
      { slug: 'sensors', name: 'Sensors', desc: 'Precise measurement, stable & reliable' },
      { slug: 'cables', name: 'Cables', desc: 'Durable connection, stable signal' },
      { slug: 'control-handles', name: 'Control Handles', desc: 'Precise control, comfortable grip' },
      { slug: 'displays', name: 'Displays', desc: 'Clear display, smart monitoring' },
      { slug: 'junction-boxes', name: 'Junction Boxes', desc: 'Safe protection, stable connection' },
      { slug: 'complete-kits', name: 'Complete Kits', desc: 'One-stop solution kits' },
    ],
    whyTitle: 'Why Choose Glowisd',
    why: [
      { name: 'Quality Assured', desc: 'Strict quality control system' },
      { name: 'Wide Compatibility', desc: 'Compatible with major paver brands' },
      { name: 'Fast Delivery', desc: 'Global logistics network' },
      { name: 'Professional Service', desc: 'Professional technical support' },
    ],
    aboutTitle: 'About Glowisd',
    aboutText:
      'Glowisd specializes in the R&D and manufacturing of paving machine sensors, cables and accessories. Our products are widely compatible with Vogele, Bomag, Wirtgen and other leading brands, and are exported to the Middle East, Europe and China. We put quality first and provide stable, reliable replacement parts and professional service.',
    learnMore: 'Learn More',
    factoryPlaceholder: 'Factory Photo',
  },
}

export default function HomePage() {
  const { lang } = useLanguage()
  const c = content[lang]

  return (
    <div>
      {/* Hero */}
      <section className="bg-[#1a1a1a] px-4 py-28 text-center">
        <h1 className="mx-auto max-w-3xl text-3xl font-bold leading-tight text-white md:text-5xl">
          {c.heroTitle}
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-gray-400">
          {c.heroSub}
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-4">
          <Link
            href="/products"
            className="rounded bg-primary px-6 py-3 font-medium text-white transition-colors hover:bg-primary-dark"
          >
            {c.viewProducts}
          </Link>
          <Link
            href="/contact"
            className="rounded border border-white px-6 py-3 font-medium text-white transition-colors hover:bg-white hover:text-dark"
          >
            {c.contactUs}
          </Link>
        </div>
      </section>

      {/* 分类快览 */}
      <section className="mx-auto max-w-6xl px-4 py-16">
        <h2 className="text-center text-2xl font-bold text-dark md:text-3xl">
          {c.categoriesTitle}
        </h2>
        <div className="mt-10 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {c.categories.map((cat) => (
            <Link
              key={cat.slug}
              href={`/products?category=${cat.slug}`}
              className="rounded-lg border border-gray-100 bg-white p-6 shadow-sm transition-all hover:-translate-y-1 hover:shadow-md"
            >
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-orange-100 text-xl font-bold text-primary">
                {cat.name.slice(0, 1)}
              </div>
              <div className="mt-4 font-semibold text-dark">{cat.name}</div>
              <div className="mt-1 text-sm text-gray-500">{cat.desc}</div>
            </Link>
          ))}
        </div>
      </section>

      {/* 为什么选择我们 */}
      <section className="bg-light px-4 py-16">
        <div className="mx-auto max-w-6xl">
          <h2 className="text-center text-2xl font-bold text-dark md:text-3xl">
            {c.whyTitle}
          </h2>
          <div className="mt-10 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {c.why.map((w) => (
              <div
                key={w.name}
                className="rounded-lg border-t-4 border-primary bg-white p-6 shadow-sm"
              >
                <div className="font-semibold text-dark">{w.name}</div>
                <div className="mt-2 text-sm text-gray-500">{w.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 公司简介 */}
      <section className="mx-auto max-w-6xl px-4 py-16">
        <div className="grid items-center gap-10 md:grid-cols-5">
          <div className="md:col-span-3">
            <h2 className="text-2xl font-bold text-dark md:text-3xl">
              {c.aboutTitle}
            </h2>
            <p className="mt-4 leading-relaxed text-gray-600">{c.aboutText}</p>
            <Link
              href="/about"
              className="mt-6 inline-block rounded bg-primary px-5 py-2.5 font-medium text-white transition-colors hover:bg-primary-dark"
            >
              {c.learnMore}
            </Link>
          </div>
          <div className="md:col-span-2">
            <div className="flex aspect-[4/3] items-center justify-center rounded-lg bg-gray-200 text-gray-400">
              {/* 预留：后续替换为 <img src="/images/factory/xxx.jpg" alt="Factory" /> */}
              {c.factoryPlaceholder}
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
