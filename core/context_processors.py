"""模板上下文：语言（cookie lang 优先，缺省按 Accept-Language）"""


def get_lang(request):
    lang = request.COOKIES.get('lang', '')
    if lang not in ('zh', 'en'):
        accept = (request.META.get('HTTP_ACCEPT_LANGUAGE') or '').lower()
        lang = 'zh' if 'zh' in accept else 'en'
    return lang


def lang_context(request):
    return {'lang': get_lang(request)}
