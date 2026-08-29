import json

from django.core.management.base import BaseCommand

from products.models import Product


class Command(BaseCommand):
    help = '从 products/fixtures/product_names_ocr.json 导入中英文品名到产品（按 image 字段匹配）'

    def handle(self, *args, **options):
        path = 'products/fixtures/product_names_ocr.json'
        with open(path, encoding='utf-8') as f:
            data = json.load(f)

        updated = 0
        missing = []
        for item in data:
            n = Product.objects.filter(image=item['image']).update(
                part_name=item['part_name'],
                part_name_en=item['part_name_en'],
            )
            updated += n
            if n == 0:
                missing.append(item['image'])

        self.stdout.write(self.style.SUCCESS(f'品名导入完成：更新 {updated} 条 / 共 {len(data)} 条'))
        if missing:
            self.stdout.write(self.style.WARNING(f'未匹配 {len(missing)} 条：{missing}'))
