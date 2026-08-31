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


@register.filter
def row_is_anomalous(cl, index):
    """判断 changelist 结果第 index 行对应的记录是否为「异常登录」（用于行高亮）。

    依赖 LoginRecordAdmin.get_changelist_instance 挂到 ChangeList 上的
    anomalous_ids 集合；异常集合缺失时一律返回 False。
    """
    try:
        obj = cl.result_list[index]
    except (IndexError, TypeError, AttributeError):
        return False
    return getattr(obj, 'pk', None) in getattr(cl, 'anomalous_ids', set())
