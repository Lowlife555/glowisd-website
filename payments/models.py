"""支付与订单：产品定价后的下单 / 收款记录。

收款方式由后台「订单与收款 → 收款设置」统一切换（PaymentSettings 单例）：

1. 在线收款开启 + 配置了 STRIPE_SECRET_KEY → 五种方式走 Stripe Checkout
   （银行卡：Visa / MasterCard / UnionPay；支付宝；微信支付），真实收款；
2. 在线收款关闭 / 未配密钥 → 只显示「银行转账」，客户看到后台维护的收款账户，
   线下汇款、后台确认到账（订单provider=manual）；
3. 产品单独填了「外部支付链接」→ 该产品直接跳转到外部收款页。

无论哪种方式，订单都会入库，后台「订单与收款 → 订单」可实时看到。
"""

import secrets
from decimal import Decimal

from django.db import models
from django.urls import reverse
from django.utils import timezone

from products.models import CURRENCY_CHOICES, Product, format_money


class PaymentMethod(models.TextChoices):
    VISA = 'visa', 'Visa'
    MASTERCARD = 'mastercard', 'MasterCard'
    UNIONPAY = 'unionpay', '银联 UnionPay'
    ALIPAY = 'alipay', '支付宝 Alipay'
    WECHAT = 'wechat', '微信支付 WeChat Pay'
    BANK_TRANSFER = 'bank_transfer', '银行转账 Bank transfer'


#: 线下汇款：不经过在线通道，客户按后台维护的银行账户自行转账
OFFLINE_METHOD = PaymentMethod.BANK_TRANSFER

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
        'bank_transfer': ('银行转账 Bank transfer', 'Bank transfer'),
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


class PaymentSettings(models.Model):
    """收款设置单例（后台「订单与收款 → 收款设置」）。

    一个开关决定前台收银台呈现哪种收款方式，切换即时生效：
    - online_enabled=True  → 在线收款（Visa / MasterCard / 银联 / 支付宝 / 微信支付）；
    - online_enabled=False → 线下汇款，客户按下面维护的银行账户转账，后台人工确认。
    """

    online_enabled = models.BooleanField(
        '启用在线收款（Stripe）',
        default=False,
        help_text='勾选后前台显示 Visa / MasterCard / 银联 / 支付宝 / 微信支付；'
                  '取消勾选则只显示线下汇款信息，订单进入人工确认。',
    )
    offline_enabled = models.BooleanField(
        '启用线下汇款（银行转账）',
        default=True,
        help_text='关闭在线收款时，前台是否展示银行账户并允许客户提交汇款订单。',
    )
    offline_title_zh = models.CharField(
        '线下汇款标题(中文)', max_length=100, blank=True, default='银行转账（电汇 / T/T）',
    )
    offline_title_en = models.CharField(
        '线下汇款标题(英文)', max_length=100, blank=True, default='Bank transfer (T/T)',
    )
    offline_intro_zh = models.TextField(
        '线下汇款说明(中文)', blank=True, default='',
        help_text='展示在收银台的收款账户上方，例如「提交订单后请按以下账户汇款，'
                  '汇款时请在附言填写订单号，到账后我们安排发货」。',
    )
    offline_intro_en = models.TextField('线下汇款说明(英文)', blank=True, default='')
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '收款设置'
        verbose_name_plural = '收款设置'

    def __str__(self):
        return '收款设置'

    def save(self, *args, **kwargs):
        # 单例：永远只保留 pk=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def title(self, lang='zh'):
        en = self.offline_title_en
        zh = self.offline_title_zh
        return en if lang == 'en' and en else (zh or 'Bank transfer')

    def intro(self, lang='zh'):
        return self.offline_intro_en if lang == 'en' else self.offline_intro_zh


class BankAccount(models.Model):
    """收款银行账户：线下汇款时展示给客户，可随时增删改、停用。"""

    label_zh = models.CharField('账户名称(中文)', max_length=100, blank=True, default='')
    label_en = models.CharField('账户名称(英文)', max_length=100, blank=True, default='')
    bank_name = models.CharField('开户银行', max_length=200)
    account_name = models.CharField('收款人 / 户名', max_length=200)
    account_number = models.CharField('银行账号', max_length=100)
    swift_code = models.CharField('SWIFT / BIC', max_length=40, blank=True, default='')
    iban = models.CharField('IBAN（欧洲账户）', max_length=40, blank=True, default='')
    bank_address = models.CharField('开户行地址', max_length=300, blank=True, default='')
    currency = models.CharField('账户币种', max_length=3, choices=CURRENCY_CHOICES, default='USD')
    note_zh = models.CharField('备注(中文)', max_length=200, blank=True, default='')
    note_en = models.CharField('备注(英文)', max_length=200, blank=True, default='')
    is_active = models.BooleanField('启用', default=True)
    sort_order = models.IntegerField('排序', default=0)
    settings = models.ForeignKey(
        PaymentSettings, on_delete=models.CASCADE, related_name='bank_accounts',
        null=True, blank=True, editable=False, verbose_name='所属收款设置',
    )

    class Meta:
        verbose_name = '收款账户'
        verbose_name_plural = '收款账户'
        ordering = ['sort_order', 'id']

    def __str__(self):
        name = self.label_zh or self.label_en or self.bank_name
        return f'{name} · {self.account_number[-4:]}'

    def label(self, lang='zh'):
        if lang == 'en':
            return self.label_en or self.label_zh or self.bank_name
        return self.label_zh or self.label_en or self.bank_name

    def note(self, lang='zh'):
        return self.note_en if lang == 'en' else self.note_zh

    def save(self, *args, **kwargs):
        if not self.settings_id:
            self.settings = PaymentSettings.load()
        super().save(*args, **kwargs)
