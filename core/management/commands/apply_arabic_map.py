"""按内置映射批量写入阿拉伯语字段（不依赖 API Key，可重复执行）。

用法（服务器/本地均可）：
    python manage.py apply_arabic_map            # 应用映射 + 设置分类默认封面图
    python manage.py apply_arabic_map --dry-run  # 只看匹配情况，不写库

匹配规则：
- 产品：按 part_name_en 精确匹配 → 写 part_name_ar（已有值不覆盖）
- 分类：按 slug 匹配 → 写 name_ar
- 分类封面：cover_image 为空且该分类有带图产品时，取第一个产品图作为默认封面
未匹配到的名称会打印出来，便于补充映射后重跑。
"""
from django.core.management.base import BaseCommand

from core.translation import GLOSSARY  # noqa: F401  (术语表作为译法依据保留)
from products.models import Category, Product

# 产品英文名 => 阿语（品牌名/件号/型号保持拉丁不译）
PRODUCT_AR = {
    '10-7can Y': '10-7 CAN Y',
    '10Hole-12Hole': '10 فتحات - 12 فتحة',
    '58614': '58614',
    # 线上存量补充（V0.12.0 部署时 dry-run 报出的未匹配名）
    'Angle Sensor': 'مستشعر الزاوية',
    'Bomag senser': 'مستشعر Bomag',
    'Controller': 'وحدة التحكم',
    'Electronic  control': 'وحدة تحكم إلكترونية',
    'Heating strip': 'شريط التسخين',
    'IO card': 'بطاقة الإدخال والإخراج',
    'Ignition module': 'وحدة الإشعال',
    'Iron sliding boots': 'أحذية انزلاق حديدية',
    'Milling machine  cutter head impact rod': 'قضيب الصدم لرأس القطع في آلة الطحن',
    'Sensing arm': 'ذراع الاستشعار',
    'Sensor bracket': 'حامل المستشعر',
    'Sliding tube': 'أنبوب الانزلاق',
    'Sonic Sensor': 'مستشعر صوتي',
    'Sonic sensor': 'مستشعر صوتي',
    'Sonsic sensor': 'مستشعر صوتي',
    'YType can line': 'كابل نوع Y',
    '加热喷嘴': 'فوهة التسخين',
    '平衡梁': 'عارضة التوازن',
    '找平仪': 'جهاز التسوية',
    '油缸': 'أسطوانة هيدروليكية',
    '福格勒平衡梁电控': 'وحدة التحكم الإلكتروني لعارضة التوازن Vogele',
    '行程开关': 'مفتاح الحد',
    'Aviation Plug': 'قابس الطيران',
    'Ball Joint Separator': 'فاصل المفصل الكروي',
    'Bomag ABG': 'Bomag ABG',
    'Bracket': 'حامل',
    'Cable': 'كابل',
    'Circuit Board': 'لوحة دوائر',
    'Coiled Cable': 'كابل ملفوف',
    'Connecting Cable': 'كابل توصيل',
    'Connector': 'موصل',
    'Control Board': 'لوحة تحكم',
    'Control Box': 'صندوق تحكم',
    'Control Handle': 'مقبض تحكم',
    'Control Panel': 'لوحة تحكم',
    'Control handle Can': 'مقبض تحكم CAN',
    'Control handle PWM': 'مقبض تحكم PWM',
    'Damper': 'مخمد',
    'Displacement Sensor': 'مستشعر الإزاحة',
    'Display': 'شاشة عرض',
    'Display Screen': 'شاشة عرض',
    'Draw-wire Sensor': 'مستشعر سلك السحب',
    'Dynapac141': 'Dynapac141',
    'ECU': 'وحدة تحكم إلكترونية ECU',
    'Emergency Stop Switch': 'مفتاح إيقاف الطوارئ',
    'Hall Current Sensor': 'مستشعر تيار هول',
    'Handheld Tester': 'جهاز اختبار محمول',
    'Hydraulic Pump': 'مضخة هيدروليكية',
    'Ignition Electrode': 'قطب الإشعال',
    'Industrial Plug': 'قابس صناعي',
    'Joystick': 'عصا التحكم',
    'Junction Box': 'صندوق توصيل',
    'Junction box': 'صندوق توصيل',
    'Keyboard': 'لوحة مفاتيح',
    'Keypad': 'لوحة أزرار',
    'LED Work Light': 'مصباح عمل LED',
    'Limit Switch': 'مفتاح حد',
    'Membrane Switch': 'مفتاح غشائي',
    'Nozzle': 'فوهة',
    'Potentiometer': 'مقياس الجهد',
    'Power Controller': 'وحدة تحكم الطاقة',
    'Remote Control': 'تحكم عن بعد',
    'Rotary /grade sensor Can': 'مستشعر الدوران/التدرج CAN',
    'Rotary /grade sensor Pwm': 'مستشعر الدوران/التدرج PWM',
    'Rotary Sensor': 'مستشعر الدوران',
    'Rubber Boot': 'غطاء مطاطي',
    'Sensor': 'مستشعر',
    'Sensor Bracket': 'حامل المستشعر',
    'Slope Sensor': 'مستشعر الميل',
    'Slope sensor': 'مستشعر الميل',
    'Slope sensor Can': 'مستشعر الميل CAN',
    'Solenoid Valve': 'صمام الملف اللولبي',
    'Sonic sensor Can': 'مستشعر صوتي CAN',
    'Sonic ski Pwm': 'حذاء صوتي PWM',
    'Temperature Sensor': 'مستشعر الحرارة',
    'Toolbox': 'صندوق الأدوات',
    'Typ11 ABG': 'Typ11 ABG',
    'Warning Light': 'ضوء تحذيري',
    'Wiring Harness': 'حزمة الأسلاك',
    'Wirtgen': 'Wirtgen',
}

