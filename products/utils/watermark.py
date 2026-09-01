"""产品图自动打水印工具。

水印参数来源（阶段1 vision 采样确定，采样脚本见根目录 _wm_gen_test.py）：
    - logo：static/img/logo.png（RGBA 透明底）
    - 宽度：产品图宽的 18%（等比缩放）
    - 不透明度：75%（对 logo 的 alpha 通道 point(lambda a: a * 75 // 100)）
    - 位置：左上角，距左/上边缘 25px
    - 用途：B2B 工业配件，水印用于品牌保护防盗图

只做「就地覆盖保存」的单张图处理，供 Product.save() 自动调用；批量/可配置水印
走 products/management/commands/apply_watermark.py（参数来自 core.SiteSettings）。
"""
import logging
import os

from django.conf import settings
from PIL import Image

logger = logging.getLogger(__name__)

# 水印 logo 路径：static/img/logo.png
WATERMARK_LOGO_PATH = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.png')

# 水印参数（阶段1 vision 采样确定，勿随意改动）
WATERMARK_WIDTH_PCT = 18        # 水印宽度 = 产品图宽的 18%
WATERMARK_OPACITY = 75          # 不透明度 75%
WATERMARK_MARGIN_PX = 25        # 距左/上边缘 25px

# 近白阈值：仅当 logo 为不透明白底时用于去底
_WHITE_THRESHOLD = 245


def add_watermark(image_path, logo_path):
    """给产品图就地打水印。

    成功返回 True；任何异常被捕获并打印日志、返回 False，绝不向上抛异常。
    """
    try:
        if not os.path.exists(image_path):
            logger.error('水印失败：产品图不存在 %s', image_path)
            return False
        if not os.path.exists(logo_path):
            logger.error('水印失败：logo 不存在 %s', logo_path)
            return False

        # 1. 打开产品图转 RGB；RGBA/透明图先贴白底，避免透明底合成后发黑
        with Image.open(image_path) as src:
            fmt = src.format
            if src.mode in ('RGBA', 'LA') or (src.mode == 'P' and 'transparency' in src.info):
                base = _flatten_on_white(src)
            else:
                base = src.convert('RGB')
        w, h = base.size

        # 2. 打开 logo 转 RGBA；若为不透明白底则近白去底（透明底 logo 不受影响）
        with Image.open(logo_path) as src_logo:
            logo = _strip_white_background(src_logo.convert('RGBA'))

        # 3. 等比缩放到产品图宽的 18%
        target_w = max(1, int(w * WATERMARK_WIDTH_PCT / 100))
        target_h = max(1, int(logo.height * target_w / logo.width))
        logo = logo.resize((target_w, target_h), Image.LANCZOS)

        # 4. 调不透明度 75%（缩放后 alpha 通道按比例衰减）
        alpha = logo.getchannel('A').point(lambda a: a * WATERMARK_OPACITY // 100)
        logo.putalpha(alpha)

        # 5. 粘贴到左上角（距左/上边缘 25px）
        x = WATERMARK_MARGIN_PX
        y = WATERMARK_MARGIN_PX
        base.paste(logo, (x, y), logo)

        # 6. 存回：JPEG quality=90，PNG 保持 PNG，其余一律按 PNG 存
        if fmt == 'JPEG':
            base.save(image_path, 'JPEG', quality=90)
        else:
            base.save(image_path, 'PNG')
        return True
    except Exception:  # noqa: BLE001
        logger.exception('水印失败：%s', image_path)
        return False


def _flatten_on_white(img):
    """把 RGBA/LA/P(带透明) 图贴到白底上，返回 RGB 图。"""
    rgba = img.convert('RGBA')
    bg = Image.new('RGB', rgba.size, (255, 255, 255))
    bg.paste(rgba, mask=rgba.getchannel('A'))
    return bg


def _strip_white_background(rgba):
    """仅当 logo 为不透明白底时，将近白像素 alpha 置 0 去底；透明底 logo 保持原样。"""
    a = rgba.getchannel('A')
    if a.getextrema()[0] >= 250:  # alpha 全不透明 → 说明是白底 logo，需要去底
        gray = rgba.convert('RGB').convert('L')
        near_white = gray.point(lambda v: 255 if v >= _WHITE_THRESHOLD else 0)
        new_a = Image.composite(Image.new('L', rgba.size, 0), a, near_white)
        rgba.putalpha(new_a)
    return rgba
