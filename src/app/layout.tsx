import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Glowisd - Paving Machine Sensors & Accessories',
  description:
    'Professional manufacturer of paving machine sensors, cables, and accessories. Compatible with Vogele, Bomag, Wirtgen.',
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
