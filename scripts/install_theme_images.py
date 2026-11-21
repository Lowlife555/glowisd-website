"""把站内已有素材装进 SiteImage 固定槽位（页头主题图 + 首页工厂图）。

素材全部取自项目自有媒体（hero 大图 / 工厂航拍），无第三方授权问题 —— 不引入任何外链图库。
输出：media/site_images/<key>.jpg（按用途裁切、去 EXIF），并写入对应槽位的库记录与三语说明。

用法：
    python scripts/install_theme_images.py            # 生成 + 写库
    python scripts/install_theme_images.py --dry-run  # 只看会做什么

说明：
- 源文件缺失但目标文件已存在时，保留现有目标文件、只补库记录（便于老图继续用）。
- 裁切锚点 (ax, ay) 0–1 决定保留原图的哪一部分（0=左/上，1=右/下），用来避开主体被裁掉。
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from PIL import Image, ImageOps  # noqa: E402

from core.models import SiteImage  # noqa: E402

SRC = os.path.join(ROOT, 'media')
OUT_DIR = os.path.join(SRC, 'site_images')

#: key: (源文件, 目标宽, 目标高, 裁切锚点 x, 裁切锚点 y, 中文, 英文, 阿语)
JOBS = {
    'home_factory': (
        os.path.join('site_images', 'factory_hero.jpg'),
        1600, 1200, 0.50, 0.55,
        '常州工厂厂区', 'Changzhou plant', 'مصنع تشانغتشو',
    ),
    'custom_hero': (
        os.path.join('hero', 'hero4.jpg'),
        1600, 900, 0.62, 0.45,
        '摊铺机现场作业与调试', 'Paver on site: operation and tuning',
        'آلة رصف في الموقع: التشغيل والمعايرة',
    ),
    'catalog_hero': (
        os.path.join('site_images', 'catalog_hero.jpg'),
        1600, 900, 0.50, 0.50,
        '控制盒与线缆特写', 'Control boxes and cable harness', 'علب التحكم وضفيرة الكابلات',
    ),
    'contact_hero': (
        os.path.join('hero', 'hero5.jpg'),
        1600, 900, 0.55, 0.50,
        '整机发运与现场支持', 'Equipment shipping and on-site support',
        'شحن المعدات والدعم الميداني',
    ),
}

MAX_BYTES = 700 * 1024
QUALITY = 84


def prepare(src_path, tw, th, ax, ay, dst_path):
    """按目标比例裁切（锚点决定保留区域）→ 只缩不放 → 控制体积 → 去掉 EXIF。"""
    with Image.open(src_path) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        w, h = im.size
        target_ratio = tw / th
        if w / h > target_ratio:                      # 太宽 → 裁左右
            crop_w = round(h * target_ratio)
            left = round((w - crop_w) * ax)
            im = im.crop((left, 0, left + crop_w, h))
        elif w / h < target_ratio:                    # 太高 → 裁上下
            crop_h = round(w / target_ratio)
            top = round((h - crop_h) * ay)
            im = im.crop((0, top, w, top + crop_h))
        scale = min(1.0, tw / im.width, th / im.height)  # 只缩不放，避免糊
        if scale < 1.0:
            im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))),
                           Image.LANCZOS)
        q = QUALITY
        while True:
            im.save(dst_path, 'JPEG', quality=q, optimize=True, progressive=True)
            if os.path.getsize(dst_path) <= MAX_BYTES or q <= 62:
                break
            q -= 4
        return im.size, os.path.getsize(dst_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)

    for key, (rel, tw, th, ax, ay, zh, en, ar) in JOBS.items():
        src = os.path.join(SRC, rel.replace('/', os.sep))
        dst = os.path.join(OUT_DIR, f'{key}.jpg')
        if os.path.abspath(src) != os.path.abspath(dst) and not os.path.exists(src):
            if os.path.exists(dst):
                print(f'· {key:13} 源缺失，沿用现有 {os.path.relpath(dst, ROOT)}')
            else:
                print(f'! {key:13} 源与目标都缺失，跳过（{rel}）')
                continue
        else:
            if args.dry_run:
                print(f'[dry-run] {key}: {rel} → site_images/{key}.jpg ({tw}×{th})')
                continue
            size, nbytes = prepare(src, tw, th, ax, ay, dst)
            print(f'✓ {key:13} {rel:34} → {size[0]}×{size[1]} {nbytes // 1024}KB')

        if args.dry_run:
            continue
        obj, _ = SiteImage.objects.get_or_create(key=key)
        obj.image.name = f'site_images/{key}.jpg'   # 文件已就位，不再走 storage 复制
        obj.caption_zh, obj.caption_en, obj.caption_ar = zh, en, ar
        obj.save()
        print(f'  库记录：{key} → {obj.image.url}')


if __name__ == '__main__':
    main()
