import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { requireAdmin, unauthorized } from '@/lib/admin'

export async function GET() {
  const session = await requireAdmin()
  if (!session) return unauthorized()

  const [productCount, unreadCount, recentInquiries] = await Promise.all([
    prisma.product.count(),
    prisma.contactMessage.count({ where: { isRead: false } }),
    prisma.contactMessage.findMany({
      orderBy: { createdAt: 'desc' },
      take: 5,
    }),
  ])

  return NextResponse.json({ productCount, unreadCount, recentInquiries })
}
