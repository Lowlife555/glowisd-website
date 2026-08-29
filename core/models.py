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
