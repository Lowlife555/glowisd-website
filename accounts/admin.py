import random
import secrets
import string
from urllib.parse import unquote

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.html import format_html

from .models import AdminProfile
from .utils import is_super_admin


class CustomUserChangeForm(forms.ModelForm):
    """编辑表单：业务化字段（去掉密码/权限/组等技术字段），标签中文化。"""

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active')
        labels = {
            'first_name': '姓名',
            'email': '邮箱',
            'is_active': '账号状态',
        }
        help_texts = {
            'is_active': '勾选表示启用该账号，取消勾选则禁用其登录。',
        }


class CustomUserCreationForm(UserCreationForm):
    """新增表单：只保留业务字段 + Django 的两次密码输入（password1/password2）。"""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
        labels = {
            'first_name': '姓名',
            'email': '邮箱',
        }


class AdminProfileForm(forms.ModelForm):
    """inline 表单：控制 role 下拉的可见选项与 glowisd 的角色只读。"""

    class Meta:
        model = AdminProfile
        fields = ['role', 'phone']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        role_field = self.fields.get('role')
        if role_field is None:
            return
        parent_user = self._parent_user()
        if parent_user is not None and parent_user.username == settings.SUPER_ADMIN_USERNAME:
            # glowisd：角色只读（配合 inline 的 readonly_fields 展示「超级管理员」）
            role_field.disabled = True
        else:
            # 编辑其他管理员 / 新增：role 只能选 普通管理员 / 只读管理员，不能设成超管
            role_field.choices = [
                c for c in AdminProfile.ROLE_CHOICES if c[0] in ('admin', 'viewer')
            ]

    def _parent_user(self):
        instance = self.instance
        if instance is None or not getattr(instance, 'user_id', None):
            return None
        try:
            return instance.user
        except User.DoesNotExist:
            return None


class AdminProfileInline(admin.StackedInline):
    model = AdminProfile
    form = AdminProfileForm
    extra = 0
    max_num = 1
    can_delete = False
    fields = ['role', 'phone']
    verbose_name = '管理员资料'
    verbose_name_plural = '管理员资料'

    def get_readonly_fields(self, request, obj=None):
        # obj 是当前编辑的 User；编辑 glowisd 时 role 只读展示「超级管理员」
        if obj is not None and obj.username == settings.SUPER_ADMIN_USERNAME:
            return ['role']
        return []


