"""清空站点缓存（整页缓存 + 登录限流计数）。

什么时候用：
- 部署后想让内容立刻生效，不等 120 秒整页缓存过期；
- 后台改完页面发现前台没变，想立刻刷新；
- 登录限流误封了某个人，想立刻解除。

用法：
    python manage.py clear_site_cache
"""

from django.core.cache import cache
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = '清空站点缓存（整页缓存与登录限流计数），用于部署后立即生效或解除误封'

    def handle(self, *args, **options):
        cache.clear()
        self.stdout.write(self.style.SUCCESS('站点缓存已清空。'))
