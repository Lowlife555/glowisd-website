import time

from django.db.models import Count
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render

from products.models import Category, Product

from .context_processors import get_lang
from .forms import ContactForm
from .models import HeroSlide

RATE_LIMIT_WINDOW = 300  # 5 分钟
RATE_LIMIT_MAX = 3       # 同一会话最多 3 次


CATEGORY_TAGLINES = {
    'sensors': ('精确测量，稳定可靠', 'Precise measurement, stable and reliable'),
    'cables': ('耐用连接，信号稳定', 'Durable connections, stable signals'),
    'control-handles': ('操控精准，手感可靠', 'Precise control, reliable feel'),
    'displays': ('清晰显示，智能监控', 'Clear display, smart monitoring'),
    'junction-boxes': ('安全防护，稳定接线', 'Protected, stable wiring'),
    'leveling-arms': ('精准找平，适应工况', 'Accurate leveling for every job site'),
    'pcb-boards': ('原厂级电路方案', 'OEM-grade circuit boards'),
    'membrane-switches': ('耐用面板，灵敏反馈', 'Durable panels, responsive feedback'),
    'complete-kits': ('一站式配套方案', 'One-stop complete kits'),
}


def home(request):
    categories = Category.objects.annotate(product_count=Count('products')).all()
    cats = []
    for c in categories:
        tl = CATEGORY_TAGLINES.get(c.slug, ('', ''))
        cats.append({
            'slug': c.slug,
            'name': c.name,
            'name_en': c.name_en,
            'count': c.product_count,
            'tl_zh': tl[0],
            'tl_en': tl[1],
        })
    hero_slides = HeroSlide.objects.filter(is_active=True).order_by('sort_order')
    return render(request, 'core/home.html', {
        'active': 'home',
        'cats': cats,
        'hero_slides': hero_slides,
        'category_count': len(cats),
        'product_count': Product.objects.count(),
    })


def factory(request):
    return render(request, 'core/factory.html', {'active': 'factory'})


def custom(request):
    return render(request, 'core/custom.html', {'active': 'custom'})


def _rate_limited(request):
    """会话级限流：5 分钟内最多 3 次提交。"""
    now = time.time()
    key = 'contact_submits'
    stamps = request.session.get(key, [])
    stamps = [s for s in stamps if now - s < RATE_LIMIT_WINDOW]
    if len(stamps) >= RATE_LIMIT_MAX:
        request.session[key] = stamps
        return True
    stamps.append(now)
    request.session[key] = stamps
    return False


def _contact_ctx(**kw):
    ctx = {
        'active': 'contact',
        'categories': Category.objects.all(),
        'ok': False,
    }
    ctx.update(kw)
    return ctx


def contact(request):
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        lang = get_lang(request)

        # 蜜罐：填了隐藏字段的一律视为机器人，静默成功但不入库
        if request.POST.get('website'):
            if is_ajax:
                return JsonResponse({'ok': True})
            return HttpResponseRedirect('/contact/?ok=1')

        if _rate_limited(request):
            msg = '提交过于频繁，请 5 分钟后再试。' if lang == 'zh' else \
                'Too many submissions. Please try again in 5 minutes.'
            if is_ajax:
                return JsonResponse({'ok': False, 'rate_limited': True, 'error': msg}, status=429)
            return render(request, 'core/contact.html',
                          _contact_ctx(error_key='rate_limited'), status=429)

        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            if is_ajax:
                return JsonResponse({'ok': True})
            return HttpResponseRedirect('/contact/?ok=1')

        if is_ajax:
            msg = '提交内容有误，请检查必填项与邮箱格式。' if lang == 'zh' else \
                'Submission invalid. Please check required fields and email format.'
            return JsonResponse({'ok': False, 'error': msg}, status=400)
        return render(request, 'core/contact.html',
                      _contact_ctx(error_key='invalid'), status=400)

    return render(request, 'core/contact.html', _contact_ctx(
        ok=bool(request.GET.get('ok')),
    ))
