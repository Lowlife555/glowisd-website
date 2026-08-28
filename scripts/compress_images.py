from pathlib import Path

from PIL import Image

src = Path('media/products')
count = 0
for p in sorted(src.glob('*.png')):
    img = Image.open(p).convert('RGB')
    w, h = img.size
    if max(w, h) > 1200:
        scale = 1200 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    out = p.with_suffix('.jpg')
    img.save(out, 'JPEG', quality=82, optimize=True)
    p.unlink()
    count += 1

print(f'compressed {count} images')
