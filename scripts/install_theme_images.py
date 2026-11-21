"""把站内已有素材装进 SiteImage 槽位（页头主题图 + 首页工厂图）。

素材全部取自项目自有媒体（hero 大图 / 产品图 / 工厂航拍原图），无第三方授权问题。
输出：media/site_images/<key>.jpg（去 EXIF、按用途裁切），并写入对应槽位的库记录。

用法： python scripts/install_theme_images.py [--dry-run]
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from django.core.files.base import File  # noqa: E402
from PIL import Image, ImageOps  # noqa: E402

from core.models import SiteImage  # noqa: E402

SRC = os.path.join(ROOT, 'media')
OUT_DIR = os.path.join(SRC, 'site_images')

#: key: (源文件, 目标宽, 目标高, 中文说明, 英文说明, 阿语说明)
JOBS = {
    'home_factory': (
        os.path.join('products', '20170609_141530_web.jpg'),
        1600, 1200,
        '常州厂区与产线', 'Changzhou plant and production lines', 'مصنع تشانغتشو وخطوط الإنتاج',
    ),
    'custom_hero': (
        os.path.join('hero', 'hero4.jpg'),
        1600, 900,
        '摊铺机现场作业', 'Paver at work on site', 'آلة رصف في موقع العمل',
    ),
    'catalog_hero': (
        os.path.join('products', '20170215_111751_web.jpg'),
        1600, 900,
        '控制盒与线缆特写', 'Control boxes and cable harness', 'علب التحكم وضفيرة الكابلات',
    ),
    'contact_hero': (
        os.path.join('hero', 'hero1.jpg'),
        1600, 900,
        '道路施工与养护现场', 'Road construction and maintenance', 'موقع إنشاء وصيانة الطرق',
    ),
}

MAX_BYTES = 700 * 1024
QUALITY = 82


def prepare(src_path, tw, th, dst_path):
    """先按目标比例从原图居中裁切，再缩放到目标尺寸（只缩不放），去 EXIF，控制体积。"""
    with Image.open(src_path) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        w, h = im.size
        target_ratio = tw / th
        ratio = w / h
        # 1) 先裁到目标比例（保留原分辨率，之后只缩不放）
        if ratio > target_ratio:                      # 太宽 → 裁左右
            crop_w = round(h * target_ratio)
            left = (w - crop_w) // 2
            im = im.crop((left, 0, left + crop_w, h))
        elif ratio < target_ratio:                    # 太高 → 裁上下
            crop_h = round(w / target_ratio)
            top = (h - crop_h) // 2
            im = im.crop((0, top, w, top + crop_h))
        # 2) 再缩到目标尺寸
        scale = min(1.0, tw / im.width, th / im.height)
        if scale < 1.0:
            im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        q = QUALITY
        while True:
            im.save(dst_path, 'JPEG', quality=q, optimize=True, progressive=True)
            if os.path.getsize(dst_path) <= MAX_BYTES or q <= 60:
                break
            q -= 4
        return im.size, os.path.getsize(dst_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)

    for key, (rel, tw, th, zh, en, ar) in JOBS.items():
        src = os.path.join(SRC, rel)
        if not os.path.exists(src):
            print(f'! 缺源文件，跳过 {key}: {src}')
            continue
        dst = os.path.join(OUT_DIR, f'{key}.jpg')
        if args.dry_run:
            print(f'[dry-run] {key}: {rel} → {os.path.relpath(dst, ROOT)} ({tw}×{th})')
            continue
        size, nbytes = prepare(src, tw, th, dst)
        obj, _ = SiteImage.objects.get_or_create(key=key)
        # 文件已经写好，直接指向它（不走 image.save，避免 Django 再存一份带随机后缀的副本）
        obj.image.name = f'site_images/{key}.jpg'
        obj.caption_zh, obj.caption_en, obj.caption_ar = zh, en, ar
        obj.save()
        print(f'✓ {key:13} {rel:42} → {size[0]}×{size[1]} {nbytes // 1024}KB → {obj.image.url}')


if __name__ == '__main__':
    main()
