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
