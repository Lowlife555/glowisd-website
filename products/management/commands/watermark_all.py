"""批量触发 save() 钩子给产品图打水印。

用法：
    python manage.py watermark_all            # 处理所有 is_watermarked=False 且图片非空的产品
    python manage.py watermark_all --force    # 先把全部产品 is_watermarked 置回 False，再全量重打

水印参数来自 products/utils/watermark.py（阶段1 vision 采样：宽18%/不透明75%/右下角/边距25px），
由 Product.save() 钩子自动调用 add_watermark() 就地覆盖；本命令只负责遍历与统计，不直接改图。
"""
import os

from django.core.management.base import BaseCommand

from products.models import Product
from products.utils.watermark import WATERMARK_LOGO_PATH


class Command(BaseCommand):
    help = '遍历产品调用 save() 触发水印钩子，统计成功/失败/跳过'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true', dest='force', default=False,
            help='先把全部产品 is_watermarked 置回 False，再全量重打水印',
        )

    def handle(self, *args, **options):
        if options.get('force'):
            reset = Product.objects.filter(is_watermarked=True).update(is_watermarked=False)
            self.stdout.write(self.style.WARNING(
                f'--force：已把 {reset} 个产品 is_watermarked 置回 False'
            ))

        success = 0
        failed = 0
        skipped = 0

        for product in Product.objects.all():
            # 已打水印 → 跳过
            if product.is_watermarked:
                skipped += 1
                continue
            # 无产品图 → 跳过
            if not product.image:
                skipped += 1
                continue

            # 触发 save 钩子：save() 内部检测到有图且未打水印 → 调 add_watermark 并写回标记
            product.save()

            if product.is_watermarked:
                success += 1
                self.stdout.write(self.style.SUCCESS(
                    f'已打水印 #{product.pk}（{product.sku}）：{product.image.name}'
                ))
            else:
                failed += 1
                self.stdout.write(self.style.ERROR(
                    f'打水印失败 #{product.pk}（{product.sku}）：{self._failure_reason(product)}'
                ))

        total_done = Product.objects.filter(is_watermarked=True).count()
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'水印处理完成：成功 {success} 个 / 失败 {failed} 个 / 跳过 {skipped} 个；'
            f'当前 is_watermarked=True 总数 {total_done} 个'
        ))

    def _failure_reason(self, product):
        """save 钩子吞掉异常只返回 bool，这里补充常见失败原因用于打印。"""
        img_path = product.image.path if product.image else ''
        if not img_path or not os.path.exists(img_path):
            return '产品图文件不存在'
        if not os.path.exists(WATERMARK_LOGO_PATH):
            return f'水印 logo 不存在：{WATERMARK_LOGO_PATH}'
        return 'add_watermark 处理失败（详见运行日志）'
