"""生成媒体图片的 WebP 多尺寸变体（性能优化用）。

背景：官网首屏曾一次下载 ~11MB 图片（60 张，单张最大 797KB），
在 2 核 2G 的服务器 + 移动端 4G 下会明显卡顿。本脚本在**构建期**把原图
转成小尺寸 WebP 变体，模板按用途引用，原图保留不动（可随时回退）。

用法：
    python scripts/make_webp.py            # 增量生成（已存在且比原图新则跳过）
    python scripts/make_webp.py --force    # 全量重生成
    python scripts/make_webp.py --stats    # 只打印统计，不写文件

输出：media/opt/<子目录>/<原文件名主干>-<宽度>.webp
"""

import argparse
import os
import sys
import time

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(ROOT, 'media')
OPT = os.path.join(MEDIA, 'opt')

#: 各类图片需要生成的宽度档位（像素）
WIDTHS = {
    'products': (320, 640, 48),   # 48 用于分类卡背景（放大后天然模糊，省掉 CSS blur 滤镜）
    'hero': (960, 1600),
    'site_images': (800, 1400),
}

#: WebP 质量
QUALITY = 78

EXTS = ('.jpg', '.jpeg', '.png', '.webp')


def variants_for(rel_path):
    """返回该相对路径需要生成的宽度列表。"""
    sub = rel_path.split(os.sep)[0]
    return WIDTHS.get(sub, (640,))


def out_path(rel_path, width):
    sub, name = os.path.split(rel_path)
    stem = os.path.splitext(name)[0]
    return os.path.join(OPT, sub, f'{stem}-{width}.webp')


def make_one(src, rel_path, width, force):
    dst = out_path(rel_path, width)
    if not force and os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return 'skip'
    try:
        with Image.open(src) as im:
            im = im.convert('RGB')
            w, h = im.size
            target_w = min(width, w)          # 不放大
            if target_w < width and width <= 64:
                pass                          # 小缩略图仍生成（不足宽时按原尺寸）
            if target_w != w:
                ratio = target_w / w
                im = im.resize((target_w, max(1, round(h * ratio))), Image.LANCZOS)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            im.save(dst, 'WEBP', quality=QUALITY, method=6)
        return 'made'
    except Exception as exc:                  # 单张失败不影响整体
        print(f'  ! {rel_path} @{width}: {exc}')
        return 'fail'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--stats', action='store_true')
    args = ap.parse_args()

    t0 = time.time()
    made = skipped = failed = 0
    src_bytes = out_bytes = 0

    for sub in WIDTHS:
        base = os.path.join(MEDIA, sub)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if not name.lower().endswith(EXTS):
                continue
            src = os.path.join(base, name)
            rel = os.path.join(sub, name)
            if args.stats:
                for w in variants_for(rel):
                    dst = out_path(rel, w)
                    if os.path.exists(dst):
                        src_bytes += os.path.getsize(src)
                        out_bytes += os.path.getsize(dst)
                        made += 1
                continue
            for w in variants_for(rel):
                r = make_one(src, rel, w, args.force)
                if r == 'made':
                    made += 1
                elif r == 'skip':
                    skipped += 1
                else:
                    failed += 1

    if args.stats:
        print(f'已有变体 {made} 个；原图合计 {src_bytes / 1024 / 1024:.1f} MB → 变体合计 {out_bytes / 1024 / 1024:.1f} MB')
        return

    total = 0
    for dirpath, _dirs, files in os.walk(OPT):
        for f in files:
            total += os.path.getsize(os.path.join(dirpath, f))
    print(f'生成 {made} 个 / 跳过 {skipped} 个 / 失败 {failed} 个；'
          f'opt 目录合计 {total / 1024 / 1024:.1f} MB，耗时 {time.time() - t0:.1f}s')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
