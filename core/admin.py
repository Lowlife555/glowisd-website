import csv
import json
import re
from collections import Counter
from datetime import timedelta

from django.contrib import admin
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import HeroSlide, LoginRecord, SiteImage, SiteSettings

# 后台浏览器标签页标题（V0.7.1）
admin.site.site_title = 'Glowisd站点管理员'
admin.site.site_header = 'Glowisd 站点管理'


@admin.register(SiteImage)
class SiteImageAdmin(admin.ModelAdmin):
    """站点展示图片：工厂页/车间照片/定制页等固定槽位的图片替换入口。

    列表固定展示全部槽位（无图显示「未上传」），点进任意一行上传图片即替换前台展示。
    """

    list_display = ['key_display', 'image_preview', 'caption_zh', 'updated_at']
    list_display_links = ['key_display']
    list_per_page = 30
    fieldsets = (
        ('图片位置', {
            'fields': ('key',),
            'description': '图片位置由系统预设，不可修改；每个位置对应网站上一个固定的展示区域。',
        }),
        ('图片', {'fields': ('image',), 'description': '上传新图片即可替换；建议横图 1600×1000 以上，JPG/PNG/WebP，单张 < 3MB。'}),
        ('图片说明（可选）', {
            'fields': ('caption_zh', 'caption_en', 'caption_ar'),
            'description': '中文/英文/阿语图片说明，用于图片替代文字（SEO/无障碍）；留空则用默认文案。',
        }),
    )

    @admin.display(description='图片位置', ordering='key')
    def key_display(self, obj):
        return obj.get_key_display()

    @admin.display(description='当前图片')
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" alt="{}" '
                'style="height:56px;width:100px;object-fit:cover;'
                'border:1px solid #E4E9F5;border-radius:2px;display:block;" />',
                obj.image.url,
                obj.get_key_display(),
            )
        return mark_safe(
            '<span style="display:block;height:56px;width:100px;line-height:56px;'
            'text-align:center;color:#A6B0CC;border:1px dashed #C9D1E8;'
            'border-radius:2px;font-size:12px;">未上传</span>'
        )

    # 槽位由系统预设（7 个固定位置），不允许新增重复槽位或删除槽位：
    # 只允许在已有槽位上上传/替换图片（V0.7.3）
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ['image_preview', 'title_zh', 'title_en', 'title_ar', 'sort_order', 'is_active', 'created_at']
    list_editable = ['sort_order', 'is_active']
    list_per_page = 20
    fieldsets = (
        ('图片', {'fields': ('image',)}),
        ('标题', {'fields': ('title_zh', 'title_en', 'title_ar')}),
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
        ('公司信息', {'fields': ('company_name_zh', 'company_name_en', 'company_name_ar', 'address_zh', 'address_en', 'address_ar')}),
        ('联系方式', {'fields': ('phone', 'email', 'whatsapp')}),
        ('生产信息', {'fields': ('factory_area', 'moq')}),
        ('公司简介', {'fields': ('about_zh', 'about_en', 'about_ar')}),
        ('SEO 设置', {'fields': ('seo_title_zh', 'seo_title_en', 'seo_title_ar', 'seo_desc_zh', 'seo_desc_en', 'seo_desc_ar')}),
        ('收银台说明', {
            'fields': ('payment_note_zh', 'payment_note_en'),
            'description': '展示在产品支付页下单按钮下方，例如「价格含税，运费另计，3-7 个工作日发货」。',
        }),
        ('水印设置', {'fields': ('watermark_enabled', 'watermark_image', 'watermark_position', 'watermark_opacity', 'watermark_width_pct', 'watermark_margin')}),
        ('翻译服务（阿拉伯语）', {
            'fields': ('deepseek_api_key',),
            'description': (
                '后台新增/修改产品、分类、站点内容时自动生成阿拉伯语翻译需要此项配置。'
                'Key 在 platform.deepseek.com 申请（形如 sk-...），只保存在服务器数据库，不会进入代码仓库。'
                '未配置时：内容照常保存，阿语字段留空，不会阻塞任何操作。'
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        pairs = [
            ('company_name_ar', obj.company_name_zh or obj.company_name_en),
            ('address_ar', obj.address_zh or obj.address_en),
            ('about_ar', obj.about_zh or obj.about_en),
            ('seo_title_ar', obj.seo_title_zh or obj.seo_title_en),
            ('seo_desc_ar', obj.seo_desc_zh or obj.seo_desc_en),
        ]
        missing = [field for field, src in pairs if not getattr(obj, field) and src]
        if not missing:
            return
        from core.translation import translate_ar
        sources = [getattr(obj, f.replace('_ar', '_zh')) or getattr(obj, f.replace('_ar', '_en'))
                   for f in missing]
        res = translate_ar(sources)
        if res:
            updates = []
            for field, value in zip(missing, res):
                if value:
                    setattr(obj, field, value)
                    updates.append(field)
            if updates:
                obj.save(update_fields=updates)
                messages.info(request, '已自动生成阿拉伯语内容（可在对应字段校对）')
        else:
            messages.warning(
                request,
                '阿拉伯语内容未生成：当前「翻译服务」未配置 DeepSeek API Key 或网络异常。',
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
        'display_user', 'formatted_time', 'region_display', 'device_type', 'os_name',
        'browser', 'success_display', 'fail_reason',
    ]
    list_filter = ['success', 'user', 'login_time']
    search_fields = ['user__username', 'username_attempted', 'os_name', 'browser', 'region']
    list_per_page = 30
    actions = ['export_login_csv']
    # 详情页只展示审计增强后的字段，隐藏 ip_address / user_agent
    fields = [
        'user', 'username_attempted', 'login_time', 'success', 'fail_reason',
        'device_type', 'os_name', 'browser', 'region', 'is_proxy',
    ]
    readonly_fields = [
        'user', 'username_attempted', 'login_time', 'success', 'fail_reason',
        'device_type', 'os_name', 'browser', 'region', 'is_proxy',
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
        # DB 按 UTC 存储（USE_TZ=True），显示须转北京时间（TIME_ZONE=Asia/Shanghai）
        return timezone.localtime(obj.login_time).strftime('%Y-%m-%d %H:%M:%S')

    @admin.display(description='登录成功', ordering='success')
    def success_display(self, obj):
        return '✅ 成功' if obj.success else '❌ 失败'

    @admin.display(description='登录地区', ordering='region')
    def region_display(self, obj):
        """登录地区 + 疑似代理出口红色警示标记。"""
        region = obj.region or '—'
        if obj.is_proxy:
            return format_html('<span style="color:#D32F2F;" title="IP 归属数据中心/代理服务商，可能为 VPN/代理出口">{} ⚠️代理</span>', region)
        return region

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

    list_display = ['action_time', 'user', 'content_type', 'object_repr', 'action_badge', 'change_message_natural']
    list_filter = ['user', 'action_flag', 'content_type']
    search_fields = ['object_repr', 'change_message', 'user__username']
    list_per_page = 30
    readonly_fields = ['action_time', 'user', 'content_type', 'object_id', 'object_repr', 'action_flag', 'change_message_natural']
    date_hierarchy = 'action_time'

    @admin.display(description='动作', ordering='action_flag')
    def action_badge(self, obj):
        """添加=绿 / 修改=蓝 / 删除=红。"""
        mapping = {
            ADDITION: ('添加', '#E8F5E9', '#1B6B32'),
            CHANGE: ('修改', '#E8F0FE', '#1A4FB0'),
            DELETION: ('删除', '#FDECEA', '#A61B1B'),
        }
        label, bg, color = mapping.get(obj.action_flag, ('其他', '#F1F3F8', '#5A6B9E'))
        return format_html(
            '<span style="display:inline-block;padding:2px 10px;border-radius:10px;'
            'background:{};color:{};font-size:12px;white-space:nowrap;">{}</span>',
            bg, color, label,
        )

    @admin.display(description='修改内容')
    def change_message_natural(self, obj):
        """把 Django 存储的 JSON change_message 翻成自然语言（如「修改了 产品分类 字段」）。

        用 Django 内置 LogEntry.get_change_message()：它会把字段名映射回模型的
        verbose_name（本项目为中文），历史记录同样适用；不再直接显示原始 JSON。
        兜底：极早期日志若存成非列表 JSON（或 get_change_message 解析失败），
        用正则从 ``"fields": [...]`` 里抽字段名，避免又出现一串 JSON。
        """
        try:
            text = obj.get_change_message()
        except Exception:  # noqa: BLE001 —— 日志脏数据不能把后台打挂
            text = obj.change_message or ''
        if not text:
            return '—'
        if isinstance(text, str) and text.lstrip().startswith('{'):
            try:
                data = json.loads(text)
                fields = data.get('changed', {}).get('fields') if isinstance(data, dict) else None
                if fields:
                    return '已修改 ' + '、'.join(str(f) for f in fields) + '。'
            except (ValueError, AttributeError):
                pass
            m = re.search(r'"fields"\s*:\s*\[(.*?)\]', text)
            if m:
                names = re.findall(r'"((?:[^"\\]|\\.)+)"', m.group(1))
                if names:
                    try:
                        names = [n.encode().decode('unicode_escape') for n in names]
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        pass
                    return '已修改 ' + '、'.join(names) + '。'
        return text

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
