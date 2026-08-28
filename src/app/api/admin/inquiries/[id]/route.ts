import { NextResponse } from 'next/server'
import { z } from 'zod'
import { Prisma } from '@prisma/client'
import { prisma } from '@/lib/db'
import { requireAdmin, unauthorized } from '@/lib/admin'

const updateSchema = z.object({
  isRead: z.boolean(),
})

async function parseId(raw: string): Promise<number | null> {
  const id = Number(raw)
  return Number.isInteger(id) && id > 0 ? id : null
}

export async function PUT(request: Request, context: { params: Promise<{ id: string }> }) {
  const session = await requireAdmin()
  if (!session) return unauthorized()

  const { id: rawId } = await context.params
  const inquiryId = await parseId(rawId)
  if (!inquiryId) {
    return NextResponse.json({ error: '无效的 ID' }, { status: 400 })
  }

  let body: unknown
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: '无效的 JSON' }, { status: 400 })
  }

  const parsed = updateSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json({ error: '输入不合法' }, { status: 400 })
  }

  try {
    const updated = await prisma.contactMessage.update({
      where: { id: inquiryId },
      data: { isRead: parsed.data.isRead },
    })
    return NextResponse.json(updated)
  } catch (e) {
    if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2025') {
      return NextResponse.json({ error: '询价记录不存在' }, { status: 404 })
    }
    throw e
  }
}

export async function DELETE(request: Request, context: { params: Promise<{ id: string }> }) {
  const session = await requireAdmin()
  if (!session) return unauthorized()

  const { id: rawId } = await context.params
  const inquiryId = await parseId(rawId)
  if (!inquiryId) {
    return NextResponse.json({ error: '无效的 ID' }, { status: 400 })
  }

  try {
    await prisma.contactMessage.delete({ where: { id: inquiryId } })
    return NextResponse.json({ ok: true })
  } catch (e) {
    if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2025') {
      return NextResponse.json({ error: '询价记录不存在' }, { status: 404 })
    }
    throw e
  }
}
