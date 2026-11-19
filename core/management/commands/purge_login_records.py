"""清理登录记录（默认保留 365 天，比操作日志更久，用于安全审计）。

用法：
    python manage.py purge_login_records              # 清理 365 天前
    python manage.py purge_login_records --dry-run    # 只看会删多少条
    python manage.py purge_login_records --days 180   # 自定义
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import LoginRecord


class Command(BaseCommand):
    help = '清理超过保留期的登录记录（默认 365 天）'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=365, help='保留天数（默认 365）')
        parser.add_argument('--dry-run', action='store_true', help='只统计不删除')

    def handle(self, *args, **options):
        days = max(int(options['days']), 1)
        cutoff = timezone.now() - timezone.timedelta(days=days)
        queryset = LoginRecord.objects.filter(login_time__lt=cutoff)
        total = queryset.count()
        if options['dry_run']:
            self.stdout.write(f'[dry-run] 早于 {cutoff:%Y-%m-%d %H:%M} 的登录记录共 {total} 条（未删除）')
            return
        deleted, _ = queryset.delete()
        self.stdout.write(f'已清理 {deleted} 条登录记录（保留期 {days} 天），剩余 {LoginRecord.objects.count()} 条')
