from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from .models import Category, Product


def product_list(request):
    products = Product.objects.select_related('category').all()
    categories = Category.objects.annotate(product_count=Count('products')).all()
    category_slug = request.GET.get('category', '').strip()
    search = request.GET.get('search', '').strip()

    if category_slug:
        products = products.filter(category__slug=category_slug)
    if search:
        products = products.filter(
            Q(sku__icontains=search)
            | Q(pn__icontains=search)
            | Q(part_name__icontains=search)
            | Q(part_name_en__icontains=search)
        )

    return render(request, 'products/list.html', {
        'products': products,
        'categories': categories,
        'active_category': category_slug,
        'search': search,
        'active': 'products',
    })


def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
    related = Product.objects.filter(category=product.category).exclude(pk=pk)[:4]
    return render(request, 'products/detail.html', {
        'product': product,
        'related': related,
        'active': 'products',
    })
