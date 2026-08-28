import type { NextAuthOptions } from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'
import bcrypt from 'bcryptjs'
import { prisma } from '@/lib/db'
import { rateLimit, clientIp } from '@/lib/rate-limit'

// 登录限流：同 IP + 用户名，15 分钟窗口内最多 5 次尝试
const LOGIN_LIMIT = 5
const LOGIN_WINDOW_MS = 15 * 60 * 1000

/**
 * authorize 收到的 req.headers 在 App Router 下是 WHATWG Headers 实例，
 * 这里做一层防御，兼容纯对象形态。
 */
function ipFromReq(req: {
  headers?: Headers | Record<string, string | undefined>
}): string {
  const h = req?.headers
  if (!h) return 'local'
  if (typeof (h as Headers).get === 'function') return clientIp(h as Headers)
  const rec = h as Record<string, string | undefined>
  const xff = rec['x-forwarded-for']
  if (xff) return xff.split(',')[0].trim()
  return rec['x-real-ip']?.trim() || 'local'
}

export const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET,
  session: { strategy: 'jwt' },
  pages: { signIn: '/admin/login' },
  providers: [
    CredentialsProvider({
      name: '管理员登录',
      credentials: {
        username: { label: '用户名', type: 'text' },
        password: { label: '密码', type: 'password' },
      },
      async authorize(credentials, req) {
        const username = (credentials?.username ?? '').trim()
        const password = credentials?.password ?? ''
        if (!username || !password) return null

        // 每次尝试都计数：第 6 次起（15 分钟内）即使密码正确也会被拦截
        const ip = ipFromReq(req)
        const rl = rateLimit(
          `login:${ip}:${username.toLowerCase()}`,
          LOGIN_LIMIT,
          LOGIN_WINDOW_MS,
        )
        if (!rl.ok) return null

        const user = await prisma.user.findUnique({ where: { username } })
        if (!user) return null

        const valid = await bcrypt.compare(password, user.password)
        if (!valid) return null

        return { id: String(user.id), name: user.username, role: user.role }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) token.role = (user as { role?: string }).role
      return token
    },
    async session({ session, token }) {
      if (session.user) {
        ;(session.user as { role?: string }).role = token.role as string | undefined
      }
      return session
    },
  },
}
