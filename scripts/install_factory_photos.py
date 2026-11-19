"""工厂照片批量预处理 / 本地安装（V0.14.1 工具）。

背景：站点图片 7 个槽位（SiteImage.KEY_CHOICES）在后台一个一个上传很麻烦，
且原始手机照常见问题——竖图、超大体积、带 EXIF（含 GPS/机型）。本脚本负责：

1. `--prepare`：把一个文件夹里的原始照片统一成站点需要的规格
   （4:3 居中裁切、1600×1200、JPEG q82、去 EXIF、目标体积 < 400KB），
   输出到 `--out` 目录，文件名改成槽位 key，直接拖进后台对应槽位即可。
2. `--install`：本地开发库直接写 SiteImage（含三语说明），用来看效果预览。

用法：
    # 把 ../工厂照片 里的原图整理成可上传成品
    venv/bin/python scripts/install_factory_photos.py prepare --src ../工厂照片 --out ../工厂照片-ready

    # 本地预览安装（不改生产）
    venv/bin/python scripts/install_factory_photos.py install --src ../工厂照片-ready --dry-run
    venv/bin/python scripts/install_factory_photos.py install --src ../工厂照片-ready

文件命名约定：用槽位 key 命名，例：
    factory_hero.jpg  workshop_1.jpg  workshop_2.jpg  workshop_3.jpg
    workshop_4.jpg    home_factory.jpg  custom_hero.jpg
其它名字的文件会被忽略并打印提示。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

TARGET_W, TARGET_H = 1600, 1200          # 4:3，与 .photo-frame / .photo-grid 一致
MAX_BYTES = 400 * 1024
EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}

# 槽位 -> 三语说明（与模板默认文案一致）
CAPTIONS = {
    'home_factory': ('工厂车间', 'Factory workshop', 'ورشة المصنع'),
    'factory_hero': ('工厂外景', 'Factory building', 'مبنى المصنع'),
    'workshop_1': ('组装产线', 'Assembly line', 'خط التجميع'),
    'workshop_2': ('CNC 加工区', 'CNC machining area', 'منطقة التصنيع CNC'),
    'workshop_3': ('检测与标定', 'Testing and calibration', 'الاختبار والمعايرة'),
    'workshop_4': ('成品仓储', 'Finished goods warehouse', 'مخزن المنتجات النهائية'),
    'custom_hero': ('定制服务', 'Custom manufacturing', 'التصنيع حسب الطلب'),
}


def _slug(filename: str) -> str:
    return Path(filename).stem.strip().lower().replace('-', '_').replace(' ', '_')


def prepare(src: Path, out: Path) -> int:
    from PIL import Image, ImageOps

    out.mkdir(parents=True, exist_ok=True)
    found = {}
    for p in sorted(src.iterdir()):
        if not p.is_file() or p.suffix.lower() not in EXTS:
            continue
        key = _slug(p.name)
        if key not in CAPTIONS:
            print(f'  跳过（文件名不是槽位 key）: {p.name}')
            continue
        if key in found:
            print(f'  跳过（重复）: {p.name}，已用 {found[key]}')
            continue
        found[key] = p.name

        with Image.open(p) as im:
            im = ImageOps.exif_transpose(im)          # 按 EXIF 方向摆正
            im = im.convert('RGB')
            # 居中裁成 4:3；源图比目标小时**不放大**（避免糊），按比例缩到能放下为止
            scale = min(1.0, im.width / TARGET_W, im.height / TARGET_H)
            tw, th = max(1, int(TARGET_W * scale)), max(1, int(TARGET_H * scale))
            fitted = ImageOps.fit(im, (tw, th), method=Image.LANCZOS, centering=(0.5, 0.5))
            if scale < 1.0:
                print(f'  注意：源图 {im.width}x{im.height} 小于 {TARGET_W}x{TARGET_H}，按原尺寸输出 {tw}x{th}（不放大）')

        dst = out / f'{key}.jpg'
        quality = 82
        while True:
            fitted.save(dst, 'JPEG', quality=quality, optimize=True, progressive=True)
            if dst.stat().st_size <= MAX_BYTES or quality <= 55:
                break
            quality -= 6
        print(f'  {p.name} -> {dst.name}  {fitted.width}x{fitted.height}  {dst.stat().st_size // 1024}KB (q{quality})')

    missing = [k for k in CAPTIONS if k not in found]
    print(f'\n完成：{len(found)}/{len(CAPTIONS)} 个槽位有图，输出目录 {out}')
    if missing:
        print('仍缺:', ', '.join(missing))
    print('\n下一步：打开后台「站点图片」，把对应文件拖进同名槽位；或运行 install 子命令做本地预览。')
    return 0 if found else 1


def install(src: Path, dry_run: bool) -> int:
    import django

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

    from django.core.files import File

    from core.models import SiteImage

    done = 0
    for key, (zh, en, ar) in CAPTIONS.items():
        path = next((src / f'{key}{ext}' for ext in ('.jpg', '.jpeg', '.png', '.webp')
                     if (src / f'{key}{ext}').exists()), None)
        if not path:
            print(f'  缺图: {key}')
            continue
        if dry_run:
            print(f'  [dry-run] {key} <- {path.name} ({path.stat().st_size // 1024}KB)')
            done += 1
            continue
        obj, _ = SiteImage.objects.get_or_create(key=key)
        with path.open('rb') as fh:
            obj.image.save(path.name, File(fh), save=False)
        obj.caption_zh, obj.caption_en, obj.caption_ar = zh, en, ar
        obj.save()
        print(f'  已安装 {key} <- {path.name}')
        done += 1
    print(f'\n{"[dry-run] " if dry_run else ""}处理 {done}/{len(CAPTIONS)} 个槽位')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description='工厂照片批量预处理 / 本地安装')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p1 = sub.add_parser('prepare', help='统一规格，输出可直接上传的成品')
    p1.add_argument('--src', required=True, type=Path, help='原始照片文件夹')
    p1.add_argument('--out', required=True, type=Path, help='输出文件夹')

    p2 = sub.add_parser('install', help='写本地数据库做预览（生产请用后台上传）')
    p2.add_argument('--src', required=True, type=Path, help='已整理好的照片文件夹')
    p2.add_argument('--dry-run', action='store_true')

    args = ap.parse_args()
    if not args.src.is_dir():
        print(f'目录不存在: {args.src}')
        return 2
    if args.cmd == 'prepare':
        return prepare(args.src, args.out)
    return install(args.src, args.dry_run)


if __name__ == '__main__':
    raise SystemExit(main())
