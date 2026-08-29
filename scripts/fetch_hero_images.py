"""Download on-theme (paver / road construction) hero images from Pexels and
normalize them to 1920x1080 cover crops, overwriting media/hero/hero1..6.jpg.

Pexels license: free for commercial use, no attribution required.
"""
import io
import urllib.request

from PIL import Image

BASE = 'https://images.pexels.com/photos/{pid}/pexels-photo-{pid}.jpeg'

# pid -> hero slot. All are on-theme (paver / asphalt / road construction).
PLAN = [
    (10000255, 'hero1.jpg'),   # A paving machine laying asphalt on a rural road
    (37820986, 'hero2.jpg'),   # Asphalt paver resurfacing a rural road under blue sky
    (34287627, 'hero3.jpg'),   # Yellow road construction machine applying asphalt
    (37981110, 'hero4.jpg'),   # Worker operating a Weiler P385C paver
    (34053335, 'hero5.jpg'),   # Paving equipment and crew working on road construction
    (29181420, 'hero6.jpg'),   # Road paving machine on a scenic autumn highway
]

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'}
TARGET_W, TARGET_H = 1920, 1080


def cover_crop(img: Image.Image) -> Image.Image:
    """Resize + center-crop to fill TARGET_W x TARGET_H."""
    sw, sh = img.size
    scale = max(TARGET_W / sw, TARGET_H / sh)
    nw, nh = int(round(sw * scale)), int(round(sh * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - TARGET_W) // 2
    top = (nh - TARGET_H) // 2
    return img.crop((left, top, left + TARGET_W, top + TARGET_H))


for pid, out_name in PLAN:
    url = BASE.format(pid=pid) + '?auto=compress&cs=tinysrgb&w=1920'
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        img = Image.open(io.BytesIO(data)).convert('RGB')
        print(f'{out_name}  <- photo-{pid}  raw {img.size}  {len(data)//1024}KB')
        img = cover_crop(img)
        img.save('media/hero/' + out_name, 'JPEG', quality=86)
        print(f'   saved 1920x1080')
    except Exception as e:
        print(f'{out_name}  <- photo-{pid}  FAILED: {e}')
