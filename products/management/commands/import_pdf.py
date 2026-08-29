import json
from pathlib import Path

from django.core.management.base import BaseCommand

from products.models import Category, Product


class Command(BaseCommand):
    help = '从 素材/extracted_products.json 导入 PDF 产品（照片 + 临时 SKU）'

    def handle(self, *args, **options):
        from django.conf import settings

        json_path = settings.BASE_DIR / 'products' / 'fixtures' / 'extracted_products.json'
        if not json_path.exists():
            self.stderr.write(f'找不到 {json_path}')
            return

        data = json.loads(json_path.read_text(encoding='utf-8'))
        products = data.get('products', [])

        # 未分类（PDF 为扫描版，分类后续人工/OCR 补充）
        uncat, _ = Category.objects.get_or_create(
            slug='uncategorized',
            defaults={'name': '未分类', 'name_en': 'Uncategorized', 'sort_order': 99},
        )

        created = 0
        for p in products:
            page = p.get('page')
            index = p.get('index')
            image_path = p.get('image', '')
            # image 字段存相对 MEDIA_ROOT 的路径：products/pXXX_Y.png
            rel_image = image_path.replace('site/glowisd-website/media/', '').replace('\\', '/').replace('.png', '.jpg') if image_path else ''
            sku = f'PDF-{page:03d}-{index}'
            Product.objects.update_or_create(
                sku=sku,
                defaults={
                    'pn': p.get('part_number') or '',
                    'category': uncat,
                    'image': rel_image or None,
                },
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(f'导入完成：{created} 个产品（分类=未分类，件号待 OCR 补充）'))
