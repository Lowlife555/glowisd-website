from django.core.management.base import BaseCommand

from products.models import Category, Product

CATEGORIES = [
    ('传感器', 'Sensors', 'sensors', 1),
    ('线缆', 'Cables', 'cables', 2),
    ('控制手柄', 'Control Handles', 'control-handles', 3),
    ('显示控制器', 'Displays', 'displays', 4),
    ('接线盒', 'Junction Boxes', 'junction-boxes', 5),
    ('找平臂', 'Leveling Arms', 'leveling-arms', 6),
    ('电路板', 'PCB & Boards', 'pcb-boards', 7),
    ('膜开关', 'Membrane Switches', 'membrane-switches', 8),
    ('套件', 'Complete Kits', 'complete-kits', 9),
]

# (sku, part_name, pn, category_slug)
PRODUCTS = [
    ('R202419002', 'Control handle Can', '04-25-10453', 'control-handles'),
    ('R202419003', 'Sonic sensor Can', '04-20-10020', 'sensors'),
    ('R202419028', 'Bomag ABG', '05940023', 'sensors'),
    ('R202419029', '', '24-3413-0067', 'sensors'),
    ('R202419030', 'Wirtgen', '161400', 'displays'),
    ('R202419043', '', '2134259', 'control-handles'),
    ('R202419044', '', '2143913', 'pcb-boards'),
    ('R202419045', '', '2472560017', 'sensors'),
    ('R202419133', '', '80863798', 'cables'),
    ('R202419178', '', '', 'complete-kits'),
]


class Command(BaseCommand):
    help = '初始化产品分类与示例产品（幂等）'

    def handle(self, *args, **options):
        cat_map = {}
        for name, name_en, slug, order in CATEGORIES:
            cat, _ = Category.objects.update_or_create(
                slug=slug,
                defaults={'name': name, 'name_en': name_en, 'sort_order': order},
            )
            cat_map[slug] = cat

        for sku, part_name, pn, cat_slug in PRODUCTS:
            Product.objects.update_or_create(
                sku=sku,
                defaults={
                    'part_name': part_name,
                    'part_name_en': part_name,
                    'pn': pn,
                    'category': cat_map[cat_slug],
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f'Seed 完成：{len(CATEGORIES)} 分类，{len(PRODUCTS)} 产品'
        ))
