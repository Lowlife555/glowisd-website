import json

from django.conf import settings
from django.core.management.base import BaseCommand

from products.models import Product


class Command(BaseCommand):
    help = '从 product_annotations.json 导入件号(GW)+品名'

    def handle(self, *args, **options):
        json_path = settings.BASE_DIR / 'products' / 'fixtures' / 'product_annotations.json'
        if not json_path.exists():
            self.stderr.write(f'找不到 {json_path}')
            return

        data = json.loads(json_path.read_text(encoding='utf-8'))
        updated = 0
        skipped = 0
        for item in data:
            image = item.get('image', '')
            pn = item.get('pn', '')
            part_name = item.get('part_name', '')
            part_name_en = item.get('part_name_en', '')

            try:
                product = Product.objects.get(image=image)
            except Product.DoesNotExist:
                skipped += 1
                continue

            product.pn = pn or product.pn
            product.part_name = part_name or product.part_name
            product.part_name_en = part_name_en or product.part_name_en
            product.save(update_fields=['pn', 'part_name', 'part_name_en', 'updated_at'])
            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'更新完成：{updated} 个产品（{skipped} 个未匹配），件号已改写为 GW 前缀'
        ))
