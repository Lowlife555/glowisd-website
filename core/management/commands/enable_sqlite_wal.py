"""把 SQLite 切到 WAL 模式（一次性设置，持久生效）。

为什么：默认 journal_mode=delete 下，写操作（后台保存、询价单入库）会锁住整个库，
并发的读请求要排队等锁。WAL 让读不被写阻塞，多人同时浏览时更稳。

用法：
    python manage.py enable_sqlite_wal          # 查看当前模式并在需要时切换
    python manage.py enable_sqlite_wal --check  # 只查看，不改

注：WAL 是数据库文件属性，切换后一直有效，不需要每次启动都跑。
    会额外生成 db.sqlite3-wal / db.sqlite3-shm 两个文件，属正常现象。
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = '把 SQLite 数据库切换到 WAL 日志模式（提升并发读写）'

    def add_arguments(self, parser):
        parser.add_argument('--check', action='store_true', help='只查看当前模式，不修改')

    def handle(self, *args, **options):
        if connection.vendor != 'sqlite':
            self.stdout.write(self.style.WARNING(
                f'当前数据库是 {connection.vendor}，WAL 只对 SQLite 有意义，跳过。'))
            return

        with connection.cursor() as cur:
            cur.execute('PRAGMA journal_mode')
            current = cur.fetchone()[0]
            self.stdout.write(f'当前 journal_mode: {current}')

            if options['check']:
                return
            if current.lower() == 'wal':
                self.stdout.write(self.style.SUCCESS('已经是 WAL 模式，无需修改。'))
                return

            cur.execute('PRAGMA journal_mode=WAL')
            new_mode = cur.fetchone()[0]
            cur.execute('PRAGMA synchronous=NORMAL')
            cur.execute('PRAGMA busy_timeout=5000')

        self.stdout.write(self.style.SUCCESS(f'已切换 journal_mode: {current} → {new_mode}'))
        self.stdout.write('提示：synchronous=NORMAL 只对当前连接生效，'
                          '如需长期生效可在 settings 的 DATABASES OPTIONS 里配置。')
