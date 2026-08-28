import { NextResponse } from 'next/server'
import { z } from 'zod'
import { Prisma } from '@prisma/client'
import { prisma } from '@/lib/db'
import { requireAdmin, unauthorized } from '@/lib/admin'

const productSchema = z.object({
  sku: z.string().trim().min(1, 'SKU 必填').max(100),
  partName: z.string().trim().max(200).nullish(),
  partNameEn: z.string().trim().max(200).nullish(),
  pn: z.string().trim().max(200).nullish(),
  brand: z.string().trim().max(100).nullish(),
  weight: z.string().trim().max(100).nullish(),
  warranty: z.string().trim().max(100).nullish(),
  description: z.string().trim().max(5000).nullish(),
  descriptionEn: z.string().trim().max(5000).nullish(),
  categoryId: z.coerce.number().int().positive(),
  featured: z.boolean().default(false),
  imageUrl: z.string().trim().max(1000).nullish(),
})

function parseImageUrl(
  v: string | null | undefined,
): { ok: true; url: string | null } | { ok: false } {
  const s = (v ?? '').trim()
  if (!s) return { ok: true, url: null }
  try {
    new URL(s)
  } catch {
    return { ok: false }
  }
  return { ok: true, url: s }
}

const PAGE_SIZE = 20

export async function GET(request: Request) {
  const session = await requireAdmin()
  if (!session) return unauthorized()

  const url = new URL(request.url)
  const q = url.searchParams.get('search')?.trim() || ''
  const page = Math.max(1, Number(url.searchParams.get('page')) || 1)

  const where: Prisma.ProductWhereInput = {}
  if (q) {
    where.OR = [
      { sku: { contains: q } },
      { partName: { contains: q } },
      { partNameEn: { contains: q } },
      { pn: { contains: q } },
      { brand: { contains: q } },
    ]
  }

  const [items, total, categories] = await Promise.all([
    prisma.product.findMany({
      where,
      include: { category: true, images: true },
      orderBy: { createdAt: 'desc' },
      skip: (page - 1) * PAGE_SIZE,
      take: PAGE_SIZE,
    }),
    prisma.product.count({ where }),
    prisma.category.findMany({ orderBy: { sortOrder: 'asc' } }),
  ])

  return NextResponse.json({ items, total, page, pageSize: PAGE_SIZE, categories })
}

export async function POST(request: Request) {
  const session = await requireAdmin()
  if (!session) return unauthorized()

  let body: unknown
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: '无效的 JSON' }, { status: 400 })
  }

  const parsed = productSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json(
      { error: '输入不合法', details: parsed.error.flatten().fieldErrors },
      { status: 400 },
    )
  }
  const data = parsed.data

  const cat = await prisma.category.findUnique({ where: { id: data.categoryId } })
  if (!cat) {
    return NextResponse.json({ error: '分类不存在' }, { status: 400 })
  }

  const image = parseImageUrl(data.imageUrl)
  if (!image.ok) {
    return NextResponse.json({ error: '图片 URL 不合法' }, { status: 400 })
  }

  try {
    const product = await prisma.$transaction(async (tx) => {
      const created = await tx.product.create({
        data: {
          sku: data.sku,
          partName: data.partName ?? null,
          partNameEn: data.partNameEn ?? null,
          pn: data.pn ?? null,
          brand: data.brand ?? null,
          weight: data.weight ?? null,
          warranty: data.warranty ?? null,
          description: data.description ?? null,
          descriptionEn: data.descriptionEn ?? null,
          categoryId: data.categoryId,
          featured: data.featured,
        },
      })
      if (image.url) {
        await tx.image.create({
          data: { url: image.url, productId: created.id, isPrimary: true, sortOrder: 0 },
        })
      }
      return created
    })
    return NextResponse.json(product, { status: 201 })
  } catch (e) {
    if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2002') {
      return NextResponse.json({ error: 'SKU 已存在' }, { status: 409 })
    }
    throw e
  }
}
