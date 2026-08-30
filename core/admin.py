from django.contrib import admin
from django.contrib.admin.models import LogEntry

from .models import HeroSlide, LoginRecord


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


@admin.register(LoginRecord)
class LoginRecordAdmin(admin.ModelAdmin):
    """管理员登录历史：谁、何时、用什么设备、什么 IP 登录过后台。"""
    list_display = ['user', 'formatted_time', 'ip_address', 'short_ua']
    list_filter = ['user']
    search_fields = ['user__username', 'ip_address', 'user_agent']
    list_per_page = 30
    readonly_fields = ['user', 'formatted_time', 'ip_address', 'user_agent']
    date_hierarchy = 'login_time'

    @admin.display(description='登录时间', ordering='login_time')
    def formatted_time(self, obj):
        return obj.login_time.strftime('%Y-%m-%d %H:%M:%S')

    @admin.display(description='设备/浏览器')
    def short_ua(self, obj):
        ua = obj.user_agent or ''
        return ua[:60] + ('…' if len(ua) > 60 else '')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    """操作日志：每个管理员在后台做过哪些增删改操作。"""
    list_display = ['action_time', 'user', 'content_type', 'object_repr', 'action_flag', 'change_message']
    list_filter = ['user', 'action_flag', 'content_type']
    search_fields = ['object_repr', 'change_message', 'user__username']
    list_per_page = 30
    readonly_fields = ['action_time', 'user', 'content_type', 'object_id', 'object_repr', 'action_flag', 'change_message']
    date_hierarchy = 'action_time'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
