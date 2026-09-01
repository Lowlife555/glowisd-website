from django.contrib.auth.models import User
from django.db import models


class HeroSlide(models.Model):
    image = models.ImageField('轮播图片', upload_to='hero/')
    title_zh = models.CharField('标题(中文)', max_length=200, blank=True)
    title_en = models.CharField('标题(英文)', max_length=200, blank=True)
    sort_order = models.IntegerField('排序', default=0)
    is_active = models.BooleanField('启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '首页轮播图'
        verbose_name_plural = '首页轮播图'
        ordering = ['sort_order', '-created_at']

    def __str__(self):
        return f'Slide {self.sort_order} - {self.title_zh or self.title_en or "未命名"}'


class LoginRecord(models.Model):
    """管理员后台登录记录（成功/失败都记录：登录时间 / IP / 设备）"""
    # 失败登录无用户对象，故 user 可空；成功登录才关联 User
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='管理员', related_name='login_records'
    )
    login_time = models.DateTimeField('登录时间', auto_now_add=True)
    ip_address = models.GenericIPAddressField('IP 地址', blank=True, null=True)
    user_agent = models.CharField('设备/浏览器', max_length=500, blank=True)
    # 以下 4 字段为登录审计增强，历史记录不回填，保持空字符串
    device_type = models.CharField('设备类型', max_length=20, blank=True, default='')
    os_name = models.CharField('操作系统', max_length=50, blank=True, default='')
    browser = models.CharField('浏览器', max_length=50, blank=True, default='')
    region = models.CharField('登录地区', max_length=100, blank=True, default='')
    # 阶段二：登录追踪增强（成功/失败都记录），历史数据留空/默认成功，不回填
    username_attempted = models.CharField('尝试用户名', max_length=150, blank=True, default='')
    success = models.BooleanField('登录成功', default=True)
    fail_reason = models.CharField('失败原因', max_length=100, blank=True, default='')

    class Meta:
        verbose_name = '登录记录'
        verbose_name_plural = '登录记录'
        ordering = ['-login_time']

    def __str__(self):
        if self.user_id:
            return f'{self.user.username} @ {self.login_time.strftime("%Y-%m-%d %H:%M:%S")}'
        label = self.username_attempted or '未知用户'
        status = '成功' if self.success else '失败'
        return f'{label}({status}) @ {self.login_time.strftime("%Y-%m-%d %H:%M:%S")}'


class SiteSettings(models.Model):
    """站点设置单例：公司信息 / 联系方式 / SEO / 生产信息 / 水印（始终只有 pk=1 一条）。"""

    WATERMARK_POSITION_CHOICES = [
        ('bottom_right', '右下角'),
        ('bottom_left', '左下角'),
        ('top_right', '右上角'),
        ('top_left', '左上角'),
        ('center', '居中'),
    ]

    company_name_zh = models.CharField('公司名(中文)', max_length=200, blank=True, default='')
    company_name_en = models.CharField('公司名(英文)', max_length=200, blank=True, default='')
    address_zh = models.CharField('地址(中文)', max_length=200, blank=True, default='')
    address_en = models.CharField('地址(英文)', max_length=200, blank=True, default='')
    phone = models.CharField('电话', max_length=50, blank=True, default='')
    email = models.CharField('邮箱', max_length=100, blank=True, default='')
    whatsapp = models.CharField('WhatsApp', max_length=100, blank=True, default='')
    factory_area = models.CharField('工厂面积', max_length=50, blank=True, default='')
    moq = models.CharField('起订量', max_length=50, blank=True, default='')
    about_zh = models.TextField('公司简介(中文)', blank=True, default='')
    about_en = models.TextField('公司简介(英文)', blank=True, default='')
    seo_title_zh = models.CharField('SEO标题(中文)', max_length=200, blank=True, default='')
    seo_title_en = models.CharField('SEO标题(英文)', max_length=200, blank=True, default='')
    seo_desc_zh = models.TextField('SEO描述(中文)', blank=True, default='')
    seo_desc_en = models.TextField('SEO描述(英文)', blank=True, default='')
    # —— 水印设置（产品图水印）——
    watermark_enabled = models.BooleanField('启用水印', default=False)
    watermark_image = models.ImageField('水印图片', upload_to='watermark/', blank=True, null=True)
    watermark_position = models.CharField(
        '水印位置', max_length=20, choices=WATERMARK_POSITION_CHOICES, default='bottom_right',
    )
    watermark_opacity = models.IntegerField('水印透明度(%)', default=45)
    watermark_width_pct = models.PositiveIntegerField('水印宽度(%)', default=18)
    watermark_margin = models.PositiveIntegerField('水印边距(px)', default=20)

    class Meta:
        verbose_name = '站点设置'
        verbose_name_plural = '站点设置'

    def __str__(self):
        return self.company_name_zh or self.company_name_en or '站点设置'

    @classmethod
    def load(cls):
        """取（或首次创建）唯一的站点设置实例。"""
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj
