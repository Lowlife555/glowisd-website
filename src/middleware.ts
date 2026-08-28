import { withAuth } from 'next-auth/middleware'

export default withAuth({
  pages: { signIn: '/admin/login' },
  callbacks: {
    authorized({ req, token }) {
      // 登录页本身放行（未登录用户要能访问它），其余 /admin/* 必须已登录
      if (req.nextUrl.pathname === '/admin/login') return true
      return !!token
    },
  },
})

export const config = {
  matcher: ['/admin/:path*'],
}
