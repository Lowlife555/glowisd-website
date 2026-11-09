from django.conf import settings
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, mark_safe

from . import gateway
from .models import BankAccount, Order, PaymentSettings


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_no', 'sku', 'product_name', 'quantity', 'amount_display_col',
        'method', 'status', 'provider', 'customer_email', 'created_at',
    ]
    list_editable = ['status']
    list_filter = ['status', 'method', 'provider', 'currency', 'created_at']
    search_fields = ['order_no', 'sku', 'customer_name', 'customer_email', 'provider_ref']
    date_hierarchy = 'created_at'
    list_per_page = 30
    ordering = ['-created_at']

    readonly_fields = [
        'order_no', 'sku', 'product_name', 'quantity', 'unit_price', 'amount',
        'currency', 'method', 'provider', 'provider_ref',
        'customer_name', 'customer_email', 'customer_phone', 'customer_country',
        'created_at', 'paid_at',
    ]
    fieldsets = (
        ('订单信息', {'fields': ('order_no', 'product', 'sku', 'product_name', 'quantity',
                              'unit_price', 'amount', 'currency')}),
        ('支付', {
            'fields': ('method', 'provider', 'provider_ref', 'status', 'created_at', 'paid_at'),
            'description': '线下收款到账后，把「订单状态」改成「已支付」即可（支付时间自动写入）。',
        }),
        ('客户', {'fields': ('customer_name', 'customer_email', 'customer_phone',
                          'customer_country', 'note')}),
    )

    STATUS_COLORS = {
        'pending': '#E67E22',
        'paid': '#27AE60',
        'cancelled': '#7F8C8D',
        'refunded': '#8E44AD',
        'failed': '#A93226',
    }

    def has_add_permission(self, request):
        # 订单只能由前台下单产生，后台不手工新增
        return False

    @admin.display(description='金额', ordering='amount')
    def amount_display_col(self, obj):
        return obj.amount_display

    def save_model(self, request, obj, form, change):
        # 状态改成「已支付」时自动补支付时间；改回其他状态则清空
        if obj.status == 'paid' and not obj.paid_at:
            obj.paid_at = timezone.now()
        elif obj.status != 'paid':
            obj.paid_at = None
        super().save_model(request, obj, form, change)


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    """收款账户：线下汇款时展示给客户的银行账户，可随时增删改、停用。

    入口：后台「订单与收款 → 收款账户」。
    """

    list_display = ['label_col', 'bank_name', 'account_number_col', 'currency_display',
                    'swift_code', 'is_active', 'sort_order']
    list_display_links = ['label_col']
    list_editable = ['is_active', 'sort_order']
    list_filter = ['is_active', 'currency']
    search_fields = ['label_zh', 'label_en', 'bank_name', 'account_name', 'account_number']
    list_per_page = 20
    ordering = ['sort_order', 'id']
    fieldsets = (
        ('账户标识', {
            'fields': (('label_zh', 'label_en'), 'bank_name', 'account_name', 'account_number'),
        }),
        ('跨境信息（可选）', {
            'fields': (('swift_code', 'iban'), 'bank_address', 'currency'),
            'description': '外贸电汇通常需要 SWIFT/BIC 与开户行地址；欧洲账户可填 IBAN。',
        }),
        ('展示与排序', {
            'fields': (('note_zh', 'note_en'), ('is_active', 'sort_order')),
            'description': '停用后前台收银台立即不再显示该账户（历史订单不受影响）。',
        }),
    )

    @admin.display(description='账户名称')
    def label_col(self, obj):
        return obj.label_zh or obj.label_en or obj.bank_name

    @admin.display(description='银行账号')
    def account_number_col(self, obj):
        no = obj.account_number or ''
        return f'…{no[-6:]}' if len(no) > 6 else no

    @admin.display(description='币种')
    def currency_display(self, obj):
        return obj.currency


