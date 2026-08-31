from datetime import timedelta

from django import template
from django.db.models import Q
from django.utils import timezone

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


@register.simple_tag
def admin_dashboard():
    """后台首页仪表盘数据（6 统计卡片 + 最近询价 8 条 + 待办 4 项）。

    所有时间边界都以 timezone.now() 为基准换算到本地时区（Asia/Shanghai）。
    """
    now = timezone.now()
    local_now = timezone.localtime(now)

    # —— 本周（周一起算）与本月边界（本地时区，aware datetime） ——
    week_start = (local_now - timedelta(days=local_now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # —— 顶部 6 个统计卡片 ——
    product_total = Product.objects.count()
    unread_inquiries = ContactMessage.objects.filter(is_read=False).count()
    week_inquiries = ContactMessage.objects.filter(created_at__gte=week_start).count()
    incomplete_products = Product.objects.filter(
        Q(part_name_en='') | Q(description_en='')
    ).count()
    month_inquiries = ContactMessage.objects.filter(created_at__gte=month_start).count()
    active_categories = (
        Category.objects.filter(products__isnull=False)
        .exclude(slug='uncategorized')
        .distinct()
        .count()
    )

    # —— 最近询价动态（最近 8 条） ——
    recent_inquiries = []
    for m in ContactMessage.objects.order_by('-created_at')[:8]:
        excerpt = m.message or ''
        if len(excerpt) > 40:
            excerpt = excerpt[:40] + '…'
        recent_inquiries.append({
            'id': m.pk,
            'company': m.company or m.name,
            'country': m.country or '—',
            'category': m.category or '—',
            'excerpt': excerpt,
            'is_read': m.is_read,
        })

    # —— 待办事项（4 项自动检测） ——
    overdue_unread = ContactMessage.objects.filter(
        is_read=False, created_at__lt=now - timedelta(hours=24)
    ).count()
    missing_desc_en = Product.objects.filter(description_en='').count()
    uncat = Category.objects.filter(slug='uncategorized').first()
    uncat_count = Product.objects.filter(category=uncat).count() if uncat else 0
    uncat_url = (
        f'/admin/products/product/?category__id__exact={uncat.id}'
        if uncat
        else '/admin/products/product/'
    )
    featured_count = Product.objects.filter(featured=True).count()
    featured_done = featured_count >= 8

    todos = [
        {
            'title': '超24小时未读询价',
            'count': overdue_unread,
            'url': '/admin/products/contactmessage/?is_read__exact=0',
            'status': 'warn' if overdue_unread > 0 else 'ok',
            'note': '',
        },
        {
            'title': '缺英文描述产品',
            'count': missing_desc_en,
            'url': '/admin/products/product/',
            'status': 'warn' if missing_desc_en > 0 else 'ok',
            'note': '',
        },
        {
            'title': '未分类产品',
            'count': uncat_count,
            'url': uncat_url,
            'status': 'warn' if uncat_count > 0 else 'ok',
            'note': '',
        },
        {
            'title': '首页推荐',
            'count': featured_count,
            'url': '/admin/products/product/?featured__exact=0',
            'status': 'done' if featured_done else 'warn',
            'note': '已满 8 个' if featured_done else f'当前 {featured_count} 个，建议补到 8 个',
        },
    ]

    return {
        'product_total': product_total,
        'unread_inquiries': unread_inquiries,
        'week_inquiries': week_inquiries,
        'incomplete_products': incomplete_products,
        'month_inquiries': month_inquiries,
        'active_categories': active_categories,
        'recent_inquiries': recent_inquiries,
        'todos': todos,
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
