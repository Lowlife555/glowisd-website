from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.views.generic import RedirectView

from core.sitemaps import ProductSitemap, StaticViewSitemap

sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
}

urlpatterns = [
    # 浏览器默认请求 /favicon.ico（不读 link 标签）→ 重定向到静态 favicon，消除 404 噪音
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),
    # SEO：搜索引擎收录入口（robots.txt 中声明 Sitemap 地址）
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('', include('products.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
