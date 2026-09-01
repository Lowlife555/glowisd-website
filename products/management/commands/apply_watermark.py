"""给产品图片批量添加水印。

用法：
    python manage.py apply_watermark                 # 处理所有有图片的产品
    python manage.py apply_watermark --sku A B C      # 只处理指定 SKU（可多个，空格分隔）

水印参数来自 core.SiteSettings 单例（后台「站点设置 → 水印设置」）：
    启用水印 / 水印图片 / 水印位置 / 水印透明度(%) / 水印宽度(%) / 水印边距(px)

幂等：首次处理前把原图备份到 media/products_original/（同相对路径），
备份已存在则视为已打过水印，直接跳过，避免重复叠加。
"""
import os
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image

from core.models import SiteSettings
from products.models import Product


class Command(BaseCommand):
    help = '给产品图片批量添加水印（参数来自 SiteSettings「水印设置」）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sku', nargs='+', dest='skus', default=None,
            help='只处理指定的 SKU（可多个，空格分隔）；缺省处理所有有图片的产品',
        )

    def handle(self, *args, **options):
        site = SiteSettings.load()

        # 未启用或未配置水印图片 → 全部跳过
        if not site.watermark_enabled:
            self.stdout.write(self.style.WARNING(
                '水印未启用（SiteSettings.watermark_enabled=False），已跳过全部产品'
            ))
            return
        if not site.watermark_image:
            self.stdout.write(self.style.WARNING(
                '未配置水印图片（SiteSettings.watermark_image 为空），已跳过全部产品'
            ))
            return

        logo_path = site.watermark_image.path
        if not os.path.exists(logo_path):
            self.stdout.write(self.style.ERROR(f'水印图片文件不存在：{logo_path}'))
            return

        skus = options.get('skus')
        qs = Product.objects.all()
        if skus:
            qs = qs.filter(sku__in=skus)
        else:
            qs = qs.exclude(image__isnull=True).exclude(image='')

        products = list(qs)
        if not products:
            self.stdout.write(self.style.WARNING('没有需要处理的产品'))
            return

        opacity = max(1, min(100, int(site.watermark_opacity or 45)))
        width_pct = max(1, min(100, int(site.watermark_width_pct or 18)))
        margin_px = max(0, int(site.watermark_margin or 20))
        position = site.watermark_position or 'bottom_right'

        backup_root = os.path.join(settings.MEDIA_ROOT, 'products_original')

        processed = 0
        skipped = 0
        already_done = 0
        failed = 0

        for product in products:
            if not product.image:
                skipped += 1
                self.stdout.write(self.style.WARNING(f'跳过 {product.sku}：无产品图片'))
                continue
            img_path = product.image.path
            if not os.path.exists(img_path):
                skipped += 1
                self.stdout.write(self.style.WARNING(f'跳过 {product.sku}：图片文件不存在 {img_path}'))
                continue

            # 幂等：首次处理前把原图备份到 media/products_original/（同相对路径）。
            # 备份已存在 → 该图已打过水印，跳过，避免重复叠加。
            backup_path = os.path.join(backup_root, product.image.name)
            if os.path.exists(backup_path):
                already_done += 1
                self.stdout.write(self.style.WARNING(f'已打过跳过 {product.sku}：备份已存在'))
                continue

            try:
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                shutil.copy2(img_path, backup_path)
                self._apply_watermark(img_path, logo_path, position, opacity, width_pct, margin_px)
                processed += 1
                self.stdout.write(self.style.SUCCESS(f'已处理 {product.sku}：{img_path}'))
            except Exception as exc:  # noqa: BLE001
                failed += 1
                self.stdout.write(self.style.ERROR(f'处理失败 {product.sku}：{exc}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'水印处理完成：成功 {processed} 个 / 跳过 {skipped} 个 / 已打过跳过 {already_done} 个 / 失败 {failed} 个'
        ))

    def _apply_watermark(self, img_path, logo_path, position, opacity, width_pct, margin_px):
        """把 logo 按位置与透明度贴到底图上，就地覆盖保存。"""
        with Image.open(img_path) as src:
            fmt = src.format
            base = src.convert('RGBA')
        w, h = base.size

        with Image.open(logo_path) as src_logo:
            logo = src_logo.convert('RGBA')

        # 水印宽度为底图宽度的 width_pct%（可配置，默认 18%）
        target_w = max(40, int(w * width_pct / 100))
        ratio = target_w / logo.width
        target_h = int(logo.height * ratio)
        logo = logo.resize((target_w, target_h), Image.LANCZOS)

        # 按透明度百分比调整 logo 的 alpha 通道
        alpha = logo.getchannel('A').point(lambda a: int(a * opacity / 100))
        logo.putalpha(alpha)

        margin = int(margin_px)
        x, y = self._position_xy(w, h, target_w, target_h, position, margin)
        base.paste(logo, (x, y), logo)

        if fmt == 'JPEG':
            base.convert('RGB').save(img_path, 'JPEG', quality=90)
        else:
            base.save(img_path, fmt or 'PNG')

    def _position_xy(self, w, h, tw, th, position, margin):
        if position == 'top_left':
            return margin, margin
        if position == 'top_right':
            return w - tw - margin, margin
        if position == 'bottom_left':
            return margin, h - th - margin
        if position == 'center':
            return (w - tw) // 2, (h - th) // 2
        # bottom_right（默认）
        return w - tw - margin, h - th - margin
