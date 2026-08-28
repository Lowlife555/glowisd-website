import { NextResponse } from 'next/server'
import { z } from 'zod'
import { prisma } from '@/lib/db'
import { rateLimit, clientIp } from '@/lib/rate-limit'

const schema = z.object({
  name: z.string().trim().min(1).max(100),
  company: z.string().trim().max(200).optional(),
  email: z.string().trim().email().max(200),
  phone: z.string().trim().max(50).optional(),
  country: z.string().trim().max(100).optional(),
  category: z.string().trim().max(100).optional(),
  productSku: z.string().trim().max(100).optional(),
  message: z.string().trim().min(1).max(2000),
  website: z.string().optional(),
})

export async function POST(request: Request) {
  const ip = clientIp(request.headers)
  const rl = rateLimit(`contact:${ip}`, 3, 5 * 60 * 1000)
  if (!rl.ok) {
    return NextResponse.json(
      { error: 'Too many requests' },
      { status: 429, headers: { 'Retry-After': String(rl.retryAfterSec) } },
    )
  }

  let body: unknown
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  const parsed = schema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Invalid input', details: parsed.error.flatten().fieldErrors },
      { status: 400 },
    )
  }

  const data = parsed.data

  // 蜜罐：机器人填了 website → 直接丢弃，但仍返回成功以迷惑
  if (data.website && data.website.trim() !== '') {
    return NextResponse.json({ ok: true })
  }

  await prisma.contactMessage.create({
    data: {
      name: data.name,
      company: data.company || null,
      email: data.email,
      phone: data.phone || null,
      country: data.country || null,
      category: data.category || null,
      message: data.message,
    },
  })

  return NextResponse.json({ ok: true })
}
