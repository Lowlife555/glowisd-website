"""Sitemap 定义（django.contrib.sitemaps）：静态页面 + 全部产品详情页。

收录入口：/sitemap.xml（robots.txt 中声明）。
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from products.models import Product


class StaticViewSitemap(Sitemap):
    """前台静态页：首页/产品列表/工厂/定制/联系。"""

    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return ['home', 'product_list', 'factory', 'custom', 'contact']

    def location(self, item):
        return reverse(item)


class ProductSitemap(Sitemap):
    """全部产品详情页（182 个，搜索引擎逐个收录）。"""

    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return Product.objects.all().order_by('pk')

    def location(self, obj):
        return reverse('product_detail', args=[obj.pk])

    def lastmod(self, obj):
        return obj.updated_at