CATEGORY_AR = {
    'sensors': 'المستشعرات',
    'cables': 'الكابلات',
    'control-handles': 'مقابض التحكم',
    'displays': 'وحدات التحكم بالعرض',
    'junction-boxes': 'صناديق التوصيل',
    'leveling-arms': 'أذرع التسوية',
    'pcb-boards': 'لوحات الدوائر',
    'membrane-switches': 'المفاتيح الغشائية',
    'complete-kits': 'الأطقم الكاملة',
    'uncategorized': 'غير مصنف',
}


class Command(BaseCommand):
    help = '按内置映射批量写入阿语字段，并为分类设置默认封面图'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='只报告匹配情况，不写库')

    def handle(self, *args, **options):
        dry = options['dry_run']
        p_ok = p_missing = 0
        missing_names = []

        for product in Product.objects.all():
            source = (product.part_name_en or product.part_name or '').strip()
            if not source:
                continue
            ar = PRODUCT_AR.get(source)
            if not ar:
                missing_names.append(source)
                p_missing += 1
                continue
            if product.part_name_ar:
                p_ok += 1
                continue
            if not dry:
                product.part_name_ar = ar
                product.save(update_fields=['part_name_ar'])
            p_ok += 1

        c_ok = 0
        for category in Category.objects.all():
            ar = CATEGORY_AR.get(category.slug)
            if ar and not category.name_ar and not dry:
                category.name_ar = ar
                category.save(update_fields=['name_ar'])
            if ar:
                c_ok += 1

        # 分类默认封面：无封面时取该分类第一个有图产品
        cover_set = 0
        for category in Category.objects.all():
            if category.cover_image:
                continue
            product = category.products.exclude(image='').exclude(image__isnull=True).first()
            if not product:
                continue
            if not dry:
                category.cover_image = product.image.name
                category.save(update_fields=['cover_image'])
            cover_set += 1

        self.stdout.write(f'产品：已覆盖/已写 {p_ok} 条，未匹配 {p_missing} 条')
        if missing_names:
            self.stdout.write('未匹配的产品名（请在 PRODUCT_AR 中补充）：')
            for name in sorted(set(missing_names)):
                self.stdout.write(f'  - {name!r}')
        self.stdout.write(f'分类阿语名：{c_ok} 条')
        self.stdout.write(f'分类默认封面：{cover_set} 条')
        if dry:
            self.stdout.write(self.style.WARNING('（dry-run：未写入数据库）'))
        else:
            self.stdout.write(self.style.SUCCESS('完成'))
