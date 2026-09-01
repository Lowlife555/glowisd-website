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
