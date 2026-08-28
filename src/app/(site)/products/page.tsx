import Link from 'next/link'
import { cookies } from 'next/headers'
import { Prisma } from '@prisma/client'
import { prisma } from '@/lib/db'
import type { Lang } from '@/lib/i18n'
import ProductCard from '@/components/ProductCard'

export default async function ProductsPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string; search?: string }>
}) {
  const sp = await searchParams
  const cookieStore = await cookies()
  const lang: Lang = cookieStore.get('lang')?.value === 'en' ? 'en' : 'zh'

  const categories = await prisma.category.findMany({ orderBy: { sortOrder: 'asc' } })

  const where: Prisma.ProductWhereInput = {}
  if (sp.category) where.category = { slug: sp.category }
  if (sp.search) {
    where.OR = [
      { sku: { contains: sp.search } },
      { pn: { contains: sp.search } },
      { partName: { contains: sp.search } },
      { partNameEn: { contains: sp.search } },
    ]
  }

  const products = await prisma.product.findMany({
    where,
    include: { category: true, images: true },
    orderBy: { createdAt: 'desc' },
  })

  const title = lang === 'en' ? 'Products' : '产品中心'
  const all = lang === 'en' ? 'All' : '全部'
  const searchPlaceholder = lang === 'en' ? 'Search SKU / P/N...' : '搜索产品编号 SKU / P/N...'
  const searchBtn = lang === 'en' ? 'Search' : '搜索'
  const empty = lang === 'en' ? 'No products found' : '暂无匹配产品'

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-2xl font-bold text-dark md:text-3xl">{title}</h1>

      <div className="mt-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-2">
          <Link
            href="/products"
            className={`rounded-full px-3 py-1.5 text-sm ${
              !sp.category ? 'bg-primary text-white' : 'bg-gray-100 text-dark hover:bg-gray-200'
            }`}
          >
            {all}
          </Link>
          {categories.map((c) => {
            const active = sp.category === c.slug
            return (
              <Link
                key={c.id}
                href={`/products?category=${c.slug}`}
                className={`rounded-full px-3 py-1.5 text-sm ${
                  active ? 'bg-primary text-white' : 'bg-gray-100 text-dark hover:bg-gray-200'
                }`}
              >
                {lang === 'en' ? c.nameEn : c.name}
              </Link>
            )
          })}
        </div>

        <form action="/products" method="get" className="flex gap-2">
          {sp.category && <input type="hidden" name="category" value={sp.category} />}
          <input
            type="text"
            name="search"
            defaultValue={sp.search || ''}
            placeholder={searchPlaceholder}
            className="w-full rounded border border-gray-200 px-3 py-2 text-sm outline-none focus:border-primary lg:w-56"
          />
          <button
            type="submit"
            className="rounded bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark"
          >
            {searchBtn}
          </button>
        </form>
      </div>

      {products.length === 0 ? (
        <div className="mt-12 py-20 text-center text-gray-400">{empty}</div>
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {products.map((p) => (
            <ProductCard key={p.id} product={p} lang={lang} />
          ))}
        </div>
      )}
    </div>
  )
}
