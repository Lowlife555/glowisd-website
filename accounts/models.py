from django.contrib.auth.models import User
from django.db import models


class AdminProfile(models.Model):
    """管理员的角色资料：取代纯 is_superuser 判断的角色体系。

    role 取值：
      - super_admin  超级管理员（可管理其他管理员）
      - admin        普通管理员（不可访问用户管理）
      - viewer       只读管理员
    """

    ROLE_CHOICES = [
        ('super_admin', '超级管理员'),
        ('admin', '普通管理员'),
        ('viewer', '只读管理员'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='admin_profile',
        verbose_name='用户',
    )
    role = models.CharField(
        '角色',
        max_length=20,
        choices=ROLE_CHOICES,
        default='admin',
    )
    phone = models.CharField('电话', max_length=30, blank=True, default='')
    must_change_password = models.BooleanField('需修改密码', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '管理员资料'
        verbose_name_plural = '管理员资料'

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'
