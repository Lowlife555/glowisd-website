"""
recrop_final.py — Glowisd 产品图批量重裁到"满分"标准。

目标标准（由 vision 模型从 3 张满分参考图总结）:
  - 纯白背景 #FFFFFF
  - 产品是画面唯一主体, 水平/垂直居中
  - 产品占画布宽度约 88-90% (宽型产品) / 占高度约 90% (高型产品, 避免溢出)
  - 四周约 25-30px 白色边距
  - 无顶部橙色 P/N 横幅 / 无右侧参数表格 / 无底部水印

处理流程 (每张图):
  1. 备份原图到 media/products_backup/ (幂等, 已存在则不覆盖)
  2. 去除顶部 1px 裁切残留线 (仅 _2 系列存在)
  3. 稳健检测产品主体 bbox:
     - 白底判定 r,g,b >= 240 视为背景
     - 形态学闭运算 (膨胀+腐蚀, 13px) 填平产品内部浅色/白色部件造成的孔洞
     - 连通域分析: 保留面积 >= max(1% 最大连通域, 1000px) 的所有连通域
       (产品可能由多部件/线缆组成, 取并集 bbox; 1px 残留线/角标噪声被丢弃)
     - 最大连通域面积 < 3000px 判为空白图 (无产品), 只等比缩放到目标尺寸
  4. bbox + 8px 内边距裁剪
  5. 等比缩放, 使产品占目标画布宽/高约 90% (取较小缩放比, 保证不溢出), 居中
  6. 输出纯白底 600x430 (约 1.4:1), 覆盖写回 media/products/ 同名文件

依赖: Pillow + numpy (opencv 非必需)。
"""
from pathlib import Path
import shutil
import json
import statistics

import numpy as np
from PIL import Image, ImageFilter

SRC = Path('media/products')
BACKUP = Path('media/products_backup')
STATS = Path('scripts/recrop_stats.json')

TARGET_W, TARGET_H = 600, 430
FILL = 0.90            # 产品占目标画布宽/高比例
WHITE = 240            # 白底阈值 r,g,b >= 240 视为背景
CLOSE = 13             # 闭运算核尺寸(奇数)
PAD = 8                # bbox 内边距
MIN_COMP = 1000        # 连通域绝对面积下限
MIN_COMP_FRAC = 0.01   # 连通域相对最大域面积下限
BLANK_AREA = 3000      # 最大连通域面积低于此值判为空白图
JPEG_QUALITY = 92


def masks(a):
    r = a[..., 0].astype(np.int16)
    g = a[..., 1].astype(np.int16)
    b = a[..., 2].astype(np.int16)
    white = (r >= WHITE) & (g >= WHITE) & (b >= WHITE)
    orange = (r > 180) & (g > 60) & (g < 150) & (b < 90)
    return white, orange


def crop_top_remnant(a):
    """去掉顶部 1~几 px 的裁切残留线 (整行非白, 与产品之间有空隙)."""
    h, w, _ = a.shape
    if h == 0:
        return a
    r = a[..., 0].astype(np.int16)
    g = a[..., 1].astype(np.int16)
    b = a[..., 2].astype(np.int16)
    white = (r >= WHITE) & (g >= WHITE) & (b >= WHITE)
    row_frac = white.mean(axis=1)  # 每行白色占比
    # 仅当第 0 行几乎整行非白时才处理 (残留线特征)
    if (1.0 - row_frac[0]) < 0.8:
        return a
    y = 0
    while y < min(6, h) and (1.0 - row_frac[y]) > 0.5:
        y += 1
    return a[y:, :, :]


def detect_top_orange_band(orange, w):
    """顶部橙色条检测: 顶部 70 行内若出现密集(>45% 宽)水平橙条则返回其底边, 否则 0."""
    top = orange[:70, :]
    row = top.sum(axis=1)
    for y in range(70):
        if row[y] > 0.45 * w:
            # 向下找橙条结束
            y2 = y
            while y2 + 1 < 70 and row[y2 + 1] > 0.45 * w:
                y2 += 1
            return y2 + 1
    return 0


def closing(mask, size):
    m = (mask.astype(np.uint8)) * 255
    im = Image.fromarray(m, 'L')
    d = im.filter(ImageFilter.MaxFilter(size))
    e = d.filter(ImageFilter.MinFilter(size))
    return np.asarray(e) > 127


