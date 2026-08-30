from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.models import LogEntry
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import HeroSlide, LoginRecord


class SuperuserOnlyAdminMixin:
    """仅超级管理员可访问的模块：普通 staff 连模块入口都看不到。"""

    def has_module_permission(self, request):
        return bool(
            request
            and getattr(request, 'user', None)
            and request.user.is_authenticated
            and request.user.is_superuser
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ['image_preview', 'title_zh', 'title_en', 'sort_order', 'is_active', 'created_at']
    list_editable = ['sort_order', 'is_active']
    list_per_page = 20
    fieldsets = (
        ('图片', {'fields': ('image',)}),
        ('标题', {'fields': ('title_zh', 'title_en')}),
        ('设置', {'fields': ('sort_order', 'is_active')}),
    )

    @admin.display(description='轮播图片')
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" alt="{}" '
                'style="height:56px;width:100px;object-fit:cover;'
                'border:1px solid #E4E9F5;border-radius:2px;display:block;" />',
                obj.image.url,
                obj.title_zh or obj.title_en or '轮播图',
            )
        return mark_safe(
            '<span style="display:block;height:56px;width:100px;line-height:56px;'
            'text-align:center;color:#A6B0CC;border:1px dashed #C9D1E8;'
            'border-radius:2px;font-size:12px;">—</span>'
        )


@admin.register(LoginRecord)
class LoginRecordAdmin(admin.ModelAdmin):
    """管理员登录历史：谁、何时、什么设备/系统/浏览器、从哪里登录过后台。

    注意：ip_address / user_agent 原始字符串只在数据库保存，不在后台列表或详情页展示，
    超管如需自查请用 Django shell。
    """
    list_display = ['user', 'formatted_time', 'device_type', 'os_name', 'browser', 'region']
    list_filter = ['user', 'device_type', 'os_name', 'browser']
    search_fields = ['user__username', 'os_name', 'browser', 'region']
    list_per_page = 30
    # 详情页只展示审计增强后的字段，隐藏 ip_address / user_agent
    fields = ['user', 'device_type', 'os_name', 'browser', 'region']
    readonly_fields = ['user', 'formatted_time', 'device_type', 'os_name', 'browser', 'region']
    date_hierarchy = 'login_time'

    @admin.display(description='登录时间', ordering='login_time')
    def formatted_time(self, obj):
        return obj.login_time.strftime('%Y-%m-%d %H:%M:%S')

    # —— 超管门槛：普通 staff 看不到「登录记录」模块 ——
    def has_module_permission(self, request):
        return bool(
            request
            and getattr(request, 'user', None)
            and request.user.is_authenticated
            and request.user.is_superuser
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    """操作日志：每个管理员在后台做过哪些增删改操作（仅超管可见）。"""
    list_display = ['action_time', 'user', 'content_type', 'object_repr', 'action_flag', 'change_message']
    list_filter = ['user', 'action_flag', 'content_type']
    search_fields = ['object_repr', 'change_message', 'user__username']
    list_per_page = 30
    readonly_fields = ['action_time', 'user', 'content_type', 'object_id', 'object_repr', 'action_flag', 'change_message']
    date_hierarchy = 'action_time'

    # —— 超管门槛：普通 staff 看不到「日志记录」模块 ——
    def has_module_permission(self, request):
        return bool(
            request
            and getattr(request, 'user', None)
            and request.user.is_authenticated
            and request.user.is_superuser
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class RestrictedUserAdmin(SuperuserOnlyAdminMixin, UserAdmin):
    """用户管理：仅超级管理员可见/可操作，且带超管自保护。

    - 不能删除自己；
    - 不能删除/降级系统里唯一的超级管理员；
    - 新增用户走 Django 默认表单（不含 is_superuser 字段，默认即普通 staff）。
    """

    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        # 禁止删除自己
        if obj is not None and obj.pk == request.user.pk:
            return False
        # 禁止删除系统里唯一的超级管理员
        if obj is not None and obj.is_superuser and User.objects.filter(is_superuser=True).count() <= 1:
            return False
        return True

    def save_model(self, request, obj, form, change):
        if change:
            try:
                orig = User.objects.get(pk=obj.pk)
            except User.DoesNotExist:
                orig = None
            # 阻止把系统里唯一的超管降级为普通管理员（忽略该变更）
            if (
                orig is not None
                and orig.is_superuser
                and not obj.is_superuser
                and User.objects.filter(is_superuser=True).count() <= 1
            ):
                obj.is_superuser = True
                obj.is_staff = True
                self.message_user(
                    request,
                    '该用户是系统里唯一的超级管理员，无法降级为普通管理员（已保留超管权限）。',
                    level=messages.WARNING,
                )
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        if obj.pk == request.user.pk:
            return
        if obj.is_superuser and User.objects.filter(is_superuser=True).count() <= 1:
            return
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        # 批量删除时排除自己与唯一的超管
        protected_ids = {request.user.pk}
        if User.objects.filter(is_superuser=True).count() <= 1:
            protected_ids.update(
                User.objects.filter(is_superuser=True).values_list('pk', flat=True)
            )
        queryset.exclude(pk__in=protected_ids).delete()


class RestrictedGroupAdmin(SuperuserOnlyAdminMixin, GroupAdmin):
    """组管理：仅超级管理员可见/可操作。"""


# 用受限版本替换默认的 User / Group 管理（默认由 django.contrib.auth 注册）
admin.site.unregister(User)
admin.site.register(User, RestrictedUserAdmin)
admin.site.unregister(Group)
admin.site.register(Group, RestrictedGroupAdmin)
