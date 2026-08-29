from django.contrib import admin

from .models import HeroSlide


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ['image', 'title_zh', 'title_en', 'sort_order', 'is_active', 'created_at']
    list_editable = ['sort_order', 'is_active']
    list_per_page = 20
    fieldsets = (
        ('图片', {'fields': ('image',)}),
        ('标题', {'fields': ('title_zh', 'title_en')}),
        ('设置', {'fields': ('sort_order', 'is_active')}),
    )
