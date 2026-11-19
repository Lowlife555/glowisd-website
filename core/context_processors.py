"""模板上下文：语言（cookie lang 优先，缺省按 Accept-Language）+ 站点设置单例。"""


def get_lang(request):
    """语言：cookie lang（zh/en/ar）优先，其次 Accept-Language（含 ar 则阿语），最后英文。"""
    lang = request.COOKIES.get('lang', '')
    if lang not in ('zh', 'en', 'ar'):
        accept = (request.META.get('HTTP_ACCEPT_LANGUAGE') or '').lower()
        if 'ar' in accept:
            lang = 'ar'
        elif 'zh' in accept:
            lang = 'zh'
        else:
            lang = 'en'
    return lang


def is_bot(request):
    """粗判搜索引擎爬虫：弹窗对爬虫不显示，避免影响收录。"""
    ua = (request.META.get('HTTP_USER_AGENT') or '').lower()
    tokens = ('bot', 'spider', 'crawler', 'slurp', 'baiduspider', 'bingpreview', 'yandex')
    return any(t in ua for t in tokens)


def lang_context(request):
    """语言 + 是否展示「首次进入语言选择弹窗」。

    弹窗仅当 cookie 里没有 lang_chosen 且访问者不是爬虫时显示；
    用户选择或关闭后写入 lang_chosen（1 年），之后不再出现。
    """
    lang = get_lang(request)
    chosen = request.COOKIES.get('lang_chosen') == '1'
    return {
        'lang': lang,
        'show_lang_modal': (not chosen) and (not is_bot(request)),
    }


def site_settings(request):
    """向前台模板提供 site_settings 全局变量（单例，不存在时自动创建 pk=1）+ 站点版本（cache busting）。"""
    from django.conf import settings
    from core.models import SiteSettings
    return {
        'site_settings': SiteSettings.load(),
        'site_version': getattr(settings, 'SITE_VERSION', '0.0.0'),
    }


def site_images(request):
    """向前台模板提供 site_images：{key: SiteImage}，仅含后台已上传图片的槽位。

    模板用法：{% if site_images.factory_hero %} 用 {{ site_images.factory_hero.image.url }}，
    否则回退占位图。后台「站点图片」上传即替换，无需改代码（V0.7.3）。
    """
    from core.models import SiteImage
    return {'site_images': SiteImage.get_map()}


def pricing_flags(request):
    """向前台模板提供 show_prices：后台「收款设置 → 前台显示价格」一键开关（V0.11.0）。"""
    from payments.models import PaymentSettings
    return {'show_prices': PaymentSettings.prices_visible()}


def nav_categories(request):
    """导航「产品」二级菜单的分类列表（V0.13.0）。

    只取有产品的可见分类（排除未分类），按后台排序（sort_order）输出，
    供下拉面板渲染缩略图 + 名称 + 数量。当前台分类很少时面板自动变矮。
    """
    from django.db.models import Count

    from products.models import Category

    qs = (
        Category.objects
        .annotate(nav_count=Count('products'))
        .filter(nav_count__gt=0)
        .exclude(slug='uncategorized')
        .order_by('sort_order', 'name')
    )
    return {'nav_categories': list(qs)}
