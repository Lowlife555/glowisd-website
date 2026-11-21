import time

from django.db.models import Count, Prefetch
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse

from products.models import Category, Product

from .context_processors import get_lang
from .forms import ContactForm
from .models import HeroSlide

RATE_LIMIT_WINDOW = 300  # 5 分钟
RATE_LIMIT_MAX = 3       # 同一会话最多 3 次


CATEGORY_TAGLINES = {
    'sensors': ('精确测量，稳定可靠', 'Precise measurement, stable and reliable', 'قياس دقيق وموثوق'),
    'cables': ('耐用连接，信号稳定', 'Durable connections, stable signals', 'توصيلات متينة وإشارات مستقرة'),
    'control-handles': ('操控精准，手感可靠', 'Precise control, reliable feel', 'تحكم دقيق وإحساس موثوق'),
    'displays': ('清晰显示，智能监控', 'Clear display, smart monitoring', 'عرض واضح ومراقبة ذكية'),
    'junction-boxes': ('安全防护，稳定接线', 'Protected, stable wiring', 'حماية آمنة وتوصيلات مستقرة'),
    'leveling-arms': ('精准找平，适应工况', 'Accurate leveling for every job site', 'تسوية دقيقة تناسب كل موقع عمل'),
    'pcb-boards': ('原厂级电路方案', 'OEM-grade circuit boards', 'لوحات دوائر بمعايير المصنع الأصلي'),
    'membrane-switches': ('耐用面板，灵敏反馈', 'Durable panels, responsive feedback', 'لوحات متينة واستجابة حساسة'),
    'complete-kits': ('一站式配套方案', 'One-stop complete kits', 'أطقم متكاملة من مكان واحد'),
    # 生产库实际在用的分类 slug（早期为中文/机型号命名），缺文案时卡片会露出「63 款 · 」后面空着
    'paver': ('摊铺机全系配件', 'Full paver parts range', 'قطع غيار كاملة لآلات الرصف'),
    'Roadroller': ('压路机专用配件', 'Road roller parts', 'قطع غيار مداحل الطرق'),
    'Millingmachine': ('铣刨机专用配件', 'Milling machine parts', 'قطع غيار آلات التفريز'),
    'Paveror-MillingMachineBalanceBeam': ('找平梁与平衡梁', 'Leveling and balance beams', 'عوارض التسوية والتوازن'),
    'machine': ('整机与配套件', 'Machines and accessories', 'آلات وملحقات'),
}

#: 未登记 slug 的兜底文案，避免分类卡片出现空标签行
GENERIC_TAGLINE = ('工程机械配件', 'Construction machinery parts', 'قطع غيار آلات الإنشاءات')


def home(request):
    # 一次取全分类（含在架数），并一次性预取各类最新产品：
    # 旧写法在 lineups 循环里对每个分类单独查一次产品（N+1，实测 8 次多余查询），
    # 且 categories.exclude() 会再查一次分类表；现在固定 2 次查询。
    categories = list(
        Category.objects
        .annotate(product_count=Count('products'))
        .order_by('sort_order', 'name')
        .prefetch_related(Prefetch(
            'products',
            queryset=Product.objects.order_by('-created_at'),
            to_attr='recent_products',
        ))
    )
    cats = []
    for c in categories:
        tl = CATEGORY_TAGLINES.get(c.slug, GENERIC_TAGLINE)
        cats.append({
            'slug': c.slug,
            'name': c.name,
            'name_en': c.name_en,
            'name_ar': c.name_ar,
            'count': c.product_count,
            'tl_zh': tl[0],
            'tl_en': tl[1],
            'tl_ar': tl[2],
        })
    hero_slides = HeroSlide.objects.filter(is_active=True).order_by('sort_order')

    # 首页推荐产品：featured=True，按最近更新排序，取前 8 个
    featured_products = Product.objects.filter(featured=True).order_by('-updated_at')[:8]

    # 分类卡片只展示「有产品」且已归类的分类：0 款分类点进去是空列表，
    # 「未分类」不是产品线、放在首页只会暴露数据整理进度，两者都从卡片墙隐藏。
    # 传 Category 对象（带 tl_zh/tl_en/tl_ar/count 附加属性），模板用 |cname:lang 与 |cat_cover 取封面图
    cat_cards = []
    for c in categories:
        if c.product_count > 0 and c.slug != 'uncategorized':
            tl = CATEGORY_TAGLINES.get(c.slug, GENERIC_TAGLINE)
            c.tl_zh, c.tl_en, c.tl_ar = tl[0], tl[1], tl[2]
            c.count = c.product_count
            cat_cards.append(c)

    # 产品线分区陈列：有产品的分类（排除"未分类"），每线取前 4 个产品（走上面的 prefetch 缓存，不再逐类查询）
    lineups = []
    for c in categories:
        if c.slug != 'uncategorized' and c.product_count > 0:
            lineups.append({
                'category': c,
                'products': c.recent_products[:4],
            })

    return render(request, 'core/home.html', {
        'active': 'home',
        'cats': cats,
        'cat_cards': cat_cards,
        'hero_slides': hero_slides,
        'featured_products': featured_products,
        'lineups': lineups,
        'category_count': len(cat_cards),
        'product_count': Product.objects.count(),
    })


def robots(request):
    """robots.txt：允许全部爬虫 + 声明 Sitemap 地址（SEO 收录入口）。"""
    sitemap_url = request.build_absolute_uri(reverse('django.contrib.sitemaps.views.sitemap'))
    content = 'User-agent: *\nAllow: /\nSitemap: %s\n' % sitemap_url
    return HttpResponse(content, content_type='text/plain')


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
            instance = form.save(commit=False)
            # 关联询价产品 + 记录来源：隐藏字段 product 携带产品详情页跳转时的 sku
            sku = (form.cleaned_data.get('product') or '').strip()
            if sku:
                instance.inquired_product = Product.objects.filter(sku=sku).first()
                instance.source_page = f'product_detail:{sku}'
            else:
                instance.source_page = 'contact_page'
            instance.save()
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
