from collections import Counter

from PIL import Image

img = Image.open(r'C:\Users\15782\Desktop\dsh_glowised_website\site\glowisd-website\static\img\logo.png').convert('RGBA')
pixels = []
for r, g, b, a in img.getdata():
    if a > 128:
        pixels.append((r, g, b))

print(f'非透明像素: {len(pixels)}')

# 精确颜色计数
counter = Counter(pixels)
print('=== 出现次数最多的颜色（精确）===')
for color, count in counter.most_common(15):
    print(f'RGB{color} #{color[0]:02X}{color[1]:02X}{color[2]:02X}  {count}')

# 量化到 32 级（聚类相近颜色）
def quant(c):
    return tuple(x // 32 * 32 for x in c)

qcounter = Counter(quant(c) for c in pixels)
print('=== 量化主色（32级聚类）===')
for color, count in qcounter.most_common(12):
    print(f'#{color[0]:02X}{color[1]:02X}{color[2]:02X}  {count}')
