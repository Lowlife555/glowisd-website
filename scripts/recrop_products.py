from pathlib import Path

from PIL import Image

# ---------------------------------------------------------------------------
# Recrop product photos to "product + white background only".

# Defects found on every media/products/*.jpg (564px wide, already horizontally
# shortened by a previous pass that removed the right-side table):
#   1. TOP orange part-number band with white text "R202419xxx"  -> crop off.
#   2. Possible right-side Part/P/N/Brand/Weight/Warranty table   -> crop off.
#   3. Any leftover numeric text (PDF-XXX-XX / part numbers).      -> crop off.
#
# Measured from a sample of all 183 images (band colour ~ (225,96,2)):
#   - The orange band always occupies the top rows, bottom edge = 57 or 58.
#   - After the previous left-crop, the product already starts at/after y=59,
#     so TopCut=59 removes the band without touching the product.
#   - The product spans the full width edge-to-edge; no right-table remnant
#     is present on these 564px images, so the horizontal cut is a safety
#     pass that only trims a right-hand table column when one is detected.
# ---------------------------------------------------------------------------

def is_orange(r, g, b):
    return r > 180 and 60 < g < 150 and b < 90 and (r - b) > 120

def is_white(r, g, b):
    return r > 230 and g > 230 and b > 230

def is_grey(r, g, b):
    return 200 <= r <= 246 and 200 <= g <= 246 and 200 <= b <= 246 and abs(r - b) < 14

# Vertical cut: discard rows [0, TOP_CUT); the orange band bottom is 57/58.
TOP_CUT = 59

# Horizontal safety cut: search the region x in [0.78*W, W) for a column of
# dense grey "table stripe" cells; if found, crop just before it. Otherwise
# keep the full width (product spans edge-to-edge).
RIGHT_SCAN_FROM = 0.78
GREY_CUTOFF = 1200  # min grey pixel count in the right region to call it a table

src = Path('media/products')
count = 0
h_cut_list = []
for p in sorted(src.glob('*.jpg')):
    img = Image.open(p).convert('RGB')
    w, h = img.size
    px = img.load()

    # --- vertical: remove top orange band ---
    top = TOP_CUT
    # If this image happens to have no orange band (already cropped), keep it.
    has_band = any(
        sum(1 for x in range(0, w, 4) if is_orange(*px[x, y])) > w / 4 * 0.5
        for y in range(top)
    )
    if has_band:
        crop_top = top
    else:
        crop_top = 0

    # --- horizontal safety: trim a right-hand table column if present ---
    crop_right = w
    if w > 100:
        grey = 0
        for y in range(crop_top, h):
            for x in range(int(w * RIGHT_SCAN_FROM), w):
                if is_grey(*px[x, y]):
                    grey += 1
        if grey > GREY_CUTOFF:
            # Walk columns from the left of the scan region to find the first
            # column that is mostly white = start of the table's left edge.
            for cx in range(int(w * RIGHT_SCAN_FROM), w):
                col_white = sum(1 for y in range(crop_top, h, 2) if is_white(*px[cx, y]))
                if col_white > (h - crop_top) / 2 * 0.55:
                    crop_right = max(crop_right, cx)
                    break

    cropped = img.crop((0, crop_top, crop_right, h))
    cropped.save(p, 'JPEG', quality=90, optimize=True)
    count += 1
    h_cut_list.append((p.name, w, h, crop_top, crop_right))

print(f'recropped {count} images')
if h_cut_list:
    names = [n for n, *_ in h_cut_list]
    tops = sorted(set(t for _, _, _, t, _ in h_cut_list))
    rights = sorted(set(r for _, _, _, _, r in h_cut_list))
    print(f'vertical crop rows (top cut): {len(names)} images -> values {tops}')
    print(f'horizontal right edges: values {rights}')
    # summary of cropped dimensions
    from collections import Counter
    new_sizes = Counter()
    for n, w, h, t, r in h_cut_list:
        new_sizes[(r - 0, h - t)] += 1
    for size, cnt in sorted(new_sizes.items()):
        print(f'  new size {size[0]}x{size[1]} : {cnt} images')
