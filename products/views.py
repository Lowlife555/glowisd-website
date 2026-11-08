from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from .models import Category, Product

#: 产品目录每页数量（182 款产品一页到底会把页面拉到 1.6 万像素，翻页更易浏览）
PRODUCTS_PER_PAGE = 24


def _query_prefix(**params):
    """分页链接要保留当前的分类/搜索条件。"""
    pairs = {key: value for key, value in params.items() if value}
    return (urlencode(pairs) + '&') if pairs else ''


def product_list(request):
    queryset = Product.objects.select_related('category').all()
    categories = Category.objects.annotate(product_count=Count('products')).all()
    category_slug = request.GET.get('category', '').strip()
    search = request.GET.get('search', '').strip()

    if category_slug:
        queryset = queryset.filter(category__slug=category_slug)
    if search:
        queryset = queryset.filter(
            Q(sku__icontains=search)
            | Q(pn__icontains=search)
            | Q(part_name__icontains=search)
            | Q(part_name_en__icontains=search)
        )

    paginator = Paginator(queryset, PRODUCTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))
    page_range = paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)

    return render(request, 'products/list.html', {
        'products': page_obj.object_list,
        'page_obj': page_obj,
        'page_range': page_range,
        'ellipsis': Paginator.ELLIPSIS,
        'total_count': paginator.count,
        'per_page': PRODUCTS_PER_PAGE,
        'query_prefix': _query_prefix(category=category_slug, search=search),
        'categories': categories,
        'active_category': category_slug,
        'search': search,
        'active': 'products',
    })


def product_detail(request, pk):
    from payments.views import payment_mode  # 延迟导入：products 不依赖 payments 的其他部分

    product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
    related = Product.objects.filter(category=product.category).exclude(pk=pk)[:4]
    return render(request, 'products/detail.html', {
        'product': product,
        'related': related,
        'active': 'products',
        'price_required': request.GET.get('price') == 'required',
        'pay_mode': payment_mode(product),
    })
