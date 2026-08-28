'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { signOut } from 'next-auth/react'

const nav = [
  { href: '/admin', label: '仪表盘' },
  { href: '/admin/products', label: '产品管理' },
  { href: '/admin/inquiries', label: '询价管理' },
]

export default function Sidebar() {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)

  const isActive = (href: string) =>
    href === '/admin' ? pathname === '/admin' : pathname.startsWith(href)

  const navList = (
    <nav aria-label="后台导航" className="flex flex-1 flex-col gap-1 px-3 py-4">
      {nav.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          onClick={() => setOpen(false)}
          className={`flex min-h-11 items-center rounded-md px-4 text-base font-medium transition-colors ${
            isActive(item.href)
              ? 'bg-primary text-white'
              : 'text-gray-600 hover:bg-gray-100 hover:text-primary'
          }`}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  )

  const footer = (
    <div className="border-t border-gray-200 p-3">
      <button
        type="button"
        onClick={() => signOut({ callbackUrl: '/admin/login' })}
        className="flex min-h-11 w-full items-center justify-center rounded-md border border-gray-200 text-base font-medium text-gray-600 transition-colors hover:bg-gray-100 hover:text-red-600"
      >
        退出登录
      </button>
    </div>
  )

  return (
    <>
      {/* 移动端顶栏（含汉堡按钮） */}
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4 lg:hidden">
        <button
          type="button"
          aria-label="打开菜单"
          aria-expanded={open}
          onClick={() => setOpen(true)}
          className="flex h-11 w-11 items-center justify-center rounded-md text-gray-600 hover:bg-gray-100"
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <span className="text-base font-semibold text-dark">Glowisd 后台</span>
        <span className="w-11" aria-hidden="true" />
      </header>

      {/* 移动端抽屉（默认收起） */}
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col bg-white shadow-xl">
            <div className="flex h-14 items-center justify-between border-b border-gray-200 px-4">
              <span className="text-base font-semibold text-dark">Glowisd 后台</span>
              <button
                type="button"
                aria-label="关闭菜单"
                onClick={() => setOpen(false)}
                className="flex h-11 w-11 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100"
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                >
                  <path d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            </div>
            {navList}
            {footer}
          </aside>
        </div>
      )}

      {/* 桌面端固定侧边栏 */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-gray-200 bg-white lg:sticky lg:top-0 lg:flex lg:h-screen">
        <div className="flex h-14 items-center border-b border-gray-200 px-4 text-base font-semibold text-dark">
          Glowisd 后台
        </div>
        {navList}
        {footer}
      </aside>
    </>
  )
}
