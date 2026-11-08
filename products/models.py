from decimal import Decimal

from django.db import models
from django.urls import reverse

from products.utils.watermark import WATERMARK_LOGO_PATH, add_watermark

# 防拍价：产品未定价时统一展示 99999（线上防误拍价），后台改成真实价格后才会开放下单。
PLACEHOLDER_PRICE = Decimal('99999.00')

CURRENCY_CHOICES = [
    ('USD', 'USD — 美元 $'),
    ('CNY', 'CNY — 人民币 ¥'),
    ('EUR', 'EUR — 欧元 €'),
    ('GBP', 'GBP — 英镑 £'),
]
CURRENCY_SYMBOLS = {'USD': '$', 'CNY': '¥', 'EUR': '€', 'GBP': '£'}
CURRENCY_DECIMALS = {'USD': 2, 'CNY': 2, 'EUR': 2, 'GBP': 2}


def format_money(amount, currency='USD'):
    """金额格式化：符号 + 千分位，例 $1,299.00。金额为空时按 0 处理。"""
    if amount is None:
        amount = Decimal('0')
    amount = Decimal(amount)
    symbol = CURRENCY_SYMBOLS.get(currency, '')
    return f'{symbol}{amount:,.{CURRENCY_DECIMALS.get(currency, 2)}f}'


class Category(models.Model):
    name = models.CharField('中文名', max_length=100)
    name_en = models.CharField('英文名', max_length=100)
    slug = models.SlugField('URL标识', unique=True)
    sort_order = models.IntegerField('排序', default=0)

    class Meta:
        verbose_name = '产品分类'
        verbose_name_plural = '产品分类'
        ordering = ['sort_order']

    def __str__(self):
        return self.name


class Product(models.Model):
    sku = models.CharField('SKU编号', max_length=100, unique=True)
    part_name = models.CharField('名称(中文)', max_length=200, blank=True)
    part_name_en = models.CharField('名称(英文)', max_length=200, blank=True)
    pn = models.CharField('P/N件号', max_length=100, blank=True)
    brand = models.CharField('兼容品牌', max_length=100, blank=True)
    weight = models.CharField('重量', max_length=100, blank=True)
    warranty = models.CharField('质保', max_length=100, blank=True)
    description = models.TextField('描述(中文)', blank=True)
    description_en = models.TextField('描述(英文)', blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='products', verbose_name='分类'
    )
    image = models.ImageField('产品图片', upload_to='products/', blank=True, null=True)
    is_watermarked = models.BooleanField('已打水印', default=False)
    featured = models.BooleanField('首页推荐', default=False)
    # —— 定价与支付（后台改价即时生效）——
    price = models.DecimalField(
        '售价', max_digits=12, decimal_places=2, default=PLACEHOLDER_PRICE,
        help_text='未定价的产品保持 99999 防拍价，前台不开放直接下单；改成真实价格后支付按钮自动出现',
    )
    currency = models.CharField('币种', max_length=3, choices=CURRENCY_CHOICES, default='USD')
    payment_link = models.URLField(
        '外部支付链接', blank=True, default='',
        help_text='可选。填写后「立即支付」直接跳转到该链接（如 Stripe Payment Link / PayPal / 收款页）；留空则使用站内收银台',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '产品'
        verbose_name_plural = '产品'
        ordering = ['-created_at']

    def __str__(self):
        return self.sku

    def save(self, *args, **kwargs):
        # 图片变更检测：已存在的记录，若图片文件名与库中不同 → 视为换图，需重新打水印
        if self.pk:
            old_image = Product.objects.filter(pk=self.pk).values_list('image', flat=True).first() or ''
            new_image = self.image.name if self.image else ''
            if old_image != new_image:
                self.is_watermarked = False

        super().save(*args, **kwargs)

        # 自动打水印：有图且尚未标记已打 → 打水印成功后写回标记。
        # 写回用 update_fields 只更新标记字段，且走 super() 而非 self.save()，
        # 避免二次进入本方法造成递归；即使再进来 is_watermarked 已为 True，也不会再触发。
        if self.image and not self.is_watermarked:
            if add_watermark(self.image.path, WATERMARK_LOGO_PATH):
                self.is_watermarked = True
                super().save(update_fields=['is_watermarked', 'updated_at'])

    def display_name(self, lang='zh'):
        name = self.part_name if lang == 'zh' else self.part_name_en
        return name or self.part_name or self.part_name_en or '产品名称待更新'

    # —— 定价 / 支付辅助 ——
    @property
    def is_placeholder_price(self):
        """是否仍为 99999 防拍价（未定价）：是则前台不开放直接下单。"""
        return self.price is None or self.price == PLACEHOLDER_PRICE

    @property
    def price_display(self):
        return format_money(self.price if self.price is not None else PLACEHOLDER_PRICE, self.currency)

    @property
    def currency_symbol(self):
        return CURRENCY_SYMBOLS.get(self.currency, '')

    def get_absolute_pay_url(self):
        """每个产品的固定支付链接（可分享给客户直接下单）。"""
        return reverse('payment_start', args=[self.pk])

    def completeness_percent(self):
        """资料完整度：10 个字段各占 10%（品名中英/描述中英/重量/质保/品牌/PN/分类/图片）。"""
        fields = [
            bool(self.part_name),
            bool(self.part_name_en),
            bool(self.description),
            bool(self.description_en),
            bool(self.weight),
            bool(self.warranty),
            bool(self.brand),
            bool(self.pn),
            # 分类：已关联且非「未分类」才算完整
            (self.category_id is not None and getattr(self.category, 'slug', '') != 'uncategorized'),
            bool(self.image),
        ]
        filled = sum(1 for f in fields if f)
        return int(round(filled / len(fields) * 100))


class ContactMessage(models.Model):
    name = models.CharField('姓名', max_length=100)
    company = models.CharField('公司', max_length=200, blank=True)
    email = models.EmailField('邮箱')
    phone = models.CharField('电话', max_length=50, blank=True)
    country = models.CharField('国家/地区', max_length=100, blank=True)
    category = models.CharField('感兴趣分类', max_length=100, blank=True)
    message = models.TextField('留言')
    is_read = models.BooleanField('已读', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    STATUS_CHOICES = [
        ('new', '新询价'),
        ('contacted', '已联系'),
        ('quoted', '已报价'),
        ('won', '已成交'),
        ('lost', '已流失'),
    ]
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='new')
    quote_amount = models.DecimalField('报价金额', max_digits=12, decimal_places=2, null=True, blank=True)
    lost_reason = models.CharField('流失原因', max_length=200, blank=True, default='')
    inquired_product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='询价产品',
    )
    source_page = models.CharField('来源页面', max_length=200, blank=True, default='')

    class Meta:
        verbose_name = '询价留言'
        verbose_name_plural = '询价留言'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} <{self.email}>'
