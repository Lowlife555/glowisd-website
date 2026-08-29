import fitz

ai_path = r'C:\Users\15782\Desktop\dsh_glowised_website\素材\logo\Glowisd (1).ai'
out_png = r'C:\Users\15782\Desktop\dsh_glowised_website\site\glowisd-website\static\img\logo.png'
out_favicon = r'C:\Users\15782\Desktop\dsh_glowised_website\site\glowisd-website\static\img\favicon-logo.png'

doc = fitz.open(ai_path)
print(f'页数: {doc.page_count}')
for i, page in enumerate(doc):
    imgs = page.get_images()
    print(f'第{i+1}页: 尺寸 {page.rect.width:.0f}x{page.rect.height:.0f}pt, 内嵌图片 {len(imgs)} 张')

page = doc[0]
# 渲染为 PNG（透明背景，300 DPI）
pix = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72), alpha=True)
pix.save(out_png)
print(f'已保存 logo.png: {pix.width}x{pix.height}')

# favicon 缩到 64x64
pix_small = page.get_pixmap(matrix=fitz.Matrix(64 / page.rect.width, 64 / page.rect.width), alpha=True)
pix_small.save(out_favicon)
print(f'已保存 favicon-logo.png: {pix_small.width}x{pix_small.height}')
