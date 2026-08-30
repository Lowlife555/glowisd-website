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
    """管理员后台登录记录（登录时间 / IP / 设备）"""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name='管理员', related_name='login_records'
    )
    login_time = models.DateTimeField('登录时间', auto_now_add=True)
    ip_address = models.GenericIPAddressField('IP 地址', blank=True, null=True)
    user_agent = models.CharField('设备/浏览器', max_length=500, blank=True)
    # 以下 4 字段为登录审计增强，历史记录不回填，保持空字符串
    device_type = models.CharField('设备类型', max_length=20, blank=True, default='')
    os_name = models.CharField('操作系统', max_length=50, blank=True, default='')
    browser = models.CharField('浏览器', max_length=50, blank=True, default='')
    region = models.CharField('登录地区', max_length=100, blank=True, default='')

    class Meta:
        verbose_name = '登录记录'
        verbose_name_plural = '登录记录'
        ordering = ['-login_time']

    def __str__(self):
        return f'{self.user.username} @ {self.login_time.strftime("%Y-%m-%d %H:%M:%S")}'
