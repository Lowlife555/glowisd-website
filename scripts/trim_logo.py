from PIL import Image

src = r'C:\Users\15782\Desktop\dsh_glowised_website\site\glowisd-website\static\img\logo.png'
img = Image.open(src).convert('RGBA')

print('原图尺寸:', img.size)
bbox = img.getbbox()
print('内容边界(非透明):', bbox)

if bbox:
    w, h = img.size
    bx, by, bx2, by2 = bbox
    print(f'内容占宽: {(bx2-bx)/w*100:.1f}%, 占高: {(by2-by)/h*100:.1f}%')
    # 裁掉透明留白
    cropped = img.crop(bbox)
    cropped.save(src)
    print('已裁掉留白，新尺寸:', cropped.size)
