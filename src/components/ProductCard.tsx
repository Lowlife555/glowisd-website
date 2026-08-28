import Link from 'next/link'
import type { Product, Category, Image } from '@prisma/client'
import type { Lang } from '@/lib/i18n'

type ProductWithCategory = Product & { category: Category; images: Image[] }

export default function ProductCard({
  product,
  lang,
}: {
  product: ProductWithCategory
  lang: Lang
}) {
  const name =
    lang === 'en'
      ? product.partNameEn || product.partName
      : product.partName || product.partNameEn
  const displayName = name || (lang === 'en' ? 'Product Name TBD' : '产品名称待更新')
  const primaryImage = product.images.find((i) => i.isPrimary) || product.images[0]
  const viewDetails = lang === 'en' ? 'View Details' : '查看详情'

  return (
    <Link
      href={`/products/${product.id}`}
      className="group overflow-hidden rounded-lg border border-gray-100 bg-white shadow-sm transition-all hover:-translate-y-1 hover:border-primary hover:shadow-md"
    >
      <div className="aspect-[4/3] w-full overflow-hidden bg-gray-100">
        {primaryImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={primaryImage.url}
            alt={displayName}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-gray-300">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none">
              <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.5" />
              <circle cx="9" cy="9" r="2" stroke="currentColor" strokeWidth="1.5" />
              <path d="M21 15l-5-5L5 21" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          </div>
        )}
      </div>
      <div className="p-4">
        <div className="truncate font-semibold text-dark">{displayName}</div>
        <div className="mt-1 text-xs text-gray-500">SKU: {product.sku}</div>
        {product.pn && <div className="text-xs text-gray-500">P/N: {product.pn}</div>}
        <div className="mt-3 text-sm font-medium text-primary group-hover:underline">
          {viewDetails}
        </div>
      </div>
    </Link>
  )
}
