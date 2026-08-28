import { getServerSession } from 'next-auth'
import { NextResponse } from 'next/server'
import { authOptions } from '@/lib/auth'

/**
 * admin API 鉴权：未登录或非 admin 角色返回 null，调用方返回 401。
 */
export async function requireAdmin() {
  const session = await getServerSession(authOptions)
  if (!session?.user) return null
  const role = (session.user as { role?: string }).role
  if (role && role !== 'admin') return null
  return session
}

export function unauthorized() {
  return NextResponse.json({ error: '未授权' }, { status: 401 })
}
