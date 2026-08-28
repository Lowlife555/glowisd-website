import Link from 'next/link'
import { prisma } from '@/lib/db'

export const dynamic = 'force-dynamic'

export default async function AdminDashboardPage() {
  const [productCount, unreadCount, recent] = await Promise.all([
    prisma.product.count(),
    prisma.contactMessage.count({ where: { isRead: false } }),
    prisma.contactMessage.findMany({
      orderBy: { createdAt: 'desc' },
      take: 5,
      select: {
        id: true,
        name: true,
        company: true,
        email: true,
        category: true,
        isRead: true,
        createdAt: true,
      },
    }),
  ])

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-xl font-bold text-dark sm:text-2xl">仪表盘</h1>

      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Link
          href="/admin/products"
          className="flex min-h-11 items-center justify-between rounded-lg border border-gray-200 bg-white p-5 shadow-sm transition-colors hover:border-primary"
        >
          <div>
            <div className="text-3xl font-bold text-primary">{productCount}</div>
            <div className="mt-1 text-sm text-gray-500">产品总数</div>
          </div>
          <span className="text-sm text-gray-400">管理 →</span>
        </Link>
        <Link
          href="/admin/inquiries"
          className="flex min-h-11 items-center justify-between rounded-lg border border-gray-200 bg-white p-5 shadow-sm transition-colors hover:border-primary"
        >
          <div>
            <div className="text-3xl font-bold text-primary">{unreadCount}</div>
            <div className="mt-1 text-sm text-gray-500">未读询价</div>
          </div>
          <span className="text-sm text-gray-400">处理 →</span>
        </Link>
      </div>

      <div className="mt-6 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
          <h2 className="font-semibold text-dark">最近询价</h2>
          <Link href="/admin/inquiries" className="min-h-11 py-2 text-sm text-primary hover:underline">
            查看全部
          </Link>
        </div>
        {recent.length === 0 ? (
          <div className="px-4 py-10 text-center text-gray-400">暂无询价记录</div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {recent.map((m) => (
              <li
                key={m.id}
                className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium text-dark">{m.name}</span>
                    {!m.isRead && (
                      <span className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary">
                        未读
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 truncate text-sm text-gray-500">
                    {m.company || '—'}
                    {m.email ? ` · ${m.email}` : ''}
                  </div>
                </div>
                <div className="shrink-0 text-sm text-gray-400">
                  {new Date(m.createdAt).toLocaleString('zh-CN', { hour12: false })}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
