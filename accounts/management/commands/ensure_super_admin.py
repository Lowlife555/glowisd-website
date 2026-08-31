from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import AdminProfile


class Command(BaseCommand):
    help = (
        '确保超级管理员账号存在且 role=super_admin，'
        '并为所有 is_staff 用户补齐 AdminProfile（按 is_superuser 映射角色）。'
    )

    def handle(self, *args, **options):
        username = settings.SUPER_ADMIN_USERNAME

        # 1) 确保受保护的超级管理员账号存在
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'is_staff': True, 'is_superuser': True},
        )
        if created:
            # 初始密码可设初始值；创建后建议尽快修改
            user.set_password(username)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'已创建超级管理员账号 {username}（初始密码同用户名，请尽快修改）'))
        else:
            changed = []
            if not user.is_staff:
                user.is_staff = True
                changed.append('is_staff')
            if not user.is_superuser:
                user.is_superuser = True
                changed.append('is_superuser')
            if changed:
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'已修正超级管理员 {username} 的标记：{", ".join(changed)}')
                )
            else:
                self.stdout.write(f'超级管理员 {username} 已存在（is_staff/is_superuser 正常）')

        # 2) 确保其 AdminProfile 存在且 role=super_admin
        profile, profile_created = AdminProfile.objects.get_or_create(
            user=user, defaults={'role': 'super_admin'}
        )
        if profile.role != 'super_admin':
            profile.role = 'super_admin'
            profile.save(update_fields=['role'])
            self.stdout.write(self.style.SUCCESS(f'已把 {username} 的 role 强制为 super_admin'))
        else:
            self.stdout.write(f'{username} 的 AdminProfile 已就绪（role=super_admin）')

        # 3) 为所有 staff 用户补齐 AdminProfile（role 按 is_superuser 映射）
        self._backfill_profiles()

        self.stdout.write(self.style.SUCCESS('ensure_super_admin 完成'))

    def _backfill_profiles(self):
        for u in User.objects.filter(is_staff=True).order_by('username'):
            role = 'super_admin' if u.is_superuser else 'admin'
            profile, created = AdminProfile.objects.get_or_create(
                user=u, defaults={'role': role}
            )
            if created:
                self.stdout.write(f'已为 {u.username} 创建 AdminProfile（{profile.get_role_display()}）')
