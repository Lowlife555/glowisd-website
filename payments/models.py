"""支付与订单：产品定价后的下单 / 收款记录。

支付通道采用「可配置 + 优雅降级」：
- 配置了 STRIPE_SECRET_KEY → 五种方式走 Stripe Checkout（银行卡：Visa / MasterCard / UnionPay；
  支付宝；微信支付），真实收款；
- 产品填了「外部支付链接」→ 直接跳转到该链接（Stripe Payment Link / PayPal / 收款页均可）；
- 两者都没有 → 生成订单进入「人工确认」，客服线下收款后后台标记已支付。

无论哪种方式，订单都会入库，后台「订单管理」可实时看到。
"""

import secrets
from decimal import Decimal

from django.db import models
from django.urls import reverse
from django.utils import timezone

from products.models import Product, format_money


class PaymentMethod(models.TextChoices):
    VISA = 'visa', 'Visa'
    MASTERCARD = 'mastercard', 'MasterCard'
    UNIONPAY = 'unionpay', '银联 UnionPay'
    ALIPAY = 'alipay', '支付宝 Alipay'
    WECHAT = 'wechat', '微信支付 WeChat Pay'


#: 银行卡类支付方式（Stripe 里统一走 card，具体卡组织由收单行/Stripe 决定）
CARD_METHODS = {PaymentMethod.VISA, PaymentMethod.MASTERCARD, PaymentMethod.UNIONPAY}

#: 方法 → Stripe Checkout 的 payment_method_types
STRIPE_PAYMENT_METHOD_TYPES = {
    PaymentMethod.VISA: ['card'],
    PaymentMethod.MASTERCARD: ['card'],
    PaymentMethod.UNIONPAY: ['card'],
    PaymentMethod.ALIPAY: ['alipay'],
    PaymentMethod.WECHAT: ['wechat_pay'],
}


def _new_order_no():
    stamp = timezone.localtime().strftime('%Y%m%d')
    token = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
    return f'GW{stamp}-{token}'


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', '待支付'),
        ('paid', '已支付'),
        ('cancelled', '已取消'),
        ('refunded', '已退款'),
        ('failed', '支付失败'),
    ]

    PROVIDER_CHOICES = [
        ('stripe', 'Stripe 在线收银台'),
        ('external_link', '外部支付链接'),
        ('manual', '人工确认'),
    ]

    order_no = models.CharField('订单号', max_length=32, unique=True, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders', verbose_name='产品',
    )
    # 下单时的产品快照：产品改名/改价/删除后，历史订单仍可核对
    sku = models.CharField('SKU(快照)', max_length=100)
    product_name = models.CharField('产品名称(快照)', max_length=200, blank=True, default='')
    quantity = models.PositiveIntegerField('数量', default=1)
    unit_price = models.DecimalField('单价', max_digits=12, decimal_places=2)
    amount = models.DecimalField('应付金额', max_digits=12, decimal_places=2)
    currency = models.CharField('币种', max_length=3, default='USD')

    method = models.CharField('支付方式', max_length=20, choices=PaymentMethod.choices)
    status = models.CharField('订单状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    provider = models.CharField('收款通道', max_length=20, choices=PROVIDER_CHOICES, default='manual')
    provider_ref = models.CharField('通道流水号', max_length=200, blank=True, default='')

    customer_name = models.CharField('客户名称', max_length=100, blank=True, default='')
    customer_email = models.EmailField('客户邮箱', blank=True, default='')
    customer_phone = models.CharField('联系电话', max_length=50, blank=True, default='')
    customer_country = models.CharField('国家/地区', max_length=100, blank=True, default='')
    note = models.CharField('备注', max_length=500, blank=True, default='')

    created_at = models.DateTimeField('下单时间', auto_now_add=True)
    paid_at = models.DateTimeField('支付时间', null=True, blank=True)

    class Meta:
        verbose_name = '订单'
        verbose_name_plural = '订单'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order_no} · {self.sku} · {self.get_status_display()}'

    def save(self, *args, **kwargs):
        if not self.order_no:
            self.order_no = _new_order_no()
            # 极小概率撞号：重新生成一次
            while Order.objects.filter(order_no=self.order_no).exists():
                self.order_no = _new_order_no()
        super().save(*args, **kwargs)

    @property
    def amount_display(self):
        return format_money(self.amount, self.currency)

    @property
    def unit_price_display(self):
        return format_money(self.unit_price, self.currency)

    @property
    def is_paid(self):
        return self.status == 'paid'

    STATUS_LABELS = {
        'pending': ('待支付', 'Awaiting payment'),
        'paid': ('已支付', 'Paid'),
        'cancelled': ('已取消', 'Cancelled'),
        'refunded': ('已退款', 'Refunded'),
        'failed': ('支付失败', 'Failed'),
    }

    METHOD_LABELS = {
        'visa': ('Visa', 'Visa'),
        'mastercard': ('MasterCard', 'MasterCard'),
        'unionpay': ('银联 UnionPay', 'UnionPay'),
        'alipay': ('支付宝 Alipay', 'Alipay'),
        'wechat': ('微信支付 WeChat Pay', 'WeChat Pay'),
    }

    def status_label(self, lang='zh'):
        zh, en = self.STATUS_LABELS.get(self.status, (self.status, self.status))
        return en if lang == 'en' else zh

    def method_label(self, lang='zh'):
        zh, en = self.METHOD_LABELS.get(self.method, (self.method, self.method))
        return en if lang == 'en' else zh

    def mark_paid(self, provider_ref=''):
        """幂等标记为已支付（webhook / 回跳校验 / 后台手动都会调用）。"""
        if self.status == 'paid':
            return False
        self.status = 'paid'
        self.paid_at = timezone.now()
        if provider_ref:
            self.provider_ref = provider_ref
        self.save(update_fields=['status', 'paid_at', 'provider_ref'])
        return True

    def get_success_url(self):
        return reverse('payment_success', args=[self.order_no])
