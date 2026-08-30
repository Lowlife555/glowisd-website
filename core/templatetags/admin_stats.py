from django import template

from core.models import LoginRecord
from products.models import Category, ContactMessage, Product

register = template.Library()


@register.simple_tag
def admin_stats():
    """后台首页统计卡片数据。"""
    return {
        'products': Product.objects.count(),
        'featured': Product.objects.filter(featured=True).count(),
        'categories': Category.objects.count(),
        'inquiries': ContactMessage.objects.filter(is_read=False).count(),
        'logins': LoginRecord.objects.count(),
    }
