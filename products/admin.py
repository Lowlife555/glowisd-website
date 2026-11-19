from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import EmptyFieldListFilter
from django.db.models import Count
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import PLACEHOLDER_PRICE, Category, ContactMessage, Product


class PriceStatusFilter(admin.SimpleListFilter):
    """按定价状态筛选：99999 防拍价 = 未定价（前台不开放下单）。"""

    title = '定价状态'
    parameter_name = 'priced'

    def lookups(self, request, model_admin):
        return [
            ('pending', '待定价（99999 防拍价）'),
            ('priced', '已定价（可在线下单）'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'pending':
            return queryset.filter(price=PLACEHOLDER_PRICE)
        if self.value() == 'priced':
            return queryset.exclude(price=PLACEHOLDER_PRICE)
        return queryset


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['cover_preview', 'name', 'name_en', 'name_ar', 'slug', 'sort_order', 'product_count']
    search_fields = ['name', 'name_en', 'name_ar', 'slug']
    ordering = ['sort_order']
    fieldsets = (
        ('分类信息', {'fields': ('name', 'name_en', 'name_ar', 'slug', 'sort_order')}),
        ('首页卡片封面图', {
            'fields': ('cover_image',),
            'description': '首页「按产品线浏览」卡片右侧展示图。留空自动取该分类第一个有图产品的首图。',
        }),
    )

    @admin.display(description='封面')
    def cover_preview(self, obj):
        image = obj.cover_or_first_product_image()
        if image:
            return format_html(
                '<img src="{}" alt="{}" style="width:56px;height:42px;object-fit:cover;'
                'border:1px solid #E4E9F5;border-radius:2px;display:block;" />',
                image.url, obj.name,
            )
        return mark_safe(
            '<span style="display:block;width:56px;height:42px;line-height:42px;'
            'text-align:center;color:#A6B0CC;border:1px dashed #C9D1E8;'
            'border-radius:2px;font-size:12px;">—</span>'
        )

    @admin.display(description='产品数')
    def product_count(self, obj):
        return obj.products.count()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not obj.name_ar and (obj.name or obj.name_en):
            from core.translation import translate_ar
            res = translate_ar([obj.name or obj.name_en])
            if res and res[0]:
                obj.name_ar = res[0]
                obj.save(update_fields=['name_ar'])
                messages.info(request, '已自动生成分类的阿拉伯语名称')
            else:
                messages.warning(request, '分类阿语名未生成：请检查「站点设置 → 翻译服务」的 API Key')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'image_preview', 'sku', 'part_name', 'pn',
        'price', 'currency', 'price_state', 'category', 'featured', 'updated_at',
    ]
    list_filter = [
        PriceStatusFilter, 'category', 'featured', 'currency',
        ('part_name_en', EmptyFieldListFilter),
        ('description_en', EmptyFieldListFilter),
        ('weight', EmptyFieldListFilter),
        ('warranty', EmptyFieldListFilter),
        ('brand', EmptyFieldListFilter),
    ]
    search_fields = ['sku', 'part_name', 'part_name_en', 'pn', 'brand']
    # 后台列表直接改价：输入新价格 → 点保存 → 前台立即生效
    list_editable = ['price', 'currency', 'featured']
    list_per_page = 20
    readonly_fields = ['pay_link_display']

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
        ('名称', {'fields': ('part_name', 'part_name_en', 'part_name_ar')}),
        ('定价与支付', {
            'fields': ('price', 'currency', 'payment_link', 'pay_link_display'),
            'description': (
                '未定价的产品保持 99999 防拍价，前台只展示「联系确认价格」，不会产生误拍；'
                '改成真实价格后前台立即出现「立即购买」。'
                '如需使用 Stripe Payment Link / PayPal 等外部收款页，把链接填到「外部支付链接」。'
            ),
        }),
        ('参数', {'fields': ('brand', 'weight', 'warranty')}),
        ('描述', {'fields': ('description', 'description_en', 'description_ar')}),
        ('图片', {'fields': ('image',)}),
    )

    # —— 阿语翻译：保存时自动生成（失败不阻塞保存）；批量重译走独立视图 ——
    # 注意：不使用 admin actions——simpleui 的 custom_button 标签无法序列化
    # Django 6.1 admin action 的 ActionLocation 元数据，会让产品列表页 500。

    def translate_all_arabic_view(self, request):
        """批量重新生成全部产品的阿语翻译（缺省时补全）。入口：数据质量检查页。"""
        from core.translation import translate_ar
        missing = Product.objects.filter(part_name_ar='')
        ok = fail = 0
        for obj in missing:
            res = translate_ar([obj.part_name or obj.part_name_en,
                                obj.description or obj.description_en])
            if res:
                obj.part_name_ar = res[0] or obj.part_name_ar
                obj.description_ar = res[1] or obj.description_ar
                obj.save(update_fields=['part_name_ar', 'description_ar'])
                ok += 1
            else:
                fail += 1
        if fail:
            self.message_user(
                request,
                f'已翻译 {ok} 个产品，失败 {fail} 个。失败通常是未配置 API Key 或网络异常，'
                '请检查「站点设置 → 翻译服务」。',
                messages.WARNING,
            )
        else:
            self.message_user(request, f'已生成 {ok} 个产品的阿拉伯语翻译', messages.SUCCESS)
        return redirect('admin:products_product_changelist')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        need_name = not obj.part_name_ar and (obj.part_name or obj.part_name_en)
        need_desc = not obj.description_ar and (obj.description or obj.description_en)
        if not (need_name or need_desc):
            return
        from core.translation import translate_ar
        res = translate_ar([obj.part_name or obj.part_name_en,
                            obj.description or obj.description_en])
        if res:
            if need_name and res[0]:
                obj.part_name_ar = res[0]
            if need_desc and res[1]:
                obj.description_ar = res[1]
            obj.save(update_fields=['part_name_ar', 'description_ar'])
            messages.info(request, '已自动生成阿拉伯语翻译（可在「名称/描述」中的阿拉伯语字段校对）')
        else:
            messages.warning(
                request,
                '阿拉伯语翻译未生成：请先在「站点设置 → 翻译服务」填写 DeepSeek API Key，'
                '或稍后在产品列表勾选本产品点「重新生成阿拉伯语翻译」。',
            )

    @admin.display(description='定价状态')
    def price_state(self, obj):
        if obj.is_placeholder_price:
            return mark_safe(
                '<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
                'background:#FDF1DF;color:#9A6200;font-size:12px;">待定价</span>'
            )
        return mark_safe(
            '<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
            'background:#E8F5E9;color:#1B6B32;font-size:12px;">可下单</span>'
        )

    @admin.display(description='产品支付链接')
    def pay_link_display(self, obj):
        if not obj.pk:
            return '保存后自动生成'
        path = obj.get_absolute_pay_url()
        url = f'{settings.SITE_BASE_URL.rstrip("/")}{path}'
        return format_html(
            '<a href="{}" target="_blank" rel="noopener" style="word-break:break-all;">{}</a>'
            '<div style="color:#8A93AD;font-size:12px;margin-top:4px;">'
            '这个链接可直接发给客户：定价后即完成在线下单，未定价时会跳回产品页。</div>',
            url, url,
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
            path(
                'translate-arabic/',
                self.admin_site.admin_view(self.translate_all_arabic_view),
                name='products_product_translate_arabic',
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
