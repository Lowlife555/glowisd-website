from django import template

from products.models import Category

register = template.Library()


@register.filter
def pname(product, lang='zh'):
    """产品名：按语言取 part_name / part_name_en（空值自动回退）"""
    return product.display_name(lang)


@register.filter
def cname(category, lang='zh'):
    """分类名：按语言取 name / name_en"""
    return category.name_en if lang == 'en' else category.name


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
