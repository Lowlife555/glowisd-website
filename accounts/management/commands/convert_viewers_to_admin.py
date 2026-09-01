from django.core.management.base import BaseCommand

from accounts.models import AdminProfile


class Command(BaseCommand):
    help = '把历史 viewer 角色批量转为 admin（V0.6.0 起后台不再新增 viewer）'

    def handle(self, *args, **options):
        converted = 0
        skipped = 0
        # 遍历 viewer + admin（不碰 super_admin）：viewer 转 admin，admin 跳过
        for profile in AdminProfile.objects.filter(role__in=('viewer', 'admin')).order_by('user__username'):
            if profile.role == 'viewer':
                profile.role = 'admin'
                profile.save(update_fields=['role'])
                converted += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(f'已转换 {converted} 条 viewer → admin / 跳过 {skipped} 条（已是 admin）')
        )
