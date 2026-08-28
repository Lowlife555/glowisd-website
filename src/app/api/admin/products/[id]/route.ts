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

async function parseId(raw: string): Promise<number | null> {
  const id = Number(raw)
  return Number.isInteger(id) && id > 0 ? id : null
}

export async function PUT(request: Request, context: { params: Promise<{ id: string }> }) {
  const session = await requireAdmin()
  if (!session) return unauthorized()

  const { id: rawId } = await context.params
  const productId = await parseId(rawId)
  if (!productId) {
    return NextResponse.json({ error: '无效的 ID' }, { status: 400 })
  }

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
    const updated = await prisma.$transaction(async (tx) => {
      const existing = await tx.product.findUnique({
        where: { id: productId },
        include: { images: true },
      })
      if (!existing) return null

      const product = await tx.product.update({
        where: { id: productId },
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

      // 提供了图片 URL 时：更新主图或新建主图
      if (image.url) {
        const primary = existing.images.find((i) => i.isPrimary) || existing.images[0]
        if (primary) {
          await tx.image.update({
            where: { id: primary.id },
            data: { url: image.url, isPrimary: true },
          })
        } else {
          await tx.image.create({
            data: { url: image.url, productId, isPrimary: true, sortOrder: 0 },
          })
        }
      }
      return product
    })

    if (!updated) {
      return NextResponse.json({ error: '产品不存在' }, { status: 404 })
    }

    const full = await prisma.product.findUnique({
      where: { id: productId },
      include: { category: true, images: true },
    })
    return NextResponse.json(full)
  } catch (e) {
    if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2002') {
      return NextResponse.json({ error: 'SKU 已存在' }, { status: 409 })
    }
    if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2025') {
      return NextResponse.json({ error: '产品不存在' }, { status: 404 })
    }
    throw e
  }
}

export async function DELETE(request: Request, context: { params: Promise<{ id: string }> }) {
  const session = await requireAdmin()
  if (!session) return unauthorized()

  const { id: rawId } = await context.params
  const productId = await parseId(rawId)
  if (!productId) {
    return NextResponse.json({ error: '无效的 ID' }, { status: 400 })
  }

  try {
    // 关联 Image 由 schema 的 onDelete: Cascade 自动清理
    await prisma.product.delete({ where: { id: productId } })
    return NextResponse.json({ ok: true })
  } catch (e) {
    if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2025') {
      return NextResponse.json({ error: '产品不存在' }, { status: 404 })
    }
    throw e
  }
}
