import 'dotenv/config'
import { PrismaClient } from '@prisma/client'
import bcrypt from 'bcryptjs'

const prisma = new PrismaClient()

const categories = [
  { name: '传感器', nameEn: 'Sensors', slug: 'sensors', sortOrder: 1 },
  { name: '线缆', nameEn: 'Cables', slug: 'cables', sortOrder: 2 },
  { name: '控制手柄', nameEn: 'Control Handles', slug: 'control-handles', sortOrder: 3 },
  { name: '显示控制器', nameEn: 'Displays', slug: 'displays', sortOrder: 4 },
  { name: '接线盒', nameEn: 'Junction Boxes', slug: 'junction-boxes', sortOrder: 5 },
  { name: '找平臂', nameEn: 'Leveling Arms', slug: 'leveling-arms', sortOrder: 6 },
  { name: '电路板', nameEn: 'PCB & Boards', slug: 'pcb-boards', sortOrder: 7 },
  { name: '膜开关', nameEn: 'Membrane Switches', slug: 'membrane-switches', sortOrder: 8 },
  { name: '套件', nameEn: 'Complete Kits', slug: 'complete-kits', sortOrder: 9 },
]

const products = [
  { sku: 'R202419002', partName: 'Control handle Can', pn: '04-25-10453', category: 'control-handles' },
  { sku: 'R202419003', partName: 'Sonic sensor Can', pn: '04-20-10020', category: 'sensors' },
  { sku: 'R202419028', partName: 'Bomag ABG', pn: '05940023', category: 'sensors' },
  { sku: 'R202419029', partName: null, pn: '24-3413-0067', category: 'sensors' },
  { sku: 'R202419030', partName: 'Wirtgen', pn: '161400', category: 'displays' },
  { sku: 'R202419043', partName: null, pn: '2134259', category: 'control-handles' },
  { sku: 'R202419044', partName: null, pn: '2143913', category: 'pcb-boards' },
  { sku: 'R202419045', partName: null, pn: '2472560017', category: 'sensors' },
  { sku: 'R202419133', partName: null, pn: '80863798', category: 'cables' },
  { sku: 'R202419178', partName: null, pn: null, category: 'complete-kits' },
]

async function main() {
  const categoryIdMap: Record<string, number> = {}

  for (const c of categories) {
    const cat = await prisma.category.upsert({
      where: { slug: c.slug },
      update: { name: c.name, nameEn: c.nameEn, sortOrder: c.sortOrder },
      create: c,
    })
    categoryIdMap[c.slug] = cat.id
  }

  for (const p of products) {
    const data = {
      sku: p.sku,
      partName: p.partName,
      pn: p.pn,
      categoryId: categoryIdMap[p.category],
    }
    await prisma.product.upsert({
      where: { sku: p.sku },
      update: data,
      create: data,
    })
  }

  const existingAdmin = await prisma.user.findFirst({ where: { username: 'admin' } })
  if (!existingAdmin) {
    await prisma.user.create({
      data: {
        username: 'admin',
        password: await bcrypt.hash('glowisd2026', 10),
        role: 'admin',
      },
    })
    console.log('Created admin user (admin / glowisd2026)')
  } else {
    console.log('Admin user already exists, skipped')
  }

  console.log(`Seed done: ${categories.length} categories, ${products.length} products`)
}

main()
  .catch((e) => {
    console.error(e)
    process.exit(1)
  })
  .finally(() => prisma.$disconnect())
