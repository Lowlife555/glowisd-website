from PIL import Image, ImageDraw, ImageFont

BLUE = (22, 42, 135, 255)   # #162A87
GOLD = (210, 174, 0, 255)   # #D2AE00
FONT = r'C:\Windows\Fonts\arialbd.ttf'


def make_favicon(size):
    img = Image.new('RGBA', (size, size), BLUE)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, int(size * 0.74))
    bbox = draw.textbbox((0, 0), 'G', font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(
        ((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]),
        'G', fill=GOLD, font=font,
    )
    return img


for s in [16, 32, 48, 192, 512]:
    make_favicon(s).save(f'static/img/favicon-{s}.png')
    print(f'favicon-{s}.png 已生成')
