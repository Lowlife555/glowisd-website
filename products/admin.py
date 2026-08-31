from django.contrib import admin
from django.contrib.admin import EmptyFieldListFilter
from django.db.models import Count
from django.shortcuts import render
from django.urls import path
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import Category, Product, ContactMessage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'name_en', 'slug', 'sort_order', 'product_count']
    search_fields = ['name', 'name_en', 'slug']
    ordering = ['sort_order']

    @admin.display(description='产品数')
    def product_count(self, obj):
        return obj.products.count()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['image_preview', 'sku', 'part_name', 'pn', 'brand', 'category', 'featured', 'updated_at']
    list_filter = [
        'category', 'featured',
        ('part_name_en', EmptyFieldListFilter),
        ('description_en', EmptyFieldListFilter),
        ('weight', EmptyFieldListFilter),
        ('warranty', EmptyFieldListFilter),
        ('brand', EmptyFieldListFilter),
    ]
    search_fields = ['sku', 'part_name', 'part_name_en', 'pn', 'brand']
    list_editable = ['featured']
    list_per_page = 20

    @admin.display(description='图片')
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" alt="{}" '
                'style="width:56px;height:42px;object-fit:cover;'
                'border:1px solid #E4E9F5;border-radius:2px;display:block;" />',
                obj.image.url,
                obj.sku,
            )
        return mark_safe(
            '<span style="display:block;width:56px;height:42px;line-height:42px;'
            'text-align:center;color:#A6B0CC;border:1px dashed #C9D1E8;'
            'border-radius:2px;font-size:12px;">—</span>'
        )
    fieldsets = (
        ('基本信息', {'fields': ('sku', 'pn', 'category', 'featured')}),
        ('名称', {'fields': ('part_name', 'part_name_en')}),
        ('参数', {'fields': ('brand', 'weight', 'warranty')}),
        ('描述', {'fields': ('description', 'description_en')}),
        ('图片', {'fields': ('image',)}),
    )

    # —— 数据质量检查自定义页面 ——

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'data-quality/',
                self.admin_site.admin_view(self.data_quality_view),
                name='products_product_data_quality',
            ),
        ]
        return custom + urls

    def data_quality_view(self, request):
        """7 项数据质量统计，每项可点击跳转到预筛选后的产品列表。"""
        uncat = Category.objects.filter(slug='uncategorized').first()
        uncat_count = Product.objects.filter(category=uncat).count() if uncat else 0

        duplicate_skus = list(
            Product.objects.values('sku')
            .annotate(cnt=Count('id'))
            .filter(cnt__gt=1)
            .order_by('-cnt', 'sku')
        )
        first_dup_sku = duplicate_skus[0]['sku'] if duplicate_skus else None

        stats = [
            {
                'label': '缺英文品名',
                'count': Product.objects.filter(part_name_en='').count(),
                'url': '/admin/products/product/?part_name_en__isempty=1',
            },
            {
                'label': '缺英文描述',
                'count': Product.objects.filter(description_en='').count(),
                'url': '/admin/products/product/?description_en__isempty=1',
            },
            {
                'label': '缺重量',
                'count': Product.objects.filter(weight='').count(),
                'url': '/admin/products/product/?weight__isempty=1',
            },
            {
                'label': '缺质保',
                'count': Product.objects.filter(warranty='').count(),
                'url': '/admin/products/product/?warranty__isempty=1',
            },
            {
                'label': '缺品牌',
                'count': Product.objects.filter(brand='').count(),
                'url': '/admin/products/product/?brand__isempty=1',
            },
            {
                'label': '未分类',
                'count': uncat_count,
                'url': (
                    f'/admin/products/product/?category__id__exact={uncat.id}'
                    if uncat else '/admin/products/product/'
                ),
            },
            {
                'label': 'SKU 重复',
                'count': len(duplicate_skus),
                'url': (
                    f'/admin/products/product/?q={first_dup_sku}'
                    if first_dup_sku else '/admin/products/product/'
                ),
            },
        ]

        context = {
            **self.admin_site.each_context(request),
            'title': '数据质量检查',
            'stats': stats,
        }
        return render(request, 'admin/products/product/data_quality.html', context)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'company', 'email', 'status_badge', 'status',
        'inquired_product', 'quote_amount', 'is_read', 'created_at',
    ]
    list_editable = ['status']
    list_filter = ['status', 'country']
    search_fields = ['name', 'email', 'company', 'message']
    readonly_fields = [
        'name', 'company', 'email', 'phone', 'country', 'category',
        'message', 'source_page', 'created_at',
    ]
    fieldsets = (
        ('基本信息', {'fields': ('name', 'company', 'email', 'phone', 'country', 'created_at')}),
        ('询价内容', {'fields': ('inquired_product', 'category', 'message', 'source_page')}),
        ('跟进状态', {'fields': ('status', 'quote_amount', 'lost_reason', 'is_read')}),
    )

    STATUS_COLORS = {
        'new': '#1976D2',        # 蓝
        'contacted': '#E67E22',  # 橙
        'quoted': '#8E44AD',     # 紫
        'won': '#27AE60',        # 绿
        'lost': '#A93226',       # 灰红
    }

    @admin.display(description='状态', ordering='status')
    def status_badge(self, obj):
        color = self.STATUS_COLORS.get(obj.status, '#1976D2')
        label = dict(ContactMessage.STATUS_CHOICES).get(obj.status, obj.status)
        return format_html(
            '<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
            'color:#fff;background:{};font-size:12px;line-height:1.4;">{}</span>',
            color,
            label,
        )

    # —— 按国家分组统计面板（Top 10 国家 + 总数） ——

    def _build_country_stats(self):
        rows = (
            ContactMessage.objects
            .exclude(country='')
            .values('country')
            .annotate(count=Count('id'))
            .order_by('-count', 'country')
        )
        return {
            'total': ContactMessage.objects.count(),
            'top': list(rows[:10]),
        }

    def get_changelist_instance(self, request):
        cl = super().get_changelist_instance(request)
        cl.country_stats = self._build_country_stats()
        return cl
