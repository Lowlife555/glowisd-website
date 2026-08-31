from django.db import models


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
    featured = models.BooleanField('首页推荐', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '产品'
        verbose_name_plural = '产品'
        ordering = ['-created_at']

    def __str__(self):
        return self.sku

    def display_name(self, lang='zh'):
        name = self.part_name if lang == 'zh' else self.part_name_en
        return name or self.part_name or self.part_name_en or '产品名称待更新'

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
