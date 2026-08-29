from pathlib import Path

from PIL import Image

# Reference: products/fixtures/examples/ex3_crop.jpg blue box right edge ~ 0.425.
# Current product images: table column starts at x ~= 0.473; product pixels end ~ 0.464.
# Crop ratio leaves a margin before the table while keeping the full product.
CROP_RATIO = 0.47

src = Path('media/products')
count = 0
for p in sorted(src.glob('*.jpg')):
    img = Image.open(p).convert('RGB')
    w, h = img.size
    if w < 600:  # already recropped / smaller than a native product page width
        continue
    new_w = int(w * CROP_RATIO)
    img.crop((0, 0, new_w, h)).save(p, 'JPEG', quality=90, optimize=True)
    count += 1

print(f'recropped {count} images to left {CROP_RATIO*100:.0f}% width')
