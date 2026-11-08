from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import Order


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
