import { cookies } from 'next/headers'
import type { Lang } from '@/lib/i18n'

const content: Record<
  Lang,
  {
    title: string
    subtitle: string
    intro: string
    advantages: { name: string; desc: string }[]
    factoryPlaceholder: string
  }
> = {
  zh: {
    title: '关于 Glowisd',
    subtitle: '专注摊铺机配件，服务全球客户',
    intro:
      'CZ Glowisd Science And Technology co., ltd 是一家专业生产摊铺机传感器、线缆及配件的制造商。产品广泛兼容 Vogele、Bomag、Wirtgen 等国际主流品牌，远销中东、欧洲及中国等多个国家和地区，拥有完善的质量管理体系。',
    advantages: [
      { name: '品质至上', desc: '严格品控' },
      { name: '兼容广泛', desc: '适配多品牌' },
      { name: '全球供应', desc: '服务中东欧洲中国' },
      { name: '持续创新', desc: '不断优化产品' },
    ],
    factoryPlaceholder: '工厂照片',
  },
  en: {
    title: 'About Glowisd',
    subtitle: 'Specialized in paver parts, serving global customers',
    intro:
      'CZ Glowisd Science And Technology co., ltd is a manufacturer specialized in paving machine sensors, cables and accessories. Our products are widely compatible with Vogele, Bomag, Wirtgen and other leading brands, and are exported to the Middle East, Europe and China. We maintain a complete quality management system.',
    advantages: [
      { name: 'Quality First', desc: 'Strict quality control' },
      { name: 'Wide Compatibility', desc: 'Multi-brand compatible' },
      { name: 'Global Supply', desc: 'Serving ME, EU, CN' },
      { name: 'Continuous Innovation', desc: 'Constant improvement' },
    ],
    factoryPlaceholder: 'Factory Photo',
  },
}

export default async function AboutPage() {
  const cookieStore = await cookies()
  const lang: Lang = cookieStore.get('lang')?.value === 'en' ? 'en' : 'zh'
  const c = content[lang]

  return (
    <div>
      <section className="bg-[#1a1a1a] px-4 py-20 text-center">
        <h1 className="text-3xl font-bold text-white md:text-4xl">{c.title}</h1>
        <p className="mt-4 text-lg text-gray-400">{c.subtitle}</p>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16">
        <div className="grid items-center gap-10 md:grid-cols-5">
          <div className="md:col-span-3">
            <p className="leading-relaxed text-gray-600">{c.intro}</p>
          </div>
          <div className="md:col-span-2">
            <div className="flex aspect-[4/3] items-center justify-center rounded-lg bg-gray-200 text-gray-400">
              {/* 预留：后续替换为 <img src="/images/factory/xxx.jpg" alt="Factory" /> */}
              {c.factoryPlaceholder}
            </div>
          </div>
        </div>

        <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {c.advantages.map((a) => (
            <div key={a.name} className="rounded-lg border-t-4 border-primary bg-white p-6 shadow-sm">
              <div className="font-semibold text-dark">{a.name}</div>
              <div className="mt-2 text-sm text-gray-500">{a.desc}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