@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    """收款设置单例：一个开关切换「在线收款 / 线下汇款」。

    入口：后台「订单与收款 → 收款设置」。保存后立即对前台生效，无需重启。
    """

    readonly_fields = ['status_box', 'accounts_box', 'updated_at']
    fieldsets = (
        ('价格展示', {
            'fields': ('show_prices',),
            'description': '一键开关：取消勾选后，产品卡、详情页与收银台全部隐藏价格和购买按钮，'
                           '改为「价格面议 / 联系我们获取报价」；重新勾选即恢复。历史订单金额不受影响。',
        }),
        ('在线收款', {
            'fields': ('online_enabled', 'status_box'),
            'description': '勾选「启用在线收款」且服务器已配置 Stripe 密钥时，前台显示 '
                           'Visa / MasterCard / 银联 / 支付宝 / 微信支付；取消勾选则关闭在线收款。',
        }),
        ('线下汇款', {
            'fields': ('offline_enabled', 'offline_title_zh', 'offline_title_en',
                       'offline_intro_zh', 'offline_intro_en', 'accounts_box'),
            'description': '关闭在线收款时，前台收银台只显示银行转账：客户提交订单后按「收款账户」'
                           '汇款，到账后在「订单」里把状态改为「已支付」。',
        }),
    )

    @admin.display(description='收款账户')
    def accounts_box(self, obj):
        total = BankAccount.objects.count()
        active = BankAccount.objects.filter(is_active=True).count()
        url = reverse('admin:payments_bankaccount_changelist')
        add_url = reverse('admin:payments_bankaccount_add')
        if active:
            summary = f'已启用 <b>{active}</b> 个收款账户（共 {total} 个），前台收银台会依次展示。'
        elif total:
            summary = '收款账户全部处于停用状态，前台会显示「收款账户正在配置中」。'
        else:
            summary = ('还没有收款账户。关闭在线收款后，客户将看不到可汇款的银行账号，'
                       '请先添加至少一个。')
        return format_html(
            '<div style="line-height:1.9;font-size:13px">{}'
            '<div style="margin-top:10px">'
            '<a href="{}" style="display:inline-block;margin-right:8px;padding:6px 14px;'
            'background:#f2f3f5;color:#1f2d3d !important;border:1px solid #dcdfe6;'
            'border-radius:3px;font-size:12px;text-decoration:none">管理收款账户</a>'
            '<a href="{}" style="display:inline-block;padding:6px 14px;background:#1f2d3d;'
            'color:#fff !important;border-radius:3px;font-size:12px;text-decoration:none">'
            '新增收款账户</a>'
            '</div></div>',
            mark_safe(summary), url, add_url,
        )

    def has_add_permission(self, request):
        if PaymentSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = PaymentSettings.load()
        return redirect(reverse('admin:payments_paymentsettings_change', args=[obj.pk]))

    @admin.display(description='连接状态')
    def status_box(self, obj):
        key_mode = gateway.stripe_key_mode()
        configured = gateway.stripe_configured()
        webhook = bool(getattr(settings, 'STRIPE_WEBHOOK_SECRET', ''))
        probe_url = reverse('admin:payments_paymentsettings_probe')
        state = '已开启' if obj.online_enabled else '已关闭'
        key_text = {'live': '已配置（LIVE 真实收款）',
                    'test': '已配置（TEST 测试模式）'}.get(key_mode, '未配置')
        rows = [
            f'<b>前台价格显示：</b>{"显示价格" if obj.show_prices else "已隐藏（价格面议）"}',
            f'<b>在线收款开关：</b>{state}',
            f'<b>Stripe 密钥：</b>{key_text}',
            f'<b>Webhook 密钥：</b>{"已配置" if webhook else "未配置（支付结果以回跳核对兜底）"}',
            f'<b>回调地址：</b>https://glowisd.cn/pay/webhook/stripe/',
        ]
        body = mark_safe(
            '<div style="line-height:1.9;font-size:13px">' + '<br>'.join(rows) + '</div>'
        )
        if configured:
            link = format_html(
                '<a href="{}" style="display:inline-block;margin-top:10px;padding:6px 16px;'
                'background:#c9a227;color:#1f2d3d !important;border-radius:3px;font-size:12px;'
                'font-weight:600;text-decoration:none">检测 Stripe 连接</a>', probe_url,
            )
        else:
            link = mark_safe(
                '<p style="margin:6px 0 0;color:#8a6d3b">尚未配置 STRIPE_SECRET_KEY：'
                '即使打开在线收款开关，前台也会自动回落到线下汇款。</p>'
            )
        return format_html('{}{}', body, link)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('probe-stripe/', self.admin_site.admin_view(self.probe_stripe_view),
                 name='payments_paymentsettings_probe'),
        ]
        return custom + urls

    def probe_stripe_view(self, request):
        back = redirect(reverse('admin:payments_paymentsettings_change', args=[1]))
        if not gateway.stripe_configured():
            messages.error(request, '未配置 STRIPE_SECRET_KEY，无法检测。')
            return back
        try:
            info = gateway.probe_stripe()
        except Exception as exc:  # 密钥无效 / 网络不通 / 权限不足
            messages.error(request, f'连接失败：{exc}')
            return back
        messages.success(
            request,
            '连接成功：账户 {id} · 国家 {country} · 默认币种 {currency} · 模式 {mode}。'
            '注意：到账银行账户不在这里设置，而在 Stripe 后台 '
            'Settings → Payouts 指定。'.format(
                id=info['id'] or '-', country=info['country'] or '-',
                currency=info['default_currency'] or '-',
                mode='LIVE 真实收款' if info['mode'] == 'live' else 'TEST 测试模式',
            ),
        )
        return back
