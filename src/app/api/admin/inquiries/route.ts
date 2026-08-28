import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { requireAdmin, unauthorized } from '@/lib/admin'

const PAGE_SIZE = 20

export async function GET(request: Request) {
  const session = await requireAdmin()
  if (!session) return unauthorized()

  const url = new URL(request.url)
  const page = Math.max(1, Number(url.searchParams.get('page')) || 1)

  const [items, total, unread] = await Promise.all([
    prisma.contactMessage.findMany({
      orderBy: { createdAt: 'desc' },
      skip: (page - 1) * PAGE_SIZE,
      take: PAGE_SIZE,
    }),
    prisma.contactMessage.count(),
    prisma.contactMessage.count({ where: { isRead: false } }),
  ])

  return NextResponse.json({ items, total, unread, page, pageSize: PAGE_SIZE })
}
