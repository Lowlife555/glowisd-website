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
