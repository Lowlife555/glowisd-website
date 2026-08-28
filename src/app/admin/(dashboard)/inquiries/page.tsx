'use client'

import { useCallback, useEffect, useState } from 'react'

type Inquiry = {
  id: number
  name: string
  company: string | null
  email: string
  phone: string | null
  country: string | null
  category: string | null
  message: string
  isRead: boolean
  createdAt: string
}

const PAGE_SIZE = 20

export default function AdminInquiriesPage() {
  const [items, setItems] = useState<Inquiry[]>([])
  const [total, setTotal] = useState(0)
  const [unread, setUnread] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Inquiry | null>(null)
  const [deleting, setDeleting] = useState(false)

  const fetchList = useCallback(async (p: number) => {
    setLoading(true)
    setListError('')
    try {
      const res = await fetch(`/api/admin/inquiries?page=${p}`)
      if (!res.ok) throw new Error('加载失败')
      const data = await res.json()
      setItems(data.items ?? [])
      setTotal(data.total ?? 0)
      setUnread(data.unread ?? 0)
      setPage(data.page ?? 1)
    } catch {
      setListError('询价列表加载失败，请刷新重试')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchList(1)
  }, [fetchList])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  async function toggleRead(m: Inquiry) {
    try {
      const res = await fetch(`/api/admin/inquiries/${m.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ isRead: !m.isRead }),
      })
      if (!res.ok) throw new Error('更新失败')
      await fetchList(page)
    } catch {
      setListError('状态更新失败，请重试')
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      const res = await fetch(`/api/admin/inquiries/${deleteTarget.id}`, { method: 'DELETE' })
      if (!res.ok) {
        setListError('删除失败，请重试')
      } else {
        const nextPage = items.length === 1 && page > 1 ? page - 1 : page
        setDeleteTarget(null)
        await fetchList(nextPage)
      }
    } catch {
      setListError('删除请求失败，请重试')
    } finally {
      setDeleting(false)
    }
  }

  function fmt(iso: string) {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  }

  const btnGhost =
    'inline-flex h-10 items-center justify-center rounded border border-gray-200 bg-white px-3 text-sm font-medium text-gray-600 transition-colors hover:border-primary hover:text-primary'
  const btnDanger =
    'inline-flex h-10 items-center justify-center rounded border border-gray-200 bg-white px-3 text-sm font-medium text-gray-600 transition-colors hover:border-red-300 hover:text-red-600'

  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-bold text-dark sm:text-2xl">询价管理</h1>
        <p className="text-sm text-gray-500">
          共 {total} 条{unread > 0 ? ` · 未读 ${unread} 条` : ''}
        </p>
      </div>

      {listError && (
        <p role="alert" className="mt-3 text-sm text-red-600">
          {listError}
        </p>
      )}

      <div className="mt-4 overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="w-full min-w-[820px] text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
              <th className="px-4 py-3 font-medium">时间</th>
              <th className="px-4 py-3 font-medium">姓名</th>
              <th className="px-4 py-3 font-medium">公司</th>
              <th className="px-4 py-3 font-medium">邮箱</th>
              <th className="px-4 py-3 font-medium">分类</th>
              <th className="px-4 py-3 font-medium">状态</th>
              <th className="px-4 py-3 text-right font-medium">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-gray-400">
                  加载中…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-gray-400">
                  暂无询价记录
                </td>
              </tr>
            ) : (
              items.map((m) => {
                const expanded = expandedId === m.id
                return (
                  <FragmentRow
                    key={m.id}
                    m={m}
                    expanded={expanded}
                    fmt={fmt}
                    btnGhost={btnGhost}
                    btnDanger={btnDanger}
                    onToggle={() => setExpandedId(expanded ? null : m.id)}
                    onToggleRead={() => toggleRead(m)}
                    onDelete={() => setDeleteTarget(m)}
                  />
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* 分页 */}
      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-sm text-gray-500">
          共 {total} 条 · 第 {page} / {totalPages} 页
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1 || loading}
            onClick={() => fetchList(page - 1)}
            className="inline-flex h-11 items-center justify-center rounded border border-gray-200 bg-white px-4 text-base font-medium text-gray-600 transition-colors hover:bg-gray-100 disabled:opacity-40"
          >
            上一页
          </button>
          <button
            type="button"
            disabled={page >= totalPages || loading}
            onClick={() => fetchList(page + 1)}
            className="inline-flex h-11 items-center justify-center rounded border border-gray-200 bg-white px-4 text-base font-medium text-gray-600 transition-colors hover:bg-gray-100 disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      </div>

      {/* 删除二次确认 */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => !deleting && setDeleteTarget(null)}
            aria-hidden="true"
          />
          <div className="relative z-10 w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
            <h3 className="text-base font-bold text-dark">确认删除</h3>
            <p className="mt-2 text-sm text-gray-600">
              确定要删除 <span className="font-medium text-dark">{deleteTarget.name}</span>{' '}
              的这条询价记录吗？此操作不可恢复。
            </p>
            <div className="mt-5 flex gap-2">
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="inline-flex h-11 flex-1 items-center justify-center rounded bg-red-600 text-base font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-60"
              >
                {deleting ? '删除中…' : '删除'}
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={() => setDeleteTarget(null)}
                className="inline-flex h-11 flex-1 items-center justify-center rounded border border-gray-200 bg-white text-base font-medium text-gray-600 transition-colors hover:bg-gray-100"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function FragmentRow({
  m,
  expanded,
  fmt,
  btnGhost,
  btnDanger,
  onToggle,
  onToggleRead,
  onDelete,
}: {
  m: Inquiry
  expanded: boolean
  fmt: (iso: string) => string
  btnGhost: string
  btnDanger: string
  onToggle: () => void
  onToggleRead: () => void
  onDelete: () => void
}) {
  return (
    <>
      <tr
        onClick={onToggle}
        className={`cursor-pointer ${
          expanded ? 'bg-primary/5' : ''
        } ${!m.isRead ? 'bg-amber-50/60' : 'hover:bg-gray-50'}`}
      >
        <td className="whitespace-nowrap px-4 py-3 text-gray-500">{fmt(m.createdAt)}</td>
        <td className="px-4 py-3">
          <span className={`${!m.isRead ? 'font-semibold text-dark' : 'text-gray-700'}`}>
            {m.name}
          </span>
        </td>
        <td className="max-w-[160px] px-4 py-3">
          <span className="block truncate">{m.company || '—'}</span>
        </td>
        <td className="max-w-[200px] px-4 py-3">
          <span className="block truncate">{m.email}</span>
        </td>
        <td className="px-4 py-3">{m.category || '—'}</td>
        <td className="px-4 py-3">
          {m.isRead ? (
            <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">已读</span>
          ) : (
            <span className="rounded bg-primary px-1.5 py-0.5 text-xs text-white">未读</span>
          )}
        </td>
        <td className="px-4 py-3">
          <div className="flex justify-end gap-2" onClick={(e) => e.stopPropagation()}>
            <button type="button" onClick={onToggleRead} className={btnGhost}>
              {m.isRead ? '标为未读' : '标为已读'}
            </button>
            <button type="button" onClick={onDelete} className={btnDanger}>
              删除
            </button>
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-gray-50/70">
          <td colSpan={7} className="px-4 py-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="text-sm text-gray-600">
                <span className="font-medium text-dark">电话：</span>
                {m.phone || '—'}
              </div>
              <div className="text-sm text-gray-600">
                <span className="font-medium text-dark">国家/地区：</span>
                {m.country || '—'}
              </div>
            </div>
            <div className="mt-3 rounded bg-white p-3 text-sm leading-relaxed text-gray-700">
              {m.message}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
