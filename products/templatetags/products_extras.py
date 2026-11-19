from django import template

from products.models import Category

register = template.Library()


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
    """分类卡片封面图 URL：优先分类封面，其次该分类第一个有图产品。"""
    image = category.cover_or_first_product_image()
    return image.url if image else ''


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
