'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { signIn } from 'next-auth/react'

export default function AdminLoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  // 已登录则直接进入后台
  useEffect(() => {
    let active = true
    fetch('/api/auth/session')
      .then((r) => r.json())
      .then((s) => {
        if (active && s?.user) router.replace('/admin')
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [router])

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!username || !password) {
      setError('请输入用户名和密码')
      return
    }
    setError('')
    setLoading(true)
    try {
      const res = await signIn('credentials', {
        redirect: false,
        username,
        password,
      })
      if (res?.error) {
        setError('用户名或密码错误；或尝试次数过多，请 15 分钟后再试')
      } else {
        router.push('/admin')
        router.refresh()
      }
    } catch {
      setError('登录请求失败，请稍后再试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-light px-4 py-10">
      <div className="w-full max-w-sm rounded-lg border border-gray-100 bg-white p-6 shadow-sm sm:p-8">
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded bg-primary text-xl font-bold text-white">
            G
          </div>
          <h1 className="mt-4 text-xl font-bold text-dark">Glowisd 后台管理</h1>
          <p className="mt-1 text-sm text-gray-500">请登录以继续</p>
        </div>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4" noValidate>
          <div>
            <label htmlFor="username" className="mb-1.5 block text-sm font-medium text-dark">
              用户名
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              placeholder="请输入用户名"
              className="w-full rounded border border-gray-200 px-3 py-2.5 text-base outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-dark">
              密码
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              placeholder="请输入密码"
              className="w-full rounded border border-gray-200 px-3 py-2.5 text-base outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="h-11 w-full rounded bg-primary font-medium text-white transition-colors hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? '登录中…' : '登录'}
          </button>
        </form>
      </div>
    </div>
  )
}
