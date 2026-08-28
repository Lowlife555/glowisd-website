from django.contrib import admin

from .models import Category, Product, ContactMessage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'name_en', 'slug', 'sort_order']
    search_fields = ['name', 'name_en', 'slug']
    ordering = ['sort_order']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['sku', 'part_name', 'pn', 'brand', 'category', 'featured', 'updated_at']
    list_filter = ['category', 'featured']
    search_fields = ['sku', 'part_name', 'part_name_en', 'pn', 'brand']
    list_editable = ['featured']
    list_per_page = 20
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
