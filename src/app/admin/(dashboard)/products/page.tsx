'use client'

import { useCallback, useEffect, useState } from 'react'

type AdminCategory = {
  id: number
  name: string
  nameEn: string
  slug: string
  sortOrder: number
}

type AdminImage = { id: number; url: string; isPrimary: boolean; sortOrder: number }

type AdminProduct = {
  id: number
  sku: string
  partName: string | null
  partNameEn: string | null
  pn: string | null
  brand: string | null
  weight: string | null
  warranty: string | null
  description: string | null
  descriptionEn: string | null
  categoryId: number
  category: AdminCategory
  images: AdminImage[]
  featured: boolean
  createdAt: string
  updatedAt: string
}

type ProductForm = {
  sku: string
  partName: string
  partNameEn: string
  pn: string
  brand: string
  weight: string
  warranty: string
  description: string
  descriptionEn: string
  categoryId: string
  featured: boolean
  imageUrl: string
}

const emptyForm: ProductForm = {
  sku: '',
  partName: '',
  partNameEn: '',
  pn: '',
  brand: '',
  weight: '',
  warranty: '',
  description: '',
  descriptionEn: '',
  categoryId: '',
  featured: false,
  imageUrl: '',
}

const PAGE_SIZE = 20

export default function AdminProductsPage() {
  const [items, setItems] = useState<AdminProduct[]>([])
  const [categories, setCategories] = useState<AdminCategory[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<AdminProduct | null>(null)
  const [form, setForm] = useState<ProductForm>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const [deleteTarget, setDeleteTarget] = useState<AdminProduct | null>(null)
  const [deleting, setDeleting] = useState(false)

  const fetchList = useCallback(async (p: number, q: string) => {
    setLoading(true)
    setListError('')
    try {
      const params = new URLSearchParams({ page: String(p) })
      if (q) params.set('search', q)
      const res = await fetch(`/api/admin/products?${params.toString()}`)
      if (!res.ok) throw new Error('加载失败')
      const data = await res.json()
      setItems(data.items ?? [])
      setTotal(data.total ?? 0)
      setCategories(data.categories ?? [])
      setPage(data.page ?? 1)
    } catch {
      setListError('产品列表加载失败，请刷新重试')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchList(1, '')
  }, [fetchList])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  function openCreate() {
    setEditing(null)
    setForm(emptyForm)
    setFormError('')
    setModalOpen(true)
  }

  function openEdit(p: AdminProduct) {
    setEditing(p)
    setForm({
      sku: p.sku,
      partName: p.partName ?? '',
      partNameEn: p.partNameEn ?? '',
      pn: p.pn ?? '',
      brand: p.brand ?? '',
      weight: p.weight ?? '',
      warranty: p.warranty ?? '',
      description: p.description ?? '',
      descriptionEn: p.descriptionEn ?? '',
      categoryId: String(p.categoryId),
      featured: p.featured,
      imageUrl: (p.images.find((i) => i.isPrimary) || p.images[0])?.url ?? '',
    })
    setFormError('')
    setModalOpen(true)
  }

  function setField<K extends keyof ProductForm>(key: K, value: ProductForm[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setFormError('')
    if (!form.sku.trim()) {
      setFormError('SKU 为必填项')
      return
    }
    if (!form.categoryId) {
      setFormError('请选择分类')
      return
    }
    setSaving(true)
    try {
      const body = {
        sku: form.sku.trim(),
        partName: form.partName.trim() || null,
        partNameEn: form.partNameEn.trim() || null,
        pn: form.pn.trim() || null,
        brand: form.brand.trim() || null,
        weight: form.weight.trim() || null,
        warranty: form.warranty.trim() || null,
        description: form.description.trim() || null,
        descriptionEn: form.descriptionEn.trim() || null,
        categoryId: Number(form.categoryId),
        featured: form.featured,
        imageUrl: form.imageUrl.trim() || null,
      }
      const url = editing ? `/api/admin/products/${editing.id}` : '/api/admin/products'
      const res = await fetch(url, {
        method: editing ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        setFormError(data.error || '保存失败，请检查输入')
        return
      }
      setModalOpen(false)
      await fetchList(page, search)
    } catch {
      setFormError('保存请求失败，请稍后再试')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      const res = await fetch(`/api/admin/products/${deleteTarget.id}`, { method: 'DELETE' })
      if (!res.ok) {
        setListError('删除失败，请重试')
      } else {
        // 当前页删空则回退一页
        const nextPage = items.length === 1 && page > 1 ? page - 1 : page
        setDeleteTarget(null)
        await fetchList(nextPage, search)
      }
    } catch {
      setListError('删除请求失败，请重试')
    } finally {
      setDeleting(false)
    }
  }

  function handleSearch(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setSearch(searchInput.trim())
    fetchList(1, searchInput.trim())
  }

  function resetSearch() {
    setSearchInput('')
    setSearch('')
    fetchList(1, '')
  }

  const inputCls =
    'w-full rounded border border-gray-200 px-3 py-2.5 text-base outline-none focus:border-primary focus:ring-1 focus:ring-primary'
  const btnPrimary =
    'inline-flex h-11 items-center justify-center rounded bg-primary px-4 text-base font-medium text-white transition-colors hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-60'
  const btnGhost =
    'inline-flex h-11 items-center justify-center rounded border border-gray-200 bg-white px-4 text-base font-medium text-gray-600 transition-colors hover:bg-gray-100'

  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-bold text-dark sm:text-2xl">产品管理</h1>
        <button type="button" onClick={openCreate} className={btnPrimary}>
          + 添加产品
        </button>
      </div>

      <form onSubmit={handleSearch} className="mt-5 flex flex-col gap-2 sm:flex-row">
        <input
          type="search"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="搜索 SKU / 名称 / P/N / 品牌"
          className={`${inputCls} sm:max-w-sm`}
        />
        <div className="flex gap-2">
          <button type="submit" className={`${btnPrimary} flex-1 sm:flex-none`}>
            搜索
          </button>
          <button type="button" onClick={resetSearch} className={`${btnGhost} flex-1 sm:flex-none`}>
            重置
          </button>
        </div>
      </form>

      {listError && (
        <p role="alert" className="mt-3 text-sm text-red-600">
          {listError}
        </p>
      )}

      <div className="mt-4 overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
              <th className="px-4 py-3 font-medium">缩略图</th>
              <th className="px-4 py-3 font-medium">SKU</th>
              <th className="px-4 py-3 font-medium">名称</th>
              <th className="px-4 py-3 font-medium">P/N</th>
              <th className="px-4 py-3 font-medium">分类</th>
              <th className="px-4 py-3 font-medium">推荐</th>
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
                  暂无产品{search ? '，试试其他关键词' : ''}
                </td>
              </tr>
            ) : (
              items.map((p) => {
                const primary = p.images.find((i) => i.isPrimary) || p.images[0]
                return (
                  <tr key={p.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      {primary ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={primary.url}
                          alt={p.sku}
                          className="h-12 w-12 rounded object-cover"
                        />
                      ) : (
                        <div className="flex h-12 w-12 items-center justify-center rounded bg-gray-100 text-gray-300">
                          —
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 font-medium text-dark">{p.sku}</td>
                    <td className="max-w-[200px] px-4 py-3">
                      <div className="truncate">{p.partName || p.partNameEn || '—'}</div>
                      {p.brand && <div className="text-xs text-gray-400">{p.brand}</div>}
                    </td>
                    <td className="px-4 py-3">{p.pn || '—'}</td>
                    <td className="px-4 py-3">{p.category.name}</td>
                    <td className="px-4 py-3">
                      {p.featured ? (
                        <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary">
                          是
                        </span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => openEdit(p)}
                          className="inline-flex min-h-10 items-center rounded border border-gray-200 px-3 text-sm font-medium text-gray-600 hover:border-primary hover:text-primary"
                        >
                          编辑
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteTarget(p)}
                          className="inline-flex min-h-10 items-center rounded border border-gray-200 px-3 text-sm font-medium text-gray-600 hover:border-red-300 hover:text-red-600"
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
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
            onClick={() => fetchList(page - 1, search)}
            className={`${btnGhost} disabled:opacity-40`}
          >
            上一页
          </button>
          <button
            type="button"
            disabled={page >= totalPages || loading}
            onClick={() => fetchList(page + 1, search)}
            className={`${btnGhost} disabled:opacity-40`}
          >
            下一页
          </button>
        </div>
      </div>

      {/* 添加/编辑弹窗 */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => !saving && setModalOpen(false)}
            aria-hidden="true"
          />
          <div className="relative z-10 max-h-[92vh] w-full overflow-y-auto rounded-t-lg bg-white p-5 shadow-xl sm:max-w-2xl sm:rounded-lg sm:p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-dark">
                {editing ? `编辑产品 ${editing.sku}` : '添加产品'}
              </h2>
              <button
                type="button"
                aria-label="关闭"
                onClick={() => !saving && setModalOpen(false)}
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

            <form onSubmit={handleSubmit} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="f-sku" className="mb-1.5 block text-sm font-medium text-dark">
                  SKU <span className="text-red-500">*</span>
                </label>
                <input
                  id="f-sku"
                  type="text"
                  value={form.sku}
                  onChange={(e) => setField('sku', e.target.value)}
                  className={inputCls}
                  placeholder="如 R202419002"
                />
              </div>
              <div>
                <label htmlFor="f-pn" className="mb-1.5 block text-sm font-medium text-dark">
                  P/N
                </label>
                <input
                  id="f-pn"
                  type="text"
                  value={form.pn}
                  onChange={(e) => setField('pn', e.target.value)}
                  className={inputCls}
                />
              </div>
              <div>
                <label htmlFor="f-partName" className="mb-1.5 block text-sm font-medium text-dark">
                  名称（中文）
                </label>
                <input
                  id="f-partName"
                  type="text"
                  value={form.partName}
                  onChange={(e) => setField('partName', e.target.value)}
                  className={inputCls}
                />
              </div>
              <div>
                <label htmlFor="f-partNameEn" className="mb-1.5 block text-sm font-medium text-dark">
                  名称（英文）
                </label>
                <input
                  id="f-partNameEn"
                  type="text"
                  value={form.partNameEn}
                  onChange={(e) => setField('partNameEn', e.target.value)}
                  className={inputCls}
                />
              </div>
              <div>
                <label htmlFor="f-brand" className="mb-1.5 block text-sm font-medium text-dark">
                  品牌
                </label>
                <input
                  id="f-brand"
                  type="text"
                  value={form.brand}
                  onChange={(e) => setField('brand', e.target.value)}
                  className={inputCls}
                />
              </div>
              <div>
                <label htmlFor="f-category" className="mb-1.5 block text-sm font-medium text-dark">
                  分类 <span className="text-red-500">*</span>
                </label>
                <select
                  id="f-category"
                  value={form.categoryId}
                  onChange={(e) => setField('categoryId', e.target.value)}
                  className={inputCls}
                >
                  <option value="">请选择分类</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}（{c.nameEn}）
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="f-weight" className="mb-1.5 block text-sm font-medium text-dark">
                  重量
                </label>
                <input
                  id="f-weight"
                  type="text"
                  value={form.weight}
                  onChange={(e) => setField('weight', e.target.value)}
                  className={inputCls}
                />
              </div>
              <div>
                <label htmlFor="f-warranty" className="mb-1.5 block text-sm font-medium text-dark">
                  质保
                </label>
                <input
                  id="f-warranty"
                  type="text"
                  value={form.warranty}
                  onChange={(e) => setField('warranty', e.target.value)}
                  className={inputCls}
                />
              </div>
              <div className="sm:col-span-2">
                <label htmlFor="f-desc" className="mb-1.5 block text-sm font-medium text-dark">
                  描述（中文）
                </label>
                <textarea
                  id="f-desc"
                  rows={3}
                  value={form.description}
                  onChange={(e) => setField('description', e.target.value)}
                  className={inputCls}
                />
              </div>
              <div className="sm:col-span-2">
                <label htmlFor="f-descEn" className="mb-1.5 block text-sm font-medium text-dark">
                  描述（英文）
                </label>
                <textarea
                  id="f-descEn"
                  rows={3}
                  value={form.descriptionEn}
                  onChange={(e) => setField('descriptionEn', e.target.value)}
                  className={inputCls}
                />
              </div>
              <div className="sm:col-span-2">
                <label htmlFor="f-image" className="mb-1.5 block text-sm font-medium text-dark">
                  图片 URL
                </label>
                <input
                  id="f-image"
                  type="url"
                  value={form.imageUrl}
                  onChange={(e) => setField('imageUrl', e.target.value)}
                  className={inputCls}
                  placeholder="https://…（本阶段以图片链接代替上传）"
                />
                <p className="mt-1 text-xs text-gray-400">
                  {editing ? '留空表示不修改现有图片' : '留空则产品暂无图片'}
                </p>
              </div>
              <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-medium text-dark sm:col-span-2">
                <input
                  type="checkbox"
                  checked={form.featured}
                  onChange={(e) => setField('featured', e.target.checked)}
                  className="h-5 w-5 accent-primary"
                />
                设为推荐产品
              </label>

              {formError && (
                <p role="alert" className="text-sm text-red-600 sm:col-span-2">
                  {formError}
                </p>
              )}

              <div className="flex gap-2 sm:col-span-2">
                <button type="submit" disabled={saving} className={`${btnPrimary} flex-1`}>
                  {saving ? '保存中…' : '保存'}
                </button>
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => setModalOpen(false)}
                  className={`${btnGhost} flex-1`}
                >
                  取消
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

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
              确定要删除产品 <span className="font-medium text-dark">{deleteTarget.sku}</span>{' '}
              吗？此操作不可恢复。
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
                className={`${btnGhost} flex-1`}
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