class CustomUserAdmin(UserAdmin):
    """accounts 接管后的用户管理：角色体系 + 超管保护 + 业务化编辑页。"""

    inlines = [AdminProfileInline]
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    # —— 编辑页：只保留业务字段，去掉 密码/权限/组/技术字段 ——
    fieldsets = (
        ('基本信息', {'fields': ('username', 'first_name', 'last_name', 'email')}),
        ('账号状态', {'fields': ('is_active',)}),
    )

    # —— 新增表单：只保留 用户名/姓名/邮箱 + 两次密码输入 ——
    add_fieldsets = (
        ('基本信息', {'fields': ('username', 'first_name', 'last_name', 'email')}),
        ('密码', {'fields': ('password1', 'password2')}),
    )

    list_display = [
        'username',
        'display_name',
        'email',
        'role_display',
        'is_active_display',
        'last_login',
        'last_region',
    ]
    list_filter = ['is_active', 'admin_profile__role']
    search_fields = ['username', 'email', 'first_name']
    list_per_page = 30
    actions = ['reset_selected_admin_password']

    # —— 列表列 ——

    @admin.display(description='姓名', ordering='first_name')
    def display_name(self, obj):
        return obj.first_name or '—'

    @admin.display(description='角色', ordering='admin_profile__role')
    def role_display(self, obj):
        profile = getattr(obj, 'admin_profile', None)
        if profile is None:
            return '—'
        # 彩色小标签：超管红 / 管理员蓝 / 只读灰
        color_map = {
            'super_admin': '#D32F2F',
            'admin': '#1976D2',
            'viewer': '#9E9E9E',
        }
        color = color_map.get(profile.role, '#9E9E9E')
        return format_html(
            '<span style="display:inline-block;padding:2px 10px;border-radius:11px;'
            'color:#fff;background:{};font-size:12px;line-height:1.5;">{}</span>',
            color,
            profile.get_role_display(),
        )

    @admin.display(description='账号状态', ordering='is_active')
    def is_active_display(self, obj):
        if obj.is_active:
            return format_html('<span style="color:#2E7D32;font-weight:600;">● {}</span>', '启用')
        return format_html('<span style="color:#9E9E9E;font-weight:600;">● {}</span>', '停用')

    @admin.display(description='最近登录地区')
    def last_region(self, obj):
        record = obj.login_records.order_by('-login_time').first()
        if record is None or not record.region:
            return '—'
        return record.region

    # —— action：重置选中管理员密码为随机强密码（仅超管可进入，权限已受 has_change_permission 门槛控制）——
    # 注：不用 @admin.action 装饰器，Django 6.1 会给函数挂 locations(含 ActionLocation 枚举)，
    #      而 simpleui 的 custom_button 会 json.dumps 该属性导致 "ActionLocation is not JSON serializable"。

    def reset_selected_admin_password(self, request, queryset):
        lines = []
        for user in queryset:
            password = self._random_strong_password()
            user.set_password(password)
            user.save(update_fields=['password'])
            lines.append(f'已将用户 {user.username} 的密码重置为：{password}')
        self.message_user(request, '；'.join(lines) + '，请妥善保管并通知用户')

    reset_selected_admin_password.short_description = '重置选中管理员密码为随机强密码'

    @staticmethod
    def _random_strong_password():
        """生成 12 位随机强密码（至少各含一个大写字母、小写字母、数字）。"""
        alphabet = string.ascii_letters + string.digits
        chars = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
        ] + [secrets.choice(alphabet) for _ in range(9)]
        return ''.join(random.SystemRandom().sample(chars, len(chars)))

    # —— username 仅编辑时只读，新增时可输入 ——
    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return ('username',)
        return []

    # —— 编辑页注入「最近 10 条登录记录」到模板上下文 ——
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, unquote(object_id))
        if obj is not None:
            records = obj.login_records.order_by('-login_time')[:10]
            recent_logins = []
            for rec in records:
                parts = [p for p in (rec.device_type, rec.os_name, rec.browser) if p]
                recent_logins.append({
                    'time': timezone.localtime(rec.login_time).strftime('%Y-%m-%d %H:%M:%S'),
                    'region': rec.region or '—',
                    'device': ' / '.join(parts) or '—',
                    'success': rec.success,
                })
            extra_context['recent_logins'] = recent_logins
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    # —— 只显示 is_staff 用户；非超管只返回自己 ——
    def get_queryset(self, request):
        qs = super().get_queryset(request).filter(is_staff=True)
        if not is_super_admin(request.user):
            qs = qs.filter(pk=request.user.pk)
        return qs

    # —— 访问门槛：仅超级管理员可进入用户管理，普通管理员 403 ——
    def has_module_permission(self, request):
        return is_super_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return is_super_admin(request.user)

    def has_add_permission(self, request):
        return is_super_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_super_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        if not is_super_admin(request.user):
            return False
        if obj is None:
            return True
        # 受保护的超级管理员账号不可删除
        if obj.username == settings.SUPER_ADMIN_USERNAME:
            return False
        # 最后一名超级管理员不可删除
        if is_super_admin(obj) and AdminProfile.objects.filter(role='super_admin').count() <= 1:
            return False
        return True

    # —— 新增时自动 is_staff=True；glowisd 标记保持最高权限 ——
    def save_model(self, request, obj, form, change):
        if not change:
            obj.is_staff = True
        if obj.username == settings.SUPER_ADMIN_USERNAME:
            obj.is_staff = True
            obj.is_superuser = True
        super().save_model(request, obj, form, change)

    # —— 保存时强制 glowisd 的 role 为 super_admin（兜底，即使绕过只读） ——
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if form.instance.username == settings.SUPER_ADMIN_USERNAME:
            profile, _created = AdminProfile.objects.get_or_create(user=form.instance)
            if profile.role != 'super_admin':
                profile.role = 'super_admin'
                profile.save(update_fields=['role'])

    def delete_model(self, request, obj):
        if obj.username == settings.SUPER_ADMIN_USERNAME:
            self.message_user(
                request,
                f'「{settings.SUPER_ADMIN_USERNAME}」是受保护的超级管理员，不可删除。',
                level=messages.WARNING,
            )
            return
        if is_super_admin(obj) and AdminProfile.objects.filter(role='super_admin').count() <= 1:
            self.message_user(
                request,
                '该用户是系统里唯一的超级管理员，无法删除。',
                level=messages.WARNING,
            )
            return
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        # 批量删除时排除受保护账号与唯一的超级管理员
        protected_ids = set(
            User.objects.filter(username=settings.SUPER_ADMIN_USERNAME).values_list('pk', flat=True)
        )
        if AdminProfile.objects.filter(role='super_admin').count() <= 1:
            protected_ids.update(
                AdminProfile.objects.filter(role='super_admin').values_list('user_id', flat=True)
            )
        queryset.exclude(pk__in=protected_ids).delete()
