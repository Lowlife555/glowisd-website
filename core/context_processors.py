"""模板上下文：语言（cookie lang 优先，缺省按 Accept-Language）+ 站点设置单例。"""


def get_lang(request):
    lang = request.COOKIES.get('lang', '')
    if lang not in ('zh', 'en'):
        accept = (request.META.get('HTTP_ACCEPT_LANGUAGE') or '').lower()
        lang = 'zh' if 'zh' in accept else 'en'
    return lang


def lang_context(request):
    return {'lang': get_lang(request)}


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