def connected_components(mask):
    """返回连通域列表 [(area, x0, y0, x1, y1), ...], 按面积降序."""
    h, w = mask.shape
    visited = np.zeros((h, w), dtype=bool)
    comps = []
    fg = np.argwhere(mask)
    for y, x in fg:
        if visited[y, x]:
            continue
        stack = [(y, x)]
        visited[y, x] = True
        area = 0
        minx = maxx = x
        miny = maxy = y
        while stack:
            cy, cx = stack.pop()
            area += 1
            if cx < minx:
                minx = cx
            if cx > maxx:
                maxx = cx
            if cy < miny:
                miny = cy
            if cy > maxy:
                maxy = cy
            if cy > 0 and mask[cy - 1, cx] and not visited[cy - 1, cx]:
                visited[cy - 1, cx] = True
                stack.append((cy - 1, cx))
            if cy < h - 1 and mask[cy + 1, cx] and not visited[cy + 1, cx]:
                visited[cy + 1, cx] = True
                stack.append((cy + 1, cx))
            if cx > 0 and mask[cy, cx - 1] and not visited[cy, cx - 1]:
                visited[cy, cx - 1] = True
                stack.append((cy, cx - 1))
            if cx < w - 1 and mask[cy, cx + 1] and not visited[cy, cx + 1]:
                visited[cy, cx + 1] = True
                stack.append((cy, cx + 1))
        comps.append((area, minx, miny, maxx, maxy))
    comps.sort(key=lambda c: -c[0])
    return comps


def is_fullwidth_line(c, w):
    """判断连通域是否为整幅宽度的细残留线 (裁切边界 1~2px 残留)."""
    _, x0, y0, x1, y1 = c
    cw = x1 - x0 + 1
    ch = y1 - y0 + 1
    return ch <= 4 and cw >= 0.85 * w


def product_bbox(a):
    """返回 (bbox, is_blank). bbox=(x0,y0,x1,y1) 含 padding 前坐标; 空白图返回 (None, True)."""
    h, w, _ = a.shape
    white, orange = masks(a)
    # 顶部橙色条 (安全保险, 当前数据基本无)
    band = detect_top_orange_band(orange, w)
    if band > 0:
        a = a[band:, :, :]
        h, w, _ = a.shape
        white, orange = masks(a)
    fg = ~white
    if fg.sum() == 0:
        return None, True
    closed = closing(fg, CLOSE)
    comps = connected_components(closed)
    if not comps:
        return None, True
    largest = comps[0][0]
    if largest < BLANK_AREA:
        return None, True
    thresh = max(largest * MIN_COMP_FRAC, MIN_COMP)
    kept = [c for c in comps if c[0] >= thresh and not is_fullwidth_line(c, w)]
    if not kept:
        return None, True
    x0 = min(c[1] for c in kept)
    y0 = min(c[2] for c in kept)
    x1 = max(c[3] for c in kept)
    y1 = max(c[4] for c in kept)
    return (x0, y0, x1, y1), False


def rescale_centered(src, bbox):
    """裁剪 bbox(+padding 作安全缓冲) -> 等比缩放使产品恰好占 90% -> 产品居中到 600x430 白底."""
    x0, y0, x1, y1 = bbox
    h, w, _ = src.shape
    pw = x1 - x0 + 1
    ph = y1 - y0 + 1
    # 等比缩放: 宽型占宽 90%, 高型占高 90%, 取较小者保证不溢出
    scale = min(FILL * TARGET_W / pw, FILL * TARGET_H / ph)
    # 裁剪 bbox + 内边距 (安全缓冲, 避免边缘裁切)
    cx0 = max(0, x0 - PAD)
    cy0 = max(0, y0 - PAD)
    cx1 = min(w - 1, x1 + PAD)
    cy1 = min(h - 1, y1 + PAD)
    crop = src[cy0:cy1 + 1, cx0:cx1 + 1]
    nw = max(1, int(round((cx1 - cx0 + 1) * scale)))
    nh = max(1, int(round((cy1 - cy0 + 1) * scale)))
    img = Image.fromarray(crop).resize((nw, nh), Image.LANCZOS)
    # 产品在缩放后裁剪块中的偏移 (padding 缩放后)
    px0 = (x0 - cx0) * scale
    py0 = (y0 - cy0) * scale
    pw_s = pw * scale
    ph_s = ph * scale
    # 让产品(而非含 padding 的裁剪块)严格居中
    canvas = Image.new('RGB', (TARGET_W, TARGET_H), (255, 255, 255))
    ox = int(round((TARGET_W - pw_s) / 2 - px0))
    oy = int(round((TARGET_H - ph_s) / 2 - py0))
    canvas.paste(img, (ox, oy))
    return canvas


