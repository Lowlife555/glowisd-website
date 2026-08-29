from django.contrib import admin
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
    list_filter = ['category', 'featured']
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


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'email', 'category', 'is_read', 'created_at']
    list_filter = ['is_read']
    search_fields = ['name', 'email', 'company', 'message']
    readonly_fields = ['name', 'company', 'email', 'phone', 'country', 'category', 'message', 'created_at']
