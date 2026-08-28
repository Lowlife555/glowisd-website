import Link from 'next/link'
import { notFound } from 'next/navigation'
import { cookies } from 'next/headers'
import { prisma } from '@/lib/db'
import type { Lang } from '@/lib/i18n'
import ProductCard from '@/components/ProductCard'

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const cookieStore = await cookies()
  const lang: Lang = cookieStore.get('lang')?.value === 'en' ? 'en' : 'zh'

  const productId = Number(id)
  if (Number.isNaN(productId)) notFound()

  const product = await prisma.product.findUnique({
    where: { id: productId },
    include: { category: true, images: true },
  })
  if (!product) notFound()

  const related = await prisma.product.findMany({
    where: { categoryId: product.categoryId, id: { not: product.id } },
    include: { category: true, images: true },
    take: 4,
  })

  const name =
    lang === 'en'
      ? product.partNameEn || product.partName
      : product.partName || product.partNameEn
  const displayName = name || (lang === 'en' ? 'Product Name TBD' : '产品名称待更新')
  const catName = lang === 'en' ? product.category.nameEn : product.category.name

  const labels = {
    home: lang === 'en' ? 'Home' : '首页',
    products: lang === 'en' ? 'Products' : '产品中心',
    brand: lang === 'en' ? 'Compatible Brand' : '兼容品牌',
    weight: lang === 'en' ? 'Weight' : '重量',
    warranty: lang === 'en' ? 'Warranty' : '质保',
    description: lang === 'en' ? 'Description' : '产品描述',
    category: lang === 'en' ? 'Category' : '分类',
    inquire: lang === 'en' ? 'Send Inquiry' : '发送询价',
    related: lang === 'en' ? 'Related Products' : '相关产品',
  }

  const description = lang === 'en' ? product.descriptionEn : product.description
  const primaryImage = product.images.find((i) => i.isPrimary) || product.images[0]

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <nav className="text-sm text-gray-500">
        <Link href="/" className="hover:text-primary">
          {labels.home}
        </Link>
        {' / '}
        <Link href="/products" className="hover:text-primary">
          {labels.products}
        </Link>
        {' / '}
        <span className="text-dark">{displayName}</span>
      </nav>

      <div className="mt-6 grid gap-10 md:grid-cols-2">
        <div className="flex aspect-square items-center justify-center rounded-lg bg-gray-100 text-gray-300">
          {primaryImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={primaryImage.url}
              alt={displayName}
              className="h-full w-full rounded-lg object-cover"
            />
          ) : (
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none">
              <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.5" />
              <circle cx="9" cy="9" r="2" stroke="currentColor" strokeWidth="1.5" />
              <path d="M21 15l-5-5L5 21" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          )}
        </div>

        <div>
          <h1 className="text-2xl font-bold text-dark">{displayName}</h1>
          <div className="mt-4 space-y-2 text-sm">
            <p>
              <span className="text-gray-500">SKU: </span>
              <span className="font-medium text-dark">{product.sku}</span>
            </p>
            {product.pn && (
              <p>
                <span className="text-gray-500">P/N: </span>
                <span className="font-medium text-dark">{product.pn}</span>
              </p>
            )}
            {product.brand && (
              <p>
                <span className="text-gray-500">{labels.brand}: </span>
                {product.brand}
              </p>
            )}
            {product.weight && (
              <p>
                <span className="text-gray-500">{labels.weight}: </span>
                {product.weight}
              </p>
            )}
            {product.warranty && (
              <p>
                <span className="text-gray-500">{labels.warranty}: </span>
                {product.warranty}
              </p>
            )}
            <p>
              <span className="text-gray-500">{labels.category}: </span>
              {catName}
            </p>
          </div>

          {description && (
            <p className="mt-4 leading-relaxed text-gray-600">{description}</p>
          )}

          <Link
            href={`/contact?product=${product.sku}`}
            className="mt-6 inline-block rounded bg-primary px-6 py-3 font-medium text-white transition-colors hover:bg-primary-dark"
          >
            {labels.inquire}
          </Link>
        </div>
      </div>

      {related.length > 0 && (
        <div className="mt-16">
          <h2 className="text-xl font-bold text-dark">{labels.related}</h2>
          <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {related.map((p) => (
              <ProductCard key={p.id} product={p} lang={lang} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
