"""清理后台操作日志（默认保留 180 天，删除类记录永久保留）。

用法（服务器/本地均可）：
    python manage.py purge_admin_log                 # 清理 180 天前的普通日志
    python manage.py purge_admin_log --dry-run       # 只看会删多少条
    python manage.py purge_admin_log --days 90       # 自定义天数
    python manage.py purge_admin_log --include-deletions   # 连删除记录一起清

保留策略（V0.14.0 与用户确认）：
* 普通操作（添加 / 修改）保留 180 天；
* 删除类（action_flag=3）默认永久保留，除非显式 --include-deletions；
* 由服务器 crontab 每天 03:00 自动执行。
"""
from django.contrib.admin.models import DELETION, LogEntry
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = '清理超过保留期的后台操作日志（默认 180 天，删除记录永久保留）'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=180, help='保留天数（默认 180）')
        parser.add_argument('--dry-run', action='store_true', help='只统计不删除')
        parser.add_argument(
            '--include-deletions', action='store_true',
            help='连删除类日志一起清理（默认永久保留删除记录）',
        )

    def handle(self, *args, **options):
        days = max(int(options['days']), 1)
        cutoff = timezone.now() - timezone.timedelta(days=days)
        queryset = LogEntry.objects.filter(action_time__lt=cutoff)
        if not options['include_deletions']:
            queryset = queryset.exclude(action_flag=DELETION)

        total = queryset.count()
        if options['dry_run']:
            self.stdout.write(f'[dry-run] 早于 {cutoff:%Y-%m-%d %H:%M} 的日志共 {total} 条（未删除）')
            return
        deleted, _ = queryset.delete()
        kept = LogEntry.objects.count()
        self.stdout.write(
            f'已清理 {deleted} 条（保留期 {days} 天，删除记录'
            f'{"已一并清理" if options["include_deletions"] else "永久保留"}），剩余 {kept} 条'
        )
