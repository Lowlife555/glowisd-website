import os
from functools import lru_cache

from django import template
from django.conf import settings as dj_settings

from products.models import Category

register = template.Library()


@lru_cache(maxsize=4096)
def _variant_path(rel):
    """WebP 变体是否存在（结果永久缓存：单进程内每个变体只 stat 一次）。

    没有这层缓存时，首页 60 张产品卡 × (src + srcset) 会做上百次 os.path.exists，
    每次都是文件系统调用；缓存后整页渲染只剩字典查找。
    部署新图后变体不会立刻出现？重启进程即可（变体由 scripts/make_webp.py 生成）。
    """
    return os.path.exists(os.path.join(dj_settings.MEDIA_ROOT, rel))


def _variant_url(image, width):
    """取 WebP 变体 URL；变体不存在时回退原图（脚本 scripts/make_webp.py 生成）。

    性能背景：原图单张最大 797KB，首屏一次拉 60 张共 ~11MB。变体 320w 约 22KB。
    """
    if not image:
        return ''
    try:
        original = image.url
    except (ValueError, AttributeError):
        return ''
    name = getattr(image, 'name', '') or ''
    if not name:
        return original
    sub, fname = os.path.split(name)
    stem = os.path.splitext(fname)[0]
    rel = f'opt/{sub}/{stem}-{width}.webp'
    if _variant_path(rel):
        # 带版本号：nginx 里 /media/opt/ 可长缓存（30 天），部署升版即自动失效
        ver = getattr(dj_settings, 'SITE_VERSION', '0')
        return f'{dj_settings.MEDIA_URL}{rel}?v={ver}'
    return original


@register.simple_tag
def opt_img(image, width=640):
    """模板用：{% opt_img p.image 640 %} → 优化后的图片 URL（无变体时回退原图）"""
    try:
        width = int(width)
    except (TypeError, ValueError):
        width = 640
    return _variant_url(image, width)


@register.simple_tag
def opt_srcset(image, widths='320,640'):
    """模板用：{% opt_srcset p.image "320,640" %} → "url 320w, url 640w"（供 srcset）

    只输出真实存在的变体：缺变体时返回空串，由模板的 src（回退原图）兜底。
    绝不能把同一个原图按不同 width 描述符重复输出 —— 那样浏览器会按声明的宽度
    误判该下哪张，属于错误的声明。
    """
    if not image:
        return ''
    name = getattr(image, 'name', '') or ''
    if not name:
        return ''
    sub, fname = os.path.split(name)
    stem = os.path.splitext(fname)[0]
    ver = getattr(dj_settings, 'SITE_VERSION', '0')
    parts = []
    for raw in str(widths).split(','):
        raw = raw.strip()
        if not raw.isdigit():
            continue
        rel = f'opt/{sub}/{stem}-{raw}.webp'
        if _variant_path(rel):
            parts.append(f'{dj_settings.MEDIA_URL}{rel}?v={ver} {raw}w')
    return ', '.join(parts)


@register.filter
def pname(product, lang='zh'):
    """产品名：按语言取 part_name / part_name_en / part_name_ar（空值自动回退）"""
    return product.display_name(lang)


@register.filter
def pdesc(product, lang='zh'):
    """产品描述：按语言取值（阿语为空回退英文，英文为空回退中文）"""
    return product.display_description(lang)


@register.filter
def cname(category, lang='zh'):
    """分类名：按语言取 name / name_en / name_ar（空值自动回退）"""
    return category.display_name(lang)


@register.simple_tag
def cat_cover(category):
    """分类卡片封面图 URL：优先分类封面，其次该分类第一个有图产品。

    取 48px 变体：卡片背景图会被放大铺满，小图缩放本身就是天然模糊，
    可以去掉原来的 CSS `filter: blur(7px)`（滤镜在每个卡片上滚动时都要重算，很贵）。
    """
    image = category.cover_or_first_product_image()
    if not image:
        return ''
    return _variant_url(image, 48) or image.url


@register.simple_tag
def footer_categories(limit=6):
    """页脚产品分类快捷入口"""
    return Category.objects.all()[:limit]


@register.simple_tag
def product_completeness(obj):
    """产品资料完整度百分比（0-100），用于后台编辑页顶部进度条。"""
    if obj is None or obj.pk is None:
        return 0
    return obj.completeness_percent()
