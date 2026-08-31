import csv
from collections import Counter
from datetime import timedelta

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import HeroSlide, LoginRecord, SiteSettings


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


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """站点设置单例：始终只有一条（pk=1），不可新增多条、不可删除。"""
    fieldsets = (
        ('公司信息', {'fields': ('company_name_zh', 'company_name_en', 'address_zh', 'address_en')}),
        ('联系方式', {'fields': ('phone', 'email', 'whatsapp')}),
        ('生产信息', {'fields': ('factory_area', 'moq')}),
        ('公司简介', {'fields': ('about_zh', 'about_en')}),
        ('SEO 设置', {'fields': ('seo_title_zh', 'seo_title_en', 'seo_desc_zh', 'seo_desc_en')}),
    )

    # 单例：已存在记录时禁止再新增；永不删除
    def has_add_permission(self, request):
        if SiteSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    # 点击菜单直接进入唯一一条记录的编辑页（不存在则自动创建）
    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.load()
        return redirect(reverse('admin:core_sitesettings_change', args=[obj.pk]))


@admin.register(LoginRecord)
class LoginRecordAdmin(admin.ModelAdmin):
    """管理员登录历史：谁、何时、什么设备/系统/浏览器、从哪里登录过后台。

    注意：ip_address / user_agent 原始字符串只在数据库保存，不在后台列表或详情页展示，
    超管如需自查请用 Django shell。
    """
    list_display = [
        'display_user', 'formatted_time', 'region', 'device_type', 'os_name',
        'browser', 'success_display', 'fail_reason',
    ]
    list_filter = ['success', 'user', 'login_time']
    search_fields = ['user__username', 'username_attempted', 'os_name', 'browser', 'region']
    list_per_page = 30
    actions = ['export_login_csv']
    # 详情页只展示审计增强后的字段，隐藏 ip_address / user_agent
    fields = [
        'user', 'username_attempted', 'login_time', 'success', 'fail_reason',
        'device_type', 'os_name', 'browser', 'region',
    ]
    readonly_fields = [
        'user', 'username_attempted', 'login_time', 'success', 'fail_reason',
        'device_type', 'os_name', 'browser', 'region',
    ]
    date_hierarchy = 'login_time'

    @admin.display(description='用户', ordering='user__username')
    def display_user(self, obj):
        """无关联用户（失败登录）时展示尝试用户名。"""
        if obj.user_id:
            return obj.user.username
        return obj.username_attempted or '—'

    @admin.display(description='登录时间', ordering='login_time')
    def formatted_time(self, obj):
        return obj.login_time.strftime('%Y-%m-%d %H:%M:%S')

    @admin.display(description='登录成功', ordering='success')
    def success_display(self, obj):
        return '✅ 成功' if obj.success else '❌ 失败'

    # —— 统计卡片 + 异常登录判定 ——

    def _anomalous_pk_set(self):
        """返回「异常登录」记录的 pk 集合。

        异常定义：该条记录的 region 与该用户「最近30天」最常见 region 不同。
        无关联用户（失败登录）、region 为空、或该用户最近30天没有有效 region
        基线时，不判定为异常（无法比较）。
        """
        now = timezone.now()
        cutoff = now - timedelta(days=30)
        by_user = {}
        for r in LoginRecord.objects.all():
            if r.user_id is None:
                continue
            by_user.setdefault(r.user_id, []).append(r)

        anomalous = set()
        for recs in by_user.values():
            recent = [r.region for r in recs if r.region and r.login_time >= cutoff]
            if not recent:
                continue
            mode = Counter(recent).most_common(1)[0][0]
            for r in recs:
                if r.region and r.region != mode:
                    anomalous.add(r.pk)
        return anomalous

    def _build_login_stats(self, anomalous_ids):
        now = timezone.now()
        today_start = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = now - timedelta(days=7)

        today_count = LoginRecord.objects.filter(login_time__gte=today_start).count()
        active_admin_count = (
            LoginRecord.objects.filter(login_time__gte=seven_days_ago, user__isnull=False)
            .values('user').distinct().count()
        )
        fail_count_7d = LoginRecord.objects.filter(
            login_time__gte=seven_days_ago, success=False
        ).count()

        return {
            'today_count': today_count,
            'active_admin_count': active_admin_count,
            'fail_count_7d': fail_count_7d,
            'anomaly_count': len(anomalous_ids),
        }

    def get_changelist_instance(self, request):
        """在 ChangeList 实例上挂载统计与异常集合，供自定义 changelist 模板使用。"""
        cl = super().get_changelist_instance(request)
        cl.anomalous_ids = self._anomalous_pk_set()
        cl.login_stats = self._build_login_stats(cl.anomalous_ids)
        return cl

    # —— CSV 导出（不含 IP）——

    def export_login_csv(self, request, queryset):
        """导出选中记录为 CSV：管理员/时间/地区/设备/系统/浏览器/结果/失败原因（不含 IP）。"""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="login_records.csv"'
        # UTF-8 BOM，保证 Excel 直接打开中文不乱码
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['管理员', '时间', '地区', '设备', '系统', '浏览器', '结果', '失败原因'])
        for r in queryset:
            user_label = r.user.username if r.user_id else (r.username_attempted or '—')
            writer.writerow([
                user_label,
                timezone.localtime(r.login_time).strftime('%Y-%m-%d %H:%M:%S'),
                r.region or '',
                r.device_type or '',
                r.os_name or '',
                r.browser or '',
                '成功' if r.success else '失败',
                r.fail_reason or '',
            ])
        return response

    export_login_csv.short_description = '导出选中记录为 CSV'

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