def measure_ratio(a):
    """用同一套稳健 bbox 算法测量产品占宽/占高比例 (用于处理前后对比)."""
    h, w, _ = a.shape
    bbox, blank = product_bbox(a)
    if blank or bbox is None:
        return 0.0, 0.0, True
    x0, y0, x1, y1 = bbox
    return (x1 - x0 + 1) / w, (y1 - y0 + 1) / h, False


def main():
    # 1) 备份
    BACKUP.mkdir(exist_ok=True)
    files = sorted(SRC.glob('*.jpg'))
    for p in files:
        dst = BACKUP / p.name
        if not dst.exists():
            shutil.copy2(p, dst)

    stats = []
    for p in files:
        orig = np.array(Image.open(p).convert('RGB'))
        bw_before, bh_before, blank_before = measure_ratio(orig)

        a = crop_top_remnant(orig)
        bbox, blank = product_bbox(a)
        if blank or bbox is None:
            # 空白图: 等比缩放到目标尺寸(不裁剪), 保持纯白
            img = Image.fromarray(orig).convert('RGB')
            img.thumbnail((TARGET_W, TARGET_H), Image.LANCZOS)
            canvas = Image.new('RGB', (TARGET_W, TARGET_H), (255, 255, 255))
            canvas.paste(img, ((TARGET_W - img.width) // 2, (TARGET_H - img.height) // 2))
        else:
            canvas = rescale_centered(a, bbox)
        canvas.save(p, 'JPEG', quality=JPEG_QUALITY, optimize=True)

        out = np.array(canvas)
        bw_after, bh_after, blank_after = measure_ratio(out)
        stats.append({
            'name': p.name,
            'before_w': round(bw_before, 4),
            'before_h': round(bh_before, 4),
            'before_fill': round(max(bw_before, bh_before), 4),
            'after_w': round(bw_after, 4),
            'after_h': round(bh_after, 4),
            'after_fill': round(max(bw_after, bh_after), 4),
            'blank': bool(blank_before or blank_after),
        })

    # 2) 汇总
    STATS.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')

    blanks = [s['name'] for s in stats if s['blank']]
    n = len(stats)
    print(f'processed {n} images (blank: {len(blanks)} -> {blanks})')
    # 主指标: 填充比 = max(占宽, 占高), 宽型产品取宽, 高型产品取高
    afs = sorted(s['after_fill'] for s in stats if not s['blank'])
    if afs:
        print(f'after fill ratio (max dim): min={afs[0]:.3f} max={afs[-1]:.3f} '
              f'mean={statistics.mean(afs):.3f} median={statistics.median(afs):.3f}')
        print(f'  in [0.86, 0.92]: {sum(1 for v in afs if 0.86 <= v <= 0.92)} / {len(afs)}')
        print(f'  <0.86: {sum(1 for v in afs if v < 0.86)}   >0.92: {sum(1 for v in afs if v > 0.92)}')
    aws = sorted(s['after_w'] for s in stats if not s['blank'])
    if aws:
        print(f'after width ratio: min={aws[0]:.3f} max={aws[-1]:.3f} '
              f'mean={statistics.mean(aws):.3f} median={statistics.median(aws):.3f}')
        print(f'  <0.70: {sum(1 for v in aws if v < 0.70)}   >0.95: {sum(1 for v in aws if v > 0.95)}')
        print(f'  in [0.86, 0.92]: {sum(1 for v in aws if 0.86 <= v <= 0.92)}')
    bws = sorted(s['before_w'] for s in stats if not s['blank'])
    if bws:
        print(f'before width ratio: min={bws[0]:.3f} max={bws[-1]:.3f} '
              f'mean={statistics.mean(bws):.3f} median={statistics.median(bws):.3f}')
        print(f'  <0.70: {sum(1 for v in bws if v < 0.70)}   >0.95: {sum(1 for v in bws if v > 0.95)}')


if __name__ == '__main__':
    main()
